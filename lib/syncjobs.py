#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Jobs lent between paired computers (a0.7.0, lane D; docs/sync.md "Jobs").

A computer that cannot do a heavy piece of work -- build a book's PDF without
LaTeX, estimate by the sound without NumPy or ffmpeg, align a narration -- may
send it to a paired Parseh that can, and the result comes back.  Two switches,
both OFF on a fresh install and never synced (config/sync/jobs.json is this
device's): "send heavy jobs to paired computers" and "accept jobs from paired
devices".

    switches() -> {"send", "accept"};  set_switches(send=None, accept=None)
    capabilities(partner_id=None) -> {"whisper": [models], "latex", "aligners": [codes],
                                      "analyzers": [codes], "gpu", "accepts", ...}
    jobs() -> [{"id", "kind", "title", "state", "asked_by", "asked_by_name",
                "taken_by", "taken_by_name", "reason", "at", ...}]
    cancel(job_id) -> {"ok"};  waiting_here() -> [jobs asked here, not finished]
    ask(kind, args, title, unit=None, prefer=None) -> the job;  view(job_id)
    can_here(kind, args) -> (bool, why);  who_can(kind, args) -> [partners]

THE RECORD IS THE ASKER'S, AND TRAVELS BY ITS OWN OPS -- NOT AS A SYNCED UNIT.
A job is a record: what to do (`kind`, `args`), on what (`unit` and the hash it
had when asked, or the values in `args`), who asked, who can do it, its state.
It lives in the asking computer's config/sync/jobs.json, and that computer
alone decides who has it.  Taking is therefore an exchange, not a race: the
asker offers the job to ONE partner at a time (`jobs.offer`), and only an
answer "taken" makes that partner its holder.  An offer that got no answer is
asked about (`jobs.state`) before the job is offered to anyone else.  A synced
record would have made every computer an author of the same state, and two
partners taking one job a conflict for lane C's rules to settle after the fact.

THE STATES (said in words on the page that started it):
    waiting   -> "waiting for a computer"   nobody has it; it waits, whatever
                 the silence, and never fails for want of a partner
    taken     -> "on <partner>"             the partner answers `jobs.state`;
                 one silent for longer than DEADLINE gives it back (waiting)
    done      -> "done"                     the result is here
    failed    -> the reason, in words       the partner said why
    cancelled                               asked away here

THE RESULT COMES BACK AS ORDINARY CHANGES.  A job on a unit (a book's source)
runs on the partner's own copy, which it first HOLDS at the asker's version
(syncexchange.fetch: a partner that left the book out takes it in); what the
pipeline writes into that unit reaches the asker through the exchange
(sync_from the taker, at once, as well as by the scheduler).  What sync never
carries -- a built PDF, a reader (docs/sync.md: built pages never sync) -- comes
back as the job's OUTPUT FILES (`jobs.blob`, by sha256, in chunks), written into
the asker's own copy of the unit.  A small answer (an estimate's times) comes
back in `result`.

Standard library only; the pipelines are imported where a job runs.
"""
import contextlib
import hashlib
import json
import os
import secrets
import shutil
import sys
import threading
import time
import traceback

LIB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(LIB)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import syncid      # noqa: E402
import synclog     # noqa: E402
import syncunits   # noqa: E402

DEADLINE = 120.0        # seconds a partner that took a job may stay silent before it is given back
TICK = 2.0              # how often the asker looks at its jobs
TIMEOUT = 10.0          # one call to a partner
CAPS_TTL = 60.0         # how long a partner's capabilities are trusted before they are asked again
KEEP_DONE = 24 * 3600   # a finished job stays on the list for a day
CHUNK = 1 << 20         # one piece of an output file
MAX_DOING = 1           # jobs this computer works on for others at once

STATES = ("waiting", "taken", "done", "failed", "cancelled")
OPEN = ("waiting", "taken")

_LOCK = threading.RLock()
_DOCS = {}              # the file's path -> its contents (one install; several in a test's one process)
_CAPS = {}              # partner id -> {"caps", "at", "name"}
_HERE = {}              # the file's path -> {"caps", "at"}: this computer's own, worked out
_LOOP = {"thread": None, "stop": None, "wake": threading.Event()}
CAPS_FORCE = {}         # a test's seam: install id (or "*") -> keys put over that computer's own capabilities
INLINE = False          # a test's seam: a taken job runs in the offer's own call, and a fetch too
ON_APPLIED = []         # callbacks(job) after a job's output files were written here (serve.py: the library page)
FINISH = {}             # kind -> fn(args, result) -> what the page that asked is answered (serve.py: the estimate)


class JobFailed(Exception):
    """A job that ran and could not be done; the message is said to the person."""


# ------------------------------------------------------------------ this device's file
def _path():
    return os.path.join(synclog.home(), "jobs.json")


def _doc():
    p = _path()
    if p not in _DOCS:
        try:
            with open(p, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            doc = {}
        doc = doc if isinstance(doc, dict) else {}
        sw = doc.get("switches") if isinstance(doc.get("switches"), dict) else {}
        doc = {"switches": {"send": sw.get("send") is True, "accept": sw.get("accept") is True},
               "asked": doc.get("asked") if isinstance(doc.get("asked"), dict) else {},
               "doing": doc.get("doing") if isinstance(doc.get("doing"), dict) else {}}
        # a job this computer was working on for another did not survive a
        # restart: forgotten, so the asker hears "unknown" and gives it back at once
        for jid in [j for j, r in doc["doing"].items() if r.get("state") == "taken"]:
            doc["doing"].pop(jid)
        _DOCS[p] = doc
    return _DOCS[p]


def _save():
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_DOCS[p], fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, p)


def _files_dir(jid):
    return os.path.join(synclog.home(), "jobs", jid)


# ------------------------------------------------------------------ the switches
def switches():
    with _LOCK:
        return dict(_doc()["switches"])


def set_switches(send=None, accept=None):
    with _LOCK:
        sw = _doc()["switches"]
        if send is not None:
            sw["send"] = bool(send)
        if accept is not None:
            sw["accept"] = bool(accept)
        _save()
        _HERE.pop(_path(), None)
    wake()
    return switches()


# ------------------------------------------------------------------ what a computer can do
def _caps_here():
    caps = {"whisper": [], "latex": False, "aligners": [], "analyzers": [], "gpu": False,
            "accepts": switches()["accept"], "reader": False, "estimate": False, "ffmpeg": False,
            "narration": True, "send_only": False}
    with contextlib.suppress(Exception):
        import getstt
        import speechmodels
        if getstt.runtime_ready():
            caps["whisper"] = [m for m in speechmodels.MODELS if getstt.model_ready(m)]
        caps["aligners"] = [c for c in getstt.ALIGNERS if getstt.aligner_ready(c)]
        hw = getstt._HW.get("data")          # the last look; never a probe from here
        caps["gpu"] = bool(isinstance(hw, dict) and hw.get("ready"))
    with contextlib.suppress(Exception):
        import runtime
        prefix, python = runtime.find_env()
        caps["latex"] = bool(runtime.tool("lualatex", prefix))
        caps["reader"] = bool(python)
    with contextlib.suppress(Exception):
        import importlib.util
        caps["estimate"] = (importlib.util.find_spec("numpy") is not None
                            and os.path.isfile(os.path.join(LIB, "wavealign.py")))
    with contextlib.suppress(Exception):
        import audiofile
        caps["ffmpeg"] = bool(audiofile.have_ffmpeg())
    with contextlib.suppress(Exception):
        import analysispins
        import analyzer
        caps["analyzers"] = [c for c in analysispins.UDPIPE_MODELS if analyzer.available(c)]
    caps.update(CAPS_FORCE.get("*") or {})
    caps.update(CAPS_FORCE.get(syncid.install_id()) or {})
    caps["accepts"] = switches()["accept"]
    return caps


def capabilities(partner_id=None):
    """What this computer (None) or a partner can do: worked out from what
    Settings has installed, never typed.  A partner's are what it last said
    (asked again after CAPS_TTL); one never heard from answers all-false
    with "known": False."""
    if partner_id is None:
        with _LOCK:
            got = _HERE.get(_path())
            if got is None or time.time() - got["at"] > CAPS_TTL:
                got = _HERE[_path()] = {"caps": _caps_here(), "at": time.time()}
            return dict(got["caps"], known=True)
    got = _CAPS.get(partner_id)
    if got is None or time.time() - got["at"] > CAPS_TTL:
        with contextlib.suppress(Exception):
            got = _ask_caps(partner_id)
    if got is None:
        return {"whisper": [], "latex": False, "aligners": [], "analyzers": [], "gpu": False,
                "accepts": False, "known": False}
    return dict(got["caps"], known=True)


def _ask_caps(pid):
    ans, _ = _call(pid, "jobs.caps", {}, timeout=5.0)
    rec = {"caps": ans.get("caps") or {}, "at": time.time(), "name": ans.get("name") or ""}
    _CAPS[pid] = rec
    return rec


# ------------------------------------------------------------------ the kinds of job
def _book_args(args):
    return args.get("what") if args.get("what") in ("pdf", "html") else "pdf"


def _need_book(caps, args):
    return bool(caps.get("reader")) and (_book_args(args) == "html" or bool(caps.get("latex")))


def _here_book(args):
    caps = capabilities()
    if not caps.get("reader"):
        return False, "this computer cannot build a book's reader: Parseh's reading environment is not installed"
    if _book_args(args) == "pdf" and not caps.get("latex"):
        return False, "this computer cannot build the PDF: LaTeX (lualatex) is not installed"
    return True, ""


def _need_estimate(caps, args):
    return bool(caps.get("estimate")) and (args.get("values") is not None or bool(caps.get("ffmpeg")))


def _here_estimate(args):
    caps = capabilities()
    if not caps.get("estimate"):
        return False, "this computer cannot estimate by the sound: NumPy is not installed"
    if args.get("values") is None and not caps.get("ffmpeg"):
        return False, "this computer cannot read the recording: ffmpeg is not installed"
    return True, ""


def _run_book(rec, say):
    import bookbuild
    d = syncunits.locate(rec["unit"]).where
    what = _book_args(rec["args"])
    t0 = time.time()
    bookbuild.start(d, what)
    while True:
        st = bookbuild.status(d)
        if st.get("state") != "running":
            break
        last = next((ln.strip() for ln in reversed(st.get("log") or []) if ln.strip()), "")
        say(last or "building…")
        time.sleep(1.0)
    if st.get("state") != "done":
        lines = [ln.strip() for ln in (st.get("log") or []) if ln.strip()]
        err = next((ln for ln in lines if ln.startswith("!") or "FAILED" in ln), None)
        raise JobFailed("the build failed on %s: %s" % (syncid.name(), err or " / ".join(lines[-2:]) or "no log"))
    return {"result": {"what": what, "took": round(time.time() - t0, 1)}, "outputs": _built_files(d, what)}


def _built_files(d, what):
    """What a book's build made that sync never carries: its PDF and its reader."""
    out = {}
    if what == "pdf":
        for f in sorted(os.listdir(d)):
            if f.endswith(".pdf") and os.path.isfile(os.path.join(d, f)):
                out[f] = os.path.join(d, f)
    reader = os.path.join(d, "reader")
    for here, dirs, files in os.walk(reader):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in files:
            if f.startswith(".") or f.endswith((".tmp", ".part")):
                continue
            p = os.path.join(here, f)
            out[os.path.relpath(p, d).replace(os.sep, "/")] = p
    return out


def _run_estimate(rec, say):
    import wavealign
    a = rec["args"]
    values, times = a.get("values"), a.get("times")
    if values is None:
        import audiofile
        u = syncunits.locate(rec["unit"])
        src = syncunits.path_of(u, a["inner"])
        values = audiofile.envelope(src, a["start"], a["end"], a.get("rate") or 100)
    say("estimating…")
    try:
        res = wavealign.estimate_pieces(values, a["end"] - a["start"], a["texts"], a["kind"],
                                        sample_times=times)
    except MemoryError:
        raise JobFailed("this stretch is too long to estimate by the sound at once")
    except ValueError as e:
        raise JobFailed(str(e))
    return {"result": json.loads(json.dumps(res, default=float))}


def _run_align(rec, say):
    """The narration's alignment, as the reader's align button runs it
    (serve.py _narration_align): lib/timestamp.py, then the reader."""
    import subprocess
    d = syncunits.locate(rec["unit"]).where
    a = rec["args"]
    cmd = [sys.executable, os.path.join(LIB, "timestamp.py")]
    if a.get("narration"):
        cmd += ["--narration", str(a["narration"])]
    if a.get("force"):
        cmd.append("--force")
    with contextlib.suppress(Exception):
        import audiofile
        if not audiofile.have_ffmpeg():
            cmd.append("--no-snap")
    for what, c in (("aligning", cmd), ("the reader", [sys.executable, os.path.join(LIB, "tex2html.py")])):
        say(what + "…")
        r = subprocess.run(c, cwd=d, capture_output=True, text=True, timeout=3600)
        if r.returncode:
            tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-1:] or ["no output"]
            raise JobFailed("%s failed on %s: %s" % (what, syncid.name(), tail[0]))
    return {"result": {}, "outputs": _built_files(d, "html")}


