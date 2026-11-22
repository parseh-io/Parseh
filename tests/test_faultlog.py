# SPDX-License-Identifier: GPL-3.0-or-later
"""The server's log kept for one run more, and the fault report made from it (lib/faultlog.py, TO-DO 5.31).

    python3 -m unittest tests.test_faultlog

Rotation (what serve.sh and the Windows launcher do before a start), the copy
of the server's output into serve.log on Windows (driven here on Linux with a
real child process), the last traceback found in a log, the redaction of what
is nobody else's business, and the About page that shows it all on the
computer only.
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
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import faultlog                                                # noqa: E402

TB = """Traceback (most recent call last):
  File "/home/ana/Parseh/serve.py", line 10, in do_GET
    self._route("GET", path)
  File "/home/ana/Parseh/lib/books.py", line 3, in load
    return json.loads(text)
           ^^^^^^^^^^^^^^^^
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)"""


class Rotation(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.td.name, "serve.log")

    def tearDown(self):
        self.td.cleanup()

    def write(self, path, data):
        with open(path, "wb") as f:
            f.write(data)

    def readb(self, path):
        with open(path, "rb") as f:
            return f.read()

    def test_the_run_before_is_kept_and_the_new_run_starts_empty(self):
        self.write(self.log, b"first run\n" + TB.encode() + b"\n")
        self.assertTrue(faultlog.rotate(self.log))
        self.assertEqual(self.readb(self.log), b"")
        self.assertIn(b"JSONDecodeError", self.readb(self.log + ".1"))

    def test_one_run_back_no_more(self):
        self.write(self.log, b"run one\n")
        faultlog.rotate(self.log)
        self.write(self.log, b"run two\n")
        faultlog.rotate(self.log)
        self.assertEqual(self.readb(self.log + ".1"), b"run two\n")
        self.assertEqual(sorted(os.listdir(self.td.name)), ["serve.log", "serve.log.1"])

    def test_an_empty_run_leaves_the_one_before_where_it_is(self):
        self.write(self.log + ".1", b"the crash\n")
        self.write(self.log, b"")
        faultlog.rotate(self.log)
        self.assertEqual(self.readb(self.log + ".1"), b"the crash\n")
        os.remove(self.log)
        faultlog.rotate(self.log)                # no log at all: one is made, the old one stays
        self.assertEqual(self.readb(self.log), b"")
        self.assertEqual(self.readb(self.log + ".1"), b"the crash\n")

    def test_a_long_log_keeps_its_end_cut_at_a_line(self):
        lines = b"".join(b"line %06d of a long run\n" % i for i in range(5000))
        self.write(self.log, lines)
        faultlog.rotate(self.log, keep=4096)
        kept = self.readb(self.log + ".1")
        self.assertLess(len(kept), 4096 + 200)
        self.assertTrue(kept.startswith(b"[... the start of this log was cut"))
        body = kept.split(b"\n", 1)[1]
        self.assertTrue(body.startswith(b"line "), body[:40])          # a whole line, not half of one
        self.assertTrue(body.endswith(b"line 004999 of a long run\n"))
        self.assertFalse(os.path.exists(self.log + ".1.part"))

    def test_serve_sh_rotates_with_the_cli(self):
        self.write(self.log, b"before\n")
        r = subprocess.run([sys.executable, str(ROOT / "lib" / "faultlog.py"), "rotate", self.log],
                           capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.readb(self.log + ".1"), b"before\n")
        self.assertEqual(self.readb(self.log), b"")

    def test_serve_sh_no_longer_empties_the_log_by_hand(self):
        sh = (ROOT / "serve.sh").read_text(encoding="utf-8")
        self.assertNotIn('\n: > "$LOG"\n', sh)
        self.assertIn('lib/faultlog.py" rotate "$LOG"', sh)
        self.assertIn("PARSEH_LOG", sh)


class WindowsCopy(unittest.TestCase):
    """The launcher's copy of the server's output, run on Linux as it runs on Windows."""

    def test_pump_writes_every_line_to_the_console_and_the_file(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "serve.log")
            console = io.BytesIO()
            faultlog.pump(io.BytesIO(b"one\ntwo\n" + TB.encode() + b"\n"), console, log)
            self.assertEqual(console.getvalue(), Path(log).read_bytes())
            self.assertIn(b"JSONDecodeError", console.getvalue())

    def test_a_console_that_fails_does_not_stop_the_file(self):
        class Broken:
            def write(self, b):
                raise OSError("the window was closed")

            def flush(self):
                pass
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "serve.log")
            faultlog.pump(io.BytesIO(b"still written\n"), Broken(), log)
            self.assertEqual(Path(log).read_bytes(), b"still written\n")

    def test_the_launcher_serves_with_a_log_file_and_names_it(self):
        import launcher
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "serve.log")
            Path(log).write_bytes(b"the run before\n")
            console = io.BytesIO()
            child = ("import os, sys; print('up at https://localhost:7654/'); "
                     "print('log is', os.environ['PARSEH_LOG'], os.environ['PARSEH_LAUNCHER']); "
                     "sys.stdout.flush(); raise RuntimeError('boom')")
            proc, copier = launcher.serve_logged([sys.executable, "-u", "-c", child], rotate=True,
                                                 log=log, console=console, env=dict(os.environ))
            proc.wait(20)
            copier.join(20)
            got = Path(log).read_text(encoding="utf-8")
            self.assertIn("up at https://localhost:7654/", got)
            self.assertIn("log is %s 1" % log, got)
            self.assertIn("RuntimeError: boom", got)                    # stderr too
            self.assertEqual(console.getvalue().decode("utf-8"), got)   # the window shows the same
            self.assertEqual(Path(log + ".1").read_text(encoding="utf-8"), "the run before\n")
            self.assertEqual(faultlog.last_traceback(got).splitlines()[-1], "RuntimeError: boom")

    def test_after_an_update_the_same_run_goes_on_in_the_same_file(self):
        import launcher
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "serve.log")
            Path(log).write_bytes(b"before the update\n")
            proc, copier = launcher.serve_logged([sys.executable, "-c", "print('after')"], rotate=False,
                                                 log=log, console=io.BytesIO(), env=dict(os.environ))
            proc.wait(20)
            copier.join(20)
            self.assertEqual(Path(log).read_text(encoding="utf-8"), "before the update\nafter\n")
            self.assertFalse(os.path.exists(log + ".1"))

    def test_start_uses_it(self):
        src = (ROOT / "lib" / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("serve_logged(cmd, rotate=not updated)", src)


class Tracebacks(unittest.TestCase):
    def test_none(self):
        self.assertEqual(faultlog.last_traceback("served /\nserved /books/\n"), "")
        self.assertEqual(faultlog.last_traceback(""), "")
        self.assertEqual(faultlog.last_traceback(None), "")

    def test_one_amid_the_noise(self):
        text = "Parseh is up\n127.0.0.1 GET /\n" + TB + "\n127.0.0.1 GET /books/\nstill serving\n"
        self.assertEqual(faultlog.last_traceback(text), TB)

    def test_the_last_one_wins(self):
        first = "Traceback (most recent call last):\n  File \"a.py\", line 1, in <module>\nKeyError: 'x'"
        text = first + "\nlater\n" + TB + "\n"
        self.assertEqual(faultlog.last_traceback(text), TB)

    def test_a_chain_is_kept_whole(self):
        cause = "Traceback (most recent call last):\n  File \"a.py\", line 1, in f\n    open(p)\nFileNotFoundError: [Errno 2] x"
        text = ("noise\n" + cause + "\n\nDuring handling of the above exception, another exception occurred:\n\n"
                + TB + "\nmore noise\n")
        got = faultlog.last_traceback(text)
        self.assertTrue(got.startswith("Traceback"))
        self.assertIn("FileNotFoundError", got)
        self.assertIn("During handling of the above exception", got)
        self.assertTrue(got.endswith("JSONDecodeError: Expecting value: line 1 column 1 (char 0)"))
        self.assertNotIn("noise", got)

    def test_http_servers_own_frame(self):
        text = ("-" * 40 + "\nException occurred during processing of request from ('127.0.0.1', 5)\n"
                + TB + "\n" + "-" * 40 + "\n")
        self.assertEqual(faultlog.last_traceback(text), TB)

    def test_a_syntax_error_keeps_its_caret(self):
        tb = ('Traceback (most recent call last):\n  File "serve.py", line 1, in <module>\n    import x\n'
              '  File "/x/lib/x.py", line 2\n    def (\n        ^\nSyntaxError: invalid syntax')
        self.assertEqual(faultlog.last_traceback("start\n" + tb + "\n"), tb)


class Redaction(unittest.TestCase):
    TOKEN = "Zq3_kd8Jw0aP-4vLr9XbN2yHc6TmEs1UoGfI5nVqR7w"       # what secrets.token_urlsafe(32) makes

    def red(self, text, **kw):
        args = dict(home="/home/ana", user="ana", secrets=(), host="anas-laptop")
        args.update(kw)
        return faultlog.redact(text, **args)

    def test_a_device_token_and_its_id(self):
        got = self.red("cookie for %s, shown as %s" % (self.TOKEN, self.TOKEN[:8]), secrets=[self.TOKEN])
        self.assertNotIn(self.TOKEN, got)
        self.assertNotIn(self.TOKEN[:8], got)

    def test_a_long_random_run_even_unknown(self):
        self.assertEqual(self.red("x " + self.TOKEN + " y"), "x [hidden] y")

    def test_the_pairing_code_as_serve_py_prints_it(self):
        line = "a device on the Wi-Fi is let in with the code:  K7MPQ2   (Settings > Network shows the one that works)"
        got = self.red(line)
        self.assertNotIn("K7MPQ2", got)
        self.assertIn("(Settings > Network", got)
        self.assertNotIn("K7MPQ2", self.red("code=K7MPQ2"))
        self.assertNotIn("K7MPQ2", self.red("something", secrets=["K7MPQ2"]) + self.red("K7MPQ2 x", secrets=["K7MPQ2"]))

    def test_named_secrets(self):
        for line in ("Cookie: parseh_device=abc123", "token=abc&x=1", "password: hunter2",
                     "Authorization: Bearer sk-abc", '"api_key": "sk-123"'):
            got = self.red(line)
            for secret in ("abc123", "abc&", "hunter2", "sk-abc", "sk-123"):
                self.assertNotIn(secret, got, line)

    def test_home_user_host_and_addresses(self):
        text = ("File \"/home/ana/Parseh/serve.py\", line 3\n"
                "installed in /run/media/ana/Data/Parseh\n"
                "  https://anas-laptop.tail1234.ts.net:7654/\n"
                "  https://192.168.1.20:7654/  https://100.101.102.103:7654/\n"
                "  https://127.0.0.1:7654/  served on anas-laptop\n")
        got = self.red(text)
        self.assertIn('File "~/Parseh/serve.py"', got)
        self.assertIn("/run/media/<user>/Data/Parseh", got)
        for gone in ("ana/", "192.168.1.20", "100.101.102.103", "ts.net", "anas-laptop"):
            self.assertNotIn(gone, got)
        self.assertIn("127.0.0.1", got)

    def test_windows_home(self):
        got = faultlog.redact(r'File "C:\Users\Ana\Parseh\serve.py"', home=r"C:\Users\Ana", user="Ana")
        self.assertEqual(got, r'File "~\Parseh\serve.py"')

    def test_what_a_report_needs_stays(self):
        text = "Parseh: a0.6.3\nPython: 3.12.13\nKeyError: 'code'\nlanguage code fa\n" + TB
        self.assertEqual(self.red(text, home="/nowhere", user="nobody", host="nohost"), text)


class Report(unittest.TestCase):
    def test_it_finds_the_crash_of_the_run_before_and_hides_what_is_private(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "serve.log")
            Path(log + ".1").write_text("up\nlet in with the code:  K7MPQ2\n" + TB + "\n", encoding="utf-8")
            Path(log).write_text("up again, fine\n", encoding="utf-8")
            with patch.dict(os.environ, {"PARSEH_LOG": log}):
                text = faultlog.report(td, "a0.6.3", parts=[("TeX", "lualatex")],
                                       redact_with=lambda t: faultlog.redact(t, home="/home/ana", user="ana"))
        self.assertIn("Parseh: a0.6.3", text)
        self.assertIn("Python: ", text)
        self.assertIn("  TeX: lualatex", text)
        self.assertIn("The last error in the logs (the previous run's log):", text)
        self.assertIn('File "~/Parseh/serve.py"', text)
        self.assertIn("JSONDecodeError", text)
        self.assertNotIn("K7MPQ2", text)

    def test_this_runs_crash_comes_first(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "serve.log")
            Path(log + ".1").write_text(TB + "\n", encoding="utf-8")
            Path(log).write_text("Traceback (most recent call last):\n  File \"x\", line 1\nOSError: now\n",
                                 encoding="utf-8")
            with patch.dict(os.environ, {"PARSEH_LOG": log}):
                text = faultlog.report(td, "v", parts=[], redact_with=lambda t: t)
        self.assertIn("(this run's log)", text)
        self.assertIn("OSError: now", text)
        self.assertNotIn("JSONDecodeError", text)

    def test_the_optional_parts_are_asked_one_by_one(self):
        parts = dict(faultlog.optional_parts(str(ROOT)))
        for k in ("Speech to text", "Word analyzers", "TeX", "ffmpeg", "Dictionaries", "Translation models",
                  "Pictograms"):
            self.assertIn(k, parts)
            self.assertNotIn("could not tell", parts[k], k)


class AboutPage(unittest.TestCase):
    def page(self, where, log):
        import aboutpage
        with patch.dict(os.environ, {"PARSEH_LOG": log}):
            return aboutpage.page(where)

    def test_the_computer_sees_the_logs_and_the_button_another_device_does_not(self):
        import network
        import project
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "serve.log")
            Path(log).write_text("SECRET-LOOKING LINE of this run\n", encoding="utf-8")
            Path(log + ".1").write_text("line of the run before\n" + TB + "\n", encoding="utf-8")
            here = self.page(network.SELF, log)
            self.assertIn("data-copy-report>Copy a report", here)
            self.assertIn("SECRET-LOOKING LINE of this run", here)
            self.assertIn("line of the run before", here)
            self.assertIn("JSONDecodeError", here)
            self.assertIn(project.ISSUES_URL, here)
            for where in (network.LAN, network.VPN, network.AWAY):
                there = self.page(where, log)
                self.assertNotIn("data-copy-report>", there)
                self.assertNotIn("SECRET-LOOKING", there)
                self.assertNotIn("run before\n", there)
                self.assertNotIn("JSONDecodeError", there)
                self.assertIn("data-fault-elsewhere", there)
                self.assertIn(project.ISSUES_URL, there)


if __name__ == "__main__":
    unittest.main()
