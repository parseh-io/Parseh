---
title: Getting started
weight: 10
description: Install Parseh, start and stop it, reach it from a phone, and find your way round the hub.
---

Parseh is a toolbox for learning a language the way Ilya Frank's reading
editions teach one: the text cut into small chunks, each chunk glossed, and
the narration playing in step, so that you read, hear and understand at
once. It runs on your own computer as one small web server, and you use it
in a browser — on that computer, or on a phone or a laptop that can reach
it.

It teaches twelve languages — Persian, Arabic, Italian, Japanese, French,
German, Turkish, English, Hindi, Spanish, Chinese and Catalan — right to left for
Persian and Arabic, and set vertically for Japanese and Chinese when you
want them so.

## What is behind the doors

The first page Parseh opens on is the **hub**, and everything is behind one
of its doors:

| Door | What is behind it |
|---|---|
| **Books** | reading editions: a book in small chunks, each with its gloss, the audiobook playing in step |
| **Videos** | a YouTube video, or a film of your own, with its whole transcript underneath and every phrase glossed |
| **Studio** | notes on the language in a small Markdown dialect, read on screen or built into a PDF |
| **Exercises** | decks of the studio's exercises, studied like Anki cards: each comes back when it is due |
| **⚑ Review later** | the chunks you flagged while reading or watching, to go back to, test yourself on, or turn into cards |
| **⇆ Anki** | the card store the books and the videos write cards into, and the way to and from Anki |
| **✂ The clip tray** | the recordings and pictures cut for cards, waiting to go onto one |
| **🔍 Reading what nobody has glossed** | dictionaries, and the rest of what reading an unglossed text takes |

What you read through them is yours: Parseh comes with the doors and
nothing of anybody's, so its shelves are empty until you fill them.

## The short version

1. **Get it, and install it, once.** Download the newest release's zip,
   `parseh-<version>.zip`, from the
   [releases page](https://github.com/parseh-io/Parseh/releases/latest)
   and unpack it where Parseh will live. Then, on Linux, run `./install.sh`
   in that folder; on a Mac, double-click **Parseh.command**; on Windows,
   double-click **install.bat**. [Installing Parseh](installing.md) says
   what that does and what it needs.
2. **Start it.** On Linux, `./serve.sh`; on a Mac, **Parseh.command** again;
   on Windows, **serve.bat** — whose first run is a
   [setup wizard](windows-wizard.md). See
   [Starting and stopping](starting-and-stopping.md).
3. **Open it** at `https://localhost:7654/`. Your browser warns you once
   about the certificate, which Parseh made for itself: accept it, and it
   never asks again. From a phone, use one of the other addresses Parseh
   prints — [From a phone or another computer](other-devices.md).
4. **Pick a door** on [the hub](the-hub.md).
5. **Update it** from **⚙ Settings → Updating Parseh**, when a new version
   comes out: your books, decks, dictionaries and settings stay as they are.
   [Updating Parseh](updating.md) says how.

When you are done, the **⏻ stop** button at the top of the hub stops the
server; while it is still working on something — a build, an upload — it
tells you first.

## Where to go from here

The other sections of the guide take each door in turn: the
[books](../books/index.html), the [videos](../videos/index.html), the
[studio](../studio/index.html), [its Markdown](../dialect/index.html) and
[the exercises written in it](../dialect-exercises/index.html), the
[exercise decks](../exercises/index.html),
[cards and Anki](../cards-and-anki/index.html),
[looking words up, and the languages](../lookup-and-languages/index.html),
and the [reference](../reference/index.html), where the commands are and
what a message means.

The pages of this section, below, go through the first steps one at a
time: installing and starting, the hub, the two interfaces, the ⚙ settings
of a page, the Working… indicator, where everything lives on the disk, the backups, and this guide
itself.
