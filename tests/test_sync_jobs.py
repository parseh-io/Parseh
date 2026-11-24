# SPDX-License-Identifier: GPL-3.0-or-later
"""Jobs lent between paired computers (lib/syncjobs.py, lane D; docs/sync.md "Jobs").

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_jobs.py

Two or three installs in one process (tests/syncfake.py).  The book build
and the narration's alignment are FAKED by runners put in syncjobs.RUNNERS
(they write what the real pipelines write: a PDF and a reader; a changed
chapter); the estimate by the sound runs the real lib/wavealign.py when
NumPy is there.  The capabilities are set through syncjobs.CAPS_FORCE.
"""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from syncfake import World      # noqa: E402
import syncexchange as X        # noqa: E402
import syncjobs as J            # noqa: E402
import synclog                  # noqa: E402

BOOK = "book:italian/storia"
CAN = {"latex": True, "reader": True, "estimate": True, "ffmpeg": True}
CANNOT = {"latex": False, "reader": False, "estimate": False, "ffmpeg": False}


def book(inst, text="Una storia.\n"):
    base = "books/italian/storia/"
    inst.w(base + "book.json", '{"title": "Storia"}')
    inst.w(base + "ch1.tex", text)
    return BOOK


def fake_build(rec, say):
    import syncunits
    d = syncunits.locate(rec["unit"]).where
    os.makedirs(os.path.join(d, "reader"), exist_ok=True)
    with open(os.path.join(d, "storia.pdf"), "wb") as fh:
        fh.write(b"%PDF-1.5 built on " + J.syncid.name().encode() + b"\n" + os.urandom(3000))
    with open(os.path.join(d, "reader", "index.html"), "w") as fh:
        fh.write("<p>the reader</p>")
    say("built")
    return {"result": {"what": "pdf"}, "outputs": J._built_files(d, "pdf")}


def fake_align(rec, say):
    import syncunits
    d = syncunits.locate(rec["unit"]).where
    with open(os.path.join(d, "ch1.tex"), "a") as fh:
        fh.write("% @par 1.25\n")
    return {"result": {}}


class Jobs(unittest.TestCase):
    names = ("A", "B")

    def setUp(self):
        self.release = threading.Event()     # set in tearDown: lets a held runner end
        self.w = World(*self.names).__enter__()
        for n in self.names:
            setattr(self, n, getattr(self.w, n))
            with self.w.on(getattr(self.w, n)):
                J.syncid.set_name(n)
        J.forget()
        J.register()
        J.INLINE = True
        self.was = (dict(J.RUNNERS), J.DEADLINE, dict(J.CAPS_FORCE))
        J.RUNNERS.update({"book-build": fake_build, "narration-align": fake_align})
        J.CAPS_FORCE.clear()
        J.CAPS_FORCE[self.A.id] = dict(CAN)
        J.CAPS_FORCE[self.B.id] = dict(CANNOT)

    def tearDown(self):
        # A job left working (a runner held for a frozen-holder test) must END HERE, inside this test's stores:
        # finished later it records its unit in whatever config/sync the next test has put in place
        # (it once left a stray config/sync beside tests/test_later.py's prefs).
        self.release.set()
        for t in threading.enumerate():
            if t.name.startswith("job-"):
                t.join(timeout=10)
        J.RUNNERS.clear()
        J.RUNNERS.update(self.was[0])
        J.DEADLINE = self.was[1]
        J.CAPS_FORCE.clear()
        J.CAPS_FORCE.update(self.was[2])
        J.INLINE = False
        J.forget()
        self.w.__exit__(None, None, None)

    def on(self, inst):
        return self.w.on(inst)

    def switch(self, inst, **kw):
        with self.on(inst):
            return J.set_switches(**kw)

    def ask_build(self):
        with self.on(self.B):
            self.assertEqual(J.can_here("book-build", {"what": "pdf"})[0], False)
            return J.ask("book-build", {"what": "pdf"}, "Build “Storia”", unit=BOOK)["id"]

    def step(self, inst, n=1):
        for _ in range(n):
            with self.on(inst):
                J.step()

    def state(self, inst, jid):
        with self.on(inst):
            return J.view(jid)


