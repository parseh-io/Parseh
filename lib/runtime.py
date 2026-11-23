#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""What Parseh needs, where it finds it, and how it installs it.

    python3 lib/runtime.py status            what this machine has, in words
    python3 lib/runtime.py status --json     the same, as one JSON object
    python3 lib/runtime.py install           the environment, its packages, the guide, the models, the readers
    python3 lib/runtime.py install --json    ... reporting as it goes in JSON lines, for a window to show
    python3 lib/runtime.py python            the Python the launchers run, as a path

    install flags:  --conda       make the environment with this machine's conda, not micromamba
                    --recreate    throw the checkout's own environment away and make it again
                    --no-readers  leave the readers alone (./install.sh builds them itself)
                    --dry-run     say what would happen, and do none of it

ONE LIST OF WHAT THE TOOLBOX NEEDS.  Serving needs only the standard library;
rebuilding a book, dividing Japanese and Chinese into words, opening an Anki
export and the rest need the packages of environment.yml, which live in one
environment called ilya-frank.  That list used to be written out four times --
environment.yml, install.sh, the Windows wizard, lib/segmenter.py -- and the
copies drifted: the wizard never heard of the word analyzers.  PACKAGES and
ENV_TOOLS below are what the installers, the wizard and the launchers read,
and tests/test_runtime.py holds them to environment.yml.  A package added to
that file reaches every machine the next time it is installed or started: an
environment that lacks it gets it (complete_env), whatever made it.

WHERE THE ENVIRONMENT IS.  In order: $PARSEH_PYTHON when it is set; the
checkout's own .runtime/env, which ./install.sh, install.bat and the Windows
wizard make with micromamba when asked -- one program downloaded into
.runtime/, nothing installed anywhere else, nothing to undo but the folder;
then an environment called ilya-frank wherever a conda, a mamba or a
micromamba keeps its environments.  lib/env.sh searches the same places in sh
for serve.sh, build.sh and install.sh, and serve.bat in cmd.

READY FOR A WINDOW.  `install --json` writes one JSON object a line --
{"event": "step", "id", "title", "state", "detail"}, {"event": "log", "line"},
{"event": "done", "ok", "python", "environment"} -- so an installer with a
progress bar runs exactly what the terminal runs, and shows it
(docs/installer.md).

Standard library only: this runs before the environment exists.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(LIB, ".."))
if LIB not in sys.path:
    sys.path.insert(0, LIB)

ENVNAME = "ilya-frank"
WIN = os.name == "nt"
ENV_FILE = os.path.join(ROOT, "environment.yml")
RUNTIME = os.path.join(ROOT, ".runtime")
LOCAL_ENV = os.path.join(RUNTIME, "env")
MAMBA_ROOT = os.path.join(RUNTIME, "mamba")
MICROMAMBA = os.path.join(RUNTIME, "bin", "micromamba.exe" if WIN else "micromamba")
MICROMAMBA_URL = ("https://github.com/mamba-org/micromamba-releases/releases/"
                  "latest/download/micromamba-%s")

# (the module to import, the name environment.yml gives it, what it is for)
PACKAGES = (
    ("pymupdf", "PyMuPDF", "re-extracting a book's text from its scans"),
    ("rapidfuzz", "rapidfuzz", "aligning a narration, and saving an edited timing"),
    ("fontTools", "fonttools", "making the web fonts"),
    ("brotli", "brotli", "compressing them (woff2)"),
    ("sudachipy", "sudachipy", "dividing Japanese into words"),
    ("sudachidict_core", "SudachiDict-core", "the dictionary SudachiPy reads"),
    ("spacy_pkuseg", "spacy-pkuseg", "dividing Chinese into words, and naming their parts of speech"),
    ("pypinyin", "pypinyin", "reading Chinese words in pinyin"),
    ("zstandard", "zstandard", "opening a modern Anki export"),
    ("numpy", "numpy", "estimating timings by the sound of a recording"),
    ("PIL", "Pillow", "printing a WebP or GIF picture in a studio PDF, and a HEIC turned into a JPEG"),
    ("pillow_heif", "pillow-heif", "reading a phone's HEIC picture"),
)
# (the program, the name environment.yml gives it, what it is for): programs
# the environment carries, so that no machine has to find them for itself
ENV_TOOLS = (
    ("openssl", "openssl", "making the https certificate"),
    ("deno", "deno", "the browser tests, and checking a new language's patterns"),
)
# (the program, what it is for, where it comes from): never the environment's
SYSTEM_TOOLS = (
    ("lualatex", "building a book's PDF", "TeX Live; ./install.sh --pdf adds the packages it lacks"),
    ("xelatex", "building a studio document's PDF, and the LaTeX drawings of a theme that asks "
                "for it", "TeX Live or MiKTeX"),
    ("pdflatex", "the LaTeX drawings of a theme that asks for it", "TeX Live or MiKTeX"),
    ("ffmpeg", "snapping a narration's timings to its silences, drawing the picture of the sound "
               "that \"estimate the rest by the sound\" reads, and cutting a card's recording out of "
               "a narration or a film", "the system's package manager"),
    ("pdftotext", "re-extracting a book's source from a PDF", "poppler-utils"),
)


