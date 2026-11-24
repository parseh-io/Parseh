// SPDX-License-Identifier: GPL-3.0-or-later
/* THE DRAWINGS THIS COMPUTER CANNOT MAKE, MADE ON A PAIRED ONE (a0.7.0 lane J;
   docs/sync.md "Jobs").  A LaTeX block whose theme's compiler this computer
   lacks, and that no paired computer has drawn yet, stands as a frame that
   says so ("This drawing is made with …, which this computer does not have").
   When "send heavy jobs to paired computers" is on, each such frame gets a
   button, and pressing any of them sends ALL of this page's missing drawings
   as one job (lib/jobs.js: "Send to <partner>", then "waiting for a
   computer", "on <partner>", "done").  The drawings come back filed by their
   content, and the page is opened again to show them.  With "send" off
   nothing is added: the frames say what they said before.

   It looks again whenever latexwait.js swaps drawings into the sheet, since
   a page opened before its drawings were tried shows the frames only then. */
(function () {
  "use strict";
  var sheet = document.getElementById("sheet");
  var base = sheet && sheet.getAttribute("data-drawings");
  if (!base || location.protocol === "file:") return;
  var url = base + "/lend";
  var SEL = '.latex-fail[data-latex-kind="compiler"], .latex-inline-fail[data-latex-kind="compiler"]';
  var looked = null, busy = false, bar = null, timer = null;

  function post(body) {
    return fetch(url, {method: "POST", credentials: "same-origin", cache: "no-store",
                       headers: {"Content-Type": "application/json"}, body: JSON.stringify(body || {})});
  }
  function buttons() { return Array.prototype.slice.call(document.querySelectorAll("[data-latex-lend]")); }
  function say(text, bad) {
    buttons().forEach(function (b) {
      var p = b.parentNode && b.parentNode.querySelector(".latex-lend-say");
      if (p) { p.textContent = text; p.style.color = bad ? "var(--danger,#b00)" : ""; }
    });
  }
  function label(n) {
    return n === 1 ? "Have a paired computer draw it" : "Have a paired computer draw these " + n;
  }
  function button(n) {
    var p = document.createElement("p");
    p.className = "latex-lend";
    var b = document.createElement("button");
    b.type = "button";
    b.className = "btn";
    b.setAttribute("data-latex-lend", "");
    b.textContent = label(n);
    b.addEventListener("click", send);
    var s = document.createElement("span");
    s.className = "latex-lend-say";
    s.setAttribute("role", "status");
    s.style.marginInlineStart = ".6em";
    p.appendChild(b);
    p.appendChild(s);
    return p;
  }
  function place(n) {
    var frames = sheet.querySelectorAll(SEL);
    if (!frames.length) return;
    var blocks = 0;
    Array.prototype.forEach.call(frames, function (f) {
      if (!f.classList.contains("latex-fail")) return;
      blocks++;
      if (!f.querySelector("[data-latex-lend]")) {
        var code = f.querySelector(".latex-code");
        f.insertBefore(button(n), code || null);
      }
    });
    // drawings inside a line of text only: one bar above the page holds the button
    if (!blocks && !bar) {
      bar = button(n);
      bar.classList.add("latex-lend-bar");
      sheet.parentNode.insertBefore(bar, sheet);
    }
  }
  function look() {
    timer = null;
    if (busy || !sheet.querySelector(SEL)) return;
    if (!looked) {
      looked = post({look: true}).then(function (r) { return r.json(); })
        .catch(function () { looked = null; return null; });
    }
    looked.then(function (j) { if (j && j.send && j.missing) place(j.missing); });
  }
  function send() {
    if (busy) return;
    busy = true;
    buttons().forEach(function (b) { b.disabled = true; });
    say("");
    var go = window.ParsehJobs ? window.ParsehJobs.fetch : fetch;
    go(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"})
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) { return {ok: r.ok, j: j}; });
      })
      .then(function (res) {
        if (res.ok) {
          say("Drawn. Showing them…");
          setTimeout(function () { location.reload(); }, 600);
          return;
        }
        busy = false;
        buttons().forEach(function (b) { b.disabled = false; });
        // "Not now" answers the door's own refusal, which only says why: nothing to show then
        if (!(res.j && res.j.jobs)) say(res.j.error || "It was refused.", true);
      }, function () {
        busy = false;
        buttons().forEach(function (b) { b.disabled = false; });
        say("Parseh's computer cannot be reached from here.", true);
      });
  }
  if (window.MutationObserver) {
    new MutationObserver(function () { if (!timer) timer = setTimeout(look, 300); })
      .observe(sheet, {childList: true, subtree: true});
  }
  look();
})();
