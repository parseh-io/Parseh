---
title: Fields every exercise takes
linkTitle: Common fields
weight: 2
description: The prompt and its regular-weight passages, the explanations, a picture and a recording for the question and for the answer, pictures inside the text, the writing direction, and formulas.
---

Besides the fields and rows of its own type, every scored exercise takes
the same handful of fields. This page describes them; the page of each
family lists the rest.

| Field | What it holds | On which types |
|---|---|---|
| `prompt` | the instruction or question above the activity | all (the form offers it on all but a flashcard); on a [follow-up](follow-up.md) the text the steps are about |
| `explanation-correct` | shown after the check | all but a flashcard; on a follow-up, after its last step, by the result of the whole chain |
| `explanation-incorrect` | shown after a wrong answer | all but a flashcard |
| `image`, `image-answer` | a picture with the question; one shown once it is answered | all but a flashcard |
| `audio`, `audio-answer` | a recording with the question; one heard once it is answered | all but a flashcard |
| `content-direction` | `target`, `rtl` or `ltr`: the direction the whole activity is laid out in | all (the form offers it on all but a flashcard) |
| `text` | the sentence with its blanks | [`fill-blanks`](placement.md#fill-blanks) |
| `answer-direction` | `rtl` or `ltr`: the way the answer's row of words runs | [`construct-sentence`](placement.md#construct-sentence) |
| `direction` | which side is shown first | [matching](matching.md#which-side-is-shown), [flashcards](flashcards.md#which-side-comes-first) |
| `card-type` and the card's fields | the card's kind and its text, pictures and recordings | [`flashcard`](flashcards.md) |

A flashcard's own pictures and recordings are its sides' — `front-image`,
`back-image`, `front-audio`, `back-audio` — and a card that is given
`image:` or `audio:` says so rather than ignoring it.

## The prompt

`prompt:` is what the learner reads first: an instruction, a question, a
passage to read. It is **bold** by default, since it is usually an
instruction, and it takes the whole inline dialect.

- **Regular weight.** Wrap a stretch in `[…]{no-bold}` to set it in
  regular weight, on the page and on paper alike — a reading passage after
  the instruction, say. The wrapper may hold a target-language mark, with
  its own line breaks inside it: `[[دیروز دوشنبه بود.⏎امروز سه‌شنبه است.]{tl}]{no-bold}`.
  Only a prompt reads `{no-bold}`: an explanation or an answer is not bold
  to begin with.
- **Lines.** `⏎` breaks the prompt's line, and `prompt: |` with the lines
  indented under it keeps each line as a line, and a blank line as a blank
  line.
- **Right-to-left lines.** In Persian or Arabic, a line of the prompt that
  is wholly in the target language is set as a block of its own, from the
  right — on paper too, down to its last line — while the instruction
  before it keeps its own alignment.
- **What the form starts with.** A new exercise in the form begins with a
  prompt of its type — *Drag the blocks into the blanks.*, *Decide whether
  each statement is True or False.* — to keep or to change.

```parseh-example
:::exercise true-false
prompt: Read the two sentences, then judge each statement.⏎[[دیروز دوشنبه بود.⏎امروز سه‌شنبه است.]{tl}]{no-bold}
- [امروز سه‌شنبه است.]{tl} => true
- [فردا دوشنبه است.]{tl} => false
explanation-correct: *Yesterday was Monday, today is Tuesday* — so tomorrow is Wednesday, چهارشنبه.
:::
```

A flashcard takes a `prompt:` too, drawn above the card, although the form
does not offer one.

## Explanations

An explanation appears when the exercise is checked. There are two
fields, and how many you fill decides how they behave:

| You write | After a right answer | After a wrong answer |
|---|---|---|
| `explanation-correct` only | it | it — one neutral explanation, shown either way |
| `explanation-correct` and `explanation-incorrect` | the first, framed green | the second, framed red |
| `explanation-incorrect` only | nothing | it |

So either result-specific text may be left empty: write only
`explanation-incorrect` when nothing needs saying after a success. The
older single field `explanation:` is still read, as a neutral explanation.
Explanations are hidden until the check and hidden again when the answer
is changed. The editor's preview, which draws every exercise solved,
shows the neutral or right-answer explanation from the start, and never
the one for a wrong answer — so an exercise with only
`explanation-incorrect` shows none there. And explanations are **never
printed**: paper is the unsolved exercise.
In the form they are **Shown when the answer is correct** and **Shown when
the answer is incorrect**, under *Explanation after checking (optional)*.

```parseh-example
---
target: es
---
:::exercise single-choice
prompt: Choose the right form: *Yesterday I __ to the cinema.*
- [ ] [voy]{tl}
- [x] [fui]{tl}
- [ ] [iré]{tl}
explanation-correct: [Ayer]{tl}, *yesterday*, asks for the past: [fui]{tl}, from [ir]{tl}.
explanation-incorrect: Look at *yesterday*: the verb must be in the past, [fui]{tl}. [Voy]{tl} is *I go*, [iré]{tl} *I will go*.
:::
```

## A picture with the question, and one with the answer

```markdown
image: images/map.png
image-answer: images/map-answered.png {width=45 align=center}
```

- **`image`** is shown between the prompt and the activity, and printed
  there in the PDF.
- **`image-answer`** is kept back until the exercise has been answered —
  right or wrong — and then appears above the explanations: on the page, on
  a deck's study page, and from the start in the editor's preview. Changing
  the answer hides it again with the rest of the result. It is never
  printed.

Each names a file under `images/` — `.png`, `.jpg`, `.svg`, or `.pdf`,
which is drawn through the picture the studio makes of it — and any other
value is an error. Each may carry a figure's layout in braces:
`width=` is a share of the text column, from 5 to 100 per cent, and
`align=` is `left`, `center` or `right`. Said nothing, a picture takes 60
per cent of the column, on the left, as a figure does; screen and paper
place it alike.

In the form, *Pictures (optional)* has the two fields, each with
**Upload…**, which stores the file in the document's own `images/` and
fills in its path, and **Size and position** (*Width (% of the column)*
and *Where it sits*). A document must have been saved once before anything
can be uploaded into it.

```parseh-example
---
target: tr
---
:::exercise single-choice
prompt: Which word means *house*?
image-answer: images/starter-house.svg {width=30 align=center}
- [x] [ev]{tl}
- [ ] [elma]{tl}
- [ ] [kitap]{tl}
explanation-correct: [ev]{tl} = *house*; [elma]{tl} is an apple, [kitap]{tl} a book.
:::
```

## A recording with the question, and one with the answer

The same pair over again, for sound: `audio:` plays with the question,
`audio-answer:` once the exercise has been answered, shown in the same two
places and held back on the same rule.

```markdown
audio: audio/cafe.mp3 {start=1:05.2 end=1:09}
audio-answer: audio/cafe-slow.mp3 {width=45 align=center}
```

Each names a file under `audio/` — MP3, M4A, AAC, Ogg, Opus, WAV, FLAC or
WebM — and takes a picture's `width=` and `align=`, and one thing more: a
**clip**, `start=` and `end=`, in clock time (`1:05.2`, `1:02:03`) or in
seconds (`65.2`). A player given a clip plays that stretch and no more;
either end may be left out.

The recording is **a player with its controls**, not a card's 🔊: an
exercise's recording is listened to again, wound back and stopped.
Nothing plays by itself — a recording is there to press, as a picture is
there to look at. The answer's recording, hidden again when the answer is
changed, stops as it goes, and whatever is playing stops when a deck's
study page moves on. On paper, which cannot play it,
the question's recording is a small card saying ♪ *audio*, the file's name
and its stretch (`1:05–1:09`, or `dal 1:05` / `fino a 1:09` when only one
end is given); the answer's is not printed.

In the form, *Recordings (optional)* has the two fields, each with
**Upload…** and **Size, position and clip**: the width and the side, and
**Play from** and **Play to**.

```parseh-example
---
target: tr
---
:::exercise single-choice
prompt: Listen. Which word names this sound?
audio: audio/starter-chime.mp3 {width=50 align=center}
- [x] [zil]{tl}
- [ ] [elma]{tl}
- [ ] [ev]{tl}
explanation-correct: [zil]{tl} is a bell, and the sound of one.
:::
```

## Pictures inside the text

A picture may also sit **inside** a prompt, an answer, a pair, a sentence,
an explanation or a card: write `![a description](images/name.png)` in the
text. The description is what a screen reader says. On the page such a
picture is at most 10 em wide and 8 em tall, in line with the words; on
paper it takes the `{width=…}` written after it as its share of the line
(60 per cent when nothing is said), and at most an eighth or so of the
page's height. Only pictures go inline: a recording's line inside a row is
shown as the text it is.

```parseh-example
---
target: ar
---
:::exercise single-choice
prompt: Which picture shows a [بيت]{tl}?
- [ ] ![an apple](images/starter-apple.svg)
- [x] ![a house](images/starter-house.svg)
explanation-correct: [بيت]{tl} is a house; an apple is [تفاحة]{tl}.
:::
```

The picture travels with the exercise when it is copied into a deck.

## The writing direction: `content-direction`

The activity — its answers, its blanks, its blocks — is laid out in the
direction of the document's prose, unless you say otherwise:

| Value | The activity runs |
|---|---|
| `target` | in the target language's direction: right to left in Persian and Arabic, left to right elsewhere |
| `rtl` | right to left |
| `ltr` | left to right |
| (none) | as the prose runs — except a fill-in sentence written wholly in a right-to-left target, which follows its language by itself |

An explicit setting is always the author's word: nothing overrides it. On
paper it decides how a fill-in sentence is set (a right-to-left one flush
right, its blanks where they are read), and `ltr` keeps a matching entry
or a true/false statement flush left even when it is wholly Persian or
Arabic. In the form it is *Writing direction of the activity*:
**Automatic**, **Use Arabic direction** (the name of the document's
language), **Right to left**, **Left to right**.

```parseh-example
---
target: ar
---
:::exercise choose-all
prompt: Choose every word that names something to eat.
content-direction: target
- [x] خبز
- [ ] كتاب
- [x] تفاحة
- [ ] بيت
- [x] جبن
explanation-correct: خبز *bread*, تفاحة *an apple* and جبن *cheese*; كتاب is a book, بيت a house.
:::
```

`content-direction` sets the direction of the activity as a whole. Two
other fields are narrower: `answer-direction` sets only the way a
construct-the-sentence answer's words run
([Placement](placement.md#construct-sentence)), and `direction` which side
of a pair or a card is shown first ([Matching](matching.md#which-side-is-shown),
[Flashcards](flashcards.md#which-side-comes-first)).

## Formulas

A formula is `[a^2+b^2=c^2]{math}` — LaTeX, anywhere prose goes: a prompt,
a fill-in sentence, an answer, a pair, a card. Neither `$` nor `\[` is a
marker in this dialect. The formula may hold brackets of its own
(`[x \in [0,1]]{math}`), since it is read up to the `]{math}` that closes
it. **A blank may not sit inside a formula** — `[[slot]]` cuts the sentence
in pieces, and half a formula is nothing — so put the blank beside it. In
the form, **∑ Maths…** opens a sheet that draws the formula as you type it
and writes it into the field you were last in.

```parseh-example
---
target: it
---
:::exercise fill-blanks
prompt: Complete the sentence.
text: [La derivata di]{tl} [x^2]{math} [è [[d]].]{tl}
- [d] [2x]{math}
- [ ] [x]{math}
- [ ] [x^3/3]{math}
:::
```
