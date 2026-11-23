# exlex studio

**Markdown → XeLaTeX → verified PDF for lexical essays about a language,
plus a local web studio to read, annotate and drill them.**

`exlex` turns a markdown file — typically written by an LLM given the
prompt the studio's LLM prompt page copies (it resolves the sections of
[`exlex/PROMPT.md`](exlex/PROMPT.md) for the features ticked) plus a
question — into a typeset PDF
in which the **target language** appears large, in its own font (Vazirmatn
for Persian, Noto Naskh Arabic for Arabic, Noto Serif Devanagari for Hindi,
Noto Serif CJK JP and CJK SC for Japanese and Chinese, and the text face
itself for the Latin-script ones: Italian, French, German, Turkish,
English, Spanish, Catalan), with **provably correct rendering**
— right-to-left inside left-to-right prose for the RTL languages — and the
studio is a local web application around it: a document library, a reading
view with the typography of the LaTeX output, a live-preview editor, hover
annotation tools, a glossary browser with flashcards, and one-click
verified PDF builds. The directory is `markdown/`; it was `markdown
persian reader/` for as long as Persian was the only language, which is
still the default when a document names none. The languages come from the toolbox's
registry, `../lib/languages.json`; how they were designed in is
[`../docs/languages.md`](../docs/languages.md).

**A second library.** The same store, editor and renderer also serve the
*notes* that sit in the seams of a book or a video, kept in that content's own
`markdown/` directory rather than here. Nothing is duplicated for them: the
library root is a thread-local (`store.lib()`), the mount prefix another
(`server.base()`), and a third says the document is never built — a note is
read on its page and has no PDF and no `.tex`. See `app/notes.py`.

It was extracted from a working session in which the document was first
built by hand; every non-obvious choice below was forced by an actual
failure, and the failures are documented so future refactoring doesn't
re-discover them.

---

## Quick start

The studio is one of the doors of **Parseh**, the toolbox one directory up,
and is normally served with the book reader, the video player and the
exercise decks by `../serve.py`:

```bash
cd .. && ./serve.sh                   # the studio → https://localhost:7654/studio/
                                      # its exercise decks → https://localhost:7654/exercises/
```

On its own, for hacking on it:

```bash
python3 app/server.py                 # the studio alone → http://127.0.0.1:8766
                                      # (the decks at the same /exercises/)
```

or the toolchain on its own:

```bash
python3 exlex/exlex.py setup                            # one-time env prep
python3 exlex/exlex.py build ../tests/fixtures/studio/persiano/persiano.md
python3 exlex/exlex.py build … --size 17 --mono         # large print, black and white
```

`build` ends with a verification line counting the target-language strings
found in the PDF in the right order (`N/N … strings correct`); treat
anything short of the full count as a broken build (exit code 1).

**Requirements.** TeX Live with **XeLaTeX** and the TeX Gyre OpenType
fonts (any full-ish distro), Python ≥ 3.9, PyMuPDF for verification, and
network access to github.com only when the fonts must be fetched.
The web app itself uses **only the Python standard library**. Inside Parseh
it is mounted under `/studio` — the server sets `BASE`, the templates carry
`{{BASE}}`, the script reads `data-base` — and the **Stop server** button
on any page stops the whole toolbox, naming first whatever the server is
still working on. Every page also loads the toolbox's `/lib/activity.js`,
the pill in the corner that says what is running (a PDF being built, a
backup going up or coming down) on every page until it is over — see the
guide's *The Working… indicator*
(`html-guide/markdown/getting-started/working-indicator.md`). Run alone, it binds to 127.0.0.1, has no
such list, and the page's tag for it simply finds nothing.