# kind -> words, what a computer needs (from its capabilities), whether this one can, the runner
KINDS = {
    "book-build": {"title": "Build a book", "need": _need_book, "here": _here_book, "run": _run_book},
    "estimate": {"title": "Estimate by the sound", "need": _need_estimate, "here": _here_estimate,
                 "run": _run_estimate},
    "narration-align": {"title": "Align a narration", "need": lambda caps, a: bool(caps.get("narration")),
                        "here": lambda a: (True, ""), "run": _run_align},
}
RUNNERS = {k: v["run"] for k, v in KINDS.items()}      # a test may put a fake runner here


def can_here(kind, args):
    k = KINDS.get(kind)
    if k is None:
        return False, "no such job: %s" % kind
    return k["here"](args or {})


def _names():
    try:
        import syncpeer
        return {p["id"]: p.get("name") or p["id"] for p in syncpeer.partners() if isinstance(p, dict)}
    except Exception:                                 # noqa: BLE001 -- no transport: no partner
        return {}


def _partners():
    try:
        import syncpeer
        return [p for p in syncpeer.partners() if isinstance(p, dict) and p.get("id")]
    except Exception:                                 # noqa: BLE001
        return []


def who_can(kind, args):
    """Every paired computer, with whether it can do this job from what it
    last said: [{"id", "name", "reachable", "can": True | False | None}]
    (None: never heard from, so not known)."""
    k = KINDS.get(kind)
    out = []
    for p in _partners():
        got = _CAPS.get(p["id"])
        if got is None and p.get("reachable") is not False:
            with contextlib.suppress(Exception):
                got = _ask_caps(p["id"])
        can = None if got is None else bool(k and got["caps"].get("accepts") and k["need"](got["caps"], args or {}))
        out.append({"id": p["id"], "name": p.get("name") or (got or {}).get("name") or p["id"],
                    "reachable": p.get("reachable"), "can": can})
    return out


