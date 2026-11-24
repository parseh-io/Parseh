# SPDX-License-Identifier: GPL-3.0-or-later
"""The exchange of sync (lib/syncexchange.py, lane B; docs/sync.md).

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_exchange.py

Two temporary installs (tests/syncfake.py) wired together in one process,
each with its own shelves, config stores and change log, written through the
real modules (the studio store, the decks, the clip tray, prefs):

  * one-side changes travel both ways, with no question, for a studio
    document with a picture, a deck's exercise, a video's files, a clip and a
    setting; a second sync moves nothing; the version replaced is kept for a day;
  * a file the receiver already has (in any unit) is never sent;
  * a transfer cut off halfway leaves the receiver untouched, and the next
    sync goes on from the chunk it reached; a write cut off by a crash is
    finished by recover(), recorded as the partner's version;
  * a unit an editor holds waits, and comes once the editor closes;
  * a change on both sides and a deletion are left untouched on both sides
    and listed in pending(); a rule given in RULES settles one;
  * a left-out book is listed by elsewhere() and fetched on demand;
  * the scheduler: at start, after a change here, when a partner comes
    back, never two syncs with one partner at once.
"""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import syncfake                 # noqa: E402
from syncfake import World      # noqa: E402
import clips                    # noqa: E402
import decks                    # noqa: E402
import prefs                    # noqa: E402
import store                    # noqa: E402
import syncexchange as X        # noqa: E402
import synckeep                 # noqa: E402
import synclock                 # noqa: E402
import synclog                  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"a picture"
FLASH = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\n:::"


def row(w, inst, uid):
    with w.on(inst):
        synclog.scan()
        return synclog.get(uid)


def units(w, inst, prefix=""):
    with w.on(inst):
        synclog.scan()
        return {r["unit"]: r["hash"] for r in synclog.rows(prefix, deleted=False)}


def video(inst, vid="v1", media=b"film" * 10, text="one\ntwo\n"):
    base = "youtube/videos/persian/%s/" % vid
    inst.w(base + "video.json", '{"title": "V"}')
    inst.w(base + "transcript.txt", text)
    inst.w(base + "annotations.json", "{}")
    inst.w(base + "media.mp4", media)
    return "video:persian/%s" % vid


def clip(inst, name="c.mp3", data=b"sound"):
    with inst.world.on(inst):
        with open(os.path.join(clips.DIR, name), "wb") as fh:
            fh.write(data)
        clips._write_json(os.path.join(clips.DIR, name + ".json"), {"lang": "fa"})
    return "clip:" + name


