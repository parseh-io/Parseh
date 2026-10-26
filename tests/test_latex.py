# SPDX-License-Identifier: GPL-3.0-or-later
"""LaTeX drawings (TO-DO §8.39): the ::::latex fence, theme names, a rename's
rewrite of the text, and the key a drawing is kept under.  No TeX is run:
what a compile makes is checked by hand (docs/releasing.md).  The themes'
store is redirected to a temporary folder, so config/ is never written."""
import json
import contextlib
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
for folder in (ROOT / "lib", ROOT / "markdown" / "exlex", ROOT / "markdown" / "app"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import latexdraw    # noqa: E402
import latexthemes  # noqa: E402
import mdparser     # noqa: E402
import texgen       # noqa: E402
import htmlgen      # noqa: E402


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.was = latexthemes.STORE, latexdraw.DRAWN
        latexthemes.STORE = os.path.join(self.tmp.name, "config", "latex.json")
        latexdraw.DRAWN = os.path.join(self.tmp.name, "latex")

    def tearDown(self):
        latexthemes.STORE, latexdraw.DRAWN = self.was
        self.tmp.cleanup()


class TheFence(unittest.TestCase):
    def blocks(self, md):
        return [b for b in mdparser.parse(md)[1] if b["type"] == "latex"]

    def test_a_block_with_its_theme_and_layout(self):
        b, = self.blocks("::::latex chemistry {width=45 align=left}\n\\ce{H2O}\n::::\n")
        self.assertEqual((b["theme"], b["tex"], b["align"]), ("chemistry", "\\ce{H2O}", "left"))
        self.assertEqual(b["width"], 45)
        self.assertFalse(b["errors"])

    def test_no_theme_no_width(self):
        b, = self.blocks("::::latex\nx\n::::\n")
        self.assertIsNone(b["theme"] or None)
        self.assertIsNone(b["width"])
        self.assertEqual(b["align"], "center")

    def test_three_colons_inside_do_not_close_it(self):
        b, = self.blocks("::::latex drawing\n\\node {:::};\n:::\n::::\nafter\n")
        self.assertIn(":::", b["tex"])
        self.assertTrue(any(x["type"] == "para" for x in mdparser.parse(
            "::::latex drawing\n:::\n::::\nafter\n")[1]))

    def test_an_unclosed_block_says_so(self):
        b, = self.blocks("::::latex\nx\n")
        self.assertTrue(b["errors"])

    def test_math_is_untouched(self):
        kinds = [b["type"] for b in mdparser.parse(":::math\nx^2\n:::\n")[1]]
        self.assertNotIn("latex", kinds)

    def test_a_card_field_keeps_it_and_the_exercise_goes_on(self):
        md = (":::exercise flashcard\ntype: jolly\nfront: |\n  ::::latex\n  \\ce{H2O}\n  ::::\n"
              "back: water\n:::\n\nafter\n")
        blocks = mdparser.parse(md)[1]
        self.assertTrue(any(b["type"] == "exercise" for b in blocks))
        self.assertEqual([b for b in latexthemes.blocks_in(md)][0]["tex"], "\\ce{H2O}")

    def test_the_light_scanner_finds_a_block_in_a_box(self):
        b, = latexthemes.blocks_in("> ::::latex drawing\n> x\n> ::::\n")
        self.assertEqual((b["theme"], b["tex"], b["closed"]), ("drawing", "x", True))

    def test_a_drawing_in_a_step_of_a_follow_up_has_one_colon_more(self):
        # a0.5.4: a step is one fence deeper, so its drawing is `:::::latex` … `:::::`, closed by its own colons --
        # a `::::` inside it does not end it, and the four-colon block after it is a block of its own
        md = (":::exercise follow-up\n::::exercise single-choice\nprompt: |\n  Which?\n"
              "  :::::latex chemistry {width=40}\n  \\ce{H2O}\n  ::::\n  \\ce{CO2}\n  :::::\n"
              "- [x] a\n- [ ] b\n::::\n:::\n\n::::latex\n$x$\n::::\n")
        deep, plain = latexthemes.blocks_in(md)
        self.assertEqual((deep["theme"], deep["attrs"], deep["tex"], deep["closed"]),
                         ("chemistry", "width=40", "\\ce{H2O}\n::::\n\\ce{CO2}", True))
        self.assertEqual((plain["theme"], plain["tex"], plain["closed"]), ("", "$x$", True))
        self.assertEqual([], deep["errors"])

    def test_the_page_does_not_load_mathjax_for_what_a_deeper_drawing_holds(self):
        import offline
        inside = ("::::exercise single-choice\nprompt: |\n  :::::latex\n  [x^2]{math}\n  :::::\n- [x] a\n- [ ] b\n::::\n")
        self.assertFalse(offline._maths_in(":::exercise follow-up\n" + inside + inside + ":::\n"))
        self.assertTrue(offline._maths_in(":::exercise follow-up\n" + inside + inside + ":::\n\n[y]{math}\n"))

    def test_a_deeper_fence_that_is_never_closed_says_so(self):
        b, = latexthemes.blocks_in(":::::latex\nx\n::::\n")
        self.assertEqual((b["tex"], b["closed"]), ("x\n::::", False))


def _drawn(calls=None, w=99.0):
    def draw(tex, theme, **kw):
        if calls is not None:
            calls.append((tex, theme, sorted(kw)))
        return {"ok": True, "key": "c" * 64, "url": "/latex/%s.svg" % ("c" * 64), "w": w, "h": 20,
                "pdf": "/nowhere/%s.pdf" % ("c" * 64)}
    return draw


def _figure(md, **kw):
    with mock.patch.dict(htmlgen.LATEX, {"draw": _drawn(), "draw_all": None}):
        return htmlgen.render_document(md, **kw)["html"]


class Caption(unittest.TestCase):
    """A latex BLOCK (never the inline mark) may take `caption="…"` in its braces:
    inline markup in double quotes, set under the drawing as a figure's caption is."""

    def blocks(self, md):
        return [b for b in mdparser.parse(md)[1] if b["type"] == "latex"]

    def test_the_braces_take_a_quoted_caption(self):
        b, = self.blocks('::::latex chemistry {width=45 align=left caption="Water forms from hydrogen"}\nx\n::::\n')
        self.assertEqual((b["caption"], b["width"], b["align"], b["theme"]),
                         ("Water forms from hydrogen", 45, "left", "chemistry"))
        self.assertFalse(b["errors"])

    def test_no_caption_is_none_and_the_theme_is_optional(self):
        b, = self.blocks("::::latex {width=45}\nx\n::::\n")
        self.assertEqual(b["caption"], "")
        b, = self.blocks('::::latex {caption="A"}\nx\n::::\n')
        self.assertEqual((b["caption"], b["theme"], b["width"]), ("A", "", None))

    def test_a_caption_may_hold_braces_brackets_and_the_layout_words(self):
        b, = self.blocks('::::latex chem {caption="[x^2]{math} and width=9, a } too" width=30}\nx\n::::\n')
        self.assertEqual(b["caption"], "[x^2]{math} and width=9, a } too")
        self.assertEqual(b["width"], 30, "the words outside the quotes still read")
        self.assertFalse(b["errors"])

    def test_whitespace_is_one_space(self):
        b, = self.blocks('::::latex {caption="  two   words "}\nx\n::::\n')
        self.assertEqual(b["caption"], "two words")

    def test_a_caption_without_quotes_or_with_an_open_one_is_said_not_dropped(self):
        b, = self.blocks("::::latex chem {caption=Water}\nx\n::::\n")
        self.assertTrue(any("double quotes" in e for e in b["errors"]), b["errors"])
        b, = self.blocks('::::latex chem {caption="Water}\nx\n::::\n')
        self.assertTrue(b["errors"], "an open quote is a bad opening line")

    def test_a_caption_on_a_card(self):
        md = (":::exercise flashcard\ntype: jolly\nfront: |\n  ::::latex {caption=\"Water\"}\n  \\ce{H2O}\n  ::::\n"
              "back: water\n:::\n")
        self.assertEqual(latexthemes.blocks_in(md)[0]["attrs"], 'caption="Water"')

    def test_a_caption_never_changes_the_drawing_asked_for(self):
        calls = []
        plain = '::::latex chemistry {width=45}\n\\ce{H2O}\n::::\n'
        said = '::::latex chemistry {width=45 caption="Water"}\n\\ce{H2O}\n::::\n'
        with mock.patch.dict(htmlgen.LATEX, {"draw": _drawn(calls), "draw_all": None}):
            htmlgen.render_document(plain)
            htmlgen.render_document(said)
        self.assertEqual(calls[0], calls[1], "the same (tex, theme) is asked of the drawer, nothing more")
        self.assertEqual(calls[0][:2], ("\\ce{H2O}", "chemistry"))
        # and the key is made of what latexdraw.key_of is given, which has no room for one
        import inspect
        self.assertEqual(list(inspect.signature(latexdraw.key_of).parameters),
                         ["tex", "resolved", "state", "inline"])

    def test_the_html_is_a_figures_caption_below_a_natural_size_drawing(self):
        html = _figure('::::latex chemistry {caption="Water with *care* and [x^2]{math}"}\nx\n::::\n')
        self.assertIn('<figure class="latex has-caption align-center"', html)
        self.assertRegex(html, r"<figcaption[^>]*><span>Water with <em>care</em> and .*</span></figcaption>")
        self.assertIn('data-latex-caption="Water with *care* and [x^2]{math}"', html,
                      "the source, for the editor's pencil")
        self.assertLess(html.index("<img"), html.index("<figcaption"))
        # the drawing keeps its natural width (9.9 ems); the caption's box is never narrower than 20em
        self.assertIn("width:9.90em", html)
        self.assertIn("min(100%,20em)", html)

    def test_the_html_of_a_drawing_with_a_width(self):
        html = _figure('::::latex chemistry {width=45 align=right caption="Water"}\nx\n::::\n')
        self.assertIn("width:45%", html)
        self.assertIn("margin-left:55.00%", html, "where an uncaptioned drawing of that width would stand")
        self.assertIn("<figcaption", html)
        self.assertIn('data-width="45" data-align="right"', html)

    def test_a_drawing_without_a_caption_is_the_figure_it_always_was(self):
        html = _figure("::::latex chemistry {width=45}\nx\n::::\n")
        self.assertNotIn("figcaption", html)
        self.assertNotIn("has-caption", html)
        self.assertIn('style="width:45%;margin-left:27.50%"', html)
        self.assertIn('data-latex-caption=""', html)

    def test_a_drawing_that_could_not_be_made_shows_no_caption_but_keeps_it_for_the_pencil(self):
        def broken(tex, theme, **kw):
            return {"ok": False, "kind": "latex", "said": "LaTeX stopped."}
        with mock.patch.dict(htmlgen.LATEX, {"draw": broken, "draw_all": None}):
            html = htmlgen.render_document('::::latex {caption="Kept"}\nx\n::::\n')["html"]
        self.assertIn("latex-fail", html)
        self.assertNotIn("<figcaption", html)
        self.assertIn('data-latex-caption="Kept"', html)

    def test_a_card_shows_it_and_has_no_pencil(self):
        md = ("---\ntarget: it\n---\n\n:::exercise flashcard\ncard-type: jolly\nfront-primary: |\n"
              "  ::::latex {caption=\"On a card\"}\n  x\n  ::::\nback-primary: y\n:::\n")
        html = _figure(md)
        self.assertRegex(html, r"<figcaption[^>]*><span>On a card</span></figcaption>")
        self.assertNotIn("data-latex-caption", html)

    def test_the_paper_sets_it_under_the_drawing_in_small_grey_type(self):
        block = self.blocks('::::latex chemistry {caption="Water & *care*"}\nx\n::::\n')[0]
        with mock.patch.dict(texgen.LATEX, {"draw": _drawn()}):
            tex = texgen._render_latex(block)
        self.assertIn(r"{\footnotesize\color{graytx} Water \& \emph{care}\par}", tex)
        self.assertIn(r"\includegraphics[scale=", tex, "the drawing at its natural size")
        self.assertIn(r"\dimen1=20em", tex, "and the caption's box no narrower than 20em or the line")
        sized = self.blocks('::::latex chemistry {width=45 align=left caption="W"}\nx\n::::\n')[0]
        with mock.patch.dict(texgen.LATEX, {"draw": _drawn()}):
            tex = texgen._render_latex(sized)
        self.assertIn(r"\includegraphics[width=0.450\linewidth]", tex)
        self.assertIn(r"\raggedright", tex)
        plain = self.blocks("::::latex chemistry {width=45}\nx\n::::\n")[0]
        with mock.patch.dict(texgen.LATEX, {"draw": _drawn()}):
            self.assertNotIn(r"\footnotesize", texgen._render_latex(plain))


class Names(unittest.TestCase):
    def test_one_word_any_script(self):
        for good in ("chemistry", "شیمی", "化学", "my-theme_2"):
            self.assertTrue(latexthemes.name_ok(good), good)
        for bad in ("", "two words", "a/b", "x" * 41):
            self.assertFalse(latexthemes.name_ok(bad), bad)

    def test_case_does_not_matter(self):
        self.assertEqual(latexthemes.name_key("Chemistry"), latexthemes.name_key("chemistry"))


class Rename(unittest.TestCase):
    def test_only_the_name_on_the_opening_line(self):
        md = ("::::latex Chemistry {width=40}\n\\ce{chemistry}\n::::\n"
              "> ::::latex chemistry\n> x\n> ::::\n::::latex drawing\ny\n::::\n")
        out, n = latexthemes.rename_in_text(md, "chemistry", "chem")
        self.assertEqual(n, 2)
        self.assertIn("::::latex chem {width=40}", out)
        self.assertIn("> ::::latex chem\n", out)
        self.assertIn("\\ce{chemistry}", out)
        self.assertIn("::::latex drawing", out)

    def test_a_drawing_in_a_step_is_renamed_too(self):
        md = ":::exercise follow-up\n::::exercise single-choice\nprompt: |\n  :::::latex Chemistry {width=40}\n  x\n  :::::\n::::\n:::\n"
        out, n = latexthemes.rename_in_text(md, "chemistry", "chem")
        self.assertEqual(n, 1)
        self.assertIn("  :::::latex chem {width=40}\n", out)

    def test_an_editor_catches_up(self):
        mark = latexthemes.rename_mark()
        latexthemes.log_rename("zzold", "zznew")
        self.assertIn("::::latex zznew", latexthemes.catch_up("::::latex zzold\nx\n::::\n", mark))
        self.assertIn("::::latex zzold",
                      latexthemes.catch_up("::::latex zzold\nx\n::::\n", latexthemes.rename_mark()))


class Themes(Store):
    def test_base_packages_have_a_public_name_and_explanation(self):
        base, = [g for g in latexthemes.GROUPS if g[0] == "base"]
        self.assertEqual(base[1], "Base packages")
        self.assertTrue(base[2])
        self.assertNotIn("formulae", " ".join(base).lower())

    def test_the_language_groups_added_for_l10_are_real_rows(self):
        # TO-DO §8.39's L10, researched and each one really compiled, 2026-09-27:
        # every group id a package below names must have a heading, and every
        # package must give tlmgr a real name, a licence, and a file that
        # proves it once it is here.
        group_ids = {g[0] for g in latexthemes.GROUPS}
        for group in ("linguistics", "phonetics", "scripts"):
            self.assertIn(group, group_ids)
        expect = {"forest": "linguistics", "tikz-dependency": "linguistics",
                  "tipa": "phonetics", "xpinyin": "scripts"}
        for pid, group in expect.items():
            row = latexthemes.PACKAGES[pid]
            self.assertEqual(row["group"], group)
            self.assertTrue(row["tl"] and all(row["tl"]))
            self.assertTrue(row["licence"])
            self.assertTrue(row["file"] and row["file"].endswith(".sty"))
            self.assertIn(pid, row["code"])

    def test_starters_and_the_default(self):
        names = [t["name"] for t in latexthemes.themes()]
        self.assertEqual(names[:3], ["default", "chemistry", "drawing"])
        self.assertEqual(latexthemes.default_name(), "default")
        self.assertFalse(os.path.exists(os.path.join(ROOT, "config", "latex.json.tmp")))

    def test_a_missing_theme_is_said(self):
        p = latexdraw.plan("x", "nosuch")
        self.assertFalse(p["ok"])
        self.assertEqual(p["fix"], {"kind": "theme-missing", "theme": "nosuch"})

    def test_the_key_follows_the_drawing_not_the_name(self):
        a = latexthemes.resolve("chemistry")
        b = dict(a, name="renamed")
        self.assertEqual(latexdraw.key_of("x", a, "s"), latexdraw.key_of("x", b, "s"))
        self.assertNotEqual(latexdraw.key_of("x", a, "s"),
                            latexdraw.key_of("x", latexthemes.resolve("drawing"), "s"))
        self.assertNotEqual(latexdraw.key_of("x", a, "s"), latexdraw.key_of("x", a, "t"))

    def test_mhchem_only_where_ticked(self):
        self.assertIn("mhchem", latexthemes.resolve("chemistry")["preamble"])
        self.assertNotIn("mhchem", latexthemes.resolve("default")["preamble"])

    def test_export_and_import_under_a_free_name(self):
        data = latexthemes.export_bytes("chemistry")
        theme = latexthemes.read_export(data)
        with self.assertRaises(latexthemes.ThemeError):
            latexthemes.import_theme(theme, "drawing")
        latexthemes.import_theme(theme, "chem2")
        self.assertIsNotNone(latexthemes.find("CHEM2"))


class SheetThemes(Store):
    """What the drawing sheet's Theme list is told: a theme's missing packages, and where Settings is."""

    class Reply:
        def send_json(self, obj, status=200):
            self.obj = obj

    def ask(self, gone, settings, got=(), kind="texlive"):
        import server
        import texpackages
        h = self.Reply()
        with mock.patch.object(texpackages, "installed_many",
                               lambda files: {f: f not in gone for f in files}), \
                mock.patch.object(texpackages, "manifest",
                                  lambda: {"packages": {n: {} for n in got}}), \
                mock.patch.object(texpackages, "_KIND", [kind]), \
                mock.patch.dict(htmlgen.LATEX, {"settings": settings}):
            server.api_latex_themes(h)
        return h.obj

    def test_a_theme_s_own_packages_are_missing_until_parseh_has_them(self):
        # the computer's TeX has everything (a full TeX Live): only Parseh's own copy counts
        got = self.ask(set(), "/settings/latex/")
        self.assertEqual(got["themes"], ["default", "chemistry", "drawing"])
        self.assertEqual(got["missing"], {
            "chemistry": [{"id": "mhchem", "install": "mhchem,chemgreek"}, {"id": "chemfig", "install": "chemfig"}],
            "drawing": [{"id": "tikz", "install": "pgf"}, {"id": "pgfplots", "install": "pgfplots"}]},
            "the base is the computer's; what a theme adds is Parseh's own")
        self.assertEqual(got["settings"], "/settings/latex/")

    def test_nothing_missing_once_got_and_no_settings_page(self):
        got = self.ask(set(), None, got=("mhchem", "chemgreek", "chemfig", "pgf", "pgfplots"))
        self.assertEqual(got["missing"], {})
        self.assertIsNone(got["settings"], "the studio alone has no Settings to send anyone to")

    def test_a_base_file_the_computer_lacks_is_missing_for_every_theme(self):
        got = self.ask({"amsmath.sty"}, None, got=("mhchem", "chemgreek", "chemfig", "pgf", "pgfplots"))
        self.assertEqual({k: [x["install"] for x in v] for k, v in got["missing"].items()},
                         {"default": ["amsmath"], "chemistry": ["amsmath"], "drawing": ["amsmath"]})

    def test_on_miktex_a_package_is_there_or_not(self):
        got = self.ask({"mhchem.sty"}, None, kind="miktex")
        self.assertEqual(got["missing"], {"chemistry": [{"id": "mhchem", "install": "mhchem,chemgreek"}]})

    def test_a_compiler_this_computer_lacks_is_missing_too(self):
        import server
        h = self.Reply()
        with mock.patch.object(latexdraw, "compiler", lambda name, fresh=False: None):
            server.api_latex_themes(h)
        self.assertTrue(h.obj["missing"]["default"][0]["install"] is None
                        and h.obj["missing"]["default"][0]["id"] == latexthemes.find("default")["compiler"])


class ParsehsOwnPackages(Store):
    """A theme's packages beyond the base are Parseh's own (the owner, 2026-09-28):
    a drawing uses one only once Parseh has got it into texmf/, whatever the
    computer's TeX has; the base comes with the computer's TeX."""

    def rule(self, got=(), kind="texlive"):
        import texpackages
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(texpackages, "_KIND", [kind]))
        stack.enter_context(mock.patch.object(texpackages, "manifest",
                                              lambda: {"packages": {n: {} for n in got}}))
        self.addCleanup(stack.close)
        return texpackages

    def test_what_is_own_and_what_is_the_base(self):
        tp = self.rule()
        self.assertTrue(tp.own("mhchem") and tp.own("pgf") and tp.own("chemgreek"))
        self.assertFalse(tp.own("amsmath") or tp.own("tools") or tp.own("standalone") or tp.own("lm-math"))
        self.assertEqual(latexthemes.own_packages(latexthemes.find("chemistry")), ["mhchem", "chemfig"])
        self.assertEqual(latexthemes.own_packages(latexthemes.find("default")), [])

    def test_a_preamble_that_loads_a_catalogue_package_makes_it_the_theme_s_own(self):
        t = dict(latexthemes.find("default"), preamble="\\usepackage[version=4]{mhchem}\n\\usepackage{tikz,zzmine}")
        self.assertEqual(latexthemes.own_packages(t), ["tikz", "mhchem"])
        self.assertIn("mhchem", [x[0] for x in latexthemes.files_needed(t)])

    def test_a_drawing_is_refused_until_parseh_has_the_theme_s_own_packages(self):
        self.rule()
        p = latexdraw.plan("\\ce{H2O}", "chemistry")
        self.assertFalse(p["ok"])
        self.assertEqual(p["kind"], "package")
        self.assertEqual(p["fix"], {"kind": "install", "package": "mhchem,chemgreek,chemfig"})
        self.assertIn("mhchem and chemfig are not among Parseh's own TeX packages", p["said"])
        self.assertIn('"chemistry"', p["said"])

    def test_once_got_it_is_drawn_and_the_base_never_asks(self):
        self.rule(got=("mhchem", "chemgreek", "chemfig"))
        with mock.patch.object(latexdraw, "compiler", lambda name, fresh=False: {"path": "/x", "version": "v"}), \
                mock.patch.object(latexdraw, "tex_state", lambda c: "s"):
            self.assertTrue(latexdraw.plan("\\ce{H2O}", "chemistry")["ok"])
            self.assertTrue(latexdraw.plan("x", "default")["ok"], "the base is the computer's")

    def test_a_drawing_made_beforehand_elsewhere_may_use_the_computer_s_tex(self):
        self.rule()
        with mock.patch.object(latexdraw, "compiler", lambda name, fresh=False: {"path": "/x", "version": "v"}), \
                mock.patch.object(latexdraw, "tex_state", lambda c: "s"):
            self.assertTrue(latexdraw.plan("\\ce{H2O}", "chemistry", local=False)["ok"])

    def test_on_miktex_the_computer_s_tree_answers(self):
        self.rule(kind="miktex")
        with mock.patch.object(latexdraw, "compiler", lambda name, fresh=False: {"path": "/x", "version": "v"}), \
                mock.patch.object(latexdraw, "tex_state", lambda c: "s"):
            self.assertTrue(latexdraw.plan("\\ce{H2O}", "chemistry")["ok"])

    def test_the_page_calls_a_theme_s_own_package_there_only_when_parseh_has_it(self):
        import latexpage
        tp = self.rule(got=("mhchem", "chemgreek"))
        with mock.patch.object(tp, "installed_many", lambda files: {f: True for f in files}), \
                mock.patch.object(tp, "distribution", lambda: {"kind": "texlive", "year": 2026, "tool": None,
                                                                "said": "TeX Live 2026"}), \
                mock.patch.object(tp, "status", lambda: {"installed": {}, "jobs": {}, "available": {}}), \
                mock.patch.object(latexdraw, "compilers", lambda: {}):
            v = latexpage.view("computer")
        self.assertTrue(v["local"])
        self.assertIs(v["files"]["mhchem.sty"], True, "got by Parseh")
        self.assertIs(v["files"]["chemfig.sty"], False, "the computer has it, Parseh has not")
        self.assertIs(v["files"]["amsmath.sty"], True, "the base: the computer's")