# ------------------------------------------------------------------ the transport
def _call(pid, op, payload, timeout=None, body=None):
    import syncpeer
    got, data = syncpeer.call(pid, op, payload, body=body, timeout=timeout or TIMEOUT)
    if not isinstance(got, dict):
        raise syncpeer.Refused("an answer that is not an object")
    return got, data


def _transport_errors():
    import syncpeer
    return syncpeer.Unreachable, syncpeer.Refused


# ------------------------------------------------------------------ asking
def _unit_hash(uid):
    with contextlib.suppress(Exception):
        synclog.refresh(uid)
    row = synclog.get(uid)
    return row["hash"] if row and not row.get("deleted") else None


def book_unit(book_dir):
    """A book's folder -> its unit id ("book:<language folder>/<slug>"), or None."""
    root = syncunits.SHELVES.get("books")
    if not root:
        return None
    rel = os.path.relpath(os.path.abspath(book_dir), os.path.abspath(root)).replace(os.sep, "/")
    if rel.startswith("..") or rel.count("/") != 1:
        return None
    return "book:" + rel


def video_unit(video_dir):
    root = syncunits.SHELVES.get("videos")
    if not root:
        return None
    rel = os.path.relpath(os.path.abspath(video_dir), os.path.abspath(root)).replace(os.sep, "/")
    if rel.startswith("..") or rel.count("/") != 1:
        return None
    return "video:" + rel


