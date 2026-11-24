#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Two REAL installs, paired over real TLS, syncing through the real exchange.

Lane A (pairing, transport) was tested with a dummy op and lane B (the
exchange) through an in-process fake of the transport.  This is the two
together, with nothing faked: each install is a serve.py process in its own
temporary tree (tests/sync_harness.py), they pair through the Settings ->
Devices routes, and a change made through an ordinary page route on one --
a studio document, the theme -- must arrive on the other by itself: the
change's debounce, the pull, the nudge that makes the partner pull back.
And back the other way: an edit on B reaches A, A's old version kept for a day.

The rules (lane C, lib/syncrules.py), with the two computers kept APART by
freezing one process (SIGSTOP: a computer that answers nothing, as a
partner that went to sleep does) while the other is edited, then the other
way round, then both thawed:
  * a document edited on both -> a question on both -> answered on one ->
    the same everywhere, the question gone on both, a diff file on both;
  * a deletion asked, answered "delete" on the computer that did not delete,
    and another answered "restore" on the computer that deleted;
  * make this computer identical: the summary, then A takes B's state.
"""
import glob
import http.client
import json
import os
import shutil
import signal
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_sync_pairing import Install  # noqa: E402

WAIT = 150         # seconds for a change to travel: a 5 s debounce, a pull, a nudge


def ask(inst, method, route, body=None):
    c = http.client.HTTPConnection("127.0.0.1", inst.port, timeout=30)
    try:
        origin = "http://localhost:%d" % inst.port
        c.request(method, route, body=json.dumps(body) if body is not None else None,
                  headers={"Content-Type": "application/json", "Origin": origin,
                           "Referer": origin + "/", "Host": "localhost:%d" % inst.port})
        r = c.getresponse()
        raw = r.read()
        try:
            return r.status, json.loads(raw or b"{}")
        except ValueError:
            return r.status, raw[:200]
    finally:
        c.close()


def sources(inst):
    return sorted(glob.glob(os.path.join(inst.tree, "library", "*", "*", "source.md")))


def until(what, test):
    end = time.time() + WAIT
    while time.time() < end:
        got = test()
        if got:
            return got
        time.sleep(0.5)
    raise AssertionError("waited %d s: %s" % (WAIT, what))


def rules(inst, do, **kw):
    st, out = ask(inst, "POST", "/settings/api/devices/rules", dict(kw, do=do))
    assert st == 200, (st, out)
    return out


def text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def make_doc(inst, md):
    before = set(sources(inst))
    st, out = ask(inst, "POST", "/studio/api/docs", {"markdown": md})
    assert st in (200, 201), out
    made = sorted(set(sources(inst)) - before)
    assert len(made) == 1, made
    return made[0]


def edit_doc(inst, path, md):
    doc_id = os.path.basename(os.path.dirname(path))
    st, out = ask(inst, "PUT", "/studio/api/docs/%s" % doc_id, {"markdown": md})
    if st == 405:
        st, out = ask(inst, "POST", "/studio/api/docs/%s" % doc_id, {"markdown": md})
    assert st == 200, out


def unit_of(inst, path):
    rel = os.path.relpath(os.path.dirname(path), os.path.join(inst.tree, "library"))
    return "doc:" + rel.replace(os.sep, "/")


def freeze(inst):
    os.kill(inst.proc.pid, signal.SIGSTOP)


def thaw(inst):
    os.kill(inst.proc.pid, signal.SIGCONT)


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-e2e-")
        cls.A = Install(cls.base, "A")
        cls.B = Install(cls.base, "B")
        try:
            cls.A.wait()
            cls.B.wait()
            st, offer = cls.A.dev("pair-start")
            assert st == 200, offer
            st, out = cls.B.dev("pair-enter", {"code": offer["said"], "address": "127.0.0.1:%d" % cls.A.port,
                                               "fingerprint": offer["fingerprint"]})
            assert st == 200, out
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for i in (getattr(cls, "A", None), getattr(cls, "B", None)):
            if i:
                i.stop()
        if os.environ.get("KEEP_SYNC_E2E"):
            print("trees kept in", cls.base)
        else:
            shutil.rmtree(cls.base, ignore_errors=True)

    def test_1_a_document_made_on_A_arrives_on_B_and_an_edit_on_B_comes_back(self):
        md = "---\ntitle: Sync by itself\nlanguage: italian\n---\n\n# Sync by itself\n\nUna frase.\n"
        st, out = ask(self.A, "POST", "/studio/api/docs", {"markdown": md})
        self.assertIn(st, (200, 201), out)
        made = sources(self.A)
        self.assertEqual(len(made), 1, made)
        rel = os.path.relpath(made[0], self.A.tree)
        there = os.path.join(self.B.tree, rel)
        until("the document on B", lambda: os.path.isfile(there))
        with open(there, encoding="utf-8") as f, open(made[0], encoding="utf-8") as g:
            self.assertEqual(f.read(), g.read())
        # an edit on B, through B's own route, comes back to A
        doc_id = os.path.basename(os.path.dirname(there))
        edited = md.replace("Una frase.", "Una frase, cambiata su B.")
        st, out = ask(self.B, "PUT", "/studio/api/docs/%s" % doc_id, {"markdown": edited})
        if st == 405:
            st, out = ask(self.B, "POST", "/studio/api/docs/%s" % doc_id, {"markdown": edited})
        self.assertEqual(st, 200, out)

        def back():
            with open(made[0], encoding="utf-8") as f:
                return "cambiata su B" in f.read()
        until("B's edit on A", back)
        kept = glob.glob(os.path.join(self.A.tree, "config", "sync", "kept", "**"), recursive=True)
        self.assertTrue([k for k in kept if os.path.isfile(k)], "A's old version is kept for a day")

    def test_2_a_setting_changed_on_A_arrives_on_B(self):
        st, out = ask(self.A, "POST", "/__prefs", {"settings": {"parseh_theme": {"v": "dark"}}, "by": "e2e"})
        self.assertEqual(st, 200, out)

        def theme():
            try:
                with open(os.path.join(self.B.tree, "config", "prefs.json"), encoding="utf-8") as f:
                    return json.load(f).get("settings", {}).get("parseh_theme", {}).get("v") == "dark"
            except (OSError, ValueError):
                return False
        until("the theme on B", theme)


    # ---------------------------------------------------------------- the rules (lane C)
    def apart(self, path_a, md_a, path_b, md_b):
        """Edit on A while B is frozen, then on B while A is frozen; both thawed."""
        freeze(self.B)
        try:
            edit_doc(self.A, path_a, md_a)
            time.sleep(4)                       # A's change log has it (2 s after the write)
            freeze(self.A)
            try:
                thaw(self.B)
                edit_doc(self.B, path_b, md_b)
                time.sleep(4)
            finally:
                thaw(self.A)
        finally:
            thaw(self.B)

    def shared_doc(self, title):
        md = "---\ntitle: %s\nlanguage: italian\n---\n\n# %s\n\nUna.\nDue.\n" % (title, title)
        pa = make_doc(self.A, md)
        pb = os.path.join(self.B.tree, os.path.relpath(pa, self.A.tree))
        until("%s on B" % title, lambda: text(pb) == text(pa))
        return md, pa, pb

    def test_3_edited_on_both_while_apart_asked_on_both_answered_on_one(self):
        md, pa, pb = self.shared_doc("Both sides")
        self.apart(pa, md.replace("Una.", "Una, scritta su A."), pb, md.replace("Due.", "Due, scritta su B."))
        uid = unit_of(self.A, pa)

        def asked(inst):
            return [q for q in rules(inst, "questions")["questions"] if q["units"][0]["unit"] == uid]
        qa = until("the question on A", lambda: asked(self.A))
        qb = until("the question on B", lambda: asked(self.B))
        self.assertEqual(qa[0]["id"], qb[0]["id"])
        self.assertEqual(qa[0]["kind"], "choice")
        self.assertIn("scritta su B", qa[0]["discard_preview"]["theirs"])
        self.assertEqual(rules(self.B, "question_for", unit=uid)["question"]["id"], qb[0]["id"])
        # nothing moved while it waits
        self.assertIn("scritta su A", text(pa))
        self.assertIn("scritta su B", text(pb))
        out = rules(self.B, "answer", id=qb[0]["id"], choice="theirs")     # B keeps A's
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["diff_id"], out)
        until("A's version on B", lambda: "scritta su A" in (text(pb) or ""))
        until("the question gone on A", lambda: not asked(self.A))
        self.assertFalse(asked(self.B))
        self.assertEqual(text(pa), text(pb))
        self.assertNotIn("scritta su B", text(pa))
        for inst in (self.A, self.B):
            ds = until("a diff file on %s" % os.path.basename(inst.tree),
                       lambda: [d for d in rules(inst, "diffs")["diffs"] if d["unit"] == uid])
            got = rules(inst, "diff", id=ds[0]["id"])["text"]
            self.assertIn("Due, scritta su B.", got)
        kept = rules(self.B, "kept")["kept"]
        self.assertIn(uid, [k["unit"] for k in kept if k["why"] == "choice"])
        time.sleep(8)                            # and it stays settled: no question comes back
        self.assertFalse(asked(self.A) or asked(self.B))
        self.assertEqual(text(pa), text(pb))

    def test_4_deletions_asked_and_answered_both_ways(self):
        md1, pa1, pb1 = self.shared_doc("Delete me")
        md2, pa2, pb2 = self.shared_doc("Bring me back")
        u1, u2 = unit_of(self.A, pa1), unit_of(self.A, pa2)
        for path in (pa1, pa2):
            st, out = ask(self.A, "DELETE", "/studio/api/docs/%s" % os.path.basename(os.path.dirname(path)))
            self.assertEqual(st, 200, out)

        def deletion(inst, uid):
            return [q for q in rules(inst, "questions")["questions"]
                    if q["kind"] == "deletion" and uid in [u["unit"] for u in q["units"]]]
        until("the deletions asked on B", lambda: deletion(self.B, u1) and deletion(self.B, u2))
        until("the deletions asked on A", lambda: deletion(self.A, u1) and deletion(self.A, u2))
        self.assertTrue(os.path.isfile(pb1) and os.path.isfile(pb2), "nothing deleted on B before the answer")
        # one sync may group both: answer each unit on its own ("go through them")
        out = rules(self.B, "answer", id=deletion(self.B, u1)[0]["id"], choice="delete", unit=u1)
        self.assertTrue(out["ok"], out)
        self.assertFalse(os.path.exists(pb1))
        qa = until("the other deletion still asked on A", lambda: deletion(self.A, u2))
        out = rules(self.A, "answer", id=qa[0]["id"], choice="restore", unit=u2)
        self.assertTrue(out["ok"], out)
        until("restored on A", lambda: text(pa2) is not None and text(pa2) == text(pb2))
        until("no deletion asked on B", lambda: not deletion(self.B, u1) and not deletion(self.B, u2))
        until("no deletion asked on A", lambda: not deletion(self.A, u1) and not deletion(self.A, u2))
        self.assertFalse(os.path.exists(pa1) or os.path.exists(pb1))
        self.assertIn(u1, [k["unit"] for k in rules(self.B, "kept")["kept"] if k["why"] == "deletion"])
        time.sleep(8)
        self.assertFalse(os.path.exists(pa1) or os.path.exists(pb1))
        self.assertEqual(text(pa2), text(pb2))

    def test_5_make_this_computer_identical(self):
        md, pa, pb = self.shared_doc("Identical")
        self.apart(pa, md.replace("Una.", "Una, persa su A."), pb, md.replace("Una.", "Una, da B."))
        uid = unit_of(self.A, pa)
        until("the question on A", lambda: rules(self.A, "question_for", unit=uid)["question"])
        st, state = self.A.dev("state")
        b_id = state["partners"][0]["id"]
        s = rules(self.A, "identical_summary", partner=b_id)
        self.assertGreaterEqual(s["replace"], 1, s)
        self.assertIn(uid, [x["unit"] for x in s["lost"]])
        self.assertGreaterEqual(s["questions"], 1)
        before_b = text(pb)
        out = rules(self.A, "make_identical", partner=b_id)
        self.assertTrue(out["ok"], out)
        self.assertEqual(text(pa), before_b)
        self.assertEqual(text(pb), before_b)                       # the partner unchanged
        self.assertIsNone(rules(self.A, "question_for", unit=uid)["question"])
        until("the question gone on B", lambda: not rules(self.B, "question_for", unit=uid)["question"])
        got = rules(self.A, "diff", id=out["diff_id"])["text"]
        self.assertIn("persa su A", got)
        self.assertIn(uid, [k["unit"] for k in rules(self.A, "kept")["kept"] if k["why"] == "identical"])
        time.sleep(8)
        self.assertEqual(text(pa), before_b)
        self.assertEqual(text(pb), before_b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
