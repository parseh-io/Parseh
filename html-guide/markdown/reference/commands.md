---
title: "The command line: install, serve, build"
linkTitle: "Commands: install, serve, build"
weight: 2
description: For those who like a terminal — the installers, the server, the book builds, the two guides and the tests, with every flag.
---

> **For the command line — and only if you want it.** Nearly everything on
> this page is something a page of Parseh already does with a button, or
> that happens by itself: the installer and the setup wizard, the **build**
> and **build PDF** buttons, the guide's **Compile the guide**. (The
> exceptions, such as a fresh certificate, are on the [troubleshooting
> page](troubleshooting.md).) The commands
> are here for people who like a terminal, for fixing something by hand,
> and for scripting. On Windows, where there is no shell, the double-clicks
> (`install.bat`, `serve.bat`) are the whole of it.

Run everything from the top of Parseh's folder, the one that holds
`serve.sh`. Where a line starts with `python3`, it means the Python of
Parseh's environment: `./serve.sh`, `./build.sh` and `./install.sh` find
that environment by themselves (`lib/env.sh`), and
`python3 lib/runtime.py python` prints its path when you want to run a
script with it directly.

The companion page, [The command line: content, lookup,
Anki](commands-content.md), has the tools that work on books, videos,
dictionaries and cards.

## Installing

### install.sh (Linux and macOS)

```bash
# everything: the environment and its packages, the guide, the word
# analyzers' models, a report on the machine, the readers
./install.sh
# only the report, the readers and the guide; installs nothing
./install.sh --check
# only compile the guide, and stop
./install.sh --guide
```

| Flag | What it does |
|---|---|
| *(none)* | Makes the environment if there is none (with micromamba, into `.runtime/env`), adds what an older one lacks, compiles the guide, fetches the word analyzers' models, reports on the machine, and builds every book's reader. |
| `--check` | The report, the readers and the guide only. Nothing is installed. |
| `--guide` | Compiles the guide (`html-guide/markdown/` into `html-guide/site/`) and stops. Nothing else runs; any Python 3 will do. |
| `--conda` | Makes the environment with this machine's conda (`ilya-frank`) instead of the checkout's own micromamba. |
| `--recreate` | Throws `.runtime/env` away and makes it again. |
| `--json` | The installing only, reported as JSON lines for a graphical installer to read (below), and nothing else. |
| `--pdf` | The report also checks the TeX Live packages a book's or a studio document's PDF needs, and installs the missing ones with `tlmgr` — among them `extsizes`, which the studio's large print needs, `pgf`, which draws a flashcard's round frame on paper, and the hyphenation patterns of every language that hyphenates. |
| `--align` | The report also says how to re-align a narration from the command line. |

Flags combine (`./install.sh --pdf --align`); an unknown one is refused
with `unknown argument: …` and exit status 2. Without `--check`, the
installing comes first, under `== installing ==`. Then the report comes,
under these headings:

- `required to serve the reader` — Python 3, the bundled web fonts, every
  book with its narration and its alignment, and a Japanese or Chinese
  font when there is content in that language;
- `the environment (everything that rebuilds)`;
- `optional: rebuilding the PDF`;
- `optional: re-running the alignment, cutting a card's recording`;
- `optional: reading a book nobody has glossed yet`;
- `optional: dividing Japanese and Chinese into words`;
- `building the readers`;
- `compiling the guide` — with `--check` only; otherwise the installing
  compiled it.

It ends with `N checks passed, M missing.` An `ok` line is there; a
`MISS` line is not, says why it matters, and is counted as missing; a
`--` line is something optional that is not there, and is not counted.

### install.bat (Windows) and Parseh.command (macOS)

