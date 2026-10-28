# SPDX-License-Identifier: GPL-3.0-or-later
"""The LaTeX themes, and the fence that asks for one (TO-DO §8.39, a0.4.0).

A LATEX BLOCK is a drawing made by TeX itself -- chemistry, TikZ, units --
where a `:::math` formula is drawn by MathJax on the screen and set by the
document's own TeX on paper.  It is written between a line `::::latex` and a
line `::::`:

    ::::latex chemistry {width=45 align=center caption="Water forms from hydrogen"}
    \\ce{2H2 + O2 -> 2H2O}
    ::::

FOUR COLONS, NOT THREE (the owner, 2026-09-25).  A block may sit in a jolly
card's field, and there a line of three colons ends the exercise (the reason a
`:::math` formula cannot sit on a card, a gap the owner chose to leave): a
line of four is never that line, so an exercise is read exactly as it always
was, and a block left unclosed takes the rest of its own field and no more.

THE WORD AFTER `latex` NAMES A THEME: one word, in any script -- letters,
digits, `-` and `_` -- told apart from the others ignoring case (the owner,
2026-09-25).  No word, the default theme.  The braces take a figure's own
layout words and mean what they mean for a figure (mdparser.IMAGE_RE): `width`
a percentage of the column, 5 to 100, `align` left, center or right, `offset`
a sideways shift -- with two defaults of the block's own, decided by the owner:
no width is the drawing's NATURAL size, as TeX set it and measured against
the text round it, and no align is CENTRED, as a formula is.  A block, not an
inline mark, may also take a `caption="…"` in double quotes, set under the
drawing as a figure's is.

A THEME is a named preamble, as many as wanted, kept in config/latex.json,
made and edited in Settings -> LaTeX drawings on the computer alone
(lib/settingspage.py, RUN): the packages commonly wanted as checkboxes
(Formulae's eight and its nineteen), a box for "text in the languages Parseh
teaches", a font of this computer's, a free preamble beneath, and the
compiler, which belongs to the theme (the owner, 2026-09-25).  A block is
compiled on its own, in its own `standalone` document with its theme's
preamble (lib/latexdraw.py): nothing here touches a `:::math` formula, on the
screen or on paper.

WHAT A THEME RESOLVES TO -- its preamble as it now is, and its compiler --
is what a drawing's key is made of (lib/latexdraw.py), never the theme's
name: renaming a theme redraws nothing, and editing one redraws exactly the
blocks that name it.

Standard library only: lib/offline.py and the studio's parser read the fence
from here, and neither may pull more than this in.
"""
import copy
import json
import os
import re
import threading
import time
import unicodedata

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
STORE = os.path.join(ROOT, "config", "latex.json")
# the shape of STORE, as a number (lib/version.py FORMATS): RAISE IT when the
# shape changes so that the Parseh before this one would read the file wrong
STORE_FORMAT = 1
# the stamp an exported theme carries, read back by its stamp (TRAVEL)
EXPORT_FORMAT = "parseh-latex-theme/1"

NAME = "Parseh"

# `standalone`'s crop margin, on every side, every theme (preamble, below).
# An inline drawing's depth (lib/latexdraw.py) is measured from a probe
# compile that has none of it, then this same constant is added back, since
# the border sits below the ink as much as above it.
BORDER_PT = 2.0

# ------------------------------------------------------------------ the fence
FENCE_OPEN_RE = re.compile(r"^::::latex\b(.*)$", re.I)
FENCE_CLOSE = "::::"
# a drawing inside a step of a follow-up (mdparser.py) is one colon more, the dialect's one rule for a block inside a
# block: `:::::latex` … `:::::`; the light scans below take a fence of four colons or more and close it with its own
_DEEPER_OPEN_RE = re.compile(r"^(:{4,})latex\b", re.I)
_OPENING_RE = re.compile(r'^\s*([^\s{}]+)?\s*(?:\{((?:"[^"]*"|[^{}"])*)\})?\s*$')
NAME_MAX = 40


def name_ok(name):
    """Is `name` one word a theme may be called: letters of any script (their
    marks included, which Hindi's vowels are), digits, `-` and `_`?"""
    if not isinstance(name, str) or not name or len(name) > NAME_MAX:
        return False
    for ch in name:
        if ch in "-_":
            continue
        if unicodedata.category(ch)[0] not in "LMN":
            return False
    return True


def name_key(name):
    """The form two names are compared in: ignoring case, and the ways one
    letter can be spelt in Unicode."""
    return unicodedata.normalize("NFC", str(name or "")).casefold()


NAME_RULE = ("a theme's name is one word: letters of any script, digits, "
             "'-' and '_', at most %d of them" % NAME_MAX)


def opening(line):
    """A line (stripped) that opens a latex block -> {"theme", "attrs",
    "errors"}; None when it opens none."""
    m = FENCE_OPEN_RE.match(line)
    if not m:
        return None
    rest = m.group(1)
    out = {"theme": "", "attrs": "", "errors": []}
    mm = _OPENING_RE.match(rest)
    if not mm:
        out["errors"].append("the opening line reads ::::latex, a theme's name if "
                             "any, and the layout in braces: "
                             "::::latex chemistry {width=45 align=center}")
        return out
    name, attrs = mm.group(1) or "", mm.group(2) or ""
    if re.search(r'\bcaption\s*=\s*(?!")', re.sub(r'"[^"]*"', '""', attrs)):
        out["errors"].append('a caption goes in double quotes: caption="Water forms from '
                             'hydrogen and oxygen"')
    if name and not name_ok(name):
        out["errors"].append("%r is not a theme's name: %s" % (name, NAME_RULE))
    out["theme"], out["attrs"] = name, attrs
    return out


