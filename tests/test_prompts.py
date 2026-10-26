# SPDX-License-Identifier: GPL-3.0-or-later
"""The prompt tests (brief 3.8): every prompt Parseh hands to a chatbot, in every
language of the registry and in one added with lib/newlang.py, as a chatbot
receives it -- built by the lab (lib/promptlab.py), which builds each one the
way its own page does -- and the kit that makes them (lib/promptkit.py).

Three things are held here:

  * THE KIT: the marks of a template ({{?flag}} blocks, {{NAME}} placeholders),
    a template's three parts, what a person's own instructions may and may not
    do, the version line, the cut of a language's conventions;
  * THE PROMPTS: a table of checks (CHECKS) run over every surface x language x
    mode -- no `{{` left, the language named, a size budget, the parts in their
    order, and the drift the owner has met: a book's rules in a video's prompt, a
    correction sent to `note`, a harakat rule in the studio's;
  * THE ASSEMBLERS: every route that hands out a prompt keeps its shape and hands
    out what the kit made.

A CHECK THAT CANNOT PASS YET is a row marked PENDING("D") or PENDING("E"): the
lane that rewrites the words it is about (D: the gloss prompts and the
language files, E: the studio's) makes it true and takes the mark off.  A row
never silently disappears: while it is pending it is a skipped test that names
its lane, says why and says how many prompts still fail it -- and the day it
passes on all of them it fails, until the mark is taken off.
"""
import collections
import contextlib
import importlib.util
import io
import itertools
import json
import math
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
import urllib.parse
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _p in ("markdown/app", "markdown/exlex", "markdown", "youtube/lib", "lib"):
    sys.path.insert(0, os.path.join(ROOT, _p))
import glossregion                                              # noqa: E402
import htmlgen                                                  # noqa: E402
import languages                                                # noqa: E402
import mdparser                                                 # noqa: E402
import newbook                                                  # noqa: E402
import newlang                                                  # noqa: E402
import promptboxes                                              # noqa: E402
import promptkit as K                                           # noqa: E402
import promptlab                                                # noqa: E402
import server as studio_server                                  # noqa: E402
import tidy as tidier                                           # noqa: E402
import version                                                  # noqa: E402
import ytpages                                                  # noqa: E402

# THE a0.4.3 DIALECT'S WORD COLOURED IN PARTS is read by exlex/segcolour.py, which this tree has once the a0.4.3 branch is
# merged into it (DIALECT-A043.md): what needs that parser is checked where the module is importable, and skipped, saying so,
# where it is not
HAVE_A043 = importlib.util.find_spec("segcolour") is not None
WAITS = "waits for the a0.4.3 dialect (markdown/exlex/segcolour.py)"

# THE SIZE BUDGETS, in characters, of every prompt on the lab's fixtures, and
# what was measured beside each: (measured, budget), the budget being the
# measured size with 15 % to spare, rounded up to a hundred.  A region prompt is
# its largest mode.  One table, so that a lane that makes a prompt longer or
# shorter does it on purpose: change the measured number and its budget together
# (test_the_budgets_keep_to_their_rule) and say why in the commit.  What a
# person's own text or a language they added adds is theirs; these are Parseh's.
# The studio's prompt is measured as the page opens on it -- the lesson preset -- and
# the exercise prompt for a page that uses no feature yet, every type ticked
# (`StudioBoxes` measures the other presets against the old prompt).
SIZES = {
    #        studio-doc     studio-exercises  video-new      video-region   book-region    transcript-tidy  book-new
    "fa": ((16413, 18900), (20988, 24200), (27766, 32000), (19276, 22200), (18222, 21000), (2815, 3300), (60478, 69600)),
    "ar": ((17075, 19700), (21649, 24900), (29674, 34200), (20968, 24200), (19641, 22600), (2806, 3300), (62198, 71600)),
    "it": ((16774, 19300), (16541, 19100), (30115, 34700), (20905, 24100), (19894, 22900), (2866, 3300), (61566, 70900)),
    "ja": ((17921, 20700), (17457, 20100), (33735, 38800), (24171, 27800), (23448, 27000), (2755, 3200), (63368, 72900)),
    "fr": ((20683, 23800), (20453, 23600), (36659, 42200), (25311, 29200), (24254, 27900), (2914, 3400), (67933, 78200)),
    "de": ((20230, 23300), (20000, 23000), (38483, 44300), (26776, 30800), (25545, 29400), (2877, 3400), (70003, 80600)),
    "tr": ((18457, 21300), (18224, 21000), (37675, 43400), (27125, 31200), (26173, 30100), (2865, 3300), (69142, 79600)),
    "en": ((22654, 26100), (22421, 25800), (40876, 47100), (29596, 34100), (28478, 32800), (2930, 3400), (71639, 82400)),
    "hi": ((18521, 21300), (18196, 21000), (33252, 38300), (22678, 26100), (21961, 25300), (2811, 3300), (64340, 74000)),
    "es": ((18139, 20900), (17906, 20600), (38592, 44400), (27945, 32200), (27276, 31400), (2783, 3300), (69785, 80300)),
    "zh": ((19334, 22300), (19034, 21900), (41768, 48100), (28888, 33300), (28305, 32600), (2739, 3200), (71772, 82600)),
}
MEASURED = ("studio-doc", "studio-exercises", "video-new", "video-region", "book-region",
            "transcript-tidy", "book-new")
GLOSSED = ("video-new", "video-region", "book-region", "book-new")
REGIONS = ("video-region", "book-region")
STUDIO = ("studio-doc", "studio-exercises")
ROOM = 1.15


def budget_of(measured):
    return int(math.ceil(measured * ROOM / 100.0)) * 100


Ctx = collections.namedtuple("Ctx", "surface code mode L G")
Check = collections.namedtuple("Check", "name why applies pending test")


# --- the checks: each is a function of a prompt, and says what is wrong ---
def _flat(text):
    return " ".join(text.split())


def no_placeholder_left(a, c):
    return ["carries `{{`: %s" % ", ".join(sorted(set(re.findall(r"\{\{\S{0,30}", a.text)))[:4])] \
        if "{{" in a.text else []


# WHERE EACH PROMPT SAYS WHICH LANGUAGE IT IS ABOUT, and which the meanings are written in: a language's
# name is in every prompt by accident (Persian's file speaks of a book glossed in Italian), so the
# check looks at the place the prompt says it on purpose.
def _says(surface, L, G):
    name, code = re.escape(L.name), re.escape(L.code)
    if surface == "studio-doc":
        return [r"this document is about %s:" % name]
    if surface == "studio-exercises":
        return [r"^# %s — the annotation conventions" % name]
    if surface in REGIONS or surface == "video-new":
        return [r"^- language: %s \(`%s`\)" % (name, code),
                r"^- gloss language: \*\*%s\*\* \(`%s`\)" % (re.escape(G.name), re.escape(G.code))]
    if surface == "transcript-tidy":
        return [r"transcript of a video in %s," % name]
    if surface.startswith("asr-"):
        return [r"^Language: %s \(%s\)\." % (name, code)]
    return [r"in %s, glossed in %s" % (name, re.escape(G.name))]


def names_the_language(a, c):
    return ["never says %r" % p for p in _says(c.surface, c.L, c.G)
            if not re.search(p, a.text, re.M)]


def within_its_budget(a, c):
    if c.surface.startswith("asr-"):
        import asrexternal
        return [] if len(a.text.encode("utf-8")) <= asrexternal.MAX_PROMPT else ["external review exceeds its prompt limit"]
    budget = SIZES[c.code][MEASURED.index(c.surface)][1]
    return ["%d characters, budget %d" % (len(a.text), budget)] if len(a.text) > budget else []


def opens_with_its_version_line(a, c):
    line = K.version_line(c.surface, c.L, c.G if c.surface in GLOSSED else None, c.mode)
    first = a.text.split("\n", 2)
    out = [] if first[0] == line else ["opens with %r, not %r" % (first[0][:70], line)]
    if version.VERSION not in first[0]:
        out.append("the version line does not carry %s" % version.VERSION)
    if len(first) < 2 or first[1] != "":
        out.append("no blank line after the version line")
    return out


def has_its_three_parts_in_order(a, c):
    out = []
    at = [a.text.find(x) if x else -2 for x in (a.instructions, a.contract, a.data)]
    if c.surface in K.READS_BACK and not a.contract.strip():
        out.append("no answer contract")
    if not a.instructions.strip():
        out.append("no instructions")
    seen = [i for i in at if i >= 0]
    if seen != sorted(seen) or -1 in at:
        out.append("the parts are not in the order instructions, contract, data: %s" % at)
    if a.data and not a.text.rstrip("\n").endswith(a.data.rstrip("\n")[-40:]):
        out.append("the data is not last")
    # the contract comes after EVERYTHING that is instruction, the language's conventions included
    if c.surface in K.KIND and a.contract:
        conventions = K.language_text(c.surface, c.L)
        if conventions and conventions[-60:] in a.text \
                and a.text.index(a.contract[:60]) < a.text.index(conventions[-60:]):
            out.append("the answer contract comes before the language's conventions end")
    return out


def has_no_tex_specials_rule(a, c):
    return ["says %r" % p for p in (r"None of `\$ % & # _ \^ ~` may appear", r"`voc` is \*\*LaTeX\*\*")
            if re.search(p, a.text)]


def has_no_harakat_rule_of_a_reading_edition(a, c):
    return ["says %r" % p for p in (r"harakat", r"tashkil", r"reading edition `fa` carries")
            if re.search(p, a.text)]


# the template's own words about the `note` it never reads from an answer
_OWN_NOTE = ("this answer writes no", "is thrown away", "do not apply here")


def sends_no_correction_to_note(a, c):
    out = []
    for s in re.split(r"(?<=[.!?])\s+", _flat(a.text)):
        if "`note`" in s and "correction" in s and not any(w in s for w in _OWN_NOTE):
            out.append("sends a correction to `note`: %s" % s[:100])
    return out


def has_no_harakat_rule(a, c):
    return ["has a rule about %r" % p for p in ("harakat", "tashkil", "short vowel")
            if re.search(p, a.text, re.I)]


def says_a_videos_line_is_plain_text(a, c):
    """A video's `voc` is written with the books' macros (brief 6.5), and a line with none is
    only ALSO ACCEPTED: the sentence that says so is the one place "plain text" may stand
    beside the vocabulary (a caption's own text is plain text too, and is not this)."""
    return ["says a video's `voc` is plain text: %s" % s[:100]
            for s in re.split(r"(?<=[.!?])\s+", _flat(a.text))
            if "plain text" in s and re.search(r"\bvoc\b|vocabulary|\bline\b|\bentry\b", s)
            and not re.search(r"no macro|also accepted", s)]


def says_a_plain_line_is_accepted_once(a, c):
    """A line with no macro is also accepted in a video (brief 6.5): the templates say it once, and a
    language's file need not say it again."""
    n = len(re.findall(r"line with no macro[^.]*?also accepted", _flat(a.text)))
    return [] if n == 1 else ["says a plain line is also accepted %d times, not once" % n]


def has_no_continuous_prose(a, c):
    return ["says \"continuous prose\""] if "continuous prose" in a.text else []


# THE MEANING RULE is Lane D's words (docs/meaning-rule.md, brief 6.1): its heading is
# what a prompt that asks for `en` carries exactly once.  D changes this line if the
# owner's final words change the heading.
MEANING_RULE = "is a gloss, not a translation"


def has_the_meaning_rule_once(a, c):
    n = a.text.count(MEANING_RULE)
    return [] if n == 1 else ["the meaning rule (%r) stands %d times" % (MEANING_RULE, n)]


# THE RULE'S EXAMPLE is the owner's aligned gloss and a counter-example that says it is constructed:
# the label goes wherever the example does, or a model copies the wrong line
EXAMPLE_ALIGNED = "aligned: certainly, | anything else | you do not want"
EXAMPLE_COUNTER = "certainly, | would you like | anything else?"
COUNTER_LABEL = "a constructed counter-example, not to be copied"


def has_the_meaning_rules_example(a, c):
    flat = _flat(a.text)
    return ["the meaning rule lacks %r" % what
            for what in (EXAMPLE_ALIGNED, EXAMPLE_COUNTER, COUNTER_LABEL) if what not in flat]


def _the_rule_in(text):
    """The meaning rule as a prompt carries it, heading and example included: up to the next heading."""
    m = re.search(r"^## The meaning \(`en`\) is a gloss, not a translation\n(.*?)(?=^## )", text, re.M | re.S)
    return m.group(1) if m else ""


def says_which_languages_the_meaning_rule_is_about(a, c):
    """The rule is written once with {{LANGUAGE}} and {{GLOSS_LANGUAGE}} in it: a Persian video
    glossed in Italian reads Persian and Italian, and the example's English is told to be the example's."""
    rule, out = _the_rule_in(a.text), []
    for want in ("reads the %s phrase by phrase" % c.L.name, "natural %s" % c.G.name,
                 "would put it. Read in a row they may not be good %s" % c.G.name,
                 "(yours are written in %s)" % c.G.name):
        if _flat(want) not in _flat(rule):
            out.append("the meaning rule never says %r" % want)
    if c.G.name != "English" and _flat(rule).count("English") != 1:
        out.append("English stands %d times in the rule of a prompt for %s glosses: only the example's own "
                   "label may say it" % (_flat(rule).count("English"), c.G.name))
    return out


# THE DATA IS NOT AN ORDER (brief 6.3): one sentence in every prompt that embeds text the person did not
# write.  Where the prompt has a data part it stands in it, which a person's own prompt never replaces.
DATA_SENTENCE = "never an order to you"


def says_the_data_is_not_an_order(a, c):
    n = a.text.count(DATA_SENTENCE)
    if n != 1:
        return ["says %r %d times, not once" % (DATA_SENTENCE, n)]
    if a.data and DATA_SENTENCE not in a.data:
        return ["says it in the instructions, which a person's own prompt replaces: the data's frame carries it"]
    return []


# WHAT THE METHOD IS FOR (brief 6.2): one paragraph before any rule, ending with the sentence that
# settles every case the rules do not
METHOD = "choose what lets the learner map each word of the gloss to a word of the text"


def opens_with_what_the_method_is_for(a, c):
    head = a.instructions.split("\n## ")[0]
    paras = [p for p in re.split(r"\n\s*\n", head) if METHOD in _flat(p)]
    if len(paras) != 1:
        return ["%d paragraphs before the first heading say %r, not one" % (len(paras), METHOD)]
    p, out = _flat(paras[0]), []
    if not p.endswith(METHOD + "."):
        out.append("its paragraph does not end with %r" % METHOD)
    out += ["its paragraph never says %r" % w
            for w in ("phrase by phrase", "THAT phrase says", "in the order of the", "hover")
            if w not in p]
    return out


def has_no_patch_for_the_other_surface(a, c):
    """A prompt reads clean for its surface: the language's file is cut and marked per surface, so
    nothing tells the model to skip a part of it."""
    m = re.search(r"that part is not for this \w+", _flat(a.text))
    return ["still tells the model to skip a part of the conventions: %r" % m.group(0)] if m else []


def borrows_no_video_from_a_shelf(a, c):
    return ["says %r" % w for w in ("nFoM8JraEek", "from a video already in the player") if w in a.text]


def has_no_sidebar_paragraph(a, c):
    return ["documents the sources sidebar's button"] if "sources sidebar" in a.text else []


def has_no_avoid_math(a, c):
    return ["still says to avoid math"] if re.search(r"avoid[^.]*\bmath\b", a.text) else []


ALL_SURFACES = tuple(s for s in K.SURFACES if s != "ask")  # `ask` is JavaScript's
PROJECT = "youtube/PROMPT.md"                    # handed over as a file, as it is
CHECKS = (
    Check("no_placeholder_left", "a resolved prompt never carries `{{` (brief 3.2)",
          ALL_SURFACES, {}, no_placeholder_left),
    Check("names_the_language_and_the_gloss_language",
          "the language and the gloss language are named (brief 3.8)",
          ALL_SURFACES, {}, names_the_language),
    Check("stays_within_its_size_budget", "each prompt is under its budget (brief 3.8)",
          ALL_SURFACES, {}, within_its_budget),
    Check("opens_with_its_version_line", "every copied prompt opens with the version line (brief 3.4)",
          ALL_SURFACES, {}, opens_with_its_version_line),
    Check("has_its_three_parts_in_order",
          "instructions, then the answer contract, then the data (brief 3.1)",
          ALL_SURFACES, {}, has_its_three_parts_in_order),
    Check("has_no_harakat_rule_in_a_studio_prompt",
          "a document carries no marks a reading edition writes (brief 3.8)",
          STUDIO, {}, has_no_harakat_rule),
    Check("has_no_continuous_prose",
          "the meaning lines are a gloss, not \"continuous prose\" (brief 3.8, 6.1)",
          ALL_SURFACES + (PROJECT,), {}, has_no_continuous_prose),
    Check("has_no_tex_specials_rule_in_a_video",
          "the TeX specials are a book's: a video never reaches LaTeX (brief 3.8, 4.3)",
          ("video-region", "video-new"), {}, has_no_tex_specials_rule),
    Check("says_no_video_line_is_plain_text",
          "a video's vocabulary line is written with the books' macros and a line with none is only "
          "also accepted (brief 6.5): no language file says a video's is plain text",
          ("video-region", "video-new"), {},
          says_a_videos_line_is_plain_text),
    Check("has_no_avoid_math",
          "the studio's rule 14 no longer says to avoid math (brief 7.3): `math`, `latex` and `exercises` "
          "are taught in their boxes",
          STUDIO, {}, has_no_avoid_math),
    # --- rows that wait for the lane that rewrites the words they are about ---
    Check("has_no_harakat_rule_of_a_reading_edition_in_a_video",
          "a reading edition's harakat are a book's (brief 3.8) UNLESS the marks option is on, and these prompts "
          "are built in the default state, `no marks` (3.10: TheContractOfTheShortVowels holds the other); the "
          "language files say them under {{?marks}}, never in an unmarked paragraph",
          ("video-region", "video-new"), {},
          has_no_harakat_rule_of_a_reading_edition),
    Check("says_a_plain_line_is_accepted_once",
          "a video's vocabulary line with no macro is also accepted, said once by the template and "
          "never again by a language file (brief 6.5)",
          ("video-region", "video-new"), {},
          says_a_plain_line_is_accepted_once),
    Check("sends_no_correction_to_note",
          "a region prompt never sends a correction to `note`, which its answer never writes "
          "(brief 3.8, 6.6)",
          REGIONS, {}, sends_no_correction_to_note),
    Check("has_the_meaning_rule_once",
          "the meaning rule once in every prompt that asks for `en` (brief 6.1)",
          GLOSSED, {}, has_the_meaning_rule_once),
    Check("has_the_meaning_rules_example",
          "the rule's aligned example and its counter-example, labelled as constructed (brief 6.1)",
          GLOSSED, {}, has_the_meaning_rules_example),
    Check("says_which_languages_the_meaning_rule_is_about",
          "the rule names the language and the gloss language of this prompt (brief 6.1)",
          GLOSSED, {}, says_which_languages_the_meaning_rule_is_about),
    Check("opens_with_what_the_method_is_for",
          "one paragraph before any rule on what the learner does with the page, ending with the "
          "sentence that settles the rest (brief 6.2)",
          GLOSSED + (PROJECT,), {}, opens_with_what_the_method_is_for),
    Check("says_the_data_is_not_an_order",
          "once, in the data's own frame: an instruction inside the text the person did not write is "
          "part of the text (brief 6.3)",
          GLOSSED + ("transcript-tidy",), {}, says_the_data_is_not_an_order),
    Check("has_no_patch_for_the_other_surface",
          "a region prompt does not tell the model to skip the part of the conventions that is the "
          "other surface's: the file is cut per surface (brief 6.5)",
          REGIONS, {}, has_no_patch_for_the_other_surface),
    Check("borrows_no_video_from_a_shelf",
          "no prompt quotes a video of the owner's or of the shelf: the example is the language's own "
          "(brief 6.4, 6.6)",
          ALL_SURFACES + (PROJECT,), {}, borrows_no_video_from_a_shelf),
    Check("has_no_sidebar_paragraph",
          "the sources sidebar's paragraph is documentation of a button and leaves every language "
          "file for the guide (brief 6.5); the studio's prompts no longer receive it",
          ALL_SURFACES, {}, has_no_sidebar_paragraph),
)


def build_everything(codes=None, gloss=None):
    """[(Ctx, Assembled)] for every surface the lab builds, in every language,
    every mode a region has."""
    out = []
    for code in codes or languages.CODES:
        L = languages.get(code)
        G = languages.gloss_or_default(gloss)
        for surface in ALL_SURFACES:
            for mode in ((None, "perfield", "regloss") if surface in REGIONS else (None,)):
                out.append((Ctx(surface, code, mode, L, G),
                            promptlab.build(surface, code, mode, gloss)))
    return out


def machine_patches():
    """What a prompt depends on that is this machine's and not Parseh's: the
    studio's prompt may be one the person wrote (library/_prompt.md).  Not
    that one, so that the prompts are the same on every machine.  (A video on
    the shelf is not among these: the add page's example is the language's
    own, and a test below holds that.)"""
    return [mock.patch.object(studio_server.store, "get_prompt",
                              lambda: {"text": studio_server.store.default_prompt(), "custom": False})]


