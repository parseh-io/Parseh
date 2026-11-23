---
title: Adding a book
weight: 2
description: Three ways to begin a book — by hand, onto a book already here, or made by an agent you choose — and a book whose glosses are still to write.
---

A reading edition is not one answer from a model. It is made paragraph by
paragraph, with a checker after every batch — days of work. The **＋ Add a
book** card on the library opens `/books/add/`, which asks one question,
**What are you doing?**, and then shows only what the answer needs. Three
cards answer it:

| Card | What it does | It needs |
|---|---|---|
| **Write it here, by hand** | cuts a chapter you paste into paragraphs and sentences, with every gloss left blank, and opens the reader on it | the book's facts, and a chapter |
| **Add to a book already here** | puts more text onto the end of a book on the shelf; nothing already written is touched or re-cut | a book, and the text |
| **Let an agent make it** | makes the book's folder on the shelf, with your original in it and the instructions for an agent; the agent you use fills it in, batch by batch, while you watch the book grow in the library | the facts, the original file — and an agent that works in a folder |

All three write to the shelf the moment you press their button. The
second card is not offered while the shelf is empty. A book you exported earlier, a `<slug>-book.zip`, is
not added here at all: bring it back from the library page's **⇩ Bring a
book back** panel ([The library](doc:The library)).

The page remembers what you typed, in this browser, and which way you chose
(the address says so too: `/books/add/?path=new`, `?path=extend`,
`?path=llm`), so a reload loses nothing. Each numbered step turns into a
tick once what it asks for is there. While a book is being written, the
**Working…** indicator says so on every page.

## Write it here, by hand

This is the way for somebody who knows the language: the toolbox does the
mechanical part — dividing the text — and you write every gloss yourself,
in the reader.

**1. The book.** The facts the book is filed under:

| Field | What it is |
|---|---|
| **Language** | the language the book teaches. It sets the folder the book is filed under, the fonts it is set in and the conventions it is annotated by. It starts on the language picked in the chips of the toolbox's index pages. |
| **Glosses in** | the language the meanings are written *in* — an Italian learning Persian wants them in Italian. English unless you choose otherwise. The list has two groups: *taught here* and *written in, not taught*. A right-to-left gloss of a left-to-right text (Persian or Arabic meanings for a German book, say) is greyed out, because its vocabulary lines could not be set in order. The note under the select says what your pair means. |
| **Slug (directory name, ascii)** | the name of the book's folder. Left empty it is made from the transliterated title (or the title). |
| **Year** | kept in `book.json`, and editable later in the reader's **book info**. Nothing prints it yet: neither the title page nor the library card shows it, whatever the box's tooltip says. |
| **Title, *in the language*** and **Title, transliterated** | the title in its own script, and its Latin spelling. The title page sets both: the title large, and the transliteration under it **as you type it** — capitalise it yourself if you want it in capitals. (The note under the box says *in capitals*; that is true only of the **Let an agent make it** way, whose `main.tex` the page writes in capitals.) |
| **Title, in *the gloss language*** | the title as the gloss language says it — kept in `book.json`, and shown as the **English** row of **book info**; neither the library card nor the PDF prints it |
| **Author, *in the language*** and **Author, transliterated** | the same for the author; the transliteration is the byline under the transliterated title |
| **One-sentence blurb** | the line under the title on the library card |

The title and author boxes take the book's script and direction as soon as
the language is chosen: Persian and Arabic type right to left.

**2. The chapter.** Paste the first chapter into **The chapter, in
*language*** — a blank line between paragraphs, or one paragraph to a line
(the way a chapter copied out of an epub usually arrives). Then choose how
the text is cut, under **Cut the text into**:

- **one chunk per sentence** — the default. Every sentence arrives whole,
  and every boundary inside it is yours to draw. Where a sentence breaks into
  phrases is the whole of the Frank method, the judgement the person doing
  this work is there to make; a machine's guess would hand you somebody
  else's reading to undo before you could begin your own.