def ask(kind, args, title, unit=None, prefer=None):
    """A new job, asked here -> its record.  It waits until a partner that can
    takes it; `prefer` is offered it first (the page's "send to <partner>")."""
    if kind not in KINDS:
        raise ValueError("no such job: %s" % kind)
    now = time.time()
    rec = {"id": secrets.token_hex(8), "kind": kind, "title": title or KINDS[kind]["title"],
           "args": args or {}, "unit": unit, "unit_hash": _unit_hash(unit) if unit else None,
           "asked_by": syncid.install_id(), "asked_by_name": syncid.name(), "state": "waiting",
           "taken_by": None, "taken_by_name": None, "reason": "", "say": "waiting for a computer",
           "at": now, "asked_at": now, "heard": None, "asked_of": None, "prefer": prefer,
           "drops": [], "result": None, "note": ""}
    with _LOCK:
        _doc()["asked"][rec["id"]] = rec
        _save()
    wake()
    return dict(rec)


def _public(rec, mine=True):
    out = {k: rec.get(k) for k in ("id", "kind", "title", "state", "asked_by", "asked_by_name",
                                   "taken_by", "taken_by_name", "reason", "at", "unit", "say")}
    out["mine"] = mine
    if not out["say"]:
        out["say"] = _say(rec)
    return out


def _say(rec):
    s = rec.get("state")
    if s == "waiting":
        return "waiting for a computer"
    if s == "taken":
        return "on %s" % (rec.get("taken_by_name") or rec.get("taken_by"))
    if s == "done":
        return "done"
    if s == "failed":
        return rec.get("reason") or "failed"
    return "cancelled"


def jobs():
    """Every job this computer asked, and every job it works on for another,
    newest first."""
    with _LOCK:
        d = _doc()
        out = [_public(r, True) for r in d["asked"].values()]
        out += [_public(r, False) for r in d["doing"].values()]
    return sorted(out, key=lambda r: -(r.get("at") or 0))


def waiting_here():
    """The jobs this computer asked that have not finished (waiting, or on a
    partner): lane C's "make identical" lists and cancels these."""
    return [j for j in jobs() if j["mine"] and j["state"] in OPEN]


