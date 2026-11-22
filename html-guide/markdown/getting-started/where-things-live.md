---
title: Where everything lives
weight: 8
description: The folders on the disk — the software, your books, videos, documents and decks, your settings, and what the toolbox makes — what a release brings, and what never leaves your computer.
---

Everything Parseh has is in its own folder: the software, everything you
put into it, and everything it makes. Outside it there are only:

- the models of the Chinese word analyzer, in `~/.pkuseg`;
- the environment, when you made it with your own conda;
- on a TeX Live that has no Italian hyphenation, the Italian patterns the
  server adds to your own TeX folders as it starts (`TEXMFHOME` and
  `TEXMFCONFIG`, with the XeLaTeX format rebuilt to take them), so that
  the PDF of a studio document written in Italian breaks its words where
  Italian breaks them;
- with `./install.sh --pdf`, the TeX packages it adds to TeX Live itself;
- in each browser, a few of your preferences.

Deleting the Parseh folder leaves these behind: [Removing
it](installing.md#removing-it) says where each of them is.

## The folder

```text
Parseh/
  books/                 the books
  youtube/videos/        the videos
  youtube/anki/          the Anki card store
  markdown/library/      the studio's documents
  exercises/             the exercise decks
  clips/                 the clip tray
  dict/  corpus/  mt/  components/
                         what the reading help fetches
  stt/                   speech to text: its program and its two models
  arasaac/               the ARASAAC pictograms and the words that name them
  texmf/                 the TeX packages Parseh got for its drawings
  markdown/latex/        the LaTeX drawings, made again when missing
  config/                your settings, the devices let in
  lib/  markdown/app/  markdown/exlex/  youtube/lib/
                         the software
  html-guide/            this guide
  docs/                  notes on the design
  .runtime/              the environment the installer made
  .tls/                  the certificate
  .parseh-release.json   the list of the release's own files
  .parseh-update/        the backups of the last updates
```

**What one of each is made of**:

- `books/<language>/<slug>/` — **a book**: `book.json`, `main.tex` and its
  chapters, `source/` (the text it was made from), `markdown/` (the notes
  written beside it), `audio/` (its narration), `reader/` (its reader,
  built) and `main.pdf`.
- `youtube/videos/<language>/<id>/` — **a video**: `video.json`,
  `annotations.json` (the glossed transcript), its transcript and parts,
  `media.*` (the film, for a video of your own), `markdown/` (its notes).
- `youtube/anki/<language>/<deck>/` — **a deck of the Anki card store**.
- `markdown/library/<language>/<id>/` — **a studio document**:
  `source.md`, `meta.json`, its pictures and recordings, `build/` (its
  PDF).
- `exercises/<language>/<slug>/` — **an exercise deck**: `deck.json`,
  `items/`, `schedule/` (your answers), `images/`, `audio/`.
- `clips/` — **the clip tray**: the recordings and frames cut for cards.
- `dict/`, `corpus/`, `mt/`, `components/` — **what the reading help
  fetches** (**Settings → Reading help**): dictionaries, translated
  sentences, translation models, character packs.
- `stt/` — **speech to text**, fetched on **Settings → Speech to text**:
  `runtime/` (the program, in a folder named for the pinned list and the
  Python it was made for), `models/` (the two Whisper models) and `tmp/` (the
  sound of a video while it is being transcribed, deleted afterwards).
- `arasaac/` — **the ARASAAC pictograms**, fetched on **Settings →
  Pictograms (ARASAAC)** ([Pictograms](../studio/pictograms.md)):
  `pictograms/` (the pictures), `index.<language>.json` (the words that
  name them), a manifest, and `LICENSE-ARASAAC.txt`, which carries the credit
  their licence asks for.
- `texmf/` — **the TeX packages Parseh got** on **Settings → LaTeX
  drawings**, for the [latex blocks](../dialect/latex-drawings.md) of a
  theme, with `parseh-packages.json`, the list of them.
- `markdown/latex/` — **the drawings** the latex blocks became, each once:
  made again from its block when it is missing.
- `config/` — **your settings**: `prefs.json`, each book's reading place,
  the settings that follow you from device to device, the names you gave
  the levels and the chunks you flagged to review later; `network.json`,
  who may reach Parseh, its port, and every device you let in, each with
  the secret token it carries — keep it to yourself, as you would a key;
  `languages.json`, the languages you added, when you have; `updates.json`,
  whether Parseh looks for a new version once a day; `prompts.json`, the
  prompts you wrote for a chatbot; and `digests.json` with `wheres.json`, what a
  phone checks the things it keeps against. When one of your settings files
  cannot be read (cut short by a crash, or broken by hand), Parseh does not
  write over it: before its next save it renames the file, for example to
  `prefs.json.damaged-20261122-101500`, starts that file fresh, and says so at
  the top of the hub until you press **I have read this**. The renamed file
  stays in `config/` for you to open and mend.

**The files at the top**:

| File | What it is |
|---|---|
| `install.sh`, `install.bat` | the installers, for Linux and macOS, and for Windows |
| `Parseh.command` | the Mac's double-click: install once, then start |
| `serve.sh`, `serve.bat` | starting and stopping, on Linux and macOS, and on Windows |
| `serve.py` | the server itself |
| `build.sh` | building the books: their PDFs, their readers, the library page |
| `environment.yml` | what the environment holds |
| `VERSION` | which version of Parseh this is, in one line |
| `CHANGELOG.md` | what each version changed |
| `README.md`, `LICENSE` | what Parseh is, and its licence |
| `.parseh-release.json` | the release's list of its own files, each with its checksum: what an [update](updating.md) reads |
| `serve.log`, `serve.log.1` | the server's log, and the log of the run before (its last megabyte) |
| `.serve.pid` | the server's process number, on Linux and macOS |
| `.setup-done` | the Windows wizard has run through |

**Every kind of content is filed under its language**, in a folder named
after the language in English, in lower case: `persian`, `arabic`,
`italian`, `japanese`, `french`, `german`, `turkish`, `english`, `hindi`,
`spanish`, `chinese`. A book, a video or a note lying directly under
`books/`, `youtube/videos/` or `markdown/library/` — the way they were kept
before Parseh had languages — is still read, as Persian, with a note to
move it.

You never need to touch these folders: every door adds, changes, backs up
and removes what is behind it from its own pages. They are described here
so that you know what to keep safe, and what a folder you see is for.

## What a release brings

Parseh comes as a release: one zip, `parseh-<version>.zip`, holding **the
software, and not your content** ([Installing Parseh](installing.md#getting-parseh)).
A fresh install has:

- all the code, the fonts of Persian, Arabic and Hindi (with their
  licences), the language registry, and the installers;
- the studio's starting pages — what a new document opens with, one for
  each language — with their pictures and their recording;
- this guide, its pages already compiled;
- the list of its own files, `.parseh-release.json`;
- and empty shelves: every folder of content holds nothing but a
  placeholder until you fill it.

An [update from Settings](updating.md) replaces the files on that list and
nothing else. What you add is not on it, so no update touches it.

## What never leaves your computer

What you read and write is yours, not the software's. No release carries
it, no update touches it, and none of it leaves the computer unless you take
it — a download, a backup, a book kept on your phone:

- your books, with their narrations, hundreds of megabytes each:
  `books/`;
- your videos, and the films of your own: `youtube/videos/`;
- your studio documents: `markdown/library/`;
- your exercise decks, with every answer you gave in them: `exercises/`;
- your Anki cards and decks: `youtube/anki/`;
- the clip tray: `clips/`;
- the dictionaries, sentences, translation models and character packs —
  somebody else's work, under somebody else's licence: `dict/`, `corpus/`,
  `mt/`, `components/`;
- the TeX packages Parseh got for its drawings: `texmf/`;
- speech to text's program and models — somebody else's work, and gigabytes:
  `stt/`;
- the ARASAAC pictograms — somebody else's pictures, under a licence that asks
  for a credit: `arasaac/`;
- your settings and the devices you let in: `config/`;
- the environment, the certificate, the log: `.runtime/`, `.tls/`,
  `serve.log`;
- the backups the last updates kept: `.parseh-update/`.

So the backups are how your content moves to another computer:
[Backups at a glance](backups.md) has the four shelves, and a single book,
video, document or deck travels as its own zip from its own page. Moving a
whole Parseh from before it could update itself into a fresh install is
[a few folders moved once](updating.md#moving-into-a-fresh-install-once).

**A copy of the source code**, made with git, holds the same software and
more — the tests, and what GitHub needs. Git ignores most of the list above,
and shows your books, videos and documents as files it has never been told
to keep, so none of it is committed unless you commit it. Such a copy is for
working on Parseh itself, not for using it: it cannot update itself from
Settings.

## Kept in the browser

A few things are not in the folder at all, because they are yours in one
browser rather than the toolbox's: the language picked on the chips, the
**Browser | Mobile** choice, the switches of the reader and the player, the
settings of the ⚙ panels — the sizes, the levels shown, **Diacritics**, the page zoom —, the kanji you marked as known. Each browser
keeps its own, per address, and a backup does not carry them. Where you are
in each book, the narration's speed and its gap, the theme, the names of the levels and the
chunks you flagged to review later are the
computer's, in `config/prefs.json`, so a phone goes on where the desk
stopped.

## Pages that open from the disk

Three kinds of page are plain files that a browser opens without the
server: a book's reader (`books/<language>/<slug>/reader/index.html`), the
books' library page (`books/index.html`), and this guide
(`html-guide/index.html`). They read as they always do; whatever needs the
server — saving, uploading, building, a backup — needs the page opened from
Parseh's own address, and the library page's buttons say so when it is
not.
