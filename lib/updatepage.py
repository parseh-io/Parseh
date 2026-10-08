# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings > Updating Parseh: the page (TO-DO §13.16; lib/updater.py does
the work, serve.py answers the routes).

ONE PAGE FOR BOTH ROADS IN.  A version arrives either from GitHub -- "Check
now", or the daily look somebody ticked -- or as a zip the person chose:
the release's own download, or one built on this computer with
lib/release.py.  Either way it becomes THE CANDIDATE, and the page then says
everything installing it would do before anything is done: which way it
goes, the files it would replace, add and delete, the ones changed by hand
that it would overwrite (kept in the backup), what the environment needs,
and what may not survive a step back.  Only then the button -- worded by
the direction, because "update" is the wrong word for going back -- and a
plain question under it.

WHILE IT RUNS, THE SERVER IS DOWN.  The page polls one address,
/settings/api/update/state, which the server answers before, the helper
while it works, and the new server after: each step with its mark and its
words, the files counted, and at the end the page loads itself again on the
new version, where the report of what was done stands at the top, with the
way back to the page the person came from.

A PHONE SEES IT AND IS TOLD WHY IT CANNOT START IT.  An update changes what
Parseh will run, so it is started on the computer Parseh runs on
(lib/settingspage.py SETTINGS, "parseh.update"); a device let in over the
network reads the page with a lock and that sentence where the buttons
would be -- never a dead button.  Asking GitHub what is newest changes
nothing, and is open to it ("parseh.check").
"""
import time

import settingspage

NAME = settingspage.NAME
esc = settingspage.esc

STYLE = """
.upd .row{display:flex;gap:10px 16px;align-items:center;flex-wrap:wrap}
.upd .row .sp{flex:1}
.upd .dir{display:inline-flex;align-items:center;gap:5px;font-size:12.5px;line-height:1.2;
  padding:2px 10px 2px 8px;border-radius:20px;border:1px solid currentColor;white-space:nowrap;
  background:color-mix(in srgb,currentColor 9%,transparent)}
.upd .dir i{font-style:normal;font-weight:700}
.upd .dir.newer{color:var(--ok)}
.upd .dir.older{color:var(--warn)}
.upd .dir.same{color:var(--dim)}
.upd .vers{font-size:20px;font-weight:600;letter-spacing:.01em}
.upd .vers .arrow{color:var(--faint);font-weight:400;margin:0 .35em}
.upd .facts{margin:.6rem 0;padding-left:1.2rem}
.upd .facts li{margin:.2rem 0}
.upd .paths{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;margin:.3rem 0 .2rem;
  padding-left:1.2rem;max-height:14rem;overflow:auto}
.upd details{margin:.4rem 0}
.upd details summary{cursor:pointer}
.upd .back{border-inline-start:3px solid var(--warn);background:var(--boxbg);padding:10px 12px;
  border-radius:0 8px 8px 0;margin:.7rem 0}
.upd .back.danger{border-color:var(--danger)}
.upd .insist{display:flex;gap:8px;align-items:flex-start;margin:.6rem 0;font-weight:600}
.upd .confirm{background:var(--boxbg);border:1px solid var(--rule);border-radius:8px;
  padding:10px 12px;margin-top:.8rem}
.upd button.go.older{background:var(--warn);border-color:var(--warn)}
.upd .bar{height:6px;background:var(--rule);border-radius:3px;overflow:hidden;margin:8px 0;
  max-width:32rem}
.upd .bar i{display:block;height:100%;background:var(--accent);border-radius:3px;
  transition:width .4s}
.upd .bar.loose i{width:30%;animation:upd-slide 1.4s ease-in-out infinite}
@keyframes upd-slide{0%{margin-inline-start:-30%}100%{margin-inline-start:100%}}
.upd ol.steps{list-style:none;padding:0;margin:.6rem 0}
.upd ol.steps li{display:grid;grid-template-columns:1.6rem minmax(0,1fr);gap:2px 6px;
  padding:3px 0;font-size:14px}
.upd ol.steps li .m{font-weight:700;text-align:center}
.upd ol.steps li .d{grid-column:2;font-size:12.5px;color:var(--dim);overflow-wrap:anywhere}
.upd ol.steps li.waiting{color:var(--faint)}
.upd ol.steps li.running{color:var(--accent);font-weight:600}
.upd ol.steps li.done .m{color:var(--ok)}
.upd ol.steps li.failed .m,.upd ol.steps li.failed{color:var(--danger)}
.upd .said{min-height:1.3rem;margin:.5rem 0}
.upd .said.bad{color:var(--danger)}
.upd .tech{display:block;font-family:ui-monospace,Menlo,monospace;font-size:11.5px;line-height:1.45;
  color:var(--faint);font-weight:400;margin:.25rem 0 .5rem;overflow-wrap:anywhere}
