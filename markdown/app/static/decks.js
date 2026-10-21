// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh exercise decks — the pages of the Exercises door (/exercises):
   the decks (decks.html), one deck to browse and manage (deck.html), and
   studying it (study.html).

   A classic script loaded after the studio's app.js, whose helpers it uses:
   $, $$, PAGE, BASE, toast, escAttr, debounce, lang, foldCase, sharedLang,
   setSharedLang, applyTypo, loadTypo, bindExercises, clipWindow and the
   exercise form (openExercisePicker, openExerciseMarkdown).  Both scripts
   share the page's global scope, so everything of this one lives inside the
   function below: no name here can collide with a top-level name of app.js. */
(function () {
"use strict";

if (!["decks", "deck", "study", "cram"].includes(PAGE)) return;

/* the prefix the studio's own pages live under ("/studio" inside Parseh,
   "" when the studio runs alone): a deck exercise links to the document it
   was copied from there */
const STUDIO = document.body.dataset.studio || "";
const RATINGS = ["again", "hard", "good", "easy"];

function readScript(el, fallback) {
  if (!el) return fallback;
  try { return JSON.parse(el.textContent) || fallback; } catch (e) { return fallback; }
}
const LANG_LIST = readScript($("#langs-json"), []);
const LANG_BY_CODE = Object.fromEntries(LANG_LIST.map(l => [l.code, l]));

const cap = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
const plural = (n, one, many) => `${n} ${n === 1 ? one : (many || one + "s")}`;
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/* ---------------- talking to the deck store ---------------- */

/* app.js's api() less one thing it cannot give: the kind of a 409 -- a
   duplicate exercise, a deck that is already here -- which decides what
   the page asks next. */
async function call(path, opts = {}) {
  const init = Object.assign({}, opts);
  if (init.json !== undefined) {
    init.body = JSON.stringify(init.json);
    init.headers = Object.assign({"Content-Type": "application/json"}, init.headers);
    delete init.json;
  }
  /* AN ASK MAY BE GIVEN A PATIENCE, AND ONE THAT HAS A COPY TO FALL BACK ON
     IS GIVEN A SHORT ONE.  `fetch` gives up when the socket does, and a
     socket towards a computer that cannot be reached over a tunnel settles
     NEITHER WAY -- it is not refused, it is swallowed.  On this computer the
     same absence is a refusal in microseconds, which is why every page here
     behaved on the desk and none of them on his phone.  lib/sw.js cannot
     help: it answers GETs only (`r.method !== 'GET'`), so a POST leaves the
     page with no deadline anywhere in the stack.  Where the caller knows
     something else can answer, it says how long this ask is worth. */
  const patience = init.patience;
  delete init.patience;
  /* AND A PAGE THAT KNOWS THE COMPUTER IS AWAY DOES NOT ASK IT TO WRITE
     (the owner's rule of 2026-09-23).  The mark is on <html> before any
     script of this page runs -- lib/mobile.py's AWAY_BOOT reads what the
     page before wrote down -- and a page that opened away stays away while
     it is open (lib/keep.js).  So this is the page acting on what was
     already known instead of finding out again, slowly, into a socket that
     will never answer.  A GET still goes: the worker may hold a copy of it,
     and answering from what is kept is the whole point of keeping. */
  /* `evenAway`: WHAT WAS ANSWERED AWAY GOING HOME IS NOT A PERSON ASKING AN
     OFFLINE PAGE TO WRITE.  The rule above is about a thumb pressing a
     button on a page that already knows the computer is not there.  The
     queue of answers made on a train is the opposite: it is the page
     reconciling by itself, the moment anything opens, and refusing it
     because the page is still marked away would strand a journey's work on
     the phone until every page had been closed and opened again. */
  /* And only a page that KNOWS: an away this page has confirmed, not one it
     assumed from the page before (static/app.js, `pageIsAway`; TO-DO §2.24). */
  const evenAway = init.evenAway;
  delete init.evenAway;
  if (!evenAway && (init.method || "GET").toUpperCase() !== "GET" &&
      (typeof pageIsAway === "function" ? pageIsAway()
       : document.documentElement.getAttribute("data-parseh-away") === "confirmed")) {
    const shut = new Error("Parseh's computer cannot be reached, and this needs it");
    shut.away = true;
    throw shut;
  }
  let r;
  try {
    const go = fetch(BASE + path, init);
    // a named patience where the caller has something else to answer with;
    // otherwise watched beside the one cheap question "is anybody there?",
    // so an honestly slow answer is waited for and an absent one is not
    // (static/app.js, `watched`)
    r = patience > 0
      ? await Promise.race([go, new Promise((_, no) => setTimeout(
          () => no(new Error("nobody answered within the deadline")), patience))])
      : typeof watched === "function" ? await watched(go) : await go;
  }
  catch (e) {
    /* WHY an ask failed decides what the page says next, and a phone in a
       tunnel is not a broken Parseh.  The pages that can go on without the
       computer -- cramming a deck that is kept here -- look at this flag to
       tell "nobody answered" from "the deck said no". */
    const gone = new Error("the server does not answer — is Parseh still running?");
    gone.away = true;
    throw gone;
  }
  let data = {};
  try { data = await r.json(); } catch (e) { /* not JSON: an error page */ }
  if (!r.ok || data.ok === false) {
    const err = new Error(data.error || (r.status + " " + r.statusText));
    err.status = r.status;
    err.conflict = data.conflict || "";
    err.detail = data.detail || null;       // what a "linked" conflict names: the other sides
    // the worker's own refusal for a door it has no copy of: 503, and it
    // says so in the body (lib/sw.js, refused)
    err.away = data.offline === true || r.status === 503;
    throw err;
  }
  return data;
}

/* IS THE COMPUTER THERE?  The page's own mark answers it: `data-parseh-away`
   on <html>, which the head of every deck page sets before any script of it
   runs when the page before found the computer away (AWAY_BOOT, in
   deckroutes' APP_HEAD -- never on a refresh), and which lib/keep.js
   confirms, or takes off, once the page's one question has an answer
   (lib/activity.js).  This used to read the memory in localStorage again
   for itself, on terms of its own, and to believe `navigator.onLine ===
   false` on its own: a second opinion beside the one question, which
   disagreed with it whenever another tab wrote the memory -- and "no
   network" is a reason to ask, not an answer (the owner, TO-DO §2.24).

   This is what lets a deck page decide whether to ask the computer AT ALL.
   Cramming a kept deck must not wait out a door nobody is going to answer. */
function computerAway() {
  return document.documentElement.hasAttribute("data-parseh-away");
}

/* NEVER A SPINNER THAT NEVER STOPS (the owner's 8, 2026-09-23).  When a page
   of exercises cannot show one, it says in a line what is wrong, in the
   lines under it what would mend it, and gives the ways on at the foot.

   It borrows the panel the end of a session is drawn in (.dk-done), because
   this IS an end of a session -- one that ends before it began -- and
   because the mobile layout already gives that panel's buttons their 52px
   (static/mobile.css).  Its box stands beside the stage in the page
   (cram.html, study.html) rather than inside it: an exercise's sheet is no
   place for a panel, and the stage has to be able to come back. */
function sayInstead(stage, box, head, lines, ways) {
  const parts = [el("h2", "", head)];
  (lines || []).forEach(line => parts.push(el("p", "", line)));
  const row = el("div", "dk-done-actions");
  (ways || []).forEach(([label, href, primary]) => {
    const a = el("a", "btn" + (primary ? " primary" : ""), label);
    a.href = href;
    row.appendChild(a);
  });
  if (row.firstChild) parts.push(row);
  box.replaceChildren(...parts);
  box.hidden = false;
  if (stage) stage.hidden = true;
}

const seg = s => encodeURIComponent(String(s || ""));
const deckApi = d => `/api/decks/${seg(d.folder)}/${seg(d.slug)}`;
const deckPage = d => `${BASE}/deck/${seg(d.folder)}/${seg(d.slug)}/`;
const studyPage = d => deckPage(d) + "study";
const exportUrl = (d, scheduling) => `${BASE}${deckApi(d)}/export?scheduling=${scheduling ? 1 : 0}`;
const toStudy = s => s ? (s.new || 0) + (s.learning || 0) + (s.review || 0) : 0;

/* ---------------- time, as the scheduler labels it ---------------- */

// srs.label's twin: the rating bar's labels come from the server, and the
// "next exercise in …" lines written here must read the same way
const DAY = 86400, MONTH = DAY * 365 / 12, YEAR = DAY * 365;
const halfUp = x => Math.floor(x + 0.5);
function tenths(x) {
  const n = Math.floor(x * 10 + 0.5) / 10;
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}
function spanLabel(seconds) {
  const s = Math.max(0, seconds);
  if (s < 60) return "<1m";
  if (s < 3600) { const n = halfUp(s / 60); return n >= 60 ? "1h" : n + "m"; }
  if (s < DAY) { const n = halfUp(s / 3600); return n >= 24 ? "1d" : n + "h"; }
  if (s < MONTH) return halfUp(s / DAY) + "d";
  if (s < YEAR) {
    const m = Math.floor(s / MONTH * 10 + 0.5) / 10;
    return m >= 12 ? "1y" : tenths(m) + "mo";
  }
  return tenths(s / YEAR) + "y";
}

/* The learner's day starts at the deck's rollover hour (04:00, as in Anki);
   the server is this machine, so the browser's clock is its clock. */
const rolloverOf = d => {
  const h = ((d && d.settings) || {}).rollover_hour;
  return Number.isFinite(h) ? h : 4;
};
/* Wall-clock hours, as srs.day_number takes them: shifting by elapsed time
   instead puts the morning the clocks go forward on the day before. */
function dayNumber(date, rollover) {
  return Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(),
                             date.getHours() - rollover, date.getMinutes()) / 864e5);
}
/* When a due comes, in ms.  The scheduler writes a review's due as the start
   of its day: the rollover hour on the clock of the moment it was answered,
   with that moment's offset.  Its own date is the day meant.  Read as an
   instant, a due written in summer time would begin at 03:00 in winter,
   before the rollover, so it would fall on the day before.  srs.due_day
   reads it the same way.  Any other due is an instant. */
const DAY_START_RE = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):00:00(?:\.0+)?(?:Z|[+-]\d\d:\d\d)?$/;
function dueTime(iso, rollover) {
  const m = DAY_START_RE.exec(iso || "");
  if (m && +m[4] === rollover) return new Date(+m[1], m[2] - 1, +m[3], rollover).getTime();
  return Date.parse(iso || "");
}
/* The day a due counts on: a day-start due's own date, read straight from
   its text (never through a local instant, which a clock change moves). */
function dueDay(iso, rollover) {
  const m = DAY_START_RE.exec(iso || "");
  if (m && +m[4] === rollover) return Date.UTC(+m[1], m[2] - 1, +m[3]) / 864e5;
  const t = Date.parse(iso || "");
  return Number.isFinite(t) ? dayNumber(new Date(t), rollover) : NaN;
}
/* "now", "in 8m", "tomorrow", "in 5d" */
function whenDue(iso, rollover = 4) {
  const t = dueTime(iso, rollover);
  if (!Number.isFinite(t)) return "";
  const now = new Date(), secs = (t - now.getTime()) / 1000;
  if (secs <= 0) return "now";
  const days = dueDay(iso, rollover) - dayNumber(now, rollover);
  if (days <= 0 || secs < 3600) return "in " + spanLabel(secs);
  if (days === 1) return "tomorrow";
  return "in " + spanLabel(days * DAY);
}
function nextDueText(iso, rollover) {
  if (!iso) return "no exercises scheduled";
  const w = whenDue(iso, rollover);
  return w === "now" ? "next exercise due now" : "next exercise " + w;
}

/* new · learning · review, coloured as Anki colours its three queues;
   `current` underlines the queue the exercise on screen comes from */
function studyCounts(study, current) {
  const s = study || {};
  const box = el("span", "dk-study");
  const parts = [["new", "dk-new", "new"], ["learning", "dk-learn", "learning"],
                 ["review", "dk-rev", "to review"]];
  box.appendChild(el("span", "dk-sr",
    parts.map(([k, , words]) => `${s[k] || 0} ${words}`).join(", ")));
  parts.forEach(([k, cls, words], i) => {
    if (i) {
      const sep = el("span", "dk-sep", "·");
      sep.setAttribute("aria-hidden", "true");
      box.appendChild(sep);
    }
    const n = el("span", `dk-n ${cls}${s[k] ? "" : " dk-zero"}${current === k ? " dk-current" : ""}`,
                 String(s[k] || 0));
    n.title = words;
    n.setAttribute("aria-hidden", "true");
    box.appendChild(n);
  });
  return box;
}

/* ---------------- dialogs ---------------- */

/* A modal in the studio's markup (#modal-root > .modal-overlay > .modal).
   It resolves to what the chosen button gives: the result of its `run()`
   (which may be async; when it throws, the message is toasted and the
   dialog stays open), else its `value` (true by default); null for Cancel,
   Escape or a click beside the box.  `stack` opens it over what is already
   open -- the exercise form asking "add it again?" -- instead of replacing
   it. */
function dialog({title, hint = "", body = null, buttons, cls = "", stack = false}) {
  const root = $("#modal-root");
  if (!stack) root.innerHTML = "";
  const ov = el("div", "modal-overlay");
  const box = el("div", "modal dk-modal" + (cls ? " " + cls : ""));
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-label", title);
  box.appendChild(el("h3", "", title));
  if (hint) box.appendChild(el("p", "", hint));
  if (body) box.appendChild(body);
  const row = el("div", "row");
  box.appendChild(row);
  ov.appendChild(box);
  return new Promise(resolve => {
    let busy = false, settled = false;
    const close = value => {
      if (settled) return;
      settled = true;
      ov.remove();
      resolve(value);
    };
    const made = buttons.map(spec => {
      const b = el("button", "btn" + (spec.primary ? " primary" : "") + (spec.danger ? " danger" : ""),
                   spec.label);
      b.type = "button";
      if (spec.cancel) b.dataset.x = "cancel";
      b.addEventListener("click", async () => {
        if (busy) return;                     // one request per click, however fast
        if (spec.cancel) return close(null);
        const fallback = spec.value === undefined ? true : spec.value;
        if (!spec.run) return close(fallback);
        busy = true;
        made.forEach(x => { x.disabled = true; });
        try {
          const out = await spec.run();
          close(out === undefined ? fallback : out);
        } catch (e) {
          toast(e.message, true);
          busy = false;
          made.forEach(x => { x.disabled = false; });
        }
      });
      row.appendChild(b);
      return b;
    });
    ov.addEventListener("click", e => { if (e.target === ov && !busy) close(null); });
    // Enter in a one-line field is the main button
    box.addEventListener("keydown", e => {
      if (e.key !== "Enter" || !e.target.matches("input:not([type=checkbox]):not([type=radio])")) return;
      e.preventDefault();
      const main = made.find((b, i) => buttons[i].primary);
      if (main) main.click();
    });
    root.appendChild(ov);
    // typing starts in the first field; a question with a dangerous answer
    // starts on Cancel, the first button
    const first = $("input, select, textarea", box)
      || made.find((b, i) => buttons[i].primary) || made[0];
    if (first) {
      first.focus();
      if (first.matches("input[type=text]")) first.select();
    }
  });
}

const CANCEL = {label: "Cancel", cancel: true};
function confirmDialog({title, hint, ok = "OK", danger = false, stack = false}) {
  return dialog({title, hint, stack,
                 buttons: [CANCEL, {label: ok, primary: !danger, danger, value: true}]})
    .then(v => v === true);
}

/* A LINKED CARD IS ONE SIDE OF A PAIR (a both-repeat flashcard, added to a
   deck as two cards).  Changing or deleting one asks what becomes of the
   other -- the server refuses to do either without an answer (409 "linked",
   decks.py) -- and this is the question, asked the same way whichever
   button, page or selection led here.  Each answer is a button that DOES
   the thing (`act("both" | "alone")`, an ask of the server), so the dialog
   is the confirmation and a refusal keeps it open; it resolves to
   {choice, data}, or null for Cancel.  `others` are the rows that name the
   other sides: the deck's own summaries, or what the refusal carried
   ({excerpt, side}). */
function sideOf(row) { return row.direction === "reverse" || row.side === "back" ? "back" : "front"; }
function askLinked({title, hint, others, both, alone, act, danger = false, stack = false}) {
  const body = el("ul", "dk-others");
  for (const row of others.slice(0, 3)) {
    const li = el("li");
    // a card's text may run the other way: <bdi> keeps it from taking the quotes with it
    li.append("“", el("bdi", "dk-other-text", row.excerpt || row.label || "(no text)"), "”",
              el("small", "", `shows the ${sideOf(row)} first`));
    body.appendChild(li);
  }
  const answer = choice => async () => ({choice, data: await act(choice)});
  return dialog({title, hint, body, stack, cls: "dk-ask", buttons: [
    CANCEL,
    {label: alone, run: answer("alone")},
    {label: both, primary: !danger, danger, run: answer("both")}]});
}
const LINKED_HINT = "The two are linked: they are the front and the back of one card. " +
  "Their scheduling is never shared.";
const mateRows = (list, it) => (it.mates || []).map(id => list.find(x => x.id === id)).filter(Boolean);

/* Every edit of a card goes through here (Browse, and the study page): saved
   as it is, or -- for a card with another side -- after the question above
   has been answered.  A Cancel throws, as "Add again" does, so the form stays
   open and the card stays as it was. */