def parse_attrs(raw, card=False):
    """`width=45 align=center offset=-10 caption="Water"` -> {"width": 45 or
    None, "align", "offset", "caption"}.  The words and their ranges are a
    figure's (mdparser.parse_image_attrs); the defaults are the block's own: no
    width is its natural size, no align is centred, no caption is none.  On a
    card there is no offset, as an exercise's picture has none.  A caption is
    inline markup in double quotes, with no escapes, on the one line: a
    figure's own (`![caption](path)`).  It is never part of the drawing's key
    (lib/latexdraw.py): a caption edited draws nothing again."""
    out = {"width": None, "align": "center", "offset": 0, "caption": ""}
    for m in re.finditer(r'([a-z]+)\s*=\s*(?:"([^"]*)"|(-?[\w.:]+))', raw or ""):
        k, v = m.group(1), m.group(3)
        if k == "caption":
            if m.group(2) is not None:
                out["caption"] = re.sub(r"\s+", " ", m.group(2)).strip()
        elif v is None:
            continue
        elif k in ("width", "offset"):
            try:
                n = int(round(float(v)))
            except ValueError:
                continue
            if k == "width":
                out["width"] = max(5, min(100, n))
            elif not card:
                out["offset"] = max(-100, min(100, n))
        elif k == "align" and v in ("left", "center", "right"):
            out["align"] = v
    return out


def _unquote(line):
    """A line of a box (`> > text`) -> (the `>`s and their spaces, the text)."""
    m = re.match(r"^(\s*(?:>\s?)*)(.*)$", line)
    return m.group(1), m.group(2)


def blocks_in(markdown):
    """Every latex block the text holds, in order: [{"theme", "attrs",
    "tex", "line", "closed"}].  A light reading of the fence alone, for what
    may not import the studio's parser (lib/offline.py, a rename): a block
    in a box, one indented in a card's field and one in a step of a follow-up
    (a fence of five colons) are found as mdparser finds them."""
    out = []
    lines = (markdown or "").replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        quote, text = _unquote(lines[i])
        head = text.strip()
        deeper = _DEEPER_OPEN_RE.match(head)
        depth = len(deeper.group(1)) if deeper else len(FENCE_CLOSE)
        op = opening(head[depth - len(FENCE_CLOSE):])
        if op is None:
            i += 1
            continue
        start, body = i, []
        i += 1
        closed = False
        while i < len(lines):
            q2, t2 = _unquote(lines[i])
            if t2.strip() == ":" * depth:
                closed = True
                i += 1
                break
            body.append(t2)
            i += 1
        out.append({"theme": op["theme"], "attrs": op["attrs"], "errors": op["errors"],
                    "tex": dedent_body(body), "line": start, "closed": closed})
    return out


# INLINE LATEX (TO-DO §8.39's L8): `[\ce{H2O}]{latex}`, or with its own
# theme after the word -- `[\ce{H2O}]{latex chemistry}`, the owner's own
# choice, 2026-09-27, the same way a `::::latex chemistry` block names one.
# The body is raw LaTeX in text mode exactly as a block's is (so his own
# examples write `$…$` INSIDE the brackets for a formula).  This lives here,
# beside `blocks_in`, for the same reason that does (lib/offline.py's own
# light reading, no studio parser needed) -- markdown/exlex/texgen.py and
# markdown/app/htmlgen.py both import it from here, unchanged, for their own
# full parsing; everything MATH_RE (texgen.py) works through to allow a
# bracket the body opens and closes itself is copied unchanged, the same
# reasons -- `\sqrt[3]{x}`, `[0,1)` -- being exactly as true of arbitrary
# LaTeX as they are of a formula.
_LATEX_END = r"\]\{\s*latex(?:\s+([^\s{}]+))?\s*\}"
_LATEX_GROUP = r"\[[^\[\]]*\]"
_LATEX_GROUP = r"\[(?:[^\[\]]|%s)*\]" % _LATEX_GROUP
_LATEX_GROUP = r"\[(?:[^\[\]]|%s)*\]" % _LATEX_GROUP
_LATEX_GROUP += r"(?!\{\s*latex\b)"
_LATEX_SLOT = r"\[\[[^\[\]]+\]\](?!\{\s*latex\b)"
LATEX_INLINE_RE = re.compile(
    r"(?!%s)\[((?:[^\[\]]|%s|(?!%s)\[|\](?![{(\]])|\](?=%s))+?)%s"
    % (_LATEX_SLOT, _LATEX_GROUP, _LATEX_GROUP, _LATEX_END, _LATEX_END))


# A list item's own bracket -- a checkbox, "- [x] ", or a blank's name,
# "- [blank1] " -- is not the start of a mark, but the body rule above (a "]"
# may stand inside one, as in "[0,1)") would read "- [x] [a]{latex}" as the
# body "x] [a".  The raw source is swept with those brackets blanked, kept as
# long, so that an option's mark is the one the page draws.
_ITEM_BRACKET = re.compile(r"(?m)^([ \t>]*(?:[-*+]|\d+[.)])[ \t]+)\[([^\[\]\n]*)\](?=[ \t])")