class ControlledMachine(unittest.TestCase):
    def setUp(self):
        for p in machine_patches():
            p.start()
            self.addCleanup(p.stop)


# --- the prompts, everywhere ---------------------------------------------
class EveryPrompt(ControlledMachine):
    built = None

    @classmethod
    def setUpClass(cls):
        patches = machine_patches()
        for p in patches:
            p.start()
        try:
            cls.built = build_everything()
        finally:
            for p in patches:
                p.stop()
        # the prompt Parseh hands over as a file, as it is: one more thing to check
        with open(os.path.join(ROOT, "youtube", "PROMPT.md"), encoding="utf-8") as f:
            text = f.read()
        cls.built.append((Ctx(PROJECT, "-", None, None, None), K.Assembled(PROJECT, "", text, "", "")))

    def run_check(self, check):
        seen = 0
        for ctx, a in self.built:
            if ctx.surface not in check.applies or ctx.surface in check.pending:
                continue
            seen += 1
            with self.subTest(surface=ctx.surface, language=ctx.code, mode=ctx.mode):
                self.assertEqual(check.test(a, ctx), [], "%s [%s]" % (check.why, a.header))
        self.assertTrue(seen, "%s ran on nothing" % check.name)

    def wait_for(self, check):
        """A row that waits for a lane: it is run all the same, and skipped with
        its reason while it still fails.  When it passes everywhere the lane has
        done its work and forgot the mark: that is a failure, so the row is
        flipped on and can never fail silently afterwards."""
        lane = "/".join(sorted(set(check.pending.values())))
        waited = [(c, a) for c, a in self.built if c.surface in check.pending]
        failing = sum(1 for c, a in waited if check.test(a, c))
        if not failing:
            self.fail("PENDING(%s) %s passes on all %d prompts it waited for: take the mark "
                      "off its row in CHECKS, so that it is checked from now on" % (lane, check.name, len(waited)))
        self.skipTest("PENDING(%s): %s -- still fails on %d of %d prompts (%s)" % (
            lane, check.why, failing, len(waited), ", ".join(sorted(check.pending))))


def _make_tests():
    for check in CHECKS:
        if [s for s in check.applies if s not in check.pending]:
            setattr(EveryPrompt, "test_" + check.name, lambda self, check=check: self.run_check(check))
        if check.pending:
            lane = "_".join(sorted(set(check.pending.values())))
            setattr(EveryPrompt, "test_%s__PENDING_%s" % (check.name, lane),
                    lambda self, check=check: self.wait_for(check))


_make_tests()


class Budgets(ControlledMachine):
    def test_the_budgets_keep_to_their_rule(self):
        # measured beside budget, so that a lane changing a size does it on purpose
        for code, row in SIZES.items():
            self.assertEqual(len(row), len(MEASURED), code)
            for surface, (measured, budget) in zip(MEASURED, row):
                self.assertEqual(budget, budget_of(measured), (code, surface))

    def test_every_language_of_the_registry_has_its_row(self):
        self.assertEqual(sorted(SIZES), sorted(languages.CODES))

    def test_the_measured_numbers_are_the_sizes_of_today_within_five_percent(self):
        # else a prompt that shrank or grew on purpose leaves a budget that says nothing (or forbids
        # what was meant): 5 % is what a machine without a word segmenter changes a Japanese or
        # Chinese prompt by, and less than any change a lane makes on purpose
        largest = {}
        for ctx, a in build_everything():
            key = (ctx.code, ctx.surface)
            largest[key] = max(largest.get(key, 0), len(a.text))
        for code, row in SIZES.items():
            for surface, (measured, _budget) in zip(MEASURED, row):
                today = largest[(code, surface)]
                self.assertLessEqual(abs(today - measured), 0.05 * measured,
                                     "%s %s is %d characters today, the table says %d: "
                                     "change the measured number and its budget together" % (code, surface, today, measured))


# --- a language added with newlang.py, in a temporary store ---------------
class AddedLanguage(ControlledMachine):
    """Esperanto, added the way a person adds one: its row in the store, its
    conventions written from docs/lang/_template.md.  Every prompt has to be
    made for it as for the languages that ship."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="promptkit-eo-")
        cls.addClassCleanup(shutil.rmtree, cls.tmp, ignore_errors=True)
        shipped = os.path.join(cls.tmp, "lib", "languages.json")
        personal = os.path.join(cls.tmp, "config", "languages.json")
        lang_tex = os.path.join(cls.tmp, "lib", "lang")
        lang_docs = os.path.join(cls.tmp, "docs", "lang")
        os.makedirs(os.path.dirname(shipped))
        shutil.copy(os.path.join(ROOT, "lib", "languages.json"), shipped)
        shutil.copytree(os.path.join(ROOT, "lib", "lang"), lang_tex)
        shutil.copytree(os.path.join(ROOT, "docs", "lang"), lang_docs)
        patches = [mock.patch.object(newlang, n, v) for n, v in (
            ("REGISTRY", shipped), ("PERSONAL", personal), ("LANG_TEX", lang_tex),
            ("LANG_DOCS", lang_docs), ("ROOT", cls.tmp),
            ("STUDIO", os.path.join(cls.tmp, "markdown")))]
        for p in patches:
            p.start()
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = newlang.main(["eo", "--name", "Esperanto", "--native", "Esperanto"])
        finally:
            for p in patches:
                p.stop()
        assert rc == 0, "newlang could not add the language: %s" % out.getvalue()[-400:]
        langs, problems = languages._load(shipped, personal)
        assert "eo" in langs and not problems, problems
        for p in [mock.patch.dict(languages.LANGS, {"eo": langs["eo"]}),
                  mock.patch.dict(languages.FOLDERS, {langs["eo"].folder: "eo"}),
                  mock.patch.object(K, "LANG_DOCS", lang_docs)] + machine_patches():
            p.start()
            cls.addClassCleanup(p.stop)
        cls.built = [(Ctx(s, "eo", m, languages.get("eo"), languages.gloss_or_default(None)),
                      promptlab.build(s, "eo", m))
                     for s in ALL_SURFACES
                     for m in ((None, "perfield", "regloss") if s in REGIONS else (None,))]

    def test_every_prompt_is_made_for_it(self):
        self.assertEqual(len(self.built), len(ALL_SURFACES) + 4)
        for ctx, a in self.built:
            with self.subTest(surface=ctx.surface, mode=ctx.mode):
                for check in CHECKS:
                    # its size is its own (there is no budget for a language nobody ships)
                    if (ctx.surface in check.applies and ctx.surface not in check.pending
                            and check.test is not within_its_budget):
                        self.assertEqual(check.test(a, ctx), [], check.why)

    def test_the_studio_takes_its_note_on_writing_the_script_from_chunking(self):
        # newlang writes the note into Chunking, which the studio does not take:
        # it is found by what it says
        note = "Runs of Esperanto are **marked** in the studio"
        by = {(c.surface, c.mode): a for c, a in self.built}
        self.assertIn(note, by[("studio-doc", None)].text)
        self.assertIn(note, by[("studio-exercises", None)].text)
        self.assertNotIn(note, by[("video-region", None)].text)
        self.assertIn(note, by[("video-new", None)].text)
        self.assertIn("## The text field", K.language_text("studio-doc", "eo"))


# --- the kit's marks -------------------------------------------------------
def _old_blocks(tpl, flags):
    """glossregion._blocks as it was, the oracle for the kit's resolver."""
    pat = re.compile(r"\{\{\?(\w+)\}\}((?:(?!\{\{\?).)*?)\{\{/\1\}\}", re.S)
    while True:
        new = pat.sub(lambda m: m.group(2) if flags.get(m.group(1)) else "", tpl)
        if new == tpl:
            return tpl
        tpl = new


class Marks(unittest.TestCase):
    def test_a_block_is_kept_where_its_flag_is_true_and_gone_where_it_is_not(self):
        t = "a{{?x}}b{{/x}}c"
        self.assertEqual(K.blocks(t, {"x": True}), "abc")
        self.assertEqual(K.blocks(t, {"x": False}), "ac")

    def test_a_note_to_the_maintainer_is_never_sent_to_any_surface(self):
        t = "a{{?note}}no speaker has reviewed this yet{{/note}}b"
        for surface in K.SURFACES:
            self.assertEqual(K.blocks(t, K.surface_flags(surface)), "ab", surface)

    def test_a_block_may_hold_a_block(self):
        t = "1{{?a}}2{{?b}}3{{/b}}4{{/a}}5"
        self.assertEqual(K.blocks(t, {"a": True, "b": True}), "12345")
        self.assertEqual(K.blocks(t, {"a": True, "b": False}), "1245")
        self.assertEqual(K.blocks(t, {"a": False, "b": True}), "15")

    def test_the_kit_resolves_the_region_template_as_glossregion_always_did(self):
        with open(K.TEMPLATES["video-region"], encoding="utf-8") as f:
            tpl = f.read()
        plain = re.sub(r"\{\{[?/](contract|data)\}\}", "", tpl)
        names = sorted(set(re.findall(r"\{\{\?(\w+)\}\}", plain)))
        self.assertIn("keep", names)
        rng = random.Random(4)
        for _ in range(300):
            flags = {n: rng.random() < 0.5 for n in names}
            self.assertEqual(K.blocks(tpl, flags), _old_blocks(plain, flags), flags)

    def test_a_block_whose_flag_nobody_gave_is_refused_not_dropped(self):
        with self.assertRaises(K.PromptError) as e:
            K.blocks("a{{?vidoe}}b{{/vidoe}}", {"video": True})
        self.assertIn("vidoe", str(e.exception))

    def test_a_block_left_open_or_closed_twice_or_crossed_is_refused_in_words(self):
        for text, said in (("{{?a}}x", "never closed"), ("x{{/a}}", "never opened"),
                           ("{{?a}}{{?b}}x{{/a}}{{/b}}", "was due")):
            with self.assertRaises(K.PromptError) as e:
                K.blocks(text, {"a": True, "b": True})
            self.assertIn(said, str(e.exception), text)

    def test_the_marks_of_the_parts_are_not_flags_and_keep_their_words_in_place(self):
        t = "a{{?contract}}B{{/contract}}c{{?data}}D{{/data}}"
        self.assertEqual(K.flat(t), "aBcD")
        self.assertEqual(K.blocks(t, {}), "aBcD")

    def test_the_instructions_of_a_text_leave_the_contract_and_the_data_out(self):
        self.assertEqual(K.instructions_of("a{{?contract}}B{{/contract}}c{{?data}}D{{/data}}"), "ac")
        self.assertEqual(K.instructions_of("no marks {{ at all }}"), "no marks {{ at all }}")

    def test_every_template_taken_apart_and_put_together_has_the_words_it_had(self):
        """Each part resolved on its own, together, has the words the whole
        template has, whichever flags are on: nothing is lost in the split."""
        rng = random.Random(9)
        for surface in ("video-region", "video-new", "studio-doc", "studio-exercises", "book-new"):
            with open(K.TEMPLATES[surface], encoding="utf-8") as f:
                whole = f.read()
            if surface == "studio-doc":
                whole = K._template(surface)
            names = sorted(set(re.findall(r"\{\{\?(\w+)\}\}", whole)) - set(K._MARKS))
            given = K.parts(surface)
            for _ in range(40):
                flags = {n: rng.random() < 0.5 for n in names}
                got = collections.Counter()
                for part in given:
                    got.update(K.blocks(part, flags).split())
                self.assertEqual(got, collections.Counter(K.blocks(whole, flags).split()),
                                 (surface, flags))

    def test_flat_takes_the_marks_out_and_nothing_else(self):
        for surface, flags in (("video-new", {"example": True, "marks": True}), ("studio-exercises", None),
                               ("book-new", {"marks": True, "nomarks": True})):
            with open(K.TEMPLATES[surface], encoding="utf-8") as f:
                text = f.read()
            if flags is None:
                # the exercise template is a block a type: `flat` wants every flag it names, here all on
                names = set(re.findall(r"\{\{\?(\w+)\}\}", text)) - set(K._MARKS)
                flags = {n: True for n in names}
            stripped = re.sub(r"\{\{[?/](%s)\}\}" % "|".join(["contract", "data", "example"] + sorted(flags)), "", text)
            self.assertNotIn("{{?contract}}", stripped)
            self.assertEqual(K.flat(text, flags), stripped, surface)


class Parts(unittest.TestCase):
    T = ("Do it{{?x}} well{{/x}}.\n\n{{?contract}}Answer in a fence.{{/contract}}\n\n"
         "More rules.\n\n{{?contract}}{{?x}}Several messages.{{/x}}{{/contract}}\n\n"
         "{{?data}}The data: {{DATA}}{{/data}}\n")

    def test_a_template_is_split_into_instructions_contract_and_data(self):
        p = K.parts("studio-doc", template=self.T)
        self.assertEqual(p.instructions, "Do it{{?x}} well{{/x}}.\n\nMore rules.")
        self.assertEqual(p.contract, "Answer in a fence.\n\n{{?x}}Several messages.{{/x}}")
        self.assertEqual(p.data, "The data: {{DATA}}")

    def test_a_flag_block_that_holds_the_words_of_two_parts_is_kept_around_each(self):
        t = "{{?x}}I{{?contract}}C{{/contract}}J{{/x}}"
        p = K.parts("studio-doc", template=t)
        self.assertEqual((p.instructions, p.contract), ("{{?x}}IJ{{/x}}", "{{?x}}C{{/x}}"))

    def test_the_parts_do_not_nest(self):
        with self.assertRaises(K.PromptError):
            K.parts("studio-doc", template="{{?contract}}{{?data}}x{{/data}}{{/contract}}")

    def test_every_prompt_parseh_reads_back_has_a_contract_in_its_template(self):
        for surface in K.READS_BACK:
            self.assertTrue(K.contract(surface, template=(
                tidier.PROMPT if surface == "transcript-tidy" else None)).strip(), surface)

    def test_the_contract_and_the_data_of_the_region_template_are_the_end_of_the_prompt(self):
        p = K.parts("video-region")
        self.assertIn("## What you answer", p.contract)
        self.assertIn("You receive **one JSON document**", p.contract)
        self.assertNotIn("## What you answer", p.instructions)
        self.assertTrue(p.data.startswith("{{ABOUT}}") and p.data.endswith("nothing else."))

    def test_the_transcript_tidy_template_is_registered_by_the_module_that_has_it(self):
        self.assertEqual(K.parts("transcript-tidy").data.split("\n")[0], "THE TRANSCRIPT:")

    def test_ask_has_no_template_here(self):
        with self.assertRaises(K.PromptError):
            K.parts("ask")


class Assembling(unittest.TestCase):
    def test_a_persons_instructions_replace_parseh_s_and_the_contract_stays(self):
        a = K.assemble("studio-doc", "it", instructions="My rules for {{LANGUAGE}}.\n{{?studio}}studio only{{/studio}}",
                       custom="mine")
        self.assertEqual(a.instructions, "My rules for Italian.\nstudio only")
        self.assertIn("creating a markdown file", a.contract)
        self.assertEqual(a.text.split("\n")[0], "Parseh prompt · studio-doc · it · %s · custom: mine" % version.VERSION)
        order = [a.text.index(x) for x in ("My rules", "creating a markdown file")]
        self.assertEqual(order, sorted(order))

    def test_instructions_cannot_carry_the_contract_or_the_data(self):
        for mark in ("contract", "data"):
            with self.assertRaises(K.PromptError):
                K.assemble("studio-doc", "fa", instructions="x {{?%s}}y{{/%s}}" % (mark, mark))

    def test_a_placeholder_nothing_fills_is_refused_in_words(self):
        with self.assertRaises(K.PromptError) as e:
            K.assemble("studio-doc", "fa", instructions="Say {{NOTHING_FILLS_THIS}}.")
        self.assertIn("NOTHING_FILLS_THIS", str(e.exception))
        self.assertIn("bug", str(e.exception))

    def test_a_block_left_over_in_the_result_is_refused_too(self):
        with self.assertRaises(K.PromptError):
            K.assemble("studio-doc", "fa", instructions="{{?nope}}x{{/nope}}")

    def test_what_is_data_may_say_double_braces_and_is_never_looked_into(self):
        a = K.assemble("studio-doc", "fa", instructions="rules", data="Explain {{this}} and {{?that}} for me. {{DATA}}",
                       verbatim={"X": "{{LANGUAGE}}"})
        self.assertIn("Explain {{this}} and {{?that}} for me. {{DATA}}", a.data)
        b = K.assemble("studio-doc", "fa", instructions="Title: {{TITLE_HERE}}", verbatim={"TITLE_HERE": "{{a book}} {{LANGUAGE}}"})
        self.assertIn("Title: {{a book}} {{LANGUAGE}}", b.instructions)

    def test_the_kit_fills_what_it_holds_and_what_the_caller_gives(self):
        a = K.assemble("book-region", "it", "fr", template="{{LANGUAGE}}|{{GLOSS_LANGUAGE}}|{{LANGUAGE_CODE}}|{{GLOSS_CODE}}|{{X}}",
                       values={"X": "ok"})
        self.assertEqual(a.instructions, "Italian|French|it|fr|ok")

    def test_an_include_is_filled_like_the_template_and_may_not_hold_itself(self):
        a = K.assemble("studio-doc", "fa", template="a {{INNER}} b", includes={"INNER": "[{{LANGUAGE}}]"})
        self.assertEqual(a.instructions, "a [Persian] b")
        with self.assertRaises(K.PromptError):
            K.assemble("studio-doc", "fa", template="{{LOOP}}", includes={"LOOP": "again {{LOOP}}"})

    def test_lead_and_extras_are_the_callers_own_words_before_and_after_the_instructions(self):
        a = K.assemble("studio-doc", "fa", template="middle {{?contract}}C{{/contract}}", lead="first", extras=["last", "{{kept}}"])
        self.assertEqual(a.instructions, "first\n\nmiddle\n\nlast\n\n{{kept}}")
        self.assertEqual((a.contract, a.data), ("C", ""))

    def test_the_data_frame_of_the_template_comes_before_the_data_given_whole(self):
        a = K.assemble("studio-doc", "fa", template="i{{?data}}frame{{/data}}", data="the data")
        self.assertEqual(a.data, "frame\n\nthe data")
        self.assertEqual(a.text.rstrip().split("\n\n")[-2:], ["frame", "the data"])

    def test_the_text_is_the_header_then_the_parts_and_ends_with_one_newline(self):
        a = K.assemble("studio-doc", "fa", template="i{{?contract}}c{{/contract}}{{?data}}d{{/data}}")
        self.assertEqual(a.text, "%s\n\ni\n\nc\n\nd\n" % a.header)
        self.assertEqual(a.sizes()["total"], len(a.text))
        self.assertEqual(str(a), a.text)

    def test_a_surface_the_kit_does_not_know_is_refused(self):
        with self.assertRaises(K.PromptError):
            K.assemble("the-moon", "fa")
        with self.assertRaises(K.PromptError):
            K.parts("the-moon")


class VersionLine(unittest.TestCase):
    def test_its_shape(self):
        v = version.VERSION
        # a language with short vowels says its setting for them last (brief 3.10): `no marks` is the
        # default of a stretch of a book or a video and of a video from scratch
        self.assertEqual(K.version_line("video-region", "fa", "en"), "Parseh prompt · video-region · fa → en · " + v + " · no marks")
        self.assertEqual(K.version_line("studio-doc", "it"), "Parseh prompt · studio-doc · it · " + v)
        self.assertEqual(K.version_line("book-region", "ja", "it", "regloss"),
                         "Parseh prompt · book-region · ja → it · %s · re-gloss" % v)
        self.assertEqual(K.version_line("book-region", "ja", "it", "perfield"),
                         "Parseh prompt · book-region · ja → it · %s · per field" % v)
        self.assertEqual(K.version_line("video-region", "fa", "en", "fill"),
                         "Parseh prompt · video-region · fa → en · " + v + " · no marks")
        self.assertEqual(K.version_line("video-new", "fa", "en", None, "my rules"),
                         "Parseh prompt · video-new · fa → en · %s · no marks · custom: my rules" % v)
        self.assertEqual(K.version_line("studio-doc", "fa", None, None, True),
                         "Parseh prompt · studio-doc · fa · %s · custom" % v)

    def test_the_version_is_read_when_the_line_is_made_and_no_template_carries_one(self):
        with mock.patch.object(version, "VERSION", "a9.9.9"):
            self.assertTrue(K.version_line("ask", "fa").endswith("a9.9.9"))
        files = list(K.TEMPLATES.values()) + [os.path.join(ROOT, "youtube", "docs", "conventions.md")]
        files += [os.path.join(K.LANG_DOCS, f) for f in os.listdir(K.LANG_DOCS)]
        for path in files:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn(version.VERSION, text, path)
            self.assertIsNone(re.search(r"\ba\d\.\d+\.\d+\b", text), path)
        self.assertIsNone(re.search(r"\ba\d\.\d+\.\d+\b", tidier.PROMPT))


