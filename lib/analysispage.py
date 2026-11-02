# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> Linguistic analysis: getting the optional analyzers, what they are used for, and
trying them on a sentence (lib/getanalysis.py, lib/analysisconfig.py).

Who may press what is lib/settingspage.py's table, as for every page of settings.  The page draws
from one answer, `view`, on opening and each time it asks how things stand; nothing about it loads
a model, except "Try it", which is a person asking for exactly that.
"""
import html

import analysisconfig
import analysispins as pins
import analyzer
import chunker
import evidence
import getanalysis
import languages
import lookup
import lookupassist
import lookuppage
import settingspage

PAGE = "/settings/analysis/"
GUIDE = "/guide/site/lookup-and-languages/linguistic-analysis.html"
KEYS = ("analysis.get", "analysis.remove", "analysis.use")
MAX_TRY = 600


def esc(s):
    return html.escape(str(s), quote=True)


def door_tags():
    """What the Settings hub says under this door, from file names alone."""
    if not getanalysis.installed():
        return '<span class="tag">not installed</span>'
    out = ""
    for name in pins.PACKAGES:
        if getanalysis.package_here(name):
            out += '<span class="tag on">%s</span>' % esc(name)
    used = [k for k, v in analysisconfig.load().items() if v != "off"]
    return out + ('<span class="tag on">in use: %s</span>' % esc(", ".join(used)) if used
                  else '<span class="tag">not in use</span>')


def _items(st):
    """Every thing there is to get, language by language: what a person chooses among.  A language has one row, or
    two where its word forms and its sentence structure come from different programs."""
    rows = []
    by_code = {m["code"]: m for m in st["models"]}
    for code in pins.UDPIPE_MODELS:
        name = languages.get_or_default(code).name
        m = by_code[code]
        if code == "ar":
            f = st["programs"]["farahidi"]
            rows.append({"item": "farahidi", "name": name, "part": "word forms", "mb": f["mb"], "have": f["have"],
                         "code": code, "note": "Farahidi " + f["version"] + ", " + f["licence"] +
                         ". Half a gigabyte of memory while it is working."})
        if code == "tr":
            t = st["programs"]["starlang"]
            rows.append({"item": "starlang", "name": name, "part": "word forms", "mb": t["mb"], "have": t["have"],
                         "code": code, "note": "Starlang " + t["version"] + ", " + t["licence"] +
                         ". Compiled when it is installed, which takes a minute or two.",
                         "cannot": "" if t["compiler"] else "It needs a C compiler, and this computer has none."})
        rows.append({"item": m["item"], "name": name, "part": "sentence structure" if code in ("ar", "tr") else "",
                     "mb": round(m["bytes"] / 1048576), "have": m["have"], "loaded": m["loaded"], "code": code,
                     "note": "UDPipe, " + m["treebank"] + ", " + m["licence"] + "."})
    return rows


def _ready():
    """{use: the names of the languages it can work in now}.  Read from the files; it loads nothing.  The dictionary
    panel needs the language's dictionary as well, and says which languages lack only that."""
    codes = list(pins.UDPIPE_MODELS)
    name = lambda c: languages.get_or_default(c).name
    return {"lookup": [name(c) for c in codes if analyzer.available(c) and lookup.available(c)],
            "lookup_no_dict": [name(c) for c in codes if analyzer.available(c) and not lookup.available(c)],
            "chunking": [name(c) for c in codes if analyzer.available(c, syntax=True)],
            "evidence": [name(c) for c in codes if analyzer.available(c, syntax=True)]}


def view(where="", device=""):
    st = getanalysis.status()
    return {"ok": True, "analysis": st, "items": _items(st), "ready": _ready(), "choices": analysisconfig.load(),
            "here": [{"code": c, "name": languages.get_or_default(c).name} for c in pins.UDPIPE_MODELS if analyzer.available(c)],
            "offered": {k: list(v) for k, v in analysisconfig.CHOICES.items()},
            "credit": pins.MODEL_CREDIT, "licence": pins.MODEL_LICENCE, "licence_url": pins.MODEL_LICENCE_URL,
            "model_page": pins.MODEL_PAGE, "program_mb": st["programs"]["udpipe"]["mb"],
            "where": where or "", "device": device or "",
            "may": {k: settingspage.may(k, where) for k in KEYS}}


