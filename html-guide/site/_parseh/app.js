// SPDX-License-Identifier: GPL-3.0-or-later
/* exlex studio — client logic for library, reading view, editor, prompt. */
"use strict";

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
const PAGE = document.body.dataset.page;
const DOC_ID = document.body.dataset.docId || "";
// the prefix the studio is served under: "" on its own, "/studio" inside
// Parseh.  Every absolute URL the script builds goes through it.
const BASE = document.body.dataset.base || "";

// Framed -- this document is a note opened over a book or a video -- Escape
// belongs to the page that opened it, which cannot hear a key pressed in
// here.  Only when nothing in this document has already claimed it.
if (window.parent !== window) {
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || e.defaultPrevented) return;
    try { window.parent.postMessage({ parseh: "close-note" }, location.origin); }
    catch (_) {}
  });
}

/* The document's target language (docs/languages.md): the page embeds
   the registry record (`Lang.as_json()`) as #doc-lang and the registry
   list (for chips, badges and the prompt select) as #langs-json.  Nothing
   here names a language: direction, labels, whether there is a reading
   (kana) or a vertical mode, the alternate face -- all come from the
   record.  The editor replaces LANG when a preview reports another
   `target:` in the front matter. */
function readJson(id, fallback) {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try { return JSON.parse(el.textContent) || fallback; } catch (e) { return fallback; }
}
const LANGS = readJson("langs-json", []);
// what a page without a record (the library, the prompt) falls back to:
// the toolbox's first language, described minimally
let LANG = readJson("doc-lang", null);
const FALLBACK_LANG = {code: "fa", name: "Persian", native: "فارسی", dir: "rtl",
                       script: "arabic", reading: false, vertical: false,
                       translit_label: "transliteration", reading_label: null,
                       fonts: {alt_key: null}};
function lang() { return LANG || FALLBACK_LANG; }
function langAttrs(el) {
  el.setAttribute("lang", lang().code);
  el.setAttribute("dir", lang().dir);
}
function capital(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }
/* The toolbox's one case fold (`languages.fold`), spliced in by the server
   from `languages.FOLD_JS` so it is written once and the browser narrows a
   list exactly as store.py does.  Every comparison of typed text with
   target text goes through it: toLowerCase alone spells Turkish's İ as
   i + a combining dot, and a filter keyed on that finds nothing a Turk
   can type.  For matching only -- never for what is stored or shown. */
const foldCase = s => (s || '').normalize('NFC').replace(/[\u0130\u0131]/g, 'i').replace(/\u0307/g, '').toLowerCase();
/* the default size of the target script relative to the Latin: the
   Arabic-script faces are small on the x-height and were always set
   "very big"; CJK glyphs fill their em box; a Latin-script target is the
   same alphabet as the prose (texgen.default_scale is the PDF twin) */
function defaultScale(L) {
  if (L.script === "latin") return 1.0;
  if (L.script === "arabic") return 1.52;
  return 1.2;
}
/* the shared language preference of the toolbox (`parseh_lang`: "all" or
   a code), read directly -- parseh.js is not loaded in the studio */
function sharedLang() {
  try { return localStorage.getItem("parseh_lang") || "all"; } catch (e) { return "all"; }
}
function setSharedLang(v) {
  try { localStorage.setItem("parseh_lang", v); } catch (e) { /* private mode */ }
}

/* The library's sort order, remembered the way the language is: coming back
   to the page and finding it sorted by something else is the page forgetting
   what the reader chose.  Only the three the menu offers are accepted, so a
   stale or hand-written value cannot leave the list sorted by nothing. */
const SORTS = ["updated", "created", "title"];
function savedSort() {
  let v = null;
  try { v = localStorage.getItem("parseh_studio_sort"); } catch (e) { /* private mode */ }
  return SORTS.includes(v) ? v : "updated";
}
function saveSort(v) {
  try { localStorage.setItem("parseh_studio_sort", v); } catch (e) { /* private mode */ }
}

/* A library visit should survive opening a document in this tab.  The
   language chip and sort already have their own shared preferences; search
   and tags belong to this tab, so another window can browse independently. */
const LIBRARY_FILTERS_KEY = "parseh_studio_filters";
function savedLibraryFilters() {
  let saved = {};
  try { saved = JSON.parse(sessionStorage.getItem(LIBRARY_FILTERS_KEY) || "{}"); }
  catch (e) { /* private mode or an old, unreadable value */ }
  if (!saved || typeof saved !== "object") saved = {};
  const tags = value => new Set(Array.isArray(value)
    ? value.filter(tag => typeof tag === "string" && tag) : []);
  return {q: typeof saved.q === "string" ? saved.q : "",
          intext: saved.intext === true,
          tags: tags(saved.tags), excludedTags: tags(saved.excludedTags)};
}

/* ---------------- helpers ---------------- */

/* WHAT THE SERVER ACTUALLY SAID, out of a refusal, for every studio route.
   Most of them answer {"error": "..."}, but a route that was asked to MAKE
   something reports on the thing it was making: a failed build is
   {"build": {"status": "error", "error": "! Undefined control sequence ..."}}
   with a 500 beside it.  Reading `data.error` alone threw LaTeX's own words
   away and left the page saying "500 Internal Server Error", which names
   nothing anybody can act on.  So one level down is looked at too, in the
   order the answer wrote its keys. */
function serverSaid(data, r) {
  if (data && typeof data === "object") {
    if (typeof data.error === "string" && data.error) return data.error;
    for (const value of Object.values(data)) {
      if (value && typeof value === "object" && typeof value.error === "string"
          && value.error) return value.error;
    }
  }
  return r.status + " " + r.statusText;
}

/* NOBODY THERE IS NOT THE SAME AS SLOW, and until now nothing here could
   tell them apart (the owner's rule of 2026-09-23).

   `fetch` gives up when the socket does.  A socket towards a computer that
   has been switched off is REFUSED, in microseconds -- that is what this
   desk sees, and it is why every page of this toolbox behaved perfectly
   here.  A socket towards a computer on the far side of a tunnel that has
   gone is SWALLOWED: the connection is made and no answer ever comes, for
   ever.  Only a phone meets the second kind.  lib/sw.js cannot rescue it
   either, because it answers GETs alone (`r.method !== 'GET'`), so every
   write on every page of this app had no deadline anywhere in the stack.

   A BLANKET TIMEOUT WOULD BE THE WRONG MEND.  Importing a deck, packing a
   backup, building a PDF: these are honestly slow and must not be cut off
   at three seconds because a phone might have been in a tunnel.  So the ask
   is not timed -- it is WATCHED: it waits for the page's one question, "is
   the computer there?", which lib/activity.js asks for the whole page.  A
   computer that is slow goes on being waited for however long it needs --
   slow is online (TO-DO §2.24) -- and a computer the question finds gone
   ends the ask at once, saying so (`away`), which is what every offline
   fallback in this app keys off.  It used to ask the question itself, beside
   every ask, and read three seconds of silence as "gone": on a slow tunnel
   the asks and the probes beside them piled up until a computer that was
   right there looked absent. */
// on a page already offline an ask is given as long as the worker takes to
// answer from a kept copy (lib/sw.js, DEADLINE), and no longer
const KEPT_ONLY = 3000;
function watched(go) {
  return new Promise((yes, no) => {
    let settled = false, short = null;
    const end = () => {
      settled = true;
      clearTimeout(short);
      document.removeEventListener("parseh:reach", heard);
    };
    const gone = () => {
      if (settled) return;
      end();
      const out = new Error("the server does not answer — is Parseh still running?");
      out.away = true;
      no(out);
    };
    const heard = e => { if (e.detail && e.detail.state === "away") gone(); };
    go.then(r => { if (!settled) { end(); yes(r); } },
            e => { if (!settled) { end(); no(e); } });
    document.addEventListener("parseh:reach", heard);
    if (pageIsAway()) short = setTimeout(gone, KEPT_ONLY);
  });
}
/* AND A PAGE THAT KNOWS THE COMPUTER IS AWAY DOES NOT ASK IT TO WRITE.  But
   KNOWS: an away this page has confirmed (lib/keep.js marks it `confirmed`),
   or that the page's one question has found -- not one merely ASSUMED from
   what the page before found (AWAY_BOOT marks that `assumed`).  An assumed
   away is the page drawing itself offline before anything has been asked,
   and the question corrects it in the page's first breath; a write pressed
   in that breath used to fail with "cannot be reached" on a computer that
   was right there (TO-DO §2.24).  A GET is left alone either way: the worker
   may have a copy of it, and answering from what is kept is the point. */
function pageIsAway() {
  if (document.documentElement.getAttribute("data-parseh-away") === "confirmed") return true;
  const A = window.ParsehActivity;
  return !!(A && A.reach && A.reach().state === "away");
}

async function api(path, opts = {}) {
  if (opts.json !== undefined) {
    opts.body = JSON.stringify(opts.json);
    opts.headers = Object.assign({"Content-Type": "application/json"},
                                 opts.headers);
    delete opts.json;
  }
  const writes = (opts.method || "GET").toUpperCase() !== "GET";
  if (writes && pageIsAway()) {
    const gone = new Error("Parseh's computer cannot be reached, and this needs it");
    gone.away = true;
    throw gone;
  }
  const r = await watched(fetch(BASE + path, opts));
  let data = {};
  try { data = await r.json(); } catch (e) { /* non-JSON error page */ }
  if (!r.ok) {
    // the whole answer rides along: a caller with more to show than one
    // sentence -- the build, whose log tail comes with the refusal -- reads
    // it from here rather than asking again for something already sent
    const err = new Error(serverSaid(data, r));
    err.status = r.status;
    err.data = data;
    // the worker's own refusal for a door it has no copy of (lib/sw.js,
    // `refused`): not a Parseh that said no, a Parseh that was not there
    err.away = data.offline === true || r.status === 503;
    throw err;
  }
  return data;
}

/* A document's name as a `[…](doc:Name)` link writes it: itself, with a
   backslash before every backslash and before every parenthesis that does
   not pair up (or pairs up more than two deep) -- texgen.escape_doc_name,
   character for character, so the link closes where it should and the
   server reads back the very name that was picked. */
function escapeDocName(name) {
  const s = String(name || "").replace(/\s*\n\s*/g, " ").trim();
  const keep = new Set(), open = [];
  for (let i = 0; i < s.length; i++) {
    if (s[i] === "(") open.push([i, open.length + 1]);
    else if (s[i] === ")" && open.length) {
      const [j, depth] = open.pop();
      if (depth <= 2) { keep.add(i); keep.add(j); }
    }
  }
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "\\" || ((c === "(" || c === ")") && !keep.has(i))) out += "\\";
    out += c;
  }
  return out;
}

/* api() for the requests whose refusal is an answer to act on rather than
   an error to show -- an upload short of its header (422), a name already
   taken (409): {status, ok, data}, and never a throw for a status. */
async function send(path, opts) {
  const init = Object.assign({}, opts);
  if (init.json !== undefined) {
    init.body = JSON.stringify(init.json);
    init.headers = {"Content-Type": "application/json"};
    delete init.json;
  }
  const r = await fetch(BASE + path, init);
  let data = {};
  try { data = await r.json(); } catch (e) { /* not JSON */ }
  return {status: r.status, ok: r.ok && data.ok !== false, data};
}
const nameClash = a => !!(a && a.status === 409 && a.data && a.data.name_conflicts);

/* THE NAME-CONFLICT DIALOG.  A document's name is its title, and a link
   names its target (`[…](doc:Name)`), so no two documents of one library
   may share a name.  Whatever adds a document or renames one -- a save, a
   new document, a paste, an upload, a zip, a backup -- is answered 409 when
   a name is taken, with nothing written, and `first` is that answer.

   For each clash this asks for two names: one for the document already in
   the library (or already in the zip), one for the document being saved or
   added; either may stay as it is, not both.  `resend(renames)` sends the
   same request again with them -- {existing: {id: name}, incoming: {ref:
   name}} -- and the server checks every name again, together: a name still
   taken comes back as a problem shown under its own field, and the dialog
   stays open for another.  Resolves to the answer that went through
   ({status, ok, data}), or to null when cancelled: nothing was written.
   `verb` says what the incoming document is being: "saved" or "added".

   The first answer may refuse a name the page itself sent -- a backup's
   second pass (Replace) goes with the names its first pass was given --
   or a name no other document has but that cannot be one (a "|"): every
   name refused gets a field all the same, from the pair the server makes
   of it or, failing that, on its own (`fields` says what it was). */
function askNames(first, resend, {verb = "added"} = {}) {
  return new Promise(resolve => {
    const root = $("#modal-root");
    root.innerHTML = "";
    const ov = document.createElement("div");
    ov.className = "modal-overlay";
    const clash = (first.name_conflicts || []).length > 0;
    ov.innerHTML = `<div class="modal names-modal" role="dialog" aria-modal="true"
                         aria-labelledby="names-title">
      <h3 id="names-title">${clash ? "This name is already in use" : "This name cannot be used"}</h3>
      <p>${clash ? `A link to a document names it, so two documents of one library cannot
         share a name. Rename the document already there, the one being ${verb},
         or both — every link to a renamed document follows it to its new name.`
         : `Give the document being ${verb} another name — what is wrong with this
         one is said under it.`}</p>
      <div class="names-list"></div>
      <p class="names-error" role="alert" hidden></p>
      <div class="row">
        <button class="btn" type="button" data-x="cancel">Cancel</button>
        <button class="btn primary" type="button" data-x="ok">Use these names</button>
      </div></div>`;
    const list = $(".names-list", ov), errBox = $(".names-error", ov);
    const okBtn = $('[data-x="ok"]', ov), cancelBtn = $('[data-x="cancel"]', ov);
    const fields = new Map();          // "existing:<id>" / "incoming:<ref>" -> input
    let settled = false, busy = false;

    function field(box, key, label, value, extra) {
      const lab = document.createElement("label");
      lab.className = "modal-field names-field";
      if (fields.has(key)) {           // the same document in a second clash
        lab.innerHTML = `<span class="names-label"></span><span class="names-same">renamed above</span>`;
        $(".names-label", lab).textContent = label;
        box.appendChild(lab);
        return;
      }
      lab.innerHTML = `<span class="names-label"></span>
        <input type="text" dir="auto" spellcheck="false" autocomplete="off">
        <span class="names-problem" dir="ltr" hidden></span>`;
      $(".names-label", lab).textContent = label;
      if (extra) $(".names-label", lab).appendChild(extra);
      const input = $("input", lab);
      input.value = value || "";
      input.dataset.key = key;
      input.addEventListener("input", () => problem(key, ""));
      fields.set(key, input);
      box.appendChild(lab);
    }
    // a way to look at a document of the library first, in a tab of its
    // own: this one holds the unsaved text or the upload being answered
    function opener(id) {
      const open = document.createElement("a");
      open.className = "names-open";
      open.href = `${BASE}/doc/${encodeURIComponent(id)}`;
      open.target = "_blank";
      open.rel = "noopener";
      open.textContent = "open it ↗";
      return open;
    }
    const keyOf = side => side.id ? "existing:" + side.id
      : "incoming:" + (side.ref !== undefined ? side.ref : side.incoming_ref);
    // a side's field: prefilled with the name it was given, else its own
    function side(box, s, label) {
      field(box, keyOf(s), label, s.name !== undefined ? s.name : s.title,
            s.id ? opener(s.id) : null);
    }
    function pair(c) {
      const ex = c.existing || {}, inc = c.incoming || {};
      // asked again, the pair of a document that has its field already
      // says nothing new: the problem under that field says it
      if (fields.has(keyOf(inc))) return;
      const box = document.createElement("fieldset");
      box.className = "names-pair";
      const legend = document.createElement("legend");
      const wanted = inc.name !== undefined ? inc.name : ex.name;
      legend.textContent = wanted !== undefined ? `Both would be called “${wanted}”`
        : `Both are called “${ex.title || inc.title}”`;
      box.appendChild(legend);
      side(box, ex, ex.id ? "Rename the document already in the library"
        : `Rename the other document being ${verb}` + (ex.file ? ` (${ex.file})` : ""));
      side(box, inc, inc.id ? "Rename this other document of the library"
        : `Rename the document being ${verb}` + (inc.file ? ` (${inc.file})` : ""));
      list.appendChild(box);
    }
    // a name refused that no pair brought a field for
    function lone(key, f) {
      const box = document.createElement("fieldset");
      box.className = "names-pair";
      const legend = document.createElement("legend");
      legend.textContent = `“${f.title || f.name || ""}”`;
      box.appendChild(legend);
      const id = key.startsWith("existing:") ? key.slice(9) : "";
      field(box, key, id ? "Rename the document already in the library"
        : `Rename the document being ${verb}` + (f.file ? ` (${f.file})` : ""),
            f.name || f.title || "", id ? opener(id) : null);
      list.appendChild(box);
    }
    function problem(key, text) {
      const input = fields.get(key);
      if (!input) return false;
      const out = input.parentNode.querySelector(".names-problem");
      out.textContent = text || "";
      out.hidden = !text;
      input.classList.toggle("bad", !!text);
      input.setAttribute("aria-invalid", text ? "true" : "false");
      return true;
    }
    function show(answer) {
      for (const c of answer.name_conflicts || []) pair(c);
      const problems = answer.problems || {};
      for (const key of Object.keys(problems))
        if (!fields.has(key)) lone(key, (answer.fields || {})[key] || {});
      let shown = 0;
      for (const [key, text] of Object.entries(problems)) if (problem(key, text)) shown++;
      const bad = [...fields.values()].find(i => i.classList.contains("bad"));
      (bad || fields.values().next().value || okBtn).focus();
      return shown;
    }
    function hold(on) {
      busy = on;
      okBtn.disabled = cancelBtn.disabled = on;
      okBtn.textContent = on ? "Checking…" : "Use these names";
    }
    const finish = value => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      if (ov.parentNode) ov.parentNode.removeChild(ov);
      resolve(value);
    };
    async function submit() {
      if (busy) return;
      errBox.hidden = true;
      const renames = {existing: {}, incoming: {}};
      let empty = null;
      for (const [key, input] of fields) {
        const value = input.value.replace(/\s+/g, " ").trim();
        const cut = key.indexOf(":");
        renames[key.slice(0, cut)][key.slice(cut + 1)] = value;
        if (!value) { problem(key, "A document needs a name — give it one"); empty = empty || input; }
      }
      if (empty) { empty.focus(); return; }
      hold(true);
      let answer;
      try {
        answer = await resend(renames);
      } catch (e) {
        errBox.textContent = e.message;
        errBox.hidden = false;
        hold(false);
        return;
      }
      if (nameClash(answer)) {
        hold(false);
        for (const key of fields.keys()) problem(key, "");
        if (!show(answer.data)) {
          errBox.textContent = answer.data.error || "a name is still taken";
          errBox.hidden = false;
        }
        return;
      }
      finish(answer);
    }
    function onKey(e) {
      if (e.key === "Escape" && !busy) { e.preventDefault(); e.stopPropagation(); finish(null); }
      else if (e.key === "Enter" && e.target.matches && e.target.matches(".names-field input")) {
        e.preventDefault(); submit();
      }
    }
    document.addEventListener("keydown", onKey, true);
    okBtn.addEventListener("click", submit);
    cancelBtn.addEventListener("click", () => { if (!busy) finish(null); });
    ov.addEventListener("click", e => { if (e.target === ov && !busy) finish(null); });
    root.appendChild(ov);
    show(first);
  });
}
/* THE TOOLBOX'S ACTIVITY LIST (lib/activity.js, which every studio page
   loads with a tag of its own): work started here is on it at once, under
   `label`, until the promise `fn(act)` returns settles.  `act.url(u)` puts
   the list's token on the request, so the server's own entry for it -- the
   one with the sizes -- is shown as the same one and not beside it.  A
   studio run on its own has no list, and a falsy label means the work is
   too small to be worth an entry (a picture of a few kilobytes): either
   way `fn` simply runs. */
const NO_ACTIVITY = {job: "", url: u => u, end() {}, progress() {}, set() {}, adopt() {}};
function working(label, fn) {
  const A = window.ParsehActivity;
  return A && label ? A.track(fn, label) : fn(NO_ACTIVITY);
}
// the size from which a file put into a document is worth an entry: the
// same line the server draws (serve.py's BIG_BODY)
const BIG_UPLOAD = 4 * 1024 * 1024;

// a file made on demand (the HTML exports), fetched under a bar rather than
// navigated to: slow is waited for, and only the page's verdict or its own
// deadline gives up, saying so with Try again (TO-DO §2.28)
const MADE_PATIENCE = 5 * 60 * 1000;
const MADE_STALL = 60 * 1000;
function madeName(r, fallback) {
  const cd = r.headers.get("Content-Disposition") || "";
  const star = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  if (star) { try { return decodeURIComponent(star[1]); } catch (e) { /* the plain one */ } }
  const plain = /filename="([^"]+)"/i.exec(cd);
  return plain ? plain[1] : fallback;
}
function madeSize(n) {
  return n >= 1e6 ? (n / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1e3)) + " kB";
}
function madeClock(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return s < 60 ? s + " s" : Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}
function madeReason(why) {
  return {
    away: "Parseh's computer cannot be reached from this device",
    patience: "Parseh gave no answer in five minutes, so this page stopped waiting",
    stall: "it stopped arriving: nothing more came for a minute",
    cut: "it arrived cut short",
  }[why] || "the connection to Parseh failed before it arrived";
}
function madeSave(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.hidden = true;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 30000);
}
function madeDownload({place, busy = () => {}, done = () => {}}) {
  let box = null, ask = null, running = null;
  function close() {
    if (running) running("cancel");
    if (box) box.remove();
    box = null;
  }
  function panel() {
    if (box && box.isConnected) return box;
    box = document.createElement("div");
    box.className = "made-work";
    box.innerHTML = `<p class="made-say" role="status" aria-live="polite"></p>
      <div class="bar loose" role="progressbar"><i></i></div>
      <div class="made-row"><span class="made-when"></span>
        <button type="button" class="btn small primary" data-x="again" hidden>Try again</button>
        <button type="button" class="btn small" data-x="stop">Cancel</button></div>`;
    $('[data-x="again"]', box).addEventListener("click", () => { if (ask) start(ask); });
    $('[data-x="stop"]', box).addEventListener("click", close);
    place(box);
    return box;
  }
  async function start(req) {
    if (running) return;
    ask = req;
    const b = panel();
    const say = $(".made-say", b), when = $(".made-when", b), bar = $(".bar", b);
    const again = $('[data-x="again"]', b), stop = $('[data-x="stop"]', b);
    b.classList.remove("err");
    say.textContent = req.label + "…";
    bar.hidden = false;
    bar.className = "bar loose";
    bar.setAttribute("aria-label", req.label);
    bar.removeAttribute("aria-valuenow");
    bar.firstChild.style.width = "";
    again.hidden = true;
    stop.textContent = "Cancel";
    const began = Date.now();
    let got = 0, total = 0;
    const clock = () => {
      when.textContent = (total ? `${Math.min(100, Math.floor(100 * got / total))}% of ${madeSize(total)} · `
                                : got ? madeSize(got) + " · " : "") + madeClock(Date.now() - began);
    };
    clock();
    const tick = setInterval(clock, 1000);
    const ctl = new AbortController();
    let why = "", timer = null;
    const quit = w => { if (!why) { why = w; ctl.abort(); } };
    const wait = (ms, w) => { clearTimeout(timer); timer = setTimeout(() => quit(w), ms); };
    const heard = e => { if (e.detail && e.detail.state === "away") quit("away"); };
    running = quit;
    busy(true);
    document.addEventListener("parseh:reach", heard);
    wait(MADE_PATIENCE, "patience");
    try {
      const out = await working(req.label, async act => {
        let r;
        try {
          r = await fetch(act.url(req.url), Object.assign({cache: "no-store", credentials: "same-origin"},
                                                          req.init || {}, {signal: ctl.signal}));
        } catch (e) {
          throw new Error(madeReason(why));
        }
        if (!r.ok) {
          let data = {};
          try { data = await r.json(); } catch (e) { /* not JSON */ }
          throw new Error(serverSaid(data, r));
        }
        total = +(r.headers.get("Content-Length") || 0);
        const parts = [];
        const rd = r.body.getReader();
        wait(MADE_STALL, "stall");
        for (;;) {
          let step;
          try { step = await rd.read(); } catch (e) { throw new Error(madeReason(why || "cut")); }
          if (step.done) break;
          parts.push(step.value);
          got += step.value.length;
          wait(MADE_STALL, "stall");
          if (total) {
            const pc = Math.min(100, 100 * got / total);
            bar.className = "bar";
            bar.firstChild.style.width = pc + "%";
            bar.setAttribute("aria-valuenow", String(Math.floor(pc)));
            act.progress(got, total);
          }
        }
        if (total && got < total) throw new Error(madeReason("cut"));
        const name = madeName(r, req.fallback);
        madeSave(new Blob(parts, {type: r.headers.get("Content-Type") || "application/octet-stream"}), name);
        return {r, name};
      });
      if (box === b) { b.remove(); box = null; }
      done(out.r, out.name, req);
    } catch (e) {
      if (why === "cancel" || box !== b) return;
      b.classList.add("err");
      say.textContent = `${req.failed}: ${String(e.message).replace(/[.\s]+$/, "")}.`;
      bar.hidden = true;
      when.textContent = "";
      again.hidden = false;
      stop.textContent = "Close";
      const seen = b.getBoundingClientRect();
      if (seen.bottom <= 0 || seen.top >= innerHeight) toast(say.textContent, true);
    } finally {
      clearInterval(tick);
      clearTimeout(timer);
      document.removeEventListener("parseh:reach", heard);
      running = null;
      busy(false);
    }
  }
  return {start, close};
}

let toastTimer = null;
function toast(msg, isErr) {
  const t = $("#toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.toggle("err", !!isErr);
  t.hidden = false;
  t.style.opacity = "1";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.style.opacity = "0";
    setTimeout(() => { t.hidden = true; }, 300);
  }, isErr ? 4200 : 2200);
}

/* A QUESTION IN THE STUDIO'S OWN WINDOW, where the browser's confirm() would
   be a box in another theme.  The same window the exercise decks ask in
   (decks.js `dialog`): Cancel is the first button and has the focus, Escape
   and a click beside the box answer no, and the answer is a promise -- true
   for the main button, false for anything else.  `run`, when there is one,
   is what the main button does, and it does it INSIDE the window: both
   buttons are off while it works, and when it throws the message is toasted
   and the window stays, so a refusal is said where the question was asked
   and the button can be pressed again.  Focus goes back to `opener` (or to
   what had it) when the window closes. */
function confirmDialog({title, hint = "", ok = "OK", danger = false, run = null, opener = null}) {
  const root = $("#modal-root");
  const back = opener || document.activeElement;
  root.innerHTML = "";
  const ov = document.createElement("div");
  ov.className = "modal-overlay";
  const box = document.createElement("div");
  box.className = "modal dk-modal";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-label", title);
  const h = document.createElement("h3");
  h.textContent = title;
  box.appendChild(h);
  if (hint) {
    const p = document.createElement("p");
    p.textContent = hint;
    box.appendChild(p);
  }
  const row = document.createElement("div");
  row.className = "row";
  const noBtn = document.createElement("button");
  noBtn.type = "button";
  noBtn.className = "btn";
  noBtn.dataset.x = "cancel";
  noBtn.textContent = "Cancel";
  const yesBtn = document.createElement("button");
  yesBtn.type = "button";
  yesBtn.className = "btn " + (danger ? "danger" : "primary");
  yesBtn.dataset.x = "ok";
  yesBtn.textContent = ok;
  row.append(noBtn, yesBtn);
  box.appendChild(row);
  ov.appendChild(box);
  return new Promise(resolve => {
    let busy = false, settled = false;
    const close = value => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      ov.remove();
      if (back && back.isConnected && typeof back.focus === "function") back.focus();
      resolve(value);
    };
    const hold = on => { busy = on; noBtn.disabled = yesBtn.disabled = on; };
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault(); e.stopPropagation();
        if (!busy) close(false);
      } else if (e.key === "Tab") {
        e.preventDefault();               // the page beneath is not reachable
        const live = [noBtn, yesBtn].filter(b => !b.disabled);
        if (!live.length) return;
        const i = live.indexOf(document.activeElement);
        live[(i + (e.shiftKey ? live.length - 1 : 1)) % live.length].focus();
      }
    }
    document.addEventListener("keydown", onKey, true);
    noBtn.addEventListener("click", () => { if (!busy) close(false); });
    ov.addEventListener("click", e => { if (e.target === ov && !busy) close(false); });
    yesBtn.addEventListener("click", async () => {
      if (busy) return;                   // one request per click, however fast
      hold(true);
      try {
        if (run) await run();
      } catch (e) {
        toast(e.message, true);
        hold(false);
        noBtn.focus();
        return;
      }
      close(true);
    });
    root.appendChild(ov);
    (danger ? noBtn : yesBtn).focus();
  });
}