.upd .said .tech{margin:.2rem 0 0}
.upd .notes{white-space:pre-wrap;font-size:13px;background:var(--boxbg);border:1px solid var(--rule);
  border-radius:8px;padding:8px 10px;max-height:18rem;overflow:auto}
.upd .src{color:var(--dim);font-size:13px}
.upd .src code{font-size:12px}
.upd .report.ok{border-color:var(--ok)}
.upd .report.bad{border-color:var(--danger)}
.upd .foot{color:var(--faint);font-size:12.5px;line-height:1.7;margin-top:22px}
.upd .foot a{color:var(--dim)}
.upd input[type=file]{font:inherit;font-size:13px;max-width:100%}
.upd code{font-size:12.5px;overflow-wrap:anywhere}
@media (max-width:620px){.upd .vers{font-size:17px}}
"""

DIR = {"newer": ("&#8593;", "newer"), "older": ("&#8595;", "older &mdash; going back"),
       "same": ("=", "the same version")}


def _dir(d):
    glyph, word = DIR.get(d, ("?", d))
    return '<span class="dir %s"><i aria-hidden="true">%s</i>%s</span>' % (esc(d), glyph, word)


def go_label(d, target):
    """The button's words, from the direction: going back is never
    "Update"."""
    return {"newer": "Update to %s" % target, "older": "Go back to %s" % target,
            "same": "Install %s again" % target}.get(d, "Install %s" % target)


def _when(iso):
    """2026-09-25T03:08:18Z -> 25 September 2026."""
    try:
        return time.strftime("%d %B %Y", time.strptime(str(iso)[:10], "%Y-%m-%d")).lstrip("0")
    except (ValueError, TypeError):
        return ""


def _tech(detail):
    """Python's own line behind a failure said in words (updater.plainly):
    beneath the words, smaller, for whoever mends Parseh."""
    return '<span class="tech">%s</span>' % esc(detail) if detail else ""


KEPT = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def _kept_jobs():
    try:
        import updater
        return KEPT.get(updater.KEEP_JOBS, str(updater.KEEP_JOBS))
    except ImportError:
        return "three"


def _by_whom(rows):
    """[[path, version, ...]] -> "path (the update to version took it)"
    lines, for the lists of the person's own files."""
    return ["%s (replaced by the update to %s)" % (r[0], r[1]) if len(r) > 1 and r[1] else r[0]
            for r in rows or [] if r]


def _paths(title, paths, open_=False, limit=400):
    if not paths:
        return ""
    items = "".join("<li>%s</li>" % esc(p) for p in paths[:limit])
    more = "<li>&hellip; and %d more</li>" % (len(paths) - limit) if len(paths) > limit else ""
    return ('<details%s><summary>%s (%d)</summary><ul class="paths">%s%s</ul></details>'
            % (" open" if open_ or len(paths) <= 6 else "", title, len(paths), items, more))


def _installed_line(p):
    inst = p.get("installed") or {}
    v = inst.get("version") or "?"
    if p.get("refused") and not inst.get("commit"):
        return 'This is %s <b>%s</b>.' % (NAME, esc(v))
    bits = []
    if inst.get("built"):
        bits.append("built %s" % _when(inst["built"]))
    if inst.get("commit"):
        bits.append("from commit <code>%s</code>" % esc(inst["commit"][:12]))
    return 'This is %s <b>%s</b>, installed from a release%s.' % (
        NAME, esc(v), (" (" + ", ".join(bits) + ")") if bits else "")


