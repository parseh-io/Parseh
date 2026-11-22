---
title: Mending the transcript first
linkTitle: Mending the transcript
weight: 5
description: The add page's small subtitle editor — recorded word starts where Parseh made the transcript, timings to a tenth of a second, cutting and joining captions, ✨ tidy up in two modes, and the same job done by an LLM.
---

A pasted transcript is what YouTube **heard**, cut where YouTube chose to
cut it — and one made by [speech to
text](adding-a-video.md#speech-to-text) is what Whisper heard, cut where
Whisper chose to. Both are often wrong: a name misheard, a sentence split across two
captions, a caption that begins three seconds late, two words glued to the
caption before. Every road out of the add page — the prompt, the blank
draft, the checker — reads the panel as it stands, so a panel that is wrong
makes a video that is wrong.

So the add page has a small subtitle editor, in the manner of
*Subtitle Edit*, for the one moment it is wanted: **before anything is built
from the transcript**. Paste the transcript (step 2 of
[Adding a video](adding-a-video.md)), then press **Edit the transcript…**
under the box.

![The transcript editor: every caption in a list, its time between the six steps, its words in a box](shots/transcript-editor.png)

## The list

The editor, **The transcript**, says how many captions it read and lists
them, one row each:

| In each row | What it does |
|---|---|
| the number | the caption's place in the transcript |
| **−1** **−.5** **−.1** | move the caption earlier by a second, a half or a tenth |
| the time | where it starts; type one — `0:08`, `0:08.4`, `1:02:03`, or a number of seconds |
| **+.1** **+.5** **+1** | move it later by a tenth, a half or a second |
| the words | what is said, to correct as you like |
| **▶** | play the caption, from its start to where the next one begins |
| **✂** | cut the caption in two where the cursor is in its words |
| **⤓** | join the caption after this one to it |
| **✕** | delete it |

**A caption runs until the next one begins**, so moving one moves where the
one before it ends; there is no end to set.

After **✂**, a transcript Parseh made with word times starts the second half
at its first recorded word. A pasted transcript still uses the former halfway
guess and says so. A join puts the two captions' words together with a space;
if it would remove a start you set by hand, it asks before doing that.

Above the list:

- **shift** *n* **s**, **move them all** — add that many seconds (negative
  for earlier) to every caption's start at once. A panel copied from a
  re-uploaded video is often late or early by the same amount throughout.
  It refuses to take the first caption before the video begins.
- **+ caption at the end** — one more, four seconds after the last, to give
  its words and its time.
- **✨ tidy up**, its **text cues / recorded pauses** choice, **undo**, **redo**
  and **or with an LLM…** — below.

### Starts from the recording

When Parseh made the transcript, it carries the heard words behind the panel
while this editor is open. A cut, tidy result and accepted LLM answer takes a
new caption's start from its first matched word. A start you type or nudge is
kept as a person-set boundary; automatic work cannot quietly discard it. The
editor's count explains how many starts are from the recording and how many
are worked out. This timing detail belongs only to a Parseh-made transcript:
a pasted transcript remains the familiar panel editor.

### Hearing a nudge

For a YouTube video, the video itself stands over the list, and **▶** plays
one caption and stops where the next begins. That is how a nudge is
answered: press, play, press again. If the video cannot load (no internet),
its place says *the video did not load — the times can still be typed*.

A film on this machine is not in the player yet while it is being added, so
there is no video over the list: its captions are timed by eye and by
typing. The **▶** in each row stays, but cannot play a film: it answers
*the video is still loading*.

### A tenth of a second

The panel keeps what the steps make. A caption's clock line takes a
fraction — `0:08.4` — written only where there is one, so a panel of whole
seconds goes back as whole seconds, and every transcript written before
reads exactly as it did. The player seeks to a tenth as readily as to a
whole second. A pasted `.srt` keeps its cues' own fractions.

## ✨ tidy up

An automatic transcript is cut where YouTube ran out of room, never where a
sentence ends. **✨ tidy up** reads the whole transcript at once and
re-cuts it into **sentences**, one caption each:

1. With a Parseh-made transcript, it reads the carried word times. With a
   pasted transcript it lays words across the time their caption covers as
   before (a language written without spaces, character by character).
2. It cuts that stream into sentences — **across** the caption edges, which
   is what the transcript cannot do for itself.
3. Each sentence becomes a caption starting at its first word's time, and
   ends with the stop its language prints: `.` and `?`, `؟` in the Arabic
   script, `。` and `？` for Japanese and Chinese, `।` for Devanagari — a
   question mark where one of the language's own question words opens or
   closes it. A video written in an Arabic dialect also asks with the
   dialect's question words, so *انت رايح فين* gets its `؟`.

Every language here gives it something to read:

- **the stops the transcript already carries** — YouTube punctuates its
  automatic captions for English, Italian, French, German, Spanish and
  Japanese, and for those this is nearly the whole job;
- **the verb**, where the language puts it last and nothing is punctuated —
  Persian, Turkish: the toolbox knows the copulas from the language's own
  word lists and the verbs from the installed dictionary;
- **a pause** the caption edges betray, a **question asked without a verb**
  at a caption's edge, and a **`[music]`** tag, which is kept on a line of
  its own — these belong to every language.

**Not one word changes**: only the punctuation is new, and a tidy that could
not promise that gives the captions back untouched. It is a guess, so it is
a button and not a rule: the editor says what it did (*40 captions became
23*), **undo the tidy** takes it back in one press, and whatever it got
wrong is a **✂** or a **⤓** away.

**What decides whether it is offered is the dictionary** of the video's
language. Not because a full stop needs one, but because everything above a
full stop is a question about a word — is it a verb, is it a name — and a
dictionary is what answers that. Without it the button is not shown at all;
install the dictionary from the reading-help page (**Settings → Reading help**) and it is
there the next time you open the editor, with nothing to restart.

## Or with an LLM…

**or with an LLM…** is the other road — the one the glossing step already
walks. It copies to the clipboard a prompt that sets out the same job — one
caption per sentence, keep the words, punctuate, time each caption at its
first word, mend only a word that is plainly misheard — with the
transcript inside it, and opens a box for the answer. Paste the model's
whole answer there and press **use the answer**; it is read as an
ordinary transcript. **copy the prompt again** copies it once more, and
**close** folds the box away.

The two roads fail differently, which is why both are offered: the
algorithm cannot hear a misheard word and will never invent one; a model
hears the sense and may invent anything. So when a model's answer goes in,
the editor says how far the letters moved — *40 captions became 23, and not
one letter of the words changed*, or *— and the words are not the same: 3
letters more or fewer. Look them over.* **undo the tidy** takes an answer
back too. The prompt needs nothing installed.

**Beside the button that copies the prompt is a menu, prompt: Parseh's ▾**:
Parseh's own prompt for this job, and the ones you wrote for it
([Your own prompts](../studio/your-prompts.md)). Choose one and it is what
is copied, and the line it opens with says so (`… · custom: keep the
captions`). A prompt of yours can add a rule after Parseh's — *never correct a
name*, *leave out the tags* — or stand in place of Parseh's rules; either way
the answer's shape, one fenced block in the panel's own form, and the
transcript are Parseh's, so what comes back goes into the box as an ordinary
panel whichever prompt asked.

## Putting it back

Nothing is written until **Use this transcript**: the captions go back into
the transcript box as an ordinary panel, which is what the next step reads,
and the page says *the transcript was edited* (or *unchanged*). The panel
comes back in its plainest form — a chapter marker as `Chapter 1: …`, no
spoken-duration lines — which reads exactly as before. A prompt you had
already prepared is forgotten, since it was made from the old panel.

It refuses, by name, a caption whose start does not come after the one
before it — *caption 7 starts at 0:21, which is not after the one before it
(0:22)* — and marks that row: the checker would refuse it later, and later
is worse. It also refuses a transcript whose every caption is empty.

**Cancel**, **✕** or Esc leave the box as it was (*left as it was*).

**A transcript made by speech to text is edited by this same editor**, and
Whisper is nowhere in it: the editor opens on what is in the box, whoever put
it there, and gives the box back a panel. A generated transcript is always
yours to correct before the video is added — a misheard name, a caption
cut in the wrong place, a start a tenth late — and what you write over it is
what the video is made of. The block that made it does not touch the box
again unless you press **Transcribe** again, and then it asks first. While a
YouTube video is being recorded there, the editor says it must wait: it would
play a second copy of the same video.

## Only while the video is being added

There is no such editor in the player, and no speech to text either: a video
already in the library has no *transcribe*, no *transcribe again* and no
Whisper model to choose in its player — what a person adds is corrected with
the tools every transcript has. Once a video is added, its
transcript is what its glosses were checked against, and a door that could
rewrite what a caption **says** would quietly unmake that check. The one
thing that may still move afterwards is where a caption **starts** —
[the timings](the-timings.md) — and a phrase whose words YouTube got wrong
has its own way out ([Editing a phrase](editing-a-phrase.md#when-youtube-heard-wrong)).
