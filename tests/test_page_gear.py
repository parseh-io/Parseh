#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""THE GEAR, ⚙ page (lib/pagesettings.js, lib/pagesettings.css), as the files say it.

    python3 -m unittest discover -s tests -p test_page_gear.py

What the panel DOES -- every kind of row, the button and where it stands, the
popover and the phone's sheet, Esc, the back gesture, the mode and the theme,
the zoom's stub and a page really zoomed -- is driven in a real Chromium by
tests/page_gear.mjs.  What is checked here is what only the SOURCE can say, and
what no browser test would notice until a page was on a phone or offline:

* the toolbox serves the two files and a phone keeps them (a kept page whose
  ⚙ is in no offline list opens away from the computer and does nothing);
* the layer builds nothing with innerHTML, in the way tests/test_mobile_pages.py
  pins for the mobile layer: a row's words may come from a book;
* the contract of plan §9 is all there under its own names -- the nine kinds and
  the one the integrator added (node), the three standard groups, the button's
  words, the panel's words, the foot link, the sentences the owner approved;
* the sheet of styles is written in the tokens of whichever sheet is in force,
  with a fallback behind each, in classes of its own (pg-), with no viewport unit
  anywhere (the zoom module takes those apart), a finger's 48px, reduced motion.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "tests", "."):
    sys.path.insert(0, str(ROOT / p))

JS = ROOT / "lib" / "pagesettings.js"
CSS = ROOT / "lib" / "pagesettings.css"


def code(src):
    """The script with its comments taken out, so that what a comment says about
    a thing is never taken for the thing."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(^|\s)//[^\n]*", r"\1", src)


def flat(src):
    """The script's strings as they read: \\uXXXX escapes made characters and
    "a" + "b" made "ab" -- the plan's sentences are pinned as the owner reads them."""
    src = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), src)
    src = re.sub(r'"\s*\+\s*"', "", src)
    return re.sub(r"'\s*\+\s*'", "", src)


class ServedAndKeptTests(unittest.TestCase):

    def test_both_files_are_there(self):
        self.assertTrue(JS.is_file())
        self.assertTrue(CSS.is_file())

    def test_the_toolbox_serves_both(self):
        import serve
        for f in ("/lib/pagesettings.js", "/lib/pagesettings.css"):
            self.assertIn(f, serve.STATIC_FILES)
            self.assertTrue(serve.static_ok(f), f)

    def test_a_phone_keeps_both(self):
        import offline
        for f in ("/lib/pagesettings.js", "/lib/pagesettings.css"):
            self.assertIn(f, offline.SHARED, "a kept page must open away from the computer WITH its gear")

    def test_the_script_links_its_sheet_from_beside_itself(self):
        # as lib/explain.js and the loaders in lib/parseh.js find what is beside them: by the address the
        # script itself was loaded by, found while it runs (currentScript is nothing a moment later)
        src = code(JS.read_text(encoding="utf-8"))
        self.assertIn("document.currentScript", src)
        self.assertIn("pagesettings\\.js(?=[?#]|$)", src)
        self.assertIn("'pagesettings.css'", src)
        self.assertIn("'/lib/pagesettings.css'", src, "and the toolbox's own address where there is no src to go by")
        self.assertIn("data-pg-style", src, "one link, however many times it is asked for")


class NothingIsBuiltFromAString(unittest.TestCase):
    """The panel is made with createElement and textContent: a level's name, a
    book's own words, are what a row may carry."""

    def setUp(self):
        self.js = code(JS.read_text(encoding="utf-8"))

    def test_no_innerhtml_anywhere(self):
        self.assertNotIn("innerHTML", self.js)
        self.assertNotIn("outerHTML", self.js)
        self.assertNotIn("insertAdjacentHTML", self.js)
        self.assertNotIn("createContextualFragment", self.js)
        self.assertNotIn("DOMParser", self.js)
        self.assertNotIn("document.write", self.js)

    def test_not_even_the_comments_name_innerhtml_as_a_thing_in_use(self):
        # the whole file, comments and all, never says it assigns one
        whole = JS.read_text(encoding="utf-8")
        self.assertNotRegex(whole, r"\.innerHTML\s*=")

    def test_no_code_is_made_from_a_string(self):
        self.assertNotRegex(self.js, r"\beval\s*\(")
        self.assertNotRegex(self.js, r"new\s+Function\b")
        self.assertNotRegex(self.js, r"set(?:Timeout|Interval)\s*\(\s*['\"]")

    def test_words_are_set_as_text(self):
        self.assertGreater(self.js.count("textContent"), 10)

    def test_no_style_is_written_as_a_string_either(self):
        # a page with a strict content-security-policy would refuse it; the CSSOM it is allowed
        self.assertNotIn("setAttribute('style'", self.js)
        self.assertNotIn("cssText", self.js)


