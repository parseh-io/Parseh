---
title: The languages
weight: 7
description: The languages Parseh teaches — their codes, scripts, directions, fonts, digits and what each calls its transliteration — and the one table all of it comes from.
---

Parseh began as a Persian toolbox and now teaches twelve languages through
the same doors, with the same buttons and the same file formats. Nothing
about how you use it changes from one language to the next; what changes is
what each language needs in order to be read.

## The table

| Language | Code | Its own name | Script and direction |
|---|---|---|---|
| Persian | `fa` | فارسی | Arabic script, right to left |
| Arabic | `ar` | العربية | Arabic script, right to left |
| Italian | `it` | italiano | Latin, left to right |
| Japanese | `ja` | 日本語 | kanji and kana, left to right, and also vertical |
| French | `fr` | français | Latin, left to right |
| German | `de` | Deutsch | Latin, left to right |
| Turkish | `tr` | Türkçe | Latin, left to right |
| English | `en` | English | Latin, left to right |
| Hindi | `hi` | हिन्दी | Devanagari, left to right |
| Spanish | `es` | español | Latin, left to right |
| Chinese | `zh` | 中文 | Han characters (simplified), left to right, and also vertical |
| Catalan | `ca` | català | Latin, left to right |

| Language | The transliteration line is called | Required? | Digits |
|---|---|---|---|
| Persian | transliteration | yes | ۰۱۲۳۴۵۶۷۸۹ |
| Arabic | transliteration | yes | ٠١٢٣٤٥٦٧٨٩ |
| Hindi | transliteration | yes | ०१२३४५६७८९ |
| Japanese | rōmaji, with a **kana** reading beside it | yes | 0–9 |
| Chinese | pinyin | yes | 0–9 |
| Italian, French, German, Turkish, English, Spanish, Catalan | pronunciation | no | 0–9 |

The first table is in the registry's order, which every list of languages
in Parseh follows — the language chips, the add pages' selects, the rows of
the [reading-help page](reading-help.md).

- **The code** is what everything is filed under: `"language"` in a book's
  or a video's details, `target:` at the top of a studio document, the
  `data-lang` every page carries.
- **The name** labels the language on screen — the first slider of the
  **Aa** panel is called *Persian* or *Japanese*, not *text* — and names its
  folder: `books/persian/`, `youtube/videos/japanese/`,
  `markdown/library/italian/`, `exercises/italian/`.
- **Its own name** is what a language chip shows.
- **The transliteration line** is the second line of a gloss — how the
  chunk is said, in Latin letters — and each language calls it by its own
  name. Where it is **required**, the checkers refuse a glossed chunk
  without one; in a Latin-script language it is a pronunciation aid, given
  where the spelling misleads and left out where it does not.
- **The digits** are the ones chapter and paragraph labels are written in:
  a Persian book's third chapter's first paragraph is ۳.۱. The reader's
  buttons stay in Latin digits: they are controls, not text.

## Scripts that can be found, and scripts that must be marked

In **Persian, Arabic, Hindi, Japanese and Chinese**, the language's text can
be told from English by its letters alone. A studio document or a guide page
finds it on its own and sets it in the language's face and direction; a
paragraph with no Latin letters in it becomes a whole block of the
language:

```parseh-example
The word کتاب means *book*, and کتاب‌ها is its plural.

من کتاب را خواندم، و بعد به خانه رفتم.
```

```parseh-example
---
target: hi
---
The word किताब means *book*; नमस्ते is how you greet somebody.
```

