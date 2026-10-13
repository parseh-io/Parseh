// SPDX-License-Identifier: GPL-3.0-or-later
/* THE PREVIEW IN ITS OWN TAB, AND THE DOUBLE-CLICK THAT LANDS YOU ON THE TEXT (a0.5.1).

   Two things the editor lacked that a LaTeX editor on the web (Overleaf) has:

   1. DOUBLE-CLICK THE PREVIEW, and the editor goes to the text that drew what you clicked: the
      word itself where it can be found, else the start of its block.  The renderer tags every top-level
      block with the line it starts on (data-src-line, htmlgen.py); the click names its block and the
      word and which of that word's occurrences in the block it is, and the editor looks in the lines
      of that block.  Nothing here looks at a rendered word's markup, which is why it holds for every
      kind of block: a paragraph, a list, a table, an exercise, a box (which is one block, found
      by its first line, then by the word).

   2. THE PREVIEW IN ANOTHER TAB, OPTIONALLY.  The half page beside the text is narrow, and it is not the page:
      its hover tools are on and its exercises are the ones being written.  With the preview in its
      own tab the editor has the whole window, and the other tab is THE READING PAGE of the document
      (`/doc/<id>?live=1`, templates/doc.html) drawn from the editor's text as it is typed, unsaved
      changes and all, at the width and in the typography the document is read in.  A double-click
      there lands the editor on the text too.

   The two tabs talk through a BroadcastChannel of the document (no server in between, nothing
   written anywhere), in these messages -- each carrying `from`, "editor" or "preview", because the
   channel is shared by the editor and every preview tab of the document and hears them all:

     editor -> preview   text   {seq, markdown, line}   the buffer, and the line the cursor is on
                         caret  {line}                  the cursor moved
                         alive  {}                      the editor is there (every few seconds)
                         bye    {}                      the editor is closing
     preview -> editor   hello  {}                      I am open: send the buffer
                         alive  {}                      I am still open
                         jump   {line, endLine, word, nth}   the double-click
                         bye    {}

   This file is the pieces both sides share (StudioLive) and the preview's side; the editor's is in
   editor.js, which has the textarea.  A browser cannot bring another of its tabs to the front, so the
   editor says so on its own page when a jump has landed, and the preview tries to switch to it by its window
   name where the editor opened it; where it cannot, the sentence is all there is. */