def view(job_id):
    """A job as the page that asked follows it -> {"id", "kind", "state",
    "say", "reason", "taken_by_name", "result"?} or None."""
    with _LOCK:
        rec = _doc()["asked"].get(job_id)
        if rec is None:
            return None
        out = _public(rec)
        if rec["state"] == "done":
            fin = FINISH.get(rec["kind"])
            out["result"] = fin(rec["args"], rec.get("result")) if fin else rec.get("result")
        return out


def latest_for(kind, unit):
    """The newest job of this kind on this unit asked here, or None."""
    with _LOCK:
        got = [r for r in _doc()["asked"].values() if r["kind"] == kind and r.get("unit") == unit]
    if not got:
        return None
    return view(max(got, key=lambda r: r["at"])["id"])


def cancel(job_id):
    """Cancel a job: asked here, it is taken back from whoever has it; done
    here for another, the work's result is not sent."""
    with _LOCK:
        d = _doc()
        rec = d["asked"].get(job_id)
        if rec is not None:
            if rec["state"] in OPEN:
                for p in (rec.get("taken_by"), rec.get("asked_of")):
                    if p and p not in rec["drops"]:
                        rec["drops"].append(p)
                rec.update(state="cancelled", reason="cancelled here", say="cancelled", at=time.time())
                _save()
            wake()
            return {"ok": True}
        rec = d["doing"].get(job_id)
        if rec is not None:
            rec.update(state="cancelled", reason="cancelled on %s" % syncid.name(), at=time.time())
            _save()
            return {"ok": True}
    return {"ok": False, "error": "no such job"}


# ------------------------------------------------------------------ the partner's side: the ops
def _caller_name(pid):
    return _names().get(pid) or pid


def op_caps(partner, payload, body):
    return {"ok": True, "caps": capabilities(), "name": syncid.name(), "install": syncid.install_id()}, None


def op_offer(partner, payload, body):
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    jid, kind = job.get("id"), job.get("kind")
    if not isinstance(jid, str) or not jid.isalnum() or len(jid) > 40:
        return {"ok": True, "taken": False, "why": "not a job"}, None
    with _LOCK:
        d = _doc()
        mine = d["doing"].get(jid)
        if mine is not None and mine.get("asked_by") == partner and mine["state"] != "cancelled":
            return {"ok": True, "taken": True, "name": syncid.name()}, None
        if not d["switches"]["accept"]:
            return {"ok": True, "taken": False, "why": "%s does not accept jobs" % syncid.name()}, None
        if kind not in KINDS:
            return {"ok": True, "taken": False, "why": "%s does not know this job" % syncid.name()}, None
        ok, why = can_here(kind, job.get("args") or {})
        if not ok:
            return {"ok": True, "taken": False, "why": why}, None
        busy = sum(1 for r in d["doing"].values() if r["state"] == "taken")
        if busy >= MAX_DOING:
            return {"ok": True, "taken": False, "why": "%s is busy with another job" % syncid.name()}, None
    uid = job.get("unit")
    if uid:
        # THE PARTNER HOLDS THE UNIT, AT THE ASKER'S VERSION, before it works on it
        try:
            syncunits.locate(uid)
        except KeyError:
            return {"ok": True, "taken": False, "why": "not a unit that syncs"}, None
        if _unit_hash(uid) != job.get("unit_hash") and INLINE:
            _fetch_quietly(uid, partner)
        if _unit_hash(uid) != job.get("unit_hash"):
            threading.Thread(target=_fetch_quietly, args=(uid, partner), daemon=True).start()
            return {"ok": True, "taken": False, "why": "%s is bringing in the asker's version first"
                    % syncid.name(), "retry": True}, None
    rec = {"id": jid, "kind": kind, "title": job.get("title") or KINDS[kind]["title"],
           "args": job.get("args") or {}, "unit": uid, "asked_by": partner,
           "asked_by_name": job.get("asked_by_name") or _caller_name(partner),
           "taken_by": syncid.install_id(), "taken_by_name": syncid.name(), "state": "taken",
           "say": "starting…", "reason": "", "at": time.time(), "result": None, "outputs": {}}
    with _LOCK:
        _doc()["doing"][jid] = rec
        _save()
    if INLINE:
        _work(jid)
    else:
        threading.Thread(target=_work, args=(jid,), name="job-%s" % jid, daemon=True).start()
    return {"ok": True, "taken": True, "name": syncid.name()}, None


_FETCHING = set()


def _fetch_quietly(uid, partner):
    import syncexchange
    key = (uid, partner)
    if key in _FETCHING:
        return
    _FETCHING.add(key)
    try:
        syncexchange.fetch(uid, partner)
    except Exception as e:                            # noqa: BLE001 -- the asker offers again
        print("!! jobs: could not bring in %s: %s" % (uid, e), flush=True)
    finally:
        _FETCHING.discard(key)


