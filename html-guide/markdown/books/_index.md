---
title: Books
weight: 20
description: The reading editions — the library, the reader, narrations, writing a book yourself, taking it away and bringing it back.
---

A **book** in Parseh is a *reading edition* in the Ilya Frank manner: the
text cut into small pieces — *chunks*, a phrase or a sense group each —
and every chunk glossed where it stands, with its transliteration, the
words it is made of and what it means. You read the sentence whole first,
then chunk by chunk with the help beside it, then the sentence whole again
without the help. A recording of the book can play in step with the text,
a subparagraph at a time.

The **Books** door of the hub opens the library at `/books/`. Everything in
this section is done from there and from the pages it leads to: nothing
here needs a terminal, even the way of adding a book that hands the work to
an AI coding assistant — the folder is made by a button, the assistant is the
one you choose, and you watch the book grow from the library.

## Where to start

Open the library ([The library](doc:The library)), pick a book, and read
([The reader](doc:The reader)). To make a book of your own, start at
[Adding a book](doc:Adding a book); to hear one, at [Adding a
narration](doc:Adding a narration). While you read, flag a chunk without stopping
and come back to it later ([Review later](review-later.md)), or see every word of the
vocabulary lines of a chapter or the whole book in one list ([The vocabulary as a
list](vocabulary.md)); every setting of the
page is in its ⚙ panel ([The ⚙ settings of a page](../getting-started/page-settings.md)).
The pages of this section are listed at
the foot of this one, in the order a book is usually met: finding it,
reading it, hearing it, writing it, taking it away.

## Levels: the same text, several ways

Each subparagraph of a book is set several times over, one *level* after the
other. Which levels there are depends on the language, and the header of
the reader has one button for each, named for what it shows, to show or hide it:

| Language | The levels, by the name on their button |
|---|---|
| Persian | **With vowels** · **Chunks** · **Plain** · **Nastaliq** |
| Arabic | **With vowels** · **Chunks** · **Plain** |
| Japanese | **Furigana** · **Kana only** · **Chunks** · **Plain** · **Vertical** |
| Chinese | **Pinyin** · **Pinyin only** · **Chunks** · **Plain** · **Vertical** |
| Italian, French, German, Turkish, English, Hindi, Spanish, Catalan | **Sentence** · **Chunks** |

The first level is your own attempt at the sentence, before any help arrives; the
chunks level is the help; the others give the sentence again — as
it is really printed, in its other face, or, in Japanese and Chinese, as it is
read aloud. The names are yours to change, and a Persian or Arabic book can put
the vowel marks away: [Levels and their names](levels.md). The list comes from
Parseh's language registry, so a language added to the toolbox brings its own
levels with it.

## Where a book lives

A book is a folder, and nothing anywhere keeps a list of books: a folder
with a `book.json` in it, under its language's folder, is on the shelf.

```text
books/
  persian/
    farsi-shakar-ast/
      book.json      the title, the author, the language
      main.tex       the frame: title page, one \input per chapter
      ch1.tex ...    the text, chunk by chunk, with the glosses
      source/        the original paragraphs, to check the text against
      reading.json   what you folded away
      markdown/      the notes in the seams
      audio/         the recordings (never committed)
      timings.json   where each subparagraph starts and ends
      main.pdf       the printed edition, once built
      reader/        the reading page, built from the .tex
```

The toolbox ships with no book: each language's folder under `books/` holds
only a `.gitkeep` until you add one, bring one back from a bundle or start
an empty one. The files themselves are described in
[What a book is made of](doc:What a book is made of).
