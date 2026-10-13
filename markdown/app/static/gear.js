// SPDX-License-Identifier: GPL-3.0-or-later
/* exlex studio — THE GEAR of a document, of the editor and of the exercises
   (a0.5.0, plan §6).

   Every page of Parseh has one panel for the settings of the page it is on, a
   ⚙ in its bar (lib/pagesettings.js draws the button and the panel; this file
   says what is IN it, for five pages of the studio: `body[data-page]` is doc,
   edit, deck, study or cram).  What each of them held before is in the panel
   now, as a row with a name and one sentence:

     a document   Text · Exercises · Page · Zoom · Colours · Interface
     the editor   Text · Zoom · Colours · Editor              (no phone layout)
     a deck, studying it, cramming it
                  Text (four rows) · Exercises · Zoom · Colours · Interface

   THE ROWS ARE THE PAGE'S OWN STATE, NOT COPIES OF IT.  The text rows read and
   write what app.js keeps (studioTypo: the same two keys of localStorage, the
   same sheet, the PDF's scale), the two exercise switches turn what a card's
   own buttons turn (setTransliterationsHidden, setDragOn), "Hide the bars" is
   the bars' own button's (setBarsOff), the editor's direction is the one of
   its ⇤ RTL button.  Each says so to the others (`parseh:studio`, studioTypo's
   subscribers), so a row follows a change made anywhere else on the page while
   the panel is up -- and neither side has a second copy to drift from the
   first.  The Text group of the pages of exercises is the documents' own: one
   stored value (exlex-typo:global), so what is set in one is read in the
   other.

   `Aa` (a document's toolbar) opens the gear at its Text group, on every
   width; there is one set of sliders in Parseh and this is where it is.

   THE THEME has one function for every page of the studio (app.js,
   paintTheme): the gear's Colours hand it in as `apply`, and ◐ on the bars
   is the same function's.

   WHERE THE BUTTON STANDS.  In the browser layout: the right end of the bar's
   row of buttons, after ◐ (templates carry both in a `.bar-tail`, which keeps
   them on the screen where that row scrolls sideways).  On a phone: the
   mobile bar, after ◐ -- and on the study and cram pages, which have no bar
   there, the row of the exercise's title.  The Browser | Mobile switch left
   the bars of the pages that have a gear and lives in its Interface group.

   A studio run alone has no /lib/ of the toolbox's, bar the two files of the
   gear that server.py answers for itself; without lib/prefs.js the theme stays
   on this device and the panel says so. */