def _latest_section(s, p, may_check, may_update, fetching):
    """The newest release on GitHub: what the last look found, Check now,
    and the daily look."""
    latest = s.get("latest") or {}
    inst_v = (p.get("installed") or {}).get("version")
    lines = []
    if s.get("error"):
        lines.append('<p class="said bad">%s%s</p>' % (esc(s["error"]), _tech(s.get("detail"))))
    if latest.get("version") and inst_v:
        try:
            import updater
            d = updater.direction_of(inst_v, latest["version"])
        except (ValueError, ImportError):
            d = ""
        verb = {"newer": "It is newer than this %s." % NAME,
                "older": "It is OLDER than this %s: this %s is ahead of what is published."
                         % (NAME, NAME),
                "same": "It is the version this %s already is." % NAME}.get(d, "")
        pub = _when(latest.get("published"))
        lines.append('<p>The newest release is <b>%s</b>%s. %s %s</p>'
                     % (esc(latest["version"]), (", published " + esc(pub)) if pub else "",
                        _dir(d) if d else "", verb))
        if latest.get("notes"):
            lines.append('<details><summary>What %s says about itself</summary>'
                         '<div class="notes">%s</div></details>'
                         % (esc(latest["version"]), esc(latest["notes"])))
        if may_update and not p.get("refused"):
            cand = p.get("candidate") or {}
            if cand.get("version") == latest["version"] and cand.get("source") == "github":
                lines.append('<p class="src">Downloaded and checked: it is below, ready.</p>')
            else:
                lines.append('<div class="row"><button type="button" class="go" data-get>'
                             'Download %s (%s)</button><span class="src" data-get-said>'
                             'checked against the SHA-256 published beside it</span></div>'
                             % (esc(latest["version"]), esc(_size(latest.get("size")))))
                lines.append('<div data-fetch%s><div class="bar loose" data-fetch-bar><i></i></div>'
                             '<div class="row"><span class="src" data-fetch-said></span><span '
                             'class="sp"></span><button type="button" class="plain" data-stop-get>'
                             'Stop</button></div></div>' % ("" if fetching else " hidden"))
    elif not s.get("error"):
        lines.append('<p>Nobody has asked GitHub yet.</p>')
    checked = settingspage.when(s["checked"]) if s.get("checked") else ""
    return """<section>
  <h2>The newest release</h2>
  <p class="why">%(name)s asks GitHub which release of %(name)s is newest. It sends nothing about you:
  one question, with %(name)s's name and version on it.%(checked)s</p>
  %(lines)s
  <div class="row">
    %(button)s
    <label class="door" style="margin:0"><input type="checkbox" data-daily%(daily)s%(shut)s>
    <b>Look once a day</b></label>
  </div>
  <p class="said" data-check-said></p>
</section>""" % {
        "name": NAME, "lines": "".join(lines),
        "checked": (" The last look was %s." % esc(checked)) if checked else "",
        "button": ('<button type="button" class="plain" data-check>Check now</button>'
                   if may_check else ""),
        "daily": " checked" if s.get("daily") else "", "shut": "" if may_check else " disabled",
    }


def _size(n):
    try:
        import updater
        return updater.size_said(n)
    except ImportError:
        return "?"


def _zip_section(may_update):
    if not may_update:
        return ""
    return """<section>
  <h2>A zip of your own</h2>
  <p class="why">A release's zip, <code>parseh-&lt;version&gt;.zip</code>: downloaded from the
  releases page (a draft's too, once you are signed in there), or built on this computer
  from a commit. Nothing is installed yet: %(name)s checks it, and says below what installing
  it would do.</p>
  <div class="row"><input type="file" accept=".zip,application/zip" data-zip aria-label="a release's zip">
  <span class="src" data-zip-said></span></div>
  <div class="bar" data-zip-bar hidden><i style="width:0"></i></div>
</section>""" % {"name": NAME}


