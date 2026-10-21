# ARASAAC pictograms in the studio: what is built, what the licence asks, and the design to decide

Written on 5 October 2026 for the owner, a0.4.2, lane P (TO-DO §8.40, brief 9C). **Read this before anything more is built.**

| Piece | State |
|---|---|
| **A. The Settings door** (Settings → Pictograms (ARASAAC)): fetches the words and the pictures, with the licence said first | **Built and proved.** `lib/getarasaac.py`, `lib/arasaacpage.py`, tests against a fake server and in a browser. Section 4. |
| **D. The picker** (a0.5.3): a frame in which a person looks for a pictogram by a word, sees it, and adds it from the editor, the exercise form and a deck; the door only looks | **Built and proved.** `lib/arasaacsearch.py`, `lib/pictograms.js`, `lib/pictograms.css`, three entry points. Section 4b. |
| **B. The toggle** in the studio's exercise prompt | **Not built.** Waits for your answers. Draft of its text in 5.2. |
| **C. The macro, the resolver and the swap** | **Not built.** Designed in section 5; your decisions are the questions of section 7. |

Everything below that says "driven" was run against the studio's own parser and renderer, or against the real English word list that was fetched once on 2 October 2026 (kept in the build's scratch area, not in the repository). Nothing of ARASAAC's is in the repository, and for this note nothing was asked of ARASAAC but one look at its terms page.

## 1. The licence: what ARASAAC's terms ask

From https://arasaac.org/terms-of-use, read in a real browser on 2 October 2026 (the page is a script: a plain fetch gets nothing) and looked at once more on 5 October, when all fourteen sentences of the first copy were still there word for word. The duties, in their words where they matter:

