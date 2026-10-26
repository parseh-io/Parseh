#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""THE GEAR OF A DOCUMENT, THE EDITOR AND THE EXERCISES (markdown/app/static/gear.js),
as the files say it.

    python3 -m unittest discover -s tests -p test_gear_studio.py

What the panel DOES on the real pages -- every row changing the page and back,
the bars, the theme across tabs and browsers, the phone's bar in one row, the
widths -- is driven in a real Chromium by tests/gear_studio.mjs.  What is
checked here is what only the SOURCE can say, and what no browser test would
notice until a page was on a phone, offline, or exported:

* the gear's rows are kept by a phone (lib/offline.py's STUDIO_FILES), and the
  studio run alone answers the toolkit's two files for itself;
* each of the five pages loads the toolkit in its head, the rows after the
  scripts that hold what they move, and has ◐ and the gear's place in its bar;
* the pages WITHOUT a gear (the library, the decks' list, a note, the exported
  files) have none of it, and the library and the decks' list keep their switch;
* the sliders that stood in a document's toolbar, the sheet's own theme menu
  and the old typography binders are gone, and the theme has ONE function;
* the plan's names and sentences are the ones in the panel, word for word;
* the harnesses that serve these pages point the toolbox's preferences at
  their temporary tree (the pages load lib/prefs.js now).
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "tests", "."):
    sys.path.insert(0, str(ROOT / p))

APP = ROOT / "markdown" / "app"
STATIC = APP / "static"
TEMPLATES = APP / "templates"


def text(path):
    return Path(path).read_text(encoding="utf-8")


def code(src):
    """The script with its comments taken out, so that what a comment says about
    a thing is never taken for the thing."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(^|\s)//[^\n]*", r"\1", src)


def flat(src):
    """The strings as they read: \\uXXXX escapes made characters, "a" + "b" made "ab"."""
    src = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), src)
    src = re.sub(r'"\s*\+\s*"', "", src)
    src = re.sub(r'`\s*\+\s*`', "", src)
    return re.sub(r"'\s*\+\s*'", "", src)


def scripts(html):
    """[(src, the rest of the tag)] of the page's script tags, in the order they are written."""
    return [(m.group(2), (m.group(1) + m.group(3)).strip())
            for m in re.finditer(r'<script([^>]*?)\ssrc="([^"]+)"([^>]*)>', html)]


GEAR_PAGES = ("doc.html", "edit.html", "deck.html", "study.html", "cram.html")


class ServedAndKept(unittest.TestCase):

    def test_a_phone_keeps_the_rows_and_the_toolkit(self):
        import offline
        self.assertIn("/static/gear.js", offline.STUDIO_FILES,
                      "a kept page without its rows has a button that does nothing")
        for f in ("/lib/pagesettings.js", "/lib/pagesettings.css", "/lib/prefs.js"):
            self.assertIn(f, offline.SHARED, f)

    def test_the_studios_own_files_are_weighed_and_gear_js_is_there(self):
        import offline
        urls = [e["url"] for e in offline.studio_files("/studio")]
        self.assertIn("/studio/static/gear.js", urls)
        self.assertTrue((STATIC / "gear.js").is_file())

    def test_the_toolbox_serves_the_toolkit(self):
        import serve
        for f in ("/lib/pagesettings.js", "/lib/pagesettings.css", "/lib/prefs.js"):
            self.assertTrue(serve.static_ok(f), f)

    def test_the_studio_run_alone_answers_the_toolkits_two_files(self):
        import server
        src = text(APP / "server.py")
        self.assertIn(r'r"^/lib/(pagesettings\.(?:js|css)|pagezoom\.js)$"', src)
        self.assertIn("serve_gear_file", src)
        self.assertTrue(any(re.match(p, "/lib/pagesettings.js") for m, p, f in server.ROUTES if f.__name__ == "serve_gear_file"))
        self.assertTrue(any(re.match(p, "/lib/pagesettings.css") for m, p, f in server.ROUTES if f.__name__ == "serve_gear_file"))
        self.assertFalse(any(re.match(p, "/lib/pagesettings.py") for m, p, f in server.ROUTES if f.__name__ == "serve_gear_file"),
                         "and nothing else of lib/")


