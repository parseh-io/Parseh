# SPDX-License-Identifier: GPL-3.0-or-later
"""The licences page, /licences/: what Parseh is under, and what it carries
and fetches of other people's work under theirs.

The GPL asks a program with an interactive interface to show "Appropriate
Legal Notices" -- the copyright, that there is no warranty, the licence and
how to read it (GPL-3.0, section 0).  This page is where the toolbox shows
them, linked from the foot of the hub in both of its layouts.  It carries
both layouts itself, the way the hub does (docs/mobile.md): one column that
reads on a phone, and nothing on it that edits.

WHAT IT LISTS IS NAMED ONCE.  The licences of what the reading help
downloads are read from the downloaders themselves (getdict, getcorpus,
getmt, getsyn, and decomposition's PACKS), which also write them into the
file each builds -- so this page cannot say one thing while the file says
another.  The fonts are FONTS below, which tests/test_licences.py holds to
what lib/fonts/ holds, to its README and to OFL.txt.
"""
import html
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import mobile                                                  # noqa: E402
import author                                                  # noqa: E402

# Parseh's own licence, as SPDX names it (every source file's header says the
# same), and the file with its text, at the top of the checkout
LICENCE = "GPL-3.0-or-later"
LICENCE_FILE = os.path.join(ROOT, "LICENSE")

# The fonts in lib/fonts/: (family, version, the copyright notice exactly as
# the font carries it, its files, where it comes from).  All under the SIL Open
# Font License 1.1, whose text is lib/fonts/OFL.txt; each file also carries its
# notice and the licence's name in its own name table, so a face packed into
# an Anki deck goes with its licence.
FONTS = (
    ("Noto Naskh Arabic", "2.004",
     "Copyright 2019-2020 Google LLC. All Rights Reserved.",
     ("NotoNaskhArabic-Regular.ttf", "NotoNaskhArabic-Bold.ttf", "NotoNaskhArabic.woff2"),
     "https://notofonts.github.io"),
    ("Noto Nastaliq Urdu", "20.0d1e3",
     "Copyright 2014 Google Inc. All Rights Reserved.",
     ("NotoNastaliqUrdu-Regular.ttf", "NotoNastaliqUrdu.woff2"),
     "https://notofonts.github.io"),
    ("Noto Serif Devanagari", "2.001",
     "Copyright 2019 Google Inc. All Rights Reserved.",
     ("NotoSerifDevanagari-Regular.ttf", "NotoSerifDevanagari-Bold.ttf",
      "NotoSerifDevanagari.woff2"),
     "https://notofonts.github.io"),
    ("Vazirmatn", "33.003",
     "Copyright 2015 The Vazirmatn Project Authors (https://github.com/rastikerdar/vazirmatn)",
     ("Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf", "Vazirmatn.woff2"),
     "https://github.com/rastikerdar/vazirmatn"),
)
# THE FACES THE STUDIO AND THE GUIDE ARE SET IN, which now travel with Parseh
# rather than being copied out of a TeX installation (TO-DO §2.23: on a
# machine without TeX the compile used to drop them, and the seven tracked
# files vanished from the compiled guide).  They are under the GUST Font
# License, whose text is lib/fonts/GUST-FONT-LICENSE.txt -- one text for the
# whole family rather than a copyright line per font, which is why they are a
# tuple of their own and not part of FONTS above.
GUST_FONTS = (
    ("TeX Gyre Pagella", "2.501",
     "\u00a9 B. Jackowski, J. M. Nowacki and the TeX users groups (GUST)",
     ("texgyrepagella-regular.otf", "texgyrepagella-bold.otf",
      "texgyrepagella-italic.otf", "texgyrepagella-bolditalic.otf"),
     "https://www.gust.org.pl/projects/e-foundry/tex-gyre"),
    ("TeX Gyre Heros", "2.004",
     "\u00a9 B. Jackowski, J. M. Nowacki and the TeX users groups (GUST)",
     ("texgyreheros-regular.otf", "texgyreheros-bold.otf", "texgyreheros-italic.otf"),
     "https://www.gust.org.pl/projects/e-foundry/tex-gyre"),
    ("TeX Gyre Chorus", "2.003",
     "\u00a9 B. Jackowski, J. M. Nowacki and the TeX users groups (GUST)",
     ("texgyrechorus-mediumitalic.otf",),
     "https://www.gust.org.pl/projects/e-foundry/tex-gyre"),
)
# the licence files that travel beside the fonts, served from the same folder
FONT_LICENCE_FILES = ("OFL.txt", "GUST-FONT-LICENSE.txt")

