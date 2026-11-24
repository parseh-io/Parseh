# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> Devices (a0.7.0, lane E): several computers, one shelf.

    /settings/devices/                 the door: this install's name, the partners, pairing both ways,
                                       "sync now", "make this computer identical to <partner>", the two
                                       job switches, what this device holds, the questions waiting, the
                                       versions kept for a day, the diff files, the jobs
    /settings/devices/question/<id>    one question: a choice (the two versions, the two buttons, the diff
                                       of what each would discard, shown before and offered as a file
                                       after) or a deletion, single or grouped
    /settings/devices/diff/<id>        a diff file, to read (text/plain) or ?download=1

WHO MAY.  Everything that changes sync -- pairing, a partner removed, the job
switches, what is held, an answer, "make identical", a version put back --
belongs to the computer alone (lib/settingspage.py "sync.devices"): a partner
paired here brings its changes in.  Two things are open to every device let
in, because they are not settings: what a unit's page asks ("unit": is there a
question, is its build out of date), and the editors' LEASES (synclock): an
editor open on a phone holds its unit against sync exactly as one open here.

THE OTHER LANES' MODULES ARE IMPORTED LAZILY and by name: lib/syncrules.py
(lane C: questions, answers, diffs, "make identical", kept, out of date) and
lib/syncjobs.py (lane D: the switches, capabilities, the jobs).  Until they
exist the page says which part is not there yet; the tests put fakes in
sys.modules (tests/syncrules_fake.py, tests/syncjobs_fake.py).
"""
import html
import json
import os
import re
import sys
import threading

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import settingspage                                          # noqa: E402

PAGE = "/settings/devices/"
QUESTION = "/settings/devices/question/"
DIFF = "/settings/devices/diff/"
GUIDE = "/guide/site/getting-started/several-computers.html"
API = "/settings/api/devices/"
SETTING = "sync.devices"

# the routes this module answers are named in serve.py (DEVICES_MORE), as every /settings/api/ route is;
# these four are open to every device let in (lib/settingspage.py ROUTES: READ)
OPEN = ("unit", "lease-open", "lease-keep", "lease-close")

# the editors' tickets: a page names its lease before it knows the token, so that leaving at once still lets go
_TLOCK = threading.Lock()
_TICKETS = {}                     # ticket -> token
_CLOSED = set()                   # tickets closed before their open was answered

DIFF_ID = re.compile(r"^[A-Za-z0-9._-]{1,160}$")


def esc(s):
    return html.escape(str(s), quote=True)


def _module(name):
    """Lane C's or lane D's module, or None while it is not there."""
    try:
        return __import__(name)
    except ImportError:
        return None


def rules():
    return _module("syncrules")


def jobs():
    return _module("syncjobs")


def exchange():
    return _module("syncexchange")


# ---------------------------------------------------------------- what a page is about

def resolve(body):
    """The unit a page or an editor names -> uid or None.  A page that knows
    its unit says it (`unit`, the studio's pages: lib/syncpage.js reads
    data-sync-unit); the others are known by their address (`path`)."""
    import syncunits
    uid = str(body.get("unit") or "")
    if uid:
        try:
            syncunits.locate(uid)
            return uid
        except KeyError:
            return None
    path = str(body.get("path") or "")
    m = re.match(r"^/books/([^/]+)/([^/]+)/", path)
    if m:
        return _known("book:%s/%s" % m.groups())
    m = re.match(r"^/youtube/v/([A-Za-z0-9_-]+)/", path)
    if m:
        vid = m.group(1)
        root = syncunits.SHELVES.get("videos")
        try:
            for folder in sorted(os.listdir(root)):
                if os.path.isdir(os.path.join(root, folder, vid)):
                    return "video:%s/%s" % (folder, vid)
        except (OSError, TypeError):
            return None
        return None
    m = re.search(r"/deck/([^/]+)/([^/]+)(?:/|$)", path)
    if m:
        return _known("deck:%s/%s" % m.groups())
    return None


def _known(uid):
    import syncunits
    try:
        syncunits.locate(uid)
        return uid
    except KeyError:
        return None


def unit_at(folder):
    """The unit a folder IS (a studio document, a note) -> uid or "" -- for a
    page the server writes its unit into (data-sync-unit)."""
    try:
        import syncunits
        folder = os.path.abspath(str(folder))
        for u in syncunits.units_for(folder):
            if os.path.abspath(u.where) == folder and u.kind in ("doc", "note", "book", "video", "deck"):
                return u.id
    except Exception:                       # noqa: BLE001 -- a page never fails over its unit
        return ""
    return ""


def title_of(uid):
    """A unit's id in words, when nobody gave a title."""
    kind, _, name = str(uid).partition(":")
    words = {"book": "book", "video": "video", "doc": "document", "note": "note", "deck": "deck",
             "item": "exercise", "setting": "setting", "prompt": "prompt", "latextheme": "LaTeX theme",
             "language": "language", "ankideck": "Anki deck"}.get(kind, kind)
    return "%s %s" % (words, name.rsplit("/", 1)[-1] if name else "")


# ---------------------------------------------------------------- the routes

def _partners():
    try:
        import syncpeer
        return syncpeer.partners()
    except Exception:                       # noqa: BLE001
        return []


def _names():
    return {p["id"]: p["name"] for p in _partners()}


def _languages():
    try:
        import languages
        return [{"folder": L.folder, "name": getattr(L, "name", L.folder)}
                for L in sorted(languages.LANGS.values(), key=lambda L: L.folder)]
    except Exception:                       # noqa: BLE001
        return []


def _holds_nothing():
    """A computer that holds no book, video, document or deck yet: "make
    identical" is its first sync."""
    try:
        import syncunits
        return not any(u.kind in ("book", "video", "doc", "deck", "item", "note") for u in syncunits.walk())
    except Exception:                       # noqa: BLE001
        return False


def overview():
    C, D, B = rules(), jobs(), exchange()
    names = _names()
    out = {"ok": True, "missing": [n for n, m in (("syncrules", C), ("syncjobs", D), ("syncexchange", B))
                                   if m is None],
           "languages": _languages(), "holds_nothing": _holds_nothing()}
    if D:
        out["switches"] = D.switches()
        out["capabilities"] = D.capabilities()
        out["jobs"] = D.jobs()
    if B:
        out["holding"] = B.holding()
        out["status"] = B.status()
        out["elsewhere"] = [dict(e, title=title_of(e["unit"]),
                                 partners=[{"id": p, "name": names.get(p, p[:8])} for p in e.get("partners", [])])
                            for e in B.elsewhere()]
    if C:
        out["questions"] = C.questions()
        out["kept"] = C.kept()
        out["diffs"] = C.diffs()
        out["out_of_date"] = C.out_of_date()
    else:
        try:
            import synckeep
            out["kept"] = [{"id": e.get("id"), "unit": e.get("unit"), "title": title_of(e.get("unit")),
                            "why": e.get("why"), "partner": e.get("partner"), "at": e.get("at"),
                            "until": e.get("until")} for e in synckeep.entries()]
        except Exception:                   # noqa: BLE001
            pass
    return out


