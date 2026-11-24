# SPDX-License-Identifier: GPL-3.0-or-later
"""The transcription job (lib/sttjobs.py): its rules, run for real against a stand-in runtime.

    python3 -m unittest tests/test_stt_jobs.py

No model, no CUDA, no PyAV.  `tests/stt_fakes.py` puts a stand-in `getstt`
(INTERFACE 1 of the a0.4.1 note) in sys.modules and a stand-in faster-whisper
on the worker's PYTHONPATH, so the job runs its REAL child process (lib/
sttworker.py) and every rule below is read off what that child did:

  brief tests   7-15  the devices, the fall back, the eleven languages
                 16   a timed result becomes text the add page's own parser reads
                 17   a film needs no browser capture
                 20   cancelling cleans up: the audio, the child, the table
                 27   28  nothing hostile reaches the model loader or the disk
plus the single slot (409 busy), the audio door (idempotent offsets, a gap,
size caps, the disk), the clock (marks), the held waveform, abandonment, a
stopped server, and that no answer ever carries a traceback.

Any device the network door let in may start a job (the owner): nothing here
asks who calls, and a film's waveform is never written.  Needs numpy, as the
worker does.
"""
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, os.path.join(ROOT, "lib"), os.path.join(ROOT, "youtube", "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import languages                                              # noqa: E402
import sttjobs                                                # noqa: E402
import stt_fakes                                              # noqa: E402
import wavefile                                               # noqa: E402
import ytpages                                                # noqa: E402
from test_stt_panel import SPEECH                             # noqa: E402

TURBO, LARGE = "large-v3-turbo", "large-v3"
PERSIAN = [[0.0, 2.0, " سلام دنیا"], [2.5, 4.0, " خداحافظ"]]
LAZY = "Library libcublas.so.12 is not found or cannot be loaded"
OOM = "CUDA failed with error out of memory"
CANCELLED_YT = "Recording was cancelled."
NO_ROOM = "There was not enough disk space to finish the capture."
YT = "dQw4w9WgXcQ"
POSIX = os.name != "nt"


def alive(pid):
    """Is a process still there (a zombie is gone)?"""
    try:
        with open("/proc/%d/stat" % pid, encoding="ascii", errors="replace") as f:
            return f.read().rsplit(")", 1)[-1].split()[0] != "Z"
    except OSError:
        return False


class Base(unittest.TestCase):
    """A stand-in getstt in a temporary root, and helpers to drive one job."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.td.cleanup)
        self.root = self.td.name
        self.videos = os.path.join(self.root, "videos")
        os.makedirs(self.videos)
        held = stt_fakes.installed(self.root)
        self.gs = held.__enter__()
        self.addCleanup(held.__exit__, None, None, None)
        moved = mock.patch.object(ytpages, "VIDEOS", self.videos)
        moved.start()
        self.addCleanup(moved.stop)
        # the worker's own stderr is printed to the server's log; here it is read
        self.log = io.StringIO()
        quiet = mock.patch.object(sys, "stderr", self.log)
        quiet.start()
        self.addCleanup(quiet.stop)
        sttjobs.JOBS.clear()
        sttjobs.TOMBS.clear()
        self.addCleanup(self.reset)

    def reset(self):
        sttjobs.stop_all()
        end = time.time() + 8
        while sttjobs.CHILDREN and time.time() < end:
            time.sleep(0.05)
        sttjobs.JOBS.clear()
        sttjobs.TOMBS.clear()
        sttjobs.CHILDREN.clear()

    # ----- the fake's state
    def fake(self, **cfg):
        stt_fakes.configure(self.root, fake=cfg)

    def records(self, kind=None):
        return stt_fakes.records(self.root, kind)

    def built(self):
        return [(r["device"], r["compute_type"]) for r in self.records("construct")]

    def heard(self):
        return [r["device"] for r in self.records("transcribe")]

    # ----- sources
    def film(self, seconds=3, name=None):
        # the first film of a test is film.mp4; a second is another file: a job
        # holds its film by its path and stat, and writing over it would be a
        # film that changed
        self.films = getattr(self, "films", 0) + 1
        name = name or ("film.mp4" if self.films == 1 else "film-%d.mp4" % self.films)
        return stt_fakes.write_wav(os.path.join(self.root, name), seconds)

    def start_film(self, lang="fa", model=TURBO, processing="cpu", seconds=3, **kw):
        return sttjobs.start({"kind": "film", "path": self.film(seconds)}, lang, model,
                             processing, **kw)

    def start_yt(self, lang="fa", model=TURBO, processing="cpu", vid=YT, **kw):
        return sttjobs.start({"kind": "youtube", "id": vid}, lang, model, processing, **kw)

    # ----- waiting
    def wait(self, token, states, timeout=40):
        end = time.time() + timeout
        s = None
        while time.time() < end:
            s = sttjobs.status(token)
            if s["state"] in states:
                return s
            time.sleep(0.03)
        self.fail("the job is still %r, wanted %r" % (s and s["state"], states))

    def done(self, token, timeout=40):
        status = self.wait(token, ("awaiting-review-choice", "done", "failed", "cancelled"), timeout)
        if status["state"] == "awaiting-review-choice":
            evidence = sttjobs.result(token)["review"]["evidence"]
            sttjobs.review(token, "whisper", evidence["source_sha256"])
            return sttjobs.status(token)
        return status

    def until(self, test, what, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            got = test()
            if got:
                return got
            time.sleep(0.03)
        self.fail("never: " + what)

    def tmp(self):
        try:
            return sorted(os.listdir(self.gs.TMP_DIR))
        except OSError:
            return []

    def settled(self):
        """The child gone and its temporary files with it (the runner tidies up a
        moment AFTER the state says done)."""
        self.until(lambda: not sttjobs.CHILDREN and not self.tmp(), "the child and its files gone")

    def refused(self, fn, *args, **kw):
        """A refusal -> (status, body); the call is failed if it was not one."""
        body, status = sttjobs.call(fn, *args, **kw)
        self.assertFalse(body["ok"], body)
        self.assertGreaterEqual(status, 400)
        self.assertEqual(sorted(k for k in ("error", "code") if k in body), ["code", "error"])
        return status, body

    def pcm(self, seconds):
        return stt_fakes.pcm(seconds)


# ============================================================ start: what is refused
class Start(Base):
    def test_a_film_job_needs_no_browser_capture(self):
        # brief test 17: a film and no audio call ever -- and it reaches done
        got = self.start_film(seconds=4)
        self.assertEqual((got["state"], got["need"], got["kind"], got["source"]),
                         ("queued", "", "film", "film"))
        self.assertEqual(got["film"], "film.mp4")
        self.assertRegex(got["job"], r"^[A-Za-z0-9_-]{16}$")
        s = self.done(got["job"])
        self.assertEqual((s["state"], s["pct"], s["done"], s["total"]), ("done", 100, 4.0, 4.0))
        self.assertEqual(s["device"], "cpu")
        (rec,) = self.records("transcribe")
        self.assertEqual((rec["samples"], rec["audio_type"]), (4 * 16000, "ndarray"))

    def test_a_youtube_job_says_it_wants_audio_and_which_video(self):
        got = self.start_yt(vid="abcdefghijk", duration=600)
        self.assertEqual((got["state"], got["need"], got["source"], got["video_id"]),
                         ("awaiting-audio", "audio", "youtube", "abcdefghijk"))
        self.assertEqual(got["say"], "Waiting for the recording to start…")

    def test_the_result_is_text_the_add_pages_own_parser_reads_in_all_eleven_languages(self):
        # brief tests 15 and 16, through the whole job and the real registry
        self.assertTrue(set(SPEECH) <= set(languages.LANGS))
        for code, (a, b) in SPEECH.items():
            with self.subTest(lang=code):
                open(os.path.join(self.root, "fake.log"), "w").close()
                self.fake(segments=[[0.0, 2.0, " " + a], [3.24, 5.0, " " + b]])
                source, lang = sttjobs.source_of({"source": "film", "path": self.film(6),
                                                  "lang": code})
                self.assertEqual(lang, code)
                job = sttjobs.start(source, lang, TURBO, "cpu")["job"]
                s = self.done(job)
                self.assertEqual(s["state"], "done", s)
                self.assertEqual(s["say"], "Done — 2 captions.")
                (rec,) = self.records("transcribe")
                self.assertEqual(rec["language"], code, "the code reached transcribe(language=)")
                got = sttjobs.result(job)
                caps = ytpages.parse_transcript_text(ytpages.as_transcript(got["text"]), code)
                self.assertEqual([c["text"] for c in caps], [a, b])
                self.assertEqual([c["start"] for c in caps], [0, 3.24])
                self.assertFalse(any(c["plain"] for c in caps))
                self.assertEqual((got["captions"], got["want"], got["plain"], got["lang"]),
                                 (2, 2, 0, code))
                self.assertEqual(got["warning"], "")
                self.settled()

    def test_a_wrong_script_is_warned_of_not_refused(self):
        self.fake(segments=[[0, 2, " hello there"], [3, 5, " and goodbye"]])
        job = self.start_film()["job"]
        self.done(job)
        got = sttjobs.result(job)
        self.assertEqual((got["captions"], got["want"]), (2, 0))
        self.assertIn("another script than Persian", got["warning"])

    def test_hostile_values_never_reach_the_model_loader_or_the_disk(self):
        # brief test 27: a model name, a path, a language, a processing mode -- of
        # every wrong kind -- is refused BEFORE the model is named, the disk is
        # touched or a job made
        film = self.film()
        good = dict(source={"kind": "film", "path": film}, lang="fa", model=TURBO,
                    processing="cpu")
        models = ["../../etc/passwd", "/etc/passwd", "large-v3\0", "large-v3-turbo ", "LARGE-V3",
                  "x" * 100000, 5, None, ["large-v3"], {"a": 1}, "large-v3/../large-v3", "", "small",
                  "medium", "distil-large-v3", "whisper.cpp", "large-v3;rm -rf", "large-v2"]
        modes = ["cuda:0", "cpu; rm -rf", "CUDA", "gpu", "float16", "int8_float16", "", None, 3,
                 ["cpu"], "auto\0", "AUTO", "int8", "nvidia"]
        langs = ["../x", "fa\0", "farsi", 1, None, "", "f" * 1000, "F", "fa ", "faa", "f", "فا"]
        sources = [None, "film", 5, [], {}, {"kind": "url", "path": film},
                   {"kind": "film"}, {"kind": "film", "path": None}, {"kind": "film", "path": 5},
                   {"kind": "film", "path": "film.mp4"}, {"kind": "film", "path": "../film.mp4"},
                   {"kind": "film", "path": film + "\0"}, {"kind": "film", "path": "/etc/passwd\0"},
                   {"kind": "film", "path": self.root},
                   {"kind": "film", "path": os.path.join(self.root, "missing.mp4")},
                   {"kind": "youtube", "id": "../../../etc"}, {"kind": "youtube", "id": "x" * 12},
                   {"kind": "youtube", "id": "abc def ghij"}, {"kind": "youtube", "id": None},
                   {"kind": "youtube", "id": 5}, {"kind": "youtube"}, {"kind": None}]
        tried = 0
        for key, values in (("model", models), ("processing", modes), ("lang", langs),
                            ("source", sources)):
            for value in values:
                with self.subTest(key=key, value=repr(value)[:50]):
                    args = dict(good, **{key: value})
                    status, body = self.refused(
                        sttjobs.start, args["source"], args["lang"], args["model"],
                        args["processing"])
                    self.assertIn(status, (400, 409, 422))
                    tried += 1
        self.assertGreater(tried, 60)
        self.assertEqual(self.gs.asked["model_dir"], [], "no model was ever named to the loader")
        self.assertEqual(self.records(), [], "no model was ever built")
        self.assertEqual(sttjobs.JOBS, {}, "no job was made")
        self.assertEqual(self.tmp(), [], "and nothing was written")
        self.assertFalse(sttjobs.CHILDREN)

    def test_a_hostile_duration_is_refused(self):
        # (10 ** 400 is JSON's way of writing a number no float can hold: it is refused
        # like the rest, and is not a 500 with a traceback in the log)
        for d in (0, -5, True, "600", [1], float("nan"), float("inf"), 10 ** 9, 10 ** 400):
            with self.subTest(duration=d):
                status, body = self.refused(self.start_yt, duration=d)
                self.assertEqual((status, body["code"]), (400, "bad-duration"))
        self.assertEqual(sttjobs.JOBS, {})

    def test_the_standard_models_keep_the_three_processing_modes(self):
        self.assertEqual(sttjobs.MODELS, sttjobs.speechmodels.MODELS)
        self.assertEqual(sttjobs.MODELS[:2], ('large-v3-turbo', 'large-v3'))
        self.assertEqual(sttjobs.MODES, ("auto", "cpu", "cuda"))
        stt_fakes.configure(self.root, cuda_ready=True)
        for model in sttjobs.speechmodels.STANDARD_MODELS:
            for mode in sttjobs.MODES:
                with self.subTest(model=model, mode=mode):
                    job = self.start_film(model=model, processing=mode)["job"]
                    self.assertEqual(self.done(job)["state"], "done")
                    self.settled()
        paths = sorted(set(r["path"] for r in self.records("construct")))
        self.assertEqual([os.path.basename(p) for p in paths], ["large-v3", "large-v3-turbo"])

    def test_language_specific_model_records_exact_provenance_and_decodes_both_passes(self):
        import speechconfig
        speechconfig.save({'second_pass': True})
        stt_fakes.configure(self.root, models=['fa-fast'], fake={
            'segments': [[0, 3, ' سلام جهان']],
            'word_evidence': {'جهان': {'score': .2, 'alternatives': [{'text':'دنیا', 'score':None}]}}})
        job = self.start_film(model='fa-fast')['job']
        status = self.done(job)
        self.assertEqual(status['model_revision'], sttjobs.speechmodels.provenance('fa-fast'))
        result = sttjobs.result(job)
        self.assertEqual(result['model_revision'], status['model_revision'])
        self.assertEqual(result['review']['evidence']['second_pass']['total'], 1)
        calls = self.records('transcribe')
        self.assertEqual([(call['language'], call['task'], call['beam_size']) for call in calls],
                         [('fa', 'transcribe', 5), ('fa', 'transcribe', 10)])
        self.assertFalse(calls[-1]['options']['condition_on_previous_text'])
        self.assertEqual(calls[-1]['options']['temperature'], 0)
        source_word = result['review']['evidence']['segments'][0]['words'][1]
        self.assertEqual((source_word['text'], source_word['start'], source_word['end'], source_word['asr_confidence']),
                         ('جهان', 1.5, 3, .2))
        self.assertIn('دنیا', [item['text'] for item in source_word['asr_alternatives']])

    def test_language_specific_model_cannot_be_used_for_another_language(self):
        stt_fakes.configure(self.root, models=['fa-fast'])
        status, body = self.refused(self.start_film, model='fa-fast', lang='ja')
        self.assertEqual(status, 400)
        self.assertFalse(self.records('construct'))

    def test_changed_catalogue_revision_invalidates_saved_model_before_loading(self):
        job = self.start_film()['job']
        self.done(job)
        state = sttjobs.JOBS[job]
        state['model_revision'] = dict(state['model_revision'], package_revision='0' * 40)
        with self.assertRaises(sttjobs.Refusal) as caught:
            sttjobs._spec(self.gs, state, recheck=True)
        self.assertEqual(caught.exception.code, 'model-changed')

    def test_extra_fields_a_client_might_send_are_not_part_of_the_signature(self):
        import inspect
        sig = inspect.signature(sttjobs.start).parameters
        params = [n for n, p in sig.items() if p.kind is not p.KEYWORD_ONLY]
        self.assertEqual(params, ["source", "lang", "model", "processing", "duration", "exact"])
        # a0.7.0: who the job is lent to, lent for, or aligned on is the SERVER's to say (the partner it
        # resolved from the jobs switches), never a field a client sends -- so those are keyword-only
        self.assertEqual(sorted(n for n, p in sig.items() if p.kind is p.KEYWORD_ONLY),
                         ["align_on", "lend_to", "lent_for"])
        with self.assertRaises(TypeError):
            sttjobs.start({"kind": "film", "path": self.film()}, "fa", TURBO, "cpu",
                          device="cuda")
        with self.assertRaises(TypeError):
            sttjobs.start({"kind": "film", "path": self.film()}, "fa", TURBO, "cpu",
                          compute_type="float32")

    def test_speech_to_text_that_is_not_installed_is_a_sentence(self):
        stt_fakes.configure(self.root, runtime=False)
        status, body = self.refused(self.start_film)
        self.assertEqual((status, body["code"], body["error"]),
                         (409, "not-installed", "Speech to text is not installed."))
        stt_fakes.configure(self.root, runtime=True, models=[LARGE])
        status, body = self.refused(self.start_film, model=TURBO)
        self.assertEqual((status, body["code"], body["error"]),
                         (409, "no-model", "The selected model is not installed."))
        self.assertEqual(self.start_film(model=LARGE)["state"], "queued")

    def test_a_checkout_with_no_getstt_at_all_is_simply_not_installed(self):
        with mock.patch.dict(sys.modules, {"getstt": None}):      # `import getstt` fails
            status, body = self.refused(self.start_film)
        self.assertEqual((status, body["code"]), (409, "not-installed"))

    def test_a_language_whisper_lacks_is_said(self):
        status, body = self.refused(self.start_film, lang="xx")
        self.assertEqual((status, body["code"]), (409, "unsupported-language"))
        self.assertIn("cannot listen for", body["error"])

    def test_an_explicit_graphics_card_that_is_not_ready_is_refused_at_once(self):
        # brief test 11 -- before anybody records an hour of sound for it
        status, body = self.refused(self.start_yt, processing="cuda")
        self.assertEqual((status, body["code"]),  (409, "gpu-unavailable"))
        self.assertEqual(body["error"], "GPU acceleration is unavailable; CPU mode is still available.")
        self.assertEqual(sttjobs.JOBS, {})
        self.assertEqual(self.gs.asked["resolve"], ["cuda"])

    def test_a_second_start_while_one_runs_is_busy_and_gets_no_token(self):
        first = self.start_yt()
        status, body = self.refused(self.start_film)
        self.assertEqual((status, body["code"], body["error"]),
                         (409, "busy", "Another transcription is running."))
        self.assertNotIn(first["job"], json.dumps(body), "a token is the one capability")
        self.assertNotIn("job", body)
        self.assertEqual(list(sttjobs.JOBS), [first["job"]])

    def test_the_slot_is_free_the_moment_a_job_ends(self):
        self.fake(load_delay=1.0)                      # long enough to be seen running
        first = self.start_film()
        self.assertEqual(self.refused(self.start_film)[1]["code"], "busy")
        self.done(first["job"])
        second = self.start_film()                     # done: not busy, though not forgotten
        self.assertNotEqual(first["job"], second["job"])
        self.done(second["job"])

    def test_source_of_speaks_the_add_flows_own_sentences(self):
        film = self.film()
        open(os.path.join(self.root, "x.txt"), "w").close()
        ok = sttjobs.source_of({"source": "youtube", "url": "https://www.youtube.com/watch?v="
                                + YT + "&t=5s", "lang": "it"})
        self.assertEqual(ok, ({"kind": "youtube", "id": YT}, "it"))
        self.assertEqual(sttjobs.source_of({"source": "youtube", "url": YT, "lang": "ja"})[0]["id"], YT)
        source, lang = sttjobs.source_of({"source": "film", "path": '"%s"' % film, "lang": "ar"})
        self.assertEqual((source, lang), ({"kind": "film", "path": film}, "ar"),
                         "the ABSOLUTE path check_film made, not the page's spelling")
        for body, said in [
                ({"source": "youtube", "url": YT, "path": film, "lang": "fa"},
                 "a video is either an address or a file on this machine, and this names both"),
                ({"source": "youtube", "url": "https://example.com/x", "lang": "fa"},
                 "that is not a YouTube URL (or id) -- or name a film on this machine instead"),
                ({"source": "youtube", "url": "", "lang": "fa"}, "that is not a YouTube URL"),
                ({"source": "film", "path": os.path.join(self.root, "gone.mp4"), "lang": "fa"},
                 "no file at "),
                # a file that is there and is not a video: the film door's own sentence
                ({"source": "film", "path": os.path.join(self.root, "x.txt"), "lang": "fa"},
                 "is not a video this can play"),
                ({"source": "film", "path": "", "lang": "fa"}, "name the film"),
                ({"source": "film", "lang": "fa"}, "name the film"),
                ({"source": "film", "url": YT, "lang": "fa"}, "is named by its path"),
                ({"source": "tape", "url": YT, "lang": "fa"}, "starts from a YouTube video"),
                ({"url": YT, "lang": "fa"}, "starts from a YouTube video"),
                ({"source": "youtube", "url": YT, "lang": "xx"}, "is not a language this toolbox teaches"),
                ({"source": "youtube", "url": YT, "lang": ""}, "name the language"),
                ({"source": "youtube", "url": YT}, "name the language"),
                ({"source": "youtube", "url": ["x"], "lang": "fa"}, "has to be text"),
                ({"source": "film", "path": {"a": 1}, "lang": "fa"}, "has to be text"),
                ({"source": "film", "path": film, "lang": 5}, "has to be text"),
                ({"source": ["film"], "path": film, "lang": "fa"}, "has to be text")]:
            with self.subTest(body=repr(body)[:80]):
                status, out = self.refused(sttjobs.source_of, body)
                self.assertEqual(status, 400)
                self.assertIn(said, out["error"])
                self.assertNotIn("Traceback", out["error"])

    def test_a_path_is_never_read_again_after_it_was_named(self):
        # the job stores what the validators made: nothing but the token names it later
        film = self.film()
        got = sttjobs.start({"kind": "film", "path": film}, "fa", TURBO, "cpu")
        job = sttjobs.JOBS[got["job"]]
        self.assertEqual(job["source"], {"kind": "film", "path": os.path.abspath(film)})
        for fn in (sttjobs.status, sttjobs.result, sttjobs.cancel):
            self.assertEqual(fn.__code__.co_argcount, 1, "the token, and nothing else")
        self.done(got["job"])


# ======================================================================== the devices
class Devices(Base):
    """Brief tests 7-14 through the whole job: what the CHILD did, read off the stand-in."""

    def run_film(self, processing, **cfg):
        if cfg:
            self.fake(**cfg)
        job = self.start_film(processing=processing)["job"]
        return job, self.done(job)

    def test_cpu_is_cpu_and_int8_and_the_card_is_never_asked_after(self):
        stt_fakes.configure(self.root, cuda_ready=True)          # ready, and still not used
        job, s = self.run_film("cpu")
        self.assertEqual((s["state"], s["device"], s["fell_back"]), ("done", "cpu", False))
        (rec,) = self.records("construct")
        self.assertEqual((rec["device"], rec["compute_type"], rec["cpu_threads"]),
                         ("cpu", "int8", 3))
        self.assertEqual(self.built(), [("cpu", "int8")], "never constructed with device cuda")

    def test_automatic_is_the_cpu_when_no_card_is_ready_and_the_card_when_one_is(self):
        job, s = self.run_film("auto")
        self.assertEqual((s["device"], self.built()), ("cpu", [("cpu", "int8")]))
        self.settled()
        open(os.path.join(self.root, "fake.log"), "w").close()
        stt_fakes.configure(self.root, cuda_ready=True, cuda_name="Fake GPU 8 GB")
        job, s = self.run_film("auto")
        self.assertEqual((s["state"], s["device"], s["fell_back"]), ("done", "cuda", False))
        self.assertEqual(self.built(), [("cuda", "int8_float16")])
        self.assertEqual(self.heard(), ["cuda"])

    def test_the_card_is_named_and_the_lines_are_the_ones_the_brief_gives(self):
        stt_fakes.configure(self.root, cuda_ready=True, cuda_name="NVIDIA GeForce RTX 4060")
        self.fake(load_delay=0.8, delay=0.5, segments=[[0, 1, " a"], [1, 2, " b"], [2, 3, " c"]])
        job = self.start_film(processing="auto", seconds=3)["job"]
        loading = self.wait(job, ("loading",))
        self.assertEqual(loading["say"], "Loading large-v3-turbo… Using NVIDIA GeForce RTX 4060.")
        run = self.wait(job, ("transcribing",))
        self.assertRegex(run["say"], r"^Transcribing on GPU… \d+%$")
        self.assertEqual(self.done(job)["say"], "Done — 3 captions.")

    def test_the_cpu_lines_say_cpu(self):
        self.fake(load_delay=0.6, delay=0.5, segments=[[0, 1, " a"], [1, 2, " b"], [2, 3, " c"]])
        job = self.start_film(seconds=3)["job"]
        self.assertEqual(self.wait(job, ("loading",))["say"], "Loading large-v3-turbo…")
        self.assertRegex(self.wait(job, ("transcribing",))["say"], r"^Transcribing on CPU… \d+%$")
        self.done(job)

    def test_an_automatic_card_failure_falls_back_once_and_says_so(self):
        # brief test 12
        stt_fakes.configure(self.root, cuda_ready=True)
        self.fake(cuda_load_error="the card said no", delay=0.5,
                  segments=[[0, 1, " a"], [1, 2, " b"], [2, 3, " c"]])
        job = self.start_film(processing="auto", seconds=3)["job"]
        mid = self.until(lambda: (lambda s: s if s["state"] == "transcribing"
                                  and s["fell_back"] else None)(sttjobs.status(job)),
                         "a status on the CPU after the fall back")
        self.assertEqual(mid["device"], "cpu")
        self.assertTrue(mid["say"].startswith(
            "The graphics card could not start this model, so Parseh continued on the CPU."),
            mid["say"])
        self.assertRegex(mid["say"], r"Transcribing on CPU…")
        self.assertEqual(mid["note"], sttjobs.FELL_BACK)
        s = self.done(job)
        self.assertEqual((s["state"], s["device"], s["fell_back"]), ("done", "cpu", True))
        self.assertEqual(self.built(), [("cuda", "int8_float16"), ("cpu", "int8")],
                         "one try on the card, ONE on the CPU, no third")
        self.settled()
        self.assertIn("the card said no", self.log.getvalue(),
                      "the technical error is kept for the server's log")
        self.assertNotIn("the card said no", json.dumps(s))

    def test_an_explicit_card_failure_is_not_hidden(self):
        # brief test 13
        stt_fakes.configure(self.root, cuda_ready=True)
        self.fake(cuda_load_error="the card said no")
        job, s = self.run_film("cuda")
        self.assertEqual((s["state"], s["code"], s["fell_back"], s["device"]),
                         ("failed", "gpu-error", False, "cuda"))
        self.assertIn("CUDA was requested but could not be initialized", s["error"])
        self.assertIn("Choose Automatic or CPU", s["error"])
        self.assertEqual(self.built(), [("cuda", "int8_float16")], "and it did not switch")
        status, body = self.refused(sttjobs.result, job)
        self.assertEqual((status, body["code"]), (409, "gpu-error"))
        self.assertNotIn("the card said no", json.dumps(body))

    def test_the_lazy_libcublas_error_in_the_generator_falls_back_in_automatic(self):
        stt_fakes.configure(self.root, cuda_ready=True)
        job, s = self.run_film("auto", cuda_lazy_error=LAZY)
        self.assertEqual((s["state"], s["device"], s["fell_back"]), ("done", "cpu", True))
        self.assertEqual(self.heard(), ["cuda", "cpu"])
        self.settled()
        self.assertIn("libcublas", self.log.getvalue())
        job, s = self.run_film("cuda")
        self.assertEqual((s["state"], s["code"]), ("failed", "gpu-error"))

    def test_out_of_memory_on_the_card(self):
        # brief test 14
        stt_fakes.configure(self.root, cuda_ready=True)
        job, s = self.run_film("auto", cuda_load_error=OOM)
        self.assertEqual((s["state"], s["device"], s["fell_back"]), ("done", "cpu", True))
        self.settled()
        job, s = self.run_film("cuda")
        self.assertEqual((s["state"], s["code"]), ("failed", "gpu-memory"))
        self.assertIn("ran out of memory", s["error"])
        self.assertNotIn("CUDA failed", s["error"])

    def test_a_card_that_lacks_the_lighter_precision_is_asked_for_the_next(self):
        stt_fakes.configure(self.root, cuda_ready=True)
        job, s = self.run_film("cuda", cuda_reject_compute=["int8_float16"])
        self.assertEqual((s["state"], s["device"]), ("done", "cuda"))
        self.assertEqual(self.built(), [("cuda", "int8_float16"), ("cuda", "float16")])

    def test_cpu_failures_are_sentences_and_never_tracebacks(self):
        for cfg, code, say in [
                ({"cpu_load_error": "cannot open model.bin"}, "model-load",
                 "The model could not be loaded."),
                ({"cpu_lazy_error": "kernel exploded"}, "failed", "Transcription failed."),
                ({"cpu_load_error": "std::bad_alloc"}, "no-memory",
                 "The computer ran out of memory for this model.")]:
            with self.subTest(cfg=cfg):
                job, s = self.run_film("cpu", **cfg)
                self.assertEqual((s["state"], s["code"], s["error"]), ("failed", code, say))
                self.assertNotIn("Traceback", json.dumps(s))
                self.settled()

    def test_a_runtime_taken_away_after_start_is_said(self):
        got = self.start_yt()
        stt_fakes.configure(self.root, runtime=False)
        self.assertEqual(sttjobs.audio(got["job"], 0, self.pcm(2), True)["state"], "queued")
        s = self.done(got["job"])
        self.assertEqual((s["state"], s["code"]), ("failed", "not-installed"))

    def test_the_child_is_told_nothing_the_client_chose_and_is_isolated(self):
        job = self.start_film(processing="cpu")["job"]
        self.done(job)
        (rec,) = self.records("construct")
        self.assertEqual(rec["path"], os.path.join(self.gs.STT_DIR, "models", TURBO))
        self.assertEqual(rec["rest"], [])
        self.assertTrue(rec["local_files_only"])
        self.assertEqual(rec["env"]["PYTHONPATH"], stt_fakes.FIXTURE_RUNTIME)
        self.assertEqual((rec["env"]["HF_HUB_OFFLINE"], rec["env"]["PYTHONNOUSERSITE"],
                          rec["env"]["PYTHONSAFEPATH"]), ("1", "1", "1"))


# ============================================================================ a film
class Films(Base):
    def test_a_film_that_changed_after_it_was_named_is_not_read(self):
        with mock.patch.object(sttjobs, "_launch", lambda job: None):
            got = self.start_film()
        with open(os.path.join(self.root, "film.mp4"), "ab") as f:
            f.write(b"\0" * 10)
        sttjobs._launch(sttjobs.JOBS[got["job"]])
        s = self.done(got["job"])
        self.assertEqual((s["state"], s["code"]), ("failed", "film-changed"))
        self.assertIn("name it again", s["error"])
        self.assertEqual(self.records(), [], "no model was built for it")

    def test_a_film_that_cannot_be_decoded_is_a_sentence(self):
        bad = os.path.join(self.root, "bad.mp4")
        with open(bad, "wb") as f:
            f.write(b"not a film at all")
        got = sttjobs.start({"kind": "film", "path": bad}, "fa", TURBO, "cpu")
        s = self.done(got["job"])
        self.assertEqual((s["state"], s["code"], s["error"]),
                         ("failed", "film-undecodable", "The local film could not be decoded."))
        self.settled()
        self.assertIn("Invalid data", self.log.getvalue())
        self.assertNotIn("Invalid data", json.dumps(s))

    def test_a_film_with_no_sound_is_said(self):
        got = self.start_film(seconds=0)
        s = self.done(got["job"])
        self.assertEqual((s["state"], s["code"]), ("failed", "no-sound"))

    def test_nothing_is_heard_in_a_film(self):
        self.fake(segments=[])
        s = self.done(self.start_film()["job"])
        self.assertEqual((s["state"], s["code"]), ("failed", "no-speech"))
        self.assertIn("No speech was heard", s["error"])

    def test_a_film_takes_no_recording_no_marks_and_sends_no_waveform(self):
        got = self.start_film()
        for fn, args in ((sttjobs.audio, (got["job"], 0, b"\0\0", False)),
                         (sttjobs.marks, (got["job"], [[1, 1]])),
                         (sttjobs.wave, (got["job"], 20, [0.5]))):
            with self.subTest(route=fn.__name__):
                status, body = self.refused(fn, *args)
                self.assertEqual((status, body["code"]), (409, "wrong-state"))
        self.done(got["job"])

    def test_a_film_survives_every_end_of_a_job(self):
        # THE PERSON'S FILM IS NEVER MODIFIED OR DELETED: what a job tidies away is its own temporary
        # files.  Said for each way a job ends, since each tidies up in a place of its own -- a
        # list of what to delete that ever named the film would take it in all four
        def stamp(path):
            try:
                st = os.stat(path)
                with open(path, "rb") as f:
                    return (st.st_size, st.st_mtime_ns, hashlib.sha256(f.read()).hexdigest())
            except OSError:
                return "the film is gone"

        def alone(seconds=3):
            path = self.film(seconds)
            return path, stamp(path)
        slow = dict(load_delay=0.3, delay=1.0, segments=[[0, 1, " a"], [1, 2, " b"], [2, 3, " c"],
                                                          [3, 4, " d"], [4, 5, " e"]])
        # done
        path, before = alone()
        self.assertEqual(self.done(sttjobs.start({"kind": "film", "path": path}, "fa", TURBO, "cpu")["job"])["state"], "done")
        self.settled()
        self.assertEqual(stamp(path), before, "a film that was transcribed")
        # failed
        self.fake(segments=[])
        path, before = alone()
        self.assertEqual(self.done(sttjobs.start({"kind": "film", "path": path}, "fa", TURBO, "cpu")["job"])["state"], "failed")
        self.settled()
        self.assertEqual(stamp(path), before, "a film whose transcription failed")
        # cancelled
        self.fake(**slow)
        open(os.path.join(self.root, "fake.log"), "w").close()
        path, before = alone(5)
        job = sttjobs.start({"kind": "film", "path": path}, "fa", TURBO, "cpu")["job"]
        self.until(lambda: self.records("construct"), "the worker built its model")
        self.assertEqual(sttjobs.cancel(job), {"cancelled": True})
        self.settled()
        self.assertEqual(stamp(path), before, "a film whose job was cancelled")
        # a server that is stopping
        open(os.path.join(self.root, "fake.log"), "w").close()
        path, before = alone(5)
        sttjobs.start({"kind": "film", "path": path}, "fa", TURBO, "cpu")
        self.until(lambda: self.records("construct"), "the worker built its model")
        sttjobs.stop_all()
        self.settled()
        self.assertEqual(stamp(path), before, "a film whose job was stopped with the server")
        # and what a job does list to delete is its own
        for job in sttjobs.JOBS.values():
            self.assertNotIn(job["source"]["path"], sttjobs._files(job))

    def test_a_film_gets_no_waveform_written(self):
        # the owner: nothing is written for a film, and a film's job holds nothing
        got = self.start_film()
        self.done(got["job"])
        self.assertFalse(wavefile.held(got["job"]))
        self.assertFalse(os.path.exists(wavefile.hold_dir()))
        self.assertEqual(sttjobs.result(got["job"])["wave"], {"held": False})
        self.settled()

    def test_the_job_is_registered_with_getstt_and_holds_its_model_while_it_runs(self):
        self.fake(load_delay=0.6, delay=0.3)
        got = self.start_film(model=LARGE)
        self.until(lambda: len(self.gs._procs) == 1 and self.gs._using == [LARGE],
                   "the worker tracked and the model in use")
        (proc,) = self.gs._procs
        self.assertIsNone(proc.poll())
        self.done(got["job"])
        self.settled()
        self.assertEqual((self.gs._procs, self.gs._using), (set(), []))

    def test_the_temporary_files_are_gone_when_it_is_done(self):
        got = self.start_film()
        self.done(got["job"])
        self.settled()
        self.assertEqual(self.tmp(), [])
        self.assertEqual(sttjobs.status(got["job"])["state"], "done")
        self.assertIn("text", sttjobs.result(got["job"]), "and the answer can be read again")
        # (that it is the SAME text, read again, is tests/test_stt_route.py's: it holds the first
        # answer, a known Persian string, beside the second)

    def test_a_finished_pending_review_can_be_restored_after_memory_retention(self):
        got = self.start_film()
        self.done(got["job"])
        with mock.patch.object(sttjobs, "KEEP", 0.0):
            time.sleep(0.05)
            self.assertIn(sttjobs.status(got["job"])["state"], ("done", "awaiting-review-choice"))
        self.assertIn("text", sttjobs.result(got["job"]))

    def test_the_answer_of_a_job_that_is_not_done_is_not_finished(self):
        self.fake(load_delay=0.8)
        got = self.start_film()
        status, body = self.refused(sttjobs.result, got["job"])
        self.assertEqual((status, body["code"], body["error"]),
                         (409, "not-finished", "It has not finished yet."))
        self.done(got["job"])


# ====================================================================== the recording
class Recording(Base):
    def job(self, **kw):
        return self.start_yt(**kw)["job"]

    def pcm_file(self, token):
        return sttjobs.JOBS[token]["pcm"]

    def test_pieces_are_written_where_they_say_and_a_piece_sent_twice_is_written_once(self):
        job = self.job()
        one, two = stt_fakes.pcm(1, hz=440), stt_fakes.pcm(1, hz=880)
        r = sttjobs.audio(job, 0, one, False)
        self.assertEqual((r["have"], r["state"]), (16000, "receiving"))
        self.assertEqual(sttjobs.audio(job, 0, one, False)["have"], 16000, "sent again: no more")
        self.assertEqual(sttjobs.audio(job, 16000, two, False)["have"], 32000)
        self.assertEqual(sttjobs.audio(job, 16000, two, False)["have"], 32000)
        self.assertEqual(sttjobs.audio(job, 0, one, False)["have"], 32000, "an old piece again")
        with open(self.pcm_file(job), "rb") as f:
            self.assertEqual(f.read(), one + two)
        # a piece that overlaps what is there and reaches past it is written whole,
        # at its own offset: sample 24000 is byte 48000
        third = stt_fakes.pcm(1, hz=220)
        self.assertEqual(sttjobs.audio(job, 24000, third, False)["have"], 40000)
        with open(self.pcm_file(job), "rb") as f:
            data = f.read()
        self.assertEqual(len(data), 40000 * 2)
        self.assertEqual(data[:48000], (one + two)[:48000])
        self.assertEqual(data[48000:], third)

    def test_a_piece_that_skips_ahead_is_a_gap_and_says_where_the_recording_is(self):
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(1), False)
        status, body = self.refused(sttjobs.audio, job, 20000, self.pcm(1), False)
        self.assertEqual((status, body["code"], body["have"]), (409, "gap", 16000))
        # and an empty piece must say where the end is
        status, body = self.refused(sttjobs.audio, job, 9999, b"", True)
        self.assertEqual((status, body["code"], body["have"]), (409, "gap", 16000))
        self.assertEqual(sttjobs.audio(job, 16000, self.pcm(1), False)["have"], 32000,
                         "sent again from `have`, it goes on")

    def test_the_size_caps(self):
        job = self.job()
        status, body = self.refused(sttjobs.audio, job, 0, b"\0" * (sttjobs.CHUNK_MAX + 2), False)
        self.assertEqual((status, body["code"]), (413, "too-big"))
        full = b"\1\0" * (sttjobs.CHUNK_MAX // 2)
        self.assertEqual(sttjobs.audio(job, 0, full, False)["have"], sttjobs.CHUNK_MAX // 2,
                         "exactly one MiB is allowed")
        self.assertEqual(self.refused(sttjobs.audio, job, sttjobs.CHUNK_MAX // 2, b"\0\0\0", False)[1]["code"],
                         "bad-audio", "an odd number of bytes is no samples")
        self.assertEqual(self.refused(sttjobs.audio, job, sttjobs.CHUNK_MAX // 2, b"", False)[1]["code"],
                         "bad-audio", "an empty piece is not a piece, unless it is the last")
        with mock.patch.object(sttjobs, "MAX_SAMPLES", 262144 + 100):
            status, body = self.refused(sttjobs.audio, job, sttjobs.CHUNK_MAX // 2, b"\0\0" * 101, False)
            self.assertEqual((status, body["code"]), (413, "too-long"))
        self.assertEqual(sttjobs.JOBS[job]["have"], sttjobs.CHUNK_MAX // 2)

    def test_offsets_and_bodies_of_the_wrong_kind_are_refused(self):
        job = self.job()
        for offset in (-1, "0", None, 1.5, True, [0], 10 ** 30):
            with self.subTest(offset=offset):
                status, body = self.refused(sttjobs.audio, job, offset, self.pcm(1), False)
                self.assertIn(body["code"], ("bad-offset", "gap"))
        for data in ("text", None, 5, [1, 2], {"a": 1}):
            with self.subTest(data=data):
                self.assertEqual(self.refused(sttjobs.audio, job, 0, data, False)[1]["code"],
                                 "bad-audio")
        self.assertEqual(sttjobs.JOBS[job]["have"], 0)
        self.assertFalse(os.path.exists(self.pcm_file(job)))

    def test_the_last_piece_starts_the_job_and_sent_again_starts_nothing_more(self):
        self.fake(segments=PERSIAN)
        job = self.job(duration=10)
        sttjobs.audio(job, 0, self.pcm(2), False)
        r = sttjobs.audio(job, 32000, self.pcm(1), True)
        self.assertEqual((r["have"], r["state"]), (48000, "queued"))
        self.assertEqual(sttjobs.status(job)["total"], 3.0)
        again = sttjobs.audio(job, 32000, self.pcm(1), True)   # its answer was lost
        self.assertEqual(again["have"], 48000)
        s = self.done(job)
        self.assertEqual((s["state"], s["say"]), ("done", "Done — 2 captions."))
        self.assertEqual(len(self.records("construct")), 1, "one worker, not two")
        (rec,) = self.records("transcribe")
        self.assertEqual(rec["samples"], 48000, "what the worker heard is what was sent")
        status, body = self.refused(sttjobs.audio, job, 0, self.pcm(1), False)
        self.assertEqual((status, body["code"]), (409, "wrong-state"))
        self.settled()
        self.assertEqual(self.tmp(), [], "the temporary recording is deleted after the job")

    def test_an_empty_last_piece_seals_what_is_there(self):
        self.fake(segments=PERSIAN)
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(2), False)
        self.assertEqual(sttjobs.audio(job, 32000, b"", True)["state"], "queued")
        self.assertEqual(self.done(job)["state"], "done")

    def test_no_recording_worth_the_name_is_said(self):
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(0.2), False)
        status, body = self.refused(sttjobs.audio, job, 3200, b"", True)
        self.assertEqual((status, body["code"]), (400, "no-sound"))
        self.assertEqual(sttjobs.status(job)["state"], "failed")
        self.assertEqual(self.tmp(), [])

    def test_the_recording_says_how_far_it_has_got(self):
        job = self.job(duration=600)
        self.assertEqual(sttjobs.status(job)["say"], "Waiting for the recording to start…")
        sttjobs.audio(job, 0, self.pcm(1), False)
        self.assertEqual(sttjobs.status(job)["say"], "Recording 0:01 / 10:00…")
        self.assertEqual(sttjobs.status(job)["pct"], 0)
        sttjobs.audio(job, 16000, self.pcm(30), False)              # one piece may not pass 1 MiB
        sttjobs.audio(job, 16000 + 30 * 16000, self.pcm(30), False)
        self.assertEqual(sttjobs.status(job)["say"], "Recording 1:01 / 10:00…")
        self.assertEqual(sttjobs.status(job)["pct"], 10)
        sttjobs.cancel(job)
        # a page that does not know how long the video is gets no total to say
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(1), False)
        s = sttjobs.status(job)
        self.assertEqual((s["say"], s["pct"], s["total"]), ("Recording 0:01…", None, None))

    def test_the_clock_the_browser_sent_is_the_clock_of_the_captions(self):
        # a start lag of 1.0 s: what Whisper heard at recording second 3 was said at
        # video second 2 -- and a caption's start in the box is video time
        self.fake(segments=[[3.0, 4.0, " سلام"], [8.0, 9.0, " خدا"]])
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(10), False)
        marks = [[16000 * k, k - 1.0] for k in range(2, 10)]
        self.assertEqual(sttjobs.marks(job, marks + ["junk", None, [1]])["marks"], 8)
        sttjobs.audio(job, 160000, b"", True)
        self.assertEqual(self.done(job)["state"], "done")
        text = sttjobs.result(job)["text"]
        self.assertEqual(text.split("\n")[::2][:2], ["0:02", "0:07"])

    def test_marks_are_a_replace_all_and_only_while_recording(self):
        job = self.job()
        sttjobs.marks(job, [[16000, 0.0], [32000, 1.0]])
        self.assertEqual(sttjobs.marks(job, [[16000, 0.0]])["marks"], 1)
        self.assertEqual(len(sttjobs.JOBS[job]["marks"]), 1)
        self.assertEqual(self.refused(sttjobs.marks, job, "x")[1]["code"], "bad-marks")
        sttjobs.audio(job, 0, self.pcm(1), True)
        status, body = self.refused(sttjobs.marks, job, [[1, 1]])
        self.assertEqual((status, body["code"]), (409, "wrong-state"))
        self.done(job)

    def test_the_browsers_waveform_is_held_for_the_video_that_will_be_made(self):
        self.fake(segments=PERSIAN)
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(3), False)
        self.assertEqual(sttjobs.wave(job, 20, [0, 0.5, 1.0, 0.25])["buckets"], 4)
        self.assertTrue(wavefile.held(job))
        held = os.path.join(self.videos, ".waveforms", job + ".json")
        with open(held, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"rate": 20.0, "peaks": [0.0, 0.5, 1.0, 0.25]})
        sttjobs.audio(job, 48000, b"", True)
        self.done(job)
        self.assertEqual(sttjobs.result(job)["wave"], {"held": True})
        video = os.path.join(self.videos, "persian", "some-id")
        os.makedirs(video)
        self.assertEqual(wavefile.adopt(job, video), {"kept": True, "buckets": 4})
        self.assertFalse(os.path.exists(held))
        self.assertEqual(sttjobs.result(job)["wave"], {"held": False})

    def test_a_bad_waveform_is_refused_in_the_waveform_doors_own_words(self):
        job = self.job()
        for rate, peaks, said in [(20, [], "no waveform was sent"),
                                  (0, [0.5], "a waveform carries between 1 and 200 numbers a second"),
                                  ("x", [0.5], "a waveform says how many numbers a second it has"),
                                  (10 ** 400, [0.5], "a waveform says how many numbers a second it has")]:
            status, body = self.refused(sttjobs.wave, job, rate, peaks)
            self.assertEqual((status, body["code"], body["error"]), (400, "bad-wave", said))
        self.assertFalse(wavefile.held(job))

    def test_a_number_no_float_can_hold_is_a_number_that_is_not_believed(self):
        # a peak that is one is like any other peak that is not a number: nothing, and not a 500
        job = self.job()
        self.assertEqual(sttjobs.wave(job, 20, [0.5, 10 ** 400, 1.0])["buckets"], 3)
        held = os.path.join(self.videos, ".waveforms", job + ".json")
        with open(held, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["peaks"], [0.5, 0.0, 1.0])
        self.assertEqual(sttjobs.marks(job, [[10 ** 400, 1], [1, 10 ** 400], [16000, 1]]),
                         {"marks": 1})

    def test_a_recording_that_stops_arriving_is_given_up_and_its_audio_deleted(self):
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(1), False)
        sttjobs.wave(job, 20, [0.5, 1.0])
        self.assertTrue(os.path.exists(self.pcm_file(job)))
        self.assertTrue(wavefile.held(job))
        path = self.pcm_file(job)
        sttjobs.JOBS[job]["touched"] -= sttjobs.IDLE + 1
        s = sttjobs.status(job)
        self.assertEqual((s["state"], s["code"]), ("failed", "abandoned"))
        self.assertIn("given up", s["error"])
        self.assertFalse(os.path.exists(path))
        self.assertFalse(wavefile.held(job), "a partial capture holds nothing")
        self.assertFalse(sttjobs.busy(), "and the slot is free")
        self.assertEqual(self.start_film()["state"], "queued")

    def test_the_waveform_of_a_whole_capture_survives_a_transcription_that_failed(self):
        # an hour of the person's time: the peaks stay for the video, whatever the model did
        self.fake(cpu_load_error="cannot open model.bin")
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(2), False)
        sttjobs.wave(job, 20, [0.5, 1.0, 0.25])
        sttjobs.audio(job, 32000, b"", True)
        s = self.done(job)
        self.assertEqual((s["state"], s["code"]), ("failed", "model-load"))
        self.assertTrue(wavefile.held(job))
        self.settled()

    def test_a_disk_with_no_room_is_said_before_and_during_the_capture(self):
        with mock.patch.object(sttjobs, "_free", lambda p: 1000):
            status, body = self.refused(self.start_yt)
        self.assertEqual((status, body["code"], body["error"]), (507, "no-room", NO_ROOM))
        self.assertEqual(sttjobs.JOBS, {})
        # room for the start, and for the whole of the hour the page says it is
        with mock.patch.object(sttjobs, "_free", lambda p: sttjobs.FREE_TO_START + 1000):
            self.assertEqual(self.refused(self.start_yt, duration=3600)[1]["code"], "no-room")
            job = self.start_yt(duration=0.01)["job"]
        # and then the disk fills up while the recording comes in
        sttjobs.audio(job, 0, self.pcm(1), False)
        path = self.pcm_file(job)
        with mock.patch.object(sttjobs, "_free", lambda p: 1000):
            status, body = self.refused(sttjobs.audio, job, 16000, self.pcm(1), False)
        self.assertEqual((status, body["code"], body["error"]), (507, "no-room", NO_ROOM))
        s = sttjobs.status(job)
        self.assertEqual((s["state"], s["error"]), ("failed", NO_ROOM))
        self.assertFalse(os.path.exists(path), "what was written is deleted")

    def test_a_write_that_the_disk_refuses_is_the_same_sentence(self):
        job = self.job()
        real = open

        def refuse(path, *a, **k):
            if str(path).endswith(".pcm"):
                raise OSError(28, "No space left on device")
            return real(path, *a, **k)
        with mock.patch("builtins.open", refuse):
            status, body = self.refused(sttjobs.audio, job, 0, self.pcm(1), False)
        self.assertEqual((status, body["error"]), (507, NO_ROOM))
        self.assertNotIn("No space", json.dumps(body))
        self.assertEqual(sttjobs.status(job)["state"], "failed")

    def test_a_recording_the_disk_lost_is_a_sentence(self):
        job = self.job()
        sttjobs.audio(job, 0, self.pcm(1), False)
        os.unlink(self.pcm_file(job))
        with mock.patch.object(sttjobs, "_launch", lambda j: None):
            sttjobs.audio(job, 16000, b"", True)
        sttjobs._run(sttjobs.JOBS[job])
        s = sttjobs.status(job)
        self.assertEqual((s["state"], s["code"], s["error"]),
                         ("failed", "audio-gone", "The temporary recording disappeared."))


# ================================================================= cancel and the child
class Cancel(Base):
    def slow_film(self, **cfg):
        self.fake(load_delay=0.3, delay=1.0, segments=[[0, 1, " a"], [1, 2, " b"], [2, 3, " c"],
                                                       [3, 4, " d"], [4, 5, " e"]], **cfg)
        got = self.start_film(seconds=5)
        rec = self.until(lambda: self.records("construct"), "the worker built its model")
        return got["job"], rec[0]["pid"]

    @unittest.skipUnless(POSIX, "process states are read from /proc")
    def test_cancelling_a_film_kills_the_child_and_leaves_the_table_clean(self):
        job, pid = self.slow_film()
        self.assertTrue(alive(pid))
        self.assertTrue(self.tmp(), "there are temporary files while it runs")
        self.assertEqual(sttjobs.cancel(job), {"cancelled": True})
        self.assertFalse(alive(pid), "the child was killed")
        self.assertEqual(sttjobs.JOBS, {}, "and the table is clean")
        self.assertEqual(self.tmp(), [])
        self.assertFalse(sttjobs.busy())
        s = sttjobs.status(job)
        self.assertEqual((s["state"], s["stopped"], s["say"]),
                         ("cancelled", True, "Transcription was cancelled."))
        self.assertEqual(self.refused(sttjobs.result, job)[1]["code"], "cancelled")
        self.until(lambda: not self.gs._procs and self.gs._using == [], "getstt let go of it")
        # the slot is free at once, and a new job goes through
        self.fake()
        again = self.start_film()
        self.assertEqual(self.done(again["job"])["state"], "done")
        self.assertEqual(sttjobs.cancel(job), {"cancelled": False}, "twice is fine")

    def test_cancelling_a_recording_deletes_the_audio_and_the_held_waveform(self):
        job = self.start_yt()["job"]
        sttjobs.audio(job, 0, stt_fakes.pcm(1), False)
        sttjobs.wave(job, 20, [0.5, 1.0])
        path = sttjobs.JOBS[job]["pcm"]
        self.assertTrue(os.path.exists(path) and wavefile.held(job))
        self.assertEqual(sttjobs.cancel(job), {"cancelled": True})
        self.assertFalse(os.path.exists(path))
        self.assertFalse(wavefile.held(job), "a cancelled capture keeps nothing")
        self.assertEqual((sttjobs.JOBS, self.tmp()), ({}, []))
        s = sttjobs.status(job)
        self.assertEqual((s["state"], s["say"]), ("cancelled", CANCELLED_YT))
        # nothing more is taken for it, and a page still sending is told why
        status, body = self.refused(sttjobs.audio, job, 16000, stt_fakes.pcm(1), False)
        self.assertEqual((status, body["code"], body["error"]), (409, "cancelled", CANCELLED_YT))
        self.assertEqual(self.refused(sttjobs.wave, job, 20, [1])[1]["code"], "cancelled")
        self.assertEqual(self.refused(sttjobs.marks, job, [[1, 1]])[1]["code"], "cancelled")
        self.assertEqual(sttjobs.cancel(job), {"cancelled": False})
        self.assertFalse(wavefile.held(job), "and the late waveform was not kept")

    def test_cancelling_while_the_last_piece_is_being_taken_leaves_no_worker(self):
        self.fake(load_delay=1.0)
        job = self.start_yt()["job"]
        sttjobs.audio(job, 0, stt_fakes.pcm(1), True)
        self.assertTrue(self.until(lambda: sttjobs.JOBS[job]["state"] != "queued", "it began"))
        sttjobs.cancel(job)
        self.until(lambda: not sttjobs.CHILDREN, "no worker left")
        self.assertEqual(self.tmp(), [])

    def test_a_job_that_is_over_has_nothing_to_stop(self):
        got = self.start_film()
        self.done(got["job"])
        review = sttjobs.result(got['job'])['review']['evidence']
        sttjobs.use_review(got['job'], review['source_sha256'], {})
        self.assertEqual(sttjobs.cancel(got["job"]), {"cancelled": False})
        self.assertEqual(sttjobs.status(got["job"])["state"], "done")
        self.assertIn("text", sttjobs.result(got["job"]))

    def test_a_token_nobody_holds_cancels_nothing(self):
        self.assertEqual(sttjobs.cancel("A" * 16), {"cancelled": False})
        for bad in ("../x", "A" * 15, "", None, 5):
            self.assertEqual(self.refused(sttjobs.cancel, bad)[1]["code"], "no-such-job")

    @unittest.skipUnless(POSIX, "process states are read from /proc")
    def test_stopping_the_server_ends_every_worker_and_deletes_the_recordings(self):
        job, pid = self.slow_film()
        self.assertTrue(alive(pid))
        sttjobs.stop_all()
        self.until(lambda: not alive(pid), "the worker gone")
        self.until(lambda: not self.tmp(), "the files gone")


# ================================================================ the part a job holds
class Holds(Base):
    """A JOB HOLDS ITS MODEL, AND WITH IT THE PROGRAM, FROM start() TO ITS END.
    The hold was once taken only inside the worker's own thread, which begins
    after the last piece: for the whole of a capture (as long as the video
    plays) Settings could take the model away, and the recording was lost to a
    failure that named nothing.  getstt.remove is refused while `using` is held
    (tests/test_getstt.py); what is pinned here is that a job holds it, at
    every moment it is alive, and lets it go at every end."""

    def held(self):
        return list(self.gs._using)

    def test_a_capture_holds_its_model_from_start_through_every_piece_to_its_end(self):
        got = self.start_yt(model=LARGE)
        job = got["job"]
        self.assertEqual(self.held(), [LARGE], "held before a piece has come: nothing has run yet")
        sttjobs.audio(job, 0, self.pcm(1), False)
        self.assertEqual(self.held(), [LARGE], "and while it is being recorded")
        sttjobs.audio(job, 16000, self.pcm(1), False)
        self.assertEqual(self.held(), [LARGE])
        sttjobs.audio(job, 32000, self.pcm(1), True)
        self.until(lambda: sttjobs.status(job)["state"] != "queued", "the worker began")
        self.assertEqual(self.held(), [LARGE], "and while the worker has it")
        self.assertEqual(self.done(job)["state"], "done")
        self.assertEqual(self.held(), [], "and it is let go in the same breath as `done` is said")

    def test_it_holds_one_model_and_not_the_other(self):
        self.start_yt(model=TURBO)
        self.assertEqual(self.held(), [TURBO])
        self.assertNotIn(LARGE, self.held(), "the model it does not use may be taken away")

    def test_every_end_of_a_job_lets_its_part_go(self):
        # cancelled
        job = self.start_yt()["job"]
        sttjobs.audio(job, 0, self.pcm(1), False)
        self.assertEqual(self.held(), [TURBO])
        sttjobs.cancel(job)
        self.assertEqual(self.held(), [], "cancelled")
        # a recording too short to be one
        job = self.start_yt()["job"]
        self.assertEqual(self.held(), [TURBO])
        sttjobs.audio(job, 0, self.pcm(0.2), False)
        self.refused(sttjobs.audio, job, 3200, b"", True)
        self.assertEqual(self.held(), [], "no sound")
        # a capture that stopped arriving
        job = self.start_yt()["job"]
        sttjobs.audio(job, 0, self.pcm(1), False)
        self.assertEqual(self.held(), [TURBO])
        sttjobs.JOBS[job]["touched"] -= sttjobs.IDLE + 1
        self.assertEqual(sttjobs.status(job)["state"], "failed")
        self.assertEqual(self.held(), [], "abandoned")
        # a worker that could not load the model
        self.fake(cpu_load_error="cannot open model.bin")
        job = self.start_yt()["job"]
        sttjobs.audio(job, 0, self.pcm(1), True)
        self.assertEqual(self.done(job)["state"], "failed")
        self.assertEqual(self.held(), [], "failed")
        # a film that is transcribed
        self.fake()
        job = self.start_film()["job"]
        self.assertEqual(self.done(job)["state"], "done")
        self.assertEqual(self.held(), [], "a film, done")
        # a server that is stopping
        job = self.start_yt()["job"]
        sttjobs.audio(job, 0, self.pcm(1), False)
        self.assertEqual(self.held(), [TURBO])
        sttjobs.stop_all()
        self.assertEqual(self.held(), [], "stopped")

    def test_a_job_lets_go_of_its_own_hold_only_and_only_once(self):
        # an install holds the same model while it fetches it (getstt.build): the end
        # of a job, or a second look at an ended one, must not undo THAT hold
        with self.gs.using(TURBO):
            job = self.start_yt()["job"]
            self.assertEqual(self.held(), [TURBO, TURBO])
            sttjobs.audio(job, 0, self.pcm(1), False)
            sttjobs.JOBS[job]["touched"] -= sttjobs.IDLE + 1
            self.assertEqual(sttjobs.status(job)["state"], "failed")
            self.assertEqual(self.held(), [TURBO])
            sttjobs.stop_all()                    # the ended job is still in the table
            sttjobs.cancel(job)
            self.assertEqual(self.held(), [TURBO], "the install's hold is the install's")
        self.assertEqual(self.held(), [])


# ================================================================= tokens and answers
class Answers(Base):
    TOKENS = ["../x", "../../etc/passwd", "/etc/passwd", "a\0" + "b" * 14, "x" * 10000, 5, None,
              ["a"], {"a": 1}, "", " " * 16, "A" * 15, "A" * 17, "A" * 15 + "/", "..%2f" * 4,
              "ف" * 16, "A" * 15 + "\n", "A" * 16 + "\n", "A" * 16 + "\n\n"]

    def test_a_token_that_is_not_one_reaches_no_table_and_no_file(self):
        good = self.start_yt()["job"]
        before = self.tmp()
        for token in self.TOKENS:
            for name, fn, args in (("status", sttjobs.status, ()), ("result", sttjobs.result, ()),
                                   ("cancel", sttjobs.cancel, ()),
                                   ("audio", sttjobs.audio, (0, b"\0\0", False)),
                                   ("marks", sttjobs.marks, ([[1, 1]],)),
                                   ("wave", sttjobs.wave, (20, [0.5]))):
                with self.subTest(route=name, token=repr(token)[:30]):
                    status, body = self.refused(fn, token, *args)
                    self.assertEqual((status, body["code"]), (404, "no-such-job"))
        self.assertEqual(self.tmp(), before, "no file was made or touched")
        self.assertFalse(os.path.exists(wavefile.hold_dir()))
        self.assertEqual(list(sttjobs.JOBS), [good])
        self.assertEqual(sttjobs.JOBS[good]["have"], 0)

    def test_a_token_that_is_shaped_right_but_unknown_is_not_here(self):
        for name, fn, args in (("status", sttjobs.status, ()), ("result", sttjobs.result, ()),
                               ("audio", sttjobs.audio, (0, b"\0\0", False)),
                               ("marks", sttjobs.marks, ([[1, 1]],)),
                               ("wave", sttjobs.wave, (20, [0.5]))):
            status, body = self.refused(fn, "Z" * 16, *args)
            self.assertEqual((status, body["code"], body["error"]),
                             (404, "no-such-job", "That transcription is not here any more "
                              "(Parseh may have been restarted)."), name)

    def test_an_unforeseen_failure_is_a_sentence_and_never_a_traceback(self):
        with mock.patch.object(sttjobs, "_tmp", side_effect=RuntimeError("Traceback (most recent "
                                                                        "call last): boom /home/x.py")):
            body, status = sttjobs.call(sttjobs.start, {"kind": "film", "path": self.film()},
                                        "fa", TURBO, "cpu")
        self.assertEqual((status, body), (500, {"ok": False, "code": "failed",
                                                "error": "Transcription failed."}))
        self.assertIn("boom", self.log.getvalue(), "it went to the server's log")

    def test_every_refusal_is_a_sentence_and_a_slug_and_no_answer_has_a_traceback(self):
        seen = []
        for fn, args in [(sttjobs.start, ({"kind": "film", "path": "x"}, "fa", TURBO, "cpu")),
                         (sttjobs.start, ({"kind": "youtube", "id": "bad"}, "fa", TURBO, "cpu")),
                         (sttjobs.start, ({"kind": "youtube", "id": YT}, "fa", "small", "cpu")),
                         (sttjobs.start, ({"kind": "youtube", "id": YT}, "fa", TURBO, "gpu")),
                         (sttjobs.start, ({"kind": "youtube", "id": YT}, "xx", TURBO, "cpu")),
                         (sttjobs.start, ({"kind": "youtube", "id": YT}, "fa", TURBO, "cuda")),
                         (sttjobs.status, ("Q" * 16,)), (sttjobs.result, ("Q" * 16,)),
                         (sttjobs.audio, ("Q" * 16, 0, b"", False)),
                         (sttjobs.source_of, ({"source": "film", "path": 5, "lang": "fa"},))]:
            body, status = sttjobs.call(fn, *args)
            seen.append(body)
            self.assertFalse(body["ok"])
            self.assertTrue(body["error"].strip() and body["code"].strip(), body)
        text = json.dumps(seen)
        for word in ("Traceback", 'File "', ".py", "line ", "Error:", "Exception", "0x"):
            self.assertNotIn(word, text)

    def test_the_hold_of_a_waveform_follows_the_job_only_by_its_token(self):
        # nothing of a job is readable by anything but its own token; a token
        # made by the client (any 16 characters) holds nothing
        job = self.start_yt()["job"]
        sttjobs.audio(job, 0, stt_fakes.pcm(1), False)
        self.assertEqual(self.refused(sttjobs.wave, "B" * 16, 20, [0.5])[1]["code"], "no-such-job")
        self.assertFalse(wavefile.held("B" * 16))


# ====================================================================== the server's hooks
class Hooks(Base):
    def test_start_up_sweeps_the_temporary_folder_and_the_old_holds(self):
        os.makedirs(self.gs.TMP_DIR)
        stale = os.path.join(self.gs.TMP_DIR, "stt-old.pcm")
        open(stale, "wb").close()
        wavefile.hold("C" * 16, 20, [0.5])
        old = wavefile.hold_path("C" * 16)
        then = time.time() - 40 * 86400
        os.utime(old, (then, then))
        sttjobs.startup()
        self.assertFalse(os.path.exists(stale))
        self.assertFalse(os.path.exists(old))
        self.assertEqual(self.gs.swept, [1])

    def test_start_up_needs_no_getstt(self):
        with mock.patch.dict(sys.modules, {"getstt": None}):
            sttjobs.startup()                       # no error, nothing made
        self.assertFalse(os.path.exists(os.path.join(self.root, "stt")))

    def test_the_slot_is_shown_to_the_reading_help_page(self):
        self.assertFalse(sttjobs.busy())
        self.start_yt()
        self.assertTrue(sttjobs.busy())

    def test_the_child_is_started_so_that_a_killed_server_takes_it_along(self):
        # what tests/test_stt_route.py drives for real (SIGTERM, and SIGKILL); here,
        # what it rests on: a group of its own, the kernel's word (Linux), and the
        # worker's look for its parent (every platform)
        import inspect
        self.assertIn("prctl", inspect.getsource(sttjobs._preexec))
        spawn = inspect.getsource(sttjobs._spawn)
        self.assertIn("start_new_session", spawn)
        self.assertIn("CREATE_NEW_PROCESS_GROUP", spawn)
        self.assertIn("preexec_fn", spawn)
        self.assertIn('"parent": os.getpid()', inspect.getsource(sttjobs._spec))


if __name__ == "__main__":
    unittest.main()