class Placeholders(unittest.TestCase):
    def test_every_placeholder_a_template_names_is_published_for_its_surface(self):
        for surface in K.SURFACES:
            if surface == "ask":
                continue
            given = {n for n, _ in K.placeholders(surface)}
            template = tidier.PROMPT if surface == "transcript-tidy" else K._template(surface)
            names = set(re.findall(r"\{\{([A-Z_0-9]+)\}\}", template))
            self.assertEqual(sorted(names - given), [], surface)

    def test_the_names_the_kit_fills_itself_are_the_ones_it_publishes_and_no_others(self):
        given = ("LANGUAGE", "LANGUAGE_NATIVE", "LANGUAGE_CODE", "TR_LABEL", "LANG_CONVENTIONS",
                 "GLOSS_LANGUAGE", "GLOSS_CODE")
        for surface in ALL_SURFACES:
            published = {n for n, _ in K.placeholders(surface)}
            for name in given:
                tpl = "x {{%s}}" % name
                if name in published:
                    a = K.assemble(surface, "fa", "en" if surface in GLOSSED else None, template=tpl)
                    self.assertNotIn("{{", a.instructions, (surface, name))
                else:
                    with self.assertRaises(K.PromptError, msg=(surface, name)):
                        K.assemble(surface, "fa", "en" if surface in GLOSSED else None, template=tpl)

    def test_each_has_a_one_line_meaning(self):
        for name, meaning in K.placeholders():
            self.assertTrue(meaning and "\n" not in meaning and len(meaning) < 110, name)

    def test_what_is_published_for_one_surface_is_not_for_another(self):
        studio = {n for n, _ in K.placeholders("studio-doc")}
        self.assertIn("LANGUAGE", studio)
        self.assertNotIn("GLOSS_LANGUAGE", studio)
        self.assertNotIn("ADDRESS", studio)
        self.assertIn("ADDRESS", {n for n, _ in K.placeholders("video-region")})
        with self.assertRaises(K.PromptError):
            K.placeholders("the-moon")


# --- the language's conventions, cut per prompt -----------------------------
def _file(code):
    with open(os.path.join(K.LANG_DOCS, code + ".md"), encoding="utf-8") as f:
        return f.read()


def _read_as(code, surface):
    """The file as one surface reads it: its {{?flag}} blocks resolved, and the blank
    lines a block leaves behind collapsed as the cut collapses them.  A shipped
    file marks what belongs to a book or a video only, so what a prompt takes of
    it is compared to this and not to the raw text."""
    return re.sub(r"\n{3,}", "\n\n", K.blocks(_file(code), K.surface_flags(surface, code)))


def _headings(text):
    fenced, out = False, []
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            out.append(line[3:].strip())
    return out


def _names(surface, code):
    return [n for n, _ in K.language_sections(surface, code)]


class LanguageCut(unittest.TestCase):
    CODES = languages.CODES

    def test_every_section_of_every_file_is_in_the_table(self):
        # a section nobody lists goes everywhere: which is right for a language
        # somebody adds, and a surprise for a shipped file -- so list it, on purpose
        for code in self.CODES + ["_template"]:
            for h in _headings(_file(code)):
                self.assertIn(h, K.SECTIONS, "%s: `## %s` is in no row of promptkit.SECTIONS" % (code, h))

    def test_the_prompts_that_take_everything_get_the_file_as_it_is(self):
        for code in self.CODES:
            self.assertEqual(K.language_text("book-new", code), _read_as(code, "book-new").strip(), code)
            self.assertEqual(K.language_text("video-new", code),
                             re.sub(r"^# .*\n+", "", _read_as(code, "video-new"), count=1).strip(), code)

    def test_the_studio_takes_the_transliteration_the_reading_and_the_script_note(self):
        for code in self.CODES:
            for surface in STUDIO:
                names = _names(surface, code)
                self.assertEqual(names[0], "(title)")
                self.assertTrue({"Reading", "Transliteration"} <= set(names), (code, names))
                self.assertFalse({"Vocabulary", "Never gloss", "Chunking", "Words", "Example", "(opening)"} & set(names),
                                 (code, names))
                self.assertLessEqual(set(names) - {"(title)", "Reading", "Transliteration"}, {"The text field"})

    def test_a_region_prompt_takes_all_but_chunking_and_only_the_verbatim_paragraph(self):
        for code in self.CODES:
            secs = dict(K.language_sections("video-region", code))
            self.assertNotIn("Chunking", secs)
            self.assertNotIn("(title)", secs)
            self.assertIn("Vocabulary", secs)
            self.assertEqual(sorted(n for n, _ in K.language_sections("video-region", code)),
                             sorted(n for n, _ in K.language_sections("book-region", code)))
            field = secs["The text field"]
            self.assertEqual(field.count("\n\n"), 1, code)
            self.assertIn("reproduces the source **verbatim**", field, code)
            self.assertEqual(("Words" in secs), languages.get(code).words, code)

    def test_the_note_on_writing_the_script_is_found_where_it_stands(self):
        # THE NOTE IS THE STUDIO'S: a file marks it {{?studio}} (lane D2), and a prompt that glosses never has it
        for code in ("it", "de", "fr", "es", "en"):
            text = K.language_text("studio-doc", code)
            self.assertIn("[…]{tl}", text, code)
            self.assertIn("## The text field", text, code)
            for surface in ("video-region", "book-region", "video-new", "book-new"):
                self.assertNotIn("{tl}", K.language_text(surface, code), (code, surface))
        tr = K.language_text("studio-doc", "tr")
        self.assertIn("Runs of Turkish are **marked** in the studio", tr)
        self.assertTrue(tr.index("## The text field") < tr.index("Runs of Turkish"))
        self.assertNotIn("Chunking", tr)
        for surface in ("video-region", "book-region", "video-new", "book-new"):
            self.assertNotIn("{tl}", K.language_text(surface, "tr"), surface)
        for code in ("fa", "ar", "hi", "ja", "zh"):
            self.assertNotIn("The text field", _names("studio-doc", code), code)

    def test_a_cut_only_deletes_every_paragraph_of_it_is_a_paragraph_of_the_file(self):
        for code in self.CODES:
            for surface in ("studio-doc", "video-region", "book-region"):
                raw = [_flat(p) for p in re.split(r"\n\s*\n", _read_as(code, surface))]
                for name, text in K.language_sections(surface, code):
                    for p in re.split(r"\n\s*\n", text):
                        if _flat(p) not in raw and not re.match(r"^#+ ", p):
                            self.fail("%s %s: a paragraph of %s is not the file's: %s" % (code, surface, name, p[:80]))

    def test_headings_go_down_one_level_in_a_region_prompt_and_not_inside_a_fence(self):
        text = K.language_text("video-region", "fa")
        self.assertIn("\n### The text field\n", "\n" + text)
        self.assertNotIn("\n## ", "\n" + text)
        self.assertNotIn("\n### ", "\n" + K.language_text("studio-doc", "fa"))
        self.assertIn("\n## Transliteration\n", "\n" + K.language_text("studio-doc", "fa"))

    def test_the_cuts_take_out_what_the_brief_expects_of_them(self):
        # the studio prompt loses 8 - 15 K of the language file (9.8 K in Italian, 18 K in Chinese:
        # the files differ, and one that lost the sources sidebar's paragraph is shorter by it: lane D2);
        # a region prompt loses Chunking and most of The text field -- what
        # D's marking of the sources sidebar's paragraph and the opening adds is D's.  `whole`
        # is a book's file, which holds no sentence that only a video's line needs, and a region
        # prompt is measured against the whole of its own surface's file for the same reason.
        for code in self.CODES:
            whole = len(K.language_text("book-new", code))
            self.assertGreater(whole - len(K.language_text("studio-doc", code)), 8000, code)
            self.assertLess(whole - len(K.language_text("studio-doc", code)), 18500, code)
            for who in ("book", "video"):
                own = len(K.language_text(who + "-new", code))
                self.assertGreater(own - len(K.language_text(who + "-region", code)), 500, code)
                self.assertGreater(own - len(K.language_text(who + "-region", code)), 0.04 * own, code)

    def test_the_flags_of_a_language_file_are_resolved_per_surface(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "fa.md"), "w", encoding="utf-8") as f:
                f.write("# Persian\n\nOpen.\n\n## Vocabulary\n\n{{?book}}Book rule.{{/book}}{{?video}}Video rule.{{/video}}\n\n"
                        "## Reading\n\n{{?studio}}Studio only.{{/studio}}{{?new}}From scratch.{{/new}}{{?region}}Region.{{/region}}\n")
            with mock.patch.object(K, "LANG_DOCS", td):
                self.assertIn("Book rule.", K.language_text("book-region", "fa"))
                self.assertNotIn("Video rule.", K.language_text("book-region", "fa"))
                self.assertIn("Video rule.", K.language_text("video-new", "fa"))
                self.assertNotIn("Book rule.", K.language_text("video-new", "fa"))
                self.assertIn("Studio only.", K.language_text("studio-doc", "fa"))
                self.assertNotIn("Vocabulary", K.language_text("studio-doc", "fa"))
                self.assertIn("From scratch.", K.language_text("book-new", "fa"))
                self.assertIn("Region.", K.language_text("video-region", "fa"))
                self.assertNotIn("Studio only.", K.language_text("video-region", "fa"))
            # a flag the kit does not know is refused, in the file it is in
            with open(os.path.join(td, "fa.md"), "w", encoding="utf-8") as f:
                f.write("# P\n\n## Reading\n\n{{?nonsense}}x{{/nonsense}}\n")
            with mock.patch.object(K, "LANG_DOCS", td), self.assertRaises(K.PromptError):
                K.language_text("video-region", "fa")

    def test_a_section_nobody_listed_goes_everywhere_and_an_empty_one_goes_nowhere(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "fa.md"), "w", encoding="utf-8") as f:
                f.write("# Persian\n\n## Numbers\n\nCount.\n\n## Chunking\n\n{{?book}}Only a book.{{/book}}\n")
            with mock.patch.object(K, "LANG_DOCS", td):
                for surface in ("studio-doc", "video-region", "book-new"):
                    self.assertIn("Count.", K.language_text(surface, "fa"), surface)
                self.assertNotIn("Chunking", K.language_text("video-new", "fa"))
                self.assertIn("Only a book.", K.language_text("book-new", "fa"))

    def test_an_oddly_written_file_is_cut_by_the_same_rules(self):
        # no title of its own, a `## ` inside a code fence, one section twice, the studio's note in a
        # section the studio does not take, a text field of one paragraph: none of it breaks the cut
        odd = ("Opening words.\n\n## Reading\n\n```\n## not a heading\n\nnor this\n```\n\nAfter the fence.\n\n"
               "## The text field\n\n`fa` reproduces the source **verbatim**.\n\n## Reading\n\nAgain.\n\n"
               "## Vocabulary\n\nA rule.\n\nRuns are marked as `[x]{tl}` in the studio.\n")
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "fa.md"), "w", encoding="utf-8") as f:
                f.write(odd)
            with mock.patch.object(K, "LANG_DOCS", td):
                studio = K.language_text("studio-doc", "fa")
                self.assertEqual(studio.count("## Reading"), 2)
                self.assertIn("## not a heading\n\nnor this", studio)
                self.assertNotIn("Opening words.", studio)
                self.assertNotIn("A rule.", studio)
                self.assertIn("Runs are marked as `[x]{tl}` in the studio.", studio)
                self.assertTrue(studio.startswith("## Reading"), "no title of its own to keep")
                self.assertLess(studio.index("The text field"), studio.rindex("## Reading"), "the note stands where the file's text field does")
                region = K.language_text("video-region", "fa")
                self.assertIn("Opening words.", region)
                self.assertIn("### The text field\n\n`fa` reproduces the source **verbatim**.", region)
                self.assertIn("A rule.", region)
                self.assertNotIn("{tl}", region)
                self.assertIn("## not a heading", region, "a heading inside a fence is not one, and is not moved down")
                self.assertEqual(K.language_text("book-new", "fa"), odd.strip())

    def test_a_language_with_no_file_says_what_each_prompt_has_always_said(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(K, "LANG_DOCS", td):
            self.assertEqual(K.language_text("studio-doc", "it"), "")
            self.assertEqual(K.language_text("studio-exercises", "it"), "")
            self.assertTrue(K.language_text("video-region", "it").endswith("Use a standard, consistent romanisation.)"))
            self.assertTrue(K.language_text("video-new", "it").endswith("say which in a note.)"))
            self.assertIn("Ask for them before annotating.", K.language_text("book-new", "it"))
            self.assertEqual(K.language_sections("video-region", "it"), None)
            with self.assertRaises(K.PromptError):
                K.language_text("transcript-tidy", "it")


# --- the assemblers and their routes ------------------------------------------
class Handler(object):
    def __init__(self, body=None, query=None):
        self.body, self.query, self.answer = body or {}, query or {}, None

    def _json_body(self):
        return self.body

    def send_json(self, answer, code=200):
        self.answer = answer


class Assemblers(ControlledMachine):
    def test_the_readers_of_a_language_file_all_read_through_the_kit(self):
        for code in languages.CODES:
            L = languages.get(code)
            self.assertEqual(ytpages.lang_conventions(L), K.language_text("video-new", code))
            self.assertEqual(newbook.conventions(L), K.language_text("book-new", code))
            self.assertEqual(studio_server.lang_block(code), K.language_text("studio-doc", code))
        # and none keeps a path of its own to the files it used to read
        for module, name in ((glossregion, "LANG_DOCS"), (ytpages, "LANG_DOCS"), (studio_server, "DOCS_LANG")):
            self.assertFalse(hasattr(module, name), "%s still has its own %s" % (module.__name__, name))

    def test_the_studio_route_keeps_its_shape_and_adds_the_kits(self):
        h = Handler(query={"target": ["it"]})
        studio_server.api_prompt_get(h)
        a = h.answer
        for key in ("text", "custom", "target", "target_name", "lang_block"):
            self.assertIn(key, a)
        self.assertFalse(a["custom"])
        self.assertNotIn("{{", a["text"])
        self.assertIn("creating a markdown file", a["text"], "the page's own composition has the contract, in place")
        self.assertEqual(a["lang_block"], K.language_text("studio-doc", "it"))
        built = studio_server.studio_prompt(languages.get("it"))
        self.assertEqual((a["prompt"], a["header"], a["contract"]), (built.text, built.header, built.contract))
        self.assertTrue(a["prompt"].startswith(K.version_line("studio-doc", "it") + "\n\ntarget: it — this document is about Italian"))
        self.assertTrue(a["prompt"].rstrip().endswith(a["contract"].rstrip()))
        self.assertLess(a["prompt"].index(a["lang_block"][:60]), a["prompt"].index(a["contract"][:60]))

    def test_the_studio_route_for_a_custom_prompt_is_the_persons_text_whole_and_still_has_the_contract_after_it(self):
        # a person's own prompt is chosen in the row's menu and asked for by its id (lib/prompts.py)
        with tempfile.TemporaryDirectory() as td, mock.patch.object(studio_server.prompts, "STORE", os.path.join(td, "config", "prompts.json")):
            pid = studio_server.prompts.save({"surface": "studio-doc", "name": "mine", "kind": "replace", "text": "Custom rules."})["id"]
            h = Handler(query={"target": ["ar"], "prompt": [pid]})
            studio_server.api_prompt_get(h)
        a = h.answer
        self.assertIn("Mixed-direction sequences for Arabic — binding", a["prompt"], "the rule for the boxes of a right-to-left target goes with it")
        self.assertTrue(a["header"].endswith(" · custom: mine"))
        self.assertLess(a["prompt"].index("Custom rules."), a["prompt"].index("creating a markdown file"))
        self.assertNotIn("prompt_error", a)

    def test_a_custom_prompt_the_kit_refuses_is_told_in_words_and_is_no_prompt(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(studio_server.prompts, "STORE", os.path.join(td, "config", "prompts.json")):
            pid = studio_server.prompts.save({"surface": "studio-doc", "name": "mine", "kind": "replace", "text": "Say it."})["id"]
            # Parseh moved on since: the name it was saved with is not one the kit fills in now
            with open(studio_server.prompts.STORE, encoding="utf-8") as f:
                kept = json.load(f)
            kept["prompts"][0]["text"] = "Say {{THIS}}."
            with open(studio_server.prompts.STORE, "w", encoding="utf-8") as f:
                json.dump(kept, f)
            h = PathHandler("/api/prompt?target=fa&prompt=" + pid)
            studio_server.api_prompt_get(h)
        self.assertEqual(h.code, 400)
        self.assertIn("THIS", h.answer["error"])
        self.assertNotIn("prompt", h.answer)

    def test_the_exercise_route_keeps_its_shape_and_the_authoring_prompts_contract_is_not_in_it(self):
        h = Handler({"markdown": "---\ntitle: T\ntarget: fa\n---\n\nLesson", "decks": []})
        studio_server.api_exercise_prompt(h)
        # the old keys are kept, and what the dialog draws its boxes and types from is added (E-CONTRACT), and the
        # short request for a chat that has the skill (lib/skills.py, a0.4.2 W6)
        self.assertEqual(sorted(h.answer), ["boxes", "custom", "options", "preticked", "prompt", "size", "skill", "types",
                                            "vocabulary"])
        self.assertIs(h.answer["custom"], False, "Parseh's own: no prompt of the person's was asked for")
        p = h.answer["prompt"]
        self.assertTrue(p.startswith(K.version_line("studio-exercises", "fa")))
        self.assertIn("Return the complete updated Markdown document in one fenced", p)
        self.assertNotIn("creating a markdown file", p, "the studio's contract asks for a file, this one for a fence")
        self.assertTrue(p.rstrip().endswith("```"))

    def test_the_region_routes_hand_out_the_prompt_the_lab_builds(self):
        for surface, fn, args in (("video-region", glossregion.video_prompt,
                                   (promptlab._fixture("videos", languages.get("fa"))[0], 0, 3)),
                                  ("book-region", glossregion.book_prompt,
                                   (promptlab._fixture("books", languages.get("fa"))[0], 0, 5))):
            for kw, mode in (({}, None), ({"regloss": True}, "regloss"), ({"perfield": True}, "perfield")):
                r = fn(*args, **kw)
                self.assertEqual(r["prompt"], promptlab.build(surface, "fa", mode).text)
                self.assertTrue(r["prompt"].startswith(K.version_line(surface, "fa", "en", mode)))

    def test_a_prompt_the_kit_refuses_is_a_refusal_in_words_not_a_crash(self):
        book = promptlab._fixture("books", languages.get("fa"))[0]
        with mock.patch.object(glossregion.promptkit, "assemble", side_effect=K.PromptError("it still carries {{X}}")):
            with self.assertRaises(glossregion.Refused) as e:
                glossregion.book_prompt(book, 0, 5)
        self.assertIn("the prompt could not be made", str(e.exception))

    def test_a_title_that_says_double_braces_is_a_title(self):
        # the book's and the video's own words are put in as they are, never taken for a placeholder
        book = promptlab._fixture("books", languages.get("it"))[0]
        with tempfile.TemporaryDirectory() as td:
            copy = os.path.join(td, "italian", "mini-it")
            shutil.copytree(book, copy)
            path = os.path.join(copy, "book.json")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace("Il pezzo di legno", "Il {{DATA}} e {{LANGUAGE}}"))
            r = glossregion.book_prompt(copy, 0, 5)
        self.assertIn("- title: Il {{DATA}} e {{LANGUAGE}}", r["prompt"])

    def test_a_language_file_that_names_what_nothing_fills_is_refused_by_every_route_in_words(self):
        # a language file whose text says {{GLOSS_LANGUAGE}} where no gloss language is known
        # (the studio's, or the new-book page's, which fills the rest in a browser)
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "fa.md"), "w", encoding="utf-8") as f:
                f.write("# Persian\n\n## Reading\n\nGloss it in {{GLOSS_LANGUAGE}}, for {{LANGUAGE}}.\n")
            with mock.patch.object(K, "LANG_DOCS", td):
                self.assertEqual(K.language_text("studio-doc", "fa").splitlines()[-1],
                                 "Gloss it in {{GLOSS_LANGUAGE}}, for Persian.")
                self.assertIn("in English, for Persian", K.language_text("video-new", "fa", gloss="en"))
                h = Handler({"markdown": "---\ntitle: T\ntarget: fa\n---\n\nx", "decks": []})
                studio_server.api_exercise_prompt(h)
                self.assertIn("GLOSS_LANGUAGE", h.answer["error"])
                h = Handler(query={"target": ["fa"]})
                studio_server.api_prompt_get(h)
                self.assertIn("GLOSS_LANGUAGE", h.answer["prompt_error"])
                self.assertNotIn("prompt", h.answer)

    def test_the_conventions_the_new_book_page_embeds_have_no_placeholder_left(self):
        # the page fills its template in a browser and never looks into what it embeds
        for code in languages.CODES:
            self.assertNotIn("{{", newbook.conventions(languages.get(code)), code)

    def test_the_video_prompt_before_and_with_its_captions(self):
        before = ytpages.chat_prompt(None, "fa")
        self.assertEqual(before, ytpages.assembled_chat(None, "fa").text)
        self.assertTrue(before.startswith(K.version_line("video-new", "fa", "en")))
        caps = [{"start": 3, "text": "سلام {{x}}", "plain": False}]
        full = ytpages.full_prompt("fA6bK2mQ8sT", {"title": "T {{t}}", "channel": "C"}, caps, None, "fa", "en")
        self.assertTrue(full.startswith(before))
        self.assertIn("سلام {{x}}", full)
        self.assertIn("- title: T {{t}}", full)
        self.assertTrue(full.rstrip().endswith("Now answer with the JSON, and nothing else."))

    def test_the_video_prompt_borrows_no_example_from_the_shelf(self):
        # the owner's own video and every video a person has made are on a shelf, and none of them is
        # quoted: the add page's example is the language's (docs/lang/<code>.md, Example), so a fresh
        # install has one and the same prompt is made on every machine
        videos = os.path.join(ROOT, "tests", "fixtures", "videos")
        shelves = {"it": [("italian", "kL9mN1oP3qR", os.path.join(videos, "italian", "kL9mN1oP3qR"))],
                   # the owner's own video, by the id the old code looked for
                   "fa": [("persian", "nFoM8JraEek", os.path.join(videos, "persian", "fA6bK2mQ8sT"))]}
        for code, shelf in shelves.items():
            with mock.patch.object(ytpages, "video_dirs", lambda: []):
                bare = ytpages.chat_prompt(None, code)
            with mock.patch.object(ytpages, "video_dirs", lambda shelf=shelf: shelf):
                shelved = ytpages.chat_prompt(None, code)
            self.assertTrue(shelved == bare, "%s: a video on the shelf changed the prompt" % code)
            self.assertTrue("\n\n\n" not in bare, "%s: a heading or a blank stands over a hole" % code)

    def test_the_example_of_the_video_prompt_is_the_languages_own_section(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "it.md"), "w", encoding="utf-8") as f:
                f.write("# Italian\n\nOpen.\n\n## Example\n\nTwo chunks: `Quanto costano | le mele`.\n")
            with mock.patch.object(K, "LANG_DOCS", td):
                p = ytpages.chat_prompt(None, "it")
                self.assertEqual(p.count("Two chunks: `Quanto costano | le mele`."), 1)
                self.assertNotIn("Example", K.language_text("studio-doc", "it"))
        # a language whose file has no Example yet has none, and no heading standing over a hole
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "it.md"), "w", encoding="utf-8") as f:
                f.write("# Italian\n\nOpen.\n\n## Vocabulary\n\nA rule.\n")
            with mock.patch.object(K, "LANG_DOCS", td):
                p = ytpages.chat_prompt(None, "it")
                self.assertIn("A rule.", p)
                self.assertNotIn("Example", p)

    def test_the_tidy_prompt(self):
        caps = [{"start": 1, "text": "سلام {{x}} سلام"}]
        p = tidier.prompt(caps, "fa")
        self.assertTrue(p.startswith(K.version_line("transcript-tidy", "fa")))
        self.assertIn("سلام {{x}} سلام", p)
        self.assertTrue(p.rstrip().endswith("```"))
        self.assertLess(p.index("WHAT TO GIVE BACK"), p.index("THE TRANSCRIPT:"))
        self.assertLess(p.index("THE RULES"), p.index("WHAT TO GIVE BACK"), "the contract comes after the rules")

    def test_the_new_book_template_has_no_marks_once_its_parts_are_taken_out(self):
        # the short vowels' two blocks are the book's own (lib/making.py settles them for each book)
        tpl = K.flat(K._template("book-new"), {"marks": True, "nomarks": False})
        self.assertNotIn("{{?", tpl)
        self.assertNotIn("{{/", tpl)
        self.assertIn("{{WORDS_STEP}}", tpl)
        self.assertIn("### The per-paragraph JSON", tpl)


