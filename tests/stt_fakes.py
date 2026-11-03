# SPDX-License-Identifier: GPL-3.0-or-later
"""Stand-ins for lib/getstt.py and for faster-whisper, for the transcription job's tests.

    fake = stt_fakes.make(root)                    # a module object, as `getstt`
    with stt_fakes.installed(root): ...            # sys.modules["getstt"] = fake
    stt_fakes.configure(root, cuda_ready=True, fake={"cuda_lazy_error": "..."})
    stt_fakes.records(root)                        # what the fake WhisperModel saw

THE FAKE `getstt` follows INTERFACE 1 of the a0.4.1 note to the letter -- the
names lib/sttjobs.py reads, and no others: MODELS, MODES, TMP_DIR, STT_DIR,
runtime_ready, model_ready, model_dir, worker_env, hardware, resolve,
cpu_threads, whisper_code, speech_languages, SpeechError, track, untrack,
stop_all, using, in_use, sweep.  It holds NO state in the process: what is
installed, whether the card is ready and how the fake faster-whisper
behaves are read from small files in `root` at each call, so the same fake
serves an in-process test and a real serve.py in a child process that the
test then changes its mind about.

THE FAKE faster-whisper is tests/fixtures/stt_runtime/faster_whisper, which
`worker_env()` puts on the worker's PYTHONPATH; it records how it was built
(device, compute_type, threads, the model path) in root/fake.log.
"""
import contextlib
import json
import os
from pathlib import Path
import signal
import sys
import types
import wave

HERE = os.path.dirname(os.path.realpath(__file__))
FIXTURE_RUNTIME = os.path.join(HERE, "fixtures", "stt_runtime")

sys.path.insert(0, str(Path(HERE).parent / 'lib'))
import speechmodels
MODELS = speechmodels.MODELS
DEFAULT_INSTALLED = speechmodels.STANDARD_MODELS
MODES = ("auto", "cpu", "cuda")
# Whisper's own list is 100 codes; the ones the tests need, and one it lacks
WHISPER = frozenset("fa ar it ja fr de tr en hi es zh ca af ko yue".split())


class SpeechError(Exception):
    """A human sentence, never a traceback (INTERFACE 1)."""

    def __init__(self, code, say):
        Exception.__init__(self, say)
        self.code, self.say = code, say


