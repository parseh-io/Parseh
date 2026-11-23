---
title: Target-language text
weight: 6
description: How words of the language you learn are found, set in their face and direction; whole paragraphs, display lines, [...]{tl} and its tints, faces and vertical columns.
---

The heart of a studio document is the language you are learning — the
**target language** of the front matter's `target:`. Every word of it is
set in that language's own face, at a size of its own (the reading view's
first slider, named after the language, scales it apart from the prose),
and in its own direction: right to left for Persian and Arabic.

There are two ways a word becomes target-language text:

- **It is found by its script.** Persian, Arabic, Hindi, Japanese and
  Chinese have scripts of their own, and the studio finds their words in
  the prose without being told.
- **It is marked**, `[…]{tl}`. That is how a Latin word goes inside a
  Persian sentence, and the only way at all for Italian, French, German,
  Turkish, English, Spanish and Catalan, whose words cannot be told from the
  prose's by their letters.

## Words found by their script

In a document whose target has a script of its own, write the words
straight into the prose. Each stretch of them — a **run** — is found and
set in the target face; in Persian and Arabic, right to left.

```parseh-example
The word سلام *salām* means hello, and می‌روم *mi-ravam* is I go.
Both words of خانهٔ من are one run: words parted by single spaces stay together.
```

What a run takes in, and what ends it:

- **Words parted by single spaces** join into one run in Persian, Arabic
  and Hindi. Japanese and Chinese put no spaces between words, so there a
  run is the characters that touch, and a space ends it.
- **The script's own punctuation and digits belong to it**: the Arabic
  comma `،`, semicolon `؛` and question mark `؟`, the Persian digits
  `۰۱۲۳`, the Devanagari full stop `।`, the Japanese and Chinese `。、「」`
  and full-width signs. So does the zero-width non-joiner of Persian (and
  of Arabic and Hindi), which is part of the word it sits in.
- **Anything from outside the script ends it**: a Latin letter, a western
  digit `0–9`, a Latin comma, full stop, question mark or bracket. A
  phrase with one of these in the middle is cut in two — mark it
  `[…]{tl}` to keep it whole (below).

A run is **opaque**: nothing inside it is read as Markdown, and emphasis
never crosses it ([Paragraphs and emphasis](paragraphs-and-emphasis.md)).
In the reading view a click on a run copies it, and pointing at it opens a
small cloud with its transliteration or reading
([Colours, pronunciation and glosses](colours-and-pronunciation.md)). On
paper a run of up to four words (eight characters in Japanese and Chinese)
is never broken across two lines; a longer one may be. In large print a
line holds fewer words, and the limit shrinks with it: at 20 pt a run of
three words may be broken.

### Whose punctuation?

Persian punctuation — `،` `؛` `؟` — belongs **only inside a Persian
sentence or clause of its own**. Between Persian words that stand in
English prose, the prose's own comma is the right one, and it matters: a
Persian comma next to Persian words is taken into the run, and vanishes
from the prose around it.

```parseh-example
Three words for slow: کند, آهسته, یواش — a list, with the comma of the prose.
A whole Persian question takes its own mark: چرا این‌قدر یواشی؟
```

The same holds for Arabic's marks in an Arabic document.

## Whole paragraphs

A paragraph that is all target language is laid out as a **block** of
its own, in the target's direction — no mark needed. Two kinds are told
apart:

- **A display line** is a paragraph of nothing but the target script and
  spaces, with at least three characters of the script. It is set larger,
  on a line of its own, like a proverb set apart.
- **A target-language paragraph** is one with no Latin letter in it at all
  and at least two characters of the script. Western digits, Latin
  punctuation and emoji may be in it; the whole paragraph is set in the
  target face and direction, right-aligned for Persian and Arabic.

```parseh-example
قطره قطره جمع گردد، وانگهی دریا شود

امروز هوا خیلی خوب است. با دوستم به پارک می‌روم!
```

The first is a display line: Persian letters, a Persian comma, spaces.
The second has a full stop and an exclamation mark, which are Latin, so it
is a Persian paragraph rather than a display line. A Latin-script target
has neither: its paragraphs can never be told from the prose's.

## Marking a stretch: `[…]{tl}`

Square brackets round a stretch, and `{tl}` after them, say *this is the
target language*, whatever is in it:

```parseh-example
[یک فایل PDF]{tl}, *a PDF file*: the Latin letters stay inside the Persian phrase.

[امروز یک فایل PDF برای معلمم فرستادم.]{tl}
```

Inside a line, the stretch becomes **one unit** in the target's direction:
a Latin word, a figure, a bracket or an emoji inside it stays where the
sentence puts it. Alone as a paragraph, it becomes a **block**, exactly
like a target-language paragraph found on its own.

On paper a Latin word inside the stretch is printed in a face that has
Latin letters: the target's own when it has them (Vazirmatn, the Japanese
and Chinese faces), otherwise that of the text round the stretch — Noto
Naskh Arabic, the nastaliq face and the Devanagari faces have none. Latin
words next to each other read left to right, in the order they are
written, in a right-to-left sentence too.

Why the mark is needed: a right-to-left sentence with a Latin word in it
would otherwise be cut, at the Latin word, into two right-to-left runs,
and a left-to-right paragraph places runs left to right — the second half
of the sentence would come first. Marked, the sentence is laid out as one.

The mark's rules:

- **The word in the braces** is `tl`, or the document's own language code
  — `{fa}` in a Persian document, `{ja}` in a Japanese one, `{it}` in an
  Italian one — and a Persian document also takes `{rtl}`, its old name.
  Another language's code is not a mark: in a Persian document,
  `[bello]{it}` stays exactly as typed.