/* A FLASHCARD, LARGE, OVER THE PAGE.  A card on the page is a column wide,
   and a picture on it is shrunk to fit -- which is what makes a picture card
   hard to see.  So every flashcard has ⤢ Enlarge: the same card in a window
   over the page, as big as the window holds.  The window shows a copy, and
   turning it turns the card on the page -- a click on that card, so
   whatever listens there hears it (the study page counts a turned card as
   the answer shown) -- and the copy is drawn again from it.  While the
   window is open the keys are its own: Space or Enter turns the card,
   Escape closes it, and nothing reaches the page underneath.

   THE SAME CARD, ONLY BIGGER.  A card's fields are not all centred: a
   paragraph of right-to-left text sits on the right, a Latin block is
   justified, a field of several blocks starts where its lines start -- and
   what puts them there is the page around the card as much as the card:
   the sheet's typography (its "justify", its sizes), the direction and
   language of the exercise it is in, and the card's width, which decides
   which lines wrap and so which fields fill the card.  A copy set loose in
   a window as wide as the screen had none of that, and every line of it
   came out centred.  So the copy is laid out as the card on the page is --
   at the card's own width, in its own text size, inside that same context --
   and only then magnified whole, by a transform: the lines break where they
   break on the page (they are laid out at the page's size, and a zoom that
   laid them out again at the larger one would break a long paragraph a word
   differently), and every picture, player and margin keeps its place and
   its proportion.  How much larger is what the window holds: the whole
   card, the taller of its two sides deciding, when that is at least half as
   large again; a card too tall for that is drawn at least that large, never
   wider than the window, and scrolls.

   ON A PHONE the card on the page is already nearly as wide as the window,
   and a card magnified whole can grow no more than that -- a third or so,
   the rest of the window left empty.  There the copy is laid out narrower
   than the card on the page instead, at the window's width divided by the
   magnification, and magnified to the window's width: every field, picture
   and player as it is on the page, in the page's text size and context.
   Narrower, a line may break that did not break on the page, and a card
   whose short fields -- a word, its meaning, a sentence -- wrap onto two
   lines is no longer the card on the page, only bigger.  So no line breaks
   that is whole on the page: a field, a paragraph or a line of a Jolly
   field (up to its ⏎) that is one line there is one line enlarged, and
   only a paragraph that already wraps on the page may wrap at other words.
   Nor is a picture or a player laid out any narrower than on the page: a
   figure is a share of its field's width, and a card's picture or a
   recording that fills its field narrows with it, so laid out narrower
   they would come out smaller beside the words than on the page -- a
   recording a few centimetres wide losing its timeline -- in the very
   window that is there to show them.
   The magnification is as much as that allows, and the window's height,
   up to ZOOM_RELAID_AT_MOST, and never so much that anything is wider than
   its box at the narrower width that is not on the page (a word sticking
   out of the card, a table that would scroll).  Where that is hardly more
   than magnifying the card whole -- less than ZOOM_RELAID_GAIN times as
   much -- or where even the card magnified whole is too tall for the
   window, it is magnified whole at the page's width instead, as far as
   the window's width allows, every line where it is on the page; one too
   tall scrolls. */
const ZOOM_AT_LEAST = 1.5, ZOOM_RELAID_AT_MOST = 2, ZOOM_RELAID_GAIN = 1.1;
/* How many lines each stretch of an element's text is drawn in, in the
   order the stretches come: a stretch is what only wrapping breaks -- the
   text of a paragraph, a field, a cell, a button, up to its end or to a
   hard line break (a <br>, a Jolly field's ⏎).  Its lines are its text's
   boxes as drawn, grouped by where they sit down the block (across it, in
   vertical text); ruby's reading above a word and a footnote's cloud,
   which is out of the flow until it is shown, are no line of it, nor is
   anything hidden.  The same element gives the same stretches in the same
   order at any width, so two counts compare stretch by stretch. */
function lineCounts(el) {
  const blocks = new Map();      // a block -> the lines of each of its stretches
  // (the box a run of text wraps in: not an inline one, but an inline
  // block -- a button, a 🔊 -- wraps its own text)
  const inline = b => /^(inline|contents|ruby)$|^ruby-/.test(getComputedStyle(b).display);
  const blockOf = node => {
    let b = node.parentElement;
    while (b !== el && inline(b)) b = b.parentElement;
    if (!blocks.has(b)) blocks.set(b, [[]]);
    return blocks.get(b);
  };
  const walk = document.createTreeWalker(el, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: n => n.nodeType === 1 && n.matches("rt, rp, .fncloud, [hidden], script, style")
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  });
  const range = document.createRange();
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    if (n.nodeType === 1) {
      if (n.localName === "br") blockOf(n).push([]);
      continue;
    }
    if (!/\S/.test(n.data)) continue;
    const stretches = blockOf(n), lines = stretches[stretches.length - 1];
    const horizontal = !/^(vertical|sideways)/.test(getComputedStyle(n.parentElement).writingMode);
    range.selectNodeContents(n);
    for (const q of range.getClientRects()) {
      if (!q.width || !q.height) continue;
      const [a, b] = horizontal ? [q.top, q.bottom] : [q.left, q.right];
      const line = lines.find(([c, d]) => Math.min(b, d) - Math.max(a, c) > Math.min(b - a, d - c) / 2);
      if (line) { line[0] = Math.min(line[0], a); line[1] = Math.max(line[1], b); }
      else lines.push([a, b]);
    }
  }
  return [...blocks.values()].flat().map(lines => lines.length);
}
function openCardZoom(ex) {
  const card = ex && $(".ex-flashcard", ex);
  if (!card) return;
  const ov = document.createElement("div");
  ov.className = "modal-overlay ex-zoom-overlay";
  ov.innerHTML = `<div class="modal ex-zoom-modal" role="dialog" aria-modal="true" tabindex="-1">
      <div class="ex-zoom-head"><span class="ex-kicker"></span>
        <span class="ex-zoom-hint">click the card or press Space to turn it · Esc closes</span>
        <button type="button" class="btn ghost ex-zoom-close" title="Close (Esc)">✕</button></div>
      <div class="sheet ex-zoom-stage"><div class="ex-zoom-card"><div class="ex-zoom-scale"></div></div></div></div>`;
  const modal = $(".ex-zoom-modal", ov), stage = $(".ex-zoom-stage", ov);
  const frame = $(".ex-zoom-card", ov), scaled = $(".ex-zoom-scale", ov);
  const kicker = $(":scope > .ex-head > .ex-kicker", ex);
  $(".ex-kicker", ov).textContent = kicker ? kicker.textContent : "Flashcard";
  modal.setAttribute("aria-label", $(".ex-kicker", ov).textContent + ", enlarged");
  // the page the card is on: its language, and the typography the reader
  // set on it (applyTypo: the scale of the target script, the text size,
  // the leading, and whether its paragraphs are justified)
  const home = ex.closest(".sheet, [data-lang]");
  if (home) {
    for (const a of ["lang", "dir", "data-lang"])
      if (home.hasAttribute(a)) stage.setAttribute(a, home.getAttribute(a));
    for (const p of Array.from(home.style))
      if (p.startsWith("--")) stage.style.setProperty(p, home.style.getPropertyValue(p));
    const scale = getComputedStyle(home).getPropertyValue("--fa-scale").trim();
    if (scale) stage.style.setProperty("--fa-scale", scale);
    stage.classList.toggle("justify", home.classList.contains("justify"));
  }
  // and the exercise it is in: the direction its content-direction gives
  // the body, and the text size there
  const around = card.parentElement;
  for (const a of ["dir", "lang"]) {
    const from = around.closest(`[${a}]`);
    if (from && ex.contains(from)) scaled.setAttribute(a, from.getAttribute(a));
  }
  scaled.style.fontSize = getComputedStyle(around).fontSize;
  // the copy is a card of its own, with players of its own: one playing on
  // the page underneath is stopped, and the copy's stop when it is drawn again
  const hush = el => $$("audio, video", el).forEach(m => m.pause());
  let magnified = 1;
  // a picture arriving, a player laying itself out, a face loading: the
  // copy changes size after it was drawn, and is measured again -- in the
  // next frame, since fitting it may change its size itself (laid out at
  // another width), which the observer would otherwise have to report
  // again in the frame it is reporting
  let fitting = 0;
  const sizer = window.ResizeObserver ? new ResizeObserver(() => {
    if (!fitting) fitting = requestAnimationFrame(() => { fitting = 0; fit(); });
  }) : null;
  const draw = () => {
    hush(stage);
    const copy = card.cloneNode(true);
    $$("[id]", copy).forEach(x => x.removeAttribute("id"));
    $$(".ex-card-play.playing", copy).forEach(x => x.classList.remove("playing"));
    copy.tabIndex = -1;                  // the window takes the keys, not the copy
    scaled.replaceChildren(copy);
    if (sizer) { sizer.disconnect(); sizer.observe(copy); }
    fit();
  };
  // Measured at the page card's width as it is now (a phone turned on its
  // side gives the page another), and magnified by what fits.  Both sides
  // count, so that turning the card does not change its size.  The frame
  // takes the magnified size, which is what the window centres and scrolls:
  // a transform draws larger but takes no more room.
  function fit() {
    const copy = scaled.firstElementChild;
    if (!copy || !ov.isConnected) return;
    const cs = getComputedStyle(stage);
    const roomX = stage.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const roomY = stage.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    // (a card not drawn on the page has no width there: the widest it can be)
    const onPage = card.getBoundingClientRect().width > 0 ? getComputedStyle(card).width : "34em";
    const front = $(":scope > .ex-card-front", copy), back = $(":scope > .ex-card-back", copy);
    // the copy laid out at a width: how wide it is, and how tall its taller
    // side -- to the fraction of a pixel (offsetWidth rounds, and a card
    // magnified from a width rounded down comes out wider than the window,
    // which then scrolls sideways by a pixel) -- and how many things on
    // either side are wider than their box: a word sticking out of the
    // card, a table its wrapper has to scroll
    const size = () => {
      const c = getComputedStyle(copy);
      return [parseFloat(c.width), parseFloat(c.height)];
    };
    const sticksOut = () => [copy, ...$$("*", copy)]
      .filter(el => el.scrollWidth > el.clientWidth + 1).length;
    // the width of every picture and player shown, in the order they come
    // (the same at any width)
    const media = () => $$("img, video, audio, iframe", copy)
      .filter(el => el.getClientRects().length)
      .map(el => parseFloat(getComputedStyle(el).width) || 0);
    // -- and, asked to `count`, how many lines each stretch of its text is
    // drawn in on either side (lineCounts), and how wide each of its
    // pictures and players is
    const layOut = (width, count) => {
      copy.style.width = width;
      let [wide, high] = size(), out = sticksOut();
      const counts = count ? lineCounts(copy) : [], widths = count ? media() : [];
      if (front && back && front.hidden !== back.hidden) {
        front.hidden = !front.hidden; back.hidden = !back.hidden;
        high = Math.max(high, size()[1]);
        out += sticksOut();
        if (count) { counts.push(...lineCounts(copy)); widths.push(...media()); }
        front.hidden = !front.hidden; back.hidden = !back.hidden;
      }
      return {wide, high, out, counts, widths};
    };
    const {wide, high, out} = layOut(onPage);
    const across = roomX / Math.max(1, wide), down = roomY / Math.max(1, high);
    let zoom = Math.max(0.1, Math.min(across, Math.max(down, Math.min(across, ZOOM_AT_LEAST))));
    if (across < ZOOM_AT_LEAST && high * across <= roomY) {
      // a phone, and a card the window holds whole: laid out narrower,
      // magnified to the window's width, as much as its height holds with
      // no line of the page broken, no picture or player narrower than on
      // the page, and nothing wider than its box that is not so on the
      // page.  Magnified whole it fits, and every step narrower is taller,
      // breaks more and narrows more, so what fits is found halving the
      // gap between what does and what does not.
      const {counts, widths} = layOut(onPage, true);
      const fits = m => {
        const at = layOut(roomX / m + "px", true);
        return at.high * m <= roomY && at.out <= out
          && at.counts.every((n, i) => counts[i] !== 1 || n === 1)
          && at.widths.every((w, i) => w >= widths[i] - 0.5);
      };
      let lo = across, hi = ZOOM_RELAID_AT_MOST;
      if (fits(hi)) lo = hi;
      else for (let i = 0; i < 7; i++) {
        const m = (lo + hi) / 2;
        if (fits(m)) lo = m; else hi = m;
      }
      if (lo >= across * ZOOM_RELAID_GAIN) {
        zoom = lo;
        layOut(roomX / zoom + "px");
      } else layOut(onPage);
    }
    scaled.style.transform = `scale(${zoom})`;
    scaled.style.setProperty("--zoom", zoom);    // a footnote's cloud fits the window
    magnified = zoom;
    // as drawn, to the fraction of a pixel: a width rounded up would make
    // a card as wide as the window scroll sideways
    const drawn = copy.getBoundingClientRect();
    frame.style.width = drawn.width + "px";
    frame.style.height = drawn.height + "px";
  }
  // A footnote's cloud on the copy is over its mark, as on the page, but
  // kept inside the window, which cuts off whatever sticks out of it: put
  // under its line where there is no room above it (as bindFootnoteClouds
  // does on the page) -- on the side with more room, where it fits on
  // neither -- and moved along its line where it would stick out at a side.
  // Measured shown, however far the hover or the focus that shows it has got.
  function placeCloud(e) {
    const fn = e.target.closest && e.target.closest(".fn");
    const cloud = fn && stage.contains(fn) && $(".fncloud", fn);
    if (!cloud) return;
    cloud.style.removeProperty("--fn-shift");
    fn.classList.remove("fn-below");
    cloud.style.display = "block";
    const box = stage.getBoundingClientRect();
    const gutter = (box.width - stage.clientWidth) / 2;   // a scrollbar's, kept on both sides
    const left = box.left + gutter + 4, right = box.right - gutter - 4;
    const above = cloud.getBoundingClientRect();
    if (above.top < box.top + 4) {
      fn.classList.add("fn-below");
      const below = cloud.getBoundingClientRect();
      if (below.bottom > box.bottom - 4 && above.top - box.top > box.bottom - below.bottom)
        fn.classList.remove("fn-below");
    }
    const r = cloud.getBoundingClientRect();
    const dx = r.left < left ? left - r.left : r.right > right ? right - r.right : 0;
    if (dx) cloud.style.setProperty("--fn-shift", dx / magnified + "px");
    cloud.style.display = "";
  }
  stage.addEventListener("mouseover", placeCloud);
  stage.addEventListener("focusin", placeCloud);
  hush(card);
  const opener = document.activeElement;
  const refit = debounce(fit, 120);
  const close = () => {
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("resize", refit);
    if (sizer) sizer.disconnect();
    cancelAnimationFrame(fitting);
    hush(stage);
    ov.remove();
    if (opener && opener.isConnected && opener.focus) opener.focus({preventScroll: true});
  };
  const turn = () => {
    if (!card.isConnected) { close(); return; }   // the page moved on under it
    card.click();
    draw();
    modal.focus({preventScroll: true});          // a turned card may take the focus below
  };
  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); close(); return; }
    const onControl = e.target !== modal && e.target.closest && e.target.closest(CARD_CONTROLS);
    // a key on the close button or on a player, a link or a 🔊 in the copy is
    // theirs, and goes on down to it: a native player hears Space only there.
    // The window stops it on its way back up.
    if (onControl && ov.contains(onControl)) return;
    e.stopImmediatePropagation();                // the page underneath hears nothing
    if ((e.key === " " || e.key === "Enter") && !onControl) { e.preventDefault(); turn(); }
  }
  document.addEventListener("keydown", onKey, true);
  ov.addEventListener("keydown", e => e.stopPropagation());
  ov.addEventListener("click", e => {
    if (e.target === ov || e.target.closest(".ex-zoom-close")) { close(); return; }
    const copy = e.target.closest(".ex-flashcard");
    if (!copy) return;
    // the same rules as the card on the page: 🔊 plays, a player or a link
    // does its own thing, anywhere else turns it
    const play = e.target.closest(".ex-card-play");
    if (play) {
      toggleCardAudio(play);
      // clicked, not pressed: the keys go back to the window, where Space turns
      if (e.detail) modal.focus({preventScroll: true});
      return;
    }
    const control = e.target.closest(CARD_CONTROLS);
    if (control && copy.contains(control)) return;
    turn();
  });
  // in the page before it is drawn: the room it has is measured there
  document.body.appendChild(ov);
  draw();
  window.addEventListener("resize", refit);
  modal.focus({preventScroll: true});
}

function debounce(fn, ms) {
  let h = null;
  return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); };
}

function fmtDate(s) { return (s || "").replace("T", " ").slice(0, 16); }

/* A clip time as m:ss.  A video's is whole seconds (YouTube takes no
   more); a recording's keeps hundredths when `frac` (1:05.25), which is
   what its clip window is written in. */
function fmtClock(s, frac) {
  if (s === null || s === undefined || s === "") return "";
  const cs = frac ? Math.round(Math.max(0, +s) * 100) : Math.floor(Math.max(0, +s)) * 100;
  const whole = Math.floor(cs / 100), rest = cs % 100;
  const h = Math.floor(whole / 3600), m = Math.floor((whole % 3600) / 60), sec = whole % 60;
  const tail = rest ? "." + String(rest).padStart(2, "0").replace(/0$/, "") : "";
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}${tail}`
           : `${m}:${String(sec).padStart(2, "0")}${tail}`;
}

function parseClock(v, frac) {
  v = String(v || "").trim();
  if (!v) return null;
  const parts = v.split(":");
  let s = 0;
  for (let i = 0; i < parts.length; i++) {
    const last = i === parts.length - 1;
    if (!(frac && last ? /^(?:\d+(?:\.\d*)?|\.\d+)$/ : /^\d+$/).test(parts[i])) return null;
    s = s * 60 + Number(parts[i]);
  }
  return frac ? Math.round(s * 100) / 100 : s;
}

/* ---- recordings on a page -------------------------------------------
   What a file picker offers for a recording: lib/audiofile.py's ACCEPT,
   written again here (tests/exercises.mjs holds the two together), and
   the one list of extensions on a page: a recording's file name, and a
   path the dialect takes (audiofile.PATH_RE), are made from it.  The
   editor's own picker has its accept from the server. */
const AUDIO_ACCEPT = "audio/*,.mp3,.m4a,.aac,.ogg,.oga,.opus,.wav,.flac,.webm";
const AUDIO_EXTS = AUDIO_ACCEPT.split(",").filter(x => x.startsWith(".")).map(x => x.slice(1)).join("|");
const AUDIO_NAME_RE = new RegExp(`\\.(?:${AUDIO_EXTS})$`, "i");
const AUDIO_PATH_RE = new RegExp(`^audio/[A-Za-z0-9][A-Za-z0-9._\\-]*\\.(?:${AUDIO_EXTS})$`, "i");
const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.svg,.pdf";
// what a click on a flashcard may land on without turning it: a player, a
// link, a form control, a note's mark and its cloud -- each does its own
// thing there (a tap on the mark is how a phone opens the note)
const CARD_CONTROLS = "audio, video, iframe, a, button, input, select, textarea, label, summary, details, "
  + ".fnref, .fncloud";

/* The window of a recording laid out with a clip (figure.audio, or an
   exercise's own .ex-audio box, with data-start and/or data-end), or null. */
function clipWindow(media) {
  const fig = media.closest && media.closest("figure.audio, .ex-audio");
  if (!fig) return null;
  const num = v => (v === undefined || v === "" || !Number.isFinite(+v)) ? null : +v;
  const start = num(fig.dataset.start), end = num(fig.dataset.end);
  if (start === null && end === null) return null;
  return {start: start || 0, end: end !== null && end > (start || 0) ? end : null};
}

/* A window that starts at or past the end of its recording has nothing to
   play: the browser puts a seek to its start at the end, which is before
   the start again, and a player that kept seeking there would never stop. */
function clipPastEnd(media, w) {
  return Number.isFinite(media.duration) && w.start >= media.duration - 0.05;
}

/* It stops at its end by a timer that looks again as the end comes near:
   timeupdate arrives four times a second at best, which is a syllable. */
function watchClipEnd(media) {
  clearTimeout(media._clipTimer);
  const w = clipWindow(media);
  if (!w || media.paused) return;
  if (clipPastEnd(media, w)) { media.pause(); return; }
  if (media.currentTime < w.start - 0.25) media.currentTime = w.start;   // dragged back before it
  if (w.end === null) return;
  const left = (w.end - media.currentTime) / (media.playbackRate || 1);
  if (left <= 0.02) { media.pause(); return; }
  media._clipTimer = setTimeout(() => watchClipEnd(media), Math.max(8, Math.min(250, left * 1000 - 30)));
}

/* A card's 🔊 plays its own recording, or pauses it. */
function toggleCardAudio(button) {
  const box = button.closest(".ex-card-audio");
  const audio = box && $("audio", box);
  if (!audio) return;
  if (!audio.paused) { audio.pause(); return; }
  const p = audio.play();
  if (p && p.catch) p.catch(e => {
    // a play cut short by a pause (the card turned) is no failure
    if (e.name !== "AbortError") toast("Could not play the recording: " + e.message, true);
  });
}

/* Every page that loads this script, once: a recording with a clip window
   plays that window only -- played from outside it, it starts at its start
   -- and among the flashcards one recording speaks at a time.  Media events
   do not bubble, so these listen on the way down. */
document.addEventListener("play", e => {
  const media = e.target;
  if (!(media instanceof HTMLMediaElement)) return;
  const w = clipWindow(media);
  if (w && clipPastEnd(media, w)) { media.pause(); return; }
  if (w && (media.currentTime < w.start - 0.05
            || (w.end !== null && media.currentTime >= w.end - 0.05)))
    media.currentTime = w.start;
  if (w) watchClipEnd(media);
  if (media.closest(".ex-flashcard"))
    $$(".ex-flashcard audio, .ex-flashcard video").forEach(x => { if (x !== media && !x.paused) x.pause(); });
  // and one recording of an exercise at a time, by the same rule: its
  // question's and its answer's would otherwise sound over each other
  const own = media.closest(".ex-audio") && media.closest(".exercise");
  if (own) $$(".ex-audio audio", own).forEach(x => { if (x !== media && !x.paused) x.pause(); });
  const play = media.parentElement && media.parentElement.querySelector(":scope > .ex-card-play");
  if (play) play.classList.add("playing");
}, true);
document.addEventListener("seeked", e => {
  if (e.target instanceof HTMLMediaElement && !e.target.paused) watchClipEnd(e.target);
}, true);
for (const type of ["pause", "ended", "emptied"]) {
  document.addEventListener(type, e => {
    const media = e.target;
    if (!(media instanceof HTMLMediaElement)) return;
    clearTimeout(media._clipTimer);
    const play = media.parentElement && media.parentElement.querySelector(":scope > .ex-card-play");
    if (play) play.classList.remove("playing");
  }, true);
}

/* A flashcard turned: the other side shown, and whatever was playing on the
   side going out of sight stopped. */
function flipCard(card) {
  const flipped = card.classList.toggle("flipped");
  const front = $(":scope > .ex-card-front", card), back = $(":scope > .ex-card-back", card);
  if (front) front.hidden = flipped;
  if (back) back.hidden = !flipped;
  const hidden = flipped ? front : back;
  if (hidden) $$("audio, video", hidden).forEach(m => m.pause());
  card.setAttribute("aria-pressed", flipped ? "true" : "false");
  const hint = $(":scope > .ex-card-hint", card) || $(":scope > small", card);
  if (hint) hint.textContent = flipped ? "tap to see front" : "tap to reveal";
}

/* A `both-random` card (data-first="random") shows either side first, drawn
   each time it is shown -- here, where it is drawn, and not on the server,
   which would freeze the draw into an export, a study pack and the cached
   cram page.  The two sides swap names, so `.ex-card-front` is still the
   side shown first for everything that reads it (flipCard, the recording
   played first, the enlarged copy).  A card already turned (a preview shows
   both sides) is left as it is, and one drawn once is not drawn again.
   The example, the notes and the source (data-extra) go with the answer, which
   the draw has just changed: each goes to the other side, after that side's
   own fields, and each side keeps them in the order they were drawn in. */
function drawFirstSide(card) {
  if (card.dataset.first !== "random" || card.dataset.drawn || card.classList.contains("flipped")) return;
  card.dataset.drawn = "1";
  const front = $(":scope > .ex-card-front", card), back = $(":scope > .ex-card-back", card);
  if (!front || !back || Math.random() < 0.5) return;
  front.className = "ex-card-back"; back.className = "ex-card-front";
  front.hidden = true; back.hidden = false;
  card.insertBefore(back, front);
  const [fromFront, fromBack] = [front, back].map(side => $$(":scope > [data-extra]", side));
  back.append(...fromFront); front.append(...fromBack);
}

function escAttr(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}

/* Direction is a typing aid for exercise source fields.  `dir=auto` makes
   an existing Persian answer readable on opening, while the adjacent button
   can force either direction for mixed text or an empty field.  It never
   changes the markdown that is saved or the rendered activity's direction. */
function exerciseTextDirectionButton(input) {
  input.dir = "auto";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ex-text-direction";
  const sync = () => {
    const rtl = getComputedStyle(input).direction === "rtl";
    button.textContent = rtl ? "⇥ LTR" : "⇤ RTL";
    button.title = rtl ? "Write this text box left to right" : "Write this text box right to left";
    button.setAttribute("aria-label", button.title);
  };
  input.addEventListener("input", sync);
  button.addEventListener("click", e => {
    e.preventDefault();
    e.stopPropagation();
    input.dir = getComputedStyle(input).direction === "rtl" ? "ltr" : "rtl";
    input.focus();
    sync();
  });
  sync();
  queueMicrotask(sync); // the field is attached after this helper returns
  return button;
}

/* `fields` adds single-line inputs above the textarea; their values reach
   onOk as a third argument, keyed by `key`.  Callers that pass none are
   unaffected. */
function showModal({title, hint, value, okLabel, onOk, onCancel,
                    fields, textarea}) {
  const root = $("#modal-root");
  root.innerHTML = "";
  const ov = document.createElement("div");
  ov.className = "modal-overlay";
  ov.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true">
      <h3></h3><p></p>
      <div class="modal-fields"></div>
      <textarea spellcheck="false"></textarea>
      <div class="row">
        <button class="btn" data-x="cancel">Cancel</button>
        <button class="btn primary" data-x="ok"></button>
      </div>
    </div>`;
  $("h3", ov).textContent = title;
  $("p", ov).textContent = hint || "";
  const fieldBox = $(".modal-fields", ov);
  fieldBox.hidden = !(fields && fields.length);
  for (const f of fields || []) {
    const lab = document.createElement("label");
    lab.className = "modal-field";
    lab.textContent = f.label || f.key;
    const inp = document.createElement("input");
    inp.type = "text";
    inp.spellcheck = false;
    inp.dataset.key = f.key;
    inp.value = f.value || "";
    if (f.placeholder) inp.placeholder = f.placeholder;
    lab.appendChild(inp);
    fieldBox.appendChild(lab);
  }
  const fieldValues = () => Object.fromEntries(
    $$("input[data-key]", fieldBox).map(i => [i.dataset.key, i.value]));
  const ta = $("textarea", ov);
  ta.value = value || "";
  // a dialog made only of single-line fields has nothing to put in it
  if (textarea === false) ta.hidden = true;
  $('[data-x="ok"]', ov).textContent = okLabel || "OK";
  // `onCancel` lets a caller undo whatever it did to open the dialog —
  // a paste, say, that suppressed the browser's own handling of it
  let settled = false;
  const drop = () => { settled = true; if (ov.parentNode) root.removeChild(ov); };
  const close = drop;
  const cancel = () => {
    if (settled) return;
    drop();
    if (onCancel) onCancel();
  };
  ov.addEventListener("click", e => { if (e.target === ov) cancel(); });
  $('[data-x="cancel"]', ov).addEventListener("click", cancel);
  const okBtn = $('[data-x="ok"]', ov);
  let busy = false;
  okBtn.addEventListener("click", async () => {
    if (busy) return;                    // guard against double-submit
    busy = true;
    okBtn.disabled = true;
    $('[data-x="cancel"]', ov).disabled = true;
    try {
      await onOk(ta.value, close, fieldValues());
    } catch (e) {
      toast(e.message, true);
      busy = false;
      okBtn.disabled = false;
      $('[data-x="cancel"]', ov).disabled = false;
    }
  });
  root.appendChild(ov);
  // with extra fields the first of them is where typing starts
  const first = $("input[data-key]", fieldBox);
  (first || ta).focus();
}

/* The toolbar is sticky and wraps to a variable number of rows, so the
   offset an anchor jump has to clear is only known at runtime.  It is
   also recomputed immediately before each jump: an observer can miss a
   reflow that happened while the page was not being rendered, and the
   jump is the one moment the number has to be right. */
