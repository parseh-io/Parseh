# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> Backups (TO-DO §13.19): every backup in one place, with the day
each was last taken.

    Everything        one zip for a new computer (lib/wholebackup.py): Backup, Load
    Your settings     config/ without what is the computer's (lib/configbackup.py): Backup, Load
    The four shelves  each shelf's own Backup button, and its day; its Load is on its page

WHY A DOOR OF SETTINGS.  The four shelves keep their buttons on their own
pages, where a person looks for them, and those pages show the day too
(lib/backupday.js).  But config/ belongs to no shelf, and "everything" to all
of them: their place is the one page that is about this computer as a whole,
and the guide's "Backups" page points here.  The shelves' buttons are
repeated here so that one page answers "when did I last back up, and what?".

WHO MAY.  Taking a backup is a read: any device that has been let in may
download one (it is that device's person's own things).  LOADING one is the
computer's alone (lib/settingspage.py, "backups.load"): it writes the
person's LaTeX themes and a language's LaTeX file -- what Parseh will run --
and puts whole shelves in place.  A phone sees the page, the days and the
download buttons, and a lock where the Load buttons are.
"""
import html
import json
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import backupdays                                            # noqa: E402
import configbackup                                          # noqa: E402
import settingspage                                          # noqa: E402

PAGE = "/settings/backups/"
GUIDE = "/guide/site/getting-started/backups.html"
API = "/settings/api/backups/"
LOAD = "backups.load"

SHELVES = (("book", "Books", "/books/", "/books/__backup", "the books' library, panel ⇩ The whole shelf"),
           ("video", "Videos", "/youtube/", "/youtube/api/backup", "the video index, panel ⇩ The whole shelf"),
           ("studio", "Studio documents", "/studio/", "/studio/api/export", "the studio's library, Backup ▾"),
           ("decks", "Exercise decks", "/exercises/", "/exercises/api/backup", "the exercise decks, at the top"))


def esc(s):
    return html.escape(str(s), quote=True)


def state():
    return {"ok": True, "days": backupdays.view(), "present": configbackup.present()}


def page(where=""):
    may = settingspage.may(LOAD, where)
    lock = settingspage.lockline(LOAD, where, "Loading a backup is done on the computer only.")
    days = backupdays.view()

    def day(k):
        d = days[k]
        return '<small class="backupday" data-backup-day="%s">%s</small>' % (
            k, esc("last backup: " + d["said"]) if d["at"] else "never backed up")
    shelves = "".join(
        '<tr><td><b>%s</b></td><td><a class="plain" href="%s" download>Backup</a></td><td>%s</td>'
        '<td><a href="%s">Load from backup</a> <small>on %s</small></td></tr>'
        % (esc(name), esc(href), day(k), esc(page_), esc(where_said)) for k, name, page_, href, where_said in SHELVES)
    stores = "".join("<li><b>%s</b> &mdash; %s</li>" % (esc(n), esc(label)) for n, label, _w in configbackup.STORES)
    left = "".join("<li><b>%s</b> &mdash; %s</li>" % (esc(n), esc(w)) for n, w in configbackup.LEFT_OUT)
    disabled = "" if may else " disabled"
    main = """<main class="settings bk-page">
%(doors)s
<h1 class="idx">backups</h1>
<p class="whomay">%(gate)s <span>Any device that has been let in may take a backup and see when each was taken.
Loading one is done on the computer %(name)s runs on.</span></p>

<section id="everything"><h2>Everything, for a new computer</h2>
<p class="why">One zip holding the four shelves &mdash; books, videos, studio documents, exercise decks &mdash; your
settings, the Anki card store and the clip tray. On the new computer, install %(name)s and load it here: your settings
go back first, then each shelf, each through its own Load from backup.</p>
<div class="actions"><a class="go" href="%(api)severything" download data-get="everything">Backup everything</a>
%(day_everything)s</div>
<div class="actions"><button type="button" class="plain" data-load="everything"%(disabled)s>Load everything from a backup&hellip;</button>
<label class="door"><input type="checkbox" data-replace%(disabled)s> <b>Replace</b> what is already here
<span class="said">A book, a video, a document, a deck or a card deck already here is kept and named, unless this is
ticked. Your settings are merged either way.</span></label></div>
%(lock)s
<div class="doing" data-said="everything" role="status"></div>
</section>

<section id="settings"><h2>Your settings</h2>
<p class="why">What no shelf holds: what is kept in %(name)s&rsquo;s <code>config/</code> folder for you.</p>
<ul class="stores">%(stores)s</ul>
<div class="actions"><a class="go" href="%(api)ssettings" download data-get="settings">Backup your settings</a>
%(day_settings)s
<button type="button" class="plain" data-load="settings"%(disabled)s>Load from backup&hellip;</button></div>
%(lock)s
<div class="doing" data-said="settings" role="status"></div>
<div data-plan hidden></div>
<details><summary>What is left out, and why</summary><ul class="stores">%(left)s</ul></details>
</section>