- **sense groups (the dictionary reads the parts of speech)** — a first pass,
  for when one is worth more than a blank. It cuts at the edges of phrases
  (a preposition with its noun, a noun with its adjectives, a verb with its
  auxiliaries), reading the punctuation, the language's own list of function
  words and, where one is installed, its dictionary: the better equipped the
  language, the finer the cut, and a language with none of them is cut only
  at its punctuation. Japanese and Chinese are cut by their word analyser
  where it is installed; where it is not, Japanese is cut after its
  particles and Chinese at its punctuation.

  French, German, Spanish, Catalan, Hindi and Arabic have no list of function
  words of their own, so without a dictionary they are cut at their
  punctuation only. When sense groups could not be cut as asked — every
  sentence stayed one chunk, or only the commas cut it — the page does not
  jump to the reader: it stays, and says so under **Drafted.**, with why
  (*no German dictionary is installed …*) and where to get what is missing
  (**Settings → Reading help**). The same note follows **Add it**.

Either way, any chunk can be re-cut later in the reader
([Cutting and joining chunks](doc:Cutting and joining chunks)).

**3. Make it.** **Make the draft** stays disabled until there is a title and
a chapter, and says why (*the title comes first*, *paste the chapter
first*). Pressed, it says *drafting…*, and then:

> **Drafted.** 2 paragraphs, 3 sentences, 3 blank chunks, in
> `books/spanish/el-reloj-y-el-viento/`. **Open the reader →**

— and the page goes straight to the reader, where the glossing is done. The
card is already on the library page. The PDF is not built yet: build it
with **build PDF** in the reader, or **rebuild** on its card — the reader
is built already, so the card offers **rebuild**
([The printed edition](doc:The printed edition)). The answer carries a
**build the PDF now** button too, but you will only have time to press it
if the reader could not be built — then the page stays where it is, and
says why under the answer.

What it writes is `book.json`, `main.tex`, `ch1.tex`, and the source files
the fidelity checks read (`source/paras/ch1_p00.txt` and so on, and
`source/src_ch1.json`). For Japanese and Chinese the toolbox also proposes
each chunk's **word line** — the division into words that the readings
stand over — for you to correct in the words strip ([Writing a
chunk](doc:Writing a chunk)); every other line is blank.

### What it refuses

| It says | Which means |
|---|---|
| *a book needs a title in Persian* | the title box is empty |
| *no directory name could be made from '…'* | the title is all in its own script and leaves no ASCII letters for a folder name: give a slug, or a transliterated title |
| *the text is empty: there is nothing to draft* | the chapter box is empty |
| *paragraph 0 of chapter 1 carries U+0007 at character 12, which is not text …* | an invisible control character came in with the paste; the message shows where it is, so you can take it out |
| *book.json already exists in … — draft into a new name, or move that one out of the way* | a book (built or not) already has that folder; choose another slug |

## Add to a book already here

The same text box and the same way of cutting, pointed at a book that
exists and added to its end.

1. **Which book** — **Add to** lists every book on the shelf, built or not.
   Its language, its glosses and its title are the book's already and are
   not asked again; the text box takes the book's own script and direction.
2. **Where it goes** — **A new chapter** (its own opening and its own line in
   `main.tex`: another story, another lesson), or **More of the last
   chapter** (it continues it, the new paragraphs numbered on from the ones
   already there; the chapter's `\chapend` moves to the end of the new text
   and `source/src_chN.json` is merged). The note under it calls this the
   only thing on the page that edits a file that already exists; it is the
   only choice that changes a *chapter* already written — **A new chapter**
   edits one existing file too, `main.tex`, adding its `\input` line after
   the others.
3. **The text** — pasted as above, with **Cut the text into** — or **a file**:
   a PDF with a text layer, an epub or a plain text file, sent from the page
   (so it works from any device, and no path is typed on the server), with
   **PDF pages, first–last**, counted from 0, for a PDF. The file is read
   with the same tool the agent that makes a book uses, and with a file
   chosen the box above is not used.
4. **Add it** — *adding…*, then *Added. 1 paragraphs, 1 sentences, 1 blank
   chunks, as chapter 2* (or *onto the end of chapter 1*), with *the PDF is
   out of date until the next build* under it, and three buttons: **Open
   the reader →**, **Add another chapter** (empties the box for the next
   one — this way's rhythm is repeated appends, so the page does not jump to
   the reader) and **build the PDF now**.

