## [a0.5.7] - 2026-10-28
### Added
- Check as I answer: a document page's ⚙ → Exercises switch that checks an exercise the moment it is answered, instead of at Check exercises (a button of its own for choose-all and orderings)

### Changed
- Make drawings of N shown is done by a helper program at the lowest priority: it begins at once, looks through the documents under a count of its own, and no longer slows the rest of Parseh

## [a0.5.6] - 2026-10-28
### Added
- The library's Make drawings of N shown: every LaTeX drawing the documents shown need, made in the background without opening them, on the Working bar of every page and the hub, which counts drawings and moves with each one
- The exercises' prompt and the skill teach where a LaTeX drawing goes in an exercise, with an example: inside `prompt: |`, every line of the prompt indented under it

### Fixed
- A LaTeX drawing written between an exercise's fields was refused with one "unrecognized line" for each of its lines; it is now one message that says where a drawing goes

## [a0.5.5] - 2026-10-28
### Added
- The prompts and the skill say what each LaTeX theme's packages are for, including the ones its own lines load, and teach choosing the theme by the commands a drawing needs; the exercise prompt says where a drawing may stand in an exercise and how a follow-up's step writes one

### Changed
- Follow-up questions: a drawing in a step may be written with four colons, as a drawing is written everywhere else; one colon deeper, as the other fences of a step, is still how a page writes it

### Fixed
- A drawing inside an exercise or a step of a follow-up: its ✎ rewrote lines at the top of the page instead of the drawing, and now rewrites the drawing in place, indented and fenced as it was
- A follow-up that needs attention made the page script stop, and the form's preview say "Preview unavailable"; it is drawn as the exercise that needs attention, with what is wrong
- A page whose only drawings are inside exercises, or inside a follow-up's steps, now has the LaTeX box ticked in the prompt dialogs, and the steps' types are the page's

## [a0.5.4] - 2026-10-26
### Added
- Follow-up questions, a fourteenth exercise type: a chain of exercises answered one after the other, with a form for its steps, and the same in a deck (study and cram) and on paper
- LaTeX drawings: The .tex that was compiled and The whole log, on request, beside a drawing that cannot be made and under Settings → LaTeX drawings → Draw the sample, each with a Copy
- LaTeX drawings: the xskak set (its fonts and the packages it leans on) is one package row, got in one go

### Changed
- The phone's ⚙ sheet opens on a list of themes, each saying what it is set to, and a tap opens one theme; it rests half the screen high and can be made tall, which is remembered

### Fixed
- LaTeX drawings: an error in a package's file was said to be "LaTeX stopped without saying why"; it now says what and in which file, and a compile that makes no page says so

## [a0.5.3] - 2026-10-22
### Added
- Pictograms: a frame to look for an ARASAAC pictogram by a word, in any language fetched, with thumbnails and a preview of each; it opens from Settings → Pictograms (to look), from the editor's Pictograms… (a figure at the cursor, with ARASAAC's credit added once) and from the exercise form and the decks (a card's picture, an exercise's picture, a small picture inside the text, a figure in a jolly card)

### Fixed
- Settings → Pictograms: a page that watched a download or an update end could stay on "Part of it is here" until it was loaded again
- The editor: a figure, a recording, a video or an exercise added with the cursor still at the top of a page went in above the front matter, and the page stopped being its language

## [a0.5.2] - 2026-10-21
### Added
- Open a file… in the studio: a Markdown or zip file from anywhere on the computer Parseh runs on, from any device it lets in, edited through a copy and written only when you save

## [a0.5.1] - 2026-10-14
### Added
- The dictionary reads Persian written as it is said (خونه, میگم, اینجوری, دوس دارم) as the formal word it stands for, and says what it read and why: in the book's panel, the player's, the phone's sheet and the review of a transcript
- The editor: double-click a word of the preview to land on it in the source, and the preview can be drawn in a tab of its own, as the finished page, from what you type
- Download ▾ of a studio document: LaTeX + media (.zip), the .tex with its pictures, fonts and LaTeX drawings (as compiled PDFs and as the .tex they came from), ready for Overleaf