let stickyObserver = null;
function measureSticky(target) {
  const bar = $("#typobar");
  if (!bar) return;
  let h = bar.getBoundingClientRect().height + 10;
  if (pinnedPair()) {
    // on a phone the topbar is pinned above the toolbar, so a jump up has
    // both to clear; a jump down puts both away (bindBarHide), and clearing
    // them there would leave the heading halfway down the screen
    const top = $(".topbar");
    h += top ? top.getBoundingClientRect().height : 0;
    if (target) {
      const r = target.getBoundingClientRect();
      if (r.top > 0 && r.top + (window.pageYOffset || 0) - 10 > barsStand()) h = 10;
    }
    h = Math.min(h, window.innerHeight * .6);   // never a margin past the screen
  }
  document.documentElement.style.setProperty("--sticky-h", h + "px");
}
function syncStickyOffset() {
  const bar = $("#typobar");
  if (!bar) return;
  measureSticky();
  if (window.ResizeObserver) {
    stickyObserver = new ResizeObserver(() => measureSticky());   // kept referenced
    stickyObserver.observe(bar);
  }
  window.addEventListener("resize", debounce(() => measureSticky(), 120));
  // A link to a heading, opened on a phone: the browser scrolls to it before
  // anything here runs, with a margin for both bars -- and that scroll, down
  // the page, is what puts both bars away.  So the heading is placed again
  // once the page is laid out, with the margin a jump down has.  Only when
  // the link was followed: a reload or Back puts the reader where they were,
  // and a reader who has touched the page before it finished loading has
  // moved on from the heading.
  const nav = performance.getEntriesByType ? performance.getEntriesByType("navigation")[0] : null;
  if (location.hash && pinnedPair() && (!nav || nav.type === "navigate")) {
    let el = null;
    try { el = document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch (e) { el = null; }
    if (el) {
      const TOUCHES = ["touchstart", "wheel", "keydown", "pointerdown"];
      let moved = false;
      const mark = () => { moved = true; };
      TOUCHES.forEach(t => window.addEventListener(t, mark, {capture: true, passive: true}));
      const place = () => requestAnimationFrame(() => {
        TOUCHES.forEach(t => window.removeEventListener(t, mark, {capture: true}));
        if (moved) return;
        measureSticky(el);
        el.scrollIntoView({block: "start"});
      });
      if (document.readyState === "complete") place();
      else window.addEventListener("load", place, {once: true});
    }
  }
}

/* The toolbar holds the way to the contents and the glosses, and "Aa", which
   opens the gear at its Text group (static/gear.js): the sliders that used to
   open under it, in a row that scrolled sideways, took the finger that meant
   to scroll the row, and moved a setting every document shares.  They are
   rows of a panel now, on a phone a sheet over the foot of the screen. */
/* THE BARS, PUT AWAY BY HAND.  Three of them stand over a reading page --
   the topbar, the tags, the toolbar -- and once the text is set the way
   somebody wants it, they are in the way.  "⌃ hide bars" takes all three off
   and leaves one faint button in the corner ("⌄ show bars"); pressing that
   brings them back.  The gear's "Hide the bars" is the same switch
   (setBarsOff), and says so to the page's own two buttons and to itself.

   Remembered for every document and not for one: it is a way of reading, not
   a property of a page, and a reader who has cleared the window does not want
   it filled again by opening the next note.  A phone's own hiding (barhidden,
   bindBarHide) is the other thing and is untouched: that comes back on the
   smallest move up, this holds until it is undone. */
/* WHETHER A SEQUENCE MAY BE DRAGGED.  Its blocks carry arrows, and on a
   touch screen the arrows are the only thing that works properly: a drag the
   phone never reports as one leaves the block where it was, and the touch
   path that stands in for dragging reads a tap as "put this at the end".  So
   dragging starts turned off where the pointer is a finger -- and because
   that guess is a guess, every such exercise carries a switch that says which
   it is, remembered here for every page this browser opens.  Only sequences:
   an exercise with no arrows has nothing to fall back on, and is never
   touched by this. */
const DRAG_KEY = "parseh_exercise_drag";
// What the reader said on this page, which is the answer wherever there is
// one: a browser that refuses storage (a private window, site data blocked)
// must still obey the switch -- it only forgets it when the page goes.
let dragChoice = null;
function dragIsOn() {
  if (dragChoice !== null) return dragChoice;
  let v = null;
  try { v = localStorage.getItem(DRAG_KEY); } catch (e) { /* private mode */ }
  if (v === "1" || v === "0") return (dragChoice = v === "1");
  // nothing said yet: a coarse pointer is a finger, and a finger drags badly
  return !(window.matchMedia && matchMedia("(pointer: coarse)").matches);
}
// ONE SWITCH, TWO BUTTONS (a0.5.0): the one on an exercise and the gear's
// "Drag to answer" turn the same choice, and every sheet of the page follows
// at once (bindExercises listens for `parseh:studio`) -- a sheet drawn later
// reads the choice when it is bound
function setDragOn(v) {
  dragChoice = !!v;
  try { localStorage.setItem(DRAG_KEY, v ? "1" : "0"); } catch (e) { /* private mode */ }
  document.dispatchEvent(new CustomEvent("parseh:studio", {detail: {what: "drag"}}));
}

const BARS_KEY = "parseh_bars_off";
function barsAreOff() {
  try { return localStorage.getItem(BARS_KEY) === "1"; } catch (e) { return false; }
}
// bindBarsToggle's own `set`, where this page has the two buttons
let barsApply = null;
function setBarsOff(v) { if (barsApply) barsApply(!!v, "gear"); }
function bindBarsToggle() {
  const off = $("#btn-bars"), on = $("#btn-bars-show");
  if (!off || !on) return;
  // `how`: nothing at load, "hand" from the page's own two buttons, "gear" from the gear's switch
  const set = (v, how) => {
    // A bar that goes or comes moves the text under it, and the browser
    // would scroll to keep the text where it was: the phone's scroll
    // watcher must not read that as a reader's move.  Only when a hand
    // moved it, though -- held at load, the watcher would sit out the jump
    // a link to a heading makes, and the bars would stand over it.
    if (how) holdBars(400);
    document.body.classList.toggle("chrome-off", v);
    off.hidden = v;
    on.hidden = !v;
    off.setAttribute("aria-expanded", String(!v));
    on.setAttribute("aria-expanded", String(!v));
    try { localStorage.setItem(BARS_KEY, v ? "1" : "0"); } catch (e) { /* private mode */ }
    measureSticky();               // no bar to clear: a jump lands at the text
    // the focus follows the button that was pressed -- not the gear's switch, which keeps it
    if (how === "hand") (v ? on : off).focus({preventScroll: true});
    document.dispatchEvent(new CustomEvent("parseh:studio", {detail: {what: "bars"}}));
  };
  barsApply = set;
  off.addEventListener("click", () => set(true, "hand"));
  on.addEventListener("click", () => set(false, "hand"));
  set(barsAreOff(), "");
}

/* ---------------- glosses: table + flashcards ----------------

   The list is assembled server-side from the markdown itself (every
   `فارسی = *translation*`), so it stays in step with the document with
   nothing to keep in sync by hand. */

function bindGlosses() {
  const btn = $("#btn-glosses");
  const data = $("#doc-glosses");
  if (!btn || !data) return;
  let items = [];
  try { items = JSON.parse(data.textContent) || []; } catch (e) { items = []; }

  btn.disabled = !items.length;
  const L = lang();
  if (!items.length) {
    btn.title = `This document has no glosses (${L.name} text = *translation*) yet`;
    return;
  }
  btn.title = `${items.length} gloss${items.length === 1 ? "" : "es"} in this document`;

  // Shown on rows whose translation had to be guessed: the source wrote
  // the gloss without italics, so only the single word after the `=`
  // could be taken, and it may well be short of the real translation.
  const GUESS_CLOUD =
    `<span class="gl-warn" role="note"><span class="gl-warn-x">!</span>` +
    `<span class="gl-cloud">Only this one word could be read as the` +
    ` translation. The gloss is written without italics, so where it` +
    ` ends is not marked — write it as` +
    ` <code>فارسی = *translation*</code> and the whole translation will` +
    ` appear here.</span></span>`;

  // Lemma entries come from a `= *…*` on a lemma heading, which is
  // printed nowhere in the document; restricting to them turns the
  // glossary into the document's word list rather than everything it
  // happens to gloss in passing.
  const lemmaCount = items.filter(g => g.lemma).length;

  // one shuffled pass through the deck, so a drill asks every gloss once
  // before any of them comes round again
  function shuffled(pool) {
    const a = pool.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function open() {
    const root = $("#modal-root");
    root.innerHTML = "";
    const ov = document.createElement("div");
    ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal gl-modal" role="dialog" aria-modal="true"
                         aria-label="Glosses">
      <div class="gl-head">
        <h3>Glosses</h3>
        <span class="gl-count"></span>
        <button class="btn ghost gl-x" data-x="close" title="Close (Esc)">✕</button>
      </div>
      <div class="gl-tabs">
        <button class="btn small on" data-tab="list">Table</button>
        <button class="btn small" data-tab="cards">Flashcards</button>
        <button class="btn small gl-lemma" data-x="lemmas" hidden
                title="Only the words that head a lemma entry">Lemmas only</button>
      </div>
      <input class="gl-filter" type="search" placeholder="Filter — ${escAttr(L.name)}, ${L.reading ? escAttr(L.reading_label || "reading") + ", " : ""}${escAttr(L.translit_label)} or translation"
             autocomplete="off" spellcheck="false">
      <div class="gl-body"></div>
      <div class="gl-foot" hidden>
        <span class="gl-progress"></span>
        <button class="btn small grow" data-x="reveal">Show answer</button>
        <button class="btn small primary" data-x="next">Next →</button>
      </div>
    </div>`;

    const body = $(".gl-body", ov);
    const filter = $(".gl-filter", ov);
    const foot = $(".gl-foot", ov);
    const count = $(".gl-count", ov);
    const progress = $(".gl-progress", ov);
    const btnReveal = $('[data-x="reveal"]', ov);
    const btnNext = $('[data-x="next"]', ov);

    let mode = "list", lemmaOnly = false;
    // what both views draw from; the deck holds the entries themselves,
    // so narrowing the pool cannot leave stale indices behind
    const pool = () => lemmaOnly ? items.filter(g => g.lemma) : items;
    let deck = shuffled(pool()), pos = 0, shown = false;
    // null = the order the glosses appear in the text (the default)
    let sortKey = null, sortDir = 1;

    /* The target language collates by its own code, and the translation
       column follows the document's prose language; base sensitivity
       keeps macrons and case from scattering the transliterations (ārām
       next to arnia).  A reading language gets a Reading column between
       the text and the transliteration. */
    const docLang = ($("#sheet") || {}).lang || undefined;
    const collators = {
      fa: new Intl.Collator(L.code, {sensitivity: "base"}),
      kana: new Intl.Collator(L.code, {sensitivity: "base"}),
      translit: new Intl.Collator(undefined, {sensitivity: "base"}),
      tr: new Intl.Collator(docLang, {sensitivity: "base"}),
    };
    const COLS = [{key: "fa", label: L.name}];
    if (L.reading) COLS.push({key: "kana", label: capital(L.reading_label || "reading")});
    COLS.push({key: "translit", label: capital(L.translit_label)},
              {key: "tr", label: "Translation"});
    const SORT_LABEL = {fa: L.name, kana: L.reading_label || "reading",
                        translit: L.translit_label, tr: "translation"};
    ov.firstElementChild.setAttribute("data-lang", L.code);

    function sortRows(rows) {
      if (!sortKey) return rows;             // already in document order
      const cmp = collators[sortKey];
      return rows.slice().sort((a, b) => {
        const x = (a[sortKey] || "").trim(), y = (b[sortKey] || "").trim();
        // a gloss with no transliteration sinks to the bottom either way,
        // rather than heading a column of blanks
        if (!x || !y) return !x && !y ? 0 : (!x ? 1 : -1);
        return cmp.compare(x, y) * sortDir;
      });
    }

    /* click cycles ascending -> descending -> back to document order */
    function cycleSort(key) {
      if (sortKey !== key) { sortKey = key; sortDir = 1; }
      else if (sortDir === 1) { sortDir = -1; }
      else { sortKey = null; sortDir = 1; }
      renderList();
    }

    /* ---- table ---- */
    function renderList() {
      // foldCase on both sides, never toLowerCase: the headword column is
      // target text, and "İyi günler" has to answer to "iyi"
      const q = foldCase(filter.value.trim());
      const rows = sortRows(pool().filter(g => !q
        || foldCase(g.fa).includes(q)
        || foldCase(g.kana).includes(q)
        || foldCase(g.translit).includes(q)
        || foldCase(g.tr).includes(q)));
      const how = sortKey
        ? `by ${SORT_LABEL[sortKey]} ${sortDir === 1 ? "A→Z" : "Z→A"}`
        : "in text order";
      const total = pool().length;
      const scope = lemmaOnly ? "lemmas" : "in this document";
      count.textContent = (q ? `${rows.length} of ${total} ${scope}`
                             : `${total} ${scope}`) + ` · ${how}`;
      if (!rows.length) {
        body.innerHTML = `<div class="gl-empty">Nothing matches “${escAttr(filter.value)}”.</div>`;
        return;
      }
      const head = COLS.map(c => {
        // a column nothing fills (an older document with no transliteration
        // marks) would sort to a no-op — say so instead of pretending
        if (!pool().some(x => (x[c.key] || "").trim()))
          return `<th title="No ${SORT_LABEL[c.key]} in this document">${c.label}</th>`;
        const on = sortKey === c.key;
        const arrow = on ? (sortDir === 1 ? "▲" : "▼") : "";
        const tip = on && sortDir === -1
          ? "Click to go back to the order they appear in the text"
          : `Sort by ${SORT_LABEL[c.key]}`;
        return `<th class="sortable${on ? " on" : ""}" data-sort="${c.key}"
                    tabindex="0" role="button" title="${escAttr(tip)}"
                    aria-sort="${on ? (sortDir === 1 ? "ascending" : "descending") : "none"}"
                >${c.label}<span class="gl-ar">${arrow}</span></th>`;
      }).join("");
      body.innerHTML = `<table class="gl-table${L.dir === "rtl" ? " dir-rtl" : ""}"><thead><tr>${head}</tr></thead>
        <tbody>${rows.map(g => `<tr${g.guessed ? ' class="gl-guessed"' : ""}>
          <td class="gl-fa" lang="${L.code}" dir="${L.dir}">${escAttr(g.fa)}</td>
          ${L.reading ? `<td class="gl-kana" lang="${L.code}">${g.kana ? escAttr(g.kana) : "—"}</td>` : ""}
          <td class="gl-tr">${g.translit ? escAttr(g.translit) : "—"}</td>
          <td class="gl-tx">${escAttr(g.tr)}${g.guessed ? GUESS_CLOUD : ""}</td>
        </tr>`).join("")}</tbody></table>`;
      $$("th.sortable", body).forEach(th => {
        th.addEventListener("click", () => cycleSort(th.dataset.sort));
        th.addEventListener("keydown", e => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            cycleSort(th.dataset.sort);
          }
        });
      });
    }

    /* ---- flashcards ---- */
    function renderCard() {
      const g = deck[pos];
      count.textContent = lemmaOnly ? `${deck.length} lemmas`
                                    : `${deck.length} in this document`;
      progress.textContent = `${pos + 1} / ${deck.length}`;
      btnReveal.textContent = shown ? "Hide answer" : "Show answer";
      body.innerHTML = `<div class="gl-card" role="button" tabindex="0">
        <div class="q" lang="${L.code}" dir="${L.dir}">${escAttr(g.fa)}</div>
        ${shown ? `<div class="a">
             ${g.kana ? `<div class="a-kana" lang="${L.code}">${escAttr(g.kana)}</div>` : ""}
             ${g.translit ? `<div class="a-tr">${escAttr(g.translit)}</div>` : ""}
             <div class="a-tx${g.guessed ? " guessed" : ""}">${escAttr(g.tr)}</div>
             ${g.guessed ? `<div class="a-warn">only the first word — this
                gloss is written without italics</div>` : ""}
           </div>`
          : `<div class="tap">click the card, or press space, to see the answer</div>`}
      </div>`;
      const card = $(".gl-card", body);
      card.addEventListener("click", () => { shown = !shown; renderCard(); });
      card.focus();
    }

    function next() {
      pos += 1;
      if (pos >= deck.length) { deck = shuffled(pool()); pos = 0; }
      shown = false;
      renderCard();
    }

    function setMode(m) {
      mode = m;
      $$('[data-tab]', ov).forEach(b =>
        b.classList.toggle("on", b.dataset.tab === m));
      filter.hidden = m !== "list";
      foot.hidden = m !== "cards";
      if (m === "list") renderList();
      else { shown = false; renderCard(); }
    }

    /* The cloud is positioned in viewport coordinates (the scrolling
       table body would otherwise clip it): put it above the badge when
       there is room, below when there is not, and keep it inside the
       window horizontally. */
    body.addEventListener("mouseover", e => {
      const w = e.target.closest(".gl-warn");
      if (!w || !body.contains(w)) return;
      const cloud = $(".gl-cloud", w);
      if (!cloud) return;
      const r = w.getBoundingClientRect();
      const cw = cloud.offsetWidth, ch = cloud.offsetHeight, gap = 6;
      const top = r.top - ch - gap >= gap ? r.top - ch - gap : r.bottom + gap;
      const left = Math.min(Math.max(gap, r.left),
                            window.innerWidth - cw - gap);
      cloud.style.top = top + "px";
      cloud.style.left = left + "px";
    });

    /* Restrict both views to the words that head a lemma entry.  The
       control is offered only when the document actually has some —
       otherwise it would be a toggle that empties the overlay. */
    const lemmaBtn = $('[data-x="lemmas"]', ov);
    lemmaBtn.hidden = !lemmaCount;
    lemmaBtn.title = `Only the ${lemmaCount} words that head a lemma entry`;
    lemmaBtn.addEventListener("click", () => {
      lemmaOnly = !lemmaOnly;
      lemmaBtn.classList.toggle("on", lemmaOnly);
      deck = shuffled(pool());          // the drill follows the choice
      pos = 0;
      shown = false;
      if (mode === "list") renderList(); else renderCard();
    });

    $$('[data-tab]', ov).forEach(b =>
      b.addEventListener("click", () => setMode(b.dataset.tab)));
    filter.addEventListener("input", renderList);
    btnReveal.addEventListener("click", () => { shown = !shown; renderCard(); });
    btnNext.addEventListener("click", next);

    const close = () => {
      document.removeEventListener("keydown", onKey);
      if (ov.parentNode) root.removeChild(ov);
    };
    function onKey(e) {
      if (e.key === "Escape") { e.preventDefault(); return close(); }
      if (mode !== "cards") return;
      // don't steal the space bar from a focused text field
      if (e.target && /^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
      if (e.key === " ") { e.preventDefault(); shown = !shown; renderCard(); }
      else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); next(); }
    }
    document.addEventListener("keydown", onKey);
    ov.addEventListener("click", e => { if (e.target === ov) close(); });
    $('[data-x="close"]', ov).addEventListener("click", close);

    root.appendChild(ov);
    setMode("list");
    filter.focus();
  }

  btn.addEventListener("click", open);
}

function bindStopServer() {
  $$("#btn-stop").forEach(btn => btn.addEventListener("click", async () => {
    // what is still running is named first, as lib/parseh.js's stopServer
    // does on every other page: stopping cuts it off.  A studio run on its
    // own has no /__activity and gets the plain question.
    let running = [];
    try {
      const r = await fetch("/__activity", {cache: "no-store"});
      if (r.ok) running = (await r.json()).running || [];
    } catch (e) { /* no list here */ }
    const names = running.slice(0, 5).map(e => "  \u2022 " + e.label).join("\n");
    const ask = running.length
      ? `${running.length === 1 ? "1 task is" : running.length + " tasks are"} still running:\n\n`
        + names + `\n\nStopping the server now cuts ${running.length === 1 ? "it" : "them"} off. `
        + "Stop the Parseh server anyway?"
      : "Stop the Parseh server?";
    if (!confirm(ask)) return;
    try { await api("/api/shutdown", {method: "POST"}); } catch (e) { /* dying */ }
    $("#shutdown-overlay").hidden = false;
  }));
}

/* ---------------- typography (reading + preview) ---------------- */

/* `fa` (the target-script scale) has no fixed default: it is the
   language's (defaultScale), and a stored value is honoured only when it
   was set for a language of the same script -- a Persian 1.6 must not
   reach a Japanese document through the global key. */
const TYPO_DEFAULTS = {fa: null, base: 17, lead: 1.45, voce: 3.4,
                       width: 720, justify: true, theme: "paper"};

/* The whole toolbox shares one theme preference -- `parseh_theme`, the ◐
   button on every other page, which cycles light / dark / sepia.  The sheet
   has the same three under its own names (paper, dark, sepia), and it IS the
   shared one: the sheet had a menu of its own once, and a pick made there
   outranked ◐ -- so one page could be dark while the rest of the toolbox was
   light.  There is one control now (◐, or Colours in the gear), and a `theme`
   an older build wrote into `exlex-typo` is not read at all.  `auto`, the
   value before anything is picked, means the system decides between paper
   and dark. */
function sharedSheetTheme() {
  try {
    const s = localStorage.getItem("parseh_theme") || "auto";
    if (s === "dark" || s === "sepia") return s;
    if (s === "light") return "paper";
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "paper";
  } catch (e) { return "paper"; }
}

function loadTypo(id) {
  let t = Object.assign({}, TYPO_DEFAULTS);
  for (const key of ["exlex-typo:global", id ? "exlex-typo:" + id : null]) {
    if (!key) continue;
    try {
      Object.assign(t, JSON.parse(localStorage.getItem(key) || "{}"));
    } catch (e) { /* ignore */ }
  }
  // `themeFollows` says the theme is the toolbox's and not the reader's own
  // (the exported page, which has no ◐, starts from its own instead)
  t.theme = sharedSheetTheme();
  t.themeFollows = true;
  const L = lang();
  // a record written before the script was noted beside the scale is a
  // Persian one (the only language there was), so it keeps its value for
  // an Arabic-script target and is reset, like any other, for the rest
  if (t.faScript === undefined && t.fa > 0) t.faScript = "arabic";
  if (t.fa == null || !(t.fa > 0) || t.faScript !== L.script) t.fa = defaultScale(L);
  t.faScript = L.script;
  return t;
}

function saveTypo(id, t) {
  // the theme is the toolbox's, never the sheet's own: it is not written down
  const out = Object.assign({}, t);
  delete out.theme;
  delete out.themeFollows;
  try {
    localStorage.setItem("exlex-typo:global", JSON.stringify(out));
    if (id) localStorage.setItem("exlex-typo:" + id, JSON.stringify(out));
  } catch (e) { /* private mode */ }
}

function applyTypo(t) {
  $$(".sheet").forEach(sheet => {
    sheet.style.setProperty("--fa-scale", t.fa == null ? defaultScale(lang()) : t.fa);
    sheet.style.setProperty("--voce-scale", t.voce);
    sheet.style.setProperty("--base-size", t.base + "px");
    sheet.style.setProperty("--leading", t.lead);
    sheet.style.setProperty("--sheet-width", t.width + "px");
    sheet.classList.toggle("justify", !!t.justify);
  });
  if (t.theme && t.theme !== "paper") document.body.dataset.theme = t.theme;
  else delete document.body.dataset.theme;
}

/* THE TYPOGRAPHY OF A PAGE, ONE STATE FOR EVERYTHING THAT TOUCHES IT (a0.5.0).
   The text size, the width of the column, the leading, the headwords' size and
   the justifying were five sliders and a tick in the document's own toolbar,
   each bound by hand.  They are rows of the gear now (static/gear.js), the
   edit page has them too, and four of them are on the pages of exercises.  So
   the state is no control's any more: it is the two keys of localStorage
   (loadTypo and saveTypo above) and this object, which reads them afresh at
   every ask -- the other page's change, another tab's, is never one behind --
   applies what it writes to every sheet of the page at once (the reading
   sheet, the editor's preview, an exercise's stage) and tells whoever asked
   (`subscribe`: the gear's rows).  The PDF is built at `get().fa`.  `use(id)`
   names the document the page is of: a document writes its own key as well as
   the shared one, a page of exercises writes the shared one alone. */
const studioTypo = (() => {
  let id = null;
  const subs = new Set();
  const tell = t => subs.forEach(fn => { try { fn(t); } catch (e) { /* the listener's own fault */ } });
  const put = t => { saveTypo(id, t); applyTypo(t); tell(t); return t; };
  return {
    use(docId) { id = docId || null; },
    id: () => id,
    get: () => loadTypo(id),
    set(patch) {
      const t = loadTypo(id), was = t.base;
      Object.assign(t, patch);
      // The column width follows the Latin size through whatever ratio the two
      // hold at the moment (as when the width was in em).  Moving the width
      // itself rebases that ratio: nothing is stored of it, so the next change
      // of the size scales from where the width is NOW, never snapping back to
      // where it "would have been".
      if ("base" in patch && !("width" in patch) && was > 0)
        t.width = Math.max(420, Math.min(1400, t.width / was * t.base));
      return put(t);
    },
    // the PDF's own: what a document starts from, the language's scale for its script
    reset() {
      const L = lang();
      const t = Object.assign({}, TYPO_DEFAULTS, {fa: defaultScale(L), faScript: L.script});
      t.theme = sharedSheetTheme();
      t.themeFollows = true;
      return put(t);
    },
    // worn again and told again: another tab wrote, the language changed, the theme moved
    refresh() { const t = loadTypo(id); applyTypo(t); tell(t); return t; },
    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
  };
})();
window.ParsehStudioTypo = studioTypo;
// a document's own pages remember their typography under its key as well
studioTypo.use(PAGE === "doc" || PAGE === "edit" ? DOC_ID : null);

/* THE THEME OF A STUDIO PAGE, ONE FUNCTION FOR EVERY WAY IT CHANGES (a0.5.0).
   `parseh_theme` is the whole toolbox's one colour setting, and the studio's
   pages paint it on <body> (sheet.css keys its three themes there), not on
   <html> where the toolbox's own pages keep it.  Three things used to write
   it -- the library's and the documents' ◐ (static/mode.js), the decks' ◐
   (static/decks.js) and the sheet's own menu -- each repainting what it
   thought it owned: the documents' ◐ set <html> and left <body> alone, so on
   a phone it turned a glyph and nothing else, and no studio page loaded
   lib/prefs.js, so what the computer knew of the theme never reached it.
   Now there is this: whatever changes the theme -- ◐ on any bar, the gear's
   Colours, another tab (`storage`), the computer bringing a newer value
   (lib/prefs.js says `parseh:pref` for every key it wears), the system
   turning dark while the page follows it -- ends in paintTheme(), which sets
   <html data-theme> the way Parseh.theme.apply() does, dresses <body> and
   every sheet, and gives every ◐ its glyph and its words.  The glyphs, the
   order and the sentence are lib/parseh.js's. */
const THEME_ORDER = ["light", "dark", "sepia"];
const THEME_GLYPH = {light: "○", dark: "●", sepia: "◐"};
function storedTheme() {
  let t = null;
  try { t = localStorage.getItem("parseh_theme"); } catch (e) { /* private mode */ }
  return t === "auto" || THEME_ORDER.includes(t) ? t : "auto";
}
// the palette on the screen: `auto` is whichever of light and dark the system has
function shownTheme() {
  const t = storedTheme();
  if (t !== "auto") return t;
  try { return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
  catch (e) { return "light"; }
}
function paintTheme() {
  const stored = storedTheme(), now = shownTheme();
  if (stored === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", stored);
  studioTypo.refresh();                 // <body data-theme>, every sheet, the gear's rows
  const next = THEME_ORDER[(THEME_ORDER.indexOf(now) + 1) % THEME_ORDER.length];
  $$("[data-parseh-theme]").forEach(b => {
    b.textContent = THEME_GLYPH[now];
    b.title = `theme: ${now}${stored === "auto" ? " (following the system)" : ""} — click for ${next}`;
  });
}
function cycleTheme() {
  const next = THEME_ORDER[(THEME_ORDER.indexOf(shownTheme()) + 1) % THEME_ORDER.length];
  try { localStorage.setItem("parseh_theme", next); } catch (e) { /* private mode */ }
  paintTheme();
}
function bindStudioLook() {
  paintTheme();
  // delegated, so a ◐ a page draws later is wired the moment it exists.  THE GUIDE EMBEDS THIS SCRIPT for its exercises
  // (data-page="guide") and its ◐ is its own (html-guide/assets/guide.js): a second handler on the same button turned
  // every click into two steps of the cycle, so there it is left to the guide
  document.addEventListener("click", e => {
    if (PAGE === "guide") return;
    if (e.target.closest && e.target.closest("[data-parseh-theme]")) cycleTheme();
  });
  addEventListener("storage", e => {
    if (!e.key || e.key === "parseh_theme") paintTheme();
    else if (e.key === "exlex-typo:global" || e.key === "exlex-typo:" + studioTypo.id()) studioTypo.refresh();
  });
  document.addEventListener("parseh:pref", e => {
    if (e.detail && e.detail.key === "parseh_theme") paintTheme();
  });
  // a page brought back from the back-forward cache ran none of its script
  addEventListener("pageshow", e => { if (e.persisted) paintTheme(); });
  if (window.matchMedia) {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const flip = () => { if (storedTheme() === "auto") paintTheme(); };
    if (mq.addEventListener) mq.addEventListener("change", flip);
    else if (mq.addListener) mq.addListener(flip);
  }
}

function bindPersianCopy(container) {
  container.addEventListener("click", async e => {
    if (e.target.closest(".fapal")) return;      // palette clicks aren't copies
    // nor is a click that fills a blank or a match: a word of the bank, a
    // place, a word of a place's cloud -- an answer, not a copy
    if (e.target.closest(".ex-cloud, .ex-bank, .ex-blank, .ex-match-drop")) return;
    const fa = e.target.closest(".fa, .voce-fa");
    if (!fa || !container.contains(fa)) return;
    const text = fa.textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
      toast("Copied: " + (text.length > 40 ? text.slice(0, 40) + "…" : text));
    } catch (err) { toast("Clipboard unavailable", true); }
  });
}

/* Footnote clouds open upwards; flip them below when the top of the
   viewport would clip them, and move them along their line when they
   would stick out of the window at a side (a mark near the edge of a
   phone): --fn-shift, which the cloud's tail undoes to stay on its mark.
   Measured shown, whether a hover or a focus (a tap) shows it. */
function bindFootnoteClouds(container) {
  function place(e) {
    const fn = e.target.closest && e.target.closest(".fn");
    if (!fn || !container.contains(fn) || fn.closest(".ex-zoom-stage")) return;
    const cloud = $(".fncloud", fn);
    if (!cloud) return;
    fn.classList.remove("fn-below");
    cloud.style.removeProperty("--fn-shift");
    cloud.style.display = "block";
    const r = fn.getBoundingClientRect();
    if (r.top < cloud.offsetHeight + 60) fn.classList.add("fn-below");
    const c = cloud.getBoundingClientRect(), right = document.documentElement.clientWidth - 6;
    const dx = c.left < 6 ? 6 - c.left : c.right > right ? right - c.right : 0;
    if (dx) cloud.style.setProperty("--fn-shift", dx + "px");
    cloud.style.display = "";
  }
  container.addEventListener("mouseover", place);
  container.addEventListener("focusin", place);
}

/* Hovering a run of the target language (or a lemma heading) opens its
   linguistic cloud.  `opts.applyTranslit` and `opts.applyKana` write the
   transliteration and, for a
   language with a reading, the kana -- two independent halves of the
   same mark, each with its own field at the head of the cloud.
   `opts.only(span)`, when given, says which runs open the cloud at all;
   `opts.host` is the element the cloud is put in instead of <body>; and
   `opts.onlyHere` marks a page that keeps nothing, which only changes what
   the toasts say -- the cloud itself is the same. */
function bindWordCloud(container, opts) {
  if (!opts) return;
  let pal = null, target = null, hideTimer = null;
  // an open text field pins the cloud and remembers which run it belongs to
  let editPinned = false, trSpan = null;
  // the mark fields the current language has: the reading first (it sits
  // above the transliteration everywhere else), then the transliteration.
  // Resolved when the cloud is built, not when it is bound: the editor
  // swaps the language live as the preview reports another `target:`,
  // and show() rebuilds the cloud when that has happened.
  let MARKS = [];
  // A RUN NAMES ITS OWN LANGUAGE (lang="…" on the span, from the record the
  // page embeds in #langs-json): a page may hold examples of several, and the
  // cloud's fields, labels and face are those of the word it opens on.  A run
  // of the page's own language, or one whose language the page has no full
  // record of, takes the page's -- which is every run of a studio document.
  function langOf(span) {
    const code = span && span.getAttribute && span.getAttribute("lang");
    if (!code || code === lang().code) return lang();
    return LANGS.find(l => l.code === code && l.translit_label) || lang();
  }
  function markFields(L) {
    const out = [];
    if (L.reading && opts.applyKana)
      out.push({kind: "kana", label: L.reading_label || "reading", cls: "kana-edit"});
    out.push({kind: "translit", label: L.translit_label, cls: "translit-edit"});
    return out;
  }

  function build(L) {
    MARKS = markFields(L);
    pal = document.createElement("div");
    pal.className = "fapal";
    pal.setAttribute("data-lang", L.code);
    // the mark fields sit at the head of the cloud: click one to edit,
    // or click + to annotate a run that has none
    pal.innerHTML = MARKS.map(m =>
      `<span class="tr-edit ${m.cls}" data-kind="${m.kind}">` +
        `<button type="button" class="tr-val" hidden` +
        ` title="Click to edit this ${escAttr(m.label)}"></button>` +
        `<button type="button" class="tr-add" hidden` +
        ` title="Add a ${escAttr(m.label)}">+</button>` +
        `<input class="tr-in" hidden spellcheck="false" autocomplete="off"` +
        ` placeholder="${escAttr(m.label)}" aria-label="${escAttr(capital(m.label))}"` +
        `${m.kind === "kana" ? ` lang="${L.code}"` : ""}>` +
      `</span>`).join("");
    MARKS.forEach(bindMarkEditor);
    pal.addEventListener("mouseenter", () => clearTimeout(hideTimer));
    pal.addEventListener("mouseleave", scheduleHide);
    (opts.host || document.body).appendChild(pal);
  }

  // the reading applier is gated on the language at the moment of use: a
  // buffer switched away from Japanese has no reading field to write
  const applier = (kind, span) => kind === "kana"
    ? (langOf(span).reading ? opts.applyKana : null) : opts.applyTranslit;

  /* A mark control: a label that turns into a text field on click, or a
     + when the run carries no annotation yet.  Writing it back is the
     same kind of edit as a colour — it lands in the markdown as
     `[متن]{translit:…}` / `[漢字]{kana:…}` and so reaches the glossary
     and the LLM. */
  function bindMarkEditor(m) {
    const box = $(`.tr-edit[data-kind="${m.kind}"]`, pal);
    const val = $(".tr-val", box), add = $(".tr-add", box),
          input = $(".tr-in", box);

    const open = ev => {
      ev.stopPropagation();
      trSpan = target;
      input.value = val.hidden ? "" : val.textContent;
      val.hidden = add.hidden = true;
      input.hidden = false;
      editPinned = true;
      clearTimeout(hideTimer);
      input.focus();
      input.select();
    };
    val.addEventListener("click", open);
    add.addEventListener("click", open);

    // Enter commits directly rather than by blurring the field: a blur
    // does not fire when the window itself is not focused, and an edit
    // that silently evaporates is worse than one that needs a click.
    let committing = false;
    async function commit(value) {
      if (committing) return;
      committing = true;
      editPinned = false;
      try { await applyMark(m, value); } finally { committing = false; }
    }
    function cancel() {
      editPinned = false;
      showMarks(trSpan);                       // also re-hides the field
      scheduleHide();
    }

    // keystrokes stay inside the field: the page binds ⌘Z, Esc and more
    input.addEventListener("keydown", ev => {
      ev.stopPropagation();
      if (ev.key === "Enter") { ev.preventDefault(); commit(input.value); }
      else if (ev.key === "Escape") { ev.preventDefault(); cancel(); }
    });
    // clicking away commits too; the hidden check keeps that from
    // running again after Enter or Esc already closed the field
    input.addEventListener("blur", () => {
      if (!input.hidden) commit(input.value);
    });
  }

  function currentMark(span, kind) {
    if (!span) return "";
    return span.dataset[kind]
      || (span.parentElement && span.parentElement.dataset[kind]) || "";
  }
  const currentTranslit = span => currentMark(span, "translit");

  function showMarks(span) {
    for (const m of MARKS) {
      const box = $(`.tr-edit[data-kind="${m.kind}"]`, pal);
      const val = $(".tr-val", box), add = $(".tr-add", box),
            input = $(".tr-in", box);
      const v = currentMark(span, m.kind);
      input.hidden = true;
      val.textContent = v;
      // a lemma heading already carries its transliteration and reading
      // in the heading itself (`## فارسی | translit | …`); a second,
      // marked-up copy would be a competing source of truth, so the
      // editor is offered only on ordinary runs
      const editable = !!applier(m.kind, span) && span
        && span.classList.contains("fa");
      val.hidden = !v;
      add.hidden = !!v || !editable;
      val.disabled = !editable;
    }
  }
  const showTranslit = () => showMarks(target);

  async function applyMark(m, value) {
    const span = trSpan;
    const fn = applier(m.kind, span);
    if (!span || !fn) return;
    const v = value.trim(), before = currentMark(span, m.kind);
    if (v === before) { showMarks(span); return scheduleHide(); }
    const body = {text: span.dataset.fa, occurrence: Number(span.dataset.occ)};
    body[m.kind] = v;
    const what = capital(m.label);
    try {
      await fn(body, span);
      showMarks(span);
      toast(opts.onlyHere
        ? (v ? `${what}: ${v}` : `${what} removed`)
        : (v ? `${what} saved: ${v}` : `${what} removed`));
      hide();
    } catch (e) {
      toast(`Could not save the ${m.label}: ` + e.message, true);
      showMarks(span);
    }
  }

  function show(span) {
    // a cloud built for another language is thrown away: its fields, face
    // and labels are that language's (never while a field is open in it)
    const L = langOf(span);
    if (pal && pal.dataset.lang !== L.code && !editPinned) {
      pal.remove();
      pal = null;
    }
    if (!pal) build(L);
    target = span;
    showMarks(span);
    if (![...pal.querySelectorAll(".tr-val, .tr-add, .tr-in")]
        .some(control => !control.hidden)) return hide();
    pal.style.visibility = "hidden";
    pal.style.display = "flex";
    const r = span.getBoundingClientRect();
    const top = r.top + window.scrollY - pal.offsetHeight - 8;
    let left = r.left + window.scrollX + r.width / 2 - pal.offsetWidth / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - pal.offsetWidth - 8));
    pal.style.top = (top < window.scrollY + 4
      ? r.bottom + window.scrollY + 8 : top) + "px";
    pal.style.left = left + "px";
    pal.style.visibility = "visible";
  }

  function hide() {
    if (editPinned) return;   // a field is open in it
    if (pal) pal.style.display = "none";
    target = null;
  }
  function scheduleHide() { hideTimer = setTimeout(hide, 220); }

  container.addEventListener("mouseover", e => {
    const span = e.target.closest(".fa[data-fa], .voce-fa[data-fa]");
    if (!span || !container.contains(span)) return;
    if (opts.only && !opts.only(span)) return;
    clearTimeout(hideTimer);
    if (span !== target) show(span);
  });
  container.addEventListener("mouseout", e => {
    const span = e.target.closest(".fa[data-fa], .voce-fa[data-fa]");
    if (!span) return;
    // Moving between a segmented word and one of its visual children is
    // still inside the same semantic word, and must not start the close
    // timer.  The same guard avoids a synthetic child/parent transition
    // closing an ordinary run's cloud just after it opens.
    if (e.relatedTarget && span.contains(e.relatedTarget)) return;
    scheduleHide();
  });
  window.addEventListener("scroll", hide, {passive: true});
}

