# SPDX-License-Identifier: GPL-3.0-or-later
"""htmlgen — render the mdparser block model as LaTeX-styled HTML.

This is the HTML twin of texgen.py: same block model in, same inline
semantics (opaque target-language runs, bold/italic on Latin only, gloss
`=`, linguistics `✗`), but the output is markup for the web reading view.
RTL correctness needs no TeXXeT here — the runs are emitted as
`<span dir="rtl">` and the browser's Unicode bidi algorithm does the
word reversal that \\beginR/\\endR do in the PDF; a left-to-right target
gets `dir="ltr"` and nothing else changes.

The language comes from the parsed front matter (`target:`), exactly as
in texgen: set_target() at the top of render_document() / glosses() /
stats(), then cur_lang() / run_re() / has_script() wherever a script is
tested.  The class names keep the `fa` of the Persian-only days -- every
stylesheet and script uses them -- and read "the target language".

Class map (styled in static/app.css):
  .fa       inline target text, unbreakable (the \\pe analogue)
  .fa-l     breakable target text (the \\pel analogue)
  .fa-b     bold target text (\\peb)
  .fa-display  stand-alone display line
  .fa-par   a whole-paragraph block; .fa-rich an inline one
  .fa-alt   the alternate face (.fa-nasta is kept as a second class)
  .tl-vertical  a vertical block (columns), height in --tl-vh
  .voce     lemma header block (.voce-kana above .voce-translit)
  .box      tinted highlight box
  .bt       booktabs-style table
  .desc/.lex   description lists (inline / label-on-own-line)
"""
import contextlib
import hashlib
import html
import re
import sys
import threading
import unicodedata
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXLEX = HERE.parent / "exlex"
if str(EXLEX) not in sys.path:
    sys.path.insert(0, str(EXLEX))

import mdparser  # noqa: E402
from texgen import (FA_CHARS, FA_RE, RUN_RE, PE_WORD_LIMIT,  # noqa: E402,F401
                    PALETTE, HEX_RE, FN_INLINE_RE, FN_REF_RE, LINK_RE,
                    COLOR_RE, TRANSLIT_RE, TL_RE, RTL_RE, RTL_BG, LA_RE,
                    LATIN_RUN_RE, DOCLINK_RE, resolve_doclink, set_doc_index,
                    unescape_doc_name, find_doclinks,
                    parse_tl_attrs, parse_rtl_attrs, parse_la_attrs,
                    parse_mark_fields, ThreadDict, image_indent, fmt_time,
                    _norm_colour, is_fa_only_paragraph, _is_pure_fa_paragraph,
                    set_target, cur_lang, run_re, has_script, is_latin_target,
                    run_is_long, tl_re, UNGRAM_MARK_RE, UNGRAM_WORD,
                    PROSE_WORD_RE, audio_window,
                    MATH_RE, LATEX_INLINE_RE, inline_latex_pairs,
                    NOT_A_RUN, is_target_line, prompt_lines)
from texgen import target_marks, target_fullmatch  # noqa: E402
import languages  # noqa: E402
from segcolour import find_runs as segmented_runs  # noqa: E402

# THE PROSE A DOCUMENT IS EXPLAINED IN, when its front matter does not say.
# It used to be Italian, from the months when the studio had one author and
# one prose language; everything else had already moved on -- the README
# says an omitted `lang:` means English, the PDF sets English
# (texgen.DEFAULT_HYPHEN) and the guide's own pages default to English --
# so a document that said nothing was hyphenated as Italian by the browser
# and read out in an Italian voice by a screen reader.
DEFAULT_PROSE = "en"


def _dir_lang():
    """The `dir`/`lang` attributes of every target-language element."""
    L = cur_lang()
    return ' dir="%s" lang="%s"' % (L.dir, L.code)


def _tl_style_bits(attrs):
    """Block attrs -> (extra classes, data attributes, style) for a span
    or paragraph.  The data-tl-* attributes let the editor's hover cloud
    reopen the block in the target-text overlay; data-rtl-kind/-src are
    the names the first version used and are still written beside them."""
    cls = ""
    if attrs.get("font"):
        cls += " fa-alt fa-nasta"
    if attrs.get("bg"):
        cls += " rtl-bg-%s" % attrs["bg"]
    style = ""
    if attrs.get("vertical"):
        cls += " tl-vertical"
        style = ' style="--tl-vh:%dem"' % attrs["height"]
    data = (' data-tl-font="%s" data-tl-bg="%s" data-tl-vertical="%s" '
            'data-tl-height="%d" data-rtl-font="%s" data-rtl-bg="%s"'
            % (attrs.get("font") or "", attrs.get("bg") or "",
               "1" if attrs.get("vertical") else "", attrs.get("height", 22),
               attrs.get("font") or "", attrs.get("bg") or ""))
    return cls, data, style

# Only these schemes become clickable links; anything else (javascript:,
# data:, …) is rendered as plain text.
SAFE_SCHEMES = ("http://", "https://", "mailto:", "#", "/")

# The prefix the studio is served under ("" alone, "/studio" inside Parseh);
# the server sets it.  Only document-to-document links need it here --
# image URLs arrive ready-made through asset_base.
URL_BASE = ""

# The prefix a cross-document link carries.  A process global was enough while
# there was one library; there are two now (the studio's, and the notes beside
# one book or one video), and a link from one note to another has to stay
# inside the mount it was written in.  Held per thread, like the library and
# the mount themselves, with the process global as the default -- so the CLI
# and anything that never sets one are unchanged.
_HERE = threading.local()


def set_url_base(base):
    """Point this thread's document links at another mount, and give back
    what it was so a caller can put it back."""
    was = getattr(_HERE, "base", None)
    _HERE.base = base
    return was


def url_base():
    b = getattr(_HERE, "base", None)
    return URL_BASE if b is None else b

# Footnote state, mirroring texgen's: numbering is document-global and
# assigned in source order.  `muted` is set while rendering footnote
# bodies, so runs inside a note are not offered to the word cloud
# (they are rendered twice — in the cloud and in the end list — and would
# desynchronise the occurrence counter against the source).  It is set
# too while a flashcard draws a field as blocks: the page's editors leave
# a card alone, and store skips the same text (mdparser.card_spans).
_FN = ThreadDict(n=0, defs={}, notes=[], muted=False, open=())
# an inline latex mark's own failures (_inline_latex), counted the same way
# a block's are (ctx["latex_failed"], _latex_frame) -- inline() has no ctx
# to add to directly, so this is read back into it once render_document is
# whole, the same reason _FN is a ThreadDict rather than threaded through
_LATEX_INLINE_RUN = ThreadDict(failed=0)
# How many of each thing the hover editors name by (what, occurrence) have
# been drawn so far: a run under its text, a target-language block under
# ("tl", kind, tl_key(content)).
_OCC = ThreadDict()

# THE WORDS OF AN EXERCISE ARE NUMBERED IN THE ORDER THEY ARE WRITTEN.  The
# page draws an exercise in an order of its own -- the prompt, the rows, then
# the explanations, whatever order the fields come in; every left side of a
# matching exercise, then every right side in the bank; a solved fill-in with
# its answers inside the sentence; a reversed card back first -- and the
# hover palette names a run by (text, occurrence), which store finds by
# counting in the source.  So while an exercise is drawn a run's number is
# held back, with the source line of the piece it is in (`at`, set by
# _written_at) and a part within the line (a row's left side before its
# right), and given out once the exercise is whole, in that order.  The
# number of a target-language block the target-text overlay edits
# (data-tl-occ) is held back with them, for the same reason.
_EX_ORDER = ThreadDict(on=False, at=(0, 0), runs=[], block=None)


def reset_state(defs=None):
    _FN.update({"n": 0, "defs": dict(defs or {}), "notes": [], "muted": False, "open": ()})
    _OCC.clear()
    _EX_ORDER.update({"on": False, "at": (0, 0), "runs": [], "block": None})
    _LATEX_INLINE_RUN.update({"failed": 0, "preview": False, "defer": False, "idx": 0, "pending": 0})


def _next_occ(key):
    occ = _OCC.get(key, 0)
    _OCC[key] = occ + 1
    return occ


def _occurrence(key):
    """The number of the next thing drawn under `key` (see _OCC) -- or,
    while an exercise is drawn, a placeholder for it (_EX_ORDER)."""
    if not _EX_ORDER["on"]:
        return _next_occ(key)
    runs = _EX_ORDER["runs"]
    runs.append((_EX_ORDER["at"], len(runs), key))
    return "\x07%d\x07" % (len(runs) - 1)


def tl_key(content):
    """What makes two target-language blocks the same block to the
    overlay's count: their text, however it is spaced and however its
    ⏎ are (store._norm_rtl is this)."""
    return re.sub(r"\s*⏎\s*", "⏎", re.sub(r"\s+", " ", content).strip())


def _tl_occ(kind, content):
    return ' data-tl-occ="%s"' % _occurrence(("tl", kind, tl_key(content)))


@contextlib.contextmanager
def _written_at(line, part=0):
    """`with _written_at(line, part):` -- the runs drawn inside come from
    that line of the source (see _EX_ORDER)."""
    was, _EX_ORDER["at"] = _EX_ORDER["at"], (line, part)
    try:
        yield
    finally:
        _EX_ORDER["at"] = was


def _field_at(key):
    """The runs of a field of the exercise being drawn: its first line."""
    b = _EX_ORDER["block"] or {}
    lines = (b.get("_field_lines") or {}).get(key)
    return _written_at(lines[0] if lines else b.get("_line", 0))


def _row_at(i, part=0):
    """The runs of the i-th item (row) of the exercise being drawn; `part`
    1 for the right side of a `left => right` row."""
    b = _EX_ORDER["block"] or {}
    lines = b.get("_item_lines") or ()
    return _written_at(lines[i] if 0 <= i < len(lines) else b.get("_line", 0), part)


def _number_exercise_runs(html, runs):
    """Give the numbers held back while an exercise was drawn, in the order
    of the source (_EX_ORDER), and write them into its HTML."""
    number = {}
    for _at, k, key in sorted(runs):
        number[k] = _next_occ(key)
    return re.sub("\x07(\\d+)\x07", lambda m: str(number[int(m.group(1))]), html)


def esc(s):
    return html.escape(s, quote=True)


def _safe_url(u):
    return u if u.lower().startswith(SAFE_SCHEMES) else ""


def _rtl_html(content):
    """Opaque block content -> HTML: escaped, with ⏎ as a line break."""
    return re.sub(r"\s*⏎\s*", "<br>", esc(content))


def _segmented_html(node, force_breakable=False):
    """One semantic coloured word and its visual child spans."""
    plain = node.plain_text
    cls = "fa segmented-colour-run"
    if force_breakable or run_is_long(plain):
        cls += " fa-l"
    bits = ' data-fa="%s" data-occ="%s"' % (esc(plain), _occurrence(plain))
    if node.mark("translit"):
        bits += ' data-translit="%s"' % esc(node.mark("translit"))
    if node.mark("kana"):
        bits += ' data-kana="%s"' % esc(node.mark("kana"))
    inside = []
    for piece in node.pieces:
        body = esc(piece.text)
        if not piece.colour:
            inside.append(body)
        elif piece.colour.startswith("#"):
            inside.append('<span class="seg-colour fac" data-color="%s" '
                          'style="color:%s">%s</span>'
                          % (piece.colour, piece.colour, body))
        else:
            inside.append('<span class="seg-colour fac fac-%s" '
                          'data-color="%s">%s</span>'
                          % (piece.colour, piece.colour, body))
    return '<span class="%s"%s%s>%s</span>' % (
        cls, _dir_lang(), bits, "".join(inside))


def _rtl_segmented_html(content):
    """Opaque target prose, except for recognised segmented-colour words."""
    out, at = [], 0
    for node in segmented_runs(content):
        out.append(_rtl_html(content[at:node.start]))
        out.append(_segmented_html(node, force_breakable=True))
        at = node.end
    out.append(_rtl_html(content[at:]))
    return "".join(out)


def _fa_span(run, breakable, bold=False, countable=True):
    cls = "fa"
    if bold:
        cls += " fa-b"          # \peb is an \mbox: bold runs never break
    elif breakable or run_is_long(run):
        cls += " fa-l"
    # Inside a footnote body, or after ✗, the run is not colourable: no
    # data attributes and no occurrence count, so the picker's indices
    # stay in step with store._run_matches, which masks the same spots.
    if _FN["muted"] or not countable:
        return '<span class="%s"%s>%s</span>' % (cls, _dir_lang(), esc(run))
    return ('<span class="%s"%s data-fa="%s" data-occ="%s">'
            '%s</span>' % (cls, _dir_lang(), esc(run), _occurrence(run), esc(run)))


def _footnote(num, content):
    """A reference plus its hover cloud; also collected for the end list."""
    was, _FN["muted"] = _FN["muted"], True
    # a note that cites itself, or a ring of notes, would expand forever:
    # a body already being expanded further up is left empty
    opened, body = _FN["open"], ""
    if content.strip() and content not in opened:
        _FN["open"] = opened + (content,)
        try:
            body = inline(content)
        finally:
            _FN["open"] = opened
    _FN["muted"] = was
    _FN["notes"].append((num, body))
    return ('<span class="fn"><sup class="fnref" tabindex="0" '
            'role="button" aria-describedby="fn-%d">%d</sup>'
            '<span class="fncloud" role="tooltip" id="fn-%d">%s</span></span>'
            % (num, num, num, body))


# A TITLE SHOWN FOR AN EMPTY LABEL.  `[](doc:Name)` shows the target's
# current title, which is not in the source where the link is.  It is
# drawn on its own, as the page draws a title (a mark in it coloured, a run
# of the target script in its font), muted like a footnote's body: its
# runs are not counted, as store._mask_uncountable blanks the name they
# stand in for, so the occurrence numbers the hover tools edit by stay the
# source's own.  And it goes into the link whole, so a bracket in a title
# ("[bracket] {brace}", "A [x]{teal} word") can never break the link
# around it.  A title shown inside a title is shown as its plain words: a
# title holding a label-less link to itself would never end.
_SHOWING = ThreadDict(on=False)


def _shown_title(title, force_breakable=False):
    if _SHOWING["on"]:
        return esc(title)
    was, _FN["muted"], _SHOWING["on"] = _FN["muted"], True, True
    try:
        # a note in a title would be one of this document's notes
        return inline(FN_REF_RE.sub("", FN_INLINE_RE.sub("", title)), force_breakable)
    finally:
        _FN["muted"], _SHOWING["on"] = was, False