- The pictograms are the work of **Sergio Palao** for **ARASAAC**; the owner is the **Government of Aragon** (Spain). ARASAAC is its registered brand and the collection is registered as a collective work (Deposit Legal Z 901-2013).
- "Resources offered on the website (pictograms, images, locutions or videos), as well as the materials based on them, are published under **Creative Commons License BY-NC-SA**, authorizing their use for non-profit purposes providing the source and the author, and are shared under the same license."
- "The use of these resources within any product or publication for **commercial purposes is excluded**." Any other use needs written authorization.
- "Any work derived from the resources ... must be distributed with the **same Creative Commons License BY-NC-SA**. The author (Sergio Palao), the owner (Gobierno de Aragón), their origin (ARASAAC) and the license ... must be cited."
- Two ways to cite, word for word. Long: *The pictographic symbols used are the property of the Government of Aragón and have been created by Sergio Palao for ARASAAC (http://www.arasaac.org), that distributes them under Creative Commons License BY-NC-SA.* Short: *Pictograms author: Sergio Palao. Origin: ARASAAC (http://www.arasaac.org). License: CC (BY-NC-SA). Owner: Government of Aragon (Spain)*
- "The ARASAAC **logo** must be included on all signs, posters, and plates when the pictograms are used for signage of public areas, services, stores." A page for studying a language is none of these; Parseh puts no logo anywhere.
- The Government is not responsible for use that exceeds the licence.

**What the terms do not say** (and what to do about it, your call, section 7):

- Anything about **fetching many files** from the API or the picture host. The developers' page (https://arasaac.org/developers/api) offers the REST API with no key and no conditions; it lists `GET /pictograms/all/{language}` and the machine-readable description is at api.arasaac.org/arasaac_v1.json. Parseh asks for the whole set once, on a button, one picture at a time on one kept-open connection (at most about twenty a second; about twelve minutes), with a User-Agent that names Parseh and its project, a server's `Retry-After` obeyed and a wait that grows after an error. "For other uses and any queries" the terms point to arasaac.org/contact-us.
- Anything about **an application keeping a local copy for its user**, or about **hosting**. Parseh ships and hosts none: each person's copy comes from ARASAAC's hosts on that person's request.
- What "non-commercial" means. The Creative Commons deed's own definition is *not primarily intended for or directed towards commercial advantage or monetary compensation*: a document one studies from, prints for a class or gives a friend is on the right side; a book one sells is not.

**What Parseh does about it.** The door says all of the above before anyone presses a button (the credit in ARASAAC's words, "not for sale", "shared on the same terms"); `arasaac/LICENSE-ARASAAC.txt` carries both citations word for word and is written when a download ends; `/licences/` (lib/notices.py) lists the pictograms with their licence and its link; the guide page `studio/pictograms.md` says plainly what NC and SA mean for a document. Parseh enforces none of it (it cannot): the licence does. What it must not do is make the duties easy to forget, which is what section 5.6 is about.

## 2. The facts

Measured against the real hosts on 2 October 2026 (the table in `lib/getarasaac.py` `MEASURED` is what the page quotes before a download, so nobody is asked for anything blind) and recounted from the saved lists on 5 October (every figure in `MEASURED` reproduces exactly).

- **13,829 pictograms**, the same 13,829 in every list I counted. A pictogram's `_id` is stable; its picture can change (`lastUpdated` moves; the host's `Last-Modified` is the picture's own date).
- **The API's languages** are forty (an ar bg br ca cs da de el en es et eu fa fr gl he hi hr hu it is ko lt lv mk nb nl pl pt ro ru sk sq sv sr tr val uk zh), asked for as `GET /v1/pictograms/all/{locale}`. Of Parseh's eleven: Persian, Arabic, Italian, French, German, Turkish, Spanish and Chinese have words, English names every pictogram, **Japanese has none** (no list), **Hindi has one word** (and it is Spanish). The door offers the first nine and says why it does not offer the last two.

| Language | Words (entries) | Pictograms they name | List as served | Kept by Parseh |
|---|---|---|---|---|
| English | 26,578 | all 13,829 | 7.6 MB | 1.8 MB |
| Spanish | 21,074 | all | 8.2 MB | 2.4 MB |
| Persian | 25,037 | 13,112 | 6.7 MB | 1.1 MB |
| French | 26,020 | 13,712 | 6.8 MB | 1.2 MB |
| German | 24,484 | 13,800 | 6.4 MB | 0.8 MB |
| Italian | 22,399 | 13,799 | 6.4 MB | 0.9 MB |
| Chinese | 15,203 | 11,315 | 5.8 MB | 0.5 MB |
| Arabic | 11,572 | 8,609 | 5.7 MB | 0.4 MB |
| Turkish | 2,783 | 2,656 | 5.2 MB | 0.1 MB |

- **The pictures**: a random 400 of the ids, both sizes, all 400 answered at both: **11.5 kB at 300 pixels, 23.2 kB at 500** on average; so **159 MB and 321 MB** for the lot (2500 pixels is a 335 kB poster: never). English at 300 pixels is a 166 MB download and about 161 MB on the disk, twelve minutes.
- **The flags** each pictogram has: `schematic` (3,722: a simpler drawing of the same thing), `skin` (6,332) and `hair` (2,688: the colours the API can change), `aac` (858), `aacColor` (159), **`violence` (106) and `sex` (77)**: 170 pictograms in all, and 120 keywords that would have no pictogram left if those are left out. The flags are kept in `arasaac/pictograms.json`.
- **The words**: 15,770 distinct English keywords (case and Unicode folded), 7,912 of them more than one word; the keyword kinds are 2 (nouns, 16,416 entries), 3 (verbs, 6,161) and 4 (adjectives, 1,962), read from samples, and 1 (924), 6 (702) and 5 (400), which I did not decode. The list of the keywords alone is **186 kB**: it cannot be put in a prompt.
- **Ambiguity** (driven on the real list): 11,008 keywords (70%) name exactly one pictogram and 4,762 (30%) name several. For a beginner's 201 concrete words that I wrote down (house, dog, bread, eat, big, red ...) **200 are an exact keyword and 169 (84%) have more than one pictogram**: *bank* has 6, *house* 3 (a house, a detached house, and the schematic one), *play* 10, *light* 9 (the lamp, the weight, to illuminate, low-calorie ...), *bat* 3 (the animal, the baseball bat, to bat).
- **Absence** (driven): an abstract vocabulary of 55 words (maybe, idea, knowledge, although ...) finds a pictogram for 26 and none for 29. Of eight verb phrases, "to eat", "to look for", "to wake up", "to get dressed" and "to go to bed" are found by dropping "to"; "to be afraid of", "to have breakfast" and "to take a shower" are not.
- **How big the studio draws a picture** (read from `sheet.css` and `texgen.py`, and looked at with the real pictures, `shots/P/layout-real-pictograms.png`): in an exercise cell and on a flashcard at most 8 em tall (136 pixels on the page I rendered), a figure line at the width it is given as a percentage of the column, on paper an inline picture is 0.12 of the text height (about 2.7 cm). 300 pixels is sharp for all of those; 500 helps only a figure drawn wide or a large print.

## 3. How the studio treats a picture today (driven, because the design rests on it)

`![alt](images/name.png)` is read in some places and garbled in others. I rendered one real pictogram in every place with the studio's own renderer:

| Where it is written | What the studio does |
|---|---|
| A line of its own in prose (also a line of a wrapped paragraph, or a `>` box that holds only it) | A figure; the alt text is its caption; `{width=18 align=center}` sizes it |
| Inside a sentence, a list item, a table cell, a heading | **Garbled**: `la !casa è grande`, the picture lost and its brackets eaten |
| Inside an exercise's text: an option, a side of a pair, the sentence with its blanks, the prompt, a flashcard's `meaning` or `context` | Drawn inline (`ex-inline-image`), 8 em |
| `front-image:` / `back-image:` of a flashcard | Drawn on that side of the card |
| `image:` / `image-answer:` of any other exercise | A figure at 60% of the column unless it says `{width=...}`: 450 pixels wide for a 300-pixel picture, soft; so a pictogram needs `{width=20 align=center}` |

A whole answer from a chatbot comes into the studio **only through the library page** (**Paste LLM answer**, **Upload .md**: `api_create`); the editor says in a comment that importing a whole document inside it "replaced everything already typed" and so does not do it. One exercise comes into an open page through the exercise form's **Paste markdown…** (and Ctrl+V on the type grid), which already calls `POST /api/docs/<id>/adopt` to bring the clips it names in from the tray. `store.extract_markdown` takes the document out of a four- or three-backtick fence or out of no fence, and keeps every character a macro would use (driven with the three shapes). `store.save_image(doc, name, bytes)` returns a collision-free name and **reuses a file with identical bytes**, so `arasaac-2317.png` is stored once however often it is placed.

## 4. Part A as built

- `lib/getarasaac.py`: the downloader and the facts of what is installed. Languages are one of the forty names, sizes one of two numbers, ids integers; nothing a client sends becomes a path or an address. Pictures appear under their name by one rename, so a file there is whole (checked as a PNG, signature and closing chunk); `pictograms.json` marks each record whose picture is still to come, so a stop, a kill or a dropped line carries on with nothing fetched twice; an update asks for the lists again and then fetches only what moved, with `If-Modified-Since`; a list with far fewer pictograms than are here is refused and changes nothing; a whole install stays whole when an update is refused or the host is down.
- `lib/arasaacpage.py`: the page. The licence first, then the languages (what ARASAAC has in each, what each costs), the size of the pictures, **what it all costs before the button**, one button that says what it does, progress and Stop, Update, Remove (a language's words, or everything).
- `serve.py`, `lib/settingspage.py`: the door and its six routes; `arasaac.get`, `arasaac.remove`, `arasaac.stop` are open to **any device that has been let in** (nothing a device sends becomes anything that is fetched; the same two hosts, the same files for everybody), every write refused from another site, a download on the Working list. `lib/notices.py` and `/licences/`: the entry. `.gitignore`, `lib/release.py`, `lib/updater.py`, `lib/version.py` (a format row, `parseh-arasaac`): the folder `arasaac/` is somebody else's content, outside a release, kept by every update and left out of backups.
- The guide: `studio/pictograms.md` and a line each in the hub, backups, updating, other devices, where things live, the file layout and the licences page.
- It is **not** wired into any prompt, and no page asks for a pictogram yet: until B and C are built the door only fetches.

## 4b. The picker, for a person (a0.5.3)

**Why.** The pictograms were made for the model to ask for (B and C, not built); a person who opened the door could fetch them and then do nothing with them, and the pictures cannot be told apart by their numbers. The picker is the way in for a hand.

**One frame, three doors.** `lib/pictograms.js` (and its sheet, linked from beside it by the script itself, the frame shown only once the sheet is there) draws a dialog over the page, as every dialog of Parseh is drawn: a search box, the language to look in (every one that is here, or one), the thumbnails, and a preview of the one chosen (the picture as large as the screen allows, its word, what it means, the words it has in every language, what ARASAAC says of it, its number). Arrows walk the thumbnails, Tab stays inside, Escape and a click outside close it, and the keys go back to what opened it. On a phone it fills the screen and the preview is a sheet over the list, with *Back*. What differs between the doors is handed to it:

| Door | Button | Does |
|---|---|---|
| **Settings → Pictograms (ARASAAC)** | *Look through the pictograms…* in the row that says what is installed, drawn only when a picture is here | **Only looks.** Nothing to add |
| **The studio's editor** | *Pictograms…* beside *Images…* | A **figure on a line of its own** at the cursor, `![word](images/arasaac-2317.png){width=18 align=center}`, its caption the word in the document's language; *Add to the page*, or *Add, keep looking* for several |
| **The exercise form** (the editor's and a deck's: one form) | *Pictogram…* beside each picture field's *Upload…*; one more in the bar beside *LaTeX drawing…* and *Maths…* | A card's side: `images/arasaac-2317.png`. An exercise's picture: the path with **`{width=20 align=center}`** (the form's 60 % at the left would be soft and huge, section 3) and the boxes say so. The bar's button puts a **small picture inside the line** of the field the hand was last in (`![house](images/arasaac-2317.png)`, a space either side where it touches a word), a **figure** in a jolly card's blocks, and the path in a picture field |

**No page links the script.** The exercise form (`exform.js`, which the editor and the deck pages share) and the door fetch it **when a button is pressed**, with a ten-second deadline. A tag in a page, `async` or not, is a request the page's `load` waits for: a deck kept on a phone and opened with the computer answering nothing sat on it for thirty seconds (`tests/mobile_pages.mjs` b2 found it, in the a0.5.3 loop, the first time the tag was there). What only a search needs is asked for when a search is wanted; a phone keeps nothing of it.

**How a copy is made.** The frame fetches the picture's bytes and hands them to the page's own uploader (the document's `images/`, a deck's), so the copy is the document's own, named `arasaac-<number>.png`, and the same bytes are stored once (`store.save_image`). **The server has no route that takes a pictogram into a document**: the two routes it answers (`POST /api/arasaac/search` and `GET /arasaac/<number>.png` in the studio; `POST /settings/api/arasaac/search`, a read open to any device let in, and `GET /settings/arasaac/picture/<number>.png` in the toolbox) only read what `lib/getarasaac.py` kept, and nothing a client sends becomes a path (a number is digits, a language one of ARASAAC's forty).

**The credit** (5.7). The editor writes ARASAAC's short credit as the document's last paragraph **the first time** a pictogram goes in, once (it recognises `Pictograms author: Sergio Palao`), in the same undo step as the picture, and says so; also after an exercise made with the form's own pictograms, and after an exercise copied from a deck that names `images/arasaac-*.png`. It is never taken out for the person. **A deck gets no credit yet**: a deck's zip refuses any entry it does not know (`decks._check_entries`), so a `LICENSE-ARASAAC.txt` in it is a change of format that an older Parseh would refuse. *Your call* (still 5.7); until then the frame, in a deck, says where the copy goes and the licence says the rest.

**What is looked for.** Folded, so that "casa", "Casa", "cása" and a Persian word typed with an Arabic yeh or kaf are one (case, accents, the vowel marks of Arabic, Persian and Hebrew, the digits of every script, the zero-width non-joiner as a gap). Ranked: the keyword is what was typed, its plural is, a keyword starts with it, a word inside a keyword does, the text is inside a keyword, a word of the meaning begins with it; every word typed must be found, in any order; two at one step go by the shorter keyword, then the number. About 25 ms for one language and 250 ms at worst for twelve (measured on a synthetic set of 13,829 each). The words under the pictures are the document's language when it is here. **`violence` and `sex` are left out** unless a box is ticked, and the frame says how many were (*3 more pictograms match but are left out…*, with a way in), so nobody wonders why a word they know has no picture. A download that is not finished is searched as far as it got, and it says so; nothing installed says where to get it (a link in the toolbox, words in the studio run alone).

**A fault found on the way and mended for everything**: an embed put in with the cursor still at the top of a page that nobody had clicked in (a figure, a recording, a video, an exercise) went in **above the front matter**, and the page stopped being its language (the preview falls back to the first the toolbox has). `insertStandaloneLine` now puts it below.

**Proved** by `tests/test_arasaacsearch.py` (folding, ranking, the flags, pages, a request not well made, changes on the disk), `tests/test_pictogram_picker.py` (the routes of the toolbox and the studio, the gate, the files, the pages) and `tests/pictogram_picker.mjs` (a real browser, both the toolbox's server and the studio's own, on an installed set of pictograms written by `tests/pictogram_world.py`: the door, the words, the keys, the editor, the exercise form, a deck, nothing installed and part of it, the three themes, a phone).

## 5. The design of B and C

### 5.1 The whole mechanism in ten lines

1. With the pictograms installed, the studio's exercise prompt (and the library's prompt page) gets a box **pictograms (ARASAAC)**, ticked by no preset and remembered on this device. Not installed: no box, a line that links to the door.
2. Ticked, the prompt adds one paragraph (about 1,000 characters, 5.2) that teaches one notation: **`⟦pictogram: house⟧`**, an English word for a thing a drawing shows.
3. The model never writes a picture, a path or a number; it only asks. With the box off, the notation is in the reserved list ("you were not taught this: do not write it").
4. When a whole answer comes in through **Paste LLM answer** or **Upload .md**, or one exercise through the exercise form's paste, and the pictograms are installed, the studio reads every request, finds a pictogram for each with the rules of 5.4, copies its picture into the document's own `images/` as `arasaac-<number>.png`, and writes an ordinary image where the request was. **The saved document never holds a request.**
5. A request the studio cannot draw where it stands, or that has no pictogram, is taken out and named; the intake says what happened ("5 pictograms placed; none for: idea, maybe").
6. The first time a document gets a pictogram the swap adds the credit as the document's last paragraph, once.
7. The person can look at the result in the studio as at any page, and change one pictogram for another that has the same word (5.4).
8. The feature sends nothing and starts nothing: the person carries the prompt and the answer, as with every prompt of the kit; the box, the prompt text and the swap run no model.
9. Everything works with no connection once the pictograms are here.
10. The pictures a document holds are copies: an update of the pictograms never changes a document, and the document stays self-contained, exportable and shareable with its credit.