# ------------------------------------------------------------------ the list
def env_spec(path=ENV_FILE):
    """environment.yml's dependencies -> {"conda": [(name, spec)], "pip": [(name, spec)]}.

    Read by hand, because this runs before any package is installed and a
    YAML reader is one: the file keeps to the shape conda writes -- a list
    under `dependencies:`, and a `pip:` list inside it -- and
    tests/test_runtime.py holds it to that shape."""
    out = {"conda": [], "pip": []}
    in_deps, pip_at = False, None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            item = line.strip()
            if indent == 0:
                in_deps, pip_at = item == "dependencies:", None
                continue
            if not in_deps or not item.startswith("- "):
                continue
            item = item[2:].strip()
            if pip_at is not None and indent <= pip_at:
                pip_at = None
            if item == "pip:":
                pip_at = indent
                continue
            name = re.split(r"[<>=!~\s\[]", item, maxsplit=1)[0]
            out["pip" if pip_at is not None else "conda"].append((name, item))
    return out


# ------------------------------------------------------------------ finding it
def conda_roots():
    """Every directory a conda, a mamba or a micromamba may keep an `envs`
    directory in, best first."""
    home = os.path.expanduser("~")
    roots = [os.environ.get("MAMBA_ROOT_PREFIX", "")]
    if os.environ.get("CONDA_EXE"):
        roots.append(os.path.dirname(os.path.dirname(os.environ["CONDA_EXE"])))
    names = ("miniconda3", "anaconda3", "miniforge3", "mambaforge", "micromamba")
    bases = [home]
    if WIN:
        local = os.environ.get("LOCALAPPDATA", "")
        bases += [local, os.path.join(local, "Programs") if local else "",
                  os.environ.get("ProgramData", "")]
    else:
        bases += ["/opt"]
        roots += ["/opt/homebrew/Caskroom/miniconda/base", "/opt/homebrew/Caskroom/miniforge/base",
                  "/usr/local/Caskroom/miniconda/base", "/usr/local/Caskroom/miniforge/base",
                  os.path.join(home, ".local", "share", "mamba")]
    for b in bases:
        if b:
            roots += [os.path.join(b, n) for n in names]
    roots.append(os.path.join(home, ".conda"))           # conda's own per-user envs
    return [r for r in roots if r]


def python_in(prefix):
    return os.path.join(prefix, "python.exe") if WIN else os.path.join(prefix, "bin", "python3")


def env_path_dirs(prefix):
    """The directories an environment keeps its programs in, to go first on PATH."""
    if WIN:
        return [prefix, os.path.join(prefix, "Library", "bin"),
                os.path.join(prefix, "Scripts"), os.path.join(prefix, "bin")]
    return [os.path.join(prefix, "bin")]


def find_env():
    """(prefix, python) of the environment, or (None, None) where there is none."""
    forced = os.environ.get("PARSEH_PYTHON")
    if forced and os.path.isfile(forced):
        up = os.path.dirname(forced)
        return (up if WIN else os.path.dirname(up)), forced
    for prefix in [LOCAL_ENV] + [os.path.join(r, "envs", ENVNAME) for r in conda_roots()]:
        if os.path.isfile(python_in(prefix)):
            return prefix, python_in(prefix)
    return None, None


def environ_for(prefix, base=None):
    """os.environ with the environment's programs first on the PATH, which is
    what activating it does as far as anything here is concerned."""
    env = dict(base if base is not None else os.environ)
    if prefix:
        env["PATH"] = os.pathsep.join(env_path_dirs(prefix) + [env.get("PATH", "")])
    return env


