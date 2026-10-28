# SPDX-License-Identifier: GPL-3.0-or-later
"""The LaTeX drawings of many documents, made in the background without opening one (a0.5.6, lib/latexbatch.py).

    python3 -m unittest tests/test_latex_batch.py

  * THE JOB, with the TeX run left out (latexdraw's peek and draw are the test's own, each draw waiting on a gate the
    test opens): the total is known before the first drawing is made and counts what two documents share once; `done`
    goes up by one each time a drawing is over, in the order they end, whatever their number; a drawing that fails, or
    raises, is over and kept as a problem, and never ends the batch; a stop begins no new drawing and keeps what was
    made; one batch at a time; nothing to make starts nothing; and no more of its own compiles stand in latexdraw's
    pool than it has workers, so that a page opened meanwhile never waits for the rest of the batch;
  * THE ENTRY every page's bar and the hub's panel are drawn from: kind `compile`, `unit` "items", `done` and `total`
    in drawings, the page's own token, finished entries kept for `activity.KEEP` seconds and no longer;
  * THE ROUTES of the studio, on a temporary library and with real documents: ids in, the distinct drawings not made
    yet counted, a refusal in words for what is not a list of ids, a second batch refused while one runs, the status
    and the stop; and serve.py's /__activity list carries the entry.
The real compile, 70 drawings, the bar on the page and the hub: tests/latex_batch.mjs.
"""
import json
import os
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
import activity     # noqa: E402
import latexbatch   # noqa: E402
import latexdraw    # noqa: E402


def until(fn, what, seconds=10.0):
    end = time.time() + seconds
    while time.time() < end:
        if fn():
            return
        time.sleep(0.01)
    raise AssertionError("timed out: " + what)


class Drawing:
    """latexdraw's peek and draw, as the job meets them: a drawing is `made` once drawn, and each draw waits on `gate`
    (one permit lets one drawing end), so a test sees the job between two drawings, never racing it"""

    def __init__(self, fail=(), boom=()):
        self.made, self.fail, self.boom = set(), set(fail), set(boom)
        self.gate = threading.Semaphore(0)
        self.started, self.alive, self.most = [], 0, 0
        self.lock = threading.Lock()

    def peek(self, tex, theme, inline=False):
        key = "k:%s:%s:%s" % (tex, theme or "", bool(inline))
        if key in self.made:
            return {"ok": True, "key": key}
        return {"ok": None, "key": key}

    def draw(self, tex, theme, inline=False, **kw):
        with self.lock:
            self.started.append(tex)
            self.alive += 1
            self.most = max(self.most, self.alive)
        try:
            self.gate.acquire()
            if tex in self.boom:
                raise RuntimeError("TeX fell over on " + tex)
            if tex in self.fail:
                return {"ok": False, "kind": "latex", "said": "%s is not a command LaTeX knows" % tex}
            self.made.add("k:%s:%s:%s" % (tex, theme or "", bool(inline)))
            return {"ok": True, "key": tex}
        finally:
            with self.lock:
                self.alive -= 1

    def let(self, n=1):
        for _ in range(n):
            self.gate.release()


class Base(unittest.TestCase):
    def setUp(self):
        self.drawing = Drawing()
        for target, fn in (("peek", self.drawing.peek), ("draw", self.drawing.draw)):
            patch = mock.patch.object(latexdraw, target, fn)
            patch.start()
            self.addCleanup(patch.stop)
        latexbatch.clear()
        self.addCleanup(self.finish)

    def finish(self):
        # a test that left drawings waiting must not leave the thread waiting for the next test
        self.drawing.let(500)
        until(lambda: not latexbatch.status()["running"], "the job is over", 10)
        latexbatch.clear()

    @staticmethod
    def wanted(n, doc="Dialoghi", inline=False, prefix="x"):
        return [("\\textbf{%s%d}" % (prefix, i), None, inline, doc) for i in range(n)]


