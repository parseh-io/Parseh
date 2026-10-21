// SPDX-License-Identifier: GPL-3.0-or-later
/* THE PICTOGRAM PICKER (a0.5.3): a frame over the page in which a person looks for an ARASAAC pictogram
   by a word, sees the thumbnails, looks at one properly, and -- where the page that opened the frame can
   use it -- adds it.

   THREE PAGES OPEN IT and it is one frame for all of them: the Settings door that lists the pictograms
   (to look, nothing to add), the studio's editor (a figure at the cursor) and the exercise form (the
   picture of a card, or a small one inside a line of text).  What differs is handed in:

       ParsehPictograms.open({
         search:  "/studio/api/arasaac/search",          POST, the words in a JSON body (lib/arasaacsearch.py)
         picture: id => "/studio/arasaac/" + id + ".png",  where a picture is, the version put after it
         lang:    "es",                                   the language the words are shown in, if it is here
         title:   "Pictograms",
         note:    "A copy goes into this document.",       a line under the title
         door:    "/settings/arasaac/",                    where they are got, said when none are here
         onPick:  async pick => {...},                     only to ADD: without it the frame only shows; a string
                                                           it returns is said in the frame's line ("the credit was added")
         addLabel, keepLabel,                              the words on the two buttons
         onClose, root })                                  -> {close()}

   `pick` is {id, word, lang, meaning, words, flags, url, name, credit, alt, file()}: file() fetches
   the picture's bytes as a File named arasaac-<id>.png, which the page puts where it keeps its own
   pictures (the document's images/, a deck's).  Nothing is written by this file: the server has no route
   that takes a pictogram into a document, only the ones that take any picture, and the credit and the
   copy are the page's business.

   LIKE THE OTHER DIALOGS: appended to the page (over the exercise form when it was opened from there),
   role=dialog and aria-modal, Escape and a click outside close it, focus goes to the search box and back
   to what had it, Tab stays inside.  Arrow keys walk the thumbnails.  The words are looked for as they
   are typed (one answer at a time: a slow one never lands over a newer one), in every language that
   is here or in the one chosen; the pictograms ARASAAC marks as about violence or sex are left out, and
   the frame says how many were, and lets them in with one tick. */