- **No square brackets inside.** The stretch runs to the first `]`.
- **Opaque.** Nothing inside is read: no bold, no italics, no colour, no
  gloss, no link. A `*` is a star.
- `⏎` inside it **breaks the line** (the only thing that is read).
- Emoji are kept on the screen; the PDF, which has no emoji in its fonts,
  drops them from the block.

```parseh-example
The same mark under its other names: [این یک PDF است]{fa}, [این یک PDF است]{rtl};
and [bello]{it} in a Persian document is just text.
```

### Several lines: the long form

A passage of several lines — a dialogue, a verse — is written with its
opening bracket on a line of its own and its closing bracket, with the
braces, on another. The lines between are joined like any paragraph, so
end each one with `⏎` to keep it a line:

```parseh-example
[
— سلام! حالت چطوره؟ ⏎
— خوبم، مرسی. تو چطوری؟ ⏎
— من هم خوبم.
]{tl bg=sand}
```

The passage must stay one paragraph: **no blank line** inside it, and no
line that starts a block of its own — a `- ` or `1. ` list item, a `#`
heading, a `>` line. Any of these breaks the passage, and the brackets are
left showing.

### Its options

After `tl`, inside the same braces, a few words style the block. Each is
offered only where the language has it; elsewhere it is ignored.

| Option | What it does | Languages |
|---|---|---|
| `bg=quote` `bg=sand` `bg=rose` `bg=sage` `bg=lilac` | tints the block's background, with darker variants in the dark theme | all |
| `font=nastaliq` | sets the block in Nastaliq, the flowing hand of Persian poetry and calligraphy | Persian |
| `font=gothic` | sets the block in the plain sans-serif face of Japanese signs and screens | Japanese |
| `vertical` (or `tategaki`, or `mode=vertical`) | sets the block in columns, top to bottom, the columns from right to left | Japanese, Chinese |
| `height=` a number | the height of a column of a vertical block, in em: 8 to 60, 22 when left out | Japanese, Chinese |

```parseh-example
[
بنی آدم اعضای یک پیکرند ⏎
که در آفرینش ز یک گوهرند
]{tl font=nastaliq bg=quote}
```

The five tints:

```parseh-example
[رنگ quote]{tl bg=quote}

[رنگ sand]{tl bg=sand}

[رنگ rose]{tl bg=rose}

[رنگ sage]{tl bg=sage}

[رنگ lilac]{tl bg=lilac}
```

A vertical block is always a whole paragraph — inside a line `vertical`
is ignored — and it is the way Japanese and Chinese poetry and books are
set:

```parseh-example
---
target: ja
---
[
古池や⏎
蛙飛び込む⏎
水の音
]{tl vertical height=8}
```

```parseh-example
---
target: zh
---
[
白日依山尽，黄河入海流。⏎
欲穷千里目，更上一层楼。
]{tl vertical height=14}
```

```parseh-example
---
target: ja
---
[本日休業]{tl font=gothic bg=rose}
```

Inside a line, `bg=` and `font=` style the stretch too:

```parseh-example
A tinted phrase inside a line: [یک فایل PDF]{tl bg=sand}, and one in Nastaliq: [بنی آدم]{tl font=nastaliq}.
```

**On paper** a tint is a tinted panel, and in a PDF printed **Black and
white** a white one in a thin black frame. A vertical block is set in
rotated columns, and its tint is dropped — a tinted slab the height of the
page would help nobody; in large print a column is never longer than the
page. A right-to-left block keeps its Latin words left to right inside it,
and its brackets turned the way the sentence reads.

## Latin-script targets: every run is marked

Italian, French, German, Turkish, English, Spanish and Catalan have no letters of
their own, so nothing is found by its script: **every** word of the target
language you want set as such is marked. Any mark does it:

- `[bello]{tl}`, or the language's code, `[bello]{it}`;
- a colour, `[bello]{teal}`, or a transliteration, `[bello]{translit:bèllo}`;
- any other word in the braces — only `la`, `ltr` and `math` are not
  target language, since they mean something else.

```parseh-example
---
target: it
---
In Italian, [bello]{tl} = *beautiful* and [la casa]{teal} = *the house*;
[ancora]{translit:àncora} = *anchor* carries its pronunciation.

[Una frase intera, in italiano.]{tl bg=sand}
```

A whole paragraph marked `{tl}` is a block, and takes `bg=` like any
other; inside a line a marked word is simply a run of the target, and the
options are not read. There are no automatic paragraphs and no display
lines: marked is the only way.

## Writing it without typing the marks

The editor has two buttons for this:

- **tl** wraps the selected text in `[…]{tl}` — in the long form when the
  selection spans several lines — and takes out any square brackets inside
  it; with nothing selected it puts an empty `[]{tl}` at the cursor.
- **✎** and the language's name — **✎ Persian**, **✎ Japanese** — opens a
  box that writes in the language's direction and face, with the options
  the language has: **Font** where it has a second face, **Background**,
  and **vertical** with its **height** for Japanese and Chinese. Each line
  of the box becomes a line of the passage, `⏎` and all; square brackets
  typed in it are taken out; **Insert** puts the result in as a `[…]{tl}`
  block. In the preview, pointing at a block offers **✎**,
  which opens it in the same box again. A paragraph found on its own stays
  unmarked while it has no Latin letter, and is marked `[…]{tl}` as soon
  as one is added.