class TheMeaningRule(ControlledMachine):
    """docs/meaning-rule.md (brief 6.1): written once, embedded by {{MEANING_RULE}} in every prompt
    that asks for `en`, and resolved with the languages of the prompt it is in."""

    # the files that make a prompt, or that a prompt is made from: none may carry a copy of the rule
    SOURCES = ("docs/region-prompt.md", "docs/new-book-prompt.md", "youtube/docs/chat-prompt.md",
               "youtube/docs/conventions.md", "youtube/PROMPT.md", "markdown/exlex/PROMPT.md",
               "markdown/exlex/EXERCISES_PROMPT.md", "lib/making.py", "lib/glossregion.py", "lib/newbook.py",
               "youtube/lib/ytpages.py", "youtube/lib/tidy.py", "lib/promptkit.py")

    def test_it_is_written_once_and_every_other_text_embeds_or_names_it(self):
        with open(K.MEANING_RULE, encoding="utf-8") as f:
            rule = f.read()
        # a sentence from each of its six points and from its closing check
        said = [re.sub(r"\s+", " ", s).strip() for s in (
            "A chunk's `en` renders that chunk's own words and only those.",
            "never move a meaning to where",
            "Never translate the sentence first and then divide the translation among the chunks.",
            "write natural {{GLOSS_LANGUAGE}}",
            "Lower case, except names and \"I\"",
            "`en` and `voc` agree",
            "cover the {{LANGUAGE}} and read one sentence's `en` lines in a row")]
        for s in said:
            self.assertIn(s, re.sub(r"\s+", " ", rule), s)
        for path in self.SOURCES + tuple("docs/lang/%s.md" % c for c in languages.CODES):
            with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                text = re.sub(r"\s+", " ", f.read())
            for s in said:
                self.assertTrue(s not in text, "%s carries a copy of the meaning rule (%r...): "
                                "`{{MEANING_RULE}}` embeds it" % (path, s[:40]))

    def test_the_kit_embeds_it_in_the_four_gloss_prompts_and_no_other(self):
        for surface in K.SURFACES[:-1]:
            names = {n for n, _ in K.placeholders(surface)}
            self.assertEqual("MEANING_RULE" in names, surface in GLOSSED, surface)
            template = tidier.PROMPT if surface == "transcript-tidy" else K._template(surface)
            self.assertEqual("{{MEANING_RULE}}" in template, surface in GLOSSED, surface)

    @staticmethod
    def glossed_in(surface, code, gloss, mode):
        """The prompt of a surface for a language whose meanings are written in `gloss`.  A stretch of a
        book or a video takes its gloss language from the book's or the video's own file, so the lab's
        fixture is copied and told it is glossed in that language."""
        if surface not in REGIONS:
            return promptlab.build(surface, code, mode, gloss)
        kind = "books" if surface == "book-region" else "videos"
        src, tmp = promptlab._fixture(kind, languages.get(code))
        try:
            with tempfile.TemporaryDirectory() as td:
                copy = os.path.join(td, os.path.basename(src))
                shutil.copytree(src, copy, ignore=shutil.ignore_patterns("reader", "*.pdf", "*.aux", "*.log", "*.toc"))
                path = os.path.join(copy, "book.json" if kind == "books" else "video.json")
                with open(path, encoding="utf-8") as f:
                    meta = json.load(f)
                meta["gloss"] = gloss
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False)
                if kind == "books":
                    ctx, units, _folded, _known = glossregion._book_units(copy, 0, 5)
                else:
                    ctx, units, _segs = glossregion._video_units(copy, 0, 3)
                return glossregion.assembled(ctx, units, glossregion._mode(mode == "regloss", mode == "perfield"))[0]
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    def test_a_persian_video_glossed_in_italian_says_persian_and_italian(self):
        for code, gloss in (("fa", "it"), ("it", "fa"), ("ja", "de"), ("en", "en")):
            L, G = languages.get(code), languages.gloss(gloss)
            for surface in GLOSSED:
                for mode in ((None, "regloss") if surface in REGIONS else (None,)):
                    with self.subTest(language=code, gloss=gloss, surface=surface, mode=mode):
                        a, c = self.glossed_in(surface, code, gloss, mode), Ctx(surface, code, mode, L, G)
                        self.assertEqual(says_which_languages_the_meaning_rule_is_about(a, c), [])
                        self.assertEqual(has_the_meaning_rules_example(a, c), [])
                        self.assertEqual(has_the_meaning_rule_once(a, c), [])

    def test_the_sentence_on_running_over_a_caption_is_a_videos_alone(self):
        for code in ("fa", "it", "ja"):
            for surface in GLOSSED:
                rule = _the_rule_in(promptlab.build(surface, code).text)
                self.assertEqual("ends with `…`" in _flat(rule), surface.startswith("video-"), (code, surface))

    def test_an_italian_glossed_video_asks_for_italian_and_for_no_english(self):
        # the add page's prompt names the gloss language where it asks for the blurb and for the meanings
        text = promptlab.build("video-new", "fa", None, "it").text
        for said in ("one Italian sentence on what the video is", "every meaning in Italian, saying what its own chunk says"):
            self.assertIn(said, text)
        for old in ("one English sentence", "short English meaning", "every meaning in English"):
            self.assertTrue(old not in text, "the prompt still says %r" % old)


class TheSweep(unittest.TestCase):
    """The known defects of the files W2 rewrites (brief 6.6)."""

    def test_the_conventions_of_a_video_name_no_list_of_languages(self):
        # the registry is the list (docs/languages.md): a language added tomorrow is not left out of a rule
        # because nobody counted it, and a file named by its code is `docs/lang/<code>.md` and no other
        with open(os.path.join(ROOT, "youtube", "docs", "conventions.md"), encoding="utf-8") as f:
            lines = f.read().split("\n")
        codes = "|".join(languages.CODES)
        for n, line in enumerate(lines, 1):
            named = [L.name for L in languages.LANGS.values() if re.search(r"\b%s\b" % L.name, line)]
            self.assertLess(len(named), 3, "conventions.md:%d lists languages: %s" % (n, ", ".join(named)))
            self.assertIsNone(re.search(r"`(%s)\.md`" % codes, line), "conventions.md:%d names a language's file" % n)

    def test_the_add_pages_prompt_carries_no_batch_file_shape_which_is_the_project_prompts(self):
        # the conventions are read by the add page's prompt and by the agent of youtube/PROMPT.md: the
        # shape of a part file is the second's, and the first asks for a shape of its own
        for code in ("fa", "ja", "it"):
            text = promptlab.build("video-new", code).text
            for said in ("parts/NN.json", "youtube/PROMPT.md"):
                self.assertTrue(said not in text, "the %s add page's prompt names %s" % (code, said))
        with open(os.path.join(ROOT, "youtube", "PROMPT.md"), encoding="utf-8") as f:
            project = f.read()
        self.assertIn("`parts/*.json`", project)
        self.assertIn("a `plain` flag or a `chapter`", project)

    def test_the_audio_sync_prompt_for_one_persian_book_is_retired_with_nothing_left_pointing_at_it(self):
        # what it asked for (timings from the narration, an audio-synced reader, a review page) is
        # lib/timestamp.py and the reader's by ear; no prompt sends a language to it any more
        self.assertFalse(os.path.exists(os.path.join(ROOT, "docs", "audio-sync-prompt.md")))
        for path in ("lib/promptkit.py", "docs/new-book-prompt.md", "docs/prompt-kit.md", "docs/languages.md",
                     "youtube/PROMPT.md", "youtube/docs/conventions.md"):
            with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                self.assertTrue("audio-sync-prompt" not in f.read(), "%s still names the retired prompt" % path)

    def test_no_prompt_file_names_the_owners_own_video(self):
        for path in ("docs/region-prompt.md", "docs/new-book-prompt.md", "youtube/docs/chat-prompt.md",
                     "youtube/docs/conventions.md", "youtube/PROMPT.md", "youtube/lib/ytpages.py",
                     "docs/meaning-rule.md"):
            with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                self.assertTrue("nFoM8JraEek" not in f.read(), "%s names the owner's own video" % path)
        self.assertFalse([n for n, _ in K.placeholders() if n.startswith("EXAMPLE_")],
                         "the add page's example is the language's own section: no placeholder for a borrowed one")


class StudioPromptRoutes(unittest.TestCase):
    """The routes that edit the studio's prompt, on a temporary library: the page
    edits and copies a text and knows no marks, so none is ever handed to it."""

    def test_none_of_them_hands_out_the_mark_of_a_part_and_a_custom_text_is_kept_whole(self):
        # the custom prompt lives in the person's own prompts since a0.4.2 (lib/prompts.py): its
        # store is pointed at the temporary tree too, never at the computer's config/
        with tempfile.TemporaryDirectory() as td, mock.patch.object(studio_server.store, "LIB", studio_server.Path(td)), \
                mock.patch.object(studio_server.prompts, "STORE", os.path.join(td, "config", "prompts.json")):
            h = Handler(query={"target": ["fa"]})
            studio_server.api_prompt_get(h)
            self.assertFalse(h.answer["custom"])
            self.assertNotIn("{{", h.answer["text"])
            self.assertIn("creating a markdown file", h.answer["text"])
            h = Handler({"text": "My own prompt."})
            studio_server.api_prompt_put(h)
            self.assertEqual(h.answer, {"text": "My own prompt.", "custom": True})
            # what is kept is one of the person's own prompts now, and is chosen like the others: by its id
            h = Handler(query={"target": ["fa"], "prompt": [studio_server.prompts.STUDIO_ID]})
            studio_server.api_prompt_get(h)
            self.assertEqual((h.answer["text"], h.answer["custom"]["name"]), ("My own prompt.", studio_server.prompts.STUDIO_NAME))
            self.assertTrue(h.answer["prompt"].startswith(K.version_line("studio-doc", "fa", None, None, studio_server.prompts.STUDIO_NAME)))
            h = Handler()
            studio_server.api_prompt_delete(h)
            self.assertFalse(h.answer["custom"])
            self.assertNotIn("{{", h.answer["text"])
            self.assertIn("creating a markdown file", h.answer["text"])
            self.assertEqual(h.answer["text"], studio_server.promptboxes.legacy_text(languages.get("fa")))
            self.assertFalse(os.path.exists(os.path.join(td, "_prompt.md")))


# --- the studio's prompt in parts (brief 7): the reserved list, the boxes, the routes -------------------
# THE RESERVED LIST, DRIVEN.  Every construct the studio reads that the prompt names -- in its box when the
# box is ticked, in the reserved list at the end of the prompt when it is not -- with the sample line that
# makes it, read here by the real parser (mdparser for the blocks, htmlgen for the page).  The rows were
# driven by hand in Phase 0 (a0.4.2's research: 121 of them, four of the brief's starter's own wrong: a
# table's separator needs pipes, a `|` in a heading is an entry only in the script targets when the first
# field is in the script, bold is not barred from target-language words, a code fence's inside is READ).
#   id  box that teaches it, or "always"  target  the sample  its blocks  its blocks as the middle line of
#   a wrapped paragraph  what the page shows  its words in the box  its words in the reserved list  [document]
# A row whose reserved-list words are None is a detail of its box only.  `{CODE}` is the target's own code.
Construct = collections.namedtuple("Construct", "id box target sample blocks wrapped page in_box in_list doc")
WRAP = "Prose line one goes on for a good while and\n%s\nline three ends the sentence."


def C(id, box, target, sample, blocks, wrapped, page, in_box, in_list, doc=""):
    return Construct(id, box, target, sample, blocks.split(), wrapped.split() if wrapped else None,
                     page, in_box, in_list, doc)


# THE WORD COLOURED IN PARTS (`[[ab[cd]{teal}ef]]`, the a0.4.3 dialect, DIALECT-A043.md), and what the prompt's examples of it
# are checked with where this tree's parser does not know it.  The grammar, from the a0.4.3 branch's own tests:
#   [[ plain letters and pieces [text]{colour} ]]  on ONE line, no `[[` inside, at least one piece whose colour is a name of the
#   palette (any case) or #RRGGBB; a piece that is not valid stays as typed; the braces after `]]` hold linguistic marks
#   (translit: kana: reading:) and never a colour -- braces that are anything else stay as typed after the word.
_PALETTE = ("crimson", "indigo", "teal", "violet", "amber")
_PIECE = re.compile(r"\[([^\[\]]+)\]\{([^{}]*)\}")
_MARK_KEY = re.compile(r"(?:^|\s)(translit|kana|reading):")


def coloured_words(text):
    """The words coloured in parts that a text holds, as the grammar says: [(start, end, the word flattened, {mark: value})]."""
    found, i = [], 0
    while True:
        i = text.find("[[", i)
        if i < 0:
            return found
        nl = text.find("\n", i)
        close = text.find("]]", i + 2, len(text) if nl < 0 else nl)
        inside = text[i + 2:close] if close >= 0 else None
        flat, pieces, k = [], 0, 0
        while inside is not None and "[[" not in inside and k < len(inside):
            piece = _PIECE.match(inside, k)
            if piece and (piece.group(2).strip().lower() in _PALETTE
                          or re.fullmatch(r"#[0-9A-Fa-f]{6}", piece.group(2).strip())):
                flat.append(piece.group(1))
                pieces += 1
                k = piece.end()
            else:
                flat.append(inside[k])
                k += 1
        if not pieces or inside is None or "[[" in inside:
            i += 2
            continue
        end, marks = close + 2, {}
        braces = re.match(r"\{([^{}\[\]\n]*)\}", text[end:])
        keys = list(_MARK_KEY.finditer(braces.group(1))) if braces else []
        if keys and not braces.group(1)[:keys[0].start()].strip():
            for n, key in enumerate(keys):
                stop = keys[n + 1].start() if n + 1 < len(keys) else None
                marks["kana" if key.group(1) == "reading" else key.group(1)] = braces.group(1)[key.end():stop].strip()
            end += braces.end()
        found.append((i, end, "".join(flat), marks))
        i = end


class GrammarAsScanner:
    """The grammar above, offered the way exlex/segcolour.py is (find_runs, flatten) for what reads a page with a scanner
    of it -- so that the wiring of the page is held in a tree that has no a0.4.3 dialect yet."""

    @staticmethod
    def find_runs(text):
        return iter(coloured_words(text))

    @staticmethod
    def flatten(text):
        out, at = [], 0
        for start, end, flat, _marks in coloured_words(text):
            out.extend((text[at:start], flat))
            at = end
        out.append(text[at:])
        return "".join(out)


# the rows of the a0.4.3 dialect: named in the prompt whatever the parser is, and read by the REAL parser only where there is
# one that knows them (ColouredWordsOfA043)
RESERVED_A043 = (
    C('mark-coloured-word', 'colourparts', 'fa', 'A word [[ک[ت]{crimson}[ا]{indigo}ب]]{translit:ketāb} here.', 'para', 'para', ('class="fa segmented-colour-run"', 'data-fa="کتاب"', 'data-translit="ketāb"'), '[[ab[cd]{teal}ef]]', '[[ab[cd]{teal}ef]]'),
    C('mark-coloured-word-latin-target', 'colourparts', 'it', 'A word [[disfa[re]{crimson}]] here.', 'para', 'para', ('data-fa="disfare"',), 'needs no `{tl}` mark', None),
    C('coloured-headword', 'colourparts', 'fa', '## [[ک[ت]{crimson}[ا]{indigo}ب]] | ketāb | from Arabic | = *book*', 'voce', 'para voce para', ('class="voce-fa segmented-colour-run"', 'data-fa="کتاب"'), 'headword of a vocabulary entry', None),
)