`install.bat`, double-clicked, does what `./install.sh` does without the
report: it finds or makes the environment (under `.runtime\`, or an
`ilya-frank` environment conda already has), then adds its packages,
compiles the guide, fetches the models and builds the readers. Its flags
are those of `lib/runtime.py install`, below; the one worth knowing is
`install.bat --recreate`.

`Parseh.command`, double-clicked in the Finder, runs `./install.sh` the
first time (when it finds no environment), then `./serve.sh`, and opens
the browser on `https://localhost:7654/`.

### lib/runtime.py

Where the installing is actually done — standard-library Python, so it
runs before the environment exists.

```bash
# what this machine has, in words
python3 lib/runtime.py status
# the same, as one JSON object
python3 lib/runtime.py status --json
# the environment, its packages, the guide, the models, the readers
python3 lib/runtime.py install
# ... reporting as it goes, in JSON lines
python3 lib/runtime.py install --json
# the Python the launchers run, as a path
python3 lib/runtime.py python
```

| `install` flag | What it does |
|---|---|
| `--conda` | Makes the environment with the machine's conda, not micromamba. |
| `--recreate` | Removes the checkout's own environment and makes it again. |
| `--no-readers` | Leaves the readers alone (`./install.sh` builds them itself, after its report). |
| `--dry-run` | Walks every step as *skipped* and touches nothing: the way to try a window out. |
| `--json` | One JSON object a line on standard output: `step` (with `id`, `title`, `state`, `detail`), `log`, and a last `done` with `ok`. |

The steps, in order, are `env` (find or make the environment), `packages`
(add what `environment.yml` lists and it lacks), `guide`, `models`
(`lib/words.py --fetch ja zh`) and `readers` (`./build.sh --html`). A step
is `running`, `done`, `skipped`, `warning` or `failed`; the guide is the
one step that ends as a `warning` rather than a failure when it goes
wrong, since Parseh works without it. The environment is looked for in
this order: `$PARSEH_PYTHON` when it is set; the checkout's
`.runtime/env`; then an environment called `ilya-frank` wherever a conda,
a mamba or a micromamba keeps its environments. `docs/installer.md` is
the full contract.

A conda user can still make the environment the usual way —
`conda env create -f environment.yml` — and every script finds it.

## Serving

### serve.sh (Linux and macOS)

```bash
# start it in the background and print the addresses (https, the port
# Settings > Network keeps -- 7654 on a fresh install)
./serve.sh
# ... on another port, this once (the page moves it for good)
./serve.sh 9000
# is it running, and where
./serve.sh status
# follow the log (serve.log)
./serve.sh log
# stop it (the stop button on any page does too)
./serve.sh stop
# stop, then start again
./serve.sh restart
# a fresh certificate in .tls/, under Parseh's own authority
./serve.sh cert
```

The server keeps running when the terminal closes; its process id is in
`.serve.pid` and its output in `serve.log`. A second start while one is
running says `already running` and leaves it alone. (A copy of the
source code also has `youtube/serve.sh`, which only forwards to this one,
for old habits; a release does not carry it.)

### serve.py (any system, in the foreground)

```bash
# the doors Settings > Network has open, https on the port it keeps;
# Ctrl-C stops it
python3 serve.py
# another port (or --port 9000)
python3 serve.py 9000
# bind 127.0.0.1 only for this run: this machine and nothing else.
# (Shutting both doors on Settings > Network does the same for good,
#  and at once.)
python3 serve.py --local
# bind one address only (your Tailscale one, say)
python3 serve.py --host 100.x.y.z
# plain http, no TLS (screen capture and the clipboard: localhost only)
python3 serve.py --http
# make a fresh certificate and exit
python3 serve.py --cert
```

On start it lists the books it found (and any narration a `book.json`
names that is missing), the addresses it can be reached at, and the
doors: `/books/`, `/youtube/`, `/studio/`, `/exercises/`, `/anki/sync/`,
`/settings/` — and, under them, who may reach it.
The rest of the addresses are `/settings/reading-help/` (the reading help; its old address `/lookup/` still opens it), `/clips/`
(the clip tray), `/guide/` (these pages) and `/licences/` (what Parseh, its
fonts and the data it downloads are under).

### serve.bat and lib/launcher.py (Windows)

```bash
# the first time a setup wizard; then start and open the browser
serve.bat
# ... on another port
serve.bat 9000
# run the wizard again
serve.bat setup
# stop a running server
serve.bat stop
# is it running, and where
serve.bat status
# a fresh certificate
serve.bat cert
# every book's reader and the library page, as ./build.sh --html does
serve.bat readers
# start without opening a browser window
serve.bat --no-browser
```

`serve.bat` only finds a Python — Parseh's environment first, any
Python 3 otherwise, and offers to install one with winget when there is
none — and hands its arguments to `lib/launcher.py`. The server runs in
that window: closing it, Ctrl-C or a stop button stops it. The wizard
checks what `install.sh` checks, offers to make or complete the
environment and to install `openssl`, builds the readers and makes the
certificate; without `openssl` it serves plain http.

### The studio on its own

`python3 markdown/app/server.py [--port 8766] [--open]` serves the studio
alone, over plain http — the way it was developed. Everything else
(books, videos, exercises, the **Working…** indicator) belongs to
`serve.py`; use that.

## Building

### build.sh: the books

```bash
# every book that changed: PDF + reader + library page
./build.sh
# one book: a slug, <language>/<slug>, or books/<language>/<slug>/
./build.sh <slug>
# the readers and the library page only, no LaTeX
./build.sh --html
# ignore the cache and rebuild even what is unchanged
./build.sh --force
# a PDF of just those chapters, in seconds
./build.sh --draft ch3h ch3i
```

A book whose sources have not changed is skipped: `.build-key` and
`.reader-key` in its folder remember what the last build read, and
`--force` ignores them. The build checks the LaTeX log as well as the PDF
— a PDF with an error in its log counts as failed — and `./build.sh`
exits with status 1 when any PDF failed (2 for an unknown option). The
**build**, **rebuild** and **build PDF** buttons run this same script for
one book as a job the page follows; on Windows, which has no shell, the
same steps run in Python (`lib/bookbuild.py`). `python3
lib/make_index.py` writes the library page, `books/index.html`, alone.

### html-guide/build.py: these pages

```bash
# compile into html-guide/site/
python3 html-guide/build.py
# compile into a scratch folder, keep nothing, say what is wrong
python3 html-guide/build.py --check
# warnings fail the compile too
python3 html-guide/build.py --strict
# compile into DIR instead of html-guide/site/
python3 html-guide/build.py --out DIR
# remove html-guide/site/ and stop
python3 html-guide/build.py --clean
# a whole site in DIR, as GitHub Pages publishes it
python3 html-guide/build.py --pages DIR
# the guide, with what it needs of Parseh, as a project of its own
python3 html-guide/build.py --export DIR
# say only what is wrong (also -q)
python3 html-guide/build.py --quiet
```

| Flag | What it does |
|---|---|
| *(none)* | Compiles `html-guide/markdown/` into `html-guide/site/`: a clean rebuild, swapped in whole. |
| `--check` | Compiles into a temporary folder, prints every problem, and keeps nothing. |
| `--strict` | A warning fails the compile, as an error does. |
| `--out DIR` | Compiles somewhere else. |
| `--clean` | Removes `site/`. |
| `--pages DIR` | Lays out `index.html`, `assets/` and the compiled `site/` in one folder — what the GitHub Pages workflow publishes, and what any static host can serve. |
| `--export DIR` | Copies the guide into a project of its own, with a snapshot of the studio's renderer, the language registry, and the fonts with their licences in `engine/vendor/`. |
| `--quiet`, `-q` | Prints only the problems. |

It needs any Python 3.8 or newer and nothing else. Each problem is
printed as `warning:` or `error:` with its file and line, then one line
sums up: *the guide: N pages and M other files -> …; W warnings, E
errors*. The exit status is 0, or 1 when there was an error (or, with
`--strict`, a warning), or 2 for a wrong argument — among them a folder
for `--out`, `--pages` or `--export` that holds something else, which is
refused untouched. [Compiling and
publishing](../writing-this-guide/compiling.md) says more, and the
installers and the front page's **Compile the guide** button run the
same compile.

### The word analyzers' models

```bash
# download what the Japanese and Chinese analyzers need
python3 lib/words.py --fetch ja zh
# the word line the machine proposes for a chunk
python3 lib/words.py ja 山へ柴刈りに、
```

The installers fetch the models (pkuseg's, some 75 MB, into `~/.pkuseg/`
or `$PKUSEG_HOME`) so that no page ever waits for them.
`python3 lib/fill_words.py` gives the chunks of an older Japanese or
Chinese book or video the word lines they lack: [The command line:
content, lookup, Anki](commands-content.md#books-by-hand).

## Checking the toolbox

For whoever changes Parseh's own code, in a copy of its source code — a
release does not carry the tests. Never run two of these at once in the
same checkout.

```bash
# the unit tests
python3 -m unittest discover -s tests -p 'test_*.py'
# a fixture of every language through every renderer
python3 tests/smoke.py
# ... and the LaTeX builds (minutes)
python3 tests/smoke.py --pdf
# only some areas
python3 tests/smoke.py --only studio,books
# the translation model, run in a real browser
python3 tests/mtcheck.py
# what a reader's panel draws, in a browser
python3 tests/mtcheck.py --panels
```

The browser tests are `tests/*.mjs`, run with `deno` (which the
environment carries) against a Chromium:

```bash
CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 \
  deno run --allow-all tests/html_guide.mjs
```

A browser test that fails now and then is run again and again, to see how often
and why, one run after another or with the computer made busy on purpose
(`--stress`), and its failures counted by their reasons:

```bash
python3 tests/repeat.py studio_audio -n 20
```

## Releasing a version

For whoever releases Parseh, from a copy of its source code;
[`docs/releasing.md`](https://github.com/parseh-io/Parseh/blob/main/docs/releasing.md)
is the whole procedure, step by step. The one tool it uses:

```bash
# the release's zip, its checksum and its list of files, in dist/,
# made from a commit (HEAD, or --ref) exactly as GitHub makes it
python3 lib/release.py build
# refuses unless the tag, VERSION and CHANGELOG.md's newest heading agree
python3 lib/release.py check <version>
# that version's section of CHANGELOG.md: the release's notes
python3 lib/release.py notes <version>
# whether two builds -- zips, lists of files, or one of each -- ship the same
python3 lib/release.py compare dist/parseh-<version>.zip ~/Downloads/parseh-<version>.zip
# asks every address Parseh names -- the update feed, the site, the guide, the phone app's
# icons, the links in the documents -- and prints what each answers (needs the network)
python3 lib/release.py links --expect <version>
```
