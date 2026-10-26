# The mobile mode — the design

Parseh has two interfaces. The **browser** one is every page as it has always
been, with everything that makes and changes content on it. The **mobile** one
is a second set of pages made to be *read* on a phone: streamlined, a single
column, big targets for a finger, and **no editing controls at all**. It is for
looking at what is there — reading a book, watching a video, reading a note,
studying a deck — and never for writing it.

The mode is a choice, made with the **Browser | Mobile** switch in the hub's top
bar (and in the bar of every mobile page), and it holds across every page and
every reload until it is switched back. It was built one interface at a time,
and today the hub, the books (their shelf and every book's reader), the
exercise decks, the videos (their shelf, a channel, and the player with its
transcript) and the studio's pages (its library, a document and its notes, to
read) all have their mobile layouts. Only the guide has none, so its door
opens the browser pages: **a page without a mobile version always falls back
to its browser version.**

A phone is held **sideways** as often as upright — more, to read — so every
mobile layout is made for both: from 600px wide the columns widen and go two
to a row, the reader's controls take one line, and studying puts its buttons
in a column down the right edge (*A phone held sideways*, below). And the
mobile interface can be **installed as an app**, from the phone's browser: an
icon on the home screen that opens it on the whole screen, with no address bar
(*Parseh as an app*, below).

## What it is not

**It is not the phone adjustments the pages already make.** Those follow the
width of the screen, in either mode, and nothing about the mobile mode changes
them. They stay exactly as they are:

* the bar that gets out of the way on a scroll under 560px (`bars()` in
  `lib/parseh.js`, `body.barhidden`), and the reader's and the studio's bars
  put away by hand (`body.chrome-off`) — in the mobile mode the same `bars()`
  follows the scroll at every width, and only the mobile pages' own sheets
  answer it there (a phone held sideways is wider than 560px); a browser page
  opened in the mobile mode still hides its bar under 560px only;
* the layouts under 560px, 620px, 720px and 820px in `lib/parseh.css`, the
  reader, the player, the card kit, the timeline and the studio;
* a tap that opens a gloss on a screen that claims a hover it never delivers,
  and the studio's drag handles that are off on a coarse pointer.

A mobile page is free to use the same classes (the mobile hub's bar is a
`.parseh-bar`, so it hides on a phone scroll like every other one), but nothing
in the mobile mode restates or undoes them.

**It is not a lock.** Nothing is refused in the mobile mode. A browser page
reached by typing its address, or from a bookmark, opens and works as it always
does, editing and all. The mobile pages simply do not *show* the controls that
edit; the server never checks the mode before doing what it is asked.

## How the mode is stored

* **`localStorage` `parseh_mode`**: `browser` or `mobile`. Nothing stored means
  `browser`. This is the one that decides.
* **A cookie of the same name**, `parseh_mode=mobile|browser; Path=/;
  SameSite=Lax; Max-Age=31536000` — a year, for the whole site. It mirrors the
  stored value so that the server, and the pages that do not load
  `lib/parseh.js`, can read the mode too. It is not `Secure`, because `serve.py`
  can speak plain http (`--http`, or a Windows machine without OpenSSL). Every
  page that loads `parseh.js` rewrites it whenever it disagrees with
  `localStorage`, so the two never differ for longer than one page load. When
  `localStorage` holds nothing — blocked, or never written on this origin — the
  cookie answers.
* **`<html data-mode="browser|mobile">`**, set by `parseh.js` as soon as it is
  parsed. The script is in `<head>`, as it is for the theme, so a page's
  stylesheet has switched layouts before the first paint and never flashes the
  other one. Another tab follows a switch made in this one (the `storage`
  event), and so does a page brought back by the back button.

`Parseh.mode` is the API, in `lib/parseh.js`:

| | |
|---|---|
| `get()` | `'browser'` or `'mobile'` |
| `set(m)` | store `m` (anything else is ignored), write the cookie, apply it |
| `isMobile()` | `get() === 'mobile'` |
| `route(url)` | where a link to `url` leads in this mode (below) |
| `onChange(fn)` | `fn(mode)` after every change of the mode on this page; returns a function that takes `fn` off again |
| `apply()` | put the stored mode on the page again |
| `pages` | the registry of mobile versions (below) |
| `KEY` | `'parseh_mode'` |

The switch itself is any pair of buttons with `data-parseh-mode="browser"` and
`data-parseh-mode="mobile"`, wrapped in a `.parseh-mode` group: `parseh.js` wires
them wherever they are, and `serve.mode_switch()` writes them. The pressed half
is drawn from `<html data-mode>`, not from `aria-pressed` (which the script keeps
up to date for a screen reader), so it is right from the first paint.

A bar that carries the switch stays one row on a phone, as the hub's bar was
before it: under 560px the browser hub's bar drops *the hub* and the word after
the stop button's ⏻, and under 420px the name beside the home glyph, and draws
the switch a little tighter (`lib/parseh.css`); the mobile bar drops the name
beside its home glyph under 360px (`lib/mobile.css`). The words are hidden from
the eye only (each sits in a `.word` span), so a screen reader still reads them.

A page that is **only** a mobile version, at an address of its own (`/m/books/`),
names the page it stands for in `<body data-browser-page="/books/">`: switched to
the browser mode — there, or in another tab — it goes to that page
(`location.replace`), since it has nothing of its own to show in that mode. Only
on a switch: opened in the browser mode (a link kept from a phone), it opens as it
is and says, in a line only that mode shows, where its browser page is. Nothing
goes the other way — a browser page may hold somebody's unsaved work.

### Reading the mode where `parseh.js` is not loaded

The studio's and the exercises' pages (`markdown/app/templates/*`, `app.js`,
`decks.js`) do not load `parseh.js`. The exercise decks' pages have a mobile
layout, so they read the mode the way `parseh.js` does, the stored value first
and the cookie when there is none — in their `<head>`, before anything is drawn
(`deckroutes.MODE_SCRIPT`, which every deck template takes as `{{MODE_SCRIPT}}`),
and `decks.js` keeps the switch from there on (`bindMode`: stored, mirrored in the
cookie, drawn, and followed when another tab changes it). The studio's own pages
read it from `<html data-mode>` and the gear's *Interface* group (a0.5.0,
`markdown/app/static/gear.js`, on `lib/pagesettings.js`) sets it the same way the
switch does: the stored value, the cookie, `html[data-mode]` and a `parseh:mode`
event -- the Browser | Mobile switch left the bars of the pages that have a gear (a
document, the editor, a deck, studying it, cramming it) and lives there; the hub's
and the decks' own list keep theirs in the bar. In JavaScript, the reading is:

```js
function parsehMode() {
  try {
    var m = localStorage.getItem('parseh_mode');
    if (m === 'browser' || m === 'mobile') return m;
  } catch (e) {}
  var c = /(?:^|;\s*)parseh_mode=(browser|mobile)(?:;|$)/.exec(document.cookie || '');
  return c ? c[1] : 'browser';
}
```

The server reads the cookie (`http.cookies.SimpleCookie(self.headers.get("Cookie",
""))`, then `.get("parseh_mode")`). It may use it to pick a default or to write a
page's mobile layout at the page's own address. It must never use it to redirect
a browser address somewhere else or to refuse a request.

## Links: the registry and the fallback

`MOBILE_PAGES`, in `lib/parseh.js` (`Parseh.mode.pages`), lists the pages that
have a mobile version:

```js
var MOBILE_PAGES = [
  // the hub is its own mobile version: the one page carries both layouts
  { match: /^\/(index\.html)?$/, to: '/' },
  // the book library is a static page: its mobile version is one of its own
  { match: /^\/books\/(index\.html)?$/, to: '/m/books/' },
  // a book's reader is its own mobile version (the layer, below)
  { match: /^(\/books\/(?:[^\/]+\/){1,2}reader\/)(index\.html)?$/, to: '$1' },
  // the exercise decks: each page carries both layouts
  { match: /^\/exercises\/(.*)$/, to: '/exercises/$1' },
  // the licences: both layouts, in one column
  { match: /^\/licences\/$/, to: '/licences/' },
  // the chunks flagged to review later: both layouts, in one column
  { match: /^\/later\/$/, to: '/later/' }
];
```

`match` is a regular expression over the whole path (anchored, and not `g`);
`to` is handed to `String.replace`, so it may say `$1` for part of the match —
`{ match: /^\/youtube\/v\/([^/]+)\/$/, to: '/m/v/$1/' }` — or be a function. The
query and the fragment are carried over. `route(url)` answers the mobile address
when the mode is mobile and a row matches a same-origin `url`, and `url` itself
otherwise: **the browser page is always the fallback.** A page that is its own
mobile version is registered too, mapped onto itself: the registry is the list of
what has a mobile version, and says so of every page that has one.

On a **mobile page** — one whose `<body>` carries `data-mobile-page` — every link
followed in the mobile mode goes where `route()` says. The link's `href` is
rewritten in the capture phase, before the browser acts on the click, rather than
the click being cancelled and the page moved by hand: so a ctrl- or cmd-click
into a new tab, a middle click, a long press's *open in new tab* and a
`target=_blank` all get the mobile address too. The address the page was written
with is kept in `data-parseh-href` and put back when the mode goes back to
browser. Two kinds of link are never routed: a download (`download`), and a link
marked `data-no-route` — for a mobile page that deliberately offers its browser
version.

## Adding a mobile page

1. **Write it.** In one of three ways, whichever the browser page allows:
   - at an address of its own, as the book shelf is (`/m/books/`, `lib/mobile.py`
     — served like any other page, added to `serve.py`'s routes, and naming its
     browser page in `data-browser-page`): the way for a page written as a file
     on disk, which a layout added to it would not reach until it is written
     again;
   - as a second layout of the same page, the way the hub and the exercise decks
     are: its browser elements marked `data-layout="browser"`, its mobile ones
     `data-layout="mobile"`, and the sheet (`lib/mobile.css`, or the studio's
     `static/mobile.css`) shows one or the other by `<html data-mode>`;
   - as a layer over a page BUILT for its content, the way a book's reader is: a
     script and a sheet in `lib/` that `parseh.js` loads into the page, so every
     page built before the mobile interface gets it without being built again.
     The layer lays the page's own controls out for a phone and hides what edits
     — it moves, copies and rewrites none of them — and refuses the gestures that
     would write.
2. **Mark it and load the shared files.** `<body data-mobile-page>`, and in
   `<head>` `/lib/parseh.css`, `/lib/langs.css`, `/lib/mobile.css`, then
   `/lib/parseh.js`. A new shared file goes into `serve.py`'s `STATIC_FILES`, or
   it is a 404.
3. **Register it** in `MOBILE_PAGES`. From then on every link to its browser
   address, on every mobile page, lands on it in the mobile mode.
4. **Show nothing that edits.** What a reader or a learner does stays: read,
   play, look a word up, open a gloss, answer a due card. What makes or changes
   content does not appear: edit, add, delete, build, upload, download a bundle,
   sync, the clip tray, the dictionary setup, stop the server. When in doubt, it
   is not on the mobile page; the browser page still has it.
5. **Design for a phone first.** One column, `--m-col` wide on anything larger
   and centred there; every target at least 48px; colours only from
   `parseh.css`'s tokens, so light, dark and sepia all follow (check the three).
   Nothing only a swipe can reach, either: the mobile mode is also opened on a
   desktop, where a mouse cannot swipe a row sideways and a wheel over it
   scrolls the page — the hub's chip row wraps under
   `(hover:hover) and (pointer:fine)` for that reason.
6. **Every language.** Right-to-left Persian and Arabic, the Latin languages,
   Japanese and Chinese (vertical text where the browser page has it), Hindi in
   Devanagari: the registry's tokens (`langs.css`, `data-lang`) give each its
   face and direction, as on the browser pages.
7. **Test it where it is drawn.** `tests/mobile_mode.mjs` drives the hub, and
   `tests/mobile_pages.mjs` the book shelf, the readers, the decks and the app,
   in a headless Chromium as a touch phone held upright (390x844 and 360x740)
   and sideways (844x390) and with a mouse, and measures what is on the
   screen; a new page gets the same: that its
   layout is the one shown, that nothing on it edits, that its links route,
   that the switch back to browser restores the browser page.
   `tests/test_mobile_mode.py` and `tests/test_mobile_pages.py` read the markup
   and the sheets: every rule in `lib/mobile.css` hangs off a mobile class
   (`m-…`, `html.m-reader`) or `[data-layout=…]`, and every rule in the studio's
   `static/mobile.css` off `html[data-mode=mobile]`, so neither can reach a
   browser page.

## The pages

