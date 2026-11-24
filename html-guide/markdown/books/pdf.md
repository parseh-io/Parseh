---
title: The printed edition
weight: 14
description: Building a book's PDF from the pages, following the build, where the PDF is, and rebuilding the reader alone.
---

Every book has a printed edition beside its reader: a PDF set by LuaLaTeX,
with the same levels as the reader, subparagraph by subparagraph, the
colours on the first level, a title page and a table of contents. It is built from
the same chapter files as the reader, so it says what they say — once it has
been built since they changed.

## Building it

There are four buttons, and all four run the same build on the server:

| Where | Button |
|---|---|
| the library | **build** on a card whose book has never been built (or a click anywhere on that card), **rebuild** on one that has |
| the reader | **build PDF** in the header, and **PDF behind the text — build it**, which appears there after an edit |
| the add page | **build the PDF now**, in the answer after text is added to a book (**Add it**) — and after **Make the draft** only when the reader could not be built, since otherwise the page goes straight on to the reader |

The build makes the PDF **and** the reader, and writes the library page
again. It runs as a **job** on the server: the page that started it follows
it and says, line by line, what it is doing — *The Clock and the Wind —
references moved, second pass* — in a toast on the library, beside the
header's buttons in the reader. The **Working…** indicator shows it on every
page, the hub included, so you can close the tab and do something else. A
book is built once at a time: pressing again while it builds follows the
build already running (*already building…*).

When it ends, the page says **built** — in the reader, *the PDF and the
reader are built*, and **PDF behind the text** goes away; on the library,
the page reloads so the card shows what the new reader says. If it fails,
what follows *the build failed —* is taken from the build's own output, and
it reads differently on the two kinds of machine:

- **On Windows** it is the line that says the PDF failed, then the first error
  LaTeX printed (the line that starts with `!`): *the build failed — PDF
  FAILED: ! Undefined control sequence.*
- **On Linux and macOS** a first pass that fails is tried once more before
  the failure is believed, and the message starts with the line that says
  so: *the build failed — first pass failed; clearing stale .aux/.out/.toc
  and retrying once*. When LaTeX stopped without making a PDF, its first
  error follows — *…: ! LaTeX Error: File \`nosuchfile.tex' not found.* An
  error LaTeX carried on past, making a PDF anyway (an undefined command,
  say), is not quoted: the build still counts it as a failure, and the
  error is in `main.log`, in the book's folder.

On the library a failed build leaves the page as it was; the toast shows
the message for a few seconds. The reader is written even when the PDF
fails, so reading goes on.

**How long.** A book's PDF is every pass of every chapter: a few seconds for
a short book, and three quarters of an hour for a Persian edition of 2,500
pages. On Linux and macOS the build keeps it as short as it can: a book
whose sources have not changed is not set again at all, a reader whose
sources have not changed is not written again, and LaTeX's second pass runs
only when the first moved the page references.

**What it needs.** LuaLaTeX (TeX Live, or MiKTeX on Windows). On Windows —
or any machine with no `sh` — the same steps run in Python instead, and give
the same PDF and the same reader, only more slowly: that build keeps no
record of what it set last time, so it sets the book in two passes and
writes the reader every time it is pressed, changed or not. Its progress
lines say so (*lualatex, pass 1*, *lualatex, pass 2*, *the reader*).
Without LuaLaTeX there is no PDF, and the build says so; the reader is
still written.

## Where the PDF is

The PDF is `main.pdf`, in the book's own folder:
`books/<language>/<slug>/main.pdf`. No page links to it yet: open it from
that folder, or in the browser at its address,
`http://localhost:7654/books/<language>/<slug>/main.pdf`. It is not in the
book's download — it is made from the text, and built again wherever the
text goes.

## Rebuilding the reader alone

**rebuild the reader**, in the reader's header, writes the reading page
again and nothing else — no LaTeX, so it takes a moment. Everything a reader
page can do is written into it when it is built, so a book built before a
feature has not got it; this is how it gains it. It says *the reader is
rebuilt — reload the page to read it*. The PDF is left as it is.

Most changes made from the reader — a chunk saved, a chunk cut or joined, a
section named, a fold, a narration aligned — rebuild the reader by
themselves, in a fraction of a second. None of them sets the PDF: that
waits for its button, because it is LaTeX, and takes minutes.

> **For the command line.** The same build is `./build.sh <slug>` from the
> toolbox's folder; `./build.sh` alone builds every book that changed,
> `--html` the readers only, `--force` ignores the cache. `./build.sh --draft
> ch3` sets a PDF of just that chapter file, in seconds, as `frankdraft.pdf`
> beside the book, for looking at your own work.