def inline(text, force_breakable=False):
    """Markdown inline fragment -> HTML fragment (mirrors texgen.inline)."""
    store = []
    aux = []
    latin = is_latin_target()

    # ❌ is a synonym of ✗; a colour mark straight after ✗ is stripped —
    # the ungrammatical red cannot be overridden, not even by the user.
    # For a script language the bare text is re-detected as a run below;
    # for a Latin target the mark IS the run, so it is written back as
    # the plain marker, which the block pass freezes and ✗ then flags.
    text = text.replace("❌", "✗")
    text = UNGRAM_MARK_RE.sub(r"✗[\1]{tl}" if latin else r"✗\1", text)

    def _aux(*payload):
        aux.append(payload)
        return "\x05%d\x05" % (len(aux) - 1)

    def freeze(m):
        store.append(m.group(0))
        return "\x00%d\x00" % (len(store) - 1)

    def freeze_text(s):
        store.append(s)
        return "\x00%d\x00" % (len(store) - 1)

    # 0. footnote bodies, URLs and colour names, frozen before escaping
    def _fn_inline(m):
        _FN["n"] += 1
        return _aux("fn", _FN["n"], m.group(1))
    text = FN_INLINE_RE.sub(_fn_inline, text)

    def _fn_ref(m):
        _FN["n"] += 1
        return _aux("fn", _FN["n"], _FN["defs"].get(m.group(1), ""))
    text = FN_REF_RE.sub(_fn_ref, text)

    # Hold a balanced target-language mark containing a segmented word
    # before freezing the inner run, so its outer brackets stay structural.
    for mark in reversed(list(target_marks(text))):
        if list(segmented_runs(mark.content)):
            text = (text[:mark.start]
                    + _aux("rtl-seg", mark.content, parse_tl_attrs(mark.attrs))
                    + text[mark.end:])

    # Keep a partially coloured word as one semantic node.  This happens
    # before the old colour pass so its inner pieces never become separate
    # target-language runs/cloud targets.
    for node in reversed(list(segmented_runs(text))):
        text = text[:node.start] + _aux("seg", node) + text[node.end:]

    # target-language stretches (before links/colours: same [..]{..}
    # shape); for a Latin target an inline `[…]{tl}` is just a run
    if latin:
        text = tl_re().sub(lambda m: freeze_text(m.group(1)), text)
    else:
        text = tl_re().sub(
            lambda m: _aux("rtl", m.group(1), parse_tl_attrs(m.group(2))), text)

    # maths, before every other bracketed mark: its body may hold brackets
    # and braces that one of them would otherwise claim, and frozen here it
    # never meets esc() -- the escaping happens once, at emission, where
    # the TeX goes into an attribute AND into the text
    text = MATH_RE.sub(lambda m: _aux("math", m.group(1)), text)

    # inline latex (TO-DO §8.39's L8), the same reason: raw LaTeX, drawn
    # apart with its own (optional) theme, never mistaken for prose or run
    text = LATEX_INLINE_RE.sub(lambda m: _aux("latex", m.group(1), m.group(3)), text)

    # cross-document links before LINK_RE, which matches the same shape.
    # An empty label shows the target's title (or the name a dead link
    # waits for), drawn apart and handed in whole (_shown_title)
    def _doclink(m):
        label, target = resolve_doclink(m.group(2), m.group(1))
        if not m.group(1).strip():
            label = _aux("html", _shown_title(label, force_breakable))
        return "[%s]%s" % (label, _aux("doc", target, unescape_doc_name(m.group(2))))
    text = DOCLINK_RE.sub(_doclink, text)

    text = LINK_RE.sub(
        lambda m: "[%s]%s" % (m.group(1), _aux("url", m.group(2))), text)

    # transliteration/reading annotations (optionally coloured) — before
    # the plain-colour pass, whose regex would not match the colon
    def _translit(m):
        fields = parse_mark_fields(m.group(3))
        return "[%s]%s" % (m.group(1),
                           _aux("colt", _norm_colour(m.group(2)),
                                fields.get("translit", ""),
                                fields.get("kana", "")))
    text = TRANSLIT_RE.sub(_translit, text)

    def _col(m):
        v = m.group(2)
        if v.startswith("#"):        # arbitrary colour by hex
            return "[%s]%s" % (m.group(1), _aux("col", "#" + v[1:].upper()))
        name = v.lower()
        if name not in PALETTE:
            # an unknown word still marks a run for a Latin target -- but
            # not the Latin-block keywords, which LATIN_RUN_RE excludes too
            if latin and name not in NOT_A_RUN:
                return "[%s]%s" % (m.group(1), _aux("colt", None, "", ""))
            return m.group(0)
        return "[%s]%s" % (m.group(1), _aux("col", name))
    text = COLOR_RE.sub(_col, text)

    # 1. freeze the runs (opaque from here on); a Latin target's runs are
    #    the bracketed texts of the marks just processed
    if latin:
        def _mark_run(m):
            item = aux[int(m.group(2))]
            if item[0] in ("col", "colt"):
                return "[%s]\x05%s\x05" % (freeze_text(m.group(1)), m.group(2))
            return m.group(0)
        text = re.sub(r"\[([^\[\]\x00]*)\]\x05(\d+)\x05", _mark_run, text)
    else:
        text = run_re().sub(freeze, text)

    # 2. escape HTML in the Latin remainder
    text = esc(text)

    # 3. inline markdown on Latin
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    def bold(m):
        inner = m.group(1)
        pm = re.fullmatch(r"\x00(\d+)\x00", inner)
        if pm:                       # **فارسی** -> bold run
            store[int(pm.group(1))] = "\x01" + store[int(pm.group(1))]
            return inner
        return "<strong>%s</strong>" % inner
    text = re.sub(r"\*\*(.+?)\*\*", bold, text)

    def ital(m):
        inner = m.group(1)
        if "\x00" in inner:          # never across a run
            return m.group(0)
        return "<em>%s</em>" % inner
    text = re.sub(r"(?<![\w*\\])\*([^*\n]+?)\*(?!\*)", ital, text)

    text = text.replace("→", '<span class="arrow">→</span>')
    text = re.sub(r"\s*-&gt;\s*", ' <span class="arrow">→</span> ', text)

    # ⏎ forces a line break (source newlines are ignored by design)
    text = re.sub(r"\s*⏎\s*", "<br>", text)

    # ✗ marks the following form ungrammatical: red ❌ before it and the
    # form itself tinted red (never colourable).  ✅ is a stand-alone
    # green check that leaves the following text untouched.
    def _ungram_run(m):
        idx = int(m.group(1).strip("\x00"))
        store[idx] = "\x02" + store[idx]
        return m.group(1)
    text = re.sub(r"✗(\x00\d+\x00)", _ungram_run, text)
    text = re.sub(r"✗(%s)" % UNGRAM_WORD,
                  r'<span class="ungram-run"><span class="ungram-x">❌</span>'
                  r'\1</span>', text)
    text = text.replace("✗", '<span class="ungram-x">❌</span>')

    # 4. thaw the runs.  The index can only be out of range if a literal
    # \x00<digits>\x00 was present in the input (ingest strips C0 controls,
    # but stay defensive): leave any such match untouched rather than crash.
    def thaw(m):
        idx = int(m.group(1))
        if idx >= len(store):
            return m.group(0)
        raw = store[idx]
        flags = set()
        while raw[:1] in ("\x01", "\x02"):
            flags.add(raw[0])
            raw = raw[1:]
        span = _fa_span(raw, breakable=force_breakable,
                        bold=("\x01" in flags),
                        countable=("\x02" not in flags))
        if "\x02" in flags:
            return ('<span class="ungram-run">'
                    '<span class="ungram-x">❌</span>%s</span>' % span)
        return span
    text = re.sub(r"\x00(\d+)\x00", thaw, text)

    # 5. assemble links and colour marks around their (now rendered) text
    def _bracket(m):
        inner, item = m.group(1), aux[int(m.group(2))]
        if item[0] == "url":
            url = _safe_url(item[1])
            if not url:
                return inner
            return ('<a class="lnk" href="%s" target="_blank" '
                    'rel="noopener noreferrer">%s</a>' % (esc(url), inner))
        if item[0] == "doc":
            # same tab: this is a move within the library, not an exit
            if not item[1]:
                # left hanging, not dropped: a document given this name
                # again (made, uploaded, restored or renamed) is what it
                # points at from then on, with nothing rewritten
                return ('<span class="doclink-dead" data-name="%s" title="No '
                        'document named “%s” in this library — create or upload '
                        'one with this name and this link will work again">%s</span>'
                        % (esc(item[2]), esc(item[2]), inner))
            return ('<a class="doclink" href="%s/doc/%s" data-name="%s">%s</a>'
                    % (url_base(), esc(item[1]), esc(item[2]), inner))
        if item[0] == "col":
            if item[1].startswith("#"):
                return ('<span class="fac" data-color="%s" '
                        'style="color:%s">%s</span>'
                        % (item[1], item[1], inner))
            return '<span class="fac fac-%s" data-color="%s">%s</span>' % (
                item[1], item[1], inner)
        if item[0] == "colt":
            # the text renders as if unmarked; the wrapper only carries
            # the transliteration and the reading (and the colour, when
            # present) as data for the hover overlay
            col, tr, kana = item[1], item[2], item[3]
            bits = ""
            if tr:
                bits += ' data-translit="%s"' % esc(tr)
            if kana:
                bits += ' data-kana="%s"' % esc(kana)
            if col is None:
                return '<span class="fac"%s>%s</span>' % (bits, inner)
            if col.startswith("#"):
                return ('<span class="fac" data-color="%s" '
                        'style="color:%s"%s>%s</span>'
                        % (col, col, bits, inner))
            return ('<span class="fac fac-%s" data-color="%s"%s>%s</span>'
                    % (col, col, bits, inner))
        return m.group(0)
    # innermost first: a mark inside a link's label (DOCLINK_RE) is
    # assembled before the link around it can be
    for _ in range(3):
        was, text = text, re.sub(r"\[([^\[\]]*)\]\x05(\d+)\x05", _bracket, text)
        if text == was:
            break
    # and a label still holding brackets -- a mark in it that is none
    # (`[[کتاب]{red}](doc:…)`: no such colour), printed as it was written,
    # as it is outside a link -- is a link all the same
    text = re.sub(r"\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\x05(\d+)\x05", _bracket, text)

    # 6. footnote marks, target-language stretches, and any link whose
    #    [text] did not survive
    def _lone(m):
        item = aux[int(m.group(1))]
        if item[0] == "fn":
            return _footnote(item[1], item[2])
        if item[0] == "math":
            # The notation goes out TWICE: into data-tex, which is what the
            # page draws from and what an editor reads back, and as the
            # text of the span, which is what is seen by anything that
            # never runs a script -- a print, a page opened off the disk,
            # a reader with the renderer missing.  Both escaped: a formula
            # with a `<` or a `"` in it is an ordinary formula.
            return '<span class="math" data-tex="%s">%s</span>' \
                % (esc(item[1]), esc(item[1]))
        if item[0] == "latex":
            return _inline_latex(item[1], item[2] if len(item) > 2 else None)
        if item[0] == "seg":
            return _segmented_html(item[1], force_breakable)
        if item[0] == "rtl-seg":
            attrs = dict(item[2])
            attrs["vertical"] = False
            cls, data, _ = _tl_style_bits(attrs)
            tag = ("" if _FN["muted"] else
                   ' data-tl-kind="mark" data-tl-src="%s"%s'
                   ' data-rtl-kind="mark" data-rtl-src="%s"%s'
                   % (esc(item[1]), _tl_occ("mark", item[1]), esc(item[1]), data))
            return ('<span class="fa fa-l fa-rich%s"%s%s>%s</span>'
                    % (cls, _dir_lang(), tag, _rtl_segmented_html(item[1])))
        if item[0] == "rtl":
            # one isolated unit in the target's direction: the browser's
            # bidi keeps punctuation and embedded Latin words in reading
            # order (not colourable — the content is not a single run).
            # data-tl-* lets the editor's hover cloud open the block in
            # the target-text overlay (skipped inside footnotes, whose
            # bodies render twice).  Vertical applies to whole paragraphs
            # only, so an inline block ignores it.
            attrs = dict(item[2] if len(item) > 2 else parse_tl_attrs(""))
            attrs["vertical"] = False
            cls, data, _ = _tl_style_bits(attrs)
            tag = ("" if _FN["muted"] else
                   ' data-tl-kind="mark" data-tl-src="%s"%s'
                   ' data-rtl-kind="mark" data-rtl-src="%s"%s'
                   % (esc(item[1]), _tl_occ("mark", item[1]), esc(item[1]), data))
            return ('<span class="fa fa-l fa-rich%s"%s%s>%s'
                    '</span>' % (cls, _dir_lang(), tag, _rtl_html(item[1])))
        if item[0] == "url":
            url = _safe_url(item[1])
            return ('<a class="lnk" href="%s" target="_blank" '
                    'rel="noopener noreferrer">%s</a>' % (esc(url), esc(url))
                    if url else esc(item[1]))
        if item[0] == "html":
            return item[1]
        return ""
    text = re.sub(r"\x05(\d+)\x05", _lone, text)

    # 7. grey `=` in glosses  (فارسی = translation).  Only after a run's
    # span — possibly inside a colour/translit wrapper, possibly bold —
    # exactly as texgen keys off \pe/\pel/\peb; an `=` following an arrow
    # or ✗ is ordinary text.
    text = re.sub(
        r'(<span class="fa[^"]*"[^>]*>[^<]*</span>(?:</(?:span|strong)>)*) = ',
        r'\1 <span class="eq">=</span> ', text)
    return text


# ----------------------------------------------------------------------
# block renderers
# ----------------------------------------------------------------------