<section id="shelves"><h2>Each shelf</h2>
<p class="why">The same backups as the button on each shelf&rsquo;s page; loading one is done there.</p>
<table class="devices">%(shelves)s</table>
</section>
<input type="file" data-file accept=".zip,application/zip,application/x-zip-compressed" hidden>
<p class="foot"><a href="%(guide)s">Backups</a>, in the guide.</p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "gate": settingspage.gate(settingspage.door_keys(PAGE)),
              "name": settingspage.NAME, "api": API, "day_everything": day("everything"),
              "day_settings": day("settings"), "disabled": disabled, "lock": lock, "stores": stores,
              "left": left, "shelves": shelves, "guide": esc(GUIDE)}
    return settingspage.frame("Backups &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; backups', "Backups", GUIDE, main,
                              style=STYLE, script='<script src="/lib/backupday.js" defer></script><script>%s</script>'
                              % SCRIPT.replace("__API__", json.dumps(API)))


STYLE = r"""
.bk-page .whomay{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap;margin:.2rem 0 1rem;font-size:13.5px;color:var(--dim)}
.bk-page .whomay .gate{flex:none}
.bk-page .backupday{color:var(--dim);font-size:13px}
.bk-page ul.stores{margin:.3rem 0 .6rem;padding-inline-start:1.2rem;font-size:14px}
.bk-page table.devices td{vertical-align:baseline}
.bk-page .plan h3{font-size:15px;margin:.9rem 0 .2rem}
.bk-page .plan table{border-collapse:collapse;width:100%;font-size:13.5px}
.bk-page .plan td,.bk-page .plan th{text-align:start;padding:.25rem .4rem;border-bottom:1px solid var(--rule,#8883);vertical-align:top;overflow-wrap:anywhere}
.bk-page .plan .st{white-space:nowrap;font-weight:600}
.bk-page .plan .n{color:var(--dim)}
.bk-page .doing ul{margin:.3rem 0;padding-inline-start:1.2rem}
.bk-page .foot a{color:var(--accent,#be3455);text-decoration:underline}
@media (max-width:40rem){.bk-page table.devices td{display:block;border:0;padding:.15rem 0}.bk-page table.devices tr{display:block;padding:.4rem 0;border-bottom:1px solid var(--rule)}}
"""

