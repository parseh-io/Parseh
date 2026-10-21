# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> Pictograms (ARASAAC) (TO-DO §8.40, W9, a0.4.2): the pictures the studio's exercises may
carry, fetched once and kept on this computer.

A DOOR OF ITS OWN, drawn the way Speech to text is (lib/speechpage.py) and answering the way the LaTeX
drawings do (lib/latexpage.py): the page, and one `api()` that serve.py's `/settings/api/arasaac/...`
routes call, each of them in lib/settingspage.py ROUTES.  The work is lib/getarasaac.py's.

ANY DEVICE THAT HAS BEEN LET IN MAY DO ALL OF IT -- get, update, stop, remove -- and the door's pill
says so (lib/settingspage.py SETTINGS says why: whoever presses the button, the only bytes that can
arrive are ARASAAC's own word lists and pictures, from the two hosts it names, and nothing a device sends
becomes a path or an address).  So this page draws no lock and no dead button.

WHAT THE PAGE SAYS BEFORE ANYBODY PRESSES A BUTTON, in this order: whose pictures these are and what
the licence asks (the credit in ARASAAC's own words, shared-alike and non-commercial said plainly,
the terms and the licence linked), then what is to be fetched -- the languages whose words find a
picture, and the size of the pictures -- with the size of it all, which is the shipped table of what
was measured on the real hosts and not a guess, and how long it takes.  A language ARASAAC has no
words in (Japanese), or hardly any (Hindi: one, and it is Spanish), is shown, and said not to be
offered, so that nobody wonders where it went.

THE ROWS AND THE BAR ARE THE READING HELP'S (lib/lookuppage.py ROW_JS and STYLE): a state that is a
glyph, a word and a colour; a bar that moves with the time left; Get it, Carry on, Stop, Remove.  One
button says what pressing it does, and a different fact is a different button: *Get it* (or *Carry on*,
or *Add the languages ticked*) fetches; *Update* looks for what ARASAAC has changed; *Remove…* is one
language's words or the whole folder; changing the size of the pictures is its own question, because
it replaces every picture.
"""
import html
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import getarasaac                                                # noqa: E402
import arasaacsearch                                             # noqa: E402
import languages                                                 # noqa: E402
import lookuppage                                                # noqa: E402
import settingspage                                              # noqa: E402

PAGE = getarasaac.SETTINGS_PAGE
GUIDE = getarasaac.GUIDE
# the three settings this page's buttons are, and only these (*update* is *get*: it fetches)
KEYS = ("arasaac.get", "arasaac.remove", "arasaac.stop")


def esc(s):
    return html.escape(str(s), quote=True)


def door_tags():
    """What the Settings hub says under this door: that nothing is installed, or what is.  Read
    from the manifest and the file names, never from a walk of the pictures."""
    mine = getarasaac.manifest()
    here = getarasaac.locales_here()
    if not mine and not here:
        return '<span class="tag">not installed</span>'
    if not mine.get("complete"):
        return '<span class="tag">part of it</span>'
    out = '<span class="tag on">%s pictograms</span>' % esc(format(mine.get("pictograms") or 0, ","))
    return out + "".join('<span class="tag on">%s</span>' % esc(loc) for loc in here)


def credit():
    """The credit and where it comes from, for the page and for /licences/: one record."""
    return {"text": getarasaac.CREDIT, "short": getarasaac.CREDIT_SHORT, "licence": getarasaac.LICENCE,
            "licence_url": getarasaac.LICENCE_URL, "terms": getarasaac.TERMS, "source": getarasaac.SOURCE}


def _bytes(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def language_rows(st):
    """Every language Parseh has, with what ARASAAC has in it: offered, or why not; the words and the
    pictograms they name (measured); what it costs to fetch; whether it is here.  English first, then
    the offered ones in the registry's order, then the ones that are not."""
    rows = []
    for L in languages.LANGS.values():
        ok, why = getarasaac.offered(L.code)
        got = getarasaac.MEASURED["locales"].get(L.code)
        have = st["locales"].get(L.code)
        rows.append({"code": L.code, "name": L.name, "native": L.native, "rtl": L.dir == "rtl",
                     "offered": ok, "why": why, "words": got["entries"] if got else None,
                     "covered": got["covered"] if got else None,
                     "raw": (got or getarasaac.GUESS)["raw"], "measured": bool(got),
                     "here": have is not None, "fetched": (have or {}).get("fetched") or "",
                     "kept_bytes": _bytes(getarasaac.index_path(L.code)) if have is not None else 0,
                     "base": L.code == getarasaac.BASE_LOCALE})
    rows.sort(key=lambda r: (not r["base"], not r["offered"]))
    return rows


