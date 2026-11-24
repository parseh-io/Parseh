#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A job lent between two REAL installs, paired over real TLS (lib/syncjobs.py, lane D).

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_jobs_end_to_end.py

Each install is a serve.py process in its own temporary tree
(tests/sync_harness.py).  B has "send" on and cannot build a book's PDF; A can,
and its "accept" starts off.  THE BUILD ITSELF IS FAKED (SYNC_JOBS_FAKE: a
runner that waits, then writes a PDF and a reader, as ./build.sh would) and
the capabilities are set by the harness; everything else is real: the page's
door (__build, with and without send_to), the job's ops over pinned TLS, the
exchange that brings B's book to A, the output files back, __build/status.

  1. accept off on A: the job is never taken;
  2. accept on: A takes it, the PDF and the reader arrive on B, and the page's
     __build/status says "done";
  3. A frozen (SIGSTOP) after taking a second job: B gives it back after the
     deadline, the job then waits while nobody can be reached and never fails,
     and once A runs again it is taken and done.
"""
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
from test_sync_end_to_end import ask  # noqa: E402

BOOK = "/books/italian/storia"
FAKE = {"deadline": 6, "caps_ttl": 1, "timeout": 4, "run_seconds": 8}


def until(what, test, wait=90):
    end = time.time() + wait
    while time.time() < end:
        got = test()
        if got:
            return got
        time.sleep(0.5)
    raise AssertionError("waited %d s: %s" % (wait, what))


def switches(inst, **kw):
    path = os.path.join(inst.tree, "config", "sync", "jobs-switches.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(kw, fh)


def doing(inst):
    try:
        with open(os.path.join(inst.tree, "config", "sync", "jobs.json")) as fh:
            return json.load(fh).get("doing", {})
    except (OSError, ValueError):
        return {}


class JobsEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-jobs-e2e-")
        can = dict(FAKE, caps={"latex": True, "reader": True})
        cannot = dict(FAKE, caps={"latex": False, "reader": True, "estimate": False}, no_numpy=True)
        cls.A = Install(cls.base, "A", env={"SYNC_JOBS_FAKE": json.dumps(can)})
        cls.B = Install(cls.base, "B", env={"SYNC_JOBS_FAKE": json.dumps(cannot)})
        try:
            cls.A.wait()
            cls.B.wait()
            st, offer = cls.A.dev("pair-start")
            assert st == 200, offer
            st, out = cls.B.dev("pair-enter", {"code": offer["said"], "address": "127.0.0.1:%d" % cls.A.port,
                                               "fingerprint": offer["fingerprint"]})
            assert st == 200, out
            cls.A_id = out["partner"]["id"]
        except Exception:
            cls.tearDownClass()
            raise
        switches(cls.B, send=True)
        switches(cls.A, send=False, accept=False)
        d = os.path.join(cls.B.tree, "root", "books", "italian", "storia")
        os.makedirs(d)
        with open(os.path.join(d, "book.json"), "w") as fh:
            json.dump({"title": "Storia", "language": "italian"}, fh)
        with open(os.path.join(d, "ch1.tex"), "w") as fh:
            fh.write("Una storia.\n")

    @classmethod
    def tearDownClass(cls):
        for i in (getattr(cls, "A", None), getattr(cls, "B", None)):
            if i:
                i.stop()
        if os.environ.get("KEEP_SYNC_E2E"):
            print("trees kept in", cls.base)
        else:
            shutil.rmtree(cls.base, ignore_errors=True)

    def job(self, jid):
        st, j = ask(self.B, "GET", "/__jobs/state?id=" + jid)
        self.assertEqual(st, 200, j)
        return j

    def lend(self):
        st, out = ask(self.B, "POST", BOOK + "/__build", {"what": "pdf"})
        self.assertEqual(st, 409, out)
        self.assertIn("LaTeX", out["error"])
        self.assertEqual([p["id"] for p in out["jobs"]["send"]], [self.A_id])
        st, out = ask(self.B, "POST", BOOK + "/__build", {"what": "pdf", "send_to": self.A_id})
        self.assertEqual(st, 202, out)
        self.assertEqual(out["job"]["say"], "waiting for a computer")
        return out["job"]["id"]

    def test_1_accept_off_never_takes(self):
        jid = self.lend()
        type(self).first = jid
        time.sleep(12)
        j = self.job(jid)
        self.assertEqual(j["state"], "waiting", j)
        self.assertEqual(doing(self.A), {})

    def test_2_accept_on_the_job_is_taken_and_its_result_arrives_on_B(self):
        switches(self.A, accept=True)
        jid = self.first
        until("the job done", lambda: self.job(jid)["state"] == "done")
        j = self.job(jid)
        self.assertEqual(j["taken_by"], self.A_id)
        pdf = os.path.join(self.B.tree, "root", "books", "italian", "storia", "storia.pdf")
        with open(pdf, "rb") as fh:
            self.assertEqual(fh.read(), b"%PDF-1.5 built by " + self.A_id.encode() + b"\n")
        reader = os.path.join(os.path.dirname(pdf), "reader", "index.html")
        with open(reader) as fh:
            self.assertIn(self.A_id, fh.read())
        st, s = ask(self.B, "GET", BOOK + "/__build/status")
        self.assertEqual((st, s["state"]), (200, "done"), s)
        self.assertTrue(os.path.isfile(os.path.join(self.A.tree, "root", "books", "italian", "storia",
                                                    "ch1.tex")), "A held the book before building it")
        st, act = ask(self.B, "GET", "/__activity")
        mine = [e for e in act.get("finished", []) if e.get("id") == "job-" + jid]
        self.assertEqual([(e["kind"], e["ok"]) for e in mine], [("job", True)], act)

    def test_3_a_frozen_partner_gives_the_job_back_and_the_job_waits(self):
        jid = self.lend()
        until("on A", lambda: self.job(jid)["state"] == "taken")
        os.kill(self.A.proc.pid, signal.SIGSTOP)
        try:
            t0 = time.time()
            until("given back", lambda: self.job(jid)["state"] == "waiting", wait=60)
            self.assertGreaterEqual(time.time() - t0, FAKE["deadline"] - 1)
            self.assertIn("went silent", self.job(jid)["say"])
            time.sleep(15)                     # nobody reachable: it waits, and never fails for it
            j = self.job(jid)
            self.assertEqual(j["state"], "waiting", j)
        finally:
            os.kill(self.A.proc.pid, signal.SIGCONT)
        until("done once A runs again", lambda: self.job(jid)["state"] == "done", wait=120)


    def test_4_an_estimate_by_the_sound_made_on_A(self):
        d = os.path.join(self.B.tree, "root", "youtube", "videos", "italian", "abcdefghijk")
        os.makedirs(d)
        with open(os.path.join(d, "video.json"), "w") as fh:
            json.dump({"id": "abcdefghijk", "title": "V", "language": "it"}, fh)
        peaks = ([0.0] * 50 + [0.9] * 70 + [0.0] * 40 + [0.9] * 70 + [0.0] * 20)
        body = {"video": "abcdefghijk", "start": 0, "end": 2.5, "kind": "point",
                "texts": ["uno due tre", "quattro cinque"], "wave": {"rate": 100, "start": 0, "peaks": peaks}}
        st, out = ask(self.B, "POST", "/youtube/api/estimate", body)
        self.assertEqual(st, 409, out)
        self.assertIn("numpy", out["error"])
        st, out = ask(self.B, "POST", "/youtube/api/estimate", dict(body, send_to=self.A_id))
        self.assertEqual(st, 202, out)
        jid = out["job"]["id"]
        until("the estimate done", lambda: self.job(jid)["state"] == "done", wait=60)
        res = self.job(jid)["result"]
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(len(res["pieces"]), 2)
        self.assertEqual((res["pieces"][0]["t0"], res["pieces"][1]["t1"]), (0, 2.5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
