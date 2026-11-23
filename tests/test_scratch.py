# SPDX-License-Identifier: GPL-3.0-or-later
"""Where Parseh stages a temporary file (lib/scratch.py): `.tmp/` in its own folder, never the system's temp folder.

    python3 -m unittest tests.test_scratch

What has to hold: the folder is the one the server set, or the tree a harness moved serve.ROOT to, and never the
checkout when nobody set one (a test must not write there); what a killed server left is swept at start-up once it is
a day old, and nothing outside `.tmp/` is ever touched -- not even what a link inside it points at.
"""
import os
import shutil
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))
import scratch      # noqa: E402


class Root(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="parseh-test-scratch-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_the_root_the_server_set_is_used(self):
        with mock.patch.object(scratch, "ROOT", self.tmp):
            fd, path = scratch.mkstemp(prefix="x-", suffix=".zip")
            os.close(fd)
            d = scratch.mkdtemp(prefix="y-")
        self.assertEqual(os.path.dirname(path), os.path.join(self.tmp, ".tmp"))
        self.assertEqual(os.path.dirname(d), os.path.join(self.tmp, ".tmp"))
        self.assertTrue(os.path.basename(path).startswith("x-") and path.endswith(".zip"))

    def test_a_harness_that_moved_serve_root_is_followed(self):
        fake = types.SimpleNamespace(ROOT=self.tmp)
        with mock.patch.object(scratch, "ROOT", None), mock.patch.dict(sys.modules, {"serve": fake}):
            self.assertEqual(scratch.root(), self.tmp)

    def test_nobody_set_one_and_it_is_never_the_checkout(self):
        unmoved = types.SimpleNamespace(ROOT=str(ROOT))
        for mods in ({"serve": unmoved}, {}):
            with mock.patch.object(scratch, "ROOT", None), mock.patch.dict(sys.modules, mods):
                if not mods:
                    sys.modules.pop("serve", None)
                got = os.path.realpath(scratch.root())
            self.assertNotEqual(got, os.path.realpath(str(ROOT)))
            self.assertFalse(got.startswith(os.path.realpath(str(ROOT)) + os.sep), got)

    def test_at_overrides(self):
        fd, path = scratch.mkstemp(at=self.tmp)
        os.close(fd)
        self.assertEqual(os.path.dirname(path), os.path.join(self.tmp, ".tmp"))

    def test_the_server_sets_it_before_anything_else_and_a_test_s_root_is_kept(self):
        src = (ROOT / "serve.py").read_text(encoding="utf-8")
        main = src[src.index("\ndef main():"):]
        self.assertLess(main.index("scratch.ROOT = ROOT"), main.index("argparse.ArgumentParser"))
        self.assertIn("if scratch.ROOT is None:", main[:main.index("scratch.ROOT = ROOT")])
        self.assertIn("scratch.sweep()", main)


class Sweep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="parseh-test-scratch-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dot = os.path.join(self.tmp, ".tmp")
        os.makedirs(self.dot)

    def age(self, path, seconds):
        t = time.time() - seconds
        os.utime(path, (t, t), follow_symlinks=False)

    def test_leftovers_older_than_a_day_go_and_the_rest_stay(self):
        old_f = os.path.join(self.dot, "parseh-shelf-old.zip")
        new_f = os.path.join(self.dot, "parseh-shelf-new.zip")
        old_d = os.path.join(self.dot, "parseh-everything-load-old")
        for f in (old_f, new_f):
            Path(f).write_bytes(b"zip")
        os.makedirs(os.path.join(old_d, "inner"))
        Path(old_d, "inner", "books.zip").write_bytes(b"zip")
        self.age(old_f, 2 * 86400)
        self.age(old_d, 2 * 86400)
        gone = scratch.sweep(at=self.tmp)
        self.assertEqual(sorted(gone), sorted(["parseh-shelf-old.zip", "parseh-everything-load-old"]))
        self.assertEqual(os.listdir(self.dot), ["parseh-shelf-new.zip"])

    def test_nothing_outside_tmp_is_touched_not_even_through_a_link(self):
        outside = os.path.join(self.tmp, "books")
        os.makedirs(outside)
        Path(outside, "keep.txt").write_text("mine")
        beside = os.path.join(self.tmp, "old-beside.zip")
        Path(beside).write_bytes(b"zip")
        self.age(beside, 9 * 86400)
        link = os.path.join(self.dot, "link")
        os.symlink(outside, link)
        self.age(link, 9 * 86400)
        self.age(outside, 9 * 86400)
        self.assertEqual(scratch.sweep(at=self.tmp), ["link"])
        self.assertTrue(Path(outside, "keep.txt").is_file())
        self.assertTrue(os.path.isfile(beside))

    def test_a_missing_tmp_is_not_made(self):
        shutil.rmtree(self.dot)
        self.assertEqual(scratch.sweep(at=self.tmp), [])
        self.assertFalse(os.path.exists(self.dot))


class EveryStagingPath(unittest.TestCase):
    """No backup, restore, export or upload path makes a temporary file without a dir= (the system's temp folder):
    read from the sources, so a path added next year is asked the same question."""

    FILES = ("serve.py", "lib/shelf.py", "lib/wholebackup.py", "lib/configbackup.py", "lib/bundle.py",
             "markdown/app/server.py", "markdown/app/deckroutes.py", "markdown/app/decks.py",
             "markdown/app/webexport.py", "youtube/lib/anki_export.py", "youtube/lib/import_apkg.py",
             "youtube/lib/sync_apkg.py")

    def test_no_bare_tempfile_in_them(self):
        import re
        bare = re.compile(r"tempfile\.(mkstemp|mkdtemp|TemporaryDirectory|NamedTemporaryFile)\((?![^)]*\bdir=)")
        for rel in self.FILES:
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIsNone(bare.search(src), "%s stages in the system's temp folder: %s"
                              % (rel, (bare.search(src) or [""])[0]))


class TheFolderIsNobodysContent(unittest.TestCase):
    def test_ignored_never_shipped_never_written_by_an_update(self):
        self.assertIn("/.tmp/", (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
        import release
        import updater
        self.assertIn(".tmp/", release.NEVER)
        self.assertIsNotNone(updater.guard(".tmp/parseh-shelf-x.zip"))


if __name__ == "__main__":
    unittest.main()