class EachPageLoadsTheGearRight(unittest.TestCase):

    def test_the_toolkit_is_in_the_head_and_not_deferred(self):
        for name in GEAR_PAGES:
            html = text(TEMPLATES / name)
            head = html[:html.index("</head>")]
            tag = re.search(r'<script src="/lib/pagesettings\.js"([^>]*)></script>', head)
            self.assertTrue(tag, name + ": the toolkit is in the head")
            self.assertEqual(tag.group(1), "", name + ": and is not deferred, so that its sheet is on its way at once")
            prefs = re.search(r'<script src="/lib/prefs\.js"([^>]*)></script>', head)
            self.assertTrue(prefs, name + ": lib/prefs.js is loaded, so that the theme follows a person")
            self.assertEqual(prefs.group(1), "", name + ": and not deferred: gear.js asks at once whether it is there")
            self.assertLess(head.index("/lib/pagesettings.js"), head.index("/lib/prefs.js"), name)

    def test_the_rows_come_after_the_scripts_that_hold_what_they_move(self):
        for name in GEAR_PAGES:
            html = text(TEMPLATES / name)
            srcs = [s for s, a in scripts(html)]
            gear = [s for s in srcs if s.endswith("/static/gear.js")]
            self.assertEqual(len(gear), 1, name)
            at = srcs.index(gear[0])
            for held in ("app.js", "decks.js", "editor.js", "exform.js"):
                for i, s in enumerate(srcs):
                    if s.endswith("/static/" + held):
                        self.assertLess(i, at, "%s: %s holds what the rows move, and loads first" % (name, held))
            self.assertTrue(gear[0].startswith("{{STUDIO}}/static/"), name + ": at the studio's own address, as app.js is")
            tag = re.search(r'<script src="%s"([^>]*)>' % re.escape(gear[0]), html)
            self.assertEqual(tag.group(1), "", name + ": not deferred: the page is complete when it runs")

    def test_a_browser_bar_has_theme_then_gear_in_a_box_that_stays_on_the_screen(self):
        for name in GEAR_PAGES:
            html = text(TEMPLATES / name)
            start = html.index('<header class="topbar"')
            bar = html[start:html.index("</header>", start)]
            tail = re.search(r'<span class="bar-tail">(.*?)</span>', bar, re.S)
            self.assertTrue(tail, name)
            self.assertIn("data-parseh-theme", tail.group(1), name + ": ◐ is in the box")
            self.assertIn("◐", tail.group(1), name)
            self.assertNotIn("data-parseh-gear", tail.group(1), name + ": the gear is put after it by the toolkit, not written")
            # and it is the last thing of the row: nothing is written after it
            row = bar[bar.index('<div class="topbar-actions"'):]
            self.assertRegex(row, r'</span>\s*</div>\s*$', name + ": and the box is the last of the row")

    def test_a_document_and_a_deck_have_their_gear_after_the_theme_on_the_phones_bar_and_no_switch(self):
        for name in ("doc.html", "deck.html"):
            html = text(TEMPLATES / name)
            bar = html[html.index('<header class="m-topbar"'):]
            bar = bar[:bar.index("</header>")]
            self.assertNotIn("MODE_SWITCH", bar, name + ": the Browser | Mobile switch is in the gear's Interface group")
            self.assertNotIn("data-parseh-mode", bar, name)
            self.assertIn("data-parseh-theme", bar, name + ": ◐ stays")
            self.assertIn('class="m-up"', bar, name + ": the way up stays")

    def test_studying_and_cramming_have_no_bar_on_a_phone_and_the_gear_goes_in_the_title_row(self):
        for name in ("study.html", "cram.html"):
            html = text(TEMPLATES / name)
            self.assertNotIn("m-topbar", html, name + ": no bar over the exercise on a phone")
            self.assertNotIn("MODE_SWITCH", html, name + ": and so no switch")
            self.assertIn('class="dk-studyhead"', html, name + ": the title's row is where the gear stands")
        gear = text(STATIC / "gear.js")
        self.assertIn('first(".m-topbar", ".dk-studyhead")', gear)

    def test_the_pages_without_a_gear_have_none_and_keep_their_switch(self):
        for name in ("index.html", "decks.html"):
            html = text(TEMPLATES / name)
            self.assertIn("{{MODE_SWITCH}}", html, name + ": the visible switch stays where there is no gear")
            for never in ("pagesettings", "gear.js", "prefs.js", "bar-tail"):
                self.assertNotIn(never, html, name + ": no " + never)
            self.assertIn("data-parseh-theme", html, name + ": ◐ stays (and is app.js's, like every page's)")
        for name in ("note.html", "export_doc.html", "export_deck.html", "prompt.html", "404.html"):
            html = text(TEMPLATES / name)
            for never in ("pagesettings", "gear.js", "prefs.js", "bar-tail", "data-parseh-gear"):
                self.assertNotIn(never, html, name + ": no " + never)


