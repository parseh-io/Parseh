#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""THE VIDEO PLAYER'S GEAR, ⚙ page (a0.5.0), as the files say it.

    python3 -m unittest discover -s tests -p test_gear_player.py

What the gear DOES on the player page -- every row pressed and the page's own
control and key read back, the bar under the video and its slider, the marks
put away on a Persian and an Arabic video, Aa, the phone's sheet and its first
line, the whole screen, the three themes -- is driven in a real Chromium by
tests/gear_player.mjs.  What is checked here is what only the SOURCE can say:

* the page loads the toolkit synchronously, before the script that mounts it,
  and the toolbox serves it and a phone keeps it (a kept video whose ⚙ is in
  no offline list opens away from the computer and does nothing);
* the groups, the rows and the words of the panel are the owner's (plan §6,
  "Video"), in the plan's order -- the sentences are pinned as he reads them;
* the page's own buttons carry the names he chose, and the ones that live only
  in the gear are put away by the stylesheet and still in the page, since the
  gear presses them;
* the adapter builds nothing with innerHTML (a row's words may come from a
  video), reads the page's own settings and moves them by pressing the page's
  own buttons, and Aa is caught in the capture phase before Parseh.typo's own;
* DIACRITICS is ONE rule and display only: the lines are drawn from `asDrawn()`,
  and the copy, the card, the editor and the lookups read the chunk as written;
* the phone's layer builds neither ⋯ nor its group lines nor the switch where
  there is a gear, and the stylesheet's first line is the plan's.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "youtube/lib", "lib", "tests", "."):
    sys.path.insert(0, str(ROOT / p))

HTML = ROOT / "youtube" / "lib" / "player.html"
JS = ROOT / "youtube" / "lib" / "player.js"
CSS = ROOT / "youtube" / "lib" / "style.css"
MOBILE_JS = ROOT / "lib" / "mobileplayer.js"
MOBILE_CSS = ROOT / "lib" / "mobile.css"


def code(src):
    """The script with its comments taken out, so that what a comment says about
    a thing is never taken for the thing."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(^|\s)//[^\n]*", r"\1", src)


def flat(src):
    """The script's strings as they read: \\uXXXX escapes made characters and
    'a' + 'b' made 'ab' -- the plan's sentences are pinned as the owner reads them."""
    src = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), src)
    src = re.sub(r"'\s*\+\s*'", "", src)
    return re.sub(r'"\s*\+\s*"', "", src)


def adapter(js):
    """The gear's section of player.js, from its heading to the handle the other layers read."""
    start = js.index("THE GEAR, ⚙ page (a0.5.0)")
    return js[start:js.index("THE VIDEO, FOR THE LAYERS OUTSIDE THIS SCRIPT", start)]


class LoadedServedAndKeptTests(unittest.TestCase):

    def setUp(self):
        self.html = HTML.read_text(encoding="utf-8")

    def test_the_toolkit_is_loaded_synchronously_before_the_script_that_mounts_it(self):
        tag = '<script src="/lib/pagesettings.js"></script>'
        self.assertIn(tag, self.html, "no async or defer: the layers ask whether there is a gear when they start")
        self.assertLess(self.html.index('<script src="/lib/parseh.js"></script>'), self.html.index(tag))
        self.assertLess(self.html.index(tag), self.html.index("/lib/player.js"))
        # the mark that hides what lives only in the gear is put on before the first paint,
        # and only where the toolkit is there
        self.assertIn("if (window.ParsehGear) document.documentElement.classList.add('pg-player');", self.html)
        self.assertLess(self.html.index(tag), self.html.index("classList.add('pg-player')"))

    def test_every_script_and_sheet_the_page_loads_from_lib_is_served_and_kept(self):
        import offline
        import serve
        for src in re.findall(r'(?:src|href)="(/lib/[^"]+\.(?:js|css))"', self.html):
            if src == "/lib/langs.css":
                continue                # written out of the registry, and served as what it is
            self.assertIn(src, serve.STATIC_FILES, src + " is not served")
            self.assertIn(src, offline.SHARED, src + " is not kept on a phone, so a kept video would open without it")
        # the toolkit's own sheet is linked by the script, from beside itself: served and kept too
        for f in ("/lib/pagesettings.js", "/lib/pagesettings.css"):
            self.assertIn(f, serve.STATIC_FILES)
            self.assertIn(f, offline.SHARED)

    def test_the_adapter_is_in_the_script_the_page_already_keeps(self):
        import offline
        self.assertIn("/lib/player.js", offline.PLAYER_FILES, "the adapter is part of player.js, which a kept video carries")


