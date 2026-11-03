---
title: Glossing captions with an LLM
weight: 9
description: The player's gloss with an LLM panel — picking a run of captions, the two checkboxes, the prompt, the answer pasted back, the report — and why a gloss already written is never touched.
---

The add page has an LLM gloss a whole video before it reaches the shelf
([Adding a video](adding-a-video.md)). This panel does the same for **part
of a video already in the player**: the phrases of a video you started
empty, a run the model skipped, a caption whose gloss you deleted to have it
written again. Any chatbot will do, in another tab, with nothing installed;
Parseh sends nothing anywhere — you carry the prompt to the chatbot and its
answer back — and the answer is written **phrase by phrase, through the
same door as the ✎ form** ([Editing a phrase](editing-a-phrase.md)).

What it fills is the phrases **nobody has glossed yet**. A gloss already in
the video is left exactly as it is, whatever the answer says — not because
the prompt asks the LLM to leave it alone (it does), but because Parseh
itself refuses to change it when the answer is put in. Two checkboxes widen
that, and only when you tick them ([The two checkboxes](#the-two-checkboxes)).

## Picking the captions

**gloss with an LLM**, in the player's bar, opens the panel **gloss a
stretch with an LLM**. Its two slots, **from** and **to**, say *click a
caption* until they are set.

While the panel is open, **a click on a caption line picks it instead of
playing it**: the first click sets **from**, the second sets **to** (the
two are swapped if the second is the earlier), and a third starts again.
Each slot then shows the caption's number and its time (*caption 12,
1:02*), and the run between them is highlighted in the transcript. The
video pauses while the panel is open, so that the transcript holds still
under your hand. **✕** or **Esc** closes the panel: the video plays on if
it was playing, a click on a line plays it again, and the picks are kept
for the next time the panel is opened.

A caption in another language inside the run — the English opening of a
lesson — goes into the prompt only so that the LLM can follow what is said,
and so does a phrase marked plain: neither is ever glossed. Past 400
phrases the panel warns that the LLM may answer over several messages:
paste them all, one under the other.

## The two checkboxes

| Checkbox | Ticked, it means |
|---|---|
| **re-gloss what is already glossed** | *its glosses are not sent, and the answer replaces them*: every phrase of the run is glossed afresh |
| **also fill the empty boxes of partly glossed chunks** | every phrase that already has a gloss has its **empty** boxes filled, and keeps the ones it has — whole glosses included (below). Unticked, *a chunk with any gloss is left exactly as it is* |

With neither ticked (the way the panel opens), a phrase with nothing written
in it is glossed, and every other phrase is sent with its gloss, so that the
new glosses agree with it, and is kept whole.

**The second box reaches whole glosses too.** It is there for a phrase
glossed in part — the meanings typed, the transliterations still to come —
but what it asks for is *every* empty box of every phrase that has a gloss.
That includes a vocabulary line left empty on purpose, because its words
were given earlier (Frank's repetition rule), and, in a language written in
Latin letters, where the transliteration is optional, a transliteration
left out. The prompt tells the LLM to fill a box like that only where the
conventions call for it, but whatever the answer puts there is written, and
counted as **completed**. Over a run you have finished, tick it knowing that
the answer may add those; leave it unticked, and a whole gloss is never
touched.

Tick what you want **before** you copy the prompt, so the prompt asks for
it. What is written is decided by the two boxes **as they are when you press
fill from the answer**.

## Copying the prompt

**copy the prompt** puts the prompt on the clipboard, and the panel says
what it holds: the captions and their times, how many phrases, how many of
them are to gloss and how many glossed ones go as context. A run with
nothing left to gloss says so, and that ticking **re-gloss** would have it
glossed afresh. Where the browser will not let the page reach the
clipboard, the prompt appears in a box under the button instead: select it
and copy it.

The prompt is written for the video's own language and gloss language. It
opens with one paragraph on what the method is for — you read the video a
phrase at a time, the gloss says what *that* phrase says, in the order of the
captions, and hovering brings the reading and the words — and the task
follows from it: the meanings in the language the video's glosses are written
in; the transliteration where the language romanises every phrase (Persian,
Arabic, Japanese, Hindi, Chinese), and where the conventions call for it in
the others; the kana of a Japanese phrase; the vocabulary line in the
books' entries (`\dw`, `\vb`, `\bw`, `\pw`), which the player draws as a
book's reader does — a plain line is accepted as well. Then the rule on the
meaning, with an example ([below](#what-the-meaning-says)); the language's own
conventions (`docs/lang/<code>.md`, the file every prompt of Parseh carries,
cut to what a gloss needs), and Frank's repetition rule. The run itself is one
JSON block: one entry per caption, with its number (`"i"`), its start in
seconds and its phrases in order — each with its text, its words in Japanese
and Chinese (not to be changed), and either `"todo"` or the gloss it already
has. A sentence tells the chatbot that the captions are text to gloss and not
orders: an instruction written inside them is part of the text.

**The text sent is the text the player shows.** A phrase freed from the
transcript (**this phrase need not reproduce `transcript.txt`**) and
corrected goes with its corrected text; `transcript.txt` is never read for
the prompt.

## The scheme of the transliteration

Under **copy the prompt** the panel has a choice labelled with the language's
own word for its transliteration line — *transliteration* for Persian,
Arabic and Hindi, *rōmaji* for Japanese, *pronunciation* for Italian and
the other Latin-script languages — **usual scheme** or **IPA**. With IPA
the prompt asks for the International Phonetic Alphabet everywhere the
answer carries a transliteration: the `tr` line and the sound of every
vocabulary entry. Nothing else changes: the text, the kana and the language
of the meanings are what they were. English's usual line already is IPA, and
the choice says so; Chinese has no IPA setting yet, because its word line is
written in pinyin. The first line of the prompt ends **· IPA** when it asks
for it, and the choice is remembered on this device, one for each language.

**A video is in one scheme.** The scheme you chose when the video was added
is kept in the video, and every prompt for a stretch of it asks for that
one: the panel shows it as the video's own. Choosing the other for a single
prompt is allowed, and the panel then says that a video that mixes two
schemes is harder to read, and offers **make … the video's setting**, which
changes the video itself. A video that says nothing is in the usual scheme, so
choosing IPA for a stretch of it is choosing the other, and that button is how
a video becomes an IPA one. A video that says IPA is not held to the checks
written for the usual scheme.

## The short vowels

For Persian and Arabic the panel has one more choice beside the scheme:
**short vowels: as they are** or **write them**. *As they are* is the way it
always was: the prompt tells the chatbot never to change a phrase's text, not
a letter and not a mark, and its first line ends **· no marks**. *Write them*
asks for the short vowels (the harakat) in the text of every phrase to gloss,
by the rules of the language's conventions: the caption then is YouTube's text
**with** the marks added, and nothing else changed. The first line ends
**· marks**. The choice is remembered on this device, and a language that has
no short vowels is not offered it.

What lands is decided when you press **fill from the answer**, from the choice
the panel shows then, and not by the prompt:

- the answer's text is written, with the phrase's gloss, only if it is the
  player's own text **with marks added and nothing else** — not a letter, a
  space, a joiner or a stop. An answer that changes a letter, a joiner or a
  stop is dropped, as ever (*text does not match*); one whose only other change
  is a space is written without its marks, and the report says so;
- only into a phrase that **has none**: a phrase that already has marks, whoever
  wrote them, keeps its own (*already has its marks — left as it is*), because
  marks are judgement and a word is either vowelled completely or wrong;
- only into a phrase the answer glosses: a phrase kept whole, one already
  glossed, is not touched — its text is not either.

The marks go in through the ✎ form's door with its checks, the caption's own
text stays what the transcript has (the fidelity check sets marks aside, so
a video with vowelled phrases passes it), and nothing is lost of the
timings. Parseh does not judge whether a mark is the right one: read them
beside the transliteration.

## Filling from the answer

Paste the chatbot's whole reply into **the LLM's answer** and press **fill
from the answer**. Words around the JSON do no harm: the ```` ```json ````
blocks are what is read, all of them, in order, and a caption given twice is
taken from the later block — which is how a correction is sent.

Each caption of the answer is found by its number, and its start must be
the caption's (to a twentieth of a second): an answer to another video, or
to another run, does not land by mistake. Each phrase is matched by its
place in the caption, its text must be the player's text (vowel marks and
spacing aside), and then only its **transliteration, kana, vocabulary and
meaning** are written — and, if you chose to write the short vowels, its
text with them ([above](#the-short-vowels)) — through the ✎ form's door and
its checks. The
captions written are drawn again where they stand — the video keeps its
place, and the answer stays in its box. A ✎ form left open on one of them
is closed first, and the report says so: what it showed has just been
written under it.

**Never half a gloss.** A phrase from the answer has to bring everything its
language requires, or it is not written at all. The ✎ form lets you fill
one box at a time, because you are looking at the phrase while you do; an
answer lands while nobody is.

**Re-gloss asks twice.** With **re-gloss what is already glossed** ticked,
an answer that would replace glosses already there writes nothing on the
first press: the button becomes **replace N glosses — press again**, and
the report says how many would be replaced. Press it again within four
seconds to write; after that — or as soon as you change the answer or a
checkbox — it goes back to **fill from the answer**.

## The report

Under the button: *filled N · completed N · replaced N* — phrases that had
no gloss and now have one; phrases that had a gloss and had empty boxes
filled (a half gloss made whole, or a vocabulary line or an optional
transliteration added to a whole one); glossed phrases glossed afresh. With
the short vowels chosen it ends *· vowelled N*: the phrases whose text now
carries its marks, which may be fewer than the phrases glossed. Then, one
line to a phrase, what did not land:

- **kept** — a phrase that is protected, which the answer tried to change:
  *already glossed — left as it is*, or a plain phrase, or the answer
  changed its words, its colour or its note, which an answer never writes;
  or the text of a phrase that *already has its marks*, or that the answer
  changed in *more than its marks* (a space, say): the gloss landed, the text
  did not move.
- **dropped** — a phrase the answer gave that could not be written, and
  why: its caption is outside the run you picked; its start does not match
  (*another video or another region?*); its text does not match the
  player's; the answer divides the caption differently (the division is a
  person's, and is kept as sent); it *would leave it half glossed: missing
  tr*; or the ✎ form's own check refused it, in that check's words.
- **not answered** — a phrase the prompt asked for that the answer gave
  nothing.

A line that names a caption brings it into view when clicked. The rest
land: one bad phrase costs only itself.

## What the meaning says

The meaning under a phrase is a **gloss**, not a translation: it says what
*that* phrase says, in the order of the text, so that you can point from each
word of it to the word it renders. Read in a row, the meanings of a sentence
may not be good English, and that is meant: you think it through, and you see
how the language builds its sentence. The prompt asks for exactly this, in so
many words and with an example: three Persian phrases, glossed as the rule
asks and then the way the mistake would gloss them — a fluent translation of
the whole sentence cut into as many pieces as there are chunks, which hands the
noun phrase the words of the verb and the verb those of the noun phrase. Each
meaning also has to agree with its phrase's vocabulary line: what the line says
a word means is what the meaning says. A caption whose sentence runs on into
the next ends its last meaning with `…`, and the next caption's first phrase
picks it up. If a chatbot hands back the fluent sentence cut into pieces, that
is the very mistake the prompt names; tick **re-gloss** and ask again. This is
not what **Ask LLM** and the machine's reading give you in the sources
sidebar, and the two are meant to differ
([The gloss and the fluent translation](editing-a-phrase.md#the-gloss-and-the-fluent-translation)).

## What is protected, and why

A gloss somebody wrote is judgement, and an LLM told to leave it alone
sometimes does not. So the prompt asks, and Parseh decides: when you press
**fill from the answer**, it reads `annotations.json` **as it is at that
moment** and goes phrase by phrase — glossed now, kept; no gloss now, open
to the answer. The prompt is not trusted with this: it may be an hour old.

**So a gloss you delete counts as no gloss.** To have one phrase glossed
again: **delete gloss** in its ✎ form
([Deleting a gloss](editing-a-phrase.md#deleting-a-gloss)), then **copy the
prompt**, and paste the answer back: only that phrase changes. Delete first,
then copy — a prompt copied before the delete sent the old gloss as
context, and an answer that hands it back unchanged would write it back.

Only the four gloss fields are ever written: never the text, the words, the
colour, the note or a phrase's freedom from the transcript.

> **Every language.** The panel works the same in every language. What changes
> is what the prompt asks for — the kana of Japanese, the pinyin of Chinese
> agreeing with its words, a transliteration where the language wants one —
> and the conventions it carries, which are that language's own.