def view(where="", device="", picked=None, resolution=None):
    """Everything the page draws, in one answer: drawn from it when it opens and from the next one every
    time it asks how things stand (`state`).  `plan` is for what is ticked: the languages and the size
    given, else what is here, else English at 300 pixels."""
    st = getarasaac.status()
    locales = list(picked) if picked else (list(st["locales"]) or [getarasaac.BASE_LOCALE])
    px = resolution or st["resolution"] or getarasaac.DEFAULT_RESOLUTION
    try:
        plan = getarasaac.plan(locales, px)
    except getarasaac.ArasaacError:
        plan = getarasaac.plan([getarasaac.BASE_LOCALE], getarasaac.DEFAULT_RESOLUTION)
    try:
        free = getarasaac.disk_free(getarasaac.folder())
    except OSError:
        free = None
    return {"ok": True, "arasaac": st, "plan": plan, "room": getarasaac.room(plan),
            "languages": language_rows(st), "credit": credit(),
            "sizes": [{"px": px_, "mean": getarasaac.MEASURED["png"][px_], "default": px_ == getarasaac.DEFAULT_RESOLUTION}
                      for px_ in getarasaac.RESOLUTIONS],
            "pictograms": getarasaac.MEASURED["pictograms"], "measured": getarasaac.MEASURED["date"],
            "seconds": getarasaac.SECONDS_PER_PICTURE, "hosts": list(getarasaac.HOSTS), "guide": GUIDE,
            "kept": st["bytes"], "free": free, "where": where or "", "device": device or "",
            "may": {k: settingspage.may(k, where) for k in KEYS}}


def api(what, body, where=""):
    """One route's work -> (status, answer).  Who may was asked first, of lib/settingspage.py ROUTES."""
    body = body if isinstance(body, dict) else {}
    try:
        if what == "state":
            return 200, view(where, body.get("device") or "")
        if what == "search":
            # the picker's search (lib/arasaacsearch.py): a read, open to every device let in, like the state
            return 200, arasaacsearch.search(body.get("q", ""), body.get("locales"), body.get("display"),
                                             body.get("offset"), body.get("limit"), body.get("sensitive") is True)
        if what == "plan":
            px = body.get("resolution", getarasaac.DEFAULT_RESOLUTION)
            locales = getarasaac.check_locales(body.get("locales", [getarasaac.BASE_LOCALE]))
            plan = getarasaac.plan(locales, getarasaac.check_resolution(px), update=bool(body.get("update")))
            return 200, dict(plan, ok=True, room=getarasaac.room(plan))
        if what == "get":
            answer, status = getarasaac.start(body.get("locales", []), body.get("resolution", getarasaac.DEFAULT_RESOLUTION))
            return status, answer
        if what == "update":
            answer, status = getarasaac.start([], getarasaac.DEFAULT_RESOLUTION, update=True)
            return status, answer
        if what == "stop":
            return 200, {"ok": True, "stopped": getarasaac.stop()}
        if what == "remove":
            if body.get("all") is True:
                getarasaac.remove()
            elif isinstance(body.get("locale"), str):
                getarasaac.remove(body["locale"])
            else:
                return 400, {"ok": False, "error": "Say what to remove: one language's words, or everything."}
            return 200, {"ok": True}
    except getarasaac.ArasaacError as e:
        return (409 if e.code == "busy" else 400), {"ok": False, "error": e.say, "code": e.code}
    return 404, {"ok": False, "error": "%s has no such request." % settingspage.NAME}


def page(where="", device=""):
    """/settings/arasaac/, the whole page."""
    v = view(where, device)
    main = """<main class="settings rh ar">
%(doors)s
<h1 class="idx">pictograms (ARASAAC)</h1>
<p class="whomay">%(gate)s <span>Nothing is fetched until you press a button here, and what goes with the request is
Parseh&rsquo;s name and nothing of yours. Any device that has been let in may get, update, stop or remove what is on this
page. Whoever presses the button, only ARASAAC&rsquo;s own word lists and pictures can be fetched, from the two
hosts named below.</span></p>
<div id="ar-band" class="band"></div>
<div id="ar"><p class="rh-wait">Reading what is here&hellip;</p></div>
<p class="foot">What is fetched here lives in the <code>arasaac/</code> folder &mdash; <code>pictograms/</code> for
the pictures, <code>index.&lt;language&gt;.json</code> for the words, and <code>LICENSE-ARASAAC.txt</code>, which
carries the credit &mdash; kept by every update and left out of backups. It comes from
<code>api.arasaac.org</code> (the words) and <code>static.arasaac.org</code> (the pictures) and from nowhere else;
once it is here, everything works with no connection. Every licence is also on the
<a href="/licences/">licences</a> page. <a href="%(guide)s" data-guide>How the pictograms are used</a>, in the
guide.</p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "gate": settingspage.gate(KEYS), "guide": esc(GUIDE)}
    script = ('<script id="ar-state" type="application/json">%s</script>\n<script>%s</script>'
              % (settingspage._in_script(v), SCRIPT))
    return settingspage.frame("Pictograms (ARASAAC) &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; pictograms (ARASAAC)',
                              "Pictograms", GUIDE, main, style=lookuppage.STYLE + STYLE, script=script)


STYLE = r"""
.ar .whomay{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap;margin:.2rem 0 1rem;font-size:13.5px;color:var(--dim)}
.ar .whomay .gate{flex:none}
.ar section.about{padding:14px 16px}
.ar .about p{margin:.35rem 0;font-size:14px}
.ar .about a{color:var(--accent)}
.ar .about .credit{margin:.5rem 0;padding:8px 12px;border-inline-start:3px solid var(--accent);background:var(--boxbg);
  border-radius:0 8px 8px 0;font-size:13.5px}