def attempt(body):
    """The page's "Try it": one sentence through the analyzer, the chunker with and without it, a
    lookup with and without it, and the evidence a prompt would carry.  It stores nothing."""
    code = body.get("language")
    text = body.get("text")
    if not isinstance(code, str) or not isinstance(text, str) or not text.strip():
        return 400, {"ok": False, "error": "Choose a language, and write a sentence."}
    text = text.strip()[:MAX_TRY]
    code = languages.get_or_default(code).code
    result = analyzer.analyze(code, text, syntax=True)
    out = {"ok": True, "language": code, "outcome": result.outcome, "backend": result.backend,
           "diagnostics": list(result.diagnostics), "tokens": []}
    for t in result.tokens:
        said = lookupassist._machine(t)
        if said is None or said["upos"] == "PUNCT":
            continue
        out["tokens"].append(dict(said, surface=t.surface, relation=next((w.relation for w in t.parsed() if w.relation), "")))
    out["chunks_before"] = chunker.chunk(text, code, "phrase")
    out["chunks_after"] = chunker.chunk(text, code, "phrase", (lambda t: result) if result.ok else None)
    out["lookup"] = _lookups(code, text)
    out["evidence"] = evidence.for_text(code, text)["sentences"] if result.ok else []
    return 200, out


def _lookups(code, text):
    """What the part of speech does to the dictionary, word by word: its entries without the analyzer and with it,
    for the rows it changed.  [{word, pos, entries: [{head, pos, fits}], before, via}], or None with no dictionary."""
    if not lookup.available(code):
        return None
    before = lookup.look_up(code, text) or {}
    after = lookup.look_up(code, text) or {}
    lookupassist.apply(code, after, text, text, "assist")
    rows = []
    for a, b in zip(before.get("words") or [], after.get("words") or []):
        hits = b.get("hits") or []
        if a.get("hits") != hits:
            rows.append({"word": a.get("word"), "pos": (b.get("machine") or {}).get("pos") or "", "via": b.get("via") or "",
                         "entries": [{"head": h.get("headword"), "pos": h.get("pos") or "", "fits": bool(h.get("fits"))} for h in hits[:4]],
                         "before": [h.get("headword") for h in a.get("hits") or []][:4],
                         "found": not a.get("hits")})
    return rows


def api(what, body, where=""):
    """One route's work -> (status, answer).  Who may was asked first, of lib/settingspage.py ROUTES."""
    body = body if isinstance(body, dict) else {}
    try:
        if what == "state":
            return 200, view(where, body.get("device") or "")
        if what == "get":
            answer, status = getanalysis.start(body.get("items"))
            return status, answer
        if what == "stop":
            return 200, {"ok": True, "stopped": getanalysis.stop()}
        if what == "remove":
            getanalysis.remove(body.get("item"))
            return 200, {"ok": True}
        if what == "use":
            return 200, {"ok": True, "choices": analysisconfig.save(body.get("choices"))}
        if what == "try":
            return attempt(body)
    except (getanalysis.AnalysisError, ValueError) as e:
        return 400, {"ok": False, "error": str(e)}
    return 404, {"ok": False, "error": "%s has no such request." % settingspage.NAME}


def page(where="", device=""):
    v = view(where, device)
    main = """<main class="settings rh an">
%(doors)s
<h1 class="idx">linguistic analysis</h1>
<p class="whomay">%(gate)s <span>Programs on this computer that read a sentence and say what each word is in it: its part of
speech above all, so that the dictionary can show the entry that fits. Getting one changes nothing by itself: you choose where
Parseh listens.</span></p>
<div id="an-say" role="status"></div>
<div id="an"><p class="rh-wait">Reading what is here&hellip;</p></div>
<p class="foot">What is fetched here lives in the <code>analysis/</code> folder, kept by every update and left out of
backups, books and exports. It runs on this computer and asks nobody else anything once it is here. Every licence is
also on the <a href="/licences/">licences</a> page. <a href="%(guide)s" data-guide>What the analyzers do</a>, in the
guide.</p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "gate": settingspage.gate(KEYS), "guide": esc(GUIDE)}
    script = ('<script id="an-state" type="application/json">%s</script>\n<script>%s</script>'
              % (settingspage._in_script(v), SCRIPT))
    return settingspage.frame("Linguistic analysis &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; linguistic analysis',
                              "Linguistic analysis", GUIDE, main, style=lookuppage.STYLE + STYLE, script=script)


STYLE = r"""
.an .whomay{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap;margin:.2rem 0 1rem;font-size:13.5px;color:var(--dim)}
.an .whomay .gate{flex:none}
.an section{padding:12px 16px 14px;margin:0 0 14px}
.an h3{font:600 15px/1.3 inherit;margin:.2rem 0 .35rem}
.an h4{font:600 13.5px/1.3 inherit;margin:.9rem 0 .25rem}
.an .lead{font-size:13.5px;color:var(--dim);margin:0 0 .6rem}
.an a{color:var(--accent)}
.an .say{margin:0 0 14px;padding:8px 12px;border-radius:8px;border:1px solid var(--danger);color:var(--danger);font-size:14px}
.an .err{color:var(--danger);font-size:13.5px;margin:.4rem 0}
.an .credit{margin:.5rem 0 .7rem;padding:8px 12px;border-inline-start:3px solid var(--accent);background:var(--boxbg);
  border-radius:0 8px 8px 0;font-size:13px}