def find_question(qid):
    C = rules()
    if not C:
        return None
    return next((q for q in C.questions() if str(q.get("id")) == str(qid)), None)


class Refused(Exception):
    def __init__(self, code, error):
        self.code, self.error = code, error
        super().__init__(error)


def _need(mod, lane):
    if mod is None:
        raise Refused(503, "This part of sync (%s) is not in this version yet." % lane)
    return mod


def api(what, body, where=""):
    """One route of ROUTES -> (status, answer).  The gate (settingspage.may_post) was asked before."""
    try:
        return 200, dict(_api(what, body or {}, where), ok=True)
    except Refused as e:
        return e.code, {"ok": False, "error": e.error}
    except (ValueError, KeyError) as e:
        return 400, {"ok": False, "error": str(e).strip("'\"") or "That could not be done."}


def _api(what, body, where):
    if what == "overview":
        return overview()
    if what == "sync-now":
        B = _need(exchange(), "the exchange")
        B.sync_now(body.get("partner") or None)
        return {"status": B.status()}
    if what == "identical-summary":
        C = _need(rules(), "the rules")
        return {"summary": C.identical_summary(_partner(body))}
    if what == "make-identical":
        C = _need(rules(), "the rules")
        return C.make_identical(_partner(body))
    if what == "switches":
        D = _need(jobs(), "the jobs")
        kw = {k: bool(body[k]) for k in ("send", "accept") if k in body}
        D.set_switches(**kw)
        return {"switches": D.switches()}
    if what == "holding":
        B = _need(exchange(), "the exchange")
        langs = body.get("languages")
        units = body.get("units")
        B.set_holding(languages=langs if isinstance(langs, list) else None,
                      units=units if isinstance(units, list) else None)
        return {"holding": B.holding()}
    if what == "fetch":
        B = _need(exchange(), "the exchange")
        return {"summary": B.fetch(str(body["unit"]), _partner(body))}
    if what == "answer":
        C = _need(rules(), "the rules")
        qid = str(body.get("id") or "")
        q = find_question(qid)
        if q is None:
            raise Refused(404, "That question was answered already, or is no longer asked.")
        choice = str(body.get("choice") or "")
        allowed = {"choice": ("mine", "theirs"), "deletion": ("delete", "restore"),
                   "deletion-edited": ("send-edited", "delete")}.get(q.get("kind"), ())
        if choice not in allowed:
            raise ValueError("The answer must be one of: %s." % ", ".join(allowed))
        units = body.get("units")
        if isinstance(units, list) and units:
            # "go through them": one unit of a grouped deletion at a time.  lib/syncrules.py answers ONE unit per
            # call (answer(qid, choice, unit=...)), so a list is answered unit by unit; the last answer is the
            # page's, and the first that fails stops there and is the one reported
            r = None
            for u in units:
                r = C.answer(qid, choice, unit=str(u))
                if not (r or {}).get("ok", True):
                    break
        else:
            r = C.answer(qid, choice)
        return {"result": r, "diff_id": (r or {}).get("diff_id")}
    if what == "put-back":
        C = _need(rules(), "the rules")
        return {"result": C.put_back(str(body["id"]))}
    if what == "diff-delete":
        C = _need(rules(), "the rules")
        did = str(body["id"])
        if not DIFF_ID.match(did):
            raise ValueError("No such diff file.")
        C.delete_diff(did)
        return {"deleted": did}
    if what == "job-cancel":
        D = _need(jobs(), "the jobs")
        return {"result": D.cancel(str(body["id"]))}
    if what == "unit":
        uid = resolve(body)
        out = {"unit": uid, "question": None, "out_of_date": False, "what": ""}
        C = rules()
        if uid and C:
            q = C.question_for(uid)
            if q:
                out["question"] = {"id": q["id"], "kind": q["kind"],
                                   "partner_name": q.get("partner_name") or q.get("partner"),
                                   "count": len(q.get("units") or []),
                                   "page": QUESTION + str(q["id"])}
            if C.is_out_of_date(uid):
                out["out_of_date"] = True
                out["what"] = next((o.get("what", "") for o in C.out_of_date() if o.get("unit") == uid), "")
        out["may_answer"] = settingspage.may(SETTING, where)
        if uid:
            import synclock
            out["editing"] = len(synclock.editing(uid))     # how many editors hold it now (not who)
        return out
    if what == "lease-open":
        import synclock
        uid = resolve(body)
        if not uid:
            return {"token": None, "unit": None}
        ticket = str(body.get("ticket") or "")[:64]
        try:
            tok = synclock.open_editor(uid, str(body.get("holder") or "editor"))
        except synclock.Busy as e:
            raise Refused(409, "Sync is writing this just now; it opens in a moment.") from e
        with _TLOCK:
            if ticket and ticket in _CLOSED:
                # the page was left before this answer could reach it: its close came first
                _CLOSED.discard(ticket)
                synclock.close_editor(tok)
                return {"token": None, "unit": uid}
            if ticket:
                _TICKETS[ticket] = tok
                while len(_TICKETS) > 500:
                    _TICKETS.pop(next(iter(_TICKETS)))
        return {"token": tok, "unit": uid, "lease": synclock.LEASE}
    if what == "lease-keep":
        import synclock
        return {"kept": bool(body.get("token")) and synclock.keep(str(body["token"]))}
    if what == "lease-close":
        import synclock
        # A PAGE LEFT WHILE ITS LEASE WAS ON ITS WAY knows only the ticket it sent, not the token: the ticket closes
        # it, and a close that comes before its own open is remembered, so the open lets go at once
        tok, ticket = str(body.get("token") or ""), str(body.get("ticket") or "")[:64]
        with _TLOCK:
            if ticket:
                tok = _TICKETS.pop(ticket, None) or tok
                if not tok:
                    _CLOSED.add(ticket)
                    while len(_CLOSED) > 500:
                        _CLOSED.pop()
        return {"closed": bool(tok) and synclock.close_editor(tok) is not None}
    raise Refused(404, "No such route.")


def _partner(body):
    pid = str(body.get("partner") or "")
    if pid not in _names():
        raise ValueError("No partner with that id is paired here.")
    return pid


