#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A transcription lent by its sound, between two REAL installs paired over
real TLS (lib/syncjobs.py "transcribe", lib/sttjobs.py; a0.7.0 lane D2).

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_jobs_stt_end_to_end.py

Each install is a serve.py process in its own temporary tree
(tests/sync_harness.py).  B has no speech to text and "send" on; A has it and
"accept" on.  WHISPER IS THE ONE THING FAKED: SYNC_JOBS_FAKE "stt" makes each
install's getstt tests/addstt_fakes.py's, so A runs the real job and the real
lib/sttworker.py with the faster-whisper stand-in of tests/fixtures/stt_runtime.
Everything else is real: the add page's doors on B (start: 409 with
jobs.send, then send_to: 202; audio in pieces; status; result), the recording
fetched by A over pinned TLS (jobs.input), A's own pipeline, the transcript
back (jobs.blob) and into B's review.

  1. the recording goes to A and the transcript comes back into B's review,
     word times included; A keeps nothing of it;
  2. A frozen (SIGSTOP) while it works: B gives the job back after the
     deadline, says "waiting for a computer", never fails for it, and once A
     runs again the transcript arrives.
"""
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
from test_sync_end_to_end import ask  # noqa: E402
from test_sync_jobs_end_to_end import switches, until, doing  # noqa: E402
import stt_fakes  # noqa: E402

TURBO = "large-v3-turbo"
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
SEGMENTS = [[0.0, 1.5, " uno due tre"], [2.0, 3.5, " quattro cinque"]]
FAKE = {"deadline": 6, "caps_ttl": 1, "timeout": 4}


def pcm_in(inst, job, data, piece=64000):
    """The capture's pieces, as the add page sends them (audio?job=&offset=)."""
    off = 0
    while off < len(data):
        part = data[off:off + piece]
        last = off + len(part) >= len(data)
        c = http.client.HTTPConnection("127.0.0.1", inst.port, timeout=30)
        origin = "http://localhost:%d" % inst.port
        c.request("POST", "/youtube/api/transcribe/audio?job=%s&offset=%d%s" % (job, off // 2, "&last=1" if last else ""),
                  body=part, headers={"Content-Type": "application/octet-stream", "Origin": origin,
                                      "Referer": origin + "/", "Host": "localhost:%d" % inst.port})
        r = c.getresponse()
        got = json.loads(r.read() or b"{}")
        c.close()
        assert r.status == 200, got
        off += len(part)
    return got


class SttEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-stt-e2e-", dir=os.environ.get("TMPDIR"))
        can = dict(FAKE, stt={"runtime": True, "models": [TURBO], "segments": SEGMENTS})
        cannot = dict(FAKE, stt={"runtime": False, "models": []})
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
            cls.A_name = out["partner"].get("name") or cls.A_id
        except Exception:
            cls.tearDownClass()
            raise
        switches(cls.B, send=True)
        switches(cls.A, send=False, accept=True)

    @classmethod
    def tearDownClass(cls):
        for i in (getattr(cls, "A", None), getattr(cls, "B", None)):
            if i:
                with __import__("contextlib").suppress(OSError):
                    os.kill(i.proc.pid, signal.SIGCONT)
                i.stop()
        if os.environ.get("KEEP_SYNC_E2E"):
            print("trees kept in", cls.base)
        else:
            shutil.rmtree(cls.base, ignore_errors=True)

    def status(self, job):
        st, s = ask(self.B, "POST", "/youtube/api/transcribe/status", {"job": job})
        self.assertEqual(st, 200, s)
        return s

    def lend(self):
        body = {"source": "youtube", "url": URL, "lang": "it", "model": TURBO, "processing": "auto"}
        st, out = ask(self.B, "POST", "/youtube/api/transcribe/start", body)
        self.assertEqual(st, 409, out)
        self.assertEqual(out["code"], "not-installed")
        self.assertEqual([(p["id"], p["can"]) for p in out["jobs"]["send"]], [(self.A_id, True)])
        st, slim = ask(self.B, "POST", "/lookup/api/speech", {})
        self.assertEqual([(p["id"], p["models"]) for p in slim["lend"]], [(self.A_id, [TURBO])], slim)
        st, out = ask(self.B, "POST", "/youtube/api/transcribe/start", dict(body, send_to=self.A_id))
        self.assertEqual(st, 202, out)
        self.assertEqual(out["lent"], {"to": self.A_id})
        self.assertEqual(out["need"], "audio")
        return out["job"]

    def test_1_the_recording_goes_to_A_and_the_transcript_comes_back_into_Bs_review(self):
        job = self.lend()
        st, out = ask(self.B, "POST", "/youtube/api/transcribe/marks",
                      {"job": job, "marks": [[0, 0.0], [16000 * 4, 4.0]]})
        self.assertEqual(st, 200, out)
        self.assertEqual(pcm_in(self.B, job, stt_fakes.pcm(4))["state"], "queued")
        said = set()

        def done():
            s = self.status(job)
            said.add(s["say"].split(":")[0])
            self.assertNotEqual(s["state"], "failed", s)
            return s["state"] == "done"
        until("the transcript back on B", done, wait=120)
        self.assertTrue(any(x.startswith("On " + self.A_name) for x in said), said)
        st, res = ask(self.B, "POST", "/youtube/api/transcribe/result", {"job": job})
        self.assertEqual(st, 200, res)
        self.assertIn("uno due tre", res["text"])
        self.assertIn("quattro cinque", res["text"])
        self.assertIn("Transcribed on %s." % self.A_name, res["notes"])
        self.assertTrue(res["words"]["held"])
        self.assertTrue(res["review"]["evidence"])
        pending = os.path.join(self.B.tree, "root", "youtube", "videos", ".pending-transcriptions")
        self.assertTrue(os.path.isfile(os.path.join(pending, job + ".json")))
        self.assertTrue(os.path.isfile(os.path.join(pending, job + ".pcm")))
        # A keeps nothing of it once B has it
        until("A forgot the job", lambda: doing(self.A) == {}, wait=30)
        a_pending = os.path.join(self.A.tree, "root", "youtube", "videos", ".pending-transcriptions")
        self.assertFalse(os.path.isdir(a_pending) and os.listdir(a_pending))
        self.assertFalse(os.listdir(os.path.join(self.A.tree, "config", "sync", "jobs"))
                         if os.path.isdir(os.path.join(self.A.tree, "config", "sync", "jobs")) else [])

    def test_2_A_frozen_gives_the_job_back_and_it_waits(self):
        # A's Whisper is slow now: two seconds between segments
        cfg = os.path.join(self.A.tree, "sttfake", "fake.json")
        with open(cfg) as fh:
            fake = json.load(fh)
        with open(cfg, "w") as fh:
            json.dump(dict(fake, delay=3), fh)
        job = self.lend()
        pcm_in(self.B, job, stt_fakes.pcm(4))
        until("on A", lambda: self.status(job)["say"].startswith("On " + self.A_name), wait=60)
        os.kill(self.A.proc.pid, signal.SIGSTOP)
        try:
            t0 = time.time()
            until("given back", lambda: self.status(job)["say"].startswith("Waiting for a computer"), wait=60)
            self.assertGreaterEqual(time.time() - t0, FAKE["deadline"] - 1)
            self.assertIn("went silent", self.status(job)["say"])
            time.sleep(12)                     # nobody reachable: it waits, and never fails for it
            s = self.status(job)
            self.assertEqual(s["state"], "queued", s)
        finally:
            os.kill(self.A.proc.pid, signal.SIGCONT)
        with open(cfg, "w") as fh:
            json.dump(fake, fh)
        until("the transcript once A runs again", lambda: self.status(job)["state"] == "done", wait=180)
        st, res = ask(self.B, "POST", "/youtube/api/transcribe/result", {"job": job})
        self.assertIn("uno due tre", res["text"])


class AlignerEndToEnd(unittest.TestCase):
    """a0.7.0 lane G: A transcribes with its own Whisper but has no aligner for
    Italian; B has one ("aligners" in its capabilities, its runner a stand-in
    for lib/ctcalign.py).  The add page's door offers "Send to B" for the exact
    word times; the transcription runs on A, the alignment on B."""

    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-align-e2e-", dir=os.environ.get("TMPDIR"))
        whisper = dict(FAKE, stt={"runtime": True, "models": [TURBO], "segments": SEGMENTS})
        aligner = dict(FAKE, caps={"aligners": ["it"]}, words=True, stt={"runtime": False, "models": []})
        cls.A = Install(cls.base, "A", env={"SYNC_JOBS_FAKE": json.dumps(whisper)})
        cls.B = Install(cls.base, "B", env={"SYNC_JOBS_FAKE": json.dumps(aligner)})
        try:
            cls.A.wait()
            cls.B.wait()
            st, offer = cls.B.dev("pair-start")
            assert st == 200, offer
            st, out = cls.A.dev("pair-enter", {"code": offer["said"], "address": "127.0.0.1:%d" % cls.B.port,
                                               "fingerprint": offer["fingerprint"]})
            assert st == 200, out
            cls.B_id = out["partner"]["id"]
            cls.B_name = out["partner"].get("name") or cls.B_id
        except Exception:
            cls.tearDownClass()
            raise
        switches(cls.A, send=True)
        switches(cls.B, send=False, accept=True)

    @classmethod
    def tearDownClass(cls):
        for i in (getattr(cls, "A", None), getattr(cls, "B", None)):
            if i:
                i.stop()
        if os.environ.get("KEEP_SYNC_E2E"):
            print("trees kept in", cls.base)
        else:
            shutil.rmtree(cls.base, ignore_errors=True)

    def test_exact_word_times_are_made_on_B_and_come_back_into_As_review(self):
        body = {"source": "youtube", "url": URL, "lang": "it", "model": TURBO, "processing": "auto",
                "exact": True}
        st, out = ask(self.A, "POST", "/youtube/api/transcribe/start", body)
        self.assertEqual(st, 409, out)
        self.assertEqual(out["code"], "aligner-elsewhere")
        self.assertEqual(out["jobs"]["kind"], "word-align")
        self.assertEqual([(p["id"], p["can"]) for p in out["jobs"]["send"]], [(self.B_id, True)])
        st, out = ask(self.A, "POST", "/youtube/api/transcribe/start", dict(body, send_to=self.B_id))
        self.assertEqual(st, 200, out)                      # the transcription itself runs here
        job = out["job"]
        pcm_in(self.A, job, stt_fakes.pcm(4))
        said = set()

        def done():
            st, s = ask(self.A, "POST", "/youtube/api/transcribe/status", {"job": job})
            said.add(s.get("say", "").split(":")[0])
            self.assertNotEqual(s["state"], "failed", s)
            return s["state"] == "done"
        until("the transcript with B's word times", done, wait=120)
        self.assertIn("Making exact word times", said)
        st, res = ask(self.A, "POST", "/youtube/api/transcribe/result", {"job": job})
        self.assertEqual(st, 200, res)
        self.assertIn("uno due tre", res["text"])
        self.assertIn("Exact word times made on %s." % self.B_name, res["notes"])
        self.assertEqual(res["words"].get("source"), "aligner", res["words"])
        self.assertTrue(res["words"]["held"])
        # "Not now": the same transcription with Whisper's own times, no question
        st, out = ask(self.A, "POST", "/youtube/api/transcribe/start", dict(body, align_here=True))
        self.assertEqual(st, 200, out)
        ask(self.A, "POST", "/youtube/api/transcribe/cancel", {"job": out["job"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