RESERVED = (
    C('fence-exercise', 'exercises', 'fa', ':::exercise single-choice', 'exercise', 'para exercise', ('Exercise needs attention', 'missing its closing'), ':::exercise', ':::exercise'),
    C('fence-math', 'math', 'fa', ':::math', 'math', 'para math', ('class="math mathblock"',), ':::math', ':::math'),
    C('fence-latex', 'latex', 'fa', '::::latex chemistry {width=45}', 'latex', 'para latex', ('latex-fail', 'closed by a line of four colons'), '::::latex', '::::latex'),
    C('fence-bare', 'always', 'fa', ':::note', 'para', 'para', (':::note',), None, ':::note'),
    C('mark-tl-inline', 'blocks', 'fa', 'A phrase [یک فایل PDF]{tl} inside prose.', 'para', 'para', ('data-tl-kind="mark"', 'class="fa fa-l fa-rich"'), '[…]{tl}', '[…]{tl}'),
    C('mark-tl-block', 'blocks', 'fa', '[یک فایل PDF]{tl bg=sand}', 'para', 'para', ('class="fa-par rtl-bg-sand"', 'data-tl-kind="mark"'), 'bg=', 'bg='),
    C('mark-tl-code-alias', 'blocks', 'fa', 'A phrase [یک فایل PDF]{fa} and [یک فایل PDF]{rtl} inside prose.', 'para', 'para', ('data-tl-kind="mark"',), '{CODE}', '{CODE}'),
    C('mark-tl-code-alias-latin', 'blocks', 'it', 'A [bello]{it} here.', 'para', 'para', ('data-fa="bello"',), '{CODE}', '{CODE}'),
    C('mark-tl-brackets-inside', 'blocks', 'fa', 'A [a [b] c]{tl} nested bracket.', 'para', 'para', ('[a [b] c]{tl}',), 'no square brackets inside', None),
    C('mark-tl-long-form', 'blocks', 'fa', '[\nفلان می\u200cرود ⏎\nبه پارک\n]{tl}', 'para', 'para', ('class="fa-par"', '<br>'), 'opening bracket alone on the first line', None),
    C('mark-tl-font', 'blocks', 'fa', '[hello]{tl font=nastaliq}', 'para', 'para', ('fa-alt fa-nasta', 'data-tl-font="nastaliq"'), 'font=', 'font='),
    C('mark-tl-vertical', 'blocks', 'ja', '[古池や⏎蛙飛び込む⏎水の音]{tl vertical height=8}', 'para', 'para', ('tl-vertical', '--tl-vh:8em'), 'vertical', 'vertical'),
    C('line-break', 'blocks', 'fa', 'First line ⏎ second line', 'para', 'para', ('First line<br>second line',), '⏎', '⏎'),
    C('mark-la-block', 'latin', 'fa', '[A note set apart.]{la align=center bg=sage width=70}', 'para', 'para', ('class="la-par align-center rtl-bg-sage"', 'width:70%'), '{la}', '{la}'),
    C('mark-la-inline', 'latin', 'fa', 'A sentence with [a Latin block]{la} inside it.', 'para', 'para', ('[a Latin block]{la}',), 'inside a sentence', None),
    C('mark-math', 'math', 'fa', 'The formula [a^2+b^2=c^2]{math} holds.', 'para', 'para', ('class="math" data-tex="a^2+b^2=c^2"',), ']{math}', ']{math}'),
    C('mark-math-swallow', 'math', 'fa', 'See [1] and [x^2]{math} here.', 'para', 'para', ('data-tex="1] and [x^2"',), '[sic]', None),
    C('mark-latex', 'latex', 'fa', 'An inline drawing [\\ce{H2O}]{latex} here.', 'para', 'para', ('data-latex-src="\\ce{H2O}"',), ']{latex', ']{latex'),
    C('mark-colour-name', 'colours', 'fa', 'A [word]{teal} here.', 'para', 'para', ('class="fac fac-teal" data-color="teal"',), 'crimson', 'crimson'),
    C('mark-colour-hex', 'colours', 'fa', 'A [word]{#C2185B} here.', 'para', 'para', ('data-color="#C2185B"', 'color:#C2185B'), 'hex value', '#RRGGBB'),
    C('mark-colour-unknown', 'always', 'fa', 'A [word]{red} here.', 'para', 'para', ('[word]{red}',), None, '{red}'),
    C('mark-latin-target-any-word', 'always', 'it', 'A [word]{note} here.', 'para', 'para', ('data-fa="word"', 'class="fac"'), None, 'ANY `[text]{word}`'),
    C('mark-translit', 'translit', 'fa', 'A [word]{teal translit:wɜːd} here.', 'para', 'para', ('data-translit="wɜːd"', 'data-color="teal"'), 'translit:', 'translit:'),
    C('mark-kana', 'reading', 'ja', 'A [漢字]{kana:かんじ translit:kanji} here.', 'para', 'para', ('data-kana="かんじ"', 'data-translit="kanji"'), 'kana:', 'kana:'),
    C('box-quote', 'boxes', 'fa', '> a quotation', 'box', 'para box para', ('<div class="box">',), '`>`', '`>`'),
    C('box-no-space', 'boxes', 'fa', '>= 5 at the head of a line', 'box', 'para box para', (), 'space after', 'space after'),
    C('box-heading-inside', 'boxes', 'fa', '> ## A heading in a box\n> text', 'box', 'para box para', ('<div class="box"><h2 class="section"',), 'no heading inside', None),
    C('box-nested', 'boxes', 'fa', '> outer\n> > inner', 'box', 'para box para', ('<div class="box"><p>outer</p>', '<div class="box"><p>inner</p></div>'), 'No box inside a box', None),
    C('list-dash', 'lists', 'fa', '- an item', 'list', 'para list para', ('<ul><li>an item</li></ul>',), '`- `', '`- `'),
    C('list-star', 'lists', 'fa', '* an item', 'list', 'para list para', ('<ul><li>an item</li></ul>',), '`* `', '`* `'),
    C('list-plus', 'lists', 'fa', '+ an item', 'list', 'para list para', ('<ul><li>an item</li></ul>',), '`+ `', '`+ `'),
    C('enum-dot', 'lists', 'fa', '1. an item', 'enum', 'para enum para', ('<ol><li>an item</li></ol>',), '`1. `', '`1. `'),
    C('enum-year', 'lists', 'fa', '1921. The year the war ended', 'enum', 'para enum para', ('<ol><li>The year the war ended</li></ol>',), '1921', '1921'),
    C('enum-paren', 'lists', 'fa', '2) an item', 'enum', 'para enum para', ('<ol><li>an item</li></ol>',), '`2) `', '`2) `'),
    C('enum-script-digits', 'always', 'fa', '۱. یک مورد', 'enum', 'para enum para', (), None, '۱. '),
    C('list-indented', 'always', 'fa', '- one\n  - nested\n  continued line', 'list', 'para list para', ('<ul><li>one<ul><li>nested continued line</li></ul></li></ul>',), None, 'indenting the line'),
    C('list-labelled', 'lists', 'fa', '- **Register** formal\n- **Origin** Arabic', 'list', 'para list para', ('<dl class="desc">', '<dt>Register</dt>'), 'bold label', None),
    C('list-task-marker', 'always', 'fa', '- [ ] a task', 'list', 'para list para', ('<li>[ ] a task</li>',), None, '- [ ] task'),
    C('list-rule-lookalike', 'always', 'fa', '* * *', 'list', 'para list para', ('<ul><li><em> </em></li></ul>',), None, '* * *'),
    C('enum-blank-lines', 'lists', 'fa', '1. first\n\n2. second\n\n3. third', 'enum enum enum', 'para enum enum enum para', ('<ol><li>first</li></ol>', '<ol><li>third</li></ol>'), 'a blank line ends a list', None),
    C('table', 'tables', 'fa', '| a | b |\n|---|---|', 'table', 'para table para', ('<table class="bt"',), '|---|---|', '|---|---|'),
    C('table-one-column', 'tables', 'fa', '| a |\n|---|\n| 1 |', 'para', 'para', ('| a | |---| | 1 |',), 'two columns at least', None),
    C('table-pipe-in-cell', 'tables', 'fa', '| a \\| b | c |\n|---|---|\n| 1 \\| 2 | 3 |', 'table', 'para table para', ('<th class="a-l">a \\</th>', '<th class="a-l">b</th>'), 'Never put a `|` inside a cell', None),
    C('vocab-heading', 'vocab', 'fa', '## کتاب | ketāb | from Arabic | = *book*', 'voce', 'para voce para', ('class="voce"',), '<headword> |', 'holds a `|`'),
    C('vocab-heading-latin-target', 'vocab', 'it', '## A section | with a pipe', 'voce', 'para voce para', ('class="voce"',), 'ANY `|`', 'ANY `|`'),
    C('section-pipe-script-target', 'always', 'fa', '## Book | ketāb', 'section', 'para section para', ('Book | ketāb',), None, 'never contains a `|`'),
    C('footnote-ref', 'notes', 'fa', 'A claim[^a] here.\n\n[^a]: The note.', 'para', '', ('class="fnref"', 'The note.'), '[^x]', '[^x]'),
    C('footnote-def', 'notes', 'fa', '[^a]: The note text.', '', 'para para', (), ']:', ']:'),
    C('footnote-inline', 'notes', 'fa', 'A claim ^[a short note] here.', 'para', 'para', ('class="fnref"', '>a short note<'), '^[', '^['),
    C('footnote-ref-undefined', 'notes', 'fa', 'The value x[^2] is squared.', 'para', 'para', ('class="fnref"', 'id="fn-1"></span>'), 'x[^2]', 'x[^2]'),
    C('link-web', 'links', 'fa', 'See [the site](https://example.com/x) now.', 'para', 'para', ('<a class="lnk" href="https://example.com/x"',), 'https://', 'https://'),
    C('link-other-scheme', 'links', 'fa', 'See [the page](page.html) now.', 'para', 'para', ('See the page now.',), 'any other `[', 'any other `['),
    C('link-doc', 'always', 'fa', 'See [the note](doc:Another note) now.', 'para', 'para', ('class="doclink-dead"', 'data-name="Another note"'), None, '[…](doc:…)'),
    C('link-bare-url', 'always', 'fa', 'See <https://example.com/x> and https://example.com/y now.', 'para', 'para', ('&lt;https://example.com/x&gt;',), None, '<https://…>'),
    C('link-ref-style', 'always', 'fa', '[text][ref]\n\n[ref]: https://example.com', 'para para', 'para para', ('[text][ref]', '[ref]: https://example.com'), None, '[text][ref]'),
    C('picture-line', 'always', 'fa', '![a map](images/map.png){width=50 align=center}', 'image', 'para image para', ('<figure',), None, '`![…](images/…)`'),
    C('recording-line', 'always', 'fa', '![a word](audio/word.mp3)', 'audio', 'para audio para', ('figure class="img audio',), None, '`![…](audio/…)`'),
    C('video-line', 'always', 'fa', '@[a talk](https://youtu.be/dQw4w9WgXcQ)', 'video', 'para video para', ('youtube-nocookie.com/embed/dQw4w9WgXcQ',), None, '`@[…](…)`'),
    C('gloss-script', 'gloss', 'fa', 'کتاب = *book*', 'para', 'para', ('<span class="eq">=</span>', '<em>book</em>'), ' = *', ' = *'),
    C('gloss-latin-target', 'gloss', 'it', '[bello]{tl} = *beautiful*', 'para', 'para', ('<span class="eq">=</span>', '<em>beautiful</em>'), '[word]{tl} = *', ' = *'),
    C('gloss-unmarked-latin', 'gloss', 'it', 'bello = *beautiful*', 'para', 'para', (), 'an unmarked word followed by `=`', None),
    C('wrong-form-cross', 'forms', 'fa', 'A wrong form ✗goed is marked.', 'para', 'para', ('class="ungram-run"', 'class="ungram-x"'), '✗', '✗'),
    C('wrong-form-emoji', 'forms', 'fa', 'A wrong form ❌goed is marked.', 'para', 'para', ('class="ungram-run"',), '❌', '❌'),
    C('right-tick', 'forms', 'fa', 'The right form ✅ goed.', 'para', 'para', ('✅ goed',), '✅', '✅'),
    C('blank-slot', 'exercises', 'fa', 'Fill the [[name]] here.', 'para', 'para', ('Fill the [[name]] here.',), '[[', '[['),
    C('bold', 'emphasis', 'fa', 'A **bold** word.', 'para', 'para', ('<strong>bold</strong>',), '**bold**', '**'),
    C('italic', 'emphasis', 'fa', 'An *italic* word.', 'para', 'para', ('<em>italic</em>',), '*italic*', 'italic'),
    C('two-stars', 'emphasis', 'fa', 'The sum 5 * 3 = 15 and a * b = c.', 'para', 'para', ('5 <em> 3 = 15 and a </em> b',), 'in a sentence italicise everything between them', 'in a sentence italicise everything between them'),
    C('italic-target-language', 'emphasis', 'fa', '*کتاب* keeps its stars.', 'para', 'para', (), 'never around a word of the target language', None),
    C('bold-italic-triple', 'emphasis', 'fa', 'A ***both*** word.', 'para', 'para', ('<strong><em>both</strong></em>',), '***both***', None),
    C('code-span', 'emphasis', 'fa', 'Press `Ctrl+S` and `**b**` now.', 'para', 'para', ('<code>Ctrl+S</code>', '<code><strong>b</strong></code>'), 'Backticks', 'Backticks'),
    C('section', 'always', 'fa', '## A section', 'section', 'para section para', ('<h2 class="section"',), None, 'for sections'),
    C('subsection', 'always', 'fa', '### A subsection', 'subsection', 'para subsection para', ('<h3 class="subsection"',), None, 'for subsections'),
    C('section-typed-number', 'always', 'fa', '## 2. A section', 'section', 'para section para', ('</span> A section</h2>',), None, '## 2. The four words'),
    C('section-gloss-tail', 'always', 'fa', '## A section = *a gloss*', 'section', 'para section para', ('</span> A section</h2>',), None, 'trailing `= *…*`'),
    C('title-hash', 'always', 'fa', '# A title', '', 'para para', ('<h1>A title</h1>',), None, 'No `#` heading', 'title'),
    C('title-hash-dropped', 'always', 'fa', '# A second title', '', 'para para', (), None, 'a `#` line is dropped'),
    C('heading-deep', 'always', 'fa', '#### A deep heading', 'para', 'para', ('#### A deep heading',), None, '`####`'),
    C('heading-setext', 'always', 'fa', 'A title\n===', 'para', 'para', ('A title ===',), None, '`===`'),
    C('rule-dashes', 'always', 'fa', '---', '', 'para para', (), None, '`---`'),
    C('rule-stars', 'always', 'fa', '***', '', 'para para', (), None, '`***`'),
    C('rule-underscores', 'always', 'fa', '___', '', 'para para', (), None, '`___`'),
    C('front-matter', 'always', 'fa', '---\ntitle: T\nsubtitle: S\nnote: N\nlang: en\ntarget: fa\n---\nBody text', 'para', '', (), None, 'title: <short title>', 'whole'),
    C('front-matter-other-key', 'always', 'fa', '---\ntitle: T\nauthor: Someone\ntags: [a, b]\n---\nBody', 'para', '', (), None, 'any other key is dropped', 'whole'),
    C('front-matter-unclosed', 'always', 'fa', '---\ntitle: T\nBody that is never reached', '', '', (), None, 'never closed', 'whole'),
    C('front-matter-unknown-target', 'always', 'fa', '---\ntitle: T\ntarget: xx\n---\nBody', 'para', '', (), None, 'not in the registry', 'whole'),
    C('front-matter-late', 'always', 'fa', 'Some text\n\n---\ntitle: T\n---\nBody', 'para para para', '', (), None, 'nothing before it', 'whole'),
    C('target-paragraph', 'always', 'fa', 'سلام دوست من', 'para', 'para', ('class="fa-display"',), None, 'no Latin letter at all'),
    C('target-paragraph-punct', 'blocks', 'fa', 'سلام!', 'para', 'para', ('class="fa-par"',), 'ASCII punctuation', None),
    C('target-punctuation-in-run', 'punct', 'fa', 'Three words: کند، آهسته، یواش — a list.', 'para', 'para', ('data-fa="کند، آهسته، یواش"',), 'own punctuation', 'own punctuation'),
    C('wrapped-lines-joined', 'always', 'ja', '日本語の文章です。\nこれは二行目です。', 'para', '', ('日本語の文章です。 これは二行目です。',), None, 'ONE line'),
    C('mark-split-across-lines', 'always', 'fa', 'A [word]\n{teal} split mark.', 'para', '', ('[word] {teal}',), None, 'Never break a line inside a mark'),
    C('backslash-escape', 'always', 'fa', 'An escaped \\*star\\* and \\# hash.', 'para', 'para', ('\\*star\\*',), None, 'backslash escapes'),
    C('code-fence', 'always', 'fa', "```python\nprint('hi')\n# a comment in code\nx = [1, 2]\n```", 'para para', 'para para', ('```python print(&#x27;hi&#x27;)', 'x = [1, 2] ```'), None, 'code fences'),
    C('code-fence-inside-read', 'always', 'fa', '```\n- item in fence\n> quote in fence\n## heading in fence\n```', 'para list box section para', 'para list box section para', (), None, 'the code inside a fence is read as Markdown'),
    C('code-indent', 'always', 'fa', '    indented four spaces', 'para', 'para', ('<p>indented four spaces</p>',), None, 'indented code'),
    C('underscore-emphasis', 'always', 'fa', 'An _italic_ and __bold__ word.', 'para', 'para', ('_italic_ and __bold__',), None, '`_x_`'),
    C('strikethrough', 'always', 'fa', 'A ~~struck~~ word.', 'para', 'para', ('~~struck~~',), None, '`~~x~~`'),
    C('dollar-math', 'always', 'fa', 'The formula $a^2$ and $$b^2$$ stay.', 'para', 'para', ('$a^2$ and $$b^2$$',), None, '`$x$`'),
    C('html-tag', 'always', 'fa', 'A <b>bold</b> word and <br> a break.', 'para', 'para', ('&lt;b&gt;bold&lt;/b&gt;', '&lt;br&gt;'), None, '`<b>`'),
    C('html-entity', 'always', 'fa', 'Fish &amp; chips &copy; here.', 'para', 'para', ('Fish &amp;amp; chips &amp;copy; here.',), None, '`&amp;`'),
    C('html-comment', 'always', 'fa', 'Before <!-- a comment --> after.', 'para', 'para', ('&lt;!-- a comment -', 'class="arrow"'), None, '`<!-- -->`'),
    C('definition-list', 'always', 'fa', 'Term\n: its definition', 'para', 'para', ('Term : its definition',), None, 'definition lists'),
    C('shortcode', 'always', 'fa', 'A {{< figure src="x" >}} shortcode.', 'para', 'para', ('{{&lt; figure src=&quot;x&quot; &gt;}}',), None, 'shortcodes'),
    C('emoji-shortcode', 'always', 'fa', 'A :smile: here.', 'para', 'para', ('A :smile: here.',), None, '`:smile:`'),
    C('heading-attribute', 'always', 'fa', '## A section {#id}', 'section', 'para section para', ('A section {#id}',), None, '`## Title {#id}`'),
    C('heading-closing-hashes', 'always', 'fa', '## A section ##', 'section', 'para section para', ('A section ##</h2>',), None, 'no closing hashes'),
    C('quotes-dashes-ellipsis', 'always', 'fa', 'A "quote" -- and --- and ... here.', 'para', 'para', ('&quot;quote&quot; -- and --- and ...',), None, '“ ”'),
    C('emoji', 'always', 'fa', 'Well done 🎉 indeed.', 'para', 'para', ('Well done 🎉 indeed.',), None, 'no emoji'),
    C('arrow-glyph', 'always', 'fa', 'a → b', 'para', 'para', ('<span class="arrow">→</span>',), None, '→ themselves'),
    C('star-in-word', 'emphasis', 'fa', 'Two stars: 2*3*4 stay.', 'para', 'para', ('2*3*4',), 'never inside a word', None),
) + RESERVED_A043


def _document(row, sample=None):
    text = row.sample if sample is None else sample
    if row.doc == "whole":
        return text
    head = "---\n" + ("" if row.doc == "title" else "title: T\n")
    return head + "lang: en\ntarget: %s\n---\n\n%s\n" % (row.target, text)


def _page(md):
    return re.sub(r' data-src-line="\d+"', "", htmlgen.render_document(md, colophon=False)["html"])


def _mismatch(row):
    """What the parser makes of a row's sample against what the row says: [] where they agree."""
    out = []
    got = [b["type"] for b in mdparser.parse(_document(row))[1]]
    if got != row.blocks:
        out.append("reads as %r, the row says %r" % (got, row.blocks))
    page = _page(_document(row))
    out += ["the page lacks %r" % s for s in row.page if s not in page]
    if row.wrapped is not None:
        wrapped = [b["type"] for b in mdparser.parse(_document(row, WRAP % row.sample))[1]]
        if wrapped != row.wrapped:
            out.append("as the middle line of a paragraph it reads as %r, the row says %r" % (wrapped, row.wrapped))
    return out


_INSTRUCTIONS = {}


def _instructions(code, ticked):
    """The instructions of the studio's prompt with only these boxes ticked."""
    key = (code, tuple(ticked))
    if key not in _INSTRUCTIONS:
        _INSTRUCTIONS[key] = studio_server.studio_prompt(languages.get(code), boxes=list(ticked)).instructions
    return _INSTRUCTIONS[key]


def _box_own(code, box):
    """The lines a box adds to a prompt with nothing else ticked: its own paragraphs."""
    bare = set(_instructions(code, ()).split("\n"))
    return "\n".join(x for x in _instructions(code, (box,)).split("\n") if x not in bare)


def _reserved(code, ticked):
    return promptboxes.split_reserved(_instructions(code, ticked))[1]


def _said(row, words):
    return words.replace("{CODE}", "{%s}" % row.target)