async function saveEdited(deck, item, markdown) {
  const put = linked => call(`${deckApi(deck)}/items/${item.id}`,
                             {method: "PUT", json: linked ? {markdown, linked} : {markdown}});
  try {
    return await put();
  } catch (e) {
    if (e.conflict !== "linked") throw e;
    const done = await askLinked({
      stack: true, title: "This card has another side",
      hint: LINKED_HINT + " Is this change for both cards?",
      others: (e.detail && e.detail.mates) || [],
      both: "Change both cards", alone: "Change only this one (unlink them)", act: put});
    if (!done) throw new Error("Not saved: the card is left as it was");
    return done.data;
  }
}

function field(label, input, help) {
  const lab = el("label", "modal-field");
  lab.append(el("span", "", label), input);
  if (help) lab.appendChild(el("small", "", help));
  return lab;
}
function textInput(value, attrs = {}) {
  const i = el("input");
  i.type = "text";
  i.value = value || "";
  i.spellcheck = false;
  i.autocomplete = "off";
  for (const [k, v] of Object.entries(attrs)) i.setAttribute(k, v);
  return i;
}

/* Escape closes what is on top: a dialog (through its Cancel, so whatever
   it was waiting for hears the answer), else an open menu.  The exercise
   form closes itself when the key is pressed inside it. */
document.addEventListener("keydown", e => {
  if (e.key !== "Escape" || e.defaultPrevented) return;
  const overlays = $$("#modal-root > .modal-overlay");
  const top = overlays[overlays.length - 1];
  if (top) {
    e.preventDefault();
    const cancel = $('[data-x="cancel"]', top);
    if (!cancel) top.remove();
    else if (!cancel.disabled) cancel.click();
    return;
  }
  const menu = $("details.dropdown[open]");
  if (menu) { e.preventDefault(); menu.open = false; }
});
// a menu closes when something is chosen in it or the click lands elsewhere
document.addEventListener("click", e => {
  $$("details.dropdown[open]").forEach(d => {
    if (!d.contains(e.target) || e.target.closest(".menu a, .menu button")) d.open = false;
  });
});

/* A link standing for a button that has nothing to do: dimmed, out of the
   tab order, and inert to a click that reaches it anyway. */
function setLinkEnabled(a, on, title) {
  a.classList.toggle("dk-off", !on);
  if (on) { a.removeAttribute("aria-disabled"); a.removeAttribute("tabindex"); }
  else { a.setAttribute("aria-disabled", "true"); a.tabIndex = -1; }
  if (title !== undefined) a.title = title;
}
document.addEventListener("click", e => {
  if (e.target.closest && e.target.closest("a.dk-off")) e.preventDefault();
}, true);

/* What the server is still working on (lib/activity.py's list, as
   /__activity hands it to every page) -> its entries, or none.  The
   studio run on its own has no such address, and that is none too. */
async function stillRunning() {
  try {
    const r = await fetch("/__activity", {cache: "no-store"});
    if (r.ok) return (await r.json()).running || [];
  } catch (e) { /* no list here */ }
  return [];
}

function bindStop() {
  const btn = $("#btn-stop");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    // WHAT IS STILL RUNNING IS NAMED FIRST, as the stop button on every
    // other page names it (lib/parseh.js's stopServer, the studio's own):
    // stopping the server cuts it off, and a deck being restored or a book
    // being built is exactly what nobody should lose to a click on the
    // wrong button.  One line a task, the first five of them.
    const running = await stillRunning();
    const n = running.length;
    let list = null;
    if (n) {
      list = el("ul", "dk-running");
      running.slice(0, 5).forEach(e => list.appendChild(el("li", "", e.label)));
      if (n > 5) list.appendChild(el("li", "", `\u2026 and ${n - 5} more`));
    }
    const yes = await dialog({
      title: "Stop the Parseh server?",
      hint: n ? `${n === 1 ? "1 task is" : n + " tasks are"} still running, and stopping the `
                + `server now cuts ${n === 1 ? "it" : "them"} off. Every Parseh page stops `
                + "answering until it is started again."
              : "Every Parseh page stops answering until it is started again.",
      body: list,
      buttons: [CANCEL, {label: n ? "Stop server anyway" : "Stop server", danger: true, value: true}],
    }).then(v => v === true);
    if (!yes) return;
    try { await fetch(BASE + "/api/shutdown", {method: "POST"}); } catch (e) { /* on its way out */ }
    $("#shutdown-overlay").hidden = false;
  });
}

/* ---------------- the interface: browser or mobile ----------------
   The toolbox's one switch (docs/mobile.md): `parseh_mode` in localStorage,
   mirrored in a cookie of the same name, and put on <html data-mode> --
   which the page's head has already done (deckroutes.MODE_SCRIPT), so the
   layout drawn first is the right one.  Every page here carries both
   layouts and static/mobile.css shows one of them: the mobile one reads and
   studies, and has nothing that edits, builds, imports or stops anything.
   These pages do not load lib/parseh.js, so the switch in the mobile bar is
   kept here the way parseh.js keeps it on every other page: stored,
   mirrored, drawn, and followed when another tab changes it. */
const MODE_KEY = "parseh_mode";
function modeNow() {
  let m = null;
  try { m = localStorage.getItem(MODE_KEY); } catch (e) { /* blocked */ }
  if (m !== "browser" && m !== "mobile") {
    const c = /(?:^|;\s*)parseh_mode=(browser|mobile)(?:;|$)/.exec(document.cookie || "");
    m = c ? c[1] : "browser";
  }
  return m;
}
const isMobile = () => document.documentElement.getAttribute("data-mode") === "mobile";
function modeApply() {
  const m = modeNow();
  document.documentElement.setAttribute("data-mode", m);
  // the server's copy follows what this page found, as parseh.js has it
  if (!new RegExp(`(?:^|;\\s*)${MODE_KEY}=${m}(?:;|$)`).test(document.cookie || ""))
    document.cookie = `${MODE_KEY}=${m}; Path=/; SameSite=Lax; Max-Age=31536000`;
  $$("[data-parseh-mode]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.parsehMode === m)));
  if (m === "mobile") appRegister();
}
/* The mobile interface installed as an app (docs/mobile.md): the service
   worker a browser asks for before it installs a site (lib/sw.js), which
   lib/parseh.js registers on the toolbox's own pages in the mobile mode --
   these load it not, so it is registered here the same way.  Refused where
   the phone does not trust the certificate; the install page says so. */
function appRegister() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  navigator.serviceWorker.register("/sw.js").catch(() => { /* see above */ });
}
function modeSet(m) {
  if (m !== "browser" && m !== "mobile") return;
  try { localStorage.setItem(MODE_KEY, m); } catch (e) { /* the cookie still says it */ }
  document.cookie = `${MODE_KEY}=${m}; Path=/; SameSite=Lax; Max-Age=31536000`;
  modeApply();
}
/* THE THEME IS NOT HERE.  The ◐ of the bars, the colours of the sheet and what
   the computer says of them are app.js's (paintTheme, bindStudioLook): one
   function for every page of the studio, the decks among them.  This file
   kept a cycle of its own, which wrote the toolbox's key and repainted what
   it thought was its page. */
function bindMode() {
  modeApply();
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("[data-parseh-mode]");
    if (b) modeSet(b.dataset.parsehMode);
  });
  addEventListener("storage", e => {
    if (e.key === MODE_KEY || e.key === null) modeApply();
  });
  // a page brought back from the back-forward cache ran none of its script
  addEventListener("pageshow", e => { if (e.persisted) modeApply(); });
  bindBarFollow();
  // what the gear's Interface group asks (lib/pagesettings.js std.interface),
  // which does the same as the switch it replaces on a phone's bar: stored,
  // mirrored, drawn, and the worker registered where the mobile mode is
  window.ParsehStudioMode = {get: modeNow, set: modeSet, isMobile};
}

/* The mobile bar goes on the way down and comes back on the way up
   (static/mobile.css).  app.js puts the bars away on a phone's width
   (bindBarHide, under 560px, in both layouts); a phone held sideways is
   wider than that, and has the least height of all, so in the mobile
   layout this does the same from 560px up. */
function bindBarFollow() {
  const mq = window.matchMedia ? window.matchMedia("(max-width: 560px)") : null;
  let lastY = Math.max(0, scrollY), ticking = false, off = false;
  const set = v => {
    if (v === off) return;
    off = v;
    document.body.classList.toggle("barhidden", v);
  };
  const read = () => {
    ticking = false;
    const y = Math.max(0, scrollY), d = y - lastY;
    if (Math.abs(d) < 4) return;            // a finger resting is not a move
    lastY = y;
    if (mq && mq.matches) { off = document.body.classList.contains("barhidden"); return; }
    set(isMobile() && y > 56 && d > 0);
  };
  addEventListener("scroll", () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(read);
  }, {passive: true});
}

/* ---------------- the exercise form, pointed at a deck ---------------- */

/* The deck renders the preview (the deck's language, its pictures, the
   exercise's own footnotes when it is an existing one). */
function formPreview(deck, itemId) {
  return async markdown => {
    const json = itemId ? {markdown, item: itemId} : {markdown};
    return (await call(deckApi(deck) + "/preview", {method: "POST", json})).html;
  };
}

/* A picture chosen in the form goes straight into the deck's images/, a
   recording into its audio/.  The field gets the path the deck stored it
   under -- the same bytes reuse a name, and a different file with that name
   gets another -- and the form the address it is served at (its ▶ plays a
   recording from there before the preview has drawn it). */
function deckUpload(deck, kind = "images") {
  return async file => {
    const fallback = kind === "audio" ? "recording" : "picture";
    // on the activity list when it is big enough to take a while (app.js)
    const data = await working(file.size > BIG_UPLOAD && `Uploading ${file.name || fallback}`,
      act => call(act.url(`${deckApi(deck)}/${kind}?name=${encodeURIComponent(file.name || fallback)}`),
        {method: "POST", body: file, headers: {"Content-Type": file.type || "application/octet-stream"}}));
    return {path: data.path || `${kind}/${data.name}`, url: data.url};
  };
}
const uploads = deck => ({uploadImage: deckUpload(deck), uploadAudio: deckUpload(deck, "audio"), pictureHome: "this deck"});

/* An exercise is saved even when a picture or a recording it names is not
   in the deck.  The answer says so, and the toast passes it on. */
function savedToast(what, data) {
  const raw = (data && (data.warnings || (data.item && data.item.warnings))) || [];
  const warnings = Array.isArray(raw) ? raw.filter(w => typeof w === "string" && w) : [];
  if (!warnings.length) return toast(what);
  toast(`${what}, but ${warnings.join("; ")}`, true);
}

/* WHICH SIDE A FLASHCARD SHOWS FIRST, in a deck's edit form.  A card that is
   one of no pair may show its front, its back, or either at random each time
   (Both (random)); "Both (repeat)" is a way to ADD a card -- it makes two --
   so it is not offered for one that is already here, unless a hand-written
   card already says it.  The side of a card that is one of a pair is what
   makes the pair: its choice is fixed (fixSide, once the form is open). */
const SIDES = ["forward", "reverse", "both-random", "both-repeat"];
function editDirections(item) {
  if ((item.mates || []).length) return [item.direction || "forward"];
  return item.direction === "both-repeat" ? SIDES : SIDES.slice(0, 3);
}
function fixSide() {
  for (const select of $$("#modal-root .ex-form-modal select")) {
    const values = [...select.options].map(o => o.value);
    if (!values.length || !values.every(v => SIDES.includes(v))) continue;
    select.disabled = true;
    select.closest("label").appendChild(
      el("small", "dk-fixed-side", "This card is one side of a pair: its side is fixed."));
  }
}

/* Open an exercise in the form; a shape the form cannot show (an exercise
   saved with errors, say) opens as its markdown instead, so it can still be
   put right from here. */
function editExercise(deck, item, onSave) {
  const opts = Object.assign({preview: formPreview(deck, item.id), onSave, saveLabel: "Save exercise",
                              directions: editDirections(item)}, uploads(deck));
  if (openExerciseMarkdown(item.markdown, opts)) {
    if ((item.mates || []).length) fixSide();
    return;
  }
  const ta = el("textarea", "dk-raw");
  ta.value = item.markdown;
  ta.spellcheck = false;
  dialog({
    title: "Edit the exercise as markdown", cls: "dk-raw-modal", body: ta,
    hint: "The form cannot show this exercise, so here is its source: one :::exercise block, " +
          "written as in a studio document.",
    buttons: [CANCEL, {label: "Save exercise", primary: true, run: () => onSave(ta.value)}],
  });
}

/* ================================================================ decks */