On first start the server copies the web fonts into `app/static/fonts`
(Vazirmatn and Noto Naskh Arabic from the toolbox's `../lib/fonts`, TeX
Gyre located via `kpsewhich`; Japanese uses the device's CJK fonts),
registers Italian hyphenation in the background, and copies whatever
example documents `exlex/examples/` holds into the library, once each —
which at present is none. The per-language font tokens every page
links, `static/langs.css`, are generated from the registry and served by
the studio itself.

## Repository layout

```
exlex/                  the toolchain — usable entirely on its own
  exlex.py              CLI: build / verify / inspect / setup
  mdparser.py           markdown dialect → block model (no TeX knowledge)
  texgen.py             block model → main.tex (all TeX knowledge lives here)
  verify.py             PDF ↔ source round-trip proof of RTL correctness
  envsetup.py           idempotent env prep (deps, fonts, hyphenation+format)
  template.tex          preamble: fonts, direction macros, colours, \voce, lists;
                        the target-font block and the vertical macro are placeholders
                        texgen fills per language
  PROMPT.md             the prompt that makes an LLM emit this dialect
  assets/fonts/         Vazirmatn + Noto Nastaliq Urdu (+ Noto Naskh Arabic from ../lib/fonts)
  assets/hyph/          hyph-it.tex + loader (see "Hyphenation")
  examples/             the example documents — none at present (see its .gitkeep)

app/                    the studio web UI
  server.py             stdlib-only HTTP server: pages, JSON API, builds
  htmlgen.py            block model → HTML, the twin of texgen.py
  store.py              library CRUD, tags, search, prompt override
  decks.py              the exercise decks: store, copy from a document, export/import (no HTTP)
  deckroutes.py         the decks' pages and JSON API, mounted at /exercises in both servers
  srs.py                the decks' scheduler: Anki's SM-2, pure functions, no clock of its own
  templates/            index / doc / edit / prompt / 404 page shells;
                        decks / deck / study for the exercise decks
  static/               app.css, app.js, decks.js (the deck pages), langs.css (generated),
                        fonts/ (provisioned at startup)

library/<language>/     the documents, one folder per target language (persian, arabic,
                        italian, japanese, french, german, turkish, english, hindi,
                        spanish, chinese): source.md, meta.json, images/, audio/ and
                        the compiled build/ per document
```

The recordings cut in a book or a video wait in the toolbox's **clip tray**,
`../clips/` (`../lib/clips.py`), until a document, an exercise deck or an
Anki card copies them in; see **Brought in from the clip tray** below.

A document lying directly under `library/` — the layout before languages —
is still read, as Persian, with a note to move it; `/studio/doc/<id>` does
not carry the folder, the id being unique on its own.

Regenerable output — `out-*/`, `library/*/*/build/`, both font directories,
`__pycache__` — is git-ignored; the markdown is the single source of
truth, so fix the `.md` or the generator, never the produced `.tex`.

---

## The markdown dialect (authoritative)

Front matter: `title:`, `subtitle:`, `note:`, `lang:`, `target:` between
`---` fences. Two languages, and they mean different things:

- `target:` is the **language being learned** — a registry code (`fa`,
  `ar`, `it`, `ja`); omitted, the document is about Persian. It decides
  which script the run detector looks for, which font the target text is
  set in, which direction a target block takes, whether lemma headings have
  a reading field, and which folder of the library the document is filed
  under.
- `lang:` is the ISO code of the **prose** language (`en`, `it`, `fr`, …)
  and is not cosmetic: it chooses the hyphenation patterns the typesetter
  breaks words with. Omitted, the document is set as English. A Japanese
  note written in Italian has `target: ja` and `lang: it`. The prose
  language need not be one the toolbox teaches — `pt`, `nl`, `ca`, `ro`,
  `pl`, `ru` are in the table too (`texgen.hyphenation_for`), because
  writing *in* a language asks nothing of the toolbox but where to break its
  words. The reading editions and the videos draw the same distinction in
  their own metadata, `"language"` and `"gloss"` in `book.json` /
  `video.json`; the codes are the same ones, kept in `../lib/languages.py`
  (`GLOSS_CODES`) because `lib/` imports nothing outside itself, so anything
  a book may be glossed in can be written in here as well.

Blocks, in the order the parser tries them:

| Markdown | Rendered as |
|---|---|
| `## text` | numbered `\section` — **never number it yourself** |
| `## فارسی \| translit \| etym \| = *translation*` | lemma header `\voce` (huge target text); triggers when the first `\|`-field is a run of the target script — or, for a Latin-script target, when the heading has two or more `\|` fields. The trailing `= *…*` is optional, printed nowhere, and puts the headword into the glossary |
| `## 漢字 \| かんじ \| kanji \| etym \| = *translation*` | the same for a **reading language** (Japanese): four fields, the **reading first**, then the transliteration; the reading is shown above the transliteration. The fourth field exists only when the document's target has a reading — Persian headings keep their three |
| `### text` | unnumbered `\subsection` |
| `> ...` block | tinted highlight box; anything the document can hold goes inside it — paragraphs, lists, tables, headings, even another box |
| pipe table — the line under the header has one dash or more a cell, as in GFM (`\|-\|-\|`, `:-:`, `---:`), and two columns at least | booktabs table; `:-:` centre, `-:` right, anything else left; a body cell that is only `—`, `--` or `-` is empty; ≥4 cols → `\small`, ≥6 → `\footnotesize` |
| `- ` / `1. ` lists | itemize / enumerate; one nesting level for bullets |
| list where *every* item starts `**Label**` | description list; if any label is in the target script and long → `lex` style (label on its own line) |
| paragraph of the target script only (≥3 characters of it, whether that is one word or five) | stand-alone display line, `\large`, breakable — RTL for Persian and Arabic, an LTR target block for Japanese; a Latin-script target has no automatic block |
| anything else | paragraph |

Inline: `**bold**`, `*italic*` (Latin only), `` `code` ``, `→`/`->` →
`$\rightarrow$`, plus the annotation forms:

| Markdown | PDF | Web |
|---|---|---|
| `فارسی = *translation*` | grey `=`, translation in italics | same |
| `testo[^id]` + `[^id]: nota` | `\footnote` at the page foot | hover cloud + list at the end |
| `^[nota inline]` | same, numbered in source order | same |
| `[testo](https://…)` | `\href`, clickable, coloured | `<a>`, opens in a new tab |
| `[](doc:The shape of a word)` — a link to another document of the same library, by its **name** (its title, spaces and all); empty label means "show that document's title" | the resolved text, in the link colour (nothing to click through to on paper) | `<a>` to `/doc/<id>`, same tab; red and dashed while no document has that name |
| `[متن]{teal}` / `[متن]{#2F6B8F}` | `\textcolor{fateal}` / `\textcolor[HTML]{…}` | tinted span, editable by hover (HSV picker for hex) |
| `[تند]{translit:tond}`, or a 2–3 word group `[یواش برو]{translit:yavâš borou}`; colour may share the braces: `{teal translit:tond}` | mark vanishes — bare `\pe` (colour kept if present) | renders bare; transliteration shown in the hover overlay and in the glossary |
| `[漢字]{kana:かんじ translit:kanji}` — the **reading** mark of a reading language (`reading:` is an alias of `kana:`) | mark vanishes; the reading is not printed inline | renders bare; the kana is shown above the transliteration in the hover overlay and fills the glossary's reading column |
| `[bello]{tl}`, or the code `[bello]{it}` — a **marked run** of a Latin-script target. Italian, French, German, Turkish, English, Spanish and Catalan have no character range of their own in the registry, so nothing detects a run of one — and in prose that is Latin-script too, which is what `lang:` usually names, nothing tells them apart by eye either (an English document's target not by so much as an accent) — so every run of them is marked; any bracket mark already on it (`[bello]{translit:'bɛllo}`, `[bello]{teal}`) counts as the mark too | set in the target font | the `.fa` span: target font, scaled by the slider, colourable and translit-able by hover |
| `![didascalia](images/f.png){width=55 align=center offset=-10}` | `\includegraphics` in an indented minipage | `<figure>`, laid out by click |
| `![didascalia](audio/f.mp3){width=60 align=center offset=0 start=1:05.2 end=1:09}` — a **recording**, written like a picture | a card like the video's, not a link: ♪, the caption, `audio · f.mp3 · 1:05.2–1:09` | `<audio>` player laid out like a figure, playing only its clip |
| `@[didascalia](youtube url){… start=90 end=150}` | clickable play-card linking the clip | embedded player, clipped to start/end |
| `✗فرم` (or `❌فرم`) | red ✗ + form in red (DejaVu glyph) | red ❌ + form in red — never colourable |
| `✅ فرم` | green ✓ | green ✅ — no effect on what follows |
| Latin-free paragraph (punct/emoji ok) | `fapar` env: RTL, right-aligned, the target font — for an RTL target | `<p dir="rtl">`, automatic |
| `[امروز یک فایل PDF فرستادم]{tl}` — a **block of the target language**; the document's own code (`{ja}`, `{ar}`, `{it}`) is an alias, and `{fa}` / `{rtl}` still work for Persian documents | RTL target: TeXXeT R with `\beginL` islands (Latin words next to each other one island), brackets mirrored, emoji dropped. LTR target: a left-to-right paragraph in the target font. A Latin word is `{\tllatin …}`: in the target face when it has Latin letters, else in the family round the run (Noto Naskh Arabic, Noto Nastaliq Urdu and the Devanagari faces have none) | one isolated unit in the language's direction, emoji kept |
| `[a^2+b^2=c^2]{math}` — **mathematics in the line**. LaTeX notation. Neither `$` nor `\[` is a marker: `$` is a character somebody writing about money types by accident, `\[` is LaTeX's own and would have to be escaped everywhere else, and a brace word after a bracketed text is what every other mark here looks like. **The body may hold brackets** (`[x \in [0,1]]{math}`, `\sqrt[3]{x}`) — it is read up to the `]{math}` that ends it, and no formula contains that; it starts at its own `[`, so a mark, a link or a blank before it in the paragraph stays out of it | `\( … \)`, the author's notation untouched — the document IS LaTeX | `<span class="math" data-tex="…">`, drawn to `<svg>` by MathJax (lib/mathjax.js) |
| `{tl font=nastaliq bg=quote}` — `font=<alt_key>` is the language's **alternate face** (`nastaliq` for Persian, `gothic` for Japanese; nothing for the others); `bg=` one of `quote sand rose sage lilac` | the alternate font (Noto Nastaliq Urdu, Noto Sans CJK JP) + `\colorbox` tint | the alternate web font + CSS tint (dark-theme variants) |
| `{tl vertical height=22}` — a **vertical** block (also `mode=vertical`, `tategaki`), for languages that can be set vertically (Japanese); `height` is the column height in em, default 22 | a rotated box: the text set in a `minipage` whose width is the column height, in a font loaded with `Vertical=RotatedGlyphs`, rotated −90° — true tategaki without any CJK package; in large print the column is never longer than the page less four lines (its ems grow with the print) | `writing-mode: vertical-rl; text-orientation: mixed`, a fixed block height so the columns wrap, starting at the right and scrolling sideways when needed |
| `[testo]{la align=right bg=sand width=60 offset=20}` | minipage at the image indent, `\raggedleft`/`\centering`, `\colorbox` | positioned block, laid out by click like an image |
| `⏎` | `\newline` | `<br>` — source newlines stay ignored; ⏎ forces one |

Colour names: `crimson`, `indigo`, `teal`, `violet`, `amber` (defined in
`template.tex` as `fa<name>`; unknown names are left as literal text).
Images and videos sit on a line of their own; the image path must be
`images/<file>` (PNG, JPEG, WebP, GIF, SVG or PDF -- a HEIC is turned into a JPEG as it is
added -- stored per document by the studio — the
prompt tells the LLM *not* to emit them, they are added by the human;
each vector format is unreadable by one of the two renderers, so each
gets a twin made where it is missing — and **both twins stay vector**,
since a figure supplied as PDF or SVG was supplied that way precisely so
it could be scaled without loss. An SVG becomes `<name>.svg.pdf` at build
time for XeLaTeX; a PDF's first page becomes `<name>.pdf.svg` at upload
time for the browser, which shows no PDF inside a figure. Glyphs are
written as outlines, so the SVG needs none of the PDF's fonts to render
exactly as the PDF does. Both twins are hidden from the image manager and
removed with the file they came from, and a missing one is rebuilt on
demand — a figure stored before the twin existed repairs itself). `width` and `offset` are percentages of the text column, `align`
is left|center|right; both renderers compute the same left indent
(`texgen.image_indent`), so the figure sits in the same place on screen
and on paper. Video `start`/`end` accept seconds or `m:ss`, whole seconds
only (YouTube takes nothing finer, so a fraction is dropped); a recording's
take hundredths too (`65.5`, `1:05.25`) — see **Recordings** below. The ✗ red
(`faungram`) is deliberately outside the five-colour palette and the
generators strip any colour mark placed on an ✗-marked form.

### Recordings

A recording is written exactly as a picture is, on a line of its own, with
its path under `audio/`:

```
![the greeting, spoken](audio/greeting.mp3)
![one sentence of the lesson](audio/lesson.m4a){width=60 align=center offset=0 start=1:05.2 end=1:09}
```

`width`, `align` and `offset` place it as they place a picture, and it
shares the pictures' numbering: recordings, pictures and videos are counted
as one series, which is how the layout panel finds the line to rewrite. `start` and `end` cut out the stretch to play, in
seconds or `m:ss`, to the hundredth; either may be left out (no start is the
beginning, no end the end), and an end that is not after the start is
ignored. The file is one of MP3, M4A, AAC, Ogg (`.ogg`, `.oga`), Opus, WAV,
FLAC or WebM (`lib/audiofile.py`, the one list every door of the toolbox
asks), stored by the studio in the document's `audio/` folder and at most
30 MB. **The extension follows the bytes**, as a picture's does: a file
called `x.mp3` that holds a WAV is stored as `x.wav`, because a browser and
Anki both believe the extension before the content. Like pictures,
recordings are added by the human: the prompt (rule 14) tells the LLM never
to write one, and to keep the ones a document it revises already has.

On screen the line is a `<figure class="img audio">` holding an
`<audio controls>` whose address carries the clip as a media fragment
(`lesson.m4a#t=65.2,69`); the page's script keeps it inside that window
(see **Playing a clip** under the studio). On paper a recording cannot be
played, so the PDF draws the card a video gets, placed like a figure but
linking nowhere: a ♪ (DejaVu's; `\sharp` where DejaVu is missing), the
caption, and `audio · lesson.m4a · 1:05.2–1:09` in small grey type —
`dal …` or `fino a …` when only one end is given. The file itself is never
copied into the build or read by TeX. A path under `audio/` that does not
name a recording (`audio/notes.txt`) shows `not an audio file:` and the path
on screen, and prints nothing. A recording may stand in a `>` box like
anything else.

### Flashcards that hold blocks, and flashcards that speak

The exercise dialect is in
[`../docs/studio-exercises.md`](../docs/studio-exercises.md); two things in
it reach into the renderers.

**A jolly card's four fields** (`front-primary`, `front-secondary`,
`back-primary`, `back-secondary`) may each be one line or a `key: |` block
whose lines are indented under it, and a block may hold **any block of the
dialect**: paragraphs, lists, tables, `>` boxes, `###` headings, target
blocks, pictures, recordings, videos, footnotes. A side needs one of its
two fields. `mdparser.parse_exercise` keeps the ⏎-joined text it always
kept in `fields` and the dedented block beside it in `raw_fields`; both
renderers read a field with `mdparser.card_field`, which parses it as a
small document. **One plain paragraph renders inline, exactly as before**,
so every card written before blocks were allowed looks the same; anything
else renders as blocks. A heading on a card is unnumbered and never enters
the contents, a footnote defined on a card joins the document's notes, and
a field may not hold an `:::exercise` (`front-primary cannot hold an
exercise`). A line that is exactly `:::` still closes the exercise, even
indented. In the PDF every card is a card to cut out and fold
(`texgen._card_sides`, `\expapercard` in `CARD_PAPER`): its front in the
left half of a frame with round corners, its back in the right, a dashed
line between them; a jolly field of one paragraph is a centred line there
(`\exlexfitpar`, so nothing crosses the fold), a field of blocks is laid
out as the page lays it out, its tables fitted to the half and its target
runs breakable (`_CARD`).

**What a card does not offer.** A figure on a card — picture, recording or
video — has no layout number and no ⚙ handle, and a click on a picture there
turns the card rather than opening a panel; its layout is written by hand.
A field drawn as blocks offers nothing to the hover editors either: no
transliteration or kana cloud, no ✎ on a target block, no layout panel on a `{la}` block. Those
editors find a word by its occurrence, and `store` blanks such fields before
it counts (`mdparser.card_spans`), so the n-th word the page offers stays the
n-th the source holds. A field that is one plain paragraph is offered and
counted as it always was.

**Vocab and opposites cards** take `front-audio` and `back-audio` beside
`front-image` and `back-image`, each the path of a recording
(`front-audio: audio/word.mp3`); anything else is the error `front-audio
must name a file under audio/ (e.g. audio/word.mp3)`. On a side the picture
comes first, then the recording, then the text. On screen the recording is
a 🔊 button over a hidden `<audio>` (`.ex-card-audio`); in the PDF the side
starts with `♪ word.mp3`.

**Where a vocab or opposites card draws `context`, `notes` and `source`** is
`mdparser.card_extras(fields)`, the one rule both renderers read: on the side
the flip reveals, so on the front of a `reverse` card, unless a `context-side`,
`notes-side` or `source-side` says `question` (`answer` is the default; any
other value is an error of the card). It answers in the halves a card is
composed in, the word's first (`htmlgen._render_exercise_flashcard`,
`texgen._card_sides`), and `reverse` turns them round after, as it always did;
a custom `back` replaces them all. A `both-random` card is composed forward and
marks each of them `data-extra`, which `app.js` `drawFirstSide` moves to the
other side when the draw shows the back first; no other card's markup carries
the attribute. A deck needs nothing of its own: `decks._faces` writes the two
directions of a `both-repeat` card, and each is drawn by the rule for its own.

### Mathematics

`[a^2+b^2=c^2]{math}` sets a formula in the line. On its own it is a fence,
the same shape an exercise has one line shorter:

```
:::math
\int_0^1 x^2\,dx = \tfrac13
:::
```

The notation is LaTeX. **Neither `$` nor `\[` is a marker here** — `$` is a
character somebody writing about money types by accident, `\[` is LaTeX's
own and would have to be escaped in every other mark's content, and a brace
word after a bracketed text is what every mark in this dialect already
looks like.

**Two destinations, and neither is a picture stored anywhere.** On paper the
document *is* LaTeX, so the notation goes through as itself and TeX sets it
(`amsmath` is loaded for it). On the web it becomes
`<span class="math" data-tex="…">` with the notation also as its text, and
`lib/mathjax.js` draws it to an `<svg>` — MathJax (3.2.2, `tex-svg`) is
vendored whole in `lib/mathjax/` and is fetched **only by a page that turns
out to have a formula on it**. A page whose script never runs — a print, a
document opened off the disk — still *says* what the formula was.

Rules worth knowing:

* **The body may hold brackets.** `[x \in [0,1]]{math}`, an interval open
  at one end, `[x^2 + [0,1)]{math}` or `[x \in (0,1]]{math}`, the French
  `]0,1[` and `\sqrt[3]{x}` are ordinary mathematics; the mark is read up to
  the `]{math}` that ends it, and no formula contains that. This is why its
  body is not the bracketless one `{tl}` has.
* **A formula starts at its own `[`.** A colour mark, a link or a blank
  written before it in the same paragraph — `[تند]{teal} then [x^2]{math}`,
  `[the site](https://…) and [x^2]{math}`, `[[slot]] mg/L as [CaCO_3]{math}`
  — stays out of it, and so colouring a word from the palette never breaks
  the formula after it. A bracket the formula opens and closes itself may
  be followed by anything (`\sqrt[3]{x}`); a `]` it did not open may not be
  followed by `{`, `(` or `]`, which is how another mark, a link or a blank
  ends — except its own last one, `(0,1]]{math}`. One reading stays
  ambiguous: plain brackets in the prose before a formula,
  `[sic] … [x]{math}`, have the shape of `]0,1[` and go into it; write
  them after the formula, or as parentheses.
* **A formula is left to right whatever the line is.** Mathematics is
  written left to right in every language, so a formula inside a Persian or
  an Arabic sentence is isolated from the paragraph's direction
  (`unicode-bidi: isolate`) — the CSS of the `\babelsublr{\mbox{…}}` the
  reading editions already use.
* **A blank cannot sit inside a formula.** `[[slot]]` cuts a sentence into
  pieces and a formula cut in half is two halves of nothing; put the blank
  beside the formula, not in it.
* **A mistake is shown, not hidden.** MathJax does not refuse bad notation,
  it draws it and marks it; the page then keeps the notation as written and
  says what is wrong, and the editor's sheet says the same in MathJax's own
  words ("Missing close brace").

In the editor: **math** wraps the selection, **∑ Maths** opens a sheet with
the picture under the notation and the choice of line or block. The exercise
form has the same sheet on its own button, writing into the field the hand
was last in.

### Glosses

A gloss is `فارسی = *translation*`: the `=` is greyed automatically and
**the translation itself is written in italics**. The italics are not
decoration — they are what marks where the translation stops, which is
otherwise undecidable:

```
آهستگی = *lentezza, delicatezza*          both words are the gloss
حرکت آهسته = *il rallentatore*, nel cinema  only the first is
```

Everything the translation covers goes inside the asterisks, several
near-synonyms included; commentary, context and register notes stay
outside. This is what lets the studio harvest a correct glossary from
the document (see **Glosses overlay** below). For a Latin-script target the
head is a marked run: `[bello]{tl} = *beautiful*`.

A **lemma heading** may carry one too, as a fourth field: `## تند | tond
| mp. tund | = *sharp, spicy, fast*`. It is printed nowhere — the heading
already shows the transliteration and the etymology — and exists purely
so the headword enters the glossary, which otherwise only ever sees the
words a document glosses in passing. Written without the pipe, hung off
the etymology (`… mp. tund = *fast*`), it reads the same; there the
italics are required, so an ordinary `=` inside an etymology note
(`mp. tund, 'x = y'`) is not mistaken for a gloss.

Write a gloss **without** the italics and the harvester takes exactly
one word — the first after the `=` — and marks the entry as guessed:
the glossary shows that row in red with a hover cloud saying what to
fix. It deliberately does not try to infer the end of the translation
from punctuation, because a plausible-looking wrong answer is worse
than a visibly incomplete one.

### Links between documents

A link to another document names it by its **name** — its title, exactly
as the front matter's `title:` line spells it:

```
[](doc:The shape of a Persian word)          shows the target's current title
[the companion piece](doc:Verbs of motion)   shows your own words
```

The name is compared the way a Mac or a Windows machine compares file
names: case-blind, and with runs of spaces counted as one, so
`doc:verbs  of Motion` reaches "Verbs of motion" too. A parenthesis inside
a name is written as it is when it pairs up — `doc:Table 7-6 (percentages)`
— and a lone one, or a backslash, with a backslash in front of it:
`doc:Notes \(draft`. The **Doc link…** button writes all of this for you:
it lists the other documents in the library (filterable, the current one
excluded), takes an optional shown text, and inserts the link at the
cursor, replacing the selection if there is one.

The shown text may hold marks of its own, one level deep: a stretch of the
target language, `[[il nome]{tl}](doc:Nomi)` (what the button writes when
the words selected are one), or a word coloured or transliterated,
`[the [verbs]{teal}](doc:Verbs of motion)` (what the colour tools write
when you colour a word of a link on the page). Such a link is a link like
any other: on the page and in the PDF, to a rename, to **↩ Linked from**,
and to the colour tools, which never take the name after `doc:` — it is
not on the page — for words to colour.

**Renaming follows the links**, as in Obsidian: a save whose `title:` line
says something new renames the document, and every link in the library
that named it by the old name is rewritten to the new one — its shown text
kept, the document's own links to itself included (the editor takes the
rewritten text back), and the exercises of the decks too, which link to the
studio's documents the same way. A document rewritten only because another
one was renamed keeps its "updated" date; a PDF built from it is marked as
out of date. A change of case or of spacing is a rename like any other: a
link always spells the name as it is now. An editor left open meanwhile —
in another tab, say — follows the renames too: its next save writes its
links by the new names instead of putting the old ones back (the renames
it follows are the ones this run of the server made; after a restart, a
page opened before it has none to follow).

A document's page lists what links to it: **↩ Linked from** (see "Reading
view" below).

A link reaches only the documents of **its own library**: the studio's, or
the notes of one book, or the notes of one video. A link whose name no
document there has — its target deleted, or not written yet — is not
dropped: it renders in red, dashed, with a tooltip naming the document it
is waiting for, and the moment a document of that name exists again
(created, uploaded, restored or renamed) the same link works again, with
nothing rewritten.

**A name is one document's.** No two documents of a library share one
(compared as above), so a link can only mean one of them. Whenever a
document would take a name another one has — a **Save** (or Save & view,
or Ctrl+S) whose `title:` says it, a new document's first save, **Paste
LLM answer**, **Upload .md / .zip** (after its header, when it had to be
asked for), **Load from backup** (a backed-up document of another id; one
with the same id is the same document and is kept or replaced as ever) —
nothing is written and a dialog, "This name is already in use", shows each
clash with two fields: *Rename the document already in the library* (with
a link to open it in a tab of its own) and *Rename the document being
saved* (or *added*, naming its file), both filled with the names they
have. Change either, or both — they may even swap names — and *Use these
names*: the server checks them all again, and a name still taken is said
under its own field ("“X” is already the name of another document — choose
another name") while the dialog stays open for another. Every link to a
document renamed there follows it; a link inside the upload or the backup
that named another document of it follows *that* one, since it was written
for it. Cancel writes nothing, and the editor keeps its text. The names
given for a backup are given again to its **Replace them**; should one of
the documents put back by it hold such a name, the dialog asks again,
with a field for each of the two. The same holds in a book's or a video's
notes. A name cannot hold a `|` either — a link to it in a table would
split the cell it stands in — and the same dialog ("This name cannot be
used") asks for another. A document named with one before names were
checked keeps it; the **Doc link…** button links it by its uid, which
reaches it too. A document made without a person to
ask — a new note beside a book is "A note", the next "A note 2" — gets
" 2", " 3"… after a name already taken, a text with no title at all is
"Untitled", and **Duplicate** names its copy "… (copy)", then "… (copy 2)",
in its front matter as in the library.

Links written before names stored the target's **uid** — twelve hex
characters, `[](doc:9f3c1a7b20de)`, the permanent id every document keeps
in its `meta.json`. They still work: a link whose name no document has but
which spells the uid of one reaches that one. And they are rewritten, once:
the first time the server meets a library (the studio's at start-up, a
book's or a video's notes when they are first opened) it writes every such
link as a link by name, its shown text kept, and gives any two documents
that still share a name — nothing forbade it before — names of their own:
the oldest keeps it, the others get " 2", " 3"…, each said on the console.
The same pass runs after every upload and restore, for the links that came
in with them — a book's or a video's notes included, when **Bring a book
back** (or **Bring a video back**) or a shelf's **Load from backup** puts
them back: they come as they were written, and are put right as they
arrive, over notes opened earlier in the same run of the server too.

### Persian (and Arabic) punctuation

Persian punctuation — the Arabic comma `،`, semicolon `؛`, question mark
`؟` — belongs **only inside a continuous Persian sentence or clause of
its own**, typically inside a `[…]{tl}` block or a full Persian display
line; the same holds for an Arabic document. Everywhere else the document
is running prose in whatever language the answer is written in, and that
prose takes its own Latin punctuation. The test is always what the mark is
punctuating, never how much Persian sits on either side of it:

```
کند, سریع, تند                     a list — Latin comma
… estremista; [تندباد]{…} = *raffica*   Latin semicolon between clauses
چرا این‌قدر یواشی؟                  a whole Persian sentence — Persian ؟
```

The Arabic comma sits inside the Persian Unicode block, so a `،` next to
unspaced Persian is absorbed into the `\pe{}` box and disappears from
the Latin side of the line — this is a silent corruption, not just a
wrong glyph.

### Target-language prose: blocks and runs

The classic run detector splits on anything outside the target script, so
`درود!!!` used to shatter into fragments an LTR paragraph then scrambled.
Now a paragraph with **no Latin letters** renders as an RTL paragraph
automatically (for `fa` and `ar`; for `ja` a paragraph of nothing but the
target script is an automatic LTR target block; a Latin-script target has
none), and `[…]{tl}` forces the same for stretches that embed Latin words.
`{tl}` means "target language"; the document's own registry code (`{fa}`,
`{it}`, `{ja}`, `{fr}`, …) is an alias, and `{rtl}` is still accepted in
Persian documents. A block may span several source lines (multiline form,
`]{tl}` on its own closing line); newlines still join, `⏎` forces real
breaks. Content is
**opaque** (no markdown, no gloss `=`, not colour-pickable) and is
**excluded from the glyph-level verification** — the browser bidi /
TeXXeT-with-islands emission is trusted there; classic `\pe/\pel` runs
remain fully verified. A vertical block is excluded the same way.

Footnotes are numbered document-wide in source order; inside headings,
`\voce`, tables and boxes — where `\footnote` is unsafe or would be
swallowed — the generator emits `\footnotemark`/`\footnotetext` instead,
keeping LaTeX's counter in step with its own. Runs of a **script**
language's text are detected automatically from the registry's character
ranges — space-joined words for Persian and Arabic, contiguous characters
for Japanese, which has no word separator — and are **opaque**: no
markdown is interpreted inside them. Runs of ≤ 4 words become `\pe{}`
(atomic), longer ones `\pel{}` (line-breakable); in large print the limit
shrinks with the line, by the ratio of the sizes (`run_is_long`), so at
20 pt a run of three words is breakable. For a **Latin-script**
target nothing is detected: every run is marked, `[bello]{tl}` or any
other bracket mark on it, and the occurrence counting the hover tools rely
on follows the same rule, so the palette and the source always agree. The
renderers hold no regex for any script; they ask the registry for the
document's language.

---

## The studio

### Library (`/`)

Every document is stored under `library/<language>/<id>/` (`source.md` +
`meta.json` + `build/`), the folder being the target language's; `meta.json`
records the `target`, and a save that changes the front matter's `target:`
moves the document to the new folder. Cards show title, a subtitle aware of
the target script, a **language badge**, tags, build status, verification
badge and stats. A row of **language chips** above the cards filters by
language — the same chips, and the same remembered choice, as every other
index page of the toolbox. Search matches title/subtitle/note/tags with an
optional full-text mode. A tag chip cycles include → exclude → off
(Shift-click excludes at once): a document must carry every included tag
and none of the excluded ones. Sortable by updated/created/title.
**Backup** downloads the whole library as a zip. **Download N shown**
downloads only what the search, the tags and the language chip leave on the
page, as one zip of `.md` sources (`studio-<n>-documents-<date>.zip`): each
file is named by the document's id without its random suffix, or by the
whole id where two would share a name. It is disabled when nothing is
shown.

**Getting documents in** — the normal path is *Upload .md* (multi-file):
the authoring prompt asks the model to write a `.md` file, so you
download it and drop it here. *Paste LLM answer* covers models that
answer inline instead — the markdown inside the code fence is extracted
and the surrounding chatter discarded. *+ New* starts from that language's
starter page — `exlex/starters/<code>.md`, one for each of the eleven
languages: a guided tour, in English, of everything a document can hold —
boxes, headings, target-language runs and blocks, readings and colours, lemma
headings, tables, footnotes, links by name, formulas, two pictures, a
recording, a video, and one exercise of every kind — with every example in
that language, written with the marks it uses (a Persian or a Japanese run
recognised by its script, a Latin-script one marked by hand, a Persian
couplet in nastaliq, Japanese and Chinese set vertically). Keep what you
need and delete the rest. The button carries the toolbox's language
preference; a language added later gets, until somebody writes its starter,
a short generic skeleton built from its registry row. The prose language of
all of them is English — change the `lang:` line and the hyphenation follows,
which is the whole of what the prose language decides here. The two pictures
and the chime a starter shows ship beside it and become the document's own
when it is saved (**The starters' pictures and recording**, below).
Deleting asks for confirmation and removes the whole folder.

### Reading view (`/doc/<id>`)

The dialect rendered as HTML mirroring `template.tex`: same colours,
numbered sections, lemma headers with rules and the target text huge in
its font, tinted boxes, booktabs tables, description/`lex` lists, display
lines, grey gloss `=`, the linguistics `✗`. The sheet carries
`data-lang="<code>"`, from which the stylesheet takes the font and the
direction (the tokens come from the generated `langs.css`). RTL correctness
is delegated to the browser's Unicode bidi algorithm — each RTL run is an
isolated `dir="rtl"` span, the web twin of `\pe`/`\pel`; a Japanese run is
an LTR span in the CJK font, and a vertical block is a `writing-mode:
vertical-rl` box.

**Interactive typography**, persisted per document, in the page's **⚙ page** panel
(`static/gear.js`, on the toolbox's `lib/pagesettings.js`; **Aa** in the toolbar opens it
at its **Text** group):

* **the target size** — the slider is named for the language (**Persian text size**,
  **Japanese text size**…) and scales the target text *independently* of
  the Latin (the same knob as fontspec's `Scale`; the PDF build uses the
  current slider value as `--scale`);
* **Latin text size**, **Line spacing**, **Headword size** (the lemma header);
* **Text width** (420–1400 px) — by default it follows the Latin size
  proportionally, so the two sliders move together; dragging the width
  yourself never moves the Latin slider and simply rebases the ratio;
* **Justify the text** (hyphenation); **Put the text back to normal**; print view in the
  toolbar. The sheet has no theme menu of its own: it follows the toolbox's colours (◐, or
  **Colours** in the panel); the exercises' two switches, **Hide transliterations** and
  **Drag to answer**, are in the panel's **Exercises** group.

The sheet is always centred. **☰ Contents** opens the table of contents
as a drawer floating over the page, closing on Esc, on the backdrop, or
as soon as you jump to a heading (the jump offset is measured from the
toolbar's real height, which changes as it rewraps). Clicking any
phrase of the target language copies it.

**↩ Linked from (N)**, beside them, opens the same kind of drawer from the
other side: every document of the same library whose text links to this
one (by its name, or by the uid of a link written before names), each a
link to it, with the words around each of its links and the link itself
marked — a Persian line read right to left, an English one left to right.
A document nothing links to says "No document links here yet." It stays on
a phone's toolbar with Contents and Glosses, closes on Esc or on the
backdrop, and on a note beside a book or a video it lists the notes of that
book or video.

**⌃ hide bars**, in the toolbar (and **Hide the bars** in the panel's **Page** group),
takes all three bars away — the
topbar, the tags and the toolbar — and leaves one faint **⌄ show bars** in the
corner to bring them back, so a page that is set the way you want it gives
the whole window to its text. The choice is remembered for every document,
since it is a way of reading rather than a property of a page; a phone's own
hiding (the bars go as the page moves down and come back on the smallest
move up) is untouched.

### Glosses overlay

**⇄ Glosses**, directly under Contents, opens a centred overlay built
from the document itself — every `فارسی = *translation*` in it, with
nothing to keep in sync by hand.

**Table** — three columns: the target word, transliteration, translation —
and for a reading language a fourth, the **reading**, between the word and
the transliteration. The harvester reads paragraphs, headings, bulleted-list items, table cells, blockquotes, `{la}` blocks and both footnote forms; a numbered list is not mined, and `[…]{tl}` blocks stay opaque and are never mined. A head may be a bare run of the
target script (or a marked run, for a Latin-script target), a
`{translit:…}`, `{kana:…}` or colour mark, several combined, or
`**bold**`-wrapped. A missing transliteration or reading is backfilled from
any other mark or lemma heading for the same word.
Identical entries collapse; a word carrying two genuinely different
senses keeps both. **Lemmas only** narrows both the table and the
flashcards to the words that head a lemma entry, turning the glossary
into the document's word list rather than everything it glosses in
passing; the button appears only when the document has such lemmas. A
filter box matches all three columns. A row whose
gloss was written without italics is shown in red, with a hover cloud
explaining that only its first word could be read as the translation;
the flashcards mark the same entries.

**Sorting** — every column header sorts, cycling **A→Z → Z→A → back to
the order they appear in the text**, which is the default. The target
column collates in its own language rather than by code points; the
transliteration ignores macrons and case, so `āheste` files next to
`ajale`; the translation follows the document's own language. Entries with
no transliteration sink to the bottom either way instead of heading a
column of blanks, and a column nothing fills is simply not sortable.

**Flashcards** — the same glosses as a drill: a word of the target
language, click the card (or press space) to reveal reading,
transliteration and translation, `Next`
(or `→`/Enter) to move on. It deals a shuffled deck rather than picking
independently at random, so every gloss comes up once before any
repeats, with a counter; the deck reshuffles on wrap.

### Colour by selection; linguistic annotation by hover

**Colour marks.** In the source editor, select exactly the letters or words
to colour and use the split **colour** control. Its main button applies the
active colour; its palette chooses a named hue, custom hex, or no colour.
A partial word is stored as a semantic segmented run, for example
`[[ک[ت]{crimson}[ا]{indigo}ب]]{translit:ketāb}`. It renders and behaves as
one target-language word whose flattened value is `کتاب`. The reading view
and preview cloud construct no colour controls.

**Transliteration.** A word — or a short 2–3 word group — can carry
`[تند]{translit:tond}`, invisible in both outputs but shown in the hover
overlay, and used by the glossary. In a Japanese
document the same mark carries the reading too, `{kana:かんじ
translit:kanji}`, and the overlay shows the kana above the rōmaji.

It is **editable in place**: the transliteration at the head of the
cloud is a button — click it and it becomes a text field, prefilled;
Enter saves, Esc cancels, clicking away saves. A run that has none yet
shows a **+** instead, which opens the same empty field. Saving an
empty field removes the annotation, and if that was the run's only mark
the brackets go too, leaving the bare word. Lemma headings already carry
their transliteration in the heading itself (`## فارسی | translit | …`),
where it is visible beside the headword, so they do not open an empty cloud
with a second, competing copy.

Colour and transliteration share one ordinary mark (`{teal
translit:tond}`); a segmented run keeps linguistic marks on its outer
wrapper. Selection colouring preserves those fields, and a cloud edit
preserves every inner colour piece. Each source selection command is one
editor history transaction, undoable with ⌘Z like any other edit.

**Which copy is edited.** A word that appears several times is named by its
text and its place among the words with that text, and the server finds that
place in the source. Both sides count in the order the source is written —
also inside an exercise, which the page draws in an order of its own (the
rows before the explanations whatever order the fields come in, every left
side of a matching exercise before the bank of right ones, a solved fill-in
with its answers in the sentence, a reversed card back first). What the page
offers no editor is counted by neither: a footnote's text, whether written
as a definition (its indented lines included, and inside a box) or inline
with a mark inside it; a card's field drawn as blocks; a form struck with ✗;
a formula; a front-matter key other than the title, subtitle and note, and a
`#` heading the title drops; and the parts of an exercise the page does not
draw — a comment, a field no exercise reads, and the rows of one that shows
its errors instead. A word wrapped over two lines of a paragraph or of a
list item is one word, and a mark written round it keeps the line break. A
piece of a fill-in sentence that holds blanks, `[Gestern [[aux]] ich
…]{tl}`, is a word of its own for a Latin-script target; colouring it writes
the sentence out as the pieces the page draws, `[Gestern]{teal} [[aux]] [ich
…]{tl}`. A target block (below) is named the same way, by its text and its
place among the blocks with that text, and counted the same way.

**Target-language blocks.** The *block* button wraps the **current
selection** in `[…]{tl}` — multiline form when the selection spans lines.
The **✎ target-text editor** (what used to be "✎ RTL") opens an overlay
with a text box in the document's direction and font, for comfortable
typing in the target language; each line of the box becomes a real line
(`⏎`). Hovering any rendered target block offers a **✎** button that
reopens it in the same overlay; saving writes back into the unsaved
buffer, undoable with one ⌘Z/Ctrl+Z. An automatic paragraph stays plain
markdown while it remains Latin-free, and is wrapped as `[…]{tl}` the
moment a Latin word is added.

The overlay carries optional controls, stored on the marker and defaulting
to the plain block when empty, and offered only when the language has
them. *Font* appears when the language has an alternate face — *Nastaliq*
(`{tl font=nastaliq}`) for Persian, typeset in Noto Nastaliq Urdu
(provisioned automatically: the variable font is fetched from Google Fonts
once, instanced to a static TTF for XeLaTeX and compressed to woff2 for the
web; without it, the PDF falls back to Vazirmatn); *Gothic*
(`{tl font=gothic}`) for Japanese, Noto Sans CJK JP. *Vertical* is a
checkbox offered for languages that can be set vertically (Japanese):
`{tl vertical}`, with the column height in `height=`. *Background*
(`{tl bg=quote}`, also `sand`, `rose`, `sage`, `lilac`) tints the block,
with dark-theme variants on the web and the same light tints as
`\colorbox` fills in the PDF.

**Latin blocks** — the mirror of `{tl}` for ordinary text: `[testo]{la}`,
recognised when the whole paragraph is the block. Unlike `{tl}` the
content stays real markdown — glosses, target runs, links, footnotes all
work inside. Clicking the block opens the same panel images have: width
and sideways shift (percentages of the column), text alignment, and a
background tint.

**Images** — uploaded by you, never by the LLM. The *Image* button,
**pasting a figure straight from the clipboard**, or dragging a PNG,
JPEG, SVG or PDF onto the source pane, stores the file under
`library/<language>/<id>/images/` and inserts `![didascalia](images/<name>)` with
the caption preselected; *Images…* lists the folder with thumbnails.

A PDF figure is shown as vector, in an ordinary `<img>` — never a
rastered page and never an embedded PDF reader — so it stays crisp at
any width the layout gives it. Only the first page is used.

A pasted figure has bytes but no name of its own — a screenshot is
`image.png` at best — so pasting one opens a box asking what to call it,
with an optional caption, and drops the embed back exactly where the
cursor was. Only the stem matters: the server sniffs the bytes and gives
the file the extension that actually matches them. A paste that is not a
figure is left to the browser untouched, and SVG that arrives as markup
rather than as a file is offered the same way — cancel, and the markup
is pasted as text instead of being swallowed.
**Click an image** to open its layout panel: width (10–100 %), alignment
and horizontal shift, all written into the embed's attribute block.
Uploads are validated by magic bytes, name collisions get a suffix,
identical re-uploads are deduplicated, and *Duplicate* copies the images
and audio folders along with the source.

**Recordings** — uploaded by you too. The *Audio* button (several files at
once) or dragging recordings onto the source pane — pictures and recordings
may be dropped together, and go in in the order dropped — stores each under
`library/<language>/<id>/audio/` and inserts `![didascalia](audio/<name>)` on
a line of its own, the caption preselected. The server reads the bytes, as
it does a picture's: the extension follows them, a name already taken by a
different file gets `-2`, the same file uploaded twice is stored once, and
anything that is not a recording, or is larger than 30 MB, is refused with
the reason. A file dropped anywhere else on the edit page is ignored rather
than opened in place of the editor. *Recordings…* lists the document's own
recordings — ▶ plays one, a click puts it in at the cursor, *in use* marks
the ones the editor's text names at that moment, and ✕ deletes the file
(asking first) — and, when the studio is served by the hub, **Clips cut from
books and videos**: the recordings of the toolbox's clip tray
([`../clips/README.md`](../clips/README.md)) in the document's language, each
with ▶ and **Add**, which puts its line in at the cursor, captioned with the
clip's words, and copies the file into the document at once. The section is
not shown when the tray has none, nor when the studio runs on its own.

**Brought in from the clip tray.** A card made in a book or a video and
copied as markdown names its recording and its frame by their tray names
(`audio/wind-47de68.mp3`). Pasted into the editor of a saved document, every
such name the document does not have is copied in from the tray at once —
*Brought 1 file from the clip tray* — and the preview plays it; each save
does the same for the whole text (`POST /api/docs/<id>/adopt`,
`store.adopt_media`), so a new document takes them in when it is first
saved. The tray keeps its copy. A name neither the document nor the tray
holds stays as written, and plays nothing.

**The starters' pictures and recording.** A starter shows a picture and a
recording where the dialect puts one — on a line of their own, on a card,
with an exercise — and names files that ship beside the starters, in
`exlex/starters/assets/`: `images/starter-apple.svg`,
`images/starter-house.svg` and `audio/starter-chime.mp3`. Every save copies
each of them the text names and the document has never held into the
document's own `images/` or `audio/` (`store.adopt_starter_media`), as a
clip comes in from the tray, so a new document takes them in when it is
first saved and an older one when it first names one; an upload does the
same, a `.md` or a zip that leaves them out. From then on it is the
document's file like any other: listed by *Images…* and *Recordings…*,
taken away in its zip and its backup, a picture printed in its PDF, and a
file of the document's own under the same name is never replaced.
**Deleted there with ✕, it stays deleted**: the document's `meta.json` lists
the starter's files it has held (`starter_media`), and no save copies one
of those in again — while the text names it, the editor and the reading
view show it missing and the PDF build stops on it by name, as they would
on any file the document lacks. Nothing is replaced in place, since a
different file uploaded under a name already taken gets `-2`: to show a
picture or a recording of your own instead, upload it and let the line
name it, or delete the starter's first and upload yours under its name.
*Duplicate* and a backup keep the list; a document made from a zip or a
`.md` starts its own, and so takes in afresh the starter's files the zip
leaves out. A note beside a book or a video does the same.
Until a save has copied one in, the editor's preview shows it from where
the starters keep it (`GET /starter-media/…`); in a document not saved yet,
a picture of its own stays a placeholder, having no folder to live in yet.

**Playing a clip.** A recording laid out with `start` and/or `end` plays
that stretch and no more: started from outside it, it jumps to its start,
and it pauses at its end — on a timer that looks again as the end nears,
since `timeupdate` arrives four times a second at best, which is a
syllable. This holds on every page that shows a document: the reading view,
the editor's preview, a note beside a book or a video. Among flashcards only
one recording plays at a time. **A recording's ⚙ layout** handle, shown
on hover at the figure's lower right (under the player, or under its
caption where it has one), or a click on its caption,
opens the image layout panel as *Recording layout*, with a *Clip* row whose start and end take
seconds or `m:ss` with hundredths (`65.5`, `1:05.25`); empty means from the
beginning, or to the end. A recording on a flashcard has no handle.

**YouTube embeds** — the *Video* button inserts
`@[didascalia](youtube-url)`. By default the whole video is embedded;
hovering the player shows a ⚙ handle opening the same layout panel plus
two optional *clip* fields (seconds or `m:ss`). YouTube honours
start/end only on the first play of a loaded iframe, so clipped embeds
enable the player's JS API and the page reloads the iframe whenever the
player reports *ended* — every replay is the same snippet. The PDF
renders a clickable play-card opening the clip at its start time.

All of these panels work in the editor's live preview too, where they
rewrite the unsaved buffer (undoable) instead of the stored file.

### Editor (`/doc/<id>/edit`, `/new`)

Split source/preview with debounced server-side rendering — the same
renderer as the reading view, so the preview *is* the document. Insert
buttons for ZWNJ / `→` / `✗` / `✅` / `«»` / gloss `=` / `⏎` / the target
block / the Latin block / image / recording / video / doc link, ⌘S to save,
unsaved-changes guard. Pictures and recordings live in the document's own
folder, so their buttons ask for the document to be saved first.

**note** opens a box for the note's name and its text, then does the two
things a footnote needs: the reference `[^id]` goes in at the cursor, and
the note itself is placed among the existing definitions **in the order
the reader meets them** — so the block at the foot of the document reads
in the same order as the page. The name is optional (`n1`, `n2`, … when
left empty) and a name already in use is refused rather than silently
merged.

Starting a document from an outside source — *Paste LLM answer*, *Load
.md* — lives on the library page, not here: inside the editor both
replaced everything already typed.

**Aligned panes** — the renderer tags every top-level block with the
source line it starts on, and the editor keeps the panes lined up
against those anchors. Since a textarea has a single interline, its
line-height and top padding are least-squares fitted over *all* the
anchors (when the fit wants a negative padding the preview container is
shifted down instead — its typography is never touched), and the same
anchors act as piecewise correction points for synchronised scrolling.
Everything refits on every render and on resize.

**History** — dedicated ↺/↻ buttons plus the native shortcuts of all
three platforms: ⌘Z / ⇧⌘Z, Ctrl+Z / Ctrl+Shift+Z, Ctrl+Z / Ctrl+Y. The
stack is the editor's own, so programmatic edits are undoable too;
rapid typing collapses into single steps.

**Editor** — **⇤ RTL editor** writes the whole source right to left, and
**⇥ LTR editor** turns it back: for a document whose prose is written
right to left — a Persian writing to teach English to Persians, whose
full stops, question marks and heading marks a left-to-right box puts at
the wrong end of every line. The button always says what a click does,
its tooltip which way the source goes now. Right to left, the source is
set from the right, in the face of the right-to-left language it is
written in — the prose language's when the registry has one (Vazirmatn
for Persian, Noto Naskh Arabic for Arabic), else the target's — and a
step larger, every line of it right to left: the prose, and a key whose
value is a Persian sentence (`prompt:`, `meaning:`, an answer `- [x] …`)
with its key on the right and its full stop on the left, where the
sentence ends. A line of Latin letters alone — a `:::exercise` fence, an
English `context:` — reads the way any right-to-left editor draws it, its
`:::` on the right and an English full stop on the left. Left to right it
keeps the monospace.
Only the source box changes: the preview is drawn as before, the
exercise form's own ⇤ RTL / ⇥ LTR buttons are their own, and the panes
stay lined up (the hidden copy that counts the wrapped rows takes the
same direction and face). Until the button is pressed, the source goes
the way the prose language of `lang:` is written — right to left for
`lang: fa` or `lang: ar`, and it follows a `lang:` typed into the front
matter; once pressed, the choice is the document's, remembered in this
browser under `parseh_editor_dir:<id>`. A new document, which has no id
yet, keeps it with the page it is written in (its entry in the browser's
history, so a reload keeps it) and takes it as its own when it is first
saved; the next new document starts again from its own `lang:`.

### PDF

*Build PDF* runs parse → texgen → `xelatex` ×2 → the glyph-level
verification, all server-side, and reports how many target strings were
found correct, page count and overfull boxes in the toolbar (failures
listed inline). The verifier reads a marker comment the generator writes
into the `.tex` (`% exlex-target: ja ltr`) and checks an RTL document as
it always did — every run found reversed in the visual order — and an LTR
document in forward order; vertical blocks are excluded like `{tl}` blocks
always were. *View PDF* swaps the sheet for the browser's viewer; Download
offers `.md`, `.tex`, `.pdf`. Editing a built document flags the build as
**stale** until rebuilt.

**PDF options ▾**, beside *Build PDF*, says how the next build prints the
document — options of the build, not of the markdown, so one worksheet
prints both ways:

* **Print size** — Normal (11 pt), Large (14 pt), Extra large (17 pt),
  Maximum (20 pt), for readers with low vision. The larger sizes set the
  document in `extarticle` (TeX Live's `extsizes`, which `install.sh --pdf`
  installs; a TeX without it stops with a message that names it), so the
  headings, the target script's `Scale` and every `em` grow with the text;
  the lemma head, the one absolute size, is scaled by hand, the margins give
  a little, and the rules — a fill blank, a frame, a writing line — get
  heavier. The column beside a lemma's headword (its reading,
  transliteration and meaning) is fitted as the exercises' columns are: a
  one-word IPA wider than it is scaled to it, as the headword is, rather
  than run off the paper's edge. An **exercise is set a step larger still** (`\large` on the new
  base). One taller than a page, which at 20 pt a reading passage and
  its questions can be (and ten framed pictures to match are at any size,
  11 pt included), starts a page and goes on over as many as it needs,
  a frame on each, instead of being cut off at the foot of one. A table wider
  than the line is scaled down to it, and a vertical block's column is never
  longer than the page. A word that fits a matching frame or a
  true/false statement's column at 11 pt can be twice as wide as it at 20:
  see *Exercises in columns* under the design notes.
