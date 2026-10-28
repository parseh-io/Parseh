# SPDX-License-Identifier: GPL-3.0-or-later
"""LaTeX drawings in what a chatbot is taught (a0.5.5): the themes, and a drawing in an exercise or in a step of a follow-up.

    python3 -m unittest tests/test_latex_in_prompts.py

  * A THEME IS SAID BY WHAT ITS PACKAGES ARE FOR, the ones it ticks and the ones its own lines load, so that a model
    can match a drawing's commands to the theme that has them (a theme called `chess` that loads xskak was said to add
    nothing at all);
  * THE PROMPT TEACHES TO CHOOSE THE THEME by what the drawing needs, and the skill says the same words: the exercises'
    prompt says where a drawing may stand in an exercise and how a step of a follow-up writes one (five colons), only
    when the LaTeX box is ticked -- and what it shows is the dialect: the example is parsed by the real parser;
  * A PAGE THAT ALREADY HOLDS A DRAWING IN AN EXERCISE, OR IN A STEP, has the box ticked: the scan reads the steps.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
import unittest.mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("lib", "markdown/app", "markdown/exlex", "markdown", "youtube/lib"):
    sys.path.insert(0, os.path.join(ROOT, _p))
import languages        # noqa: E402
import latexthemes      # noqa: E402
import mdparser         # noqa: E402
import promptboxes      # noqa: E402
import promptkit        # noqa: E402
import skills           # noqa: E402
import server as studio     # noqa: E402

PAGE = "---\ntitle: T\ntarget: %s\n---\n\nLesson\n"
CHESS = {"name": "chess", "compiler": "xelatex", "packages": [], "languages": False, "font": "",
         "preamble": "\\usepackage{xskak}\n\\usepackage{wrapfig}"}


class WithThemes(unittest.TestCase):
    """A store of themes of its own: the three a fresh Parseh has, and `chess`"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="latex-prompts-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.was = latexthemes.STORE
        latexthemes.STORE = os.path.join(self.tmp, "latex.json")
        self.addCleanup(setattr, latexthemes, "STORE", self.was)
        latexthemes.save(dict(CHESS))

    def exercise_text(self, boxes, types, lang="it", markdown=None):
        a, _rows = studio.exercise_prompt(markdown or PAGE % lang, (), boxes=boxes, types=types)
        return a.text


class ThemesAreSaidByWhatTheyAreFor(WithThemes):
    def test_each_package_a_theme_adds_says_what_it_is_for(self):
        said = promptboxes.latex_themes()
        self.assertIn("`chemistry` (adds mhchem — chemical formulas and reactions; chemfig — structures of molecules)", said)
        self.assertIn("`drawing` (adds tikz — drawing; pgfplots — plots and surfaces, inside an axis)", said)
        self.assertTrue(said.startswith("`default`, "), "the default adds nothing to itself")

    def test_a_package_the_themes_own_lines_load_counts_as_one_it_adds(self):
        said = promptboxes.latex_themes()
        self.assertIn("`chess` (adds xskak — chess: the moves of a game in figurine notation, and the board after them; wrapfig)", said)
        self.assertEqual(["wrapfig"], latexthemes.other_packages(latexthemes.find("chess")))

    def test_a_theme_that_sets_words_in_the_languages_parseh_teaches_says_so(self):
        latexthemes.save(dict(CHESS, name="words", preamble="", languages=True))
        self.assertIn("`words` (sets words in the languages Parseh teaches)", promptboxes.latex_themes())

    def test_a_store_that_cannot_be_read_leaves_the_rule_standing(self):
        with unittest.mock.patch.object(latexthemes, "themes", side_effect=OSError("no store")):
            self.assertEqual("`default`", promptboxes.latex_themes())


