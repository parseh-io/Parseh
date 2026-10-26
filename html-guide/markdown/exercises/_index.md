---
title: Exercise decks
weight: 60
description: The Exercises door — studio exercises kept in decks and brought back when they are due, the way Anki brings back a card.
---

An exercise on a studio page is done once and forgotten: you answer it, you
press **Check exercises**, and you move on. That is fine for reading, and not
enough for remembering. The hub's fourth door, **Exercises**, is where an
exercise goes to be remembered. It keeps exercises in **decks** and brings
each one back when it is due, sooner when it was hard and later when it was
easy, exactly as Anki brings back a card.

The door is at `/exercises/` in Parseh. On the hub it carries two counts —
how many decks you have and how many exercises are due now — and, like every
door, the counts follow the language chip you picked there.

## What a deck holds

A deck holds studio exercises: the same `:::exercise` blocks a document
holds, all fourteen kinds of them — blanks to fill, sentences to build and
to order, pairs to match, choices, true or false, yes or no, and flashcards
of every kind, with their pictures and recordings. On the study page each
one is shown **unsolved**, as a question, and you answer it as you would on
the page.

```parseh-example
:::exercise true-false
prompt: True or false?
- [سلام]{tl} is said on arriving => true
- [خداحافظ]{tl} is said on arriving => false
:::

:::exercise flashcard
card-type: vocab
target: [نان]{tl}
transliteration: nân
meaning: bread
:::
```

Try them: answer the first and press **Check exercises** at the foot of
this page; click the card to turn it. They are written in the studio's
dialect — this guide's section on the dialect shows every kind, and
[The Parseh dialect](../writing-this-guide/parseh-dialect.md) sums it up —
but you rarely write one by hand: the studio's exercise form writes them for
you. A deck does not care how an exercise was written: once it is in, it is
one exercise with its own schedule.

**A deck has one language.** When you make a deck you say which of the
eleven languages it is for, and every exercise in it is in that language,
drawn in that language's face and direction — right to left for Persian and
Arabic. That is also why a document's exercises are offered only to the
decks of the document's own language.

## The life of an exercise

1. **You write it**, in a studio document (or straight into a deck, with the
   same form the editor uses).
2. **You copy it into a deck**: the **+ Deck** button beside it on the
   document's page, or **+ Add all exercises** for the whole page. A book's
   reader and a video's player send the cards you make there to a deck too.
3. **You study**: **Study now** shows the exercises that are due, one at a
   time. You answer, you see whether you were right, and you say how hard it
   was — **Again**, **Hard**, **Good** or **Easy**.
4. **It comes back** when the scheduler says it should: in a minute if you
   did not know it, in a day, then in a few days, then in weeks and months as
   long as you keep knowing it.

The copy is a copy. Changing the document afterwards changes nothing in the
deck, and studying the deck changes nothing in the document: the deck keeps
its own exercise, its own pictures and recordings, and its own record of
every answer you gave.

## Where to start

New to decks? Three pages take you from nothing to a first session:

1. [The decks page](decks-page.md) — make a deck with **+ New deck**.
2. [Filling a deck](filling-a-deck.md) — copy a document's exercises into it
   with **+ Deck** or **+ Add all exercises**.
3. [Studying](studying.md) — **Study now**, and the four ratings.

The rest can wait until you want it: browsing and tidying a deck, cramming
before a test, the scheduler's arithmetic and its options, and moving decks
between machines. Every page of the section is listed below.

{{< details summary="Where do the words “new”, “learning” and “review” come from?" >}}
From Anki, as does the whole scheme. An exercise you have never answered is
**new**. Once answered, it goes through a few short **learning** steps —
minutes apart — until you know it, and then becomes a **review**: it waits
days, and each time you know it the wait grows. Forgetting a review is a
**lapse**, and sends it back through a short **relearning** step. The
[scheduler](scheduler.md) page has the numbers.
{{< /details >}}
