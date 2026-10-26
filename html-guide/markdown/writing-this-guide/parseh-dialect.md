---
title: The Parseh dialect
weight: 3
description: Target-language text, lemmas, boxes, exercises and formulas, as the studio draws them — and where the dialect wins over Hugo.
---

Everything a document in Parseh's studio can hold, a page of the guide can
hold too, and it is drawn by the studio's own code: the parser that reads
the dialect and the renderer that draws it are the studio's, imported by the
compiler, never copied. A lemma heading here is a lemma heading there, down
to the pixel. The studio's own reference for the dialect is
`markdown/README.md`; this page shows each construct working, with a
[`parseh-example`](code-blocks.md#showing-markdown-and-what-it-becomes)
block: the Markdown above, what it becomes below.

Every example here is Persian unless it says otherwise — a page is read as
Persian when its front matter names no `target:`, as a studio document is.
An example may carry its own front matter, as a document does, and name
another language.

## Target-language text

In a script language — Persian, Arabic, Hindi, Japanese, Chinese — text in
the target's script is found on its own, set in the language's face and,
for Persian and Arabic, right to left. A paragraph with no Latin letters in
it becomes a whole block in the target language. `[…]{tl}` marks a stretch
by hand, which is how a Latin word goes inside a Persian sentence, and the
only way at all in a Latin-script target, where nothing can be found by its
script.

```parseh-example
The word کتاب means *book*, and کتاب‌ها is its plural.

[این یک PDF است]{tl} — a Persian sentence with a Latin word in it.

من کتاب را خواندم، و بعد به خانه رفتم.
```

```parseh-example
---
target: it
---
In an Italian lesson every run is marked: [bello]{tl} = *beautiful*,
[libro]{translit:ˈli.bro} = *book*, and [la casa]{teal} = *the house*.
```

A target-language stretch is opaque: nothing inside `[…]{tl}` is read as
Markdown, so a `*` there is a star.

### Its attributes

```parseh-example
[تو را من چشم در راهم ⏎ شباهنگام]{tl font=nastaliq bg=quote}
```

`font=nastaliq` sets a block in the language's alternate face, `bg=` tints
it (`quote`, `sand`, `rose`, `sage`, `lilac`), and in Japanese and Chinese
`vertical` sets it in columns, `height=` of them in em. `⏎` breaks a line.

```parseh-example
---
target: ja
---
[
春はあけぼの。やうやう白くなりゆく山ぎは、
すこしあかりて、紫だちたる雲のほそくたなびきたる。
]{tl vertical height=12}
```

## Colours, transliterations, readings

```parseh-example
[تند]{teal} fast, [آهسته]{translit:âheste} slow, [کتاب]{#8E2B34 translit:ketâb}
in a colour of your own, and [خانه]{crimson} = *house*.
```

The colours are the studio's five — `crimson`, `indigo`, `teal`,
`violet`, `amber` — or any `#RRGGBB`. `translit:` (and in Japanese
`kana:`) are shown over the word when you point at it. After a target
word, ` = *gloss*` greys the `=`: that is a gloss, and the studio collects
glosses into a table.

```parseh-example
---
target: ja
---
[漢字]{kana:かんじ translit:kanji} = *Chinese characters*
```

## Lemma headings

A `##` heading whose fields are separated by `|` and which starts with a
target-language word is a lemma: the headword, its transliteration, its
etymology. In Japanese the reading comes second.

```parseh-example
## [کتاب]{teal} | ketâb | Arabic *kitāb* | = *book*

The entry itself, as ordinary paragraphs.
```

## Boxes

A `>` block is the studio's tinted box, not a quotation, and it can hold
anything a page can: lists, tables, even an exercise.

```parseh-example
> **Remember.** A box holds anything:
> - a list,
> - a formula, [e^{i\pi} + 1 = 0]{math},
> - a word, [کتاب]{tl}.
```

## Latin blocks and marks

```parseh-example
[A paragraph of *Latin-script* prose laid out on its own, centred and tinted.]{la align=center bg=sage width=70}

A form that is wrong: ✗[کتابا]{tl}; one that is right: ✅ [کتاب‌ها]{tl}.
From here -> to there, → and ⏎ a line break.
```

## Formulas

`[…]{math}` inside a line and `:::math … :::` on lines of their own are
LaTeX, drawn by MathJax. `$…$` is not a formula, here or in the studio.

```parseh-example
The area of a circle is [\pi r^2]{math}.

:::math
\int_0^1 x^2\,dx = \frac{1}{3}
:::
```

## LaTeX drawings

What MathJax cannot draw — a reaction, a molecule, a plot — LaTeX draws: in
a line with `[…]{latex}`, or on lines of their own between `::::latex` and
`::::`, four colons. The guide is compiled where there may be no TeX, so
these are pictures made beforehand and kept in `markdown/drawings/`: a new
one is made with `build.py --draw`, and a compile that finds one missing
says so ([Compiling and publishing](compiling.md#latex-drawings)).

```parseh-example
Water, [\ce{H2O}]{latex chemistry}, from hydrogen and oxygen:

::::latex chemistry {width=45 align=center}
\ce{2H2 + O2 -> 2H2O}
::::
```

## Exercises

`:::exercise <type>` … `:::` is one of the studio's fourteen exercises,
and it works on the page as it does in the studio: blocks to drag or tap
into place, answers to choose, cards to turn. **Check exercises** at the
end of the page marks them all.

```parseh-example
:::exercise fill-blanks
prompt: Put the words where they belong.
text: من [[blank1]] را خواندم
- [blank1] کتاب
- [ ] خانه
explanation-correct: کتاب — *the book*.
:::
```

```parseh-example
:::exercise flashcard
target: کتاب
transliteration: ketâb
meaning: book
:::
```

```parseh-example
:::exercise match-translations
prompt: Match each word with its translation.
- [کتاب]{tl} => book
- [خانه]{tl} => house
- [آب]{tl} => water
:::
```

The [showcase](../showcase.md) has one of each kind, in Persian,
Japanese and English. The fields each exercise takes are listed in
`docs/studio-exercises.md`.

## Recordings and videos

A picture line whose file is a recording — `.mp3`, `.m4a`, `.ogg`, `.wav`
and the other formats the studio plays — is a player, and `@[…](…)` is a
YouTube video, both laid out as the studio lays out a figure:

```markdown
![The word, read aloud](sounds/ketab.mp3){width=60 start=0:01.5 end=0:03}
@[The lesson on YouTube](https://www.youtube.com/watch?v=dQw4w9WgXcQ){width=80 align=center start=30}
```

[Pictures, recordings and videos](pictures.md) has more.

## Links to other pages

The studio's `[label](doc:…)` links one document to another; here it links
to the page of the guide whose **title** is given: [Shortcodes](doc:Shortcodes),
and `[](doc:Code blocks)`, left empty, shows the title: [](doc:Code blocks).

## Where Parseh wins {#where-parseh-wins}

Some text means one thing to Hugo and another to the studio. In every such
case the page reads it the studio's way:

| You write | Hugo would draw | The guide draws |
|---|---|---|
| `> text` | a quotation | the studio's tinted box; every line needs its `>` |
| `## a \| b \| c` | a heading “a \| b \| c” | a lemma: headword, transliteration, etymology |
| `## Title` | a heading | a numbered section, “1. Title”, with Hugo's address |
| `## 3. Title`, `## Title = *x*` | the heading as written | “1. Title”: the typed number and the gloss are taken off |
| `[text]{…}` | the text, then `{…}` | a mark: `{tl}`, a colour, `{translit:…}`, `{math}`, `{la}`… |
| `![cap](pic.png){width=50}` | a picture, then `{width=50}` | the studio's figure, laid out as the braces say |
| `![cap](sound.mp3)` | a broken picture | a player |
| `@[cap](youtube address)` | text | a video |
| `*x*`, `**x**` | emphasis anywhere | the studio's: never inside a word, never across a target-language run |
| `- **Label** text`, every item | a list | the studio's description list |
| a line under a list item, at the margin | more of the item | a paragraph after the list; indented two spaces, more of the item |
| `[^1]` twice | one note, cited twice | two notes, one per reference, each with its hover cloud |
| `^[a note]` | text | a footnote written in place |
| a table | GFM's rules | GFM's, with the studio's look; a cell of `—`, `--` or `-` is empty; the rows end at the first line without a `\|` |
| `->` | `->` | an arrow, → |
| `✗word`, `✅`, `⏎` | text | wrong form, tick, line break |
| `word = *gloss*` after a target run | text | a gloss, its `=` greyed |
| `:::exercise`, `:::math` | text | an exercise, a formula |
| `[label](doc:Title)` | a link to “doc:Title” | a link to the page with that title |
| `<b>html</b>` | nothing (Hugo leaves raw HTML out) | the tag shown as text, as in the studio; an HTML comment is left out |
| lines indented four spaces | a code block | ordinary text: code is always fenced |

And where the studio has no reading of its own, Hugo's holds: code spans
are opaque (`` `**b**` `` is two stars, a b and two stars — in the studio
it would be bold), links take titles and reference definitions, lists nest
to any depth and keep their start number, a heading may be written with
`===` or `---` under it and go down to level six, and the rest of
[Hugo’s Markdown](markdown.md).

One case goes Hugo's way on purpose: a **blank line between two list
items** makes one spaced-out list, numbered on. The studio would end the
list there and number the next one from 1 again — it has no list item of
more than one line — but a page of this guide needs items that hold more
paragraphs, a code block or a box, and lists that count on across them.
