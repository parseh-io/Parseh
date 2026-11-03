# SPDX-License-Identifier: GPL-3.0-or-later
"""lib/sttworker.py, run as the child it is, against a stand-in faster-whisper.

    python3 -m unittest tests/test_stt_worker.py

No model, no CUDA, no PyAV: tests/fixtures/stt_runtime/faster_whisper is put
on the worker's PYTHONPATH by tests/stt_fakes.py and RECORDS how it was built
and called, so each of the brief's device rules is read off what the worker
really did (brief tests 7-15 and 28):

    7   CPU is device="cpu", compute_type="int8"
    8/9 Automatic is the CPU unless the card is ready, and then the card
    10  an explicit CPU never so much as builds a model on the card
    12  an Automatic card failure falls back ONCE, said in `fell_back`
    13  an explicit card failure is the card's error, and no fall back
    14  out of memory on the card in Automatic falls back too
    15  each of the eleven language codes reaches transcribe(language=...)
    28  a device or precision that is not on the worker's short lists never
        reaches CTranslate2 (table-driven)
plus the lazy `libcublas not found` that arrives INSIDE the segment generator,
progress from the last segment over the duration, a film decoded by the
runtime, and a worker that goes when its parent does.
Needs numpy (environment.yml has it), as the worker does.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import stt_fakes                                              # noqa: E402

WORKER = os.path.join(ROOT, "lib", "sttworker.py")


def _worker():
    """The worker's own module, read for its sentences (it is stdlib only, and
    nothing at import runs; everything else here is the child, run for real)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("sttworker_read", WORKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


worker = _worker()
# every language Parseh ships (the registry's _shipped), not a copy of the list
ELEVEN = __import__("json").loads(open(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                                                    "lib", "languages.json"), encoding="utf-8").read())["_shipped"]
LAZY = "Library libcublas.so.12 is not found or cannot be loaded"
OOM = "CUDA failed with error out of memory"


