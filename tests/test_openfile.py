# SPDX-License-Identifier: GPL-3.0-or-later
"""A file from anywhere on the computer, open in the studio (a0.5.2): openfile.py -- the working copy in a temporary
folder, what makes it "unsaved", and the one moment the original changes.

    python3 -m unittest discover -s tests -p test_openfile.py

No server and no socket.  The person's own files live in a temporary folder of this test; the studio's library and
the folder of working copies are temporary too, so nothing here can touch the real ones -- and the tests check that
the library stays empty."""
import io
import json
import os
import stat
import struct
import sys
import tempfile
import time
import unittest
import wave
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app", ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import openfile  # noqa: E402
import store     # noqa: E402

LESSON = "---\ntitle: Lesson\nlang: en\ntarget: fa\n---\n\nHello.\n\n## Part\n\nMore.\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"cat" * 40
PNG2 = b"\x89PNG\r\n\x1a\n" + b"dog" * 40


def tiny_wav(seconds=0.2):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * int(8000 * seconds))
    return buf.getvalue()


WAV = tiny_wav()
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


def make_zip(path, entries, comment=b""):
    """A zip with fixed dates and modes, so that a copy can be compared with it entry by entry."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries:
            zi = zipfile.ZipInfo(name, (2020, 5, 17, 10, 30, 0))
            zi.compress_type = zipfile.ZIP_STORED if name.endswith((".wav", ".png")) else zipfile.ZIP_DEFLATED
            zi.external_attr = 0o640 << 16
            zi.comment = b"keep me" if name == "README.txt" else b""
            zf.writestr(zi, data)
        zf.comment = comment


def read_zip(path):
    """{name: (bytes, date_time, external_attr, compress_type, comment)} and the order."""
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        return ({i.filename: (zf.read(i), i.date_time, i.external_attr, i.compress_type, i.comment) for i in infos},
                [i.filename for i in infos])


class Base(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name).resolve()
        self.mine = self.tmp / "mine"                 # the person's own folder
        self.mine.mkdir()
        self.lib = self.tmp / "library"               # the studio's library, which must stay empty
        self.lib.mkdir()
        for obj, name, value in ((store, "LIB", self.lib), (openfile, "OPEN_DIR", self.tmp / "open"),
                                 (store, "CLIPS_DIR", self.tmp / "clips")):
            was = getattr(obj, name)
            setattr(obj, name, value)
            self.addCleanup(setattr, obj, name, was)
        openfile._SESSIONS.clear()
        self.addCleanup(openfile._SESSIONS.clear)

    # ---- helpers
    def write(self, name, data):
        path = self.mine / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path

    def open(self, path, **kw):
        got = openfile.open_path(str(path), **kw)
        return got["session"] if "session" in got else got

    def edit(self, sess, text):
        with sess.scope():
            store.save(sess.doc_id, text)

    def text_of(self, sess):
        with sess.scope():
            return store.get(sess.doc_id)[1]

    def add_picture(self, sess, name="cat.png", data=PNG):
        with sess.scope():
            return store.save_image(sess.doc_id, name, data)

    def assert_library_untouched(self):
        self.assertEqual(list(self.lib.iterdir()), [], "the studio's own library was written to")


class OpenMarkdown(Base):
    def test_open_reads_and_changes_nothing(self):
        path = self.write("lesson.md", LESSON)
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        sess = self.open(path)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        st = sess.state()
        self.assertEqual((st["kind"], st["dirty"], st["changed_on_disk"], st["missing"], st["can_write"]),
                         ("md", False, False, False, True))
        self.assertEqual(self.text_of(sess), LESSON)
        self.assertTrue(str(sess.dir).startswith(str(openfile.OPEN_DIR)))
        self.assert_library_untouched()

    def test_the_same_file_twice_is_one_session(self):
        path = self.write("lesson.md", LESSON)
        first = openfile.open_path(str(path))
        second = openfile.open_path(str(path))
        self.assertIs(first["session"], second["session"])
        self.assertEqual((first["again"], second["again"]), (False, True))
        # and through a link to it
        link = self.mine / "link.md"
        try:
            os.symlink(str(path), str(link))
        except (OSError, NotImplementedError):
            return
        self.assertIs(openfile.open_path(str(link))["session"], first["session"])

    def test_refusals_are_in_words(self):
        folder = self.mine / "a folder.md"
        folder.mkdir()
        cases = [("lesson.md", "path"),                                  # not a whole path
                 (str(self.mine / "nothing.md"), "gone"),
                 (str(folder), "path"),
                 (str(self.write("picture.png", PNG)), "kind"),
                 ("", "path")]
        for path, code in cases:
            with self.assertRaises(openfile.OpenError, msg=path) as caught:
                openfile.open_path(path)
            self.assertEqual(caught.exception.code, code, path)
            self.assertTrue(caught.exception.say.endswith((".", "?")), caught.exception.say)

    def test_parsehs_own_folders_are_not_opened(self):
        own = self.lib / "persian" / "x"
        own.mkdir(parents=True)
        (own / "source.md").write_text(LESSON, encoding="utf-8")
        for path in (own / "source.md",):
            with self.assertRaises(openfile.OpenError) as caught:
                openfile.open_path(str(path))
            self.assertEqual(caught.exception.code, "protected")
        sess = self.open(self.write("lesson.md", LESSON))
        # nor a working copy, which is Parseh's till it is closed
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(sess.dir / "library" / "persian" / sess.doc_id / "source.md"))
        self.assertEqual(caught.exception.code, "protected")
        with self.assertRaises(openfile.OpenError) as caught:
            sess.save(target=str(self.lib / "copy.md"))
        self.assertEqual(caught.exception.code, "protected")

    def test_not_text_and_too_large(self):
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(self.write("latin.md", "caf\xe9\n".encode("latin-1"))))
        self.assertEqual(caught.exception.code, "encoding")
        big = self.write("big.md", "x" * 2000)
        was, openfile.MD_MAX = openfile.MD_MAX, 1000
        self.addCleanup(setattr, openfile, "MD_MAX", was)
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(big))
        self.assertEqual(caught.exception.code, "size")
        self.assertEqual(list(openfile.OPEN_DIR.iterdir()), [], "a refused file leaves no working copy behind")

    def test_a_file_with_no_header_opens_and_stays_so(self):
        path = self.write("note.txt", "Just a note.\n\nSecond paragraph.\n")
        sess = self.open(path)
        self.assertFalse(sess.state()["dirty"])
        self.assertEqual(sess.save()["unchanged"], True)
        self.edit(sess, "Just a note.\n\nSecond paragraph, longer.\n")
        self.assertTrue(sess.save()["ok"])
        self.assertEqual(path.read_text(encoding="utf-8"), "Just a note.\n\nSecond paragraph, longer.\n",
                         "no header was added, no title made")

    def test_line_ends_and_the_byte_order_mark_come_back(self):
        raw = b"\xef\xbb\xbf" + LESSON.replace("\n", "\r\n").encode("utf-8")
        path = self.write("windows.md", raw)
        sess = self.open(path)
        self.assertEqual(self.text_of(sess), LESSON, "the studio works on \\n")
        self.edit(sess, LESSON + "\nA new line.\n")
        sess.save()
        self.assertEqual(path.read_bytes(), b"\xef\xbb\xbf" + (LESSON + "\nA new line.\n").replace("\n", "\r\n").encode("utf-8"))

    def test_a_save_of_nothing_new_writes_nothing(self):
        path = self.write("lesson.md", LESSON)
        sess = self.open(path)
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        time.sleep(0.01)
        got = sess.save()
        self.assertEqual((got["ok"], got.get("unchanged")), (True, True))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        # saving the very text again through the editor's own save is not a change either
        self.edit(sess, LESSON)
        self.assertFalse(sess.state()["dirty"])

    def test_unsaved_is_about_content_not_about_keystrokes(self):
        sess = self.open(self.write("lesson.md", LESSON))
        self.edit(sess, LESSON + "x\n")
        self.assertTrue(sess.state()["dirty"])
        self.edit(sess, LESSON)
        self.assertFalse(sess.state()["dirty"], "typed back to what the file holds")
        name = self.add_picture(sess)
        self.assertTrue(sess.state()["dirty"], "a picture is a change")
        with sess.scope():
            store.delete_image(sess.doc_id, name)
        self.assertFalse(sess.state()["dirty"], "and so is taking it away again")

    def test_save_writes_atomically_and_keeps_the_mode(self):
        path = self.write("lesson.md", LESSON)
        os.chmod(path, 0o640)
        sess = self.open(path)
        self.edit(sess, LESSON + "More.\n")
        got = sess.save()
        self.assertEqual((got["ok"], got["saved"]["wrote"]), (True, True))
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON + "More.\n")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
        self.assertEqual(sorted(p.name for p in self.mine.iterdir()), ["lesson.md"], "no temporary file left beside it")
        self.assertFalse(sess.state()["dirty"])
        self.assertFalse(sess.state()["changed_on_disk"], "what it wrote is what it expects to find")

    @unittest.skipIf(os.name == "nt", "links")
    def test_a_link_is_written_through(self):
        real = self.write("real/lesson.md", LESSON)
        link = self.mine / "link.md"
        os.symlink(str(real), str(link))
        sess = self.open(link)
        self.edit(sess, LESSON + "Through.\n")
        sess.save()
        self.assertTrue(link.is_symlink(), "the link is still a link")
        self.assertEqual(real.read_text(encoding="utf-8"), LESSON + "Through.\n")

    @unittest.skipIf(IS_ROOT or os.name == "nt", "permissions")
    def test_a_read_only_file_is_not_replaced(self):
        path = self.write("lesson.md", LESSON)
        os.chmod(path, 0o444)
        self.addCleanup(os.chmod, path, 0o644)
        sess = self.open(path)
        self.assertFalse(sess.state()["can_write"])
        self.edit(sess, LESSON + "x\n")
        with self.assertRaises(openfile.OpenError) as caught:
            sess.save()
        self.assertEqual(caught.exception.code, "readonly")
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON)
        self.assertTrue(sess.state()["dirty"], "and nothing was lost")

    @unittest.skipIf(IS_ROOT or os.name == "nt", "permissions")
    def test_a_locked_folder_with_a_writable_file_is_written_in_place(self):
        path = self.write("locked/lesson.md", LESSON)
        sess = self.open(path)
        self.edit(sess, LESSON + "In place.\n")
        os.chmod(path.parent, 0o555)
        self.addCleanup(os.chmod, path.parent, 0o755)
        got = sess.save()
        self.assertTrue(got["ok"])
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON + "In place.\n")

    def test_a_failed_write_leaves_the_original_whole(self):
        path = self.write("lesson.md", LESSON)

        def fill(f):
            f.write(b"half of a new ver")
            raise OSError(28, "No space left on device")
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.write_file(path, fill, like=path, stage_dir=self.tmp)
        self.assertEqual(caught.exception.code, "full")
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON)
        self.assertEqual(sorted(p.name for p in self.mine.iterdir()), ["lesson.md"])

    # ---- somebody else changed it, or took it away
    def test_a_file_changed_behind_our_back_is_not_overwritten(self):
        path = self.write("lesson.md", LESSON)
        sess = self.open(path)
        self.edit(sess, LESSON + "Mine.\n")
        path.write_text(LESSON + "Theirs, longer.\n", encoding="utf-8")
        self.assertTrue(sess.state()["changed_on_disk"])
        got = sess.save()
        self.assertEqual((got["ok"], got["need"]), (False, "conflict"))
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON + "Theirs, longer.\n")
        forced = sess.save(force=True)
        self.assertTrue(forced["ok"])
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON + "Mine.\n")
        self.assertFalse(sess.state()["changed_on_disk"])

    def test_a_file_only_touched_is_not_a_conflict(self):
        path = self.write("lesson.md", LESSON)
        sess = self.open(path)
        self.edit(sess, LESSON + "Mine.\n")
        os.utime(path, ns=(time.time_ns() + 5_000_000_000, time.time_ns() + 5_000_000_000))
        self.assertFalse(sess.state()["changed_on_disk"], "the same bytes with another date")
        self.assertTrue(sess.save()["ok"])

    def test_a_file_that_was_taken_away(self):
        path = self.write("lesson.md", LESSON)
        sess = self.open(path)
        self.edit(sess, LESSON + "Mine.\n")
        path.unlink()
        self.assertTrue(sess.state()["missing"])
        got = sess.save()
        self.assertEqual((got["ok"], got["need"]), (False, "path"))
        saved = sess.save(target=str(self.mine / "again.md"))
        self.assertTrue(saved["ok"])
        self.assertEqual((self.mine / "again.md").read_text(encoding="utf-8"), LESSON + "Mine.\n")
        self.assertEqual(sess.state()["name"], "again.md", "the session now stands for the new file")

    def test_save_as_asks_before_overwriting_and_leaves_the_original(self):
        path = self.write("lesson.md", LESSON)
        other = self.write("other.md", "Other.\n")
        sess = self.open(path)
        self.edit(sess, LESSON + "Mine.\n")
        got = sess.save(target=str(other))
        self.assertEqual((got["ok"], got["need"]), (False, "exists"))
        self.assertEqual(other.read_text(encoding="utf-8"), "Other.\n")
        got = sess.save(target=str(other), overwrite=True)
        self.assertTrue(got["ok"] and got["saved"]["as_new"])
        self.assertEqual(other.read_text(encoding="utf-8"), LESSON + "Mine.\n")
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON, "the file it was opened from is as it was")
        self.assertEqual(sess.path, str(other))

    def test_save_as_refuses_a_folder_a_missing_folder_and_a_wrong_kind(self):
        sess = self.open(self.write("lesson.md", LESSON))
        for target, code in ((str(self.mine), "path"), (str(self.mine / "no" / "such" / "x.md"), "gone"),
                             (str(self.mine / "x.pdf"), "kind"), ("relative.md", "path")):
            with self.assertRaises(openfile.OpenError, msg=target) as caught:
                sess.save(target=target)
            self.assertEqual(caught.exception.code, code, target)


class FaithfulCopies(Base):
    @unittest.skipIf(os.name == "nt", "modes")
    def test_a_file_made_by_save_as_has_the_mode_a_new_file_has(self):
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)
        sess = self.open(self.write("lesson.md", LESSON))
        self.edit(sess, LESSON + "x\n")
        copy = self.mine / "copy.md"
        self.assertTrue(sess.save(target=str(copy))["ok"])
        self.assertEqual(stat.S_IMODE(copy.stat().st_mode), 0o644, "not the owner-only mode of a temporary file")
        self.assertEqual(sorted(p.name for p in self.mine.iterdir()), ["copy.md", "lesson.md"], "and no temporary left")

    def test_a_zips_comment_and_the_extra_fields_of_its_entries_come_back(self):
        path = self.mine / "lesson.zip"
        stamp = struct.pack("<HHBI", 0x5455, 5, 1, 1_700_000_000)                 # an extended modification time
        old_zip64 = struct.pack("<HHQQ", 1, 16, 5, 5)                               # how another archive held an entry
        with zipfile.ZipFile(path, "w") as zf:
            zi = zipfile.ZipInfo("lesson.md", (2024, 1, 2, 3, 4, 6))
            zi.extra = stamp
            zf.writestr(zi, LESSON)
            zi2 = zipfile.ZipInfo("README.txt", (2023, 1, 2, 3, 4, 6))
            zi2.extra = old_zip64 + stamp
            zi2.internal_attr = 1
            zf.writestr(zi2, "read me\n")
            zf.comment = b"made by hand"
        sess = self.open(path)
        self.edit(sess, LESSON + "x\n")
        self.assertTrue(sess.save()["ok"])
        with zipfile.ZipFile(path) as zf:
            self.assertEqual(zf.comment, b"made by hand", "the archive's own comment")
            info = zf.getinfo("README.txt")
            self.assertEqual(info.internal_attr, 1)
            self.assertIn(stamp, info.extra, "an entry's extra fields are kept")
            self.assertNotIn(struct.pack("<HH", 1, 16), info.extra, "but not the one about how another archive held it")
            self.assertEqual(zf.read("README.txt"), b"read me\n")

    def test_a_damaged_zip_is_refused_in_words_and_a_failed_copy_leaves_the_original_whole(self):
        def damaged(name, entries, victim):
            path = self.mine / name
            with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
                for entry, data in entries:
                    zf.writestr(entry, data)
            raw = bytearray(path.read_bytes())
            at = raw.index(victim)
            raw[at] ^= 0x01                                   # one bit of an entry's stored bytes: its checksum fails
            path.write_bytes(bytes(raw))
            return path
        # a picture the document shows: the zip cannot be opened as it is, and the sentence says which entry
        bad_picture = damaged("picture.zip", [("lesson.md", LESSON + "\n![x](images/cat.png)\n"), ("images/cat.png", PNG)], PNG)
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(bad_picture))
        self.assertEqual(caught.exception.code, "zip")
        self.assertIn("images/cat.png", caught.exception.say)
        self.assertEqual(list(openfile.OPEN_DIR.iterdir()), [], "and nothing is left behind")
        # an entry the document has nothing to do with opens, and cannot be copied across: nothing is written
        path = damaged("readme.zip", [("lesson.md", LESSON), ("README.txt", "Read me, please.\n")], b"Read me")
        sess = self.open(path)
        before = path.read_bytes()
        self.edit(sess, LESSON + "x\n")
        with self.assertRaises(openfile.OpenError) as caught:
            sess.save()
        self.assertEqual(caught.exception.code, "zip")
        self.assertIn("nothing was written", caught.exception.say)
        self.assertEqual(path.read_bytes(), before, "the zip is as it was, byte for byte")
        self.assertEqual(sorted(p.name for p in self.mine.iterdir()), ["picture.zip", "readme.zip"], "and no temporary left")
        self.assertTrue(sess.state()["dirty"], "and what was typed is not lost")

    def test_the_extra_fields_that_cannot_be_read_are_dropped_not_copied_wrong(self):
        self.assertEqual(openfile._extra_without_zip64(b""), b"")
        self.assertEqual(openfile._extra_without_zip64(b"\x55\x54\x09\x00abc"), b"", "a field longer than what is there")
        self.assertEqual(openfile._extra_without_zip64(b"\x55"), b"")
        keep = struct.pack("<HH", 0x5455, 2) + b"ab"
        self.assertEqual(openfile._extra_without_zip64(keep + struct.pack("<HHQ", 1, 8, 7) + keep), keep + keep)

    @unittest.skipIf(os.name == "nt", "names are text there")
    def test_a_name_that_is_no_text_does_not_fail_the_list(self):
        try:
            with open(os.path.join(os.fsencode(str(self.mine)), b"bad\xff.md"), "wb") as f:
                f.write(b"x")
        except OSError:
            self.skipTest("this file system refuses a name of undecodable bytes")
        self.write("good.md", "x")
        got = openfile.listing(str(self.mine))
        self.assertEqual([e["name"] for e in got["entries"]], ["good.md"])
        json.dumps(got, ensure_ascii=False).encode("utf-8")        # what the server does with it


class MarkdownCannotHoldMedia(Base):
    def lesson_with_picture(self, beside=True):
        text = LESSON + "\nimages/cat.png\n"
        path = self.write("lesson.md", text)
        if beside:
            self.write("images/cat.png", PNG)
        return path, text

    def test_pictures_beside_the_file_are_read_never_written(self):
        path, text = self.lesson_with_picture()
        sess = self.open(path)
        self.assertEqual(sorted(sess.payload()["media"]), ["images/cat.png"])
        self.assertFalse(sess.state()["dirty"])
        self.edit(sess, text + "More words.\n")
        got = sess.save()
        self.assertTrue(got["ok"], "the picture is beside the file already: the md holds the document")
        self.assertEqual((self.mine / "images" / "cat.png").read_bytes(), PNG)
        self.assertEqual(sorted(p.name for p in self.mine.iterdir()), ["images", "lesson.md"])

    def test_a_picture_in_the_files_own_folder_is_found_too(self):
        text = LESSON + "\nimages/cat.png\n"
        path = self.write("lesson.md", text)
        self.write("cat.png", PNG)
        sess = self.open(path)
        self.assertEqual(sorted(sess.payload()["media"]), ["images/cat.png"])

    def test_a_missing_picture_is_a_warning_not_a_refusal(self):
        path, _text = self.lesson_with_picture(beside=False)
        sess = self.open(path)
        self.assertTrue(any("images/cat.png" in w for w in sess.state()["warnings"]), sess.state()["warnings"])

    def test_a_new_picture_makes_the_save_ask(self):
        path, text = self.lesson_with_picture()
        sess = self.open(path)
        name = self.add_picture(sess, "dog.png", PNG2)
        self.edit(sess, text + "\nimages/%s\n" % name)
        got = sess.save()
        self.assertEqual((got["ok"], got["need"]), (False, "format"))
        self.assertEqual(got["reasons"], [{"what": "media", "names": ["images/dog.png"]}])
        self.assertEqual(got["suggest"], str(self.mine / "lesson.zip"))
        self.assertEqual(path.read_text(encoding="utf-8"), text, "asking changed nothing")
        # "text only": the md is written, the picture is not
        done = sess.save(accept_loss=True)
        self.assertTrue(done["ok"])
        self.assertEqual(path.read_text(encoding="utf-8"), text + "\nimages/dog.png\n")
        self.assertFalse((self.mine / "images" / "dog.png").exists())
        self.assertEqual(done["saved"]["left_out"], [{"what": "media", "names": ["images/dog.png"]}])
        # and it is not asked again while nothing new is left out
        self.assertEqual(sess.save().get("unchanged"), True)
        self.edit(sess, text + "\nimages/dog.png\n\nMore.\n")
        again = sess.save()
        self.assertTrue(again["ok"], again)
        # but a second new picture is
        self.add_picture(sess, "bird.png", PNG + b"2")
        self.edit(sess, self.text_of(sess) + "\nimages/bird.png\n")
        self.assertEqual(sess.save().get("need"), "format")

    def test_tags_make_the_save_ask(self):
        sess = self.open(self.write("lesson.md", LESSON))
        with sess.scope():
            store.update_meta(sess.doc_id, {"tags": ["Verbs", "a1"]})
        got = sess.save()
        self.assertEqual(got["need"], "format")
        self.assertEqual(got["reasons"], [{"what": "tags", "tags": ["a1", "verbs"]}])
        done = sess.save(accept_loss=True)
        self.assertTrue(done["ok"])
        self.assertEqual(done["saved"]["wrote"], False, "the text was not touched: nothing to write")
        self.assertEqual(sess.save().get("unchanged"), True)

    def test_save_as_a_zip_holds_the_studios_layout(self):
        path, text = self.lesson_with_picture()
        sess = self.open(path)
        name = self.add_picture(sess, "dog.png", PNG2)
        with sess.scope():
            store.update_meta(sess.doc_id, {"tags": ["verbs"]})
            store.save_audio(sess.doc_id, "word.wav", WAV)
        self.edit(sess, text + "\nimages/%s\n\naudio/word.wav\n" % name)
        target = self.mine / "lesson.zip"
        got = sess.save(target=str(target))
        self.assertTrue(got["ok"], got)
        entries, order = read_zip(target)
        self.assertEqual(sorted(order), ["audio/word.wav", "images/cat.png", "images/dog.png", "lesson.md",
                                         "lesson.tags.json"])
        self.assertEqual(entries["lesson.md"][0].decode("utf-8"), text + "\nimages/dog.png\n\naudio/word.wav\n")
        self.assertEqual(json.loads(entries["lesson.tags.json"][0]), {"tags": ["verbs"]})
        self.assertEqual((entries["images/cat.png"][0], entries["images/dog.png"][0], entries["audio/word.wav"][0]),
                         (PNG, PNG2, WAV))
        self.assertEqual(path.read_text(encoding="utf-8"), text, "the Markdown file is untouched")
        st = sess.state()
        self.assertEqual((st["kind"], st["name"], st["dirty"], st["entry"]), ("zip", "lesson.zip", False, "lesson.md"))
        # from here on it is a zip like any other: a later edit patches it
        self.edit(sess, self.text_of(sess) + "\nLater.\n")
        self.assertTrue(sess.save()["ok"])
        later, _ = read_zip(target)
        self.assertEqual(later["images/cat.png"][0], PNG)
        self.assertTrue(later["lesson.md"][0].decode("utf-8").endswith("Later.\n"))

    def test_the_zip_beside_it_is_named_by_the_person(self):
        path, text = self.lesson_with_picture()
        sess = self.open(path)
        self.add_picture(sess, "dog.png", PNG2)
        target = self.mine / "course.zip"
        self.assertTrue(sess.save(target=str(target))["ok"])
        entries, _ = read_zip(target)
        self.assertIn("course.md", entries, "the Markdown inside is named like the zip, the way the studio's own is")

    def test_the_starters_pictures_are_not_a_change_nor_something_the_markdown_lacks(self):
        text = LESSON + "\nimages/starter-apple.svg\n"
        path = self.write("lesson.md", text)
        sess = self.open(path)
        self.assertEqual(sess.payload()["media"], {})
        with sess.scope():
            store.adopt_starter_media(sess.doc_id)            # what every save of the editor does
            self.assertTrue((store.images_dir(sess.doc_id) / "starter-apple.svg").is_file())
        self.assertEqual(sess.payload()["media"], {}, "it comes from where Parseh ships it, not from the file")
        self.assertFalse(sess.state()["dirty"])
        self.edit(sess, text + "More.\n")
        self.assertTrue(sess.save()["ok"], "no question about a picture the md never had")


def tags_zip_entries(extra=()):
    return [("lesson.md", LESSON + "\nimages/cat.png\n\naudio/word.wav\n"),
            ("lesson.tags.json", json.dumps({"tags": ["verbs", "a1"]})),
            ("images/cat.png", PNG), ("audio/word.wav", WAV), ("README.txt", "Read me.\n"),
            ("data/numbers.csv", "1,2\n3,4\n")] + list(extra)


class OpenZip(Base):
    def make(self, entries=None, name="lesson.zip"):
        path = self.mine / name
        make_zip(path, entries if entries is not None else tags_zip_entries())
        return path

    def test_open_reads_the_layout(self):
        path = self.make()
        before = path.read_bytes()
        sess = self.open(path)
        self.assertEqual(path.read_bytes(), before)
        st = sess.state()
        self.assertEqual((st["kind"], st["entry"], st["dirty"]), ("zip", "lesson.md", False))
        pay = sess.payload()
        self.assertEqual(sorted(pay["media"]), ["audio/word.wav", "images/cat.png"])
        self.assertEqual(pay["tags"], ["a1", "verbs"])
        self.assertEqual(pay["text"], LESSON + "\nimages/cat.png\n\naudio/word.wav\n")
        self.assert_library_untouched()

    def test_a_save_changes_only_what_the_document_changed(self):
        path = self.make()
        old, old_order = read_zip(path)
        sess = self.open(path)
        self.edit(sess, self.text_of(sess) + "\nA new line.\n")
        self.assertTrue(sess.save()["ok"])
        new, new_order = read_zip(path)
        self.assertEqual(new_order, old_order, "same entries in the same order")
        for name in old:
            if name == "lesson.md":
                self.assertEqual(new[name][0].decode("utf-8"), old[name][0].decode("utf-8") + "\nA new line.\n")
                self.assertEqual(new[name][2:4], old[name][2:4], "its mode and how it is stored")
            else:
                self.assertEqual(new[name], old[name], "%s is copied as it was: bytes, date, mode, comment" % name)

    def test_a_save_can_add_and_take_away(self):
        path = self.make()
        old, _ = read_zip(path)
        sess = self.open(path)
        name = self.add_picture(sess, "dog.png", PNG2)
        with sess.scope():
            store.delete_audio(sess.doc_id, "word.wav")
            store.update_meta(sess.doc_id, {"tags": ["new"]})
        self.edit(sess, LESSON + "\nimages/cat.png\n\nimages/%s\n" % name)
        self.assertTrue(sess.save()["ok"])
        new, order = read_zip(path)
        self.assertNotIn("audio/word.wav", new, "the recording the person deleted")
        self.assertEqual(order[-1], "images/dog.png", "what is new is at the end")
        self.assertEqual(new["images/dog.png"][0], PNG2)
        self.assertEqual(json.loads(new["lesson.tags.json"][0]), {"tags": ["new"]})
        self.assertEqual((new["README.txt"], new["data/numbers.csv"]), (old["README.txt"], old["data/numbers.csv"]))
        self.assertFalse(sess.state()["dirty"])

    def test_a_changed_picture_is_replaced_where_it_was(self):
        path = self.make()
        sess = self.open(path)
        with sess.scope():
            (store.images_dir(sess.doc_id) / "cat.png").write_bytes(PNG2)
        self.assertTrue(sess.state()["dirty"])
        self.assertTrue(sess.save()["ok"])
        new, order = read_zip(path)
        self.assertEqual(new["images/cat.png"][0], PNG2)
        self.assertEqual(order, [n for n, _data in tags_zip_entries()])

    def test_taking_every_tag_off_drops_the_tags_entry(self):
        path = self.make()
        sess = self.open(path)
        with sess.scope():
            store.update_meta(sess.doc_id, {"tags": []})
        self.assertTrue(sess.save()["ok"])
        self.assertNotIn("lesson.tags.json", read_zip(path)[0])

    def test_nothing_new_writes_nothing(self):
        path = self.make()
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        sess = self.open(path)
        time.sleep(0.01)
        self.assertEqual(sess.save().get("unchanged"), True)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_a_zip_with_a_folder_keeps_its_places(self):
        entries = [("course/lesson.md", LESSON + "\nimages/cat.png\n"), ("course/images/cat.png", PNG),
                   ("course/notes.txt", "x\n")]
        path = self.make(entries)
        sess = self.open(path)
        self.assertEqual(sess.state()["entry"], "course/lesson.md")
        self.assertEqual(sorted(sess.payload()["media"]), ["images/cat.png"])
        name = self.add_picture(sess, "dog.png", PNG2)
        with sess.scope():
            store.update_meta(sess.doc_id, {"tags": ["x"]})
        self.edit(sess, self.text_of(sess) + "\nimages/%s\n" % name)
        self.assertTrue(sess.save()["ok"])
        new, order = read_zip(path)
        self.assertEqual(order[:3], ["course/lesson.md", "course/images/cat.png", "course/notes.txt"])
        self.assertIn("course/images/dog.png", new)
        self.assertIn("course/lesson.tags.json", new)

    def test_names_that_differ_in_case_are_written_back_as_they_were(self):
        entries = [("Lesson.MD", LESSON + "\nimages/cat.png\n"), ("Images/Cat.PNG", PNG)]
        path = self.make(entries)
        sess = self.open(path)
        self.assertEqual(sorted(sess.payload()["media"]), ["images/cat.png"])
        with sess.scope():
            (store.images_dir(sess.doc_id) / "cat.png").write_bytes(PNG2)
        sess.save()
        new, order = read_zip(path)
        self.assertEqual(order, ["Lesson.MD", "Images/Cat.PNG"])
        self.assertEqual(new["Images/Cat.PNG"][0], PNG2)

    def test_several_documents_are_chosen_from(self):
        entries = [("a.md", "---\ntitle: First one\nlang: en\ntarget: fa\n---\n\nA.\n"), ("b.md", "# Second one\n\nB.\n")]
        path = self.make(entries)
        got = openfile.open_path(str(path))
        self.assertEqual([c["path"] for c in got["choose"]], ["a.md", "b.md"])
        self.assertEqual([c["title"] for c in got["choose"]], ["First one", "Second one"])
        self.assertEqual(list(openfile.OPEN_DIR.iterdir()), [], "choosing leaves nothing behind")
        sess = openfile.open_path(str(path), entry="b.md")["session"]
        self.assertEqual(sess.state()["entry"], "b.md")
        self.edit(sess, "# Second one\n\nB, changed.\n")
        sess.save()
        new, order = read_zip(path)
        self.assertEqual(new["b.md"][0].decode("utf-8"), "# Second one\n\nB, changed.\n")
        self.assertEqual(new["a.md"][0].decode("utf-8"), entries[0][1], "the other document is as it was")
        with self.assertRaises(openfile.OpenError) as caught:      # the zip is open: one session for it
            openfile.open_path(str(path), entry="a.md")
        self.assertEqual((caught.exception.code, caught.exception.more["sid"]), ("busy", sess.sid))
        self.assertEqual(openfile.open_path(str(path), entry="b.md")["session"], sess, "the one it is open on")
        sess.close()
        with self.assertRaises(openfile.OpenError):
            openfile.open_path(str(path), entry="nope.md")

    def test_what_a_zip_that_is_not_a_document_says(self):
        cases = {
            "garbage.zip": (b"this is not a zip", "not a zip"),
        }
        for name, (data, words) in cases.items():
            path = self.write(name, data)
            with self.assertRaises(openfile.OpenError, msg=name) as caught:
                openfile.open_path(str(path))
            self.assertIn(words, caught.exception.say)
        nomd = self.make([("a.txt", "x"), ("images/c.png", PNG)], "nomd.zip")
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(nomd))
        self.assertIn("no Markdown", caught.exception.say)
        zips = self.make([("one.zip", b"PK"), ("two.zip", b"PK")], "zips.zip")
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(zips))
        self.assertIn("other zips", caught.exception.say)
        backup = self.make([("persian/x-123456/source.md", "x"), ("persian/x-123456/meta.json", "{}")], "backup.zip")
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(backup))
        self.assertIn("backup", caught.exception.say)

    def test_an_encrypted_zip_is_refused(self):
        path = self.make([("lesson.md", LESSON)], "secret.zip")
        data = bytearray(path.read_bytes())
        at = data.index(b"PK\x01\x02")
        flags = struct.unpack_from("<H", data, at + 8)[0]
        struct.pack_into("<H", data, at + 8, flags | 1)
        path.write_bytes(bytes(data))
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(path))
        self.assertIn("password", caught.exception.say)

    def test_limits(self):
        path = self.make()
        was = openfile.ZIP_ENTRIES_MAX
        openfile.ZIP_ENTRIES_MAX = 3
        self.addCleanup(setattr, openfile, "ZIP_ENTRIES_MAX", was)
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(path))
        self.assertEqual(caught.exception.code, "size")
        openfile.ZIP_ENTRIES_MAX = was
        self.addCleanup(setattr, openfile, "ZIP_MANAGED_MAX", openfile.ZIP_MANAGED_MAX)
        openfile.ZIP_MANAGED_MAX = 50
        with self.assertRaises(openfile.OpenError) as caught:
            openfile.open_path(str(path))
        self.assertEqual(caught.exception.code, "size")
        self.assertEqual(list(openfile.OPEN_DIR.iterdir()), [])

    def test_an_entry_name_is_never_a_path_on_the_disk(self):
        evil = self.tmp / "evil.png"
        entries = [("lesson.md", LESSON + "\nimages/cat.png\n"), ("images/cat.png", PNG),
                   ("../evil.png", PNG), ("/abs/evil2.png", PNG), ("images/../../evil3.png", PNG)]
        path = self.make(entries)
        before = read_zip(path)
        sess = self.open(path)
        self.assertEqual(sorted(sess.payload()["media"]), ["images/cat.png"])
        self.edit(sess, self.text_of(sess) + "x\n")
        sess.save()
        after = read_zip(path)
        for name in ("../evil.png", "/abs/evil2.png", "images/../../evil3.png"):
            self.assertEqual(after[0][name], before[0][name], "carried across untouched")
        self.assertFalse(evil.exists())
        self.assertFalse((self.tmp / "evil3.png").exists())
        self.assertFalse(Path("/abs").exists() and (Path("/abs") / "evil2.png").exists())

    def test_what_the_studio_cannot_show_is_left_alone_and_said(self):
        entries = [("lesson.md", LESSON + "\nimages/cat.png\n"), ("images/cat.png", PNG),
                   ("images/notes.txt", "hello"), ("images/Big Name.PNG", PNG), ("images/fake.png", b"not a picture")]
        path = self.make(entries)
        sess = self.open(path)
        self.assertEqual(sorted(sess.payload()["media"]), ["images/cat.png"])
        self.assertTrue(len(sess.state()["warnings"]) >= 2, sess.state()["warnings"])
        self.edit(sess, self.text_of(sess) + "y\n")
        sess.save()
        new, order = read_zip(path)
        self.assertEqual(order, [n for n, _ in entries])
        self.assertEqual(new["images/fake.png"][0], b"not a picture")

    def test_a_file_changed_behind_our_back_is_not_overwritten(self):
        path = self.make()
        sess = self.open(path)
        self.edit(sess, self.text_of(sess) + "Mine.\n")
        make_zip(path, tags_zip_entries([("extra.txt", "somebody added this\n")]))
        got = sess.save()
        self.assertEqual((got["ok"], got["need"]), (False, "conflict"))
        self.assertIn("extra.txt", read_zip(path)[0])

    def test_save_as_a_copy_keeps_the_rest_of_the_zip(self):
        path = self.make()
        sess = self.open(path)
        self.edit(sess, self.text_of(sess) + "Copy.\n")
        copy = self.mine / "copy.zip"
        self.assertTrue(sess.save(target=str(copy))["ok"])
        old, _ = read_zip(path)
        new, _ = read_zip(copy)
        self.assertIn("data/numbers.csv", new)
        self.assertEqual(new["README.txt"], old["README.txt"])
        self.assertTrue(new["lesson.md"][0].decode("utf-8").endswith("Copy.\n"))
        self.assertFalse(old["lesson.md"][0].decode("utf-8").endswith("Copy.\n"), "the original is as it was")
        self.assertEqual(sess.path, str(copy))

    def test_save_as_markdown_asks_what_a_markdown_cannot_hold(self):
        path = self.make()
        sess = self.open(path)
        got = sess.save(target=str(self.mine / "plain.md"))
        self.assertEqual(got["need"], "format")
        self.assertEqual({r["what"] for r in got["reasons"]}, {"media", "tags"})
        done = sess.save(target=str(self.mine / "plain.md"), accept_loss=True)
        self.assertTrue(done["ok"])
        self.assertEqual(sess.state()["kind"], "md")
        self.assertEqual((self.mine / "plain.md").read_text(encoding="utf-8"), LESSON + "\nimages/cat.png\n\naudio/word.wav\n")


class Lifecycle(Base):
    def test_closing_a_clean_session_removes_its_folder(self):
        sess = self.open(self.write("lesson.md", LESSON))
        folder = sess.dir
        self.assertTrue(folder.is_dir())
        self.assertEqual(sess.close(), {"ok": True})
        self.assertFalse(folder.exists())
        with self.assertRaises(KeyError):
            openfile.get(sess.sid)
        self.assertEqual(self.write("lesson.md", LESSON).read_text(encoding="utf-8"), LESSON)

    def test_closing_with_unsaved_work_asks_first(self):
        path = self.write("lesson.md", LESSON)
        sess = self.open(path)
        self.edit(sess, LESSON + "x\n")
        got = sess.close()
        self.assertEqual((got["ok"], got["need"]), (False, "unsaved"))
        self.assertTrue(sess.dir.is_dir())
        self.assertEqual(sess.close(discard=True), {"ok": True})
        self.assertFalse(sess.dir.exists())
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON, "the original never moved")

    def test_a_saved_session_closes_without_asking(self):
        sess = self.open(self.write("lesson.md", LESSON))
        self.edit(sess, LESSON + "x\n")
        sess.save()
        self.assertEqual(sess.close(), {"ok": True})

    def test_a_restart_finds_its_sessions_again(self):
        path = self.write("lesson.md", LESSON)
        sess = self.open(path)
        self.edit(sess, LESSON + "unsaved\n")
        openfile._SESSIONS.clear()                       # a stopped and started Parseh knows nothing in memory
        back = openfile.get(sess.sid)
        self.assertIsNot(back, sess)
        self.assertTrue(back.state()["dirty"])
        self.assertEqual(self.text_of(back), LESSON + "unsaved\n")
        self.assertTrue(back.save()["ok"])
        self.assertEqual(path.read_text(encoding="utf-8"), LESSON + "unsaved\n")
        self.assertEqual(openfile.open_path(str(path))["session"].sid, sess.sid, "still one session for the file")

    def test_sweep_keeps_what_has_unsaved_work_and_removes_the_rest(self):
        clean = self.open(self.write("clean.md", LESSON))
        dirty = self.open(self.write("dirty.md", LESSON))
        self.edit(dirty, LESSON + "unsaved\n")
        openfile._SESSIONS.clear()
        old_orphan = openfile.OPEN_DIR / "aaaaaaaaaaaa"
        old_orphan.mkdir()
        young_orphan = openfile.OPEN_DIR / "bbbbbbbbbbbb"
        young_orphan.mkdir()
        stale = time.time() - 3 * 24 * 3600
        os.utime(old_orphan, (stale, stale))
        got = openfile.sweep()
        self.assertEqual(got["kept"], [dirty.sid])
        self.assertEqual(sorted(got["removed"]), sorted([clean.sid, old_orphan.name]))
        self.assertFalse(clean.dir.exists())
        self.assertFalse(old_orphan.exists())
        self.assertTrue(young_orphan.exists(), "it may be being made")
        self.assertTrue(dirty.dir.is_dir())
        self.assertTrue(openfile.get(dirty.sid).state()["recovered"], "the page offers it back")
        self.assertEqual([s.sid for s in openfile.live()], [dirty.sid])

    def test_a_copy_this_parseh_cannot_open_is_not_thrown_away_after_a_day(self):
        sess = self.open(self.write("lesson.md", LESSON))
        self.edit(sess, LESSON + "unsaved\n")
        openfile._SESSIONS.clear()
        record = json.loads((sess.dir / "session.json").read_text(encoding="utf-8"))
        record["format"] = 99                                  # made by another version of Parseh
        (sess.dir / "session.json").write_text(json.dumps(record), encoding="utf-8")
        nothing = openfile.OPEN_DIR / "cccccccccccc"           # and a folder with no record, and no work in it
        nothing.mkdir()
        stale = time.time() - 3 * 24 * 3600
        for folder in (sess.dir, nothing):
            os.utime(folder, (stale, stale))
        got = openfile.sweep()
        self.assertEqual(got, {"kept": [], "removed": [nothing.name]})
        self.assertTrue(sess.dir.is_dir(), "the unsaved work of a session that cannot be opened here stays")
        self.assertFalse(nothing.exists())

    def test_shutdown_removes_only_the_clean(self):
        clean = self.open(self.write("clean.md", LESSON))
        dirty = self.open(self.write("dirty.md", LESSON))
        self.edit(dirty, LESSON + "unsaved\n")
        self.assertEqual(openfile.shutdown(), [clean.sid])
        self.assertTrue(dirty.dir.is_dir())

    def test_a_working_copy_that_went_missing_is_nothing_to_keep(self):
        sess = self.open(self.write("lesson.md", LESSON))
        import shutil
        shutil.rmtree(str(sess.dir / "library"))
        self.assertEqual(sess.close(), {"ok": True})

    def test_sessions_do_not_see_each_other_nor_the_library(self):
        a = self.open(self.write("a.md", "---\ntitle: Same\nlang: en\ntarget: fa\n---\n\nA.\n"))
        b = self.open(self.write("b.md", "---\ntitle: Same\nlang: en\ntarget: fa\n---\n\nB.\n"))
        self.assertNotEqual(a.sid, b.sid)
        self.edit(a, "---\ntitle: Same\nlang: en\ntarget: fa\n---\n\nA changed.\n")
        self.assertIn("B.", self.text_of(b))
        self.assertTrue(a.state()["dirty"])
        self.assertFalse(b.state()["dirty"])
        self.assert_library_untouched()
        with a.scope():
            self.assertEqual([m["id"] for m in store.list_docs()], [a.doc_id])


class FileBrowser(Base):
    def test_listing_a_folder(self):
        for name in ("b10.md", "b2.md", "a.zip", "note.txt", ".hidden.md", "cat.png"):
            self.write(name, "x")
        (self.mine / "Zeta").mkdir()
        (self.mine / "alpha").mkdir()
        (self.mine / ".secret").mkdir()
        got = openfile.listing(str(self.mine))
        self.assertTrue(got["ok"])
        self.assertEqual([e["name"] for e in got["entries"]], ["alpha", "Zeta", "a.zip", "b2.md", "b10.md", "note.txt"])
        self.assertEqual([e["kind"] for e in got["entries"]][:2], ["dir", "dir"])
        self.assertTrue(all(e["openable"] for e in got["entries"] if e["kind"] == "file"))
        self.assertEqual(got["parent"], str(self.tmp))
        every = openfile.listing(str(self.mine), hidden=True, everything=True)
        self.assertIn(".hidden.md", [e["name"] for e in every["entries"]])
        self.assertEqual([e for e in every["entries"] if e["name"] == "cat.png"][0]["openable"], False)

    def test_a_typed_file_path_is_a_file_and_a_missing_one_gives_the_nearest_folder(self):
        path = self.write("lesson.md", LESSON)
        got = openfile.listing(str(path))
        self.assertEqual((got["ok"], got["kind"], got["path"]), (True, "file", str(path)))
        missing = openfile.listing(str(self.mine / "no" / "such"))
        self.assertEqual((missing["ok"], missing["code"], missing["path"]), (False, "gone", str(self.mine)))
        rel = openfile.listing("relative/path")
        self.assertEqual((rel["ok"], rel["code"]), (False, "path"))

    def test_the_places_are_there_to_start_from(self):
        names = [p["name"] for p in openfile.places()]
        self.assertIn("Home", names)


if __name__ == "__main__":
    unittest.main()