class ThePageItselfTests(unittest.TestCase):

    def setUp(self):
        self.html = HTML.read_text(encoding="utf-8")
        self.css = CSS.read_text(encoding="utf-8")

    def test_the_buttons_that_stay_have_the_names_the_owner_chose(self):
        names = {"follow": "keep in view", "pin": "keep video", "sbs": "beside the text", "aloud": "reading only"}
        for ident, name in names.items():
            m = re.search(r'<button id="%s"[^>]*>([^<]*)</button>' % ident, self.html)
            self.assertIsNotNone(m, ident)
            self.assertEqual(m.group(1), name, ident)
        # the dictionary, the theme and Aa stay as they were
        for ident, name in (("dictmode", "dictionary"), ("theme", "◐"), ("typo", "Aa")):
            self.assertRegex(self.html, r'<button id="%s"[^>]*>%s</button>' % (ident, name))

    def test_what_lives_only_in_the_gear_is_put_away_and_not_removed(self):
        for ident in ("hoverpause", "defmode", "defmt", "lookupset"):
            self.assertIn('id="%s"' % ident, self.html, "the gear presses it, so it stays in the page")
        self.assertIn("html.pg-player header :is(#hoverpause,#defmode,#defmt,#lookupset){display:none}", self.css)

    def test_the_bar_under_the_video_has_a_handle_and_says_what_it_does(self):
        self.assertIn('id="grip" title="drag to make the video bigger or smaller — double-click for its usual size"', self.html)
        self.assertIn("radial-gradient(circle,var(--dim) 1.6px", self.css, "dots to take hold of, not a bare line")
        # beside the text the same handle stands upright
        beside = self.css[self.css.index("body.sbs #grip::before"):]
        self.assertIn("height:30px", beside[:400])


