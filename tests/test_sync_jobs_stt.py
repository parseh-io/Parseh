#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A transcription lent by its sound (lib/syncjobs.py kind "transcribe",
lib/sttjobs.py lend_ask / lend_look / run_lent; a0.7.0 lane D2).

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_jobs_stt.py

Two installs in one process (tests/syncfake.py).  B has no Whisper and "send"
on; A has one and "accept" on.  B's add-page job takes the recording exactly
as it does today (sttjobs.audio, in pieces); the recording travels to A
(jobs.input, by sha256, in pieces); A runs the add page's OWN pipeline on it
(sttjobs.run_lent: the real lib/sttworker.py, with the faster-whisper stand-in
of tests/fixtures/stt_runtime through tests/stt_fakes.py -- WHISPER IS THE
ONE THING FAKED); the finished job comes back (jobs.blob) and B takes it into
its usual review (sttjobs.result), word times included.

sttjobs keeps its jobs in one table and the pending reviews under
ytpages.VIDEOS: each install gets its own of both here (Install.apply), as two
processes would have.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "youtube", "lib"))
import syncfake                 # noqa: E402
import stt_fakes                # noqa: E402
from test_sync_jobs import Jobs  # noqa: E402
import syncjobs as J            # noqa: E402
import sttjobs                  # noqa: E402
import wordtimes                # noqa: E402
import ytpages                  # noqa: E402

TURBO = "large-v3-turbo"
YT = "dQw4w9WgXcQ"
PERSIAN = [[0.0, 2.0, " سلام دنیا"], [2.5, 4.0, " خداحافظ"]]


