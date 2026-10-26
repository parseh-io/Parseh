#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""THE BOOK READER'S GEAR (lib/gear-reader.js), as the files say it.

    python3 -m unittest discover -s tests -p test_gear_reader.py

What the gear DOES -- every row, the names, Diacritics, the phone's sheet, a reader built before a0.5.0 --
is driven in a real Chromium by tests/gear_reader.mjs.  What is checked here is what only the SOURCE can say:

* THE LEVELS' NAMES THE LAYER CARRIES for a reader built before the names existed (its table LEVELS) are
  the registry's, word for word, for every language Parseh ships -- and the rule that names a level of a
  language somebody added since (its JS twin of languages.default_level_name) answers as the Python one
  does, for all eleven and for languages lib/newlang.py wrote;
* the loader puts the toolkit, the layer and the mobile layer in ORDER, and every list that serves or keeps
  a file names the new one;
* the layer builds nothing with innerHTML (a row's words may come from a book), keeps its hands off the
  reader's own handlers, and says the plan's sentences;
* the build writes the names, and the phone's header is the first line alone.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "youtube/lib", "lib", "tests", "."):
    sys.path.insert(0, str(ROOT / p))

import languages  # noqa: E402

JS = ROOT / "lib" / "gear-reader.js"
DENO = shutil.which("deno") or os.path.expanduser("~/miniconda3/envs/ilya-frank/bin/deno")


def read(path):
    return Path(path).read_text(encoding="utf-8")


def flat(src):
    """The script's strings as they read: \\uXXXX escapes made characters and "a" + "b" made "ab"."""
    src = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), src)
    src = re.sub(r'"\s*\+\s*"', "", src)
    src = re.sub(r"'\s*\+\s*'", "", src)
    return src.replace("\\'", "'")


def shipped():
    """The rows of lib/languages.json, as Parseh ships them."""
    rows = json.loads(read(ROOT / "lib" / "languages.json"))
    return {k: v for k, v in rows.items() if not k.startswith("_")}


class TheTable(unittest.TestCase):
    """LEVELS in the layer is lib/languages.json."""

    @classmethod
    def setUpClass(cls):
        src = read(JS)
        m = re.search(r"// LEVELS-BEGIN\s+var LEVELS = (\{.*?\n  \});\s+// LEVELS-END", src, re.S)
        assert m, "the layer's LEVELS table is not between its markers"
        cls.table = json.loads(m.group(1))

    def test_it_is_the_registry_word_for_word(self):
        want = {code: {p["key"]: [p["name"], p["title"]] for p in row["passes"]} for code, row in shipped().items()}
        self.assertEqual(self.table, want)

    def test_it_has_every_shipped_language_and_nothing_else(self):
        self.assertEqual(set(self.table), set(shipped()))
        self.assertEqual(len(self.table), 11)

    def test_no_name_is_longer_than_a_button_holds_and_none_has_a_digit(self):
        for code, row in self.table.items():
            for key, (name, title) in row.items():
                self.assertLessEqual(len(name), languages.LEVEL_NAME_MAX, (code, key))
                self.assertFalse(re.search(r"\d", name + title), (code, key))


# the layer's code run in Deno with no page: it exports its table and its rule and stops short of the DOM
HARNESS = r"""
const src = await Deno.readTextFile(Deno.args[0]);
(0, eval)(src);
const g = globalThis.ParsehGearReader;
const cases = JSON.parse(Deno.args[1]);
console.log(JSON.stringify(cases.map(c => ({
  rule: g.defaultName(c.lang, c.pass),
  chosen: g.levelDefault(c.lang, c.pass),
}))));
"""