function initDecks() {
  const cardsEl = $("#deck-cards");
  const empty = $("#decks-empty"), emptyLang = $("#decks-empty-lang");
  const chipRow = $(".parseh-langs");
  let decks = [];

  /* The language chip row: rendered by the server for the first paint,
     rebuilt from the decks after every change (a deck created, deleted or
     imported changes the counts).  A click records the toolbox's shared
     preference, as on every index page. */
  function refreshChips() {
    if (!chipRow) return;
    const counts = {};
    for (const d of decks) counts[d.lang] = (counts[d.lang] || 0) + 1;
    chipRow.replaceChildren();
    const all = el("button", "chip");
    all.type = "button";
    all.dataset.pick = "all";
    all.append("all", el("span", "n", String(decks.length)));
    chipRow.appendChild(all);
    for (const l of LANG_LIST) {
      if (!counts[l.code]) continue;
      const c = el("button", "chip");
      c.type = "button";
      c.dataset.pick = c.dataset.lang = c.lang = l.code;
      c.title = l.name;
      c.append(el("span", "native", l.native), el("span", "n", String(counts[l.code])));
      chipRow.appendChild(c);
    }
  }

  function applyLangFilter() {
    let pick = sharedLang();
    // a stored preference no chip offers would hide every card and light
    // no chip: read it as 'all' and put the store right, as the studio does
    if (pick !== "all" && chipRow && !$$(".chip", chipRow).some(c => c.dataset.pick === pick)) {
      pick = "all";
      setSharedLang("all");
    }
    if (chipRow) $$(".chip", chipRow).forEach(c => c.classList.toggle("on", c.dataset.pick === pick));
    let shown = 0;
    $$(".dk-card", cardsEl).forEach(c => {
      const on = pick === "all" || c.dataset.lang === pick;
      c.hidden = !on;
      if (on) shown++;
    });
    empty.hidden = decks.length > 0;
    $(".lang-name", emptyLang).textContent = (LANG_BY_CODE[pick] || {}).name || pick;
    emptyLang.hidden = !(decks.length > 0 && shown === 0);
  }

  if (chipRow) chipRow.addEventListener("click", e => {
    const c = e.target.closest(".chip");
    if (!c || !chipRow.contains(c)) return;
    setSharedLang(c.dataset.pick);
    applyLangFilter();
  });

  function deckCard(d) {
    const l = LANG_BY_CODE[d.lang] || {code: d.lang, name: d.language || d.lang, native: d.lang, dir: "ltr"};
    const total = (d.counts || {}).total || 0, due = toStudy(d.study);
    const card = el("article", "card dk-card");
    card.dataset.lang = d.lang;
    card.dataset.path = d.path;
    card.innerHTML = `
      <h3><a class="dk-card-title" href="${escAttr(deckPage(d))}"></a></h3>
      <div class="badges">
        <span class="badge lang" lang="${escAttr(l.code)}" dir="${escAttr(l.dir)}"
              title="${escAttr(l.name)}"></span>
        <span class="badge dk-total"></span>
      </div>
      <div class="dk-card-study"></div>
      <div class="dk-card-actions">
        <a class="btn primary small" data-x="study" href="${escAttr(studyPage(d))}">Study</a>
        <a class="btn small" data-x="browse" href="${escAttr(deckPage(d))}"><span
          data-layout="browser">Browse</span><span data-layout="mobile">Open</span></a>
        <details class="dropdown">
          <summary class="btn small" title="Export or delete" aria-label="More for this deck">⋯</summary>
          <div class="menu">
            <a href="${escAttr(exportUrl(d, true))}">Export with scheduling</a>
            <a href="${escAttr(exportUrl(d, false))}">Export without scheduling</a>
            <button type="button" class="danger" data-x="delete">Delete deck…</button>
          </div>
        </details>
      </div>`;
    $(".dk-card-title", card).textContent = d.name;
    $(".badge.lang", card).textContent = l.native;
    $(".dk-total", card).textContent = plural(total, "exercise");
    const study = $(".dk-card-study", card);
    if (!total) {
      // said in each layout's terms: a phone has no page to add from
      const here = el("span", "", "Empty: add exercises from its page, or from a studio document.");
      const phone = el("span", "", "Empty: exercises are added in the browser interface.");
      here.dataset.layout = "browser";
      phone.dataset.layout = "mobile";
      study.append(here, phone);
    } else {
      // WHAT THE CLOCK MAKES WRONG IS NOT SHOWN WHILE THE COMPUTER IS AWAY
      // (the owner's 1, 2026-09-23).  What is due here was worked out on the
      // computer the last time this page was read from it; a day later it is
      // a number nobody should act on, while the deck beside it is still
      // perfectly true.  data-clock-count marks it, and lib/keep.js takes it
      // off the page for as long as the computer cannot be reached.
      const label = el("span", "dk-label", "To study"), counts = studyCounts(d.study);
      label.dataset.clockCount = counts.dataset.clockCount = "";
      study.append(label, counts);
      if (!due) {
        const next = el("span", "dk-next", nextDueText(d.next_due, rolloverOf(d)));
        next.dataset.clockCount = "";
        study.appendChild(next);
      }
    }
    setLinkEnabled($('[data-x="study"]', card), due > 0,
                   due ? `Study ${plural(due, "exercise")} now` : "Nothing to study now");
    $('[data-x="delete"]', card).addEventListener("click", async () => {
      const gone = await dialog({
        title: `Delete “${d.name}”?`,
        hint: `Its ${plural(total, "exercise")} and their scheduling are moved to exercises/.trash/ ` +
              "in the Parseh folder, not erased: move the folder back to restore the deck.",
        buttons: [CANCEL, {label: "Delete deck", danger: true,
                           run: () => call(deckApi(d), {method: "DELETE"})}],
      });
      if (!gone) return;
      toast(`“${d.name}” moved to exercises/.trash`);
      load();
    });
    return card;
  }

  let loadSeq = 0;
  async function load() {
    const seq = ++loadSeq;
    let data;
    try { data = await call("/api/decks"); }
    catch (e) { toast("Could not read the decks: " + e.message, true); return; }
    if (seq !== loadSeq) return;            // a newer reload is on its way
    decks = data.decks || [];
    cardsEl.replaceChildren(...decks.map(deckCard));
    refreshChips();
    applyLangFilter();
  }

  async function newDeck() {
    const body = el("div", "modal-fields");
    const name = textInput("", {placeholder: "e.g. Everyday verbs", maxlength: "200"});
    const sel = el("select");
    for (const l of LANG_LIST) {
      const o = el("option", "", `${l.name} — ${l.native}`);
      o.value = l.code;
      sel.appendChild(o);
    }
    const pick = sharedLang();
    sel.value = LANG_BY_CODE[pick] ? pick : ((LANG_LIST[0] || {}).code || "");
    body.append(field("Name", name),
                field("Language", sel, "Every exercise of a deck is in its language."));
    const made = await dialog({
      title: "New exercise deck", body,
      buttons: [CANCEL, {label: "Create deck", primary: true, run: async () => {
        const n = name.value.trim();
        if (!n) { name.focus(); throw new Error("Give the deck a name"); }
        return (await call("/api/decks", {method: "POST", json: {name: n, lang: sel.value}})).deck;
      }}],
    });
    // an empty deck is filled on its own page
    if (made && made.folder) location.href = deckPage(made);
  }

  /* Import: the file goes up as it is; the scheduling it carries is kept
     unless unticked.  A deck already here (the same deck id) is a 409, and
     the learner decides between replacing it and keeping both. */
  async function importDeck(file) {
    const body = el("div", "modal-fields");
    const lab = el("label", "check dk-check");
    const keep = el("input");
    keep.type = "checkbox";
    keep.checked = true;
    lab.append(keep, " Keep the scheduling saved in the file");
    body.append(lab, el("small", "dk-help", "Unticked, every exercise starts again as new."));
    // each press is on the activity list while the file goes up (app.js)
    const send = mode => working(`Importing the deck ${file.name}`, act => call(
      act.url(`/api/import?scheduling=${keep.checked ? 1 : 0}&mode=${mode}`
              + `&name=${encodeURIComponent(file.name)}`),
      {method: "POST", body: file, headers: {"Content-Type": "application/zip"}}));
    let out = await dialog({
      title: `Import “${file.name}”`,
      hint: "A deck exported from Parseh: its exercises, their pictures and recordings and, if it was " +
            "saved with it, the scheduling.",
      body,
      buttons: [CANCEL, {label: "Import", primary: true, run: async () => {
        try { return await send("new"); }
        catch (e) { if (e.conflict === "exists") return {conflict: e.message}; throw e; }
      }}],
    });
    if (!out) return;
    if (out.conflict) {
      out = await dialog({
        title: "This deck is already here",
        hint: cap(out.conflict) + ". Replace it moves the deck that is here to exercises/.trash/ " +
              "and puts the imported one in its place; a copy keeps both.",
        buttons: [CANCEL,
                  {label: "Import as a copy", run: () => send("copy")},
                  {label: "Replace it", danger: true, run: () => send("replace")}],
      });
      if (!out) return;
    }
    const skipped = (out.skipped || []).length, deck = out.deck || {};
    toast(`Imported “${deck.name}”: ${plural(out.imported || 0, "exercise")}` +
          (skipped ? `, ${skipped} skipped (not a valid exercise)` : "") +
          (out.scheduling ? ", with its scheduling" : ", all new"), skipped > 0);
    load();
  }

  $("#btn-new-deck").addEventListener("click", () => newDeck().catch(e => toast(e.message, true)));
  $$('[data-x="new-deck"]', empty).forEach(b =>
    b.addEventListener("click", () => newDeck().catch(e => toast(e.message, true))));
  const fileInput = $("#file-import");
  $("#btn-import").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    fileInput.value = "";            // the same file can be picked again
    if (file) importDeck(file).catch(e => toast(e.message, true));
  });

  /* THE WHOLE SHELF PUT BACK.  Not importDeck: that one adds a deck
     somebody sent you, under a new id where the id is taken and with the
     scheduling left behind if you say so.  This puts back what the Backup
     button wrote -- the ids, the settings, the pictures nothing names any
     more and the months of answers -- and a deck already here is KEPT
     until replacing it is asked for, which is the studio's own rule for a
     library and is right for the same reason: the backup is usually the
     older of the two. */
  async function restoreShelf(file) {
    // each sending of the backup is on the activity list while it runs
    // (app.js), and what is sent is THE FILE ITSELF, streamed from the disk
    // and sent again if replacing is asked for: read into the page first, a
    // big backup held the page -- and the pill that says it has begun --
    // still for seconds
    const post = replace => working(`Restoring the decks from ${file.name}`, act => call(
      act.url("/api/restore?name=" + encodeURIComponent(file.name) + (replace ? "&replace=1" : "")),
      {method: "POST", body: file, headers: {"Content-Type": "application/zip"}}));
    let out = await post(false);
    if ((out.kept || []).length) {
      const names = out.kept.slice(0, 4).join(", ")
        + (out.kept.length > 4 ? ", …" : "");
      const go = await dialog({
        title: `${plural(out.kept.length, "deck")} already here`,
        hint: `${names} — left exactly as they are. Replacing them puts the `
            + `backup's copy in their place, and anything written or studied `
            + `since the backup was made is lost. The backup is sent again.`,
        buttons: [{label: "Keep mine", cancel: true},
                  {label: "Replace them", danger: true, run: () => post(true)}],
      });
      if (go && go !== true) out = go;
    }
    const n = (out.restored || []).length, kept = (out.kept || []).length;
    const notes = out.warnings || [];
    // a warning is not a failure: a backup that put ten decks back and
    // skipped one stray file has not failed, and colouring it red would say
    // it had.  Red is for nothing restored at all.
    toast(`${plural(n, "deck")} restored`
          + (kept ? `, ${kept} left as ${kept === 1 ? "it is" : "they are"}` : "")
          + (notes.length ? `; ${notes[0]}` : ""), n === 0);
    if (notes.length > 1) console.warn("[decks] restore:", notes);
    load();
  }

  const restoreInput = $("#file-restore");
  const restoreBtn = $("#btn-restore");
  if (restoreBtn && restoreInput) {
    restoreBtn.addEventListener("click", () => restoreInput.click());
    restoreInput.addEventListener("change", () => {
      const file = restoreInput.files[0];
      restoreInput.value = "";
      if (!file) return;
      // a shelf is big and nothing else says so: the button says it while
      // the bytes go up, because there is no progress to show over a body
      const was = restoreBtn.textContent;
      restoreBtn.disabled = true;
      restoreBtn.textContent = "Restoring…";
      restoreShelf(file)
        .catch(e => toast(e.message, true))
        .finally(() => { restoreBtn.disabled = false; restoreBtn.textContent = was; });
    });
  }

  applyLangFilter();
  load();
}

/* ================================================================ deck */