| Browser page | Mobile version |
|---|---|
| the hub, `/` | **done**: the same page, its mobile layout — the four doors (books, videos, the studio's notes, the exercises) with their counts, two to a row from 600px, the language chips in one row that scrolls sideways and always shows the picked one (with a mouse, in rows that wrap), the guide, and the door to installing the mobile interface as an app (not drawn inside the app) |
| the book library, `/books/` | **done**: the shelf, `/m/books/` — below |
| a book's reader | **done**: the same page, its mobile layer — below |
| the videos, `/youtube/`, a channel, and the player | to come: the index, and the player with its transcript and glosses |
| the studio's library, `/studio/`, and a document, `/studio/doc/<id>` | to come: the notes to read |
| the exercise decks, `/exercises/`, a deck, studying it and cramming it | **done**: each page, its mobile layout — below |
| the guide, `/guide/` | to come, if it needs more than it has |

### The book shelf, `/m/books/`

`lib/mobile.py` writes it on every request from the shelf itself — the browser
library is a static file (`lib/make_index.py`) written when a book is built or
put on the shelf, so a layout added to it would reach nobody's library until the
next build. The mobile bar (home, "Books", the switch, the theme); the chips, in
one row that scrolls sideways (wrapping for a mouse), filtering the books by
language; and each book as the library's card says it — its title and author in
the book's own face and direction, the Latin line, the blurb in three lines, the
chapters, whether it is narrated and how much is timed — the whole card a link to
its reader, at least 96px high, two to a row from 600px (a language's heading
the whole width). A book whose reader has never been built opens
nothing, and says it is built in the browser interface. A book read on this
phone says how far ("read on · 40%", and a line along the card's foot): the
reader keeps its place in the browser under `bk_pos:` and its address
(`lib/tex2html.py`, `save()`), and the shelf reads it, never writes it, and links
the address the place was kept under. Nothing that manages the shelf is on it:
no delete, no build, no bundle in or out, no backup, no stop.

### A book's reader: the mobile layer

A reader is built for its book, and `lib/parseh.js` — which every reader loads,
however old — puts `html.m-reader` on it and loads `lib/mobile.css` and
`lib/mobilereader.js` beside itself, the way it loads `lib/activity.js`. In the
mobile mode:

* **The header is laid out again, for a thumb.** Its rows stop being boxes
  (`display: contents`), so each control is an item of the header, placed by
  `order`. The first line is the way out and what a reader reaches for: the
  hub, the shelf, ☰ the contents, Aa the text size, and ⚙ the page's settings — five
  48px targets (and ⚑ later, beside them, once the book has a flag), which fit a 320px phone, whatever the book and however the phone is
  held. The recording is not moved from the header any more: ▶ leaves it (it
  stays on the page, unshown, as the button the dock presses) and the dock
  below does the moving.
  ⚙ opens the rest as ONE sheet from the foot of the screen, half its height at rest, the text
  still showing above it (a0.5.0; `lib/pagesettings.js`, filled for a reader by
  `lib/gear-reader.js`, which drives the reader's own controls from its rows, so that
  every one of them stays in the DOM).  **The sheet has two stages** (a0.5.4): it opens on
  an INDEX of the page's themes -- one 56px row for each, its name and one line saying
  what it is set to (`Group.summary`, else the toolkit joins the drawn rows' values with
  " · "; a switch says its `Row.short` where it is on; 50px rows where seven would not
  fit a small phone's half sheet) -- and a tap slides it to ONE theme (‹ and the back
  gesture return: a second history entry); `gear.open('text')`, which Aa calls, lands on
  the theme.  Half is the resting height, TALL (the window less 48px) by a drag up on
  the head or a tap on its grab line, remembered on the device (`parseh_gear_tall`); a
  borrowed node (the Keep buttons) stands in its row only while its theme is on stage.
  The themes are: *Levels & reading* (the levels, each with its tick
  and its name, Diacritics, gloss, the cloud, hide the bars), *Listening* (keep going,
  repeat and the pause between repeats, wait at each new chapter, pause while a gloss is
  open, how far ↺ and ↻ move, the speed, listen on its own), *Looking a word up* (the
  dictionary, its definitions and the way to get one), *Text*, *Zoom*, *Colours* and
  *Interface* (the switch, and the Keep buttons: *Away from the computer*). A group with
  nothing this book offers is not drawn. While listening on its own, a second line under
  the first holds highlight, keep in view, where the recording is (0:12 / 3:40) and the seek.
* **The dock: the recording, under the thumb** (`lib/narrctl.js`, the owner's
  choices of 2026-09-22). A narrated book floats three buttons at the foot of
  the screen, in the two corners a thumb owns without the hand shifting its
  grip: **↺** in the left corner, **⏯** and **↻** in the right, with the
  **speed** as a chip above them. They are 56px, not the 48px a target must be
  at least, because they are pressed again and again and often without
  looking; the page keeps a foot's room under its last line so nothing is read
  through them, and they sit above the phone's own bottom bar
  (`env(safe-area-inset-bottom)`).
  They **fade when nothing is touched** for four seconds and are whole again
  at the first touch, key or wheel — a page that scrolls *itself*, as this one
  does all the while a narration plays, is not a touch, so they do not stay
  bright over the text being read. ⏯ is the reader's own ▶ pressed: everything
  play does — keep going, the loop, the fold ahead, the reading place — stays
  the reader's own business, and the dock only mirrors whether the sound is
  going.
* **↺ and ↻ move the recording** back and on by so many seconds: ten, until
  told otherwise. **Holding either one opens the seconds to choose from —
  5 · 10 · 15 · 30 · 60** — and because a hold cannot be seen, the gear's *Listening*
  group shows the same row (*Skip distance*), and the first tap of ↺ or ↻ says "hold ↺
  or ↻ to choose the seconds", once and never again (`bk_skiphint`). The
  number is one for every book, kept in this browser as `bk_skip` beside the
  reader's gap and rate. The reader plays by subparagraph, so the move takes
  the reading place with it: the subparagraph the recording lands in becomes
  the place — the mark, the place kept for next time, and where the playing
  stops — found as the reader's own *follow* finds it (`subAtTime`). In
  *listen* there is no reading place, and only the fold ahead is worked out
  again. All of that is the reader's own state, the top-level bindings of its
  script, which every classic script on the page shares; a reader built before
  one of them existed has the recording moved, and follows as it can. Paused,
  it stays paused. A book with no narration has no dock and no row.
* **hover ⏸: the narration waits while a gloss is open** (a0.4.1; the owner,
  2026-09-25 and 2026-09-28; `lib/mobilereader.js`, "pause on touch"). The
  video's switch (`#hoverpause`, whose 350 ms grace it keeps), made here in BOTH modes
  and kept in the header out of sight, since the gear's row *Pause while a gloss is
  open* (under *Glosses in a cloud*) presses it -- and not drawn in a book with no
  narration (`body.noaudio`: the gear has no row for it there either).
  **Off until it is turned on, and kept on THIS device only**: `bk_hoverpause`,
  '1' or '0', in `localStorage` -- never in `prefs.KEYS`, so nothing on the
  computer changes, and one device's choice cannot flip another's. With it on, the reader's
  own `openCloud` (wrapped, once, by its bare name: every caller resolves it so)
  presses ▶ if the narration is playing and remembers that *it* paused it
  (`hpHeld`); the wrapper of `closeCloud` starts the 350 ms grace, and when it
  ends ▶ is pressed again unless a cloud is open again. **The press is a click
  that does not bubble** (`dispatchEvent(new MouseEvent('click', {bubbles:
  false}))`): a bubbling one reaches the page's "a click outside the cloud
  closes it" and shuts the very cloud the tap just opened -- `narrHold`'s
  `b.click()` gets away with it only because it hides the cloud first. It
  cannot fight the dictionary's sheet because each owner pauses only what it
  sees playing and resumes only what it paused: with the cloud's pause standing
  the sheet's `narrHold` finds the narration paused, and the sheet's close
  (which shuts the cloud, then asks for the grace again) is the one resume.
  The audio's own *play* gives the debt up, so a narration the person paused, or
  played and paused under the cloud, is never started; a tap on another word
  has no close between and so no resume; the reader opening its cloud again for
  a late model (`cloudFor` emptied, `cloudC` still set) is not a new open.
  **Loop's wait** (the audio paused, playback in the reader's `waiting` timer,
  up to five seconds): the cloud takes the timer and the grace gives it back
  as `playSub(cur, false)`; keep-going's tenth of a second is left alone.
  **The reader's own sheets** (browser mode: cards, the chunk's editor, the
  fold, the LLM gloss, the narration's, the sections', the downloads') each
  record whether the narration was playing and put it back themselves; one up
  when the grace ends means the narration is theirs, so the debt is dropped and
  nothing is started -- the narration stays paused until ▶ is pressed. On a
  real touch device the resume is a timer, not inside a touch (Chrome allows
  it, the element having been started by one; the sheet's `narrGoOn` takes the
  same risk), and ⏸ may be drawn as a coloured emoji on Android
  (`lib/narrctl.js`, the owner's report of 2026-09-23) -- `HP_LABEL` is the one
  place to change. Not driven headless: both are on the owner's Parseh-test
  checklist.
* **The speed is a chip**, saying 1.5×, and a tap opens the row: 0.5 · 0.6 ·
  0.75 · 0.9 · 1 · 1.1 · 1.25 · 1.5 · 1.75 · 2 — the reader's own menu, with
  the two speeds the owner asked for added to it. The chip *is* that menu: it
  sets its value and lets the reader's own handler run, so the rate is saved
  and applied exactly as it always was. **And the speed never changes by
  itself**: loading a recording — which the reader does whenever the narration
  moves into a part kept in another file — used to put the rate back to 1×
  while the control still said 1.5×. Now `defaultPlaybackRate` is set with
  every rate and the rate is set again after every load; a rate changed at any
  other time (the audio element has a speed in its own menu) is somebody
  meaning it, and the chip follows the sound instead of fighting it.
* **The header gets out of the way at every width**: down, it goes; the
  smallest move up brings it back (parseh.js `bars()`, which the mobile mode
  runs whatever the width). It holds still where something needs it to
  (`<body data-bars-held>`; the dictionary's sheet holds it with a class of its own). The dock needs no such hold: it floats, and stays
  wherever the page goes.
* **The reading place and the settings are the toolbox's** (`lib/prefs.py`,
  `lib/prefs.js`, `/__prefs`, `config/prefs.json`). The place per book — which
  subparagraph, said in words, how far in, by which device and when — and the
  settings that follow a person: the narration's speed, the gap, the seconds ↺
  and ↻ carry, stop-at-a-change, keep-going (`bk_cont`, whether the recording
  goes on into the next line), the theme, and **the names a person gave the
  levels of a book** (one key per language and level, `bk_lvl:fa:vocal`: the
  only keys `lib/prefs.py` knows by their beginning, each checked whole, a name
  of 12 characters at most; docs/languages.md §3). **What is shown stays with
  the device that shows it**: which levels are open, the text size, the margins
  -- and the touch habit of hover ⏸ (above), which is not in `prefs.KEYS` on
  purpose. A value the toolbox brings is also announced on the document
  (`parseh:pref`, `{key, value}`, for every key, and for a change another tab
  makes), so a page that draws a setting itself follows it. For the
  settings the last change wins. For the place nothing is overruled: a book
  opens where THIS device left it, and a line over the text asks — "On the
  computer you were at 2.1, a moment ago. Go there?" — with *Go there* and
  *Stay here*. A device names itself from its own browser ("Android phone ·
  Chrome"): nothing to type. The shelf shows the toolbox's place too, so a
  phone that has never opened a book still says how far it has been read. With
  the computer unreachable, every page keeps its own place as it always did
  and says nothing about it.
* **The chunks flagged to review later are the person's too** (`lib/later.py`,
  `lib/later.js`, `/__later`, a third key of `config/prefs.json`; never in a
  book, never in a bundle). A phone may flag a chunk, list the flags (a sheet
  from the foot in a reader or a player, and the page `/later/`, which both
  layouts carry), go to one, remove one with an Undo, test itself and copy the
  list; it never makes a card — the sheet draws no *+ card* — and edits no book.
  The flags are kept in `localStorage` (`parseh_later`) with an outbox of the
  changes the computer has not been told (`parseh_later_out`), sent when a page
  loads, when the browser comes back online and when the page is shown again —
  so what was flagged on a train arrives, and `/__later` is among the doors the
  worker refuses at once while the computer is away. Per flag the newest change
  wins and a removal is remembered for 90 days, so a device that still holds a
  flag cannot bring it back.
* **A finger reaches what a key reached** (`lib/wordtouch.js`). Copying is a
  Shift-click and a card an Alt-click, and a finger holds neither: so a finger
  HELD on a word for half a second opens a small menu — *Card for “word”* ·
  *Copy “the chunk”* · *Copy the sentence* (a video's transcript says *Copy
  the caption*). Each line dispatches the very click the page already listens
  for, so the card that opens is the page's own, with its cut editor, and the
  copy is the page's own, with its toast. A tap is left alone — it still plays
  or opens a gloss — and the click a phone sends when the finger is lifted is
  swallowed. In the mobile mode the card is not offered: a card writes.
* **“?”: nothing is known only to a mouse** (`lib/explain.js`). On a screen
  that cannot hover, the page's bar gains a **?**. Press it and the next tap
  on any control says what that control does, in a bubble beside it, instead
  of pressing it; press it again, or Escape, or *done explaining*, and the
  page is itself. The sentence is the control's own `title`, then its
  aria-label, then its words — so nothing is written twice and a control added
  later is explained the day it is added. Every page of the toolbox gets it
  from parseh.js; the studio's pages carry a tag of their own, having no
  parseh.js. Where a mouse can hover, nothing is drawn at all. The buttons
  that only a hover brought out — a book card's build and delete — are always
  drawn where there is no mouse; in the mobile mode nothing builds or deletes.
* **Only what reads is there.** The sheet names the controls that stay; every
  other one — book info, the builds, the narration, folding, gloss with an
  LLM, the timings, the download, the dictionary setup, stop, and whatever a
  later reader adds that nobody has named — is not on a phone at all. Neither are the page's other
  writing doors: the pencil over a chunk, the gloss cloud's *card* and *edit*,
  a seam's *+* for a note and the note viewer's *edit*, the naming of chapters
  and sections in the contents, and every sheet they open. A sheet left open
  in the browser mode is hidden, not closed, so going back finds it as it was.
* **The gestures that write are refused**, in the capture phase before the
  reader's own listeners hear them: a modifier-click on a word (a card) and E
  (the chunk's editor). A plain click, a tap and a shift-click (a copy) are the
  reader's as they always were.
* **Reading is untouched**: the levels, the glosses and the gloss cloud (a tap
  opens it in hover mode), the narration in step, the contents, the notes
  between two lines (the viewer opens the **bare note page** — the note on the
  studio's own sheet and nothing else; one that holds an exercise opens the
  full studio page, so it can still be answered), looking a word up, taking a
  character apart, the Aa panel, the reading place.
* **The dictionary under any gloss** (a0.3.1): the gloss cloud gets a
  *dictionary* button beside *copy*, which opens the dictionary for a chunk
  that has a gloss too -- the entry the cloud opens by itself only for an
  unglossed chunk with the header's switch on.  The cloud is the reader's
  (`fillCloud`, built into the page), so `lib/mobilereader.js` adds the button
  each time the cloud is filled (and has the reader place its cloud again,
  `refitCloud`, since the button can change its size), and the entry is drawn
  by the reader's own `dictInto`, a global of its classic script: every reader
  built since the dictionary existed has it, and one built before gets no
  button.  The video's cloud has the same button, written by
  `youtube/lib/player.js` itself (the player is served live), in the mobile
  mode only.
* **The dictionary's sheet** (a0.3.2, TO-DO §4.18): on a phone the entry is
  never read inside the cloud -- a small box scrolling inside a scrolling
  page, over the word, which the owner found "basically unusable".  The
  button, and a tap on a chunk with NOTHING written while the switch is on
  (the reader's own auto panel, handed over whole by the layer's
  MutationObserver; only for a click or a tap, never a mouse at rest), open
  **`Parseh.dictSheet`** (`lib/parseh.js`, the one script both pages and every
  reader load; drawn by `lib/mobile.css` under its own classes, `.m-dback` /
  `.m-dsheet`, in the look of the keep sheet's `.kp-back` / `.kp-sheet`):
  - the box the page's own `dictInto` fills, in a sheet as tall as the entry
    up to `86dvh` (no peek, the owner's choice), whose body is the one
    scroller (`overscroll-behavior:contain`) -- ALWAYS, whatever the page pins
    at its top (the owner, 2026-09-25: it once stopped short of the word under
    the player's pinned video, down to 45% of the screen).  The box is taken in whole: the
    inline `max-height` a cloud cut its panel to (`placeCloud`, both pages)
    is cleared, and `.m-dsheet .dict` is `max-height:none!important`, or an
    entry already cached opened as a peek of itself;
  - the chunk as its head, in `--tl-font` and `--tl-dir`, and the cloud's
    gloss lines copied over the entry; every entry rule restated under
    `.m-dsheet`, because every rule the reader and the player have for an
    entry is scoped `#cloud .dict` and means nothing outside the cloud; each
    hit's `.dhead2` split into the headword (`.m-dhw`, with the language's
    `lang` and `dir`, isolated) and its romanisation; each sense numbered with
    a `.m-dsn` of the sheet's own (text, so it is read out);
  - the word marked (`.m-dword`) and scrolled into the room between what is
    pinned at the top of the screen OVER ITS COLUMN (`pinned`: the header,
    and the player's `#playerwrap`; held sideways the video is pinned down the
    left, beside the transcript, and does not count) and the sheet, again
    whenever the sheet grows -- where that room holds it; where it does not
    (an upright video under a long entry, a book held sideways), the page is
    left where it is and the sheet covers the word, still marked, and the
    sheet's closing, which spends its history entry, brings the page back to
    where the word was tapped; the
    page lent room at its foot (`.m-dspace`) where it is too short to scroll
    that far, and given it back on closing; the header held where it is while
    the sheet is up (`html.m-dsup`, which `bars()` asks, as it asks
    `data-bars-held`);
  - dismissed by a swipe down (the head with pointer events, the body with
    touch events while it is at its top), a tap on the backdrop, ✕, Escape
    and the back gesture (`history.pushState({parsehDictSheet: id})`; any
    other close spends that entry with `history.back()`, whose popstate the
    sheet counts as its own; a sheet opened over a sheet `replaceState`s the
    entry instead, since a spending `back()` lands after a push and took the
    new entry with it);
  - `lang="en" dir="ltr"` on `.m-dback`, as the reader's `#cloud` has: its
    English would otherwise be taken for the book's language; the runs in
    the language carry their own;
  - a dialog that holds the page (`aria-modal`): Tab and Shift+Tab go round
    its own buttons and links, and closing gives the keyboard back to what
    opened it where that is still drawn;
  - `z-index:300`: over the page, its dialogs and the cloud, under the toast
    (400), the held finger's menu (420) and the ? bubble (430).  The two
    lines at the foot at 415 -- `.pf-bar` (where the other device stopped)
    and `.kp-bar` -- are `display:none` while `.m-dback` is on the page, and
    `lib/prefs.js`'s `sheetOver()` waits for it before it asks;
  - `Parseh.dictSheet.up()` / `.close(how)` for a page that did not open
    it: `lib/mobileplayer.js`'s `onFullChange`, when the browser leaves ITS
    full screen with a sheet up (Android's Chrome spends the back gesture on
    that and sends no popstate), closes the sheet alone -- which spends its
    own entry -- and keeps the overlay and the full screen's entry, so the
    next back leaves the video: one back, one thing, no dead entry.
  THE CLOUD IS HIDDEN, NOT CLOSED, while the sheet is up: the reader's
  `dictInto` fills only while `cloudC` is still that chunk, and its "click
  outside" listener asks `!cloud.hidden`; the player's `closeCloud` and
  `scheduleClose` refuse while its `dsheet` is up (as they do while
  `editing`).  And it STAYS hidden when the page draws it again (the reader
  reopens its cloud when a translation model is found late, and placing it
  shows it: the layer's MutationObserver hides it again while the sheet is
  up for that chunk; the player's `refillCloud` does nothing while `dsheet`
  is up).  The video is paused for the sheet when it plays or is buffering
  (YouTube's state 3), and a book's narration is paused and started again
  through the reader's own `#play` -- the button the dock presses.  And the mouse events a phone makes up after a tap on the
  sheet (the pointer "leaving" the cloud's button) are stopped at the window
  while the sheet is up: both pages close the cloud on its `mouseleave`, which
  would have thrown the book's answer away and started a paused video again.
  Closing the sheet closes the cloud with it -- nothing is left open -- and a
  video paused for the sheet or by the cloud's own pause goes on.  On the
  whole screen `lib/mobileplayer.js`'s `onPop` stays put when the entry it
  lands on is its own (`parsehVideoFull` carries an id, since
  `history.state` outlives a reload), so the back gesture closes the sheet
  and not the video's whole screen.  `tests/phone_clouds.mjs` drives all of
  it, with an English, a Persian and an Arabic dictionary of its own.
* **What a gloss is, on a phone** (the owner, 2026-09-25): ANY line of one --
  a meaning, a transliteration (the kana too, in a language with a reading),
  a vocabulary line -- save a reading a draft seeded from the word line with
  nothing else written (`ParsehWordline.seed`, as the build's `seeded()` and
  the player's `hasGloss` ask).  The reader's `fillCloud` and the player's
  go by the vocabulary line alone for their dictionary panel; in the mobile
  mode a chunk with a meaning or a reading and no vocabulary line opens its
  cloud with the dictionary's button instead (the player never draws the
  panel for it; the reader's layer takes the panel the reader poured in out
  again), and only a chunk with nothing written opens the sheet by itself.
  One rule, `hasGloss`, in both pages, for the press and for the count below.
* **Few glosses** (a0.3.2): in the mobile mode, a book (`lib/mobilereader.js`)
  or a video (`youtube/lib/player.js`) with a gloss on fewer than half its
  chunks gets `html.m-sparse` and `.m-gl` on every drawn element of its
  glossed chunks (a book's `.pass [data-c]`, the transcript's `.w`, which the
  subtitles over the whole screen copy).  A book is counted from the
  reader's `SRC` (every chunk of the book, `[colour, text, kana, tr, voc, en,
  words]`), not from the page, which holds only the chapters fetched so far;
  a chapter the reader fills later (`fillChapter` takes its `data-part` off)
  is marked by a MutationObserver as it arrives.  `lib/mobile.css` draws the
  mark: where nothing is underlined (a book's levels; in hover mode its levels
  but the first) a 1px dotted `--faint` underline on the glossed chunks;
  where every phrase already wears that underline (a video's transcript, a
  book's first level in hover mode) the unglossed KEEP it and the glossed wear it
  in `--dim` -- over the subtitles' black, a near white.  Nothing is written
  in the browser mode, where `tests/player_words.mjs` compares the transcript
  byte for byte.

The page is marked `data-mobile-page`, so its links route: the shelf's ▤ goes to
`/m/books/`. Going back to the browser mode leaves the page exactly as the reader
built it: every rule is a mobile-mode rule, what the layer adds is
`data-layout="mobile"`, and nothing of the reader's own was moved.

### The videos, `/m/videos/`, and a video's page

The browser's video index and channel pages are written per request
(`youtube/lib/ytpages.py`) and carry what adds, deletes and bundles a video,
so the phone has pages of its own (`lib/mobile.py`). **`/m/videos/` is the
channels** — one card each, under its language, saying how many videos it
holds, how many are glossed to the end and the levels they are marked with
(there is no "in draft" count: a video is no longer marked as one, a blank
gloss being legal in every video) — **and the videos are one tap inside**, on
**`/m/videos/<channel>/`**, which has always been there. That is the browser
index's own shape, and it is what the owner asked for (2026-09-23): this shelf
was a flat list before — every video of every channel under a heading apiece —
which on a phone is a page you scroll past rather than one you choose from. A
channel with videos in two languages is two cards, one under each language's
heading, so the chip row's counts stay honest; a card counts only the videos
of the language it is filed under. A video nobody has glossed yet has nothing
to read and says so, inside the channel, instead of being a link.
`parseh.js` routes `/youtube/` and `/youtube/c/<slug>/` there in the mobile
mode.

**With the computer away** the shelf itself opens — it is part of the way in,
kept with the app — and shows the channels the computer had when it was last
reached. A **channel's page** is on this phone only if the app warmed it, and
one added since the last warming is on nobody's: so `CHANNELS_JS` asks the
phone's own caches, address by address, and a card whose page is not here is
**drawn and cannot be tapped**, with a line saying so — the same face a book
whose reader was never built has always worn. Nothing there decides whether
the computer is away (that is the page's one question, `lib/activity.js`,
drawn by `lib/keep.js`), and nothing is greyed
until the caches have answered: the worse mistake is to refuse a page this
phone really holds.

**A video's own page is the same page**, with a layer over it
(`lib/mobileplayer.js`, `html.m-player` in `lib/mobile.css`), exactly as a
book's reader has one:

* the header is **one line** — the hub, the channel, what this video is, Aa, ⛶,
  ? and ⚙ (the title has no room at 320px and is left out there; it is the
  title that gives way, `flex:1 1 0`, so the line stays one line down to 320) —
  and ⚙ opens the rest as one sheet from the foot, as in a book's reader
  (a0.5.0; the same two stages, a0.5.4): *Watching & reading* (keep in view, pause while a gloss is open, the
  reading, Diacritics, keep the video in view, the lines around), *Looking a word up*,
  *Playback* (the skip, the speed), *Text*, *Zoom*, *Colours*, *Interface* (the switch and
  *Use it without the computer*). **Aa**, the text size, is on the first line as it is
  in a book's reader, one tap, and opens the sheet at *Text*. What writes the video or administers
  it is not there at all: its details, the caption timings, the download, the
  dictionary setup, stop, and the cloud's card, edit and colour marks
  (`#cloud .colrow` and its status line `.cstat` -- the rule once named them
  `.colors`, which matched nothing, and a phone could write a phrase's
  colour), and the transcript's *+* between two captions that writes a note
  (`#segs .gap .plus`, a0.3.2; the book's reader has hidden its own from the
  first) — nor the page's long explanation of the mouse's gestures, since a
  held finger now says what a finger can do; the cloud's own buttons are
  48px tall, as every target is;
* **the dock** at the foot plays it, moves it back and on by the seconds, and
  sets its speed (`lib/narrctl.js`). A video has no `<audio>` element to
  drive: it is YouTube's frame, or a film of this machine, behind the handle
  the player hands out (`window.ParsehPlayer`), and the speeds offered are the
  ones that player will really play at. ⏯ says **‖** and **▶** — the marks the
  rest of Parseh uses, and not ⏸, which a phone's colour font claims and draws
  as an orange emoji. **A video keeps a speed of its own** (`vd_rate`), put
  back when the player says it is ready, and never the book's `bk_rate`:
  watching and listening are different habits. The chip paints **the speed
  that was chosen**, at once, and holds it until the player confirms — a
  player is asked over a frame boundary and answers the old speed for a moment,
  which made the chip lag one change behind. **The dock is never mirrored**: it
  says `dir="ltr"` for itself, because time does not run backwards in a book
  that reads right to left — ↺ is behind and ↻ ahead, wherever the words go;
* **a video that will not play says what really went wrong**, and only when it
  really has (the owner's 9, 2026-09-23: the player said *the video needs an
  internet connection* while the phone was online, and embedded YouTube videos
  in the studio's own pages would not open either). Two faults in one: that
  sentence was the box's hardcoded default, put up by a blind six-second
  timer; and the cause behind it was `lib/keep.js` starting to warm the app
  shell — a megabyte and a half — the instant any mobile page loaded, which
  over a tunnel is bandwidth YouTube's own script needed and lost. The warming
  waits for the page's `load` and then for an idle moment, and fetches at low
  priority; the player waits for the script's own `load` and `error`, gives it
  a real grace, and then says what actually failed, with *Try again* and a way
  out to YouTube;
* **held sideways** the video goes to the left and the transcript to the
  right, with the divider between them draggable by a finger — the player's
  own `#grip`, whose side-by-side layout is restated for the phone here
  (its own rules need 860px, and a phone's long side is less);
* **⛶ gives the video the whole screen**, sideways only, with the line being
  said lying over its foot as subtitles. **The full-screen element is the page
  itself** (`document.documentElement`), and the layout over it is Parseh's own
  (`html.m-vfullon` in `lib/mobile.css`): the video's box pinned over the page,
  the picture centred on black, the subtitles at its foot, the dock where the
  thumb left it. It is not the video's box that is enlarged — that box holds
  YouTube's cross-origin frame, which takes the top layer with it, so nothing
  of Parseh's was drawn over it and a phone was left with no subtitles and a
  system bar it could not answer. Where a phone **refuses** the request the
  pinned layout is all there is, which is the same picture with the browser's
  own bars still showing, and the refusal is **said**. **Three ways out**,
  because nobody may be trapped inside a video: the ⛶ in the corner (faint
  with the dock, whole at a touch), the phone's **back gesture** (an entry is
  pushed on the way in), and a **tap on the black** beside the picture.
  YouTube's own ⛶ is not offered on a phone (`fs: 0`): there is one whole
  screen, Parseh's, and it is the one that carries the subtitles. The gloss
  **cloud stays in `<body>`** — it is fixed over everything the page has, so
  the overlay never needs to hold it, and a cloud moved into a box that is over
  nothing is a cloud nobody can see. The subtitle is a **copy** of the
  transcript's line and a copy carries no listeners, so it says which caption
  and which phrase it is and the player opens its own cloud anchored to it
  (`ParsehPlayer.gloss`) — the gloss stands over the subtitle, where the finger
  is. Upright there is no such button: a video on the whole screen leaves
  nothing to read.
* **The lines around the one being said** (a0.3.1): beside the ⛶ in the corner
  a second button (`.m-vctx`, three bars, the middle one bright) shows the
  caption before above the line being said and the caption after below it, in
  **one** cloud (`.m-subctx`) that grows for them -- as tall as the screen
  allows under the corner's buttons, scrolled within beyond that -- each a
  little smaller (0.82 of the text size) and greyer (white at 70%) than the
  line being said. Every phrase of the three answers a tap with its own gloss
  (`ParsehPlayer.gloss` is told which caption from the copy's own `data-i`),
  and a mouse at rest on one as well, as the transcript's phrases answer one
  (`gloss(..., hover)` opens without toggling, `unglossSoon` closes after the
  transcript's grace). The choice is kept for every video on the phone
  (`vd_subctx`). A caption of the video's own framing (`.plain`, an
  `.en-line`) is white over the picture too: it used to take the
  transcript's ink, dark on the black in the light theme
  (`tests/phone_clouds.mjs`).
* **The size of the words** (a0.4.0, the owner's L12: "one size each"). The
  transcript has its own size and the subtitles have theirs, both remembered
  by the device under `yt_typo` (`fa`, and the new `sub`, a store from before
  it has the subtitles at 20px), and both are sliders of the ONE panel the
  player already had (`Parseh.typo`, `--yt-fa`, `--yt-sub`, `--yt-gl`).
  On the header's first line Aa opens it with every row; **on the whole screen
  the header is under the picture** (the black box, z-index 55, covers it),
  so a button of its own, `.m-vtxt`, sits in the corner beside the lines-around
  switch (three 48px buttons, at 122, 66 and 10px from the right) and opens the
  same panel over the picture (z-index 120) with the subtitles' row and the
  glosses' row only (`html.m-vfullon .parseh-typo .trow:not(:has(#st-sub,#st-gl))`;
  the transcript's rows are not what the picture wears, and *reset* would put
  them back, so it is not there either). The subtitles' slider is not there
  upright (no whole screen), nor in the browser mode (no subtitles). The
  sliders are 34px tall in the mobile mode, for a finger. The panel is kept on
  the screen (`place()` clamps at the foot as well as at the sides, which a
  panel opened low in a phone held sideways used to run off), it closes at a
  tap on the black beside the picture (the whole screen stays; the next tap
  leaves it), at a tap on a word of the subtitle (which opens the gloss), at
  ⛶, at the back gesture and at a turn upright; the lines-around switch
  leaves it open, so a size is judged with the lines around it there. The line being said is `--yt-sub`; the lines around it are .82 of it
  (.64 for a plain line of the video's own English, .775 when it is the one
  being said, .66 and .8 for an English run inside a phrase line), all in
  `lib/mobile.css`; the dictionary's sheet is fixed-size, as the book reader's
  is. (`tests/mobile_pages.mjs` e1, `tests/phone_clouds.mjs` m.)

### The exercise decks, `/exercises/`

Each of the four pages — the decks, a deck, studying it, cramming it — carries
both layouts (`markdown/app/templates/*`), its head says which to draw
(`deckroutes.MODE_SCRIPT`), `decks.js` keeps the switch and the theme, and
`markdown/app/static/mobile.css` lays the mobile one out in the studio's own
colour tokens, so paper, dark and sepia carry over. The mobile bar has the way
home, the way up (the decks, the deck) and the theme — and, on a deck, ⚙, whose
*Interface* group holds the switch (the decks' own list keeps it in its bar).  Its
sheet is the same two-stage one: an index of *Text*, *Exercises*, *Zoom*, *Colours* and
*Interface*, and a theme at a time.

* **The decks**: the chips in one row, filtering the decks; each deck with what
  is due in it and its two doors, *Study* and *Open*, the whole width (two decks
  to a row from 600px). No import, backup, restore, new deck or stop; no ⋯ on a
  deck (export, delete).
* **A deck**: its name, its language, what is in it and what is due; *Study now*
  and *Cram all* — every exercise of the deck, crammed, the scheduling as it
  was. Then **its exercises, to pick the ones to cram**: the browser layout's
  own list, filters (the text, the type, the state, the tag) and ways to pick
  (all, the ones shown, by tag — a dialog with the deck's tags —, none), each
  exercise with a box a finger can hit (drawn by the sheet: 24px inside 48),
  and a tap on the rest of it showing it solved, as a click does in the browser.
  While anything is picked a *Cram N exercises* button floats at the foot of the
  screen (`#m-cram`, the bulk bar's own *Cram* is at the list's top). That is
  a cram plan — a tag, the lapsed ones, the ones a word is in — and nothing in
  it edits: the bulk bar's copy, move, tags, *Set to new* and delete, and every
  exercise's own buttons, are the browser layout's. A deck with nothing due
  says cramming leaves the scheduling alone; an empty one says exercises are
  added in the browser interface, and draws no list. No rename, add, export,
  options or delete.
* **Studying**: the exercise has the screen — **no bar over it**; the deck's
  name and what is left are one line, with ‹ back to the deck at its start and ⚙ at its end. What
  to do next is one box (`.dk-answerbar` in `study.html`, around the actions and
  the ratings; nothing in the browser layout) and the answering button is always
  in the same place in it: *Check* or *Show answer*, and, the answer back,
  **Next** where it was — rating the exercise as the answer says (Good when it
  was right or a card was turned, Again when it was wrong: its label says which,
  and when the exercise comes back) — so the exercises go by at a tap in one
  spot, with the four ratings beside it for any other. Held upright the box is a
  bar fixed at the foot of the screen (Skip and the answer; the ratings come in
  over them); held sideways, or on anything wider than it is tall from 600px, it
  is a column down the right edge — Skip at the top, the ratings two by two, the
  answer at the foot, where a thumb holding the phone rests — and the exercise
  has the whole height beside it. The answers, blocks, blanks and arrows inside
  an exercise are 48px. **A blank, and a matching exercise's place, are
  filled the other way round** (app.js, `bindExercises`, which asks `<html
  data-mode>` at each tap): a tap on the place opens a cloud — a copy of what
  the bank holds now, hung under the sentence or the list of rows (or right
  under the place, when their end is far below it) inside the exercise,
  which takes it along when it is redrawn — and a tap on a word puts it there
  by the same `moveItem` a drop uses, so what the place held goes back to the
  bank and checking is unchanged; a filled place's cloud can empty it. The
  bank stays, to show what is left, and is not picked up or dragged in this
  mode; an empty match's place says *tap to choose*. (Since a0.3.1 the
  browser layout has the same cloud, beside its dragging and its word picked
  then placed -- a place clicked while a word is picked takes that word and
  opens no cloud; only this mode has the cloud alone. `tests/blank_cloud.mjs`
  drives every way in both, on a document, a deck and an exported page.) (An ordering exercise
  has no places: its blocks move by their arrows, in either layout.) No *Edit* (correcting an exercise is the browser
  layout's), no key hints, no stop.
* **Cramming**: the same box, the same place — *Skip* beside *Check* then
  *Next exercise*, *Show answer* then *Wrong* and *Correct* — in the mobile
  layout's words; and the end's two lists, what was answered wrong at least
  once and what was skipped, each entry 48px, opening the exercise solved.

On the decks and a deck the bar gets out of the way on the way down at every
width, as the toolbox's own mobile pages' does (`decks.js`, `bindBarFollow`,
from 560px up; `app.js` does it below).

The theme button is the toolbox's ◐, cycling `parseh_theme`, and the studio's pages
follow that preference like every other page — they load `lib/prefs.js` since a0.5.0, so
the theme follows the person there too, and one function paints it (the sheet has no
theme menu of its own any more; ◐ and the gear's *Colours* both call it).

These stay browser pages only, with no mobile version planned, because what
they are for is making or administering something: adding a book or a video
(`/books/add/`, `/youtube/add/`), the studio's editor, new document and LLM
prompt pages, the Anki sync (`/anki/sync/`) and the clip tray (`/clips/`). A
link to one of them from a mobile page still opens it — in its browser version.
The reading help (`/settings/reading-help/`, once `/lookup/`, which redirects
there) moved into Settings (TO-DO §11.10) and, like its sibling Network,
carries the phone's bar; the mobile hub still has no door to it (the gear's
**Get a dictionary for this language →** and a cloud's **Set any of them up** reach it). Getting
a dictionary is not administering by the rule Settings now writes down in
`lib/settingspage.py`: a setting is risky — and changed on the computer
alone — when it changes who may reach Parseh, what it exposes, or what it
runs.

### The studio's library and a document, `/studio/`

Both carry the two layouts, as the deck pages do
(`markdown/app/templates/index.html`, `doc.html`, `static/mobile.css`): the
head decides which is drawn before anything is painted
(`deckroutes.MODE_SCRIPT`, handed to the studio's templates by
`render_template`), the browser's header says `data-layout="browser"` and the
phone's bar `data-layout="mobile"`. The few lines that keep the page in step
with the mode — the switch, the theme button, the worker in the mobile mode,
the bar that hides on a scroll — are `static/mode.js`, a tag of its own, so a
page that only reads need not wait for `app.js`.

**The library** keeps what finds a document: the search, the language chips,
the tags, the cards (a finger's size). It loses the upload, the backup, the
restore, the downloads, *+ New*, *Paste LLM answer*, *Stop server*, and the
delete on a card — nothing there builds or deletes.

**A document** keeps what reads it: the text, ☰ *Contents*, ⇄ *Glosses*, ↩
*Linked from*, and Aa (the size of the text, which stays with the device).
**Its exercises can be answered** — answering writes nothing — with targets of
48px. It loses *Edit*, *Build PDF*, *View PDF*, *+ Add all exercises*, *+
Deck*, *⚙ layout*, *Download*, *Duplicate*, *Delete*, the tag editor, *Print*
and *Stop server* (the owner's choice, 2026-09-22).

## A phone held sideways

What a phone held sideways lacks is height — 320 to 430px of it, against 640 to
930px of width — so the mobile layouts spend width to save height. Two
thresholds do it, both in the sheets:

* **From 600px wide** (a phone sideways, a tablet, a desktop in the mobile
  mode): the column widens to 880px (`--m-col`), and what was one under
  another goes two to a row — the hub's doors, the shelf's books (a language's
  heading the whole width), the decks, a deck's *Study now* and *Cram all*,
  its filters and ways to pick. The reader's header is one line, the
  recording's controls in it.
* **Sideways and 600px wide** (`(orientation: landscape) and (min-width:
  600px)`): studying and cramming put their buttons in a column down the right
  edge instead of a bar at the foot. A desktop in the mobile mode is sideways
  too, and gets the column.
* **Sideways and short** (`(orientation: landscape) and (max-height: 500px)`):
  the lines under a page's name that only say what the page is go, and the
  hub's brand is smaller.

And every mobile page's bar goes on the way down at every width (above). The
phone adjustments of the browser pages are untouched: they still answer only
under 560px.

**The scroll strip** (TO-DO §4.16). Studying and cramming put their buttons in
a column down the right, Skip at its top and the answer's button at its foot,
and a long exercise had to be scrolled by reaching back across the screen. So
the empty stretch of that column, between the buttons, scrolls the exercise: a
finger dragged up or down it moves the page one pixel to one pixel, and leaves
it flying on when the finger is lifted — slowing as a phone's own scrolling
does, and stopping dead at the top and the bottom. `touch-action: none` on the
strip alone, so the browser hands the drag over instead of moving the column,
and never over a button: nothing there changes, and a tap on one is still a
tap. A quiet grip marks it, and only while there is something to scroll. Study
and cram alike; upright there is no empty column and no strip
(`markdown/app/templates/study.html`, `cram.html`, `static/mobile.css`,
`decks.js` `bindScrollStrip`).

## Kept on this phone: Parseh with the computer away (§19)

The worker used to keep nothing: every page came from the computer, fresh, and
what an installed app needed of a worker was that there is one. That is
reversed now — **what has been kept on this phone is answered by the phone**,
so a book works with the computer asleep, off, or a train away.

* **What a thing is made of** is asked of the computer: `GET <book>/__offline`
  and `GET /youtube/v/<id>/__offline` (`lib/offline.py`) answer with every
  address to keep, each with its size, in **three** lists — the **small
  parts** (the page, the text, the pictures), which the phone renews by
  itself; the **groups**, which are one tick apiece (today, the notes written
  beside this book or this video); and the **heavy ones** (a recording, a
  film), picked one by one — plus the shared files every page leans on and a
  **version** for the whole. `totals()` says the cost in those same three
  parts, because a group can be unticked and a sheet that had folded it into
  "its text" would be taking back a number it had already given. An entry of
  any of the three may carry **`urls`** instead of standing for one address:
  then `url` is its NAME, what the phone remembers as kept and unkept, and
  `urls` is what is fetched and freed (the notes are one row of forty
  addresses; their recordings are one row of all of them).
* **Every entry says what the phone may test about it** (the owner's decision
  A, 2026-09-23). A file of at most `DIGEST_MAX` (8 MB) carries **`digest`**,
  the SHA-256 of the very bytes the server will send, lowercase hex; anything
  bigger carries none and is tested by its **length** alone, because WebCrypto
  has no streaming digest and hashing a 228 MB narration on a phone would want
  all of it in memory at once. The line falls by **size and not by kind**: a
  26 kB recording carries a digest like any other small file. And an answer
  the computer **composes as it sends** — a note's page from a template, a
  deck's exercises with the scheduler's numbers riding in them, a stylesheet
  written out of the language registry — has neither a digest nor a length
  anybody can predict, and says so with **`check: "here"`**: the phone may
  test that it HAS that answer and must test nothing else about it. Where such
  an entry still carries a size, the size is what the owner is being asked to
  spend and not a claim about the body.
* **The digests are remembered** in `config/digests.json`, one file for the
  whole machine, keyed by the file's own path and holding `{size, mtime,
  sha256}` — the same pair `_stamp()` decides a version by, so the two can
  never disagree about whether a file changed. Written atomically and
  best-effort: what is lost when it cannot be written is the second call's
  speed and never the digest. **Nothing is ever written inside a book's, a
  video's or a deck's own folder**, which hold the owner's work and nothing of
  ours.
* **A book's reader is kept whole, and that means every address its parser
  stops on.** `/lib/mt.js` is loaded as a parser-blocking script in the head
  of every reader `lib/tex2html.py` builds, and it was in no list at all: with
  the computer away the request missed every cache, the parser stopped where
  it stood, and the page never reached its body — the owner's "all books do
  not open while offline, loading stops at ~half", in all five of his books.
  It is in `SHARED` now, and `tests/mobile_pages.mjs` reads the reader the
  computer really sends and checks every `src` and stylesheet `href` in it
  against the record. **`timings.json` goes with it too**: the reader replaces
  the times baked into its pages with that file's, so without it a kept
  narrated book played to its build-time timings and none of the owner's
  corrections.
* **Every shape of narration is found.** A book may declare `"narrations": [
  {id, audio, transcript, from, to} ]`, or the older top-level `"audio"` and
  `"transcript"`, or nothing at all with a sound sitting in `audio/` that no
  `book.json` names. All three are asked of `lib/books.py`'s own
  `Book.narrations` rather than read out of the metadata by hand, and the
  fallback scan over `audio/` takes films as well as sounds — a fully narrated
  book whose recording was `audio/audio.webm` was offered no recording at all
  until 2026-09-23, because `.webm` is a film's extension.
* **Keep on this phone** (`lib/keep.js`) sits in the row the page names with
  `data-keep-slot` — the deck's actions, the document's toolbar; in the gear's last
  group where a page names none (*Away from the computer* in a reader, *Use it without
  the computer* in a player). The slot's value is the
  class that page dresses its own buttons in, so the buttons stand in the row
  looking like the ones beside them. It says what the text costs, lists the
  recordings to pick one by one — a narrated book is hundreds of megabytes,
  and nobody wants all of it by surprise (the owner's choice) — and shows its
  progress. Persistent storage is asked for as it starts.
* **Kept, it is two buttons, not one** (the owner's choice, 2026-09-23), and
  **they share one line, half each** (his 4 of the block after it): *Change
  what is kept* and *Remove from this phone* divide the space the one button
  used to have. Remove used to hang on a line of its own directly underneath —
  under the thumb that had just reached for the other one — and a button that
  throws three hundred megabytes away should not stand where the other one was
  a moment ago. `.kp-btn` is the **wrapper** now and no longer either button:
  it wears that name because every sheet places the one button by it
  (`lib/mobile.css` gives `.kp-btn` its order in a reader's header and its own
  full line), so the pair has to answer to it to stand where the button stood;
  what `.kp-btn` used to draw is undrawn on it in `lib/parseh.css`. With
  nothing kept the second is hidden and the first has the line to itself.
* *Change what is kept* opens the same list with **what is on the phone**
  ticked — **Save fetches what is ticked and frees what is not**, saying both
  numbers ("fetches 180 MB, frees 240 MB"), and **asks once** before it frees
  anything that is already here. A **Select all** and a **Clear all** stand
  over the list, and **a finger drawn across the boxes** takes every one it
  crosses: `touch-action: none` on the rows alone (`lib/parseh.css`), pointer
  events with the pointer captured, and the sheet still scrolls from anywhere
  else. The list is the computer's (`<thing>/__offline`), so with the computer
  away the button says **— needs the computer** and does not open.
* **A row is four fifths of the width and sits against the left** (the owner's
  2, 2026-09-23: *"reduce the size of the rectangles by 20% and align them
  left, so that part of the page is free to move the thumb and scroll without
  issues"*). A row takes the drag away from the browser, which is what makes
  the finger stroke above work — so with rows the whole width of the sheet, a
  book with fifty narrations was a list nobody could scroll past: wherever the
  thumb landed it was on a row. The clear strip down the right is what it
  lands on now, and that strip scrolls. **It is the width that shrinks and
  nothing else**: every row keeps its 48px, which is the one rule the mobile
  interface does not trade.
* **A recording's row says where it is in the book** (his 2 again: *"indicate
  also chapters and section range that each narration covers in the rectangles
  instead of only the range of paragraphs"*). The chapter and the section come
  first, in the reader's own wording — *chapter 2 · Sustainability · Water
  Resources*, or *chapters 1-6* where it runs across several — and the
  paragraph addresses go **under** them, small and dim, for whoever knows the
  book by those. The wording is the reader's because it is read the same way
  the reader reads it: `texparse.parse_book` once per record,
  `structure.plain` for the names, the section carried forward per chapter
  file exactly as `lib/tex2html.py` carries `sec_now`, and the stretch located
  with `texparse.region_bounds`, the function the narration pickers use. A
  record made before any of this — an older computer answering a newer app —
  has no `where`, and then the paragraphs stay on top, exactly as they were.
* **A tick means the file is there AND whole** (the owner's 3, 2026-09-23:
  *"the boxes should by default show the things that are actually kept in
  memory, and there should be a check of this, it should actually look for the
  file and check that the download was complete and correct"*). A box used to
  be ticked because the address was a key in a cache — which a 503 kept by
  mistake satisfies, and a page the computer sent where a picture was asked
  for, and a fetch a tunnel cut in half. So *Change what is kept* asks the
  worker `{check: id, want: [{url, bytes, digest, check}]}` and is answered
  `{check: id, urls: [{url, here, whole}]}`, and **the boxes are ticked from
  that and from nothing else**. `here` is whether the cache holds the address
  at all, which is what says there is room to give back; `whole` is whether
  the body passes — a refusal is never whole, an HTML body where a recording
  or a picture was asked for is never whole, a digest must match where the
  record gave one and a length where it did not, and an entry marked `check:
  "here"` is asked nothing beyond being there. What was kept and is no longer
  whole is **unticked and says so in its own row** (*kept, but no longer whole
  — tick it to fetch it again*), with a line over the list saying which of the
  two things will happen: a recording is his choice, and the text, the pages
  and the notes are fetched again unasked because the thing does not open
  without them. Ticking it again fetches it **whole**: that press carries
  `renew`, so nothing passes over "what is already there" and reports success
  on a broken copy — not the worker's `keep`, and not the page, which on a
  book's background way (below) is what takes what the phone holds off the
  list before it is handed over (`planOf`), and takes nothing off on a renew.
  And what comes by that way is put away only once it has passed this same
  `whole` (`arrived`).
* **An update is not damage** (TO-DO §13.16). The digest in `want` is the
  computer's *now*, and a new release changes Parseh's own scripts by design,
  so every kept copy of `/lib/`'s files used to fail it the morning after an
  update. So **each kept copy carries the digest it was kept with**, as a
  header on the stored answer (`X-Parseh-Kept-Digest`, lib/sw.js `stamped`):
  the page hands the worker the record's digests with every keep
  (`digestsOf`, and `decks.js` for a deck), `keep` and `settle` write them
  on, and `renew` writes the digest of the body it has just read whole. The
  check then answers `{url, here, whole, updated}`: a body matching the
  computer's digest is whole, and where the digest it was kept with is
  another, that record is **refreshed** to it (`updated`); a body matching the
  digest it was kept with while the computer's has moved on is **still whole
  and `updated`**, and is **not fetched again** — kept things can be big, and
  a page that uses it renews it behind itself; only a body matching neither
  is *no longer whole*. The line says it: *N of its files were updated on the
  computer since they were kept: the copies here are whole, and nothing is
  fetched again for them.* A copy kept by a Parseh from before this carries no
  digest and is measured against the computer's alone, as every copy was.
* **The worker** (`lib/sw.js`) keeps one cache per thing, `parseh-kept-<id>`,
  and one for the shared files, and **fetches into them itself** (`keep`: one
  message from the page, one loop here) — everything on the iPad and in
  Firefox, and everything but a book everywhere. A book, where the page's
  registration has the browser's own download, is fetched by the browser and
  only **put away** here (`settle`, *Two ways of keeping a book* below).
  **The kept copy answers first**, and the small
  parts are fetched again behind the page so the next open has whatever the
  computer changed. **A range asked of a kept recording is cut in the worker
  and answered 206** — the Cache API knows nothing of ranges, and without this
  a kept narration would play from 0:00 and refuse to be moved.
* **What has no answer offline says so at once**: looking a word up, the
  translation, every door that writes — and the notes of a
  thing whose notes were **not** kept — are answered 503 with a line of JSON.
  No dictionary and no translation model is kept on the phone (the owner's
  choice, 2026-09-22). Where the notes **were** kept, they are read from the
  phone like everything else that was kept (below).
* **Knowing you are offline**: every page asks the computer quietly, and when
  it cannot be reached wears an **offline** chip that opens `/m/kept/` — the
  list of what is kept, what each takes, how much room is left, each openable
  and each removable — with **↻** beside it, which opens the page afresh. The
  offline page is that list too, since the worker keeps it.
  `<html data-parseh-away>` says the same thing to the page itself: `assumed`
  when it came from the page before, `confirmed` when this page found it.
* **Offline is a verdict, not a guess** (TO-DO §2.24, the owner, 2026-09-24:
  *"Offline will mean drastic things usually, it's not a status that should
  change fast … We should not talk of offline for simply having a slow
  connection"*). Whether the computer is there is asked **once per page**, by
  the same poll that draws the *Working…* list (`lib/activity.js`), one ask at
  a time and each one **cancelled** when it is given up on — three pollers
  that never cancelled anything used to pile up on a slow tunnel until a
  computer that was right there looked gone. The worker leaves that one
  address alone, so what the page hears is the network itself. **Any answer,
  however late, is online.** Offline is: three asks in a row that fail at
  once, two seconds apart (a refusal, a name not found, no route — about four
  seconds); or the browser saying there is no network together with an ask
  that fails (at once); or **three asks across 45 seconds with not one
  answered** — which is the only sign there is when the computer on the far
  side of Tailscale is off or asleep, since that is silence and not a
  refusal, and silence is also what a slow link looks like at first. While an
  answer is five seconds late the page says **checking…** where the chip
  goes, and goes on behaving as online. A page that has **confirmed** the
  computer away is the offline version for as long as it is open (§19), and a
  write on it fails at once; an away it only **assumed** from the page before
  refuses no write.
* **And a page opens in the state the last one was in** (the owner's 5,
  2026-09-23: *"when changing pages the app rechecks if it's offline and
  assumes being online even if the page before showed being offline; good on
  the check, but assume that the status is the same of the page previous …
  and yes do the check and if the situation changes, correct, of course"*).
  Every answer is written to `localStorage` under **`parseh_away`**
  (`{at, away, trusted, why}`), and the next page reads it before anything is
  drawn (`AWAY_BOOT`, the first thing in its head) — so walking from an
  offline hub into the shelf no longer gives a moment of a page pretending
  all is well: cards that could be tapped and went nowhere, no chip, the
  counts the clock had made wrong still on the screen. **It is a memory and
  it is treated as one**: it is not trusted past three minutes — a phone
  picked up in the evening must not open on what it found at lunchtime — and
  the question behind it corrects it either way, which is the half he asked
  to keep. Nothing writes it but the question; a remembered state that
  stamped itself afresh from page to page would never grow old at all. The
  deck pages read the same mark, so they start where the last page left off
  too.
* **Except after a refresh** (the owner's fall-back, 2026-09-24: *"if we
  refresh the page, then it is forced to check again if the computer is
  online — so upon refreshing, do not assume still offline"*). F5, the
  browser's button, a finger pulling the page down, ↻ — the browser reports
  every one of them as `reload`, already in the head and whether or not the
  worker answered from its cache (driven in Chromium and Firefox), and on one
  the memory is kept but not acted on: the page says *checking…* if the
  memory said away, and asks at once. So a page wrongly offline is one
  refresh from right; a page rightly offline comes back offline — at once
  when the computer refuses, after the 45 seconds when it is silent. In the
  installed app on Android the pull-down is the only refresh there is; on an
  iPhone or iPad there is, as far as is known, none at all, which is what ↻
  is for.

### The notes come with the book or the video (2026-09-23, second block)

Until that day the records here never walked a `markdown/` folder, so a kept
book kept its text and its recordings and left every note behind: every seam
on a train opened on nothing. The owner's decisions, and where each one lives:

* **One tick, beside the recordings.** The keep sheet has a row of its own —
  *its notes · 34 · about 280 kB* — which can be unticked, and is ticked to
  begin with. It is a **group**: one row carrying every note's page, the
  pictures in those notes, and the seams' list. *About*, and the sheet says
  the word: a note's page is the same wrapper every time (measured off
  `templates/note.html` and `doc.html`, so it cannot go stale) plus its own
  `source.md`; the pictures are files and are weighed exactly. Nothing here is
  rendered to answer a question about keeping — asking what a thing is made of
  must not cost what reading it costs.
* **The marks travel with them.** The reader draws a mark from
  `<mount>/api/marks` and from nothing else, so a kept note whose list stayed
  on the computer is a page nothing on the phone can reach. It is kept as a
  **door** (`lib/sw.js` `isDoor`): the computer is asked first and the kept
  copy stands behind it — which is also what makes a note written after the
  book was kept show its mark the moment the phone is home.
* **A note that holds an exercise keeps its full studio page**, because
  without the studio's scripts an exercise is a box that cannot be answered;
  that is why the bare address redirects at the desk, and away from the desk
  it must open exactly as it does there. The scripts are paid **once for the
  phone**: the document page links them at the studio's own address
  (`{{STUDIO}}`), as the bare note page already did, and `lib/sw.js` puts
  everything under a `static/` path in the **shared** cache.
* **The studio's thirteen faces travel too**, once, 1.83 MB
  (`markdown/app/static/fonts/`, read off the directory rather than off a
  list). Nothing named them before — they are named only inside `url()` calls
  in `sheet.css`, which nothing but a browser reads — so a kept *document*
  already rendered in whatever face the phone had. This mends that as well.
* **MathJax where there is a formula**, and at the address the page really
  asks for: `<studio>/static/mathjax/tex-svg.js`, 2.1 MB, because the little
  loader works the library's address out of its own `src`. Whether there is a
  formula is asked of this toolbox's dialect (`]{math}`, `:::math`) and not of
  `$`, which is an ordinary character here.
* **A note's pictures come with the notes; its recordings do not.** They are
  one row of their own in the heavy list, beside the narrations — *the notes'
  recordings · 4 files · 12 MB* — so nothing heavy is ever kept by surprise.
* **A note written, edited or deleted moves the thing's version**, so the
  out-of-date bar offers it in one tap; and what the phone holds under a
  thing's cache that the door no longer names is what the next *Save* gives
  back, with the sheet saying how many first.
* **Books and videos together**: `<book>/notes` and `/youtube/v/<id>/notes`
  are the same mount served by the same routes, and the two records are one
  shape. `serve.py`'s `notes_to_keep` gathers the list for both — the studio's
  own knowledge of which notes there are and what each render holds stays in
  the studio, because `lib/` must never import it.

### Two ways of keeping a book: the browser's own download, and the worker's (2026-09-23)

Keeping was one message to the worker and one loop there (`keep`), and
Chromium stops a worker's event once it has run five minutes (driven: stopped
at 310 s, the fetch in flight cut, no `catch` run and no `{kept}` sent) —
which a narration of two hundred megabytes over a tunnel does not finish
inside. So **a book goes by the browser's own download (Background Fetch)
where the page's registration has one**: the browser finishes it, with the
page closed and the worker stopped (driven) and, it is meant, with the phone
locked (his phone's to show, below), and on Android it shows in a
notification of its own, with its own Cancel. Everywhere else — the iPad,
Firefox — **the worker keeps it exactly as it always did**, and that is not a
lesser way: it is the whole feature there. The owner's decisions, and where
each one lives:

* **The page decides, per press** (`bgFor`, `lib/keep.js`): a book, and
  `'backgroundFetch' in registration` — his own check — asked of the page's
  own registration (`bgLook`: once when the page starts, with a deadline, and
  again on `controllerchange`, since the first page after an install looks
  before any worker is active; driven: a fresh phone's first keep went the
  old way until this). **The page starts the downloads, not the worker**:
  since Chrome 149 a worker may not start one at all (driven:
  `NotAllowedError`, although `'backgroundFetch' in self.registration` is
  still true there). Every keep of a book goes this way where it can — *Keep
  it*, *Save* and *Keep it again*, and Chrome on a computer too. Videos,
  decks and documents stay on the worker's way, and so does `decks.js`'s
  `keepDeck`.
* **Two downloads a press, the text first** (`bgKeep`): the text — the page,
  the chapters, the pictures, the shared files, and the notes, which travel
  with it — and then the recordings, the book's ticked ones and the
  notes' together, so a book opens on a train as soon as its text is in. Both
  are registered at the press, since the worker could not start the second;
  one with nothing in it is not started, and a press with nothing left to
  fetch answers at once. What the phone holds already is taken off the list
  first, asked of the two caches the worker's `held` asks (`planOf`), because
  a download cannot pass over a file. The ids are
  `parseh-keep:<token>:<text|rec>:<thing id>`, and the notifications read
  `<title> — its text, coming onto this phone` and `<title> — its
  recordings, coming onto this phone`. The recordings' download carries
  `downloadTotal`, the exact sum of their sizes, so that Android's bar counts
  megabytes; where one size is not known the total is left out, since a total
  too small leaves a download waiting for ever.
* **A note for whoever finishes it** (the cache `parseh-jobs`). The download
  may end with every page closed and a worker the browser has only just
  woken, and a worker cannot write the registry (`parseh_kept` is
  `localStorage`). So at the press the page writes a note at
  `/__keepjob/<token>` — an address no page ever asks for — saying what the
  thing is, which addresses each download holds, what each should weigh,
  whether it is a first keep, and the registry entry to write when it is
  done, with the version it was started on. The entry is made by the same
  `entryOf` as a keep that ends in front of the page: two copies of that
  shape would be two registries that drift. Each download's outcome goes
  under `/__keepjob/<token>/<part>`, and the end under `…/end`. The notes are
  read without making the cache, so a browser that never keeps in the
  background — the iPad — is not left an empty one; and the book's own
  `parseh-kept-` cache is made at the press, as `keep` makes it, so that a
  book waiting behind another counts as kept to `reclaim` and the shared
  files it was told it need not fetch are not swept away by another book's
  Remove.
* **The download ending is not the keep ending** (`settle`, `lib/sw.js`). The
  browser wakes the worker with `backgroundfetchsuccess`, `…fail` or
  `…abort`, and `settle` does what `keep` does, address by address. It writes
  a *settling* note first — the browser stops this event after five minutes
  as well, and a note still saying so long after is how a page tells — and
  puts each answer that passes where `isShared` says. **A success is not
  taken on trust**: a connection refused under the download can end in
  "success" over an EMPTY body, status 200, with the file's own
  Content-Length (driven, four ways), so each answer is measured before it is
  put away (`arrived`: the body's size against its Content-Length, and then
  the sheet's own `whole`, with what the record said the file weighs). A 404
  or a 410 is a file the computer no longer has; a `QuotaExceededError` on a
  put is no room, and every put after it is counted as the same fact rather
  than tried. When every download of the press has settled (`finish`), the
  end is written in the notes, `{kept}` goes to **every** page with the
  keep's token — this event has no page to answer — and the notification's
  last words are set (`updateUI`, which a Cancel does not allow):
  `<title> is on this phone now`, `<title>: 3 of its files could not be
  kept`, `<title>: no room on this phone`; and the text's, while the
  recordings follow, `<title> — its text is on this phone; its recordings are
  next`. A first keep that brought nothing leaves no empty cache behind. A tap
  on the notification opens the book's reader, or brings it forward where it
  is open (`backgroundfetchclick`).
* **A keep that ends part-way keeps what arrived** (the owner). A Cancel on
  **either** notification stops the whole keep, the other download of the
  press as well (`stopOthers`: a worker may stop a download where it may not
  start one). What came is written down, *Change what is kept* shows what did
  not come unticked, and the line says which fact it was, each in its own
  words (`keptLine`): `<title>: stopped from the notification — what had come
  is on this phone`; `<title>: 2 of its files are no longer on the computer`;
  `<title>: no room on this phone for 2 of its files`; and otherwise today's
  *N of its files could not be kept — try again with the computer awake*. A
  **first** keep cancelled before anything had come says `<title>: stopped
  from the notification — nothing of it had come yet`, is **not** written
  down, and its button reads *Keep on this phone* again.
* **Written down by the next page that opens** (`bgMerge`, `written`,
  `foot`). Whichever page of Parseh opens next writes the entry down — dated
  when the keep finished, and never over a newer one (a *Save* since) — says
  the line **once, at its foot**, in a bar with *OK* that stays until it is
  put away (a toast gone in two seconds would be a line never read, about a
  book that came while he was not looking), and clears the notes. *Kept on
  this phone* and the offline page draw from the registry before
  `lib/keep.js` could run, and the offline page has no script from anywhere,
  so they do it themselves first (`MERGE_JS` in `lib/mobile.py`, which says
  so with `parsehMerging`), and say the line under their list rather than in
  that bar. A note whose downloads are gone and which has no end — the
  putting-away cut off, or never run — is written down from what the caches
  really hold (`interrupted`), and only once it has had a minute and no fresh
  *settling* note says the worker is still at it.
* **What the page says while it comes** (`bgFollow`, `keepingWords`). The
  progress is counted in bytes, from the browser's own downloads against what
  the note says the files weigh, and never goes backwards. **The page says
  which way it is**: *Keeping… 43% — you can leave this page*, where the
  worker's way reads *Keeping… 43%* as it always did. A second book waits
  behind the first and says so — `Waiting for <first book> — you can leave
  this page` — and starts by itself; a press that would not fit Android's
  five downloads of one site is refused: *Two books are already coming onto
  this phone — keep this one once one of them is in.* The computer going
  quiet is waited out, and said — *Keeping… 43% — waiting for the computer*
  — and the browser carries on by itself when it answers. A browser that
  refuses (the site's permission, asked first, or the download refused as it
  is asked for) is said plainly and nothing is fetched: *Chrome will not
  download for Parseh in the background — turn on Automatic downloads for this
  site in Chrome’s Site settings.* A download taken and not started yet is
  **waited for**, never called a refusal (the owner, on second thought, the
  same day): Chrome holds a new download while any page is loading and for
  half a minute after, and on a computer for up to a minute after it starts —
  driven here, where a rule that stopped a keep bringing no byte in thirty
  seconds stopped three good keeps out of four that, left alone, arrived at
  about sixty seconds. The same hold PAUSES a download already running when a
  tab starts loading, until half a minute after it stops (read in Chromium's
  source; not driven), so walking between Parseh's pages mid-download may
  slow it. A recording that has grown on the computer since the list was
  made is NOT failed by the browser: the download stops a little short of
  the total it was given and waits there for ever (driven), which looks just
  like a paused download or a quiet computer. So a page that is open looks
  into a recordings download that has not moved for a minute: it asks the
  computer what the book is made of now, and only if one of those recordings
  is named at another size than the note has is the download stopped — what
  had come stays (`grown`, D12). A page opened or reloaded while its book is
  coming takes the keep up where it is (`bgResume`), and the out-of-date bar
  waits until it has ended. A second tap on the press, or a press on a book
  already coming — *Keep on this phone*, or a *Save* whose sheet was opened
  before another tab pressed — takes that keep up rather than starting
  another (`bgKeep`, `bgTakeUp`): nothing is freed, and what is written down
  at its end is what that keep brought, never the second press's own picks.
  Where those picks were not all in it, the press says so in the owner's
  words (D20): `<title> was already coming onto this phone — change what is
  kept once it is in`.
  Save asks whether the browser will take it (`bgReady`) **before** it
  frees what was unticked, so a refused Save gives nothing back; and Keep it
  again that brings nothing leaves the registry at the version the phone
  really holds, so the out-of-date bar still offers it.
* **Remove, and Stop.** *Remove from this phone* while the book is coming —
  from its page or from *Kept on this phone*, looked at when it is pressed —
  stops it first and puts nothing of it away (`bgRemove`, `stopAll`): its notes say
  `removed` **before** the downloads are stopped, so the `settle` the stop
  wakes finds the word and keeps nothing, and takes out what a put already in
  flight wrote (`thrownAway`). *Kept on this phone* lists a book still coming
  — read from the browser's own list of downloads and the notes, never made
  up, so the iPad's list is the one it always drew — as *coming — 43%*, with
  **Stop** in place of Remove. Stop is what Cancel is: the whole keep stops,
  what had come stays, and the line says where it was stopped —
  `<title>: stopped on this phone — what had come is on this phone`, or
  `— nothing of it had come yet`.
* **The room it needs for a moment** (`roomFor`, `roomWords`; the background
  way only). The browser holds a download until it has been put away in the
  cache, so for a moment it is on the phone twice. The sheet asks the browser
  what this site may still use (`navigator.storage.estimate()`, its quota
  less its usage) and, where that is short of twice what will be fetched,
  says so before anything starts — *Needs about 980 MB free while it
  arrives; this phone has 600 MB* — and the press then reads *Keep it
  anyway*; a tick changed afterwards asks again. The out-of-date bar asks the
  same, with *Keep it anyway* and *Not now*. Where the browser says nothing,
  nothing is said. The worker's way needs the room once, and its sheet is as
  it was.
* **Two things mended on both ways.** **The button says *Keeping… N%* until
  the keep has ended** (`busy`): the page is repainted whenever the question
  of whether the computer is there changes its answer (`paintAway`), and a
  repaint with no state put the button back to
  *Keep on this phone* in the middle of a keep — for the whole of a
  narration, and live again under the thumb. And **an answer is taken only by
  the keep it answers**: the background end goes to every page, so `tell()`
  and `decks.js`'s `keepDeck` compare the id in `{kept}` with their own — a
  deck waiting for its copy must not take a book's end for its own and check
  itself out with its copy half made.

**Both ways are driven on every run** of `tests/mobile_pages.mjs`. As
launched, its Chromium has the background download, so a book is kept that
way through every keep assertion the suite had; at its end the suite runs its
parts *offline* and *checkout* again, by itself and only after the first run
has closed (never at once), with `MOBILE_KEEP_WAY=worker` — the same Chromium
launched with `--disable-blink-features=BackgroundFetch`, the API gone from
the page and the worker alike, as on the iPad — through the very same
assertions. **Which way a keep went is proven from outside the page's own
words** (`keptWay`): the browser's own record of its background downloads
(CDP's `BackgroundService`) and the notes in `parseh-jobs`, which a
background keep leaves and clears; a keep that fell back quietly to the other
way would otherwise pass every assertion. A deck is held to the worker's way
even where the browser has the other. The part *background* drives what only
that way has, with the computer stopped by SIGSTOP (a phone meets silence, not
refusal) and the notification's Cancel made as the notification makes it, by
the download's own abort; its scenarios are lettered, and
`MOBILE_BG_ONLY=a,j` runs some of them alone:

* (a) the page closed and the worker stopped mid-download, and the book still
  arrives, each file in the cache it belongs in, written down by the next page
  opened, its line said once;
* (b) Cancel before anything had come, and (c) after the text had, the
  recording then unticked in *Change what is kept*;
* (d) a recording taken off the computer after the list was made;
* (e) no room, the site's quota made really short, and (e2) the room warning,
  with the browser's report made small in that one context — nothing else
  makes `estimate()` say so;
* (f) a second book waiting behind the first, and the first waiting for a
  silent computer; (g) a page reloaded mid-keep taking it up;
* (h) *coming — N%* and Stop on *Kept on this phone*; (i) Chrome refusing,
  the permission denied; (i2) a Save refused that way gives nothing back;
  and in (a), two taps at once start one keep;
* (j) the phone's own kind of profile — an incognito one never resumes a
  download — with the computer killed mid-recording and started again ten
  seconds later: resumed, and whole.

Waits on the caches are polled from outside the page (`until`): Playwright
1.52's `waitForFunction` takes an async predicate's Promise for a yes and
"passes" at once, which had made the suite's own *ticking it again fetches it
again* wait vacuous; it is real now.

**What only his phones can show** (TO-DO §19.11): Android's notification
itself — its words, its Cancel and Pause, the tap that opens the book; a
locked phone, and Doze; the installed app; his tunnel; the cookie of a phone
let in at the Wi-Fi door, on a real phone's downloads; and the iPad's own
WebKit — the suite drives the worker's way in Chromium with the API taken
out, not in Safari. **And what was not driven here either** (TO-DO §19.14):
the stop of a recording grown on the computer mid-download; the five-minute
cap on `settle`; a new `sw.js` arriving mid-download; and a page opening in
the moment between a download ending and the worker putting it away.

### The app with the computer away (the owner's 1 and 2, 2026-09-23)

The app used to stall on its own splash: its start address `/?mode=mobile`
was in no cache, and the worker's `fetch` had no deadline, so a network that
was up with a computer that was not — asleep, or a Tailscale peer down — left
a socket that never settled and a `respondWith` that never resolved. Both are
put right, and the rule is: **the usual pages open, and there is no "Parseh
cannot be reached" page for them.**

* **The way in is kept**, from one list the computer gives at `GET /__shell`
  (`offline.shell()`): the hub at **both** its addresses — `caches.match`
  tells `/` and `/?mode=mobile` apart, so the one answer is put under both —
  `/m/books/`, `/m/videos/`, `/exercises/`, `/studio/`, `/m/kept/`, `/later/`
  (an empty frame that `lib/later.js` fills from the phone's own copy of the
  flags, so it lists what was flagged on the train) and `/m/offline/`, the two
  lists the library pages ask for rather than carry,
  and every sheet and script they load with the toolbox's own faces (`SHARED`,
  and the studio's own `STUDIO_FILES`) — the studio's thirteen faces apart,
  which are `later` and are warmed only where they are wanted (below).
* **It is kept AFTER the app is installed, not during** (TO-DO §0, the third
  block of 2026-09-23). The worker's `install` event fetched the whole way in
  — fifty-nine addresses, 3.26 MB, one after another inside `waitUntil` — and
  a worker that grinds through three megabytes over a tunnel stays in the
  installing state, which is a state **Chrome will not install a site from**:
  the offer was accepted on the phone and no icon appeared. Install is back to
  what it was before §19 — the two small pages that must open with the
  computer away (`OWN`: `/m/offline/` and `/m/kept/`), `skipWaiting()` called
  first of all — and neither `install` nor `activate` so much as reads the
  shell.
* **A page asks for the warming, by message**, once it is up and the computer
  is known to be there: `{warm: 'way-in'}` is the pages, the two lists and the
  files; `{warm: 'studio'}` is the faces. The worker reads `/__shell` when it
  has not got the list, then fetches **one address at a time**, passing over
  every address the shell's cache or the shared one holds already — asked of
  the caches and not guessed from the address, by the same `held` that `keep`
  asks with. A kept book's own cache is deliberately not among them: it leaves
  when the book does, and the app shell must not be left pointing at a face
  that went with somebody's book. So **asking is cheap**: a warm phone
  settles the list without a single fetch, and a warming cut off partway
  through (Chrome stops a worker whenever it likes) carries on where it
  stopped the next time it is asked. `lib/keep.js` sends both — the way in on
  every app page, the studio's faces on a studio or deck page and the moment a
  note's mark is clicked — and sends neither in the browser mode or while the
  computer is away: this is the app fetching its own pages.
* **The studio's thirteen faces are `later`**, not `files` — 1.83 MB that a
  studio PAGE needs to look like itself, which is not how anybody gets
  anywhere. They are named by `studio_faces()` in the same one place as
  everything else, kept by the same worker into the same cache, and no phone
  fetches one until a page that needs it says so.
* **And the app says how it is going** (the owner's decision, 2026-09-23: "I
  want the warming not to be silent"). The worker tells every window
  `{warming: {what, done, of}}` as it goes and `{warmed: {what, of}}` when it
  has stopped working on that list; `done` counts addresses **settled**,
  fetched or skipped. Any page may carry `[data-parseh-warm]`: while a warming
  runs it reads *Getting ready — 41 of 59*, and a page that asked for nothing
  shows nothing. The hub carries one and the line **goes** when there is
  nothing left to say; the install page's says `stay`, because that page asks
  somebody to wait until it is ready and a line that vanished would answer the
  waiting with nothing. **It stands at the foot of the page, under the last
  door, and not above them** (the owner's 1, 2026-09-23): a line that appears
  and goes at the top pushed every door down and let them spring back a moment
  later, under a thumb that was already reaching for one — and on a phone that
  has everything already, which is most days, that is the whole of what he saw
  of it.
* **A shell page opens from the phone and is filled in.** It is answered from
  the phone's copy at once; the worker reads it again behind the page and,
  when what comes back differs, says so (`shellFresh`). `lib/keep.js` then
  replaces the page's one list block in place — the block a page marks with
  `data-shell-block` (`lib/mobile.py`), or the hub's `.m-doors`. `/m/kept/`
  carries no such mark: that list is the phone's own. The two lists that are
  asked for rather than carried go the other way round — the computer first,
  under the same deadline, the phone's last copy behind it.
* **What is not on this phone is drawn and cannot be tapped**, with a line
  saying so — exactly as a book whose reader was never built already looks on
  the shelf (`m-book m-off`). The phone knows what is kept from the
  `parseh_kept` registry, and `lib/keep.js` undoes it the moment the computer
  can be reached again.
* **Counts the clock makes wrong are not shown** while the computer is away —
  what is due, on the hub and on the decks. The lists stay; the numbers
  nobody should act on go. A page marks its own with `data-clock-count`.
* **`/m/offline/` is left for a navigation that is neither kept nor part of
  the way in** ("Parseh cannot be reached", and *Try again* — a page that
  stands alone, no stylesheet or script from anywhere).  *Try again* loads
  the address again, which can succeed the moment the computer is back; the
  press is written down in the tab (`sessionStorage`, read once, good for one
  load), so a page that fails again says so and when — "Still cannot reach
  it. Tried again at 14:02:11." — instead of being word for word the page
  that was there before, and the button reads "Trying…" while it waits.
  *Go back* is a button of its own for a page the person came from
  (`history.length > 1`, never inside a frame).  Neither makes a page a
  computer is slow to begin arrive: *Try again* is made from a page that cannot
  answer the worker's question (this one has no poll of its own, by design:
  below, *At the deadline the page is asked*), so it waits the deadline and
  one question — about four seconds — and is the offline page again; *Go
  back*, and the link followed again from the page the person was on, is what
  waits for the computer.
* **At the deadline the page is asked** (the owner's decision of
  2026-09-28, TO-DO §2.28, which overturns the rule of 2026-09-23 in this
  one respect). A navigation to a page nothing kept used to be given
  `DEADLINE` (2.5 s) and then answered with `/m/offline/`: a computer that
  was **alive** and took longer than that to begin — a big document, a
  tunnel in a slow hour — was called unreachable, and *Try again* met the
  same race. The deadline is now **where the pages are asked, not where the
  computer is called gone** (`navigate`, `computerAnswers` in `lib/sw.js`):
  * the worker makes **one** fetch and waits for it twice — never a second
    ask of the computer, so a page slow to make is made once;
  * at `DEADLINE` it sends every open window one message with a port
    (`{reachAsk: true}`) and gives them `ASKED` (1.5 s) to answer. The page's
    poll (`lib/activity.js`) is **still the one asker of the computer**: a
    page only brings its next ask forward and answers `{state: 'there'}` when
    the computer's answer to it comes — never from memory, since what a page
    heard a few seconds ago says nothing of a computer suspended since — or
    `{state: 'away'}` at once when it has already judged it gone;
  * while a page says `there` the worker goes on waiting for the fetch, up to
    `PATIENT` (30 s) from the start; when every page says `away`, or none
    answers within `ASKED`, it answers with `/m/offline/` as it always did;
  * so: a computer **alive and slow** is waited for, from a page that is
    open; a **refusing** one still ends at once (the fetch fails before the
    deadline and no page is asked); one **silent** (suspended, asleep) ends at
    `DEADLINE + ASKED` — four seconds, far from `PATIENT` — because an
    unanswered question is the answer; one the page has judged **away** ends
    at `DEADLINE`; and a link followed where **no page of Parseh's is open**
    (typed in a new tab, opened from another app) has nobody to ask and ends
    at `DEADLINE`, as before. Nor does a page **in a tab behind another**
    answer: a hidden page does not ask anything (lib/activity.js), so it is a
    silence too — one tab in sight is enough;
  * a computer that answers after `PATIENT` is given up on at it.
  Downloads made on demand are unchanged, and are not the worker's at all
  (next bullet).
* **A file made on demand is not the worker's at all** (TO-DO §2.28): a
  document's **Download ▾** (`/download/<id>/md|tex|pdf|zip|html`), a book or
  a video packed to download, a backup, a deck's zip, an Anki deck
  (`MADE_ON_DEMAND` in `lib/sw.js`, the same list `lib/activity.js` follows
  plus the document's own downloads). None is ever kept, and each is honestly
  slow: the computer makes the file before the first byte leaves. Raced
  against `DEADLINE`, a navigation to one fell to `/m/offline/` while the
  computer was still making it — "Parseh cannot be reached" for a computer
  that was busy, with a *Try again* that met the same race. Left to the
  browser, as `/__activity` is, a link waits for its file with the page still
  on the screen, and a page's fetch hears the network itself. The two HTML
  exports are fetched under a bar besides (`madeDownload` in
  `markdown/app/static/app.js`): the bar where the press was, and a deadline
  of its own — five minutes for the answer to begin, a minute of nothing more
  once it has; the page's offline verdict ends it too, a slow answer never
  does, and whatever ends it is said in place of the bar, with *Try again*.

| Kind | Kept | Works offline | Still needs the computer |
|---|---|---|---|
| A book | the reader, its chapters, its pictures; the recordings picked; **its notes**, one tick, with their marks and their pictures — their recordings a row of their own | reading, the glosses, the narration with seeking, the reading place; **the notes in their seams**, and an exercise in one answerable | looking a word up, the translation, *Ask LLM*; writing or editing a note; the notes of a book kept with that row unticked |
| A video | the page, the transcript, the glosses; a film on this machine; **its notes**, exactly as a book's | reading the transcript and its glosses; a local film plays; **the notes in the seams of the transcript** | a YouTube video itself (§18), looking a word up; writing or editing a note |
| A deck | its three pages, **its exercises as the cram page renders them**, their pictures and recordings, and the studio's own sheets and scripts | **cramming** — an exercise shown, answered, and the next one; **studying, when the deck is checked out** (below) | adding or correcting an exercise; **studying a deck that was not taken out**, which says so at once rather than hanging |
| A document | the page as the computer rendered it, its pictures, its recordings picked, **the faces it is set in** | reading it, and answering its exercises — **in the studio's own face**, which it was not until 2026-09-23 | editing it, building anything from it |

### Studying offline: a deck is CHECKED OUT (§19.10)

Studying writes — every rating changes a card's schedule — and a phone away
from the computer cannot write there. Of the four ways out (merge, queue and
replay, check out, two equal peers) the owner chose **check-out**, and this is
what it means:

* **Keeping a deck and taking it out are two things** (the owner's choice,
  2026-09-23). *Keep on this phone* is the **copy** — the deck's pages, its
  exercises and their media — which is what makes it open and be crammed with
  the computer away. *Take it out* is the **right to study** it away, and it
  is no use without the copy: where the deck is not kept, taking it out
  **keeps it as part of the same press**, saying so while it does it;
* **the exercises travel with the deck, always, under its one tick** (the
  owner's decision B, 2026-09-23): their rendered HTML, their pictures and
  their recordings, a few hundred kilobytes for a deck of a hundred — the same
  order as the deck's own text — so there is nothing left to choose and
  `media` is empty on purpose. Two things had to change for it to be possible
  at all. **A service worker cannot cache a POST**: not "does not" — the Cache
  API refuses a request whose method is anything but GET — and the cram page
  asked for its exercises with a POST carrying the picked ids, so from the day
  it did, a kept deck could never show one exercise away from the computer,
  however faithfully its pages and scripts had been kept. That is the "loading
  exercises…" the owner sat in front of in airplane mode. Beside the POST
  there is now a **GET at the same address** (`GET …/cram`) which renders the
  whole deck, nothing chosen and nothing in the address to vary, which is
  exactly what makes it keepable: `lib/offline.py` names it in the record and
  `static/decks.js` asks for it when the POST cannot be made or when the
  computer is known to be away, taking the picks out of the whole deck here.
  And **the media is read off the RENDERED html** — `src`, `href`, `data-src`,
  `poster`, resolved back to files through the deck module's own `image_file`
  and `audio_file` — instead of by a regex for markdown links over the
  exercise's source, which matched nothing any exercise in this toolbox has
  ever been written as and so kept not one of his recordings;
* the phone's deck page offers **Take it out**. The computer hands over the
  whole queue — every card that is due, in the order it would give them,
  rendered as the learner sees them, each with the four interval labels **the
  computer** worked out;
* **while it is out the computer may only cram that deck.** Studying and
  editing are refused, in a line saying which device has it and since when; a
  second phone is refused as well. Cramming never schedules, so it is
  untouched (§18);
* the phone studies from that pack and keeps every answer. Whenever it can
  reach the computer — opening any deck page, coming back online, or *Give it
  back* — the answers are sent, and the computer **replays them in the order
  they were given, through its own scheduler**;
* the deck stays the phone's until **Give it back**, so it can be studied day
  after day away from the desk without being taken out again. **Giving it back
  leaves the kept copy alone**: coming home from a journey must not cost the
  whole deck again the next time. *Remove from this phone* is what takes it
  off — and it **refuses while the deck is out**, saying why, because what has
  been answered here is nowhere else until it has gone home;
* **Take it back**, on the computer, is for a phone that will not come home.
  After it, that phone's answers are **refused and listed** on the deck, with
  why — nothing is applied behind the learner's back, and nothing is dropped
  in silence. The list is cleared when it has been read.

**There is no scheduler on the phone, and none is needed.** The alternative
that queued answers without ownership would have wanted a JavaScript port of
`markdown/app/srs.py`, held equal to the Python by shared cases; a check-out
does not, because only one place answers the deck at a time. The phone shows
what the computer worked out; the computer schedules for real. One scheduler,
no drift.

The state lives in `checkout.json` beside the deck (`decks.checkout_of`,
`checkout`, `give_back`, `take_back`, `answers_from`), and the doors are
`POST …/checkout`, `…/return`, `…/takeback`, `…/answers`, `…/refused`.

## Parseh as an app

Installed from a phone's browser, the mobile interface is an app: an icon on
the home screen, opening on the whole screen, with no address bar and no
browser around the page. A browser installs a site when the site describes
itself, has a service worker, and is served over https with a certificate the
phone trusts. Here:

* **The manifest**, `/manifest.webmanifest` (`mobile.manifest()`): the name, the
  icons, `start_url` `/?mode=mobile` — the app opens on the mobile hub, in the
  mobile mode; `lib/parseh.js` sets the mode from the address and gives the
  address back without it (`history.replaceState`) before anything is painted
  — the scope `/` (the whole toolbox is the app), `display` `fullscreen` (on
  Android the phone's own bars go too; where that is not offered, an app's
  window, `standalone`), any orientation.
* **The icons**, `lib/icons/`: پ in white in the toolbox's own Noto Nastaliq Urdu
  on the accent, `#be3455` — 192 and 512 in a circle (`any`), 512 filling the
  square with the letter inside the middle 80% (`maskable`: the launcher cuts
  its own shape), and Apple's 180. `lib/icons/make.mjs` drew them (headless
  Chromium, a canvas, the letter's ink box in the middle: a nastaliq line box
  hangs the letter low), and is kept to make them again; it is not served.
* **The tags**, `mobile.app_head()`: the manifest's link, Apple's icon, the
  bars' colour for a light and a dark phone, and Apple's names for "an app".
  The hub, the shelf and the install page carry them; the decks' templates do
  too (`{{APP_HEAD}}`, `deckroutes.APP_HEAD`, held equal to `app_head()` by
  `tests/test_mobile_pages.py`); `lib/parseh.js` adds them to a page that has
  none — every book's reader, built without them. No favicon: a page keeps its
  own.
* **The service worker**, `lib/sw.js`, served at `/sw.js` so that its scope is
  the whole site, and registered by `lib/parseh.js` and the decks' `decks.js`
  while the mode is mobile (on every page, which costs nothing). It used to
  keep nothing but the offline page; §19 reversed that, and *Kept on this
  phone* below says what it holds now. What it keeps of **the app itself** is
  the way in — the hub at `/` and at `/?mode=mobile`, the shelves, the two
  libraries, `/m/kept/` and `/m/offline/`, with the sheets and scripts they
  load — but **its install event fetches two small pages and nothing else**:
  the way in is warmed afterwards, when a page that is open asks for it, and
  the studio's faces when a page that needs them does (below, *The app with
  the computer away*). An install event that fetched the whole shell is what
  stopped the app installing at all. And **every navigation has a deadline** of about 2.5 seconds, so
  that a computer which is unreachable rather than refusing does not leave the
  app on its splash for ever (at it, a page nothing kept asks the open pages
  whether the computer answers — *At the deadline the page is asked*, above).
  A new `APP`/`SHELL` name in it lets the old copies go.
* **Every release is a new worker, and says so** (TO-DO §13.16). A browser
  installs a new worker only when `/sw.js` is new bytes, so the server writes
  the release into it as it serves it (`mobile.worker()`: the version from
  `lib/version.py`, and the commit from the install's `.parseh-release.json`
  as the build, for the same version installed twice). The first mobile page
  of each opening of the app, and then at most one page in ten minutes, asks
  the browser for a new worker once it has found the computer (`lib/keep.js`
  `releaseCheck`; the browser's own check never came in two minutes of
  navigations, driven in Chromium);
  the new one notes at install whether it replaced another
  (`registration.active`, in the app's cache under `/__release`), keeps
  `parseh-kept-*` and `parseh-shared` at activate as always, and tells the
  pages it claims `{updated}`; a page opened later asks `{release}`. The page
  compares with the release this phone last knew (`parseh_release` in
  `localStorage`) and says once, in the toast, *Parseh was updated to
  <version>* — or *Parseh went back to <version>, an older version than this
  phone had*, by `lib/version.py`'s order — and **reloads nothing**. A first
  install says nothing. `renew` now writes a fresh copy into **every** cache
  that holds the address (the way in's, the shared one, the app's own two
  pages), where it used to stop at the first, which left the shared copy the
  old release's for good. Driven in `tests/mobile_pages.mjs` (`update`).
* **Installing**, `/m/install/` (`mobile.install_page()`), from the mobile hub's
  *As an app* door (not drawn inside the app: `display-mode`). It says, live,
  where this phone stands — in the app already; a browser that installs nothing;
  a certificate not trusted yet (the service worker is refused over it); ready —
  and gives the two steps: trusting the certificate, and installing (an
  *Install Parseh* button while Chrome offers one, and the menu's *Install app*,
  or Safari's *Add to Home Screen*). In the mobile mode `lib/parseh.js` keeps
  Chrome's offer (`beforeinstallprompt`) for the page's own
  `[data-parseh-install]` buttons, `Parseh.app.prompt()`, rather than a bar of
  the browser's over whatever is being read.
* **The certificate.** A browser tab goes on after one warning about a
  certificate nobody vouches for; an app does not. So `serve.py` (`make_cert`)
  makes two: **an authority of the machine's own** (`.tls/ca.pem`, its key
  `ca-key.pem`), made once and never again — what a phone is told to trust,
  once, from the install page (`/m/install/parseh-ca.crt`, the authority's
  certificate in DER as `application/x-x509-ca-cert`, which an iPhone offers to
  install as a profile and an Android phone saves for *Settings* → *Install a
  certificate* → *CA certificate*) — and **the server's**, signed by it for
  every name and address the machine has, for 825 days (the most an iPhone
  accepts), with the server-authentication use Apple requires, made again
  when it nears its end or when `serve.sh cert` asks: a phone that trusts the
  authority trusts each one, and nothing is installed again. **The authority
  can vouch for this machine and nothing else**: its name constraints permit
  only `localhost`, the machine's own name, `.local` and tailnet (`.ts.net`)
  names, and the private and Tailscale address ranges (127/8, 10/8,
  172.16/12, 192.168/16, 100.64/10) — so it is good for nothing on the
  internet, were its key ever copied off the machine; the server's certificate
  names nothing outside them. A certificate made before the authority (one
  self-signed, `O=Parseh`) is replaced by the pair once, at the next start —
  each browser warns once more, as it did about the old one; **one put in
  `.tls/` by hand** — Tailscale's (`tailscale cert`), Let's Encrypt's — is used
  as it is and never touched, and the install page then has no authority to
  hand over (a phone trusts those already). Over plain http there is no app,
  except from the computer itself at `localhost`.

`tests/test_mobile_pages.py` holds the manifest, the icons' sizes, the tags on
every page, the worker's rules, the install page and the certificate — the
authority and the server's, their constraints and lifetimes, renewal, the
migration, a hand-placed one left alone, and a real TLS server handing over the
authority to a client that trusts nothing else. `tests/mobile_pages.mjs` (its
part *app*) drives it: the app's address, Chromium's own verdict that the pages
are installable (`Page.getInstallabilityErrors`: nothing but the test's
incognito profile), the worker taking the pages over, **the app getting itself
ready afterwards** — the page asking for the way in by itself, the hub counting
the addresses as they come and saying nothing once they are all there, the
studio's faces on no phone that has only installed the app and all thirteen of
them the moment a note is opened — the install page, and — the server stopped —
the page that says so. Its part *kept on this phone* waits for the worker's own
*that list is done* before it stops the computer, since the way in is warmed
now rather than installed.