/* THE CLOUD ON A PAGE THAT KEEPS NOTHING -- an exported page, and the guide:
   the studio's linguistic cloud, whose marks are written onto this open
   page and nowhere else.  No server is asked and nothing is stored; edits
   are gone with the tab.  `only(span)` picks the runs that open it (the
   guide's: those that carry a transliteration or a reading) and `host` is
   where the cloud is put (the guide's layer, inside the scope its rules
   are written under). */
function bindPageCloud(container, opts) {
  opts = opts || {};
  const mark = kind => (body, span) => {
    const v = (body[kind] || "").trim();
    if (v) span.dataset[kind] = v;
    else delete span.dataset[kind];
    if (span.parentElement && span.parentElement.dataset[kind] && !v)
      delete span.parentElement.dataset[kind];
  };
  bindWordCloud(container, {applyTranslit: mark("translit"),
                            applyKana: mark("kana"), onlyHere: true,
                            only: opts.only, host: opts.host});
}

/* The reading view's appliers: save on the server, then patch the DOM in
   place (wrap/re-class/unwrap inline runs; toggle classes on a lemma). */
/* Hovering the "N FAIL" badge explains what the check is and what a
   failure does and does not mean.  It is pointer-events:none, so it can
   never swallow the click that opens the list of failing strings. */
function verifyCloud() {
  const L = lang();
  const rtl = L.dir === "rtl";
  return `<span class="vfx-cloud">` +
    `<b>${rtl ? "Right-to-left verification." : "Text verification."}</b>` +
    ` After each build every ${escAttr(L.name)} string in the generated` +
    ` <code>.tex</code> is looked for in the finished PDF — read back glyph` +
    ` by glyph, in the order the glyphs actually sit on the page.` +
    (rtl
      ? ` A failure means one of two things: the text never reached the` +
        ` PDF, or its words came out left-to-right, which is the bidi bug` +
        ` this toolchain exists to catch.`
      : ` A failure means the text never reached the PDF as written.`) +
    `<span class="vfx-note"><b>One false alarm is known.</b> A long` +
    ` run may wrap across a line, and a run split over two lines` +
    ` may be reported <i>missing</i> even though it is set correctly. Check a` +
    ` <i>missing</i> on a long run by eye before treating it as real.` +
    `</span><span class="vfx-hint">Click to see which strings failed.</span>` +
    `</span>`;
}

/* Writing a transliteration or a reading into the stored document.  A
   run with no mark yet is bare text in the DOM, so the annotation may
   need a wrapper built around it — and removing the last mark takes it
   away.  `kind` is "translit" or "kana": the endpoint, the request key
   and the data attribute all carry that name. */
function docMarkApplier(docId, kind) {
  return async (body, span) => {
    const data = await api(`/api/docs/${docId}/${kind}`,
                           {method: "POST", json: body});
    if (span.classList.contains("segmented-colour-run")) {
      if (data[kind]) span.dataset[kind] = data[kind];
      else delete span.dataset[kind];
      if (onSourceChanged) onSourceChanged(data.meta);
      return;
    }
    let wrap = span.parentElement;
    const wrapped = wrap && wrap.classList.contains("fac");
    if (data[kind]) {
      if (!wrapped) {
        wrap = document.createElement("span");
        wrap.className = "fac";
        span.replaceWith(wrap);
        wrap.appendChild(span);
      }
      wrap.dataset[kind] = data[kind];
    } else if (wrapped) {
      delete wrap.dataset[kind];
      // nothing left to hold: no colour and no other mark
      if (!wrap.dataset.color && !wrap.dataset.translit && !wrap.dataset.kana)
        wrap.replaceWith(span);
    }
    if (onSourceChanged) onSourceChanged(data.meta);
  };
}
const docTranslitApplier = docId => docMarkApplier(docId, "translit");

let onSourceChanged = null;

/* ---- clipped YouTube embeds: make every play the same snippet -------
   The embed honours start/end only on the FIRST playback.  Each clipped
   player is registered with the iframe's postMessage protocol (no
   external script); when it reports `ended`, the iframe is reloaded, so
   the clip is re-armed for the next play. */
const clipRegistry = new Map();     // listener id -> figure
let clipSeq = 0;

function videoSrc(fig) {
  const qs = ["rel=0"];
  if (fig.dataset.start !== "") qs.push("start=" + fig.dataset.start);
  if (fig.dataset.end !== "") qs.push("end=" + fig.dataset.end);
  if (fig.dataset.start !== "" || fig.dataset.end !== "")
    qs.push("enablejsapi=1");
  return `https://www.youtube-nocookie.com/embed/${fig.dataset.vid}?`
    + qs.join("&");
}

function armClipReplay(container) {
  $$("figure.video", container).forEach(fig => {
    if (fig.dataset.start === "" && fig.dataset.end === "") return;
    const ifr = $("iframe", fig);
    if (!ifr || ifr.dataset.clipArmed) return;
    ifr.dataset.clipArmed = "1";
    const id = "exlex-clip-" + (++clipSeq);
    clipRegistry.set(id, fig);
    const hello = () => {
      try {
        ifr.contentWindow.postMessage(
          JSON.stringify({event: "listening", id}), "*");
      } catch (e) { /* iframe not ready yet */ }
    };
    ifr.addEventListener("load", () => {
      hello();                       // the player script needs a moment
      setTimeout(hello, 700);
      setTimeout(hello, 2000);
    });
    hello();
    setTimeout(hello, 700);
    setTimeout(hello, 2000);
  });
}

window.addEventListener("message", e => {
  if (typeof e.data !== "string" ||
      !/^https:\/\/www\.youtube/.test(e.origin)) return;
  let d;
  try { d = JSON.parse(e.data); } catch (err) { return; }
  if (d.event !== "infoDelivery" || !d.info || d.info.playerState !== 0)
    return;                          // 0 = ended
  const fig = clipRegistry.get(d.id);
  if (!fig) return;
  if (fig.dataset.start === "" && fig.dataset.end === "") return;
  const ifr = $("iframe", fig);
  if (ifr) ifr.src = videoSrc(fig);  // reload re-arms start/end
});

/* Clicking an image opens a layout panel: width, alignment, and a
   horizontal shift in percentage points of the column width.  Every
   change is written into the image's attribute block in the markdown,
   so the PDF lays the figure out identically.  A video and a recording
   take a clip too (start and end; a recording's to the hundredth).  A
   figure on a flashcard has no layout of its own: a click there turns
   the card. */
function bindImageLayout(container, opts) {
  if (!opts || !opts.save) return {close: () => {}};
  let panel = null, fig = null, queue = Promise.resolve();

  const mlOf = (w, align, off) => {
    const base = align === "center" ? (100 - w) / 2
               : align === "right" ? 100 - w : 0;
    return Math.max(-25, Math.min(base + off, 125));
  };
  const kindOf = f => f.classList.contains("video") ? "video"
                    : f.classList.contains("audio") ? "audio" : "image";
  const KIND_NAME = {image: "Image", video: "Video", audio: "Recording"};
  const state = () => ({
    width: +fig.dataset.width, align: fig.dataset.align,
    offset: +fig.dataset.offset,
  });

  function build() {
    panel = document.createElement("div");
    panel.className = "imgpanel";
    panel.innerHTML = `
      <div class="panel-head"><span>Image layout</span>
        <button type="button" data-x="close" title="Close (Esc)">✕</button></div>
      <div class="row2"><label>Width</label>
        <input type="range" data-k="width" min="10" max="100" step="1">
        <output data-o="width"></output></div>
      <div class="row2"><label>Shift</label>
        <input type="range" data-k="offset" min="-50" max="50" step="1">
        <output data-o="offset"></output></div>
      <div class="row2"><label>Align</label><div class="aligns">
        <button type="button" data-a="left">left</button>
        <button type="button" data-a="center">center</button>
        <button type="button" data-a="right">right</button></div></div>
      <div class="row2 times-row" hidden><label>Clip</label><div class="times">
        <input data-t="start" placeholder="start"> –
        <input data-t="end" placeholder="end"></div></div>
      <div class="hint2">Saved into the markdown — the PDF uses the same layout.</div>`;
    $('[data-x="close"]', panel).addEventListener("click", close);
    $$(".times input", panel).forEach(inp =>
      inp.addEventListener("change", () => {
        const frac = kindOf(fig) === "audio";
        const v = parseClock(inp.value, frac);
        if (inp.value.trim() && v === null) {
          toast(frac ? "Time as seconds or m:ss, to the hundredth (e.g. 65.25 or 1:05.25)"
                     : "Time as seconds or m:ss (e.g. 90 or 1:30)", true);
          inp.value = fmtClock(fig.dataset[inp.dataset.t], frac);
          return;
        }
        fig.dataset[inp.dataset.t] = v === null ? "" : v;
        inp.value = fmtClock(v, frac);
        persist();
      }));
    for (const k of ["width", "offset"]) {
      const sl = $(`[data-k="${k}"]`, panel);
      sl.addEventListener("input", () => {          // live while dragging
        const s = state(); s[k] = +sl.value; apply(s);
      });
      sl.addEventListener("change", persist);       // save on release
    }
    $$(".aligns button", panel).forEach(b =>
      b.addEventListener("click", () => {
        const s = state(); s.align = b.dataset.a; apply(s); persist();
      }));
    document.body.appendChild(panel);
  }

  function apply(s) {
    const kind = kindOf(fig);
    fig.dataset.width = s.width;
    fig.dataset.align = s.align;
    fig.dataset.offset = s.offset;
    fig.style.width = s.width + "%";
    fig.style.marginLeft = mlOf(s.width, s.align, s.offset).toFixed(2) + "%";
    fig.className = "img align-" + s.align + " img-editing"
      + (kind === "image" ? "" : " " + kind);
    $('[data-k="width"]', panel).value = s.width;
    $('[data-k="offset"]', panel).value = s.offset;
    $('[data-o="width"]', panel).textContent = s.width + "%";
    $('[data-o="offset"]', panel).textContent =
      (s.offset > 0 ? "+" : "") + s.offset + "%";
    $$(".aligns button", panel).forEach(b =>
      b.classList.toggle("on", b.dataset.a === s.align));
  }

  function refreshVideo(f) {
    const ifr = $("iframe", f);
    if (ifr) ifr.src = videoSrc(f);
    armClipReplay(f.parentNode || document);  // a video that just gained
  }                                           // a clip needs its listener

  // the recording's own media fragment follows its window, so its player
  // shows the start before it is played (the window itself is kept by the
  // play listener); a change of width or alignment leaves it alone
  function refreshAudio(f) {
    const a = $("audio", f);
    if (!a) return;
    const has = v => v !== undefined && v !== "";
    const {start, end} = f.dataset;
    const frag = has(start) || has(end)
      ? "#t=" + (has(start) ? start : 0) + (has(end) ? "," + end : "") : "";
    const src = (a.getAttribute("src") || "").replace(/#.*$/, "") + frag;
    if (a.getAttribute("src") !== src) a.setAttribute("src", src);
  }

  function persist() {
    const target = fig;
    const kind = kindOf(target);
    queue = queue.then(async () => {
      const s = {index: +target.dataset.idx,
                 width: +target.dataset.width,
                 align: target.dataset.align,
                 offset: +target.dataset.offset};
      if (kind !== "image") {
        const time = v => v === undefined || v === "" ? null : +v;
        s.start = time(target.dataset.start);
        s.end = time(target.dataset.end);
      }
      await opts.save(s, target);
      if (kind === "video") refreshVideo(target);
      if (kind === "audio") refreshAudio(target);
      toast(KIND_NAME[kind] + " layout saved in the markdown");
    }).catch(e => toast("Layout not saved: " + e.message, true));
  }

  function place() {
    const r = fig.getBoundingClientRect();
    panel.style.display = "block";
    let top = r.top + window.scrollY - panel.offsetHeight - 10;
    if (top < window.scrollY + 8) top = r.bottom + window.scrollY + 10;
    let left = r.left + window.scrollX;
    left = Math.max(8, Math.min(left, window.innerWidth - panel.offsetWidth - 8));
    panel.style.top = top + "px";
    panel.style.left = left + "px";
  }

  function open(f) {
    if (!panel) build();
    if (fig) fig.classList.remove("img-editing");
    fig = f;
    const kind = kindOf(f), frac = kind === "audio";
    $(".panel-head span", panel).textContent = KIND_NAME[kind] + " layout";
    $(".times-row", panel).hidden = kind === "image";
    if (kind !== "image") {
      const unit = frac ? "seconds or m:ss, to the hundredth" : "seconds or m:ss";
      $('[data-t="start"]', panel).title = `Start time — ${unit}; empty = from the beginning`;
      $('[data-t="end"]', panel).title = `End time — ${unit}; empty = to the end`;
      $('[data-t="start"]', panel).value = fmtClock(f.dataset.start, frac);
      $('[data-t="end"]', panel).value = fmtClock(f.dataset.end, frac);
    }
    apply(state());
    place();
  }
  function close() {
    if (panel) panel.style.display = "none";
    if (fig) fig.classList.remove("img-editing");
    fig = null;
  }

  container.addEventListener("click", e => {
    const btn = e.target.closest(".video-edit, .audio-edit");
    if (btn && container.contains(btn) && !btn.closest(".ex-flashcard")) {
      e.preventDefault();
      open(btn.closest("figure.img"));
      return;
    }
    const f = e.target.closest("figure.img");
    if (!f || !container.contains(f) || f.closest(".ex-flashcard")) return;
    // videos and recordings open via their ⚙ handle or caption (the player
    // takes the clicks on itself); images open on any click
    if (f.classList.contains("video") || f.classList.contains("audio")) {
      if (e.target.closest("figcaption")) open(f);
      return;
    }
    e.preventDefault();
    open(f);
  });
  document.addEventListener("click", e => {
    if (fig && !fig.contains(e.target) && !e.target.closest(".imgpanel"))
      close();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && fig) close();
  });
  window.addEventListener("resize", () => { if (fig) place(); });
  return {close};
}

/* Clicking a [ … ]{la} block opens its layout panel: width, sideways
   shift and text alignment (the image knobs) plus a background tint.
   Every change is written into the block's attribute marker. */
function bindLaLayout(container, opts) {
  if (!opts || !opts.save) return {close: () => {}};
  let panel = null, blk = null, queue = Promise.resolve();

  const state = () => ({
    width: +blk.dataset.laWidth, offset: +blk.dataset.laOffset,
    align: blk.dataset.laAlign, bg: blk.dataset.laBg,
  });

  function build() {
    panel = document.createElement("div");
    panel.className = "imgpanel";
    panel.innerHTML = `
      <div class="panel-head"><span>Block layout</span>
        <button type="button" data-x="close" title="Close (Esc)">✕</button></div>
      <div class="row2"><label>Width</label>
        <input type="range" data-k="width" min="10" max="100" step="1">
        <output data-o="width"></output></div>
      <div class="row2"><label>Shift</label>
        <input type="range" data-k="offset" min="-50" max="50" step="1">
        <output data-o="offset"></output></div>
      <div class="row2"><label>Text</label><div class="aligns">
        <button type="button" data-a="left">left</button>
        <button type="button" data-a="center">center</button>
        <button type="button" data-a="right">right</button></div></div>
      <div class="row2 bgsel"><label>Backg.</label>
        <select data-k="bg">
          <option value="">none</option>
          <option value="quote">quote</option>
          <option value="sand">sand</option>
          <option value="rose">rose</option>
          <option value="sage">sage</option>
          <option value="lilac">lilac</option>
        </select></div>
      <div class="hint2">Saved into the markdown — the PDF uses the same layout.</div>`;
    $('[data-x="close"]', panel).addEventListener("click", close);
    for (const k of ["width", "offset"]) {
      const sl = $(`[data-k="${k}"]`, panel);
      sl.addEventListener("input", () => {
        const s = state(); s[k] = +sl.value; apply(s);
      });
      sl.addEventListener("change", persist);
    }
    $$(".aligns button", panel).forEach(b =>
      b.addEventListener("click", () => {
        const s = state(); s.align = b.dataset.a; apply(s); persist();
      }));
    $('[data-k="bg"]', panel).addEventListener("change", ev => {
      const s = state(); s.bg = ev.target.value; apply(s); persist();
    });
    document.body.appendChild(panel);
  }

  function apply(s) {
    blk.dataset.laWidth = s.width;
    blk.dataset.laOffset = s.offset;
    blk.dataset.laAlign = s.align;
    blk.dataset.laBg = s.bg;
    if (s.width === 100 && s.offset === 0) {
      blk.style.width = ""; blk.style.marginLeft = "";
    } else {
      blk.style.width = s.width + "%";
      blk.style.marginLeft =
        Math.max(-25, Math.min(s.offset, 125)).toFixed(2) + "%";
    }
    blk.className = "la-par align-" + s.align
      + (s.bg ? " rtl-bg-" + s.bg : "") + " img-editing";
    $('[data-k="width"]', panel).value = s.width;
    $('[data-k="offset"]', panel).value = s.offset;
    $('[data-o="width"]', panel).textContent = s.width + "%";
    $('[data-o="offset"]', panel).textContent =
      (s.offset > 0 ? "+" : "") + s.offset + "%";
    $('[data-k="bg"]', panel).value = s.bg;
    $$(".aligns button", panel).forEach(b =>
      b.classList.toggle("on", b.dataset.a === s.align));
  }

  function persist() {
    const target = blk;
    queue = queue.then(async () => {
      const content = target.dataset.laSrc;
      const same = $$(".la-par", container)
        .filter(x => x.dataset.laSrc === content);
      const s = {content, occurrence: Math.max(0, same.indexOf(target)),
                 width: +target.dataset.laWidth,
                 offset: +target.dataset.laOffset,
                 align: target.dataset.laAlign,
                 bg: target.dataset.laBg};
      await opts.save(s, target);
      toast("Block layout saved in the markdown");
    }).catch(e => toast("Layout not saved: " + e.message, true));
  }

  function place() {
    const r = blk.getBoundingClientRect();
    panel.style.display = "block";
    let top = r.top + window.scrollY - panel.offsetHeight - 10;
    if (top < window.scrollY + 8) top = r.bottom + window.scrollY + 10;
    panel.style.top = top + "px";
    panel.style.left = Math.max(8, Math.min(
      r.left + window.scrollX,
      window.innerWidth - panel.offsetWidth - 8)) + "px";
  }

  function open(el) {
    if (!panel) build();
    if (blk) blk.classList.remove("img-editing");
    blk = el;
    apply(state());
    place();
  }
  function close() {
    if (panel) panel.style.display = "none";
    if (blk) blk.classList.remove("img-editing");
    blk = null;
  }

  container.addEventListener("click", e => {
    const el = e.target.closest(".la-par");
    // a block on a flashcard is part of the card: a click there turns it
    if (!el || !container.contains(el) || el.closest(".ex-flashcard")) return;
    if (e.target.closest("a, .fa, .fnref")) return;   // links/copy still work
    e.preventDefault();
    open(el);
  });
  document.addEventListener("click", e => {
    if (blk && !e.target.closest(".la-par") && !e.target.closest(".imgpanel"))
      close();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && blk) close();
  });
  window.addEventListener("resize", () => { if (blk) place(); });
  return {close};
}

/* Upload helper shared by the editor's button, drag-drop and manager. */
/* `name` overrides the file's own — a pasted figure has no filename of
   its own, so one is asked for.  Only the stem matters: the server sniffs
   the bytes and appends the extension that actually matches them. */
async function uploadImage(docId, file, name) {
  return working(file.size > BIG_UPLOAD && `Uploading ${name || file.name}`, async act => {
    const r = await fetch(act.url(
      BASE + `/api/docs/${docId}/images?name=` + encodeURIComponent(name || file.name)),
      {method: "POST", body: file});
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || r.statusText);
    return data;
  });
}

/* Its twin for a recording, into the document's audio/ folder: the server
   names it by its bytes as it does a picture -> {name, path, url}. */
async function uploadAudio(docId, file, name) {
  return working(file.size > BIG_UPLOAD && `Uploading ${name || file.name}`, async act => {
    const r = await fetch(act.url(
      BASE + `/api/docs/${docId}/audio?name=` + encodeURIComponent(name || file.name)),
      {method: "POST", body: file});
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || r.statusText);
    return data;
  });
}

/* A document's file keeps its address when it is deleted, and when another
   is uploaded under its name; and a page keeps drawing what it once loaded
   from an address for as long as it lives, whatever the server says since:
   a picture deleted with ✕ went on showing in the editor's preview, and one
   uploaded in its place showed the old picture, until the page was
   reloaded.  So a name this page deletes gets a mark, and the preview asks
   for a marked file under an address carrying it (freshMedia), which the
   page never loaded while the file was there: it shows the file missing,
   and then whatever is uploaded under the name, since an address that
   failed is asked for again.  Any other file keeps its plain address.  The
   server reads no query on a file's route. */