class TheContractIsAllThere(unittest.TestCase):

    def setUp(self):
        self.raw = JS.read_text(encoding="utf-8")
        self.js = code(self.raw)
        self.flat = flat(self.js)

    def test_the_kinds(self):
        for kind in ("switch", "choice", "slider", "stepper", "levels", "link", "buttons", "action", "note", "node"):
            self.assertRegex(self.js, r"KINDS(?:\.%s|\['%s'\])\s*=\s*function" % (kind, kind), kind)
        # and no kind the contract does not name
        names = re.findall(r"KINDS(?:\.(\w+)|\['(\w+)'\])\s*=\s*function", self.js)
        self.assertEqual(10, len(names))

    def test_the_api(self):
        self.assertIn("window.ParsehGear = {", self.js)
        for name in ("mount: mount", "mounted: function () { return current; }", "std: std"):
            self.assertIn(name, self.js)
        for name in ("open: open", "toggle: toggle", "isOpen: function", "refresh: function", "onToggle: function",
                     "button: btn", "unmount: unmount"):
            self.assertIn(name, self.js, "the handle: " + name)
        self.assertIn("close: function () { close('page'); }", self.js)

    def test_the_standard_groups(self):
        for name in (r"zoom:\s*function \(\)", r"colours:\s*function \(o\)", r"'interface':\s*function \(\)"):
            self.assertRegex(self.js, name)

    def test_the_sentences_of_the_plan_as_the_owner_reads_them(self):
        f = self.flat
        for sentence in (
                "Makes everything on the page bigger or smaller together — bars, buttons, clouds, sheets. "
                "A computer's own Ctrl + and Ctrl − do the same; the installed app cannot.",
                "The colours of every Parseh page. 'Follow my device' uses your phone's or computer's own "
                "light or dark setting.",
                "Browser: every page, with everything that edits. Mobile: pages made for a phone, "
                "to read and to study, with nothing that edits.",
                "Saved on this device, for all of Parseh.",
                "Follows you to your other devices.",
                "Saved on this device.",
                "Parseh's own settings (network, updating, dictionaries)",
                "Only for this page.",
                "Settings of this page: how it looks, how it reads, how it zooms",
                ):
            self.assertIn(sentence, f)

    def test_the_button(self):
        s = self.js
        self.assertIn("'data-parseh-gear': ''", s)
        self.assertIn("'aria-haspopup': 'dialog'", s)
        self.assertIn("'aria-expanded': 'false'", s)
        self.assertIn("'aria-label': BUTTON_LABEL", s)
        self.assertIn("var BUTTON_LABEL = 'Settings of this page';", s)
        self.assertIn("el('span', 'pg-gear-glyph', '\\u2699')", s)
        self.assertIn("el('span', 'pg-gear-word', 'page')", s)
        self.assertIn("{ 'aria-hidden': 'true' }", s)

    def test_the_panel(self):
        s = self.js
        self.assertIn("role: 'dialog'", s)
        self.assertIn("'aria-label': BUTTON_LABEL", s)
        self.assertIn("dir: 'ltr', lang: 'en'", s, "the chrome is English and left to right, in any page")
        self.assertIn("title: 'close (Esc)'", s)
        self.assertIn("title: 'This page'", s)
        self.assertIn("href: '/settings/'", s)
        self.assertIn("var SHEET_MAX = 560;", s, "a window this narrow gets the sheet")
        self.assertIn("var POP_W = 380;", s)

    def test_the_level_name_field_takes_the_direction_of_what_is_typed(self):
        self.assertIn("dir: 'auto'", self.js)
        self.assertIn("var NAME_MAX = 12;", self.js)
        self.assertIn("maxlength: String(NAME_MAX)", self.js)

    def test_the_roles_and_the_keys(self):
        s = self.js
        for needle in ("role: 'switch'", "role: 'radiogroup'", "role: 'radio'", "'aria-checked'", "'aria-pressed'",
                       "'aria-describedby'", "'aria-labelledby'", "'aria-valuetext'", "'aria-live'", "e.key !== 'Escape'",
                       "e.key === 'ArrowRight'", "e.key === 'ArrowLeft'", "e.key === 'ArrowDown'", "e.key === 'ArrowUp'",
                       "e.key === 'Home'", "e.key === 'End'", "e.key === 'Enter'"):
            self.assertIn(needle, s)

    def test_escape_is_spent_on_the_panel_and_not_on_a_composition(self):
        s = self.js
        body = s[s.index("function onKey(e)"):s.index("function onClick(e)")]
        self.assertIn("e.defaultPrevented", body, "an Esc a layer above spent is not spent again")
        self.assertIn("e.isComposing", body, "an Esc that cancels an IME composition is not the panel's")
        self.assertIn("e.preventDefault();", body)

    def test_keys_typed_in_the_panel_go_no_further(self):
        # a reader plays on Space and moves on the arrows on anything but a text box: not for a switch
        s = self.js
        for needle in ("panel.addEventListener('keydown', function (e) {", "panel.addEventListener('keyup', function (e) { e.stopPropagation(); });",
                       "panel.addEventListener('keypress', function (e) { e.stopPropagation(); });"):
            self.assertIn(needle, s)
        body = s[s.index("panel.addEventListener('keydown', function (e) {"):s.index("panel.addEventListener('keyup'")]
        self.assertIn("close('key');", body, "Escape closes it from inside, and then stops there")
        self.assertIn("e.stopPropagation();", body)
        # and the keys that press the button are the button's own
        self.assertIn("btn.addEventListener('keydown', function (e) { if (e.key === ' ' || e.key === 'Enter') e.stopPropagation(); });", s)

    def test_the_sheet_has_a_history_entry_of_its_own(self):
        s = self.js
        self.assertIn("var HIST = 'parsehGear';", s)
        self.assertIn("history.pushState({ parsehGear: id }, '')", s)
        self.assertIn("history.back()", s)
        self.assertIn("window.addEventListener('popstate', onPop);", s)
        # wired ONCE and let go only with the gear: the popstate a spent entry answers with arrives after the
        # sheet has gone, and a listener taken off with it would leave the next back gesture swallowed
        shut = s[s.index("function close(how)"):s.index("function toggle()")]
        self.assertNotIn("popstate", shut)

    def test_the_outside_click_is_heard_in_the_capture_phase_from_the_path(self):
        s = self.js
        self.assertIn("document.addEventListener('click', onClick, true);", s)
        self.assertIn("pathOf(e)", s)

    def test_the_mode_and_the_theme(self):
        s = self.js
        self.assertIn("'parseh_mode'", s)
        self.assertIn("'parseh_theme'", s)
        self.assertIn("'parseh_mode=' + m + '; Path=/; SameSite=Lax; Max-Age=31536000'", s)
        self.assertIn("document.documentElement.setAttribute('data-mode', m);", s)
        self.assertIn("new CustomEvent('parseh:mode'", s)
        self.assertIn("P.mode.set(m)", s)
        self.assertIn("P.theme.set(t)", s)
        self.assertIn("'data-theme'", s)

    def test_the_zoom_is_the_modules_and_is_not_drawn_without_it(self):
        s = self.js
        self.assertIn("window.ParsehZoom", s)
        self.assertIn("when: function () { return !!zoomOf(); }", s)
        for member in ("z.STEPS", "z.applied", "z.set(v)", "z.can(dir)", "z.reset()", "z.onChange(cb)"):
            self.assertIn(member, s)
        self.assertIn("'parseh:zoom'", s)

    def test_nothing_is_placed_from_anything_a_zoomed_page_does_not_speak(self):
        # placed from getBoundingClientRect, the root's clientWidth and clientHeight and the panel's own size,
        # as Parseh.typo places its panel (lib/pagezoom.js makes those speak the page's own pixels) -- and
        # never from the window's own, nor a media query, nor a viewport unit
        s = self.js
        self.assertIn("function vw() { return document.documentElement.clientWidth || window.innerWidth; }", s)
        self.assertIn("function vh() { return document.documentElement.clientHeight || window.innerHeight; }", s)
        self.assertEqual(1, s.count("innerWidth"))
        self.assertEqual(1, s.count("innerHeight"))
        self.assertNotIn("matchMedia", s)
        self.assertNotRegex(s, r"[0-9.]\s*(?:vw|vh|vmin|vmax|dvh|dvw|svh|svw|lvh|lvw)\b")
        self.assertIn("'--pg-vh'", s)
        self.assertIn("panel.offsetHeight", s)
        self.assertIn("btn.getBoundingClientRect()", s)

    def test_the_four_additions_of_the_integrator(self):
        s = self.js
        # node: moved in while the panel is up, put back to the same place when it is not
        self.assertIn("KINDS.node = function", s)
        self.assertIn("document.createComment('pg')", s, "a mark keeps the place whatever else is moved meanwhile")
        self.assertIn("insertBefore(n, mark)", s)
        self.assertIn("x.isUp()", s)
        self.assertIn("has: function () { return !!resolve(); }", s, "an el() that answers null is a row that is not drawn")
        # indent, and what disabled() is told of the row above
        self.assertIn("data-pg-indent", s)
        self.assertIn("safe(row.disabled, above ? above.state() : undefined)", s)
        self.assertIn("state: function () { return !!safe(row.get); }", s, "a switch says whether it is on")
        # mounted(), and what the layers that drew their own menus listen for
        self.assertIn("document.dispatchEvent(new CustomEvent('parseh:gear', { detail: what }))", s)
        self.assertIn("announce('mounted')", s)
        self.assertIn("announce('unmounted')", s)
        # unmount() takes everything away, and a replaced mount says nothing of it
        self.assertIn("unmount: unmount, destroy: unmount", s)
        self.assertIn("if (current === handle) { current = null; announce('unmounted'); }", s)

    def test_the_top_of_the_script_documents_all_of_it(self):
        head = self.raw[:self.raw.index("(function () {")]
        for needle in ("ParsehGear.mount(spec)", "ParsehGear.mounted()", "unmount()", "parseh:gear", "node ", "indent",
                       "disabled?: (above)", "ParsehGear.std.zoom()", "levels ", "stepper ", "buttons "):
            self.assertIn(needle, head, "the header names " + needle)