def _plan_section(p, may_update):
    cand = p.get("candidate")
    if not cand or not p.get("target"):
        return ""
    d, target = p["direction"], p["target"]
    inst_v = (p.get("installed") or {}).get("version")
    src = ("downloaded from GitHub%s" % ((", published " + _when(cand.get("published")))
                                          if cand.get("published") else "")
           if cand.get("source") == "github" else
           "from <code>%s</code>, the zip you chose" % esc(cand.get("name") or "a zip"))
    # a name that goes back to the person is counted as theirs, not as a
    # deletion (the lists below say the same)
    back = set(r[0] for r in p.get("back") or [])
    facts = ["<li>%d of %s's files to write (%d of them new), %d to delete, %d as they are%s.</li>"
             % (p["write"], NAME, p["added"], len([x for x in p["delete"] if x not in back]),
                p["same"], ", and %d of yours put back" % len(back) if back else "")]
    if p.get("modes"):
        facts.append("<li>%d whose permissions are put right.</li>" % p["modes"])
    facts.append("<li>%s</li>" % esc(p["environment"]["said"]))
    facts.append("<li>Your books, videos, documents, decks, Anki cards and clips, the "
                 "dictionaries and models, speech to text's program and models, your settings, the "
                 "certificate and the devices let in are not touched: only the files the two "
                 "releases list are.</li>")
    fm = p.get("formats") or {}
    warn = ""
    if d == "older":
        warn += ('<div class="back"><b>This goes back.</b> Do it to escape a release that went '
                 'wrong. What %s added is gone until you update again.</div>' % esc(inst_v))
    if fm.get("lowered"):
        warn += ('<div class="back danger"><b>What may not survive going back.</b> %s'
                 '<ul class="facts">%s</ul>%s</div>'
                 % (esc(fm["said"]),
                    "".join("<li>%s <span class=src>(shape %s here, %s in %s)</span></li>"
                            % (esc(x["what"]), x["from"], x["to"] if x["to"] else "unknown",
                               esc(target)) for x in fm["lowered"]),
                    ('<label class="insist"><input type="checkbox" data-insist> I understand, and '
                     'want to go back to %s anyway.</label>' % esc(target)) if may_update else ""))
    elif fm.get("said"):
        facts.append("<li>%s</li>" % esc(fm["said"]))
    # a file of the person's that goes back is not listed as deleted too:
    # Parseh's file of that name goes, and theirs is what they will find
    lists = (_paths("Deleted, because %s does not ship them" % esc(target),
                    [x for x in p["delete"] if x not in back])
             + _paths("Yours, put back: %s does not ship these names, so the file of yours that "
                      "an update replaced goes back where it was, from that update's copy"
                      % esc(target), _by_whom(p.get("back")), open_=True)
             + _paths("Yours once, and not put back: an update replaced them, and the copy it "
                      "kept is gone (only the last %s updates keep theirs)" % _kept_jobs(),
                      _by_whom(p.get("gone")), open_=True)
             + _paths("Yours, left in that update's copy: %s has a folder where each was"
                      % esc(target), _by_whom(p.get("held")), open_=True)
             + _paths("Changed by hand since they were installed: overwritten, the copy you had "
                      "kept in the backup", p["edited"])
             + _paths("Not %s's until now: %s ships a file of the same name. Yours is kept in the "
                      "backup, and goes back where it was if one of the next %s updates installs "
                      "a version without that name" % (NAME, esc(target), _kept_jobs()),
                      p["foreign"])
             + _paths("The guide's pages, compiled again on this computer since they were "
                      "installed: overwritten, then compiled again", p.get("compiled") or []))
    if p.get("refused"):
        buttons = '<p class="said bad">%s</p>' % esc(p["refused"])
    elif not may_update:
        buttons = settingspage.lockline("parseh.update", p.get("_where"),
                                        "An update is started on the computer only.")
    else:
        buttons = """<div class="row">
    <button type="button" class="go %(d)s" data-go>%(label)s</button>
    <button type="button" class="plain" data-discard>Throw it away</button>
  </div>
  <div class="confirm" data-confirm hidden>
    <p>%(name)s stops, puts %(target)s's files in place of its own, and starts again; this page
    comes back by itself. A copy of every file it replaces is kept.%(extra)s</p>
    <div class="row"><button type="button" class="go %(d)s" data-yes>Yes, %(lower)s now</button>
    <button type="button" class="plain" data-no>Not now</button></div>
  </div>""" % {"d": esc(d), "label": esc(go_label(d, target)), "name": NAME,
               "target": esc(target), "lower": esc(go_label(d, target)[0].lower() + go_label(d, target)[1:]),
               "extra": (" <b>It is an older version.</b>" if d == "older" else "")}
    notes = ""
    if cand.get("notes"):
        notes = ('<details><summary>What %s says about itself</summary><div class="notes">%s'
                 '</div></details>' % (esc(target), esc(cand["notes"])))
    return """<section id="plan" data-plan>
  <h2>Ready to install</h2>
  <div class="row"><span class="vers">%(from)s<span class="arrow">&rarr;</span>%(to)s</span>%(dir)s</div>
  <p>%(said)s</p>
  <p class="src">%(target)s, %(src)s; built %(built)s from commit <code>%(commit)s</code>.</p>
  %(warn)s
  <ul class="facts">%(facts)s</ul>
  %(lists)s
  %(notes)s
  %(buttons)s
  <p class="said" data-apply-said></p>
</section>""" % {"from": esc(inst_v), "to": esc(target), "dir": _dir(d), "said": esc(p["said"]),
                 "target": esc(target), "src": src,
                 "built": esc(_when(p["incoming"].get("built")) or "?"),
                 "commit": esc((p["incoming"].get("commit") or "")[:12]),
                 "warn": warn, "facts": "".join(facts), "lists": lists, "notes": notes,
                 "buttons": buttons}


def _run_section(st, busy):
    """The update in progress: every step, marked, and the files counted --
    drawn by the page's script from the state it polls; here only the frame
    it fills, open when an update is running as the page loads."""
    return """<section id="run" data-run%(hidden)s>
  <h2>Updating</h2>
  <p><span class="vers" data-run-vers>%(vers)s</span></p>
  <ol class="steps" data-steps></ol>
  <div class="bar" data-run-bar><i style="width:0"></i></div>
  <p class="said" data-run-said>%(said)s</p>
  <p class="src">While %(name)s is being replaced this page is answered by the update itself, and
  comes back by itself when %(name)s is running again.</p>
</section>""" % {"hidden": "" if busy else " hidden", "name": NAME,
                 "vers": ("%s &rarr; %s" % (esc(st.get("from")), esc(st.get("to")))) if busy else "",
                 "said": esc(st.get("said") or "") if busy else ""}