def _work(jid):
    with _LOCK:
        rec = _doc()["doing"].get(jid)
        if rec is None:
            return

    def say(words):
        with _LOCK:
            rec["say"] = str(words)[:300]

    try:
        out = RUNNERS[rec["kind"]](rec, say) or {}
        outputs = {}
        for inner, path in (out.get("outputs") or {}).items():
            outputs[inner] = {"path": path, "sha": _sha(path), "size": os.path.getsize(path)}
        if rec.get("unit"):
            with contextlib.suppress(Exception):
                synclog.refresh(rec["unit"])           # recorded now, not 2 s from now
        with _LOCK:
            if rec["state"] == "taken":
                rec.update(state="done", say="done", result=out.get("result"), outputs=outputs,
                           at=time.time())
    except JobFailed as e:
        with _LOCK:
            rec.update(state="failed", reason=str(e), say=str(e), at=time.time())
    except Exception as e:                            # noqa: BLE001 -- said, never a traceback
        traceback.print_exc()
        with _LOCK:
            rec.update(state="failed", reason="the job failed on %s: %s" % (syncid.name(), e),
                       at=time.time())
    with _LOCK:
        if jid in _doc()["doing"]:
            _save()
    with contextlib.suppress(Exception):
        import syncexchange
        syncexchange.request(rec["asked_by"], "a job's result")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def op_state(partner, payload, body):
    with _LOCK:
        rec = _doc()["doing"].get(payload.get("id"))
        if rec is None or rec.get("asked_by") != partner:
            return {"ok": True, "state": "unknown"}, None
        out = {"ok": True, "state": {"taken": "running"}.get(rec["state"], rec["state"]),
               "say": rec.get("say") or "", "reason": rec.get("reason") or ""}
        if rec["state"] == "done":
            out["result"] = rec.get("result")
            out["outputs"] = [{"inner": k, "sha": v["sha"], "size": v["size"]}
                              for k, v in sorted(rec["outputs"].items())]
        return out, None


def op_blob(partner, payload, body):
    with _LOCK:
        rec = _doc()["doing"].get(payload.get("id"))
        if rec is None or rec.get("asked_by") != partner or rec["state"] != "done":
            return {"ok": False, "error": "no such job here"}, None
        f = rec["outputs"].get(payload.get("inner"))
    if f is None:
        return {"ok": False, "error": "no such file in this job"}, None
    off, n = int(payload.get("offset") or 0), min(int(payload.get("length") or CHUNK), 8 * CHUNK)
    with open(f["path"], "rb") as fh:
        fh.seek(off)
        data = fh.read(n)
    return {"ok": True, "size": f["size"], "chunk": hashlib.sha256(data).hexdigest()}, data


def op_drop(partner, payload, body):
    with _LOCK:
        d = _doc()
        rec = d["doing"].get(payload.get("id"))
        if rec is not None and rec.get("asked_by") == partner:
            if rec["state"] == "taken":
                rec.update(state="cancelled", reason="given back to %s" % rec.get("asked_by_name"))
            d["doing"].pop(rec["id"], None)
            _save()
    return {"ok": True}, None


OPS = {"jobs.caps": op_caps, "jobs.offer": op_offer, "jobs.state": op_state,
       "jobs.blob": op_blob, "jobs.drop": op_drop}


def register():
    import syncroutes
    for op, h in OPS.items():
        syncroutes.register(op, h)


# ------------------------------------------------------------------ the asker's loop
def wake():
    _LOOP["wake"].set()


def step():
    """One look at every job asked here (the loop calls it every TICK; tests call it)."""
    with _LOCK:
        ids = list(_doc()["asked"])
    for jid in ids:
        with _LOCK:
            rec = _doc()["asked"].get(jid)
        if rec is None:
            continue
        try:
            _drops(rec)
            if rec["state"] == "waiting":
                _place(rec)
            elif rec["state"] == "taken":
                _follow(rec)
        except Exception as e:                        # noqa: BLE001 -- one job never stops the others
            traceback.print_exc()
            with _LOCK:
                rec["note"] = str(e)
    _prune()


def _set(rec, **kw):
    with _LOCK:
        rec.update(kw)
        _save()


def _drops(rec):
    Unreachable, Refused = _transport_errors()
    for pid in list(rec.get("drops") or []):
        try:
            _call(pid, "jobs.drop", {"id": rec["id"]})
        except Unreachable:
            continue
        except Refused:
            pass
        with _LOCK:
            if pid in rec["drops"]:
                rec["drops"].remove(pid)
            _save()