class TheJob(Base):
    def test_the_total_is_known_before_the_first_drawing_and_counts_what_is_shared_once(self):
        wanted = self.wanted(5) + self.wanted(3, doc="Another")        # three drawings both documents show
        st = latexbatch.start(wanted, docs=2)
        self.assertEqual((True, 5, 0), (st["running"], st["total"], st["done"]), "five distinct, none made yet")
        self.assertEqual(0, st["already"])

    def test_it_counts_one_by_one_in_the_order_drawings_end_whatever_their_number(self):
        n = 60
        latexbatch.start(self.wanted(n), docs=1)
        seen = []
        for want in range(1, n + 1):
            self.drawing.let(1)
            until(lambda: latexbatch.status()["done"] >= want, "drawing %d is over" % want)
            seen.append(latexbatch.status()["done"])
        until(lambda: not latexbatch.status()["running"], "the job is over")
        st = latexbatch.status()
        self.assertEqual((n, n, n, 0, False), (st["total"], st["done"], st["made"], st["failed"], st["stopped"]))
        self.assertEqual(sorted(seen), seen, "never backwards")
        self.assertEqual(n, len(set(seen)), "every drawing moved the count: %d steps for %d drawings" % (len(set(seen)), n))

    def test_a_drawing_that_cannot_be_made_is_over_and_kept_as_a_problem_and_the_batch_goes_on(self):
        self.drawing.fail, self.drawing.boom = {"\\textbf{x1}"}, {"\\textbf{x3}"}
        latexbatch.start(self.wanted(5, doc="Bad one"), docs=1)
        self.drawing.let(5)
        until(lambda: not latexbatch.status()["running"], "the job is over")
        st = latexbatch.status()
        self.assertEqual((5, 5, 3, 2), (st["total"], st["done"], st["made"], st["failed"]))
        said = sorted(p["said"] for p in st["problems"])
        self.assertTrue(said[0].startswith("RuntimeError: TeX fell over") and "is not a command LaTeX knows" in said[1], said)
        self.assertEqual({"Bad one"}, {p["doc"] for p in st["problems"]})

    def test_a_stop_begins_no_new_drawing_and_keeps_what_was_made(self):
        window = latexbatch.workers()
        latexbatch.start(self.wanted(window * 4), docs=1)
        until(lambda: len(self.drawing.started) == window, "the first drawings are under way")
        self.drawing.let(1)
        until(lambda: latexbatch.status()["done"] == 1, "one is over")
        latexbatch.stop()
        self.drawing.let(window * 4)
        until(lambda: not latexbatch.status()["running"], "the job is over")
        st = latexbatch.status()
        self.assertTrue(st["stopped"])
        self.assertLess(st["done"], st["total"])
        self.assertEqual(st["done"], st["made"])
        self.assertLessEqual(len(self.drawing.started), window + 1, "the ones under way finished, no new one was begun")

    def test_one_batch_at_a_time_and_another_when_it_is_over(self):
        latexbatch.start(self.wanted(3), docs=1)
        with self.assertRaises(latexbatch.Busy):
            latexbatch.start(self.wanted(3, prefix="y"), docs=1)
        self.drawing.let(3)
        until(lambda: not latexbatch.status()["running"], "the first is over")
        again = latexbatch.start(self.wanted(2, prefix="y"), docs=1)
        self.assertTrue(again["running"])
        self.assertEqual(2, again["total"])

    def test_nothing_to_make_starts_nothing_and_says_what_it_found(self):
        self.drawing.made = {"k:\\textbf{x0}:" + ":False", "k:\\textbf{x1}::False"}
        got = latexbatch.start(self.wanted(2), docs=1)
        self.assertEqual((False, 0, 2), (got["running"], got["total"], got["already"]))
        self.assertEqual([], latexbatch.activity_entries(activity.entry, activity.KEEP))
        self.assertEqual(0, len(self.drawing.started))

    def test_a_drawing_known_not_to_be_makeable_is_not_made_again_and_is_said(self):
        with mock.patch.object(latexdraw, "peek", lambda tex, theme, inline=False: {"ok": False, "said": "no such theme"}):
            got = latexbatch.start(self.wanted(2, doc="Theme gone"), docs=1)
        self.assertEqual((False, 0, 2), (got["running"], got["total"], got["known_failed"]))

    def test_no_more_compiles_are_in_the_pool_than_it_has_workers(self):
        window = latexbatch.workers()
        latexbatch.start(self.wanted(window * 5), docs=1)
        until(lambda: len(self.drawing.started) >= window, "the window is full")
        time.sleep(0.2)
        self.assertEqual(window, len(self.drawing.started), "a window's worth begun, the rest waiting its turn")
        self.drawing.let(window * 5)
        until(lambda: not latexbatch.status()["running"], "the job is over")
        self.assertLessEqual(self.drawing.most, window)

    def test_an_inline_mark_and_a_block_of_the_same_words_are_two_drawings(self):
        got = latexbatch.start([("\\x", None, False, "A"), ("\\x", None, True, "A")], docs=1)
        self.assertEqual(2, got["total"])