.ar .about .credit q{quotes:none;display:block}
.ar .about ul{margin:.4rem 0 .2rem;padding-inline-start:1.25rem;font-size:14px}
.ar .about li{margin:.2rem 0}
.ar section.pick{padding:12px 16px 14px}
.ar .pick h3{font:600 14px/1.3 inherit;margin:.2rem 0 .4rem}
.ar .pick .lead{font-size:13px;color:var(--dim);margin:0 0 .5rem}
.ar .lang{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:0 10px;align-items:center;padding:3px 0;
  border-top:1px solid var(--rule);font-size:14px}
.ar .lang:first-of-type{border-top:0}
.ar .pickline{display:flex;gap:10px;align-items:center;min-height:34px;cursor:pointer}
.ar span.pickline{cursor:default}
.ar .pickline input{margin:0;width:20px;height:20px;flex:none}
.ar .pickline .mark{width:20px;flex:none;text-align:center;color:var(--ok);font-weight:700}
.ar .lang .nm{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.ar .lang .nat{font-size:17px;color:var(--accent)}
.ar .lang .facts{grid-column:1;padding-inline-start:30px;color:var(--dim);font-size:12.5px;font-variant-numeric:tabular-nums;
  padding-bottom:4px}
.ar .lang.no{color:var(--dim)}
.ar .lang.no .nat{color:var(--dim)}
.ar .lang .act{grid-row:1;grid-column:2}
.ar .lang .ask{grid-column:1/-1;margin:2px 0 6px}
.ar .size{display:flex;gap:6px 18px;flex-wrap:wrap;margin:.3rem 0 .6rem}
.ar .size label{display:flex;gap:8px;align-items:center;font-size:14px;min-height:34px;cursor:pointer}
.ar .size label small{color:var(--dim);font-size:12.5px}
.ar .plan{margin:.6rem 0;padding:10px 12px;background:var(--boxbg);border:1px solid var(--rule);border-radius:8px;font-size:13.5px;
  font-variant-numeric:tabular-nums}
.ar .plan b{font-weight:600}
.ar .plan.stale{opacity:.55}
/* a box and a dot are drawn in the colours of the theme the page is in, not the system's */
:root[data-theme=dark] .ar input{color-scheme:dark}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]):not([data-theme=sepia]) .ar input{color-scheme:dark}}
.ar .plan .bad{color:var(--danger)}
.ar .plan .small{display:block;color:var(--dim);font-size:12.5px;margin-top:3px}
.ar .go-row{display:flex;gap:8px 10px;flex-wrap:wrap;align-items:center;margin-top:.5rem}
.ar .it{padding:12px 16px}
.ar .it .it-act{justify-content:flex-start}
.ar a.plain{text-decoration:none}
.ar .band .who a{color:var(--accent)}
@media (max-width:620px){
  .ar .go-row button,.ar .go-row a{flex:1 1 auto}
  .ar .pickline,.ar .size label{min-height:44px}
  .ar .pickline input,.ar .size input{width:24px;height:24px}
}
"""

SCRIPT = r"""
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('ar-state').textContent);
  var root = document.getElementById('ar');
  var band = document.getElementById('ar-band');
  var asking = null;       // a question put to the person: {kind: 'remove'|'size'|'bad', ...}
  var polling = null;
  var pick = {locales: {}, px: 300};     // what is ticked, and the size of the pictures
  var plan = S.plan;                      // what that costs, from the server (the shipped table: nothing is asked of ARASAAC)
  var room = S.room || '';
  var planning = 0;
  var stale = false;                      // the plan on the screen is for an earlier choice
  /*ROW_JS*/

  function may(setting) { return !S.may || S.may[setting] !== false; }
  function ST() { return S.arasaac; }
  function J() { return ST().job || {}; }
  function num(n) { return Number(n || 0).toLocaleString('en'); }
  function size(n) {
    if (n == null) return '';
    if (n >= 1e9) return (n / 1e9).toFixed(1) + ' GB';
    if (n >= 1e7) return Math.round(n / 1e6) + ' MB';
    if (n >= 1e5) return (n / 1e6).toFixed(1) + ' MB';
    return Math.max(1, Math.round(n / 1e3)) + ' kB';
  }
  function said(e) { return String(e || '').replace(/^getarasaac:\s*/, ''); }
  function day(s) {
    if (!s) return '';
    var d = new Date(String(s).slice(0, 10) + 'T12:00:00');
    return isNaN(d) ? esc(s) : d.toLocaleDateString('en-GB', {day: 'numeric', month: 'long', year: 'numeric'});
  }
  function minutes(files) {
    var t = files * (S.seconds || 0.05);
    if (t < 90) return 'about a minute';
    return 'about ' + Math.round(t / 60) + ' minutes';
  }
  function running() { return !!J().running; }

  /* ---- what is ticked starts as what is here (English where nothing is) */
  (function () {
    var here = Object.keys(ST().locales || {});
    (here.length ? here : ['en']).forEach(function (c) { pick.locales[c] = true; });
    pick.px = ST().resolution || 300;
  })();
  function ticked() { return Object.keys(pick.locales).filter(function (c) { return pick.locales[c]; }); }
  function here(code) { return !!(ST().locales || {})[code]; }

  /* ---- the plan is the server's, asked again when a tick or the size changes */
  function replan() {
    var mine = ++planning;
    // what is on the screen is the plan of what was ticked a moment ago: it says so until the new one comes
    post('plan', {locales: ticked(), resolution: pick.px}).then(function (j) {
      if (mine !== planning || !j || !j.ok) return;
      plan = j; room = j.room || ''; stale = false; drawn = null; draw();
    }).catch(function () {});
    stale = true;
  }

  /* ---- the state of the whole, in a pill */
  function stateOf() {
    var j = J(), s = ST();
    if (j.running) {
      var pc = j.total ? Math.min(99, Math.floor(100 * j.done / j.total)) : null;
      return {cls: 'run', glyph: '↓', word: (j.update ? 'Updating' : 'Downloading') + (pc != null ? ' · ' + pc + '%' : '')};
    }
    if (s.state === 'installed') return {cls: 'ok', glyph: '✓', word: 'Installed'};
    if (s.state === 'partial') return {cls: 'old', glyph: '↻', word: 'Part of it is here'};
    if (s.state === 'other') return {cls: 'bad', glyph: '!', word: 'Made by another Parseh'};
    return {cls: 'not', glyph: '○', word: 'Not yet'};
  }

  /* ---- whose pictures these are: before anything else, and always */
  function about() {
    var c = S.credit;
    return '<section class="shared about"><p><b>Whose pictures these are.</b> They are ARASAAC&rsquo;s &mdash; the Aragonese Portal of ' +
      'Augmentative and Alternative Communication &mdash; drawn by Sergio Palao, the property of the Government of Aragón, and shared under ' +
      '<a href="' + esc(c.licence_url) + '" rel="noopener" target="_blank">' + esc(c.licence) + '</a>. What that asks of you:</p><ul>' +
      '<li><b>Name them.</b> Wherever you use a pictogram, ARASAAC, its author and the licence are to be named, in either of the two ' +
      'forms its <a href="' + esc(c.terms) + '" rel="noopener" target="_blank">terms</a> give.</li>' +
      '<li><b>Not for sale.</b> No use within any product or publication for commercial purposes.</li>' +
      '<li><b>Shared on the same terms.</b> What you make with them goes to others under the same licence: a document that holds them is for ' +
      'sharing as it is, credit and all, and never for selling.</li></ul>' +
      '<p class="credit"><q>' + esc(c.text) + '</q></p>' +
      '<p>The same words are written into <code>arasaac/LICENSE-ARASAAC.txt</code> when a download ends. ' +
      '<a href="' + esc(c.terms) + '" rel="noopener" target="_blank">ARASAAC&rsquo;s terms of use</a> · ' +
      '<a href="' + esc(c.licence_url) + '" rel="noopener" target="_blank">the licence</a> · ' +
      '<a href="' + esc(S.guide) + '" data-guide>what it means for your documents</a>.</p></section>';
  }

  /* ---- the languages, each with what ARASAAC has in it */
  function langRow(L) {
    var id = 'lang-' + L.code, q = asking && asking.kind === 'remove' && asking.locale === L.code ? asking : null;
    var name = '<span class="nm"><span class="nat" lang="' + esc(L.code) + '"' + (L.rtl ? ' dir="rtl"' : '') + '>' + esc(L.native) +
      '</span>' + (L.native === L.name ? '' : '<span>' + esc(L.name) + '</span>') + '</span>';
    if (!L.offered) {
      return '<div class="lang no" data-lang="' + esc(L.code) + '"><span class="pickline"><span class="mark"></span>' + name + '</span>' +
        '<span class="act"></span><span class="facts">' + esc(L.why) + '</span></div>';
    }
    var facts = [];
    if (L.words != null) facts.push(num(L.words) + ' words, naming ' + (L.covered >= S.pictograms ? 'every pictogram' :
      num(L.covered) + ' of ' + num(S.pictograms) + ' pictograms'));
    if (L.here) facts.push('installed' + (L.fetched ? ' · fetched ' + day(L.fetched) : ''));
    else facts.push(size(L.raw) + ' to fetch' + (L.measured ? '' : ' (about: not measured)'));
    // A BOX IS PRESSED THROUGH ITS LABEL, which is the whole of the line it is on
    var head, act = '';
    if (L.here) {
      head = '<span class="pickline"><span class="mark" aria-hidden="true">✓</span>' + name + '</span>';
      if (may('arasaac.remove') && !running()) act = '<button class="plain" type="button" data-remove-lang="' + esc(L.code) +
        '" aria-label="Remove the ' + esc(L.name) + ' words">Remove…</button>';
    } else {
      head = '<label class="pickline" for="' + id + '"><input type="checkbox" id="' + id + '" data-tick="' + esc(L.code) + '"' +
        (pick.locales[L.code] ? ' checked' : '') + (running() || !may('arasaac.get') ? ' disabled' : '') + '>' + name + '</label>';
    }
    var ask = '';
    if (q) ask = '<div class="ask"><span class="said">Remove the ' + esc(L.name) + ' words? It frees ' + size(L.kept_bytes || 0) +
      '; the pictures stay. Getting them back is a ' + size(L.raw) + ' download.' +
      '</span>' +
      '<button class="danger" type="button" data-yes-lang="' + esc(L.code) + '">Remove</button>' +
      '<button class="plain" type="button" data-cancel>Keep it</button></div>';
    return '<div class="lang" data-lang="' + esc(L.code) + '">' + head + '<span class="act">' + act + '</span>' +
      '<span class="facts">' + facts.join(' · ') + '</span>' + ask + '</div>';
  }

  function sizes() {
    return '<div class="size" role="radiogroup" aria-label="size of the pictures">' + S.sizes.map(function (z) {
      var all = z.mean * S.pictograms;
      return '<label><input type="radio" name="px" value="' + z.px + '" data-px="' + z.px + '"' + (pick.px === z.px ? ' checked' : '') +
        (running() || !may('arasaac.get') ? ' disabled' : '') + '> <span><b>' + z.px + ' pixels</b> <small>about ' + size(all) +
        (z.default ? ' · the one to start with' : ' · sharper on a large page') + '</small></span></label>';
    }).join('') + '</div>';
  }

  /* ---- what it costs, said before the button */
  function planLine() {
    if (!plan) return '';
    var p = plan, bits = [], files = p.pictures ? p.pictures.files : 0;
    var words = Object.keys(p.words || {});
    var rest = (p.download || 0) - (p.have || 0);
    if (!files && !words.length) return '<div class="plan' + (stale ? ' stale' : '') + '">Everything ticked is here already.</div>';
    var lead = '<b>' + (p.measured ? '' : 'about ') + size(rest) + '</b> to fetch';
    var parts = [];
    if (words.length) parts.push(size(words.reduce(function (n, k) { return n + p.words[k].raw; }, 0)) + ' of word lists');
    if (files) parts.push(num(files) + ' pictures at ' + p.resolution + ' pixels, about ' + size(p.pictures.bytes));
    if (parts.length) lead += ' &mdash; ' + parts.join(' and ');
    var more = [];
    if (files) more.push('takes ' + minutes(files) + ', one picture at a time');
    if (p.kept != null) more.push('kept as about ' + size(p.kept));
    if (p.have) more.push(size(p.have) + ' of the pictures are here already');
    return '<div class="plan' + (stale ? ' stale' : '') + '">' + lead + '.<span class="small">' + more.join(' · ') + '</span>' +
      (p.replaces ? '<span class="small">The pictures that are here are replaced: they are all of one size.</span>' : '') +
      (room ? '<span class="small bad">' + esc(room) + '</span>' : '') + '</div>';
  }

  /* ---- the bar, while it runs */
  function progress() {
    var j = J();
    if (!j.running) return '';
    sample('job', j);
    var pc = j.total ? Math.min(100, 100 * j.done / j.total) : null, bits = [];
    if (j.phase === 'pictures') bits.push(num(j.done) + ' of ' + num(j.total) + ' pictures');
    else bits.push(j.total ? size(j.done) + ' of ' + size(j.total) + ' of the word list' : size(j.done || 0) + ' of the word list so far');
    var lt = left('job', j);
    if (lt) bits.push('<b>' + lt + '</b>');
    else if (j.total) bits.push('<span class="q">working out the time left</span>');
    return '<div class="it busy" data-row="job"><div class="it-main"><div class="it-head"><span class="it-name">' +
      (j.update ? 'Looking for what has changed' : 'Fetching the pictograms') + '</span>' + pill('run', '↓', 'Downloading') + '</div>' +
      '<div class="it-facts">' + bits.join(' · ') + '</div>' +
      '<div class="bar' + (pc == null ? ' loose' : '') + '" role="progressbar" aria-label="fetching the pictograms"' +
      (pc != null ? ' aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round(pc) + '"><i style="width:' + pc.toFixed(1) + '%"></i>' : '><i></i>') +
      '</div>' + (j.say ? '<div class="note">' + esc(j.say) + '</div>' : '') + '</div><span></span><div class="it-act">' +
      (may('arasaac.stop') ? '<button class="plain" type="button" data-stop aria-label="Stop fetching the pictograms">Stop</button>' : '') +
      '</div></div>';
  }

  /* ---- the buttons: one that fetches, saying what it fetches; and the others, each their own */
  function actions() {
    var s = ST(), j = J(), out = '', note = '', q = asking;
    if (running()) return '';
    if (q && q.kind === 'size') {
      return '<div class="ask"><span class="said">Fetch every picture again at ' + pick.px + ' pixels? ' + num(plan && plan.total || S.pictograms) +
        ' pictures are replaced, about ' + size(plan && plan.pictures && plan.pictures.bytes) + ' to fetch.</span>' +
        '<button class="go" type="button" data-yes-size>Fetch again</button><button class="plain" type="button" data-cancel>Keep what is here</button></div>';
    }
    if (q && q.kind === 'removeall') {
      return '<div class="ask"><span class="said">Remove all the pictograms? It frees ' + size(s.bytes) + '; getting them back is a ' +
        size((plan && plan.download) || 0) + ' download.</span><button class="danger" type="button" data-yes-all>Remove</button>' +
        '<button class="plain" type="button" data-cancel>Keep it</button></div>';
    }
    if (q && q.kind === 'bad') {
      out += '<div class="ask bad"><span class="said">' + esc(q.said) + '</span><button class="plain" type="button" data-cancel>All right</button></div>';
    }
    if (j.error) note = '<div class="note bad">The last try stopped: ' + esc(said(j.error)) + '</div>';
    else if (j.stopped) note = '<div class="note">You stopped it' + (j.done && j.phase === 'pictures' ? ' at ' + num(j.done) + ' pictures' : '') +
      '; what came is kept, and pressing it again carries on from there.</div>';
    var go = '', extra = ticked().filter(function (c) { return !here(c); });
    var resized = s.resolution && s.resolution !== pick.px;
    if (may('arasaac.get')) {
      if (s.state === 'absent' || s.state === 'other') {
        go = '<button class="go" type="button" data-get ' + (ticked().length ? '' : 'disabled ') + 'aria-label="Get it: the pictograms">' +
          (j.error ? 'Try again' : 'Get it') + '</button>';
      } else if (s.state === 'partial') {
        go = '<button class="go" type="button" data-get>' + (j.error ? 'Try again' : 'Carry on') + '</button>';
      } else if (resized) {
        go = '<button class="go" type="button" data-resize>Fetch again at ' + pick.px + ' pixels…</button>';
      } else if (extra.length) {
        go = '<button class="go" type="button" data-get>Add ' + (extra.length === 1 ? 'the language' : extra.length + ' languages') + ' ticked</button>';
      }
      if (s.state === 'installed' && !resized) {
        go += '<button class="plain" type="button" data-update title="Ask ARASAAC which pictograms are new or changed, and fetch only those">Update</button>';
      }
    }
    var rm = '';
    if (may('arasaac.remove') && (s.state !== 'absent' || (s.pictograms || s.files))) {
      rm = '<button class="plain" type="button" data-remove-all>Remove…</button>';
    }
    var last = s.finished && s.state === 'installed' ? '<span class="note">Fetched ' + day(s.finished) +
      (s.missing ? '; ARASAAC has no picture of ' + num(s.missing) + ' of them at this size' : '') + '.</span>' : '';
    return out + note + '<div class="go-row">' + go + rm + last + '</div>';
  }

  function rowOfState() {
    // (while it runs the bar below says all of this, and the counts here would only be a poll old)
    if (running()) return '';
    var s = ST(), st = stateOf();
    var facts = [];
    if (s.state === 'installed' || s.state === 'partial') {
      facts.push(num(s.files) + ' of ' + num(s.pictograms) + ' pictures · ' + s.resolution + ' pixels · ' + size(s.bytes) + ' kept');
      if (s.state === 'partial' && s.pending) facts.push(num(s.pending) + ' still to fetch');
    }
    if (s.state === 'other') facts.push('Made by a Parseh with another shape of file: press Get it to make it again, or remove it.');
    if (!facts.length) return '';
    // LOOKING AT THEM is not fetching them: its own button, and only where there is a picture to look at (the picker, a0.5.3)
    var look = s.files ? '<button class="go" type="button" data-look title="Search the pictograms by a word and look at them, as large as you like">' +
      'Look through the pictograms…</button>' : '';
    return '<div class="it" data-row="whole"><div class="it-main"><div class="it-head"><span class="it-name">The pictograms</span>' +
      pill(st.cls, st.glyph, st.word) + '</div><div class="it-facts">' + facts.join(' · ') + '</div></div><span></span><div class="it-act">' + look + '</div></div>';
  }

  var drawn = null, held = null;
  // WHICH CONTROL HAS THE KEYBOARD: its first data-… attribute names it, and where it goes when the page is drawn again
  function focusToken(el) {
    if (!el || !el.attributes) return null;
    for (var i = 0; i < el.attributes.length; i++) {
      if (el.attributes[i].name.indexOf('data-') === 0) return {name: el.attributes[i].name, value: el.attributes[i].value};
    }
    return null;
  }
  function refocus(tok) {
    var found = null;
    Array.prototype.forEach.call(root.querySelectorAll('[' + tok.name + ']'), function (el) {
      if (!found && el.getAttribute(tok.name) === tok.value) found = el;
    });
    found = found || root.querySelector('.ask [data-cancel]') || root.querySelector('button:not(:disabled)');
    try { if (found) found.focus({preventScroll: true}); } catch (e) {}
  }
  function draw() {
    var rows = S.languages.map(langRow).join('');
    var html = about() + rowOfState() + progress() +
      '<h2 class="part">What to fetch</h2><section class="shared pick"><h3>Languages</h3>' +
      '<p class="lead">A picture is found by a word, so the studio needs ARASAAC&rsquo;s words. English is ticked to begin with: it names every ' +
      'pictogram. Tick the languages your documents are written in as well, if you like; a pictogram has the same number in every language.</p>' +
      rows + '<h3>Size of the pictures</h3>' + sizes() + planLine() + actions() + '</section>';
    drawBand();
    if (html === drawn) return;
    drawn = html;
    var now = document.activeElement, inside = now && root.contains(now) && now !== root;
    var tok = inside ? focusToken(now) : (!now || now === document.body ? held : null);
    held = null;
    root.innerHTML = html;
    if (tok) refocus(tok);
  }
  function drawBand() {
    var who = S.where === 'self' ? 'You are on <b>the computer Parseh runs on</b>.' :
      'You are on <b>' + esc(S.device || 'another device') + '</b>, ' + (S.where === 'vpn' ? 'on a VPN' : 'let in over the Wi-Fi') + '.';
    who += ' ' + (may('arasaac.get') && may('arasaac.remove') ? 'You may get, update, stop and remove anything on this page.' : 'Some of this page is changed on the computer Parseh runs on.');
    band.innerHTML = '<div><div class="n">' + (ST().bytes ? size(ST().bytes) : '0 MB') + '</div><div class="l">kept for pictograms</div></div>' +
      (S.free != null ? '<div><div class="n">' + size(S.free) + '</div><div class="l">free on this computer</div></div>' : '<div></div>') +
      '<div class="who">' + who + '</div>';
  }

  /* ---- asking the server */
  function post(what, body) {
    return fetch('/settings/api/arasaac/' + what, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})})
      .then(function (r) { return r.json().then(function (j) { j.status = r.status; return j; }); });
  }
  function busy() { return running() || !!ST().job && ST().job.running; }
  function refresh() {
    return post('state', {}).then(function (j) {
      if (!j || !j.ok) return;
      var was = busy();
      S = j;
      replanOnChange(was);
      draw();
      if (busy() || was) schedule(busy() ? 1000 : 0);
      if (was && !busy() && window.ParsehActivity) ParsehActivity.poke(200);
    // ONE FAILED ANSWER IS NEVER A VERDICT: while something was being fetched the next look is asked for all the same
    }).catch(function () { if (busy()) schedule(2000); });
  }
  function replanOnChange(was) { if (was && !running()) { plan = S.plan; room = S.room || ''; } }
  function schedule(ms) { clearTimeout(polling); if (ms) polling = setTimeout(refresh, ms); }
  function kick() {
    if (window.ParsehActivity) ParsehActivity.poke(200);
    refresh().then(function () { schedule(1000); });
  }
  function lost() { asking = {kind: 'bad', said: 'The server did not answer.'}; drawn = null; draw(); }

  /* ---- looking through them: the picker (lib/pictograms.js) with nothing to add, over this page.  The script is fetched
     when the button is pressed, as the studio's pages fetch it: no tag of this page asks for it, so nothing of the page waits
     on it, and it is asked for with a deadline */
  var picker = null;
  function loadPicker() {
    if (window.ParsehPictograms) return Promise.resolve();
    if (!picker) {
      picker = new Promise(function (ok, no) {
        var tag = document.createElement('script');
        function fail(why) { clearTimeout(timer); tag.remove(); no(new Error(why)); }
        var timer = setTimeout(function () { fail('The picker did not come: the computer may not be reachable.'); }, 10000);
        tag.src = '/lib/pictograms.js';
        tag.onload = function () { clearTimeout(timer); if (window.ParsehPictograms) ok(); else fail('The picker did not start.'); };
        tag.onerror = function () { fail('The picker could not be fetched: the computer may not be reachable.'); };
        document.head.appendChild(tag);
      });
      picker.catch(function () { picker = null; });
    }
    return picker;
  }
  function look() {
    loadPicker().then(function () {
      ParsehPictograms.open({
        search: '/settings/api/arasaac/search',
        picture: function (id) { return '/settings/arasaac/picture/' + id + '.png'; },
        title: 'Pictograms (ARASAAC)',
        note: 'These are the pictures on this computer. Search them by a word, in any of the languages fetched, and click one to look at it properly.'
      });
    }, function (e) { asking = {kind: 'bad', said: e.message}; drawn = null; draw(); });
  }

  root.addEventListener('change', function (e) {
    var t = e.target, c;
    if ((c = t.getAttribute('data-tick'))) { pick.locales[c] = t.checked; drawn = null; replan(); draw(); }
    else if (t.hasAttribute('data-px')) { pick.px = Number(t.value); asking = null; drawn = null; replan(); draw(); }
  });
  root.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b || b.disabled) return;
    var code;
    function press() { held = document.activeElement === b ? focusToken(b) : null; drawn = null; b.disabled = true; }
    function start(what, body) {
      press(); asking = null;
      post(what, body).then(function (j) {
        if (!j.ok) { asking = {kind: 'bad', said: j.error || 'That was refused.'}; drawn = null; draw(); return; }
        kick();
      }).catch(lost);
    }
    if (b.hasAttribute('data-look')) { look(); return; }
    if (b.hasAttribute('data-get')) { start('get', {locales: ticked(), resolution: pick.px}); return; }
    if (b.hasAttribute('data-update')) { start('update', {}); return; }
    if (b.hasAttribute('data-resize')) { asking = {kind: 'size'}; draw(); return; }
    if (b.hasAttribute('data-yes-size')) { start('get', {locales: ticked(), resolution: pick.px}); return; }
    if (b.hasAttribute('data-stop')) { press(); post('stop', {}).then(kick, lost); return; }
    if ((code = b.getAttribute('data-remove-lang'))) { asking = {kind: 'remove', locale: code}; draw(); return; }
    if (b.hasAttribute('data-remove-all')) { asking = {kind: 'removeall'}; draw(); return; }
    if (b.hasAttribute('data-cancel')) { asking = null; drawn = null; draw(); return; }
    if ((code = b.getAttribute('data-yes-lang'))) {
      press(); asking = null;
      post('remove', {locale: code}).then(function (j) {
        if (!j.ok) { asking = {kind: 'bad', said: j.error || 'That was refused.'}; drawn = null; draw(); return; }
        pick.locales[code] = false; refresh();
      }).catch(lost);
      return;
    }
    if (b.hasAttribute('data-yes-all')) {
      press(); asking = null;
      post('remove', {all: true}).then(function (j) {
        if (!j.ok) { asking = {kind: 'bad', said: j.error || 'That was refused.'}; drawn = null; draw(); return; }
        pick.locales = {en: true}; pick.px = 300; refresh().then(replan);
      }).catch(lost);
    }
  });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) refresh(); });

  draw();
  if (busy()) schedule(1000);
})();
""".replace("/*ROW_JS*/", lookuppage.ROW_JS)
