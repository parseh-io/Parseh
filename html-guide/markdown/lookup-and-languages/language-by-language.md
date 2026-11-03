---
title: What differs, language by language
linkTitle: Language by language
weight: 10
description: Levels, readings, words, vertical text, verb entries, transliteration schemes and the reading help — everything that is not the same in every languages.
---

The doors, the buttons and the file formats are the same for every
language. This page is everything that is not: what each language needs to
be read, and what each part of Parseh does about it.

## The levels of a reading edition

A reading edition gives each passage several times — as **levels** — and how
many, and what each one is, depends on the language. The reader shows one
button per level in its header, named as below and captioned *levels*; each
button's tooltip says what the level shows, and turning one off hides that
level. The names are each language's own defaults, and a person can change
them ([Levels and their names](../books/levels.md)).

| Language | Its levels, by the name on their button |
|---|---|
| Persian | **With vowels** the vowelled attempt · **Chunks** chunks and glosses · **Plain** bare naskh · **Nastaliq** nastaliq |
| Arabic | **With vowels** the vowelled attempt · **Chunks** chunks and glosses · **Plain** unvowelled, as Arabic is written |
| Japanese | **Furigana** with furigana over each word · **Kana only** the reading alone, in kana · **Chunks** chunks and glosses · **Plain** plain, as Japanese is written · **Vertical** vertical (tategaki) |
| Chinese | **Pinyin** with pinyin over each word · **Pinyin only** the reading alone, in pinyin · **Chunks** chunks and glosses · **Plain** plain, as Chinese is written · **Vertical** vertical |
| Italian, French, German, Turkish, English, Spanish, Hindi, Catalan | **Sentence** the sentence · **Chunks** chunks and glosses |

Why these and not others:

- **A plain level exists only where it shows something the first does not.**
  Persian and Arabic are written in the reading editions with their vowel
  marks (harakat) — the first level, **With vowels**, is *the vowelled attempt* — and **Plain**
  takes them off, as the languages are normally printed. Japanese and
  Chinese take away the readings over the words. The Latin-script languages
  and Hindi have nothing to take off (Devanagari writes its vowels), so
  their first level, **Sentence**, already shows all a plain level could.
- **A fourth face** is Persian's alone: the passage again in **nastaliq**,
  the calligraphic hand of Persian poetry and titles.
- **Japanese and Chinese have a reading level and a vertical level.** In
  the first level each word of a chunk wears its reading over it, where the chunk
  carries its word line (a Japanese chunk without one wears its kana over
  the whole of it); **Kana only** (**Pinyin only**) is the reading alone — the passage in kana, or
  in pinyin, as it is said, with the punctuation that ends each chunk —
  and **Vertical** sets the passage in columns read top to bottom and right to
  left.
- **Persian and Arabic can put the marks away.** **Diacritics**, in the ⚙ panel, takes
  the very marks the plain level leaves off from the first two levels, and from a
  video's lines — on the screen only ([Levels and their names](../books/levels.md#diacritics)).

## Readings, words and columns

| | Japanese | Chinese | the rest |
|---|---|---|---|
| **Transliteration line** | rōmaji (Hepburn) | pinyin, with tone marks | see below |
| **A reading beside it** | **kana**: every glossed chunk carries it, and the checkers require it | none — pinyin *is* the transliteration | none |
| **Words** | every chunk may carry a **word line**, `山(やま) へ 柴刈り(しばかり) に`: its words and each word's reading | the same, with pinyin: `我(wǒ) 想(xiǎng) 喝(hē) 茶(chá)` | no need: spaces already divide the words |
| **Vertical text** | the **Vertical** level; a studio block with `vertical` | the same | — |
| **No word separator** | a chunk counts as one word everywhere; the dictionary cuts it (or follows its word line) | the same | — |

The word line is what the furigana of the first level stand over, what the
[dictionary](dictionaries.md) looks up word by word, and what the cloud's
*山: I know this* buttons work by: a word you know stops wearing its reading
wherever it appears in that book or video. The video player of a Japanese
or Chinese video has one more button, named after the reading — **kana only** or
**pinyin only** — which shows every phrase as it is said, in place of its text.

## The transliteration, language by language

Each language's rules for writing its lines live in its **conventions
file**, `docs/lang/<code>.md` — the rules every prompt that asks a model to
annotate that language includes, and the page to read when you wonder why
a gloss is written the way it is.