class TheEntry(Base):
    def test_the_entry_counts_drawings_not_bytes_and_carries_the_pages_token(self):
        latexbatch.start(self.wanted(8), docs=3, page="/studio/", job="abc123")
        self.drawing.let(2)
        until(lambda: latexbatch.status()["done"] == 2, "two are over")
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual(("compile", "items", 2, 8, "abc123", "/studio/"),
                         (e["kind"], e["unit"], e["done"], e["total"], e["job"], e["page"]))
        self.assertEqual("Making the LaTeX drawings of 3 documents", e["label"])
        self.assertEqual("Dialoghi", e["stage"], "the document the last drawing was for")
        self.assertNotIn("finished", e)

    def test_a_label_of_one_document_is_singular(self):
        latexbatch.start(self.wanted(2), docs=1)
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual("Making the LaTeX drawings of 1 document", e["label"])

    def test_a_finished_entry_is_kept_for_a_while_and_says_how_it_ended(self):
        latexbatch.start(self.wanted(2), docs=2, job="tok")
        self.drawing.let(2)
        until(lambda: not latexbatch.status()["running"], "over")
        t = latexbatch.status()["finished"]
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP, now=t + 1)
        self.assertEqual((True, "items", None, None), (e["ok"], e["unit"], e["done"], e["total"]))
        self.assertEqual("tok", e["job"], "the page that asked knows it is its own to the end")
        self.assertEqual([], latexbatch.activity_entries(activity.entry, activity.KEEP, now=t + activity.KEEP + 1))

    def test_a_batch_with_a_failure_or_a_stop_did_not_go_well(self):
        self.drawing.fail = {"\\textbf{x0}"}
        latexbatch.start(self.wanted(2), docs=1)
        self.drawing.let(2)
        until(lambda: not latexbatch.status()["running"], "over")
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertFalse(e["ok"])

    def test_an_entry_of_bytes_has_no_unit_at_all(self):
        self.assertNotIn("unit", activity.entry("x", "upload", "Uploading", 1.0, done=5, total=10))
        self.assertEqual("items", activity.entry("x", "compile", "Making", 1.0, done=5, total=10, unit="items")["unit"])