def _report_section(st):
    """What the last update did, when it has finished: at the top of the
    page the new version loads."""
    r = st.get("report") or {}
    if st.get("phase") not in ("done", "failed", "rolled-back") or not r:
        return ""
    ok = st["phase"] == "done"
    # A FAILURE IN WORDS, Python's own line smaller beneath them
    # (updater.plainly): the words for the person, the line for whoever
    # mends Parseh
    head = (("%s is now <b>%s</b>" % (NAME, esc(r.get("to"))))
            + (" &mdash; it went back from %s." % esc(r.get("from")) if r.get("direction") == "older"
               else " (it was %s)." % esc(r.get("from")) if r.get("direction") == "newer"
               else ", installed again.")) if ok else \
        ("The update to %s did not happen. %s" % (esc(r.get("to")), esc(r.get("error") or ""))).strip()
    tech = ('<p class="tech" data-report-detail>%s</p>' % esc(r["error_detail"])
            if not ok and r.get("error_detail") else "")
    facts = []
    if ok:
        listed = r.get("written", 0) - r.get("replaced", 0) - len(r.get("added") or [])
        facts.append("<li>%d of %s's files written &mdash; %d as they were installed, %d new%s &mdash; "
                     "and %d already as they should be.</li>"
                     % (r.get("written", 0), NAME, r.get("replaced", 0), len(r.get("added") or []),
                        ", %d listed below" % listed if listed > 0 else "", r.get("unchanged", 0)))
    else:
        facts.append("<li>Everything was put back as it was%s.</li>"
                     % (" (%d files)" % r["restored"] if r.get("restored") else ""))
    if r.get("backup"):
        facts.append("<li>The files as they were before are kept in <code>%s</code>.</li>"
                     % esc(r["backup"]))
    if r.get("content_copy"):
        facts.append("<li>The small files of your books, videos, decks and settings were copied "
                     "first, to <code>%s</code> (%d files).</li>"
                     % (esc(r["content_copy"]), r.get("content_files") or 0))
    env = r.get("environment") or {}
    if env.get("ran"):
        facts.append("<li>The environment: %s.</li>" % esc(env.get("said")))
    for s in r.get("post") or []:
        facts.append("<li>%s: %s.</li>" % (esc(s.get("step")), esc(s.get("said"))))
    if r.get("resumed"):
        facts.append("<li>It was interrupted, and finished when %s next started.</li>" % NAME
                     if ok else "<li>It was interrupted, and undone when %s next started.</li>" % NAME)
    lists = ""
    if ok:
        # a file of the person's that went back is listed as that, not also
        # as deleted: Parseh's file of that name went, and theirs is there
        back = set(x[0] for x in r.get("put_back") or [] if x)
        lists = (_paths("Deleted, because %s does not ship them" % esc(r.get("to")),
                        [x for x in (r.get("deleted") or []) + (r.get("deleted_edited") or [])
                         if x not in back])
                 + _paths("Yours again: put back as they were before an update replaced them",
                          _by_whom(r.get("put_back")), open_=True)
                 + _paths("Yours once, and not put back: the copy kept when an update replaced them "
                          "is gone (only the last %s updates keep theirs)" % _kept_jobs(),
                          _by_whom(r.get("put_back_gone")), open_=True)
                 + _paths("Yours, still in that update's copy, because %s has a folder where each "
                          "was" % esc(r.get("to")),
                          ["%s (in %s)" % (x[0], x[2]) if len(x) > 2 else x[0]
                           for x in r.get("put_back_held") or [] if x], open_=True)
                 + _paths("Changed by hand since they were installed, and overwritten (your copy "
                          "is in the backup)", r.get("edited") or [], open_=True)
                 + _paths("Deleted although changed by hand (your copy is in the backup)",
                          r.get("deleted_edited") or [], open_=True)
                 + _paths("Not %s's until now, and overwritten: yours is in the backup, and goes "
                          "back where it was if one of the next %s updates installs a version "
                          "without that name" % (NAME, _kept_jobs()),
                          r.get("foreign") or [], open_=True)
                 + _paths("The guide's pages as this computer had compiled them (in the backup), "
                          "compiled again", r.get("compiled") or [])
                 + _paths("New in %s" % esc(r.get("to")), r.get("added") or []))
    when = settingspage.when(r.get("finished")) if r.get("finished") else ""
    return """<section class="report %(cls)s" data-report="%(id)s">
  <h2>The last update%(when)s</h2>
  <p>%(head)s</p>%(tech)s
  <ul class="facts">%(facts)s</ul>
  %(lists)s
  <p data-back hidden><a class="parseh-btn" href="#" data-back-link>Back to where you were</a></p>
</section>""" % {"cls": "ok" if ok else "bad", "id": esc(st.get("id")), "head": head,
                 "tech": tech, "when": (" &middot; " + esc(when)) if when else "",
                 "facts": "".join(facts), "lists": lists}


