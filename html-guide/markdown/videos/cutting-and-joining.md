---
title: Cutting and joining phrases
linkTitle: Cutting and joining
weight: 8
description: Moving where a phrase ends — cut in two, join next, join previous — what is proposed for each half, and what is refused.
---

Everything on the [editing page](editing-a-phrase.md) changes what a phrase
**says**. This changes where it **stops**, inside its line; where a **line**
stops — words moved to the line before or after — is
[Moving text between lines](moving-text.md).

A phrase is a sense group, and where the sense groups fall is a judgement
somebody makes while reading — which means the division a model produced
on its first pass, or the one-phrase-per-sentence of a video started empty,
is exactly what a person who knows the language wants to move. It takes
three buttons, at the foot of the ✎ form:

| Button | Does |
|---|---|
| **✂ cut in two** | divides this phrase into two |
| **join next** | joins this phrase and the one after it into one |
| **join previous** | joins the phrase before this one to it — shown from a caption's second phrase on |

**join previous** is the same operation asked of the phrase before, and it
is also how a run drawn bare — a phrase marked plain, or a stretch of the
video's own framing, neither of which has a cloud of its own to open — is
reached: from either side. (A phrase of the language that nobody has glossed
yet is not bare: it has its cloud and its ✎.)

Each opens a sheet over the form, named after what it does — *cut segment
3 chunk 0 in two*, *join segment 3 chunk 0 to the next* — and writes
nothing until its button. **✕**, a click beside the sheet, or Esc closes it.

## Where a phrase may be cut

At a space, and nowhere else — for a language whose words are separated by
one. The reason is the check and not taste: the phrases of a caption joined
back with the language's separator have to **be** the caption again, and
`wo rd` is not `word` however the spaces are tidied. Japanese and Chinese,
which write no separator, divide between any two characters.

So the sheet shows the phrase's text with a **✂** at every place it may be
cut, and no others:

- *Pick where it divides. Joined back with the space, the two halves have
  to be this caption again — which is why a word is never cut through.*
- For Japanese and Chinese: *Pick where it divides. This language writes no
  spaces, so it divides between any two characters.*
- A phrase of one word: *This phrase is one word, and a phrase of a language
  written with spaces divides at a space. Join it to a neighbour instead.*
  One character, in Japanese or Chinese: *This phrase is a single
  character, so there is nothing to divide.*

With a single place to cut, it is picked for you.

## What each half is given

Dividing the text is arithmetic. Dividing the gloss is not: nothing in the
data says which half of a meaning belongs to which half of a phrase. So the
sheet shows two columns, **first phrase** and **second phrase**, and
**proposes** what goes in each, in boxes you type over:

| Field | What is proposed |
|---|---|
| the text | the cut itself — the only thing that is not a guess, and not a box: a cut divides, it does not rewrite; change a letter in the ✎ form, before or after |
| kana (Japanese) | all to the first half, unless the reading opens with the first half's own characters — which is what happens when a phrase is parted at a particle |
| transliteration | cut at the same word, when it has exactly as many words as the text; otherwise all to the first half |
| vocabulary | entry by entry: each follows its headword to the half whose text holds it, and an entry with no headword of its own stays with the one before it. The entries are drawn as chips, and **→** or **←** sends one to the other half |
| meaning | all to the first half, so that the second is visibly unwritten and gets written — unless the meaning has exactly one comma, the one place a two-way division is already marked |
| words (Japanese, Chinese) | divided where the text is |
| colour | both halves keep it: it marked the phrase, and the phrase is still there in two pieces |

A phrase nobody has glossed divides into two phrases nobody has glossed. In
Japanese and Chinese, where such a phrase carries the reading proposed from
its words, each half is given the reading of its own words instead — the
whole reading on the first half would make it look written.

Press **divide**. A phrase that carries a note divides like any other: the
note stays with the first half (*the note stayed with the first chunk*),
and a join puts two notes end to end.

## Joining

**join next** shows the two texts, `first · second`, and the one phrase
they become, in one column of boxes to type over. The texts go end to end
with the language's separator — so the caption is reproduced character for
character, and no check **can** fail — the transliterations and the
meanings with a space, the vocabulary lines with their own middle dot.
What could not simply be run together is said in a note under the boxes:
two different colours (the first one's stands), two meanings written to be
read apart — and a phrase now past seven words, which the checker warns
about: *That is 9 words in one phrase; the conventions ask for two to six,
and the checker warns above seven.*

Press **join**. On the last phrase of a caption the sheet says *chunk 2 is
the last of segment 3: there is nothing after it to join it to*, and the
button stays grey.

## Afterwards

Every phrase after the change has a new number, so the caption is drawn
again from the list the server sends back, and the sheet says so: *The
phrase is two phrases now. Segment 3 has 3 of them, and the transcript has
been drawn again from the file.* Its button becomes **close**.

What is written is `annotations.json`, and that is the whole of the
video's annotation: the answer it was built from was folded in when it was
added, and the batches went with it, so there is nothing left on the shelf
that could put the old division back
([A video's files](the-files.md#parts)).

## What it refuses

The division is put through `check_annotations.py` before it is written,
like any edit, and refused if it brings in an error the file did not
already have — but never for a box left empty. Each half may come out
glossed, blank, or glossed in part: the second half of a glossed phrase
usually has its meaning still to write, and is saved so, for you to fill in
the ✎ form (the checker lists it until you do). A join is the same.

| It says | Which means |
|---|---|
| *the page is showing the first chunk as '…' and the file has '…' -- reload the reader before dividing: somebody has changed the book underneath it* | the page is out of date — the video was changed elsewhere since the player drew it. Every divide sends the text it is looking at, and the server compares before it writes. (The sentence is shared with the reading editions, hence *reader* and *book*: reload the player.) |
| *segment 3 chunk 1: its words cannot be divided until the line is mended -- …* | Japanese, Chinese: the phrase's word line is broken; mend it in the ✎ form first |
| *the server did not answer (…) — nothing was written* | the server is stopped or could not be reached |

A page left open is safe as well as stale: the next divide from it is
refused by name rather than made to the wrong phrase.
