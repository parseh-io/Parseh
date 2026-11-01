---
title: A video's files
weight: 14
description: What a video is on disk — video.json, transcript.txt, annotations.json, parts, notes, the waveform and the film — field by field, and the tools behind the pages.
---

Every page of the Videos door reads and writes a handful of plain files in
one folder, and reads them afresh on every visit: drop a video's folder in
place and it is on the shelf, with nothing to build and nothing to restart.
You never need to open them — every change has a page — but knowing what is
in them explains what the pages check, and lets a text editor do what a page
cannot, such as one find-and-replace across a whole video's meanings.

## One folder per video

```text
youtube/videos/
  persian/                        the language's folder: persian, arabic, italian,
    <id>/                         japanese, french, german, turkish, english,
      video.json                  hindi, spanish, chinese
      transcript.txt              the pasted transcript: the source of truth
      annotations.json            what the player draws
      parts/01.json …             the batches an LLM's answer was saved as
      markdown/persian/<note>/    the notes, one studio document each
      waveform.json               the drawn picture of a YouTube video's sound
      media.mp4                   the film, for a film on this machine
      media.mp3                   or the sound: media.<ext> is either
      media-orig.wma              the original of a sound made playable
  .trash/                         videos taken off the shelf, or replaced
  .incoming/                      files sent and not yet used: cleared after two days
```

`<id>` is the YouTube id, eleven characters, or for a film the id made from
its name. The player's address carries only the id, `/youtube/v/<id>/`,
because an id is unique across languages. Only the first three files are
needed; the others appear when there is something to put in them.

## video.json