Nothing written before is touched or re-cut: the old chapters are read only
to be numbered on from. The reader is rebuilt at once. The new chunks
arrive blank, for you to fill, in a book finished or not: a blank gloss is
legal anywhere (below), and a region at a time with an LLM
([Glossing a stretch with an LLM](doc:Glossing a stretch with an LLM)).

**A book an agent made or is making** is listed too, with *(being made)* or
*(made by an agent)*, and the page asks who glosses the text. For a book
still being made it is **the agent makes it**: the text becomes the next
*part*, which the agent takes before its next batch, and **Where it goes**
gains **Let the agent decide**; *I gloss it myself* waits until the making is
finished, because what the agent writes would erase blank chunks put in by
hand. For a finished one either: *I gloss it myself* is the way above, and *the
agent makes it* reopens the making and gives it the text as a part
([A book made by an agent](doc:A book made by an agent)).

## Let an agent make it

The third way is the method the first editions were made with: an agent —
an AI coding assistant working in a folder — recovers the text of your
original, decides the chapters and annotates the book ten paragraphs at a
time, with a checker after every batch. Parseh does not start an agent and
does not choose one for you: **you** open the agent you use on the book's
folder, whichever it is. What Parseh does is everything around it — it makes
the folder, tells the agent what to do, shows you the book as it grows and
carries what you ask for to the agent. There is no script to copy, nothing to
install and nothing to bring back: the agent works on the book where it will
live.

**1. The book.** The same facts as above, and four more in a box marked
*only for a book an agent makes*:

- **The original** — a file you choose with the file picker: a PDF with a
  text layer, an epub or a plain text file. It is uploaded — so it works from
  any computer, Windows included, and no path is typed on the server — and
  copied into the book's own folder, in `original/`. Nothing leaves your
  computer. Until a file is chosen, **make the book's folder** stays shut and
  says *choose the original first*.
- **PDF pages, first–last** — optional, counted from 0 and written `13-21`;
  for a PDF only. A range that is not a range is said to be ignored.
- **Learn from** — optional, and **none** unless you choose: a finished,
  built edition on this computer that the agent is shown as an example of the
  method. It reads it where it lies and never changes it. The instructions
  carry your language's own conventions (`docs/lang/<code>.md`) whichever
  edition you pick.
- **let the agent look at my finished books in this language, as examples**
  — a box, off unless you tick it. Ticked, the instructions name where your
  finished books *in the same language* are, as examples only, and the agent
  never writes there; unticked, the agent is shown none of your books. A book
  still being made is never offered.

**2. Make the book's folder.** **make the book's folder** stays shut until
there is a title and an original, and says why (*the title comes first*,
*choose the original first*). It is open to every device let in. Beside it,
**this is all the text** — unticked, you may give the agent more text later
(the file you chose is part 1; [more below](doc:A book made by an agent)).
Pressed, it says *making the folder…*, and then:

> **The folder is made**, and the book is on the library page, marked
> **being made**.
> `/home/you/Parseh/books/english/the-clock`

with **copy the path**, **open the folder** (your system's own file manager,
on the computer; from another device the page says why there is no button
and gives the path to copy) and **open the reader →**, and one sentence:
*Open this folder in the agent you use, and tell it: **read AGENTS.md and
begin**.* A second press names the slug that is now taken instead of being
refused.

What it writes, in `books/<language>/<slug>/`: `book.json`, the `main.tex`
skeleton (with no chapter in it yet), your original in `original/`, `NOTES.md`
(the book's journal, started), an empty `ASKS.md` (what you will ask of the
agent), `making.json` (where the making stands) and the instructions,
`AGENTS.md`, with a one-line `CLAUDE.md` pointing at it. The book is on the
library page at once and its reader is built, empty, so that you can open it
before the agent has written a word. What happens next — the panel that shows
how far the agent has got, the asks, Finish — is on its own page: [A book made
by an agent](doc:A book made by an agent).