class TheSheetHasTwoStages(unittest.TestCase):
    """a0.5.4: the phone's sheet opens on an index of the themes and enters one; the toolkit says all of it."""

    def setUp(self):
        self.raw = JS.read_text(encoding="utf-8")
        self.js = code(self.raw)

    def test_the_api_gains_the_stage_and_the_back(self):
        for name in ("stage: function () { return isUp && sheet ? stage : null; }", "back: back"):
            self.assertIn(name, self.js)
        for fn in ("function enter(gid)", "function leaveStage(spend)", "function back()", "function updateIndex()",
                   "function summaryOf(b)", "function rowParts(row)", "function paintHead()", "function paintStage()"):
            self.assertIn(fn, self.js, fn)

    def test_the_summary_rule_is_kind_by_kind(self):
        s = self.js
        rule = s[s.index("function rowParts(row)"):s.index("function asParts(v)")]
        for kind in ("switch", "choice", "slider", "stepper", "levels", "buttons"):
            self.assertIn("case '%s':" % kind, rule, kind)
        for never in ("case 'link'", "case 'action'", "case 'note'", "case 'node'"):
            self.assertNotIn(never, rule, "a " + never[6:-1] + " says nothing in a summary")
        self.assertIn("words(row.short)", rule, "a switch says its short name, where it is on")
        self.assertIn("{ bdi: name }", rule, "a level's name is told apart for a right-to-left reading")
        self.assertIn("el('bdi', null, p.bdi)", self.js)
        # a group's own summary wins, and an empty one is a summary
        self.assertIn("given !== undefined && given !== null", s)

    def test_two_history_entries_and_the_gesture_that_leaves_the_theme_first(self):
        s = self.js
        self.assertIn("function spendEntries(how, keep)", s)
        self.assertIn("history.go(-n)", s, "both entries given back in one go, to be spent in one popstate")
        self.assertIn("if (stage === 'index') pushEntry();", s, "the second entry is pushed by the first theme only")
        self.assertIn("stack.length = at + 1;", s, "a gesture out of a theme forgets the entry it spent")

    def test_the_two_heights_are_remembered_on_the_device(self):
        s = self.js
        self.assertIn("var TALL_KEY = 'parseh_gear_tall';", s)
        self.assertIn("localStorage.setItem(TALL_KEY, '1')", s)
        self.assertIn("localStorage.removeItem(TALL_KEY)", s)
        self.assertIn("function halfH()", s)
        self.assertIn("function tallH()", s)

    def test_a_borrowed_node_follows_the_stage(self):
        self.assertIn("isUp: function () { return isUp && (!sheet || stage === g.id); }", self.js)

    def test_the_pane_that_is_not_on_stage_is_out_of_reach(self):
        self.assertIn("setInert(indexPane, inTheme);", self.js)
        self.assertIn("setInert(themePane, sheet && !inTheme);", self.js)

    def test_the_x_is_last_for_the_keyboard_in_the_sheet(self):
        self.assertIn("if (xEl.parentNode !== panel) panel.appendChild(xEl);", self.js)

    def test_the_standard_interface_group_says_its_pages(self):
        self.assertIn("'Mobile pages' : 'Browser pages'", self.js)

    def test_the_top_of_the_script_documents_the_stages(self):
        head = self.raw[:self.raw.index("(function () {")]
        for needle in ("THE PHONE'S SHEET HAS TWO STAGES", "stage()", "back()", "Group.summary", "`short`", "parseh_gear_tall",
                       "HISTORY:", "bdi"):
            self.assertIn(needle, head, "the header names " + needle)

    def test_no_media_query_asks_whether_motion_is_wanted(self):
        # the slide asks the sheet's own transition, which the stylesheet takes away under reduced motion
        self.assertIn("getComputedStyle(trackEl).transitionDuration", self.js)