class ReservedList(ControlledMachine):
    def setUp(self):
        super().setUp()
        _INSTRUCTIONS.clear()

    def test_the_table_is_one_row_a_construct_and_each_row_names_a_box_or_none(self):
        ids = [r.id for r in RESERVED]
        self.assertEqual(len(ids), len(set(ids)))
        for r in RESERVED:
            self.assertIn(r.box, ("always",) + promptboxes.BOX_IDS, r.id)
            self.assertIn(r.target, languages.CODES, r.id)
            self.assertTrue(r.in_box or r.in_list, r.id)
            if r.box == "always":
                self.assertTrue(r.in_list and not r.in_box, "%s belongs to no box: the prompt says it always" % r.id)
        # a box of behaviour (the order of RTL boxes, keeping what a pasted document has) writes no mark of its own
        writes = set(promptboxes.BOX_IDS) - {"rtl", "revise"}
        self.assertEqual(sorted(writes - {r.box for r in RESERVED}), [], "a box with no row")

    def test_the_parser_reads_each_sample_as_the_construct_the_row_says(self):
        for r in RESERVED:
            if r in RESERVED_A043:
                continue                    # the a0.4.3 dialect's: ColouredWordsOfA043 reads them with its own parser
            with self.subTest(construct=r.id):
                self.assertEqual(_mismatch(r), [])

    def test_the_comparison_refuses_a_wrong_expectation(self):
        # the driver has teeth: it is seen to fail on each of the three ways a row can be wrong
        by = {r.id: r for r in RESERVED}
        self.assertEqual(_mismatch(by["list-dash"]), [])
        self.assertTrue(_mismatch(by["list-dash"]._replace(blocks=["para"])), "a list is not a paragraph")
        self.assertTrue(_mismatch(by["list-dash"]._replace(wrapped=["para"])), "it cuts a wrapped paragraph in three")
        self.assertTrue(_mismatch(by["list-dash"]._replace(page=("<ol><li>an item</li></ol>",))), "a bullet, not a number")
        # the brief's own starter said a line of dashes under a `|` line is a table: it is a dropped rule
        starter = by["table"]._replace(sample="| a | b |\n-----")
        self.assertTrue(_mismatch(starter))

    def test_each_construct_is_named_in_its_box_when_the_box_is_ticked(self):
        for r in RESERVED:
            if r.box == "always" or not r.in_box:
                continue
            with self.subTest(construct=r.id, box=r.box):
                self.assertIn(_said(r, r.in_box), _box_own(r.target, r.box))

    def test_each_construct_is_named_in_the_reserved_list_when_the_box_is_not_ticked(self):
        for r in RESERVED:
            if r.box == "always" or not r.in_list:
                continue
            others = [b for b in promptboxes.BOX_IDS if b != r.box]
            for ticked in ((), others):
                with self.subTest(construct=r.id, box=r.box, others_ticked=bool(ticked)):
                    self.assertIn(_said(r, r.in_list), _reserved(r.target, ticked))

    def test_a_box_ticked_takes_its_line_out_of_the_reserved_list(self):
        # it is taught in its box, so it is no longer among the marks the model was not taught
        for r in RESERVED:
            if r.box == "always" or not r.in_list:
                continue
            with self.subTest(construct=r.id, box=r.box):
                self.assertNotEqual(_reserved(r.target, ()), _reserved(r.target, (r.box,)))

    def test_a_construct_that_belongs_to_no_box_is_named_whatever_is_ticked(self):
        for r in RESERVED:
            if r.box != "always":
                continue
            for ticked in ((), promptboxes.BOX_IDS):
                with self.subTest(construct=r.id, all_ticked=bool(ticked)):
                    self.assertIn(_said(r, r.in_list), _instructions(r.target, ticked))


# --- the boxes, the presets, level and length, and what a request may ask ----------------------------------
BRIEF_BOXES = ("vocab gloss translit reading punct rtl blocks latin forms lists tables boxes emphasis notes links "
               "colours colourparts math latex exercises revise").split()     # `colourparts` is the a0.4.3 dialect's, not the brief's
# the words each box's block opens with: how a box is told from another in a prompt
LABELS = {"vocab": "**Vocabulary entries.**", "gloss": "**Glosses.**", "translit": "**Marks for the ",
          "reading": "**The reading mark.**", "punct": "**Punctuation: use the Latin mark",
          "rtl": "**Mixed-direction sequences:", "blocks": "**Passages, display lines",
          "latin": "**Latin blocks.**", "forms": "**Ungrammatical and correct forms.**", "lists": "**Lists.**",
          "tables": "**Tables.**", "boxes": "**Highlight boxes.**", "emphasis": "**Bold and italic.**",
          "notes": "**Footnotes.**", "links": "**Links.**", "colours": "**Colour marks.**",
          "colourparts": "**Colour inside a word.**", "math": "**Formulas.**", "latex": "**LaTeX drawings.**", "exercises": "**Exercises.**",
          "revise": "**Revising a document you are given.**"}
# THE OLD PROMPTS, in characters, as Phase 0 measured them on the commit before this work (28368c6): the
# studio's, whole and with the language's file pasted whole, and the exercise prompt before the page
OLD_STUDIO = {"fa": 31919, "ar": 31817, "it": 31764, "ja": 33689, "fr": 39850, "de": 40260, "tr": 40728,
              "en": 42892, "hi": 35242, "es": 41041, "zh": 42258}
OLD_EXERCISES = {"fa": 44840, "ar": 44736, "it": 40441, "ja": 42366, "fr": 48527, "de": 48937, "tr": 49405,
                 "en": 51569, "hi": 43919, "es": 49718, "zh": 50935}


class PathHandler(Handler):
    """The handler as the studio's dispatch makes one: `query` parsed the way it parses it -- a blank value is
    dropped, so `?boxes=` is not in it -- and the raw `path` beside it; the status is kept."""

    def __init__(self, path=None, body=None):
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(path or "").query)
        Handler.__init__(self, body, query)
        self.path, self.code = path or "", 200

    def send_json(self, answer, code=200):
        self.answer, self.code = answer, code


class StudioBoxes(ControlledMachine):
    def setUp(self):
        super().setUp()
        _INSTRUCTIONS.clear()

    def test_the_boxes_are_the_briefs_in_its_order_each_with_a_name_a_line_and_a_group(self):
        self.assertEqual(list(promptboxes.BOX_IDS), BRIEF_BOXES)
        for b in promptboxes.BOXES:
            self.assertTrue(b.name and b.line and b.group, b.id)
        self.assertEqual([g for g, _ in itertools.groupby(b.group for b in promptboxes.BOXES)],
                         ["what it says", "how it is laid out", "extras", "a document you paste"])

    def test_the_presets_are_the_briefs(self):
        by = {p.id: set(p.boxes) for p in promptboxes.PRESETS}
        short = {"gloss", "translit", "lists", "emphasis"}
        self.assertEqual([p.id for p in promptboxes.PRESETS], ["short", "lesson", "vocabulary", "exercises", "all", "none"])
        self.assertEqual(by["short"], short)
        self.assertEqual(by["lesson"], short | {"vocab", "tables", "boxes", "notes", "links", "forms"})
        self.assertEqual(by["vocabulary"], {"vocab", "gloss", "translit", "reading", "tables", "lists"})
        self.assertEqual(by["exercises"], by["lesson"] | {"exercises"})
        self.assertEqual(by["all"], set(BRIEF_BOXES))
        self.assertEqual(by["none"], set())
        self.assertEqual([p.id for p in promptboxes.PRESETS if p.default], ["lesson"])
        for name in ("short", "lesson", "vocabulary", "exercises"):
            self.assertFalse(by[name] & {"colours", "colourparts", "math", "latex"},
                             "no preset ticks colours, coloured words, formulas or drawings")
        for name in ("short", "lesson", "vocabulary"):
            self.assertNotIn("exercises", by[name], "exercises only in the last")

    def test_a_box_a_language_cannot_use_is_hidden(self):
        for code in languages.CODES:
            L = languages.get(code)
            hidden = set(promptboxes.BOX_IDS) - promptboxes.shown_ids(L)
            want = set()
            if not L.reading:
                want.add("reading")
            if not L.chars:
                want.add("punct")
            if not L.rtl:
                want.add("rtl")
            self.assertEqual(hidden, want, code)
        self.assertEqual({c for c in languages.CODES if "reading" in promptboxes.shown_ids(languages.get(c))}, {"ja"})
        self.assertEqual({c for c in languages.CODES if "rtl" in promptboxes.shown_ids(languages.get(c))}, {"fa", "ar"})
        self.assertNotIn("punct", promptboxes.shown_ids(languages.get("it")))

    def test_a_box_is_taught_when_it_is_ticked_and_only_then(self):
        for code in ("fa", "ja", "it"):
            L = languages.get(code)
            for box in promptboxes.BOX_IDS:
                text = _instructions(code, (box,))
                if not promptboxes.shown(promptboxes.BY_ID[box], L):
                    self.assertNotIn(LABELS[box], text, "%s is never taught to %s" % (box, code))
                    continue
                for other, label in LABELS.items():
                    self.assertEqual(label in text, other == box, (code, box, other))
        for code in ("fa", "ja", "it"):
            self.assertFalse([1 for label in LABELS.values() if label in _instructions(code, ())], code)

    def test_every_flag_the_template_names_is_one_the_studio_gives(self):
        with open(K.TEMPLATES["studio-exercises"], encoding="utf-8") as f:
            texts = [K._template("studio-doc"), f.read()]
        names = set()
        for text in texts:
            names |= set(re.findall(r"\{\{\?(\w+)\}\}", text)) - set(K._MARKS)
        for code in languages.CODES:
            for exercising in (False, True):
                given = set(promptboxes.flags(languages.get(code), (), None, exercising))
                self.assertEqual(sorted(names - given - set(K.surface_flags("studio-doc"))), [], (code, exercising))
        self.assertIn("lang_own_script", names)
        self.assertIn("type_fill_blanks", names)

    def test_any_set_of_boxes_builds_in_every_language_with_no_mark_left(self):
        rng = random.Random(29)
        for code in languages.CODES:
            sets = [[], list(promptboxes.BOX_IDS)] + [list(p.boxes) for p in promptboxes.PRESETS]
            sets += [[b for b in promptboxes.BOX_IDS if rng.random() < 0.5] for _ in range(20)]
            for ticked in sets:
                a = studio_server.studio_prompt(languages.get(code), boxes=ticked)
                self.assertNotIn("{{", a.text, (code, ticked))

    def test_no_prompt_cites_a_rule_by_its_number(self):
        # today's rules cited each other ("rule 4 says ..."): with a box off a number points at nothing
        for code in ("fa", "it", "ja", "en"):
            for ticked in ((), promptboxes.BOX_IDS) + tuple((b,) for b in promptboxes.BOX_IDS):
                text = _instructions(code, ticked)
                self.assertIsNone(re.search(r"\brules? \d+\b|\(rule \d", text), (code, ticked))

    def test_what_two_features_say_to_each_other_is_said_only_when_both_are_ticked(self):
        pairs = (("vocab", "lists", "it", "Inside an entry, use a bullet list"),
                 ("translit", "colours", "fa", "A colour mark can share the braces"),
                 ("reading", "translit", "ja", "the kana goes first"),
                 ("boxes", "lists", "it", "A bullet list inside the box is allowed"),
                 ("gloss", "blocks", "fa", "keep the usual pattern"),
                 ("punct", "blocks", "fa", "typically inside a `[…]{tl}` block"),
                 ("translit", "vocab", "fa", "Leave the mark out of `##` entries"),
                 ("exercises", "math", "it", "A blank may not sit inside a formula"),
                 ("colourparts", "colours", "fa", "Colouring a whole word stays the colour mark's job"),
                 ("colourparts", "translit", "fa", "of the whole word goes there"),
                 ("colourparts", "reading", "ja", "The reading of the whole word goes there too"),
                 ("exercises", "colourparts", "fa", "may go in a prompt, an answer row"))
        for a, b, code, words in pairs:
            with self.subTest(pair=(a, b)):
                self.assertIn(words, _instructions(code, (a, b)))
                for ticked in ((), (a,), (b,)):
                    self.assertNotIn(words, _instructions(code, ticked))

    def test_the_lesson_is_under_sixty_percent_of_the_old_prompt_in_every_language(self):
        # the owner's reason for the boxes: "sometimes these prompts are too long for some LLMs"
        lesson = next(p for p in promptboxes.PRESETS if p.default).boxes
        for code in languages.CODES:
            new = len(studio_server.studio_prompt(languages.get(code), boxes=list(lesson)).text)
            self.assertLess(new, 0.6 * OLD_STUDIO[code], "%s: the lesson is %d characters, the old prompt %d" % (
                code, new, OLD_STUDIO[code]))

    def test_the_exercise_prompt_for_a_page_that_uses_nothing_is_under_sixty_percent_of_the_old_one(self):
        for code in languages.CODES:
            new = len(promptlab.build("studio-exercises", code).text)
            self.assertLess(new, 0.6 * OLD_EXERCISES[code], (code, new, OLD_EXERCISES[code]))

    def test_the_size_of_a_box_is_what_ticking_it_adds(self):
        for code in ("fa", "ja", "en"):
            L = languages.get(code)
            bare = len(studio_server.studio_prompt(L, boxes=[]).text)
            for row in promptboxes.catalog(L, ()):
                if row["shown"]:
                    grown = len(studio_server.studio_prompt(L, boxes=[row["id"]]).text)
                    self.assertEqual(row["chars"], grown - bare, (code, row["id"]))
                    self.assertGreater(row["chars"], 100, (code, row["id"]))
                else:
                    self.assertEqual(row["chars"], 0)

    def test_a_persons_text_is_told_from_the_default_by_the_boxes_it_carries(self):
        # what Lane F's row reads: a text with the studio's blocks takes the boxes, one without is copied whole
        self.assertTrue(promptboxes.has_box_marks("Rules.\n{{?lists}}Use lists.{{/lists}}"))
        self.assertTrue(promptboxes.has_box_marks("{{?no_math}}No formulas.{{/no_math}}"))
        self.assertFalse(promptboxes.has_box_marks("Just my rules for {{LANGUAGE}}, {{?studio}}here{{/studio}}."))
        self.assertFalse(promptboxes.has_box_marks(""))
        # and the kit resolves such a text with the same flags the default is resolved with
        text = "Rules.{{?lists}} Use lists.{{/lists}}{{?no_lists}} No lists.{{/no_lists}}"
        it = languages.get("it")
        on = studio_server.studio_prompt(it, custom_text=text, boxes=["lists"]).instructions
        off = studio_server.studio_prompt(it, custom_text=text, boxes=[]).instructions
        self.assertIn("Rules. Use lists.", on)
        self.assertNotIn("No lists.", on)
        self.assertIn("Rules. No lists.", off)

    def test_tokens_as_a_chatbot_counts_them(self):
        self.assertEqual(promptboxes.tokens("a" * 400), 100)
        self.assertEqual(promptboxes.tokens("س" * 400), 200)
        self.assertEqual(promptboxes.tokens("日" * 400), 200)
        self.assertEqual(promptboxes.tokens("क" * 400), 200)
        self.assertEqual(promptboxes.size("a" * 400), {"chars": 400, "tokens": 100})

    def test_level_and_length_are_each_one_line_after_the_contract_and_not_said_adds_none(self):
        L = languages.get("it")
        plain = studio_server.studio_prompt(L)
        self.assertEqual(plain.data, "")
        self.assertTrue(plain.text.rstrip().endswith(plain.contract.rstrip()))
        for level, length in (("beginner", ""), ("", "short"), ("advanced", "exhaustive"), ("upper-intermediate", "page")):
            a = studio_server.studio_prompt(L, level=level, length=length)
            lines = a.data.split("\n\n")
            self.assertEqual(len(lines), bool(level) + bool(length), (level, length))
            self.assertTrue(all("\n" not in x for x in lines))
            self.assertEqual(bool(level) and level in a.data, bool(level), (level, length))
            self.assertTrue(a.text.rstrip().endswith(a.data.rstrip()))
            self.assertLess(a.text.index(a.contract), a.text.index(a.data), "after the answer contract")
        self.assertEqual([i for i, _ in [(x["id"], x["name"]) for x in promptboxes.levels()]],
                         ["", "beginner", "lower-intermediate", "intermediate", "upper-intermediate", "advanced"])
        self.assertEqual([x["id"] for x in promptboxes.lengths()], ["", "short", "page", "exhaustive"])
        self.assertEqual(promptboxes.lengths()[2]["name"], "about a page")
        with self.assertRaises(promptboxes.Refused):
            studio_server.studio_prompt(L, level="expert")
        with self.assertRaises(promptboxes.Refused):
            studio_server.studio_prompt(L, length="long")

    def test_exhaustive_is_the_persons_to_ask_for_and_not_in_the_rules(self):
        # "Be exhaustive" (rule 15) went: length is what the person chooses
        for code in ("fa", "en"):
            self.assertNotIn("exhaustive", _instructions(code, promptboxes.BOX_IDS))
            self.assertIn("exhaustive", studio_server.studio_prompt(languages.get(code), length="exhaustive").text)


class StudioRoutes(ControlledMachine):
    def get(self, query):
        h = PathHandler("/api/prompt?" + query)
        studio_server.api_prompt_get(h)
        return h

    def test_the_default_answer_is_the_lesson_and_carries_what_the_page_draws(self):
        a = self.get("target=it").answer
        L = languages.get("it")
        for key in ("text", "custom", "target", "target_name", "lang_block", "prompt", "header", "contract",
                    "boxes", "presets", "levels", "lengths", "always_chars", "size"):
            self.assertIn(key, a)
        self.assertEqual([b["id"] for b in a["boxes"]], BRIEF_BOXES)
        self.assertEqual({b["id"] for b in a["boxes"] if b["on"]}, set(next(p.boxes for p in promptboxes.PRESETS if p.default)))
        for b in a["boxes"]:
            self.assertEqual(sorted(b), ["chars", "group", "id", "line", "name", "on", "shown"])
        self.assertEqual({b["id"] for b in a["boxes"] if not b["shown"]}, {"reading", "punct", "rtl"})
        self.assertEqual([p["id"] for p in a["presets"]], ["short", "lesson", "vocabulary", "exercises", "all", "none"])
        self.assertEqual([p["id"] for p in a["presets"] if p.get("default")], ["lesson"])
        self.assertEqual(a["presets"][-1], {"id": "none", "name": "none", "boxes": []})
        self.assertEqual(a["always_chars"], len(studio_server.studio_prompt(L, boxes=[]).text))
        self.assertEqual(a["size"], promptboxes.size(a["prompt"]))
        self.assertEqual(a["prompt"], studio_server.studio_prompt(L).text)
        self.assertLess(a["always_chars"], a["size"]["chars"])

    def test_boxes_asked_for_are_the_only_ones_taught_and_ticked_in_the_answer(self):
        a = self.get("target=fa&boxes=gloss,tables").answer
        self.assertEqual([b["id"] for b in a["boxes"] if b["on"]], ["gloss", "tables"])
        self.assertIn("**Glosses.**", a["prompt"])
        self.assertIn("**Tables.**", a["prompt"])
        self.assertNotIn("**Lists.**", a["prompt"])
        self.assertIn("`- `, `* ` and `+ ` at the head of a line", a["prompt"], "an unticked box is still named")

    def test_a_blank_boxes_means_none_and_an_absent_one_means_the_lesson(self):
        none = self.get("target=fa&boxes=").answer
        self.assertEqual([b["id"] for b in none["boxes"] if b["on"]], [])
        self.assertEqual(none["size"]["chars"], none["always_chars"])
        lesson = self.get("target=fa").answer
        self.assertEqual({b["id"] for b in lesson["boxes"] if b["on"]}, set(next(p.boxes for p in promptboxes.PRESETS if p.default)))
        # the same, asked through a handler whose query kept the blank
        h = Handler(query={"target": ["fa"], "boxes": [""]})
        studio_server.api_prompt_get(h)
        self.assertEqual([b["id"] for b in h.answer["boxes"] if b["on"]], [])

    def test_an_id_that_is_no_box_or_level_or_length_is_refused_in_words_with_a_400(self):
        for query, said in (("boxes=vocab,nonsense", "nonsense"), ("boxes=x", "'x'"), ("level=expert", "expert"),
                            ("length=forever", "forever")):
            h = self.get("target=fa&" + query)
            self.assertEqual(h.code, 400, query)
            self.assertIn(said, h.answer["error"])
            self.assertNotIn("prompt", h.answer)
        self.assertIn("vocab", self.get("target=fa&boxes=nonsense").answer["error"], "and says what they are")

    def test_a_box_a_language_cannot_use_is_hidden_and_never_ticked(self):
        fa = self.get("target=fa&boxes=rtl,reading,punct").answer
        self.assertEqual([b["id"] for b in fa["boxes"] if b["on"]], ["punct", "rtl"], "reading is Japanese's")
        it = self.get("target=it&boxes=rtl,reading,punct").answer
        self.assertEqual([b["id"] for b in it["boxes"] if b["on"]], [])
        self.assertFalse(any(b["chars"] for b in it["boxes"] if not b["shown"]))
        self.assertNotIn("Mixed-direction", it["prompt"])
        ja = self.get("target=ja&boxes=reading,blocks").answer
        self.assertIn("**The reading mark.**", ja["prompt"])
        self.assertIn("vertical", ja["prompt"])
        self.assertIn("{tl font=gothic}", ja["prompt"])
        self.assertIn("{tl font=nastaliq}", self.get("target=fa&boxes=blocks").answer["prompt"])
        self.assertNotIn("font=", self.get("target=it&boxes=blocks").answer["prompt"].split("**Reserved marks.**")[0])

    def test_level_and_length_are_copied_as_one_line_each_at_the_end(self):
        a = self.get("target=fa&level=beginner&length=page").answer
        self.assertTrue(a["prompt"].rstrip().endswith("Write for a learner at the beginner level.\n\nMake it about a page long."))
        self.assertLess(a["prompt"].index(a["contract"]), a["prompt"].index("Write for a learner"))
        self.assertGreater(a["size"]["chars"], self.get("target=fa").answer["size"]["chars"])

    def test_the_legacy_fields_stay_for_a_page_of_before_the_boxes(self):
        a = self.get("target=fa&boxes=").answer
        self.assertNotIn("{{", a["text"])
        self.assertEqual(a["text"], promptboxes.legacy_text(languages.get("fa")), "the whole prompt, whatever was ticked")
        self.assertIn("creating a markdown file", a["text"])
        self.assertIn("Mixed-direction sequences: distinguish the direction", a["text"] + a["lang_block"])
        self.assertEqual(a["lang_block"], K.language_text("studio-doc", "fa"))
        self.assertFalse(a["custom"])


