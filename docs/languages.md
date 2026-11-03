# Languages in Parseh — the design and the contract

Parseh began as a Persian toolbox. It now teaches several languages at once,
and everything below is the one description of how: the registry, where each
language's content lives, what the data formats carry, what each door of the
toolbox does per language, and what a new language needs. Every tool follows
this document; when a tool and this document disagree, the tool is wrong.

The languages today: **Persian** (`fa`), **Arabic** (`ar`), **Italian**
(`it`), **Japanese** (`ja`), **French** (`fr`), **German** (`de`),
**Turkish** (`tr`), **English** (`en`), **Hindi** (`hi`), **Spanish** (`es`),
**Chinese** (`zh`), **Catalan** (`ca`) — twelve rows in four scripts: the Arabic abjad, the
Latin alphabet, Devanagari and the Han characters (which Japanese writes
alongside its two kana syllabaries, and which the registry therefore gives
`japanese` and `cjk` as two `script` values rather than one). This is the
only place they are listed out. Everywhere below a count is stated by the
registry field that decides it — the Latin-script languages are the rows
whose `chars` is null, six of them today — because the field is what will
still be true after the next row lands and a number in a sentence is not.

---

## 1. The registry: `lib/languages.json` and `lib/languages.py`

One table, `lib/languages.json` — with a second half, `config/languages.json`,
for the languages added on one machine (below) — holds everything a language is: code, names,
folder, direction, script (as regex character ranges), digits, the marks the
bare pass strips, whether it has a *reading* (kana), whether it can be set
vertically, fonts (CSS stacks and TeX names), the babel/fontspec names, the
reading editions' passes, what a verb entry is in the language — the two
labels a `\vb` prints (`vb_labels`), what its three forms are (`vb_forms`)
and whether a video writes them without the marks (`vb_video_bare`), §3 —
the ISO 639-3 code an outside source keys its files by (`iso3`, below), what
the prompts' IPA setting makes of the language (`ipa`: left out, a person may
ask for IPA in place of the usual scheme; `usual`, the usual scheme already is
IPA, as English's; `none`, no setting yet, as Chinese's, whose words are written
in pinyin), the Anki note-type ids. `lib/languages.py` is the Python API over it
(`get(code)`, `LANGS`, `by_folder`, `detect_from_path`, `Lang.has_script /
strip / run_re / to_latin_digits / passes / vb_labels / vb_forms /
vb_video_bare / as_json`), and it
answers the other language question too — `gloss(code)`, `GLOSS_CODES`,
`DEFAULT_GLOSS` (below). Pages never fetch the registry: the tool that
writes or serves a page embeds that page's language record (`Lang.as_json()`)
into it.

**No other file may hold a list of languages, a language-specific regex, a
font name or a digit table.** A tool that needs one asks the registry.

### Two files, one registry: Parseh's languages and this machine's

The registry has **two halves**, and to every tool they are one table.
`lib/languages.json` holds **Parseh's own** languages — the ones a release
ships, tests and documents — and it is part of the software: updating
Parseh replaces it with the new version's, like every other file a release
carries. **A language somebody adds on their own machine** is theirs, like
their settings, and lives where their settings live:
**`config/languages.json`**, beside the checkout, which no release carries
and no update touches (and which `.gitignore` keeps out of git). It holds
rows of exactly the same shape, under the store's own `_comment` and a
`_format` stamp, `parseh-languages/1` (`languages.STORE_FORMAT`, which
`lib/version.formats()` reports so an update to a Parseh that reads an older
shape is told so first). `lib/newlang.py` writes it (§10).

`lib/languages.py` reads **Parseh's table first and then the machine's**
(`read_rows`), and marks every language of the second half as the person's:
`Lang.mine` is true, `languages.mine()` lists them. The rules, and why:

- **Parseh's own row wins a code both hold.** The day Parseh ships Korean, a
  Korean somebody added for themselves is passed over, not merged — two rows
  for one code would be two answers to every question — and `newlang.py
  --check` says so, as a note: their row can go.
- **A row whose folder another language already has is left out**, because a
  folder is how a book, a video or a document is found to *be* in a language
  (§2). `--check` calls that a fault.
- **The person's half never stops Parseh.** A `config/languages.json` that is
  not JSON, or a row missing a field or carrying a class that does not
  compile, is left out and said — in the server's log as it starts
  (`languages.PROBLEMS`) and by `--check` — and every other language goes on
  working. Parseh's own table still raises on a fault, as it always has: a
  fault there is a fault of the release.

The **book preamble reads the registry itself**, in Lua (§6), and follows the
same rule: `lib/frank-preamble.tex` reads `lib/languages.json`, then
`config/languages.json` for the codes Parseh's own lacks, so the PDF and the
reader of one book never take a language from two different rows. The path
is `\FrankLib`'s with its last component changed from `lib` to `config`,
worked out on the text rather than through `lib/..`, so a tree whose `lib/`
is a link into another checkout reads its own `config/`, as the Python side
does (`languages.PERSONAL` comes from the imported path, not the resolved
one). **Both files are in both of `build.sh`'s keys**, so a change to a
language added on this machine rebuilds its books as a change to Parseh's
table does; a missing `config/languages.json` adds nothing to either key, so
no existing book's key moved when the second half was introduced.

**`_shipped`** at the top of `lib/languages.json` names the rows that are
Parseh's, in order, and a unit test (`tests/test_languages_store.py`) holds it
to the table. It is how a row that is **not** Parseh's is told apart when it
turns up in Parseh's file anyway — an older `newlang.py` spliced every new
language there, and a hand may still. **`languages.migrate()` moves such a
row**: written into `config/languages.json`, then cut out of
`lib/languages.json` so that Parseh's own rows come out **byte for byte** and
the file is again the one the release shipped (the update that follows then
has nothing of the person's to replace). The server runs it as it starts,
and a file with nothing to move costs one read and writes nothing — which is
how it happens once. It is careful where a mistake would lose something: it
**never runs in a git checkout** (there a row `_shipped` does not name is a
language being added to Parseh by its author, and `newlang.py --migrate` is
the way to ask for it); it **never writes over a `config/languages.json` it
could not read**; a row the store already holds **the same** is only taken
out of `lib/`; one it holds **differently** is left in both, the one in
`lib/` is read, and the log says so, because which of two hand edits is right
is not a thing to guess. A `lib/languages.json` with **no** `_shipped` — one
from before the list existed — is taken as all Parseh's, and nothing is
moved.

**What stays where it was.** A language added on this machine still has its
`lib/lang/<code>.tex` and `docs/lang/<code>.md` (and whatever else §10 lists:
`lib/verbs/<code>.py`, a starter, `lib/lang/<code>.*.json`) where every tool
looks for them. They are not in any release's manifest, so an update, which
replaces and removes only the files its manifests name, never touches them.

**`iso3` is in the table because one outside source keys its files by it.**
Parseh keys everything by ISO 639-1; Tatoeba, whose exports `lib/getcorpus.py`
builds a parallel corpus from (§12), keys its exports by ISO 639-3, and the
third letter cannot be derived from the second. For Persian the two differ by
more than length: `fas` is the macrolanguage and `pes` is Western Persian, and
only `pes` has an export at all — a corpus built under `fas` would be a
download that is not there. Chinese is the same trouble read from the other
end: `zh` is a macrolanguage, the toolbox teaches Mandarin, and the export
is keyed `cmn`. Spanish, where nothing is ambiguous, is the ordinary case
and carries `spa`. Which code names a language is a fact about the
language and not about the tool that asked, so it is a field here and not a
table inside the downloader. A row with no `iso3` is not an error —
`lib/newlang.py` takes `--iso3` and leaves the field empty when it is not
given, so a language added without it has none until somebody looks it up,
and `--check` reports that as a note rather than a fault. `getcorpus.py`
refuses by naming the field rather than inventing a third letter.

The **default language is `fa`**: content written before languages were
declared is Persian, and every reader of `language`/`target` falls back to it
(`languages.get_or_default`).

### Two languages, everywhere

A studio document is written *about* a target language *in* a prose
language. The front matter's `target:` is the language being learned (the
registry code, default `fa`); `lang:` stays what it was — the ISO code of the
**prose** (`en`, `it`, …), which picks the hyphenation patterns. A Japanese
note written in Italian has `target: ja` and `lang: it`.

Books and videos say the same two things, and for the same reason: an
Italian who wants to learn English wants the meanings in Italian. `book.json`
and `video.json` carry **`language`** — what the thing *teaches*, a registry
code, the folder it lives in — and **`gloss`**, the language its meanings are
*written in*. The two are not interchangeable and the names must never be
read as each other: one is the subject, the other is the prose. **`gloss`
absent means `en`**, which is what every book and video written before the
field existed is, so nothing has to be migrated and nothing in the toolbox
today changes meaning (§11).

A gloss language is a **prose** language and need not be one the registry
teaches: somebody may gloss Persian in Portuguese, and nobody studies
Portuguese here. What may be written in is every row of the registry *plus*
a handful of prose-only codes — the same set the studio takes for `lang:`,
because it is the same question asked at the other door and one document
must not be sayable there and unsayable here. `languages.gloss(code)` is the
single answer to all of it: whether the code is accepted, what the language
is called on screen, which way it runs, and what babel calls it. Where the
code is one the registry teaches, **the registry is what names it**; the
prose-only rows carry their own name, native name, babel name and
direction.

Those rows are a table in `lib/languages.py`, not an entry in
`lib/languages.json`, and that is not an exception to the rule above. An
entry in the registry is a language somebody **studies**: a folder under
`books/`, a script, digits, fonts, passes, Anki note-type ids,
`lib/lang/<code>.tex` and `docs/lang/<code>.md`, every one of them required
by `newlang.py --check`. Portuguese has none of that and needs none — it is
a language the toolbox *writes in*, not one it teaches — and where a
prose-only code is also a code the registry teaches the registry is what
answers, so the table is not a second list of the languages. The
studio's `texgen._HYPHEN_PROSE` holds the same codes with the other half of
the answer, TeX's pattern name and the hyphenation minima; `lib/` cannot
reach it (it sits inside the studio, and importing it pulls the whole studio
in behind it) and the dependency already runs the other way, `texgen.py`
importing `lib/languages.py` and deferring to `tex.hyphen` for a code the
registry teaches. The same deferral is what should carry the codes when
somebody comes to write it.

**A code may cross from that table into the registry, and one just has.**
Spanish is the example this section used to give for prose-only — glossed
in, never taught — and it is now a row of its own, with a folder, a script
kind, passes and note types. Nothing had to be taken out of the prose table
for that to work: `languages._glosses()` builds the registry's rows first
and adds a prose-only row only for a code the registry has not got, so the
`es` line still sitting in `_PROSE` is passed over and Spanish is named on
screen by its registry row. That ordering was written against exactly this
collision — one name for a language on screen, and it is the registry's —
and this is the first time anything has landed on it. The stale line is
worth clearing when somebody is next in that file; it is inert, not wrong.

---

## 2. Where content lives: one folder per language

The folder name is the registry's `folder` (the English name, lower-case):

```
books/<folder>/<slug>/                books/persian/farsi-shakar-ast/  books/japanese/…
youtube/videos/<folder>/<id>/         youtube/videos/persian/Gbfc-2sy_pc/
markdown/library/<folder>/<id>/       library/persian/feature-test-f9cf3d/
exercises/<folder>/<slug>/            exercises/italian/everyday-verbs/
```

Every tool that lists content walks two levels. The folder is where the
content *lives*; the language of the content is what its own JSON says
(`language` / `target`) — the two must agree, and `books.py`, `ytpages.py`
and `store.py` warn when they do not (the JSON wins for rendering, the
folder for the URL). A legacy flat directory directly under `books/`,
`videos/` or `library/` is still read, taken as Persian, and reported with
a note to move it.

URLs that name an item by a globally unique id do not carry the folder:
`/youtube/v/<id>/`, `/youtube/c/<channel>/`, `/studio/doc/<id>`. Static book
readers follow their folder: `/books/<folder>/<slug>/reader/`, and so do the
exercise decks, a deck's slug being unique only within its folder:
`/exercises/deck/<folder>/<slug>/`. A deck's language *is* its folder —
`decks.py` reads no other, and `deck.json`'s `"lang"` only repeats it — so
every exercise in a deck is checked against that language.

The studio's own directory is `markdown/`. It was `markdown persian
reader/` for as long as Persian was the only language.

Anki decks follow the same rule: a deck lives at
`youtube/anki/<folder>/<slug>/` (`cards/`, `media/`, `deleted/` inside
it), and `deck.json` carries `"lang"` — absent it is the folder's
language, and Persian for a deck lying directly under `anki/`, which is
the legacy layout, still read and reported and never moved by a tool.
`notetypes.json`, `seen.json`, `inbox/` and `build/` are collection-level
and stay directly under `anki/`. Deck *names* are the user's own
(`Japanese::Videos`), and two languages may hold a deck of the same name
and so the same slug: nothing addresses a deck by slug alone —
`anki_store.decks()` hands back `{lang, folder, language, slug, path,
name, cards, legacy}`, `path` (`japanese/videos`) being the handle. A
card is filed by ITS language, not the deck the dashboard named
(§4).

---

## 3. The data formats

### The foreign text is `fa`, and the meaning is `en`

In every stored format the target-language text is under the key **`fa`**:
video chunks (`{"fa": …, "tr": …, "voc": …, "en": …}`), Anki cards, and the
`Chunk.fa` texparse reads from a `\ch`. The key is from the Persian-only days
and is kept because every tool and every stored file uses it. Prompts and
docs say so in one line ("`fa` is the caption's text in the target language;
the key is named after Persian, the toolbox's first language").

Its opposite number, the meaning, is under the key **`en`** — the fifth
argument of `\ch{col}{fa}{tr}{voc}{en}`, the `en` of a video chunk, the
`English` field of an Anki note type — and it stays `en` **whatever language
the gloss is written in**, exactly as the text's key stays `fa` whatever
language the text is. Both are names of *slots*, and neither is a claim
about a language: `fa` is named after the toolbox's first language, `en`
after the only language its glosses were written in for as long as there was
only one of them. Renaming either would rewrite every book, every video,
every Anki note type and the studio, to say what `gloss` already says. An
`en` field holding Italian is not a mistake; it is a book whose `gloss` is
`it`.

What `en` says is the same in every language, for a book and for a video, and
is written once, in `docs/meaning-rule.md`: a **gloss**, not a translation. It
renders that chunk's own words and no others, in the order of the text, so that
a learner who reads the meanings one after another can point from each word of
them to the word it renders; it agrees with the chunk's `voc`; and it is never
a fluent translation of the sentence cut into as many pieces as there are
chunks. Every prompt that asks for one embeds that file (`{{MEANING_RULE}}`, §9),
so there is no second statement of it to keep in step. The fluent translation is
what the sources sidebar's *Ask LLM* and the machine's reading give, on purpose:
the guide says why the two differ.

The Anki note type's field keeps the name `English` for that reason and one
more: Anki matches a note type on import by its id and its field list, so
renaming the field would split or merge a deck somebody is already studying
(§4, §11). What a card must carry instead is the gloss's `lang` and `dir`,
so that an Italian or an Arabic gloss renders as itself.

### The reading: `kana`

A language with `reading: true` (Japanese) carries the kana reading of each
chunk **beside** the transliteration, wherever a transliteration can be
given:

| where | transliteration | reading |
|---|---|---|
| video chunk (JSON) | `tr` | `kana` |
| book chunk (LaTeX) | `\ch{col}{fa}{tr}{voc}{en}` | `\chr{col}{fa}{kana}{tr}{voc}{en}` |
| studio inline mark | `[漢字]{translit:kanji}` | `[漢字]{kana:かんじ translit:kanji}` |
| studio lemma heading | `## فارسی \| translit \| etym \| = *gloss*` | `## 漢字 \| かんじ \| kanji \| etym \| = *gloss*` |
| Anki card (JSON) | `tr`, `opp_tr` | `kana`, `opp_kana` |
| Anki note type | field `Transliteration` | field `Reading` (vocab), `OppositeReading` (opposites) |

`\chr` is a distinct macro, not a sixth argument of `\ch`, so that every
parser knows the arity from the name. For a reading language the checkers
require `kana` on every glossed chunk (`check_batch.py`, `check_annotations.py`);
for the others the field is ignored if present. `{reading:…}` is accepted as
an alias of `{kana:…}` in the studio's markdown. In a lemma heading the
reading field exists **only** when the document's target language has a
reading — Persian headings keep their three fields.

**`reading` and `translit` are two registry fields and two different ideas,
and Chinese is the row that shows it.** A transliteration writes the language
in Latin letters, for a reader who cannot yet read the script at all. A
reading writes it in the language's *own* script, in the part of that script
that spells sound, for a reader who can read that part and not the rest.
Japanese wants both and has both: `translit` is Hepburn rōmaji and `reading`
is the kana, and it is the kana that goes over the text as furigana, because
rōmaji over a Japanese line helps nobody who is reading Japanese. Chinese
wants only the first. Pinyin is written in Latin letters, so pinyin *is* the
transliteration — `translit_label` is "pinyin" — and `reading` is false, with
no `reading_label` beside it. Two rows are written without word separators
and the same two can be set vertically; only one of them has a reading. The
fields were never a pair, and it took a second unspaced language to make that
plain.

The kana is the reading of the **whole chunk**, never a per-kanji
alignment: `\chr{}{漢字を書く}{かんじをかく}{kanji o kaku}{…}{…}`. It is the
chunk's own line in the gloss, and the ruby a chunk without words wears over
it in pass 1. The reading of each **word** is the word line's (below).

### Words: the word line

A language with `words: true` (Japanese, Chinese) divides a chunk into
**words**, each with its own reading, in one plain string -- the **word
line** -- which is the same bytes in both formats:

| where | the word line |
|---|---|
| video chunk (JSON) | `"words": "山(やま) へ 柴刈り(しばかり) に 、"` |
| book chunk (LaTeX), a language with a reading | `\chrw{col}{fa}{kana}{tr}{voc}{en}{words}` |
| book chunk (LaTeX), a language without one | `\chw{col}{fa}{tr}{voc}{en}{words}` |

- Words are parted by spaces; a word's reading follows it in ASCII
  parentheses (kana for ja, pinyin for zh), and a word with nothing to read
  is bare. `((` `))` are literal parentheses. The grammar has three parsers --
  `lib/wordline.py`, `lib/wordline.lua` for the PDF, `lib/wordline.js` for the
  pages -- held to one fixture, `tests/fixtures/wordline.json`, by error code.
- **The text is not in the line, only its division.** The words joined with
  the word separator must reproduce `fa` under the fidelity comparison, and
  every page and the PDF draw the characters from `fa`, taking only the
  boundaries and the readings from the line -- so a space in `fa` is kept
  though the line cannot spell it.
- **The chunk's reading is its own.** In a finished text `kana` (or `tr`) is
  not derived from the words, nor they from it: kanbun reorders the words when
  it is read, and Chinese `tr` writes the changed tones of 一 and 不. The one
  place it starts from them is a **draft**: `lib/draft.py` gives a chunk its
  proposed words and the reading they spell (`wordline.reading_from` -- the
  kana run together, or the pinyin parted by spaces, the punctuation where the
  text has it -- as written in kana, in ASCII in pinyin -- and nothing at all
  when a word in characters has no reading), and the checkers
  count a chunk whose only written field is that reading, unchanged, as
  unwritten (`wordline.seed`). `lib/fill_words.py --json` gives an annotator's
  JSON the same start, filling a reading only where it is blank.
  `wordline.check` compares the two only to *warn*, tones and punctuation set
  aside, and a book or video read out of its written order says
  `"reorders": true` in `book.json` / `video.json` and is not compared at all.
  It is a switch -- true, or the key absent -- and the metadata routes set it
  (`<book>/reader/__edit/meta` through `bookmeta.edit_meta`,
  `/youtube/api/editmeta` through `ytpages.edit_meta`, and the reader's book
  info and the player's video info sheets show it as a checkbox for a
  language with words); `false` is never written.
- The words go **last**, in macros of their own, so every positional reader of
  `\ch` and `\chr` keeps its argument numbers; `fa` never carries markup (a
  macro inside it is fatal to the collect pass, which expands it). A chunk
  without a word line is legal forever; giving a `\chr` one rewrites it as
  `\chrw`, and clearing it rewrites it back.
- A word's identity -- for "I know this" and for the dictionary -- is its own
  token, surface and reading together: `山(やま)` and `山(さん)` are two words,
  and a word that repeats is one.
- `lib/words.py` proposes a line when a text is added (SudachiPy for ja,
  merged by part of speech; spacy-pkuseg and pypinyin for zh; the rules in
  `lib/lang/<code>.words.json`). Where the analyzers are not installed in the
  running Python nothing is proposed. A proposal is a draft to correct.
  **Given the chunk's own reading** (`kana`, or `tr` for zh) it cuts that
  reading into one stretch per word and gives each word its own -- the kana
  a Japanese word is written with, and one pinyin syllable to a Chinese
  character, holding the cut in place, the machine's readings choosing among
  cuts that fit equally -- so the furigana say what the chunk's reading says
  (私 わたし, not the dictionary's わたくし; zǎoshang with tr's neutral tone).
  Where no cut fits, the machine's readings stand; the reading never moves
  where the words are cut. Every door that adds a glossed text passes it, as
  does `lib/fill_words.py`. The pages ask for a proposal through
  `POST <book>/__words/propose {"text", "reading"?}` and
  `POST /youtube/api/words {"video", "text", "reading"?}`, which answer
  `{"ok", "words", "available", "python"}` and write nothing.
- **The dictionary looks up the document's own words.** A lookup body
  (`<book>/__lookup`, `/youtube/api/lookup`) may carry `"words"`, the chunk's
  line, beside `"text"`. When it parses, the words are looked up as given --
  one row per word, a repeated word its own row, a word the dictionary does
  not know never cut again -- and each row carries `"i"`, **the word's index
  in the line**: the page puts row `i` under `ParsehWordline.parse(line)[i]`
  and filters nothing itself (punctuation and words past the length cap simply
  have no row). Without `"words"` the answer is exactly what it always was.
- **"I know this" is per word** in a worded chunk: `localStorage`
  `parseh_known_word:<scope>` holds tokens, and a word also counts as known
  when every kanji or hanzi of it is in the older per-character store
  `parseh_known_kanji:<scope>` -- so nothing marked before the word layer is
  lost, and nothing is migrated.

A reading edition sets a worded chunk's readings **per word**, in pass 1 and in
the chunk column, where line breaks may now fall between words; a new pass
after pass 1 sets the readings alone, each chunk's own reading with the
punctuation that ends its text, so kanbun prints in the spoken order. Japanese
and Chinese have five passes each: with ruby, the reading alone, the chunks,
plain, vertical.

### Marks that are stripped: the vowelled pass and the bare pass

The reading editions give a passage first *with help* and then *bare*. What
"help" and "bare" mean is per language, and the registry's `strip` field is
the mechanism:

| language | `fa` carries | `strip` removes | bare pass shows |
|---|---|---|---|
| fa | harakat (U+064B–U+0652) | that range | unvowelled naskh |
| ar | harakat + U+0670 | that range | unvowelled Arabic |
| ja | plain text; the kana is in `kana`, and each word's in `words` | nothing | the same text, without the ruby |
| zh | plain text; the pinyin is in `tr`, and each word's in `words` | nothing | the same text, without the pinyin over its words |
| it, fr, de, tr, en, es | plain text | nothing | (no bare pass) |
| hi | plain text; Devanagari writes its vowels | nothing | (no bare pass) |

**Diacritics** (a0.5.0) puts the very same marks away from what is drawn -- the one
rule, whichever page: from a book's levels 1 and 2 (`lib/gear-reader.js`: the text nodes
of `.p1 .w` and of the chunk column are changed, the originals kept, and `textOf` and
`Parseh.baseText` are given a copy with the book's own text, so a card or a copy
carries the vowelled chunk) and from a video's lines (`youtube/lib/player.js`,
`asDrawn()`; the copy, the cards, the editor and every lookup read the chunk as it was
written). Display only: level 3 is unchanged -- it never had the marks, and `bare_strip`
and the LaTeX `frank_strip` are not touched -- and a language whose record has no `strip`
has no such switch. It is a device key (`bk_marks`, `yt_marks`), never in `prefs.KEYS`.

Fidelity checks (`assemble.py`, `check_batch.py`, `verify_book.py`,
`check_annotations.py`) strip with the language's `strip`; the LaTeX
preamble's `frank_strip` does the same for the same language. `timings.json`
keys hash the stripped text, as before.

### The passes, and what a page calls them: `name`, `label`, `title`

A reading edition sets the same passage in several **passes**; to the person
reading, each is a **level**, and a page shows them as buttons. The registry's
`passes` list holds one entry per pass, in the order the language has them, and
each says four things:

| field | what it is | who reads it |
|---|---|---|
| `key` | `vocal`, `aloud`, `chunks`, `bare`, `alt` — what the pass *is*; the CSS class (`.p1`…), what a button hides and every prefs key are told by it | everything |
| `name` | the word its button wears: **1 to 12 characters**, no two the same within a language | the pages: the buttons, the panel's rows, the hover mode's tooltip |
| `label` | its digit, counting the language's own passes (Chinese: 1, 2, 3, 4, 5 — the vertical pass is `.p4` all the same) | the PDF and the checkers only; **a page no longer prints it** |
| `title` | one line saying what the level shows | printed beside the name, and as the button's own explanation |

The names a language starts with, and what each says (these are the shipped
rows; `title` is the sentence the panel prints):

| language | levels, by `key` → `name` |
|---|---|
| fa | vocal **With vowels** · chunks **Chunks** · bare **Plain** · alt **Nastaliq** |
| ar | vocal **With vowels** · chunks **Chunks** · bare **Plain** |
| it, fr, de, tr, en, hi, es | vocal **Sentence** · chunks **Chunks** |
| ja | vocal **Furigana** · aloud **Kana only** · chunks **Chunks** · bare **Plain** · alt **Vertical** |
| zh | vocal **Pinyin** · aloud **Pinyin only** · chunks **Chunks** · bare **Plain** · alt **Vertical** |

The titles say the same thing in every language: *vocal* — "the sentence with
its vowels, to read on its own" (fa, ar) or "the sentence, to read on its own";
with a reading it stays "with furigana over each word" / "with pinyin over each
word"; *aloud* — "the reading alone, in kana" / "in pinyin"; *chunks* — "the
sentence cut into chunks, each with its gloss beside it"; *bare* — "the
sentence as Persian (Arabic) is ordinarily printed, with no marks" for the two
that strip marks, "plain, as Japanese (Chinese) is written" for the two that do
not; *alt* — "the same sentence in nastaliq script", "the sentence in vertical
columns (tategaki)".