def _read(root, name, default):
    try:
        with open(os.path.join(root, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def configure(root, runtime=None, models=None, cuda_ready=None, cuda_name=None, fake=None):
    """Change what the fake reports; anything left out is kept."""
    os.makedirs(root, exist_ok=True)
    state = _read(root, "state.json", {"runtime": True, "models": list(DEFAULT_INSTALLED),
                                       "cuda": {"ready": False, "name": "Fake GPU 8 GB"}})
    if runtime is not None:
        state["runtime"] = bool(runtime)
    if models is not None:
        state["models"] = list(models)
    if cuda_ready is not None:
        state["cuda"]["ready"] = bool(cuda_ready)
    if cuda_name is not None:
        state["cuda"]["name"] = cuda_name
    with open(os.path.join(root, "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f)
    if fake is not None:
        with open(os.path.join(root, "fake.json"), "w", encoding="utf-8") as f:
            json.dump(fake, f)


def records(root, kind=None):
    """Every line the fake WhisperModel wrote, oldest first."""
    out = []
    try:
        with open(os.path.join(root, "fake.log"), encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
    except OSError:
        pass
    return [r for r in out if kind is None or r["kind"] == kind]


_REAL = []


def _real():
    """lib/getstt.py loaded under a name of its own, once: `getstt` in
    sys.modules may already be the fake."""
    if not _REAL:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "getstt_real", os.path.join(os.path.dirname(HERE), "lib", "getstt.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("getstt_real", mod)
        spec.loader.exec_module(mod)
        _REAL.append(mod)
    return _REAL[0]


def make(root):
    """A module standing in for lib/getstt.py, working under `root`."""
    root = os.path.abspath(root)
    configure(root)
    mod = types.ModuleType("getstt")
    mod.ROOT = root
    mod.STT_DIR = os.path.join(root, "stt")
    mod.TMP_DIR = os.path.join(mod.STT_DIR, "tmp")
    mod.MODELS = MODELS
    mod.MODES = MODES
    mod.DEFAULT_MODEL = "large-v3-turbo"
    mod.RUNTIME_PYTHON = "3.12"
    mod.SpeechError = SpeechError
    mod._procs = set()
    mod._using = []
    mod.swept = []
    # what the job asked of getstt, so a test can say what was NEVER asked
    mod.asked = {"model_dir": [], "resolve": [], "whisper_code": []}

    def state():
        return _read(root, "state.json", {"runtime": True, "models": list(DEFAULT_INSTALLED),
                                          "cuda": {"ready": False}})

    def runtime_dir():
        return FIXTURE_RUNTIME if state()["runtime"] else None

    def runtime_ready():
        return bool(state()["runtime"])

    def model_dir(key):
        mod.asked["model_dir"].append(key)
        if not isinstance(key, str) or key not in MODELS:
            raise ValueError("that is not one of the speech models")
        path = os.path.join(mod.STT_DIR, "models", key)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "model.bin"), "wb") as f:
            f.write(b"\0")
        return path

    def model_ready(key):
        return isinstance(key, str) and key in MODELS and key in state()["models"] \
            and runtime_ready()

    def worker_env():
        if not runtime_ready():
            raise SpeechError("not-installed", "Speech to text is not installed.")
        return {"PYTHONPATH": FIXTURE_RUNTIME, "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "STT_FAKE": json.dumps(_read(root, "fake.json", {})),
                "STT_FAKE_LOG": os.path.join(root, "fake.log")}

    def hardware(refresh=False):
        cuda = dict(state()["cuda"])
        cuda.setdefault("name", "")
        cuda.setdefault("memory", 8 << 30)
        return {"cpu": {"available": True, "cores": 4}, "cuda": cuda}

    def resolve(mode):
        mod.asked["resolve"].append(mode)
        if mode not in MODES:
            raise ValueError("that is not a way to process")
        if mode == "cpu":
            return "cpu", "Using the processor."
        ready = hardware()["cuda"]["ready"]
        if mode == "auto":
            return ("cuda", "Using the graphics card.") if ready \
                else ("cpu", "Using the processor.")
        if not ready:
            raise SpeechError("gpu-unavailable",
                              "GPU acceleration is unavailable; CPU mode is still available.")
        return "cuda", "Using the graphics card."

    def cpu_threads():
        return 3

    def whisper_code(lang):
        mod.asked["whisper_code"].append(lang)
        code = (lang or "").strip().lower() if isinstance(lang, str) else ""
        if code not in WHISPER:
            raise SpeechError("unsupported-language",
                              "Speech to text cannot listen for %s." % lang)
        return code

    def speech_languages():
        import languages
        return {c: (c in WHISPER) for c in languages.LANGS}

    def track(proc):
        mod._procs.add(proc)

    def untrack(proc):
        mod._procs.discard(proc)

    def stop_all():
        for proc in list(mod._procs):
            try:
                if os.name == "nt":
                    proc.kill()
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass

    @contextlib.contextmanager
    def using(key):
        mod._using.append(key)
        try:
            yield
        finally:
            mod._using.remove(key)

    def in_use():
        return list(mod._using)

    def sweep():
        n = 0
        try:
            for name in os.listdir(mod.TMP_DIR):
                os.unlink(os.path.join(mod.TMP_DIR, name))
                n += 1
        except OSError:
            pass
        mod.swept.append(n)
        return n

    for f in (runtime_dir, runtime_ready, model_dir, model_ready, worker_env, hardware,
              resolve, cpu_threads, whisper_code, speech_languages, track, untrack,
              stop_all, using, in_use, sweep):
        setattr(mod, f.__name__, f)
    # EVERYTHING ELSE THE REAL MODULE NAMES (its constants above all: GUIDE, PIN,
    # GPU_NEEDS...), so that a server which imports speechpage, lookuppage or
    # notices on top of the fake still starts.  The names above stay the fake's.
    real = _real()
    for name in dir(real):
        if not name.startswith("__") and not hasattr(mod, name):
            setattr(mod, name, getattr(real, name))
    return mod


@contextlib.contextmanager
def installed(root):
    """`import getstt` finds the fake, and the real one is put back."""
    fake = make(root)
    before = sys.modules.get("getstt")
    sys.modules["getstt"] = fake
    import speechconfig
    config_before = speechconfig.CONFIG
    speechconfig.CONFIG = Path(root) / 'speech.json'
    try:
        yield fake
    finally:
        speechconfig.CONFIG = config_before
        if before is None:
            sys.modules.pop("getstt", None)
        else:
            sys.modules["getstt"] = before


# --------------------------------------------------------------------- audio
def pcm(seconds, hz=440, rate=16000, amplitude=12000):
    """`seconds` of a sine tone as PCM16LE bytes (numpy is in the environment)."""
    import numpy as np
    t = np.arange(int(seconds * rate)) / float(rate)
    return (amplitude * np.sin(2 * np.pi * hz * t)).astype("<i2").tobytes()


def write_wav(path, seconds, hz=440, rate=16000):
    """A real 16-bit mono WAV, which a test may call film.mp4."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm(seconds, hz, rate))
    return path
