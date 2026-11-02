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


def view(where="", device=""):
    st = getanalysis.status()
    for m in st["models"]:
        m["name"] = languages.get_or_default(m["code"]).name
    return {"ok": True, "analysis": st, "choices": analysisconfig.load(),
            "offered": {k: list(v) for k, v in analysisconfig.CHOICES.items()},
            "credit": pins.MODEL_CREDIT, "licence": pins.MODEL_LICENCE, "licence_url": pins.MODEL_LICENCE_URL,
            "model_page": pins.MODEL_PAGE, "where": where or "", "device": device or "",
            "may": {k: settingspage.may(k, where) for k in KEYS}}


def attempt(body):
    """The page's "Try it": one sentence through the analyzer, the chunker with and without it, a
    lookup with and without it, and the evidence a prompt would carry.  It stores nothing."""
    code = body.get("language")
    text = body.get("text")
    if not isinstance(code, str) or not isinstance(text, str) or not text.strip():
        return 400, {"ok": False, "error": "Say which language, and write a sentence."}
    text = text.strip()[:MAX_TRY]
    code = languages.get_or_default(code).code
    result = analyzer.analyze(code, text, syntax=True)
    out = {"ok": True, "language": code, "outcome": result.outcome, "backend": result.backend,
           "diagnostics": list(result.diagnostics), "tokens": [],
           "resources": [{"backend": r.backend, "version": r.version, "resource": r.resource} for r in result.resources]}
    for t in result.tokens:
        out["tokens"].append({"surface": t.surface, "lemmas": t.lemmas()[:4], "analyzed": t.analyzed,
                              "pos": next((w.upos for w in t.parsed() if w.upos), "") or
                                     next((c.upos for c in t.candidates if c.upos), "") or "",
                              "relation": next((w.relation for w in t.parsed() if w.relation), "") or "",
                              "candidates": len(t.candidates),
                              "status": t.selection.lemma_status if t.selection else "lexical"})
    out["chunks_before"] = chunker.chunk(text, code, "phrase")
    out["chunks_after"] = chunker.chunk(text, code, "phrase", (lambda t: result) if result.ok else None)
    out["lookup"] = _lookups(code, text)
    out["evidence"] = evidence.for_text(code, text)["sentences"] if result.ok else []
    return 200, out


def _lookups(code, text):
    """[{word, before, after, via}]: what the dictionary found for each word without and with the analyzer."""
    if not lookup.available(code):
        return []
    before = lookup.look_up(code, text) or {}
    after = lookup.look_up(code, text) or {}
    lookupassist.apply(code, after, text, text, "assist")
    rows = []
    for a, b in zip(before.get("words") or [], after.get("words") or []):
        rows.append({"word": a.get("word"), "before": [h.get("headword") for h in a.get("hits") or []][:4],
                     "after": [h.get("headword") for h in b.get("hits") or []][:4], "via": b.get("via") or "",
                     "changed": a.get("hits") != b.get("hits")})
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
<p class="whomay">%(gate)s <span>Nothing is fetched until you press a button here. Getting an analyzer changes no
result: Parseh uses one only where you say so, under <em>What they are used for</em>.</span></p>
<div id="an-band" class="band"></div>
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
.an h3{font:600 14px/1.3 inherit;margin:.2rem 0 .4rem}
.an .lead{font-size:13.5px;color:var(--dim);margin:0 0 .6rem}
.an .row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;align-items:center;padding:6px 0;
  border-top:1px solid var(--rule);font-size:14px}
.an .row:first-of-type{border-top:0}
.an .row .facts{grid-column:1;color:var(--dim);font-size:12.5px}
.an .row .act{grid-row:1/3;grid-column:2}
.an .row.have .nm::before{content:"\2713\a0";color:var(--ok);font-weight:700}
.an .use{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,auto);gap:4px 12px;align-items:center;padding:6px 0;
  border-top:1px solid var(--rule);font-size:14px}
.an .use:first-of-type{border-top:0}
.an .use small{display:block;color:var(--dim);font-size:12.5px}
.an select,.an textarea,.an input[type=text]{font:inherit;max-width:100%}
.an textarea{width:100%;box-sizing:border-box;min-height:64px;margin:.3rem 0}
.an table{border-collapse:collapse;font-size:13.5px;width:100%;margin:.4rem 0}
.an td,.an th{border-top:1px solid var(--rule);padding:3px 6px;text-align:start;vertical-align:top;overflow-wrap:anywhere}
.an .chunks span{display:inline-block;border:1px solid var(--rule);border-radius:6px;padding:1px 6px;margin:2px}
.an .scroll{overflow-x:auto}
.an .credit{margin:.5rem 0;padding:8px 12px;border-inline-start:3px solid var(--accent);background:var(--boxbg);
  border-radius:0 8px 8px 0;font-size:13.5px}