(function () {
  "use strict";
  if (window.ParsehPictograms) return;

  /* ITS SHEET IS LINKED FROM BESIDE THE SCRIPT, as lib/pagesettings.js links its own: by the address this script was loaded
     by (currentScript is nothing a moment later, so it is read now).  A page carries ONE tag, and that one is `async`:
     a page kept on a phone and opened away from the computer waits for nothing that only a search needs, and a sheet
     asked for at once is not one a later script of the page waits behind. */
  (function sheet() {
    if (document.querySelector("link[data-pictograms]")) return;
    const own = (document.currentScript && document.currentScript.src) || "";
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.dataset.pictograms = "";
    link.href = own ? own.replace(/pictograms\.js(?=[?#]|$)/, "pictograms.css") : "/lib/pictograms.css";
    (document.head || document.documentElement).append(link);
  })();

  const PAGE = 48;
  const WAIT = 220;                        // ms after the last key before a search is asked for
  const KEEP = "parseh.pictograms.language";
  const FLAGS = {schematic: "simplified drawing", aac: "used on communication boards (AAC)",
                 violence: "about violence", sex: "about sex"};
  const NASTY = {violence: 1, sex: 1};
  let serial = 0;
  let CREDIT = "";                         // ARASAAC's credit, as the last answer of the server worded it
  const PICKED = new Set();                // the numbers of the pictograms added through a frame of this page's life

  const make = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  const remembered = () => { try { return localStorage.getItem(KEEP) || ""; } catch (e) { return ""; } };
  const remember = v => { try { localStorage.setItem(KEEP, v); } catch (e) { /* not kept: asked again */ } };
  const plural = (n, one, many) => n === 1 ? one : many;

  /* A word as the dialect's alt text: no bracket, brace or bar to break the line it goes in. */
  function alt(word) {
    return String(word || "").replace(/[\[\]{}\\|<>]/g, " ").replace(/\s+/g, " ").trim();
  }

  const TEMPLATE = `
    <div class="pg-modal" role="dialog" aria-modal="true" tabindex="-1">
      <div class="pg-head"><h3></h3><button type="button" class="pg-x" aria-label="Close" title="Close">×</button></div>
      <p class="pg-note" hidden></p>
      <form class="pg-search" role="search" autocomplete="off">
        <input class="pg-q" type="search" enterkeyhint="search" autocomplete="off" autocapitalize="off" spellcheck="false" dir="auto"
               placeholder="Search for a word…" aria-label="Search the pictograms for a word">
        <select class="pg-lang" aria-label="The language to search in" hidden></select>
        <label class="pg-sens" title="ARASAAC marks some pictograms as about violence or sex; they are left out unless this is ticked"><input type="checkbox"> Include violence and sex</label>
      </form>
      <div class="pg-body">
        <div class="pg-results" aria-busy="false">
          <p class="pg-count" role="status" aria-live="polite"></p>
          <p class="pg-hidden-note" hidden></p>
          <div class="pg-grid" role="listbox" aria-label="Pictograms" hidden></div>
          <div class="pg-more-row" hidden><button type="button" class="pg-btn pg-more">Show more</button></div>
          <div class="pg-empty" hidden></div>
        </div>
        <aside class="pg-preview" aria-label="The chosen pictogram">
          <button type="button" class="pg-btn pg-back">← Back to the list</button>
          <div class="pg-big"></div>
          <div class="pg-info">
            <h4 class="pg-word"></h4>
            <p class="pg-meaning" hidden></p>
            <ul class="pg-tags" hidden></ul>
            <dl class="pg-words"></dl>
            <p class="pg-number"></p>
          </div>
          <div class="pg-actions"></div>
        </aside>
      </div>
      <div class="pg-foot">
        <p class="pg-credit"></p>
        <p class="pg-say" role="status" aria-live="polite"></p>
      </div>
    </div>`;

  function open(opts) {
    opts = opts || {};
    const root = opts.root || document.body;
    for (const old of root.querySelectorAll(":scope > .pg-overlay")) {
      if (old._pgClose) old._pgClose(); else old.remove();
    }
    const adding = typeof opts.onPick === "function";
    const before = document.activeElement;
    const ov = make("div", "pg-overlay");
    ov.innerHTML = TEMPLATE;
    const at = sel => ov.querySelector(sel);
    const modal = at(".pg-modal");
    const title = at("h3");
    title.id = "pg-title-" + (++serial);
    title.textContent = opts.title || "Pictograms (ARASAAC)";
    modal.setAttribute("aria-labelledby", title.id);
    const note = at(".pg-note"), form = at(".pg-search"), q = at(".pg-q"), langSel = at(".pg-lang"),
          sens = at(".pg-sens input"), results = at(".pg-results"), count = at(".pg-count"),
          hiddenNote = at(".pg-hidden-note"), grid = at(".pg-grid"), moreRow = at(".pg-more-row"),
          more = at(".pg-more"), empty = at(".pg-empty"), preview = at(".pg-preview"), big = at(".pg-big"),
          word = at(".pg-word"), meaning = at(".pg-meaning"), tags = at(".pg-tags"), words = at(".pg-words"),
          number = at(".pg-number"), actions = at(".pg-actions"), credit = at(".pg-credit"), say = at(".pg-say");
    if (opts.note) { note.textContent = opts.note; note.hidden = false; }

    const S = {q: "", lang: "", sensitive: false, items: [], total: 0, more: false, hidden: 0, locales: [],
               ready: null, selected: null, busy: false, seq: 0, abort: null, closed: false, timer: 0, credit: ""};
    const names = {};
    const link = item => `${opts.picture(item.id)}?v=${encodeURIComponent(item.v || "0")}`;

    /* ---- the message line at the bottom: what was done, or what went wrong ---- */
    function tell(text, kind) {
      say.textContent = text || "";
      say.className = "pg-say" + (kind ? " pg-" + kind : "");
    }

    /* ---- what the frame says instead of thumbnails ---- */
    function showEmpty(parts) {
      empty.replaceChildren(...parts);
      empty.hidden = false;
      grid.hidden = true; moreRow.hidden = true; hiddenNote.hidden = true;
      count.textContent = "";
      preview.hidden = true;                  // nothing to look at: the pane would only repeat that
    }
    function para(text, cls) { return make("p", cls || "", text); }
    function again(label) {
      const b = make("button", "pg-btn", label || "Look again");
      b.type = "button";
      b.addEventListener("click", () => load(true));
      return b;
    }
    function notReady(data) {
      const out = [];
      if (data.fetching) {
        out.push(para("The pictograms are being fetched right now, and there is nothing to look through yet."));
        out.push(again("Look again"));
      } else if (data.state === "partial") {
        out.push(para("The pictograms were not all fetched, and nothing can be looked through yet. Carry on the download from Settings → Pictograms (ARASAAC)."));
        out.push(again("Look again"));
      } else {
        const b = make("p");
        b.append(make("b", "", "The pictograms are not on this computer yet. "),
                 "They are ARASAAC's, free for non-commercial use, and fetched once from Settings → Pictograms (ARASAAC); after that this works with no connection.");
        out.push(b);
        if (opts.door) {
          const a = make("a", "pg-btn pg-primary", "Open Settings → Pictograms");
          a.href = opts.door;
          out.push(a);
        } else {
          out.push(para("Open Parseh's Settings → Pictograms (ARASAAC) to get them, then look again."));
          out.push(again("Look again"));
        }
      }
      showEmpty(out);
    }
    function failed(message) {
      const p = para(message, "pg-error");
      p.setAttribute("role", "alert");
      showEmpty([p, again("Try again")]);
    }

    /* ---- the language to look in: only drawn when there is a choice ---- */
    function drawLanguages(rows) {
      S.locales = rows || [];
      for (const r of S.locales) names[r.code] = r.name;
      if (S.locales.length < 2) { langSel.hidden = true; if (S.lang) S.lang = ""; return; }
      langSel.replaceChildren(new Option("All languages here", ""));
      for (const r of S.locales) langSel.append(new Option(r.name + (r.native && r.native !== r.name ? " · " + r.native : ""), r.code));
      if (S.lang && !S.locales.some(r => r.code === S.lang)) S.lang = "";
      langSel.value = S.lang;
      langSel.hidden = false;
    }

    /* ---- the thumbnails ---- */
    function cell(item) {
      const b = make("button", "pg-cell");
      b.type = "button";
      b.dataset.id = item.id;
      b.setAttribute("role", "option");
      b.setAttribute("aria-selected", "false");
      b.tabIndex = -1;
      const tile = make("span", "pg-tile");
      const img = document.createElement("img");
      img.alt = "";
      img.loading = "lazy";
      img.decoding = "async";
      img.draggable = false;
      img.addEventListener("error", () => b.classList.add("pg-missing"));
      img.src = link(item);
      tile.append(img);
      const cap = make("span", "pg-cap", item.word || "#" + item.id);
      cap.dir = "auto";
      if (item.lang) cap.lang = item.lang;
      b.append(tile, cap);
      b.title = (item.word || "#" + item.id) + (item.meaning ? " — " + item.meaning : "");
      b.addEventListener("click", () => choose(item));
      if (adding) b.addEventListener("dblclick", () => add(false));
      b._item = item;
      return b;
    }
    function drawGrid(fresh, from) {
      if (fresh) grid.replaceChildren();
      for (const item of S.items.slice(from)) grid.append(cell(item));
      grid.hidden = !S.items.length;
      const cells = [...grid.children];
      const mine = cells.find(c => S.selected && c._item.id === S.selected.id);
      for (const c of cells) { c.tabIndex = -1; c.setAttribute("aria-selected", c === mine ? "true" : "false"); }
      const tab = mine || cells[0];
      if (tab) tab.tabIndex = 0;
    }

    /* ---- the pictogram looked at ---- */
    function choose(item, focus) {
      S.selected = item;
      // on a narrow screen the preview is a sheet over the list: a tap opens it, the keys walking the thumbnails do not
      const sheet = !focus;
      if (sheet) preview.classList.remove("pg-closed");
      for (const c of grid.children) {
        const on = c._item.id === item.id;
        c.setAttribute("aria-selected", on ? "true" : "false");
        c.tabIndex = on ? 0 : -1;
        if (on && focus) c.focus({preventScroll: false});
      }
      preview.classList.add("pg-has");
      const img = document.createElement("img");
      img.alt = item.word || "";
      img.src = link(item);
      big.replaceChildren(img);
      word.textContent = item.word || "#" + item.id;
      word.dir = "auto";
      if (item.lang) word.lang = item.lang;
      meaning.hidden = !item.meaning;
      meaning.textContent = item.meaning || "";
      meaning.dir = "auto";
      tags.replaceChildren();
      for (const f of item.flags || []) {
        if (!FLAGS[f]) continue;
        tags.append(make("li", NASTY[f] ? "pg-flag" : "", FLAGS[f]));
      }
      tags.hidden = !tags.children.length;
      words.replaceChildren();
      for (const [code, list] of Object.entries(item.words || {})) {
        const dt = make("dt", "", names[code] || code), dd = make("dd", "", list.join(", "));
        dd.lang = code;
        dd.dir = "auto";
        words.append(dt, dd);
      }
      number.textContent = "ARASAAC pictogram " + item.id;
      tell("");
      buttons();
      // a sheet over the list (a narrow screen) is where the keys go when it opens; beside the list they stay on it
      if (sheet && window.matchMedia && matchMedia("(max-width: 760px)").matches) at(".pg-back").focus({preventScroll: true});
    }
    function buttons() {
      actions.replaceChildren();
      if (!adding) {
        actions.append(make("p", "pg-view-only", "To use a pictogram, open it from the editor or from an exercise: they have a “Pictogram…” button that adds it there."));
        return;
      }
      const go = make("button", "pg-btn pg-primary", opts.addLabel || "Add");
      go.type = "button";
      go.disabled = S.busy || !S.selected;
      go.addEventListener("click", () => add(false));
      actions.append(go);
      if (opts.keepLabel) {
        const keep = make("button", "pg-btn", opts.keepLabel);
        keep.type = "button";
        keep.disabled = S.busy || !S.selected;
        keep.addEventListener("click", () => add(true));
        actions.append(keep);
      }
    }
    function pickOf(item) {
      const name = "arasaac-" + item.id + ".png";
      return {id: item.id, word: item.word || "", lang: item.lang || "", meaning: item.meaning || "",
              words: item.words || {}, flags: item.flags || [], url: link(item), name, credit: S.credit || "",
              alt: alt(item.word),
              async file() {
                const r = await fetch(link(item));
                if (!r.ok) throw new Error("That picture is not on this computer any more.");
                return new File([await r.blob()], name, {type: "image/png"});
              }};
    }
    async function add(keepOpen) {
      const item = S.selected;
      if (!adding || !item || S.busy) return;
      S.busy = true;
      buttons();
      tell("Adding…");
      PICKED.add(item.id);
      try {
        // what the page says it did besides (a string it hands back) is said in the frame's own line: a toast of the page
        // is under the frame's dim while it is open
        const also = await opts.onPick(pickOf(item), {close});
        if (S.closed) return;
        if (keepOpen) {
          preview.classList.add("pg-closed");           // narrow: back to the list, to choose another
          tell("Added “" + (item.word || "#" + item.id) + "”. " + (typeof also === "string" && also ? also + " " : "")
               + "Choose another, or close this.", "good");
          // what was added may have taken the focus to the page behind (the editor puts the cursor in its text)
          if (!modal.contains(document.activeElement)) q.focus({preventScroll: true});
        } else close();
      } catch (e) {
        if (!S.closed) tell((e && e.message) || "That could not be added.", "bad");
      } finally {
        S.busy = false;
        if (!S.closed) buttons();
      }
    }

    /* ---- asking: the first page of an answer replaces the thumbnails, the next ones follow them ---- */
    async function load(fresh) {
      const mine = ++S.seq;
      if (S.abort) S.abort.abort();
      const stop = S.abort = new AbortController();
      const from = fresh ? 0 : S.items.length;
      results.classList.add("pg-loading");
      results.setAttribute("aria-busy", "true");
      let data;
      try {
        const r = await fetch(opts.search, {
          method: "POST", headers: {"Content-Type": "application/json"}, signal: stop.signal,
          body: JSON.stringify({q: S.q, locales: S.lang ? [S.lang] : [], display: S.lang || opts.lang || "",
                                offset: from, limit: PAGE, sensitive: S.sensitive})});
        data = await r.json().catch(() => ({}));
        if (!r.ok || data.ok === false) throw new Error(data.error || "The search failed (" + r.status + ").");
      } catch (e) {
        if (S.closed || mine !== S.seq || (e && e.name === "AbortError")) return;
        results.classList.remove("pg-loading");
        results.setAttribute("aria-busy", "false");
        return failed((e && e.message) || "The search failed.");
      }
      if (S.closed || mine !== S.seq) return;
      results.classList.remove("pg-loading");
      results.setAttribute("aria-busy", "false");
      S.ready = !!data.ready;
      S.credit = data.credit || S.credit || "";
      if (S.credit) CREDIT = S.credit;
      credit.textContent = S.credit;
      drawLanguages(data.locales);
      if (!S.ready) return notReady(data);
      empty.hidden = true;
      preview.hidden = false;
      S.items = fresh ? data.results : S.items.concat(data.results);
      S.total = data.total;
      S.more = !!data.more;
      S.hidden = data.hidden || 0;
      drawGrid(fresh, from);
      moreRow.hidden = !S.more;
      const where = S.lang ? " in " + (names[S.lang] || S.lang) : "";
      // a download that is not finished is searched as far as it got, and that is said
      const part = data.state === "partial"
        ? " · only " + (data.pictures || 0).toLocaleString() + " of " + (data.listed || 0).toLocaleString()
          + " pictures are here" + (data.fetching ? ", the rest being fetched" : "") : "";
      if (S.total) {
        count.replaceChildren(make("b", "", S.total.toLocaleString()),
          " " + plural(S.total, "pictogram", "pictograms") + (S.q ? " for “" + data.q + "”" : "") + where + part);
      } else {
        count.textContent = (S.q ? "No pictogram for “" + data.q + "”" : "No pictogram") + where + part + ".";
      }
      if (S.hidden && !S.sensitive) {
        const b = make("button", "pg-link", "Include them");
        b.type = "button";
        b.addEventListener("click", () => { sens.checked = true; S.sensitive = true; load(true); });
        const lead = data.q ? S.hidden + " more " + plural(S.hidden, "pictogram matches but is", "pictograms match but are")
                            : S.hidden + " " + plural(S.hidden, "pictogram is", "pictograms are");
        hiddenNote.replaceChildren(lead + " left out, because ARASAAC marks " + plural(S.hidden, "it", "them")
          + " as about violence or sex. ", b);
        hiddenNote.hidden = false;
      } else hiddenNote.hidden = true;
    }

    /* ---- the keys ---- */
    function grow(from, step) {
      const cells = [...grid.children];
      const i = cells.indexOf(from);
      if (i < 0) return;
      let j = i + step;
      if (Math.abs(step) > 1) {           // up and down: the cell above or below in the same column
        const per = cells.filter(c => c.offsetTop === cells[0].offsetTop).length || 1;
        j = i + Math.sign(step) * per;
      }
      if (j < 0 || j >= cells.length) {
        if (j >= cells.length && S.more && step > 0) more.focus();
        return;
      }
      choose(cells[j]._item, true);
    }
    grid.addEventListener("keydown", e => {
      const c = e.target.closest(".pg-cell");
      if (!c) return;
      const rtl = getComputedStyle(grid).direction === "rtl";
      const k = e.key;
      const step = k === "ArrowRight" ? (rtl ? -1 : 1) : k === "ArrowLeft" ? (rtl ? 1 : -1)
                 : k === "ArrowDown" ? 2 : k === "ArrowUp" ? -2 : 0;
      if (step) { e.preventDefault(); grow(c, step); }
      else if (k === "Home" || k === "End") {
        e.preventDefault();
        const cells = [...grid.children];
        choose((k === "Home" ? cells[0] : cells[cells.length - 1])._item, true);
      }
    });
    function trap(e) {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
      if (e.key !== "Tab") return;
      const live = [...modal.querySelectorAll("button, input, select, a[href], [tabindex='0']")]
        .filter(n => !n.disabled && !n.hidden && n.tabIndex >= 0 && n.getClientRects().length);
      if (!live.length) return;
      const first = live[0], last = live[live.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === modal)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    ov.addEventListener("keydown", trap);

    q.addEventListener("input", () => {
      clearTimeout(S.timer);
      S.timer = setTimeout(() => { S.q = q.value; load(true); }, WAIT);
    });
    form.addEventListener("submit", e => {
      e.preventDefault();
      clearTimeout(S.timer);
      S.q = q.value;
      load(true);
    });
    q.addEventListener("search", () => { clearTimeout(S.timer); S.q = q.value; load(true); });
    langSel.addEventListener("change", () => { S.lang = langSel.value; remember(S.lang); load(true); });
    sens.addEventListener("change", () => { S.sensitive = sens.checked; load(true); });
    more.addEventListener("click", () => load(false));
    at(".pg-back").addEventListener("click", () => {
      preview.classList.add("pg-closed");
      const cell = [...grid.children].find(c => S.selected && c._item.id === S.selected.id);
      if (cell) cell.focus({preventScroll: false});
    });

    /* ---- opening and closing ---- */
    function close() {
      if (S.closed) return;
      S.closed = true;
      clearTimeout(S.timer);
      if (S.abort) S.abort.abort();
      ov.remove();
      // the focus goes back to what opened the frame -- unless what was added has put it somewhere better (the text
      // the editor has just written into)
      const now = document.activeElement;
      const lost = !now || now === document.body || modal.contains(now);
      if (lost && before && before.isConnected && before.focus) { try { before.focus(); } catch (e) { /* gone */ } }
      if (opts.onClose) opts.onClose();
    }
    ov._pgClose = close;
    ov.addEventListener("click", e => { if (e.target === ov) close(); });
    at(".pg-x").addEventListener("click", close);

    const keptLang = remembered();
    if (keptLang) S.lang = keptLang;
    buttons();
    root.append(ov);
    q.focus({preventScroll: true});
    load(true);
    return {close};
  }

  /* What a page asks of this file besides the frame:
       credit(searchUrl)  ARASAAC's credit in its own short words, as the server words it: what a search last said, else
                   asked of `searchUrl` (a page that took a picture from a deck has searched nothing); a promise
       used(text)  does `text` name a picture of a pictogram that was added through a frame since this page loaded?
       named(text) does `text` name one at all (images/arasaac-<number>.png)?  The pictures are copies named so.
     A page that has just taken a pictogram in asks whether the document is credited (docs/arasaac.md, 5.7). */
  const NAMED = /images\/arasaac-(\d+)(?:-\d+)?\.png/g;
  window.ParsehPictograms = {
    open, alt,
    credit: async searchUrl => {
      if (CREDIT || !searchUrl) return CREDIT;
      const r = await fetch(searchUrl, {method: "POST", headers: {"Content-Type": "application/json"},
                                        body: JSON.stringify({q: "", limit: 1})});
      const data = await r.json().catch(() => ({}));
      if (r.ok && data.credit) CREDIT = data.credit;
      return CREDIT;
    },
    named: text => /images\/arasaac-\d+(?:-\d+)?\.png/.test(String(text || "")),
    used: text => [...String(text || "").matchAll(NAMED)].some(m => PICKED.has(+m[1])),
  };
})();
