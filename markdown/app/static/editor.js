// SPDX-License-Identifier: GPL-3.0-or-later
/* The studio's EDIT PAGE (TO-DO §4.8).

   Lifted out of app.js with the exercise form (static/exform.js, which this
   needs and which the deck pages need too).  Loaded by the edit page alone,
   so that the library, a document being read, and every page a phone shows
   carry none of it.

   A classic script, after app.js and exform.js; nothing here is new.
*/
/* ---------------- edit page ---------------- */

function initEdit() {
  const src = $("#src");
  const sheet = $("#sheet");
  const status = $("#pv-status");
  let dirty = false;
  bindPersianCopy(sheet);
  bindFootnoteClouds(sheet);
  bindStopServer();

  // a new document starts in the language the toolbox is set to (the
  // shared preference), unless it is "all"
  if (!DOC_ID) {
    const pick = sharedLang();
    if (pick !== "all" && LANGS.some(l => l.code === pick))
      src.value = src.value.replace(/^target:\s*\S+\s*$/m, "target: " + pick);
  }

  /* The language of the buffer: the record the page came with, replaced
     by whatever the preview reports (a `target:` typed into the front
     matter takes effect live).  Everything language-dependent in the
     chrome is set here so a change reaches every control. */
  function applyLangUi() {
    const L = lang();
    document.body.dataset.lang = L.code;
    sheet.dataset.lang = L.code;
    const kanaBtn = $("#ins-kana");
    if (kanaBtn) kanaBtn.hidden = !L.reading;
    const tlLabel = $("#btn-tl-editor-label");
    if (tlLabel) tlLabel.textContent = "✎ " + L.name;
    // the preview wears the document's typography (the gear's Text rows move it,
    // and name themselves after this language: they are told)
    studioTypo.refresh();
  }
  applyLangUi();

  const back = $("#btn-back");
  back.href = DOC_ID ? BASE + "/doc/" + DOC_ID : BASE + "/";

  const panelClosers = [];   // layout panels die with the DOM they point at

  /* The exercise form itself lives at top level (openExerciseForm), shared
     with the exercise decks; here it only has to know where the result
     goes: at the cursor for a new exercise, over lines line..endLine for
     one reopened from the preview's ✎ Edit. */
  /* A card's pictures and recordings go into this document's own folders,
     as the toolbar's do: a document not saved yet has none. */
  const formUploads = {
    uploadImage: async file => {
      if (!DOC_ID) throw new Error("Save the document first");
      const data = await uploadImage(DOC_ID, file);
      return {path: data.path, url: data.url};
    },
    uploadAudio: async file => {
      if (!DOC_ID) throw new Error("Save the document first");
      const data = await uploadAudio(DOC_ID, file);
      return {path: data.path, url: data.url};
    },
  };

  /* WHAT A FOLLOW-UP'S FORM CAN OFFER OF THIS PAGE (exform.js, "+ From this page…"): the exercises the source has,
     found by their fences in the text itself, which is what will be written to -- the preview may be a moment
     behind.  `own`: the line of the follow-up being edited, which is not one of them. */
  const pageOffer = own => ({
    noun: "page",
    list: () => exerciseBlocksIn(src.value).filter(b => b.line !== own)
      .map(b => ({key: b.line, source: b.source})),
    removeLabel: "Remove them from the page once they are in the chain",
    putBackWhere: "on the page",
  });

  /* What the form hands over besides the chain: the exercises it was made of, to leave the page, and the steps to
     become exercises of their own after it.  Both are written with the chain in ONE undoable step. */
  function removedBlocks(extra) {
    const keys = new Set((extra && extra.remove) || []);
    return exerciseBlocksIn(src.value).filter(b => keys.has(b.key));
  }
  const withPutBack = (text, extra) => [text].concat((extra && extra.putBack) || []).join("\n\n");
  // two blank lines where a block was taken off are one too many
  const tidyAt = (lines, at) => {
    if (at < lines.length && !lines[at].trim() && (at === 0 || !lines[at - 1].trim())) lines.splice(at, 1);
  };

  function editExerciseAt(line, endLine) {
    const lines = src.value.split("\n");
    openExerciseMarkdown(lines.slice(line, endLine + 1).join("\n"), Object.assign({
      fromPage: pageOffer(line),
      onSave: (text, extra) => {
        const current = src.value.split("\n");
        // from the bottom up, so that every line number still means what it did when the form was opened
        const ops = removedBlocks(extra).filter(b => b.line < line || b.line > endLine)
          .map(b => ({from: b.line, to: b.endLine, text: null}));
        ops.push({from: line, to: Math.max(line, endLine), text: withPutBack(text, extra)});
        for (const op of ops.sort((x, y) => y.from - x.from)) {
          current.splice(op.from, op.to - op.from + 1, ...(op.text === null ? [] : op.text.split("\n")));
          if (op.text === null) tidyAt(current, op.from);
        }
        setSource(current.join("\n"));
        if (pictogramsUsed(text)) ensureArasaacCredit();
      },
    }, formUploads));
  }

  /* The source with some blocks taken off, the cursor kept where it was in the text (or, if it was inside one that
     went, at the place it left). */
  function takeOff(blocks) {
    const mark = "\u0001", text = src.value, at = src.selectionStart;
    const lines = (text.slice(0, at) + mark + text.slice(at)).split("\n");
    const cursorLine = text.slice(0, at).split("\n").length - 1;
    let lost = null;
    for (const b of blocks.slice().sort((x, y) => y.line - x.line)) {
      if (b.line <= cursorLine && cursorLine <= b.endLine)
        lost = b.line - blocks.filter(o => o.endLine < b.line).reduce((n, o) => n + o.endLine - o.line + 1, 0);
      lines.splice(b.line, b.endLine - b.line + 1);
      tidyAt(lines, b.line);
    }
    let value = lines.join("\n");
    let k = value.indexOf(mark);
    if (k >= 0) value = value.slice(0, k) + value.slice(k + 1);
    else k = lost === null ? value.length : value.split("\n").slice(0, lost).join("\n").length + (lost ? 1 : 0);
    src.value = value;
    src.setSelectionRange(k, k);
  }

  // a pasted exercise names its clips; they come into the document before
  // the form opens, so its preview plays them (a document not saved yet
  // brings them in when it is saved)
  function chooseExercise() {
    openExercisePicker(Object.assign({onSave: (text, extra) => {
                                        // the exercises a new follow-up was made of leave the page in the same step that writes it
                                        const gone = removedBlocks(extra);
                                        insertStandaloneLine(withPutBack(text, extra), undefined,
                                                             gone.length ? () => takeOff(gone) : undefined);
                                        // a pictogram the form's own Pictogram… put in: the document is to credit ARASAAC
                                        if (pictogramsUsed(text)) ensureArasaacCredit();
                                      },
                                      fromPage: pageOffer(-1),
                                      onPaste: text => adoptFromTray(text)}, formUploads));
  }

  /* ---- an exercise out of a deck ----

     The other direction of "+ Deck": a deck of this page's language, one of
     its exercises, and it goes in at the cursor.  The copy is the server's
     (POST …/items/<id>/to-doc), not this script's, because an exercise
     brings its pictures and recordings with it and they have to be written
     into THIS document's images/ and audio/ -- renamed where a different
     file of that name is already there, with the references rewritten to
     match, which is the deck store's own rule read backwards.  What comes
     back is the markdown and the definitions of the footnotes it calls. */
  function deckItemRow(item) {
    const row = document.createElement("button");
    row.type = "button"; row.className = "dl-item"; row.dataset.id = item.id;
    const label = document.createElement("span");
    label.className = "dl-t"; label.textContent = item.label || "Exercise";
    const text = document.createElement("span");
    // dir="auto": a prompt is often written in the gloss language and a
    // target-language excerpt in the target's, and the first strong
    // character says which -- one rule for both, and no Latin sentence
    // shown with its question mark on the wrong end
    text.className = "dl-s"; text.lang = lang().code; text.dir = "auto";
    text.textContent = item.excerpt || "(no text)";
    row.append(label, text);
    if ((item.errors || []).length) {
      row.classList.add("dk-broken");
      row.title = item.errors.join("; ");
    }
    return row;
  }

  /** The definition lines of `footnotes` put into `text`, and the ids that
      had to be renamed on the way rewritten in `block`.
      A document of its own may already call a note "n1" and mean something
      else by it; the same id with the same words is the same note and is
      left alone. */
  function mergeFootnotes(text, block, footnotes) {
    const lines = (footnotes || "").split("\n").filter(l => FN_DEF_RE.test(l));
    if (!lines.length) return {text, block};
    const here = new Map();
    for (const d of footnoteDefs(text.split("\n")))
      here.set(d.id, text.split("\n").slice(d.from, d.to).join("\n").replace(FN_DEF_RE, "").trim());
    for (const line of lines) {
      const id = line.match(FN_DEF_RE)[1];
      const body = line.replace(FN_DEF_RE, "").trim();
      if (here.has(id) && here.get(id) === body) continue;   // the same note
      let final = id, n = 2;
      while (here.has(final)) final = `${id}-${n++}`;
      if (final !== id)                       // only whole references, and
        block = block.split(`[^${id}]`).join(`[^${final}]`);   // only in the block
      here.set(final, body);
      text = placeFootnoteDef(text, final, body);
    }
    return {text, block};
  }

  async function loadFromDeck() {
    if (!DOC_ID) {
      toast("Save the document first — an exercise's pictures live in its folder", true);
      return;
    }
    const root = $("#modal-root"); root.innerHTML = "";
    const ov = document.createElement("div"); ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal ex-from-deck-modal" role="dialog" aria-modal="true">
      <h3>Load an exercise from a deck</h3>
      <p>It goes in at the cursor, exactly as it is in the deck. Its pictures and
        recordings are copied into this document.</p>
      ${DECK_FIELDS}
      <div class="dl-list" data-x="items"></div>
      <div class="row"><span class="pv-status" data-x="status"></span>
        <button class="btn" data-x="cancel">Cancel</button>
        <button class="btn primary" data-x="insert" disabled>Insert</button></div></div>`;
    let picker;
    try {
      picker = await deckPicker(ov, {allowNew: false});
    } catch (e) {
      toast("Could not read the decks: " + e.message, true);
      return;
    }
    const list = $('[data-x="items"]', ov), status = $('[data-x="status"]', ov);
    const insert = $('[data-x="insert"]', ov);
    let chosen = null, items = [];
    const close = () => { root.innerHTML = ""; src.focus(); };
    $('[data-x="cancel"]', ov).addEventListener("click", close);
    ov.addEventListener("click", e => { if (e.target === ov) close(); });

    async function showDeck() {
      chosen = null; insert.disabled = true; list.innerHTML = "";
      const path = picker.select.value;
      if (!path) {
        status.textContent = `No ${lang().name} deck yet — make one with “+ Deck” on a page.`;
        return;
      }
      status.textContent = "Reading the deck…";
      try {
        const data = await decksFetch(deckUrl(path));
        items = data.items || [];
      } catch (e) {
        status.textContent = "Could not read that deck: " + e.message;
        return;
      }
      status.textContent = items.length
        ? `${items.length} exercise${items.length === 1 ? "" : "s"}`
        : "That deck is empty.";
      for (const item of items) list.appendChild(deckItemRow(item));
    }
    list.addEventListener("click", e => {
      const row = e.target.closest(".dl-item");
      if (!row) return;
      $$(".dl-item", list).forEach(r => r.classList.toggle("on", r === row));
      chosen = row.dataset.id;
      insert.disabled = false;
    });
    picker.select.addEventListener("change", showDeck);
    await showDeck();
    picker.focus();

    insert.addEventListener("click", async () => {
      if (!chosen) return;
      insert.disabled = true; status.textContent = "Copying…";
      try {
        const body = {doc_id: DOC_ID};
        if (notesSource) body.source = notesSource;
        const got = await decksFetch(
          `${deckUrl(picker.select.value)}/items/${encodeURIComponent(chosen)}/to-doc`,
          {method: "POST", json: body});
        picker.remember(picker.select.value);
        // the footnotes first: an id that had to be renamed is renamed in
        // the block before the block goes in
        const merged = mergeFootnotes(src.value, got.markdown, got.footnotes);
        if (merged.text !== src.value) {
          // the cursor is where the writer left it, and the notes went in
          // further down; setSource keeps it there
          const at = src.selectionStart;
          setSource(merged.text, at);
        }
        insertStandaloneLine(merged.block);
        // a deck's exercise may carry pictograms, copied with it: the page takes the credit with them
        if (pictogramsNamed(merged.block)) ensureArasaacCredit();
        close();
        // one toast, as the copies into a deck answer: a second would only
        // rub out the first, and a warning nobody reads is no warning
        const warnings = got.warnings || [];
        toast("Exercise inserted" + (warnings.length ? " — " + warnings.join(" · ") : ""),
              warnings.length > 0);
      } catch (e) {
        status.textContent = "";
        insert.disabled = false;
        toast("Could not load it: " + e.message, true);
      }
    });
    root.appendChild(ov);
  }

  async function exercisePrompt() {
    const code = encodeURIComponent(lang().code);
    // ONLY THE DECKS OF THIS PAGE'S LANGUAGE: a Persian page is not offered a Japanese deck's words (brief §7.6).
    // The levels and the lengths are the server's lists, which the exercise prompt's answer does not carry: they
    // come with the prompt page's, asked for with no box ticked, which is its shortest
    const [data, lists] = await Promise.all([
      api("/api/exercise-decks?target=" + code),
      api("/api/prompt?target=" + code + "&boxes=").catch(() => ({})),
    ]);
    const root = $("#modal-root"); root.innerHTML = "";
    const ov = document.createElement("div"); ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal ex-prompt-modal" role="dialog" aria-modal="true">
      <h3>Generate exercises with an LLM</h3>
      <p>The page itself is always included. Optionally add vocabulary the learner already knows from these Anki decks.</p>
      <div class="ex-prompt-body">
        <div class="ex-decks"></div>
        <div data-x="boxes"></div>
        <div data-x="under"></div>
      </div>
      <div data-x="row"></div>
      <div class="row"><span class="pv-status ex-copy-status"></span>
        <button class="btn" data-x="cancel">Close</button></div></div>`;
    const list = $(".ex-decks", ov);
    if (!(data.decks || []).length) list.innerHTML = `<span class="pv-status">No ${lang().name} Anki deck installed — the prompt works without one.</span>`;
    for (const d of data.decks || []) {
      const label = document.createElement("label"); label.className = "ex-deck";
      const ck = document.createElement("input"); ck.type = "checkbox"; ck.value = d.path;
      const text = document.createElement("span");
      text.textContent = `${d.name} · ${d.language} · ${d.cards} card${d.cards === 1 ? "" : "s"}`;
      label.append(ck, text); list.appendChild(label);
    }
    /* WHAT THE PROMPT TEACHES (static/promptpick.js, the panel the prompt page draws too): the dialect's
       boxes and the twelve exercise types come ticked from what THIS PAGE already uses -- the server
       reads it with the parser and says it in `preticked` -- and are the person's to change from there.
       Nothing is remembered between two openings: what a page uses is not what another one does, and
       the studio page's own choices (its boxes, its prompt) are that page's and do not come here. */
    const teach = ParsehPromptPick.boxes($('[data-x="boxes"]', ov), {
      level: 4, types: "the exercises to ask for",
      why: "ticked from what this page already uses. whatever you do not tick is still named in the prompt " +
        "as reserved, so the model does not write it by accident.",
      onChange: () => row && row.invalidate(),
    });
    const under = ParsehPromptPick.line($('[data-x="under"]', ov), {
      surface: "studio-exercises", lang: lang().code, remember: null,
      onChange: () => row && row.invalidate(),
    });
    under.draw(lists);
    /* THE PROMPT is made by the server from this page, the boxes and types ticked and the decks ticked,
       as the dialog opens and each time one changes; the row (lib/llmrow.js) holds it, says how long it
       is before the copy, and copies exactly it.  What the decks added to it is said as soon as it is
       made.  The first ask names neither boxes nor types: the answer says what the page uses. */
    const say = text => { $(".ex-copy-status", ov).textContent = text; };
    const row = window.ParsehLLMRow ? ParsehLLMRow.mount($('[data-x="row"]', ov), {
      surface: "studio-exercises", cls: "btn primary",
      remind: "paste it into your chatbot, then put the exercises it writes into this page.",
      // THE PROMPT MENU lists the person's own prompts for exercises, in this page's language; its choice is
      // this dialog's own (the studio page's prompt has a menu of its own, and a choice of its own)
      lang: lang().code, options: false, promptsUrl: BASE + "/api/prompts/",
      // the editor of a prompt opens at the top of the part of the dialog that scrolls: the row has no room for it
      editorHost: () => $(".ex-prompt-body", ov),
      getText: async () => {
        const decks = $$('input[type="checkbox"]:checked', list).map(x => x.value);
        const body = Object.assign({markdown: src.value, decks}, under.params());
        if (row && row.promptId()) body.prompt = row.promptId();
        if (teach.boxes()) body.boxes = teach.boxes();
        if (teach.types()) body.types = teach.types();
        if (body.types && !body.types.length) {
          say("tick at least one exercise type: there is nothing to ask for without one");
          return "";
        }
        const result = await api("/api/exercise-prompt", {method: "POST", json: body});
        teach.draw(result);
        const known = result.vocabulary;
        say(known ? `${known} known item${known === 1 ? "" : "s"} from your decks ${known === 1 ? "is" : "are"} in it` : "");
        // the short request for a chat that has the skill is made with the prompt, and the row holds it beside it
        if (row && row.skillOf) row.skillOf(result.skill);
        return result.prompt;
      },
      measure: () => ov.isConnected,
    }) : null;
    const close = () => { if (row) row.destroy(); under.destroy(); root.innerHTML = ""; };
    $('[data-x="cancel"]', ov).addEventListener("click", close);
    ov.addEventListener("click", e => { if (e.target === ov) close(); });
    root.appendChild(ov);
    if (row) {
      list.addEventListener("change", () => row.invalidate());
      // the first prompt waits for the options, so that it is made the way it will be asked for
      Promise.all([under.ready(), row.promptReady()]).then(() => row.refresh());
    } else $('[data-x="row"]', ov).textContent = "The prompt helper could not be loaded.";
  }

  async function preview() {
    liveSend();           // the preview in its own tab, if there is one (below)
    try {
      const data = await api("/api/preview",
                             {method: "POST",
                              json: {markdown: src.value, doc_id: DOC_ID}});
      if (!data.ok) throw new Error(data.error);
      panelClosers.forEach(c => c());
      sheet.innerHTML = data.doc.html;
      freshMedia(sheet, DOC_ID);
      // the prose the document declares; an omitted `lang:` is English,
      // the same as the PDF sets and as the README has always said
      sheet.lang = data.doc.lang || "en";
      const target = lang().code;
      if (data.doc.lang_record && data.doc.target !== lang().code) {
        LANG = data.doc.lang_record;
        applyLangUi();
      }
      // a `lang:` or a `target:` typed into the front matter: the way the
      // source is written by default, and its face, may follow them
      if ((data.doc.prose && (data.doc.prose.code !== prose.code || data.doc.prose.dir !== prose.dir))
          || lang().code !== target) {
        if (data.doc.prose) prose = data.doc.prose;
        applyEditorDir();
      }
      armClipReplay(sheet);
      bindExercises(sheet, {preview: true, onEdit: editExerciseAt});
      status.textContent = (data.doc.target_error ? data.doc.target_error + " · " : "")
        + "rendered " + new Date().toTimeString().slice(0, 8);
      status.classList.toggle("err", !!data.doc.target_error);
      setTimeout(alignPanes, 0);   // not rAF: it stalls in a hidden pane
    } catch (e) {
      status.textContent = "render error: " + e.message;
      status.classList.add("err");
    }
  }

  /* ---- pane alignment --------------------------------------------------
     The renderer tags every top-level block with its source line
     (data-src-line).  A textarea has ONE line-height, so per-block
     spacing is impossible; instead: (1) the editor's line-height and top
     padding are least-squares fitted against ALL anchors, so the whole
     document — not just its end — pulls the interline into place, and
     (2) the same anchors drive piecewise-corrected synchronised
     scrolling, which keeps the middle of the two panes lined up in view
     where a single interline cannot. Recomputed on every render. */
  const scroller = $(".preview-scroll");
  const alignState = {off: null, lh: null, srcYs: [], prevYs: [],
                      fontPx: parseFloat(getComputedStyle(src).fontSize)};
  let mirror = null;

  function measureRows() {
    // per-source-line wrapped row counts, via a mirror at a fixed 20px
    // line-height (wrap count depends on width/font, not on line-height)
    const cs = getComputedStyle(src);
    if (!mirror) {
      mirror = document.createElement("div");
      mirror.className = "src-mirror";
      mirror.setAttribute("aria-hidden", "true");
      src.parentElement.appendChild(mirror);
    }
    mirror.style.font = cs.font;
    // and its direction, and its unicode-bidi (whatever a style gives the
    // textarea's lines, its lines have): a line wraps where the textarea
    // wraps it
    mirror.style.direction = cs.direction;
    mirror.style.unicodeBidi = cs.unicodeBidi;
    mirror.style.textAlign = cs.textAlign;
    mirror.style.lineHeight = "20px";
    mirror.style.width = Math.max(
      60, src.clientWidth - parseFloat(cs.paddingLeft)
      - parseFloat(cs.paddingRight)) + "px";
    const lines = src.value.split("\n");
    const frag = document.createDocumentFragment();
    for (const l of lines) {
      const d = document.createElement("div");
      d.textContent = l || " ";
      frag.appendChild(d);
    }
    mirror.textContent = "";
    mirror.appendChild(frag);
    const rows = [];
    for (const d of mirror.children) rows.push(d.offsetTop / 20);
    rows.push(mirror.scrollHeight / 20);      // total, as a sentinel
    return rows;
  }

  function alignPanes() {
    if (!scroller) return;
    // a collapsed pane (tiny window, hidden panel) produces degenerate
    // geometry — leave the defaults alone until there is room to fit
    if (src.clientWidth < 200 || scroller.clientWidth < 200) return;
    const els = $$("[data-src-line]", sheet);
    if (els.length < 2) {
      src.style.lineHeight = "";
      src.style.paddingTop = "";
      alignState.srcYs = [];
      return;
    }
    const rows = measureRows();
    // measure the preview at its baseline margin (a previous pass may
    // have shifted it)
    sheet.style.marginTop = "";
    const baseMargin = parseFloat(getComputedStyle(sheet).marginTop) || 0;
    const scRect = scroller.getBoundingClientRect();
    const seen = new Set();
    const xs = [], ys = [];
    for (const el of els) {
      const line = +el.dataset.srcLine;
      if (seen.has(line) || line >= rows.length - 1) continue;
      seen.add(line);
      xs.push(rows[line]);
      ys.push(el.getBoundingClientRect().top - scRect.top
              + scroller.scrollTop);
    }
    if (xs.length < 2) return;
    // least squares y = off + lh * rows
    const n = xs.length;
    const mx = xs.reduce((a, b) => a + b, 0) / n;
    const my = ys.reduce((a, b) => a + b, 0) / n;
    let sxx = 0, sxy = 0;
    for (let i = 0; i < n; i++) {
      sxx += (xs[i] - mx) * (xs[i] - mx);
      sxy += (xs[i] - mx) * (ys[i] - my);
    }
    if (sxx < 1e-6) return;
    let lh = sxy / sxx;
    lh = Math.max(alignState.fontPx * 1.25,
                  Math.min(lh, alignState.fontPx * 6));
    let off = my - lh * mx;
    // a negative intercept means the source's opening lines are taller
    // than the rendered title block: the editor cannot have negative
    // padding, so the PREVIEW is shifted down by a container margin
    // instead (its typography is untouched)
    const MINPAD = 12;
    let shift = 0;
    if (off < MINPAD) {
      shift = MINPAD - off;
      off = MINPAD;
    }
    sheet.style.marginTop = shift ? (baseMargin + shift) + "px" : "";

    // keep the source line at the viewport top where it was
    const cs = getComputedStyle(src);
    const oldLh = alignState.lh || parseFloat(cs.lineHeight);
    const oldOff = alignState.off !== null
      ? alignState.off : parseFloat(cs.paddingTop);
    const topRows = Math.max(0, (src.scrollTop - oldOff) / oldLh);
    src.style.lineHeight = lh.toFixed(2) + "px";
    src.style.paddingTop = off.toFixed(1) + "px";
    src.scrollTop = off + topRows * lh - 0.0001;
    alignState.lh = lh;
    alignState.off = off;

    // piecewise map for the synchronised scroll (0,0 and totals close it)
    const srcYs = [0], prevYs = [0];
    for (let i = 0; i < n; i++) {
      srcYs.push(off + xs[i] * lh);
      prevYs.push(ys[i] + shift);
    }
    srcYs.push(off + rows[rows.length - 1] * lh + 40);
    prevYs.push(scroller.scrollHeight);
    alignState.srcYs = srcYs;
    alignState.prevYs = prevYs;
  }

  function pwMap(y, from, to) {
    if (!from.length) return y;
    let i = 1;
    while (i < from.length - 1 && from[i] < y) i++;
    const a = from[i - 1], b = from[i];
    const t = b > a ? (y - a) / (b - a) : 0;
    return to[i - 1] + t * (to[i] - to[i - 1]);
  }

  let syncLock = null;
  function syncFrom(which) {
    if (!alignState.srcYs.length || syncLock === (which === "src"
        ? "preview" : "src")) return;
    syncLock = which;
    const focus = 0.35;      // align at just above the middle of the view
    if (which === "src") {
      const yv = src.scrollTop + src.clientHeight * focus;
      scroller.scrollTop = pwMap(yv, alignState.srcYs, alignState.prevYs)
        - scroller.clientHeight * focus;
    } else {
      const yv = scroller.scrollTop + scroller.clientHeight * focus;
      src.scrollTop = pwMap(yv, alignState.prevYs, alignState.srcYs)
        - src.clientHeight * focus;
    }
    setTimeout(() => { syncLock = null; }, 60);
  }
  src.addEventListener("scroll", () => syncFrom("src"), {passive: true});
  if (scroller) scroller.addEventListener(
    "scroll", () => syncFrom("preview"), {passive: true});
  window.addEventListener("resize", debounce(alignPanes, 250));
  if (document.fonts && document.fonts.ready)
    document.fonts.ready.then(() => setTimeout(alignPanes, 50));
  const debouncedPreview = debounce(preview, 350);

  /* ---- the direction of the source -------------------------------------
     A Persian writing to teach English to Persians writes Persian prose
     around English words, and a textarea laid out left to right puts every
     full stop, question mark and heading mark of that prose at the wrong
     end of its line.  ⇤ RTL editor turns the whole source right to left:
     the textarea alone -- the preview is drawn as it always is, and the
     exercise form's own direction buttons are their own.  Until it is
     pressed the source goes the way its prose language (`lang:`, the
     server's prose record) is written, and follows a `lang:` typed into
     the front matter; once pressed, the choice is the document's,
     remembered in this browser under parseh_editor_dir:<id>.  A document
     not saved yet has no id: its choice is kept with the page it is being
     written in, in that page's entry of the browser's history -- a reload
     keeps it, and the next new document, a page of its own, starts from
     its own `lang:` and never from a choice made for another one -- and is
     the saved document's own from its first save.  Right to left, the
     source is set in a face made for the script: the prose language's,
     when that is a right-to-left language the registry has a face for
     (Vazirmatn for Persian), else the target's, when that is one; left to
     right it stays monospace. */
  const DIR_KEY = "parseh_editor_dir:";
  function storedDir(id) {
    let v = null;
    try { v = id ? localStorage.getItem(DIR_KEY + id) : (history.state || {}).editorDir; }
    catch (e) { /* private mode */ }
    return v === "rtl" || v === "ltr" ? v : null;
  }
  function storeDir(id, v) {
    try {
      if (id) localStorage.setItem(DIR_KEY + id, v);
      else history.replaceState({...(history.state || {}), editorDir: v}, "");
    } catch (e) { /* private mode: the page keeps it */ }
  }
  let prose = readJson("prose-lang", null) || {code: "en", dir: "ltr"};
  let chosenDir = storedDir(DOC_ID);
  const btnDir = $("#btn-editor-dir");
  // who is told when the direction is drawn (the gear's row, static/gear.js)
  const dirSubs = new Set();
  function rtlFace() {
    const tokens = getComputedStyle(document.documentElement);
    const face = [prose, lang()].find(L => L && L.dir === "rtl"
                                      && tokens.getPropertyValue("--tl-font-" + L.code).trim());
    return face ? face.code : null;
  }
  function applyEditorDir() {
    const rtl = (chosenDir || (prose.dir === "rtl" ? "rtl" : "ltr")) === "rtl";
    src.dir = rtl ? "rtl" : "ltr";
    const face = rtl ? rtlFace() : null;
    if (face) {
      src.dataset.face = face;
      src.style.setProperty("--src-face", `var(--tl-font-${face})`);
    } else {
      delete src.dataset.face;
      src.style.removeProperty("--src-face");
    }
    if (btnDir) {
      btnDir.textContent = rtl ? "⇥ LTR editor" : "⇤ RTL editor";
      btnDir.title = rtl
        ? "The source is written right to left. Click to write it left to right (remembered for this document)"
        : "The source is written left to right. Click to write it right to left, "
          + "for a right-to-left prose language (remembered for this document)";
      btnDir.setAttribute("aria-label", btnDir.title);
    }
    // another face wraps the lines elsewhere: the panes are lined up again
    alignState.fontPx = parseFloat(getComputedStyle(src).fontSize);
    alignPanes();
    dirSubs.forEach(fn => { try { fn(); } catch (e) { /* the listener's own fault */ } });
  }
  // THE ONE PLACE THE CHOICE IS MADE: the button's press and the gear's
  // "Write the source right to left" (a0.5.0) both come here.  The button's
  // press keeps the cursor in the box it turned; the gear's switch keeps the
  // focus it has, so the keyboard that pressed it is still in the panel.
  function setEditorDir(rtl, keepFocusInSource) {
    chosenDir = rtl ? "rtl" : "ltr";
    storeDir(DOC_ID, chosenDir);
    applyEditorDir();
    if (keepFocusInSource) src.focus({preventScroll: true});
  }
  if (btnDir) btnDir.addEventListener("click", () => setEditorDir(src.dir !== "rtl", true));
  window.ParsehStudioEditorDir = {
    isRtl: () => src.dir === "rtl",
    set: rtl => setEditorDir(!!rtl, false),
    subscribe: fn => { dirSubs.add(fn); return () => dirSubs.delete(fn); },
  };
  applyEditorDir();

  /* ---- the double-click, and the preview in its own tab (a0.5.1) ---------
     static/live.js says what both are and what the two tabs say to each other; this is the
     editor's half, the half that has the textarea.

     DOUBLE-CLICK THE PREVIEW (the half page here, or the page in the other tab) and the
     source selects the word that drew what was clicked, and scrolls to it.  A tab cannot
     bring another to the front, so the page says where it landed (and the preview tab tries,
     by this window's name, to switch to this one).

     THE PREVIEW IN ITS OWN TAB is optional and off.  On, this page gives the half to the text and
     the reading page of the document (`/doc/<id>?live=1`) is drawn in another tab from the buffer
     as it is typed.  The switch is the gear's ("Preview in its own tab") or the button over the
     preview, and is remembered on this device. */
  const LIVE = window.StudioLive;
  const liveOk = !!(LIVE && LIVE.supported && DOC_ID);
  const OWN_KEY = "parseh_editor_preview_tab";
  const split = $(".split"), liveBar = $("#editor-livebar"), liveSay = $("#editor-live-say");
  const liveSubs = new Set();
  const titleWas = document.title;
  let ownTab = false, lastPreview = 0, seq = 0, lastCaret = -1, titleTimer = null;
  try { ownTab = liveOk && localStorage.getItem(OWN_KEY) === "1"; } catch (e) { /* private mode */ }
  const channel = liveOk ? new BroadcastChannel(LIVE.CHANNEL) : null;
  // who sent it is in every message (see live.js): another editor of the document, or a preview tab, is not this one's preview
  const post = m => channel.postMessage(Object.assign({from: "editor"}, m));
  const previewIsOpen = () => Date.now() - lastPreview < 10000;
  const caretLine = () => src.value.slice(0, src.selectionStart).split("\n").length - 1;

  function liveSend() {
    if (channel && previewIsOpen())
      post({t: "text", seq: ++seq, markdown: src.value, line: caretLine()});
  }
  function paintLive() {
    if (split) split.classList.toggle("own-tab", ownTab);
    if (liveBar) liveBar.hidden = !ownTab;
    if (liveSay) {
      liveSay.textContent = previewIsOpen()
        ? "The preview tab is open and follows what you type. Double-click its text to land here."
        : "The preview tab is not open.";
      liveSay.title = previewIsOpen() ? "It is drawn from what is in this box, unsaved changes included." : "";
    }
    const here = $("#pv-own-tab");
    if (here) here.hidden = !liveOk;
    setTimeout(alignPanes, 0);
    liveSubs.forEach(fn => { try { fn(); } catch (e) { /* the listener's own fault */ } });
  }
  function openPreviewTab() {
    if (!liveOk) return;
    let w = null;
    try { w = window.open("", LIVE.PREVIEW_WINDOW); } catch (e) { /* blocked */ }
    if (!w) { toast("The browser did not open the preview tab. Allow pop-ups for this page, then press the button again.", true); return; }
    let fresh = false;
    try { fresh = w.location.href === "about:blank"; } catch (e) { /* another origin: not ours */ }
    if (fresh) w.location.href = BASE + "/doc/" + DOC_ID + "?live=1";
    else { try { w.focus(); } catch (e) { /* the browser will not */ } }
  }
  function setOwnTab(on, open) {
    ownTab = !!on && liveOk;
    try { localStorage.setItem(OWN_KEY, ownTab ? "1" : "0"); } catch (e) { /* private mode */ }
    if (ownTab && open) openPreviewTab();       // a press is the gesture a browser wants for a new tab
    paintLive();
  }

  /* WHERE A DOUBLE-CLICK LANDS: the source's own selection and scroll.  `measureRows` is the alignment's
     (rows a source line takes, wrapped); the line is put just above the middle of the box. */
  function scrollSourceTo(line) {
    const rows = measureRows();
    const lh = alignState.lh || parseFloat(getComputedStyle(src).lineHeight) || alignState.fontPx * 1.5;
    const off = alignState.off !== null ? alignState.off : (parseFloat(getComputedStyle(src).paddingTop) || 0);
    src.scrollTop = Math.max(0, off + rows[Math.max(0, Math.min(line, rows.length - 2))] * lh - src.clientHeight * 0.35);
  }
  function jumpTo(req, fromOtherTab) {
    const hit = LIVE ? LIVE.locate(src.value, req) : null;
    if (!hit) { toast("That part of the page is not made from your text."); return false; }
    src.focus({preventScroll: true});
    src.setSelectionRange(hit.start, hit.end);
    scrollSourceTo(hit.line);
    lastCaret = hit.line;
    if (fromOtherTab) {
      toast("Landed on " + (hit.exact ? "“" + src.value.slice(hit.start, hit.end) + "”" : "the line") + ", line " + (hit.line + 1));
      document.title = "↩ line " + (hit.line + 1) + " · " + titleWas;
      clearTimeout(titleTimer);
      titleTimer = setTimeout(() => { document.title = titleWas; }, 6000);
    }
    return true;
  }
  const isControl = e => e.target.closest && e.target.closest("button, input, select, textarea, a, audio, video, summary, [contenteditable]");
  if (LIVE) sheet.addEventListener("dblclick", e => {
    if (isControl(e)) return;
    const req = LIVE.jumpRequest(sheet, e);
    if (typeof req.line !== "number" && !req.word) return;
    jumpTo(req, false);
  });

  if (channel) {
    window.name = LIVE.EDITOR_WINDOW;           // so that the preview can bring this tab forward
    channel.onmessage = e => {
      const m = e.data || {};
      if (m.from !== "preview") return;
      if (m.t === "hello" || m.t === "alive") {
        const was = previewIsOpen();
        lastPreview = Date.now();
        if (m.t === "hello") liveSend();
        if (!was) paintLive();
      } else if (m.t === "bye") {
        lastPreview = 0;
        paintLive();
      } else if (m.t === "jump") {
        lastPreview = Date.now();
        jumpTo(m, true);
      }
    };
    const caretMoved = () => {
      const line = caretLine();
      if (line !== lastCaret) { lastCaret = line; if (previewIsOpen()) post({t: "caret", line}); }
    };
    ["keyup", "mouseup", "focus"].forEach(type => src.addEventListener(type, caretMoved));
    setInterval(() => { post({t: "alive"}); paintLive(); }, 3000);
    window.addEventListener("pagehide", () => post({t: "bye"}));
    post({t: "hello-editor"});   // a preview tab that is already open asks for the text
  }
  const bind = (id, fn) => { const b = $(id); if (b) b.addEventListener("click", fn); };
  bind("#pv-own-tab", () => setOwnTab(true, true));
  bind("#editor-live-open", openPreviewTab);
  bind("#editor-live-here", () => setOwnTab(false));
  window.ParsehStudioLive = {
    available: liveOk,
    isOwnTab: () => ownTab,
    set: on => setOwnTab(!!on, !!on),
    open: openPreviewTab,
    subscribe: fn => { liveSubs.add(fn); return () => liveSubs.delete(fn); },
  };
  paintLive();

  /* ---- undo / redo -----------------------------------------------------
     An own stack: programmatic edits (paste-answer, image insert, colour
     marks) would break the browser's native one.  Rapid typing within
     700 ms collapses into one step. */
  const hist = {stack: [{v: src.value, s: 0, e: 0}], idx: 0, last: 0,
                muted: false};
  const btnUndo = $("#btn-undo"), btnRedo = $("#btn-redo");
  const snapState = () =>
    ({v: src.value, s: src.selectionStart, e: src.selectionEnd});
  function histButtons() {
    if (btnUndo) btnUndo.disabled = hist.idx <= 0;
    if (btnRedo) btnRedo.disabled = hist.idx >= hist.stack.length - 1;
  }
  function pushHistory(force) {
    if (hist.muted) return;
    const now = Date.now();
    const cur = snapState();
    if (cur.v === hist.stack[hist.idx].v) {
      hist.stack[hist.idx] = cur;
      return;
    }
    hist.stack.splice(hist.idx + 1);          // typing drops the redo branch
    if (!force && now - hist.last < 700 && hist.idx > 0) {
      hist.stack[hist.idx] = cur;             // group rapid keystrokes
    } else {
      hist.stack.push(cur);
      hist.idx++;
      if (hist.stack.length > 300) { hist.stack.shift(); hist.idx--; }
    }
    hist.last = now;
    histButtons();
  }
  function restoreHist(state) {
    hist.muted = true;
    const st = src.scrollTop;
    src.value = state.v;
    src.setSelectionRange(state.s, state.e);
    src.scrollTop = st;
    hist.muted = false;
    dirty = true;
    src.focus();
    debouncedPreview();
    histButtons();
  }
  function undo() {
    if (hist.idx > 0) { hist.idx--; hist.last = 0; restoreHist(hist.stack[hist.idx]); }
  }
  function redo() {
    if (hist.idx < hist.stack.length - 1) {
      hist.idx++; hist.last = 0; restoreHist(hist.stack[hist.idx]);
    }
  }
  if (btnUndo) btnUndo.addEventListener("click", undo);
  if (btnRedo) btnRedo.addEventListener("click", redo);
  histButtons();

  /* every programmatic replacement goes through here so it is undoable */
  function setSource(value, selStart, selEnd) {
    pushHistory(true);
    const st = src.scrollTop;
    src.value = value;
    if (selStart !== undefined)
      src.setSelectionRange(selStart, selEnd !== undefined ? selEnd : selStart);
    src.scrollTop = st;
    dirty = true;
    pushHistory(true);
    debouncedPreview();
  }

  src.addEventListener("input", () => {
    dirty = true;
    pushHistory(false);
    debouncedPreview();
  });

  let saving = false;
  const btnSave = $("#btn-save"), btnSaveView = $("#btn-save-view");
  /* How far the library's renames go in the text here (store.names_mark):
     sent with every save, which follows in the text the renames made
     elsewhere since -- another tab, an upload's names dialog -- so an editor
     left open does not put a name back that a rename took away. */
  let namesMark = document.body.dataset.namesMark || "";
  /* The text the server wrote, when it is not the text that was sent: a
     save that renamed the document rewrote its own links to itself, and
     one that followed a rename made elsewhere rewrote those (store.save);
     the next save must not put the old names back.  Taken only when
     nothing was typed meanwhile, and undoable like any edit -> whether the
     editor now holds what was written (else the renames are followed
     again at the next save, from the mark it had). */
  function takeBack(sent, written) {
    if (typeof written !== "string") written = sent;
    if (written !== sent && src.value === sent) {
      setSource(written, Math.min(src.selectionStart, written.length),
                Math.min(src.selectionEnd, written.length));
    }
    dirty = src.value !== written;
    return written === sent || src.value === written;
  }
  /* `file: false` saves the document here and leaves the file of a file opened from the computer to the caller
     (static/openfile.js's bar, which asks its own questions) -> whether the document was saved. */
  async function save(thenView, {file: toFile = true} = {}) {
    if (saving) return false;    // in-flight guard: no duplicate POST on /new
    saving = true;
    btnSave.disabled = btnSaveView.disabled = true;
    let id = DOC_ID;
    try {
      // the text as it was when Save was pressed: what goes up, and what
      // goes up again with the names the dialog is given, however long it
      // stays open (Save stays disabled meanwhile, and the text untouched)
      const sent = src.value;
      const path = id ? "/api/docs/" + id : "/api/docs", method = id ? "PUT" : "POST";
      const since = namesMark;
      let a = await send(path, {method, json: {markdown: sent, since}});
      if (nameClash(a)) {
        a = await askNames(a.data, renames =>
          send(path, {method, json: {markdown: sent, since, renames}}), {verb: "saved"});
        if (!a) {
          toast("Not saved: that name is taken — nothing was written", true);
          src.focus();
          return false;
        }
      }
      if (!a.ok) throw new Error(a.data.error || `the server answered ${a.status}`);
      if (id) {
        if (takeBack(sent, a.data.markdown) && a.data.names_mark) namesMark = a.data.names_mark;
        $(".doc-title").textContent = a.data.meta.title;
        if (!toFile) return true;
        // a file opened from the computer (static/openfile.js) is written to as well, and asks what it must
        // and says what it did; if the person called that off, the page stays: it holds what the file does not
        const file = window.ParsehFile ? await window.ParsehFile.afterSave() : null;
        toast(file ? file.said : "Saved");
        if (thenView && !(file && file.stay)) location.href = BASE + "/doc/" + id;
        return true;
      } else {
        dirty = false;
        // the direction chosen for it before it had an id is now its own
        if (chosenDir) storeDir(a.data.meta.id, chosenDir);
        location.href = thenView ? BASE + "/doc/" + a.data.meta.id
                                 : BASE + "/doc/" + a.data.meta.id + "/edit";
        return true;
      }
    } catch (e) {
      toast("Save failed: " + e.message, true);
      return false;
    } finally {
      // On success we navigate away; only re-enable if we're still here.
      saving = false;
      btnSave.disabled = btnSaveView.disabled = false;
    }
  }

  $("#btn-save").addEventListener("click", () => save(false));
  $("#btn-save-view").addEventListener("click", () => save(true));
  /* What the file bar of a file opened from the computer (static/openfile.js) asks of the editor: whether there is
     typing that not even the working copy holds, to save it (without the file, which the bar writes), and to forget
     it when the person throws it away -- so that leaving the page does not ask twice. */
  window.ParsehEditor = {dirty: () => dirty, save: opts => save(false, opts), forget: () => { dirty = false; }};
  document.addEventListener("keydown", e => {
    const mod = e.metaKey || e.ctrlKey;
    if (!mod) return;
    const k = e.key.toLowerCase();
    const inModal = e.target.closest && e.target.closest(".modal");
    if (k === "s") {
      e.preventDefault(); save(false);
    } else if (!inModal && k === "z" && !e.shiftKey) {
      e.preventDefault(); undo();      // ⌘Z (mac) / Ctrl+Z (win, linux)
    } else if (!inModal && ((k === "z" && e.shiftKey) || k === "y")) {
      e.preventDefault(); redo();      // ⇧⌘Z, Ctrl+Shift+Z, Ctrl+Y
    }
  });
  window.addEventListener("beforeunload", e => {
    if (dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  function insertAtCursor(text, cursorBack) {
    pushHistory(true);
    const [a, b] = [src.selectionStart, src.selectionEnd];
    src.setRangeText(text, a, b, "end");
    if (cursorBack) src.selectionStart = src.selectionEnd = a + text.length - cursorBack;
    src.focus();
    dirty = true;
    pushHistory(true);
    debouncedPreview();
  }
  const inserts = [["#ins-zwnj", "‌", 0], ["#ins-arrow", "→", 0],
                   ["#ins-ungram", "✗", 0], ["#ins-ok", "✅ ", 0],
                   ["#ins-guill", "«»", 1],
                   ["#ins-gloss", " = ", 0],
                   ["#ins-link", "[testo](https://)", 1],
                   ["#ins-br", "⏎", 0]];
  for (const [sel, text, back2] of inserts) {
    const b = $(sel);
    if (b) b.addEventListener("click", () => insertAtCursor(text, back2));
  }

  /* Selection-first foreground colour.  The browser owns grapheme
     boundaries; the server owns Parseh's semantic source transform and
     canonical serialisation. */
  const colourButton = $("#ins-color"), colourMenu = $("#colour-menu");
  const colourDetails = colourMenu && colourMenu.closest("details");
  const colourSwatch = colourButton && $(".colour-active", colourButton);
  let activeColour = "teal";
  function graphemeRange(text, a, b) {
    if (a === b) return [a, b];
    let starts = [0];
    if (typeof Intl !== "undefined" && Intl.Segmenter) {
      const segmenter = new Intl.Segmenter(lang().code || undefined,
                                           {granularity: "grapheme"});
      starts = [...segmenter.segment(text)].map(part => part.index);
      starts.push(text.length);
    } else {
      starts = [0];
      let at = 0, previous = "", regional = 0;
      const mark = ch => /[\u0300-\u036f\u0483-\u0489\u0591-\u05c7\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0900-\u0903\u093a-\u094f\u0981-\u0983\u09bc-\u09cd\u0a01-\u0a03\u0a3c-\u0a4d\u0a70-\u0a71\u0a81-\u0a83\u0abc-\u0acd\u0b01-\u0b03\u0b3c-\u0b4d\u0b82\u0bbe-\u0bcd\u0c00-\u0c04\u0c3e-\u0c56\u0c81-\u0c83\u0cbc-\u0ccd\u0d00-\u0d03\u0d3b-\u0d4d\u0e31\u0e34-\u0e3a\u0e47-\u0e4e\u3099-\u309a\ufe00-\ufe0f]/u.test(ch);
      const virama = ch => /[\u094d\u09cd\u0a4d\u0acd\u0b4d\u0bcd\u0c4d\u0ccd\u0d3b\u0d3c\u0d4d]/u.test(ch);
      const ri = ch => { const cp = ch.codePointAt(0); return cp >= 0x1f1e6 && cp <= 0x1f1ff; };
      for (const ch of text) {
        const size = ch.length;
        const cp = ch.codePointAt(0);
        const modifier = cp >= 0x1f3fb && cp <= 0x1f3ff;
        const joins = mark(ch) || modifier || ch === "\u200d"
          || previous === "\u200d" || virama(previous)
          || (ri(ch) && regional % 2 === 1);
        if (at && !joins) starts.push(at);
        regional = ri(ch) ? regional + 1 : 0;
        previous = ch;
        at += size;
      }
      starts.push(text.length);
    }
    let left = 0, right = text.length;
    for (const edge of starts) {
      if (edge <= a) left = edge;
      if (edge >= b) { right = edge; break; }
    }
    return [left, right];
  }
  function showActiveColour(colour) {
    if (!colourSwatch || !colour) return;
    colourSwatch.className = "colour-active";
    colourSwatch.style.background = "";
    if (colour.startsWith("#")) colourSwatch.style.background = colour;
    else colourSwatch.classList.add("fac-" + colour);
  }
  async function applyEditorColour(colour, remember = true) {
    let a = src.selectionStart, b = src.selectionEnd;
    [a, b] = graphemeRange(src.value, a, b);
    try {
      const data = await api("/api/colour-selection", {method: "POST", json: {
        markdown: src.value, start: a, end: b, color: colour || null,
      }});
      setSource(data.markdown, data.caret, data.caret);
      src.focus();
      if (remember && colour) {
        activeColour = colour;
        showActiveColour(colour);
      }
      toast(colour ? `Marked ${colour}` : "Colour removed from the selection");
    } catch (e) {
      toast(e.message || "Select text to colour", true);
      src.focus();
    } finally {
      if (colourDetails) colourDetails.open = false;
    }
  }
  if (colourButton) colourButton.addEventListener("click", () =>
    applyEditorColour(activeColour));
  if (colourMenu) colourMenu.addEventListener("click", e => {
    const choice = e.target.closest("button[data-editor-colour]");
    if (!choice) return;
    e.preventDefault();
    const colour = choice.dataset.editorColour || null;
    applyEditorColour(colour, !!colour);
  });
  const customColour = $("#editor-custom-colour");
  if (customColour) customColour.addEventListener("change", e => {
    const colour = "#" + e.target.value.slice(1).toUpperCase();
    applyEditorColour(colour);
  });
  // every entry of the Exercises menu opens a dialog over it, and a menu
  // left standing behind one is a menu whose next use closes it instead of
  // opening it -- so the menu shuts as the entry is pressed
  document.addEventListener("click", e => {
    const entry = e.target.closest(".dropdown .menu button");
    const menu = entry && entry.closest("details.dropdown");
    if (menu) menu.open = false;
  });
  const btnExercise = $("#btn-exercise");
  if (btnExercise) btnExercise.addEventListener("click", chooseExercise);
  const btnExercisePrompt = $("#btn-exercise-prompt");
  if (btnExercisePrompt) btnExercisePrompt.addEventListener("click", () =>
    exercisePrompt().catch(e => toast("Could not open exercise prompt: " + e.message, true)));
  // no deck store within reach (the studio alone beside a shelf it does not
  // know): no address, and so no entry rather than one that cannot work
  const btnExerciseDeck = $("#btn-exercise-deck");
  if (btnExerciseDeck && !decksBase) btnExerciseDeck.remove();
  else if (btnExerciseDeck) btnExerciseDeck.addEventListener("click", () =>
    loadFromDeck().catch(e => toast("Could not open the decks: " + e.message, true)));

  /* ---- footnotes ----

     A note is two separate pieces of markdown: the reference `[^id]`
     where it is called, and the definition `[^id]: …` further down.
     Writing them by hand means keeping the ids in step and, if the
     definitions are to read in the order the reader meets them, putting
     each new one in the right place among the others.  The dialog does
     both from one form. */

  const FN_DEF_RE = /^\[\^([^\[\]\s]+)\]:/;

  /** Every definition block in `lines`: the `[^id]:` line plus any
      indented continuation lines that belong to it. */
  function footnoteDefs(lines) {
    const out = [];
    for (let i = 0; i < lines.length; i++) {
      const m = lines[i].match(FN_DEF_RE);
      if (!m) continue;
      let j = i + 1;
      while (j < lines.length && /^\s+\S/.test(lines[j])) j++;
      out.push({id: m[1], from: i, to: j});
      i = j - 1;
    }
    return out;
  }

  /** The ids in the order the reader first meets them in the body. */
  function footnoteRefOrder(lines) {
    const order = [];
    for (const l of lines) {
      if (FN_DEF_RE.test(l)) continue;          // a definition, not a call
      for (const m of l.matchAll(/\[\^([^\[\]\s]+)\]/g))
        if (!order.includes(m[1])) order.push(m[1]);
    }
    return order;
  }

  /** Splice `[^id]: content` into `text` so the definitions stay in the
      same order as the references that call them. */
  function placeFootnoteDef(text, id, content) {
    const lines = text.split("\n");
    const defs = footnoteDefs(lines);
    const order = footnoteRefOrder(lines);
    const rank = x => {
      const i = order.indexOf(x);
      return i === -1 ? Number.MAX_SAFE_INTEGER : i;   // never called: last
    };
    const line = `[^${id}]: ${content}`.trimEnd();
    const mine = rank(id);

    const after = defs.find(d => rank(d.id) > mine);
    if (after) {                       // before the first later-called note
      lines.splice(after.from, 0, line);
    } else if (defs.length) {          // after the last definition
      lines.splice(defs[defs.length - 1].to, 0, line);
    } else {                           // the document's first note
      while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
      lines.push("", line);
    }
    return lines.join("\n");
  }

  const btnNote = $("#ins-note");
  if (btnNote) btnNote.addEventListener("click", () => {
    const taken = new Set(footnoteDefs(src.value.split("\n")).map(d => d.id));
    let auto = 1;
    while (taken.has("n" + auto)) auto++;

    showModal({
      title: "Footnote",
      hint: "The reference goes in at the cursor; the note itself is placed "
          + "with the others, in the order the reader meets them.",
      value: "",
      okLabel: "Insert note",
      fields: [{key: "name", label: "Name", value: "",
                placeholder: `optional — “n${auto}” if you leave it empty`}],
      onOk: async (content, close, fields) => {
        const body = (content || "").trim();
        if (!body) throw new Error("the note has no text");
        let id = (fields.name || "").trim()
                   .replace(/\s+/g, "-").replace(/[\[\]^:]/g, "");
        if (!id) id = "n" + auto;
        if (taken.has(id))
          throw new Error(`there is already a note called “${id}”`);

        const a = src.selectionStart, b = src.selectionEnd;
        const ref = `[^${id}]`;
        const withRef = src.value.slice(0, a) + ref + src.value.slice(b);
        setSource(placeFootnoteDef(withRef, id, body), a + ref.length);
        src.focus();
        close();
        toast(`Note “${id}” inserted`);
      },
    });
  });

  /* tl button: with a selection, wrap it in [ … ]{tl} — multiline form
     when the selection spans lines; without one, insert an empty mark.
     `{tl}` is the generic marker; the Persian `{fa}` stays readable. */
  const insTl = $("#ins-tl");
  if (insTl) insTl.addEventListener("click", () => {
    const a = src.selectionStart, b = src.selectionEnd;
    if (a === b) { insertAtCursor("[]{tl}", 5); return; }
    const clean = src.value.slice(a, b).replace(/[\[\]]/g, "");
    const wrapped = clean.includes("\n")
      ? "[\n" + clean.replace(/^\n+|\n+$/g, "") + "\n]{tl}"
      : "[" + clean + "]{tl}";
    pushHistory(true);
    src.setRangeText(wrapped, a, b, "end");
    src.focus();
    dirty = true;
    pushHistory(true);
    debouncedPreview();
  });

  /* math button: wrap the selection in [ … ]{math}.  Brackets are NOT
     stripped as the tl button strips them -- an interval [0,1] and a
     \sqrt[3]{x} are ordinary mathematics, and MATH_RE reads its body up to
     the `]{math}` that ends it, so they survive. */
  const insMath = $("#ins-math");
  if (insMath) insMath.addEventListener("click", () => {
    const a = src.selectionStart, b = src.selectionEnd;
    if (a === b) { insertAtCursor("[]{math}", 7); return; }
    pushHistory(true);
    src.setRangeText("[" + src.value.slice(a, b) + "]{math}", a, b, "end");
    src.focus();
    dirty = true;
    pushHistory(true);
    debouncedPreview();
  });

  /* kana button (reading languages): wrap the selection as [ … ]{kana:}
     with the caret before the closing brace, ready for the reading;
     without a selection the caret lands inside the brackets */
  const insKana = $("#ins-kana");
  if (insKana) insKana.addEventListener("click", () => {
    const a = src.selectionStart, b = src.selectionEnd;
    if (a === b) { insertAtCursor("[]{kana:}", 8); return; }
    const clean = src.value.slice(a, b).replace(/[\[\]\n]/g, "");
    pushHistory(true);
    src.setRangeText("[" + clean + "]{kana:}", a, b, "end");
    src.selectionStart = src.selectionEnd = src.selectionEnd - 1;
    src.focus();
    dirty = true;
    pushHistory(true);
    debouncedPreview();
  });

  /* la button: wrap the selection (or an empty mark) in [ … ]{la} —
     the Latin mirror of rtl; content keeps its markdown untouched */
  const insLa = $("#ins-la");
  if (insLa) insLa.addEventListener("click", () => {
    const a = src.selectionStart, b = src.selectionEnd;
    if (a === b) { insertAtCursor("[]{la}", 5); return; }
    const sel = src.value.slice(a, b);
    const wrapped = sel.includes("\n")
      ? "[\n" + sel.replace(/^\n+|\n+$/g, "") + "\n]{la}"
      : "[" + sel + "]{la}";
    pushHistory(true);
    src.setRangeText(wrapped, a, b, "end");
    src.focus();
    dirty = true;
    pushHistory(true);
    debouncedPreview();
  });

  /* Tidying one line of the target-text overlay.  `trim()` and `\s` take
     U+3000, the ideographic space, for blank space; in a language without
     a word separator that space is an indent the writer meant (the first
     line of a Japanese verse), so there only ASCII whitespace is trimmed
     and nothing inside the line is collapsed.  (The store's rewriter
     must keep the same rule, or the indent is lost on the server.) */
  function tidyTlLine(s, collapse) {
    if (lang().word_sep === "") return s.replace(/^[ \t]+|[ \t]+$/g, "");
    if (collapse) s = s.replace(/\s+/g, " ");
    return s.trim();
  }

  /* the target-text overlay: a big box in the document's direction and
     face for comfortable typing; every line of the box becomes a real
     line (⏎ in markdown).  Font is offered only when the language has an
     alternate face, Vertical (with a column height) only when it can be
     set vertically; the result is a [ … ]{tl …} block. */
  function openTlOverlay(opts) {
    const L = lang();
    const altKey = (L.fonts || {}).alt_key;
    const root = $("#modal-root");
    root.innerHTML = "";
    const ov = document.createElement("div");
    ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal rtl-modal" data-lang="${escAttr(L.code)}">
      <h3></h3>
      <p>Every line of the box becomes a real line (a ⏎ in the markdown).
      Square brackets are not allowed inside and will be removed.</p>
      <textarea class="rtlbox" dir="${escAttr(L.dir)}" lang="${escAttr(L.code)}" rows="8" spellcheck="false"></textarea>
      <div class="row rtl-opts">
        <label ${altKey ? "" : "hidden"}>Font
          <select data-k="font">
            <option value="">${escAttr(L.name)} (default)</option>
            ${altKey ? `<option value="${escAttr(altKey)}">${escAttr(altKey)}</option>` : ""}
          </select></label>
        <label>Background
          <select data-k="bg">
            <option value="">none (default)</option>
            <option value="quote">quote</option>
            <option value="sand">sand</option>
            <option value="rose">rose</option>
            <option value="sage">sage</option>
            <option value="lilac">lilac</option>
          </select></label>
        <label ${L.vertical ? "" : "hidden"} title="Columns top-to-bottom, progressing right-to-left (tategaki)">
          <input type="checkbox" data-k="vertical"> vertical</label>
        <label ${L.vertical ? "" : "hidden"} title="Column height, in em (8–60)">height
          <input type="number" data-k="height" min="8" max="60" step="1" value="22"></label>
      </div>
      <div class="row">
        <button class="btn" data-x="cancel">Cancel</button>
        <button class="btn primary" data-x="ok"></button>
      </div></div>`;
    $("h3", ov).textContent = opts.title;
    $('[data-x="ok"]', ov).textContent = opts.okLabel || "Insert";
    const ta = $("textarea", ov);
    ta.value = (opts.lines || []).join("\n");
    const selFont = $('[data-k="font"]', ov), selBg = $('[data-k="bg"]', ov);
    const ckVert = $('[data-k="vertical"]', ov), inHeight = $('[data-k="height"]', ov);
    selFont.value = altKey && opts.font === altKey ? altKey : "";
    selBg.value = opts.bg || "";
    ckVert.checked = !!(L.vertical && opts.vertical);
    if (opts.height) inHeight.value = opts.height;
    const applyBoxStyle = () => {
      ta.classList.toggle("alt", !!selFont.value);
      ta.style.background = selBg.value
        ? `var(--rtlbg-${selBg.value})` : "";
    };
    selFont.addEventListener("change", applyBoxStyle);
    selBg.addEventListener("change", applyBoxStyle);
    applyBoxStyle();
    const close = () => { if (ov.parentNode) root.removeChild(ov); };
    ov.addEventListener("click", e => { if (e.target === ov) close(); });
    $('[data-x="cancel"]', ov).addEventListener("click", close);
    let busy = false;
    $('[data-x="ok"]', ov).addEventListener("click", async () => {
      if (busy) return;
      const lines = ta.value.split("\n")
        .map(l => tidyTlLine(l.replace(/[\[\]]/g, ""))).filter(Boolean);
      if (!lines.length) { toast("The block cannot be empty", true); return; }
      const height = Math.max(8, Math.min(60, parseInt(inHeight.value, 10) || 22));
      busy = true;
      try {
        await opts.onSave(lines,
                          {font: selFont.value, bg: selBg.value,
                           vertical: L.vertical && ckVert.checked,
                           height}, close);
      } catch (e) {
        toast(e.message, true);
        busy = false;
      }
    });
    root.appendChild(ov);
    ta.focus();
  }

  /* the marker the overlay writes: `{tl …}` for every language (the
     store's _tl_marker is the server twin) */
  function tlMarker(style) {
    const parts = ["tl"];
    if (style.font) parts.push("font=" + style.font);
    if (style.bg) parts.push("bg=" + style.bg);
    if (style.vertical) {
      parts.push("vertical");
      if (style.height && style.height !== 22) parts.push("height=" + style.height);
    }
    return "{" + parts.join(" ") + "}";
  }

  const btnMathEditor = $("#btn-math-editor");
  if (btnMathEditor) btnMathEditor.addEventListener("click", () => {
    // a selection is taken as the formula to start from, which is how the
    // tl editor behaves and what somebody who has just typed one expects
    const a = src.selectionStart, b = src.selectionEnd;
    const picked = a === b ? "" : src.value.slice(a, b).trim();
    openMathOverlay({
      backTo: src,
      tex: picked,
      display: picked.includes("\n"),
      onSave: (tex, block) => {
        if (block) insertStandaloneLine(mathMarkup(tex, true));
        else if (a === b) insertAtCursor(mathMarkup(tex, false));
        else {
          pushHistory(true);
          src.setRangeText(mathMarkup(tex, false), a, b, "end");
          dirty = true;
          pushHistory(true);
          debouncedPreview();
        }
      },
    });
  });

  const btnLatexEditor = $("#btn-latex-editor");
  if (btnLatexEditor) btnLatexEditor.addEventListener("click", () => {
    openLatexOverlay({backTo: src, onSave: text => insertStandaloneLine(text)});
  });
  /* ✎ on a drawing in the preview reopens its block in the sheet, and the
     edit goes back over the lines it came from (the fence to its `::::`).
     The button is the RTL pencil's (sheet.css keeps it `display: none`, so it
     is shown and hidden through `display`, as bindTlEditCloud does: setting
     `hidden` never showed it, and nothing ever hid it again), and it is put
     where the drawing is on the screen -- so a scroll of the preview hides
     it rather than leave it hanging where the drawing was. */
  (function bindLatexPencil() {
    let btn = null, target = null, hideTimer = null;
    const hide = () => { clearTimeout(hideTimer); if (btn) btn.style.display = "none"; target = null; };
    const scheduleHide = () => { clearTimeout(hideTimer); hideTimer = setTimeout(hide, 260); };
    function reopen(el) {
      const at = +el.dataset.srcLine;
      const lines = src.value.split("\n");
      let end = at + 1;
      while (end < lines.length && lines[end].trim() !== "::::") end++;
      const w = el.dataset.width ? +el.dataset.width : null;
      openLatexOverlay({backTo: src, okLabel: "Save", tex: el.dataset.latexSrc,
                        theme: el.dataset.latexTheme,
                        layout: {width: w, align: el.dataset.align || "center",
                                 offset: +el.dataset.offset || 0,
                                 caption: el.dataset.latexCaption || ""},
                        onSave: text => {
                          pushHistory(true);
                          const cur = src.value.split("\n");
                          cur.splice(at, Math.min(end, cur.length - 1) - at + 1, ...text.split("\n"));
                          src.value = cur.join("\n");
                          dirty = true;
                          pushHistory(true);
                          debouncedPreview();
                        }});
    }
    function build() {
      btn = document.createElement("button");
      btn.type = "button"; btn.className = "rtl-edit-btn"; btn.textContent = "✎";
      btn.title = "Edit this drawing";
      btn.addEventListener("mouseenter", () => clearTimeout(hideTimer));
      btn.addEventListener("mouseleave", scheduleHide);
      btn.addEventListener("click", () => { const el = target; hide(); if (el) reopen(el); });
      document.body.appendChild(btn);
    }
    function show(el) {
      if (!btn) build();
      clearTimeout(hideTimer);
      target = el;
      btn.style.display = "block";
      btn.style.position = "fixed";
      const r = el.getBoundingClientRect();
      btn.style.top = Math.max(4, r.top + 4) + "px";
      btn.style.left = Math.max(4, r.right - btn.offsetWidth - 4) + "px";
    }
    const drawing = e => e.target.closest && e.target.closest("[data-latex-src][data-src-line]");
    sheet.addEventListener("mouseover", e => { const el = drawing(e); if (el) show(el); });
    sheet.addEventListener("mouseout", e => { if (drawing(e)) scheduleHide(); });
    window.addEventListener("scroll", hide, true);
  })();

  const btnTlEditor = $("#btn-tl-editor");
  if (btnTlEditor) btnTlEditor.addEventListener("click", () => {
    openTlOverlay({
      title: lang().name + " text", okLabel: "Insert", lines: [],
      onSave: (lines, style, close) => {
        const marker = tlMarker(style);
        if (lines.length === 1 && !style.vertical) {
          insertAtCursor(`[${lines[0]}]` + marker, 0);
        } else {
          insertStandaloneLine("[\n" + lines.join("⏎\n") + "\n]" + marker);
        }
        close();
      },
    });
  });

  /* hovering a rendered block in the preview offers ✎ — it reopens the
     block in the overlay and writes the edit back into the buffer */
  (function bindTlEditCloud(container) {
    let btn = null, target = null, hideTimer = null;
    function build() {
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rtl-edit-btn";
      btn.title = "Edit this block in the overlay editor";
      btn.addEventListener("mouseenter", () => clearTimeout(hideTimer));
      btn.addEventListener("mouseleave", scheduleHide);
      btn.addEventListener("click", () => {
        const el = target;
        hide();
        openFor(el);
      });
      document.body.appendChild(btn);
    }
    function show(el) {
      if (!btn) build();
      target = el;
      btn.textContent = "✎ " + lang().code;   // the buffer's language, live
      btn.style.display = "block";
      const r = el.getBoundingClientRect();
      btn.style.top = Math.max(4, r.top + window.scrollY - 24) + "px";
      btn.style.left = Math.max(4,
        r.right + window.scrollX - btn.offsetWidth) + "px";
    }
    function hide() { if (btn) btn.style.display = "none"; target = null; }
    function scheduleHide() { hideTimer = setTimeout(hide, 260); }
    container.addEventListener("mouseover", e => {
      const el = e.target.closest("[data-tl-src]");
      if (el && container.contains(el)) { clearTimeout(hideTimer); show(el); }
    });
    container.addEventListener("mouseout", e => {
      if (e.target.closest("[data-tl-src]")) scheduleHide();
    });
    window.addEventListener("scroll", hide, {passive: true});

    function openFor(el) {
      const kind = el.dataset.tlKind, content = el.dataset.tlSrc;
      // which of the blocks with this text it is, as the source counts
      // them: the page draws an exercise out of the source's order, and
      // numbers each block in the source's (htmlgen, data-tl-occ)
      const occ = el.dataset.tlOcc !== undefined ? Number(el.dataset.tlOcc)
        : Math.max(0, $$('[data-tl-kind="' + kind + '"]', container)
            .filter(x => x.dataset.tlSrc === content).indexOf(el));
      const lines = content.split(lang().word_sep === "" ? /[ \t]*⏎[ \t]*/ : /\s*⏎\s*/)
        .map(s => tidyTlLine(s, true)).filter(Boolean);
      openTlOverlay({
        title: "Edit " + lang().name + " block", okLabel: "Save", lines,
        font: el.dataset.tlFont || "",
        bg: el.dataset.tlBg || "",
        vertical: el.dataset.tlVertical === "1",
        height: parseInt(el.dataset.tlHeight, 10) || 22,
        onSave: async (newLines, style, close) => {
          const data = await api("/api/tl-edit", {method: "POST",
            json: {markdown: src.value, kind, content,
                   occurrence: occ, lines: newLines,
                   font: style.font, bg: style.bg,
                   vertical: style.vertical, height: style.height}});
          setSource(data.markdown);
          close();
          preview();
        },
      });
    }
  })(sheet);

  /* Importing a whole document — "Paste LLM answer", "Load .md" — belongs
     to the library page, which is where a document is started.  Inside
     the editor both replaced everything already typed, which is not an
     edit but an accident waiting to happen. */

  /* layout panels over the preview: same interactive tools as the
     reading view, but they rewrite the (possibly unsaved) buffer via
     the pure endpoints.  The preview DOM is already updated live by the
     panel itself, so the buffer is patched quietly — no re-render, no
     lost panel — and only the alignment map is refreshed. */
  function setSourceQuiet(value) {
    pushHistory(true);
    const st = src.scrollTop;
    src.value = value;
    src.scrollTop = st;
    dirty = true;
    pushHistory(true);
    histButtons();
  }
  panelClosers.push(bindImageLayout(sheet, {save: async payload => {
    const data = await api("/api/image-layout",
                           {method: "POST",
                            json: Object.assign({markdown: src.value},
                                                payload)});
    setSourceQuiet(data.markdown);
    setTimeout(alignPanes, 0);
  }}).close);
  panelClosers.push(bindLaLayout(sheet, {save: async payload => {
    const data = await api("/api/la-layout",
                           {method: "POST",
                            json: Object.assign({markdown: src.value},
                                                payload)});
    setSourceQuiet(data.markdown);
    setTimeout(alignPanes, 0);
  }}).close);

  /* The preview cloud edits linguistic annotations only.  Foreground
     colour is a source-selection command in the toolbar below. */
  bindWordCloud(sheet, {
    applyTranslit: async body => {
      const data = await api("/api/translit",
                             {method: "POST",
                              json: Object.assign({markdown: src.value}, body)});
      setSource(data.markdown);
      preview();
    },
    applyKana: async body => {
      const data = await api("/api/kana",
                             {method: "POST",
                              json: Object.assign({markdown: src.value}, body)});
      setSource(data.markdown);
      preview();
    },
  });

  /* ---- images: upload, insert, manage ---- */

  // The embed put in last, while its placeholder is still selected.  Another
  // embed arriving then -- the next of several files uploaded or dropped at
  // once -- goes in on the line after it, not over the word inside it.
  let lastEmbed = null;
  /* A page nobody has clicked into has its cursor at the very first character, which is the front matter's opening
     line.  An embed put there stands above the `---` and the page is then no language at all (the preview falls back to
     the first the toolbox has), so wherever a cursor is inside or before the matter, an embed goes below it. */
  function belowFrontMatter() {
    const m = /^---[ \t]*\n[\s\S]*?\n---[ \t]*(?:\n|$)/.exec(src.value);
    const end = m ? m[0].length : 0;
    if (src.selectionStart < end) src.setSelectionRange(end, end);
  }
  function insertStandaloneLine(line, selectWord, prepare) {
    // the dialect wants embeds on a line of their own
    pushHistory(true);
    // `prepare`: what is to be done to the source in the same undoable step (taking exercises off the page)
    if (prepare) prepare();
    const last = lastEmbed;
    lastEmbed = null;
    if (last && src.selectionStart === last.word[0] && src.selectionEnd === last.word[1]
        && src.value.slice(last.from, last.to) === last.line)
      src.setSelectionRange(last.to, last.to);
    belowFrontMatter();
    const a = src.selectionStart;
    const before = src.value.slice(0, a), after = src.value.slice(src.selectionEnd);
    const pre = before && !before.endsWith("\n\n")
      ? (before.endsWith("\n") ? "\n" : "\n\n") : "";
    // the same blank line on the way out: an embed pushed straight up
    // against the next heading parses, but it is not what anyone writes
    const post = !after ? ""
      : after.startsWith("\n\n") ? ""
      : after.startsWith("\n") ? "\n" : "\n\n";
    src.setRangeText(pre + line + post, a, src.selectionEnd, "end");
    if (selectWord) {
      // leave the placeholder selected so typing replaces it
      const p = line.indexOf(selectWord);
      if (p >= 0) {
        const s = a + pre.length + p;
        src.setSelectionRange(s, s + selectWord.length);
        lastEmbed = {line, from: a + pre.length, to: a + pre.length + line.length,
                     word: [s, s + selectWord.length]};
      }
    }
    src.focus();
    dirty = true;
    pushHistory(true);
    debouncedPreview();
  }

  const insertImageLine = path =>
    insertStandaloneLine(`![didascalia](${path})`, "didascalia");
  // a recording is written as a picture is, its path under audio/
  const insertAudioLine = insertImageLine;

  /* ---- the clip tray ----

     A recording cut in a book or a video, or a frame captured from a film,
     waits in the toolbox's clip tray under a name unique across it, and
     `audio/<name>` or `images/<name>` pasted anywhere names that one file.
     The document has no copy of it until the server brings one in
     (POST …/adopt): a saved document does so on every save, and the editor
     asks at once for what was just pasted or added, so the preview plays
     it before anything is saved. */
  const MEDIA_REF_RE = /(?<![A-Za-z0-9._\/\-])(?:images|audio)\/[A-Za-z0-9][A-Za-z0-9._\-]*/;
  async function adoptFromTray(markdown) {
    if (!DOC_ID || !MEDIA_REF_RE.test(markdown)) return null;
    const data = await api(`/api/docs/${DOC_ID}/adopt`, {method: "POST", json: {markdown}});
    const n = (data.adopted || []).length;
    if (n) {
      toast(`Brought ${n} file${n === 1 ? "" : "s"} from the clip tray`);
      preview();
    }
    return data;
  }

  /* ---- pasting a figure ----

     A figure on the clipboard arrives as bytes with no useful name — a
     screenshot is "image.png" at best — so ask what to call it, store it
     in the document's own images/ folder, and put the embed back where
     the cursor was.  The cursor has to be remembered before the dialog
     opens, because opening it takes the focus out of the textarea. */

  const FIGURE_TYPE = /^(?:image\/(?:png|jpeg|svg\+xml)|application\/pdf)$/;
  const FIGURE_KIND = {"image/png": "PNG", "image/jpeg": "JPEG",
                       "image/svg+xml": "SVG", "application/pdf": "PDF"};

  function clipboardFigure(cd) {
    const named = [...(cd.files || [])].find(f => FIGURE_TYPE.test(f.type));
    if (named) return named;
    const item = [...(cd.items || [])]
      .find(i => i.kind === "file" && FIGURE_TYPE.test(i.type));
    return item ? item.getAsFile() : null;
  }

  src.addEventListener("paste", e => {
    const cd = e.clipboardData;
    if (!cd) return;
    let file = clipboardFigure(cd);
    let svgText = null;
    if (!file) {
      // SVG often travels as markup rather than as a file
      const text = cd.getData("text/plain") || "";
      if (/^\s*(?:<\?xml[^>]*\?>\s*)?<svg[\s>]/i.test(text)) {
        svgText = text;
        file = new File([text], "figure.svg", {type: "image/svg+xml"});
      }
    }
    if (!file) {
      // ordinary paste: left to the browser -- and what it names from the
      // clip tray brought into the document
      adoptFromTray(cd.getData("text/plain") || "")
        .catch(err => toast("Could not bring the clips in: " + err.message, true));
      return;
    }
    e.preventDefault();

    if (!DOC_ID) {
      // fall back to the plain paste rather than losing what was copied
      if (svgText) insertAtCursor(svgText);
      toast("Save the document first — figures live in its own folder", true);
      return;
    }

    const at = src.selectionStart, to = src.selectionEnd;
    const stem = (file.name || "").replace(/\.[^.]*$/, "").trim();
    const kind = FIGURE_KIND[file.type] || "figure";

    showModal({
      title: `Paste ${kind} figure`,
      hint: `${Math.max(1, Math.round(file.size / 1024))} kB. It is saved in `
          + "this document's images/ folder and embedded where the cursor "
          + "was; the extension follows the file's actual type.",
      textarea: false,
      okLabel: "Save and insert",
      onCancel: () => {
        // the browser's own paste was suppressed to open this; if the
        // clipboard held SVG markup rather than a file, give it back
        if (!svgText) return;
        src.focus();
        src.setSelectionRange(at, to);
        insertAtCursor(svgText);
      },
      fields: [
        {key: "name", label: "File name", value: stem && stem !== "image" ? stem : "",
         placeholder: "figure"},
        {key: "caption", label: "Caption (optional)", value: "",
         placeholder: "shown under the figure"},
      ],
      onOk: async (_ignored, close, f) => {
        const name = (f.name || "").trim() || "figure";
        const data = await uploadImage(DOC_ID, file, name);
        close();
        // put the caret back where the paste happened before inserting
        src.focus();
        src.setSelectionRange(at, to);
        const cap = (f.caption || "").trim();
        if (cap) insertStandaloneLine(`![${cap}](${data.path})`);
        else insertImageLine(data.path);
        toast(`Saved as ${data.name}`);
      },
    });
  });

  const btnVideo = $("#btn-video");
  if (btnVideo) btnVideo.addEventListener("click", () => {
    const url = prompt(
      "YouTube URL (watch / youtu.be / shorts link, or the 11-char ID).\n" +
      "The whole video is embedded; optional clip times and the layout\n" +
      "can be set at any moment by clicking ⚙ on the embedded player.");
    if (!url || !url.trim()) return;
    insertStandaloneLine(`@[didascalia](${url.trim()})`, "didascalia");
  });

  /* Link to another document.  What goes into the markdown is the
     target's NAME -- its title, as its front matter spells it -- which a
     person can read and which the studio keeps pointing at the same
     document: a rename rewrites every link to it.  The shown text is
     optional and, left empty, the target's current title is displayed. */
  const btnDocLink = $("#btn-doclink");
  if (btnDocLink) btnDocLink.addEventListener("click", async () => {
    let docs = [];
    try {
      docs = (await api("/api/docs")).docs || [];
    } catch (e) {
      return toast("Could not read the library: " + e.message, true);
    }
    // linking a document to itself is never what is meant
    docs = docs.filter(d => d.title && d.id !== DOC_ID);
    if (!docs.length)
      return toast("No other document in the library to link to");

    const selected = src.value.slice(src.selectionStart, src.selectionEnd);
    const root = $("#modal-root");
    root.innerHTML = "";
    const ov = document.createElement("div");
    ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal dl-modal" role="dialog" aria-modal="true">
      <h3>Link to another document</h3>
      <p>The link names the document by its title; renaming it rewrites
         every link to it, so it keeps working. Leave the shown text empty
         to display that document's current title.</p>
      <input class="dl-filter" type="search" placeholder="Filter by title or tag"
             autocomplete="off" spellcheck="false">
      <div class="dl-list"></div>
      <label class="dl-textrow">Shown text
        <input class="dl-text" type="text" spellcheck="false"
               placeholder="(empty — use the linked document's title)"></label>
      <div class="row">
        <button class="btn" data-x="cancel">Cancel</button>
        <button class="btn primary" data-x="ok" disabled>Insert link</button>
      </div></div>`;

    const list = $(".dl-list", ov), filter = $(".dl-filter", ov);
    const textIn = $(".dl-text", ov), okBtn = $('[data-x="ok"]', ov);
    let chosen = null;
    textIn.value = selected.trim();

    function draw() {
      // titles and tags are the target's own words: "İstanbul Rehberi"
      // must answer to "istanbul", and the tag "italyanca" to the
      // "İtalyanca" its language spells it with (the fold store.py
      // searches the library by, so the two lists narrow alike)
      const q = foldCase(filter.value.trim());
      const rows = docs.filter(d => !q
        || foldCase(d.title).includes(q)
        || (d.tags || []).some(t => foldCase(t).includes(q)));
      if (!rows.length) {
        list.innerHTML = `<div class="dl-empty">Nothing matches.</div>`;
        return;
      }
      list.innerHTML = rows.map(d => `
        <button type="button" class="dl-item${chosen && d.id === chosen.id ? " on" : ""}"
                data-id="${escAttr(d.id)}">
          <span class="dl-t">${escAttr(d.title || d.id)}</span>
          <span class="dl-s">${escAttr(d.subtitle || "")}</span>
        </button>`).join("");
      $$(".dl-item", list).forEach(b => b.addEventListener("click", () => {
        chosen = docs.find(d => d.id === b.dataset.id) || null;
        okBtn.disabled = false;
        draw();
      }));
    }
    filter.addEventListener("input", draw);
    draw();

    const close = () => { if (ov.parentNode) root.removeChild(ov); };
    ov.addEventListener("click", e => { if (e.target === ov) close(); });
    $('[data-x="cancel"]', ov).addEventListener("click", close);
    okBtn.addEventListener("click", () => {
      if (!chosen) return;
      const label = textIn.value.trim();
      close();
      // replaces the selection when the button was used on one.  A name
      // holding "|" -- only one from before names were checked can -- would
      // split a table's cell: that document is linked by its uid, which
      // reaches it as well (and which the next start writes by name, once
      // it has one without)
      const target = chosen.title.includes("|") && chosen.uid ? chosen.uid
        : escapeDocName(chosen.title);
      insertAtCursor(`[${label}](doc:${target})`);
      toast(label ? "Link inserted" : "Link inserted — shows the target's title");
    });
    root.appendChild(ov);
    filter.focus();
  });

  async function handleImageFiles(files) {
    if (!DOC_ID) {
      toast("Save the document first — images are stored in its folder", true);
      return;
    }
    for (const f of files) {
      try {
        const data = await uploadImage(DOC_ID, f);
        insertImageLine(data.path);
        toast("Uploaded " + data.name);
      } catch (e) {
        toast(`${f.name}: ${e.message}`, true);
      }
    }
  }

  async function handleAudioFiles(files) {
    if (!DOC_ID) {
      toast("Save the document first — recordings are stored in its folder", true);
      return;
    }
    for (const f of files) {
      try {
        const data = await uploadAudio(DOC_ID, f);
        insertAudioLine(data.path);
        toast("Uploaded " + data.name);
      } catch (e) {
        toast(`${f.name}: ${e.message}`, true);
      }
    }
  }

  const imgUpload = $("#img-upload");
  if (imgUpload) imgUpload.addEventListener("change", e => {
    handleImageFiles([...e.target.files]);
    e.target.value = "";
  });
  const audioUpload = $("#audio-upload");
  if (audioUpload) audioUpload.addEventListener("change", e => {
    handleAudioFiles([...e.target.files]);
    e.target.value = "";
  });

  /* A file dropped on the page is never opened in place of it, which would
     leave the editor and whatever was not saved.  On the editor a picture
     or a recording is stored and embedded; anywhere else nothing happens. */
  const draggingFiles = e => !!e.dataTransfer && [...e.dataTransfer.types].includes("Files");
  const isFigureFile = f => /^image\/(png|jpeg|svg\+xml)$/.test(f.type)
    || f.type === "application/pdf" || /\.pdf$/i.test(f.name);
  const isAudioFile = f => /^audio\//.test(f.type) || AUDIO_NAME_RE.test(f.name);
  window.addEventListener("dragover", e => {
    if (!draggingFiles(e) || e.defaultPrevented) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "none";
  });
  window.addEventListener("drop", e => {
    if (draggingFiles(e)) e.preventDefault();
  });
  const editorPane = $(".editor-pane");
  if (editorPane) {
    editorPane.addEventListener("dragover", e => {
      if (draggingFiles(e)) {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        editorPane.classList.add("dragover");
      }
    });
    editorPane.addEventListener("dragleave", () =>
      editorPane.classList.remove("dragover"));
    editorPane.addEventListener("drop", async e => {
      if (!draggingFiles(e)) return;
      e.preventDefault();
      editorPane.classList.remove("dragover");
      const files = [...e.dataTransfer.files];
      const refused = files.filter(f => !isFigureFile(f) && !isAudioFile(f));
      if (refused.length)
        toast(`${refused.map(f => f.name).join(", ")}: only pictures (PNG, JPEG, SVG, PDF) `
              + `and recordings (${audioUpload.dataset.formats}) go into a document`, true);
      // in the order dropped, one line after another from the cursor
      for (const f of files) {
        if (isFigureFile(f)) await handleImageFiles([f]);
        else if (isAudioFile(f)) await handleAudioFiles([f]);
      }
    });
  }

  const btnImages = $("#btn-images");
  if (btnImages) btnImages.addEventListener("click", async () => {
    if (!DOC_ID) {
      toast("Save the document first — images are stored in its folder", true);
      return;
    }
    const root = $("#modal-root");
    root.innerHTML = "";
    const ov = document.createElement("div");
    ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal"><h3>Images of this document</h3>
      <p>Click one to insert it at the cursor; ✕ deletes the file.</p>
      <div class="imggrid"></div>
      <div class="row"><button class="btn" data-x="close">Close</button></div></div>`;
    const closeM = () => { if (ov.parentNode) root.removeChild(ov); };
    ov.addEventListener("click", e => { if (e.target === ov) closeM(); });
    $('[data-x="close"]', ov).addEventListener("click", closeM);
    root.appendChild(ov);
    const grid = $(".imggrid", ov);

    async function refresh() {
      const data = await api(`/api/docs/${DOC_ID}/images`);
      grid.innerHTML = "";
      if (!data.images.length) {
        grid.innerHTML = '<p class="hint">No figures uploaded yet — use the Image button, or drag a PNG, JPEG, SVG or PDF into the editor.</p>';
        return;
      }
      for (const im of data.images) {
        const cell = document.createElement("div");
        cell.className = "imgcell";
        cell.innerHTML = `<img loading="lazy"><div class="nm"></div>
          ${im.referenced ? '<span class="ref">in use</span>' : ""}
          <button class="del" title="Delete file">✕</button>`;
        $("img", cell).src = `${BASE}/media/${DOC_ID}/images/${im.name}`;
        $(".nm", cell).textContent =
          `${im.name} · ${Math.round(im.size / 1024)} kB`;
        cell.addEventListener("click", e => {
          if (e.target.closest(".del")) return;
          insertImageLine("images/" + im.name);
          closeM();
        });
        $(".del", cell).addEventListener("click", async () => {
          const warn = im.referenced
            ? `“${im.name}” is used by the document — the embed will break. Delete anyway?`
            : `Delete “${im.name}”?`;
          if (!confirm(warn)) return;
          await api(`/api/docs/${DOC_ID}/images/${im.name}`,
                    {method: "DELETE"});
          // the preview shows it gone at once, as the warning said
          mediaChanged("images/" + im.name);
          preview();
          refresh();
        });
        grid.appendChild(cell);
      }
    }
    refresh().catch(e => toast(e.message, true));
  });

  /* ---- pictograms (ARASAAC): looked for and seen in a frame, added as the figure they are ----

     The button opens lib/pictograms.js over the page.  What is chosen is fetched as the bytes it is and put into
     this document's own images/ by the same upload as any picture (so the copy is the document's, named
     arasaac-<number>.png, and the same bytes are stored once); the line that goes in is a figure on a line of its
     own, its caption the word and its size the one a pictogram wants (docs/arasaac.md, 5.5).  The licence asks
     for a credit that travels with the document, so the first time one is added the last paragraph becomes
     ARASAAC's own words -- once, never twice, and only the person takes it out. */
  const CREDIT_MARK = /Pictograms author: Sergio Palao/;
  async function ensureArasaacCredit() {
    let credit = "";
    try { credit = await (await loadPictograms()).credit(pictogramOptions().search); } catch (e) { /* said below */ }
    if (!credit) {
      toast("The ARASAAC credit could not be read: the licence asks for it, so add it as the last paragraph "
            + "(Settings → Pictograms has its words)", true);
      return false;
    }
    if (CREDIT_MARK.test(src.value)) return false;
    const at = src.value.length;
    const gap = src.value.endsWith("\n\n") ? "" : src.value.endsWith("\n") ? "\n" : "\n\n";
    src.setRangeText(gap + credit + "\n", at, at, "preserve");
    dirty = true;
    pushHistory(false);                       // one step with the picture that asked for it
    debouncedPreview();
    toast("Added ARASAAC's credit as the last paragraph — the licence asks for it, and it stays until you delete it");
    return true;
  }

  const btnPictograms = $("#btn-pictograms");
  if (btnPictograms) btnPictograms.addEventListener("click", () => {
    if (!DOC_ID) {
      toast("Save the document first — pictures are stored in its folder", true);
      return;
    }
    openPictograms({
      title: "Add a pictogram to this page",
      note: "A copy of the picture goes into this document's images/ folder and a figure at the cursor. "
          + "The line that credits ARASAAC is added once, as the last paragraph.",
      addLabel: "Add to the page",
      keepLabel: "Add, keep looking",
      onPick: async pick => {
        const data = await uploadImage(DOC_ID, await pick.file());
        const caption = pick.alt || "pictogram";
        // text the person had selected is theirs: a figure goes in after it, not over it (an embed replaces the selection,
        // except the caption of the one put in last, which the next goes in after)
        const placeholder = lastEmbed && src.selectionStart === lastEmbed.word[0] && src.selectionEnd === lastEmbed.word[1];
        if (!placeholder && src.selectionEnd > src.selectionStart) src.setSelectionRange(src.selectionEnd, src.selectionEnd);
        insertStandaloneLine(`![${caption}](${data.path})${PICTOGRAM_FIGURE}`, caption);
        return await ensureArasaacCredit() ? "ARASAAC's credit is now the page's last paragraph." : "";
      },
    });
  });

  /* ---- recordings: the manager ----

     The document's own recordings -- ▶ plays one, a click puts it in at the
     cursor, ✕ deletes the file -- and, where the toolbox has a clip tray
     (the hub; the studio run on its own has none), the clips cut from books
     and videos in the document's language, each put in with "Add" and
     brought into the document at once, or deleted from the tray with ✕.
     "In use" is what the editor's text names now, saved or not. */
  const btnAudios = $("#btn-audios");
  if (btnAudios) btnAudios.addEventListener("click", () => {
    if (!DOC_ID) {
      toast("Save the document first — recordings are stored in its folder", true);
      return;
    }
    const root = $("#modal-root");
    root.innerHTML = "";
    const ov = document.createElement("div");
    ov.className = "modal-overlay";
    ov.innerHTML = `<div class="modal audio-modal" role="dialog" aria-modal="true" aria-label="Recordings" tabindex="-1">
      <h3>Recordings of this document</h3>
      <p>Click one to insert it at the cursor; ▶ plays it, ✕ deletes the file.</p>
      <div class="audlist" data-x="mine"></div>
      <section class="audclips" hidden>
        <h4>Clips cut from books and videos</h4>
        <p>Cut with “🔊 cut the audio…” on a book's or a video's card sheet. Add puts one in at the cursor and copies it into this document; ✕ deletes it from the tray.</p>
        <div class="audlist" data-x="clips"></div>
      </section>
      <div class="row"><button class="btn" data-x="close">Close</button></div></div>`;
    const player = new Audio();
    let playing = null;
    // the keys go to the dialog while it is open, and Escape closes it
    // wherever the focus is -- a deleted row takes a focused ✕ with it
    const opener = document.activeElement;
    const onKey = e => {
      if (!ov.isConnected) { document.removeEventListener("keydown", onKey); return; }
      if (e.key === "Escape" && !e.defaultPrevented) { e.preventDefault(); closeM(); }
    };
    const closeM = () => {
      player.pause();
      document.removeEventListener("keydown", onKey);
      if (!ov.parentNode) return;
      const inside = ov.contains(document.activeElement);
      root.removeChild(ov);
      if (inside && opener && opener.isConnected && opener.focus) opener.focus({preventScroll: true});
    };
    ov.addEventListener("click", e => { if (e.target === ov) closeM(); });
    document.addEventListener("keydown", onKey);
    $('[data-x="close"]', ov).addEventListener("click", closeM);
    root.appendChild(ov);
    $(".audio-modal", ov).focus({preventScroll: true});
    const mine = $('[data-x="mine"]', ov), clipList = $('[data-x="clips"]', ov);
    const clipBox = $(".audclips", ov);

    const showPlaying = () => $$(".audplay", ov).forEach(b => {
      const on = b === playing && !player.paused;
      b.textContent = on ? "❚❚" : "▶";
      b.classList.toggle("playing", on);
    });
    for (const type of ["play", "pause", "ended", "emptied"]) player.addEventListener(type, showPlaying);
    const playButton = (url, name) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "audplay"; b.textContent = "▶";
      b.title = "Play"; b.setAttribute("aria-label", "Play " + name);
      b.addEventListener("click", e => {
        e.stopPropagation();                       // not an insert
        if (playing === b && !player.paused) { player.pause(); return; }
        if (player.getAttribute("src") !== url) player.src = url;
        playing = b;
        player.play().catch(err => { if (err.name !== "AbortError") toast("Could not play: " + err.message, true); });
      });
      return b;
    };
    const kb = size => `${Math.max(1, Math.round(size / 1024))} kB`;
    const namedNow = () => new Set((src.value.match(
      /(?<![A-Za-z0-9._\/\-])audio\/[A-Za-z0-9][A-Za-z0-9._\-]*/g) || []).map(p => p.slice(6)));

    async function refresh() {
      const data = await api(`/api/docs/${DOC_ID}/audio`);
      const used = namedNow();
      mine.innerHTML = "";
      if (!data.audio.length) {
        mine.innerHTML = '<p class="hint">No recordings uploaded yet — use the Audio button, or drag an MP3, M4A, Ogg, WAV or other recording into the editor.</p>';
        return;
      }
      for (const rec of data.audio) {
        const row = document.createElement("div");
        row.className = "audrow";
        row.tabIndex = 0;
        row.setAttribute("role", "button");
        row.title = "Insert at the cursor";
        row.dataset.name = rec.name;
        const name = document.createElement("span");
        name.className = "audname"; name.textContent = rec.name;
        const size = document.createElement("span");
        size.className = "audsize"; size.textContent = kb(rec.size);
        const del = document.createElement("button");
        del.type = "button"; del.className = "del"; del.textContent = "✕"; del.title = "Delete file";
        row.append(playButton(`${BASE}/media/${DOC_ID}/audio/${rec.name}`, rec.name), name, size);
        if (used.has(rec.name)) {
          const ref = document.createElement("span");
          ref.className = "ref"; ref.textContent = "in use";
          row.append(ref);
        }
        row.append(del);
        const insert = () => { closeM(); insertAudioLine("audio/" + rec.name); };
        row.addEventListener("click", e => { if (!e.target.closest("button")) insert(); });
        row.addEventListener("keydown", e => {
          if ((e.key === "Enter" || e.key === " ") && e.target === row) { e.preventDefault(); insert(); }
        });
        del.addEventListener("click", async e => {
          e.stopPropagation();
          const warn = used.has(rec.name)
            ? `“${rec.name}” is used by the document — the embed will break. Delete anyway?`
            : `Delete “${rec.name}”?`;
          if (!confirm(warn)) return;
          try {
            if (playing && player.getAttribute("src").endsWith("/" + rec.name)) player.pause();
            await api(`/api/docs/${DOC_ID}/audio/${encodeURIComponent(rec.name)}`, {method: "DELETE"});
            // the preview shows it gone at once, as the warning said
            mediaChanged("audio/" + rec.name);
            preview();
            await refresh();
            // the row went with its ✕: the focus stays in the dialog
            if (ov.isConnected && !ov.contains(document.activeElement))
              $(".audio-modal", ov).focus({preventScroll: true});
          } catch (err) { toast(err.message, true); }
        });
        mine.appendChild(row);
      }
    }

    // the tray is the hub's (/clips), not the studio's: no BASE before it,
    // and nothing shown where nothing answers
    async function refreshClips() {
      let clips = [];
      try {
        const r = await fetch("/clips/api/list?kind=audio&lang=" + encodeURIComponent(lang().code));
        const data = await r.json();
        if (r.ok && data.ok !== false && Array.isArray(data.clips)) clips = data.clips;
      } catch (e) { clips = []; }
      clipList.innerHTML = "";
      clipBox.hidden = !clips.length;
      for (const clip of clips) {
        const row = document.createElement("div");
        row.className = "audrow clip";
        row.dataset.name = clip.name;
        const words = String(clip.text || clip.label || "").replace(/\s+/g, " ").trim();
        const name = document.createElement("span");
        name.className = "audname";
        const said = document.createElement("span");
        said.className = "audtext"; said.textContent = words || clip.name;
        const detail = document.createElement("small");
        detail.textContent = [words ? clip.name : "", clip.duration ? clip.duration.toFixed(1) + " s" : "",
          (clip.source && clip.source.title) || ""].filter(Boolean).join(" · ");
        name.append(said, detail);
        const add = document.createElement("button");
        add.type = "button"; add.className = "btn small"; add.dataset.x = "add"; add.textContent = "Add";
        add.title = "Put it in at the cursor and copy it into this document";
        add.addEventListener("click", async () => {
          closeM();
          // its words as the caption, when a caption can hold them
          const caption = words.replace(/[\[\]]/g, "").slice(0, 120).trim() || "didascalia";
          insertStandaloneLine(`![${caption}](${clip.path})`, caption);
          try {
            const data = await adoptFromTray(src.value);
            if (data && (data.missing || []).includes(clip.path))
              toast(`${clip.name} is no longer in the clip tray`, true);
          } catch (err) { toast("Could not bring the clip in: " + err.message, true); }
        });
        // a clip nobody wants any more leaves the tray from here; whatever
        // it went into kept its own copy
        const del = document.createElement("button");
        del.type = "button"; del.className = "del"; del.textContent = "✕";
        del.title = "Delete it from the clip tray";
        del.setAttribute("aria-label", "Delete " + clip.name + " from the clip tray");
        del.addEventListener("click", async e => {
          e.stopPropagation();
          if (!confirm(`Delete “${clip.name}” from the clip tray? A document, a deck or a card `
                       + "it already went into keeps its own copy.")) return;
          try {
            if (playing && player.getAttribute("src") === clip.url) player.pause();
            const r = await fetch("/clips/api/" + encodeURIComponent(clip.name), {method: "DELETE"});
            let data = {};
            try { data = await r.json(); } catch (_) { /* not JSON */ }
            // gone already (another page emptied the tray) is what was wanted
            if (!r.ok && r.status !== 404) throw new Error(data.error || r.status + " " + r.statusText);
            await refreshClips();
            if (ov.isConnected && !ov.contains(document.activeElement))
              $(".audio-modal", ov).focus({preventScroll: true});
          } catch (err) { toast("Could not delete the clip: " + err.message, true); }
        });
        row.append(playButton(clip.url, clip.name), name, add, del);
        clipList.appendChild(row);
      }
    }
    refresh().catch(e => toast(e.message, true));
    refreshClips();
  });

  preview();
}

/* ---------------- boot ----------------
   app.js's own boot leaves the edit page to this file, which is loaded only
   there (markdown/app/templates/edit.html). */
if (PAGE === "edit") initEdit();