def page(p, s, st, where, fetching=None):
    """/settings/update/.  `p` is updater.plan(), `s` updater.settings(),
    `st` updater.state(), `where` lib/network.py's word for the device
    asking, `fetching` the download job the server is running, if any."""
    may_update = settingspage.may("parseh.update", where)
    may_check = settingspage.may("parseh.check", where)
    p = dict(p, _where=where)
    busy = bool(p.get("busy"))
    notice = ""
    if not may_update:
        notice = ('<div class="notice">You are reading this on another device. %s</div>'
                  % settingspage.lockline("parseh.update", where,
                                          "An update is started on the computer only."))
    refused = ""
    if p.get("refused") and not p.get("target"):
        refused = ('<section><h2>This %s cannot update itself</h2><p>%s</p></section>'
                   % (NAME, esc(p["refused"])))
    # what is happening first, then what is waiting, then what was done
    body = [_run_section(st, busy), refused]
    if not refused:
        body.append(_plan_section(p, may_update))
    body.append(_report_section(st))
    if not refused:
        body += [_latest_section(s, p, may_check, may_update, fetching), _zip_section(may_update)]
    main = """<main class="settings upd">
%(doors)s
<h1 class="idx">updating %(lname)s</h1>
<p class="ver" data-version>%(inst)s</p>
%(notice)s
%(body)s
<p class="foot">An update replaces only the files %(name)s's releases list: everything else in its
folder is yours and is left alone. A copy of every file it replaces is kept, and one that did not
finish (the power cut, the laptop closed) is finished or undone the next time %(name)s starts.
<a href="/guide/site/getting-started/updating.html">How updating works</a>.</p>
</main>""" % {"doors": settingspage.settings_doors("/settings/update/"), "lname": NAME.lower(),
              "name": NAME, "inst": _installed_line(p), "notice": notice,
              "body": "\n".join(b for b in body if b)}
    boot = {"busy": busy, "job": st.get("id") if busy else "",
            "state": st if busy else None, "fetching": bool(fetching),
            "report": st.get("id") if st.get("phase") in ("done", "failed", "rolled-back") else "",
            "name": NAME}
    script = """
<script id="upd-state" type="application/json">%s</script>
<script>%s</script>""" % (settingspage._in_script(boot), SCRIPT)
    return settingspage.frame("Updating %s &mdash; %s settings" % (NAME, NAME),
                              '<a href="/settings/">settings</a> &middot; updating', "Updating",
                              "/guide/site/getting-started/updating.html", main,
                              style=STYLE, script=script)


