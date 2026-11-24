# Parseh: the video player

A video with its transcript underneath, glossed the way the reading editions
under `../books/` are: the target language split into small
phrases, and a hover (or tap) on any phrase opening a cloud with the
transliteration (and, for Japanese, the kana reading above it), the
vocabulary and the meaning — the same fonts, the same palette, the same
conventions as the books. The player speaks every language of the registry
(`../lib/languages.json`, the only list of them) and glosses each of them in whatever language the
video says its glosses are written in — English unless it says otherwise,
which is what every video written before the key existed says. The Persian
examples below are examples, not the rule.

The player is one of the doors of **Parseh**, the toolbox served as a
whole by `../serve.py`: it lives at `/youtube/` on the one https address,
beside the books at `/books/`, the studio at `/studio/` and the exercise
decks at `/exercises/`. This directory
holds its pages (`lib/ytpages.py`, assembled per request), its pipeline, and
the Anki deck store under `anki/` that the book reader writes into too.

## Run it

```
cd ..                   # the project root
./serve.sh              # everything, in the background, https on port 7654
./serve.sh status       # is it running
./serve.sh stop         # stop it
```

Then open <https://localhost:7654/youtube/> (the browser warns once about the
self-signed certificate; accept it). Serving needs only stdlib Python; the
script activates the `ilya-frank` conda environment when it exists, as every
script in this project does. A YouTube video streams from YouTube in the
browser, so the page needs internet — the transcript works without it. **A
video that is a file on this machine needs no internet at all**: it is served
from `videos/<language>/<id>/media.<ext>` by the same static route that
serves a book's narration, which answers HTTP Range, and that is what lets it
seek.

## A film on this machine

A video does not have to be on YouTube. Give `/youtube/add/` the **path to a
file** instead of a URL — `.mp4`, `.webm`, `.mkv`, `.mov`, `.m4v`, `.avi`,
`.ogv`, or a **sound** (`.mp3`, `.m4a`, `.wav`, `.ogg`, `.flac`, … `bundle.MEDIA_EXTS`),
which `video.json` then marks `"kind": "audio"` and the player draws as a bar of
its waveform instead of a frame — and its transcript may then be a **`.srt` or `.vtt` subtitle file**,
pasted whole: it is translated into the transcript format the rest of this
door already reads, cue numbers dropped, `<i>` tags stripped, and the rolling
repetition of automatic captions collapsed to what is new in each cue.

The film is **hardlinked** beside the transcript, which costs no disk and no
time even for a two-hour film; where the filesystem forbids a link (another
disk) it is copied. Either way what lands is a real file called
`media.<ext>`, and the file being there is the whole of what makes the video
local — nothing in `video.json` declares it, so there is no field to keep
true. It is gitignored, the way a book's `audio/` is.

Everything else is the same video: the same glossing, the same hover clouds,
the same dictionary, the same Anki cards. Two
differences follow from there being no YouTube: `video.json`'s `url` is empty
(no address is invented), and an Anki card's source link points at the player
here rather than at youtube.com.

**The download button hands over the film with the glosses.** A video that is
a file packs `full` by default — the zip carries `media.<ext>` STORED rather
than deflated — so the video that comes out of a bundle on another machine
plays there. `?media=text` on the download address leaves the film behind for
somebody who wants only the words. (A book's narration defaults the other
way, to `linked`: a book without its recording is still the book, and a video
without its film is a transcript of something nobody can watch.)

The index is a two-level tree: `/youtube/` lists every **channel** that has
at least one video, grouped under language headings with the toolbox's
row of language chips above them, and `/youtube/c/<channel>/` lists that
channel's own videos — there is no page that lists every video flat across
channels. A channel is just a video's own `channel` field in `video.json`;
nothing else declares one, so a channel appears the moment its first video
does and disappears the moment its last one is removed. A video's language
is its `video.json`'s `language` (a registry code; absent means Persian,
which is what every video written before languages existed is), and the
video lives under that language's folder: `videos/persian/<id>/`,
`videos/japanese/<id>/`. The player page's URL, `/youtube/v/<id>/`, does
not carry the folder — the id is unique on its own.

## Add a video

**From the page** — <https://localhost:7654/youtube/add/>, the *Add a video*
card on the videos page. No Claude Code, no access to the project:

