# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> Languages: every language Parseh has, what each one has feature
by feature, a form that adds a language of this computer's, and for such a
language the prose it still needs, written with a chatbot.

THE SAME ANSWERS AS THE COMMAND LINE.  The list is lib/langfeatures.py's (what
`python3 lib/newlang.py --features` prints), the form runs lib/newlang.py with
the flags the fields give -- the row goes into config/languages.json, which an
update leaves alone -- and the prose is lib/langprompts.py's: a prompt to copy
to a chatbot, with a related language's file as the model, and a box that
takes the answer back, checks it and writes it.  Nothing here asks the network.

WHO MAY.  Reading is open to every device let in.  Adding a language and
taking an answer in write files Parseh reads as it runs -- a LaTeX file among
them -- so both are the computer's alone (lib/settingspage.py SETTINGS).  The
prose of Parseh's own languages is not offered: it comes with Parseh, and an
update would replace what was written over it.

A language added here is in every page at once (languages.reload): its chip,
its folders, its prompts.  What a module worked out from the table when it was
imported -- which analyzer reads it -- is the next start's, and a language added
from this form names no analyzer anyway.
"""
import contextlib
import html
import io
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import langfeatures                                          # noqa: E402
import langprompts                                           # noqa: E402
import languages                                             # noqa: E402
import settingspage                                          # noqa: E402

PAGE = "/settings/languages/"
GUIDE = "/guide/site/lookup-and-languages/adding-a-language.html"
KEYS = ("languages.add", "languages.prose")
SCRIPTS = ("latin", "arabic", "devanagari", "cjk", "other")


def esc(s):
    return html.escape(str(s), quote=True)


def view(where=""):
    """What the page draws, in one answer."""
    out = []
    mine = set(languages.mine())
    for code, L in languages.LANGS.items():
        have, of, missing = langfeatures.summary(code)
        out.append({"code": code, "name": L.name, "native": L.native, "dir": L.dir, "mine": code in mine,
                    "like": L.like or "", "have": have, "of": of, "missing": missing,
                    "features": [f.as_json() for f in langfeatures.features(code)]})
    return {"ok": True, "languages": out, "scripts": list(SCRIPTS),
            "pieces": {k: v[0] for k, v in langprompts.PIECES.items()},
            "may": {k: settingspage.may(k, where) for k in KEYS},
            "problems": [{"code": c, "why": w} for c, w in languages.PROBLEMS]}


def _argv(body):
    """The newlang.py command line the form's fields make: only the flags a
    person can be asked for in a form; everything else newlang works out."""
    def field(k):
        return str(body.get(k) or "").strip()
    code, name, native = field("code").lower(), field("name"), field("native")
    if not (code and name and native):
        raise ValueError("A code, the English name and the language's own name are needed.")
    argv = [code, "--name", name, "--native", native]
    script = field("script") or "latin"
    if script not in SCRIPTS:
        raise ValueError("Choose the kind of script from the list.")
    argv += ["--script", script]
    for key, flag in (("chars", "--chars"), ("like", "--like"), ("iso3", "--iso3"), ("font", "--font")):
        if field(key):
            argv += [flag, field(key)]
    if field("dir") in ("ltr", "rtl"):
        argv += ["--dir", field("dir")]
    return argv


def add(body, where=""):
    """Run newlang.py on the form -> (status, answer).  Its own words come back,
    the refusal or the list of what it wrote and what is left to write."""
    import newlang
    argv = _argv(body)
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = newlang.main(argv)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
    said = (err.getvalue().strip().replace("newlang: ", "") or out.getvalue().strip())
    if rc:
        return 400, {"ok": False, "error": said or "The language was not added."}
    languages.reload()
    return 200, {"ok": True, "code": argv[0], "said": out.getvalue(), "state": view(where)}


def api(what, body, where=""):
    """One route's work -> (status, answer).  Who may was asked first, of lib/settingspage.py ROUTES."""
    body = body if isinstance(body, dict) else {}
    try:
        if what == "state":
            return 200, view(where)
        if what == "prompt":
            code = str(body.get("code") or "")
            return 200, {"ok": True, "prompt": langprompts.prompt(code, str(body.get("piece") or ""),
                                                                   str(body.get("like") or "") or None),
                         "like": str(body.get("like") or "") or langprompts.like_for(code)}
        if what == "add":
            return add(body, where)
        if what == "answer":
            code = str(body.get("code") or "")
            if code not in languages.mine():
                return 400, {"ok": False, "error": "Only a language added on this computer takes prose here: "
                                                   "Parseh's own come with it, and an update would replace it."}
            path = langprompts.intake(code, str(body.get("piece") or ""), str(body.get("text") or ""))
            languages.reload()
            return 200, {"ok": True, "wrote": os.path.relpath(path, langprompts.ROOT), "state": view(where)}
    except (langprompts.Refused, ValueError) as e:
        return 400, {"ok": False, "error": str(e)}
    return 404, {"ok": False, "error": "%s has no such request." % settingspage.NAME}


