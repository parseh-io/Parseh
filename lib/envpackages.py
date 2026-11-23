# SPDX-License-Identifier: GPL-3.0-or-later
"""The packages Parseh's environment lacks, added from Settings > Updating
Parseh (TO-DO §5.3, §5.13, a0.6.3).

environment.yml and lib/runtime.py's PACKAGES are the one list of what Parseh
runs with; the installers and the Windows wizard add what is missing every
time they run (runtime.complete_env).  A page that finds one missing -- the
narration panel without rapidfuzz, the Anki page without zstandard -- used to
print the pip command that adds it, which nobody on Windows can type and no
non-expert should have to.  This is the same complete_env, run by a button:
one job at a time, in a thread, reporting into JOB for the page to poll.

The environment is the one Parseh's own Python is in (runtime.find_env): a
Parseh started from some other Python, with no environment of its own, is
told so in words, and nothing is installed into a Python Parseh does not own.
"""
import threading
import time

import runtime

ANCHOR = "packages"                      # /settings/update/#packages
DOOR = "/settings/update/#" + ANCHOR
LOCK = threading.Lock()
JOB = {}                                 # the one job: running, say, log, error, ok


def missing():
    """[{name, what}] of the packages environment.yml lists and this
    environment lacks -- what the page lists, and what the button adds."""
    st = runtime.status()
    return [{"name": p["name"], "what": p["what"]} for p in st["packages"] if not p["have"]]


def job():
    with LOCK:
        return dict(JOB, log=list(JOB.get("log") or []))


class _Report(runtime.Report):
    """runtime's report, kept in JOB rather than written to a terminal."""

    def __init__(self):
        super().__init__(as_json=False)

    def _emit(self, obj, text):
        with LOCK:
            if obj.get("event") == "step" and obj.get("detail"):
                JOB["say"] = obj["detail"]
            if obj.get("event") == "log":
                JOB.setdefault("log", []).append(obj["line"])
                del JOB["log"][:-40]


def start():
    """Add what is missing, in a thread -> (answer, HTTP status)."""
    with LOCK:
        if JOB.get("running"):
            return {"ok": True, "running": True}, 200
    prefix, python = runtime.find_env()
    if not prefix or not python:
        return {"ok": False, "error": "This Parseh does not run in an environment of its own, so "
                "it cannot add packages from here. Installing Parseh from its release makes "
                "one, with every package in it."}, 409
    lacking = missing()
    if not lacking:
        return {"ok": True, "nothing": True}, 200
    with LOCK:
        JOB.clear()
        JOB.update(running=True, started=time.time(), log=[], error="", ok=False,
                   adding=[p["name"] for p in lacking],
                   say="adding " + ", ".join(p["name"] for p in lacking))

    def work():
        ok, error = False, ""
        try:
            ok = runtime.complete_env(prefix, python, _Report())
            if not ok:
                left = [p["name"] for p in missing()]
                error = ("Not everything could be added%s. The lines below say why; a computer "
                         "with no internet connection cannot fetch them."
                         % (" (still missing: %s)" % ", ".join(left) if left else ""))
        except Exception as e:                  # noqa: BLE001 -- said, never a dead page
            error = "%s: %s" % (type(e).__name__, e)
        with LOCK:
            JOB.update(running=False, ok=ok and not error, error=error, finished=time.time(),
                       say="done" if ok and not error else JOB.get("say", ""))

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "running": True}, 200