1. On YouTube: *…more → Show transcript*, copy the whole panel, timestamps
   included; paste it with the URL. **Pick the video's language** — the
   language being taught; the select defaults to the language the chips
   last picked. The glosses are English unless the video declares another
   language (`"gloss"`, below). Pick a word list if the video belongs to a
   family that has one.

   Some panels repeat an extra line on every caption that the parser does
   not already know to drop — a second timestamp, or a spoken-duration line
   in digits the parser was not told to read as one for that language. If
   the pasted box has a line like that sitting at the same position in
   every group, *Drop pasted lines where line-number mod … equals …* (below
   the transcript box, first line counted as 0) removes it from every group
   at once — e.g. mod 3, remainder 1 for a panel that repeats as timestamp,
   duration, caption.

   **What YouTube heard is often not what was said**, and it is cut in the
   wrong places: a sentence split across two captions, a caption that starts
   three seconds late. *Edit the transcript…* opens a small
   [Subtitle Edit](https://www.nikse.dk/subtitleedit) over the panel — every
   caption in a list, its words in a box and its start between the six steps
   of the book's timing editor — **−1 −.5 −.1 … +.1 +.5 +1**, so a caption is
   moved a second, a half or a **tenth** at a time; ▶ plays it, from its start
   to where the next one begins, which is how a nudge is answered. ✂ cuts one
   in two where the cursor is, ⇣ joins the next to it, ✕ deletes, *+ caption*
   adds, and *shift … s → move them all* moves every start at once (a panel
   from a re-upload is often late by the same amount throughout). A caption
   runs until the next one begins, so moving one moves where the one before
   it ends.

   **After a video is added**, that editor is gone — its transcript is what
   its annotations were checked against — but *the timings*, in the player's
   header beside *video info*, moves a caption's **start** and nothing else.
   It is the door `youtube/lib/captimes.py` opens, and it is narrow on
   purpose: a start moved in `annotations.json`, `transcript.txt` and any
   note anchored to that caption (under `markdown/`), all
   together, leaves every rule `check_annotations` enforces exactly as true
   as it was — the count is the same, the two files still agree to within
   nothing, and no word was touched. It runs the checker before and after
   and refuses whatever its own edit would break. Same sheet the books use
   (`lib/timeline.js`), except that a caption has one number per boundary
   and so no *split*. A film on this machine draws its waveform from the
   server (ffmpeg, as for a book); a YouTube video has none unless you press
   *● draw the sound*, which plays it once while recording this tab
   (`lib/tabcapture.js`) and keeps the shape — one number every 50 ms, as
   `waveform.json` beside the video, so it is done once. Chrome and Edge
   only; without it the six steps and ▶ still move a caption by ear. **,** and **.** take up the caption
   before and after (so do `[` `]` and PageUp/PageDown), **F** brings the
   view back onto the one being timed, **S** drops the line the arrows would
   move into the middle of the nearest stretch where the sound falls away
   (grey where there is no waveform to look in), **E** lays a fresh guess
   over every caption *after* that line — a slice each, in proportion to how
   much text it has, with nothing before the line touched — and **Space**
   plays it; none of them while a time is being typed.

   **✨ tidy up** reads the whole transcript at once, for the mess an
   automatic one is: YouTube cuts its captions where it runs out of room,
   never where a sentence ends. It lays every word across the time its
   caption covers (in proportion to how long the word is — `lib/timestamp.py`'s
   own first guess for a narration; a language written without spaces is laid
   out character by character, as that file lays out such a book), cuts that
   stream into **sentences**, and gives each one a caption of its own starting
   at its first word.

   **Every language the toolbox teaches gets it**, because each gives at
   least one cue:

   - **the stops the transcript already carries** — YouTube punctuates its
     automatic captions for English, Italian, French, German, Spanish,
     Japanese, and for those this is nearly the whole job: a full stop is a
     sentence end, and cutting at it *across the caption edges* is what the
     transcript itself cannot do. (Read here rather than through
     `draft.sentences`, whose "a lower-case letter after a stop means it was
     an abbreviation" guard is right for a book and exactly wrong for an
     all-lower-case ASR transcript; its other guard, that `J.` and `1.` end
     nothing, is kept.)
   - **the verb**, where the language puts it last and nothing is punctuated
     — Persian, Turkish. `lib/chunker.py` already knows which words those
     are: its function-word lists give the copulas (`است`, `نیست`, `هستم`)
     and the dictionary gives the verbs (`دارد`, `می‌گوید`).
   - **a pause** the caption edges betray, **a verbless question** at a
     caption's edge (`یعنی چه`), and a `[موسیقی]` the transcript wrote on a
     line of its own, which keeps that line. These belong to every language.

   Each sentence gets the stop its language prints (`.`/`?`, `؟` for the
   Arabic script, `。`/`？` for CJK, `।` for Devanagari), and a question mark
   where one of the language's own question words opens or closes it — the
   bare-transcript languages list theirs in `lib/lang/<code>.chunk.json`; a
   punctuated one needs no list, the mark being in the text already.

   **Not one word changes** — the letters that come out are the letters that
   went in (`tidy._same_words`), and a tidy that cannot promise that gives the
   captions back untouched. It is a guess, so it is a button and not a rule,
   and *undo the tidy* is one press away.

   **What gates it is the dictionary, and nothing else.** Not because a full
   stop needs one, but because everything done *above* a full stop is a
   question about a word — is it a verb, is it a name. Without the dictionary
   the button says which one to install; install it and it works, with no
   reload.

   **✎ or with an LLM…** is the other road, the one the glossing step already
   walks: it copies a prompt that explains the same job — one caption per
   sentence, keep the words, punctuate, time each caption at its first word,
   correct only a plainly misheard word — with the transcript itself inside
   it. Paste the answer back in the same panel and it is read as an ordinary
   transcript. The two fail differently, which is why both are here: the
   algorithm cannot hear a misheard word and will never invent one; a model
   hears the sense and may invent anything, so the editor says how far the
   letters moved when its answer goes in. The prompt needs nothing installed.

   **A tenth of a second is carried by the panel itself.** The clock line
   takes a fraction — `0:08.4`, written only where there is one, so a panel of
   whole seconds goes back as whole seconds and every transcript written
   before reads exactly as it did — and the player seeks to one as readily as
   to a whole second. A pasted `.srt` keeps its cues' own fractions now
   instead of being truncated to the second.

   It round-trips through the box: the captions are read from the pasted text
   and written back to it (`POST /youtube/api/transcript`,
   `check_annotations.parse_transcript_text` and `transcript_text`), so what
   the next step reads is a panel in the one format everything downstream
   already knows. **Only while the video is being added** — once it is in the
   player its transcript is what its annotations were checked against, and
   there is no route here that rewrites it.
2. *Prepare & copy the prompt* puts a self-contained prompt on the
   clipboard — what the method is for, the generic conventions, the rule on
   what a meaning says (`../docs/meaning-rule.md`), the language's own
   conventions with its worked example (`## Example` in its file, so a fresh
   install has one and no video of the shelf is quoted), the word list, the
   captions numbered with their start times, the plain ones marked as plain.
   Paste it to any LLM.
3. Paste the answer back (one message or several) and *Check & add*. The
   page checks it with the pipeline's own tools, parsing the transcript
   with the language you picked, writes `videos/<language>/<id>/`
   (`transcript.txt`, `video.json` with `language` and `title_native`,
   `parts/*.json`), runs `merge_parts.py` and `check_annotations.py`, drops
   the batches, and
   links the player page. A failing answer writes nothing and lists the
   captions to fix.

The prompt's text is [`docs/chat-prompt.md`](docs/chat-prompt.md), a generic
recipe naming the language; it embeds [`docs/conventions.md`](docs/conventions.md)
— what is the same for every language: the chunk size, the fields, the
repetition rule, plain captions — then the rule on the meaning, and then the
language's own block,
[`../docs/lang/<code>.md`](../docs/lang/): what the text field carries, the
transliteration scheme, the vocabulary line, what never to gloss, how to
chunk that language. Both are about the language being **taught**; what
language the glosses come out in is the video's `gloss`, and each
conventions file says which of its rules turn on that and which do not — a
transliteration scheme does not, a decision about which words a reader
already knows does. So there is one copy of the rules for both ways of
working, and one per language of what differs.

**From the older watching-edition format** — a directory holding
`segments.json`, `sections.json` and a `script.tex` in the books' `\ch`
form: `python3 lib/import_old_video.py "<that directory>"` rebuilds the
transcript, converts the script into parts, and runs the same merge and
check. A `\chp` of Persian the old edition never glossed becomes a chunk
marked `"plain": true` — shown as text, never a target; the checker asks
nothing of it. Only an import writes that mark on a chunk of the target
script (the one exception is a Latin-script target, below, whose annotator
marks an aside so). A chunk with no gloss is another thing: not plain, just
still to be glossed (*Glossed, blank, or half way*, below).

**By hand, in Claude Code** — for a long video that wants a glossary of its
own:

1. Copy the transcript as above.
2. Open a Claude session in the project root and paste it the contents of
   [`PROMPT.md`](PROMPT.md), then the video URL, then the transcript.
3. Claude fills `videos/<language>/<id>/` and runs the checks; when
   `check_annotations.py` says `0 error(s)`, reload the index.

### The chunk, per language

A chunk is `{"fa": …, "tr": …, "voc": …, "en": …}` whatever the language,
and two of those keys are named after languages they are not tied to: `fa`
is the caption's text in the target language and `en` is the gloss beside
it — the names Persian and English left behind when they were the only two
languages here, kept because every tool and every stored file uses them.

Which language the gloss is *written* in is `video.json`'s **`"gloss"`**, a
language code; absent it is `en`, so every video made before the key existed
means exactly what it always meant. `language` is what the video teaches and
`gloss` is what its glosses are written in — an Italian who is learning
English watches a video with `"language": "en", "gloss": "it"` — and the
gloss language need not be one the toolbox teaches, since writing *in* a
language asks nothing of it: the codes are every taught language plus the
prose-only ones (`../lib/languages.py`, `GLOSS_CODES` — the same set the
studio takes for its `lang:`), so `pt`, `nl`, `ca` and `ru` are as welcome as
Persian.

A **reading language** (Japanese) adds
**`kana`**, the reading of the whole chunk in kana, beside `tr`; the
checkers require it on every glossed Japanese chunk and ignore it
elsewhere. `tr` is required where the language says so (`require_tr` in the
registry — a Latin-script language may omit it). The player shows `kana`
above `tr` in the cloud, sets the transcript's direction and font from the
language, and
splits words the language's way (a Japanese chunk, which has no spaces, is
one word).

