---
title: Glossary
weight: 6
description: The words Parseh uses — chunk, gloss, seam, run, level, shape, jolly card and the rest — each in a sentence or two.
---

The words the pages and this guide use in a sense of their own, grouped
by where you meet them and in alphabetical order inside each group. The
search box finds any of them.

## Languages

Gloss language
: The language a book's or a video's glosses are written in: `"gloss"` in
  its `book.json` or `video.json`, English when it says nothing. An
  Italian learning English reads an English book glossed in Italian.

Prose language
: The language a studio document is written in — its front matter's
  `lang:`, English when absent. It decides where the PDF may break a word.
  A Japanese lesson written in Italian has `target: ja` and `lang: it`.

Registry
: `lib/languages.json`, the one table that says what each of the eleven
  languages is: its code, its folder, its script and direction, its
  fonts, the passes of its books, its Anki note types. Nothing else in
  Parseh holds a list of languages. A language added on this machine has
  its row in `config/languages.json`, read after it.

Target language
: The language being learned: `"language"` in a `book.json` or
  `video.json`, `target:` in a studio document's front matter, one of the
  registry's codes (`fa`, `ar`, `it`, `ja`, `fr`, `de`, `tr`, `en`, `hi`,
  `es`, `zh`). Content that names none is Persian, the toolbox's first
  language.

## Books and videos

Alignment
: Finding where each subparagraph of a book is in its recording, so that
  the page follows the voice. **align** does it against a transcript;
  **estimate times** shares a recording out over its text in proportion to
  length, a first guess to nudge by ear.

Bundle
: One zip holding a book's or a video's authored files and a manifest,
  `parseh-bundle.json`, that lets another Parseh check it: what
  **download** makes and **Bring a book back** (or a video) takes. Never a
  PDF or a built reader — those are made again from the text.

Caption
: One line of a video's transcript, with its start time. A **plain**
  caption is one that is not glossed — a line in the video's own prose
  language, say.

Chunk
: The unit a text is cut into: a few words that are read, glossed and
  played as one. In a book, one `\ch` call of a chapter; in a video, a
  piece of a caption. Its words joined back must give the text exactly.

Colour
: A chunk may carry one of four: red, blue, orange or green — the
  reader's own mark, chosen in the chunk's sheet (in the player, with the
  four dots of its gloss cloud). In a book it shows on the first level only.

