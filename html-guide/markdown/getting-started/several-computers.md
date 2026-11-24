---
title: Several computers, one shelf
linkTitle: Several computers
weight: 9
description: Pairing two computers in Settings → Devices, what syncs and what does not, the choice when a thing changed on both and the diff of what it throws away, deletions, making one computer identical to another, undo for a day, jobs one computer lends another, and why sync is not a backup.
---

Each computer with Parseh installed holds its own shelf and works alone.
**Pair two of them, and they keep each other up to date**: a document you
wrote on the laptop is on the desktop the next time both are on, a book
narrated on the desktop is on the laptop. There is no server in between:
the two talk directly, peer to peer, whenever both are on and can reach
each other.

Everything is done in **Settings → Devices**, on the computer itself.

## Pairing

On one computer, open **Settings → Devices** and press **Show a code**. A
code such as `KP4-R7M` appears, with a QR code, the addresses this computer
answers at and its fingerprint. On the other computer, open the same page,
type the code and one of the addresses under **Type a code shown on another
computer**, and press **Pair**.

- **Fifteen minutes.** The code lasts that long and is used once; **Throw
  the code away** ends it sooner.
- **The fingerprint is optional.** Typed too, it makes sure the computer you
  reach is the one whose screen you are reading.
- **A name.** Each computer has one, which its partners show; change it
  under **This computer**.
- **Remove.** It forgets a partner: from that moment the partner is
  refused, until you pair the two again. The partner is told, if it
  answers within a few seconds: its own page then says this computer
  removed it, with a button to remove it there too. If it does not
  answer, it is removed here all the same, and the page says it was not
  told.

**A copied Parseh folder is not a new computer.** A copy carries the
identity of the computer it came from, so its partners cannot tell the
two apart, and pairing the copy with the original is refused. On the
copy, open **Settings → Devices** and press **This is a copy of another
computer: give it its own identity** under **This computer**. It gets a
new identity and keeps its name. Its list of partners is emptied, because
those partners belong to the original; pair the copy with them again. The
original is not changed. When Parseh sees that its identity was made on
another machine, the page says so and offers the same button, or **It is
the same computer** if you only moved your system to a new disk. It never
changes the identity on its own.

Both computers must reach each other — the same Wi-Fi, or a VPN. The
browser on a phone still opens a computer's pages as before
([From a phone or another computer](other-devices.md)); pairing is for
computers that each have Parseh installed.

## What syncs, and what does not

Sync compares **units**, and a unit is always taken whole:

- **A studio document.** Its text, its settings and its own pictures and
  recordings, together.
- **A note** beside a book or a video.
- **A video's own edited files.** The transcript, its times, the glosses,
  the phrase notes, together — never half of one with half of the other.
- **A book's source**, all its chapters together.
- **An exercise of a deck, and a deck's options.**
- **A prompt and a LaTeX theme.**
- **Your personal settings**, one at a time: the theme, the levels of each
  language, the reading places.

**This computer's own settings never sync**: the zoom, the port, the network
doors, the certificate, the job switches, what it holds and its partners.
Caches, downloaded models and dictionaries never sync either: each computer
fetches its own.

**Pictures, recordings and built pages** are copied whole; they never
change once written, so they cannot disagree. **Additions to a list** — a
clip added to the tray, a chunk flagged to review later, a card in the Anki
store — combine: each computer gets the other's.

**Exercise progress combines too.** Different exercises studied on the two
computers simply add up; the same exercise studied on both keeps the state
of the most recent answer. A personal setting or a reading place changed on
both keeps the most recent, with no question.

## The choice

A thing changed on **one** computer goes to the other, with no question.
When it changed on **both** since they last agreed, sync stops for that one
thing and asks. It never merges two versions.

- **Two answers only.** **Keep this computer's**, or **keep <partner>'s**.
  There is no "keep both".
- **Until you answer.** Each computer keeps working with its own version,
  and the rest syncs on.