A language that **divides its chunks into words** (Japanese and Chinese)
adds **`"words"`**, one string placed after `fa`: the chunk's text parted
into words by spaces, each word's reading after it in ASCII parentheses —
`"今日(きょう) は 天気(てんき) が いい です ね"`. Joined with nothing between
them the words must be `fa` exactly; `kana` (or `tr`) stays the reading of
the whole chunk and is only compared with the words, to warn. A chunk
without `"words"` is legal, and draws as it always did. With it, the
transcript sets the reading over each word, the cloud's **I know this** is a
word's, the dictionary looks up the words, and the **kana** (**pinyin**)
button turns the transcript into the reading alone, at the size of the text.
The words start from the machine's: the prompt lists its division under each
caption for the model to start from and correct, the words a pasted answer
left out are proposed when it is pasted in, `../lib/fill_words.py --video
<dir>` gives a video already here the words it lacks, and `--json` a part
being written. A video drafted from its transcript (*Write it yourself*,
below) gets them too, with each chunk's reading — `kana`, or the pinyin of
`tr` — starting as theirs, run together, punctuation and all. The editor's
*words* strip corrects them — cut a word, join two, move a boundary with
<kbd>←</kbd> <kbd>→</kbd>, *edit as text*, or *propose* again. A video read out
of its written order (kanbun) is marked on the **video info** sheet, which
writes `"reorders": true` into `video.json`. `../docs/lang/ja.md` and
`zh.md` hold the conventions.