class InlineMark(unittest.TestCase):
    """`[…]{latex}` / `[…]{latex theme}` (TO-DO §8.39's L8): no TeX run here
    either, same rule as this whole file -- LATEX_INLINE_RE and
    inline_latex_pairs are pure regex, imported (not copied) from
    lib/latexthemes.py by markdown/exlex/texgen.py and lib/offline.py alike."""
    def test_a_mark_names_its_body_and_an_optional_theme(self):
        m = latexthemes.LATEX_INLINE_RE.search(r"[\ce{H2O}]{latex}")
        self.assertEqual((m.group(1), m.group(3)), (r"\ce{H2O}", None))
        m = latexthemes.LATEX_INLINE_RE.search(r"[\ce{H2O}]{latex chemistry}")
        self.assertEqual((m.group(1), m.group(3)), (r"\ce{H2O}", "chemistry"))

    def test_a_bracket_the_body_opens_and_closes_itself_is_kept(self):
        # the same reason MATH_RE reads `[0,1)` and `\sqrt[3]{x}` correctly
        m = latexthemes.LATEX_INLINE_RE.search(r"[x \in [0,1)]{latex}")
        self.assertEqual(m.group(1), r"x \in [0,1)")

    def test_two_marks_on_one_line_are_both_found_apart(self):
        found = [m.groups() for m in
                 latexthemes.LATEX_INLINE_RE.finditer(r"a [x]{latex} b [y]{latex drawing} c")]
        self.assertEqual([(g[0], g[2]) for g in found], [("x", None), ("y", "drawing")])

    def test_not_a_run_of_the_target_language(self):
        self.assertIn("latex", texgen.NOT_A_RUN)

    def test_pairs_are_deduplicated_in_first_seen_order(self):
        pairs = latexthemes.inline_latex_pairs(
            "[x]{latex} and [y]{latex chemistry} and [x]{latex} again")
        self.assertEqual(pairs, [("x", None), ("y", "chemistry")])

    def test_a_mark_is_found_in_every_text_field_because_the_sweep_is_of_the_raw_source(self):
        # no block tree, no exercise type list to keep in step: an inline
        # mark in a prompt, an option, a note or a document paragraph is the
        # same three characters to a regex over the whole markdown
        source = ("prompt: [p]{latex}\n\nOne option: [a]{latex}, another: "
                  "[b]{latex chemistry}\n\nA note: [c]{latex}.\n")
        self.assertEqual(
            {t for t, _ in latexthemes.inline_latex_pairs(source)}, {"p", "a", "b", "c"})

    def test_a_mark_right_after_an_exercise_s_own_checkbox_is_the_option_s_own(self):
        # the raw sweep once read "- [x] [a]{latex}" as the body "x] [a", and
        # an option's drawing was let go by "Forget drawings nothing uses"
        # while the page still showed it (the owner, 2026-09-28)
        source = ("- [x] [a]{latex}\n- [ ] [$2 + 2$]{latex}\n- [blank1] [1]{latex}\n"
                  "  - [first] [\\ce{H2O}]{latex chemistry}\n- [$x$]{latex} a mark first\n")
        self.assertEqual(latexthemes.inline_latex_pairs(source),
                         [("a", None), ("$2 + 2$", None), ("1", None), ("\\ce{H2O}", "chemistry"),
                          ("$x$", None)])