**The name is a default, and a person may change it.** On the book's own page
a person renames a level, for one language and one pass, and the new name
**follows them to their other devices** — it is a prefs key, `bk_lvl:<language
code>:<pass key>` (`bk_lvl:fa:vocal`), kept in `config/prefs.json` with the
settings that follow a person (`lib/prefs.py`; the whole key must match
`^bk_lvl:[a-z]{2,3}:[a-z][a-z0-9_]{0,15}$` and the value is at most 12
characters once trimmed, or the server keeps nothing). An empty name is a value
too: it means "the registry's name again". Which levels are *shown* stays with
the device (`bk_no1`…`bk_no5`); only the names travel. The registry is never
written for this: a rename is one person's word, not the language's.

`lib/languages.py` refuses a pass without a name — Parseh's own rows at import,
a person's row by leaving the language out with the reason in
`newlang.py --check` and the server's log — and refuses a name over 12
characters, with a line break in it, or the same as another pass's of that
language. One exception, for the sake of languages already added: a row in
`config/languages.json` written **before** names existed (no pass of it has
one) is read with the default names `languages.default_level_name` gives, and
`--check` says so as a note; a row that names some passes and not others is
simply wrong. `lib/newlang.py` writes a name and a title for every pass it
scaffolds by that same rule: *vocal* is **Sentence**, **With vowels** where
marks come off in an Arabic script (**With marks** in another) and the
reading's own name (**Pinyin**, **Kana**; **Reading** when that is longer than
12 characters) where the chunks carry words — or what the row's `vocal_label`
calls it where that says "with <reading>": Japanese's "with furigana" is
**Furigana**; *aloud* is `<reading> only`;
*chunks* is **Chunks**, *bare* is **Plain**, a vertical *alt* is **Vertical**
and a font *alt* takes its `--alt-key` ("nastaliq" → **Nastaliq**) or **Other
font**.

The *Plain* level of Persian and Arabic is unchanged by all this: it is
exactly the text as it is ordinarily printed, which is what the registry's
`strip` (above) takes off, and what its title says.

### Digits

Labels (`\parnum{۳.۱}`, contents entries) are written in the language's
digits: Persian ۰–۹, Arabic ٠–٩, Hindi ०–९, and the Latin figures everywhere
else — Japanese and Chinese write them as well as the Latin-script rows do.
The registry's `digits` is what decides, never the script:
`languages.any_to_latin_digits` reads a label of any language;
`Lang.to_native_digits` writes one.

### Videos: `video.json`

```json
{"id": "…", "url": "…", "title": "…", "title_native": "<display title in the target language>",
 "channel": "…", "language": "ja", "gloss": "it", "level": "…", "duration": "…",
 "added": "…", "blurb": "…"}
```

`title_native` replaces `title_fa`; every reader accepts `title_fa` as the
legacy spelling (`m.get("title_native") or m.get("title_fa")`). The pipeline
writes `title_native`. `gloss` is the language of the `en` field of every
chunk in `annotations.json` (§1) — the video above is Japanese glossed in
Italian — and absent it is `en`, which is what the Persian videos and every
other video written before the field existed say by saying nothing. It lives
in `video.json` and not in `annotations.json` because it is true of the whole
video, not of one caption. (It was also, when this was written, the only way
to keep it: `merge_parts.py` rebuilt the annotations from the parts. The
batches are folded in once while the video is being added, and dropped, so
nothing rebuilds them now.) Neither file marks a book or a video as still
being written: a chunk with no gloss is legal in every one (§12), and a
`"draft": true` an older version left in `book.json` or `video.json` is never
read.

**The scheme of a transliteration: `translit`.** `"translit": "ipa"` in
`book.json` or `video.json` says that the book's or the video's `tr` and the
sound groups of its vocabulary are written in IPA and not in the language's
usual scheme; absent is the usual scheme, which is what every book and video
written before the setting existed says by saying nothing, and `"classic"` is
never written. The prompts that hand out a stretch ask for what the record says
unless the person chooses otherwise for that prompt; a book that mixes two
schemes is harder to read than one that uses either, which is why it is a fact
of the book and not only a choice of the moment. The checks written for the
usual scheme (`lib/check_batch.py`'s `/ey/` and čašm of a Persian `tr`, `lib/normalize_batch.py`'s
spellings) step aside for a book that says IPA and say so in a note. It is a
key an older Parseh ignores (`BOOK_FORMAT` and `VIDEO_FORMAT` do not change);
the person sets it when the book or the video is made, and the row of a stretch's
prompt offers to change it, in either direction (a record that says nothing says the
usual scheme, so asking for IPA for a stretch of such a book offers to make IPA the
book's), written through the doors the info sheets use, `bookmeta.edit_meta` and
`ytpages.edit_meta`. Which languages offer it is the registry's
`ipa` (§1: left out, the setting is offered; `usual`, the usual scheme already is
IPA; `none`, no setting).

### The reader's mark: `col`

A chunk may carry one of four colours — `red`, `blue`, `orange`, `green` —
and it is the reader's own mark on the text, not data: no checker judges it,
no Anki card carries it, nothing is filtered by it. It is the **first**
argument of `\ch`, `\chr` and `\chp` (`\Cred`…`\Cgreen`, or empty) and the
`col` key of a video chunk (absent means none). In a book it reaches **pass 1
only**, on screen and on paper: the mark is what the reader noticed before
any help arrived, so it must not appear beside the glosses or in the bare
pass. The four names and the four shades are the same in both doors.

### A verb: `\vb`, seven arguments in every language

A vocabulary line gives a verb as `\vb`, not as `\dw`:
`\vb{form1}{sound1}{form2}{sound2}{form3}{sound3}{meaning}`, a form and its
sound three times, then the meaning. (Two exceptions, each its language's
conventions and each for want of forms: a Chinese verb has none, so it
takes `\dw` like any headword and `\vb` is kept for the two kinds of verb
that come apart in a sentence — `docs/lang/zh.md`; and an English modal has
no principal parts, and a `\vb` for one would print a *p.p.* that does not
exist — `docs/lang/en.md`.) The arity is the same for every row of the
registry and so is everything else about the macro — there is no optional
argument and no macro per language. What differs is what the three forms
*are*, which is a fact about the language, so the registry holds it:
`vb_forms` names the three in words, `vb_labels` is the pair the line prints
before the second and the third.

| code | `vb_labels` | `vb_forms` |
|---|---|---|
| fa | pres. / past | infinitive · present stem · past stem |
| ar | impf. / masdar | perfect (3rd m. sg.; its form number in the sound) · imperfect (3rd m. sg.) · masdar |
| it | pres. / p.p. | infinitive · 1st sg. present · past participle |
| ja | stem / -te | dictionary form · -masu stem · -te form |
| fr | pres. / p.p. | infinitive · 1st sg. present · past participle |
| de | pret. / p.p. | infinitive · preterite (3rd sg.) · past participle |
| tr | pres. / aor. | infinitive · present in -iyor (3rd sg.) · aorist (3rd sg.) |
| en | past / p.p. | plain form · past · past participle |
| hi | stem / perf. | infinitive · stem · perfective (m. sg.) |
| es | pres. / pret. | infinitive · 1st sg. present · 3rd sg. preterite |
| zh | split / can't | verb · A了B (a separable verb only) · A不B (a verb with a complement only) |

**A pair whose form is blank is not printed** — not the form, not its label,
not the dot before it — and the meaning is tested the same way. Only the
form decides: a sound slot is empty in every `\vb` the Turkish, Spanish and
German conventions model, and a pair with a form and no sound is a pair.
`\ifblank` takes spaces for blank. Two languages need a pair left out.
Chinese gives a separable verb its split and a verb with a complement its
"can't" form and never both: `\vb{睡觉}{shuìjiào}{睡了觉}{shuìle jiào}{}{}{to
sleep}` prints *睡觉 shuìjiào · split 睡了觉 shuìle jiào · to sleep*, where
before the test it printed a *can't* standing over nothing. And an Arabic
verb whose source says it has no verbal noun has no masdar to give. A blank
sound sets no space either (`\FrankSound`, which `\dw` and `\bw` use too):
the Turkish fixture had 3.79pt before every dot of *yağmak · pres. yağıyor ·
aor. yağar* where a `\vb` with its sounds has 1.89pt. A book whose pairs are
all filled prints as it did — six fixture editions, mini-fa with its 136
`\vb` among them, gave the same pdftotext across the blank-pair change, and
nine of the eleven across the sound change, mini-tr and mini-es moving only
line breaks.

The PDF is not the only reader of a `\vb`, and every reader makes the same
test: `texparse._voc_runs` for the book reader, whose `render_voc` prints
what it hands back, `lib/vocline.js` for a video's cloud (held equal to the
reader's on one fixture), and `texparse.voc_text` for the flat text a card's
note makes of a line (`import_old_video.tex_text` delegates to it). A pair
the PDF leaves out and the reader prints is one book teaching two things.
They agree on one more thing, a run that starts or ends with `/` taking no
space: `aux. \pw{avere}/\pw{essere}` is *avere/essere* in the PDF, the reader,
the cloud and the card. `texparse.VOC_MACROS` and `check_batch`'s argument
count hold the seven.

**What a language adds goes inside the meaning**, as one parenthesis after
it, items parted by `; `: `\vb{fahren}{}{fuhr}{}{gefahren}{}{to drive (er
fährt; aux. sein)}`, `\vb{書く}{kaku}{書き}{kaki}{書いて}{kaite}{to write
(godan; tr.)}`. An optional argument and a macro per language were both
tried for these, and both would have had every tool that reads a `\vb`
learn a new shape on the same day, failing loudly or quietly where one did
not: `texparse.parse_voc` died on `\vb[aux. sein]{…}` with "expected a group
at 3", which takes the reader's build down with it, `check_batch` counted
its arguments as 0, and a `\vbde` was refused as a macro not allowed. A word
of the language inside an extra is `\pw{…}` (with `\textit{sound}` after it
where it has one), in a book and in a video. The labels are the
language's and are not translated. A book or a video not glossed in English
gets no meaning from the dictionary (§12), and then the parenthesis is the
whole of the last argument: `\vb{andare}{}{vado}{}{andato}{}{(aux.
\pw{essere})}`.

**The registry and the `.tex` each say the labels once, and must say the
same.** `vb_labels` is the pair `lib/lang/<code>.tex` sets as
`\FrankVbPres` / `\FrankVbPast` for the PDF and `texparse` reads for the
reader; `newlang.py --check` faults a row whose pair is not two non-empty
strings, or which the `.tex` does not set, or sets otherwise (a wrapping
`\textit` aside — Japanese prints `\textit{-te}`). `vb_forms` is for whoever
types a `\vb`: the book's chunk editor builds its `\vb` button's title from
it (*a verb: infinitive · present stem · past stem — each with its
romanisation — then the meaning*), where it used to build one out of the
labels and told a Turkish annotator "stem stem, aor. stem"; `--check` faults
a row without three. A row written before either field reads `pres. / past`
and the neutral *dictionary form · second form · third form* — not
Persian's three, which would be a claim about a grammar nobody has looked
at. `newlang.py` takes both, `--vb-labels a,b` (exactly two) and
`--vb-forms a,b,c` (exactly three), and refuses a character TeX reads as
syntax in either, since both are written into the `.tex`. Eleven rows, no
fault, today.

**In a video** the vocabulary line is a book's: the same macros, entries
parted by `; `, checked by `check_annotations.check_voc` and drawn by
`lib/vocline.js` as the reader draws it. A video never reaches LaTeX, so TeX's
special characters are ordinary text in it, each written as itself; and a
line with no macro at all is a plain line, still accepted and drawn as it
always was. A verb in it is the book's `\vb`, and what only a video says goes
inside the meaning's parenthesis (`vb.tex_video`): Persian's colloquial Tehrani
present where it differs (`{to say (coll. \pw{می‌گم} \textit{mi-gam})}`: the
videos are spoken Tehrani and the books are not), and Arabic's forms without
the harakat. That last is the registry's `vb_video_bare` — true for Arabic
alone, false by default — because an Arabic caption is unvowelled and the
dictionary's forms, and a book's `\vb`, are not; it strips the words of the
language and leaves the sounds and the meaning. `newlang.py` has no flag for
it: a row that wants it says so by hand. The form the chunk has, where it is
none of the three the `\vb` prints, follows the entry, outside it, with that
word's own sound where anything says it: `\vb{venir}{venir}{viens}{vyẽ}{venu}{venü}{to
come}; here \pw{vint} \textit{vẽ}`. The plain entry the sidebar wrote before
(`می‌سازم mi-sāzam (ساختن sāxtan · pres. ساز sāz · past ساخت sāxt · to
make)`, `vb.here`) is still what a page without `lib/vocline.js` puts.

### Anki cards

```json
{"lang": "ja", "fa": "…", "kana": "…", "tr": "…", "en": "…", "opp": "…", "opp_kana": "…", "opp_tr": "…", …}
```

`lang` defaults to `fa` when absent. Tags: `<tag>-youtube` / `<tag>-book`
with the registry's `tag` (`farsi-youtube` stays exactly what it was).

---

## 4. Note types in Anki

The Persian note types keep their ids, names, fields and templates **byte for
byte** (`1724563200001` "Frank YouTube Persian", `1724563200002` "Frank
Persian Opposites"); their shape can never change (anki/README.md). Every
other language gets note types of its own, from the registry's `anki`
record:

- vocab: `[<Field>, ("Reading",)? "Transliteration", "English", "Context", "Notes", "FrontImage", "BackImage", "Source", "Reverse", "ReverseOnly"]`
- opposites: `[<Field>, ("Reading",)? "Transliteration", "Opposite", ("OppositeReading",)? "OppositeTr", "Notes", "FrontImage", "BackImage", "Source", "Reverse"]`

where `<Field>` is the registry's `anki.field` ("Arabic", "Italian",
"Japanese") and the reading fields exist only for `reading: true`. Templates
are the Persian ones with `{{Persian}}` → `{{<Field>}}`, a `{{#Reading}}`
line under the text, and the CSS `direction` set from the language. Ids:
`anki.vocab_model` / `anki.opposites_model`. `anki_export.MODELS` is the
table keyed by model id → `{lang, kind, fields, name}`; `import_apkg`,
`sync_apkg`, `notetypes` and `check_shape` all read it — none holds a
second list. A deck's `.apkg` carries only the note types its cards use, and
one font: the first face of the language's `fonts.web_files`
(`anki_export.font_file`), which travels under Anki's leading underscore. A
language whose `web_files` is empty sends none and relies on the device's own
fonts for its script.

**An id that has been used is never used again, not even when its language
leaves.** Pali was removed from the registry and its pair — `1724563200091`
and `1724563200092`, slot 9 of the grid — is **retired**. Spanish took slot 10
(`…101` / `…102`) and Chinese slot 11 (`…111` / `…112`); slot 9 stands empty
and stays empty. The reason is Anki's own import rule, the one that also keeps
the `English` field named `English` (§3): a note type is matched by its id, so
a deck anybody ever synced while Pali was here would meet a new language's
note type under the id its own cards already carry, and Anki would merge the
two — one type holding Devanagari cards and Spanish cards, on somebody else's
machine, with nothing said at either end. Those cards are the learner's and
are not in this repository, so there is no way to know whether such a deck
exists and no way to repair one that does. Ten skipped integers cost nothing;
that merge cannot be undone.

**`lib/newlang.py` carries the list itself.** `next_anki_pair` used to walk
the grid from zero and hand back the first pair no row in the registry held —
and a removed row takes its ids out of the registry along with everything else
it had, so the grid looked free exactly where it was not, and the tool offered
slot 9 the moment Pali left. The retired pairs are now a frozenset in that
file (`RETIRED_ANKI_IDS`, with the language and the date beside each), checked
along with the registry, so the twelfth language is offered slot 12
(`…121` / `…122`) and slot 9 cannot be handed out by accident. A guarantee
that rests on somebody reading a paragraph at the right moment is not a
guarantee; this one is made by the code that would otherwise break it.

**A language added on one machine takes its pair from another part of the
grid.** Parseh's own languages walk up from slot 0, and the next one Parseh
ships takes the next free slot of that walk — in the checkout it is added
in, which knows nothing of a Korean somebody added for themselves (§1, *Two
files, one registry*). Had that Korean walked the same grid it would have
taken the same slot, and after the update Anki would merge the two. So
`newlang.py` gives a language of this machine's a slot **drawn at random from
slot 1000 up** (`PERSONAL_SLOT`, ten million slots wide), checked like any
other against every id in both halves and the retired ones; Parseh's walk
stops below it (`--shipped`, §10, is the walk). At random, not the first free
one, because two people who each add a language and then swap decks meet the
same danger one step further on, and a fixed "first personal slot" would be
everybody's. A row an older `newlang.py` wrote, and `migrate()` moved to
`config/`, keeps the ids it has — they are what that person's cards already
carry — and `--check` notes that it sits on Parseh's part of the grid.

### The store, per language

- **Writing.** `anki_store.add_card` files a card under its own
  language's folder (the card's `lang`, validated there; absent → `fa`).
  A deck of that name already held *in that language* reuses its
  directory (a legacy one included); the name-collision hash is unchanged
  and never fires between two languages, which are in different folders.
  When the dashboard named a deck of another language (`deck_lang` in the
  body, or a deck of that name found in exactly one other language) the
  card still goes to the deck of its own language and the answer carries
  `refiled: {from, to, …}`, which the page shows.
- **Building.** `anki_export.build_deck` takes the deck directory (which
  already carries the language) and writes
  `anki/build/<folder>-<slug>.apkg`, named after both so two languages'
  decks of one name cannot overwrite each other.
  `anki_export.collection_dir` is what finds `anki/` from a deck
  directory, one level up or two.
- **The round trip.** `import_apkg` and `sync_apkg` match a deck by its
  Anki id (then, unambiguously, by name) across *every* language folder,
  and address decks by `path`; a deck the package brings in is created
  under the language of the note type most of its notes use (`MODELS`).
  Guid matching, anki-owned mirrors, retirement into `deleted/`, the one
  collection-level `seen.json` and the refusal to sync a package this
  toolbox built are all unchanged.
- **The endpoints.** `GET /anki/decks` answers the list, `?lang=<code>`
  narrows it; `GET /anki/build/<folder>/<slug>.apkg` builds one deck, and
  the old `/anki/build/<slug>.apkg` resolves while the slug names one
  deck, else answers with a JSON error naming the candidates. Both
  dashboards group the deck picker by language, the page's own first, and
  the "+ new deck…" placeholder suggests that language's nesting; the
  sync wizard shows each deck's language beside its path.

---

## 5. The studio (`markdown/`)

### Front matter

```
---
title: …
subtitle: …
note: …
lang: it          # prose language (hyphenation) — unchanged meaning
target: ja        # the language being learned; default fa
---
```

`store.py` records `target` in `meta.json`, files the document under
`library/<folder>/`, and moves it when a save changes the target. Cards in
the library show a language badge; a chip row filters by language (the
shared `parseh_lang` preference, §8).

### Runs of the target language

For a **script language** (a row with a non-null `chars`) runs are detected
from the registry's `chars` exactly as Persian always was: `Lang.run_re`
(space-joined words where `word_sep` is a space — fa, ar and hi — and
contiguous characters for ja and zh, whose `word_sep` is the empty string).
They render as the `.fa` span: the target font, scaled independently of the
Latin by the `--fa-scale` slider, colourable and translit-able by hover.

For a **Latin-script language** (a row whose `chars` is null) nothing is
detected — a Latin run cannot be told from the English prose around it — so
every run is **marked**: `[bello]{tl}`, or the language's code `[bello]{it}`,
or any bracket mark that already exists
(`[bello]{translit:'bɛllo}`, `[bello]{teal}`, `[bello]{teal translit:…}`):
for a Latin-script target every `[…]{…}` mark whose content has no nested
brackets and whose attributes are not `la`/`ltr`, not a footnote, not a link
is a target run. Occurrence counting (`store._run_matches`,
`_mask_uncountable`) follows the same rule, so the hover palette and the
source agree. Glosses are written `[bello]{tl} = *beautiful*`.

The prose language and the target may both be Latin: then the target must be
marked, and the prompt says so. The bare headword of a `## bello | …` lemma
heading counts as a run too (the renderers show it as one), and the studio
marks it `## [bello]{teal} | …`.

### Blocks of the target language

`[…]{fa}` and `{rtl}` were "a stretch of Persian laid out as one RTL unit".
The generic marker is **`{tl}`** ("target language"); the document's own
code is an alias (`{ja}`, `{ar}`, `{it}`), and `{fa}` / `{rtl}` remain
accepted for Persian documents. Attributes:

| attribute | meaning | languages |
|---|---|---|
| `font=<alt_key>` | the alternate face: `nastaliq` (fa), `gothic` (ja) | those with `fonts.alt` |
| `bg=quote\|sand\|rose\|sage\|lilac` | tint | all |
| `vertical` (also `mode=vertical`, `tategaki`) | columns top-to-bottom, progressing right-to-left | `vertical: true` (ja, zh) |
| `height=<em>` | the column height of a vertical block (default 22) | with `vertical` |

Direction follows the language: an RTL block is what `{fa}` always was; an
LTR block is a left-to-right paragraph in the target font. A **vertical**
block on the web is `writing-mode: vertical-rl; text-orientation: mixed`
with a fixed block height so columns wrap, scrolling sideways if needed
(columns start at the right); in the PDF it is a rotated box — the text set
in a `minipage` whose width is the column height, in a font loaded with
`Vertical=RotatedGlyphs`, rotated −90° with `\rotatebox` — which gives true
tategaki in XeLaTeX without any CJK package (verified on this machine with
Noto Serif CJK JP; the face is the language's own, from its `tex` record, so
Chinese is set in Noto Serif CJK SC by the same machinery and not by a second
copy of it). A Latin-free paragraph is auto-RTL for `fa`/`ar` as before; for
an unspaced language a paragraph consisting only of the target script is an
auto target block (LTR); for a Latin-script target there is no automatic
block.

The RTL overlay editor ("✎ RTL") becomes the **target-text editor**: its box
takes the document's direction and font, offers *Font* only when the
language has an alternate, and a *Vertical* checkbox only for `vertical`
languages; it writes `{tl …}`.

### Lemma headings

`## <target> | <translit> | <etym> | = *gloss*` is a lemma when the first
field is a run of the target script — or, for a Latin-script target, when
the heading has two or more `|` fields (a plain section title then cannot
contain `|`, which the prompt states). With a reading language the fields
are `## 漢字 | かんじ | kanji | etym | = *gloss*` (`reading`, then
`translit`); `mdparser` reads the document's `target` before deciding. The
web and TeX renderers show the reading line above the transliteration.

### The two renderers

`texgen.py` and `htmlgen.py` take the language from the parsed front matter
(`mdparser.parse` returns `fm["target"]` normalised to a registry code) and
hold it, like the footnote state, in a thread-local set at the top of
`generate()` / `render_document()` / `glosses()` and the store rewriters.
The old module constants (`FA_CHARS`, `FA_RE`, `RUN_RE`) are replaced by
accessors on the current language; **no regex for a script is written in
these files any more**.

`template.tex` gets its target-font block, direction macros and vertical
macro from placeholders `texgen.generate` fills per language:

- `\pe`/`\pel`/`\peb` wrap in `\beginR…\endR` only for RTL;
- the target font is `\tlfont` (`\vaz` kept as an alias), from the
  registry's `tex.main` with `\IfFontExistsTF` fallbacks down `tex.main_fallbacks`;
  Vazirmatn, Noto Naskh Arabic and Noto Serif Devanagari travel with the toolbox (`lib/fonts/`, copied into the build
  dir); the CJK rows use the system's faces (Noto Serif CJK JP for Japanese,
  Noto Serif CJK SC for Chinese, or the fallbacks) — a row whose
  `fonts.web_files` is empty bundles nothing;
- Japanese adds `\XeTeXlinebreaklocale "ja"` and `\XeTeXlinebreakskip = 0pt plus 1pt`;
- `\tlalt` is the alternate face (`\nasta` kept as an alias);
- `\tlvertical{<height>}{<text>}` is the rotated-box tategaki;
- `\voce` prints the reading line when there is one.

`verify.py` reads a marker comment the generator writes into the `.tex`
(`% exlex-target: ja ltr`) and checks RTL documents as before and LTR
documents in forward order; vertical blocks are excluded like `{fa}` blocks
always were.

### Typography panel

The slider labelled "Persian" is labelled with the language's name; the
sheet carries `data-lang="<code>"` (the same attribute every door uses, §8)
and `app.css` sets `--fa-font: var(--tl-font)` on `.sheet[data-lang]`, the
token coming from the generated `langs.css` (`languages.css()`), which the
studio serves itself at `{{BASE}}/static/langs.css` and links from every
template — so `app.css` holds no font stack per language. The `--fa-scale`
variable and slider keep their names.

### Prompt

`exlex/PROMPT.md` is generic: it names the target language from the
`target:` line, keeps the machinery rules, and includes what a document needs
of the language's own conventions (`docs/lang/<code>.md`, §9): its
Transliteration, its Reading and the note on writing the script — what it
takes to write a sound or a reading, and none of the rules of a reading
edition, a vocabulary line or a gloss, which a document never carries.
`lib/promptkit.py` makes the cut (`SECTIONS`: one row a section, one column a
kind of prompt), the same for the exercise prompt; a section nobody listed,
which a language may add, goes everywhere, so that it is never lost. The
prompt page has a target-language select; the copied prompt states the
target.

---

## 6. The reading editions (`books/`, `lib/`)

### `book.json` and `main.tex`

```json
{"slug": "…", "language": "ja", "gloss": "it", "title": "…", "title_latin": "…", …}
```

```latex
\newcommand{\BookLang}{ja}
\newcommand{\BookGloss}{it}
\newcommand{\FrankLib}{../../../lib}
\newcommand{\BookTitle}{…} … \newcommand{\BookAuthorLatin}{…}
\input{\FrankLib/frank-preamble.tex}
\input{\FrankLib/frank-frontmatter.tex}
\input{ch1.tex}
\end{document}
```

`\BookLang`, `\BookGloss` and `\FrankLib` are defined before the preamble is
input; the preamble `\providecommand`s all three (`fa`, `en`, `../../lib`) so
an unmigrated main.tex still builds — and every main.tex in the toolbox today
is one of those as far as the gloss goes, which is exactly what "absent means
English" has to mean in TeX as well. `\BookGloss` is `book.json`'s `gloss`
and nothing else may set it; `lib/draft.py` writes the two together.