def tool(program, prefix=None, system=True):
    """Where `program` is: in the environment first, then (with `system`)
    on the PATH.  None where it is nowhere."""
    for d in (env_path_dirs(prefix) if prefix else []):
        for name in ((program + ".exe", program) if WIN else (program,)):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
    return shutil.which(program) if system else None


_PROBE = ("import importlib.util, json, sys\n"
          "print(json.dumps({m: importlib.util.find_spec(m) is not None for m in sys.argv[1:]}))")


def modules(python):
    """{module: importable} for PACKAGES, asked of `python` -- which is usually
    not the Python running this."""
    names = [m for m, _n, _w in PACKAGES]
    try:
        r = subprocess.run([python, "-c", _PROBE] + names, capture_output=True,
                           text=True, timeout=120)
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {m: False for m in names}


def status():
    """What this machine has, as a dict: the environment, its packages, the
    programs, the models the word analyzers download."""
    import segmenter
    prefix, python = find_env()
    py = python or sys.executable
    have = modules(py)
    out = {
        "root": ROOT,
        "environment": prefix,
        "local": bool(prefix) and os.path.realpath(prefix) == os.path.realpath(LOCAL_ENV),
        "python": py,
        "packages": [{"module": m, "name": n, "what": w, "have": bool(have.get(m))}
                     for m, n, w in PACKAGES],
        "tools": ([{"program": c, "what": w, "path": tool(c, prefix), "from": "environment"}
                   for c, _n, w in ENV_TOOLS]
                  + [{"program": c, "what": w, "path": tool(c, prefix), "from": f}
                     for c, w, f in SYSTEM_TOOLS]),
        "models": [dict(m, language="zh") for m in segmenter.models("zh")],
    }
    out["missing"] = [p["name"] for p in out["packages"] if not p["have"]]
    return out


# ------------------------------------------------------------------ saying it
class Report:
    """What an install says as it goes: lines of text for a terminal, or one
    JSON object a line for a window (docs/installer.md).  A step that did not
    finish but that Parseh works without -- the guide's compile -- ends as a
    "warning": said, and not a failure of the install."""

    MARK = {"running": "..", "done": "ok", "skipped": "--", "warning": "warn", "failed": "MISS"}

    def __init__(self, as_json=False, out=None):
        self.json = as_json
        self.out = out or sys.stdout

    def _emit(self, obj, text):
        if self.json:
            self.out.write(json.dumps(obj, ensure_ascii=False) + "\n")
        elif text is not None:
            self.out.write(text + "\n")
        self.out.flush()

    def step(self, sid, title, state, detail=""):
        self._emit({"event": "step", "id": sid, "title": title, "state": state, "detail": detail},
                   "  %-5s %s%s" % (self.MARK[state], title, (" -- " + detail) if detail else ""))

    def log(self, line):
        self._emit({"event": "log", "line": line}, "        " + line)

    def done(self, ok, **extra):
        self._emit(dict({"event": "done", "ok": bool(ok)}, **extra), None)


def run(cmd, report, env=None, cwd=ROOT):
    """A command, its output passed on line by line -> its exit status."""
    try:
        p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", bufsize=1)
    except OSError as e:
        report.log("could not run %s: %s" % (cmd[0], e))
        return 127
    for line in p.stdout:
        line = line.rstrip()
        if line.strip():
            report.log(line)
    return p.wait()


# ------------------------------------------------------------------ installing it
def micromamba_platform():
    """micromamba's name for this machine: linux-64, osx-arm64, win-64, ..."""
    machine = platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if WIN:
        return "win-64"
    if sys.platform == "darwin":
        return "osx-arm64" if arm else "osx-64"
    if machine == "ppc64le":
        return "linux-ppc64le"
    return "linux-aarch64" if arm else "linux-64"


def get_micromamba(report):
    """The micromamba this checkout uses, downloaded into .runtime/bin the
    first time: one program of some ten megabytes, which is all it takes to
    make an environment on a machine with no conda."""
    if os.path.isfile(MICROMAMBA):
        return MICROMAMBA
    url = MICROMAMBA_URL % micromamba_platform()
    report.log("downloading micromamba from %s" % url)
    os.makedirs(os.path.dirname(MICROMAMBA), exist_ok=True)
    part = MICROMAMBA + ".part"
    with urllib.request.urlopen(url, timeout=120) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(part, MICROMAMBA)
    os.chmod(MICROMAMBA, 0o755)
    return MICROMAMBA