def _render_table(b):
    ncols = len(b["header"])
    size = " t-fn" if ncols >= 6 else (" t-sm" if ncols >= 4 else "")
    align = (b["align"] + ["l"] * ncols)[:ncols]
    out = ['<div class="tablewrap"><table class="bt%s">' % size,
           "<thead><tr>"]
    for a, c in zip(align, b["header"]):
        out.append('<th class="a-%s">%s</th>' % (a, inline(c)))
    out.append("</tr></thead><tbody>")
    for row in b["rows"]:
        row = (row + [""] * ncols)[:ncols]
        out.append("<tr>")
        for a, c in zip(align, row):
            body = "—" if c in {"—", "--", "-"} else inline(c)
            out.append('<td class="a-%s">%s</td>' % (a, body))
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _render_list(b, ordered):
    labelled = all(re.match(r"^\*\*.+?\*\*", it[1]) for it in b["items"]) \
        and not ordered and len(b["items"]) > 1
    if labelled:
        env = "desc"
        for _, it in b["items"]:
            lab = re.match(r"^\*\*(.+?)\*\*", it).group(1)
            if has_script(lab) and len(lab) > 10:
                env = "lex"
                break
        out = ['<dl class="%s">' % env]
        for _, it in b["items"]:
            m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", it, re.S)
            out.append('<div class="di"><dt>%s</dt><dd>%s</dd></div>'
                       % (inline(m.group(1)), inline(m.group(2))))
        out.append("</dl>")
        return "".join(out)

    # one nesting level for bullets, as in texgen: any item indented past
    # the base indent sits in a nested list.  texgen applies this to every
    # item including the first, so a leading indented item nests too.
    tag = "ol" if ordered else "ul"
    items = b["items"]
    base = min(ind for ind, _ in items)
    out, i, n = ["<%s>" % tag], 0, len(items)
    while i < n:
        if items[i][0] > base:          # nested run with no parent item
            subs = []
            while i < n and items[i][0] > base:
                subs.append("<li>%s</li>" % inline(items[i][1]))
                i += 1
            out.append("<ul>%s</ul>" % "".join(subs))
            continue
        out.append("<li>%s" % inline(items[i][1]))
        i += 1
        subs = []
        while i < n and items[i][0] > base:
            subs.append("<li>%s</li>" % inline(items[i][1]))
            i += 1
        if subs:
            out.append("<ul>%s</ul>" % "".join(subs))
        out.append("</li>")
    out.append("</%s>" % tag)
    return "".join(out)


def _figure_idx(ctx):
    """The layout index of the next figure (image, video or recording):
    ` data-idx="n"`, the counter moved on.  A figure inside a flashcard
    has none and moves nothing -- store.image_layout_markdown's line scan
    is what data-idx has to agree with, and the layout editor never opens
    on a card."""
    if ctx.get("in_card"):
        return ""
    idx = ctx["img"]
    ctx["img"] += 1
    return ' data-idx="%d"' % idx


def _asset_url(ctx, path):
    """Where the page loads one of the document's files from (`path` as the
    markdown names it, `images/cat.png`, `audio/word.mp3`): `asset_base` and
    the path -- or, when `asset_base` is a function of the path, what it
    answers (a deck's form preview: a file the unsaved exercise names may be
    a clip still in the tray, deckroutes.api_preview).

    None when the file has no URL: there is no `asset_base` at all, or the
    function says so (the editor's preview of a document not saved yet
    shows the starter's own pictures and has no URL for any other,
    server.api_preview).  The caller then draws its placeholder."""
    base = ctx.get("asset_base")
    if not base:
        return None
    return base(path) if callable(base) else base + path


def _render_image(b, ctx):
    idx = _figure_idx(ctx)
    if not b.get("valid"):
        return ('<div class="img-missing">immagine non valida: '
                '<code>%s</code></div>' % esc(b["path"]))
    ml = image_indent(b) * 100
    cap = ("<figcaption>%s</figcaption>" % inline(b["caption"])
           if b["caption"] else "")
    src = b["path"]
    if src.lower().endswith(".pdf"):
        # No browser shows a PDF inside a figure, so the store writes
        # its first page beside it as SVG — still vector, so it scales
        # with the figure exactly as the PDF does on paper.  The
        # mirror of the SVG -> PDF conversion XeLaTeX needs.
        src += ".svg"
    url = _asset_url(ctx, src)
    if url is not None:
        media = ('<img src="%s" alt="%s">'
                 % (esc(url), esc(b["caption"])))
    else:   # unsaved preview: the file has no URL yet
        media = ('<div class="img-placeholder">🖼 <code>%s</code></div>'
                 % esc(b["path"]))
    return ('<figure class="img align-%s"%s data-width="%d" '
            'data-align="%s" data-offset="%d" '
            'style="width:%d%%;margin-left:%.2f%%">%s%s</figure>'
            % (b["align"], idx, b["width"], b["align"], b["offset"],
               b["width"], ml, media, cap))


def _render_video(b, ctx):
    idx = _figure_idx(ctx)
    if not b.get("valid"):
        return ('<div class="img-missing">video non valido: '
                '<code>%s</code></div>' % esc(b["url"]))
    ml = image_indent(b) * 100
    # YouTube takes whole seconds: a fraction written for a recording's
    # sake never reaches its URL
    start = None if b.get("start") is None else int(b["start"])
    end = None if b.get("end") is None else int(b["end"])
    qs = "rel=0"
    if start is not None:
        qs += "&start=%d" % start
    if end is not None:
        qs += "&end=%d" % end
    if start is not None or end is not None:
        # YouTube honours start/end only on the FIRST play of a loaded
        # iframe; with the JS API enabled the page listens for `ended`
        # and reloads the player, so every replay is the same snippet.
        qs += "&enablejsapi=1"
    src = "https://www.youtube-nocookie.com/embed/%s?%s" % (b["vid"], qs)
    cap = ("<figcaption>%s</figcaption>" % inline(b["caption"])
           if b["caption"] else "")
    edit = ("" if ctx.get("in_card") else
            '<button class="video-edit" type="button" '
            'title="Layout &amp; clip">⚙ layout</button>')
    return ('<figure class="img video align-%s"%s data-width="%d" '
            'data-align="%s" data-offset="%d" data-vid="%s" '
            'data-start="%s" data-end="%s" '
            'style="width:%d%%;margin-left:%.2f%%">'
            '<div class="video-box"><iframe src="%s" title="%s" '
            'allow="accelerometer; encrypted-media; picture-in-picture" '
            'allowfullscreen loading="lazy"></iframe></div>'
            '%s%s</figure>'
            % (b["align"], idx, b["width"], b["align"], b["offset"],
               esc(b["vid"]),
               "" if start is None else start,
               "" if end is None else end,
               b["width"], ml, esc(src), esc(b["caption"] or "YouTube"),
               edit, cap))


def _render_audio(b, ctx):
    """A recording on its own line: an <audio> laid out like a picture.
    start/end become a media fragment (`#t=65.2,69`), which the browser
    seeks to; stopping at the end is the page script's job."""
    idx = _figure_idx(ctx)
    if not b.get("valid"):
        return ('<div class="img-missing">not an audio file: '
                '<code>%s</code></div>' % esc(b["path"]))
    ml = image_indent(b) * 100
    start, end = audio_window(b)
    url = _asset_url(ctx, b["path"])
    if url is not None:
        frag = ""
        if start is not None or end is not None:
            frag = "#t=%s" % mdparser.clip_seconds(start or 0)
            if end is not None:
                frag += ",%s" % mdparser.clip_seconds(end)
        media = ('<audio controls preload="metadata" src="%s"></audio>'
                 % esc(url + frag))
    else:   # unsaved preview: the file has no URL yet
        media = ('<div class="img-placeholder">🔊 <code>%s</code></div>'
                 % esc(b["path"]))
    edit = ("" if ctx.get("in_card") else
            '<button class="audio-edit" type="button" '
            'title="Layout &amp; clip">⚙ layout</button>')
    cap = ("<figcaption>%s</figcaption>" % inline(b["caption"])
           if b["caption"] else "")
    window = "".join(' data-%s="%s"' % (k, mdparser.clip_seconds(v))
                     for k, v in (("start", start), ("end", end))
                     if v is not None)
    return ('<figure class="img audio align-%s"%s data-width="%d" '
            'data-align="%s" data-offset="%d"%s '
            'style="width:%d%%;margin-left:%.2f%%">%s%s%s</figure>'
            % (b["align"], idx, b["width"], b["align"], b["offset"], window,
               b["width"], ml, media, edit, cap))


# ----------------------------------------------------------------------
# LaTeX drawings (TO-DO §8.39)
# ----------------------------------------------------------------------

# WHO DRAWS A LATEX BLOCK: lib/latexdraw.py, handed in by whoever serves the
# pages (set_latex) -- the toolbox, the studio alone, the exlex command.  A
# renderer with none -- the guide's compile, which runs on computers with no
# TeX -- never draws one live, and shows the block as what it is instead.
# `settings` is where the computer's Settings -> LaTeX drawings is, for the
# buttons under a block that cannot be drawn: none where there is no such page.
LATEX = {"draw": None, "draw_all": None, "settings": None, "peek": None}


def set_latex(draw, draw_all=None, settings=None, peek=None):
    LATEX.update(draw=draw, draw_all=draw_all, settings=settings, peek=peek)


# A PAGE THAT WAITS FOR NO DRAWING (the owner, 2026-09-28).  A document with
# many drawings not made yet took as long to open as they took to compile,
# and a phone gave up on it ("Parseh cannot be reached").  Rendered with
# `latex_defer`, a page shows the drawings already made and, for each other
# one, a placeholder; the page then has them made (the studio's drawings
# route) and swaps each in.  Every drawing carries its number in the page,
# data-latex-idx, the same in every render of the same text.
def _latex_idx():
    # a caption's own marks are part of its figure, which is swapped whole:
    # they take no number, so that a block drawn, waiting or refused numbers
    # the drawings after it alike
    if _LATEX_INLINE_RUN.get("noidx"):
        return ""
    _LATEX_INLINE_RUN["idx"] = _LATEX_INLINE_RUN.get("idx", 0) + 1
    return ' data-latex-idx="%d"' % _LATEX_INLINE_RUN["idx"]


def _latex_ready(tex, theme):
    """A deferred page's drawing: what peek has, or None when it is not made."""
    r = LATEX["peek"](tex, theme)
    return None if r.get("ok") is None else r


def _latex_ready_inline(tex, theme):
    r = LATEX["peek"](tex, theme, inline=True)
    return None if r.get("ok") is None else r


def latex_wanted(markdown):
    """Every drawing a page of `markdown` shows -> [(tex, theme, inline)]:
    render_document's own two lists, blocks then inline marks."""
    fm, blocks = mdparser.parse(markdown)
    code = languages.get_or_default(fm.get("target")).code
    return ([(t, th, False) for t, th in latex_pairs(blocks, code)] +
            [(t, th, True) for t, th in inline_latex_pairs(markdown)])


def latex_pairs(blocks, target=None):
    """(tex, theme) of every well-formed latex block, in a box, in a prompt
    that is a fence on its own, and on a jolly card too -- drawn side by
    side before a page is rendered (render_document)."""
    out = []
    for b in blocks:
        if b["type"] == "latex" and not b.get("errors"):
            out.append((b.get("tex", ""), b.get("theme") or None))
        elif b["type"] == "box":
            out += latex_pairs(b["blocks"], target)
        elif b["type"] == "exercise" and not b.get("errors"):
            # a follow-up's steps are exercises of their own, their drawings too
            out += latex_pairs(b.get("steps") or [], target)
            if b.get("primitive") == "flashcard" and (b["fields"].get("card-type") or "").lower() == "jolly":
                for field in mdparser.card_fields(b, target)[0].values():
                    if field and field[0] == "blocks":
                        out += latex_pairs(field[1], target)
            prompt = mdparser.card_field(b, "prompt", target)
            if prompt and prompt[0] == "blocks":
                out += latex_pairs(prompt[1], target)
    return out


# a display fraction reads at the size of the words round it (a block's own
# rule), but MAY NOT push its own line apart from the ones around it: the
# owner, 2026-09-27, chose a cap over letting one grow however tall it likes
INLINE_LATEX_MAX_EM = 1.8


def _inline_latex_sizing(w, h, d):
    """(width, height, depth) in ems, the drawing's own w/h/d over the ten
    points they were set at -- shrunk together, keeping their proportion,
    when the height would be past INLINE_LATEX_MAX_EM."""
    w_em, h_em, d_em = (w or 0) / 10.0, (h or 0) / 10.0, (d or 0) / 10.0
    if h_em > INLINE_LATEX_MAX_EM > 0:
        scale = INLINE_LATEX_MAX_EM / h_em
        w_em, h_em, d_em = w_em * scale, h_em * scale, d_em * scale
    return w_em, h_em, d_em


def _inline_latex(tex, theme):
    """`[…]{latex}` / `[…]{latex theme}` (TO-DO §8.39's L8) -- a drawing made
    to sit inside a line of running text, on its own baseline, unlike a
    block: never a hole, its own source shown in its place when it cannot be
    made, exactly as a block's own failure frame promises, just without one
    (nothing this small belongs in a box in the middle of a sentence)."""
    draw = LATEX.get("draw")
    idx = _latex_idx()
    if draw is None:
        _LATEX_INLINE_RUN["failed"] += 1
        return ('<code class="latex-inline-src"%s data-latex-src="%s" data-latex-theme="%s">%s'
                '</code>' % (idx, esc(tex), esc(theme or ""), esc(tex)))
    if _LATEX_INLINE_RUN.get("defer") and LATEX.get("peek"):
        r = _latex_ready_inline(tex, theme)
        if r is None:
            _LATEX_INLINE_RUN["pending"] += 1
            return ('<code class="latex-inline-src latex-pending"%s data-latex-pending="1" '
                    'data-latex-src="%s" data-latex-theme="%s" title="Being drawn">%s</code>'
                    % (idx, esc(tex), esc(theme or ""), esc(tex)))
    # Do not add a false-valued keyword: integrations have long supplied the
    # two/three-argument drawing callable, and only the editor needs preview
    # storage in the first place.
    elif _LATEX_INLINE_RUN.get("preview"):
        r = draw(tex, theme, inline=True, preview=True)
    else:
        r = draw(tex, theme, inline=True)
    if not r.get("ok"):
        _LATEX_INLINE_RUN["failed"] += 1
        said = r.get("said") or "This drawing could not be made."
        return ('<code class="latex-inline-src latex-inline-fail" title="%s"%s '
                'data-latex-src="%s" data-latex-theme="%s">%s</code>'
                % (esc(said), idx, esc(tex), esc(theme or ""), esc(tex)))
    w_em, h_em, d_em = _inline_latex_sizing(r.get("w"), r.get("h"), r.get("d"))
    return ('<img class="latex-inline" src="%s" alt="A drawing made by LaTeX" '
            'data-latex-key="%s" data-latex-src="%s" data-latex-theme="%s"%s '
            'style="width:%.3fem;height:%.3fem;vertical-align:%.3fem">'
            % (esc(URL_BASE + r["url"]), esc(r["key"]), esc(tex), esc(theme or ""), idx,
               w_em, h_em, -d_em))


