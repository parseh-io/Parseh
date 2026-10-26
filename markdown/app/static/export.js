// SPDX-License-Identifier: GPL-3.0-or-later
/* THE HTML EXPORT'S OWN SCRIPT (markdown/app/webexport.py, TO-DO §8.38 and
   §9.7).  No page of the studio loads this file.  The export writes it into
   the one file it makes, after the slice of app.js the page needs (the
   functions that draw and mark an exercise, play a clip, open a footnote,
   set the sheet's sizes and theme), inside the function whose localStorage
   and sessionStorage are storages that die with the tab.  So everything
   named here is app.js's -- $, $$, lang, loadTypo, applyTypo, bindExercises,
   bindFootnoteClouds, armClipReplay, foldCase -- and everything defined here
   is named xp..., so that nothing of app.js is ever shadowed by it.

   WHAT IT DOES: puts the recordings where the page plays them (xpMedia),
   says under a YouTube video, when the page is opened from the disk, that
   it plays only on a website (xpVideoNotes), works the Aa menu (xpLook),
   and then either binds a document's sheet (xpDocument) or crams a deck's
   exercises (xpCram) -- the cram page's practice, less the computer: the
   exercises and their solved twins are in the file (#parseh-cards), and
   nothing is scheduled or sent. */

/* ---------------------------------------------------------------- maths */

/* A formula is drawn by MathJax, which the export carries only into a page
   that has one; this is lib/mathjax.js's typeset() less its loading, which
   could only fail here (the page may fetch nothing): the library is already
   in the page, and starts a tick after its script has run. */
function xpMath() {
  if (window.ParsehMath || !window.MathJax) return;
  const style = document.createElement("style");
  style.textContent =
    "mjx-assistive-mml{position:absolute!important;top:0;left:0;" +
    "clip:rect(1px,1px,1px,1px);padding:1px 0 0 0!important;border:0!important;" +
    "display:block!important;width:auto!important;overflow:hidden!important;" +
    "-webkit-user-select:none;user-select:none}" +
    "mjx-assistive-mml[display=\"block\"]{width:100%!important}.math{position:relative}";
  document.head.appendChild(style);
  const ready = new Promise(done => {
    let wait = 0;
    const look = () => {
      if (window.MathJax && window.MathJax.tex2svg) return done(window.MathJax);
      if (++wait > 400) return done(null);
      setTimeout(look, 25);
    };
    look();
  });
  window.ParsehMath = {
    typeset(root) {
      const all = (root || document).querySelectorAll(".math[data-tex]:not([data-drawn])");
      if (!all.length) return Promise.resolve(0);
      return ready.then(MJ => {
        let n = 0;
        all.forEach(el => {
          if (!MJ) { el.setAttribute("data-drawn", "no"); return; }
          let node;
          try { node = MJ.tex2svg(el.getAttribute("data-tex") || "",
                                  {display: el.classList.contains("mathblock")}); }
          catch (e) { el.setAttribute("data-drawn", "no"); return; }
          if (node.querySelector("[data-mjx-error], merror")) {
            el.setAttribute("data-drawn", "no");
            return;
          }
          el.innerHTML = node.innerHTML;
          el.setAttribute("data-drawn", "yes");
          n++;
        });
        return n;
      });
    }
  };
}

/* ---------------------------------------------------------------- the recordings */

/* Each recording -- or each stretch of one the export cut out -- is carried
   once, in #parseh-media, however many players play it; an <audio> says
   which by data-media.  It is made a blob: URL the first time it is asked
   for, so twenty clips of one narration hold one copy of it.  A clip the
   export CUT is the whole of its file now: the window its box still names
   (data-start / data-end, what the studio plays a clip of a longer
   recording by) is taken off before anything can play it.  One it could not
   cut (no ffmpeg on the machine that exported it) is the whole recording,
   and plays its window out of it exactly as the studio does. */
