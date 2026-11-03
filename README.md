<!--
  The banner is docs/banner-light.svg and docs/banner-dark.svg, built from
  docs/banner.tex by `cd docs && ./banner.sh` (never edit the SVGs).  Keep
  the pair: GitHub picks the dark one on a dark theme.
-->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/banner-dark.svg">
    <img src="docs/banner-light.svg" width="820"
         alt="Parseh — one toolbox for reading a language the Ilya Frank way">
  </picture>
</p>

A toolkit for learning languages through annotated content and active
recall. Read books and watch videos glossed the Ilya Frank way, chunk by
chunk, with the narration in step; write notes and interactive exercises in
a Markdown dialect of its own and study them with spaced repetition; turn
anything you read into Anki cards. Twelve languages: Persian, Arabic,
Italian, Japanese, French, German, Turkish, English, Hindi, Spanish,
Chinese and Catalan.

**In alpha: bugs are to be expected.** The newest version is on the
[releases page](https://github.com/parseh-io/Parseh/releases/latest),
with what it changed; the one you are running is written at the foot of
Parseh's hub. ([`CHANGELOG.md`](CHANGELOG.md) lists every version.)

**The guide — installing, using and extending Parseh, and the full reference
of its Markdown dialect — is at
<https://parseh.io/guide/>.**

## Quick start

Download **`parseh-<version>.zip`** from the newest release's *Assets* on the
[releases page](https://github.com/parseh-io/Parseh/releases/latest)
— not *Code → Download ZIP*, which is the source code — and unpack it where
Parseh will live. In that folder:

| Linux | macOS | Windows |
|---|---|---|
| `./install.sh`, then `./serve.sh` | double-click **`Parseh.command`** | double-click **`install.bat`**, then **`serve.bat`** |

Then open <https://localhost:7654/> and accept the browser's warning about
the certificate, once — it is one Parseh makes for this computer alone.

A fresh install answers **this computer** and any other on your **personal VPN**: Tailscale's range is
trusted out of the box, and any other name or range you add. The local network access is also allowed — open it in **Settings → Network**, on the hub, and let
each phone in once with the pairing code the page shows.

A new version comes in from **Settings → Updating Parseh**, keeping your
books, videos, decks, dictionaries and settings.

Then read on the phone. The mobile interface installs **as an app**:

| Android | iOS |
|---|---|
| **1.** Download the certificate from `/m/install/`, then *Settings* → search *CA certificate* → *Install anyway*, and pick `Parseh-CA.crt`. | **1.** Download the certificate, *Install* the profile in *Settings*, then *General* → *About* → *Certificate Trust Settings* and turn on full trust for *Parseh local authority*. |
| **2.** Chrome offers **Install Parseh** on that page; or its **⋮** menu → *Install app*. | **2.** In Safari, the **Share** button → *Add to Home Screen*. |

The guide has the details:
[Installing Parseh](https://parseh.io/guide/site/getting-started/installing.html),
[Reaching Parseh from other devices](https://parseh.io/guide/site/getting-started/other-devices.html)
and [Browser and Mobile](https://parseh.io/guide/site/getting-started/mobile-mode.html).

## License

Copyright © 2026 Bruno Ursino, the author of Parseh —
[GitHub](https://github.com/Addicted2BayesianEpistemology) ·
[imbrunoursino.net](https://imbrunoursino.net/).

Parseh is free software under the GNU General Public License, version 3
or (at your option) any later version — `GPL-3.0-or-later`
([`LICENSE`](LICENSE)); every source file says so in its
`SPDX-License-Identifier` line.

What it carries of other people's work keeps their licences:

- the fonts in `lib/fonts/` (Vazirmatn, Noto Naskh Arabic, Noto Nastaliq
  Urdu, Noto Serif Devanagari): SIL Open Font License 1.1 — the licence and
  their copyright notices in [`lib/fonts/OFL.txt`](lib/fonts/OFL.txt), every
  file named in [`lib/fonts/README.md`](lib/fonts/README.md);
- TeX Gyre Pagella, Heros and Chorus, which now travel with Parseh in `lib/fonts/`
  (Pagella, Heros and Chorus also in the compiled guide, `html-guide/site/_parseh/fonts/`;
  Chorus sets only the name Parseh, in the bars and the hub's title): GUST Font
  License ([`lib/fonts/GUST-FONT-LICENSE.txt`](lib/fonts/GUST-FONT-LICENSE.txt)),
  every file named in [`lib/fonts/README.md`](lib/fonts/README.md);
- MathJax 3.2.2 (`lib/mathjax/`): Apache License 2.0 (its `LICENSE` beside it);
- the Italian hyphenation patterns (`markdown/exlex/assets/hyph/hyph-it.tex`,
  © Claudio Beccari, hyph-utf8): LaTeX Project Public License 1.3 or later,
  or MIT — the file's header says so and carries the MIT text;
- excerpts in the tests' data (`tests/fixtures/`): conjugation rows from
  Wiktionary (CC BY-SA 4.0) and sentences from Tatoeba (CC BY 2.0 FR).
  [`tests/fixtures/README.md`](tests/fixtures/README.md) says where every
  test text comes from.

The dictionaries, sentences, translation models and character data the
reading help downloads on request are not in the repository; each keeps its
own licence, which travels inside the file it becomes. The app's
**Licences** page (the hub's foot, `/licences/`) lists all of it. The
repository ships the software and none of the content: what you read with
it is yours.