# Where each licence can be read.  A local copy where the toolbox has one; the
# licence's own page otherwise.  A downloader that starts naming a licence
# not here fails tests/test_licences.py, rather than drawing it with no link.
LICENCE_URLS = {
    "GPL-3.0-or-later": "/licences/LICENSE",
    "OFL-1.1": "/lib/fonts/OFL.txt",
    "GUST": "/lib/fonts/GUST-FONT-LICENSE.txt",
    "Apache-2.0": "/lib/mathjax/LICENSE",
    "LPPL-1.3": "https://www.latex-project.org/lppl/",
    "MIT": "https://opensource.org/license/mit",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-NC-SA-4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY 2.0 FR": "https://creativecommons.org/licenses/by/2.0/fr/deed.en",
    "MPL 2.0": "https://www.mozilla.org/MPL/2.0/",
    "WordNet": "https://wordnet.princeton.edu/license-and-commercial-use",
    "LGPL-3.0-or-later": "https://www.gnu.org/licenses/lgpl-3.0.html",
    "GPL-2.0": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
    # PyAV, which speech to text's program carries (lib/getstt.py)
    "BSD-3-Clause": "https://opensource.org/license/bsd-3-clause",
    # the ARASAAC pictograms (lib/getarasaac.py): the deed ARASAAC's own terms page links
    "CC BY-NC-SA 4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
}


def esc(s):
    return html.escape(str(s), quote=True)


def licence_link(name, key=None):
    """A licence's name, linked to where it can be read."""
    url = LICENCE_URLS.get(key or name)
    if not url:
        return esc(name)
    ext = "" if url.startswith("/") else ' rel="noopener" target="_blank"'
    return '<a href="%s"%s>%s</a>' % (esc(url), ext, esc(name))


def work(title, what, who, licence):
    """One work: its name, what it is to Parseh, whose it is, its licence --
    `licence` already HTML."""
    return ('<section class="work">\n  <h3>%s</h3>\n  <p class="what">%s</p>\n'
            '%s  <p class="lic">%s</p>\n</section>\n'
            % (esc(title), what, ('  <p class="who">%s</p>\n' % who) if who else "", licence))


