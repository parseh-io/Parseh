# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> Your prompts (brief §8.5, a0.4.2): every prompt a person wrote
for a chatbot, by the place it is for, with export, import and delete.

THE MENUS ARE ELSEWHERE.  A prompt is made, edited, saved as and chosen from
the row beside the button that copies a prompt, on every page that hands one
out (lib/llmrow.js); this page is where they are all seen together, taken to
another computer as files, brought in from one, or thrown away.  It reads and
writes through the same routes the row does (/settings/api/prompts/...,
lib/prompts.py api()).

ANY DEVICE THAT HAS BEEN LET IN MAY DO ALL OF IT, and the door's pill says so
(lib/settingspage.py SETTINGS says why: what a prompt says is text a person
copies, and decides nothing Parseh will run).  So there is no lock on this page
and no dead button; a control is disabled only where the table said no, which
it never does today.

Parseh's own prompts are not on it: they are not in the store, and cannot be
changed or deleted from anywhere.
"""
import html
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import prompts                                               # noqa: E402
import settingspage                                          # noqa: E402

PAGE = "/settings/prompts/"
GUIDE = "/guide/site/studio/your-prompts.html"
# the two settings this page's buttons are, and only these
KEYS = ("prompts.save", "prompts.delete")


def esc(s):
    return html.escape(str(s), quote=True)


def view(where=""):
    """Everything the page draws, in one answer."""
    return dict(prompts.view(), ok=True, where=where or "",
                may={k: settingspage.may(k, where) for k in KEYS})


def page(where=""):
    """/settings/prompts/, the whole page."""
    main = """<main class="settings pr">
%(doors)s
<h1 class="idx">your prompts</h1>
<p class="whomay">%(gate)s <span>%(name)s&rsquo;s own prompts are not listed here: they cannot be changed or deleted. Any device that has been let in may keep, import or delete one of
these: what a prompt says is text you copy into a chatbot, and decides nothing %(name)s runs.</span></p>
<div id="pr"><p>Reading what is here&hellip;</p></div>
<p class="foot">Your prompts are kept in <code>config/prompts.json</code>, and an update keeps them. A
prompt is made from the <b>prompt</b> menu beside the button that copies one, on the page that
hands it out. <a href="%(guide)s">Your prompts</a>, in the guide.</p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "gate": settingspage.gate(KEYS),
              "name": settingspage.NAME, "guide": esc(GUIDE)}
    script = ('<script id="pr-state" type="application/json">%s</script>\n<script>%s</script>'
              % (settingspage._in_script(view(where)), SCRIPT))
    return settingspage.frame("Your prompts &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; your prompts',
                              "Your prompts", GUIDE, main, style=STYLE, script=script)


STYLE = r"""
.pr .whomay{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap;margin:.2rem 0 1rem;font-size:13.5px;color:var(--dim)}
.pr .whomay .gate{flex:none}
.pr .pk{border:1px solid var(--rule);border-radius:10px;padding:10px 14px;margin:10px 0;background:var(--card)}
.pr .pk h3{margin:0 0 4px;font-size:16px;overflow-wrap:anywhere}
.pr .pk .facts{color:var(--dim);font-size:13px}
.pr .pk .old{margin:6px 0 0;font-size:13px;border-inline-start:3px solid var(--warn);padding:2px 0 2px 10px}
.pr .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px}
.pr .sure{margin:8px 0 0;padding:8px 10px;border:1px dashed var(--rule);border-radius:8px;background:var(--boxbg);font-size:13.5px}
.pr .sure .row{margin-top:6px}
.pr details{margin-top:8px;font-size:13px}
.pr summary{cursor:pointer;color:var(--dim);width:max-content;max-width:100%}
.pr pre.text{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--boxbg);padding:8px;border-radius:6px;font-size:12px;
  max-height:22rem;overflow:auto;margin:6px 0 0}
.pr .said{min-height:1.4em;font-size:13.5px;margin:.6rem 0}
.pr .bad{color:var(--danger,#c33)}
.pr .none{color:var(--dim);font-size:14px}
.pr section h2{display:flex;gap:.6rem;align-items:baseline;justify-content:space-between}
.pr section h2 small{flex:none;font-weight:400;color:var(--dim);font-size:.85rem}
"""