class APageWaitsForNoDrawing(Store):
    """A document or a note page is made at once, whatever it holds: a drawing
    not made yet is a numbered placeholder, and the page has it made
    afterwards through the studio's drawings route (the owner, 2026-09-28:
    a document with many drawings to make took as long to open as they took,
    and a phone gave up on it)."""

    DOC = ("---\ntitle: T\nlang: en\ntarget: it\n---\n\n::::latex {caption=\"with [a]{latex} in it\"}\n$x$\n::::\n\n"
           "One [$y$]{latex}, two [$z$]{latex}.\n\n::::latex\n$w$\n::::\n\n"
           ":::exercise choose-all\nprompt: Pick.\n- [x] [$1$]{latex}\n- [ ] [$2$]{latex}\n:::\n")

    def stubs(self, made):
        def peek(tex, theme=None, inline=False):
            if (tex, bool(inline)) in made:
                return {"ok": True, "key": "k" * 64, "url": "/latex/x.svg", "w": 10.0, "h": 5.0, "d": 1.0}
            return {"ok": None, "key": "k" * 64}

        def draw(*a, **k):
            raise AssertionError("a deferred page compiles nothing")
        return {"draw": draw, "draw_all": draw, "peek": peek}

    def idx(self, html):
        return re.findall(r'<(\w+)[^>]*?data-latex-idx="(\d+)"', html)

    def test_a_deferred_page_compiles_nothing_and_numbers_every_drawing(self):
        with mock.patch.dict(htmlgen.LATEX, self.stubs(set())):
            out = htmlgen.render_document(self.DOC, latex_defer=True)
        html = out["html"]
        self.assertEqual(out["latex_pending"], 6, "two blocks and four marks; the caption's mark is its block's")
        self.assertEqual(html.count('data-latex-pending="1"'), 6)
        self.assertEqual([n for _t, n in self.idx(html)], [str(i) for i in range(1, 7)])
        self.assertIn('class="latex-pending-block"', html)
        self.assertIn("$w$", html, "a waiting block shows its source")

    def test_the_numbers_are_the_same_waiting_or_drawn(self):
        with mock.patch.dict(htmlgen.LATEX, self.stubs(set())):
            waiting = self.idx(htmlgen.render_document(self.DOC, latex_defer=True)["html"])
        made = {("$x$", False), ("$y$", True), ("$z$", True), ("$w$", False), ("$1$", True), ("$2$", True),
                ("a", True)}
        with mock.patch.dict(htmlgen.LATEX, self.stubs(made)):
            out = htmlgen.render_document(self.DOC, latex_defer=True)
        self.assertEqual(out["latex_pending"], 0)
        drawn = self.idx(out["html"])
        self.assertEqual([n for _t, n in waiting], [n for _t, n in drawn])
        self.assertEqual([t for t, _n in drawn], ["figure", "img", "img", "figure", "img", "img"])

    def test_the_drawings_route_makes_a_few_and_says_how_many_are_left(self):
        import server
        import store
        store.LIB = type(store.LIB)(self.tmp.name) / "library"
        store.LIB.mkdir(parents=True, exist_ok=True)
        was = store.use_library(store.LIB)
        self.addCleanup(store.use_library, was)
        meta = store.create(self.DOC)
        made = set()

        def peek(tex, theme=None, inline=False):
            return ({"ok": True, "key": "k" * 64, "url": "/latex/x.svg", "w": 1.0, "h": 1.0, "d": 0.0}
                    if (tex, bool(inline)) in made else {"ok": None, "key": "k" * 64})

        def draw_all(pairs, inline=False, preview=False):
            made.update((t, bool(inline)) for t, _th in pairs)
            return [{"ok": True} for _ in pairs]

        class H:
            def _json_body(self):
                return {"batch": 3}

            def send_json(self, obj, status=200):
                self.sent = (status, obj)
        rounds = []
        with mock.patch.object(latexdraw, "peek", peek), mock.patch.object(latexdraw, "draw_all", draw_all), \
                mock.patch.dict(htmlgen.LATEX, {"peek": peek, "draw": lambda *a, **k: {"ok": False}}):
            for _ in range(4):
                h = H()
                server.api_doc_drawings(h, meta["id"])
                rounds.append((h.sent[1]["drawn"], h.sent[1]["left"], h.sent[1]["pending"]))
                if not h.sent[1]["left"]:
                    break
        self.assertEqual(rounds, [(3, 4, 4), (3, 1, 1), (1, 0, 0)])