`\BookTitle`, `\BookAuthor`, `\BookTitleLatin` and `\BookAuthorLatin` are the
other pair kept in step, and by a different tool: the reader's **book info**
sheet, over `lib/bookmeta.py`. Nothing re-derives main.tex's title page from
book.json at build time -- the book is built by running LaTeX on main.tex,
and book.json is never read during that -- so a metadata edit that touched
book.json alone would leave the next PDF naming the old title, silently.
`bookmeta.edit_meta` rewrites both files, or neither: a value that cannot
sit inside a bare `\newcommand{...}{...}` (one of `\ { } $ % & # _ ^ ~`,
unescaped -- the reader's own refusal, same characters `lib/texwrite.py`
refuses in `fa`/`kana`/`tr`/`en`) refuses the whole edit before book.json
changes either. It is never upper-cased: `lib/draft.py`'s own main.tex
writes `\BookTitleLatin` exactly as typed (Python's `str.upper()` does not
know a Turkish dotted i from an English one, and the registry keeps no case
table for it), while `lib/newbook.py`'s page uppercases it in the browser
before main.tex is ever written -- a difference an edit here cannot tell
apart from a title simply typed in capitals, so it always writes the field
as given.

### The preamble, per language

The gloss is set in `\BookGloss`'s own language, not in the `english` every
gloss used to be wrapped in: an Italian gloss then hyphenates by Italian
rules and an Arabic one runs the other way. For a language the toolbox
teaches, babel's name and the direction are the registry's (`tex.babel`,
`dir` — the same pair `languages.gloss(code)` hands the reader and the Anki
card); for a prose-only code the preamble provides a language of its own and
lets babel read the locale from `import=<code>`, which is why no list of the
languages one may write in is kept in TeX either. That is one question, and
the language files below answer a different one: `\BookLang` decides
everything about the **text**, `\BookGloss` only what the meaning column is
set in.

`lib/frank-preamble.tex` keeps the page, the sizes, babel's core, navigation,
the `frank` environment and the passes; everything a language decides is
`\input{\FrankLib/lang/\BookLang.tex}` — one file per row of the registry,
`lib/lang/<code>.tex`, and `lib/lang/_template.tex` is what `newlang.py`
writes the next one from. Each language file must define:

- `\FrankLangName` — the babel language from the registry's `tex.babel` (babel's name, not the folder's: German's is `ngerman`) and its `\babelprovide` + `\babelfont` (fonts from the registry's `tex` record, with `\IfFontExistsTF` fallbacks; the locale imported is `tex.import`, which need not be the code, though every row's is one today — §12 says why the field stays);
- `\FrankAltFont` (the alternate face) or leave it undefined; `\ifFrankHasAlt`;
- `\ifFrankHasBare` — whether the bare pass differs from pass 1 (fa/ar/ja/zh yes — Chinese since its pass 1 carries pinyin over each word; the Latin-script rows and Hindi no, printing in pass 1 everything a bare pass could show); `\ifFrankHasReading`; `\ifFrankHasAloud` — whether the reading pass exists, which is every row with `words` (ja, zh);
- `\ifFrankRTL`, so the chunk column and its gloss sit on the language's side (RTL: chunk right, gloss left; LTR: chunk left, gloss right) and `\pw` isolates with `\babelsublr` only for RTL;
- the Lua `frank_strip` body (fa/ar drop the harakat range; every other language's is the identity) and `frank_latin` digit map (fa ۰–۹, ar ٠–٩, hi ०–९, others identity — the registry's `digits`, never the script);
- `\FrankHowTo` — the "How to read this" text of the front matter (Persian's mentions harakat and nastaliq; Japanese's and Chinese's walk through their five passes, the reading over each word first; a Latin-script one has two passes to describe and then whatever its pronunciation line is for);
- for a **reading** row (`ja`): `\jruby{text}{kana}` (a plain `\vbox` group-ruby) used by `\chr` in pass 1, and the kana line in the gloss block;
- for a **words** row (`ja`, `zh`): `\FrankRuby{word}{reading}`, what is set over one word of a `\chrw` or `\chw` (`\jruby` unless the file says otherwise; Chinese sets small upright pinyin, stacked above a word wider than the column), and `\FrankAloudText{reading}`, how a chunk's reading is set in the reading pass (Chinese's through `\FrankRoman`);
- for a **vertical** row (`ja`, `zh`): the vertical pass as a rotated box, through the row's own babel language — the hook is `\ifFrankHasVert` and the pass is `\FrankVertPass` (§12), so the second vertical language needed the mechanism and not a change to it.

`\chr{col}{fa}{kana}{tr}{voc}{en}` is defined in the core preamble: in pass 1
it sets `\jruby{fa}{kana}` when `\ifFrankHasReading`, the gloss block gets
the kana as a first line, and the collect buffers receive `fa` exactly as
`\ch` does. The Persian book must build **byte-identical PDF text** to what
it built before the refactor (`pdftotext` before/after, the test the
narration work already used).

`\chw` and `\chrw` are `\ch` and `\chr` with the word line as their last
argument. Pass 1 and the chunk column set `\FrankWords{fa}{words}`:
`lib/wordline.lua`, loaded once with `dofile`, turns the line into one
`\FrankWord{text}{reading}` per word with `\FrankWordSep` between them, taking
the characters from `fa`, and stops the build naming the chunk when the line
does not fit it. The word line only ever reaches the pass-1 buffer through
`\gappto`; `\FrankBuf` still gets `\Strip{fa}` alone, because expanding
anything but plain text there is fatal. A reading pass, `\FrankAloudPass`,
follows pass 1 wherever `\ifFrankHasAloud`: each chunk's own reading
(`kana`, or `tr` where there is no reading) with the punctuation that closes
its text, as `wordline.aloud` gives it in all three parsers -- so a kanbun
chunk is read in its spoken order, and a `\ch`, `\chr` or `\chp` contributes
too.

### `lib/books.py` (done)

`all_books()` walks `books/<folder>/<slug>/` (and legacy `books/<slug>/`);
`Book.language` (code), `Book.lang` (the `Lang`), `Book.gloss` (code) and
`Book.gloss_lang` (the `Gloss`), `Book.folder`, `Book.rel_from_books()`
("persian/farsi-shakar-ast", for URLs and the index),
`Book.check_placement()`; `find_book()` takes a slug, a `<folder>/<slug>`, a
directory, or the current directory. `language_problem()` and
`gloss_problem()` name a code the toolbox has not got, and `find_book()`
refuses on either: the tools that write files must not produce them in a
guessed language, and of the two the gloss is the one that would go
unnoticed — a book glossed in the wrong language looks right and merely
breaks its meanings at another language's points.

### The reader (`lib/tex2html.py`)

