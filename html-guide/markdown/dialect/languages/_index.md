---
title: Documents in each language
weight: 15
description: What changes from one target language to the next — how its text is found, its direction and faces, its options, its vocabulary headings and its transliteration.
---

The dialect is the same for every language, and the front matter's
`target:` decides what differs. Everything the studio knows about a
language comes from the toolbox's language registry, `lib/languages.json`
(and `config/languages.json`, for a language added on this machine):
the characters of its script, its direction, its faces, whether it has a
reading or can be set vertically. Nothing about a language is written into
the studio itself, which is why every construct of this section works the
same for every language.

| `target:` | Language | Its text is… | Direction | Second face | Vertical | Reading | Its transliteration |
|---|---|---|---|---|---|---|---|
| `fa` | [Persian](persian.md), فارسی | found by its script | right to left | Nastaliq | — | — | transliteration |
| `ar` | [Arabic](arabic.md), العربية | found by its script | right to left | — | — | — | transliteration |
| `it` | [Italian](italian.md), italiano | marked | left to right | — | — | — | pronunciation |
| `ja` | [Japanese](japanese.md), 日本語 | found by its script | left to right, or vertical | Gothic | yes | kana | rōmaji |
| `fr` | [French](french.md), français | marked | left to right | — | — | — | pronunciation |
| `de` | [German](german.md), Deutsch | marked | left to right | — | — | — | pronunciation |
| `tr` | [Turkish](turkish.md), Türkçe | marked | left to right | — | — | — | pronunciation |
| `en` | [English](english.md) | marked | left to right | — | — | — | pronunciation |
| `hi` | [Hindi](hindi.md), हिन्दी | found by its script | left to right | — | — | — | transliteration |
| `es` | [Spanish](spanish.md), español | marked | left to right | — | — | — | pronunciation |
| `zh` | [Chinese](chinese.md), 中文 | found by its script | left to right, or vertical | — | yes | — | pinyin |
| `ca` | [Catalan](catalan.md), català | marked | left to right | — | — | — | pronunciation |

A document that names no `target:` is Persian.

## Two families

**Languages with a script of their own** — Persian, Arabic, Hindi,
Japanese, Chinese. Their words are found in the prose on their own; a
paragraph of nothing but their script is a display line, and one with no
Latin letter is a paragraph in the target language; `[…]{tl}` is needed
only where a Latin letter or a western digit belongs inside their text. On
the screen and on paper their text is set a size larger than the prose:
**1.52 times** for the Arabic script, whose letters are small for their
size, **1.20 times** for Devanagari, Japanese and Chinese. The first slider
of the reading view, named after the language, changes it, and the PDF
takes its value.

**Latin-script languages** — Italian, French, German, Turkish, English,
Spanish, Catalan. Their letters are the prose's letters, so nothing can be found:
every word you want set as the target language is marked, and there are
no automatic paragraphs. Their text is set in the prose's own face,
TeX Gyre Pagella, at the same size (1.00): what marks it out is the mark
itself — a colour, a transliteration to point at, a place in the glossary.
A heading with two or more `|` parts is always a vocabulary entry, so
their section titles cannot hold a `|`.

## Each page

The page of each language says how its text is found or marked, which
faces it is set in on the screen and on paper, the options its
`[…]{tl}` blocks take, how its vocabulary headings are written, and the
conventions of its transliteration — the ones the toolbox's prompt for
writing a document asks of an assistant, taken from the language's notes
in `docs/lang/`.