class Basics(Jobs):
    def test_switches_are_off_on_a_fresh_install_and_this_devices_own(self):
        with self.on(self.A):
            self.assertEqual(J.switches(), {"send": False, "accept": False})
            self.assertEqual(J.set_switches(send=True), {"send": True, "accept": False})
            self.assertTrue(os.path.isfile(os.path.join(synclog.home(), "jobs-switches.json")))
            synclog.scan()
            self.assertFalse([r for r in synclog.rows() if "job" in r["unit"]], "never a synced unit")
        with self.on(self.B):
            self.assertEqual(J.switches(), {"send": False, "accept": False})

    def test_capabilities_here_and_of_a_partner(self):
        self.switch(self.A, accept=True)
        with self.on(self.A):
            caps = J.capabilities()
            for k in ("whisper", "latex", "aligners", "analyzers", "gpu", "accepts"):
                self.assertIn(k, caps)
            self.assertTrue(caps["accepts"] and caps["latex"])
        with self.on(self.B):
            them = J.capabilities(self.A.id)
            self.assertTrue(them["known"] and them["accepts"] and them["latex"])
            self.assertFalse(J.capabilities()["latex"])
            who = J.who_can("book-build", {"what": "pdf"})
            self.assertEqual([(p["id"], p["can"]) for p in who], [(self.A.id, True)])