function xpMedia() {
  let store = {};
  try { store = JSON.parse(document.getElementById("parseh-media").textContent) || {}; }
  catch (e) { store = {}; }
  const made = new Map();
  function urlOf(key) {
    if (made.has(key)) return made.get(key);
    const data = store[key];
    let url = "";
    if (typeof data === "string") {
      const m = /^data:([^;,]+);base64,(.*)$/.exec(data);
      url = data;
      if (m) {
        const bin = atob(m[2]);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        url = URL.createObjectURL(new Blob([bytes], {type: m[1]}));
      }
    }
    made.set(key, url);
    return url;
  }
  return function place(root) {
    $$("audio[data-media]", root).forEach(a => {
      const url = urlOf(a.dataset.media);
      if (!url) return;
      if (a.dataset.cut === "1") {
        const box = a.closest("figure.audio, .ex-audio");
        if (box) { delete box.dataset.start; delete box.dataset.end; }
      }
      a.src = url + (a.dataset.frag || "");
    });
    xpVideoNotes(root);
  };
}

/* A YOUTUBE VIDEO ON A PAGE OPENED FROM THE DISK plays nothing: YouTube
   wants to know which site a player is on, and a file on the disk is on
   none ("Video player configuration error").  There, and only there, a line
   under the video says so and opens it on YouTube itself, from where the
   page's window begins (the owner's choice).  On a website nothing is
   added: the player plays. */
function xpVideoNotes(root) {
  if (location.protocol !== "file:") return;
  $$("figure.video[data-vid]", root).forEach(fig => {
    if (!$('iframe[src^="https://www.youtube-nocookie.com/"]', fig) || $(".xp-video-note", fig)) return;
    const start = parseFloat(fig.dataset.start);
    const a = document.createElement("a");
    a.href = "https://www.youtube.com/watch?v=" + encodeURIComponent(fig.dataset.vid) +
      (start > 0 ? "&t=" + Math.floor(start) + "s" : "");
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = "watch it on YouTube";
    const note = document.createElement("p");
    note.className = "xp-video-note";
    note.append("YouTube plays this video only when the page is on a website — ", a);
    fig.appendChild(note);
  });
}

/* ---------------------------------------------------------------- Aa */

/* The size of the text and the theme, and nothing else of the studio's Aa
   bar.  The size starts where the studio's sheet starts, at the PDF's; the
   theme on the page's own, below.  Both are kept for as long as the tab: the
   storage loadTypo reads is this page's own, and empty. */
function xpLook() {
  const t = loadTypo(null);
  /* SEPIA, WHATEVER THE SYSTEM PREFERS (TO-DO §2.26, the owner's choice).
     These pages are read by students, on somebody else's website, and sepia
     is the paper made for reading -- the warm one the studio has always read
     on.  What loadTypo falls back to when nothing was picked -- the
     toolbox's shared ◐, then the system's light or dark -- belongs to no
     reader of this page, so the page starts on the theme its own <body>
     names instead: the template sets it there, which makes it sepia from
     the first frame, before this has run, and where it never runs.  A
     default and not a lock: a pick in the menu below wins, for as long as
     the tab. */
  if (t.themeFollows) {
    t.theme = document.body.dataset.theme || "paper";
    t.themeFollows = false;
  }
  const size = $("#xp-size"), out = $("#xp-size-out"), theme = $("#xp-theme");
  const base = t.base;
  function paint() {
    applyTypo(t);
    document.documentElement.style.setProperty("--xp-width", Math.round(t.width) + "px");
    if (size) size.value = t.base;
    if (out) out.textContent = Math.round(t.base / base * 100) + "%";
    if (theme) theme.value = t.theme;
  }
  if (size) size.addEventListener("input", () => {
    const v = parseFloat(size.value);
    if (!(v > 0)) return;
    // the column follows the text, as the studio's does
    t.width = Math.max(420, Math.min(1400, t.width / t.base * v));
    t.base = v;
    paint();
  });
  if (theme) theme.addEventListener("change", () => {
    t.theme = theme.value;
    t.themeFollows = false;
    paint();
  });
  // Escape shuts the menu, and a click anywhere else
  const menu = $(".xp-aa");
  if (menu) {
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && menu.open) { menu.open = false; e.preventDefault(); }
    });
    document.addEventListener("click", e => {
      if (menu.open && !menu.contains(e.target)) menu.open = false;
    });
  }
  paint();
  return {apply: () => applyTypo(t)};
}

/* ---------------------------------------------------------------- a document */