(function () {
  "use strict";
  const body = document.body;
  const BASE = body.dataset.base || "", DOC = body.dataset.docId || "";
  const CHANNEL = "parseh-studio-live:" + BASE + ":" + DOC;
  const EDITOR_WINDOW = "parseh-studio-editor:" + BASE + ":" + DOC;
  const PREVIEW_WINDOW = "parseh-studio-preview:" + BASE + ":" + DOC;
  const WORD_MAX = 80;

  /* ---------------------------------------------------------------- what both sides share */

  // how many times `needle` is in `hay`
  function count(hay, needle) {
    let n = 0, i = -1;
    if (!needle) return 0;
    while ((i = hay.indexOf(needle, i + 1)) >= 0) n++;
    return n;
  }

  /* WHAT A DOUBLE-CLICK ASKS FOR: the block that was clicked (the first tagged element up the tree, and the
     line the next tagged one starts on, which is where this one stops), the word the browser selected, and
     how many times that word came before it inside the block. */
  function jumpRequest(sheet, event) {
    const origin = event.target && event.target.nodeType === 1 ? event.target : (event.target || {}).parentElement;
    const req = {};
    const sel = window.getSelection ? window.getSelection() : null;
    const word = sel && !sel.isCollapsed ? sel.toString().trim() : "";
    if (word && word.length <= WORD_MAX && !/\n/.test(word)) req.word = word;
    const block = origin && origin.closest ? origin.closest("[data-src-line]") : null;
    if (block && sheet.contains(block)) {
      req.line = +block.dataset.srcLine;
      const tagged = Array.from(sheet.querySelectorAll("[data-src-line]"));
      const next = tagged.slice(tagged.indexOf(block) + 1).find(el => +el.dataset.srcLine > req.line);
      if (next) req.endLine = +next.dataset.srcLine - 1;
      if (req.word && sel.rangeCount) {
        try {
          const r = document.createRange();
          r.setStart(block, 0);
          r.setEnd(sel.getRangeAt(0).startContainer, sel.getRangeAt(0).startOffset);
          req.nth = count(r.toString(), req.word);
        } catch (e) { /* a selection that straddles blocks: the first occurrence will do */ }
      }
    }
    return req;
  }

  /* WHERE THE TEXT IS: `req` against the editor's own buffer -> {start, end, line, exact} or null.
     Inside the lines of the block, the `nth` occurrence of the word (the last one there is, when the
     page counted more than the source holds: a rendered number, an annotation); failing that the
     block's first line.  A click on nothing tagged (the title, the contents) looks for the word in the whole
     text and, if it is not there, finds nothing: the page's own furniture is not in the source. */
  function locate(text, req) {
    const lines = text.split("\n"), last = lines.length - 1;
    const clamp = n => Math.max(0, Math.min(last, n | 0));
    const starts = [];
    let at = 0;
    for (const l of lines) { starts.push(at); at += l.length + 1; }
    const tagged = typeof req.line === "number";
    const a = tagged ? clamp(req.line) : 0;
    const b = tagged && typeof req.endLine === "number" ? Math.max(a, clamp(req.endLine)) : last;
    const from = starts[a], to = starts[b] + lines[b].length;
    const region = text.slice(from, to);
    const lineOf = offset => {
      let lo = 0, hi = last;
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (starts[mid] <= offset) lo = mid; else hi = mid - 1; }
      return lo;
    };
    if (req.word) {
      let found = -1, n = -1, i = -1, lastAt = -1;
      while ((i = region.indexOf(req.word, i + 1)) >= 0) {
        n++; lastAt = i;
        if (n === (req.nth || 0)) { found = i; break; }
      }
      if (found < 0) found = lastAt;
      if (found >= 0) {
        const start = from + found;
        return {start, end: start + req.word.length, line: lineOf(start), exact: true};
      }
    }
    if (!tagged) return null;
    return {start: starts[a], end: starts[a] + lines[a].length, line: a, exact: false};
  }

  window.StudioLive = {CHANNEL, EDITOR_WINDOW, PREVIEW_WINDOW, jumpRequest, locate,
                       supported: typeof BroadcastChannel === "function"};

  /* ------------------------------------------------------------- the preview tab's side */
  if (body.dataset.live !== "1" || body.dataset.page !== "doc") return;
  if (!window.StudioLive.supported) {
    const bar = document.getElementById("livebar");
    if (bar) { bar.hidden = false; bar.textContent = "This browser cannot link two tabs, so the preview cannot follow the editor."; }
    return;
  }

  const sheet = document.getElementById("sheet");
  const bar = document.getElementById("livebar");
  const say = document.getElementById("live-say");
  const follow = document.getElementById("live-follow");
  const toEditor = document.getElementById("live-editor");
  const channel = new BroadcastChannel(CHANNEL);
  // every message says who sent it: the editor and any number of preview tabs share the one channel, and a
  // preview's "alive" or "bye" is not the editor's
  const post = m => channel.postMessage(Object.assign({from: "preview"}, m));
  body.classList.add("is-live");
  bar.hidden = false;
  document.title = "Preview · " + document.title;
  let latest = -1, working = false, waiting = null, heard = 0, shown = false, closed = false;
  const FOLLOW_KEY = "parseh_live_follow";
  try { if (localStorage.getItem(FOLLOW_KEY) === "0") follow.checked = false; } catch (e) { /* private mode */ }
  follow.addEventListener("change", () => {
    try { localStorage.setItem(FOLLOW_KEY, follow.checked ? "1" : "0"); } catch (e) { /* private mode */ }
  });

  const clock = () => new Date().toTimeString().slice(0, 8);
  function present() {
    // is the editor there: it says so every few seconds
    return !closed && Date.now() - heard < 10000;
  }
  function sayNow() {
    if (present()) say.textContent = shown
      ? "From the editor tab, unsaved changes included · drawn " + clock()
      : "The editor tab is open: waiting for its text…";
    else if (closed) say.textContent = "The editor tab was closed. This is its text as it was left: what was not saved is not in the document.";
    else if (shown) say.textContent = "No editor tab answers. This is the text as it was left.";
    else say.textContent = "No editor tab is open for this document: this is the saved text. Open the editor with the button, and this page follows it.";
    toEditor.textContent = present() ? "Editor ↗" : "Open the editor ↗";
  }

  /* THE BLOCK AT THE TOP OF THE WINDOW, and how far down it is: kept where it was when the page is drawn
     again.  It is found again by what it SAYS, not by its line: a paragraph typed above it moves every line
     number after it, and the line's number would then be another block.  (Two blocks that say the same
     thing: the nearer line.  A block being typed in has changed its words: the line is the way back.) */
  function scroller() { return document.scrollingElement || document.documentElement; }
  const keyOf = el => el.tagName + "|" + el.textContent.trim().slice(0, 80);
  function topAnchor() {
    for (const el of sheet.querySelectorAll("[data-src-line]")) {
      const r = el.getBoundingClientRect();
      if (r.bottom > 0) return {line: +el.dataset.srcLine, top: r.top, key: keyOf(el)};
    }
    return null;
  }
  function restore(anchor) {
    if (!anchor) return;
    const blocks = Array.from(sheet.querySelectorAll("[data-src-line]"));
    const near = (a, b) => Math.abs(+a.dataset.srcLine - anchor.line) - Math.abs(+b.dataset.srcLine - anchor.line);
    const same = blocks.filter(e => keyOf(e) === anchor.key).sort(near)[0];
    const el = same || blocks.find(e => +e.dataset.srcLine >= anchor.line);
    if (el) scroller().scrollTop += el.getBoundingClientRect().top - anchor.top;
  }
  // the block the editor's cursor is in, brought into view when it is not
  function followLine(line) {
    if (!follow.checked || typeof line !== "number") return;
    let target = null;
    for (const el of sheet.querySelectorAll("[data-src-line]")) {
      if (+el.dataset.srcLine <= line) target = el; else break;
    }
    if (!target) return;
    const r = target.getBoundingClientRect(), h = window.innerHeight;
    if (r.top < 90 || r.top > h - 120) scroller().scrollTop += r.top - h * 0.3;
  }

  /* DRAWING THE PAGE AGAIN, from the editor's text.  The server draws it as the reading page draws a saved
     document (/api/preview with `page`); what the page's script bound to the old article is bound to the new one. */
  async function render(m) {
    working = true;
    try {
      const data = await api("/api/preview", {method: "POST", json: {markdown: m.markdown, doc_id: DOC_ID, page: true}});
      if (!data.ok) throw new Error(data.error);
      const anchor = topAnchor();
      const doc = data.doc;
      sheet.innerHTML = doc.html;
      freshMedia(sheet, DOC_ID);
      sheet.lang = doc.lang || "en";
      if (doc.lang_record && doc.target !== lang().code) {
        LANG = doc.lang_record;
        sheet.dataset.lang = doc.target;
        body.dataset.lang = doc.target;
        if (typeof studioTypo !== "undefined") studioTypo.refresh();
      }
      const toc = document.querySelector("#tocpane .toc-list");
      if (toc) {
        const fresh = document.createElement("div");
        fresh.innerHTML = doc.toc;
        const next = fresh.querySelector(".toc-list");
        if (next) {
          toc.replaceWith(next);
          next.querySelectorAll("a").forEach(a => a.addEventListener("click", e => {
            const target = document.querySelector(a.getAttribute("href"));
            if (!target) return;
            e.preventDefault();
            const close = document.getElementById("btn-toc-close");
            if (close) close.click();
            target.scrollIntoView({block: "start"});
          }));
        }
      }
      const glosses = document.getElementById("doc-glosses");
      const button = document.getElementById("btn-glosses");
      if (glosses && button) {
        glosses.textContent = JSON.stringify(doc.glosses || []);
        const fresh = button.cloneNode(true);       // a clone has none of the old click handlers
        button.replaceWith(fresh);
        bindGlosses();
      }
      armClipReplay(sheet);
      bindExercises(sheet);
      shown = true;
      restore(anchor);
      followLine(m.line);
      sayNow();
    } catch (e) {
      say.textContent = "Could not draw the editor's text: " + e.message;
    } finally {
      working = false;
      if (waiting) { const next = waiting; waiting = null; render(next); }
    }
  }

  channel.onmessage = event => {
    const m = event.data || {};
    if (m.from !== "editor") return;
    if (m.t === "text") {
      heard = Date.now();
      if (m.seq <= latest) return;
      latest = m.seq;
      if (working) waiting = m; else render(m);
    } else if (m.t === "caret") {
      heard = Date.now();
      followLine(m.line);
    } else if (m.t === "alive") {
      heard = Date.now();
      sayNow();
    } else if (m.t === "bye") {
      closed = true;
      sayNow();
    } else if (m.t === "hello-editor") {
      // an editor that has just opened says so: ask it for its text
      closed = false;
      heard = Date.now();
      post({t: "hello"});
    }
  };
  post({t: "hello"});
  setInterval(() => { post({t: "alive"}); sayNow(); }, 3000);
  // nobody answered: the page says it is the saved text
  setTimeout(sayNow, 1500);
  window.addEventListener("pagehide", () => post({t: "bye"}));

  /* THE DOUBLE-CLICK */
  function toast2(text) { if (typeof toast === "function") toast(text); }
  sheet.addEventListener("dblclick", event => {
    if (event.target.closest && event.target.closest("button, input, select, textarea, a, audio, video, summary, [contenteditable]")) return;
    const req = jumpRequest(sheet, event);
    if (typeof req.line !== "number" && !req.word) return;
    if (!present()) { toast2("No editor tab is open for this document: open it with the button above."); return; }
    post(Object.assign({t: "jump"}, req));
    toast2("Showing it in the editor tab" + (switchToEditor() ? "" : " — switch to it to see where"));
  });

  // the editor's tab, where this one was opened by it and the browser lets it be brought forward
  function switchToEditor() {
    try {
      const opener = window.opener;
      if (opener && !opener.closed && opener.name === EDITOR_WINDOW) {
        window.open("", EDITOR_WINDOW);
        opener.focus();
        return true;
      }
    } catch (e) { /* another origin or a browser that will not */ }
    return false;
  }
  toEditor.addEventListener("click", () => {
    if (present()) { if (!switchToEditor()) toast2("The editor is in another tab of this browser: switch to it."); return; }
    window.open(BASE + "/doc/" + DOC + "/edit", EDITOR_WINDOW);
  });
})();