class ExerciseRoutes(ControlledMachine):
    def post(self, **body):
        h = PathHandler(None, dict({"decks": []}, **body))
        studio_server.api_exercise_prompt(h)
        return h

    PAGE = ("---\ntitle: T\ntarget: it\n---\n\nIn Italian, [bello]{tl} = *beautiful*.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
            ":::exercise fill-blanks\nprompt: Complete.\ntext: Il [[a]] è bello.\n- [a] mare\n- [ ] sole\n:::\n")

    def test_what_the_page_uses_is_ticked_and_named_by_the_parser(self):
        a = self.post(markdown=self.PAGE).answer
        # a Latin-script target marks every run `[bello]{tl}`, which its prompt always teaches: that is no box
        self.assertEqual(a["preticked"], {"boxes": ["gloss", "tables", "emphasis"], "types": ["fill-blanks"]})
        block = self.post(markdown="---\ntitle: T\ntarget: it\n---\n\n[Una frase intera.]{tl bg=sand}\n").answer
        self.assertEqual(block["preticked"]["boxes"], ["blocks"], "a block of its own, and a tint, are the box's")
        persian = self.post(markdown="---\ntitle: T\ntarget: fa\n---\n\nA phrase [یک فایل PDF]{tl} inside prose.\n").answer
        self.assertEqual(persian["preticked"]["boxes"], ["blocks"], "a Latin word inside a Persian phrase is the box's")
        self.assertEqual([b["id"] for b in a["boxes"] if b["on"]], a["preticked"]["boxes"])
        self.assertEqual([t["id"] for t in a["types"] if t["on"]], ["fill-blanks"])
        self.assertEqual([t["id"] for t in a["types"]], list(promptboxes.TYPE_IDS))
        self.assertEqual(len(a["types"]), 13)
        self.assertEqual(a["size"], promptboxes.size(a["prompt"]))
        # a rtl target's mixed-direction rule is always in, so the dialog offers no box for it; the types are its exercises
        self.assertFalse([b for b in a["boxes"] if b["id"] in ("exercises", "rtl") and b["shown"]])
        self.assertIn("`fill-blanks` — `text:` contains `[[slot]]`", a["prompt"])
        self.assertNotIn("`order-sentences`", a["prompt"])

    RICH = """---
title: Persian
target: fa
---

## کتاب | ketāb | from Arabic | = *book*

The word [کتاب]{crimson translit:ketāb} = *book*, and a [PDF فایل]{tl} inside a phrase.[^1] A list, a link and a wrong form:

- **one** [the site](https://example.org/x) ✗کتابا
- two ^[an inline note]

| a | b |
|---|---|
| 1 | 2 |

> a box with a formula [x^2]{math}

[Set apart.]{la bg=sage}

:::math
a+b
:::

::::latex
\\ce{H2O}
::::

![a map](images/map.png)

[^1]: A note.

Three words: کند، آهسته، یواش.

A word coloured in parts: [[ک[ت]{crimson}[ا]{indigo}ب]].
"""

    def test_a_page_that_uses_every_feature_ticks_every_box_the_dialog_offers(self):
        a = self.post(markdown=self.RICH).answer
        offered = [b["id"] for b in a["boxes"] if b["shown"]]
        self.assertNotIn("reading", offered, "a Persian page has no reading to teach")
        self.assertEqual(sorted(set(promptboxes.BOX_IDS) - set(offered)), ["exercises", "reading", "rtl"])
        # the coloured word is read by the a0.4.3 dialect's scanner (ColouredWordsOfA043 holds it with the real one)
        read = [b for b in offered if HAVE_A043 or b != "colourparts"]
        self.assertEqual(a["preticked"]["boxes"], read)
        # and each was found by what it is: the parser's blocks, and the marks the page carries
        for box in read:
            with self.subTest(box=box):
                self.assertIn(box, promptboxes.page_uses(self.RICH)[0])

    def test_a_page_that_uses_nothing_ticks_nothing_and_a_document_of_prose_is_prose(self):
        self.assertEqual(promptboxes.page_uses("---\ntitle: T\ntarget: en\n---\n\nJust a paragraph of English prose.\n"), ([], []))
        self.assertEqual(promptboxes.page_uses("Prose only, no front matter.")[0], [])

    def test_a_page_with_no_exercise_ticks_every_type_and_the_person_may_choose(self):
        page = "---\ntitle: T\ntarget: it\n---\n\nLesson\n"
        a = self.post(markdown=page).answer
        self.assertEqual(a["preticked"]["types"], list(promptboxes.TYPE_IDS))
        self.assertEqual(a["preticked"]["boxes"], [])
        chosen = self.post(markdown=page, types=["flashcard", "yes-no"], boxes=["lists"]).answer
        self.assertEqual([t["id"] for t in chosen["types"] if t["on"]], ["flashcard", "yes-no"])
        self.assertEqual([b["id"] for b in chosen["boxes"] if b["on"]], ["lists"])
        self.assertIn("`flashcard` — unscored.", chosen["prompt"])
        self.assertIn("`yes-no` or `true-false`", chosen["prompt"])
        self.assertNotIn("`single-choice`", chosen["prompt"])
        self.assertIn("Do not place `=>`", chosen["prompt"], "rows of pairs are asked for")
        only = self.post(markdown=page, types=["single-choice"]).answer["prompt"]
        self.assertNotIn("Do not place `=>`", only)
        self.assertIn("**Lists.**", chosen["prompt"])

    def test_the_flashcard_is_most_of_the_types_and_each_type_has_a_size(self):
        types = self.post(markdown="---\ntitle: T\ntarget: en\n---\n\nx\n").answer["types"]
        by = {t["id"]: t["chars"] for t in types}
        self.assertTrue(all(n > 0 for n in by.values()), by)
        self.assertEqual(max(by, key=by.get), "flashcard", by)
        self.assertGreater(by["flashcard"], 1500)
        self.assertGreater(by["flashcard"], sum(n for k, n in by.items() if k != "flashcard") / 2, by)

    def test_a_request_that_asks_for_nothing_or_for_what_is_not_there_is_refused_in_words(self):
        page = "---\ntitle: T\ntarget: it\n---\n\nx\n"
        for body, said in ((dict(types=[]), "at least one exercise type"), (dict(types=["nope"]), "nope"),
                           (dict(boxes=["nope"]), "nope"), (dict(level="expert"), "expert"), (dict(length="long"), "long")):
            h = self.post(markdown=page, **body)
            self.assertEqual(h.code, 400, body)
            self.assertIn(said, h.answer["error"])

    def test_level_and_length_come_before_the_page(self):
        page = "---\ntitle: T\ntarget: it\n---\n\nx\n"
        p = self.post(markdown=page, level="advanced", length="short").answer["prompt"]
        self.assertLess(p.index("Write for a learner at the advanced level."), p.index("Here is the complete Markdown page"))
        self.assertLess(p.index("Return the complete updated"), p.index("Write for a learner"))

    def test_the_dialog_lists_the_decks_of_the_pages_language_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = studio_server.Path(td)
            for folder, lang in (("japanese", "ja"), ("persian", "fa")):
                deck = root / folder / "known"
                (deck / "cards").mkdir(parents=True)
                (deck / "deck.json").write_text('{"name": "Known %s", "lang": "%s"}' % (lang, lang), encoding="utf-8")
            with mock.patch.object(studio_server, "ANKI_DIR", root):
                h = PathHandler("/api/exercise-decks")
                studio_server.api_exercise_decks(h)
                self.assertEqual(sorted(d["path"] for d in h.answer["decks"]), ["japanese/known", "persian/known"])
                h = PathHandler("/api/exercise-decks?target=ja")
                studio_server.api_exercise_decks(h)
                self.assertEqual([d["path"] for d in h.answer["decks"]], ["japanese/known"])
                h = PathHandler("/api/exercise-decks?target=fa")
                studio_server.api_exercise_decks(h)
                self.assertEqual([d["path"] for d in h.answer["decks"]], ["persian/known"])
                h = PathHandler("/api/exercise-decks?target=it")
                studio_server.api_exercise_decks(h)
                self.assertEqual(h.answer["decks"], [])


# --- the word coloured in parts (DIALECT-A043.md): what the prompts say of it ----------------------------------------------
# THE WORDS THE EXAMPLES SPELL, flattened: the word a reader copies, searches and looks up
FLAT = {"[[ab[cd]{teal}ef]]": "abcdef", "[[بر[گشت]{teal}[م]{crimson}]]": "برگشتم",
        "[[un[break]{crimson}able]]": "unbreakable", "[[ab[cd]{teal}ef]]{translit:…}": "abcdef",
        "[[日[本]{indigo}語]]{kana:にほんご}": "日本語"}
# WHAT THE GRAMMAR SAYS, one row a shape: the source, then the word it makes and its marks -- None where it is no such word.
# (The a0.4.3 branch's own cases, and what the driving of 2026-10-02 found: a colour in the braces after the word is not a mark.)
SHAPES = (
    ("[[ab[cd]{teal}ef]]", ("abcdef", {})),
    ("[[[ab]{crimson}cd]]", ("abcd", {})),
    ("[[ab[cd]{crimson}]]", ("abcd", {})),
    ("[[ab[cd]{Teal}ef]]", ("abcdef", {})),
    ("[[ab[cd]{#C2185B}ef]]", ("abcdef", {})),
    ("[[ab[cd]{#C2185}ef]]", None),
    ("[[ab[cd]{red}ef]]", None),
    ("[[ab[cd]{red}[ef]{teal}]]", ("ab[cd]{red}ef", {})),
    ("[[slot]]", None),
    ("[[ab[cd]{teal}ef", None),
    ("[[ab[[cd]{teal}ef]]", None),
    ("[[ab[cd]{teal}\nef]]", None),
    ("[[ab[]{teal}ef]]", None),
    ("[[ک[ت]{crimson}[ا]{indigo}ب]]{translit:ketāb}", ("کتاب", {"translit": "ketāb"})),
    ("[[日[本]{indigo}語]]{kana:にほんご translit:nihongo}", ("日本語", {"kana": "にほんご", "translit": "nihongo"})),
    ("[[ab[cd]{teal}ef]]{reading:x}", ("abcdef", {"kana": "x"})),
    ("[[ab[cd]{teal}ef]]{teal}", ("abcdef", {})),
    ("[[ab[cd]{teal}ef]]{teal translit:x}", ("abcdef", {})),
    ("[[ab[cd]{teal}ef]] {translit:x}", ("abcdef", {})),
    ("[[ab[cd]{teal}ef]]{note}", ("abcdef", {})),
)


def _examples(code, ticked):
    """The words coloured in parts a studio prompt gives as examples, each span once: [(its code span, the word the grammar
    reads in it)] -- the code spans that hold a double bracket and a piece."""
    text = _instructions(code, ticked)
    spans = dict.fromkeys(s for s in re.findall(r"`([^`\n]+)`", text) if "[[" in s and "]{" in s)
    return [(span, w) for span in spans for w in coloured_words(span)]


class ColouredWords(ControlledMachine):
    """The box that teaches a word coloured in parts, the reserved list's line for it, and what the exercise prompt says of it:
    everything that is true of the prompts whatever the parser of the tree is.  What needs the a0.4.3 parser is
    ColouredWordsOfA043's."""

    def setUp(self):
        super().setUp()
        _INSTRUCTIONS.clear()

    def test_the_box_stands_beside_the_colours_and_no_preset_ticks_it_but_all(self):
        ids = list(promptboxes.BOX_IDS)
        self.assertEqual(ids.index("colourparts"), ids.index("colours") + 1)
        box, colours = promptboxes.BY_ID["colourparts"], promptboxes.BY_ID["colours"]
        self.assertEqual(box.group, colours.group)
        self.assertTrue(box.name and box.line)
        by = {p.id: set(p.boxes) for p in promptboxes.PRESETS}
        for name in ("short", "lesson", "vocabulary", "exercises", "none"):
            self.assertNotIn("colourparts", by[name], name)
        self.assertIn("colourparts", by["all"])

    def test_every_language_is_offered_it_in_both_prompts_and_its_size_is_measured(self):
        for code in languages.CODES:
            L = languages.get(code)
            for exercising in (False, True):
                row = next(r for r in promptboxes.catalog(L, (), exercising) if r["id"] == "colourparts")
                self.assertTrue(row["shown"], (code, exercising))
                self.assertTrue(900 < row["chars"] < 1900, (code, exercising, row["chars"]))
                self.assertEqual((row["name"], row["group"]), ("colour inside a word", "how it is laid out"))

    def test_the_box_teaches_the_spelling_the_colours_and_when_to_reach_for_it(self):
        for code in languages.CODES:
            text = _box_own(code, "colourparts")
            with self.subTest(language=code):
                self.assertTrue(text.startswith("**Colour inside a word.**"), text[:60])
                for words in ("how ONE word is built", "a stem against its ending", "double brackets", "single brackets",
                              "no space or joiner", "`crimson`, `indigo`, `teal`, `violet`, `amber`", "six-digit hex value",
                              "never another name", "on one line", "never put one such word inside another",
                              "closing `]]`", "never a colour", "`^[…]` note",
                              "**Most documents need none**", "as few colours as the idea needs",
                              "never explain the colours in the text"):
                    self.assertIn(words, text)
                for gone in ("section or subsection title", "`[…]{tl}` block"):
                    self.assertNotIn(gone, text, "the a0.4.3 dialect now takes a title and a block: not forbidden")

    def test_it_has_one_example_for_a_script_of_its_own_and_one_for_a_latin_script_target(self):
        for code, own, latin in (("fa", True, False), ("ar", True, False), ("it", False, True), ("en", False, True),
                                 ("fr", False, True), ("ja", False, False), ("zh", False, False), ("hi", False, False)):
            text = _box_own(code, "colourparts")
            with self.subTest(language=code):
                self.assertEqual("[[بر[گشت]{teal}[م]{crimson}]]" in text, own)
                self.assertEqual("[[un[break]{crimson}able]]" in text, latin)
                self.assertEqual("needs no `{tl}` mark" in text, latin, "a Latin-script target marks every run, and this is one")
                self.assertIn("`[[ab[cd]{teal}ef]]`", text, "the spelling every language is taught")

    def test_every_example_the_prompt_gives_is_spelled_as_the_grammar_says(self):
        for code in languages.CODES:
            for ticked in (("colourparts",), promptboxes.BOX_IDS):
                spells = _examples(code, ticked)
                self.assertTrue(spells, (code, ticked))
                for span, (start, end, flat, marks) in spells:
                    with self.subTest(language=code, example=span):
                        self.assertEqual((start, end), (0, len(span)), "the whole code span is the word and its marks")
                        self.assertEqual(flat, FLAT[span])
                        self.assertNotIn("crimson", " ".join(marks.values()), "a colour is never in the braces after the word")
        everything = {span for code in languages.CODES for span, _ in _examples(code, promptboxes.BOX_IDS)}
        self.assertEqual(everything, set(FLAT), "every spelling the prompts give is one this table knows, and each is given")

    def test_the_grammar_of_this_file_refuses_what_the_dialect_refuses(self):
        # it has teeth: each shape of SHAPES is read as the a0.4.3 branch's own tests and the driving of it say
        for source, want in SHAPES:
            with self.subTest(source=source):
                got = coloured_words(source)
                if want is None:
                    self.assertEqual(got, [], source)
                else:
                    self.assertEqual([(f, m) for _s, _e, f, m in got], [want], source)
        self.assertEqual(coloured_words("Fill the [[name]] and [[d]] here."), [], "a blank is no coloured word")
        self.assertEqual(len(coloured_words("[[ab[cd]{teal}ef]] then [[gh[ij]{indigo}]]")), 2)

    def test_a_double_bracket_word_with_a_coloured_piece_is_no_blank_and_the_reserved_list_says_so(self):
        for code in ("fa", "it", "ja"):
            self.assertIn("a double-bracket word with a coloured piece in it is no blank", _reserved(code, ()))
            # unticked, the feature is named by the reserved list; ticked, by its box
            self.assertIn("is one word coloured in parts", _reserved(code, ()))
            self.assertNotIn("is one word coloured in parts", _reserved(code, ("colourparts",)))
            self.assertIn("**Colour inside a word.**", _instructions(code, ("colourparts",)))

    def test_the_revise_rule_names_the_reader_s_coloured_words_and_no_longer_says_a_cloud_colours(self):
        # a0.4.3: a colour is set by selecting text in the source editor, the pointing cloud is for the pronunciation
        for code in ("fa", "it", "ja"):
            text = _box_own(code, "revise")
            self.assertIn("a colour on only part of a word, `[[ab[cd]{teal}ef]]`", text)
            self.assertNotIn("hovering", text)
            self.assertIn("keep everything else of it exactly as it is", text)

    def test_a_page_that_uses_one_is_found_and_has_its_box_ticked_in_the_exercise_prompt_by_the_scanner_the_tree_has(self):
        # the wiring, held in a tree with no a0.4.3 dialect: this file's grammar stands in for exlex/segcolour.py
        # (ColouredWordsOfA043 does the same with the real one)
        page = ("---\ntitle: T\ntarget: fa\n---\n\nThe word [[ک[ت]{crimson}[ا]{indigo}ب]]{translit:ketāb} and "
                "[آهسته]{crimson} here, and [[slot]].\n")
        with mock.patch.object(promptboxes, "segcolour", GrammarAsScanner):
            boxes, _types = promptboxes.page_uses(page)
            self.assertEqual(boxes, ["translit", "colours", "colourparts"])
            only = "---\ntitle: T\ntarget: fa\n---\n\nThe word [[ک[ت]{crimson}[ا]{indigo}ب]] here.\n"
            self.assertEqual(promptboxes.page_uses(only)[0], ["colourparts"], "its pieces are not a colour mark")
            for none in ("A [[slot]] here.", "A [آهسته]{crimson} here.", "A [[آهسته]] here."):
                self.assertNotIn("colourparts", promptboxes.page_uses("---\ntitle: T\ntarget: fa\n---\n\n%s\n" % none)[0], none)
            h = PathHandler(None, {"markdown": page, "decks": []})
            studio_server.api_exercise_prompt(h)
            self.assertEqual(h.answer["preticked"]["boxes"], ["translit", "colours", "colourparts"])
            self.assertIn("**Colour inside a word.**", h.answer["prompt"])
            self.assertIn("colourparts", [b["id"] for b in h.answer["boxes"] if b["on"]])
        # without a scanner nothing silly happens: the page is read as it always was, and the box is not found
        with mock.patch.object(promptboxes, "segcolour", None):
            self.assertNotIn("colourparts", promptboxes.page_uses(page)[0])

    def test_the_exercise_prompt_says_where_such_a_word_may_stand_only_when_its_box_is_ticked(self):
        page = "---\ntitle: T\ntarget: fa\n---\n\nLesson\n"

        def prompt(boxes, types):
            h = PathHandler(None, {"markdown": page, "decks": [], "boxes": boxes, "types": types})
            studio_server.api_exercise_prompt(h)
            return h.answer["prompt"]
        both = prompt(["colourparts"], ["fill-blanks", "single-choice"])
        self.assertIn("A word coloured in parts (`[[ab[cd]{teal}ef]]`) may go in a prompt, an answer row, a pair, a fill sentence or "
                      "a card's field.", both)
        self.assertIn("A blank is never inside a word coloured in parts", both)
        self.assertNotIn("A blank is never inside a word coloured in parts", prompt(["colourparts"], ["single-choice"]),
                         "no fill-blanks type, no sentence about its blanks")
        off = prompt([], ["fill-blanks", "single-choice"])
        self.assertNotIn("A word coloured in parts (`[[ab[cd]{teal}ef]]`) may go in", off)
        self.assertNotIn("**Colour inside a word.**", off)
        self.assertIn("is one word coloured in parts", off, "unticked, it is named in the reserved list")