class TheRowsTests(unittest.TestCase):
    """Every group and row of the panel, in the plan's order, with the owner's words."""

    def setUp(self):
        self.src = flat(adapter(JS.read_text(encoding="utf-8")))
        self.code = code(self.src)

    def in_order(self, *needles):
        at = -1
        for n in needles:
            i = self.src.find(n, at + 1)
            self.assertGreater(i, at, "missing, or out of the plan's order: " + n[:70])
            at = i

    def test_the_groups_come_in_the_plans_order(self):
        self.in_order("id: 'watching', title: 'Watching & reading'", "id: 'looking', title: 'Looking a word up'",
                      "id: 'playback', title: 'Playback'", "id: 'text', title: 'Text'",
                      "Gear.std.zoom()", "Gear.std.colours()", "iface")
        self.assertIn("groups: [watching, looking, playback, text, Gear.std.zoom(), Gear.std.colours(), iface]", self.src)
        self.assertIn("page: 'video'", self.src)

    def test_watching_and_reading_in_the_plans_order_with_its_sentences(self):
        self.in_order(
            "label: 'Keep the playing caption in view'",
            "Scrolls the transcript so the caption being said stays on screen; it waits a moment after you scroll yourself.",
            "label: 'Pause while a gloss is open'",
            "While a gloss is open the video waits, and goes on a moment after it closes, so you can read at your own pace. With a mouse or a finger.",
            "label: 'Show only the reading'",
            "Draws each phrase as its reading alone (kana, or pinyin) and keeps the text in the hover cloud.",
            "label: 'Diacritics'",
            "Shows the small marks that write the vowels, the doubling and the silent stop (fatha, damma, kasra, tanwin, shadda, sukun) on the transcript.",
            "Off, the text reads as it is ordinarily printed and you can still point at a phrase for its gloss.",
            "label: 'Video beside the text'",
            "Puts the video in a column beside the transcript instead of above it. Only on wide screens (860 px and up); on a phone, turning it sideways does it.",
            "label: 'Keep the video in view'",
            "The video stays at the top while the transcript scrolls under it. Not needed when the video is beside the text.",
            "label: 'Video size'",
            "How big the video is. You can also drag the bar under it; double-click it to reset.",
            "label: 'Show the lines around'",
            "On the whole-screen video, shows the caption before above and the caption after below the one being said.")

    def test_looking_a_word_up_hangs_each_row_from_the_one_above(self):
        self.in_order("label: 'Look words up in a dictionary'",
                      "Where a phrase has not been glossed, its cloud looks its words up in the dictionary installed for this language.",
                      "indent: 1, label: 'Show the dictionary’s definitions'", "Under each word it finds, the dictionary’s own definition in ",
                      "indent: 2,", "'Translate the definitions into ' + G.name",
                      "a machine’s reading, not a gloss.", "href: '/settings/reading-help/'",
                      "label: 'Get a dictionary for this language →'")
        # the switches are drawn only where the page's own dictionary button is there; the link always is
        self.assertIn("when: function () { return !$('#dictmode').hidden; }", self.src)
        link = self.src[self.src.index("{id: 'help', kind: 'link'"):]
        self.assertNotIn("when:", link[:link.index("}")], "drawn even where nothing is installed: it is how one gets installed")

    def test_playback_has_the_skip_for_both_layouts_and_the_speed_where_the_page_has_a_control(self):
        self.in_order("id: 'skip', kind: 'choice', kept: 'you', label: 'Skip distance'", "id: 'speed', kind: 'stepper', layouts: 'mobile'",
                      "label: 'Playback speed'")
        self.assertIn("watch: watchKeys(['bk_skip'])", self.src, "the skip is the person's: it follows the others who set it")
        self.assertIn("Shift+← and Shift+→", self.src, "the keys use it")
        self.assertIn("narr().setSecs(v)", self.src, "set through the dock's own, so its labels follow")
        self.assertNotIn("layouts: 'mobile'", self.src[self.src.index("id: 'skip'"):self.src.index("id: 'speed'")],
                         "the skip is in both layouts")

    def test_text_is_the_aa_panels_own_fields_with_the_owners_words(self):
        self.in_order("' text size'", "How big the transcript’s own words are, the ones you are learning.",
                      "label: 'Subtitle size', layouts: 'mobile'",
                      "How big the subtitles are over the video when it fills the screen (a phone held sideways).",
                      "label: 'Gloss size'", "How big the meanings and notes in the hover cloud are.",
                      "label: 'Text width'", "How wide the column of transcript may grow on a wide screen; on a narrow screen it always fits.",
                      "label: 'Line spacing'", "The space between lines: 1 is the usual, more is airier.",
                      "label: 'Space between characters'", "Extra room between characters; 0 is the normal spacing.",
                      "label: 'Furigana contrast'", "label: 'Furigana size'",
                      "label: 'Put the text back to normal'")
        # built from the very fields Parseh.typo is given, so the ranges and the defaults cannot drift apart
        self.assertIn("typoFields.forEach(function (f) {", self.src)
        self.assertIn("fields: typoFields", JS.read_text(encoding="utf-8"))
        self.assertIn("typoApi.set(f.name, v)", self.src)
        self.assertIn("typoApi.reset()", self.src)
        # the same key, as ever
        self.assertIn("Parseh.typo({key: 'yt_typo'", JS.read_text(encoding="utf-8"))

    def test_the_keep_buttons_are_brought_into_the_last_group_of_the_phones_sheet(self):
        self.assertIn("iface.rows.push({id: 'keep', kind: 'node', layouts: 'mobile'", self.src)
        self.assertIn("document.querySelector('.kp-btn')", self.src)

    def test_a_row_is_pressed_through_the_pages_own_button(self):
        for button in ("#follow", "#hoverpause", "#aloud", "#sbs", "#pin", "#dictmode", "#defmode", "#defmt"):
            self.assertIn("press('%s'," % button, self.src)
        press = self.src[self.src.index("function press(sel, want, now) {"):]
        press = press[:press.index("\n    }")]
        self.assertIn("b.onclick.call(b)", press, "the button's own handler runs: a click outside the panel would shut a popover")
        self.assertIn("else b.click();", press, "and where the handler is not a property, the click is all there is")

    def test_the_adapter_builds_no_html(self):
        self.assertNotIn("innerHTML", self.code)
        self.assertNotIn("insertAdjacentHTML", self.code)


class AaTests(unittest.TestCase):

    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")
        self.src = adapter(self.js)

    def test_aa_is_caught_at_the_window_in_the_capture_phase(self):
        self.assertIn("window.addEventListener('click', function (e) {", self.src)
        self.assertIn("e.target.closest('#typo')", self.src)
        self.assertIn("e.preventDefault(); e.stopImmediatePropagation();", self.src)
        self.assertIn("}, true);", self.src)
        self.assertIn("gear.open('text')", self.src)
        # where there is no gear, Aa is the panel it was: the capture handler asks first
        self.assertIn("Gear.mounted() !== gear", self.src)

    def test_the_whole_screens_aa_keeps_its_panel(self):
        self.assertIn("    typo: typoApi,", self.js, "lib/mobileplayer.js opens the same panel from the whole screen's own button")
        mp = MOBILE_JS.read_text(encoding="utf-8")
        self.assertIn("api.toggle(size)", mp)