- **Asked once.** The question comes up on whichever computer you open
  next, and is settled there for both. It is listed in **Settings → Devices** under
  **Questions waiting**, and a banner on the thing's own page — the document,
  the video, the book, the deck — leads to it.

**The choice page shows the diff before you press.** Under each of the two
buttons is what that button would throw away, as git would show it: lines
taken out in red, lines added in green. Text gets a line-by-line diff,
structured files the fields that differ, and a picture or a recording the
name of the file put aside.

**After you press, the same diff is offered as a file** to download, and it
stays in **Settings → Devices → Diff files** until you delete it. With it
you can copy back by hand whatever you wanted from the side you did not keep.

## Deletions are always asked

A deletion never travels without a question.

- **Deleted on the partner, untouched here.** Delete it here too, or restore
  it on the partner.
- **Deleted on the partner, edited here.** Send the edited version
  everywhere, or delete it everywhere.
- **Many at once.** Deletions from one sync — the clip tray emptied, say —
  come as one question with the list: delete them all, restore them all, or
  go through them one by one.

A deleted thing never comes back by accident from a partner that still had
it.

## Making this computer identical to another

Each partner in **Settings → Devices** has **Make this computer identical
to <partner>**. It is meant for a computer Parseh was not opened on for a
while, and for a computer just paired that holds nothing yet, which is
offered it as its first sync.

- **A summary first.** It says how many things will be replaced, added and
  deleted here, and lists this computer's own changes that will be lost.
  One button runs it.
- **It goes one way.** This computer takes the partner's state; the partner
  is not changed.
- **It touches the synced things only.** This computer's own settings, what
  it holds and its partners stay.
- **Questions and jobs.** Questions waiting here are answered in the
  partner's favour; jobs this computer had waiting are listed in the summary
  and cancelled.
- **Nothing lost silently.** The lost changes are written as one diff file,
  and everything it replaced is kept for a day.

## Undo for a day

Every version a sync replaced or deleted on a computer — a change that came
in, a choice, an answered deletion, "make identical" — is **kept on that
computer for one day**. **Settings → Devices → Kept for a day** lists them,
each with **Put back**. Put back, a version becomes this computer's change
and syncs like any other. After a day it is gone; the diff files stay.

## While you edit

A thing open in an editor — the studio editor, a video's phrase editor, a
note, an exercise's form, a deck's options — **is not touched by sync until
the editor is closed**. Its incoming change waits; if both sides changed,
the choice is asked once the editor closes. The other way round, while a
sync is writing a thing, its editor says *Sync is writing this just now* and
opens by itself a moment later.

## Out of date

A book's reader or a studio PDF is built from its source. When the source
changes through sync, the build is marked **Out of date** on its page, with
a button to build it again. Nothing rebuilds by itself.

## Jobs

Heavy work — transcribing with Whisper, building a book, estimating or
aligning times — can be **lent**: one computer sends the job, a partner that
can do it does it, and the result comes back through sync. Two switches in
**Settings → Devices → Jobs** decide it:

- **Send heavy jobs to paired computers.** A job this computer cannot do,
  or does slowly, goes to a partner that says it can.
- **Accept jobs from paired devices.** A partner's job runs here.

**Both are off on a fresh install**, and a computer with both off still
syncs. The page lists what this computer can run, and every job sent or
taken, with its state; a job not finished can be cancelled there.

## What this computer holds

A computer holds everything by default. Under **What this computer holds**
you can leave a language out: nothing is deleted here, but this computer
stops taking it. A thing left out shows as **on <partner>**, with a button
to fetch it, and from then on it is held here again.

## Sync is not a backup

**A deletion, once answered, travels to every paired computer.** A mistake
synced is a mistake on both. Keep backups as before — **Settings →
Backups** and each shelf's own Backup button ([Backups](backups.md)): a
backup is a copy that nothing changes afterwards, which sync is not.
