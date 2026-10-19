// SPDX-License-Identifier: GPL-3.0-or-later
/* A FILE FROM ANYWHERE ON THE COMPUTER, OPEN IN THE STUDIO (a0.5.2).

   markdown/app/openfile.py keeps the other half of this: a Markdown or zip
   file chosen anywhere on the disk is read into a working copy in a temporary
   folder, the studio edits THAT, and the file itself changes at one moment
   only -- Save.  Closing deletes the copy.  This script is what a person sees
   of it, in three places:

     the library page   "Open a file…" (a file browser of the computer's disk,
                        or a path typed or pasted), and the list of the files
                        open now -- among them any that a stopped Parseh left
                        with changes nobody saved;
     a document page    the bar under the title: which file this is, whether it
                        holds what the page holds, and Save to file / Save as… /
                        Close file;
     the editor         the same bar, and the editor's own Save writes to the
                        file as well (ParsehFile.afterSave, called by editor.js).

   A classic script, after app.js (and editor.js on the edit page): it reads
   their top-level names ($, $$, BASE, send, toast) and adds none of its own to
   the page but ParsehFile.  On a page that is neither it does nothing.  Every
   device Parseh lets in may use it: what it shows and writes is always the disk
   of the computer Parseh runs on, so from another device the windows say whose
   disk that is (`where`, told by the server). */