class TheDocumentsToolbar(unittest.TestCase):

    def setUp(self):
        self.html = text(TEMPLATES / "doc.html")
        self.bar = self.html[self.html.index('id="typobar"'):self.html.index('<div class="layout">')]

    def test_the_sliders_the_tick_the_menu_and_the_reset_are_gone(self):
        for gone in ("sl-fa", "sl-base", "sl-width", "sl-lead", "sl-voce", "out-fa", "ck-justify", "sel-theme",
                     "btn-typo-reset", "typo-group", "lbl-fa", "Back to the PDF defaults"):
            self.assertNotIn(gone, self.html, gone)

    def test_it_keeps_contents_glosses_linked_from_the_keep_slot_print_and_the_bars(self):
        for kept in ('id="btn-toc"', 'id="btn-glosses"', 'id="btn-backlinks"', 'data-keep-slot="btn ghost"',
                     'id="btn-print"', 'id="btn-bars"', 'id="btn-bars-show"'):
            self.assertIn(kept, self.html, kept)

    def test_aa_stays_and_opens_the_gear(self):
        self.assertIn('id="btn-typo"', self.bar)
        self.assertRegex(self.bar, r'id="btn-typo"[^>]*>Aa</button>')

    def test_the_bars_buttons_are_named_hide_and_show(self):
        self.assertRegex(self.html, r'id="btn-bars"[^>]*>⌃ hide bars</button>')
        self.assertRegex(self.html, r'id="btn-bars-show"[^>]*>⌄ show bars</button>')
        self.assertNotIn("⌃ bars<", self.html)
        self.assertNotIn("⌄ bars<", self.html)