def diff_file(did):
    """(path, name) of a diff file, or None."""
    C = rules()
    if not C or not DIFF_ID.match(did or ""):
        return None
    path = C.diff_path(did)
    if not path or not os.path.isfile(path):
        return None
    return path, os.path.basename(path)


# ---------------------------------------------------------------- the pages

def page(where=""):
    may = settingspage.may(SETTING, where)
    lock = settingspage.lockline(SETTING, where, "Sync is set up on the computer only.")
    main = """<main class="settings dv-page" data-may="%(may)s">
%(doors)s
<h1 class="idx">devices</h1>
<p class="whomay">%(gate)s <span>Paired computers keep one shelf between them. Pairing, the answers and what
this computer holds are set on the computer %(name)s runs on.</span></p>
%(lock)s
<div class="dv-say" data-say role="status"></div>
<div data-first hidden></div>

<section id="this"><h2>This computer</h2>
<p class="why">The name partners see. <span data-this-fp class="addr"></span></p>
<div class="actions"><input type="text" data-name maxlength="60" aria-label="this computer's name">
<button type="button" class="plain" data-rename>Rename</button></div>
<div data-copied class="dv-sum" role="alert" hidden></div>
<div class="actions"><button type="button" class="plain" data-new-identity>This is a copy of another computer: give it
its own identity</button></div>
<div data-new-identity-confirm class="dv-sum" hidden>
<p><b>Give this computer its own identity?</b></p>
<p>A Parseh folder copied from another computer carries that computer&rsquo;s identity, so partners cannot tell the
two apart. This makes a new identity here: a new install id and a new key. The name stays.</p>
<p>The list of partners is emptied: those partners were paired with the computer this was copied from. They know its
key, not the new one, and would refuse this computer. They are not told anything, because the original computer
still syncs with them. Pair this computer with each of them again.</p>
<p>The history of changes stays. The computer this was copied from is not changed.</p>
<div class="actions"><button type="button" class="danger" data-new-identity-go>Give it its own identity</button>
<button type="button" class="plain" data-new-identity-cancel>Cancel</button></div>
</div>
</section>

<section id="partners"><h2>Partners</h2>
<p class="why">Each paired computer, whether it answers now, when you last synced with it and what it holds that
this one leaves out. Sync runs by itself when both are on; &ldquo;Sync now&rdquo; asks for it at once.</p>
<div data-partners></div>
<div data-identical hidden></div>
<div class="actions"><button type="button" class="plain" data-sync-all>Sync now with every partner</button></div>
</section>

<section id="pair"><h2>Pair a computer</h2>
<p class="why">On one computer show a code; on the other type it, with the address shown beside it. The code
lasts fifteen minutes and is used once.</p>
<div class="actions"><button type="button" class="go" data-pair-start>Show a code</button>
<button type="button" class="plain" data-pair-stop hidden>Throw the code away</button></div>
<div data-offer hidden></div>
<h3>Type a code shown on another computer</h3>
<div class="dv-enter">
<label class="fld"><span>The code</span><input type="text" data-enter-code autocomplete="off" placeholder="KP4-R7M"></label>
<label class="fld"><span>Its address</span><input type="text" data-enter-address autocomplete="off" placeholder="192.168.1.20:7654"></label>
<label class="fld"><span>Its fingerprint (optional)</span><input type="text" data-enter-fp autocomplete="off"></label>
<button type="button" class="go" data-pair-enter>Pair</button></div>
</section>

<section id="questions"><h2>Questions waiting</h2>
<p class="why">A thing changed on both computers since they last agreed, or deleted on one: sync waits for that
one thing until you answer, and the rest syncs on. Asked once, answered for both.</p>
<div data-questions></div>
</section>

<section id="jobs"><h2>Jobs</h2>
<p class="why">Heavy work &mdash; transcribing, building a book, estimating times &mdash; one computer can lend
another. Both switches are off until you turn them on; a computer with both off still syncs.</p>
<label class="door"><input type="checkbox" data-switch="send"> <b>Send heavy jobs to paired computers</b>
<span class="said">A job this computer cannot do, or does slowly, goes to a partner that says it can.</span></label>
<label class="door"><input type="checkbox" data-switch="accept"> <b>Accept jobs from paired devices</b>
<span class="said">A partner's job runs here; the result goes back through sync.</span></label>
<p class="dv-cap" data-cap></p>
<div data-jobs></div>
</section>

<section id="holding"><h2>What this computer holds</h2>
<p class="why">Everything, unless you leave something out. Leaving a language out deletes nothing here: it stops
this computer from taking it. A thing left out shows as &ldquo;on &lt;partner&gt;&rdquo;, with a button to fetch it.</p>
<div data-langs class="dv-langs"></div>
<div data-leftout></div>
<div data-elsewhere></div>
</section>

<section id="kept"><h2>Kept for a day</h2>
<p class="why">Every version a sync replaced or deleted here stays for one day. Put one back and it becomes this
computer's change, which then syncs like any other.</p>
<div data-kept></div>
</section>

<section id="diffs"><h2>Diff files</h2>
<p class="why">What a choice threw away, as git would show it. They stay until you delete them.</p>
<div data-diffs></div>
</section>

<section id="outofdate" data-ood-section hidden><h2>Out of date</h2>
<p class="why">Builds whose source changed through sync. Nothing rebuilds on its own: rebuild from the thing's page.</p>
<div data-ood></div>
</section>

<p class="foot">Kept in <code>config/sync/</code> on this computer. <a href="%(guide)s">Several computers, one
shelf</a>, in the guide &mdash; and sync is not a backup.</p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "gate": settingspage.gate(settingspage.door_keys(PAGE)),
              "name": settingspage.NAME, "lock": lock, "guide": esc(GUIDE), "may": "1" if may else "0"}
    return settingspage.frame("Devices &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; devices', "Devices", GUIDE, main,
                              style=STYLE, script="<script>%s</script>" % SCRIPT.replace(
                                  "__API__", json.dumps(API)).replace("__QUESTION__", json.dumps(QUESTION))
                              .replace("__DIFF__", json.dumps(DIFF)))


def question_page(qid, where=""):
    """The choice page, or a deletion's.  None when there is no such question."""
    q = find_question(qid)
    may = settingspage.may(SETTING, where)
    lock = settingspage.lockline(SETTING, where, "Questions are answered on the computer only.")
    if q is None:
        body = ('<p class="why" data-gone>That question was answered already, or is no longer asked. '
                '<a href="%s#questions">Settings &rarr; Devices</a> lists those still waiting.</p>' % PAGE)
        data = None
    else:
        body = '<div data-question></div>'
        data = q
    partner = (q or {}).get("partner_name") or (q or {}).get("partner") or "the partner"
    main = """<main class="settings dv-page dv-q" data-may="%(may)s">
<p><a href="%(page)s#questions">&larr; Settings &rarr; Devices</a></p>
<h1 class="idx">%(h1)s</h1>
%(lock)s
<div class="dv-say" data-say role="status"></div>
%(body)s
<p class="foot"><a href="%(guide)s#the-choice">The choice and its diff</a>, in the guide.</p>
</main>""" % {"may": "1" if may else "0", "page": PAGE, "lock": lock, "body": body, "guide": esc(GUIDE),
              "h1": esc("a question from %s" % partner)}
    script = "<script>window.PARSEH_QUESTION = %s;</script><script>%s</script>" % (
        settingspage._in_script(data), SCRIPT.replace("__API__", json.dumps(API))
        .replace("__QUESTION__", json.dumps(QUESTION)).replace("__DIFF__", json.dumps(DIFF)))
    return settingspage.frame("A question from %s &mdash; %s" % (esc(partner), settingspage.NAME),
                              '<a href="/settings/">settings</a> &middot; <a href="%s">devices</a> &middot; question'
                              % PAGE, "Question", GUIDE, main, style=STYLE, script=script)


