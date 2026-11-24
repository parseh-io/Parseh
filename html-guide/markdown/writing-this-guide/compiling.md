---
title: Compiling and publishing
weight: 7
description: The compile and what it says, reading the guide, GitHub Pages, and a project of its own.
---

## Compiling

The pages in `html-guide/markdown/` become web pages in
`html-guide/site/` when they are compiled. Three things compile them:

- **The installer**, every time it runs, on every system: its step
  “the guide”. On Linux and macOS, `./install.sh --guide` does that step
  and nothing else.
- **The guide's front page, when Parseh serves it.** The hub's **guide**
  button opens it; when the compiled pages are missing, or older than the
  Markdown they come from, it says so and offers **Compile the guide**,
  and opens the new pages when the compile is done. If the compile fails,
  it still opens every page it could write, and what it said is shown on
  the front page.
- **`html-guide/build.py`**, run by hand, with any Python 3 — it needs
  nothing but the standard library.

`site/` is not kept in git: it is made from `markdown/`, whole, by every
compile.

## What the compile says

```text
warning: markdown/writing-this-guide/pages.md:48: no such file: shots/editor.png (looked for markdown/writing-this-guide/shots/editor.png)
error: markdown/showcase.md:12: ref: no page 'studio/decks.md'
the guide: 11 pages and 3 other files -> html-guide/site; 1 warning, 1 error
```

Each line names the page and the line. A **warning** leaves the page as
good as it can be — a picture missing, a link to a page that is not there,
an unknown shortcode (drawn as a red box), an exercise that needs attention
(drawn as the studio draws it) — and the compile goes on. An **error** —
a `ref` to no page, a front matter that cannot be read — still writes every
page it can, and makes the compile end with a failure, so that the
installer and the page's button say so.

```bash
python3 html-guide/build.py             # compile into html-guide/site/
python3 html-guide/build.py --check     # compile into a scratch folder and only say what is wrong
python3 html-guide/build.py --strict    # warnings fail it too
python3 html-guide/build.py --clean     # remove html-guide/site/
python3 html-guide/build.py --draw      # draw the LaTeX drawings the pages ask for, and stop
python3 html-guide/build.py --draw --check   # only say which it would draw
```

A compile takes a second or two for the whole guide, and gives the same
files for the same pages every time: nothing in them depends on the day.

## LaTeX drawings {#latex-drawings}

A page may hold a [LaTeX drawing](../dialect/latex-drawings.md), a
`::::latex` block or a `[…]{latex}` mark. **A compile never draws one**:
it needs nothing but the standard library, and no TeX. Every drawing a
page shows is a picture made beforehand and kept in
`html-guide/markdown/drawings/` — `<name>.svg`, and its size in
`<name>.json` — which the compile copies to the site with the other
pictures, so a machine with no TeX, or GitHub's, builds the same pages.

- **`--draw` makes them.** It compiles the guide into a scratch folder to
  learn which drawings the pages ask for, draws the ones the folder does not
  hold yet, and removes the ones no page asks for any more. It is a
  developer's step, run from the Parseh checkout on a computer that has
  TeX (xelatex) and the checkout's environment (PyMuPDF); a guide exported
  out of Parseh has no drawer, and carries the pictures it has. Commit the
  pictures with the page.
- **The three starter themes only.** The guide draws with `default`,
  `chemistry` and `drawing`, as a fresh Parseh has them, never with the
  themes in this computer's Settings, so that it is the same on every
  computer. A block or a mark naming another theme is not drawn, and the
  compile says so.
- **The name is what the picture is made of.** It comes from the LaTeX, the
  theme's packages and whether it is a mark in a line, and from nothing of
  the computer. A changed LaTeX is a new picture, and the old one goes at
  the next `--draw`.
- **A drawing that is not there** is shown as the studio shows one it
  cannot make — its LaTeX in a frame, or in code where it stands — and the
  compile warns, *no pre-drawn picture … run html-guide/build.py --draw*.
  `--strict` makes that a failure.

## Reading it

The same compiled pages work three ways, which is why every address in
them is relative:

1. **In Parseh**, from the hub's **guide** button, at
   `http://localhost:7654/guide/`.
2. **From the disk**: open `html-guide/index.html` in a browser. Nothing
   needs a server — not the list of pages, the search, the exercises or
   the formulas.
3. **On the web**, below: Parseh's own guide at `https://parseh.io/guide`, or a copy of your own on GitHub Pages.

## Publishing on GitHub Pages

**Parseh's own guide** is at `https://parseh.io/guide`. It is not published
from the Parseh repository: the organisation's domain serves each repository
of it that publishes Pages at `parseh.io/<repository name>`, so the guide has a
repository of its own, `parseh-io/guide`, whose name is the address and is
never changed. It holds no pages, only one workflow, **publish the guide**,
which the owner runs by hand (**Actions → publish the guide → Run workflow**).
It checks Parseh out at `main`, runs `python3 html-guide/build.py --pages
_site` and publishes the result: a changed page reaches the web when it is on
`main` and that workflow has been run. The workflow in Parseh,
`.github/workflows/guide-pages.yml`, only compiles the guide on every push
that changes it, as a check that it still builds, and publishes nothing.

`--pages` puts the front page, `assets/` and the compiled `site/` together in
one folder — the same layout as `html-guide/`, so the same relative
addresses hold, and the same folder can be put on any static host. In a
checkout of Parseh it also lays out the phone app's icons (`lib/icons/`, which
Chrome fetches from the internet when it builds the app) and gives every page
a bar at the top, the website's own: the Parseh logo and name, which lead to
`https://parseh.io`, with Guide marked as where you are. The guide that comes
with an install, `html-guide/site/`, has neither, and a guide exported into a
project of its own (below) has neither.

**A copy of your own** on a GitHub account's Pages — a person's or an
organisation's — is one setting away in your fork, because the repository's
root holds the two small files GitHub Pages needs to serve the committed pages
as they are: `index.html`, which sends a visitor on to the guide's front page,
and an empty `.nojekyll`, without which GitHub would leave out the folders
whose names start with `_` (the studio's runtime among them):

1. On GitHub, open the repository's **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a
   branch**, pick the branch **main** and the folder **/ (root)**, and
   press **Save**.

The guide is then at `https://<your account>.github.io/Parseh/`, a minute or
two later, and each push to `main` publishes it again. A changed page reaches
the web once it is compiled and committed: compile (the front page's button,
`./install.sh --guide` or `python3 html-guide/build.py`), then commit
`html-guide/markdown/` and `html-guide/site/` together. To have GitHub compile
the guide instead, set **Source** to **GitHub Actions** and give your fork a
workflow like the one in `parseh-io/guide`: check Parseh out, set up Python,
run `python3 html-guide/build.py --pages _site`, and publish `_site` with
GitHub's Pages actions.

## A project of its own

The guide is meant to be part of Parseh's website one day, in a repository
that holds nothing else.

```bash
python3 html-guide/build.py --export ../parseh-site
```

copies the guide there — the engine, the assets, the pages, the front page
— with a snapshot of exactly what it takes from Parseh (the studio's parser
and renderer, the language registry, the exercises' script and stylesheet,
MathJax, the fonts and their licences) in `engine/vendor/`, and a workflow of
its own for GitHub Pages. The copy compiles on its own, with any Python 3,
into the same pages. Run the export again to bring the snapshot up to date.

The folder must be new or empty, or an earlier export: the export replaces
the engine, the pages and the front page in it. Any other folder is refused
and left exactly as it was — and so is one given to `--out` or `--pages`
that holds anything but what they made there before.