const MEDIA_CHANGED = new Map();          // "images/cat.png" -> its mark
let mediaSerial = 0;
function mediaChanged(path) {
  MEDIA_CHANGED.set(path, String(++mediaSerial));
}
function freshMedia(root, docId) {
  if (!MEDIA_CHANGED.size || !docId) return;
  const own = `/media/${docId}/`;
  for (const el of root.querySelectorAll("img[src], audio[src]")) {
    const src = el.getAttribute("src"), cut = src.search(/[?#]|$/);
    const at = src.lastIndexOf(own, cut);
    if (at < 0 || src[cut] === "?") continue;
    const path = src.slice(at + own.length, cut);
    // a PDF figure is drawn through its x.pdf.svg twin
    const mark = MEDIA_CHANGED.get(path)
      || (/\.pdf\.svg$/i.test(path) && MEDIA_CHANGED.get(path.slice(0, -4)));
    if (mark) el.setAttribute("src", src.slice(0, cut) + "?v=" + mark + src.slice(cut));
  }
}

/* ---------------- primitive-driven exercises -----------------------
   What an exercise IS on the page: how it is drawn and how it is answered.
   Every page that shows an exercise needs this -- a document being read, a
   deck, studying, cramming.  What WRITES one (the exercise form) is in
   static/editor.js, which the edit page alone loads. */

// The picker names pedagogical activities.  Their editors below share a few
// repeatable form controls, but never ask the author to understand the four
// implementation primitives or the Markdown wire format.
const EXERCISE_DEFINITIONS = [
  {label: "Fill in blanks", subtype: "fill-blanks", editor: "fill",
   description: "Build a sentence from ordinary text, blank spaces, and movable distractors."},
  {label: "Embedded vocabulary flashcard", subtype: "flashcard", cardType: "vocab", editor: "flashcard",
   description: "A self-checked vocabulary card inside the page."},
  {label: "Order sentences", subtype: "order-sentences", editor: "order",
   description: "Enter the sentences in their correct final order."},
  {label: "Match translations", subtype: "match-translations", editor: "matching",
   description: "Pair words, phrases, or sentences with their translations."},
  {label: "Match opposites", subtype: "match-opposites", editor: "matching",
   description: "Pair each word or expression with its opposite."},
  {label: "Match definitions", subtype: "match-definitions", editor: "matching",
   description: "Pair words with definitions in either direction."},
  {label: "Yes / No questions", subtype: "yes-no", editor: "boolean",
   description: "Add one or more questions whose answer is Yes or No."},
  {label: "True / False questions", subtype: "true-false", editor: "boolean",
   description: "Add one or more statements to judge True or False."},
  {label: "Choose one answer", subtype: "single-choice", editor: "choice",
   description: "Provide alternatives and mark exactly one as correct."},
  {label: "Construct a sentence", subtype: "construct-sentence", editor: "order",
   description: "Enter words or chunks in the correct final sequence."},
  {label: "Identify the incorrect part", subtype: "incorrect-part", editor: "choice",
   description: "Split a sentence into segments and mark the segment containing the error."},
  {label: "Choose all correct answers", subtype: "choose-all", editor: "choice",
   description: "Provide alternatives and mark every valid answer."},
  {label: "Odd one out", subtype: "odd-one-out", editor: "choice",
   description: "Provide a group and mark the one item that does not belong."},
  {label: "Embedded opposites flashcard", subtype: "flashcard", cardType: "opposites", editor: "flashcard",
   description: "A self-checked card with a word on one side and its opposite on the other."},
  {label: "Embedded Jolly flashcard", subtype: "flashcard", cardType: "jolly", editor: "flashcard",
   description: "A self-checked card with a primary and secondary field on each side."},
  {label: "Follow-up questions", subtype: "follow-up", editor: "chain",
   description: "A chain of exercises answered one after the other; a step may build on the one before."},
];

const TRANSLITERATION_VISIBILITY_KEY = "parseh_exercise_hide_transliteration";
let hideExerciseTransliterations = false;
try { hideExerciseTransliterations = localStorage.getItem(TRANSLITERATION_VISIBILITY_KEY) === "1"; }
catch (e) { /* private pages keep the choice until this page closes */ }

/* THE TRANSLITERATIONS' SWITCH, TURNED IN ONE PLACE (a0.5.0).  A flashcard's
   own button (.ex-translit-switch, in its head) and the gear's "Hide
   transliterations" are the same choice, kept under the one key for every
   page this browser opens, and each of them says it to the other
   (`parseh:studio`).  The class on <body> is what hides the line, so it
   works on a page that has no exercise yet and on every sheet drawn later;
   the buttons on the cards are worded to match wherever there are any. */
function showTransliterationChoice() {
  document.body.classList.toggle("ex-hide-transliteration", hideExerciseTransliterations);
  $$(".ex-translit-switch").forEach(button => {
    button.textContent = hideExerciseTransliterations ? "Show transliterations" : "Hide transliterations";
    button.setAttribute("aria-pressed", String(hideExerciseTransliterations));
    button.title = "Apply to all exercise flashcards";
  });
}
function setTransliterationsHidden(v) {
  hideExerciseTransliterations = !!v;
  try { localStorage.setItem(TRANSLITERATION_VISIBILITY_KEY, hideExerciseTransliterations ? "1" : "0"); }
  catch (err) { /* page-local choice still works */ }
  showTransliterationChoice();
  document.dispatchEvent(new CustomEvent("parseh:studio", {detail: {what: "transliteration"}}));
}

function bindExercises(container, opts = {}) {
  // EVERY PIECE OF RENDERED HTML IN THIS TOOLBOX COMES PAST HERE -- the
  // document page, the editor's preview, the exercise form's stage, a deck
  // row, the study stage, the solution sheet, and the card kit's iframe,
  // which loads this file for exactly that reason.  So a formula is drawn
  // in one place rather than in seven, and a site added later gets it
  // without anybody remembering to.  Nothing waits on it: it is drawn
  // while the rest of this binds.
  if (window.ParsehMath) ParsehMath.typeset(container);
  if (container._parsehExercises) container._parsehExercises.abort();
  const controller = new AbortController();
  container._parsehExercises = controller;
  const listen = (el, type, fn, options = {}) =>
    el.addEventListener(type, fn, Object.assign({}, options, {signal: controller.signal}));
  const preview = !!opts.preview;
  /* A FOLLOW-UP IS AN `.exercise` HOLDING `.exercise`S (its steps).  `everything` is what the caller is given, in
     the order of the page -- a follow-up, then its steps; `exercises` is what has answers, drops and blocks of its
     own: every one but a follow-up, whose steps would otherwise be found twice by a search below it. */
  const everything = $$(".exercise", container);
  /* a follow-up that needs attention (a step wrong, a fence lost) is drawn as any exercise that does: its list of
     what is wrong, with none of a chain's markup, so it has nothing to bind */
  const isChain = ex => ex.dataset.primitive === "chain" && ex.classList.contains("ex-chain");
  const exercises = everything.filter(ex => !isChain(ex));
  if (!everything.length) return {judge: () => false, exercises: [], chains: []};
  $$(".ex-flashcard[data-first]", container).forEach(drawFirstSide);

  showTransliterationChoice();
  listen(container, "click", e => {
    const button = e.target.closest(".ex-translit-switch");
    if (!button || !container.contains(button)) return;
    e.preventDefault();
    e.stopPropagation();
    setTransliterationsHidden(!hideExerciseTransliterations);
  });

  const shuffled = a => {
    a = a.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  };
  const shuffleInto = el => shuffled([...el.children]).forEach(x => el.appendChild(x));

  function clearFeedback(ex) {
    if (preview) return;
    ex.classList.remove("correct", "incorrect");
    $$(".answer-correct,.answer-wrong,.answer-missed", ex).forEach(x =>
      x.classList.remove("answer-correct", "answer-wrong", "answer-missed"));
    $$(".ex-explanation", ex).forEach(why => {
      why.hidden = true; why.classList.remove("success", "error");
    });
    $$(".ex-image-answer", ex).forEach(img => { img.hidden = true; });
    // and the recording kept for the answer, which is stopped as it goes:
    // a player hidden while it plays would go on sounding out of nowhere
    $$(".ex-audio-answer", ex).forEach(box => {
      box.hidden = true;
      $$("audio", box).forEach(a => { if (!a.paused) a.pause(); });
    });
    const score = $("[data-exercise-results] .ex-score", container);
    if (score) { score.hidden = true; score.textContent = "Answers changed — check again"; }
  }

  function bankFor(ex) { return $(".ex-bank[data-bank]", ex); }
  function moveItem(item, drop, anchor) {
    if (!item || !drop || item.closest(".exercise") !== drop.closest(".exercise")) return;
    const ex = drop.closest(".exercise"), bank = bankFor(ex);
    if (drop.dataset.drop === "slot" || drop.dataset.drop === "match") {
      const old = $(".ex-item", drop);
      if (old && old !== item && bank) bank.appendChild(old);
      drop.appendChild(item);
    } else if (drop.dataset.drop === "sequence") {
      if (anchor && anchor !== item) drop.insertBefore(item, anchor);
      else drop.appendChild(item);
    } else if (drop.dataset.bank && bank) {
      bank.appendChild(item);
    }
    item.classList.remove("picked");
    clearFeedback(ex);
    $$(".ex-sequence", ex).forEach(markEnds);
  }

  /* THE ARROWS: a box moved one place, without dragging it.  Dragging is
     what a mouse does best and a touch screen worst -- a drag the page never
     sees as one leaves the box where it was, or drops it at the end -- so
     every box in a sequence carries two arrows, and they are also the way
     through from the keyboard.  What they do is what a drag does, and it is
     recorded the same way: the answer is the order of the boxes, and any
     move unsettles the mark the exercise was given. */
  function moveAlong(item, by) {
    const seq = item && item.parentElement;
    if (!seq || seq.dataset.drop !== "sequence") return;
    const kin = $$(".ex-item", seq), i = kin.indexOf(item), j = i + by;
    if (i < 0 || j < 0 || j >= kin.length) return;
    // insertBefore with the neighbour, or with what follows it: the two
    // boxes change places, and nothing else in the order moves
    seq.insertBefore(item, by < 0 ? kin[j] : kin[j].nextElementSibling);
    clearFeedback(seq.closest(".exercise"));
    markEnds(seq);
  }

  /* A block of a sequence: the only kind the switch governs, and the only
     kind with arrows to fall back on. */
  const inSequence = item => !!item && !!item.parentElement
    && item.parentElement.dataset.drop === "sequence";
  const mayDrag = item => !inSequence(item) || dragIsOn();

  /* The switch, and what it does: every sequence on the page follows it at
     once, and so does every page opened afterwards. */
  function applyDrag() {
    const on = dragIsOn();
    exercises.forEach(ex => {
      const seq = $(".ex-sequence", ex);
      if (!seq) return;
      ex.classList.toggle("no-drag", !on);
      $$(".ex-item", seq).forEach(item => { item.draggable = on; });
      const sw = $(".ex-drag-switch", ex);
      if (!sw) return;
      sw.hidden = false;
      sw.textContent = on ? "✥ dragging on" : "✥ dragging off";
      sw.setAttribute("aria-pressed", on ? "true" : "false");
      sw.title = on
        ? "Blocks can be dragged as well as moved with their arrows. Press to use the arrows alone."
        : "Only the arrows move the blocks, which is what a touch screen does well. Press to allow dragging too.";
    });
  }

  /* An arrow at the end of the line has nowhere to go and says so.  Run
     after every move, whoever made it -- a drag, a tap, an arrow, the
     shuffle that opens the exercise. */
  function markEnds(seq) {
    if (!seq || seq.dataset.drop !== "sequence") return;
    const kin = $$(".ex-item", seq);
    kin.forEach((item, i) => {
      const back = $('.ex-move[data-move="earlier"]', item);
      const on = $('.ex-move[data-move="later"]', item);
      if (back) back.disabled = i === 0;
      if (on) on.disabled = i === kin.length - 1;
    });
  }

  // Sentence chunks flow across rows, unlike ordered sentences. Work out
  // whether the pointer means "before" in the sequence's visual direction;
  // an RTL flex row starts on the right, while vertical lists still use Y.
  function sequenceAnchor(drop, over, clientX, clientY) {
    if (!over || over.parentElement !== drop) return null;
    const rect = over.getBoundingClientRect();
    if (drop.classList.contains("ex-sequence-inline")) {
      const rtl = getComputedStyle(drop).direction === "rtl";
      const before = rtl ? clientX > rect.left + rect.width / 2
                         : clientX < rect.left + rect.width / 2;
      return before ? over : over.nextElementSibling;
    }
    return clientY < rect.top + rect.height / 2
      ? over : over.nextElementSibling;
  }

  /* A BLANK OR A MATCH: THE PLACE FIRST, THEN WHAT GOES IN IT.  A word is
     taken from the bank and put where it goes -- a fill-in's blank, the
     place beside a matching exercise's term -- dragged, or tapped and then
     its place tapped; or the other way round.  A click (a tap) on a blank,
     or on a match's place, opens a cloud beside it holding a copy of
     everything the bank holds now; a click on one puts it there -- the same
     move a drop makes (moveItem), so what was there goes back to the bank,
     and checking is as it always was.  A filled place's cloud can empty it.
     A click anywhere else, or Escape, puts the cloud away.  The cloud hangs
     inside the exercise, so the exercise redrawn or checked takes it with
     it.  (An ordering exercise has no such places: its blocks move by their
     arrows.)

     Every interface has the cloud; the browser keeps the other ways beside
     it -- a word dragged, or picked and then its place clicked, which puts
     the picked word there rather than opening the cloud.  On a phone
     neither goes smoothly -- a drag the page does not see as one, two taps
     a screen apart -- so the mobile interface (<html data-mode="mobile">,
     asked at each tap: the mode can change under an open page) has the
     cloud alone: the bank stays where it is, and says what is left; it is
     no longer picked up or dragged there. */
  const PLACES = ".ex-blank, .ex-match-drop";
  const hasCloud = ex => !!ex
    && (ex.dataset.subtype === "fill-blanks" || ex.dataset.primitive === "matching");
  const cloudOnly = ex => hasCloud(ex)
    && document.documentElement.getAttribute("data-mode") === "mobile";
  let cloud = null, cloudFor = null;
  function closeCloud(refocus) {
    if (!cloud) return;
    const blank = cloudFor;
    cloud.remove();
    cloud = cloudFor = null;
    if (!blank || !blank.isConnected) return;
    blank.classList.remove("choosing");
    blank.setAttribute("aria-expanded", "false");
    if (refocus) blank.focus({preventScroll: true});
  }
  function openCloud(blank) {
    const ex = blank.closest(".exercise"), bank = bankFor(ex);
    closeCloud();
    if (!bank) return;
    const match = blank.classList.contains("ex-match-drop");
    cloud = document.createElement("div");
    cloud.className = "ex-cloud";
    cloud.setAttribute("role", "group");
    cloud.setAttribute("aria-label", match ? "The answers for this match" : "The words for this blank");
    const words = $$(".ex-item", bank);
    for (const word of words) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ex-cloud-pick";
      b.dataset.pick = word.dataset.item;
      // the word as the bank shows it: its script, its direction, its reading
      for (const node of word.childNodes) b.appendChild(node.cloneNode(true));
      // a copy to choose from, not a word of the document: the page's hover
      // tools (the linguistic cloud of the reading view) are not offered on it
      $$("[data-fa], [data-occ], [data-tl-src], [data-rtl-src]", b).forEach(x =>
        ["data-fa", "data-occ", "data-tl-src", "data-rtl-src"].forEach(a => x.removeAttribute(a)));
      cloud.appendChild(b);
    }
    if ($(".ex-item", blank)) {
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "ex-cloud-clear";
      clear.textContent = match ? "Empty this match" : "Empty this blank";
      cloud.appendChild(clear);
    } else if (!words.length) {
      const none = document.createElement("p");
      none.className = "ex-cloud-none";
      none.textContent = match ? "Every answer is in place: tap a filled one to empty it."
                               : "Every word is in a blank: tap a filled one to empty it.";
      cloud.appendChild(none);
    }
    ex.appendChild(cloud);
    cloudFor = blank;
    blank.classList.add("choosing");
    blank.setAttribute("aria-expanded", "true");
    placeCloud(true);
    const first = $("button", cloud);
    if (first) first.focus({preventScroll: true});
  }
  /* UNDER THE SENTENCE, its tip pointing up at the blank: the words are
     chosen for the sentence, and a cloud right under a blank on its first
     line would cover the rest of it -- where under the sentence it covers
     only the bank, which it copies.  A matching exercise's rows are its
     sentence.  A long passage, or a long list of rows, whose end is far
     below the place, has it right under the place instead; a screen with
     more room above than below, over the place, the tip pointing down.
     Never past the exercise's own edges. */
  function placeCloud(show) {
    if (!cloud || !cloudFor || !cloudFor.isConnected) return;
    const ex = cloudFor.closest(".exercise");
    const er = ex.getBoundingClientRect(), br = cloudFor.getBoundingClientRect();
    const fill = cloudFor.closest(".ex-fill, .ex-pairs");
    const fr = fill ? fill.getBoundingClientRect() : br;
    const foot = fr.bottom - br.bottom <= Math.max(96, 3 * br.height) ? Math.max(fr.bottom, br.bottom) : br.bottom;
    const cw = cloud.offsetWidth, ch = cloud.offsetHeight;
    const middle = br.left + br.width / 2 - er.left;
    const left = Math.max(8, Math.min(middle - cw / 2, er.width - cw - 8));
    const room = innerHeight - foot;
    const under = room >= ch + 16 || room >= br.top;
    cloud.style.left = left + "px";
    cloud.style.top = (under ? foot - er.top + 10 : br.top - er.top - ch - 10) + "px";
    cloud.classList.toggle("over", !under);
    // under a sentence the blank is lines above: a tip would point at
    // whatever is between, and the blank's own border says which it is
    cloud.classList.toggle("apart", under && foot > br.bottom + 4);
    cloud.style.setProperty("--tip", Math.max(16, Math.min(middle - left, cw - 16)) + "px");
    // a bar fixed over the page's foot has its room kept by the page's own
    // sheet (scroll-margin); on a desktop nothing moves
    if (show) cloud.scrollIntoView({block: "nearest"});
  }
  /* The taps the cloud answers; true when one was its. */
  function cloudClick(e) {
    const inCloud = cloud && cloud.contains(e.target);
    if (inCloud) {
      const b = e.target.closest("button");
      if (!b) return true;
      const blank = cloudFor, ex = blank.closest(".exercise"), bank = bankFor(ex);
      if (b.classList.contains("ex-cloud-clear")) {
        const placed = $(".ex-item", blank);
        if (placed && bank) moveItem(placed, bank);
      } else {
        const word = bank && $$(".ex-item", bank).find(w => w.dataset.item === b.dataset.pick);
        if (word) moveItem(word, blank);
      }
      closeCloud(true);
      return true;
    }
    const ex = e.target.closest(".exercise");
    if (!hasCloud(ex)) return false;
    const blank = e.target.closest(PLACES);
    if (blank) {
      // a word picked in the bank (the browser's other way) goes where the
      // click is, as it always did; otherwise the place opens its cloud
      if (picked && picked.closest(".exercise") === ex) {
        const item = picked;
        picked = null;
        moveItem(item, blank);
        return true;
      }
      if (cloudFor === blank) closeCloud(true);
      else openCloud(blank);
      return true;
    }
    // in the mobile interface the bank's words are there to be read: the
    // blanks take them
    return cloudOnly(ex) && !!e.target.closest(".ex-bank");
  }
  listen(document, "pointerdown", e => {
    if (cloud && !cloud.contains(e.target) && !cloudFor.contains(e.target)) closeCloud();
  }, {capture: true});
  listen(window, "resize", () => placeCloud(false));
  controller.signal.addEventListener("abort", () => closeCloud());

  let dragged = null, picked = null;
  listen(container, "dragstart", e => {
    const item = e.target.closest(".ex-item");
    if (item && !preview && cloudOnly(item.closest(".exercise"))) { e.preventDefault(); return; }
    if (!item || preview || !mayDrag(item)) return;
    // the cloud is a copy of the bank as it was: a drag changes the bank
    closeCloud();
    dragged = item; item.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", item.dataset.item || "item");
  });
  listen(container, "dragend", () => {
    if (dragged) dragged.classList.remove("dragging");
    dragged = null;
  });
  listen(container, "dragover", e => {
    if (!dragged) return;
    const drop = e.target.closest("[data-drop], [data-bank]");
    if (drop && drop.closest(".exercise") === dragged.closest(".exercise")) e.preventDefault();
  });
  listen(container, "drop", e => {
    const drop = e.target.closest("[data-drop], [data-bank]");
    if (dragged && drop) {
      e.preventDefault();
      const over = e.target.closest(".ex-item");
      const anchor = sequenceAnchor(drop, over, e.clientX, e.clientY);
      moveItem(dragged, drop, anchor);
    }
  });

  // Tap-to-place is the touch and keyboard-friendly twin of dragging.
  listen(container, "click", e => {
    // the document page's copy-to-deck button belongs to initDoc
    if (e.target.closest(".ex-to-deck")) return;
    const zoom = e.target.closest(".ex-card-zoom");
    if (zoom) { openCardZoom(zoom.closest(".exercise")); return; }
    const edit = e.target.closest(".ex-edit");
    if (edit && opts.onEdit) {
      const ex = edit.closest(".exercise");
      opts.onEdit(+ex.dataset.srcLine, +ex.dataset.srcEnd);
      return;
    }
    // A flashcard turns on a click anywhere on it but on what does a thing
    // of its own there: its 🔊 plays the recording, a player plays, a link
    // is followed.  None of those is an answer shown (the study page counts
    // a turn as one), and none of them turns it.
    const flash = e.target.closest(".ex-flashcard");
    if (flash) {
      const play = e.target.closest(".ex-card-play");
      if (play && flash.contains(play)) { toggleCardAudio(play); return; }
      const control = e.target.closest(CARD_CONTROLS);
      if (control && flash.contains(control)) return;
      flipCard(flash);
      return;
    }
    if (preview) return;
    if (cloudClick(e)) return;
    const sw = e.target.closest(".ex-drag-switch");
    if (sw) { setDragOn(!dragIsOn()); applyDrag(); sw.focus(); return; }
    const arrow = e.target.closest(".ex-move");
    if (arrow) {
      // the box keeps the focus for the next press; where the arrow it was
      // pressed with has just reached the end, the other one takes it
      const item = arrow.closest(".ex-item");
      moveAlong(item, arrow.dataset.move === "earlier" ? -1 : 1);
      const still = arrow.disabled ? $$(".ex-move", item).find(b => !b.disabled) : arrow;
      if (still) still.focus();
      return;
    }
    const option = e.target.closest(".ex-option");
    if (option) {
      const group = option.closest(".ex-choice-group");
      if (group.dataset.choice === "single")
        $$(".ex-option", group).forEach(x => {
          x.classList.remove("selected"); x.setAttribute("aria-pressed", "false");
        });
      option.classList.toggle("selected");
      option.setAttribute("aria-pressed", option.classList.contains("selected") ? "true" : "false");
      clearFeedback(option.closest(".exercise"));
      return;
    }
    const item = e.target.closest(".ex-item");
    if (item) {
      if (!mayDrag(item)) return;        // the arrows move this one
      if (picked && picked !== item) picked.classList.remove("picked");
      picked = item.classList.toggle("picked") ? item : null;
      return;
    }
    const drop = e.target.closest("[data-drop], [data-bank]");
    if (drop && picked) { const item0 = picked; picked = null; moveItem(item0, drop); }
  });
  listen(container, "keydown", e => {
    // the card is no <button> any more (a side may hold one): Enter and
    // Space on the card itself turn it, as a click does -- through a click,
    // so whoever listens for one hears this too
    if (["Enter", " "].includes(e.key) && e.target.classList && e.target.classList.contains("ex-flashcard")) {
      e.preventDefault();                          // Space would scroll the page
      if (!e.repeat) e.target.click();
      return;
    }
    if (e.key === "Escape" && cloud) {
      e.preventDefault();
      closeCloud(true);
      return;
    }
    if (preview || !["Enter", " "].includes(e.key)) return;
    // a place filled from its cloud: Enter or Space on it is the click that
    // opens it, or that puts a picked word there (a key on a word in the
    // cloud is its button's)
    const choose = e.target.matches && e.target.matches(PLACES) ? e.target : null;
    if (choose && hasCloud(choose.closest(".exercise"))) {
      e.preventDefault();
      if (!e.repeat) choose.click();
      return;
    }
    // a box with arrows is a div (it holds them), so the browser makes no
    // click of its own here: this is the click the <button> used to make
    const box = e.target.classList && e.target.classList.contains("ex-item")
      && e.target.tagName !== "BUTTON" ? e.target : null;
    if (box) {
      e.preventDefault();
      if (!e.repeat) box.click();
      return;
    }
    const drop = e.target.closest("[data-drop], [data-bank]");
    if (drop && picked) { e.preventDefault(); const item = picked; picked = null; moveItem(item, drop); }
  });

  // Native HTML dragging is inconsistent on touch screens. A short touch
  // selects the block; releasing over a destination places it there.
  let touchItem = null;
  listen(container, "pointerdown", e => {
    if (preview || e.pointerType !== "touch") return;
    // A PRESS ON AN ARROW IS NOT A DRAG OF THE BLOCK IT IS IN.  Without this
    // a finger on an arrow picked the block up and the release put it at the
    // end of the line -- the very thing the arrows are there to avoid.
    if (e.target.closest(".ex-move")) return;
    touchItem = e.target.closest(".ex-item");
    // nor is a word that the mobile interface places from a blank's cloud
    if (touchItem && (!mayDrag(touchItem) || cloudOnly(touchItem.closest(".exercise")))) {
      touchItem = null;
      return;
    }
    if (touchItem) touchItem.classList.add("picked");
  });
  listen(container, "pointerup", e => {
    if (!touchItem) return;
    const at = document.elementFromPoint(e.clientX, e.clientY);
    const drop = at && at.closest("[data-drop], [data-bank]");
    const over = at && at.closest(".ex-item");
    if (drop) moveItem(touchItem, drop,
      over && over !== touchItem
        ? sequenceAnchor(drop, over, e.clientX, e.clientY) : null);
    touchItem.classList.remove("picked"); touchItem = null;
  });

  /* WHAT A BLOCK IS, WHEN IT IS JUDGED: ITS TEXT, NOT ITS ROW.  Every block
     also carries the row it was written on (`data-item`, i0, i1, p0 …), and
     that used to be the whole of its identity -- so a sentence with two
     "the" to place, two blanks that take the same word, or two words sharing
     one translation was marked wrong for putting the right word in the right
     place, because it was the other row's copy of it.  htmlgen now writes
     the block's own text beside the row (`data-key`, and `data-answer-key` /
     `data-answer-keys` on what receives it), and those decide.  Rendered
     HTML from before that -- a page still open, a deck kept on a phone --
     has no keys, so the row is the fallback and nothing old stops working. */
  const identityOf = (el, by) =>
    !el ? null : (by === "key" ? (el.dataset.key || null) : (el.dataset.item || null));
  const itemFits = (item, drop) =>
    !!item && (drop.dataset.answerKey
      ? item.dataset.key === drop.dataset.answerKey
      : item.dataset.item === drop.dataset.answer);
  /* The order a sequence is put in to be right: by text where the renderer
     wrote the texts, by row where it did not.  Both lists are the same
     length by construction; a half-written pair falls back to the rows. */
  function sequenceAnswer(seq) {
    const rows = (seq.dataset.answer || "").split(",").filter(x => x);
    const keys = (seq.dataset.answerKeys || "").split(",").filter(x => x);
    return keys.length === rows.length && keys.length
      ? {by: "key", list: keys} : {by: "item", list: rows};
  }

  function judgeChoice(ex) {
    let good = true;
    $$(".ex-choice-group", ex).forEach(group => {
      $$(".ex-option", group).forEach(o => {
        const chosen = o.classList.contains("selected"), correct = o.dataset.correct === "1";
        if (chosen && correct) o.classList.add("answer-correct");
        else if (chosen) o.classList.add("answer-wrong");
        else if (correct) o.classList.add("answer-missed");
        if (chosen !== correct) good = false;
      });
    });
    return good;
  }
  function judgePlacement(ex) {
    let good = true;
    if (ex.dataset.subtype === "fill-blanks") {
      $$(".ex-blank", ex).forEach(drop => {
        const item = $(".ex-item", drop), ok = itemFits(item, drop);
        drop.classList.add(ok ? "answer-correct" : "answer-wrong");
        if (!ok) good = false;
      });
    } else {
      const seq = $(".ex-sequence", ex);
      const expected = sequenceAnswer(seq);
      $$(".ex-item", seq).forEach((item, i) => {
        const ok = identityOf(item, expected.by) === expected.list[i];
        item.classList.add(ok ? "answer-correct" : "answer-wrong");
        if (!ok) good = false;
      });
      if ($$(".ex-item", seq).length !== expected.list.length) good = false;
    }
    return good;
  }
  function judgeMatching(ex) {
    let good = true;
    $$(".ex-match-drop", ex).forEach(drop => {
      const item = $(".ex-item", drop), ok = itemFits(item, drop);
      drop.classList.add(ok ? "answer-correct" : "answer-wrong");
      if (!ok) good = false;
    });
    return good;
  }
  function judge(ex) {
    clearFeedback(ex);
    const good = ex.dataset.primitive === "choice" ? judgeChoice(ex)
      : ex.dataset.primitive === "matching" ? judgeMatching(ex) : judgePlacement(ex);
    ex.classList.add(good ? "correct" : "incorrect");
    // the picture and the recording the author kept for the answer, right
    // or wrong: both are shown, neither is played by itself
    $$(".ex-image-answer", ex).forEach(img => { img.hidden = false; });
    $$(".ex-audio-answer", ex).forEach(box => { box.hidden = false; });
    $$(".ex-explanation", ex).forEach(why => {
      const wanted = why.dataset.explanationFor;
      why.hidden = !!wanted && wanted !== (good ? "correct" : "incorrect");
      if (!why.hidden && why.classList.contains("ex-explanation-result"))
        why.classList.add(good ? "success" : "error");
    });
    return good;
  }

  /* AN ORDERING EXERCISE MUST NOT BE DEALT ALREADY SOLVED.  A fair shuffle
     of two blocks comes out in the answer's order half the time, of three
     one time in six, and a learner handed the finished sentence has nothing
     to do but press Check.  So the deal is repeated while it lands on the
     answer -- judged by what judgePlacement itself compares, so that two
     blocks with the SAME text count as the same deal whichever way round
     they fall.  A sequence whose blocks all read alike has no other order
     to reach, and dealing it for ever would hang the page: it is dealt once
     and left, which is what it looked like anyway. */
  function deal(seq) {
    const answer = sequenceAnswer(seq);
    const solved = () => $$(".ex-item", seq)
      .every((item, i) => identityOf(item, answer.by) === answer.list[i]);
    const alike = new Set(answer.list).size < 2;
    for (let tries = 0; tries < 24; tries++) {
      shuffleInto(seq);
      if (alike || !solved()) return;
    }
  }

  /* ----------------------------------------------------------- a follow-up's steps
     One step at a time, because the next may build on -- or give away -- the one before: step 1 is shown, with its own
     button under it, Check step (Show answer for a card); the check marks the step as the page marks any exercise, says
     Correct or Not quite, locks the answer and shows the step's explanation right there; Next step, after it, brings the
     next, scrolled into view and given the focus.  From the third step on the steps before the last two fold into one
     line, "Earlier steps (n)".  At the last check the chain says its result in words, and its own explanations.  Every
     step is an ordinary exercise of the page, so Check exercises counts each scored step; a step the learner has not come
     to is counted and not judged.  In the editor's preview nothing is checked: Next step goes on, and "Show every step"
     unfolds the whole chain to look it over. */
  function bindChain(chain) {
    const steps = $$(".ex-step", chain);
    const n = steps.length;
    const state = steps.map(() => ({checked: false, good: null}));
    const say = $(".ex-strip-say", chain), dots = $$(".ex-dot", chain);
    const earlier = $(".ex-earlier", chain), earlierBody = $(".ex-earlier-body", chain);
    const earlierN = $(".ex-earlier-n", chain), resultEl = $(".ex-chain-result", chain);
    const showAll = $(".ex-showall", chain);
    let at = 0, finished = false, all = false, folded = 0;
    const told = [];
    const stepEx = i => $(":scope > .exercise", steps[i]);
    const isCard = i => steps[i].dataset.kind === "card";
    const parts = i => ({go: $(".ex-step-check, .ex-step-show", steps[i]), next: $(".ex-step-next", steps[i]),
                         result: $(".ex-step-result", steps[i])});
    const tell = () => told.forEach(fn => fn());
    function paint() {
      chain.dataset.step = String(at + 1);
      chain.dataset.answered = String(state.filter(s => s.checked).length);
      chain.classList.toggle("ex-chain-done", finished);
      chain.classList.toggle("ex-chain-all", all);
      steps.forEach((step, i) => {
        step.hidden = !all && i > at;
        step.classList.toggle("ex-step-current", i === at && !finished && !all);
        step.classList.toggle("ex-step-checked", state[i].checked);
      });
      dots.forEach((d, i) => {
        d.classList.toggle("on", i === at && !finished);
        d.classList.toggle("done", state[i].checked);
        d.textContent = state[i].checked ? "\u2713" : String(i + 1);
      });
      say.textContent = finished ? `All ${n} steps` : `Step ${at + 1} of ${n}`;
      // the steps before the last two are folded, from the third on; the editor's "show every step" has none
      const want = all ? 0 : Math.max(0, at - 1);
      if (want > folded) {
        for (let i = folded; i < want; i++) earlierBody.appendChild(steps[i]);
      } else if (want < folded) {
        // unfolded: back in their places, in order, after the fold's own line
        let after = earlier;
        for (let i = 0; i < n; i++) {
          if (steps[i].parentNode === earlierBody) { after.after(steps[i]); }
          after = steps[i].parentNode === earlierBody ? after : steps[i];
        }
      }
      folded = want;
      earlier.hidden = folded === 0;
      earlierN.textContent = String(folded);
      steps.forEach((step, i) => {
        const p = parts(i);
        if (preview) {
          p.go.hidden = true;
          p.result.textContent = "";
          if (p.next) p.next.hidden = i >= n - 1;
          return;
        }
        p.go.hidden = state[i].checked;
        if (p.next) p.next.hidden = !(state[i].checked && i === at && !finished);
      });
      if (showAll) showAll.setAttribute("aria-pressed", all ? "true" : "false");
    }
    function finish() {
      finished = true;
      const scoredN = state.filter(s => s.good !== null).length;
      const rights = state.filter(s => s.good === true).length;
      resultEl.textContent = scoredN ? `${rights} of ${scoredN} steps right` : `All ${n} steps seen`;
      resultEl.hidden = false;
      resultEl.classList.toggle("ok", !scoredN || rights === scoredN);
      resultEl.classList.toggle("err", !!scoredN && rights !== scoredN);
      // the chain's own explanations, as the result of the whole: right only when every scored step was
      const good = !scoredN || rights === scoredN;
      $$(":scope > .ex-explanation", chain).forEach(why => {
        const wanted = why.dataset.explanationFor;
        why.hidden = !!wanted && wanted !== (good ? "correct" : "incorrect");
        if (!why.hidden && why.classList.contains("ex-explanation-result"))
          why.classList.add(good ? "success" : "error");
      });
    }
    function mark(i, good) {
      state[i] = {checked: true, good};
      if (i === at && at === n - 1) finish();
    }
    // a card's turn, whoever made it (its Show answer, a click on the card, the enlarged copy): the answer is shown
    steps.forEach((step, i) => {
      const flash = isCard(i) && $(".ex-flashcard", step);
      if (!flash || preview) return;
      new MutationObserver(() => {
        if (flash.classList.contains("flipped") && !state[i].checked) { mark(i, null); paint(); tell(); }
      }).observe(flash, {attributes: true, attributeFilter: ["class"]});
    });
    function check() {
      if (preview || finished || state[at].checked) return false;
      const ex = stepEx(at), p = parts(at);
      if (isCard(at)) {
        const flash = $(".ex-flashcard", ex);
        if (flash && !flash.classList.contains("flipped")) flipCard(flash);
        if (!state[at].checked) mark(at, null);
      } else {
        const good = judge(ex);
        const body = $(".ex-body", ex);
        if (body) body.inert = true;
        p.result.textContent = good ? "Correct" : "Not quite";
        p.result.className = "ex-step-result " + (good ? "ok" : "err");
        mark(at, good);
      }
      paint();
      tell();
      if (p.next && !p.next.hidden) p.next.focus({preventScroll: true});
      return true;
    }
    function next() {
      if (finished || at >= n - 1 || (!preview && !state[at].checked)) return false;
      at++;
      paint();
      const step = steps[at];
      step.scrollIntoView({block: "nearest", behavior: "smooth"});
      step.focus({preventScroll: true});
      tell();
      return true;
    }
    if (showAll) listen(showAll, "click", () => { all = !all; paint(); });
    steps.forEach((step, i) => {
      const p = parts(i);
      listen(p.go, "click", () => { if (i === at) check(); });
      if (p.next) listen(p.next, "click", () => { if (i === at) next(); });
    });
    // Enter does what the button in view does (as on the study page); not on a control, which has its own Enter
    if (opts.chainBar !== false) listen(chain, "keydown", e => {
      if (e.key !== "Enter" || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.target.closest("input, textarea, select, button, a[href], summary, [contenteditable], audio, video, .ex-flashcard, .ex-item, .ex-blank, .ex-match-drop, [role=button]")) return;
      const p = parts(at);
      const press = [p.next, p.go].find(b => b && !b.hidden && !b.disabled);
      if (press) { e.preventDefault(); press.click(); }
    });
    paint();
    const handle = {
      el: chain, steps, n, preview,
      get at() { return at; },
      get finished() { return finished; },
      get checked() { return state[at].checked; },
      get card() { return isCard(at); },
      get rights() { return state.filter(s => s.good === true).length; },
      get scored() { return state.filter(s => s.good !== null).length; },
      get wrong() { return state.some(s => s.good === false); },
      get wrongHere() { return state[at].good === false; },
      get answered() { return state.filter(s => s.checked).length; },
      check, next,
      onChange: fn => { told.push(fn); },
      // a step that is not the learner's yet: counted by Check exercises, and not judged
      unreached: ex => { const i = steps.findIndex(s => s.contains(ex)); return i > at && !state[i].checked; },
      // Check exercises, pressed: a chain left half-way says how far it got
      pageChecked: () => {
        if (finished) return;
        resultEl.textContent = `${state.filter(s => s.checked).length} of ${n} steps answered`;
        resultEl.hidden = false;
        resultEl.classList.remove("ok", "err");
      },
      showAll: on => { all = !!on; paint(); },
    };
    chain._parsehChain = handle;
    return handle;
  }
  const chains = everything.filter(isChain).map(bindChain);

  if (!preview) {
    exercises.forEach(ex => {
      if (ex.dataset.primitive === "placement" && ex.dataset.subtype !== "fill-blanks") {
        deal($(".ex-sequence", ex));
        markEnds($(".ex-sequence", ex));
      }
      if (ex.dataset.primitive === "choice" &&
          !["yes-no", "true-false", "incorrect-part"].includes(ex.dataset.subtype))
        $$(".ex-options", ex).forEach(shuffleInto);
      $$(".ex-bank", ex).forEach(shuffleInto);
    });
    applyDrag();
    // a sheet taken out of the page and not bound again has nothing to apply it to
    listen(document, "parseh:studio", e => {
      if (e.detail && e.detail.what === "drag" && container.isConnected) applyDrag();
    });
    const correct = $(".ex-correct-all", container);
    if (correct) listen(correct, "click", () => {
      const scored = exercises.filter(ex => ex.dataset.scored === "1");
      // a step of a follow-up the learner has not come to is counted, as unanswered, and not judged
      const unreached = ex => chains.some(c => c.unreached(ex));
      const points = scored.reduce((n, ex) => n + (unreached(ex) ? 0 : judge(ex) ? 1 : 0), 0);
      chains.forEach(c => c.pageChecked());
      const out = $(".ex-score", correct.closest("[data-exercise-results]"));
      out.textContent = `${points} / ${scored.length} correct`;
      out.hidden = false;
      out.classList.toggle("perfect", points === scored.length);
    });
  } else {
    $$(".ex-option,.ex-item", container).forEach(x => {
      x.disabled = true; x.draggable = false;
    });
  }
  // the study page checks one exercise at a time with the same judge the
  // "Check exercises" button uses
  return {judge, exercises: everything, chains};
}

/* ---------------- index page ---------------- */

function initIndex() {
  const state = {...savedLibraryFilters(), sort: savedSort()};
  function saveFilters() {
    try { sessionStorage.setItem(LIBRARY_FILTERS_KEY, JSON.stringify({
      q: state.q, intext: state.intext,
      tags: [...state.tags], excludedTags: [...state.excludedTags],
    })); } catch (e) { /* private mode */ }
  }
  $("#search").value = state.q;
  $("#intext").checked = state.intext;
  const cards = $("#cards"), tagbar = $("#tagbar"), empty = $("#empty");
  const emptyLang = $("#empty-lang");
  const byCode = Object.fromEntries(LANGS.map(l => [l.code, l]));
  let listed = 0;      // the documents the last query returned, all languages

  /* Every document the filters show, at once.  The count follows each
     filter pass (a search answered, a language chip); the ids go up in
     the order the cards are shown, through a plain form, so the browser
     saves the zip the server answers with as a file.  The form answers
     into a hidden frame: a zip is saved and leaves the frame as it was,
     so the frame only ever loads a refusal (its JSON), which is told in a
     toast while the library, its search and its filters stay put. */
  const btnDownload = $("#btn-download-shown");
  const dlBox = $("#download-shown");
  function refreshDownloadShown(n) {
    if (!btnDownload) return;
    btnDownload.textContent = `Download ${n} shown`;
    btnDownload.title = `Download the ${n} document${n === 1 ? "" : "s"} shown`;
    // a <summary> takes no disabled attribute: the menu is shut and made
    // unclickable instead, which is the same thing to look at and to press
    if (dlBox) {
      dlBox.classList.toggle("disabled", n === 0);
      if (n === 0) dlBox.open = false;
    }
  }
  /* Either shape, the same way the per-document Download ▾ offers them: the
     .md sources in one zip, or each document's own zip (its markdown, its
     tags and its pictures) inside one. */
  function sendDownload(shape) {
    const ids = $$(".card:not([hidden])", cards).map(c => c.dataset.id).filter(Boolean);
    if (!ids.length) return;
    // on the activity list at once, and followed there by its token until
    // the server has packed and sent it: the frame below says nothing of a
    // download that worked
    const form = $("#download-form");
    const A = window.ParsehActivity;
    if (form) {
      const plain = form.getAttribute("data-action") || form.getAttribute("action");
      form.setAttribute("data-action", plain);
      form.setAttribute("action", A
        ? A.expect(`Packing ${ids.length} document${ids.length === 1 ? "" : "s"} to download`).url(plain)
        : plain);
    }
    $("#download-ids").value = ids.join(",");
    const sh = $("#download-shape");
    if (sh) sh.value = shape;
    if (dlBox) dlBox.open = false;
    // A fresh frame each time: its one navigation replaces the new frame's
    // own blank page, so a refusal never adds an entry to the tab's history
    // (Back would otherwise walk the hidden frame and toast the old error).
    const old = $("#download-sink");
    if (old) {
      const sink = document.createElement("iframe");
      sink.name = sink.id = "download-sink";
      sink.title = "Download";
      sink.hidden = true;
      sink.addEventListener("load", onDownloadSinkLoad);
      old.replaceWith(sink);
    }
    $("#download-form").submit();
  }
  const dlShownMd = $("#dl-shown-md"), dlShownZip = $("#dl-shown-zip");
  if (dlShownMd) dlShownMd.addEventListener("click", () => sendDownload("md"));
  if (dlShownZip) dlShownZip.addEventListener("click", () => sendDownload("zip"));

  /* A backup put back — the other half of the Backup button.  The documents
     already here are KEPT and counted first, and replacing them is offered
     only then: a restore is not a merge, and a backup is usually older than
     the work sitting beside it. */
  function askReplace(kept) {
    return new Promise(done => {
      const root = $("#modal-root"); root.innerHTML = "";
      const ov = document.createElement("div");
      ov.className = "modal-overlay";
      ov.innerHTML = `<div class="modal" role="dialog" aria-modal="true">
        <h3>${kept.length} document${kept.length === 1 ? " is" : "s are"} already here</h3>
        <p>They were left exactly as they are. Replacing them puts the backup's
        copy in their place — anything written since the backup was made is lost.</p>
        <div class="row"><button class="btn" data-x="keep">Keep mine</button>
        <button class="btn danger" data-x="replace">Replace them</button></div></div>`;
      const close = v => { root.innerHTML = ""; done(v); };
      $('[data-x="keep"]', ov).addEventListener("click", () => close(false));
      $('[data-x="replace"]', ov).addEventListener("click", () => close(true));
      ov.addEventListener("click", e => { if (e.target === ov) close(false); });
      root.appendChild(ov);
    });
  }
  /* A document of the backup with an id of its own whose name is taken
     is asked about first (askNames), before anything is written; the names
     given are sent again with the "Replace them" of the same backup, so a
     document restored under a new name keeps it when it is put back again. */
  async function restoreBackup(file) {
    // THE FILE ITSELF is the body, as the book and video shelves send theirs:
    // the browser streams it from the disk, and sends it again for the second
    // request if replacing or new names are asked for.  Read into the page
    // first, a backup of a few hundred megabytes held the page still for
    // seconds -- the activity pill included, which is what says the restore
    // has begun.
    let renames = {existing: {}, incoming: {}};
    const post = replace => sendWorking(`Restoring the library from ${file.name}`,
      withName("/api/library/zip" + query({
        replace: replace ? 1 : 0, renames: Object.keys(renames.existing).length
          || Object.keys(renames.incoming).length ? renames : null}), file.name),
      {method: "POST", body: file, headers: {"Content-Type": "application/zip"}});
    const named = async (a, replace) => !nameClash(a) ? a : askNames(a.data, given => {
      renames = {existing: Object.assign({}, renames.existing, given.existing),
                 incoming: Object.assign({}, renames.incoming, given.incoming)};
      return post(replace);
    });
    let a = await named(await post(false), false);
    if (!a) return;                      // cancelled: nothing was restored
    if (!a.ok) throw refusal(a);
    let out = a.data;
    if ((out.kept || []).length && await askReplace(out.kept)) {
      const b = await named(await post(true), true);
      if (b && !b.ok) throw refusal(b);
      if (b) out = b.data;
    }
    const n = (out.restored || []).length, kept = (out.kept || []).length;
    const notes = out.warnings || [];
    toast(`${n} document${n === 1 ? "" : "s"} restored`
          + (kept ? `, ${kept} left as ${kept === 1 ? "it is" : "they are"}` : "")
          + (notes.length ? `; ${notes[0]}` : ""), notes.length > 0);
    await loadTags();
    await loadDocs();
  }
  const btnRestore = $("#btn-restore"), backupFile = $("#backup-file");
  if (btnRestore && backupFile) {
    btnRestore.addEventListener("click", () => backupFile.click());
    backupFile.addEventListener("change", () => {
      const f = backupFile.files[0];
      backupFile.value = "";          // the same file can be picked again
      if (f) restoreBackup(f).catch(e => toast(e.message, true));
    });
  }
  const downloadSink = $("#download-sink");
  if (downloadSink) downloadSink.addEventListener("load", onDownloadSinkLoad);
  function onDownloadSinkLoad(e) {
    const sink = e.currentTarget;
    let doc = null, msg = "";
    try { doc = sink.contentDocument; } catch (err) { doc = null; }
    if (!doc) {
      // not ours to read: the browser's own error page, no server answered
      msg = "the server did not answer";
    } else {
      if (doc.URL === "about:blank") return;             // the frame's own first page
      const text = (doc.body ? doc.body.textContent : "").trim();
      try { msg = (JSON.parse(text) || {}).error || text; } catch (e) { msg = text; }
    }
    if (msg) toast("Could not download: " + msg.slice(0, 200), true);
  }

  /* The language chip row (rendered server-side, the same row every index
     page of the toolbox has).  A click records the shared preference and
     hides the cards of the other languages; the counts follow the
     current search.  parseh.js does this elsewhere; it is not loaded
     here, so the wiring is repeated with the same storage key. */
  const chipRow = $(".parseh-langs");
  function applyLangFilter() {
    let pick = sharedLang();
    // a stored preference no chip offers (including a language with no
    // remaining documents) would hide every card and mark
    // no chip: read it as 'all' and put the store right, as parseh.js does
    if (pick !== "all" && chipRow && !$(`.chip[data-pick="${pick}"]`, chipRow)) {
      pick = "all";
      setSharedLang("all");
    }
    if (chipRow) $$(".chip", chipRow).forEach(c =>
      c.classList.toggle("on", c.dataset.pick === pick));
    let shown = 0;
    $$(".card", cards).forEach(c => {
      const on = pick === "all" || c.dataset.lang === pick;
      c.hidden = !on;
      if (on) shown++;
    });
    refreshDownloadShown(shown);
    // the first-run message is for an empty library; when the chip is
    // what hides every card the page says so instead
    empty.classList.toggle("hidden", listed > 0);
    const filtered = listed > 0 && shown === 0;
    if (emptyLang) {
      const name = $(".lang-name", emptyLang);
      if (name) name.textContent = (byCode[pick] || {}).name || pick;
      emptyLang.classList.toggle("hidden", !filtered);
    }
    // +New opens on the picked language's own starting document -- a
    // Japanese one carries the kana marks and a vertical block, a
    // Latin-script one the marked runs.  On 'all' the link stays bare and
    // the server picks the registry's first language.
    $$('a[href$="/new"], a[href*="/new?"]').forEach(a => {
      a.href = BASE + "/new" + (pick === "all" ? "" : "?target=" + encodeURIComponent(pick));
    });
  }
  function refreshChipCounts(docs) {
    if (!chipRow) return;
    const counts = {};
    for (const d of docs) counts[d.target || "fa"] = (counts[d.target || "fa"] || 0) + 1;
    // Rebuild from the results so deleting the last document removes its
    // language, and clearing a search restores the available languages.
    chipRow.innerHTML = `<button type="button" class="chip" data-pick="all">all<span class="n">${docs.length}</span></button>`;
    for (const l of LANGS) {
      if (!counts[l.code]) continue;
      const c = document.createElement("button");
      c.type = "button";
      c.className = "chip";
      c.dataset.pick = c.dataset.lang = c.lang = l.code;
      c.title = l.name;
      const native = document.createElement("span");
      native.className = "native";
      native.textContent = l.native;
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = counts[l.code];
      c.append(native, n);
      chipRow.appendChild(c);
    }
  }
  if (chipRow) chipRow.addEventListener("click", e => {
    const c = e.target.closest(".chip");
    if (!c || !chipRow.contains(c)) return;
    setSharedLang(c.dataset.pick);
    applyLangFilter();
    renderTagbar();     // a language picked narrows what the tags can offer
  });

  let allTags = [];       // every tag in the library, by name, from /api/tags
  let lastDocs = [];      // what the last query answered, for the counts

  /* THE TAG BAR COUNTS WHAT IS STILL VISIBLE.  How many documents in the
     whole library wear a tag is no use once a filter is on: what the reader
     wants to know is how many of the ones in front of them it would leave.
     So the numbers are counted from the documents the last query returned,
     narrowed by the language chip, and a tag that would leave none is not
     offered at all -- it could only ever empty the page.

     A TAG DOING THE FILTERING ALWAYS STAYS, whatever its count. An excluded
     tag shows zero by its very nature (those documents are the ones being
     kept out), and hiding it would take away the only way to switch it off. */
  function renderTagbar() {
    const pick = sharedLang();
    const docs = lastDocs.filter(d => pick === "all" || (d.target || "fa") === pick);
    const counts = {};
    for (const d of docs) for (const t of d.tags || []) counts[t] = (counts[t] || 0) + 1;
    // a tag doing the filtering that the library no longer holds would
    // otherwise be unreachable: it goes in the row so it can be cleared
    const names = allTags.slice();
    for (const t of [...state.tags, ...state.excludedTags])
      if (!names.includes(t)) names.push(t);
    tagbar.innerHTML = "";
    let shown = 0;
    for (const tag of names) {
      const on = state.tags.has(tag), off = state.excludedTags.has(tag);
      const n = counts[tag] || 0;
      if (!on && !off && !n) continue;
      shown++;
      const b = document.createElement("button");
      b.className = "tagchip" + (on ? " active" : "") + (off ? " excluded" : "");
      b.innerHTML = `<span></span><span class="n"></span>`;
      b.firstChild.textContent = tag;
      b.lastChild.textContent = n;
      b.title = on ? "Included — click to exclude"
        : off ? "Excluded — click to clear"
        : "Click to include; Shift-click to exclude";
      b.addEventListener("click", event => {
        // neutral → include → exclude → neutral. Shift-click goes straight
        // to exclusion, useful when a shelf has many tags.
        if (event.shiftKey) {
          state.tags.delete(tag);
          if (state.excludedTags.has(tag)) state.excludedTags.delete(tag);
          else state.excludedTags.add(tag);
        } else if (state.tags.has(tag)) {
          state.tags.delete(tag); state.excludedTags.add(tag);
        } else if (state.excludedTags.has(tag)) {
          state.excludedTags.delete(tag);
        } else state.tags.add(tag);
        saveFilters();
        loadDocs();          // which draws this row again, with the new counts
      });
      tagbar.appendChild(b);
    }
    const hint = $("#tag-filter-hint");
    if (hint) hint.hidden = !shown;
    updateClearFilters();
  }

  function updateClearFilters() {
    const b = $("#btn-clear-filters");
    if (!b) return;
    b.hidden = !(state.q || state.intext || state.tags.size
                 || state.excludedTags.size || sharedLang() !== "all");
  }

  function clearFilters() {
    state.q = "";
    state.intext = false;
    state.tags.clear();
    state.excludedTags.clear();
    const s = $("#search"); if (s) s.value = "";
    const t = $("#intext"); if (t) t.checked = false;
    setSharedLang("all");          // the chip row is a filter on this page too
    saveFilters();
    loadDocs();
  }

  async function loadTags() {
    const data = await api("/api/tags");
    allTags = (data.tags || []).map(t => t.tag);
    renderTagbar();
  }

  function buildBadge(b) {
    if (!b || b.status === "none")
      return `<span class="badge">no PDF yet</span>`;
    if (b.status === "error")
      return `<span class="badge err">build failed</span>`;
    const stale = b.stale ? `<span class="badge warn">source changed</span>` : "";
    // the check is "RTL order" for a right-to-left target, "found in the
    // PDF" for the others; the card badge says "verified" for both
    const verify = b.verify_failed
      ? `<span class="badge err">${b.verify_failed} verify fail</span>`
      : (b.verified === false
          ? `<span class="badge warn">not verified</span>`
          : `<span class="badge ok">${b.verify_ok}/${b.verify_ok} verified</span>`);
    const pp = b.pages != null ? ` ${b.pages} pp` : "";
    // a latex block that could not be drawn is a framed note on the paper
    const drawn = b.latex_failed
      ? `<span class="badge warn">${b.latex_failed} drawing${b.latex_failed === 1 ? "" : "s"} could not be made</span>`
      : "";
    return `<span class="badge ok">PDF ✓${pp}</span>${verify}${drawn}${stale}`;
  }

  let loadSeq = 0;
  async function loadDocs() {
    const seq = ++loadSeq;
    const p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.intext) p.set("intext", "1");
    if (state.tags.size) p.set("tags", [...state.tags].join(","));
    if (state.excludedTags.size) p.set("exclude_tags", [...state.excludedTags].join(","));
    p.set("sort", state.sort);
    const data = await api("/api/docs?" + p.toString());
    if (seq !== loadSeq) return;      // a newer filter superseded this one
    cards.innerHTML = "";
    listed = data.docs.length;
    lastDocs = data.docs;             // what the tag counts are counted from
    refreshChipCounts(data.docs);
    for (const d of data.docs) {
      const el = document.createElement("a");
      el.className = "card";
      el.href = BASE + "/doc/" + d.id;
      const code = d.target || "fa";
      const l = byCode[code] || {code, name: code, native: code, dir: "ltr"};
      el.dataset.lang = code;
      el.dataset.id = d.id;
      const s = d.stats || {};
      const statBits = [];
      if (s.voci) statBits.push(s.voci + (s.voci === 1 ? " lemma" : " lemmi"));
      if (s.words) statBits.push(s.words + " words");
      if (s.fa_runs) statBits.push(s.fa_runs + " runs");
      el.innerHTML = `
        <h3>${d.title_html || "Untitled"}</h3>
        <p class="sub">${d.subtitle_html || ""}</p>
        <div class="badges"><span class="badge lang" lang="${escAttr(l.code)}" dir="${escAttr(l.dir)}"
            title="${escAttr(l.name)}">${escAttr(l.native)}</span>${buildBadge(d.build)}
          ${statBits.map(x => `<span class="badge">${x}</span>`).join("")}
        </div>
        <div class="tagrow"></div>
        <div class="dates">updated ${fmtDate(d.updated)} · created ${fmtDate(d.created)}</div>
        <button class="card-del" title="Delete">✕</button>`;
      const tagrow = $(".tagrow", el);
      for (const t of d.tags || []) {
        const sp = document.createElement("span");
        sp.className = "tag"; sp.textContent = t;
        tagrow.appendChild(sp);
      }
      $(".card-del", el).addEventListener("click", async e => {
        e.preventDefault(); e.stopPropagation();
        const gone = await confirmDialog({
          title: `Delete “${d.title}”?`,
          hint: "Its builds are deleted too. This cannot be undone.",
          ok: "Delete document", danger: true, opener: e.currentTarget,
          run: async () => {
            // the card by its id: a list drawn again since the question was
            // asked (after a refusal) made this one a copy nobody sees
            const drop = () => $$(".card", cards).forEach(c => { if (c.dataset.id === d.id) c.remove(); });
            try {
              await api("/api/docs/" + d.id, {method: "DELETE"});
              drop();
            } catch (err) {
              if (err.status === 404) drop();          // already gone: what was asked for
              else { err.message = "Delete failed: " + err.message; throw err; }
            } finally {
              loadDocs(); loadTags();     // the server may have done part of it either way
            }
          },
        });
        if (gone) toast("Deleted " + d.title);
      });
      cards.appendChild(el);
    }
    applyLangFilter();
    renderTagbar();          // the counts follow the filters that are on now
  }

  const btnClearFilters = $("#btn-clear-filters");
  if (btnClearFilters) btnClearFilters.addEventListener("click", clearFilters);

  const searchDocs = debounce(() => loadDocs(), 200);
  $("#search").addEventListener("input", e => {
    state.q = e.target.value.trim();
    saveFilters();
    searchDocs();
  });
  $("#intext").addEventListener("change", e => {
    state.intext = e.target.checked; saveFilters(); loadDocs();
  });
  // the menu opens on what it was left on, and remembers what it is moved to
  $("#sort").value = state.sort;
  $("#sort").addEventListener("change", e => {
    state.sort = e.target.value;
    saveSort(state.sort);
    loadDocs();
  });

  $("#btn-paste-answer").addEventListener("click", () => pasteAnswer(""));
  // A title already in the library makes way for the name-conflict dialog;
  // cancelling that brings the paste back, text and all.
  function pasteAnswer(value) {
    showModal({
      title: "Paste the LLM answer",
      hint: "Paste the model's whole reply — the markdown document inside " +
            "the code fence is extracted automatically.",
      value,
      okLabel: "Create document",
      onOk: async (value, close) => {
        if (!value.trim()) throw new Error("Nothing pasted");
        let a = await send("/api/docs", {method: "POST", json: {markdown: value}});
        if (nameClash(a)) {
          close();
          a = await askNames(a.data, renames =>
            send("/api/docs", {method: "POST", json: {markdown: value, renames}}));
          if (!a) return pasteAnswer(value);
        }
        if (!a.ok) throw refusal(a);
        close();
        location.href = BASE + "/doc/" + a.data.meta.id;
      },
    });
  }

  /* UPLOAD.  A .md (or .markdown, .txt) is one document; a .zip is what a
     document's Download ▾ gives as "Markdown + media" -- the markdown and
     the pictures and recordings it shows -- or several documents at once.
     The server looks at each markdown file's header first: one without the
     lines a document is filed by (title, subtitle, note, lang, target), or
     short of some of them, makes nothing and answers with what is missing,
     and the dialog asks for exactly that.  A complete header, extra keys
     and all, goes in as it is. */
  // the same reading api() gives a refusal, so a route that reports inside
  // the thing it was making is quoted here too rather than counted
  const refusal = a => new Error(serverSaid(a.data, {status: a.status, statusText: ""}).trim()
                                 || `the server answered ${a.status}`);
  /* `send`, on the activity list while the request runs (working(), above):
     a zip going up is minutes for a big library.  One entry a request -- not
     one for the whole exchange, which waits on the dialogs between two
     requests -- and "done" only when the answer was ok, since send() hands
     a refusal back rather than throwing it. */
  async function sendWorking(label, path, opts) {
    const A = window.ParsehActivity;
    const act = A ? A.local(label) : NO_ACTIVITY;
    try {
      const a = await send(act.url(path), opts);
      act.end(a.ok);
      return a;
    } catch (e) { act.end(false); throw e; }
  }
  const HEADER_FIELDS = {
    title: ["Title", "the note's title"],
    subtitle: ["Subtitle", "what the note is about"],
    note: ["Note", "the small line under the title"],
    lang: ["Written in", ""],
    target: ["The language it is about", ""],
  };
  // the header an upload lacks, asked for: the fields it lacks, and the lines
  // that will go in.  Resolves to those fields, or null when the file is skipped.
  function askHeader(label, need, lists) {
    return new Promise(resolve => {
      const missing = need.missing || [], defaults = need.defaults || {};
      const root = $("#modal-root"); root.innerHTML = "";
      const ov = document.createElement("div"); ov.className = "modal-overlay";
      ov.innerHTML = `<div class="modal header-modal" role="dialog" aria-modal="true">
        <h3></h3><p></p><div class="modal-fields"></div>
        <pre class="header-preview" aria-label="What goes into the header"></pre>
        <div class="row"><button class="btn" data-x="skip">Skip this file</button>
          <button class="btn primary" data-x="ok"></button></div></div>`;
      $("h3", ov).textContent = need.present ? `“${label}”: the header is incomplete`
                                             : `“${label}” has no header`;
      $("p", ov).textContent = need.present
        ? `Its header has no ${missing.join(", ")}. Only these lines are added; the rest of the header stays as it is.`
        : "A document is filed by the lines at its top. Fill them in and they are added above the text.";
      $('[data-x="ok"]', ov).textContent = need.present ? "Add them and import" : "Add the header and import";
      const box = $(".modal-fields", ov), preview = $(".header-preview", ov);
      for (const key of missing) {
        const [name, hint] = HEADER_FIELDS[key] || [key, ""];
        const lab = document.createElement("label"); lab.className = "modal-field";
        lab.textContent = name;
        let input;
        if (key === "lang" || key === "target") {
          input = document.createElement("select");
          const options = (key === "lang" ? lists.langs : lists.targets) || [];
          for (const o of options) {
            const opt = document.createElement("option");
            opt.value = o.code; opt.textContent = `${o.name} (${o.code})`;
            input.appendChild(opt);
          }
          // the library's language chip, when one is picked, is the likeliest target
          const chip = sharedLang();
          const want = key === "target" && options.some(o => o.code === chip) ? chip : defaults[key];
          if (want && options.some(o => o.code === want)) input.value = want;
        } else {
          input = document.createElement("input");
          input.type = "text"; input.spellcheck = false; input.autocomplete = "off";
          input.value = defaults[key] || ""; input.placeholder = hint;
        }
        input.dataset.key = key;
        lab.appendChild(input);
        box.appendChild(lab);
      }
      const values = () => Object.fromEntries($$("[data-key]", box).map(i => [i.dataset.key, i.value.trim()]));
      const draw = () => {
        const v = values(), lines = missing.map(k => `${k}: ${v[k] || ""}`.trimEnd());
        preview.textContent = need.present ? lines.map(l => "+ " + l).join("\n")
                                           : ["---", ...lines, "---"].join("\n");
      };
      box.addEventListener("input", draw);
      box.addEventListener("change", draw);
      draw();
      const done = answer => { root.innerHTML = ""; resolve(answer); };
      const ok = () => {
        const v = values();
        if (missing.includes("title") && !v.title) {
          toast("Give the note a title", true);
          $('[data-key="title"]', box).focus();
          return;
        }
        done(v);
      };
      $('[data-x="skip"]', ov).addEventListener("click", () => done(null));
      $('[data-x="ok"]', ov).addEventListener("click", ok);
      ov.addEventListener("keydown", e => {
        if (e.key === "Escape") { e.preventDefault(); done(null); }
        else if (e.key === "Enter" && e.target.matches("input")) { e.preventDefault(); ok(); }
      });
      root.appendChild(ov);
      const first = $("[data-key]", box);
      if (first) first.focus();
    });
  }
  /* The header first, then the name: a file whose title another document
     of the library has already -- or, in a zip, another file of it -- is
     asked about in the name-conflict dialog (askNames), and cancelling it
     skips the file, as skipping its header does. */
  async function uploadMarkdown(file) {
    const text = await file.text();
    let body = {markdown: text, check_header: true, name: file.name};
    let a = await send("/api/docs", {method: "POST", json: body});
    if (a.status === 422 && a.data.header_needed) {
      const header = await askHeader(file.name, a.data, a.data);
      if (!header) return null;
      body = {markdown: text, header, name: file.name};
      a = await send("/api/docs", {method: "POST", json: body});
    }
    if (nameClash(a)) {
      a = await askNames(a.data, renames =>
        send("/api/docs", {method: "POST", json: Object.assign({}, body, {renames})}));
      if (!a) return null;
    }
    if (!a.ok) throw refusal(a);
    return {docs: [a.data.meta], warnings: []};
  }
  async function uploadZip(file) {
    // the file itself, streamed and sent again as often as it is asked for
    // (restoreBackup, above, says why)
    const post = (headers, renames) => sendWorking(`Importing ${file.name}`,
      withName("/api/docs/zip" + query({headers, renames}), file.name),
      {method: "POST", body: file, headers: {"Content-Type": "application/zip"}});
    let a = await post(null, null), headers = null;
    if (a.status === 422 && a.data.header_needed) {
      // each file asked about in turn; one skipped is left out, the rest go in
      headers = {};
      for (const need of a.data.files || [])
        headers[need.name] = await askHeader(`${need.name}, in ${file.name}`, need, a.data);
      a = await post(headers, null);
    }
    if (nameClash(a)) {
      a = await askNames(a.data, renames => post(headers, renames));
      if (!a) return null;
    }
    if (!a.ok) throw refusal(a);
    return {docs: a.data.docs || [], warnings: a.data.warnings || []};
  }
  // ?headers=…&renames=… for the raw-body routes: each a JSON, when there is one
  function query(parts) {
    const q = Object.entries(parts).filter(([, v]) => v)
      .map(([k, v]) => `${k}=${encodeURIComponent(JSON.stringify(v))}`);
    return q.length ? "?" + q.join("&") : "";
  }
  // …and the file's own name, plain, which the activity list shows while it goes up
  function withName(path, name) {
    return path + (path.includes("?") ? "&" : "?") + "name=" + encodeURIComponent(name);
  }
  $("#file-upload").addEventListener("change", async e => {
    const files = [...e.target.files];
    e.target.value = "";
    if (!files.length) return;
    const made = [], notes = [];
    for (const f of files) {
      try {
        const out = /\.zip$/i.test(f.name) ? await uploadZip(f) : await uploadMarkdown(f);
        if (!out) continue;                         // skipped in its dialog
        made.push(...out.docs);
        notes.push(...out.warnings);
      } catch (err) {
        notes.push(`${f.name}: ${err.message}`);
      }
    }
    if (made.length === 1 && !notes.length) { location.href = BASE + "/doc/" + made[0].id; return; }
    if (!made.length && !notes.length) return;
    toast(`${made.length} document${made.length === 1 ? "" : "s"} imported`
          + (notes.length ? " — " + notes.join(" · ") : ""), notes.length > 0);
    loadDocs(); loadTags();
  });

  api("/api/status").then(s => {
    $("#statusline").textContent =
      `${s.docs} document${s.docs === 1 ? "" : "s"} · ` +
      `XeLaTeX ${s.xelatex ? "✓" : "✗ missing"} · Italian hyphenation ` +
      (s.hyphenation === null ? "…" : s.hyphenation ? "✓" : "✗") +
      ` · library: ${s.library}`;
  }).catch(() => {});

  loadTags();
  loadDocs();
}