class TheScriptsHaveOneOfEach(unittest.TestCase):

    def setUp(self):
        self.app = text(STATIC / "app.js")
        self.appc = code(self.app)
        self.mode = text(STATIC / "mode.js")
        self.decks = text(STATIC / "decks.js")
        self.gear = text(STATIC / "gear.js")

    def test_the_old_binders_are_gone(self):
        for gone in ("bindTypoControls", "bindTypoToggle", "typo-open", "#sl-fa", "#sel-theme", "#btn-typo-reset", "#ck-justify"):
            self.assertNotIn(gone, self.appc, gone)
        css = text(STATIC / "app.css")
        self.assertNotIn("typo-open", css)
        self.assertNotIn(".typo-group", css)

    def test_the_typography_has_one_state_the_gear_the_pages_and_the_pdf_share(self):
        self.assertIn("const studioTypo = (() => {", self.appc)
        self.assertIn("window.ParsehStudioTypo = studioTypo;", self.appc)
        for member in ("use(docId)", "get: () => loadTypo(id)", "set(patch)", "reset()", "refresh()", "subscribe(fn)"):
            self.assertIn(member, self.appc, member)
        # the keys are the ones they always were, and a document writes both
        self.assertIn('localStorage.setItem("exlex-typo:global", JSON.stringify(out));', self.appc)
        self.assertIn('if (id) localStorage.setItem("exlex-typo:" + id, JSON.stringify(out));', self.appc)
        # the PDF is built at the same scale
        self.assertIn("const getTypo = studioTypo.get;", self.appc)
        self.assertIn("json: {scale: t.fa,", self.appc)
        # the exercise pages edit the shared key alone
        self.assertIn('studioTypo.use(PAGE === "doc" || PAGE === "edit" ? DOC_ID : null);', self.appc)

    def test_a_theme_an_older_build_wrote_into_the_sheets_record_is_not_read(self):
        load = re.search(r"function loadTypo\(id\) \{.*?\n\}\n", self.appc, re.S).group(0)
        self.assertNotIn('"theme" in saved', load)
        self.assertNotIn("chosen", load)
        self.assertIn("t.theme = sharedSheetTheme();", load)
        save = re.search(r"function saveTypo\(id, t\) \{.*?\n\}\n", self.appc, re.S).group(0)
        self.assertIn("delete out.theme;", save)

    def test_the_theme_has_one_function_and_the_other_two_scripts_have_none(self):
        self.assertEqual(self.app.count("function cycleTheme()"), 1)
        self.assertEqual(self.app.count("function paintTheme()"), 1)
        for name, src in (("mode.js", self.mode), ("decks.js", self.decks)):
            c = code(src)
            for gone in ("cycleTheme", "paintTheme", "THEME_GLYPH", "shownTheme"):
                self.assertNotIn(gone, c, "%s must not keep a theme of its own: %s" % (name, gone))
            self.assertNotIn("data-parseh-theme", c, name)
            self.assertNotIn("html.setAttribute('data-theme'", c)
        # what changes it all ends in paintTheme: ◐, the storage event, the computer's value, the pageshow, the system
        boot = re.search(r"function bindStudioLook\(\) \{.*?\n\}\n", self.appc, re.S).group(0)
        for heard in ('[data-parseh-theme]', '"storage"', '"parseh:pref"', '"pageshow"', "prefers-color-scheme: dark"):
            self.assertIn(heard, boot, heard)
        self.assertEqual(boot.count("paintTheme()"), 5, "each of the five ends in it")
        # it dresses <html> as parseh.js does, and <body>, where the sheet's themes are keyed
        paint = re.search(r"function paintTheme\(\) \{.*?\n\}\n", self.appc, re.S).group(0)
        self.assertIn('removeAttribute("data-theme")', paint)
        self.assertIn('setAttribute("data-theme", stored)', paint)
        self.assertIn("studioTypo.refresh();", paint)
        # and every page of the studio takes it, the library and the prompt page too
        self.assertIn("bindStudioLook();", self.appc)

    def test_the_glyphs_and_the_words_are_the_toolboxs_own(self):
        js = text(ROOT / "lib" / "parseh.js")
        self.assertIn("var GLYPH = { light: '○', dark: '●', sepia: '◐' };", js)
        self.assertIn('const THEME_GLYPH = {light: "○", dark: "●", sepia: "◐"};', self.app)
        self.assertIn("var ORDER = ['light', 'dark', 'sepia'];", js)
        self.assertIn('const THEME_ORDER = ["light", "dark", "sepia"];', self.app)
        self.assertIn('(following the system)', self.app)
        self.assertIn("click for ${next}", self.app)

    def test_both_scripts_that_know_the_mode_offer_it_to_the_gear(self):
        self.assertIn("window.ParsehStudioMode = {get: now, set: set, isMobile: isMobile};", self.mode)
        self.assertIn("window.ParsehStudioMode = {get: modeNow, set: modeSet, isMobile};", self.decks)

    def test_the_two_exercise_switches_are_one_state_each(self):
        self.assertIn("function setTransliterationsHidden(v) {", self.appc)
        self.assertIn("function showTransliterationChoice() {", self.appc)
        self.assertIn("setTransliterationsHidden(!hideExerciseTransliterations);", self.appc, "the card's own button goes through it")
        self.assertIn('document.dispatchEvent(new CustomEvent("parseh:studio", {detail: {what: "drag"}}));', self.appc)
        self.assertIn('listen(document, "parseh:studio", e => {', self.appc, "every sheet bound hears the drag")
        self.assertIn("function setBarsOff(v)", self.appc)
        self.assertIn('detail: {what: "bars"}', self.appc)

    def test_the_export_carries_the_switches_and_none_of_the_gear(self):
        import webexport
        js = webexport._runtime()
        for needed in ("function setTransliterationsHidden", "function showTransliterationChoice", "function applyTypo"):
            self.assertIn(needed, js)
        for never in ("studioTypo", "ParsehStudioTypo", "paintTheme", "bindStudioLook", "ParsehGear", "setBarsOff"):
            self.assertNotIn(never, js, never)

    def test_the_editor_offers_its_direction_to_the_gear_without_the_cursor(self):
        ed = text(STATIC / "editor.js")
        self.assertIn("window.ParsehStudioEditorDir = {", ed)
        self.assertIn("function setEditorDir(rtl, keepFocusInSource)", ed)
        self.assertIn("setEditorDir(src.dir !== \"rtl\", true)", ed, "the button keeps the cursor in the box it turned")
        self.assertIn("set: rtl => setEditorDir(!!rtl, false)", ed, "the gear's switch keeps the keyboard where it is")


