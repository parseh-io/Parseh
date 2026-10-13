---
title: Licences and credits
linkTitle: Licences
weight: 8
description: What Parseh is under, and whose work it carries and downloads — the fonts, MathJax, the hyphenation patterns, the dictionaries, sentences and translation models — under which licence.
---

Parseh is free software, under the **GNU General Public License, version 3
or (at your option) any later version** — `GPL-3.0-or-later`. The
licence's text is the file `LICENSE`, at the top of the Parseh folder, and
every source file says so in its first lines:

```
SPDX-License-Identifier: GPL-3.0-or-later
```

It comes with no warranty. The source is the Parseh folder itself: the
server runs from it as it is.

The copyright is **Bruno Ursino's**, who made Parseh: *Copyright © 2026
Bruno Ursino*, with links to his GitHub account and his website, in the
`README.md`'s License section and at the head of the Licences page. The
text of `LICENSE` is the Free Software Foundation's, unchanged.

In Parseh, the foot of the hub leads to **Licences** (`/licences/`), in
the browser interface and in the mobile one. That page says all of this,
with a link to each licence's text.

## What Parseh carries

These are in the Parseh folder and are not Parseh's own work. Each keeps
its licence, which travels with it.

| What | Where | Whose | Licence |
|---|---|---|---|
| Vazirmatn 33.003 | `lib/fonts/` | © 2015 The Vazirmatn Project Authors | SIL Open Font License 1.1 |
| Noto Naskh Arabic 2.004 | `lib/fonts/` | © 2019–2020 Google LLC | SIL Open Font License 1.1 |
| Noto Nastaliq Urdu | `lib/fonts/` | © 2014 Google Inc. | SIL Open Font License 1.1 |
| Noto Serif Devanagari 2.001 | `lib/fonts/` | © 2019 Google Inc. | SIL Open Font License 1.1 |
| TeX Gyre Pagella, Heros and Chorus | `lib/fonts/`; copied by the studio, and into this guide's pages (Chorus sets no document, only the name Parseh, in the bar of every page of Parseh, in the hub's title, and in the bar of the guide published on the web) | © B. Jackowski, J. M. Nowacki and the TeX users groups | GUST Font License |
| MathJax 3.2.2 | `lib/mathjax/` | © The MathJax Consortium | Apache License 2.0 |
| The Italian hyphenation patterns, `hyph-it.tex` | `markdown/exlex/assets/hyph/` | © 2008–2011 Claudio Beccari | LaTeX Project Public License 1.3 or later, or MIT |
| Hazm's lists of informal Persian words and verbs, as `hazm` rows of the spoken-Persian tables, `fa.spoken.words.tsv` and `fa.spoken.verbs.tsv` | `lib/lang/` | © 2013 Alireza Nourian | MIT |
| Conjugation rows, and sentences with their machine translations, in the tests' data | `tests/fixtures/verbs/`, `tests/fixtures/align/` | Wiktionary's contributors; Tatoeba's contributors | CC BY-SA 4.0 (Wiktionary); CC BY 2.0 FR (Tatoeba) |

The texts sit beside the files:

- `lib/fonts/OFL.txt` is the Open Font License, with the copyright notice
  of each font under it. `lib/fonts/GUST-FONT-LICENSE.txt` is the TeX Gyre
  fonts' licence. `lib/fonts/README.md` says which file is which font.
  The compiled guide carries copies of all three beside its fonts, in
  `html-guide/site/_parseh/fonts/`.
- Each font file also carries its notice and the name of its licence in
  its own metadata. So a font packed into an Anki deck goes with its
  licence.
- `lib/mathjax/LICENSE` is MathJax's licence.
- `lib/lang/fa.spoken.HAZM-LICENSE.txt` is Hazm's licence (MIT), with its copyright line, beside the tables it seeded.
- `hyph-it.tex` says in its own header which licences it is under, and
  carries the MIT text.
- `tests/fixtures/README.md` says where every text the tests read comes
  from.

The Japanese and Chinese pages are set in the device's own faces, so none
travels with Parseh.

## What it downloads when you ask

The dictionaries, the sentences people have translated, the translation
models and their engine, the English synonyms and the character
components are not in the Parseh folder. Each is downloaded from its
source when you ask for it on [the reading-help
page](../lookup-and-languages/reading-help.md), and keeps its own licence.
Parseh writes that licence into the file it builds, and shows it wherever
it shows what the file says.
[Whose work it is](../lookup-and-languages/reading-help.md#whose-work-it-is)
lists every source and its licence.

**Speech to text**, which has a page of its own,
[Settings → Speech to text](../lookup-and-languages/speech-to-text.md#whose-work-it-is),
is fetched the same way: its program (faster-whisper, CTranslate2 and
onnxruntime under the MIT licence, PyAV under BSD-3-Clause with the
FFmpeg libraries and codecs it carries under their own) from PyPI, and its
two models (OpenAI's Whisper, under the MIT licence) from Hugging Face.
The optional exact-word-time networks are likewise fetched only when asked,
from Parseh's hash-pinned per-language Hugging Face repositories; their own
Apache-2.0 notices travel with them (Hindi is MIT and Turkish CC-BY-4.0).

**The ARASAAC pictograms**, which also have a page of their own,
[Settings → Pictograms (ARASAAC)](../studio/pictograms.md#whose-pictures-these-are),
are fetched from ARASAAC's own hosts, and are under a licence that asks
something of what you make with them: **CC BY-NC-SA 4.0**. They were drawn by
Sergio Palao for ARASAAC and are the property of the Government of Aragón.
Name them wherever you use them (the credit is written, word for word, in
`arasaac/LICENSE-ARASAAC.txt`), never use them for commercial purposes, and
share what you make with them on the same licence.

The installer fetches micromamba, Python and the packages
`environment.yml` lists. Each of them is under the licence it comes with.

## What you read with it

The books, videos, documents and decks are yours, or their authors'.
Parseh ships none of them, and its licence says nothing about them.

## A new font

A face added for a new language travels with its licence ([Adding a
language](../lookup-and-languages/adding-a-language.md#giving-it-a-font)).
Record it in three places:

- a row in `lib/fonts/README.md`;
- its copyright line in `lib/fonts/OFL.txt`, or a licence file of its own
  beside the font, if it is not under the OFL;
- an entry in `FONTS`, in `lib/notices.py`, which draws the Licences page.

`tests/test_licences.py` fails until all three name the new font.