class WhatIsCountedIsWhatIsDrawn(Store):
    """"Forget drawings nothing uses", the day of grace and a phone's kept list
    count a document's drawings from its raw text; a page draws them from the
    parsed one.  Both must name the same drawings."""

    DOC = ("---\ntitle: T\nlang: en\ntarget: it\n---\n\n::::latex\n$x$\n::::\n\n"
           "In a line [$\\frac{1}{2}$]{latex}.\n\n"
           ":::exercise fill-blanks\nprompt: Drag.\ntext: |\n  [$1 = $]{latex} [[blank1]]\n"
           "- [blank1] [1]{latex}\n- [ ] [2]{latex}\n:::\n\n"
           ":::exercise choose-all\nprompt: Choose.\n- [x] [$4 \\cdot 0.25$]{latex}\n- [ ] [$2 + 2$]{latex}\n:::\n\n"
           ":::exercise single-choice\nprompt: |\n  Choose.\n  ::::latex\n  $y$\n  ::::\n- [x] 1\n- [ ] 2\n:::\n\n"
           ":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n  ::::latex {caption=\"c\"}\n  $z$\n  ::::\n"
           "back-primary: 1\n:::\n")

    def test_every_drawing_a_page_draws_is_counted(self):
        import texpackages
        drawn = []

        def draw(tex, theme=None, **kw):
            drawn.append((tex, theme or None, bool(kw.get("inline"))))
            return {"ok": False, "kind": "here", "said": "not here"}
        with mock.patch.dict(htmlgen.LATEX, {"draw": draw, "draw_all": None}), \
                mock.patch.object(latexdraw, "compiler", lambda name, fresh=False: {"path": "/x", "version": "v"}), \
                mock.patch.object(latexdraw, "tex_state", lambda c: "s"), \
                mock.patch.object(texpackages, "_KIND", ["miktex"]):
            htmlgen.render_document(self.DOC)
            asked = {latexdraw.plan(t, th, inline=i)["key"] for t, th, i in drawn}
            counted = latexdraw._source_keys(self.DOC)
        self.assertEqual(len(set(drawn)), 9, drawn)
        self.assertEqual(asked - counted, set(), "a drawing the page draws that nothing counts is let go")
        self.assertEqual(counted - asked, set(), "and nothing is counted that the page never draws")