def _items_unmarked(source):
    return _ITEM_BRACKET.sub(lambda m: m.group(1) + " " * (len(m.group(2)) + 2), source)


def inline_latex_pairs(source):
    """Every distinct (tex, theme name or None) an inline `[…]{latex …}`
    mark names in `source` (the WHOLE raw markdown, frontmatter and all --
    an inline mark can sit in any text field), first-seen order, deduplicated
    the way `htmlgen.latex_pairs` deduplicates a page's blocks: drawn side by
    side before the page or the paper that shows it, the same reason a
    block's own pre-compile exists (a screen calls `draw_all` on the result;
    a paper document compiles each in turn, as it already does for blocks)."""
    seen, out = set(), []
    for m in LATEX_INLINE_RE.finditer(_items_unmarked(source)):
        pair = (m.group(1), m.group(3) or None)
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    return out


def dedent_body(lines):
    """A block's body as its lines were written, less the indentation they all
    share (a block in a card's `key: |` field is indented with the field)."""
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    pad = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    cut = min(pad) if pad else 0
    return "\n".join(l[cut:] if len(l) >= cut else l.lstrip() for l in lines)


def rename_in_text(text, old, new):
    """`text` with every latex block that names the theme `old` (ignoring
    case) naming `new` instead -> (text, how many).  Only the name on the
    opening line changes: the layout, the body, the indentation and a box's
    `>`s stay as written."""
    if "::::" not in (text or ""):
        return text, 0
    want = name_key(old)
    lines = text.split("\n")
    n = 0
    for i, line in enumerate(lines):
        quote, rest = _unquote(line)
        lead = rest[:len(rest) - len(rest.lstrip())]
        deeper = _DEEPER_OPEN_RE.match(rest.strip())
        op = opening(rest.strip()[(len(deeper.group(1)) - len(FENCE_CLOSE)) if deeper else 0:])
        if not op or not op["theme"] or name_key(op["theme"]) != want:
            continue
        m = re.match(r"^(:{4,}latex)(\s+)(\S+?)(\s*\{.*)?(\s*)$", rest.strip(), re.I)
        if not m:
            continue
        lines[i] = quote + lead + m.group(1) + m.group(2) + new + (m.group(4) or "") + (m.group(5) or "")
        n += 1
    return "\n".join(lines), n