def carried():
    """What travels in the repository that is not Parseh's own work."""
    out = []
    for family, version, notice, files, home in FONTS:
        out.append(work(
            "%s %s" % (family, version),
            "A font, in <code>lib/fonts/</code>: %s. From <a href=\"%s\" rel=\"noopener\" "
            "target=\"_blank\">%s</a>." % (", ".join("<code>%s</code>" % esc(f) for f in files),
                                           esc(home), esc(home.split("//", 1)[1])),
            esc(notice),
            "SIL Open Font License 1.1 &mdash; " + licence_link("its text, and every font's notice",
                                                               "OFL-1.1")))
    out.append(work(
        "TeX Gyre Pagella, TeX Gyre Heros and TeX Gyre Chorus",
        "The fonts the studio&rsquo;s and the guide&rsquo;s pages are set in, in "
        "<code>lib/fonts/</code>: %s. They travel with Parseh, so a machine with no TeX "
        "installation still has them; the studio copies them into its own static folder "
        "when it starts, and the guide&rsquo;s build into its site, with their licence "
        "beside them. (Chorus is the odd one out: no document is set in it, only the name "
        "Parseh, in the bar of every page of Parseh and in the hub&rsquo;s title, as on "
        "the website.) From "
        "<a href=\"https://www.gust.org.pl/projects/e-foundry/tex-gyre\" "
        "rel=\"noopener\" target=\"_blank\">gust.org.pl</a>."
        % ", ".join("<code>%s</code>" % esc(f) for fam in GUST_FONTS for f in fam[3]),
        "&copy; B. Jackowski, J. M. Nowacki and the TeX users groups (GUST)",
        "GUST Font License &mdash; the LaTeX Project Public License 1.3c or later, with a "
        "request to rename a modified font; " + licence_link("its text", "GUST")))
    out.append(work(
        "MathJax 3.2.2",
        "What draws a formula, in <code>lib/mathjax/</code>.",
        "&copy; The MathJax Consortium",
        "Apache License 2.0 &mdash; " + licence_link("its text", "Apache-2.0")))
    out.append(work(
        "Italian hyphenation patterns",
        "<code>hyph-it.tex</code>, from the hyph-utf8 project: where the studio&rsquo;s "
        "PDFs may break an Italian word.",
        "&copy; 2008&ndash;2011 Claudio Beccari",
        "The LaTeX Project Public License 1.3 or later, or the MIT licence, whichever "
        "you choose (the file&rsquo;s own header says so, and carries the MIT text): "
        + licence_link("LPPL", "LPPL-1.3") + ", " + licence_link("MIT")))
    out.append(work(
        "Hazm's list of informal Persian words",
        "Pairs of a spoken Persian word and its formal word, from Hazm&rsquo;s <code>iwords.dat</code>, and the "
        "spoken stems of verbs, from its <code>iverbs.dat</code>, checked one by one and written in Parseh&rsquo;s own "
        "format in <code>lib/lang/fa.spoken.words.tsv</code> and <code>lib/lang/fa.spoken.verbs.tsv</code> "
        "(the rows whose last column says <code>hazm</code>): they let the dictionary panel read a spoken word "
        "back to the formal word it is. From <a href=\"https://github.com/roshan-research/hazm\" "
        "rel=\"noopener\" target=\"_blank\">github.com/roshan-research/hazm</a>.",
        "&copy; 2013 Alireza Nourian",
        "MIT licence &mdash; its text, with the copyright line, is <code>lib/lang/fa.spoken.HAZM-LICENSE.txt</code>, "
        "beside the table: " + licence_link("MIT")))
    out.append(work(
        "Excerpts in the tests' data",
        "In <code>tests/fixtures/</code>, beside the texts written for the tests: conjugation "
        "rows cut from Wiktionary, and sentences from Tatoeba with their machine translations. "
        "<code>tests/fixtures/README.md</code> says where every text there comes from.",
        "Wiktionary&rsquo;s contributors, Tatoeba&rsquo;s contributors",
        licence_link("CC BY-SA 4.0") + " (Wiktionary), " + licence_link("CC BY 2.0 FR")
        + " (Tatoeba)"))
    return "".join(out)


def speech_credits():
    """Whose work speech to text is: {"speech:runtime": (whose, the licences as
    HTML), "speech:<model>": ...} for the program and for each catalogue
    model.  Read from lib/getstt.py's constants, so the licence beside a part
    on its page is the one named on the Licences page.

    THE PROGRAM CARRIES SEVERAL LICENCES, and each is said with what carries
    it: faster-whisper, CTranslate2 and onnxruntime are MIT, PyAV is
    BSD-3-Clause, and the FFmpeg libraries inside PyAV's wheels report
    LGPL-3.0-or-later while the codec libraries beside them keep their own;
    the other packages of the list, and the Intel MKL and oneDNN in
    CTranslate2's Linux wheel, are said in one sentence (getstt.RUNTIME_REST).
    None of it is in Parseh's folder: a person's own press of a button fetches
    it from PyPI, under a hash Parseh ships."""
    import getstt
    also = ["%s (%s)" % (licence_link(lic), esc(what)) for what, lic in getstt.RUNTIME_LICENCES]
    licence = (licence_link(getstt.LICENCE) + ", " + (", ".join(also[:-1]) + " and " if len(also) > 1 else "")
               + also[-1] + "; the codecs inside those libraries keep their own; "
               + esc(getstt.RUNTIME_REST))
    out = {"speech:runtime": (esc(getstt.SOURCE), licence)}
    for model in getstt.MODELS:
        info = getstt.MODEL_INFO[model]
        source = info.get('source', getstt.MODEL_SOURCE)
        model_licence = info.get('licence', getstt.MODEL_LICENCE)
        package = getstt.MODEL_PINS.get(model, {})
        package_source = package.get('repo')
        package_licence = info.get('package_licence') or model_licence
        attribution = esc(source)
        if package_source and package_source != source:
            attribution += ' (CTranslate2 package: %s)' % esc(package_source)
        licence = licence_link(model_licence)
        if package_licence != model_licence:
            licence += ' (source); %s (CTranslate2 package)' % licence_link(package_licence)
        out["speech:" + model] = (attribution, licence)
    for code, pin in getstt.ALIGN_PINS.items():
        out["speech:align-" + code] = (
            esc("Parseh %s CTC alignment network" % code), licence_link(pin["licence"]))
    return out


