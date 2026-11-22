---
title: A book made by an agent
weight: 3
description: Watching a book grow in the library while an agent you choose writes it — the making panel, the asks you steer it with, and Finish.
---

An edition made the way the first ones were — an agent recovering the text,
deciding the chapters and annotating ten paragraphs at a time, with a checker
after every batch — takes days. So the book does not wait for the end to
appear: it is on the library from the first minute, marked **being made**,
and everything that used to be done in a terminal is a button. This page is
about what happens after **make the book's folder** on the add page ([Adding a
book](doc:Adding a book)): opening the folder in an agent, watching the book
grow, steering it, and finishing it.

**An Arabic book in a dialect** says so on the add page, in **Written in**
beside the language, as any book does. The choice is written into the
folder's `book.json` (`variety`), and the instructions and the skill's
request tell the agent the text is Egyptian Arabic (say): to gloss each
word as that dialect uses it and to write its transliteration as it is said
there. They never offer the agent the linguistic analysis for it, which
reads standard Arabic. Changed later in the reader's dictionary panel, the
instructions are written again at once, and the panel says to tell the
agent to read them again.

**Parseh never starts an agent.** You use whichever you like — a coding
assistant in its own app, in a terminal or in an editor: anything that works
inside a folder — and Parseh does not name one as *the* way. It writes the
folder and the instructions, shows you where they are, and reads what the
agent writes.

## What is in the folder

The agent works on the real book, in `books/<language>/<slug>/`, not on a
copy, with Parseh's own tools run by Parseh's own Python (the instructions
give its full path, so nothing is installed or activated) and writing nowhere
but in that folder. Beside the book's own files the folder holds:

- **`original/`** The text the book is made from, as you chose it: the first
  file, and a file for every part you add later.
- **`AGENTS.md`** The instructions, one plain file written for this book
  alone: its language and the language of its glosses, where the tools and
  the folder are (the full paths), the order of the work, the rules, and what
  the agent keeps. Any agent that works in a folder can be told to read it,
  and several read it by themselves. **`CLAUDE.md`** is one line pointing at
  it, which Claude Code reads without being told.
- **`.claude/skills/parseh-book/`** and **`.agents/skills/parseh-book/`** The
  same method as a *skill*: a folder of notes that some agents look for in the
  folder they are working in, and open only when they need a part. The first
  is the one Claude Code looks in, the second the one most of the others do.
  They are copies of one another, written with `AGENTS.md`, and an agent that
  reads `AGENTS.md` has no need of them. None of these files is a setting:
  Parseh writes no permission file for any agent, because what an agent may
  do on your computer is yours to decide.
- **`NOTES.md`** The book's journal: the source's oddities, the decisions
  taken, what is open. The agent keeps it, and its last lines are shown in the
  making panel.
- **`ASKS.md`** What you ask of the agent, one dated entry at a time
  (below). Empty until you write in it.
- **`making.json`** The record of the making: where it stands, for the panel
  and the library card.
- **`annot/`** The annotation the chapters are assembled from. It is the
  book's truth while it is made: the `.tex` files are output.

The agent never runs the full build (`build.sh`) while it works — the page
does that, one job at a time. It may typeset the chapters so far into
`frankdraft.pdf` beside the book, which is never `main.pdf`, so the two
cannot collide.

## Watching it

**On the library page** the book's card says **being made** with where the
making stands and when the agent last wrote — *being made · batch 2 of 6 ·
3 minutes ago* — and moves by itself while the page is open. The stage is one
of: *not started yet*, *source recovered*, *chapter table*, *batch N of M*,
*all batches in*, *waiting for the next part* and, once you finish it,
nothing at all.

**In the reader** the header has a button, **being made · batch 2 of 6**, which
opens the **making panel**. It is a panel any device let in can read, on a
phone too, and it is drawn again by itself every few seconds while it is open:

- **Where it is.** The stage, when the agent last wrote, and the one line it
  says it is on. Under it, in a box of its own, anything you should know:
  *Parseh was updated during the making* (with the version it began under and
  this one — the tools the agent calls may have changed under it); a
  `making.json` the agent is writing at that moment and cannot be read just
  now (the book is still being made, and stays locked); or *the agent has
  written more since this page was built*.
- **look at it now.** Rebuilds this page from what has been written so far
  — the same job as **rebuild the reader** — and reloads it with the panel
  open again. The reader of a book being made shows the batches it has, and
  says under the last of them which chapters are still to come.
- **the PDF of these chapters.** The chapters written so far, typeset into a
  PDF (`frankdraft.pdf`), with a link to open it, and whether it is older than
  the newest batch. It is the reading edition's own draft build, a shell
  script, so where the computer has none — Windows — the panel says so
  plainly: *the PDF of these chapters is not available on this computer,
  which has no shell to make it. The reader is available: look at it now.*
- **The chapters.** The table the agent decided on, the chapters written so
  far and those still to come.
- **What the tools said.** The last words of `check_batch`, `assemble` and
  `verify_book`, as the agent kept them in `making.json`.