def _latex_src(b, ctx):
    idx = ctx.get("latex_idx") or ""
    if ctx.get("in_card"):
        return idx
    return (idx + ' data-latex-src="%s" data-latex-theme="%s" data-latex-caption="%s"'
            % (esc(b.get("tex", "")), esc(b.get("theme") or ""), esc(b.get("caption") or "")))


def _latex_frame(b, r, ctx):
    """A block that is not drawn, and why -- its source shown as code, never
    a hole and never a wrong drawing (the owner, 2026-09-24)."""
    ctx["latex_failed"] = ctx.get("latex_failed", 0) + 1
    said = r.get("said") or "This drawing could not be made."
    out = ['<div class="latex-fail" role="note" data-latex-kind="%s"%s>'
           % (esc(r.get("kind") or ""), _latex_src(b, ctx)),
           '<p class="latex-said"><b>LaTeX drawing.</b> %s</p>' % esc(said)]
    fix, url = r.get("fix") or {}, LATEX.get("settings")
    links = []
    if url and fix.get("kind") == "theme-missing":
        links.append('<a class="btn" href="%s?import=1">Import a theme…</a>' % esc(url))
        links.append('<a class="btn" href="%s?make=%s">Make a theme called “%s”</a>'
                     % (esc(url), esc(fix.get("theme") or ""), esc(fix.get("theme") or "")))
    elif url and fix.get("kind") == "install":
        pkg = fix.get("package") or ""
        links.append('<a class="btn" href="%s?install=%s">Get %s…</a>'
                     % (esc(url), esc(urllib.parse.quote(pkg, safe=",")),
                        esc(", ".join(n for n in pkg.split(",") if n))))
    elif url and fix.get("kind") == "theme" and fix.get("theme"):
        links.append('<a class="btn" href="%s?theme=%s">Open the theme “%s”</a>'
                     % (esc(url), esc(fix["theme"]), esc(fix["theme"])))
    if links:
        out.append('<p class="latex-fix">%s</p>' % " ".join(links))
    # THE .tex AND THE WHOLE LOG, on request (a0.5.4): of a compile that took place, as kept with it.  A button of the
    # studio's own page (app.js opens them in a frame on top); never of an exported page (webexport drops the class)
    key = r.get("key")
    if key and LATEX.get("draw"):
        base = URL_BASE + "/latex/" + str(key)
        marks = ",".join(str(n) for n in (r.get("marks") or []) if isinstance(n, int))
        out.append('<p class="latex-views">'
                   '<button type="button" class="btn latex-view" data-latex-view="tex" data-latex-url="%s.tex">'
                   'The .tex that was compiled</button> '
                   '<button type="button" class="btn latex-view" data-latex-view="log" data-latex-url="%s.log" '
                   'data-latex-marks="%s">The whole log</button></p>' % (esc(base), esc(base), esc(marks)))
    if r.get("detail"):
        out.append('<details class="latex-log"><summary>What LaTeX said</summary>'
                   '<pre dir="ltr">%s</pre></details>' % esc(r["detail"]))
    out.append('<pre class="latex-code" dir="ltr">%s</pre></div>' % esc(b.get("tex", "")))
    return "".join(out)


def _latex_captioned(b, r, ctx, align, offset, caption):
    """A drawing with a caption: the figure is the column wide, the drawing
    keeps the width and place it would have had, and the caption is a box
    centred under it, never narrower than 20em (or the column) so that it does
    not wrap into a sliver, and kept inside the column.  Its small type is the
    span's (sheet.css), so that the box's ems are the drawing's."""
    if b.get("width"):
        left = "%.2f%%" % (image_indent({"width": b["width"], "align": align, "offset": offset}) * 100)
        width = "%d%%" % b["width"]
        pic = "width:%s;margin-left:%s" % (width, left)
    else:
        width = "min(%.2fem,100%%)" % ((r.get("w") or 0) / 10.0)
        shift = "%d%%" % offset
        left = {"left": shift, "right": "calc(100%% - %s + %s)" % (width, shift)
                }.get(align, "calc((100%% - %s)/2 + %s)" % (width, shift))
        pic = "width:%.2fem;max-width:100%%;margin-left:%s" % ((r.get("w") or 0) / 10.0, left)
    box = "max(%s,min(100%%,20em))" % width
    cap = ("width:%s;margin-left:clamp(0px,calc(%s + (%s - %s)/2),calc(100%% - %s))"
           % (box, left, width, box, box))
    _LATEX_INLINE_RUN["noidx"] = True
    try:
        said = inline(caption)
    finally:
        _LATEX_INLINE_RUN["noidx"] = False
    return ('<figure class="latex has-caption align-%s" data-latex-key="%s" data-width="%s" '
            'data-align="%s" data-offset="%d"%s><img src="%s" alt="%s" style="%s;margin-right:auto">'
            '<figcaption style="%s;margin-right:auto"><span>%s</span></figcaption></figure>'
            % (align, esc(r["key"]), b.get("width") or "", align, offset, _latex_src(b, ctx),
               esc(URL_BASE + r["url"]), esc("A drawing made by LaTeX"), pic, cap, said))


def _render_latex(b, ctx):
    """A latex block: the drawing lib/latexdraw.py made of it, laid out as a
    figure is -- `width` a percentage of the column, `align`, `offset` -- and
    at its natural size when it gives no width: its width in points over
    the ten points it was set at, in ems, so it reads at the size of the
    text round it and grows with it."""
    ctx["latex_idx"] = _latex_idx()
    if b.get("errors"):
        return _latex_frame(b, {"kind": "dialect",
                                "said": "; ".join(b["errors"]).capitalize() + "."}, ctx)
    draw = LATEX.get("draw")
    if draw is None:
        return _latex_frame(b, {"kind": "here", "said": "It is drawn by LaTeX where Parseh "
                                "can compile it, and shown here as it is written."}, ctx)
    if _LATEX_INLINE_RUN.get("defer") and LATEX.get("peek"):
        r = _latex_ready(b.get("tex", ""), b.get("theme") or None)
        if r is None:
            _LATEX_INLINE_RUN["pending"] += 1
            return ('<figure class="latex-pending-block" data-latex-pending="1"%s>'
                    '<span class="latex-wait">Being drawn…</span>'
                    '<pre class="latex-code" dir="ltr">%s</pre></figure>'
                    % (_latex_src(b, ctx), esc(b.get("tex", ""))))
    # latex_preview, not editor_preview: a deck's solved study/cram view sets
    # the latter alone (show the answer) and its drawings must still be kept,
    # not treated as an unsaved editor's ephemeral preview (TO-DO §8.39's L9).
    # The kwarg is passed only when true, as every other LATEX["draw"] call
    # here does, so a test's simpler (tex, theme) stand-in keeps working.
    elif ctx.get("latex_preview"):
        r = draw(b.get("tex", ""), b.get("theme") or None, preview=True)
    else:
        r = draw(b.get("tex", ""), b.get("theme") or None)
    if not r.get("ok"):
        return _latex_frame(b, r, ctx)
    align, offset = b.get("align") or "center", 0 if ctx.get("in_card") else b.get("offset") or 0
    caption = (b.get("caption") or "").strip()
    if caption:
        return _latex_captioned(b, r, ctx, align, offset, caption)
    if b.get("width"):
        ml = image_indent({"width": b["width"], "align": align, "offset": offset}) * 100
        style = "width:%d%%;margin-left:%.2f%%" % (b["width"], ml)
    else:
        em = (r.get("w") or 0) / 10.0
        side = {"left": "margin-left:0;margin-right:auto", "right": "margin-left:auto;margin-right:0"
                }.get(align, "margin-left:auto;margin-right:auto")
        style = "width:%.2fem;max-width:100%%;%s" % (em, side)
        if offset:
            style += ";position:relative;left:%d%%" % offset
    return ('<figure class="latex align-%s" data-latex-key="%s" data-width="%s" data-align="%s" '
            'data-offset="%d"%s style="%s"><img src="%s" alt="%s"></figure>'
            % (align, esc(r["key"]), b.get("width") or "", align, offset, _latex_src(b, ctx),
               style, esc(URL_BASE + r["url"]), esc("A drawing made by LaTeX")))


def _render_box(b, ctx):
    inner = render_blocks(b["blocks"], ctx, inside_box=True)
    return '<div class="box">%s</div>' % inner


EXERCISE_LABELS = {
    "fill-blanks": "Fill the blanks", "flashcard": "Flashcard",
    "order-sentences": "Order the sentences",
    "match-translations": "Match translations",
    "match-opposites": "Match opposites",
    "match-definitions": "Match words and definitions",
    "yes-no": "Yes or no", "true-false": "True or false",
    "single-choice": "Choose one answer",
    "construct-sentence": "Construct the sentence",
    "incorrect-part": "Identify the incorrect part",
    "choose-all": "Choose all correct answers",
    "odd-one-out": "Odd one out",
    "follow-up": "Follow-up questions",
}


_EX_INLINE_IMAGE_RE = re.compile(r"!\[[^\[\]]*\]\(\s*[^()\s]+\s*\)(?:\{[^{}]*\})?")


def _ex_inline_text(text, ctx):
    """Render pictures inside any exercise text cell alongside ordinary prose."""
    out, end = [], 0
    for found in _EX_INLINE_IMAGE_RE.finditer(text):
        out.append(inline(text[end:found.start()], force_breakable=True))
        image = mdparser.IMAGE_RE.fullmatch(found.group(0))
        path = image.group(2) if image else ""
        if not mdparser.IMAGE_PATH_RE.fullmatch(path):
            out.append(esc(found.group(0)))
        else:
            src = path + ".svg" if path.lower().endswith(".pdf") else path
            url = _asset_url(ctx, src)
            if url is None:
                out.append('<span class="ex-inline-image-placeholder">%s</span>' % esc(path))
            else:
                out.append('<img class="ex-inline-image" src="%s" alt="%s">' %
                           (esc(url), esc(image.group(1))))
        end = found.end()
    out.append(inline(text[end:], force_breakable=True))
    return "".join(out)


def _ex_inline(text, ctx):
    """Exercise prose uses the document's full inline/bidi dialect.

    Each line made solely of target-language marks is a block, as the same
    mark is in an ordinary Markdown paragraph. A cell may contain several
    such lines, separated by ⏎, and a mark may itself contain ⏎. Only breaks
    outside marks separate blocks; breaks inside a mark stay in its RTL run.
    """
    source = str(text or "")
    if not cur_lang().rtl:
        return _ex_inline_text(source, ctx)

    def only_target_marks(line):
        matches = list(tl_re().finditer(line))
        if not matches:
            return False
        end = 0
        for mark in matches:
            if line[end:mark.start()].strip():
                return False
            end = mark.end()
        return not line[end:].strip()

    def rendered_line(line):
        content = _ex_inline_text(line, ctx)
        if only_target_marks(line):
            return '<span class="ex-target-block"%s>%s</span>' % (_dir_lang(), content)
        return '<span class="ex-field-line">%s</span>' % (content or '&nbsp;')

    # Split the explicit line breaks that are outside marks. The parser uses
    # ⏎ for both a field's source lines and a break inside an opaque {tl}
    # mark; splitting the latter would lose the mark's direction and style.
    lines = [""]
    end = 0
    for mark in tl_re().finditer(source):
        outside = source[end:mark.start()].split('⏎')
        lines[-1] += outside[0]
        lines.extend(outside[1:])
        lines[-1] += mark.group(0)
        end = mark.end()
    outside = source[end:].split('⏎')
    lines[-1] += outside[0]
    lines.extend(outside[1:])
    if len(lines) > 1 and any(only_target_marks(line) for line in lines):
        return ''.join(rendered_line(line) for line in lines)
    if only_target_marks(source):
        return rendered_line(source)
    return _ex_inline_text(source, ctx)


def _ex_prompt(text, ctx):
    lines = prompt_lines(text)
    target_lines = [cur_lang().rtl and is_target_line("".join(s for s, _ in line))
                    for line in lines]

    def render(line):
        return "".join('<span class="ex-no-bold">%s</span>' % _ex_inline_text(span, ctx)
                       if regular else _ex_inline_text(span, ctx)
                       for span, regular in line)

    if len(lines) == 1 and not target_lines[0]:
        return render(lines[0])
    if not any(target_lines):
        return "<br>".join(render(line) for line in lines)
    return "".join(
        '<span class="ex-target-block"%s>%s</span>' % (_dir_lang(), render(line))
        if target else '<span class="ex-field-line">%s</span>' % (render(line) or "&nbsp;")
        for line, target in zip(lines, target_lines))


def _ex_explanations(b, preview, ctx):
    """Render the author explanations without choosing a result server-side.

    ``explanation-correct`` is also the neutral explanation when it is the
    only text supplied.  As soon as an incorrect explanation exists, the two
    fields become result-specific; either side may then be empty.  The old
    single ``explanation`` field remains readable and follows the new neutral
    rule, so existing documents do not lose their prose.
    """
    fields = b["fields"]
    ckey = "explanation-correct" if fields.get("explanation-correct") else "explanation"
    correct = fields.get(ckey, "")
    incorrect = fields.get("explanation-incorrect", "")
    if correct:
        with _field_at(ckey):
            correct_html = _ex_inline(correct, ctx)
    if not incorrect:
        if not correct:
            return ""
        return ('<div class="ex-explanation ex-explanation-neutral"%s>%s</div>'
                % ("" if preview else " hidden", correct_html))
    out = []
    if correct:
        out.append('<div class="ex-explanation ex-explanation-result" '
                   'data-explanation-for="correct"%s>%s</div>'
                   % ("" if preview else " hidden", correct_html))
    with _field_at("explanation-incorrect"):
        out.append('<div class="ex-explanation ex-explanation-result" '
                   'data-explanation-for="incorrect" hidden>%s</div>'
                   % _ex_inline(incorrect, ctx))
    return "".join(out)


def _ex_direction(fields):
    direction = (fields.get("content-direction") or "").lower()
    if direction == "target":
        return _dir_lang()
    if direction in ("rtl", "ltr"):
        return ' dir="%s"' % direction
    return ""


def _ex_key(text):
    """A BLOCK'S TEXT, AS ITS IDENTITY.  A block used to be known by the row
    it was written on alone (`i0`, `p3`), and judging compared those rows --
    so a sentence with two "the" to place, two blanks that take the same
    word, or two words sharing one translation was marked WRONG for putting
    the right word in the right place, because it was the other row's copy
    of it.  This travels beside the row (`data-key`, `data-answer-key`) and
    decides; the row stays as it was, for what is judged by rendered HTML
    written before this existed.

    A short digest rather than the text itself: it goes into an attribute
    and, for a sequence, into a comma-separated list of them, and a text
    with a quote or a comma in it would have to be spelt around twice.  The
    text is normalised first (one space between words, NFC), so a block
    rewrapped in the source keeps the identity it had."""
    norm = unicodedata.normalize("NFC", re.sub(r"\s+", " ", str(text or "")).strip())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:10]


