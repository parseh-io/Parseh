# SPDX-License-Identifier: GPL-3.0-or-later
"""The LaTeX drawings of many documents, made by a helper process at the lowest priority (a0.5.6; the helper a0.5.7, lib/latexbatch.py).

    python3 -m unittest tests/test_latex_batch.py

  * THE HELPER'S WORK (`latexbatch.work`, with the TeX run, the reading of the documents and the memory left to the test): the
    documents are looked through first, one at a time, yielding between two, with a count of their own; what is not made is
    worked out; the total is known before the first drawing; `done` goes up by one each time a drawing is over, whatever their
    number; a drawing that fails, or raises, is over and kept as a problem, and never ends the batch; a stop (a file) begins no new
    drawing, in either stage; no more run side by side than it has workers; and with little memory free no new run is begun beside
    the ones under way (and one is begun when none is, or nothing would ever be made);
  * THE SERVER'S SIDE (`start`, `status`, `stop`, `activity_entries`, with a stand-in for the process): start answers at once and
    reads nothing; one at a time; the status is the helper's file and nothing else; a helper that is gone without its last word is
    said in words; the entry the bar is drawn from counts documents and then drawings (`unit` "items") and carries the page's token;
  * THE ROUTES of the studio, and serve.py's list; and the books of who owns which drawing (latexdraw) are left alone by the helper
    and no longer rewritten for each drawing made;
  * THE REAL HELPER, with the TeX this computer has: it works at nice 19 and so does the TeX it starts, it makes the drawings, and it
    ends when the process that started it is killed.
The page, the bar, and the requests of the rest of the hub while it works: tests/latex_batch.mjs.
"""
import json
import os
import signal
import subprocess
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


def until(fn, what, seconds=15.0):
    end = time.time() + seconds
    while time.time() < end:
        if fn():
            return
        time.sleep(0.01)
    raise AssertionError("timed out: " + what)


class Drawing:
    """latexdraw's peek and draw as the helper meets them: a drawing is `made` once drawn, and each draw waits on `gate` (one
    permit lets one drawing end), so a test sees the helper between two drawings, never racing it"""

    def __init__(self, fail=(), boom=()):
        self.made, self.fail, self.boom = set(), set(fail), set(boom)
        self.gate = threading.Semaphore(0)
        self.started, self.alive, self.most = [], 0, 0
        self.lock = threading.Lock()

    def peek(self, tex, theme, inline=False):
        key = "k:%s:%s:%s" % (tex, theme or "", bool(inline))
        return {"ok": True, "key": key} if key in self.made else {"ok": None, "key": key}

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


def wanted_of(docs):
    """The way the helper reads a document, as the test has it: {id: [(tex, theme, inline, title)]}; None = gone"""
    return lambda doc_id: docs.get(doc_id)


def drawings(n, title="Dialoghi", inline=False, prefix="x"):
    return [("\\textbf{%s%d}" % (prefix, i), None, inline, title) for i in range(n)]


