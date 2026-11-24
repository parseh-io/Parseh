// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — sync on a thing's own page (a0.7.0, lane E; docs/sync.md).

     ParsehLease.hold(spec, holder) -> Promise<lease>   spec: {unit} or {path}; lease.release(), lease.releaseWhenGone(el)

   THE BANNER.  A unit changed on both computers, or deleted on a partner, waits
   for an answer; the question is listed on Settings -> Devices AND shown here,
   on the unit's own page (a studio document, a video, a book, a deck), with a
   link to the page that answers it.  A build whose source changed through sync
   (a book's reader, a studio PDF) gets a mark that says so, with a button to
   build it again; nothing rebuilds on its own.

   THE LEASE.  An editor open on a unit holds it against sync (lib/synclock.py):
   the studio editor, a video's phrase editor, an exercise's form, a deck's
   options.  It takes a lease when it opens, renews it every minute while it is
   open and gives it back when it closes; a page that dies without a word lets
   it run out after two minutes.  While a sync is writing the unit, the editor
   cannot open: it says so and opens a moment later, by itself.

   Which unit: the page says it (body[data-sync-unit], written by the server),
   or the server knows it by the page's address.  Loaded by lib/parseh.js on
   every page it serves, and by the studio's own templates. */
(function () {
  'use strict';
  if (window.ParsehLease || location.protocol === 'file:') return;
  var API = '/settings/api/devices/';
  var KEEP_EVERY = 60000;

  function post(route, body, beacon) {
    var data = JSON.stringify(body || {});
    if (beacon) {
      // A PAGE BEING LEFT: a beacon (a plain-text body needs no question first) AND a keepalive fetch, since
      // either may be dropped as the page goes; a second close is answered "not held" and changes nothing
      try { if (navigator.sendBeacon) navigator.sendBeacon(API + route, new Blob([data], {type: 'text/plain'})); }
      catch (e) { /* the fetch below still goes */ }
    }
    return fetch(API + route, {method: 'POST', credentials: 'same-origin', keepalive: !!beacon,
                               headers: {'Content-Type': 'application/json'}, body: data})
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { j.status = r.status; return j; }); });
  }
  function here() {
    var b = document.body;
    var u = b && b.getAttribute('data-sync-unit');
    return u ? {unit: u, path: location.pathname} : {path: location.pathname};
  }

  /* ---------------------------------------------------------------- the waiting note */
  var note = null;
  function waiting(on, text) {
    if (!on) { if (note) { note.remove(); note = null; } return; }
    if (!note) {
      note = document.createElement('div');
      note.setAttribute('data-sync-busy', '');
      note.setAttribute('role', 'status');
      note.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:2147483000;' +
        'max-width:calc(100vw - 32px);box-sizing:border-box;padding:10px 14px;border-radius:8px;font:14px/1.4 system-ui,sans-serif;' +
        'background:var(--ink,#222);color:var(--bg,#fff);box-shadow:0 4px 18px #0004';
      document.body.appendChild(note);
    }
    note.textContent = text;
  }

  function Lease(token, ticket) {
    var self = this, timer = null, gone = false;
    this.token = token;
    function keep() {
      if (gone || !token) return;
      post('lease-keep', {token: token}).then(function (j) {
        if (j && j.kept === false && !gone) {
          // it ran out (a sleeping laptop): take a new one for the same unit
          post('lease-open', self.spec).then(function (k) { if (k && k.token) token = self.token = k.token; });
        }
      }).catch(function () {});
    }
    if (token) timer = setInterval(keep, KEEP_EVERY);
    this.release = function () {
      if (gone) return; gone = true; clearInterval(timer);
      if (token || ticket) post('lease-close', {token: token, ticket: ticket}, true).catch(function () {});
    };
    this.releaseWhenGone = function (el) {
      if (!el) return self;
      var mo = new MutationObserver(function () { if (!el.isConnected) { mo.disconnect(); self.release(); } });
      mo.observe(document.body, {childList: true, subtree: true});
      return self;
    };
    window.addEventListener('pagehide', function () { self.release(); });
  }
  function ticketOf() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }

  function hold(spec, holder) {
    spec = Object.assign({}, spec || here(), {holder: holder || 'editor'});
    return new Promise(function (resolve) {
      var tries = 0, ticket = null, left = false;
      // a page left while its lease is on its way still lets go: by the ticket it sent
      function leaving() { left = true; if (ticket) post('lease-close', {ticket: ticket}, true).catch(function () {}); }
      window.addEventListener('pagehide', leaving);
      (function ask() {
        ticket = ticketOf();
        spec.ticket = ticket;
        post('lease-open', spec).then(function (j) {
          if (left) return;
          if (j.status === 409 && tries < 150) {
            tries++;
            waiting(true, j.error || 'Sync is writing this just now; it opens in a moment.');
            setTimeout(ask, 2000);
            return;
          }
          waiting(false);
          window.removeEventListener('pagehide', leaving);
          var l = new Lease(j.token || null, ticket); l.spec = spec; l.unit = j.unit || null;
          resolve(l);
        }).catch(function () {
          waiting(false); window.removeEventListener('pagehide', leaving);
          var l = new Lease(null, ticket); l.spec = spec; resolve(l);
        });
      })();
    });
  }
  window.ParsehLease = {hold: hold, here: here};

  /* ---------------------------------------------------------------- the banner and the mark */
  function banner(info) {
    var q = info.question;
    var bar = document.createElement('div');
    bar.setAttribute('data-sync-banner', q.kind);
    bar.setAttribute('role', 'status');
    bar.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;padding:9px 14px;margin:0;' +
      'font:14px/1.4 system-ui,sans-serif;background:var(--card,#fff6e0);color:var(--ink,#222);' +
      'border-bottom:2px solid var(--accent,#be3455);position:relative;z-index:50';
    var who = q.partner_name || 'a partner';
    var text = q.kind === 'choice' ? 'This was changed here and on ' + who + '. Sync waits for you to keep one.'
      : q.kind === 'deletion-edited' ? 'This was deleted on ' + who + ' and edited here. Sync waits for your answer.'
      : 'This was deleted on ' + who + '. Sync waits for your answer.';
    if (q.count > 1) text += ' (One question for ' + q.count + ' things.)';
    var s = document.createElement('span'); s.textContent = text; s.style.flex = '1 1 16rem';
    bar.appendChild(s);
    var a = document.createElement('a');
    a.href = q.page; a.textContent = q.kind === 'choice' ? 'Choose which to keep' : 'Answer';
    a.setAttribute('data-sync-answer', '');
    a.style.cssText = 'font-weight:600;color:var(--accent,#be3455)';
    if (!info.may_answer) { a.removeAttribute('href'); a.textContent = 'Answered on the computer Parseh runs on'; a.style.fontWeight = '400'; }
    bar.appendChild(a);
    document.body.insertBefore(bar, document.body.firstChild);
  }
  function mark(info) {
    var m = document.createElement('div');
    m.setAttribute('data-sync-ood', '');
    m.setAttribute('role', 'status');
    m.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;padding:7px 14px;' +
      'font:13.5px/1.4 system-ui,sans-serif;background:var(--boxbg,#eee);color:var(--ink,#222);border-bottom:1px dashed var(--rule,#999)';
    var s = document.createElement('span');
    s.textContent = 'Out of date: ' + (info.what || 'this was built') + ' from an older source; its source changed through sync.';
    s.style.flex = '1 1 16rem';
    m.appendChild(s);
    // the page's own build button, where it has one: the studio's Build PDF; a book's reader is rebuilt from its
    // library, where Rebuild is
    var own = document.getElementById('btn-build');
    var b = document.createElement(own ? 'button' : 'a');
    b.textContent = own ? 'Build again' : 'Rebuild';
    b.setAttribute('data-sync-rebuild', '');
    if (own) { b.type = 'button'; b.addEventListener('click', function () { own.click(); m.remove(); }); }
    else b.href = '/books/';
    m.appendChild(b);
    document.body.insertBefore(m, document.body.firstChild);
  }
  function look() {
    var spec = here();
    if (/^\/settings\//.test(location.pathname)) return;
    post('unit', spec).then(function (j) {
      if (!j || j.ok === false || !j.unit) return;
      if (j.out_of_date) mark(j);
      if (j.question) banner(j);
    }).catch(function () {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', look); else look();

  /* THE STUDIO EDITOR holds its document for as long as the page is open: while
     a sync writes it, the text cannot be typed in, and the note says why */
  function studioEditor() {
    var src = document.getElementById('src');
    if (!src || document.body.getAttribute('data-page') !== 'edit' || !document.body.getAttribute('data-sync-unit')) return;
    var was = src.readOnly;
    src.readOnly = true;
    hold(here(), 'studio').then(function () { src.readOnly = was; });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', studioEditor); else studioEditor();
})();