STYLE = r"""
.dv-page .whomay{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap;margin:.2rem 0 1rem;font-size:13.5px;color:var(--dim)}
.dv-page .whomay .gate{flex:none}
.dv-page h3{font-size:15px;margin:1rem 0 .3rem}
.dv-page .dv-say:empty{display:none}
.dv-page .dv-say{border-inline-start:3px solid var(--accent);background:var(--card);padding:8px 12px;margin:0 0 12px;font-size:13.5px;border-radius:0 8px 8px 0}
.dv-page .dv-say.bad{border-color:var(--danger,#c33)}
.dv-page .dv-list{list-style:none;margin:.3rem 0;padding:0}
.dv-page .dv-list>li{display:flex;flex-wrap:wrap;gap:.4rem .8rem;align-items:center;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid var(--rule,#8883)}
.dv-page .dv-list>li .what{flex:1 1 14rem;min-width:0;overflow-wrap:anywhere}
.dv-page .dv-list>li .what small{display:block;color:var(--dim);font-size:12.5px}
.dv-page .dv-list>li .acts{display:flex;gap:.4rem;flex-wrap:wrap}
.dv-page .n{color:var(--dim);font-size:13.5px}
.dv-page .dv-enter{display:flex;flex-wrap:wrap;gap:.3rem .8rem;align-items:flex-end}
.dv-page .dv-enter .fld{flex:1 1 10rem;margin:.3rem 0}
.dv-page .dv-enter input{width:100%;box-sizing:border-box}
.dv-page .dv-offer{display:flex;flex-wrap:wrap;gap:1rem;align-items:center;margin:.8rem 0}
.dv-page .dv-offer .qr svg{width:180px;height:180px;display:block;border-radius:6px}
.dv-page .dv-langs label{display:inline-flex;gap:.3rem;align-items:center;margin:.2rem .9rem .2rem 0;font-size:14px}
.dv-page .dv-cap{font-size:13.5px;color:var(--dim)}
.dv-page .dv-sum{border:1px solid var(--accent);border-radius:8px;padding:.7rem .9rem;margin:.8rem 0;background:var(--card)}
.dv-page .dv-sum ul{margin:.3rem 0;padding-inline-start:1.2rem}
.dv-page pre.diff{max-height:22rem;overflow:auto;font:12.5px/1.45 ui-monospace,monospace;background:var(--boxbg,#8881);border:1px solid var(--rule);border-radius:6px;padding:.5rem .6rem;white-space:pre-wrap;overflow-wrap:anywhere;margin:.4rem 0}
.dv-page pre.diff .add{color:var(--ok,#287a3e)}
.dv-page pre.diff .del{color:var(--danger,#b3261e)}
.dv-page pre.diff .hunk{color:var(--dim)}
.dv-q .sides{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.dv-q .side{border:1px solid var(--rule);border-radius:10px;padding:.8rem .9rem;background:var(--card);min-width:0}
.dv-q .side h2{font-size:16px;margin:.1rem 0 .3rem}
.dv-q .side .when{color:var(--dim);font-size:13px;margin:0 0 .5rem}
.dv-q .side .go{width:100%;margin:.4rem 0}
.dv-q .units{margin:.3rem 0 .8rem;padding-inline-start:1.2rem}
.dv-q .done{border:1px solid var(--accent);border-radius:10px;padding:.8rem .9rem;margin:1rem 0}
.dv-page .foot a{color:var(--accent,#be3455);text-decoration:underline}
.dv-page [data-new-identity]{white-space:normal;text-align:start}
.dv-page .dv-list>li[data-removed-you] .what{color:var(--danger,#b3261e)}
@media (max-width:40rem){.dv-q .sides{grid-template-columns:1fr}.dv-page .dv-list>li .acts{width:100%}
.dv-page .dv-list>li .acts>*{flex:1 1 auto}.dv-page .dv-offer .qr svg{width:160px;height:160px}}
"""