def _place(rec):
    Unreachable, Refused = _transport_errors()
    names = _names()
    pid = rec.get("asked_of")
    if pid:
        # AN OFFER THAT GOT NO ANSWER: asked about before anyone else is offered it
        try:
            ans, _ = _call(pid, "jobs.state", {"id": rec["id"]})
        except Unreachable:
            if time.time() - (rec.get("offered_at") or 0) > DEADLINE:
                if pid not in rec["drops"]:
                    rec["drops"].append(pid)
                _set(rec, asked_of=None)
            return
        except Refused:
            _set(rec, asked_of=None)
            return
        if ans.get("state") in ("running", "done", "failed"):
            _set(rec, state="taken", taken_by=pid, taken_by_name=names.get(pid, pid), asked_of=None,
                 heard=time.time(), at=time.time(), say="on %s" % names.get(pid, pid))
            return _follow(rec)
        _set(rec, asked_of=None)
    partners = _partners()
    partners.sort(key=lambda p: (p["id"] != rec.get("prefer"), p.get("reachable") is False))
    for p in partners:
        pid = p["id"]
        if pid in (rec.get("drops") or []):
            continue
        try:
            caps = capabilities(pid)
        except Exception:                             # noqa: BLE001
            continue
        if not caps.get("known") or not caps.get("accepts") or not KINDS[rec["kind"]]["need"](caps, rec["args"]):
            continue
        _set(rec, asked_of=pid, offered_at=time.time())
        offer = {k: rec.get(k) for k in ("id", "kind", "title", "args", "unit", "unit_hash", "asked_by_name")}
        try:
            ans, _ = _call(pid, "jobs.offer", {"job": offer})
        except Unreachable:
            return                                    # asked about at the next look
        except Refused as e:
            _set(rec, asked_of=None, note=str(e))
            continue
        if ans.get("taken"):
            name = ans.get("name") or names.get(pid, pid)
            _set(rec, state="taken", taken_by=pid, taken_by_name=name, asked_of=None, heard=time.time(),
                 at=time.time(), say="on %s" % name, note="")
            return
        _set(rec, asked_of=None, note=ans.get("why") or "")
        if ans.get("retry"):
            return
    with _LOCK:
        rec["say"] = "waiting for a computer" + (": " + rec["note"] if rec.get("note") else "")


def _give_back(rec, why):
    pid = rec.get("taken_by")
    with _LOCK:
        if pid and pid not in rec["drops"]:
            rec["drops"].append(pid)
        rec.update(state="waiting", taken_by=None, taken_by_name=None, heard=None, note=why,
                   say="waiting for a computer: " + why, at=time.time())
        _save()


def _follow(rec):
    Unreachable, Refused = _transport_errors()
    pid, name = rec["taken_by"], rec.get("taken_by_name") or rec["taken_by"]
    try:
        ans, _ = _call(pid, "jobs.state", {"id": rec["id"]})
    except Unreachable:
        if time.time() - (rec.get("heard") or 0) > DEADLINE:
            _give_back(rec, "%s went silent, so the job was given back" % name)
        return
    except Refused as e:
        return _give_back(rec, "%s refused: %s" % (name, e))
    with _LOCK:
        rec["heard"] = time.time()
    st = ans.get("state")
    if st == "running":
        with _LOCK:
            rec["say"] = "on %s" % name + (": " + ans["say"] if ans.get("say") else "")
        return
    if st in ("unknown", "cancelled"):
        return _give_back(rec, "%s no longer had the job" % name)
    if st == "failed":
        _set(rec, state="failed", reason=ans.get("reason") or "it failed on %s" % name, at=time.time(),
             say=ans.get("reason") or "failed", drops=rec["drops"] + [pid])
        return
    if st != "done":
        return
    _collect(rec, pid, ans)


