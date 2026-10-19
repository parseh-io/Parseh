---
title: Bringing documents in and out
linkTitle: Documents in and out
weight: 2
description: Paste LLM answer, Upload .md / .zip and its header dialog, Download N shown, Backup and Load from backup.
---

Five buttons on the library's bar move documents across the studio's
border. Three bring documents in — each makes **new** documents, except
**Load from backup**, which puts back the very documents a backup took
away — and two take them out.

| Button | What it does |
|---|---|
| **Paste LLM answer** | a new document from a model's reply pasted into a box |
| **Upload .md / .zip** | new documents from Markdown files, or from zips of them with their pictures and recordings |
| **Load from backup** | the documents of a **Backup** zip put back as they were |
| **Download N shown** | the documents the library is showing, in one zip |
| **Backup** | the whole library, in one zip |

A document's own page has **Download ▾** too, for that one document: see
[the document page](document-page.md#download).

A sixth button, **Open a file…**, is not like these: it brings nothing in. It
opens a Markdown or zip file from anywhere on the computer Parseh runs on,
where it is, and changes it only when you save: see
[Opening a file from your computer](open-files.md).

Whatever comes in goes through the same check as a save: **its name**. A
document's name is its title, and no two documents of the library share
one, so an incoming document whose title is taken opens the dialog
*This name is already in use* before anything is written — see
[Names and links](names-and-links.md#the-name-conflict-dialog).

## Paste LLM answer

Some models answer in the chat rather than with a file. Copy the whole
reply — the chatter around it included — press **Paste LLM answer**, paste
it into the box, and press **Create document**. The studio finds the
document inside: when the reply holds a fenced code block that looks like
a document (it starts with the front matter, or it has a heading and is at
least half of what was pasted), that block is the document, the longest
one if there are several; otherwise the whole paste is. A block opened with
four backticks — what the [LLM prompt](llm-prompt.md#a-file-or-one-fenced-block)
asks for when a chatbot cannot make a file — is the document whole, even when
the document holds a fence of three backticks of its own. The new document
opens at once.

A paste is taken as it is, but for its name. Without a `title:` it is
named *Untitled* (or *Untitled 2*…), and that line is the only one added:
a text with no front matter gets one holding just `title: Untitled`, one
with a front matter gets the line put into it. Without a `target:` it is
read as Persian. Change both in the editor. If its title is one another
document has, the name dialog opens; cancelling it brings the paste box
back with your text still in it.

## Upload .md / .zip

**Upload .md / .zip** opens a file picker for `.md`, `.markdown` and `.txt`
files and `.zip` archives, several at once. It is the way in for a file a
model wrote for you (the [LLM prompt](llm-prompt.md) asks for one), for a
document downloaded from another Parseh, and for a document of your own
brought back.

**A Markdown file** becomes one new document, its text exactly as it is —
unless it came wrapped in a model's code fence, which is unwrapped as a
paste is.

**A zip** can be what a document's **Download ▾ → Markdown + media (.zip)**
gives — its Markdown, its tags and the pictures and recordings it shows —
or any zip of several documents. Every `.md` or `.markdown` file in it
becomes a document, and what it names comes with it:

- the pictures it shows, from its own folder's `images/` or from its
  folder itself, and the recordings it names, from `audio/` or its folder;
- its tags, from a `<name>.tags.json` beside it, as a document's download
  writes it;
- a file name the studio spells otherwise is renamed on the way in, and the
  Markdown with it: `Cat.PNG` is kept as `cat.png`, a WAV recording called
  `word.mp3` as `word.wav`, and a picture whose name is taken by a different
  one as `cat-2.png`.

A picture or recording the Markdown names and the zip lacks is not a
refusal: the document goes in, and the message at the end names what was
missing. The starter pages' own apple, house and chime are the exception —
a document that names them and lacks them gets them from the studio, as a
new document does.

A zip is refused, with nothing made, when it holds no Markdown file, more
than 2,000 files or more than 200 MB unpacked, a Markdown file larger than
5 MB, or one that is not UTF-8 text. Hidden files and a Mac's `__MACOSX`
folder are ignored.

### The header dialog

A document is filed by the five lines at the top of its text — `title`,
`subtitle`, `note`, `lang` and `target` — and a file from elsewhere often
lacks them. So an uploaded file with no front matter, or one short of some
of those lines, is not made at once: a dialog asks for what is missing,
and nothing else.

- **“notes.md” has no header** — the file has no front matter. Fill in the
  fields, and the whole header goes above the text.
- **“notes.md”: the header is incomplete** — the file has one, short of
  some lines. Only those lines are added; the rest of its header stays
  exactly as it was.

The fields are the missing ones only: **Title** (offered from the file's
first `# heading`, or else its file name), **Subtitle**, **Note**,
**Written in** (the language of the prose) and **The language it is about**
(the target, which starts on the library's language chip when one is
picked). A title, the prose language and the target are required; a
subtitle or a note may stay empty. Under the fields the lines that will go
in are shown as you type them.

**Add the header and import** (or **Add them and import**) goes on;
**Skip this file** — or Escape — leaves this file out and goes on with the
others. For a zip the dialog comes once for every file of it that needs
one, each named with its zip (*notes.md, in lessons.zip*), and then the
zip goes in with every answer at once.

### When it is done

One document uploaded with nothing to report opens straight away. Anything
else — several documents, a warning, a file refused — is said in a message
at the bottom of the page (*3 documents imported — …*) and the library is
drawn again. Every upload makes **new** documents, with ids of their own:
uploading a file twice makes two documents, and the second is asked for
another name.

A zip going up is on the toolbox's **Working** list, the pill in the corner
of every page, while it travels and while the server unpacks it.

## Download N shown

**Download N shown** says how many cards the library is showing — after the
search, the tags and the language chip — and downloads exactly those, in
the order they are shown, as one zip. Its menu offers two shapes, the same
two a single document's **Download ▾** offers:

- **Markdown (.md)** — one zip of their Markdown sources,
  `studio-12-documents-20260921-1430.zip`. Each file is named after the
  document's id without its random end (`verbs-of-motion.md`), or with the
  whole id where two documents would otherwise share a name.
- **Markdown + media (.zip)** — one zip holding each document's own zip
  (its Markdown, its tags and the pictures and recordings it shows),
  `studio-12-documents-with-media-….zip`. A zip of zips, because pictures of
  twelve documents poured into one folder would collide by name.

Either one can be uploaded again with **Upload .md / .zip**. The button is
greyed out when nothing is shown.

## Backup

**Backup** downloads the whole library as one zip,
`exlex-library-20260921-1430.zip`: every document's folder — its Markdown,
its `meta.json` (id, name, tags, dates, the state of its PDF), its pictures,
its recordings and its last PDF — and the custom prompt, if you saved one.
The rest of a build (the `.tex`, the fonts) is left out, since a build
makes it again. The download is on the **Working** list while the server
packs it.

## Load from backup

**Load from backup** is Backup's other half: pick a backup zip and the
documents in it come back **as they were** — the same ids, the same
permanent identifiers, the same names every link to them spells, the same
tags, dates, pictures, recordings and PDF. That is the difference from
**Upload**, which reads Markdown and makes new documents of it: a backup
restored is the library it was.

**A document that is already here is kept.** The same document is the one
with the same id, whatever language folder it sits in now. A restore is not
a merge, and a backup is usually older than the work beside it, so those
documents are left exactly as they are, and only then does a dialog say
so: *3 documents are already here — They were left exactly as they are.
Replacing them puts the backup's copy in their place — anything written
since the backup was made is lost.*

- **Keep mine** leaves them as they are.
- **Replace them** sends the backup again and puts its copies in their
  place.

**A document with a name that is taken** — one of the backup with an id of
its own, whose title another document of the library has now, or another
document of the same backup — is asked about first, in the name dialog,
before anything is written. The names you give there go with **Replace
them** too, and if a document put back by **Replace them** holds a name
that is taken, the dialog asks again.

When it is done, a message says how many documents were restored and how
many were left as they were, with the first warning if there was one (a
file in the zip that is no part of a document is left out and named). Each
document is written beside its old copy and swapped in whole, so a restore
that fails half way leaves what was there. A custom prompt in the backup
is put back only if you have none, or when you press **Replace them**.
Links written the old way, by a
document's permanent id, are rewritten by name as the documents come in
(see [Names and links](names-and-links.md#links-written-before-names)).

A backup is refused when it is not a zip, when nothing in it is a
`<language>/<document>/` folder of a library, or when it holds more than
20,000 files or 2 GB. The restore is on the **Working** list while it runs;
through the hub a backup of any size goes up, spooled to the disk, while
the studio run on its own takes up to 32 MB.

> **The other shelves have the same pair.** The books page has **Backup
> every book** and **Load from backup**, the videos page **Backup every
> video** and **Load from backup**, the exercise decks **Backup** and
> **Load from backup** — each with the same rule: what is already there is
> kept and named, and replacing it is offered only then.