# ------------------------------------------------------------ the catalogue
# Every checkbox a theme has: Formulae's eight (its fixed head) and its
# nineteen (its preamble tab), each with a line and an example, as Formulae
# shows them, and what TeX Live calls the packages it needs (`tl`) and the
# licence the TeX Catalogue gives them (read from CTAN, 2026-09-25), which
# the row of a package this Parseh installs shows, and /licences/.
CATALOGUE = (
    # group, id, shown as, what it is for, an example, the preamble, TeX Live
    # packages, a file whose presence says it is installed, licence
    ("base", "amsmath", "amsmath", "Displayed equations, matrices and the rest of "
     "the AMS's mathematics.", r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
     r"\usepackage{amsmath}", ("amsmath",), "amsmath.sty", "lppl1.3c"),
    ("base", "amssymb", "amssymb", "The AMS symbols.", r"\mathbb{R} \leqslant \varnothing",
     r"\usepackage{amssymb}", ("amsfonts",), "amssymb.sty", "ofl"),
    ("base", "amsfonts", "amsfonts", "The AMS fonts: blackboard and Fraktur letters.",
     r"\mathfrak{g}", r"\usepackage{amsfonts}", ("amsfonts",), "amsfonts.sty", "ofl"),
    ("base", "mathtools", "mathtools", "amsmath mended and extended.",
     r"\coloneqq", r"\usepackage{mathtools}", ("mathtools",), "mathtools.sty", "lppl1.3c"),
    ("base", "bm", "bm", "Bold symbols in mathematics.", r"\bm{\alpha}",
     r"\usepackage{bm}", ("tools",), "bm.sty", "lppl1.3c"),
    ("base", "xcolor", "xcolor", "Colours.", r"\textcolor{teal}{x}",
     r"\usepackage{xcolor}", ("xcolor",), "xcolor.sty", "lppl1.3c"),
    ("base", "siunitx", "siunitx", "Numbers with units, set as units are set.",
     r"\qty{9.81}{\metre\per\second\squared}", r"\usepackage{siunitx}", ("siunitx",),
     "siunitx.sty", "lppl1.3c"),
    ("base", "physics", "physics", "The physicist's shorthands. (It redefines "
     r"\div and a few more.)", r"\dv{f}{x}, \abs{x}, \bra{\psi}",
     r"\usepackage{physics}", ("physics",), "physics.sty", "lppl"),
    ("letters", "mathrsfs", "mathrsfs", "Script letters.", r"\mathscr{L}",
     r"\usepackage{mathrsfs}", ("jknapltx", "rsfs"), "mathrsfs.sty", "gpl"),
    ("letters", "dsfont", "dsfont", "Double-stroke letters.", r"\mathds{R}",
     r"\usepackage{dsfont}", ("doublestroke",), "dsfont.sty", "other-free"),
    ("letters", "esvect", "esvect", "Better-looking vectors.", r"\vv{AB}",
     r"\usepackage{esvect}", ("esvect",), "esvect.sty", "gpl"),
    ("letters", "stmaryrd", "stmaryrd", "Special symbols of mathematics.",
     r"\llbracket x \rrbracket", r"\usepackage{stmaryrd}", ("stmaryrd",), "stmaryrd.sty",
     "lppl"),
    ("letters", "wasysym", "wasysym", "Extra symbols: astronomical signs and more.",
     r"\male\ \female\ \smiley", r"\usepackage{wasysym}", ("wasysym",), "wasysym.sty",
     "lppl1.3c"),
    ("letters", "marvosym", "marvosym", "Currency and technical symbols.", r"\Yen\ \Mundus",
     r"\usepackage{marvosym}", ("marvosym",), "marvosym.sty", "ofl"),
    ("operations", "cancel", "cancel", "Strike through in mathematics.",
     r"\cancelto{0}{x}", r"\usepackage{cancel}", ("cancel",), "cancel.sty", "pd"),
    ("operations", "slashed", "slashed", "Feynman's slash.", r"\slashed{p}",
     r"\usepackage{slashed}", ("carlisle",), "slashed.sty", "lppl"),
    ("operations", "relsize", "relsize", "Mathematics set a size larger or smaller.",
     r"\mathlarger{\sum}", r"\usepackage{relsize}", ("relsize",), "relsize.sty", "pd"),
    ("operations", "amsthm", "amsthm", "Theorems, with \\newtheorem.",
     r"\begin{proof} ... \end{proof}", r"\usepackage{amsthm}", ("amscls",), "amsthm.sty",
     "lppl1.3c"),
    ("drawings", "tikz", "tikz", "Drawing. Loads the libraries arrows.meta, "
     "positioning, shapes and calc.", r"\begin{tikzpicture}\draw (0,0) -- (2,1);\end{tikzpicture}",
     "\\usepackage{tikz}\n\\usetikzlibrary{arrows.meta,positioning,shapes,calc}", ("pgf",),
     "tikz.sty", "fdl,lppl1.3c,gpl2"),
    ("drawings", "tikz-cd", "tikz-cd", "Commutative diagrams.",
     r"\begin{tikzcd} A \arrow{r}{f} & B \end{tikzcd}",
     "\\usepackage{tikz}\n\\usepackage{tikz-cd}", ("pgf", "tikz-cd"), "tikz-cd.sty", "lppl1.3"),
    ("drawings", "bayesnet", "bayesnet", "Bayesian networks: the nodes latent, obs, "
     r"det and factor, \edge and \plate.", r"\node[latent] (x) {$x$};",
     "\\usepackage{tikz}\n\\usetikzlibrary{bayesnet}", ("pgf", "tikz-bayesnet"),
     "tikzlibrarybayesnet.code.tex", "lppl1.3"),
    ("drawings", "pgfplots", "pgfplots", "Plots and surfaces, inside an axis.",
     r"\begin{tikzpicture}\begin{axis}\addplot{x^2};\end{axis}\end{tikzpicture}",
     "\\usepackage{pgfplots}\n\\pgfplotsset{compat=newest}", ("pgfplots",), "pgfplots.sty",
     "gpl3+"),
    ("drawings", "circuitikz", "circuitikz", "Electrical circuits.",
     r"\begin{circuitikz}\draw (0,0) to[R] (2,0);\end{circuitikz}",
     r"\usepackage{circuitikz}", ("circuitikz",), "circuitikz.sty", "gpl,lppl"),
    ("chemistry", "mhchem", "mhchem", "Chemical formulas and reactions.",
     r"\ce{Mg + 2 HCl -> MgCl2 + H2 ^}", r"\usepackage[version=4]{mhchem}",
     ("mhchem", "chemgreek"), "mhchem.sty", "lppl1.3c"),
    ("chemistry", "chemfig", "chemfig", "Structures of molecules.", r"\chemfig{H-O-H}",
     r"\usepackage{chemfig}", ("chemfig",), "chemfig.sty", "lppl1.3c"),
    ("code", "listings", "listings", "Code, set as code.",
     r"\begin{lstlisting}[language=Python] ... \end{lstlisting}",
     r"\usepackage{listings}", ("listings",), "listings.sty", "lppl1.3c"),
    ("code", "algorithm2e", "algorithm2e", "Pseudocode. Write [H] after "
     r"\begin{algorithm}: a drawing has no page to float to.",
     r"\begin{algorithm}[H] ... \end{algorithm}",
     "\\usepackage{float}\n\\usepackage[ruled,vlined]{algorithm2e}",
     ("float", "algorithm2e", "ifoddpage", "relsize"), "algorithm2e.sty", "lppl"),
    # For someone teaching or learning a language rather than mathematics
    # (TO-DO §8.39's L10, researched and each one really compiled, 2026-09-25):
    ("linguistics", "forest", "forest", "Syntax trees, node by node.",
     r"[S [NP [Det][N]] [VP [V][NP]]]", r"\usepackage{forest}", ("forest",),
     "forest.sty", "lppl1.3"),
    ("linguistics", "tikz-dependency", "tikz-dependency", "Dependency arcs between words.",
     r"\begin{dependency}\begin{deptext}Cats \& sleep \\ \end{deptext}\depedge{2}{1}{subj}\end{dependency}",
     "\\usepackage{tikz}\n\\usepackage{tikz-dependency}", ("pgf", "tikz-dependency"),
     "tikz-dependency.sty", "lppl1.3c,gpl2"),
    ("phonetics", "tipa", "tipa", "The International Phonetic Alphabet.",
     '[\\textipa{s\\ae"læm}]', r"\usepackage{tipa}", ("tipa",), "tipa.sty", "lppl"),
    ("scripts", "xpinyin", "xpinyin", "Pinyin written automatically over Chinese characters.",
     r"\pinyin{你好}", "\\usepackage{xeCJK}\n\\usepackage{xpinyin}", ("xecjk", "xpinyin"),
     "xpinyin.sty", "lppl1.3c"),
    # A game's moves and its board (the owner's own report, 2026-10-25, a0.5.4).  ONE ROW FOR THE WHOLE SET, because
    # TeX Live does not say what these packages lean on besides themselves: its xskak, skak, chessboard and
    # chessfss declare no dependency, and a drawing needs the chess fonts (skaknew), the lists lambda.sty makes
    # (lambda-lists), the conditionals (xifthen, ifmtarg) and the node macros (pst-node, pstricks) as well --
    # found by drawing the sample from nothing, one missing file at a time.
    ("games", "xskak", "xskak", "Chess: the moves of a game in figurine notation, and the board after them.",
     r"\newchessgame\mainline{1.e4 e5 2.Nf3 Nc6}\chessboard[hideblack]", r"\usepackage{xskak}",
     ("xskak", "skak", "chessfss", "chessboard", "skaknew", "lambda-lists", "xifthen", "ifmtarg",
      "pst-node", "pstricks"), "xskak.sty", "lppl1"),
)
# The first line is the group heading a person sees in Settings.  The optional
# third value is its plain-language explanation there; it is deliberately
# independent of the application this catalogue originally came from.
GROUPS = (("base", "Base packages", "The basics every drawing uses: mathematics, colour, units and scientific notation. "
                                    "They come with this computer's TeX: Parseh neither gets nor removes them."),
          ("letters", "Letters and symbols"),
          ("operations", "Operations and theorems"), ("drawings", "Drawings and plots"),
          ("chemistry", "Chemistry"), ("code", "Code and algorithms"),
          ("linguistics", "Linguistics", "Trees and diagrams for syntax and grammar."),
          ("phonetics", "Phonetics"),
          ("scripts", "Scripts and annotation", "Help with a non-Latin script beyond Parseh's own faces."),
          ("games", "Games", "Boards and notation, with the fonts they need."))