(function () {
"use strict";

const kind = document.body.dataset.page;
if (!["doc", "edit", "deck", "study", "cram"].includes(kind)) return;

/* WITHOUT THE TOOLKIT THE PAGE STILL WORKS, as the pages do without explain.js
   and keep.js: the one control that would have opened it has nothing to open. */
const aa = document.getElementById("btn-typo");
if (!window.ParsehGear) {
  if (aa) aa.hidden = true;
  return;
}

const T = window.ParsehStudioTypo;
const G = window.ParsehGear;
const SAVED = "Saved on this device.";

/* WHAT A SWITCH OF THE PAGE SAYS TO ITS ROW: `parseh:studio`, {what}.  The
   page's own buttons say it (app.js: the transliterations, the drag, the
   bars); this listens for one of them and answers with the way to stop. */
const heard = what => cb => {
  const fn = e => { if (e.detail && e.detail.what === what) cb(); };
  document.addEventListener("parseh:studio", fn);
  return () => document.removeEventListener("parseh:studio", fn);
};

/* ------------------------------------------------------------------ Text */

const nameOf = () => lang().name;
function textGroup(full) {
  const row = r => Object.assign({kind: "slider", watch: T.subscribe}, r);
  const rows = [
    row({id: "fa", label: () => nameOf() + " text size",
         help: () => `How big the ${nameOf()} text is compared with the Latin text around it (1× = the same size). ` +
                     (full ? "The PDF you build uses the same size." : "Documents use the same size."),
         min: 0.8, max: 2.6, step: 0.02, format: v => v.toFixed(2) + "×",
         get: () => T.get().fa, set: v => { T.set({fa: v}); }}),
    row({id: "base", label: "Latin text size",
         help: () => `How big the Latin-script text (the explanations around the ${nameOf()}) is, from 13 to 23 pixels.` +
                     (full ? " The text width follows it unless you set the width yourself." : ""),
         min: 13, max: 23, step: 0.5, format: v => v + " px",
         get: () => T.get().base, set: v => { T.set({base: v}); }}),
  ];
  if (full) rows.push(
    row({id: "width", label: "Text width",
         help: "How wide the column of text may grow on a wide screen; on a narrow screen it always fits.",
         min: 420, max: 1400, step: 1, format: v => Math.round(v) + " px",
         get: () => T.get().width, set: v => { T.set({width: v}); }}));
  rows.push(
    row({id: "lead", label: "Line spacing",
         help: "The space between lines: 1 is the usual, more is airier.",
         min: 1.15, max: 2, step: 0.05, format: v => v.toFixed(2),
         get: () => T.get().lead, set: v => { T.set({lead: v}); }}));
  if (full) rows.push(
    row({id: "voce", label: "Headword size",
         help: "How big the word at the top of each dictionary-style entry is, as a multiple of the text size.",
         min: 2.2, max: 4.6, step: 0.1, format: v => v.toFixed(1) + "×",
         get: () => T.get().voce, set: v => { T.set({voce: v}); }}));
  rows.push(
    {id: "justify", kind: "switch", label: "Justify the text",
     help: "Straight left and right edges, with words hyphenated at line ends, the way the PDF sets it.",
     get: () => !!T.get().justify, set: v => { T.set({justify: !!v}); }, watch: T.subscribe});
  if (full) rows.push(
    {id: "reset", kind: "action", label: "Put the text back to normal",
     help: "Sets every size above back to the one the PDF starts from.",
     onClick: () => { T.reset(); toast("The text is back to the PDF’s own sizes"); }});
  return {id: "text", title: "Text", caption: SAVED, rows};
}

/* ------------------------------------------------------------- Exercises */

const exercisesGroup = () => ({
  id: "exercises", title: "Exercises", caption: SAVED,
  rows: [
    {id: "translit", kind: "switch", label: "Hide transliterations",
     help: "Hides the line that spells how a word sounds in Latin letters on every exercise flashcard, so you read the script itself.",
     get: () => hideExerciseTransliterations, set: v => setTransliterationsHidden(v),
     watch: heard("transliteration")},
    {id: "drag", kind: "switch", label: "Drag to answer",
     help: "Lets you drag words into place in exercises that offer it. Off by default on a touch screen, where tapping is easier.",
     get: () => dragIsOn(), set: v => setDragOn(v), watch: heard("drag")},
  ]
});

const pageGroup = () => ({
  id: "page", title: "Page", caption: SAVED,
  rows: [
    {id: "bars", kind: "switch", label: "Hide the bars",
     help: "Puts the header away so the text has the whole window; a small ⌄ at the top corner brings it back.",
     get: () => barsAreOff(), set: v => setBarsOff(v), watch: heard("bars")},
  ]
});

/* --------------------------------------------------------------- Editor */

/* The direction of the source box (static/editor.js keeps it, one document at
   a time, and offers it as window.ParsehStudioEditorDir) */
const editorGroup = () => ({
  id: "editor", title: "Editor", caption: "Saved on this device, for this document.",
  rows: [
    {id: "dir", kind: "switch", label: "Write the source right to left",
     help: "Which way the source text box runs, for a right-to-left language. Remembered for this document.",
     when: () => !!window.ParsehStudioEditorDir,
     get: () => window.ParsehStudioEditorDir.isRtl(),
     set: v => window.ParsehStudioEditorDir.set(!!v),
     watch: cb => window.ParsehStudioEditorDir ? window.ParsehStudioEditorDir.subscribe(cb) : () => {}},
    {id: "tab", kind: "switch", label: "Preview in its own tab",
     help: "Gives the whole window to the text and draws the preview in another tab of the browser, as the finished page, from what you type (unsaved changes included). Double-click anything in it to land on its text. Remembered on this device.",
     when: () => !!(window.ParsehStudioLive && window.ParsehStudioLive.available),
     get: () => window.ParsehStudioLive.isOwnTab(),
     set: v => window.ParsehStudioLive.set(!!v),
     watch: cb => window.ParsehStudioLive ? window.ParsehStudioLive.subscribe(cb) : () => {}},
    {id: "opentab", kind: "action", label: "Open the preview tab",
     help: "Opens the preview in its own tab, or brings that tab forward if it is already open.",
     when: () => !!(window.ParsehStudioLive && window.ParsehStudioLive.available),
     onClick: () => window.ParsehStudioLive.open()},
  ]
});

/* ----------------------------------------------------------- the three
   standard groups, and the theme's one function */

function colours() {
  const g = G.std.colours({apply: () => paintTheme()});
  // the theme follows the person only where the toolbox's own script is there
  // to carry it (lib/prefs.js): a studio run alone keeps it on this device
  if (!window.ParsehPrefs) g.caption = SAVED;
  return g;
}

/* ------------------------------------------------------------ the spec */

const mobileNow = () => document.documentElement.getAttribute("data-mode") === "mobile";
const first = (...sel) => () => {
  for (const s of sel) { const e = document.querySelector(s); if (e) return e; }
  return null;
};

const spec = {
  page: kind,
  host: {
    // the row of the browser bar that keeps ◐ and ⚙ in view (templates: .bar-tail)
    browser: first(".topbar .bar-tail", ".topbar .topbar-actions", ".topbar"),
    // a phone's bar -- or, where the page has none (the exercise on a phone), its title's row
    mobile: first(".m-topbar", ".dk-studyhead"),
  },
  mobileMode: mobileNow,
  groups: [],
};
// the toolbox's own settings door is only there when the toolbox is
if (!window.ParsehPrefs) spec.titles = {foot: false};

if (kind === "doc") {
  spec.groups = [textGroup(true), exercisesGroup(), pageGroup(), G.std.zoom(), colours(), G.std["interface"]()];
} else if (kind === "edit") {
  // the editor has no phone layout, whatever the device's mode says: its bar is the one bar
  spec.mobileMode = () => false;
  spec.onMode = () => () => {};
  spec.groups = [textGroup(true), G.std.zoom(), colours(), editorGroup()];
} else {
  spec.groups = [textGroup(false), exercisesGroup(), G.std.zoom(), colours(), G.std["interface"]()];
}

const gear = G.mount(spec);

/* ------------------------------------------------------------------- Aa */

/* `Aa` OPENS THE GEAR AT TEXT, and a second press shuts it.  A press OUTSIDE the
   popover shuts it before the button's own handler runs (the toolkit hears the
   click first, as it must, and the button is outside), so what the press
   found -- whether the panel was up and whether it was up at Text -- is read in
   the capture phase, before anyone has acted on it.  A panel opened by the
   gear's own button is not "at Text": Aa then takes it there. */
if (aa) {
  let at = "", foundUp = false, foundAt = "";
  document.addEventListener("click", e => {
    if (e.target.closest && e.target.closest("#btn-typo")) { foundUp = gear.isOpen(); foundAt = at; }
  }, true);
  gear.onToggle(open => {
    aa.setAttribute("aria-expanded", String(open));
    if (!open) at = "";
  });
  aa.setAttribute("aria-expanded", "false");
  aa.addEventListener("click", () => {
    if (foundUp && foundAt === "text") { if (gear.isOpen()) gear.close(); return; }
    at = "text";
    gear.open("text");
  });
}
})();
