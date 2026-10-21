---
title: Pictures and recordings in a document
linkTitle: Pictures and recordings
weight: 5
description: Image, Images…, Audio, Recordings…, Video, drag and drop, pasting a figure, the clip tray, the layout panels, and the starters' own files.
---

A document's pictures and recordings are files of its own, kept in its
folder (`images/` and `audio/`) and named by a line of the Markdown:
`![A cat asleep](images/cat.png)`, `![The greeting](audio/salam.mp3)`. A
video is a line too, `@[A lesson](https://www.youtube.com/watch?v=…)`, and
is not stored: it is played from YouTube. How those lines are written, with
their width, alignment and clip, is in the
[dialect section](../dialect/_index.md); this page is about the buttons
that put them there.

> **Save first.** A document gets its folder on its first save, so the
> buttons that store a file — **Image**, **Images…**, **Audio**,
> **Recordings…**, **Pictograms…**, a picture pasted or dropped — ask you to save a new
> document first (*Save the document first — images are stored in its
> folder*). A line naming a file can be typed at any time; until the file is
> there, the preview shows a placeholder.

## Pictures: Image and Images…

(A picture that is an ARASAAC pictogram has a button of its own, **Pictograms…**,
which searches them by a word and shows each before you add it:
[Pictograms](pictograms.md#looking-for-a-pictogram-and-using-one).)

**Image** opens a file picker for PNG, JPEG, SVG and PDF files, several at
once. Each is stored in the document's `images/` and put in on a line of
its own at the cursor, as `![didascalia](images/<name>)` with the
placeholder caption *didascalia* selected, so that what you type next
replaces it. Several files go in one line after another.

What the studio does with a picture it is given:

- **It reads the bytes, not the name.** A PNG called `photo.jpg` is stored
  as `photo.png`; a file that is none of the four kinds is refused (*only
  PNG, JPEG, SVG and PDF figures are supported*), and so is one larger than
  15 MB.
- **It tidies the name** into lower-case letters, digits, dots and dashes:
  `Mon Chat.PNG` becomes `mon-chat.png`.
- **A name already taken** by a different picture gets `-2` (`cat-2.png`);
  the same picture uploaded twice is stored once.
- **A PDF is shown as a vector picture** — its first page is turned into an
  SVG beside it, for the browser, which shows no PDF inside a page; an SVG
  gets a PDF twin when the document's PDF is built. Both stay sharp at any
  size, and the twins are never listed.

**Pasting a picture** straight from the clipboard — a screenshot, a figure
copied from another program — works in the source box: a dialog asks for a
**File name** (the extension is added from the bytes) and an optional
**Caption**, and **Save and insert** stores the picture and puts its line
where the cursor was. SVG copied as text arrives the same way; cancel the
dialog and it is pasted as text after all. Anything else you paste is left
to the browser, as ever.

**Images…** shows the document's pictures as thumbnails, each with its
name and size, and *in use* on the ones the saved text shows. Click one to
put its line in at the cursor. **✕** deletes the file, after asking — and
warning, when the document still shows it, that the picture will be
missing there. The preview shows the change at once.

## Recordings: Audio and Recordings…

**Audio** does for a recording what **Image** does for a picture: a file
picker for MP3, M4A, AAC, Ogg, Opus, WAV, FLAC and WebM files, several at
once, each stored in the document's `audio/` and put in on a line of its
own as `![didascalia](audio/<name>)`. On the page the line is a player; in
the PDF, a card naming the file.

The same rules hold: the extension follows the bytes (a WAV called
`word.mp3` is stored as `word.wav`, since browsers believe the extension),
a name already taken by a different recording gets `-2`, the same file
twice is stored once, a file larger than 30 MB or not a recording at all is
refused with the reason — and so is a recording that holds no sound.

**Recordings…** lists the document's recordings: **▶** plays one (and
**❚❚** pauses it), a click on the row puts its line in at the cursor,
*in use* marks the ones the editor's text names at that moment, saved or
not, and **✕** deletes the file, after asking. Escape closes the list.

### Clips cut from books and videos

A recording cut from a book's narration or a video's sound waits in the
toolbox's **clip tray** until something takes it. When the studio is served
by the hub, **Recordings…** has a second list, **Clips cut from books and
videos**: the clips of the tray in the document's language, each with its
words, its length and where it was cut. **▶** plays one; **Add** puts its
line in at the cursor, captioned with the clip's words, and copies the file
into the document at once; **✕** deletes it from the tray, after asking — a
document, a deck or a card it already went into keeps its own copy. The
list is not shown when the tray has nothing in this language.

A clip can also come in as text. A card copied as Markdown on a book's or a
video's card sheet names its recording by its name in the tray
(`audio/wind-47de68.mp3`). Paste it into the editor of a saved document and
every such file the document lacks is copied in from the tray at once —
*Brought 1 file from the clip tray* — and the preview plays it. Every save
does the same for the whole text, so a new document takes them in when it
is first saved. A name neither the document nor the tray holds stays as
written, and plays nothing.

## Dragging files in

Drag pictures and recordings from your file manager onto the **source
box**: they are stored and put in as the buttons put them, in the order you
dropped them, one line after another from the cursor. Pictures and
recordings may be dropped together. A file of any other kind is refused
with a message naming it. A file dropped anywhere else on the page is
ignored — it is never opened in place of the editor, which would lose what
you had not saved.

## Video

**Video** asks for a YouTube address — a `watch` link, a `youtu.be` or a
`shorts` link, or the video's eleven-character id — and puts in
`@[didascalia](<address>)` on a line of its own, the caption selected. The
whole video is embedded; the stretch to play and the layout are set
afterwards, with its **⚙ layout** handle.

## Laying out a picture, a player, a block {#laying-out}

Every picture, player and Latin block can be sized and placed with the
mouse, in the preview as on the document page, and the choice is written
into the Markdown — `{width=55 align=center offset=-10}` — so the PDF lays
it out the same way.

- **A picture** — click it. The **Image layout** panel has **Width** (10 to
  100 % of the column), **Shift** (−50 to +50 %, sideways) and **Align**
  (**left**, **center**, **right**).
- **A recording** — click **⚙ layout** at the player's lower corner, or its
  caption. **Recording layout** adds a **Clip** row: the stretch to play,
  start and end, in seconds or minutes and seconds to the hundredth (`65.5`,
  `1:05.25`). Empty means from the beginning, or to the end.
- **A video** — point at it and click **⚙ layout**. **Video layout** has the
  same **Clip** row, in whole seconds, which is all YouTube takes.
- **A Latin block** (`[…]{la}`) — click it. **Block layout** has
  **Width**, **Shift**, the alignment of its **Text**, and a **Backg.**
  tint: none, *quote*, *sand*, *rose*, *sage* or *lilac*.

The sliders move the figure as you drag them and save when you let go.
Escape, **✕** or a click elsewhere closes the panel. In the editor the
change goes into the text as an edit you can undo; on the document page it
is saved into the document at once.

A player laid out with a clip plays that stretch and no more, on every page
that shows the document: started outside it, it jumps to its start, and it
stops at its end. A clipped YouTube video starts again from its clip's
start at every play. A picture, player or video on a **flashcard** has no
panel: a click there turns the card, and its layout is written by hand.

## The starters' pictures and recording {#the-starters-pictures}

The starter page every new document begins as shows two pictures and a
recording — `images/starter-apple.svg`, `images/starter-house.svg` and
`audio/starter-chime.mp3` — which ship with the studio. The preview of a
new document shows them from where the studio keeps them. The first save
copies every one of them the text still names into the document's own
folders; after that they are the document's files like any other: listed
in **Images…** and **Recordings…**, carried in its zip and its backup,
printed in its PDF.

Two rules keep them out of your way:

- **Deleted, they stay deleted.** Delete the apple with **✕** and no later
  save brings it back, even while the text still names it: the page shows
  it missing, and a PDF build stops on it, as on any file a document lacks
  (see [When a build fails](pdf.md#when-a-build-fails)).
- **Yours is never replaced.** A file of your own with the same name is
  never overwritten by the starter's. To show a picture of your own
  instead, upload it and let the line name it — or delete the starter's
  first and then upload yours under its name.

A document duplicated keeps what its original held; one made from an
uploaded `.md` or zip takes in afresh whichever of the three it names and
the upload lacks. A note beside a book or a video does the same.
