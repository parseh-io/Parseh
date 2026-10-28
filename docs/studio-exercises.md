# Studio interactive exercises

Studio exercises live in the Markdown source and render interactively in the web reader. They use one fenced container and four primitives: placement, choice, matching, and embedded flashcards; a fifth, the follow-up, is a chain of the others (see *Follow-up questions* below). The subtype on the opening line records the pedagogical purpose explicitly.

```markdown
:::exercise single-choice
prompt: Which answer is correct?
- [ ] An incorrect answer
- [x] The correct answer
explanation-correct: This appears after a correct answer.
explanation-incorrect: This appears after an incorrect answer.
:::
```

Explanations are optional. If only `explanation-correct` is present, that one text is shown neutrally after either result. If `explanation-incorrect` is present, the result selects between the two texts: the correct text after success and the incorrect text after an error. Either result-specific field may be empty. The earlier single `explanation` field remains readable as a neutral explanation.

The normal reader starts exercises unsolved. A single **Check exercises** button appears at the end whenever the page has at least one scored exercise. It scores exercise blocks equally, marks individual answers or positions, and reveals explanations. Changing an answer clears that exercise's old result and hides the page score until it is checked again. The editor preview instead shows the stored solution. Its **Edit** button reopens the exact source block.

**Mathematics** is `[a^2+b^2=c^2]{math}`, in any field that carries prose — a prompt, a fill sentence, an answer row, a pair, a card. LaTeX notation; neither `$` nor `\[` is a marker here. The body may hold brackets, since the mark is read up to the `]{math}` that closes it. A blank may not sit *inside* a formula (`[[slot]]` cuts a sentence into pieces and half a formula is nothing) — put it beside one. The exercise form has a **∑ Maths…** button that writes into the field you were last in, with the formula drawn as you type it.