PACKAGES = {row[1]: {"group": row[0], "id": row[1], "name": row[2], "what": row[3],
                     "example": row[4], "code": row[5], "tl": row[6], "file": row[7],
                     "licence": row[8]} for row in CATALOGUE}
ORDER = [row[1] for row in CATALOGUE]
BASE = tuple(row[1] for row in CATALOGUE if row[0] == "base")
# a package a preamble may load by name that is part of another row's set: loading it asks for that row's packages
ALSO_LOADS = {"skak": "xskak", "chessboard": "xskak", "chessfss": "xskak"}
# what every drawing needs whatever its theme: the class that crops a page to
# its ink, and what a font or the languages' faces need
ALWAYS = {"standalone": (("standalone",), "standalone.cls", "lppl1.3"),
          "fontspec": (("fontspec",), "fontspec.sty", "lppl1.3c"),
          "unicode-math": (("unicode-math", "lm-math"), "unicode-math.sty", "lppl1.3c")}

COMPILERS = ("xelatex", "pdflatex", "lualatex")
DEFAULT_COMPILER = "xelatex"      # the owner, 2026-09-25: the studio's PDFs need it
UNICODE = ("xelatex", "lualatex")
TIMEOUT_DEFAULT = 30              # seconds; the owner: editable in Settings
TIMEOUT_MIN, TIMEOUT_MAX = 5, 600
PREAMBLE_MAX = 20000
DEFAULT = "default"


def _theme(name, packages, compiler=DEFAULT_COMPILER, languages=False, font="",
           preamble="", at=""):
    return {"name": name, "compiler": compiler,
            "packages": [p for p in ORDER if p in packages],
            "languages": bool(languages), "font": font, "preamble": preamble,
            "created": at, "updated": at}


# the three a fresh Parseh has (the owner, 2026-09-25): the default --
# Formulae's eight -- which may be edited and never deleted, and two to start
# from, one for each reason the second environment exists
STARTERS = (
    _theme("default", BASE),
    _theme("chemistry", BASE + ("mhchem", "chemfig")),
    _theme("drawing", BASE + ("tikz", "pgfplots")),
)


class ThemeError(Exception):
    """A theme refused, in words for the person who asked."""


# ------------------------------------------------------------------ the store
_LOCK = threading.RLock()


def _fresh():
    return {"format": STORE_FORMAT, "themes": [copy.deepcopy(t) for t in STARTERS],
            "default": DEFAULT, "timeout": TIMEOUT_DEFAULT}