class Worker(unittest.TestCase):
    """Base: a fake getstt in a temporary root, and a way to run the child."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = self.td.name
        self.fake = stt_fakes.make(self.root)
        self.model = self.fake.model_dir("large-v3-turbo")

    def pcm(self, seconds=3.0, name="rec.pcm"):
        path = os.path.join(self.root, name)
        with open(path, "wb") as f:
            f.write(stt_fakes.pcm(seconds))
        return path

    def spec(self, **over):
        # the default recording is made only when nobody named one (`rec.pcm` is
        # one file: a longer one a test wrote first must not be written over)
        s = {"source_path": over["source_path"] if "source_path" in over else self.pcm(),
             "audio_kind": "pcm16", "lang": "fa",
             "model_path": self.model, "device": "cpu", "cpu_threads": 5,
             "compute": {"cpu": "int8", "cuda": ["int8_float16", "float16"]},
             "mode": "auto", "film": None, "parent": os.getpid()}
        s.update(over)
        return s

    def run_spec(self, spec, timeout=60, input_text=None):
        """The worker's own run -> (return code, the JSON lines, its stderr)."""
        path = os.path.join(self.root, "spec.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f)
        env = dict(os.environ)
        env.update(self.fake.worker_env())
        env.update(PYTHONSAFEPATH="1", PYTHONNOUSERSITE="1")
        p = subprocess.run([sys.executable, "-B", "-u", WORKER, path], env=env,
                           capture_output=True, text=True, timeout=timeout, input=input_text)
        msgs = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
        return p.returncode, msgs, p.stderr

    def go(self, fake=None, **over):
        if fake is not None:
            stt_fakes.configure(self.root, fake=fake)
        return self.run_spec(self.spec(**over))

    def built(self):
        return [(r["device"], r["compute_type"]) for r in stt_fakes.records(self.root, "construct")]

    def heard(self):
        return [r["device"] for r in stt_fakes.records(self.root, "transcribe")]

    @staticmethod
    def kinds(msgs):
        return [m["t"] for m in msgs]

    @staticmethod
    def last(msgs, t):
        return [m for m in msgs if m["t"] == t][-1]


class Devices(Worker):
    def test_cpu_is_cpu_and_int8_with_the_threads_it_was_told(self):
        rc, msgs, _ = self.go(mode="cpu", device="cpu", cpu_threads=5)
        self.assertEqual(rc, 0)
        (rec,) = stt_fakes.records(self.root, "construct")
        self.assertEqual((rec["device"], rec["compute_type"], rec["cpu_threads"]), ("cpu", "int8", 5))
        self.assertEqual(rec["path"], self.model)
        self.assertTrue(rec["local_files_only"], "the model is a folder here; nothing is asked of a hub")
        self.assertEqual(rec["rest"], [], "nothing else is passed to the loader")
        self.assertEqual(self.last(msgs, "device"), {"t": "device", "device": "cpu", "fell_back": False})

    def test_explicit_cpu_never_builds_a_model_on_the_card(self):
        # even when the card is ready and the spec's own `device` says cuda
        stt_fakes.configure(self.root, cuda_ready=True)
        rc, msgs, _ = self.go(mode="cpu", device="cuda")
        self.assertEqual(rc, 0)
        self.assertEqual(self.built(), [("cpu", "int8")])
        self.assertNotIn("cuda", self.heard())
        self.assertEqual([m["device"] for m in msgs if m["t"] == "device"], ["cpu"])

    def test_automatic_is_the_cpu_when_the_card_is_not_ready(self):
        rc, msgs, _ = self.go(mode="auto", device="cpu")
        self.assertEqual((rc, self.built()), (0, [("cpu", "int8")]))

    def test_automatic_is_the_card_when_it_is_ready_and_asks_for_the_lighter_precision(self):
        rc, msgs, _ = self.go(mode="auto", device="cuda")
        self.assertEqual(rc, 0)
        self.assertEqual(self.built(), [("cuda", "int8_float16")])
        self.assertEqual(self.heard(), ["cuda"])
        self.assertEqual(self.last(msgs, "device"), {"t": "device", "device": "cuda", "fell_back": False})
        self.assertEqual(self.last(msgs, "done")["language"], "fa")

    def test_a_card_that_lacks_int8_float16_is_asked_for_float16(self):
        rc, msgs, _ = self.go({"cuda_reject_compute": ["int8_float16"]}, mode="cuda", device="cuda")
        self.assertEqual(rc, 0)
        self.assertEqual(self.built(), [("cuda", "int8_float16"), ("cuda", "float16")])
        self.assertEqual(self.heard(), ["cuda"])

    def test_a_card_that_does_neither_is_a_card_failure(self):
        rc, msgs, _ = self.go({"cuda_reject_compute": ["int8_float16", "float16"]},
                              mode="cuda", device="cuda")
        self.assertEqual(rc, 2)
        self.assertEqual(self.last(msgs, "error")["code"], "gpu-error")
        self.assertEqual(self.built(), [("cuda", "int8_float16"), ("cuda", "float16")])

    def test_automatic_falls_back_once_when_the_card_will_not_load(self):
        rc, msgs, err = self.go({"cuda_load_error": "boom"}, mode="auto", device="cuda")
        self.assertEqual(rc, 0)
        self.assertEqual(self.built(), [("cuda", "int8_float16"), ("cpu", "int8")],
                         "one try on the card, then ONE on the CPU, and no third")
        devices = [(m["device"], m["fell_back"]) for m in msgs if m["t"] == "device"]
        self.assertEqual(devices, [("cuda", False), ("cpu", True)])
        self.assertEqual(self.kinds(msgs).count("done"), 1)
        self.assertIn("boom", err, "the technical error is kept for the server's log")

    def test_explicit_card_failure_is_reported_and_never_switched(self):
        rc, msgs, err = self.go({"cuda_load_error": "boom"}, mode="cuda", device="cuda")
        self.assertEqual(rc, 2)
        self.assertEqual(self.built(), [("cuda", "int8_float16")])
        self.assertEqual(self.kinds(msgs).count("done"), 0)
        e = self.last(msgs, "error")
        self.assertEqual(e["code"], "gpu-error")
        self.assertIn("CUDA was requested but could not be initialized", e["say"])
        self.assertIn("Choose Automatic or CPU", e["say"], "and what to do about it")
        self.assertNotIn("boom", e["say"], "no technical text for the person")
        self.assertEqual([m["device"] for m in msgs if m["t"] == "device"], ["cuda"])

    def test_the_lazy_libcublas_error_inside_the_generator_falls_back_in_automatic(self):
        # ctranslate2 loads the model on a card with no cuBLAS and fails only when
        # the first segment is asked for: exactly what a probe cannot see
        rc, msgs, err = self.go({"cuda_lazy_error": LAZY}, mode="auto", device="cuda")
        self.assertEqual(rc, 0)
        self.assertEqual(self.built(), [("cuda", "int8_float16"), ("cpu", "int8")])
        self.assertEqual(self.heard(), ["cuda", "cpu"])
        self.assertEqual([(m["device"], m["fell_back"]) for m in msgs if m["t"] == "device"],
                         [("cuda", False), ("cpu", True)])
        self.assertIn("libcublas", err)
        done = self.last(msgs, "done")
        self.assertEqual(len(done["segments"]), 2, "the CPU's own, from the start")

    def test_the_lazy_libcublas_error_is_the_cards_in_an_explicit_choice(self):
        rc, msgs, _ = self.go({"cuda_lazy_error": LAZY}, mode="cuda", device="cuda")
        self.assertEqual(rc, 2)
        self.assertEqual(self.heard(), ["cuda"])
        self.assertEqual(self.last(msgs, "error")["code"], "gpu-error")

    def test_out_of_memory_on_the_card_falls_back_in_automatic(self):
        rc, msgs, _ = self.go({"cuda_load_error": OOM}, mode="auto", device="cuda")
        self.assertEqual(rc, 0)
        self.assertEqual(self.built(), [("cuda", "int8_float16"), ("cpu", "int8")])
        self.assertTrue(self.last(msgs, "device")["fell_back"])

    def test_out_of_memory_while_transcribing_falls_back_too(self):
        rc, msgs, _ = self.go({"cuda_lazy_error": OOM}, mode="auto", device="cuda")
        self.assertEqual((rc, self.heard()), (0, ["cuda", "cpu"]))

    def test_out_of_memory_on_the_card_is_said_so_when_the_card_was_chosen(self):
        rc, msgs, _ = self.go({"cuda_load_error": OOM}, mode="cuda", device="cuda")
        self.assertEqual(rc, 2)
        e = self.last(msgs, "error")
        self.assertEqual(e["code"], "gpu-memory")
        self.assertIn("ran out of memory", e["say"])
        self.assertEqual(self.built(), [("cuda", "int8_float16")])

    def test_only_one_fall_back_and_then_it_is_an_error(self):
        rc, msgs, _ = self.go({"cuda_load_error": "boom",
                               "cpu_load_error": "std::bad_alloc"}, mode="auto", device="cuda")
        self.assertEqual(rc, 2)
        self.assertEqual(self.built(), [("cuda", "int8_float16"), ("cpu", "int8")])
        self.assertEqual(self.last(msgs, "error")["code"], "no-memory")

    def test_cpu_failures_are_sentences(self):
        for fake, code, say in [
                ({"cpu_load_error": "cannot open model.bin"}, "model-load",
                 "The model could not be loaded."),
                ({"cpu_lazy_error": "kernel exploded"}, "failed", "Transcription failed."),
                ({"cpu_load_error": "std::bad_alloc: out of memory"}, "no-memory",
                 "The computer ran out of memory for this model.")]:
            with self.subTest(fake=fake):
                rc, msgs, _ = self.go(fake, mode="cpu", device="cpu")
                self.assertEqual(rc, 2)
                e = self.last(msgs, "error")
                self.assertEqual((e["code"], e["say"]), (code, say))
                self.assertNotIn("Traceback", e["say"])

    def test_a_missing_runtime_is_a_sentence_too(self):
        path = os.path.join(self.root, "spec.json")
        with open(path, "w") as f:
            json.dump(self.spec(), f)
        env = dict(os.environ, PYTHONPATH=os.path.join(self.root, "nowhere"), PYTHONSAFEPATH="1")
        p = subprocess.run([sys.executable, "-B", WORKER, path], env=env,
                           capture_output=True, text=True, timeout=60)
        msgs = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
        self.assertEqual(p.returncode, 2)
        self.assertEqual(self.last(msgs, "error")["code"], "broken")
        # speech to text has a door of its own in Settings, and is not under Reading help
        self.assertEqual(self.last(msgs, "error")["say"],
                         "Speech to text could not start. Reinstall it in Settings, under Speech to text.")
        for code, say in worker.SAYS.items():
            self.assertNotIn("Reading help", say, code)

    def test_a_program_that_is_there_but_will_not_load_is_the_same_sentence(self):
        # on Windows a DLL that cannot be loaded is an OSError when the program is imported (the
        # loader's own, WinError 126), and not an ImportError: it is "broken", not "failed"
        rt = os.path.join(self.root, "brokenrt")
        os.makedirs(os.path.join(rt, "faster_whisper"))
        with open(os.path.join(rt, "faster_whisper", "__init__.py"), "w") as f:
            f.write("raise OSError('[WinError 126] The specified module could not be found')\n")
        path = os.path.join(self.root, "spec.json")
        with open(path, "w") as f:
            json.dump(self.spec(), f)
        env = dict(os.environ, PYTHONPATH=rt, PYTHONSAFEPATH="1")
        p = subprocess.run([sys.executable, "-B", WORKER, path], env=env,
                           capture_output=True, text=True, timeout=60)
        msgs = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
        self.assertEqual(p.returncode, 2)
        e = self.last(msgs, "error")
        self.assertEqual((e["code"], e["say"]), ("broken", worker.SAYS["broken"]))
        self.assertNotIn("WinError", p.stdout, "the loader's words are for the server's log")
        self.assertIn("WinError 126", p.stderr)


class Words(Worker):
    def test_backend_word_scores_and_genuine_alternatives_are_preserved(self):
        rc, msgs, _ = self.go({"segments": [[0, 1, " loro anno"]],
            "word_evidence": {"loro": {"score": None}, "anno": {"score": .51,
                "alternatives": [{"text": "hanno", "score": .37}]}}})
        self.assertEqual(rc, 0)
        segment = self.last(msgs, "done")["segments"][0]
        self.assertEqual(segment["text"], " loro anno")
        self.assertEqual(segment["asr_words"], segment["words"])
        first, second = segment["asr_words"]
        self.assertIsNone(first["score"])
        self.assertFalse(first["alternatives_available"])
        self.assertEqual(first["asr_alternatives"], [])
        self.assertEqual(second["score"], .51)
        self.assertTrue(second["alternatives_available"])
        self.assertEqual(second["asr_alternatives"], [{"text": "hanno", "score": .37}])
        self.assertEqual((second["start"], second["end"]), (.5, 1.0))

    def test_each_of_the_eleven_language_codes_reaches_transcribe(self):
        for code in ELEVEN:
            with self.subTest(lang=code):
                open(os.path.join(self.root, "fake.log"), "w").close()
                rc, msgs, _ = self.go(lang=code)
                self.assertEqual(rc, 0)
                (rec,) = stt_fakes.records(self.root, "transcribe")
                self.assertEqual(rec["language"], code)
                self.assertEqual(self.last(msgs, "done")["language"], code)

    def test_the_settings_of_a_subtitle_are_the_settings_of_the_call(self):
        self.go()
        (rec,) = stt_fakes.records(self.root, "transcribe")
        self.assertEqual((rec["beam_size"], rec["vad_filter"], rec["task"]), (5, True, "transcribe"),
                         "explicit language, beam 5, VAD on, and NO translation")
        self.assertEqual(rec["rest"], ['condition_on_previous_text', 'temperature', "word_timestamps"],
                         "one Whisper pass asks for words, and no prompt reaches it")
        self.assertEqual((rec["audio_type"], rec["dtype"]), ("ndarray", "float32"))
        self.assertEqual(rec["samples"], 3 * 16000)
        self.assertAlmostEqual(rec["peak"], 12000 / 32768.0, places=3, msg="int16 scaled to -1..1")

    def test_text_comes_back_as_whisper_gave_it(self):
        said = [[0.0, 2.0, " سلام، ببخشید سیب چند است؟"], [2.0, 4.5, " こんにちは。"],
                [4.5, 6.0, " नमस्ते!"], [6.0, 8.0, " 你好，世界"], [8.0, 9.0, " «Ça va?» — Ünïcödé…"]]
        rc, msgs, _ = self.go({"segments": said}, source_path=self.pcm(10))
        self.assertEqual(rc, 0)
        got = self.last(msgs, "done")["segments"]
        self.assertEqual([s["text"] for s in got], [t for _a, _b, t in said])
        self.assertEqual([(s["start"], s["end"]) for s in got], [(a, b) for a, b, _t in said])

    def test_one_pass_carries_each_whisper_word_and_its_time(self):
        rc, msgs, _ = self.go({"segments": [[1.0, 3.0, " hello world"]]}, source_path=self.pcm(4))
        self.assertEqual(rc, 0)
        done = self.last(msgs, "done")
        self.assertEqual(done["word_source"], "whisper")
        self.assertEqual([(w["text"], w["start"], w["end"]) for w in done["segments"][0]["words"]],
                         [("hello", 1.0, 2.0), ("world", 2.0, 3.0)])

    def test_language_specific_profile_and_missing_required_timestamps(self):
        rc, msgs, _ = self.go({'segments': [[0, 2, ' سلام دنیا']]}, model_id='fa-fast',
                              decoding={'beam_size':1, 'temperature':99, 'task':'translate'})
        self.assertEqual(rc, 0)
        call = stt_fakes.records(self.root, 'transcribe')[-1]
        profile = worker.catalogue().decoding('fa-fast')
        self.assertEqual((call['language'], call['task'], call['beam_size']), ('fa', 'transcribe', profile['beam_size']))
        self.assertEqual(call['options']['temperature'], 0)
        self.assertEqual(call['options']['condition_on_previous_text'], profile['condition_on_previous_text'])
        rc, msgs, _ = self.go({'segments': [[0, 2, ' سلام دنیا']], 'no_words':True}, model_id='fa-fast')
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.last(msgs, 'error')['code'], 'word-timestamps')
        self.assertNotIn('done', self.kinds(msgs))

    def test_numpy_word_probability_is_preserved_with_language_specific_model(self):
        rc, msgs, _ = self.go({'segments': [[0, 2, ' سلام']], 'numpy_word_scalars':'float32',
                              'word_evidence': {'سلام': {'score':.375}}}, model_id='fa-fast')
        self.assertEqual(rc, 0)
        word = self.last(msgs, 'done')['segments'][0]['words'][0]
        self.assertEqual((word['start'], word['end'], word['score']), (0, 2, .375))

    def test_the_wire_is_ascii_and_gives_the_unicode_back_exactly(self):
        # a Windows console is not UTF-8: nothing but ASCII crosses the pipe
        path = os.path.join(self.root, "spec.json")
        with open(path, "w") as f:
            json.dump(self.spec(), f)
        stt_fakes.configure(self.root, fake={"segments": [[0, 1, " سلام"]]})
        env = dict(os.environ)
        env.update(self.fake.worker_env())
        env["PYTHONSAFEPATH"] = "1"
        p = subprocess.run([sys.executable, "-B", "-u", WORKER, path], env=env, capture_output=True)
        p.stdout.decode("ascii")
        self.assertIn(b"\\u0633", p.stdout)

    def test_progress_is_the_last_segment_over_the_duration(self):
        stt_fakes.configure(self.root, fake={"delay": 0.35, "segments": [
            [0, 3, " a"], [3, 6, " b"], [6, 9, " c"], [9, 12, " d"]]})
        rc, msgs, _ = self.run_spec(self.spec(source_path=self.pcm(12)))
        self.assertEqual(rc, 0)
        progress = [(m["done"], m["total"]) for m in msgs if m["t"] == "progress"]
        self.assertEqual(progress[0], (0.0, 12.0), "decoded: how long it is, before anything else")
        self.assertTrue(all(t == 12.0 for _d, t in progress))
        dones = [d for d, _t in progress]
        self.assertEqual(dones, sorted(dones))
        self.assertIn(6.0, dones, "the end of a segment is what has been done")
        self.assertEqual(progress[-1], (12.0, 12.0))
        order = self.kinds(msgs)
        self.assertLess(order.index("device"), order.index("loading"))
        self.assertLess(order.index("loading"), len(order) - 1)
        self.assertEqual(order[-1], "done")

    def test_a_recording_with_no_sound_or_no_file_is_a_sentence(self):
        empty = os.path.join(self.root, "empty.pcm")
        open(empty, "wb").close()
        rc, msgs, _ = self.go(source_path=empty)
        self.assertEqual((rc, self.last(msgs, "error")["code"]), (2, "no-sound"))
        rc, msgs, _ = self.go(source_path=os.path.join(self.root, "gone.pcm"))
        e = self.last(msgs, "error")
        self.assertEqual((rc, e["code"], e["say"]), (2, "audio-gone",
                                                     "The temporary recording disappeared."))
        self.assertEqual(stt_fakes.records(self.root), [], "no model was built for either")


