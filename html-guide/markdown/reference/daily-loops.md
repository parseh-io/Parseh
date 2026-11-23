---
title: The daily loops
weight: 5
description: The routines most days are made of — reading, watching, making cards, syncing with Anki, studying, writing, adding — each in a few steps.
---

Most days with Parseh are one of a handful of routines. Here they are in
order, a few steps each, with the buttons named as the pages name them.
The sections of this guide explain every step at length; this page is
the map.

## Starting and stopping

1. Start Parseh: `./serve.sh` on Linux, a double-click on
   **Parseh.command** on a Mac, on **serve.bat** on Windows.
2. Open `https://localhost:7654/` — or, from a phone or another computer
   on your network, the address Parseh printed when it started. The first
   time, each browser warns about the certificate: accept it once.
3. On the hub, pick your language's chip: every door then opens on that
   language, and counts what it holds in it.
4. When you are done, **⏻ stop**. If something is still running, it tells
   you what first; wait for the **Working…** pill to go, then stop.

## Reading a book

1. **Books** on the hub, then the book's card.
2. Play the narration, and the page follows the voice. A click on a chunk
   plays it; **hover** puts the gloss in a cloud over the chunk you are
   reading instead of between the lines.
3. A word you want to keep: Alt-click or Ctrl-click it, and the card sheet
   opens already filled in — to **Anki**, to an **exercise deck**, or as
   **markdown** for a document.
4. A chunk nobody has glossed yet: switch on **dictionary** in the header
   (it is there once **reading help** has a dictionary for the language).

## Watching a video

1. **Videos** on the hub, then the video.
2. The transcript runs under the video, the line being spoken marked; a
   click on a line replays it, and the gloss is where you hover.
3. The same Alt-click makes a card, with the caption as its context and
   the word's own sound cut with **cut the audio…** — from the film, in
   any browser, for a film on this machine; for a YouTube video, recorded
   from the tab as it plays, which only Chrome and Edge on a computer can
   do.

## Making cards and taking them to Anki

1. Make cards as you read and watch (above): they wait in Parseh's card
   store.
2. **If you have edited anything inside Anki since the last time, sync
   first.** Skipping this is the one way to lose an edit.
3. Build the deck: **build .apkg** in a card sheet (with the deck chosen
   in it), or step 5 of the sync. The deck downloads, rebuilt from the
   store; in Anki, **File → Import…** it. Cards are matched by their
   identifier, so the ones already there are updated in place and keep
   their history.

## After a session of editing inside Anki

1. In Anki, **File → Export…**, *Anki Deck Package (.apkg)*, with **Include
   media** ticked if your cards have pictures or recordings.
2. **Anki** on the hub: drop the export on step 2.
3. **Preview the changes** (step 3), read them, then **Apply to the
   store** (step 4).
4. Step 5: download the rebuilt deck and import it into Anki. Five
   minutes, and the two sides agree again.

## Studying exercises

1. **Exercises** on the hub: each deck's card says how many exercises are
   new, learning and due for review.
2. Open the deck and **Study now**. Answer and **Check** (or Enter), or turn
   a flashcard with **Show answer**; **⤢ Enlarge** shows a card as large
   as the window holds.
3. Rate it — **Again**, **Hard**, **Good**, **Easy**, or the keys 1 to 4 —
   and the next one comes. When nothing is left, the page says when the
   next one is due.
4. To go over some exercises without touching their schedule, select them
   on the deck's page and **Cram exercises**.

## Writing in the studio

1. **Studio** on the hub. **LLM prompt**: pick the target language, type
   your question, **Copy prompt + question**, and paste it to any model.
2. The model writes a `.md` file: **Upload .md / .zip** it in the library
   — or **Paste LLM answer** when the model answered in the chat.
3. Or write your own: **+ New** opens a page that shows everything a
   document can hold in your language; keep what you need, **Save & view**.
4. Read it, tag it, and **Build PDF** when you want paper — with **PDF
   options ▾** for large print or black and white.