SCRIPT = r"""
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('upd-state').textContent);
  var API = '/settings/api/update/';
  function $(sel) { return document.querySelector(sel); }
  /* A FAILURE IN WORDS, and Python's own line -- when the server sends one
     (`detail`, lib/updater.py plainly) -- smaller beneath them */
  function tech(el, detail) {
    if (!detail) return;
    var t = document.createElement('span'); t.className = 'tech'; t.textContent = detail;
    el.appendChild(t);
  }
  function say(sel, text, bad, detail) {
    var el = $(sel); if (!el) return;
    el.textContent = text || ''; el.className = 'said' + (bad ? ' bad' : '');
    tech(el, detail);
  }
  function post(what, body, headers) {
    return fetch(API + what, {method: 'POST', cache: 'no-store',
                              headers: headers || {'Content-Type': 'application/json'},
                              body: body instanceof Blob ? body : JSON.stringify(body || {})})
      .then(function (r) { return r.json().catch(function () { return {ok: false, error: 'HTTP ' + r.status}; }); });
  }
  function getState() {
    return fetch(API + 'state', {cache: 'no-store'}).then(function (r) { return r.json(); });
  }
  function size(n) {
    if (n == null) return '';
    return n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + ' MB' : Math.round(n / 1e3) + ' kB';
  }

  /* WHERE THE PERSON CAME FROM, so the report can take them back: the page
     they opened Settings from, remembered for this tab.  Only an address on
     this Parseh, and never another page of the updater. */
  try {
    var ref = document.referrer ? new URL(document.referrer) : null;
    if (ref && ref.origin === location.origin && ref.pathname.indexOf('/settings/update/') !== 0)
      sessionStorage.setItem('parseh-update-from', ref.pathname + ref.search + ref.hash);
  } catch (e) { /* storage refused: the report simply has no way back */ }
  function cameFrom() {
    try { return sessionStorage.getItem('parseh-update-from') || ''; } catch (e) { return ''; }
  }
  var back = $('[data-back]');
  if (back && cameFrom()) {
    back.hidden = false;
    $('[data-back-link]').href = cameFrom();
  }

  /* THE NEWEST RELEASE */
  var chk = $('[data-check]');
  if (chk) chk.addEventListener('click', function () {
    chk.disabled = true;
    say('[data-check-said]', 'Asking GitHub…');
    post('check').then(function (j) {
      if (!j.ok) { chk.disabled = false; say('[data-check-said]', j.error || 'that was refused', true, j.detail); return; }
      location.reload();
    }, function () { chk.disabled = false; say('[data-check-said]', 'Parseh did not answer', true); });
  });
  var daily = $('[data-daily]');
  if (daily) daily.addEventListener('change', function () {
    post('daily', {on: daily.checked}).then(function (j) {
      say('[data-check-said]', j.ok ? (daily.checked ? 'Parseh looks once a day from now on.'
                                                    : 'Parseh no longer looks by itself.')
                                    : (j.error || 'that was refused'), !j.ok);
      if (!j.ok) daily.checked = !daily.checked;
    });
  });

  /* A DOWNLOAD FROM GITHUB: a bar, the size, Stop */
  function watchFetch() {
    var box = $('[data-fetch]'); if (!box) return;
    box.hidden = false;
    var got = $('[data-get]'); if (got) got.disabled = true;
    (function tick() {
      getState().then(function (j) {
        var f = j.fetch || {};
        var bar = $('[data-fetch-bar]');
        if (f.total) { bar.className = 'bar'; bar.firstChild.style.width = Math.round(100 * f.done / f.total) + '%'; }
        if (f.running) {
          $('[data-fetch-said]').textContent = f.total ? size(f.done) + ' of ' + size(f.total) : size(f.done);
          setTimeout(tick, 600); return;
        }
        if (f.error || f.stopped) {
          box.hidden = true; if (got) got.disabled = false;
          var s = $('[data-get-said]'); s.textContent = f.stopped ? 'Stopped. What came is kept; Download carries on from there.' : f.error;
          s.className = 'src' + (f.stopped ? '' : ' bad');
          if (!f.stopped) tech(s, f.detail);
          return;
        }
        location.reload();
      }, function () { setTimeout(tick, 1500); });
    })();
  }
  var get = $('[data-get]');
  if (get) get.addEventListener('click', function () {
    post('fetch').then(function (j) {
      if (!j.ok) { var s = $('[data-get-said]'); s.textContent = j.error || 'that was refused'; s.className = 'src bad'; tech(s, j.detail); return; }
      watchFetch();
    });
  });
  var stopGet = $('[data-stop-get]');
  if (stopGet) stopGet.addEventListener('click', function () { post('stop'); });
  if (S.fetching) watchFetch();

  /* A ZIP OF ONE'S OWN: sent as it is, the bar counting it up */
  var zip = $('[data-zip]');
  if (zip) zip.addEventListener('change', function () {
    var f = zip.files && zip.files[0]; if (!f) return;
    var said = $('[data-zip-said]'), bar = $('[data-zip-bar]');
    said.textContent = 'Sending ' + f.name + ' (' + size(f.size) + ')…'; said.className = 'src';
    bar.hidden = false;
    var x = new XMLHttpRequest();
    x.open('POST', API + 'upload?name=' + encodeURIComponent(f.name));
    x.setRequestHeader('Content-Type', 'application/zip');
    x.upload.onprogress = function (e) {
      if (e.lengthComputable) bar.firstChild.style.width = Math.round(100 * e.loaded / e.total) + '%';
      if (e.loaded === e.total) said.textContent = 'Checking ' + f.name + ' against its own list of files…';
    };
    x.onload = function () {
      var j = {}; try { j = JSON.parse(x.responseText); } catch (e) {}
      if (j.ok) { location.hash = 'plan'; location.reload(); return; }
      bar.hidden = true; zip.value = '';
      said.textContent = j.error || ('HTTP ' + x.status); said.className = 'src bad';
      tech(said, j.detail);
    };
    x.onerror = function () { bar.hidden = true; said.textContent = 'the zip could not be sent'; said.className = 'src bad'; };
    x.send(f);
  });

  var discard = $('[data-discard]');
  if (discard) discard.addEventListener('click', function () {
    post('discard').then(function () { location.reload(); });
  });

  /* THE BUTTON, AND THE PLAIN QUESTION UNDER IT */
  var go = $('[data-go]'), insist = $('[data-insist]');
  function goable() { if (go) go.disabled = !!insist && !insist.checked; }
  if (insist) insist.addEventListener('change', goable);
  goable();
  if (go) go.addEventListener('click', function () {
    $('[data-confirm]').hidden = false; go.disabled = true;
  });
  var no = $('[data-no]');
  if (no) no.addEventListener('click', function () { $('[data-confirm]').hidden = true; goable(); });
  var yes = $('[data-yes]');
  if (yes) yes.addEventListener('click', function () {
    yes.disabled = true;
    say('[data-apply-said]', 'Starting…');
    post('apply', {insist: !!(insist && insist.checked), from: cameFrom()}).then(function (j) {
      if (!j.ok) { yes.disabled = false; say('[data-apply-said]', j.error || 'that was refused', true, j.detail); return; }
      watchRun(j.job, j.state);
    }, function () { yes.disabled = false; say('[data-apply-said]', 'Parseh did not answer', true); });
  });

  /* WHILE IT RUNS: one address, answered by the server, then by the update
     itself, then by the new server -- and silence between them, which is
     only a moment and is waited through. */
  var MARK = {waiting: '○', running: '…', done: '✓', failed: '✗', skipped: '–'};
  function drawRun(st) {
    var run = $('[data-run]'); run.hidden = false;
    /* while it runs nothing else on the page can be done -- the server that
       would answer it is down -- so nothing else is shown */
    [].forEach.call(document.querySelectorAll('main section'), function (s) {
      if (s !== run) s.hidden = true;
    });
    $('[data-run-vers]').textContent = (st.from || '') + ' → ' + (st.to || '');
    var ol = $('[data-steps]'); ol.textContent = '';
    (st.steps || []).forEach(function (s) {
      var li = document.createElement('li'); li.className = s.state;
      var m = document.createElement('span'); m.className = 'm'; m.textContent = MARK[s.state] || '';
      m.setAttribute('aria-label', s.state);
      var t = document.createElement('span'); t.textContent = s.title;
      li.appendChild(m); li.appendChild(t);
      if (s.detail) { var d = document.createElement('span'); d.className = 'd'; d.textContent = s.detail; li.appendChild(d); }
      ol.appendChild(li);
    });
    var bar = $('[data-run-bar]');
    if (st.total) { bar.className = 'bar'; bar.firstChild.style.width = Math.round(100 * (st.done || 0) / st.total) + '%'; }
    else { bar.className = 'bar loose'; bar.firstChild.style.width = ''; }
    say('[data-run-said]', st.said || '');
  }
  function watchRun(job, first) {
    if (first) drawRun(first);
    if (window.scrollTo) { var r = $('[data-run]'); if (r && r.scrollIntoView) r.scrollIntoView({block: 'start'}); }
    var quiet = 0;
    (function tick() {
      getState().then(function (j) {
        quiet = 0;
        var st = j.update || {};
        if (st.id && st.id !== job) { setTimeout(tick, 1000); return; }
        drawRun(st);
        var over = ['done', 'failed', 'rolled-back'].indexOf(st.phase) >= 0;
        if (over && !j.helper) { location.replace('/settings/update/?after=' + encodeURIComponent(job)); return; }
        setTimeout(tick, 700);
      }, function () {
        quiet++;
        say('[data-run-said]', quiet > 3 ? 'Parseh is between two steps, and not answering for a moment…' : '');
        setTimeout(tick, 1000);
      });
    })();
  }
  if (S.busy) watchRun(S.job, S.state);
})();
"""


