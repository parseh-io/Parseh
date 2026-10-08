# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> LaTeX drawings (TO-DO §8.39, a0.4.0): the themes a latex block
is drawn with, the TeX this computer has, the packages Parseh got for it, how
long a drawing may take, and the drawings kept.

EVERY CHANGE HERE IS THE COMPUTER'S ALONE (lib/settingspage.py, RUN): a theme
is LaTeX that every block naming it runs, a package is somebody else's code
TeX then runs, and renaming a theme rewrites what a person wrote.  A phone
sees all of it, each part with its lock and the sentence the server would
refuse it with; it may export a theme (a read), and forget the drawings
nothing uses (it frees space and changes nothing any drawing will be).

The routes are serve.py's (`/settings/api/latex/...`, each a literal there, as
tests/test_settings_risk.py finds them); what each one does is api() below.
"""
import html
import json
import os
import shutil
import subprocess
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import latexdraw                                             # noqa: E402
import latexthemes                                           # noqa: E402
import settingspage                                          # noqa: E402
import texpackages                                           # noqa: E402

PAGE = "/settings/latex/"
GUIDE = "/guide/site/dialect/latex-drawings.html"
SAMPLE = r"\ce{2H2 + O2 -> 2H2O}"

# what each route does, and the setting it is (lib/settingspage.py ROUTES)
KEYS = ("latex.theme", "latex.rename", "latex.import", "latex.packages", "latex.limit",
        "latex.forget")


def esc(s):
    return html.escape(str(s), quote=True)


def fonts():
    """The font families this computer has, for a theme's font."""
    fc = shutil.which("fc-list")
    if not fc:
        return []
    try:
        out = subprocess.run([fc, ":", "family"], capture_output=True, text=True,
                             timeout=15, stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    names = sorted({l.split(",")[0].strip() for l in out.splitlines() if l.strip()})
    return names[:2000]


def view(where):
    """Everything the page draws, in one answer."""
    doc = latexthemes.all_of()
    comps = latexdraw.compilers()
    # every file a theme could ask for, not only the saved themes' own: a box
    # ticked in an open editor is marked missing at once, from one kpsewhich
    checks = texpackages.installed_many([row["file"] for row in latexthemes.PACKAGES.values()] +
                                        [row[1] for row in latexthemes.ALWAYS.values()])
    # a theme's own package is there only when Parseh has got it, whatever the
    # computer's TeX holds (latexthemes.own_packages)
    local = texpackages.local_rule()
    if local:
        got = texpackages.manifest()["packages"]
        for p in latexthemes.ORDER:
            if p not in latexthemes.BASE:
                row = latexthemes.PACKAGES[p]
                checks[row["file"]] = all(n in got for n in row["tl"])
    return {
        "themes": doc["themes"], "default": doc["default"], "timeout": doc["timeout"],
        "limits": [latexthemes.TIMEOUT_MIN, latexthemes.TIMEOUT_MAX],
        "compilers": {k: (v or None) for k, v in comps.items()},
        "catalogue": [latexthemes.PACKAGES[p] for p in latexthemes.ORDER],
        "groups": latexthemes.GROUPS,
        "files": checks,
        "local": local,
        "always": {k: [list(v[0]), v[1], v[2]] for k, v in latexthemes.ALWAYS.items()},
        "unicode": list(latexthemes.UNICODE),
        "needs": {t["name"]: [list(x[:2]) + [list(x[2]), x[3]] for x in latexthemes.files_needed(t)]
                  for t in doc["themes"]},
        "tex": texpackages.distribution(),
        "packages": texpackages.status(),
        "kept": latexdraw.size(),
        "may": {k: settingspage.may(k, where) for k in KEYS},
        "where": where or "",
        "rule": latexthemes.NAME_RULE,
        "sample": SAMPLE,
    }


def page(where):
    v = view(where)
    main = """<main class="settings lx">
%(doors)s
<h1 class="idx">latex drawings</h1>
<div id="lx"><p>Reading what is here&hellip;</p></div>
<p class="foot">The themes are kept in <code>config/latex.json</code>, the packages Parseh got
in <code>texmf/</code>, and the drawings in <code>markdown/latex/</code>, made again whenever
they are needed. A formula written <code>:::math</code> is not touched by anything here. <a href="%(guide)s">LaTeX drawings</a>, in the guide.</p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "guide": GUIDE}
    script = ('<script id="lx-state" type="application/json">%s</script>\n<script>%s</script>'
              % (settingspage._in_script(v), SCRIPT))
    return settingspage.frame("LaTeX drawings &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; latex drawings',
                              "LaTeX drawings", GUIDE, main, style=STYLE, script=script)


class Refused(Exception):
    pass


def api(what, body, where, libraries=(), rename=None, used=None):
    """One route's work -> (status, answer).  `rename` is the studio's
    latexrename module, `used` a function giving every drawing's key in use:
    both are the server's, which knows the libraries."""
    body = body or {}
    try:
        if what == "state":
            return 200, dict(view(where), ok=True)
        if what == "fonts":
            return 200, {"ok": True, "fonts": fonts()}
        if what == "sample":
            theme = latexthemes.clean(dict(body.get("theme") or {}, name=body.get("theme", {}).get("name") or "sample"))
            r = latexdraw.draw(body.get("tex") or SAMPLE, None, theme=theme, preview=True)
            return 200, {"ok": True, "result": r, "preamble": latexthemes.preamble(theme)}
        if what == "save":
            t = latexthemes.save(body.get("theme") or {}, was=body.get("was"))
            return 200, {"ok": True, "theme": t}
        if what == "delete":
            latexthemes.delete(body.get("name") or "")
            return 200, {"ok": True}
        if what == "default":
            latexthemes.set_default(body.get("name") or "")
            return 200, {"ok": True}
        if what == "rename-plan":
            return 200, dict(rename.plan(body.get("old") or "", body.get("new") or "", libraries),
                             ok=True)
        if what == "rename":
            done = rename.apply(body.get("old") or "", body.get("new") or "", libraries)
            return 200, dict(done, ok=True)
        if what == "import-read":
            t = latexthemes.read_export(body.get("data") or "")
            taken = latexthemes.find(t["name"]) is not None
            return 200, {"ok": True, "theme": t, "preamble": latexthemes.preamble(t),
                         "taken": taken}
        if what == "import":
            t = latexthemes.read_export(body.get("data") or "")
            name = body.get("name") or t["name"]
            if latexthemes.find(name) is not None:
                raise Refused("There is a theme called %s already: choose another name." % name)
            return 200, {"ok": True, "theme": latexthemes.import_theme(t, name)}
        if what == "limit":
            latexthemes.set_timeout(body.get("seconds"))
            latexdraw.forget_failures()
            return 200, {"ok": True}
        if what == "forget":
            # what is in a trash keeps nothing here: a drawing is derived, and a
            # deck or a book taken back from its trash is drawn again
            keys = used(include_trash=False) if used else set()
            latexdraw.repair_owners(keys, force=True)
            gone = latexdraw.forget_unused(keys)
            return 200, dict(gone, ok=True, forgotten=gone["drawings"], kept=latexdraw.size())
        if what == "package-plan":
            names = list(dict.fromkeys(n for n in (body.get("packages") or []) if isinstance(n, str)))
            return 200, dict(texpackages.plan(names), ok=True)
        if what == "package-get":
            for n in dict.fromkeys(n for n in (body.get("packages") or []) if isinstance(n, str)):
                texpackages.start(n)
            return 200, dict(texpackages.status(), ok=True)
        if what == "package-remove":
            texpackages.remove(body.get("package") or "")
            return 200, dict(texpackages.status(), ok=True)
        if what == "package-stop":
            texpackages.stop(body.get("package"))
            return 200, dict(texpackages.status(), ok=True)
        if what == "package-status":
            return 200, dict(texpackages.status(), ok=True)
    except (latexthemes.ThemeError, Refused, ValueError) as e:
        return 400, {"ok": False, "error": str(e)}
    return 404, {"ok": False, "error": "no such route"}


STYLE = r"""
.lx .theme{border:1px solid var(--rule);border-radius:10px;padding:10px 14px;margin:10px 0;background:var(--card)}
.lx .theme h3{margin:0 0 4px;font-size:16px}
.lx .theme .facts{color:var(--dim);font-size:13px}
.lx .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px}
.lx .grp{margin:8px 0}
.lx .grp h4{margin:6px 0 4px;font-size:13px;color:var(--dim);text-transform:uppercase;letter-spacing:.08em}
.lx .grp-why{margin:0 0 5px;font-size:13px;color:var(--dim)}
.lx label.pk{display:block;margin:3px 0;font-size:14px}
.lx label.pk small{color:var(--dim)}
.lx label.pk code{font-size:12px}
.lx .missing{color:var(--danger,#c33);font-size:12px}
.lx textarea{width:100%;min-height:6rem;font-family:ui-monospace,monospace}
.lx pre.pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--boxbg);padding:8px;border-radius:6px;font-size:12px;max-height:22rem;overflow:auto}
.lx .said{min-height:1.2em;font-size:13px}
.lx .bar{height:6px;background:var(--rule);border-radius:3px;overflow:hidden;margin:8px 0;max-width:32rem}
.lx .bar i{display:block;height:100%;background:var(--accent);border-radius:3px;transition:width .4s}
.lx .bar.loose i{width:30%;animation:lx-slide 1.4s ease-in-out infinite}
@keyframes lx-slide{0%{margin-inline-start:-30%}100%{margin-inline-start:100%}}
@media (prefers-reduced-motion:reduce){.lx .bar.loose i{width:100%;opacity:.45;animation:none}}
.lx .edit-missing{position:sticky;bottom:0;margin:8px 0 0;padding:8px 12px;font-size:13px;background:var(--boxbg);
  border:1px solid var(--rule);border-inline-start:3px solid var(--warn);border-radius:8px}
.lx .edit-missing a{color:var(--accent);text-underline-offset:2px}
.lx .bad{color:var(--danger,#c33)}
@keyframes lx-plan-flash{0%{outline:3px solid var(--accent);outline-offset:3px}100%{outline:3px solid transparent;outline-offset:7px}}
.lx img.sample{max-width:100%;background:#fff;padding:6px;border-radius:4px}
.lx .tex-status{margin:.65rem 0 1rem}
.lx .tex-status>div{display:grid;grid-template-columns:minmax(8rem,.8fr) minmax(0,2fr);gap:6px 12px;align-items:center;
  padding:8px 0;border-top:1px solid var(--rule)}
.lx .tex-status>div:last-child{border-bottom:1px solid var(--rule)}
.lx .tex-status dt{font-size:14px;font-weight:600}
.lx .tex-status dd{margin:0;min-width:0;display:flex;align-items:center;gap:6px 10px;flex-wrap:wrap}
.lx .st{display:inline-flex;align-items:center;gap:5px;font-size:12px;line-height:1.2;
  padding:2px 9px 2px 7px;border-radius:20px;border:1px solid currentColor;white-space:nowrap;
  background:color-mix(in srgb,currentColor 9%,transparent)}
.lx .st i{font-style:normal;font-weight:700}
.lx .st.ok{color:var(--ok)}
.lx .st.not,.lx .st.wait{color:var(--dim);border-style:dashed;background:none}
.lx .st.run{color:var(--accent)}
.lx .st.need{color:var(--warn)}
.lx .st.bad{color:var(--danger);background:color-mix(in srgb,var(--danger) 8%,transparent)}
.lx .tex-status .compiler-version{min-width:0;color:var(--dim);font:12px ui-monospace,monospace;overflow-wrap:anywhere}
@media (max-width:40rem){.lx .tex-status>div{grid-template-columns:1fr;gap:4px}}
.lx table{border-collapse:collapse;width:100%}
.lx td,.lx th{text-align:left;padding:4px 6px;border-bottom:1px solid var(--rule);font-size:13px}
.lx [data-package-panel]{scroll-margin-block:2rem}
.lx [data-package-panel].flash,.lx section.edit.flash{animation:lx-plan-flash 1.1s ease-out}
.lx section.edit{scroll-margin-top:12px}
.lx section.edit h2:focus{outline:none}
@media (prefers-reduced-motion:reduce){.lx [data-package-panel].flash,.lx section.edit.flash{animation:none}}
.lx .pkg-intro{margin:.35rem 0 .65rem;color:var(--dim);font-size:13px}
.lx .pkg-live{min-height:1.35em;margin:.35rem 0;font-size:13px}
.lx .pkg-table{margin:.45rem 0}
.lx .pkg-table th,.lx .pkg-table td{vertical-align:top}
.lx .pkg-table th[scope=row]{font-weight:600;white-space:nowrap}
.lx .pkg-table td[data-label=Size]{white-space:nowrap}
.lx .pkg-why{display:block;margin-top:2px;color:var(--dim);font-size:12px;overflow-wrap:anywhere}
.lx .pkg-state{min-width:12rem}
.lx .pkg-detail{display:block;margin-top:3px;color:var(--dim);font-size:12px;overflow-wrap:anywhere}
.lx .pkg-detail.bad{color:var(--danger)}
.lx .pkg-actions{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.lx .pkg-confirm{font-size:12px;color:var(--danger);margin-bottom:4px}
.lx .pkg-empty{color:var(--dim);font-size:13px}
.lx .pkg-bulk{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:.65rem 0}
.lx .pkg-table tr.pkg-group th{padding:14px 6px 5px;font-size:13px;font-weight:700;text-align:start;white-space:normal;
  border-bottom:2px solid var(--rule)}
.lx .pkg-table tr.pkg-group small{display:block;margin-top:2px;font-size:12px;font-weight:400;color:var(--dim)}
.lx .pkg-table tbody:first-of-type tr.pkg-group th{padding-top:6px}
.lx .st.sys{color:var(--ink);border-color:var(--rule);background:none}
.lx .pkg-table tr.pkg-sys td{color:var(--dim)}
.lx .pkg-none{color:var(--dim)}
.lx .vh{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media (max-width:40rem){
  .lx .pkg-table,.lx .pkg-table tbody,.lx .pkg-table tr,.lx .pkg-table th,.lx .pkg-table td{display:block;width:100%}
  .lx .pkg-table thead{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
  .lx .pkg-table tr{border:1px solid var(--rule);border-radius:8px;background:var(--boxbg);padding:6px 8px;margin:8px 0}
  .lx .pkg-table th,.lx .pkg-table td{border:0;padding:4px 0;display:grid;grid-template-columns:7rem minmax(0,1fr);gap:5px 10px}
  .lx .pkg-table th::before,.lx .pkg-table td::before{content:attr(data-label);font-size:12px;color:var(--dim);font-weight:400}
  .lx .pkg-table tr.pkg-group{border:0;background:none;padding:0;margin:18px 0 2px}
  .lx .pkg-table tr.pkg-group th{display:block;padding:0 0 4px}
  .lx .pkg-table tr.pkg-group th::before{content:none}
  .lx .pkg-table tr.pkg-sys .pkg-action{display:none}
  .lx .pkg-table .pkg-action{display:block}
  .lx .pkg-table .pkg-action::before{display:block;margin-bottom:4px}
  .lx .pkg-table .pkg-state{min-width:0}
}
"""

SCRIPT = r"""
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('lx-state').textContent);
  var root = document.getElementById('lx');
  var API = '/settings/api/latex/';
  var editing = null;       // the theme being edited: {was, theme}
  var packagePlans = {};    // name -> its quote, kept for the session while the rest redraws
  var packageAsked = {};    // one-off names typed into the package box
  var packageRequest = {};  // name -> the newest ask, the only one allowed to change it
  var packageSerial = 0;
  var packageMessage = '';
  var removing = null;
  var polling = false;
  var forgetting = false;   // the cleanup of the drawings is being done
  var draft = {features: [], names: [], need: []};  // what the open editor's unsaved theme lacks here
  var draftTimer = 0;
  var QUOTES = 'parseh.lx.quotes', QUOTE_AGE = 30 * 60 * 1000;
  var FORGET_WORKING = 'Looking through every document, deck and note…';
  var ASK_MS = 150000;      // tlmgr may take 60 s on each of two repositories
  var q = new URLSearchParams(location.search);
  function esc(s) { return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
    return {'<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;'}[c]; }); }
  function post(what, body, ms) {
    var ctl = ms && window.AbortController ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, ms) : 0;
    return fetch(API + what, {method: 'POST', headers: {'Content-Type': 'application/json'},
                              body: JSON.stringify(body || {}), signal: ctl ? ctl.signal : undefined})
      .then(function (r) { return r.json().catch(function () { return {ok: false, error: r.statusText}; }); })
      .then(function (v) { clearTimeout(timer); return v; }, function (e) { clearTimeout(timer); throw e; });
  }
  function may(k) { return !!S.may[k]; }
  function dis(k) { return may(k) ? '' : ' disabled'; }
  function lock(k) { return may(k) ? '' : '<div class="lockline">Changed on the computer only.</div>'; }
  function MB(n) { return n == null ? '' : (n >= 1e6 ? (n / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1e3)) + ' kB'); }
  function drawings(n) { return n + ' drawing' + (n === 1 ? '' : 's'); }
  // an editor open while the page is read again keeps what was typed in it
  function keepEditing() { if (editing && root.querySelector('section.edit')) { try { editing.theme = current(); } catch (e) {} } }
  function reload() { keepEditing(); return post('state').then(function (v) { if (v.ok) { S = v; draw(); } }); }

  function unique(a) { return a.filter(function (x, at) { return x && a.indexOf(x) === at; }); }
  function packageAvailable(name) {
    var plan = packagePlans[name] || {};
    return !!(((S.packages || {}).available || {})[name] || plan.here === 'available');
  }
  // an unsaved theme's [id, file, TeX Live packages, licence], as latexthemes.files_needed gives a saved one's
  function draftNeeds(t) {
    var a = S.always, uni = S.unicode.indexOf(t.compiler) >= 0;
    var out = [['standalone', a.standalone[1], a.standalone[0], a.standalone[2]]];
    S.catalogue.forEach(function (p) { if (t.packages.indexOf(p.id) >= 0) out.push([p.id, p.file, p.tl, p.licence]); });
    if (uni && (t.font || t.languages)) out.push(['fontspec', a.fontspec[1], a.fontspec[0], a.fontspec[2]]);
    if (uni && t.font) out.push(['unicode-math', a['unicode-math'][1], a['unicode-math'][0], a['unicode-math'][2]]);
    return out;
  }
  function themeNeed(t, needs) {
    var features = [], names = [];
    needs = needs || S.needs[t.name] || [];
    needs.forEach(function (need) {
      if (S.files[need[1]] !== false) return;
      var want = (need[2] || []).filter(function (name) { return !packageAvailable(name); });
      if (!want.length) return;
      if (features.indexOf(need[0]) < 0) features.push(need[0]);
      names = names.concat(want);
    });
    return {features: features, names: unique(names), need: needs};
  }
  function missingMarkup(t) {
    var need = themeNeed(t);
    if (!need.features.length) return '';
    return '<div class="missing">Not installed here: ' + need.features.map(esc).join(', ') +
      (need.names.length ? ' <button type="button" class="plain" data-install="' + esc(need.names.join(' ')) +
       '" aria-label="Review packages needed by ' + esc(t.name) + '"' + dis('latex.packages') +
       '>Review packages…</button>' : '') + '</div>';
  }
  function requiredPackages() {
    var rows = {};
    S.themes.forEach(function (t) {
      var need = themeNeed(t);
      need.names.forEach(function (name) {
        var row = rows[name] || (rows[name] = {name: name, themes: [], licence: ''});
        if (row.themes.indexOf(t.name) < 0) row.themes.push(t.name);
        (S.needs[t.name] || []).forEach(function (one) {
          if ((one[2] || []).indexOf(name) >= 0 && !row.licence) row.licence = one[3] || '';
        });
      });
    });
    draft.names.forEach(function (name) {
      var row = rows[name] || (rows[name] = {name: name, themes: [], licence: ''});
      row.draft = true;
      draft.need.forEach(function (one) {
        if ((one[2] || []).indexOf(name) >= 0 && !row.licence) row.licence = one[3] || '';
      });
    });
    Object.keys(packageAsked).forEach(function (name) {
      if (packageAvailable(name)) return;
      rows[name] = rows[name] || {name: name, themes: [], licence: ''};
      rows[name].asked = true;
    });
    return rows;
  }
  // What comes with this computer's TeX: a package a theme needs that TeX
  // finds, and that is not a copy Parseh got -- listed, with nothing to do.
  function systemRows(own) {
    var rows = {}, installed = (S.packages || {}).installed || {};
    function add(t, needs, isDraft) {
      needs.forEach(function (need) {
        if (S.files[need[1]] !== true) return;
        (need[2] || []).forEach(function (name) {
          if (installed[name] || own[name]) return;
          var row = rows[name] || (rows[name] = {name: name, themes: [], licence: need[3] || '', system: true});
          if (isDraft) row.draft = true;
          else if (row.themes.indexOf(t.name) < 0) row.themes.push(t.name);
        });
      });
    }
    S.themes.forEach(function (t) { add(t, S.needs[t.name] || []); });
    if (editing && draft.need && draft.need.length) add(null, draft.need, true);
    return rows;
  }
  function packageRows() {
    var rows = requiredPackages(), installed = (S.packages || {}).installed || {}, jobs = (S.packages || {}).jobs || {};
    Object.keys(installed).forEach(function (name) {
      rows[name] = rows[name] || {name: name, themes: [], licence: ''};
      rows[name].installed = installed[name];
    });
    Object.keys(jobs).forEach(function (name) {
      rows[name] = rows[name] || {name: name, themes: [], licence: ''};
      rows[name].job = jobs[name];
    });
    Object.keys(rows).forEach(function (name) { if (packagePlans[name]) rows[name].plan = packagePlans[name]; });
    return Object.keys(rows).sort().map(function (name) { return rows[name]; });
  }
  function packageWhy(row) {
    var why = [];
    if (row.themes.length > 1 && row.themes.length === S.themes.length) why.push('for every theme');
    else if (row.themes.length) why.push('for the theme' + (row.themes.length === 1 ? ' ' : 's ') + row.themes.map(esc).join(', '));
    if (row.draft) why.push('for the theme being edited (unsaved)');
    if (!why.length && row.asked) why.push('you asked for it');
    return why.join('; ');
  }
  function packageState(row) {
    var name = row.name, job = row.job || {}, plan = row.plan || {}, state = job.state ||
      (job.running ? 'running' : (job.error ? (job.error === 'Stopped.' ? 'stopped' : 'failed') : ''));
    var cost = plan.size == null ? '' : ', ' + MB(plan.size);
    var get = '<button type="button" class="go" data-package-get="' + esc(name) +
      '" aria-label="Get ' + esc(name + cost) + '"' + dis('latex.packages') + '>Get it</button>';
    var retry = '<button type="button" class="go" data-package-retry="' + esc(name) +
      '" aria-label="Try getting ' + esc(name) + ' again"' + dis('latex.packages') + '>Try again</button>';
    var stop = '<button type="button" class="plain" data-package-stop="' + esc(name) +
      '" aria-label="Stop getting ' + esc(name) + '"' + dis('latex.packages') + '>Stop</button>';
    var none = '<span class="pkg-none" aria-hidden="true">—</span><span class="vh">Nothing to get or remove</span>';
    var busy = state === 'queued' || state === 'waiting' || state === 'running';
    if (row.system && !row.installed && !busy) return {kind: 'system',
      text: '<span class="st sys"><i aria-hidden="true">✓</i> With this computer\'s TeX</span>', detail: '', action: none};
    if (row.installed) {
      if (removing === name) return {kind: 'got', text: '<span class="st ok"><i aria-hidden="true">✓</i> Got</span>',
        detail: 'Remove only the copy Parseh got.', action: '<div class="pkg-confirm">Remove ' + esc(name) +
        ' from Parseh?</div><div class="pkg-actions"><button type="button" class="danger" data-remove-yes="' + esc(name) +
        '" aria-label="Yes, remove ' + esc(name) + ' from Parseh"' + dis('latex.packages') + '>Remove</button>' +
        '<button type="button" class="plain" data-remove-no>Cancel</button></div>'};
      return {kind: 'got', text: '<span class="st ok"><i aria-hidden="true">✓</i> Got</span>',
        detail: '', action: '<button type="button" class="plain" data-remove="' + esc(name) +
        '" aria-label="Remove ' + esc(name) + ' from Parseh"' + dis('latex.packages') + '>Remove…</button>'};
    }
    if (state === 'queued' || state === 'waiting') return {kind: 'waiting',
      text: '<span class="st wait"><i aria-hidden="true">○</i> Waiting</span>', detail: 'Another package is being got first.', action: stop};
    if (state === 'running') return {kind: 'getting',
      text: '<span class="st run"><i aria-hidden="true">↻</i> Getting</span>',
      detail: (job.total ? job.done + ' of ' + job.total : '') + (job.say ? (job.total ? ' — ' : '') + esc(job.say) : ''), action: stop};
    if (state === 'failed') return {kind: 'failed',
      text: '<span class="st bad"><i aria-hidden="true">!</i> Could not get it</span>', detail: esc(job.error || 'It failed.'), action: retry};
    if (state === 'stopped') return {kind: 'stopped',
      text: '<span class="st not"><i aria-hidden="true">—</i> Stopped</span>', detail: '', action: retry};
    if (state === 'available' || packageAvailable(name) || plan.here === 'available') return {kind: 'available',
      text: '<span class="st sys"><i aria-hidden="true">✓</i> With this computer\'s TeX</span>', detail: 'Parseh will not add a second copy.', action: none};
    if (plan.state === 'asking') return {kind: 'asking',
      text: '<span class="st wait"><i aria-hidden="true">○</i> Asking…</span>', detail: '', action: ''};
    if (plan.state === 'unreachable') return {kind: 'unreachable',
      text: '<span class="st bad"><i aria-hidden="true">!</i> Could not ask</span>',
      detail: esc(plan.why || 'The TeX Live repository could not be reached.'),
      action: '<button type="button" class="plain" data-package-review="' + esc(name) +
        '" aria-label="Ask again what ' + esc(name) + ' costs"' + dis('latex.packages') + '>Ask again</button>'};
    if (plan.repository === 'unavailable' || plan.can_get === false || plan.state === 'unavailable') return {kind: 'unavailable',
      text: '<span class="st bad"><i aria-hidden="true">!</i> Not available here</span>',
      detail: esc(plan.why || 'This TeX Live repository does not offer it.'), action: ''};
    if (plan.state === 'ready') return {kind: 'ready', text: '<span class="st need"><i aria-hidden="true">○</i> Not installed</span>',
      detail: '', action: get, ready: true, size: plan.size};
    return {kind: 'review', text: '<span class="st need"><i aria-hidden="true">○</i> Not installed</span>',
      detail: 'Its cost is not known yet.', action: '<button type="button" class="plain" data-package-review="' + esc(name) +
      '" aria-label="Review the cost of ' + esc(name) + '"' + dis('latex.packages') + '>Review cost</button>'};
  }
  // read as one line: Not installed · 26 kB · lppl1.3c · Get it
  function packageRow(row, state) {
    var plan = row.plan || {}, licence = plan.licence || (row.installed || {}).licence || row.licence || '';
    var size = plan.size != null ? MB(plan.size) : ((row.installed || {}).size != null ? MB(row.installed.size) : '');
    var sys = state.kind === 'system' || state.kind === 'available';
    return '<tr data-package-row="' + esc(row.name) + '"' + (sys ? ' class="pkg-sys"' : '') + '><th scope="row" data-label="Package"><code>' + esc(row.name) +
      '</code></th><td data-label="Needed for">' + packageWhy(row) + '</td><td class="pkg-state" data-label="State" aria-live="polite">' +
      state.text + (state.detail ? '<span class="pkg-detail' + (state.kind === 'failed' || state.kind === 'unavailable' || state.kind === 'unreachable' ? ' bad' : '') +
      '">' + state.detail + '</span>' : '') + '</td><td data-label="Size">' + (sys ? '<span aria-hidden="true">—</span><span class="vh">not downloaded by Parseh</span>' : esc(size || 'Not known yet')) +
      '</td><td data-label="Licence">' + esc(licence) + '</td><td class="pkg-action" data-label="Action">' + state.action + '</td></tr>';
  }
  function rowFromHtml(html) {
    var t = document.createElement('tbody');
    t.innerHTML = html;
    var tr = t.firstElementChild;
    tr._sig = html;
    return tr;
  }
  // which control of a row has the keyboard: the first data-… attribute names it
  function focusToken(el) {
    if (!el || !el.attributes) return null;
    for (var i = 0; i < el.attributes.length; i++) {
      if (el.attributes[i].name.indexOf('data-') === 0) return {name: el.attributes[i].name, value: el.attributes[i].value};
    }
    return null;
  }
  function refocus(tr, tok) {
    var found = null;
    if (tok) Array.prototype.forEach.call(tr.querySelectorAll('[' + tok.name + ']'), function (el) {
      if (!found && el.getAttribute(tok.name) === tok.value) found = el;
    });
    found = found || tr.querySelector('[data-remove-no]') || tr.querySelector('button');
    try { if (found) found.focus({preventScroll: true}); } catch (e) {}
  }
  // The table is kept, not rebuilt: a quote changes its own row alone, so focus and typing stay.
  function renderPackages() {
    var panel = root.querySelector('[data-package-panel]');
    if (!panel) return;
    if (!panel.querySelector('[data-pkg-rows]')) {
      var texName = esc(S.tex.said || 'this computer\'s TeX');
      panel.innerHTML = '<h3 id="tex-packages">TeX packages</h3><p class="pkg-intro">' + (S.local
        ? 'Every package the themes use. A theme\'s packages beyond the base are Parseh\'s own: a drawing uses them only once Parseh has got them into its <code>texmf/</code> folder, even when this computer\'s TeX has them too. What each missing one costs is asked of the TeX Live repository, and nothing is downloaded until you press Get it; they are got one at a time. The base comes with ' + texName + ': it is listed below them, and there is nothing to get or remove.'
        : 'Every package the themes use. One this computer lacks says what it costs, and nothing is downloaded until you press Get it; they are got one at a time. What this computer\'s TeX already has is listed below them, with nothing to get or remove.') + '</p>' +
        '<div class="pkg-live" data-pkg-said aria-live="polite" aria-atomic="true" tabindex="-1"></div><div data-pkg-bulk></div>' +
        '<table class="pkg-table"><thead><tr><th scope="col">Package</th><th scope="col">Needed for</th><th scope="col">State</th><th scope="col">Size</th><th scope="col">Licence</th><th scope="col">Action</th></tr></thead>' +
        '<tbody><tr class="pkg-group"><th colspan="6" scope="colgroup" id="pkg-own">Parseh\'s own <small>' + (S.local ? 'in its <code>texmf/</code> folder: got and removed here' : 'got and removed here') + '</small></th></tr></tbody>' +
        '<tbody data-pkg-rows></tbody>' +
        '<tbody data-pkg-sys-head hidden><tr class="pkg-group"><th colspan="6" scope="colgroup" id="pkg-sys">With this computer\'s TeX <small>' + texName + (S.local ? ' — LaTeX\'s base, which every drawing uses: nothing to get or remove' : ' — nothing to get or remove') + '</small></th></tr></tbody>' +
        '<tbody data-pkg-sys></tbody></table>' +
        '<div class="row"><input type="text" data-pkgname placeholder="a TeX Live package, e.g. chemfig"' + dis('latex.packages') +
        '><button type="button" class="plain" data-package-plan' + dis('latex.packages') + '>What it costs…</button></div>' + lock('latex.packages');
    }
    var all = packageRows().map(function (row) { return {row: row, state: packageState(row)}; });
    var rows = all.filter(function (x) { return x.state.kind !== 'available'; }), ownNames = {};
    all.forEach(function (x) { ownNames[x.row.name] = true; });
    var sysMap = systemRows(ownNames);
    var sysRows = all.filter(function (x) { return x.state.kind === 'available'; }).concat(Object.keys(sysMap).map(function (n) {
      return {row: sysMap[n], state: packageState(sysMap[n])};
    })).sort(function (a, b) { return a.row.name < b.row.name ? -1 : a.row.name > b.row.name ? 1 : 0; });
    var ready = rows.filter(function (x) { return x.state.ready; });
    var total = ready.reduce(function (n, x) { return n + (+x.state.size || 0); }, 0);
    var bulk = ready.length > 1 ? '<div class="pkg-bulk"><button type="button" class="go" data-package-get-all="' +
      esc(ready.map(function (x) { return x.row.name; }).join(' ')) + '" aria-label="Get all ' + esc(ready.map(function (x) { return x.row.name; }).join(', ')) +
      '"' + dis('latex.packages') + '>Get all' + (total ? ' — ' + MB(total) : '') + '</button><span>' + ready.length + ' packages ready</span></div>' : '';
    var live = panel.querySelector('[data-pkg-said]');
    if (live.textContent !== packageMessage) live.textContent = packageMessage;
    var bulkBox = panel.querySelector('[data-pkg-bulk]');
    if (bulkBox._sig !== bulk) {
      var tok = bulkBox.contains(document.activeElement) ? focusToken(document.activeElement) : null;
      bulkBox._sig = bulk; bulkBox.innerHTML = bulk;
      if (tok) refocus(bulkBox, tok);
    }
    var body = panel.querySelector('[data-pkg-rows]'), have = {}, at = 0;
    Array.prototype.forEach.call(body.children, function (tr) { if (tr.hasAttribute('data-package-row')) have[tr.getAttribute('data-package-row')] = tr; });
    // a row that goes first, so that the rows after it are not moved (a moved row loses the keyboard)
    Object.keys(have).forEach(function (name) {
      if (!rows.some(function (x) { return x.row.name === name; })) { body.removeChild(have[name]); delete have[name]; }
    });
    rows.forEach(function (x) {
      var html = packageRow(x.row, x.state), cur = have[x.row.name], tr = cur;
      if (!cur || cur._sig !== html) {
        tr = rowFromHtml(html);
        var tok2 = cur && cur.contains(document.activeElement) ? focusToken(document.activeElement) : null;
        if (cur) body.replaceChild(tr, cur);
        if (tok2) refocus(tr, tok2);
      }
      if (body.children[at] !== tr) body.insertBefore(tr, body.children[at] || null);
      at++;
    });
    while (body.children.length > at) body.removeChild(body.lastChild);
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6" class="pkg-empty">' + (S.local ? 'None: no theme uses a package beyond the base.' : 'None needed.') + '</td></tr>';
    }
    var sysHtml = sysRows.map(function (x) { return packageRow(x.row, x.state); }).join('');
    var sysBody = panel.querySelector('[data-pkg-sys]');
    if (sysBody._sig !== sysHtml) { sysBody._sig = sysHtml; sysBody.innerHTML = sysHtml; }
    panel.querySelector('[data-pkg-sys-head]').hidden = !sysRows.length;
  }
  function flashPackages() {
    var panel = root.querySelector('[data-package-panel]');
    if (!panel) return;
    panel.classList.remove('flash'); void panel.offsetWidth; panel.classList.add('flash');
  }
  // the editor opens below every theme: take the person to it, and say it is there
  function revealEditor() {
    var box = root.querySelector('section.edit');
    if (!box) return;
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    box.scrollIntoView({block: 'start', behavior: reduced ? 'auto' : 'smooth'});
    var h = box.querySelector('h2');
    if (h) { h.setAttribute('tabindex', '-1'); try { h.focus({preventScroll: true}); } catch (e) {} }
    box.classList.remove('flash'); void box.offsetWidth; box.classList.add('flash');
  }
  function revealPackages(focus) {
    var panel = root.querySelector('[data-package-panel]');
    if (!panel) return;
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    panel.scrollIntoView({block: 'center', behavior: reduced ? 'auto' : 'smooth'});
    try { (focus || panel.querySelector('[data-pkg-said]')).focus({preventScroll: true}); } catch (e) {}
  }
  function refreshThemeNeeds() {
    Array.prototype.forEach.call(root.querySelectorAll('[data-theme-missing]'), function (box) {
      var name = box.getAttribute('data-theme-missing');
      var theme = S.themes.filter(function (t) { return t.name === name; })[0];
      if (theme) box.innerHTML = missingMarkup(theme);
    });
  }

  // A missing package's cost is asked at once (the owner, 2026-09-28): metadata only, nothing
  // downloaded, but it reaches the TeX Live repository, so a quote is kept for the session.
  function quoteFrom(row, cacheable) {
    var q = Object.assign({}, row, {name: row.name});
    q.state = row.here === 'available' || row.here === 'parseh' ? 'available'
      : (row.repository === 'unreachable' ? 'unreachable'
        : (row.repository === 'unavailable' || row.can_get === false ? 'unavailable' : 'ready'));
    q.at = cacheable && q.state !== 'unreachable' && q.state !== 'available' ? Date.now() : 0;
    return q;
  }
  function loadQuotes() {
    try {
      var kept = JSON.parse(sessionStorage.getItem(QUOTES) || '{}');
      Object.keys(kept).forEach(function (name) {
        var one = kept[name];
        if (one && one.at && Date.now() - one.at < QUOTE_AGE && !packagePlans[name]) packagePlans[name] = one;
      });
    } catch (e) {}
  }
  function saveQuotes() {
    try {
      var kept = {};
      Object.keys(packagePlans).forEach(function (name) { if (packagePlans[name].at) kept[name] = packagePlans[name]; });
      sessionStorage.setItem(QUOTES, JSON.stringify(kept));
    } catch (e) {}
  }
  function quoteMessage(names) {
    var ready = names.filter(function (name) { return (packagePlans[name] || {}).state === 'ready'; });
    var lost = names.filter(function (name) { return (packagePlans[name] || {}).state === 'unreachable'; });
    var no = names.filter(function (name) { return (packagePlans[name] || {}).state === 'unavailable'; });
    if (lost.length && !ready.length) return 'Could not ask what ' + (lost.length === 1 ? lost[0] + ' costs' : lost.length + ' packages cost') + '. ' +
      ((packagePlans[lost[0]] || {}).why || 'The TeX Live repository could not be reached.') + ' Nothing has been downloaded.';
    if (ready.length) return ready.length + ' package' + (ready.length === 1 ? '' : 's') + ' ready to get' +
      (no.length ? '; ' + no.length + ' unavailable here' : '') + (lost.length ? '; ' + lost.length + ' could not be asked' : '') + '. Nothing has been downloaded.';
    return no.length ? 'These packages are not available from this TeX Live repository.' : 'Nothing needs to be downloaded.';
  }
  function askQuotes(names, o) {
    o = o || {};
    names = unique(names.map(function (name) { return String(name || '').trim(); })).filter(function (name) { return !packageAvailable(name); });
    if (!names.length) return false;
    var serial = ++packageSerial;
    names.forEach(function (name) {
      packageRequest[name] = serial;
      packagePlans[name] = Object.assign({}, packagePlans[name] || {}, {name: name, state: 'asking', at: 0});
    });
    if (o.reveal) packageMessage = 'Asking what ' + (names.length === 1 ? names[0] + ' costs' : names.length + ' packages cost') + '… Nothing has been downloaded.';
    renderPackages();
    if (o.reveal) { flashPackages(); revealPackages(); }
    function lose(why) {
      names.forEach(function (name) {
        if (packageRequest[name] === serial) packagePlans[name] = {name: name, state: 'unreachable', why: why, at: 0};
      });
    }
    function done(bad) {
      // a newer ask for every one of these names has taken over from this one
      if (!names.some(function (name) { return packageRequest[name] === serial; })) return;
      packageMessage = quoteMessage((o.all || unique(Object.keys(requiredPackages()).concat(names))).filter(function (name) {
        return (packagePlans[name] || {}).state !== 'asking';
      }));
      saveQuotes();
      renderPackages();
      if (o.reveal) {
        flashPackages();
        revealPackages(bad ? null : root.querySelector('[data-package-get]') || root.querySelector('[data-pkg-said]'));
      }
    }
    post('package-plan', {packages: names}, ASK_MS).then(function (p) {
      if (!p.ok) { lose(p.error || 'Could not ask what it costs.'); return done(true); }
      var seen = {};
      (p.packages || []).forEach(function (row) {
        if (!row || !row.name || packageRequest[row.name] !== serial) return;
        seen[row.name] = true;
        packagePlans[row.name] = quoteFrom(row, p.can !== false);
      });
      names.forEach(function (name) {
        if (packageRequest[name] === serial && !seen[name]) packagePlans[name] = {name: name, state: 'unreachable', at: 0,
          why: p.why || 'The TeX Live repository did not answer for this package.'};
      });
      done(false);
    }).catch(function () {
      lose('Parseh did not answer, so what it costs is not known. Check the connection and try again.');
      done(true);
    });
    return true;
  }
  // a person asked: nothing is asked twice, but an answer that did not come is asked for again
  function reviewPackages(names) {
    names = unique(names.map(function (name) { return String(name || '').trim(); }));
    var skipped = names.filter(packageAvailable);
    names = names.filter(function (name) { return !packageAvailable(name); });
    if (!names.length) {
      packageMessage = skipped.length ? 'That package is already available to this TeX.' : 'Enter a TeX Live package name first.';
      renderPackages(); flashPackages(); revealPackages(); return;
    }
    var ask = names.filter(function (name) { return !packagePlans[name] || packagePlans[name].state === 'unreachable'; });
    if (ask.length) { askQuotes(ask, {reveal: true, all: names}); return; }
    var waiting = names.filter(function (name) { return (packagePlans[name] || {}).state === 'asking'; });
    packageMessage = waiting.length ? 'Asking what ' + (waiting.length === 1 ? waiting[0] + ' costs' : waiting.length + ' packages cost') + '… Nothing has been downloaded.' : quoteMessage(names);
    renderPackages(); flashPackages();
    revealPackages(root.querySelector('[data-package-get]') || root.querySelector('[data-pkg-said]'));
  }
  function wantedQuotes() {
    var jobs = (S.packages || {}).jobs || {}, installed = (S.packages || {}).installed || {};
    return Object.keys(requiredPackages()).filter(function (name) {
      return !packagePlans[name] && !installed[name] && !jobs[name] && !packageAvailable(name);
    });
  }
  function editorMissing() {
    var el = root.querySelector('[data-edit-missing]');
    if (!el) return;
    var html = draft.features.length ? '<b>Not installed here:</b> ' + draft.features.map(esc).join(', ') +
      ' — <a href="#tex-packages" data-see-table>see the table</a>' : '';
    if (el._sig === html) return;
    el._sig = html; el.innerHTML = html; el.hidden = !html;
  }
  // The open editor's unsaved theme is read again on every change; only the table and one line follow it.
  function syncDraft() {
    var box = root.querySelector('section.edit');
    if (editing && box) {
      var t;
      try { t = current(); } catch (e) { t = editing.theme; }
      draft = themeNeed(t, draftNeeds(t));
    } else draft = {features: [], names: [], need: []};
    editorMissing();
    var ask = wantedQuotes();
    if (!ask.length || !askQuotes(ask)) renderPackages();
  }
  function scheduleDraft() { clearTimeout(draftTimer); draftTimer = setTimeout(syncDraft, 120); }

  function themeCard(t) {
    var isDef = t.name.toLowerCase() === S.default.toLowerCase();
    var comp = S.compilers[t.compiler];
    return '<div class="theme" data-theme="' + esc(t.name) + '"><h3>' + esc(t.name) +
      (isDef ? ' <small>(the default: a block naming no theme)</small>' : '') + '</h3>' +
      '<div class="facts">' + esc(t.compiler) + (comp ? '' : ' — not on this computer') + ' · ' +
      (t.packages.length ? esc(t.packages.join(', ')) : 'no packages') +
      (t.languages ? ' · text in the languages Parseh teaches' : '') +
      (t.font ? ' · font ' + esc(t.font) : '') + (t.preamble ? ' · a preamble of its own' : '') + '</div>' +
      '<div data-theme-missing="' + esc(t.name) + '">' + missingMarkup(t) + '</div>' +
      '<div class="row">' +
      '<button type="button" class="plain" data-edit="' + esc(t.name) + '" aria-label="Edit theme ' + esc(t.name) + '"' + dis('latex.theme') + '>Edit</button>' +
      '<button type="button" class="plain" data-rename="' + esc(t.name) + '" aria-label="Rename theme ' + esc(t.name) + '"' + dis('latex.rename') + '>Rename…</button>' +
      (isDef ? '' : '<button type="button" class="plain" data-default="' + esc(t.name) + '" aria-label="Make ' + esc(t.name) + ' the default theme"' + dis('latex.theme') + '>Make it the default</button>') +
      '<a class="plain" href="' + API + 'export?name=' + encodeURIComponent(t.name) + '" aria-label="Export theme ' + esc(t.name) + '">Export</a>' +
      (t.name.toLowerCase() === 'default' ? '' : '<button type="button" class="plain" data-delete="' + esc(t.name) + '" aria-label="Delete theme ' + esc(t.name) + '"' + dis('latex.theme') + '>Delete…</button>') +
      '</div><div class="said" data-said-for="' + esc(t.name) + '"></div></div>';
  }

  function editor() {
    if (!editing) return '';
    var t = editing.theme;
    var comps = ['xelatex', 'pdflatex', 'lualatex'].map(function (c) {
      return '<label><input type="radio" name="lx-comp" value="' + c + '"' + (t.compiler === c ? ' checked' : '') + '> ' + c +
        (S.compilers[c] ? '' : ' <small>(not on this computer)</small>') + '</label> ';
    }).join('');
    var groups = S.groups.map(function (g) {
      var rows = S.catalogue.filter(function (p) { return p.group === g[0]; }).map(function (p) {
        return '<label class="pk"><input type="checkbox" data-pkg="' + esc(p.id) + '"' + (t.packages.indexOf(p.id) >= 0 ? ' checked' : '') + '> <b>' + esc(p.name) +
          '</b> <small>' + esc(p.what) + ' <code>' + esc(p.example) + '</code></small></label>';
      }).join('');
      return '<div class="grp"><h4>' + esc(g[1]) + '</h4>' +
        (g[2] ? '<p class="grp-why">' + esc(g[2]) + '</p>' : '') + rows + '</div>';
    }).join('');
    return '<section class="edit"><h2>' + (editing.was ? 'The theme ' + esc(editing.was) : 'A new theme') + '</h2>' +
      (editing.was ? '' : '<div class="fld"><span>Its name — ' + esc(S.rule) + '</span><input type="text" data-name value="' + esc(t.name) + '"></div>') +
      '<div class="fld"><span>The compiler</span>' + comps + '</div>' +
      '<label class="pk"><input type="checkbox" data-languages' + (t.languages ? ' checked' : '') + '> <b>Text in the languages Parseh teaches</b> <small>Each language\'s face, as \\textfa{…}, \\textja{…}, \\texthi{…} and so on (xelatex or lualatex).</small></label>' +
      '<div class="fld"><span>A font of this computer for the drawing (xelatex or lualatex); empty for LaTeX\'s own</span><input type="text" data-font list="lx-fonts" value="' + esc(t.font) + '"><datalist id="lx-fonts"></datalist></div>' +
      '<div class="fld"><span>Packages</span>' + groups + '<div class="edit-missing" data-edit-missing aria-live="polite" hidden></div></div>' +
      '<div class="fld"><span>A preamble of its own, after the packages</span><textarea data-preamble>' + esc(t.preamble) + '</textarea></div>' +
      '<div class="fld"><span>Draw a sample with the theme as it is here</span><textarea data-sample>' + esc(S.sample) + '</textarea></div>' +
      '<div class="row"><button type="button" class="plain" data-draw-sample>Draw the sample</button><button type="button" class="go" data-save>Save the theme</button><button type="button" class="plain" data-cancel>Cancel</button></div>' +
      '<div class="said" data-edit-said></div><div data-sample-out></div></section>';
  }

  function current() {
    var box = root.querySelector('section.edit');
    var t = JSON.parse(JSON.stringify(editing.theme));
    var n = box.querySelector('[data-name]');
    if (n) t.name = n.value.trim();
    var c = box.querySelector('input[name="lx-comp"]:checked');
    if (c) t.compiler = c.value;
    t.languages = box.querySelector('[data-languages]').checked;
    t.font = box.querySelector('[data-font]').value.trim();
    t.packages = Array.prototype.map.call(box.querySelectorAll('[data-pkg]:checked'), function (x) { return x.getAttribute('data-pkg'); });
    t.preamble = box.querySelector('[data-preamble]').value;
    return t;
  }

  function draw() {
    var comps = Object.keys(S.compilers).map(function (c) {
      var v = S.compilers[c];
      return '<div data-compiler="' + esc(c) + '"><dt><code>' + esc(c) + '</code></dt><dd>' +
        (v ? '<span class="st ok"><i aria-hidden="true">✓</i> Available</span><span class="compiler-version">' + esc(v.version) + '</span>'
           : '<span class="st not"><i aria-hidden="true">—</i> Not on this computer</span>') +
        '</dd></div>';
    }).join('');
    root.innerHTML =
      '<section><h2>The themes</h2><p class="why">A latex block names its theme after the fence — <code>::::latex chemistry</code> — and a block that names none is drawn with the default. Each theme is compiled on its own: nothing here touches a <code>:::math</code> formula.</p>' +
      S.themes.map(themeCard).join('') +
      '<div class="row"><button type="button" class="plain" data-new' + dis('latex.theme') + '>New theme</button>' +
      '<button type="button" class="plain" data-import-open' + dis('latex.import') + '>Import a theme…</button>' +
      '<input type="file" data-import accept=".json,application/json" hidden' + dis('latex.import') + '></div>' +
      lock('latex.theme') + '<div class="said" data-top-said></div><div data-import-out></div></section>' +
      editor() +
      '<section><h2>TeX on this computer</h2><p class="why">' + esc(S.tex.said || '') + '. Parseh installs no TeX: it draws with the TeX this computer has, and puts the packages it gets for the drawings in its own folder, <code>texmf/</code>.</p><h3>Compilers</h3><dl class="tex-status">' + comps + '</dl>' +
      '<div data-package-panel></div></section>' +
      '<section><h2>How long a drawing may take</h2><p class="why">A drawing that has not finished by then is stopped, and its block says so.</p><div class="row"><input type="number" data-limit min="' + S.limits[0] + '" max="' + S.limits[1] + '" value="' + S.timeout + '"' + dis('latex.limit') + '> seconds <button type="button" class="go" data-save-limit' + dis('latex.limit') + '>Save</button></div>' + lock('latex.limit') + '<div class="said" data-limit-said></div></section>' +
      '<section><h2>The drawings kept</h2><p class="why"><span data-kept>' + (S.kept.drawings === 1 ? '1 saved drawing' : S.kept.drawings + ' saved drawings') + ', ' + (S.kept.drawings ? MB(S.kept.bytes) : '0 kB') + '</span>. A live preview is temporary and is kept only when its document or exercise is saved. Saved source owns its drawing; one no saved source names is let go after a day. Each is made again when its block, theme, packages or TeX change. A document, deck or book in a trash keeps none: what comes back from a trash is drawn again.</p><div class="row"><button type="button" class="plain" data-forget' + (forgetting ? ' disabled' : dis('latex.forget')) + '>Forget drawings nothing uses</button></div>' +
      '<div class="bar loose" role="progressbar" aria-label="Looking through every document, deck and note" data-forget-bar' + (forgetting ? '' : ' hidden') + '><i></i></div>' +
      '<div class="said" data-forget-said aria-live="polite">' + (forgetting ? FORGET_WORKING : '') + '</div></section>';
    syncDraft();
    var fl = root.querySelector('#lx-fonts');
    if (fl) post('fonts').then(function (r) { if (r.ok) fl.innerHTML = r.fonts.map(function (f) { return '<option value="' + esc(f) + '">'; }).join(''); });
  }

  function say(sel, text, bad) { var el = root.querySelector(sel); if (el) { el.textContent = text || ''; el.className = 'said' + (bad ? ' bad' : ''); } }

  root.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('[data-see-table]')) { e.preventDefault(); flashPackages(); revealPackages(); return; }
    var b = e.target.closest ? e.target.closest('button') : null;
    if (!b) return;
    var a = function (n) { return b.getAttribute(n); };
    if (a('data-import-open') !== null) { var picker = root.querySelector('[data-import]'); if (picker) picker.click(); return; }
    if (a('data-new') !== null) { editing = {was: null, theme: {name: q.get('make') || '', compiler: 'xelatex', packages: S.themes[0] ? S.themes[0].packages.slice() : [], languages: false, font: '', preamble: ''}}; draw(); revealEditor(); return; }
    if (a('data-edit')) { var t = S.themes.filter(function (x) { return x.name === a('data-edit'); })[0]; editing = {was: t.name, theme: JSON.parse(JSON.stringify(t))}; draw(); revealEditor(); return; }
    if (a('data-cancel') !== null) { editing = null; draw(); return; }
    if (a('data-draw-sample') !== null) {
      say('[data-edit-said]', 'Drawing…');
      post('sample', {theme: current(), tex: root.querySelector('[data-sample]').value}).then(function (r) {
        var out = root.querySelector('[data-sample-out]');
        if (!r.ok) { say('[data-edit-said]', r.error, true); return; }
        var res = r.result;
        say('[data-edit-said]', res.ok ? 'Drawn.' : res.said, !res.ok);
        out.innerHTML = (res.ok ? '<img class="sample" src="' + esc(res.url) + '" alt="the sample">' : (res.detail ? '<pre class="pre">' + esc(res.detail) + '</pre>' : '')) +
          '<details><summary>The whole preamble</summary><pre class="pre">' + esc(r.preamble) + '</pre></details>';
      });
      return;
    }
    if (a('data-save') !== null) {
      post('save', {theme: current(), was: editing.was}).then(function (r) {
        if (!r.ok) { say('[data-edit-said]', r.error, true); return; }
        editing = null;
        reload().then(function () {
          var saved = S.themes.filter(function (x) { return x.name === r.theme.name; })[0];
          var need = saved ? themeNeed(saved) : {features: []};
          if (!need.features.length) return;
          packageMessage = 'Saved the theme ' + saved.name + '. Not installed here: ' + need.features.join(', ') + '. Each is listed below with what it costs.';
          renderPackages(); flashPackages(); revealPackages();
        });
      });
      return;
    }
    if (a('data-default')) { post('default', {name: a('data-default')}).then(reload); return; }
    if (a('data-delete')) {
      if (!confirm('Delete the theme ' + a('data-delete') + '? A block that names it will say that this Parseh has no such theme.')) return;
      post('delete', {name: a('data-delete')}).then(function (r) { if (!r.ok) say('[data-top-said]', r.error, true); else reload(); });
      return;
    }
    if (a('data-rename')) {
      var old = a('data-rename');
      var neu = prompt('A new name for the theme ' + old + ' — ' + S.rule, old);
      if (!neu || neu === old) return;
      post('rename-plan', {old: old, new: neu}).then(function (p) {
        var where = '[data-said-for="' + old.replace(/"/g, '') + '"]';
        if (!p.ok || p.refused) { say(where, p.refused || p.error, true); return; }
        if (p.blocked.length) { say(where, 'Nothing can be renamed now: ' + p.blocked.join('; ') + '.', true); return; }
        if (!confirm('Renaming ' + old + ' to ' + neu + ' rewrites the name in ' + p.blocks + ' block' + (p.blocks === 1 ? '' : 's') + ': ' + p.said + '. No drawing changes. Go on?')) return;
        post('rename', {old: old, new: neu}).then(function (r) {
          if (!r.ok) { say(where, r.error, true); return; }
          reload().then(function () { say('[data-top-said]', 'Renamed ' + old + ' to ' + neu + ': ' + r.said + ' put right.'); });
        });
      });
      return;
    }
    if (a('data-install') !== null) { reviewPackages(a('data-install').split(' ').filter(Boolean)); return; }
    if (a('data-package-plan') !== null) {
      var n = root.querySelector('[data-pkgname]').value.trim();
      if (n) { packageAsked[n] = true; reviewPackages([n]); } else reviewPackages([]);
      return;
    }
    if (a('data-package-review')) { reviewPackages([a('data-package-review')]); return; }
    if (a('data-package-get')) { startPackages([a('data-package-get')]); return; }
    if (a('data-package-retry')) { startPackages([a('data-package-retry')]); return; }
    if (a('data-package-get-all')) { startPackages(a('data-package-get-all').split(' ').filter(Boolean)); return; }
    if (a('data-package-stop')) {
      post('package-stop', {package: a('data-package-stop')}).then(function (r) {
        if (!r.ok) { packageMessage = r.error || 'Could not stop that package.'; }
        else { S.packages = r; packageMessage = 'Stopped ' + a('data-package-stop') + '.'; }
        renderPackages();
      }).catch(function () { packageMessage = 'Could not stop that package.'; renderPackages(); });
      return;
    }
    if (a('data-remove')) { removing = a('data-remove'); renderPackages(); return; }
    if (a('data-remove-no') !== null) { removing = null; renderPackages(); return; }
    if (a('data-remove-yes')) {
      var removeName = a('data-remove-yes');
      post('package-remove', {package: removeName}).then(function (r) {
        removing = null;
        if (!r.ok) { packageMessage = r.error || 'Could not remove ' + removeName + '.'; renderPackages(); return; }
        S.packages = r;
        packageMessage = 'Removed ' + removeName + ' from Parseh.';
        renderPackages();
        refreshPackageFacts();
      }).catch(function () { removing = null; packageMessage = 'Could not remove ' + removeName + '.'; renderPackages(); });
      return;
    }
    if (a('data-save-limit') !== null) {
      post('limit', {seconds: +root.querySelector('[data-limit]').value}).then(function (r) { say('[data-limit-said]', r.ok ? 'Saved.' : r.error, !r.ok); });
      return;
    }
    if (a('data-forget') !== null) { forgetDrawings(b); return; }
    if (a('data-import-go') !== null) {
      var name = root.querySelector('[data-import-name]').value.trim();
      post('import', {data: importing, name: name}).then(function (r) {
        if (!r.ok) { say('[data-top-said]', r.error, true); return; }
        importing = null; root.querySelector('[data-import-out]').innerHTML = '';
        reload().then(function () { say('[data-top-said]', 'Imported as ' + r.theme.name + '.'); });
      });
    }
  });

  var importing = null;
  root.addEventListener('input', function (e) { if (editing && e.target.matches && e.target.matches('[data-font]')) scheduleDraft(); });
  root.addEventListener('change', function (e) {
    if (editing && e.target.closest && e.target.closest('section.edit')) scheduleDraft();
    var f = e.target.matches && e.target.matches('[data-import]') ? e.target.files[0] : null;
    if (!f) return;
    f.text().then(function (text) {
      post('import-read', {data: text}).then(function (r) {
        var out = root.querySelector('[data-import-out]');
        if (!r.ok) { say('[data-top-said]', r.error, true); return; }
        importing = text;
        // THE WHOLE PREAMBLE, SHOWN BEFORE THE IMPORT COMPLETES (the owner,
        // 2026-09-24): it is LaTeX this computer will run for every block
        // that names the theme
        out.innerHTML = '<section><h3>The theme ' + esc(r.theme.name) + ', as it would be compiled (' + esc(r.theme.compiler) + ')</h3>' +
          '<pre class="pre">' + esc(r.preamble) + '</pre>' +
          '<div class="fld"><span>Keep it as — ' + esc(S.rule) + (r.taken ? '. A theme called ' + esc(r.theme.name) + ' is here already: choose another name' : '') + '</span>' +
          '<input type="text" data-import-name value="' + esc(r.taken ? '' : r.theme.name) + '"></div>' +
          '<div class="row"><button type="button" class="go" data-import-go>Import this theme</button></div></section>';
      });
    });
  });

  // slow (every source is read), and a stopped server answers nothing: a bar, a deadline, no second press
  function forgetDrawings(btn) {
    if (forgetting) return;
    forgetting = true;
    btn.disabled = true;
    var bar = root.querySelector('[data-forget-bar]');
    if (bar) bar.hidden = false;
    say('[data-forget-said]', FORGET_WORKING);
    function over() {
      forgetting = false;
      var again = root.querySelector('[data-forget]'), gone = root.querySelector('[data-forget-bar]');
      if (again) again.disabled = !may('latex.forget');
      if (gone) gone.hidden = true;
    }
    post('forget', {}, 60000).then(function (r) {
      over();
      if (!r.ok) { say('[data-forget-said]', r.error || 'Parseh could not do that.', true); return; }
      var said = r.drawings ? drawings(r.drawings) + ' forgotten, ' + MB(r.bytes) + ' freed.' :
        'Nothing to forget: every saved drawing is still named by a document, deck or note.';
      reload().then(function () { say('[data-forget-said]', said); });
    }).catch(function () {
      over();
      say('[data-forget-said]', 'Parseh did not answer in a minute. It may still be working: read this page again to see how many drawings are kept.', true);
    });
  }
  function startPackages(names) {
    names = unique(names.map(function (name) { return String(name || '').trim(); })).filter(function (name) {
      return (packagePlans[name] || {}).state === 'ready';
    });
    if (!names.length) { packageMessage = 'Review a package cost before getting it.'; renderPackages(); return; }
    packageMessage = 'Getting ' + names.join(', ') + ' one at a time…';
    renderPackages();
    post('package-get', {packages: names}).then(function (st) {
      if (!st.ok) { packageMessage = st.error || 'Could not start getting those packages.'; renderPackages(); return; }
      S.packages = st;
      packageMessage = 'Getting ' + names.join(', ') + ' one at a time…';
      renderPackages();
      pollPackages();
    }).catch(function () { packageMessage = 'Could not start getting those packages.'; renderPackages(); });
  }
  function refreshPackageFacts() {
    post('state').then(function (v) {
      if (!v.ok) return;
      S = v;
      syncDraft();
      refreshThemeNeeds();
    });
  }
  function pollPackages() {
    if (polling) return;
    polling = true;
    function check() {
      post('package-status').then(function (st) {
        if (!st.ok) { packageMessage = st.error || 'Could not check package progress.'; polling = false; renderPackages(); return; }
        S.packages = st;
        renderPackages();
        var busy = Object.keys(st.jobs || {}).some(function (name) {
          var job = st.jobs[name] || {};
          return job.running || job.state === 'queued' || job.state === 'waiting' || job.state === 'running';
        });
        if (busy) { setTimeout(check, 1000); return; }
        polling = false;
        refreshPackageFacts();
      }).catch(function () { packageMessage = 'Could not check package progress.'; polling = false; renderPackages(); });
    }
    check();
  }

  loadQuotes();
  draw();
  if (q.get('theme')) { var t0 = S.themes.filter(function (x) { return x.name.toLowerCase() === q.get('theme').toLowerCase(); })[0]; if (t0 && may('latex.theme')) { editing = {was: t0.name, theme: JSON.parse(JSON.stringify(t0))}; draw(); revealEditor(); } }
  if (q.get('make') && may('latex.theme')) { root.querySelector('[data-new]').click(); }
  if (q.get('install') && may('latex.packages')) {
    var asked0 = q.get('install').split(/[\s,]+/).filter(Boolean);
    asked0.forEach(function (n) { packageAsked[n] = true; });
    reviewPackages(asked0);
  }
})();
"""