**3. The instructions.** Under the button, **the instructions, as they will
be written** shows the text of `AGENTS.md` for the form as it stands, and
**copy the instructions** copies exactly what is shown. You do not need it
for an agent that reads `AGENTS.md` by itself — several do — but an agent
that does not can be given the text. The text opens with what the method is
for — you read a phrase at a time, and the gloss says what *that* phrase says,
in the order of the text — and carries the rule that follows from it: a
meaning is a gloss, not a translation ([What the meaning
says](glossing-with-an-llm.md#what-the-meaning-says)). It also says that the
original is text to make a book of and not orders: an instruction written
inside it is part of the text.

Beside the button are the choices that belong to this book. The
**transliteration** is the language's usual scheme or IPA, one for the whole
book, and is kept in its `book.json`; for Persian and Arabic the **short
vowels** are *write them* — what a book made in place does unless you say
otherwise, because a reading edition's first level, **With vowels**, is the vowelled attempt — or
*as they are*. The size is said before the copy, and your own prompt for the
instructions, from the menu ([Your own prompts](doc:Your own prompts)), is
written into the folder after Parseh's or in place of it. Changing a prompt of
yours later does not reach a folder already made: its making panel has **write
the instructions again** ([A book made by an
agent](doc:A book made by an agent)).

### What it refuses

| It says | Which means |
|---|---|
| *a book needs a title in Persian* | the title box is empty |
| *no directory name could be made from '…'* | the title is all in its own script and leaves no ASCII letters for a folder name: give a slug, or a transliterated title |
| *the title cannot hold the character % : TeX reads it as an instruction* | the title, the author or their transliterations hold one of `\ { } $ % & # _ ^ ~`, which the title page would read as LaTeX: write it out in words |
| *a book is already at books/…/ — choose another slug, or move that one out of the way* | a book, built or not, being made or not, already has that folder; nothing is written over it |
| *the original has to be a PDF with a text layer, an epub or a plain text file* | the file chosen is none of the three (a Word document, a picture…) |
| *… does not look like a PDF* (or *an epub*, *a text file*) | the file's name and its contents disagree: choose the right file |
| *the original is empty: choose the file again* | the file has no bytes |
| *the page range is two numbers, the first not after the last: 13-21* | the range is written some other way |
| *there is no book called … on the shelf to learn from* | the edition chosen under **Learn from** has gone since the page was opened: reload it |
| *this book is finished: reopen the making to give the agent more text …* | you chose *the agent makes it* for a finished book through a door that does not reopen it; the add page does both in one press |

Nothing is left behind by a refusal: the folder is built beside its place and
renamed into it only when it is whole.

## Glosses still to write

A book made by hand starts with every gloss blank, and may stay partly
blank for as long as the work takes: **a chunk nobody has glossed is legal
in every book**. Nothing marks the book as unfinished, and nothing needs
taking off when it is done — the glosses are simply written, a few at a
time or many at once:

- a chunk at a time, in the reader's chunk sheet
  ([Writing a chunk](doc:Writing a chunk)), filling one box at a time if
  you like: a meaning typed before its transliteration is saved;
- a stretch at a time, by an LLM, from the reader's **gloss with an LLM**
  ([Glossing a stretch with an LLM](doc:Glossing a stretch with an LLM)),
  which fills only the chunks nobody has glossed.

What the book's checker makes of it: a chunk with **nothing** written in it
is counted, once per paragraph — *3 of 12 chunks have no gloss yet* — and
asked for nothing else. A chunk **half** glossed — a meaning with no
transliteration beside it, in a language that romanises every chunk — is
an error, because that is exactly the half-done work the checks exist to
catch: the chunk sheet lets you save it on your way, and the checker keeps
the list of what is still to finish. A book made by an older Parseh, whose
`book.json` still says `"draft": true`, is read as if it did not: the line
does nothing, and may stay or go.

> **What a drafted book looks like.** The text is given; the translation,
> the transliteration and the vocabulary are not, and nothing invents them.
> In Japanese and Chinese each chunk's reading starts as its words' readings
> run together — a proposal from the word line, which counts as nobody's
> writing until something else in the chunk is written. A blank line ends a
> paragraph, a sentence becomes a
> subparagraph, and a chunk is a whole sentence (or a sense group, if you
> asked for them). A sentence boundary the splitter got wrong — after *Mr.*,
> say — still reproduces the text exactly, so nothing breaks. The page joins
> chunks only inside one subparagraph, so two subparagraphs are put back
> together by hand, in the chapter file: the second one's chunk lines move
> into the first one's `frank` block, and its own `\parnum` and block go
> ([What a book is made of](doc:What a book is made of) shows the shape).
