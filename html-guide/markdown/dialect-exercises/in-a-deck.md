---
title: Exercises in a deck
weight: 8
description: From a document into an exercise deck and back — + Deck, + Add all exercises, Load from a deck — and how each family of exercises is studied there.
---

An exercise written in a document can also be **studied**: copied into an
*exercise deck*, the toolbox's Anki-like store, it comes back when it is
due and is rated as a card is. The deck keeps the exercise exactly as it
is written — the same `:::exercise` block — so everything on the other
pages of this section holds there too. This page is about the way in and
the way back, and about what each family looks like on the study page;
the decks themselves — their scheduling, options, export and import — are
the *Exercises* door's, described in its own section of this guide.

## Into a deck

- **One exercise.** On a document's reading view every exercise, those in
  a `>` box included, has a **+ Deck** button in its head. It asks for a
  deck of the document's language — the one used last is already chosen,
  and **+ New deck…** makes one — and **Copy** puts the exercise into it
  with the document's tags. The copy brings along the footnotes the
  exercise cites and every picture and recording it names, wherever the
  name is written: an `image:` or `back-audio:` field, a line in a Jolly
  field, a footnote. A file whose name the deck already uses for a
  different file is stored under a new name (`name-2.png`, `name-3.png`…)
  and every mention of it in the copy is rewritten to match; the same file
  is never copied twice. An exercise the deck already has asks before it
  goes in again.
- **All of them.** **+ Add all exercises**, beside **Edit** at the top of
  the reading view, lists every exercise of the page, each ticked; when
  the document has glosses, **Show gloss flashcards (N)** — *N* is how
  many — adds them to the list as vocabulary cards. Untick what you do not
  want (**Select all**, **Select none**), choose the deck, and press the
  button that counts what is ticked: **Add 3 exercises**, say. What the
  deck already holds is left out unless **Add again the ones this deck
  already has** is ticked.
- **Straight into the deck.** A deck's own page has **Add exercise…**,
  which opens the same grid of types and the same form as the editor, with
  **Paste markdown…** at the grid's foot for an exercise copied as
  Markdown. What is saved there must be exactly one `:::exercise` block,
  with nothing round it and no errors.
- **From a book or a video.** A word met in a book or a video goes into
  a deck as a flashcard: see [where cards come from](flashcards.md#where-cards-come-from).

- **A flashcard's side.** A flashcard's `direction:` says [which side
  appears first](flashcards.md#which-side-comes-first), and a deck reads it
  as a document does — with two more values. **Both (random)** is copied as
  it is, and the study page draws a face for the card each time it comes
  up. **Both (repeat)** becomes **two linked cards**: one front first, one
  back first, each written out with its own `direction:`, each scheduled
  on its own, and asked about together when one is edited or deleted
  ([more](../exercises/deck-page.md#linked-cards)).

The deck's copy is a **snapshot**: it is made once, at the moment of
copying, and changing the document afterwards — its words, or a card's
`direction:` — changes nothing in the deck, as changing the deck's card
changes nothing in the document. That is also why the two cards of a
**Both (repeat)** exercise exist only in the deck: the document keeps the
one exercise it always had.

An exercise that [needs attention](container.md#needs-attention) has no
**+ Deck** button and is not offered by **+ Add all exercises**: a deck
always refuses it. Nor does the editor's preview have the button, nor this
guide — only a document's reading view, and the notes a document is
attached as, beside a book or a video.

## Back into a document

**Exercises ▾ → Load from a deck…**, in the editor, lists the decks in the
page's language and, under the chosen one, each exercise with its kind and
its opening words. **Insert** puts it into the document at the cursor,
exactly as the deck has it, and copies its pictures and recordings into
the document's own `images/` and `audio/` (renaming them where a different
file already has the name) and the footnotes it cites among the
document's own. The deck is left as it was: this copies out of it. The
document must have been saved once, since the files go into its folder.

## On the study page

**Study now** shows one exercise at a time, unsolved, and each family is
answered the way it is on a page:

| Family | Answered with | Then |
|---|---|---|
| [placement](placement.md), [matching](matching.md) | the blocks, dragged, tapped, chosen from a blank's cloud or moved with their arrows | **Check** or Enter: *Correct* or *Not quite*, the explanations, and — when it was wrong — **Correct answer**, the exercise shown solved underneath |
| [choice](choice.md) | the answer buttons | **Check** or Enter: *Correct* or *Not quite*, the explanations; the answers are marked as on a page, the one it wanted included |
| [flashcards](flashcards.md) | nothing | **Show answer**, Enter, or a click on the card — or on the enlarged card of **⤢ Enlarge** |
| [follow-up](follow-up.md) | the steps, one after the other | **Check step**, then **Next step**; the ratings come after the last step only |

After the check or the turn, a bar of four ratings appears — **Again**,
**Hard**, **Good**, **Easy**, or the keys 1 to 4 — each saying how long the
exercise would wait. The check never rates for you: a wrong answer only
moves the focus to **Again**, and a right one to **Good**. Once checked, an
exercise's answer is locked, so the explanations stay beside what was
answered.

What else the study page does with each kind:

- **The other side of a pair waits a day.** When one of two linked cards is
  answered, the other is not offered until the next day begins — as Anki
  does with the cards of one note. Cramming ignores it.

- **Recordings.** A flashcard plays the first recording of its front when
  it appears and the first of its back when it is turned, as Anki plays a
  card's sound; an exercise's `audio:` player never plays by itself.
  Whatever is playing stops when the exercise is rated or skipped.
- **The ✥ dragging switch** of an ordering exercise is there too, and says
  the same as on every other page of that browser.
- **An exercise with errors** — should a deck hold one — offers only
  **✎ Edit** and **Skip**.
- **✎ Edit** corrects any exercise in the same form, without touching its
  schedule. The form writes the exercise afresh as it saves, so a fill-in
  exercise comes back with [its blanks renamed and its answers
  first](placement.md#form-rewrites).

**Cram exercises**, on the deck's page, goes through the selected
exercises in random order without changing their schedule: a scored
exercise is checked, a flashcard revealed and then marked **Correct** or
**Wrong** by you, and whatever was wrong comes round again until it is
right.
