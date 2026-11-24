# SPDX-License-Identifier: GPL-3.0-or-later
"""The rules of sync (lib/syncrules.py, lane C; docs/sync.md).

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_rules.py

Two temporary installs (tests/syncfake.py) in one process, written through the
real modules, synced through the real exchange with the rules installed:

  * never asked: a personal setting and a reading place (the most recent wins),
    an exercise's progress (the newest latest answer wins, different exercises
    combine), the Anki store's seen.json (the union), a clip edited on both;
  * a document changed on both -> one question on both computers; answered on
    either, both ways ("mine" / "theirs") -> the same everywhere, the question
    gone on both, the diff file on both, the discarded version kept for a day;
  * deletions asked: untouched on one side (several from one sync are one
    question), both answers; edited on one side, both answers;
  * an answer given while the partner is away waits in the outbox and is
    settled at the next sync, with no second question;
  * make this computer identical: the summary, then the run; the partner unchanged;
  * out of date: a build made before its source came through sync, cleared by
    a newer build; kept() / put_back(), diffs() / diff_path() / delete_diff().
"""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from syncfake import World      # noqa: E402
import clips                    # noqa: E402
import decks                    # noqa: E402
import prefs                    # noqa: E402
import store                    # noqa: E402
import syncexchange as X        # noqa: E402
import synckeep                 # noqa: E402
import synclog                  # noqa: E402
import syncrules as R           # noqa: E402

FLASH = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\n:::"
DOC = "---\nlang: fa\ntitle: Doc\n---\n# Doc\n\nline one\nline two\n"


def clip(inst, name="c.mp3", data=b"sound", rec=None):
    with inst.world.on(inst):
        with open(os.path.join(clips.DIR, name), "wb") as fh:
            fh.write(data)
        clips._write_json(os.path.join(clips.DIR, name + ".json"), rec or {"lang": "fa"})
    return "clip:" + name


