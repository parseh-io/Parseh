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


TEX_ENGINES = ("xelatex", "lualatex", "pdflatex", "xetex", "luatex", "pdftex")


def path_without_tex(base):
    """This test's PATH with every TeX engine left out: each folder that holds
    one is replaced, at its own place, by a folder of links to everything else
    it holds -- a computer without TeX, for the studio's build as for the
    drawings (B below)."""
    out = []
    for i, d in enumerate(os.environ.get("PATH", "").split(os.pathsep)):
        if not d or not any(os.path.exists(os.path.join(d, t)) for t in TEX_ENGINES):
            out.append(d)
            continue
        shadow = os.path.join(base, "notex-%d" % i)
        os.makedirs(shadow)
        for n in os.listdir(d):
            if n not in TEX_ENGINES:
                os.symlink(os.path.join(d, n), os.path.join(shadow, n))
        out.append(shadow)
    return os.pathsep.join(out)


def find(tree, name):
    for here, _dirs, files in os.walk(tree):
        if name in files:
            return os.path.join(here, name)
    return None


class LatexJobsEndToEnd(unittest.TestCase):
    """A studio document's PDF and the LaTeX drawings no computer made, lent
    between two REAL installs (lane J: "doc-build", "latex-draw").  B has NO
    TeX at all: its PATH holds no TeX engine and latexdraw finds no compiler
    (SYNC_BUILDS_FAKE "no_tex").  A has its real TeX, except that -- as in
    tests/test_sync_builds_end_to_end.py -- its XeLaTeX for a document's PDF is
    a script that writes a real one-page PDF where xelatex would; the studio's
    build_pdf, its checks and its record are the real ones.  A's DRAWINGS are
    made by A's real TeX (the default theme's compiler).  Everything else is real: the studio's doors on
    B (build, drawings, drawings/lend) with and without send_to, the offer,
    A holding B's document, the files back, meta.json back through sync."""

    @classmethod
    def setUpClass(cls):
        from test_sync_builds_end_to_end import FAKE_XELATEX
        import stat
        cls.base = tempfile.mkdtemp(prefix="sync-jobs-latex-e2e-", dir=os.environ.get("TMPDIR"))
        fakebin = os.path.join(cls.base, "fakebin")
        os.makedirs(fakebin)
        real = shutil.which("xelatex")
        with open(os.path.join(fakebin, "xelatex"), "w") as fh:
            fh.write(FAKE_XELATEX % (sys.executable, real, real))
        os.chmod(os.path.join(fakebin, "xelatex"), 0o755 | stat.S_IXUSR)
        fake = json.dumps({"deadline": 60, "caps_ttl": 1, "timeout": 8})
        cls.A = Install(cls.base, "A", env={"SYNC_JOBS_FAKE": fake, "SYNC_BUILDS_FAKE": json.dumps({}),
                                            "PATH": fakebin + os.pathsep + os.environ.get("PATH", "")})
        cls.B = Install(cls.base, "B", env={"SYNC_JOBS_FAKE": fake,
                                            "SYNC_BUILDS_FAKE": json.dumps({"no_tex": True}),
                                            "PATH": path_without_tex(cls.base)})
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
        switches(cls.B, send=False)
        switches(cls.A, send=False, accept=True)

    @classmethod
    def tearDownClass(cls):
        JobsEndToEnd.tearDownClass.__func__(cls)

    def job(self, jid):
        st, j = ask(self.B, "GET", "/__jobs/state?id=" + jid)
        self.assertEqual(st, 200, j)
        return j

    def make(self, title, body):
        md = "---\ntitle: %s\nlanguage: english\n---\n\n# %s\n\n%s" % (title, title, body)
        st, out = ask(self.B, "POST", "/studio/api/docs", {"markdown": md})
        self.assertIn(st, (200, 201), out)
        doc_id = out.get("id") or (out.get("meta") or {}).get("id")
        self.assertTrue(doc_id, out)
        return doc_id

    def test_1_a_documents_pdf_without_XeLaTeX_and_send_off_says_it_cannot(self):
        doc_id = self.make("Off here", "Nothing to draw.\n")
        st, out = ask(self.B, "POST", "/studio/api/docs/%s/build" % doc_id, {})
        self.assertEqual(st, 500, out)
        self.assertNotIn("jobs", out)
        self.assertIn("no XeLaTeX", out["build"]["error"])

    def test_2_a_documents_pdf_is_built_on_A_and_arrives_on_B(self):
        switches(self.B, send=True)
        doc_id = self.make("Built on A", "Words to print.\n")
        route = "/studio/api/docs/%s/build" % doc_id
        st, out = ask(self.B, "POST", route, {"scale": 1.6})
        self.assertEqual(st, 409, out)
        self.assertIn("XeLaTeX", out["error"])
        self.assertEqual([(p["id"], p["can"]) for p in out["jobs"]["send"]], [(self.A_id, True)])
        st, out = ask(self.B, "POST", route, {"scale": 1.6, "send_to": self.A_id})
        self.assertEqual(st, 202, out)
        jid = out["job"]["id"]
        until("the PDF built on A", lambda: self.job(jid)["state"] in ("done", "failed"), wait=120)
        j = self.job(jid)
        self.assertEqual((j["state"], j["taken_by"]), ("done", self.A_id), j)
        self.assertEqual(j["result"]["build"]["status"], "ok", j)
        # the PDF on B is the one A's build wrote (its stand-in XeLaTeX: a real page saying so)
        lib = os.path.join(self.B.tree, "library")
        folder = next(os.path.join(h, d) for h, ds, _f in os.walk(lib) for d in ds if d == doc_id)
        pdf = os.path.join(folder, "build", "main.pdf")
        with open(pdf, "rb") as fh:
            raw = fh.read()
        self.assertTrue(raw.startswith(b"%PDF"), raw[:20])
        import pymupdf
        with pymupdf.open(pdf) as d:
            self.assertIn("a document", d[0].get_text())
        st, served = get_raw(self.B, "/studio/pdf/%s" % doc_id)
        self.assertEqual((st, served), (200, raw))
        self.assertTrue(os.path.isfile(os.path.join(folder, "build", "main.tex")))
        # meta.json, which says it was built, came back through sync; the record names B's source as it is
        with open(os.path.join(folder, "meta.json")) as fh:
            self.assertEqual(json.load(fh)["build"]["status"], "ok")
        with open(os.path.join(folder, ".built-from.json")) as fh:
            self.assertIn("pdf", json.load(fh)["parts"])
        st, unit = ask(self.B, "POST", "/settings/api/devices/unit", {"unit": "doc:" + os.path.relpath(folder, lib)})
        self.assertEqual(st, 200, unit)
        self.assertFalse(unit.get("out_of_date"), unit)

    def test_3_a_drawing_nobody_made_is_drawn_on_A_and_shown_on_B(self):
        switches(self.B, send=False)
        doc_id = self.make("Drawn on A", "::::latex\n\\(x^3 + 7y = \\frac{1}{2}\\)\n::::\n")
        draws = "/studio/api/docs/%s/drawings" % doc_id
        st, page = ask(self.B, "POST", draws, {})
        self.assertEqual(st, 200, page)
        self.assertIn('data-latex-kind="compiler"', page["html"])
        self.assertIn("which this computer does not have", page["html"])
        # "send" off: nothing to offer, and asking says why
        st, look = ask(self.B, "POST", draws + "/lend", {"look": True})
        self.assertEqual((st, look["send"], look["missing"]), (200, False, 1), look)
        st, out = ask(self.B, "POST", draws + "/lend", {})
        self.assertEqual(st, 409, out)
        self.assertNotIn("jobs", out)
        switches(self.B, send=True)
        st, look = ask(self.B, "POST", draws + "/lend", {"look": True})
        self.assertEqual((st, look["send"], look["missing"]), (200, True, 1), look)
        st, out = ask(self.B, "POST", draws + "/lend", {})
        self.assertEqual(st, 409, out)
        self.assertIn("cannot be made here", out["error"])
        self.assertEqual([(p["id"], p["can"]) for p in out["jobs"]["send"]], [(self.A_id, True)])
        st, out = ask(self.B, "POST", draws + "/lend", {"send_to": self.A_id})
        self.assertEqual(st, 202, out)
        jid = out["job"]["id"]
        until("the drawing made on A", lambda: self.job(jid)["state"] in ("done", "failed"), wait=120)
        j = self.job(jid)
        self.assertEqual((j["state"], j["taken_by"]), ("done", self.A_id), j)
        (ck, made), = j["result"]["drawn"].items()
        # B's page now shows the drawing A made, found by its content
        st, page = ask(self.B, "POST", draws, {})
        self.assertEqual(st, 200, page)
        self.assertNotIn('data-latex-kind="compiler"', page["html"])
        self.assertIn("/latex/%s.svg" % made["key"], page["html"])
        st, svg = get_raw(self.B, "/latex/%s.svg" % made["key"])
        self.assertEqual(st, 200)
        self.assertIn(b"<svg", svg)
        with open(find(self.A.tree, made["key"] + ".svg"), "rb") as fh:
            self.assertEqual(svg, fh.read(), "the very drawing A's TeX made")
        st, look = ask(self.B, "POST", draws + "/lend", {"look": True})
        self.assertEqual(look["missing"], 0, look)


def get_raw(inst, route):
    import http.client
    c = http.client.HTTPConnection("127.0.0.1", inst.port, timeout=30)
    try:
        c.request("GET", route, headers={"Host": "localhost:%d" % inst.port})
        r = c.getresponse()
        return r.status, r.read()
    finally:
        c.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