* **Black and white** — no colour and no grey anywhere, pictures excepted,
  for the photocopier: every ink of the template is redefined black and
  every tint white, a tinted panel (a box, a `{tl bg=…}` block, an
  exercise, a recording's card) becomes a white one in a thin black frame,
  and nothing is written inline in a colour — not a `{teal}` or `{#…}` mark,
  not a coloured lemma, not the red of an exercise that needs attention.
  xcolor's gray model was not used: it turns the tints and the dim text into
  the greys a copier smudges.

The choice is kept per document in the browser (`exlex-pdf:<id>`, beside
the typography's `exlex-typo:<id>`); a browser that has chosen nothing
starts from what the PDF on disk was built with. The build badge says what
that was (`PDF ✓ 7 pages · scale 1.52 · 17 pt · B&W`), and when the menu
says otherwise a badge of its own appears, **built with other options —
rebuild**, with both sets on hover. The command line takes the same two,
`--size 11|14|17|20` and `--mono`, and writes the same `.tex`.

### Prompt page (`/prompt`)

The prompt made from `exlex/PROMPT.md` plus a question box; one button
copies prompt + question for the LLM, which answers with a `.md` file you
then upload, or, where it cannot make a file, with the whole document in one
fenced block that **Paste LLM answer** takes the document out of. The
prompt can be edited and saved as a custom override (`library/_prompt.md`)
and reset to the default.

**The prompt is in parts a person ticks.** `exlex/PROMPT.md` holds every
rule the prompt can teach, each feature in a section marked
`{{?id}}…{{/id}}` (a "box": vocabulary entries, glosses, transliteration,
reading marks, the language's own punctuation, right-to-left sequences,
passages, Latin blocks, wrong and right forms, lists, tables, boxes, bold
and italic, footnotes, links, colours, colour inside a word, formulas, LaTeX
drawings, exercises, and keeping what a pasted document has), and the copy has only the ones
ticked (`app/promptboxes.py`: the boxes, the presets — a short answer, **a
lesson** (the default), a vocabulary study, a lesson with exercises, all,
none — level and length, and what each box costs, measured). A box a
language cannot use is hidden (a reading only for Japanese, its own
punctuation only for a language with a script of its own, the box order of
mixed directions only for right-to-left targets). Whatever is ticked, the
copy carries an always-in part — the task, the front matter, the structure,
how the target language is written, **one paragraph on one line**, and that
the model never writes a picture, a recording, a video or a link to another
document — and a **reserved list**: every mark the studio reads, with what
it does, so that a feature that was not ticked is forbidden by name and the
model writes it only when it was taught. The answer contract comes last
(the file, or the fence), then the learner's level and the length asked
for, one line each. The routes are `GET /api/prompt?target=&boxes=&level=&length=`
and, for the editor's **Generate with LLM…**, `POST /api/exercise-prompt`,
which builds its dialect from the same boxes (ticked from what the page
already uses) and its exercises from one box per type. The page and the
dialog draw the boxes, the presets and the sizes from those answers, and
nothing else (`static/promptpick.js`: no list of boxes lives in the
browser, so one the server gains is drawn the day it exists).

The prompt is written in **no particular prose language** — it tells the
model to answer in the language of the question, and its own rules and
examples avoid naming one. The **target language** is chosen on the page:
a select above the boxes; the copied prompt states the target,
asks for the matching `target:` line, and includes that language's own
conventions block (`../docs/lang/<code>.md`) so the transliteration scheme
— and, for Japanese, the kana rule — reach the model. A prompt for a
Latin-script target says that every run of it must be marked `[…]{tl}`
and that a plain section title then cannot contain `|`. It also states
plainly that the features are **tools, not tasks**: most documents need no
colour at all, nothing may be used merely to demonstrate it, and the
document must never describe its own markup, colour scheme or format.

### Exercise decks (`/exercises/`)

A document's `:::exercise` blocks
([`../docs/studio-exercises.md`](../docs/studio-exercises.md)) can be
gathered into **decks** and studied like Anki cards, on pages of their own
at `/exercises/`, which is a door of the hub. Both servers mount them at that
address: `../serve.py`, and `app/server.py` when the studio runs alone. On a
document's reading view every exercise, boxed ones included, has a
**+ Deck** button. It copies that exercise exactly as written, with the
footnotes it refers to and every picture and recording it names, into a
deck of the document's target language (or a new one). A deck's page adds
exercises with **Add exercise…**, the editor's own form, and lists them to
edit, duplicate or delete. Studying rates each exercise Again / Hard / Good /
Easy and schedules it as Anki does, and plays a flashcard's recording as the
card is shown and turned. A note beside a book or a video has
**+ Deck** too, since `../serve.py` tells the decks which notes its address
stands for; the editor's preview has none. A flashcard's picture and
recording fields upload the file into the deck. The editor's
**Exercises ▾ → Load from a deck…** is the way back: an exercise of a deck of
the page's language goes in at the cursor, its pictures and recordings copied
into this document's `images/` and `audio/` (renamed there where a different
file has the name, with the block rewritten to match) and the footnotes it
calls placed among the document's own, renamed round any of the same name. The book reader and the
video player add cards to a deck as well (`lib/cardkit.js`, with the
`origin` the deck's page links back by), and a card naming a clip-tray file
the deck lacks brings it in as it is added.

The pages are `app/deckroutes.py`, the store is `app/decks.py`
(`../exercises/<language>/<slug>/`, git-ignored except its README) and the
scheduler is `app/srs.py`. How it works from the learner's side, the
scheduler's defaults and the export format are in
[`../docs/studio-exercises.md`](../docs/studio-exercises.md).

## API (all JSON, all local)

```
GET    /api/docs?q=&tags=a,b&exclude_tags=c,d&intext=1&sort=updated
POST   /api/docs                     {markdown, tags?}   (fence auto-extracted)
GET    /api/docs/<id>                PUT /api/docs/<id>  {markdown}
PATCH  /api/docs/<id>/meta           {tags?, title?...}
POST   /api/docs/<id>/duplicate      DELETE /api/docs/<id>
POST   /api/docs/<id>/build          {scale?, size?: 11|14|17|20, mono?: bool}   (else 400)
POST   /api/docs/<id>/color          {text, occurrence, color|null}
POST   /api/docs/<id>/translit       {text, occurrence, translit|null}
POST   /api/docs/<id>/kana           {text, occurrence, kana|null}   (reading languages only)
GET/POST /api/docs/<id>/images       list · upload (raw body, ?name=)
DELETE /api/docs/<id>/images/<name>  · GET /media/<id>/images/<name>
GET    /api/docs/<id>/audio          {audio: [{name, size, referenced}]}
POST   /api/docs/<id>/audio?name=    a recording as the raw body → 201 {name, path, url}
DELETE /api/docs/<id>/audio/<name>   · GET /media/<id>/audio/<name>   (Range-aware)
POST   /api/docs/<id>/adopt          {markdown?} → {adopted: [paths], missing: [paths]}
GET    /starter-media/(images|audio)/<name>   a starter's picture or recording, read-only
POST   /api/docs/<id>/image-layout   {index, width, align, offset, start?, end?}
POST   /api/docs/<id>/la-layout      {content, occurrence, width, offset, align, bg}
POST   /api/preview                  {markdown, doc_id?} → rendered html + toc + stats, the
                                     target's record and the prose language's (`prose`: its dir)
POST   /api/recolor                  {markdown, text, occurrence, color} → new markdown
POST   /api/tl-edit                  {markdown, kind, content, occurrence, lines} → new markdown
                                     (/api/rtl-edit is the old name, still served)
POST   /api/translit · /api/kana     same as above, on an unsaved buffer (pure)
POST   /api/image-layout · /api/la-layout    same, on an unsaved buffer (pure)
GET    /api/tags · /api/palette · /api/status · /api/export (zip)
POST   /api/download                 ids=a,b (a form) or {ids: [...]} → zip of those .md sources
GET    /api/exercise-decks[?target=] the Anki decks the LLM exercise prompt may take words from
                                     (only the language's own, with ?target=<code>)
POST   /api/exercise-prompt          {markdown, decks?, boxes?, types?, level?, length?} →
                                     {prompt, vocabulary, boxes, types, preticked, size}
GET    /api/prompt[?target=&boxes=&level=&length=]  → {prompt, size, boxes, presets, levels, lengths, …}
PUT/DELETE /api/prompt               the one custom prompt (library/_prompt.md), kept as it was
POST   /api/shutdown
```

The `/api/recolor`, `/api/tl-edit`, `/api/translit`, `/api/kana` and the
two pure layout endpoints take and return markdown with no disk I/O,
which is what lets the editor apply the same rewrites to an unsaved
buffer that the reading view applies to a stored file. `/api/tl-edit`
is the endpoint of the target-text editor, the **✎ <language>** box
that writes a `[ … ]{tl}` block (Persian-only before languages, it was
called the rtl editor then, hence `/api/rtl-edit`, which still answers
as its alias); it has nothing to do with the **⇤ RTL editor** button,
which only turns the direction of the source.
`/api/exercise-decks` and `/api/exercise-prompt` serve the editor's
**Exercises ▾ → Generate with LLM…**, and their "decks" are Anki card decks,
not the exercise decks below.

The exercise decks answer under `/exercises` (`app/deckroutes.py`; the paths
below follow that prefix). Every JSON answer carries `"ok"`; a 409 also
carries `"conflict"`: `exists`, `duplicate`, `stale`, `reviewed` (an
answer to an exercise that has been answered since it was shown) or
`linked` (the exercise is one side of a linked pair -- a `both-repeat`
flashcard is two exercises in a deck -- and what was asked would leave the
other side as it was: send `linked: "both"` or `"alone"`; `detail.mates`
names the other sides).

```
GET    /api/decks?lang=                          POST /api/decks  {name, lang}
GET    /api/decks/<folder>/<slug>                the deck and its exercises
PATCH  /api/decks/<folder>/<slug>                {name?, settings?}
DELETE /api/decks/<folder>/<slug>                (moved to exercises/.trash/)
POST   /api/decks/<folder>/<slug>/items          {markdown, force?, origin?} → {item, items, warnings}
                                                 (origin: a card made in a book or a video --
                                                 book, video, label, time, url, title; `items`
                                                 holds both cards of a both-repeat flashcard)
GET    /api/decks/<folder>/<slug>/items/<id>     the exercise and its solved html
PUT    /api/decks/<folder>/<slug>/items/<id>     {markdown, linked?} → {item, warnings}
DELETE /api/decks/<folder>/<slug>/items/<id>?linked=both|alone
POST   /api/decks/<folder>/<slug>/items/bulk     {action: delete|set-new|add-tag|remove-tag|copy|move,
                                                 ids, tag?, target?, linked?}   (linked: for delete)
POST   /api/decks/<folder>/<slug>/items/<id>/duplicate
POST   /api/decks/<folder>/<slug>/items/<id>/to-doc  {doc_id, source?}
                                     the other direction: the exercise as markdown for a
                                     studio document, its pictures and recordings copied
                                     into that document's own images/ and audio/ first
                                     → {markdown, footnotes, warnings}
POST   /api/decks/<folder>/<slug>/images?name=   a picture as the raw body → {name, path, url}
POST   /api/decks/<folder>/<slug>/audio?name=    a recording as the raw body → 201 {name, path, url}
POST   /api/decks/<folder>/<slug>/copy           {doc_id, ordinal, subtype, updated, force?, source?}
                                                 → {item, items, warnings, deck}
                                                 (source: a note's mount, /books/…/notes)
POST   /api/decks/<folder>/<slug>/preview        {markdown, item?} → solved html
GET    /api/decks/<folder>/<slug>/next?skip=a,b  the exercise to study now and its four intervals
                                                 (`buried`: how many cards wait for the next day
                                                 because their other side was answered today)
POST   /api/decks/<folder>/<slug>/review         {item, rating, result, reps?, skip?} → the next one
                                                 (next is null when it cannot be built)
GET    /api/decks/<folder>/<slug>/export?scheduling=1|0      zip
POST   /api/import?scheduling=1|0&mode=new|replace|copy      the zip as the raw body
GET    /media/<folder>/<slug>/images/<name>      a deck's picture
GET    /media/<folder>/<slug>/audio/<name>       a deck's recording (Range-aware)
POST   /api/shutdown
```

**Range.** Every file the two servers send that is not a download answers a
single `Range: bytes=a-b`, `bytes=a-` or `bytes=-n` with `206` and
`Content-Range` (`416` when nothing of the file is in it; of a list of
ranges the first is answered; a header that is not a byte range is ignored
and the whole file sent). A media element asks `bytes=0-` and then
`bytes=<n>-` for every seek, so without this a recording could not be sought
in. `byte_range` is written the same in `app/server.py` and `../serve.py`,
and `tests/test_studio_audio.py` holds the two together. A download
(`/download/<id>/md` and the like) is always sent whole.

The clip tray is the hub's, not the studio's: `../serve.py` answers it under
`/clips/` (`/clips/api/status`, `list`, `upload`, `preview`, `DELETE
/clips/api/<name>`, `/clips/media/<name>`), and the cuts under a book reader's
`__clip/cut` and `__clip/peaks` and the player's `/youtube/api/clip` and
`/youtube/api/peaks` (a film on the machine). A YouTube video has no file
to cut: `../lib/cardkit.js` records the tab while the stretch plays (Chrome
and Edge, over https), cuts the clip out of that recording in the browser,
and sends it to `upload` as a WAV, which the tray re-encodes where there
is ffmpeg (`audiofile.best_output`, MP3 when it can). `../clips/README.md` says what the tray holds.

---

## Pipeline

`build` = envsetup → parse → generate `main.tex` from `template.tex` →
`xelatex` ×2 (`-halt-on-error`) → copy `⟨stem⟩.pdf` → verify. The `.tex`
is a build artifact: fix the `.md` or the generator, never the `.tex`.

## Design notes — read before refactoring

**Why XeLaTeX, and why raw TeXXeT primitives.** In the target
environment LuaLaTeX is unusable for this (no `luaotfload`, so fontspec
cannot load OpenType fonts at all; no `luatexbase`, so babel's
`bidi=basic` aborts) and `bidi.sty` is absent, which rules out
polyglossia's RTL support. What remains — and is fully sufficient — is
XeLaTeX with e-TeX's TeXXeT: `\TeXXeTstate=1` plus `\beginR…\endR`
around every Persian run.

**The double-reversal trap (the core lesson).** XeTeX's HarfBuzz shaper
already reverses the *letters* within each shaped word; TeX then places
the *words* left-to-right. So:

* no `\beginR` → letters correct, word order LTR — the classic bug;
* `\beginR` → correct;
* `\beginR` *plus* any additional reversal layer → words back to LTR.

When testing this, do **not** trust your eyes on symmetric-looking
words: use numbered words (`یک دو سه چهار` = 1 2 3 4) and check whether
the visual order is 4-3-2-1. During development the low-resolution
render was misread *twice*; only glyph-coordinate extraction settled it.
That is why `verify.py` exists and why `build` runs it by default.

**`\pe` is an `\mbox` on purpose.** The box isolates the run: adjacent
runs separated by commas keep source order, punctuation stays on the
Latin side, and nothing interacts across the boundary. The cost is no
line-breaking, hence the `\pel` variant (plain group, still inside
`\beginR…\endR`) for long runs. Keep `\tolerance`/`\emergencystretch`
raised: unbreakable boxes make paragraphs harder to justify (large print
raises `\emergencystretch` to 3em, since its short lines have fewer spaces
to stretch). A fill-in blank in a language written without spaces
(Chinese, Japanese) has an `\allowbreak` on each side it touches a
character: a sentence of short `\pe` runs and blanks had no place to end a
line at all. But not beside a character that may not begin a line after it
(。，、？ ）」, the small kana, ー, 々) or end one before it (（「, a currency
sign): the `\allowbreak` overrode XeTeX's own line breaking, which keeps
that rule (kinsoku), and set a "？" alone at the head of a line at every
size. `texgen._beside` finds that character past the LaTeX the sentence
is already in (`\pe{？}`, `\textbf{…}`).

**Colour inside a right-to-left segment.** XeTeX reverses an R segment
when it ships it out, and it reverses what the boxes in that segment hold
as well: a Latin word boxed inside comes out backwards, and a colour —
pushed before a box and popped after it — is popped before it is pushed,
which paints a framed box solid. Something coloured or framed that must
sit in an R segment (the framed chunks of a construct-the-sentence row
flowing right to left) is therefore shut in a `\beginL…\endL` of its own
inside its box; a right-to-left text in it carries its own `\beginR`,
and the innermost segment is what it is set by.

**Exercises in columns.** A matching entry sits in its frame, a
true/false statement in the column beside its marks, and a chunk too long
for a construct-the-sentence row in a frame as wide as the line: each is a
paragraph of a fixed width that nothing may cross. `\exlexfitpar` sets it.
The paragraph gets every break it can take: its target runs are all
`\pel` (in a cell, and only there, a short run is not the one box of a
`\pe`), an `\hspace{0pt}` in front lets TeX hyphenate its first word (TeX
hyphenates only a word that follows glue), and a line may end after a
slash (an intercharacter class of `/`, switched on only inside these
paragraphs). The paragraph is set once with the complaint silenced, and
its lines are read back with `\lastbox`, each packed again to its width
so that `\badness` says whether it was overfull. If one was, the paragraph
is set again as wide as its widest line and scaled down to the column:
smaller, but inside. A German compound in a 20 pt frame is hyphenated at
20 pt; a long number is scaled. A paragraph given to `\exlexfitpar` must
close any colour it opens in a group of its own: a colour reset after its
last line would hide the lines from `\lastbox`, and it would be left as
set. In large print the macro is in `%%PRINTOPTIONS%%`, before the
template's `\voce`, whose three lines beside the headword it fits there:
the template marks them `%%VOCEFIT%%`, which is nothing at 11 pt and
`\exlexfitvoce` in large print, where a first word is not hyphenated (a
hyphen inside a transcription reads as part of it). Otherwise it comes
with the exercises' own macros (`%%EXERCISEPAPER%%`).

**Two renderers, one block model.** `texgen.py` and `app/htmlgen.py`
consume the same block model and must agree. Shared numeric helpers
(`image_indent`, `fmt_time`, the palette and tint tables) live in
`texgen.py` and are imported by `htmlgen.py` so a figure lands in the
same place on screen and on paper. Any change to one renderer needs the
matching change in the other, and the fidelity checks compare their
output block for block.

**One language at a time, held like the footnote state.** Both renderers
take the target from the parsed front matter and hold it in the same
thread-local the footnote counters use, set at the top of each render;
the old module constants for the Persian character class are gone, and
neither file writes a regex for any script — the registry's `run_re` is
the only one. `template.tex` has its target-font block, its direction
macros (`\pe`/`\pel`/`\peb` wrap in `\beginR…\endR` only for an RTL
target) and its vertical macro filled per language by `texgen.generate`:
the target face is `\tlfont` (`\vaz` kept as an alias) with
`\IfFontExistsTF` fallbacks down the registry's list, the alternate is
`\tlalt` (`\nasta` kept), and `\tlvertical{<height>}{<text>}` is the
rotated-box tategaki. Japanese adds `\XeTeXlinebreaklocale "ja"` and a
small `\XeTeXlinebreakskip`, which is what lets XeTeX break a line inside
a run of kanji and kana without any CJK package — verified on this
machine with Noto Serif CJK JP.

**Concurrency.** The server is threaded, so per-document render state
(footnote numbering, run occurrence counters) is held in a thread-local
`ThreadDict`; `meta.json` is written atomically under a per-document
lock, and a build refuses to start while one is already running.

**Fonts.** No TeX engine reads `.woff2`. The TTFs in `assets/fonts` are
the official Vazirmatn v33.003 `.woff2` files decompressed with
fontTools — same outlines, same GSUB (`arab` script present, which is
what gives contextual shaping). `envsetup.ensure_fonts()` re-derives
them from the GitHub release if the directory is emptied.

**Hyphenation is per document, and never guessed.** One language's
patterns applied to another are worse than none: English rules chop
Italian into `straordinar-` and `soprav-`, and Italian rules do the
same violence to English. So the language comes from the document's own
`lang:`, mapped to a TeX language name by `texgen.hyphenation_for()`,
and the template activates it **only if the running format actually
carries that language**:

```tex
\expandafter\ifx\csname l@italian\endcsname\relax\else
  \language=\csname l@italian\endcsname
  \lefthyphenmin=2 \righthyphenmin=2
\fi
```

An unknown, misspelled or missing `lang:` therefore costs nothing but
TeX's own default — language 0, US English — rather than a confidently
wrong set of break points. Each language carries its own
`\lefthyphenmin`/`\righthyphenmin` (Italian 2/2, English 2/3).

Italian is the one language exlex ships patterns for, because it is
absent from many TeX Live installs; every other language is expected to
come from the distribution. XeTeX loads patterns **only at format-build
time**, so `envsetup.ensure_italian_hyphenation()` installs
`assets/hyph` into `TEXMFHOME`, **copies the system `language.dat`** and
appends `italian loadhyph-it.tex` to the copy — the other languages'
entries are preserved, which is what keeps English working — then runs
`fmtutil-sys --byfmt xelatex` (falling back to `--user`). Two traps:
(1) the loader must set `\lccode"0027="0027` (and U+2019) before
`\input hyph-it.tex`, because the Italian patterns contain apostrophes
and INITEX otherwise dies with `! Nonletter.`; (2) that whole step is
optional — if it fails, an Italian document is merely unhyphenated and
every other language is unaffected.

**Verification method** (`verify.py`). Extract every glyph with its x
coordinate (PyMuPDF `rawdict`), bucket into baselines, sort by x = true
visual order (by each glyph's middle: the second letter of a Latin `ff`
ligature is a glyph of no width at the next glyph's left edge, and
ordered by left edges "Kaffee" once read "Kafefe"); then **reverse the glyph sequence first and only then
decompose presentation forms** to base letters. Order matters: the
lam-alef ligature is a single glyph whose decomposition is already in
logical order, so decompose-then-reverse corrupts every word containing
`لا` (this produced three false failures — چالاک, لاک‌پشتی, ملایم —
before the order was fixed). Diacritics (Mn) and ZWNJ are stripped on
both sides, so a *misplaced* diacritic would not be caught — check those
visually at high resolution. A string found only unreversed is reported
as `LTR word order (bidi bug!)`.

Two spellings of one letter would otherwise read as two letters, so a
small fold is applied to both sides before comparing: Persian writes
`روزنامهٔ` as heh + hamza-above, while the shaper hands back the
precomposed U+06C0, and the Arabic/Persian yeh and kaf pairs differ the
same way. Folding them cannot hide a word-order fault — it changes
letter identity, never sequence.

**Runs that wrap.** A `\pel` run is breakable by design, and one that
wraps is split between reconstructed lines, with other material between
the pieces. A breakable run not found whole on one line is looked for
once more across the line ends (`verify.wrapped_runs`): the right-to-left
islands of each line (the stretches between its Latin letters and
digits), chained in reading order — in a left-to-right paragraph from a
line's last island to the next line's first, in a right-to-left one from
its first to the next line's last — through any lines that are one island
each. Large print made this common (a display line at 20 pt, a phrase in
an Italian sentence at 17). A `\pe` is never looked for this way — it
cannot wrap, and two short words are too easily met by chance where two
lines are joined — and a run whose words came out reversed on any line
still fails: with the classic bug put back (no `\beginR`), the check
reports exactly what it reported without the second look
(tests/test_studio_pdf_print.py). A run broken across a line whose other
target-language text sits between the pieces is still reported
`missing`: check any `missing` on a long run by eye before ignoring it.

A left-to-right target has no islands to chain: its lines are joined
whole, so a wrapped run is found — unless something stood beside it on
its lines. A printed true/false statement's first line ends in its
marks, and a matching entry's lines alternate with those of the entry it
faces, so a correct German or Italian worksheet was reported `missing`.
A breakable run not found is looked for once more down the page's
columns (`verify.column_runs`): each line is cut where a gap wider than
three quarters of an em opens in it, and the pieces that start at one x
are read down the page in order. A run with a word out of order or one
the PDF lacks is still reported (tests/test_studio_pdf_print.py).

**Devanagari is drawn out of its written order**, in two places, and the
PDF reads back as drawn: the vowel sign i (ि) comes before the consonants
it follows in writing ("किताब" reads "िकताब"), and a र् before a consonant
is a hook over the end of the cluster it begins ("कुर्सी" reads "कुसर्ी",
"दर्शक" reads "दशर्क"). A correct Hindi starter was 34 strings `missing`.
`verify._written_order` puts both back where they are written before the
comparison — only them, and only from where the shaper draws them: a PDF
set without Devanagari shaping draws ि after its consonant and र् before
it, the rules move them past the next consonant and before the one in
front (a र् with none in front, as in "अर्थ", is read as nothing), and
every string holding one is reported (a starter with each ि cut from its
consonant: 25 failures, each with a ि; the old comparison passed it
121/122 and failed the correct PDF). Where the two meet the order alone
cannot tell which cluster the reph is on: "धार्मिक" (reph on मि) and
"मर्यादित" (reph on या, then दि) both read back with र्ि between two
clusters. The glyphs can: Noto Serif Devanagari draws a reph over a
syllable with ि as one glyph with it, whose ि comes back with no width,
and a reph over the syllable before as a glyph of its own
(`verify._span_chars`). And a ो or ौ under a reph is drawn in two, ा and
the stroke of े or ै with the reph between ("धर्मों" reads "धमार्ें"): once
the reph is back they are one sign again. The Hindi starter verifies
122/122 at every size, and so does a note of everyday words with a reph
(दर्शक, कार्यक्रम, धार्मिक, मर्यादित, धर्मनिरपेक्ष, धर्मों …), in Noto Serif
Devanagari, whose glyphs carry their characters (the system's Noto Sans
Devanagari leaves the ि and the conjuncts without any).

**Debugging order problems.** `python3 exlex/exlex.py inspect FILE.pdf
PAGE` prints each line as Persian islands `[…]` in visual left-to-right
order with each island already re-read logically — the fastest way to
answer "did these comma-separated items keep their order?".

## Extending

* **A new language** is an entry in `../lib/languages.json` (its
  character ranges, direction, fonts, TeX names, whether it has a reading
  or can be set vertically) plus a `../lib/lang/<code>.tex` for the
  reading editions and a `../docs/lang/<code>.md` of conventions; the
  studio needs nothing of its own — it asks the registry. The steps are in
  [`../docs/languages.md`](../docs/languages.md), §10.
* **Sizes.** `--scale` (inline target text vs Latin; the default is the language's own — 1.52 for an Arabic script, 1.20 for CJK, 1.00 for a Latin-script target, which is the same alphabet as the prose), `--size` (the print size: `%%DOCUMENTCLASS%%`, `%%MARGINS%%` and `%%PRINTOPTIONS%%`, which at 11 pt in colour write exactly what the template always had) and the `%%VOCESIZE%%`/`%%VOCELEAD%%` placeholders (default 38/44 pt, scaled with the print size; `%%VOCEFIT%%`, nothing at 11 pt, fits the lines beside the headword in large print). A placeholder line of the template may carry a note after its name: the whole line is replaced, and the note never reaches the `.tex`.
* **New block types.** Add a branch in `mdparser.parse` producing a new
  block dict, and renderers in **both** `texgen.render_blocks` and
  `htmlgen.render_blocks`. Keep parser and generators ignorant of each
  other's internals.
* **Layout changes** belong in `template.tex`; anything touching
  `\pe/\pel/\peb` or `\TeXXeTstate` must be followed by a full
  `build ../tests/fixtures/studio/persiano/persiano.md` and a clean verify.

## Known limitations

No code blocks. Footnotes do not nest, though an inline
footnote, a link and a `{la}` block each tolerate one level of bracketed
mark inside; a **colour mark** still cannot
(`[[a](b)]{teal}` stays literal). one nesting level for bullets; `|` cannot occur inside table cells. one nesting level for bullets; `|` cannot occur
inside table cells. Western digits or Latin letters *inside* a phrase of
the target script split the run — write them outside, or wrap the stretch
as `[…]{tl}`. Emphasis never applies across the target script (a stray `*`
next to it stays literal — use `✗` for ungrammaticality). A
`## فارسی | …` heading is always a lemma, so a plain section title
cannot start with the target script *and* contain `|`; for a Latin-script
target a heading with two or more `|` fields is a lemma, so there a plain
section title cannot contain `|` at all. Very wide tables can exceed
the text block: shorten cells or drop a column. The gloss harvester
depends on the italics to know where a translation ends; without them it
reads a single word and says so, in red, rather than guessing.

## Regression test

Three documents under `../tests/fixtures/studio/` whose counts are pinned,
each in a directory of its own with its `images/` (and `audio/`) beside it,
exactly as a document sits in the library:

* `persiano/persiano.md` — **6 pages, `186/186 target strings correct`, no
  overfull > 10 pt.** Run it after any change to the parser, generator,
  template, or macros: the Persian document must render the same HTML and
  verify the same count as before languages existed (`../docs/languages.md`
  §11).
* `feature-test/feature-test.md` — **`21/21`**, and the one that
  exercises figures, footnotes, links, the palette and blocks all the way
  to a PDF.
* `audio/audio.md` — **`8/8`**, with `audio/greeting.mp3` and
  `images/swatch.png` beside it: recordings on the page, clipped
  (`start=0.5 end=1.25`, a start alone, an end alone), inside a box beside a
  footnote, numbered in one series with a picture; a jolly card whose fields
  hold a heading, a recording, a table, a nested list, a box with a note and
  a picture; and a vocabulary card with a recording on each side. Run it
  after any change to how recordings or card fields are parsed or drawn.

The first two sat in `exlex/examples/` until the examples were cleared.
Beside them
stood one document per script — an Arabic, an Italian and a Japanese one
exercising the marks each adds: full tashkil, `{tl}`-marked runs, `kana:`
and a vertical block — written when the studio read Persian for Italians,
and gone until better ones exist. The two fixtures followed the tests
instead, because a verify count is a property of that exact document and
cannot be reconstructed from another. Meanwhile every language still
reaches both renderers through its fixture edition, as a document built
from its own first chunk: `python3 ../tests/smoke.py`, which also builds
the fixtures to PDF with `--pdf` and holds each to its pinned count.

## Licences & provenance

Code: the studio is part of Parseh, and under Parseh's licence, the GNU
General Public License, version 3 or (at your option) any later version
(`GPL-3.0-or-later`, the toolbox's [`LICENSE`](../LICENSE)); each source file
says so in its `SPDX-License-Identifier` line. The app's *Licences* page
(`/licences/`) lists everything below for a user.

Fonts, each under its own licence (their texts and the copyright notices in
[`lib/fonts/OFL.txt`](../lib/fonts/OFL.txt) and
[`lib/fonts/GUST-FONT-LICENSE.txt`](../lib/fonts/GUST-FONT-LICENSE.txt),
every file named in [`lib/fonts/README.md`](../lib/fonts/README.md)):
Vazirmatn © the Vazirmatn Project Authors (Saber Rastikerdar), SIL OFL 1.1
(TTFs derived from the official v33.003 release `.woff2`); Noto Nastaliq
Urdu, Noto Naskh Arabic and Noto Serif Devanagari © Google, SIL OFL 1.1.
Japanese and Chinese are set in the device's Noto Serif/Sans CJK (SIL OFL
1.1) or the system's own faces; none travels with the studio. TeX Gyre
Pagella and Heros, which set the studio's and the guide's pages: ©
B. Jackowski, J. M. Nowacki and the TeX users groups, GUST Font License
(LPPL 1.3c or later), copied from TeX Live — the studio copies them at
start, and the guide's build into `html-guide/site/_parseh/fonts/`, with
the licence beside them.

`assets/hyph/hyph-it.tex` © 2008–2011 Claudio Beccari, from the hyph-utf8
project, under the LaTeX Project Public License 1.3 or later or the MIT
licence, at the user's choice (its header says so, and carries the MIT
text); `loadhyph-it.tex` beside it is a minimal local loader, and Parseh's. MathJax (`../lib/mathjax/`) © The
MathJax Consortium, Apache License 2.0 (its `LICENSE` beside it).