class Rules(unittest.TestCase):
    def setUp(self):
        self.w = World("A", "B").__enter__()
        self.A, self.B = self.w.A, self.w.B
        self._rules = dict(X.RULES)
        self._hooks = (list(X.ON_TAKEN), list(X.BEFORE_PULL), list(X.AFTER_PULL))
        R.install()

    def tearDown(self):
        X.RULES.clear()
        X.RULES.update(self._rules)
        X.ON_TAKEN[:], X.BEFORE_PULL[:], X.AFTER_PULL[:] = self._hooks
        R.close()
        self.w.__exit__(None, None, None)

    # -- helpers
    def both(self, a, b):
        with self.w.on(a):
            return X.sync_with(b.id)

    def units(self, inst, prefix=""):
        with self.w.on(inst):
            synclog.scan()
            return {r["unit"]: r["hash"] for r in synclog.rows(prefix, deleted=False)}

    def on(self, inst, fn, *a, **kw):
        with self.w.on(inst):
            return fn(*a, **kw)

    def doc_apart(self):
        """A document both have, then edited on A and on B while apart."""
        A, B = self.A, self.B
        with self.w.on(A):
            meta = store.create(DOC)
        uid = next(iter(self.units(A, "doc:")))
        self.both(A, B)
        rel = "markdown/library/" + uid[4:] + "/source.md"
        self.assertEqual(A.read(rel), B.read(rel))
        A.w(rel, DOC.replace("line two", "line two, as A wrote it"))
        B.w(rel, DOC.replace("line one", "line one, as B wrote it"))
        return uid, rel, meta

    # ---------------------------------------------------------------- never asked
    def test_setting_and_place_most_recent_wins(self):
        A, B, w = self.A, self.B, self.w
        t = time.time()
        with w.on(A):
            prefs.set_settings({"bk_rate": {"v": 1.0, "at": t}}, by="t")
            prefs.set_place("/books/x/y/reader/", 3, at=t)
        self.both(A, B)
        with w.on(A):
            prefs.set_settings({"bk_rate": {"v": 1.5, "at": t + 10}}, by="t")
            prefs.set_place("/books/x/y/reader/", 7, at=t + 20)
        with w.on(B):
            prefs.set_settings({"bk_rate": {"v": 0.5, "at": t + 20}}, by="t")   # newer
            prefs.set_place("/books/x/y/reader/", 5, at=t + 10)                # older
        got = self.both(A, B)
        self.assertEqual(got["held"], [], got)
        self.both(B, A)
        for inst in (A, B):
            with w.on(inst):
                self.assertEqual(float(prefs.settings()["bk_rate"]["v"]), 0.5, inst.name)
                self.assertEqual(prefs.place("/books/x/y/reader/")["i"], 7, inst.name)
                self.assertEqual(R.questions(), [])
                self.assertEqual(X.pending(), [])
        self.assertEqual(self.units(A), self.units(B))

    def test_progress_newest_latest_answer_and_combine(self):
        A, B, w = self.A, self.B, self.w
        with w.on(A):
            deck = decks.create_deck("Words", "fa")
            i1 = decks.add_item(deck["folder"], deck["slug"], FLASH)
            i2 = decks.add_item(deck["folder"], deck["slug"], FLASH.replace("cat", "dog"))
        self.both(A, B)
        base = "exercises/%s/%s/schedule/" % (deck["folder"], deck["slug"])

        def sched(when, rating):
            return json.dumps({"state": {"reps": 1, "last_review": when},
                               "history": [{"at": when, "rating": rating}]})
        A.w(base + i1["id"] + ".json", sched("2026-11-24T10:00:00+00:00", "good"))
        B.w(base + i1["id"] + ".json", sched("2026-11-24T11:00:00+00:00", "again"))   # newer
        B.w(base + i2["id"] + ".json", sched("2026-11-24T09:00:00+00:00", "easy"))    # only on B
        got = self.both(A, B)
        self.assertEqual(got["held"], [], got)
        self.both(B, A)
        for inst in (A, B):
            self.assertIn(b"again", inst.read(base + i1["id"] + ".json"), inst.name)
            self.assertIn(b"easy", inst.read(base + i2["id"] + ".json"), inst.name)
        self.assertEqual(self.units(A), self.units(B))

    def test_additions_seen_union_and_clip_most_recent(self):
        A, B, w = self.A, self.B, self.w
        A.w("youtube/anki/seen.json", json.dumps({"g1": "2026-11-01"}))
        c = clip(A, "k.mp3", b"k", {"lang": "fa"})
        self.both(A, B)
        A.w("youtube/anki/seen.json", json.dumps({"g1": "2026-11-01", "gA": "2026-11-20"}))
        B.w("youtube/anki/seen.json", json.dumps({"g1": "2026-11-01", "gB": "2026-11-21"}))
        with w.on(A):
            clips._write_json(os.path.join(clips.DIR, "k.mp3.json"), {"lang": "fa", "note": "A"})
        time.sleep(1.1)
        with w.on(B):
            clips._write_json(os.path.join(clips.DIR, "k.mp3.json"), {"lang": "fa", "note": "B"})
        got = self.both(A, B)
        self.assertEqual(got["held"], [], got)
        self.both(B, A)
        for inst in (A, B):
            seen = json.loads(inst.read("youtube/anki/seen.json"))
            self.assertEqual(sorted(seen), ["g1", "gA", "gB"], inst.name)
            self.assertEqual(json.loads(inst.read("clips/k.mp3.json"))["note"], "B", inst.name)
        self.assertEqual(self.units(A), self.units(B))
        self.assertIn(c, self.units(A))

    # ---------------------------------------------------------------- the choice
    def _choice(self, answer_on, choice, winner):
        A, B, w = self.A, self.B, self.w
        uid, rel, _ = self.doc_apart()
        got = self.both(A, B)
        self.assertIn(uid, got["held"])
        qa, qb = self.on(A, R.questions), self.on(B, R.questions)
        self.assertEqual(len(qa), 1, qa)
        self.assertEqual(len(qb), 1, qb)
        self.assertEqual(qa[0]["id"], qb[0]["id"])
        self.assertEqual(qa[0]["kind"], "choice")
        self.assertEqual(qa[0]["units"][0]["unit"], uid)
        self.assertEqual(self.on(A, R.question_for, uid)["id"], qa[0]["id"])
        self.assertIn("as B wrote it", qa[0]["discard_preview"]["theirs"])
        self.assertIn("as A wrote it", qa[0]["discard_preview"]["mine"])
        self.assertEqual(qa[0]["partner_name"], "B")
        # nothing moved while it waits
        self.assertIn(b"as A wrote it", A.read(rel))
        self.assertIn(b"as B wrote it", B.read(rel))
        asker = A if answer_on == "A" else B
        out = self.on(asker, R.answer, qa[0]["id"] if asker is A else qb[0]["id"], choice)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["diff_id"], out)
        self.both(B, A)
        self.both(A, B)
        want = b"as A wrote it" if winner == "A" else b"as B wrote it"
        other = b"as B wrote it" if winner == "A" else b"as A wrote it"
        for inst in (A, B):
            self.assertIn(want, inst.read(rel), inst.name)
            self.assertNotIn(other, inst.read(rel), inst.name)
            with w.on(inst):
                self.assertEqual(R.questions(), [], inst.name)
                self.assertEqual(X.pending(), [], inst.name)
                ds = R.diffs()
                self.assertEqual(len(ds), 1, (inst.name, ds))
                with open(R.diff_path(ds[0]["id"]), encoding="utf-8") as fh:
                    text = fh.read()
                self.assertIn(other.decode(), text)
                self.assertIn("@@", text)                     # a unified diff
        loser = B if winner == "A" else A
        with w.on(loser):
            kept = [k for k in R.kept() if k["unit"] == uid]
            self.assertTrue(kept, "the discarded version is kept for a day on the loser")
        self.assertEqual(self.units(A), self.units(B))

    def test_choice_mine_answered_on_A(self):
        self._choice("A", "mine", "A")

    def test_choice_theirs_answered_on_A(self):
        self._choice("A", "theirs", "B")

    def test_choice_mine_answered_on_B(self):
        self._choice("B", "mine", "B")

    def test_answer_while_away_waits_then_settles(self):
        A, B, w = self.A, self.B, self.w
        uid, rel, _ = self.doc_apart()
        self.both(A, B)
        qid = self.on(B, R.questions)[0]["id"]
        w.reachable[A.id] = False
        out = self.on(B, R.answer, qid, "theirs")      # A's version, while A is away
        self.assertTrue(out["ok"], out)
        self.assertIn(uid, out.get("waiting", {}))
        self.assertEqual(self.on(B, R.questions), [])
        self.assertEqual(len(self.on(A, R.questions)), 1)       # A has not heard yet
        w.reachable[A.id] = True
        got = self.both(B, A)                                    # the outbox first, then the pull
        self.assertEqual(got["held"], [], got)
        self.both(A, B)
        for inst in (A, B):
            self.assertIn(b"as A wrote it", inst.read(rel), inst.name)
            self.assertEqual(self.on(inst, R.questions), [], inst.name)
        self.assertEqual(self.units(A), self.units(B))

    # ---------------------------------------------------------------- deletions
    def test_deletions_untouched_grouped_both_answers(self):
        A, B, w = self.A, self.B, self.w
        c1, c2 = clip(A, "a.mp3", b"1"), clip(A, "b.mp3", b"2")
        self.both(A, B)
        with w.on(A):
            clips.delete("a.mp3")
            clips.delete("b.mp3")
        got = self.both(B, A)                                    # B meets the deletions
        self.assertEqual(sorted(got["held"]), sorted([c1, c2]))
        qb, qa = self.on(B, R.questions), self.on(A, R.questions)
        self.assertEqual(len(qb), 1, qb)                         # one question with the list
        self.assertEqual(qb[0]["kind"], "deletion")
        self.assertEqual(sorted(u["unit"] for u in qb[0]["units"]), sorted([c1, c2]))
        self.assertEqual(len(qa), 1, qa)                         # and on the computer that deleted
        self.assertEqual(sorted(u["unit"] for u in qa[0]["units"]), sorted([c1, c2]))
        # "go through them": restore one, on B
        out = self.on(B, R.answer, qb[0]["id"], "restore", c1)
        self.assertTrue(out["ok"], out)
        self.both(A, B)
        self.both(B, A)
        self.assertEqual(A.read("clips/a.mp3"), b"1")                     # restored on A
        self.assertEqual(len(self.on(A, R.questions)[0]["units"]), 1)     # b.mp3 still asked
        # delete the rest, answered on A (the computer that deleted)
        qa = self.on(A, R.questions)
        out = self.on(A, R.answer, qa[0]["id"], "delete")
        self.assertTrue(out["ok"], out)
        self.both(B, A)
        self.both(A, B)
        self.assertFalse(os.path.exists(B.p("clips/b.mp3")))
        self.assertTrue(os.path.exists(B.p("clips/a.mp3")))
        for inst in (A, B):
            self.assertEqual(self.on(inst, R.questions), [], inst.name)
            self.assertEqual(self.on(inst, X.pending), [], inst.name)
        with w.on(B):
            self.assertIn(c2, [k["unit"] for k in R.kept() if k["why"] == "deletion"])
        self.assertEqual(self.units(A), self.units(B))
        # the tray emptied on A: one question, "delete them all" on B
        c3, c4 = clip(A, "c.mp3", b"3"), clip(A, "d.mp3", b"4")
        self.both(A, B)
        with w.on(A):
            clips.delete("a.mp3")
            clips.delete("c.mp3")
            clips.delete("d.mp3")
        self.both(B, A)
        qb = self.on(B, R.questions)
        self.assertEqual([len(q["units"]) for q in qb], [3])
        self.assertTrue(self.on(B, R.answer, qb[0]["id"], "delete")["ok"])
        self.both(B, A)
        self.both(A, B)
        for inst in (A, B):
            self.assertEqual(sorted(os.listdir(inst.p("clips"))), [], inst.name)
            self.assertEqual(self.on(inst, R.questions), [], inst.name)
        self.assertEqual(self.units(A), self.units(B))
        self.assertIn(c3, [k["unit"] for k in self.on(B, R.kept) if k["why"] == "deletion"])
        self.assertIn(c4, [k["unit"] for k in self.on(B, R.kept) if k["why"] == "deletion"])

    def test_deleted_there_edited_here(self):
        A, B, w = self.A, self.B, self.w
        for choice, survives in (("send-edited", True), ("delete", False)):
            with self.subTest(choice=choice):
                with w.on(A):
                    meta = store.create(DOC.replace("Doc", "Doc " + choice))
                uid = [u for u in self.units(A, "doc:") if u.endswith(meta["id"])][0]
                rel = "markdown/library/" + uid[4:] + "/source.md"
                self.both(A, B)
                with w.on(A):
                    store.delete(meta["id"])
                B.w(rel, DOC + "\nedited on B\n")
                self.both(A, B)
                qa, qb = self.on(A, R.questions), self.on(B, R.questions)
                self.assertEqual([q["kind"] for q in qa], ["deletion-edited"])
                self.assertEqual([q["kind"] for q in qb], ["deletion-edited"])
                out = self.on(A, R.answer, qa[0]["id"], choice)
                self.assertTrue(out["ok"], out)
                self.both(B, A)
                self.both(A, B)
                for inst in (A, B):
                    self.assertEqual(os.path.exists(inst.p(rel)), survives, inst.name)
                    if survives:
                        self.assertIn(b"edited on B", inst.read(rel))
                    self.assertEqual(self.on(inst, R.questions), [], inst.name)
                self.assertEqual(self.units(A), self.units(B))

    # ---------------------------------------------------------------- make identical
    def test_make_identical(self):
        A, B, w = self.A, self.B, self.w
        uid, rel, _ = self.doc_apart()                  # a question will wait
        self.both(A, B)
        c = clip(A, "only-a.mp3", b"mine")              # only here (A)
        with w.on(B):
            store.create(DOC.replace("Doc", "Only on B"))
        b_before = self.units(B)
        b_files = B.read(rel)
        s = self.on(A, R.identical_summary, B.id)
        self.assertEqual((s["replace"], s["add"], s["delete"]), (1, 1, 1), s)
        self.assertEqual(sorted(x["unit"] for x in s["lost"]), sorted([uid, c]))
        self.assertEqual(s["questions"], 1)
        self.assertEqual(s["jobs"], [])
        out = self.on(A, R.make_identical, B.id)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["diff_id"])
        self.assertEqual(A.read(rel), b_files)
        self.assertFalse(os.path.exists(A.p("clips/only-a.mp3")))
        self.assertEqual(self.units(A), b_before)
        self.assertEqual(self.units(B), b_before)              # the partner unchanged
        self.assertEqual(B.read(rel), b_files)
        with w.on(A):
            self.assertEqual(R.questions(), [])
            with open(R.diff_path(out["diff_id"]), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("as A wrote it", text)
            self.assertIn(c, text)
            self.assertEqual({k["why"] for k in R.kept()}, {"identical"})
        self.assertEqual(self.on(B, R.questions), [])
        # nothing comes back the other way afterwards
        got = self.both(A, B)
        self.assertEqual((got["held"], got["taken"]), ([], []), got)
        self.assertEqual(self.units(B), b_before)

    # ---------------------------------------------------------------- out of date, kept, diffs
    def test_out_of_date_kept_and_diffs(self):
        A, B, w = self.A, self.B, self.w
        A.w("books/english/three/main.tex", "\\chapter{One}\n")
        A.w("books/english/three/book.json", '{"title": "Three"}')
        self.both(A, B)
        uid = "book:english/three"
        A.w("books/english/three/main.pdf", b"%PDF built")
        old = time.time() - 60
        os.utime(A.p("books/english/three/main.pdf"), (old, old))
        B.w("books/english/three/main.tex", "\\chapter{One, changed on B}\n")
        self.both(A, B)
        with w.on(A):
            self.assertTrue(R.is_out_of_date(uid))
            self.assertEqual([(o["unit"], o["title"], o["what"]) for o in R.out_of_date()],
                             [(uid, "Three", ["the PDF"])])
        A.w("books/english/three/main.pdf", b"%PDF rebuilt")      # a newer build clears it
        with w.on(A):
            self.assertFalse(R.is_out_of_date(uid))
            self.assertEqual(R.out_of_date(), [])
            # the old main.tex was kept for a day: put it back
            k = [x for x in R.kept() if x["unit"] == uid]
            self.assertEqual(k[0]["title"], "Three")
            self.assertTrue(R.put_back(k[0]["id"])["ok"])
        self.assertEqual(A.read("books/english/three/main.tex"), b"\\chapter{One}\n")
        with w.on(A):
            d = R._write_diff(uid, "--- a\n+++ b\n", "Three")
            self.assertEqual([x["id"] for x in R.diffs()], [d])
            self.assertTrue(os.path.isfile(R.diff_path(d)))
            self.assertTrue(R.delete_diff(d)["ok"])
            self.assertEqual(R.diffs(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