| Field | Is |
|---|---|
| `id` | the video's id |
| `url` | its YouTube address; empty for a film on this machine |
| `title` | the title in Latin letters |
| `title_native` | a short title in the video's own language, for its card (older files spell it `title_fa`, which is still read) |
| `channel` | the channel it is filed under — the only place a channel exists |
| `language` | the language it **teaches**, a registry code: `fa`, `ar`, `it`, `ja`, `fr`, `de`, `tr`, `en`, `hi`, `es`, `zh` |
| `gloss` | the language its meanings are **written** in; English when absent |
| `level` | `beginner`, `lower-intermediate`, `intermediate`, `upper-intermediate` or `advanced` |
| `duration` | about how long it is, the last caption's time |
| `added` | the day it was added |
| `blurb` | one sentence for the card |
| `reorders` | `true` for a text read out of its written order ([kanbun](video-info-and-drafts.md#kanbun)) |
| `kind` | `"audio"` for a video whose media is a **sound** with no picture, written once, when the file was attached; absent for a film or a YouTube video, and then the media is a picture, as it always was. A video made before the key reads it from the extension of `media.<ext>` ([A film on this machine](a-film-on-this-machine.md#a-sound-instead-of-a-film)) |

`language` and `gloss` are never to be read for each other: an Italian
learning English watches a video with `"language": "en", "gloss": "it"`. The
gloss may also be a language the toolbox does not teach — `pt`, `nl`, `ca`,
`ro`, `pl`, `ru`, `en-gb`, `en-us`. The folder should agree with the
language; if it does not, the JSON wins for drawing the page and the server
says so once in its log.

## transcript.txt

The pasted transcript, the **single source of truth**: every caption's
start, its text, its chapter heading and whether it is plain are read from
it, and the phrases are checked against it letter for letter.

```text
0:00
Hello everyone, welcome to today's lesson
0:05
こんにちは、みなさん
Chapter 1: 朝
0:09.4
今日は 天気が いいですね
```

- A **time** line starts a caption: `0:05`, `1:02:03`, and a fraction where
  there is one, `0:09.4`.
- The lines under it are what is said, joined into one caption.
- A **chapter marker** — a word for *chapter* in any of the toolbox's
  languages, a number, a separator and a title: `Chapter 1: …`,
  `Capitolo 3: …`, `第3章：…`, `فصل ۱: …` — becomes a heading over the
  **next** caption. A bare number is speech.
- A **spoken-duration** line under a time (`1 minuto e 6 secondi`,
  `۱ دقیقه و ۳ ثانیه`) is dropped.
- A caption is **plain** — shown as it stands, never glossed — when the
  language has a script of its own and the caption has not one character of
  it. For a language in Latin letters nothing is plain by itself: an aside
  is a phrase marked `"plain": true` instead.

Never retype it. After a video is added, the only change any page makes to
it is a caption's start, through [the timings](the-timings.md).

## annotations.json

What the player draws: the id, the language, and one **segment** per
caption, in the transcript's order.

```json
{"video": "aB3dE5fG7hI", "language": "ja", "segments": [
 {"start": 0, "plain": true,
  "text": "Hello everyone, welcome to today's lesson"},
 {"start": 5, "text": "こんにちは、みなさん",
  "chunks": [
   {"fa": "こんにちは、", "kana": "こんにちは、", "tr": "konnichiwa,", "en": "hello,"},
   {"fa": "みなさん", "kana": "みなさん", "tr": "minasan", "en": "everyone"}
  ]},
 {"start": 9.4, "chapter": "朝",
  "text": "今日は 天気が いいですね",
  "chunks": [
   {"fa": "今日は", "words": "今日(きょう) は", "kana": "きょうは", "tr": "kyō wa",
    "voc": "今日 きょう kyō today; は wa topic marker", "en": "today", "col": "blue"},
   {"fa": "天気が", "kana": "てんきが", "tr": "tenki ga", "en": "the weather"},
   {"fa": "いいですね", "kana": "いいですね", "tr": "ii desu ne", "en": "is nice, isn't it"}
  ]}
]}
```

A segment carries its `start`, its `text` (the caption's), its `chapter`
where the transcript has one, `"plain": true` for a caption in another
language — which then has no phrases — and its `chunks`, the phrases:

| Field | Holds |
|---|---|
| `fa` | the phrase's text — named after Persian, the toolbox's first language, whatever the language is. In Persian and Arabic it is the caption's text as YouTube has it, bare, unless somebody wrote the short vowels into it — by hand in the ✎ form, or with an LLM's answer when **write them** was chosen ([glossing with an LLM](glossing-with-an-llm.md#the-short-vowels)); the timings and the fidelity check set the marks aside, so either way the phrase is the same phrase |
| `words` | Japanese, Chinese: the phrase's words, each with its reading in ASCII parentheses; joined with nothing they must be `fa` exactly |
| `kana` | Japanese: the reading of the whole phrase |
| `tr` | the transliteration — required where the language wants one, optional for a language in Latin letters |
| `voc` | the vocabulary line, in the books' entries (`\dw`, `\vb`, `\bw`, `\pw`) or plain text: a word's first appearance in the video, and rarely after |
| `en` | the meaning — named after English, and written in the video's `gloss` language |
| `note` | anything else worth saying: what the automatic transcript really heard, a cultural point; the ✎ form edits it, and emptying its box takes the key out ([The note](editing-a-phrase.md#the-note)) |
| `plain` | `true` for a phrase asked for nothing: an aside in another language, in a language written in Latin letters |
| `col` | `red`, `blue`, `orange` or `green`: your own mark |
| `free` | `true`: this phrase need not reproduce `transcript.txt` ([When YouTube heard wrong](editing-a-phrase.md#when-youtube-heard-wrong)) |

Absent and empty mean the same thing everywhere, so the pages remove a field
you empty rather than leave `"col": ""` behind.

**The rules the checker holds it to:**

- one segment per caption of the transcript, the same start (within half a
  second), the same text, the same chapter, the same plain mark — except
  that a caption holding a `free` phrase is not held to the transcript's
  text, and is counted in a warning instead;
- the phrases of a segment, **joined back** with the language's separator —
  a space, or nothing for Japanese and Chinese, whose spaces are ignored —
  **reproduce** its text; the language's marks (the harakat of Persian and
  Arabic) are set aside first, and nothing else is;
- every phrase of the language that has any gloss written has all the
  fields its language requires: the meaning; the transliteration where
  required; the kana for Japanese. A phrase with **nothing** written in it
  is legal in every video, and is only counted, in one note (*12 of 40
  chunks have no gloss yet*); a phrase half glossed is an error;
- a colour is one of the four; `words`, where present, give back `fa`;
- a phrase longer than **seven words** is warned about: the conventions ask
  for two to six.

### parts/ is retired {#parts}

A video added from an LLM's answer is assembled from that answer in batches
of twenty-five captions, under `parts/`. They live only while the video is
being added: `merge_parts.py` folds them into `annotations.json`, the
checker passes on it, and the batches are dropped before the video reaches
the shelf. **A video on the shelf has no `parts/`, and `annotations.json`
is its only annotation** — the player writes it, and nothing rebuilds it.

That is new since the 23rd of September 2026, and it is there because the
old arrangement lost work: every change made in the player went to
`annotations.json` alone, so a `merge_parts.py` run again by hand rebuilt
the file from the old answer and threw those changes away — the colours,
the edited glosses, the phrases cut and joined — without a word.

A video added before that date still has its batches on disk. Nothing
reads them, and you may delete the folder. If you do run `merge_parts.py`
on such a video, it now refuses when `annotations.json` is newer than the
batches, and says how many captions and which fields the rebuild would
have lost.

## The other files

- **`markdown/`** holds the [notes](notes-in-the-seam.md), in the studio's
  own layout.
- **`waveform.json`** is `{"rate": 20, "peaks": [0, 0.12, …]}`: the shape
  of a YouTube video's sound, twenty numbers a second between 0 and 1,
  recorded once by [**● draw the sound**](the-timings.md#the-picture-of-the-sound).
  A film has none: the server reads the film.
- **`wordtimes.json`** is optional, and appears only when this video was added
  from a matching transcript Parseh made. It is the `parseh-wordtimes/1`
  capture track: ordered words with video-clock starts and ends, their source
  (Whisper, the optional aligner, or an honest worked-out value), and any
  accepted person-set boundary. The player does not edit or depend on it in
  this version — [moving text between lines](moving-text.md) does not rewrite it
  either, since it is the capture as it was; it travels in a video bundle for later
  timing work.
- **`media.<ext>`** is the film of [a film on this machine](a-film-on-this-machine.md).
  It is kept out of git; the rest can be.
- **`media-orig.<ext>`** exists only for a sound a browser could not play: the
  person's own file, kept beside the playable copy that is `media.<ext>`. It is
  never taken for the film and a download does not carry it.

## For the command line {#for-the-command-line}

> Everything below has a page, and the pages are the way to do it. These
> are the same tools, for a terminal on the machine that serves Parseh —
> for a long video written by hand in a Claude Code session with
> `youtube/PROMPT.md`, or a check after a find-and-replace.

```bash
cd youtube
V=videos/persian/<id>
python3 lib/check_annotations.py $V        # the whole check; it must end: 0 error(s)
python3 lib/slice_part.py $V               # how the captions divide into batches
python3 lib/slice_part.py $V 0 25          # captions 0..24, verbatim, to annotate
python3 lib/check_part.py $V parts/01.json # one batch, checked on its own
python3 lib/merge_parts.py $V              # parts/ + transcript.txt -> annotations.json, once, while adding
python3 lib/import_old_video.py <dir>      # a video in the older watching-edition format
cd ..
python3 lib/draft.py video --transcript t.txt --lang fa --url <URL> --into youtube/videos
python3 lib/fill_words.py --video youtube/$V   # Japanese, Chinese: the words a video lacks
python3 lib/bundle.py pack <id>            # the ⤓ zip; `inspect` and `install` take one back
```

The fidelity check sets the language's marks aside before comparing, so it
cannot see a vowel written wrong, and it knows nothing about whether a
meaning is right. A clean check means the text matches — reread the
glosses yourself.