### 5.2 Q1. The macro's shape

*Requirements*: unmistakable and impossible to confuse with the dialect; robust to a chatbot's habits; one line to teach; carrying what is needed.

**Driven.** Twelve candidate notations in eleven places of the studio (a prose line, a sentence, a list item, a table cell, a box, an exercise's blanks sentence, a pair, an option, a flashcard's text, and the two image fields): is the text kept as it was?

| Candidate | Read as text everywhere | Why it is not the one |
|---|---|---|
| `⟦pictogram: house⟧` | **yes** (the image fields take a path, so it is swapped before they are read) | nothing |
| `@pictogram(house)`, `(pictogram: house)`, `<pictogram house>` | yes | a chat window may take `<...>` for a tag and hide it from what is copied; `( )` is a sentence's own punctuation, and a lesson can say "(pictogram: a drawing)" |
| `⟨pictogram: house⟩`, `«pictogram: house»` | yes | ⟨ ⟩ is how a language lesson writes letters (and `markdown/README.md` already uses it as a placeholder); « » is the Persian fixtures' quotation mark (52 files) |
| `{{pictogram: house}}` | no: mangled in an option | `{...}` is a mark; `{{ }}` is the kit's own marker (113 files) |
| `[[pictogram: house]]` | no: a **blank** in a fill-in sentence | |
| `[house]{pictogram}` | no: the mark is eaten, only `house` shows | it is dialect syntax |
| `![pictogram: house](arasaac:house)` | no: garbled in prose | it is image syntax: the model would be writing a picture, which §18 forbids |