def door_tags():
    n, mine = len(languages.LANGS), len(languages.mine())
    tags = '<span class="tag on">%d languages</span>' % n
    if mine:
        tags += '<span class="tag">%d added here</span>' % mine
    return tags


def page(where=""):
    v = view(where)
    main = """<main class="settings lg">
%(doors)s
<h1 class="idx">languages</h1>
<p class="whomay">%(gate)s <span>Every language %(name)s has, and what each one has: the conventions a chatbot is
given, printed books, the dictionary's rules, speech, pictograms. A language of your own is added at the end of the
page, and the prose it needs can be written with a chatbot.</span></p>
<div id="lg-say" role="status"></div>
<div id="lg"><p class="lg-wait">Reading the languages&hellip;</p></div>
<section id="lg-add" aria-labelledby="lg-add-h"></section>
<p class="foot">A language added here is this computer's: its row is kept in <code>config/languages.json</code> and its
files beside Parseh's own, and an update keeps both. <a href="%(guide)s" data-guide>Adding a language</a>, in the guide.</p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "gate": settingspage.gate(KEYS), "guide": esc(GUIDE),
              "name": settingspage.NAME}
    script = ('<script id="lg-state" type="application/json">%s</script>\n<script>%s</script>'
              % (settingspage._in_script(v), SCRIPT))
    return settingspage.frame("Languages &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; languages',
                              "Languages", GUIDE, main, style=STYLE, script=script)


STYLE = r"""
.lg .whomay{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap;margin:.2rem 0 1rem;font-size:13.5px;color:var(--dim)}
.lg .whomay .gate{flex:none}
.lg a{color:var(--accent)}
.lg .say{margin:0 0 14px;padding:8px 12px;border-radius:8px;border:1px solid var(--danger);color:var(--danger);font-size:14px}
.lg .said{margin:0 0 14px;padding:8px 12px;border-radius:8px;border:1px solid var(--ok);font-size:14px}
.lg details.lang{border:1px solid var(--rule);border-radius:10px;margin:8px 0;background:var(--card)}
.lg details.lang>summary{display:flex;gap:6px 12px;align-items:baseline;flex-wrap:wrap;padding:9px 14px;cursor:pointer;
  list-style:none;min-height:44px;box-sizing:border-box}
.lg details.lang>summary::-webkit-details-marker{display:none}
.lg summary .nm{font-weight:600}
.lg summary .nat{font-family:var(--tl-font, inherit)}
.lg summary .cnt{color:var(--dim);font-size:13px;margin-inline-start:auto}
.lg summary .mine{font-size:12px;border:1px solid var(--accent);color:var(--accent);border-radius:99px;padding:0 8px}
.lg summary .miss{font-size:12.5px;color:var(--danger);flex-basis:100%}
.lg .feats{list-style:none;margin:0;padding:0 14px 10px}
.lg .feats li{display:grid;grid-template-columns:1.4em minmax(9rem,13rem) minmax(0,1fr);gap:2px 10px;padding:6px 0;
  border-top:1px solid var(--rule);font-size:14px}