function initDeck() {
  // the chrome outside the sheets (modals, the form) takes the deck's language
  document.body.dataset.lang = lang().code;
  let deck = readScript($("#deck-json"), null);
  if (!deck || !deck.folder) { toast("This page came without its deck", true); return; }
  const base = deckApi(deck);
  let items = [];
  let visible = [];
  const selected = new Set();
  // A source is an OR within this facet, then an AND with the text, type,
  // state and tag facets below.  It is deliberately page-local: browsing a
  // deck must not change its stored exercises or their provenance.
  const sourceFilters = new Set();
  const sourceLabels = new Map();
  let selectionAnchor = null;
  const selectionKey = `parseh-selected:${deck.path}`;
  try {
    const kept = JSON.parse(sessionStorage.getItem(selectionKey) || "[]");
    if (Array.isArray(kept)) kept.forEach(id => { if (typeof id === "string") selected.add(id); });
  } catch (e) { /* private browsing or an old selection */ }
  const arrival = new URLSearchParams(location.search);
  const movedIds = arrival.get("selected");
  if (movedIds) {
    movedIds.split(",").filter(id => /^[0-9a-f]{12}$/.test(id)).forEach(id => selected.add(id));
  }
  if (movedIds || arrival.has("notice") || arrival.has("warning"))
    history.replaceState(null, "", location.pathname);
  if (arrival.has("warning")) toast(arrival.get("warning"), true);
  else if (arrival.has("notice")) toast(arrival.get("notice"));
  const openIds = new Set();          // rows whose solved preview is open
  const shownHtml = new Map();        // id -> {updated, html}

  function renderHead() {
    $("#deck-name").textContent = deck.name;
    document.title = `${deck.name} — Parseh exercises`;
    const c = deck.counts || {}, due = toStudy(deck.study);
    const box = $("#deck-counts");
    box.replaceChildren(el("span", "dk-totals",
      `${plural(c.total || 0, "exercise")} · ${c.new || 0} new · ${c.learning || 0} learning · ` +
      `${c.review || 0} in review`));
    if (c.total) {
      const now = el("span", "dk-now");
      // what is due is the clock's, and the clock has moved since the
      // computer said this: taken off the page while it cannot be reached
      // (the owner's 1, 2026-09-23; lib/keep.js, showClock)
      now.dataset.clockCount = "";
      now.append(el("span", "dk-label", "To study now"), studyCounts(deck.study));
      if (!due) now.appendChild(el("span", "dk-next", nextDueText(deck.next_due, rolloverOf(deck))));
      box.appendChild(now);
    }
    const study = $("#btn-study");
    study.href = studyPage(deck);
    setLinkEnabled(study, due > 0, due ? `${plural(due, "exercise")} to study now` : "Nothing to study now");
    // The mobile layout's own two: cramming every exercise at a tap (the
    // list below crams the ones picked in it, in both layouts), once the
    // list is here to take them from; and a line for a deck a phone can do
    // nothing with -- empty -- or can only cram.
    const practise = $("#btn-practise");
    if (practise) practise.disabled = !items.length;
    const note = $("#deck-mobile-note");
    if (note) {
      note.textContent = !c.total ? "This deck has no exercises yet: they are added in the browser interface."
        : due ? "" : "Nothing is due now. Cramming leaves the scheduling as it is.";
      note.hidden = !note.textContent;
    }
    paintCheckout();
    // no list to pick from, said as soon as the note is (renderList says it
    // again from the exercises themselves)
    $(".dk-browse").classList.toggle("dk-none", !c.total);
    $("#btn-export-sched").href = exportUrl(deck, true);
    $("#btn-export-plain").href = exportUrl(deck, false);
  }

  /* WHO HAS THIS DECK (§19.10).  On the computer: a line saying it is out,
     with the way to take it back, and what could not be applied after a
     take-back; Study is shut while it is out, cramming is not.  On the phone:
     Take it out / Give it back. */
  let checkout = null;
  function paintCheckout() {
    const box = $("#deck-checkout");
    const out = deckOut(deck);
    const mine = !!(out && checkout && checkout.out && checkout.id === out.id);
    const takeout = $("#btn-takeout"), giveback = $("#btn-giveback");
    if (takeout) {
      takeout.hidden = !isMobile() || !!(checkout && checkout.out);
      takeout.disabled = false;
    }
    if (giveback) {
      giveback.hidden = !isMobile() || !mine;
      giveback.disabled = false;
    }
    if (!box) return;
    box.replaceChildren();
    const refused = (checkout && checkout.refused) || [];
    if (!(checkout && checkout.out) && !refused.length) { box.hidden = true; return; }
    box.hidden = false;
    if (checkout && checkout.out) {
      box.appendChild(el("span", "dk-outsay",
        mine ? `This deck is out on this device since ${(checkout.since || "").slice(0, 16).replace("T", " ")}. ` +
               "The computer will not study or edit it until it comes back."
             : `This deck is on ${checkout.device || "a phone"} since ` +
               `${(checkout.since || "").slice(0, 16).replace("T", " ")}. It can be crammed here; ` +
               "studying and editing wait for it."));
      if (!isMobile()) {
        const back = el("button", "btn danger ghost", "Take it back");
        back.type = "button";
        back.title = "For a phone that will not come back. After this, what that phone answered " +
                     "is refused and listed here rather than applied.";
        back.addEventListener("click", async () => {
          if (!confirm("Take this deck back from " + (checkout.device || "that phone") + "?\n\n" +
                       "What it has answered since, and has not sent yet, cannot be applied " +
                       "afterwards — it will be listed here instead.")) return;
          back.disabled = true;
          try { await call(base + "/takeback", {method: "POST", json: {}}); await reload(); }
          catch (e) { toast("It could not be taken back: " + e.message, true); back.disabled = false; }
        });
        box.appendChild(back);
      }
    }
    if (refused.length) {
      const list = el("div", "dk-refused");
      list.appendChild(el("span", "dk-label",
        `${plural(refused.length, "answer")} could not be applied`));
      refused.slice(-8).forEach(r => {
        list.appendChild(el("div", "dk-refuse",
          `${(r.at || "").slice(0, 16).replace("T", " ")} · ${r.rating || "?"} · ${r.why || ""}`));
      });
      const clear = el("button", "btn ghost small", "I have seen these");
      clear.type = "button";
      clear.addEventListener("click", async () => {
        clear.disabled = true;
        try { await call(base + "/refused", {method: "POST", json: {}}); await reload(); }
        catch (e) { clear.disabled = false; }
      });
      list.appendChild(clear);
      box.appendChild(list);
    }
  }

  async function load() {
    const data = await call(base);
    deck = data.deck;
    checkout = data.checkout || null;
    items = data.items || [];
    const live = new Set(items.map(it => it.id));
    for (const id of selected) if (!live.has(id)) selected.delete(id);
    renderHead();
    fillTypes();
    fillTags();
    renderList();
  }
  const reload = () => load().catch(e => toast("Could not read the deck: " + e.message, true));

  // taking the deck out, and giving it back (§19.10)
  const takeoutBtn = $("#btn-takeout"), givebackBtn = $("#btn-giveback");
  if (takeoutBtn) takeoutBtn.addEventListener("click", async () => {
    takeoutBtn.disabled = true;
    takeoutBtn.textContent = "Taking it…";
    try {
      // taking it out keeps it first where it is not kept, and says which of
      // the two it is doing while it does it (the owner's 8, 2026-09-23)
      await takeDeckOut(deck, what => {
        takeoutBtn.textContent = "Keeping it…";
        toast(what);
      });
      toast("This deck is on this device now: study it with the computer away, and give it " +
            "back when you are done");
      await reload();
    } catch (e) {
      toast(e.message || "it could not be taken out", true);
    } finally {
      takeoutBtn.textContent = "Take it out";
      takeoutBtn.disabled = false;
    }
  });
  if (givebackBtn) givebackBtn.addEventListener("click", async () => {
    givebackBtn.disabled = true;
    givebackBtn.textContent = "Sending…";
    try {
      await giveDeckBack(deck);
      toast("Given back: the computer has what was answered here");
      await reload();
    } catch (e) {
      toast(e.message || "it could not be given back", true);
    } finally {
      givebackBtn.textContent = "Give it back";
      givebackBtn.disabled = false;
    }
  });

  /* ---- the browse list ---- */

  /* An exercise copied from notes beside a book or a video records the
     notes' mount (/books/<folder>/<slug>/notes, /youtube/v/<id>/notes); its
     document lives there, not in the studio.  Only a path on this server,
     as the store keeps it: a hand-edited file cannot make the link go
     elsewhere. */
  const notesMount = source =>
    typeof source === "string" && /^\/[A-Za-z0-9._~%-][A-Za-z0-9._~%\/-]{0,299}$/.test(source)
      && !source.split("/").includes("..") ? source.replace(/\/+$/, "") : "";
  /* A card made in a book's reader or a video's player names the book
     (/books/<folder>/<slug>) or the video (its id), the moment in it and a
     link back to that moment -- as the store keeps them (decks._clean_origin):
     a path on this server or a YouTube address, nothing a browser would take
     for another host. */
  const bookPath = b =>
    typeof b === "string" && /^\/books\/[A-Za-z0-9_~%-][A-Za-z0-9._~%-]{0,99}\/[A-Za-z0-9_~%-][A-Za-z0-9._~%-]{0,199}$/.test(b)
      && !b.split("/").includes("..") ? b : "";
  const videoId = v => typeof v === "string" && /^(?!\.+$)[A-Za-z0-9._-]{1,90}$/.test(v) ? v : "";
  const backUrl = u =>
    typeof u === "string" && u.length <= 500
      && /^(?:\/(?![\/\\])|https:\/\/www\.youtube\.com\/)[^\s\\\x00-\x1f\x7f]*$/.test(u) ? u : "";

  /* What one source means in the browse facet.  A document's saved uid is
     its identity even if its title was later changed or the document is no
     longer here; old cards without one fall back to their saved id, then
     title.  The label is likewise only saved provenance, never a fresh
     document lookup. */
  function sourceOf(it) {
    const o = it && it.origin && typeof it.origin === "object" ? it.origin : {};
    const saved = value => typeof value === "string" ? value.trim() : "";
    const uid = saved(o.doc_uid), docId = saved(o.doc_id), title = saved(o.title);
    // A book or a video origin carries a title too (Browse's own "from …"
    // row prints it for either kind), so title alone must never decide this:
    // only doc_uid/doc_id say "document", the same test the row's own link
    // uses (o.doc_id, just above). A bare title with none of the three is
    // "written here", exactly as that row already reads it.
    const book = bookPath(o.book), video = videoId(o.video);
    if (uid || docId) {
      const identity = uid ? `uid:${uid}` : `id:${docId}`;
      return {key: `document:${identity}`, label: `Document: ${title || docId || uid}`};
    }
    if (book) return {key: `book:${book}`, label: `Book: ${title || book.split("/").pop()}`};
    if (video) return {key: `video:${video}`, label: `Video: ${title || video}`};
    return {key: "written-here", label: "Written here"};
  }

  const typeKey = it => it.subtype || "unreadable";
  const bucket = it => {
    const s = (it.schedule || {}).state;
    return s === "relearning" || s === "learning" ? "learning" : s === "review" ? "review" : "new";
  };
  function dueNow(it) {
    const s = it.schedule || {};
    if (!s.state || s.state === "new" || !s.due) return false;
    const r = rolloverOf(deck);
    // a review is due for its whole day, as the scheduler counts it;
    // a learning step is an instant
    if (s.state === "review") {
      const day = dueDay(s.due, r);
      return Number.isFinite(day) && day <= dayNumber(new Date(), r);
    }
    const t = Date.parse(s.due);
    return Number.isFinite(t) && t <= Date.now();
  }

  function fillTypes() {
    const sel = $("#browse-type"), current = sel.value;
    const seen = new Map();
    for (const it of items) {
      const k = typeKey(it);
      const row = seen.get(k) || {label: it.subtype ? (it.label || it.subtype) : "Unreadable", n: 0};
      row.n++;
      seen.set(k, row);
    }
    const all = el("option", "", "All types");
    all.value = "";
    sel.replaceChildren(all);
    [...seen.entries()].sort((a, b) => a[1].label.localeCompare(b[1].label)).forEach(([k, row]) => {
      const o = el("option", "", `${row.label} (${row.n})`);
      o.value = k;
      sel.appendChild(o);
    });
    sel.value = seen.has(current) ? current : "";
  }

  function fillTags() {
    const sel = $("#browse-tag"), current = sel.value;
    const counts = new Map();
    items.forEach(it => (it.tags || []).forEach(tag => counts.set(tag, (counts.get(tag) || 0) + 1)));
    const all = el("option", "", "All tags");
    all.value = "";
    sel.replaceChildren(all);
    [...counts].sort((a, b) => a[0].localeCompare(b[0])).forEach(([tag, count]) => {
      const option = el("option", "", `${tag} (${count})`);
      option.value = tag;
      sel.appendChild(option);
    });
    sel.value = counts.has(current) ? current : "";
  }

  function browseFilters() {
    return {q: foldCase($("#browse-filter").value.trim()), type: $("#browse-type").value,
            state: $("#browse-state").value, tag: $("#browse-tag").value};
  }

  function matchesOtherFilters(it, filters) {
    return (!filters.q || foldCase(it.excerpt || "").includes(filters.q)
            || foldCase(it.markdown || "").includes(filters.q))
      && (!filters.type || typeKey(it) === filters.type)
      && (!filters.state || (filters.state === "due" ? dueNow(it) : bucket(it) === filters.state))
      && (!filters.tag || (it.tags || []).includes(filters.tag));
  }

  /* The source menu is a self-narrowing facet: its counts and choices are
     made after the other filters but before source choices.  An active
     source with no remaining match stays as a checked zero only long enough
     to be cleared; otherwise an AND filter could silently turn itself off.
     Unselected zeroes are never offered. */
  function renderSourceOptions(filters) {
    const choices = new Map();
    for (const it of items) {
      const source = sourceOf(it);
      if (!sourceLabels.has(source.key)) sourceLabels.set(source.key, source.label);
      if (!matchesOtherFilters(it, filters)) continue;
      const row = choices.get(source.key) || {key: source.key, label: source.label, count: 0};
      row.count++;
      choices.set(source.key, row);
    }
    for (const key of sourceFilters) {
      if (!choices.has(key))
        choices.set(key, {key, label: sourceLabels.get(key) || "Unavailable source", count: 0});
    }

    const box = $("#browse-source-options"), menu = $("#browse-source-filter");
    const active = document.activeElement;
    const focusedKey = active && active.matches && active.matches("input[data-source-key]")
      ? active.dataset.sourceKey : "";
    const rows = [...choices.values()].sort((a, b) => a.label.localeCompare(b.label) || a.key.localeCompare(b.key));
    box.replaceChildren(...rows.map(row => {
      const label = el("label", "dk-source-option");
      if (!row.count) label.classList.add("dk-source-zero");
      const input = el("input");
      input.type = "checkbox";
      input.dataset.sourceKey = row.key;
      input.checked = sourceFilters.has(row.key);
      const name = el("span", "dk-source-name", row.label);
      const count = el("span", "dk-source-count", `(${row.count})`);
      label.append(input, name, count);
      return label;
    }));
    menu.hidden = rows.length === 0;
    if (!rows.length) menu.open = false;
    $("#browse-source-label").textContent = sourceFilters.size ? `Sources (${sourceFilters.size})` : "Sources";
    if (focusedKey) {
      const next = $$('input[data-source-key]', box).find(input => input.dataset.sourceKey === focusedKey);
      if (next) next.focus();
      else $("#browse-source-filter summary").focus();
    }
  }

  function updateSelection() {
    const n = selected.size;
    try { sessionStorage.setItem(selectionKey, JSON.stringify([...selected])); }
    catch (e) { /* page-local selection still works */ }
    $("#browse-selected").textContent = `${n} selected`;
    ["copy", "move", "add-tag", "remove-tag", "new", "delete"].forEach(x => {
      $(`#btn-bulk-${x}`).disabled = n === 0;
    });
    $("#btn-cram").disabled = n === 0;
    $("#btn-cram").textContent = n ? `Cram ${plural(n, "exercise")}` : "Cram exercises";
    // beside it, the same selection as one page for a website (§9.7)
    const xp = $("#btn-export-html");
    if (xp && !xp.dataset.busy) xp.disabled = n === 0;
    // the mobile layout's, over the list while anything is picked
    const go = $("#m-cram");
    if (go) {
      go.hidden = n === 0;
      go.textContent = `Cram ${plural(n, "exercise")}`;
    }
  }

  function selectRange(id, checked) {
    const end = visible.findIndex(it => it.id === id);
    const start = visible.findIndex(it => it.id === selectionAnchor);
    if (end < 0) return;
    // Only rows currently shown are between the two clicks. A filtered-out
    // anchor starts a new range without changing hidden selections.
    const range = start < 0 ? [visible[end]] :
      visible.slice(Math.min(start, end), Math.max(start, end) + 1);
    const rows = new Map($$(".dk-row", $("#browse-list")).map(row => [row.dataset.id, row]));
    for (const it of range) {
      if (checked) selected.add(it.id);
      else selected.delete(it.id);
      const row = rows.get(it.id);
      if (row) {
        $(".dk-select", row).checked = checked;
        row.classList.toggle("selected", checked);
      }
    }
    selectionAnchor = id;
    updateSelection();
  }

  function renderList() {
    const filters = browseFilters();
    renderSourceOptions(filters);
    const shown = items.filter(it => matchesOtherFilters(it, filters)
      && (!sourceFilters.size || sourceFilters.has(sourceOf(it).key)));
    visible = shown;
    $("#browse-list").replaceChildren(...shown.map(itemRow));
    $("#browse-count").textContent = filters.q || filters.type || filters.state || filters.tag || sourceFilters.size
      ? `${shown.length} of ${items.length}` : plural(items.length, "exercise");
    const empty = $("#browse-empty");
    empty.hidden = shown.length > 0;
    $('[data-x="empty-deck"]', empty).hidden = items.length > 0;
    $('[data-x="empty-filter"]', empty).hidden = items.length === 0;
    // a deck with nothing in it has nothing to pick: the mobile layout
    // says so once, over Study now, and draws no list (static/mobile.css)
    $(".dk-browse").classList.toggle("dk-none", items.length === 0);
    updateSelection();
  }

  function itemRow(it) {
    const s = it.schedule || {};
    const row = el("article", "dk-row" + (selected.has(it.id) ? " selected" : ""));
    row.dataset.id = it.id;
    row.innerHTML = `
      <input type="checkbox" class="dk-select" aria-label="Select exercise" ${selected.has(it.id) ? "checked" : ""}>
      <button type="button" class="dk-row-toggle" aria-expanded="false"
              title="Show the exercise, solved">
        <span class="dk-kickers"><span class="ex-kicker"></span></span>
        <span class="dk-excerpt" dir="auto"></span>
      </button>
      <div class="dk-row-meta">
        <span class="dk-state dk-state-${bucket(it)}"></span>
        <span class="dk-when"></span>
        <span class="dk-reps"></span>
        <span class="dk-origin"></span>
        <span class="dk-item-tags"></span>
      </div>
      <div class="dk-row-actions">
        <button type="button" class="btn small" data-x="edit">Edit</button>
        <button type="button" class="btn small" data-x="duplicate">Duplicate</button>
        <button type="button" class="btn small" data-x="copy">Copy to deck…</button>
        <button type="button" class="btn small" data-x="move">Move to deck…</button>
        <button type="button" class="btn small danger ghost" data-x="delete">Delete</button>
      </div>
      <div class="dk-row-preview" hidden></div>`;
    $(".ex-kicker", row).textContent = it.label || it.subtype || "Exercise";
    if ((it.mates || []).length) {
      // the two sides of a pair look alike: this says which one a row is
      const pair = el("span", "badge dk-linked", `↔ linked · ${sideOf(it)} first`);
      pair.title = "One side of a pair: the front and the back of one card. " +
                   "Editing or deleting it asks about the other side.";
      $(".dk-kickers", row).appendChild(pair);
    }
    if ((it.errors || []).length) {
      const bad = el("span", "badge err", "needs attention");
      bad.title = it.errors.join("\n");
      $(".dk-kickers", row).appendChild(bad);
    }
    $(".dk-excerpt", row).textContent = it.excerpt || "(no text)";
    $(".dk-select", row).setAttribute("aria-label",
      `Select ${it.label || it.subtype || "exercise"}: ${(it.excerpt || "no text").slice(0, 100)}`);
    $(".dk-select", row).title = "Shift-click to select or deselect a range";
    $(".dk-state", row).textContent = s.state === "relearning" ? "relearning" : bucket(it);
    $(".dk-when", row).textContent = bucket(it) === "new" ? "not studied yet"
      : dueNow(it) ? "due now" : ("due " + whenDue(s.due, rolloverOf(deck))).trim();
    $(".dk-reps", row).textContent = `${plural(it.reps || 0, "review")} · ${plural(it.lapses || 0, "lapse")}`;
    $(".dk-item-tags", row).textContent = (it.tags || []).length ? `Tags: ${it.tags.join(", ")}` : "";
    $(".dk-select", row).addEventListener("click", e => {
      if (e.shiftKey) selectRange(it.id, e.currentTarget.checked);
    });
    $(".dk-select", row).addEventListener("change", e => {
      if (e.target.checked) selected.add(it.id);
      else selected.delete(it.id);
      row.classList.toggle("selected", e.target.checked);
      selectionAnchor = it.id;
      updateSelection();
    });
    const origin = $(".dk-origin", row), o = it.origin;
    const book = o ? bookPath(o.book) : "", video = o ? videoId(o.video) : "";
    if (o && o.doc_id) {
      const a = el("a", "", o.title || o.doc_id);
      const notes = notesMount(o.source);
      a.href = `${notes || STUDIO}/doc/${seg(o.doc_id)}`;
      a.title = notes ? "The notes it was copied from" : "The studio document it was copied from";
      origin.append("from ", a);
      if (o.duplicate_of) origin.append(" (a duplicate)");
    } else if (book || video) {
      // the book or the video, and where in it: its link opens that moment
      const name = (typeof o.title === "string" && o.title) || (book ? book.split("/").pop() : video);
      const label = typeof o.label === "string" ? o.label : "";
      const a = el("a", "dk-made", label ? `${name} · ${label}` : name);
      // a book at the link it was made with, else its reader; a video in
      // Parseh's own player at its second, its link only when no second
      // was kept (a YouTube address would leave Parseh)
      const at = Number.isFinite(o.time) && o.time >= 0 ? Math.floor(o.time) : null;
      const player = `/youtube/v/${seg(video)}/`;
      a.href = book ? backUrl(o.url) || `${book}/reader/`
        : at !== null ? `${player}#t=${at}` : backUrl(o.url) || player;
      a.title = book ? "The book the card was made from" : "The video the card was made from";
      origin.append("from ", a);
      if (o.duplicate_of) origin.append(" (a duplicate)");
    } else {
      origin.textContent = o && o.duplicate_of ? "a duplicate" : "written here";
    }

    row.addEventListener("click", e => {
      // the buttons, the links and the exercise itself keep their own clicks
      if (e.target.closest(".dk-row-actions, .dk-row-preview, a, input")) return;
      if (e.target.closest("button:not(.dk-row-toggle)")) return;
      if (e.shiftKey) {
        selectRange(it.id, !selected.has(it.id));
        return;
      }
      togglePreview(row, it);
    });
    $('[data-x="edit"]', row).addEventListener("click", () =>
      editExercise(deck, it, async markdown => {
        savedToast("Exercise saved", await saveEdited(deck, it, markdown));
        reload();
      }));
    $('[data-x="duplicate"]', row).addEventListener("click", async e => {
      const b = e.currentTarget;
      b.disabled = true;
      try {
        await call(`${base}/items/${it.id}/duplicate`, {method: "POST"});
        toast("Duplicated: the copy starts as new");
        reload();
      } catch (err) { toast(err.message, true); b.disabled = false; }
    });
    $('[data-x="copy"]', row).addEventListener("click", () => transfer("copy", [it.id]));
    $('[data-x="move"]', row).addEventListener("click", () => transfer("move", [it.id], selected.has(it.id)));
    $('[data-x="delete"]', row).addEventListener("click", async () => {
      const del = linked => call(`${base}/items/${it.id}` + (linked ? `?linked=${linked}` : ""),
                                 {method: "DELETE"});
      const ask = (others, stack) => askLinked({
        stack, others, title: "This card has another side", danger: true, act: del,
        hint: LINKED_HINT + " Delete the other side too?",
        both: "Delete both", alone: "Delete only this (the other stays, unlinked)"});
      // a card the list knows is one side of a pair is asked about at once;
      // one that became so meanwhile is refused by the server, and asked then
      const linked = mateRows(items, it);
      const done = linked.length ? await ask(linked, false) : await dialog({
        title: "Delete this exercise?",
        hint: `“${it.excerpt || it.label}” and its scheduling (${plural(it.reps || 0, "review")}) ` +
              "leave the deck for good.",
        buttons: [CANCEL, {label: "Delete exercise", danger: true, run: async () => {
          try {
            return {choice: "", data: await del()};
          } catch (e) {
            if (e.conflict !== "linked") throw e;
            const asked = await ask((e.detail && e.detail.mates) || [], true);
            if (!asked) throw new Error("Not deleted");
            return asked;
          }
        }}],
      });
      if (!done) return;
      openIds.delete(it.id);
      toast(done.choice === "both" ? "Both cards deleted" : "Exercise deleted");
      reload();
    });
    if (openIds.has(it.id)) togglePreview(row, it, true);
    return row;
  }

  async function togglePreview(row, it, open) {
    const box = $(".dk-row-preview", row), toggle = $(".dk-row-toggle", row);
    if (open === undefined) open = box.hidden;
    toggle.setAttribute("aria-expanded", String(open));
    row.classList.toggle("open", open);
    box.hidden = !open;
    if (!open) { openIds.delete(it.id); return; }
    openIds.add(it.id);
    let shown = shownHtml.get(it.id);
    if (!shown || shown.updated !== it.updated) {
      box.replaceChildren(el("p", "pv-status", "Rendering…"));
      try {
        const data = await call(`${base}/items/${it.id}`);
        shown = {updated: it.updated, html: data.html || ""};
        shownHtml.set(it.id, shown);
      } catch (e) {
        box.replaceChildren(el("p", "pv-status err", "Preview unavailable: " + e.message));
        return;
      }
      if (box.hidden || !row.isConnected) return;     // closed or redrawn meanwhile
    }
    // a row reopened while the list is being redrawn is not in the page
    // yet, and applyTypo styles only the sheets it can find there
    if (!row.isConnected) await Promise.resolve();
    const sheet = el("div", "sheet dk-sheet");
    sheet.dataset.lang = deck.lang;
    sheet.innerHTML = shown.html;
    $$(".ex-edit, .ex-to-deck, .exercise-correction", sheet).forEach(x => x.remove());
    box.replaceChildren(sheet);
    applyTypo(loadTypo(null));                    // the new sheet takes the typography
    bindExercises(sheet, {preview: true});
  }

  const redraw = debounce(renderList, 120);
  $("#browse-filter").addEventListener("input", redraw);
  $("#browse-type").addEventListener("change", renderList);
  $("#browse-state").addEventListener("change", renderList);
  $("#browse-tag").addEventListener("change", renderList);
  $("#browse-source-options").addEventListener("change", e => {
    const input = e.target.closest && e.target.closest("input[data-source-key]");
    if (!input) return;
    if (input.checked) sourceFilters.add(input.dataset.sourceKey);
    else sourceFilters.delete(input.dataset.sourceKey);
    renderList();
  });

  $("#btn-select-all").addEventListener("click", () => {
    items.forEach(it => selected.add(it.id));
    renderList();
  });
  $("#btn-select-shown").addEventListener("click", () => {
    visible.forEach(it => selected.add(it.id));
    renderList();
  });
  // its opposite: the rows the filters show are let go, and whatever they
  // hide stays selected -- so a selection is trimmed by filtering, the way
  // Select shown builds one
  $("#btn-deselect-shown").addEventListener("click", () => {
    visible.forEach(it => selected.delete(it.id));
    renderList();
  });
  $("#btn-deselect-all").addEventListener("click", () => {
    selected.clear();
    renderList();
  });
  $("#btn-select-tag").addEventListener("click", async () => {
    const tags = [...new Set(items.flatMap(it => it.tags || []))].sort();
    if (!tags.length) { toast("This deck has no exercise tags yet"); return; }
    const pick = el("select");
    tags.forEach(tag => {
      const option = el("option", "", tag);
      option.value = tag;
      pick.appendChild(option);
    });
    if (tags.includes($("#browse-tag").value)) pick.value = $("#browse-tag").value;
    const tag = await dialog({title: "Select exercises by tag", body: field("Tag", pick),
                              buttons: [CANCEL, {label: "Select matching", primary: true,
                                                 run: () => pick.value}]});
    if (!tag) return;
    selected.clear();
    items.filter(it => (it.tags || []).includes(tag)).forEach(it => selected.add(it.id));
    renderList();
  });

  async function transfer(action, ids, carrySelection = false) {
    let choices;
    try {
      const data = await call(`/api/decks?lang=${seg(deck.lang)}`);
      choices = (data.decks || []).filter(d => d.path !== deck.path && d.lang === deck.lang);
    } catch (e) { toast(e.message, true); return; }
    if (!choices.length) { toast("Create another deck in this language first"); return; }
    const pick = el("select");
    choices.forEach(d => {
      const option = el("option", "", d.name);
      option.value = d.path;
      pick.appendChild(option);
    });
    const verb = action === "move" ? "Move" : "Copy";
    let destination = null;
    const done = await dialog({
      title: `${verb} ${plural(ids.length, "exercise")} to another deck`,
      hint: action === "move" ? "Scheduling and tags travel with moved exercises." :
                               "Copies keep their tags and start with fresh scheduling.",
      body: field("Destination deck", pick),
      buttons: [CANCEL, {label: `${verb} to deck`, primary: action === "copy",
                         run: async () => {
                           const target = choices.find(d => d.path === pick.value);
                           destination = target;
                           return call(base + "/items/bulk", {method: "POST", json: {
                             action, ids, target: {folder: target.folder, slug: target.slug}}});
                         }}],
    });
    if (!done) return;
    if (action === "move" && carrySelection && destination) {
      const key = `parseh-selected:${destination.path}`;
      let saved = false;
      try {
        const previous = JSON.parse(sessionStorage.getItem(key) || "[]");
        const kept = Array.isArray(previous) ? previous : [];
        sessionStorage.setItem(key, JSON.stringify([...new Set([...kept, ...(done.ids || [])])]));
        saved = true;
      } catch (e) { /* selection travels in the URL when storage is unavailable */ }
      const params = new URLSearchParams();
      if (!saved) params.set("selected", (done.ids || []).join(","));
      params.set("notice", `${plural(done.count, "exercise")} moved`);
      if ((done.warnings || []).length) params.set("warning", done.warnings.join("; "));
      location.href = deckPage(destination) + "?" + params;
      return;
    }
    if (action === "move") ids.forEach(id => selected.delete(id));
    toast(`${done.count} ${done.count === 1 ? "exercise" : "exercises"} ${action === "move" ? "moved" : "copied"}`);
    if ((done.warnings || []).length) toast(done.warnings.join("; "), true);
    reload();
  }
  $("#btn-bulk-copy").addEventListener("click", () => transfer("copy", [...selected]));
  $("#btn-bulk-move").addEventListener("click", () => transfer("move", [...selected], true));
  $("#btn-bulk-delete").addEventListener("click", async () => {
    const ids = [...selected];
    if (!ids.length) return;
    const del = linked => call(base + "/items/bulk", {method: "POST", json:
      linked ? {action: "delete", ids, linked} : {action: "delete", ids}});
    // asked ONCE, for the whole selection, when a picked card is one side of
    // a pair whose other side is not picked: the other sides go too, or stay
    const ask = (others, count, stack) => askLinked({
      stack, others, danger: true, act: del,
      title: `Delete ${plural(ids.length, "exercise")}?`,
      hint: `${plural(count, "picked exercise")} ${count === 1 ? "is" : "are"} one side of a pair ` +
            "whose other side is not picked (shown here). Their scheduling will be deleted too.",
      both: "Delete their other sides too", alone: "Delete only the selected"});
    const picked = items.filter(it => selected.has(it.id));
    const outside = [...new Set(picked.flatMap(it => it.mates || []).filter(id => !selected.has(id)))];
    try {
      let done;
      if (outside.length) {
        done = await ask(outside.map(id => items.find(x => x.id === id)).filter(Boolean),
                         picked.filter(it => (it.mates || []).some(id => !selected.has(id))).length, false);
      } else {
        const okay = await confirmDialog({title: `Delete ${plural(ids.length, "exercise")}?`,
          hint: "Their scheduling will be deleted too.", ok: "Delete selected", danger: true});
        if (!okay) return;
        try { done = {choice: "", data: await del()}; }
        catch (e) {
          if (e.conflict !== "linked") throw e;
          const d = e.detail || {};
          done = await ask(d.mates || [], d.count || 1, false);
        }
      }
      if (!done) return;
      selected.clear();
      toast(`${plural(done.data.count, "exercise")} deleted`);
      reload();
    } catch (e) { toast(e.message, true); }
  });
  $("#btn-bulk-new").addEventListener("click", async () => {
    const ids = [...selected];
    if (!ids.length) return;
    const okay = await confirmDialog({title: `Set ${plural(ids.length, "exercise")} to new?`,
      hint: "Their review history and scheduling will be cleared. They will remain selected.",
      ok: "Set to new"});
    if (!okay) return;
    try {
      await call(base + "/items/bulk", {method: "POST", json: {action: "set-new", ids}});
      toast(`${plural(ids.length, "exercise")} set to new`);
      reload();
    } catch (e) { toast(e.message, true); }
  });
  $("#btn-bulk-add-tag").addEventListener("click", async () => {
    const ids = [...selected], input = textInput("");
    const done = await dialog({title: `Tag ${plural(ids.length, "exercise")}`,
      body: field("Tag", input), buttons: [CANCEL, {label: "Add tag", primary: true,
        run: () => call(base + "/items/bulk", {method: "POST", json: {
          action: "add-tag", ids, tag: input.value}})}]});
    if (done) { toast("Tag added"); reload(); }
  });
  $("#btn-bulk-remove-tag").addEventListener("click", async () => {
    const ids = [...selected];
    const tags = [...new Set(items.filter(it => selected.has(it.id)).flatMap(it => it.tags || []))].sort();
    if (!tags.length) { toast("The selected exercises have no tags"); return; }
    const pick = el("select");
    tags.forEach(tag => {
      const option = el("option", "", tag);
      option.value = tag;
      pick.appendChild(option);
    });
    const done = await dialog({title: `Remove a tag from ${plural(ids.length, "exercise")}`,
      body: field("Tag", pick), buttons: [CANCEL, {label: "Remove tag", primary: true,
        run: () => call(base + "/items/bulk", {method: "POST", json: {
          action: "remove-tag", ids, tag: pick.value}})}]});
    if (done) { toast("Tag removed"); reload(); }
  });
  function cramSelected() {
    const ids = items.filter(it => selected.has(it.id)).map(it => it.id);
    if (!ids.length) return;
    let stored = false;
    try { sessionStorage.setItem(`parseh-cram:${deck.path}`, JSON.stringify(ids)); stored = true; }
    catch (e) { /* carry the selected ids in the URL instead */ }
    location.href = deckPage(deck) + "cram" + (stored ? "" : `?selected=${ids.join(",")}`);
  }
  $("#btn-cram").addEventListener("click", cramSelected);
  $("#m-cram").addEventListener("click", cramSelected);

  /* EXPORT SELECTED TO HTML (TO-DO §9.7): the picked exercises as ONE page
     that crams them, for a website -- asked of the deck with the ids, as the
     cram page asks, and saved as the file the answer names.  Nothing about
     the deck changes; webexport.py says what the page holds and what it
     never does (the exercises' Markdown among it). */
  const exportButton = $("#btn-export-html");
  const exportLabel = exportButton ? exportButton.textContent : "";
  const exporter = exportButton && madeDownload({
    place: el => exportButton.closest(".dk-bulkbar").after(el),
    busy: on => {
      if (on) exportButton.dataset.busy = "1";
      else delete exportButton.dataset.busy;
      exportButton.textContent = on ? "Exporting…" : exportLabel;
      exportButton.disabled = on || selected.size === 0;
    },
    done: (r, name, req) => {
      // a latex block that could not be drawn travels as a frame saying so
      const failed = +(r.headers.get("X-Parseh-Drawings-Failed") || 0);
      toast(`${plural(req.count, "exercise")} exported: ${name}` +
            (failed ? ` — ${plural(failed, "drawing")} could not be made` : ""));
    },
  });
  function exportSelected() {
    const ids = items.filter(it => selected.has(it.id)).map(it => it.id);
    if (!ids.length || !exporter || exportButton.dataset.busy) return;
    exporter.start({url: BASE + base + "/export-html", count: ids.length,
                    init: {method: "POST", headers: {"Content-Type": "application/json"},
                           body: JSON.stringify({ids})},
                    label: `Exporting ${plural(ids.length, "exercise")} of “${deck.name}” to HTML`,
                    failed: "The exercises were not exported",
                    fallback: (deck.slug || "exercises") + ".html"});
  }
  if (exportButton) exportButton.addEventListener("click", exportSelected);

  /* ---- adding, the deck's own buttons ---- */

  async function addExercise(markdown) {
    let data;
    try {
      data = await call(base + "/items", {method: "POST", json: {markdown}});
    } catch (e) {
      if (e.conflict !== "duplicate") throw e;
      const again = await confirmDialog({
        stack: true, title: "Already in this deck",
        hint: cap(e.message) + ". Add it a second time?", ok: "Add again"});
      // the form stays open, so the exercise can still be changed
      if (!again) throw new Error("Not added: the same exercise is already in this deck");
      data = await call(base + "/items", {method: "POST", json: {markdown, force: true}});
    }
    // a both-repeat card went in as two, the front first and the back first
    savedToast((data.items || []).length > 1 ? `Added two linked cards to “${deck.name}”`
                                             : `Added to “${deck.name}”`, data);
    reload();
  }

  $("#btn-add-exercise").addEventListener("click", () => openExercisePicker(Object.assign({
    onSave: addExercise, preview: formPreview(deck), saveLabel: "Add to deck"}, uploads(deck))));

  $("#btn-rename").addEventListener("click", async () => {
    const input = textInput(deck.name, {maxlength: "200"});
    const renamed = await dialog({
      title: "Rename the deck", body: field("Name", input),
      hint: "Only the name changes: the deck's address, exercises and scheduling stay.",
      buttons: [CANCEL, {label: "Rename", primary: true, run: async () => {
        const name = input.value.trim();
        if (!name) throw new Error("The name cannot be empty");
        return (await call(base, {method: "PATCH", json: {name}})).deck;
      }}],
    });
    if (!renamed || !renamed.name) return;
    deck = renamed;
    renderHead();
    toast("Deck renamed");
  });

  $("#btn-options").addEventListener("click", async () => {
    const S = deck.settings || {};
    const whole = (key, label, help) => ({key, label, help, kind: "whole"});
    const steps = (key, label, help) => ({key, label, help, kind: "steps"});
    const specs = [
      whole("new_per_day", "New exercises a day", "How many never-studied exercises a day brings."),
      whole("reviews_per_day", "Reviews a day", "The most review answers a day asks for."),
      steps("learning_steps", "Learning steps (minutes)",
            "Separated by spaces, e.g. 1 10. Empty: a new exercise graduates at its first Good."),
      steps("relearning_steps", "Relearning steps (minutes)",
            "After an Again on a review. Empty: straight back to review."),
      whole("graduating_interval", "Graduating interval (days)", "After the last learning step."),
      whole("easy_interval", "Easy interval (days)", "A new exercise answered Easy."),
      whole("maximum_interval", "Maximum interval (days)", "No exercise waits longer than this."),
    ];
    const grid = el("div", "dk-options");
    const inputs = {};
    for (const spec of specs) {
      const v = S[spec.key];
      const shown = spec.kind === "steps" ? (Array.isArray(v) ? v.join(" ") : "")
                                         : (v === undefined || v === null ? "" : String(v));
      inputs[spec.key] = textInput(shown, {inputmode: spec.kind === "steps" ? "decimal" : "numeric"});
      grid.appendChild(field(spec.label, inputs[spec.key], spec.help));
    }
    const saved = await dialog({
      title: "Deck options", cls: "dk-options-modal", body: grid,
      hint: "How this deck schedules its exercises, as in Anki.",
      buttons: [CANCEL, {label: "Save options", primary: true, run: async () => {
        const settings = {};
        for (const spec of specs) {
          const raw = inputs[spec.key].value.trim();
          if (spec.kind === "whole") {
            if (!/^\d+$/.test(raw)) throw new Error(`${spec.label}: a whole number, please`);
            settings[spec.key] = Number(raw);
          } else {
            const parts = raw ? raw.split(/[\s,;]+/).filter(Boolean) : [];
            if (parts.some(p => !/^\d+(\.\d+)?$/.test(p) || !(Number(p) > 0)))
              throw new Error(`${spec.label}: minutes above zero, separated by spaces`);
            settings[spec.key] = parts.map(Number);
          }
        }
        return (await call(base, {method: "PATCH", json: {settings}})).deck;
      }}],
    });
    if (!saved || !saved.settings) return;
    deck = saved;
    renderHead();
    toast("Options saved");
  });

  $("#btn-delete-deck").addEventListener("click", async () => {
    const total = (deck.counts || {}).total || 0;
    const gone = await dialog({
      title: `Delete “${deck.name}”?`,
      hint: `Its ${plural(total, "exercise")} and their scheduling are moved to exercises/.trash/ ` +
            "in the Parseh folder, not erased: move the folder back to restore the deck.",
      buttons: [CANCEL, {label: "Delete deck", danger: true, run: () => call(base, {method: "DELETE"})}],
    });
    if (gone) location.href = BASE + "/";
  });

  // every exercise of the deck, to the cram page -- as "Cram exercises" sends
  // the picked ones, and by the same two ways
  // (the mobile layout's Cram all; what is picked in the list stays picked)
  $("#btn-practise").addEventListener("click", () => {
    const ids = items.map(it => it.id);
    if (!ids.length) return;
    let stored = false;
    try { sessionStorage.setItem(`parseh-cram:${deck.path}`, JSON.stringify(ids)); stored = true; }
    catch (e) { /* the address carries them instead */ }
    location.href = deckPage(deck) + "cram" + (stored ? "" : `?selected=${ids.join(",")}`);
  });

  renderHead();
  reload();
}

