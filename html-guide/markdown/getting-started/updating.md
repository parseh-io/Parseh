---
title: Updating Parseh
linkTitle: Updating
weight: 3
description: Putting another version of Parseh in place of this one, from Settings — the newest release or a zip of your own, newer, older or the same again — and what it keeps, what it replaces, and what it says afterwards.
---

Parseh updates itself from a page of its own: **Settings → Updating
Parseh**, from the hub's **⚙ Settings** door. It puts another version in
place of the one you have, and keeps everything that is yours: the books,
the videos, the documents, the exercise decks with every answer ever given,
the Anki cards, the clips, the dictionaries and translation models, your
settings, the certificate and the devices you let in.

It works because every release carries a list of its own files, with a
checksum for each. The install holds that list for the version it is; the
zip holds the list for the version it brings. An update writes the files
the new list names, **deletes the files the old list names that the new one
does not**, and touches nothing that is in neither list — that is yours.

## Where a version comes from

- **The newest release.** *Check now* asks GitHub, in Parseh's own
  repository (`parseh-io/Parseh`), which release of Parseh is newest, and says
  whether it is newer than yours. (Parseh moved there in a0.4.4. A Parseh
  from before asks the old address, which GitHub sends on to the new one, so
  it finds the newest release too.) *Download* fetches its
  zip and checks it against the checksum published beside it. Ticking *Look
  once a day* makes Parseh ask by itself, once a day; it is off until you
  tick it. Asking sends nothing about you: one question, with Parseh's name
  and version on it. When the look finds a newer version, the page's door
  on **Settings** says so in its tags — *… is out* — and nothing is
  downloaded until you press *Download*.
- **A zip of your own.** *Choose file* takes a release's zip,
  `parseh-<version>.zip`, from wherever you have it: downloaded from the
  releases page, or built on this computer. Parseh checks every file in it
  against the zip's own list before it will use it, and says so in words
  when something is wrong.

Either way, nothing is installed yet. The version waits under **Ready to
install**, and *Throw it away* forgets it.

## Before anything happens: what it would do

**Ready to install** says, before you press anything:

- **Which way it goes.** Newer (↑), older (↓, *going back*), or the same
  version again (=). All three are allowed. Going back is how you escape a
  release that went wrong; installing the same version again puts back any
  file of Parseh's that was changed or damaged, and is how a build of the
  same number made after a fix is tried. The button says which it is:
  *Update to…*, *Go back to…*, *Install … again*.
- **The files.** How many of Parseh's files it writes, how many are new,
  which it deletes because the other version does not ship them, and how
  many are already as they should be.
- **Files changed by hand.** A file of Parseh's that was edited since it was
  installed is overwritten all the same — the copy you had is kept, and it
  is listed. So is a file of yours that happens to have the name of one the
  new version ships, under *Not Parseh's until now*: yours is kept in that
  update's backup, and comes back by itself as the next bullet says. The
  guide's own pages, which the installer compiles on
  this computer, are listed apart: they are compiled again afterwards.
- **Your own files, back.** When the version you install no longer ships a
  name under which an earlier update replaced a file of yours — going back,
  most often — your file goes back where it was, byte for byte, from the
  copy that update kept, with the same permissions and date, and the page
  lists it under *Yours, put back* (the report afterwards, under *Yours
  again*). Only the last three updates keep their copies: if the update that
  replaced it was longer ago than that, the page says plainly that your
  copy is gone.
- **The environment.** Whether the other version asks for packages this
  environment lacks; if it does, they are added before any file is
  replaced. Going back keeps the newer packages, and says so.
- **The shape of your data.** When going back would take a version that
  wrote something — a deck's schedule, a video's annotations, your settings —
  in a newer shape than the older version reads, the page says plainly what
  may not survive, and the button stays off until you tick *I understand,
  and want to go back anyway*. Then, before anything is replaced, a copy of
  the small files of your books, videos, decks and settings is kept (not the
  narrations and films), so that going forward again finds them. Going
  forward to a version that writes something in a newer shape keeps the
  same copy first, so that if the new version reads your files wrong, they
  can be put back as they were.

Pressing the button asks once more, in a sentence, and *Yes* starts it.

## While it runs

Parseh stops, replaces its files, compiles the guide, builds the readers
that need it, and starts again. The page shows each step as it goes — it is
answered by the update itself while Parseh is down — and comes back by
itself when Parseh is running again. A tab open elsewhere says *Parseh is
being updated* for that moment, and comes back too.

On Windows it happens in the window serve.bat opened, and Parseh starts
again in that same window.

## Afterwards

**The last update** stands at the top of the page: the version you have
now, what was written, deleted and overwritten, the files that had been
changed by hand, any file of yours that was put back, and *Back to where
you were*, which returns you to the
page you came to Settings from.

Every file an update replaces or deletes is kept first, in the folder
`.parseh-update/jobs/` inside Parseh's folder, one folder per update; the
last three updates are kept.

**If it is interrupted** — the power cut, the laptop closed, the program
killed — nothing is left half done: the next time Parseh starts, it first
finishes the update, or undoes it from the files it kept. A new version that
does not start is undone at once, and the old one started again.

**If it fails**, everything is put back as it was, and **The last update**
says in words which step it stopped in and what went wrong — *It stopped
while replacing Parseh's files: this computer did not let it change a
file.* Beneath, in small type, is the technical line behind it: it is what
to copy into a report of the fault.

## What it keeps

An update writes only the files that one of the two versions lists as its
own. Everything else in Parseh's folder is yours, and is exactly as it was
afterwards:

- **Your content.** `books/` with the narrations, `youtube/videos/` with
  your films, `markdown/library/`, `exercises/` with every answer in the
  decks' schedules, `youtube/anki/` and `clips/`.