Language-aware throughout: `lang`/`dir` attributes and fonts from the registry
(through `parseh.css`'s per-language tokens, §8); digits; the passes that
exist (a button appears only for each of the language's passes, and it wears the
pass's **name**, never a digit — the registry's `name`, or the person's own
word for it, §3 "The passes, and what a page calls them"; what a button
hides is told by the pass's key and not by its place in the row: the vertical
pass is the vertical one for Japanese and for Chinese alike, `.p4.vert`, with
the CSS `writing-mode: vertical-rl`); pass 1 of a reading language sets
`<ruby>fa<rt>kana</rt></ruby>` per chunk; the gloss gets `<div class="kana">`;
`words()` splits with `Lang.split_words` (a chunk of an unspaced language is
one word); the typography panel's first slider is labelled with the language
name; the Anki dashboard labels its first field with the language name, shows
a *reading* row for reading languages, sets `dir` only for RTL, and tags
`<tag>-book`. `META` carries `lang` and `dir`. The contents panel's incipit is
in the language's script. The chunk sheet's `\vb` button names the
language's three forms from `vb_forms` (§3), and the sheet's sources column
opens on the physical left in every book, a right-to-left one included,
because the sheet is chrome and not text (§12).

### The pipeline tools

Every tool takes its language from the book (`books.Book.lang`, a `Lang`)
and uses `Lang.strip`, `Lang.to_native_digits`, `Lang.split_words`. The
Persian conventions (`/ey/`, `/ow/`, sukun, چشم, بودن's stem, the
never-gloss list, the ezafe seam scan, `normalize_batch`'s spellings) run
**only for `fa`**; the generic checks (fidelity, macro allowlist, empty
fields, `kana` required for reading languages, `tr` required where
`require_tr`) run for all. `assemble.py` writes `\chr` when the language has a
reading, labels in the language's digits, and refuses a reading language's
chunk without `kana`. `inject_parstart.py`, `verify_book.py`,
`apply_pointing.py`, `merge_batch.py`, `chapter_src.py` and `extract_pdf.py`
(which gets `--lang`, its "several words of the script" filter using
`Lang.has_script`) read digits and marks through the registry.

### Building and adding

`build.sh` walks `books/*/*/` (and warns about a book.json directly under
`books/`); `.gitignore` patterns become `books/*/*/…`; `install.sh` and
`lib/launcher.py` walk the same way and check for a CJK font when a Japanese
or a Chinese book exists — those are the rows whose `fonts.web_files` is empty
because their face is tens of megabytes and the system's. `lib/make_index.py`
groups the library page by language, each group headed by the language's name,
with the chip row. `/books/add/` (`lib/newbook.py`) has a language select; the
recipe and `docs/new-book-prompt.md` carry `{{LANG}}`, `{{LANG_NAME}}`,
`{{LANG_FOLDER}}` and the language's conventions block (`docs/lang/<code>.md`)
in place of the Persian-only rules, which move into `docs/lang/fa.md`. The
reference edition offered is one of the same language when there is one, else
the Persian one with a sentence saying the method is the same and the
conventions differ.

---

## 7. The video player (`youtube/`)

- `youtube/videos/<folder>/<id>/`; `ytpages.list_videos` walks two levels; the index groups channels under language headings with the chip row; `/youtube/v/<id>/` and `/youtube/c/<slug>/` are unchanged; the player page fetches `videos/<folder>/<id>/annotations.json`.
- `check_annotations.parse_transcript(path, language)`: a caption is *plain* when the language is a script language and the caption has no character of the script (`Lang.has_script`); for a Latin-script target no caption is plain automatically — an English aside is a chunk with `"plain": true`, which for Latin-script targets the annotator **is** allowed to write. `check_chunk`: a chunk of the target script needs `en`, `tr` where `require_tr`, `kana` where `reading`; the duration and chapter regexes take their words from every language's `duration_units` / `chapter_words`.
- `api_prepare` / `api_add`: the add page has a language select (defaulting to the shared preference); the transcript is parsed with that language; the video is written under its folder with `language` and `title_native`. The prompt (`youtube/docs/chat-prompt.md`) is generic — `{{LANGUAGE}}`, the generic conventions (`youtube/docs/conventions.md`: chunking, fields, the repetition rule, plain captions, with no list of languages: the registry is the list), the rule on the meaning (`docs/meaning-rule.md`) and the language's block (`docs/lang/<code>.md`, §9); the worked example is that file's `## Example`, so a fresh install has one and no video of the shelf is quoted in a prompt.
- `player.js` / `player.html` / `style.css`: `window.YTFRANK.lang` is the language record; the transcript line gets `dir`/`lang` and the font token; the cloud shows `kana` above `tr`; the run regex for words of the target script inside a gloss comes from `lang.chars` (none for Latin); `bare` runs are told apart with `lang.chars`; word spans follow `word_sep`; panel and dashboard labels use the language name; the dashboard has a *reading* row for reading languages; the card carries `lang`, `kana`, `opp_kana`.
- `merge_parts.py`, `check_part.py`, `slice_part.py`, `import_old_video.py` pass the language through as they already do (`video.json["language"]`).
- The edit window's sources column opens to the left of the fields, and a verb the language's recipe recognised goes into the vocabulary line as the book's own `\vb` with what only a video says added (`vb.tex_video`, §3), parted from what is there by `; ` and without the marks where the registry's `vb_video_bare` says so (§12); a row's arrow and the sounds it shows are the lookup's, each word isolated in a `<bdi lang>` so a right-to-left pair reads in the row's order.

---

## 8. Shared chrome (`lib/parseh.css`, `lib/parseh.js`, the hub)

- Per-language font tokens are **generated from the registry** by `languages.css()`: the Parseh server serves them at `/lib/langs.css`, the studio at `{{BASE}}/static/langs.css`, and every page links the file after its own stylesheet:
  ```css
  :root{--tl-font-fa:…;--tl-alt-fa:…;--tl-font-ar:…;…}
  [data-lang=fa]{--tl-font:var(--tl-font-fa);--tl-alt:var(--tl-alt-fa);--tl-dir:rtl;--tl-alt-lh:2.6}
  …
  ```
  `parseh.css` (and the studio's `app.css`) declare the `@font-face` of the bundled faces — Vazirmatn, Noto Nastaliq Urdu, Noto Naskh Arabic and **Noto Serif Devanagari** (one `woff2` each in `lib/fonts/`; a face may be named by more than one row — Vazirmatn is Persian's main and Arabic's fallback — and which faces travel is read from every row's `fonts.web_files`, never written out, §12) — and nothing per language. Content elements carry `data-lang="<code>"` (a card, a reader's `<html>`, a player's `<html>`, a sheet) and use `var(--tl-font)` / `var(--tl-alt)`; the nastaliq/RTL rules on `a.book .fa`, `.hub .dfa` etc. become `[data-lang]`-scoped (direction from `dir` attributes or `var(--tl-dir)`, never a bare `direction:rtl`).
- The chip row is `languages.chips_html(counts)`; `parseh.js` wires it (`Parseh.lang`).
- `parseh.js`: `Parseh.lang` — the shared preference `parseh_lang` (`all` or a code), `get/set/apply`, and the wiring of `.parseh-langs` chip rows: clicking a chip sets the preference; elements with `data-lang` under a `[data-lang-filter]` container are hidden when they do not match; the row shows counts. Index pages (hub, `/books/`, `/youtube/`, the studio library, `/exercises/`) render the chip row server-side with `languages.chips()`.
- The hub's doors count for the picked language. Each count is one tag written by `serve.count_tag`, carrying every language's number in `data-counts` (`{"all": "12 videos", "fa": "3 videos", …}`); `parseh.js langApply()` writes the picked one into it. No door lists a tag per language beside its count.

---

## 9. Conventions per language: `docs/lang/<code>.md`

One file per language, the binding conventions for annotators of both books
and videos: what `fa` must reproduce, the transliteration scheme, what the
vowelled/bare distinction is, the reading rule, what to hyphenate, what
never to gloss, and what a verb's `\vb` gives — its three forms in the
registry's order (`newlang.py` writes that paragraph from `vb_forms` and
`vb_labels`), what goes in its parenthesis, and which verbs, if any, take a
`\dw` instead (§3). `docs/lang/fa.md` is the Persian scheme lifted out of
`youtube/docs/conventions.md` and `NOTES.md` §4; every other language's is
written new, from `docs/lang/_template.md`. The generic parts (chunk size,
the fields, the repetition rule, the rule on what a meaning says) stay in the
prompts and are the same for every language: `youtube/docs/conventions.md`
(with `chat-prompt.md`, the add page's video prompt), `docs/new-book-prompt.md`
(the instructions an agent making a book is given), `docs/region-prompt.md` (a
stretch of a book or a video glossed by an LLM, filled in by
`lib/glossregion.py`), and `docs/meaning-rule.md`, which those three prompts
embed (`{{MEANING_RULE}}`). `docs/lang/<code>.md` is read afresh for every prompt
and **cut to what that prompt needs** by `lib/promptkit.py`: the sections it
takes are named by one table (`SECTIONS`) — a gloss prompt for a stretch takes
everything but Chunking, a prompt for a whole book or video takes everything,
a document's prompt takes Transliteration and Reading — and what only a book,
or only a video, is told is marked `{{?book}}…{{/book}}` or
`{{?video}}…{{/video}}` in the file, so each prompt reads clean for its
surface and no template has to say "where this speaks of a book, skip it".
Two sections serve the gloss prompts beyond the rules: `## Example`, a chunk or
two of the language with its transliteration, vocabulary line and an
**aligned** meaning, which the add page's prompt carries in place of a video
from the shelf, and `## Vocabulary`, **one** convention for a book and a video
(the books' macros). The sources sidebar's buttons are not a convention and
are not in these files: the guide documents them. A language's conventions
therefore reach every LLM that glosses in it, and only the part it needs.

---

## 10. Adding a language

One command, and the two pieces of prose it cannot write.

```sh
python3 lib/newlang.py                 # what it needs, and the languages there are
python3 lib/newlang.py --check         # every entry validated, every file it needs present
python3 lib/newlang.py ko --name Korean --native 한국어 --script other \
    --chars '\uAC00-\uD7AF\u1100-\u11FF' --font 'Noto Serif KR' --web-font NotoSerifKR.woff2
```

`lib/newlang.py` writes all six things a language is: the entry, in
**`config/languages.json`** — the registry's second half, this machine's, which
no update touches (§1, *Two files, one registry*) — then `lib/lang/<code>.tex`
and `docs/lang/<code>.md` from the templates beside them
(`lib/lang/_template.tex`, `docs/lang/_template.md`), and the three content
directories, each with a `.gitkeep` so the layout survives a clone. The two
files and the directories are where they always were: the whole toolbox looks
for them there, and no release's manifest names them, so an update leaves
them alone.

**Where the entry goes is the one choice left to make.** Without a flag it is
a language of this machine's. **`--shipped`** is the other case: a developer
adding a language to Parseh itself, for everybody, in a checkout. The entry
then goes into `lib/languages.json` (spliced into the text, so the entries
already there come out byte for byte) and its code into that file's
`_shipped`, in the same write — a row there that `_shipped` did not name would
be taken for somebody's own and moved out to `config/` the first time an
install started. **`--migrate`** moves the rows of `lib/languages.json` that
`_shipped` does not name to `config/languages.json` on request: what Parseh
does by itself as it starts (§1), for the one place it will not, a git
checkout. Adding a language runs the same move first, so the new row lands in
a registry whose two halves already say whose is whose.

It derives what it can — the folder, the tag, the babel
name, the passes (each with its name, the word its button wears, and its
one-line title, §3), the labels, and the Anki model ids on the
`1724563200000 + 10·n + 1/2` grid, checked against every id in both halves:
the next free pair for `--shipped`, and a free pair drawn from slot 1000 up
for a language of this machine's (§4) —
and refuses what a default cannot rescue: a code or folder already in use, a
code that is not two or three letters, a `chars` that does not compile as a
regex in Python **and** as a JS RegExp source. The one thing the grid cannot
see is a **retired** pair — a language that has left takes its ids out of the
registry with it, so the tool would offer them again and must not be let to
(§4). A font the machine has not got is a warning, not a refusal: the entry
may be written for another machine. The verb entry's shape is the row's
too: `--vb-forms` names the three forms and `--vb-labels` the two labels
printed before the second and the third (§3), and a row written without
them gets the neutral names and `pres.` / `past` — which the tool quotes
back when it finishes, so that nobody leaves Persian's grammar on a
language by not looking.

What is left by hand, and what the tool lists when it finishes:
`\FrankHowTo` in the `.tex` (§6), the seven sections of the `.md` (§9), a
fixture under `tests/fixtures/` if the smoke test is to cover the language —
it only tries what it has a fixture for — the studio's starter document
`markdown/exlex/starters/<code>.md`, a guided tour of everything a document
can hold with every example in the new language and one exercise of every
kind, written like the ones already there (`it.md` is the model for a
Latin script, `hi.md` for a script of its own, `ar.md` for one written right
to left; until it exists the studio builds a short generic one from the
row) — and **a verb recipe**,
`lib/verbs/<code>.py`. A bundled face in `lib/fonts/` with its `@font-face`
in `lib/parseh.css` and the studio's `app.css` (§8) is left by hand too; the
tool warns, before anything else, of a `--web-font` not yet in `lib/fonts/`,
and says nothing of the `@font-face`.

The recipe is the one piece no template can start, because which forms a
verb gives is the language's grammar. Without one the dictionary's verbs are
offered in the gloss editor as `\dw`, which is the toolbox as it was before
any recipe existed and not a fault — `tests/smoke.py` names the language and
moves on — and with one they are offered as `\vb` (§12; the recipe, the hand
table `lib/lang/<code>.verbs.json` beside it, and the eight cases under
`tests/fixtures/verbs/` that try it without a dictionary). The list used to
end without it, so a new language's author learnt from this section or not
at all why every other language's verbs came as `\vb` and theirs did not;
it now names the recipe, the hand table, the command line that tries one
and the fixture file. For a language with marks to strip it also names
**`vb_video_bare`**, which goes in the row by hand — there is no flag — for
a language whose videos are written without the marks its dictionary keeps
(§3). The other files a language may have beside its `.tex` —
`<code>.lookup.json`, `<code>.ipa.json`, `<code>.chunk.json` — are read only
where they exist (§12), and a language starts without them.

Then `python3 lib/newlang.py --check` (non-zero when anything is missing; it
walks every language of both halves, not only the new one, marks the ones
added on this machine, and reports a row of theirs the registry had to leave
out) and `python3 tests/smoke.py`.

The process end to end, written for someone who has not read the code, is the
guide's page **"Adding a language"**
(`html-guide/markdown/lookup-and-languages/adding-a-language.md`): the one
command and its flags, what is left to write by hand, the font, the check, and
worked examples.

### Easier since a0.6.1: one place, a related language, the prose by a chatbot

**No file keeps its own list of the languages.** What used to be written
per language outside the registry is now a field of the row: `analysis`
(which program reads its word forms and its sentences: lib/analyzer.py's
MORPHOLOGY and SYNTAX are built from it), `examples` (what the lookup page
shows for a dictionary, a corpus and a model, and `macros`, what each gloss
button writes), `compounds` (`"parts"` where a compound is glossed as a
whole with its parts, else a light verb), `like` (the related language it
was started from). The pages learn a language's name from `/lib/langs.css`
(`--tl-name`, beside `--tl-dir`). Two tables of the browser stay, FROZEN at
the eleven of a0.6.0 because readers built before the record carried the
same facts still ask them: the level names of lib/gear-reader.js and the
gloss-button examples of lib/vocbuttons.js; a language added since has
never had such a reader, and needs no edit there. The tests count from the
registry (`_shipped`), never a number.

**`--like CODE`** starts a language from a related one: its verb entry's
shape, its `compounds`, a copy of its chunking rules to review, and `like`
in the row. **`--features`** (lib/langfeatures.py) says, per language and
feature by feature, what it has, what it is without the rest and what adds
it -- the same list **Settings → Languages** shows (lib/languagespage.py),
where a language of this machine's is added from a form and its prose is
written with a chatbot: lib/langprompts.py gives a prompt per piece
(conventions, the "How to read this" page, the studio starter, the
examples, the lookup rules, the chunking rules), the related language's
file as the model, and an intake that checks the answer's shape -- the
seven sections, a `\FrankHowTo` that only writes text (no `\directlua`,
`\input`, `\def`…), JSON that parses -- before it writes it. Adding and
taking prose in are the computer's alone (lib/settingspage.py SETTINGS
`languages.add`, `languages.prose`). `languages.reload()` puts a language
added from the page into every page at once. `python3 lib/getanalysis.py
measure <treebank>` prints a new UDPipe pin.

### Varieties: a language written in more than one way

A row may name **varieties** (`varieties`: `[{key, name, kaikki: [[extract
name, lang_code], ...]}]`, and `standard_name` for the standard one):
Arabic's `egy`, `lev`, `gulf`, `mor`. A book's or a video's `variety`
(book.json, video.json; none is the standard language) says which its text
is in. `languages.get("ar.egy")` (or `Lang.with_variety`) is the same Lang
with `key` = `ar.egy` and `variety_name`, and its key is the stem of its own
files: `dict/ar.egy.db` (lib/getdict.py builds it from every extract the
row names, accepting their `lang_code`s) and `lib/lang/ar.egy.lookup.json`,
read before `ar.lookup.json` (lookup.rules), with `max_peel` up to 3.
`lookup.look_up(..., variety=)` looks each word up with those rules in the
variety's dictionary and then in the language's, the variety's hits first
and marked (`variety`, and its name at the head of the hit's note). The
analyzers are not asked for a variety: they read the standard language.
A prompt for a book or a video in a variety names it before the
conventions (promptkit.language_text).

---

## 11. What did not change

The Persian content and its tools behave exactly as before: same `\ch`, same
harakat rules, same `farsi-*` tags, same note types, same URLs for the
videos and the studio, same `book.json` fields (plus `language`). The
`fa` key stays, and so do the `en` key and the `English` field of the note
types. Nothing in the toolbox declares a `gloss` and nothing has to: absent
is `en`, which is what all of it is glossed in, so every book and every video
means today exactly what it meant before the field existed. The Persian book
must rebuild to the same PDF text and the same reader; the four Persian
videos must pass `check_annotations.py`; the Persian studio document must
render the same HTML and still verify `186/186` in its PDF — it is
`tests/fixtures/studio/persiano/persiano.md` now, moved out of the studio's
examples when those were cleared, because the count is a property of that
exact document and no replacement can inherit it.

That content has since left the repository — a book, a video and a note are
the owner's, and `books/`, `youtube/videos/` and `markdown/library/` ship
empty behind a `.gitkeep` — but the guarantee did not leave with it. It is
owed to those files wherever they are kept, and it is what a change is still
to be tried against. Inside the suite the fixture editions and fixture videos
stand in for them — Persian's video fixture and Arabic's were written when
the four Persian videos left, so the door those four were covering is covered
still; `tests/smoke.py` also tries whatever is actually on the shelf, and says
by name which door an empty one leaves uncovered.

The editing doors added since (§12) do not touch that. They wait behind a
pencil — a reader who never presses one never meets any of it — they write
one chunk at a time and leave every other byte of the file alone, and they
refuse an edit that would stop a paragraph reproducing `source/paras/` or a
caption's chunks reproducing its caption. A Persian book or video that
nobody has edited is byte for byte the file it was. The download's three
shapes (§12) do not touch it either: they move only a narration, the Persian
edition has none, and its bundle is byte for byte — manifest included, with
no shape written into it — the one that door made before the shapes existed.

The verb entry (§3, §12) holds the same line. A `\vb` whose pairs and
sounds are all filled prints as it did — the Persian fixture edition's 136
are, and its pdftotext is byte for byte what it was — and what a dictionary
drafts for a verb reaches a file only through the editor's save, like
everything else the sources column offers. The column opening to the left,
the ruled panel and the note preview change what a page shows and nothing
it stores.

---

## 12. Implementation notes (what the code settled beyond this document)

Recorded after the first implementation, so the contract and the tools say
the same thing.

- **The Latin-script model is a shape, not a list.** Its members are the rows
  whose `chars` is null — six of them today, Italian, French, German, Turkish,
  English and Spanish — and they are one shape in the registry: `chars` null,
  `strip` null, two passes, no reading, no vertical setting, `require_tr`
  false, `translit_label` "pronunciation", and no font of their own — the core
  roman (TeX Gyre Pagella) sets them, so a chunk and its English gloss differ
  by size and colour only. What a new member actually decides is a handful of
  strings: babel's name for it and its hyphenation patterns (`italian`,
  `french`, `ngerman`, `turkish`, `english`, `spanish` — babel's name for
  German is not the folder's), the native name, `duration_units`,
  `chapter_words`, and its Anki pair. Adding the three **needed no tool taught
  about them**: three rows, the six files and nine directories `newlang.py`
  wrote, and not one line anywhere else that asks whether a language is `fr`,
  `de` or `tr`. That is what §1 is for, and these are the first languages it
  was tried on: added to finished code rather than alongside code being
  written. (The commit does carry `lib/newlang.py` and five `lib/lang/*.tex`
  edited as well, and none of them is about these three: it is `vb_labels`
  entering the registry and the scaffold — the verb-label item of the audit
  below, arriving one commit early because the three rows had to be written
  with it.) What the three did do is make the leaks in §1 visible, and the
  audit that followed them changed nineteen files — a hard-coded conjunction
  in the duration checker, a locale-blind `.lower()` in four places that a
  Turkish `İ` corrupts, a punctuation class written for Persian's `، ؛ ؟` that
  never learned ASCII's `, ; ?`, the reader printing its own verb labels
  instead of the language's and the free text of `\vb` and `\bw` as source
  instead of parsing it, an Anki deck that went invisible the moment a
  language took the folder name it was sitting under, and no hyphenation
  patterns installed for any of the four Latin-script languages, so every one
  of them broke its lines at English points. Every one of them was wrong
  before today and wrong for a language already in the table; the new three
  only made someone look. A language added to a table is cheap. A language
  added to a table is also the best audit that table gets.

  **Spanish was that shape a second time, and nothing at all was learned for
  it.** One row — babel `spanish`, patterns `spanish`, *segundo / minuto /
  hora*, *capítulo*, Anki slot 10 — and not one line anywhere asks whether a
  language is `es`. That is what the audit above bought: the first three
  Latin rows found the places holding an assumption, and by the time the
  sixth arrived those places were reading the registry instead. The first
  member of a shape proves the shape can be written; the second proves it was
  a shape and not a special case, and the sixth is only a row.

  Two things the shape does not settle,
  and each `docs/lang/<code>.md` must: `require_tr: false` makes the
  pronunciation line editorial rather than checked — Italian gives one only
  where the spelling misleads, French needs one far more often, English takes
  the licence straight back (below), and each language's file says when — and
  a Latin-script target's runs are **marked** in the studio (§5), which is a
  rule about the script, not about Italian.
- **Devanagari is a script kind, not a hand-typed row.** `lib/newlang.py`'s
  `SCRIPTS` table carries a `devanagari` entry (the block plus the two
  extension blocks plus ZWNJ and ZWJ, a space between words, the Devanagari
  figures, no `strip`, OpenType `Script=Devanagari`, `require_tr` true), so
  the next Indic language is `--script devanagari` and nothing else. Hindi is
  the only row using it today, and the entry is right anyway: what is in it
  is true of the script and not of the language, which is the whole
  difference between a script kind and a row somebody typed the flags into.
  **ZWNJ and ZWJ are inside the character class and are not separators**: in
  Devanagari they are how a writer says whether a virāma makes a conjunct or
  a half-form, and a run broken at one would be two runs of a word that is
  one.

  Two things the Devanagari rows raised, and both outlived the row that
  raised them:

  - **A row's `tex.import` need not be its code, and the field stays although
    nothing needs it now.** babel ships no `pi.ini`, and Devanagari Pali
    wanted exactly what Sanskrit-in-Devanagari wants, so the row that has
    since left imported `sa-Deva`. The registry always had the field; what
    was missing was any way to *set* it, because `newlang.py` wrote the code
    into it. It now takes `--import`, and `--check` asks whether the TeX
    install carries the ini — a note and not a fault, on the same grounds as
    the font check, because the wrong answer to this one is a book that dies
    in lualatex days later with "Unknown language" and nothing nearer to
    blame. Every row's `tex.import` is its own code today. The field and the
    flag stay, for the reason given under `fold` below: the thing that had
    one user is a fact about babel's locale files, not about the language
    that first met it, and the next language whose locale babel spells
    differently would otherwise have to rediscover it from a build failure.
  - **One face, more than one row.** Two rows naming the same
    `NotoSerifDevanagari.woff2` is how it came out that the studio kept a
    hand-written list of which faces travel. It no longer does:
    `markdown/app/server.py`'s `WEB_FONTS` takes the target-language half
    from every row's `fonts.web_files`. A language that bundled a face and
    was missing from that hand-written list rendered in the reader and fell
    back to a system font in the studio, on the same screen, with nothing to
    say so. The sharing today is Persian's and Arabic's — Vazirmatn is
    Persian's main face and Arabic's fallback — and Hindi's Devanagari face
    is named by one row alone. Neither fact needs anything done about it,
    which is the point: there is no longer a list anywhere for a row to be
    missing from.

  Hindi has no third pass, for the reason the Latin-script rows have none:
  Devanagari writes its vowels, so there is nothing to take off and pass 3
  would reprint pass 1. What the transliteration line carries instead is what
  the script does *not* write — the dropped schwa, `कमल` *kamal*.

- **Chinese is the second row of two shapes, and the first case that tells
  two registry fields apart.** `lib/newlang.py`'s `SCRIPTS` table carries a
  `cjk` entry as it carries `devanagari`, so the row itself was cheap. What
  the row is worth recording for is what having a *second* of something makes
  visible.

  It is the second row whose `word_sep` is the empty string, and the second
  whose `vertical` is true. Both of those already had a mechanism written for
  them — `Lang.run_re` reads runs off contiguous characters where there is no
  separator, `chunkdiv` divides between any two characters, `\ifFrankHasVert`
  and `\FrankVertPass` set a rotated box — and the second user needed the
  mechanism and not a change to it, which is the only way to find out whether
  the first one was generalised or merely parameterised. The one thing the
  row says for itself about having no spaces is in TeX: its `tex.options`
  carries `intraspace=0 .1 0`, which is how babel is told that a line with no
  spaces in it may none the less stretch between characters.

  It is the **first unspaced row with no reading**, and that is the one that
  taught something. `reading` and `translit` had never been apart: the only
  language with either had both, so nothing distinguished *a line in Latin
  letters for a reader who cannot read the script* from *a line in the
  language's own sound-spelling script for a reader who can read that part of
  it*. Japanese needs both and the kana is what goes over the text, because
  rōmaji as furigana helps nobody. Chinese needs only the first: pinyin is
  Latin letters, so pinyin **is** the transliteration, `reading` is false and
  `reading_label` is null (§3). Two fields, two ideas, and it took a second
  unspaced language to make the difference cost anything.

  Three smaller things the row settled:

  - **A pass label is an identity, not a position.** Chinese had three
    passes and they were labelled **1, 2 and 4**. There was no bare pass —
    nothing is taken off a Chinese line — and the vertical pass was 4 wherever
    it appeared, Japanese's included. Numbering the buttons by their position
    in the list would have printed Chinese's vertical pass as *3* and made one
    digit mean two different things in two languages. The word layer then gave
    both languages five passes, labelled 1–5 — with the reading over each
    word, the reading alone, the chunks, plain, vertical — and Chinese a bare
    pass, since its pass 1 now carries pinyin to take off. The labels moved;
    the CSS classes, which follow the pass's key and not its label, did not:
    the vertical pass is still `.p4`, and the reading pass is `.p5`. (Since
    a0.5.0 a page does not print the digit at all: a button wears the pass's
    `name`, and the label is left to the PDF and the checkers, §3.)
  - **`translit_label` earns its keep on a proper noun.** Persian and Arabic
    say *transliteration*, the Latin-script rows say *pronunciation*,
    Japanese says *rōmaji*, and Chinese says **pinyin** — the name of a
    standard the reader may well know already, and not a scheme this series
    chose. The field was in the registry so a language could name its own
    line; this is the row where the name is the answer.
  - **`require_tr` is true for exactly the rows with a `chars`.** Chinese
    makes it five of five. No code enforces the correspondence and none
    should — they are two questions — but it is what the pair of fields
    means: a reader who cannot yet read the script has nothing on the page
    without that line, and a reader of a Latin-script language has the text.

- **One question, one answer: `available` and `about` must not disagree.**
  They did, and it made the whole dictionary look broken. `_conn` cached
  its result per thread and per language — so whatever a thread found the
  *first* time it asked, including "there is nothing here", it went on
  answering forever. On a threading server that meant: press **get it**, and
  every thread that had served a request before the build kept saying there
  was no dictionary.

  It showed as two symptoms that seemed unrelated, which is what made it
  worth writing down:

  - the setup page offered **get it** for a dictionary plainly sitting in
    `dict/` — because it asks `about()`, which went through the stale cache;
  - the reader drew the panel's header with *nothing under it* — because
    `serve._lookup` asked `available()`, which asked the filesystem and said
    yes, and then `look_up()` asked the same stale cache and had nothing.

  `_conn` now stats the file every call and reopens when `(mtime, size)`
  changes — appeared, rebuilt, or thrown away — and `available()` goes
  through `_conn` too, so a file that exists but cannot be opened is not an
  available dictionary and nothing can be told two different stories. A stat
  is cheap; being permanently wrong is not. The `_CONNS.map = {}` calls that
  `serve.py` used to make after a build are gone: they only ever cleared the
  one thread that ran them, which is why they never worked.

- **The dictionaries are set up from one page, and it is linked from three
  places.** `/lookup/` (`lib/lookuppage.py`; since TO-DO §11.10 the reading
  help in Settings, `/settings/reading-help/`, a card per language, with
  `/lookup/` redirecting to it) carries them, in the first of
  the page's three sections (the corpora and the models are the other two,
  below) — a row per language, with a button that does what `getdict.py`
  does, a progress line while it builds, and a remove. What the row offers
  depends on what is there (`drawDicts`): **get it** where there is no
  dictionary, and **rebuild** beside **remove** where there is one. Rebuild
  is the same build over again, and it is there because the dictionary is a
  snapshot of a Wiktionary extract taken on the day it was built — the row
  says which day — so the way to a newer one is to take it again, not to
  remove the old one first and hope. It is also the way to what a newer
  `getdict.py` keeps: the verb entries read columns and rows a dictionary
  built before them has not got (below), and such a file is still read, and
  gives less. The hub has a door to it, both readers have a **reading help**
  link beside their **dictionary** switch, and the cloud over an unglossed
  chunk offers the link when no dictionary is set up, which is the moment
  somebody actually wants it.

  That last part is the point, and it was missing for three commits: the page
  existed and *nothing linked to it*, so the whole feature was reachable only
  by knowing a command that no document mentioned. `tests/smoke.py` now checks
  the door and both links, because a feature nobody can find is a feature
  nobody has.

  The build runs in a thread and reports into `serve.DICT_JOBS`, which the
  page polls: it is a download of up to a gigabyte — German's extract is
  1 077 MB and Spanish's 1 038 MB — and cannot happen inside a request.
  Removing is refused while a build is running — the page hides the button,
  and the server refuses anyway, because deleting a file being written to
  leaves a half-built dictionary that reports itself whole.

- **A dictionary is not a gloss, and the code says so in four places.**
  `lib/lookup.py` reads one SQLite file per language out of `dict/`, built by
  `lib/getdict.py` from Wiktionary's kaikki.org extracts. It ships no data,
  adds no dependency (`sqlite3` is standard library), and a toolbox with no
  dictionary is the toolbox as it was: no lookup is made.

  **The switch is for all three of them, and each is asked separately.** The
  dictionary, the corpus and the model are three downloads and any one can be
  here without the others, so the header button appears when ANY of them is —
  and it says which, in its title. This was got wrong first: the panel was
  gated on the dictionary alone and the corpus was consulted only where one
  was installed, so a reader who had downloaded a corpus for a language with
  no dictionary had a corpus they could not reach, and a video's unglossed
  phrase went bare on exactly the lines the corpus could have spoken for.
  Each block now draws only if it has something to draw, so nothing shows an
  empty heading.

  The switch defaults off and where it is left is remembered, but the two
  doors remember it differently, and anyone reading one after the other
  should know which they are in. The book reader files it under the reading
  page's own address (`lib/tex2html.py`'s `MINE`, `bk_dict:<path>` — the same
  key shape that holds where you are in the book and its audio offsets), so
  it is **per book**: turned on in one, it is still off in the next. The
  player keeps a plain `yt_dict` (`youtube/lib/player.js`), so it is **one
  setting for every video**.

  What it is held to:

  - **Only where nothing is written.** The panel is drawn only for a chunk
    with no vocabulary line. A finished edition looks exactly as it did.
  - **Marked, always.** Its own tinted panel, ruled off, labelled
    *dictionary — not a gloss*, with the source and its licence under it. A
    dictionary lists what a word can mean and cannot say which is meant; that
    is the judgement a written gloss is, and the two must never be mistaken
    for each other on a glance. That distinction is where the panel starts
    and not where it ends: a list nobody can choose from is a poor answer
    even when every line of it is right, and شیر is lion, faucet, tiger and
    milk. Two later things narrow it without anybody guessing — the source's
    own register tags, which put the senses a living text uses first, and a
    parallel corpus, which shows the word inside a sentence somebody has
    already translated (both below). Neither chooses, both are evidence, and
    both are drawn in this same panel under labels of their own.
  - **Read-only.** The dictionary is opened `mode=ro` and a lookup leaves it
    byte for byte. Nothing it shows reaches a book or a video except by
    somebody typing it into the ordinary edit route, with the ordinary
    checkers on it. The question is bounded in the other direction too:
    `serve._lookup` cuts the text it is asked about to its **first 400
    characters** before it looks anything up. A chunk is a chunk, and a whole
    unglossed subparagraph pasted in as one would be a lot of words to look
    up for a panel that shows a handful — so a chunk longer than that is
    answered for its beginning, and the tail contributes nothing. The
    sentence round the chunk, which both readers now send beside it for the
    verb entries' sake (below), is cut to its first 1 000, and is taken only
    as a string.
  - **The books and the videos only.** Neither the studio nor the card store
    imports the module, and `tests/smoke.py` checks that they do not.

  One thing worth recording because it cost time. The **danda** `।` and the
  double danda `॥` are punctuation that lives INSIDE the Devanagari block a
  language's `chars` names, so "is it in the script" cannot decide what to
  strip from a word's edges — `lookup._keeps` asks Unicode's own categories
  instead, which also settles `،` `؛` `。` `、` for free.

  **An affix rule is written in the dictionary's script, not the page's.**
  Where a row declares `fold` (below) its dictionary is keyed in one script
  and its pages are printed in another, so its endings are written in the
  first of the two and `_routes` applies them to the *transliterated*
  spellings and not only to the surface form. Without that half, a word folds
  correctly, is looked for correctly, and stops one strip short of the stem
  that is actually in the dictionary — the folding alone looks as though it
  works, which is why the two halves are recorded together and not in two
  places. It was found by reading a real video against a real dictionary,
  which is the only way it would have been found.

  **What is coming is prepared while nothing is being asked.** A lookup is
  one local SQLite read and a round trip, which is quick and is still a wait
  — so both readers work through the unglossed chunks of the next `AHEAD`
  sentences, a subparagraph in a book and a caption in a video, and by the
  time the reader gets there the panel opens already filled. `AHEAD` is a
  plain constant, ten, written once in each reader: there is no address to
  reach and nothing to spend, so nothing has to decide whether preparing is
  worth it, and it is simply on wherever the dictionary is.

  Three rules, and every one of them is about not being in the way:

  - **One at a time.** Firing ten would queue them and make the one the
    reader is waiting on the last to arrive.
  - **The reader goes first.** The loop does not run while a cloud is open —
    a cloud open is a reader, and the lookup they asked for must not sit
    behind ten they did not. The player stands it down while a chunk is being
    written too. Nothing is lost — the page caches by chunk, so whatever was
    prepared is still there when the queue refills.
  - **Only when idle**, a second and a half after the last scroll, keypress
    or click. Somebody paging through a chapter is not reading it.

  **The model's batch shares that loop, and takes its turn first.** Since the
  panel now draws a machine's reading of the sentence without being asked
  (the translation model, below), a tick of the loop has two things it could
  do, and `prePump` tries the translation before the dictionary: where there
  are sentences ahead that have not been translated it hands them over — all
  of them, in one call — and that is the turn; only when there are none does
  it shift one chunk off the dictionary's queue. It goes first because one
  call covers ten sentences where the queue covers one chunk, and because an
  untranslated sentence is the thing in the panel a reader would actually be
  left waiting on, a lookup being a local SQLite read. The three rules are
  not bent to let it in: the batch **is** the one thing in flight, it does
  not start while a cloud is open, and it waits out the same second and a
  half of quiet. And like the lookups it does nothing at all while the
  reading-help switch is off, which is what keeps a page with the switch off
  costing what it always cost.

  **THE TRANSLITERATION COMES FROM THE PRONUNCIATION, NOT FROM THE SOURCE'S
  OWN ROMANISATION.** Asked about `کتاب را خواندم`, the panel answered
  `kitāb`, `rā`, `xwāndan`, where Persian says `ketāb rā xāndam` — and
  `xwāndan` is not a defensible romanisation at all: the و of `خوا` has been
  silent for centuries. Measured over eight ordinary phrases, six came back
  in the wrong register and none in the right one.

  The cause was not a mistake anywhere in the chain. Wiktionary carries
  several pronunciations per Persian word, tagged — `Classical-Persian`,
  `Dari`, `Kabuli`, `Tajik`, `Iran` — and **its own `translit` field is the
  classical one**. So the panel repeated `kitāb` faithfully, and everything
  downstream was correct about a Persian nobody in Tehran speaks.

  So the pronunciation is now stored (`entry.ipa`, 81% of Persian entries
  carry one) in **the register the language asks for**, and the
  transliteration is a table walk from it:
  `lib/lang/<code>.ipa.json` says which tags to prefer and avoid and how each
  sound is written; `translit.from_ipa` walks it. `[kʰʲe.t̪ʰɒ́ːb̥]` → `ketāb`,
  `[xɒːn̪.d̪æn]` → `xāndan`, `[now.ɹuːz]` → `nowruz`, `[bæʔd̪̥]` → `ba'd`
  while `[ʔɒːb̥]` → `āb`, because a word-initial glottal stop is not written
  and a medial one is.

  **A language with no such file keeps the romanisation the source gives**,
  and that is the right answer for most of them, or nearly: Hindi's `kamal`,
  `ādmī`, `kitāb` are already this edition's scheme (Hindi's *kitāb* really
  is *kitāb*) — nearly, because its file now respells a nasal vowel and two
  letters (below) — and Japanese's is Hepburn. Persian was the first language
  whose source romanisation was in another register, and it is no longer the
  only file. Five rows have one, and between them they use each of the four
  things such a file can say:

  - **which pronunciation**: `prefer` and `avoid`, tags of the source's.
    Persian prefers `Iran` and `Tehrani` and avoids `Classical-Persian`,
    `Dari`, `Kabuli` and `Tajik`. English says only this — `General-American`
    preferred, 27 tags avoided — and adds `avoid_mode: "all"`, which
    `getdict.py` reads when it builds `en.db`: a sound is avoided only when
    every one of its tags is, because fix's only /fɪks/ is tagged Australia,
    Canada, UK and US, and a `weak form` never while another is left (do
    /də/). It has no `map`: the English recipe writes the edition's IPA
    itself.
  - **how a pronunciation is written**: `map` (longest match first), `drop`
    and `strip_leading` for a table walk, which is Persian's; or `respell`,
    the name of a function in `translit.RESPELL`, for a language a table
    cannot write. French is `respell_fr`, because its nasal vowels are a
    vowel and a combining tilde that a table walk strips as a mark of manner
    (ɑ̃ ɛ̃ ɔ̃ came out a è ò). Without it every French hit came back with no
    sound at all; with it the lemma is said (aller *alé*, prendre *prãdr*),
    and so is the form a chunk holds, from that row's own IPA (vint /vɛ̃/ is
    *vẽ*).
  - **how the source's own romanisation is put into the edition's
    letters**: `roman`, which `translit.tidy_roman` applies to whatever the
    source romanised — `drop_marks`, then `map`, then `drop_initial`, a
    letter no word of the edition begins with. Arabic's is four letters and
    one habit: ʔ→ʾ ʕ→ʿ ḵ→ḫ ḡ→ġ, and no hamza at the start of a word
    (ʔastaṭīʕu is *astaṭīʿu*; *saʾala* keeps its inner one). Hindi's is a
    nasal vowel and two letters (हँसा *hãsā* is *haṁsā*; ŕ is *ri*, ṣ is
    *ś*). Persian's drops the accents of stress and writes â as ā and ġ as
    q (`mí-sâzam` is *mi-sāzam*).
  - **which of a form's rows says how it is said**: `roman.prefer`, a
    pattern, and `roman.after_last`, where a cell's second reading starts.
    Wiktionary writes some Persian verbs' Dari table before the Iranian one,
    so the first row of نمی‌دانستم gave *dānistam*, and it writes بود as
    `būd /bud`, the classical reading first; `translit.form_sound` takes the
    first row that matches the Iranian pattern, from after its last `/`.

  Measured again on the same eight phrases: none in the wrong register. What
  the panel prints beside a headword is how the word in the text is said,
  where the source romanised that form — خواندم is *xāndam*, beside خواندن
  (the hit's `of_form`) — and the lemma's line where it did not. The lemma's
  own sound travels with it (`head_sound`, *xāndan*), for whatever writes the
  lemma down, which a vocabulary line does (below); a dictionary gives the
  word's entry and not the text's reading of it, and is labelled as one.

  **THE READING COMES FROM THE DICTIONARY TOO.** Rōmaji is no answer at all
  in a furigana field, which the vocalised pass prints *over* the text.
  Wiktionary keeps a word's kana in the head template (`日本語` →
  `にほんご`), so it is stored (`entry.reading`, 55% of Japanese entries) and
  shown beside the rōmaji.

  And what a reading is written in is a fact about a language, so the registry
  holds it: `reading_chars` for Japanese is the kana blocks, `L.is_reading`
  asks it, and a `kana` field that is not kana is refused rather than printed.
  `chars` cannot answer this — for Japanese it is kana *and* kanji, so it
  cannot tell a reading from the text it is a reading of.

  **Every installed dictionary was rebuilt and compared answer by answer**:
  Japanese 0 of 36 changed, Hindi 0 of 24 (before Hindi had the `roman`
  file above). A language with no `.ipa.json`
  keeps the romanisation its source gives, so the rebuild moves nothing for
  them and only adds what was missing.

  **And where a romanisation can be computed, nothing has to hold it.** A row
  declaring `fold: deva-iast` has said two things about itself: that its
  dictionary is keyed in a different script from the one its pages are
  printed in, and that its spelling is phonemic, so the bridge between the
  two is a table walk and not a fact to be looked up per word.
  `lookup._folded_variants` walks `lib/translit.py`'s table over the page's
  own words — `बुद्धं सरणं गच्छामि` → `buddhaṃ saraṇaṃ gacchāmi`, exactly —
  and asks the dictionary under that spelling.

  **No row declares it today, and the mechanism stays.** Pali was its only
  user, and Pali has left the registry. Taking `fold` and
  `translit.deva_to_iast` out with it was considered and refused, and the
  reason is what the field actually says. *The dictionary is keyed in another
  script than the page* is a fact about a **source**, not about a language,
  and it is the ordinary condition of a great deal of lexicography: a reader
  wants the script the book is printed in and a lexicographer romanised the
  headwords. Any language could arrive in that position tomorrow, and what it
  would have to write is one line of JSON. `_folded_variants` is written
  against the field rather than against the table — the table is one branch of
  one `if`, so a second romanisation is a table and a line — and
  `deva_to_iast` is a deterministic function of Unicode that has nothing to
  rot: no network, no data file, no version. What removing it would buy is a
  table and thirty lines. What it would cost is that the next language in that
  position meets a lookup which finds nothing and says nothing, the failure
  this file exists to keep out of the toolbox. So it is recorded here as a
  **capability with no current user**, which is not the same thing as dead
  code: dead code is what nothing can reach, and this is reached by any row
  that declares it.

  **A language written without spaces needs the dictionary to cut its
  words.** For a row whose `word_sep` is the empty string — Japanese, and now
  Chinese — `split_words` hands back the whole chunk, which is right for
  every other caller in the toolbox — a chunk is the hoverable
  unit, and an Anki card is made from one — and useless here: `昨日本を読んだ`
  is not a headword and never will be. `lookup._segment` cuts by longest
  match against the dictionary's own form table, so the word list *is* the
  dictionary and nothing extra is installed. Two things make it work rather
  than merely run:

  - **the cut asks the language's rules too** (`_is_word`), because a word
    the reader meets is usually inflected: `住んで` is in no dictionary and is
    unmistakably a word, and without the rules the cut left `住` alone and
    matched `んで`, absurdly, against `ぬ`;
  - **one character of stem is enough** — the guard used to demand two, which
    suited Persian and left every Japanese `-mu` verb's te-form uncut,
    since a Japanese stem is very often the single kanji. Generating a
    nonsense stem costs nothing: it still has to be in the dictionary before
    anybody is told about it.

  It is greedy and therefore sometimes wrong — the standard failure is a
  compound eaten where two words were meant, and `おじいさん`, which
  Wiktionary does not carry as a reading, comes out as `おじ` + `いさん`
  (*inheritance*). Wrong and visible, which is the trade this whole feature
  is built on.

  **What getdict keeps had to change for Japanese too.** The kana reading is
  not in the `forms` list at all: it is in `head_templates[].args["1"]`,
  written with Wiktionary's own `%` markers for the okurigana boundaries
  (`お爺さん` reads `お%じい%さん`). Without it a kana-written sentence — which
  is what a children's story is, and what a beginner reads — matched nothing.
  The rule stays general: an arg is taken only when every character of it is
  in the language's own script and it is not the word itself, so a Latin
  romanisation is excluded and a Latin-script language contributes nothing.
  And a form of an unspaced language cannot contain a space, which threw out
  `住む intransitive godan` — the headword *line*, which no lookup could ever
  match.

  **The cascade peels more than one affix, because Persian stacks them.**
  It used to take exactly one off, and `نمی‌بینمش` is
  *ne-* + *mi-* + بین + *-am* + *-aš*: the prefix came off, or the enclitic
  did, never both, and the reader was told nothing was found. `_routes` is
  now breadth-first by number of strips, out to `MAX_PEEL`, and
  **shallowest first is what keeps it safe** — a word the dictionary has is
  found as itself and never explained away as somebody else's stem. Nothing
  is visited twice, so a rule that takes a form back where it came from
  cannot loop, and the total is capped.

  **`MAX_PEEL` is 2, and three was tried first.** Run over all 16,879 Persian
  headwords, depth 3 differs from depth 2 on thirty of them and every single
  one is an invention: `زرتشت` (Zoroaster) read as `زر` (gold), `لیتیم`
  (lithium) as `لی`, `موریتانی` (Mauritania) as `مور`. Not one correct answer
  is gained. A third strip is where a word stops being a word and becomes
  whatever letters are left.

  **One prefix per route**, for the same reason. Every language here has a
  single prefix slot — Persian's `نمی` is already *ne-* + *mi-* as one rule —
  so a second one is always the search eating the word. Unguarded it read
  `بنده` (a servant) as `ده` (a village), `بندر` (a port) as `در` (a door)
  and `بنزین` as `زین` (a saddle): twenty-one such answers dictionary-wide,
  and nothing correct lost by refusing them.

  The cost is real but small. Depth 2 roughly **doubles** the candidates —
  14 against 7 for `نمی‌بینمش` — which an earlier draft of this file got
  wrong by claiming it was free. In absolute terms `_routes` on that word is
  0.028 ms, and a Japanese sentence, which calls it for every candidate
  substring of every position during segmentation, takes 0.8 ms.

  **What Persian's inventory should be was decided by measuring, not by
  listing what the grammar has.** Two things are missing from Wiktionary, and
  the 35 rules that measuring gave are those two things and nothing else
  (seven more came later, and are the third thing below).

  The first is the **object enclitic**: `-mān -tān -šān`, the colloquial
  `-mun -tun -šun`, the bare `-am -at -aš`, longest first. Against the 590
  distinct words of the Persian fixture story these take the lookup from
  **75.9% to 89.8%** found, and **not one word that was already right changed
  its answer** — which is shallowest-first doing its job. Of the newly found,
  a handful are wrong (`بگوشم`, which is به + گوش + م, comes back through بگو
  as *to say* rather than *ear*), and each carries the route that produced
  it, which is what the panel is for.

  The second is the **past tense**, and finding it corrected a belief this
  file used to state outright. It said Wiktionary's conjugation tables were
  good, so verb endings were deliberately left out. They are not good: 456 of
  Persian's 1402 verbs arrive with no conjugation table at all, and of the
  2,646 past forms the simple infinitives imply, **1,116 are absent** — whole
  paradigms, every person and number, for a third of the verbs.

  No amount of taking letters *off* a word finds those, because the past stem
  is a real word's infinitive minus its ن. What finds them is putting the ن
  **back**: `پوسیدم` is `پوسید` + *-am*, and `پوسید` is `پوسیدن` minus ن, so
  strip the ending, add the ن, ask again. That is what `add` in a rule is
  for. Over the 1,116 forms Wiktionary omits this moves **1% found to 100%
  found, with nothing wrong**; over the running-text corpus it loses nothing,
  changes nothing, and gains one word — the gap it closes is precisely the
  one the corpus cannot see, which is why it was worth measuring separately.

  Two orderings inside those seven rules were decided by measurement, not
  taste. The bare stem (`ت`→`تن`, `د`→`دن`) must come **before** `-ند`,
  because `سوزاند` is `سوزاندن` with its ن gone, not `سوزان` with *-and*
  added; reversed, a verb answers *burning*. And the endings are rebuilt with
  the ن rather than simply shaved, because the bare `-ید -ند -یم` fire on the
  negative past and answer `نزدیم` (*we did not hit*) with `نزد`, the
  preposition *near*. Rebuilding, `نزدیم` reaches `زدن` by the ordinary road:
  ending off, then the negative *na-* off.

  One thing that cost the right answer by a hair: **a zero-width joiner left
  at an edge**. Persian writes `نمی` + ZWNJ + `بینم`, so taking the prefix off
  leaves the joiner leading the stem and nothing is keyed under that;
  `نمی‌بینمش` reached دیدن through `می‌بینم`, having silently dropped the
  negation, instead of through `بینم` with the negation named. `_peel` trims
  it.

  **The third thing is a word the tables spell as two.** `برمی‌گردم` is
  *bar-* + *mi-* + گرد + *-am* written as one word, and Wiktionary's tables
  write it `بر میگردم`, the preverb apart. Taking بر off alone leaves a verb that is
  not this one (گشتن, to turn, where برگشتن is to return), so the preverb
  and mi- come off together and are put back in front the way the table
  spells them (`front`): one rule for each preverb docs/lang/fa.md lists,
  بر در فرا فرو باز وا ور, and `برمی‌گردم` now reaches برگشتن and nothing
  else. With them came the other side of the same coin, a stem that is not
  a word: `bare_stem` names Persian's present-stem notes, and a hit reached
  only through one goes after every other hit when the word is also some
  entry's own headword — در is the preposition and the door before it is
  دریدن's present stem, بر is *on* before it is بردن's. The past stem is not
  in the list: کرد and بود are the third person past as well, which is what
  a text means by them.

  **The fourth is the other way round: one word the text spells as two.**
  The joiner is what the spelling wants — `نمی‌بیند` — and a plain space is
  what a typewriter, an old printing and a good part of the Web give
  instead: 13 of the fixture book's chunks (`کَسی نِمی بینَد`) and 1,032 of
  Tatoeba's 8,454 Persian sentences have a نمی or می standing alone. Split
  at the space, می was *wine* (and a preposition, a conjunction and a
  name), نمی was نم *moisture* with an -i taken off, and the verb was
  looked for without its prefix: بیند reached دیدن with the negation gone,
  and کنم is کردن *and* کندن where می‌کنم is only کردن. So the file's
  `join_next` names the words a text writes apart from the word they
  belong to (`words`, compared without marks: می, نمی) and what the two
  must make together (`pos`: a verb), and `lookup._joined` looks such a
  word up JOINED to the next — with the ZWNJ, as one word — wherever
  nothing but the space stands between them (`می،` is the wine and a
  comma). The reader is shown the two as written, as one word with its
  route: `نِمی بینَد`, found *as one word (نِمی‌بینَد), the negative
  continuous nemi- taken off*. Where the two together find no verb, each is
  looked up alone, as before, and the second one's `tried` lists the join's
  spellings too, so a *not found* under سوزانند says نمی‌سوزانند was asked
  as well. `pos` is what keeps `می ناب`, pure wine, wine: می is also
  a prefix rule, so any word at all is found again behind it, and ناب came
  back "found" by taking a verb prefix off an adjective (as the fixture's
  `با هَم می سوزانَد` came back سوزان, *burning*); the same filter drops what
  only shares the spelling, so `می زد` is زدن and not also میزد, a banquet.
  And the joined word's routes are walked until one finds what `pos`
  allows: `نمی دانم` is first found as written, Wiktionary's phrase page
  *I don't know*, which is no verb, and the walk goes on to take nemi- off
  and reach دانستن. Over every standalone می and نمی in the corpus, 1,129 of
  1,140 now reach their verb. The eleven that do not are `می بارد` four
  times — باریدن is there, but with no table, and a present stem cannot be
  rebuilt from the infinitive as a past one is — a verb the dictionary has
  not got (`می بالند`), the colloquial `نمی یاد` twice and four slips of the
  typist's.

  **What a chunk is, and the two ways a draft is cut.** A chunk is the unit
  of the mapping a reader makes: the foreign span, then its gloss. That fixes
  what a good one is from both sides at once — small enough to hold while the
  eye moves, whole enough that the gloss is a natural translation of exactly
  that span. So: **cut at the edges of phrases, never inside one**, two to
  five words, and a content word with its trailing particles where the
  language has no spaces.

  The rules, in the order they are worth: an **adposition never stands alone**
  (`به خانه`, `家に`); a **noun keeps its modifiers**; the **verb group is the
  unit, not the verb** (auxiliaries, negation, a separable prefix, the light
  verb of a compound); a **word keeps its particles and clitics**; a **fixed
  expression is one chunk even where that breaks the syntax**, because the
  meaning is not in the pieces. A **clause boundary is always a cut**, and the
  conjunction opens the chunk it introduces. An **adverb joins the verb it
  modifies when it stands next to it**; a sentence adverb stands alone. And a
  chunk is never one word per word — that is a dictionary with the text
  interleaved — nor a whole sentence, which is where the reader stops mapping
  and starts reading the translation.

  `lib/chunker.py` offers that as a CHOICE and never imposes it, because the
  two things it cannot see are exactly the two that matter most: an idiom,
  and which reading of an ambiguous word is meant. **`sentence`** is one chunk
  per sentence and remains the default — it is what every book and video here
  already holds, and it leaves the cutting where it has always been, with the
  author. **`phrase`** cuts by the rules above, reading the parts of speech
  out of the language's own installed dictionary (`lookup.pos_of`) through the
  same affix cascade the reading panel uses. `lib/lang/<code>.chunk.json` says
  which side of the noun that language puts its modifiers on and which side of
  its object the adposition sits on; Persian's also carries the ezafe, which
  binds forward and is marked in these texts.

  **Punctuation is the first cut, in every language.** A comma, a semicolon,
  a colon, a 、 or a ， ends a clause, and a clause boundary is a chunk
  boundary: it is the one cue every writer prints. A spaced language writes
  the mark against the word before it (`home,`), which the dictionary reads
  as a plain noun, so the chunker looks for the mark at the end of the token;
  a cut that asked only the parts of speech went `When I got | home, my
  mother`. A group too small to stand goes to the neighbour it shares no mark
  with.

  **Then the language's own function words.** `lib/lang/<code>.chunk.json`
  lists a spaced language's articles, prepositions, conjunctions, pronouns
  and auxiliaries (`function_words`): a closed list of a few hundred words
  that a dictionary is the wrong authority on — Wiktionary files `man` under
  an interjection and `not` under a conjunction, and whichever reading it
  listed first used to decide the cut (`The old | man wound the clock`). The
  dictionary is asked about everything else, each reading weighted by how
  many senses it has (`lookup.pos_weights`), and a word under two headings is
  read in its place: `that man`, `that he`, `that is`; `la casa`, `la vedo`.
  The same file says what else holds a phrase together in that language: the
  prepositions that tie a noun to the one before it (`ties`: `a pound of
  apples`, `un pezzo di legno`), the particles of a phrasal verb
  (`particles`), the clitics written into a word (`elisions`: `l'uomo`;
  `enclitics`: `I'd`), a verb that comes last (`verb_final`), the particle
  that closes its phrase (`closing`: را), and the light verbs of a compound
  (`light_verbs`: فکر کردن, teşekkür etmek). With the list and no dictionary
  a language is cut by the list and its punctuation, and two words the list
  does not know are never parted; with neither, the punctuation is all
  `phrase` cuts at, and a sentence with none stays whole. Measured against
  the hand-made chunks of the toolbox's fixtures, the boundaries agree at F1
  0.92 in English (0.67 before the list), 0.90 in Italian (0.69), 0.75 in
  Persian (0.62) and 0.83 in Turkish (0.81).

  **An unspaced language is never cut from the dictionary's word list.**
  Japanese is read in bunsetsu — a content word with the particles after it.
  Where `lib/words.py` has SudachiPy, a sentence is cut between the words the
  word strip shows (`words.parsed`), by the part of speech SudachiPy names for
  each: a particle, an auxiliary and a mark stay with what they follow; a
  modifier binds forward (`この`, `大きな`, an attributive form, `の`); a noun
  keeps its `する`; は, も and a subject が hold firm, and every other particle
  leans toward the verb after it. The pieces then grow while two neighbours
  fit in `grow_to` characters — eight, the 2–8 of `docs/lang/ja.md` — so an
  object keeps its verb (`本を読んで | 映画を見ました`, not four pieces), and a
  chunk cannot end inside a word. Without SudachiPy the characters are read:
  a mark from `marks` cuts whatever follows it, a particle from `closes` cuts
  when a content word begins next, and the pieces grow the same way. Asking
  the dictionary's longest-match instead inherited its mistakes: it reads
  `へし` as a verb and `ています` as a noun, and one bad segmentation became
  three bad chunks. `の` is deliberately not in the list — it binds a modifier
  to its noun the way an ezafe does, and listing it cut `この` off the noun it
  determines. Before the marks were read, a particle in front of a comma was
  refused because a comma is no content word: `寒い朝に、窓を開ける。` came out
  `寒い朝に、窓を | 開ける。`, and a run long enough to reach `max_chars` was cut
  inside a word whose kana spells a particle (`…窓の外になが | れ落ちる。`).

  Chinese is the second row with no separator and walks through the same
  door — `chunker.phrase` asks `word_sep` and the `closes` list, never the
  code. What it closes on is not what Japanese closes on: Japanese has a
  particle after nearly every phrase and Chinese has not, so
  `lib/lang/zh.chunk.json` closes on Chinese's own punctuation
  (。，、；：？！ and the closing brackets) with 吗呢吧 for captions nobody
  punctuates. The aspect markers 了/着/过 were tried and are recorded in that
  file as rejected: cutting on them parts a verb from its object
  (我昨天去了 | 北京，) and breaks words that merely begin with one
  (我了 | 解他的想法。). Where pkuseg's part-of-speech model is installed
  (`words.tagger_available`; `./install.sh` and `python3 lib/words.py --fetch
  zh` fetch it, and no request of the server ever does), the punctuation is
  only the first cut: the sentence is then cut between its words by their
  tags (`chunker._zh_seams`) — a coverb binds its object and 的 its head, a
  measure word its number and its noun, an adverb its verb; a verb takes its
  object; and where a verb or a coverb has already come in the clause, the
  noun before the next verb closes a phrase — and the pieces grow to six
  characters. A clause nobody punctuated, an auto-caption's whole case, is
  cut too (`我昨天 | 在北京的一家小书店里 | 买了 | 一本很有意思的书。`), and on
  the fixtures the boundaries agree with the hand's at F1 0.98, against 0.84
  by punctuation alone. Whatever is asked
  for, `chunker.chunk` checks its own answer against the text it was given:
  the reproduction rule the toolbox rests on, asked by the thing that writes
  the chunks rather than by a checker two steps later.

  What a language may say for itself is `lib/lang/<code>.lookup.json`, and it
  is optional: without one a word is looked for as written, then folded
  (case — Turkish's with its own İ→i and I→ı, which a locale-blind lower
  case gets wrong — the language's `strip` marks, the zero-width joiners),
  then in whatever inflected forms the source itself listed — which for
  nine of the eleven rows is nearly all of the inflection, because
  Wiktionary carries the morphology. The file began with the two that need
  more, Persian and Japanese, and what they write in it is `affixes`:
  endings the source does not list, each carrying the note the reader is
  shown, so a hit found by taking `-hā` off says so rather than pretending
  the page read the stem.

  Six rows have one now, and what the four newer ones add is, but for one
  kind, not morphology the source lacks but what a text writes onto a word
  and the source files without it: Arabic's clitics, و ف ب ل ك س in front and the pronoun
  suffixes behind, vowelled and bare (فَرَأَى, وَقَالَ, أُرِيدُهُ are reached);
  French's and Italian's elisions, each with both apostrophes (`l'uomo` is
  uomo, the hit's word staying `l'uomo`); the pronouns Italian writes after
  an infinitive, a gerund or an imperative (alzandosi, portamelo), and its
  agreeing participles — the one piece of morphology among them, since
  only the masculine singular points at its verb and incontrati is a page
  nowhere; and Chinese, which has no affix at all and says three other
  things (below). A rule is a `suffix` or a `prefix` with its `note`, and may
  carry `add` (put back at the end: a past stem's ن), `front` (put back in
  front: Persian's preverbs, above), `after` (what the rest must end in for
  the rule to fire: an Italian enclitic comes off an infinitive's -r or a
  gerund's -ndo, never off the name Carla) and `prefer` (the notes that put
  an entry first when this rule is the one that answered: after -mashita,
  the verb reached through its `stem` row, so 来ました is 来る first).

  The file's other keys say what the source's rows mean and cannot say
  themselves: `own`, notes that make a row the word itself as an empty note
  does (Chinese `Simplified-Chinese`: 帮忙 IS 幫忙); `spelled`, notes saying
  the text spells the entry another way, whereupon the hit carries the
  text's spelling and a Simplified book is not handed a Traditional `\dw`;
  `regional`, the sense tags that name another lect — Cantonese, Hokkien,
  Min and sixteen more — which rank a sense with the dialectal ones unless
  it is tagged Mandarin too (生日 "to have one's birthday" is Cantonese);
  `bare_stem` (Persian, above); and `also_peel`, the pages a whole word may
  match that are only spellings of two words — a contraction, a phrase — so
  that the prefix rules are tried as well and n'avait reaches avoir as well
  as ne. One key is about the text and not the source: `join_next`, the
  words a text writes apart from the word they belong to (Persian's verb
  prefix, above). `lookup.rules()`'s docstring is the list. `fold` is the one key no
  row sets today (above).

- **The senses are ordered before they are cut, and the order is the
  source's own.** Wiktionary records a REGISTER TAG per sense — `obsolete`,
  `archaic`, `dialectal`, `figurative`, `slang` — and `lib/getdict.py` used to
  throw them away. It now stores them in the entry's `sense_tags`, one line
  per line of `sense`, and `lookup.rank_senses(senses, tags, code)` returns
  `(sense, tags, tier)` plainest first: **tier 0** plain, **tier 1** marked
  (figurative, dialectal, regional, slang, vulgar, humorous, broadly,
  specifically, euphemistic, childish, ironic — and another lect's sense,
  where the language's `regional` rule names the lects), **tier 2** stale
  (obsolete, archaic, historical, dated, rare, uncommon, nonstandard,
  proscribed, misspelling, neologism, and the three spellings Wiktionary
  marks a respelling with); the two sets are `lookup._MARKED` and
  `lookup._STALE`. There is no judgement in it and no model: the tags are
  facts the source already recorded, and **the sort is stable**, so an
  entry whose senses carry no tags comes back exactly as the source ordered
  it — which, for an unmarked sense, is the best signal there is. A tag with
  a colon (`aux:sein`, `obj:dat`) says how a sense is used and not its
  register, and is not read here, nor is `with-dative`: split into words,
  `folgen`'s `obj:dat<something; e.g. a book; film plot; etc.>` would have
  ranked a plain sense by what its object is like.

  **What is deliberately not demoted decides more than what is.** `literary`
  and `poetic` are left alone, because this toolbox is pointed at literature:
  یار is tagged `literary` for "friend, lover", which is the sense a page of
  Hafez wants, and demoting it promotes the untagged "a player in a team"
  over it. `colloquial` is left alone — a novel's dialogue is colloquial. And
  every REGION tag is left alone: `Iran`, `Dari` and the rest say where a
  word is said, not that it is the wrong reading, and Persian carries `Iran`
  on 620 senses, which is the register these editions are written in. A
  demotion list that swallowed those would have made the panel read worse
  than the unranked list it replaced.

  **The ranking happens before the list is cut to `MAX_SENSES`**, which is
  three. It used to cut first, and that is the bug worth recording, because
  the panel could not show it: a plain sense sitting fifth behind four
  obsolete ones was not merely shown late, it could not be reached at all.
  Measured on the rebuilt Persian dictionary, 7 229 of 16 942 entries carry
  tags and the ranking changes the top three for 214 of the 4 870 tagged
  entries with more than one sense — "cuckold, pimp" (vulgar) giving way to
  "mover", "condom" (slang) to "hood, bonnet (of a car)". **A dictionary
  built before the column existed keeps working**: `lookup._has_col` asks
  whether it is there and passes empty tags, and empty tags return the senses
  untouched — which the smoke test checks by passing none.

  **A second signal orders the HITS and not the senses, and it is a tiebreak
  and never an override.** Where one written word reaches two lemmas,
  `lookup._by_use` asks the corpus below how many translated sentences hold
  each headword. That count may not decide alone: `_hits_for` already puts
  the entry a word IS above the entries it merely inflects to — the tiers of
  the next note — and that order outranks any count, because بستن (to
  close) is commoner in every corpus than بنده (a servant) and sorting on
  the count alone told the reader that بنده was two prefixes off *to
  close*. So the count only orders hits the dictionary had no reason to
  separate, and it is stable inside that; the smoke test pins بنده, بندر,
  بنزین and بنیاد coming back as themselves. It fires only where a corpus is
  installed, and only for a word with competing lemmas — 13% of words,
  measured on Persian.

- **A hit says which entry it is, how its lemma is said and how the text
  spells it, because a verb entry is built from it.** `lookup.look_up`
  answers each word with at most `MAX_HITS` (four) hits. A hit carries its
  `headword`, `pos`, up to `MAX_SENSES` ranked senses with their `marks` and
  how many were `buried`, the route's `note`, `ipa`, `reading`, and three
  sounds that are not to be confused: `of_form`, the word the text holds as
  the source romanised THAT form (می‌سازم *mi-sāzam*), or as its own row's
  IPA says it where no row is romanised (French vint *vẽ*); `said`, the
  lemma's pronunciation walked through the language's ipa.json; and
  `translit`, which is `of_form`, else `said`, else the source's
  romanisation of the headword, tidied — the sound of the word in front of
  the reader wherever anything gives it. Three fields came with the verb
  entries:

  - `entry`, the entry's id, which is what tells homographs apart — Persian
    has two رفتن, *raftan* "to go" and *roftan* "to sweep" — and what the
    verb builder reads the conjugation table by;
  - `head_sound`, the LEMMA's sound (`said`, else the source's romanisation
    of the headword, tidied) and never the reached form's. Whatever writes
    the lemma down takes it: the sidebar wrote `\dw{ساختن}{mi-sāzam}`, the
    infinitive with the inflected form's sound, and now writes *sāxtan*. A
    headword of several words is said word by word (فکر کردن *fekr kardan*);
  - `spelled`, the text's spelling where the row the word came through says
    it spells the entry another way (`spelled`, above), `''` otherwise:
    帮忙 reaches the entry 幫忙 with `spelled: 帮忙`, and what a vocabulary
    line writes is `spelled` or else the headword.

  And `vb`, where the language's recipe recognised the hit (two notes
  down).

  **The hits are ranked by what reached them**, in tiers; then an entry
  spelt as the word before one that is the word in another spelling; then by
  entry id. The corpus count only reorders inside a tier.

  - `T_PREFERRED` (−1): reached through a row the answering affix rule
    `prefer`s — 来ました is 来る first, before the prefix 来.
  - `T_IS` (0): the word is this headword, joiners and marks aside but not
    the capital.
  - `T_FORM` (1): the word is one of its forms.
  - `T_CASE` (2): the word is its headword only once the capital is gone.
    getdict writes a capitalised headword's lower-case copy beside it with
    the same empty note, so `given` WAS the name Given as surely as it was
    the adjective, and with four places English lost give, come, leave and
    run; German essen and the noun Essen, Italian marco and the name Marco
    are the same case.
  - `T_PART` (3): a headword of several words reached through one of them.
    Wiktionary's colloquial table for بلد بودن has the bare هستند among its
    cells, and six other compounds of بودن have it too, so هستند came back
    as four compounds and never as بودن; it is بودن first now.
  - `T_STEM` (4): reached only through a `bare_stem` row where the word is
    also some entry's own headword (در, above).
  - A letter of the alphabet goes ten tiers further back, in a language
    written with spaces.

  Four smaller rules sit round the tiers. **An entry reached only through
  an auxiliary is not a hit**: getdict keeps a conjugation table's
  multiword cells and the auxiliary's own cell with them, so `haben` is a
  form of 9 243 German verbs and `Wir haben Zeit` listed raven and listen;
  an entry reached ONLY through an `auxiliary` or a `multiword-construction`
  row is dropped, and one the word is, or reaches another way, stays (haben
  is haben). **One place is kept for the verb**: in a spaced language, when
  the four hits are all entries the word is and none of them a verb, the
  verb it is a plain inflection of takes the fourth place — `left` is two
  adjectives, an adverb and a noun, and leave was fifth; Persian کند is an
  adjective and three nouns, and کردن was fifth 37 times in 1 500 Tatoeba
  sentences — at the cost of an unlikely verb now and then (Italian `ora`
  gives the noun, the adverb, the conjunction, and orare). **A sentence may
  open with a name that is not one**: a capitalised word that may start a
  sentence and finds only names is looked up in lower case too, and that
  answer goes first with the name kept after it, even as a fifth hit —
  `Seppe la verità` gives sapere, then Seppe. **And the chunk is
  normalised to NFC before it is split**, so a precomposed Devanagari nukta
  letter matches the dictionary's spelling of it.

- **A verb entry reads more of the source than the panel did, so getdict
  keeps more, and an installed dictionary has to be rebuilt to give it.**
  Three additions to the schema (`lookup.SCHEMA`), each asked for by
  `lookup._has_col` / `_has_index` before it is read, so a file built
  before them still opens:

  - `entry.head`, a JSON object of what the head line says and nothing else
    does (`getdict._head`): a Japanese verb's class and transitivity
    (`{"class": "godan", "tr": "tr."}`), a Chinese verb's type (`vo`
    separable, `vc` taking a potential), a Hindi verb's transitivity,
    Persian's literary Iranian stems with their sounds (`{"prs": "گو",
    "prs_tr": "gu", "ps": "گفت", "ps_tr": "goft", "inf_tr": "goftán"}`, from
    the one table whose header names that register — the form rows of five
    tables share their tags, and دانستن came out with a Dari infinitive —
    and only where that table's infinitive is this headword), the Arabic
    perfects whose head says there is no verbal noun (`vn_none`), and
    an Italian verb's auxiliaries (`aux`, written and not yet read by the
    Italian recipe). In the dictionaries built here 825 Persian entries
    carry one, 12 251 Japanese, 3 378 Chinese and 1 026 Hindi;
  - `form.ipa`, how THIS form is said where the source says it: a French
    conjugation row carries it (prends /pʁɑ̃/), and so does a page that is
    only "past of go" (went /wɛnt/). The lemma's pronunciation can give
    neither;
  - `form_entry_ix`, an index on `form(entry_id)`. One entry's whole table
    is what a verb entry reads, and without the index that is a scan of the
    form table per hit, 0.061 s on German's 2 429 661 rows.

  Each sense's tags gain facts that are not registers and never move a
  sense: `aux:sein` (the German gloss's `[auxiliary sein]`), `obj:<what it
  governs>` (its commas made `;`), `with-<case>` (Turkish qualifiers, read
  conservatively). Chinese gains standard Mandarin pinyin, from the
  source's `zh_pron` rows — 156 024 of 189 192 entries have a romanisation
  now, against 160 before, and those 160 were grammar labels — so a Chinese
  dictionary built before gives no `\vb` at all. And the form rows are cut
  more carefully (`_form_rows`): one row per form and note; a head-line row
  outranks a table row of the same spelling; Persian's verb tables lose
  their pronoun column (من, تو and ما had reached آراستن); Japanese gets
  stem and past rows for every alternative kanji spelling (飲み and 飲んだ
  under のむ); Hindi gets the modern -ई/-ए spelling beside each -यी/-ये
  cell (दिखायी, दिखाई); a pointer page links only to the homograph with its
  own part of speech; a lower-cased copy that is only the headword again is
  not written (German loses 69 874); and a Turkish verb page that is only a
  pointer but has a `tr-conj` table of its own becomes an entry. English
  chooses among its pronunciations by `avoid_mode` (above).

  None of it reaches a file that is not rebuilt — **Rebuild** on the
  reading help, or `python3 lib/getdict.py <code>` (`--out PATH` writes it
  there and leaves `dict/` alone; a build is written to a `.part` and
  renamed, so a failed one leaves the old file where it was). A dictionary
  built before is still read and gives less: Chinese no `\vb` (no pinyin),
  French and English no sound for a form (no `form.ipa`), German no
  auxiliary or government per sense, Persian the head line's stems where
  the literary table would have spoken, and every one of them slower
  without the index. Built on this machine (2026-09-10): German 342 MB,
  Spanish 272 MB, Italian 155 MB, Hindi 88 MB, Japanese 62 MB, Chinese
  57 MB, Persian 21 MB. Built again on 2026-09-24: Turkish 306 MB (from a
  431 MB extract), Japanese 89 MB, Persian 21 MB — so read the older
  figures as floors; `lib/getdict.py`'s MEASURED table is what the reading
  help says.

- **A verb hit carries its `\vb`, and what goes into it is each language's
  recipe.** A dictionary hit for a verb used to reach the gloss editor as a
  `\dw` — `\dw{ساختن}{mi-sāzam} to make` — which is what the conventions
  tell a vocabulary line never to do with a verb, most Chinese verbs and the
  English modals aside (§3), and which paired the infinitive with the
  inflected form's sound besides. The forms a `\vb` prints are exactly what
  a learner cannot guess and a dictionary can say: the conjugation table is
  already in `dict/<code>.db`, a form row per cell with the cell's name in
  its note. `lib/verbs/` builds the entry from those rows. The core,
  `lib/verbs/__init__.py` (standard library only: the server imports it),
  does what every language needs and none should write twice — finding the
  rows, the meaning, taking out what LaTeX would read as an instruction,
  writing the four shapes from one description. Which forms, and what else,
  is the language's business and never the core's: `lib/verbs/<code>.py`,
  one function, `recipe(ctx)`, which returns a `verbs.Parts`, or None for a
  hit that is not a verb it can describe. Every row of the registry has one
  today.

  **No recipe is an answer and not a fault.** A language without
  `lib/verbs/<code>.py` offers no `\vb`, the way a language with no
  dictionary offers no lookup, and every verb it finds goes into the editor
  as the `\dw` it always was. `lib/newlang.py` writes no recipe (§10), so a
  new language starts there. The recipe is imported the first time a hit of
  that language asks (`verbs.recipe_for`), so a server reading Persian never
  loads German's; a file that fails to import is said once on stderr and
  costs that language its `\vb` and nothing else; a recipe that raises, or
  returns something that is not a `Parts`, costs that hit its `\vb` and not
  the lookup. `serve._lookup` calls `verbs.attach` after `lookup.look_up`
  for both doors, with the chunk, the gloss code and the sentence, and
  guards the call a second time, for a bug in the core itself.

  What a recipe is given (`verbs.Ctx`, read only when asked: a recipe that
  looks at the part of speech and answers None has cost one indexed row):

  - `code`, `L` (the registry record), `conn` (the dictionary, read-only,
    rows by name), `hit` (as lookup built it), `word` (as the chunk has
    it), `text` (the chunk), `sentence` (the sentence round it, where the
    reader sent one — both readers do), `gloss`;
  - `entry`, the entry's row — id, headword, translit, ipa, reading, pos,
    sense, sense_tags, head, `''` for a column the dictionary predates — and
    from it `head` (entry.head as a dict), `senses`, `sense_tags` (a set per
    sense line), `meaning` (below) and `head_sound` (the lemma's sound);
  - `rows`, its form rows as `Form(form, note, tags, roman, rowid, ipa)` in
    the order getdict wrote them, `tags` being the note split on spaces and
    commas; `own_rows`, the unbroken run of rowids getdict wrote with the
    entry, before any pointer page's (a pointer row with one tag has no
    comma to give it away, and 3 531 Japanese verbs carry one); `rows_of(id)`,
    another entry's; `other(id)`, a `Ctx` on another entry for the same word,
    chunk and sentence — the separable verb a German finite form belongs to,
    the verb an Italian clitic compound names;
  - `pick(…)` / `picks(require, forbid, exact, where, own, script)`, the
    form rows with the tags required, none of the tags forbidden, or exactly
    the tags given; `data()`, the language's hand table (below);
    `in_script(s)`, `bare(s)`.

  What it returns, a `Parts`: `parts`, three (form, sound) pairs — a blank
  form is a pair not printed, a blank first form is no `\vb`; `meaning`,
  None for the core's; `extras`, the items of the parenthesis, a word of the
  language in them written `verbs.tl(form, sound)` so that only the core
  ever writes `\pw` (the sanitiser, which takes every backslash and brace
  out of every slot, would take a recipe's own apart); `extras_video`,
  items only a video's line carries; `missing`, what the language needs and
  the data did not give, in words a person reads; `notes`, hints that are
  not missing (Arabic's other masdars); `reading`, the kana a Japanese
  headword is read with.

  **Nothing guesses.** A recipe fills a slot from a row the source wrote or
  leaves it empty and names it in `missing`; the hit's `vb.complete` is then
  false and the editor says what is left. A `\vb` that looks finished and is
  wrong costs more than one that says it is not finished.

  From one `Parts` the core writes the four shapes a reader might want, so
  that they cannot disagree: `tex` for a book's vocabulary line, `plain` for
  the lemma's entry in a video's, `here` for the same entry hung on the word
  the chunk has, and `line`, what the reading panel and the sidebar show
  under the hit — the labelled second and third forms and the book's extras,
  and no meaning. Beside them `vb` carries `lemma`, `parts`, `labels`,
  `extras`, `meaning`, `reading`, `notes`, `complete` and `missing`:

  ```
  می‌سازم   tex    \vb{ساختن}{sāxtan}{ساز}{sāz}{ساخت}{sāxt}{to make}
            plain  ساختن sāxtan · pres. ساز sāz · past ساخت sāxt · to make
            here   می‌سازم mi-sāzam (ساختن sāxtan · pres. ساز sāz · past ساخت sāxt · to make)
            line   pres. ساز sāz · past ساخت sāxt
  ```

  Three rules the core holds for every language:

  - **The meaning is the dictionary's first ranked sense, trimmed, and only
    under an English gloss.** Cut at its first top-level `;`, a parenthesis
    longer than 25 characters taken out — a qualifier that short,
    "(transitive)", "(of a liquid)", is information a learner uses, and one
    that long is a definition: piottare is "to go (on a vehicle) at 100 km/h
    (~62 mph) or beyond" — and capped at 60 characters. A book or a video
    glossed in anything else gets no meaning at all, and it is not counted
    missing: `--gloss=it` gives `\vb{andare}{}{vado}{}{andato}{}{(aux.
    \pw{essere})}`, complete. It is the dictionary's first sense and not the
    text's — `devo` is dovere, "to owe" — and it is the first thing a person
    corrects. Where a kept short qualifier already ends the meaning in a
    parenthesis, the language's extras join THAT one rather than open a
    second beside it: German's `warten` is "to wait (for; auf + acc.)", not
    "to wait (for) (auf + acc.)" — only the trailing parenthesis merges, and
    only where the meaning is plain text.
  - **What LaTeX reads as an instruction is taken out, not escaped.** Every
    slot loses `\ { } $ # _ ^ ~` and control characters, `%` becomes " per
    cent" and `&` " and ", because `texwrite` refuses those escaped as well
    as raw and refuses the whole save (Chinese 研發 is "to do R&D"); and
    `build` then asks `texwrite._check_voc` itself, so the editor can never
    offer a line the save would refuse.
  - **An entry is built once.** An LRU of 4 096, keyed on the dictionary
    file's stamp, the hand table's, the recipe, the entry, the word, its
    sound and the gloss. The chunk and the sentence join the key only for a
    recipe that read them: German's `fährt` is fahren in one chunk and
    abfahren in the next, where every other verb is the same entry wherever
    it is met.

  The hand tables, `lib/lang/<code>.verbs.json`, hold what no dictionary
  records, and are read again whenever the file changes, so nobody restarts
  a server to see a fix: the Hindi verbs whose subject takes ने in the
  perfective (77 do, 6 either way, 42 never) and its light verbs; English's
  ten modals and its closed list of presents worth printing; German's
  prepositions and the case each governs; the thirty Arabic prepositions a
  sense's bracket may name; Persian's preverbs and the verb that takes no
  mi-; Chinese's hand-typed separable and complement verbs, read before the
  head line; the meanings of ser and estar, which one "to be" cannot tell
  apart, and sixty Spanish spellings that are never a verb here (para);
  the French verbs whose second auxiliary is a sense nobody meets now
  (partir takes être: the avoir is "to divide"); Turkish's imek, which has
  no present and no aorist to print. Nine rows have one; Italian and
  Japanese read everything from the dictionary.

  What each recipe reads, and what it leaves to a person. The examples are
  `python3 lib/verbs/__init__.py <code> "<text>"` on the dictionaries built
  here, and on scratch builds for Arabic, French, Turkish and English, which
  have none installed:

  - **fa** — infinitive · present stem · past stem, all three sounds from
    the one literary Iranian table in `entry.head` where there is one (256 of
    471 simple verbs), else from the head line; `pres. without mi-` for داشتن
    alone; in a video only, `coll. <form>` where the Tehrani present
    differs. A compound gives its light verb's `\vb` with no meaning and
    names the `\bw` it still wants: `فکر می‌کنم` →
    `\vb{کردن}{kardan}{کن}{kon}{کرد}{kard}{}`, missing *bw for فکر fekr
    after it: to think*. `برگشتم` →
    `\vb{برگشتن}{bar-gaštan}{برگرد}{bar-gard}{برگشت}{bar-gašt}{to return}`.
  - **ar** — the perfect, vowelled, its form number in its sound; the
    imperfect; the masdar, the first the source lists, and the others as a
    note (*masdar also: مَقَال maqāl, مَقَالَة maqāla* — 1 122 of 7 233 verbs
    list more than one); `+ \pw{P}` for the preposition the shown sense
    governs; a verb whose head says it has no verbal noun leaves the pair
    blank and is complete. `قَالَ` →
    `\vb{قَالَ}{qāla (I)}{يَقُولُ}{yaqūlu}{قَوْل}{qawl}{to say}`, and the video
    line `قال qāla (I) · impf. يقول yaqūlu · masdar قول qawl · to say`.
  - **it** — infinitive · 1st sg. present with its pronouns · past
    participle; a sound only where the stress is not on the next-to-last
    syllable (`córrere`); `aux. \pw{essere}` or `aux. \pw{avere}/\pw{essere}`,
    nothing for avere alone; `p.r.` only when the passato remoto is
    irregular. `si` or `se` before the verb gives the pronominal verb, flagged
    with the doubt. `vado` →
    `\vb{andare}{}{vado}{}{andato}{}{to go (aux. \pw{essere})}`.
  - **ja** — dictionary form · -masu stem · -te form, each with its rōmaji;
    the class always (godan, ichidan, suru, irregular), `tr.` / `intr.` and
    `hon.` / `hum.` where the source says; the kana after a kanji headword in
    a video's line. `手紙を書いた` →
    `\vb{書く}{kaku}{書き}{kaki}{書いて}{kaite}{to write (godan; tr.)}`.
  - **fr** — infinitive · 1st sg. present · past participle, each sound its
    row's own IPA respelt; `aux. être` or `aux. être/avoir`; `nous …` and
    `fut. …` only where they are not built on the infinitive; the pronominal
    verb read from the chunk. `il se lève` →
    `\vb{se lever}{se levé}{me lève}{me lèv}{levé}{levé}{to rise (aux. être)}`.
  - **de** — infinitive (with `sich` for a reflexive) · preterite as a main
    clause has it · past participle, and no sounds; the 3rd sg. present
    where it is not stem + (e)t (`er fährt`), `aux. sein` or
    `aux. haben/sein`, the government a sense is tagged with, and a two-way
    preposition's case left to `missing`. A separable verb is put back
    together from the SENTENCE: the fixture's chunk `und stand langsam`,
    with its sentence `… von seinem Stuhl auf.`, gives
    `\vb{aufstehen}{}{stand auf}{}{aufgestanden}{}{to get up (aux. sein)}`,
    and stehen's without it.
  - **tr** — infinitive · present in -iyor · aorist, the sound slots empty
    because the spelling says it; `-e`, `-den`, `-de`, `ile`, `-in` where the
    sense is tagged; a compound as its light verb with the `\bw` named.
    `bakıyor` → `\vb{bakmak}{}{bakıyor}{}{bakar}{}{to look at (-e)}`.
  - **en** — plain form · past · past participle with their General American
    sounds, a sound refused and named where the source's transcription is
    visibly not GA; a present printed for be, have, do and say alone; no
    `\vb` for a modal. `said` →
    `\vb{say}{seɪ}{said}{sɛd}{said}{sɛd}{to pronounce (pres. \pw{says} \textit{sɛz})}`.
  - **hi** — infinitive · stem · perfective m. sg.; `+\pw{ने}` or `±\pw{ने}`
    from the hand table, then the head's transitivity, then the sense
    labels, and `missing` where none says. `वह घर गया` →
    `\vb{जाना}{jānā}{जा}{jā}{गया}{gayā}{to go}`.
  - **es** — infinitive · 1st sg. present · 3rd sg. preterite, the sounds
    empty; `p.p.` and `fut.` only when irregular; `se` with a verb drafted as
    the -se verb and flagged. `hizo` →
    `\vb{hacer}{}{hago}{}{hizo}{}{to do, perform, execute, carry out (p.p. \pw{hecho}; fut. \pw{haré})}`.
  - **zh** — a `\vb` for two kinds of verb and no other: a separable
    verb-object verb, with its split and no can't form, and a verb with a
    resultative or directional complement, with its can't form and no
    split. Every other verb and every single character stays `\dw`, and so
    does everything in a dictionary built before pinyin was kept. `睡觉` →
    `\vb{睡觉}{shuìjiào}{睡了觉}{shuìle jiào}{}{}{to sleep}`; `看见` →
    `\vb{看见}{kànjiàn}{}{}{看不见}{kànbujiàn}{to see}`.

  Built over every verb entry as its own headword, with an English gloss:
  Italian 47 030 of 47 138 get a `\vb`, German 10 170 of 10 237, Japanese
  12 073 of 12 750, Spanish 10 708 of 11 856, Persian 1 366 of 1 415 (917 of
  its 921 compounds among them, every one incomplete by its `\bw`), Hindi
  1 495 of 1 633, and Chinese 2 244 of 34 141, which is the design; on the
  scratch builds, Arabic 7 152 of 7 233, French 7 320 of 7 712 one-word
  verbs, Turkish every -mek lemma but imek, English 35 568 of 36 613
  one-word verbs. What is a person's in every language is the same short
  list: the sense (the first ranked, not the text's), a sound the data has
  not got, which of two auxiliaries (German prints `haben/sein` for 314
  verbs), which masdar, a compound's `\bw`, and which of two homographs —
  einen gets "to unite" and vais gets vader, and the editor picks.

  `python3 lib/verbs/__init__.py <code> "<text>" [--gloss=<code>]
  [--sentence="…"]` prints what each hit would offer, or `no vb`, and says
  when the language has no recipe. `tests/fixtures/verbs/<code>.json` holds
  eight real entries per language, cut to the rows the recipe reads, and
  `python3 tests/smoke.py --only verbs` builds each into a dictionary of one
  entry, so no dictionary need be installed, and checks that every `\vb`
  it builds is one `texwrite` accepts and reads back the same in `texparse`,
  in the book reader and in the video's line.

- **A parallel corpus answers the question a dictionary cannot: not what the
  word can mean, but what this sentence means by it.** `lib/corpus.py` reads
  one SQLite per PAIR of languages, `corpus/<code>-<gloss>.db`, built by
  `lib/getcorpus.py` from Tatoeba's own exports (CC BY 2.0 FR) — exactly the
  arrangement `dict/` has: somebody else's work, downloaded once, git-ignored,
  and a pair without one simply offers nothing. Given the chunk it finds
  sentences a person translated that share the chunk's rare words, and shows
  both sides with the shared words named, so the panel says WHY a sentence is
  there rather than asking the reader to spot it. It is **not a translation
  of the chunk** and the panel says so; the reader decides, which is the
  dictionary panel's own arrangement with better evidence in it.

  **Three downloads per pair**, because Tatoeba stores sentences per language
  and the LINKS between them separately, a sentence translated into thirty
  languages being stored once: `<iso3>_sentences`, `<gloss iso3>_sentences`
  and `<iso3>-<gloss iso3>_links`. Only the gloss-language sentences the links
  actually name are kept, which is why the 24 MB English export does not
  become 24 MB of Persian corpus. This is what put `iso3` in the registry
  (§1).

  **The match is weighted by inverse document frequency**, counted at build
  time into a `df` table rather than computed per lookup: sharing "and" is
  worth nothing, sharing "homeland" is worth the match. Two things about that
  weighting were wrong first, both found by testing, and both are the kind of
  wrong that says nothing while it happens:

  - **The relevance floor cannot be an absolute score.** It was 2.0, tuned on
    Persian's 8 454 pairs. Inverse document frequency is measured against the
    size of the corpus, so on a corpus of five sentences the highest score any
    word can reach is below that number, and a small corpus would have matched
    nothing at all, silently, forever. The floor is now a fraction of what the
    rarest possible word is worth — `MIN_SCORE_SHARE` (0.5) of `log(total/2)`,
    a word appearing in one sentence — so it scales with the corpus it judges.
  - **The gate is on the RAREST WORD IN COMMON, not on the sum.** Gating on
    the sum let common words add up: «این و آن» ("this and that"), three of
    the commonest words in Persian, scored 8.47 between them and offered a
    sentence about nothing to do with the chunk. One genuinely rare word in
    common is what makes a sentence worth showing; the sum then decides which
    of the qualifying sentences goes first.

  **The corpus folds a word exactly as the dictionary does**, borrowing
  `lookup._bare` and `lookup._fold` rather than writing a second copy of them,
  because the half that indexes and the half that asks would otherwise be
  looking for different strings — which the smoke test checks per language.

  What it is for, in the case it was written against: «سیگار می‌کشد» finds
  «سامی دارد علف می‌کشد و می‌نوشد» / "Sami is smoking weed and drinking" —
  the SMOKING sense of a verb the dictionary offers only as *to kill*, because
  Wiktionary files the می‌-forms under کشتن and only the bare aorist under
  کشیدن. No affix rule was going to find that, and no dictionary was going to
  choose it. **Coverage is very uneven and nothing here can even it out**,
  and the spread is worth the three measurements: built on this machine,
  Italian–English is 719 192 pairs and 182 MB and Spanish–English 283 123
  pairs and 83 MB, while Persian–English is 8 454 pairs and 3.3 MB. Two
  orders of magnitude between languages the toolbox treats identically, and
  the smaller one is not a smaller version of the larger — it is a corpus
  that answers a common sentence and is silent on an uncommon one. A pair
  Tatoeba does not carry at all offers nothing, which is the same silence a
  language with no dictionary already has.

- **A translation model that runs in the page, and writes nothing anywhere.**
  `lib/getmt.py` fetches it; `lib/mt.js` is the glue both readers share rather
  than two copies of the dirty part. It is a **translation** model and not a
  chat model: one job, no prompt, no endpoint, no key, no conversation, and
  the same answer every time for the same sentence. It runs as WebAssembly in
  a Web Worker **inside the reader**, so the line never leaves the machine and
  the toolbox gains no Python dependency at all.

  **The engine is pinned**: bergamot-translator (MPL 2.0), the one Firefox's
  own translations feature uses, at `getmt.ENGINE_VERSION` = 0.4.9. An
  unpinned dependency fetched over the network changes under a reader without
  anybody deciding to change it, so the version is written once and moved by
  hand. The models are Mozilla's, from the service Firefox itself fetches them
  from, and they are small — about 20 MB a pair against gigabytes for a
  general model. Engine and models live in `mt/`, git-ignored for the reason
  `dict/` is. Every row of the registry has a model to and from English
  today, Spanish and Chinese included; where a pair has none it is not
  offered at all rather than offered and broken, which is what `trainable()`
  is asked before the picker is drawn.

  **The service does not always spell a language the way the registry does.**
  Mozilla names Chinese by its script — `zh-Hans` for the simplified
  characters Parseh's `zh` teaches, `zh-Hant` for the traditional ones — so
  `lib/getmt.py` translates the code on the way out: `_SERVICE` is the map,
  `service_code()` is the one function that reads it, and both halves of a
  pair go through it at the one place a record is matched — `_pick` is handed
  `service_code(A.code)` and `service_code(B.code)`, never the raw codes. It
  lives in the downloader and **not** in the registry because it is a fact
  about one service's spelling and not about the language. A `service` field in
  `lib/languages.json` would be a second name for Chinese sitting beside the
  real one, true only for as long as this service keeps that habit and
  meaningless to every other reader of the row — and a row holds what the
  language *is*. The next service that spells something its own way writes a
  map inside its own downloader, which is the shape this one is already in,
  and no row moves.

  That Parseh's `zh` teaches the **simplified** characters is settled here,
  and the rest follows from it rather than being decided again: the model
  fetched is `zh-Hans`, the face is Noto Serif CJK SC, and `docs/lang/zh.md`
  is where the annotator is told so in the language's own conventions. The
  row's `chars` says something narrower and just as deliberate — it covers the
  CJK blocks and the fullwidth forms and **leaves hiragana and katakana out**,
  so a run of Japanese cannot be taken for Chinese by a studio that detects
  runs from `chars` alone (§5). Japanese's `chars` has to cover kana *and*
  kanji and so cannot make that distinction in the other direction, which is
  why it is Chinese's row that carries it.

  **There is no button: the reading is simply there.** Over a chunk nobody
  has glossed, with the reader's switch on, the panel opens with the
  machine's reading already in it. It used to be a **translate this line**
  button that replaced itself with its own answer, and the button was asking
  a question that had already been answered: a reader who turned the reading
  help on has said they want help, and a press whose only possible outcome
  is the thing they asked for is a press that buys nothing. What the button
  really stood guard over was the 20 MB, and the SWITCH is where that choice
  belongs — it is the reader's one deliberate act, it is remembered, and it
  is off by default. So the model is fetched by the first batch the
  preparing loop above sends and not on the chance of a press; with the
  switch off nothing is fetched, nothing is translated, and the page costs
  exactly what it cost before any of this existed.

  **The unit of translation is the SENTENCE, and a chunk cannot be one.**
  This is the decision the rest of the block follows from. A chunk is a
  fragment BY CONSTRUCTION — that is what a chunk is: two to five words, cut
  at the edges of phrases (above) — and a model whose only context is the
  string it is handed will read a fragment as a fragment. Measured: `مثل
  ایران با هم` alone came back "The parable of Iran with Hem", three words
  each defensible on its own and a sentence about nothing; the sentence
  holding «دوباره می‌سازمت، وطن» came back "I will rebuild you, my
  country, even with the ads of your soul" — which carries the near future
  and the attached *you* that every small model dropped when it was shown
  the chunk by itself. Nothing about the model could have been tuned to fix
  that, because the missing thing was never in the input. So the sentence is
  what is translated, in both readers: a subparagraph's chunks joined back
  up in the book (`subSentence`), the whole caption in the player — and the
  label says which, *a machine's reading of the sentence* or *of the
  caption*.

  **Which words of that sentence are THIS chunk's is a guess, is drawn as
  one — and is made from MEANING, never from place.** The panel shows the
  sentence entire, marks the chunk's share of it, and names underneath what
  the mark stands on — *this chunk is likely: "short hat" — کوتاه → short ·
  کلاه → hat*. There is no better answer available: the engine's WebAssembly
  build exposes `getTranslatedText` and the sentence ranges and **no word
  alignment at all**. `ParsehMT.align(target, probe, words, lang)`
  (`lib/mt.js` — one implementation, shared by both readers) works from:

  - **the dictionary's meanings for the chunk's words** — the lookup the
    panel has just drawn (`words`, as `/__lookup` answers it). Each sense is
    cut into its equivalents at `;` `,` `.`, brackets out; an equivalent
    longer than five words, one that describes grammar ("Used to mark…",
    "genitive case marker" — `GRAMMAR`) or one that points or names
    ("synonym of…", "See Usage notes", "a surname" — `META`) is dropped, and
    what is left is what a gloss line would print. The first hit's first
    sense counts most, a homograph's third sense least, a word from a
    one-word equivalent more than one from a description ("hat" for کلاه;
    not "made" out of 笄's "hairpin of women, perhaps made of bamboo");
  - **the chunk translated on its own**, the PROBE (poor prose, a decent bag
    of words: `کاسب کارهای لباده دراز` alone says "business" and "Deraz").

  **Place is not used at all.** It used to be: the mark preferred the run of
  the translation sitting where the chunk sits in its sentence, and fell back
  on that place when nothing matched — and word order is exactly what a
  translation changes. `امروز صبح` opens its Persian sentence and "this
  morning" ends the English one; a Persian verb comes last. Measured on the
  393 chunks of the fixtures' Persian, Chinese, Spanish and Italian books and
  videos, against the human gloss of each (twelve of those real cases are
  frozen in `tests/fixtures/align/cases.json`, which `tests/mtcheck.py
  --align` runs): Persian
  marks right went from 76% to 84% and **wrong from 21% to 4%**; Chinese,
  Spanish and Italian wrong from 10%, 4% and 0% to none, with precision up
  8–15 points in each. On the 214 chunks the model garbled past matching,
  confident marks went from 195 to 87.

  The rules, each forced by a measured case:

  - **Only a CONTENT word starts a mark.** English words are function (the,
    of, to, and — `STOP`), light (up, under, all, not, without — `LIGHT`) or
    content. A function word the chunk's senses use (از "of, from", و "and")
    only extends a mark it touches, and only when an equivalent is nothing
    but function words: the "to" of "to wear" made every verb reach its mark
    into "…sun to the". A light word starts a mark only as the first meaning
    of a word that is not itself a function word (下 "under"), and never on
    the probe's say-so: 没有目标的 translated alone said "without", and the
    sentence's one "without" was the previous chunk's.
  - **A word whose first answer is grammatical is a function word.** آن is
    first "that", به "to", که "that"; 的's second answer is "genitive case
    marker", 到's "used as a verbal complement…". Their homographs — آن
    "moment", به "good", 的 "clear" — marked "comes", "good", "clear" where
    the sentence had them. A light first meaning does not count: luego is
    "then", and then "later", which "see you later" has.
  - **Words meet once stemmed**, on both sides the same way: inflection
    (burn/burned, city/cities, and a table of irregulars: fall/fallen,
    find/found), derivation (dark/darkness, goal/goalless), British and
    American spelling (colour/color, centre/center), a word beginning
    another (business/businessman, Iran/Iranian) or ending it after a real
    prefix (build/rebuild — not ring/bring, which marked "stone ring" for 帶回
    "to bring back"), one letter apart from six letters up
    (moustache/mustache), and the parts of a hyphenated word (red-clad).
  - **A mark is the words that stand together**, with at most two function
    or light words between (*parable of Iran*, *Baku and Rasht*); an
    unmatched content word or the end of a sentence ends it (是我发现她的 was
    marked *found her. She*); it does not end on *and* or *the*. A lone weak
    match (quality under 0.7) is no mark. **Only a STRONG anchor (0.7 or
    above — the word itself, or an inflection of it) may EXTEND a cluster**,
    and only into another strong one: a synonym-quality anchor (below 0.7)
    neither joins a neighbour nor lets one join it. Skipping this let a
    garbled reading's repeated "Lord of the Lord, the Lord of the Lord"
    chain every repeat of a synonym match into one span covering the whole
    line, measured; and let a strong match two words later drag a weak,
    unrelated one in for free (below).
  - **The chunk is marked in every place its meaning landed**, but a place
    is added only for a word of the chunk the others do not cover — a word
    already in a mark by its function word is in it (در is "in" there, and
    its homograph "door" further on is not a second place) — or for a
    STRONG new content word of the probe (*found … dreams*: the dictionary
    has پیدا only as "evident"; a synonym-quality probe match, below 0.7,
    does not qualify on its own — `aid`, a synonym of the probe "help", is
    not enough to add a second mark beside the real `helped`). A word the
    translation says twice with nothing to tell the two apart is marked
    twice, up to three places.
  - **Where nothing anchors, nothing is marked**, and the line says *no word
    of this reading matches what the dictionary says of the chunk*. A mark
    resting on half the chunk's meaningful words or fewer is drawn dotted,
    *part of this chunk is likely*.

  **A SYNONYM IS REAL EVIDENCE, WEAKER THAN THE WORD ITSELF.**
  `lib/getsyn.py` builds `mt/synonyms.en.json` from
  [WordNet 3.1](https://wordnet.princeton.edu/) (Princeton University;
  the WordNet 3.0 licence, redistribution and modification allowed with the
  notice kept): `{stem: [stem, ...]}`, about a megabyte, fetched from the
  reading help and loaded once (`synLoad`, kicked off from `has()` the moment
  a reader learns a model exists — well before a hover, so it is ready in
  time — with `translate()` as a backstop). `meet(a, b)` tries it last, at a
  fixed quality `SYN_Q` (0.62) — below a stemmed match (1), a
  build/rebuild-style inflection (0.8) and one letter apart (0.75), always —
  after nothing stronger answers. **Only a synset that is the FIRST, most
  common sense of BOTH its words counts**: WordNet groups `heap`, `mountain`
  and the phrase `about_face` into one synset for `heap`'s primary sense,
  "a large quantity", and taking any pairing from it wherever either word
  merely appears would have `mountain` (a land mass) inherit `heap`'s
  synonyms; requiring the synset to be `mountain`'s OWN first sense too
  drops that whole cluster and keeps the real pair, `mountain`<->`mount`.
  Measured: 101,880 candidate pairs falls to 64,206 once both sides must
  agree, and the biggest group shrinks from 74 words to 26.

  Given that a synonym alone reaches a cluster, it is admitted only from the
  word's OWN first sense (`meaningsOf`'s `firstContent`, the same
  restriction the table's build uses on WordNet's side): `صاحب` ("owner;
  master") links to `lord` because `master` is what its first sense gives,
  not because some OTHER hit of the same word happens to reach it. This is
  what kept `pueblo`'s second, unrelated hit (`poblar`, "to populate") from
  lending `living` to `pueblo`'s real sense ("town, village") in a Tatoeba
  sentence, measured. `stem` is ported by hand into `lib/getsyn.py`
  (`tests/mtcheck.py --align`'s `synonyms()` checks the two agree on the
  same word list; `tests/smoke.py`'s `test_getsyn` builds a table from a
  synthetic archive and checks the mutual-first-sense rule on its own).

  Measured on the fixtures' 393 chunks and a further Tatoeba sample against
  their human glosses: adding synonyms changed 3 of 508 chunks once the
  join and probe restrictions above were in place (down from 9 before them);
  two were real, contained wins (`جیغ` "shriek" reaching *cried*, `صاحب`
  "master" reaching *lord*, each in a garbled reading and each still bounded
  to at most 3 places); one remains a genuine miss — `نگاهم` ("my gaze")
  reached *sound* through `look`, a word WordNet's "look" (verb, "to seem")
  shares a sense with, though the dictionary meant it as "a look, a glance"
  — the SAME stem can be two different English words' senses, and nothing
  here tells them apart. WordNet also does not catch every informal
  paraphrase a model makes: `want` and `like`, `plain` and `simple`,
  `piece` and `chunk` are not literal WordNet synonyms, so a translation
  that swapped one of those still gets no mark. Small, honest gains, always
  beneath an exact match.

  `align` returns `{ranges, from, to, text, sure, pairs, by}`;
  `ParsehMT.marked(target, span)` cuts the sentence for drawing and
  `ParsehMT.why(span)` writes *صبح → morning*. The sources column's model
  block waits for the same lookup before it marks anything (`Promise.all`
  of the translation and the lookup), so both places mark the same words.

  **The sentences ahead are translated in ONE call, because the engine's
  cost is fixed.** Measured: ten Persian sentences came back in 74 ms
  against about 30 ms for one — the batch is almost all overhead — so
  preparing ten costs about what preparing one costs, and there is no reason
  to prepare one. Both readers hand the next `AHEAD` sentences over together
  — the same ten the preparing loop above counts in — and only the ones that
  hold a chunk nobody has glossed, so a finished page asks for nothing. That
  is what buys the panel opening already filled rather than opening onto a
  wait: measured, a panel opened in 0.3 s in the book reader and 1.3 s in
  the player. **It runs only while the switch is on** (`preSentences` returns
  nothing otherwise), which is the same rule the download follows and for the
  same reason — reading ahead is work done for somebody who asked to be
  helped.

  **What is kept, and why it is two maps and both bounded.** Each reader
  holds the sentence translations, which is what the panel shows and what
  every chunk of a sentence shares, and separately the chunk probes, which
  are never shown and exist only for the guess above. They are two maps
  because they are two different things keyed by two different strings, and
  merging them would have made a probe answerable as though it were a
  reading. Both are bounded at `MT_KEEP`, 400 entries, oldest evicted first
  (the player keeps one insertion list over the two and trims it to twice
  that): a long book walked end to end would otherwise hold every sentence
  it had passed, for a reader who is looking at one.

  **The panel's order is the dictionary, then the machine's reading, then
  the sentences somebody translated**, and the order is an argument about
  what a reader should meet first: what the words can mean, then what the
  line means, then what somebody else made of a different line. It used to
  put Tatoeba second and the machine's reading last, which is where a button
  naturally goes — a thing you have to press is a thing you put at the end.
  With the reading simply there that stops being a reason, and it belongs
  beside the words it is a reading of, leaving the corpus — which is
  explicitly *not this sentence* — as the footnote it always was. Both
  readers draw it in that order and `tests/smoke.py` pins it by position in
  both, `tests/mtcheck.py --panels` by opening a real book and a real video
  and reading the panel's children back.

  **Where one block ends and the next begins has to be seen**, and for a
  while it could not be. The three were parted by a 1px dotted `--rule`
  line, which on the panel's tint measures 1.08:1 in the light and the dark
  theme and 1.12:1 in sepia — no line at all — and each block's source line
  wore the same rule, so the end of one block and the start of the next
  were one invisible stroke. Now the dictionary is a block of its own
  (`.ddict`) like the other two (`.dmt`, `.dpairs`), the gap between two
  blocks is a solid 2px `--faint` rule with room either side of it
  (2.3–2.4:1 in all three themes), a block's head is `--dim` at weight 600
  (4.1–5.7:1, where `--faint` was 2.3), and the source line under a block
  has no rule at all: a line belongs to the block above it, a rule to the
  gap between two. Theme tokens only, so light, dark and sepia follow
  without a rule of their own, and the sources column's three heads carry
  the same 2px rule, all but the first. A verb hit carries one more line in
  the dictionary block, under its headword and before its senses (`.dvb`):
  `vb.line`, led by the lemma where that is another word — `→ aufstehen ·
  pret. stand auf · p.p. aufgestanden · aux. sein` under *stehen* — because
  "to burn" is what an infinitive means and the stem the sentence is built
  on is what a reader was left to guess.

  An answer that lands after the cloud was placed used to grow it down over
  its own phrase and off the window. Both readers place it again when the
  panel fills: the book keeps the side the cloud opened on and cuts the
  panel, which scrolls, to the room there, changing sides only where the
  panel would drop under 120px (`PANEL_LEAST`); the player places it again
  only if its size changed, and never while a phrase is being edited, and
  cuts a panel that fits on neither side to the larger, never under 96px
  (`PANEL_MIN`).

  **What has not changed**, and none of it is negotiable: it is labelled *a
  machine's reading of the sentence — not a gloss*, *of the caption* in the
  player, and plain *a machine's reading* where the chunk turns out to BE the
  whole line — a subparagraph or a caption holding one chunk and nothing else
  — because there the sentence and the chunk are the same string and naming
  the sentence would claim a distinction the panel is not making (nor is a
  span marked inside it, for the same reason). It has **no `use` button in
  the panel** — the reader's panel is for reading — and it is shown only
  where nobody has written a vocabulary line. Where it CAN be taken up is
  the gloss editor's sources sidebar, which puts it into an unsaved box for
  somebody to correct; nothing reaches a book or a video except through the
  ordinary edit route with the ordinary checkers on it. That is the same line the
  dictionary panel holds, and it is the whole reason a machine reading can be
  shown beside a hand-written gloss at all.

  Two things the browser settled. `serve.py` has to name the wasm MIME type
  (`mimetypes.add_type("application/wasm", ".wasm")`), because
  `WebAssembly.instantiateStreaming` refuses anything else, and `/mt/` joins
  the static prefixes. And the test is a **separate script**,
  `tests/mtcheck.py` (Playwright and Chromium), rather than a case in
  `tests/smoke.py`: the only honest test of WebAssembly needs a browser, and a
  browser is not something this toolbox otherwise depends on — so it skips
  cleanly with a message where Playwright or a model is absent, and `smoke.py`
  keeps only what it can check without one (the pin, the shared glue, both
  readers' labels, the panel's order, that neither reader asks for a button,
  the MIME type). `--panels` is the other half, and the one that answers
  whether any of it reaches a reader: it parks the Persian fixture book and
  the fixture video where the server serves them, opens each, turns the
  switch on, and reads back what the panel actually drew over an unglossed
  chunk — the entries, the reading, the marked span, the sentences, and the
  order they came in. Verified in a real browser: «دوباره می‌سازمت، وطن» →
  "I'll build you again, home." in 0.3 s including the model load, and "Mi
  manchi tanto." → "I miss you so much."

- **Three optional things, one panel, one rule.** The sense ranking, the
  corpus and the model are drawn in the same borrowed panel as the dictionary,
  each labelled with what it is and where it came from, each shown **only
  where nobody has written a vocabulary line**, and **none of them writes
  anything into a book or a video**. (The one place their output can be taken
  up is the gloss editor's sources sidebar, below, and even there it lands in
  an unsaved field.) All three are downloaded rather than shipped and silent
  rather than loud when absent, so a toolbox with none of them is the toolbox
  as it was, and a finished edition looks exactly as it did. `/lookup/` then
  carried three sections — dictionaries, corpora, models — a row per language
  in each: the dictionary row offers **get it**, or **rebuild** beside
  **remove** (above), and the corpus and model rows carry a **gloss picker**
  beside **get it**, with **remove** for each pair already there, because a
  corpus and a model are a PAIR of languages and one language may hold
  several. The picker lists only the glosses that language has *not* got.
  **A corpus also offers rebuild and a model does not**, and the difference
  is what each is a snapshot of: Tatoeba gains sentences every week, so a
  corpus is worth retaking in place exactly as a dictionary is, while a model
  is a pinned version (`getmt.ENGINE_VERSION`, and a version per pair) that
  would come back byte for byte. The model picker is narrower still: it
  offers only the glosses a model could exist for, because Mozilla trains its
  pairs against English rather than against each other, and a choice that can
  only fail is worse than no choice. `install.sh` reports all three, and says
  for each what is missing and what the machine loses by it.

  A FOURTH thing is not per language at all: the synonym table (below) is
  one file, English only, and the page's row for it has no gloss picker
  and no per-language loop — **get it**, **rebuild**, **remove**, the same
  three words, on one row. `install.sh` reports it alongside the other
  three.

- **The sources sidebar: the same three things, where the gloss is actually
  written.** The reader's panel is for reading, so it has no buttons; but
  reading a sense in the cloud and then retyping it into the sheet was the
  whole of the work, and retyping is where a romanisation loses a macron. So
  the **gloss editor** carries the three as well, behind a `⊕ sources` button:
  `#chsrc` opening `#chside` in the book reader's chunk sheet
  (`lib/tex2html.py`), `.esrc` opening `.eside` in the player's edit cloud
  (`youtube/lib/player.js`). Closed by default, and the choice remembered —
  per book (`bk_chside:<path>`, the reader's usual `MINE()` namespace) and
  once for every video (`yt_side`), which is the difference between a reader
  that is opened at one book and a player that is opened at whichever video
  is next.

  **A column to the LEFT of the fields, and the window grows to hold it.**
  It used to be a block above the fields inside the same sheet, so every
  word's entries, the model and the corpus pushed the boxes they were meant
  to fill below the fold. In the book reader the sources are `aside#chside`
  beside the fields' `.chmain`, first in the DOM and so on the left in every
  book, a right-to-left one included — the sheet is chrome, `dir="ltr"`.
  Opening them puts `side` on `#chbox`, which keeps the sheet's right edge
  where the 680px sheet had it and grows it leftwards, to at most 1180px and
  never nearer than 16px to the window's edge; the fields keep 642px while
  there is room, the column takes 260 to 480px, and its `contain:size`
  means nothing that lands in it makes the sheet taller than its fields.
  Measured in Chromium at 1280px wide: the sheet goes from 680 to 964px, the
  column is 266px, and the text box stays at x=425, 532px wide, before and
  after. In the player the sources are `.eside` beside the fields' `.emain`,
  and `sideon` on `#cloud` widens the edit window from 460 to at most 940px
  with a fixed height, `min(82vh, 620px)`, because the answers arrive a
  round trip after the window opens and a window that grew as they came in
  would move the field somebody had started typing into; `placeEditor` keeps
  the right edge where the fields-only window's would be. At 1280×800 the
  fields stay at x=700, 434px wide, and the sources take 220 to 688. Both
  columns scroll on their own, and the save row stays in sight under the
  fields. A narrow window has no left to open into — 820px in the book,
  720px in the player — so the fields keep the top and the sources go under
  them: the book's sheet scrolls as a whole and, on the press of ⊕, down to
  the column, and the player's sources are a strip of at most 36vh.

  **Three blocks, in the panel's own order**: `dictionary`, `a machine's
  reading`, `sentences somebody translated` — the same order for the same
  reason, each head ruled off from the block above by the panel's own solid
  line (above). Both readers draw the three at once, each holding a
  waiting line until its answer lands (`sideSection` in the book,
  `srcSection` in the player), so a lookup that fails still leaves three,
  the dictionary's and the corpus's each saying it could not be reached;
  the player used to add the third heading only when the lookup answered,
  and a failed one left two. A block with nothing to offer says so
  in words rather than drawing an empty heading. What each line carries is
  the buttons that put it where it goes: a romanisation into `tr` (the
  hit's `translit`, the sound of the word as the chunk has it where the
  source romanised that form, else the lemma's); a sense into `en`; a whole
  entry appended to `voc` **in the form that shelf writes, and a verb as a
  verb**. A hit the language's recipe recognised goes in as its `\vb` —
  `vb.tex` in a book, whose vocabulary line is LaTeX, and `vb.tex_video` in a
  video, whose line takes the same macros with what only a video says added
  (`vb.here`, the plain entry hung on ` · `, is what a page without
  `lib/vocline.js` still puts) — and gets
  no `\dw` button; the row shows `vb.line` under the headword, so what the
  button will put is read before it is pressed. Where the book already
  writes a `\vb` for that lemma, the book's own is offered first (`\vb as
  this book glosses it`), found by counting braces so a `\pw` inside it
  survives, and the dictionary's only beside it and only where the two
  differ. Anything else goes in as `\dw{headword}{sound} sense`, in a book
  and in a video, where the headword is the text's
  spelling when the hit has one (`spelled`) and the sound is the lemma's
  (`head_sound`), so `\dw{ساختن}{mi-sāzam}` cannot be written again. And for
  the model, either the marked span or the whole reading into `en`. The
  model's block marks the chunk's share inside the sentence exactly as the
  panel does, by `ParsehMT.align` on the same lookup, and says underneath
  which of the chunk's words the dictionary found there — or that none
  matched, in which case nothing is marked.

  **A draft that is not finished says so, on the row and on the button.**
  Where the recipe could not fill something (`vb.complete` false) the row
  lists `vb.missing` under *to fill in:*, one item to a line, because the
  items carry colons and semicolons of their own (*bw for فکر fekr after it:
  to think*) and joined with commas they read as more items than there are;
  the button's title repeats the list, and the button is dashed as well
  (`sgap`, in both readers: the player's used to be drawn solid, as if the
  video's line went in finished). A verb the recipe calls incomplete
  without naming the gap gets the item *part of it (the dictionary did not
  say which)*, in both. `vb.notes` — hints that are not missing, Arabic's
  other masdars — go under the line, a step quieter, and never make a
  button dashed. The row is headed by the word as the text spells it
  (`spelled`, else the headword, which the title then names), and where
  what the vocabulary gets is another word, the row says so with an arrow:
  `stehen → aufstehen`. Both readers compare the two with the language's
  marks and case folded (`wordKey`), so an Arabic verb's bare headword and
  its vowelled lemma are one word and draw no arrow, and nor does a
  Chinese verb filed under its Traditional spelling; the player compared
  them as written, and drew `وصل → وَصَلَ` and `睡覺 → 睡觉`, one word
  pointing at itself.

  **It appends, it never replaces**, because a vocabulary line is built up
  entry by entry and a meaning is often two of these joined: `put`/`srcPut`
  join with `; ` (the book) or ` · ` (the player) for `voc` and a space
  elsewhere, then focus the field and leave the caret at the end, so the next
  thing typed continues the line rather than landing in front of it.

  **It writes into a box and never into the file.** Everything lands in the
  sheet's own fields, unsaved, for somebody to correct: the dictionary does
  not know which sense this sentence wants, the model is a machine, and the
  corpus is somebody else's sentence. Save is the ordinary edit route with the
  ordinary checkers on the far side (`check_annotations.py`, the reproduction
  invariant, the reader's own rebuild) — the sidebar adds no way into a file
  that did not already exist.

  **It is not gated the way the panel is.** The panel is drawn only where
  nobody has written a vocabulary line; the sidebar is offered on every chunk
  that HAS gloss slots, written or not, because correcting a line is as much
  of the work as writing one. It does not ask whether the reading switch is
  on either — the switch belongs to reading, and this is editing. The one
  chunk it is not offered on is `\chp`, which carries a colour and no gloss
  at all: with no fields to fill, `#chsrc` is hidden (`chGlossed`), and so
  is the column, which used to stay open over a `\chp` with the previous
  chunk's sources in it and no button to shut it.

  **A late answer goes nowhere.** A lookup is a round trip and the column
  can be refilled before it comes back — shut and opened again, or one
  chunk closed and the next opened — and the answer used to land in
  whatever the column held by then: chunk A's sentences under chunk B's, a
  fourth heading where there are three. Every fill takes a number
  (`sideGen` in the book, `srcGen` in the player), closing the column or
  the editor takes the next one, and an answer whose number is no longer
  current is dropped. The request carries the chunk and its sentence, the
  subparagraph's in the book and the caption in the player, because the
  German recipe needs the end of the clause (above).

  **Both halves are driven in a browser.** `tests/smoke.py` holds the wiring
  (a door in each editor, a filler behind it, the remembered key, the fields
  it can write into, and that the only route to a file is still the editor's
  own save), and `tests/mtcheck.py --panels` drives it: it opens the gloss
  editor in a real book and a real video, opens the sidebar, checks the three
  headings and their order, presses `meaning →`, and checks both that the
  sense arrived in the meaning box and that the page asked the server to save
  nothing. That last check is the contract itself, so it is a count of
  requests to the two save routes rather than a claim in a comment. It also
  asks four things only a rectangle on a screen can answer, at 1280×800 and
  at a phone's 390×844: that the sources open to the left of the fields in a
  window grown to hold them and still wholly on the screen, and under the
  fields on the phone; that the panel's three blocks are parted by a solid
  line; that a note's mark, hovered, shows the note's text and still opens
  the note when clicked; and that a real verb goes in as a verb — it asks
  the server chunk by chunk until one comes back with a `\vb` (`dict/fa.db`
  and `lib/verbs/fa.py`), presses that hit's button, and expects the `\vb`
  in the book's vocabulary box and the verb's entry in the video's, unsaved.

  **One name to keep clear of.** `sideOn` in `youtube/lib/player.js` already
  meant *the side-by-side layout*, and reusing it for the sidebar broke the
  player outright (`sideOn is not a function`). The player's half is
  therefore prefixed `src` throughout — `srcOpen`, `srcShow`, `srcFill`,
  `srcRow`, `srcHead`, `srcPairs`, `srcPut`, `srcGen` — while the book
  reader, which has no such name, keeps `side*`. The class that widens the
  edit window, `sideon` on `#cloud`, is a class in the stylesheet and not a
  name in the script, and the one place the two spellings meet. Anything
  added here should check the file it is being added to first; the two
  readers share a contract, not a namespace.

- **English is the eighth, and it is not special.** In the registry it is an
  ordinary member of the shape above: `chars` null, two passes, `require_tr`
  false, no font of its own, babel `english`, Anki slot 7
  (`1724563200071`/`72`). Nothing was taught about it, and nothing had to be:
  `en` as a *target code* and `en` as the *name of the meaning field* never
  meet, because the field key is a string in a chunk and the code is a key of
  the registry. What it did seem to change was what the fields are *for*, and
  the first version of this note said so in a way that has since turned out
  to be wrong: that English is "the one language whose glosses are in the
  language being taught, so `en` is a definition rather than a translation".
  That is not a fact about English. It is a fact about **any** book whose
  gloss language equals its target — an Italian edition glossed in Italian is
  the same monolingual case, and an English one glossed in Italian is not a
  definition at all — and since `gloss` exists it is a per-book choice rather than a
  property of the eighth row (§1). What survives is `docs/lang/en.md`'s business and not the code's:
  in the monolingual case `voc` is a monolingual dictionary's work, and `tr`
  — which the shape makes optional — is the only line on the page carrying
  what the reader could not have got from the text, so that file requires it
  on every chunk, in IPA (General American), and says why a respelling would
  not do. The one thing the machinery cannot enforce is exactly that:
  `require_tr` is false, so an English chunk with no `tr` passes every
  checker. It is a convention, held by the conventions file and by whoever is
  reading the proofs.
- **The gloss language, and why nothing was renamed.** A book or a video
  now declares two languages, `language` and `gloss` (§1), because the
  toolbox is used by people who are not English speakers: an Italian
  learning English wants the meanings in Italian, and until this the gloss
  was English everywhere by assumption — the chunk key said so, the preamble
  set every gloss inside `otherlanguage{english}` whatever it held, the
  reader labelled the row "english" and the annotation prompts asked for it.
  Three decisions carried the change and each of them was to leave something
  alone.

  The **keys stay**: `en` in a chunk, `English` in a note type, the fifth
  argument of `\ch`. They are slots, not languages (§3), the way `fa` is;
  renaming them would rewrite every stored file in the toolbox and every
  tool that reads one, and the Anki field would split a deck somebody is
  studying into two on the next import (§4). What moved instead is the
  `lang` and `dir` around the gloss, which is what actually renders it.

  The **set of gloss languages is wider than the registry**, because a gloss
  is prose and prose is not a subject: every row of the registry plus a table
  of prose-only codes in `lib/languages.py` (§1), which is the same set the
  studio has taken for `lang:` since it had a front matter. One function
  answers all of it, `languages.gloss(code)` — accepted or not, the name, the
  direction, babel's name — and it defaults to `en`, so a caller that asks
  about a book written last year gets the right answer without knowing the
  field exists. `Gloss` is deliberately not a `Lang`: a `Lang` promises a
  folder, a script, digits, fonts and note types, and a prose-only code —
  Portuguese, Dutch, Russian — has none of them. A code can hold both
  answers over time, which Spanish now does (§1): it was a prose-only row
  when this note was written and is a taught one today, and the only thing
  that had to be right for that to be painless was which of the two lists
  gets asked first.

  And **nothing that exists changed meaning**: absent is `en`. `lib/books.py`
  reads it as `Book.gloss` / `Book.gloss_lang` beside `Book.language` /
  `Book.lang`, with a `gloss_problem()` beside `language_problem()` that
  `find_book()` refuses on — a wrong gloss is the quiet failure of the two,
  since the book looks right and only hyphenates by another language's rules.
  `lib/draft.py` takes the gloss and writes it in all three places a draft
  says anything (`book.json`, `\BookGloss` in `main.tex`, `video.json`) and
  names the language in the chapter header the author types into.
  `lib/bundle.py` carries it in the manifest, refuses a bundle glossed in a
  language nothing here can set, and refuses one whose manifest and JSON
  disagree — the rule every other field of that manifest already lives by.
  The manifest's `format` was **not** bumped: a toolbox that reads
  `parseh-bundle/1` and has never heard of a gloss installs such a bundle
  correctly, because the field is in the `book.json` inside it and absent
  means English at both ends.
- **The toolbox can now be authored by hand**, and none of it needed a
  language taught about. Four modules under `lib/` (and one under
  `youtube/lib/`) carry it, and the server does nothing but map a request onto
  one of their calls and their refusals onto a status code.
  - **`lib/texwrite.py`** rewrites ONE `\ch` / `\chr` / `\chp` call of a
    chapter `.tex` and leaves every other byte alone. A chapter is written by
    hand — its comments, its blank lines, where a long `\voc` was broken
    across lines, the `\parstart` / `\parnum` scaffolding — and none of that
    can be derived from the chunks, so nothing ever re-emits a parsed chapter.
    The walk that finds the call is `texparse.parse_chapter`'s own, step for
    step, because the file that reads a chunk and the file that writes it must
    cut a call into the same pieces or the reader would edit a chunk other than
    the one it showed; the splice is proved (every byte outside the call
    unchanged, the same chunks read back with one changed) *before* the file is
    written.
  - **`youtube/lib/annwrite.py`** does the same for one chunk of
    `annotations.json`, and matches the file rather than its own taste: the
    indent, whether non-ASCII is escaped and whether the file ends in a newline
    are read off the file on disk and written back, so an edit made from the
    player lands as the edit a hand would have made — one line moved in the
    diff. Both write atomically (temp file, rename).
  - **The validation is imported, never restated.** `texwrite` uses
    `check_batch.ALLOWED`, `BADTEX` and `count_args` for the vocabulary field,
    so an edit cannot pass the editor and fail the checker that judges the file
    afterwards; `annwrite` runs `check_annotations.check_segments` twice round
    an edit and refuses whatever the edit *introduces* — introduces, not has,
    because a video being written from nothing is missing half its glosses by
    definition — and it passes the checker's half-glossed messages to nobody
    (`half=`), so filling a blank chunk one box at a time is never refused for
    the boxes still empty (§ a blank gloss, below). What a hand edit may not
    do is *empty* a box the language requires while the rest of the gloss
    stays: `annwrite._emptied` and `texwrite._check_required` refuse that,
    unless the edit empties every box at once — the "delete gloss" the reader
    and the player offer.
  - **Nothing is escaped.** `fa`, `kana`, `tr` and `en` are set by LaTeX as
    literal text, and `\ { } $ % & # _ ^ ~` in them is *refused* rather than
    escaped: `check_batch` rejects those escaped exactly as raw, `\{` would
    reach the reader as a visible backslash (`tex2html` HTML-escapes those four
    fields and never un-escapes LaTeX), and no edition in the repository
    contains one. `voc` is the exception and is written through byte for byte,
    because it is LaTeX by design; it is validated instead, plus one check
    `check_batch` does not make — the braces must balance under
    `read_group`'s rule, since a `voc` leaving one open would swallow the
    arguments after it.
  - **The text field is narrow, in both doors.** A book's `fa` is judged by
    `verify_book.py`'s own rebuild: the chunks of the paragraph, joined with
    the language's separator and stripped of its marks, must still reproduce
    `source/paras/chN_pNN.txt`. A video's is judged against its caption. So
    vowelling a chunk goes through and changing its words does not. A
    paragraph with no source file, or one that did not reproduce its source
    before the edit either, cannot be judged: the edit goes through and the
    answer says which it was.
  - **Where a chunk ENDS is moved by a different pair of operations**, in both
    doors: `lib/chunkdiv.py` holds the rules, `texwrite.merge_chunks` /
    `split_chunk` and `annwrite.merge_chunks` / `split_chunk` write them, and
    `divide_preview` (one in each) is what a page draws. A chunk divides at the
    language's word separator and nowhere else — for a language without one
    (Japanese, Chinese) between any two characters — which is the fidelity check
    read backwards, and a division must be the chunk's text character for
    character, which is *stricter* than the checkers: they strip the harakat
    before comparing, so a cut inside a Persian word would pass them and set a
    PDF nobody meant. A join is safe by construction, the texts going end to end
    with that same separator. Everything else is proposed and typed over: the
    romanisation cut at the same word when it has one per word, each vocabulary
    entry following its headword, the meaning left whole on the first half
    unless a single comma marks the division. Both writers prove the result
    against the checker before it lands, and refuse rather than write: a
    subparagraph seam, a comment between two calls, a chunk sharing its line, a
    caption reduced to no chunks, a page whose text no longer matches the file.
    A `\parnum` label, a `% @par` comment and the subparagraph timing key all
    survive a division — the key because `timestamp.subkey` joins the chunks
    with the language's separator rather than with a space, so it is the
    subparagraph's text and not its division into chunks.
  - **A note is a studio document in a second library.** `markdown/app/notes.py`
    is almost nothing on purpose: what a note needs that a studio document
    does not is where it lives and where it sits. Where it lives is one
    thread-local (`store.lib()`, with `store.use_library` to point it at a
    content's own `markdown/` directory) and one more for the mount
    (`server.base()` and `html_only()`); both are held per thread because the
    server is threaded, both are restored in a `finally`, and a thread that
    sets neither gets the studio, so the studio, the CLI and every test are
    untouched. The routes a note is served by are the studio's own, under
    `/books/<f>/<s>/notes/` and `/youtube/v/<id>/notes/`; the PDF, the
    LaTeX download and the build are refused there by the server. Where it
    sits is one line of its own front matter — `anchor: after sub <subkey>`,
    `anchor: before cap <start>` — read by `notes.py` and NOT added to
    `mdparser.FM_KEYS`, because that list is the dialect the prompt
    enumerates and no prompt may ask for a note. Notes travel in every shape
    of every bundle (`lib/bundle.py`, `NOTES_DIR`), because they are part of
    the content and not of the toolbox.
  - **A note says what it is before it is opened.** Resting the pointer on a
    note's mark for 350 ms, or giving it the keyboard's focus, shows a card
    (`#ntpeek`) with the note's title and the start of what it says, so a
    reader can tell whether to open it without leaving the line; leaving the
    mark, Escape, a scroll, a click or opening the note takes it away, and a
    device with no hover (`(hover: hover)` false) is not offered one at all
    — a tap opens the note, as before. The text is made on the server, as
    plain text, by `notes.excerpt`, and `notes.index` sends it with every
    mark on the request both readers already make to paint the marks, so a
    hover costs no request and neither reader carries a second markdown
    parser. What it keeps: each block as one line — a paragraph, a heading
    below the title, a list item as `• …`, a table row with its cells joined
    ` · ` — links as their text, and at most 280 characters, the `…`
    included, cut at a space; where the last space comes too early (a
    Chinese or Japanese note, one long word) it cuts between two characters,
    never between a letter and its combining marks or just after a virama.
    What it drops: the front matter, footnotes, figures and video lines,
    fences and rules, and the level-1 heading, which is the title shown
    above it. Italics follow the page's own rule for the note's `target`:
    with `target: fa` the asterisks of `*کتابِ من*` stay, as the page keeps
    them. The card is filled with `textContent` and nothing else, each line
    taking its own direction (`unicode-bidi: plaintext`), since a note beside
    a Persian video is as likely to open in Persian as in English — and
    textContent only because a note is a file that travels, in somebody
    else's bundle, and a preview is involuntary: it happens to whoever's
    pointer crosses the seam, where opening a note, which runs its page in a
    frame, is a choice. The two readers differ in one thing: the book's card
    can be moved onto and stays while the pointer is on it (150 ms of grace
    on leaving the mark), and the player's goes the moment the pointer
    leaves and lets every click through (`pointer-events: none`).
  - **The four colours are a fifth face of one table.** `red`, `blue`,
    `orange`, `green` — `\Cred`…`\Cgreen` in `lib/frank-preamble.tex`,
    `HL` in `lib/tex2html.py`, `COLOURS` in `lib/texwrite.py` and in
    `youtube/lib/check_annotations.py`, and the swatch names in
    `youtube/lib/player.js`; the smoke test reads two of them against each
    other so they cannot drift. A colour means **nothing to any tool** — the
    only thing a checker does with one is confirm it is one of the four, no
    Anki card carries one (a Colour field would fork
    every deck in the toolbox for a mark Anki cannot use), and in a book it
    reaches **pass 1 only**, the reader's own attempt before any help arrives.
    In a video it is the one chunk key nothing in the pipeline writes, which is
    why `merge_parts.py` drops it and why `CHUNK_FIELDS` puts it last.
  - **`lib/bundle.py`** is the way out and back: an allowlist of the authored
    files (never a blocklist, because everything under `books/` and
    `youtube/videos/` is served as a static file), a `parseh-bundle.json`
    manifest of which only `format` is believed on the bundle's word, unpacking
    into a staging directory *beside* the destination so every check runs there
    and the move into place is a rename, and a replace that carries across
    everything of the old directory's that *this* bundle did not carry — the
    PDF, the built reader, the build keys, and whatever of the narration the
    shape left out (below). The build keys are deliberately neither carried
    nor replaced, so the next `./build.sh` sees the new text.
  - **`lib/draft.py`** starts a book or a video from nothing but its text.
    Three cuts, and only two of them are made: into paragraphs (mechanical),
    into sentences (mechanical, at the script's terminators — a fact about
    scripts, so the class is written once and not per language), and into
    **chunks**, which is the editorial heart of the method and is left undone
    unless sense groups are asked for (`how="phrase"`, a first pass to
    correct). So a draft is one chunk per sentence by default: an addition to
    a blank page, never an argument with a guess. The two mechanical cuts are
    safe to get wrong in a way the third is not, since the fidelity checks
    join the chunks back together.
  - **A blank gloss is legal everywhere.** There is no flag: nothing writes
    `"draft": true` and nothing reads one an older version left behind. A
    chunk is *unglossed* when none of `tr`, `voc`, `en`, `kana` holds text,
    a reading still exactly as `wordline.seed` proposed it from the word line
    not counting (`check_batch.unwritten`, `check_annotations.unwritten`,
    `texwrite._unglossed`); it is *complete* when it is written and carries
    `en`, `tr` where the language `require_tr`s, `kana` where it has a
    reading — and there a seeded reading counts as present. `check_batch.py`
    and `check_annotations.py` count unglossed chunks in one note (*N of M
    chunks have no gloss yet*: per paragraph, per video) and ask nothing else
    of them — no required field, no length warning, no "no words" or missing
    `\vb` warning — and call a half-glossed chunk (written, not complete) an
    error: that is the half-done work the checkers exist to catch. Hand edits
    may fill one box at a time and may not empty a required box on its own
    (above); a cut or a join may leave either half blank or half glossed, and
    a blank Japanese or Chinese chunk divides into two blank halves, each
    with the reading of its own words. `lib/bundle.py` takes back a video
    with half-glossed chunks and says so in a note. Only an LLM's answer is
    held to the whole gloss — the add page refuses a half-glossed chunk, and
    `lib/glossregion.py` drops one — because nobody is looking at the chunk
    while it lands.
  - **What the server adds** is only the mapping: a book edit rebuilds
    `reader/index.html` (a `tex2html.py` subprocess, so a book that makes it
    raise fails one request and not the server) and answers `pdf_stale`,
    because nothing in a browser can run LaTeX; a video edit rebuilds nothing,
    the player assembling its page from the files on every request.
- **A book comes out in three shapes, and only a book.** The download used to
  be one zip and one sentence about it — *no PDF, no reader, no narration* —
  and that sentence was quietly false in the one way that matters: the zip
  left the recording behind but carried a `book.json` naming it, a
  `timings.json` beside it and a `% @par` comment above every subparagraph of
  every chapter, so what a person got was a book *claiming* a narration it
  had not got. `bundle.pack_book` now takes `audio`, one of `text`, `linked`
  and `full`, and the same three words carry the choice all the way through:
  the reader's download sheet, serve.py's `?audio=`, the CLI's `--audio`, the
  manifest's new field, and the sentence the upload panel says back.

  What the shapes made visible is **what a narration actually is**, which is
  wider than the two files `book.json` names. `bundle._narration` looks for
  all of it: the two fields, `timings.json`, `review.json`,
  `review-corrections.json`, `review.html`, everything in `audio/`, and the
  chapters carrying `% @par` lines — that last being the one a person forgets,
  because it lives *inside* a file every shape carries and is what the reader
  reads its times from (`tex2html.load_times`, not `timings.json`). So `text`
  is not a smaller file list: it is a transform. `book.json`'s two fields are
  set to `null` (not removed — absent and null are one answer, and a book with
  no narration must come out of all three shapes as the same bytes), and the
  `% @par` lines are taken out with the aligner's own pattern,
  `timestamp.AT_RE`, never a second spelling of it. Taking one out cannot move
  a glyph: a comment occupying a whole line is consumed by TeX with its
  newline, which is why the PDF and the reader are the same book either way.

  `review.html` is carried by **no** shape, and for none of the usual reasons.
  It is a *page*, and everything under `books/` is served as a static file, so
  a bundle able to carry an `.html` could put a script of its own same-origin
  with the reader. The allowlist is what stops it, exactly as it stops
  `main.pdf` — and the copy already in a book is left where it stands.

  **The manifest gained `audio` and `format` did not move**, the argument
  being the one the gloss language made above, run again and coming out the
  same way. It is a
  *shape* and never a path — `book.json`'s field of that name holds the file,
  this one holds the word — and it is written only for a book that *has* a
  narration; absent means `linked`, which is what every bundle written before
  the shapes is, those having carried the fields and the comments exactly as
  they stood. A toolbox that reads `parseh-bundle/1` and has never heard of a
  shape gets all three right: it installs a `text` bundle correctly, the
  cleaning being in the files and not in the field; installs a `linked` one as
  the bundle it would have written itself; and refuses a `full` one outright,
  its `MAX_UNPACKED` being 64 MB and a recording hundreds. Not one of them is
  quietly got wrong, which is the whole of what the field would have to be
  believed for. The cleaning therefore runs at **both** ends — pack writes the
  cleaned bytes, and install cleans the staged tree again before a single
  check touches it — because a bundle is a file a person may edit by hand, and
  what `text` promises is about the book that *lands*.

  **A shape says what is in the zip and never what to destroy at the far
  end.** Install deletes no part of a narration, ever. A `text` bundle
  uploaded over the book it came from keeps the recording, the timings and the
  review, and `book.json` is pointed *back* at what stayed (`_reattach`), from
  the old `book.json` and only where the file it names is still there: nulled
  fields beside a 219 MB file that is still sitting there is not a state any
  door here produces, and would be keeping the bytes while losing the
  narration. The asymmetry is deliberate — the text is in git and the
  recording is nowhere. The one thing that does not come back is the `% @par`
  comments, which are in the text the replace overwrote; the times are safe in
  `timings.json` and the answer names the command that writes them back
  (`timestamp.py --from-sidecar`).

  **A video has no shape and is not offered one**: its media is on YouTube and
  never here, and its timestamps sync its own transcript rather than naming a
  file that could be missing, so `pack_video` writes the bundle it always did
  and the player keeps its single button. **A book with no narration** has
  nothing to leave out, so the three are one bundle — the same bytes, the same
  filename, and no shape in the manifest at all, which is also what keeps such
  a book's zip byte for byte the one this door made before shapes existed. The
  reader keeps its plain link for it, a choice that cannot matter being worse
  than no choice.

  Two smaller things the recording settled. The size budgets are **counted
  apart**: `MAX_UNPACKED` still guards the text as before, so carrying a
  recording cannot become a way to smuggle four gigabytes of `source/*.txt`
  past a route that unpacks before it can check, and `MAX_MEDIA` is the
  recording's own, set where `serve.py`'s `MAX_AUDIO` already sets it. And a
  recording is **stored, not deflated**: measured on the 218 MiB `audio.webm`
  this was written against, deflating saves 0.061% for thirty times the work,
  a webm or an m4a holding nothing left for zlib to find. `bundle.AUDIO_EXTS`
  is a second copy of `serve.py`'s and has to be — the server imports this
  module, not the other way about — so the smoke test reads the two against
  each other, the way it already does for the four colours.

- **Files on disk.** `lib/langs.css` is generated (`languages.write_css()`)
  by `make_index.py` and at every server start, and git-ignored: the built
  readers and the library page link it relatively, so it must exist beside
  `parseh.css`; the server still answers `/lib/langs.css` itself. Three more
  directories are git-ignored, all three for one reason: what is in them is
  **somebody else's work under somebody else's licence**, fetched on request
  and megabytes to hundreds of megabytes of it, and the toolbox ships the
  doors and none of the content. `dict/*.db` (and the `*.jsonl` extract a
  build reads) holds the dictionaries, 21 MB for Persian to 342 MB for
  German among the seven built on this machine; `corpus/*.db` the
  parallel corpora, 3 MB for Persian–English, 83 MB for Spanish–English and
  182 MB for Italian–English, because Tatoeba's coverage is that uneven;
  `mt/` the WebAssembly engine and about 20 MB per language pair of
  Mozilla's models. A language or a pair with none of them has no lookup, no
  example sentence and no button, and nothing else about it changes — which
  is what makes ignoring them safe rather than merely tidy.
- **The preamble's hooks.** Beyond §6, a `lib/lang/<code>.tex` may define
  `\FrankChunkSep` (the glue between chunks in a rebuilt pass: a zero-width
  stretchable glue for Japanese and Chinese, a space elsewhere), `\FrankVbPres` /
  `\FrankVbPast` (the words the `\vb` line prints before its second and
  third forms — every language file sets them, `newlang.py --check` faults
  one that does not, and the registry's `vb_labels` is the same pair; each
  `docs/lang/<code>.md` names the three forms of its `\vb` in that order, as
  the registry's `vb_forms` does, so the printed labels and the annotator's
  slots agree, §3), and
  `\ifFrankHasVert` — when true, the last pass is `\FrankVertPass` (the
  rotated vertical box) and the font pass is suppressed. The vertical pass
  balances the sentence over as many columns as it needs at `\FrankVertColumn`
  (0.5\textheight), growing them towards `\FrankVertHeight` (0.78\textheight)
  only when the measure holds no more columns, so the box is only as tall as
  its share of text and follows the plain pass on the same page. The language files take
  their font names from `lib/languages.json` through Lua
  (`frank_reg_fonts` / `\FrankPickFont`, which walks `tex.main` and
  `tex.main_fallbacks` with `\IfFontExistsTF`), so no `.tex` names a font.
  `etoolbox` now loads before `xcolor` (needed for the font pick).
- **The gloss line is one line, in both editions.** A `\vb`'s two labels are
  the language's own — Arabic's *impf. / masdar*, Japanese's *stem / -te*,
  German's *pret. / p.p.* — and they are written once, in the registry's
  `vb_labels`: `lib/lang/<code>.tex` sets `\FrankVbPres` / `\FrankVbPast`
  from that pair for the PDF, and `texparse.parse_voc` takes the same pair for
  the reader, which is why the field is in the registry at all. The parser
  learns the language from `parse_book`, and remembers it (`texparse.set_lang`),
  the way `tex2html` remembers its `LANG`: a vocabulary field says nothing
  about the language that wrote it. The registry holds the word alone — the
  `\textit{-te}` in `ja.tex` is that page's typography — and
  `lib/newlang.py --check` and the smoke test compare the two spellings, so a
  book cannot label a form one way in print and another on screen; the
  reader leaves out a pair whose form is blank exactly where the PDF does
  (§3), for the same reason. The free-text slots (`\vb`'s meaning, `\bw`'s
  phrase) are parsed like the rest of the line, so the `\textit` a French
  past historic, a German stranded prefix and a Turkish segmentation are
  written with reaches the reader as italics instead of as source. And the
  transliteration is optional wherever `require_tr` is false, so `\glbodyr`
  guards that line with `\ifblank` as it already guarded the vocabulary: a
  chunk with no `tr` prints no empty line.
- **Digits and incipits.** The subparagraph buttons (`.lab`) of the reader
  stay in Latin digits for every language — a control you quote back, not
  text — while contents entries and chapter headings use the language's
  digits. For a language without word separators the incipit of a
  paragraph is its first twelve characters (`assemble.py`,
  `inject_parstart.py`).
- **Japanese fidelity.** Both pipelines compare a Japanese caption or
  paragraph with the chunks joined by nothing and *all* whitespace ignored
  on both sides (YouTube's Japanese captions carry spaces at phrase
  boundaries inconsistently); the player renders the line without those
  spaces. `check_batch.py` runs the Persian conventions (§3–8 of its
  checks) only for `fa`; Arabic gets the generic checks and nothing else
  until `docs/lang/ar.md` grows rules worth automating.
- **Tools' arguments.** `assemble.py`, `merge_batch.py`, `normalize_batch.py`
  (a no-op outside Persian, saying so), `apply_pointing.py` and
  `verify_book.py` take `--book` (or `$FRANK_BOOK`); `assemble.py`'s chapter
  label may be typed in Latin digits and comes out in the book's;
  `extract_pdf.py` takes `--lang <code>`. A LuaLaTeX-made Persian PDF has
  its text layer in visual order and cannot be re-extracted by
  `extract_pdf.py` (a scan or a XeLaTeX PDF can) — not a regression.
- **The player page.** `<html>` carries `data-lang` and `data-dir` and keeps
  `lang="en"` with no `dir`: a `dir="rtl"` on the root would mirror the
  whole chrome (header, cloud, dashboard). Every content element sets its
  own `lang`/`dir`. The transcript's duration line accepts `1分6秒` as well
  as `1 minuto e 6 secondi` (the conjunction became optional).
  `stats()["channels"]` counts distinct channels, `by_lang` counts a
  channel once per language it has videos in.
- **The studio.** For a script language the display-line rule (a paragraph
  of only script characters, ≥ 3 words) still wins over the auto block,
  exactly as for Persian; a Japanese paragraph becomes an auto target block
  only when ASCII punctuation or digits keep it from being a display line.
  Removing the last colour/translit mark from a Latin-target run writes it
  back as `[text]{tl}` (the run must stay marked). A run that is only part
  of a mark's content (`[速い 車]{kana:…}`, `[سلام! دنیا]{teal}`) is edited
  as the whole mark. A target-text block of an unspaced language keeps its
  ideographic spaces (U+3000) through the editor and the store. The verify line reads
  "N/N target strings correct". `envsetup` copies the bundled faces from
  `lib/fonts/` before it ever downloads. Studio PDF builds need `microtype`
  (added to `install.sh`'s package list).
- **Anki.** For a reading language the kana line sits under the text on
  both sides of the forward card (the reading editions show furigana in
  pass 1 too); drop `READING_LINE` from the question templates in
  `anki_export._localise` if the front should hide it — a template-only
  change, safe before the first Japanese notes are studied. The default
  deck name for a bare POST is "Parseh" (the dashboards always send one).
  The Persian model CSS keeps its historical `Vazirmatn, serif` stack so the
  Persian sheet stays byte for byte; the other languages use the registry's
  stack. Persian cards rewritten by a sync gain `lang: fa` and empty
  `kana`/`opp_kana` keys; untouched cards are never rewritten.
- **Glyphs the body face lacks.** The Italian pronunciation line (`ʎ ɲ ʃ ṡ`,
  the stress mark), a French one's nasal vowels and `ʒ`, and a scholarly
  transliteration's dotted letters are not in TeX Gyre Pagella. Every
  Latin-script language that writes IPA in `tr` meets the same wall, and
  the two answers below are keyed on the script, not on Italian, so a new
  one of them needs nothing done. The reading editions declare a luaotfload
  fallback (DejaVu Serif, glyph by glyph, only when the machine has it) on
  the roman in `lib/frank-preamble.tex`; the studio, which has no fallback
  under XeTeX, sets a lemma heading's transliteration line in `\trfont` —
  DejaVu Serif for a Latin-script target, the body face for the others — so
  the Persian PDF is unchanged. A missing glyph still shows in the `.log` as
  `Missing character`; `tests/smoke.py --pdf` does not count those, so look
  once when a new scheme adds letters.
- **Hyphenation patterns are a package of their own.** A language's
  `tex.hyphen` names babel's pattern set — `italian`, `french`, `ngerman`,
  `turkish`, `english`, `spanish`, one for every row whose `chars` is null,
  and null for the rows written in another script, which are not
  hyphenated — and TeX Live ships each as `hyphen-<the language
  in English>`, which is how `install.sh --pdf` gets the package names
  out of the registry without holding a list of its own. Without them
  `\babelprovide[import=de]` still succeeds — the locale, the quotation marks
  and the case pairs all arrive, only the patterns are missing — so babel
  writes `Hyphen rules for 'ngerman' set to \l@english` once into the `.log`,
  leaves `\language` at 0, and breaks the book at English points for the rest
  of the run: `Fre-und-schaft` for `Freund-schaft`, `print-emps` for
  `prin-temps`, `faleg-name` for `fa-le-gna-me`, `lächelte` never broken at
  all. The PDF compiles clean and the failure survives only in a log nobody
  opens, so `install.sh` checks the patterns reach `language.dat` (a package
  can be installed and still not reach it) and `build.sh` names the fallback
  beside the page count. The rows whose `tex.hyphen` is null — Persian,
  Arabic, Japanese, Hindi and Chinese — fall back to English in every log
  there has ever been and are unharmed by it: English patterns are made of
  ASCII letters, which none of the four scripts those five are written in
  contains, so no break point is ever found — which is why neither tool warns
  about them.
- **Tests.** `python3 tests/smoke.py` (add `--pdf` for the LaTeX builds)
  is the regression run: fixtures under `tests/fixtures/` (an edition, a
  video and an Anki card per language, and eight verb cases per language
  under `tests/fixtures/verbs/`, which `--only verbs` runs with no
  dictionary installed).
