#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The optional analyzers: getting them, knowing what is here, and asking them.

    python3 lib/getanalysis.py                  what is here
    python3 lib/getanalysis.py get farahidi udpipe:de udpipe:fa starlang
    python3 lib/getanalysis.py remove udpipe:de | farahidi | starlang | all

Nothing here is imported, fetched or started until somebody asks on Settings ->
Linguistic analysis (lib/analysispage.py); a person who never does has the
Parseh they had.  INSTALLING CHANGES NO RESULT: what is installed is used only
where lib/analysisconfig.py says so, and it says "off" until somebody changes it.

WHERE IT ALL LIVES.  `analysis/`, kept by every update and left out of backups,
books and releases:

    runtime/     an environment of its own, made with this Python's `venv`
    models/      UDPipe's models, each moved into place only after its hash is right
    tmp/         pip's scratch, gone when the job ends

The packages are pinned by hash in lib/analysis-*-requirements.txt and the models
in lib/analysispins.py; nothing a client sends becomes a path or an address: a
request names an item of `ITEMS` or it is refused.

THE ANALYZERS RUN IN THEIR OWN PROGRAM (lib/analyzerworker.py).  status() looks at
files and imports nothing.  A request starts the program if it is not running,
and the program goes away after IDLE_SECONDS, taking its memory with it.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import venv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysispins as pins    # noqa: E402
import analyzer                # noqa: E402
import download                # noqa: E402
import project                 # noqa: E402
import version                 # noqa: E402

LIB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(LIB)
FOLDER = os.path.join(ROOT, "analysis")
WORKER = os.path.join(LIB, "analyzerworker.py")
IDLE_SECONDS = 600
LOAD_SECONDS = 180          # the first request of a language loads its model
MAX_LINE = 1 << 28

STARLANG_ORDER = ("NlpToolkit-Util-Cy", "NlpToolkit-DataStructure-Cy", "NlpToolkit-Math-Cy",
                  "NlpToolkit-Dictionary-Cy", "NlpToolkit-Corpus-Cy", "NlpToolkit-MorphologicalAnalysis-Cy")


class AnalysisError(ValueError):
    """Something a person can be told."""


def runtime_dir():
    return os.path.join(FOLDER, "runtime")


def models_dir():
    return os.path.join(FOLDER, "models")


def tmp_dir():
    return os.path.join(FOLDER, "tmp")


def python():
    return os.path.join(runtime_dir(), "Scripts", "python.exe") if os.name == "nt" \
        else os.path.join(runtime_dir(), "bin", "python")


def _site_packages():
    if os.name == "nt":
        return [os.path.join(runtime_dir(), "Lib", "site-packages")]
    lib = os.path.join(runtime_dir(), "lib")
    try:
        return [os.path.join(lib, d, "site-packages") for d in os.listdir(lib) if d.startswith("python")]
    except OSError:
        return []


def package_here(which):
    """Did pip finish installing this program?  It writes the dist-info last."""
    names = pins.PACKAGES[which]
    for site in _site_packages():
        if all(os.path.isdir(os.path.join(site, n)) for n in names):
            return True
    return False


def model_path(code):
    return os.path.join(models_dir(), pins.UDPIPE_MODELS[code]["file"])


def model_here(code):
    """The right file at the right size.  Its hash was checked before it was
    moved here; a file of another size was not put here by this module."""
    pin = pins.UDPIPE_MODELS.get(code)
    if not pin:
        return False
    try:
        return os.path.getsize(model_path(code)) == pin["bytes"]
    except OSError:
        return False


ITEMS = tuple(["farahidi", "starlang"] + ["udpipe:%s" % c for c in pins.UDPIPE_MODELS])


def check_items(items):
    if not isinstance(items, (list, tuple)) or not items:
        raise AnalysisError("Say what to get.")
    out = []
    for x in items:
        if x not in ITEMS:
            raise AnalysisError("Parseh has no such analyzer to get: %s" % str(x)[:40])
        if x not in out:
            out.append(x)
    return out


def compiler():
    """A C compiler Starlang's sources can be built with, or "" where none is
    seen.  Windows keeps its compiler out of PATH, so there it is pip who finds out."""
    if os.name == "nt":
        return "msvc?"
    for c in ("cc", "gcc", "clang"):
        got = shutil.which(c)
        if got:
            return got
    return ""


def cannot_run():
    """Why this Python cannot make an environment, in a sentence, or ""."""
    if importlib.util.find_spec("ensurepip") is None:
        return ("This Python (%s) has no ensurepip, which making the analyzers' environment needs. "
                "On Debian and Ubuntu, that is the python3-venv package." % sys.executable)
    return ""