class KeptDrawings(Store):
    """L9: a live editor's cache is not the saved-library cache."""

    def _put(self, key, preview=False):
        p = latexdraw.paths(key, preview)
        os.makedirs(os.path.dirname(p["meta"]), exist_ok=True)
        for kind, data in (("svg", b"<svg/>"), ("pdf", b"%PDF-"),
                           ("meta", json.dumps({"w": 10, "h": 10}).encode("utf-8"))):
            with open(p[kind], "wb") as fh:
                fh.write(data)

    def test_a_preview_is_not_counted_or_kept_until_promoted(self):
        key = "a" * 64
        self._put(key, preview=True)
        self.assertEqual(latexdraw.size()["drawings"], 0)
        self.assertEqual(latexdraw.file_of(key + ".svg"), latexdraw.paths(key, True)["svg"])
        self.assertTrue(latexdraw._promote(key))
        self.assertEqual(latexdraw.size()["drawings"], 1)
        self.assertEqual(latexdraw.file_of(key + ".svg"), latexdraw.paths(key)["svg"])

    def test_an_owner_keeps_its_key_and_an_orphan_waits_for_the_grace(self):
        key = "b" * 64
        self._put(key)
        doc = {"format": 1, "owners": {"document:test": [key]}, "unowned": {}, "repaired": 0}
        latexdraw._reconcile_owners(doc, [key], now=100)
        self.assertNotIn(key, doc["unowned"])
        doc["owners"].clear()
        latexdraw._reconcile_owners(doc, [key], now=100)
        self.assertEqual(doc["unowned"][key], 100)
        self.assertTrue(os.path.exists(latexdraw.paths(key)["svg"]))
        latexdraw._reconcile_owners(doc, [key], now=100 + latexdraw.OWNER_GRACE_SECONDS + 1)
        self.assertFalse(os.path.exists(latexdraw.paths(key)["svg"]))

    def test_a_delete_starts_the_grace_clock_even_after_a_repair(self):
        # found by the owner, rc3: repair_owners keeps the whole live set as one
        # owner, so a deleted document's keys still counted as owned and the
        # day of grace began at the next repair, not at the delete
        key = "e" * 64
        self._put(key)
        with open(latexdraw._owners_path(), "w", encoding="utf-8") as fh:
            json.dump({"format": 1, "owners": {"document:a": [key]}, "unowned": {}, "repaired": 0}, fh)
        latexdraw.repair_owners({key}, force=True)
        self.assertIn(key, latexdraw._owner_doc()["owners"][latexdraw.REPAIR_OWNER])
        latexdraw.forget_owner("document:a")
        doc = latexdraw._owner_doc()
        self.assertIn(key, doc["unowned"], "the day starts at the delete")
        self.assertNotIn(key, latexdraw._owned(doc))

    def test_a_delete_of_a_source_no_owner_recorded_starts_it_too(self):
        key = "f" * 64
        self._put(key)
        latexdraw.repair_owners({key}, force=True)
        latexdraw.forget_owner("document:never-recorded", also={key})
        self.assertIn(key, latexdraw._owner_doc()["unowned"])

    def test_forgetting_leaves_no_empty_owner_and_no_empty_folder(self):
        gone, kept = "1" * 64, "2" * 64
        self._put(gone)
        self._put(kept)
        with open(latexdraw._owners_path(), "w", encoding="utf-8") as fh:
            json.dump({"format": 1, "owners": {"document:a": [gone], "document:b": [kept]},
                       "unowned": {gone: 5}, "repaired": 0}, fh)
        out = latexdraw.forget_unused({kept})
        self.assertEqual(out["drawings"], 1)
        doc = latexdraw._owner_doc()
        self.assertEqual(doc["owners"], {"document:b": [kept]}, "an owner of nothing is dropped")
        self.assertEqual(doc["unowned"], {})
        self.assertFalse(os.path.exists(os.path.dirname(latexdraw.paths(gone)["svg"])),
                         "the emptied folder goes with its last drawing")
        self.assertTrue(os.path.isfile(latexdraw.paths(kept)["svg"]))

    def test_saving_promotes_the_matching_preview_and_records_its_owner(self):
        key = "c" * 64
        self._put(key, preview=True)
        with mock.patch.object(latexdraw, "plan", return_value={"ok": True, "key": key}):
            keys = latexdraw.own_source("document:test", "::::latex\nx\n::::\n")
        self.assertEqual(keys, {key})
        self.assertTrue(os.path.isfile(latexdraw.paths(key)["svg"]))
        with open(latexdraw._owners_path(), encoding="utf-8") as fh:
            owners = json.load(fh)["owners"]
        self.assertEqual(owners["document:test"], [key])

    def test_showing_a_solved_exercise_is_not_the_same_question_as_caching_a_preview(self):
        # found reviewing this: the two were briefly one flag
        # (editor_preview alone), and a deck's solved study/cram view
        # (editor_preview=True, its own drawings meant to be KEPT) silently
        # stopped showing solved at all, because htmlgen read that one flag
        # for both "show the answer" and "cache this as an unsaved preview".
        calls = []

        def drawn(tex, theme, **kw):
            calls.append(kw.get("preview", False))
            return {"ok": True, "key": "d" * 64, "url": "/latex/d.svg", "w": 10, "h": 10}
        md = ("---\ntarget: it\n---\n\n:::exercise flashcard\ncard-type: jolly\n"
             "front-primary: |\n  ::::latex\n  x\n  ::::\nback-primary: y\n:::\n")
        with mock.patch.dict(htmlgen.LATEX, {"draw": drawn, "draw_all": None}):
            solved = htmlgen.render_document(md, editor_preview=True, latex_preview=False)
            self.assertIn('data-editor-preview="1"', solved["html"], "shown solved")
            self.assertEqual(calls, [False], "kept, not cached as an unsaved preview")
            calls.clear()
            live = htmlgen.render_document(md, editor_preview=True, latex_preview=True)
            self.assertIn('data-editor-preview="1"', live["html"])
            self.assertEqual(calls, [True], "the studio's own unsaved typing IS both at once")


class Handler:
    """The parts of a request the routes below read and answer with."""

    def __init__(self, body=None):
        self.body, self.sent, self.query = body, None, {}

    def _json_body(self):
        return self.body

    def _body(self):
        return json.dumps(self.body).encode("utf-8")

    def send_json(self, obj, code=200):
        self.sent = (code, obj)


NOTE = "---\ntarget: it\n---\n\n# %s\n\n::::latex\n\\ce{%s}\n::::\n\nA mark, [\\ce{%s2}]{latex}, in a line.\n"
EXERCISE = (":::exercise single-choice\nprompt: |\n  Pick.\n  ::::latex\n  \\ce{NaCl}\n  ::::\n"
            "- [x] [\\ce{Na}]{latex}\n- [ ] [\\ce{Cl}]{latex}\n:::\n")


