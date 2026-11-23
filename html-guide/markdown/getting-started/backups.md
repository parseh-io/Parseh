---
title: Backups at a glance
linkTitle: Backups
weight: 9
description: The four shelves, each with a Backup button and a Load from backup button; Settings → Backups, with a backup of your settings and one backup of everything for a new computer; the day of each last backup; what each holds, and what none does.
---

Parseh keeps four shelves of your own, and each has a pair of buttons on
its own page: one that downloads the whole shelf as a single zip, and one
that puts such a zip back. Beside them, **Settings → Backups** has two more:
a backup of **your settings**, and **one backup of everything** for moving to
a new computer. Beside every Backup button is the day it was last pressed —
*last backup: 3 days ago*, or *never backed up*.

## The four shelves

| Shelf | Where the buttons are | Back it up |
|---|---|---|
| **Books** | the books' library, `/books/`, panel **⇩ The whole shelf** | **Backup every book** |
| **Videos** | the video index, `/youtube/`, panel **⇩ The whole shelf** | **Backup every video** |
| **Studio documents** | the studio's library, `/studio/`, in the bar's **Backup ▾** menu | **Backup the whole library** |
| **Exercise decks** | the exercise decks, `/exercises/`, at the top | **Backup** |

Beside each of them, on every shelf, is **Load from backup**, which puts
such a zip back. **Settings → Backups** lists the four again, each with its
Backup button and its day, so that one page says what was backed up and
when.

A backup is an ordinary download: the browser saves it where it saves
everything. While the server packs it — a shelf of narrated books can take
a while — the [Working… indicator](working-indicator.md) says so, on that
page and on the hub, and it does the same while a backup goes back up.

**The day is counted when the backup has been sent whole**, not when the
button is pressed: a download that failed half way is not a backup. The days
are kept by the computer Parseh runs on, so every device shows the same ones.

## Settings → Backups

### Your settings

**Backup your settings** downloads what Parseh keeps for you in its
`config/` folder, and that no shelf holds:

- **Reading places, flags, levels.** Where you were in each book, the chunks
  you flagged to [review later](../books/review-later.md), the settings that
  follow you from device to device (the speed, the pause, the theme…) and the
  names you gave the levels.
- **Your prompts.** The ones you wrote for a chatbot.
- **Your languages.** The languages you added, with their files: the LaTeX
  file a book in that language is built with, its conventions and its lookup
  rules.
- **Your LaTeX themes.** With the default one and how long a drawing may take.
- **Linguistic analysis.** Where the optional analyzers are used.
- **Speech to text.** Which model for which language, and the checks for
  suspect words. The models themselves are fetched again on the new computer.

**Left out, because they belong to the computer and not to you:** who may
reach Parseh, its port, its certificate and the devices you let in with their
tokens (a new computer decides its own, and a phone is let in there once
more); what phones keep, which is written by this computer's own paths; what
the updater last found; the paths of this computer's own model for LM
likelihood; the LLM connection of a0.6.2 and before, no longer read; and the
days of this computer's own backups. The page lists them too, under **What
is left out, and why**.

**Load from backup merges; it never overwrites without asking.** Choosing a
settings backup first shows, store by store, what loading it would do, and
writes nothing:

- **Added.** What the backup has and this computer has not comes in.
- **The same.** What both have alike is left alone.
- **Decided by the later change.** A reading place, a setting, a level's
  name: the one changed last wins, as between two of your devices — a place
  you reached here after the backup was made stays.
- **Flags to review later.** They are joined, and a removal is remembered: a
  flag you removed here after the backup was made stays removed, and one the
  backup had removed goes.
- **Your choice.** A prompt, a language, a LaTeX theme or a choice that
  differs and has no such rule is offered with **keep yours** and **take the
  backup's**; yours is kept unless you pick the backup's.

Press **Load these** to load it, or **Cancel**. A prompt whose name you have
used already for another comes in as *name (2)*. A language Parseh itself now
has is left out, and said: Parseh's own is the one read.

### Everything, for a new computer

**Backup everything** downloads one zip holding the four shelves' own
backups, your settings, the **Anki card store** and the **clip tray** — the
two that no shelf holds: a card that never reached Anki, or a clip not yet
on a card, exists nowhere else. Of the card store, the decks Parseh built for
Anki and the files dropped in its inbox are left out: they are made again, or
are copies of something you have.

On the new computer, install Parseh, open **Settings → Backups** and press
**Load everything from a backup…**. Your settings go back first — a book, a
deck or a card in a language you added needs that language — then the
books, the videos, the studio, the decks, the cards and the clips, each
through its own Load from backup. The answer says, part by part, what was
put back and what was already there.

