# SPDX-License-Identifier: GPL-3.0-or-later
"""A stand-in for lane D's lib/syncjobs.py (a0.7.0), with its interface exactly,
for Settings -> Devices' tests until the real module is merged.  Put in
sys.modules["syncjobs"] by the tests."""
import time

SWITCHES = {"send": False, "accept": False}
JOBS = []


def seed():
    SWITCHES.update(send=False, accept=False)
    del JOBS[:]
    JOBS.extend([
        {"id": "j1", "kind": "whisper", "title": "Transcribe the interview", "state": "waiting",
         "asked_by": "me", "asked_by_name": "this computer", "taken_by": None, "taken_by_name": None,
         "reason": "", "at": time.time() - 60},
        {"id": "j2", "kind": "book", "title": "Build Demo book", "state": "done", "asked_by": "p-laptop",
         "asked_by_name": "laptop", "taken_by": "me", "taken_by_name": "this computer", "reason": "",
         "at": time.time() - 3600},
    ])


def switches():
    return dict(SWITCHES)


def set_switches(send=None, accept=None):
    if send is not None:
        SWITCHES["send"] = bool(send)
    if accept is not None:
        SWITCHES["accept"] = bool(accept)
    return dict(SWITCHES)


def capabilities(partner_id=None):
    return {"whisper": True, "latex": True, "aligners": False, "analyzers": False, "gpu": False,
            "accepts": SWITCHES["accept"]}


def jobs():
    return [dict(j) for j in JOBS]


def cancel(job_id):
    for j in JOBS:
        if j["id"] == job_id and j["state"] in ("waiting", "taken", "running"):
            j["state"] = "cancelled"
            return {"ok": True}
    return {"ok": False}


def waiting_here():
    return [dict(j) for j in JOBS if j["state"] == "waiting"]
