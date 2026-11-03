---
title: Adding a language
weight: 11
description: For whoever maintains Parseh — the one command that adds a twelfth language, what it writes, what is left to write by hand, fonts, and how to check it.
---

> **From a page, or from the command line.** Nothing here is needed to
> *use* Parseh. A new language is a row of its language table and the files
> that go with it. **Settings → Languages** adds one from a form and has a
> chatbot write the prose it needs ([below](#from-settings)); everything it
> does is also a command in Parseh's folder, which the rest of this page
> describes. Once it is done, the language is simply there in every page.
>
> **The language is yours, and an update keeps it.** Its row goes into
> `config/languages.json`, beside Parseh's own table rather than inside it —
> the same folder as your settings, which no update touches — and its two
> files stay in `lib/lang/` and `docs/lang/`, which an update does not
> touch either. Adding a language to Parseh itself, for everybody, is the
> one flag `--shipped` (below).

Nothing about the number twelve is special. French, German, Turkish,
Hindi, Spanish, Chinese and Catalan each arrived as one run of one command — a row
of the table and the files that go with it — because every part of Parseh
reads the table rather than keeping a list of languages of its own.

## From Settings

**Settings → Languages** lists every language Parseh has, and opens each
one on what it has, feature by feature: its annotation conventions,
printed books, hyphenation, the studio's starter, examples, the
dictionary and its rules, verb entries, chunking rules, linguistic
analysis, translation models, translated sentences, speech to text, exact
word times, pictograms. Each says what the language is without it and what
adds it. The same list is `python3 lib/newlang.py --features` (one language:
`--features ca`).

**Add a language** at the foot of the page asks for what a form can ask:
the code, the English name and the language's own, the kind of script
(and its characters, for *other*), a **related language**, the ISO 639-3
code and a font. It writes what the command below writes, the row in
`config/languages.json`; the language is in every page at once. Only the
computer Parseh runs on may add one: a device let in sees the page and not
the button.

**The related language** is the starting point. The new one takes its
verb entry's shape and how it glosses a compound, and a copy of its
chunking rules to read and change; and the prose the new one needs is
drafted from the related one's own files. In its card, each piece still
missing — the conventions, the "How to read this" page, the studio's
starter, the examples, the lookup rules, the chunking rules — has **write
it with a chatbot**: **copy the prompt** (it carries the related
language's file as the model and the new one's row as the facts), paste it
in the chatbot of your choice, read what it writes, paste the answer back
and **take it in**. Parseh checks the answer's shape before it writes it —
the seven sections of the conventions, a "How to read this" page that only
writes text, JSON it can read — and never judges the language itself:
that is yours to read. On the command line the same prompts are
`python3 lib/langprompts.py <code> <piece>` and the answer goes back with
`--answer FILE`.

## What a language is

A language is **one row of the registry** plus the files that go with it.
The registry is two files read as one: **`lib/languages.json`**, Parseh's own
languages, which comes with Parseh and is replaced by each update, and
**`config/languages.json`**, the languages added on this machine, read after
it. Where both have a row for the same code, Parseh's own is the one used.
Beside the row:

- `lib/lang/<code>.tex` — what a reading edition's LaTeX needs to know about
  it;
- `docs/lang/<code>.md` — its annotation conventions;
- three content folders, `books/<folder>/`, `youtube/videos/<folder>/` and
  `markdown/library/<folder>/`, each with a `.gitkeep` so an empty one
  survives a clone.

The fields of the row that carry a decision:

| Field | What it decides |
|---|---|
| the key | the code, two or three letters (`fa`, `ja`, `nap`): `"language"` in a book or video, `target:` in a document, `data-lang` on every page |
| `name` | the English name: the folder, babel's language, the Anki field, every label that names the language |
| `native` | what the language calls itself: what its chip shows |
| `folder`, `tag` | the content folders; the stem of the Anki tags (`<tag>-book`, `<tag>-youtube`) |
| `iso3` | the ISO 639-3 code outside sources file it under — the corpus download needs it; without it the language can have no corpus |
| `dir` | `rtl` or `ltr` |
| `script`, `chars` | the kind of script, and the character ranges its text is recognised by (a regular-expression class, compiled by both Python and the browser). **`null`** means it cannot be told from English, and every run is marked by hand in the studio |
| `word_sep` | what separates words; the empty string for a language written without spaces, where a chunk counts as one word |
| `digits` | the ten figures its labels are written in |
| `strip` | the marks the plain level takes off (the harakat) — and the same marks **Diacritics** puts away from the first two levels and a video's lines. A language with no marks to strip, no reading and no word line has no plain level, since it would only reprint the first; Japanese and Chinese have none to strip and still get one, which takes the readings away |
| `reading`, `reading_label` | a second reading line beside the transliteration (Japanese's **kana**): a field on the cards, a line in every gloss, ruby in the first level, a rule the checkers enforce |
| `words` | chunks carry a word line, each word with its reading (Japanese, Chinese) — and a reading-alone level follows the first |
| `vertical` | it can be set in columns: a vertical last level, and the studio's `vertical` |
| `require_tr`, `translit_label` | whether every chunk needs a transliteration, and what the line is called |
| `ipa` | what the prompts' IPA setting makes of the language: left out, a person may ask for IPA in place of the usual scheme; `usual` says the usual scheme already is IPA (English); `none` offers no setting (Chinese, whose words are written in pinyin) |
| `vocal_label`, `bare_label` | the one-line titles of the first level and the plain level — what the panel prints under their names. The names the buttons wear are worked out from them: **Sentence**, **With vowels**, the reading's own (**Pinyin**), and **Plain** |
| `vb_forms`, `vb_labels` | what a verb entry's three forms are, and the two labels it prints ([Verb entries](language-by-language.md#verb-entries)) |
| `vb_video_bare` | a video's verb entries written without the marks (Arabic's are unvowelled); set by hand, there is no flag |
| `fonts`, `tex` | the faces on screen (the CSS stacks, and any `.woff2` that travels with Parseh) and on paper (babel's and fontspec's names, the faces to try in order, the hyphenation) |
| `passes` | the reading edition's levels, each with its name and its title — worked out from the fields above |
| `anki` | the two note-type ids and names, and the first field's name. **The ids are what Anki matches note types by, and must be this language's alone, forever** |
| `duration_units`, `chapter_words` | the words a transcript uses for seconds, minutes, hours and chapters |

## The one command

`lib/newlang.py` writes all of it. Run from Parseh's folder:

```bash
python3 lib/newlang.py                 # what it needs, and the languages there are
python3 lib/newlang.py --check         # every language validated, every file present
python3 lib/newlang.py --features      # what each language has, feature by feature
python3 lib/newlang.py --help          # every flag
python3 lib/newlang.py ko --name Korean --native 한국어 --script other \
    --chars '\uAC00-\uD7AF\u1100-\u11FF' --font 'Noto Serif KR' --iso3 kor
```

It asks for nothing it can work out — the folder, the tag, babel's name,
the levels, their names and their titles, the labels, and a free pair of Anki ids,
checked against every id in both files and every retired one — and works
out nothing you ought to decide. The flags that carry a decision:

| Flag | |
|---|---|
| `--name`, `--native` | required: the English name and the language's own |
| `--script KIND` | the kind of script: `arabic`, `devanagari`, `latin`, `cjk` or `other` (default `latin`). It picks the direction, `chars`, `word_sep`, `digits`, `strip`, whether a transliteration is required and what the line is called |
| `--chars RANGES` | the script's ranges, as a regular-expression class (`'\uAC00-\uD7AF…'`); required with `--script other`, and the way to narrow a kind (Chinese's class is the `cjk` one without the kana) |
| `--dir rtl`, `--dir ltr` | when it is not the script's usual direction |
| `--digits`, `--word-sep`, `--strip` | to override what the script kind gave |
| `--require-tr`, `--no-require-tr` | whether every chunk needs a transliteration, when the script kind's answer is wrong (only `latin` makes it optional, since there the line is a pronunciation aid) |
| `--iso3` | the ISO 639-3 code, for the corpus download |
| `--reading`, `--reading-label` | a reading beside the transliteration, and what it is called (`kana`) |
| `--words` | chunks carry a word line (only for a language written without spaces) |
| `--vertical` | it can be set in columns |
| `--folder`, `--tag` | the content folder and the Anki tag stem, when the ones the English name gives are taken or are not a folder name — the refusal says which to give |
| `--font`, `--font-fallback` | the face on paper and on screen, and faces to try when it is missing |
| `--css-font` | the whole CSS stack, when the one built from `--font` is not right |
| `--web-font` | a face bundled in `lib/fonts/`, by its `.woff2` file name (repeatable) |
| `--alt-font`, `--alt-key` | a second face (Persian's nastaliq): the title, the chapter numbers and a level of its own; the key is what a studio block calls it, `font=<key>` |
| `--alt-line-height` | the leading the second face needs on screen (Persian's nastaliq asks for 2.6) |
| `--translit-label`, `--vocal-label`, `--bare-label` | what the lines are called, and the one-line titles of the first and the plain level |
| `--vb-forms`, `--vb-labels` | the verb entry's three forms and two labels, each comma-separated |
| `--hyphen`, `--import`, `--babel`, `--tex-language` | LaTeX's names, when the defaults are wrong |
| `--anki-field`, `--duration-units`, `--chapter-words` | the rest of the row |
| `--like CODE` | a related language (`es` for Catalan): lends its verb entry's shape and how it glosses a compound, copies its chunking rules to read and change, and is the model the prompts for the prose show |
| `--dry-run` | print the row that would be added, and write nothing |
| `--force` | overwrite the `.tex` and the `.md` if they are already there |
| `--shipped` | put the row into Parseh's own table, `lib/languages.json`, and name it in that file's `_shipped` list: for a language added to Parseh itself, to be shared with everybody. Without it the row goes into `config/languages.json` and is this machine's |

It **refuses**, and writes nothing, for a code that is taken or is not two
or three lower-case letters, a folder or a tag another language has, a
`chars` that does not compile in both Python and JavaScript, `--script
other` without `--chars`, `--reading` on a script that cannot be
recognised, `--words` on a language written with spaces, `--digits` that
are not exactly ten, and verb labels carrying a character LaTeX would read
as syntax. A font the machine does not have is only a **warning**: the row
may be written on one machine for another.

What it said for Korean:

```text
adding Korean (ko, 한국어) to Parseh

warnings (none of them stopped anything):
  - --font 'Noto Serif KR' is not on this machine.  Kept: the entry may be for another one, and \FrankPickFont falls through tex.main_fallbacks.

  config/languages.json entry added -- a language of this machine's, which an update leaves where it is:
      folder korean/   tag korean   dir ltr   script other   digits Latin
      passes: Sentence (the sentence, to read on its own); Chunks (the sentence cut into chunks, each with its gloss beside it)
              (each button wears its name; a person renames a level on their own pages, and this is the default)
      fonts:  main Noto Serif KR, alt none, bundled none
      anki:   1724645326311 / 1724645326312 (slot 8212631), field Korean
  lib/lang/ko.tex      written
  docs/lang/ko.md      written
  books/korean/        made, with .gitkeep
  youtube/videos/korean/ made, with .gitkeep
  markdown/library/korean/ made, with .gitkeep
```

## What is left to write by hand

The command fills in the shape and not the prose, and it ends by listing
what is yours:

1. **`\FrankHowTo` in `lib/lang/<code>.tex`** — the “How to read this” page
   at the front of every printed book: what each level is for, and what the
   marks of the transliteration mean. It is written with a placeholder, so
   a book builds meanwhile; `lib/lang/fa.tex` is the voice to follow. For a
   language with a reading, words or a vertical pass, the file also has
   **TODO** blocks — the ruby over a word, the reading pass, the rotated
   columns — to copy from `lib/lang/ja.tex` and `zh.tex`; copy them rather
   than writing your own, since both are tuned against real pages.
2. **`docs/lang/<code>.md`** — the conventions, in seven sections (below).
3. **A fixture**, if the test suite is to cover the language: a small book
   under `tests/fixtures/books/<folder>/`, a video under
   `tests/fixtures/videos/<folder>/`, a card in `tests/fixtures/anki/`. The
   smoke test only tries a language it has a fixture for.
4. **A starter document**, `markdown/exlex/starters/<code>.md` — the page the
   studio's **+ New** opens on for this language, showing the marks it
   really uses. Until it exists the studio builds a plain one from the row.
5. **A verb recipe**, `lib/verbs/<code>.py`, which reads a dictionary entry
   and returns the language's three verb forms, with an optional table of
   exceptions in `lib/lang/<code>.verbs.json`. Without it nothing breaks:
   the editor's sources offer every verb as a plain word (`\dw`) instead of
   a whole `\vb`. Try one with `python3 lib/verbs/__init__.py <code> "<a
   sentence>"` and pin it with cases in `tests/fixtures/verbs/<code>.json`.

A language with marks to strip is also reminded that `vb_video_bare` has to
be set by hand if its videos are written without them. Other files a
language may have, read only where they exist: `lib/lang/<code>.lookup.json`
(the dictionary's rules for what is written onto a word), `<code>.ipa.json`,
`<code>.chunk.json`, and for a worded language `<code>.words.json`.

### The conventions file

`docs/lang/<code>.md` starts from `docs/lang/_template.md` with the
language's name, labels and verb forms filled in. It is **instructions to an
annotator** — and the annotator is usually a model: the video prompt, the
new-book prompt and the prompt that has an LLM gloss a stretch of a book or
a video (**gloss with an LLM**) take it in when that language is chosen, each
the sections it needs — a stretch, whose chunks are already cut, has no use
for **Chunking**, and the studio's prompts take only the transliteration, the
reading and the note on writing the script. What only a book is told, or only
a video, is marked in the template, so that each prompt reads clean for its
own. Keep all seven sections, even one that only says the language has no
such thing:

1. **The text field** — what `fa` must reproduce, verbatim, and what it
   must never silently correct. The fidelity checks are measured against it.
2. **Reading** — the reading rule, or one line saying there is none.
3. **Transliteration** — the scheme, letter by letter, and what is
   hyphenated: an annotator with only this file must write the line another
   one would.
4. **Vocabulary** — what a gloss carries, and the three forms of a verb in
   the order `\vb` prints them.
5. **Never gloss** — the function words that never get an entry, as a list.
6. **Chunking** — how big a chunk is, and what must never be split.
7. **Example** — a chunk or two of the language, each with its
   transliteration, its vocabulary line and a meaning that is **aligned**: it
   says what that chunk's own words say, in the order of the text, and read in
   a row may not be good prose
   ([What the meaning says](../books/glossing-with-an-llm.md#what-the-meaning-says)).
   The prompts that ask a model for glosses carry it, so that a model sees the
   shape of an answer in your language, and the add page's prompt uses it in
   place of a video from the shelf. Have a speaker of the language read it.

`\FrankHowTo` says the same things to the reader; the two must agree. The
nearest existing file is the one to model yours on: `docs/lang/it.md` for a
Latin-script language that spells itself, `fr.md` where the spelling hides
the sound, `fa.md` or `ar.md` for an Arabic script, `ja.md` for a reading,
`zh.md` for words without a reading.

**Linguistic analysis** is the row's `"analysis"`: which program reads the
language's word forms and which its sentences (`{"morphology": "udpipe",
"syntax": "udpipe"}` for most). A language read by UDPipe also needs its
model pinned in `lib/analysispins.py`; `python3 lib/getanalysis.py measure
catalan-ancora` fetches the model of that treebank into a throwaway folder
and prints the line, with its size and its hash, to paste into
`UDPIPE_MODELS`. **Examples** are the row's `"examples"` (what the lookup
page and the gloss buttons show), and a chatbot writes them too.

## Giving it a font

**If the device can be trusted to have the face**, name it with `--font`
and its fallbacks, and nothing else is needed: a Latin-script language
needs no face at all (it is set in the toolbox's roman), and the CJK
languages name the system's faces rather than carrying tens of megabytes.

**If it cannot**, the face travels with Parseh:

1. put the **`.woff2`** in `lib/fonts/` for the pages, and the **`.ttf`**
   or `.otf` beside it for LaTeX;
2. name the `.woff2` in the row's `fonts.web_files` — `--web-font` does
   that, and warns if the file is not in `lib/fonts/` yet;
3. declare it once with `@font-face` in `lib/parseh.css` and once in the
   studio's `markdown/app/static/app.css`, beside the four already there;
4. check its licence allows it: the four bundled faces are under the SIL
   Open Font License;
5. record the licence, so that the font travels with it: a row in
   `lib/fonts/README.md`, the font's copyright line in `lib/fonts/OFL.txt`
   (or a licence file of its own beside the font, if it is not under the
   OFL), and an entry in `FONTS` in `lib/notices.py`, which draws the
   **Licences** page. `tests/test_licences.py` fails until all three name
   it ([Licences and credits](../reference/licences.md)).

The CSS stacks themselves need no editing: the per-language stylesheet
every page links is generated from the registry when Parseh starts.

## Checking it

```bash
python3 lib/newlang.py --check       # every language: files, folders, fonts, ids, ranges
python3 tests/smoke.py               # the regression run, every renderer
python3 tests/smoke.py --pdf         # ... and the LaTeX builds (minutes)
```

`--check` walks the **whole** registry — both files, marking the languages
added on this machine — and prints a line for everything it
looked at: the `.tex` and the `.md`, that the verb labels and the passes in
the registry and the `.tex` agree, the three folders, that babel has the
locale, the fonts, the bundled files, that the Anki ids are the language's
alone, that `chars` compiles. A **MISSING** line is a fault — a missing
file, a shared Anki id, a range that does not compile, labels that
disagree — and makes it exit with a failure. A **note** is not: a folder
that does not exist yet, a font this machine lacks, a locale this TeX
installation has not got. `--strict` counts the notes as faults too.

```text
  ko  Korean (korean)  -- added on this machine
      ok       lib/lang/ko.tex (the reading editions' preamble)
      ok       docs/lang/ko.md (the annotation conventions)
      ok       vb labels 'pres.' / 'past': the registry and the .tex agree
      ok       vb forms: dictionary form / second form / third form
      ok       passes vocal/chunks: the registry and the .tex agree
      ok       books/korean/, youtube/videos/korean/, library/korean/
      ok       babel imports 'ko', which is installed
      note     tex.main 'Noto Serif KR' is not on this machine and no fallback is either
      ok       Anki ids 1724587311241 / 1724587311242 are this language's alone
      ok       chars: compiles in Python and JS

12 languages: 0 faults, 1 note.
```

## After that

Restart Parseh, and the language is everywhere a language is chosen: the
**Language** selects of **Add a book** and **Add a video**, the studio's
LLM prompt page, a new exercise deck, the gloss selects. Its chip appears
on a page as soon as that page has something in it. The
[reading-help page](reading-help.md) has a row for it in each section:
its dictionary is fetched from kaikki.org by its English name, its corpus
from Tatoeba by its `iso3`, and a translation model exists only if Mozilla
offers one between it and English. (The character components are for
Japanese and Chinese alone.)

The quickest proof that it works end to end is a video: **Add a video**,
choose the language, and the prompt it copies carries your conventions
file. The real test is a book, the one door that goes through LaTeX —
build its first chapter early, because `lib/lang/<code>.tex` is proved by
nothing until LaTeX has read it.

## Three examples

**A Latin-script language** is the easy case — seven of the twelve are:

```bash
python3 lib/newlang.py sv --name Swedish --native svenska --script latin \
    --iso3 swe --hyphen swedish
```

Two levels, **Sentence** and **Chunks**; an optional
*pronunciation* line; no font, no ranges, no marks to strip. What is left is
the prose: `\FrankHowTo` and the seven sections.

**A right-to-left language with its own digits and a face to carry:**

```bash
python3 lib/newlang.py ur --name Urdu --native اردو --script arabic \
    --font "Noto Nastaliq Urdu" --web-font NotoNastaliqUrdu.woff2 \
    --alt-font "Noto Naskh Arabic" --alt-key naskh \
    --digits "۰۱۲۳۴۵۶۷۸۹" --iso3 urd
```

`--script arabic` gives right to left, the Arabic ranges and the harakat to
strip, so the row has a bare pass; `--alt-font` adds a fourth pass in the
second face; `--digits` puts the Persian figures in place of the Arabic
ones. Nastaliq is already in `lib/fonts/`, because Persian uses it — a face
that is not needs the four steps above.

**A script of its own:** the Korean example above — `--script other` and
the Hangul ranges. And **a language written without spaces** adds `--words`
(each chunk then carries its words and their readings, and gets a
reading-alone pass) and, if it can be set in columns, `--vertical`; the
scaffold then leaves TODO blocks in the `.tex` to copy from `ja.tex` and
`zh.tex`.

> **Never type an Anki note-type id by hand.** The command allocates a
> free pair and checks it against every id in both files and every
> retired one, which is the whole reason to let it. A language added on
> your own machine draws its pair at random from slot 1000 up, a part of
> the grid Parseh's own languages never reach — so the next language
> Parseh ships cannot be handed the pair yours already has. An id that collides
> with another language's breaks nothing in Parseh — it breaks inside
> Anki, months later, by quietly merging two note types and the cards
> under them.
>
> **Removing a language needs one more line.** Its row takes its ids out of
> the table with it, so the grid would look free where it is not — and
> anybody who ever synced a deck of that language still has those note
> types in Anki. So when you remove one, add its two ids to
> `RETIRED_ANKI_IDS` in `lib/newlang.py`, with the language and the date
> beside them. Pali's pair (slot 9, `1724563200091` / `1724563200092`) is
> already there, which is why a twelfth language added to Parseh itself
> (`--shipped`) is given slot 12 and not slot 9.
> The command then never hands a retired pair out again, and `--check`
> calls any row that uses one a **MISSING** fault (*the Anki id … is
> already retired*).

`docs/languages.md` is the design underneath all of this.