/* ---------------- doc page ---------------- */

/* The bar on a phone: away as the page moves down, back on the smallest move
   up -- not only at the top of the page, which would mean scrolling a whole
   note back to reach one button. This is lib/parseh.js's bars() written again
   in the studio's own script, down to the class name and the breakpoint,
   because the studio does not load parseh.js; the toolbox should behave as
   one thing. NOTHING CHANGES ON A WIDE SCREEN: the listener is wired only
   while the media query matches, and the class it toggles is defined only
   inside the same query.

   A document's reading page has TWO bars, the topbar and the toolbar under
   it, and on a wide screen only the toolbar is pinned. On a phone both are:
   the topbar at the top, the toolbar right under it (--topbar-h, measured
   here while the query matches), and both go away together and come back
   together -- two bars pinned are a good part of a phone's screen however
   short app.css makes them there, and one left standing is the reading
   page's whole problem.  Near the top they stand, as everywhere: there that
   means until the page's whole head (topbar, tags, toolbar) has scrolled
   by, because putting the bars away while their places are still on the
   screen would only leave those places empty. */
const PHONE_MQ = "(max-width: 560px)";
const pinnedPair = () => PAGE === "doc" && !!window.matchMedia
  && window.matchMedia(PHONE_MQ).matches && !!$(".topbar") && !!$("#typobar");