/* ================================================================ study */

function initStudy() {
  document.body.dataset.lang = lang().code;
  const deck = readScript($("#deck-json"), null);
  if (!deck || !deck.folder) { toast("This page came without its deck", true); return; }
  const base = deckApi(deck);
  const stage = $("#study-stage"), actions = $("#study-actions");
  const result = $("#study-result"), bar = $("#rating-bar"), done = $("#study-done");
  const btnCheck = $("#btn-check"), btnShow = $("#btn-show");
  const btnEdit = $("#btn-edit-card"), btnSkip = $("#btn-skip");
  // the mobile layout's Next (study.html): the rating the answer suggests
  const btnNext = $("#btn-next");
  const solution = $("#study-solution"), solutionSheet = $(".dk-sheet", solution);
  // where "studying needs the computer" is said, in the stage's place
  const cannot = $("#study-cannot");
  const skipped = new Set();          // left for later, this visit only
  // the exercise on screen: {item, intervals, run, ex, kind, revealed, result}
  let card = null;
  let rating = false, pollTimer = 0, loadSeq = 0;
  /* The control of the exercise a pointer last pressed, while it keeps the
     focus.  Enter right after a click on an answer checks the exercise.  On
     a control reached from the keyboard, Enter presses that control
     instead: it picks the answer, places the item, opens the footnote.
     :focus-visible cannot tell the two apart: Chromium turns it on at the
     keypress itself.  A card's player is such a control too. */
  let pointed = null;
  const CONTROL = "button, a[href], summary, [tabindex], audio, video";
  document.addEventListener("pointerdown", e => {
    const c = e.target.closest && e.target.closest(CONTROL);
    pointed = c && stage.contains(c) ? c : null;
  }, true);
  document.addEventListener("focusin", e => { if (e.target !== pointed) pointed = null; });

  function clearSolution() {
    solution.hidden = true;
    solutionSheet.replaceChildren();
  }

  /* A card's recordings, played as Anki plays them.  A flashcard shown plays
     the first recording of the side in view, once; turned over, the back's
     first.  A recording is a card's front-audio or back-audio (its 🔊,
     .ex-card-audio) or a recording line inside a jolly field (figure.audio,
     with a player of its own), whichever comes first on that side; one laid
     out with a clip plays only its window (app.js, on its play event).
     Whatever plays stops when the card is rated or skipped, or the next one
     comes.  A browser that lets no page make a sound before it has been
     clicked plays nothing: the card's 🔊 and players are still there.
     Enlarged (app.js openCardZoom), the card in view is the window's copy,
     drawn again from the card as it turns: that copy plays, where its own 🔊
     shows it playing and stops it, and the card it covers keeps still.
     A clip waits for the recording's length before it plays: a window that
     starts at or past the end has nothing to play and is not started at
     all (app.js would stop it again at once, but the card would have said
     it played).  A clip still waiting gives way to whatever plays first. */
  const ZOOMED = ".ex-zoom-overlay .ex-zoom-stage .ex-flashcard";
  const RECORDING = ".ex-card-audio audio, figure.audio audio";
  let waiting = null;
  function hush() {
    waiting = null;
    [...$$("audio, video", stage), ...$$("audio, video", solution),
     ...$$(".ex-zoom-overlay audio, .ex-zoom-overlay video")].forEach(m => {
      if (!m.paused) m.pause();
    });
  }
  document.addEventListener("play", e => {
    if (waiting && e.target !== waiting) waiting = null;
  }, true);
  function recordingOf(shown, side) {
    const own = shown && shown.ex && $(".ex-flashcard", shown.ex);
    const flash = own && ($(ZOOMED) || own);
    const face = flash && $(`:scope > .ex-card-${side}`, flash);
    // a selector list: the first match in the side's own order
    return face && $(RECORDING, face);
  }
  function playSide(shown, side) {
    const audio = recordingOf(shown, side);
    if (!audio || card !== shown) return;
    hush();
    const w = clipWindow(audio);
    const speak = () => {
      if (w && Number.isFinite(audio.duration) && w.start >= audio.duration) return;
      const playing = audio.play();
      if (playing && playing.catch) playing.catch(() => { /* not allowed yet, or gone */ });
    };
    if (!w || audio.readyState >= 1) { speak(); return; }
    waiting = audio;
    audio.addEventListener("loadedmetadata", () => {
      // meanwhile hushed, turned, enlarged, played by hand, or gone
      if (waiting !== audio || card !== shown || recordingOf(shown, side) !== audio) return;
      waiting = null;
      speak();
    }, {once: true});
  }

  /* The enlarged window shows a copy of the card on the stage.  One opened
     while the answer was on its way would be left over the next card drawn
     there, and taken for it: it closes (its own ✕, which gives the keys
     back to the page) whenever the stage is drawn again. */
  function closeZoom() {
    $$(".ex-zoom-overlay .ex-zoom-close").forEach(b => b.click());
  }

  /* A flashcard is turned by app.js -- a click on it, but not on a control
     inside it (its player, a link, its 🔊), Enter or Space on it, the
     enlarged copy, Show answer -- and the first turn is the answer shown,
     however it came. */
  let turning = null;
  function watchTurn(shown) {
    if (turning) turning.disconnect();
    turning = null;
    const flash = shown.kind === "flashcard" && $(".ex-flashcard", shown.ex);
    if (!flash) return;
    turning = new MutationObserver(() => {
      if (flash.classList.contains("flipped")) revealed(shown);
    });
    turning.observe(flash, {attributes: true, attributeFilter: ["class"]});
  }
  function revealed(shown) {
    if (card !== shown || shown.revealed) return;
    shown.revealed = true;
    btnShow.hidden = true;
    showBar("good");
    playSide(shown, "back");
  }

  $("#study-name").textContent = deck.name;
  document.title = `Study: ${deck.name} — Parseh exercises`;
  $("#btn-back-deck").href = deckPage(deck);
  $$(".dk-back").forEach(a => { a.href = deckPage(deck); });

  const queueOf = item => {
    const s = ((item || {}).schedule || {}).state;
    return s === "learning" || s === "relearning" ? "learning" : s === "review" ? "review" : "new";
  };

  /* THIS DECK MAY BE OUT ON THIS DEVICE (§19.10): then the cards come from
     what the computer handed over, not from the computer -- which may be
     asleep -- and every answer is kept here until it can be sent. */
  const out = () => deckOut(deck);
  function fromPack() {
    const card = packNext(deck, skipped);
    if (!card) return {done: true, item: null, html: null, intervals: null,
                       counts: packCounts(deck, skipped), next_due: null};
    return {done: false, item: card.item, html: card.html, intervals: card.intervals,
            counts: packCounts(deck, skipped), next_due: null};
  }

  /* Nothing on the stage but a sentence: the page put back to the state it
     is in between exercises, so that a rating bar or a Check left over from
     the card before cannot be pressed at what is no longer there. */
  function clearStage() {
    card = null;
    hush();
    closeZoom();
    clearSolution();
    done.hidden = true;
    if (cannot) cannot.hidden = true;
    bar.hidden = result.hidden = btnNext.hidden = true;
    stage.hidden = false;
    btnCheck.hidden = btnShow.hidden = btnEdit.hidden = btnSkip.hidden = true;
  }

  /* A DECK THAT WAS NOT TAKEN OUT CANNOT BE STUDIED AWAY FROM THE COMPUTER,
     AND THIS SAYS SO AT ONCE (§19.10, the owner's 8, 2026-09-23).

     Parseh schedules in one place on purpose: the computer chooses the next
     card and works out what each rating would cost, and no scheduler was
     ever written for the phone, because two of them drift apart and the
     learner pays for it.  So there is nothing here that could answer this
     page -- and nothing kept could have been.

     What it used to do was find that out the slow way: the ask went to a
     door nobody was going to answer, the worker waited out its patience, and
     the page ended on a fetch's complaint about a server.  What can be done
     instead is said here, in the place the waiting used to be: cram the deck
     now, and take it out next time the computer is there.

     AND THE WAY OUT HAS TO BE AN ADDRESS THE PHONE ACTUALLY HAS, which is
     the whole point of offering it here: this panel is only ever drawn with
     the computer out of reach.  It used to read `cram?all=1`, and what
     lib/offline.py keeps when a deck is kept is the BARE cram address -- it
     cannot keep anything else, since an address carrying a selection would
     be a different address for every selection and none of them the one that
     was kept.  The worker matches a page by its path AND its query
     (lib/sw.js, `ignoreSearch: false`), so the one link Parseh offered a
     learner stranded away from his computer missed the copy sitting on his
     phone by five characters and landed him on /m/offline/.

     So the whole deck is asked for in the FRAGMENT instead.  A fragment is
     never part of a request -- the browser does not send it and the Cache
     API leaves it out when it matches -- so `cram#all` is, to the worker and
     to the network alike, the very address that was kept, while the cram
     page can still read it off `location`.  The old query is still understood
     there, for a link somebody has kept or bookmarked. */
  function needsTheComputer() {
    clearStage();
    $("#study-counts").replaceChildren();
    actions.hidden = true;
    sayInstead(stage, cannot, "Studying needs the computer, and this deck is not out.",
      ["Parseh keeps one scheduler, on the computer, so that nothing drifts: a phone can only " +
       "study a deck the computer has handed over.",
       "Cramming asks nothing of it — every exercise, in random order, until each one is right, " +
       "with the scheduling left exactly as it is.",
       "And next time the computer is there, Take it out on the deck's page hands over the queue: " +
       "studying then works away from it until you give it back."],
      [["Cram this deck", deckPage(deck) + "cram#all", true],
       ["Back to the deck", deckPage(deck)]]);
  }

  async function load() {
    clearTimeout(pollTimer);
    const seq = ++loadSeq;
    const q = skipped.size ? "?skip=" + [...skipped].map(encodeURIComponent).join(",") : "";
    if (out()) {
      if (seq === loadSeq) show(fromPack());
      // whenever the computer can be reached, what was answered goes home
      sendAnswers(deck).catch(() => {});
      return;
    }
    // the deck is not out, and the computer is known to be away: there is
    // no point asking, and every second spent asking is a second the
    // learner spends watching a spinner that cannot end well
    if (computerAway()) { if (seq === loadSeq) needsTheComputer(); return; }
    try {
      const next = await call(base + "/next" + q);
      if (seq === loadSeq) show(next);
    } catch (e) {
      if (seq !== loadSeq) return;
      // it went away between the probe and the ask, or while this page was
      // open: the same thing is true, and the same thing is said
      if (e.away) { needsTheComputer(); return; }
      clearStage();
      stage.replaceChildren(el("p", "pv-status err", "Could not read the next exercise: " + e.message));
    }
  }

  /* An answer is saved when the learner has seen it come back: the bar is
     not shown before the exercise is checked, or the card turned over. */
  function show(next) {
    hush();
    closeZoom();
    // the deck may have come out since (Take it out, then straight here):
    // whatever was said in the stage's place is no longer true
    if (cannot) cannot.hidden = true;
    $("#study-counts").replaceChildren(studyCounts(next.counts, next.item ? queueOf(next.item) : ""));
    result.hidden = true;
    result.textContent = "";
    bar.hidden = true;
    btnNext.hidden = true;
    btnNext.disabled = false;
    clearSolution();
    pointed = null;
    if (next.done || !next.item) {
      card = null;
      stage.hidden = actions.hidden = true;
      stage.replaceChildren();
      done.hidden = false;
      $("#study-next-due").textContent = nextDueText(next.next_due, rolloverOf(deck));
      const left = $(".dk-skipped", done), again = $(".dk-unskip", done);
      left.hidden = again.hidden = skipped.size === 0;
      left.textContent = skipped.size ? `${plural(skipped.size, "exercise")} skipped this time.` : "";
      // the other side of a card answered today waits for the next day
      const held = $(".dk-held", done);
      held.hidden = !next.buried;
      held.textContent = next.buried
        ? `${plural(next.buried, "card")} held back until tomorrow: the other side of a card answered today.`
        : "";
      $("#btn-back-deck").focus();
      // a learning step that ends soon brings the next exercise by itself
      const t = Date.parse(next.next_due || "");
      if (Number.isFinite(t) && t - Date.now() <= 20 * 60e3)
        pollTimer = setTimeout(load, Math.max(1000, t - Date.now() + 1000));
      return;
    }
    done.hidden = true;
    stage.hidden = actions.hidden = false;
    stage.innerHTML = next.html || "";
    // one exercise, checked here: the page's own "Check exercises" goes
    $$(".exercise-correction, .ex-edit, .ex-to-deck", stage).forEach(x => x.remove());
    applyTypo(loadTypo(null));
    const run = bindExercises(stage);
    const ex = run.exercises[0] || null;
    const kind = !ex || $(".ex-invalid", ex) ? "invalid"
      : ex.dataset.primitive === "flashcard" ? "flashcard"
      : ex.dataset.scored === "1" ? "scored" : "invalid";
    card = {item: next.item, intervals: next.intervals || {}, run, ex, kind,
            revealed: false, result: null};
    watchTurn(card);
    btnCheck.hidden = kind !== "scored";
    btnShow.hidden = kind !== "flashcard";
    btnEdit.hidden = btnSkip.hidden = false;
    // held while an answer was on its way; this card's own from here (and Edit may take the focus)
    btnEdit.disabled = btnSkip.disabled = false;
    const keys = $(".dk-keys", actions);
    keys.textContent = kind === "scored" ? "Enter checks · 1–4 rate"
      : kind === "flashcard" ? "Enter shows the answer · 1–4 rate" : "";
    keys.hidden = kind === "invalid";
    RATINGS.forEach((r, i) => {
      const b = $(`[data-rating="${r}"]`, bar);
      const ivl = card.intervals[r] || "";
      $(".dk-ivl", b).textContent = ivl;
      b.setAttribute("aria-label", `${cap(r)}${ivl ? ": comes back in " + ivl : ""} (key ${i + 1})`);
      b.disabled = false;
    });
    if (stage.getBoundingClientRect().top < 0) stage.scrollIntoView({block: "start"});
    const first = kind === "scored" ? btnCheck : kind === "flashcard" ? btnShow : btnEdit;
    first.focus({preventScroll: true});
    if (kind === "flashcard") playSide(card, "front");
  }

  function showBar(focus) {
    bar.hidden = false;
    // Next, in the mobile layout: the rating focused here, said with the
    // interval it gives, in the place Check or Show answer had
    const ivl = card ? card.intervals[focus] || "" : "";
    btnNext.dataset.rating = focus;
    $(".dk-ivl", btnNext).textContent = cap(focus) + (ivl ? " · " + ivl : "");
    btnNext.setAttribute("aria-label", `Next: rated ${cap(focus)}${ivl ? ", back in " + ivl : ""}`);
    btnNext.classList.toggle("dk-wrong", focus === "again");
    btnNext.hidden = false;
    const b = $(`[data-rating="${focus}"]`, bar);
    // the card enlarged over the page keeps the focus while it is open
    if (b && !$(".ex-zoom-overlay")) b.focus({preventScroll: true});
    bar.scrollIntoView({block: "nearest"});
  }

  function check() {
    if (!card || card.kind !== "scored" || card.revealed) return;
    const good = card.run.judge(card.ex);
    card.revealed = true;
    card.result = good;
    // the answer stays as it was checked; the explanations below stay readable
    const body = $(".ex-body", card.ex);
    if (body) body.inert = true;
    btnCheck.hidden = true;
    result.textContent = good ? "Correct" : "Not quite";
    result.className = "dk-result " + (good ? "ok" : "err");
    result.hidden = false;
    showBar(good ? "good" : "again");
    // the mobile layout's answer bar keeps no place in the page to scroll
    // to: what the check said is brought into view instead
    if (isMobile()) result.scrollIntoView({block: "nearest", behavior: "smooth"});
    if (!good && ["matching", "placement"].includes(card.ex.dataset.primitive)) showSolution(card);
  }

  /* A choice marks the answer it wanted when it is judged; a match or a
     placement only marks what is right or wrong, and the exercise is locked
     now.  So the deck's solved form of it (the browse preview) goes under
     the result until the next exercise comes. */
  async function showSolution(checked) {
    let data;
    try {
      data = await call(`${base}/items/${checked.item.id}`);
    } catch (e) {
      if (card === checked) toast("Could not show the correct answer: " + e.message, true);
      return;
    }
    if (card !== checked) return;           // skipped, rated or edited meanwhile
    solutionSheet.innerHTML = data.html || "";
    // the card above already shows the explanations and the exercise's own
    // pictures and recordings, and is the one checked -- a second player
    // here would be a second copy of the same sound
    $$(".ex-edit, .ex-to-deck, .exercise-correction, .ex-explanation, .ex-image, .ex-audio, .footnotes",
       solutionSheet).forEach(x => x.remove());
    // its footnote clouds would repeat the ids of the card's own
    $$("[id]", solutionSheet).forEach(x => { x.id = "solution-" + x.id; });
    $$("[aria-describedby]", solutionSheet).forEach(x =>
      x.setAttribute("aria-describedby", "solution-" + x.getAttribute("aria-describedby")));
    if (!$(".exercise", solutionSheet)) return clearSolution();
    solution.hidden = false;
    applyTypo(loadTypo(null));              // the sheet takes the typography
    bindExercises(solutionSheet, {preview: true});
    if (!bar.hidden) bar.scrollIntoView({block: "nearest"});
  }

  function reveal() {
    if (!card || card.kind !== "flashcard" || card.revealed) return;
    const flash = $(".ex-flashcard", card.ex);
    if (flash) flash.click();             // bindExercises turns it; watchTurn notes it
  }

  /* One answer per card.  While it is on its way, Skip and Edit wait with
     the rating buttons, which stay held whatever comes back: the next card
     brings its own. */
  async function rate(r) {
    if (!card || rating || bar.hidden) return;
    rating = true;
    const rated = card;
    hush();
    $$("button", bar).forEach(b => { b.disabled = true; });
    btnSkip.disabled = btnEdit.disabled = btnNext.disabled = true;
    try {
      let data;
      try {
        if (out()) {
          // kept here, in the order it was answered; the computer replays it
          // through its own scheduler when it hears from this device
          const queue = answerQueue(deck);
          queue.push({item: rated.item.id, rating: r,
                      result: rated.kind === "scored" ? rated.result : null,
                      at: new Date().toISOString()});
          writeJsonKey(ANS_KEY(deck), queue);
          sendAnswers(deck).catch(() => {});
          loadSeq++;
          show(fromPack());
          return;
        }
        data = await call(base + "/review", {method: "POST", json: {
          item: rated.item.id, rating: r, result: rated.kind === "scored" ? rated.result : null,
          // the state the labels were worked out for: an exercise answered
          // since (in another tab, or before this page came back from
          // history) is refused, not scheduled a second time
          reps: rated.item.reps,
          // what comes next leaves out what was skipped, as /next does
          skip: [...skipped]}});
      } catch (e) {
        if (e.status === 409 && e.conflict === "reviewed") toast(cap(e.message));
        // a lost answer or a failure after the save cannot say which: the
        // deck can -- this exercise again if it was not saved, else the next
        else toast("The answer may not have been saved: " + e.message, true);
        await load();
        return;
      }
      if (!data.next || (!data.next.done && !data.next.html)) await load();
      else {
        loadSeq++;                  // a load() still on its way would draw over it
        show(data.next);
      }
    } finally {
      rating = false;
      btnSkip.disabled = btnEdit.disabled = false;
    }
  }

  btnCheck.addEventListener("click", check);
  btnShow.addEventListener("click", reveal);
  bar.addEventListener("click", e => {
    const b = e.target.closest("button[data-rating]");
    if (b) rate(b.dataset.rating);
  });
  btnNext.addEventListener("click", () => {
    if (btnNext.dataset.rating) rate(btnNext.dataset.rating);
  });
  btnSkip.addEventListener("click", () => {
    if (!card || rating) return;
    skipped.add(card.item.id);
    hush();
    // it is done with for this visit: a rating key pressed before the next
    // card arrives finds nothing to rate
    card = null;
    bar.hidden = btnNext.hidden = true;
    clearSolution();
    load();
  });
  $(".dk-unskip", done).addEventListener("click", () => {
    skipped.clear();
    load();
  });
  btnEdit.addEventListener("click", () => {
    if (!card || rating) return;
    const item = card.item;
    editExercise(deck, item, async markdown => {
      savedToast("Exercise saved: its scheduling is unchanged",
                 await saveEdited(deck, item, markdown));
      load();                    // the queue has not moved: the same exercise, as edited
    });
  });

  document.addEventListener("keydown", e => {
    if (!card || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
    if ($("#modal-root .modal-overlay")) return;         // the form or a dialog is open
    const t = e.target;
    if (t.closest && t.closest("input, textarea, select, [contenteditable]")) return;
    if (/^[1-4]$/.test(e.key)) {
      if (bar.hidden) return;
      e.preventDefault();
      rate(RATINGS[+e.key - 1]);
      return;
    }
    if (e.key !== "Enter") return;
    // a button of the page itself (Check, Skip, Edit, a rating) does what it
    // says; so does a control of the exercise reached from the keyboard
    const control = t.closest && t.closest(CONTROL);
    if (control && (!stage.contains(control) || control !== pointed)) return;
    if (card.kind === "scored" && !card.revealed) {
      // Enter just after a click on an answer: it checks, and does not
      // toggle the answer the click left the focus on
      e.preventDefault();
      check();
    } else if (card.kind === "flashcard" && !card.revealed) {
      e.preventDefault();
      reveal();
    }
  });

  load();
}

/* ================================================================ cram */

function initCram() {
  document.body.dataset.lang = lang().code;
  const deck = readScript($("#deck-json"), null);
  if (!deck || !deck.folder) { toast("This page came without its deck", true); return; }
  const base = deckApi(deck), stage = $("#cram-stage"), actions = $("#cram-actions");
  const done = $("#cram-done"), progress = $("#cram-progress");
  const result = $("#cram-result"), solution = $("#cram-solution");
  const solutionSheet = $(".dk-sheet", solution);
  // where "these exercises are not on this phone" is said, in the stage's place
  const cannot = $("#cram-cannot");
  const asked = new URLSearchParams(location.search);
  const carried = asked.get("selected") || "";
  // THE WHOLE DECK, without a selection carried from anywhere -- what Study
  // offers when the deck is not out and the computer is away.  It is asked
  // for in the fragment, because "#all" leaves the address itself exactly
  // the one lib/offline.py kept and the worker can answer with the computer
  // gone, which is the only state this link is ever offered in (see
  // needsTheComputer).  "?all=1" is read too: it is what the link used to
  // say, and a bookmark from then must not come up empty.
  const wantAll = asked.get("all") === "1" || location.hash === "#all";
  const back = deckPage(deck) + (carried ? `?selected=${carried}` : "");
  $$(".dk-back").forEach(a => { a.href = back; });
  // pool: the exercises of this practice, each once; order: the turns, a
  // wrong answer's exercise put at the end again
  let pool = [], order = [], index = 0, current = null;
  let turnObserver = null, waitingAudio = null;
  /* What this practice made of each exercise, by id, for the end to say:
     how many times it was answered wrong, whether its first answer was
     right, whether it was skipped -- and the order they first came up in,
     which is the order the end lists them in. */
  let tally = null;
  const fresh = () => ({wrong: new Map(), right: new Set(), seen: new Set(), skipped: new Set(),
                        shown: []});
  function judged(card, good) {
    const id = card.item.id;
    if (!tally.seen.has(id)) {
      tally.seen.add(id);
      if (good) tally.right.add(id);
    }
    if (!good) tally.wrong.set(id, (tally.wrong.get(id) || 0) + 1);
  }
  function stopMedia() {
    if (turnObserver) turnObserver.disconnect();
    turnObserver = null;
    waitingAudio = null;
    [...$$("audio, video", stage), ...$$("audio, video", solution)].forEach(m => {
      if (!m.paused) m.pause();
    });
    $$(".ex-zoom-overlay .ex-zoom-close").forEach(b => b.click());
  }
  function playSide(side) {
    const audio = $(`.ex-card-${side} audio`, stage);
    if (!audio) return;
    const window = clipWindow(audio);
    const play = () => {
      if (window && Number.isFinite(audio.duration) && window.start >= audio.duration) return;
      const promise = audio.play();
      if (promise && promise.catch) promise.catch(() => { /* browser needs a click first */ });
    };
    if (!window || audio.readyState >= 1) { play(); return; }
    waitingAudio = audio;
    audio.addEventListener("loadedmetadata", () => {
      if (waitingAudio !== audio) return;
      waitingAudio = null;
      play();
    }, {once: true});
  }
  /* A practice of these exercises, in random order, from the start: the
     selection, and at the end "Shuffle and repeat" (the same ones) or
     "Cram these again" (the wrong ones, or the skipped). */
  function start(set) {
    pool = set;
    tally = fresh();
    order = [...pool];
    for (let i = order.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [order[i], order[j]] = [order[j], order[i]];
    }
    index = 0;
    show();
  }
  function show() {
    stopMedia();
    result.hidden = true;
    result.textContent = "";
    solution.hidden = true;
    solutionSheet.replaceChildren();
    if (index >= order.length) {
      current = null;
      stage.hidden = actions.hidden = true;
      done.hidden = false;
      progress.textContent = plural(pool.length, "exercise");
      summarise();
      return;
    }
    const card = order[index];
    if (!tally.shown.includes(card)) tally.shown.push(card);
    stage.hidden = actions.hidden = false;
    done.hidden = true;
    progress.textContent = `${index + 1} of ${order.length}`;
    stage.innerHTML = card.html;
    $$(".exercise-correction, .ex-edit, .ex-to-deck", stage).forEach(x => x.remove());
    applyTypo(loadTypo(null));
    const run = bindExercises(stage);
    const ex = run.exercises[0] || null;
    const kind = !ex || $(".ex-invalid", ex) ? "invalid"
      : ex.dataset.primitive === "flashcard" ? "flashcard"
      : ex.dataset.scored === "1" ? "scored" : "invalid";
    current = {card, run, ex, kind, checked: false};
    const flash = $(".ex-flashcard", stage);
    if (flash) {
      turnObserver = new MutationObserver(() => {
        const flipped = flash.classList.contains("flipped");
        $("#cram-show").disabled = flipped;
        $("#cram-wrong").hidden = $("#cram-correct").hidden = !flipped;
        playSide(flipped ? "back" : "front");
      });
      turnObserver.observe(flash, {attributes: true, attributeFilter: ["class"]});
    }
    $("#cram-check").hidden = kind !== "scored";
    $("#cram-show").hidden = kind !== "flashcard";
    $("#cram-show").disabled = false;
    $("#cram-wrong").hidden = $("#cram-correct").hidden = true;
    $("#cram-next").hidden = kind !== "invalid";
    // until it is answered; an exercise that cannot be shown has Next
    $("#cram-skip").hidden = kind === "invalid";
    // as studying does: a long exercise, or the end's lists, may have left
    // the page scrolled past where the next one starts
    if (stage.getBoundingClientRect().top < 0) stage.scrollIntoView({block: "start"});
    if (kind === "flashcard") playSide("front");
    $("#cram-next").textContent = index === order.length - 1 ? "Finish" : "Next exercise";
  }

  /* ---- the end: how it went, and what to look at again ---- */
  const wrongList = $("#cram-wrong-list"), skippedList = $("#cram-skipped-list");
  let listed = 0;                     // gives each solved sheet's ids their own prefix
  const TIMES = ["", "once", "twice"];
  function summarise() {
    const inTurn = list => tally.shown.filter(card => list.has(card.item.id));
    const wrong = inTurn(tally.wrong), skipped = inTurn(tally.skipped);
    const right = pool.filter(card => tally.right.has(card.item.id)).length;
    const parts = [];
    if (right) parts.push(`${right} right the first time`);
    if (wrong.length) parts.push(`${wrong.length} wrong at least once`);
    if (skipped.length) parts.push(`${skipped.length} skipped`);
    $("#cram-tally").textContent = wrong.length || skipped.length || right !== pool.length
      ? `${plural(pool.length, "exercise")}: ${parts.join(", ")}.`
      : pool.length === 1 ? "Right the first time." : `All ${pool.length} right the first time.`;
    // a practice ends only once each exercise it put back has been answered
    // right, or skipped: which of the two, the line says
    fillList(wrongList, wrong, card => {
      const n = tally.wrong.get(card.item.id);
      return "wrong " + (TIMES[n] || `${n} times`) +
        (tally.skipped.has(card.item.id) ? ", then skipped" : ", then right");
    });
    fillList(skippedList, skipped, () => "");
  }
  function fillList(section, cards, says) {
    section.hidden = !cards.length;
    $(".dk-cram-items", section).replaceChildren(...cards.map(card => {
      const it = card.item;
      const li = el("li", "dk-cram-entry");
      const b = el("button", "dk-cram-item");
      b.type = "button";
      b.title = "Show it solved";
      b.setAttribute("aria-expanded", "false");
      const excerpt = el("span", "dk-excerpt", it.excerpt || "(no text)");
      excerpt.dir = "auto";
      b.append(el("span", "ex-kicker", it.label || it.subtype || "Exercise"), excerpt);
      const meta = says(card);
      if (meta) b.append(el("span", "dk-cram-meta", meta));
      const box = el("div", "dk-cram-solved");
      box.hidden = true;
      b.addEventListener("click", () => toggleSolved(b, box, it));
      li.append(b, box);
      return li;
    }));
    $('[data-x="again"]', section).onclick = () => start(cards);
  }
  /* An exercise of the list, solved, under it -- as the deck's list shows
     one (its preview) -- and put away again at the next click. */
  async function toggleSolved(button, box, it) {
    const open = box.hidden;
    button.setAttribute("aria-expanded", String(open));
    box.hidden = !open;
    if (!open || box.firstChild) return;
    box.replaceChildren(el("p", "pv-status", "Rendering…"));
    let data;
    try { data = await call(`${base}/items/${it.id}`); }
    catch (e) {
      box.replaceChildren(el("p", "pv-status err", "Could not show it: " + e.message));
      return;
    }
    const sheet = el("div", "sheet dk-sheet");
    sheet.dataset.lang = deck.lang;
    sheet.innerHTML = data.html || "";
    $$(".ex-edit, .ex-to-deck, .exercise-correction", sheet).forEach(x => x.remove());
    // several of them on one page: their footnotes' ids each their own
    const mark = `cram-done-${++listed}-`;
    $$("[id]", sheet).forEach(x => { x.id = mark + x.id; });
    $$("[aria-describedby]", sheet).forEach(x =>
      x.setAttribute("aria-describedby", mark + x.getAttribute("aria-describedby")));
    box.replaceChildren(sheet);
    applyTypo(loadTypo(null));
    bindExercises(sheet, {preview: true});
  }
  async function showSolution(checked) {
    let data;
    try { data = await call(`${base}/items/${checked.card.item.id}`); }
    catch (e) {
      if (current === checked) toast("Could not show the correct answer: " + e.message, true);
      return;
    }
    if (current !== checked) return;
    solutionSheet.innerHTML = data.html || "";
    $$(".ex-edit, .ex-to-deck, .exercise-correction, .ex-explanation, .ex-image, .ex-audio, .footnotes",
       solutionSheet).forEach(x => x.remove());
    $$("[id]", solutionSheet).forEach(x => { x.id = "cram-solution-" + x.id; });
    $$("[aria-describedby]", solutionSheet).forEach(x =>
      x.setAttribute("aria-describedby", "cram-solution-" + x.getAttribute("aria-describedby")));
    if (!$(".exercise", solutionSheet)) return;
    solution.hidden = false;
    applyTypo(loadTypo(null));
    bindExercises(solutionSheet, {preview: true});
  }
  $("#cram-check").addEventListener("click", () => {
    if (!current || current.kind !== "scored" || current.checked) return;
    const good = current.run.judge(current.ex);
    current.checked = true;
    judged(current.card, good);
    if (!good) order.push(current.card);
    const body = $(".ex-body", current.ex);
    if (body) body.inert = true;
    // answered: there is nothing to skip any more, only to go on
    $("#cram-check").hidden = $("#cram-skip").hidden = true;
    result.textContent = good ? "Correct" : "Not quite";
    result.className = "dk-result " + (good ? "ok" : "err");
    result.hidden = false;
    progress.textContent = `${index + 1} of ${order.length}`;
    $("#cram-next").hidden = false;
    $("#cram-next").textContent = index === order.length - 1 ? "Finish" : "Next exercise";
    // as studying does: the mobile layout's bar keeps no place in the page
    if (isMobile()) result.scrollIntoView({block: "nearest", behavior: "smooth"});
    if (!good && ["matching", "placement"].includes(current.ex.dataset.primitive))
      showSolution(current);
  });
  $("#cram-show").addEventListener("click", () => {
    const flash = $(".ex-flashcard", stage);
    if (flash && !flash.classList.contains("flipped")) flash.click();
    $("#cram-show").disabled = true;
  });
  function gradeFlash(good) {
    if (!current || current.kind !== "flashcard" || current.checked ||
        !$(".ex-flashcard.flipped", stage)) return;
    current.checked = true;
    judged(current.card, good);
    if (!good) order.push(current.card);
    index++;
    show();
  }
  $("#cram-wrong").addEventListener("click", () => gradeFlash(false));
  $("#cram-correct").addEventListener("click", () => gradeFlash(true));
  /* Skip: the exercise is left unanswered and does not come back in this
     practice -- nor does the turn a wrong answer earlier put back for it --
     and the end names it among the skipped. */
  $("#cram-skip").addEventListener("click", () => {
    if (!current || current.checked) return;
    const id = current.card.item.id;
    tally.skipped.add(id);
    order = order.filter((card, i) => i <= index || card.item.id !== id);
    index++;
    show();
  });
  $("#cram-next").addEventListener("click", () => {
    // an exercise that could not be shown was not answered: it is said so
    // at the end, with the skipped ones
    if (current && current.kind === "invalid") tally.skipped.add(current.card.item.id);
    index++;
    show();
  });
  $("#cram-again").addEventListener("click", () => start(pool));

  /* ---- WHERE THE EXERCISES COME FROM (the owner's 8, 2026-09-23) ----

     The exercises are rendered by the computer -- there is nothing on a
     phone that could render one -- and until today the ask that did it was a
     POST carrying the picked ids.  A service worker cannot cache a POST at
     all, whatever is kept: so a phone away from the computer had nothing to
     answer this page with, and it sat on "Loading exercises…" until it was
     closed.  Keeping a deck could never have made cramming work, however
     faithfully everything else was kept.

     Beside the POST there is now a GET at the same address which renders the
     WHOLE deck -- every exercise, nothing chosen, nothing in the address to
     vary -- and that is precisely what makes it keepable.  Keeping a deck
     keeps it, with the pictures and the recordings those exercises ask for
     (deckroutes api_cram_all, lib/offline.py deck()).

     Which of the two is asked: with the computer there, the POST, because it
     alone knows about an exercise added a minute ago and it renders only
     what was picked.  With the computer away -- or when the POST goes
     unanswered -- the GET, whose copy is on this phone; the picks are then
     taken out of the whole deck here.  "Cram all" of the whole deck asks the
     GET either way: it is the same question. */
  let ids = [];
  try { ids = JSON.parse(sessionStorage.getItem(`parseh-cram:${deck.path}`) || "[]"); }
  catch (e) { /* unavailable or invalid selection */ }
  if ((!Array.isArray(ids) || !ids.length) && carried)
    ids = carried.split(",").filter(id => /^[0-9a-f]{12}$/.test(id));
  if (!wantAll && (!Array.isArray(ids) || !ids.length)) {
    stage.replaceChildren(el("p", "pv-status", isMobile()
      ? "On the deck's page, choose Cram all, or pick exercises and cram them."
      : "Select exercises in Browse, then choose Cram exercises."));
    return;
  }

  // the picked exercises out of the whole deck's cards, in the order they
  // were picked, and which of the picks that copy does not hold
  function pickOut(cards) {
    const byId = new Map((cards || []).filter(c => c && c.item).map(c => [c.item.id, c]));
    if (wantAll) return {cards: (cards || []).filter(c => c && c.item), missing: []};
    return {cards: ids.map(id => byId.get(id)).filter(Boolean),
            missing: ids.filter(id => !byId.has(id))};
  }

  /* IS THE WHOLE DECK'S ANSWER ALREADY ON THIS PHONE?  Asked of the caches
     themselves, not of a record: it decides how long the ask below is worth
     waiting for, and the honest answer to that is what is actually here. */
  async function copyHere() {
    try {
      if (!window.caches) return false;
      return !!(await caches.match(BASE + base + "/cram", {ignoreVary: true}));
    } catch (e) { return false; }
  }

  async function exercises() {
    if (!wantAll && !computerAway()) {
      // with the whole deck on this phone there is no reason to wait out a
      // computer that is not answering: the copy is as good for cramming,
      // and the picks are taken out of it here
      const spare = await copyHere();
      try {
        const data = await call(base + "/cram", {method: "POST", json: {ids},
                                                 patience: spare ? 2500 : 0});
        return {cards: data.cards || [], missing: [], from: "computer"};
      } catch (e) {
        // only the computer being out of reach is worth asking the copy
        // for: a deck that refused this ask would refuse the other one too
        if (!e.away) throw e;
      }
    }
    const data = await call(base + "/cram");
    return Object.assign(pickOut(data.cards),
                         {from: "phone", held: (data.cards || []).length});
  }

  /* Nothing to show, and why -- with the way to mend it, which for a deck
     that was never kept is one press on the computer. */
  function nothingToCram(from, missing, held) {
    if (from === "computer") {
      stage.replaceChildren(el("p", "pv-status", "No selected exercises are available."));
      return;
    }
    // the copy answered and holds nothing: an empty deck, not a short one
    if (!held) {
      sayInstead(stage, cannot, "This deck has no exercises.",
        ["Exercises are added on the computer, in the browser interface."],
        [["Back to the deck", back, true]]);
      return;
    }
    sayInstead(stage, cannot,
      missing.length === 1 ? "That exercise is not on this phone."
                           : "These exercises are not on this phone.",
      ["Parseh's computer cannot be reached, and what is kept here does not hold them.",
       "Open this deck with the computer there and press Keep on this phone: that puts every " +
       "exercise, with its pictures and its recordings, here — and cramming then works anywhere."],
      [["Back to the deck", back, true]]);
  }

  exercises().then(({cards, missing, from, held}) => {
    if (!cards.length) { nothingToCram(from, missing, held); return; }
    // some of them here and some not: cram what there is, and say what is
    // short rather than quietly showing fewer exercises than were picked
    if (missing.length)
      toast(`${plural(missing.length, "exercise")} of the selection ${missing.length === 1 ? "is" : "are"} ` +
            "not on this phone: the rest are here", true);
    start(cards);
  }).catch(e => {
    if (!e.away) { stage.replaceChildren(el("p", "pv-status err", e.message)); return; }
    sayInstead(stage, cannot, "This deck is not kept on this phone.",
      ["Parseh's computer cannot be reached, and cramming needs the exercises themselves, " +
       "which only the computer can render.",
       "Open this deck with the computer there and press Keep on this phone: every exercise, " +
       "its pictures and its recordings come here, and cramming works away from it afterwards."],
      [["Back to the deck", back, true]]);
  });
}



/* ================= A DECK TAKEN OUT (TO-DO §19.10) =================
   Studying writes, and a phone away from the computer cannot write there.  So
   a phone that wants to study on a train TAKES THE DECK OUT: the computer
   hands over the whole queue -- every card that is due, in its order,
   rendered, with the four interval labels IT worked out -- and will not study
   or edit that deck until it comes back.  Cramming on the computer is
   untouched: cram never schedules.

   The phone shows the cards it was handed, records what was answered, and
   sends the answers whenever the computer can be reached; the computer
   replays them through its own scheduler, in the order they were given.  That
   is why there is no scheduler here: one scheduler, no drift.

   The deck stays the phone's until "Give it back", so it can be studied day
   after day without taking it out again (the owner's choice, 2026-09-22). */
const OUT_KEY = d => "parseh_deck_out:" + d.folder + "/" + d.slug;
const ANS_KEY = d => "parseh_deck_answers:" + d.folder + "/" + d.slug;
const DEV_KEY = "parseh_device";

function deviceId() {
  let id = null;
  try { id = localStorage.getItem(DEV_KEY); } catch (e) {}
  if (!id) {
    id = "d" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
    try { localStorage.setItem(DEV_KEY, id); } catch (e) {}
  }
  return id;
}
// the phone names itself, as lib/prefs.js does for the reading place: nothing
// to type, and nothing that leaves this machine
function deviceName() {
  const ua = navigator.userAgent || "";
  const what = /Android/i.test(ua) ? (/Mobile/.test(ua) ? "Android phone" : "Android tablet")
             : /iPhone/i.test(ua) ? "iPhone" : /iPad/i.test(ua) ? "iPad"
             : /Windows/i.test(ua) ? "Windows computer"
             : /Macintosh|Mac OS/i.test(ua) ? "Mac"
             : /CrOS/i.test(ua) ? "Chromebook"
             : /Linux/i.test(ua) ? "Linux computer" : "this device";
  const who = /Edg\//.test(ua) ? "Edge" : /OPR\//.test(ua) ? "Opera"
            : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome"
            : /Safari\//.test(ua) ? "Safari" : "";
  return who ? what + " · " + who : what;
}
function readJsonKey(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || "null") || fallback; }
  catch (e) { return fallback; }
}
function writeJsonKey(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch (e) { /* private browsing: the deck simply is not out */ }
}
// what this phone holds of this deck, or null
const deckOut = deck => readJsonKey(OUT_KEY(deck), null);
const answerQueue = deck => readJsonKey(ANS_KEY(deck), []) || [];