`⟦` and `⟧` (U+27E6, U+27E7) appear in **none of the 888 text files** I scanned (the code, tests, docs and guide sources of the repository), in no guide page and no fixture; the studio's intake keeps them through every fence shape (driven). They mean nothing to Markdown, so a chat window neither escapes nor renders them.

**Driven again: a prototype of the reader** (in scratch, not in the repository), over 3,000 real English keywords decorated the way chatbots decorate: straight, curly and guillemet quotes round the word, `\_` and `\*` escapes, the macro wrapped in `**`, `*`, `_`, `__`, `~~` or backticks, a line break inside it, non-breaking and zero-width spaces, a fullwidth colon, capital letters, in a sentence, a list, a table cell, a box, a bracket: **3,000 read correctly, 0 failures** (the wrappers that surround it are taken away with it); ten near misses (`⟦pictogram⟧`, `[pictogram: house]`, `{{pictogram: house}}`, an empty word, a word of 90 letters ...) **are not requests**; **0 macros found in the 200 shipped markdown files**. Reading is one regular expression and ~30 lines; a property test keeps it so.

**Recommendation**: `⟦pictogram: house⟧`. The word is English, singular, the name of the thing (for a verb without "to"). Alt text, caption and width are the studio's to write, not the model's. A leading number is reserved (`⟦pictogram: 6964 house⟧`) for the shortlist of 5.3, so it can come later without changing the notation.