## Write it yourself

**Speech to text, optional.** Under the transcript box the add page has one
block (`lib/addstt.js`) that can make the transcript on this computer with
Whisper instead of pasting it: the models and the processor are picked in the
block, from what `POST /lookup/api/speech` says is installed (`../lib/getstt.py`;
installed in Settings → Speech to text), and the job is `../lib/sttjobs.py`'s
seven routes under `/youtube/api/transcribe/`. A film is read by the computer
itself, no playback, any browser; a YouTube video is played from its frame on the
page while `lib/tabcapture.js` records this tab's sound and sends it, in
pieces, with the marks that put it on the video's own clock, and the shape of
the sound, which `wavefile.py` holds until the video is added — `api_add`,
`/api/empty` and `/api/local` take a `wave` token and put it beside the video as
`waveform.json`. The result goes into the box the page already has, in the
panel format (`sttpanel.py`), never adds the video, and makes a prepared
prompt stale. There is nothing of it in `player.js` or on `/youtube/v/<id>/`, and
`tests/test_addstt.py` says so. The page itself only says what the video, the
language and the box are (`ParsehAddStt.mount`); tests: `tests/add_stt.mjs`,
and section n of `tests/youtube_capture.mjs`.

**Start it empty.** Below the prompt on the add page is a second lane that
uses no model at all: the transcript as it stands, every caption cut into
sentences, one chunk per sentence, every `tr`, `voc` and `en` blank. Where a
sentence breaks into phrases is the editorial heart of the method, so nothing
guesses at it — you split a chunk yourself, which is an addition to a blank
page rather than an argument with a guess. `../lib/draft.py` is the same
thing on the command line.