.an .err{color:var(--warn,#a33)}
"""

SCRIPT = r"""
(function () {
  var st = JSON.parse(document.getElementById('an-state').textContent), box = document.getElementById('an');
  var band = document.getElementById('an-band'), timer = null;
  var USES = {
    lookup: ['The dictionary panel', 'Off, as ever. Show: a line under each word saying what the analyzer read it as. ' +
             'Find: the same, and a word the dictionary did not find is looked for under the analyzer’s lemma; ' +
             'the row says so.', {off: 'off', show: 'show', assist: 'show and find'}],
    chunking: ['Cutting new text into phrases', 'What a new book or video is cut into before you edit it. ' +
               'Chunks you have edited are never cut again.', {off: 'off', assist: 'listen to the analyzer'}],
    evidence: ['The gloss prompts', 'Copy prompt and the skill’s request, for a stretch of a book or a video: each ' +
               'chunk to do carries what the analyzer read, as evidence the model may weigh.', {off: 'off', on: 'on'}]
  };
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
  function mb(n) { return Math.round(n / 1048576) + ' MB'; }
  function post(path, body) {
    return fetch('/settings/api/analysis/' + path, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})}).then(function (r) { return r.json(); });
  }
  function refresh() {
    return post('state').then(function (v) { st = v; draw(); });
  }
  function act(path, body) {
    return post(path, body).then(function (r) {
      if (!r.ok) { band.textContent = r.error || 'That could not be done.'; band.className = 'band err'; }
      else { band.textContent = ''; band.className = 'band'; }
      return refresh();
    });
  }
  function button(item, have, may) {
    if (have) return '<button class="btn" data-remove="' + esc(item) + '"' + (may.remove ? '' : ' disabled') + '>Remove</button>';
    return '<button class="btn" data-get="' + esc(item) + '"' + (may.get ? '' : ' disabled') + '>Get</button>';
  }
  function draw() {
    var a = st.analysis, job = a.job || {}, busy = job.state === 'running';
    var may = {get: st.may['analysis.get'] && !busy, remove: st.may['analysis.remove'] && !busy};
    var h = '';
    if (busy) h += '<section class="box"><h3>Fetching&hellip;</h3><p class="lead">' + esc(job.now || 'Starting') +
                   '</p><button class="btn" id="an-stop">Stop</button></section>';
    if (job.state === 'failed') h += '<section class="box"><p class="err">' + esc(job.error) + '</p></section>';
    if (a.cannot) h += '<section class="box"><p class="err">' + esc(a.cannot) + '</p></section>';
    h += '<section class="box"><h3>What they are used for</h3><p class="lead">Each is off until you change it.</p>';
    Object.keys(USES).forEach(function (k) {
      var u = USES[k], opts = st.offered[k].map(function (o) {
        return '<option value="' + o + '"' + (st.choices[k] === o ? ' selected' : '') + '>' + esc(u[2][o]) + '</option>';
      }).join('');
      h += '<label class="use"><span>' + esc(u[0]) + '<small>' + esc(u[1]) + '</small></span><select data-use="' + k + '"' +
           (st.may['analysis.use'] ? '' : ' disabled') + '>' + opts + '</select></label>';
    });
    h += '</section><section class="box"><h3>Arabic and Turkish</h3><p class="lead">Each word’s morphology, with every reading ' +
         'it can have. With their UDPipe model below they get its syntax too, kept apart from this.</p>';
    var f = a.programs.farahidi, s = a.programs.starlang;
    h += '<div class="row' + (f.have ? ' have' : '') + '"><span class="nm">Farahidi, for Arabic</span><span class="act">' +
         button('farahidi', f.have, may) + '</span><span class="facts">about ' + f.mb + ' MB &middot; ' + esc(f.version) +
         ' &middot; ' + esc(f.licence) + ' &middot; half a gigabyte of memory while it is working</span></div>';
    h += '<div class="row' + (s.have ? ' have' : '') + '"><span class="nm">Starlang, for Turkish</span><span class="act">' +
         button('starlang', s.have, may) + '</span><span class="facts">about ' + s.mb + ' MB &middot; ' + esc(s.version) +
         ' &middot; ' + esc(s.licence) + ' &middot; compiled when it is installed, so it takes a minute and a C compiler' +
         (s.compiler ? '' : ' &mdash; <b>none was found</b>') + '</span></div></section>';
    h += '<section class="box"><h3>UDPipe, a model per language</h3><p class="lead">Lemma, part of speech, grammar and ' +
         'sentence structure.</p><p class="credit">The models are ' + esc(st.credit) + ', <a href="' + esc(st.licence_url) +
         '">' + esc(st.licence) + '</a>: free for non-commercial use, and shared on the same licence.</p>';
    a.models.forEach(function (m) {
      h += '<div class="row' + (m.have ? ' have' : '') + '"><span class="nm">' + esc(m.name) + '</span><span class="act">' +
           button(m.item, m.have, may) + '</span><span class="facts">' + esc(m.treebank) + ' &middot; ' + mb(m.bytes) + '</span></div>';
    });
    h += '</section><section class="box"><h3>Try it</h3><p class="lead">A sentence of your own, read by the analyzer: the phrases ' +
         'with and without it, and what a prompt would carry. Nothing is kept. The first try of a language loads its model.</p>' +
         '<select id="an-lang">' + a.models.map(function (m) { return '<option value="' + m.code + '">' + esc(m.name) + '</option>'; }).join('') +
         '</select><textarea id="an-text" dir="auto"></textarea><button class="btn" id="an-try">Try it</button><div id="an-out"></div></section>';
    h += '<section class="box"><h3>Where it is</h3><p class="lead"><code>' + esc(a.folder) + '</code><br>Program: <code>' + esc(a.python) +
         '</code><br>Serving Python: <code>' + esc(a.serving_python) + '</code></p>' +
         '<button class="btn" data-remove="all"' + (may.remove ? '' : ' disabled') + '>Remove all of it</button></section>';
    var keep = {lang: (document.getElementById('an-lang') || {}).value, text: (document.getElementById('an-text') || {}).value,
                out: (document.getElementById('an-out') || {}).innerHTML};
    box.innerHTML = h;
    if (keep.lang) document.getElementById('an-lang').value = keep.lang;
    if (keep.text) document.getElementById('an-text').value = keep.text;
    if (keep.out) document.getElementById('an-out').innerHTML = keep.out;
    clearTimeout(timer);
    if (busy) timer = setTimeout(refresh, 1500);
  }
  function chunks(list) { return '<div class="chunks" dir="auto">' + list.map(function (c) { return '<span>' + esc(c) + '</span>'; }).join('') + '</div>'; }
  function tried(r) {
    var out = document.getElementById('an-out');
    if (!r.ok) { out.innerHTML = '<p class="err">' + esc(r.error) + '</p>'; return; }
    var h = '<p class="lead">' + esc(r.outcome) + (r.backend ? ' &middot; ' + esc(r.backend) : '') + '</p>';
    (r.diagnostics || []).forEach(function (d) { h += '<p class="lead">' + esc(d) + '</p>'; });
    if (r.tokens.length) {
      h += '<div class="scroll"><table><tr><th>word</th><th>lemma</th><th>part of speech</th><th>relation</th><th>readings</th><th>chosen</th></tr>';
      r.tokens.forEach(function (t) {
        h += '<tr><td dir="auto">' + esc(t.surface) + '</td><td dir="auto">' + esc(t.lemmas.join(', ')) + '</td><td>' + esc(t.pos) +
             '</td><td>' + esc(t.relation) + '</td><td>' + (t.candidates || '') + '</td><td>' + esc(t.status === 'contextual' ? 'by the sentence' : 'word alone') + '</td></tr>';
      });
      h += '</table></div>';
    }
    h += '<h3>Phrases, without it</h3>' + chunks(r.chunks_before) + '<h3>Phrases, with it</h3>' + chunks(r.chunks_after);
    if (r.lookup.length) {
      h += '<h3>The dictionary, without and with it</h3><div class="scroll"><table><tr><th>word</th><th>without</th><th>with</th></tr>';
      r.lookup.forEach(function (w) {
        h += '<tr><td dir="auto">' + esc(w.word) + '</td><td dir="auto">' + esc(w.before.join(', ') || '—') + '</td><td dir="auto">' +
             (w.changed ? '<b>' + esc(w.after.join(', ')) + '</b>' + (w.via ? ' <small>' + esc(w.via) + '</small>' : '') : 'the same') + '</td></tr>';
      });
      h += '</table></div>';
    }
    out.innerHTML = h;
  }
  box.addEventListener('click', function (e) {
    var t = e.target, item;
    if (t.id === 'an-stop') return act('stop');
    if (t.id === 'an-try') {
      document.getElementById('an-out').innerHTML = '<p class="lead">Reading&hellip;</p>';
      return post('try', {language: document.getElementById('an-lang').value, text: document.getElementById('an-text').value}).then(tried);
    }
    if ((item = t.getAttribute('data-get'))) return act('get', {items: [item]});
    if ((item = t.getAttribute('data-remove'))) return act('remove', {item: item});
  });
  box.addEventListener('change', function (e) {
    var k = e.target.getAttribute('data-use');
    if (k) { var c = {}; c[k] = e.target.value; act('use', {choices: c}); }
  });
  draw();
})();
"""