// Until this moment the bars neither go nor come: a bar that goes or comes
// (put away by hand) moves the text under it, the browser scrolls to keep the
// text where it was, and that scroll is no reader's.
let barsHeldUntil = 0;
const holdBars = ms => { barsHeldUntil = performance.now() + ms; };
function barsStand() {
  if (!pinnedPair()) return 56;
  const h = sel => { const e = $(sel); return e ? e.getBoundingClientRect().height : 0; };
  return Math.max(56, h(".topbar") + h(".metabar") + h("#typobar"));
}
function bindBarHide() {
  if (!window.matchMedia) return;
  const mq = window.matchMedia(PHONE_MQ);
  const topbar = PAGE === "doc" && $("#typobar") ? $(".topbar") : null;
  let lastY = 0, ticking = false, off = false, sizer = null;
  const set = v => {
    if (v === off) return;
    off = v;
    document.body.classList.toggle("barhidden", v);
    // a menu hung from the reading page's bars would stay over the text,
    // catching taps (the gear's sheet hangs from nothing: it stands over the
    // page on its own, and the bars going leaves it where it is)
    if (v && PAGE === "doc") {
      document.querySelectorAll(".topbar details[open], .toolbar details[open]")
        .forEach(d => { d.open = false; });
    }
  };
  const read = () => {
    ticking = false;
    const y = Math.max(0, window.pageYOffset || 0);
    const d = y - lastY;
    if (Math.abs(d) < 4) return;          // a finger resting is not a move
    lastY = y;
    if (performance.now() < barsHeldUntil) return;
    set(y > barsStand() && d > 0);
  };
  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(read);
  };
  const measure = () => document.documentElement.style.setProperty(
    "--topbar-h", topbar.getBoundingClientRect().height + "px");
  const follow = () => {
    if (mq.matches) {
      lastY = window.pageYOffset || 0;
      window.addEventListener("scroll", onScroll, {passive: true});
      if (topbar) {
        measure();
        if (window.ResizeObserver && !sizer) {
          sizer = new ResizeObserver(measure);
          sizer.observe(topbar);
        }
      }
    } else {
      window.removeEventListener("scroll", onScroll);
      set(false);
      if (sizer) { sizer.disconnect(); sizer = null; }
      document.documentElement.style.removeProperty("--topbar-h");
      // The window widened past a phone's -- a phone turned on its side --
      // with the bars standing: the pinned topbar was the first thing on the
      // screen, the browser keeps the page where that thing is, and the
      // topbar, back in the flow, is at the very top of the page.  So the
      // page is put back where it was, as it stays on a desktop.
      const was = topbar ? Math.max(lastY, window.pageYOffset || 0) : 0;
      if (was > 1) requestAnimationFrame(() => requestAnimationFrame(() => {
        if ((window.pageYOffset || 0) < 1) window.scrollTo(0, was);
      }));
    }
  };
  follow();
  if (mq.addEventListener) mq.addEventListener("change", follow);
  // Tab moving along the topbar's row, which scrolls sideways on a phone:
  // the control that takes the focus is brought into the row's view
  if (topbar) document.addEventListener("focusin", e => {
    const row = mq.matches && e.target.closest ? e.target.closest(".topbar-actions") : null;
    if (row && row.scrollWidth > row.clientWidth)
      e.target.scrollIntoView({block: "nearest", inline: "nearest"});
  });
}

/* Back to the top of a long note. It shows itself only once the page has
   moved a screenful down: a button that is always there is one more thing
   between the reader and the text. */
function bindToTop() {
  const b = $("#btn-top");
  if (!b) return;
  const show = () => { b.hidden = (window.pageYOffset || 0) < 400; };
  window.addEventListener("scroll", show, {passive: true});
  show();
  b.addEventListener("click", () => {
    window.scrollTo({top: 0, behavior: "smooth"});
  });
}

/* THE DECK DOOR, from both studio pages.  A reading view copies one of its
   exercises into a deck ("+ Deck"); the editor takes one out of a deck and
   puts it in the document ("Load from a deck…").  The decks are another door
   with an address of their own (data-decks-base), so they are fetched there
   and not through api(), which prefixes the studio's.  Empty where no deck
   store is reachable: no button, no handler.  A note beside a book or a video
   names its mount (data-notes-source), since the decks read and write that
   shelf's documents and not the studio library's. */
const decksBase = document.body.dataset.decksBase || "";
const notesSource = document.body.dataset.notesSource || "";
async function decksFetch(path, opts = {}) {
  const init = Object.assign({}, opts);
  if (init.json !== undefined) {
    init.body = JSON.stringify(init.json);
    init.headers = {"Content-Type": "application/json"};
    delete init.json;
  }
  const r = await fetch(decksBase + path, init);
  let data = {};
  try { data = await r.json(); } catch (e) { /* not JSON: no deck store answered */ }
  if (!r.ok || data.ok === false) {
    const err = new Error(data.error || (r.status + " " + r.statusText));
    err.conflict = data.conflict || "";
    throw err;
  }
  return data;
}
const deckUrl = path => "/api/decks/" + String(path).split("/").map(encodeURIComponent).join("/");

/* THE DECK HALF OF BOTH COPY DIALOGS -- one exercise (+ Deck) and a page's
   worth (+ Add all exercises): the decks of the page's language in a select,
   the one used last already chosen, "+ New deck…" at its foot and the name
   field that option needs.  `ensure()` makes the new deck when that is what
   is chosen, and answers what it made.  `unmake()` takes a deck made for a
   copy that then failed away again, so the store is as it was before -- and
   when the deck cannot be removed it stays selected, so that trying again
   does not make a second one. */
const DECK_FIELDS = `<label class="modal-field">Deck<select data-x="deck"></select></label>
    <label class="modal-field" data-x="new-field">Name of the new deck
      <input type="text" data-x="name" spellcheck="false" autocomplete="off"></label>`;
async function deckPicker(ov, {allowNew = true} = {}) {
  const code = lang().code, lastKey = "parseh_deck_last_" + code;
  const data = await decksFetch("/api/decks?lang=" + encodeURIComponent(code));
  const decks = (data.decks || []).filter(d => d.lang === code);
  let last = "";
  try { last = localStorage.getItem(lastKey) || ""; } catch (e) { /* private mode */ }
  const select = $('[data-x="deck"]', ov), newField = $('[data-x="new-field"]', ov);
  const nameInput = $('[data-x="name"]', ov);
  nameInput.placeholder = `${lang().name} exercises`;
  // a copy INTO a deck may make one on the way; a copy OUT of one has
  // nothing to take from a deck that does not exist yet (allowNew: false)
  const newOption = document.createElement("option");
  newOption.value = ""; newOption.textContent = "+ New deck…";
  if (allowNew) select.appendChild(newOption);
  const addDeck = d => {
    const o = document.createElement("option");
    const n = (d.counts || {}).total || 0;
    o.value = d.path; o.dataset.name = d.name;
    o.textContent = `${d.name} · ${n} exercise${n === 1 ? "" : "s"}`;
    select.insertBefore(o, newOption.parentNode ? newOption : null);
    return o;
  };
  decks.forEach(addDeck);
  select.value = decks.some(d => d.path === last) ? last : (decks[0] ? decks[0].path : "");
  const syncNew = () => { newField.hidden = !allowNew || select.value !== ""; };
  select.addEventListener("change", () => { syncNew(); if (!select.value) nameInput.focus(); });
  syncNew();
  return {
    select, nameInput,
    name: () => (select.selectedOptions[0] && select.selectedOptions[0].dataset.name) || select.value,
    async ensure() {
      if (select.value) return null;
      const name = nameInput.value.trim();
      if (!name) { nameInput.focus(); throw new Error("Give the new deck a name"); }
      const answer = await decksFetch("/api/decks", {method: "POST", json: {name, lang: code}});
      const made = {deck: answer.deck, option: addDeck(answer.deck)};
      select.value = answer.deck.path;
      syncNew();
      return made;
    },
    async unmake(made) {
      const gone = await decksFetch(deckUrl(made.deck.path), {method: "DELETE"})
        .then(() => true, () => false);
      if (!gone) return;
      made.option.remove();
      select.value = "";
      syncNew();
    },
    remember(path) {
      try { localStorage.setItem(lastKey, path); } catch (e) { /* private mode */ }
    },
    focus() { (select.value ? select : nameInput).focus(); }
  };
}