class DiacriticsTests(unittest.TestCase):

    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")

    def test_one_switch_one_key_default_shown(self):
        self.assertIn("marks: store('yt_marks', true)", self.js)
        self.assertIn("localStorage.setItem('yt_marks', on ? '1' : '0');", self.js)

    def test_the_lines_are_drawn_from_asdrawn_and_nothing_else_reads_it(self):
        self.assertIn("function marksOff() { return !!marksRe && !opts.marks; }", self.js)
        self.assertIn("marksRe = L.strip ? new RegExp('[' + L.strip + ']', 'g') : null;", self.js,
                      "the very marks the record's strip names, the lookups' own class")
        users = [m.start() for m in re.finditer(r"\basDrawn\(", code(self.js))]
        # the definition, paintWords' two draws, the bare run, the cloud's head text, and the in-place redraw
        self.assertEqual(len(users), 6, "the one function the lines are drawn through, and the five places that draw")
        self.assertIn("said.textContent = ParsehWordline.aloud((L.reading ? ch.kana : ch.tr) || '', asDrawn(ch.fa));", self.js)
        self.assertIn("wordsOf(asDrawn(ch.fa)).forEach(function (wordTxt, k) {", self.js)
        self.assertIn("bare.textContent = asDrawn(ch.fa);", self.js)
        self.assertIn("esc(asDrawn(ch.fa))", self.js)
        self.assertIn("if (e.classList.contains('bare')) e.textContent = asDrawn(ch.fa);", self.js)

    def test_the_copy_and_the_card_read_the_chunk_as_it_was_written(self):
        self.assertIn("var text = w ? (marksOff() && own ? own.fa : Parseh.baseText(w))", self.js)
        self.assertIn("wordsOf(ch.fa)[at.k]", self.js)
        self.assertIn("Parseh.copy(cloudCtx.ch.fa)", self.js, "the cloud's copy button always did")

    def test_a_video_with_nothing_to_put_away_has_no_row(self):
        self.assertIn("when: function () { return videoHasMarks(); }", self.js)
        self.assertIn("var hasMarkRe = L.strip ? new RegExp('[' + L.strip + ']') : null;", self.js,
                      "not the global one, whose test() keeps a place")

    def test_the_redraw_keeps_the_elements_and_the_scroll(self):
        body = self.js[self.js.index("function redrawText() {"):self.js.index("// the words of a chunk as spans of their own")]
        self.assertNotIn("segEl(", body, "the lines are written again where they stand, not made again")
        self.assertNotIn("render(", body)
        self.assertIn("window.scrollBy(0, d)", body)
        self.assertIn("refillCloud();", body)


class TheVideoSizeTests(unittest.TestCase):

    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")

    def test_the_handle_and_the_bar_share_one_size(self):
        self.assertIn("    size: videoSize,", self.js)
        self.assertIn("grip.addEventListener('dblclick', videoSize.reset);", self.js)
        self.assertIn("localStorage.setItem(r.side ? 'yt_sidew' : 'yt_vidw'", self.js, "the same two keys the bar kept")
        self.assertIn("watch: function (cb) { return videoSize.onChange(cb); }", self.js)
        # the least a video can be is one number for the bar and for the slider
        self.assertIn("var VID_MIN = 280, COL_MIN = 320;", self.js)
        # and the most it can be stacked is what the stylesheet lets the video be: the bar stores the width the video
        # has, so a slider that offered more would jump back as soon as it was moved
        self.assertIn("parseFloat(getComputedStyle(vid).maxWidth)", self.js)
        self.assertNotIn("Math.max(280,", self.js.replace("Math.max(VID_MIN,", ""))


class TheSheetsIndexTests(unittest.TestCase):
    """a0.5.4: what each theme says it is set to, on the phone's list of themes."""

    def setUp(self):
        self.src = flat(adapter(JS.read_text(encoding="utf-8")))
        self.code = code(self.src)

    def test_every_switch_worth_a_summary_has_a_short_name(self):
        for short in ("short: 'follows'", "short: 'pauses'", "short: 'reading only'", "short: 'beside the text'", "short: 'pinned'",
                      "short: 'lines around'", "short: 'dictionary'", "short: 'definitions'", "short: 'translated'"):
            self.assertIn(short, self.code, short)

    def test_the_themes_say_their_own_summaries(self):
        for needle in ("watching.summary = function", "looking.summary = function", "playback.summary = function", "text.summary = function",
                       "'video ' + Math.round(sizeShare()) + ' %'", "'no dictionary'", "'no diacritics'", "'skip ' + playback.rows[0].get() + ' s'"):
            self.assertIn(needle, self.code, needle)

    def test_aa_is_at_text_when_text_is_the_theme_on_stage(self):
        self.assertIn("function atText()", self.code)
        self.assertIn("return st === 'text';", self.code)


