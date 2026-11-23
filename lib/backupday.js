/* SPDX-License-Identifier: GPL-3.0-or-later
   The day of each shelf's last backup, beside the button that takes it (TO-DO §13.19).

   Every element <… data-backup-day="book|video|studio|decks|settings|everything"> is filled
   with "last backup: 3 days ago" (or "never backed up"), from /settings/api/backups/state, which
   serve.py answers from config/backups.json (lib/backupdays.py).  The day is written by the
   server when it has SENT a backup whole, so a download that failed is not counted.

   Opened off the disk there is no server to ask, and nothing is said.  A page that is shown
   again from the browser's history asks again, so the day is never a stale one. */
(function () {
  'use strict';
  if (location.protocol === 'file:') return;
  function fill() {
    var els = document.querySelectorAll('[data-backup-day]');
    if (!els.length) return;
    fetch('/settings/api/backups/state', {credentials: 'same-origin', cache: 'no-store'})
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.days) return;
        Array.prototype.forEach.call(els, function (el) {
          var d = j.days[el.getAttribute('data-backup-day')];
          if (!d) return;
          el.textContent = d.at ? 'last backup: ' + d.said : 'never backed up';
          el.setAttribute('data-at', d.at ? String(d.at) : '');
          if (d.at) el.title = new Date(d.at * 1000).toLocaleString();
        });
      })
      .catch(function () {});
  }
  window.ParsehBackupDay = {fill: fill};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fill);
  else fill();
  window.addEventListener('pageshow', function (e) { if (e.persisted) fill(); });
  // a backup is a download started from a link: the page stays, so it asks again a little after
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest && e.target.closest('a[href]');
    if (a && /\/(?:__backup|api\/backup|api\/export|api\/backups\/(?:settings|everything))(?:$|\?)/.test(a.getAttribute('href'))) {
      setTimeout(fill, 4000);
      setTimeout(fill, 15000);
    }
  }, true);
})();