def arasaac_credits():
    """Whose work the pictograms are: {"arasaac": (whose, the licence as HTML)}.  Read from
    lib/getarasaac.py's constants, so the credit beside the pictograms on their page, in the
    folder (LICENSE-ARASAAC.txt) and here is the same words.

    THE LICENCE IS SAID WITH ITS TERMS, because it is the one licence here that asks something
    of what a person makes with the files: a credit wherever they are used, nothing sold, and
    the same licence for what is shared."""
    import getarasaac
    return {"arasaac": (esc(getarasaac.CREDIT),
                        licence_link(getarasaac.LICENCE) + " &mdash; free for non-profit use, with a credit "
                        "wherever the pictograms are used, never for commercial use, and what is made with "
                        "them shared on the same licence; <a href=\"%s\" rel=\"noopener\" target=\"_blank\">"
                        "ARASAAC&rsquo;s terms of use</a>" % esc(getarasaac.TERMS))}


def credits():
    """Whose work each download of the reading help is, and under which
    licence: {what: (whose, the licence as HTML)} -- "dict", "corpus",
    "model", "engine", "synonyms", and "components:<pack>" for each component
    pack, and speech to text's parts (speech_credits).  Read from the
    downloaders themselves, and used twice: by this
    page, and on each row of the reading help (lib/lookuppage.py), so that
    the licence beside a download is the licence named here."""
    import getdict
    import getcorpus
    import getmt
    import getsyn
    import decomposition
    out = {"dict": (esc(getdict.SOURCE), licence_link(getdict.LICENCE)),
           "corpus": (esc(getcorpus.SOURCE), licence_link(getcorpus.LICENCE)),
           "model": (esc(getmt.MODEL_SOURCE), licence_link(getmt.MODEL_LICENCE)),
           "engine": ("bergamot-translator %s" % esc(getmt.ENGINE_VERSION),
                      licence_link(getmt.ENGINE_LICENCE)),
           "synonyms": (esc(getsyn.SOURCE), licence_link(getsyn.LICENCE, "WordNet"))}
    for key, pack in decomposition.PACKS.items():
        out["components:" + key] = (esc(pack["attribution"]), licence_link(pack["licence"]))
    out.update(speech_credits())
    out.update(arasaac_credits())
    return out


def fetched():
    """What the reading help downloads when somebody asks it to, each with the
    licence its downloader records in the file it builds."""
    import decomposition
    import getstt
    who = credits()
    out = [work("Dictionaries", "One per language, in <code>dict/</code>: what the words of "
                "a chunk nobody has glossed mean.", *who["dict"]),
           work("Sentences people have translated", "One file per pair of languages, in "
                "<code>corpus/</code>: a word shown in use.", *who["corpus"]),
           work("Translation models", "One per pair of languages, in <code>mt/</code>: what "
                "translates a chunk, inside the page.", *who["model"]),
           work("The translation engine", "In <code>mt/</code>: what runs the models, inside "
                "the page.", *who["engine"]),
           work("English synonyms", "One file in <code>mt/</code>: how a machine translation "
                "is matched word by word to the chunk it translates.", *who["synonyms"])]
    for key, pack in decomposition.PACKS.items():
        out.append(work(
            "Character components: " + pack["name"],
            "In <code>components/</code>: how a %s character is built from its parts." % " or ".join(
                {"ja": "Japanese", "zh": "Chinese"}.get(c, c) for c in pack["languages"]),
            *who["components:" + key]))
    out.append(work(
        "Speech to text: the program",
        "In <code>stt/runtime/</code>: what runs the speech models &mdash; faster-whisper, "
        "CTranslate2, PyAV and what they need &mdash; installed by pip from PyPI when you ask for "
        "it under <a href=\"/settings/speech/\">Speech to text</a>, in Settings. Every package "
        "is checked against a hash that travels with Parseh.", *who["speech:runtime"]))
    model_notices = ''.join('<dt>%s</dt><dd>%s &mdash; %s</dd>\n' %
                            (esc(getstt.MODEL_INFO[model]['label']), *who['speech:' + model])
                            for model in getstt.MODELS)
    out.append('<section class="work">\n<h3>Speech to text: the models</h3>\n'
               '<p class="what">In <code>stt/models/</code>: OpenAI Whisper large-v3-turbo '
               'and large-v3, and language-specific Whisper models, in CTranslate2&rsquo;s '
               'format. Available packages are fetched from Hugging Face at a fixed '
               'version when you ask for them under <a href="/settings/speech/">Speech '
               'to text</a>. Every file is checked against its own hash. Sources and '
               'converted packages keep their own licences, listed below.</p>\n'
               '<dl>%s</dl>\n</section>\n' % model_notices)
    out.append(work(
        "ARASAAC pictograms",
        "In <code>arasaac/</code>: some fourteen thousand pictograms and the words that name them in "
        "each language you ask for, fetched from <code>api.arasaac.org</code> and "
        "<code>static.arasaac.org</code> when you ask for them under "
        "<a href=\"/settings/arasaac/\">Pictograms (ARASAAC)</a>, in Settings. The credit "
        "ARASAAC asks for is written beside them, in <code>arasaac/LICENSE-ARASAAC.txt</code>.",
        *who["arasaac"]))
    return "".join(out)