/* keeping the deck's own pages and media, so it opens with the computer away
   (lib/keep.js does the same for a book; here the worker is asked straight) */
function keepDeck(deck, urls, version, digests) {
  const w = navigator.serviceWorker && navigator.serviceWorker.controller;
  if (!w) return Promise.resolve(false);
  return new Promise(done => {
    // THIS deck's answer, and no other's: a book kept in the background ends
    // with a {kept} sent to every page (lib/sw.js, settle), and taken for this
    // deck's it would check the deck out with its copy only half made
    const hear = e => {
      if (!e.data || !e.data.kept || e.data.kept !== deckPage(deck)) return;
      navigator.serviceWorker.removeEventListener("message", hear);
      done(true);
    };
    navigator.serviceWorker.addEventListener("message", hear);
    // with what the computer said each file was, which the worker writes on
    // the copy it keeps (lib/sw.js, `stamped`): it is how the keep check
    // tells a file Parseh updated since from one that is broken
    w.postMessage({keep: {id: deckPage(deck), urls, version, digests: digests || {}}});
    setTimeout(() => done(false), 10 * 60 * 1000);
  });
}
/* The registry lib/keep.js keeps beside the worker's caches: the same shape,
   so that the deck page's Change what is kept and Remove from this phone see
   a deck kept from here exactly as they see a book kept from there.

   NO `notes` FIELD, and that is the whole of what it says.  A book and a
   video have a notes mount beside them, and lib/keep.js writes `notes: true`
   or `notes: false` for one so that Keep it again knows whether to fetch
   them and /m/kept/ can say whether they came (TO-DO §0, the notes kept with
   their book).  A deck has no such mount and never will: written false here
   it would draw a "without its notes" tag on the kept page offering a thing
   that does not exist, so the field is left out, which is how both readers
   of the registry say "this cannot have any". */