### Changed
- The doors' pages, and the pages inside Settings, lose their one-line subtitles, and the books' and videos' pages are titled Books and Videos
- The reasoning workspace of an external chatbot review is one prompt by default, and dividing it into several is an option; the connected model's workspace is one region by default, with small regions as an option
- Use this transcript is never held back by a review that is unfinished, by settings that changed, or by one edit that does not fit: that edit alone is left out and said; a pasted answer is read row by row
- A chatbot's or model's review says what it decided for every word it was asked about, changed, agrees, not sure or no answer, and a walk through its answers asks for each whether to take it; the sure edits can be taken together
- An answer read loosely, in any review method, says so on its words (≈), says what was forgiven, and the word can be asked again by itself; a change that could not be used is no longer shown as agreement

## [a0.5.0] - 2026-10-07
### Added
- ⚙ page: one panel of settings on a book, a video, a document and its editor and an exercise deck, on a computer and on a phone
- Page zoom, 70 to 200 %, for all of Parseh, also in the installed app
- Levels have names, per language, which you can change and which follow you
- Diacritics: put the vowel marks of Persian and Arabic away from a book's first two levels and a video's lines
- Review later: flag a chunk or a phrase, then go to it, test yourself, copy the list or make its card; a hub door and a page for every flag

### Changed
- Plainer names on the page's own buttons: keep going (now remembered, and following you), between repeats, hide bars, highlight, keep in view, keep video, beside the text, kana only, pinyin only
- One colour control on every page: the studio's sheet has no theme menu of its own
- The foot of the hub, Settings and the guide: GitHub leads to Parseh's repository, and parseh.io is a link of its own beside it
- The name Parseh is set in TeX Gyre Chorus in the bars and on the hub's title

### Fixed
- Two writes at once to the settings file no longer fail
- Colours set on a phone's document page repaint its sheet

## [a0.4.4] - 2026-10-06
### Added
- Parseh lives in the parseh-io organisation on GitHub; Settings → Updating Parseh looks in the new repository
- The guide is at parseh.io/guide, under a bar that leads to Parseh's site; pages exported from Parseh link to it for good
- The phone app's icons are published with the guide again
- Every address Parseh writes for itself is kept in one place, lib/project.py
- release.py links asks every address Parseh names and says what each answers
- Settings → About shows a few friendly numbers: cards answered, videos and books on the shelves, since when
- From a0.4.2: prompts of your own, the studio's prompt in parts, IPA and short-vowel options, skills for your chatbot, a book made by an agent from any device, pictograms (ARASAAC)
- From a0.4.2: a video's vocabulary in the books' entries, notes on a video's phrases, a sound in place of a video, flashcards that turn
- From a0.4.3: Whisper models for each language, optional exact word times kept through every edit of a transcript
- From a0.4.3: a transcript workspace with LM likelihood, an LLM connection, a reasoning workspace and chatbot copy-and-paste review
- From a0.4.3: partial-word colours in the studio, mobile arrow keys that skip, a card maker for books and videos

### Changed
- Speech to text lists the Whisper program first, above the second pass and the models
- a0.4.2 and a0.4.3 were finished but not released on their own: their full entries follow

### Fixed
- LLM Integration, LM likelihood and About are drawn with their own stylesheet and end in a foot like the other doors
- The README and the settings pages link to guide pages that exist

## [a0.4.3] - 2026-10-05
### Added
- A standalone reasoning-workspace CSV checker, shipped with the helper and skill, for draft checks, exact source spans and required-entry coverage
- Standard and language-specific Whisper models in one pinned catalogue, with independent resumable installs, per-language model choices and model provenance in transcription jobs
- Optional Hugging Face downloads for Persian fast/accuracy, Arabic, Italian, Hindi fast and Spanish, including merged LoRA models, matching offline assets and original licence notices
- Settings → About with version, author, launch-script locations and installation information using the host's native paths
- Saved pending transcription reviews, with pause/resume from Videos across server and browser restarts
- Checked-word locks, selected-section review, single-word LM likelihood and bulk selection of the latest method's best choices
- Optional similar-sound and candidate search-probability filters for additional model-derived words; every genuine Whisper alternative remains eligible
- LM likelihood review with installed-model selection, raw-token candidate search, numerical rankings and an isolated CPU/GPU scoring worker
- External chatbot copy/paste review for suspect words, whole text and reasoning workspaces, with bounded prompts, validated answer import and downloadable text/CSV workspace files
- Additional reasoning workspace review with numbered transcript blanks, CSV evidence, isolated Python tools, separate model selection and two-pass word progress; existing review modes and thresholds stay unchanged
- Browser transcription workspace with video beside the transcript, word/caption replay, ±1/2/5-second playback controls, caption filters and a persistent word editor
- Brief word playback with automatic pause, installed-dictionary suspect flags and original/replacement meanings in browser transcript review
- Dictionary meanings for native Whisper alternatives alongside their recognition scores in the word inspector
- Native faster-whisper beam alternatives mapped to source words, with sequence log scores kept separate from word probabilities
- Browser Settings → LLM Integration: a reusable OpenAI-compatible endpoint, host-local credentials, model discovery and Unsloth run-settings link import
- Review-first Whisper results with short sentence LLM replies, word-count progress, local failure recovery, retry of unresolved words, keyboard edits and inspectable responses
- Remote installed-model profiles from Studio links, with explicit API loading of quantization, KV cache, context and vision options
- Separate models, prompts and downloadable skills for suspect-word and whole-text review, including confident words and contiguous ASR spans
- Individual pending draft decisions and explicit Use this transcript preserve the existing box and timing guards
- Optional, local exact word times for every speech-to-text language, with hash-pinned int8 CTC networks and a remembered add-page switch
- A Parseh-made transcript carries its word timing through the add-page editor and stores it with the matching video
- Two transcript tidy cues: the existing text cues and recorded pauses
- Mobile-mode keyboard arrows skip narration or video by the selected amount
- Partial-word foreground colours in Studio, with selection-first editing, Unicode-safe boundaries, one-word linguistic clouds, PDF and standalone-HTML output