Diacritics
: The small marks that write a Persian or an Arabic word's vowels, its doubled
  consonants and its silent stop. **Diacritics**, a switch in the ⚙ panel, puts them
  away from what is drawn — the first two levels of a book, the lines of a video — and
  nothing else ([Levels and their names](../books/levels.md#diacritics)).

Draft
: A book or a video started from its text alone — **Make the draft** on
  the add-a-book page, **Start it empty** on the add-a-video page: the text
  cut into chunks, every gloss blank. Nothing marks it as a draft
  afterwards; it is an ordinary book or video with unglossed chunks.
  (`./build.sh --draft` is something else: a PDF of a few chapters, fast.)

Fidelity
: The rule that a book's chunks, joined, still say what its source
  paragraphs say, and a video's what its captions say — so that nothing
  quietly rewrites a text. Vowel marks aside, an edit that breaks it is
  refused — unless the book's paragraph, or the video's phrase, is ticked
  as free to depart (**this paragraph need not reproduce `source/paras/`**,
  **this phrase need not reproduce `transcript.txt`**).

Gloss
: What a chunk carries besides its text: the transliteration, the
  vocabulary line (the words one by one, a verb with its principal parts)
  and the meaning, which says what *that* chunk's own words say, in the order
  of the text, and is not a translation of the sentence
  ([What the meaning says](../books/glossing-with-an-llm.md#what-the-meaning-says)).
  **delete gloss**, in the chunk sheet or the player's
  ✎ form, takes all of it off at once. In the studio, `word = *meaning*`
  is a gloss, and the document's **⇄ Glosses** table collects them.

Half-glossed chunk
: A chunk with some of its gloss written and something its language
  requires still empty — a meaning with no transliteration beside it, in a
  language that romanises every chunk. The chunk sheet and the ✎ form save
  one on the way to a whole gloss; the checkers list it as an error until
  it is finished, and an LLM's answer never writes one.

Level
: One way of setting a book's text: the sentence whole, the chunks with
  their glosses, the text without its vowel marks, a second face, the
  text set vertically. Each language has its own list, and its own names for them —
  **With vowels**, **Chunks**, **Plain**… — which a person can change; the buttons in
  the reader's header switch them on and off. (The registry and the files call
  them *passes*.) [Levels and their names](../books/levels.md).

Narration
: A book read aloud. It is a list of **recordings**, each covering a
  stretch of the text and timed in seconds into its own file, so a book
  can be recorded a few chapters at a time. The **narration** panel in the
  reader holds the list.

Reader
: A book's web page, built from its chapters by **build**. What a reader
  can do is written into it when it is built, which is why an old one
  gains a new feature only with **rebuild the reader**.

Review later
: A flag on a chunk of a book or a phrase of a video, put there without stopping
  — the cloud's **review later**, the **L** key, **⚑**, a held finger — so that its
  card can be made, or the chunk gone back to, later. The flags are yours, kept by
  the computer, and never written into a book ([Review later](../books/review-later.md)).

Seam
: The gap between two lines of a book or a video. A `+` there writes a
  **note** into it: a studio document kept with the book or the video,
  marked in the seam and opened over the page, never shown inside the
  reading.

Shape
: Which of three downloads a narrated book is: **the text alone** (no
  sign of a narration), **everything but the recording** (all of the
  narration but the audio file: put `audio/` back and the book is whole)
  or **all of it**. On the command line, `text`, `linked` and `full`.

Shelf
: A door's collection — the book library, the video index. **✕** takes an
  item off the shelf into a `.trash/` folder, from where it can be moved
  back.

Source paragraphs
: `source/paras/`, the text a book was made from, one file a paragraph:
  what its chapters must go on reproducing.

Subparagraph
: The unit a narration is timed by, labelled by its chapter and place
  (`1.2`), the unit the reader plays and the cut editor cuts from.

Transliteration
: A chunk's sound in Latin letters, by each language's own scheme. For
  Japanese there is also the **reading**, in kana; for Chinese the pinyin
  is the transliteration.

Unglossed chunk
: A chunk with nothing written in its gloss (in Japanese and Chinese, a
  reading still as it was proposed from the words does not count). Legal
  in every book and every video, for as long as it stays so: the checkers
  count such chunks in one note (*3 of 12 chunks have no gloss yet*), and
  **gloss with an LLM** fills only these.

Word line
: For Japanese and Chinese, which write no spaces, the chunk divided into
  words, each with its reading: `山(やま) へ 柴刈り(しばかり) に 、`. The
  machine proposes it; the **word strip** in the chunk editor corrects it.

## Cards and Anki

Card sheet
: What an Alt-click (or Ctrl-click) on a word opens in a reader or the
  player: a card already filled in from the word, which its *to* row sends
  to **Anki**, to an **exercise deck**, or to the clipboard as
  **markdown**.

Card store
: `youtube/anki/`, where the cards made in the readers and the player
  wait, one file a card, until they are built into a deck for Anki.

Clip tray
: `clips/`, where a recording cut from a narration or a film, and a frame
  captured from a video, wait until a card, a deck or a document takes a
  copy. **The clip tray** on the hub plays and deletes them.

Jolly card
: A flashcard whose two sides are entirely yours: each side has a main
  text and a smaller one under it, and each of the four takes any studio
  markdown — paragraphs, lists, tables, pictures, recordings. Beside it
  are the **vocabulary** card (a word, its reading, its meaning) and the
  **opposites** card (a word and its opposite). Anki has no jolly note
  type, so a jolly card goes to an exercise deck or into a document.

Sync
: Bringing the edits you made inside Anki back into the card store, from
  an export: the **Anki** page on the hub. Always before a rebuilt deck is
  imported, or the import overwrites them.

## Reading help

Corpus
: Sentences somebody wrote and somebody else translated (Tatoeba's),
  kept per pair of languages and offered when they share the rare words
  of a chunk.

Machine's reading
: A translation model's reading of the sentence a chunk is in, run in the
  page itself, with the chunk's share of it marked — a guess, and drawn as
  one.

Reading help
: What helps with a chunk nobody has glossed: a dictionary, sentences
  somebody translated, a machine's reading. All three are got on the
  reading-help page, in Settings, with **Get it**; none of them is a gloss, and none goes into
  a book unless you put it in the chunk's fields and save.

Sources sidebar
: **⊕ sources**, beside the fields of the chunk editor: the reading help
  for the chunk being edited, with buttons that put a romanisation, a
  sense or a whole entry into the fields — for you to correct and save.

## The studio

Block
: A stretch set apart as a unit: a target-language block
  `[ … ]{tl}` (right to left for Persian and Arabic, vertical for Japanese
  and Chinese when asked), or a `{la}` block of prose-language text with
  its own width, side and tint.

Box
: Lines starting with `>`: a tinted panel that may hold anything the
  document can.

Display line
: A paragraph made only of the target language's script, set large and on
  its own line.

Document
: A studio page: Markdown in the studio's dialect, with a front matter
  (`title`, `subtitle`, `note`, `lang`, `target`), read on screen or built
  into a verified PDF. A **note** in a seam is one too.

Id and uid
: A document's two permanent identifiers: its folder's id (made from its
  first title, never changed) and a twelve-character uid in `meta.json`.
  Links used to name the uid; they now name the document by its **name**.

Lemma heading
: A `##` heading that is a dictionary entry: the headword in the target
  language, its transliteration, its etymology and, if you like, its
  meaning — `## کتاب | ketâb | Arabic kitāb | = *book*` — set very large.

Link by name
: `[label](doc:Name)`: a link to the document of the same library whose
  title is *Name*. Renaming that document rewrites the link; deleting it
  leaves the link **dead** (red and dashed) until a document of that name
  exists again. **↩ Linked from** on a document's page lists what links to
  it.

Name
: A document's title, which its links spell. No two documents of one
  library share one: a save or an upload that would take a name already in
  use opens the *This name is already in use* dialog.

Run
: A stretch of target-language text inside prose. In a script language
  (Persian, Arabic, Hindi, Japanese, Chinese) it is found by its script;
  in a Latin-script one it must be marked, `[bello]{tl}`, since nothing
  tells it from the prose.

Starter
: The page **+ New** opens in each language: a tour of everything a
  document can hold, in English with examples in that language, with a
  picture and a recording that become the document's own when it is
  saved.

Tategaki
: Japanese (and Chinese) set vertically, in columns from the right:
  `[ … ]{tl vertical}` in the studio, a level of its own (**Vertical**) in a book.

## Exercise decks

Cram
: Going over selected exercises in random order, a wrong one coming back
  until it is right — without changing their schedule.

Deck
: A collection of exercises in one language, studied like Anki cards:
  each comes back when it is due. Exercises come from a document's
  **+ Deck**, from a card sheet, or from the deck's own **Add exercise…**.

Ease, interval, lapse
: The scheduler's terms, Anki's own: the **interval** is how long an
  exercise waits; the **ease** multiplies it after a good answer (2.5 to
  begin with); a **lapse** is a review answered **Again**, which lowers the
  ease and sends the exercise back to relearning.

Exercise
: A `:::exercise` block in a document, one of fourteen kinds — filling
  blanks, putting sentences in order, building a sentence from chunks,
  three kinds of matching, yes-no, true-false, single choice, finding the
  wrong part, choosing all that apply, the odd one out, flashcards, and the
  follow-up, a chain of the others answered one after the other.

New, learning, review
: The states of an exercise in a deck: never studied; going through its
  first short steps (minutes apart); graduated to waits of days.

## The toolbox

Browser | Mobile
: The switch in the hub's top bar. **Browser** is every page as it has
  always been; **Mobile** is a streamlined set of pages for reading on a
  phone, with no editing on them: so far the hub, the books (a shelf, and
  every reader) and the exercise decks. It installs on a phone as an app
  (**As an app**, on the mobile hub).

Door
: One of the ways in on the hub: Books, Videos, Studio, Exercises, and
  the wide ones below them — Anki, the clip tray, the reading help.

Environment
: The packages Parseh uses beyond Python itself, in one environment
  called `ilya-frank`: in Parseh's folder, `.runtime/env`, when the
  installer made it, or wherever your conda keeps it.

Hub
: The first page, `https://localhost:7654/`: the doors, the language
  chips, the **guide** button.

Going back
: Installing an older version in place of the one you have, from
  **Settings → Updating Parseh**: the same update, the other way, never
  presented as an ordinary one. It is how a release that went wrong is
  escaped ([Updating Parseh](../getting-started/updating.md)).

Language chips
: The row of languages on the hub and on each door's page. Behind a door
  they filter what is listed; on the hub they choose the language the doors
  open with and count for. One setting for the whole toolbox.

Release
: One version of Parseh as it is given out: a zip, `parseh-<version>.zip`,
  on GitHub's releases page, holding the program and a list of its own
  files with a checksum for each (`.parseh-release.json`). Parseh is
  installed from one, and updated from one
  ([Installing Parseh](../getting-started/installing.md#getting-parseh)).

Version
: Which Parseh this is — `a` for alpha, then three numbers — written in
  `VERSION`, at the foot of the hub and on **Settings**. [What changed,
  version by version](whats-new.md) says what each brought. A rehearsal,
  made before a version is released, adds `-rc` and a number (`-rc1`):
  Parseh counts it as coming before the version it rehearses, and
  **Settings → Updating Parseh** names it so on an install made from one.

Working…
: The pill in the corner of every page, and the panel on the hub, that
  says what the server is doing — a build, an upload, a download being
  packed — until it is over.