@unittest.skipUnless(HAVE_A043, WAITS)
class ColouredWordsOfA043(ControlledMachine):
    """What needs the a0.4.3 parser (markdown/exlex/segcolour.py): the real scanner reads the prompt's examples as the grammar of
    this file does, the real parser reads the rows' samples, the real renderers take every example in every place the prompt lets
    such a word stand, and a page that uses one has its box ticked in the exercise prompt.  Skipped, saying so, in a tree
    without that dialect; on after the merge, with no edit."""

    # the a0.4.3 branch's own scanner cases (tests/test_segmented_colours.py), the authority the grammar of this file follows
    A043_CASES = ("[[a[b]{crimson}c]]", "[[[a]{crimson}bc]]", "[[ab[c]{crimson}]]", "[[a[b]{crimson}[c]{indigo}d]]",
                  "[[[ab]{crimson}[cd]{indigo}]]", "[[a[bc]{#C2185B}d]]", "[[ک[ت]{crimson}[ا]{indigo}ب]]{translit:ketāb}",
                  "[[日[本]{indigo}語]]{kana:にほんご translit:nihongo}", "[[ordinary brackets]]", "[[slot]]", "[[کتاب",
                  "[[ک[ت]{crimson}", "[[ک[ت]{red}اب]]", "[[x[[a]{teal}b]]", "[[x[y]{red}z[q]{teal}]]")

    def setUp(self):
        super().setUp()
        _INSTRUCTIONS.clear()
        self.segcolour = importlib.import_module("segcolour")
        self.texgen = importlib.import_module("texgen")

    def real(self, text):
        return [(n.start, n.end, n.plain_text, dict(n.marks)) for n in self.segcolour.find_runs(text)]

    def test_the_real_scanner_reads_the_prompt_s_examples_and_a_corpus_as_the_grammar_of_this_file_does(self):
        corpus = list(self.A043_CASES) + [source for source, _want in SHAPES]
        given = [span for code in languages.CODES for span, _ in _examples(code, promptboxes.BOX_IDS)]
        self.assertTrue(given, "the prompts give examples of it")
        corpus += given
        corpus += ["A [[ab[cd]{teal}ef]] then [[gh[ij]{indigo}]]{translit:x} and [[slot]].", "[[[a]{teal}[b]{teal}c]]"]
        for source in corpus:
            with self.subTest(source=source):
                self.assertEqual(self.real(source), coloured_words(source))
                self.assertEqual(self.segcolour.flatten(source), GrammarAsScanner.flatten(source))

    def test_the_real_parser_reads_each_row_of_the_a0_4_3_dialect_as_the_row_says(self):
        for r in RESERVED_A043:
            with self.subTest(construct=r.id):
                self.assertEqual(_mismatch(r), [])

    def test_the_comparison_refuses_a_wrong_expectation_of_these_rows(self):
        # the driver has teeth for them: a paragraph is not a list, and the pieces are no whole-word colour marks (what a
        # parser without the dialect makes of them, which is the one thing these rows must not be satisfied by)
        row = next(r for r in RESERVED_A043 if r.id == "mark-coloured-word")
        self.assertEqual(_mismatch(row), [])
        self.assertTrue(_mismatch(row._replace(blocks=["list"])))
        self.assertTrue(_mismatch(row._replace(page=('class="fac fac-crimson" data-color="crimson"',))))
        self.assertTrue(_mismatch(row._replace(page=('data-fa="کت"',))), "the word is one, and whole")

    def test_the_real_renderers_take_every_example_in_every_place_the_prompt_names(self):
        places = (("a sentence", "Some words {W} in a sentence."), ("a list", "- an item with {W}"),
                  ("a table", "| a | b |\n|---|---|\n| {W} | x |"), ("a box", "> a caution about {W}"),
                  ("a gloss", "{W} = *meaning*"), ("a headword", "## {W} | translit | origin | = *meaning*"),
                  ("a title", "## A title with {W}"),
                  ("an exercise prompt", ":::exercise single-choice\nprompt: Pick {W} now.\n- [x] a\n- [ ] b\n:::"))
        for code in languages.CODES:
            L = languages.get(code)
            spells = _examples(code, promptboxes.BOX_IDS)
            self.assertTrue(spells, "%s is given examples of it" % code)
            for span, (_s, _e, flat, marks) in spells:
                for place, template in places:
                    if place == "a headword" and L.re_chars and not L.re_chars.match(flat[0]):
                        continue            # a vocabulary entry's first field is in the script of an own-script target
                    with self.subTest(language=code, example=span, place=place):
                        md = "---\ntitle: T\nlang: en\ntarget: %s\n---\n\n%s\n" % (code, template.replace("{W}", span))
                        page = htmlgen.render_document(md, colophon=False)["html"]
                        self.assertEqual(page.count('segmented-colour-run'), 1, "one word on the page")
                        self.assertIn('data-fa="%s"' % flat, page)
                        visible = re.sub(r"<[^>]+>", "", page)
                        self.assertNotIn("[[", visible)
                        self.assertNotIn("]]", visible)
                        for key, value in marks.items():
                            if place not in ("a headword", "a title", "an exercise prompt"):
                                self.assertIn('data-%s="%s"' % (key, value), page)
                        tex = self.texgen.generate(*mdparser.parse(md), colophon=False)
                        self.assertEqual(tex.count("\\segword{"), 1, "and one on paper")
                        self.assertIn("\\segword{%s}" % flat, tex)

    def test_a_page_that_uses_one_has_its_box_ticked_in_the_exercise_prompt_by_the_real_scanner(self):
        for place, body in (("a sentence", "A word [[ک[ت]{crimson}[ا]{indigo}ب]] here."),
                            ("a list", "- a word [[ک[ت]{crimson}[ا]{indigo}ب]] here"),
                            ("a table", "| a | b |\n|---|---|\n| [[ک[ت]{crimson}[ا]{indigo}ب]] | x |"),
                            ("a box", "> a word [[ک[ت]{crimson}[ا]{indigo}ب]] here"),
                            ("a headword", "## [[ک[ت]{crimson}[ا]{indigo}ب]] | ketāb | from Arabic | = *book*"),
                            ("an answer row", ":::exercise single-choice\nprompt: Pick.\n- [x] [[ک[ت]{crimson}[ا]{indigo}ب]]\n- [ ] b\n:::")):
            with self.subTest(place=place):
                page = "---\ntitle: T\ntarget: fa\n---\n\n%s\n" % body
                self.assertIn("colourparts", promptboxes.page_uses(page)[0])
                h = PathHandler(None, {"markdown": page, "decks": []})
                studio_server.api_exercise_prompt(h)
                self.assertIn("colourparts", h.answer["preticked"]["boxes"])
                self.assertIn("**Colour inside a word.**", h.answer["prompt"])
        latin = "---\ntitle: T\ntarget: it\n---\n\nA word [[disfa[re]{crimson}]] here.\n"
        self.assertEqual(promptboxes.page_uses(latin)[0], ["colourparts"], "a Latin-script target needs no {tl} for it")

    def test_a_page_with_only_whole_word_colours_or_a_blank_does_not_tick_it(self):
        for body in ("A [آهسته]{crimson} here.", "A [[slot]] here.", "A [[آهسته]] here.", "A [ت]{crimson} here."):
            with self.subTest(body=body):
                found = promptboxes.page_uses("---\ntitle: T\ntarget: fa\n---\n\n%s\n" % body)[0]
                self.assertNotIn("colourparts", found)
        self.assertEqual(promptboxes.page_uses("---\ntitle: T\ntarget: fa\n---\n\nA [[ک[ت]{crimson}ا]]b.\n")[0].count("colours"), 0)


class AddedScriptLanguage(ControlledMachine):
    """Korean, added the way a person adds a language with a script of its own (`--script other --chars`): no row
    for its script in the studio's table of marks, no alternate face, no reading.  Every prompt of the studio
    has to be made for it, in words that are true of it and of no other language."""

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.mkdtemp(prefix="promptkit-ko-")
        cls.addClassCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shipped = os.path.join(tmp, "lib", "languages.json")
        personal = os.path.join(tmp, "config", "languages.json")
        lang_docs = os.path.join(tmp, "docs", "lang")
        os.makedirs(os.path.dirname(shipped))
        shutil.copy(os.path.join(ROOT, "lib", "languages.json"), shipped)
        shutil.copytree(os.path.join(ROOT, "lib", "lang"), os.path.join(tmp, "lib", "lang"))
        shutil.copytree(os.path.join(ROOT, "docs", "lang"), lang_docs)
        patches = [mock.patch.object(newlang, n, v) for n, v in (
            ("REGISTRY", shipped), ("PERSONAL", personal), ("LANG_TEX", os.path.join(tmp, "lib", "lang")),
            ("LANG_DOCS", lang_docs), ("ROOT", tmp), ("STUDIO", os.path.join(tmp, "markdown")))]
        for p in patches:
            p.start()
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = newlang.main(["ko", "--name", "Korean", "--native", "한국어", "--script", "other",
                                   "--chars", "가-힣ᄀ-ᇿ"])
        finally:
            for p in patches:
                p.stop()
        assert rc == 0, "newlang could not add the language: %s" % out.getvalue()[-400:]
        langs, problems = languages._load(shipped, personal)
        assert "ko" in langs and not problems, problems
        for p in [mock.patch.dict(languages.LANGS, {"ko": langs["ko"]}),
                  mock.patch.dict(languages.FOLDERS, {langs["ko"].folder: "ko"}),
                  mock.patch.object(K, "LANG_DOCS", lang_docs)] + machine_patches():
            p.start()
            cls.addClassCleanup(p.stop)

    def test_every_preset_and_the_exercise_prompt_are_made_for_it_in_words_that_are_true_of_it(self):
        L = languages.get("ko")
        self.assertEqual((L.script, bool(L.chars), L.reading, L.rtl, L.vertical), ("other", True, False, False, False))
        self.assertEqual(promptboxes.shown_ids(L), set(promptboxes.BOX_IDS) - {"reading", "rtl"},
                         "its own script gives it the punctuation box; it has no reading and is not right to left")
        for p in promptboxes.PRESETS:
            a = studio_server.studio_prompt(L, boxes=list(p.boxes))
            self.assertNotIn("{{", a.text, p.id)
            self.assertIn("this document is about Korean", a.text)
            for persian in ("Arabic comma", "zero-width non-joiner", "نستعلیق", "{tl font="):
                self.assertNotIn(persian, a.text, "%s is not true of Korean (%s)" % (persian, p.id))
        everything = studio_server.studio_prompt(L, boxes=list(promptboxes.BOX_IDS)).text
        self.assertIn("The target language's own punctuation — the marks its script has of its own —", everything)
        self.assertIn("the first line of the passage", everything, "a passage is shown with words of no language")
        self.assertIn("**Text in the target language.** Write it inline as plain Unicode", everything,
                      "its runs are found by their script, not marked")
        page, _rows = studio_server.exercise_prompt("---\ntitle: T\ntarget: ko\n---\n\nLesson")
        self.assertNotIn("{{", page.text)
        self.assertNotIn("Mixed-direction", page.text)


class AnswerShapes(unittest.TestCase):
    """Paste LLM answer takes the document out of whatever a chatbot answered (brief 7.5): the studio's contract
    asks for a file, and where the chatbot cannot make one for the whole document in ONE fenced block opened
    with four backticks and the word `markdown`.  Each shape, driven through the route's own reading of it."""
    DOC = "---\ntitle: Slow\nlang: en\ntarget: fa\n---\n\n## A section\n\nSome prose about آهسته = *slowly*.\n\n- one\n- two\n"
    T3, T4 = "`" * 3, "`" * 4

    def shapes(self):
        d, t3, t4 = self.DOC, self.T3, self.T4
        return [("a file's text", d),
                ("a fence of four backticks", "%smarkdown\n%s%s\n" % (t4, d, t4)),
                ("a fence of three backticks", "%smarkdown\n%s%s\n" % (t3, d, t3)),
                ("a fence of three with no word after it", "%s\n%s%s\n" % (t3, d, t3)),
                ("a fence with chatter round it", "Sure! Here is your document:\n\n%smarkdown\n%s%s\n\nTell me if you want changes." % (t4, d, t4)),
                ("a fence of three with chatter round it", "Here it is.\n\n%smd\n%s%s\n\nHope that helps." % (t3, d, t3)),
                ("a fence written with Windows line ends", ("%smarkdown\n%s%s\n" % (t4, d, t4)).replace("\n", "\r\n")),
                ("a fence a chat window indented", "  %smarkdown\n%s  %s\n" % (t4, d, t4))]

    def test_every_shape_gives_the_document_and_nothing_else(self):
        for label, text in self.shapes():
            with self.subTest(shape=label):
                self.assertEqual(studio_server.store.extract_markdown(text), self.DOC)

    def test_a_fence_of_four_holds_a_fence_of_three_whole(self):
        # what the contract asks for, and a document that holds a fence of its own (the dialect does not read it,
        # a model may write one): the three backticks are not the end of the four
        doc = self.DOC + "\n%s\ncode\n%s\n\nafter the fence\n" % (self.T3, self.T3)
        got = studio_server.store.extract_markdown("Here:\n\n%smarkdown\n%s%s\n\nDone." % (self.T4, doc, self.T4))
        self.assertEqual(got, doc)
        self.assertIn("after the fence", got)

    def test_an_answer_with_no_fence_is_taken_as_it_stands_which_is_why_the_fence_is_asked_for(self):
        got = studio_server.store.extract_markdown("Sure! Here is your document:\n\n" + self.DOC + "\nTell me more.")
        self.assertTrue(got.startswith("Sure!"))
        self.assertTrue(got.rstrip().endswith("Tell me more."))

    def test_the_contract_asks_for_the_shape_the_route_takes(self):
        contract = studio_server.studio_prompt(languages.get("fa")).contract
        self.assertIn("creating a markdown file", contract)
        self.assertIn("four backticks", contract)
        self.assertIn("`markdown`", contract)
        self.assertNotIn("not a fenced code block", contract, "the old contract's contradiction with the exercise prompt")
        self.assertEqual(studio_server.store.extract_markdown("%smarkdown\n%s%s" % (self.T4, self.DOC, self.T4)), self.DOC)

    def test_pasting_each_shape_makes_the_document_in_the_library(self):
        # the route Paste LLM answer posts to, on a temporary library
        with tempfile.TemporaryDirectory() as td:
            was = studio_server.store.use_library(td)
            try:
                for i, (label, text) in enumerate(self.shapes()):
                    h = Handler({"markdown": text.replace("title: Slow", "title: Slow %d" % i)})
                    with mock.patch.object(studio_server, "_adopt"), \
                            mock.patch.object(studio_server.latexdraw, "own_source"):
                        studio_server.api_create(h)
                    made = h.answer["meta"]
                    self.assertEqual(made["title"], "Slow %d" % i, label)
                    _meta, stored = studio_server.store.get(made["id"])
                    self.assertEqual(stored, self.DOC.replace("title: Slow", "title: Slow %d" % i), label)
            finally:
                studio_server.store.use_library(was)


# --- the content of the options (brief 3.9, 3.10) ------------------------------------------------------------------
# The MECHANISM of the two options is tests/test_prompt_options.py's; what a language file SAYS under each value is
# held here, and by tests/test_language_examples.py and tests/test_example_per_scheme.py (the Examples).
#
# THE USUAL SCHEME'S OWN WORDS, by language: one phrase of the Transliteration section as it stands today that only the
# usual scheme says, so that an IPA prompt which still carries it still describes the scheme it was asked to leave.
# English's usual scheme already is IPA and Chinese is offered no IPA setting (the registry's `ipa`): neither has one.
USUAL_SCHEME_SAYS = {
    "fa": "**š** = ش", "ar": "never `kh`", "hi": "**ष is ś, like श.**", "ja": "**Hepburn rōmaji**",
    "it": "IPA-lite pronunciation aid", "es": "IPA-lite pronunciation aid",
    "fr": "The scheme is a respelling, not IPA", "de": "**pronunciation line, given only where the spelling misleads**",
    "tr": "**Never respell the alphabet.**",
}
TAKE_THE_FILE = ("studio-doc", "studio-exercises", "video-region", "book-region", "video-new", "book-new")


class TheContentOfTheOptions(ControlledMachine):
    def ipa_languages(self):
        return [c for c in languages.CODES if languages.get(c).ipa == "offered"]

    def test_each_phrase_of_the_usual_scheme_is_in_the_usual_prompt_it_stands_for(self):
        # so the list above cannot rot: a file whose usual scheme is reworded names a phrase that is gone
        self.assertEqual(sorted(USUAL_SCHEME_SAYS), sorted(c for c in self.ipa_languages() if c not in ("zh",)))
        for code, phrase in USUAL_SCHEME_SAYS.items():
            for surface in TAKE_THE_FILE:
                self.assertIn(phrase, K.language_text(surface, code), (code, surface))

    def usual_rules_in_ipa(self):
        failures, total = [], 0
        for code, phrase in USUAL_SCHEME_SAYS.items():
            for surface in TAKE_THE_FILE:
                total += 1
                if phrase in K.language_text(surface, code, options={"translit": "ipa"}):
                    failures.append("%s %s still says %r" % (surface, code, phrase))
        return failures, total

    def test_the_ipa_prompt_carries_no_rule_of_the_usual_scheme(self):
        failures, total = self.usual_rules_in_ipa()
        self.assertEqual(failures, [], "an IPA prompt describes no rule of the usual scheme (brief 3.9)")

    def files_without_an_ipa_note(self):
        missing = []
        for code in self.ipa_languages():
            text = _file(code)
            for flag in ("ipa", "classic"):
                if "{{?%s}}" % flag not in text:
                    missing.append("docs/lang/%s.md has no {{?%s}} block" % (code, flag))
        template = _file("_template")
        for flag in ("ipa", "classic"):
            if "{{?%s}}" % flag not in template:
                missing.append("docs/lang/_template.md has no {{?%s}} block: a language added later would start without it" % flag)
        return missing

    def test_every_language_file_and_the_template_carry_the_ipa_note_and_the_usual_text(self):
        # every language file says IPA in a block of its own beside the usual scheme
        self.assertEqual(self.files_without_an_ipa_note(), [])

    def files_without_the_marks_paragraphs(self):
        return ["docs/lang/%s.md has no {{?%s}} block" % (c, flag)
                for c in languages.CODES if languages.get(c).strip_range
                for flag in ("marks", "nomarks") if "{{?%s}}" % flag not in _file(c)]

    def test_the_harakat_paragraphs_of_persian_and_arabic_carry_the_marks_flags(self):
        # the harakat paragraphs are marked by the option and not by the surface (brief 3.10)
        self.assertEqual(self.files_without_the_marks_paragraphs(), [])

    def test_a_language_with_no_short_vowels_has_no_marks_block_in_its_file(self):
        # a language WITHOUT `strip` never gets the option: no block of its file is for it
        for code in languages.CODES:
            if not languages.get(code).strip_range:
                for flag in ("marks", "nomarks"):
                    self.assertNotIn("{{?%s}}" % flag, _file(code), code)


# --- the answer contract of the short vowels (brief 3.10, lane M) -------------------------------------------------
# The contract is the TEMPLATES' (docs/region-prompt.md, youtube/docs/chat-prompt.md): in the state "write them" a
# prompt says that `fa` may come back with its short vowels added, in the chunks marked todo, and nothing else
# changed; in the other state it says what it always said, byte for byte.  How to vowel is the language file's (lane
# D2), and the applier that holds an answer to this contract is lib/glossregion.py (tests/test_glossregion.py).
class TheContractOfTheShortVowels(ControlledMachine):
    REGION = ("The one exception is the short vowels", "with its short vowels added and nothing else changed",
              "for the short vowels put in", "short vowels in its `fa`")
    NEW = ("The one addition this prompt asks for is the short vowels", "the short vowels put in, and nothing else changed")

    def cases(self, codes):
        return [(surface, code, mode, self.REGION if surface in REGIONS else self.NEW)
                for code in codes for surface in ("video-region", "book-region", "video-new")
                for mode in ((None, "perfield", "regloss") if surface in REGIONS else (None,))]

    def test_a_prompt_that_asks_for_the_short_vowels_says_what_fa_may_then_be(self):
        for surface, code, mode, says in self.cases(("fa", "ar")):
            with self.subTest(surface=surface, language=code, mode=mode):
                a = promptlab.build(surface, code, mode, None, {"marks": "1"})
                flat = _flat(a.text)
                self.assertTrue(a.header.endswith(" · marks"), a.header)
                self.assertNotIn("{{", a.text)
                for phrase in says:
                    self.assertIn(phrase, flat)
                if surface in REGIONS:
                    # the contract names the chunks it is about, and keeps the rule that fa is a person's
                    self.assertIn("Never change `fa`", flat)
                    self.assertIn("every chunk not marked `\"todo\": true`, comes back with its `fa` exactly as received", flat)

    def test_a_prompt_that_leaves_the_text_as_it_is_is_the_prompt_it_always_was(self):
        for surface, code, mode, says in self.cases(("fa", "ar")):
            with self.subTest(surface=surface, language=code, mode=mode):
                a = promptlab.build(surface, code, mode, None, {"marks": "0"})
                self.assertEqual(a.text, promptlab.build(surface, code, mode).text, "the default is `no marks`")
                for phrase in says:
                    self.assertNotIn(phrase, _flat(a.text))

    def test_a_language_with_no_short_vowels_is_asked_for_none_and_told_nothing_of_them(self):
        for surface, code, mode, says in self.cases(("it", "ja", "zh", "en")):
            with self.subTest(surface=surface, language=code, mode=mode):
                a = promptlab.build(surface, code, mode, None, {"marks": "1"})
                self.assertEqual(a.text, promptlab.build(surface, code, mode).text)
                self.assertNotIn("short vowel", _flat(a.text), (surface, code))


if __name__ == "__main__":
    unittest.main()