def _conda():
    return shutil.which("mamba") or shutil.which("conda")


def make_env(report, use_conda=False):
    """Make the environment -> (prefix, python), or (None, None)."""
    title = "the environment"
    if use_conda:
        conda = _conda()
        if not conda:
            report.step("env", title, "failed", "--conda, and there is no conda or mamba on the PATH")
            return None, None
        report.step("env", title, "running", "%s env create -n %s" % (os.path.basename(conda), ENVNAME))
        rc = run([conda, "env", "create", "-n", ENVNAME, "-f", ENV_FILE], report)
    else:
        try:
            mm = get_micromamba(report)
        except Exception as e:                  # the network, most likely
            report.step("env", title, "failed", "could not download micromamba: %s" % e)
            return None, None
        report.step("env", title, "running", "with micromamba, into .runtime/env -- a few "
                    "hundred megabytes, once")
        rc = run([mm, "create", "-y", "-r", MAMBA_ROOT, "-p", LOCAL_ENV, "-f", ENV_FILE], report,
                 env=dict(os.environ, MAMBA_ROOT_PREFIX=MAMBA_ROOT))
    prefix, python = find_env()
    if rc != 0 or not prefix:
        report.step("env", title, "failed", "the lines above say why")
        return None, None
    report.step("env", title, "done", prefix)
    return prefix, python


def complete_env(prefix, python, report):
    """Add to an environment what environment.yml lists and it lacks -> True
    when nothing is missing afterwards.

    This is how a package listed after a machine was set up reaches it: the
    installers and the Windows wizard run it every time, whatever made the
    environment and whenever."""
    title = "the packages"
    spec = env_spec()
    have = modules(python)
    module_of = {n.lower(): m for m, n, _w in PACKAGES}
    pip_missing = [s for name, s in spec["pip"]
                   if name.lower() in module_of and not have.get(module_of[name.lower()])]
    tools = {n for _p, n, _w in ENV_TOOLS}
    conda_missing = [s for name, s in spec["conda"]
                     if name in tools and not tool(name, prefix, system=False)]
    if not pip_missing and not conda_missing:
        report.step("packages", title, "done", "all %d, and the programs it carries" % len(PACKAGES))
        return True
    report.step("packages", title, "running", "adding %s" % ", ".join(
        re.split(r"[<>=!~\s\[]", s, maxsplit=1)[0] for s in conda_missing + pip_missing))
    ok = True
    if conda_missing:
        conda = _conda()
        if conda and os.path.realpath(prefix) != os.path.realpath(LOCAL_ENV):
            cmd = [conda, "install", "-y", "-p", prefix, "-c", "conda-forge"] + conda_missing
            env = None
        else:
            try:
                mm = get_micromamba(report)
            except Exception as e:
                report.log("could not download micromamba: %s" % e)
                mm = None
            cmd = ([mm, "install", "-y", "-r", MAMBA_ROOT, "-p", prefix, "-c", "conda-forge"]
                   + conda_missing) if mm else None
            env = dict(os.environ, MAMBA_ROOT_PREFIX=MAMBA_ROOT)
        ok = bool(cmd) and run(cmd, report, env=env) == 0 and ok
    if pip_missing:
        ok = run([python, "-m", "pip", "install"] + pip_missing, report,
                 env=environ_for(prefix)) == 0 and ok
    left = [n for m, n, _w in PACKAGES if not modules(python).get(m)]
    left += [n for _p, n, _w in ENV_TOOLS if not tool(n, prefix, system=False)]
    if left:
        report.step("packages", title, "failed", "still missing: %s" % ", ".join(left))
        return False
    report.step("packages", title, "done", "all present")
    return ok or not left