**Italian, French, German, Turkish, English and Spanish** are written in the
same letters as the prose around them, so nothing can be found by its
script: every stretch of them is **marked**, with `[…]{tl}` (or the
language's code, or any mark such as a colour or a transliteration):

```parseh-example
---
target: it
---
[Il libro]{tl} = *the book*, and [la casa]{teal translit:ˈka.za} = *the house*.
```

Japanese and Chinese are found by their script too — Chinese's set of
characters is Japanese's without the kana, so a Japanese sentence is never
taken for Chinese — and have two things of their own: a reading over the
characters, and columns.

```parseh-example
---
target: ja
---
[漢字]{kana:かんじ translit:kanji} = *Chinese characters*

[
春はあけぼの。やうやう白くなりゆく山ぎは、
すこしあかりて、紫だちたる雲のほそくたなびきたる。
]{tl vertical height=10}
```

```parseh-example
---
target: zh
---
[中文]{translit:zhōngwén} = *Chinese*

[
从前，山下有一个小村子。
村子里住着一位老人和他的猫。
]{tl vertical height=8}
```

The studio's own pages (the Studio and Dialect sections of this guide) have
every mark in detail.

## Direction

Persian and Arabic run **right to left**, everything else left to right —
and every element of a language's text carries its direction, so a Persian
word inside an English sentence, an Arabic gloss, a Persian sentence over
its English translation all come out the right way round. In a book, the
chunk column sits on the language's own side: the chunk on the right and
its gloss on the left for Persian and Arabic, the other way round for the
rest. The chrome around the text — buttons, sheets, the editor's sources
column — stays left to right whatever the book.

Japanese and Chinese can also be set **vertically**, in columns read top to
bottom and right to left: a reading edition's last pass, and a studio block
marked `vertical`.

## Fonts

| Language | On screen | On paper | Travels with Parseh? |
|---|---|---|---|
| Persian | Vazirmatn; the alternate face Noto Nastaliq Urdu (`font=nastaliq`) | the same | yes, both |
| Arabic | Noto Naskh Arabic, falling back to Vazirmatn, then Amiri | Noto Naskh Arabic | yes |
| Hindi | Noto Serif Devanagari | the same | yes |
| Japanese | Noto Serif CJK JP (or the device's mincho face); the alternate face Noto Sans CJK JP, a gothic (`font=gothic`) | Noto Serif CJK JP, then Noto Serif JP, IPAexMincho and the system's mincho faces | no: the device's own |
| Chinese | Noto Serif CJK SC | the same | no: the device's own |
| Italian, French, German, Turkish, English, Spanish, Catalan | the toolbox's own roman: TeX Gyre Pagella, or Palatino | the book's own roman | nothing to carry |

**Four faces travel with Parseh**, in `lib/fonts/`: Vazirmatn, Noto
Nastaliq Urdu, Noto Naskh Arabic and Noto Serif Devanagari, all under the
SIL Open Font License. An Anki deck built for Persian, Arabic or Hindi
carries its language's first face inside the package, so the cards look
the same on a phone.

**The CJK faces do not travel**: a CJK font is tens of megabytes. Pages use
the device's own — Noto Serif CJK JP and SC where they are installed (the
`fonts-noto-cjk` package on Debian and Ubuntu has both), the system's
mincho, gothic and song faces on a Mac, a phone or Windows. The PDF of a
Japanese or Chinese book needs the named face on the machine that builds
it. The installer checks, for Japanese and for Chinese separately, as soon
as there is a book or a video in that language, and says what to install
when the face is missing.

**The Latin-script languages ask for no font at all.** Their text is set in
the same roman as the glosses, so a chunk and its gloss differ only by size
and colour.

Which face a language is set in is never written into a page: every page
reads it from a small stylesheet generated from the registry when Parseh
starts, so changing a language's face is a change to one table.

## The one table

Everything on this page — and everything a language *is* to Parseh: its
folders, its passes, its labels, its verb forms, its Anki note types, its
LaTeX settings — lives in one table, `lib/languages.json`, the **language
registry**, with a second file beside it, `config/languages.json`, for the
languages added on this machine (read after it, and kept by every update).
Every tool reads it, and nothing else in Parseh keeps a list of
languages, a script's letters, a font name or a table of digits. That is
why a twelfth language is a row of that table and two small files
([Adding a language](adding-a-language.md)), and why
[what differs, language by language](language-by-language.md) can be
listed in full.