SCRIPT = r"""
(function () {
  'use strict';
  var API = __API__;
  var file = document.querySelector('[data-file]'), want = null;
  function el(t, cls, text) { var e = document.createElement(t); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function said(which) { return document.querySelector('[data-said="' + which + '"]'); }
  function say(which, text, bad) { var s = said(which); s.textContent = text; s.classList.toggle('bad', !!bad); return s; }
  function post(url, body, type) {
    return fetch(url, {method: 'POST', body: body, credentials: 'same-origin',
                       headers: type ? {'Content-Type': type} : {}})
      .then(function (r) { return r.json().then(function (j) { if (!r.ok || j.ok === false) throw new Error(j.error || ('HTTP ' + r.status)); return j; }); });
  }
  var STATE = {added: 'added', differs: 'differs', 'left out': 'left out'};
  var WILL = {backup: "the backup's", mine: 'yours stays'};
  // THE PLAN: store by store, what loading does. A row the store decides by its own rule says which side wins and
  // why; a row with no such rule offers the two, keeping yours unless the backup's is picked.
  function drawPlan(box, plan, done) {
    box.innerHTML = ''; box.hidden = false; box.className = 'plan';
    var choices = 0;
    (plan.stores || []).forEach(function (s) {
      box.appendChild(el('h3', '', s.label + ' (' + s.store + ')'));
      if (!s.rows.length) { box.appendChild(el('p', 'n', done ? 'Nothing changed.' : 'The same here as in the backup.')); return; }
      var t = el('table'); var head = el('tr');
      ['', 'what', 'yours', "the backup's", ''].forEach(function (h) { head.appendChild(el('th', '', h)); });
      t.appendChild(head);
      s.rows.forEach(function (r) {
        var tr = el('tr'); tr.setAttribute('data-row', r.id);
        tr.appendChild(el('td', 'st', STATE[r.state] || r.state));
        tr.appendChild(el('td', '', r.what));
        tr.appendChild(el('td', '', r.mine || ''));
        tr.appendChild(el('td', '', r.theirs || ''));
        var last = el('td');
        if (r.will === 'choose' && !done) {
          choices++;
          var name = 'c' + Math.random().toString(36).slice(2);
          [['mine', 'keep yours'], ['backup', "take the backup's"]].forEach(function (o, i) {
            var lab = el('label'); var inp = el('input'); inp.type = 'radio'; inp.name = name; inp.value = o[0];
            inp.checked = i === 0; inp.setAttribute('data-choose', r.id);
            lab.appendChild(inp); lab.appendChild(document.createTextNode(' ' + o[1] + ' '));
            last.appendChild(lab);
          });
        } else if (r.will === 'choose') {
          last.textContent = 'yours kept unless chosen';
        } else {
          last.textContent = (WILL[r.will] || '') + (r.why ? ' — ' + r.why : '');
        }
        tr.appendChild(last); t.appendChild(tr);
      });
      box.appendChild(t);
      if (s.more) box.appendChild(el('p', 'n', 'and ' + s.more + ' more'));
    });
    if ((plan.notes || []).length) {
      var ul = el('ul'); plan.notes.forEach(function (n) { ul.appendChild(el('li', '', n)); }); box.appendChild(ul);
    }
    return choices;
  }
  function chosen(box) {
    var out = {};
    Array.prototype.forEach.call(box.querySelectorAll('input[data-choose]:checked'), function (i) {
      if (i.value === 'backup') out[i.getAttribute('data-choose')] = 'backup';
    });
    return out;
  }
  function offerApply(box, token, which, label) {
    var row = el('div', 'actions');
    var go = el('button', 'go', label); go.type = 'button'; go.setAttribute('data-apply', '');
    var no = el('button', 'plain', 'Cancel'); no.type = 'button';
    row.appendChild(go); row.appendChild(no); box.appendChild(row);
    no.onclick = function () { box.hidden = true; box.innerHTML = ''; say(which, 'Nothing was loaded.'); };
    go.onclick = function () {
      go.disabled = true; say(which, 'Loading…');
      post(API + 'settings/apply', JSON.stringify({token: token, choose: chosen(box)}), 'application/json')
        .then(function (j) {
          drawPlan(box, j, true);
          say(which, j.wrote.length ? 'Loaded: ' + j.wrote.join(', ') + '.' : 'Loaded: nothing needed changing.');
        })
        .catch(function (e) { go.disabled = false; say(which, e.message, true); });
    };
  }
  function loadSettings(f) {
    var box = document.querySelector('[data-plan]');
    say('settings', 'Reading ' + f.name + '…');
    post(API + 'settings/read', f, 'application/zip').then(function (j) {
      var n = drawPlan(box, j, false);
      say('settings', 'Made ' + (j.made || 'at some point') + (j.version ? ' by Parseh ' + j.version : '') +
          '. Nothing is loaded until you press Load these.' + (n ? ' ' + n + ' differ with no rule of their own: choose for each.' : ''));
      offerApply(box, j.token, 'settings', 'Load these');
    }).catch(function (e) { box.hidden = true; say('settings', e.message, true); });
  }
  function loadEverything(f) {
    var replace = document.querySelector('[data-replace]').checked;
    var s = say('everything', 'Sending ' + f.name + ' and putting everything back… (the Working… list says how far)');
    post(API + 'everything/load' + (replace ? '?replace=1' : ''), f, 'application/zip').then(function (j) {
      s.textContent = ''; s.classList.remove('bad');
      s.appendChild(el('p', '', 'Loaded from a backup made ' + (j.made || 'at some point') + '.'));
      var ul = el('ul');
      (j.parts || []).forEach(function (p) {
        var t = p.part + ': ';
        if (p.error) t += 'not loaded — ' + p.error;
        else {
          t += p.restored.length + ' put back';
          if (p.kept.length) t += ', ' + p.kept.length + ' already here and kept (' + p.kept.slice(0, 8).join(', ') + (p.kept.length > 8 ? ', …' : '') + ')';
          if (p.warnings.length) t += '; ' + p.warnings.join('; ');
        }
        ul.appendChild(el('li', p.error ? 'bad' : '', t));
      });
      s.appendChild(ul);
      if ((j.empty || []).length) s.appendChild(el('p', '', 'Empty in the backup: ' + j.empty.join(', ') + '.'));
      var choose = [];
      ((j.settings && j.settings.stores) || []).forEach(function (st) { choose = choose.concat(st.choose || []); });
      if (choose.length && j.token) {
        var box = document.querySelector('[data-plan]');
        drawPlan(box, {stores: j.settings.stores.filter(function (st) { return (st.choose || []).length; }).map(function (st) {
          return {store: st.store, label: st.label, rows: st.choose, more: 0}; })}, false);
        say('settings', choose.length + ' of your settings differ from the backup’s and were kept as they are here: choose below.');
        offerApply(box, j.token, 'settings', 'Take the ones chosen');
        document.getElementById('settings').scrollIntoView({behavior: 'smooth'});
      }
    }).catch(function (e) { say('everything', e.message, true); });
  }
  Array.prototype.forEach.call(document.querySelectorAll('[data-load]'), function (b) {
    b.addEventListener('click', function () { want = b.getAttribute('data-load'); file.value = ''; file.click(); });
  });
  file.addEventListener('change', function () {
    var f = file.files && file.files[0];
    if (!f) return;
    if (want === 'settings') loadSettings(f); else loadEverything(f);
  });
})();
"""