**Glossed, blank, or half way.** A chunk with *nothing* written in it is
legal in every video, at every stage: `check_annotations.py` asks nothing of
it and counts it in one note (*N of M chunks have no gloss yet*). A chunk
**half** written — the meaning typed, the transliteration still to come — is
what the middle of the work looks like, and the player's editor saves it so,
a box at a time; the checker lists it as an error until it is finished, the
⤓ bundle door only notes it (a video goes out and comes back in the middle
of its glossing), and an LLM's answer never writes one: the add page refuses
an answer that leaves a chunk half written, and the region fill (an LLM
glossing a run of captions of a video already in the player) drops that
chunk and says so. What the editor refuses is the step backwards: emptying
one box a finished gloss needs while the rest stays. Emptying every box —
**delete gloss** — takes the whole gloss off and leaves the chunk blank, its
text, word line, colour and note kept.

**Glossing in the player.** The gloss cloud carries four colour dots and a ✎.
The dots mark the phrase in the reading editions' own four colours — red,
blue, orange, green — which no tool does anything with but check that it is
one of the four: it is the reader's own mark, and the two doors show them in
the same shades. The ✎ opens the
chunk's fields, each named the way this language names them — the note
under the meaning among them: a model's aside is the person's to change, and
emptying its box takes it off — and
<kbd>Ctrl</kbd>+<kbd>↵</kbd> saves. `lib/annwrite.py` writes it: the edit
goes through `check_annotations.py` **before** anything is written and is
refused, in the checker's own words, if it introduces an error the file does
not already have; the file is written atomically and in the shape it already
has — the same indent, the same key order, the same unescaped target script —
so an edit made from the player lands as the edit a hand would have made.
Editing `fa` may vowel a chunk or repunctuate it but may not change its
words: the chunks of a caption have to go on reproducing that caption, and
the caption its line of `transcript.txt`.

**When YouTube heard wrong.** The pasted transcript is sometimes simply
wrong, and the check that guards the video would otherwise make the mistake
permanent. At the foot of the editor's fields is *the transcript* — **this
phrase need not reproduce `transcript.txt`** — which writes `"free": true`
on the chunk (`docs/conventions.md`). The edit that changes the words is
then written instead of refused, the caption's text is rewritten from its own
phrases, and `check_annotations.py` reports that caption as *not checked*: a
warning counting them, not an error. Send the mark with the edit it permits;
to go back, put the words as the transcript has them and clear the box in the
same save. It frees the whole caption, because the whole caption is what is
compared — the reading editions' own rule, per paragraph (`lib/reading.py`).

**A note in the seam.** Between any two captions there is a `+`. It makes a
markdown file under the video's own `markdown/` directory, written with the
studio's editor and read in a frame over the page — never inline, because the
transcript is the point. A note is anchored to a caption's start, so it
survives a re-chunk, and *the timings* rewrites that anchor when the start
moves (`captimes.py`); one whose caption is gone shows at the
end, marked adrift. Notes travel in the ⤓ bundle. Nothing about them is in
any prompt: they are for people.

**Where a phrase ends** is moved by the three buttons beside *save*: ✂ *cut in
two*, *join next* and *join previous*. A phrase divides at the language's word
separator and nowhere else (for Japanese, between any two characters), which
is the fidelity check read backwards; a join puts the texts end to end with
that same separator, so the caption is reproduced character for character.
Everything else — the transliteration, the vocabulary entry by entry, the
meaning — is *proposed* in boxes you type over, and the vocabulary entries
cross between the halves with an arrow. `../lib/chunkdiv.py` holds the rules
and the book reader draws the same sheet from them. Nothing is written until
the button. A phrase divides and joins glossed or not: two blank halves, or a
half whose meaning is still to type, are the middle of the work like any
other.

**Out and back.** The ⤓ in the player's header downloads `video.json`,
`annotations.json`, `transcript.txt`, the notes under `markdown/**` (and
`parts/**`, on a video old enough to still have them) and — where one was
recorded — `waveform.json` as one zip with a `parseh-bundle.json` manifest; the panel at the foot of the video index takes
such a zip back, refusing anything it cannot vouch for (a path that escapes,
an unknown language, annotations that do not pass the checker) and offering a
*replace it* choice for an id already here. The player reads the new files at
once. `../lib/bundle.py` is the same thing on the command line.

> **The waveform travels because it cannot be made again cheaply.** A
> YouTube video's sound reaches no script here, so its picture is a
> recording of the whole video made in real time; carrying it means the next
> machine does not sit through the video a second time. And it is given up
> only to another waveform: a bundle made before the sound was drawn carries
> none, and installing it leaves the one already here alone — the same rule
> the film has, for the same reason.

> **`parts/` is retired** (2026-09-23). The batches are folded into
> `annotations.json` once, while the video is being added, and dropped there
> and then: a video on the shelf has no `parts/`, and `annotations.json` is
> its only annotation — the player writes it and nothing rebuilds it. A
> video added before that date still carries its batches; `merge_parts.py`
> now refuses to rebuild over an `annotations.json` newer than they are, and
> says which captions and which fields that would have thrown away. Delete
> the folder and it will never come up again.