@unittest.skipUnless(os.path.exists(DENO), "no deno")
class TheTwin(unittest.TestCase):
    """The layer's rule names a level as languages.default_level_name does, over the record a page embeds."""

    def drive(self, cases):
        with tempfile.TemporaryDirectory() as td:
            script = os.path.join(td, "harness.mjs")
            Path(script).write_text(HARNESS, encoding="utf-8")
            r = subprocess.run([DENO, "run", "--quiet", "--allow-read", script, str(JS), json.dumps(cases)],
                               capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def old_embed(self, row, code):
        """What a reader built before the names embedded for this row: the record without the passes' names."""
        entry = dict(row)
        lang = languages.Lang(code, entry).as_json()
        lang["passes"] = [{k: v for k, v in p.items() if k != "name"} for p in lang["passes"]]
        return lang

    def test_it_agrees_for_every_shipped_language(self):
        cases, want = [], []
        for code, row in shipped().items():
            lang = self.old_embed(row, code)
            for p, q in zip(lang["passes"], row["passes"]):
                cases.append({"lang": lang, "pass": p})
                want.append((code, q["key"], languages.default_level_name(row, q), q["name"]))
        got = self.drive(cases)
        for g, (code, key, py, registry) in zip(got, want):
            self.assertEqual(py, registry, "%s %s: the Python rule is not the registry's" % (code, key))
            self.assertEqual(g["rule"], py, "%s %s: the layer's rule answers otherwise" % (code, key))
            self.assertEqual(g["chosen"]["name"], registry, "%s %s: and its table" % (code, key))

    def test_it_agrees_for_a_language_made_by_newlang(self):
        """lib/newlang.py writes the names by languages.default_level_name; a reader of such a language, built
        before the names were embedded, is named by the layer's twin of it, from what the page embeds."""
        import newlang
        made = []
        for code, args in (
                ("qx", ["--name", "Testish", "--native", "Testish", "--script", "cjk", "--words", "--vertical",
                        "--translit-label", "pinyin"]),
                ("qy", ["--name", "Testy", "--native", "Testy"]),
                ("qz", ["--name", "Arabish", "--native", "Arabish", "--script", "arabic", "--strip", "\\u064B-\\u0652"]),
                ("qr", ["--name", "Readish", "--native", "Readish", "--script", "cjk", "--words", "--reading",
                        "--reading-label", "kana", "--vertical", "--vocal-label", "with furigana"]),
                ("qm", ["--name", "Markish", "--native", "Markish", "--script", "other", "--strip", "\\u0300-\\u036F"]),
                ("qa", ["--name", "Fontish", "--native", "Fontish", "--script", "arabic", "--alt-font", "Foo Bar",
                        "--alt-key", "nastaliq"])):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    newlang.main([code] + args + ["--dry-run"])
                except SystemExit:
                    continue
            text = buf.getvalue()
            try:
                made.append((code, json.loads(text[text.index("\n{") + 1:text.index("\n--dry-run")])[code]))
            except ValueError:
                continue
        self.assertGreaterEqual(len(made), 3, "newlang made too few languages to compare: %r" % [c for c, _ in made])
        cases, want = [], []
        for code, entry in made:
            lang = self.old_embed(entry, code)
            for p, q in zip(lang["passes"], entry["passes"]):
                cases.append({"lang": lang, "pass": p})
                want.append((code, q["key"], languages.default_level_name(entry, q), q["name"]))
        got = self.drive(cases)
        for g, (code, key, py, written) in zip(got, want):
            self.assertEqual(py, written, "%s %s: newlang wrote a name the rule does not give" % (code, key))
            self.assertEqual(g["rule"], py, "%s %s: the layer's rule answers otherwise" % (code, key))
            self.assertEqual(g["chosen"]["name"], py, "%s %s: and what it uses" % (code, key))

    def test_a_record_that_names_its_levels_is_believed(self):
        """A reader built now embeds the names and the sentences: the layer wears those, not its table."""
        row = shipped()["fa"]
        lang = languages.Lang("fa", dict(row)).as_json()
        lang["passes"][0]["name"] = "Mine"
        lang["passes"][0]["title"] = "my sentence"
        got = self.drive([{"lang": lang, "pass": lang["passes"][0]}])
        self.assertEqual(got[0]["chosen"], {"name": "Mine", "title": "my sentence"})


class TheLoader(unittest.TestCase):
    """parseh.js loads the gear into every reader, in order; the lists that serve and keep it name it."""

    PARSEH = read(ROOT / "lib" / "parseh.js")

    def test_the_toolkit_then_the_layer_then_the_mobile_layer(self):
        loader = self.PARSEH[self.PARSEH.index("/* THE GEAR OF THE READER (a0.5.0)"):
                             self.PARSEH.index("/* ---- the macro buttons of a book's chunk sheet")]
        self.assertIn("[['ParsehGear', 'pagesettings.js'], ['ParsehGearReader', 'gear-reader.js']]", loader)
        self.assertLess(loader.index("pagesettings.js"), loader.index("gear-reader.js"))
        self.assertLess(loader.index("gear-reader.js"), loader.index("base + 'mobilereader.js'"))
        # ordered: a script put in by hand runs in the order it was put in only when it is told not to be async
        self.assertIn("g.async = false;", loader)
        self.assertIn("s.async = false;", loader[loader.index("base + 'mobilereader.js'"):])
        # the class the controls the gear took off the page hang on, and the way out if a script cannot be had
        self.assertIn("rootEl.classList.add('pg-reader');", loader)
        self.assertIn("g.onerror = function () { rootEl.classList.remove('pg-reader'); };", loader)
        # a reader only: the same address rule as the mobile layer's
        self.assertLess(self.PARSEH.index("a book's reader, in the mobile interface"),
                        self.PARSEH.index("THE GEAR OF THE READER"))

    def test_typo_hands_the_gear_its_fields(self):
        typo = self.PARSEH[self.PARSEH.index("  function typo(opts) {"):self.PARSEH.index("// CJK controls share")]
        self.assertIn("api.fields = fields;", typo)
        self.assertIn("typo.last = api;", typo)
        # exposed before the early return of a typo with no button, and the old panel is left as it was
        self.assertLess(typo.index("typo.last = api;"), typo.index("if (!btn) return api;"))
        self.assertIn("panel.className = 'parseh-typo';", typo)

    def test_it_is_served_and_kept(self):
        import offline
        import serve
        self.assertIn("/lib/gear-reader.js", serve.STATIC_FILES)
        self.assertTrue(serve.static_ok("/lib/gear-reader.js"))
        self.assertIn("/lib/gear-reader.js", offline.SHARED)
        self.assertTrue((ROOT / "lib" / "gear-reader.js").is_file())

    def test_the_toolkit_ignores_a_scripts_click_for_its_outside_click(self):
        """The rows press the page's own buttons with .click(); that click is outside the panel and must not
        shut the popover under a person's hand (found by driving the first row of the book's gear)."""
        kit = read(ROOT / "lib" / "pagesettings.js")
        on_click = kit[kit.index("    function onClick(e) {"):kit.index("    function onResize() {")]
        self.assertIn("if (e.isTrusted === false) return;", on_click)
        self.assertLess(on_click.index("e.isTrusted === false"), on_click.index("close('outside')"))


class TheLayer(unittest.TestCase):
    SRC = read(JS)
    CODE = re.sub(r"/\*.*?\*/", "", SRC, flags=re.S)

    def test_it_builds_nothing_with_innerHTML(self):
        self.assertNotIn("innerHTML", self.CODE)
        self.assertNotIn("insertAdjacentHTML", self.CODE)
        self.assertNotIn("document.write", self.CODE)

    def test_it_rewrites_text_and_titles_and_never_a_handler(self):
        for banned in (".onclick", ".onchange", ".oninput", "removeEventListener('click'"):
            self.assertNotIn(banned, self.CODE)
        # the only things it takes out of the page are what lib/mobile.css hides
        self.assertNotIn(".remove()", self.CODE)
        self.assertNotIn("removeChild", self.CODE)

    def test_it_says_what_each_theme_is_set_to_for_the_sheets_index(self):
        # a0.5.4: the summaries the phone's sheet shows under each theme's name
        for needle in ("var SHORT = {", "short: SHORT.gloss", "short: SHORT.hover", "short: SHORT.cont", "short: SHORT.loop",
                       "short: SHORT.dictmode", "'no glosses'", "'cloud'", "'no diacritics'", "'no dictionary'",
                       "'get one \\u2192'", "{bdi: it.name}", "' text ' + amount(f, x.get()[f.name])"):
            self.assertIn(needle, self.CODE, needle)

    def test_aa_is_at_text_when_text_is_the_theme_on_stage(self):
        self.assertIn("var st = typeof gear.stage === 'function' ? gear.stage() : null;", self.CODE)
        self.assertIn("return st === 'text';", self.CODE)

    def test_it_drives_the_readers_own_controls(self):
        for sel in ("'cont'", "'loop'", "'stopbnd'", "'listen'", "'hovermode'", "'hoverpause'", "'dictmode'", "'defmode'",
                    "'defmt'", "'bars'", "'barsback'", "'gap'", "'lookupset'", "[data-toggle=nogloss]", "[data-toggle=no"):
            self.assertIn(sel, self.CODE)
        self.assertIn("function press(b) { if (b && !b.disabled) b.click(); }", self.CODE)

    def test_the_groups_come_in_the_order_of_the_plan(self):
        spec = self.CODE[self.CODE.index("groups: [levelsGroup()"):]
        self.assertTrue(spec.startswith("groups: [levelsGroup(), listeningGroup(), lookingGroup(), textGroup(), "
                                        "G.std.zoom(), colours, iface]"))

    def test_the_plans_names_and_sentences_are_said(self):
        text = flat(self.SRC)
        for said in (
                # levels & reading
                "label: 'Levels'", "label: 'Diacritics'", "label: 'Glosses'", "label: 'Glosses in a cloud'",
                "label: 'Pause while a gloss is open'", "label: 'Hide the bars'",
                "Show the meaning beside each chunk. Turn it off to test yourself against the chunks alone. Key G.",
                "Read the text clean: a chunk's gloss opens in a cloud when you point at it (a tap on a touch screen). Key H. ",
                "While it is on, the Chunks level and the glosses switch rest, because the cloud shows the glosses instead.",
                "While a gloss is open the recording waits, and goes on a moment after it closes, so you can read at your own pace. ",
                "Puts the header away so the text has the whole window; a small ⌄ at the top corner brings it back.",
                # listening
                "label: 'Playback speed'", "label: 'Skip distance'", "label: 'Keep playing into the next line'",
                "label: 'Repeat this line'", "label: 'Pause between repeats'", "label: 'Wait at each new chapter'",
                "label: 'Listen on its own'",
                "How fast the recording plays, from 0.25× to 2×. The [ and ] keys step it.",
                "How many seconds ↺ and ↻ move the recording. Shift+← and Shift+→ do the same.",
                "When a line of the recording ends, go straight on to the next one instead of stopping. Turn it off to practise one line at a time.",
                "The silence between one repeat of a line and the next while loop is on, from none to 5 seconds.",
                "When the recording reaches the start of a new chapter or section it stops and waits for you to press ▶, so you can take in the heading and get ready.",
                "Plays the recording by itself: nothing is highlighted or scrolled and your reading place stays put. A seek bar appears so you can start anywhere.",
                # looking a word up
                "label: 'Look words up in a dictionary'", "label: 'Show the dictionary's definitions'",
                "Where a chunk has not been glossed, click or tap it to look its words up in the dictionary installed for this language. Remembered for this book.",
                "Under each word it finds, the dictionary's own definition in ",
                "Translate the definitions into ", "label: 'Get a dictionary for this language →'",
                "by the translation model on this computer: a machine's reading, not a gloss.",
                # text
                "text size'", "'Gloss size'", "'Text width'", "'Line spacing'", "'Height of vertical columns'",
                "'Space between characters'", "'Furigana contrast'", "'Furigana size'", "'Put the text back to normal'",
                "How big the book's own words are, the ones you are learning.",
                "How big the meanings and notes beside each chunk are, and inside the hover cloud.",
                "How wide the column of text may grow on a wide screen; on a narrow screen it always fits.",
                "The space between lines: 1 is the usual, more is airier.",
                "How tall each column of vertical text is, counted in character heights.",
                "Extra room between characters; 0 is the normal spacing.",
                "How strongly the small kana over the kanji are drawn: lower fades them so the kanji stand out, higher makes them darker.",
                "How big the kana over the kanji are, as a percentage of the kanji's own size.",
                "Hover mode shows the glosses in the cloud instead."):
            self.assertIn(said, text)

    def test_diacritics_keeps_the_originals_and_wraps_the_readers_of_text(self):
        for said in ("var originals = new WeakMap();", "var SCOPE = '.p1 .w, .row .fa';", "var MARKS_KEY = 'bk_marks';",
                     "root.textOf = function (el)", "p.baseText = function (el)", "watcher.observe(main, {childList: true, subtree: true});",
                     "originals.set(n, t);", "if (!L || !L.strip) return null;"):
            self.assertIn(said, self.SRC)
        # a reading drawn over the text is not the book's text
        self.assertIn("p.closest('rt, rp')", self.SRC)

    def test_keep_going_is_remembered_in_the_key_the_toolbox_follows(self):
        import prefs
        self.assertIn("bk_cont", prefs.KEYS)
        self.assertIn("getKey('bk_cont')", self.SRC)
        self.assertIn("putKey('bk_cont', on(c) ? '1' : '0')", self.SRC)
        self.assertIn("var NAME_MAX = 12;", self.SRC)
        self.assertEqual(languages.LEVEL_NAME_MAX, 12)
        self.assertIn("'bk_lvl:' + code + ':' + key", self.SRC)
        self.assertTrue(prefs.LEVEL_KEY.fullmatch("bk_lvl:fa:vocal"))

    def test_the_numbers_are_the_builds(self):
        """vocal=p1, chunks=p2, bare=p3, alt=p4, aloud=p5, exactly tex2html.pass_class."""
        import tex2html
        want = {p: int(tex2html.pass_class({"key": p}).split()[0][1:]) for p in ("vocal", "chunks", "bare", "alt", "aloud")}
        m = re.search(r"var NUMBER = (\{[^}]*\});", self.SRC)
        self.assertEqual(json.loads(re.sub(r"(\w+):", r'"\1":', m.group(1))), want)


class TheBuildAndTheSheet(unittest.TestCase):
    CSS = read(ROOT / "lib" / "mobile.css")

    def test_the_first_line_of_a_phone_is_the_four_and_the_gear(self):
        keep = re.search(r"html\.m-reader\[data-mode=mobile\] header > \.hrow > :not\(([^)]*)\)", self.CSS, re.S)
        kept = {s.strip() for s in keep.group(1).replace("\n", " ").split(",")}
        for there in ("a.home", "#toc", "#typo", "[data-parseh-gear]", ".px-ask"):
            self.assertIn(there, kept)
        order = lambda sel: int(re.search(r"html\.m-reader\[data-mode=mobile\] header %s\{order:(\d+)" % re.escape(sel), self.CSS).group(1))
        self.assertLess(order("#typo"), order("[data-parseh-gear]"))
        self.assertLess(order("[data-parseh-gear]"), order(".px-ask"))
        # the ⋯ menu's rules are gone with it: nothing of the reader's is drawn by group any more
        reader = self.CSS[self.CSS.index("/* ---------------- a book's reader"):self.CSS.index("/* ---------------- THE DOCK")]
        for dead in (".m-rmore", ".m-rlab", ".m-more", ".parseh-mode", "m-empty-g"):
            self.assertNotIn(dead, reader)

    def test_what_the_gear_took_is_hidden_in_both_layouts_and_kept_in_the_dom(self):
        # in lib/parseh.css, which every reader links in its head (so the first paint is right), and not in
        # lib/mobile.css, which is the mobile layout's alone (tests/test_mobile_mode.py holds every rule of it to that)
        base = read(ROOT / "lib" / "parseh.css")
        self.assertIn("html.pg-reader header :is(#stopbnd,#hoverpause,#defmode,#defmt,#lookupset,.m-rskip){", base)
        self.assertIn("html.pg-reader header :is(#listenfollow,#listenscroll):disabled{display:none}", base)
        self.assertIn("html.pg-sheet :is(.pf-bar,.kp-bar){display:none!important}", base)
        self.assertNotIn("pg-reader", self.CSS)
        # the generic rule is parseh.css's; the player's own sheet rules (html.m-player.pg-sheet[data-mode=mobile]) are
        # mobile-only and live in mobile.css (lane D), so only the generic one must not be repeated there
        self.assertNotIn("html.pg-sheet :is(.pf-bar,.kp-bar)", self.CSS)

    def test_the_mobile_layer_draws_no_menu_of_its_own(self):
        js = read(ROOT / "lib" / "mobilereader.js")
        for gone in ("m-rmore", "m-rlab", "GROUPS", "function setMore", "data-bars-held", "parseh-mode"):
            self.assertNotIn(gone, js)
        # but it still makes the switch the gear presses, and says so
        self.assertIn("hpBtn.id = 'hoverpause';", js)

    def test_the_build_writes_names_never_digits(self):
        import tex2html
        for code in shipped():
            tex2html.set_lang(code)
            html = tex2html.pass_buttons()
            names = [p["name"] for p in tex2html.LANG.passes]
            self.assertEqual(re.findall(r'<button data-toggle="no\d" title="[^"]*">([^<]*)</button>', html), names)
            self.assertIn('<span class="pgrpc">levels</span>', html)
            self.assertNotRegex(html, r">\d<")
            self.assertTrue(tex2html.hover_title().startswith("the text alone (the level"), tex2html.hover_title())
            self.assertNotRegex(tex2html.hover_title(), r"\d")


if __name__ == "__main__":
    unittest.main()