class ThePhoneTests(unittest.TestCase):

    def setUp(self):
        self.mjs = MOBILE_JS.read_text(encoding="utf-8")
        self.css = MOBILE_CSS.read_text(encoding="utf-8")

    def test_the_layer_builds_no_menu_where_there_is_a_gear(self):
        self.assertIn("if (!gearUp()) buildMore(row);", self.mjs)
        self.assertIn("document.addEventListener('parseh:gear', function () {", self.mjs)
        # ⋯, the lines that name its groups and the Browser | Mobile switch are all made by the one function
        more = self.mjs[self.mjs.index("function buildMore(row) {"):self.mjs.index("function unbuildMore() {")]
        for piece in ("'m-rmore'", "'m-rlab'", "'parseh-mode'"):
            self.assertIn(piece, more)
        build = self.mjs[self.mjs.index("function build() {"):self.mjs.index("/* ⋯, the lines that say")]
        for piece in ("'m-rmore'", "'m-rlab'", "'parseh-mode'"):
            self.assertNotIn(piece, build, "build() itself makes none of them")

    def test_the_whole_screen_has_no_gear(self):
        self.assertIn("gearAway();", self.mjs)
        setfull = self.mjs[self.mjs.index("function setFull(want, theirs) {"):]
        self.assertLess(setfull.index("gearAway();"), setfull.index("outButton();"))

    def test_the_whole_screen_waits_for_the_sheets_step_in_the_history(self):
        # the sheet's entry is gone back over before the whole screen pushes its own, or the step would land on the
        # sheet's entry and read as a back gesture out of the video
        self.assertIn("else gearShutThen(function () { setFull(true); });", self.mjs)
        shut = self.mjs[self.mjs.index("function gearShutThen(go) {"):]
        self.assertIn("window.addEventListener('popstate', enter);", shut[:900])
        self.assertIn("t = setTimeout(enter, 400);", shut[:900])

    def test_the_lines_around_has_a_handle_and_its_word(self):
        self.assertIn("window.ParsehMobilePlayer.lines = {", self.mjs)
        self.assertIn("ctx.appendChild(el('span', 'm-vctx-word', 'lines around'));", self.mjs)
        self.assertIn("setCtx(!ctxOn);", self.mjs, "the button over the picture and the gear's row move it one way")

    def test_the_first_line_is_the_plans_and_the_gear_takes_the_menus_place(self):
        bare = re.sub(r"\s+", "", self.css)
        self.assertIn("[data-layout=mobile],[data-parseh-gear]){display:none!important}", bare,
                      "the one thing the whitelist of the first line lets through that is new")
        self.assertIn("html.m-player[data-mode=mobile] header .pg-gear{order:6;margin-inline-start:auto}", self.css)
        # with the gear mounted, everything the menu held is a row of the sheet and not on the bar
        self.assertIn("html.m-player.pg-player[data-mode=mobile] header > :is(#follow,#hoverpause,#aloud,#pin,#dictmode,", self.css)
        # the sheet has the page above it, and the bars that would stand over it step aside
        self.assertIn("html.m-player.pg-sheet[data-mode=mobile] :is(.pf-bar,.kp-bar){display:none}", self.css)

    def test_the_lines_around_button_says_what_it_is_in_words_and_aa_moves_over_for_it(self):
        self.assertIn(".m-vctx-word{", self.css)
        self.assertRegex(self.css, r"\.m-vctx\{[^}]*flex-direction:column")
        ctx = int(re.search(r"\.m-vctx\{[^}]*right:calc\((\d+)px", self.css).group(1))
        width = int(re.search(r"\.m-vctx\{[^}]*\bwidth:(\d+)px", self.css).group(1))
        aa = int(re.search(r"\.m-vtxt\{[^}]*right:calc\((\d+)px", self.css).group(1))
        self.assertGreaterEqual(aa, ctx + width + 4, "Aa stands clear of the wider button")


if __name__ == "__main__":
    unittest.main()