class ThePromptsTeachThemesAndDrawingsInExercises(WithThemes):
    def test_the_document_prompt_teaches_to_choose_the_theme_by_the_commands_the_drawing_needs(self):
        a = studio.studio_prompt(languages.get("it"), boxes=["latex"])
        flat = " ".join(a.text.split())
        self.assertIn("**Choose the theme by what the drawing needs.**", flat)
        self.assertIn("`\\chessboard` xskak's", flat)
        self.assertIn("Write no `\\usepackage` in the body", flat)
        self.assertIn("`chess` (adds xskak", flat, "the person's own theme is in the list, with what it adds")

    def test_the_exercise_prompt_says_where_a_drawing_may_stand_only_when_its_box_is_ticked(self):
        on = " ".join(self.exercise_text(["latex"], ["single-choice"]).split())
        self.assertIn("A LaTeX drawing may go in an exercise too", on)
        self.assertIn("as a block in a prompt written `prompt: |` with the block's lines indented under it", on)
        off = " ".join(self.exercise_text([], ["single-choice"]).split())
        self.assertNotIn("A LaTeX drawing may go in an exercise too", off)

    def test_a_follow_up_is_told_the_steps_drawing_takes_five_colons_when_the_box_is_ticked(self):
        on = self.exercise_text(["latex"], ["follow-up", "single-choice"])
        self.assertIn("A LaTeX drawing in a step is written one colon deeper too", on)
        self.assertIn("(**five** colons)", on)
        self.assertIn(":::::latex chemistry {width=40}", on)
        off = self.exercise_text([], ["follow-up", "single-choice"])
        self.assertNotIn("A LaTeX drawing in a step", off)
        self.assertNotIn(":::::latex", off)
        none = self.exercise_text(["latex"], ["single-choice"])
        self.assertNotIn("A LaTeX drawing in a step", none, "no follow-up asked for, nothing about its steps")

    def test_the_example_of_a_step_with_a_drawing_is_the_dialect(self):
        # the prompt's example, as a chatbot copies it, is read by the real parser: two steps, no mistake, the drawing in the first
        text = self.exercise_text(["latex"], ["follow-up"])
        example = text[text.index("::::exercise single-choice\nprompt: |"):]
        example = example[:example.index("\n```")]
        md = ("---\ntitle: T\ntarget: it\n---\n\n:::exercise follow-up\nprompt: Look.\n" + example + "\n"
              "::::exercise true-false\n- yes => true\n::::\n:::\n")
        chain = mdparser.parse(md)[1][0]
        self.assertEqual(([], [[], []]), (chain["errors"], [s["errors"] for s in chain["steps"]]))
        self.assertIn("::::latex chemistry {width=40}\n  \\ce{2H2 + O2 -> 2H2O}\n  ::::", chain["steps"][0]["source"])

    def test_the_skill_says_the_same_in_the_files_a_model_reads(self):
        sk = skills.build("parseh-markdown")
        files = {k: (v.decode("utf-8") if isinstance(v, bytes) else v) for k, v in dict(sk.files).items()}
        latex = files["references/features/latex.md"]
        self.assertIn("**Choose the theme by what the drawing needs.**", latex)
        self.assertIn(promptboxes.latex_themes(), latex)
        self.assertIn("`chess` (adds xskak", latex)
        self.assertIn("⟦if feature latex⟧A LaTeX drawing in a step", files["references/exercises/follow-up.md"])
        self.assertIn("⟦if feature latex⟧ A LaTeX drawing may go in an exercise too", files["references/features/exercises.md"])
        # and what the skill tells a model to read for a request is what the prompt road makes of it
        L = languages.get("it")
        boxes, types = ["latex"], ["follow-up", "single-choice"]
        a, _rows = studio.exercise_prompt(PAGE % "it", (), boxes=boxes, types=types)
        named = skills._named(L, a.boxes, True)
        fields = [("features", ", ".join(named) or "none"), ("types", ", ".join(a.types)), ("level", "not said"),
                  ("length", "not said")]
        got = skills.read_markdown(sk.files, skills.render_header(
            "parseh-markdown", "a0.5.5", sk.hash, skills.WHAT["studio-exercises"], "it", fields=fields))
        self.assertIn("A LaTeX drawing in a step is written one colon deeper too", got["dialect"] + got["instructions"])
        self.assertIn("`chess` (adds xskak", got["dialect"] + got["instructions"])

    def test_a_theme_made_after_the_skill_was_built_makes_the_skill_out_of_date(self):
        before = skills.build("parseh-markdown").hash
        latexthemes.save(dict(CHESS, name="boards", preamble="\\usepackage{xskak}"))
        self.assertNotEqual(before, skills.build("parseh-markdown").hash)


class APageThatHoldsADrawingInAnExercise(WithThemes):
    STEP = ("---\ntitle: T\ntarget: it\n---\n\n:::exercise follow-up\nprompt: Look.\n::::exercise single-choice\n%s"
            "- [x] a\n- [ ] b\n::::\n::::exercise true-false\n- yes => true\n::::\n:::\n")

    def uses(self, markdown):
        return promptboxes.page_uses(markdown)

    def test_a_drawing_in_the_prompt_of_a_step_has_the_latex_box_ticked(self):
        md = self.STEP % "prompt: |\n  Which?\n  :::::latex\n  \\ce{H2O}\n  :::::\n"
        boxes, types = self.uses(md)
        self.assertIn("latex", boxes)
        # (a true/false step is the catalogue's yes-no): the steps' types are the page's, and not only "follow-up"
        self.assertEqual({"follow-up", "single-choice", "yes-no"}, set(types), "and the types of the steps are the page's")

    def test_the_same_drawing_written_with_four_colons_is_found_too(self):
        md = self.STEP % "prompt: |\n  Which?\n  ::::latex\n  \\ce{H2O}\n  ::::\n"
        self.assertIn("latex", self.uses(md)[0])

    def test_a_drawing_in_the_prompt_of_an_exercise_on_its_own_is_found(self):
        md = PAGE % "it" + "\n:::exercise single-choice\nprompt: |\n  Which?\n  ::::latex\n  \\ce{H2O}\n  ::::\n- [x] a\n- [ ] b\n:::\n"
        self.assertIn("latex", self.uses(md)[0])

    def test_a_line_mark_in_a_step_is_found(self):
        md = self.STEP % "prompt: Which [\\ce{H2O}]{latex}?\n"
        self.assertIn("latex", self.uses(md)[0])

    def test_a_follow_up_with_no_drawing_leaves_the_box_unticked(self):
        md = self.STEP % "prompt: Which?\n"
        self.assertNotIn("latex", self.uses(md)[0])

    def test_the_exercise_prompt_for_such_a_page_has_the_box_ticked_and_teaches_the_five_colons(self):
        md = self.STEP % "prompt: |\n  Which?\n  :::::latex\n  \\ce{H2O}\n  :::::\n"
        a, _rows = studio.exercise_prompt(md, ())
        self.assertIn("latex", a.boxes)
        self.assertIn("A LaTeX drawing in a step is written one colon deeper too", a.text)


if __name__ == "__main__":
    unittest.main()
