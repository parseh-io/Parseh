/* SPDX-License-Identifier: GPL-3.0-or-later
   A heavy action this computer cannot do, sent to a paired one (a0.7.0, lane D;
   lib/syncjobs.py, docs/sync.md "Jobs").

     ParsehJobs.fetch(url, opts, o)   fetch() for a door that may lend its work:
                                      the same Response back, as if the work had
                                      been done here
       o.defer   resolve as soon as the job is sent (the page follows it itself,
                 as a book's build does through __build/status)

   When "send heavy jobs to paired computers" is on and this computer cannot do
   the work, the door answers 409 with `jobs.send` (the paired computers, and
   whether each can).  A small panel then says why and offers "Send to
   <partner>"; pressed, the same request goes again with `send_to`, and the
   panel follows the job: "waiting for a computer", "on <partner>", "done".  With
   "send" off the door answers as it always did, and so does this.

   Loaded by lib/parseh.js from beside itself, like lib/activity.js. */
(function () {
  if (window.ParsehJobs) return;
  var FOLLOW_MS = 2000;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function style() {
    if (document.getElementById('pj-style')) return;
    var s = el('style');
    s.id = 'pj-style';
    s.textContent =
      '.pj-panel{position:fixed;left:1rem;bottom:1rem;z-index:2147483000;max-width:min(26rem,calc(100vw - 2rem));' +
      'background:var(--bg,#fff);color:var(--fg,#222);border:1px solid var(--rule,#bbb);border-radius:.5rem;' +
      'box-shadow:0 .2rem .8rem rgba(0,0,0,.18);padding:.7rem .9rem;font:inherit;font-size:.92rem;line-height:1.35}' +
      '.pj-panel p{margin:0 0 .5rem}.pj-panel .pj-say{font-weight:600}' +
      '.pj-panel .pj-row{display:flex;flex-wrap:wrap;gap:.4rem}' +
      '.pj-panel button{font:inherit;cursor:pointer;padding:.25rem .7rem;border-radius:.35rem;' +
      'border:1px solid var(--rule,#999);background:transparent;color:inherit}' +
      '.pj-panel button.pj-go{border-color:var(--accent,#a0205a);color:var(--accent,#a0205a)}';
    (document.head || document.documentElement).appendChild(s);
  }
  function panel() {
    style();
    var p = el('div', 'pj-panel');
    p.setAttribute('role', 'status');
    document.body.appendChild(p);
    return p;
  }
  function json(obj, status) {
    return new Response(JSON.stringify(obj), {status: status,
      headers: {'Content-Type': 'application/json'}});
  }

  /* the job followed until it ends -> its last view */
  function follow(id, box) {
    return new Promise(function (resolve) {
      var say = el('p', 'pj-say', 'waiting for a computer');
      var row = el('div', 'pj-row');
      var stop = el('button', null, 'Cancel');
      box.textContent = '';
      box.appendChild(say);
      row.appendChild(stop);
      box.appendChild(row);
      stop.addEventListener('click', function () {
        stop.disabled = true;
        fetch('/__jobs/cancel', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                 body: JSON.stringify({id: id})}).catch(function () {});
      });
      function look() {
        fetch('/__jobs/state?id=' + encodeURIComponent(id), {cache: 'no-store'})
          .then(function (r) { return r.json(); })
          .then(function (j) {
            say.textContent = j.say || j.state;
            if (j.state === 'waiting' || j.state === 'taken') { setTimeout(look, FOLLOW_MS); return; }
            stop.remove();
            setTimeout(function () { box.remove(); }, j.state === 'done' ? 2500 : 8000);
            resolve(j);
          }, function () { setTimeout(look, FOLLOW_MS * 2); });
      }
      look();
    });
  }

  function offer(url, opts, j, o) {
    var can = (j.jobs.send || []).filter(function (p) { return p.can !== false; });
    var box = panel();
    box.appendChild(el('p', null, (j.error || 'This computer cannot do this.') +
      (can.length ? '' : ' No paired computer that can do it is known.')));
    var row = el('div', 'pj-row');
    box.appendChild(row);
    return new Promise(function (resolve) {
      can.forEach(function (p) {
        var b = el('button', 'pj-go', 'Send to ' + p.name + (p.can == null ? ' (not reached yet)' : ''));
        b.addEventListener('click', function () {
          Array.prototype.forEach.call(row.querySelectorAll('button'), function (x) { x.disabled = true; });
          var body = {};
          try { body = JSON.parse((opts && opts.body) || '{}') || {}; } catch (e) {}
          body.send_to = p.id;
          fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify(body)})
            .then(function (r) { return r.json(); })
            .then(function (k) {
              if (!k.ok || !k.job) { box.remove(); resolve(json({ok: false, error: k.error || 'it was refused'}, 409)); return; }
              // a page that follows its own job (the add page's transcription, by its token)
              if (o.defer && typeof k.job !== 'object') { box.remove(); resolve(json(k, 200)); return; }
              var ended = follow(k.job.id, box);
              if (o.defer) { resolve(json(k, 200)); return; }
              ended.then(function (v) {
                if (v.state === 'done') resolve(json(v.result || {ok: true}, 200));
                else resolve(json({ok: false, error: v.reason || v.say || v.state}, 409));
              });
            }, function (e) { box.remove(); resolve(json({ok: false, error: String(e && e.message || e)}, 409)); });
        });
        row.appendChild(b);
      });
      var no = el('button', null, can.length ? 'Not now' : 'Close');
      no.addEventListener('click', function () { box.remove(); resolve(json(j, 409)); });
      row.appendChild(no);
    });
  }

  function lendable(url, opts, o) {
    o = o || {};
    return fetch(url, opts).then(function (r) {
      if (r.status !== 409) return r;
      return r.clone().json().then(function (j) {
        return j && j.jobs ? offer(url, opts, j, o) : r;
      }, function () { return r; });
    });
  }

  window.ParsehJobs = {fetch: lendable, follow: follow};
})();