function xpDocument(place) {
  const sheet = $("#sheet");
  if (!sheet) return;
  document.body.dataset.lang = lang().code;
  place(sheet);
  bindFootnoteClouds(sheet);
  armClipReplay(sheet);
  bindExercises(sheet);
  xpCloud(sheet);
  // the glosses' filter: by the target text, its reading, its
  // transliteration or its translation, folded as the studio folds
  const filter = $(".xp-gl-filter");
  if (filter) filter.addEventListener("input", () => {
    const q = foldCase(filter.value.trim());
    $$(".xp-glosses tbody tr").forEach(tr => {
      tr.hidden = !!q && !foldCase(tr.textContent).includes(q);
    });
  });
}

/* THE TRANSLITERATION CLOUD (the owner, 2026-09-25): pointing at a word of
   the target language opens the studio's own cloud -- its transliteration,
   the kana for Japanese, the colours -- and what is changed in it is changed
   ON THIS OPEN PAGE ONLY.  Nothing is sent anywhere or kept anywhere: no
   server, no file, no storage that outlives the tab (bindPageCloud, app.js).

   The cloud itself is exactly the studio's, and says nothing of that.  The
   page says it once instead, over the screen and not inside the cloud (the
   owner, 2026-09-28): the first time a word or the cloud is clicked -- a tap
   on a phone is that click; a word of an exercise, answered with, is not --
   a line names it for a few seconds.  Whether it was said is a flag of this
   closure and not a stored one: a reload is a first time again, and nothing
   is written down.  The line takes no pointer, so it can never swallow the
   click that follows. */
function xpCloud(sheet) {
  bindPageCloud(sheet);
  let told = false, timer = null, notice = null;
  function dismiss() {
    clearTimeout(timer);
    if (!notice) return;
    const gone = notice;
    notice = null;
    gone.classList.remove("xp-unsaved-on");
    setTimeout(() => gone.remove(), 300);
  }
  document.addEventListener("click", e => {
    if (told || !e.target.closest) return;
    const hit = e.target.closest(".fapal, .fa[data-fa], .voce-fa[data-fa]");
    // a word of an exercise is answered with, not asked about: only the
    // cloud itself, opened over one, is a click that changes the page
    if (!hit || (!hit.matches(".fapal") && hit.closest(".exercise"))) return;
    told = true;
    notice = document.createElement("div");
    notice.className = "xp-unsaved";
    notice.setAttribute("role", "status");
    notice.setAttribute("aria-live", "polite");
    document.body.appendChild(notice);
    const mine = notice;
    requestAnimationFrame(() => {
      mine.textContent = "Changes made here are not saved";
      mine.classList.add("xp-unsaved-on");
    });
    timer = setTimeout(dismiss, 4000);
  }, true);
  document.addEventListener("keydown", e => { if (e.key === "Escape") dismiss(); });
}

/* ---------------------------------------------------------------- a deck: cram */

/* THE CRAM PAGE'S PRACTICE (static/decks.js, initCram), with the exercises
   read from this file rather than asked of a computer.  The same turns, in
   the same words: a random order; a scored exercise checked, a wrong one
   put back at the end and -- for matching and placement -- shown solved; a
   flashcard turned and marked by its reader; Skip; and at the end how it
   went, the ones wrong at least once and the ones skipped, each shown solved
   at a click, crammed again at another.  Nothing is scheduled. */