.lg .feats .mk{font-weight:700;text-align:center}
.lg .feats .have .mk,.lg .feats .asked .mk{color:var(--ok)}
.lg .feats .missing .mk{color:var(--danger)}
.lg .feats .optional .mk{color:var(--dim)}
.lg .feats .fn{font-weight:600}
.lg .feats .adds{grid-column:3;color:var(--dim);font-size:12.5px;overflow-wrap:anywhere}
.lg .feats .write{grid-column:3}
.lg .feats .says{overflow-wrap:anywhere;min-width:0}
@media (max-width:600px){
  .lg .feats li{grid-template-columns:1.4em minmax(0,1fr)}
  .lg .feats .says,.lg .feats .adds,.lg .feats .write{grid-column:2}
}
.lg .feats .asked .says::after{content:" (asked when it is fetched)";color:var(--dim);font-size:12.5px}
.lg button,.lg select,.lg input,.lg textarea{font:inherit}
.lg button{padding:.4rem .8rem;border-radius:8px;border:1px solid var(--rule);background:var(--card);color:inherit;
  cursor:pointer;min-height:36px}
.lg button.primary{border-color:var(--accent);background:var(--accent);color:var(--accent-fg,#fff);font-weight:600}
.lg button:disabled{opacity:.55;cursor:default}
.lg .pane{margin:.5rem 0 .3rem;padding:10px 12px;border-inline-start:3px solid var(--accent);background:var(--boxbg);
  border-radius:0 8px 8px 0}
.lg .pane .row{display:flex;gap:8px 12px;flex-wrap:wrap;align-items:center;margin:.35rem 0}
.lg .pane textarea{width:100%;min-height:9rem;box-sizing:border-box;border:1px solid var(--rule);border-radius:8px;
  padding:6px 8px;background:var(--bg);color:inherit}
.lg .pane .msg{font-size:13.5px}
.lg .pane .msg.bad{color:var(--danger)}
.lg #lg-add{border:1px solid var(--rule);border-radius:10px;padding:12px 16px 14px;margin:18px 0;background:var(--card)}
.lg #lg-add h2{margin:.1rem 0 .4rem;font-size:17px}
.lg #lg-add .lead{font-size:13.5px;color:var(--dim);margin:0 0 .7rem}
.lg .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:10px 16px}
.lg .grid label{display:flex;flex-direction:column;gap:3px;font-size:13.5px}
.lg .grid label small{color:var(--dim)}
.lg .grid input,.lg .grid select{padding:.35rem .5rem;border:1px solid var(--rule);border-radius:8px;background:var(--bg);
  color:inherit;min-height:36px;box-sizing:border-box}
.lg pre.out{white-space:pre-wrap;font-size:12.5px;max-height:22rem;overflow:auto;background:var(--boxbg);padding:8px 10px;
  border-radius:8px}
.lg .lock{font-size:13.5px;color:var(--dim)}
"""

SCRIPT = r"""
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('lg-state').textContent);
  var box = document.getElementById('lg'), say = document.getElementById('lg-say'), addBox = document.getElementById('lg-add');
  var open = {};
  var MARK = {have: '✓', asked: '✓', optional: '·', missing: '✗'};
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function post(route, body) {
    return fetch('/settings/api/languages/' + route, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})}).then(function (r) {
        return r.json().catch(function () { return {ok: false, error: 'The answer could not be read.'}; })
          .then(function (j) { if (!r.ok && j.ok !== false) j = {ok: false, error: 'Refused (' + r.status + ').'}; return j; });
      }, function () { return {ok: false, error: 'Parseh did not answer.'}; });
  }
  function likeOptions(sel, skip) {
    return S.languages.filter(function (l) { return l.code !== skip; }).map(function (l) {
      return '<option value="' + esc(l.code) + '"' + (l.code === sel ? ' selected' : '') + '>' + esc(l.name) + '</option>';
    }).join('');
  }
  function feature(l, f) {
    var write = '';
    if (l.mine && f.prompt && f.state !== 'have')
      write = '<div class="write"><button type="button" data-write="' + esc(f.prompt) + '">write it with a chatbot</button>' +
        '<div class="pane" data-pane="' + esc(f.prompt) + '" hidden></div></div>';
    return '<li class="' + esc(f.state) + '" data-feature="' + esc(f.key) + '"><span class="mk" aria-hidden="true">' +
      MARK[f.state] + '</span><span class="fn">' + esc(f.name) + '</span><span class="says">' + esc(f.says) + '</span>' +
      (f.adds && f.state !== 'have' ? '<span class="adds">' + esc(f.adds) + '</span>' : '') + write + '</li>';
  }
  function draw() {
    if (S.problems && S.problems.length)
      say.innerHTML = '<div class="say">' + S.problems.map(function (p) { return esc(p.code) + ': ' + esc(p.why); }).join('<br>') + '</div>';
    box.innerHTML = S.languages.map(function (l) {
      return '<details class="lang" data-code="' + esc(l.code) + '"' + (open[l.code] ? ' open' : '') + '><summary>' +
        '<span class="nm">' + esc(l.name) + '</span><span class="nat" lang="' + esc(l.code) + '" data-lang="' + esc(l.code) +
        '" dir="' + esc(l.dir) + '">' + esc(l.native) + '</span>' + (l.mine ? '<span class="mine">added here</span>' : '') +
        '<span class="cnt">' + l.have + ' of ' + l.of + ' features</span>' +
        (l.missing.length ? '<span class="miss">still needed: ' + esc(l.missing.join(', ')) + '</span>' : '') +
        '</summary><ul class="feats">' + l.features.map(function (f) { return feature(l, f); }).join('') + '</ul></details>';
    }).join('');
  }
  box.addEventListener('toggle', function (e) {
    var d = e.target.closest && e.target.closest('details.lang');
    if (d) open[d.getAttribute('data-code')] = d.open;
  }, true);
  box.addEventListener('click', function (e) {
    var b = e.target.closest('button[data-write]');
    if (b) return writePane(b);
  });
  function writePane(b) {
    var code = b.closest('details.lang').getAttribute('data-code'), piece = b.getAttribute('data-write');
    var pane = b.parentNode.querySelector('[data-pane]'), l = S.languages.filter(function (x) { return x.code === code; })[0];
    if (!pane.hidden) { pane.hidden = true; return; }
    pane.hidden = false;
    pane.innerHTML = '<div class="row"><label>model: <select data-like>' + likeOptions(l.like, code) + '</select></label>' +
      '<button type="button" class="primary" data-copy>copy the prompt</button><span class="msg" data-cmsg></span></div>' +
      '<p class="msg">Paste it in the chatbot of your choice, read what it writes, then paste its answer here.</p>' +
      '<textarea data-answer aria-label="the chatbot\'s answer" placeholder="the chatbot\'s answer"></textarea>' +
      '<div class="row"><button type="button" data-take' + (S.may['languages.prose'] ? '' : ' disabled') + '>take it in</button>' +
      '<span class="msg" data-tmsg>' + (S.may['languages.prose'] ? '' : 'Taken in on the computer Parseh runs on only.') +
      '</span></div>';
    var like = pane.querySelector('[data-like]');
    if (!l.like) post('prompt', {code: code, piece: piece}).then(function (j) { if (j.ok) like.value = j.like; });
    pane.querySelector('[data-copy]').addEventListener('click', function () {
      var m = pane.querySelector('[data-cmsg]');
      m.className = 'msg'; m.textContent = 'making it…';
      post('prompt', {code: code, piece: piece, like: like.value}).then(function (j) {
        if (!j.ok) { m.className = 'msg bad'; m.textContent = j.error; return; }
        var done = function () { m.textContent = 'copied: ' + j.prompt.length.toLocaleString() + ' characters'; };
        (navigator.clipboard ? navigator.clipboard.writeText(j.prompt) : Promise.reject()).then(done, function () {
          var t = document.createElement('textarea'); t.value = j.prompt; document.body.appendChild(t); t.select();
          try { document.execCommand('copy'); done(); } catch (e) { m.textContent = 'select and copy it from the box'; }
          document.body.removeChild(t);
        });
      });
    });
    pane.querySelector('[data-take]').addEventListener('click', function () {
      var m = pane.querySelector('[data-tmsg]');
      m.className = 'msg'; m.textContent = 'checking…';
      post('answer', {code: code, piece: piece, text: pane.querySelector('[data-answer]').value}).then(function (j) {
        if (!j.ok) { m.className = 'msg bad'; m.textContent = j.error; return; }
        S = j.state; open[code] = true; draw();
        say.innerHTML = '<div class="said">Written: <code>' + esc(j.wrote) + '</code></div>';
      });
    });
  }
  function drawAdd() {
    var may = S.may['languages.add'];
    addBox.innerHTML = '<h2 id="lg-add-h">Add a language</h2>' +
      '<p class="lead">Its row, its LaTeX file and the template of its conventions are written at once, with a ' +
      'related language as the starting point; the prose it then needs is listed in its card above, each piece with ' +
      'a prompt for a chatbot.</p>' +
      '<form class="grid" data-add>' +
      '<label>Code<small>two or three letters (ko, eu, nap)</small><input name="code" required maxlength="3" pattern="[a-z]{2,3}" autocomplete="off"></label>' +
      '<label>English name<small>Korean, Basque</small><input name="name" required autocomplete="off"></label>' +
      '<label>Its own name<small>한국어, euskara</small><input name="native" required autocomplete="off"></label>' +
      '<label>Script<small>what it is written in</small><select name="script">' + S.scripts.map(function (s) {
        return '<option>' + esc(s) + '</option>'; }).join('') + '</select></label>' +
      '<label data-chars hidden>Characters<small>the script\'s ranges, as a regular expression class</small>' +
      '<input name="chars" placeholder="\\uAC00-\\uD7AF" autocomplete="off"></label>' +
      '<label>Related language<small>its files are the model</small><select name="like"><option value="">none</option>' +
      likeOptions('', '') + '</select></label>' +
      '<label>ISO 639-3<small>for translated sentences (kor, eus)</small><input name="iso3" maxlength="3" autocomplete="off"></label>' +
      '<label>Font<small>optional: the face for its script</small><input name="font" autocomplete="off"></label>' +
      '<div><button type="submit" class="primary"' + (may ? '' : ' disabled') + '>add the language</button></div>' +
      '</form>' + (may ? '' : '<p class="lock">A language is added on the computer Parseh runs on only.</p>') +
      '<div data-addout></div>';
    var form = addBox.querySelector('[data-add]'), chars = addBox.querySelector('[data-chars]');
    form.script.addEventListener('change', function () { chars.hidden = form.script.value !== 'other'; });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var out = addBox.querySelector('[data-addout]'), body = {};
      ['code', 'name', 'native', 'script', 'chars', 'like', 'iso3', 'font'].forEach(function (k) { body[k] = form[k].value; });
      out.innerHTML = '<p class="lock">adding…</p>';
      post('add', body).then(function (j) {
        if (!j.ok) { out.innerHTML = '<div class="say">' + esc(j.error) + '</div>'; return; }
        S = j.state; open[j.code] = true; draw(); drawAdd();
        addBox.querySelector('[data-addout]').innerHTML = '<div class="said">Added. What was written, and what is left:</div>' +
          '<pre class="out">' + esc(j.said) + '</pre>';
        var d = box.querySelector('details[data-code="' + j.code + '"]');
        if (d) d.scrollIntoView({block: 'start'});
      });
    });
  }
  draw(); drawAdd();
})();
"""
