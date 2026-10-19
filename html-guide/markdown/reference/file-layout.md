---
title: The file layout
linkTitle: File layout
weight: 4
description: The folders of Parseh, your settings in config/, and what a book, a video, a studio document, a note, an exercise deck and an Anki deck look like on the disk.
---

Every folder and file of Parseh, one by one: the detailed companion of
[Where everything lives](../getting-started/where-things-live.md) in
*Getting started*. You never need to open these folders — every page of
Parseh reads and writes them for you, and a **download** or a **Backup**
takes nearly anything away in one file (a backup of the whole book shelf
leaves the recordings out: [Keeping everything
safe](daily-loops.md#keeping-everything-safe)). This page is for when you want to look
anyway: to find a recording, to back a folder up by hand, to understand
what a zip holds.

Everything is under the folder you unpacked from a release, the one that
holds `serve.sh`. Nothing is installed anywhere else, except the word
analyzers' models (in `~/.pkuseg/`), the environment if you made it with
your own conda, and what your browser keeps.

## The folder

```text
Parseh/
  serve.sh  serve.py  serve.bat
  install.sh  install.bat  Parseh.command
  build.sh  environment.yml
  VERSION  CHANGELOG.md  README.md  LICENSE
  lib/  books/  youtube/  markdown/  exercises/  clips/
  dict/  corpus/  mt/  components/  texmf/  stt/  arasaac/  config/
  docs/  html-guide/
  .runtime/  .tls/  .parseh-release.json  .parseh-update/
```

| Path | What it is |
|---|---|
| `serve.py` | The one server: https, the hub, every door, the guide. `serve.sh` runs it in the background. |
| `serve.bat` | The same on Windows: double-click it. The first run is a setup wizard (its work is done by `lib/launcher.py`). |
| `install.sh` | The installer on Linux and macOS. `install.bat` is Windows's, and `Parseh.command` a Mac's double-click that installs the first time and then starts. |
| `build.sh` | Builds the books: each one's PDF and reader, and the library page. |
| `environment.yml` | The packages of the `ilya-frank` environment. |
| `VERSION` | Which version of Parseh this is, one line: what the hub's foot, Settings and the server's first line say. `CHANGELOG.md` says what each version changed. |
| `lib/` | What every door shares — see the next table. |
| `books/` | The books, one folder a book, under its language's folder (below). |
| `youtube/` | The video player: `lib/` (its pages, its script, the annotation pipeline, the Anki tools), `videos/` (one folder a video, below), `anki/` (the card store, below). |
| `markdown/` | The studio: `app/` (its server, pages and script, and the exercise decks' pages, store and scheduler), `exlex/` (Markdown to LaTeX to a verified PDF, and `starters/`, the page a new document starts from), `library/` (one folder a document, below), `open/` (the copies of files opened from the computer, below). |
| `exercises/` | The exercise decks, one folder a deck, under its language's folder (below). |
| `clips/` | The clip tray: recordings and frames cut for cards, waiting to be used. |
| `dict/` | The reading help's downloads, with `corpus/`, `mt/` and `components/` (below). |
| `texmf/` | The TeX packages Parseh got for the LaTeX drawings, with the list of them, `parseh-packages.json`. |
| `stt/` | Speech to text's program and models, fetched on Settings → Speech to text (below). Made on demand; git ignores it. |
| `arasaac/` | The ARASAAC pictograms and the words that name them, fetched on Settings → Pictograms (ARASAAC) (below). Made on demand; git ignores it. |
| `config/` | Your settings, and the devices let in (below). |
| `docs/` | The design notes: `languages.md`, `lang/<code>.md` (each language's conventions), `mobile.md`, `installer.md`, `studio-exercises.md`, the notes on character components, the prompts, and `releasing.md`, the checklist a new version is released by. |
| `html-guide/` | These pages: `markdown/` (their source), `build.py` and `engine/` (the compiler), `assets/` and `index.html` (the front page); `site/` is what a compile makes. |
| `.runtime/` | The environment, when the installer made it: `bin/micromamba`, `env/`, and micromamba's package cache, `mamba/`. |
| `.tls/` | The certificates `serve.py` makes: its own authority (`ca.pem`, made once — the one a phone is told to trust, to install the mobile interface as an app) and the server's, signed by it and made again as it nears its end. |
| `.parseh-release.json` | The release's list of its own files: the version, the commit it was built from, and every file with its checksum and whether it runs. An [update from Settings](../getting-started/updating.md) reads it, and writes the new version's in its place. |
| `.parseh-update/` | What the last three updates kept, one folder each under `jobs/`: every file an update replaced or deleted, before it did, and the report the page shows. |

### Inside lib/

| Path | What it is |
|---|---|
| `languages.json` | The language registry: everything a language is, read by every tool through `languages.py`. Parseh's own languages; one added on this machine is in `config/languages.json`, which is read after it and which an update never touches ([Adding a language](../lookup-and-languages/adding-a-language.md)). |
| `lang/<code>.tex` | What each language decides in a book's LaTeX preamble. |
| `verbs/<code>.py` | How each language's verb entry (`\vb`) is read out of its dictionary. |
| `parseh.js` | With `parseh.css`: the palette and the themes, the language chips, the clipboard, the Browser/Mobile mode. |
| `mobile.css` | The mobile interface's sheet. |
| `mobile.py` | The mobile interface's pages the server writes: the book shelf, `/m/books/`; installing it as an app, `/m/install/`; the page the app shows when the server cannot be reached; the app's manifest. |
| `mobilereader.js` | A book's reader in the mobile interface: the layer `parseh.js` loads into every reader. |
| `sw.js` | The app's service worker, served at `/sw.js`: it answers a page with *Parseh cannot be reached* when the server is away, and touches nothing else. |
| `icons/` | The app's icons. (A copy of the source code also has `make.mjs`, which drew them.) |
| `activity.js` | With `activity.py`: what the server is working on — the **Working…** pill and the hub's panel. |
| `tex2html.py` | A book's reader, written from its chapters. |
| `bundle.py` | A book or a video as one zip. |
| `draft.py` | A book or a video started empty. |
| `runtime.py` | Finding the environment and making it; `env.sh` finds it for the shell scripts, and `launcher.py` starts Parseh on Windows. |
| `version.py` | Reads `VERSION`, compares two versions, and names the shape of each kind of file Parseh writes. |
| `updater.py` | Updating from Settings, with `updatepage.py`, the page: the plan, the backup, the files replaced one by one, and finishing or undoing an update that was cut off. |
| `release.py` | Building a release's zip and its list of files, for whoever releases Parseh (`docs/releasing.md`). |
| `getdict.py` | With `getcorpus.py`, `getmt.py`, `getsyn.py` and the components' getter: the reading help's downloads, each through `download.py`, which stops them and carries them on. |
| `getstt.py` | Speech to text's manager: the pinned program and models, what is installed (read from the folders' names, never by importing the program), the processor, and the children it starts. With `stt-requirements.txt` (the hash-pinned list of the program's packages), `sttprobe.py` (the look at the graphics card, in a process of its own) and `speechpage.py` (the page, Settings → Speech to text). |
| `getarasaac.py` | The ARASAAC pictograms' manager: the word lists from `api.arasaac.org`, the pictures from `static.arasaac.org` one at a time on one connection, what is installed (read from the files), an update that fetches only what ARASAAC changed, and the credit its licence asks for. With `arasaacpage.py`, the page (Settings → Pictograms (ARASAAC)). |
| `guidebuild.py` | Serving the guide at `/guide/`, and its **Compile the guide** button. |
| `fonts/` | Vazirmatn, Noto Nastaliq Urdu, Noto Naskh Arabic, Noto Serif Devanagari. The Japanese and Chinese faces are the system's own. |

### One folder per language

Every door files its content under the language it teaches, in a folder
named after the language in English, in lower case: `persian`, `arabic`,
`italian`, `japanese`, `french`, `german`, `turkish`, `english`, `hindi`,
`spanish`, `chinese`. The list comes from the language registry,
`lib/languages.json`, and nowhere else. A book, a video or a document
lying directly under `books/`, `youtube/videos/` or `markdown/library/`
— the layout from before there were languages — is still read, as
Persian, with a note to move it.

## A book

`books/<language>/<slug>/`, the slug being the book's short name in Latin
letters. The tests' small books, one in each language under
`tests/fixtures/books/` (`tests/fixtures/books/japanese/mini-ja/`, say),
are short ones to look at.

| Path | What it is |
|---|---|
| `book.json` | The title and author (and their transliterations), the language and the gloss language, the narration's recordings and what each covers. |
| `main.tex` | The edition's own title page, and the chapters it inputs. |
| `ch1.tex`, `ch2.tex` … | The chapters, written by hand: every chunk one `\ch` call (or `\chr`, `\chw`, `\chp`…). |
| `NOTES.md` | Notes on the edition, when it has them. |
| `annot/` | The annotated paragraphs an LLM wrote, batch by batch, when the book was made that way (`check_batch.py` and `assemble.py` read them). |
| `source/paras/` | The text the edition was made from, one file a paragraph (`ch1_p01.txt` …): what the chapters must still reproduce. |
| `src_chN.json` | In `source/`: the same paragraphs, one list per chapter, for `assemble.py`. |
| `reading.json` | The reader's own decisions: paragraphs that may depart from their source, runs of paragraphs folded away. |
| `audio/` | The narration: one or more recordings, and their transcripts. |
| `timings.json` | Where each subparagraph is in the recordings. A `% @par` comment above each subparagraph in the chapters says the same. |
| `review.json` | With its corrections and `review.html`: an alignment's review. |
| `markdown/` | The notes written into the book's seams (below). |
| `main.pdf` | *Built:* the PDF. |
| `reader/` | *Built:* `index.html`, and `ch-2.html` … for a book of several chapters. |
| `.build-key` | And `.reader-key`. *Built:* what the last build read, so that an unchanged book is skipped. |

What is *built* is made by **build**, **build PDF** and **rebuild the
reader**, and is never in a download: a stale copy carried back in would
show text the chapters no longer say. A book's **download** holds
`book.json`, every `.tex` (`main.tex` and the chapters), `NOTES.md`,
`source/`, `markdown/` and `reading.json` — and, as the shape you pick
asks, the timings, the alignment's review and `audio/` (never
`review.html`, which is a page). `annot/` is not in it in any shape: it
stays on this machine. Taking a book off the shelf with ✕ moves the
whole folder to `books/.trash/`.

## A video

`youtube/videos/<language>/<id>/`, where the id is the YouTube video's
own, or for a film on this machine the one the add page gave it.

| Path | What it is |
|---|---|
| `video.json` | The title and its native form, the channel, the language and the gloss language, the level, the blurb. |
| `transcript.txt` | The transcript as it was pasted: the text every caption is checked against. |
| `annotations.json` | Every caption's chunks and glosses: what the player shows. |
| `parts/NN.json` | The batches an LLM annotated. They exist only **while the video is being added** — `merge_parts.py` assembles the file above from them and they are dropped before the video reaches the shelf. A video added before 23 September 2026 may still carry them; nothing reads them ([parts/ is retired](../videos/the-files.md#parts)). |
| `waveform.json` | The picture of the sound, once one has been recorded. |
| `media.<ext>` | The film itself, or the sound, for a video that is a file on this machine (`media-orig.<ext>` beside it keeps the original of a sound that had to be made playable). |
| `markdown/` | The notes written into the video's seams (below). |

The player's **⤓** downloads all of it as one zip, a film on this machine
included (`lib/bundle.py pack --media text` leaves the film out). A video
is on the index as soon as its folder is there: there is nothing to
build. Taken off with ✕, it goes to `youtube/videos/.trash/`.

## A studio document

`markdown/library/<language>/<id>/`, filed under the document's target
language (its front matter's `target:`) and moved when that changes. The
id is made from the first title and a random suffix, and never changes,
whatever the document is renamed to.

| Path | What it is |
|---|---|
| `source.md` | The document: its front matter and its Markdown — the one truth. |
| `meta.json` | Its name, its tags, its uid, its dates, its last build and the options it was built with. |
| `images/` | Its pictures. An SVG gets a `.svg.pdf` twin for the PDF, a PDF a `.pdf.svg` twin for the page. |
| `audio/` | Its recordings. |
| `build/` | *Built:* `main.tex`, `main.pdf`, and what the build needed beside them. |

A document's **Download ▾** gives the Markdown alone, the Markdown with
its pictures and recordings as a zip (its tags travel beside it, in
`<name>.tags.json`), the `.tex` or the PDF. The library's **Backup**
takes every document whole, `meta.json` included, so that **Load from
backup** brings each back as itself.

### A note in a seam

A note written between two lines of a book or a video is a studio
document in every respect but where it lives: in that book's or video's
own `markdown/` folder, laid out as the studio's library is —
`books/<language>/<slug>/markdown/<language>/<id>/source.md`. Its front
matter says where it sits (`anchor: after sub …`, `anchor: before cap …`),
and it travels in the book's or the video's download.

## Files opened from the computer

`markdown/open/<id>/`, one folder for each file the studio has open from
elsewhere on the computer ([Opening a file from your
computer](../studio/open-files.md)). It is made when you open the file and
deleted when you close it; git ignores it, and a release does not carry it.

| Path | What it is |
|---|---|
| `session.json` | Where the file is, how it looked when it was opened (its size, its date and a checksum, which is how a change made by something else is told from a touch), what it held at the last save, and what was accepted to be left out of a Markdown file. |
| `library/<language>/<id>/` | The copy: a library of one document in the shape of [a studio document](#a-studio-document), served by the studio's own pages. |

The copy is inside Parseh's folder, and not in the operating system's
temporary folder, on purpose: the PDF is built inside it, as a library
document's is, so it builds wherever the library does — a user name written
in Persian or Chinese puts the system's temporary folder where TeX may not
read it — and a copy that holds changes survives a restart of the computer.

A copy with nothing unsaved is deleted when Parseh stops, and again when it
starts; one with unsaved changes stays, and the library page lists it. The
file you opened is never in this folder: it stays where it was, and changes
only when you save.

## An exercise deck

`exercises/<language>/<slug>/`:

| Path | What it is |
|---|---|
| `deck.json` | Its name, its language, its id, and the options that differ from the defaults. |
| `items/<id>.json` | One exercise: its Markdown, its footnotes, where it came from. |
| `schedule/<id>.json` | Its state and every answer given (no file while it is new). |
| `images/` | The pictures its exercises use. |
| `audio/` | The recordings its flashcards play. |

A deck moves between machines by its **Export** (with or without the
scheduling) or by the Exercises page's **Backup**, never by git. A
deleted deck goes to `exercises/.trash/`.

## The Anki card store

`youtube/anki/`, shared by the book reader and the video player. A deck
is a folder, `<language>/<deck>/`, holding:

| Path | What it is |
|---|---|
| `deck.json` | The deck's name, its language, its Anki id. |
| `cards/<id>.json` | One card a file: the truth the `.apkg` is built from. |
| `media/` | The screenshots and recordings the cards show. |
| `deleted/` | Cards a sync retired because you deleted them inside Anki. Move one back into `cards/` to undo. |

And beside the decks, for the whole store:

| Path | What it is |
|---|---|
| `inbox/` | The exports you dropped on the sync page. |
| `build/` | The `.apkg` files built to import into Anki. |
| `notetypes.json` | With `seen.json`: what the store knows of your Anki collection. |

## The clip tray

`clips/` holds, in one flat folder, every recording cut from a narration
or a film and every frame captured from a video, under names no other
file of the toolbox has — so that a card's Markdown naming one can be
pasted anywhere. A document, a deck or an Anki card that uses one takes a
copy when it is saved; **The clip tray** on the hub plays them and deletes
what no card needs any more.

## The reading help's downloads

| Path | What it is |
|---|---|
| `dict/<code>.db` | A dictionary, from Wiktionary. |
| `corpus/` | Sentences somebody translated, from Tatoeba: `<code>-<gloss>.db`, one a pair of languages. |
| `mt/` | The translation engine, and one folder of model per pair, `mt/<from>-<to>/`. |
| `mt/synonyms.en.json` | The WordNet synonyms the machine's reading uses. |
| `components/` | The Kanji and Hanzi component packs, `<source>.db`. |

All of them are got and removed on the reading-help page, `/settings/reading-help/` (or by the commands in [The
command line: content, lookup, Anki](commands-content.md)). A download
stopped half way leaves what had come beside where it goes — a file ending
in `.part`, with a small `.part.json` saying where it came from; a model's
`mt/<from>-<to>.part/` — so that the next **Get it** carries on from there.

## Speech to text's downloads

| Path | What it is |
|---|---|
| `stt/runtime/<generation>-cp312/` | The program, made by pip from `lib/stt-requirements.txt`; the folder's name is the record of which pinned list it was made from and for which Python. |
| `stt/models/<model>/` | One of the two Whisper models: `large-v3-turbo` or `large-v3`. Five files and a `meta.json`. |
| `stt/models/<model>.part/` | A model whose download was stopped, kept for the next **Get it**. |
| `stt/runtime.part-<pid>/` | The program while it is being installed. Never taken for a program; swept when Parseh starts. |
| `stt/tmp/` | The sound of a video while it is being transcribed, and pip's scratch space. Deleted when the job ends, and swept when Parseh starts. |

They are got and removed on **Settings → Speech to text**,
`/settings/speech/` ([Speech to text](../lookup-and-languages/speech-to-text.md)).
No release carries a file of `stt/`, and no update touches it.

## The pictograms' downloads

| Path | What it is |
|---|---|
| `arasaac/pictograms/<number>.png` | One pictogram, at the one size the manifest says (300 or 500 pixels). A file is there only when it is whole: it appears under its name by one rename. |
| `arasaac/index.<language>.json` | One language's words: for each pictogram that has any, its keywords with their kinds, plurals and meanings. |
| `arasaac/pictograms.json` | One record per pictogram: when ARASAAC last changed it, its flags and its WordNet numbers; a record marked as still to be fetched is how a stopped download knows where to carry on. |
| `arasaac/manifest.json` | The shape (a format number), the size, the languages, when, and whether it is whole. |
| `arasaac/LICENSE-ARASAAC.txt` | The credit and the licence, word for word as ARASAAC's terms give them, written when a download ends. |
| `arasaac/tmp/` | A word list on its way (a `.part` and its small `.part.json`), so that a cut download carries on. |

They are got, updated and removed on **Settings → Pictograms (ARASAAC)**,
`/settings/arasaac/` ([Pictograms](../studio/pictograms.md)). No release
carries a file of `arasaac/`, and no update touches it.

## Your settings: config/

`config/` holds what this Parseh has been told, and nothing else. No
release carries a file of it, and no [update](../getting-started/updating.md)
touches one.

| Path | What it is |
|---|---|
| `prefs.json` | Each book's reading place; the settings that follow you from device to device — the narration's speed, its gap, how far ↺ and ↻ carry, whether a chapter's start waits (`bk_stopbnd`), whether the recording goes on into the next line (`bk_cont`), the theme, and the names you gave the levels (`bk_lvl:<language>:<level>`, one key each); and, in a section of its own, `later`, the chunks you flagged to [review later](../books/review-later.md): a record for each, with the chunk's text and gloss and where it is, and a mark for each removal that stays 90 days so that a device that was away cannot bring it back. It is the computer's and no book's, so no bundle carries it. Two pages writing it at once cannot cross: the file is written through a lock. |
| `network.json` | Who may reach Parseh (the doors of **Settings → Network**, and the ranges and names you added), its port, the certificate you gave it if any, and **every device you let in**, each with the secret token it carries in a cookie. Whoever has this file can pass for those devices: keep it as you would a key. |
| `languages.json` | The languages added on this machine ([Adding a language](../lookup-and-languages/adding-a-language.md)); there is none until you add one. |
| `llm.json` | The host-local LLM endpoint, selected model, context budget and private API key ([LLM Integration](../lookup-and-languages/llm-integration.md)). Never synced or shipped; keep it as you would a key. |
| `updates.json` | Whether Parseh looks for a new version once a day, and what it last found. |
| `prompts.json` | The prompts you wrote for a chatbot ([Your own prompts](../studio/your-prompts.md)): each with its name, the place it is for, its words and, for one in place of Parseh's, the words of Parseh's it began from. |
| `digests.json` | A checksum of every file a phone may keep, so that the phone can tell a file that came whole from one that did not. Worked out again whenever it is missing. |
| `wheres.json` | Where in its book each recording is, as a phone's *Keep on this phone* list says it. Worked out again whenever it is missing. |

Each is written whole, through a temporary file and a rename, so a crash
leaves the old file or the new one and never half of either.

## What is not in a release

A release ships the doors and none of the content: the language folders
under `books/`, `youtube/videos/` and `markdown/library/`, and `config/`,
`dict/`, `clips/` and `exercises/`, hold a placeholder and nothing else.
Nor does it carry what only the people working on Parseh need: the tests,
the GitHub workflows, the demo pictures of the project's page. The builder
that makes a release refuses one that would carry anything of yours.

In a copy of the source code, what you add to those folders — books,
videos, documents and their notes — shows in git as untracked files:
nothing ignores them, and nothing commits them unless you do.

Git ignores outright, so that a stray `git add` cannot take them:

- your study state and your cards: the exercise decks, the Anki store,
  the clip tray;
- the recordings and films: `audio/` under a book, `media.*` under a
  video;
- everything a build makes: the PDFs, the readers, the library page
  (`books/index.html`), a studio document's `build/` — but not the guide's
  compiled `html-guide/site/`, which is committed so that GitHub Pages can
  publish it;
- the copies of files opened from the computer (`markdown/open/`);
- a book or a video taken off the shelf (`.trash/`), the downloads of the
  reading help, your settings (`config/`), the environment
  (`.runtime/`), the certificate (`.tls/`), the updates' backups
  (`.parseh-update/`), `serve.log` and `.serve.pid`.