**The paragraph the box adds (draft, 1,016 characters, shown in the size line like every box's):**

> **Pictograms.** Parseh can put a small picture (an ARASAAC pictogram) beside a word. You do not write pictures: you ask, and Parseh draws what it has. To ask, write ⟦pictogram: house⟧ — the English word for the thing, in the singular (for a verb, the word without "to": ⟦pictogram: eat⟧). Ask only for what a drawing shows: things, places, people, animals, foods, actions, qualities such as big or hot; never for an abstract word, a grammar point, a name or a number. Write it where the picture belongs: on a line of its own in the lesson, inside an exercise's text (an option, one side of a pair, the sentence with its blank, the prompt), or as the whole value of `front-image:`, `back-image:` or `image:`; never inside a list item, a table cell or a heading, and never inside a target-language mark. At most one for a word and one for an exercise line; most words need none. You cannot know which pictograms exist: a word without one is simply left without a picture. Never write an image line, a path or a number.

Also: with the box off, the reserved list gets one row (`⟦pictogram: …⟧`: Parseh's request for a pictogram, which you were not taught, so do not write it); the `revise` box says to keep pictograms already placed (`![…](images/arasaac-….png)`) exactly as they are; the skills' request header carries the box; a person's own prompt gets the flag.

### 5.3 Q2. How the model learns which symbols exist

13,829 pictograms and 15,770 keywords (186 kB without their numbers) cannot be listed. The three ways:

- **(a) The model names a word; the studio finds the pictogram.** Costs about 1,000 characters, needs no list and no page, works on every prompt page, and every id the model could invent is impossible because it writes none. Driven: of 201 concrete beginner words **200 are an exact keyword**; of 55 abstract ones 26 are (the prompt says: concrete things only, and absence is harmless).
- **(b) A shortlist from the page's own words**, `id · word · meaning` lines, the model picking by number. It needs the words of the work at the moment the prompt is copied (the exercise dialog has them: it sends the page; the library's prompt page has none), needs the **page's language list installed** to look the words up (Italian words give pictogram numbers only if `it` was fetched), costs 1–3 kB, and makes the model copy numbers (a wrong number is the new error; a number that does not exist, the other). It earns its cost only for the polysemous words (*light*, *play*, *bat*).
- **(c) Both**: a macro that takes a number or a word.

**Recommendation: (a), with the notation open to (b).** Reasons: it is the smallest thing that does what you asked ("the LLM communicates which one"), the two ways it can go wrong (a word with no pictogram, a word with several) are exactly the ones the intake can say and the person can mend, and **whether (b) is needed is measured, not guessed**: the stand-in trials of 5.9 count, for real exercise requests, the share of requests that found nothing and the share the person judges wrong. If more than about one in six placed pictograms is wrong, (b) is added to the exercise dialog only. *Which language's keyword?* English: every pictogram has it and it is the language Parseh's glosses are in; the other languages the person fetched are only the resolver's fallback when the model wrote a word of its own language (tried after English, among the installed ones) and, later, the shortlist's way into the page's words.

### 5.4 Q3. Ambiguity and absence

**Finding one.** Fold the word (Unicode, case), then try: the exact keyword; a keyword's plural (`plural` is in the list); without a leading "to", "a", "an", "the"; with a trailing `s`, `es`, `ing`, `ed`. (Driven on the beginner's 201 words: 200 exact, 1 by a suffix.) Nothing cleverer: no stemming library, no synonyms, no WordNet; a miss is a miss.