class TheRowsAreThePlans(unittest.TestCase):
    """The names and the sentences of plan §6, word for word, and the groups in its order."""

    def setUp(self):
        self.raw = text(STATIC / "gear.js")
        self.js = code(self.raw)
        self.flat = flat(self.js)

    def test_no_html_is_built_from_a_string_and_no_code_either(self):
        for never in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            self.assertNotIn(never, self.js, never)
        self.assertNotRegex(self.js, r"\beval\s*\(")

    def test_the_toolkit_is_asked_for_and_without_it_the_page_still_works(self):
        self.assertIn("if (!window.ParsehGear) {", self.js)
        self.assertIn("if (aa) aa.hidden = true;", self.js)
        self.assertIn("G.mount(spec)", self.js)

    def test_the_groups_of_each_page_in_the_plans_order(self):
        # a document: Text, Exercises, Page, Zoom, Colours, Interface
        self.assertIn('textGroup(true), exercisesGroup(), pageGroup(), G.std.zoom(), colours(), G.std["interface"]()', self.js)
        # the editor: Text, Zoom, Colours, direction -- and no Interface, nor a phone layout
        self.assertIn('textGroup(true), G.std.zoom(), colours(), editorGroup()', self.js)
        self.assertIn("spec.mobileMode = () => false;", self.js)
        # a deck, studying it, cramming it: Text (four rows), Exercises, Zoom, Colours, Interface
        self.assertIn('textGroup(false), exercisesGroup(), G.std.zoom(), colours(), G.std["interface"]()', self.js)

    def test_the_text_rows(self):
        f = self.flat
        for needle in (
            'label: () => nameOf() + " text size"',
            "How big the ${nameOf()} text is compared with the Latin text around it (1× = the same size). ",
            "The PDF you build uses the same size.",
            'label: "Latin text size"',
            "How big the Latin-script text (the explanations around the ${nameOf()}) is, from 13 to 23 pixels.",
            "The text width follows it unless you set the width yourself.",
            'label: "Text width"',
            "How wide the column of text may grow on a wide screen; on a narrow screen it always fits.",
            'label: "Line spacing"',
            "The space between lines: 1 is the usual, more is airier.",
            'label: "Headword size"',
            "How big the word at the top of each dictionary-style entry is, as a multiple of the text size.",
            'label: "Justify the text"',
            "Straight left and right edges, with words hyphenated at line ends, the way the PDF sets it.",
            'label: "Put the text back to normal"',
        ):
            self.assertIn(needle, f, needle)
        # the ranges the toolbar's sliders had, unchanged
        for rng in ("min: 0.8, max: 2.6, step: 0.02", "min: 13, max: 23, step: 0.5", "min: 420, max: 1400, step: 1",
                    "min: 1.15, max: 2, step: 0.05", "min: 2.2, max: 4.6, step: 0.1"):
            self.assertIn(rng, f, rng)
        # the pages of exercises: four rows, no width and no headwords, and the reset is the document's
        self.assertEqual(f.count("if (full) rows.push("), 3, "width, headword size and the reset are the documents' alone")
        self.assertIn('(full ? "The PDF you build uses the same size." : "Documents use the same size.")', f)

    def test_the_exercises_the_page_and_the_editor(self):
        f = self.flat
        for needle in (
            'label: "Hide transliterations"',
            "Hides the line that spells how a word sounds in Latin letters on every exercise flashcard, so you read the script itself.",
            'label: "Drag to answer"',
            "Lets you drag words into place in exercises that offer it. Off by default on a touch screen, where tapping is easier.",
            'label: "Hide the bars"',
            "Puts the header away so the text has the whole window; a small ⌄ at the top corner brings it back.",
            'label: "Write the source right to left"',
            "Which way the source text box runs, for a right-to-left language. Remembered for this document.",
        ):
            self.assertIn(needle, f, needle)
        self.assertIn('id: "text", title: "Text"', f)
        self.assertIn('id: "exercises", title: "Exercises"', f)
        self.assertIn('id: "page", title: "Page"', f)
        self.assertIn('id: "editor", title: "Editor"', f)

    def test_each_group_says_where_its_settings_are_kept(self):
        self.assertIn('const SAVED = "Saved on this device.";', self.js)
        self.assertGreaterEqual(self.js.count("caption: SAVED"), 3)
        self.assertIn('caption: "Saved on this device, for this document."', self.js)

    def test_the_theme_is_the_pages_one_function_and_the_truth_is_told_about_where_it_follows(self):
        self.assertIn("G.std.colours({apply: () => paintTheme()})", self.js)
        self.assertIn("if (!window.ParsehPrefs) g.caption = SAVED;", self.js)
        self.assertIn("if (!window.ParsehPrefs) spec.titles = {foot: false};", self.js)

    def test_aa_opens_the_gear_at_text_and_a_second_press_shuts_it(self):
        self.assertIn('gear.open("text")', self.js)
        # what the press found is read in the capture phase: the toolkit shuts a popover on the outside click first
        self.assertRegex(self.js, r'document\.addEventListener\("click", e => \{\s*if \(e\.target\.closest && e\.target\.closest\("#btn-typo"\)\) \{')
        # and, on the phone's sheet, "at Text" is the theme on stage (a0.5.4): the person may have gone to another
        self.assertIn('foundUp = gear.isOpen();', self.js)
        self.assertIn('foundAt = st !== null && st !== undefined ? (st === "text" ? "text" : "") : at;', self.js)
        self.assertIn('if (foundUp && foundAt === "text") { if (gear.isOpen()) gear.close(); return; }', self.js)

    def test_the_button_stands_in_the_bar_that_is_on_the_screen(self):
        self.assertIn('first(".topbar .bar-tail", ".topbar .topbar-actions", ".topbar")', self.js)
        self.assertIn('document.documentElement.getAttribute("data-mode") === "mobile"', self.js, "the layout in force, which the page's own head says")

    def test_the_top_of_the_file_says_what_it_is(self):
        head = self.raw[:self.raw.index("(function () {")]
        for said in ("a document", "the editor", "Text (four rows)", "parseh:studio", "Aa", "Browser | Mobile switch"):
            self.assertIn(said, head, said)


