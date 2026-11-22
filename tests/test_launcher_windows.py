# SPDX-License-Identifier: GPL-3.0-or-later
"""The Windows launcher's log path, as far as it can be driven off Windows (a0.6.3 G5).

    python3 -m unittest tests.test_launcher_windows

serve.bat hands over to lib/launcher.py, which starts serve.py with its output
in a pipe, copied to the window and to serve.log (serve_logged, faultlog.pump).
Nobody has run that on Windows yet.  What only Windows does is stood in for
here: the ANSI code page a pipe gets (an outer PYTHONIOENCODING that cannot
write Persian), the console's Ctrl-C reaching both processes (KeyboardInterrupt
in the launcher, STATUS_CONTROL_C_EXIT from the server), an update that stops
the server and starts it again in the same window, and a new version that does
not come up and is undone.  The server in start() is a stand-in process object;
serve_logged's own child is a real Python.

On the old code: the Persian line ended the child (UnicodeEncodeError); a
Ctrl-C while starting was a traceback; a Ctrl-C answered with 0xC000013A made
serve.bat hold the window as for a failure; the version started again after an
undone update rotated away the log of the one that failed.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("lib", "."):
    if str(ROOT / p) not in sys.path:
        sys.path.insert(0, str(ROOT / p))
import launcher  # noqa: E402
import updater   # noqa: E402

CTRL_C_EXIT = 0xC000013A


class APipeIsNotTheConsole(unittest.TestCase):
    def run_child(self, code, outer):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "serve.log")
            console = io.BytesIO()
            proc, copier = launcher.serve_logged([sys.executable, "-u", "-c", code], rotate=True,
                                                 log=log, console=console, env=outer)
            rc = proc.wait(20)
            copier.join(20)
            return rc, Path(log).read_bytes(), console.getvalue()

    def test_a_persian_line_reaches_the_log_whatever_the_outer_encoding(self):
        # Windows gives a pipe the ANSI code page (cp1252), which has no Persian; an outer setting that
        # cannot write it stands in for that here
        outer = dict(os.environ, PYTHONIOENCODING="ascii")
        rc, log, console = self.run_child("print('کتاب: سلام دنیا'); print('after')", outer)
        self.assertEqual(rc, 0, log.decode("utf-8", "replace"))
        self.assertEqual(log.decode("utf-8"), "کتاب: سلام دنیا\nafter\n")
        self.assertEqual(console, log)

    def test_a_character_utf8_cannot_write_does_not_end_the_server(self):
        rc, log, _ = self.run_child("print('bad name: ' + 'x\\udcff'); print('after')", dict(os.environ))
        self.assertEqual(rc, 0, log.decode("utf-8", "replace"))
        self.assertEqual(log.decode("utf-8"), "bad name: x\\udcff\nafter\n")

    def test_the_server_stays_in_the_consoles_process_group(self):
        # CREATE_NEW_PROCESS_GROUP (0x200) would keep the console's Ctrl-C from the server
        seen = {}

        class Proc:
            stdout = io.BytesIO(b"")

        def popen(cmd, **kw):
            seen.update(kw)
            return Proc()
        with tempfile.TemporaryDirectory() as td, patch.object(launcher.subprocess, "Popen", popen), \
                patch.object(launcher.os, "name", "nt"):
            _, copier = launcher.serve_logged(["serve.py"], log=os.path.join(td, "serve.log"), console=io.BytesIO())
            copier.join(5)
        self.assertFalse(seen.get("creationflags", 0) & 0x200)
        self.assertNotIn("start_new_session", seen)
        self.assertIs(seen["stdout"], subprocess.PIPE)
        self.assertIs(seen["stderr"], subprocess.STDOUT)
        self.assertEqual(seen["env"]["PYTHONIOENCODING"], "utf-8:backslashreplace")


class FakeProc:
    """A server in start(): `waits` is what each wait() gives back or raises, in turn."""
    def __init__(self, waits=(0,), poll=None):
        self.waits, self._poll, self.calls = list(waits), poll, []

    def poll(self):
        return self._poll

    def wait(self, timeout=None):
        self.calls.append(("wait", timeout))
        what = self.waits.pop(0) if self.waits else 0
        if isinstance(what, BaseException) or (isinstance(what, type) and issubclass(what, BaseException)):
            raise what
        self._poll = what
        return what

    def terminate(self):
        self.calls.append(("terminate",))

    def kill(self):
        self.calls.append(("kill",))


class Copier:
    def __init__(self, log):
        self.log = log

    def join(self, timeout=None):
        self.log.append("join")


class Start(unittest.TestCase):
    """start() with the server, its address and the browser stood in for."""
    def setUp(self):
        self.said, self.events, self.rotates, self.procs = [], [], [], []
        self.urls = []
        for name, value in (("say", lambda s="": self.said.append(s)), ("find_tailscale", lambda: None),
                            ("have_cert", lambda: True), ("server_url", self.server_url),
                            ("serve_logged", self.serve_logged)):
            p = patch.object(launcher, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(launcher.webbrowser, "open", lambda url: self.events.append("browser"))
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(launcher.time, "sleep", lambda s: None)
        p.start()
        self.addCleanup(p.stop)

    def server_url(self, port):
        what = self.urls.pop(0) if self.urls else None
        if isinstance(what, type) and issubclass(what, BaseException):
            raise what
        return what

    def serve_logged(self, cmd, rotate=True):
        self.rotates.append(rotate)
        self.events.append("serve")
        return self.procs.pop(0), Copier(self.events)

    def test_ctrl_c_while_it_is_starting_stops_it_without_a_traceback(self):
        proc = FakeProc(waits=[CTRL_C_EXIT])
        self.procs, self.urls = [proc], [None, KeyboardInterrupt]
        self.assertEqual(launcher.start(7654), 0)
        self.assertEqual(self.said[-1], "stopped.")
        self.assertIn("join", self.events)

    def test_ctrl_c_once_it_is_up_is_a_stop_not_a_failure(self):
        # the console's Ctrl-C reaches both: the launcher's wait is interrupted, the server leaves with
        # STATUS_CONTROL_C_EXIT -- serve.bat must not hold the window as for a failure
        for code in (0, CTRL_C_EXIT):
            with self.subTest(code=code):
                proc = FakeProc(waits=[KeyboardInterrupt, code])
                self.procs, self.urls, self.events = [proc], [None, "https://localhost:7654/"], []
                self.assertEqual(launcher.start(7654), 0)
                self.assertEqual(proc.calls[1], ("wait", 10))
                self.assertNotIn(("terminate",), proc.calls)

    def test_a_server_that_does_not_stop_after_ctrl_c_is_ended(self):
        proc = FakeProc(waits=[KeyboardInterrupt, subprocess.TimeoutExpired("serve.py", 10), 1])
        self.procs, self.urls = [proc], [None, "https://localhost:7654/"]
        self.assertEqual(launcher.start(7654), 0)
        self.assertIn(("terminate",), proc.calls)

    def test_a_failure_is_still_a_failure(self):
        proc = FakeProc(waits=[1])
        self.procs, self.urls = [proc], [None, "https://localhost:7654/"]
        self.assertEqual(launcher.start(7654), 1)

    def test_an_update_runs_in_the_same_window_and_the_log_goes_on(self):
        old, new = FakeProc(waits=[updater.LAUNCHER_EXIT]), FakeProc(waits=[0])
        self.procs = [old, new]
        self.urls = [None, "https://localhost:7654/", None, "https://localhost:7654/"]
        with patch.object(updater, "running", lambda root: "job-1"), \
                patch.object(updater, "run_helper", lambda root: self.events.append("helper") or 0):
            self.assertEqual(launcher.start(7654), 0)
        self.assertEqual(self.rotates, [True, False])                       # the same serve.log after the update
        self.assertEqual(self.events, ["serve", "browser", "join", "helper", "serve", "join"])

    def test_an_update_that_does_not_come_up_is_undone_in_the_same_log(self):
        failed, back = FakeProc(waits=[1], poll=1), FakeProc(waits=[0])
        self.procs = [failed, back]
        self.urls = [None, None, "https://localhost:7654/"]
        calls = []
        with tempfile.TemporaryDirectory() as td:
            helper = Path(td) / updater.WORK / "helper.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("")
            with patch.object(launcher, "ROOT", td), \
                    patch.object(launcher.subprocess, "call", lambda cmd, cwd=None: calls.append(cmd[2]) or 0):
                self.assertEqual(launcher.start(7654, open_browser=False, updated="job-1"), 0)
        self.assertEqual(calls, ["rollback"])
        # the version before starts in the same serve.log: the failed one's lines are why it was undone
        self.assertEqual(self.rotates, [False, False])
        # and the failed one's copy was finished (its file let go of) before the rollback ran
        self.assertEqual(self.events[:3], ["serve", "join", "serve"])
        self.assertIn(("wait", 10), failed.calls)


if __name__ == "__main__":
    unittest.main()