def _collect(rec, pid, ans):
    """The result of a job done on `pid` brought here: its output files
    written into this computer's copy of the unit, and the unit's own changes
    pulled through the exchange."""
    Unreachable, Refused = _transport_errors()
    staged = {}
    folder = _files_dir(rec["id"])
    for f in ans.get("outputs") or []:
        inner = f.get("inner") or ""
        if not _safe_inner(inner):
            continue
        dst = os.path.join(folder, *inner.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not (os.path.isfile(dst) and _sha(dst) == f["sha"]):
            with open(dst + ".part", "wb") as out:
                off = 0
                while off < f["size"] or (off == 0 and f["size"] == 0):
                    got, data = _call(pid, "jobs.blob", {"id": rec["id"], "inner": inner, "offset": off,
                                                          "length": CHUNK})
                    if not got.get("ok"):
                        raise Refused(got.get("error") or "the file was refused")
                    data = data or b""
                    if hashlib.sha256(data).hexdigest() != got.get("chunk"):
                        raise Refused("a piece of %s arrived damaged" % inner)
                    out.write(data)
                    off += len(data)
                    if not data:
                        break
            if _sha(dst + ".part") != f["sha"]:
                os.remove(dst + ".part")
                raise Refused("%s arrived damaged" % inner)
            os.replace(dst + ".part", dst)
        staged[inner] = dst
    if rec.get("unit"):
        import syncexchange
        with contextlib.suppress(Exception):
            syncexchange.sync_from(pid, only=syncexchange.owner_of(rec["unit"]), why="a job's result")
    if staged and rec.get("unit"):
        _write_outputs(rec, staged)
    shutil.rmtree(folder, ignore_errors=True)
    _set(rec, state="done", result=ans.get("result"), say="done", at=time.time(), reason="",
         drops=rec["drops"] + [pid])
    for cb in list(ON_APPLIED):
        with contextlib.suppress(Exception):
            cb(dict(rec))


def _safe_inner(inner):
    parts = inner.split("/")
    return bool(inner) and not inner.startswith("/") and all(p not in ("", ".", "..") for p in parts) \
        and "\\" not in inner and "\0" not in inner


def _write_outputs(rec, staged):
    u = syncunits.locate(rec["unit"])
    hold = contextlib.nullcontext()
    with contextlib.suppress(Exception):
        import pathlock
        hold = pathlock.held(u.where)
    with hold:
        if rec["kind"] in ("book-build", "narration-align") and any(i.startswith("reader/") for i in staged):
            # the reader is replaced whole: a file the new build no longer makes goes
            old = os.path.join(u.where, "reader")
            for here, _dirs, files in os.walk(old):
                for f in files:
                    inner = os.path.relpath(os.path.join(here, f), u.where).replace(os.sep, "/")
                    if inner not in staged:
                        with contextlib.suppress(OSError):
                            os.remove(os.path.join(here, f))
        for inner, src in staged.items():
            dst = os.path.join(u.where, *inner.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = dst + ".tmp"
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)


def _prune():
    now = time.time()
    with _LOCK:
        d = _doc()
        gone = [j for j, r in d["asked"].items()
                if r["state"] not in OPEN and not r.get("drops") and now - r["at"] > KEEP_DONE]
        gone_doing = [j for j, r in d["doing"].items() if r["state"] != "taken" and now - r["at"] > KEEP_DONE]
        for j in gone:
            d["asked"].pop(j)
        for j in gone_doing:
            d["doing"].pop(j)
        if gone or gone_doing:
            _save()


def start(tick=None):
    """The asker's loop, on a thread; registers the ops."""
    if _LOOP["thread"] is not None and _LOOP["thread"].is_alive():
        return _LOOP["thread"]
    with contextlib.suppress(Exception):
        register()
    tick = TICK if tick is None else tick
    stop_ev = threading.Event()
    home = synclog.home()

    def run():
        while not stop_ev.is_set():
            if synclog.home() != home:
                break
            try:
                step()
            except Exception as e:                    # noqa: BLE001 -- never stops Parseh
                print("!! jobs: %s" % e, flush=True)
            _LOOP["wake"].wait(timeout=tick)
            _LOOP["wake"].clear()

    t = threading.Thread(target=run, name="syncjobs", daemon=True)
    _LOOP.update(thread=t, stop=stop_ev)
    t.start()
    return t


def stop(timeout=10):
    if _LOOP["stop"] is not None:
        _LOOP["stop"].set()
        _LOOP["wake"].set()
        if _LOOP["thread"] is not None:
            _LOOP["thread"].join(timeout=timeout)
    _LOOP.update(thread=None, stop=None)


def forget():
    """Drop what is held in memory (a test that moves the stores)."""
    with _LOCK:
        _DOCS.clear()
        _CAPS.clear()
        _HERE.clear()


# ------------------------------------------------------------------ the activity list
def activity_entries(entry, keep, now=None):
    """The jobs, in lib/activity.py's shape: kind `job`; running while open,
    finished (with ok) for `keep` seconds after."""
    now = time.time() if now is None else now
    out = []
    for j in jobs():
        if j["state"] not in OPEN and j["state"] != "taken" and now - (j["at"] or 0) > keep:
            continue
        if j["mine"]:
            label = "%s — %s" % (j["title"], j["say"] or _say(j))
        else:
            label = "%s, for %s" % (j["title"], j.get("asked_by_name") or j["asked_by"])
        running = j["state"] in OPEN if j["mine"] else j["state"] == "taken"
        out.append(entry("job-%s" % j["id"], "job", label, j["at"], stage=j.get("say"),
                         page="/settings/", finished=None if running else j["at"],
                         ok=j["state"] == "done"))
    return out
