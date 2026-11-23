---
title: Installing Parseh
linkTitle: Installing
weight: 1
description: Getting Parseh from its releases page, what it needs, the one command or double-click that installs it on Linux, macOS and Windows, and every option of the installers.
---

Parseh is a folder, unpacked from the zip of one of its releases.
Installing it means giving that folder what it needs to run, and almost
nothing goes anywhere else on the computer — so removing the folder removes
Parseh, all but the few things [Removing it](#removing-it) lists.

## Getting Parseh

1. Open the [releases page](https://github.com/parseh-io/Parseh/releases/latest)
   and download the zip of the newest release, **`parseh-<version>.zip`**
   (under *Assets*). The `.sha256` file beside it is its checksum, for
   those who check one.
2. Unpack it — double-click it on a Mac, **Extract All…** in its right-click
   menu on Windows, your file manager's *Extract* on Linux. It holds one
   folder, `parseh-<version>`: that folder is Parseh.
3. Put the folder where it will stay, with the name you like — `Parseh` in
   your home folder, say — **before** you install: the installer makes the
   environment inside it.
4. Install it, below.

**Install from a release, and nothing else.** A release's zip carries the
list of its own files, and that list is what lets Parseh
[update itself from Settings](updating.md) later, keeping everything that is
yours. The *Code → Download ZIP* button and the *Source code* archives on
GitHub are the source code, not a release: they have no such list, carry the
tests, and cannot update themselves. A copy made with `git clone` is for
working on Parseh's own code; git keeps it up to date, and Settings leaves it
alone.

**The first double-click may be questioned**, because the files came from
the internet. On a Mac the Finder may say that **Parseh.command** is from an
unidentified developer: Control-click it, choose **Open**, then **Open**
again, once. On Windows a blue *Windows protected your PC* may cover
**install.bat**: **More info**, then **Run anyway**.

## What it needs

**Serving the pages needs only Python 3** — version 3.8 or newer, and only
its standard library — and, once, `openssl` to make the certificate the
server speaks HTTPS with. A computer with those serves every page of
Parseh.

**Everything that makes or rebuilds something needs more**: rebuilding a
book, dividing Japanese and Chinese into words, aligning a narration,
opening an Anki export. Those packages live together in one Python
environment called `ilya-frank`, listed in `environment.yml`, so the
computer's own Python is never touched:

| Package | What it is for |
|---|---|
| PyMuPDF | re-extracting a book's text from its scans |
| rapidfuzz | aligning a narration, and saving an edited timing |
| fonttools | making the web fonts |
| brotli | compressing them (woff2) |
| sudachipy | dividing Japanese into words |
| SudachiDict-core | the dictionary SudachiPy reads |
| spacy-pkuseg | dividing Chinese into words, and naming their parts of speech |
| pypinyin | reading Chinese words in pinyin |
| zstandard | opening a modern Anki export |
| numpy | estimating the timings by the sound ([Fixing the timings](../books/timings.md#estimate-the-rest-by-the-text-or-by-the-sound)) |
| Pillow | printing a WebP or GIF picture in a studio document's PDF, and turning a HEIC into a JPEG ([Pictures and recordings](../studio/editor-media.md)) |
| pillow-heif | reading a phone's HEIC picture, for Pillow |

The environment also carries two programs of its own, `openssl` (the
certificate) and `deno` (the browser tests), so that no computer has to
find them for itself.

**A few things come from the computer, and only when you want what they
do.** Nothing breaks without them; the pages that need one say so.

| Program | What it is for | Where it comes from |
|---|---|---|
| TeX Live | a book's PDF (LuaLaTeX), a studio document's PDF (XeLaTeX) | the system's packages; `./install.sh --pdf` adds the TeX packages it lacks |
| ffmpeg | snapping a narration's timings to its silences; the picture of the sound a book's or a film's timings are estimated by; cutting a card's recording out of a narration or a film; cutting a recording down to the stretch a [page for a website](../studio/web-page.md) plays | the system's package manager |
| pdftotext | re-extracting a book's source from a PDF | poppler-utils |
| a CJK font | Japanese and Chinese PDFs, and the face their pages are set in | Noto Serif CJK (`fonts-noto-cjk` on Debian and Ubuntu); macOS and Windows have faces of their own for the pages |

The fonts of Persian, Arabic and Hindi — Vazirmatn, Noto Nastaliq Urdu,
Noto Naskh Arabic, Noto Serif Devanagari — travel with Parseh, in
`lib/fonts/`. A Japanese or Chinese font is tens of megabytes, so for those
two Parseh uses the one the computer has.

## On Linux

Open a terminal in the Parseh folder and run the installer:

```bash
./install.sh
```

The first time it takes a while and a few hundred megabytes: where the
computer has no `ilya-frank` environment yet, the installer downloads
**micromamba** — a single program, into `.runtime/bin/` — and makes the
environment with it in `.runtime/env/`. All it needs to begin is `curl`,
which every Linux has. Then it adds the packages, compiles this guide,
fetches the models the Chinese word analyzer uses, prints a report of what
the computer has, and builds the books' readers.

## On a Mac

Double-click **Parseh.command** in the Finder. The first time, it runs the
installer in a Terminal window — the same `./install.sh`, and the same
report — then starts Parseh and opens the browser on it. Every time after
that it only starts Parseh and opens the browser. Closing the Terminal
window does not stop the server: the **⏻ stop** button on any page does.

You can also run `./install.sh` in Terminal yourself, exactly as on Linux.
A new Mac, with no Python of its own, is no obstacle: the installer makes
the environment, Python included, before it needs one.

## On Windows

Double-click **install.bat**. It looks for an environment the computer
already has — `.runtime\env` in the folder, or an `ilya-frank` environment
that an Anaconda, a Miniconda, a Miniforge or a micromamba keeps — and
where there is none, it downloads micromamba and makes one in `.runtime\`:

```text
Parseh needs its environment, and this computer does not have it yet.
It goes into this folder (.runtime\) and takes a few hundred megabytes.

Downloading micromamba ...
Making the environment (this takes a while, once) ...
```

Then it does what the installer does everywhere — the packages, the guide,
the models, the readers — and ends with **Parseh is installed.
Double-click serve.bat to start it.** If a step fails, it says
`The installation did not finish -- the messages above say why.` and waits
for a key, so the window stays open for you to read them.

You can also skip it and double-click **serve.bat** straight away: its first
run is a [setup wizard](windows-wizard.md) that checks the computer,
offers to make the same environment, and makes the certificate.

## What the installer does

Every installer — `install.sh`, `install.bat`, the Windows wizard — runs the
same steps, in the same order, because they all hand the work to the same
program, `lib/runtime.py`:

| Step | What it does |
|---|---|
| **the environment** | finds `ilya-frank` — the folder's own `.runtime/env` first, then any conda, mamba or micromamba that keeps one — or makes it: with micromamba into `.runtime/env`, or with your conda when you ask for that (`--conda`) |
| **the packages** | adds whatever `environment.yml` lists and the environment lacks, with its own pip; the programs it carries with micromamba or conda |
| **the guide** | compiles these pages, `html-guide/markdown/` into `html-guide/site/` |
| **the word analyzers' models** | pkuseg's word and part-of-speech models for Chinese, some 75 MB, so that no page ever waits for that download |
| **the readers** | every book's reader, and the library page |

The second step is what keeps an older installation up to date: a package
added to `environment.yml` after your computer was set up is added the next
time the installer runs, whatever made the environment. An
[update from Settings](updating.md) does the same by itself when the new
version asks for a package, and then compiles the guide and builds the
readers as this table does. Running the installer again is always safe.

The guide's step is the one that may fail without the installation failing:
Parseh works without these pages, so a compile that goes wrong is said as
a warning, and the guide's own front page offers to compile it again
([This guide](this-guide.md)).

Outside the Parseh folder the installer writes pkuseg's models, in
`~/.pkuseg` (the environment variable `PKUSEG_HOME` moves them); when you
ask for it with `--conda`, the environment, where your conda keeps its
environments; and with `--pdf`, the TeX packages it finds missing, into
TeX Live itself ([the report](#the-report), below).

**The server adds one more thing, on a TeX Live that has no Italian
hyphenation.** Many TeX Live installations leave Italian's patterns out,
and the PDF of a studio document written in Italian would then break its
words at English points. So each time it starts, the server checks whether XeLaTeX knows
Italian, and where it does not it copies the patterns Parseh carries into
your own TeX folders — `TEXMFHOME`, with a `language.dat` that names them
in `TEXMFCONFIG` — and rebuilds XeLaTeX's format to take them. Once that
has worked, the next start finds Italian there and leaves it alone. The
line at the foot of the studio's library says how it went: *Italian
hyphenation ✓*, or *✗* where it could not be done.

## The report

On Linux and macOS, `./install.sh` then says what the computer has, one
line a thing — `ok`, `MISS` for something missing, `--` for something
optional that is not there — under these headings:

| Heading | What it checks |
|---|---|
| required to serve the reader | Python 3; the bundled web fonts; every book, with its narration and its alignment; a Japanese or Chinese font, when there is a book or a video in that language |
| the environment | `ilya-frank`, each of its packages and the two programs it carries |
| optional: rebuilding the PDF | LuaLaTeX; with `--pdf`, the TeX packages and each language's hyphenation patterns; the fonts LuaLaTeX reads, which it builds from the web fonts when they are missing |
| optional: re-running the alignment, cutting a card's recording, cutting the clips of a page for a website | ffmpeg and pdftotext |
| optional: reading a book nobody has glossed yet | a dictionary, sentences somebody translated, a translation model, a synonym table — all got from **Settings → Reading help** (the hub's **Reading what nobody has glossed** door) |
| optional: dividing Japanese and Chinese into words | the two word analyzers and pkuseg's models |

It ends by building the readers and counting what it found — *28 checks
passed, 0 missing.* on a computer that has everything. A missing line says
what to do about it. Besides the readers, the report changes something on
the computer in two places only: with `--pdf` it installs the TeX packages
it found missing, and it makes the fonts LuaLaTeX reads from the web fonts
when they are not there.

## Options

`./install.sh` alone does everything: the environment and its packages,
the guide, the models, then the report and the readers. It also takes these
options, alone or together:

- `--check` — only the report, the readers and the guide; installs
  nothing.
- `--guide` — only compile the guide, with the environment's Python or the
  system's, and stop; nothing is installed.
- `--conda` — make the environment with this computer's conda
  (`conda env create -n ilya-frank`) instead of the folder's own
  micromamba.
- `--recreate` — throw `.runtime/env` away and make it again.
- `--pdf` — where TeX Live's `tlmgr` is there, the report also installs the
  TeX packages a book's PDF needs and the studio's large print (14, 17 and
  20 pt) uses, and each language's hyphenation patterns, and checks that
  the patterns are really reachable — a book whose patterns are missing
  still compiles, broken at English points.
- `--align` — the report also prints the command that re-aligns a
  narration.
- `--json` — the installing only, one JSON object a line, for a window to
  show; no report, no readers.

Anything else is refused: `unknown argument: --bogus`.

**install.bat** takes the same kind of option, typed after it in a command
prompt: `install.bat --recreate` makes the environment again. (Whatever
follows `install.bat` is handed to `lib\runtime.py install` as it is, so
`--conda`, `--json` and `--dry-run` work there too.)

## If you already use conda

An environment called `ilya-frank` that you made yourself is used as it is,
and the installer only adds what it lacks:

```bash
conda env create -f environment.yml
./install.sh
```

`serve.sh`, `build.sh`, `install.sh` and `serve.bat` look for the
environment in the same places, in this order:
the Python named by the environment variable `PARSEH_PYTHON`, when it is
set; the folder's own `.runtime/env`; then an `envs/ilya-frank` of a conda,
a mamba or a micromamba — under `~/miniconda3`, `~/anaconda3`,
`~/miniforge3`, `~/mambaforge`, `~/micromamba`, `~/.conda` and their
counterparts in `/opt` and Homebrew's Caskroom. Without any, `./serve.sh`
still serves with the computer's own `python3`, and says so.

## Removing it

Delete `.runtime/` and the environment is gone; delete the whole folder and
Parseh is gone. What is left outside it:

- pkuseg's models, the folder `.pkuseg` in your home folder — delete it
  too;
- an environment you made with your own conda;
- the TeX packages `--pdf` installed, which belong to TeX Live now;
- on a TeX Live that had no Italian hyphenation, the Italian patterns the
  server put in your own TeX folders, and the copy of TeX Live's
  `language.dat`, with Italian added, that it put beside them.

> **For the command line.** `conda env remove -n ilya-frank` removes an
> environment you made with conda. `kpsewhich -var-value TEXMFHOME` and
> `kpsewhich -var-value TEXMFCONFIG` name your own TeX folders; the
> patterns are `hyph-it.tex` and `loadhyph-it.tex` in
> `tex/generic/hyph-utf8/patterns/tex/` under the first, and the list is
> `tex/generic/config/language.dat` under the second.

## For the command line

`lib/runtime.py` is what every installer runs, and it can say what the
computer has without changing anything:

```bash
python3 lib/runtime.py status          # what this computer has
python3 lib/runtime.py status --json   # the same, as JSON
python3 lib/runtime.py install --dry-run   # the steps, not done
python3 lib/runtime.py python          # the Python it would use
```

`status` lists the environment, its Python, every package (`ok` or
`MISS`), every program and pkuseg's two models (`ok`, or `--` where one is
not there). `docs/installer.md` describes the JSON lines that
`install --json` writes, for a graphical installer to show.