def _ex_item(text, item_id, ctx, extra="", arrows=False):
    """One block the learner moves.

    A BOX THAT IS PUT IN ORDER CARRIES ITS OWN TWO ARROWS (`arrows`), which
    move it one place earlier or later.  Dragging is what a mouse does best
    and what a touch screen does worst -- a drag that the page never sees as
    one leaves the box where it was, or drops it at the end -- so the arrows
    are the way through on a phone, and the way through for anybody working
    from the keyboard.  They are drawn inside the box, which is why a box
    with arrows is a `div` and not a `button`: a button cannot hold buttons.
    Its role and its tabindex give it back what the `button` gave it, and
    app.js turns Enter and Space on it into the click it used to make.

    Which arrow points which way is the sequence's business, not the box's
    (app.css): up and down in a list, left and right in a line of chunks,
    and the other way round in a line that runs right to left."""
    if not arrows:
        return ('<button type="button" class="ex-item" draggable="true" '
                'data-item="%s" data-key="%s"%s><span>%s</span></button>'
                % (esc(item_id), _ex_key(text), extra, _ex_inline(text, ctx)))
    return ('<div class="ex-item" role="button" tabindex="0" draggable="true" '
            'data-item="%s" data-key="%s"%s>%s<span>%s</span>%s</div>'
            % (esc(item_id), _ex_key(text), extra, _ex_move("earlier"),
               _ex_inline(text, ctx), _ex_move("later")))


def _ex_move(way):
    """One of a box's two arrows.  The glyph is the stylesheet's (the
    sequence knows its own axis and direction); the label is the meaning,
    which is the same whichever way the arrow ends up pointing."""
    return ('<button type="button" class="ex-move" data-move="%s" '
            'aria-label="Move %s" title="Move %s"></button>' % (way, way, way))


def _render_exercise_choice(b, preview, ctx):
    subtype, mode, items = b["subtype"], b["mode"], b["items"]
    multiple = mode == "multiple"
    if mode == "boolean":
        labels = ("Yes", "No") if subtype == "yes-no" else ("True", "False")
        vals = tuple(x.lower() for x in labels)
        groups = []
        for i, item in enumerate(items):
            opts = []
            for label, value in zip(labels, vals):
                correct = value == item["answer"]
                cls = " selected answer-correct" if preview and correct else ""
                opts.append('<button type="button" class="ex-option%s" '
                            'data-value="%s" data-correct="%d" aria-pressed="%s">%s</button>'
                            % (cls, value, correct, "true" if preview and correct else "false", label))
            with _row_at(i):
                question = _ex_inline(item["left"], ctx)
            groups.append('<div class="ex-choice-group" data-choice="single">'
                          '<div class="ex-question">%s</div><div class="ex-options">%s</div></div>'
                          % (question, "".join(opts)))
        return "".join(groups)

    classes = " ex-segments" if subtype == "incorrect-part" else ""
    opts = []
    for i, item in enumerate(items):
        correct = bool(item["correct"])
        cls = " selected answer-correct" if preview and correct else ""
        with _row_at(i):
            text = _ex_inline(item["text"], ctx)
        opts.append('<button type="button" class="ex-option%s" data-value="o%d" '
                    'data-correct="%d" aria-pressed="%s">%s</button>'
                    % (cls, i, correct, "true" if preview and correct else "false", text))
    return ('<div class="ex-choice-group%s" data-choice="%s"><div class="ex-options">%s</div></div>'
            % (classes, "multiple" if multiple else "single", "".join(opts)))


def _render_exercise_placement(b, preview, ctx):
    items = list(enumerate(b["items"]))
    if b["mode"] == "fill":
        by_slot = {x["mark"]: (i, x) for i, x in items if x["mark"]}
        text = b["fields"].get("text", "")
        parts = mdparser.SLOT_SPLIT_RE.split(text)
        sentence = []
        used = set()
        for part in parts:
            m = mdparser.SLOT_RE.fullmatch(part)
            if not m:
                with _field_at("text"):
                    sentence.append(_ex_inline(part, ctx))
                continue
            slot = m.group(1)
            idx, item = by_slot.get(slot, (-1, {"text": ""}))
            used.add(idx)
            inside = ""
            if preview and idx >= 0:
                with _row_at(idx):
                    inside = _ex_item(item["text"], "i%d" % idx, ctx)
            # a slot no item answers (`idx` -1) gets no key: it must match
            # nothing, and an empty text would match an empty block
            answer_key = (' data-answer-key="%s"' % _ex_key(item["text"])) if idx >= 0 else ""
            sentence.append('<span class="ex-blank%s" role="button" tabindex="0" data-drop="slot" data-answer="i%d"%s '
                            'data-slot="%s">%s</span>'
                            % (" answer-correct" if preview else "", idx,
                               answer_key, esc(slot), inside))
        bank = []
        for i, x in items:
            if not preview or i not in used:
                with _row_at(i):
                    bank.append(_ex_item(x["text"], "i%d" % i, ctx))
        # THE SENTENCE IS LAID OUT IN THE LANGUAGE IT IS WRITTEN IN.  A blank
        # after a Persian phrase is drawn to the RIGHT of it in a left-to-right
        # row of boxes, which reads as the blank coming first; a sentence that
        # is the target's throughout (texgen.is_target_line) is laid out in the
        # target's direction, and the blanks fall where they are read.  An
        # explicit `content-direction` is the author's word and is left alone:
        # it already carries the whole body, this one included.
        here = ("" if (b["fields"].get("content-direction") or "").strip()
                else (_dir_lang() if mdparser.is_target_line(text) else ""))
        return ('<div class="ex-fill"%s>%s</div><div class="ex-bank" role="group" tabindex="0" data-bank="1">%s</div>'
                % (here, "".join(sentence), "".join(bank)))

    ordered = sorted(items, key=lambda ix: int(ix[1]["mark"])
                     if str(ix[1]["mark"]).isdigit() else ix[0])
    shown = ordered if preview else items
    expected = ",".join("i%d" % i for i, _ in ordered)
    # the same order spelt by what the blocks SAY, which is what judging
    # goes by: two blocks reading alike are then interchangeable, as they
    # are to the eye (_ex_key)
    expected_keys = ",".join(_ex_key(x["text"]) for _i, x in ordered)
    sequence_class = ("ex-sequence ex-sequence-inline"
                      if b["subtype"] == "construct-sentence"
                      else "ex-sequence")
    # The direction of the answer's wrapping row is separate from the
    # activity body's writing direction. A flex row in RTL starts each new
    # line at the right edge, including the solved preview.
    answer_dir = ""
    if b["subtype"] == "construct-sentence":
        answer_dir = (b["fields"].get("answer-direction") or cur_lang().dir).lower()
    boxes = []
    for i, x in shown:
        with _row_at(i):
            boxes.append(_ex_item(x["text"], "i%d" % i, ctx, arrows=not preview))
    return ('<div class="%s"%s role="group" tabindex="0" data-drop="sequence" '
            'data-answer="%s" data-answer-keys="%s">%s</div>'
            % (sequence_class, ' dir="%s"' % answer_dir if answer_dir else "", expected,
               expected_keys, "".join(boxes)))


def _render_exercise_matching(b, preview, ctx):
    left, bank = [], []
    direction = b["fields"].get("direction", "").lower()
    reverse = direction in ("translation-to-target", "definition-to-word")
    for i, item in enumerate(b["items"]):
        first, second = ((item["right"], item["left"]) if reverse
                         else (item["left"], item["right"]))
        # the row's left side is written before its right, whichever the
        # page shows first
        with _row_at(i, 1 if reverse else 0):
            shown = _ex_inline(first, ctx)
        inside = ""
        with _row_at(i, 0 if reverse else 1):
            if preview:
                inside = _ex_item(second, "p%d" % i, ctx)
            else:
                bank.append(_ex_item(second, "p%d" % i, ctx))
        left.append('<div class="ex-pair-row"><div class="ex-pair-left">%s</div>'
                    '<div class="ex-match-drop%s" role="button" tabindex="0" data-drop="match" '
                    'data-answer="p%d" data-answer-key="%s">%s</div></div>'
                    % (shown, " answer-correct" if preview else "", i,
                       _ex_key(second), inside))
    return ('<div class="ex-pairs"%s>%s</div><div class="ex-bank" role="group" tabindex="0" data-bank="1">%s</div>'
            % ((' data-direction="%s"' % esc(direction)) if direction else "",
               "".join(left), "".join(bank)))


def _card_style(fields, key):
    secondary = key in ("front-secondary", "back-secondary", "reading",
                        "transliteration", "context", "notes", "source",
                        "opposite-reading", "opposite-transliteration")
    default_size = 88 if secondary else 120
    try:
        size = max(50, min(250, int(fields.get(key + "-size", default_size)
                                    or default_size)))
    except ValueError:
        size = default_size
    shade = (fields.get(key + "-shade") or ("subdued" if secondary else "primary")).lower()
    colours = {"primary": "var(--ink)", "subdued": "var(--graytx)",
               "muted": "color-mix(in srgb,var(--graytx) 72%,transparent)",
               "accent": "var(--accent)"}
    colour = colours.get(shade, shade if re.fullmatch(r"#[0-9a-f]{6}", shade) else colours["primary"])
    return ' style="font-size:%d%%;color:%s"' % (size, esc(colour))


def _card_field(fields, key, ctx, cls="", extra=False):
    text = fields.get(key, "")
    if not text:
        return ""
    if not cls and key in ("reading", "transliteration", "context", "notes",
                           "source", "opposite-reading", "opposite-transliteration"):
        cls = "secondary"
    if key in ("transliteration", "opposite-transliteration"):
        cls += " ex-card-transliteration"
    with _field_at(key):
        inner = _ex_inline(text, ctx)
    # A FIELD THE DRAW MOVES says so (`extra`): app.js drawFirstSide looks for data-extra
    return '<div class="ex-card-field %s"%s%s>%s</div>' % (
        cls, _card_style(fields, key), ' data-extra="%s"' % key if extra else "", inner)


def _card_image(fields, key, ctx):
    path = fields.get(key, "")
    if not path or not mdparser.IMAGE_PATH_RE.match(path):
        return ""
    url = _asset_url(ctx, path + ".svg" if path.lower().endswith(".pdf") else path)
    if url is None:
        return '<span class="ex-card-image-placeholder">%s</span>' % esc(path)
    return '<img class="ex-card-image" src="%s" alt="">' % esc(url)


def _ex_image(fields, key, ctx, cls, hidden):
    """`image: images/map.png` on any exercise but a flashcard: the picture
    that goes with the question, and `image-answer`, the one shown once it
    has been answered.  Both are drawn the way a card's picture is (a `.pdf`
    through its `.pdf.svg` twin), so a deck serves them from its own folder
    and the editor's preview from the document's."""
    pic = mdparser.exercise_image(fields.get(key, ""))
    if not pic:
        return ""
    url = _asset_url(ctx, pic["path"] + ".svg" if pic["path"].lower().endswith(".pdf")
                     else pic["path"])
    shut = " hidden" if hidden else ""
    where = "%s align-%s" % (cls, pic["align"])
    if url is None:
        return ('<div class="ex-image %s"%s><span class="ex-image-placeholder">%s</span></div>'
                % (where, shut, esc(pic["path"])))
    # an exercise's picture often IS its question, so it is announced rather
    # than passed over the way a card's decorative one is
    alt = "Picture shown with the answer" if key == "image-answer" else "Picture with the question"
    # the width is a share of the column, as a figure's is, and the two
    # renderers put the picture on the same side of it (texgen._ex_image)
    return ('<div class="ex-image %s"%s><img src="%s" alt="%s" style="width:%d%%"></div>'
            % (where, shut, esc(url), alt, pic["width"]))


def _ex_audio(fields, key, ctx, cls, hidden):
    """`audio: audio/question.mp3` on any exercise but a flashcard: the
    recording that goes with the question, and `audio-answer`, the one heard
    once it has been answered.  The picture pair's twins, field for field:
    the same two places, the same rule for holding one back, the same share
    of the column and the same side of it (_ex_image).

    A PLAYER WITH ITS CONTROLS, not a card's bare 🔊.  An exercise's
    recording often IS its question -- listened to again, wound back, stopped
    -- while a card's is one word played once.  A clip becomes a media
    fragment, as a recording line's does (_render_audio), and stopping at its
    end is the page script's business (app.js watchClipEnd, which finds this
    box the way it finds a figure).
    """
    rec = mdparser.exercise_audio(fields.get(key, ""))
    if not rec:
        return ""
    url = _asset_url(ctx, rec["path"])
    shut = " hidden" if hidden else ""
    where = "%s align-%s" % (cls, rec["align"])
    if url is None:    # an unsaved document: the file has no URL yet
        return ('<div class="ex-audio %s"%s><span class="ex-audio-placeholder">'
                '🔊 <code>%s</code></span></div>' % (where, shut, esc(rec["path"])))
    frag = ""
    if rec["start"] is not None or rec["end"] is not None:
        frag = "#t=%s" % mdparser.clip_seconds(rec["start"] or 0)
        if rec["end"] is not None:
            frag += ",%s" % mdparser.clip_seconds(rec["end"])
    window = "".join(' data-%s="%s"' % (k, mdparser.clip_seconds(v))
                     for k, v in (("start", rec["start"]), ("end", rec["end"]))
                     if v is not None)
    label = ("Recording played with the answer" if key == "audio-answer"
             else "Recording with the question")
    return ('<div class="ex-audio %s"%s%s><audio controls preload="metadata" '
            'src="%s" aria-label="%s" style="width:%d%%"></audio></div>'
            % (where, shut, window, esc(url + frag),
               label, rec["width"]))


def _card_audio(fields, key, ctx):
    """`front-audio: audio/word.mp3` -> a play button over a hidden
    <audio> (no controls: the card is small, and a click on the button,
    unlike one anywhere else on the card, does not flip it)."""
    path = fields.get(key, "")
    if not path or not mdparser.AUDIO_PATH_RE.match(path):
        return ""
    url = _asset_url(ctx, path)
    if url is None:
        return ('<span class="ex-card-audio-placeholder">🔊 <code>%s</code></span>'
                % esc(path))
    return ('<span class="ex-card-audio" data-side="%s">'
            '<audio preload="metadata" src="%s"></audio>'
            '<button type="button" class="ex-card-play" '
            'aria-label="Play the recording" title="Play">🔊</button></span>'
            % (key.split("-")[0], esc(url)))


