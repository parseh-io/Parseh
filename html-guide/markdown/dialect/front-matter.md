---
title: Front matter
weight: 3
description: The five lines at the top of a document — title, subtitle, note, lang and target — and what each one decides.
---

A document starts with its **front matter**: a few `key: value` lines
between two lines of three dashes. It names the document, says what it is
about, and says which two languages it is written in — the one you are
learning and the one the prose is in.

```parseh-example
---
title: The shape of a Persian word
subtitle: roots, stems and **affixes**
note: Notes for the Tuesday class · کتاب = *book*
lang: en
target: fa
---
The body of the document starts here.
```

The studio reads **five keys**, and only these five:

| Key | What it is | Left out |
|---|---|---|
| `title` | The document's name: the big title at the top, the name on its card in the library, and the name a link to it uses | the first `#` heading of the body; with none, the library calls it *Untitled* |
| `subtitle` | A line under the title, in a lighter colour | no subtitle |
| `note` | A small grey line under the rule below the title | no note |
| `lang` | The language the **prose** is written in: `en`, `it`, `fr`… | the PDF hyphenates as English, but the reading view and the preview take the page for Italian |
| `target` | The language being **learned**: `fa`, `ar`, `it`, `ja`, `fr`, `de`, `tr`, `en`, `hi`, `es` or `zh` | Persian, `fa` |

## title

The title is the document's **name**. It is what the library shows on the
document's card, what the title block at the top of the page shows, and
what another document writes to link to this one:
`[](doc:The shape of a Persian word)`
([Footnotes and links](footnotes-and-links.md#links-to-other-documents)
says how such a link works).

Because a link finds its document by name, **a name belongs to one
document** in a library. A save — **Save**, **Save & view** or Ctrl+S — whose
`title:` names a document that already exists is not written: the studio
opens a dialog, *This name is already in use*, and asks for another name,
for this document or for the other one. Names are compared the way a
Windows or Mac computer compares file names: case does not count, and a
run of spaces counts as one space, so `Verbs of motion` and
`verbs  of MOTION` are the same name. A name may not hold a `|` either
(*This name cannot be used*): a link to it inside a table would split the
cell.

Change the title and save, and the document is **renamed**: every link in
the library that named it by the old name is rewritten to the new one.

When the front matter has no `title:`, the first `#` heading of the body
is the title. Any other `#` heading is dropped — a document has one title.

```parseh-example
# A title from the first heading

When the front matter names no title, the first `#` heading is the title.
```

## subtitle and note

Both may hold the marks a line of prose holds — bold, italics, a colour,
a word of the target language. Both are drawn **only under a title**: a
document with a subtitle but no title shows neither.

## lang

`lang:` is the language of the prose — the language the document is
**written in**, which is usually not the one it teaches. A Japanese lesson
written in Italian has `target: ja` and `lang: it`.

It decides three things:

- **Where the PDF breaks words.** Hyphenation patterns are chosen by it,
  and one language's patterns are worse than none for another: English
  rules chop Italian words in the wrong places. The studio knows `en`,
  `en-gb`, `en-us`, `it`, `fr`, `de`, `tr`, `es`, `pt`, `nl`, `ca`, `ro`,
  `pl` and `ru`, and the three-letter `eng`, `ita`, `fra`, `deu`, `spa`.
  A regional form such as `pt-BR` or `fr-CA` takes its language's
  patterns, and a TeX language name of four letters or more (`italian`,
  `ngerman`) is handed to TeX as it is — used if the TeX installation has
  those patterns, English otherwise. Any other code, such as `fa` or
  `ja`, or no `lang:` at all, is hyphenated as English.
- **Which language the page says it is in.** The reading view and the
  editor's preview tell the browser the prose's language from it, and
  with **justify** on (the reading view's default) the browser breaks the
  words of the page by that language's rules. With no `lang:` the page is
  declared **Italian** — not English, as the PDF assumes.
- **Which way the editor writes.** With `lang: fa` or `lang: ar` the
  editor's source box starts right to left, as a Persian writing a lesson
  of English for Persians needs. The **⇤ RTL editor** button turns it
  either way by hand; its choice is then remembered for that document.

Write it in every document, even an English one: left out, the PDF
hyphenates the prose as English while the screen hyphenates it as
Italian, and neither may be the language you wrote.

## target

`target:` is the language being learned, as a code of the toolbox's
language registry. It decides nearly everything the rest of this section
describes:

- which script the studio looks for, and so which words of the prose are
  found as the target language on their own
  ([Target-language text](target-language.md));
- the face the target language is set in, its direction, and its size
  beside the prose;
- whether a vocabulary heading has a reading field (Japanese does,
  [Headings](headings.md));
- which options a `[…]{tl}` block takes: an alternate face for Persian and
  Japanese, vertical columns for Japanese and Chinese;
- the folder of the library the document is filed in, and the language
  badge on its card. Change the `target:` and save, and the document moves
  to the new language's folder.

```parseh-example
---
title: 日本語のノート
lang: it
target: ja
---
The target is Japanese and the prose Italian: 日本語 is found by its
script and set in the Japanese face.
```

A code the registry does not have is not guessed at: the document is
drawn as Persian, and the editor's preview says so in red above the page —
`unknown target language 'xx' -- rendered as Persian`. The twelve codes
are listed with what each one changes in
[Documents in each language](languages/_index.md).

## The rules of the block

The front matter looks like YAML, the language Hugo and many other tools
use for it, but it is simpler, and a few things follow from that:

- **It must be the first thing in the file.** Blank lines before it are
  fine; anything else, and the `---` is read as a rule in the body (and
  dropped), and the `title:` line under it as a line of text.
- **It must be closed.** A front matter whose closing `---` is missing
  takes the whole document with it: nothing below it is drawn.
- **One key per line, `key: value`.** The key may be written in any case
  (`Title:` is `title:`); the value is everything after the colon, as it
  is — quotation marks included, so write `title: My notes`, not
  `title: "My notes"`. A key written twice counts once, as its last line
  says.
- **Other keys are dropped** without a word: `tags:`, `date:`, `draft:`,
  `weight:` mean nothing here. A document's tags are set on its page, in
  the **Tags** bar under the toolbar, not in the file.
- A value runs to the end of its line: lists and values over several
  lines are not read.

```markdown
---
title: Verbs of motion
subtitle: رفتن, آمدن and their friends
note: for the Tuesday class
lang: en
target: fa
---
```

The **+ New** button of the library starts a document from the chosen
language's starter page, whose front matter is already written: change
the `title:` and write on.