class TheRoutes(Base):
    """The studio's doors, on a temporary library of real documents; the TeX run is still the test's own"""

    @classmethod
    def setUpClass(cls):
        import server
        import store
        cls.server, cls.store = server, store

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.was = self.store.use_library(Path(self.tmp.name) / "library")
        self.addCleanup(self.store.use_library, self.was)
        (Path(self.tmp.name) / "library").mkdir()

    class Reply:
        def __init__(self, body=None, query=None):
            self.body, self.query, self.sent = body, query or {}, None

        def _json_body(self):
            if isinstance(self.body, Exception):
                raise self.body
            return self.body

        def send_json(self, obj, code=200):
            self.sent = (code, obj)

    def doc(self, title, drawings, inline=0, exercise=False):
        md = "---\ntitle: %s\ntarget: it\n---\n\n" % title
        md += "\n\n".join("::::latex\n\\textbf{%s %d}\n::::" % (title, i) for i in range(drawings))
        md += "".join("\n\nA mark [\\textit{%s %d}]{latex} in a line." % (title, i) for i in range(inline))
        if exercise:
            md += "\n\n:::exercise single-choice\nprompt: |\n  Pick.\n  ::::latex\n  \\textbf{%s ex}\n  ::::\n- [x] a\n- [ ] b\n:::\n" % title
        return self.store.create(md)["id"]

    def make(self, body, query=None):
        h = self.Reply(body, query)
        self.server.api_latex_make(h)
        return h.sent

    def test_the_drawings_the_documents_show_are_counted_and_made(self):
        a, b = self.doc("Alpha", 3, inline=2), self.doc("Beta", 1, exercise=True)
        code, st = self.make({"ids": [a, b]})
        self.assertEqual(200, code)
        self.assertEqual((True, 7, 2, 7), (st["running"], st["total"], st["found"], st["wanted"]),
                         "3 blocks and 2 marks; 1 block and 1 in an exercise's prompt: seven distinct drawings")
        self.drawing.let(7)
        until(lambda: not latexbatch.status()["running"], "over")
        got = self.Reply()
        self.server.api_latex_make_status(got)
        self.assertEqual((7, 7, 7), (got.sent[1]["total"], got.sent[1]["done"], got.sent[1]["made"]))

    def test_a_document_that_is_gone_is_left_out_and_the_rest_are_made(self):
        a = self.doc("Alpha", 2)
        code, st = self.make({"ids": [a, "no-such-document"]})
        self.assertEqual((200, 2, 1), (code, st["total"], st["found"]))

    def test_the_pages_token_is_the_entrys(self):
        a = self.doc("Alpha", 2)
        self.make({"ids": [a]}, {"job": ["tok123"]})
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual("tok123", e["job"])

    def test_what_is_not_a_list_of_ids_is_refused_in_words(self):
        for body in ({}, {"ids": []}, {"ids": "abc"}, {"ids": [1, 2]}, None):
            code, said = self.make(body)
            self.assertEqual(400, code, body)
            self.assertEqual("Say which documents.", said["error"])
        code, said = self.make(ValueError("bad"))
        self.assertEqual((400, "That was not JSON."), (code, said["error"]))

    def test_a_second_batch_while_one_runs_is_refused_with_how_far_the_first_has_got(self):
        a = self.doc("Alpha", 3)
        self.make({"ids": [a]})
        code, said = self.make({"ids": [a]})
        self.assertEqual(409, code)
        self.assertTrue(said["running"] and said["total"] == 3, said)
        self.assertIn("being made already", said["error"])

    def test_nothing_to_make_is_a_total_of_none_and_the_page_is_told_why(self):
        none = self.doc("Plain", 0)
        code, st = self.make({"ids": [none]})
        self.assertEqual((200, 0, 0, False), (code, st["total"], st["wanted"], st["running"]))
        a = self.doc("Alpha", 2)
        self.make({"ids": [a]})
        self.drawing.let(2)
        until(lambda: not latexbatch.status()["running"], "over")
        code, again = self.make({"ids": [a]})
        self.assertEqual((0, 2, 2), (again["total"], again["wanted"], again["already"]), "all made already")

    def test_the_stop_door_stops_it(self):
        a = self.doc("Alpha", latexbatch.workers() * 4)
        self.make({"ids": [a]})
        until(lambda: len(self.drawing.started) >= 1, "begun")
        h = self.Reply()
        self.server.api_latex_make_stop(h)
        self.drawing.let(100)
        until(lambda: not latexbatch.status()["running"], "over")
        self.assertTrue(latexbatch.status()["stopped"])

    def test_the_routes_are_in_the_table_and_a_file_opened_from_the_computer_has_none_of_them(self):
        table = {(m, p) for m, p, _f in self.server.ROUTES}
        for want in (("POST", r"^/api/latex/make$"), ("GET", r"^/api/latex/make$"), ("POST", r"^/api/latex/make/stop$")):
            self.assertIn(want, table)
        import re
        for method, path in (("POST", "/api/latex/make"), ("POST", "/api/latex/make/stop"), ("GET", "/api/latex/make")):
            self.assertTrue(any(m == method and re.match(p, path) for m, p in self.server._NOT_IN_A_FILE), (method, path))


class TheHubsList(Base):
    def test_serve_merges_the_entry_into_what_every_page_asks(self):
        import serve
        latexbatch.start(self.wanted(6), docs=2, page="/studio/", job="hubtok")
        self.drawing.let(2)
        until(lambda: latexbatch.status()["done"] == 2, "two over")
        mine = [e for e in serve.activity_now()["running"] if e["kind"] == "compile" and e.get("unit") == "items"]
        self.assertEqual(1, len(mine))
        self.assertEqual((2, 6, "hubtok"), (mine[0]["done"], mine[0]["total"], mine[0]["job"]))


if __name__ == "__main__":
    unittest.main()