## Anki cards

The decks are **shared with the book reader**: a card made on a page of
بوف کور (port 7654) and a card made from a video land in the same store
under `anki/`, list in the same deck picker, and build into the same
.apkg — the endpoints and the card schema live in `lib/anki_store.py`,
which both servers import.  In the book reader the same gestures apply:
alt-click a word in pass 1 or pass 2, or the “+ card” button in a
hover-mode gloss cloud.

**Shift-click any phrase** to copy its text to the clipboard — the
phrase, the hoverable unit; shift-click beside one and the whole caption is
copied. A plain click still replays the sentence. The gloss cloud carries a
**copy** button too, which is the way on a touch screen.

**Alt-click (or Ctrl-click) any word** in the transcript — the word, not
the phrase, even though the hover gloss belongs to the phrase — and a card
dashboard opens, prefilled: the word on the target-language side (the field
is labelled with the language's name; a Japanese card has a *reading* row
for the kana as well); the phrase's meaning on the gloss side; the
phrase (or, for a whole-phrase card, its caption) as context; the
vocabulary line as notes. The Anki field behind that gloss side is called
**English** in every language's note type and keeps the name whatever the
video's glosses are written in: Anki matches a note type by its id and its
list of fields when a package is imported, so renaming one would split or
merge a deck somebody is already studying — see
[anki/README.md](anki/README.md). Delete the excess, edit anything. The
**“+ card”** button inside a gloss cloud does the same for the whole
phrase (and
is the way on a touch screen). The card records its `lang`, and is tagged
`<tag>-youtube` with the language's tag (`farsi-youtube`, `japanese-youtube`).

- **To**: where the card goes, remembered from one card to the next.
  *Anki* is everything below. *exercise deck* adds the card as an exercise
  to one of the toolbox's exercise decks of the video's language (or a new
  one): the save button reads *add to deck*; once the card is in, the sheet
  stays open and says what went in, with an *open the deck* link and any
  warning the deck gave. An exercise the deck already holds is not added:
  the button then reads *add it again*, and pressing it adds a second one
  (any change to the card first asks again). The deck page links the
  exercise back to this player at the card's moment. That moment is where
  the video stands when the sheet opens, if that is inside the word's
  caption, and the caption's start otherwise; the card's source link and
  its frame use it too. *markdown* puts the same card on the clipboard as one
  `:::exercise flashcard` block, to paste into a studio document or a deck's
  *Add exercise*; where the browser will not put it there, the sheet shows
  it, selected, to copy by hand. Those two also offer the **jolly** type:
  four fields of any studio markdown (front and back, each a main text and a
  smaller one), prefilled from the word.
