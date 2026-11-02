#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server tests/speech_door.mjs drives: Parseh's real handler, its real
Settings -> Speech to text page and its real routes, on a TEMPORARY stt/ tree,
with the graphics card and the installing standing in for what a test cannot
have (a card, and 1.7 GB of a stranger's files).

    python3 tests/speech_harness.py               the computer's own browser asking
    python3 tests/speech_harness.py --as-phone    a device that has been let in over the Wi-Fi
    python3 tests/speech_harness.py --real <stt/>  a REAL stt/ folder, read-only in practice: nothing stands
                                                  in (the real look at the card, the real status), so the
                                                  page is what a person with that install would see

WHAT IS REAL: the server, the page and every route it posts to, the job table
and its runner (serve.reading_start), getstt's status read from the disk,
getstt.remove taking a folder away, and the activity list.  WHAT STANDS IN: the
look at the graphics card (getstt._run_probe answers what a command says) and
getstt.build, which walks a bar the way a download does and makes the folders
a real one leaves -- the models as sparse files of their real sizes, so the page
says "1.6 GB" and no disk is filled.  Nothing here reaches a network, and
nothing is written outside the temporary tree (config/ included: the network
store is pointed at it).

It reads one JSON command per line on stdin and answers `OK` (or `ERR ...`)
after each, so that a browser test can change the world under an open page:

    {"cmd": "state", "runtime": "absent|ready|older|newer|other_python|broken",
     "models": {"large-v3-turbo": "absent|ready|older|broken", "large-v3": "..."}}
    {"cmd": "probe", "answer": "none|found-not-ready|ready|error"}
    {"cmd": "build", "steps": 30, "pause": 0.05, "fail": null | "a sentence"}
    {"cmd": "unavailable", "why": "" | "a sentence"}
    {"cmd": "wheel", "has": true | false}  a kind of computer the program is built for, or one it is not
    {"cmd": "clear"}                      forget every job and every look at the card

Prints `READY {json}` once listening.  SIGTERM or SIGINT removes the temp tree."""
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import network                                                 # noqa: E402
import download                                                # noqa: E402
import getstt                                                  # noqa: E402
import languages                                               # noqa: E402
import latexthemes                                             # noqa: E402
import newlang                                                 # noqa: E402
import offline                                                 # noqa: E402
import analysisconfig                                          # noqa: E402
import prefs                                                   # noqa: E402
import prompts                                                 # noqa: E402
import serve                                                   # noqa: E402
import speechconfig                                            # noqa: E402

AS_PHONE = "--as-phone" in sys.argv[1:]
REAL = sys.argv[sys.argv.index("--real") + 1] if "--real" in sys.argv[1:] else ""
tmp = Path(tempfile.mkdtemp(prefix="parseh-speech-door-test-"))
network.STORE = str(tmp / "config" / "network.json")
# and every other store of config/ (tests/test_harness_stores.py asks): the owner's preferences (a page of Settings
# saves its theme through lib/prefs.py), the two memories of the phone-keeping door, the prompts he wrote, the LaTeX
# themes, the languages added on this machine (lib/newlang.py keeps a copy of the path) and the speech settings
prefs.STORE = str(tmp / "config" / "prefs.json")
analysisconfig.STORE = str(tmp / "config" / "analysis.json")
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
prompts.STORE = str(tmp / "config" / "prompts.json")
latexthemes.STORE = str(tmp / "config" / "latex.json")
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")
speechconfig.CONFIG = tmp / "config" / "speech.json"
STT = Path(REAL) if REAL else tmp / "stt"
getstt.STT_DIR = str(STT)
if not REAL:
    getstt.platform_key = lambda: WORLD["key"]      # so the card can be driven on any computer
    getstt.unavailable_reason = lambda: WORLD["why"]
    getstt.cannot_run = lambda: WORLD["why"]
serve.Handler.log_request = lambda self, *a, **k: None
serve.Handler.log_message = lambda self, *a: None
if AS_PHONE:
    for patched in (mock.patch.object(network, "where", lambda ip, doc=None: network.LAN),
                    mock.patch.object(network, "may_connect", lambda ip, doc=None: True),
                    mock.patch.object(network, "let_in", lambda *a, **k: True)):
        patched.start()

WORLD = {"why": "", "probe": "none", "key": "linux x86_64",
         "build": {"steps": 30, "pause": 0.05, "fail": None}}

PROBES = {
    "none": {"python": "3.12", "ct2": "4.8.2", "cuda_devices": 0, "cuda_types": [], "cpu_types": ["int8"],
             "cublas": {"loads": False, "name": "libcublas.so.12", "dir": None}, "smi": None},
    "found-not-ready": {"python": "3.12", "ct2": "4.8.2", "cuda_devices": 1,
                        "cuda_types": ["float16", "float32", "int8", "int8_float16", "int8_float32"],
                        "cpu_types": ["int8"],
                        "cublas": {"loads": False, "name": "libcublas.so.12", "dir": None,
                                   "error": "libcublas.so.12: cannot open shared object file"},
                        "smi": {"name": "NVIDIA GeForce GTX 1650", "memory": 4294967296,
                                "driver": "595.91.07", "compute_cap": "7.5"}},
    "ready": {"python": "3.12", "ct2": "4.8.2", "cuda_devices": 1,
              "cuda_types": ["float16", "float32", "int8", "int8_float16", "int8_float32"],
              "cpu_types": ["int8"], "cublas": {"loads": True, "name": "libcublas.so.12", "dir": None},
              "smi": {"name": "NVIDIA GeForce RTX 4070", "memory": 12884901888, "driver": "595.91.07",
                      "compute_cap": "8.9"}},
    "error": {"error": "looking at the graphics card took more than 30 seconds"},
}
if not REAL:
    getstt._run_probe = lambda timeout=30: dict(PROBES[WORLD["probe"]])


# ---------------------------------------------------------------- the disk
def sparse(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)


def lay_out(runtime, models):
    shutil.rmtree(STT, ignore_errors=True)
    getstt._SIZES.clear()
    if runtime != "absent":
        gen, tag = getstt.PIN["generation"], getstt.PYTAG
        gen = {"older": gen - 1, "newer": gen + 1}.get(runtime, gen)
        tag = "cp311" if runtime == "other_python" else tag
        folder = STT / "runtime" / ("%d-%s" % (gen, tag))
        dists = getstt.REQUIRED if runtime != "broken" else getstt.REQUIRED[:1]
        for d, v in dists:
            (folder / ("%s-%s.dist-info" % (d, v or "1.0"))).mkdir(parents=True)
        sparse(folder / "ctranslate2" / "libctranslate2.so.4.8.2", 300_000_000)
    for key, state in (models or {}).items():
        if state == "absent":
            continue
        folder = STT / "models" / key
        pin = getstt.MODEL_PINS[key]
        for name, (_sha, size) in pin["files"].items():
            sparse(folder / name, size - (1 if state == "broken" and name == "model.bin" else 0))
        (folder / "meta.json").write_text(json.dumps(
            {"model": key, "repo": pin["repo"], "revision": pin["revision"] if state != "older" else "0" * 40,
             "pin": getstt.PIN["generation"] - (1 if state == "older" else 0), "built": "2026-09-28"}))


def fake_build(key, say=print, progress=None, cancel=None):
    """getstt.build, standing in: the bar of a download, the folders a real one leaves."""
    plan = getstt.plan(key)
    total = plan["download"] or 1
    b = dict(WORLD["build"])
    with getstt.using(key):
        say("  fetching %s" % key)
        for i in range(b["steps"] + 1):
            download.check(cancel)
            if progress:
                progress(int(total * i / b["steps"]), total,
                         "build" if key == "runtime" and i > b["steps"] * 0.9 else "download")
            if b["fail"] and i >= b["steps"] // 2:
                raise SystemExit("getstt: " + b["fail"])
            say("    %d%%" % (100 * i // b["steps"]))
            time.sleep(b["pause"])
        state = {k: ("ready" if getstt.model_info(k)["ready"] else "absent") for k in getstt.MODELS}
        if key == "runtime":
            lay_out("ready", state)
        else:
            state[key] = "ready"
            lay_out("ready", state)
    return 1


if not REAL:
    getstt.build = fake_build


# ---------------------------------------------------------------- the commands
def command(line):
    c = json.loads(line)
    what = c.get("cmd")
    if REAL:
        raise ValueError("a real stt/ is not changed by a test")
    if what == "state":
        lay_out(c.get("runtime", "absent"), c.get("models") or {})
        getstt.forget_hardware()
    elif what == "probe":
        WORLD["probe"] = c["answer"]
        getstt.forget_hardware()
    elif what == "build":
        WORLD["build"].update({k: c[k] for k in ("steps", "pause", "fail") if k in c})
    elif what == "unavailable":
        WORLD["why"] = c.get("why") or ""
    elif what == "wheel":
        # a kind of computer that has a build of the program, or one that has none (its size is not known)
        WORLD["key"] = "linux x86_64" if c.get("has", True) else None
        getstt.forget_hardware()
    elif what == "clear":
        for table in (serve.STT_JOBS, serve.PLANS, serve.CANCELS):
            table.clear()
        getstt.forget_hardware()
    else:
        raise ValueError("no such command: %r" % what)


def cleanup(*_):
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
try:
    srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("READY " + json.dumps({"port": srv.server_address[1], "stt": str(STT), "phone": AS_PHONE}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            command(line)
            print("OK", flush=True)
        except Exception as e:                                  # noqa: BLE001
            print("ERR %s: %s" % (type(e).__name__, e), flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