def _card_jolly_field(b, key, cls, ctx, field):
    """A jolly field (mdparser.card_field): inline, exactly as it always
    was, when it is one paragraph of prose; otherwise the page's own
    rendering of what the field says.

    ONE PARAGRAPH THE PAGE DRAWS AS A BLOCK -- target-language text with its
    direction, face, tint or tategaki, a Latin block with its width and
    side, a display line -- is the card's own line still: the card gives it
    its size and its place (app.css).  A FIELD OF BLOCKS -- several of them,
    a table, a list, a box, a figure -- takes the card's width at the page's
    text size instead.

    Either way it is drawn as a box's inside is: the headings unnumbered and
    out of the contents, the figures without a layout index, and nothing
    offered to the page's hover editors, which store's searches skip in step
    (mdparser.card_spans) -- a target-language block offers no word to
    colour on a page either.  Its footnote definitions are already the
    document's (_render_exercise)."""
    if field is None:
        return ""
    how, content, _notes = field
    f = b["fields"]
    if how == "inline":
        with _field_at(key):
            inner = _ex_inline(content, ctx)
        return '<div class="ex-card-field %s"%s>%s</div>' % (
            cls, _card_style(f, key), inner)
    rich = mdparser.card_field_is_rich(content)
    was, muted = ctx.get("in_card"), _FN["muted"]
    ctx["in_card"], _FN["muted"] = True, True
    try:
        inner = render_blocks(content, ctx, inside_box=True)
    finally:
        ctx["in_card"], _FN["muted"] = was, muted
    if not inner:
        return ""
    return '<div class="ex-card-field %s%s"%s>%s</div>' % (
        "ex-card-blocks " if rich else "", cls, _card_style(f, key), inner)


def _render_exercise_flashcard(b, preview, ctx, cards=None):
    f = b["fields"]
    kind = (f.get("card-type") or "vocab").lower()
    direction = (f.get("direction") or "forward").strip().lower()
    # THE EXAMPLE, THE NOTES AND THE SOURCE GO ON THE ANSWER (mdparser.card_extras).
    # A both-random card's are marked, for the page's draw to move with it
    # (app.js drawFirstSide); no other card carries the mark.
    word, meaning = mdparser.card_extras(f)
    extras = lambda keys: "".join(_card_field(f, k, ctx, extra=direction == "both-random")
                                  for k in keys)
    # within a side: the picture, the recording, then the text fields
    if kind == "jolly":
        cards = cards or {}
        front = (_card_jolly_field(b, "front-primary", "primary", ctx, cards.get("front-primary"))
                 + _card_jolly_field(b, "front-secondary", "secondary", ctx, cards.get("front-secondary")))
        back = (_card_jolly_field(b, "back-primary", "primary", ctx, cards.get("back-primary"))
                + _card_jolly_field(b, "back-secondary", "secondary", ctx, cards.get("back-secondary")))
    elif kind == "opposites":
        front = (_card_image(f, "front-image", ctx) + _card_audio(f, "front-audio", ctx)
                 + _card_field(f, "target", ctx, "primary")
                 + _card_field(f, "reading", ctx) + _card_field(f, "transliteration", ctx)
                 + extras(word))
        back = (_card_image(f, "back-image", ctx) + _card_audio(f, "back-audio", ctx)
                + _card_field(f, "opposite", ctx, "primary")
                + _card_field(f, "opposite-reading", ctx) + _card_field(f, "opposite-transliteration", ctx)
                + extras(meaning))
    else:
        front = ((_card_field(f, "front", ctx, "primary") or
                  (_card_field(f, "target", ctx, "primary") + _card_field(f, "reading", ctx)
                   + _card_field(f, "transliteration", ctx))) + extras(word))
        back = (_card_field(f, "back", ctx, "primary") or
                (_card_field(f, "meaning", ctx, "primary") + extras(meaning)))
        front = _card_image(f, "front-image", ctx) + _card_audio(f, "front-audio", ctx) + front
        back = _card_image(f, "back-image", ctx) + _card_audio(f, "back-audio", ctx) + back
    if direction == "reverse":
        front, back = back, front
    # `both-random` is drawn where the card is shown (app.js drawFirstSide):
    # a side picked here would be frozen in an export, a study pack and the
    # cached cram page.  `both-repeat` says so in the head (_card_note).
    first = ' data-first="random"' if direction == "both-random" else ""
    # not a <button>: a side may hold a table, a link, a player -- none of
    # which may sit inside one.  app.js flips it on a click anywhere but
    # on such a control, and on Enter/Space when the card has the focus.
    return ('<div class="ex-flashcard%s" role="button" tabindex="0" '
            'data-card-type="%s"%s aria-label="Flip flashcard" aria-pressed="%s">'
            '<div class="ex-card-front">%s</div>'
            '<div class="ex-card-back"%s>%s</div>'
            '<small class="ex-card-hint">%s</small></div>'
            % (" flipped" if preview else "", esc(kind), first,
               "true" if preview else "false", front,
               "" if preview else " hidden", back,
               "front and back shown in preview" if preview else "tap to reveal"))


def _render_exercise_chain(b, preview, ctx):
    """A FOLLOW-UP'S BODY (a0.5.4): the strip that says where the learner is, then every step drawn exactly as its type is
    drawn anywhere else -- the same markup, so everything an exercise does on a page comes with it -- each with its own
    bar (Check step or Show answer, its result, Next step).  app.js (bindChain) shows one step at a time and folds the
    older ones; drawn here whole, a page with no script shows every step."""
    steps = b["steps"]
    n = len(steps)
    dots = "".join('<li class="ex-dot" data-dot="%d">%d</li>' % (k, k) for k in range(1, n + 1))
    out = ['<div class="ex-strip"><span class="ex-strip-say" role="status">Step 1 of %d</span>'
           '<ol class="ex-dots" aria-hidden="true">%s</ol></div>' % (n, dots),
           '<div class="ex-steps"><details class="ex-earlier" hidden><summary>Earlier steps '
           '(<span class="ex-earlier-n">0</span>)</summary><div class="ex-earlier-body"></div></details>']
    was_block, was_chain = _EX_ORDER["block"], ctx.get("in_chain")
    ctx["in_chain"] = True
    try:
        for k, step in enumerate(steps, 1):
            # the runs of a step are numbered with the chain's own, in the order they are written
            _EX_ORDER["block"] = step
            drawn = _draw_exercise(step, ctx)
            card = step["primitive"] == "flashcard"
            check = ('<button type="button" class="btn ex-step-show">Show answer</button>' if card else
                     '<button type="button" class="btn ex-step-check">Check step</button>')
            more = ('<button type="button" class="btn primary ex-step-next" hidden>Next step</button>'
                    if k < n else "")
            out.append('<div class="ex-step" data-step="%d" data-kind="%s" tabindex="-1">'
                       '<p class="ex-step-no">Step %d of %d</p>%s'
                       '<div class="ex-step-bar">%s<span class="ex-step-result" role="status"></span>%s</div></div>'
                       % (k, "card" if card else "scored", k, n, drawn, check, more))
    finally:
        _EX_ORDER["block"], ctx["in_chain"] = was_block, was_chain
    out.append('</div><p class="ex-chain-result" role="status" hidden></p>')
    return "".join(out)


def _card_note(b, ctx):
    """What a `both-repeat` card says beside its kicker: that a deck asks
    both sides.  Only where the studio draws it: not in a deck, which asks
    them, nor in an exported page, which has no deck to go to."""
    if (b["primitive"] != "flashcard" or b["errors"] or ctx.get("in_deck")
            or ctx.get("export")
            or (b["fields"].get("direction") or "").strip().lower() != "both-repeat"):
        return ""
    return ('<span class="ex-card-note" dir="ltr">When exported to a deck, both '
            'sides will be asked.</span>')


def exercise_drawn(b):
    """What of an exercise's text the page draws, as (the fields whose text
    it shows, whether it shows the rows): the rest is written and never
    drawn -- a field no renderer reads, a vocab card's `target` under its
    own `front`, the legacy `explanation` beside an `explanation-correct`,
    and every row, sentence and card field of an exercise that needs
    attention, which shows its errors instead.  store skips the rest when it
    counts the words the page offers (store._mask_uncountable); this is the
    list _draw_exercise and its helpers follow, kept beside them."""
    f = b.get("fields") or {}
    keys = {"prompt"}
    keys.add("explanation-correct" if f.get("explanation-correct") else "explanation")
    keys.add("explanation-incorrect")
    if b.get("errors"):
        return keys, False
    # a follow-up draws its own prompt and explanations; each step is an exercise that is walked on its own
    if b.get("primitive") == "chain":
        return keys, False
    if b.get("primitive") == "placement" and b.get("mode") == "fill":
        keys.add("text")
    if b.get("primitive") == "flashcard":
        kind = (f.get("card-type") or "vocab").lower()
        if kind == "jolly":
            keys.update(mdparser.JOLLY_FIELDS)
        elif kind == "opposites":
            keys.update(("target", "reading", "transliteration", "opposite",
                         "opposite-reading", "opposite-transliteration",
                         "notes", "source"))
        else:
            keys.update(("front",) if f.get("front") else
                        ("target", "reading", "transliteration"))
            keys.update(("back",) if f.get("back") else
                        ("meaning", "context", "notes", "source"))
    return keys, True


def _render_exercise(b, ctx):
    """One exercise, its runs numbered in the order they are written
    (_EX_ORDER).  An exercise holds no exercise, but the state is put back
    as it was all the same."""
    was = {k: _EX_ORDER[k] for k in ("on", "at", "runs", "block")}
    _EX_ORDER.update({"on": True, "at": (b.get("_line", 0), 0), "runs": [], "block": b})
    try:
        html = _draw_exercise(b, ctx)
        runs = _EX_ORDER["runs"]
    finally:
        _EX_ORDER.update(was)
    return _number_exercise_runs(html, runs)


def _blocks_in_field(blocks, first):
    """The blocks a `key: |` field is drawn as (mdparser.card_field), each told the line of the DOCUMENT it is on.  They
    were numbered from the field's own first line, and a block tagged with that number (data-src-line) sent the editor
    to the wrong place: a drawing's pencil rewrote the lines at the top of the document, the front matter's among
    them.  A drawing has its place, which is all the pencil needs (the editor reopens it indented as it was and
    fenced as it was); a block that is anything else is left untagged, the exercise's own tag standing for it."""
    for b in blocks:
        if b["type"] == "latex" and first is not None and b.get("_line") is not None:
            b["_line"] += first
            if b.get("_end_line") is not None:
                b["_end_line"] += first
        else:
            b.pop("_line", None)
    return blocks


def _draw_exercise(b, ctx):
    preview = bool(ctx.get("editor_preview"))
    ctx["exercise"] += 1
    number = ctx["exercise"]
    # a follow-up is not itself answered: each of its steps is an exercise of the page
    scored = b["primitive"] not in ("flashcard", "chain") and not b["errors"]
    if scored:
        ctx["scored"] += 1
    attrs = ('data-exercise="%d" data-subtype="%s" data-primitive="%s" '
             'data-scored="%d" data-src-end="%d"%s'
             % (number, esc(b["subtype"]), esc(b["primitive"]), scored,
                b.get("_end_line", b.get("_line", 0)),
                ' data-editor-preview="1"' if preview else ""))
    chain = b["primitive"] == "chain" and not b["errors"]
    if chain:
        attrs += ' data-steps="%d" data-step="1"' % len(b["steps"])
    label = EXERCISE_LABELS.get(b["subtype"], b["subtype"] or "Exercise")
    # a step is edited from its follow-up's form, never on its own, and is not a deck's exercise either
    in_chain = bool(ctx.get("in_chain"))
    edit = ('<button type="button" class="ex-edit" title="Edit this exercise">✎ Edit</button>'
            if preview and not ctx.get("exercise_nested") and not in_chain else "")
    # a boxed exercise is copied too: decks.exercise_blocks numbers it in
    # the same render order as data-exercise, so its ordinal finds it.
    # One with errors gets none: a deck always refuses it
    to_deck = ('<button type="button" class="ex-to-deck" '
               'title="Copy this exercise into an exercise deck">+ Deck</button>'
               if ctx.get("deck_button") and not preview and not b["errors"] and not in_chain else "")
    # the author's look at the whole chain, in the editor's preview and a solved view: every step unfolded, nothing checked
    show_all = ('<button type="button" class="ex-showall" aria-pressed="false" '
                'title="Unfold every step, to look the chain over">Show every step</button>'
                if chain and preview and not in_chain else "")
    # A FLASHCARD OPENS LARGE, over the page (app.js openCardZoom): a card
    # is a column wide and its picture is shrunk to fit it, which is what
    # makes a picture card hard to see.  Wherever a card is drawn -- a
    # document, a note, a deck's list, the study page, the editor's preview
    zoom = ('<button type="button" class="ex-card-zoom" '
            'title="Open this card large, over the page">⤢ Enlarge</button>'
            if b["primitive"] == "flashcard" and not b["errors"] else "")
    card_kind = (b["fields"].get("card-type") or "vocab").lower()
    has_translit = (card_kind == "opposites" and
                    (b["fields"].get("transliteration") or
                     b["fields"].get("opposite-transliteration"))) or (
                    card_kind == "vocab" and not b["fields"].get("front") and
                    b["fields"].get("transliteration"))
    translit = ('<button type="button" class="ex-translit-switch" aria-pressed="false"></button>'
                if b["primitive"] == "flashcard" and not b["errors"] and has_translit else "")
    # AND A SEQUENCE SAYS WHETHER IT CAN BE DRAGGED.  Its blocks have arrows
    # (_ex_item), and on a touch screen those are the only thing that works
    # properly -- so dragging starts turned off where the pointer is a finger,
    # and this switch turns it back on (or off on a desktop whose dragging is
    # no better).  It is drawn hidden and app.js shows it, because what it
    # says is what that browser remembers, which no server knows; and it is
    # only ever on an exercise whose blocks have the arrows to fall back on.
    drag = ('<button type="button" class="ex-drag-switch" hidden></button>'
            if b["primitive"] == "placement" and b["mode"] == "order"
            and not preview and not b["errors"] else "")
    head = '<div class="ex-head"><span class="ex-kicker">%s</span>%s%s%s%s%s%s%s</div>' % (
        esc(label), _card_note(b, ctx), drag, translit, zoom, show_all, edit, to_deck)
    cards = None
    if b["primitive"] == "flashcard" and (b["fields"].get("card-type") or "").lower() == "jolly":
        # every note written on the card is known before anything on it (or
        # its prompt) cites one: a card's notes naturally come at its end
        cards, notes = mdparser.card_fields(b, cur_lang().code)
        _FN["defs"].update(notes)
    prompt = b["fields"].get("prompt", "")
    prompt_html = ""
    if prompt:
        with _field_at("prompt"):
            # a prompt of ordinary prose is inline text, exactly as always;
            # one that is a fence on its own (a ::::latex drawing, TO-DO
            # §8.39's L8: "notice how the template setting is relevant also
            # in this case") is not -- card_field already tells the two
            # apart for a jolly card's own fields, by the same rule
            field = mdparser.card_field(b, "prompt", cur_lang().code)
            if field and field[0] == "blocks":
                _FN["defs"].update(field[2])
                prompt_html = '<div class="ex-prompt">%s</div>' % render_blocks(
                    _blocks_in_field(field[1], (b.get("_field_text") or {}).get("prompt")), ctx)
            else:
                prompt_html = '<div class="ex-prompt">%s</div>' % _ex_prompt(prompt, ctx)
    if b["errors"]:
        body = '<div class="ex-invalid"><strong>Exercise needs attention.</strong><ul>%s</ul></div>' % "".join(
            '<li>%s</li>' % esc(e) for e in b["errors"])
    elif b["primitive"] == "choice":
        body = _render_exercise_choice(b, preview, ctx)
    elif b["primitive"] == "placement":
        body = _render_exercise_placement(b, preview, ctx)
    elif b["primitive"] == "matching":
        body = _render_exercise_matching(b, preview, ctx)
    elif b["primitive"] == "chain":
        body = _render_exercise_chain(b, preview, ctx)
    else:
        body = _render_exercise_flashcard(b, preview, ctx, cards)
    cls = "exercise" + (" correct" if preview and scored else "") + (" ex-chain" if chain else "")
    # the question's picture and recording between the prompt and the body;
    # the answer's above the explanations, and shown with them (app.js
    # judge(), which the study page drives too) once the exercise has been
    # answered either way.  Sound and picture are the same pair twice over:
    # what holds for one holds for the other, here and everywhere after.
    card = b["primitive"] == "flashcard"
    shown = (_ex_image(b["fields"], "image", ctx, "ex-image-prompt", False) +
             _ex_audio(b["fields"], "audio", ctx, "ex-audio-prompt", False)) \
        if not card else ""
    answer = (_ex_image(b["fields"], "image-answer", ctx, "ex-image-answer",
                        not preview) +
              _ex_audio(b["fields"], "audio-answer", ctx, "ex-audio-answer",
                        not preview)) if not card else ""
    return '<section class="%s" %s>%s%s%s<div class="ex-body"%s>%s</div>%s%s</section>' % (
        cls, attrs, head, prompt_html, shown, _ex_direction(b["fields"]), body,
        answer, _ex_explanations(b, preview, ctx))


