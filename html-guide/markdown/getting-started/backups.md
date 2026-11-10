---
title: Backups at a glance
linkTitle: Backups
weight: 9
description: The four shelves — books, videos, studio documents, exercise decks — each with a Backup button and a Load from backup button, what each backup holds, and what none of them does.
---

Parseh keeps four shelves of your own, and each has a pair of buttons on
its own page: one that downloads the whole shelf as a single zip, and one
that puts such a zip back. Nothing else is needed to move your work to
another computer, or to keep a copy of it somewhere safe.

## The four shelves

| Shelf | Where the buttons are | Back it up |
|---|---|---|
| **Books** | the books' library, `/books/`, panel **⇩ The whole shelf** | **Backup every book** |
| **Videos** | the video index, `/youtube/`, panel **⇩ The whole shelf** | **Backup every video** |
| **Studio documents** | the studio's library, `/studio/`, in the bar's **Backup ▾** menu | **Backup the whole library** |
| **Exercise decks** | the exercise decks, `/exercises/`, at the top | **Backup** |

Beside each of them, on every shelf, is **Load from backup**, which puts
such a zip back.

A backup is an ordinary download: the browser saves it where it saves
everything. While the server packs it — a shelf of narrated books can take
a while — the [Working… indicator](working-indicator.md) says so, on that
page and on the hub, and it does the same while a backup goes back up.

## What each one holds

| Shelf | The backup holds | It leaves out |
|---|---|---|
| **Books** | one bundle per book, each the book's *everything but the recording* zip: its text and chapters, its notes, its timings and alignment | the recordings themselves, `audio/` |
| **Videos** | one bundle per video: its glossed transcript, its notes, and a film of your own with it | nothing: a YouTube video never had a file here, only its address |
| **Studio documents** | every document with its record — its id, its tags, its dates — its pictures and recordings, and its built PDF | nothing |
| **Exercise decks** | every deck with its own id, its settings, every picture and recording it has, and its scheduling — every answer you ever gave | nothing |

**A book's recordings are left out to keep the backup small**: a narration
is hundreds of megabytes. Copy each book's `audio/` folder yourself; after
restoring the backup, put it back under `books/<language>/<slug>/` and
build that book again — the **build** button on its card on the library
page (**rebuild**, for a book that already has a reader), or **rebuild the
reader** in the reader — and the recording plays again. Its timings came
back with the book, so it is aligned as before. A single book can also be
downloaded *with* its recording, as *all of it*, from its reader.

**A shelf of books or of videos is a zip of zips**: each inside is the very
bundle one book or one video downloads as, so a backup can be taken apart
and a single book put back by itself, through the **Bring a book back**
panel beside the shelf's (**Bring a video back** for a video).

## Putting one back

**What is already there is kept, and named.** Loading a backup never
quietly overwrites something newer: a book, a video, a document or a deck
that is already on the shelf is left as it is, the page says which (the
studio, how many), and only then offers to replace it — **Replace them**
or **Keep mine**, on every shelf. A backup is usually older than what you
have, and a restore is not a merge.

**It comes back as itself.** A document keeps its id and the links that
point at it, a deck keeps its scheduling, so what you restore carries on
where it was. In the studio, where a link names the document it leads
to, two documents cannot share a name: a document coming back under a name
another one already has opens **This name is already in use**. Rename the
one already there, the one coming back, or both, and press **Use these
names** — every link to a renamed document follows it to its new name —
or **Cancel**, and nothing is restored.

**An exercise deck's backup is not its Export.** A deck's own **Export ▾**,
on its page (or in the **⋯** menu of its card on the decks page), is for
giving a deck away: **Without scheduling** leaves the answers behind so
that whoever gets it starts new, and it carries only the pictures and
recordings its exercises name. The backup is for keeping: the deck comes
back as the same deck, with every file it had and every answer.

## What no backup holds

- The Anki card store, `youtube/anki/`: your cards go to Anki and come back
  from it through the **⇆ Anki** door.
- The clip tray: the recordings and pictures waiting for a card. A card, a
  deck or a document that uses one keeps its own copy.
- The dictionaries, sentences and models fetched on **Settings → Reading
  help**: fetch them again there.
- Your settings and the devices you let in, `config/`: a Parseh on another
  computer starts with its own, and a phone is let in there once more. The chunks
  you flagged to [review later](../books/review-later.md) and the names you gave the
  levels live there too, in `config/prefs.json`, beside the places you were reading. A
  LaTeX theme travels on its own: **Export** on **Settings → LaTeX
  drawings**, and **Import a theme…** on the other computer.
- The TeX packages Parseh got, `texmf/`: get them again on **Settings →
  LaTeX drawings**.
- Speech to text's program and models, `stt/`: gigabytes of other people's
  work; get them again on **Settings → Speech to text**.
- The ARASAAC pictograms, `arasaac/`: some 160 MB of other people's pictures,
  under a licence that asks for a credit; get them again on **Settings →
  Pictograms (ARASAAC)**.
- What each browser remembers: the language, the sizes and the levels shown, the page
  zoom.
- What can be built again: the readers, the library page, the PDFs of the
  books, the LaTeX drawings (`markdown/latex/`), made again from their
  blocks.

None of it is needed to update Parseh: [an update from
Settings](updating.md) keeps every shelf, and everything in this list, as it
is. [Where everything lives](where-things-live.md) has the folders all of
these are kept in.