function rememberKept(deck, rec, files) {
  const reg = readJsonKey("parseh_kept", {}) || {};
  reg[deckPage(deck)] = {title: deck.name || deck.slug, page: deckPage(deck), kind: "deck",
                         version: rec.version || "", bytes: rec.bytes || 0,
                         at: Date.now() / 1000,
                         files: files || (rec.small || []).length,
                         media: (rec.media || []).map(m => m.url)};
  writeJsonKey("parseh_kept", reg);
}
const deckIsKept = deck => !!(readJsonKey("parseh_kept", {}) || {})[deckPage(deck)];

/* KEEPING A DECK AND TAKING IT OUT ARE TWO THINGS (the owner's 8 and 9,
   2026-09-23).  Keeping is the COPY -- the deck's pages, its exercises and
   their media on this phone -- which makes it open and be crammed with the
   computer away.  TAKING IT OUT is the RIGHT TO STUDY it away: the computer
   hands over the queue and will not study or edit the deck itself until it
   comes back.  The second is no use without the first, so taking a deck out
   keeps it as part of the same press, saying so while it does it.

   And giving it back leaves the copy alone.  It used to delete it, which
   meant that coming home from a journey cost the whole deck again the next
   time; the copy is a good thing to have whether the deck is out or not, and
   Remove from this phone is what takes it off (lib/keep.js). */