SCRIPT = r"""
(function () {
  'use strict';
  var API = __API__, QUESTION = __QUESTION__, DIFF = __DIFF__;
  var main = document.querySelector('main.dv-page');
  var may = main.getAttribute('data-may') === '1';
  function $(s, r) { return (r || document).querySelector(s); }
  function el(t, cls, text) { var e = document.createElement(t); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, run, attr) {
    var b = el('button', cls || 'plain', label); b.type = 'button'; b.disabled = !may;
    if (attr) b.setAttribute(attr[0], attr[1] == null ? '' : attr[1]);
    b.addEventListener('click', function () { run(b); }); return b;
  }
  function say(text, bad) { var s = $('[data-say]'); s.textContent = text || ''; s.classList.toggle('bad', !!bad); }
  function post(route, body) {
    return fetch(API + route, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
                               body: JSON.stringify(body || {})})
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok || j.ok === false) throw new Error(j.error || ('HTTP ' + r.status)); return j; }); });
  }
  function when(t) {
    if (!t) return 'never';
    var d = new Date(typeof t === 'number' ? t * 1000 : t);
    if (isNaN(d)) return String(t);
    return d.toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'});
  }
  function diffPre(text) {
    var pre = el('pre', 'diff');
    String(text || '').split('\n').forEach(function (line, i) {
      var s = el('span', /^\+(?!\+\+)/.test(line) ? 'add' : /^-(?!--)/.test(line) ? 'del' : /^@@/.test(line) ? 'hunk' : '', line + '\n');
      pre.appendChild(s);
    });
    if (!text) pre.textContent = '(nothing)';
    return pre;
  }
  var KIND_SAID = {choice: 'changed on both computers', deletion: 'deleted on %s', 'deletion-edited': 'deleted on %s, edited here'};
  function qSaid(q) { return (KIND_SAID[q.kind] || q.kind).replace('%s', q.partner_name || q.partner); }
  function unitTitles(q) { return (q.units || []).map(function (u) { return u.title || u.unit; }); }

  /* ---------------------------------------------------------------- the choice page */
  function drawQuestion(q, box) {
    box.innerHTML = '';
    var partner = q.partner_name || q.partner;
    var names = unitTitles(q);
    if (q.kind === 'choice') {
      box.appendChild(el('p', 'why', (names[0] || 'This') + ' was changed here and on ' + partner +
        ' since they last agreed. Keep one; what the other had is given back as a diff file.'));
      var sides = el('div', 'sides');
      [['mine', 'Keep this computer’s', q.mine, 'theirs', partner + '’s changes that will be thrown away'],
       ['theirs', 'Keep ' + partner + '’s', q.theirs, 'mine', 'This computer’s changes that will be thrown away']
      ].forEach(function (s) {
        var side = el('div', 'side'); side.setAttribute('data-side', s[0]);
        side.appendChild(el('h2', '', s[0] === 'mine' ? 'This computer' : partner));
        var v = s[2] || {};
        side.appendChild(el('p', 'when', (v.summary || '') + (v.at ? ' — ' + when(v.at) : '')));
        side.appendChild(btn(s[1], 'go', function (b) { answer(q, s[0], box); }, ['data-answer', s[0]]));
        side.appendChild(el('h3', '', s[4] + ':'));
        side.appendChild(diffPre((q.discard_preview || {})[s[0]]));
        sides.appendChild(side);
      });
      box.appendChild(sides);
      return;
    }
    var many = names.length > 1;
    var deleted = q.kind === 'deletion';
    var lead = deleted
      ? (many ? names.length + ' things were deleted on ' + partner + ' and are untouched here.'
              : (names[0] || 'This') + ' was deleted on ' + partner + ' and is untouched here.')
      : (many ? names.length + ' things were deleted on ' + partner + ' and edited here.'
              : (names[0] || 'This') + ' was deleted on ' + partner + ' and edited here.');
    box.appendChild(el('p', 'why', lead + ' A deletion never travels without asking.'));
    if (many) {
      var ul = el('ul', 'units'); names.forEach(function (n) { ul.appendChild(el('li', '', n)); }); box.appendChild(ul);
    }
    var a = deleted ? ['delete', many ? 'Delete them all here too' : 'Delete it here too',
                       'restore', many ? 'Restore them all on ' + partner : 'Restore it on ' + partner]
                    : ['send-edited', many ? 'Send the edited versions everywhere' : 'Send the edited version everywhere',
                       'delete', many ? 'Delete them everywhere' : 'Delete it everywhere'];
    var row = el('div', 'actions');
    row.appendChild(btn(a[1], 'go', function () { answer(q, a[0], box); }, ['data-answer', a[0]]));
    row.appendChild(btn(a[3], 'plain', function () { answer(q, a[2], box); }, ['data-answer', a[2]]));
    if (many) row.appendChild(btn('Go through them', 'plain', function () { goThrough(q, a, box); }, ['data-through', '']));
    box.appendChild(row);
  }
  function goThrough(q, a, box) {
    box.innerHTML = '';
    box.appendChild(el('p', 'why', 'One at a time:'));
    var ul = el('ul', 'dv-list');
    (q.units || []).forEach(function (u) {
      var li = el('li'); li.setAttribute('data-unit', u.unit);
      li.appendChild(el('span', 'what', u.title || u.unit));
      var acts = el('span', 'acts');
      [[a[0], a[1].replace(/ them all| them|versions/, function (m) { return m === 'versions' ? 'version' : ''; })],
       [a[2], a[3].replace(/ them all| them/, '')]].forEach(function (o) {
        acts.appendChild(btn(o[1], 'plain', function () {
          post('answer', {id: q.id, choice: o[0], units: [u.unit]}).then(function () {
            li.innerHTML = ''; li.appendChild(el('span', 'what', (u.title || u.unit) + ' — ' + o[1].toLowerCase() + ': done.'));
          }).catch(function (e) { say(e.message, true); });
        }, ['data-answer', o[0]]));
      });
      li.appendChild(acts); ul.appendChild(li);
    });
    box.appendChild(ul);
  }
  function answer(q, choice, box) {
    Array.prototype.forEach.call(box.querySelectorAll('button'), function (b) { b.disabled = true; });
    say('Answering…');
    post('answer', {id: q.id, choice: choice}).then(function (j) {
      say('');
      box.innerHTML = '';
      var done = el('div', 'done'); done.setAttribute('data-done', choice);
      done.appendChild(el('p', '', 'Answered for both computers.'));
      if (j.diff_id) {
        done.appendChild(el('p', '', 'What was thrown away is kept as a diff file, until you delete it:'));
        var row = el('div', 'actions');
        var dl = el('a', 'go', 'Download the diff'); dl.href = DIFF + encodeURIComponent(j.diff_id) + '?download=1';
        dl.setAttribute('download', ''); dl.setAttribute('data-diff-download', j.diff_id);
        var v = el('a', 'plain', 'Read it'); v.href = DIFF + encodeURIComponent(j.diff_id); v.target = '_blank';
        row.appendChild(dl); row.appendChild(v); done.appendChild(row);
      }
      var back = el('p'); var a = el('a', '', 'Back to Settings → Devices'); a.href = '/settings/devices/#questions';
      back.appendChild(a); done.appendChild(back);
      box.appendChild(done);
      if (window.PARSEH_DEVICES_RELOAD) window.PARSEH_DEVICES_RELOAD();
    }).catch(function (e) {
      say(e.message, true);
      Array.prototype.forEach.call(box.querySelectorAll('button'), function (b) { b.disabled = !may; });
    });
  }
  if (window.PARSEH_QUESTION !== undefined) {
    var qbox = $('[data-question]');
    if (qbox && window.PARSEH_QUESTION) drawQuestion(window.PARSEH_QUESTION, qbox);
    return;
  }

  /* ---------------------------------------------------------------- Settings -> Devices */
  var names = {};
  function list(box, rows, empty, draw) {
    box.innerHTML = '';
    if (!rows || !rows.length) { box.appendChild(el('p', 'n', empty)); return; }
    var ul = el('ul', 'dv-list');
    rows.forEach(function (r) { var li = el('li'); draw(r, li); ul.appendChild(li); });
    box.appendChild(ul);
  }
  function what(li, title, small) {
    var w = el('span', 'what', title); if (small) w.appendChild(el('small', '', small)); li.appendChild(w); return w;
  }
  function acts(li) { var a = el('span', 'acts'); li.appendChild(a); return a; }

  function drawState(st) {
    var me = st.this || {};
    var n = $('[data-name]'); if (document.activeElement !== n) n.value = me.name || '';
    n.disabled = !may; $('[data-rename]').disabled = !may;
    $('[data-this-fp]').textContent = me.fingerprint ? 'Its fingerprint: ' + me.fingerprint : '';
    $('[data-new-identity]').disabled = !may;
    var cp = $('[data-copied]'); cp.innerHTML = ''; cp.hidden = !me.copied;
    if (me.copied) {
      cp.appendChild(el('p', '', 'This computer’s identity was made on ' + me.copied.made_on + ', and it now runs on ' +
        me.copied.here + ': it looks like a copy of another computer’s Parseh. Two copies with one identity cannot both ' +
        'sync. If it is a copy, give it its own identity; if it is the same computer (its system moved to a new disk, ' +
        'say), keep it.'));
      var row = el('div', 'actions');
      row.appendChild(btn('Give it its own identity…', 'go', askNewIdentity, ['data-copied-new', '']));
      row.appendChild(btn('It is the same computer', 'plain', function (b) {
        b.disabled = true;
        post('same-computer').then(function () { say('Kept: this is the same computer.'); load(); })
          .catch(function (e) { say(e.message, true); b.disabled = !may; });
      }, ['data-same-computer', '']));
      cp.appendChild(row);
    }
    names = {};
    (st.partners || []).forEach(function (p) { names[p.id] = p.name; });
    $('[data-pair-stop]').hidden = !st.pairing;
    return st;
  }
  function drawPartners(st, ov) {
    var status = (ov.status || {}).partners || {};
    var held = {};
    (ov.elsewhere || []).forEach(function (e) { (e.partners || []).forEach(function (p) { held[p.id] = (held[p.id] || 0) + 1; }); });
    list($('[data-partners]'), st.partners, 'No partner yet: pair a computer below.', function (p, li) {
      li.setAttribute('data-partner', p.id);
      var s = status[p.id] || {};
      var reach = p.reachable === true ? 'answers now' : p.reachable === false ? 'does not answer now' : 'not tried yet';
      var bits = [reach, 'last synced ' + when(s.last_ok || p.last_ok)];
      if (s.state === 'running') bits.push('syncing now');
      if (held[p.id]) bits.push('holds ' + held[p.id] + ' thing' + (held[p.id] === 1 ? '' : 's') + ' this computer leaves out');
      if (s.last_error) bits.push('last error: ' + s.last_error);
      var dv = p.device || {};
      if (dv.send_only) bits.push('send only: it never takes jobs');
      if (dv.holds_little) bits.push('holds little: it leaves things out unless asked');
      if (p.removed_you) {
        li.setAttribute('data-removed-you', '');
        bits.unshift((p.removed_you.by || p.name) + ' removed this computer on ' + when(p.removed_you.at) +
                     ': it no longer syncs with it');
      }
      what(li, p.name, bits.join(' · '));
      var a = acts(li);
      if (p.removed_you) {
        a.appendChild(btn('Remove it here too', 'danger', function (b) {
          b.disabled = true;
          post('remove', {id: p.id}).then(function () { say(p.name + ' was removed here too.'); load(); })
            .catch(function (e) { say(e.message, true); b.disabled = !may; });
        }, ['data-remove-too', p.id]));
        return;
      }
      a.appendChild(btn('Sync now', 'plain', function (b) {
        b.disabled = true; post('sync-now', {partner: p.id}).then(function () { say('Syncing with ' + p.name + '…'); setTimeout(load, 1500); })
          .catch(function (e) { say(e.message, true); }).then(function () { b.disabled = !may; });
      }, ['data-sync', p.id]));
      a.appendChild(btn('Make this computer identical to ' + p.name + '…', 'plain', function () { identical(p); }, ['data-identical-ask', p.id]));
      a.appendChild(btn('Remove', 'danger', function () {
        if (!confirm('Remove ' + p.name + '? It can no longer sync with this computer until you pair them again. ' +
                     p.name + ' is told, if it answers.')) return;
        say('Removing ' + p.name + '…');
        post('remove', {id: p.id}).then(function (j) {
          say(j.told === false ? p.name + ' was removed here, but it could not be told (' + (j.why || 'no answer') +
                                 '): it is refused from now on, and it can be removed there too.'
              : j.told ? p.name + ' was removed, and told so.' : p.name + ' was removed.', j.told === false);
          load();
        }).catch(function (e) { say(e.message, true); });
      }, ['data-remove', p.id]));
    });
    var first = $('[data-first]');
    first.innerHTML = '';
    first.hidden = !(ov.holds_nothing && (st.partners || []).length);
    if (!first.hidden) {
      var box = el('div', 'dv-sum');
      box.appendChild(el('p', '', 'This computer holds nothing yet. Its first sync can make it identical to a partner:'));
      var row = el('div', 'actions');
      st.partners.forEach(function (p) {
        row.appendChild(btn('Make it identical to ' + p.name + '…', 'go', function () { identical(p); }, ['data-first-identical', p.id]));
      });
      box.appendChild(row); first.appendChild(box);
    }
  }
  function identical(p) {
    var box = $('[data-identical]');
    box.hidden = false; box.innerHTML = ''; box.className = 'dv-sum';
    box.scrollIntoView({block: 'nearest'});
    box.appendChild(el('p', 'n', 'Working out what would change…'));
    post('identical-summary', {partner: p.id}).then(function (j) {
      var s = j.summary || {};
      box.innerHTML = '';
      box.setAttribute('data-summary', p.id);
      box.appendChild(el('h3', '', 'Make this computer identical to ' + p.name));
      box.appendChild(el('p', '', 'This computer takes ' + p.name + '’s state; ' + p.name + ' is not changed. ' +
        'Your settings here, what this computer holds and its partners stay.'));
      var ul = el('ul');
      ul.appendChild(el('li', '', (s.replace || 0) + ' replaced, ' + (s.add || 0) + ' added, ' + (s.delete || 0) + ' deleted here.'));
      if (s.questions) ul.appendChild(el('li', '', s.questions + ' question' + (s.questions === 1 ? '' : 's') + ' waiting here answered in ' + p.name + '’s favour.'));
      if ((s.jobs || []).length) ul.appendChild(el('li', '', 'Jobs cancelled: ' + s.jobs.map(function (x) { return x.title || x.id || x; }).join(', ') + '.'));
      box.appendChild(ul);
      if ((s.lost || []).length) {
        box.appendChild(el('p', '', 'This computer’s own changes that will be lost (written as one diff file, and kept for a day):'));
        var lost = el('ul'); lost.setAttribute('data-lost', '');
        s.lost.forEach(function (u) { lost.appendChild(el('li', '', u.title || u.unit)); }); box.appendChild(lost);
      } else box.appendChild(el('p', 'n', 'No change made here will be lost.'));
      var row = el('div', 'actions');
      row.appendChild(btn('Make it identical', 'go', function (b) {
        b.disabled = true; say('Making this computer identical to ' + p.name + '…');
        post('make-identical', {partner: p.id}).then(function (r) {
          box.innerHTML = '';
          box.appendChild(el('p', '', 'This computer is now identical to ' + p.name + '. What it replaced is kept for a day.'));
          if (r.diff_id) {
            var a = el('a', 'plain', 'Download the lost changes as a diff'); a.href = DIFF + encodeURIComponent(r.diff_id) + '?download=1';
            a.setAttribute('download', ''); box.appendChild(a);
          }
          say(''); load();
        }).catch(function (e) { b.disabled = false; say(e.message, true); });
      }, ['data-identical-go', p.id]));
      row.appendChild(btn('Cancel', 'plain', function () { box.hidden = true; box.innerHTML = ''; }));
      box.appendChild(row);
    }).catch(function (e) { box.hidden = true; say(e.message, true); });
  }
  function drawQuestions(ov) {
    list($('[data-questions]'), ov.questions, ov.questions ? 'Nothing is waiting for an answer.' : 'The rules of sync are not in this version yet.', function (q, li) {
      li.setAttribute('data-q', q.id);
      var names = unitTitles(q);
      what(li, names.length > 1 ? names.length + ' things ' + qSaid(q) : (names[0] || '') + ' — ' + qSaid(q),
           names.length > 1 ? names.slice(0, 6).join(', ') + (names.length > 6 ? ', …' : '') : '');
      var a = acts(li); var go = el('a', 'go', 'Answer'); go.href = QUESTION + encodeURIComponent(q.id); a.appendChild(go);
    });
  }
  var CAP = {whisper: 'Whisper', latex: 'LaTeX', aligners: 'aligners', analyzers: 'analyzers', gpu: 'a graphics card'};
  var STATE = {waiting: 'waiting', taken: 'taken', running: 'running', done: 'done', failed: 'failed', cancelled: 'cancelled', abandoned: 'abandoned'};
  function drawJobs(ov) {
    var sw = ov.switches;
    Array.prototype.forEach.call(document.querySelectorAll('[data-switch]'), function (c) {
      c.disabled = !may || !sw; if (sw) c.checked = !!sw[c.getAttribute('data-switch')];
    });
    var cap = ov.capabilities || null;
    $('[data-cap]').textContent = cap ? 'This computer can run: ' + (Object.keys(CAP).filter(function (k) { return cap[k]; })
      .map(function (k) { return CAP[k]; }).join(', ') || 'none of the heavy tools') + '.' : '';
    list($('[data-jobs]'), ov.jobs, sw ? 'No job, sent or taken.' : 'Jobs are not in this version yet.', function (j, li) {
      li.setAttribute('data-job', j.id);
      var bits = [STATE[j.state] || j.state, 'asked by ' + (j.asked_by_name || j.asked_by || 'this computer')];
      if (j.taken_by) bits.push('taken by ' + (j.taken_by_name || j.taken_by));
      if (j.reason) bits.push(j.reason);
      if (j.at) bits.push(when(j.at));
      what(li, j.title || j.kind, bits.join(' · '));
      if (['waiting', 'taken', 'running'].indexOf(j.state) >= 0)
        acts(li).appendChild(btn('Cancel', 'plain', function () {
          post('job-cancel', {id: j.id}).then(load).catch(function (e) { say(e.message, true); });
        }, ['data-cancel', j.id]));
    });
  }
  function drawHolding(ov) {
    var h = (ov.holding || {}).leave_out || {languages: [], units: []};
    var box = $('[data-langs]'); box.innerHTML = '';
    if (!ov.holding) { box.appendChild(el('p', 'n', 'What this computer holds is set once the exchange is here.')); }
    else (ov.languages || []).forEach(function (L) {
      var lab = el('label'); var c = el('input'); c.type = 'checkbox'; c.checked = h.languages.indexOf(L.folder) < 0;
      c.disabled = !may; c.setAttribute('data-hold-lang', L.folder);
      c.addEventListener('change', function () {
        var out = Array.prototype.filter.call(document.querySelectorAll('[data-hold-lang]'), function (x) { return !x.checked; })
          .map(function (x) { return x.getAttribute('data-hold-lang'); });
        post('holding', {languages: out}).then(function () { say('Kept: what this computer holds.'); load(); }).catch(function (e) { say(e.message, true); });
      });
      lab.appendChild(c); lab.appendChild(document.createTextNode(L.name)); box.appendChild(lab);
    });
    list($('[data-leftout]'), (h.units || []).map(function (u) { return {unit: u}; }), '', function (r, li) {
      what(li, 'Left out: ' + r.unit);
      acts(li).appendChild(btn('Hold it again', 'plain', function () {
        post('holding', {units: h.units.filter(function (x) { return x !== r.unit; })}).then(load).catch(function (e) { say(e.message, true); });
      }));
    });
    if (!(h.units || []).length) $('[data-leftout]').innerHTML = '';
    list($('[data-elsewhere]'), ov.elsewhere, '', function (e, li) {
      li.setAttribute('data-elsewhere', e.unit);
      what(li, e.title || e.unit, 'on ' + (e.partners || []).map(function (p) { return p.name; }).join(', '));
      var a = acts(li);
      (e.partners || []).forEach(function (p) {
        a.appendChild(btn('Fetch from ' + p.name, 'plain', function (b) {
          b.disabled = true; say('Fetching ' + (e.title || e.unit) + ' from ' + p.name + '…');
          post('fetch', {unit: e.unit, partner: p.id}).then(function () { say('Fetched; it is held here from now on.'); load(); })
            .catch(function (x) { b.disabled = false; say(x.message, true); });
        }, ['data-fetch', e.unit]));
      });
    });
    if (!(ov.elsewhere || []).length) $('[data-elsewhere]').innerHTML = '';
  }
  var WHY = {incoming: 'replaced by a change from', choice: 'not kept in a choice with', deletion: 'deleted, answering', identical: 'replaced making this identical to'};
  function drawKept(ov) {
    list($('[data-kept]'), ov.kept, 'Nothing was replaced in the last day.', function (k, li) {
      li.setAttribute('data-kept', k.id);
      what(li, k.title || k.unit, (WHY[k.why] || k.why || '') + (k.partner ? ' ' + (names[k.partner] || k.partner) : '') +
           ' · ' + when(k.at) + (k.until ? ' · kept until ' + when(k.until) : ''));
      acts(li).appendChild(btn('Put back', 'plain', function (b) {
        b.disabled = true;
        post('put-back', {id: k.id}).then(function () { say((k.title || k.unit) + ' is back, as this computer’s change.'); load(); })
          .catch(function (e) { b.disabled = false; say(e.message, true); });
      }, ['data-put-back', k.id]));
    });
  }
  function drawDiffs(ov) {
    list($('[data-diffs]'), ov.diffs, 'No diff file.', function (d, li) {
      li.setAttribute('data-diff', d.id);
      what(li, d.title || d.unit || d.id, when(d.at) + (d.size != null ? ' · ' + d.size + ' bytes' : ''));
      var a = acts(li);
      var v = el('a', 'plain', 'Read'); v.href = DIFF + encodeURIComponent(d.id); v.target = '_blank'; a.appendChild(v);
      var dl = el('a', 'plain', 'Download'); dl.href = DIFF + encodeURIComponent(d.id) + '?download=1'; dl.setAttribute('download', ''); a.appendChild(dl);
      a.appendChild(btn('Delete', 'danger', function () {
        post('diff-delete', {id: d.id}).then(load).catch(function (e) { say(e.message, true); });
      }, ['data-diff-delete', d.id]));
    });
  }
  function drawOod(ov) {
    var rows = ov.out_of_date || [];
    $('[data-ood-section]').hidden = !rows.length;
    list($('[data-ood]'), rows, '', function (o, li) { what(li, o.title || o.unit, o.what || 'built from an older source'); });
  }
  function load() {
    if (!may) { say('Sync is set up on the computer itself.'); return Promise.resolve(); }
    return Promise.all([post('state'), post('overview')]).then(function (r) {
      var st = drawState(r[0]), ov = r[1];
      drawPartners(st, ov); drawQuestions(ov); drawJobs(ov); drawHolding(ov); drawKept(ov); drawDiffs(ov); drawOod(ov);
      main.setAttribute('data-loaded', String(Date.now()));
    }).catch(function (e) { say(e.message, true); });
  }
  window.PARSEH_DEVICES_RELOAD = load;
  function askNewIdentity() {
    var c = $('[data-new-identity-confirm]'); c.hidden = false;
    c.scrollIntoView({block: 'nearest'});
    $('[data-new-identity-go]').disabled = !may;
  }
  $('[data-new-identity]').disabled = !may;
  $('[data-new-identity]').addEventListener('click', askNewIdentity);
  $('[data-new-identity-cancel]').addEventListener('click', function () { $('[data-new-identity-confirm]').hidden = true; });
  $('[data-new-identity-go]').addEventListener('click', function () {
    var b = $('[data-new-identity-go]'); b.disabled = true;
    post('new-identity').then(function (j) {
      $('[data-new-identity-confirm]').hidden = true;
      say('This computer has its own identity now' + (j.forgot ? '; the ' + j.forgot + ' partner' +
          (j.forgot === 1 ? ' was' : 's were') + ' taken off the list: pair them again.' : '.'));
      load();
    }).catch(function (e) { say(e.message, true); }).then(function () { b.disabled = !may; });
  });
  $('[data-rename]').addEventListener('click', function () {
    post('rename', {name: $('[data-name]').value}).then(function (j) { say('This computer is called ' + j.name + '.'); load(); })
      .catch(function (e) { say(e.message, true); });
  });
  $('[data-sync-all]').disabled = !may;
  $('[data-sync-all]').addEventListener('click', function () {
    post('sync-now', {}).then(function () { say('Syncing with every partner…'); setTimeout(load, 1500); }).catch(function (e) { say(e.message, true); });
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-switch]'), function (c) {
    c.addEventListener('change', function () {
      var b = {}; b[c.getAttribute('data-switch')] = c.checked;
      post('switches', b).then(function () { say('Kept.'); }).catch(function (e) { c.checked = !c.checked; say(e.message, true); });
    });
  });
  var tick = null;
  function drawOffer(o) {
    var box = $('[data-offer]'); box.hidden = false; box.innerHTML = '';
    var wrap = el('div', 'dv-offer');
    if (o.qr_svg) { var q = el('div', 'qr'); q.innerHTML = o.qr_svg; wrap.appendChild(q); }
    var t = el('div');
    t.appendChild(el('div', 'code', o.said || o.code)).setAttribute('data-code', '');
    var left = el('p', 'left'); t.appendChild(left);
    t.appendChild(el('p', '', 'Type it on the other computer, with one of these addresses:'));
    var ul = el('ul'); (o.addresses || []).forEach(function (a) { ul.appendChild(el('li', 'addr', a)); }); t.appendChild(ul);
    if (o.fingerprint) t.appendChild(el('p', 'n', 'This computer’s fingerprint: ' + o.fingerprint));
    wrap.appendChild(t); box.appendChild(wrap);
    var ends = Date.now() + (o.left || 0) * 1000;
    clearInterval(tick);
    function show() {
      var s = Math.max(0, Math.round((ends - Date.now()) / 1000));
      left.textContent = s ? 'Lasts ' + Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2) + ' more.' : 'The code ran out.';
      if (!s) { clearInterval(tick); load(); }
    }
    show(); tick = setInterval(show, 1000);
    $('[data-pair-stop]').hidden = false;
  }
  $('[data-pair-start]').disabled = !may;
  $('[data-pair-start]').addEventListener('click', function () {
    post('pair-start').then(drawOffer).catch(function (e) { say(e.message, true); });
  });
  $('[data-pair-stop]').addEventListener('click', function () {
    post('pair-stop').then(function () { clearInterval(tick); $('[data-offer]').hidden = true; $('[data-pair-stop]').hidden = true; say('The code was thrown away.'); })
      .catch(function (e) { say(e.message, true); });
  });
  $('[data-pair-enter]').disabled = !may;
  $('[data-pair-enter]').addEventListener('click', function () {
    var b = $('[data-pair-enter]'); b.disabled = true; say('Pairing…');
    post('pair-enter', {code: $('[data-enter-code]').value.trim(), address: $('[data-enter-address]').value.trim(),
                        fingerprint: $('[data-enter-fp]').value.trim()})
      .then(function (j) { say('Paired with ' + ((j.partner || {}).name || 'the other computer') + '.'); $('[data-enter-code]').value = ''; load(); })
      .catch(function (e) { say(e.message, true); }).then(function () { b.disabled = !may; });
  });
  load();
  setInterval(function () { if (!document.hidden) load(); }, 30000);
})();
"""
