#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The transcription job: one at a time, on this computer, for the add page.

    started = sttjobs.start(source, lang, model, processing)   # -> {"job": token, ...}
    sttjobs.audio(token, offset, pcm, last)     # a YouTube capture, in pieces
    sttjobs.marks(token, marks); sttjobs.wave(token, rate, peaks)
    sttjobs.status(token); sttjobs.cancel(token); sttjobs.result(token)

NO HTTP HERE.  serve.py's /youtube/api/transcribe/* routes read the request,
call these, and send what they return; a refusal is a `Refusal`, which
becomes `{"ok": false, "error": "<a sentence>", "code": "<slug>"}` with its
status (`call`).  Nothing that reaches a person is ever a traceback: the
worker's own goes to the server's log.

WHAT A JOB IS.  It belongs to no video.  The add page names a source
(a YouTube video, or a film on this computer) through the add flow's own
validators, and gets back a TOKEN made here (secrets.token_urlsafe): the one
capability every other route takes.  No route takes a path, a device, a
precision or a temporary file's name from anybody; the model is one of two
words, the processing one of three, the language one Whisper knows.

ONE AT A TIME (a second start is 409 `busy`).  A multi-gigabyte model is
never loaded twice, a YouTube capture is real time and holds the person's
tab, and the slot is given up the moment a job ends or is cancelled.

THE MODEL IS HELD FROM start() TO THE END (getstt.using), the whole capture
included, so that Settings refuses to take the model or the program away under a
recording that has an hour of a person's time in it -- and says why.

ANY DEVICE THE NETWORK DOOR LET IN MAY START ONE (the owner): a phone, a
tablet, another computer.  Nothing here asks where the caller is, and
nothing may assume it is the machine the server runs on -- a remote
computer's Chromium can capture a tab and POST its sound, and a film is
named by a path on the SERVER's disk whoever names it.  The bound is the one
slot (409 `busy`) and Cancel.

THE STATES: awaiting-audio (a YouTube job, before its first piece) ->
receiving -> queued -> preparing -> loading -> transcribing ->
checking-dictionary -> optional whisper-second-pass -> done (editable review);
a film starts at `queued`.  failed and cancelled end it.  A finished job's
answer is kept for KEEP seconds and forgotten after; a cancelled one is
forgotten AT ONCE (only its token is remembered, so a page that asks is told
"cancelled" and not "no such job"), and an abandoned one -- a capture that
stopped arriving -- is let go after IDLE.

THE CHILD.  lib/sttworker.py, run with Parseh's own Python and the speech
runtime on its PYTHONPATH, in a process group of its own, registered with
getstt.track and with this module's own list: `cancel`, a stopped server
(atexit) and PR_SET_PDEATHSIG / the worker's own look for its parent all end
it.  The worker speaks JSON lines; `_message` is where each one lands.

