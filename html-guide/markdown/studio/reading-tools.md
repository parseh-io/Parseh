---
title: Reading, annotating and practising
linkTitle: Reading and practising
weight: 8
description: On the document page — copy a word, inspect or edit its pronunciation, drill the glosses, check the exercises, enlarge a card, copy exercises into a deck.
---

A document's page is made to be worked on as well as read. Linguistic
annotations can be inspected and edited on the typeset sheet. Foreground
colour is an authoring operation in Studio's source editor.

## Copying a word

**Click any word or phrase of the target language** and it is copied to
the clipboard, ready to paste into a dictionary: *Copied: …* says what.
(A browser that refuses the clipboard says *Clipboard unavailable*.)

A footnote's number opens its note in a small cloud when you point at it
(a tap, on a phone); the notes are also listed at the end of the document.

## Pronunciation and reading {#colours-and-transliterations}

**Point at a word of the target language** and a small cloud opens over it:

- At its head, the word's **transliteration** (or pronunciation, or
  pinyin, or rōmaji: each language names its own). Click it to edit it in
  place; a word that has none shows a **+**, which opens the same empty
  field. Enter saves, Escape cancels, a click elsewhere saves. Saving an
  empty field takes the transliteration away. For Japanese, the **kana**
  reading has a field of its own above it.