class Films(Worker):
    def film(self, seconds=4, name="film.mp4"):
        return stt_fakes.write_wav(os.path.join(self.root, name), seconds)

    def stat(self, path):
        st = os.stat(path)
        return [st.st_size, st.st_mtime_ns, st.st_ino]

    def test_a_film_is_decoded_by_the_runtime_from_its_path(self):
        film = self.film(4)
        rc, msgs, _ = self.go(source_path=film, audio_kind="media", film=self.stat(film))
        self.assertEqual(rc, 0)
        (rec,) = stt_fakes.records(self.root, "transcribe")
        self.assertEqual((rec["audio_type"], rec["samples"]), ("ndarray", 4 * 16000))
        self.assertEqual(self.last(msgs, "progress")["total"], 4.0)

    def test_a_film_that_changed_since_it_was_named_is_not_read(self):
        film = self.film(2)
        stat = self.stat(film)
        with open(film, "ab") as f:
            f.write(b"\0" * 10)
        rc, msgs, _ = self.go(source_path=film, audio_kind="media", film=stat)
        e = self.last(msgs, "error")
        self.assertEqual((rc, e["code"]), (2, "film-changed"))
        self.assertEqual(stt_fakes.records(self.root), [])

    def test_a_film_that_cannot_be_decoded_is_a_sentence(self):
        bad = os.path.join(self.root, "bad.mp4")
        with open(bad, "wb") as f:
            f.write(b"not a film at all")
        rc, msgs, err = self.go(source_path=bad, audio_kind="media", film=self.stat(bad))
        e = self.last(msgs, "error")
        self.assertEqual((rc, e["code"], e["say"]), (2, "film-undecodable",
                                                     "The local film could not be decoded."))
        self.assertNotIn("Invalid data", e["say"])
        self.assertIn("Invalid data", err, "the reason is in the log")

    def test_a_film_that_is_gone_or_not_absolute_is_refused(self):
        rc, msgs, _ = self.go(source_path=os.path.join(self.root, "gone.mp4"), audio_kind="media")
        self.assertEqual(self.last(msgs, "error")["code"], "film-undecodable")
        rc, msgs, _ = self.go(source_path="film.mp4", audio_kind="media")
        self.assertEqual(self.last(msgs, "error")["code"], "bad-spec")

    def test_a_film_gets_no_waveform_the_worker_only_listens(self):
        # the owner: nothing is written for a film's waveform (the player draws it
        # from the film itself), so the worker computes no peaks and says none
        film = self.film(3)
        rc, msgs, _ = self.go(source_path=film, audio_kind="media", film=self.stat(film))
        self.assertEqual(rc, 0)
        self.assertEqual(set(self.kinds(msgs)), {"progress", "device", "loading", "done"})


