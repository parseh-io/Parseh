# Releasing Parseh

*The checklist a release follows, from the first test to the published zip,
and what to do when a published release turns out to be bad. Written to be
followed blindly: somebody who remembers nothing about the last release must
be able to make the next one from this page alone. Decided with the owner on
2026-09-24 and 2026-09-25.*

**Releasing is a developer's act.** Every command below is one line, typed in
a terminal (Linux or macOS) at the top of a copy of Parseh's source code — a
`git clone` of the repository, called *the checkout* here. Nobody who uses
Parseh ever runs any of them. The steps that happen in a browser are said as
the pages say them.

**What a release is.** One commit, tagged with its version exactly as
`VERSION` spells it (no `v` in front), and one zip built from it, `parseh-<version>.zip`: the program without
its tests, its demo GIFs or the repository's own files, with
`.parseh-release.json` inside — the list of every file it ships with a
checksum for each, the version, the commit, the data formats this version
writes, and what `environment.yml` asked for. An install made from the zip
keeps that list, and **Settings → Updating Parseh** reads it to update in
place. GitHub builds the zip when the tag is pushed and leaves it as a
**draft**, which only the repository's owner can see; publishing it is a
separate act, by hand.

**What a rehearsal is.** Before the version's own tag, the whole road is
tried once under a rehearsal's tag, `<version>-rc1` (`a0.3.2-rc1`, say): the
same zip, named `parseh-<version>-rc1.zip`, whose list says `<version>-rc1`,
left by GitHub as a draft marked **pre-release**. It is looked at, then
deleted with its tag. Parseh counts `<version>-rc1` as coming before
`<version>` (and `-rc2` after `-rc1`), so an install made from a rehearsal
updates forward to the release. A rehearsal may be made before the release's
day is written; the version's own tag may not. `VERSION` never says `-rc`:
it is only ever a tag's name.

## Contents