THE WAVEFORM.  A YouTube job's peaks are the browser's own, from the same
capture (`wave`); they are HELD (youtube/lib/wavefile.py) for the video's
creation to adopt.  A FILM GETS NO WAVEFORM WRITTEN (the owner): the player
draws a film's from the film itself, so the worker only listens.
"""
import atexit
import contextlib
import json
import math
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(HERE, "sttworker.py")
WIN = os.name == "nt"
for _p in (HERE, os.path.join(ROOT, "youtube", "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ------------------------------------------------------------------ the limits
import speechmodels
MODELS = speechmodels.MODELS
MODES = ("auto", "cpu", "cuda")             # and the only three ways to process
SAMPLE_RATE = 16000
CHUNK_MAX = 1 << 20                         # bytes of PCM16 in one audio request
MAX_SAMPLES = SAMPLE_RATE * 3600 * 12       # twelve hours of capture, 1.4 GB on disk
MIN_SAMPLES = SAMPLE_RATE // 2              # under half a second is no recording
FREE_TO_START = 256 << 20                   # bytes free before a capture may begin
FREE_TO_GO_ON = 64 << 20                    # and that must remain after each piece
IDLE = 600.0                                # seconds without a piece: abandoned
KEEP = 900.0                                # a finished job's answer, in seconds
KEEP_CANCELLED = 300.0                      # the token of a cancelled one
MAX_LINE = 64 << 20                         # a line of the worker's, at most
FELL_BACK = "The graphics card could not start this model, so Parseh continued on the CPU."
PAGE = "/youtube/add/"

AWAITING, RECEIVING, QUEUED, PREPARING, LOADING = \
    "awaiting-audio", "receiving", "queued", "preparing", "loading"
TRANSCRIBING, ALIGNING, DONE, FAILED, CANCELLED = "transcribing", "aligning", "done", "failed", "cancelled"
REVIEW_CHOICE, CORRECTING = "awaiting-review-choice", "correcting"
CHECKING = "checking-dictionary"
SECOND_PASS = "whisper-second-pass"
ACTIVE = (AWAITING, RECEIVING, QUEUED, PREPARING, LOADING, TRANSCRIBING, ALIGNING, CHECKING, SECOND_PASS, CORRECTING)
RECORDING = (AWAITING, RECEIVING)           # a YouTube job still taking audio

TOKEN_BYTES = 12
# each ends in \Z and not $: `$` also matches before a trailing newline, and a
# token becomes part of a file name
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16}\Z")          # what token_urlsafe(12) makes
YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}\Z")
LANG_RE = re.compile(r"^[a-z]{2,3}\Z")

JOBS = {}           # token -> the job, while it lives
TOMBS = {}          # token -> {"kind", "at"} for a job that was cancelled
LOCK = threading.RLock()
CHILDREN = set()    # every worker this module started, for stop_all


# ---------------------------------------------------------------- the refusals
class Refusal(Exception):
    """A sentence for the person and a slug for the page; `status` is the
    HTTP answer.  Anything else that goes wrong is turned into this by
    `call`, so that no answer ever carries a traceback."""

    def __init__(self, code, say, status=400, **extra):
        Exception.__init__(self, say)
        self.code, self.say, self.status, self.extra = code, say, status, extra

    def body(self):
        return dict(self.extra, ok=False, error=self.say, code=self.code)


def call(fn, *args, **kw):
    """fn's dict answer -> (dict with ok, HTTP status).  The one place a
    Refusal, or anything unforeseen, becomes an answer."""
    try:
        out = fn(*args, **kw)
        return dict(out, ok=True), 200
    except Refusal as e:
        return e.body(), e.status
    except Exception:                                        # noqa: BLE001
        traceback.print_exc()
        return {"ok": False, "code": "failed", "error": "Transcription failed."}, 500


def _getstt():
    """The speech manager, imported when it is needed: a checkout without it
    (or a server that never installed speech to text) still runs, and
    every job says it is not installed."""
    try:
        import getstt
    except ImportError:
        raise Refusal("not-installed", "Speech to text is not installed.", 409)
    return getstt


def _speech(fn, *args):
    """A call into getstt, its SpeechError made a Refusal in its own words."""
    gs = _getstt()
    try:
        return fn(gs, *args)
    except getattr(gs, "SpeechError", ()) as e:
        raise Refusal(getattr(e, "code", "failed"), getattr(e, "say", "") or
                      "Speech to text could not do that.", 409)


# ------------------------------------------------------------- the add flow's own
def source_of(body):
    """The request's source and language, by the ADD FLOW'S OWN VALIDATORS
    (ytpages.one_source / video_id / local_target -> check_film /
    posted_lang) and their own sentences -> ({"kind", "id" | "path"}, code).

    What is stored is the NORMALISED source: the eleven-character id the
    server parsed, or the absolute path check_film made -- never the page's
    own spelling, which is never read again."""
    import ytpages
    for key in ("url", "path", "lang", "source"):
        if body.get(key) is not None and not isinstance(body.get(key), str):
            raise Refusal("bad-source" if key != "lang" else "bad-language",
                          "the %s has to be text, and that is a %s"
                          % (key, type(body.get(key)).__name__))
    kind = body.get("source")
    if kind not in ("youtube", "film"):
        raise Refusal("bad-source", "a transcription starts from a YouTube video "
                      "or from a film on this machine")
    try:
        ytpages.one_source(body)
    except ValueError as e:
        raise Refusal("bad-source", str(e))
    if kind == "youtube":
        if (body.get("path") or "").strip():
            raise Refusal("bad-source", "a YouTube video is named by its address, "
                          "not by a file on this machine")
        vid = ytpages.video_id(body.get("url"))
        if not vid:
            raise Refusal("bad-source", "that is not a YouTube URL (or id) -- or "
                          "name a film on this machine instead")
        source = {"kind": "youtube", "id": vid}
    else:
        if (body.get("url") or "").strip():
            raise Refusal("bad-source", "a film on this machine is named by its path, "
                          "not by an address")
        try:
            path, _ext, _id = ytpages.local_target({"path": body.get("path")}, [])
        except ValueError as e:
            raise Refusal("bad-source", str(e))
        source = {"kind": "film", "path": path}
    if not (body.get("lang") or "").strip():
        raise Refusal("bad-language", "name the language the video is spoken in")
    try:
        code = ytpages.posted_lang(body.get("lang")).code
    except KeyError as e:
        raise Refusal("bad-language", str(e.args[0] if e.args else e))
    return source, code


# --------------------------------------------------------------------- helpers
def _now():
    return time.time()


def _tmp():
    """The folder temporary audio lives in (stt/tmp/), made when first needed."""
    gs = _getstt()
    os.makedirs(gs.TMP_DIR, exist_ok=True)
    return gs.TMP_DIR


def _named(token, ext):
    """A temporary file's path: made by the server from a token it made
    itself, so nothing the client sends is ever part of it."""
    if not isinstance(token, str) or not TOKEN_RE.match(token):
        raise Refusal("no-such-job", "That transcription is not here any more "
                      "(Parseh may have been restarted).", 404)
    base = os.path.abspath(_tmp())
    path = os.path.abspath(os.path.join(base, "stt-%s%s" % (token, ext)))
    if os.path.dirname(path) != base:
        raise Refusal("no-such-job", "That transcription is not here any more.", 404)
    return path


def _free(path):
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def _clock(seconds):
    n = max(0, int(seconds))
    return "%d:%02d:%02d" % (n // 3600, n // 60 % 60, n % 60) if n >= 3600 \
        else "%d:%02d" % (n // 60, n % 60)


def _remove(*paths):
    for p in paths:
        if p:
            try:
                os.unlink(p)
            except OSError:
                pass


def _using(gs, key):
    """The model is in use for as long as the job lives, from start() to its
    end, so that Settings will not remove it under it (getstt.using)."""
    f = getattr(gs, "using", None)
    return f(key) if callable(f) else contextlib.nullcontext()


def _unhold(job):
    """The part start() took for the job, let go.  Every end of a job asks
    (done, failed, cancelled, abandoned, a stopping server) and the first
    one frees it: a second is nothing, so a part an install holds as well is
    not let go early, and one that is never let go could not be removed again."""
    with LOCK:
        hold = job.pop("hold", None)
    if hold is not None:
        hold.close()


def _job(token, missing=True):
    """A token -> its job.  A token that is not one is refused before any
    table is looked in; an unknown one is `no-such-job`, or None."""
    if not isinstance(token, str) or not TOKEN_RE.match(token):
        raise Refusal("no-such-job", "That transcription is not here any more "
                      "(Parseh may have been restarted).", 404)
    with LOCK:
        _expire()
        job = JOBS.get(token)
        if job is None:
            job = _restore_pending(token)
        cancelled = token in TOMBS
    if job is None and missing:
        if cancelled:
            raise Refusal("cancelled", "Recording was cancelled.", 409)
        raise Refusal("no-such-job", "That transcription is not here any more "
                      "(Parseh may have been restarted).", 404)
    return job


# ------------------------------------------------------------------------ files
def _files(job):
    return [job.get("pcm"), job.get("spec"), job.get("log")]


def _clean_files(job):
    """Every temporary file of a job gone -- the audio above all."""
    _remove(*_files(job))


def _kill(proc):
    """The worker and anything it started, ended (as lib/latexdraw._kill)."""
    try:
        if WIN:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass


def _preexec():
    # on Linux the worker dies with the server even when the server is
    # killed outright (PR_SET_PDEATHSIG); elsewhere the worker looks for its
    # parent itself, and the server's own stop ends it (stop_all)
    try:
        import ctypes
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGKILL)
    except Exception:                                        # noqa: BLE001
        pass


def stop_all():
    """Every worker ended, and every temporary recording with it: the server
    is stopping (atexit, and serve.py's SIGTERM handler ends in it)."""
    with LOCK:
        procs = list(CHILDREN)
        jobs = list(JOBS.values())
    for proc in procs:
        _kill(proc)
    for job in jobs:
        _save_pending(job)
        job["cancelled"] = True
        if job.get("llm_cancel"):
            job["llm_cancel"].cancel()
        _clean_files(job)
        _unhold(job)


atexit.register(stop_all)


# -------------------------------------------------------------------- the table
def _expire():
    """Forget what is over, and abandon what stopped arriving.  Asked at
    every call, under LOCK: there is no timer thread to keep."""
    now = _now()
    for token, job in list(JOBS.items()):
        if job["state"] in (DONE, FAILED, REVIEW_CHOICE) and now - (job["finished"] or now) > KEEP:
            del JOBS[token]
        elif job["state"] in RECORDING and now - job.get("touched", now) > IDLE:
            _end(job, FAILED, "abandoned", "No sound arrived for %d minutes, so this "
                 "transcription was given up." % (IDLE // 60))
    for token, tomb in list(TOMBS.items()):
        if now - tomb["at"] > KEEP_CANCELLED:
            del TOMBS[token]


def _end(job, state, code=None, say=None):
    """A job over: its state, its reason, and nothing of it left on disk
    that it does not need (the answer of a done one is in memory)."""
    with LOCK:
        if job["state"] in (DONE, FAILED, CANCELLED):
            return
        job["state"] = state
        job["finished"] = _now()
        if state == FAILED:
            job["error"] = {"code": code or "failed", "say": say or "Transcription failed."}
        _unhold(job)                     # in the breath that says it is over
    _clean_files(job)
    if state == FAILED and job["kind"] == "youtube" and not job["sealed"]:
        # A PARTIAL CAPTURE HOLDS NOTHING: the waveform is the whole video's or
        # none (a capture that was complete and whose transcription then failed
        # keeps its peaks: an hour of the person's time, and half a megabyte)
        import wavefile
        wavefile.drop(job["id"])
    if state in (FAILED, CANCELLED):
        try:
            import wordtimes
            wordtimes.drop(job["id"])
        except Exception:  # noqa: BLE001
            pass


def busy():
    """Is a job holding the slot?  (For the Reading help page: an install
    and a transcription do not both load a model.)"""
    with LOCK:
        _expire()
        return any(j["state"] in ACTIVE for j in JOBS.values())


# ------------------------------------------------------------------------ start
def start(source, lang, model, processing, duration=None, exact=True):
    """A job, for a source the add flow's validators passed -> {"job", "state",
    "need", ...}.  `source` is what source_of() made; everything here is
    checked again, because this is the door tests and other code reach too."""
    if not isinstance(model, str) or model not in MODELS:
        raise Refusal("bad-model", "Choose a model from Speech to text settings.")
    if not isinstance(processing, str) or processing not in MODES:
        raise Refusal("bad-processing", "Processing has to be Automatic, CPU or NVIDIA GPU.")
    if not isinstance(lang, str) or not LANG_RE.match(lang):
        raise Refusal("bad-language", "That is not a language code.")
    if not speechmodels.compatible(model, lang):
        raise Refusal('model-language', 'The selected speech model does not support this language.')
    if not isinstance(exact, bool):
        raise Refusal("bad-exact", "Exact word times can only be on or off.")
    if not isinstance(source, dict):
        raise Refusal("bad-source", "There is no video to transcribe.")
    kind = source.get("kind")
    film = None
    if kind == "youtube":
        vid = source.get("id")
        if not isinstance(vid, str) or not YT_ID.match(vid):
            raise Refusal("bad-source", "That is not a YouTube video's id.")
        norm = {"kind": "youtube", "id": vid}
    elif kind == "film":
        path = source.get("path")
        if not isinstance(path, str) or not path or "\0" in path or not os.path.isabs(path):
            raise Refusal("bad-source", "A film is named by the full path of a file on "
                          "this machine.")
        # the add flow's own check again (a film is a file with a video's
        # extension), and the path must be the one it made: the same words
        # in, the same words out
        import ytpages
        try:
            real, _ext = ytpages.check_film(path)
        except ValueError as e:
            raise Refusal("bad-source", str(e))
        if real != path:
            raise Refusal("bad-source", "A film is named by the full path of a file on "
                          "this machine.")
        try:
            st = os.stat(path)
        except OSError:
            raise Refusal("film-unreadable", "The local film could not be read.", 422)
        if not os.path.isfile(path):
            raise Refusal("film-unreadable", "The local film could not be read.", 422)
        film = [st.st_size, st.st_mtime_ns, st.st_ino]
        norm = {"kind": "film", "path": path}
    else:
        raise Refusal("bad-source", "A transcription starts from a YouTube video or "
                      "from a film on this machine.")
    hint = None
    if duration is not None:
        # (one comparison refuses nan, inf and a 400-digit integer alike, without
        # ever turning the number into a float, which an integer that big cannot be)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) \
                or not 0 < duration <= MAX_SAMPLES / SAMPLE_RATE:
            raise Refusal("bad-duration", "That is not how long a video can be.")
        hint = float(duration)

    gs = _getstt()
    if not gs.runtime_ready():
        raise Refusal("not-installed", "Speech to text is not installed.", 409)
    if not gs.model_ready(model):
        raise Refusal("no-model", "The selected model is not installed.", 409)
    # the language Whisper listens for; a code it lacks is SpeechError
    wlang = _speech(lambda g, c: g.whisper_code(c), lang)
    if not isinstance(wlang, str) or not LANG_RE.match(wlang):
        raise Refusal("unsupported-language", "Speech to text cannot listen for that "
                      "language.", 409)
    # the device is resolved HERE, so an explicit NVIDIA GPU that is not ready
    # is refused at once, before anybody records an hour of sound for it
    device, _note = _speech(lambda g, m: g.resolve(m), processing)
    if device not in ("cpu", "cuda"):
        raise Refusal("failed", "Transcription failed.", 500)
    name = ""
    if device == "cuda":
        try:
            name = str(gs.hardware()["cuda"].get("name") or "")
        except Exception:                                    # noqa: BLE001
            name = ""
    threads = gs.cpu_threads()
    aligner = ""
    ready = getattr(gs, "aligner_ready", None)
    if exact and callable(ready):
        try:
            aligner = lang if ready(lang) else ""
        except Exception:  # noqa: BLE001
            aligner = ""
    tmp = _tmp()
    if kind == "youtube":
        need = FREE_TO_START + (int(hint * SAMPLE_RATE * 2) if hint else 0)
        free = _free(tmp)
        if free is not None and free < need:
            raise Refusal("no-room", "There was not enough disk space to finish the "
                          "capture.", 507)

    with LOCK:
        _expire()
        if any(j["state"] in ACTIVE for j in JOBS.values()):
            raise Refusal("busy", "Another transcription is running.", 409)
        token = secrets.token_urlsafe(TOKEN_BYTES)
        now = _now()
        import speechconfig
        preferences = speechconfig.load()
        job = {"id": token, "kind": kind, "source": norm, "film": film,
               "automatic_second_pass": preferences['second_pass'],
               "model_revision": speechmodels.provenance(model),
               "lang": lang, "wlang": wlang, "model": model, "mode": processing,
               "aligner": aligner,
               "planned": device, "device": None, "device_name": name, "threads": threads,
               "fell_back": False,
               "state": AWAITING if kind == "youtube" else QUEUED,
               "created": now, "touched": now, "started": None, "finished": None,
               "have": 0, "sealed": False, "hint": hint, "marks": [],
               "total": None, "done": 0.0, "segments": None, "text": "", "notes": [],
               "words": None,
               "facts": None, "warning": "", "error": None, "cancelled": False,
               "proc": None, "lock": threading.Lock(),
               "pcm": _named(token, ".pcm"), "spec": _named(token, ".spec.json"),
               "log": _named(token, ".log")}
        JOBS[token] = job
        # THE JOB HOLDS ITS MODEL, AND WITH IT THE PROGRAM, FROM HERE TO ITS END: a
        # capture is real time and takes as long as the video plays, and Settings
        # must not take the part away under a recording (nothing else notices it)
        job["hold"] = contextlib.ExitStack()
        job["hold"].enter_context(_using(gs, model))
        if aligner:
            job["hold"].enter_context(_using(gs, "align-" + aligner))
        # the answer is made BEFORE the worker's thread can move the state on
        answer = _started(job)
    if kind == "film":
        _launch(job)
    return answer


def _started(job):
    out = {"job": job["id"], "state": job["state"], "kind": job["kind"],
           "need": "audio" if job["kind"] == "youtube" else "",
           "lang": job["lang"], "model": job["model"], "processing": job["mode"],
           "exact": bool(job.get("aligner")),
           "say": _say(job)}
    out['model_revision'] = job.get('model_revision')
    if job.get("correction"):
        out["correction"] = dict(job["correction"])
    out.update(_who(job))
    return out


def _who(job):
    if job["kind"] == "youtube":
        return {"source": "youtube", "video_id": job["source"]["id"]}
    return {"source": "film", "film": os.path.basename(job["source"]["path"])}


def _launch(job):
    threading.Thread(target=_run, args=(job,), daemon=True).start()


# ------------------------------------------------------------------------ audio
def audio(token, offset, data, last=False):
    """One piece of a YouTube capture: 16 kHz mono PCM16LE, at a sample
    offset -> {"have": samples so far}.  Idempotent: a piece sent twice is
    written once; a piece that skips ahead is 409 `gap`, with `have`, and
    the browser sends again from there."""
    job = _job(token)
    if job["kind"] != "youtube":
        raise Refusal("wrong-state", "This transcription takes no recording: it reads a "
                      "film on this machine.", 409)
    if not isinstance(data, (bytes, bytearray)):
        raise Refusal("bad-audio", "The recording did not arrive as sound.")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise Refusal("bad-offset", "The recording says where its piece belongs, and that "
                      "is not a place.")
    if len(data) > CHUNK_MAX:
        raise Refusal("too-big", "That piece of the recording is bigger than one piece "
                      "may be.", 413)
    if len(data) % 2:
        raise Refusal("bad-audio", "The recording did not arrive as whole samples.")
    n = len(data) // 2
    if not n and not last:
        raise Refusal("bad-audio", "That piece of the recording was empty.")
    with job["lock"]:
        with LOCK:
            state, have, sealed = job["state"], job["have"], job["sealed"]
            if job["cancelled"] or state == CANCELLED:
                raise Refusal("cancelled", "Recording was cancelled.", 409)
            if state not in RECORDING:
                # THE LAST PIECE SENT AGAIN, because its answer was lost, is
                # not an error: the job has it and has gone on
                if sealed and last and offset + n == have:
                    return {"have": have, "state": state}
                raise Refusal("wrong-state", "This transcription is not taking sound "
                              "any more.", 409)
        if offset > have or (not n and offset != have):
            raise Refusal("gap", "A piece of the recording is missing.", 409, have=have)
        if offset + n > MAX_SAMPLES:
            raise Refusal("too-long", "A recording of more than 12 hours cannot be "
                          "transcribed here.", 413)
        if offset + n > have:
            free = _free(os.path.dirname(job["pcm"]))
            if free is not None and free - len(data) < FREE_TO_GO_ON:
                _end(job, FAILED, "no-room", "There was not enough disk space to finish "
                     "the capture.")
                raise Refusal("no-room", "There was not enough disk space to finish the "
                              "capture.", 507)
            try:
                mode = "r+b" if os.path.exists(job["pcm"]) else "wb"
                with open(job["pcm"], mode) as f:
                    f.seek(offset * 2)
                    f.write(data)
            except OSError:
                _end(job, FAILED, "no-room", "There was not enough disk space to finish "
                     "the capture.")
                raise Refusal("no-room", "There was not enough disk space to finish the "
                              "capture.", 507)
            have = offset + n
        with LOCK:
            job["have"] = have
            job["touched"] = _now()
            job["state"] = RECEIVING
            if last:
                if have < MIN_SAMPLES:
                    _end(job, FAILED, "no-sound", "No sound was recorded.")
                    raise Refusal("no-sound", "No sound was recorded.")
                job["sealed"] = True
                job["total"] = have / float(SAMPLE_RATE)
                job["state"] = QUEUED
            state = job["state"]      # said now: the worker's thread moves it on
        if last:
            _launch(job)
    return {"have": have, "state": state}


def marks(token, marks):
    """The pairs [frame, video seconds] that put the recording on the video's
    own clock (sttpanel.remap): REPLACE ALL, sent before the last piece."""
    import sttpanel
    job = _job(token)
    if job["kind"] != "youtube":
        raise Refusal("wrong-state", "A film needs no marks: it is read from its start.", 409)
    if not isinstance(marks, list):
        raise Refusal("bad-marks", "The marks have to be a list of pairs.")
    with LOCK:
        if job["state"] not in RECORDING:
            raise Refusal("wrong-state", "This transcription is not taking marks any "
                          "more.", 409)
        job["marks"] = sttpanel.clean_marks(marks, SAMPLE_RATE)
        job["touched"] = _now()
        return {"marks": len(job["marks"])}


def wave(token, rate, peaks):
    """The peaks the browser made from the same capture -> held for the video
    the person adds (youtube/lib/wavefile.py).  A partial capture holds
    nothing: cancel and a failure drop it."""
    import wavefile
    job = _job(token)
    if job["kind"] != "youtube":
        raise Refusal("wrong-state", "A film has no waveform to send: the player draws it "
                      "from the film itself.", 409)
    with LOCK:
        if job["state"] in (FAILED, CANCELLED):
            raise Refusal("wrong-state", "This transcription is over.", 409)
    try:
        kept = wavefile.hold(token, rate, peaks)
    except ValueError as e:
        raise Refusal("bad-wave", str(e))
    with LOCK:
        job["touched"] = _now()
    return {"buckets": kept}


# ----------------------------------------------------------------- status, etc.
def _say(job):
    s, model = job["state"], job["model"]
    if s == AWAITING:
        return "Waiting for the recording to start…"
    if s == RECEIVING:
        got = _clock(job["have"] / float(SAMPLE_RATE))
        return ("Recording %s / %s…" % (got, _clock(job["hint"])) if job["hint"]
                else "Recording %s…" % got)
    if s == QUEUED:
        return "Audio captured." if job["kind"] == "youtube" else "Getting ready…"
    if s == PREPARING:
        return "Preparing audio…"
    fell = FELL_BACK + " " if job["fell_back"] else ""
    if s == LOADING:
        on = (" Using %s." % job["device_name"]) if job["device"] == "cuda" \
            and job["device_name"] else ""
        return "%sLoading %s…%s" % (fell, model, on)
    if s == TRANSCRIBING:
        where = "GPU" if job["device"] == "cuda" else "CPU"
        pct = _pct(job)
        return "%sTranscribing on %s…%s" % (fell, where, " %d%%" % pct if pct is not None
                                                  else "")
    if s == ALIGNING:
        pct = _pct(job)
        return "Making exact word times…%s" % (" %d%%" % pct if pct is not None else "")
    if s == REVIEW_CHOICE:
        return "The transcript is ready to review and edit."
    if s == CHECKING:
        return "Whisper finished. Checking words in the installed dictionary…"
    if s == SECOND_PASS:
        p = job.get('second_pass', {})
        return "Whisper second pass… %d / %d suspect words processed." % (p.get('done', 0), p.get('total', 0))
    if s == CORRECTING:
        c = job.get("correction", {})
        if c.get('task') == 'whisper-second':
            return 'Whisper second pass… %d / %d words processed.' % (c.get('done', 0), c.get('total', 0))
        if c.get("total", 0):
            if c.get("task") == "likelihood":
                return "%s… %d / %d suspect spans processed." % (c.get("phase", "Scoring likelihood"), c.get("done", 0), c["total"])
            if c.get("task") == "workspace":
                return "%s… %d / %d ASR words processed." % (c.get("phase", "Reviewing workspace"), c.get("done", 0), c["total"])
            return "Reviewing with the selected LLM… %d / %d ASR words reviewed." % (c.get("done", 0), c["total"])
        return "Reviewing with the selected LLM…"
    if s == DONE:
        n = (job["facts"] or {}).get("captions", 0)
        return "Done — %d caption%s." % (n, "" if n == 1 else "s")
    if s == FAILED:
        return (job["error"] or {}).get("say") or "Transcription failed."
    return "Recording was cancelled." if job["kind"] == "youtube" \
        else "Transcription was cancelled."


def _pct(job):
    if job['state'] == SECOND_PASS:
        p = job.get('second_pass', {})
        return int(100*p.get('done', 0)/p['total']) if p.get('total') else 100
    if job["state"] == CORRECTING:
        c = job.get("correction", {})
        return int(100 * c.get("done", 0) / c["total"]) if c.get("total", 0) > 0 else None
    if job["state"] == DONE:
        return 100
    if job["state"] in (TRANSCRIBING, ALIGNING) and job["total"]:
        return max(0, min(99, int(100 * job["done"] / job["total"])))
    if job["state"] == RECEIVING and job["hint"]:
        return max(0, min(99, int(100 * job["have"] / float(SAMPLE_RATE) / job["hint"])))
    return None


def _report(job):
    """A job as status says it: the shape the add page draws from."""
    out = {"state": job["state"], "say": _say(job), "pct": _pct(job),
           "done": round(job["done"], 3), "total": round(job["total"], 3) if job["total"]
           else None, "device": job["device"], "fell_back": job["fell_back"],
           "model": job["model"], "lang": job["lang"], "kind": job["kind"],
           "exact": bool(job.get("aligner")),
           "have": job["have"], "stopped": job["state"] == CANCELLED}
    if job.get("correction"):
        out["correction"] = dict(job["correction"])
    if job.get('second_pass') is not None:
        out['second_pass'] = {k: job['second_pass'][k] for k in ('done', 'total', 'failed')}
    out['model_revision'] = job.get('model_revision')
    out.update(_who(job))
    if job["fell_back"]:
        out["note"] = FELL_BACK
    if job["state"] == DONE:
        out["captions"] = (job["facts"] or {}).get("captions", 0)
    if job["state"] == FAILED and job["error"]:
        out["error"], out["code"] = job["error"]["say"], job["error"]["code"]
    return out


def status(token):
    job = _job(token, missing=False)
    if job is not None:
        with LOCK:
            return _report(job)
    with LOCK:
        tomb = TOMBS.get(token) if isinstance(token, str) else None
    if tomb is None:
        raise Refusal("no-such-job", "That transcription is not here any more "
                      "(Parseh may have been restarted).", 404)
    youtube = tomb["kind"] == "youtube"
    return {"state": CANCELLED, "say": "Recording was cancelled." if youtube
            else "Transcription was cancelled.", "pct": None, "done": 0, "total": None,
            "device": None, "fell_back": False, "model": None, "lang": None,
            "kind": tomb["kind"], "source": tomb["kind"], "stopped": True}


def cancel(token):
    """Stop it: the worker killed, the temporary audio deleted, the held
    waveform dropped, the slot free, and the job forgotten -- only its
    token stays (a little while), so that a page which asks is told so.
    A job that is over has nothing to stop (its answer stays)."""
    import wavefile
    import wordtimes
    import asrpending
    job = _job(token, missing=False)
    if job is None:
        asrpending.remove(token)
        return {"cancelled": False}
    with LOCK:
        if job['state'] == DONE and job.get('review_used'):
            asrpending.remove(token)
            return {'cancelled':False}
        job["review_used"] = True  # Explicit discard must not be saved again by cancel_review.
        if job["state"] not in ACTIVE + (REVIEW_CHOICE, DONE):
            asrpending.remove(token)
            return {"cancelled": False}
        job['llm_generation'] = job.get('llm_generation', 0) + 1
        if job.get('llm_cancel'):
            job['llm_cancel'].cancel()
        job["cancelled"] = True
        job["state"] = CANCELLED
        job["finished"] = _now()
        proc = job["proc"]
    if proc is not None:
        _kill(proc)
        try:
            proc.wait(10)                # its memory is free before the next job
        except (subprocess.TimeoutExpired, OSError):
            pass
    with job.get("lock", LOCK):          # after a piece being written, not in it
        _clean_files(job)
    asrpending.remove(token)
    _unhold(job)                         # with the worker dead, the part may go
    wavefile.drop(token)
    wordtimes.drop(token)
    with LOCK:
        JOBS.pop(token, None)
        TOMBS[token] = {"kind": job["kind"], "at": _now()}
    return {"cancelled": True}


def result(token):
    """The transcript, in the add page's own format, once the job is done;
    it may be read again until the job is forgotten."""
    import wavefile
    import asrpending
    job = _job(token, missing=False)
    if job is None:
        with LOCK:
            if isinstance(token, str) and token in TOMBS:
                raise Refusal("cancelled", "Recording was cancelled.", 409)
        raise Refusal("no-such-job", "That transcription is not here any more "
                      "(Parseh may have been restarted).", 404)
    with LOCK:
        state = job["state"]
        if state == FAILED and job["error"]:
            raise Refusal(job["error"]["code"], job["error"]["say"], 409)
        if state not in (DONE, REVIEW_CHOICE, CORRECTING):
            raise Refusal("not-finished", "It has not finished yet.", 409)
        _save_pending(job)
        facts = dict(job["facts"] or {})
        return dict(facts, text=job["text"], lang=job["lang"], model=job["model"],
                    model_revision=job.get('model_revision'),
                    device=job["device"], fell_back=job["fell_back"],
                    notes=list(job["notes"]), warning=job["warning"],
                    words=dict(job["words"] or {"held": False, "count": 0}),
                    wave={"held": wavefile.held(token)},
                    review={"draft": job.get("review_draft", {}),
                            "second_pass_available": bool(job.get('whisper_source')) and
                                (job['kind'] == 'film' or os.path.isfile(asrpending.audio_path(token))),
                            "last_method": job.get('last_method'),
                            "last_word_ids": job.get('last_word_ids', []),
                            "generation": job.get("llm_generation", 0),
                            "save_error": job.get("draft_save_error"),
                            "evidence": job.get("review_evidence"),
                            "choice": job.get("review_choice"),
                            "correction": dict(job.get("correction") or {}),
                            "result": job.get("correction_result"),
                            "external": _external_view(job),
                            "diagnostics": list(job.get("llm_diagnostics") or []),
                            "diagnostics_clipped": bool(job.get("llm_diagnostics_clipped"))})


def _save_pending(job):
    try:
        import asrpending
        asrpending.save(job)
        job.pop("draft_save_error", None)
    except (OSError, ValueError):
        job["draft_save_error"] = "The pending review could not be saved to disk. Keep this page open; free disk space or use/discard older pending reviews before pausing."


def _restore_pending(token):
    import asrpending
    try:
        record = asrpending.load(token)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    job = record["job"]
    job.update(state=DONE if job.get("review_choice") else REVIEW_CHOICE,
               error=None, cancelled=False, proc=None, lock=threading.Lock(), segments=None,
               pcm=None, spec=None, log=None, finished=_now())
    if job.get("correction", {}).get("state") == "running":
        if job['correction'].get('task') == 'whisper-second':
            job['correction'] = job.pop('second_pass_previous', {}).get('correction', {'state':'not-requested', 'complete':False})
        else:
            job["correction"].update(state="interrupted", complete=False)
    import wordtimes
    import wavefile
    if record.get("timings"):
        wordtimes.hold(token, record["timings"])
    if record.get("wave"):
        wavefile.hold(token, record["wave"]["rate"], record["wave"]["peaks"])
    JOBS[token] = job
    return job


def _review_targets(job, task, requested):
    import asrcorrection
    sources = asrcorrection.index(job["review_evidence"])
    locked = set(job.get("review_draft", {}).get("locked_word_ids", []))
    wanted = requested if requested is not None else [w["word_id"] for w in sources.values()
        if w["reviewable"] and (task in ("full", "workspace") or asrcorrection.suspect(w))]
    return [ident for ident in wanted if ident not in locked]


def save_review_draft(token, source_sha256, draft, generation=None):
    import asrcorrection
    import llmconfig
    job = _job(token)
    with LOCK:
        if not job.get("review_evidence") or source_sha256 != job["review_evidence"]["source_sha256"] or not _review_source_current(job):
            raise Refusal("stale-review", "This draft no longer matches the source.", 409)
        if generation is not None and generation != job.get("llm_generation", 0):
            raise Refusal("stale-review", "The review method changed before this draft could be saved.", 409)
        if not isinstance(draft, dict) or set(draft) - {"decisions", "manual_edits", "locked_word_ids", "selection", "scope", "selected_word", "browser", "phonetic_filter", "external_drafts", "walk"}:
            raise Refusal("bad-draft", "The draft contains unknown fields.")
        sources = asrcorrection.index(job["review_evidence"])
        if 'phonetic_filter' in draft and type(draft['phonetic_filter']) is not bool:
            raise Refusal("bad-draft", "The similar-sound option must be on or off.")
        if draft.get('scope', 'all') not in ('all', 'selection'):
            raise Refusal("bad-draft", "Choose all text or a selected section.")
        if not isinstance(draft.get('selected_word'), (str, type(None))) or draft.get('selected_word') is not None and draft['selected_word'] not in sources:
            raise Refusal("bad-draft", "Choose a word from the source transcript.")
        pasted = draft.get('external_drafts', {})
        if (not isinstance(pasted, dict) or len(pasted) > 4
                or any(not isinstance(k, str) or len(k) > 100 or not isinstance(v, str)
                       or len(v) > 131072 for k, v in pasted.items())):
            raise Refusal("bad-draft", "The pasted answer draft is too large or invalid.")
        walk = draft.get("walk", {})
        if (not isinstance(walk, dict) or set(walk) - {"kept", "skipped", "include_agree"}
                or type(walk.get("include_agree", False)) is not bool
                or any(not isinstance(walk.get(key, []), list) or len(walk.get(key, [])) > len(sources)
                       or any(not isinstance(w, str) or w not in sources for w in walk.get(key, [])) for key in ("kept", "skipped"))):
            raise Refusal("bad-draft", "The walk through the answers has words that are not in the transcript.")
        locked = draft.get("locked_word_ids", [])
        selection = draft.get("selection", [])
        if (not isinstance(locked, list) or len(locked) > len(sources)
                or any(not isinstance(w, str) or w not in sources or not sources[w]["reviewable"] for w in locked)
                or len(set(locked)) != len(locked)
                or not isinstance(selection, list) or len(selection) not in (0, 2)
                or any(not isinstance(w, str) or w not in sources for w in selection)):
            raise Refusal("bad-draft", "Choose locks and a section from the original transcript.")
        try:
            asrcorrection.apply(job["text"], job["review_evidence"], job.get("correction_result") or {"suggestions": []},
                                draft.get("decisions", {}), draft.get("manual_edits", {}))
        except llmconfig.LLMError as e:
            raise Refusal(e.code, e.say)
        browser = draft.get("browser", {})
        if not isinstance(browser, dict) or set(browser) - {"transcript", "hash"} or any(not isinstance(v, str) or len(v) > 2 << 20 for v in browser.values()):
            raise Refusal("bad-draft", "The browser draft is too large or invalid.")
        job["review_draft"] = json.loads(json.dumps(draft))
        _save_pending(job)
        if job.get("draft_save_error"):
            raise Refusal("disk-save-failed", job["draft_save_error"], 507)
        return {"saved": True}


def pending_reviews():
    import asrpending
    return {"pending": asrpending.listing()}


def resume_review(token):
    job = _job(token)
    if not _review_source_current(job):
        raise Refusal("source-changed", "The local video changed. Discard this draft and transcribe it again.", 409)
    return {"job": token, "source": job["source"], "lang": job["lang"], "model": job["model"],
            "draft": job.get("review_draft", {}), "state": job["state"]}


def review_media(token):
    """The original local film for this job's browser review, never a caller's path.

    The normal admission gate still applies. The unpredictable job token grants
    access only to the already validated source, while its file identity matches.
    The film is read in place; this route never creates a copy.
    """
    job = _job(token)
    with LOCK:
        if job["kind"] != "film" or not job.get("film") or job["state"] in (FAILED, CANCELLED):
            raise Refusal("no-review-media", "There is no local video for this review.", 404)
        if not _review_source_current(job):
            raise Refusal("source-changed", "The local film changed. Transcribe it again.", 409)
        return job["source"]["path"]


def review_dictionary(token, source_sha256, word_id):
    """Read-only meanings for source words, native ASR and validated LLM candidates."""
    import asrcorrection
    import asrdictionary
    job = _job(token)
    with LOCK:
        evidence = job.get("review_evidence")
        if not evidence or source_sha256 != evidence["source_sha256"] or not _review_source_current(job):
            raise Refusal("stale-review", "That dictionary lookup no longer matches the review.", 409)
        word = asrcorrection.index(evidence).get(word_id) if isinstance(word_id, str) else None
        if word is None:
            raise Refusal("bad-word", "Choose a word from this Whisper result.")
        resolver = job.get("dictionary_resolver")
        if resolver is None:
            resolver = job["dictionary_resolver"] = asrdictionary.Resolver(job["lang"])
        segment = next(s for s in evidence["segments"] if s["segment_id"] == word["segment_id"])
        source_words = segment["words"]
        index = next(i for i, w in enumerate(source_words) if w["word_id"] == word_id)
        asr_before = source_words[index-1]["text"] if index else ""
        asr_after = source_words[index+1]["text"] if index+1 < len(source_words) else ""
        asr_candidates = [a["text"] for a in word["asr_alternatives"]]
        proposal = next((s for s in (job.get("correction_result") or {}).get("suggestions", [])
                         if word_id in s.get("word_ids", [s["word_id"]])), None)
        original = proposal["original"] if proposal else word["text"]
        members = proposal.get("word_ids", [proposal["word_id"]]) if proposal else [word_id]
        first = next(j for j, w in enumerate(source_words) if w["word_id"] == members[0])
        last = next(j for j, w in enumerate(source_words) if w["word_id"] == members[-1])
        before = source_words[first-1]["text"] if first else ""
        after = source_words[last+1]["text"] if last+1 < len(source_words) else ""
        candidates = [c["text"] for c in proposal["candidates"]] if proposal else []
    return {"word_id": word_id, "source_sha256": source_sha256,
            "original": dict(resolver.word(original, before, after), text=original),
            "asr_alternatives": [dict(resolver.word(text, asr_before, asr_after), text=text) for text in asr_candidates],
            "candidates": [dict(resolver.word(text, before, after), text=text) for text in candidates]}


def _review_source_current(job):
    if job["kind"] != "film" or not job.get("film"):
        return True
    try:
        st = os.stat(job["source"]["path"])
        return [st.st_size, st.st_mtime_ns, st.st_ino] == job["film"]
    except OSError:
        return False


def review(token, mode, source_sha256, connection_id=None, word_ids=None, instruction_mode="prompt", task="suspect"):
    """Explicit browser choice. Destination and model come only from host config."""
    import llmconfig
    import llmadapter
    job = _job(token)
    with LOCK:
        if job["state"] not in (REVIEW_CHOICE, DONE):
            raise Refusal("wrong-state", "Wait for the current tool or stop it before starting another.", 409)
        if not job.get("review_evidence") or source_sha256 != job["review_evidence"]["source_sha256"]:
            raise Refusal("stale-review", "That review no longer matches the Whisper result.", 409)
        if not _review_source_current(job):
            raise Refusal("source-changed", "The local film changed. Transcribe it again.", 409)
        if mode not in ("llm", "whisper"):
            raise Refusal("bad-review", "Choose an available review tool.")
        if instruction_mode not in ("prompt", "skill"):
            raise Refusal("bad-review", "Choose the short prompt or installed correction skill.")
        if task not in ("suspect", "full", "workspace"):
            raise Refusal("bad-review", "Choose a saved transcript review method.")
        previous = job.get("correction_result")
        if word_ids is not None:
            import asrcorrection
            sources = asrcorrection.index(job["review_evidence"])
            if (mode != "llm" or not isinstance(word_ids, list) or not word_ids
                    or len(word_ids) > len(sources) or any(not isinstance(w, str) for w in word_ids)
                    or len(set(word_ids)) != len(word_ids)
                    or any(w not in sources or not sources[w]["reviewable"] or
                           (task == "suspect" and not asrcorrection.suspect(sources[w])) for w in word_ids)):
                raise Refusal("bad-review", "Choose remaining words from this review task and Whisper result.")
        word_ids = _review_targets(job, task, word_ids) if mode == "llm" else None
        if previous and previous.get("task", "suspect") != task:
            previous = None
        if mode == "whisper":
            job.pop("external_review", None)
            job["review_choice"] = "whisper"
            job["correction_result"] = None
            job["correction"] = {"state": "not-requested", "complete": False}
            job["state"], job["finished"] = DONE, _now()
            return _report(job)
        if any(j is not job and j["state"] in ACTIVE for j in JOBS.values()):
            raise Refusal("busy", "Another transcription or LLM review is running.", 409)
        config = llmconfig.load()
        if config is None:
            raise Refusal("llm-unconfigured", "Set up LLM Integration, or review the Whisper result without it.", 409)
        if instruction_mode == "skill" and task != "workspace" and config.get("adapter") != "unsloth-agent-skills":
            raise Refusal("skills-unavailable", "Select the Unsloth Agent Skills adapter in LLM Integration before using an installed skill.", 409)
        if connection_id != llmconfig.revision(config):
            raise Refusal("settings-changed", "The LLM settings changed. Inspect the current destination and choose review again.", 409)
        try:
            llmconfig.for_review(config, task)
            if task == "workspace":
                import asrworkspace
                if not asrworkspace.sandbox_status()["available"]:
                    raise llmconfig.LLMError("workspace-unavailable", asrworkspace.sandbox_status()["say"])
        except llmconfig.LLMError as e:
            raise Refusal(e.code, e.say, 409)
        if previous and job.get("llm_config_fingerprint") != llmconfig.fingerprint(config):
            previous = None
        _save_pending(job)
        cancel = llmadapter.Cancellation()
        job["llm_cancel"] = cancel
        job["llm_generation"] = job.get("llm_generation", 0) + 1
        generation = job["llm_generation"]
        job["review_choice"] = "llm"
        job['last_method'], job['last_word_ids'] = task, word_ids or []
        job.pop("external_review", None)
        job["llm_config_fingerprint"] = llmconfig.fingerprint(config)
        if word_ids is None:
            job["correction_result"] = None
            job["llm_diagnostics"] = []
            job["llm_diagnostics_bytes"] = 0
            job["llm_diagnostics_clipped"] = False
        job["correction"] = {"state": "running", "complete": False, "done": 0, "total": 0,
                             "unit": "words", "response_count": len(job.get("llm_diagnostics") or []),
                             "instruction_mode": instruction_mode,
                             "task": task,
                             "destination": config["base_url"], "model": llmconfig.for_review(config, task)["selected_model"],
                             "started": _now()}
        job["state"] = CORRECTING
        answer = _report(job)
    threading.Thread(target=_correct, args=(job, config, cancel, generation, word_ids, previous), daemon=True,
                     name="asr-correction").start()
    return answer


def _correct(job, config, cancel, generation, word_ids=None, previous=None):
    import asrcorrection
    import llmadapter
    import llmconfig
    stamp = llmconfig.fingerprint(config)
    task = job["correction"].get("task", "suspect")
    feature_config = llmconfig.for_review(config, task)

    def current():
        cancel.check()
        if not _review_source_current(job):
            raise llmconfig.LLMError("source-changed", "The local film changed during review. Transcribe it again.")
        if llmconfig.fingerprint(llmconfig.load()) != stamp:
            raise llmconfig.LLMError("settings-changed", "The LLM destination or model changed. Choose review again.")

    class SavedAdapter:
        def generate_text(self, *args, **kw):
            current()
            return llmadapter.adapter(feature_config).generate_text(*args, **kw)

        def agent_turn(self, *args, **kw):
            current()
            return llmadapter.adapter(feature_config).agent_turn(*args, **kw)

    def progress(done, total, phase=None):
        current()
        with LOCK:
            if generation == job.get("llm_generation") and job["state"] == CORRECTING:
                job["correction"].update(done=done, total=total)
                if phase:
                    job["correction"]["phase"] = phase

    def diagnostic(trace):
        # Explicitly inspectable feature data, kept only with this ephemeral
        # job. Never put prompts/replies in logs, prefs, sync or status.
        current()
        def redact(value):
            if isinstance(value, str):
                key = config.get("api_key")
                return value.replace(key, "[redacted credential]") if key else value
            if isinstance(value, list):
                return [redact(v) for v in value]
            if isinstance(value, dict):
                return {k: redact(v) for k, v in value.items()}
            return value
        trace = redact(trace)
        trace["run"] = generation
        size = len(json.dumps(trace, ensure_ascii=False).encode("utf-8"))
        with LOCK:
            if generation != job.get("llm_generation") or job["state"] != CORRECTING:
                return
            if size > 512 * 1024:
                job["llm_diagnostics_clipped"] = True
                return
            history = job.setdefault("llm_diagnostics", [])
            while history and (job.get("llm_diagnostics_bytes", 0) + size > 512 * 1024 or len(history) >= 100):
                old = history.pop(0)
                job["llm_diagnostics_bytes"] -= len(json.dumps(old, ensure_ascii=False).encode("utf-8"))
                job["llm_diagnostics_clipped"] = True
            history.append(trace)
            job["llm_diagnostics_bytes"] = job.get("llm_diagnostics_bytes", 0) + size
            job["correction"]["response_count"] = job["correction"].get("response_count", 0) + 1

    try:
        if task == "workspace":
            import asrworkspace
            out = asrworkspace.correct(job["review_evidence"], SavedAdapter(), cancel, progress,
                                       config.get("context_tokens", 8192), diagnostic, word_ids)
        else:
            out = asrcorrection.correct(job["review_evidence"], SavedAdapter(), cancel, progress,
                                        config.get("context_tokens", 8192), diagnostic, word_ids,
                                        job["correction"].get("instruction_mode") == "skill", task)
        current()
        with LOCK:
            if generation != job.get("llm_generation") or job["state"] != CORRECTING:
                return
            if word_ids is not None and previous:
                selected = set(out.get("reviewed_word_ids", word_ids))
                # A retry updates only its selected words. Other proposals and
                # the browser's accepted/manual draft remain available.
                out["suggestions"] = [s for s in previous["suggestions"] if not selected.intersection(s.get("word_ids", [s["word_id"]]))] + out["suggestions"]
                if "failed_reasons" in out or previous.get("failed_reasons"):
                    out["failed_reasons"] = dict({w: say for w, say in previous.get("failed_reasons", {}).items() if w not in selected}, **out.get("failed_reasons", {}))
                if "kept" in out or previous.get("kept"):
                    out["kept"] = [k for k in previous.get("kept", []) if not selected.intersection(k["word_ids"])] + out.get("kept", [])
                for key in ("failed_word_ids", "uncertain_word_ids"):
                    out[key] = [w for w in previous.get(key, []) if w not in selected] + out[key]
                out["assessment"] = "suggestions" if out["suggestions"] else out["assessment"]
            out["latest_word_ids"] = list(out.get("reviewed_word_ids", word_ids or []))
            job["correction_result"] = out
            job["correction"].update(state="complete", complete=True,
                                     failed_words=len(out.get("failed_word_ids", [])))
            job["state"], job["finished"] = DONE, _now()
            _save_pending(job)
    except Exception as e:
        # No tracebacks here: an unexpected exception may contain model text.
        safe = e if isinstance(e, llmconfig.LLMError) else llmconfig.LLMError(
            "correction-failed", "LLM review could not finish. The Whisper result is intact.")
        with LOCK:
            if generation != job.get("llm_generation") or job["state"] != CORRECTING:
                return
            job["correction_result"] = None
            job["correction"].update(state="failed", complete=False, code=safe.code, error=safe.say)
            job["state"], job["finished"] = REVIEW_CHOICE, _now()


def cancel_review(token):
    job = _job(token)
    proc = None
    with LOCK:
        if job["state"] == CORRECTING or (job["state"] == DONE and job.get("review_choice") in ("llm", "likelihood")):
            second = job.get('correction', {}).get('task') == 'whisper-second'
            job["llm_generation"] = job.get("llm_generation", 0) + 1
            cancel = job.pop("llm_cancel", None)
            if cancel:
                cancel.cancel()
            if second:
                proc = job.get('proc')
                job['correction'] = job.pop('second_pass_previous', {}).get('correction', {'state':'not-requested', 'complete':False})
            else:
                job["correction_result"] = None
                job["correction"].update(state="cancelled", complete=False,
                                         error="Model review was cancelled. Your transcript draft is intact.")
            job["state"], job["finished"] = DONE, _now()
        if proc is not None:
            _kill(proc)
            try:
                proc.wait(10)
            except (OSError, subprocess.TimeoutExpired):
                pass
        _save_pending(job)
        return _report(job)


def review_whisper_second(token, source_sha256, word_ids=None):
    """Recheck immutable original spans; request bodies cannot choose audio/model paths."""
    import asrcorrection
    import llmadapter
    job = _job(token)
    with LOCK:
        if job['state'] not in (DONE, REVIEW_CHOICE) or job.get('review_used'):
            raise Refusal('wrong-state', 'Wait for the current tool or stop it before running Whisper again.', 409)
        evidence = job.get('review_evidence')
        if not evidence or source_sha256 != evidence['source_sha256']:
            raise Refusal('stale-review', 'That review no longer matches the original transcript.', 409)
        if not _review_source_current(job):
            raise Refusal('source-changed', 'The local film changed. Transcribe it again.', 409)
        if any(j is not job and j['state'] in ACTIVE for j in JOBS.values()):
            raise Refusal('busy', 'Another transcription or review tool is running.', 409)
        source = job.get('whisper_source')
        if not source:
            raise Refusal('audio-gone', 'This older review has no original audio mapping. Transcribe again to use this tool.', 409)
        sources = asrcorrection.index(evidence)
        if word_ids is None:
            word_ids = [ident for ident in job.get('first_suspect_word_ids', [])
                        if sources[ident].get('second_pass', {}).get('state') != 'complete']
        if (not isinstance(word_ids, list) or not word_ids or len(word_ids) > len(sources)
                or any(not isinstance(w, str) or w not in sources or not sources[w]['reviewable'] for w in word_ids)
                or len(set(word_ids)) != len(word_ids)):
            raise Refusal('bad-review', 'Choose words from this transcript to recheck.')
        locked = set(job.get('review_draft', {}).get('locked_word_ids', []))
        ids = [ident for ident in word_ids if ident not in locked]
        if not ids:
            raise Refusal('no-targets', 'Unlock a word before rechecking it.', 409)
        if any(ident not in source['word_map'] for ident in ids):
            raise Refusal('missing-timestamps', 'Some selected words have no original audio timestamps.', 409)
        gs = _getstt()
        if not gs.runtime_ready() or not gs.model_ready(job['model']):
            raise Refusal('not-installed', 'Install the original Whisper model in Speech to text settings first.', 409)
        # Check the recording before taking the slot or loading any model.
        _spec(gs, job, recheck=True)
        job['llm_generation'] = job.get('llm_generation', 0) + 1
        generation = job['llm_generation']
        cancel = llmadapter.Cancellation()
        job['llm_cancel'] = cancel
        job['second_pass_previous'] = {'correction': dict(job.get('correction') or {})}
        job['second_pass'] = {'done': 0, 'total': len(ids), 'failed': 0, 'failures': []}
        job['correction'] = {'state': 'running', 'complete': False, 'task': 'whisper-second',
                             'done': 0, 'total': len(ids), 'started': _now(), 'model': job['model']}
        job['state'] = CORRECTING
        answer = _report(job)
    threading.Thread(target=_recheck_whisper, args=(job, gs, ids, cancel, generation), daemon=True,
                     name='whisper-second-review').start()
    return answer


def _recheck_whisper(job, gs, ids, cancel, generation):
    import copy
    import asrcorrection
    import whispersecond
    proc = None
    spec_path = _named(job['id'], '.review-%d.spec.json' % generation)
    log_path = _named(job['id'], '.review-%d.log' % generation)
    outputs, failures = {}, {}
    worker_ids = {}
    raw_words = {}
    try:
        worker_ids = {job['whisper_source']['word_map'][ident]: ident for ident in ids}
        raw_words = {w['word_id']: w for seg in job['whisper_source']['segments'] for w in seg['asr_words']}
        with contextlib.ExitStack() as hold:
            hold.enter_context(_using(gs, job['model']))
            spec = _spec(gs, job, recheck=True)
            spec['recheck'] = {'segments': copy.deepcopy(job['whisper_source']['segments']), 'word_ids': list(worker_ids)}
            with open(spec_path, 'w', encoding='utf-8') as f:
                json.dump(spec, f, allow_nan=False)
            with LOCK:
                if cancel.event.is_set() or job.get('llm_generation') != generation:
                    return
                # These are private per-run files; never reuse a cancelled run's files.
                spawn_job = dict(job, spec=spec_path, log=log_path)
                proc = _spawn(gs, spawn_job, spec_path)
                job['proc'] = proc
            if proc is None:
                return
            while True:
                line = proc.stdout.readline(MAX_LINE)
                if not line:
                    break
                if len(line) >= MAX_LINE and not line.endswith('\n'):
                    _kill(proc)
                    break
                with LOCK:
                    if cancel.event.is_set() or job.get('llm_generation') != generation or not _review_source_current(job):
                        _kill(proc)
                        break
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if (not isinstance(msg, dict) or msg.get('t') != 'second-pass'
                        or not isinstance(msg.get('word_id'), str) or msg['word_id'] not in worker_ids):
                    continue
                wid = msg['word_id']
                if wid in outputs or wid in failures:
                    continue
                before, after = raw_words[wid], msg.get('word_evidence')
                if (not isinstance(after, dict) or any(before.get(k) != after.get(k) for k in ('text', 'start', 'end', 'score'))):
                    failures[wid] = 'ambiguous-alignment'
                elif msg.get('state') == 'complete':
                    outputs[wid] = after
                else:
                    failures[wid] = msg.get('reason') if msg.get('reason') in whispersecond.REASONS else 'transcription-failed'
                with LOCK:
                    if job.get('llm_generation') == generation:
                        job['second_pass']['done'] = len(outputs) + len(failures)
                        job['second_pass']['failed'] = len(failures)
                        job['correction']['done'] = job['second_pass']['done']
            proc.wait()
    except Exception:
        # A failed worker affects this tool only, never the first transcript/draft.
        pass
    finally:
        if proc is not None:
            if proc.poll() is None:
                _kill(proc)
            try:
                proc.wait(10)
            except (OSError, subprocess.TimeoutExpired):
                pass
            with LOCK:
                CHILDREN.discard(proc)
                if job.get('proc') is proc:
                    job['proc'] = None
            untrack = getattr(gs, 'untrack', None)
            if callable(untrack):
                untrack(proc)
        _remove(spec_path, log_path)
    with LOCK:
        if cancel.event.is_set() or job.get('llm_generation') != generation or job['cancelled']:
            return
        if not _review_source_current(job):
            job['correction'].update(state='failed', code='source-changed', complete=False,
                                     error='The source changed during the Whisper second pass.')
        else:
            public = asrcorrection.index(job['review_evidence'])
            if not worker_ids:
                worker_ids = {ident: ident for ident in ids}
            for wid, ident in worker_ids.items():
                word = public[ident]
                if wid in outputs:
                    checked = _evidence_words([outputs[wid]])[0]
                    # Keep the original confidence, source offsets and video-clock timing.
                    for key in ('asr_alternatives', 'alternatives_available', 'second_pass'):
                        if key in checked:
                            word[key] = checked[key]
                            raw_words[wid][key] = copy.deepcopy(checked[key])
                else:
                    reason = failures.setdefault(wid, 'worker-stopped')
                    word['second_pass'] = {'state':'failed', 'reason':reason}
            job['second_pass'] = {'done':len(ids), 'total':len(ids), 'failed':len(failures),
                'failures':[{'word_id':worker_ids[wid], 'reason':reason} for wid, reason in failures.items()]}
            job['review_evidence']['second_pass'] = copy.deepcopy(job['second_pass'])
            job['last_method'], job['last_word_ids'] = 'whisper-second', ids
            job['correction'] = job.pop('second_pass_previous', {}).get('correction', {'state':'not-requested', 'complete':False})
        job['state'], job['finished'] = DONE, _now()
        _save_pending(job)


def review_likelihood(token, source_sha256, revision, word_ids=None, phonetic_filter=None):
    """Additional numeric method. Job input cannot choose a path or runtime."""
    import asrcorrection
    import lmlikelihoodconfig as lc
    import llmadapter
    from lmgguf import ScoringError, revalidate
    job = _job(token)
    with LOCK:
        if job["state"] not in (REVIEW_CHOICE, DONE):
            raise Refusal("wrong-state", "Wait for Whisper or cancel the current review.", 409)
        if not job.get("review_evidence") or source_sha256 != job["review_evidence"]["source_sha256"]:
            raise Refusal("stale-review", "That review no longer matches the Whisper result.", 409)
        if not _review_source_current(job):
            raise Refusal("source-changed", "The local film changed. Transcribe it again.", 409)
        if any(j is not job and j["state"] in ACTIVE for j in JOBS.values()):
            raise Refusal("busy", "Another transcription or model review is running.", 409)
        config = lc.load()
        if lc.INSTALL['state'] == 'installing':
            raise Refusal("runtime-installing", "Wait for the isolated scoring runtime to finish rebuilding.", 409)
        if revision != lc.revision(config):
            raise Refusal("settings-changed", "The likelihood model or worker settings changed. Inspect them and choose review again.", 409)
        if not config["model"]:
            raise Refusal("likelihood-unconfigured", "Select an installed GGUF in LM likelihood settings first.", 409)
        try:
            revalidate(config["model"])
        except ScoringError as e:
            raise Refusal(e.code, e.say, 409)
        sources = asrcorrection.index(job["review_evidence"])
        previous = job.get("correction_result")
        if previous and (previous.get("task") != "likelihood" or job.get("likelihood_revision") != revision):
            previous = None
        reset = word_ids is None or previous is None
        if phonetic_filter is not None:
            if type(phonetic_filter) is not bool:
                raise Refusal("bad-review", "The similar-sound option must be on or off.")
            config = dict(config, phonetic_filter=phonetic_filter)
        if word_ids is not None and (not isinstance(word_ids, list) or not word_ids or len(word_ids) > len(sources)
                or any(not isinstance(w, str) or w not in sources or not sources[w]["reviewable"] for w in word_ids)
                or len(set(word_ids)) != len(word_ids)):
            raise Refusal("bad-review", "Choose mapped words from this Whisper result.")
        word_ids = _review_targets(job, "likelihood", word_ids)
        _save_pending(job)
        cancel = llmadapter.Cancellation()
        job["llm_cancel"] = cancel
        job["llm_generation"] = job.get("llm_generation", 0) + 1
        generation = job["llm_generation"]
        job["review_choice"] = "likelihood"
        job['last_method'], job['last_word_ids'] = 'likelihood', word_ids
        job.pop("external_review", None)
        job["likelihood_revision"] = revision
        if reset:
            job["correction_result"] = None
            job["llm_diagnostics"] = []
            job["llm_diagnostics_clipped"] = False
            job["llm_diagnostics_bytes"] = 0
        total = len(word_ids)
        job["correction"] = {"state": "running", "complete": False, "done": 0, "total": total,
            "unit": "words", "task": "likelihood", "destination": "Local standalone scoring worker",
            "model": config["model"]["model_id"], "started": _now(), "phase": "loading likelihood model"}
        job["state"] = CORRECTING
        answer = _report(job)
    threading.Thread(target=_likelihood_correct, args=(job, config, cancel, generation, word_ids, previous),
                     daemon=True, name="asr-likelihood").start()
    return answer


def _likelihood_correct(job, config, cancel, generation, word_ids, previous):
    import lmlikelihood
    import lmlikelihoodconfig as lc
    from lmgguf import ScoringError, revalidate
    stamp = job.get("likelihood_revision", lc.revision(config))
    def current():
        cancel.check()
        if generation != job.get("llm_generation") or job["state"] != CORRECTING:
            raise ScoringError("cancelled", "Likelihood review was cancelled.")
        if not _review_source_current(job):
            raise ScoringError("source-changed", "The local film changed during review. Transcribe it again.")
        if lc.revision(lc.load()) != stamp:
            raise ScoringError("settings-changed", "The likelihood model or worker settings changed. Choose review again.")
        revalidate(config["model"])
    def progress(done, total, phase):
        current()
        with LOCK:
            job["correction"].update(done=done, total=total, phase=phase)
    def diagnostic(trace):
        current()
        trace["run"] = generation
        size = len(json.dumps(trace, ensure_ascii=True).encode())
        with LOCK:
            history = job.setdefault("llm_diagnostics", [])
            if size > 512 * 1024:
                job["llm_diagnostics_clipped"] = True
                return
            while history and (len(history) >= 100 or len(json.dumps(history, ensure_ascii=True).encode()) + size > 512 * 1024):
                history.pop(0); job["llm_diagnostics_clipped"] = True
            history.append(trace)
            job["correction"]["response_count"] = len(history)
    try:
        out = lmlikelihood.correct(job["review_evidence"], job["text"], config, current, progress, diagnostic, word_ids)
        current()
        with LOCK:
            if word_ids is not None and previous:
                selected = set(word_ids)
                out["suggestions"] = [s for s in previous["suggestions"] if s["word_id"] not in selected] + out["suggestions"]
                out["failed_word_ids"] = [w for w in previous.get("failed_word_ids", []) if w not in selected] + out["failed_word_ids"]
                out["storage_failed_word_ids"] = [w for w in previous.get("storage_failed_word_ids", []) if w not in selected] + out.get("storage_failed_word_ids", [])
                kept, bounded = 0, []
                for suggestion in out["suggestions"]:
                    size = len(json.dumps(suggestion, ensure_ascii=True).encode())
                    if kept + size <= lmlikelihood.MAX_REVIEW_BYTES:
                        bounded.append(suggestion); kept += size
                    else:
                        ident = suggestion["word_id"]
                        if ident not in out["failed_word_ids"]:
                            out["failed_word_ids"].append(ident)
                        if ident not in out["storage_failed_word_ids"]:
                            out["storage_failed_word_ids"].append(ident)
                out["suggestions"] = bounded
                out["complete"] = not out["failed_word_ids"]
            out["latest_word_ids"] = list(out.get("reviewed_word_ids", word_ids or []))
            job["correction_result"] = out
            job["correction"].update(state="complete" if out["complete"] else "partial", complete=out["complete"],
                                     failed_words=len(out["failed_word_ids"]))
            job["state"], job["finished"] = DONE, _now()
            _save_pending(job)
    except Exception as e:
        with LOCK:
            if generation != job.get("llm_generation") or job["state"] != CORRECTING:
                return
            job["correction_result"] = None
            job["correction"].update(state="failed", complete=False, code=e.code if isinstance(e, ScoringError) else "worker-failed",
                error=e.say if isinstance(e, ScoringError) else "Likelihood review could not finish. The Whisper result is intact.")
            job["state"], job["finished"] = REVIEW_CHOICE, _now()


def _external_job(token, source_sha256, session=None):
    job = _job(token)
    if (job["state"] not in (DONE, REVIEW_CHOICE) or not job.get("review_evidence")
            or source_sha256 != job["review_evidence"]["source_sha256"]):
        raise Refusal("stale-review", "That external review no longer matches the pending Whisper result.", 409)
    if not _review_source_current(job):
        raise Refusal("source-changed", "The local film changed. Transcribe it again.", 409)
    if session is not None and (not isinstance(session, str) or not session or job.get("review_choice") != "external" or session != job.get("external_review", {}).get("id")):
        raise Refusal("stale-review", "This external prompt was replaced. Prepare a new prompt.", 409)
    job["touched"] = _now()
    return job


def _external_view(job):
    ext = job.get("external_review")
    if not ext or job.get("review_choice") != "external":
        return None
    import asrexternal
    index = ext["index"]
    return {"id": ext["id"], "task": ext["task"], "index": index, "batches": len(ext["batches"]),
            "finished": ext["finished"], "submitted": sorted(ext["answers"]),
            "words_done": sum(len(asrexternal.ids(ext["batches"][i])) for i in ext["answers"]),
            "words_total": sum(len(asrexternal.ids(batch)) for batch in ext["batches"]),
            "divided": ext.get("divided", True),
            "prompt": ext["prompt"] if not ext["finished"] else "", "prompt_error": ext.get("prompt_error", "")}


def external_start(token, source_sha256, task, word_ids=None, divide=False):
    import asrexternal
    import asrcorrection
    with LOCK:
        job = _external_job(token, source_sha256)
        sources = asrcorrection.index(job["review_evidence"])
        if word_ids is not None and (not isinstance(word_ids, list) or not word_ids
                or any(not isinstance(ident, str) or ident not in sources or not sources[ident]["reviewable"] for ident in word_ids)
                or len(set(word_ids)) != len(word_ids) or len(word_ids) > len(sources)):
            raise Refusal("bad-review", "Choose mapped words from this Whisper result.")
        try:
            word_ids = _review_targets(job, task, word_ids)
            # only a reasoning workspace can go undivided (asrexternal.batches says why), and it does unless asked
            divided = task != "workspace" or divide is True
            batches = asrexternal.batches(job["review_evidence"], task, word_ids, divided)
            first = asrexternal.prompt(job["review_evidence"], task, batches[0], divided) if batches else ""
        except Exception as error:
            if hasattr(error, "say"):
                raise Refusal(error.code, error.say)
            raise Refusal("bad-review", "The external prompt could not be prepared.")
        previous = job.get("correction_result")
        base = previous if word_ids is not None and previous and previous.get("task") == task else None
        job["external_review"] = {"id": secrets.token_urlsafe(18), "task": task, "index": 0,
                                  "batches": batches, "divided": divided, "answers": {}, "attempts": {}, "finished": not batches, "base": base, "prompt": first}
        job["review_choice"] = "external"
        job["state"], job["finished"] = DONE, _now()
        job["correction"] = {"state": "awaiting-paste" if batches else "complete", "complete": not batches,
                             "unit": "words", "task": task, "method": "external", "done": 0,
                             "total": sum(len(asrexternal.ids(batch)) for batch in batches)}
        _external_merge(job)
        return result(token)


def _external_merge(job):
    import asrexternal
    ext = job["external_review"]
    selected = set().union(*(asrexternal.ids(batch) for batch in ext["batches"]))
    base = ext["base"] or {}
    out = {"schema_version": 1, "task": ext["task"], "method": "external-" + ext["task"],
           "suggestions": [s for s in base.get("suggestions", []) if not selected.intersection(s.get("word_ids", [s["word_id"]]))],
           "kept": [k for k in base.get("kept", []) if not selected.intersection(k["word_ids"])],
           "failed_reasons": {w: say for w, say in base.get("failed_reasons", {}).items() if w not in selected}}
    for field in ("failed_word_ids", "uncertain_word_ids", "reviewed_word_ids"):
        out[field] = [ident for ident in base.get(field, []) if ident not in selected]
    for answer in ext["answers"].values():
        out["suggestions"].extend(answer["suggestions"])
        out["kept"].extend(answer.get("kept", []))
        out["failed_reasons"].update(answer.get("failed_reasons", {}))
        for field in ("failed_word_ids", "uncertain_word_ids", "reviewed_word_ids"):
            out[field].extend(answer[field])
    if ext["finished"]:
        unseen = selected - set(out["reviewed_word_ids"])
        out["failed_word_ids"].extend(sorted(unseen))
        out["uncertain_word_ids"].extend(sorted(unseen))
        out["failed_reasons"].update((w, "its prompt's answer was never imported") for w in unseen)
    out["assessment"] = ("no_flagged_words" if ext["task"] == "suspect" else "no_reviewable_words") if not selected else (
        "partial" if out["failed_word_ids"] else "suggestions" if out["suggestions"] else "kept_original")
    out["words_reviewed"] = sum(len(asrexternal.ids(ext["batches"][i])) for i in ext["answers"])
    out["words_total"] = sum(len(asrexternal.ids(batch)) for batch in ext["batches"])
    out["latest_word_ids"] = sorted(selected)
    job["correction_result"] = out
    job["correction"].update(done=out["words_reviewed"], total=out["words_total"],
                             failed_words=len(out["failed_word_ids"]), complete=ext["finished"],
                             state="complete" if ext["finished"] else "awaiting-paste")


def external_action(token, source_sha256, session, action, index=None, answer=None):
    import asrexternal
    import llmconfig
    with LOCK:
        if not isinstance(session, str) or not session:
            raise Refusal("stale-review", "Prepare an external prompt before importing an answer.", 409)
        job = _external_job(token, source_sha256, session)
        ext = job["external_review"]
        if action == "cancel":
            job.pop("external_review", None); job["review_choice"] = None
            job["correction_result"] = None; job["correction"] = {"state": "not-requested", "complete": False}
            job["state"], job["finished"] = REVIEW_CHOICE, _now()
            return result(token)
        if ext["finished"]:
            raise Refusal("stale-review", "This external review is finished. Prepare another prompt to retry.", 409)
        # An open copy/paste review may take longer than ASR result retention.
        # Refresh only this in-memory review; it still occupies no job slot.
        if action == "keep-alive":
            job["finished"] = _now()
            return {"kept": True}
        if action in ("prompt", "answer"):
            if type(index) is not int or not 0 <= index < len(ext["batches"]):
                raise Refusal("bad-review", "Choose a prompt batch from this review.")
        if action == "answer":
            try:
                parsed = asrexternal.parse(job["review_evidence"], ext["task"], ext["batches"][index], answer)
                current_prompt = asrexternal.prompt(job["review_evidence"], ext["task"], ext["batches"][index], ext.get("divided", True))
            except llmconfig.LLMError as error:
                raise Refusal(error.code, error.say)
            ext["answers"][index] = parsed
            ext["attempts"][index] = ext["attempts"].get(index, 0) + 1
            ext.update(index=index, prompt=current_prompt, prompt_error="")
            config = llmconfig.load() or {}
            key = config.get("api_key")
            def safe(text):
                if key:
                    # Raw pasted CSV and JSON can escape quotes in a key.
                    variants = {key, key.replace('"', '""'), json.dumps(key, ensure_ascii=False)[1:-1]}
                    for value in sorted(variants, key=len, reverse=True):
                        text = text.replace(value, "[redacted credential]")
                return text
            trace = {"run": ext["id"], "sentence_id": "external-batch%d" % index, "attempt": ext["attempts"][index], "state": "complete",
                     "source": "\n".join(unit["text"] for unit in ext["batches"][index]),
                     "word_ids": parsed["reviewed_word_ids"], "answer": safe(answer)[:16000], "ignored_edits": parsed["ignored_edits"],
                     "prompt": [{"role": "user", "content": safe(current_prompt)[:32000]}]}
            # Redact strings before JSON encoding, including quoted keys in
            # pasted explanations. Never replace JSON syntax or numeric values.
            def redact(value):
                if isinstance(value, str):
                    return safe(value)
                if isinstance(value, list):
                    return [redact(item) for item in value]
                if isinstance(value, dict):
                    return {name: redact(item) for name, item in value.items()}
                return value
            trace = redact(trace)
            history = job.setdefault("llm_diagnostics", [])
            history.append(trace)
            while len(history) > 100 or len(json.dumps(history, ensure_ascii=False).encode("utf-8")) > 512 * 1024:
                history.pop(0); job["llm_diagnostics_clipped"] = True
            job["llm_diagnostics_bytes"] = len(json.dumps(history, ensure_ascii=False).encode("utf-8"))
            if len(ext["answers"]) == len(ext["batches"]):
                ext["finished"] = True
            else:
                following = next(i for i in range(len(ext["batches"])) if i not in ext["answers"])
                try:
                    text = asrexternal.prompt(job["review_evidence"], ext["task"], ext["batches"][following], ext.get("divided", True))
                    ext.update(index=following, prompt=text)
                except llmconfig.LLMError as error:
                    # A later prompt failure must preserve this imported batch.
                    ext["prompt_error"] = error.say
        elif action == "prompt":
            try:
                text = asrexternal.prompt(job["review_evidence"], ext["task"], ext["batches"][index], ext.get("divided", True))
            except llmconfig.LLMError as error:
                raise Refusal(error.code, error.say)
            ext.update(index=index, prompt=text, prompt_error="")
        elif action == "finish":
            ext["finished"] = True
        elif action != "prompt":
            raise Refusal("bad-review", "Choose prompt, import answer, finish or cancel.")
        _external_merge(job)
        job["finished"] = _now()
        return result(token)


def external_files(token, source_sha256, session, index):
    import asrexternal
    with LOCK:
        if not isinstance(session, str) or not session:
            raise Refusal("stale-review", "Prepare a workspace prompt before downloading its files.", 409)
        job = _external_job(token, source_sha256, session)
        ext = job["external_review"]
        if ext["task"] != "workspace" or type(index) is not int or not 0 <= index < len(ext["batches"]):
            raise Refusal("bad-review", "Choose this workspace review's prompt batch.")
        try:
            units = ext["batches"][index]
            return asrexternal.bundle(job["review_evidence"], units, asrexternal.prompt(job["review_evidence"], ext["task"], units, ext.get("divided", True)))
        except Exception as error:
            if hasattr(error, "say"):
                raise Refusal(error.code, error.say)
            raise Refusal("external-download", "The text workspace could not be prepared.")


def use_review(token, source_sha256, decisions, manual_edits=None):
    """Apply only chosen validated spans. Caption clocks/boundaries stay put."""
    import asrcorrection
    import llmconfig
    import wordtimes
    import ytpages
    job = _job(token)
    with LOCK:
        if job["state"] not in (DONE, REVIEW_CHOICE):
            raise Refusal("review-first", "Wait for the current tool or stop it before using the transcript.", 409)
        if job.get("review_choice") == "external" and not job.get("external_review", {}).get("finished"):
            raise Refusal("review-first", "Finish importing answers or choose Review received suggestions first.", 409)
        if not _review_source_current(job):
            raise Refusal("source-changed", "The local film changed. Transcribe it again.", 409)
        if (job["review_choice"] == "llm" and
                job.get("llm_config_fingerprint") != llmconfig.fingerprint(llmconfig.load())):
            job["correction_result"] = None
            job["correction"].update(state="failed", complete=False,
                error="The LLM settings changed. Choose review again; the old suggestions were discarded.")
            job["state"], job["finished"] = REVIEW_CHOICE, _now()
            raise Refusal("stale-review", "The LLM settings changed. Choose review again.", 409)
        if job["review_choice"] == "likelihood":
            import lmlikelihoodconfig as lc
            from lmgguf import ScoringError, revalidate
            cfg = lc.load()
            try:
                if job.get("likelihood_revision") != lc.revision(cfg) or not cfg["model"]:
                    raise ScoringError("settings-changed", "The likelihood model or worker settings changed. Choose review again.")
                revalidate(cfg["model"])
            except ScoringError as e:
                job["correction_result"] = None
                job["correction"].update(state="failed", complete=False, code=e.code, error=e.say)
                job["state"], job["finished"] = REVIEW_CHOICE, _now()
                raise Refusal("stale-review", e.say, 409)
        evidence = job["review_evidence"]
        if source_sha256 != evidence["source_sha256"]:
            raise Refusal("stale-review", "That review no longer matches the Whisper result.", 409)
        try:
            panel, changed = asrcorrection.apply(job["text"], evidence,
                job.get("correction_result") or {"suggestions": []}, decisions, manual_edits)
        except llmconfig.LLMError as e:
            raise Refusal(e.code, e.say)
        original = ytpages.parse_transcript_text(job["text"], job["lang"])
        caps = ytpages.parse_transcript_text(panel, job["lang"])
        if [c["start"] for c in caps] != [c["start"] for c in original]:
            raise Refusal("invalid-suggestions", "That edit would change the caption boundaries; it was not applied.")
        out = result(token)
        out["text"] = panel
        # Rebuild from the immutable capture tape so a retried Use with a
        # different decision set does not inherit an earlier pending edit.
        doc = wordtimes.load(token)
        if doc:
            import copy
            doc["atoms"] = copy.deepcopy(doc.get("raw_atoms") or doc["atoms"])
            doc = wordtimes.sync(doc, caps, job["lang"])
            doc["panel_sha256"] = wordtimes.panel_hash(panel)
            wordtimes.hold(token, doc)
            out["words"] = dict(out["words"], panel_sha256=doc["panel_sha256"],
                                count=len(doc.get("atoms") or []), timings_stale=changed)
        if changed:
            # Audio has been deleted, so no exact re-alignment can be claimed.
            out["notes"].append("Caption timings are unchanged. Changed word timings need review in Edit the transcript.")
        job["review_used"] = True
        import asrpending
        asrpending.remove(token)
        return out


# -------------------------------------------------------------------- the child
def _spec(gs, job, recheck=False):
    """What the worker is told: all of it made HERE, from what was checked."""
    pcm = job["kind"] == "youtube"
    if job.get('model_revision') and job['model_revision'] != speechmodels.provenance(job['model']):
        raise Refusal('model-changed', 'The speech model package changed. Transcribe again before running another pass.', 409)
    try:
        model_path = gs.model_dir(job["model"])
    except (ValueError, OSError):
        raise Refusal("no-model", "The selected model is not installed.", 409)
    if pcm:
        import asrpending
        source = str(asrpending.audio_path(job['id'])) if recheck else job["pcm"]
        if not source or not os.path.isfile(source):
            raise Refusal("audio-gone", "The original recording is no longer available. Record the video again to use Whisper's second pass."
                          if recheck else "The temporary recording disappeared.", 410)
    else:
        source = job["source"]["path"]
        try:
            st = os.stat(source)
        except OSError:
            raise Refusal("film-unreadable", "The local film could not be read.", 422)
        if [st.st_size, st.st_mtime_ns, st.st_ino] != job["film"]:
            raise Refusal("film-changed", "The film changed since you named it -- name "
                          "it again.", 409)
    return {"source_path": source, "audio_kind": "pcm16" if pcm else "media",
            "model_id": job['model'],
            "lang": job["wlang"], "model_path": model_path, "device": job["planned"],
            "cpu_threads": job["threads"],
            "compute": {"cpu": "int8", "cuda": ["int8_float16", "float16"]},
            "mode": job["mode"], "film": job["film"], "parent": os.getpid(),
            "second_pass": False if recheck else job.get('automatic_second_pass', True),
            "aligner_path": (gs.aligner_path(job["aligner"]) if job.get("aligner") and not recheck else None)}


def _spawn(gs, job, spec_path):
    """The worker, in a process group of its own, and registered wherever the
    server looks to end its children -> the process, or None if the job was
    cancelled in the meantime."""
    env = dict(os.environ)
    env.update(_speech(lambda g: g.worker_env()))
    # nothing of the user's site-packages, no bytecode written into the
    # runtime, and no script directory on the path in front of it
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONSAFEPATH="1", PYTHONIOENCODING="utf-8")
    kw = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "env": env,
          "text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1,
          "cwd": os.path.dirname(spec_path)}
    if WIN:
        kw["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                               | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kw["start_new_session"] = True
        if sys.platform.startswith("linux"):
            kw["preexec_fn"] = _preexec
    with LOCK:
        if job["cancelled"]:
            return None
        with open(job["log"], "ab") as errs:
            proc = subprocess.Popen([sys.executable, "-B", "-u", WORKER, spec_path],
                                    stderr=errs, **kw)
        job["proc"] = proc
        CHILDREN.add(proc)
    track = getattr(gs, "track", None)
    if callable(track):
        track(proc)
    return proc


def _run(job):
    """The whole life of one job after its audio is in: the spec, the child,
    what it says, and the tidying up whatever happens."""
    import asrpending
    proc = None
    gs = None
    try:
        gs = _getstt()
        # (the model is held already: start() took it for the whole of the job)
        with LOCK:
            if job["cancelled"]:
                return
            job["state"], job["started"] = PREPARING, _now()
        spec = _spec(gs, job)
        with open(job["spec"], "w", encoding="utf-8") as f:
            json.dump(spec, f)
        proc = _spawn(gs, job, job["spec"])
        if proc is None:
            return
        got = _listen(job, proc)
        rc = proc.wait()
        for pipe in (proc.stdin, proc.stdout):
            if pipe:
                pipe.close()
        # Keep captured sound only with the private pending draft, for later
        # rechecks. Use or discard deletes it; scratch files are cleaned now.
        _show_log(job)
        if not job['cancelled'] and (got.get('done') is not None or got.get('first') is not None):
            try:
                asrpending.retain_audio(job)
            except (OSError, ValueError):
                job['notes'].append('The original recording could not be kept for later Whisper rechecks. You can still review or edit this transcript.')
        _clean_files(job)
        if job["cancelled"]:
            return
        if got.get('first') is not None and not _review_source_current(job):
            _end(job, FAILED, 'film-changed', 'The film changed during transcription. Name it again to transcribe the current file.')
            return
        if got.get("done") is not None:
            _finish(job, got["done"])
        elif got.get('first') is not None:
            # Native crashes during a crop must not discard successful first ASR.
            _second_pass_incomplete(job)
            _finish(job, got['first'])
        elif got.get("error") is not None:
            _end(job, FAILED, got["error"]["code"], got["error"]["say"])
        elif rc in (-9, 137):
            _end(job, FAILED, "killed", "Transcription was stopped by the system, most "
                 "likely because the computer ran out of memory.")
        else:
            _end(job, FAILED, "failed", "Transcription failed.")
    except Refusal as e:
        _end(job, FAILED, e.code, e.say)
    except Exception:                                        # noqa: BLE001
        traceback.print_exc()
        _end(job, FAILED, "failed", "Transcription failed.")
    finally:
        if proc is not None:
            if proc.poll() is None:
                _kill(proc)
            for pipe in (proc.stdin, proc.stdout):
                if pipe and not pipe.closed:
                    pipe.close()
            with LOCK:
                CHILDREN.discard(proc)
                if job.get('proc') is proc:
                    job["proc"] = None
            untrack = getattr(gs, "untrack", None)
            if callable(untrack):
                untrack(proc)
        # (again, and harmless once it has been done: what is left of a job that
        # went wrong before its worker ended)
        _show_log(job)
        _clean_files(job)
        if job.get('cancelled') or job['state'] == FAILED:
            try:
                asrpending.remove(job['id'])
            except OSError:
                pass
        _unhold(job)                     # whatever way this thread ended, the part goes


def _show_log(job):
    """The worker's own stderr -- where the technical GPU error and any
    traceback are -- into the server's log, for whoever looks; never into an
    answer."""
    try:
        with open(job["log"], encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
    except OSError:
        return
    if text:
        print("speech to text (%s):\n%s" % (job["kind"], text[-4000:]), file=sys.stderr,
              flush=True)


def _listen(job, proc):
    """Read the worker's lines until it is done -> {"done": msg, "error": msg}
    (whichever came).  Anything that is not a JSON object is ignored."""
    got = {"done": None, "error": None}
    while True:
        line = proc.stdout.readline(MAX_LINE)
        if not line:
            return got
        if len(line) >= MAX_LINE and not line.endswith("\n"):
            _kill(proc)
            got["error"] = {"code": "failed", "say": "Transcription failed."}
            return got
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if isinstance(msg, dict):
            if msg.get('t') == 'first-pass':
                got['first'] = msg
                _prepare_second_pass(job, msg)
                if job['cancelled'] or job['state'] == FAILED:
                    _kill(proc)
                    return got
                try:
                    proc.stdin.write(json.dumps({'word_ids': job['second_pass_ids']})+'\n')
                    proc.stdin.flush()
                except (OSError, ValueError):
                    _kill(proc)
                    return got
                continue
            if msg.get('t') in ('second-pass', 'done') and got.get('first') is not None and not _review_source_current(job):
                _kill(proc)
                got['done'] = None
                return got
            if msg.get('t') == 'second-pass' and isinstance(msg.get('word_evidence'), dict) and got.get('first'):
                # Retain completed crops even if native decoding of a later one
                # kills the process. Only candidate evidence may change.
                match = re.fullmatch(r's(\d+)w(\d+)', str(msg.get('word_id', '')))
                if match and msg['word_id'] in job.get('second_pass_ids', []):
                    si, wi = map(int, match.groups())
                    raw_words = got['first']['segments'][si]['asr_words']
                    before, after = raw_words[wi], msg['word_evidence']
                    if all(before.get(k) == after.get(k) for k in ('text', 'start', 'end', 'score')):
                        raw_words[wi] = after
            _message(job, msg, got)


def _num(v, low=0.0, high=1e9):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(min(high, max(low, v)))


def _message(job, msg, got):
    """One line of the worker's, believed as far as it can be checked."""
    kind = msg.get("t")
    with LOCK:
        if job["cancelled"]:
            return
        if kind == "device":
            # a second `device` is the one fall back: it starts over
            if msg.get("device") in ("cpu", "cuda"):
                job["device"] = msg["device"]
                job["fell_back"] = bool(msg.get("fell_back"))
                job["state"], job["done"] = LOADING, 0.0
        elif kind == "loading":
            job["state"] = LOADING
        elif kind == "aligning":
            job["state"] = ALIGNING
            total, done = _num(msg.get("total")), _num(msg.get("done"))
            if total:
                job["total"] = total
            if done is not None:
                job["done"] = done
        elif kind == "progress":
            # the first line, before the model is even asked for, only says how
            # long the audio is (0 of the whole); a later one, with something
            # done, says the words are being made
            total, done = _num(msg.get("total")), _num(msg.get("done"))
            if total:
                job["total"] = total
            if done is not None:
                job["done"] = done
                if done > 0 and job["state"] in (PREPARING, LOADING):
                    job["state"] = TRANSCRIBING
        elif kind == 'second-pass' and job.get('second_pass') is not None:
            job['state'] = SECOND_PASS
            p = job['second_pass']
            wid = msg.get('word_id')
            if wid in job.get('second_pass_ids', []) and wid not in job['second_pass_completed']:
                job['second_pass_completed'].add(wid)
                p['done'] = len(job['second_pass_completed'])
                if msg.get('state') == 'failed':
                    import whispersecond
                    reason = msg.get('reason') if msg.get('reason') in whispersecond.REASONS else 'transcription-failed'
                    p['failures'].append({'word_id': job['second_pass_map'][wid], 'reason': reason})
                    p['failed'] = len(p['failures'])
    if kind == "done":
        got["done"] = msg
    elif kind == "error":
        code = msg.get("code") if isinstance(msg.get("code"), str) else "failed"
        say = msg.get("say") if isinstance(msg.get("say"), str) else ""
        got["error"] = {"code": re.sub(r"[^a-z-]", "", code)[:40] or "failed",
                        "say": " ".join(say.split())[:300] or "Transcription failed."}


def _evidence_words(raw):
    import asrcorrection
    words = []
    for source_index, w in enumerate(raw):
        if not isinstance(w, dict) or not isinstance(w.get("text"), str):
            continue
        alt, available = asrcorrection.alternatives(w.get("asr_alternatives"))
        row = {"text": w["text"][:400], "source_word_index": source_index, "start": _num(w.get("start")),
                      "end": _num(w.get("end")), "score": asrcorrection.score(w.get("score")),
                      "asr_alternatives": alt,
                      "alternatives_available": w.get("alternatives_available", available) is True}
        if isinstance(w.get('second_pass'), dict):
            import whispersecond
            record = w['second_pass']
            row['second_pass'] = {'state': 'complete' if record.get('state') == 'complete' else 'failed'}
            if record.get('reason') in whispersecond.REASONS:
                row['second_pass']['reason'] = record['reason']
            for key in ('crop_start', 'crop_end'):
                if _num(record.get(key)) is not None:
                    row['second_pass'][key] = _num(record[key])
            best = record.get('best_candidate')
            if isinstance(best, str) and any(a['text'] == best for a in alt):
                row['second_pass']['best_candidate'] = best
        words.append(row)
    return words


def _segments(job, msg):
    """Checked first-pass source words, on the video's clock for review only."""
    import sttpanel
    segs = []
    raw = msg.get("segments")
    for source_index, s in enumerate(raw[:200000] if isinstance(raw, list) else []):
        if not isinstance(s, dict) or not isinstance(s.get("text"), str):
            continue
        a, b = _num(s.get("start")), _num(s.get("end"))
        if a is None:
            continue
        row = {"start": a, "end": b if b is not None else a, "text": s["text"][:4000], 'source_segment_index': source_index}
        words = []
        raw_words = s.get("words", []) if isinstance(s.get("words"), list) else []
        for w in raw_words[:MAX_LINE // 32]:
            if not isinstance(w, dict) or not isinstance(w.get("text"), str):
                continue
            wa, wb = _num(w.get("start")), _num(w.get("end"))
            if wa is None:
                continue
            words.append({"start": wa, "end": wb if wb is not None else wa,
                          "text": w["text"][:400], "score": _num(w.get("score"), -1e6, 1e6)})
        if words:
            row["words"] = words
        # ASR evidence is independent of the optional CTC word timing tape.
        if isinstance(s.get("asr_words"), list):
            row["asr_words"] = _evidence_words(s["asr_words"])
        else:
            row["asr_words"] = _evidence_words(raw_words if msg.get("word_source") != "aligner" else [])
        segs.append(row)
    if job["kind"] == "youtube" and job["marks"]:
        segs = sttpanel.remap(segs, job["marks"], SAMPLE_RATE)
    return segs


def _prepare_second_pass(job, msg):
    import sttpanel
    import asrcorrection
    import asrdictionary
    segs = _segments(job, msg)
    text, _ = sttpanel.segments_to_panel(segs)
    evidence = asrcorrection.evidence(segs, text, job['lang'])
    resolver = asrdictionary.Resolver(job['lang'])
    with LOCK:
        if job['cancelled']:
            return
        job['state'] = CHECKING
    if not resolver.enrich(evidence, lambda: job['cancelled']):
        return
    with LOCK:
        if job['cancelled']:
            return
        job['first_pass_evidence'], job['dictionary_resolver'] = evidence, resolver
        mapping = {}
        for si, segment in enumerate(evidence['segments']):
            for wi, word in enumerate(segment['words']):
                if asrcorrection.suspect(word):
                    source_words = segs[si].get('asr_words', [])
                    source_wi = source_words[wi]['source_word_index'] if wi < len(source_words) else wi
                    mapping['s%dw%d' % (segs[si]['source_segment_index'], source_wi)] = word['word_id']
        job['second_pass_map'] = mapping
        job['second_pass_ids'] = list(mapping)
        job['second_pass_completed'] = set()
        job['second_pass'] = {'done': 0, 'total': len(job['second_pass_ids']), 'failed': 0, 'failures': []}
        job['state'] = SECOND_PASS


def _second_pass_incomplete(job):
    """Mark unfinished words explicitly if a native crop kills the process."""
    p = job.get('second_pass')
    if p is None:
        return
    for wid in job.get('second_pass_ids', []):
        if wid not in job['second_pass_completed']:
            p['failures'].append({'word_id': job['second_pass_map'][wid], 'reason': 'worker-stopped'})
            job['second_pass_completed'].add(wid)
    p['done'], p['failed'] = len(job['second_pass_completed']), len(p['failures'])


def _finish(job, msg):
    """Both Whisper stages ended; retain source text and offer explicit review."""
    import sttpanel
    segs = _segments(job, msg)
    text, notes = sttpanel.segments_to_panel(segs)
    facts = sttpanel.facts(text, job["lang"]) if text.strip() else {"captions": 0}
    if not facts["captions"]:
        _end(job, FAILED, "no-speech", "No speech was heard in it. Check that the language "
             "is the one spoken, and that the video has sound.")
        return
    warning = ""
    if not facts.get("want"):
        import languages
        L = languages.LANGS.get(job["lang"])
        warning = ("Every caption came out in another script than %s: is the language "
                   "the one spoken?" % (L.name if L else job["lang"]))
    word_info = {"held": False, "count": 0}
    all_words = [w for seg in segs for w in (seg.get("words") or [])]
    if all_words:
        try:
            import wordtimes
            import ytpages
            source = msg.get("word_source") if msg.get("word_source") in ("whisper", "aligner") else "whisper"
            doc = wordtimes.empty(job["id"], job["lang"], all_words, source, job["model"])
            doc = wordtimes.sync(doc, ytpages.parse_transcript_text(text, job["lang"]), job["lang"])
            panel = wordtimes.panel_hash(text)
            doc["panel_sha256"] = panel
            wordtimes.hold(job["id"], doc)
            word_info = {"held": True, "count": len(doc.get("atoms") or []), "source": source,
                         "panel_sha256": panel}
        except Exception:  # noqa: BLE001 - words must never discard a successful transcript
            traceback.print_exc()
            notes.append("Word timestamps could not be kept for this transcription.")
    if isinstance(msg.get("word_warning"), str) and msg.get("word_warning"):
        notes.append(msg["word_warning"])
    import asrcorrection
    review_evidence = asrcorrection.evidence(segs, text, job["lang"])
    import asrdictionary
    resolver = job.get('dictionary_resolver') or asrdictionary.Resolver(job["lang"])
    with LOCK:
        if job["cancelled"]:
            return
        job["state"] = CHECKING
    _unhold(job)                         # worker is dead; dictionary work holds no model
    if job.get('first_pass_evidence') is not None:
        first = job['first_pass_evidence']
        if first['source_sha256'] != review_evidence['source_sha256']:
            _end(job, FAILED, 'source-changed', 'The source transcript changed during the Whisper second pass.')
            return
        before = asrcorrection.index(first)
        for wid, word in asrcorrection.index(review_evidence).items():
            original = before.get(wid, {})
            if word['text'] != original.get('text'):
                _end(job, FAILED, 'source-changed', 'The source transcript changed during the Whisper second pass.')
                return
            for key in ('dictionary', 'dictionary_state', 'dictionary_miss'):
                if key in original:
                    word[key] = original[key]
        review_evidence['dictionary'] = first.get('dictionary', {})
        _second_pass_incomplete(job)
        review_evidence['second_pass'] = dict(job['second_pass'])
        if job['second_pass']['failed']:
            notes.append('Whisper second pass: %d of %d suspect words could not be safely processed. Their original words and earlier candidates are intact.' % (job['second_pass']['failed'], job['second_pass']['total']))
        failures = {f['word_id']: f['reason'] for f in job['second_pass']['failures']}
        for wid, word in asrcorrection.index(review_evidence).items():
            if wid in failures:
                word['second_pass'] = {**word.get('second_pass', {}), 'state': 'failed', 'reason': failures[wid]}
    elif not resolver.enrich(review_evidence, lambda: job["cancelled"]):
        return
    with LOCK:
        if job["cancelled"]:
            return
        if not _review_source_current(job):
            _end(job, FAILED, 'film-changed', 'The film changed during transcription. Name it again to transcribe the current file.')
            return
        job["review_evidence"] = review_evidence
        raw = _segments(dict(job, marks=[]), msg)
        for segment in raw:
            for word in segment.get('asr_words', []):
                word['word_id'] = 's%dw%d' % (segment['source_segment_index'], word['source_word_index'])
        job['whisper_source'] = {'segments':raw, 'word_map':{
            's%dw%d' % (si, wi): 's%dw%d' % (seg['source_segment_index'], w['source_word_index'])
            for si, seg in enumerate(segs) for wi, w in enumerate(seg.get('asr_words', []))}}
        job['first_suspect_word_ids'] = [w['word_id'] for w in asrcorrection.index(review_evidence).values() if asrcorrection.suspect(w)]
        if review_evidence.get('second_pass', {}).get('total'):
            job['last_method'], job['last_word_ids'] = 'whisper-second', job['first_suspect_word_ids']
        job.pop('first_pass_evidence', None)
        job.pop('second_pass_ids', None)
        job.pop('second_pass_completed', None)
        job.pop('second_pass_map', None)
        job["dictionary_resolver"] = resolver
        job["review_choice"] = None
        job["correction"] = {"state": "not-requested", "complete": False}
        job["text"], job["notes"], job["facts"], job["warning"], job["words"] = \
            text, list(job['notes']) + notes, facts, warning, word_info
        job["done"], job["segments"] = job["total"] or job["done"], None
    with LOCK:
        if job['cancelled']:
            return
        if not _review_source_current(job):
            _end(job, FAILED, 'film-changed', 'The film changed during transcription. Transcribe the current file again.')
            return
        job["state"], job["finished"] = DONE, _now()
        _unhold(job)                     # in the breath that says it is done
        _save_pending(job)


# ------------------------------------------------------------------ the server
def activity_entries(entry, keep, now=None):
    """The jobs as the activity list has them (lib/activity.py entry()), so
    that every page's Working pill, and the stop button's question, know a
    transcription is going on.  Kind `narration`: what estimating by the
    sound is already; the id has no token in it (every page reads this)."""
    now = _now() if now is None else now
    out = []
    with LOCK:
        # every page asks this every few seconds: a capture that stopped
        # arriving is noticed here, and leaves the list, without anybody
        # having to start another job to find out
        _expire()
        for job in list(JOBS.values()):
            over = job["state"] in (DONE, FAILED, REVIEW_CHOICE)
            if over and now - (job["finished"] or now) > keep:
                continue
            what = "Transcribing a YouTube video" if job["kind"] == "youtube" \
                else "Transcribing a film on this machine"
            out.append(entry(
                "stt:%s@%.3f" % (job["kind"], job["created"]), "narration", what,
                job["created"], stage=None if over else _say(job), page=PAGE,
                finished=job["finished"] if over else None,
                ok=job["state"] in (DONE, REVIEW_CHOICE)))
    return out


def startup():
    """At every start of the server, on a thread of its own: the temporary
    recordings and half-written files of a server that was killed, and the
    held waveforms nobody adopted, let go.  Neither folder is made here."""
    try:
        gs = _getstt()
        sweep = getattr(gs, "sweep", None)
        if callable(sweep):
            sweep()
    except Refusal:
        pass
    except Exception:                                        # noqa: BLE001
        traceback.print_exc()
    try:
        import wavefile
        wavefile.sweep()
    except Exception:                                        # noqa: BLE001
        traceback.print_exc()
    try:
        import wordtimes
        wordtimes.sweep()
    except Exception:                                        # noqa: BLE001
        traceback.print_exc()