**What is already there is kept and named**, as on every shelf, unless
**Replace** is ticked. Your settings are merged either way, and those that
differ with no rule of their own are kept as they are and listed under
**Your settings**, to take the backup's for any of them.

**A backup is checked whole before anything is put back.** Every file in it
is listed with its checksum; a file that does not match, a store that does
not read, or a backup made by a newer Parseh is refused in words, and nothing
at all is loaded.

**Loading a backup is done on the computer Parseh runs on.** Another device
that has been let in sees the page, the days and the Backup buttons, and a
lock where the Load buttons are.

## What each one holds

| Backup | It holds | It leaves out |
|---|---|---|
| **Books** | one bundle per book, each the book's *all of it* zip: its text and chapters, its notes, its recordings in `audio/` with their timings and alignment | its reader and its PDF, which **build** makes again |
| **Videos** | one bundle per video: its glossed transcript, its notes, and a film of your own with it | nothing: a YouTube video never had a file here, only its address |
| **Studio documents** | every document with its record — its id, its tags, its dates — its pictures and recordings, and its built PDF | nothing |
| **Exercise decks** | every deck with its own id, its settings, every picture and recording it has, and its scheduling — every answer you ever gave | nothing |
| **Your settings** | the six stores listed above, and your languages' files | what belongs to the computer, listed above |
| **Everything** | all five above, the Anki card store and the clip tray | what each of them leaves out |

**A book comes back with its recordings**, in the backup of everything
too: every recording in its `audio/` folder, its timings, its alignment
review. A narration is hundreds of megabytes, so a shelf of narrated books
makes a large backup. A book that came back is built from its card on the
library page — **build** — like any book put back; the recording then plays,
aligned as before.

**Parseh packs a backup inside its own folder**, in `.tmp/`, and never in
the computer's temporary folder, which on many computers is small and held
in memory. The file is gone again once the backup has been sent or loaded,
and anything a stopped Parseh left there is cleared the next time it
starts, once it is a day old. Make sure the disk Parseh is on has room for
the backup a second time while it is being made.

**A shelf of books or of videos is a zip of zips**: each inside is the very
bundle one book or one video downloads as, so a backup can be taken apart
and a single book put back by itself, through the **Bring a book back**
panel beside the shelf's (**Bring a video back** for a video).

## Putting a shelf back

**What is already there is kept, and named.** Loading a backup never
quietly overwrites something newer: a book, a video, a document or a deck
that is already on the shelf is left as it is, the page says which (the
studio, how many), and only then offers to replace it — **Replace them**
or **Keep mine**, on every shelf. A backup is usually older than what you
have, and a restore of a shelf is not a merge.

**It comes back as itself.** A document keeps its id and the links that
point at it, a deck keeps its scheduling, so what you restore carries on
where it was. In the studio, where a link names the document it leads
to, two documents cannot share a name: a document coming back under a name
another one already has opens **This name is already in use**. Rename the
one already there, the one coming back, or both, and press **Use these
names** — every link to a renamed document follows it to its new name —
or **Cancel**, and nothing is restored. (Loading everything cannot ask: the
studio's part is then refused and named, and the studio's own **Load from
backup** settles the names.)

**An exercise deck's backup is not its Export.** A deck's own **Export ▾**,
on its page (or in the **⋯** menu of its card on the decks page), is for
giving a deck away: **Without scheduling** leaves the answers behind so
that whoever gets it starts new, and it carries only the pictures and
recordings its exercises name. The backup is for keeping: the deck comes
back as the same deck, with every file it had and every answer.

## What no backup holds

- The dictionaries, sentences and models fetched on **Settings → Reading
  help**: fetch them again there.
- Who may reach Parseh and the devices you let in, `config/network.json`: a
  Parseh on another computer starts with its own, and a phone is let in there
  once more.
- The TeX packages Parseh got, `texmf/`: get them again on **Settings →
  LaTeX drawings**.
- Speech to text's program and models, `stt/`: gigabytes of other people's
  work; get them again on **Settings → Speech to text**.
- The ARASAAC pictograms, `arasaac/`: some 160 MB of other people's pictures,
  under a licence that asks for a credit; get them again on **Settings →
  Pictograms (ARASAAC)**.
- The optional analyzers, `analysis/`: get them again on **Settings →
  Linguistic analysis**; your choice of where they are used is in your
  settings' backup.
- What each browser remembers: the language, the sizes and the levels shown, the page
  zoom.
- What can be built again: the readers, the library page, the PDFs of the
  books, the LaTeX drawings (`markdown/latex/`), made again from their
  blocks.

None of it is needed to update Parseh: [an update from
Settings](updating.md) keeps every shelf, and everything in this list, as it
is. [Where everything lives](where-things-live.md) has the folders all of
these are kept in.
