# SPDX-License-Identifier: GPL-3.0-or-later
"""What the server is working on: the list every page shows.

    python3 -m unittest discover -s tests -p test_activity.py

Three layers, each with its own reason to break:

  * lib/activity.py, the registry: an entry begins, says how far it has
    got, ends, and stays on the "finished" list for KEEP seconds and no
    longer -- from many threads at once, because the server runs a thread
    a request;
  * serve.py's long_work, which decides from an address alone which
    requests are long work: every backup, bundle, restore, import, build
    and narration door is, and a page, a script, an edit or the poll
    itself is not;
  * serve.py's _dispatch and /__activity, driven over REAL HTTP against
    serve.py's own Handler on a temporary toolbox: a long request is on
    the list while it runs -- the upload while it is still arriving, the
    download while it is packed -- with the page it came from and the
    token that page gave it, and off it once the answer is written; a short
    one never is; and the book builds and the dictionary downloads are
    merged into the same list.
"""
import http.client
import json
import re
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in ("markdown/exlex", "markdown/app", "youtube/lib", "lib", "."):
    sys.path.insert(0, str(ROOT / folder))
import activity  # noqa: E402
import bookbuild  # noqa: E402
import guidebuild  # noqa: E402

MINI_EN = ROOT / "tests" / "fixtures" / "books" / "english" / "mini-en"


class Registry(unittest.TestCase):
    def setUp(self):
        activity.clear()
        self.addCleanup(activity.clear)

    def test_an_entry_begins_moves_on_and_ends(self):
        tok = activity.begin("upload", "Uploading x.zip", page="/books/", job="abc123",
                             total=1000, stage="receiving", now=100.0)
        snap = activity.snapshot(now=101.0)
        self.assertEqual([e["id"] for e in snap["running"]], [tok])
        e = snap["running"][0]
        self.assertEqual((e["kind"], e["label"], e["page"], e["job"], e["total"], e["stage"]),
                         ("upload", "Uploading x.zip", "/books/", "abc123", 1000, "receiving"))
        activity.progress(tok, done=400)
        activity.progress(tok, stage="installing")
        e = activity.snapshot(now=102.0)["running"][0]
        self.assertEqual((e["done"], e["total"], e["stage"]), (400, 1000, "installing"))
        activity.progress(tok, stage="")
        self.assertIsNone(activity.snapshot(now=102.0)["running"][0]["stage"],
                          "an empty stage clears it")
        activity.end(tok, ok=True, now=103.0)
        snap = activity.snapshot(now=104.0)
        self.assertEqual(snap["running"], [])
        self.assertEqual([(f["id"], f["ok"], f["finished"]) for f in snap["finished"]],
                         [(tok, True, 103.0)])

    def test_a_finished_entry_is_kept_for_a_while_and_then_forgotten(self):
        tok = activity.begin("download", "Packing", now=0.0)
        activity.end(tok, ok=False, now=10.0)
        self.assertEqual(len(activity.snapshot(now=10.0 + activity.KEEP)["finished"]), 1)
        self.assertEqual(activity.snapshot(now=10.1 + activity.KEEP)["finished"], [])

    def test_what_is_not_running_is_ignored(self):
        activity.progress(None, done=1)
        activity.progress("r-nothing", done=1)
        activity.end(None)
        activity.end("r-nothing")
        tok = activity.begin("build", "x")
        activity.end(tok)
        activity.end(tok)                       # twice: the second is nothing
        activity.progress(tok, done=5)
        self.assertEqual(len(activity.snapshot()["finished"]), 1)

    def test_a_token_or_a_page_that_is_not_one_is_dropped(self):
        self.assertEqual(activity.clean_job("k3j9-x_Z"), "k3j9-x_Z")
        for bad in ("", "a b", "<script>", "x" * 65, None, 7):
            self.assertIsNone(activity.clean_job(bad), bad)
        self.assertEqual(activity.clean_page("https://10.0.0.2:8765/books/?x=1#top"), "/books/?x=1")
        self.assertEqual(activity.clean_page("http://h/studio/doc/abc"), "/studio/doc/abc")
        for bad in (None, "", "javascript:alert(1)", "not a url"):
            self.assertIsNone(activity.clean_page(bad), bad)
        # a path a browser would read as ANOTHER SITE: every page makes it the
        # href of "open the page", and a request from another site may carry
        # a Referer of its choosing
        for off in ("http://attacker.example//evil.example/phish",
                    "http://h/\\evil.example/phish", "http://h/\t/evil.example/phish",
                    "http://h/books/ x", "http://h/books/\x7f"):
            self.assertIsNone(activity.clean_page(off), off)
        self.assertEqual(activity.clean_page("http://h/books/persian/%D8%A8/reader/?q=//x"),
                         "/books/persian/%D8%A8/reader/?q=//x")
        tok = activity.begin("upload", "x", job="<b>")
        self.assertIsNone(activity.snapshot()["running"][0]["job"])
        activity.end(tok)

    def test_sizes_are_said_the_way_a_person_says_them(self):
        self.assertEqual(activity.size(0), "0 bytes")
        self.assertEqual(activity.size(812), "812 bytes")
        self.assertEqual(activity.size(812_000), "812 kB")
        self.assertEqual(activity.size(2_300_000), "2.3 MB")
        self.assertEqual(activity.size(219_000_000), "219 MB")
        self.assertEqual(activity.size(4_400_000_000), "4.4 GB")

    def test_entries_made_elsewhere_are_merged_in_order(self):
        a = activity.begin("upload", "a", now=5.0)
        extra = [activity.entry("build:x", "build", "b", 1.0),
                 activity.entry("lookup:dict:fa", "lookup", "c", 2.0, finished=50.0, ok=True),
                 activity.entry("old", "lookup", "d", 0.0, finished=1.0, ok=True)]
        snap = activity.snapshot(extra, now=51.0)
        self.assertEqual([e["id"] for e in snap["running"]], ["build:x", a], "oldest first")
        self.assertEqual([e["id"] for e in snap["finished"]], ["lookup:dict:fa"],
                         "a finished job older than KEEP is not reported")
        activity.end(a)

    def test_many_threads_at_once(self):
        """A thread a request: begin, report and end from many at once, and
        nothing is lost, doubled or left running."""
        toks, lock = [], threading.Lock()

        def work():
            for i in range(200):
                t = activity.begin("download", "x")
                activity.progress(t, done=i, total=200)
                with lock:
                    toks.append(t)
                activity.snapshot()
                activity.end(t)
        threads = [threading.Thread(target=work) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(toks), 16 * 200)
        self.assertEqual(len(set(toks)), len(toks), "every entry has its own id")
        self.assertEqual(activity.snapshot()["running"], [])
        self.assertEqual(activity.running(), 0)