def _read():
    try:
        with open(STORE, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return _fresh()
    if not isinstance(doc, dict) or not isinstance(doc.get("themes"), list):
        return _fresh()
    good, seen = [], set()
    for t in doc["themes"]:
        try:
            t = clean(t)
        except ThemeError:
            continue
        if name_key(t["name"]) in seen:
            continue
        seen.add(name_key(t["name"]))
        good.append(t)
    if name_key(DEFAULT) not in seen:
        good.insert(0, copy.deepcopy(STARTERS[0]))
    doc["themes"] = good
    names = {name_key(t["name"]): t["name"] for t in good}
    doc["default"] = names.get(name_key(doc.get("default") or ""), DEFAULT)
    try:
        doc["timeout"] = max(TIMEOUT_MIN, min(TIMEOUT_MAX, int(doc.get("timeout"))))
    except (TypeError, ValueError):
        doc["timeout"] = TIMEOUT_DEFAULT
    return doc


def _write(doc):
    """Written whole, through a temporary file beside it (lib/prefs.py's
    way): a reader gets the old file or the new one, never half of either."""
    doc = dict(doc, format=STORE_FORMAT)
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, STORE)
    return doc


def all_of():
    """{"themes": [...], "default": name, "timeout": seconds}, as they stand."""
    with _LOCK:
        return _read()


def themes():
    return all_of()["themes"]


def default_name():
    return all_of()["default"]


def timeout():
    return all_of()["timeout"]


def find(name):
    """The theme called `name` (ignoring case), or None; no name, the default."""
    doc = all_of()
    want = name_key(name or doc["default"])
    for t in doc["themes"]:
        if name_key(t["name"]) == want:
            return t
    return None


def clean(t, name=None):
    """A theme as it may be kept -> the theme, every field checked; ThemeError
    in words for anything a theme may not be."""
    if not isinstance(t, dict):
        raise ThemeError("a theme is a set of named settings")
    name = t.get("name") if name is None else name
    if not name_ok(name):
        raise ThemeError("%r cannot be a theme's name: %s" % (name, NAME_RULE))
    compiler = t.get("compiler") or DEFAULT_COMPILER
    if compiler not in COMPILERS:
        raise ThemeError("%r is not a compiler Parseh offers (%s)" % (compiler, ", ".join(COMPILERS)))
    packages = t.get("packages") or []
    if not isinstance(packages, list) or any(p not in PACKAGES for p in packages):
        unknown = [p for p in (packages if isinstance(packages, list) else []) if p not in PACKAGES]
        raise ThemeError("a theme's packages are the ones Settings lists; %s is not one of them"
                         % (", ".join(map(str, unknown)) or "that"))
    font = t.get("font") or ""
    if not isinstance(font, str) or len(font) > 120 or re.search(r"[\\{}%\n]", font):
        raise ThemeError("a font is named by its family, as this computer lists it")
    if font and compiler not in UNICODE:
        raise ThemeError("a font of this computer needs xelatex or lualatex, and this theme "
                         "compiles with %s" % compiler)
    languages = bool(t.get("languages"))
    if languages and compiler not in UNICODE:
        raise ThemeError("text in the languages Parseh teaches needs xelatex or lualatex, "
                         "and this theme compiles with %s" % compiler)
    preamble = t.get("preamble") or ""
    if not isinstance(preamble, str) or len(preamble) > PREAMBLE_MAX:
        raise ThemeError("a free preamble is text, at most %d characters" % PREAMBLE_MAX)
    if re.search(r"\\begin\s*\{\s*document\s*\}", preamble):
        raise ThemeError("a preamble ends where the drawing begins: it may not hold "
                         "\\begin{document}")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    return {"name": name, "compiler": compiler, "packages": [p for p in ORDER if p in packages],
            "languages": languages, "font": font, "preamble": preamble.replace("\r\n", "\n"),
            "created": str(t.get("created") or now), "updated": str(t.get("updated") or now)}


def save(theme, was=None):
    """Make a theme, or change the one called `was` (not its name: renaming is
    rename(), which puts every block right) -> the theme kept."""
    with _LOCK:
        doc = _read()
        t = clean(theme)
        at = None
        for i, old in enumerate(doc["themes"]):
            if name_key(old["name"]) == name_key(was or ""):
                at = i
            elif name_key(old["name"]) == name_key(t["name"]):
                raise ThemeError("there is a theme called %s already" % old["name"])
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        if was is not None and at is None:
            raise ThemeError("there is no theme called %s" % was)
        if at is not None:
            if name_key(doc["themes"][at]["name"]) != name_key(t["name"]):
                raise ThemeError("a theme is renamed with Rename, which puts every "
                                 "block that names it right")
            t["created"] = doc["themes"][at].get("created") or now
            t["updated"] = now
            t["name"] = doc["themes"][at]["name"]
            doc["themes"][at] = t
        else:
            t["created"] = t["updated"] = now
            doc["themes"].append(t)
        _write(doc)
        return t


def delete(name):
    with _LOCK:
        doc = _read()
        if name_key(name) == name_key(DEFAULT):
            raise ThemeError("the theme called default is kept: it is what a block that "
                             "names no theme is drawn with. Change it instead")
        keep = [t for t in doc["themes"] if name_key(t["name"]) != name_key(name)]
        if len(keep) == len(doc["themes"]):
            raise ThemeError("there is no theme called %s" % name)
        doc["themes"] = keep
        if name_key(doc["default"]) == name_key(name):
            doc["default"] = DEFAULT
        _write(doc)