# ---------------------------------------------------------------- the backends

class _Worker:
    """lib/analyzerworker.py, one for all three backends."""
    def __init__(self):
        self.lock = threading.Lock()
        self.process = None
        self.last = 0
        self.timer = None
        self.loaded = {}        # backend -> the languages its program holds in memory, as it last said

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def _start(self):
        self.process = subprocess.Popen(
            [python(), "-I", "-u", "-W", "ignore", WORKER, models_dir()],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt")

    def ask(self, body, seconds=LOAD_SECONDS):
        with self.lock:
            if not self.alive():
                try:
                    self._start()
                except OSError as e:
                    raise analyzer.BackendError("the analyzers' program could not start: %s" % e)
            answer = {}
            done = threading.Event()
            proc = self.process

            def read():
                try:
                    line = proc.stdout.readline(MAX_LINE)
                    answer.update(json.loads(line) if line else {"ok": False, "error": "it stopped"})
                except (OSError, ValueError) as e:
                    answer.update(ok=False, error=str(e))
                done.set()

            try:
                proc.stdin.write((json.dumps(body, ensure_ascii=True) + "\n").encode())
                proc.stdin.flush()
            except (OSError, ValueError) as e:
                self._stop()
                raise analyzer.BackendError("the analyzers' program stopped: %s" % e)
            threading.Thread(target=read, daemon=True, name="analysis-read").start()
            if not done.wait(seconds):
                self._stop()
                raise analyzer.BackendError("no answer in %d seconds" % seconds)
            if answer.get("error") == "it stopped":
                self._stop()
            self.last = time.monotonic()
            if answer.get("loaded"):
                self.loaded = answer["loaded"]
            self._arm()
        if not answer.get("ok"):
            raise analyzer.BackendError(answer.get("error") or "no answer")
        return answer

    def _arm(self):
        if self.timer is not None:
            self.timer.cancel()
        self.timer = threading.Timer(IDLE_SECONDS, self._idle)
        self.timer.daemon = True
        self.timer.start()

    def _idle(self):
        with self.lock:
            if time.monotonic() - self.last >= IDLE_SECONDS - 1:
                self._stop()

    def _stop(self):
        p, self.process = self.process, None
        self.loaded = {}
        if p is not None:
            try:
                p.stdin.close()
            except OSError:
                pass
            try:
                p.terminate()
                p.wait(5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    p.kill()
                except OSError:
                    pass

    def stop(self):
        with self.lock:
            self._stop()
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None


WORKER_PROGRAM = _Worker()


def stop_worker():
    """Asked at shutdown, and before anything in analysis/ is replaced."""
    WORKER_PROGRAM.stop()


class _Remote:
    """A backend, as the server sees it: its status from files, its answers
    from the program, and each answer held to the text again by lib/analyzer.py."""

    def __init__(self, name, version, codes, resource):
        self.name, self.version, self.codes, self._resource = name, version, codes, resource

    def languages(self):
        return tuple(self.codes)

    def status(self, code):
        package, resource = package_here(self.name), self._resource(code)
        ready = package and resource
        why = ""
        if not package:
            why = "%s is not installed: Settings → Linguistic analysis" % self.name
        elif not resource:
            why = "the %s model for %s is not here: Settings → Linguistic analysis" % (self.name, code)
        return {"package": package, "resource": resource, "usable": ready,
                "loaded": WORKER_PROGRAM.alive() and code in WORKER_PROGRAM.loaded.get(self.name, ()),
                "version": self.version,
                "resource_id": pins.UDPIPE_MODELS[code]["file"] if self.name == "udpipe" else "bundled",
                "why": why}

    def analyze(self, code, text, syntax=False, context=""):
        answer = WORKER_PROGRAM.ask({"op": "analyze", "backend": self.name, "code": code, "text": text,
                                     "syntax": bool(syntax), "context": context})
        try:
            return analyzer.from_plain(answer["result"])
        except (KeyError, TypeError, ValueError) as e:
            raise analyzer.BackendError("an answer that could not be read: %s" % e)


def backends():
    """What lib/analyzer.py registers the first time it is asked anything."""
    import analyzer_native
    return (_Remote("udpipe", pins.UDPIPE_VERSION, pins.UDPIPE_MODELS, model_here),
            _Remote("farahidi", pins.FARAHIDI_VERSION, ("ar",), lambda code: True),
            _Remote("starlang", pins.STARLANG_VERSION, ("tr",), lambda code: True),
            analyzer_native.Backend())


# ---------------------------------------------------------------- what is here

def status():
    """Everything the page draws, from files alone.  It loads nothing."""
    models = []
    for code, pin in pins.UDPIPE_MODELS.items():
        models.append({"code": code, "treebank": pin["treebank"], "bytes": pin["bytes"],
                       "licence": pin["licence"], "have": model_here(code), "item": "udpipe:%s" % code,
                       "loaded": code in WORKER_PROGRAM.loaded.get("udpipe", ())})
    return {"folder": FOLDER, "python": python(), "serving_python": sys.executable,
            "runtime": os.path.isfile(python()), "worker_running": WORKER_PROGRAM.alive(),
            "programs": {
                "udpipe": {"have": package_here("udpipe"), "version": pins.UDPIPE_VERSION,
                           "licence": "MPL-2.0", "mb": pins.PROGRAM_MB["udpipe"]},
                "farahidi": {"have": package_here("farahidi"), "version": pins.FARAHIDI_VERSION,
                             "licence": "GPL-3.0-or-later", "mb": pins.PROGRAM_MB["farahidi"]},
                "starlang": {"have": package_here("starlang"), "version": pins.STARLANG_VERSION,
                             "licence": "GPL-3.0", "mb": pins.PROGRAM_MB["starlang"],
                             "compiler": compiler()}},
            "models": models, "job": job(), "cannot": cannot_run()}


def installed():
    return any(package_here(w) for w in pins.PACKAGES)


# ---------------------------------------------------------------- getting it

_JOB = {"state": "idle"}
_JOB_LOCK = threading.Lock()
_cancel = threading.Event()
_thread = None
_pip = None


def job():
    with _JOB_LOCK:
        return dict(_JOB)


def running():
    return job().get("state") == "running"


def _note(**kw):
    with _JOB_LOCK:
        _JOB.update(kw)


def start(items):
    """Begin fetching in the background -> (answer, status)."""
    global _thread
    items = check_items(items)
    why = cannot_run()
    if why:
        raise AnalysisError(why)
    if "starlang" in items and not compiler():
        raise AnalysisError("Starlang is compiled when it is installed, and no C compiler was found "
                            "on this computer (cc, gcc or clang).")
    with _JOB_LOCK:
        if _JOB.get("state") == "running":
            return {"ok": False, "error": "Something is being fetched already.", "code": "busy"}, 409
        _JOB.clear()
        _JOB.update(state="running", items=items, done=[], now="", error="", started=time.time())
    _cancel.clear()
    _thread = threading.Thread(target=_work, args=(items,), daemon=True, name="analysis-get")
    _thread.start()
    return {"ok": True, "job": job()}, 202


def stop():
    global _pip
    if not running():
        return False
    _cancel.set()
    p = _pip
    if p is not None:
        try:
            p.terminate()
        except OSError:
            pass
    return True


def stop_all(wait=2.0):
    stop()
    if _thread is not None:
        _thread.join(wait)
    stop_worker()


def _work(items):
    try:
        build(items, say=lambda s: _note(now=s))
        _note(state="done", now="")
    except download.Cancelled:
        _note(state="stopped", now="")
    except (AnalysisError, OSError, subprocess.SubprocessError, ValueError) as e:
        _note(state="failed", now="", error=str(e))
    finally:
        shutil.rmtree(tmp_dir(), ignore_errors=True)
        analyzer.clear_cache()


def build(items, say=print):
    """Get these items, the program for each first.  Each is whole or absent:
    what was finished before a failure stays, and asking again goes on from it."""
    stop_worker()
    os.makedirs(tmp_dir(), exist_ok=True)
    if any(x.startswith("udpipe:") for x in items) and not package_here("udpipe"):
        items = ["udpipe"] + list(items)
    for item in items:
        if _cancel.is_set():
            raise download.Cancelled()
        if item == "udpipe":
            _pip_install("udpipe", say)
        elif item == "farahidi":
            if not package_here("farahidi"):
                _pip_install("farahidi", say)
        elif item == "starlang":
            if not package_here("starlang"):
                _build_starlang(say)
        else:
            _get_model(item.split(":", 1)[1], say)
        with _JOB_LOCK:
            if "done" in _JOB:
                _JOB["done"] = _JOB["done"] + [item]
    write_licence()


def _ensure_runtime(say):
    if not os.path.isfile(python()):
        say("Making the analyzers' environment")
        venv.EnvBuilder(with_pip=True).create(runtime_dir())


def _pip_env():
    return dict(os.environ, TMPDIR=tmp_dir(), TEMP=tmp_dir(), TMP=tmp_dir(), PIP_NO_INPUT="1",
                PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_CACHE_DIR="1", PYTHONNOUSERSITE="1")


def _run_pip(args, say):
    """One pip -> nothing, or AnalysisError with the line that says why."""
    global _pip
    if _cancel.is_set():
        raise download.Cancelled()
    _pip = subprocess.Popen([python(), "-m", "pip"] + args, cwd=tmp_dir(), env=_pip_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    out = _pip.communicate()[0]
    code, _pip = _pip.returncode, None
    if _cancel.is_set():
        raise download.Cancelled()
    if code:
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        useful = [ln for ln in lines if "rror" in ln] or lines[-1:]
        raise AnalysisError("pip stopped: %s" % (useful[-1][:300] if useful else "no message"))


def _requirements(name):
    return os.path.join(LIB, "analysis-%s-requirements.txt" % name)


def _pip_install(which, say):
    _ensure_runtime(say)
    say("Installing %s" % which)
    _run_pip(["install", "--require-hashes", "-r", _requirements(which)], say)


def _pinned_lines(path):
    """{name: its block of a requirements file}: pip takes one hash-pinned
    requirement at a time from a file of its own."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    out, cur = {}, None
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if not line.startswith(" "):
            cur = line.split("==")[0]
            out[cur] = []
        out[cur].append(line)
    return out


def _build_starlang(say):
    """Starlang's Cython packages ship as source, and each compiles against the
    one before it: the build tools first, then each in order, with no isolation
    so that it can see them."""
    _ensure_runtime(say)
    say("Installing what compiling Starlang takes")
    _run_pip(["install", "--require-hashes", "-r", _requirements("starlang-build")], say)
    blocks = _pinned_lines(_requirements("starlang"))
    for n, name in enumerate(STARLANG_ORDER, 1):
        say("Compiling Starlang: %d of %d" % (n, len(STARLANG_ORDER)))
        one = os.path.join(tmp_dir(), "one.txt")
        with open(one, "w", encoding="utf-8") as f:
            f.write("\n".join(blocks[name]) + "\n")
        _run_pip(["install", "--no-build-isolation", "--no-deps", "--require-hashes", "-r", one], say)


def _get_model(code, say):
    pin = pins.UDPIPE_MODELS[code]
    dest = model_path(code)
    if model_here(code):
        return
    os.makedirs(models_dir(), exist_ok=True)
    say("Fetching the %s model" % pin["treebank"])
    try:
        download.fetch(pins.MODEL_HOST % pin["bitstream"], dest, cancel=_cancel, sha256=pin["sha256"],
                       size=pin["bytes"], limit=pin["bytes"] + 1,
                       headers={"User-Agent": project.agent(version.VERSION)})
    except download.Mismatch:
        raise AnalysisError("The %s model arrived different from the one Parseh knows; nothing "
                            "was kept." % pin["treebank"])
    except OSError as e:
        raise AnalysisError("The %s model could not be fetched: %s" % (pin["treebank"], e))


def write_licence():
    """Whose work the models are, beside them."""
    if not os.path.isdir(models_dir()):
        return
    with open(os.path.join(models_dir(), "LICENSE-MODELS.txt"), "w", encoding="utf-8") as f:
        f.write("%s\nLicence: %s, %s\nSource: %s\n"
                % (pins.MODEL_CREDIT, pins.MODEL_LICENCE, pins.MODEL_LICENCE_URL, pins.MODEL_PAGE))


def remove(what):
    """Take something away -> True.  Nothing but analysis/ is ever touched."""
    if running():
        raise AnalysisError("Something is being fetched: stop it first.")
    if what != "all" and what not in ITEMS:
        raise AnalysisError("Parseh has no such analyzer to remove.")
    stop_worker()
    if what == "all":
        shutil.rmtree(FOLDER, ignore_errors=True)
    elif what.startswith("udpipe:"):
        try:
            os.unlink(model_path(what.split(":", 1)[1]))
        except FileNotFoundError:
            pass
    elif os.path.isfile(python()):
        names = ["farahidi"] if what == "farahidi" else list(STARLANG_ORDER)
        os.makedirs(tmp_dir(), exist_ok=True)
        _cancel.clear()
        try:
            _run_pip(["uninstall", "-y"] + names, print)
        finally:
            shutil.rmtree(tmp_dir(), ignore_errors=True)
    analyzer.clear_cache()
    return True


def _cli(argv):
    if not argv:
        print(json.dumps(status(), indent=1, ensure_ascii=False))
        return 0
    try:
        if argv[0] == "get":
            build(check_items(argv[1:]))
        elif argv[0] == "remove" and len(argv) == 2:
            remove(argv[1])
        else:
            print(__doc__)
            return 2
    except AnalysisError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