5. Its exercises go to a deck with **+ Deck**, or all at once with **+ Add
   all exercises**.

## Adding a video

1. **Add a video** on the video index. Say where it is — **From YouTube**
   or **A film already on this machine** — and who writes the glosses.
2. **An LLM — I paste the answer back**: copy the prompt the page makes,
   paste it to any model, paste the answer back; it is checked before
   anything is written.
3. **Nobody — I gloss it in the player**: the video opens with every
   caption cut into chunks and every gloss blank, and you fill them in
   with the pencil.

## Adding a book

1. **Add a book** on the library page, and say what you are doing.
2. **Write it here, by hand**: paste a chapter; the book is drafted with
   the text divided and every gloss blank, and you gloss it in the reader.
3. **Add to a book already here**: more text onto the end of a book on
   the shelf, as a new chapter or more of the last one.
4. **Let an agent make it**: choose the original with the file picker and
   press **make the book's folder**; open that folder in the agent you use
   and tell it *read AGENTS.md and begin*. The book is on the library,
   marked **being made**, and its reader has a making panel to look at it
   now, to write what to change from now on, and to **finish** it when the
   agent is done.

## Glossing with an LLM

1. In a book's reader, **gloss with an LLM** in the header (or **gloss
   around here with an LLM…** in a chunk's sheet); in a video's player,
   **gloss with an LLM** in the bar, then a click on the first caption and
   one on the last.
2. Pick the stretch, and **copy the prompt**. Paste it into any chatbot.
3. Paste its whole reply into **the LLM's answer** and press **fill from
   the answer**. Only chunks nobody has glossed are filled; the report says
   what was filled, kept and dropped.
4. A gloss you want written again: **delete gloss** in its sheet or ✎
   form first, then copy the prompt.

See [Glossing a stretch with an LLM](../books/glossing-with-an-llm.md) and
[Glossing captions with an LLM](../videos/glossing-with-an-llm.md).

## Writing one yourself, in the files

1. **download** in the reader's header, or **⤓** in the player's bar: the
   authored files as one zip.
2. Work on them in a text editor — this is where find-and-replace across
   a chapter belongs — and zip the folder again.
3. Drop the zip on **Bring a book back** at the foot of the library (or
   **Bring a video back** on the video index). It is checked before it is
   installed; a book then waits on the shelf for its **build** button.

## Keeping everything safe

Each shelf has a **Backup** and a **Load from backup**: the studio's
library, the books (**Backup every book**), the videos (**Backup every
video**) and the exercise decks. Loading one brings each item back as
itself, and what is already there is kept unless you choose to replace
it.

What they carry with them:

- **Backup every book** carries every book's narration: each book is
  packed as **all of it**, its recordings and their timings included.
  After a restore, press **build** on the book's card in the library.
- **Backup every video** carries a film kept on this machine; a
  YouTube video's picture and sound stay on YouTube.

Your Anki cards go to Anki. [The file layout](file-layout.md) says where
everything is on the disk.

## Updating Parseh

1. **⚙ Settings → Updating Parseh**, on the computer Parseh runs on.
   **Check now**, then **Download** the version it names — or choose a
   release's zip you already have.
2. Read what **Ready to install** says: which way it goes, what it writes
   and deletes, any file changed by hand. Press **Update to…** and **Yes**.
3. Wait for the page to come back by itself. The update adds what the
   environment lacks, compiles the guide and rebuilds the readers; **The
   last update** at the top says what it did, and **Back to where you
   were** returns you to your page.
4. [What changed, version by version](whats-new.md) says what is new.

A Parseh installed before it could update itself moves into a fresh install
once, by hand ([Updating Parseh](../getting-started/updating.md#moving-into-a-fresh-install-once)).
And whenever a page says the environment lacks a package, run the installer
again — `./install.sh`, **Parseh.command** or **install.bat** — which adds
what is missing, and start Parseh again.
