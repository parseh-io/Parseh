---
title: The Markdown dialect
linkTitle: The Markdown dialect
weight: 50
description: Everything a studio document can hold, construct by construct, with what the studio draws from it.
---

A document in Parseh's studio is a plain text file written in a small
Markdown of its own. Most of it is the Markdown you may know already —
`##` headings, `**bold**`, lists, tables — and the rest is what a language
learner's page needs and ordinary Markdown has no word for: text in the
language you are learning, set in its own face and direction; its
pronunciation, riding along unseen until you point at a word; a vocabulary
entry with its headword set large; a box, a tint, a colour; a recording
cut to one sentence; a formula.

This section describes every one of those constructs, as the studio
reads and draws it. It is the reference: what the studio's parser accepts,
what it makes of it on the screen and on paper, and what it quietly leaves
out.

## How to read these pages

Nearly every construct is shown twice: the Markdown as you would type it,
and under it, marked **Result**, what the studio draws from it. The result
is drawn by the studio's own code — the same parser and the same renderer
the reading view uses — so what you see is what your document will look
like.

```parseh-example
The word کتاب = *book* needs no mark: its script is enough.
[این یک PDF است]{tl} is a Persian sentence with a Latin word in it.
```

Every example is **Persian unless it says otherwise**, because a document
that names no language is a Persian one. An example in another language
starts with a short front matter naming it — `target: ja`, `target: it` —
exactly as a document of that language does.

Where the studio does something this guide's own pages do differently (the
guide also reads Hugo's Markdown, and some text means one thing to Hugo
and another to the studio), the example is shown as source only, and the
page says in words what the studio makes of it.

## Where to start

[How the studio reads a document](overview.md) is the page to read first:
it says in what order the studio tries each line, and which parts of
ordinary Markdown it has and has not. The [cheat sheet](cheat-sheet.md)
then puts every construct on one page, each with a link to the page that
explains it. The pages in between take one family of constructs each, and
[Documents in each language](languages/_index.md) says what changes from one
target language to the next.

The exercises — `:::exercise` blocks, fourteen kinds of them — have a
section of their own in this guide, [Writing exercises](../dialect-exercises/_index.md).