- **The reading help.** `dict/`, `corpus/`, `mt/` and `components/` —
  gigabytes, perhaps, and nothing is downloaded again.
- **Speech to text.** `stt/`, the program and the models fetched on
  **Settings → Speech to text**: more gigabytes, and no update, forward or
  back, opens a file in it. **Going back to a0.4.0 leaves `stt/` exactly as
  it is**: that version has no page to remove it, so if you do not want the
  gigabytes while you are on it, take the folder off by hand — and fetch
  speech to text again on a version that has the page.
- **The ARASAAC pictograms.** `arasaac/`, the pictures and the words fetched
  on **Settings → Pictograms (ARASAAC)**: some 160 MB, and no update, forward
  or back, opens a file in it. A version that does not know the folder
  leaves it exactly as it is.
- **The TeX packages** Parseh got for its drawings, `texmf/`, and the
  drawings themselves, `markdown/latex/`.
- **Your settings.** `config/`: the preferences that follow you from
  device to device, who may reach Parseh and the devices you let in
  (`config/network.json`), the languages you added, the LaTeX themes
  (`config/latex.json`), the prompts you wrote for a chatbot
  (`config/prompts.json`, [Your own prompts](../studio/your-prompts.md)),
  and the daily look.
- **The certificate.** `.tls/`: no browser and no phone is asked to trust
  Parseh again, and a phone that was let in stays let in.
- **The environment.** `.runtime/`, where the installer made it, is
  changed only when the other version asks for a package it lacks.

**Copies of your small files.** An update that changed the shape of your
data, either way, copied the small files of your books, videos, decks and
settings before it replaced anything, and keeps that copy with the update
(the last three updates are kept). The page lists each copy under *Copies of
your small files*, with **Put these files back**, on the computer Parseh runs
on: it asks first, then writes each copied file back where it was. Each file
it writes over is kept beside the copy, so putting back can be undone too,
and a file made since the update is left as it is.

**On a phone that keeps books, videos or decks**, the app finds out the
next time it reaches the computer, and says so in one line: *Parseh was
updated to …*. Nothing reloads under your thumb, and nothing kept is lost;
*Change what is kept* calls the files the update changed *updated*, not
damaged, and fetches nothing again for them
([Browser and Mobile](mobile-mode.md#the-books)).

## Packages this Parseh lacks

Parseh runs with the packages its environment lists (the table in
[Installing Parseh](installing.md#what-it-needs)). Where one of them is
missing, the page lists it under **Packages this Parseh lacks**, and
**Add what is missing** adds it, with the lines it writes as it goes. It
takes a minute and needs the internet. A page that misses a package, such
as the narration panel without rapidfuzz or the Anki page without
zstandard, says so and links here. Where nothing is missing, the section is
not shown.

## From a phone

A phone that you let in may read the page, and may check for a new version,
but not install one: an update changes what Parseh runs, so it is started on
the computer Parseh runs on. The missing packages are added from there too. The page says so where the buttons would be.

## When the page says it cannot update

- **A Parseh from before.** A Parseh installed before it could update
  itself, or unpacked by hand, has no list of its own files, and an update
  will not guess which files are yours. Move into a fresh install once, as
  the next section says; from then on it updates from Settings.
- **A copy of the source code.** A git checkout is kept up to date by git,
  and the page leaves it alone. Updating from Settings is for a Parseh
  installed from a release's zip
  ([Installing Parseh](installing.md#getting-parseh)).

## Moving into a fresh install, once

Done once, by hand, for a Parseh that cannot update itself yet. It takes a
few minutes and downloads nothing of yours again.

1. **Stop Parseh**: **⏻ stop** on the hub.
2. **Rename its folder** — `Parseh` becomes `Parseh-old`, say.
3. **Get the new version**: download `parseh-<version>.zip` from the
   [releases page](https://github.com/parseh-io/Parseh/releases/latest)
   and unpack it. Put the folder it holds, `parseh-<version>`, where the old
   one was, and give it the old one's name.
4. **Move your things across.** From the old folder into the new one,
   each replacing the new one's empty folder of the same name — only those
   you have:
   - `books/`, `youtube/videos/`, `youtube/anki/`, `markdown/library/`,
     `exercises/` and `clips/`: your content;
   - `dict/`, `corpus/`, `mt/` and `components/`: the reading help's
     downloads;
   - `stt/`: speech to text's program and models;
   - `arasaac/`: the ARASAAC pictograms;
   - `texmf/`: the TeX packages Parseh got for its drawings;
   - `config/`: your settings and the devices you let in;
   - `.tls/`: the certificate, so that no browser and no phone is asked to
     trust Parseh again;
   - `.runtime/`: the environment, where the installer made it, so that it
     is not made again — it works because the new folder is where the old
     one was, under the same name.

   A name that starts with a dot is a hidden folder: show them with
   **Ctrl+H** in most Linux file managers, **⌘⇧.** in the Finder, and
   **View → Show → Hidden items** in Windows' File Explorer.
5. **Run the installer** in the new folder, as the first time
   ([Installing Parseh](installing.md)): it adds what the environment
   lacks, compiles this guide and builds your books' readers.
6. **Start Parseh** as you always do. The foot of the hub names the new
   version, and your shelves are as you left them. Delete `Parseh-old` once
   you are sure.

A language you added yourself with `lib/newlang.py` before this lived in
the old `lib/languages.json`: copy its row into `config/languages.json`, and
its `lib/lang/<code>.tex` and `docs/lang/<code>.md` across
([Adding a language](../lookup-and-languages/adding-a-language.md)).
