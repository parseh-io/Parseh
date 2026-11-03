---
title: Target language and gloss language
weight: 8
description: Every book, video and document names two languages — the one being learned, and the one its meanings and notes are written in.
---

Everything in Parseh is *about* one language and written *in* another, and
the two need not be the one you would guess: an Italian learning English
wants the meanings in Italian, not in English. So every book, every video
and every studio document names both.

| | The language being learned | The language it is written in |
|---|---|---|
| **A book** | *Language* — `"language"` in its `book.json` | *Glosses in* — `"gloss"` |
| **A video** | *Language* — `"language"` in its `video.json` | *Glossed in* — `"gloss"` |
| **A studio document** | `target:` in its front matter | `lang:` in its front matter |
| **A page of this guide** | `target:` in its front matter | `lang:` in its front matter |

The first decides everything about the **text**: which script is looked
for, which font and direction it is set in, which passes a reading edition
has, which folder it is filed under, which dictionary is looked in, what the
transliteration line is called. The second decides only what the
**meanings** (or the notes) are set in: their direction, their
hyphenation, what the reader calls them.

## Books and videos

You choose both when you add the thing:

- **Add a book** (`/books/add/`) has **Language** (“The language the book
  teaches — it sets the folder it is filed under, the fonts it is set in,
  and the conventions it is annotated by.”) and **Glosses in** (“The
  language the meanings are written in. An Italian learning Persian wants
  them in Italian.”). A note under the second says what the pair you chose
  means; for a left-to-right book the right-to-left glosses, Persian and
  Arabic, are greyed out, because a right-to-left gloss of a left-to-right
  text cannot have its vocabulary lines set in order.
- **Add a video** (`/youtube/add/`) has **Language** and **Glossed in**,
  with English chosen; the page remembers your gloss language for the next
  video.

Both selects of the gloss list the languages Parseh teaches, then
the languages it only **writes in**: Portuguese, Dutch, Catalan, Romanian,
Polish, Russian, British English and American English. A book glossed in
Portuguese gets its meanings in Portuguese, set and hyphenated as
Portuguese — and nothing else, because Portuguese has no folder, no fonts
and no note types here: nobody studies it in Parseh.

Neither choice is changed later from the **book info** or **video info**
sheet, which edit titles, authors and the like. **A book or a video that
does not say what it is glossed in is glossed in English**, which is what
everything made before the choice existed means — nothing had to be
changed for it.

A book or video **glossed in the language it teaches** — English glossed in
English, Italian in Italian — is a monolingual edition: its meanings are
definitions rather than translations. That is the book's choice, not a
property of the language, and Parseh treats it as such (the add page says
so).

### What the gloss language changes elsewhere

- **The labels.** In a book's chunk sheet the box a meaning is typed into
  is labelled with the gloss language (*italian*), and a card's two sides
  are named after both languages (*Persian → English*); in a monolingual
  edition they become *meaning*, and *word → meaning*.
- **The reading help.** A [corpus](translated-sentences.md) and a
  [translation model](translation-model.md) are pairs: the reader asks for
  the one matching its own gloss language, so a Persian book glossed in
  Italian needs a Persian–Italian corpus, and can have no model at all,
  since Mozilla's pairs all go through English. The
  [dictionaries](dictionaries.md) explain every word in English whatever
  the gloss language, and a verb entry the dictionary drafts for a book not
  glossed in English leaves the meaning empty for you to write.
- **Anki cards** carry the gloss language with them, so an Italian or an
  Arabic meaning shows as itself, in its own direction.

## Studio documents

A studio document says the same two things at its top:

```yaml
---
title: The particle は
target: ja
lang: it
---
```

- **`target:`** is the language being learned, a registry code. Without
  one, a document is about **Persian** — Parseh's first language, and what
  everything written before the others arrived was about. A new document
  starts in the language the [language chips](language-chips.md) are set
  to, unless they are set to *all*. The document is filed in the library
  under that language, and moved there when a save changes it.
- **`lang:`** is the language the notes are written in. It is not
  cosmetic: it chooses the hyphenation of the PDF. Without one, the
  document is set as English. It takes the same codes a gloss does. It
  also sets which way the editor's source box runs to begin with — right to
  left for `lang: fa` or `lang: ar` — until you press **⇤ RTL editor** or
  **⇥ LTR editor** for that document.

A Japanese note written in Italian has `target: ja` and `lang: it`. When
you bring in a Markdown file whose header lacks them, the studio asks in a
dialog — **Written in** and **The language it is about**, a select each,
the second set to the chip's language when one is picked — and adds the
lines it was missing.

The guide you are reading works the same way: each page names its target,
Persian by default, and each [`parseh-example`](../writing-this-guide/code-blocks.md#showing-markdown-and-what-it-becomes)
may name its own:

```parseh-example
---
target: es
lang: en
---
[El libro]{tl} = *the book* — a Spanish example on a page whose other
examples are Persian.
```

## Why the keys are called `fa` and `en`

If you ever open a card file, an `annotations.json` or a chapter's `.tex`,
you will find the text under the key **`fa`** and the meaning under
**`en`** — whatever the languages. They are the names of two slots, left
from the days when Persian and English were the only two languages: `fa` is
*the text in the language being learned*, and `en` is *the meaning, in the
gloss language*. An `en` holding Italian is not a mistake; it is a book
whose gloss is `it`. Renaming them would have meant rewriting every book,
video and card, to say what `"gloss"` already says.