SCRIPT = r"""
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('pr-state').textContent);
  var root = document.getElementById('pr');
  var API = '/settings/api/prompts/';
  var asking = null;          // the id whose deletion is being asked about
  var shown = {};             // the ids whose text is unfolded: kept while the rest redraws
  var told = {text: '', bad: false};
  function esc(s) { return String(s == null ? '' : s).replace(/[<>&"]/g, function (c) {
    return {'<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;'}[c]; }); }
  function post(what, body) {
    return fetch(API + what, {method: 'POST', headers: {'Content-Type': 'application/json'},
                              body: JSON.stringify(body || {})})
      .then(function (r) { return r.json().catch(function () { return {ok: false, error: r.statusText}; }); });
  }
  function may(k) { return !!S.may[k]; }
  function dis(k) { return may(k) ? '' : ' disabled'; }
  function count(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function when(at) {
    if (!at) return 'at some point';
    var gap = Math.max(0, Date.now() / 1000 - at);
    if (gap < 90) return 'a moment ago';
    if (gap < 3600) return Math.round(gap / 60) + ' minutes ago';
    if (gap < 86400) return Math.round(gap / 3600) + ' hours ago';
    if (gap < 30 * 86400) return Math.round(gap / 86400) + ' days ago';
    return new Date(at * 1000).toLocaleDateString(undefined, {day: 'numeric', month: 'long', year: 'numeric'});
  }
  function said(text, bad) { told = {text: text || '', bad: !!bad}; var el = root.querySelector('[data-said]'); if (el) paintSaid(el); }
  function paintSaid(el) { el.textContent = told.text; el.className = 'said' + (told.bad ? ' bad' : ''); }
  function language(p) {
    if (!p.languages.length) return 'for every language';
    var code = p.languages[0];
    return 'for ' + (S.languages[code] ? esc(S.languages[code]) : esc(code) + ' (a language this computer does not have)') + ' only';
  }
  function card(p) {
    var mine = asking === p.id;
    return '<div class="pk" data-prompt="' + esc(p.id) + '"><h3 dir="auto">' + esc(p.name) + '</h3>' +
      '<div class="facts">' + (p.kind === 'replace' ? 'in place of Parseh’s instructions' : 'added after Parseh’s instructions') +
      ' · ' + language(p) + ' · ' + count(p.size) + ' characters · changed ' + when(p.updated_at) + '</div>' +
      (p.stale ? '<p class="old" data-old>Parseh’s own prompt has changed since you started from this one. Open it from the prompt menu beside a copy button to see what changed.</p>' : '') +
      '<details data-text="' + esc(p.id) + '"' + (shown[p.id] ? ' open' : '') + '><summary>read it</summary><pre class="text" dir="auto">' + esc(p.text) + '</pre></details>' +
      (mine
        ? '<div class="sure" role="alertdialog" aria-label="Delete ' + esc(p.name) + '?">Delete <b dir="auto">' + esc(p.name) + '</b>? It cannot be got back.' +
          '<div class="row"><button type="button" class="danger" data-delete-yes="' + esc(p.id) + '">Delete it</button>' +
          '<button type="button" class="plain" data-keep>Keep it</button></div></div>'
        : '<div class="row"><a class="plain" href="' + API + 'export?id=' + encodeURIComponent(p.id) + '" aria-label="Export ' + esc(p.name) + '">Export</a>' +
          '<button type="button" class="plain" data-delete="' + esc(p.id) + '" aria-label="Delete ' + esc(p.name) + '"' + dis('prompts.delete') + '>Delete…</button></div>') +
      '</div>';
  }
  function draw() {
    var by = {};
    S.prompts.forEach(function (p) { (by[p.surface] = by[p.surface] || []).push(p); });
    var sections = S.surfaces.filter(function (s) { return by[s.id]; }).map(function (s) {
      return '<section><h2><span>' + esc(s.label) + '</span><small>' + by[s.id].length + '</small></h2>' + by[s.id].map(card).join('') + '</section>';
    }).join('');
    root.innerHTML =
      (sections || '<section><p class="none" data-none>You have no prompts of your own yet. You make one from the <b>prompt</b> menu beside the button that copies a prompt, on any page that hands one out, and it is listed here.</p></section>') +
      '<section><h2>Import a prompt</h2><p class="why">A prompt someone exported, from this computer or another. One that has the name of a prompt you already have for that place is kept under a new name, and never written over yours.</p>' +
      '<div class="row"><button type="button" class="plain" data-import-open' + dis('prompts.save') + '>Import a prompt…</button>' +
      '<input type="file" data-import accept=".json,application/json" hidden' + dis('prompts.save') + '></div></section>' +
      '<div class="said" aria-live="polite" data-said></div>';
    paintSaid(root.querySelector('[data-said]'));
  }
  function reload() {
    return post('state').then(function (v) { if (v.ok) { S.prompts = v.prompts; S.languages = v.languages; draw(); } });
  }
  function focusOn(selector) { var el = root.querySelector(selector); if (el) el.focus(); }

  root.addEventListener('toggle', function (e) {
    var id = e.target.getAttribute && e.target.getAttribute('data-text');
    if (id) shown[id] = e.target.open;
  }, true);
  root.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('button') : null;
    if (!b) return;
    var a = function (n) { return b.getAttribute(n); };
    if (a('data-import-open') !== null) { var picker = root.querySelector('[data-import]'); if (picker) picker.click(); return; }
    if (a('data-delete')) {
      told = {text: '', bad: false}; asking = a('data-delete'); draw(); focusOn('[data-keep]'); return;
    }
    if (a('data-keep') !== null) {
      var was = asking; asking = null; draw();
      focusOn('[data-delete="' + was + '"]'); return;
    }
    if (a('data-delete-yes')) {
      var id = a('data-delete-yes');
      var p = S.prompts.filter(function (x) { return x.id === id; })[0];
      // the page is read again either way: a prompt another device took away is gone from it too
      post('delete', {id: id}).then(function (r) {
        asking = null;
        return reload().then(function () {
          if (r.ok) said('Deleted “' + (p ? p.name : 'the prompt') + '”.');
          else said(r.error || 'Parseh could not do that.', true);
        });
      }, function () { said('The delete could not be sent: this computer did not answer.', true); });
    }
  });
  root.addEventListener('change', function (e) {
    var f = e.target.matches && e.target.matches('[data-import]') ? e.target.files[0] : null;
    if (!f) return;
    var input = e.target;
    f.text().then(function (text) {
      return post('import', {data: text});
    }).then(function (r) {
      input.value = '';
      if (!r.ok) { said(r.error || 'Parseh could not read that file.', true); return; }
      var name = r.prompt.name;
      reload().then(function () {
        said(r.renamed_from
          ? 'Imported as “' + name + '”: you have a prompt called “' + r.renamed_from + '” for this already, and an import never writes over one.'
          : 'Imported as “' + name + '”.');
      });
    }).catch(function () { input.value = ''; said('That file could not be read, or this computer did not answer.', true); });
  });
  draw();
})();
"""