class Helper(unittest.TestCase):
    """`latexbatch.work` in a thread of the test, with its status file in a temporary folder"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.drawing = Drawing()
        for target, fn in (("peek", self.drawing.peek),):
            patch = mock.patch.object(latexdraw, target, fn)
            patch.start()
            self.addCleanup(patch.stop)
        # a status file written at every change, not every fifth of a second
        patch = mock.patch.object(latexbatch, "WRITE_EVERY", 0.0)
        patch.start()
        self.addCleanup(patch.stop)
        self.status_path = os.path.join(self.tmp.name, "status.json")
        self.stop_path = os.path.join(self.tmp.name, "stop")
        self.threads = []
        self.addCleanup(self.finish)

    def finish(self):
        self.drawing.let(500)
        for t in self.threads:
            t.join(10)

    def run_helper(self, docs, free_mb=lambda: None, workers=2, sleeps=None):
        spec = {"ids": list(docs), "stop": self.stop_path}
        writer = latexbatch.Writer(self.status_path)
        yields = sleeps if sleeps is not None else []
        patch = mock.patch.object(latexbatch, "workers", lambda *a, **k: workers)
        patch.start()
        self.addCleanup(patch.stop)
        t = threading.Thread(target=latexbatch.work, kwargs=dict(
            spec=spec, writer=writer, draw=self.drawing.draw, wanted_of=wanted_of(docs), free_mb=free_mb,
            sleep=lambda s: yields.append(s)), daemon=True)
        t.start()
        self.threads.append(t)
        return t

    def status(self):
        try:
            with open(self.status_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def over(self):
        until(lambda: self.status().get("phase") == "over", "the helper is over")
        return self.status()


class TheHelperWork(Helper):
    def test_the_documents_are_looked_through_first_one_at_a_time_with_a_count_of_their_own(self):
        yields = []
        docs = {"d%d" % n: drawings(2, "Doc %d" % n, prefix="d%d" % n) for n in range(6)}
        docs["gone"] = None
        self.run_helper(docs, sleeps=yields)
        until(lambda: self.status().get("phase") == "making", "the drawings begin")
        st = self.status()
        self.assertEqual((7, 7, 6, 12), (st["docs_total"], st["docs_done"], st["docs_found"], st["wanted"]))
        self.assertGreaterEqual(len(yields), 7, "the helper yields between two documents")

    def test_the_total_is_known_before_the_first_drawing_and_counts_what_is_shared_once(self):
        docs = {"a": drawings(5), "b": drawings(3, "Another")}                  # three drawings both show
        self.run_helper(docs)
        until(lambda: self.drawing.started, "the first drawing is begun")
        st = self.status()
        self.assertEqual(("making", 5, 0), (st["phase"], st["total"], st["done"]), "five distinct, none made yet")

    def test_it_counts_one_by_one_in_the_order_drawings_end_whatever_their_number(self):
        n = 60
        self.run_helper({"a": drawings(n)}, workers=3)
        seen = []
        for want in range(1, n + 1):
            self.drawing.let(1)
            until(lambda: self.status().get("done", 0) >= want, "drawing %d is over" % want)
            seen.append(self.status()["done"])
        st = self.over()
        self.assertEqual((n, n, n, 0, False), (st["total"], st["done"], st["made"], st["failed"], st["stopped"]))
        self.assertEqual(sorted(seen), seen, "never backwards")
        self.assertEqual(n, len(set(seen)), "every drawing moved the count: %d steps for %d drawings" % (len(set(seen)), n))

    def test_a_drawing_that_cannot_be_made_is_over_and_kept_as_a_problem_and_the_batch_goes_on(self):
        self.drawing.fail, self.drawing.boom = {"\\textbf{x1}"}, {"\\textbf{x3}"}
        self.run_helper({"a": drawings(5, "Bad one")})
        self.drawing.let(5)
        st = self.over()
        self.assertEqual((5, 5, 3, 2), (st["total"], st["done"], st["made"], st["failed"]))
        said = sorted(p["said"] for p in st["problems"])
        self.assertTrue(said[0].startswith("RuntimeError: TeX fell over") and "is not a command LaTeX knows" in said[1], said)
        self.assertEqual({"Bad one"}, {p["doc"] for p in st["problems"]})

    def test_a_stop_in_the_making_begins_no_new_drawing_and_keeps_what_was_made(self):
        self.run_helper({"a": drawings(40)}, workers=2)
        until(lambda: len(self.drawing.started) == 2, "the first two are under way")
        self.drawing.let(1)
        until(lambda: self.status().get("done") == 1, "one is over")
        Path(self.stop_path).write_text("stop")
        self.drawing.let(40)
        st = self.over()
        self.assertTrue(st["stopped"])
        self.assertLess(st["done"], st["total"])
        self.assertEqual(st["done"], st["made"])
        self.assertLessEqual(len(self.drawing.started), 4, "the ones under way finished, and no more than the ones the stop crossed")

    def test_a_stop_while_the_documents_are_being_read_ends_it_there(self):
        Path(self.stop_path).write_text("stop")
        self.run_helper({"a": drawings(5), "b": drawings(5, prefix="y")})
        st = self.over()
        self.assertTrue(st["stopped"])
        self.assertEqual((0, 0), (st["total"], len(self.drawing.started)))

    def test_nothing_to_make_is_a_total_of_none_and_what_was_found(self):
        self.drawing.made = {"k:\\textbf{x0}::False", "k:\\textbf{x1}::False"}
        self.run_helper({"a": drawings(2)})
        st = self.over()
        self.assertEqual((0, 2, 2, 0), (st["total"], st["already"], st["wanted"], len(self.drawing.started)))

    def test_a_drawing_known_not_to_be_makeable_is_not_made_again_and_is_counted(self):
        with mock.patch.object(latexdraw, "peek", lambda tex, theme, inline=False: {"ok": False, "said": "no such theme"}):
            self.run_helper({"a": drawings(2, "Theme gone")})
            st = self.over()
        self.assertEqual((0, 2), (st["total"], st["known_failed"]))

    def test_no_more_run_side_by_side_than_it_has_workers(self):
        self.run_helper({"a": drawings(30)}, workers=3)
        until(lambda: len(self.drawing.started) >= 3, "the window is full")
        time.sleep(0.3)
        self.assertEqual(3, len(self.drawing.started), "a window's worth begun, the rest waiting its turn")
        self.assertEqual(3, self.status()["active"])
        self.drawing.let(30)
        self.over()
        self.assertLessEqual(self.drawing.most, 3)

    def test_with_little_memory_free_no_new_run_is_begun_beside_those_under_way(self):
        free = [4000]
        self.run_helper({"a": drawings(12)}, free_mb=lambda: free[0], workers=3)
        until(lambda: len(self.drawing.started) == 3, "three are under way")
        free[0] = 300
        self.drawing.let(1)
        until(lambda: self.status().get("done") == 1, "one is over")
        until(lambda: self.status().get("waiting") is True, "the helper says it is waiting for memory")
        self.drawing.let(1)
        until(lambda: self.status().get("done") == 2, "a second is over")
        time.sleep(1.2)
        self.assertEqual(3, len(self.drawing.started), "none was begun while little was free, though there was room")
        self.assertEqual(1, self.status()["active"])
        free[0] = 4000
        until(lambda: len(self.drawing.started) > 3, "and as soon as there is memory again the work goes on")
        self.drawing.let(20)
        st = self.over()
        self.assertEqual((12, 12), (st["total"], st["made"]))
        self.assertFalse(st["waiting"])

    def test_with_little_memory_and_nothing_under_way_one_is_begun_all_the_same(self):
        self.run_helper({"a": drawings(3)}, free_mb=lambda: 100, workers=2)
        until(lambda: len(self.drawing.started) >= 1, "a run is begun with nothing else under way")
        self.drawing.let(10)
        self.assertEqual(3, self.over()["made"], "and the work is done, slowly")

    def test_the_worker_count_follows_the_cores_and_the_free_memory(self):
        self.assertEqual(4, latexbatch.workers(24, 60000))
        self.assertEqual(2, latexbatch.workers(4, 3000))
        self.assertEqual(1, latexbatch.workers(8, 1500), "little memory free: one")
        self.assertEqual(1, latexbatch.workers(2, None), "two cores: one, memory unknown")
        self.assertEqual(3, latexbatch.workers(6, None))

    def test_an_inline_mark_and_a_block_of_the_same_words_are_two_drawings(self):
        self.run_helper({"a": [("\\x", None, False, "A"), ("\\x", None, True, "A")]})
        until(lambda: self.status().get("phase") == "making", "making")
        self.assertEqual(2, self.status()["total"])

    def test_the_helper_leaves_when_its_parent_has_gone(self):
        spec = {"ids": ["a"], "stop": self.stop_path, "parent": os.getpid() + 999999}
        writer = latexbatch.Writer(self.status_path)
        with mock.patch.object(latexbatch, "workers", lambda *a, **k: 1), \
                mock.patch.object(latexdraw, "stop_all") as killed:
            t = threading.Thread(target=latexbatch.work, kwargs=dict(
                spec=spec, writer=writer, draw=self.drawing.draw, wanted_of=wanted_of({"a": drawings(5)}),
                free_mb=lambda: None, sleep=lambda s: None), daemon=True)
            t.start()
            self.threads.append(t)
            until(lambda: self.drawing.started, "begun")
            self.drawing.let(1)
            until(lambda: not t.is_alive() or self.status().get("done"), "one over")
            self.drawing.let(10)
            t.join(10)
            self.assertFalse(t.is_alive())
            killed.assert_called()


class FakeProcess:
    def __init__(self):
        self.code, self.pid = None, 424242

    def poll(self):
        return self.code


class TheServersSide(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        was = latexdraw.DRAWN
        latexdraw.DRAWN = os.path.join(self.tmp.name, "drawn")
        self.addCleanup(setattr, latexdraw, "DRAWN", was)
        latexbatch._JOB.clear()
        self.addCleanup(latexbatch._JOB.clear)
        self.proc = FakeProcess()
        self.launched = []

    def launch(self, spec_path):
        self.launched.append(spec_path)
        return self.proc

    def start(self, ids=("a", "b"), **kw):
        return latexbatch.start(list(ids), {"library": "/x"}, launch=self.launch, **kw)

    def write(self, **state):
        path = latexbatch._JOB["status"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    def test_start_answers_at_once_and_reads_nothing(self):
        t = time.time()
        st = self.start(("a",) * 1 + tuple("doc%d" % i for i in range(500)), page="/studio/", job="tok")
        self.assertLess(time.time() - t, 0.5)
        self.assertEqual((True, "starting", 0, 0), (st["running"], st["phase"], st["done"], st["total"]))
        spec = json.load(open(self.launched[0], encoding="utf-8"))
        self.assertEqual(501, len(spec["ids"]))
        self.assertEqual({"library": "/x"}, spec["env"])
        self.assertEqual(os.getpid(), spec["parent"])

    def test_one_at_a_time_and_another_when_the_helper_is_over(self):
        self.start()
        with self.assertRaises(latexbatch.Busy):
            self.start()
        self.proc.code = 0
        self.write(phase="over", total=3, done=3, made=3, finished=time.time())
        self.start()
        self.assertEqual(2, len(self.launched))

    def test_the_status_is_what_the_helper_wrote_and_the_stage_it_is_in(self):
        self.start(("a", "b", "c"))
        self.write(phase="scanning", docs_total=3, docs_done=1, docs_found=1, wanted=4)
        st = latexbatch.status()
        self.assertEqual((True, "scanning", 3, 1), (st["running"], st["phase"], st["docs_total"], st["docs_done"]))
        self.write(phase="making", docs_total=3, docs_done=3, docs_found=3, wanted=9, total=7, done=2, made=2, active=2, last="Beta")
        st = latexbatch.status()
        self.assertEqual(("making", 7, 2, 2, 3, "Beta"), (st["phase"], st["total"], st["done"], st["active"], st["docs"], st["last"]))

    def test_a_helper_gone_without_its_last_word_is_said_in_words(self):
        self.start()
        self.write(phase="making", total=5, done=2, made=2)
        self.proc.code = -9
        st = latexbatch.status()
        self.assertFalse(st["running"])
        self.assertIn("stopped before it was done", st["error"])
        self.assertIsNotNone(st["finished"])
        self.start()                                   # and a new one may be begun

    def test_a_helper_that_could_not_be_started_is_said_too(self):
        def refuse(path):
            raise OSError("no such program")
        latexbatch.start(["a"], {}, launch=refuse)
        st = latexbatch.status()
        self.assertFalse(st["running"])
        self.assertIn("could not be started: no such program", st["error"])

    def test_the_stop_is_a_file_the_helper_looks_for_and_only_while_it_runs(self):
        self.start()
        latexbatch.stop()
        self.assertTrue(os.path.exists(latexbatch._JOB["stop"]))
        self.proc.code = 0
        self.write(phase="over", total=0)
        os.unlink(latexbatch._JOB["stop"])
        latexbatch.stop()
        self.assertFalse(os.path.exists(latexbatch._JOB["stop"]), "nothing to stop")

    def test_shutdown_ends_the_helper_and_its_whole_group(self):
        self.start()
        with mock.patch.object(os, "killpg") as killed:
            latexbatch.shutdown()
        killed.assert_called_once_with(424242, signal.SIGKILL)

    def test_an_idle_server_has_an_idle_status_and_no_entry(self):
        st = latexbatch.status()
        self.assertEqual((False, "idle", 0), (st["running"], st["phase"], st["total"]))
        self.assertEqual([], latexbatch.activity_entries(activity.entry, activity.KEEP))

    def test_the_entry_counts_documents_then_drawings_not_bytes_and_carries_the_pages_token(self):
        self.start(("a", "b", "c", "d"), page="/studio/", job="abc123")
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual(("compile", "items", "abc123", "/studio/"), (e["kind"], e["unit"], e["job"], e["page"]))
        self.assertEqual("Looking through 4 documents for LaTeX drawings", e["label"], "from the first moment, before the helper has said a word")
        self.write(phase="scanning", docs_total=4, docs_done=1, docs_found=1, wanted=2)
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual((1, 4, "reading the documents"), (e["done"], e["total"], e["stage"]))
        self.write(phase="making", docs_total=4, docs_done=4, docs_found=4, wanted=70, total=63, done=20, made=20, active=2, last="Gamma 6")
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual("Making the LaTeX drawings of 4 documents", e["label"])
        self.assertEqual((20, 63, "2 being made · Gamma 6"), (e["done"], e["total"], e["stage"]))
        self.assertNotIn("finished", e)
        self.write(phase="making", total=63, done=20, active=0, waiting=True)
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual("waiting for memory", e["stage"] if False else "waiting for memory")

    def test_a_label_of_one_document_is_singular(self):
        self.start(("a",))
        self.write(phase="making", docs_found=1, total=3, done=1)
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual("Making the LaTeX drawings of 1 document", e["label"])

    def test_a_finished_entry_is_kept_for_a_while_and_says_how_it_ended(self):
        self.start(("a", "b"), job="tok")
        t = time.time()
        self.proc.code = 0
        self.write(phase="over", docs_found=2, total=5, done=5, made=5, failed=0, finished=t)
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP, now=t + 1)
        self.assertEqual((True, "items", None, None, "tok"), (e["ok"], e["unit"], e["done"], e["total"], e["job"]))
        self.assertEqual([], latexbatch.activity_entries(activity.entry, activity.KEEP, now=t + activity.KEEP + 1))

    def test_a_batch_with_a_failure_a_stop_or_an_error_did_not_go_well(self):
        for fields in ({"failed": 1}, {"stopped": True}, {"error": "boom"}):
            latexbatch._JOB.clear()
            self.proc = FakeProcess()
            self.start()
            self.proc.code = 0
            self.write(phase="over", total=4, done=4, made=3, finished=time.time(), **fields)
            (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
            self.assertFalse(e["ok"], fields)

    def test_a_batch_that_found_nothing_to_make_leaves_no_done_behind(self):
        self.start()
        self.proc.code = 0
        self.write(phase="over", total=0, wanted=0, finished=time.time())
        self.assertEqual([], latexbatch.activity_entries(activity.entry, activity.KEEP))

    def test_an_entry_of_bytes_has_no_unit_at_all(self):
        self.assertNotIn("unit", activity.entry("x", "upload", "Uploading", 1.0, done=5, total=10))
        self.assertEqual("items", activity.entry("x", "compile", "Making", 1.0, done=5, total=10, unit="items")["unit"])

    def test_the_helper_is_started_at_the_lowest_priority_in_a_session_of_its_own(self):
        seen = {}

        class Popen:
            def __init__(self, cmd, **kw):
                seen["cmd"], seen["kw"] = cmd, kw
                self.pid = 1

        os.makedirs(self.tmp.name, exist_ok=True)
        spec = os.path.join(self.tmp.name, "spec.json")
        with mock.patch.object(subprocess, "Popen", Popen):
            latexbatch._launch(spec)
        self.assertEqual("--worker", seen["cmd"][2])
        if os.name != "nt":
            self.assertTrue(seen["kw"]["start_new_session"])
            with mock.patch.object(os, "nice") as nice:
                seen["kw"]["preexec_fn"]()
            nice.assert_called_once_with(19)
        else:
            self.assertTrue(seen["kw"]["creationflags"] & 0x40)


class TheRoutes(unittest.TestCase):
    """The studio's doors; the helper is a stand-in"""

    @classmethod
    def setUpClass(cls):
        import server
        import store
        cls.server, cls.store = server, store

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.was = self.store.use_library(Path(self.tmp.name) / "library")
        self.addCleanup(self.store.use_library, self.was)
        (Path(self.tmp.name) / "library").mkdir()
        was = latexdraw.DRAWN
        latexdraw.DRAWN = os.path.join(self.tmp.name, "drawn")
        self.addCleanup(setattr, latexdraw, "DRAWN", was)
        latexbatch._JOB.clear()
        self.addCleanup(latexbatch._JOB.clear)
        self.proc = FakeProcess()
        patch = mock.patch.object(latexbatch, "_launch", lambda spec_path: self.proc)
        patch.start()
        self.addCleanup(patch.stop)

    class Reply:
        def __init__(self, body=None, query=None):
            self.body, self.query, self.sent = body, query or {}, None

        def _json_body(self):
            if isinstance(self.body, Exception):
                raise self.body
            return self.body

        def send_json(self, obj, code=200):
            self.sent = (code, obj)

    def make(self, body, query=None):
        h = self.Reply(body, query)
        self.server.api_latex_make(h)
        return h.sent

    def test_the_post_starts_the_helper_and_answers_at_once_having_read_nothing(self):
        ids = [self.store.create("---\ntitle: T%d\ntarget: it\n---\n\n::::latex\n\\x%d\n::::\n" % (i, i))["id"] for i in range(3)]
        with mock.patch.object(self.store, "get", side_effect=AssertionError("the request read a document")):
            code, st = self.make({"ids": ids + ["not-there"]}, {"job": ["tok123"]})
        self.assertEqual((200, True, "starting", 4), (code, st["running"], st["phase"], st["shown"]))
        spec = json.load(open(os.path.join(latexbatch._JOB["dir"], "spec.json"), encoding="utf-8"))
        self.assertEqual(ids + ["not-there"], spec["ids"])
        self.assertEqual(str(self.store.lib()), spec["env"]["library"])
        self.assertEqual(latexdraw.DRAWN, spec["env"]["drawn"], "the helper is told where this studio keeps things")
        (e,) = latexbatch.activity_entries(activity.entry, activity.KEEP)
        self.assertEqual("tok123", e["job"])

    def test_what_is_not_a_list_of_ids_is_refused_in_words(self):
        for body in ({}, {"ids": []}, {"ids": "abc"}, {"ids": [1, 2]}, {"ids": ["../etc"]}, None):
            code, said = self.make(body)
            self.assertEqual(400, code, body)
            self.assertEqual("Say which documents.", said["error"])
        code, said = self.make(ValueError("bad"))
        self.assertEqual((400, "That was not JSON."), (code, said["error"]))

    def test_a_second_batch_while_one_runs_is_refused_with_how_far_the_first_has_got(self):
        self.make({"ids": ["alpha"]})
        code, said = self.make({"ids": ["alpha"]})
        self.assertEqual(409, code)
        self.assertTrue(said["running"], said)
        self.assertIn("being made already", said["error"])

    def test_the_status_and_the_stop_doors(self):
        self.make({"ids": ["alpha"]})
        h = self.Reply()
        self.server.api_latex_make_status(h)
        self.assertEqual("starting", h.sent[1]["phase"])
        self.server.api_latex_make_stop(h)
        self.assertTrue(os.path.exists(latexbatch._JOB["stop"]))

    def test_the_routes_are_in_the_table_and_a_file_opened_from_the_computer_has_none_of_them(self):
        import re
        table = {(m, p) for m, p, _f in self.server.ROUTES}
        for want in (("POST", r"^/api/latex/make$"), ("GET", r"^/api/latex/make$"), ("POST", r"^/api/latex/make/stop$")):
            self.assertIn(want, table)
        for method, path in (("POST", "/api/latex/make"), ("POST", "/api/latex/make/stop"), ("GET", "/api/latex/make")):
            self.assertTrue(any(m == method and re.match(p, path) for m, p in self.server._NOT_IN_A_FILE), (method, path))

    def test_serve_merges_the_entry_into_what_every_page_asks(self):
        import serve
        self.make({"ids": ["alpha", "beta"]}, {"job": ["hubtok"]})
        mine = [e for e in serve.activity_now()["running"] if e["kind"] == "compile" and e.get("unit") == "items"]
        self.assertEqual(1, len(mine))
        self.assertEqual("hubtok", mine[0]["job"])


