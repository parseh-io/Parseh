---
title: The studio
weight: 40
description: A library of Markdown documents about a language — written, read, annotated, drilled and printed.
---

The **Studio** door of the hub opens a library of documents you write
about a language: a note on the verbs of motion, a worksheet for a class, an
answer an LLM gave you about a word, typeset. Each document is one Markdown
file in the studio's own dialect, and the studio is everything around that
file — the shelf that holds it, the editor that writes it with the typeset
page beside it, the page that reads it, and the button that prints it as a
PDF whose every word of the target language has been checked.

This section is about the studio as an application: its pages, their
buttons and what each one does. What you can *write* inside a document —
target-language runs, lemma headings, boxes, formulas — is the
[dialect section](../dialect/_index.md), and its exercises have a section
of their own, [Writing exercises](../dialect-exercises/_index.md).

## The four pages

The studio lives at `/studio/` and has four pages, each a step of the same
work:

- **The library** (`/studio/`) lists every document, filters them by
  language, tag and words, and is where documents come in and go out:
  **+ New**, **Paste LLM answer**, **Upload .md / .zip**, **Backup**,
  **Load from backup**, **Download N shown** — and **Open a file…**, which
  opens a Markdown or zip file where it is, on the computer Parseh runs on, instead of
  bringing it in ([Opening a file from your computer](open-files.md)).
- **The editor** (`/studio/doc/<id>/edit`, or `/studio/new` for a document
  not saved yet) is the Markdown on the left and the typeset page on the
  right, redrawn as you type.
- **The document page** (`/studio/doc/<id>`) is the document as a reader
  sees it, with its ⚙ panel of typography and the rest, its contents, its glosses as a
  table and as flashcards, the documents that link to it, its exercises,
  **Build PDF**, and **Download ▾**, which also makes it
  [a page for a website](web-page.md).
- **The LLM prompt page** (`/studio/prompt`) is the text you give a
  language model so that its answer comes back already written in the
  dialect.

## A document's life, in short

1. Press **+ New** on the library. The editor opens on a starter page in
   the language the toolbox is set to: a guided tour of everything a
   document can hold, to keep what you need of and delete the rest.
2. Change the `title:` line — the title is the document's **name**, and two
   documents of one library cannot share one — and write. The preview on
   the right follows every keystroke.
3. **Save** (or Ctrl+S). The document now has a page of its own and a
   folder for its pictures and recordings.
4. **Save & view** shows it as a reader sees it. Tag it, open its glosses,
   answer its exercises, copy them into a deck.
5. **Build PDF** prints it — at a larger size for a reader with low vision,
   or in black and white for the photocopier, if you ask.

Or let a model write it: copy the prompt from **LLM prompt**, ask your
question, and bring the `.md` file it writes back in with **Upload .md /
.zip**.

## Where the documents live

Every document is a folder under `markdown/library/<language>/`, named by
an id made from its first title and six random characters
(`verbs-of-motion-3f9a1c`). The folder holds `source.md` — the Markdown,
which is the whole truth about the document — beside `meta.json` (its tags,
dates and build state), `images/`, `audio/` and `build/` (its PDF). The id
never changes, even when the title does; the folder moves to another
language's shelf only when a save changes the `target:` line.

```text
markdown/library/
  persian/
    verbs-of-motion-3f9a1c/
      source.md        the document
      meta.json        tags, dates, the last PDF build
      images/          its pictures
      audio/           its recordings
      build/           main.tex, main.pdf
  english/
    ...
```

You never need to open these folders: the library's **Backup** takes the
whole of it away as one zip, and **Load from backup** puts it back.

The same studio, with the same pages and the same buttons, also serves the
**notes** you write beside a book or a video — a second library kept with
that book or video: see [Notes beside books and videos](notes.md) — and a
file you open from anywhere on the computer, as a library of one document in a
temporary folder: see [Opening a file from your computer](open-files.md).

> **The studio works on its own too.** Parseh serves it at `/studio/`, but
> `markdown/app/server.py` can serve it alone, for hacking on it. Everything
> in this section is the same there, except what belongs to the hub: the
> clip tray, the **Working** pill in the corner and the list the **Stop server** button
> reads.
