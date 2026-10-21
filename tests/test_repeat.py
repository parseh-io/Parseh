# SPDX-License-Identifier: GPL-3.0-or-later
"""tests/repeat.py: what it says of a red run, which cores it takes, and that it refuses what it cannot run."""
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("repeat_tool", HERE / "repeat.py")
repeat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repeat)


class Reason(unittest.TestCase):
    def test_the_first_FAIL_line_is_the_reason(self):
        log = "  ok one\n  ok two\n  FAIL: the pasted clip plays\n  ok after\nFAIL the computer: g)\n"
        self.assertEqual(repeat.reason(log), "FAIL: the pasted clip plays")

    def test_without_a_FAIL_the_first_line_that_looks_like_an_error(self):
        log = "  ok one\nerror: Uncaught (in promise) TimeoutError: page.waitForFunction: Timeout 5000ms exceeded.\n    at x\n"
        self.assertIn("TimeoutError", repeat.reason(log))

    def test_a_log_that_says_nothing_shows_its_end(self):
        got = repeat.reason("one\ntwo\nthree\n")
        self.assertIn("no line says why", got)
        self.assertIn("two | three", got)

    def test_a_reason_is_one_short_line(self):
        got = repeat.reason("FAIL: " + "word " * 200)
        self.assertNotIn("\n", got)
        self.assertLessEqual(len(got), 240)


class Cores(unittest.TestCase):
    def test_the_last_cores_are_the_ones_taken(self):
        total = os.cpu_count() or 1
        got = repeat.cores(1).split(",")
        self.assertEqual(got, [str(total - 1)])
        if total >= 3:
            self.assertEqual(repeat.cores(2), "%d,%d" % (total - 2, total - 1))

    def test_more_cores_than_there_are_take_them_all(self):
        total = os.cpu_count() or 1
        self.assertEqual(len(repeat.cores(total + 10).split(",")), total)


class Running(unittest.TestCase):
    def run_tool(self, *args, path=None):
        env = dict(os.environ)
        if path is not None:
            env["PATH"] = path
        return subprocess.run([sys.executable, str(HERE / "repeat.py"), *args], capture_output=True, text=True, env=env)

    def test_a_suite_that_is_not_there_is_refused(self):
        done = self.run_tool("no_such_suite_anywhere", "-n", "1")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("no such suite", done.stderr + done.stdout)

    def test_without_deno_it_says_so(self):
        with tempfile.TemporaryDirectory() as empty:
            done = self.run_tool("reach", "-n", "1", path=empty)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("deno is not on the path", done.stderr + done.stdout)

    def test_green_and_red_runs_are_counted_and_the_reasons_named(self):
        # a stand-in for deno: green on the first and third run, red on the second with a FAIL line
        with tempfile.TemporaryDirectory() as bin_dir, tempfile.TemporaryDirectory() as logs:
            counter = Path(bin_dir) / "count"
            counter.write_text("0")
            fake = Path(bin_dir) / "deno"
            fake.write_text("#!/bin/sh\nn=$(cat %s)\nn=$((n+1))\necho $n > %s\n"
                            "if [ $n = 2 ]; then echo '  FAIL: the second run'; exit 1; fi\necho '  ok'\nexit 0\n"
                            % (counter, counter))
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            done = self.run_tool("reach", "-n", "3", "--logs", logs, path=bin_dir + os.pathsep + os.environ["PATH"])
            self.assertEqual(done.returncode, 1)
            out = done.stdout
            self.assertIn("run 1: green", out)
            self.assertIn("run 2: RED", out)
            self.assertIn("run 3: green", out)
            self.assertIn("reach: 2 green, 1 red of 3", out)
            self.assertIn("1 x FAIL: the second run", out)
            self.assertTrue((Path(logs) / "reach-2.log").is_file())


if __name__ == "__main__":
    unittest.main()