The cloud has no colour picker or swatches. Colours are applied in the
[source editor](editor.md#insert-at-cursor) by selecting exactly the letters
to colour. Existing colours remain visible while the cloud is open. A
partially coloured word opens one cloud for the complete word, and copying it
copies its complete plain text.

A lemma heading already carries its transliteration in the heading itself,
so it does not open an empty cloud merely to offer no action. It can still be
coloured by selecting its source text in Studio. The same linguistic cloud
works in [the editor's preview](editor.md#tools-in-the-preview).

> **Which word is which.** The same word can stand in a document many
> times; the page counts which occurrence you pointed at, and the Markdown
> changes at exactly that one. For a Latin-script target language — Italian,
> French, German, Turkish, English, Spanish, Catalan — only the runs marked as the
> target language (`[parola]{tl}` or any mark on them) are words of it: the
> studio cannot tell the rest apart from the prose.

**Pictures, players and Latin blocks** are laid out with the mouse too: a
click on a picture or a Latin block, or on **⚙ layout** at a player's
corner, opens its panel — see
[Pictures and recordings in a document](editor-media.md#laying-out).

## ⇄ Glosses

A gloss is a word of the target language followed by its translation in
italics — `کند = *slow*` — anywhere in the document. **⇄ Glosses**, under
**☰ Contents**, gathers every one of them into a window of their own, with
nothing to keep in sync by hand. The button is greyed out when the
document has none.

**Table** lists them in three columns — the word, its transliteration, its
translation — and a fourth, the reading, for Japanese. The glosses come from
the paragraphs, headings, bulleted lists, tables, boxes, Latin blocks and
footnotes; a lemma heading's own translation, written at its end
(`## کند | kond | … | = *slow*`), is there too. A missing transliteration is
taken from another mark or lemma heading of the same word.

- **The filter box** narrows the table to the rows where any column holds
  what you type.
- **A column's header** sorts by it, a click at a time: A→Z, then Z→A,
  then back to the order the glosses appear in the text, which is where the
  table starts. The target column sorts as its own language does, and the
  transliteration ignores accents and case. A column nothing fills is not
  sortable, and says so.
- **Lemmas only** — when the document has lemma headings with
  translations — narrows the table and the flashcards to those: the
  document's word list, without everything it glosses in passing.

A row in red is a gloss written without italics (`کند = slow`): only the
one word after the `=` could be taken as its translation, and the **!**
beside it says so and how to write it.

**Flashcards** is the same glosses as a drill. A card shows a word of the
target language; click it, or press Space, to see its reading,
transliteration and translation (**Show answer** and **Hide answer** do the
same), and **Next →** — or → or Enter — goes on. The cards are dealt from a
shuffled deck, so every gloss comes once before any comes again; the
counter says where you are, and the deck is shuffled anew at its end.

Escape, **✕** or a click beside the window closes it.

## Exercises

The document's exercises are drawn unsolved, ready to be answered: the
blocks shuffled, the choices mixed, the blanks empty. How each kind is
written and answered is in the section of its own,
[Writing exercises](../dialect-exercises/_index.md).

**Check exercises**, at the end of the page, checks them all at once: each
answer marked right or wrong, the explanations and the answer's pictures
and recordings shown, and the score beside the button — *7 / 9 correct*.
Change an answer and that exercise's marks are cleared — its explanation,
and the answer's picture and recording, put away again — and the score
disappears until you press **Check exercises** again. Flashcards are not
scored.

In an exercise's head, beside its kind:

- **⤢ Enlarge** is on every flashcard: the same card in a window over the
  page, laid out as it is on the page and magnified whole — every field in
  its place, a right-to-left paragraph on the right, pictures and players
  keeping their proportions — as large as the window holds. On a phone it
  is laid out a little narrower and magnified up to twice, a line whole on
  the page staying whole (only a paragraph that wraps there may wrap at
  other words). A click on the card, Space or Enter turns it, and the card
  on the page with it; the 🔊, a player or a link does its own thing;
  Escape or **✕** closes the window.
- **Hide transliterations** / **Show transliterations**, on a card that has
  a transliteration: one switch for every flashcard, remembered in this
  browser. It is the same switch as **Hide transliterations** in the ⚙ panel's
  **Exercises** group: turn one and the other follows.
- **✥ dragging on** / **✥ dragging off**, on an exercise whose blocks are
  put in order: whether the blocks can be dragged — **Drag to answer** in the ⚙ panel's
  **Exercises** group, the same switch. It starts off on a touch
  screen, where the arrows on each block work better, and the choice is
  remembered in this browser for every page.
- **+ Deck** — below.

This guide's pages draw exercises the way a document's page does, so you
can try all of it here: turn the card, open it with **⤢ Enlarge**, hide its
transliteration, answer the statements, and press **Check exercises** at the
end of this page.

```parseh-example
:::exercise flashcard
card-type: vocab
target: رفتن
transliteration: raftan
meaning: to go
:::

:::exercise true-false
prompt: True or false?
- رفتن means to come. => false
- آمدن means to come. => true
:::
```

## Into a deck: + Deck and + Add all exercises {#decks}

The **Exercises** door keeps exercises in decks and brings each one back
when it is due, as Anki does (see the
[exercises section](../exercises/_index.md)). From a document's page, two
buttons fill a deck.

**+ Deck**, in an exercise's head, copies that exercise. The dialog —
*Copy this exercise into a deck* — offers the decks of the document's
language, the one used last already chosen, and **+ New deck…** at the end,
which asks for **Name of the new deck**. **Copy** copies the exercise
exactly as it is written, with the footnotes it calls, every picture and
recording it names, and the document's tags. The deck remembers where it
came from; later edits to the document do not change the copy.

- An exercise the deck already has is added again only if you say so:
  *This exercise is already in “…” — add it again?*
- If the document was saved elsewhere since the page loaded, the copy is
  refused — *This page is out of date — reload it, then copy* — since the
  button could otherwise pick the wrong exercise.
- An exercise that shows errors has no **+ Deck**; a deck would refuse it.

**+ Add all exercises**, in the top bar, copies many at once. Its dialog —
*Add all exercises to a deck* — lists every exercise that has **+ Deck**, in
the page's order, each ticked, with its number, its kind and its first
words. Untick the ones to leave out (**Select all** and **Select none**
help). **Show gloss flashcards (N)** adds the document's glosses to the
list, as vocabulary flashcards to tick too. **Add again the ones this deck
already has** does what it says; otherwise those are left out. Choose the
deck, and **Add N exercises** copies them one after another, *Adding 3 of
12…*. The message at the end says how many went in and what was left out; a
page gone out of date stops the run, and a new deck that received nothing
is taken away again.

The editor's **Exercises ▾ → Load from a deck…** goes the other way: see
[Exercises in the editor](editor-exercises.md#load-from-a-deck).