def page():
    """/licences/, the whole page."""
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Licences &mdash; %(app)s</title>
%(apphead)s
<link rel="stylesheet" href="/lib/parseh.css">
<link rel="stylesheet" href="/lib/langs.css">
<link rel="stylesheet" href="/lib/mobile.css">
<script src="/lib/parseh.js"></script>
</head><body class="index" data-mobile-page>
<div class="parseh-bar" data-layout="browser">
  <a class="home" href="/"><span class="glyph" lang="fa">&#x67E;</span><span class="word">%(app)s</span></a>
  <span class="where">licences</span>
  <span class="sp"></span>
  %(modes)s
  <a class="parseh-btn" href="/guide/" title="the guide: how to use Parseh">guide</a>
  <button type="button" data-parseh-theme title="theme">&#9680;</button>
</div>
<div class="parseh-bar m-bar" data-layout="mobile">
  <a class="home" href="/"><span class="glyph" lang="fa">&#x67E;</span><span class="word">%(app)s</span></a>
  <span class="m-where">Licences</span>
  <span class="sp"></span>
  %(modes)s
  <button type="button" data-parseh-theme title="theme">&#9680;</button>
</div>
<main class="notices">
<h1 class="idx">licences</h1>
<p class="sub">What %(app)s is under, and the other people&rsquo;s work it carries and
fetches, under theirs.</p>

<h2>%(app)s</h2>
<p class="by">%(notice)s</p>
<p>%(app)s is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version
(<code>%(spdx)s</code>).</p>
<p>It is distributed in the hope that it will be useful, but <b>without any
warranty</b>; without even the implied warranty of merchantability or fitness for a
particular purpose. See the GNU General Public License for more details:
<a href="/licences/LICENSE">its text</a>, the file <code>LICENSE</code> at the top of
the %(app)s folder.</p>
<p>The source is that folder: this server runs from it, as it is.</p>

<h2>What it carries</h2>
<p class="intro">In the %(app)s folder, and not %(app)s&rsquo;s own work: each is under
its own licence, which travels with it.</p>
%(carried)s
<h2>What it fetches when you ask</h2>
<p class="intro">Not in the %(app)s folder: each is downloaded from its source when you
ask for it (<a href="/settings/reading-help/">reading help</a>, <a
href="/settings/speech/">speech to text</a> and <a
href="/settings/arasaac/">pictograms</a>, in Settings), and keeps its own
licence, which %(app)s writes into the file it builds from it. So do the programs the
installer fetches &mdash; micromamba, Python and the packages <code>environment.yml</code>
lists &mdash; each under the licence it comes with.</p>
%(fetched)s
<h2>What you read with it</h2>
<p>The books, videos, documents and decks are yours, or their authors&rsquo;:
%(app)s ships none of them, and its licence says nothing about them.</p>
</main>
</body></html>
""" % {"app": mobile.APP_NAME, "apphead": mobile.app_head(), "modes": mobile.mode_switch(),
       "spdx": LICENCE, "carried": carried(), "fetched": fetched(),
       # whose Parseh is: his name, and where to find him (lib/author.py)
       "notice": author.notice(mobile.APP_NAME)}


def licence_text():
    """The GPL's text, from the file at the top of the checkout."""
    with open(LICENCE_FILE, "rb") as f:
        return f.read()