class LongWork(unittest.TestCase):
    """Which addresses are long work.  Asked with no toolbox behind them:
    the titles fall back to what the address says, and the answer is the
    same kind either way."""

    @classmethod
    def setUpClass(cls):
        import serve
        cls.serve = serve

    def kind(self, method, path, query=None, length=0):
        got = self.serve.long_work(method, path, query or {}, length)
        return got and got[0]

    def test_the_long_doors_are_long(self):
        yt, st, dk = "/youtube", "/studio", "/exercises"
        for method, path, kind in [
                ("GET", "/books/__backup", "backup"),
                ("GET", yt + "/api/backup", "backup"),
                ("GET", "/books/english/mini-en/__download", "download"),
                ("GET", "/books/mini-en/__download", "download"),
                ("GET", "/books/english/mini-en/reader/__narration/export", "download"),
                ("GET", yt + "/v/abc/__download", "download"),
                ("GET", "/anki/build/italian/casa.apkg", "build"),
                ("GET", "/anki/build/casa.apkg", "build"),
                ("POST", "/books/__upload", "upload"),
                ("POST", "/books/__restore", "restore"),
                ("POST", "/books/__empty", "build"),
                ("POST", "/books/english/mini-en/__append", "build"),
                ("POST", yt + "/api/upload", "upload"),
                ("POST", yt + "/api/restore", "restore"),
                ("POST", yt + "/api/local", "install"),
                ("POST", yt + "/api/add", "install"),
                ("POST", yt + "/api/prepare", "compile"),
                ("POST", "/anki/sync/upload", "upload"),
                ("POST", "/anki/sync/run", "install"),
                ("POST", "/anki/sync/bootstrap", "install"),
                ("GET", st + "/api/export", "backup"),
                ("POST", st + "/api/download", "download"),
                ("GET", st + "/download/note-abc123/zip", "download"),
                ("GET", st + "/download/note-abc123/pdf", "download"),
                ("GET", st + "/download/note-abc123/html", "download"),
                ("POST", st + "/api/docs/zip", "upload"),
                ("POST", st + "/api/library/zip", "restore"),
                ("POST", st + "/api/docs/note-abc123/build", "compile"),
                ("GET", dk + "/api/backup", "backup"),
                ("GET", dk + "/api/decks/italian/casa/export", "download"),
                ("POST", dk + "/api/decks/italian/casa/export-html", "download"),
                ("POST", dk + "/api/import", "upload"),
                ("POST", dk + "/api/restore", "restore"),
                # the notes of a book and of a video are the studio's routes
                ("GET", "/books/english/mini-en/notes/api/export", "backup"),
                ("POST", "/books/english/mini-en/notes/api/docs/zip", "upload"),
                ("POST", "/books/english/mini-en/notes/api/library/zip", "restore"),
                ("GET", yt + "/v/abc/notes/api/export", "backup"),
                ("POST", yt + "/v/abc/notes/api/library/zip", "restore")]:
            self.assertEqual(self.kind(method, path), kind, "%s %s" % (method, path))
        for what in ("audio", "import", "align", "spread", "region", "remove",
                     "restore", "transcript"):
            path = "/books/english/mini-en/reader/__narration/" + what
            self.assertEqual(self.kind("POST", path), "narration", path)
        self.assertEqual(self.kind("POST", "/books/english/mini-en/reader/__save/subtimes.json"),
                         "narration")

    def test_everything_else_is_not(self):
        for method, path in [
                ("GET", "/"), ("GET", "/__activity"), ("POST", "/__shutdown"),
                ("GET", "/lib/parseh.js"), ("GET", "/lib/activity.js"),
                ("GET", "/books/"), ("GET", "/books/english/mini-en/reader/"),
                ("GET", "/books/english/mini-en/reader/__narration/status"),
                ("GET", "/books/english/mini-en/__build/status"),
                ("POST", "/books/english/mini-en/__build"),       # a job: merged in instead
                ("POST", "/books/english/mini-en/reader/__edit/chunk"),
                ("POST", "/books/english/mini-en/reader/__save/review-corrections.json"),
                ("GET", "/books/english/mini-en/audio/part1.mp3"),
                ("GET", "/youtube/"), ("GET", "/youtube/v/abc/"),
                ("GET", "/youtube/videos/english/abc/media.mp4"),
                ("POST", "/youtube/api/edit"), ("POST", "/anki/cards"),
                # a transcription is one entry for the whole job (merged in, below),
                # not one for each of the many short requests that drive it
                ("POST", "/youtube/api/transcribe/start"),
                ("POST", "/youtube/api/transcribe/audio"),
                ("POST", "/youtube/api/transcribe/status"),
                ("GET", "/studio/"), ("GET", "/studio/download/note-abc123/md"),
                ("PUT", "/studio/api/docs/note-abc123"),
                ("GET", "/exercises/"), ("POST", "/exercises/api/decks/italian/casa/review"),
                ("POST", "/lookup/api/getdict"), ("GET", "/clips/")]:
            self.assertIsNone(self.serve.long_work(method, path, {}, 10), "%s %s" % (method, path))

    def test_a_note_s_page_does_not_look_its_book_or_video_up(self):
        """Every request under a notes mount -- each script and stylesheet of
        a note's page -- is asked about; naming the video walks the video
        shelf, so it is done only for the few that are long work."""
        asked = []
        with mock.patch.object(self.serve, "_video_named", lambda v: asked.append(v) or "V"), \
                mock.patch.object(self.serve, "_book_named", lambda p: asked.append(p) or "B"):
            for path in ("/youtube/v/abc/notes/static/app.js", "/youtube/v/abc/notes/doc/x/edit",
                         "/books/english/mini-en/notes/static/app.css",
                         "/books/english/mini-en/notes/api/docs"):
                self.assertIsNone(self.serve.long_work("GET", path, {}), path)
            self.assertEqual(asked, [], "nothing looked up for a request that is not long work")
            _k, label, _a = self.serve.long_work("GET", "/youtube/v/abc/notes/api/export", {})
            self.assertEqual((label, asked), ("Packing the backup of the notes on V", ["abc"]))
            _k, label, _a = self.serve.long_work(
                "POST", "/books/english/mini-en/notes/api/library/zip", {"name": ["b.zip"]}, 10)
            self.assertIn("the notes on B", label)

    def test_a_picture_or_a_recording_counts_only_when_it_is_big(self):
        for path in ("/studio/api/docs/note-abc123/images", "/studio/api/docs/note-abc123/audio",
                     "/exercises/api/decks/italian/casa/audio", "/studio/api/docs"):
            self.assertIsNone(self.serve.long_work("POST", path, {}, 200_000), path)
            self.assertEqual(self.kind("POST", path, length=self.serve.BIG_BODY + 1), "upload", path)

    def test_the_label_names_the_file_its_size_and_the_shape(self):
        _k, label, after = self.serve.long_work(
            "POST", "/books/__upload", {"name": ["momotaro-book.zip"]}, 219_000_000)
        self.assertIn("momotaro-book.zip", label)
        self.assertIn("(219 MB)", label)
        self.assertEqual(after, "installing")
        _k, label, _a = self.serve.long_work("GET", "/books/nowhere/x/__download",
                                             {"audio": ["full"]})
        self.assertIn("(all of it)", label)
        # a name is the page's word: a path in it is not a path here
        _k, label, _a = self.serve.long_work("POST", "/books/__restore",
                                             {"name": ["../../etc/passwd"]}, 10)
        self.assertNotIn("..", label)

    def test_a_title_in_another_script_is_isolated(self):
        """A Persian or Arabic title inside the English sentence is wrapped
        in FSI..PDI, so it cannot turn the sentence around it."""
        with tempfile.TemporaryDirectory() as td:
            book = Path(td) / "books" / "persian" / "boof"
            book.mkdir(parents=True)
            (book / "book.json").write_text(json.dumps(
                {"slug": "boof", "language": "fa", "title": "\u0628\u0648\u0641 \u06a9\u0648\u0631"}),
                encoding="utf-8")
            with mock.patch.object(self.serve._AtRoot, "directory", td):
                _k, label, _a = self.serve.long_work("GET", "/books/persian/boof/__download", {})
        self.assertIn("\u201c\u2068\u0628\u0648\u0641 \u06a9\u0648\u0631\u2069\u201d", label)


