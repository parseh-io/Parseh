---
title: Note types and directions
weight: 2
description: The two kinds of Anki card, the pair of note types each language has, and the Reverse and ReverseOnly fields that decide which cards a note makes.
---

In Anki a card's layout — its fields, its templates, its styling — belongs
to its **note type**. Parseh's cards use note types of their own, and it
is worth knowing what they are, because they are also what you meet when
you edit a card inside Anki.

## Two kinds of card

- **Vocabulary** (`vocab`, the default): the word on one side, its meaning
  on the other, with the transliteration, the context, the notes, a
  picture and a recording on either side, and a link back to where the
  word was found.
- **Opposites**: the card asks *“what is the opposite of X?”* and the
  answer is the opposite word. You write the opposite yourself — the card
  sheet's **opposites** button changes the form to ask for it.

They are two note types rather than one with extra fields on purpose.
Anki refuses to update the notes of a note type whose shape has changed,
so the vocabulary type must keep its shape for ever; the opposites were
added as a second type beside it rather than as new fields in it.

## One pair per language

For the same reason, **every language has a pair of its own**. Persian's
pair is the original one and keeps its names, ids and fields exactly;
every other language's pair is the same, with the first field named after
the language:

| Language | Vocabulary note type | Opposites note type |
|---|---|---|
| Persian | Frank YouTube Persian | Frank Persian Opposites |
| Arabic | Frank Arabic | Frank Arabic Opposites |
| Italian | Frank Italian | Frank Italian Opposites |
| Japanese | Frank Japanese | Frank Japanese Opposites |
| French | Frank French | Frank French Opposites |
| German | Frank German | Frank German Opposites |
| Turkish | Frank Turkish | Frank Turkish Opposites |
| English | Frank English | Frank English Opposites |
| Hindi | Frank Hindi | Frank Hindi Opposites |
| Spanish | Frank Spanish | Frank Spanish Opposites |
| Chinese | Frank Chinese | Frank Chinese Opposites |
| Catalan | Frank Catalan | Frank Catalan Opposites |

The first field of each is named after the language — `Persian`,
`Arabic`, `Japanese`, `Hindi` — except English's, which is `Headword`,
because its meaning field is already called `English`. A language whose words have a **reading** — Japanese,
with its kana — has a `Reading` field right after the first one, and its
opposites type an `OppositeReading` right after `Opposite`; the reading is
shown in a line of its own under the word.

The fields, in order (Persian's names; another language's first field is
its own):

| Vocabulary | Opposites |
|---|---|
| `Persian` | `Persian` |
| `Transliteration` | `Transliteration` |
| `English` — the meaning | `Opposite` |
| `Context` | `OppositeTr` — the opposite's transliteration |
| `Notes` | `Notes` |
| `FrontImage` | `FrontImage` |
| `BackImage` | `BackImage` |
| `Source` | `Source` |
| `Reverse` | `Reverse` |
| `ReverseOnly` | |

The note types' ids come from Parseh's language registry, and a card
file records its language, so a build always knows which pair a card
belongs to. The package of a deck carries only the note types its cards
use: a Persian deck of vocabulary cards carries **Frank YouTube Persian**
alone, and **Frank Persian Opposites** only when the deck has an opposites
card — never another language's types.

### The meaning is not always English

The field is called `English`, and will be for ever — renaming a field
would make Anki take the note type for a new one — but what is in it is
the meaning **in the language the book or the video is glossed in**: an
Italian meaning for an English book glossed in Italian, an Arabic one for
a book glossed in Arabic.

The card file does not record which language that is, so the templates
say nothing about it: they are the plain ones, which give the meaning and
the notes no language and no direction of their own. The letters of an
Arabic meaning still run right to left, but its line is set as a
left-to-right one, and its notes are aligned to the left. For the same
reason the templates are always named after English on the meaning side
(*Persian → English*, *English → Persian*), and so are the labels of the
sheet's **preview card**, whatever the gloss language is.

### Right to left, and the fonts

For a right-to-left language — Persian, Arabic — the word, the context and
the opposite are right-to-left fields in the note type, and the cards are
set right to left. The package also carries the language's own web font
when Parseh ships one, so that the cards look as they do in the reader:
**Vazirmatn** for Persian, **Noto Naskh Arabic** for Arabic, **Noto Serif
Devanagari** for Hindi. The other languages use the fonts of the device
Anki runs on.

## Direction: which cards a note makes

A vocabulary note has two card templates:

| Card | Asks | Made while |
|---|---|---|
| 1 | the word → its meaning | `ReverseOnly` is **empty** |
| 2 | the meaning → the word | `Reverse` is **not empty** |

So the two fields are **gates**, and between them they give three shapes.
The card sheet offers them as its **direction** buttons — in a Persian
video glossed in English, **⇄ both**, **→ Persian → English** and
**← English → Persian only**:

| Button | `Reverse` | `ReverseOnly` | Cards |
|---|---|---|---|
| **⇄ both** | `y` | (empty) | 2: both directions |
| **→ Persian → English** | (empty) | (empty) | 1: the word → its meaning |
| **← English → Persian only** | `y` | `y` | 1: the meaning → the word |

Look at the third row: **a reverse-only card still needs `Reverse`
set**, because card 2 is gated on it. `ReverseOnly` does not turn the
reverse card on; it turns the *forward* card off. The card sheet sets
both for you; it matters when you edit a note by hand in Anki. And a
card already made stays when its gate changes later: it becomes an *empty
card*, kept with its history until **Tools → Empty Cards** removes it
([Editing inside Anki](editing-in-anki.md#reverse-and-reverseonly-in-practice)).

The buttons name the card's two sides. In the book reader they read
**⇆ both**, and, when a book is glossed in the language it teaches (an
English book with English glosses), **→ word → meaning** and
**← meaning → word only**, since “English → English” would say nothing.

**What the third shape is for.** A meaning with two words: *body* is both
تن *tan* and بدن *badan*. Asking *body* → Persian is fair only if either
word may be the answer, but each word asked on its own is a question of
its own. So: one note for تن and one for بدن, each **→ Persian → English**
only, and one note *body* → تن / بدن made **← English → Persian only**,
its Persian side listing both words. Three cards, no question asked twice.
[Editing inside Anki](editing-in-anki.md#a-worked-example-one-meaning-two-words)
shows the same in Anki's own fields.

### Opposites

An opposites note has the same two templates — the opposite of the word,
and the opposite of the answer — and only the `Reverse` gate: its
direction buttons are **⇄ both**, which also asks the question the other
way round, and **→ word → opposite**. There is no reverse-only opposites
card, and the third button is not shown.

## What each side shows

The vocabulary card's question is the word, with the front's picture (and
its recording) above it, and its reading under it where there is one; the
answer adds the meaning, the transliteration, the context, the notes, the
back's picture and recording, and the source, a link back to the book or
the video. The reverse card asks with the meaning and the back's picture,
and answers with the word and the rest. An opposites card asks *what is
the opposite of* with the word and its transliteration, and answers with
the opposite, its transliteration, the notes, the back's picture and the
source.

**preview card** on the card sheet draws exactly this, with the templates
and styling the package will carry: see
[Making a card](making-a-card.md#preview-card).