class TheSheetOfStyles(unittest.TestCase):

    def setUp(self):
        self.raw = CSS.read_text(encoding="utf-8")
        self.css = re.sub(r"/\*.*?\*/", "", self.raw, flags=re.S)

    def tokens_block(self):
        start = self.css.index(".pg-gear,.pg-panel{")
        return self.css[start:self.css.index("}", start) + 1]

    def test_every_class_it_writes_is_its_own(self):
        preludes = re.findall(r"([^{}]+)\{", self.css)
        classes = set()
        for pre in preludes:
            if pre.strip().startswith("@"):
                continue
            classes.update(re.findall(r"\.([A-Za-z_][\w-]*)", pre))
        self.assertTrue(classes)
        self.assertEqual([], sorted(c for c in classes if not c.startswith("pg-")),
                         "a class the page might already have")

    def test_every_colour_is_in_the_one_block_with_a_fallback_behind_each_token(self):
        block = self.tokens_block()
        rest = self.css.replace(block, "")
        self.assertNotRegex(rest, r"#[0-9a-fA-F]{3,8}\b", "a colour outside the tokens' block")
        self.assertNotRegex(rest, r"\b(?:rgb|hsl)a?\((?!0,0,0,)", "a colour outside the tokens' block")
        for name in ("bg", "ground", "btn", "ink", "dim", "rule", "accent", "accent-fg"):
            m = re.search(r"--pg-%s:([^;]+);" % re.escape(name), block)
            self.assertTrue(m, name)
            self.assertRegex(m.group(1), r"^var\(--[\w-]+,(?:var\(--[\w-]+,)?#[0-9a-f]{3,8}\)+$",
                             "--pg-%s falls back through the studio's token to a plain colour" % name)
        # the toolbox's own tokens and the studio's, both, as lib/explain.js reads them
        for token in ("--card", "--ink", "--dim", "--rule", "--accent", "--accent-fg", "--bg",
                      "--chrome-panel", "--chrome-fg", "--chrome-mut", "--chrome-line", "--chrome-bg"):
            self.assertIn("var(%s," % token, block, token)
        # and no page's token is used bare anywhere
        self.assertNotRegex(rest, r"var\(--(?:card|bg|ink|dim|faint|rule|accent|accent-fg|hl|danger|chrome-[a-z]+)\s*\)")

    def test_no_viewport_unit_anywhere(self):
        self.assertNotRegex(self.css, r"[0-9.]\s*(?:vw|vh|vmin|vmax|dvh|dvw|svh|svw|lvh|lvw)\b")
        self.assertIn("--pg-vh", self.css, "the sheet's height is made of the one number the script sets")

    def test_the_sheet_is_half_the_window_with_a_floor(self):
        self.assertRegex(self.css, r"height:max\(240px,calc\(var\(--pg-vh,8px\) \* 55\)\)")
        self.assertIn("env(safe-area-inset-bottom)", self.css)

    def test_a_fingers_target_and_a_phones_word(self):
        self.assertGreaterEqual(self.css.count("min-height:48px"), 8)
        self.assertGreaterEqual(self.css.count("height:48px"), 6)
        self.assertIn("@media (max-width:599px){.pg-gear-word{display:none}}", self.css)
        self.assertIn("html[data-mode=mobile] .pg-gear-word", self.css)
        self.assertIn("@media (pointer:coarse)", self.css)

    def test_reduced_motion_and_the_keyboards_place_and_print(self):
        self.assertIn("@media (prefers-reduced-motion:reduce)", self.css)
        self.assertIn(":focus-visible", self.css)
        self.assertIn("@media print", self.css)

    def test_the_chrome_does_not_turn_round_in_a_right_to_left_page(self):
        self.assertIn("direction:ltr", self.css)

    def test_the_two_stages_and_the_two_heights(self):
        for rule in (".pg-irow{", "min-height:var(--pg-row,56px)", ".pg-pane-index",
                     ".pg-sheet.pg-in-theme .pg-stages{transform:translateX(-50%)}",
                     ".pg-panel.pg-sheet.pg-tall{height:calc(var(--pg-vh,8px) * 100 - 48px)}",
                     "visibility:hidden;transition:visibility 0s linear .16s", ".pg-panel .pg-isum"):
            self.assertIn(rule.replace(".pg-irow{", ".pg-panel .pg-irow{"), self.css, rule)
        # the switch's own track keeps its name: the stages' container is another class
        self.assertIn(".pg-stages", self.css)
        self.assertIn("white-space:nowrap;overflow:hidden;text-overflow:ellipsis", self.css, "a summary is one line, cut")

    def test_a_hidden_row_stays_hidden_whatever_display_it_was_given(self):
        self.assertIn(".pg-panel [hidden]{display:none!important}", self.css)

    def test_the_sentence_and_the_edges_are_drawn_to_be_read(self):
        # the sentence is --dim a fifth of the way toward the ink where a browser can mix; the studio's sepia
        # --chrome-mut is 4.4:1 on its own paper, which is a hair under a small line's 4.5
        self.assertIn("@supports (color:color-mix(in srgb,red,blue))", self.css)
        self.assertIn("--pg-sub:color-mix(in srgb,var(--pg-dim) 78%,var(--pg-ink))", self.css)
        self.assertIn("--pg-edge:color-mix(in srgb,var(--pg-dim) 82%,var(--pg-bg))", self.css)


if __name__ == "__main__":
    unittest.main()