- [What the machines check, and what they do not](#what-the-machines-check-and-what-they-do-not)
- [Before you start](#before-you-start)
- [The known-red baseline](#the-known-red-baseline)
- [The checklist](#the-checklist)
  1. [The suites](#1-the-suites)
  2. [The version](#2-the-version)
  3. [The guide, compiled](#3-the-guide-compiled)
  4. [The rehearsal's commit, and its build](#4-the-rehearsals-commit-and-its-build)
  5. [The rehearsal, on Parseh-test](#5-the-rehearsal-on-parseh-test)
  6. [The rehearsal, on GitHub](#6-the-rehearsal-on-github)
  7. [The day, and the release commit](#7-the-day-and-the-release-commit)
  8. [Tag and push: GitHub's draft](#8-tag-and-push-githubs-draft)
  9. [The draft is what you built](#9-the-draft-is-what-you-built)
  10. [Publish](#10-publish)
  11. [Parseh-mine, from GitHub](#11-parseh-mine-from-github)
  12. [Afterwards](#12-afterwards)
- [Where Parseh lives](#where-parseh-lives)
- [When a draft is wrong](#when-a-draft-is-wrong)
- [When a published release is bad](#when-a-published-release-is-bad)
- [The first managed release](#the-first-managed-release)

## What the machines check, and what they do not

A step a machine enforces is a step nobody can forget. These are enforced:

| Who | Refuses |
|---|---|
| `lib/release.py check`, run by GitHub before it builds anything | a tag, `VERSION`, `CHANGELOG.md`'s newest heading and What's new's newest heading (`html-guide/markdown/reference/whats-new.md`) that do not all name the same version; a tag that is neither a version nor a rehearsal of one (`-rc1`, `-rc2` …: not `-rc0`, `-rc01`, `-RC1` or `-beta`); an empty newest section. For a **version's own tag**, also: a changelog heading that still says `unreleased`, a What's new heading that still says `not yet released`, and the two giving different days. A **rehearsal's tag** passes with both still undated. GitHub then makes no draft, and the run is red. |
| `lib/release.py guide`, run by GitHub before it builds anything | a compiled guide (`html-guide/site/`, which ships as committed) that is not what the guide's sources compile to — a page, a picture, the guide's engine or the studio's renderer changed after the last compile — or whose last compile had errors, or that is missing. GitHub then makes no draft. |
| `lib/release.py build`, locally and on GitHub | a release missing a folder Parseh writes into or a file it cannot do without; a `.bat` without CRLF line endings; a launcher that lost its executable bit; anything personal or any content (`.tls/`, a file in `config/`, `books/`, `dict/` and the rest other than a `.gitkeep` or a `README.md`); `tests/` or a GIF in `docs/`; a symbolic link. `--tag` refuses a tag that is not `VERSION`'s own or a rehearsal of it. It writes no zip then. |
| the release workflow (`.github/workflows/release.yml`) | building over a release that is already published: a published release is never replaced. An earlier **draft** of the same tag is replaced. It marks a rehearsal's draft **pre-release** and a version's draft not. **When a release is published**, a version's own tag published as a pre-release has the mark taken off and is made the latest (a guard for step 10's one box ticked by hand); marking a release pre-release later, to withdraw it, is left alone. It runs **no test suite**. |
| `tests/test_html_guide.py` | a guide page *What changed, version by version* whose `## ` headings are not the changelog's versions, in its order, with its days. |
| `tests/test_version.py` | a `VERSION` that is not one line holding a version (never a rehearsal's name); a version written by hand anywhere in the code; a `README.md` that names a version (it links to the newest release instead, so it never goes stale); a kind of file Parseh keeps without a data-format number in `lib/version.py`. |
| `tests/test_release.py` | an `export-ignore` list in `.gitattributes`, a `/dist/` rule in `.gitignore`, or a release workflow that drifted from what this page relies on (its steps and their order — check, guide, build, notes, pre-release or not, the draft — and no test suite in it) — and the builder's own refusals, each driven in a scratch repository. |

**Not enforced — this page is the only guard:** that the suites were run
and are no redder than the baseline (GitHub runs none: they need a browser
and the whole toolchain, which are on your computer); the rehearsals; the
publishing; the guide's run on GitHub Pages, launched by you (8.4);
Parseh-mine's update from GitHub; everything under *Afterwards*.

## Before you start

- **The checkout**, on `main`, up to date with GitHub (`git pull`), with
  the right to push to it.
- **Parseh's environment** on the terminal's path, so that `python3` is the
  environment's and `deno` is there. From the checkout:

  ```bash
  export PATH="$(dirname "$(python3 lib/runtime.py python)"):$PATH" PARSEH_PYTHON="$(python3 lib/runtime.py python)"
  ```

- **A Chromium** for the browser suites, named by `CHROME_BIN`. The one
  Playwright downloaded does:

  ```bash
  export CHROME_BIN="$(ls -d ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome | tail -1)"
  ```

  (Any Chrome or Chromium the system has does as well:
  `export CHROME_BIN=/usr/bin/chromium`, say.)
- **A temporary folder with room.** The browser suites write big
  temporary files — a 200 MB download the phone is made to keep, a
  browser profile per suite — into `TMPDIR`. Where `/tmp` is a memory disk
  (a *tmpfs*) that is filling up, they fail in ways that look like faults
  of Parseh: `tests/mobile_pages.mjs`'s background step *j* failed every
  time with `/tmp` 79% full, and passed every time on the main disk. Point
  it at the main disk:

  ```bash
  mkdir -p ~/.cache/parseh-tests-tmp && export TMPDIR=~/.cache/parseh-tests-tmp
  ```

- **Two installs of Parseh besides the checkout**, each made from a release's
  zip, never a git checkout. This page calls them by the names the owner
  keeps them under, as folders beside the checkout:
  - **Parseh-test** — where the update is **rehearsed** before anything is
    published: it runs the previous release, holds things to lose, and is
    updated with the zip you built. It answers on its own port, **7655**,
    so it can run beside the other. Nothing in it matters; it is there to be
    broken.
  - **Parseh-mine** — the Parseh actually used, with the real books, decks
    and dictionaries, answering on **7654**. It is **never updated by hand,
    never from a file you built and never from a draft**: once the release is
    PUBLISHED, it updates from GitHub itself, through **Settings → Updating
    Parseh → Check now → Download**, exactly as every other person's does
    (the owner, 2026-09-25). What goes wrong there would have gone wrong for
    everybody, so it is checked the day of publishing, before anybody else
    has had time to update.
  - **Never serve Parseh-test on 7654.** Each install makes its own
    certificate authority in its own `.tls/`, and the browsers you use have
    accepted Parseh-mine's for `localhost:7654`: a Parseh-test answering
    there would present another certificate to them. Parseh-test is always
    started with `./serve.sh 7655`.
- **No phone, no tablet.** Nothing here needs one. The promise a phone
  depends on (the app takes the new version, says so in a line, and keeps
  everything it kept) is held by `tests/mobile_pages.mjs`, whose `update`
  part runs in step 1.
- **A few hours.** The browser suites alone take about an hour and a half.

## The known-red baseline

**There is none: every suite is green** (a0.5.3, 2026-10-21), **and none is
accepted as flaky.** A red suite in step 1 is new breakage and stops the
release. One that is red and then green when it is run again alone is not
"flaky, accepted": it has a cause nobody has found yet (*Flaky tests*, below).

It was not always so. Three suites were red from a0.3.0 to a0.4.3 —
`decomposition`, `exercises` and `studio_narrow` — and were mended on
2026-10-05, each by finding out whose fault it was: `decomposition` and
`exercises` were wrong TESTS (the first appended its click target under a
floating bar on a hand-assembled page and now serves the real player page;
the second expected the wrong arrow for a right-to-left fixture and served
its mocked editor page without the files the real one links), and
`studio_narrow` was a REAL layout fault (the editor bar's group of insert
buttons could not shrink, so the bar was wider than the screen from 721 to
about 780 px and the colour palette ran off the edge; it wraps now, with no
control hidden). The same day the suites of a0.4.3's work, which had not been
run on this machine, were brought up to what it now does (`add_stt`,
`youtube_capture`, `speech_door`, `editor_dir`, `draft_end_to_end` and
`smoke.py`'s two player checks), and that turned up one more real fault: the
title bar of the transcription window was a `<header>`, which the video pages'
stylesheet pins to the top of the screen.

Measured on 2026-10-19 on the finished a0.5.2 tree, one suite at a time,
with `TMPDIR` on the main disk:

| Suite | State | Result |
|---|---|---|
| unit — `python3 -m unittest discover -s tests -p "test_*.py"` | green | `Ran 3779 tests … OK (skipped=14)` |
| `python3 tests/smoke.py` | green | `1901 passed, 0 failed, 21 skipped` |
| the 81 `tests/*.mjs` | green | each of them; none is accepted as flaky |

A new red is breakage: in a worktree on the previous release's tag, run the
same suite — if it is red there too, it is old; if not, it is yours. (A worktree
lacks the git-ignored fonts and built fixture readers: copy them from the
checkout first, or six unit tests of `test_mobile_pages` and
`test_offline_notes` fail for that reason alone.)

**No suite is accepted as flaky.** Until a0.5.2 this page kept a list of suites that "failed now and then and
passed when run again". a0.5.3 went through it with the tool below: every check on it that could be made to fail had a
cause, found by driving the suite, and was mended, which is why the list is gone. A suite that fails and passes again
alone has a cause nobody has found yet; a red in step 1 is breakage to be explained, not a roll of the dice.

**Finding the cause.** `tests/repeat.py` runs one suite again and again and says how often it was red, and why:

```bash
python3 tests/repeat.py studio_audio -n 20
```

Most of the flaky checks failed rarely on a quiet computer and often on a loaded one, which is the computer they
failed on. What found nearly all of them was **copies of the suite running at once** (four copies put a computer of 24
cores at a load of a dozen or so, twice or three times what it was when they were first seen), each with its own
temporary folders and ports:

```bash
for i in 1 2 3 4; do python3 tests/repeat.py studio_audio -n 3 & done; wait
```

`--stress K` pins the suite to K cores that K busy loops also use. It slows everything evenly, so it found few of
them: what fails is a check that falls between two things happening at their own pace, and that wants jitter, which
a crowd has. A suite's own selectors make a loop short (`--env NAME=VALUE`): `SECTIONS=g` for `arasaac_door`,
`REACH_PARTS=slow` for `reach`, `MOBILE_PARTS=background MOBILE_BG_ONLY=i2` for `mobile_pages`. A check that fails
without saying what it saw (which toast, which pictures, what the folder says) is mended to say it before it is chased.

**What the flaky checks of a0.5.2 were**, so that the next one is looked for among them:

| Suite | What it did | What it waits for now |
|---|---|---|
| `mobile_pages`, background (steps g, h, i2, j) | pressed Save on the sheet of a book already kept before the sheet had finished looking at the phone, which re-ticks the boxes by what it finds: the Save said *nothing was changed* and no download began (*the rec download could not be caught halfway: []*, i2's missing refusal) | the sheet's own line *Looking at what is on this phone…* to be gone |
| `mobile_pages`, the reader | waited 700 ms for a hold to open its row | the row |
| `studio_audio`, the pasted clip | clicked a player in a preview that was about to be drawn again (a paste and the clip tray's adoption draw it twice, each replacing the players of the one before) | no `/api/preview` open and none begun for 800 ms; then a click where the player has stood still for six frames, and its own `play` |
| `activity` | looked at the hub's pill in a tab behind another, which is drawn when the browser gets to it; looked for a three-second *Done* after the browser had handed the file over | the tab in front; the page's own diary of its pill |
| `studio_narrow`, a contents jump | took two looks at the scroll 150 ms apart for a page standing still | twelve drawn frames with nothing moving |
| `arasaac_door` | counted a button or a box at the instant the server's state changed, before the page's own look; slowed the host by the clock and hoped the page's once-a-second look fell inside | the page's controls; the pictures held at the host until the count had been seen |
| `reach`, the slow part | counted the asks from the browser's events, in which a cut ask's end can reach the test after the next ask's start | the page's own count |
| `cardkit` | waited five to ten seconds for sound to play through; wanted one pause at the end of a clip where two came, 5 ms apart | thirty seconds; no pause before the end |

Not reproduced in some sixty runs under every load tried, so hardened and made to describe themselves when they
fail: `studio_starter_media` (the editor draws the new picture), the 22 ms fade of `cardkit`, and the *Failed to fetch*
of a write in `reach`'s slow part.

Two of the causes were faults of Parseh, not of the tests, and are mended in it: the Pictograms page could stay on
*Part of it is here* after a job had ended (`getarasaac.status()` read the job last), and the studio alone printed a
browser's closed connection as a traceback (a0.5.2).

**Writing a check that does not flake.** Wait for the state the check is about, not for a time, and never read it at
the instant something else became true (the server's state changes before the page has been told). A flash on the
screen is read from a diary the page keeps, not caught. A thing drawn more than once is waited for until it is still.
A gesture is looked for in its effect (the player's own `play`), not trusted to have landed. What the browser reports of
the network is not what the page did: the page counts its own asks. And a failure says what it saw.

The suites are written for a computer doing little else: at a load of a hundred on 24 cores, what needs real time
(sound recorded from a tab, a smooth scroll) fails honestly. And **a Chromium that dies** (*Target page, context or
browser has been closed*; `coredumpctl list` shows it) is not a test: on this computer it happened sixteen times between
2026-09-10 and 2026-09-28, the weeks in which suites ran in several checkouts at once, and not since.

**Taking it again.** When this table is older than the last release, or you
do not trust it, measure it again before changing anything: on the last
release's own commit, so that nothing of the new work is in it. Put that
commit beside the checkout, run everything there as step 1 says, and remove
it afterwards:

```bash
git worktree add ../parseh-baseline <last release's tag>
```

```bash
git worktree remove --force ../parseh-baseline
```

Then write the new table here, with its date, and commit it with the
release.

## The checklist

Replace `<version>` everywhere with the version being released, as `VERSION`
spells it (`cat VERSION`), and `<previous>` with the last published release.
`<version>-rc1` is the first rehearsal; a second one, after a fault, is
`<version>-rc2`, and so on — a rehearsal's name is never used twice.

### 1. The suites

Run every suite on the tree you mean to release, **one at a time** — two at
once in one checkout break each other — and compare with the baseline.
`TMPDIR` must be set as [Before you start](#before-you-start) says.

1. The unit tests, then the library page they rewrite put back:

   ```bash
   python3 -m unittest discover -s tests -p "test_*.py"; python3 lib/make_index.py
   ```

   They fail by themselves if they changed anything in `config/`.
2. The smoke test:

   ```bash
   python3 tests/smoke.py
   ```

3. Every browser suite, one after another, each log kept (about an hour
   and a half):

   ```bash
   mkdir -p ../parseh-suites && : > ../parseh-suites/results.txt && python3 tests/configguard.py save ../parseh-suites/config.before && for t in tests/*.mjs; do n=$(basename "$t" .mjs); NO_COLOR=1 timeout 900 deno run --allow-all "$t" > "../parseh-suites/$n.log" 2>&1; echo "$n $?" | tee -a ../parseh-suites/results.txt; done; python3 tests/configguard.py check ../parseh-suites/config.before
   ```

   The last line must say that `config/` is as it was. The browser suites
   have no guard of their own, and one that writes there changes the owner's
   own settings (a suite once left his theme dark): `check` says what moved
   and when each file was written, and the suite that ran then is the one
   whose log has that time (`ls -l --time-style=full-iso
   ../parseh-suites/*.log`).

   (`tests/guide_shots.mjs` is among them, and saves nothing of the guide's
   unless `GUIDE_SHOTS_WRITE=1` is set: it only takes the pictures into a
   folder it removes, to show that each can still be taken.)

   Then the red ones, each with the end of its log:

   ```bash
   for n in $(grep -v ' 0$' ../parseh-suites/results.txt | cut -d' ' -f1); do echo "== $n"; tail -8 "../parseh-suites/$n.log"; done
   ```

4. A red suite is breakage: **stop, mend it, and begin again at 1.** Run it
   again alone first (`deno run --allow-all tests/<name>.mjs`) to learn what
   kind: red again, it is yours or old (the baseline above says which); green,
   it is a flaky check nobody has explained, and it is not carried into the
   release as one — `python3 tests/repeat.py <name> -n 20`, and the other
   ways of making it fail under *Flaky tests*, find its cause in minutes.
5. Remove `../parseh-suites` when done.

### 2. The version

`VERSION` names the version being made from the day its work begins
(step 12 opens the next one), so it should already be right. Three files,
and only these, say the version, and until step 7 two of them still say it
is not released:

1. **`VERSION`** — one line, the version: check it with `cat VERSION`.
2. **`CHANGELOG.md`** — its newest heading, `## [<version>] - unreleased`.
   Read the section under it once more: it becomes the release's notes,
   word for word, and it is written for the people who use Parseh — what
   they will see, not how it was built. KEEP IT SHORT (the owner,
   2026-09-25): one line per group of work, the length of a commit's
   title, about ten lines for a version (more only for a big one), no
   details — those belong in What's new. A thing changed again before the
   release is said ONCE, as it now is, never as the first try and then its
   correction.
3. **`html-guide/markdown/reference/whats-new.md`** — its newest heading,
   `## <version> — not yet released`. Its sections say the same news as the
   changelog, for a reader, with links into the guide.

Then hold the three together — the tests must end `OK`, and `check` must
say `Agreed: <version>-rc1 rehearses <version> …`:

```bash
python3 -m unittest tests/test_version.py tests/test_html_guide.py; python3 lib/release.py check <version>-rc1
```

`check` here reads the working tree; GitHub runs the same check on the
tagged commit and makes nothing while they disagree.

### 3. The guide, compiled

The compiled guide, `html-guide/site/`, ships in the zip, so it is committed
with the Markdown it comes from (GitHub Pages compiles the same sources
again, when you launch it: step 8.4):

```bash
python3 html-guide/build.py
```

It must end `0 warnings, 0 errors`. When it names files *kept from the site
that was there*, look at each: one this computer cannot make (a font, a PDF)
is rightly kept, but a picture no page shows any more is a leftover — delete
it from `html-guide/site/`. Then ask the question GitHub will ask; it must
say `In step`:

```bash
python3 lib/release.py guide
```

Compile again after **any** later change to a guide page, a picture in it,
the guide's engine (`html-guide/engine/`) or the studio's renderer: each of
them puts the compiled guide out of step, and GitHub refuses the tag.

### 4. The rehearsal's commit, and its build

A release is built from a commit, never from the working tree.

1. Commit everything the release is — the changes, `VERSION`,
   `CHANGELOG.md`, `whats-new.md`, `html-guide/site/` — and nothing else.
   `git status --short` must then print nothing that belongs in the
   release. **Do not push.**
2. Build the rehearsal, exactly as GitHub will:

   ```bash
   python3 lib/release.py build --tag <version>-rc1
   ```

   It writes `dist/parseh-<version>-rc1.zip`, its `.sha256` and its list of
   files, `dist/parseh-<version>-rc1.manifest.json`, and says how many
   files, how big, from which commit, and *A rehearsal of <version>*. Under
   **NOT IN THIS BUILD** it names every file changed or new and not
   committed: each one must be something you meant to leave out. When it
   refuses, it says why; mend that, commit, and build again.
3. What GitHub will see is the commit, not your working tree (a stray file
   under `html-guide/markdown/` that is neither committed nor ignored
   counts on your computer and not there), so ask again of the commit —
   both must agree:

   ```bash
   python3 lib/release.py check <version>-rc1 --ref HEAD; python3 lib/release.py guide --ref HEAD
   ```

A fault found in steps 5 and 6 costs nothing: mend it, commit, and rehearse
again from step 3 under the next name, `<version>-rc2`.

### 5. The rehearsal, on Parseh-test

Start Parseh-test, from its own folder, **always on port 7655**:

```bash
./serve.sh 7655
```

Parseh-test is ALWAYS served on 7655, never on 7654, so that it cannot
damage the Parseh-mine installation: Parseh-mine answers on 7654, and the
browsers you use have accepted ITS certificate (from its own `.tls/`) for
that address; another install there would present them another one.

Your own steps, by hand, in the browser, at `https://localhost:7655/` —
never scripted. The point is to go through what somebody updating will go
through, and to prove that what is theirs survives it.

1. **Parseh-test runs `<previous>`, as released.** The hub's foot says
   which version it is. If it is anything else, put `<previous>` back:
   download `parseh-<previous>.zip` from its page on
   [GitHub's releases](https://github.com/parseh-io/Parseh/releases),
   then **Settings → Updating Parseh → A zip of your own**, choose it, and
   press the button (**Go back to…** or **Install … again**).
2. **It has something to lose**, and something new since last time:
   - a book **with its narration** — from Parseh-mine, its reader's download
     *all of it*, then **Bring a book back** on Parseh-test's books;
   - a video, the same way (**⤓** in the player, **Bring a video back**);
   - an exercise deck **with answers in its schedule** — answer two or three
     exercises now, so that some are new;
   - a dictionary — **Settings → Reading help**, the Persian dictionary is
     21 MB;
   - a changed setting — the theme, and the port (7655) on
     **Settings → Network**;
   - a LaTeX theme of your own on **Settings → LaTeX drawings**, a document
     with a `::::latex` block drawn with it, and one TeX package got there
     into `texmf/` (from a0.4.0 on). A theme's packages beyond the base are
     Parseh's own even where the computer's TeX has them all, so the
     *chemistry* theme's are always there to get: press **Get it** on
     `chemgreek` (7 kB), a few seconds, and draw with a theme that ticks
     `mhchem` only once `mhchem` is got too. (The main repository is a year ahead of a
     distribution's TeX Live, and tlmgr refuses it; Parseh then falls back,
     by itself, to the archive of the installed TeX Live's own year.)
   - speech to text — the program and `large-v3-turbo` on **Settings →
     Speech to text** (from a0.4.1 on; a 1.7 GB download, a minute or two).
     **a0.4.1 only:** Parseh-test runs a0.4.0 at step 1, which has no such page,
     so this one is done at the end of step 5, on the rehearsal, once that
     step's comparison has passed. Step 6's fingerprint, taken fresh, then holds
     `stt/`, and steps 6 and 7 prove that going back and going forward leave it.
     From a0.4.2 on it can be installed here, at the start, with the rest.
3. **Fingerprint what is yours**, in Parseh-test's folder (the readers, the
   library page and the phone's checksums are left out: an update rebuilds
   the first two and the server rewrites the others as it pleases):

   `stt/` is gigabytes once speech to text is installed: allow a minute for its
   line. Nothing may be in `stt/tmp/`: a transcription that is running holds
   audio there.

   ```bash
   find books youtube/videos youtube/anki markdown/library exercises clips dict corpus mt components texmf stt config .tls -type f -not -path '*/reader/*' -not -name index.html -not -name .reader-key -not -name digests.json -not -name wheres.json -not -name updates.json -print0 2>/dev/null | sort -z | xargs -0 sha256sum > ../parseh-test-before.txt
   ```

4. **Update to the rehearsal.** **Settings → Updating Parseh → A zip of
   your own**, choose `dist/parseh-<version>-rc1.zip` from the checkout.
   Before pressing anything, read **Ready to install**:
   - it says **↑ newer**, `<previous>` → `<version>-rc1`;
   - *Changed by hand since they were installed* lists nothing — the guide's
     compiled pages are listed apart, and are expected;
   - the environment line says what it will add, if `environment.yml`
     changed, and nothing otherwise (a0.4.1 leaves `environment.yml` alone:
     speech to text is installed by its own page into `stt/`, and is in no
     environment);
   - no *What may not survive going back* (that is only for going back).

   Press **Update to <version>-rc1**, then **Yes**. The page shows each
   step and comes back by itself.
5. **Check what survived.** **The last update** stands at the top and says
   what was written and deleted. **Settings → Updating Parseh** says
   `<version>-rc1`; the hub's foot says `<version>` (it reads `VERSION`,
   which never says `-rc`). Then:
   - the fingerprint again, and compare — **no line may differ**:

     ```bash
     find books youtube/videos youtube/anki markdown/library exercises clips dict corpus mt components texmf stt config .tls -type f -not -path '*/reader/*' -not -name index.html -not -name .reader-key -not -name digests.json -not -name wheres.json -not -name updates.json -print0 2>/dev/null | sort -z | xargs -0 sha256sum > ../parseh-test-after.txt; diff ../parseh-test-before.txt ../parseh-test-after.txt && echo "all yours, untouched"
     ```

     **a0.4.0 only.** a0.3.3 has no `texmf/`, and a0.4.0 ships one, holding
     a README, so that one line is *new*: `> … texmf/README.md`. It is the
     release's own file, not yours, and it is the only line that may differ
     — going back to a0.3.3 (step 6) takes it away again, and going forward
     (step 7) brings it back. Anything else is a fault. (Checked on
     2026-09-25 with the published a0.3.3 zip and this rehearsal's, on a
     throwaway install: exactly that one line, each time.)

   - the book opens and its narration plays in step;
   - the deck opens, and the exercises you answered are not *new* any
     more;
   - a word looked up in the book answers from the dictionary;
   - the theme is the one you set, and **Settings → Network** still says
     port 7655 and lists every device you let in;
   - the browser did not warn about the certificate again;
   - the document's latex block shows its drawing, and **Settings → LaTeX
     drawings** lists your theme and the package you got;
   - **Settings → Speech to text**, a page a0.4.0 does not have, opens and says
     **Not yet** of everything: it is the place the speech program and the
     models are got, and Parseh-test has none yet. Press **Get it** on
     **faster-whisper / large-v3-turbo** — it installs the program first, under
     one bar — and wait for **Installed**. Then **Add a video** offers to
     transcribe a short local film with it.

     **a0.4.1 only.** a0.4.0 has no `stt/` and a0.4.1 ships none, so this step's
     comparison has no `stt` line at all. What it installs now is what steps 6 and
     7 keep an eye on: step 6's fingerprint holds it, and **going back to a0.4.0
     leaves it as it is** (that version has no page to remove it), and so does
     going forward again. After step 7, **Settings → Speech to text** still says
     **Installed** for the program and the model — not *Built by an older
     Parseh* — and the short film still transcribes.
6. **Go back.** Take the fingerprint again first, into
   `../parseh-test-before.txt` as in 5.3 — opening the book moved its
   reading place in `config/prefs.json`. Then choose
   `parseh-<previous>.zip` the same way: the page says
   **↓ older — going back**, and the button **Go back to <previous>**. If
   this version raised a data format, it also says *What may not survive
   going back*, names it, and keeps the button off until you tick *I
   understand*: that is expected exactly when this version's changelog says
   it changed how something is stored, and a fault otherwise (a0.4.0 raised
   the documents, the decks, the bundles and the shelves: going back to
   a0.3.3 says so; speech to text adds no data-format row, so it never causes
   that box, and going back to a0.4.0 leaves `stt/` exactly as it is). Go back, and
   compare the fingerprint as in 5.5, before opening anything: no line may
   differ.
7. **Forward again, then the same version twice.** Choose
   `dist/parseh-<version>-rc1.zip` (↑ newer), update, and compare the
   fingerprint; then choose it once more: the page says **= the same
   version** and **Install <version>-rc1 again**, which is accepted, not
   refused as up to date. Install it, and compare a last time.

Parseh-test is left on `<version>-rc1`: the release itself will be ↑ newer
to it.

### 6. The rehearsal, on GitHub

The whole road GitHub takes — check, guide, build, notes, the draft — tried
once before it counts. Pushing a tag shows nobody anything but the tag and
its commit.

1. Tag the rehearsal's commit and push **the tag alone** — not `main`,
   which must not carry the rehearsal's undated pages (the guide on GitHub
   Pages is published from `main`, step 8.4):

   ```bash
   git tag -a <version>-rc1 -m "Parseh <version>, rehearsal 1"
   ```

   ```bash
   git push origin <version>-rc1
   ```

2. On GitHub, **Actions → release**: the run for `<version>-rc1` must end
   green (a few minutes). A red run says in its failing step why, and made
   no draft: see [When a draft is wrong](#when-a-draft-is-wrong).
3. On GitHub, **Releases**: at the top, **Parseh <version>-rc1**, marked
   **Draft** and **Pre-release** — visible to you, signed in, and to nobody
   else. Its assets are `parseh-<version>-rc1.zip` and its `.sha256` (and
   GitHub's own *Source code* archives, which are not the release). Its
   notes are the changelog's `<version>` section.
4. Download both assets in the browser, then — this must print `OK`, then
   say **They agree**:

   ```bash
   cd ~/Downloads && sha256sum -c parseh-<version>-rc1.zip.sha256; cd -
   ```

   ```bash
   python3 lib/release.py compare dist/parseh-<version>-rc1.zip ~/Downloads/parseh-<version>-rc1.zip
   ```

5. **Delete the rehearsal**, draft and tag. On the draft's page,
   **Delete** (the bin), and confirm. Then the tag, on GitHub and here:

   ```bash
   git push --delete origin <version>-rc1; git tag -d <version>-rc1
   ```

   Delete the two downloads as well.

### 7. The day, and the release commit

1. **Date both headings, the same day** — the day you will publish:
   - `CHANGELOG.md`: `## [<version>] - unreleased` becomes
     `## [<version>] - 2026-09-25` (year, month, day);
   - `whats-new.md`: `## <version> — not yet released` becomes
     `## <version> — 25 September 2026` (the way the guide writes a day, no
     leading zero).
2. **Compile the guide again** — dating What's new put it out of step:

   ```bash
   python3 html-guide/build.py
   ```

3. Hold them together, commit, and ask of the commit what GitHub will ask —
   the tests end `OK`, `check` says `Agreed: … released on the same day`,
   and `guide` says `In step`:

   ```bash
   python3 -m unittest tests/test_version.py tests/test_html_guide.py
   ```

   ```bash
   git commit -am "<version>: the day it is released" && python3 lib/release.py check <version> --ref HEAD && python3 lib/release.py guide --ref HEAD
   ```

   `check` names each heading it refuses, with its file and line, and says
   how the other day is spelt; mend it, compile, and commit again.
4. **Build the release** as GitHub will, for step 9's comparison:

   ```bash
   python3 lib/release.py build
   ```

   Then compare it with the rehearsal, which proves that nothing but the
   day changed since it was rehearsed:

   ```bash
   python3 lib/release.py compare dist/parseh-<version>-rc1.zip dist/parseh-<version>.zip
   ```

   It says **They DISAGREE** — on the version, the commit, and these five
   files only: `CHANGELOG.md`, `html-guide/markdown/reference/whats-new.md`,
   and the three the compile rewrote for it, `html-guide/site/build.json`,
   `html-guide/site/reference/whats-new.html` and
   `html-guide/site/search-index.js`. Any other file named is a change that
   was never rehearsed: rehearse again (step 3, `-rc2`).

If the release slips to another day, change both dates, compile, and commit
before you tag.

### 8. Tag and push: GitHub's draft

1. Tag the release commit and push it, with `main`:

   ```bash
   git tag -a <version> -m "Parseh <version>"
   ```

   ```bash
   git push origin main <version>
   ```

   Pushing `main` publishes nothing on GitHub Pages: it only makes the
   guide's workflow compile the guide, as a check (see 8.4).
2. On GitHub, **Actions → release**: the run for `<version>` must end
   green (a few minutes). A red run says in its failing step why —
   usually `check`, naming what disagrees — and made no draft: see
   [When a draft is wrong](#when-a-draft-is-wrong).
3. On GitHub, **Releases**: at the top, **Parseh <version>**, marked
   **Draft** and **not** pre-release — visible to you, signed in, and to
   nobody else. Its assets are `parseh-<version>.zip` and
   `parseh-<version>.zip.sha256` (and GitHub's own *Source code* archives,
   which are not the release and never get a checksum). Its notes are the
   changelog's section.
4. **The guide on `parseh.io/guide`: your own step, by hand, in the browser.**
   The guide is published when you launch its workflow, and only then — and
   the workflow is in **another repository**, `parseh-io/guide` (see [Where
   Parseh lives](#where-parseh-lives)): on GitHub, `parseh-io/guide` →
   **Actions → publish the guide → Run workflow**, `ref` **`main`**,
   `repository` left as it is (`parseh-io/Parseh`), **Run workflow**. It
   checks out this repository's `main`, compiles the guide there and its
   **deploy** job puts it on the site, in a minute or two; step 12.3 looks
   at the result. Do it on the day you publish the draft (step 10), with
   the release commit on `main`, and before step 12.7 puts the next
   version's *not yet released* heading there. Nothing else publishes it
   (a push to `Parseh` runs `guide-pages.yml`, which only compiles the guide
   as a check), and whoever follows the rest of this page for you does not
   launch it: they stop here and tell you.

### 9. The draft is what you built

1. On the draft's page, download **`parseh-<version>.zip`** and
   **`parseh-<version>.zip.sha256`** in the browser (you are signed in, so
   the draft's assets download like any file).
2. The zip is whole — this must print `OK`:

   ```bash
   cd ~/Downloads && sha256sum -c parseh-<version>.zip.sha256; cd -
   ```

3. It is what you built:

   ```bash
   python3 lib/release.py compare dist/parseh-<version>.zip ~/Downloads/parseh-<version>.zip
   ```

   It must say **They agree** — the same version, the same commit, every
   file with the same checksum and mode. It says as well whether the two
   zips are the same file byte for byte; when they are not, the files in
   them still are, which is what counts (two computers' compressors may
   pack the same bytes differently). **They DISAGREE** means the draft is
   not what you built: [When a draft is wrong](#when-a-draft-is-wrong).

### 10. Publish

The moment the world sees it.

1. On GitHub, **Releases**, the draft, **Edit** (the pencil).
2. Leave the notes as they are — they are the changelog's; a change to them
   is a change to `CHANGELOG.md` and a new draft.
3. **Set as a pre-release: LEAVE IT UNTICKED.** An alpha (`a…`) is
   published as a **full release**, never a pre-release: the `a` in front of
   the numbers is not a reason to tick it. A pre-release is invisible to
   GitHub's *latest release*, which is what every Parseh's **Check now**
   asks — ticked, the release would be there and nobody would be offered
   it (a0.3.2 was published so by mistake, 2026-09-25). Only a rehearsal's
   draft (`-rc1`) is a pre-release, and it is deleted, never published.
   **Set as the latest release**: ticked.
4. **Publish release**.
5. **Check it is the latest**, in a minute or two, from the terminal. The
   command asks every address Parseh names — the feed first — and prints
   what each answers:

   ```bash
   python3 lib/release.py links --expect <version>
   ```

   The first lines are the feed and the releases page: the feed's
   `tag_name` must be `<version>`. (If the box was ticked after all,
   GitHub's *release* workflow runs its guard on publishing, takes the mark
   off and makes the release the latest — **Actions → release**, the run
   named after the release, says so in a warning — and the feed then names
   `<version>` too.) The lines about the guide are step 12.4's: they are red
   until step 8.4's run has finished.

From now on this release is somebody's download: it is never replaced, and
its tag never moves. GitHub's workflow refuses to build over it.

### 11. Parseh-mine, from GitHub

Your own step, by hand, in the browser, **once the release is published**:
Parseh-mine updates the way everybody's does — from GitHub, through the
updater's public road, never from a zip you downloaded or built — and it is
the first to take it.

1. On Parseh-mine (`https://localhost:7654/`), **Settings → Updating Parseh
   → Check now**: it names `<version>` as the newest release. (A Parseh
   built before the move to `parseh-io` — a0.4.3 and before — asks the old
   address of the repository, which GitHub redirects to the new one for as
   long as nobody takes the old name again: this step is that redirect's
   proof, and its result goes in [Where Parseh lives](#where-parseh-lives).
   If it says it cannot reach GitHub, take the release's zip by hand
   (**A zip of your own**): that is the whole of the owner's rule for his own
   copy.)
2. **Download**: the zip GitHub built comes down and is checked against the
   `.sha256` published beside it.
3. Read **Ready to install** as in step 5.4: ↑ newer, nothing changed by
   hand but the guide's compiled pages, the environment line.
4. **Update to <version>**, **Yes**, and wait for the page to come back.
5. Then use it for a few minutes as on any day: a book and its narration, a
   video, a deck, a word looked up, the page you last worked on. The hub's
   foot says `<version>`.

If anything is wrong, it is wrong for everybody: go to
[When a published release is bad](#when-a-published-release-is-bad) at once
(withdraw it first), and take Parseh-mine back through the updater
(**A zip of your own**, `parseh-<previous>.zip` from its page on GitHub's
releases, **Go back to <previous>**).

### 12. Afterwards

1. **The public road, once more.** On Parseh-mine, **Check now** now says
   *the version this Parseh already is*. On Parseh-test, go back to
   `<previous>` with its zip, then **Check now**, **Download** and **Update
   to <version>**: the whole road a user takes, checksum included, from the
   other direction. (Parseh-test then runs `<version>`, ready for the next
   rehearsal.) On a version that moved the project, Parseh-test runs the
   previous release, which asks the OLD address: it is the same proof as
   step 11's, made on a copy.
2. **The releases page, signed out** (a private window): the release is
   there, with the zip and its `.sha256`, and no rehearsal.
3. **The guide is current** — the run you launched in step 8.4. GitHub,
   `parseh-io/guide` → **Actions**: the *publish the guide* run is green,
   its **deploy** job too. Then
   `https://parseh.io/guide/site/reference/whats-new.html`
   shows `<version>` with its day, under the bar with Parseh's logo. If it
   shows the version before, the run was not launched: launch it now, from
   `main`.
4. **Every address answers.** From the checkout, once the run is done:

   ```bash
   python3 lib/release.py links --expect <version>
   ```

   It must print nothing red and exit with 0: the feed names `<version>`;
   `https://parseh.io/` answers; `https://parseh.io/guide` ends at
   `https://parseh.io/guide/` with the only hop GitHub's own; the deep link
   above answers at its own address with the bar in it; the phone app's
   icons answer `200 image/png` **with no redirect at all**; every link of
   `README.md`, `docs/` and the guide's sources ends in 200. Add `--old` to
   see what the old addresses answer. The first lines also report, without
   failing, what `https://parseh-io.github.io/guide/` (a redirect to the
   domain) and `https://parseh.io/Parseh/` (404: Pages is off in `Parseh`)
   say.
5. **README.md** needs nothing: it names no version and links to the newest
   release (a test holds it so).
6. **The baseline.** If step 1 found the reds different from the table
   above — one mended, a new known one accepted — write the new table, with
   its date.
7. **Open the next version.** Decide its number (the next `a0.x.y`; it can
   be renamed while it is unreleased), then, in one commit:
   - `VERSION` — the next version;
   - `CHANGELOG.md` — a new heading at the very top,
     `## [<next>] - unreleased`;
   - `whats-new.md` — a new heading above the others,
     `## <next> — not yet released`;
   - the guide compiled again (`python3 html-guide/build.py`): the new
     heading changed What's new.

   `python3 -m unittest tests/test_version.py tests/test_html_guide.py`
   must be `OK`. Commit, push.
8. **Clear up**: `dist/` (ignored by git, and made again at will), the two
   fingerprints `../parseh-test-*.txt`, and the downloads.
9. **An announcement**, if this version is one to announce, is a piece of
   work of its own, not a step of this list.

## Where Parseh lives

*Since a0.4.4 (decided with the owner on 2026-09-30 and 2026-10-05).*

**The project is the repository `parseh-io/Parseh`**, in the GitHub
organisation `parseh-io`. It was moved there by a *transfer* of the
repository the owner's own account held, not by making a new one, so that its
releases, its tags and the road every earlier install updates by came along.
The author's profile (the GitHub link beside his name: the Licences page,
Settings → About and the README) is a **person's** address and stays where
he is; it is not the project's, and `lib/author.py` and `lib/project.py` say
so. The GitHub link at the foot of the hub, of the Settings hub and of every
page of the guide, on the other hand, is the **project's**: the page that
draws the foot hands `project.GITHUB_URL` to `lib/author.py`.

**One module says where Parseh lives: `lib/project.py`.** The update road
(the feed Settings → Updating Parseh asks, the releases page its refusals
name), the GitHub link at the foot of the hub, the Settings hub and the guide,
the two links at the foot of every page exported from the studio, the
phone app's icons and the line each download introduces itself with are all
built from it, and nothing else in the tree spells the organisation or the
domain. **A move is one edit there**, then:

```bash
python3 lib/release.py links --old
```

which asks every address Parseh names and prints what answers (step 12.4).
`tests/test_project.py` pins the literal addresses and keeps the old place
out of the tree.

**Three repositories and one domain.** The domain `parseh.io` is the
owner's, served by GitHub Pages: its records at Cloudflare are *DNS only*
(grey cloud, never proxied: GitHub cannot renew its certificate through
Cloudflare's), and the mail records are not touched.

| Repository | Served at | What it holds |
|---|---|---|
| `parseh-io/parseh-io.github.io` | `https://parseh.io/` | Parseh's site (its own repository, its own design). Its custom domain, `parseh.io`, is what puts every other Pages site of the organisation under the domain. |
| `parseh-io/guide` | `https://parseh.io/guide/` | No pages of its own: a README and ONE workflow, *publish the guide*, run by hand (step 8.4). It checks out `parseh-io/Parseh` at a ref, compiles the guide with `html-guide/build.py --pages` and publishes it. The guide's path under the domain is **this repository's name**. |
| `parseh-io/Parseh` | nothing | Pages is switched OFF here (an old copy of the guide would stay at `parseh.io/Parseh/`). `guide-pages.yml` only compiles the guide on every push to `main`, as a check that it still builds on a clean machine. |

**The guide's address is `https://parseh.io/guide`**, and a page exported
from Parseh carries it for ever in its foot: so the domain must **never
lapse** (auto-renew on, the registrar lock on, two-factor authentication on
the Cloudflare account, the renewal price known) — a lapsed domain would put
a stranger's page behind the guide link of every export. The old address of
the guide, `https://addicted2bayesianepistemology.github.io/Parseh/`, is
**dead** and stays so: GitHub does not redirect Pages after a transfer. A page
exported by Parseh before a0.4.4 carries it; nothing can mend that.

**What an old install does.** A Parseh built before a0.4.4 asks the feed at
the old repository's name. After a transfer GitHub answers it with a `301`
to the repository's number, which `urllib` follows, and the release's zip
and `.sha256` still download from the old address: so an old install's
**Check now** finds the new release, for as long as nobody takes the old
name again. (Measured on other repositories on 2026-09-26; for this one it
is step 11's first look, and `links --old` shows the `301`.) What it did:
**2026-10-06, the day of the transfer** — a0.4.1's own `lib/updater.py`,
making its own request, asked
`api.github.com/repos/Addicted2BayesianEpistemology/Parseh/releases/latest`
and was answered `200` at `api.github.com/repositories/1379498689/releases/latest`;
the answer already names the zip and its `.sha256` under `parseh-io/Parseh`,
and both downloaded. The same road through Settings, to a release published
from the new home, **the same day**: the owner's own install (Parseh-mine,
built before the move) found a0.4.4 with **Check now**, downloaded it,
checked it and updated — the redirect carried it, and the zip by hand was
not needed. The owner's rule (2026-09-30) is that nobody but him had
installed Parseh, so no bridge release stands in the old repository: his own
copy takes the release by the public road if the redirect holds, and by the
zip if it does not.

**Never** (each of these deletes something for good or breaks it silently):

- create a repository named `Parseh` under `Addicted2BayesianEpistemology` —
  or **fork** `parseh-io/Parseh` into that account under its default name,
  which is the same thing: it deletes GitHub's redirect from the old address
  for good. Rename the fork in the dialog, or do not fork;
- rename or delete the personal account;
- rename the repository `guide`: its name IS the guide's address;
- proxy the domain's records at Cloudflare (orange cloud), or give
  `parseh-io/guide` a custom domain of its own;
- publish the guide from anywhere but the hand-run workflow of
  `parseh-io/guide`, or let a push do it.

## When a draft is wrong

Nothing of a draft is public but its tag (and the commits it points at), so
a draft is cheap to replace.

**A rehearsal's draft** (`<version>-rc1`) is never mended in place: delete
it and its tag (step 6.5), mend on `main`, commit, and rehearse again under
the next name, `<version>-rc2`, from step 3.

**The version's own draft**: mend, commit, and move the tag onto the new
commit. The workflow runs again and its draft replaces the old one.

1. Mend it on `main`, commit, build (step 7.4) and, if the mend is more
   than a word of the notes, rehearse it (steps 5 and 6, the next `-rcN`).
2. Move the tag, and push it over the old one:

   ```bash
   git tag -f -a <version> -m "Parseh <version>"
   ```

   ```bash
   git push origin main && git push --force origin <version>
   ```

3. Go on from step 8.2.

**When the run is red at *The tag, VERSION, the changelog and What's new
agree*** (`check`): the step's log names each thing that disagrees — a tag
that is not `VERSION`'s, a heading still `unreleased` or *not yet
released*, two headings on different days (with the line, and the day
spelt as the other file spells it). Mend them as step 7.1 says, compile
the guide, commit, and move the tag as above.

**When the run is red at *The compiled guide is in step with its
sources*** (`guide`): the log says *Not in step*, and why — the compiled
guide is not what the commit's pages compile to (a page, a picture, the
guide's engine or the studio's renderer changed after the last compile),
its last compile had errors, or there is none. Compile it
(`python3 html-guide/build.py`, `0 errors`), commit `html-guide/site/`,
check that `python3 lib/release.py guide --ref HEAD` now says `In step`,
and move the tag as above.

**To start again from nothing**, delete the draft (its page, **Delete**) and
the tag, then begin again at step 8:

```bash
git push --delete origin <version>; git tag -d <version>
```

**To run the workflow again without a new commit**: GitHub, **Actions →
release → Run workflow**, and type the tag. Should a run for a tag that has
only a draft stop at *Never over a published release*, delete the draft by
hand and run it again.

## When a published release is bad

A published release has been downloaded by somebody: it is **never
replaced, never deleted, and its tag never moves** — two different
Parsehs under one number would be worse than the fault. There are three
answers, and a bad fault takes all three, in this order:

1. **Withdraw it, so that nobody new gets it.** On GitHub, the release,
   **Edit**, tick **Set as a pre-release**, **Update release**. The page
   stays, for those who have it, but GitHub's *latest release* is
   `<previous>` again, so **Check now** stops offering the bad one to
   everybody. At the top of its notes (editing the notes of a published
   release is allowed; its files are not), say what is wrong and what to
   do: *Do not install this version: … If you have, go back: Settings →
   Updating Parseh, choose the zip of <previous>.*
2. **Tell people to go back.** Going back is the updater's own road:
   **Settings → Updating Parseh → A zip of your own**, `<previous>`'s zip
   from its release page, **Go back to <previous>**. Somebody who has the
   bad version and presses **Check now** is shown `<previous>` as *OLDER
   than this Parseh*, with the same button. If the bad version raised a
   data format, going back asks them to tick *I understand* and keeps a copy
   of their small files first; say so in the notes.
3. **Supersede it.** Mend the fault and release the next version by this
   whole checklist, from step 1, as quickly as care allows. Once it is
   published, **Check now** offers it to everybody, the ones on the bad
   version included.

A fault that loses data or stops Parseh starting calls for all three at
once. A fault that only looks wrong calls for the third alone.

## The first managed release

a0.3.2 is the first version released this way: every Parseh before it has
no `.parseh-release.json`, and **Settings → Updating Parseh** refuses such an
install, saying to install afresh from a release. So, that once:

- **The baseline** is the table above, taken on the a0.3.2 tree itself;
  there is no earlier tag to take it on.
- **Parseh-test** is made fresh from the rehearsal's local build —
  unpacked from `dist/parseh-<version>-rc1.zip` into a new folder,
  installed with its installer, started with `./serve.sh 7655` (then the
  port set to 7655 on **Settings → Network**). With no previous release to
  come from or go back to, 5.1 is that fresh install, and 5.4 to 5.7 go up
  to a throwaway *next* version built in a scratch clone and back down
  again (to `dist/parseh-<version>-rc1.zip`):

  ```bash
  git clone -q . ../parseh-next && cd ../parseh-next && echo <next> > VERSION && git commit -qam "throwaway <next>" && python3 lib/release.py build --out ../parseh-next-dist; cd -
  ```

  That clone is never pushed; delete `../parseh-next` and
  `../parseh-next-dist` after the rehearsal.
- **Parseh-mine** is moved into a fresh install made from the PUBLISHED
  release's zip, downloaded from its page on GitHub's releases, by hand, as
  the guide's *Updating Parseh → Moving into a fresh install, once*
  describes, in place of step 11's update — then checked as step 11.5 says.
  From the next release on it updates from GitHub like everybody's.
- **12.1's second half** (going back to `<previous>`, then the public road)
  waits for the second release.
