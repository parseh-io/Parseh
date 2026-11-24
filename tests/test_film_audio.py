# SPDX-License-Identifier: GPL-3.0-or-later
"""A sound in place of a video (W8): youtube/lib/filmkind.py, youtube/lib/filmdoor.py,
the media tables of lib/bundle.py, and the doors of serve.py that carry them.

    python3 -m unittest discover -s tests -p test_film_audio.py

What has to hold:

  * ANY SOUND IS ACCEPTED WHEREVER A FILM IS, and nothing else is: every extension
    of bundle.MEDIA_EXTS passes check_film, a page or a script never does, and
    the wording still says "is not a video this can play" (tests/test_stt_jobs.py
    pins it) and now names the sounds too;
  * THE KIND IS DECIDED ONCE, when the file is attached -- by ffprobe where there
    is one (an mp3 with the album's art inside is a sound), by the extension where
    there is not -- and video.json says it only for a sound ("kind": "audio"), so
    a film's video.json is the file it always was; a video made before the key
    reads from the extension (bundle.film_kind);
  * A SOUND THE BROWSER CANNOT PLAY gets a playable copy where ffmpeg is, with the
    original kept as media-orig.<ext> and never taken for the film; where ffmpeg
    is not, it is attached as it is and the answer says so in words;
  * REAL FILES, made by ffmpeg at test time (an mp3, an m4a, a wav, an ogg and a
    flac among them; a type this ffmpeg cannot make is skipped and said), added
    by path and by upload, played from the static route (the right Content-Type,
    Range), and carried by a bundle and back;
  * THE UPLOAD IS WHOLE OR NOT AT ALL, has no ceiling but the disk, and is refused
    in words: a name that is not media, an empty body, a file ffprobe cannot read,
    a disk with no room, a send cut short; from another site it is refused;
  * AN OLDER PARSEH opening a bundle that holds a sound accepts it and leaves the
    sound out, saying so (simulated by the media table it had).

Without ffmpeg the tests that need it skip.
"""
import http.client
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "youtube" / "lib", ROOT / "lib", ROOT):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import audiofile  # noqa: E402
import bundle     # noqa: E402
import filmkind   # noqa: E402

HAVE = audiofile.have_ffmpeg()
needs_ffmpeg = unittest.skipUnless(HAVE, "ffmpeg is not installed on this machine")
YT_FIXTURE = ROOT / "tests" / "fixtures" / "videos" / "english" / "eN5wX7zA9bC"
TRANSCRIPT = (YT_FIXTURE / "transcript.txt").read_text(encoding="utf-8")