**A LaTeX drawing** (`[…]{latex theme}` in a line, `::::latex theme` … `::::` as a block) goes in an exercise the way it goes in a document, with one rule for the block: it is part of a FIELD, never a line of the exercise's own, because an exercise's lines are fields (`name: value`) and rows (`- …`). A block stands in a prompt written `prompt: |` (its lines, the drawing's fences too, indented under it) or in one of a Jolly card's four fields; written between the fields (after a one-line `prompt: …`, among the rows) it is ONE error, `mdparser.DRAWING_PLACE` (`DRAWING_PLACE_CARD` for a flashcard), and its lines are passed over to its closing fence rather than each being an `unrecognized line`. The exercises' prompt (`EXERCISES_PROMPT.md`, under the LaTeX box) and so the skill teach it with an example that `tests/test_latex_in_prompts.py` parses.

All exercise text accepts the existing inline dialect. Use `[target text]{tl}` where the target language needs an explicit mark. The renderer gives target runs their registered `lang` and `dir` and keeps them isolated inside the surrounding prose. `[text]{rtl}`, `[text]{la}`, colors, readings, transliterations, links, and other existing inline forms work as they do elsewhere.

Prompts are bold by default. Wrap a passage in `[…]{no-bold}` to set only that passage in regular weight, in both the web reader and PDF. The wrapper can contain a target-language mark: `[[دیروز دو شنبه بود.⏎امروز سه شنبه است.]{tl}]{no-bold}`. For RTL targets, a target-language line in a prompt is right-aligned in the PDF, including its last line; the instruction before it keeps its normal alignment.

For RTL languages, keep a continuous phrase or sentence in logical order inside one target-language run. A different rule applies when an LTR question, answer, derivation, table cell, explanation, or flashcard field contains several separately isolated RTL components. Each component then behaves as one visual box, so write those boxes in their intended left-to-right screen order while leaving the text inside each box untouched. For example, the Persian analysis read from the right as `dān + -eš + -gāh` must be authored for an LTR answer as `[گاه]{#6B6B1A translit:-gāh} + [ش]{#C28E0E translit:-eš} + [دان]{translit:dān}`. This applies to any LTR separator or surrounding prose, not only `+`.

## Pictures

Every exercise but a flashcard may carry two pictures of its own (a flashcard has its sides' `front-image` and `back-image` instead, and says so if one of these is written on it):

```markdown
:::exercise single-choice
prompt: Where is the market?
image: images/map.png
image-answer: images/map-answered.png
explanation-correct: The market is north of the river.
- [x] North of the river
- [ ] South of the river
:::
```

`image` is shown between the prompt and the activity. `image-answer` is kept back until the learner has answered, right or wrong, and then appears above the explanations — on the page, on the study page of a deck, and shown from the start in the editor's preview, which draws an exercise solved. Changing an answer hides it again with the rest of the result.

Both name a file under `images/`, as a document's figures and a card's pictures do (`images/name.png`, also `.jpg`, `.svg` or `.pdf`, which is drawn through the twin the studio makes of it); any other value is an error. Each may carry the layout a figure line carries, in the same words — `image: images/map.png {width=45 align=center}` — where `width` is a percentage of the text column (5 to 100) and `align` is `left`, `center` or `right`. Said nothing, a picture is drawn as a figure written without them is: 60% of the column, on the left. Screen and paper place it alike. The printed PDF has the question's picture inside the exercise box, under the prompt, and nothing of the answer's: on paper the exercise is unsolved, as its answers and explanations are.

A picture can also appear inside an exercise's prompt, answer, matching pair, sentence, explanation, or flashcard text. Write it as `![description](images/name.jpg)` in that text. For example, a matching row can be `- ![snow](images/snow.jpg) => [برف]{tl}`. This works in every exercise type, including pictures on either side of a matching pair; the picture travels with the exercise when it is copied into a deck.

**And two recordings, on the same terms.** `audio:` plays with the question, `audio-answer:` once the exercise has been answered — the picture pair over again, in the same two places and held back on the same rule (a flashcard has its sides' `front-audio` and `back-audio` instead, and says so if one of these is written on it):

```markdown
:::exercise single-choice
prompt: What does she order?
audio: audio/cafe.mp3 {start=1:05.2 end=1:09}
audio-answer: audio/cafe-slow.mp3
- [x] A coffee
- [ ] A tea
:::
```

Both name a file under `audio/`, as a card's recordings and a document's recording lines do (`audio/word.mp3`: MP3, M4A, AAC, Ogg, Opus, WAV, FLAC or WebM); any other value is an error. Each takes the picture's layout in the same words — `{width=45 align=center}` — and, because a recording has one more thing to say, the clip a recording line takes: `{start=1:05.2 end=1:09}`, in clock time or seconds. A player laid out with a clip plays that stretch and no more. It is a player with its controls, not a card's 🔊: an exercise's recording is listened to again, wound back and stopped, while a card's is one word played once. Nothing plays by itself — a recording is there to press, as a picture is there to look at — and whatever is playing stops when the answer is changed or the study page moves on. The printed PDF has the question's recording inside the exercise box as a card saying which file it is and which stretch of it, since paper cannot play it, and nothing of the answer's.

Add `content-direction: target` when the complete interactive area should follow the learned language's direction. Explicit `content-direction: rtl` and `content-direction: ltr` are also available, and an explicit setting is never overridden by anything below.

## Placement

Fill blanks by naming slots in `text:` and giving each slot one answer. Rows with an empty mark are distractors.

```markdown
:::exercise fill-blanks
prompt: Complete the sentence.
content-direction: ltr
text: I [[verb]] the [[noun]].
- [verb] read
- [noun] book
- [ ] write
:::
```

**A blank may sit inside a target-language mark**, so a sentence of the
learned language is written as one sentence:

```markdown
:::exercise fill-blanks
prompt: Complete the phrase below using the correct option.
text: [من بابک [[slot]]]{tl}
- [slot] [هَستَم]{tl}
- [ ] [است]{tl}
- [ ] [هَست]{tl}
:::
```

A mark's content holds no brackets, so the mark is spread over the pieces
round each blank when the document is parsed — `[من بابک]{tl} [[slot]]` —
and every renderer sees marks it already understands. A blank at the very
start is written the same way, `text: [[[slot]] شُما چیه؟]{tl}`: the first
bracket opens the mark and `[[slot]]` is the blank.

**Such a sentence is laid out in its own language's direction**, on the page
and on paper alike, without `content-direction`. A run of Persian inside a
left-to-right line is one box in a left-to-right row of boxes, and a blank
after it would be drawn to its right — which reads as the blank coming
first. A sentence that is the target's throughout — every run of it marked,
or nothing in it but the target's own script — is laid out right-to-left
instead, and the blanks fall where they are read. Mixed sentences are
untouched, and so is an exercise that sets `content-direction` itself.
In a PDF, an RTL fill sentence is also right-aligned as a whole paragraph,
including its final line; `content-direction: rtl` requests this for mixed
sentences too.

`order-sentences` and `construct-sentence` use numbered rows. Their source order is the correct order; numbers make that answer explicit. The reader shuffles the blocks.

For `construct-sentence`, the answer row flows from the target language's direction by default, and wrapped lines start at the same side. Use `answer-direction: rtl` or `answer-direction: ltr` to override that flow for a particular answer. This controls the order and wrapping of the movable chunks separately from `content-direction`, which controls the writing direction of the whole activity.
Older right-to-left exercises that reversed their numbered positions to work around the former left-to-right answer row should be renumbered in reading order.
In the exercise editor, **Reverse order** flips all words or chunks in a construct-the-sentence answer at once. Use it to correct an answer that was entered in the opposite reading order; the saved position numbers update with the new order.

**Every block to be ordered carries two arrows**, and each moves it one place. They are the way through where dragging will not do — a drag a touch screen never reports as one leaves the block where it was, or drops it at the end of the line — and the way through from the keyboard, where Tab reaches them and Space or Enter presses them. The block at either end of the order has the arrow it cannot use dimmed. Which way an arrow points is the activity's: **↑** and **↓** in a list of lines, **←** and **→** in a line of chunks, and the other way round where that line runs right to left, so the arrow always points where the block will really go. What an arrow does is what a drag does — the order is the answer — so a block moved with one unsettles the mark the exercise was given, exactly as dragging it would. **Where the pointer is a finger, dragging starts turned off** and the arrows are the only thing that moves a block: a phone reports a drag as a drag only sometimes, and a tap that is read as one puts the block at the end of the line. That is a guess about the machine, so every such exercise carries a switch in its head — **✥ dragging on** / **✥ dragging off** — which says which it is and changes it, on a document's page and on a deck's study page alike (it is the same switch as **Drag to answer** in the page's ⚙ panel, **Exercises** group). What it says is remembered for every page that browser opens afterwards (and, where the browser keeps nothing — a private window — for as long as the page is open). Dragging, tapping a block and then its destination, and the arrows are three ways to the same thing; the switch governs the first two, the arrows are always there, and **an exercise with no arrows — blanks to fill, pairs to match — is never touched by it and can always be dragged**. Those two have a fourth way instead, **the place first**: a click (a tap) on a blank or on a match's place opens a cloud beside it with a copy of every block the bank holds, and a click on one puts it there, exactly as a drop would; a filled place's cloud can also empty it, and Escape or a click elsewhere puts the cloud away. A place clicked while a block is picked takes that block and opens no cloud. The mobile interface has the cloud alone: its bank is there to be read, never picked up or dragged.

```markdown
:::exercise construct-sentence
prompt: Build the sentence.
answer-direction: rtl
- [1] [First block]{tl}
- [2] [second block]{tl}
- [3] [last block]{tl}
:::
```

## Matching

`match-translations`, `match-opposites`, and `match-definitions` share the matching engine. Each row is `left => right`; write `\=>` for a literal arrow inside an item. Translation and definition exercises may record `direction: target-to-translation`, `translation-to-target`, `word-to-definition`, or `definition-to-word`.

```markdown
:::exercise match-definitions
prompt: Match each word with its definition.
direction: definition-to-word
- A young cat => kitten
- A young dog => puppy
:::
```

## Choice

`single-choice`, `incorrect-part`, and `odd-one-out` require exactly one `[x]` row. `choose-all` accepts one or more. `yes-no` and `true-false` store one statement and answer on each `=>` row.

```markdown
:::exercise true-false
prompt: Decide whether each statement is true or false.
- The first claim from the page => true
- The second claim from the page => false
:::
```

```markdown
:::exercise choose-all
prompt: Choose every valid translation.
- [x] First valid answer
- [ ] Distractor
- [x] Another valid answer
:::
```

## Embedded flashcards

Flashcards flip in place and never affect the exercise score. A click anywhere on a card turns it, except on something that does its own thing there: a player, a link, a button (the 🔊 among them), a form control, a footnote's mark or its cloud. Enter or Space turns a card that has the focus, and turning a card stops whatever was playing on the side that goes out of sight. **⤢ Enlarge** in a card's head opens the same card in a window over the page, only bigger: it is laid out exactly as the card on the page — at its width, in its text size, with the page's typography and the exercise's direction, so every field sits where it sits there (a right-to-left paragraph on the right, a Latin block justified or set to its side, a field of several blocks from the start of its lines), every line breaks where it breaks there, and its pictures and players keep their size beside the words — and then magnified whole, as much as the window holds: the whole card, the taller of its two sides deciding, and at least half as large again where the screen has the room; a card taller than the window is drawn at that size and scrolls. On a phone, where the card on the page already takes nearly the whole width and magnifying it whole would make it only a third or so larger, it is laid out narrower than on the page instead — every field, picture and player as it is there, in the page's text size — and magnified to the window's width: as much as the window's height holds, up to twice as large, never so much that anything sticks out of the card or that a picture or player comes out narrower than on the page (a figure's width is a share of its field's, and a picture or recording as wide as its field narrows with it), and never so much that a line breaks that is whole on the page. A field, a paragraph or a line of a Jolly field (up to its `⏎`) that is one line on the page is one line enlarged; only a paragraph that already wraps on the page may wrap at other words. Where that would make the card hardly larger — less than a tenth — than magnifying it whole, it is magnified whole, as far as the window's width allows, every line as on the page; so is a card too tall for the window even then, which scrolls. A footnote's cloud on the enlarged card is drawn at the size it has on the page, over its mark, and kept inside the window: under its line when there is no room above it, moved along its line when it would stick out at a side. A click on the enlarged card, Space or Enter turns it — and the card on the page with it — and Escape closes the window. Every flashcard has the button: in documents and notes, in a deck's list, on the study page and in the editor's preview. `card-type: vocab` supports `target`, `reading`, `transliteration`, `meaning`, `context`, `notes`, `source`, `front-image`, `back-image`, `front-audio`, and `back-audio`. `card-type: opposites` supports the target fields plus `opposite`, `opposite-reading`, `opposite-transliteration`, `notes`, and the same four picture and recording fields. Images use the same `images/name.ext` paths as document figures. `direction` may be `forward`, `reverse`, `both-random` or `both-repeat` (anything else needs attention): `reverse` shows the back first; `both-random` draws the side shown first each time the card is shown, in `bindExercises` (app.js `drawFirstSide`) so that an export, a study pack and a cached page draw it too; `both-repeat` shows the front first, says in the exercise's head, right after the kicker (`.ex-card-note`, small grey sans, off the card; a line of its own under the head's buttons where the head is under 32em wide), that a deck will ask both sides — never in a deck's own drawing (`render_document(in_deck=True)`) nor in an exported page (`export=True`, webexport) — and becomes two linked cards when put into a deck; paper prints every value but `reverse` front first, with no note. `bidirectional` on an older card is kept and changes nothing.

**Where a vocab or opposites card draws `context`, `notes` and `source`** — on an opposites card, `notes` and `source` — is the side the flip reveals, the answer: the back of a card that shows its front first, the front of a `reverse` card, which therefore opens on its meaning alone (`mdparser.card_extras` is the one rule, read by `htmlgen`, `texgen` and the page's draw; each side puts them after its own fields, in the order context, notes, source). `context-side`, `notes-side` and `source-side` say `answer` (the default, which the exercise form never writes) or `question`, the side shown first, for one field each, in any case; any other value needs attention (`notes-side must be answer or question`), on a Jolly card too. A `both-random` card is composed forward and its extras carry `data-extra`, which `drawFirstSide` moves to the other side when the draw shows the back first; a deck's `both-repeat` pair is two cards, each by its own direction; paper prints `both-random` front first, so there they stay on the back; pictures and recordings stay on the side that names them; a custom `back` replaces all three (so none is drawn), a custom `front` keeps them; a Jolly card has none. In the exercise form, the **Text appearance** of each of the three fields holds a box, **Show on the side shown first**, which writes `<field>-side: question` and nothing when it is not ticked. A `reverse` card written before this, with a context, notes or source, now has them with the word; `question` on each puts it back as it was.

A card with a `transliteration` or `opposite-transliteration` field shows **Hide transliterations** in its head. Pressing it hides those fields on every exercise flashcard in the current view, including cards in documents, deck previews and study. The button changes to **Show transliterations** to restore them. The choice is remembered across exercise pages in the same browser. Readings and other secondary fields remain visible.

`front-audio` and `back-audio` name a recording under `audio/`, as a document's recording lines do (`audio/word.mp3`: MP3, M4A, AAC, Ogg, Opus, WAV, FLAC or WebM); any other value is an error. On its side the picture comes first, then the recording, then the text. The recording shows as a 🔊 button: a click plays it, a second click stops it, and it never turns the card. Only one card recording plays at a time. The printed exercise has ♪ and the file's name after `Front:` or `Back:`.

The Jolly type has two fields per side:

```markdown
:::exercise flashcard
card-type: jolly
front-primary: [primary front]{tl}
front-secondary: secondary front
back-primary: primary back
back-secondary: secondary back
front-primary-size: 130
front-primary-shade: primary
front-secondary-size: 90
front-secondary-shade: subdued
:::
```

Every flashcard field accepts a matching `-size` value from 50 through 250 percent and a `-shade` value of `primary`, `subdued`, `muted`, `accent`, or a `#RRGGBB` color.

A Jolly field may span as many lines as it needs, and **a card draws what it says the way the page draws it**: paragraphs, lists, tables, `>` boxes, `###` headings, lemma headings, target-language blocks with their direction, face, tint and tategaki, Latin blocks with their width and side, display lines, pictures, recordings, videos, glosses, colour and reading marks, and footnotes. A side needs one of its two fields.

There are two ways to write a field over several lines. Either `key: |`, then its lines indented under it — what the form writes — or simply going on: the lines under a field, until another field, an answer row or the closing `:::`, belong to it.

```markdown
:::exercise flashcard
card-type: jolly
front-primary: 今日は
いい 天気ですね
back-primary: |
  It is **fine weather** today.

  | word | meaning |
  |---|---|
  | 天気 | weather |
:::
```

Line breaks inside a paragraph join, as they do everywhere in the dialect: write `⏎` for a break, or a blank line for a new paragraph. A field of one paragraph keeps the card's own size and place; a field of several blocks, or of a table, a list or a box, takes the card's width at the page's text size. A card has no answer rows: a line starting with `-` is refused rather than dropped, so a list goes inside a field.

Two things a card's fields do not offer, because a page does not offer them either on such a block: the hover tools (a word's colour, a reading, a target or Latin block's editor) reach a field's words only while it is one paragraph of prose.

```markdown
:::exercise flashcard
card-type: jolly
front-primary: |
  ### [ciao]{tl}
  ![](audio/ciao.mp3)
front-secondary: said on arriving and on leaving
back-primary: |
  **hello**, and **goodbye**.

  | on arriving | on leaving |
  |---|---|
  | [ciao]{tl} | [ciao]{tl}, [arrivederci]{tl} |
back-secondary: |
  > Familiar: to a stranger, [buongiorno]{tl}[^formal].

  [^formal]: Or [arrivederci]{tl}, on leaving.
:::
```

A field that is one plain paragraph is drawn as a line of text, exactly as a one-line field is. Anything else is drawn as its blocks. A heading on a card is not numbered and is not in the contents. A footnote written on a card is one of the document's notes. A recording on a card is an ordinary player; a click on it plays it and does not turn the card. A field cannot hold another exercise, and a line that is only `:::` ends the exercise, however far it is indented.

Two things a card does not offer. A picture, recording or video on a card has no layout panel, so its size and place are written by hand. A field drawn as blocks is not offered to the hover tools: no colour palette, no transliteration cloud, and no editor on its target or Latin blocks. A field that is one plain paragraph keeps them.

The editor's **Exercises ▾ → Add exercise…** opens a visual form for every supported type. Every type but a flashcard has a **Pictures (optional)** section with the two picture fields above, each with its own **Upload…** and, under **Size and position**, its width in percent of the column and the side it sits on, and a **Recordings (optional)** section with the two recording fields, each with the same **Upload…** and, under **Size, position and clip**, the same width and side plus **Play from** and **Play to**. The preview below plays them, so the recording fields need no ▶ of their own. Its labels describe what the learner sees; repeatable answers, pairs, sentence parts, blanks, and segments have controls for adding, deleting, and reordering them. The **Edit** control on an exercise in the live preview reopens the same form. The generated Markdown remains directly editable in the main document editor. A flashcard's picture and recording fields have **Upload…**, which stores the file in the document's own `images/` or `audio/`, and a recording field has a ▶. A Jolly field is a text box of several lines with **Image…** and **Recording…**, which upload a file and put its line in at the cursor. The document has to be saved once before anything can be uploaded into it. **Paste markdown…**, under the type grid, takes one `:::exercise` block copied as markdown — a card sheet's **copy markdown** gives one — and opens it in the same form as a new exercise, so it can be looked over before **Insert exercise**; pressing Ctrl+V on the type grid does the same at once. Words pasted around the block are left out, and text holding no exercise or more than one is refused with a note saying so. In a saved document the pictures and recordings the pasted block names come in from the clip tray before the form opens, so its preview plays them. **Exercises ▾ → Generate with LLM…** copies the dedicated generation prompt together with the current Markdown. The prompt teaches the model only the exercise types ticked (one box for each of the thirteen; the ones the page already holds, or all of them where it holds none) and the parts of the dialect ticked (the ones the page already uses, read with the parser; the studio's own prompt page has the same boxes), with the target language's conventions and, for a right-to-left target, the rule for the order of isolated boxes; a learner's level and a length may be added, one line each. It can optionally include target words, readings, transliterations, and meanings from the selected local Anki decks of the page's language; no deck is required.

Each text box in the exercise form, and the **Paste markdown…** box, has its own **⇤ RTL** or **⇥ LTR** button. The box initially follows the direction of its text; press the button to force the other direction, and press it again to switch back. This changes only how that box is edited. It does not add a direction field to the saved exercise or change how the exercise is rendered.

When the same document is attached as a note to a book or video, its hover preview represents every exercise block as `<Exercise>`. Prompts and stored answers appear only after the note is opened.

## Follow-up questions

A follow-up (`follow-up`, the fourteenth type, a0.5.4) is a chain of exercises answered one after the other: the learner checks a step, reads what that step says, and only then sees the next. Its steps are exercises of any other type, written inside it **one colon more on every fence** — the dialect's one rule for a block inside a block, the one a `::::latex` drawing inside an exercise already follows:

```markdown
:::exercise follow-up
prompt: Read the short dialogue, then answer about it, one question at a time.
explanation-correct: You followed all of it.
explanation-incorrect: Read the dialogue once more, slowly.
::::exercise single-choice
prompt: Where are the two speakers?
- [ ] at home
- [x] at the station
explanation-incorrect: Look at the sign again.
::::
::::exercise true-false
- The train leaves at nine. => false
::::
:::
```

Inside a step every fence has one more colon than it would on its own, so a drawing in a step is `:::::latex` … `:::::`. `mdparser._parse_step` reads a step by writing it out one colon shallower (`_denest`) and handing it to `parse_exercise` as the exercise it would be alone, so nothing a step may hold is written twice and its `source` reads as that exercise. A drawing written in a step with the four colons it has on its own (`::::latex` … `::::`, what every other page of the dialect and every prompt teaches for a drawing) is read too: `_parse_step` closes a drawing with the fence that opened it, and leaves the lines of a four-colon one as they are (they are already the drawing's); `exform.js` `splitChain` does the same. A four-colon drawing never closed takes the step's own closing line for its end, and the follow-up then says it has fewer than two steps. Each exercise block also carries `_field_text`, the line of the document at which a `key: |` field's own text begins, so that the blocks a prompt is drawn as (`htmlgen._blocks_in_field`) are told the line of the DOCUMENT they sit on: a drawing's ✎ (`editor.js`) finds its own lines by that number, keeps their indent and fence depth, and rewrites them alone; any other block in a prompt is left without a line. `mdparser.nest_step` is the other way. A follow-up needs at least two steps; a step is never a follow-up; it has no answer rows of its own; a step that is wrong is named by its number (`step 2: single-choice exercise needs exactly one [x] answer`); a step never closed ends before the follow-up's own `:::` and says so (`step is missing its closing :::: line`). The follow-up's own fields are `prompt`, `image`, `image-answer`, `audio`, `audio-answer`, `content-direction` and the two explanations; its `explanation-correct` and `explanation-incorrect` are shown at the end, by the result: every scored step right, or not.

**On the page** (`htmlgen._render_exercise_chain`, `app.js` `bindChain`). A strip says *Step 1 of 3* (a live region: a new step is announced) with a dot for each. Only the first step is shown, with **Check step** under it (**Show answer** for a card). The check marks the step as any exercise is marked, says *Correct* or *Not quite*, shows the explanation that answer earned **between the steps**, locks the step and offers **Next step**, which brings the next one into view, scrolled to and focused. From the third step on, the steps before the last two fold into *Earlier steps (n)*. At the last check the chain says its result in words (*2 of 3 steps right*) and its own explanation. Enter does what the button in view does. A card's step counts for nothing. The scored steps count one each in the page's **Check exercises**, and a step not come to is *not answered* (counted, not judged); a chain left half-way says *2 of 4 steps answered*. In the editor's preview the stored answers are shown, **Next step** goes on unchecked and **Show every step** unfolds all.

**The form** (`exform.js`). **Add exercise… → Follow-up questions** (the last tile, after the flashcards). Beside the chain's own prompt, pictures, recordings and explanations it has a **Steps** list: each row says its place (*Step 3 of 8*), its type, its opening words and a mark for a picture or a recording, and has a handle to drag (a finger drags by the handle alone), ↑ ↓, a box to type its place in, **✎ Edit**, **Duplicate**, **⤴ Put back**, **Delete** (with an Undo for six seconds) and a tick. Ticked steps move and are deleted together. **+ New step…** opens the same grid of types, minus *Follow-up questions*, and then that type's own form **in a frame over the chain's** — the form is not forked: `openExerciseForm` takes a `host` saying it is a step, which changes only its title (*Step 2 — Fill in blanks*), its button (*Add to the chain* / *Save step*) and that `direction: both-repeat` is not offered. **+ From this page…** (**+ From this deck…** in a deck) lists the exercises already there, in order, each with its type, its opening words and a tick, with a filter, *Select all / none*, a choice of putting them in the page's order or the order they were ticked, and a box, ticked, that takes the originals away once they are steps (in a deck their study history goes with them). One that needs attention, one that is a follow-up and one that is one side of a linked card are listed greyed, with why. The originals leave the page in the same undoable step that writes the chain. **⤴ Put back** takes a step out of the chain and writes it as an exercise of its own after it (in a deck, adds it to the deck). A step is edited from this list, never on its own: the preview's **✎ Edit** on a chain reopens the chain's form, and the preview at the foot of the form draws every step unfolded. A step's source is kept as written until it is edited, so reopening and saving a chain changes nothing but what was changed. **Paste markdown…** and Ctrl+V on the grid take a chain too; one pasted into a step's grid is refused.

**In a deck** a follow-up is **one exercise**: one block, one id, one schedule, one row in the list (*Follow-up questions · 3 steps*, its prompt or its first step's words as its opening words). `decks._walk(steps=False)` is the deck's reading, `steps=True` the page's (every step is an exercise of a page, numbered after its chain), so `+ Deck`'s ordinals still find their exercise; a step has no `+ Deck` of its own. The files of every step are carried by `+ Deck`, **+ Add all exercises**, **Load from a deck…** and an export, since they read the block's text. In **Add all exercises**, **Make a follow-up chain of these…** makes one chain of the ticked exercises of the page (`POST …/copy` with `ordinals` and the type `follow-up`: the server composes it in the page's order and copies the files of every step; look it over with **✎ Edit** in the deck), and the deck's own list has the same button over its ticked rows, which opens the chain form with them as its steps. The deck's `FORMAT` does not change: a deck holding a chain, opened by a Parseh before a0.5.4, is read with that exercise refused (its import says `unknown exercise type: follow-up` and skips it, and the rest of the deck is imported).

**Studying** goes a step at a time, as on a page: the answer bar's button is **Check step** (**Show answer** for a card), then **Next step**, and the four ratings come only after the last step, the focus on **Again** if any scored step was wrong and on **Good** if none was; the history row records `steps: {right, of}` beside the rating (only an integer pair with `0 <= right <= of` is kept). **Skip** in the middle sets the whole chain aside; **✎ Edit** opens the chain's form. **Cram**: a chain is right only when every scored step was right; otherwise it comes round again whole.

**On paper** (`texgen._render_chain`, `\expaperstep`) a follow-up is one exercise under its label with its prompt and its shared picture once at the top, then its steps **numbered 1., 2., …**, each in a lighter frame of its own and laid out exactly as its type is laid out on paper (a card prints its front and its back one under the other, labelled, not as a card to cut and fold). A chain may part between two steps at a page's foot, never inside one; the head keeps with the first step unless it carries a picture of its own. The answers, the explanations and the pictures of an answer are left out, and every step is visible at once, so a step whose prompt gives away the one before should be written with that in mind. `tests/test_follow_up_paper.py` builds the PDF in every print size and in black and white, left to right and right to left.

## On paper

A document's PDF prints the exercises without their answers marked: a blank is left empty, no choice is ticked and no statement is marked true or false, and the explanations are left out, as are the pictures and recordings of the answer. A flashcard is the exception: it prints both its sides, as a card to cut out and fold — a frame with round corners (TikZ; a square one without it), the side the card shows first in its left half and the other in its right, each drawn as the page draws it (the picture, the recording, then the fields at their sizes and in their shades), and a dashed line exactly between the halves to fold on. Nothing crosses the fold, and a card is never split between pages: one taller than a page is printed smaller, whole. The exercises a student writes on are laid out for a pen:

- **Matching** (`match-translations`, `match-opposites`, `match-definitions`). Every entry of both columns sits in a frame of its own. The two columns are equally wide, with a gap between them for the line the student draws from one frame to the other, and the two frames of a row are equally tall. The right column is shuffled as it always was. An entry in a right-to-left language is set flush right, with its continuation lines, and a picture in an entry is printed in its frame.
- **Construct the sentence.** The chunks are printed in a row, as the page shows them, each in a frame, shuffled, and flowing the way the answer is read: `answer-direction` if the exercise gives one, otherwise the target language's direction, so a Persian row starts at the right. Under the row are lines as wide as the exercise's box, for writing the whole sentence out. There are as many lines as it takes to hold one and a half times the sentence, and never fewer than one. TeX measures the sentence as it sets it: the chunks end to end, one space between each, in their own fonts and sizes. So the count is right at any print size and in any script. `order-sentences` is still a list.
- **True / False and Yes / No.** Each statement has a column of its own and wraps inside it, and the marks sit in a column at the right that nothing else enters. They are one unbroken piece, level with the statement's first line and at the same place on every row. A statement in a right-to-left language is set flush right, next to the marks. Before, a long statement ran under the marks, and "/ False" could drop onto a line of its own.

Nothing crosses a frame or runs under the marks, at any print size. A word too long for its entry's frame or its statement's column is hyphenated there, even when it is the first word, and a line may end after a slash (`socioeconomic/political`). What cannot break at all, such as a long number, is set smaller until it fits its column.

**PDF options ▾**, beside **Build PDF** on a document's page, prints the same document two other ways. The choice is kept for that document in the browser, and the build badge says which options the PDF was built with:

- **Print size**: Normal (11 pt), Large (14 pt), Extra large (17 pt) or Maximum (20 pt), for readers with low vision. Everything grows with the text, and the exercises are set a step larger still, with heavier blanks, frames and lines. An exercise taller than a page, such as a reading passage with its questions at 20 pt (or, at any size, ten framed pictures to match), starts a page and continues over as many as it needs, a frame on each page. A table wider than the line is scaled down to fit it, and the column of a vertical (tategaki) block is never longer than the page. A lemma's transliteration too wide for its place beside the headword is set smaller, as the headword is.
- **Black and white**: no colour and no grey anywhere except in the pictures, for photocopies. The tints go white, and a tinted panel keeps a thin black frame instead. Coloured words print in black.

The details are in [markdown/README.md](../markdown/README.md), under *PDF*.

## Exercise decks

The **Exercises** door (`/exercises/`, beside Studio on the hub) keeps exercises in decks and brings each one back when it is due, the way Anki schedules cards. A deck has one language, and every exercise in it is in that language. **+ New deck** asks for a name and the language. The door's card for each deck shows how many exercises it holds and what is to study now: new, learning and to review, coloured as Anki colours them. When nothing is due, the card says when the next exercise is.

### Filling a deck

- **From a document.** On a studio document's reading view every exercise, boxed ones included, has a **+ Deck** button. It lists the decks in the document's target language, with the last one used already selected and **+ New deck…** at the end. **Copy** puts that exercise into the deck exactly as it is written, with the document's tags on the exercise. The copy includes the footnote definitions the exercise refers to and every picture and recording it names, wherever the name is: a `front-image` or `back-audio` field, a picture or recording line inside a Jolly field, or a footnote. A file whose name is already taken in the deck by a different file is stored as `name-2.png` or `name-2.mp3` (`-3`, …), and every reference to it is rewritten to match; the same file already in the deck is not copied twice. A picture or recording missing from the document keeps its path, and the confirmation says so. The deck records which document and which exercise it came from. Later edits to the document do not change the copy. An exercise already in the deck asks before it is added again. If the document was saved elsewhere after the page loaded, the copy is refused until the page is reloaded, because the button could otherwise pick the wrong exercise. An exercise that shows errors has no button. Notes attached to a book or a video have **+ Deck** too, and the deck's link goes back to the note. The editor preview has none.
- **A whole document at once.** **+ Add all exercises**, beside **Edit** at the top of the reading view, lists every exercise on the page that has **+ Deck**, in the page's order, each one ticked. **Show gloss flashcards** adds the document's glosses to this list as selectable vocabulary flashcards, including their readings and transliterations when available. They are copied into the chosen deck as flashcard exercises with the document's tags. Untick the ones to leave out (**Select all** and **Select none** change the visible list), choose a deck or **+ New deck…**, and **Add** copies the rest one after another. An item the deck already has is left out unless **Add again the ones this deck already has** is ticked. One the deck refuses is counted, and the rest still go in. The confirmation says how many went in and what was left out, and names any missing picture. If the document was saved elsewhere after the page loaded, the run stops and asks for a reload, and a new deck that received nothing is removed again. An exercise that shows errors is not offered. The button appears when the page has an exercise or a gloss to copy, on notes beside a book or a video too.
- **In the deck.** **Add exercise…** on the deck's page opens the same type grid and form as the editor, with the preview rendered in the deck's language, and the same **Paste markdown…** for an exercise copied as markdown. What is saved must be exactly one `:::exercise` block with nothing around it and no errors. A flashcard's picture and recording fields have an **Upload…** button that stores the file in the deck and fills in its path, and a recording field has a ▶ to hear it. A Jolly field has **Image…** and **Recording…**, which upload the file and put its line in the field at the cursor. An exercise naming a picture or a recording the deck does not have is still saved, and the confirmation warns about it.
- **From a book or a video.** The card sheet a modifier-click opens in the book reader and in the video player has three destinations, and **exercise deck** is one of them. It lists the exercise decks of the book's or the video's language, with **+ new deck…**, and **add to deck** adds the card as a flashcard exercise: a vocabulary or opposites card from the word, or a Jolly card whose four fields start from it. The recording cut with **🔊 cut the audio…** goes in as `front-audio` or `back-audio` (on a Jolly card, as a line in a field), and a frame captured from a video as `front-image` or `back-image`. A card the deck already holds is added again only when you say so. The deck remembers where the card was made, and its list links back: to the book's reader at the paragraph, or to the player at the card's second, labelled with the book's or the video's title and the subparagraph's number or the time. The sheet's **markdown** destination puts the same card on the clipboard instead, to paste into a studio document or into **Add exercise… → Paste markdown…** (or Ctrl+V on the type grid), where it opens in the form as a new exercise.
- **From the clip tray.** A recording cut in a book or a video, and a frame captured from a video for an exercise deck or markdown, wait in the toolbox's clip tray (`clips/`) under a name no other file in the toolbox has. When an exercise is added or saved naming such a file and the deck does not have it, the file is copied in from the tray, so a card pasted from the clipboard brings its recording with it. The tray keeps its copy. A name the tray does not hold either is a warning, as above. Since the deck keeps its own copy, a clip deleted from the tray afterwards is gone from nothing in the deck: the tray's own page, **The clip tray** on the hub, plays every clip and deletes one with ✕ or all of them with **Empty the tray**.

### Back into a document

The editor's **Exercises ▾ → Load from a deck…** is the way back: it lists the decks in the page's language (no **+ New deck…** — there is nothing to take out of a deck that does not exist yet), and under the chosen deck every exercise in it, headed by what kind it is and showing its opening text. **Insert** puts that exercise into the document at the cursor, exactly as the deck has it. Its pictures and recordings are copied into this document's own `images/` and `audio/` first: a file whose name is already taken there by a *different* file is stored as `name-2.png` (`-3`, …) and the block that goes in names it where it landed, while the same file already in the document is not copied twice. The footnotes the exercise calls come with it and are placed among the document's own, in the order the reader meets them; a note whose name the document already uses for something else is renamed (`n1-2`) in the inserted block and in its own definition, so neither note is lost. The deck is left exactly as it was — this copies out of it, it does not move anything. A picture the deck itself has lost keeps its path, and a warning says which. The document has to be saved once before an exercise can be loaded, since the files go into its own folder. An exercise the deck reports as broken is still offered, marked *needs attention*: the document is where it is easiest to mend.

### Browsing

The deck's page lists every exercise with:

- its type;
- its opening text;
- its state (new, learning, relearning or review) and when it is due;
- its reviews and lapses so far;
- the document, book or video it came from, linked.

A filter box searches the exercises' text and markdown. Three selects narrow the list by type, state (**Due now** included), and tag; a counter shows how many match. Clicking a row shows the exercise solved.

Each row has a checkbox. A visible hint below the toolbar explains that you can click one checkbox, then Shift-click another checkbox or row to select the range between them; Shift-clicking an already selected row deselects the range. Ranges follow the order of the currently visible rows, so filtered-out exercises keep their selection. **Select all** selects every exercise in the deck, **Select shown** selects only those matching the current filters, **Deselect shown** takes only those out of the selection (what the filters hide stays selected), **Deselect all** clears the selection, and **Select by tag** selects every exercise with a chosen tag. The tag filter narrows the visible rows. The selection remains when filters change, tags are added or removed, exercises are copied, or the page is revisited in the same tab. **Add tag…** and **Remove tag…** apply to the whole selection; this lets you remove an old tag and add a replacement without selecting the exercises again. **Set to new** clears the selected exercises' scheduling and review history while leaving them selected. **Copy to deck…** starts copies with fresh scheduling; **Move to deck…** carries scheduling into another deck of the same language and opens that deck with the moved exercises selected. Both carry tags, pictures and recordings. **Delete** removes the selected exercises and their histories. Rows also offer their own **Copy to deck…** and **Move to deck…** buttons.

**Cram exercises** starts with all selected exercises in random order. Check a scored exercise to see whether it was correct; a missed matching or placement exercise also shows the correct answer. After revealing a flashcard, choose **Correct** or **Wrong**. Each wrong scored exercise or flashcard goes to the end of the current cram queue and returns until answered correctly. Flashcards play their front and back recordings when each side appears. Cram never changes deck scheduling or review history. After returning to Browse, the selection is still there.

- **Edit** reopens the exercise in the form. An exercise the form cannot show opens as markdown instead. An edit keeps the exercise's schedule and its origin.
- **Duplicate** adds a copy that starts as new.
- **Delete** removes the exercise and its history for good.

The same page renames the deck (its address stays the same), exports it, sets its options, and deletes it. A deleted deck is moved to `exercises/.trash/`.

### Studying

**Study now** shows one exercise at a time, unsolved.

- A scored exercise is answered, then checked with **Check** or Enter. The result reads *Correct* or *Not quite*, the explanations appear, and the answer is locked. A matching or placement exercise answered wrongly also shows its correct answer below the result. Enter checks right after a click on an answer; on an answer reached with Tab, Enter chooses it.
- A flashcard is turned with **Show answer**, Enter, or a click on the card — the enlarged one of **⤢ Enlarge** included. A click on its 🔊, a player, a link or a footnote's mark does not turn it.
- A flashcard plays its recordings as Anki plays a card's sound. When the card is shown, the first recording on its front plays once; when it is turned, the first on its back. A recording is a `front-audio` or `back-audio` field or a recording line in a Jolly field, whichever comes first on that side, and one laid out with a clip plays only its clip; a clip that starts at or past the end of its file is not played by itself. With **⤢ Enlarge** open, the enlarged card plays and the one under it keeps still, and the window closes when the next exercise comes. Whatever is playing stops when the card is rated or skipped, or the next exercise comes. A browser that lets a page make no sound until it has been clicked plays nothing by itself until then — in Chrome, arriving through **Study now** counts — and the 🔊 and the players are still there to press.
- An exercise whose markdown has errors offers only **✎ Edit** and **Skip**.

After the check or the turn, the rating bar appears. Each button shows how long the exercise would wait:

| rating | key | use it when |
|---|---|---|
| **Again** | 1 | you did not know it |
| **Hard** | 2 | you got there with effort |
| **Good** | 3 | you knew it |
| **Easy** | 4 | it was too easy |

The check never rates for you. A wrong answer only moves the focus to Again, and a right one to Good. The result is saved in the exercise's history beside the rating. An exercise already answered elsewhere, in another tab for instance, is not scheduled a second time: the answer is refused and the page moves on to what comes next. **✎ Edit** corrects the exercise on screen without touching its schedule. **Skip** sets the exercise aside, unscheduled, until the page is reloaded or **Study the skipped ones** is pressed. When nothing is left, the page says when the next exercise is due: "next exercise in 8m", "tomorrow", or "no exercises scheduled".

Exercises come in this order: learning steps that are due, then reviews that are due (the longest-waiting first), then new exercises in the order they were added. When only a learning step is left and it is due within 20 minutes, it is shown early, as Anki's learn-ahead does.

### The scheduler

The algorithm is Anki's SM-2 (the v2/v3 scheduler), in `markdown/app/srs.py`:

- **New → learning.** A new exercise goes through its **learning steps** (1 minute, then 10). Again goes back to the first step, Hard repeats the current step (on the first step it waits halfway between the first two), and Good moves on.
- **Graduating.** Good on the last step graduates the exercise to **review** with a 1-day interval. Easy at any step graduates it at once with 4 days.
- **Review.** A review waits whole days, and each exercise has an **ease** that starts at 2.5.
  - Good multiplies the interval by the ease.
  - Hard multiplies it by 1.2 and lowers the ease by 0.15.
  - Easy multiplies it by the ease and by 1.3, then raises the ease by 0.15.
  - Hard always gives at least one day more than the last interval, Good at least one day more than Hard, and Easy at least one day more than Good.
  - An exercise answered late gets credit for the extra days: half of them on Good, all of them on Easy.
- **Lapse.** Again on a review is a **lapse**. The ease drops by 0.20, never below 1.3. The exercise **relearns** through a 10-minute step, then returns to review with a 1-day interval.
- **Spread.** Intervals of 3 days or more are moved by a few percent (up to 15% for a week or less, 5% beyond 20 days), so exercises added together do not all fall due on the same day. The spread comes from the exercise's id, so the label on each button is exactly what the answer will give.
- **The day.** A day starts at 04:00 local time, as in Anki. An answer given after midnight still counts for the evening before, and an exercise due "tomorrow" is due from 04:00.
- **Daily limits.** At most 20 new exercises and 200 reviews a day, counted from the answers already given that day. Exercises held back by a limit wait for the next day. Learning steps are not limited.

### Options

**Options…** on the deck's page changes the first seven of these. The rest keep Anki's defaults and can be set by hand under `settings` in the deck's `deck.json`. The deck falls back to all the defaults if one value there cannot be used.

| setting | default | meaning |
|---|---|---|
| `new_per_day` | 20 | new exercises a day |
| `reviews_per_day` | 200 | review answers a day |
| `learning_steps` | 1 10 | minutes; empty means a new exercise graduates at its first Good |
| `relearning_steps` | 10 | minutes; empty means a lapse goes straight back to review |
| `graduating_interval` | 1 | days, after the last learning step |
| `easy_interval` | 4 | days, for a new exercise answered Easy |
| `maximum_interval` | 36500 | days; no interval is longer |
| `starting_ease` | 2.5 | the ease a graduating exercise starts with |
| `minimum_ease` | 1.3 | the ease never drops below this |
| `easy_bonus` | 1.3 | Easy's extra multiplier |
| `hard_multiplier` | 1.2 | Hard's multiplier |
| `interval_modifier` | 1.0 | scales every review interval |
| `new_interval` | 0 | the fraction of the interval kept after a lapse |
| `minimum_interval` | 1 | days; no interval is shorter |
| `rollover_hour` | 4 | the hour a new day starts |
| `learn_ahead_minutes` | 20 | how early a learning step may be shown |

### Export and import

**Export** on the deck's page, or the ⋯ menu on its card, downloads the deck as a zip. There are two versions:

- **With scheduling** (`exercises-<slug>-with-scheduling.zip`): for your own other machine.
- **Without scheduling** (`exercises-<slug>.zip`): for somebody else. Every exercise starts as new when it is imported.

Both hold:

- `parseh-exercise-deck.json`, the manifest (format `parseh-exercise-deck/1`) with the deck's id, name, language and changed options;
- every exercise under `items/`;
- the pictures the exercises use under `images/`;
- the recordings the exercises name under `audio/`.

The scheduling version adds `schedule/`, with each exercise's state and every answer given.

**Import deck…** on the Exercises page takes such a zip. **Keep the scheduling saved in the file** is ticked by default. When it is unticked, or the file was exported without scheduling, every exercise starts as new. A zip holding anything else is refused, and so is one with a file under `audio/` that is not a recording or is larger than 30 MB. Each exercise is checked on the way in, and one that is not a single sound exercise is skipped and counted in the message. A deck keeps its id through export and import, so importing a deck that is already here asks what to do:

- **Replace it** moves the deck already here to `exercises/.trash/` and puts the imported one at the same address.
- **Import as a copy** keeps both, and the new one is named "… (copy)".

An import may hold at most 512 MB uncompressed. When the studio runs on its own (`markdown/app/server.py`), the uploaded zip itself is also limited to 32 MB.

### Where decks live

Each deck is a directory, `exercises/<language>/<slug>/`, at the root of Parseh:

```
deck.json            name, language, the options that differ from the defaults
items/<id>.json      one exercise: its markdown, its footnotes, where it came from; a
                     `link` (12 hex) when it is one side of a linked pair
schedule/<id>.json   its state and every answer (no file while it is new)
images/              the pictures its exercises and flashcards use
audio/               the recordings its flashcards play
```

**Linked pairs.** A flashcard written `direction: both-repeat` goes into a deck as two items,
`direction: forward` and `direction: reverse`, that share one `link` (the second is made a
microsecond after the first, so the queue keeps their order). The link is a group id, not a
pointer: a card whose other side is gone is a group of one, which is not linked, and a group id
needs no partner to be valid. It travels in an export, an import and a backup; a copy or a move to
another deck makes a new one for the pair; **Duplicate** links the copy with nothing. Changing or
deleting one side is refused by the store (`Conflict("linked")`, HTTP 409) until the caller says
`linked: "both"` or `"alone"`: it is the server that owns the rule, so no page can forget it.
`both-random` needs no expansion: the card is stored as it is, and the page draws a face.

**Burying.** When one side of a linked pair is answered, the other is not offered until the next
day starts (Anki's bury-until-next-day). Nothing is stored for it: `srs.buried_today` reads the
answers already written in the schedule histories (`decks._buried`), so the hold lapses by itself
at the rollover, ends at once when the other side is deleted, unlinked or set to new, and is
carried by a phone's replayed answers by the day each was given. Cramming ignores it.

Decks are personal study state. Git ignores everything under `exercises/` except `exercises/README.md`, so a deck moves between machines by its export. The pages, the store and the scheduler are `markdown/app/deckroutes.py`, `markdown/app/decks.py` and `markdown/app/srs.py`.