class Exchange(unittest.TestCase):
    def setUp(self):
        self.w = World("A", "B").__enter__()
        self.A, self.B = self.w.A, self.w.B

    def tearDown(self):
        self.w.__exit__(None, None, None)

    def pull(self, into, frm, **kw):
        with self.w.on(into):
            return X.sync_from(frm.id, **kw)

    def both(self, a, b):
        with self.w.on(a):
            return X.sync_with(b.id)

    # ---------------------------------------------------------------- one side
    def test_one_side_both_ways_and_kept_for_a_day(self):
        A, B, w = self.A, self.B, self.w
        with w.on(A):
            meta = store.create("---\nlang: fa\n---\n# Doc\n\nسلام\n")
            img = store.save_image(meta["id"], "p.png", PNG)
            deck = decks.create_deck("Words", "fa")
            item = decks.add_item(deck["folder"], deck["slug"], FLASH)
        doc_uid = next(u for u in units(w, A, "doc:"))
        item_uid = next(u for u in units(w, A, "item:"))
        vid = video(B)
        c = clip(B)
        with w.on(B):
            prefs.set_settings({"parseh_theme": {"v": "dark", "at": time.time()}}, by="t")
        got = self.both(A, B)
        self.assertTrue(got["complete"], got)
        self.assertEqual(sorted(got["taken"]), sorted([vid, c, "setting:parseh_theme"]))
        self.assertTrue(got["nudged"]["ok"] and got["nudged"]["complete"], got["nudged"])
        ua, ub = units(w, A), units(w, B)
        self.assertEqual(ua, ub)                                     # the same hashes on both
        for uid in (doc_uid, item_uid, vid, c, "setting:parseh_theme", "deck:" + item_uid[5:].rsplit("/", 1)[0]):
            self.assertIn(uid, ub)
            self.assertEqual(row(w, A, uid)["vv"], row(w, B, uid)["vv"], uid)
        self.assertEqual(B.read("markdown/library/" + doc_uid[4:] + "/images/" + img), PNG)
        with w.on(A):
            self.assertEqual(prefs.settings()["parseh_theme"]["v"], "dark")
        # a second sync moves nothing
        again = self.both(A, B)
        self.assertEqual((again["taken"], again["blobs"]["chunks"]), ([], 0))
        # changed on B only -> A takes it; A's old version kept for a day
        with w.on(B):
            decks.update_item(deck["folder"], deck["slug"], item["id"],
                              FLASH.replace("cat", "a cat"))
            prefs.set_settings({"parseh_theme": {"v": "light", "at": time.time() + 1}}, by="t")
        old = A.read("exercises/" + item_uid[5:].rsplit("/", 1)[0] + "/items/%s.json" % item["id"])
        got = self.pull(A, B)
        deck_uid = "deck:" + item_uid[5:].rsplit("/", 1)[0]          # the deck's "updated" moved too
        self.assertEqual(sorted(got["taken"]), sorted([deck_uid, item_uid, "setting:parseh_theme"]))
        self.assertIn(b"a cat", A.read("exercises/" + item_uid[5:].rsplit("/", 1)[0]
                                       + "/items/%s.json" % item["id"]))
        with w.on(A):
            self.assertEqual(prefs.settings()["parseh_theme"]["v"], "light")
            kept = {e["unit"]: e for e in synckeep.entries()}
            self.assertEqual((kept[item_uid]["why"], kept[item_uid]["partner"]), ("incoming", B.id))
            with open(os.path.join(synckeep.kept_dir(), kept[item_uid]["id"], "files", "items",
                                   "%s.json" % item["id"]), "rb") as fh:
                self.assertEqual(fh.read(), old)
            self.assertEqual(kept["setting:parseh_theme"]["value"]["v"], "dark")
            # the version taken is the partner's, not a change made here
            self.assertEqual(synclog.get(item_uid)["vv"], {A.id: 1, B.id: 1})   # A's count not moved
        self.assertEqual(units(w, A), units(w, B))

    def test_a_file_both_have_is_not_sent(self):
        A, B, w = self.A, self.B, self.w
        data = os.urandom(300 * 1024)
        X.CHUNK = 64 * 1024
        c = clip(A, "big.mp3", data)
        video(B, "v9", media=data)                 # the same bytes, in another unit, on B
        got = self.pull(B, A)
        self.assertEqual(got["taken"], [c])
        self.assertEqual(got["blobs"]["local"], 1)                   # the media, copied here
        self.assertEqual(got["blobs"]["bytes"], len(B.read("clips/big.mp3.json")))   # only the JSON came
        self.assertEqual(B.read("clips/big.mp3"), data)
        # the same book on both from one zip: agreement, nothing moves
        for inst in (A, B):
            inst.w("books/persian/b/book.json", '{"t": 1}')
            inst.w("books/persian/b/ch.tex", "same")
        got = self.pull(B, A)
        self.assertIn("book:persian/b", got["adopted"])
        self.assertEqual(got["blobs"]["chunks"], 0)
        self.assertIn("book:persian/b", self.pull(A, B)["adopted"])   # and A takes the merged vector
        self.assertEqual(row(w, B, "book:persian/b")["vv"], row(w, A, "book:persian/b")["vv"])
        self.assertEqual(self.pull(B, A)["adopted"], [])

    # ---------------------------------------------------------------- cut off
    def test_cut_off_halfway_then_resumed(self):
        A, B, w = self.A, self.B, self.w
        X.CHUNK = 64 * 1024
        media = os.urandom(16 * 64 * 1024)
        vid = video(A, "v2", media=media)
        import hashlib
        sha = hashlib.sha256(media).hexdigest()
        n = {"blobs": 0, "cut": True}

        def fail(caller, target, op, payload):
            if op == "sync.blob" and payload["sha"] == sha:
                n["blobs"] += 1
                if n["cut"] and n["blobs"] > 5:
                    raise syncfake.Unreachable("the link dropped")
        w.fail = fail
        got = self.pull(B, A)
        self.assertFalse(got["complete"])
        self.assertIn("Unreachable", got["error"])
        self.assertFalse(os.path.exists(B.p("youtube/videos/persian/v2")))   # nothing half-written
        self.assertIsNone(row(w, B, vid))
        with w.on(B):
            part = [f for f in os.listdir(os.path.join(synclog.home(), "incoming")) if f.endswith(".part")]
            self.assertEqual(len(part), 1)
            self.assertEqual(os.path.getsize(os.path.join(synclog.home(), "incoming", part[0])),
                             5 * 64 * 1024)
        n.update(cut=False, blobs=0)
        got = self.pull(B, A)
        self.assertTrue(got["complete"], got)
        self.assertEqual(got["taken"], [vid])
        self.assertEqual(n["blobs"], 11)                              # from where it stopped
        self.assertEqual(B.read("youtube/videos/persian/v2/media.mp4"), media)
        self.assertEqual(units(w, A), units(w, B))
        with w.on(B):
            self.assertEqual(os.listdir(os.path.join(synclog.home(), "incoming")), [])

    def test_a_write_cut_off_by_a_crash_is_finished(self):
        A, B, w = self.A, self.B, self.w
        vid = video(A, "v3")
        video(B, "v3", text="old\n")
        self.pull(B, A)                       # both sides changed: held; make B's the old version of A's
        with w.on(B):
            X.clear_pending(vid)
        # start again cleanly: B gets A's v3, then A changes it
        import shutil
        shutil.rmtree(B.p("youtube/videos/persian/v3"))
        with w.on(B):
            synclog.scan()
            synclog.forget(vid)
        self.pull(B, A)
        A.w("youtube/videos/persian/v3/transcript.txt", "new\nlines\n")
        A.w("youtube/videos/persian/v3/video.json", '{"title": "V2"}')

        class Crash(Exception):
            pass
        real, n = X._place, {"k": 0}

        def place(src, dst):
            n["k"] += 1
            if n["k"] == 2:
                raise Crash()
            return real(src, dst)
        X._place = place
        try:
            with self.assertRaises(Crash):
                self.pull(B, A)
        finally:
            X._place = real
        with w.on(B):
            self.assertTrue(os.path.isfile(os.path.join(synclog.home(), "applying.json")))
        got = self.pull(B, A)                  # recover() first: the write finished, as A's version
        self.assertTrue(got["complete"])
        self.assertEqual(B.read("youtube/videos/persian/v3/transcript.txt"), b"new\nlines\n")
        self.assertEqual(B.read("youtube/videos/persian/v3/video.json"), b'{"title": "V2"}')
        self.assertEqual(row(w, B, vid)["vv"], row(w, A, vid)["vv"])
        self.assertNotIn(B.id, row(w, B, vid)["vv"])

    # ---------------------------------------------------------------- waits
    def test_a_unit_an_editor_holds_waits(self):
        A, B, w = self.A, self.B, self.w
        c = clip(A, "e.mp3", b"one")
        self.pull(B, A)
        clip(A, "e.mp3", b"two")
        tok = synclock.open_editor(c, "studio")
        got = self.pull(B, A)
        self.assertEqual(got["waiting"], [c])
        self.assertEqual(B.read("clips/e.mp3"), b"one")
        with w.on(B):
            self.assertEqual([(p["unit"], p["situation"]) for p in X.pending()], [(c, "editing")])
        synclock.close_editor(tok)
        got = self.pull(B, A)
        self.assertEqual(got["taken"], [c])
        self.assertEqual(B.read("clips/e.mp3"), b"two")
        with w.on(B):
            self.assertEqual(X.pending(), [])

    def test_both_sides_and_deletions_wait_untouched(self):
        A, B, w = self.A, self.B, self.w
        vid = video(A, "v4", text="base\n")
        c = clip(A, "d.mp3", b"keep")
        with w.on(A):
            prefs.set_settings({"bk_rate": {"v": 1.0, "at": time.time()}}, by="t")
        self.both(A, B)
        A.w("youtube/videos/persian/v4/transcript.txt", "A's\n")
        B.w("youtube/videos/persian/v4/transcript.txt", "B's\n")
        with w.on(A):
            clips.delete("d.mp3")
            prefs.set_settings({"bk_rate": {"v": 1.5, "at": time.time() + 1}}, by="t")
        with w.on(B):
            prefs.set_settings({"bk_rate": {"v": 0.5, "at": time.time() + 2}}, by="t")
        got = self.both(B, A)
        self.assertEqual(sorted(got["held"]), sorted([vid, c, "setting:bk_rate"]))
        self.assertEqual(got["taken"], [])
        self.assertEqual(A.read("youtube/videos/persian/v4/transcript.txt"), b"A's\n")
        self.assertEqual(B.read("youtube/videos/persian/v4/transcript.txt"), b"B's\n")
        self.assertEqual(B.read("clips/d.mp3"), b"keep")
        with w.on(B):
            self.assertEqual(sorted((p["unit"], p["situation"]) for p in X.pending()),
                             sorted([(vid, "both"), (c, "deletion"), ("setting:bk_rate", "setting")]))
            self.assertEqual(float(prefs.settings()["bk_rate"]["v"]), 0.5)
        with w.on(A):
            self.assertEqual(sorted(p["unit"] for p in X.pending()), sorted([vid, "setting:bk_rate"]))
            self.assertEqual(float(prefs.settings()["bk_rate"]["v"]), 1.5)
        # a rule in RULES settles a case: take the partner's
        seen = []

        def take_theirs(case):
            seen.append((case.unit, case.situation, sorted(case.staged())))
            return "taken" if case.take() else X.HELD
        was = X.RULES["both"]
        X.RULES["both"] = take_theirs
        try:
            got = self.pull(B, A)
        finally:
            X.RULES["both"] = was
        self.assertEqual(seen, [(vid, "both", ["annotations.json", "media.mp4", "transcript.txt",
                                               "video.json"])])
        self.assertEqual(B.read("youtube/videos/persian/v4/transcript.txt"), b"A's\n")
        with w.on(B):
            self.assertEqual(sorted(p["unit"] for p in X.pending()), sorted([c, "setting:bk_rate"]))
            self.assertIn(vid, [e["unit"] for e in synckeep.entries()])

    # ---------------------------------------------------------------- holding
    def test_left_out_is_elsewhere_and_fetched(self):
        A, B, w = self.A, self.B, self.w
        for slug in ("b1", "b2"):
            A.w("books/persian/%s/book.json" % slug, '{"t": "%s"}' % slug)
            A.w("books/persian/%s/ch.tex" % slug, "text " + slug)
        A.w("books/persian/b1/markdown/fa/n1/source.md", "a note")
        A.w("books/turkish/t1/book.json", "{}")
        with w.on(B):
            X.set_holding(languages=["turkish"], units=["book:persian/b1"])
        got = self.pull(B, A)
        self.assertEqual(got["taken"], ["book:persian/b2"])
        self.assertFalse(os.path.exists(B.p("books/persian/b1")))
        with w.on(B):
            self.assertEqual(sorted((e["unit"], e["partners"][0]) for e in X.elsewhere()),
                             sorted([("book:persian/b1", A.id), ("book:turkish/t1", A.id),
                                     ("note:book/persian/b1/fa/n1", A.id)]))
            got = X.fetch("book:persian/b1", A.id)
            self.assertEqual(sorted(got["taken"]), ["book:persian/b1", "note:book/persian/b1/fa/n1"])
            self.assertEqual(sorted(e["unit"] for e in X.elsewhere()), ["book:turkish/t1"])
            self.assertTrue(X.holds("book:persian/b1"))
            self.assertFalse(X.holds("book:turkish/t1"))
        self.assertEqual(B.read("books/persian/b1/markdown/fa/n1/source.md"), b"a note")
        A.w("books/persian/b1/ch.tex", "changed")                      # fetched: held from then on
        self.assertEqual(self.pull(B, A)["taken"], ["book:persian/b1"])

    # ---------------------------------------------------------------- when it runs
    def test_never_two_at_once(self):
        lock = X._plock(self.A.id)
        lock.acquire()
        try:
            got = X.sync_from(self.A.id, wait=False)
        finally:
            lock.release()
        self.assertTrue(got["busy"])

    def test_scheduler(self):
        A, B, w = self.A, self.B, self.w
        runs, live, most = [], {"n": 0}, {"n": 0}
        guard = threading.Lock()

        def fake_sync_with(pid, why=""):
            with guard:
                live["n"] += 1
                most["n"] = max(most["n"], live["n"])
                runs.append((pid, why))
            time.sleep(0.15)
            with guard:
                live["n"] -= 1
        real = X.sync_with
        X.sync_with = fake_sync_with
        try:
            with w.on(B):
                X.start(tick=0.02, change_debounce=0.1)

                def wait_for(cond, t=3.0):
                    end = time.time() + t
                    while time.time() < end and not cond():
                        time.sleep(0.01)
                    return cond()
                self.assertTrue(wait_for(lambda: (A.id, "start") in runs))
                for _ in range(5):                                   # sync now, many times: one at a time
                    X.request(A.id, "sync now")
                    time.sleep(0.01)
                prefs.set_settings({"bk_gap": {"v": 1, "at": time.time()}}, by="t")
                synclog.flush()                                      # what synclog's own thread does
                self.assertTrue(wait_for(lambda: (A.id, "a change here") in runs))
                w.reachable[A.id] = False
                time.sleep(0.1)
                w.reachable[A.id] = True
                self.assertTrue(wait_for(lambda: (A.id, "reachable") in runs))
                self.assertTrue(X.status()["running"])
                X.stop()
                self.assertFalse(X.status()["running"])
        finally:
            X.sync_with = real
        self.assertEqual(most["n"], 1)
        self.assertIn((A.id, "sync now"), runs)


if __name__ == "__main__":
    unittest.main()