- **🔊 cut the audio…** gives the card the word's own sound. It opens a cut
  editor over the waveform with its edges already where the word probably is
  (its share of the caption's text, from the caption's start to the next
  one's); move them by ear, save the clip, and use it. The clip is kept in the
  clip tray (`clips/`) and plays in the sheet; pick the side it goes on (for a
  jolly card it becomes a line in the box the cursor was last in, whether or
  not you typed there — or the back's main text before any box has had the
  cursor; delete that line and the card goes without it). Anki copies it into the deck as a `[sound:]` in the image
  field; a deck or a studio document brings it in from the tray when the card
  is added or pasted. A clip that no card took — the sheet closed without
  saving, adding or copying it — leaves the tray again, as it does in the book
  reader.
  - *A film on this machine* is cut by the server, from the film itself.
  - *A YouTube video* plays in a frame of YouTube's own, whose sound no page
    can read, so the editor records **this tab** instead: its first step plays
    the stretch around the caption once, sound on, while the tab records it,
    and the waveform and the edges then work on that recording. This needs
    Chrome or Edge on a computer, and this computer's address (`http://localhost`),
    or the https address from another computer. The first
    time, Chrome asks to share the tab: press **Allow** and leave **Also allow
    tab audio** on. The share lasts as long as the page (the frame capture
    uses the same one), so later clips record straight away; Chrome's *Stop
    sharing* ends it, and the next clip asks again. While it records, the
    player's own volume and speed are set to full and normal and put back
    afterwards, and **record again** records the stretch anew — around the
    edges, if they were moved past it; a clip saved from the recording before
    is cut again, from the new one, when it is used. The **reach** row moves
    where that next recording starts and ends: seconds typed into its two
    boxes, negative earlier and positive later (up to a minute either way),
    for a caption that cuts the sentence across — YouTube's transcript often
    does. The strip then shows all of what was recorded, so the cursors reach
    into what the caption left out. The clip is saved as a WAV and kept as
    an MP3 when the machine has ffmpeg.
- **Deck**: pick an existing deck or choose *+ new deck…* and name it —
  `Farsi::YouTube`-style names nest inside Anki. The last-used deck is
  remembered, and a name typed for a new deck belongs to the destination
  it was typed for.
- **Type**: *vocabulary* (the default) or *opposites*. An opposites card
  asks "what is the opposite of X?" — the word you clicked is X, and you
  write the opposite (plus its transliteration, and its kana for Japanese,
  if you like) yourself; it uses its own Anki note type. The book reader's
  dashboard has the same toggle. Each language has its own pair of note
  types (the ids are in the registry); the Persian pair is the original one
  and never changes shape — see [anki/README.md](anki/README.md).
- **Bidirectional** (default on) also generates the card the other way
  round, gloss → target — or, for an opposites card, asks the opposite of
  the answer.
- **📷 capture the current frame** grabs the video's frame at the card's
  moment and attaches it to the target-language or the gloss side. It is built
  on web standards only (display capture + canvas), so it does not decay
  as YouTube changes: in **Chrome** pick “This Tab” and the shot is
  cropped to the video pixel-perfectly (Region Capture); in **Firefox** —
  which cannot capture single tabs — share this browser window (or the
  screen) and the page calibrates itself by flashing two coloured dots on
  the video's corners and locating them in the captured frame, so
  toolbars, zoom and window position all cancel out. Either way you get
  the video area only, never the page. Needs a secure origin — every
  address Parseh serves is one — and one share approval per session (in
  Chrome and Edge it is asked with the tab's sound, which *cut the audio…*
  records on a YouTube video; a share without it still takes frames, until
  *cut the audio…* asks for one with the sound in its place); a
  paused video first rolls in muted from about five
  seconds before the moment, because YouTube keeps its overlay up for a
  full five seconds, so the control bar fades out of the shot and it
  freezes back on the exact frame. For an exercise deck or markdown the
  frame is kept in the clip tray and named as the card's picture.
- **preview card** renders the finished card right in the dashboard —
  both directions, screenshot in place, night mode following the page
  theme — using the very templates and CSS the .apkg carries, so what
  you see is what Anki will show. For an exercise deck or markdown it draws
  the card the way a deck page does; click it to turn it.
- **save card** writes JSON + screenshot (and recording) under `anki/<language>/<deck>/` — see
  [anki/README.md](anki/README.md). **build .apkg** downloads the deck as
  a package; double-click it and Anki imports it, the font the language
  needs included (Vazirmatn for Persian, Noto Naskh Arabic for Arabic;
  Japanese and the Latin-script languages use the device's own fonts).

Built for the *study-and-keep-adding* loop: every card's Anki GUID is
fixed when it is saved, so re-importing a rebuilt deck updates existing
notes **without touching your scheduling** and only adds what's new.
Add cards all week, build, re-import, keep reviewing.

## Over Tailscale

The same https address works from anywhere in the tailnet: `../serve.sh`
prints the `100.x.y.z` form. Parseh is https everywhere, with a certificate
it makes itself, so the clipboard — which browsers grant only to *secure
contexts* — works from a phone or a laptop just as it does on the machine.
**A frame** depends on which kind of video it is: a film of this machine is
read straight off the film onto a canvas, so its frame is captured anywhere,
a phone included; a **YouTube** video's frame is taken from a share of this
tab, and no phone browser shares a tab, so that one is a computer's affair.
Each browser warns once about the
certificate; accept it. `../serve.sh cert` makes a fresh one if the
machine's addresses change.

## Layout

```
youtube/
├── serve.sh, serve.py      # shims: the server is ../serve.py, for everything
├── PROMPT.md               # the prompt for a Claude Code session in the project
├── docs/
│   ├── chat-prompt.md      # the self-contained prompt the "Add a video" page copies
│   ├── conventions.md      # what is the same for every language: chunk size, fields, the repetition rule
│   └── glossary-*.md       # per-video-family word lists, for consistency
├── lib/
│   ├── ytpages.py          # the pages + Anki endpoints ../serve.py mounts at /youtube/
│   ├── style.css           # the player's own styles (the palette is ../lib/parseh.css)
│   ├── player.js           # YouTube sync, highlighting, the gloss cloud
│   ├── tabcapture.js       # this tab's share and the recording of its sound: the waveform's, and the add page's transcript
│   ├── addstt.js, addstt.css # the add page's optional speech to text: the one block, drawn from what the computer says it has
│   ├── sttpanel.py         # a transcription's segments -> the panel the add page reads (the job's own routes are ../lib/sttjobs.py)
│   ├── wavefile.py         # the one cleaner and writer of waveform.json, and the hold a transcription keeps for a video
│   ├── player.html         # page template (__ID__, __TITLE__, __BASE__, ...)
│   ├── import_old_video.py # a video from the older watching-edition format
│   ├── slice_part.py       # the captions one batch is responsible for
│   ├── check_part.py       # one batch, checked on its own
│   ├── check_annotations.py# the whole video: fidelity + schema, exit 0 = good
│   ├── merge_parts.py      # parts/*.json + transcript.txt -> annotations.json, once, as a video is added
│   ├── annwrite.py         # ONE chunk of annotations.json, edited from the player
│   ├── anki_export.py      # deck directory -> importable .apkg
│   ├── anki_store.py       # the deck store, shared with the book reader
│   └── fonts/              # Vazirmatn, Noto Nastaliq Urdu, Noto Naskh Arabic (woff2)
├── anki/<language>/<deck>/ # the decks both dashboards write (see its README)
└── videos/<language>/<id>/ # <language> is the registry's folder: persian, arabic, italian, japanese, french, german, turkish, english
    ├── transcript.txt      # the pasted transcript, verbatim; source of truth
    ├── video.json          # title, title_native, channel, language, gloss, level, blurb
    └── annotations.json    # what the player serves and writes; built once, as the video is added
```

The language registry and the per-language conventions live one level up:
`../lib/languages.json` (read through `../lib/languages.py`) and
`../docs/lang/<code>.md`.

`video.json` carries `"language"` (a registry code) and `"title_native"`,
the display title in the target language for the index card, and may carry
`"gloss"` — the code of the language its glosses are written in, English
when the key is absent. The two must not be read for each other:
`language` is what the video teaches, `gloss` is what the `en` field of
every chunk is written in. The older spelling `"title_fa"` is still read
wherever `title_native` is absent; the pipeline writes `title_native`.

The annotation format is specified in `PROMPT.md`; the conventions it
enforces live in two places: what is generic — chunking size, the fields,
the vocabulary line's shape, the repetition rule — in `docs/conventions.md`,
and what is the language's own — the transliteration scheme, the marks the
text carries, the reading rule, the never-gloss list — in
`../docs/lang/<code>.md`; a word list per family of videos sits beside the
conventions so a long video does not read as if several hands wrote it
(they did).

Two things the pipeline handles for you. A caption **entirely in another
language** — the framing these teaching videos often open with, usually
English but whatever the speaker turns to — is never annotated: for a
language written in its own script (Persian, Arabic, Hindi, Japanese,
Chinese) it is recognised by having no character of that script, filled in
from the transcript and shown as it stands, quieter than the target text and
not hoverable. For a Latin-script target (Italian, French, German, Turkish,
English, Spanish, Catalan) no caption can be told plain automatically, so the
annotator marks such an aside as a chunk with `"plain": true` — the only
place where an annotator may write that key. A **chapter marker** pasted into the
transcript (`Capitolo 3: …`, `فصل ۳: …`, `第3章：…` — a bare number is
speech; the marker needs a separator and a title after it)
becomes a heading above the caption it belongs to; the words that make a
line a chapter marker or a duration line (`1 minuto e 6 secondi`, `۱ دقیقه
و ۳ ثانیه`) come from every language's entry in the registry.

In the player: **keep in view** keeps the playing caption in view, **✱ notes** lights every phrase
that carries a note and counts them, with **‹ ›** to walk from one to the next
(browser interface only, and off every time the page opens), **keep video** keeps the video stuck
under the header while you scroll, **beside the text** puts it in a column of its own, **◐** cycles light / dark / sepia — one setting for the whole toolbox,
**⚙ page** opens the page's panel (a0.5.0: **Pause while a gloss is open**, the
dictionary's definitions, **Diacritics**, the video's size, the skip and the speed, the
text sizes, the zoom, the colours -- each row a name and a sentence, and each group saying
whether it is kept on this device or follows you), **Aa** opens that panel at its **Text**
group (the target text — the slider is labelled with the language's name, as **Persian text
size** — the gloss cloud, the column width, the
leading — remembered per browser, like the studio's sliders), and **⏻**
stops the server (every page of Parseh has that button).
The little pill under the video is a **resize grip**: drag it down for a
bigger video, up for smaller; double-click it to return to the default
size. The chosen size is remembered.
While the video plays, the spoken sentence is in full ink, its neighbours in
grey and the rest fainter — all of them permanently visible and hoverable,
because a sentence often carries over a caption boundary. Clicking any
sentence (or its timestamp) replays the video from that sentence's
beginning, as many times as you like.