.an .row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;align-items:center;padding:7px 0;
  border-top:1px solid var(--rule);font-size:14px}
.an .row:first-of-type{border-top:0}
.an .pick{display:flex;gap:10px;align-items:center;min-height:34px;cursor:pointer}
.an span.pick{cursor:default}
.an .pick input{margin:0;width:20px;height:20px;flex:none}
.an .pick .mark{width:20px;flex:none;text-align:center;color:var(--ok);font-weight:700}
.an .pick .part{color:var(--dim)}
.an .facts{grid-column:1;padding-inline-start:30px;color:var(--dim);font-size:12.5px}
.an .row .act{grid-row:1;grid-column:2}
.an .row .ask{grid-column:1/-1}
.an .go-row{display:flex;gap:8px 14px;align-items:center;flex-wrap:wrap;margin-top:.7rem}
.an .use{display:grid;grid-template-columns:minmax(0,1fr) 11.5rem;gap:4px 16px;align-items:start;padding:9px 0;
  border-top:1px solid var(--rule);font-size:14px}
.an .use:first-of-type{border-top:0}
.an .use small{display:block;color:var(--dim);font-size:12.5px;margin-top:1px}
.an .use .state{margin-top:3px}
.an .use .state.no{color:var(--warn)}
.an .use select{width:100%;min-height:34px}
.an select,.an textarea{font:inherit;max-width:100%}
.an #an-lang{min-height:34px}
.an textarea{display:block;width:100%;box-sizing:border-box;min-height:64px;margin:.5rem 0}
.an .chunks{display:flex;flex-wrap:wrap;gap:4px;margin:.2rem 0}
.an .chunks span{border:1px solid var(--rule);border-radius:6px;padding:2px 7px;font-size:15px}
.an .same{color:var(--dim);font-size:13.5px}
.an .tok{display:grid;grid-template-columns:minmax(4rem,9rem) 7.5rem minmax(0,1fr);gap:2px 12px;align-items:baseline;padding:5px 0;border-top:1px solid var(--rule);font-size:15px}
.an .tok .sub{color:var(--dim);font-size:12.5px}
.an .lkw{padding:7px 0;border-top:1px solid var(--rule);font-size:14px}
.an .lkw .dwd{font-size:16px;margin-bottom:3px}
.an .lkw .dhit{padding:1px 0}
.an .lkw .dhit.fits,.an .preview .dhit.fits{padding-inline-start:7px}
.an .lkw .same{margin:.2rem 0 0;font-size:12.5px}
.an .lkw .dpos,.an .preview .dpos{color:var(--faint);font-style:italic}
.an .preview{margin-top:8px;padding:8px 10px;border:1px dashed var(--rule);border-radius:8px;font-size:13.5px}
.an .preview .head{color:var(--dim);font-size:12px;margin-bottom:2px}
.an .preview .dwd{font-size:15px;margin-bottom:2px}
.an .preview .dhit{padding:1px 0}
.an details{margin-top:.8rem;font-size:13.5px}
.an summary{cursor:pointer;min-height:28px;color:var(--dim)}
.an pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12.5px;margin:.3rem 0}
.an code{overflow-wrap:anywhere}
@media (max-width:640px){
  .an .use{grid-template-columns:minmax(0,1fr)}
  .an .row .act button,.an .go-row button{min-height:40px}
  .an .tok{grid-template-columns:minmax(0,1fr) auto}
  .an .tok .sub{grid-column:1/-1}
}
"""

SCRIPT = r"""
(function () {
  var st = JSON.parse(document.getElementById('an-state').textContent), box = document.getElementById('an');
  var sayBox = document.getElementById('an-say'), timer = null, ticked = {}, asking = null, misses = 0, trying = false, lastOut = '';
  var USES = {
    lookup: ['The dictionary panel: part of speech', 'Each word says what it is in this sentence, and the entry of that part of speech ' +
             'is marked. The fuller choice also moves it to the top, and looks up what the dictionary missed under the word\u2019s lemma.',
             {off: 'Off', show: 'Show the part of speech', assist: 'Also put what fits first'}],
    chunking: ['Cutting new text into phrases', 'When you make a new book or video and choose to cut it into phrases. Chunks you ' +
               'have edited are never cut again.', {off: 'Off', assist: 'Listen to the analyzer'}],
    evidence: ['The gloss prompts', 'Copy the prompt and the skill\u2019s request, for a stretch of a book or a video: each chunk to ' +
               'do carries what the analyzer read, as evidence the chatbot may weigh.', {off: 'Off', on: 'On'}]
  };
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML.replace(/"/g, '&quot;'); }
  function post(path, body) {
    return fetch('/settings/api/analysis/' + path, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})}).then(function (r) { return r.json(); });
  }
  function say(text) {
    sayBox.className = text ? 'say' : '';
    sayBox.textContent = text || '';
  }
  var GONE = 'Parseh did not answer. Is it still running on the computer?';
  function refresh() {
    return post('state').then(function (v) { misses = 0; st = v; draw(); }, function () {
      // one dropped answer ends nothing: a job goes on whether or not this page heard about it
      misses++;
      clearTimeout(timer);
      timer = setTimeout(refresh, 2500);
      if (misses > 3) say(GONE);
    });
  }
  function act(path, body) {
    return post(path, body).then(function (r) {
      say(r.ok ? '' : (r.error || 'That could not be done.'));
      return refresh();
    }, function () { say(GONE); draw(); });
  }
  function listed(names) {
    return names.length > 1 ? names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1] : names.join('');
  }
  function tickedItems() { return st.items.filter(function (i) { return ticked[i.item] && !i.have; }); }
  function cost() {
    var chosen = tickedItems(), mb = 0, program = false;
    chosen.forEach(function (i) { mb += i.mb; if (i.item.indexOf('udpipe:') === 0) program = true; });
    if (program && !st.analysis.programs.udpipe.have) mb += st.program_mb;
    return {n: chosen.length, mb: mb};
  }
  function row(i, a, busy) {
    var label = esc(i.name) + (i.part ? ' <span class="part">\u00b7 ' + esc(i.part) + '</span>' : '');
    var h = '<div class="row">', remove = st.may['analysis.remove'] && !busy;
    if (i.have) {
      h += '<span class="pick"><span class="mark" aria-hidden="true">\u2713</span><span>' + label + '</span></span>';
      if (remove && asking !== i.item) h += '<span class="act"><button class="plain" type="button" data-ask="' + esc(i.item) +
        '" aria-label="Remove ' + esc(i.name + (i.part ? ', ' + i.part : '')) + '">Remove\u2026</button></span>';
    } else {
      h += '<label class="pick"><input type="checkbox" data-tick="' + esc(i.item) + '"' + (ticked[i.item] ? ' checked' : '') +
           (busy || i.cannot || !st.may['analysis.get'] ? ' disabled' : '') + '><span>' + label + '</span></label>';
    }
    h += '<span class="facts">' + i.mb + ' MB \u00b7 ' + esc(i.note) + (i.loaded ? ' In memory now.' : '') +
         (i.cannot ? ' <b>' + esc(i.cannot) + '</b>' : '') + '</span>';
    if (asking === i.item) h += '<div class="ask"><span class="said">Remove it? You can get it again, and your books and videos do ' +
      'not change.</span><button class="danger" type="button" data-remove="' + esc(i.item) + '">Remove</button>' +
      '<button class="plain" type="button" data-cancel>Keep it</button></div>';
    return h + '</div>';
  }
  function getting(a, job, busy) {
    var h = '<section class="box"><h3>Languages</h3><p class="lead">Tick the languages you want. Each is fetched once and kept on this ' +
            'computer, and what comes through a button can be removed the same way.</p>';
    h += '<p class="credit">The UDPipe models are ' + esc(st.credit) + ', under <a href="' + esc(st.licence_url) + '" rel="noopener" target="_blank">' +
         esc(st.licence) + '</a>: free for non-commercial use, and shared on the same licence. They are not part of Parseh: ' +
         'leave them unticked and nothing of theirs is ever on this computer.</p>';
    st.items.forEach(function (i) { h += row(i, a, busy); });
    if (busy) {
      var all = (job.items || []).length, done = (job.done || []).length;
      h += '<div class="go-row"><div style="flex:1 1 14rem"><div>' + esc(job.now || 'Starting') + (all > 1 ? ' \u00b7 ' + done + ' of ' + all + ' done' : '') + '</div>' +
           '<div class="bar' + (done ? '' : ' loose') + '" role="progressbar" aria-label="fetching the analyzers"' + (done ? ' aria-valuenow="' + Math.round(100 * done / all) + '"' : '') + '><i' +
           (done ? ' style="width:' + Math.round(100 * done / all) + '%"' : '') + '></i></div></div>' +
           '<button class="plain" type="button" id="an-stop">Stop</button></div>';
    } else {
      var c = cost();
      if (job.state === 'failed') h += '<p class="err">' + esc(job.error) + ' What came before it is kept, so asking again goes on from there.</p>';
      if (job.state === 'stopped') h += '<p class="lead" style="margin-top:.6rem">Stopped. What was finished is kept.</p>';
      // with everything here there is nothing to press
      if (st.items.some(function (i) { return !i.have; }))
        h += '<div class="go-row"><button class="go" type="button" id="an-get"' + (c.n && !a.cannot ? '' : ' disabled') + '>' +
             (job.state === 'failed' ? 'Try again' : 'Get it') + (c.n ? ': ' + c.n + (c.n > 1 ? ' items' : ' item') + ', about ' + c.mb + ' MB' : '') + '</button></div>';
    }
    return h + '</section>';
  }
  function trier() {
    var h = '<section class="box"><h3>Try it</h3>';
    if (!st.here.length) return h + '<p class="lead">Get a language above, and a sentence of your own can be read here, with and without the analyzer.</p></section>';
    h += '<p class="lead">A sentence of your own: the part of speech of each word, which dictionary entry fits, and the phrases with and without the analyzer. Nothing is kept. ' +
         'The first try of a language takes a moment or two.</p><select id="an-lang" aria-label="the language of the sentence">' +
         st.here.map(function (m) { return '<option value="' + m.code + '">' + esc(m.name) + '</option>'; }).join('') +
         '</select><textarea id="an-text" dir="auto" aria-label="a sentence to try"></textarea><button class="go" type="button" id="an-try"' +
         (trying ? ' disabled' : '') + '>' + (trying ? 'Reading\u2026' : 'Try it') + '</button><div id="an-out">' + lastOut + '</div></section>';
    return h;
  }
  // the dictionary panel as the choice makes it: the real classes, on a real sentence's word, so that it shows what you get
  function preview(how) {
    if (how === 'off') return '';
    var verb = '<div class="dhit fits"><b>run</b> <span class="dpos">verb</span><span class="dfits">fits this sentence</span></div>';
    var noun = '<div class="dhit"><b>ran</b> <span class="dpos">noun</span></div>';
    return '<div class="preview" aria-hidden="true"><div class="head">In <i>They ran home</i>:</div><div class="dwd">ran<span class="dposhere">verb</span></div>' +
           (how === 'assist' ? verb + noun : noun + verb) + '</div>';
  }
  function uses() {
    var h = '<section class="box"><h3>What they are used for</h3><p class="lead">Each is off until you change it, and each has its own choice.</p>';
    Object.keys(USES).forEach(function (k) {
      var u = USES[k], ready = st.ready[k], on = st.choices[k] !== 'off', state = '';
      if (on && !ready.length && !(k === 'lookup' && st.ready.lookup_no_dict.length)) state = '<small class="state no">Nothing here can do this yet, so Parseh goes on without it: get a language above.</small>';
      else if (ready.length) state = '<small class="state">' + (on ? 'Working' : 'Can work') + ' in ' + esc(listed(ready)) + '.</small>';
      if (k === 'lookup' && st.ready.lookup_no_dict.length) state += '<small class="state">' + esc(listed(st.ready.lookup_no_dict)) + (st.ready.lookup_no_dict.length > 1 ? ' also need their dictionaries' : ' also needs its dictionary') + ': <a href="/settings/reading-help/">Reading help</a>.</small>';
      if (k === 'lookup') state += preview(st.choices.lookup);
      if (k === 'evidence' && on) state += '<small class="state">A chatbot with the skill needs the newest one: <a href="/settings/skills/">Skills for your chatbot</a>.</small>';
      h += '<div class="use"><div><label for="an-use-' + k + '">' + esc(u[0]) + '</label><small>' + esc(u[1]) + '</small>' + state + '</div><select id="an-use-' + k + '" data-use="' + k + '"' +
           (st.may['analysis.use'] ? '' : ' disabled') + '>' + st.offered[k].map(function (o) {
             return '<option value="' + o + '"' + (st.choices[k] === o ? ' selected' : '') + '>' + esc(u[2][o]) + '</option>'; }).join('') + '</select></div>';
    });
    return h + '</section>';
  }
  function details(a, busy) {
    var may = st.may['analysis.remove'] && !busy, any = st.items.some(function (i) { return i.have; }) || a.runtime;
    return '<details><summary>Where it is on this computer</summary><p class="lead"><code>' + esc(a.folder) + '</code><br>The program runs with <code>' +
      esc(a.python) + '</code>, made from <code>' + esc(a.serving_python) + '</code>.' + (a.worker_running ? ' It is running now, and stops after ten idle minutes.' : '') + '</p>' +
      (any && may ? (asking === 'all'
        ? '<div class="ask"><span class="said">Remove the whole folder? You can get it all again, and your books and videos do not change.</span>' +
          '<button class="danger" type="button" data-remove="all">Remove all of it</button><button class="plain" type="button" data-cancel>Keep it</button></div>'
        : '<button class="plain" type="button" data-ask="all">Remove all of it\u2026</button>') : '') + '</details>';
  }
  // what had the keyboard, so that a redraw does not take it away (the page redraws while something is fetched)
  function focusKey() {
    var e = document.activeElement;
    if (!e || !box.contains(e)) return null;
    var attrs = ['id', 'data-tick', 'data-use', 'data-ask', 'data-remove'];
    for (var i = 0; i < attrs.length; i++) if (e.getAttribute(attrs[i])) return {sel: '[' + attrs[i] + '="' + e.getAttribute(attrs[i]) + '"]', at: e.selectionStart, end: e.selectionEnd};
    return null;
  }
  function draw() {
    var a = st.analysis, job = a.job || {}, busy = job.state === 'running';
    var keep = {lang: (document.getElementById('an-lang') || {}).value, text: (document.getElementById('an-text') || {}).value,
                open: !!(box.querySelector(':scope > details') || {}).open, focus: focusKey()};
    var h = a.cannot ? '<section class="box"><p class="err">' + esc(a.cannot) + '</p></section>' : '';
    box.innerHTML = h + getting(a, job, busy) + trier() + uses() + details(a, busy);
    var lang = document.getElementById('an-lang');
    if (lang && keep.lang && st.here.some(function (m) { return m.code === keep.lang; })) lang.value = keep.lang;
    if (keep.text && document.getElementById('an-text')) document.getElementById('an-text').value = keep.text;
    if (keep.open) box.querySelector(':scope > details').open = true;
    if (keep.focus) {
      var back = box.querySelector(keep.focus.sel);
      if (back) { back.focus(); if (back.tagName === 'TEXTAREA') back.setSelectionRange(keep.focus.at, keep.focus.end); }
    }
    clearTimeout(timer);
    if (busy) timer = setTimeout(refresh, 1500);
  }
  function chunks(list) { return '<div class="chunks" dir="auto">' + list.map(function (c) { return '<span>' + esc(c) + '</span>'; }).join('') + '</div>'; }
  var OUTCOME = {unavailable: 'Not ready for this language: ', failed: 'It could not read this: ', unsupported: 'No analyzer covers this language. ', empty: 'There is nothing to read in that.'};
  function tried(r) {
    var h = '';
    if (!r.ok) h = '<p class="err">' + esc(r.error) + '</p>';
    else if (r.outcome !== 'ok') h = '<p class="err">' + esc(OUTCOME[r.outcome] || '') + esc((r.diagnostics || []).join(' ')) + '</p>';
    else {
      h += '<h4>Each word, in this sentence</h4>';
      r.tokens.forEach(function (t) {
        var pos = t.pos && t.here ? '<span class="dposhere" style="margin:0">' + esc(t.pos) + '</span>' : (t.pos ? '<span class="same">' + esc(t.pos) + '?</span>' : '');
        var more = [];
        if (t.lemma) more.push('from ' + t.lemma);
        if (t.grammar) more.push(t.grammar);
        if ((t.others || []).length) more.push((t.lemma ? 'can also be ' : 'can be ') + t.others.join(', '));
        h += '<div class="tok"><span dir="auto">' + esc(t.surface) + '</span><span>' + pos + '</span><span class="sub" dir="auto">' + esc(more.join(' \u00b7 ')) + ' <span dir="ltr">(' + esc(t.who) + ')</span></span></div>';
      });
      h += '<h4>The dictionary, with what fits</h4>';
      if (r.lookup === null) h += '<p class="same">This language has no dictionary here yet: <a href="/settings/reading-help/">Reading help</a>.</p>';
      else if (!r.lookup.length) h += '<p class="same">In this sentence the part of speech changes nothing in the dictionary.</p>';
      else r.lookup.forEach(function (w) {
        h += '<div class="lkw"><div class="dwd" dir="auto">' + esc(w.word) + (w.pos ? '<span class="dposhere">' + esc(w.pos) + '</span>' : '') + '</div>';
        w.entries.forEach(function (e) {
          h += '<div class="dhit' + (e.fits ? ' fits' : '') + '" dir="auto"><b>' + esc(e.head) + '</b> <span class="dpos">' + esc(e.pos) + '</span>' + (e.fits ? '<span class="dfits">fits this sentence</span>' : '') + '</div>';
        });
        h += '<p class="same">' + (w.found ? 'Not found without the analyzer' + (w.via ? ': ' + esc(w.via) : '') + '.' : 'Without it, the order was: ' + esc(w.before.join(', ')) + '.') + '</p></div>';
      });
      var same = r.chunks_before.join('\n') === r.chunks_after.join('\n');
      h += '<h4>Phrases</h4>';
      if (same) h += chunks(r.chunks_after) + '<p class="same">The same with the analyzer and without it.</p>';
      else h += '<p class="same">Without the analyzer:</p>' + chunks(r.chunks_before) + '<p class="same">With it:</p>' + chunks(r.chunks_after);
      (r.diagnostics || []).forEach(function (d) { h += '<p class="same">' + esc(d) + '</p>'; });
      h += '<details><summary>What a gloss prompt would carry</summary><pre dir="auto">' + esc(JSON.stringify(r.evidence, null, 1)) + '</pre></details>';
    }
    lastOut = h;
    trying = false;
    draw();
  }
  box.addEventListener('click', function (e) {
    var t = e.target.closest('button'), item;
    if (!t) return;
    if (t.id === 'an-stop') return act('stop');
    if (t.id === 'an-get') {
      var items = tickedItems().map(function (i) { return i.item; });
      ticked = {};
      return act('get', {items: items});
    }
    if (t.id === 'an-try') {
      var lang = document.getElementById('an-lang').value, text = document.getElementById('an-text').value;
      trying = true;
      lastOut = '';
      document.getElementById('an-out').innerHTML = '';
      draw();
      return post('try', {language: lang, text: text}).then(tried, function () { tried({ok: false, error: GONE}); });
    }
    if ((item = t.getAttribute('data-ask'))) { asking = item; draw(); return; }
    if (t.hasAttribute('data-cancel')) { asking = null; draw(); return; }
    if ((item = t.getAttribute('data-remove'))) { asking = null; return act('remove', {item: item}); }
  });
  box.addEventListener('change', function (e) {
    var k = e.target.getAttribute('data-use'), item = e.target.getAttribute('data-tick');
    if (k) { var c = {}; c[k] = e.target.value; act('use', {choices: c}); }
    if (item) { ticked[item] = e.target.checked; draw(); }
  });
  draw();
  if ((st.analysis.job || {}).state === 'running') timer = setTimeout(refresh, 1500);
})();
"""