function xpCram(place, look) {
  let cards = [];
  try { cards = JSON.parse($("#parseh-cards").textContent) || []; } catch (e) { cards = []; }
  const stage = $("#cram-stage"), actions = $("#cram-actions");
  const done = $("#cram-done"), progress = $("#cram-progress");
  const result = $("#cram-result"), solution = $("#cram-solution");
  const solutionSheet = $(".dk-sheet", solution);
  const xpPlural = (n, one, many) => `${n} ${n === 1 ? one : (many || one + "s")}`;
  function xpEl(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  document.body.dataset.lang = lang().code;
  if (!cards.length) {
    stage.replaceChildren(xpEl("p", "pv-status", "This page holds no exercises."));
    return;
  }
  let pool = [], order = [], index = 0, current = null;
  let turnObserver = null, waitingAudio = null, tally = null;
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
      if (promise && promise.catch) promise.catch(() => { /* the browser wants a click first */ });
    };
    if (!window || audio.readyState >= 1) { play(); return; }
    waitingAudio = audio;
    audio.addEventListener("loadedmetadata", () => {
      if (waitingAudio !== audio) return;
      waitingAudio = null;
      play();
    }, {once: true});
  }
  // the ids a page carries more than once (a footnote of a solved exercise
  // beside the same exercise being answered) made its own
  function ownIds(sheet, mark) {
    $$("[id]", sheet).forEach(x => { x.id = mark + x.id; });
    $$("[aria-describedby]", sheet).forEach(x =>
      x.setAttribute("aria-describedby", mark + x.getAttribute("aria-describedby")));
  }
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
      progress.textContent = xpPlural(pool.length, "exercise");
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
    place(stage);
    look.apply();
    // a follow-up's own bar (Check step, Next step) is the page's own here (xpChain), as the studio's cram page does it
    const run = bindExercises(stage, {chainBar: false});
    const ex = run.exercises[0] || null;
    const chain = run.chains[0] || null;
    const kind = !ex || $(".ex-invalid", ex) ? "invalid"
      : chain ? "chain"
      : ex.dataset.primitive === "flashcard" ? "flashcard"
      : ex.dataset.scored === "1" ? "scored" : "invalid";
    current = {card, run, ex, kind, chain, checked: false};
    const flash = kind === "chain" ? null : $(".ex-flashcard", stage);
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
    $("#cram-step").hidden = true;
    $("#cram-check").textContent = "Check";
    $("#cram-next").hidden = kind !== "invalid";
    if (kind === "chain") { chain.onChange(() => xpChain(current)); xpChain(current); }
    $("#cram-skip").hidden = kind === "invalid";
    if (stage.getBoundingClientRect().top < 0) stage.scrollIntoView({block: "start"});
    if (kind === "flashcard") playSide("front");
    $("#cram-next").textContent = index === order.length - 1 ? "Finish" : "Next exercise";
  }

  const wrongList = $("#cram-wrong-list"), skippedList = $("#cram-skipped-list");
  let listed = 0;
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
      ? `${xpPlural(pool.length, "exercise")}: ${parts.join(", ")}.`
      : pool.length === 1 ? "Right the first time." : `All ${pool.length} right the first time.`;
    fillList(wrongList, wrong, card => {
      const n = tally.wrong.get(card.item.id);
      return "wrong " + (TIMES[n] || `${n} times`) +
        (tally.skipped.has(card.item.id) ? ", then skipped" : ", then right");
    });
    fillList(skippedList, skipped, () => "");
  }
  function fillList(section, list, says) {
    section.hidden = !list.length;
    $(".dk-cram-items", section).replaceChildren(...list.map(card => {
      const it = card.item;
      const li = xpEl("li", "dk-cram-entry");
      const b = xpEl("button", "dk-cram-item");
      b.type = "button";
      b.title = "Show it solved";
      b.setAttribute("aria-expanded", "false");
      const excerpt = xpEl("span", "dk-excerpt", it.excerpt || "(no text)");
      excerpt.dir = "auto";
      b.append(xpEl("span", "ex-kicker", it.label || it.subtype || "Exercise"), excerpt);
      const meta = says(card);
      if (meta) b.append(xpEl("span", "dk-cram-meta", meta));
      const box = xpEl("div", "dk-cram-solved");
      box.hidden = true;
      b.addEventListener("click", () => toggleSolved(b, box, card));
      li.append(b, box);
      return li;
    }));
    $('[data-x="again"]', section).onclick = () => start(list);
  }
  function toggleSolved(button, box, card) {
    const open = box.hidden;
    button.setAttribute("aria-expanded", String(open));
    box.hidden = !open;
    if (!open || box.firstChild) return;
    const sheet = xpEl("div", "sheet dk-sheet");
    sheet.dataset.lang = lang().code;
    sheet.innerHTML = card.solution || "";
    $$(".ex-edit, .ex-to-deck, .exercise-correction", sheet).forEach(x => x.remove());
    ownIds(sheet, `cram-done-${++listed}-`);
    box.replaceChildren(sheet);
    place(sheet);
    look.apply();
    bindExercises(sheet, {preview: true});
  }
  function showSolution(checked) {
    if (current !== checked) return;
    solutionSheet.innerHTML = checked.card.solution || "";
    $$(".ex-edit, .ex-to-deck, .exercise-correction, .ex-explanation, .ex-image, .ex-audio, .footnotes",
       solutionSheet).forEach(x => x.remove());
    ownIds(solutionSheet, "cram-solution-");
    if (!$(".exercise", solutionSheet)) return;
    solution.hidden = false;
    place(solutionSheet);
    look.apply();
    bindExercises(solutionSheet, {preview: true});
  }
  /* A FOLLOW-UP, CRAMMED (decks.js cramChain): the steps one after the other, Check step (Show answer for a card), Next
     step; right only when every scored step was right, and a chain that was not comes round again whole. */
  function xpChain(shown) {
    if (current !== shown || shown.kind !== "chain") return;
    const c = shown.chain, check = $("#cram-check"), showBtn = $("#cram-show"), step = $("#cram-step");
    if (c.finished) {
      if (shown.checked) return;
      shown.checked = true;
      const good = !c.scored || c.rights === c.scored;
      judged(shown.card, good);
      if (!good) order.push(shown.card);
      check.hidden = showBtn.hidden = step.hidden = true;
      $("#cram-skip").hidden = true;
      result.textContent = c.scored ? `${c.rights} of ${c.scored} steps right` : `All ${c.n} steps seen`;
      result.className = "dk-result " + (good ? "ok" : "err");
      result.hidden = false;
      progress.textContent = `${index + 1} of ${order.length}`;
      $("#cram-next").hidden = false;
      $("#cram-next").textContent = index === order.length - 1 ? "Finish" : "Next exercise";
      return;
    }
    result.hidden = true;
    showBtn.disabled = false;
    if (!c.checked) {
      step.hidden = true;
      check.hidden = c.card;
      showBtn.hidden = !c.card;
      check.textContent = "Check step";
    } else {
      check.hidden = showBtn.hidden = true;
      step.hidden = false;
      result.textContent = c.card ? "" : (c.wrongHere ? "Not quite" : "Correct");
      result.className = "dk-result " + (c.wrongHere ? "err" : "ok");
      result.hidden = c.card;
      step.focus({preventScroll: true});
    }
  }
  $("#cram-step").addEventListener("click", () => { if (current && current.kind === "chain") current.chain.next(); });
  $("#cram-check").addEventListener("click", () => {
    if (current && current.kind === "chain") { current.chain.check(); return; }
    if (!current || current.kind !== "scored" || current.checked) return;
    const good = current.run.judge(current.ex);
    current.checked = true;
    judged(current.card, good);
    if (!good) order.push(current.card);
    const body = $(".ex-body", current.ex);
    if (body) body.inert = true;
    $("#cram-check").hidden = $("#cram-skip").hidden = true;
    result.textContent = good ? "Correct" : "Not quite";
    result.className = "dk-result " + (good ? "ok" : "err");
    result.hidden = false;
    progress.textContent = `${index + 1} of ${order.length}`;
    $("#cram-next").hidden = false;
    $("#cram-next").textContent = index === order.length - 1 ? "Finish" : "Next exercise";
    if (!good && ["matching", "placement"].includes(current.ex.dataset.primitive))
      showSolution(current);
  });
  $("#cram-show").addEventListener("click", () => {
    if (current && current.kind === "chain") { current.chain.check(); return; }
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
  $("#cram-skip").addEventListener("click", () => {
    if (!current || current.checked) return;
    const id = current.card.item.id;
    tally.skipped.add(id);
    order = order.filter((card, i) => i <= index || card.item.id !== id);
    index++;
    show();
  });
  $("#cram-next").addEventListener("click", () => {
    if (current && current.kind === "invalid") tally.skipped.add(current.card.item.id);
    index++;
    show();
  });
  $("#cram-again").addEventListener("click", () => start(pool));
  start(cards);
}

/* ---------------------------------------------------------------- boot */

xpMath();
const xpPlace = xpMedia();
const xpLooks = xpLook();
if (document.body.dataset.export === "deck") xpCram(xpPlace, xpLooks);
else xpDocument(xpPlace);