class OverHttp(unittest.TestCase):
    """serve.py's Handler on 127.0.0.1, over a temporary toolbox with the
    English fixture book on its shelf."""

    @classmethod
    def setUpClass(cls):
        import serve
        cls.serve = serve
        cls._td = tempfile.TemporaryDirectory()
        root = Path(cls._td.name)
        cls.book = root / "books" / "english" / "mini-en"
        shutil.copytree(MINI_EN, cls.book, ignore=shutil.ignore_patterns("reader"))
        os.symlink(str(ROOT / "lib"), str(root / "lib"))       # /lib/ is served off the root
        import prefs
        # the day of each backup is written beside prefs.json (lib/backupdays.py): into the tree, never config/
        cls.patches = [mock.patch.object(prefs, "STORE", str(root / "config" / "prefs.json")),
                       mock.patch.object(serve, "ROOT", str(root)),
                       mock.patch.object(serve._AtRoot, "directory", str(root)),
                       mock.patch.object(serve.studio.store, "LIB", root / "library"),
                       mock.patch.object(serve.Handler, "log_request", lambda *a, **k: None)]
        for p in cls.patches:
            p.start()
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        for p in reversed(cls.patches):
            p.stop()
        cls._td.cleanup()

    def setUp(self):
        activity.clear()
        self.addCleanup(activity.clear)
        self.addCleanup(bookbuild.JOBS.clear)

    def http(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        c.request(method, path, body, headers or {})
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, r.msg, raw

    def now(self):
        status, msg, raw = self.http("GET", "/__activity")
        self.assertEqual(status, 200)
        self.assertEqual(msg["Cache-Control"], "no-store")
        return json.loads(raw)

    def wait_for(self, test, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            j = self.now()
            if test(j):
                return j
            time.sleep(0.02)
        self.fail("the activity list never came to that: %r" % (j,))

    def in_background(self, *args, **kw):
        out = {}
        t = threading.Thread(target=lambda: out.update(r=self.http(*args, **kw)))
        t.start()
        return t, out

    def test_the_list_is_empty_and_never_lists_itself(self):
        j = self.now()
        self.assertEqual((j["running"], j["finished"], j["ok"]), ([], [], True))
        self.assertIsInstance(j["now"], float)
        self.assertEqual(self.http("POST", "/__activity", b"{}")[0], 405)

    def test_a_download_is_on_the_list_while_it_is_packed_and_then_it_is_not(self):
        gate, real = threading.Event(), self.serve.bundle.pack_book

        def slow(book, audio="linked"):
            gate.wait(10)
            return real(book, audio=audio)
        with mock.patch.object(self.serve.bundle, "pack_book", slow):
            t, out = self.in_background(
                "GET", "/books/english/mini-en/__download?audio=text&job=tok42",
                headers={"Referer": "http://127.0.0.1/books/english/mini-en/reader/"})
            j = self.wait_for(lambda j: j["running"])
            e = j["running"][0]
            self.assertEqual(e["kind"], "download")
            self.assertEqual(e["label"], "Packing \u201c\u2068The Clock and the Wind\u2069\u201d "
                                         "to download (the text alone)")
            self.assertEqual((e["job"], e["page"]), ("tok42", "/books/english/mini-en/reader/"))
            gate.set()
            t.join(20)
        status, msg, raw = out["r"]
        self.assertEqual(status, 200)
        self.assertEqual(msg["Content-Type"], "application/zip")
        j = self.now()
        self.assertEqual(j["running"], [], "off the list once the answer is written")
        self.assertEqual([(f["job"], f["ok"], f["done"], f["total"]) for f in j["finished"]],
                         [("tok42", True, None, None)],
                         "a zip of a few kilobytes goes in one write, uncounted")

    def test_an_upload_is_on_the_list_while_it_arrives(self):
        """Registered before the body is read: the entry is there while the
        bytes are still coming, and counts them -- here through the spool
        path a body over MAX_BODY takes, which reads a megabyte at a time."""
        body = os.urandom(3_000_000)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        with mock.patch.object(self.serve, "MAX_BODY", 1000):
            c.putrequest("POST", "/books/__upload?name=big-book.zip&job=up1")
            c.putheader("Content-Length", str(len(body)))
            c.putheader("Content-Type", "application/zip")
            c.endheaders()
            c.send(body[:1_500_000])
            j = self.wait_for(lambda j: j["running"] and j["running"][0]["done"])
            e = j["running"][0]
            self.assertEqual((e["kind"], e["job"], e["total"], e["stage"]),
                             ("upload", "up1", 3_000_000, "receiving"))
            self.assertIn("big-book.zip", e["label"])
            self.assertIn("(3.0 MB)", e["label"])
            self.assertEqual(e["done"], 1 << 20, "a megabyte in, of the one and a half sent")
            c.send(body[1_500_000:])
            r = c.getresponse()
            answer = json.loads(r.read())
            c.close()
        self.assertEqual(r.status, 400, answer)      # not a bundle: refused
        # the entry ends after the last byte of the answer is written -- a
        # moment after the client has read it, and not before
        f = self.wait_for(lambda j: j["finished"] and not j["running"])["finished"]
        self.assertEqual([(x["job"], x["ok"], x["done"], x["stage"]) for x in f],
                         [("up1", False, 3_000_000, "installing")],
                         "every byte counted, and a refusal is not ok")

    def test_a_refusal_with_a_200_is_not_ok_either(self):
        """The narration doors answer a run that failed {"ok": false} with a
        200 (the log is the answer); the list must not call that done."""
        answers = iter([{"ok": False, "error": "spread failed", "log": "..."},
                        {"ok": True, "log": "..."}])
        with mock.patch.object(self.serve.Handler, "_narration_spread",
                               lambda h: h.send_json(next(answers))):
            for _ in range(2):
                status, _m, _raw = self.http(
                    "POST", "/books/english/mini-en/reader/__narration/spread", b"{}",
                    {"Content-Type": "application/json"})
                self.assertEqual(status, 200)
        f = self.wait_for(lambda j: len(j["finished"]) == 2 and not j["running"])["finished"]
        self.assertEqual([(x["kind"], x["ok"]) for x in f],
                         [("narration", False), ("narration", True)])
        self.assertIn("The Clock and the Wind", f[0]["label"])

    def test_a_short_request_is_never_on_it(self):
        with mock.patch.object(activity, "begin", wraps=activity.begin) as begin:
            for path in ("/", "/lib/langs.css", "/books/english/mini-en/reader/__narration/status",
                         "/__activity", "/studio/api/tags"):
                self.http("GET", path)
            self.http("POST", "/books/english/mini-en/reader/__edit/meta", b"{}",
                       {"Content-Type": "application/json"})
            self.assertEqual(begin.call_count, 0)
            self.http("GET", "/books/__backup")
            self.assertEqual(begin.call_count, 1)
        f = self.wait_for(lambda j: j["finished"] and not j["running"])["finished"]
        self.assertEqual([x["label"] for x in f], ["Packing the backup of every book"])

    def test_a_book_build_is_merged_in_while_it_runs_and_for_a_while_after(self):
        gate = threading.Event()
        job, started = bookbuild.start(str(self.book), "pdf",
                                       runner=lambda cmd, say: (say("lualatex, pass 1"),
                                                                gate.wait(10), 0)[-1])
        self.assertTrue(started)
        j = self.now()
        name = "build:english/mini-en@%.3f" % job["started"]
        e = next(x for x in j["running"] if x["id"] == name)
        self.assertEqual((e["kind"], e["stage"], e["page"]),
                         ("build", "lualatex, pass 1", "/books/"))
        self.assertEqual(e["label"], "Building the PDF of \u201c\u2068The Clock and the Wind\u2069\u201d")
        gate.set()
        j = self.wait_for(lambda j: j["finished"])
        self.assertEqual([(x["id"], x["ok"]) for x in j["finished"]], [(name, True)])
        # the next build of the same book is another entry, not one a page
        # has already seen finish
        _job, started = bookbuild.start(str(self.book), "html", runner=lambda cmd, say: 0)
        self.assertTrue(started)
        self.assertNotEqual(self.serve.build_entry(str(self.book), _job["started"]), name)
        # and gone once it is older than KEEP
        later = time.time() + activity.KEEP + 5
        with mock.patch.object(activity.time, "time", lambda: later):
            self.assertEqual(self.serve.activity_now()["finished"], [])

    def test_the_build_route_names_its_entry(self):
        with mock.patch.object(bookbuild, "command", lambda b, w: ["true"]), \
                mock.patch.object(bookbuild, "_run", lambda job, cmd, runner: None):
            status, _m, raw = self.http("POST", "/books/english/mini-en/__build",
                                        b'{"what": "html"}', {"Content-Type": "application/json"})
            self.assertEqual(status, 200)
            first = json.loads(raw)
            name = "build:english/mini-en@%.3f" % first["started"]
            self.assertEqual(first["activity"], name)
            status, _m, raw = self.http("POST", "/books/english/mini-en/__build",
                                        b'{"what": "html"}', {"Content-Type": "application/json"})
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(raw)["activity"], name,
                         "the build already running is the one to follow")
        e = next(x for x in self.now()["running"] if x["id"] == name)
        self.assertIn("Rebuilding the reader of", e["label"])

    def test_the_guide_s_compile_is_merged_in_while_it_runs_and_for_a_while_after(self):
        self.addCleanup(guidebuild.JOB.clear)
        gate = threading.Event()
        job, started = guidebuild.start(runner=lambda cmd, say: (say("reading markdown/"), gate.wait(10), 0)[-1])
        self.assertTrue(started)
        name = "guide:compile@%.3f" % job["started"]
        e = next(x for x in self.now()["running"] if x["id"] == name)
        self.assertEqual((e["kind"], e["label"], e["stage"], e["page"]),
                         ("compile", "Compiling the guide", "reading markdown/", "/guide/"))
        gate.set()
        j = self.wait_for(lambda j: j["finished"])
        self.assertEqual([(x["id"], x["ok"]) for x in j["finished"]], [(name, True)])
        self.assertEqual(j["running"], [])
        # the next compile is another entry (there is one compile at a time,
        # and the job keeps only the last); a failed one is finished, not ok
        _job, started = guidebuild.start(runner=lambda cmd, say: 1)
        self.assertTrue(started)
        again = "guide:compile@%.3f" % _job["started"]
        self.assertNotEqual(again, name)
        j = self.wait_for(lambda j: [x["id"] for x in j["finished"]] == [again])
        self.assertFalse(j["finished"][0]["ok"])
        later = time.time() + activity.KEEP + 5
        with mock.patch.object(activity.time, "time", lambda: later):
            self.assertEqual(self.serve.activity_now()["finished"], [])

    def test_the_compile_route_names_its_entry(self):
        self.addCleanup(guidebuild.JOB.clear)
        # the compile never runs: the job stays "running" until the cleanup
        with mock.patch.object(guidebuild, "_run", lambda cmd, runner: None):
            status, _m, raw = self.http("POST", "/guide/__compile", b"{}",
                                        {"Content-Type": "application/json"})
            self.assertEqual(status, 200)
            first = json.loads(raw)
            self.assertTrue(first["started"])
            name = first["activity"]
            self.assertRegex(name, r"^guide:compile@\d+\.\d{3}$")
            status, _m, raw = self.http("POST", "/guide/__compile", b"{}",
                                        {"Content-Type": "application/json"})
        again = json.loads(raw)
        self.assertEqual((status, again["started"], again["activity"]), (200, False, name),
                         "the compile already running is the one to follow")
        self.assertIn(name, [x["id"] for x in self.now()["running"]])

    def test_the_lookup_jobs_are_merged_in_while_they_run(self):
        now = time.time()
        with mock.patch.dict(self.serve.DICT_JOBS, {
                "fa": {"running": True, "say": "reading the dump", "error": "", "started": now},
                "it": {"running": False, "say": "done", "error": "", "started": now - 60,
                       "finished": now - 1},
                "ja": {"running": False, "say": "done", "error": ""}}, clear=True), \
                mock.patch.dict(self.serve.MT_JOBS, {
                    "fa-en": {"running": True, "say": "", "error": "", "started": now}}, clear=True), \
                mock.patch.dict(self.serve.SYN_JOB, {"running": True, "say": "x", "error": "",
                                                     "started": now}, clear=True):
            j = self.now()
        run = {e["id"].split("@")[0]: e for e in j["running"]}
        self.assertEqual(run["lookup:dict:fa"]["label"], "Getting the Persian dictionary")
        self.assertEqual(run["lookup:dict:fa"]["stage"], "reading the dump")
        self.assertEqual(run["lookup:dict:fa"]["page"], "/settings/reading-help/")
        self.assertEqual(run["lookup:model:fa-en"]["label"],
                         "Getting the Persian\u2013English translation model")
        self.assertEqual(run["lookup:synonyms:"]["label"], "Getting the synonym table")
        self.assertEqual([e["id"] for e in j["finished"]], ["lookup:dict:it@%.3f" % (now - 60)])
        self.assertNotIn("lookup:dict:ja", run, "a job with no start time is from before")

    def test_a_transcription_is_merged_in_while_it_waits_runs_and_after(self):
        import sttjobs
        now = time.time()
        token = "SECRETtoken12345"

        def job(state, kind="youtube", **kw):
            return dict({"id": token, "kind": kind, "state": state, "created": now - 30,
                         "finished": None, "model": "large-v3-turbo", "hint": 600.0,
                         "have": 16000 * 2, "fell_back": False, "device": "cpu",
                         "device_name": "", "total": 100.0, "done": 39.0, "facts": None,
                         "error": None}, **kw)
        with mock.patch.dict(sttjobs.JOBS, {token: job("receiving")}, clear=True):
            j = self.now()
        (e,) = [e for e in j["running"] if e["id"].startswith("stt:")]
        # kind `narration` (what estimating by the sound already is), the page it
        # belongs to, what it is doing -- and NOT the token, which every page reads
        self.assertEqual((e["kind"], e["label"], e["page"], e["stage"]),
                         ("narration", "Transcribing a YouTube video", "/youtube/add/",
                          "Recording 0:02 / 10:00…"))
        self.assertNotIn(token, json.dumps(j))
        self.assertIsNone(e["job"])
        with mock.patch.dict(sttjobs.JOBS, {token: job("transcribing", "film")}, clear=True):
            j = self.now()
        (e,) = [e for e in j["running"] if e["id"].startswith("stt:film")]
        self.assertEqual((e["label"], e["stage"]),
                         ("Transcribing a film on this machine", "Transcribing on CPU… 39%"))
        done = job("done", "film", finished=now - 1, facts={"captions": 426}, done=100.0)
        with mock.patch.dict(sttjobs.JOBS, {token: done}, clear=True):
            j = self.now()
        self.assertEqual([x["id"].split("@")[0] for x in j["finished"]], ["stt:film"])
        self.assertTrue(j["finished"][0]["ok"])
        self.assertEqual(j["running"], [])
        old = job("failed", finished=now - activity.KEEP - 5,
                  error={"code": "failed", "say": "Transcription failed."})
        with mock.patch.dict(sttjobs.JOBS, {token: old}, clear=True):
            self.assertEqual(self.now()["finished"], [], "not kept beyond what the list keeps")

    def test_the_script_is_served(self):
        status, msg, raw = self.http("GET", "/lib/activity.js")
        self.assertEqual(status, 200)
        self.assertIn(b"window.ParsehActivity", raw)


class Pages(unittest.TestCase):
    """Every page reaches the list: parseh.js loads it beside itself, and the
    studio's and the exercises' templates, which do not load parseh.js,
    carry a tag of their own."""

    def test_parseh_js_loads_it_from_beside_itself(self):
        js = (ROOT / "lib" / "parseh.js").read_text(encoding="utf-8")
        self.assertIn("'activity.js'", js)
        self.assertIn("document.currentScript", js)

    # THE TWO PAGES THAT CARRY NO POLL, and why each is allowed to.
    # 404.html is answered where there is nothing to work on.  note.html is
    # the bare note page (2026-09-23): a note opens inside a reader, a dozen
    # times in a session, and what made that slow was every script a document
    # page carries -- so it carries NONE, and the reader underneath it is
    # already polling the list on its own behalf.  export_doc.html and
    # export_deck.html are no pages of the studio's at all: they are the
    # skeletons of the one file a page for a website is (webexport.py),
    # opened with no server behind it and forbidden to ask one for anything.
    NO_POLL = ("404.html", "note.html", "export_doc.html", "export_deck.html")

    def test_every_studio_template_but_the_404_carries_it(self):
        for t in sorted((ROOT / "markdown" / "app" / "templates").glob("*.html")):
            html = t.read_text(encoding="utf-8")
            if t.name in self.NO_POLL:
                continue
            self.assertIn('<script src="/lib/activity.js" async></script>', html, t.name)

    def test_a_page_for_a_website_loads_no_script_at_all(self):
        """Its exemption is a promise too: everything it runs is inside it."""
        for name in ("export_doc.html", "export_deck.html"):
            html = (ROOT / "markdown" / "app" / "templates" / name).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r'<script[^>]*\ssrc="([^"]+)"', html), [], name)
            self.assertNotIn("activity.js", html, name)

    def test_the_bare_note_page_carries_no_script_of_the_studios_at_all(self):
        """The exemption above is a promise, not a hole: what makes it safe to
        leave the poll out is that the page loads nothing."""
        html = (ROOT / "markdown" / "app" / "templates" / "note.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'<script[^>]*\ssrc="([^"]+)"', html), [],
                         "the bare note page loads no script")

    def test_the_client_hooks_the_same_downloads_the_server_lists(self):
        """A link activity.js follows by its token must be one long_work
        registers, or the page would wait for an entry that never comes."""
        import re
        import serve
        js = (ROOT / "lib" / "activity.js").read_text(encoding="utf-8")
        pattern = re.search(r"var DOWNLOAD = /(.+)/;", js).group(1).replace("\\/", "/")
        rx = re.compile(pattern)
        for path in ("/books/english/mini-en/__download", "/books/__backup",
                     "/youtube/api/backup", "/youtube/v/abc/__download",
                     "/books/english/mini-en/reader/__narration/export",
                     "/studio/api/export", "/studio/download/note-abc123/zip",
                     "/studio/download/note-abc123/pdf", "/studio/download/note-abc123/html",
                     "/exercises/api/backup", "/exercises/api/decks/italian/casa/export",
                     "/books/english/mini-en/notes/api/export",
                     "/anki/build/italian/casa.apkg", "/settings/api/backups/everything"):
            self.assertTrue(rx.search(path), path)
            self.assertIsNotNone(serve.long_work("GET", path, {}), path)
        for path in ("/studio/download/note-abc123/md", "/books/english/mini-en/reader/"):
            self.assertFalse(rx.search(path), path)

    def test_the_worker_leaves_every_download_to_the_browser(self):
        """TO-DO §2.28: a download made on demand, raced by lib/sw.js against
        its DEADLINE, fell to "Parseh cannot be reached" while the computer
        was still making it.  Every download the client follows, and the
        document's own Download ▾, is left to the browser; a page, a door
        and a kept file are not."""
        import re
        sw = (ROOT / "lib" / "sw.js").read_text(encoding="utf-8")
        rx = re.compile(re.search(r"const MADE_ON_DEMAND = /(.+)/;", sw).group(1).replace("\\/", "/"))
        for path in ("/books/english/mini-en/__download", "/books/__backup",
                     "/youtube/api/backup", "/youtube/v/abc/__download",
                     "/books/english/mini-en/reader/__narration/export",
                     "/studio/api/export", "/exercises/api/backup",
                     "/exercises/api/decks/italian/casa/export",
                     "/books/english/mini-en/notes/api/export",
                     "/anki/build/italian/casa.apkg",
                     "/settings/api/backups/settings", "/settings/api/backups/everything",
                     "/books/english/mini-en/notes/download/note-abc123/html",
                     *("/studio/download/note-abc123/" + k for k in ("md", "tex", "pdf", "zip", "html"))):
            self.assertTrue(rx.search(path), path)
        for path in ("/studio/doc/note-abc123", "/studio/api/docs", "/books/english/mini-en/reader/",
                     "/exercises/api/decks/italian/casa", "/studio/static/app.js",
                     "/books/english/mini-en/audio/part1.mp3", "/studio/download/"):
            self.assertFalse(rx.search(path), path)


if __name__ == "__main__":
    unittest.main()