class ForgetWhatWasDeleted(Store):
    """L26, the owner's report after rc3: every document, deck and note that
    held a drawing deleted, the button freed only some.  Driven through the
    routes the pages use -- the studio's, the decks', Settings' -- with the keys
    the real plan() makes; only the TeX run is left out, a drawing being a file
    put where its key says."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT))
        import serve                                          # noqa: E402
        import deckroutes                                     # noqa: E402
        import decks                                          # noqa: E402
        import latexpage                                      # noqa: E402
        import network                                        # noqa: E402
        import store                                          # noqa: E402
        cls.serve, cls.studio, cls.deckroutes, cls.decks = serve, serve.studio, deckroutes, decks
        cls.latexpage, cls.network, cls.store = latexpage, network, store

    def setUp(self):
        super().setUp()
        base = Path(self.tmp.name)
        self.library, self.exercises = base / "library", base / "exercises"
        self.library.mkdir()
        self.books = [base / "book-a" / "markdown", base / "book-b" / "markdown"]
        for one in self.books:
            one.mkdir(parents=True)
        was_lib, self.store.LIB = self.store.LIB, self.library
        was_decks = self.decks.set_dir(self.exercises)
        self.addCleanup(lambda: setattr(self.store, "LIB", was_lib))
        self.addCleanup(lambda: self.decks.set_dir(was_decks))
        for patch in (mock.patch.object(latexdraw, "compiler", lambda name, fresh=False:
                                        {"path": "xelatex", "version": "test", "miktex": False}),
                      mock.patch.object(self.serve, "notes_libraries",
                                        lambda: [(str(one), "the notes of " + one.parent.name)
                                                 for one in self.books])):
            patch.start()
            self.addCleanup(patch.stop)

    def put(self, keys):
        for key in keys:
            for kind, path in latexdraw.paths(key).items():
                if kind != "fail":
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as fh:
                        fh.write(b"x")
        return set(keys)

    def make_document(self, title, formula):
        h = Handler({"markdown": NOTE % (title, formula, formula)})
        self.studio.api_create(h)
        doc_id = h.sent[1]["meta"]["id"]
        markdown = self.store.get(doc_id)[1]
        return doc_id, self.put(latexdraw._source_keys(markdown))

    def make_note(self, book, title, formula):
        was = self.store.use_library(self.books[book])
        try:
            meta = self.store.create(NOTE % (title, formula, formula))
            markdown = self.store.get(meta["id"])[1]
            keys = self.put(latexdraw._source_keys(markdown))
            latexdraw.own_source(self.studio._latex_owner(meta["id"]), markdown)
        finally:
            self.store.use_library(was)
        return meta["id"], keys

    def make_deck(self):
        h = Handler({"name": "Geometry", "lang": "it"})
        self.deckroutes.api_decks_create(h)
        deck = h.sent[1]["deck"]
        h = Handler({"markdown": EXERCISE})
        self.deckroutes.api_item_add(h, deck["folder"], deck["slug"])
        item = self.decks.get_item(deck["folder"], deck["slug"], h.sent[1]["item"]["id"])
        keys = self.put(latexdraw._source_keys(item["markdown"] + "\n" + (item.get("footnotes") or "")))
        return deck, keys

    def forget(self):
        code, out = self.latexpage.api("forget", {}, self.network.SELF, self.serve.notes_libraries(),
                                       rename=self.studio.latexrename, used=self.serve.latex_used)
        self.assertEqual(code, 200, out)
        return out

    def on_disk(self):
        return sorted(os.path.join(here, f) for here, _d, files in os.walk(latexdraw.DRAWN)
                      for f in files if f != latexdraw.OWNERS_FILE)

    def test_every_deleted_document_deck_and_note_frees_its_drawings(self):
        doc_id, doc = self.make_document("Uno", "H2O")
        deck, exercise = self.make_deck()
        note_id, note = self.make_note(0, "Nota", "NaOH")
        self.assertEqual((len(doc), len(exercise), len(note)), (2, 3, 2))
        self.assertEqual(latexdraw.size()["drawings"], 7)
        self.assertEqual(self.forget()["drawings"], 0, "everything is still named by a source")
        self.assertEqual(latexdraw.size()["drawings"], 7)

        self.studio.api_delete(Handler(), doc_id)
        self.assertEqual(self.forget()["drawings"], 2)
        h = Handler()
        self.deckroutes.api_deck_delete(h, deck["folder"], deck["slug"])
        self.assertEqual(h.sent, (200, {"ok": True}))
        self.assertTrue((self.exercises / ".trash").is_dir(), "a deck is only moved to its trash")
        out = self.forget()
        self.assertEqual(out["drawings"], 3, "the trashed deck's drawings go, as rc3 left 3 behind")
        was = self.store.use_library(self.books[0])
        try:
            self.studio.api_delete(Handler(), note_id)
        finally:
            self.store.use_library(was)
        out = self.forget()
        self.assertEqual((out["drawings"], out["forgotten"]), (2, 2))
        self.assertEqual(out["kept"], {"drawings": 0, "bytes": 0})
        self.assertEqual(self.on_disk(), [], "not one file of a drawing is left")
        doc = latexdraw._owner_doc()
        self.assertEqual(doc["owners"], {}, "no owner of nothing")
        self.assertEqual(self.forget()["drawings"], 0, "and a second press finds nothing")

    def test_the_explicit_button_ignores_a_trash_and_the_startup_repair_keeps_it(self):
        deck, exercise = self.make_deck()
        self.deckroutes.api_deck_delete(Handler(), deck["folder"], deck["slug"])
        self.assertEqual(self.serve.latex_used(), exercise, "the repair keeps what a restore would need")
        self.assertEqual(self.serve.latex_used(include_trash=False), set())
        # a book in its trash is a trash too
        trashed = self.books[0].parent.parent / "trash-book" / ".trash" / "old" / "markdown"
        trashed.mkdir(parents=True)
        self.books.append(trashed)
        was = self.store.use_library(trashed)
        try:
            meta = self.store.create(NOTE % ("Vecchia", "KCl", "KCl"))
            note = latexdraw._source_keys(self.store.get(meta["id"])[1])
        finally:
            self.store.use_library(was)
        self.assertEqual(self.serve.latex_used(), exercise | note)
        self.assertEqual(self.serve.latex_used(include_trash=False), set())

    def test_a_deck_taken_back_from_its_trash_is_simply_drawn_again(self):
        deck, exercise = self.make_deck()
        self.deckroutes.api_deck_delete(Handler(), deck["folder"], deck["slug"])
        self.assertEqual(self.forget()["drawings"], 3)
        self.assertEqual(self.on_disk(), [])
        trashed, = list((self.exercises / ".trash").iterdir())
        target = self.exercises / deck["folder"] / deck["slug"]
        target.parent.mkdir(parents=True, exist_ok=True)
        trashed.rename(target)
        self.assertEqual(self.serve.latex_used(include_trash=False), exercise,
                         "back in its place, its drawings are named again")
        made = []

        def compiled(tex, resolved, info, key, limit, inline=False, preview=False):
            made.append(key)
            self.put([key])
            return latexdraw._ok(key, {"w": 10, "h": 10})

        item = self.decks.get_item(deck["folder"], deck["slug"], self.decks._item_ids(target)[0])
        block = [b for b in latexthemes.blocks_in(item["markdown"]) if b["closed"]][0]
        with mock.patch.object(latexdraw, "_compile", compiled):
            out = latexdraw.draw(block["tex"], block["theme"] or None)
        self.assertTrue(out["ok"])
        self.assertEqual(made, [out["key"]], "it was compiled again, the way a first sight is")
        self.assertIn(out["key"], exercise)
        self.assertTrue(os.path.isfile(latexdraw.paths(out["key"])["svg"]))

    def test_the_same_note_in_two_books_is_two_owners(self):
        # found reading, then driven: the owner was built from store.LIB and not
        # from the library the request is in, so one note id in two libraries (a
        # book brought back beside its trashed copy) shared an owner and each
        # save overwrote the other's keys
        a, keys_a = self.make_note(0, "Same", "AlCl3")
        shutil.copytree(self.books[0], self.books[1], dirs_exist_ok=True)
        for source in self.books[1].rglob("source.md"):
            source.write_text(source.read_text(encoding="utf-8").replace("AlCl3", "FeCl3"), encoding="utf-8")
        was = self.store.use_library(self.books[1])
        try:
            markdown = self.store.get(a)[1]
            keys_b = self.put(latexdraw._source_keys(markdown))
            self.assertNotEqual(self.studio._latex_owner(a), "document:%s:%s" % (os.path.realpath(str(self.library)), a))
            latexdraw.own_source(self.studio._latex_owner(a), markdown)
        finally:
            self.store.use_library(was)
        self.assertTrue(keys_a and keys_b and not (keys_a & keys_b))
        owners = latexdraw._owner_doc()["owners"]
        self.assertEqual(len(owners), 2)
        self.assertEqual(sorted(k for keys in owners.values() for k in keys), sorted(keys_a | keys_b))
        was = self.store.use_library(self.books[0])
        try:
            self.studio.api_delete(Handler(), a)
        finally:
            self.store.use_library(was)
        owners = latexdraw._owner_doc()["owners"]
        self.assertEqual(sorted(k for keys in owners.values() for k in keys), sorted(keys_b),
                         "deleting one book's note leaves the other's drawings owned")
        self.assertEqual(self.forget()["drawings"], len(keys_a))
        self.assertEqual(latexdraw.size()["drawings"], len(keys_b))


FIXTURES = ROOT / "tests" / "fixtures" / "latex"


class TheDocumentAndTheLogAreKept(Store):
    """a0.5.4 (the owner, 2026-10-25): what TeX was given and what it wrote stay beside the drawing -- and beside a
    failure, which has no picture -- and are asked for by their address.  TeX is not run: `_run_tex` is
    replaced by one that writes the log a compile would have."""

    SAMPLE = "\\newchessgame\\mainline{1.e4 e5}\\chessboard"

    def compile(self, log, rc=1, make_pdf=False, out="terminal"):
        resolved = latexthemes.resolve("default")
        key = "ab" * 32

        def fake(work, filename, info, limit):
            with open(os.path.join(work, "d.log"), "w", encoding="utf-8") as fh:
                fh.write(log)
            if make_pdf:
                import pymupdf
                doc = pymupdf.open()
                doc.new_page(width=80, height=40)
                doc.save(os.path.join(work, "d.pdf"))
            return rc, out, 0.1

        with mock.patch.object(latexdraw, "_run_tex", fake):
            r = latexdraw._compile(self.SAMPLE, resolved, {"path": "/x", "version": "v"}, key, 30,
                                   preview=True)
        return r, key, resolved

    def test_a_failure_keeps_the_document_exactly_as_source_made_it_and_the_log_whole(self):
        log = "This is XeTeX\n(./d.tex\n./d.tex:12: Undefined control sequence.\nl.12 \\newchessgame\n"
        r, key, resolved = self.compile(log)
        self.assertFalse(r["ok"])
        self.assertEqual(r["key"], key, "a failure says which compile it was")
        self.assertEqual(latexdraw.read_text(key, "tex"), latexdraw.source(self.SAMPLE, resolved),
                         "byte for byte the document TeX was given")
        self.assertEqual(latexdraw.read_text(key, "log"), log, "and the whole log it wrote")
        self.assertTrue(os.path.isfile(latexdraw.file_of(key + ".tex")))
        self.assertTrue(os.path.isfile(latexdraw.file_of(key + ".log")))
        self.assertEqual([r["marks"][0]], [3], "the line the words were made from is marked in it")

    def test_a_success_keeps_them_too(self):
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            self.skipTest("PyMuPDF is not here")
        r, key, resolved = self.compile("Output written on d.pdf (1 page).\n", rc=0, make_pdf=True)
        self.assertTrue(r["ok"])
        self.assertEqual(latexdraw.read_text(key, "tex"), latexdraw.source(self.SAMPLE, resolved))
        self.assertIn("Output written", latexdraw.read_text(key, "log"))

    def test_the_address_names_a_key_and_one_of_four_kinds_and_nothing_else(self):
        self.assertIsNone(latexdraw.file_of("../../etc/passwd"))
        self.assertIsNone(latexdraw.file_of("ab" * 32 + ".txt"))
        self.assertIsNone(latexdraw.file_of("ab" * 32 + ".tex"), "nothing kept under that key")
        self.assertIsNone(latexdraw.read_text("nonsense", "tex"))
        self.assertIsNone(latexdraw.read_text("ab" * 32, "svg"))

    def test_a_log_over_the_cap_is_cut_and_says_so(self):
        long = "a line of a runaway log\n" * 40000
        self.assertGreater(len(long.encode()), latexdraw.LOG_MAX)
        kept = latexdraw._capped(long)
        self.assertLessEqual(len(kept.encode()), latexdraw.LOG_MAX + 200)
        self.assertIn("kept the first 512 KB of this log", kept)
        self.assertTrue(kept.startswith("a line of a runaway log\n"))
        self.assertEqual(latexdraw._capped("short\n"), "short\n", "a log under the cap is whole")

    def test_what_a_font_helper_printed_is_kept_beside_the_log_and_the_terminal_echo_is_not(self):
        out = ("(./d.tex (/a/b/skak.sty\nkpathsea: Running mktextfm SkakNew-Diagram\n"
               "mktextfm: `mf-nowin ...' failed to make SkakNew-Diagram.tfm.\n"
               "(/x/pgfsys-dvipdfmx.def (/x/y.def))\nTranscript written on d.log.\n")
        r, key, resolved = self.compile("This is XeTeX\n(./d.tex\n", out=out)
        log = latexdraw.read_text(key, "log")
        self.assertIn("[what the program printed besides this log]", log)
        self.assertIn("kpathsea: Running mktextfm SkakNew-Diagram", log)
        self.assertIn("failed to make SkakNew-Diagram.tfm", log)
        self.assertNotIn("pgfsys-dvipdfmx", log, "the terminal's copy of the open files is not what it printed besides")
        self.assertNotIn("Transcript written on d.log", log)

    def test_forgetting_failures_takes_a_failures_document_and_log_and_leaves_a_drawing_its_own(self):
        failed = "cd" * 32
        drawn = "ef" * 32
        for key, kinds in ((failed, ("tex", "log", "fail")), (drawn, ("tex", "log", "svg", "pdf", "meta"))):
            for kind in kinds:
                latexdraw._write_atomic(latexdraw.paths(key)[kind], b"x")
        latexdraw.forget_failures()
        got = lambda key, kind: os.path.exists(latexdraw.paths(key)[kind])
        self.assertFalse(got(failed, "fail") or got(failed, "tex") or got(failed, "log"))
        self.assertTrue(got(drawn, "tex") and got(drawn, "log") and got(drawn, "svg"))

    def test_the_bounded_cache_of_previews_counts_a_failure_that_has_no_picture(self):
        with mock.patch.object(latexdraw, "PREVIEW_MAX_DRAWINGS", 2):
            for i in range(4):
                key = ("%02d" % i) * 32
                for kind in ("tex", "log"):
                    latexdraw._write_atomic(latexdraw.paths(key, True)[kind], b"x")
                os.utime(latexdraw.paths(key, True)["tex"], (1000 + i, 1000 + i))
                os.utime(latexdraw.paths(key, True)["log"], (1000 + i, 1000 + i))
            self.assertEqual(latexdraw.prune_previews(), 2)
        left = {k for k in ("%02d" % i * 32 for i in range(4)) if os.path.exists(latexdraw.paths(k, True)["tex"])}
        self.assertEqual(left, {"02" * 32, "03" * 32}, "the newest two stay")

    def test_the_renderer_number_was_raised_so_that_every_drawing_is_made_with_its_document_and_log(self):
        self.assertGreaterEqual(latexdraw.RENDERER, 3)


class WhatTheLogOfAFailureSays(unittest.TestCase):
    """explain() on the logs TeX really writes.  The first is the owner's, kept (paths made neutral): xskak with
    the chess fonts not installed -- a message from skak.sty, which -file-line-error writes as FILE:LINE:, not as
    `! ` and not as d.tex:N:, so it was read as nothing and the log's memory statistics were the whole answer."""

    RESOLVED = {"name": "chess"}

    def explain(self, log, tex="x"):
        return latexdraw.explain(log, 11, tex, self.RESOLVED)

    def test_a_message_from_a_package_file_is_read(self):
        log = (FIXTURES / "font-not-loadable.log").read_text(encoding="utf-8")
        tex = (FIXTURES / "font-not-loadable.tex").read_text(encoding="utf-8")
        r = self.explain(log, tex)
        self.assertEqual(r["kind"], "package")
        self.assertNotIn("without saying why", r["said"])
        self.assertIn('"SkakNew-Diagram"', r["said"])
        self.assertIn("skak.sty", r["said"], "it says which file asked for it")
        self.assertIn("skaknew", r["said"])
        self.assertEqual(r["fix"], {"kind": "install", "package": "skaknew"})
        self.assertIsNone(r["line"], "a line of skak.sty is no line of the block")
        self.assertIn("not loadable", r["detail"])
        self.assertNotIn("words of memory", r["detail"], "the memory statistics are not the finding")
        lines = log.splitlines()
        self.assertTrue(any("not loadable" in lines[n - 1] for n in r["marks"]))
        self.assertTrue(any(lines[n - 1].startswith("l.1774") for n in r["marks"]))

    def test_the_whole_kept_log_is_there_with_what_the_helpers_printed(self):
        log = (FIXTURES / "font-not-loadable.log").read_text(encoding="utf-8")
        self.assertIn("kpathsea: Running mktextfm SkakNew-Diagram", log)
        self.assertIn("failed to make SkakNew-Diagram.tfm", log)

    def test_a_missing_file_asked_for_by_a_package_is_that_packages_and_not_a_line_of_the_block(self):
        log = ("(./d.tex\n! LaTeX Error: File `xifthen.sty' not found.\n\nType X to quit or <RETURN> to proceed,\n"
               "or enter new name. (Default extension: sty)\n\nEnter file name: \n"
               "/p/texmf/tex/latex/xskak/xskak.sty:41: Emergency stop.\n<read *> \n\nl.41 \\RequirePackage\n"
               "                    {etoolbox}^^M\n")
        r = self.explain(log)
        self.assertEqual(r["fix"], {"kind": "install", "file": "xifthen.sty", "package": "xifthen"})
        self.assertIsNone(r["line"], "line 41 is xskak.sty's, not the block's")
        self.assertIn("in xskak.sty", r["said"])
        self.assertNotIn("of the block", r["said"])

    def test_an_error_in_the_document_is_still_the_blocks_line_and_marks_both_lines(self):
        log = "This is XeTeX\n(./d.tex\n./d.tex:12: Undefined control sequence.\n<recently read> \\foo \n\nl.12 \\foo\n"
        r = latexdraw.explain(log, 10, "a\nb\n\\foo", self.RESOLVED)
        self.assertEqual(r["line"], 3, "line 12 of the file is the block's third line")
        self.assertEqual(r["marks"], [3, 6])
        self.assertIn("on line 3 of the block", r["said"])

    def test_a_log_that_made_no_page_and_has_no_error_says_so_and_names_no_memory(self):
        # TeX ran to its end and nothing put anything on a page (a log made by hand: there is no way to make
        # TeX say this on purpose with an error in it)
        log = ("This is XeTeX\n(./d.tex\n\nHere is how much of TeX's memory you used:\n 9119 strings out of 469739\n"
               " 555642 words of memory out of 5000000\n 38036 multiletter control sequences out of 15000+600000\n"
               "No pages of output.\n")
        r = self.explain(log, "\\relax")
        self.assertEqual(r["kind"], "empty")
        self.assertTrue(r["said"].startswith("LaTeX made no page: "))
        self.assertNotIn("without saying why", r["said"])
        self.assertNotIn("words of memory", r["detail"])
        self.assertEqual(r["marks"], [log.splitlines().index("No pages of output.") + 1])
        self.assertIn("the block is empty", self.explain(log, "  ")["said"])

    def test_a_log_with_no_message_and_pages_is_still_the_old_answer(self):
        r = self.explain("This is XeTeX\n(./d.tex\nsomething\n")
        self.assertEqual(r["said"], "LaTeX stopped without saying why.")

    def test_a_font_tex_could_not_make_is_named_with_the_package_that_has_it(self):
        log = "(./d.tex\n! Font \\x=SkakNew-DiagramT at 20pt not loadable: Metric (TFM) file not found.\n<to be read again> \nl.5 \\foo\n"
        r = self.explain(log)
        self.assertEqual(r["fix"], {"kind": "install", "package": "skaknew"})
        other = self.explain("(./d.tex\n! Font \\x=Zzz at 10pt not loadable: Metric (TFM) file not found.\nl.5 x\n")
        self.assertIn("Zzz", other["said"])
        self.assertNotIn("fix", other)
        self.assertIn("no shell", other["said"])