| Language | The transliteration line |
|---|---|
| **Persian** | required. A scheme of its own: long *ā*, *š č ž x q*, the emphatics flattened, transparent morphology hyphenated (*mi-kone*, *ketāb-hā*); what is *said*, colloquial forms included. |
| **Arabic** | required. A scholarly scheme: *ā ī ū*, *ʾ* and *ʿ*, the emphatics with a dot under them. |
| **Hindi** | required, because the script hides what it does not say: the inherent *a* printed in every consonant and often silent — कमल is *kamal*. Every noun is glossed with *m.* or *f.* |
| **Japanese** | required: Hepburn rōmaji written from the kana (*Tōkyō*, particles *wa e o* as said). |
| **Chinese** | required: pinyin with tone marks, never numbers; the neutral tone unmarked. |
| **Italian**, **Spanish** | optional, and given only where the spelling misleads — Italian's open and closed *e* and *o* and its stress, Spanish's silent *h*. Most chunks need none. |
| **Catalan** | optional, given where the spelling misleads, which is more often than in Italian or Spanish: the open and closed *e* and *o*, the neutral vowel *ə* of an unstressed *a* or *e*, the letters not said (an infinitive's *r*, *molt*'s *t*); the stressed vowel always marked in the line. |
| **German** | optional, where the spelling misleads (vowel length, the two *ch*, stress). Capitals are spelling — a noun always has one — and a separable verb is glossed as the whole verb, however far apart its halves are. |
| **Turkish** | optional and rarely needed: the spelling is phonemic. The vocabulary line carries the morphology instead — a word's stem and each suffix in order. |
| **French** | optional in principle, given on almost every chunk in practice: the spelling hides the sound (silent endings, nasal vowels, liaisons). A respelling, not IPA. |
| **English** | written for every chunk with a word in it, in IPA, General American: English spelling is the least reliable guide to sound of any here. |

## Verb entries

A vocabulary line gives a verb as a **`\vb`**: three forms, each with its
sound, then the meaning — the same shape in every language. What the three
forms *are*, and the two labels printed before the second and third, are
each language's:

| Language | The three forms | Printed labels |
|---|---|---|
| Persian | infinitive · present stem · past stem | *pres.* / *past* |
| Arabic | perfect (3rd m. sg.; its form number in the sound) · imperfect (3rd m. sg.) · masdar | *impf.* / *masdar* |
| Italian | infinitive · 1st sg. present · past participle | *pres.* / *p.p.* |
| Japanese | dictionary form · -masu stem · -te form | *stem* / *-te* |
| French | infinitive · 1st sg. present · past participle | *pres.* / *p.p.* |
| German | infinitive · preterite (3rd sg.) · past participle | *pret.* / *p.p.* |
| Turkish | infinitive · present in -iyor (3rd sg.) · aorist (3rd sg.) | *pres.* / *aor.* |
| English | plain form · past · past participle | *past* / *p.p.* |
| Hindi | infinitive · stem · perfective (m. sg.) | *stem* / *perf.* |
| Spanish | infinitive · 1st sg. present · 3rd sg. preterite | *pres.* / *pret.* |
| Chinese | verb · A了B (a separable verb only) · A不B (a verb with a complement only) | *split* / *can't* |
| Catalan | infinitive · 1st sg. present · past participle | *pres.* / *p.p.* |

A pair left blank is not printed at all — a Chinese verb has its *split*
form or its *can't* form, never both. Whatever else a language's verbs need
goes in one parenthesis after the meaning: *to drive (er fährt; aux.
sein)*. The chunk sheet's `\vb{}{}{}{}{}{}{}` button names the three
forms of the book's language in its tooltip, and the dictionary's verb entries, where a
language's recipe recognises a verb, arrive in exactly this shape
([Dictionaries](dictionaries.md)). Every one of Parseh's languages has
such a recipe.

## In each door

| Door | What changes with the language |
|---|---|
| **Book reader** | the levels above and their names; the direction and side of the chunk column; the digits of the labels; ruby over the words of Japanese and Chinese; the ⚙ panel's first slider named after the language (**Persian text size**), and a **Height of vertical columns** slider for Japanese and Chinese; **Diacritics** for Persian and Arabic |
| **Video player** | the direction and face of the transcript; the kana line of a Japanese phrase above its rōmaji; the **kana only** / **pinyin only** reading button for Japanese and Chinese; **Diacritics** for Persian and Arabic |
| **Studio** | which text is found by its script and which must be marked; the fonts offered by `font=` (`nastaliq` for Persian, `gothic` for Japanese); `vertical` for Japanese and Chinese; a lemma heading's reading field and a **kana** insert button for Japanese; the target-text editor's button, **✎ Persian**, **✎ Japanese**… |
| **Reading help** | a dictionary for every language, with extra rules for Persian, Arabic, French, Italian, Japanese, Chinese and Catalan, and for Arabic one more per dialect (Egyptian, Levantine, Gulf, Moroccan), read first in a book or a video written in it; a corpus of Japanese or Chinese only after its dictionary; **Decompose Kanji** / **Decompose Hanzi** for Japanese and Chinese only; translation models only to or from English |
| **Anki** | a pair of note types per language — *Frank Italian* and *Frank Italian Opposites*, and so on (Persian's first is *Frank YouTube Persian*) — whose first field is named after the language (*Headword* for English), with a *Reading* field for Japanese; tags `<language>-book` and `<language>-youtube` (`farsi-…` for Persian) |
| **Videos, adding one** | which captions count as *plain* (in a script language, a caption with none of its letters); the words for seconds, minutes and chapters in the transcript |

The chapters on each door have the details: this page only says what the
language decides.