class Lending(Jobs):
    def setUp(self):
        super().setUp()
        self.switch(self.B, send=True)
        self.switch(self.A, accept=True)
        book(self.B)

    def test_a_job_only_A_can_do_is_taken_by_A_and_its_result_arrives_on_B(self):
        jid = self.ask_build()
        self.assertEqual(self.state(self.B, jid)["say"], "waiting for a computer")
        self.step(self.B)
        # A did not hold the book: it brought B's version in first (the offer's answer is "retry")
        with self.on(self.A):
            self.assertIsNotNone(synclog.get(BOOK), "A holds the book now")
        self.step(self.B, 3)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "done", st)
        self.assertTrue(self.B.read("books/italian/storia/storia.pdf").startswith(b"%PDF-1.5 built on A"))
        self.assertEqual(self.B.read("books/italian/storia/reader/index.html"), b"<p>the reader</p>")
        with self.on(self.B):
            j = [x for x in J.jobs() if x["id"] == jid][0]
            self.assertEqual((j["taken_by"], j["taken_by_name"], j["asked_by"]), (self.A.id, "A", self.B.id))
            self.assertEqual(J.waiting_here(), [])
        with self.on(self.A):
            self.assertEqual(J.jobs(), [], "the finished job was dropped on A once its result was here")

    def test_a_change_to_the_unit_comes_back_through_sync(self):
        with self.on(self.B):
            jid = J.ask("narration-align", {}, "Align", unit=BOOK)["id"]
        self.step(self.B, 4)
        self.assertEqual(self.state(self.B, jid)["state"], "done")
        self.assertTrue(self.B.read("books/italian/storia/ch1.tex").endswith(b"% @par 1.25\n"))
        with self.on(self.A), open(self.A.p("books/italian/storia/ch1.tex"), "rb") as fh:
            self.assertEqual(fh.read(), self.B.read("books/italian/storia/ch1.tex"))

    def test_accept_off_never_takes(self):
        self.switch(self.A, accept=False)
        jid = self.ask_build()
        self.step(self.B, 4)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "waiting")
        with self.on(self.A):
            self.assertEqual(J.jobs(), [])
            self.assertFalse(J.capabilities()["accepts"])

    def test_a_job_waits_while_nobody_is_reachable_and_never_fails_for_it(self):
        jid = self.ask_build()
        self.w.reachable[self.A.id] = False
        J.DEADLINE = 0.0
        self.step(self.B, 5)
        st = self.state(self.B, jid)
        self.assertEqual((st["state"], st["say"]), ("waiting", "waiting for a computer"))
        self.w.reachable[self.A.id] = True
        self.step(self.B, 4)
        self.assertEqual(self.state(self.B, jid)["state"], "done")

    def test_a_partner_silent_after_taking_gives_the_job_back_after_the_deadline(self):
        J.INLINE = False
        J.RUNNERS["book-build"] = lambda rec, say: self.release.wait(30)
        with self.on(self.A):
            X.sync_from(self.B.id)                    # A holds the book already: no retry
        jid = self.ask_build()
        self.step(self.B)
        self.assertEqual(self.state(self.B, jid)["state"], "taken")
        self.assertEqual(self.state(self.B, jid)["say"].split(":")[0], "on A")
        self.step(self.B)                             # A answers: still running
        self.assertEqual(self.state(self.B, jid)["state"], "taken")
        self.w.reachable[self.A.id] = False
        J.DEADLINE = 0.2
        self.step(self.B)
        self.assertEqual(self.state(self.B, jid)["state"], "taken", "not before the deadline")
        time.sleep(0.3)
        self.step(self.B)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "waiting")
        self.assertIn("A went silent", st["say"])
        with self.on(self.A):
            self.assertEqual(len(J.jobs()), 1, "A still thinks it has it")
        self.w.reachable[self.A.id] = True
        del self.w.calls[:]
        self.step(self.B)                             # the drop reaches A first, then it is offered again
        ops = [c[2] for c in self.w.calls if c[2] in ("jobs.drop", "jobs.offer")]
        self.assertEqual(ops, ["jobs.drop", "jobs.offer"], "A was told it no longer had it")
        self.assertEqual(self.state(self.B, jid)["state"], "taken")

    def test_cancel_takes_the_job_back(self):
        J.INLINE = False
        J.RUNNERS["book-build"] = lambda rec, say: self.release.wait(30)
        with self.on(self.A):
            X.sync_from(self.B.id)
        jid = self.ask_build()
        self.step(self.B)
        with self.on(self.B):
            self.assertEqual([j["id"] for j in J.waiting_here()], [jid])
            self.assertEqual(J.cancel(jid), {"ok": True})
            self.assertEqual(J.waiting_here(), [])
        self.step(self.B)
        with self.on(self.A):
            self.assertEqual(J.jobs(), [])

    def test_a_failure_comes_back_in_words(self):
        def broken(rec, say):
            raise J.JobFailed("the build failed on A: ! Undefined control sequence")
        J.RUNNERS["book-build"] = broken
        jid = self.ask_build()
        self.step(self.B, 4)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "failed")
        self.assertIn("Undefined control sequence", st["reason"])

    def test_estimate_by_the_sound_on_a_partner(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("no NumPy")
        values = [0.0] * 50 + [1.0] * 50 + [0.0] * 50 + [1.0] * 50 + [0.0] * 50
        args = {"kind": "point", "start": 10.0, "end": 12.5, "texts": ["uno due", "tre quattro"],
                "values": values, "times": None}
        with self.on(self.B):
            self.assertFalse(J.can_here("estimate", args)[0])
            jid = J.ask("estimate", args, "Estimate")["id"]
        self.step(self.B, 3)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "done", st)
        self.assertEqual(len(st["result"]["pieces"]), 2)


class OneTakes(Jobs):
    names = ("A", "B", "C")

    def test_exactly_one_partner_takes_a_job(self):
        J.CAPS_FORCE[self.C.id] = dict(CAN)
        self.switch(self.B, send=True)
        self.switch(self.A, accept=True)
        self.switch(self.C, accept=True)
        book(self.B)
        for inst in (self.A, self.C):
            with self.on(inst):
                X.sync_from(self.B.id)
        jid = self.ask_build()
        self.step(self.B, 4)
        self.assertEqual(self.state(self.B, jid)["state"], "done")
        took = [c for c in self.w.calls if c[2] == "jobs.offer"]
        self.assertEqual(len(took), 1, took)


if __name__ == "__main__":
    unittest.main(verbosity=2)
