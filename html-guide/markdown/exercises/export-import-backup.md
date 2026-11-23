---
title: Export, import and backup
weight: 10
description: A deck as a zip, with or without its scheduling; importing one; every deck at once in a backup, and putting it back; where decks live on the disk.
---

A deck is yours alone: no deck under `exercises/` is kept in git, so a deck
moves from one machine to another — or to another person — as a zip file.
There are two kinds of zip, for two different jobs:

- **An export** is one deck, made to be **given**: to your other computer,
  or to a friend who should start it fresh.
- **A backup** is every deck at once, made to be **put back**: after a new
  installation, or on the day something went wrong.

## Exporting a deck {#exporting-a-deck}

**Export ▾** on a deck's page — or the **⋯** menu on its card on the decks
page — offers two versions:

| Choice | File | For |
|---|---|---|
| **With scheduling** | `exercises-Everyday Persian-with-scheduling.zip` | your own other machine: every exercise keeps its state and every answer you gave |
| **Without scheduling** | `exercises-Everyday Persian.zip` | somebody else: every exercise arrives as new |

The file is called by the deck's own name, in whatever script it is written:
a deck called «واژه‌ها» comes down as `exercises-واژه‌ها.zip`. The browser
saves the file as it saves any download, and the **Working…**
pill in the corner says *Exporting the deck …* while Parseh packs it.

Both hold the same things:

- `parseh-exercise-deck.json`, the manifest: the deck's id, name, language
  and options;
- every exercise, under `items/`, with its tags and where it came from;
- the pictures the exercises use, under `images/`, and the recordings,
  under `audio/`;
- and, in the version with scheduling, `schedule/`: each exercise's state
  and its whole history of answers.

Only the pictures and recordings an exercise names travel: a file the deck
holds but no exercise uses any more stays behind. (A backup, below, takes
everything.)

## Importing a deck {#importing-a-deck}

**Import deck…** on the decks page takes such a zip. Choose the file, and a
dialog asks one question:

- **Keep the scheduling saved in the file** — ticked by default. *Unticked,
  every exercise starts again as new.* A zip exported without scheduling
  starts new whatever the tick says.

**Import** adds the deck under its own name and language, with its options,
and says what came in: *Imported “Everyday Persian”: 8 exercises, with its
scheduling* (or *all new*). While a large file goes up, the **Working…**
pill says *Importing the deck …*.

Each exercise is checked on the way in, exactly as one added by hand: one
that is not a single sound exercise in the deck's language is skipped and
counted — *8 exercises, 1 skipped (not a valid exercise)* — and the rest
still come in.

### A deck that is already here

A deck keeps its **id** through export and import, so Parseh knows when the
zip is a deck you already have — your own deck coming back from the other
machine, say. Then it asks:

*This deck is already here* — *A deck with this id is already here:
"Everyday Persian". Replace it moves the deck that is here to
exercises/.trash/ and puts the imported one in its place; a copy keeps
both.*

- **Replace it** moves the deck that is here to `exercises/.trash/` (so
  nothing is lost) and puts the imported one at the same address: bookmarks
  of it keep working.
- **Import as a copy** keeps both. The new one gets an id of its own and
  its name followed by *(copy)*: `Everyday Persian (copy)`.
- **Cancel** imports nothing.

### What an import refuses

The whole file is refused, with the reason, when it is not a deck export:

- a file that is not a zip at all — *this is not a deck export: the file is
  not a zip*;
- a zip holding anything but a deck's files — *unexpected entry in the zip:
  …* (a [backup](#backing-up-every-deck) is such a zip: it goes to **Load
  from backup**, not here);
- a file under `audio/` that is not a recording, or one larger than 30 MB;
  a picture larger than 15 MB;
- more than 512 MB in all, once unpacked, or more than 20,000 files.

(The studio run on its own, without the rest of Parseh, also refuses an
upload larger than 32 MB.)

## Backing up every deck {#backing-up-every-deck}

**Backup**, at the top of the decks page, downloads every deck on the shelf
as one zip, `exercises-backup-20260921-1427.zip` (the date and time it was
made). The **Working…** pill says *Packing the backup of every deck* while
it is being made.

A backup is not a pile of exports. It is made to be put back exactly:

| | Export | Backup |
|---|---|---|
| How many decks | one | all of them |
| The scheduling | your choice | always |
| Pictures and recordings | the ones the exercises name | every one the deck holds, named or not |
| The deck's id and address | the id; the address is made afresh | both, as they were |
| Put back with | **Import deck…** | **Load from backup** |

A picture no exercise names today is often one you unlinked yesterday and
will want tomorrow: an export leaves it out on purpose, a backup must not.
The decks in `exercises/.trash/` are not backed up.

## Loading a backup

**Load from backup** takes the zip that **Backup** made. The button says
**Restoring…** while the file goes up, and the **Working…** pill says
*Restoring the decks from …*. A shelf of decks with their recordings can be
large: Parseh writes the file to the disk as it arrives rather than holding
it in memory, and takes a backup of up to 512 MB once unpacked.

Every deck in the backup that is **not** here is put back as it was — its
id, its address (or a free one, if another deck has taken it since), its
options, its pictures and recordings, and all its answers.

A deck that **is** already here — the same id, in the same language — is
**kept** as it is, and the page asks about it:

*2 decks already here* — the names — *left exactly as they are. Replacing
them puts the backup's copy in their place, and anything written or studied
since the backup was made is lost. The backup is sent again.*

- **Keep mine** leaves them as they are. This is usually right: the backup
  is usually older than the deck you have.
- **Replace them** sends the backup again and puts its copy in their place;
  each deck replaced is moved to `exercises/.trash/` first.

The message at the end counts what happened: *3 decks restored, 2 left as
they are*. A deck of the backup that cannot be read is left out and said.

**Load from backup** takes only a backup: given a single deck's export it
answers *unexpected entry in the zip: 'parseh-exercise-deck.json'* — that
zip goes to **Import deck…**.

## Where decks live {#where-decks-live}

Each deck is a folder inside Parseh, under its language's folder:

```text
exercises/
  persian/
    everyday-persian/
      deck.json            its id, name, language and changed options
      items/<id>.json      one exercise each: its markdown, its footnotes, its tags, where it came from
      schedule/<id>.json   its state and every answer (no file while it is new)
      images/              the pictures its exercises and cards show
      audio/               the recordings its cards play
  italian/
    italiano-primi-passi/
  .trash/                  deleted and replaced decks, never emptied by Parseh
```

Everything is small JSON files, one per exercise and one per exercise's
schedule, so an interrupted write can lose at most the answer being written,
and a deck can be read — and if need be mended — with a text editor. Git
ignores everything under `exercises/` except its `README.md`: decks are
your study, not the toolbox's code, and they travel by their export or by a
backup, never by git.

A deck in `exercises/.trash/` comes back by moving its folder back where it
was. Its name in the trash says where that is: `persian--everyday-persian--20260921-143012`
is the deck `everyday-persian` of the `persian` folder, deleted on 21
September 2026 at 14:30:12.