class TheChessSetIsOneRow(Store):
    """TeX Live declares no dependency for xskak, skak, chessboard or chessfss, and a drawing needs the chess fonts and
    five packages besides (found by drawing the sample from nothing): one catalogue row, so that a theme that loads
    any of them asks for all of them at once."""

    NEED = ("xskak", "skak", "chessfss", "chessboard", "skaknew", "lambda-lists", "xifthen", "ifmtarg", "pst-node", "pstricks")

    def theme(self, preamble):
        return latexthemes.clean({"name": "chess", "compiler": "xelatex", "packages": ["amsmath"], "preamble": preamble})

    def test_the_row_names_the_whole_set(self):
        self.assertEqual(tuple(latexthemes.PACKAGES["xskak"]["tl"]), self.NEED)
        self.assertEqual(latexthemes.PACKAGES["xskak"]["code"], "\\usepackage{xskak}")
        self.assertIn("games", [g[0] for g in latexthemes.GROUPS])

    def test_loading_any_of_the_four_by_name_is_the_one_row(self):
        for name in ("xskak", "skak", "chessboard", "chessfss"):
            t = self.theme("\\usepackage{%s}" % name)
            self.assertEqual(latexthemes.own_packages(t), ["xskak"], name)

    def test_a_drawing_asks_for_the_whole_set_in_one_button(self):
        import texpackages
        with mock.patch.object(texpackages, "_KIND", ["texlive"]), \
                mock.patch.object(texpackages, "manifest", lambda: {"packages": {}}):
            p = latexdraw.plan("\\chessboard", None, theme=self.theme("\\usepackage{xskak}"))
        self.assertFalse(p["ok"])
        self.assertEqual(p["fix"], {"kind": "install", "package": ",".join(self.NEED)})

    def test_and_draws_once_every_one_of_them_is_got(self):
        import texpackages
        with mock.patch.object(texpackages, "_KIND", ["texlive"]), \
                mock.patch.object(texpackages, "manifest", lambda: {"packages": {n: {} for n in self.NEED}}), \
                mock.patch.object(latexdraw, "compiler", lambda name, fresh=False: {"path": "/x", "version": "v"}), \
                mock.patch.object(latexdraw, "tex_state", lambda c: "s"):
            self.assertTrue(latexdraw.plan("\\chessboard", None, theme=self.theme("\\usepackage{xskak}"))["ok"])