def door_tags(root):
    """What Settings' door to this page says about itself: which release the
    last look found, what is waiting, whether it looks by itself."""
    try:
        import updater
        s, inst, cand = updater.settings(root), updater.installed(root), updater.candidate(root)
    except Exception:                                   # noqa: BLE001 -- a door, never a failure
        return ""
    if inst.get("refused"):
        return '<span class="tag">%s</span>' % ("a git checkout" if inst.get("git")
                                                 else "not installed from a release")
    out = []
    latest = (s.get("latest") or {}).get("version")
    if latest and inst.get("version"):
        try:
            d = updater.direction_of(inst["version"], latest)
        except ValueError:
            d = ""
        if d == "newer":
            out.append('<span class="tag on">%s is out</span>' % esc(latest))
        elif d == "same":
            out.append('<span class="tag">the newest release</span>')
    if cand:
        out.append('<span class="tag on">%s ready to install</span>' % esc(cand.get("version")))
    if s.get("daily"):
        out.append('<span class="tag">looks once a day</span>')
    return "".join(out)


def state_json(p, s, st, fetching, running_version):
    """What /settings/api/update/state answers (the server's side of it;
    the helper answers the same address with {"helper": true, "update": ...}
    while the server is down)."""
    return {"ok": True, "helper": False, "version": running_version, "update": st,
            "fetch": fetching or {},
            "check": {k: s.get(k) for k in ("daily", "checked", "error", "detail")},
            "latest": s.get("latest"), "candidate": (p or {}).get("candidate"),
            "busy": bool((p or {}).get("busy"))}