- **The agent's notes.** The end of `NOTES.md`.
- **The text**, **what to change from now on**, **the folder** and
  **finish** — below.

## Writing the instructions again

The instructions in the folder were written when the folder was made. If
Parseh has been updated since, or you changed your own prompt for them (the
menu beside **copy the instructions** on the add page, [Your own
prompts](doc:Your own prompts)), the agent is still reading the old words.
**write the instructions again**, in the folder part of the making panel,
writes `AGENTS.md`, `CLAUDE.md` and the skill folders again, from the book's
own facts and the way the folder was made: the same finished edition and
examples, the same short vowels and transliteration, the same prompt of yours
with its latest words. It touches nothing else — not `NOTES.md`, not
`ASKS.md`, not `making.json`, nothing the agent made.

Then **tell the agent**. It read the old file when it began, in its own chat,
and Parseh cannot reach into that chat: say *read AGENTS.md again before your
next batch*. The panel says so after you press. A finished book has no agent
reading its instructions any more; reopen it first
([Reopening a finished book](#reopening-a-finished-book)).

## While it is made, the reader does not edit

The pipeline's truth is `annot/*.json`, and the `.tex` files are assembled
from it. An edit made in the reader writes the `.tex`, and the agent's next
assembly of that batch would erase it. So while a book is being made:

- the **pencil** over a chunk says why (*editing is off while an agent makes
  this book*) and opens the chunk sheet, which shows the chunk, shuts
  everything that writes it — the boxes cannot be typed in, and save, delete
  gloss, cut, join, the source mark and the LLM row are not there — and
  offers **ask about this chunk** (below);
- **book info** and **gloss with an LLM** are greyed, each with its reason;
- the passes, the glosses' clouds, the dictionary, the narration and the
  builds work exactly as in any book;
- and the server refuses the doors that write a chapter — an edit, a cut or a
  join, a chapter's name or a section, an LLM's answer, the free mark —
  whatever the page does, answering *This book is being made by an agent …
  editing is off until the making is finished*. (More text is not one of
  them: added by hand it becomes a part the agent takes, below.)

Finishing ends all of it.

## Steering it

The agent re-reads `ASKS.md` before **every** batch, does what an entry asks
from the next batch on, writes in `NOTES.md` what it changed because of it,
and asks you in its own chat when an ask goes against the method. Two ways to
write an entry, both open to any device let in:

- **What to change from now on**, a box on the making panel: *keep the
  vocabulary lines shorter*, *write the meanings more literally*. **ask** adds
  a dated entry, and the panel counts the asks written so far.
- **Ask about this chunk**, in the chunk sheet of the reader: the chunk's
  address (*chapter 1, paragraph 2, subparagraph 2.1, chunk 4*), its text and
  your line, so a remark is anchored where you saw it.

An entry looks like this:

```markdown
## 2026-09-29 14:12 — about a chunk

chapter 1, paragraph 1, subparagraph 1.1, chunk 0:
> The old man

This meaning is too free: make it literal.
```

Whether a batch already built is redone because of an ask is the agent's to
propose and yours to accept, in its chat: nothing already checked is changed
behind your back.

## The text, a part at a time

A long book, or several, cannot always be given in one file. The text can come
in **parts**, a bit at a time, from any device let in, over as many days as
you like, and the agent takes each part as it comes:

- **The first file is part 1.** The panel lists every part under **the
  text**: its label or file, its size and pages, where it goes, and where it
  stands — *not taken by the agent yet*, *taken by the agent* or *in the
  book*.
- **Give the agent more text** is a box in the panel (and **add to a book**,
  on the add page, reaches the same door): a file — a PDF with a text layer
  and the pages to read, counted from 0, an epub or a plain text file — or
  text you paste; where it goes — *the agent decides where it goes* (the
  default), *a new chapter*, *on in the last chapter*, or *on in the last
  paragraph* when you cut the text in the middle of one; a label, if you like;
  and **this is all the text** when it is the last. A file is sent from the
  page, never named by a path on the computer, so it works from another
  device, and there is no limit to its size but the disk's.
- **The agent takes it before its next batch.** It looks at the list before
  every batch, recovers the part with Parseh's own tool, numbering its
  paragraphs on from the book's, makes its chapters as you said, brings its
  chapter table up to date and shows it to you in its own chat. Where you left
  the decision to it, it writes what it decided in `NOTES.md` and the panel
  shows it under the part, so that you can correct it with an ask.
- **this is all the text.** While more may come, an agent that has taken every
  part and made every batch says it is *waiting for the next part*; once you
  say there is no more, it says the text is complete and stops. **more text is
  coming** takes that back.

The agent makes every part of a book it is making, because what it writes is
assembled from its own files. To gloss a text yourself — blank chunks at the
end of the book, glossed in the reader a region at a time with a chatbot
([Glossing a stretch with an LLM](doc:Glossing a stretch with an LLM)) or by
hand — finish the making first, then use **add to a book** and choose *I gloss
it myself*.

## Finish

When the agent says every batch is in — the stage reads **all batches in** or
**waiting for the next part** — **finish…**, in the panel, ends the making,
from any device let in. It asks *Has the agent stopped?* first, because the
agent must not write in the folder any more. If a part has not been taken yet,
or the agent has not said it is done, the panel says so before you press
(*part 3 has not been taken by the agent yet*, *the agent has not said it is
done: its record says "batch 4 of 12"*) and asks *Finish anyway?*: a second
press goes through, as it must for an agent that forgot to record. It then
runs, as jobs whose progress you can watch:

1. **checks every paragraph against its source** (`verify_book`), and says in
   words what it found: *every paragraph reproduces its source (24
   paragraphs)*, or *2 paragraphs do not reproduce their source*, and for each
   one which chapter and paragraph and at which character; a book with no
   chapter yet is not finished;
2. **builds the whole book** — the PDF and the reader, the build the **build
   PDF** button runs — and says what TeX first complained of if it fails. A
   computer with no TeX cannot make the PDF, so there the reader alone is
   built and the answer says the PDF was left: such a computer could never
   have finished otherwise.

Both clean, the making ends: `making.json` says **finished**, the agent finds a
last entry in `ASKS.md` telling it to stop, the library card stops saying
*being made*, and the reader — reloaded as an ordinary book — edits again: its
pencil writes the `.tex`, which is the truth from then on. **`annot/` stays**
as the record of how the book was made; nothing of Parseh's assembles it
again. If either is not clean, the panel says which and what to do, the book
is still being made, and you can finish again once it is mended.

## Reopening a finished book

A finished book can be reopened, so that a part you add next month goes on
where the making stopped. On the add page, **add to a book**, choose the
finished book and *the agent makes it*: the making is reopened — the book
is *being made* again and its reader does not edit, `annot/`, `original/` and
`NOTES.md` are as they were, and the reader and the PDF stay as they are until
the agent assembles again — and the text becomes the next part. An agent that
stopped when you finished finds a last entry in `ASKS.md`, *reopened*, which
takes the first back; tell it to carry on.

## Who may do what

Every device let in may do all of it: make the book's folder and see the
instructions, give the agent text, say it is all the text, read the panel,
**look at it now**, make the PDF of the chapters, write an ask, write the
instructions again, **finish** and reopen. These doors only write files under `books/` and start Parseh's own
build, like the doors every device already has; the agent that runs Parseh's
tools in the folder is started by you, on the computer.

One thing is the computer's own act, and is not a permission: **open the
folder** shows it in the file manager on the screen of the computer Parseh
runs on. From another device the panel shows the folder's path to copy, and
says why there is no button
([From a phone or another computer](doc:From a phone or another computer)).

## What `making.json` says

It is one small object Parseh and the agent keep between them, and the
first thing to read if you hand the folder to another agent:

| Key | Whose | What it says |
|---|---|---|
| `state` | Parseh's | `making`, or `finished`: written when the folder is made and by Finish, never by the agent |
| `parseh`, `started` | Parseh's | the version of Parseh the folder was made under, and when |
| `parts`, `more_coming` | Parseh's | the text given so far, part by part (the first original is part 1), and whether more may come |
| `instructions` | Parseh's | how the instructions were written (the finished edition, the examples, the short vowels, your own prompt), so that they can be written again the same way |
| `asks_read` | the agent's | how many entries of `ASKS.md` it has read |
| `stage` | the agent's | `source`, `chapters`, `batch`, `done` or `waiting` |
| `on` | the agent's | one line: what it is on now |
| `chapters` | the agent's | the chapter table: `[{"chapter": 1, "paragraphs": 24}, …]`, each row may say which `part` it came from |
| `batches` | the agent's | `{"done": 3, "of": 12}` |
| `checks` | the agent's | what the tools last said |
| `sources` | the agent's | which parts it has taken, `{"done": [1, 2], "of": 3}`, and what it decided for each |
| `updated` | the agent's | when it last wrote the file |

A file the agent wrote wrongly, or half, never stops the panel: what cannot
be read is said, and the book stays locked. Parseh keeps its own copy of the
list of parts in `original/parts.json`, and puts it back into `making.json` if
an agent that wrote the whole file from what it read earlier left a part out.

## What a finished book carries

Its **download** and **Backup every book** carry the original and `annot/`
beside what they always carried — the chapters, `book.json`, `NOTES.md`,
`source/`, the notes — so a copy on another computer keeps how it was made
and what it was made from ([Taking a book away](doc:Taking a book away)). The
agent's own files — `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.agents/`, `ASKS.md` and
`making.json` — never travel: they are about one making on one computer. The
bundle's format number went up with this; an older Parseh refuses such a
bundle in words, and going back to an older Parseh asks you to tick *I
understand* first ([Updating Parseh](doc:Updating Parseh)).

## When something goes wrong

The panel and the add page say what is wrong in words; the rows for this
page are in [When something looks wrong](../reference/troubleshooting.md#a-book-made-by-an-agent).