### Changed
- Transcript word editors can include adjacent words for a short-span correction; reasoning workspaces can join split words across suspect/confident neighbors
- Transcription opens directly into a shared editing workspace; correction methods are reusable tools, with optional automatic and later per-word/section Whisper rechecks
- All four transcript-correction methods are labeled experimental; LM likelihood offers no-cutoff, suggested 0.1 and custom cutoff choices
- LLM settings and transcript review show simpler controls, with technical setup and numerical diagnostics folded away
- Markdown and exercise-deck cards made from books or videos mark target and context fields as the target language automatically
- Studio and exported word clouds are linguistic only; foreground colour is applied from the source editor

### Fixed
- Speech program and model downloads no longer fail before their progress starts
- Exported guides include the segmented-colour parser needed for independent builds
- Speech model notices list every catalogue source and converted package with its own licence
- Persian dictionary lookup recognizes colloquial copulas and combined nominal endings, with direct entries preferred and dictionary-backed stem guards
- LM likelihood candidate search preserves source whitespace with SentencePiece tokenizers, including PersianMind
- Partial-word colours compile and remain visible in PDFs, including headings, target-language blocks and exercise prompts

## [a0.4.2] - 2026-09-30
### Added
- Glosses an LLM writes are aligned to their chunks: a meaning says what its own words say, in the text's order
- Every prompt is assembled by one kit from its instructions, its answer contract and its data, and opens with a version line
- The LLM row: one control for every prompt, saying its size before the copy, on the studio, the exercise dialog, the add page, the tidy, the player, the reader and Ask LLM
- A video's vocabulary in the books' entries, asked of the chatbots and drawn as in the reader, with macro buttons that say what they write
- A book made by an agent in place, from any device, its text given in parts, watched from the library, steered through asks, finished with one button
- Prompts of your own, from a menu at every copy button, exported and imported under Settings → Your prompts
- The studio's prompt in parts you tick, with presets, a level and a length, and the exercise dialog pre-ticking what the page uses
- Options of a prompt: the transliteration in IPA, and the short vowels of Persian and Arabic
- Every language's conventions carry a worked example and one vocabulary convention
- Skills for your chatbot: gloss, markdown and book, built on request and downloaded under Settings → Skills
- A sound in place of a video, with its waveform
- A video phrase's note can be edited, and a ✱ notes button lights every phrase that has one
- A vocabulary or opposites flashcard's example, notes and source go on the side the card turns to
- Settings → Pictograms (ARASAAC): the symbols and their words fetched on request, with their licence

### Changed
- The LLM prompt page's Edit prompt, Save custom prompt and Reset to default give way to the prompt menu

## [a0.4.1] - 2026-09-29
### Added
- Speech to text, optional and local: a transcript made on this computer while adding a video, from a film on this machine or a YouTube video recorded through the tab
- Settings → Speech to text: the program, two Whisper models and the processor, open to any device let in
- The graphics card is used only once Parseh has proved it works; the CPU always does
- A YouTube video recorded for its transcript keeps that recording's waveform when it is added
- Hover ⏸ in a book's reader, in both interfaces: the narration waits while a gloss is open
- Edit times by ear in a book's header, and a video's timings, open where the listener is