async function keepDeckNow(deck) {
  const made = await call(deckApi(deck) + "/__offline");
  const urls = (made.small || []).map(x => x.url)
    .concat((made.shared || []).map(x => x.url))
    .concat((made.media || []).map(x => x.url));
  const digests = {};
  for (const x of [].concat(made.small || [], made.shared || [], made.media || []))
    if (x && x.url && x.digest) digests[x.url] = x.digest;
  await keepDeck(deck, urls, made.version, digests);
  rememberKept(deck, made, urls.length);
  return made;
}

async function takeDeckOut(deck, saying) {
  if (!deckIsKept(deck)) {
    if (saying) saying("Keeping it on this phone first…");
    await keepDeckNow(deck);
  }
  const rec = await call(deckApi(deck) + "/checkout", {method: "POST",
    json: {device: deviceName(), id: deviceId()}});
  writeJsonKey(OUT_KEY(deck), {id: deviceId(), device: deviceName(), since: rec.checkout.since,
                               cards: (rec.pack || {}).cards || [], counts: (rec.pack || {}).counts || {},
                               at: Date.now() / 1000});
  return rec;
}

async function sendAnswers(deck) {
  const queue = answerQueue(deck);
  if (!queue.length) return {applied: 0};
  // `evenAway`: this is the phone reconciling by itself, not a thumb asking
  // an offline page to write -- a journey's answers must not be stranded
  // until every page has been closed and opened again (see `call`)
  const out = await call(deckApi(deck) + "/answers", {method: "POST", evenAway: true,
    json: {id: deviceId(), answers: queue}});
  writeJsonKey(ANS_KEY(deck), []);
  if (out.taken_back) {
    writeJsonKey(OUT_KEY(deck), null);
    toast("This deck was taken back on the computer: what was answered here could not be " +
          "applied, and the computer lists it", true);
  } else if ((out.refused || []).length) {
    toast(out.refused.length + " of the answers could not be applied — the computer lists them", true);
  }
  return out;
}

async function giveDeckBack(deck) {
  try { await sendAnswers(deck); } catch (e) { /* said below */ }
  await call(deckApi(deck) + "/return", {method: "POST", json: {id: deviceId()}});
  writeJsonKey(OUT_KEY(deck), null);
  // the kept copy stays: giving the deck back is not taking it off the phone
  // (the owner's 9, 2026-09-23).  Remove from this phone does that, and says
  // so; and it refuses while the deck is out (lib/keep.js, heldBack).
}

/* studying from what the computer handed over: the next card of the pack that
   has not been answered (or skipped), and "again" brings a card back at the
   end, as cramming does */
function packNext(deck, skipped) {
  const out = deckOut(deck);
  if (!out) return null;
  const answered = new Map();
  answerQueue(deck).forEach(a => answered.set(a.item, (answered.get(a.item) || 0) + 1));
  const again = new Set(answerQueue(deck).filter(a => a.rating === "again").map(a => a.item));
  const cards = out.cards || [];
  for (const c of cards) {
    const id = c.item.id;
    if (skipped.has(id)) continue;
    if (!answered.has(id)) return c;
  }
  // the ones answered "again" come round again, once each
  for (const c of cards) {
    const id = c.item.id;
    if (skipped.has(id) || !again.has(id)) continue;
    const times = answerQueue(deck).filter(a => a.item === id);
    if (times.length && times[times.length - 1].rating === "again") return c;
  }
  return null;
}
function packCounts(deck, skipped) {
  const out = deckOut(deck) || {};
  const answered = new Set(answerQueue(deck).map(a => a.item));
  const left = (out.cards || []).filter(c => !answered.has(c.item.id) && !skipped.has(c.item.id));
  const counts = Object.assign({}, out.counts || {});
  ["new", "learning", "review"].forEach(k => { if (typeof counts[k] !== "number") counts[k] = 0; });
  const seen = left.length;
  return Object.assign({}, counts, {left: seen});
}

/* WHAT WAS ANSWERED AWAY GOES HOME BY ITSELF (§19.10).  A phone may answer
   on a train and put the deck away; the next time any deck page is opened --
   or the browser says it is online again -- whatever is still queued is sent.
   Nothing waits for the learner to remember. */
function flushAnswersSoon() {
  const decksOut = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith("parseh_deck_answers:")) continue;
      const path = k.slice("parseh_deck_answers:".length);
      const [folder, slug] = path.split("/");
      if (!folder || !slug) continue;
      const queue = readJsonKey(k, []);
      if ((queue || []).length) decksOut.push({folder, slug, path});
    }
  } catch (e) { return; }
  decksOut.forEach(d => { sendAnswers(d).catch(() => {}); });
}

/* ---------------- the scroll strip (TO-DO §4.16) ----------------
   Held sideways, studying and cramming put their buttons in a column down
   the right of the screen (static/mobile.css), with Skip at its top and the
   answer's button at its foot -- where the thumb is.  That left a long
   exercise to be scrolled by reaching back across the screen for the text.

   So the EMPTY stretch of that column, between the buttons, scrolls the
   exercise: a finger dragged up or down there moves the page, one pixel of
   page to one pixel of finger, and leaves it flying on when the finger is
   lifted -- slowing down as a phone's own scrolling does, and stopping dead
   at the top and the bottom.  The buttons do not move, and a tap on one is
   still a tap: nothing here touches them, since the strip is its own box
   between them, and it alone says touch-action:none.

   The grip in its middle is there only while there is something to scroll. */
function bindScrollStrip() {
  const strips = Array.from(document.querySelectorAll(".dk-strip"));
  if (!strips.length) return;
  const scroller = document.scrollingElement || document.documentElement;
  const room = () => Math.max(0, scroller.scrollHeight - window.innerHeight);
  // the grip says whether there is anything to scroll -- asked again
  // whenever an exercise is drawn, the screen turns, or the page is resized
  const look = () => {
    const can = room() > 8 && getComputedStyle(strips[0]).display !== "none";
    strips.forEach(s => s.classList.toggle("dk-can-scroll", can));
  };
  let at = 0, last = 0, when = 0, v = 0, flying = 0, strip = null;
  const stop = () => { if (flying) cancelAnimationFrame(flying); flying = 0; };
  const move = by => {
    const was = window.scrollY;
    window.scrollTo(0, Math.max(0, Math.min(room(), was + by)));
    return window.scrollY !== was;          // false at either end
  };
  const fly = () => {
    // a phone's own deceleration, near enough: a fifteenth off each frame,
    // and done when it is slower than a pixel every two frames
    v *= 0.94;
    if (Math.abs(v) < 0.4 || !move(-v)) { stop(); if (strip) strip.classList.remove("dk-dragging"); return; }
    flying = requestAnimationFrame(fly);
  };
  strips.forEach(s => {
    s.addEventListener("touchstart", e => {
      if (e.touches.length !== 1) return;
      stop();
      strip = s;
      at = last = e.touches[0].clientY;
      when = e.timeStamp || Date.now();
      v = 0;
      s.classList.add("dk-dragging");
    }, {passive: true});
    s.addEventListener("touchmove", e => {
      if (strip !== s || e.touches.length !== 1) return;
      const y = e.touches[0].clientY, t = e.timeStamp || Date.now();
      const dy = y - last, dt = Math.max(1, t - when);
      // the finger goes down, the page goes up: the text follows the finger,
      // as it does when the exercise itself is dragged
      move(-dy);
      v = dy / dt * 16;                     // pixels a frame, for the fling
      last = y;
      when = t;
      e.preventDefault();                   // the column itself never moves
    }, {passive: false});
    const let_go = () => {
      if (strip !== s) return;
      strip = null;
      if (Math.abs(v) > 1.2) { flying = requestAnimationFrame(fly); return; }
      s.classList.remove("dk-dragging");
    };
    s.addEventListener("touchend", let_go, {passive: true});
    s.addEventListener("touchcancel", let_go, {passive: true});
  });
  window.addEventListener("resize", look);
  window.addEventListener("orientationchange", look);
  if (window.MutationObserver) {
    const watch = new MutationObserver(() => look());
    const stage = $("#study-stage") || $("#cram-stage");
    if (stage) watch.observe(stage, {childList: true, subtree: true});
  }
  look();
  setTimeout(look, 300);
  window.ParsehStrip = {look: look};
}

/* ---------------- boot ---------------- */

// the shared theme (and, on the deck pages, the target script's size)
applyTypo(loadTypo(null));
bindMode();
bindStop();
if (PAGE === "decks") initDecks();
else if (PAGE === "deck") initDeck();
else if (PAGE === "study") initStudy();
else initCram();
// the empty stretch of the sideways column scrolls the exercise (§4.16)
if (PAGE === "study" || PAGE === "cram") bindScrollStrip();
// and whatever was answered while the computer was away goes home (§19.10)
flushAnswersSoon();
addEventListener("online", flushAnswersSoon);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") flushAnswersSoon();
});
})();