class TheSheetsIndexSaysWhatEachThemeIsSetTo(unittest.TestCase):
    """a0.5.4: the summaries of the phone's list of themes."""

    def setUp(self):
        self.js = code(text(STATIC / "gear.js"))

    def test_the_switches_have_short_names(self):
        for short in ('short: "transliterations hidden"', 'short: "drag"', 'short: "bars hidden"', 'short: "right to left"',
                      'short: "own tab"', 'short: "justified"'):
            self.assertIn(short, self.js, short)

    def test_the_text_theme_says_its_first_slider(self):
        self.assertIn("const summary = () => `${nameOf()} text ${T.get().fa.toFixed(2)}×`;", self.js)
        self.assertIn('return {id: "text", title: "Text", caption: SAVED, summary, rows};', self.js)


class TheCssBetweenThePages(unittest.TestCase):

    def test_the_tail_is_pinned_where_the_row_scrolls_and_is_a_fingers_size_on_a_phone(self):
        css = text(STATIC / "app.css")
        self.assertRegex(css, r"\.bar-tail \{[^}]*position: sticky; right: 0;")
        self.assertIn("scroll-padding-inline-end: 7rem;", css)
        self.assertRegex(css, r"@media \(max-width: 560px\), \(pointer: coarse\) \{\s*\.bar-theme \{ min-width: 48px; min-height: 48px; \}\s*\}")

    def test_the_exercise_pages_bar_wraps_where_it_would_be_wider_than_a_phone(self):
        css = text(STATIC / "app.css")
        self.assertRegex(css, r'@media \(max-width: 560px\) \{\s*body:is\(\[data-page="deck"\], \[data-page="study"\], \[data-page="cram"\]\) \.topbar \{ flex-wrap: wrap;')

    def test_hiding_the_bars_hides_the_phones_bar_too_so_the_way_back_is_not_over_the_gear(self):
        css = text(STATIC / "app.css")
        self.assertRegex(css, r"body\.chrome-off \.topbar,\s*body\.chrome-off \.m-topbar,")

    def test_the_older_than_the_computer_line_waits_for_the_sheet(self):
        self.assertIn("html.pg-sheet .kp-bar{display:none}", text(STATIC / "app.css"))

    def test_aa_is_shown_on_every_width(self):
        css = text(STATIC / "app.css")
        self.assertNotIn(".typo-toggle { display: none; }", css)
        self.assertIn('.typo-toggle[aria-expanded="true"]', css)

    def test_the_phones_bar_is_one_row_with_the_room_given_to_the_squares(self):
        css = text(STATIC / "mobile.css")
        self.assertIn("@media (max-width:430px){", css)
        self.assertIn("body:is([data-page=doc],[data-page=deck]) .m-topbar .m-home .word", css)
        self.assertIn("@media (max-width:399px){", css)
        self.assertIn("body:is([data-page=doc],[data-page=deck]) .m-topbar .m-up .word", css)
        self.assertNotIn("[data-page=cram]) .m-topbar{display:none}", css, "no bar on those pages to hide")
        self.assertIn("html[data-mode=mobile] .dk-studyhead .pg-gear{flex:none;", css)


class TheHarnessesDoNotTouchTheOwnersPreferences(unittest.TestCase):
    """The pages load lib/prefs.js now, which sends the theme to /__prefs: a suite that presses ◐ through a
    harness that serves them must have pointed prefs.STORE at its own tree (tests/configguard.py's rule)."""

    def test_every_harness_that_serves_these_pages_redirects_it(self):
        for name in ("studio_harness.py", "decks_harness.py", "doclinks_harness.py", "cardkit_harness.py"):
            src = text(ROOT / "tests" / name)
            self.assertRegex(src, r"prefs\.STORE\s*=", name)
        self.assertRegex(text(ROOT / "tests" / "decks.mjs"), r"prefs\.STORE = str\(tmp / \"config\" / \"prefs\.json\"\)")


if __name__ == "__main__":
    unittest.main()