### Changed
- An update, and going back, leave the speech program and its models as they are (stt/)
- Typing in the transcript, the address or the film's path makes a prepared LLM prompt stale
- The offline page's Try again says that it tried, and Go back is a button of its own

### Fixed
- A page not kept on the device opens from a computer that is only slow, instead of "Parseh cannot be reached"
- Stopping the tab share after a waveform was drawn no longer pauses the video or resets its speed
- The transcript editor saves the draft as it hands the transcript back

## [a0.4.0] - 2026-09-28
### Added
- LaTeX drawings: a ::::latex block, or [...]{latex} inline, compiled by LaTeX itself, beside the formulas MathJax draws
- The same drawing on screen, in the PDF, in an HTML export and on a phone; a live preview kept only once it is saved
- A drawing that cannot be made shows its source and one line saying why, with the button that mends it
- The sheet that draws a block: its preview filling its pane beside the source, a caption, size and position folded away
- Settings → LaTeX drawings, styled like the rest of Settings: named themes of packages, languages, a font, a preamble and a compiler
- Themes exported and imported as files; a rename rewrites every block that names the theme
- A theme's packages beyond the base kept in Parseh's own folder, listed with the base, asked about and gotten one at a time
- More packages to pick from: syntax trees and dependency arcs, the IPA, pinyin over Chinese characters
- A deck's exercises filtered by where they came from, beside its text and tag filters
- Flashcards that are asked both ways: both (random) and both (repeat), the second two linked cards in a deck
- The transliteration cloud works on an exported page and on the guide's own words
- On a phone's video, the subtitles have a text size of their own, reached in full-screen too

### Changed
- Every Settings page starts with the bar of its doors, Network included
- Deleting a document asks in the studio's own window, and the card leaves the list at once
- Documents, decks, bundles and shelves are stored in a new shape: going back to a0.3.3 says so first
- The size sliders of books and videos reach further, at both ends

### Fixed
- Exporting a page to HTML from another device could land on "Parseh cannot be reached": it shows a bar now

## [a0.3.3] - 2026-09-25
### Added
- Estimate the next N seconds, beside estimate the rest

## [a0.3.2] - 2026-09-25
### Added
- Estimate the rest by the sound: boundaries placed in the pauses of the waveform, in books and videos
- Update Parseh from Settings, from GitHub or a zip, to any version, keeping your content and settings
- Releases on GitHub, one zip per version; Parseh shows its version on the hub and in Settings
- Downloads show their size, progress and time left, can be stopped, and resume where they stopped
- On a phone, the dictionary opens in a sheet, and sparsely glossed books and videos mark their glossed chunks

### Changed
- Dictionaries and the other downloads moved to Settings → Reading help, laid out by language
- "Offline" only when the computer is really gone, with ↻ to check again
- Who may change a setting is decided per setting: Network and updates on the computer only
- Languages you add are kept in config/
- Exported pages open on sepia

### Fixed
- Pages of other websites could make Parseh change things
- A phone could read the Wi-Fi pairing code
- The test suites wrote into config/

## [a0.3.1] - 2026-09-24
### Changed
- Fill in the blanks and matching: a click opens the word cloud in the browser too
- Flashcards in the PDF are cards to cut out and fold
- Answering an exercise no longer copies the word to the clipboard

### Added
- On a phone, a video on the whole screen can show the captions around the one being said
- On a phone, a dictionary button in the gloss cloud

### Fixed
- A framing caption drawn dark on dark over a video on the whole screen

## [a0.3.0] - 2026-09-23
### Added
- Videos and Markdown for mobile
- Settings, with Network: who may reach Parseh, the port, your own certificate
- A phone on the Wi-Fi is let in once with a pairing code
- Notes open at once, and the reader fetches the ones near you ahead
- On Android, a kept book downloads in the background, its text first
- What is kept on a phone is checked file by file
- A kept deck brings its exercises, pictures and recordings
- Delete a gloss, with undo
- Gloss a stretch with an LLM, in books and videos
- HTML export of markdown and crammed decks

### Removed
- The "draft" flag of books and videos

## [a0.2.0] - 2026-09-22
### Added
- PWA mobile version
- Book and Exercises for mobile
- Cram mode shows which exercises were more difficult at the end of a session