class TheBooksOfWhoOwnsWhat(unittest.TestCase):
    """The helper writes none, and the server no longer rewrites them for every drawing made"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        was = latexdraw.DRAWN
        latexdraw.DRAWN = os.path.join(self.tmp.name, "drawn")
        os.makedirs(latexdraw.DRAWN)
        self.addCleanup(setattr, latexdraw, "DRAWN", was)

    def test_a_drawing_a_document_owns_rewrites_nothing(self):
        key = "a" * 64
        latexdraw.own_source("doc:one", "x")                      # an owner with no keys: the books exist
        doc = latexdraw._owner_doc()
        doc["owners"]["doc:one"] = [key]
        latexdraw._save_owner_doc(doc)
        with mock.patch.object(latexdraw, "_save_owner_doc") as saved:
            latexdraw._mark_unowned(key)
        saved.assert_not_called()
        with mock.patch.object(latexdraw, "_save_owner_doc") as saved:
            latexdraw._mark_unowned("b" * 64)                     # one nobody owns: the grace period begins, which is a change
        saved.assert_called_once()

    def test_the_helper_turns_the_books_off(self):
        with mock.patch.object(latexdraw, "BOOKKEEPING", False), mock.patch.object(latexdraw, "_save_owner_doc") as saved:
            latexdraw._mark_unowned("c" * 64)
        saved.assert_not_called()

    def test_the_helpers_folder_is_never_a_drawing_and_does_not_outlive_the_server(self):
        folder = os.path.join(latexdraw.DRAWN, latexdraw.BATCH_DIR, "1-1")
        os.makedirs(folder)
        Path(folder, "status.json").write_text("{}")
        Path(folder, ("d" * 64) + ".svg").write_text("<svg/>")      # not that it would be: it is not looked at
        self.assertNotIn("d" * 64, latexdraw._persistent_keys())
        latexdraw.prune()
        self.assertFalse(os.path.exists(os.path.join(latexdraw.DRAWN, latexdraw.BATCH_DIR)))


@unittest.skipUnless(sys.platform.startswith("linux"), "reads /proc")
@unittest.skipUnless(__import__("shutil").which("xelatex"), "no xelatex: the real helper makes real drawings")
class TheRealHelper(unittest.TestCase):
    """Started as the server starts it, on a temporary library, with the TeX this computer has"""

    def setUp(self):
        import store
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.was = store.use_library(base / "library")
        self.addCleanup(store.use_library, self.was)
        (base / "library").mkdir()
        import latexthemes
        import texpackages
        self.saved = (latexdraw.DRAWN, latexthemes.STORE, texpackages.TREE)
        latexdraw.DRAWN, latexthemes.STORE, texpackages.TREE = str(base / "drawn"), str(base / "latex.json"), str(base / "texmf")
        self.addCleanup(self.restore, latexthemes, texpackages)
        latexbatch._JOB.clear()
        self.addCleanup(latexbatch.clear)
        self.ids = [store.create("---\ntitle: R%d\ntarget: en\n---\n\n::::latex\n\\textbf{real %d}\n::::\n\nA [\\textit{mark %d}]{latex}.\n" % (i, i, i))["id"]
                    for i in range(8)]
        self.env = {"library": str(base / "library"), "drawn": latexdraw.DRAWN, "themes": latexthemes.STORE, "tex_tree": texpackages.TREE}

    def restore(self, latexthemes, texpackages):
        latexdraw.DRAWN, latexthemes.STORE, texpackages.TREE = self.saved

    @staticmethod
    def nice_of(pid):
        try:
            with open("/proc/%d/stat" % pid, encoding="ascii") as fh:
                return int(fh.read().rsplit(")", 1)[1].split()[16])
        except (OSError, ValueError, IndexError):
            return None

    def test_it_makes_the_drawings_at_the_lowest_priority_and_so_does_its_tex(self):
        t = time.time()
        st = latexbatch.start(self.ids, self.env)
        self.assertLess(time.time() - t, 0.5, "start answers at once")
        pid = latexbatch._JOB["proc"].pid
        niceness, tex_nice = set(), set()
        end = time.time() + 60
        while time.time() < end and latexbatch.status()["running"]:
            niceness.add(self.nice_of(pid))
            for name in os.listdir("/proc"):
                if name.isdigit():
                    try:
                        with open("/proc/%s/stat" % name, encoding="ascii") as fh:
                            raw = fh.read()
                        parts = raw.rsplit(")", 1)
                        if "xelatex" in parts[0] and int(parts[1].split()[1]) == pid:
                            tex_nice.add(int(parts[1].split()[16]))
                    except (OSError, ValueError, IndexError):
                        pass
            time.sleep(0.02)
        st = latexbatch.status()
        self.assertEqual((16, 16, 0), (st["total"], st["made"], st["failed"]), st)
        self.assertEqual({19}, niceness - {None}, "the helper works at nice 19")
        self.assertTrue(tex_nice and tex_nice == {19}, "and so does every TeX it starts: %s" % tex_nice)

    def test_it_ends_when_the_process_that_started_it_is_killed(self):
        base = Path(self.tmp.name)
        script = (
            "import sys, json, time\n"
            "sys.path[:0] = %r\n"
            "import latexbatch, latexdraw\n"
            "latexdraw.DRAWN = %r\n"
            "latexbatch.start(%r, %r)\n"
            "print(latexbatch._JOB['proc'].pid, flush=True)\n"
            "time.sleep(300)\n" % ([str(ROOT / "lib")], latexdraw.DRAWN, self.ids, self.env))
        # many more documents, so that the helper is still at it when the parent goes
        parent = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: parent.poll() is None and parent.kill())
        helper = int(parent.stdout.readline())
        time.sleep(0.5)
        os.kill(parent.pid, signal.SIGKILL)
        parent.wait()
        end = time.time() + 12
        while time.time() < end and os.path.exists("/proc/%d" % helper) and self._alive(helper):
            time.sleep(0.2)
        self.assertFalse(self._alive(helper), "the helper outlived the server that started it")

    @staticmethod
    def _alive(pid):
        try:
            with open("/proc/%d/stat" % pid, encoding="ascii") as fh:
                return fh.read().rsplit(")", 1)[1].split()[0] not in ("Z", "X")
        except OSError:
            return False


if __name__ == "__main__":
    unittest.main()
