# SPDX-License-Identifier: GPL-3.0-or-later
"""Edits to one book or one video at once all survive (TO-DO §3.10).

    python3 -m unittest tests.test_concurrent_edits

An edit reads the chapter (or annotations.json), changes one chunk and writes
the whole file back, on a server that answers each request on a thread of its
own -- and wrote through ONE temporary name, `path + ".tmp"`.  Two tabs, or a
phone and the computer, editing two chunks at once lost one of the edits, or
had the second write truncate the first's temporary file (an error answer).

Here serve.py's real Handler runs on 127.0.0.1 over a temporary tree holding
the English fixture book and the English fixture video, and a dozen edits to
DIFFERENT chunks are fired at the real routes at the same moment
(/books/.../__edit/chunk and /youtube/api/edit).  Every answer must be a 200
and every edit must be in the file at the end.  The window between the read
and the write is widened (the read waits a moment after it has read) so that
the old code loses edits on every run, not only on an unlucky one.
"""
import http.client
import json
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
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    if str(ROOT / p) not in sys.path:
        sys.path.insert(0, str(ROOT / p))

MINI_EN = ROOT / "tests" / "fixtures" / "books" / "english" / "mini-en"
VIDEO = "eN5wX7zA9bC"
VIDEO_FIX = ROOT / "tests" / "fixtures" / "videos" / "english" / VIDEO
WIDEN = 0.15


class Concurrent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import serve
        import annwrite
        import network
        import prefs
        import offline
        import texwrite
        import ytpages
        cls.serve, cls.annwrite, cls.texwrite = serve, annwrite, texwrite
        cls._td = tempfile.TemporaryDirectory()
        root = Path(cls._td.name)
        cls.book = root / "books" / "english" / "mini-en"
        shutil.copytree(MINI_EN, cls.book, ignore=shutil.ignore_patterns("reader"))
        videos = root / "youtube" / "videos"
        cls.video = videos / "english" / VIDEO
        shutil.copytree(VIDEO_FIX, cls.video)
        os.symlink(str(ROOT / "lib"), str(root / "lib"))       # /lib/ is served off the root
        cfg = root / "config"
        cls.patches = [mock.patch.object(serve, "ROOT", str(root)),
                       mock.patch.object(serve._AtRoot, "directory", str(root)),
                       mock.patch.object(serve.studio.store, "LIB", root / "library"),
                       mock.patch.object(ytpages, "VIDEOS", str(videos)),
                       mock.patch.object(prefs, "STORE", str(cfg / "prefs.json")),
                       mock.patch.object(network, "STORE", str(cfg / "network.json")),
                       mock.patch.object(offline, "DIGESTS", str(cfg / "digests.json")),
                       mock.patch.object(offline, "WHERES", str(cfg / "wheres.json")),
                       # the reader is rebuilt after each book edit; that is not
                       # what is tested here, and twelve rebuilds take long
                       mock.patch.object(serve.Handler, "_rebuild_reader", lambda self, b: None),
                       mock.patch.object(serve.Handler, "log_request", lambda *a, **k: None),
                       mock.patch.object(serve.Handler, "log_message", lambda *a, **k: None)]
        for p in cls.patches:
            p.start()
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        for p in reversed(cls.patches):
            p.stop()
        cls._td.cleanup()

    def post(self, path, body):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        c.request("POST", path, json.dumps(body).encode("utf-8"),
                  {"Content-Type": "application/json"})
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, raw

    def fire(self, calls):
        """Every call at the same moment -> [(status, raw)] in the calls' order."""
        out = [None] * len(calls)
        gate = threading.Barrier(len(calls))

        def one(i, path, body):
            gate.wait()
            out[i] = self.post(path, body)
        ts = [threading.Thread(target=one, args=(i,) + c) for i, c in enumerate(calls)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(300)
        return out

    def test_a_book(self):
        import texparse  # noqa: F401  (the reader's own count of the chunks)
        chapter = self.book / "ch1.tex"
        n = len(self.texwrite.read_chunks(str(chapter)))
        self.assertGreaterEqual(n, 6)
        real = self.texwrite._read

        def slow(path):
            text = real(path)
            time.sleep(WIDEN)
            return text
        want = {i: "edited at once %d" % i for i in range(n)}
        with mock.patch.object(self.texwrite, "_read", slow):
            got = self.fire([("/books/english/mini-en/reader/__edit/chunk",
                              {"index": i, "fields": {"en": want[i]}}) for i in want])
        for (status, raw), i in zip(got, want):
            self.assertEqual(status, 200, "edit %d: %s" % (i, raw[:300]))
        on_disk = self.texwrite.read_chunks(str(chapter))
        lost = [i for i in want if on_disk[i].get("en") != want[i]]
        self.assertEqual(lost, [], "edits lost: %d of %d" % (len(lost), n))
        self.assertEqual([p for p in os.listdir(self.book) if p.endswith(".tmp")], [])

    def test_a_video(self):
        ann = self.annwrite.read(str(self.video))
        where = [(s, c) for s, sg in enumerate(ann["segments"])
                 for c, ch in enumerate(sg.get("chunks") or []) if not ch.get("plain")]
        self.assertGreaterEqual(len(where), 6)
        real = self.annwrite.read

        def slow(video_dir):
            got = real(video_dir)
            time.sleep(WIDEN)
            return got
        want = {w: "a note at once %d.%d" % w for w in where}
        with mock.patch.object(self.annwrite, "read", slow):
            got = self.fire([("/youtube/api/edit",
                              {"video": VIDEO, "segment": s, "chunk": c,
                               "fields": {"note": want[(s, c)]}}) for s, c in where])
        for (status, raw), w in zip(got, where):
            self.assertEqual(status, 200, "edit %s: %s" % (w, raw[:300]))
        ann = self.annwrite.read(str(self.video))
        lost = [w for w in where if ann["segments"][w[0]]["chunks"][w[1]].get("note") != want[w]]
        self.assertEqual(lost, [], "edits lost: %d of %d" % (len(lost), len(where)))
        self.assertEqual([p for p in os.listdir(self.video) if p.endswith(".tmp")], [])


if __name__ == "__main__":
    unittest.main()
