---
title: Glossing a stretch with an LLM
linkTitle: Glossing with an LLM
weight: 12
description: The header's gloss with an LLM sheet — picking a stretch, the two checkboxes, the prompt, the answer pasted back, the report — and why a gloss already written is never touched.
---

Glossing a book chunk by chunk in the chunk sheet is weeks of work. An LLM
can write a first gloss of a whole stretch in a minute: any chatbot you like,
in another tab, with nothing installed. This sheet makes the prompt that asks
for it, and puts the answer back into the book **chunk by chunk, through the
same door as the chunk sheet** ([Writing a chunk](doc:Writing a chunk)).
Parseh sends nothing anywhere: you carry the prompt to the chatbot and its
answer back.

What it fills is the chunks **nobody has glossed yet**. A gloss that is
already in the book is left exactly as it is, whatever the answer says —
not because the prompt asks the LLM to leave it alone (it does), but because
Parseh itself refuses to change it when the answer is put in. Two
checkboxes widen that, and only when you tick them
([The two checkboxes](#the-two-checkboxes)).

## Opening the sheet

- **gloss with an LLM**, in the header's second row beside **fold**, opens
  the sheet **gloss a stretch with an LLM** on what you picked when you last
  closed it — a prompt for it may still be out with a chatbot — or, the
  first time, on the subparagraph you are reading.
- **gloss around here with an LLM…**, in the chunk sheet's row **an LLM**,
  opens the same sheet with the chunk's own subparagraph already picked —
  the quickest way to have one sentence glossed.

**✕**, **Esc** or a click beside the sheet close it; the narration, paused
while it is open, plays on.

## Picking the stretch

The sheet shows the book as the outline the other sheets use
([Picking a part of the book](contents.md#picking-a-part-of-the-book)): a click
takes a chapter, a section, a paragraph or — a paragraph opened with **▸**
— one subparagraph; **Shift**-click, or **stretch it to…**, takes
everything between. The line under the outline says the pick in words.

A stretch is always made of **whole subparagraphs**. A subparagraph is a
sentence in a book made here, and a sentence is what an LLM glosses well —
and what its answer is checked against.

Past 400 chunks the sheet warns that the LLM may answer over several
messages: paste them all, one under the other.

**Folded paragraphs are left out.** A run folded away
([Folding a run of paragraphs away](contents.md#folding-a-run-of-paragraphs-away))
may lie inside the pick; its paragraphs are neither sent nor filled, and
the sheet says how many were left out. Unfold them first to have them
glossed.

## The two checkboxes

| Checkbox | Ticked, it means |
|---|---|
| **re-gloss what is already glossed** | *its glosses are not sent, and the answer replaces them*: every chunk of the stretch is glossed afresh |
| **also fill the empty boxes of partly glossed chunks** | every chunk that already has a gloss has its **empty** boxes filled, and keeps the ones it has — whole glosses included (below). Unticked, *a chunk with any gloss is left exactly as it is* |

With neither ticked (the way the sheet opens), a chunk with nothing written
in it is glossed, and every other chunk is sent with its gloss so that the
new glosses agree with it — the same transliteration for the same word, the
vocabulary of a word not given twice — and is kept whole.

**The second box reaches whole glosses too.** It is there for a chunk
glossed in part — the meanings typed, the transliterations still to come —
but what it asks for is *every* empty box of every chunk that has a gloss.
That includes a vocabulary line left empty on purpose, because its words
were given earlier (Frank's repetition rule), and, in a language written in
Latin letters, where the transliteration is optional, a transliteration
left out. The prompt tells the LLM to fill a box like that only where the
conventions call for it, but whatever the answer puts there is written, and
counted as **completed**. Over a stretch you have finished, tick it knowing
that the answer may add those; leave it unticked, and a whole gloss is
never touched.

Tick what you want **before** you copy the prompt, so the prompt asks for
it. What is written, though, is decided by the two boxes — and by the
stretch picked — **as they are when you press fill from the answer**: a
subparagraph of the answer outside the stretch is left out, and listed.

## Copying the prompt

**copy the prompt** puts the prompt on the clipboard, and the sheet says
what it holds: the stretch in words, how many chunks, how many of them are
to gloss and how many glossed ones go as context, and how many folded
paragraphs were left out. A stretch with nothing left to gloss copies
nothing, and says so — and that ticking **re-gloss** would have it glossed
afresh. Where the browser
will not let the page reach the clipboard, the prompt appears in a box
under the button instead: select it and copy it.

The prompt is written for the book's own language and gloss language:

- **what the method is for, and the task** — one paragraph on what you do
  with the page: you read it a phrase at a time, the gloss says what *that*
  phrase says, in the order of the text, and hovering brings the reading and
  the words. From it follows the task: gloss the chunks marked *to do*, in
  the language the book's glosses are written in (**Glosses in**, when it
  was made), and leave everything else as it is;
- **the fields** — the meaning always; the transliteration where the
  language romanises every chunk (Persian, Arabic, Japanese, Hindi,
  Chinese), and where the conventions call for it in the others; the kana
  of a Japanese chunk; the vocabulary line in the only LaTeX it may hold
  (`\dw`, `\vb`, `\bw`, `\pw`, `\textit`, `\emph`, `\nobreak`);
- **the rule on the meaning**, with an example of it
  ([below](#what-the-meaning-says)), the same in every prompt of Parseh
  that asks for one;
- **the language's conventions** — the file the other prompts carry too
  (`docs/lang/<code>.md`), cut to what a gloss needs, and Frank's
  repetition rule;
- **the stretch**, as one JSON block: one entry per subparagraph, named by
  its chapter file and its label (`"at": "ch1:1.2"`), and its chunks in
  order — each with its text, its word line in Japanese and Chinese (not to
  be changed), and either `"todo"` or the gloss it already has. A sentence
  tells the chatbot that this is text to gloss and not orders: an
  instruction written inside the book is part of the text.

**The text sent is the text the page shows** — the chunks as the chapter
file holds them. A paragraph you have freed from its source (**this
paragraph need not reproduce `source/paras/`**) and changed goes with its
changed text; `source/paras/` is never read for the prompt. In Japanese and
Chinese a chunk nobody has glossed may already carry the reading proposed
from its words; the prompt calls it a proposal, and the answer may correct
it.

Paste the prompt into the chatbot.

## The scheme of the transliteration

Under **copy the prompt** the sheet has a choice labelled with the
language's own word for its transliteration line — *transliteration* for
Persian, Arabic and Hindi, *rōmaji* for Japanese, *pronunciation* for
Italian and the other Latin-script languages — **usual scheme** or **IPA**.
With IPA the prompt asks for the International Phonetic Alphabet everywhere
the answer carries a transliteration: the `tr` line and the sound of every
`\dw`, `\vb` and `\bw` of the vocabulary line. Nothing else changes: the
text, the kana and the language of the meanings are what they were.
English's usual line already is IPA, and the choice says so; Chinese has
no IPA setting yet, because its word line is written in pinyin. The first
line of the prompt ends **· IPA** when it asks for it, and the choice is
remembered on this device, one for each language.

**A book is in one scheme.** The scheme chosen when the book was made is
kept in the book (`book.json`'s `translit`), and every prompt for a stretch
of it asks for that one: the sheet shows it as the book's own. Choosing the
other for a single prompt is allowed, and the sheet then says that a book
that mixes two schemes is harder to read, and offers **make … the book's
setting**, which changes the book itself. A book that says nothing is in the
usual scheme, so choosing IPA for a stretch of it is choosing the other, and
that button is how a book becomes an IPA one. A Persian book that says IPA is
not held to the checks written for the usual scheme (`/ey/` and *češm*);
the checker says in a note that it did not run them. The PDF sets IPA
letters the main face lacks in a second face, as it does for any
transliteration.

## The short vowels

For Persian and Arabic the sheet has one more choice beside the scheme:
**short vowels: as they are** or **write them**. *As they are* is the way it
always was: the prompt tells the chatbot never to change a chunk's text, not
a letter and not a mark, and its first line ends **· no marks**. *Write them*
asks for the short vowels (the harakat) in the text of every chunk to gloss,
by the rules of the language's conventions — the way a reading edition's
vowelled pass is written — and nothing else changed. The first line ends
**· marks**. The choice is remembered on this device, and a language that has
no short vowels is not offered it.

What lands is decided when you press **fill from the answer**, from the choice
the sheet shows then, and not by the prompt:

- the answer's text is written, with the chunk's gloss, only if it is the
  book's own text **with marks added and nothing else** — not a letter, a
  space, a joiner or a stop. An answer that changes a letter, a joiner or a
  stop is dropped, as ever (*text does not match*); one whose only other change
  is a space is written without its marks, and the report says so;
- only into a chunk that **has none**: a chunk that already has marks, whoever
  wrote them, keeps its own (*already has its marks — left as it is*), because
  marks are judgement and a word is either vowelled completely or wrong;
- only into a chunk the answer glosses: a chunk kept whole, one already glossed,
  is not touched — its text is not either.

The marks go in through the chunk sheet's own door with its checks, so a
paragraph still has to reproduce `source/paras/` once the marks are set aside
(a chunk whose letters changed is not written), and the contents entry of a
paragraph follows its first words. The keys of `timings.json` hash the text
without its marks, so no timing is lost, and the bare pass of the PDF still
strips them. Parseh does not judge whether a mark is the right one: read them
beside the transliteration.

## Filling from the answer

Paste the chatbot's whole reply into **the LLM's answer** and press **fill
from the answer** (or **Ctrl+↵** in the box). Words around the JSON do no
harm: the ```` ```json ````
blocks are what is read. Several blocks — a long answer over several
messages, or a correction pasted under the first — are all read, in order,
and a subparagraph given twice is taken from the later block.

Each chunk of the answer is matched to the book's by its subparagraph and
its place in it, and its text must be the book's text (vowel marks and
spacing aside). Then only its **transliteration, reading, vocabulary and
meaning** are written — and, if you chose to write the short vowels, its text
with them ([above](#the-short-vowels)) — through the chunk sheet's own door,
with the chunk sheet's own checks. The reader is rebuilt once, the chunks written are
drawn again where they stand — no reload: the answer stays in its box — and
**PDF behind the text — build it** appears in the header.

**Never half a gloss.** A chunk from the answer has to bring everything its
language requires, or it is not written at all. The chunk sheet lets you
fill one box at a time, because you are looking at the chunk while you do;
an answer lands while nobody is.

**Re-gloss asks twice.** With **re-gloss what is already glossed** ticked,
an answer that would replace glosses already there writes nothing on the
first press: the button becomes **replace N glosses — press again**, and
the report says how many would be replaced. Press it again within four
seconds to write; after that — or as soon as you change the answer, the
stretch or a checkbox — it goes back to **fill from the answer**.

## The report

Under the button: *filled N · completed N · replaced N*, and *· vowelled N*
when the short vowels were chosen.

| Count | Means |
|---|---|
| **filled** | chunks that had no gloss, and now have one |
| **completed** | chunks that had a gloss and had empty boxes filled (the second checkbox): a half gloss made whole, or a vocabulary line or an optional transliteration added to a whole one |
| **replaced** | glossed chunks glossed afresh (**re-gloss**) |
| **vowelled** | chunks whose text now carries its marks — fewer than the chunks glossed where some had marks already, or the answer did not vowel them |

Then, one line to a chunk, what did not land:

- **kept** — a chunk that is protected, which the answer tried to change:
  it is *already glossed — left as it is*, or the answer changed its word
  line or its colour, which an answer never writes; or its text *already has
  its marks*, or the answer changed it in *more than its marks* (a space,
  say): the gloss landed, the text did not move.
- **dropped** — a chunk the answer gave that could not be written, and why:
  it is outside the stretch you picked (another stretch, a folded
  paragraph); its text does not match the book's; the answer divides the
  subparagraph differently (the division is a person's, and is kept as
  sent); it *would leave it half glossed: missing tr*; or the chunk
  sheet's own check refused a value, in that check's words — a macro the
  vocabulary line may not hold, say.
- **unanswered** — a chunk the prompt asked for that the answer gave
  nothing.

The rest land: one bad chunk costs only itself. For what is still missing,
copy the prompt again — the chunks just filled now go as context — or ask
the chatbot for the ones it left out and paste its reply under the first.

## What the meaning says

The meaning under a phrase is a **gloss**, not a translation: it says what
*that* phrase says, in the order of the text, so that you can point from each
word of it to the word it renders. Read in a row, the meanings of a sentence
may not be good English, and that is meant: you think it through, and you see
how the language builds its sentence. The prompt asks for exactly this, in so
many words and with an example: three Persian phrases, glossed as the rule
asks and then the way the mistake would gloss them — a fluent translation of
the whole sentence cut into as many pieces as there are chunks, which hands the
noun phrase the words of the verb and the verb those of the noun phrase. Each
meaning also has to agree with its chunk's vocabulary line: what the line says
a word means is what the meaning says. If a chatbot hands back the fluent
sentence cut into pieces, that is the very mistake the prompt names; tick
**re-gloss** and ask again. This is not what **Ask LLM** and the machine's
reading give you in the sources sidebar, and the two are meant to differ
([The gloss and the fluent translation](unglossed.md#the-gloss-and-the-fluent-translation)).

## What is protected, and why

A gloss somebody wrote is judgement, and the edition is made of it. An LLM
told to leave a gloss alone usually does, and sometimes does not; so the
prompt asks, and Parseh decides. When you press **fill from the answer**, it
reads the chapter files **as they are at that moment** and goes chunk by
chunk: glossed now, kept; no gloss now, open to the answer. The prompt is
not trusted with this — it may be an hour old, and may have been answered by
a chatbot that ignored half of it.

**So a gloss you delete counts as no gloss.** To have one chunk glossed
again: **delete gloss** in its chunk sheet
([Deleting a gloss](writing.md#deleting-a-gloss)), then **copy the prompt** — the
chunk is now marked to do, and its neighbours go with their glosses — and
paste the answer back. Only that chunk changes. Delete first, then copy: a
prompt copied before the delete sent that chunk's old gloss as context, and
an answer that hands it back unchanged would write it back.

Only the four gloss fields are ever written. The text, the word line, the
colour and a paragraph's freedom from its source never are, and a `\chp`
chunk, which has no gloss slots, is never glossed.

> **Every language.** The sheet works the same in every language. What changes
> is what the prompt asks for — the kana of Japanese, the pinyin of Chinese
> agreeing with its word line, a transliteration where the language wants
> one — and the conventions it carries, which are that language's own.