function initDoc() {
  let meta = JSON.parse($("#doc-meta").textContent);
  const sheet = $("#sheet");
  const frame = $("#pdfframe");
  const btnBuild = $("#btn-build");
  const btnPdf = $("#btn-pdf-toggle");
  // the chrome outside the sheet (build badges, modals) takes the
  // document's language too, so its tokens resolve there
  document.body.dataset.lang = lang().code;
  // the typography is the shared state's (studioTypo), moved by the gear's
  // rows; the PDF is built at its scale
  const getTypo = studioTypo.get;
  studioTypo.refresh();
  bindPersianCopy(sheet);
  bindFootnoteClouds(sheet);
  bindWordCloud(sheet, {applyTranslit: docMarkApplier(DOC_ID, "translit"),
                        applyKana: docMarkApplier(DOC_ID, "kana")});
  bindImageLayout(sheet, {save: async payload => {
    const data = await api(`/api/docs/${DOC_ID}/image-layout`,
                           {method: "POST", json: payload});
    if (onSourceChanged) onSourceChanged(data.meta);
  }});
  bindLaLayout(sheet, {save: async payload => {
    const data = await api(`/api/docs/${DOC_ID}/la-layout`,
                           {method: "POST", json: payload});
    if (onSourceChanged) onSourceChanged(data.meta);
  }});
  armClipReplay(sheet);
  bindExercises(sheet);
  syncStickyOffset();
  bindBarsToggle();
  bindGlosses();
  bindToTop();
  bindStopServer();

  // what one exercise of this page is copied as: which it is, of what kind,
  // the page as it was when it loaded -- and the shelf a note is on
  function copyPayload(ex) {
    const payload = {doc_id: DOC_ID, ordinal: +ex.dataset.exercise,
                     subtype: ex.dataset.subtype, updated: meta.updated};
    if (notesSource) payload.source = notesSource;
    return payload;
  }

  async function copyToDeck(ex) {
    const ov = document.createElement("div"); ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal ex-to-deck-modal" role="dialog" aria-modal="true">
      <h3>Copy this exercise into a deck</h3><p></p>
      ${DECK_FIELDS}
      <div class="row"><button class="btn" data-x="cancel">Cancel</button>
        <button class="btn primary" data-x="copy">Copy</button></div></div>`;
    const picker = await deckPicker(ov);
    const root = $("#modal-root"); root.innerHTML = "";
    const kicker = $(".ex-kicker", ex);
    $("p", ov).textContent = `${kicker ? kicker.textContent : "Exercise"} — copied exactly as it `
      + `is written here. A deck holds exercises in one language: these are your ${lang().name} decks.`;
    const copyBtn = $('[data-x="copy"]', ov);
    const close = () => { if (ov.parentNode) root.removeChild(ov); };
    $('[data-x="cancel"]', ov).addEventListener("click", close);
    ov.addEventListener("click", e => { if (e.target === ov) close(); });
    ov.addEventListener("keydown", e => {
      if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "Enter" && e.target === picker.nameInput) { e.preventDefault(); copyBtn.click(); }
    });
    let busy = false;
    copyBtn.addEventListener("click", async () => {
      if (busy) return;                  // one copy per click, however fast
      busy = true; copyBtn.disabled = true;
      let made = null;
      try {
        made = await picker.ensure();
        const path = picker.select.value, deckName = picker.name();
        const payload = copyPayload(ex);
        let result;
        try {
          result = await decksFetch(deckUrl(path) + "/copy", {method: "POST", json: payload});
        } catch (err) {
          if (made && err.conflict !== "duplicate") await picker.unmake(made);
          if (err.conflict === "stale") {
            close();
            throw new Error("This page is out of date — reload it, then copy");
          }
          if (err.conflict !== "duplicate") throw err;
          if (!confirm(`This exercise is already in “${deckName}” — add it again?`)) return;
          result = await decksFetch(deckUrl(path) + "/copy",
            {method: "POST", json: Object.assign({}, payload, {force: true})});
        }
        picker.remember(path);
        close();
        const warnings = result.warnings || [];
        toast(`Copied into “${(result.deck || {}).name || deckName}”`
          + ((result.items || []).length > 1 ? " as two linked cards" : "")
          + (warnings.length ? " — " + warnings.join(" · ") : ""), warnings.length > 0);
      } catch (err) {
        toast(err.message, true);
      } finally {
        busy = false; copyBtn.disabled = false;
      }
    });
    root.appendChild(ov);
    picker.focus();
  }
  // capture, and stopped there: the click is the modal's alone, never an
  // answer to the exercise it sits on or a copy of the text around it
  if (decksBase) sheet.addEventListener("click", e => {
    const button = e.target.closest(".ex-to-deck");
    if (!button || !sheet.contains(button)) return;
    e.preventDefault();
    e.stopPropagation();
    const ex = button.closest(".exercise");
    if (ex) copyToDeck(ex).catch(err => toast("Could not open the decks: " + err.message, true));
  }, true);

  /* "+ Add all exercises": the exercises of this page into one deck at once.
     It offers every exercise + Deck could copy -- one that shows errors has
     no button, and a deck would refuse it -- in the page's order, all of them
     ticked: untick the ones to leave out.  Each goes through the same /copy
     as + Deck, one after another.  One the deck already has is left out
     unless "add again" is ticked, one the deck refuses is counted and the
     rest still go in, and a page gone stale stops the run, since every
     exercise after it could be the wrong one.  A deck made for a run that
     then added nothing is taken away again, as + Deck takes away its own. */
  const addAllBtn = $("#btn-add-all");
  const copyable = () => $$(".exercise", sheet)
    .filter(ex => $(":scope > .ex-head > .ex-to-deck", ex));
  let glossCards = [];
  try { glossCards = JSON.parse($("#doc-glosses").textContent) || []; }
  catch (e) { /* a document without a usable gloss list offers exercises only */ }
  // an exercise as the list names it: its kind, and its first words -- the
  // prompt, a flashcard's front, or failing both whatever its body says
  function exerciseWords(ex) {
    const kicker = $(":scope > .ex-head > .ex-kicker", ex);
    const words = $(":scope > .ex-prompt", ex) || $(".ex-card-front", ex) || $(":scope > .ex-body", ex);
    const text = (words ? words.textContent : "").replace(/\s+/g, " ").trim();
    return {kind: kicker ? kicker.textContent.trim() : "Exercise",
            text: text.length > 90 ? text.slice(0, 89).trimEnd() + "…" : text};
  }
  async function addAll() {
    const exs = copyable(), unoffered = $$(".exercise", sheet).length - exs.length;
    const ov = document.createElement("div"); ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal ex-all-modal" role="dialog" aria-modal="true">
      <h3>Add all exercises to a deck</h3><p></p>
      ${DECK_FIELDS}
      <div class="ex-all-head"><span data-x="count"></span>
        <button class="btn ghost" data-x="all">Select all</button>
        <button class="btn ghost" data-x="none">Select none</button></div>
      <button class="btn small ghost ex-all-gloss-toggle" data-x="glosses" type="button"
              aria-pressed="false" ${glossCards.length ? "" : "hidden"}></button>
      <div class="ex-all-list" data-x="list"></div>
      <label class="ex-all-again"><input type="checkbox" data-x="again">
        Add again the ones this deck already has</label>
      <div class="row"><span class="ex-all-progress" data-x="progress"></span>
        <button class="btn" data-x="cancel">Cancel</button>
        <button class="btn" data-x="chain" title="Make the ticked exercises the steps of ONE follow-up question in the deck: a chain answered one after the other">Make a follow-up chain of these…</button>
        <button class="btn primary" data-x="add">Add</button></div></div>`;
    const picker = await deckPicker(ov);
    const root = $("#modal-root"); root.innerHTML = "";
    $("p", ov).textContent = "Every exercise on this page, each copied exactly as it is written "
      + `— untick the ones to leave out. A deck holds exercises in one language: these are your ${lang().name} decks.`
      + (unoffered ? ` ${unoffered} exercise${unoffered === 1 ? " that needs attention is"
                                                           : "s that need attention are"} not offered.` : "");
    const list = $('[data-x="list"]', ov), count = $('[data-x="count"]', ov);
    const addBtn = $('[data-x="add"]', ov), again = $('[data-x="again"]', ov), chainBtn = $('[data-x="chain"]', ov);
    const progress = $('[data-x="progress"]', ov);
    function addRow(kind, text, ordinal, subtype, gloss = false) {
      const row = document.createElement("label"); row.className = "ex-all-item";
      row.hidden = gloss;
      const box = document.createElement("input");
      box.type = "checkbox"; box.checked = true;
      box.dataset.ordinal = ordinal; box.dataset.subtype = subtype;
      const num = document.createElement("span");
      num.className = "ex-all-num"; num.textContent = gloss ? `G${ordinal}` : ordinal;
      const what = document.createElement("span");
      what.className = "ex-all-kind"; what.textContent = kind;
      const words = document.createElement("span");
      words.className = "ex-all-text"; words.dir = "auto"; words.textContent = text; words.title = text;
      row.append(box, num, what, words);
      list.appendChild(row);
    }
    for (const ex of exs) {
      const {kind, text} = exerciseWords(ex);
      addRow(kind, text, ex.dataset.exercise, ex.dataset.subtype);
    }
    glossCards.forEach((g, i) => addRow("Gloss flashcard", `${g.fa} — ${g.tr}`,
                                        i + 1, "gloss-flashcard", true));
    const glossToggle = $('[data-x="glosses"]', ov);
    glossToggle.textContent = `Show gloss flashcards (${glossCards.length})`;
    glossToggle.addEventListener("click", () => {
      const show = glossToggle.getAttribute("aria-pressed") !== "true";
      glossToggle.setAttribute("aria-pressed", String(show));
      glossToggle.textContent = `${show ? "Hide" : "Show"} gloss flashcards (${glossCards.length})`;
      $$(".ex-all-item", list).slice(exs.length).forEach(row => { row.hidden = !show; });
      sync();
    });
    let busy = false;
    const boxes = () => $$(".ex-all-item:not([hidden]) input[type=checkbox]", list);
    // what can be a step: an exercise of the page, not a gloss flashcard and not a follow-up
    const chainable = () => boxes().filter(b => b.checked && b.dataset.subtype !== "gloss-flashcard" && b.dataset.subtype !== "follow-up");
    const sync = () => {
      const n = boxes().filter(b => b.checked).length;
      count.textContent = `${n} of ${boxes().length} selected`;
      addBtn.textContent = `Add ${n} exercise${n === 1 ? "" : "s"}`;
      addBtn.disabled = busy || !n;
      chainBtn.disabled = busy || chainable().length < 2;
    };
    list.addEventListener("change", sync);
    $('[data-x="all"]', ov).addEventListener("click", () => { boxes().forEach(b => { b.checked = true; }); sync(); });
    $('[data-x="none"]', ov).addEventListener("click", () => { boxes().forEach(b => { b.checked = false; }); sync(); });
    const close = () => { if (ov.parentNode) root.removeChild(ov); };
    $('[data-x="cancel"]', ov).addEventListener("click", close);
    ov.addEventListener("click", e => { if (e.target === ov && !busy) close(); });
    ov.addEventListener("keydown", e => {
      if (e.key === "Escape") { e.preventDefault(); if (!busy) close(); }
      else if (e.key === "Enter" && e.target === picker.nameInput) { e.preventDefault(); addBtn.click(); }
    });
    addBtn.addEventListener("click", async () => {
      const picked = boxes().filter(b => b.checked)
        .map(b => b.dataset.subtype === "gloss-flashcard"
          ? {doc_id: DOC_ID, ordinal: +b.dataset.ordinal, subtype: "gloss-flashcard",
             updated: meta.updated, ...(notesSource ? {source: notesSource} : {})}
          : copyPayload(exs.find(ex => ex.dataset.exercise === b.dataset.ordinal)));
      if (busy || !picked.length) return;
      // the dialog holds still while it works: nothing in it changes under a
      // run, and nothing closes it
      busy = true;
      const controls = $$("select, input, button", ov);
      controls.forEach(el => { el.disabled = true; });
      let made = null, added = 0, already = 0, stale = false, deckName = "";
      const refused = [], warnings = [];
      try {
        made = await picker.ensure();
        const path = picker.select.value;
        deckName = picker.name();
        for (let i = 0; i < picked.length; i++) {
          progress.textContent = `Adding ${i + 1} of ${picked.length}…`;
          const payload = picked[i];
          if (again.checked) payload.force = true;
          try {
            const result = await decksFetch(deckUrl(path) + "/copy", {method: "POST", json: payload});
            added += (result.items || []).length || 1;      // a both-repeat card is two
            if ((result.deck || {}).name) deckName = result.deck.name;
            for (const w of result.warnings || []) if (!warnings.includes(w)) warnings.push(w);
          } catch (err) {
            if (err.conflict === "duplicate") { already++; continue; }
            if (err.conflict === "stale") { stale = true; break; }
            refused.push(`${payload.subtype === "gloss-flashcard" ? "gloss " : ""}${payload.ordinal}: ${err.message}`);
          }
        }
        if (made && !added) await picker.unmake(made);
        if (added) picker.remember(path);
        if (stale) {
          close();
          throw new Error((added ? `Added ${added} to “${deckName}”, then stopped: ` : "")
                          + "this page is out of date — reload it, then add");
        }
        if (!added) {
          // nothing went in, and the dialog stays: another deck, another choice
          throw new Error(refused.length
            ? `Nothing was added — ${refused.length} refused (${refused[0]})`
              + (already ? `, ${already} already in “${deckName}”` : "")
            : `${already === 1 ? "That exercise is" : `All ${already} are`} already in “${deckName}”`
              + " — tick “Add again” to add them anyway");
        }
        close();
        const notes = [];
        if (already) notes.push(`${already} already there, left out`);
        if (refused.length) notes.push(`${refused.length} refused (${refused[0]})`);
        toast(`Added ${added} exercise${added === 1 ? "" : "s"} to “${deckName}”`
          + (notes.length ? " — " + notes.join(" · ") : "")
          + (warnings.length ? " — " + warnings.join(" · ") : ""),
          refused.length > 0 || warnings.length > 0);
      } catch (err) {
        toast(err.message, true);
      } finally {
        busy = false;
        progress.textContent = "";
        controls.forEach(el => { el.disabled = false; });
        sync();
      }
    });
    // THE TICKED EXERCISES AS ONE FOLLOW-UP of the deck: the server makes the chain of them, in the page's order, with
    // the files of every step; look it over, or change a step, with ✎ Edit in the deck
    chainBtn.addEventListener("click", async () => {
      const picked = chainable();
      if (busy || picked.length < 2) return;
      busy = true;
      const controls = $$("select, input, button", ov);
      controls.forEach(el => { el.disabled = true; });
      let made = null, deckName = "";
      try {
        made = await picker.ensure();
        const path = picker.select.value;
        deckName = picker.name();
        progress.textContent = "Making the follow-up…";
        const payload = {doc_id: DOC_ID, ordinals: picked.map(b => +b.dataset.ordinal), subtype: "follow-up",
                         updated: meta.updated, ...(notesSource ? {source: notesSource} : {})};
        if (again.checked) payload.force = true;
        let result;
        try {
          result = await decksFetch(deckUrl(path) + "/copy", {method: "POST", json: payload});
        } catch (err) {
          if (made) await picker.unmake(made);
          if (err.conflict === "duplicate") throw new Error(`That follow-up is already in “${deckName}” — tick “Add again” to add it anyway`);
          if (err.conflict === "stale") { close(); throw new Error("this page is out of date — reload it, then add"); }
          throw err;
        }
        picker.remember(path);
        close();
        if ((result.deck || {}).name) deckName = result.deck.name;
        toast(`Added one follow-up of ${picked.length} steps to “${deckName}”`
              + ((result.warnings || []).length ? " — " + result.warnings.join(" · ") : ""), (result.warnings || []).length > 0);
      } catch (err) {
        toast(err.message, true);
      } finally {
        busy = false;
        progress.textContent = "";
        controls.forEach(el => { el.disabled = false; });
        sync();
      }
    });
    sync();
    root.appendChild(ov);
    picker.focus();
  }
  const offered = copyable().length;
  if (decksBase && addAllBtn && (offered || glossCards.length)) {
    addAllBtn.hidden = false;
    addAllBtn.title = "Choose this page's exercises and optional gloss flashcards to add to a deck";
    addAllBtn.addEventListener("click", () =>
      addAll().catch(err => toast("Could not open the decks: " + err.message, true)));
  }

  // a colour change edits the markdown, so the built PDF goes stale
  onSourceChanged = m => {
    if (m) { meta = Object.assign(meta, m); renderBuildInfo(); }
  };

  // A failed build attempt is tracked separately from meta.build so it
  // never destroys the record of the last GOOD build: the previous PDF
  // and .tex are still on disk and downloadable, and the toggle keeps
  // working. buildError is cleared on the next success.
  // buildLog is the end of the compile log the server sent with the
  // refusal: LaTeX says WHERE it stopped in the lines around the error, not
  // in the error line alone, and the file it is read from
  // (build/compile-error.log) is one nobody should have to go to a file
  // manager for.
  let buildError = null, buildLog = "";

  /* The PDF options: the print size (11 pt, or 14, 17, 20 for readers with
     low vision) and black and white (for the photocopier).  They belong to
     the build, not to the markdown, so they are kept in this browser, per
     document, beside its typography (exlex-typo:<id>); a document with no
     choice made here yet starts from the options its PDF was built with, so
     the menu says what the PDF on disk is. */
  const PDF_SIZES = [11, 14, 17, 20];
  const pdfKey = "exlex-pdf:" + DOC_ID;
  const pdfOptionsOf = o => ({
    size: PDF_SIZES.includes(Number(o && o.size)) ? Number(o.size) : 11,
    mono: !!(o && o.mono === true),
  });
  let pdfOpts = (() => {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(pdfKey) || "null"); } catch (e) { /* none */ }
    const b = meta.build || {};
    return pdfOptionsOf(saved || (b.status === "ok" ? b : {}));
  })();
  const describePdf = o => `${o.size} pt, ${o.mono ? "black and white" : "in colour"}`;
  const sizeRadios = $$('input[name="pdf-size"]');
  const monoBox = $("#ck-pdf-mono");
  sizeRadios.forEach(r => { r.checked = Number(r.value) === pdfOpts.size; });
  if (monoBox) monoBox.checked = pdfOpts.mono;
  const readPdfOptions = () => {
    const on = sizeRadios.find(r => r.checked);
    pdfOpts = pdfOptionsOf({size: on ? on.value : 11, mono: !!(monoBox && monoBox.checked)});
    try { localStorage.setItem(pdfKey, JSON.stringify(pdfOpts)); } catch (e) { /* private mode */ }
    renderBuildInfo();
  };
  sizeRadios.forEach(r => r.addEventListener("change", readPdfOptions));
  if (monoBox) monoBox.addEventListener("change", readPdfOptions);

  function renderBuildInfo() {
    const b = meta.build || {status: "none"};
    const box = $("#buildinfo");
    const built = b.status === "ok";
    // download/toggle availability follows the last GOOD build, not the
    // last attempt.
    btnPdf.disabled = !built;
    const dlPdf = $("#dl-pdf"), dlTex = $("#dl-tex"), dlTexZip = $("#dl-texzip");
    if (dlPdf) dlPdf.classList.toggle("disabled", !built);
    if (dlTex) dlTex.classList.toggle("disabled", !built);
    if (dlTexZip) dlTexZip.classList.toggle("disabled", !built);

    // The badge says what LaTeX said, not that something went wrong: the
    // first line of it fits a badge, the whole message is the hover, and
    // where the server sent the log's tail the badge opens it, so the
    // reason is on the page and not in a file beside the PDF.
    const firstLine = (buildError || "").split("\n")[0].slice(0, 120);
    const errBadge = !buildError ? ""
      : buildLog
        ? `<details><summary class="badge err" title="${escAttr(buildError)}">build failed — ${escAttr(firstLine)}</summary>`
          + `<div class="fails"><pre style="margin:0; white-space:pre-wrap">${escAttr(buildLog)}</pre>`
          + `<small>The whole log is in the document's <code>build/compile-error.log</code>.</small></div></details>`
        : `<span class="badge err" title="${escAttr(buildError)}">build failed — ${escAttr(firstLine)}</span>`;
    if (!built) {
      box.innerHTML = errBadge || `<span class="badge">no PDF built yet</span>`;
      return;
    }
    const stale = b.stale
      ? `<span class="badge warn" title="The markdown changed after this PDF was built">source changed — rebuild</span>` : "";
    const overfull = (b.overfull || []).length
      ? `<span class="badge warn">${b.overfull.length} overfull</span>` : "";
    let verify;
    const L = lang();
    const vlabel = L.dir === "rtl" ? "RTL" : "text";
    if (b.verify_failed > 0) {
      verify = `<details><summary class="badge err">${b.verify_failed} ${vlabel} FAIL`
        + verifyCloud() + `</summary>
        <div class="fails">${(b.failures || []).map(() =>
          `<div><span class="fa" dir="${L.dir}" lang="${L.code}"></span> — <em></em></div>`).join("")}</div></details>`;
    } else if (b.verified === false) {
      verify = `<span class="badge warn" title="PyMuPDF not installed — the PDF text was not checked">not verified</span>`;
    } else {
      verify = `<span class="badge ok" title="Every ${escAttr(L.name)} string verified in the PDF${L.dir === "rtl" ? ", in correct RTL order" : ""}">${b.verify_ok}/${b.verify_ok} ${vlabel} ✓</span>`;
    }
    const pages = b.pages != null ? `${b.pages} pages · ` : "";
    // what this PDF was built with (a build from before the options is an
    // 11 pt one in colour, which is what every build was), and, when the
    // menu now says otherwise, that it was -- a PDF to rebuild, not a
    // fault: its own badge, its own words
    const was = pdfOptionsOf(b);
    const printed = `${was.size} pt${was.mono ? " · B&W" : ""}`;
    const other = (was.size !== pdfOpts.size || was.mono !== pdfOpts.mono)
      ? `<span class="badge warn" id="pdf-options-stale" title="${escAttr(
          `This PDF was built at ${describePdf(was)}; the PDF options now say ${describePdf(pdfOpts)}. Build PDF again to use them.`)}">built with other options — rebuild</span>` : "";
    box.innerHTML =
      `<span class="badge ok">PDF ✓ ${pages}scale ${b.scale} · ${printed}</span>` +
      verify + overfull + stale + other +
      `<span class="badge">built ${fmtDate(b.built_at)}</span>` + errBadge;
    if (b.verify_failed > 0) {
      $$(".fails > div", box).forEach((div, i) => {
        const f = (b.failures || [])[i] || ["", ""];
        $(".fa", div).textContent = f[0];
        $("em", div).textContent = f[1];
      });
    }
  }

  function refreshFrame() {
    // A hidden iframe still loads a new src, so always bust it after a
    // build — otherwise toggling to PDF later would show the old file.
    frame.src = `${BASE}/pdf/${DOC_ID}?t=` + Date.now();
  }

  btnBuild.addEventListener("click", async () => {
    const old = btnBuild.innerHTML;
    btnBuild.disabled = true;
    btnBuild.innerHTML = `<span class="spin"></span> Compiling…`;
    try {
      const t = getTypo();
      const data = await working(`Building the PDF of ${meta.title || DOC_ID}`,
        act => api(act.url(`/api/docs/${DOC_ID}/build`),
                   {method: "POST", json: {scale: t.fa, size: pdfOpts.size,
                                           mono: pdfOpts.mono}}));
      meta.build = data.build;
      buildError = null; buildLog = "";
      renderBuildInfo();
      const vtot = (data.build.verify_ok || 0) + (data.build.verify_failed || 0);
      const vmsg = data.build.verified === false
        ? "not verified (PyMuPDF missing)"
        : `${data.build.verify_ok}/${vtot} ${lang().name} strings verified`;
      const pmsg = data.build.pages != null ? `${data.build.pages} pages, ` : "";
      toast(`PDF built: ${pmsg}${vmsg}`);
      refreshFrame();
    } catch (e) {
      buildError = e.message;             // keep the last good build intact
      buildLog = (e.data && e.data.build && e.data.build.log_tail) || "";
      renderBuildInfo();
      toast("Build failed: " + e.message, true);
    } finally {
      btnBuild.disabled = false;
      btnBuild.innerHTML = old;
    }
  });

  btnPdf.addEventListener("click", () => {
    const showPdf = frame.hidden;
    if (showPdf && !frame.getAttribute("src")) refreshFrame();
    frame.hidden = !showPdf;
    sheet.hidden = showPdf;
    btnPdf.textContent = showPdf ? "View web" : "View PDF";
  });

  $("#btn-duplicate").addEventListener("click", async () => {
    try {
      const data = await api(`/api/docs/${DOC_ID}/duplicate`, {method: "POST"});
      location.href = BASE + "/doc/" + data.meta.id;
    } catch (e) { toast("Duplicate failed: " + e.message, true); }
  });

  $("#btn-delete").addEventListener("click", async e => {
    const menu = e.currentTarget.closest("details");
    if (menu) menu.open = false;
    const gone = await confirmDialog({
      title: `Delete “${meta.title}”?`,
      hint: "Its builds are deleted too. This cannot be undone.",
      ok: "Delete document", danger: true,
      opener: menu ? $("summary", menu) : null,
      run: async () => {
        try {
          await api("/api/docs/" + DOC_ID, {method: "DELETE"});
        } catch (err) {
          if (err.status !== 404) { err.message = "Delete failed: " + err.message; throw err; }
        }                                 // 404: already gone, which is what was asked for
      },
    });
    if (gone) location.href = BASE + "/";
  });

  const btnPrint = $("#btn-print");
  if (btnPrint) btnPrint.addEventListener("click", () => window.print());

  // A .disabled download link is inert to the mouse via pointer-events,
  // but stays in the tab order — block keyboard/programmatic activation
  // too, so Enter on an unbuilt-PDF link can't navigate away.
  ["#dl-pdf", "#dl-tex", "#dl-texzip"].forEach(sel => {
    const a = $(sel);
    if (a) a.addEventListener("click", e => {
      if (a.classList.contains("disabled")) { e.preventDefault(); e.stopPropagation(); }
    });
  });

  const dlHtml = $("#dl-html"), topbar = $("header.topbar");
  if (dlHtml && topbar) {
    const exporter = madeDownload({
      place: el => { el.classList.add("hang"); topbar.appendChild(el); },
      busy: on => {
        dlHtml.classList.toggle("disabled", on);
        dlHtml.setAttribute("aria-disabled", String(on));
      },
      done: (r, name) => toast(`HTML page exported: ${name}`),
    });
    dlHtml.addEventListener("click", e => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      const menu = dlHtml.closest("details");
      if (menu) menu.open = false;
      exporter.start({url: dlHtml.getAttribute("href"),
                      label: `Making the HTML page of “${meta.title || DOC_ID}”`,
                      failed: "The HTML page was not saved",
                      fallback: (DOC_ID.replace(/-[0-9a-f]{6}$/, "") || "document") + ".html"});
    });
  }

  /* tags editor */
  const chips = $("#tag-chips"), input = $("#tag-input");
  function renderTags() {
    chips.innerHTML = "";
    for (const t of meta.tags || []) {
      const sp = document.createElement("span");
      sp.className = "tag";
      const label = document.createElement("span");
      label.textContent = t;
      const x = document.createElement("button");
      x.textContent = "✕"; x.title = "Remove tag";
      x.addEventListener("click", () => patchTags(cur => cur.filter(v => v !== t)));
      sp.append(label, x);
      chips.appendChild(sp);
    }
  }
  // Serialize tag edits through one promise chain, each computing its
  // payload from the CURRENT tags at execution time — so rapid add/remove
  // clicks compose instead of racing to a last-writer-wins loss.
  let tagQueue = Promise.resolve();
  function patchTags(compute) {
    tagQueue = tagQueue.then(async () => {
      const tags = compute(meta.tags || []);
      const data = await api(`/api/docs/${DOC_ID}/meta`,
                             {method: "PATCH", json: {tags}});
      meta = Object.assign(meta, data.meta);
      renderTags();
      refreshTagOptions();
    }).catch(e => toast("Tag update failed: " + e.message, true));
    return tagQueue;
  }
  async function refreshTagOptions() {
    try {
      const data = await api("/api/tags");
      const dl = $("#tag-options");
      dl.innerHTML = "";
      for (const {tag} of data.tags) {
        const o = document.createElement("option");
        o.value = tag; dl.appendChild(o);
      }
    } catch (e) { /* non-fatal */ }
  }
  // The tag goes up as it was typed: the store lower-cases it (and knows
  // that the small İ is a plain i, which toLowerCase here would spell
  // i + a combining dot -- a tag nobody could type again).  So the
  // duplicate check below is exact rather than case-blind; at worst it
  // sends a tag the store then folds into one it already has.
  input.addEventListener("keydown", e => {
    if (e.key !== "Enter" && e.key !== ",") return;
    e.preventDefault();
    const v = input.value.trim().replace(/,+$/, "");
    if (!v) return;
    input.value = "";
    patchTags(cur => cur.includes(v) ? cur : [...cur, v]);
  });
  input.addEventListener("change", () => {   // datalist pick
    const v = input.value.trim();
    if (!v) return;
    input.value = "";
    patchTags(cur => cur.includes(v) ? cur : [...cur, v]);
  });

  /* contents drawer — closed by default so the sheet stays centred */
  const tocPane = $("#tocpane"), tocBtn = $("#btn-toc"),
        tocBackdrop = $("#toc-backdrop");
  function setToc(open) {
    if (open) setLinks(false);
    document.body.classList.toggle("toc-open", open);
    tocBackdrop.hidden = !open;
    tocPane.setAttribute("aria-hidden", String(!open));
    tocBtn.setAttribute("aria-expanded", String(open));
  }
  tocBtn.addEventListener("click", () =>
    setToc(!document.body.classList.contains("toc-open")));
  $("#btn-toc-close").addEventListener("click", () => setToc(false));
  tocBackdrop.addEventListener("click", () => setToc(false));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && document.body.classList.contains("toc-open"))
      setToc(false);
  });

  /* "Linked from": the documents of this library whose text links here,
     listed by the server (store.backlinks), in a drawer of their own from
     the other side.  One drawer at a time; Esc closes it. */
  const linksPane = $("#linkspane"), linksBtn = $("#btn-backlinks"),
        linksBackdrop = $("#links-backdrop");
  function setLinks(open) {
    if (!linksPane) return;
    if (open) setToc(false);
    document.body.classList.toggle("links-open", open);
    linksBackdrop.hidden = !open;
    linksPane.setAttribute("aria-hidden", String(!open));
    linksBtn.setAttribute("aria-expanded", String(open));
    if (open) (($(".link-doc", linksPane)) || $(".toc-close", linksPane)).focus();
  }
  if (linksPane) {
    linksBtn.addEventListener("click", () =>
      setLinks(!document.body.classList.contains("links-open")));
    $("#btn-links-close").addEventListener("click", () => { setLinks(false); linksBtn.focus(); });
    linksBackdrop.addEventListener("click", () => setLinks(false));
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && document.body.classList.contains("links-open")) {
        setLinks(false);
        linksBtn.focus();
      }
    });
  }

  /* smooth TOC scroll; jumping closes the drawer, giving the text back */
  $$(".toc-list a").forEach(a => a.addEventListener("click", e => {
    const target = $(a.getAttribute("href"));
    if (!target) return;
    e.preventDefault();
    setToc(false);
    measureSticky(target);    // the toolbar may have rewrapped since load
    target.scrollIntoView({behavior: "smooth", block: "start"});
    history.replaceState(null, "", a.getAttribute("href"));
  }));

  renderTags();
  refreshTagOptions();
  renderBuildInfo();
}

/* ---------------- prompt page ---------------- */

function initPrompt() {
  const ta = $("#prompt-text");
  const badge = $("#prompt-badge");
  const question = $("#question");
  const sel = $("#prompt-target");
  let current = {text: "", custom: false, target: "fa", target_name: "Persian",
                 lang_block: ""};
  bindStopServer();

  /* The target-language select: the prompt text is generic and says to
     set `target:`; the language's own conventions (docs/lang/<code>.md,
     served with the prompt) are shown under it and copied with it, and
     the copied text opens with the target stated.  Starts on the
     toolbox's shared preference when that is a language. */
  const pick = sharedLang();
  for (const l of LANGS) {
    const o = document.createElement("option");
    o.value = l.code;
    o.textContent = `${l.name} (${l.code})`;
    sel.appendChild(o);
  }
  sel.value = LANGS.some(l => l.code === pick) ? pick : (LANGS[0] || {}).code || "fa";

  function guidance() {
    return `target: ${current.target} — this document is about ${current.target_name}: `
      + `write \`target: ${current.target}\` in the front matter.\n\n`;
  }
  function show(p) {
    current = p;
    // WHAT THE BOX SHOWS is the prompt the server assembled (the version line, the target
    // line, the instructions, the language's conventions, the answer contract), so that what
    // it shows is what is copied; a server that does not send one is composed the old way
    ta.value = p.prompt ? p.prompt.replace(/\n*$/, "\n")
      : guidance() + p.text.trim() + (p.lang_block ? "\n\n" + p.lang_block.trim() : "") + "\n";
    // THE BADGE NAMES THE PROMPT: Parseh's own, or the one of the person's the menu in the row chose
    badge.textContent = (p.custom ? `your prompt: ${p.custom.name || "custom"}` : "default (exlex/PROMPT.md)")
      + ` · ${p.target_name}`;
    badge.className = "badge " + (p.custom ? "warn" : "");
    teach.draw(p);
    choices.draw(p);
    teach.total(p.prompt || "", p.always_chars);
    sync();
  }

  /* WHAT THE MODEL IS TAUGHT TO WRITE, and for whom (static/promptpick.js): the boxes, the
     presets, the level and the length are drawn from the server's answer, and the choice is
     asked of the server again a moment after the last change -- only the newest answer is
     shown, a slow one that comes late is dropped.  The ticked boxes, the level and the length
     are remembered on this device, one set for every language; the scheme of the
     transliteration is the row's own control, remembered per language. */
  const teach = ParsehPromptPick.boxes($("#prompt-boxes"), {presets: true, total: true, remember: "boxes", onChange: ask});
  const choices = ParsehPromptPick.line($("#prompt-under"), {
    surface: "studio-doc", lang: sel.value, remember: "",
    ids: {level: "prompt-level", length: "prompt-length"}, onChange: ask});
  let timer = 0, seq = 0, making = false;
  function query(plain) {
    const q = ["target=" + encodeURIComponent(sel.value)];
    // a `boxes=` with nothing after it is "none ticked" -- the key stays when the list is empty
    if (!plain && teach.boxes()) q.push("boxes=" + encodeURIComponent(teach.boxes().join(",")));
    if (!plain) for (const [k, v] of Object.entries(choices.params()))
      q.push(k + "=" + encodeURIComponent(v));
    // THE PROMPT THE MENU IN THE ROW CHOSE (a person's own; Parseh's own is none): kept in the plain ask too, so
    // that what is shown is always the prompt the menu says
    if (row && row.promptId()) q.push("prompt=" + encodeURIComponent(row.promptId()));
    return "/api/prompt?" + q.join("&");
  }
  // WHAT IS HELD WAS MADE FOR THE CHOICES BEFORE THIS ONE: not to be copied meanwhile
  function outdated() {
    making = true;
    if (row) row.disable("the prompt is being made again for what you changed");
  }
  function ask() {
    clearTimeout(timer);
    // an answer on its way was made for what was asked before this: it is not shown, and not said if it is refused
    seq++;
    outdated();
    timer = setTimeout(() => load(), 150);
  }
  async function load(plain = false, again = 0) {
    clearTimeout(timer);
    const mine = ++seq;
    let p;
    try {
      p = await api(query(plain));
    } catch (e) {
      if (mine !== seq) return;
      // WHAT THIS DEVICE REMEMBERED can be something a newer Parseh refuses (a box it no longer
      // has): the plain ask gets the default, the draw puts back the ids the server does know
      // and the ask below is made once more with them
      if (e.status === 400 && !plain) { teach.stale(); return load(true, again); }
      // THE PROMPT CHOSEN MAY BE ONE ANOTHER DEVICE DELETED SINCE (the route says it is gone): the row finds out,
      // says so in its own words, chooses Parseh's own and asks again -- and then nothing more need be said here
      if (row && row.promptId() && e.status === 404) {
        const was = row.promptId();
        await row.verifyPrompt();
        if (row.promptId() !== was) return;
      }
      toast(e.message, true);
      if (row) row.disable("the prompt could not be made again: change a box to try once more");
      return;
    }
    if (mine !== seq) return;
    // WHAT THE ANSWER CORRECTED (a remembered set the server only partly knew, a plain ask made for the
    // default, a box it turned off) is asked for once more -- and what is shown meanwhile is not the
    // prompt for the choices yet, so it is not to be copied
    const more = (plain || !teach.agrees(p)) && again < 2;
    if (more) outdated(); else making = false;
    show(p);
    if (more) load(false, again + 1);
  }
  sel.addEventListener("change", async () => {
    clearTimeout(timer);
    outdated();
    await choices.setLang(sel.value);     // the scheme of the transliteration is chosen per language
    // the menu lists the prompts of this language; a choice that is not for it is Parseh's own again, and the
    // prompt is asked for once more by the row's own say-so (onPrompt)
    if (row) await row.setLang(sel.value);
    load();
  });

  /* WHAT IS COPIED: the prompt as the box shows it -- while it is being edited
     the box holds the editable text alone, and the target line and the
     language's conventions go round it -- and, after a blank line, the
     question when one is written.  The row (lib/llmrow.js) holds this text,
     says how long it is before anything is copied, and copies exactly it. */
  function copyText() {
    const q = question.value.trim();
    const prompt = ta.value;
    return q ? prompt.replace(/\n*$/, "\n") + "\n" + q + "\n" : prompt;
  }
  // THE PROMPT MENU is the row's: it lists the prompts of the person's own for this language, and what it chooses
  // is asked of the server as `prompt=<id>` (query).  The options are the choices' own, drawn under the question
  const row = window.ParsehLLMRow ? ParsehLLMRow.mount($("#llm-row"), {
    surface: "studio-doc", cls: "btn primary big", ids: {copy: "btn-copy-all"},
    title: "Put the prompt on the clipboard, with your question after it when you have written one",
    remind: "paste it into your chatbot, then bring its answer back with Upload .md or Paste LLM answer.",
    box: () => ta,
    lang: sel.value, options: false, promptsUrl: BASE + "/api/prompts/",
    onPrompt: () => ask(),
  }) : null;
  if (!row) $("#llm-row").textContent = "The prompt helper could not be loaded.";
  // a prompt not loaded yet has nothing to copy; and a button says what it copies:
  // "and your question" once one is written
  const sync = () => {
    if (!row || !current.text) return;
    row.update(copyText());
    // the short request for a chat that has the skill: its header (the server's) and, after a blank line, the question
    const k = current.skill;
    if (row.skillOf) {
      const q = question.value.trim();
      row.skillOf(k && k.available ? Object.assign({}, k, {text: k.text.replace(/\n*$/, "\n\n") + (q ? q + "\n" : "")}) : k);
    }
    // the button stays off while the prompt is being made again for a choice just changed (ask)
    if (!making) row.enable();
    row.label(question.value.trim() ? "copy the prompt and your question" : "copy the prompt");
  };
  question.addEventListener("input", sync);

  // the first prompt is asked for once the options are known, so that it is made the way it will be asked for
  // and the choice of prompt is known, where this device remembers one
  Promise.all([choices.ready(), row ? row.promptReady() : null]).then(() => load());
}

/* ---------------- the .tex that was compiled, and the whole log (a0.5.4) ----------------
   A drawing that could not be made says why in words beside its block; these two buttons of its frame
   (htmlgen._latex_frame) show what those words were made from -- the exact document TeX was given and the whole
   log it wrote, as lib/latexdraw.py kept them with the compile -- in a frame on top of the page, with a Copy of its
   own.  In the log the lines the words were read from are marked, and it opens scrolled to the first. */
function openLatexView(btn) {
  const kind = btn.dataset.latexView === "log" ? "log" : "tex", url = btn.dataset.latexUrl;
  const marks = new Set((btn.dataset.latexMarks || "").split(",").filter(Boolean).map(Number));
  const ov = document.createElement("div");
  ov.className = "modal-overlay latex-view-overlay";
  ov.innerHTML = `<div class="modal latex-view-modal" role="dialog" aria-modal="true" tabindex="-1">
      <h3></h3><p class="latex-view-note"></p>
      <pre class="latex-view-pre" dir="ltr" tabindex="0"></pre>
      <div class="row">
        <button type="button" class="btn" data-x="copy" disabled></button>
        <button type="button" class="btn primary" data-x="close">Close</button></div></div>`;
  const modal = $(".modal", ov), pre = $(".latex-view-pre", ov), copyBtn = $('[data-x="copy"]', ov);
  const title = kind === "tex" ? "The .tex that was compiled" : "The whole log";
  $("h3", ov).textContent = title;
  modal.setAttribute("aria-label", title);
  $(".latex-view-note", ov).textContent = kind === "tex"
    ? "Exactly the document LaTeX was given for this drawing: its theme's preamble, then the block."
    : "Everything LaTeX wrote while it compiled this drawing" + (marks.size ? ", with the lines the words above were made from marked." : ".");
  const copyWas = kind === "tex" ? "Copy the .tex" : "Copy the log";
  copyBtn.textContent = copyWas;
  let text = "";
  const close = () => { document.removeEventListener("keydown", onKey, true); ov.remove(); btn.focus && btn.focus(); };
  const onKey = e => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } };
  document.addEventListener("keydown", onKey, true);
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  $('[data-x="close"]', ov).addEventListener("click", close);
  copyBtn.addEventListener("click", async () => {
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; }
    catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
      document.body.appendChild(ta); ta.select();
      try { ok = document.execCommand("copy"); } catch (x) { ok = false; }
      ta.remove();
    }
    copyBtn.textContent = ok ? "Copied" : "Could not copy: select it and copy by hand";
    setTimeout(() => { copyBtn.textContent = copyWas; }, 1800);
  });
  document.body.appendChild(ov);
  pre.textContent = "Reading…";
  fetch(url, {cache: "no-store"}).then(r => r.ok ? r.text() : Promise.reject(new Error(String(r.status)))).then(t => {
    text = t;
    pre.textContent = "";
    const lines = t.split("\n");
    // the last empty piece of a file that ends with a newline is not a line
    if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
    lines.forEach((l, i) => {
      const row = document.createElement("span");
      row.className = "latex-view-ln" + (kind === "log" && marks.has(i + 1) ? " mark" : "");
      row.textContent = l;
      pre.appendChild(row);
    });
    copyBtn.disabled = false;
    const first = pre.querySelector(".mark");
    if (first) pre.scrollTop = Math.max(0, first.offsetTop - Math.round(pre.clientHeight / 3));
    pre.focus({preventScroll: true});
  }).catch(() => {
    pre.textContent = "This was not kept: the drawing was made by an older Parseh, or what is kept was cleared. " +
      "Change the block a little, or draw the sample again, and it is made afresh with its .tex and its log.";
  });
}
document.addEventListener("click", e => {
  const b = e.target.closest && e.target.closest("[data-latex-view]");
  if (!b) return;
  e.preventDefault();
  openLatexView(b);
});

/* ---------------- boot ---------------- */

// every page of the studio takes the toolbox's theme and follows it, the
// library and the prompt page too, which have no sheet to dress
bindStudioLook();

// every page of the studio, whichever it is: the bar behaves on a phone
bindBarHide();
if (PAGE === "index") { bindStopServer(); initIndex(); }
else if (PAGE === "doc") initDoc();
// the edit page's own script boots it: the editor is static/editor.js,
// which that page alone loads (TO-DO §4.8)
else if (PAGE === "prompt") initPrompt();