class TheDoorAndTheStudioOfferThem(unittest.TestCase):
    """The door's sample answers with the document and the log; the studio's frame has the two buttons and an
    exported page has none."""

    def test_the_sample_answer_carries_tex_log_and_marks(self):
        import latexpage
        key = "12" * 32
        r = {"ok": False, "kind": "latex", "said": "x", "key": key, "marks": [3]}
        with mock.patch.object(latexdraw, "draw", lambda *a, **k: r), \
                mock.patch.object(latexdraw, "read_text", lambda k, kind: {"tex": "DOC", "log": "LOG"}[kind] if k == key else None):
            status, answer = latexpage.api("sample", {"theme": {"name": "chess", "compiler": "xelatex", "packages": []}, "tex": "x"}, "computer")
        self.assertEqual(status, 200)
        self.assertEqual((answer["tex"], answer["log"], answer["marks"]), ("DOC", "LOG", [3]))
        self.assertIn("documentclass", answer["preamble"], "the whole preamble is still there, beside the .tex")

    def test_the_door_draws_the_two_views_and_a_copy_each(self):
        src = (ROOT / "lib" / "latexpage.py").read_text(encoding="utf-8")
        for needle in ("The .tex that was compiled", "The whole log", 'data-copy="tex"', 'data-copy="log"', "markedLog",
                       "The whole preamble"):
            self.assertIn(needle, src, needle)

    def test_the_studios_failure_frame_has_the_two_buttons_where_there_is_a_compile(self):
        b = {"tex": "\\foo", "theme": "", "errors": []}
        r = {"ok": False, "kind": "latex", "said": "x", "key": "34" * 32, "marks": [5, 8]}
        with mock.patch.dict(htmlgen.LATEX, {"draw": lambda *a, **k: r}):
            html = htmlgen._latex_frame(b, r, {})
        base = htmlgen.URL_BASE + "/latex/" + "34" * 32
        self.assertIn('data-latex-view="tex" data-latex-url="%s.tex"' % base, html)
        self.assertIn('data-latex-view="log" data-latex-url="%s.log" data-latex-marks="5,8"' % base, html)
        self.assertIn("The .tex that was compiled", html)
        self.assertIn("The whole log", html)
        none = htmlgen._latex_frame(b, {"ok": False, "kind": "package", "said": "y"}, {})
        self.assertNotIn("data-latex-view", none, "no compile, nothing to show")

    def test_an_exported_page_carries_no_such_buttons(self):
        import webexport
        self.assertIn("latex-views", webexport.DROP_CLASSES)

    def test_both_servers_send_the_text_as_text(self):
        server_src = (ROOT / "markdown" / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn(r"\.(?:svg|pdf|tex|log))$", server_src)
        serve_src = (ROOT / "serve.py").read_text(encoding="utf-8")
        self.assertIn('f.endswith((".tex", ".log"))', serve_src)
        self.assertIn("text/plain; charset=utf-8", serve_src)


if __name__ == "__main__":
    unittest.main()