def set_default(name):
    with _LOCK:
        doc = _read()
        t = next((t for t in doc["themes"] if name_key(t["name"]) == name_key(name)), None)
        if t is None:
            raise ThemeError("there is no theme called %s" % name)
        doc["default"] = t["name"]
        _write(doc)


def set_timeout(seconds):
    try:
        n = int(seconds)
    except (TypeError, ValueError):
        raise ThemeError("how long a drawing may take is a number of seconds")
    if not TIMEOUT_MIN <= n <= TIMEOUT_MAX:
        raise ThemeError("a drawing may take from %d to %d seconds" % (TIMEOUT_MIN, TIMEOUT_MAX))
    with _LOCK:
        doc = _read()
        doc["timeout"] = n
        _write(doc)


def rename_store(old, new):
    """The theme `old` called `new` in the store -- the last step of a rename
    (lib/latexrename.py), the blocks put right before it."""
    with _LOCK:
        doc = _read()
        if not name_ok(new):
            raise ThemeError("%r cannot be a theme's name: %s" % (new, NAME_RULE))
        hit = None
        for t in doc["themes"]:
            if name_key(t["name"]) == name_key(new) and name_key(new) != name_key(old):
                raise ThemeError("there is a theme called %s already" % t["name"])
            if name_key(t["name"]) == name_key(old):
                hit = t
        if hit is None:
            raise ThemeError("there is no theme called %s" % old)
        if name_key(old) == name_key(DEFAULT) and name_key(new) != name_key(DEFAULT):
            raise ThemeError("the theme called default keeps its name: a block that names "
                             "no theme is drawn with it")
        hit["name"] = new
        hit["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if name_key(doc["default"]) == name_key(old):
            doc["default"] = new
        _write(doc)
        return hit


# ------------------------------------------------------ export and import
def export_bytes(name):
    t = find(name)
    if t is None:
        raise ThemeError("there is no theme called %s" % name)
    out = {"format": EXPORT_FORMAT, "software": NAME,
           "theme": {k: t[k] for k in ("name", "compiler", "packages", "languages", "font",
                                        "preamble")}}
    return (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def read_export(data):
    """An exported theme's bytes -> the theme it holds, checked, and its whole
    preamble as it would be compiled (preamble()), to be shown before the
    import completes (the owner, 2026-09-24); ThemeError otherwise."""
    try:
        doc = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
    except (ValueError, UnicodeDecodeError):
        raise ThemeError("that file is not a theme exported by Parseh")
    if not isinstance(doc, dict) or doc.get("format") != EXPORT_FORMAT:
        raise ThemeError("that file is not a theme this Parseh reads (it wants %s)"
                         % EXPORT_FORMAT)
    t = clean(doc.get("theme"))
    return t


def import_theme(theme, name):
    """A theme read from a file, kept under `name` -- a name already taken is
    refused (the owner, 2026-09-25: a new name, and nothing else)."""
    t = dict(theme, name=name, created="", updated="")
    return save(t)


# ------------------------------------------------------------ what it resolves to
def _languages_tex(compiler, fonts_dir):
    """The faces of every language Parseh teaches, each a command of its own,
    \\textfa{...}, \\textja{...}: fontspec, the faces Parseh carries (copied
    beside the drawing by lib/latexdraw.py into ./fonts/), and for a
    right-to-left script its direction."""
    import languages
    out = ["% the languages Parseh teaches, each in its own face: \\text<code>{...}",
           "\\usepackage{fontspec}"]
    if compiler == "xelatex":
        out.append("\\TeXXeTstate=1")
    for L in languages.LANGS.values():
        tex = L.tex or {}
        family = tex.get("main")
        if not family:
            continue
        code = re.sub(r"[^A-Za-z]", "", L.code)
        if not code:
            continue
        opts = []
        if tex.get("script"):
            opts.append("Script=%s" % tex["script"])
        stem = family.replace(" ", "")
        local = None
        for reg in (stem + "-Regular.ttf", stem + ".ttf"):
            if os.path.exists(os.path.join(fonts_dir, reg)):
                local = reg
        if local:
            decl = "\\newfontfamily\\parseh%sface[Path=./fonts/,%s]{%s}" % (
                code, ",".join(opts + ["UprightFont=%s" % local]), stem)
        else:
            decl = "\\newfontfamily\\parseh%sface[%s]{%s}" % (code, ",".join(opts), family)
        out.append("\\IfFontExistsTF{%s}{%s}{\\let\\parseh%sface\\relax}"
                   % ("[./fonts/%s]" % local if local else family, decl, code))
        if L.rtl:
            wrap = ("{\\parseh%sface\\beginR #1\\endR}" if compiler == "xelatex"
                    else "{\\parseh%sface\\textdir TRT #1}") % code
        else:
            wrap = "{\\parseh%sface #1}" % code
        out.append("\\providecommand\\text%s[1]%s" % (code, wrap))
    return "\n".join(out)


def preamble(theme, fonts_dir=os.path.join(ROOT, "lib", "fonts")):
    """The whole preamble a block of `theme` is compiled under, from the
    class to the last line before \\begin{document} -- what the import shows,
    and what a drawing's key is made of."""
    t = theme
    out = ["\\documentclass[border=%gpt]{standalone}" % BORDER_PT]
    rows = [PACKAGES[p] for p in ORDER if p in t.get("packages", ())]
    out += [r["code"] for r in rows if r["group"] == "base"]
    if t.get("font") and t.get("compiler") in UNICODE:
        # Formulae's way: the face as the sans family and the sans family the
        # default, so \rm -- which operator names are set in -- stays Latin
        # Modern; unicode-math with Latin Modern's own mathematics
        out += ["\\usepackage{fontspec}",
                "\\setsansfont{%s}" % t["font"],
                "\\renewcommand{\\familydefault}{\\sfdefault}",
                "\\usepackage{unicode-math}",
                "\\setmathfont{latinmodern-math.otf}"]
    out += [r["code"] for r in rows if r["group"] != "base"]
    if t.get("languages") and t.get("compiler") in UNICODE:
        out.append(_languages_tex(t["compiler"], fonts_dir))
    if (t.get("preamble") or "").strip():
        out.append(t["preamble"].strip())
    return "\n".join(out) + "\n"


def resolve(name):
    """The theme a block names, as it would be drawn -> {"name", "compiler",
    "preamble", "theme"}, or None when this Parseh has no theme of that name."""
    t = find(name)
    if t is None:
        return None
    return {"name": t["name"], "compiler": t["compiler"], "preamble": preamble(t),
            "languages": t.get("languages"), "theme": t}


_USES = re.compile(r"\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")


def uses(theme):
    """The catalogue's packages a theme uses, in the catalogue's order: those
    it ticks, and those its own preamble loads by name."""
    ids = [p for p in ORDER if p in theme.get("packages", ())]
    by_name = dict(ALSO_LOADS)
    for p in ORDER:
        by_name.setdefault(p, p)
        by_name.setdefault(PACKAGES[p]["file"].rsplit(".", 1)[0], p)
    for m in _USES.finditer(theme.get("preamble") or ""):
        for name in m.group(1).split(","):
            p = by_name.get(name.strip())
            if p and p not in ids:
                ids.append(p)
    return sorted(ids, key=ORDER.index)


def other_packages(theme):
    """The packages a theme's own preamble loads by name that the catalogue has no row for, in the order it loads them:
    what a person said of the theme in its free lines, which `uses` cannot name."""
    known = set(PACKAGES) | set(ALSO_LOADS) | {PACKAGES[p]["file"].rsplit(".", 1)[0] for p in ORDER}
    out = []
    for m in _USES.finditer(theme.get("preamble") or ""):
        for name in m.group(1).split(","):
            name = name.strip()
            if name and name not in known and name not in out:
                out.append(name)
    return out


def own_packages(theme):
    """The packages a theme uses beyond the base.  They are Parseh's own (the
    owner, 2026-09-28): drawn only once Parseh has got them into its texmf/,
    even where the computer's TeX has them too; the base, and what every
    drawing loads (ALWAYS), come with the computer's TeX."""
    return [p for p in uses(theme) if PACKAGES[p]["group"] != "base"]


def files_needed(theme):
    """The TeX files a theme's drawing reads, by the package that has them ->
    [(id, file, tl packages, licence)] -- what Settings checks is installed."""
    out = [("standalone",) + (ALWAYS["standalone"][1], ALWAYS["standalone"][0],
                              ALWAYS["standalone"][2])]
    for p in uses(theme):
        r = PACKAGES[p]
        out.append((p, r["file"], r["tl"], r["licence"]))
    if theme.get("compiler") in UNICODE and (theme.get("font") or theme.get("languages")):
        out.append(("fontspec", ALWAYS["fontspec"][1], ALWAYS["fontspec"][0],
                    ALWAYS["fontspec"][2]))
    if theme.get("compiler") in UNICODE and theme.get("font"):
        out.append(("unicode-math", ALWAYS["unicode-math"][1], ALWAYS["unicode-math"][0],
                    ALWAYS["unicode-math"][2]))
    return out


# ------------------------------------------------ renames an editor has not seen
# AN EDITOR OPEN WHILE A THEME IS RENAMED would save the old name back: the
# text it sends was read before the rename rewrote the file.  So each rename
# is logged under a number, the edit page carries how far the log went when
# it read its text (inside store.names_mark), and a save follows the renames
# made since (catch_up) -- as the studio's document links do.  In memory: a
# server started since the page was read knows nothing of what came before it.
_EPOCH = "%x" % int(time.time() * 1000)
_RENAMES = []           # [(n, old name key, new name)]


def rename_mark():
    with _LOCK:
        return "%s.%d" % (_EPOCH, len(_RENAMES))


def log_rename(old, new):
    with _LOCK:
        _RENAMES.append((len(_RENAMES) + 1, name_key(old), new))


def catch_up(text, mark):
    """`text`, read at `mark` (rename_mark(), possibly inside a longer mark),
    with the theme renames made since followed in it."""
    m = re.search(r"([0-9a-f]+)\.(\d+)$", str(mark or ""))
    if not m or m.group(1) != _EPOCH:
        return text
    with _LOCK:
        todo = [r for r in _RENAMES if r[0] > int(m.group(2))]
    for _n, old_key, new in todo:
        text, _count = rename_in_text(text, old_key, new)
    return text