# appends at the end of the first opening tag: attribute order elsewhere
# stays untouched (`>` inside attribute values is always &gt;-escaped)
_FIRST_TAG_RE = re.compile(r"^(<[a-z][^>]*)>")


def render_blocks(blocks, ctx, inside_box=False):
    out = []
    card = ctx.get("in_card")
    for b in blocks:
        t = b["type"]
        pre_len = len(out)
        # a heading on a flashcard is a label on the card, not a part of
        # the document: no number, no anchor, no contents entry
        if card and t in ("section", "subsection"):
            tag = "h2" if t == "section" else "h3"
            out.append('<%s class="%s">%s</%s>' % (tag, t, inline(b["text"]), tag))
        elif card and t == "exercise":
            # mdparser refuses a card holding one; drawn here, it would
            # also renumber every exercise after it
            continue
        elif t == "section":
            ctx["sec"] += 1
            sid = "sec-%d" % ctx["sec"]
            txt = inline(b["text"])
            ctx["toc"].append(("section", sid, txt, str(ctx["sec"])))
            out.append('<h2 class="section" id="%s">'
                       '<span class="secnum">%d.</span> %s</h2>'
                       % (sid, ctx["sec"], txt))
        elif t == "subsection":
            ctx["sub"] += 1
            sid = "sub-%d" % ctx["sub"]
            txt = inline(b["text"])
            ctx["toc"].append(("subsection", sid, txt, ""))
            out.append('<h3 class="subsection" id="%s">%s</h3>' % (sid, txt))
        elif t == "voce":
            anchor = ""
            if not card:
                ctx["voce"] += 1
                sid = "voce-%d" % ctx["voce"]
                anchor = ' id="%s"' % sid
                ctx["toc"].append(("voce", sid, esc(b["fa"]),
                                   inline(b["translit"])))
            # the lemma is a colourable run like any other: it counts an
            # occurrence (before translit/etym, matching source order) and
            # may carry a colour from `## [آهسته]{teal} | …`
            pick = ""
            if not card:
                pick = ' data-fa="%s" data-occ="%d"' % (esc(b["fa"]), _next_occ(b["fa"]))
            raw_col = b.get("fa_color")
            cls, style, data = "", "", ""
            if raw_col and HEX_RE.match(raw_col):
                cls = " fac"
                style = ' style="color:%s"' % raw_col
                data = ' data-color="%s"' % raw_col
            elif raw_col in PALETTE:
                cls = " fac fac-%s" % raw_col
                data = ' data-color="%s"' % raw_col
            kana = b.get("kana") or ""
            kana_html = ('<div class="voce-kana"%s>%s</div>'
                         % (_dir_lang(), esc(kana)) if kana else "")
            head_html = esc(b["fa"])
            if b.get("fa_segments"):
                bits = []
                for text_, colour_ in b["fa_segments"]:
                    body_ = esc(text_)
                    if not colour_:
                        bits.append(body_)
                    elif colour_.startswith("#"):
                        bits.append('<span class="seg-colour fac" data-color="%s" '
                                    'style="color:%s">%s</span>'
                                    % (colour_, colour_, body_))
                    else:
                        bits.append('<span class="seg-colour fac fac-%s" '
                                    'data-color="%s">%s</span>'
                                    % (colour_, colour_, body_))
                head_html = "".join(bits)
                cls += " segmented-colour-run"
            out.append(
                '<section class="voce"%s>'
                '<div class="voce-head">'
                '<div class="voce-fa%s"%s%s%s%s>%s</div>'
                '<div class="voce-side">'
                '%s'
                '<div class="voce-translit">%s</div>'
                '<div class="voce-etym">%s</div>'
                '</div></div></section>'
                % (anchor, cls, _dir_lang(), pick, data, style,
                   head_html, kana_html, inline(b["translit"]),
                   inline(b["etym"])))
        elif t == "para":
            txt = b["text"].strip()
            la_whole = LA_RE.fullmatch(txt)
            tl_whole = tl_re().fullmatch(txt)
            tl_nested = target_fullmatch(txt) if tl_whole is None else None
            if la_whole:
                a = parse_la_attrs(la_whole.group(2))
                ml = max(-25.0, min(float(a["offset"]), 125.0))
                style = ("" if a["width"] == 100 and a["offset"] == 0 else
                         ' style="width:%d%%;margin-left:%.2f%%"'
                         % (a["width"], ml))
                bgc = " rtl-bg-%s" % a["bg"] if a["bg"] else ""
                src = "" if card else ' data-la-src="%s"' % esc(la_whole.group(1))
                out.append(
                    '<div class="la-par align-%s%s"%s '
                    'data-la-align="%s" data-la-bg="%s" data-la-width="%d" '
                    'data-la-offset="%d"%s>%s</div>'
                    % (a["align"], bgc, src,
                       a["align"], a["bg"] or "", a["width"], a["offset"],
                       style, inline(la_whole.group(1))))
            elif _is_pure_fa_paragraph(txt):
                out.append('<p class="fa-display">%s</p>'
                           % _fa_span(txt, breakable=True))
            elif tl_whole or tl_nested or is_fa_only_paragraph(txt):
                content = (tl_whole.group(1) if tl_whole else
                           (tl_nested.content if tl_nested else txt))
                kind = "mark" if tl_whole or tl_nested else "auto"
                attrs = parse_tl_attrs(tl_whole.group(2) if tl_whole else
                                       (tl_nested.attrs if tl_nested else ""))
                cls, data, style = _tl_style_bits(attrs)
                src = ("" if card else
                       ' data-tl-kind="%s" data-tl-src="%s"%s data-rtl-kind="%s" data-rtl-src="%s"'
                       % (kind, esc(content), _tl_occ(kind, content), kind, esc(content)))
                out.append('<p class="fa-par%s"%s%s%s%s>%s</p>'
                           % (cls, _dir_lang(), src, data, style,
                              (_rtl_segmented_html(content)
                               if list(segmented_runs(content)) else _rtl_html(content))))
            else:
                out.append("<p>%s</p>" % inline(b["text"]))
        elif t in ("list", "enum"):
            out.append(_render_list(b, ordered=(t == "enum")))
        elif t == "table":
            out.append(_render_table(b))
        elif t == "image":
            out.append(_render_image(b, ctx))
        elif t == "audio":
            out.append(_render_audio(b, ctx))
        elif t == "video":
            out.append(_render_video(b, ctx))
        elif t == "box":
            out.append(_render_box(b, ctx))
        elif t == "exercise":
            was_nested = ctx.get("exercise_nested", False)
            ctx["exercise_nested"] = inside_box
            out.append(_render_exercise(b, ctx))
            ctx["exercise_nested"] = was_nested
        elif t == "latex":
            out.append(_render_latex(b, ctx))
        elif t == "math":
            # a <div> and not a <p>: it is a block of its own, and the
            # opening tag is a real one so the editor's line anchor lands
            # on it (below).  data-math-src is what the hover pencil reads
            # to open the formula again in the editor.
            tex = b.get("tex", "")
            out.append('<div class="math mathblock" data-tex="%s" '
                       'data-math-kind="block" data-math-src="%s">%s</div>'
                       % (esc(tex), esc(tex), esc(tex)))
        # tag every top-level block with the source line it starts on —
        # the editor's alignment engine anchors the two panes on these
        if (not inside_box and len(out) > pre_len
                and b.get("_line") is not None):
            out[-1] = _FIRST_TAG_RE.sub(
                r'\1 data-src-line="%d">' % b["_line"], out[-1], count=1)
    return "\n".join(out)


# ----------------------------------------------------------------------
# whole document
# ----------------------------------------------------------------------

def _titleblock(fm):
    if not fm.get("title"):
        return ""
    out = ['<header class="titleblock">',
           "<h1>%s</h1>" % inline(fm["title"])]
    if fm.get("subtitle"):
        out.append('<p class="subtitle">%s</p>' % inline(fm["subtitle"]))
    out.append('<div class="titlerule"></div>')
    if fm.get("note"):
        out.append('<p class="tnote">%s</p>' % inline(fm["note"]))
    out.append("</header>")
    return "\n".join(out)


def colophon_html(L):
    """The colophon names the target language and its web face; the
    direction sentence is only for right-to-left scripts.  Persian keeps
    its historical sentence, byte for byte: the Persian example must
    render the same HTML as before languages were declared
    (docs/languages.md, 11)."""
    if L.code == languages.DEFAULT:
        about = ("Il persiano usa <em>Vazirmatn</em> di Saber Rastikerdar "
                 "(SIL OFL 1.1).")
    else:
        face = (L.fonts.get("css_main") or "serif").split(",")[0].strip("'\" ")
        about = ("La scrittura della lingua di studio (%s) usa <em>%s</em>."
                 % (esc(L.name.lower()), esc(face)))
    if L.rtl:
        about += (" Nel PDF la direzione destra→sinistra è ottenuta con i "
                  "primitivi TeXXeT <code>\\beginR</code>/<code>\\endR</code> e "
                  "verificata glifo per glifo; nella versione web è affidata "
                  "all’algoritmo bidirezionale Unicode del browser.")
    else:
        about += (" Nel PDF ogni stringa nella lingua di studio è verificata "
                  "glifo per glifo.")
    return ('<footer class="colophon"><strong>Nota tecnica.</strong> '
            'Documento generato dalla toolchain <em>exlex</em> '
            '(markdown <span class="arrow">→</span> XeLaTeX / HTML). '
            '%s Testo latino: TeX Gyre Pagella e Heros.</footer>' % about)


COLOPHON = colophon_html(languages.get("fa"))       # the old name


def _toc_html(toc):
    if not toc:
        return ""
    out = ['<nav class="toc-list">']
    for kind, sid, label, extra in toc:
        if kind == "voce":
            out.append('<a class="toc-voce" href="#%s">'
                       '<span class="fa"%s>%s</span>'
                       '<span class="toc-tr">%s</span></a>'
                       % (sid, _dir_lang(), label, extra))
        elif kind == "section":
            out.append('<a class="toc-sec" href="#%s">'
                       '<span class="secnum">%s.</span> %s</a>'
                       % (sid, extra, label))
        else:
            out.append('<a class="toc-sub" href="#%s">%s</a>' % (sid, label))
    out.append("</nav>")
    return "\n".join(out)


def _footnote_list():
    """The notes again at the end — useful when printing the web view,
    where a hover cloud cannot be seen."""
    if not _FN["notes"]:
        return ""
    items = "".join('<li id="fnlist-%d" value="%d">%s</li>' % (n, n, body)
                    for n, body in sorted(_FN["notes"]))
    return ('<section class="footnotes"><h4>Note</h4><ol>%s</ol></section>'
            % items)


def target_runs(markdown):
    """Every run of the target language in the source, in order: the
    detected runs of a script language, the marked ones of a Latin
    target (the rule of LATIN_RUN_RE)."""
    latin = is_latin_target()
    # A segmented word is one run for counts and every other nonvisual
    # consumer, not one run per source fragment.  Reduce it locally to the
    # ordinary spelling that the established run detector already knows.
    for node in reversed(list(segmented_runs(markdown))):
        plain = "[%s]{tl}" % node.plain_text if latin else node.plain_text
        markdown = markdown[:node.start] + plain + markdown[node.end:]
    if latin:
        return [m.group(1) for m in LATIN_RUN_RE.finditer(markdown)]
    return run_re().findall(markdown)