class Hostile(Worker):
    """Brief tests 27 and 28: nothing the spec carries that is not on the
    worker's short lists ever reaches the model loader."""

    def test_a_device_a_precision_or_a_path_off_the_lists_never_reaches_the_loader(self):
        stt_fakes.configure(self.root, cuda_ready=True)
        good = self.spec()
        table = [
            ("device", "cuda:0"), ("device", "gpu"), ("device", "CPU"), ("device", ""),
            ("device", None), ("device", 1), ("device", ["cpu"]), ("device", "cpu\0"),
            ("mode", "gpu"), ("mode", "cuda:0"), ("mode", "AUTO"), ("mode", None), ("mode", 5),
            ("compute", {"cpu": "float32", "cuda": ["int8_float16"]}),
            ("compute", {"cpu": "int8_float16", "cuda": ["int8_float16"]}),
            ("compute", {"cpu": "int8", "cuda": ["float32"]}),
            ("compute", {"cpu": "int8", "cuda": ["int8_float16", "bfloat16"]}),
            ("compute", {"cpu": "int8", "cuda": []}),
            ("compute", {"cpu": "int8", "cuda": "float16"}),
            ("compute", {"cpu": "int8"}), ("compute", {"cuda": ["float16"]}),
            ("compute", "int8"), ("compute", None), ("compute", ["int8"]),
            ("cpu_threads", 0), ("cpu_threads", -1), ("cpu_threads", 10 ** 9),
            ("cpu_threads", "8"), ("cpu_threads", 4.5), ("cpu_threads", True),
            ("cpu_threads", None),
            ("model_path", "large-v3"), ("model_path", "../models/large-v3"),
            ("model_path", "/etc/passwd"), ("model_path", os.path.join(self.root, "nope")),
            ("model_path", self.model + "\0"), ("model_path", ""), ("model_path", None),
            ("model_path", 5), ("model_path", ["/"]),
            ("source_path", "rec.pcm"), ("source_path", "../rec.pcm"), ("source_path", ""),
            ("source_path", None), ("source_path", "/x\0y"), ("source_path", 7),
            ("audio_kind", "url"), ("audio_kind", "pcm"), ("audio_kind", None),
            ("lang", "../fa"), ("lang", "fa\0"), ("lang", "fa\n"), ("lang", "FA"), ("lang", "persian"),
            ("lang", ""), ("lang", None), ("lang", 5), ("lang", "f"), ("lang", "x" * 5000),
            ("film", "x"), ("film", [1, 2]), ("film", [1, 2, "3"]),
        ]
        for key, value in table:
            with self.subTest(key=key, value=repr(value)[:40]):
                spec = dict(good)
                spec[key] = value
                rc, msgs, _ = self.run_spec(spec)
                self.assertEqual(rc, 2, msgs)
                self.assertEqual(self.last(msgs, "error")["code"], "bad-spec")
                self.assertEqual(self.kinds(msgs), ["error"])
        self.assertEqual(stt_fakes.records(self.root), [],
                         "not one of them reached WhisperModel or transcribe()")

    def test_a_spec_that_is_not_a_spec(self):
        for text in ("", "not json", "[]", "5", "null", '"x"', "[" * 200000, '{"a": 1}'):
            path = os.path.join(self.root, "spec.json")
            with open(path, "w") as f:
                f.write(text)
            env = dict(os.environ)
            env.update(self.fake.worker_env())
            p = subprocess.run([sys.executable, "-B", WORKER, path], env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 2, text[:20])
            self.assertEqual(json.loads(p.stdout.splitlines()[-1])["code"], "bad-spec")
        for argv in ([], ["a", "b"], [os.path.join(self.root, "missing.json")]):
            p = subprocess.run([sys.executable, "-B", WORKER] + argv, capture_output=True, text=True,
                               timeout=60)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(json.loads(p.stdout.splitlines()[-1])["code"], "bad-spec")
        self.assertEqual(stt_fakes.records(self.root), [])

    # (which precisions and devices can reach CTranslate2 is read off what the worker does, in the
    # table above and in the built() assertions: a scan of its text for `compute_type="..."` saw none
    # of the forms the worker is written in, and passed for a mutant that used another quote)
    def test_nothing_heavy_is_imported_until_a_job_is_run(self):
        with open(WORKER, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("import faster_whisper", src.split("def run(spec)")[0],
                         "nothing heavy is imported until a job is run")


class Parent(Worker):
    @unittest.skipIf(os.name == "nt", "the parent's pid is looked for the same way, but not here")
    def test_the_worker_goes_when_its_parent_is_gone(self):
        # a parent that lives a moment: the worker, doing slow work, must
        # notice it has died and go, and not go on for an hour with nobody to tell
        parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.0)"])
        stt_fakes.configure(self.root, fake={"delay": 30, "segments": [[0, 1, " a"], [1, 2, " b"]]})
        path = os.path.join(self.root, "spec.json")
        with open(path, "w") as f:
            json.dump(self.spec(parent=parent.pid), f)
        env = dict(os.environ)
        env.update(self.fake.worker_env())
        began = time.time()
        child = subprocess.Popen([sys.executable, "-B", "-u", WORKER, path], env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            parent.wait()
            rc = child.wait(timeout=20)
        finally:
            if child.poll() is None:
                child.kill()
            child.stdout.close()
        self.assertEqual(rc, 3)
        self.assertLess(time.time() - began, 15, "it went, and did not finish its 60 s of work")


if __name__ == "__main__":
    unittest.main()