def build_guide(python, prefix, report):
    """The HTML guide: html-guide/markdown/ compiled into html-guide/site/,
    which the hub's guide button opens.  Standard library only, so any Python
    compiles it -- the environment's when there is one.  A compile that fails
    is a warning, never a failed install: the guide's own front page says what
    went wrong and compiles it again from a button."""
    title = "the guide"
    report.step("guide", title, "running", "html-guide/markdown/ -> html-guide/site/")
    build = os.path.join(ROOT, "html-guide", "build.py")
    if not os.path.isfile(build):
        report.step("guide", title, "skipped", "no html-guide/ in this checkout")
        return True
    rc = run([python or sys.executable, build], report, env=environ_for(prefix) if prefix else None)
    if rc == 0:
        report.step("guide", title, "done")
    else:
        report.step("guide", title, "warning",
                    "the lines above say why; the guide's front page can compile it again")
    return True


def fetch_models(python, prefix, report):
    """What the word analyzers download for themselves, fetched now rather
    than by the first request that needs it (lib/words.py fetch_models)."""
    title = "the word analyzers' models"
    report.step("models", title, "running", "pkuseg's word and part-of-speech models, some 75 MB")
    rc = run([python, os.path.join(LIB, "words.py"), "--fetch", "ja", "zh"], report,
             env=environ_for(prefix))
    report.step("models", title, "done" if rc == 0 else "failed")
    return rc == 0


def build_readers(python, prefix, report):
    """Every book's reader and the library page: ./build.sh --html, or where
    there is no sh the launcher's own copy of it."""
    title = "the readers"
    report.step("readers", title, "running")
    if WIN or not shutil.which("sh"):
        rc = run([python, os.path.join(LIB, "launcher.py"), "readers"], report,
                 env=environ_for(prefix))
    else:
        rc = run(["sh", os.path.join(ROOT, "build.sh"), "--html"], report, env=environ_for(prefix))
    report.step("readers", title, "done" if rc == 0 else "failed")
    return rc == 0


STEPS = (("env", "the environment"), ("packages", "the packages"), ("guide", "the guide"),
         ("models", "the word analyzers' models"), ("readers", "the readers"))


def install(report, use_conda=False, recreate=False, readers=True, dry_run=False):
    """Everything, in order, each step reported -> True when all of it is in place."""
    if dry_run:
        for sid, title in STEPS:
            if sid != "readers" or readers:
                report.step(sid, title, "skipped", "dry run")
        report.done(True, python=find_env()[1] or sys.executable, dry_run=True)
        return True
    if recreate and os.path.isdir(LOCAL_ENV):
        report.log("removing .runtime/env, to make it again")
        shutil.rmtree(LOCAL_ENV)
    prefix, python = find_env()
    if prefix:
        report.step("env", "the environment", "done", prefix)
    else:
        prefix, python = make_env(report, use_conda)
        if not prefix:
            report.done(False)
            return False
    ok = complete_env(prefix, python, report)
    # the guide before the models: it needs no network, and a download that
    # hangs should not keep the manual from being there
    build_guide(python, prefix, report)
    ok = fetch_models(python, prefix, report) and ok
    if readers:
        ok = build_readers(python, prefix, report) and ok
    report.done(ok, python=python, environment=prefix)
    return ok


# ------------------------------------------------------------------ main
def _say_status(st):
    print("the environment:  %s" % (st["environment"] or "none yet -- ./install.sh (install.bat on Windows) makes it"))
    print("python:           %s" % st["python"])
    for p in st["packages"]:
        print("  %-5s %-18s %s" % ("ok" if p["have"] else "MISS", p["name"], p["what"]))
    for t in st["tools"]:
        print("  %-5s %-18s %s%s" % ("ok" if t["path"] else "--", t["program"], t["what"],
                                    "" if t["path"] else "  (%s)" % t["from"]))
    for m in st["models"]:
        print("  %-5s %-18s %s for %s" % ("ok" if m["have"] else "--", m["name"], m["what"], m["language"]))


def main(argv):
    verb = argv[0] if argv else "status"
    flags = set(argv[1:])
    if verb == "python":
        print(find_env()[1] or sys.executable)
        return 0
    if verb == "status":
        st = status()
        if "--json" in flags:
            print(json.dumps(st, ensure_ascii=False, indent=1))
        else:
            _say_status(st)
        return 0
    if verb == "install":
        report = Report("--json" in flags)
        ok = install(report, use_conda="--conda" in flags, recreate="--recreate" in flags,
                     readers="--no-readers" not in flags, dry_run="--dry-run" in flags)
        return 0 if ok else 1
    print(__doc__.strip().split("\n\n")[0])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