def stats(markdown, blocks, target=None):
    """Counts for the library card.  `target` sets the language when the
    caller has not already (store saves without a render)."""
    if target is not None:
        set_target(target)
    L = cur_lang()
    # the name after a link's `doc:` is not the document's text: the page
    # never shows it (it shows the label, or the target's title, drawn
    # uncounted), and a link that spelt a uid, now spelling the name the
    # migration wrote in its place, must leave the card saying what it said
    kept, last = [], 0
    for s, e in sorted((l.target_start, l.target_end) for l in find_doclinks(markdown, L.code)):
        kept += [markdown[last:s], " " * (e - s)]
        last = e
    markdown = "".join(kept) + markdown[last:]
    latin = re.sub("[%s]" % L.chars, " ", markdown) if L.chars else markdown
    return {
        "voci": sum(1 for b in blocks if b["type"] == "voce"),
        "sections": sum(1 for b in blocks if b["type"] == "section"),
        "tables": sum(1 for b in blocks if b["type"] == "table"),
        "fa_runs": len(target_runs(markdown)),
        "words": len(PROSE_WORD_RE.findall(latin)),
        # counted from the source, not from render state: a save without a
        # render (e.g. tag edit, image layout) must not zero the count.
        "footnotes": _count_footnotes(markdown),
        "images": _count_images(blocks),
        "audio": _count_images(blocks, ("audio",)),
    }


def _count_footnotes(markdown):
    # a definition may sit in a box (`> [^x]: …`) or on a flashcard, indented
    body = re.sub(r"(?m)^[ \t>]*\[\^[^\]\s]+\]:.*$", "", markdown)
    return len(FN_INLINE_RE.findall(body)) + len(FN_REF_RE.findall(body))


# ----------------------------------------------------------------------
# gloss harvesting  (فارسی = *translation*)
# ----------------------------------------------------------------------
# The head of a gloss is the target-language text sitting immediately
# before the ` = `: either a marked run (`[تند]{translit:tond}`, with a
# colour, a transliteration and/or a reading) or a bare one.  Surrounding
# `**bold**` is transparent.  For a Latin target only marked heads exist.
#
# The translation is the italic span the authoring rules require after the
# `=`.  Without the italics there is no way to know where a translation
# stops -- in `آهستگی = lentezza, delicatezza` both words are the gloss,
# while in `حرکت آهسته = il rallentatore, nel cinema` only the first is --
# so rather than guess at a clause boundary and quietly produce a wrong
# entry, we take exactly ONE word and mark the entry `guessed`.  The
# glossary then shows that row in red and explains, on hover, that the
# document is missing the italics.  A visibly flagged single word is
# honest; a plausible-looking multi-word guess is not.

_G_ATTRS_RE = re.compile(
    r"^\s*(?:(?:#[0-9A-Fa-f]{6}|[A-Za-z]+)\s+)?((?:translit|kana|reading):.*?)\s*$")

_GLOSS_CACHE = {}


def gloss_re():
    """GLOSS_RE for the current language (the bare alternative is the
    language's run regex; a Latin target has none)."""
    L = cur_lang()
    rx = _GLOSS_CACHE.get(L.code)
    if rx is None:
        bare = ("|(?P<bare>%s)" % L.run_re.pattern) if L.run_re else ""
        rx = re.compile(
            r"(?:\[(?P<mk>[^\[\]]*)\]\{(?P<at>[^{}]*)\}" + bare + ")"
            r"\*{0,2}[ \t]=[ \t]"
            r"(?:\*(?P<tri>[^*\n]+?)\*"
            r"|(?P<trp>[^\s*\[\]]+))")
        _GLOSS_CACHE[L.code] = rx
    return rx


def _gloss_fields(attrs):
    """`{teal kana:かんじ translit:kanji}` -> {"translit": …, "kana": …}."""
    m = _G_ATTRS_RE.match(attrs or "")
    return parse_mark_fields(m.group(1)) if m else {}


def _mark_is_run(attrs):
    """For a Latin target: is `[…]{attrs}` a run mark (not a la block)?"""
    return not re.match(r"\s*(?:la|ltr)\b", attrs or "")


def _gloss_text(text, out):
    """Collect the glosses of one inline string into `out`."""
    if not text or " = " not in text:
        return
    latin = is_latin_target()
    # A segmented head is one flattened word to the glossary too.  Reduce it
    # to the old whole-run spelling locally so the established gloss parser
    # and its validation remain the one implementation.
    for node in reversed(list(segmented_runs(text))):
        marks = dict(node.marks)
        fields = []
        if marks.get("kana"):
            fields.append("kana:" + marks["kana"])
        if marks.get("translit"):
            fields.append("translit:" + marks["translit"])
        replacement = ("[%s]{%s}" % (node.plain_text,
                                      " ".join(fields) if fields else "tl")
                       if fields or latin else node.plain_text)
        text = text[:node.start] + replacement + text[node.end:]
    # a […]{la} block is ordinary markdown inside: unwrap and keep going
    text = LA_RE.sub(lambda m: m.group(1), text)
    if not latin:
        # a […]{tl} block is opaque prose -- never a gloss
        text = tl_re().sub(" ", text)
    for m in gloss_re().finditer(text):
        fa = (m.group("mk") or m.group("bare") or "").strip()
        if not fa:
            continue
        if latin:
            if m.group("mk") is None or not _mark_is_run(m.group("at")):
                continue
        elif not has_script(fa):
            continue
        exact = m.group("tri") is not None
        tr = (m.group("tri") or m.group("trp") or "").strip()
        if exact:
            # an italic span is authored: trust its edges verbatim
            tr = tr.strip()
        else:
            # a lone word scraped off the source still carries whatever
            # punctuation followed it
            tr = tr.strip(" \t,;:.!?)]»…\"'").strip()
        if not tr:
            continue
        fields = _gloss_fields(m.group("at"))
        out.append({"fa": fa,
                    "translit": fields.get("translit", ""),
                    "kana": fields.get("kana", ""),
                    "tr": tr,
                    "exact": exact, "lemma": False})


def _gloss_blocks(blocks, out):
    for b in blocks:
        t = b["type"]
        if t == "voce":
            # a lemma heading carrying `= *…*`: it is printed nowhere, and
            # this is the only reason it was written
            if b.get("gloss"):
                out.append({"fa": (b.get("fa") or "").strip(),
                            "translit": (b.get("translit") or "").strip(),
                            "kana": (b.get("kana") or "").strip(),
                            "tr": b["gloss"].strip(),
                            "exact": True, "lemma": True})
        elif t in ("para", "section", "subsection"):
            _gloss_text(b.get("text", ""), out)
        elif t == "list":
            for _, it in b["items"]:
                _gloss_text(it, out)
        elif t == "table":
            for row in b["rows"]:
                for cell in row:
                    _gloss_text(cell, out)
        elif t == "box":
            _gloss_blocks(b["blocks"], out)


def _translit_index(markdown, blocks):
    """Target text -> (transliteration, reading), from every mark and
    lemma in the file.

    A gloss head often carries no mark of its own (`آهسته برو = …`) while
    the same run is annotated elsewhere; this lets the table fill that in
    instead of showing a blank.
    """
    idx = {}
    for node in segmented_runs(markdown):
        fields = dict(node.marks)
        if node.plain_text and fields:
            cur = idx.setdefault(node.plain_text, {"translit": "", "kana": ""})
            for k in ("translit", "kana"):
                if fields.get(k) and not cur[k]:
                    cur[k] = fields[k]
    for m in TRANSLIT_RE.finditer(markdown):
        fa = m.group(1).strip()
        fields = parse_mark_fields(m.group(3))
        if fa:
            cur = idx.setdefault(fa, {"translit": "", "kana": ""})
            for k in ("translit", "kana"):
                if fields.get(k) and not cur[k]:
                    cur[k] = fields[k]
    for b in blocks:
        if b["type"] == "voce" and b.get("fa"):
            cur = idx.setdefault(b["fa"].strip(), {"translit": "", "kana": ""})
            for k in ("translit", "kana"):
                if b.get(k) and not cur[k]:
                    cur[k] = b[k].strip()
    return idx


def glosses(markdown):
    """Every `فارسی = *translation*` in the file, in document order.

    Returns a list of {fa, kana, translit, tr, guessed, lemma} dicts,
    deduplicated on the whole tuple so a word repeated with the same gloss
    is listed once while a word carrying two genuinely different senses
    keeps both.  `guessed` is True when the source had no italics and the
    translation is therefore just the single word after the `=` — the
    reader is told.  `kana` is empty for every language without a reading.
    """
    fm, blocks = mdparser.parse(markdown)
    set_target(fm.get("target"))
    found = []
    _gloss_blocks(blocks, found)
    for body in (fm.get("_footnotes") or {}).values():
        _gloss_text(body, found)

    idx = _translit_index(markdown, blocks)
    out, seen = [], set()
    for g in found:
        known = idx.get(g["fa"], {})
        if not g["translit"]:
            g["translit"] = known.get("translit", "")
        if not g.get("kana"):
            g["kana"] = known.get("kana", "")
        key = (g["fa"], g["kana"], g["translit"], g["tr"], g.get("lemma"))
        if key in seen:
            continue
        seen.add(key)
        out.append({"fa": g["fa"], "kana": g["kana"], "translit": g["translit"],
                    "tr": g["tr"], "guessed": not g["exact"],
                    "lemma": bool(g.get("lemma"))})
    return out


def _count_images(blocks, kinds=("image", "video")):
    n = 0
    for b in blocks:
        if b["type"] in kinds:
            n += 1
        elif b["type"] == "box":
            n += _count_images(b["blocks"], kinds)
    return n


def render_document(markdown, colophon=True, asset_base=None, docs=None,
                    editor_preview=False, deck_button=False, latex_preview=None,
                    in_deck=False, export=False, latex_defer=False):
    """markdown source -> dict with article html, toc html, meta, stats,
    the target code and the language record the page embeds.

    `asset_base` is the URL prefix under which the document's uploaded
    files are served (e.g. "/media/<doc-id>/"), or a function giving the URL
    of one file's path (`images/cat.png` -> its URL, or None when that one
    has none); without it, images render as placeholders (an unsaved
    document has no file store yet), and so does a file the function gives
    no URL.
    `docs` is store.doc_index(), which resolves `[…](doc:Name)` links to a
    title and a URL; without it every such link is one to a document that
    is not there, so every caller that has a library passes it.
    `deck_button` puts a "+ Deck" button on every exercise (the reading
    view of a document that can be copied from); never in the editor's
    preview, whose exercises are being written, not studied.
    `latex_preview` (TO-DO §8.39's L9) is the SEPARATE question "is a
    drawing made for this call unsaved, so its cache entry should be a
    short-lived preview, not kept": the studio editor's own live preview is
    both this AND `editor_preview` at once, which is why it defaults to
    whatever `editor_preview` is; a deck showing an ALREADY-SAVED exercise
    solved (decks.render_item's `preview`, "show the answer") is
    `editor_preview` alone, its drawings still kept, so it passes this False
    on purpose -- the two must never be conflated into one flag again, the
    way they briefly were (found reviewing this: `render_item(preview=True)`
    stopped showing the solved exercise at all, because `editor_preview`
    had silently become this flag's alone).
    `in_deck` is a deck's own drawing of an exercise: a card that a document
    says will be asked from both sides does not say so there, where it is
    already being asked so.
    `export` is a page made to leave the studio (webexport): it does not
    say so either, since nothing on it goes into a deck.
    `latex_defer` makes no drawing: one not made yet is a placeholder the
    page has made afterwards (see _latex_idx), and "latex_pending" counts them.
    """
    fm, blocks = mdparser.parse(markdown)
    L = set_target(fm.get("target"))
    reset_state(fm.get("_footnotes"))
    if latex_preview is None:
        latex_preview = editor_preview
    latex_preview = bool(latex_preview)
    _LATEX_INLINE_RUN["preview"] = latex_preview
    defer = bool(latex_defer) and bool(LATEX.get("peek")) and not latex_preview
    _LATEX_INLINE_RUN["defer"] = defer
    set_doc_index(docs)
    ctx = {"sec": 0, "sub": 0, "voce": 0, "img": 0, "exercise": 0,
           "scored": 0, "toc": [], "asset_base": asset_base,
           "editor_preview": bool(editor_preview), "latex_preview": latex_preview,
           "deck_button": bool(deck_button) and not editor_preview,
           "in_deck": bool(in_deck), "export": bool(export)}
    title = _titleblock(fm)          # rendered first: it comes first in source
    if LATEX.get("draw_all") and not defer:
        # every drawing the page needs, made side by side before any is shown
        pairs = latex_pairs(blocks, L.code)
        if pairs:
            LATEX["draw_all"](pairs, preview=latex_preview)
        # inline marks (TO-DO §8.39's L8) live in text, not in the block
        # tree, so they are swept from the raw source instead -- a document,
        # every exercise field, a note, wherever `[…]{latex}` can be written
        inline_pairs = inline_latex_pairs(markdown)
        if inline_pairs:
            LATEX["draw_all"](inline_pairs, inline=True, preview=latex_preview)
    body = render_blocks(blocks, ctx)
    article = title + "\n" + body + "\n" + _footnote_list()
    if ctx["scored"] and not editor_preview:
        article += ('\n<section class="exercise-correction" data-exercise-results>'
                    '<button type="button" class="btn primary ex-correct-all">'
                    'Check exercises</button><output class="ex-score" hidden></output>'
                    '</section>')
    if colophon:
        article += "\n" + colophon_html(L)
    return {
        "html": article,
        "toc": _toc_html(ctx["toc"]),
        # HOW MANY EXERCISES CAME OUT, counted while they were drawn.  A page
        # that shows a document without the studio's script -- the bare note
        # page (server.py, page_note) -- would show an exercise that cannot
        # be answered, checked or copied, which is worse than not showing it:
        # the reader would think the note was broken.  So the caller asks
        # this and sends such a note to the full page instead.  It is read
        # off the render and not off the markdown because only the render
        # knows what a block actually became.
        "exercises": ctx["exercise"],
        # the latex blocks that could not be drawn: the PDF and the export
        # say how many (the owner, 2026-09-25)
        "latex_failed": ctx.get("latex_failed", 0) + _LATEX_INLINE_RUN["failed"],
        "latex_pending": _LATEX_INLINE_RUN.get("pending", 0),
        "title": fm.get("title", ""),
        "subtitle": fm.get("subtitle", ""),
        "note": fm.get("note", ""),
        "lang": fm.get("lang", DEFAULT_PROSE),
        "target": L.code,
        "target_error": fm.get("_target_error", ""),
        "lang_record": L.as_json(),
        "stats": stats(markdown, blocks),
    }