class Lent(Jobs):
    def setUp(self):
        super().setUp()
        self.addCleanup(self.ends)
        self.root = tempfile.mkdtemp(prefix="sync-stt-", dir=os.environ.get("TMPDIR"))
        self.addCleanup(shutil.rmtree, self.root, True)
        held = stt_fakes.installed(self.root)
        held.__enter__()
        self.addCleanup(held.__exit__, None, None, None)
        stt_fakes.configure(self.root, fake={"segments": PERSIAN})
        # each install its own job table and pending reviews, as two processes have
        self.tables = {}
        was = (sttjobs.JOBS, sttjobs.TOMBS, ytpages.VIDEOS)
        real_apply = syncfake.Install.apply

        def apply(inst):
            real_apply(inst)
            sttjobs.JOBS, sttjobs.TOMBS = self.tables.setdefault(inst.name, ({}, {}))
            ytpages.VIDEOS = inst.p("youtube/videos")
        patcher = mock.patch.object(syncfake.Install, "apply", apply)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: (setattr(sttjobs, "JOBS", was[0]), setattr(sttjobs, "TOMBS", was[1]),
                                 setattr(ytpages, "VIDEOS", was[2])))
        # no thread of sttjobs' own on the asker: the test takes its steps itself
        real_launch = sttjobs._launch
        launch = mock.patch.object(sttjobs, "_launch",
                                   lambda job: None if job.get("lend") else real_launch(job))
        launch.start()
        self.addCleanup(launch.stop)
        J.CAPS_FORCE[self.A.id] = {"whisper": [TURBO]}
        J.CAPS_FORCE[self.B.id] = {"whisper": []}
        self.switch(self.A, accept=True)
        self.switch(self.B, send=True)

    def ends(self):
        sttjobs.stop_all()
        for table, _tombs in self.tables.values():
            table.clear()

    # ----- B records, as the add page does
    def record(self, seconds=5, marks=None):
        with self.on(self.B):
            got = sttjobs.start({"kind": "youtube", "id": YT}, "fa", TURBO, "auto", lend_to=self.A.id)
            self.assertEqual(got["lent"], {"to": self.A.id})
            tok = got["job"]
            if marks:
                sttjobs.marks(tok, marks)
            pcm = stt_fakes.pcm(seconds)
            half = (len(pcm) // 4) * 2
            sttjobs.audio(tok, 0, pcm[:half], False)
            self.assertEqual(sttjobs.audio(tok, half // 2, pcm[half:], True)["state"], "queued")
            job = sttjobs.JOBS[tok]
            with open(job["pcm"], "rb") as fh:
                self.sent = hashlib.sha256(fh.read()).hexdigest()
            self.assertTrue(sttjobs.lend_ask(job))
            return tok, job

    def look(self, job):
        with self.on(self.B):
            return sttjobs.lend_look(job)

    def status(self, tok):
        with self.on(self.B):
            return sttjobs.status(tok)


class LentTranscription(Lent):
    def test_the_recording_travels_and_the_transcript_comes_back_into_the_review(self):
        tok, job = self.record(marks=[[0, 0.0], [16000 * 4, 4.0]])
        self.assertFalse(self.look(job))
        self.assertEqual(self.status(tok)["say"], "Waiting for a computer…")
        got_input = []
        real = J._pull_inputs

        def pulled(rec, say):
            files = real(rec, say)
            with open(files["audio.pcm"], "rb") as fh:
                got_input.append(hashlib.sha256(fh.read()).hexdigest())
            return files
        with mock.patch.object(J, "_pull_inputs", pulled):
            self.step(self.B)                          # offered to A, taken, run there (INLINE)
        self.assertEqual(got_input, [self.sent], "the very recording reached A")
        ops = [c[2] for c in self.w.calls]
        self.assertIn("jobs.input", ops)
        self.step(self.B)                              # A says done: the transcript comes back
        self.assertTrue(self.look(job))
        with self.on(self.B):
            st = sttjobs.status(tok)
            self.assertEqual(st["state"], "done", st)
            res = sttjobs.result(tok)
        self.assertIn("سلام", res["text"])
        self.assertIn("Transcribed on A.", res["notes"])
        self.assertTrue(res["words"]["held"], res["words"])
        self.assertGreater(res["words"]["count"], 0)
        self.assertTrue(res["review"]["evidence"])
        with self.on(self.B):
            doc = wordtimes.load(tok)
            self.assertEqual(doc["job"], tok)
            self.assertTrue(all(a["id"].startswith("w:%s:" % tok) for a in doc["atoms"]))
            pending = os.path.join(ytpages.VIDEOS, ".pending-transcriptions")
            self.assertTrue(os.path.isfile(os.path.join(pending, tok + ".json")), "the review is kept here")
            self.assertTrue(os.path.isfile(os.path.join(pending, tok + ".pcm")), "and its recording")
        # A keeps nothing of it: no job, no review, no word times, no files once B has it
        self.step(self.B)                              # the drop
        self.assertEqual(self.tables["A"][0], {})
        with self.on(self.A):
            self.assertFalse(os.path.isdir(os.path.join(ytpages.VIDEOS, ".pending-transcriptions"))
                             and os.listdir(os.path.join(ytpages.VIDEOS, ".pending-transcriptions")))
            self.assertFalse(os.path.isdir(J._files_dir(job["lend"]["job"])))
            self.assertEqual(J.jobs(), [])

    def test_it_waits_while_nobody_is_reachable_and_never_fails_for_it(self):
        tok, job = self.record()
        self.w.reachable[self.A.id] = False
        J.DEADLINE = 0.0
        self.step(self.B, 4)
        self.assertFalse(self.look(job))
        self.assertEqual(self.status(tok)["state"], "queued")
        self.assertTrue(self.status(tok)["say"].startswith("Waiting for a computer"))
        self.w.reachable[self.A.id] = True
        self.step(self.B, 3)
        self.assertTrue(self.look(job))
        self.assertEqual(self.status(tok)["state"], "done")

    def test_a_failure_on_A_comes_back_in_words(self):
        J.RUNNERS["transcribe"] = lambda rec, say: (_ for _ in ()).throw(
            J.JobFailed("this computer cannot transcribe: the model large-v3-turbo is not installed"))
        tok, job = self.record()
        self.step(self.B, 3)
        self.assertTrue(self.look(job))
        st = self.status(tok)
        self.assertEqual(st["state"], "failed")
        self.assertIn("model large-v3-turbo is not installed", st["error"])

    def test_cancel_here_takes_the_job_back(self):
        tok, job = self.record()
        with self.on(self.B):
            sttjobs.cancel(tok)
        self.assertTrue(self.look(job))
        with self.on(self.B):
            self.assertEqual(J.view(job["lend"]["job"])["state"], "cancelled")

    def test_a_film_on_this_computer_is_sent_whole(self):
        film = stt_fakes.write_wav(os.path.join(self.w.B.root, "talk.wav"), 4)
        with self.on(self.B):
            got = sttjobs.start({"kind": "film", "path": film}, "fa", TURBO, "auto", lend_to=self.A.id)
            job = sttjobs.JOBS[got["job"]]
            self.assertTrue(sttjobs.lend_ask(job))
        self.step(self.B, 2)
        self.assertTrue(self.look(job))
        with self.on(self.B):
            res = sttjobs.result(got["job"])
            self.assertIn("سلام", res["text"])
            self.assertEqual(sttjobs.review_media(got["job"]), film, "the review plays the film here")


class PartnerSide(Lent):
    def test_the_partner_runs_its_own_pipeline_and_keeps_nothing(self):
        pcm_path = os.path.join(self.w.A.root, "in.pcm")
        with open(pcm_path, "wb") as fh:
            fh.write(stt_fakes.pcm(5))
        out = os.path.join(self.w.A.root, "out")
        os.makedirs(out)
        rec = {"args": {"lang": "fa", "model": TURBO, "exact": True, "duration": 5,
                        "source": {"kind": "youtube", "id": YT}, "marks": []},
               "asked_by_name": "B", "state": "taken"}
        said = []
        with self.on(self.A):
            got = sttjobs.run_lent(rec, {"audio.pcm": pcm_path}, out, said.append, lambda: False)
            self.assertEqual(sttjobs.JOBS, {})
            self.assertFalse(os.path.exists(os.path.join(ytpages.VIDEOS, ".pending-transcriptions")))
        with open(got["outputs"]["transcript.json"], encoding="utf-8") as fh:
            record = json.load(fh)
        self.assertIn("سلام", record["job"]["text"])
        self.assertTrue(record["timings"]["atoms"])
        self.assertEqual(got["result"]["captions"], 2)
        self.assertTrue(said)


if __name__ == "__main__":
    unittest.main(verbosity=2)