**Choosing among several** (84% of a beginner's words have more than one): leave out `violence` and `sex` (your 9C.5 (6); 170 pictograms), then prefer, in this order, the pictogram whose **first** keyword is the word (*house*: not "detached house"), the full drawing over a `schematic` one (the simpler drawing; 27% of the pictograms), then the lowest number (the oldest, so the choice does not move). One fixed rule, said in the guide. For *house* it picks 2317, the plain coloured house; for *bank* 3062.

**What happens to each request** (the intake says it in one line: "5 pictograms placed; none for: idea, maybe"):

| Case | What the studio does |
|---|---|
| Found, one pictogram | Placed |
| Found, several | The first by the rule is placed, and the intake counts it as "chosen from several" |
| No pictogram | The request is **taken out** and named; the exercise stays text only |
| Where the studio cannot draw a picture (a list item, a table cell, a heading, the middle of a sentence: section 3) | Taken out and named, never written as an image: it would show as `!casa` |
| An empty word | Not a request; left as written |
| A number (`⟦pictogram: 6964⟧`) | A word like any other: no keyword is a number, so taken out and named (the model is told never to write one) |

**Letting the person choose.** The picture's alt text is the word the model asked for and its file is `arasaac-<number>.png`, so the editor can recognise a pictogram and offer **Another pictogram for "house"…**: a small panel with the candidates as thumbnails (a `GET` that lists the candidates of a word; the PNGs are already on the disk), and the choice rewrites that one image line. An ordinary image can already be replaced or deleted in the editor. I recommend this over a review step before the document is saved: the library's paste is one step today, and a person judges a picture better in the page than in a list. It is the largest single piece of C; it can come after the first version without changing anything else.

### 5.5 Q4. Where a pictogram may appear

From the table of section 3: **in exercises** (an option, one side of a pair, the sentence with blanks, the prompt, a flashcard's `meaning`/`context`, and as the value of `front-image:`, `back-image:`, `image:`), where the studio draws them at 8 em; and **on a line of its own in a lesson**, as a figure. Never inside a sentence, a list item, a table cell or a heading: the studio garbles an image there (driven), so the prompt says so and the swap would take such a request out rather than write it. The swap writes:

| Where the request stood | Written |
|---|---|
| In an exercise's text | `![house](images/arasaac-2317.png)` (alt = the word; no width: the style sizes it) |
| The whole value of `front-image:` or `back-image:` | `images/arasaac-2317.png` |
| The whole value of `image:` or `image-answer:` | `images/arasaac-2317.png {width=20 align=center}` |
| A line of its own in the lesson | `![house](images/arasaac-2317.png){width=18 align=center}` |

(Today's exercise prompt forbids the model to write the image fields at all; with the box ticked it may write them, and only with a request as the value.) A caption is the alt text on a figure line: the English word under the picture, which a lesson can bear and an exercise never shows. **If you would rather the studio learn to draw an image inside a sentence, a list item or a cell**, that is a change to both renderers (`htmlgen.py` and `texgen.py`, both on the list of files the a0.4.3 branch also changed), and it is not needed for exercises: say so and it becomes a separate piece.

### 5.6 Q5. The receiver's rule

- **Where**: only when a **whole answer** comes in through the library page (**Paste LLM answer**, **Upload .md**: `api_create`) or **one exercise** is pasted into the exercise form. **Never in ordinary editing, never in a zip or a backup** (they are finished documents, not answers), never in a document typed by hand: a document that has not just arrived is not touched, so one that holds the text of a request by hand stays as it is.
- **The box is not consulted.** The studio cannot know which prompt the answer came from (it may have been copied on another computer, hours before, with the box since unticked), and does not need to: a well-formed request in an answer to a studio prompt is a request. What is checked is the other half: **the pictograms must be installed.** If they are not, the requests are **left as typed and said** ("the answer asks for 5 pictograms; they are not installed: Settings → Pictograms"), which is what brief 9C.4 says for the case.
- **How**, in order, so a failure leaves a whole document: read every request; resolve each; copy the pictures with `store.save_image`; write the images and the credit; save once. A copy that fails (a full disk) leaves that request in place and says so.
- A request found twice for the same word places the same file once; pasting the same answer again, as a new page, reuses the images (identical bytes).

### 5.7 Q6. The picture and its licence inside the document

CC BY-NC-SA asks for a credit with every use, nothing sold, and the same licence for what is shared. The document is the unit people share (a zip, a backup, a page of the web, a PDF), so the credit must **travel inside it**.

**Recommendation: one paragraph, added once, as the document's last paragraph, in ARASAAC's own short wording** (section 1: *Pictograms author: Sergio Palao. Origin: ARASAAC (http://www.arasaac.org). License: CC (BY-NC-SA). Owner: Government of Aragon (Spain)*), written by the swap the first time a document gets a pictogram and never duplicated (the studio recognises its own text). It is ordinary prose, so every export carries it with no work: the library zip and a document's zip hold the markdown, the web page and the PDF print it. The pictures are named `arasaac-<number>.png`, so wherever the document goes, every picture says where it is from.

- **When it goes**: when the person deletes it. The swap is the only automatic editor and it only ever adds. The guide page says: if you take out the last pictogram, take out the credit. (A derived credit, computed from the pictures at every export, would go by itself, but it would have to be taught to every export path, among them `htmlgen.py`, `texgen.py` and `store.py`, which the a0.4.3 branch also changed.)
- **A deck** (the Exercises door): an exercise copied into a deck carries its pictures but not the document's last paragraph. Recommendation: the deck's zip gets `LICENSE-ARASAAC.txt` whenever it holds an `arasaac-*.png` (one function, `decks.export_zip`). *Your call*; without it a deck of pictograms leaves Parseh with no credit.
- **The guide** already tells someone who shares such a document to give the credit with it and where the text is. It will add, in the studio's pages, that a document with pictograms is **for non-commercial sharing under BY-NC-SA**: you can study from it, print it, give it to a friend or a class; you cannot sell it or put it in something you sell.
- **Your own materials** (9C.5 (7)): if any book, deck or page of yours may one day be sold, pictograms in it are not available for that. That is the real cost of this feature, and it is yours to accept.

### 5.8 Q7. Size and freshness

- **300 pixels by default, 500 on request, 2500 never.** The studio never draws a pictogram larger than 8 em (136 pixels on screen, about 2.7 cm on paper), so 300 is sharp on a screen of twice the density and at about 280 dpi on paper; 500 helps only a figure drawn wide or a large print. A document gets a copy of what the installation has at that moment.
- **A document's pictures never change by themselves.** They are copies in the document's own `images/`; an update of the pictograms, a change of size, a pictogram ARASAAC withdraws, none of them reaches a document. That is also what makes it self-contained and exportable. The cost: a picture ARASAAC redraws stays the old one in documents that already hold it. (They are ordinary images: replacing one by hand works.)
- **Updates** (built): `_id` is stable; a changed record is asked for again with `If-Modified-Since` and the server says *unchanged* for the many whose record moved without the picture.
- **Languages against the document's**: English decides what the model is told; the others are the resolver's fallback and the shortlist's key (5.3). Fetch the language your documents are written in if you want (b) later; nothing else needs it.

### 5.9 Q8. Proof

What is built after your answers, and how each part is shown (every check seen failing first):

| Part | Check |
|---|---|
| The reader | A property test of the prototype's kind (3,000 decorated keywords, the near misses, no match in any shipped markdown) |
| The resolver | Against a tiny fake index in the manner of `tests/arasaac_fake.py`: exact, plural, "to", a suffix, the first-keyword rule, colour before schematic, the flags, no pictogram, an empty word |
| The intake | A document in, a document out: no request left, the images in place under `images/`, the credit once, the summary; not installed: left and said; each place the studio cannot draw: taken out and named; the same answer twice; a name conflict; a copy that fails |
| What it looks like | The result opened in the studio at 1280 and 390 pixels in three themes; the PDF built; the HTML page exported; a zip and a backup round trip: the credit in each |
| The prompt | The box present only when the pictograms are installed; its size in the size line; the reserved-list row when it is off; the `revise` sentence; the skills header and the own-prompt flag |
| **Stand-in chatbots** (`bin/standin.py`) | Given the ticked prompt for three real exercise requests: the share of requests that are correct, that found nothing, that stood where the studio cannot draw, how many were asked for per exercise (overuse), how many numbers were invented; apply each answer through the real intake and look at the result. **This is where "is (a) enough" is decided** (5.3) |

## 6. What is built after the answers, and where it touches the a0.4.3 branch

In order: the reader, the resolver (`lib/arasaac.py`, standard library), the intake in `markdown/app/server.py` and `store.py` (a function each, beside `api_create` and `api_adopt`), the box in `markdown/app/promptboxes.py` and the paragraph in `markdown/exlex/EXERCISES_PROMPT.md` / `PROMPT.md`, the studio's two prompt pages (`app.js`, `editor.js`), the deck zip's credit, the editor's *Another pictogram...* panel, the guide's studio pages and What's new. Files both branches changed (so edits are kept small and local): `markdown/app/server.py`, `markdown/app/store.py`, `markdown/app/static/app.js`, `lib/promptkit.py`, `docs/prompt-kit.md`. The ASR surfaces never get the box (`OPTIONS[...].where`); and what this feature may say is "the studio sends nothing", never "Parseh sends nothing".

## 7. What I need from you (a recommendation each; the first eight are brief 9C.4's Q1 to Q8)

1. **The notation**: is `⟦pictogram: house⟧` right?
2. **How the model knows**: it names an English word and Parseh finds the picture, with no list in the prompt; a shortlist from the page's words only if the trials show it is needed?
3. **Several or none**: one fixed rule picks among several (the word's own picture, the full drawing before the simpler one, the oldest) and a panel lets a person pick another; a word with none is taken out and named in the intake. And is the panel in the first version, or later?
4. **Where**: in exercises and on a line of its own in a lesson, never inside a sentence, list, table or heading (the studio would garble it) — or should the studio learn to draw them there?
5. **When it is swapped**: only when a whole answer arrives through Paste LLM answer or Upload .md, or one exercise through the exercise form; never in editing or a zip; the box is not consulted, and with no pictograms installed the requests are left and said?
6. **The credit**: one last paragraph in ARASAAC's short wording, added once and removed only by the person; a credit file in a deck's zip; the guide says documents with pictograms are for non-commercial sharing under BY-NC-SA?
7. **Size**: 300 pixels by default, 500 on request, and a document's pictures are its own copies that updates never change?
8. **Proof**: the plan of 5.9, and the stand-in trials decide whether (a) is enough?
9. **Your own materials** (9C.5 (7)): do you accept that a page, deck or book of yours with pictograms is for non-commercial sharing under BY-NC-SA?
10. **ARASAAC** (outside the code): the terms say nothing about fetching the whole set. Parseh is polite (one picture at a time, twelve minutes, named in the User-Agent). Do you want to write to ARASAAC before release (arasaac.org/contact-us), and is that pace right (`PAUSE` in `lib/getarasaac.py`; five a second would be forty-six minutes)?
11. **Fixed by 9C.5 and built that way**: 300 pixels by default, the whole set at once, the nine languages ARASAAC has words in (not Japanese, not Hindi), `violence` and `sex` left out of what the model is offered (the flags are kept).