(function () {
  "use strict";
  const SID = document.body.dataset.openSid || "";          // set on a session's pages
  const LIBRARY = document.body.dataset.page === "index";
  if (!SID && !LIBRARY) return;

  const LAST_DIR = "parseh_open_dir", RECENT = "parseh_open_recent";
  let sep = "/";                                              // this computer's, said by the server

  /* ---------------- small things ---------------- */
  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v === null || v === undefined) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return e;
  }
  const remember = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private window */ } };
  const recall = k => { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } };
  function human(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return Math.round(n / 1024) + " KB";
    return (n / 1048576).toFixed(n < 10 * 1048576 ? 1 : 0) + " MB";
  }
  function when(seconds) {
    const d = new Date(seconds * 1000);
    return isNaN(d) ? "" : d.toLocaleDateString(undefined, {year: "numeric", month: "short", day: "numeric"});
  }
  function join(dir, name) {
    if (!dir) return name;
    return dir.endsWith(sep) ? dir + name : dir + sep + name;
  }
  function baseName(path) {
    const i = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
    return i < 0 ? path : path.slice(i + 1);
  }
  function dirName(path) {
    const i = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
    return i <= 0 ? path.slice(0, i + 1) : path.slice(0, i);
  }
  /* A click that is the SECOND of a double-click is not asked of the list: a person who double-clicks a folder (as
     every file dialog teaches) goes into it once, and the second click does not land on whatever the new list put
     under the pointer. */
  const once = fn => e => { if (!e || e.detail < 2) fn(e); };
  /* the files opened lately, newest first, as this browser remembers them: one click to open one again */
  function recents() {
    try {
      const list = JSON.parse(recall(RECENT) || "[]");
      return Array.isArray(list) ? list.filter(p => typeof p === "string").slice(0, 8) : [];
    } catch (e) { return []; }
  }
  function noteRecent(path) { remember(RECENT, JSON.stringify([path, ...recents().filter(p => p !== path)].slice(0, 8))); }
  /* WHERE THE FILES ARE.  The file doors show the disk of the computer Parseh runs on, whichever device asks; the
     server says which computer that is and whether this device is another one, in every answer that has a path in it. */
  const where = {remote: false, host: ""};
  function noteWhere(d) {
    if (d && typeof d.remote === "boolean") { where.remote = d.remote; where.host = d.host || ""; }
  }
  const onHost = () => (where.remote && where.host ? " on " + where.host : "");
  /* a POST that gives back what the server said whatever its status: {status, ok, data} (app.js send) */
  async function post(path, json) {
    try {
      const a = await send(path, {method: "POST", json: json || {}});
      noteWhere(a.data);
      return a;
    } catch (e) {
      return {status: 0, ok: false, data: {ok: false, error: "Parseh does not answer — is it still running?"}};
    }
  }

  /* ---------------- a window of our own ----------------
     The studio's own dialog look (.modal, .dk-modal), with the buttons the
     caller names; Escape and a click beside the box close it unless it is
     busy. `build(box, api)` fills the body and may call api.close(value). */
  const windows = [];          // the windows open now, the last of them on top: Escape closes that one alone
  function openDialog({title, wide, build, buttons = []}) {
    const root = $("#modal-root") || document.body;
    const back = document.activeElement;
    return new Promise(resolve => {
      const ov = el("div", {class: "modal-overlay of-overlay"});
      const box = el("div", {class: "modal dk-modal of-modal" + (wide ? " of-wide" : ""), role: "dialog",
                             "aria-modal": "true", "aria-label": title});
      box.append(el("h3", {text: title}));
      const content = el("div", {class: "of-body"});
      box.append(content);
      const row = el("div", {class: "row of-buttons"});
      box.append(row);
      ov.append(box);
      let busy = false, done = false;
      const head = box.querySelector("h3");
      const api = {
        box: content, row,
        title(text) { head.textContent = text; box.setAttribute("aria-label", text); },
        close(value) {
          if (done) return;
          done = true;
          document.removeEventListener("keydown", onKey, true);
          const at = windows.indexOf(api);
          if (at >= 0) windows.splice(at, 1);
          ov.remove();
          if (back && back.isConnected && back.focus) back.focus();
          resolve(value === undefined ? null : value);
        },
        busy(on) { busy = on; $$("button", row).forEach(b => { b.disabled = on; }); },
        button(label, cls, value, run) {
          const b = el("button", {type: "button", class: "btn " + (cls || ""), text: label});
          b.addEventListener("click", async () => {
            if (busy) return;
            if (!run) return api.close(value);
            api.busy(true);
            try { await run(api); } finally { if (!done) api.busy(false); }
          });
          row.append(b);
          return b;
        },
      };
      function onKey(e) {
        if (e.key === "Escape" && windows[windows.length - 1] === api) { e.preventDefault(); e.stopPropagation(); if (!busy) api.close(null); }
      }
      windows.push(api);
      document.addEventListener("keydown", onKey, true);
      ov.addEventListener("mousedown", e => { if (e.target === ov && !busy) api.close(null); });
      build(content, api);
      for (const b of buttons) api.button(b.label, b.cls, b.value, b.run);
      root.append(ov);
      const first = $("[autofocus], input, .of-row", box) || $(".btn.primary", row) || $(".btn", row);
      if (first) first.focus();
    });
  }

  /* ---------------- the file browser ----------------
     Both ways of choosing a place work, because a person wants either: the
     list (places on the left, a folder's contents, click to go in) and a path
     typed or pasted (Enter).  mode "open" chooses a file that is there;
     mode "save" chooses a folder and a name for a file that may not be.
     -> the full path, or null. */
  function browse({mode, title, okLabel, start, name}) {
    const saving = mode === "save";
    let dir = start || recall(LAST_DIR) || "";
    let selected = "", listing = null, dlg = null, typedAt = 0, asked = 0;
    const show = {hidden: false, everything: false};
    const status = el("p", {class: "of-status", role: "status"});
    const pathInput = el("input", {type: "text", class: "of-path", spellcheck: "false", autocomplete: "off",
                                   "aria-label": "Folder or file path",
                                   placeholder: "Type or paste a path, then press Enter"});
    const crumbs = el("div", {class: "of-crumbs"});
    const places = el("div", {class: "of-places"});
    const list = el("div", {class: "of-list", role: "listbox", "aria-label": "Folder contents"});
    const nameInput = el("input", {type: "text", class: "of-name", value: name || "", spellcheck: "false",
                                   "aria-label": "File name", placeholder: "File name"});
    const chosen = el("span", {class: "of-chosen"});
    // the title says whose disk it is once the first answer has said so
    const headline = () => title ? title + onHost()
      : saving ? "Save as…" + onHost()
      : where.remote && where.host ? "Open a file on " + where.host : "Open a file from this computer";
    return openDialog({
      title: headline(), wide: true,
      build(box, api) {
        dlg = api;
        const goBtn = el("button", {type: "button", class: "btn", text: "Go", onclick: () => go(pathInput.value)});
        const hiddenBox = el("input", {type: "checkbox", onchange: () => { show.hidden = hiddenBox.checked; go(dir); }});
        const allBox = el("input", {type: "checkbox", onchange: () => { show.everything = allBox.checked; go(dir); }});
        box.append(
          el("div", {class: "of-top"}, pathInput, goBtn),
          crumbs,
          el("div", {class: "of-main"}, places, list),
          el("div", {class: "of-opts"},
             el("label", {}, hiddenBox, " Show hidden"),
             saving ? null : el("label", {}, allBox, " Show every file, not only the ones the studio opens")),
          saving ? el("label", {class: "of-namerow"}, el("span", {text: "File name"}), nameInput)
                 : el("div", {class: "of-namerow"}, el("span", {text: "Chosen"}), chosen),
          status);
        pathInput.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); go(pathInput.value); } });
        pathInput.addEventListener("input", () => { typedAt = Date.now(); });
        nameInput.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); finish(); } });
        api.button("Cancel", "", null);
        api.button(okLabel || (saving ? "Save" : "Open"), "primary", undefined, () => finish());
        go(dir);
      },
    });

    function say(text, bad) { status.textContent = text || ""; status.classList.toggle("bad", !!bad); }

    /* Show a place.  `note` is what to say about it (why a jump to another folder happened). */
    async function go(path, note) {
      const mine = ++asked, began = Date.now();
      say(note || "", !!note);
      const a = await post("/api/file/list", {path: (path || "").trim(), hidden: show.hidden, everything: show.everything});
      if (mine !== asked) return;                // a later place was asked for while this was being read: this answer is stale
      const d = a.data || {};
      dlg.title(headline());
      if (d.sep) sep = d.sep;
      if (!d.places && !d.kind) { say(d.error || "Could not read that place.", true); return; }
      if (d.kind === "file") {                   // a path to a file was typed: that file is the choice
        dir = d.dir;
        selected = baseName(d.path);
        if (saving) { nameInput.value = selected; return go(dir); }
        return dlg.close(d.path);
      }
      if (d.ok === false) {                      // not there / not readable: the nearest folder, and the reason
        if (d.path && d.path !== path) return go(d.path, d.error);
        say(d.error, true);
        return;
      }
      listing = d;
      dir = d.path;
      drawPlaces(d.places || []);
      // what the person typed while this was being read is theirs: the list arriving must not take it away
      if (typedAt <= began) pathInput.value = dir ? join(dir, "") : "";
      if (dir) remember(LAST_DIR, dir);
      if (!saving) selected = "";
      draw();
    }

    function drawPlaces(items) {
      places.replaceChildren(el("div", {class: "of-places-h", text: "Places"}));
      for (const p of items) {
        places.append(el("button", {type: "button", class: "of-place" + (p.path && p.path === dir ? " on" : ""), text: p.name,
                                    title: p.path || "Drives", onclick: once(() => go(p.path))}));
      }
      const lately = saving ? [] : recents();
      if (lately.length) {
        places.append(el("div", {class: "of-places-h of-recent-h", text: "Recent"}));
        for (const path of lately) {
          places.append(el("button", {type: "button", class: "of-place of-recent", text: baseName(path), title: path,
                                      onclick: once(() => go(path))}));
        }
      }
    }

    function drawCrumbs() {
      crumbs.replaceChildren();
      (listing.crumbs || []).forEach((c, i) => {
        if (i) crumbs.append(el("span", {class: "of-sep", "aria-hidden": "true", text: "›"}));
        crumbs.append(el("button", {type: "button", class: "of-crumb", text: c.name === sep ? "Computer" : c.name,
                                    onclick: once(() => go(c.path))}));
      });
    }

    function draw() {
      drawCrumbs();
      list.replaceChildren();
      if (listing.parent !== null && listing.parent !== undefined) {
        list.append(el("button", {type: "button", class: "of-row of-up", onclick: once(() => go(listing.parent))},
                       el("span", {class: "of-ic", "aria-hidden": "true", text: "↰"}),
                       el("span", {class: "of-n", text: "Up one folder"})));
      }
      for (const e of listing.entries) {
        if (e.kind === "dir") {
          list.append(el("button", {type: "button", class: "of-row", role: "option", title: e.name,
                                    onclick: once(() => go(join(dir, e.name)))},
                         el("span", {class: "of-ic", "aria-hidden": "true", text: "📁"}),
                         el("span", {class: "of-n", text: e.name})));
          continue;
        }
        const on = e.name === selected;
        const row = el("button", {type: "button", class: "of-row" + (on ? " on" : "") + (e.openable ? "" : " dim"),
                                  role: "option", "aria-selected": on ? "true" : "false", title: e.name,
                                  onclick: once(() => pick(e, row)), ondblclick: () => { pick(e, row); finish(); }},
                       el("span", {class: "of-ic", "aria-hidden": "true", text: e.type === "zip" ? "📦" : "📄"}),
                       el("span", {class: "of-n", text: e.name}),
                       el("span", {class: "of-m", text: human(e.size) + (e.mtime ? " · " + when(e.mtime) : "")}));
        list.append(row);
      }
      if (!listing.entries.length) list.append(el("p", {class: "of-empty", text: "Nothing the studio opens in this folder."}));
      if (listing.truncated) say("Only the first part of this folder is listed: type the path of the file instead.");
      chosen.textContent = selected;
    }

    function pick(e, row) {
      if (!e.openable) { say("The studio opens Markdown (.md, .markdown, .txt) and zip files.", true); return; }
      say("");
      selected = e.name;
      if (saving) nameInput.value = e.name;
      for (const r of $$(".of-row.on", list)) { r.classList.remove("on"); r.setAttribute("aria-selected", "false"); }
      row.classList.add("on");
      row.setAttribute("aria-selected", "true");
      chosen.textContent = e.name;
    }

    function finish() {
      const leaf = saving ? nameInput.value.trim() : selected;
      const typed = pathInput.value.trim();
      if (!saving && !selected && typed && typed !== join(dir, "")) { go(typed); return; }   // a path typed, Open pressed
      if (!leaf) { say(saving ? "Type a name for the file." : "Choose a file in the list, or type its path.", true); return; }
      if (!dir) { say("Choose a folder first.", true); return; }
      if (/[\\/]/.test(leaf)) { say("A file name has no folder in it: choose the folder in the list.", true); return; }
      dlg.close(join(dir, leaf));
    }
  }

  /* ---------------- opening ---------------- */
  async function openPath(path, entry) {
    const a = await post("/api/file/open", entry ? {path, entry} : {path});
    const d = a.data || {};
    if (d.choose) return chooseDocument(path, d);
    if (a.ok && d.url) {
      noteRecent(path);
      location.href = d.url;
      return true;
    }
    return {error: d.error || "Could not open that file.", sid: d.sid, code: d.code};
  }

  /* a zip with several Markdown files in it: which one is the document? */
  async function chooseDocument(path, d) {
    const pick = await openDialog({
      title: "Which document in " + d.name + "?", wide: false,
      build(box, api) {
        box.append(el("p", {text: "This zip holds several Markdown files. The studio opens one at a time; the rest of the zip is kept as it is."}));
        const list = el("div", {class: "dl-list"});
        for (const c of d.choose) {
          list.append(el("button", {type: "button", class: "dl-item", onclick: () => api.close(c.path)},
                         el("span", {class: "dl-t", dir: "auto", text: c.title || c.path}),
                         el("span", {class: "dl-s", dir: "auto", text: c.path + " · " + human(c.size)})));
        }
        box.append(list);
        api.button("Cancel", "", null);
      },
    });
    if (!pick) return null;
    return openPath(path, pick);
  }

  async function chooseAndOpen() {
    let path = await browse({mode: "open"});
    while (path) {
      const result = await openPath(path);
      if (result === true || result === null) return;
      // it could not be opened: say why where the person can read it, and let them choose again
      const again = await openDialog({
        title: "That file did not open",
        build(box, api) {
          box.append(el("p", {class: "of-bad", text: result.error}));
          if (result.sid) {
            box.append(el("p", {}, el("a", {href: BASE + "/open/" + result.sid + "/"}, "Go to the one that is open")));
          }
          api.button("Cancel", "", null);
          api.button("Choose another file…", "primary", true);
        },
      });
      if (!again) return;
      path = await browse({mode: "open", start: dirName(path)});
    }
  }

  /* ---------------- the files open now (library page) ---------------- */
  async function listOpen() {
    const holder = $("#open-files");
    if (!holder) return;
    const a = await post("/api/file/sessions");
    const rows = (a.data && a.data.sessions) || [];
    holder.replaceChildren();
    holder.hidden = !rows.length;
    if (!rows.length) return;
    holder.append(el("h2", {class: "of-h", text: "Files open now"}),
                  el("p", {class: "of-hint", text: "Worked on through a copy: the file itself changes only when you save."}));
    for (const s of rows) {
      const say = s.recovered ? "Parseh stopped before these changes were saved — they are all still here."
        : s.missing ? "The file is not where it was."
        : s.changed_on_disk ? (s.dirty ? "Changed on disk, and you have changes of your own." : "Changed on disk since you opened it.")
        : s.dirty ? "Has changes not saved to the file." : "Saved.";
      holder.append(el("div", {class: "of-open" + (s.dirty ? " dirty" : "")},
        el("div", {class: "of-open-t"},
           el("a", {class: "of-open-name", href: s.url, text: s.name}),
           el("span", {class: "of-open-dir", title: s.path, text: s.dir})),
        el("div", {class: "of-open-s", text: say}),
        el("div", {class: "of-open-a"},
           el("a", {class: "btn small", href: s.url, text: "Read"}),
           el("a", {class: "btn small", href: s.edit, text: "Edit"}),
           el("button", {type: "button", class: "btn small", text: "Close", onclick: () => closeOther(s)}))));
    }
  }

  async function closeOther(s) {
    let a = await post("/open/" + s.sid + "/api/file/close", {});
    if (a.data && a.data.need === "unsaved") {
      const sure = await confirmDialog({
        title: "Close " + s.name + " without saving?",
        hint: "It has changes that are not in the file. Closing throws them away; the file stays as it is.",
        ok: "Close without saving", danger: true});
      if (!sure) return;
      a = await post("/open/" + s.sid + "/api/file/close", {discard: true});
    }
    if (!(a.data && a.data.ok)) toast((a.data && a.data.error) || "Could not close it", true);
    listOpen();
  }

  /* ---------------- the bar of a file's own page ---------------- */
  let state = null, bar = null, gone = false, saving = false, timer = null;

  function fileWords(s) {
    if (gone || !s) return ["This file was closed in another window. Open it again from the library.", "bad"];
    if (s.missing) return ["The file is not where it was. Your work is safe here: Save as… puts it somewhere.", "bad"];
    if (s.changed_on_disk && s.dirty) return ["The file changed on disk, and you have changes of your own.", "warn"];
    if (s.changed_on_disk) return ["The file changed on disk since you opened it.", "warn"];
    if (!s.can_write) return ["Read-only: save elsewhere with Save as…", "warn"];
    if (s.dirty) return ["Changes not saved to the file yet.", "warn"];
    return ["Saved — the file holds what this page holds.", "ok"];
  }

  function drawBar() {
    if (!bar) return;
    if (!state) {                        // closed in another window before this page ever heard of it
      bar.dataset.tone = "bad";
      $(".fb-state", bar).textContent = fileWords(null)[0];
      for (const b of $$(".fb-save, .fb-saveas, .fb-reload, .fb-close", bar)) b.disabled = true;
      return;
    }
    const s = state, [words, tone] = fileWords(s);
    bar.dataset.tone = tone;
    $(".fb-name", bar).textContent = s.name;
    $(".fb-name", bar).title = s.path;
    $(".fb-where", bar).textContent = (s.kind === "zip" && s.entry ? s.entry + " in the zip · " : "") + s.dir + onHost();
    $(".fb-where", bar).title = s.path;
    $(".fb-state", bar).textContent = words;
    const notes = $(".fb-notes", bar);
    notes.hidden = !(s.warnings && s.warnings.length);
    notes.textContent = "⚠ " + (s.warnings || []).length + " note" + ((s.warnings || []).length === 1 ? "" : "s");
    const save = $(".fb-save", bar);
    save.classList.toggle("primary", !!(s.dirty && !gone));
    save.disabled = gone || saving;
    $(".fb-saveas", bar).disabled = gone || saving;
    const reload = $(".fb-reload", bar);
    reload.hidden = !(s.changed_on_disk || s.missing);
    reload.disabled = s.missing || gone;
    $(".fb-close", bar).disabled = gone || saving;
  }

  let stateAsked = 0;
  async function refresh() {
    if (gone || saving) return;
    const mine = ++stateAsked;
    const a = await post("/api/file/state");
    if (mine !== stateAsked || saving) return;   // a save or a later read has been made since: this one is stale
    if (a.status === 404) { gone = true; drawBar(); clearInterval(timer); return; }
    if (a.data && a.data.state) { state = a.data.state; drawBar(); }
  }

  async function showNotes() {
    await openDialog({
      title: "About opening " + state.name,
      build(box, api) {
        box.append(el("ul", {class: "of-notes"}, (state.warnings || []).map(w => el("li", {dir: "auto", text: w}))));
        api.button("OK", "primary", true);
      },
    });
  }

  /* ---------- saving: the questions the server may ask, one at a time ---------- */
  async function askConflict(d) {
    return openDialog({
      title: baseName(d.path) + " changed on disk",
      build(box, api) {
        box.append(el("p", {text: "Something else changed this file after you opened it. Saving now would replace those changes with yours."}));
        api.button("Cancel", "", "cancel");
        api.button("Save as another file…", "", "saveas");
        api.button("Replace it with my version", "danger", "force");
      },
    });
  }

  async function askMissing(d) {
    return openDialog({
      title: baseName(d.path) + " is not there any more",
      build(box, api) {
        box.append(el("p", {text: "It was moved, renamed or deleted. What you have here is safe: save it as a new file."}));
        api.button("Cancel", "", "cancel");
        api.button("Save as…", "primary", "saveas");
      },
    });
  }

  async function askExists(path) {
    return confirmDialog({
      title: "Replace " + baseName(path) + "?",
      hint: "A file with this name is already in " + dirName(path) + ". Saving here replaces it.",
      ok: "Replace it", danger: true});
  }

  /* A Markdown file cannot hold pictures, recordings or tags: say which, and
     offer what the library's own zip does -- everything, in the layout its
     Upload takes back -- or the text alone.  The .md is never rewritten into
     a zip: the zip is a new file beside it. */
  async function askFormat(d) {
    let target = d.suggest;
    return openDialog({
      title: baseName(d.path) + " cannot hold all of this", wide: true,
      build(box, api) {
        box.append(el("p", {text: "A Markdown file is plain text. These would be left out of it:"}));
        const ul = el("ul", {class: "of-left"});
        for (const r of d.reasons) {
          if (r.what === "media") {
            ul.append(el("li", {}, el("b", {text: "Pictures and recordings: "}), el("span", {dir: "auto", text: r.names.join(", ")})));
          } else {
            ul.append(el("li", {}, el("b", {text: "Tags: "}), el("span", {dir: "auto", text: r.tags.join(", ")})));
          }
        }
        box.append(ul);
        box.append(el("p", {text: "Save everything as a zip instead — the Markdown, its pictures in images/ and recordings in audio/, and its tags — the form the library's Upload takes back. " + baseName(d.path) + " itself is left exactly as it is."}));
        const input = el("input", {type: "text", class: "of-zip", value: target, spellcheck: "false", "aria-label": "Zip file path"});
        input.addEventListener("input", () => { target = input.value; });
        const browseBtn = el("button", {type: "button", class: "btn", text: "Browse…", onclick: async () => {
          const p = await browse({mode: "save", title: "Save the zip as…", okLabel: "Choose", start: dirName(target), name: baseName(target)});
          if (p) { target = p; input.value = p; }
        }});
        box.append(el("label", {class: "of-namerow"}, el("span", {text: "Zip"}), input, browseBtn));
        if (d.suggest_exists) box.append(el("p", {class: "of-warn", text: "A file with this name already exists; you will be asked before it is replaced."}));
        api.button("Cancel", "", null);
        api.button("Save the text only", "", {text: true});
        api.button("Save as zip", "primary", undefined, a => {
          const t = input.value.trim();
          if (!t) { input.focus(); return; }
          if (!/\.zip$/i.test(t)) { input.value = t + ".zip"; }
          a.close({zip: input.value.trim()});
        });
      },
    });
  }

  /* Save the file, whatever it takes to get the person's answers. -> {ok, said} or {cancelled} */
  async function saveFile(first) {
    if (saving) return {cancelled: true};
    saving = true;
    stateAsked++;                               // whatever read of the state is on its way is from before this
    drawBar();
    let req = Object.assign({}, first || {});
    try {
      for (let turn = 0; turn < 8; turn++) {
        const a = await post("/api/file/save", req);
        const d = a.data || {};
        if (d.ok) {
          if (d.state) state = d.state;
          return {ok: true, said: said(d), data: d};
        }
        if (!d.need) {
          toast(d.error || "Could not save the file", true);
          if (d.state) state = d.state;
          return {ok: false, said: d.error};
        }
        if (d.state) state = d.state;
        if (d.need === "conflict") {
          const choice = await askConflict(d);
          if (choice === "force") { req = Object.assign({}, req, {force: true}); continue; }
          if (choice === "saveas") { const r = await saveAsDialog(req); return r; }
          return {cancelled: true};
        }
        if (d.need === "path") {
          const choice = await askMissing(d);
          if (choice === "saveas") return saveAsDialog(req);
          return {cancelled: true};
        }
        if (d.need === "exists") {
          if (await askExists(d.path)) { req = Object.assign({}, req, {overwrite: true}); continue; }
          return {cancelled: true};
        }
        if (d.need === "format") {
          const choice = await askFormat(d);
          if (!choice) return {cancelled: true};
          if (choice.text) { req = Object.assign({}, req, {accept_loss: true}); continue; }
          req = Object.assign({}, req, {target: choice.zip});
          delete req.overwrite;
          continue;
        }
        toast("The server asked for something this page does not know: " + d.need, true);
        return {ok: false};
      }
      return {ok: false};
    } finally {
      saving = false;
      drawBar();
    }
  }

  function said(d) {
    if (d.unchanged) return "Nothing new to save — the file already holds this.";
    const s = d.saved || {};
    if (s.wrote === false) {
      return "Nothing to write to " + s.name + ": its text is as it was, and what a Markdown file cannot hold stays out of it.";
    }
    let out = "Saved to " + s.name + ".";
    if (s.as_new && s.kind === "zip") out = "Saved as " + s.name + " — the Markdown, its pictures, recordings and tags in one zip.";
    if (s.left_out && s.left_out.length) out += " Pictures, recordings or tags the Markdown cannot hold were left out.";
    return out;
  }

  /* ON THE EDITOR'S PAGE the text being typed is not in the working copy until the editor saves it, so the bar's
     buttons go through the editor: "Save to file" is its own Save (the text, then the file), and what writes
     somewhere else first saves the text here.  The editor is asked, never reached into (editor.js ParsehEditor). */
  const editor = () => (document.body.dataset.page === "edit" && window.ParsehEditor) || null;
  const typing = () => !!(editor() && editor().dirty());

  /* the bar's buttons: save, then say what happened where the person is looking */
  async function saveAndSay(req) {
    if (editor()) { await editor().save(); return {ok: true, said: ""}; }    // the editor says what happened itself
    const r = await saveFile(req);
    if (r.ok) toast(r.said);
    else if (r.cancelled) toast("Not written to the file.");
    return r;
  }

  async function saveAsAndSay() {
    if (typing() && !(await editor().save({file: false}))) return;
    const r = await saveAsDialog({});
    if (r.ok) toast(r.said);
    else if (r.cancelled) toast("Not written to the file.");
  }

  async function saveAsDialog(carry) {
    if (!state) await refresh();          // pressed in the first breath of the page, before it knew its file
    const base = state ? state.path : "";
    const path = await browse({mode: "save", start: dirName(base), name: baseName(base)});
    if (!path) return {cancelled: true};
    return saveFile(Object.assign({}, carry, {target: path}));
  }

  async function reload() {
    if (!state) return;
    if (state.dirty || typing()) {
      const sure = await confirmDialog({
        title: "Load " + state.name + " as it is now?",
        hint: "Your changes on this page would be thrown away, and the file loaded again from the disk.",
        ok: "Throw them away and load it", danger: true});
      if (!sure) return;
    }
    const path = state.path, entry = state.entry;
    if (typing()) editor().forget();
    const c = await post("/api/file/close", {discard: true});
    if (!(c.data && c.data.ok)) { toast((c.data && c.data.error) || "Could not close the copy", true); return; }
    // the session is gone: ask the library's door (the page's BASE is the session's, which no longer exists)
    const root = (c.data.library || "/").replace(/\/$/, "");
    const r = await fetch(root + "/api/file/open", {method: "POST", headers: {"Content-Type": "application/json"},
                                                    body: JSON.stringify(entry ? {path, entry} : {path})});
    const d = await r.json().catch(() => ({}));
    if (d && d.url) location.href = d.url; else location.href = root + "/";
  }

  async function closeFile() {
    // typing the editor holds and not even the working copy does: the same question, asked before the server's
    if (typing()) {
      const choice = await openDialog({
        title: "Close " + state.name + "?",
        build(box, api) {
          box.append(el("p", {text: "You have typed changes that are not saved yet. Saving writes them to the file; closing without saving throws them away and leaves the file as it is."}));
          api.button("Keep working", "", null);
          api.button("Close without saving", "danger", "discard");
          api.button("Save and close", "primary", "save");
        },
      });
      if (!choice) return;
      if (choice === "discard") {
        editor().forget();
        const x = await post("/api/file/close", {discard: true});
        if (x.data && x.data.ok) { gone = true; location.href = x.data.library || "/"; return; }
        toast((x.data && x.data.error) || "Could not close the file", true);
        return;
      }
      if (!(await editor().save({file: false}))) return;
    }
    let a = await post("/api/file/close", {});
    let d = a.data || {};
    if (d.need === "unsaved") {
      const choice = await openDialog({
        title: "Close " + state.name + "?",
        build(box, api) {
          box.append(el("p", {text: "It has changes that are not in the file. Saving writes them to the file; closing without saving throws them away and leaves the file as it is."}));
          api.button("Keep working", "", null);
          api.button("Close without saving", "danger", "discard");
          api.button("Save and close", "primary", "save");
        },
      });
      if (!choice) return;
      if (choice === "save") {
        const r = await saveFile({});
        if (!r.ok) return;
        a = await post("/api/file/close", {});
      } else {
        a = await post("/api/file/close", {discard: true});
      }
      d = a.data || {};
    }
    if (d.ok) { gone = true; location.href = d.library || "/"; return; }
    toast(d.error || "Could not close the file", true);
  }

  function buildBar() {
    const header = $("header.topbar[data-layout='browser']") || $("header.topbar");
    if (!header) return;
    bar = el("div", {class: "filebar", id: "filebar", role: "region", "aria-label": "The file this page is about"},
      el("div", {class: "fb-id"},
         el("span", {class: "fb-line"}, el("span", {class: "fb-lead", text: "Editing a copy of "}), el("span", {class: "fb-name"})),
         el("span", {class: "fb-where"})),
      el("span", {class: "fb-state", role: "status", "aria-live": "polite"}),
      el("button", {type: "button", class: "btn small fb-notes", hidden: true, onclick: showNotes,
                    title: "Things to know about how this file was opened"}),
      el("span", {class: "fb-actions"},
         el("button", {type: "button", class: "btn small fb-save", text: "Save to file",
                       title: "Write what this page holds to the file (⌘S / Ctrl+S)", onclick: () => saveAndSay({})}),
         el("button", {type: "button", class: "btn small fb-saveas", text: "Save as…",
                       title: "Write it to another file and keep working on that one", onclick: () => saveAsAndSay()}),
         el("button", {type: "button", class: "btn small fb-reload", hidden: true, text: "Load it again",
                       title: "The file changed on disk: throw away this copy and load the file as it is now", onclick: reload}),
         el("button", {type: "button", class: "btn small fb-close", text: "Close file",
                       title: "Done with it: the copy is deleted, the file stays as the last save left it", onclick: closeFile})));
    header.after(bar);
  }

  function pageDetails() {
    // the library's own business is not offered for a file: there is no second document to duplicate, nothing to delete
    for (const id of ["#btn-duplicate", "#btn-delete"]) {
      const b = $(id);
      const menu = b && b.closest("details");
      if (menu) menu.hidden = true;
    }
    // ⌘S / Ctrl+S on a page that is not the editor saves the file (the editor saves, then the file, itself)
    if (document.body.dataset.page !== "edit") {
      document.addEventListener("keydown", e => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveAndSay({}); }
      });
    }
  }

  async function startFilePage() {
    buildBar();
    pageDetails();
    await refresh();
    if (state && state.recovered) {
      toast("Parseh stopped before this was saved — your changes are still here.");
    }
    timer = setInterval(() => { if (!document.hidden) refresh(); }, 4000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  }

  /* ---------------- what the editor calls ---------------- */
  window.ParsehFile = {
    active: !!SID,
    /* After the editor saved its working copy: write the file as well. -> null where there is no file, else {said, stay}:
       `stay` is true when the file was not written (the person cancelled a question), so that Save & view does not
       walk away from a page that still holds what the file does not. */
    async afterSave() {
      if (!SID) return null;
      const r = await saveFile({});
      if (r.ok) return {said: r.said, stay: false};
      if (r.cancelled) return {said: "Saved here — not to " + (state ? state.name : "the file") + " yet.", stay: true};
      return {said: "Saved here — the file could not be written.", stay: true};
    },
    save: saveFile,
    state: () => state,
  };

  /* ---------------- start ---------------- */
  if (SID) {
    startFilePage();
  } else {
    const open = $("#btn-open-file");
    if (open) {
      open.hidden = false;
      open.addEventListener("click", chooseAndOpen);
    }
    listOpen();
  }
})();