def ff(*args):
    r = subprocess.run([audiofile.ffmpeg(), "-y", "-loglevel", "error"] + [str(a) for a in args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError("ffmpeg %s -> exit %d: %s" % (" ".join(map(str, args)), r.returncode, r.stderr))
    return str(args[-1])


def sine(out, secs=3, freq=440, *opts):
    return ff("-f", "lavfi", "-i", "sine=frequency=%d:duration=%s" % (freq, secs), *opts, out)


def make_sound(directory, ext, secs=3):
    """A real sound of this extension, or None where this ffmpeg cannot write it."""
    out = os.path.join(str(directory), "sound" + ext)
    try:
        if ext == ".weba":
            return sine(out, secs, 440, "-f", "webm")
        return sine(out, secs)
    except AssertionError:
        return None


def make_film(out, secs=2):
    return ff("-f", "lavfi", "-i", "testsrc=duration=%s:size=64x64:rate=5" % secs,
              "-f", "lavfi", "-i", "sine=frequency=440:duration=%s" % secs, "-shortest",
              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out)


def make_cover(directory):
    """An mp3 with a picture inside it, the way an album's is."""
    png = ff("-f", "lavfi", "-i", "color=c=red:size=64x64:duration=1", "-frames:v", "1",
             os.path.join(str(directory), "cover.png"))
    mp3 = sine(os.path.join(str(directory), "plain.mp3"))
    return ff("-i", mp3, "-i", png, "-map", "0:a", "-map", "1:v", "-c", "copy",
              "-id3v2_version", "3", "-disposition:v", "attached_pic",
              os.path.join(str(directory), "cover.mp3"))


def slurp(path):
    with open(str(path), "rb") as f:
        return f.read()


def video_json(directory):
    with open(os.path.join(str(directory), "video.json"), encoding="utf-8") as f:
        return json.load(f)


def new_video(directory, vid="v-a1b2c3", **more):
    """A video directory as /api/local makes one, with no film yet."""
    d = os.path.join(str(directory), vid)
    os.makedirs(d)
    meta = {"id": vid, "url": "", "title": "T", "language": "en", "gloss": "en"}
    meta.update(more)
    with open(os.path.join(d, "video.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    return d


# ==================================================================== the tables
class MediaTables(unittest.TestCase):
    def test_every_sound_the_brief_names_is_media_and_a_page_is_not(self):
        for ext in (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac", ".wma",
                    ".aiff", ".aif", ".amr", ".mka", ".weba", ".caf"):
            with self.subTest(ext=ext):
                self.assertIn(ext, bundle.MEDIA_EXTS)
                self.assertTrue(bundle.is_media_name("media" + ext))
                self.assertTrue(bundle.is_media_name("media" + ext.upper()), "case of the name")
        for name in ("media.html", "media.js", "media.svg", "media.txt", "media", "media.mp3.part",
                     "media.mp3.html", "x.mp3", "media-orig.mp3", "media-new.mp3", "Media.mp3x"):
            with self.subTest(name=name):
                self.assertFalse(bundle.is_media_name(name), "an allowlist: %s is not the film" % name)

    def test_the_original_of_a_playable_copy_is_its_own_name_and_never_the_film(self):
        self.assertTrue(bundle.is_orig_name("media-orig.wma"))
        self.assertFalse(bundle.is_orig_name("media.wma"))
        self.assertFalse(bundle.is_media_name("media-orig.wma"))
        self.assertFalse(bundle.is_orig_name("media-orig.html"))

    def test_the_narrations_own_list_is_what_it_was(self):
        # the books' narration is a different door: widening a video's media must not widen it
        self.assertEqual(bundle.AUDIO_EXTS, (".mp3", ".m4a", ".mp4", ".aac", ".webm", ".ogg", ".oga",
                                            ".opus", ".wav", ".flac"))

    def test_every_sound_type_the_static_route_names_is_a_sound(self):
        for ext, kind in bundle.SOUND_TYPES.items():
            self.assertIn(ext, bundle.SOUND_EXTS)
            self.assertTrue(kind.startswith("audio/"), (ext, kind))
        self.assertNotIn(".ogg", bundle.SOUND_TYPES, ".ogg stays what it was for the films that used it")

    def test_film_kind_reads_the_key_and_then_the_extension(self):
        with tempfile.TemporaryDirectory() as td:
            d = new_video(td)
            self.assertEqual(bundle.film_kind(d), "", "no film, no kind")
            for name, key, want in (("media.mp4", None, "video"), ("media.mp3", None, "audio"),
                                    ("media.ogg", None, "video"),     # a film in every video before this
                                    ("media.ogg", "audio", "audio"), ("media.mp3", "video", "video"),
                                    ("media.wma", None, "audio"), ("media.mkv", None, "video")):
                for old in os.listdir(d):
                    if bundle.is_media_name(old):
                        os.unlink(os.path.join(d, old))
                open(os.path.join(d, name), "wb").close()
                meta = {"id": "x"} if key is None else {"id": "x", "kind": key}
                with self.subTest(name=name, key=key):
                    self.assertEqual(bundle.film_kind(d, meta), want)
            # a kind that is neither word is not believed
            self.assertEqual(bundle.film_kind(d, {"kind": "hologram"}), "video")


class CheckFilm(unittest.TestCase):
    """The path door, widened and otherwise as it was."""

    def setUp(self):
        import ytpages
        self.ytpages = ytpages
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)

    def named(self, name, body=b"x"):
        p = os.path.join(self.td.name, name)
        with open(p, "wb") as f:
            f.write(body)
        return p

    def test_every_extension_of_the_media_table_is_taken_by_path(self):
        for ext in bundle.MEDIA_EXTS:
            with self.subTest(ext=ext):
                p = self.named("lesson" + ext)
                self.assertEqual(self.ytpages.check_film(p), (p, ext))
                self.assertEqual(self.ytpages.check_film('  "%s" ' % p), (p, ext), "quoted, as a paste is")

    def test_a_page_a_script_and_a_text_are_not(self):
        for ext in (".html", ".js", ".svg", ".txt", ".exe", ".pdf", ""):
            with self.subTest(ext=ext):
                with self.assertRaises(ValueError) as cm:
                    self.ytpages.check_film(self.named("lesson" + ext))
                said = str(cm.exception)
                self.assertIn("is not a video this can play", said, "the sentence tests/test_stt_jobs.py pins")
                self.assertIn("sound", said)
                self.assertIn(".mp3", said)
                self.assertIn(".mp4", said)

    def test_the_other_refusals_are_as_they_were(self):
        for raw, said in ((None, "name the film"), ("", "name the film"), ("   ", "name the film"),
                          (os.path.join(self.td.name, "gone.mp3"), "no file at"), (5, "has to be text")):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError) as cm:
                    self.ytpages.check_film(raw)
                self.assertIn(said, str(cm.exception))


# =============================================================== kind and the copy
@needs_ffmpeg
class Settle(unittest.TestCase):
    """attach_film on real files: the kind, the playable copy, the original."""

    @classmethod
    def setUpClass(cls):
        import ytpages
        cls.ytpages = ytpages
        cls.td = tempfile.TemporaryDirectory()
        cls.made, cls.skipped = {}, []
        for ext in (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".opus", ".aac", ".oga", ".wma", ".aiff",
                    ".aif", ".mka", ".caf", ".weba"):
            got = make_sound(cls.td.name, ext)
            if got:
                cls.made[ext] = got
                # one file per extension: the next make_sound would overwrite it
                moved = got + ".keep" + ext
                os.rename(got, moved)
                cls.made[ext] = moved
            else:
                cls.skipped.append(ext)
        cls.film = make_film(os.path.join(cls.td.name, "picture.mp4"))
        cls.cover = make_cover(cls.td.name)
        if cls.skipped:
            print("\nSettle: this ffmpeg cannot write %s, so those are not made" % ", ".join(cls.skipped),
                  file=sys.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)

    def test_a_real_sound_of_each_family_is_attached_as_a_sound(self):
        for ext in (".mp3", ".m4a", ".wav", ".ogg", ".flac"):
            self.assertIn(ext, self.made, "the five the brief names are made at test time")
        for ext, path in sorted(self.made.items()):
            with self.subTest(ext=ext):
                d = new_video(self.work.name, "v-%s-a1b2c3" % ext.lstrip("."))
                got = self.ytpages.attach_film(d, path)
                self.assertEqual(got["kind"], "audio")
                self.assertEqual(video_json(d).get("kind"), "audio", "video.json says it")
                self.assertEqual(bundle.film_kind(d), "audio")
                film = bundle.film_at(d)
                self.assertEqual(got["film"], film)
                self.assertTrue(film.startswith("media."), film)
                left = sorted(n for n in os.listdir(d) if n != "video.json")
                self.assertNotIn(film + ".part", left)
                self.assertFalse([n for n in left if n.endswith((".part", ".tmp"))], left)
                playable = ext in filmkind.NATIVE_EXTS
                self.assertEqual(got["converted"], not playable, "only a sound a browser cannot play is converted")
                if playable:
                    self.assertEqual(film, "media" + ext, "kept as it is")
                    self.assertEqual(slurp(os.path.join(d, film)), slurp(path))
                    self.assertEqual(got["original"], "")
                    self.assertEqual(left, [film])
                else:
                    self.assertEqual(got["original"], "media-orig" + ext)
                    self.assertEqual(sorted(left), sorted([film, "media-orig" + ext]))
                    self.assertEqual(slurp(os.path.join(d, "media-orig" + ext)), slurp(path),
                                     "the original is the person's file, whole")
                    # and what was made is a sound a browser plays, said by ffprobe
                    found = filmkind.probe(os.path.join(d, film))
                    self.assertEqual((found["video"], found["audio"]), (False, True))
                    self.assertIn(found["acodec"], filmkind.NATIVE_CODECS)

    def test_an_audio_only_mp4_or_webm_is_a_sound_a_browser_plays_as_it_is(self):
        # what ffprobe finds INSIDE decides: a film's container with no picture in it
        for ext, opts in ((".mp4", []), (".webm", ["-c:a", "libopus"])):
            src = os.path.join(self.work.name, "only" + ext)
            try:
                sine(src, 2, 440, *opts)
            except AssertionError:
                continue
            with self.subTest(ext=ext):
                d = new_video(self.work.name, "v-only-%s-a1b2c3" % ext.lstrip("."))
                got = self.ytpages.attach_film(d, src)
                self.assertEqual((got["film"], got["kind"], got["converted"]), ("media" + ext, "audio", False))
                self.assertEqual(video_json(d)["kind"], "audio")
                self.assertEqual(bundle.film_kind(d), "audio")

    def test_a_container_or_a_codec_a_browser_lacks_is_made_playable(self):
        out_ext = audiofile.best_output()[0]
        cases = []
        mkv = os.path.join(self.work.name, "only.mkv")
        sine(mkv, 2)
        cases.append(mkv)
        alac = os.path.join(self.work.name, "lossless.m4a")
        try:
            sine(alac, 2, 440, "-c:a", "alac")       # Apple's lossless: an .m4a that a browser cannot play
            cases.append(alac)
        except AssertionError:
            print("\nSettle: this ffmpeg cannot write ALAC, so that case is not made", file=sys.stderr)
        for src in cases:
            ext = os.path.splitext(src)[1]
            with self.subTest(src=os.path.basename(src)):
                d = new_video(self.work.name, "v-made-%s-a1b2c3" % ext.lstrip("."))
                got = self.ytpages.attach_film(d, src)
                self.assertEqual((got["film"], got["converted"], got["original"], got["kind"]),
                                 ("media" + out_ext, True, "media-orig" + ext, "audio"))
                self.assertEqual(slurp(os.path.join(d, "media-orig" + ext)), slurp(src))

    def test_a_film_keeps_its_video_json_as_it_always_was(self):
        d = new_video(self.work.name)
        before = slurp(os.path.join(d, "video.json"))
        got = self.ytpages.attach_film(d, self.film)
        self.assertEqual((got["film"], got["kind"], got["converted"]), ("media.mp4", "video", False))
        self.assertEqual(slurp(os.path.join(d, "video.json")), before,
                         "a video says nothing: not one byte of its video.json moved")
        self.assertEqual(bundle.film_kind(d), "video")

    def test_an_mp3_with_the_albums_picture_inside_is_still_a_sound(self):
        found = filmkind.probe(self.cover)
        self.assertEqual((found["video"], found["audio"]), (False, True), "a cover is not a picture of the film")
        d = new_video(self.work.name)
        self.assertEqual(self.ytpages.attach_film(d, self.cover)["kind"], "audio")

    def test_a_sound_replaces_a_film_and_a_film_a_sound(self):
        d = new_video(self.work.name)
        self.ytpages.attach_film(d, self.film)
        self.ytpages.attach_film(d, self.made[".mp3"])
        self.assertEqual(sorted(n for n in os.listdir(d) if n != "video.json"), ["media.mp3"],
                         "the old film left, after the new one had arrived")
        self.assertEqual(video_json(d)["kind"], "audio")
        self.ytpages.attach_film(d, self.film)
        self.assertEqual(sorted(n for n in os.listdir(d) if n != "video.json"), ["media.mp4"])
        self.assertNotIn("kind", video_json(d), "a film that replaces a sound takes the key off")

    def test_a_playable_copy_replaces_the_original_of_the_last_film_too(self):
        if ".wma" not in self.made:
            self.skipTest("this ffmpeg cannot write .wma")
        d = new_video(self.work.name)
        self.ytpages.attach_film(d, self.made[".wma"])
        self.assertEqual(sorted(n for n in os.listdir(d) if n != "video.json"), ["media-orig.wma", "media.mp3"])
        self.ytpages.attach_film(d, self.made[".mp3"])
        self.assertEqual(sorted(n for n in os.listdir(d) if n != "video.json"), ["media.mp3"],
                         "the original of the film that went goes with it")

    def test_where_ffmpeg_is_not_a_sound_a_browser_cannot_play_is_said_so(self):
        if ".wma" not in self.made:
            self.skipTest("this ffmpeg cannot write .wma")
        d = new_video(self.work.name)
        with mock.patch.object(audiofile, "ffmpeg", lambda: None), \
                mock.patch.object(filmkind, "ffprobe", lambda: None):
            looked = filmkind.look(self.made[".wma"])
            got = self.ytpages.attach_film(d, self.made[".wma"])
        self.assertEqual((looked["kind"], looked["playable"], looked["copy"]), ("audio", False, "none"))
        self.assertIn("ffmpeg", looked["note"])
        self.assertIn("not installed", looked["note"])
        self.assertEqual((got["film"], got["kind"], got["converted"]), ("media.wma", "audio", False),
                         "attached as it is: the person asked for it")
        self.assertIn("not installed", got["note"])
        self.assertEqual(video_json(d)["kind"], "audio", "decided by the extension where there is no ffprobe")

    def test_without_ffprobe_the_extension_decides(self):
        with mock.patch.object(filmkind, "ffprobe", lambda: None):
            for ext, kind in ((".mp3", "audio"), (".wav", "audio"), (".ogg", "audio"), (".mp4", "video"),
                              (".mkv", "video"), (".webm", "video"), (".wma", "audio")):
                with self.subTest(ext=ext):
                    self.assertEqual(filmkind.kind_of(ext, filmkind.probe("/nonexistent" + ext)), kind)

    def test_a_sound_ffmpeg_cannot_read_is_refused_and_the_video_keeps_its_film(self):
        d = new_video(self.work.name)
        self.ytpages.attach_film(d, self.film)
        junk = os.path.join(self.work.name, "junk.wma")
        with open(junk, "wb") as f:
            f.write(os.urandom(4096))
        with self.assertRaises(ValueError) as cm:
            self.ytpages.attach_film(d, junk)
        self.assertIn("ffmpeg could not read this sound", str(cm.exception))
        self.assertEqual(sorted(n for n in os.listdir(d) if n != "video.json"), ["media.mp4"],
                         "the film it had, and no half file of the new one")
        self.assertNotIn("kind", video_json(d))

    def test_a_film_that_was_sent_waits_in_the_dot_directory_and_goes_when_the_video_takes_it(self):
        videos = os.path.join(self.work.name, "videos")
        waiting = os.path.join(filmkind.staging(videos), "tok123")
        os.makedirs(waiting)
        sent = os.path.join(waiting, "lesson.mp3")
        shutil.copy(self.made[".mp3"], sent)
        mine = os.path.join(self.work.name, "mine.mp3")
        shutil.copy(self.made[".mp3"], mine)
        self.assertTrue(filmkind.staged(sent, videos))
        self.assertFalse(filmkind.staged(mine, videos), "the person's own file is never the server's to remove")
        self.assertFalse(filmkind.staged(os.path.join(waiting, "a", "b.mp3"), videos))
        filmkind.release(mine, videos)
        self.assertTrue(os.path.exists(mine))
        filmkind.release(sent, videos)
        self.assertFalse(os.path.exists(sent))
        self.assertFalse(os.path.exists(waiting), "and its folder")
        self.assertTrue(os.path.isdir(filmkind.staging(videos)))

    def test_what_was_sent_and_never_used_is_swept_after_two_days(self):
        videos = os.path.join(self.work.name, "videos")
        old = os.path.join(filmkind.staging(videos), "old")
        new = os.path.join(filmkind.staging(videos), "new")
        for d in (old, new):
            os.makedirs(d)
            with open(os.path.join(d, "a.mp3.part"), "wb") as f:
                f.write(b"half")
        past = time.time() - 3 * 86400
        for p in (old, os.path.join(old, "a.mp3.part")):
            os.utime(p, (past, past))
        filmkind.sweep(videos)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(new), "what is being written now is left alone")


# ===================================================================== the doors
@needs_ffmpeg
class Routes(unittest.TestCase):
    """serve.py's Handler over real HTTP, on a temporary toolbox."""

    @classmethod
    def setUpClass(cls):
        import serve
        import ytpages
        import filmdoor
        cls.serve, cls.ytpages, cls.filmdoor = serve, ytpages, filmdoor
        cls._td = tempfile.TemporaryDirectory()
        cls.root = Path(cls._td.name)
        cls.videos = cls.root / "youtube" / "videos"
        cls.videos.mkdir(parents=True)
        cls.media = Path(cls._td.name) / "media-in"
        cls.media.mkdir()
        # a YouTube video, which has no film and may be given none
        shutil.copytree(YT_FIXTURE, cls.videos / "english" / YT_FIXTURE.name)
        cls.patches = [mock.patch.object(serve, "ROOT", str(cls.root)),
                       mock.patch.object(serve._AtRoot, "directory", str(cls.root)),
                       mock.patch.object(ytpages, "VIDEOS", str(cls.videos)),
                       mock.patch.object(serve.studio.store, "LIB", cls.root / "library"),
                       mock.patch.object(serve.Handler, "log_request", lambda *a, **k: None)]
        for p in cls.patches:
            p.start()
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.sounds = {}
        for ext in (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".wma"):
            got = make_sound(cls.media, ext)
            if got:
                keep = os.path.join(str(cls.media), "in" + ext)
                os.rename(got, keep)
                cls.sounds[ext] = keep
        cls.film = make_film(os.path.join(str(cls.media), "picture.mp4"))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        for p in reversed(cls.patches):
            p.stop()
        cls._td.cleanup()

    # ---- plumbing
    def http(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
            headers = dict(headers or {}, **{"Content-Type": "application/json"})
        c.request(method, path, body, headers or {})
        r = c.getresponse()
        raw = r.read()
        out = (r.status, r.getheaders(), raw)
        c.close()
        return out

    def json_of(self, method, path, body=None, want=200, headers=None):
        status, _h, raw = self.http(method, path, body, headers)
        j = json.loads(raw.decode("utf-8"))
        self.assertEqual(status, want, "%s %s -> %d %s" % (method, path, status, raw[:300]))
        return j

    def send(self, path, name, data=None, want=200, headers=None, query=""):
        """A file SENT as the body, the way the pages send one."""
        if data is None:
            data = slurp(name)
        label = os.path.basename(name)
        return self.json_of("POST", "/youtube/api/film?name=%s%s" % (label, query), data, want,
                            dict(headers or {}, **{"Content-Type": "application/octet-stream"}))

    def waiting(self):
        base = os.path.join(str(self.videos), ".incoming")
        found = []
        for dirpath, _dirs, files in os.walk(base):
            found += [os.path.join(dirpath, f) for f in files]
        return sorted(found)

    def setUp(self):
        shutil.rmtree(os.path.join(str(self.videos), ".incoming"), ignore_errors=True)
        for d in list(self.videos.glob("*/*")):
            if d.name != YT_FIXTURE.name:
                shutil.rmtree(d, ignore_errors=True)

    def add_local(self, path, vid=None, **more):
        body = {"path": path, "lang": "en", "gloss": "en", "transcript": TRANSCRIPT}
        if vid:
            body["id"] = vid
        body.update(more)
        return self.json_of("POST", "/youtube/api/local", body)

    # ---- what a path names, and what is about to be sent
    def test_look_names_a_video_a_sound_and_a_refusal(self):
        v = self.json_of("POST", "/youtube/api/film/look", {"path": self.film})
        self.assertEqual((v["ok"], v["kind"], v["ext"], v["playable"], v["copy"]), (True, "video", ".mp4", True, ""))
        self.assertAlmostEqual(v["seconds"], 2.0, delta=0.2)
        self.assertEqual(v["bytes"], os.path.getsize(self.film))
        s = self.json_of("POST", "/youtube/api/film/look", {"path": self.sounds[".mp3"]})
        self.assertEqual((s["kind"], s["ext"], s["playable"], s["copy"], s["note"]), ("audio", ".mp3", True, "", ""))
        if ".wma" in self.sounds:
            w = self.json_of("POST", "/youtube/api/film/look", {"path": self.sounds[".wma"]})
            self.assertEqual((w["kind"], w["playable"], w["copy"]), ("audio", False, "made"))
            self.assertIn("playable copy", w["note"])
        bad = self.json_of("POST", "/youtube/api/film/look", {"path": str(self.root / "gone.mp3")}, want=400)
        self.assertIn("no file at", bad["error"])
        txt = self.root / "x.txt"
        txt.write_text("x")
        bad = self.json_of("POST", "/youtube/api/film/look", {"path": str(txt)}, want=400)
        self.assertIn("is not a video this can play", bad["error"])

    def test_look_at_a_file_about_to_be_sent_asks_the_kind_and_the_room_first(self):
        ok = self.json_of("POST", "/youtube/api/film/look", {"name": "lesson 1.MP3", "bytes": 5000000})
        self.assertEqual((ok["ok"], ok["kind"], ok["ext"], ok["bytes"]), (True, "audio", ".mp3", 5000000))
        self.assertGreater(ok["free"], 0)
        for body, want, said in (({"name": "a.txt", "bytes": 10}, 400, "name the file with its extension"),
                                 ({"name": "a.mp3", "bytes": 0}, 400, "empty"),
                                 ({"name": "a.mp3", "bytes": "10"}, 400, "empty"),
                                 ({"name": "a.mp3", "bytes": True}, 400, "empty")):
            with self.subTest(body=body):
                j = self.json_of("POST", "/youtube/api/film/look", body, want=want)
                self.assertIn(said, j["error"])
        with mock.patch.object(self.filmdoor, "_free", lambda where: 10 << 20):
            j = self.json_of("POST", "/youtube/api/film/look", {"name": "a.mp4", "bytes": 900 << 20}, want=507)
        self.assertIn("no room on this computer's disk", j["error"])
        self.assertIn("10 MB is free", j["error"])

    # ---- a file sent, whole
    def test_each_sound_is_sent_whole_and_waits_as_a_path(self):
        for ext in (".mp3", ".m4a", ".wav", ".ogg", ".flac"):
            self.assertIn(ext, self.sounds)
        for ext, src in sorted(self.sounds.items()):
            with self.subTest(ext=ext):
                self.setUp()
                j = self.send("/youtube/api/film", src)
                self.assertEqual((j["ok"], j["kind"], j["ext"], j["bytes"]),
                                 (True, "audio", ext, os.path.getsize(src)))
                self.assertTrue(os.path.isabs(j["path"]))
                self.assertEqual(slurp(j["path"]), slurp(src), "the bytes that were sent, whole")
                self.assertEqual(os.path.dirname(os.path.dirname(j["path"])),
                                 os.path.join(str(self.videos), ".incoming"))
                self.assertEqual(self.waiting(), [j["path"]], "nothing but the file: no .part is left")
                # and the path is one every door takes, exactly as one that was typed
                self.assertEqual(self.ytpages.check_film(j["path"]), (j["path"], ext))

    def test_a_sent_film_becomes_a_video_by_the_very_door_a_path_does(self):
        j = self.send("/youtube/api/film", self.film)
        self.assertEqual((j["kind"], j["ext"]), ("video", ".mp4"))
        got = self.add_local(j["path"])
        vid = got["id"]
        d = self.videos / got["folder"] / vid
        self.assertEqual(sorted(n for n in os.listdir(str(d))), ["annotations.json", "media.mp4", "transcript.txt",
                                                                 "video.json"])
        self.assertEqual(got["kind"], "video")
        self.assertEqual(slurp(d / "media.mp4"), slurp(self.film))
        self.assertEqual(self.waiting(), [], "the video took it: the waiting copy and its folder went")
        self.assertFalse(list((self.videos / ".incoming").glob("*")))

    def test_a_sent_sound_becomes_an_audio_video_that_plays_from_the_static_route(self):
        j = self.send("/youtube/api/film", self.sounds[".mp3"])
        got = self.add_local(j["path"], title="A sound")
        self.assertEqual((got["kind"], got["film"], got["converted"]), ("audio", "media.mp3", False))
        d = self.videos / got["folder"] / got["id"]
        self.assertEqual(video_json(d)["kind"], "audio")
        url = "/youtube/videos/%s/%s/media.mp3" % (got["folder"], got["id"])
        status, heads, raw = self.http("GET", url)
        types = {k.lower(): v for k, v in heads}
        self.assertEqual((status, types["content-type"]), (200, "audio/mpeg"), "not video/mp3")
        self.assertEqual(raw, slurp(self.sounds[".mp3"]))
        status, heads, part = self.http("GET", url, headers={"Range": "bytes=10-99"})
        types = {k.lower(): v for k, v in heads}
        self.assertEqual((status, len(part), types["content-range"].startswith("bytes 10-99/")), (206, 90, True))
        self.assertEqual(part, raw[10:100])
        # the player page says what it is, in the attribute the stylesheet reads and in its config
        status, _h, page = self.http("GET", "/youtube/v/%s/" % got["id"])
        page = page.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn('<html lang="en" data-lang="en" data-dir="ltr" data-kind="audio">', page)
        cfg = json.loads(re.search(r"<script>window\.YTFRANK=(\{.*?\})</script>", page, re.S).group(1))
        self.assertEqual((cfg["kind"], cfg["media"].endswith("/media.mp3"), cfg["local"]), ("audio", True, True))
        self.assertIn(".mp3", cfg["accept"])
        self.assertTrue(cfg["accept"].startswith("audio/*,video/*,"))
        # and the shelf says so, where a thumbnail would be
        status, _h, shelf = self.http("GET", "/youtube/c/on-this-machine/")
        self.assertEqual(status, 200)
        self.assertIn("&#9834; a sound", shelf.decode("utf-8"))

    def test_the_content_types_of_a_film_and_a_sound(self):
        got = self.add_local(self.sounds[".wav"], vid="a-sound-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        for name, want in (("media.wav", "audio/wav"),):
            status, heads, _raw = self.http("GET", "/youtube/videos/%s/%s/%s" % (got["folder"], got["id"], name))
            self.assertEqual((status, {k.lower(): v for k, v in heads}["content-type"]), (200, want))
        got2 = self.add_local(self.film, vid="a-film-a1b2c3")
        status, heads, _raw = self.http("GET", "/youtube/videos/%s/%s/media.mp4" % (got2["folder"], got2["id"]))
        self.assertEqual({k.lower(): v for k, v in heads}["content-type"], "video/mp4", "a film is still a film")
        self.assertTrue(d.is_dir())

    def test_a_sound_a_browser_cannot_play_is_added_with_a_playable_copy(self):
        if ".wma" not in self.sounds:
            self.skipTest("this ffmpeg cannot write .wma")
        j = self.send("/youtube/api/film", self.sounds[".wma"])
        self.assertEqual((j["kind"], j["playable"], j["copy"]), ("audio", False, "made"))
        got = self.add_local(j["path"])
        self.assertEqual((got["film"], got["converted"], got["original"]), ("media.mp3", True, "media-orig.wma"))
        self.assertIn("playable copy was made", got["note"])
        d = self.videos / got["folder"] / got["id"]
        self.assertEqual(sorted(os.listdir(str(d))), ["annotations.json", "media-orig.wma", "media.mp3",
                                                      "transcript.txt", "video.json"])
        self.assertEqual(self.waiting(), [])

    # ---- refused, in words, before the body is read
    def test_what_is_not_media_is_refused_and_nothing_is_kept(self):
        for name, data, want, said in (
                ("page.html", b"<script>alert(1)</script>", 400, "name the file with its extension"),
                ("lesson.mp3", b"", 400, "that file is empty"),
                ("noext", b"abc", 400, "name the file with its extension"),
                ("lesson.mp3", os.urandom(5000), 400, "not a video or a sound ffmpeg can read")):
            with self.subTest(name=name, n=len(data)):
                j = self.send("/youtube/api/film", name, data, want=want)
                self.assertFalse(j["ok"])
                self.assertIn(said, j["error"])
                self.assertEqual(self.waiting(), [])
                self.assertFalse(list((self.videos / ".incoming").glob("*")) if (self.videos / ".incoming").is_dir() else [],
                                 "not even the empty folder it was waiting in")

    def test_a_disk_with_no_room_is_refused_before_a_byte_is_read(self):
        with mock.patch.object(self.filmdoor, "_free", lambda where: 1 << 20):
            j = self.send("/youtube/api/film", self.sounds[".mp3"], want=507)
        self.assertIn("no room on this computer's disk", j["error"])
        self.assertEqual(self.waiting(), [])

    def test_a_send_cut_short_keeps_nothing(self):
        import socket
        body = slurp(self.sounds[".mp3"])
        s = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        # the Host names this computer: a plain request naming anything else is refused (421) before its body is
        # read -- the guard against DNS rebinding that plain http on loopback needs (a0.7.0, lib/localhttp.py)
        s.sendall(("POST /youtube/api/film?name=half.mp3 HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nContent-Type: "
                   "application/octet-stream\r\nContent-Length: %d\r\n\r\n" % (self.port, len(body))).encode())
        s.sendall(body[:len(body) // 2])
        time.sleep(0.3)
        self.assertTrue([p for p in self.waiting() if p.endswith(".part")], "half a file is being written")
        s.close()
        for _ in range(100):
            if not self.waiting():
                break
            time.sleep(0.05)
        self.assertEqual(self.waiting(), [], "whole or not at all: the half is gone, and no .mp3 stands in its place")

    def test_a_send_is_on_the_activity_list_while_it_arrives(self):
        kind, label, after = self.serve.long_work("POST", "/youtube/api/film", {"name": ["lesson 1.mp3"]}, 4 << 20)
        self.assertEqual(kind, "upload")
        self.assertIn("lesson 1.mp3", label)
        self.assertIn("MB", label, "the size comes from the request, never from the page's word")
        self.assertTrue(after)
        self.assertIsNone(self.serve.long_work("POST", "/youtube/api/film/look", {}, 40),
                          "a look is not long work, and neither is the picture of a sound")

    def test_from_another_site_it_is_refused_and_the_body_is_never_read(self):
        for site in ("cross-site", "same-site"):
            with self.subTest(site=site):
                j = self.send("/youtube/api/film", self.sounds[".mp3"], want=403,
                              headers={"Sec-Fetch-Site": site})
                self.assertFalse(j["ok"])
                self.assertEqual(self.waiting(), [])
        j = self.json_of("POST", "/youtube/api/film/look", {"path": self.film}, want=403,
                         headers={"Sec-Fetch-Site": "cross-site"})
        self.assertFalse(j["ok"])
        # its own page is let through
        self.send("/youtube/api/film", self.sounds[".mp3"], headers={"Sec-Fetch-Site": "same-origin"})

    def test_there_is_no_ceiling_but_the_disk(self):
        # past the 32 MB an ordinary JSON body is held to: streamed to a file, never held
        big = os.path.join(str(self.media), "big.wav")
        ff("-f", "lavfi", "-i", "sine=frequency=300:duration=210", "-ar", "48000", "-ac", "2", big)
        self.assertGreater(os.path.getsize(big), self.serve.MAX_BODY, "a body bigger than an edit is allowed to be")
        j = self.send("/youtube/api/film", big)
        self.assertEqual((j["ok"], j["bytes"]), (True, os.path.getsize(big)))
        self.assertEqual(os.path.getsize(j["path"]), os.path.getsize(big))
        os.unlink(big)

    # ---- sent to a video that is already here
    def test_a_film_sent_to_a_video_replaces_its_film_and_settles_the_kind(self):
        first = self.add_local(self.film, vid="lesson-a1b2c3")
        d = self.videos / first["folder"] / first["id"]
        j = self.send("/youtube/api/film", self.sounds[".mp3"], query="&video=lesson-a1b2c3")
        self.assertEqual((j["ok"], j["film"], j["kind"], j["video"]), (True, "media.mp3", "audio", "lesson-a1b2c3"))
        self.assertEqual(sorted(n for n in os.listdir(str(d)) if n.startswith("media")), ["media.mp3"])
        self.assertEqual(video_json(d)["kind"], "audio")
        self.assertEqual(self.waiting(), [], "it went straight into the video's folder, as media.mp3.part first")
        back = self.send("/youtube/api/film", self.film, query="&video=lesson-a1b2c3")
        self.assertEqual((back["film"], back["kind"]), ("media.mp4", "video"))
        self.assertNotIn("kind", video_json(d))

    def test_a_video_that_lost_its_film_is_given_one_again(self):
        got = self.add_local(self.film, vid="lost-film-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        os.unlink(str(d / "media.mp4"))
        page = self.http("GET", "/youtube/v/lost-film-a1b2c3/")[2].decode("utf-8")
        self.assertIn('"media": ""', page)
        self.assertIn('"local": true', page)
        j = self.send("/youtube/api/film", self.film, query="&video=lost-film-a1b2c3")
        self.assertTrue(j["ok"])
        self.assertTrue((d / "media.mp4").is_file())

    def test_a_video_on_youtube_and_a_video_that_is_not_there_are_refused(self):
        j = self.send("/youtube/api/film", self.sounds[".mp3"], want=400, query="&video=" + YT_FIXTURE.name)
        self.assertIn("is on YouTube", j["error"])
        j = self.send("/youtube/api/film", self.sounds[".mp3"], want=404, query="&video=nothing-here-a1b2c3")
        self.assertEqual(j["error"], "no such video")
        self.assertEqual(self.waiting(), [])
        self.assertEqual([p.name for p in (self.videos / "english" / YT_FIXTURE.name).iterdir()
                          if p.name.startswith("media")], [])

    def test_a_refused_send_to_a_video_leaves_the_film_it_had(self):
        got = self.add_local(self.film, vid="keep-film-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        before = slurp(d / "media.mp4")
        j = self.send("/youtube/api/film", "junk.mp3", os.urandom(4000), want=400, query="&video=keep-film-a1b2c3")
        self.assertIn("ffmpeg can read", j["error"])
        self.assertEqual(slurp(d / "media.mp4"), before)
        self.assertEqual(sorted(n for n in os.listdir(str(d)) if n.startswith("media")), ["media.mp4"])

    # ---- the picture of the sound
    def test_the_bar_is_drawn_from_the_shape_of_the_sound(self):
        got = self.add_local(self.sounds[".mp3"], vid="wave-sound-a1b2c3")
        j = self.json_of("POST", "/youtube/api/film/wave", {"video": got["id"], "buckets": 300})
        self.assertTrue(j["ok"])
        self.assertAlmostEqual(j["seconds"], 3.0, delta=0.2)
        self.assertGreaterEqual(len(j["peaks"]), 300)
        self.assertLessEqual(len(j["peaks"]), 1500)
        self.assertTrue(all(0.0 <= p <= 1.0 for p in j["peaks"]))
        self.assertEqual(max(j["peaks"]), 1.0, "scaled to the loudest: a quiet lesson still fills the bar")
        self.assertGreater(sum(1 for p in j["peaks"] if p > 0.5), len(j["peaks"]) // 2, "a steady tone is steady")
        again = self.json_of("POST", "/youtube/api/film/wave", {"video": got["id"], "buckets": 300})
        self.assertEqual(again, j, "remembered while the file is unchanged")
        with mock.patch.object(audiofile, "ffmpeg", lambda: None), \
                mock.patch.object(self.filmdoor.audiofile, "have_ffmpeg", lambda: False):
            no = self.json_of("POST", "/youtube/api/film/wave", {"video": got["id"], "buckets": 301}, want=409)
        self.assertIn("ffmpeg is not installed", no["error"])
        self.json_of("POST", "/youtube/api/film/wave", {"video": "nothing-a1b2c3"}, want=404)
        self.json_of("POST", "/youtube/api/film/wave", {"video": YT_FIXTURE.name}, want=400)

    # ---- the words, the prompt, the page's own files
    def test_the_prompt_names_a_sound_a_recording_and_a_film_a_film(self):
        for src, said, not_said in ((self.sounds[".mp3"], "a recording on the reader's own machine, not on YouTube",
                                     "a film on the reader's own machine"),
                                    (self.film, "a film on the reader's own machine, not on YouTube",
                                     "a recording on the reader's own machine")):
            with self.subTest(src=os.path.basename(src)):
                j = self.json_of("POST", "/youtube/api/prepare",
                                 {"path": src, "lang": "en", "gloss": "en", "transcript": TRANSCRIPT})
                self.assertTrue(j["ok"], j)
                self.assertTrue(j["local"])
                self.assertIn(said, j["prompt"])
                self.assertNotIn(not_said, j["prompt"])

    def test_the_prompt_is_prepared_without_looking_inside_the_file(self):
        # THE PAGE ASKS FOR A PROMPT AGAIN AND AGAIN as the person types: an ffprobe on every
        # ask made the answer arrive after the next keystroke (tests/add_stt.mjs went red on it)
        with mock.patch.object(filmkind, "probe", side_effect=AssertionError("looked inside the file")), \
             mock.patch.object(filmkind, "ffprobe", side_effect=AssertionError("looked for ffprobe")):
            j = self.json_of("POST", "/youtube/api/prepare",
                             {"path": self.sounds[".mp3"], "lang": "en", "gloss": "en", "transcript": TRANSCRIPT})
        self.assertTrue(j["ok"], j)
        self.assertIn("a recording on the reader's own machine, not on YouTube", j["prompt"])

    def test_the_add_page_has_the_looking_and_the_sending_and_serves_their_files(self):
        status, _h, raw = self.http("GET", "/youtube/add/")
        page = raw.decode("utf-8")
        self.assertEqual(status, 200)
        for need in ('<script src="/youtube/lib/addfilm.js"></script>', 'href="/youtube/lib/addfilm.css"',
                     'id="filmsend"', 'id="filmlook"', 'data-base="/youtube"', "A video or a sound on this machine",
                     "The video or sound", "media-orig.&lt;ext&gt;"):
            self.assertIn(need, page)
        accept = re.search(r'data-accept="([^"]*)"', page).group(1)
        self.assertTrue(accept.startswith("audio/*,video/*,"))
        for ext in bundle.MEDIA_EXTS:
            self.assertIn(ext, accept.split(","))
        # the two files the page links are on the static allowlist (this temporary
        # toolbox has no youtube/lib to serve them from: what is asked is the guard)
        for name in ("addfilm.js", "addfilm.css"):
            self.assertTrue(self.serve.static_ok("/youtube/lib/" + name), name + " is on the static allowlist")
            self.assertTrue((ROOT / "youtube" / "lib" / name).is_file())
        self.assertFalse(self.serve.static_ok("/youtube/lib/filmdoor.py"), "a module is never served")
        self.assertFalse(self.serve.static_ok("/youtube/videos/.incoming/x/lesson.mp3"),
                         "and what was sent and waits is never served")

    def test_a_sound_whose_file_has_gone_is_still_said_to_be_one(self):
        got = self.add_local(self.sounds[".mp3"], vid="gone-sound-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        os.unlink(str(d / "media.mp3"))
        page = self.http("GET", "/youtube/v/gone-sound-a1b2c3/")[2].decode("utf-8")
        self.assertIn('data-kind="audio"', page, "the small box a sound has, not a black frame with nothing in it")
        self.assertIn('"media": ""', page)
        self.assertIn('"local": true', page)

    def test_the_checker_and_the_video_info_sheet_leave_the_kind_alone(self):
        import check_annotations as CA
        got = self.add_local(self.sounds[".mp3"], vid="kept-kind-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        errors, warnings, _counts = CA.check(str(d))
        self.assertEqual(errors, [], "a video that says what its media is passes the same checks")
        self.assertFalse([w for w in warnings if "kind" in w], warnings)
        # the sheet that edits the title, the channel and the rest writes video.json whole
        self.ytpages.edit_meta(str(d), {"title": "Another title"})
        meta = video_json(d)
        self.assertEqual((meta["title"], meta["kind"]), ("Another title", "audio"))
        j = self.json_of("POST", "/youtube/api/editmeta", {"video": got["id"], "fields": {"blurb": "A sound."}})
        self.assertTrue(j["ok"])
        self.assertEqual(video_json(d)["kind"], "audio")

    def test_what_a_phone_keeps_of_a_sound_video_is_its_media_too(self):
        import offline
        got = self.add_local(self.sounds[".mp3"], vid="phone-sound-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        # what a phone keeps remembers the digests of what it weighed, in config/: not in a test's
        with mock.patch.object(offline, "DIGESTS", str(self.root / "digests.json")), \
                mock.patch.object(offline, "WHERES", str(self.root / "wheres.json")):
            rec = offline.video(str(d), got["id"], "/youtube")
        media = [m["url"] for m in rec["media"]]
        self.assertEqual([u for u in media if u.endswith("/media.mp3")], ["/youtube/videos/%s/%s/media.mp3"
                                                                          % (got["folder"], got["id"])])

    # ---- a bundle carries the sound, and an older Parseh still takes the bundle
    def test_a_bundle_carries_the_sound_and_not_the_original(self):
        if ".wma" not in self.sounds:
            self.skipTest("this ffmpeg cannot write .wma")
        got = self.add_local(self.sounds[".wma"], vid="bundle-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        data, name = bundle.pack_video(str(d))
        self.assertTrue(name.endswith("-full.zip"), name)
        z = zipfile.ZipFile(io.BytesIO(data))
        names = [n.split("/", 1)[1] for n in z.namelist() if "/" in n]
        self.assertIn("media.mp3", names)
        self.assertNotIn("media-orig.wma", names, "the copy is what the next machine plays")
        info = z.getinfo("bundle-a1b2c3/media.mp3")
        self.assertEqual(info.compress_type, zipfile.ZIP_STORED, "stored, as a film is")
        text, tname = bundle.pack_video(str(d), "text")
        self.assertNotIn("media.mp3", [n.split("/", 1)[1] for n in zipfile.ZipFile(io.BytesIO(text)).namelist() if "/" in n])
        with tempfile.TemporaryDirectory() as into:
            os.makedirs(os.path.join(into, "youtube", "videos"))
            r = bundle.install(data, root=into)
            back = os.path.join(into, r["dir"])
            self.assertEqual(slurp(os.path.join(back, "media.mp3")), slurp(d / "media.mp3"))
            self.assertEqual(video_json(back)["kind"], "audio", "the kind came back with it")
            self.assertEqual(bundle.film_kind(back), "audio")
            self.assertEqual(r["dropped"], [])
        # and the download button, the door a person uses, hands over the same
        status, _h, raw = self.http("GET", "/youtube/v/bundle-a1b2c3/__download")
        self.assertEqual(status, 200)
        inside = zipfile.ZipFile(io.BytesIO(raw)).namelist()
        self.assertIn("bundle-a1b2c3/media.mp3", inside)
        self.assertNotIn("bundle-a1b2c3/media-orig.wma", inside)

    def test_a_bundle_made_before_the_key_reads_its_kind_from_the_extension(self):
        got = self.add_local(self.sounds[".mp3"], vid="old-bundle-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        meta = video_json(d)
        meta.pop("kind")
        with open(str(d / "video.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
        self.assertEqual(bundle.film_kind(str(d)), "audio")
        data, _name = bundle.pack_video(str(d))
        with tempfile.TemporaryDirectory() as into:
            os.makedirs(os.path.join(into, "youtube", "videos"))
            r = bundle.install(data, root=into)
            self.assertEqual(bundle.film_kind(os.path.join(into, r["dir"])), "audio")

    def test_an_older_parseh_accepts_a_bundle_that_holds_a_sound_and_leaves_the_sound_out(self):
        got = self.add_local(self.sounds[".mp3"], vid="older-a1b2c3")
        d = self.videos / got["folder"] / got["id"]
        data, _name = bundle.pack_video(str(d))
        # the media table that Parseh had: a film was one of these, and a sound was not
        with mock.patch.object(bundle, "MEDIA_EXTS", bundle.VIDEO_EXTS):
            with tempfile.TemporaryDirectory() as into:
                os.makedirs(os.path.join(into, "youtube", "videos"))
                r = bundle.install(data, root=into)
                self.assertTrue(r["ok"], "accepted, not refused")
                self.assertEqual(r["dropped"], ["media.mp3"])
                self.assertTrue([n for n in r["notes"] if "media.mp3" in n and "left out" in n], r["notes"])
                self.assertFalse(os.path.exists(os.path.join(into, r["dir"], "media.mp3")))
                self.assertTrue(os.path.exists(os.path.join(into, r["dir"], "annotations.json")),
                                "the words came: only what that Parseh cannot play was left behind")


# ================================================== speech to text, on a sound
class SpeechOnASound(unittest.TestCase):
    """A sound is a film to the transcription job.  The add flow's own validators take
    its path (check_film, through sttjobs.source_of) and the job reads it with the
    stand-in runtime of tests/stt_fakes.py -- a real 16-bit WAV with a sound's own
    name, which this job refused before, as it refused every film that was not a video."""

    def setUp(self):
        try:
            import numpy  # noqa: F401  the stand-in runtime and the worker count with it
            sys.path.insert(0, str(ROOT / "tests"))
            try:
                import stt_fakes
            finally:
                sys.path.pop(0)
            import sttjobs
        except ImportError as e:
            self.skipTest("the stand-in speech runtime is not available here (%s)" % e)
        import ytpages
        self.stt_fakes, self.sttjobs = stt_fakes, sttjobs
        self.td = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.td.cleanup)
        self.root = self.td.name
        os.makedirs(os.path.join(self.root, "videos"))
        held = stt_fakes.installed(self.root)
        self.gs = held.__enter__()
        self.addCleanup(held.__exit__, None, None, None)
        moved = mock.patch.object(ytpages, "VIDEOS", os.path.join(self.root, "videos"))
        moved.start()
        self.addCleanup(moved.stop)
        quiet = mock.patch.object(sys, "stderr", io.StringIO())
        quiet.start()
        self.addCleanup(quiet.stop)
        sttjobs.JOBS.clear()
        sttjobs.TOMBS.clear()
        self.addCleanup(self.reset)

    def reset(self):
        self.sttjobs.stop_all()
        end = time.time() + 8
        while self.sttjobs.CHILDREN and time.time() < end:
            time.sleep(0.05)
        self.sttjobs.JOBS.clear()
        self.sttjobs.TOMBS.clear()
        self.sttjobs.CHILDREN.clear()

    def test_a_sound_is_named_and_transcribed_as_a_film_is(self):
        for ext in (".wav", ".mp3"):
            with self.subTest(ext=ext):
                path = self.stt_fakes.write_wav(os.path.join(self.root, "lesson" + ext), 3)
                source, lang = self.sttjobs.source_of({"source": "film", "path": path, "lang": "en"})
                self.assertEqual((source, lang), ({"kind": "film", "path": path}, "en"))
                got = self.sttjobs.start(source, lang, "large-v3-turbo", "cpu")
                self.assertEqual((got["state"], got["need"], got["kind"], got["film"]),
                                 ("queued", "", "film", "lesson" + ext))
                end, state = time.time() + 40, None
                while time.time() < end:
                    state = self.sttjobs.status(got["job"])["state"]
                    if state in ("done", "failed", "cancelled"):
                        break
                    time.sleep(0.03)
                self.assertEqual(state, "done")
                self.assertTrue(self.sttjobs.result(got["job"])["text"].strip(),
                                "a transcript, in the panel the add page reads")
                self.reset()

    def test_what_is_not_media_is_still_refused_in_the_films_own_words(self):
        txt = os.path.join(self.root, "lesson.txt")
        open(txt, "w").close()
        with self.assertRaises(self.sttjobs.Refusal) as cm:
            self.sttjobs.source_of({"source": "film", "path": txt, "lang": "en"})
        self.assertIn("is not a video this can play", str(cm.exception))
