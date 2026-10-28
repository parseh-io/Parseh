# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
import re
import sys
import tempfile
import unittest
import urllib.parse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib"):
    sys.path.insert(0, str(folder))

import htmlgen
import mdparser
import notes
import server as studio_server
import store
import texgen


SAMPLES = {
    "fill-blanks": "text: [من]{tl} [[a]].\n- [a] [رفتم]{tl}\n- [ ] [آمدم]{tl}",
    "flashcard": "card-type: jolly\nfront-primary: [سلام]{tl}\nfront-secondary: salâm\nback-primary: hello\nback-secondary: greeting",
    "order-sentences": "- [1] one\n- [2] two",
    "match-translations": "- [سلام]{tl} => hello\n- [خداحافظ]{tl} => goodbye",
    "match-opposites": "- hot => cold",
    "match-definitions": "- cat => an animal",
    "yes-no": "- Is it so? => yes",
    "true-false": "- This is false. => false",
    "single-choice": "- [ ] no\n- [x] yes",
    "construct-sentence": "- [1] one\n- [2] two",
    "incorrect-part": "- [ ] okay\n- [x] error",
    "choose-all": "- [x] a\n- [ ] b\n- [x] c",
    "odd-one-out": "- [ ] a\n- [x] b",
}


def document(types=SAMPLES):
    blocks = []
    for subtype, body in types.items():
        blocks.append(":::exercise %s\nprompt: Test **prompt**.\n%s\n"
                      "explanation-correct: Because [this]{tl}.\n:::" % (subtype, body))
    return "---\ntitle: Exercises\ntarget: fa\n---\n\n" + "\n\n".join(blocks)


class ExerciseDialectTests(unittest.TestCase):
    def test_prompt_no_bold_preserves_nested_target_mark_in_reader_and_pdf(self):
        passage = ("[دیروز دو شنبه بود. امروز سه شنبه است.⏎"
                   "در ایران، پنج شنبه و جمعه مدرسه تعطیل است.⏎"
                   "در اروپا و آمریکا، شنبه و یک شنبه مدرسه تعطیل است.]{tl}")
        md = ("---\ntitle: Prompt test\ntarget: fa\n---\n"
              ":::exercise true-false\nprompt: |\n"
              "  Decide whether each statement is True or False.\n"
              "  [%s]{no-bold}\n- [فردا چهار شنبه است.]{tl} => true\n:::" % passage)
        block = mdparser.parse(md)[1][-1]
        self.assertEqual([], block["errors"])
        self.assertIn("[%s]{no-bold}" % passage, block["fields"]["prompt"])
        html = htmlgen.render_document(md)["html"]
        shown = re.search(r'<div class="ex-prompt">(.*?)</div>', html, re.S).group(1)
        self.assertIn('<span class="ex-field-line">Decide whether each statement is True or False.', shown)
        self.assertIn('<span class="ex-target-block" dir="rtl" lang="fa">', shown)
        self.assertIn('<span class="ex-no-bold"><span class="fa', shown)
        self.assertEqual(2, shown.count('<br>'))
        self.assertNotIn("{no-bold}", shown)
        paper = texgen.generate(*mdparser.parse(md), colophon=False)
        self.assertIn(r"\textbf{Decide whether each statement is True or False.}", paper)
        self.assertRegex(paper, re.compile(r"\\raggedleft\\noindent .*?\\mdseries .*?\\beginR .*?"
                                           r"\\newline .*?\\newline .*?\\endR.*?\\par", re.S))
        self.assertNotIn("{no-bold}", paper)

        # The right edge of an unwrapped target passage also needs the same
        # PDF paragraph alignment; the wrapper changes only its weight.
        unwrapped = md.replace("[%s]{no-bold}" % passage, passage)
        unwrapped_pdf = texgen.generate(*mdparser.parse(unwrapped), colophon=False)
        self.assertIn(r"\raggedleft\noindent", unwrapped_pdf)
        self.assertNotIn(r"\mdseries", unwrapped_pdf)

        inline_prompt = md.replace(
            "  [%s]{no-bold}" % passage,
            "  Select [this phrase]{no-bold} and [that phrase]{no-bold}.")
        inline_html = htmlgen.render_document(inline_prompt)["html"]
        self.assertIn('<span class="ex-no-bold">this phrase</span>', inline_html)
        self.assertIn('<span class="ex-no-bold">that phrase</span>', inline_html)
        inline_pdf = texgen.generate(*mdparser.parse(inline_prompt), colophon=False)
        self.assertIn(r"{\mdseries this phrase}", inline_pdf)
        self.assertIn(r"{\mdseries that phrase}", inline_pdf)

    def test_pictures_inside_exercise_cells_render_in_reader_preview_and_print(self):
        pictures = [("snow-1.jpg", "برف"), ("warm-1.jpg", "گرم"),
                    ("leaf-2.jpg", "برگ"), ("cold.jpg", "سرد"),
                    ("celebration2-2.jpg", "جشن"), ("winter-2-1.jpg", "زمستان"),
                    ("moon-1.jpg", "ماه"), ("tree-3-scaled.jpg", "درخت"),
                    ("weather-1-scaled.jpg", "هوا"), ("rain-1.jpg", "باران")]
        rows = "\n".join("- ![%s](images/%s) => [%s]{tl}" % (name, name, label)
                         for name, label in pictures)
        md = document({
            "match-translations": rows,
            "match-definitions": "- word => ![definition](images/definition.png)",
            "true-false": "- ![question](images/question.png) => true",
            "single-choice": "- [x] ![answer](images/answer.png)\n- [ ] no",
            "order-sentences": "- [1] ![first](images/first.png)\n- [2] second",
            "fill-blanks": "text: See ![scene](images/scene.png) [[a]].\n- [a] here",
            "flashcard": "front: ![front](images/front.png)\nback: back",
        })
        md = md.replace("Test **prompt**.", "See ![prompt](images/prompt.png).")
        md = md.replace("Because [this]{tl}.", "Because ![reason](images/reason.png).")
        _fm, blocks = mdparser.parse(md)
        self.assertFalse([b["errors"] for b in blocks if b["type"] == "exercise" and b["errors"]])
        for preview in (False, True):
            html = htmlgen.render_document(md, asset_base="/media/x/",
                                           editor_preview=preview)["html"]
            for name, _label in pictures:
                self.assertIn('src="/media/x/images/%s"' % name, html)
            for name in ("definition", "question", "answer", "first", "scene", "front",
                         "prompt", "reason"):
                self.assertIn('src="/media/x/images/%s.png"' % name, html)
            self.assertIn('alt="snow-1.jpg"', html)
            self.assertNotIn('![snow-1.jpg]', html)
        self.assertIn('<span class="ex-inline-image-placeholder">images/snow-1.jpg</span>',
                      htmlgen.render_document(md)["html"])
        fm, blocks = mdparser.parse(md)
        tex = texgen.generate(fm, blocks)
        for name, _label in pictures:
            self.assertIn('keepaspectratio]{images/%s}' % name, tex)
        self.assertIn('keepaspectratio]{images/question.png}', tex)

    def test_every_subtype_normalizes_to_four_primitives(self):
        _fm, blocks = mdparser.parse(document())
        exercises = [b for b in blocks if b["type"] == "exercise"]
        self.assertEqual(set(SAMPLES), {b["subtype"] for b in exercises})
        self.assertEqual({"placement", "choice", "matching", "flashcard"},
                         {b["primitive"] for b in exercises})
        self.assertFalse([(b["subtype"], b["errors"]) for b in exercises if b["errors"]])

    def test_reader_hides_solution_and_preview_is_solved(self):
        reader = htmlgen.render_document(document())
        preview = htmlgen.render_document(document(), editor_preview=True)
        self.assertEqual(12, reader["html"].count('data-scored="1"'))
        self.assertIn("ex-correct-all", reader["html"])
        self.assertNotIn("ex-correct-all", preview["html"])
        self.assertIn('data-editor-preview="1"', preview["html"])
        self.assertIn("✎ Edit", preview["html"])
        self.assertIn('dir="rtl" lang="fa"', reader["html"])
        self.assertIn("front and back shown in preview", preview["html"])

    def test_a_blank_may_sit_inside_a_target_language_mark(self):
        """`text: [من بابک [[slot]]]{tl}` -- one sentence, blanks and all.

        A mark's content holds no brackets, so the sentence used to come out
        as a literal `[`, a detected Persian run and a literal `]{tl}`; a
        blank that OPENED the sentence was worse, because `[[[slot]]` was
        read as a blank named `[slot`, no answer row claimed it, and the
        exercise was refused outright.  Both are written the natural way now
        (texgen.spread_slots), and what the renderers see is marks.
        """
        for text, first in (("[من بابک [[slot]]]{tl}", "mark"),
                            ("[[[slot]] شُما چیه؟]{tl}", "blank")):
            md = document({"fill-blanks":
                "text: %s\n- [slot] [هَستَم]{tl}\n- [ ] [است]{tl}" % text})
            fm, blocks = mdparser.parse(md)
            block = blocks[-1]
            self.assertEqual([], block["errors"], text)
            self.assertEqual({"slot"}, set(texgen.SLOT_RE.findall(block["fields"]["text"])))
            html = htmlgen.render_document(md)["html"]
            fill = re.search(r'<div class="ex-fill".*?</div>', html, re.S).group(0)
            # the sentence is marks and a blank: no bracket of the source left
            self.assertNotIn("]{tl}", fill)
            self.assertNotIn("[[", fill)
            self.assertIn('data-tl-kind="mark"', fill)
            self.assertIn('data-slot="slot"', fill)
            # and in the order it was written: the blank first only where the
            # author put it first
            self.assertEqual(first == "blank",
                             fill.index("ex-blank") < fill.index("data-tl-kind"))
            paper = texgen.generate(fm, blocks)
            self.assertIn("\\rule{5em}{0.4pt}", paper)

    def test_a_sentence_of_the_target_is_laid_out_in_its_own_direction(self):
        """A blank after a Persian phrase, drawn in a left-to-right row of
        boxes, is drawn to its RIGHT -- which reads as the blank coming
        first.  A sentence that is the target's throughout is laid out in the
        target's direction instead, on the page and on paper alike; a mixed
        one is not, and an author's own `content-direction` still rules.
        """
        def fill_of(text, extra=""):
            md = document({"fill-blanks": "%stext: %s\n- [slot] [هَستَم]{tl}" % (extra, text)})
            html = htmlgen.render_document(md)["html"]
            fm, blocks = mdparser.parse(md)
            return (re.search(r'<div class="ex-fill"[^>]*>', html).group(0),
                    texgen.generate(fm, blocks))

        marked, paper = fill_of("[من بابک [[slot]]]{tl}")
        self.assertIn('dir="rtl" lang="fa"', marked)
        # One TeXXeT R group keeps the blank in reading order. The paragraph
        # alignment also keeps its final line at the right edge in the PDF.
        self.assertRegex(paper, r"\{\\raggedleft\\noindent\\beginR .{0,200}?\\rule\{5em\}")
        # the target's own script, unmarked, is the target's line too
        bare, _paper = fill_of("من بابک [[slot]]")
        self.assertIn('dir="rtl"', bare)
        # a sentence of the prose language is left alone
        prose, prose_paper = fill_of("I am [[slot]] here")
        self.assertNotIn("dir=", prose)
        self.assertNotRegex(prose_paper, r"\{\\raggedleft\\noindent\\beginR .{0,200}?\\rule\{5em\}")
        # and the author's own word is never overridden
        said, _p = fill_of("[من بابک [[slot]]]{tl}", extra="content-direction: ltr\n")
        self.assertNotIn("dir=", said)
        _explicit, explicit_paper = fill_of("I am [[slot]] here", extra="content-direction: rtl\n")
        self.assertIn(r"{\raggedleft\noindent\beginR", explicit_paper)

    def test_multiline_rtl_fill_has_a_right_aligned_final_line_in_pdf(self):
        md = ("---\ntitle: Dialogue\ntarget: fa\n---\n"
              ":::exercise fill-blanks\n"
              "prompt: Complete the gaps in the conversation from dialogue 2.\n"
              "content-direction: rtl\ntext: |\n"
              "  بابَک: [[blank1]]، صُبح بِه خِیر.⏎\n"
              "  مَریَم: سَلام. [[blank2]] بِه خِیر.⏎\n"
              "  حالِت چِطورِه؟⏎\n"
              "  بابَک: خوبَم. [[blank3]] تو چِطورِه؟⏎\n"
              "  مَریَم: بَد نیستَم. مِرسی.⏎\n"
              "  بابَک: خُدانِگَهدار.⏎\n"
              "  مَریَم: [[blank4]].\n"
              "- [blank1] [سلام]{tl}\n- [blank2] [صُبح]{tl}\n"
              "- [blank3] [حالِ]{tl}\n- [blank4] [خُداحافِظ]{tl}\n:::")
        fm, blocks = mdparser.parse(md)
        self.assertEqual([], blocks[-1]["errors"])
        paper = texgen.generate(fm, blocks, colophon=False)
        fill = paper.split(r"\raggedleft\noindent\beginR", 1)[1].split(r"\endR\par}", 1)[0]
        self.assertEqual(4, fill.count(r"\rule{5em}{0.4pt}"))
        self.assertIn(r"\newline", fill)
        self.assertIn(r"\pe{مَریَم}: \rule{5em}{0.4pt}", fill)

    def test_whole_target_marks_align_exercise_cells_from_the_right(self):
        rows = ("prompt: Listen again and arrange the lines.\n"
                "- [1] [مامان نیک هفتۀ دیگه کنسرت داره]{tl}\n"
                "- [2] [چه روزی؟]{tl}\n"
                "- [3] [جمعه خانم راد. شما هم لطفاً بیاین. من براتون بلیت می گیرم]{tl}")
        html = htmlgen.render_document(document({"order-sentences": rows}))["html"]
        self.assertEqual(3, html.count('<span class="ex-target-block" dir="rtl" lang="fa">'))
        self.assertIn('data-item="i2"', html)
        self.assertIn('بلیت می گیرم', html)
        # The same renderer supplies both studio documents and exercise decks.
        choice = htmlgen.render_document(document({"single-choice":
            "- [x] [یک پاسخ طولانی برای دو خط]{tl}\n- [ ] English [کلمه]{tl}"}))["html"]
        self.assertEqual(1, choice.count('<span class="ex-target-block" dir="rtl" lang="fa">'))

    def test_each_target_block_in_a_multiline_exercise_cell_aligns_right(self):
        passage = ("[من هفده سال دارم و با خانواده در لندن زندگی می کنم."
                   "⏎در مدرسۀ ایرانی دوستان زیادی دارم.]{tl}")
        question = "[نویسنده تنها زندگی می کند.]{tl}"
        row = passage + "⏎⏎" + question
        md = document({
            "true-false": "- %s => false\n- [دوستم نیک است.]{tl} => true" % row,
            "single-choice": "- [x] English⏎[پاسخ فارسی]{tl}\n- [ ] no",
            "match-translations": "- [واژۀ نخست]{tl}⏎[واژۀ دوم]{tl} => translation",
        })
        _fm, blocks = mdparser.parse(md)
        self.assertFalse([b["errors"] for b in blocks if b["type"] == "exercise" and b["errors"]])
        html = htmlgen.render_document(md)["html"]
        true_false = re.search(r'<section class="exercise"[^>]*data-subtype="true-false".*?</section>',
                               html, re.S).group(0)
        first = re.search(r'<div class="ex-question">(.*?)</div>', true_false, re.S).group(1)
        self.assertEqual(2, first.count('<span class="ex-target-block" dir="rtl" lang="fa">'))
        self.assertIn('در مدرسۀ ایرانی دوستان زیادی دارم.', first)
        self.assertIn('<br>', first)  # a break inside the first {tl} mark
        self.assertIn('<span class="ex-field-line">&nbsp;</span>', first)
        self.assertLess(first.index('من هفده'), first.index('نویسنده تنها'))
        self.assertEqual(6, html.count('<span class="ex-target-block" dir="rtl" lang="fa">'))
        self.assertIn('<span class="ex-field-line">English</span>', html)

    def test_a_row_that_is_only_a_mark_is_named_not_mangled(self):
        """`- [سلام]{tl}` has no marker: the bracket is the mark's own.  It
        used to be taken for the marker, leaving `{tl}` as the answer, and
        nothing said so."""
        md = document({"single-choice": "- [x] [درست]{tl}\n- [سلام]{tl}"})
        _fm, blocks = mdparser.parse(md)
        self.assertIn("answer row needs [ ] or an explicit position before the answer",
                      blocks[-1]["errors"])
        self.assertNotIn({"mark": "سلام", "text": "{tl}"}, blocks[-1]["items"])

    def test_flashcards_alone_are_not_scored(self):
        html = htmlgen.render_document(document({"flashcard": SAMPLES["flashcard"]}))["html"]
        self.assertNotIn("ex-correct-all", html)
        self.assertIn('data-scored="0"', html)

    def test_bad_explicit_answers_render_author_feedback(self):
        md = document({"single-choice": "- [x] one\n- [x] two"})
        _fm, blocks = mdparser.parse(md)
        self.assertTrue(blocks[-1]["errors"])
        self.assertIn("Exercise needs attention", htmlgen.render_document(md)["html"])

    def test_matching_direction_and_printable_version(self):
        md = document({"match-definitions":
            "direction: definition-to-word\n- [猫]{tl} => a small feline"})
        html = htmlgen.render_document(md)["html"]
        self.assertLess(html.index("a small feline"), html.index("猫"))
        fm, blocks = mdparser.parse(md)
        paper = texgen.generate(fm, blocks)
        self.assertIn("Match definitions", paper)
        self.assertNotIn("Because", paper)  # explanations/solutions stay hidden

    def test_explanations_are_neutral_or_result_specific(self):
        neutral = document({"single-choice":
            "- [x] yes\n- [ ] no\nexplanation-correct: One explanation"})
        html = htmlgen.render_document(neutral)["html"]
        self.assertIn("ex-explanation-neutral", html)
        self.assertNotIn("data-explanation-for", html)

        result = document({"single-choice":
            "- [x] yes\n- [ ] no\nexplanation-correct: Success reason\n"
            "explanation-incorrect: Review this instead"})
        html = htmlgen.render_document(result)["html"]
        self.assertIn('data-explanation-for="correct"', html)
        self.assertIn('data-explanation-for="incorrect"', html)

    def test_sentence_construction_has_inline_sequence_layout(self):
        html = htmlgen.render_document(document({
            "construct-sentence": "- [1] one\n- [2] two",
            "order-sentences": "- [1] First sentence.\n- [2] Second sentence.",
        }))["html"]
        construct = html[html.index('data-subtype="construct-sentence"'):]
        construct = construct[:construct.index("</section>")]
        ordered = html[html.index('data-subtype="order-sentences"'):]
        ordered = ordered[:ordered.index("</section>")]
        self.assertIn('class="ex-sequence ex-sequence-inline"', construct)
        self.assertIn('class="ex-sequence ex-sequence-inline" dir="rtl"', construct)
        self.assertIn('class="ex-sequence"', ordered)
        self.assertNotIn("ex-sequence-inline", ordered)

    def test_sentence_answer_direction_is_separate_from_activity_direction(self):
        def sequence(target, fields=""):
            md = ("---\ntitle: Directions\ntarget: %s\n---\n\n"
                  ":::exercise construct-sentence\nprompt: Build it.\n%s"
                  "- [1] first\n- [2] second\n:::") % (target, fields)
            return htmlgen.render_document(md)["html"].split('class="ex-sequence ex-sequence-inline"', 1)[1]

        self.assertTrue(sequence("fa").startswith(' dir="rtl"'))
        self.assertTrue(sequence("en").startswith(' dir="ltr"'))
        self.assertTrue(sequence("fa", "content-direction: ltr\n").startswith(' dir="rtl"'))
        self.assertTrue(sequence("en", "content-direction: rtl\n").startswith(' dir="ltr"'))
        self.assertTrue(sequence("fa", "answer-direction: ltr\n").startswith(' dir="ltr"'))
        self.assertTrue(sequence("en", "answer-direction: rtl\n").startswith(' dir="rtl"'))
        bad = ("---\ntarget: fa\n---\n:::exercise construct-sentence\n"
               "answer-direction: upward\n- [1] one\n:::")
        block = next(b for b in mdparser.parse(bad)[1] if b["type"] == "exercise")
        self.assertIn("answer-direction must be rtl or ltr", block["errors"])

    def test_a_flashcard_is_a_focusable_card_not_a_button(self):
        # a side may hold a table, a link or a player, none of which may sit
        # inside a <button>; the hint has a class of its own to be found by
        md = document({"flashcard": SAMPLES["flashcard"]})
        reader = htmlgen.render_document(md)["html"]
        self.assertIn('<div class="ex-flashcard" role="button" tabindex="0" data-card-type="jolly" '
                      'aria-label="Flip flashcard" aria-pressed="false"><div class="ex-card-front">', reader)
        self.assertIn('<div class="ex-card-back" hidden>', reader)
        self.assertIn('<small class="ex-card-hint">tap to reveal</small></div>', reader)
        self.assertNotIn('class="ex-flashcard', reader[:reader.index('<div class="ex-flashcard')])
        preview = htmlgen.render_document(md, editor_preview=True)["html"]
        self.assertIn('<div class="ex-flashcard flipped" role="button" tabindex="0" data-card-type="jolly" '
                      'aria-label="Flip flashcard" aria-pressed="true">', preview)
        self.assertIn('<small class="ex-card-hint">front and back shown in preview</small>', preview)

    def test_jolly_fields_may_hold_blocks_and_need_one_a_side(self):
        md = document({"flashcard": "card-type: jolly\nfront-primary: [سلام]{tl}\n"
                                    "back-secondary: |\n  - hello\n  - hi\n\n  | a | b |\n  |---|---|\n  | 1 | 2 |"})
        _fm, blocks = mdparser.parse(md)
        self.assertEqual([], blocks[-1]["errors"])
        self.assertEqual("- hello\n- hi\n\n| a | b |\n|---|---|\n| 1 | 2 |",
                         blocks[-1]["raw_fields"]["back-secondary"])
        html = htmlgen.render_document(md)["html"]
        self.assertIn('<div class="ex-card-field ex-card-blocks secondary" style="font-size:88%;'
                      'color:var(--graytx)"><ul><li>hello</li><li>hi</li></ul>\n<div class="tablewrap">', html)
        paper = texgen.generate(*mdparser.parse(md))
        # on paper the back half of the card: its blocks from the start of
        # the line, at the page's size, in the field's shade -- and a table
        # fitted to the half, at every print size
        self.assertIn("}{{\\raggedright\\expapercardsize{100}\\color{graytx} \\begin{itemize}\n"
                      "\\item hello", paper)
        self.assertIn("\\exlexfit{\\begin{tabular}", paper)
        self.assertIn("\\newcommand\\exlexfit[1]", paper)
        lonely = document({"flashcard": "card-type: jolly\nfront-primary: only a front"})
        self.assertEqual(["a Jolly flashcard needs a front field and a back field"],
                         mdparser.parse(lonely)[1][-1]["errors"])

    def test_vocab_recordings_are_checked_and_played(self):
        md = document({"flashcard": "target: [کتاب]{tl}\nmeaning: book\n"
                                    "front-audio: audio/ketab.mp3\nback-audio: book.mp3"})
        self.assertEqual(["back-audio must name a file under audio/ (e.g. audio/word.mp3)"],
                         mdparser.parse(md)[1][-1]["errors"])
        md = md.replace("back-audio: book.mp3", "back-audio: audio/book.mp3")
        html = htmlgen.render_document(md, asset_base="/media/x/")["html"]
        self.assertIn('<span class="ex-card-audio" data-side="front"><audio preload="metadata" '
                      'src="/media/x/audio/ketab.mp3"></audio><button type="button" class="ex-card-play" '
                      'aria-label="Play the recording" title="Play">🔊</button></span>', html)
        self.assertIn('src="/media/x/audio/book.mp3"', html)

    def test_an_exercise_carries_a_picture_with_its_question_and_one_for_the_answer(self):
        md = document({"single-choice": "image: images/map.png\nimage-answer: images/key.png\n"
                                        "- [x] north\n- [ ] south"})
        block = mdparser.parse(md)[1][-1]
        self.assertEqual([], block["errors"])
        self.assertEqual("images/map.png", block["fields"]["image"])
        html = htmlgen.render_document(md, asset_base="/media/x/")["html"]
        # the question's picture between the prompt and the activity, the
        # answer's after it and hidden until the exercise has been answered
        self.assertIn('<div class="ex-prompt">Test <strong>prompt</strong>.</div>'
                      '<div class="ex-image ex-image-prompt align-left">'
                      '<img src="/media/x/images/map.png" alt="Picture with the question" '
                      'style="width:60%"></div><div class="ex-body"', html)
        self.assertIn('</div><div class="ex-image ex-image-answer align-left" hidden>'
                      '<img src="/media/x/images/key.png" alt="Picture shown with the answer" '
                      'style="width:60%"></div><div class="ex-explanation', html)
        # the editor's preview shows an exercise solved, its answer with it
        shown = htmlgen.render_document(md, asset_base="/media/x/", editor_preview=True)["html"]
        self.assertIn('<div class="ex-image ex-image-answer align-left"><img '
                      'src="/media/x/images/key.png"', shown)
        # a PDF figure is drawn through the twin the studio makes of it
        twin = htmlgen.render_document(md.replace("images/key.png", "images/key.pdf"),
                                       asset_base="/media/x/")["html"]
        self.assertIn('src="/media/x/images/key.pdf.svg"', twin)
        # with no base (an unsaved document) the path is named, not drawn
        self.assertIn('<span class="ex-image-placeholder">images/map.png</span>',
                      htmlgen.render_document(md)["html"])
        # on paper: the question's picture, and nothing of the answer
        fm, blocks = mdparser.parse(md)
        tex = texgen.generate(fm, blocks)
        # capped: a tall picture may not push the exercise's own answers off
        # the page, and its box cannot break across one
        self.assertIn("\\includegraphics[width=\\linewidth,height=0.3\\textheight,"
                      "keepaspectratio]{images/map.png}", tex)
        self.assertNotIn("images/key.png", tex)

    def test_a_printed_fill_sentence_draws_its_blanks_and_starts_a_control_word(self):
        md = document({"fill-blanks": "image: images/map.png\ntext: I [[v]] books.\n- [v] read"})
        tex = texgen.generate(*mdparser.parse(md))
        # `\smallskip` running into the sentence is one undefined control word
        self.assertNotIn("\\smallskipI", tex)
        self.assertIn("\\par\\smallskip{}I \\rule{5em}{0.4pt} books.", tex)
        self.assertNotIn("[[v]]", tex)

    def test_a_picture_takes_the_width_and_the_side_a_figure_line_takes(self):
        md = document({"single-choice": "image: images/map.png {width=45 align=center}\n"
                                        "image-answer: images/key.png{align=right}\n"
                                        "- [x] north\n- [ ] south"})
        block = mdparser.parse(md)[1][-1]
        self.assertEqual([], block["errors"])
        self.assertEqual({"path": "images/map.png", "width": 45, "align": "center"},
                         mdparser.exercise_image(block["fields"]["image"]))
        html = htmlgen.render_document(md, asset_base="/media/x/")["html"]
        self.assertIn('<div class="ex-image ex-image-prompt align-center"><img '
                      'src="/media/x/images/map.png" alt="Picture with the question" '
                      'style="width:45%"></div>', html)
        self.assertIn('<div class="ex-image ex-image-answer align-right" hidden><img '
                      'src="/media/x/images/key.png" alt="Picture shown with the answer" '
                      'style="width:60%"></div>', html)
        # the same share of the column, on the same side, on paper
        tex = texgen.generate(*mdparser.parse(md))
        self.assertIn("\\noindent\\hspace*{0.275\\linewidth}"
                      "\\begin{minipage}{0.450\\linewidth}", tex)
        # a width outside 5..100 is brought back into it, as a figure's is
        wild = document({"true-false": "image: images/map.png {width=500}\n- It is. => true"})
        self.assertEqual(100, mdparser.exercise_image(
            mdparser.parse(wild)[1][-1]["fields"]["image"])["width"])

    def test_a_picture_field_is_checked_and_a_flashcard_is_told_where_its_own_are(self):
        bad = document({"match-definitions": "image: map.png\n- cat => an animal"})
        self.assertEqual(["image must name a file under images/ (e.g. images/map.png)"],
                         mdparser.parse(bad)[1][-1]["errors"])
        bad = document({"match-definitions": "image: images/map.png and a word\n- cat => an animal"})
        self.assertEqual(["image must name a file under images/ (e.g. images/map.png)"],
                         mdparser.parse(bad)[1][-1]["errors"])
        card = document({"flashcard": "card-type: vocab\ntarget: [کتاب]{tl}\n"
                                      "meaning: book\nimage: images/map.png"})
        self.assertEqual(["a flashcard's pictures are front-image and back-image, not image"],
                         mdparser.parse(card)[1][-1]["errors"])

    def test_an_exercise_carries_a_recording_with_its_question_and_one_for_the_answer(self):
        """The picture pair over again, field for field: `audio` with the
        question and `audio-answer` once it has been answered."""
        md = document({"single-choice": "audio: audio/q.mp3\naudio-answer: audio/a.mp3\n"
                                        "- [x] north\n- [ ] south"})
        block = mdparser.parse(md)[1][-1]
        self.assertEqual([], block["errors"])
        html = htmlgen.render_document(md, asset_base="/media/x/")["html"]
        # the question's recording between the prompt and the activity, the
        # answer's after it and held back until the exercise is answered
        self.assertIn('<div class="ex-prompt">Test <strong>prompt</strong>.</div>'
                      '<div class="ex-audio ex-audio-prompt align-left">'
                      '<audio controls preload="metadata" src="/media/x/audio/q.mp3" '
                      'aria-label="Recording with the question" style="width:60%"></audio>'
                      '</div><div class="ex-body"', html)
        self.assertIn('<div class="ex-audio ex-audio-answer align-left" hidden>'
                      '<audio controls preload="metadata" src="/media/x/audio/a.mp3" '
                      'aria-label="Recording played with the answer" '
                      'style="width:60%"></audio></div><div class="ex-explanation', html)
        # the editor's preview shows an exercise solved, its answer with it
        shown = htmlgen.render_document(md, asset_base="/media/x/", editor_preview=True)["html"]
        self.assertIn('<div class="ex-audio ex-audio-answer align-left"><audio', shown)
        # with no base (an unsaved document) the path is named, not played
        self.assertIn('<span class="ex-audio-placeholder">🔊 <code>audio/q.mp3</code></span>',
                      htmlgen.render_document(md)["html"])
        # on paper: a recording cannot be played, so the question's is the
        # card that says which file it is -- and nothing of the answer's
        tex = texgen.generate(*mdparser.parse(md))
        self.assertIn("audio · q.mp3", tex)
        self.assertNotIn("a.mp3", tex)

    def test_a_recording_takes_the_width_the_side_and_the_clip(self):
        md = document({"single-choice": "audio: audio/q.mp3 {width=45 align=center "
                                        "start=1:05.2 end=1:09}\n"
                                        "- [x] north\n- [ ] south"})
        block = mdparser.parse(md)[1][-1]
        self.assertEqual([], block["errors"])
        self.assertEqual({"path": "audio/q.mp3", "width": 45, "align": "center",
                          "start": 65.2, "end": 69},
                         mdparser.exercise_audio(block["fields"]["audio"]))
        html = htmlgen.render_document(md, asset_base="/media/x/")["html"]
        # the clip is a media fragment, as a recording line's is, and the box
        # carries the window for the page script that stops at its end
        self.assertIn('<div class="ex-audio ex-audio-prompt align-center" '
                      'data-start="65.2" data-end="69"><audio controls preload="metadata" '
                      'src="/media/x/audio/q.mp3#t=65.2,69"', html)
        # the same share of the column, on the same side, on paper -- and the
        # stretch said in words, since paper cannot play it
        tex = texgen.generate(*mdparser.parse(md))
        self.assertIn("\\noindent\\hspace*{0.275\\linewidth}"
                      "\\begin{minipage}{0.450\\linewidth}", tex)
        self.assertIn("audio · q.mp3 · 1:05.2–1:09", tex)

    def test_a_recording_field_is_checked_and_a_flashcard_is_told_where_its_own_are(self):
        for value in ("q.mp3", "audio/q.txt", "audio/q.mp3 and a word"):
            bad = document({"match-definitions": "audio: %s\n- cat => an animal" % value})
            self.assertEqual(["audio must name a file under audio/ (e.g. audio/word.mp3)"],
                             mdparser.parse(bad)[1][-1]["errors"], value)
        card = document({"flashcard": "card-type: vocab\ntarget: [کتاب]{tl}\n"
                                      "meaning: book\naudio: audio/q.mp3"})
        self.assertEqual(["a flashcard's recordings are front-audio and back-audio, not audio"],
                         mdparser.parse(card)[1][-1]["errors"])

    def test_a_jolly_field_draws_everything_the_page_draws(self):
        # each construct in a field, and the same construct on the page:
        # what the card draws is what the page draws
        for target, body, want in (
                ("fa", "[سلام دنیا]{tl}", '<p class="fa-par"'),
                ("fa", "سلام دنیا", '<p class="fa-display">'),
                ("fa", "[aside]{la align=right width=60}", '<div class="la-par align-right"'),
                ("ja", "[今日は]{tl vertical height=8}", 'class="fa-par tl-vertical"'),
                ("fa", "[سلام]{tl bg=quote font=nastaliq}", "fa-alt"),
                ("en", "| a | b |\n  |---|---|\n  | 1 | 2 |", "<table"),
                ("en", "- one\n  - two", "<ul>"),
                ("en", "> a box", '<div class="box">'),
                ("en", "### a heading", '<h3 class="subsection">'),
                ("en", "![cap](images/x.png){width=40 align=center}", 'figure class="img align-center"'),
                ("en", "![cap](audio/x.mp3)", 'figure class="img audio'),
                ("en", "a[^n]\n\n  [^n]: the note", 'class="fnref"')):
            md = ("---\ntitle: T\ntarget: %s\nlang: en\n---\n\n:::exercise flashcard\n"
                  "card-type: jolly\nfront-primary: |\n  %s\nback-primary: b\n:::\n"
                  % (target, body))
            html = htmlgen.render_document(md, asset_base="/m/")["html"]
            front = html[html.index('<div class="ex-card-front">'):html.index('<div class="ex-card-back"')]
            self.assertIn(want, front, body)
        # one paragraph of prose is the card's own line, inline as it always
        # was; a field of blocks takes the card's width instead
        plain = ("---\ntitle: T\ntarget: fa\n---\n\n:::exercise flashcard\ncard-type: jolly\n"
                 "front-primary: plain **prose**\nback-primary: |\n  - a\n  - b\n:::\n")
        html = htmlgen.render_document(plain)["html"]
        self.assertIn('<div class="ex-card-field primary" style="font-size:120%;color:var(--ink)">'
                      'plain <strong>prose</strong></div>', html)
        self.assertIn('<div class="ex-card-field ex-card-blocks primary"', html)

    def test_a_jolly_field_goes_on_over_the_lines_under_it(self):
        md = ("---\ntitle: T\ntarget: ja\nlang: en\n---\n\n"
              ":::exercise flashcard\ncard-type: jolly\n"
              "front-primary: 今日は\nいい 天気ですね\n"
              "front-secondary: kyō wa ii tenki desu ne\n"
              "back-primary: It is fine weather today.\n\n"
              "| word | meaning |\n|---|---|\n| 天気 | weather |\n"
              "back-secondary: b\n:::\n")
        block = mdparser.parse(md)[1][-1]
        self.assertEqual([], block["errors"])
        self.assertEqual("今日は\nいい 天気ですね", block["raw_fields"]["front-primary"])
        self.assertEqual("kyō wa ii tenki desu ne", block["fields"]["front-secondary"])
        self.assertIn("| word | meaning |", block["raw_fields"]["back-primary"])
        html = htmlgen.render_document(md)["html"]
        self.assertIn("<table", html)
        # a line that is not a field, a row or the closing ::: is still an
        # error anywhere else: a mistyped row must not vanish into a prompt
        stray = ("---\ntitle: T\ntarget: ja\n---\n\n:::exercise single-choice\n"
                 "prompt: Pick one\nstray line\n- [x] a\n- [ ] b\n:::\n")
        self.assertEqual(["unrecognized line: stray line"],
                         mdparser.parse(stray)[1][-1]["errors"])
        # and a row on a card, which has no answers, is said rather than dropped
        rows = ("---\ntitle: T\ntarget: ja\n---\n\n:::exercise flashcard\ncard-type: jolly\n"
                "front-primary: a\nback-primary: b\n- one\n- two\n:::\n")
        self.assertEqual(["a flashcard has no answer rows: write a list inside a field, "
                          "as `front-primary: |` and its lines under it"],
                         mdparser.parse(rows)[1][-1]["errors"])

    def test_the_fixture_card_is_unchanged_but_for_its_wrapper(self):
        md = (ROOT / "tests" / "fixtures" / "studio" / "exercises" / "exercises.md").read_text(encoding="utf-8")
        html = htmlgen.render_document(md)["html"]
        # the card's first field is one target-language line: the block the
        # page draws of it, at the card's own size and in its place
        self.assertIn('<div class="ex-card-front"><div class="ex-card-field primary" style="font-size:140%;'
                      'color:var(--ink)"><p class="fa-par" dir="ltr" lang="ja"', html)
        self.assertIn('<div class="ex-card-back" hidden><div class="ex-card-field primary" style="font-size:120%;'
                      'color:var(--ink)">question</div><div class="ex-card-field secondary" style="font-size:88%;'
                      'color:var(--graytx)">a request for information</div></div>'
                      '<small class="ex-card-hint">tap to reveal</small></div>', html)

    def test_note_hover_replaces_complete_exercises(self):
        md = ("---\ntitle: Note\ntarget: en\n---\n\nBefore.\n\n"
              ":::exercise single-choice\nprompt: Secret question\n"
              "- [ ] tempting answer\n- [x] stored answer\n"
              "explanation-correct: Secret explanation\n:::\n\nAfter.")
        preview = notes.excerpt(md)
        self.assertEqual("Before.\n<Exercise>\nAfter.", preview)
        for secret in ("Secret question", "tempting answer", "stored answer", "Secret explanation"):
            self.assertNotIn(secret, preview)


class DeckButtonTests(unittest.TestCase):
    BUTTON = 'class="ex-to-deck"'
    BOXED = ("---\ntitle: Boxed\ntarget: fa\n---\n\n"
             ":::exercise single-choice\nprompt: Top.\n- [x] yes\n- [ ] no\n:::\n\n"
             "> A box.\n>\n> :::exercise true-false\n> prompt: Boxed.\n"
             "> - It is. => true\n> :::")

    def test_only_when_asked_and_never_in_the_editor_preview(self):
        self.assertNotIn(self.BUTTON, htmlgen.render_document(document())["html"])
        asked = htmlgen.render_document(document(), deck_button=True)["html"]
        self.assertEqual(len(SAMPLES), asked.count(self.BUTTON))
        self.assertIn('title="Copy this exercise into an exercise deck">+ Deck</button>', asked)
        preview = htmlgen.render_document(document(), editor_preview=True,
                                          deck_button=True)["html"]
        self.assertNotIn(self.BUTTON, preview)
        self.assertIn("✎ Edit", preview)

    def test_an_exercise_with_errors_gets_none(self):
        # a deck refuses a block with errors, so offering the copy only
        # leads to a refusal (and, from "+ New deck", to an empty deck)
        md = document({"single-choice": "- [ ] one\n- [ ] two",
                       "true-false": SAMPLES["true-false"]})
        html = htmlgen.render_document(md, deck_button=True)["html"]
        self.assertEqual(['1', '2'], re.findall(r'data-exercise="(\d+)"', html))
        invalid = html[html.index('data-exercise="1"'):html.index('data-exercise="2"')]
        self.assertIn("ex-invalid", invalid)
        self.assertNotIn(self.BUTTON, invalid)
        self.assertEqual(1, html.count(self.BUTTON))

    def test_a_boxed_exercise_gets_one_too(self):
        html = htmlgen.render_document(self.BOXED, deck_button=True)["html"]
        self.assertEqual(['1', '2'], re.findall(r'data-exercise="(\d+)"', html))
        self.assertEqual(2, html.count(self.BUTTON))

    def test_doc_page_offers_decks_but_a_note_does_not(self):
        class Handler:
            query = {}
            def send_html(self, text, code=200): self.html = text

        with tempfile.TemporaryDirectory() as td:
            old = store.use_library(td)
            try:
                doc_id = store.create(self.BOXED)["id"]
                page = Handler()
                studio_server.page_doc(page, doc_id)
                self.assertIn('data-decks-base="/exercises"', page.html)
                self.assertEqual(2, page.html.count(self.BUTTON))
                was = studio_server.use_mount(base="/books/notes", html_only=True)
                try:
                    note = Handler()
                    studio_server.page_doc(note, doc_id)
                finally:
                    studio_server.restore_mount(was)
                self.assertIn('data-decks-base=""', note.html)
                self.assertNotIn(self.BUTTON, note.html)
            finally:
                store.use_library(old)


class DownloadShownTests(unittest.TestCase):
    class Handler:
        def __init__(self, body):
            self.raw = body.encode("utf-8") if isinstance(body, str) else body
            self.sent = None
        def _body(self): return self.raw
        def send_json(self, obj, code=200): self.sent = ("json", obj, code)
        def send_bytes(self, data, ctype, code=200, extra=None):
            self.sent = ("zip", data, ctype, code, extra or {})

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.old = store.use_library(self.td.name)
        make = lambda title, target, text: store.create(
            "---\ntitle: %s\ntarget: %s\n---\n\n%s" % (title, target, text))["id"]
        # two NAMES are never one (a link by name must mean one document),
        # but two names can still make one short file name: "same-title"
        self.twin_a = make("Same Title", "en", "first")
        self.twin_b = make("Same title!", "en", "second")
        self.other = make("Other", "fa", "third")

    def tearDown(self):
        store.use_library(self.old)
        self.td.cleanup()

    def download(self, body):
        h = self.Handler(body)
        studio_server.api_download(h)
        return h.sent

    def unzip(self, sent, n):
        kind, data, ctype, code, extra = sent
        self.assertEqual(("zip", "application/zip", 200), (kind, ctype, code))
        self.assertRegex(extra["Content-Disposition"],
                         r'^attachment; filename="studio-%d-documents-\d{8}-\d{4}\.zip"$' % n)
        return zipfile.ZipFile(io.BytesIO(data))

    def test_route_is_not_shadowed(self):
        first = next(fn for m, pattern, fn in studio_server.ROUTES
                     if m == "POST" and re.match(pattern, "/api/download"))
        self.assertIs(studio_server.api_download, first)

    def test_form_body_keeps_order_skips_unknown_and_names_collisions_by_id(self):
        ids = [self.other, "missing-000000", self.twin_a, "../escape",
               self.other, self.twin_b]
        with self.unzip(self.download("ids=" + urllib.parse.quote(",".join(ids))), 3) as zf:
            self.assertEqual(["other.md", self.twin_a + ".md", self.twin_b + ".md"],
                             zf.namelist())
            self.assertEqual(store.get(self.twin_b)[1],
                             zf.read(self.twin_b + ".md").decode("utf-8"))
            self.assertEqual(zipfile.ZIP_DEFLATED, zf.getinfo("other.md").compress_type)

    def test_json_body_and_a_repeated_form_field(self):
        sent = self.download(json.dumps({"ids": [self.twin_a, "missing-000000"]}))
        with self.unzip(sent, 1) as zf:
            # one of the twins alone collides with nothing: the short name
            self.assertEqual(["same-title.md"], zf.namelist())
            self.assertEqual(store.get(self.twin_a)[1], zf.read("same-title.md").decode("utf-8"))
        sent = self.download("ids=%s&ids=%s" % (self.other, self.twin_b))
        with self.unzip(sent, 2) as zf:
            self.assertEqual(["other.md", "same-title.md"], zf.namelist())

    def test_nothing_left_answers_400_with_ok_false(self):
        for body in ("", "ids=", "ids=missing-000000%2C..%2Fx",
                     json.dumps({"ids": []}), json.dumps({"ids": "nope-123456"}),
                     json.dumps(["not", "an", "object"])):
            kind, answer, code = self.download(body)
            self.assertEqual(("json", 400), (kind, code), body)
            self.assertEqual({"ok": False, "error": "no documents to download"}, answer)
        kind, answer, code = self.download("{not json")
        self.assertEqual(("json", 400, False), (kind, code, answer["ok"]))
        # nested past the decoder's stack: unreadable too, not a 500 with a traceback
        kind, answer, code = self.download('{"ids": ' + "[" * 100000 + "}")
        self.assertEqual(("json", 400, False, "bad JSON body"),
                         (kind, code, answer["ok"], answer["error"]))


class FootnoteRingTests(unittest.TestCase):
    RING = ("---\ntitle: Ring\ntarget: fa\n---\n\n"
            "One[^a] and two[^c].\n\n"
            "[^a]: see [^a]\n"
            "[^b]: back to [^c]\n"
            "[^c]: on to [^b]\n")

    def test_notes_that_cite_themselves_render_without_recursing(self):
        html = htmlgen.render_document(self.RING)["html"]
        self.assertIn("see", html)
        self.assertIn("back to", html)
        fm, blocks = mdparser.parse(self.RING)
        paper = texgen.generate(fm, blocks)
        self.assertIn("see", paper)
        self.assertIn("back to", paper)


class TagFilterTests(unittest.TestCase):
    def test_include_and_exclude_compose(self):
        with tempfile.TemporaryDirectory() as td:
            old = store.use_library(td)
            try:
                for title, tags in (("A", ["grammar", "hard"]),
                                    ("B", ["grammar"]), ("C", ["vocabulary"])):
                    store.create("---\ntitle: %s\ntarget: en\n---\n\ntext" % title,
                                 tags=tags)
                self.assertEqual(["B"], [d["title"] for d in
                    store.list_docs(tags=["grammar"], exclude_tags=["hard"], sort="title")])
                self.assertEqual({"B", "C"}, {d["title"] for d in
                    store.list_docs(exclude_tags=["hard"])})
            finally:
                store.use_library(old)


class PromptTests(unittest.TestCase):
    def test_selected_deck_vocabulary_is_structured_and_optional(self):
        class Handler:
            def __init__(self, body): self.body, self.answer = body, None
            def _json_body(self): return self.body
            def send_json(self, answer, code=200): self.answer = answer

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            deck = root / "japanese" / "known"
            (deck / "cards").mkdir(parents=True)
            (deck / "deck.json").write_text(json.dumps(
                {"name": "Known", "lang": "ja"}), encoding="utf-8")
            (deck / "cards" / "one.json").write_text(json.dumps({
                "fa": "猫", "kana": "ねこ", "tr": "neko", "en": "cat",
                "opp": "犬", "opp_kana": "いぬ", "opp_tr": "inu"},
                ensure_ascii=False), encoding="utf-8")
            old = studio_server.ANKI_DIR
            studio_server.ANKI_DIR = root
            try:
                h = Handler({"markdown": "# Cats", "decks": ["japanese/known"]})
                studio_server.api_exercise_prompt(h)
                self.assertEqual(2, h.answer["vocabulary"])
                self.assertIn("猫\tねこ\tneko\tcat", h.answer["prompt"])
                self.assertIn("# Cats", h.answer["prompt"])
                empty = Handler({"markdown": "# Cats", "decks": []})
                studio_server.api_exercise_prompt(empty)
                self.assertEqual(0, empty.answer["vocabulary"])
                self.assertNotIn("```tsv", empty.answer["prompt"])
            finally:
                studio_server.ANKI_DIR = old

    def test_rtl_exercise_prompt_covers_visual_boxes_and_sentence_chunks(self):
        class Handler:
            def __init__(self, markdown):
                self.body = {"markdown": markdown, "decks": []}
                self.answer = None
            def _json_body(self): return self.body
            def send_json(self, answer, code=200): self.answer = answer

        rtl = Handler("---\ntitle: Arabic\ntarget: ar\n---\n\nLesson")
        studio_server.api_exercise_prompt(rtl)
        prompt = rtl.answer["prompt"]
        self.assertIn("Mixed-direction sequences for Arabic — binding", prompt)
        self.assertIn("prompt, each answer or selectable segment", prompt)
        self.assertIn(
            "[گاه]{#6B6B1A translit:-gāh} + "
            "[ش]{#C28E0E translit:-eš} + [دان]{translit:dān}", prompt)
        self.assertNotIn("`دان + ش + گاه`", prompt)
        self.assertIn("does not depend on the plus sign", prompt)
        self.assertIn("- [1] [first_word]{tl}\n- [2] [second_word]{tl}", prompt)
        self.assertIn("`answer-direction: rtl` or `answer-direction: ltr`", prompt)

        ltr = Handler("---\ntitle: English\ntarget: en\n---\n\nLesson")
        studio_server.api_exercise_prompt(ltr)
        self.assertNotIn("Mixed-direction sequences for English", ltr.answer["prompt"])

    def test_exercise_prompt_builds_its_dialect_from_the_boxes_the_page_uses_and_teaches_the_language(self):
        # CHANGED ON PURPOSE (brief 7.6; it was "teaches the whole dialect"): a jolly card takes any block of
        # the dialect, so the exercise prompt teaches the parts of it the page already uses -- built from the
        # studio prompt's own boxes, not embedded whole -- and the target's conventions, after the exercise
        # instructions, which say they win, and before the page
        class Handler:
            def __init__(self, markdown, **more):
                self.body = dict({"markdown": markdown, "decks": []}, **more)
                self.answer = None
            def _json_body(self): return self.body
            def send_json(self, answer, code=200): self.answer = answer

        page = ("---\ntitle: Persian\ntarget: fa\n---\n\n## کتاب | ketāb | from Arabic | = *book*\n\n"
                "| Form | Meaning |\n|---|---|\n| کتاب | a book |\n")
        h = Handler(page)
        studio_server.api_exercise_prompt(h)
        prompt = h.answer["prompt"]
        # what the page uses, read with the parser, is ticked; the rest is named as reserved
        self.assertEqual(h.answer["preticked"]["boxes"], ["vocab", "tables"])
        self.assertEqual([b["id"] for b in h.answer["boxes"] if b["on"]], ["vocab", "tables"])
        self.assertIn("**Vocabulary entries.**", prompt)
        self.assertIn("**Tables.**", prompt)
        self.assertNotIn("**Colour marks.**", prompt)
        self.assertNotIn("**LaTeX drawings.**", prompt)
        self.assertIn("`[word]{crimson}`", prompt[prompt.index("**Reserved marks.**"):])
        conventions = studio_server.lang_block("fa")
        self.assertTrue(conventions, "docs/lang/fa.md is there to be appended")
        dialect = studio_server.promptboxes.dialect_text(
            studio_server.languages.get("fa"), ["vocab", "tables"], studio_server.promptboxes.TYPE_IDS)
        self.assertIn("front-audio", prompt)
        self.assertIn("`field-name: |`", prompt)
        heading = "## The page's Markdown dialect"
        self.assertEqual(prompt.count(heading), 1)
        at = {name: prompt.find(text) for name, text in (
            ("instructions", "You are adding practice activities"),
            ("rtl", "Mixed-direction sequences for Persian — binding"),
            ("dialect", heading), ("boxes", dialect), ("conventions", conventions),
            ("contract", "Return the complete updated Markdown document in one fenced"),
            ("page", "Here is the complete Markdown page to augment"))}
        self.assertTrue(all(v >= 0 for v in at.values()), at)
        self.assertEqual(sorted(at, key=at.get),
                         ["instructions", "rtl", "dialect", "boxes", "conventions", "contract", "page"])
        self.assertNotIn("creating a markdown file", prompt, "the authoring prompt's file-asking "
                         "contract is not part of the dialect this prompt teaches")
        self.assertIn("the instructions above win", prompt[at["dialect"]:at["boxes"]])
        self.assertIn("![…](audio/…)", prompt, "a picture and a recording are never written, and named so")

        # the boxes are the person's to change: none is the reserved list alone, all is the whole dialect
        none = Handler(page, boxes=[])
        studio_server.api_exercise_prompt(none)
        self.assertNotIn("**Vocabulary entries.**", none.answer["prompt"])
        self.assertIn("vocabulary entry", none.answer["prompt"])
        everything = Handler(page, boxes=studio_server.promptboxes.BOX_IDS)
        studio_server.api_exercise_prompt(everything)
        self.assertIn("**LaTeX drawings.**", everything.answer["prompt"])
        self.assertNotIn("**Exercises.**", everything.answer["prompt"], "the types are this prompt's exercises")
        self.assertLess(len(prompt), len(everything.answer["prompt"]))

        # the studio page's custom prompt is that page's choice and does not carry over
        original = studio_server.store.get_prompt
        studio_server.store.get_prompt = lambda: {"text": "Custom dialect rules", "custom": True}
        try:
            custom = Handler("---\ntitle: English\ntarget: en\n---\n\nLesson")
            studio_server.api_exercise_prompt(custom)
            text = custom.answer["prompt"]
            self.assertIn(heading, text)
            self.assertNotIn("Custom dialect rules", text)
            english = studio_server.lang_block("en")
            if english:
                self.assertIn(english, text)
        finally:
            studio_server.store.get_prompt = original

    def test_standard_studio_prompt_gets_the_same_rtl_box_rule(self):
        class Handler:
            def __init__(self, target):
                self.query = {"target": [target]}
                self.answer = None
            def send_json(self, answer, code=200): self.answer = answer

        rtl = Handler("fa")
        studio_server.api_prompt_get(rtl)
        self.assertIn("Mixed-direction sequences: distinguish the direction",
                      rtl.answer["text"] + rtl.answer["lang_block"])
        self.assertIn("[گاه]{#6B6B1A translit:-gāh}",
                      rtl.answer["text"] + rtl.answer["lang_block"])

        original = studio_server.store.get_prompt
        studio_server.store.get_prompt = lambda: {"text": "Custom instructions", "custom": True}
        try:
            custom = Handler("ar")
            studio_server.api_prompt_get(custom)
            self.assertIn("Mixed-direction sequences for Arabic — binding",
                          custom.answer["lang_block"])
        finally:
            studio_server.store.get_prompt = original

        ltr = Handler("en")
        studio_server.api_prompt_get(ltr)
        self.assertNotIn("Mixed-direction sequences for English",
                         ltr.answer["lang_block"])


def paper(md, **options):
    return texgen.generate(*mdparser.parse(md), colophon=False, **options)


class PrintSizeTests(unittest.TestCase):
    """The build's print size (texgen.PRINT_SIZES): what the .tex is set
    at; tests/test_studio_pdf_print.py builds the PDFs."""

    def test_the_normal_size_writes_the_tex_it_always_wrote(self):
        md = document({"fill-blanks": SAMPLES["fill-blanks"], "single-choice": SAMPLES["single-choice"]})
        tex = paper(md)
        self.assertEqual(tex, paper(md, font_size=11, mono=False))
        self.assertIn("\\documentclass[11pt,a4paper]{article}\n", tex)
        self.assertIn("\\usepackage[a4paper,top=2.4cm,bottom=2.4cm,left=2.5cm,right=2.5cm]{geometry}", tex)
        self.assertIn("\\fontsize{38}{44}", tex)
        self.assertIn("\\rule{5em}{0.4pt}", tex)
        self.assertNotIn("extarticle", tex)
        self.assertNotIn("%%", tex)                  # every placeholder, and its note, gone
        # an exercise is in the box that goes on over pages when it is
        # taller than one, at this size too -- and not a step larger
        self.assertIn("EXERCISES ON PAPER", tex)
        self.assertIn("\\par\\medskip\\expaperexercise{{\\sffamily\\bfseries\\footnotesize"
                      "\\color{accent}Fill the blanks}", tex)
        self.assertNotIn("\\large {\\sffamily", tex)
        self.assertNotIn("\\begin{minipage}{\\dimexpr\\linewidth-1.6em\\relax}", tex)

    def test_a_large_size_is_extarticle_with_everything_grown(self):
        md = (document({"fill-blanks": SAMPLES["fill-blanks"]})
              + "\n\n## کتاب | ketâb | a book\n\n| a | b | c | d | e | f |\n|---|---|---|---|---|---|\n"
                "| 1 | 2 | 3 | 4 | 5 | 6 |\n")
        for size, margin, voce, rule in ((14, "2.2cm", "\\fontsize{48}{56}", "0.5pt"),
                                         (17, "2.0cm", "\\fontsize{59}{68}", "0.6pt"),
                                         (20, "1.8cm", "\\fontsize{69}{80}", "0.7pt")):
            tex = paper(md, font_size=size)
            self.assertIn("\\documentclass[%dpt,a4paper]{extarticle}" % size, tex)
            # a TeX without extsizes stops on a sentence saying so
            self.assertIn("\\IfFileExists{extarticle.cls}{}{\\errmessage{Large print needs "
                          "the TeX package extsizes", tex)
            self.assertIn("left=%s,right=%s" % (margin, margin), tex)
            self.assertIn(voce, tex)                 # the one absolute size, scaled
            self.assertIn("\\rule{5em}{%s}" % rule, tex)
            self.assertIn("\\setlength{\\fboxrule}{%s}" % rule, tex)
            # an exercise a step larger, in the box that may go on over pages
            self.assertIn("\\expaperexercise{\\large {\\sffamily\\bfseries\\footnotesize"
                          "\\color{accent}Fill the blanks}", tex)
            self.assertIn("\\newcommand\\expaperexercise", tex)
            # a table too wide for the line is scaled to it
            self.assertIn("\\exlexfit{\\begin{tabular}", tex)
            self.assertIn("\\end{tabular}}\n\\end{center}", tex)
            self.assertNotIn("%%", tex)

    def test_a_lemma_heads_column_fits_in_large_print(self):
        # the reading, transliteration and meaning beside the headword are
        # fitted to their column in large print (\\exlexfitvoce); at the
        # normal size the template's lines are exactly what they were
        md = "---\ntitle: L\ntarget: de\n---\n\n## Haus | haʊ̯s | house\n\nText.\n"
        tex = paper(md)
        self.assertIn("\\else{\\small\\tlfont #2}\\\\[0.2ex]\\fi\n"
                      "      {\\large\\itshape\\color{accent}\\trfont #3}\\\\[0.2ex]\n"
                      "      {\\footnotesize\\color{graytx}#4}}%", tex)
        self.assertNotIn("exlexfit", tex)
        for size in (14, 17, 20):
            tex = paper(md + ":::exercise yes-no\nprompt: Q?\n- [Ja]{tl} => yes\n:::\n", font_size=size)
            self.assertIn("\\else\\exlexfitvoce{\\small\\tlfont #2}\\\\[0.2ex]\\fi\n"
                          "      \\exlexfitvoce{\\large\\itshape\\color{accent}\\trfont #3}\\\\[0.2ex]\n"
                          "      \\exlexfitvoce{\\footnotesize\\color{graytx}#4}}%", tex)
            # defined before the template's \\voce, and once, exercises or not
            self.assertLess(tex.index("\\newcommand\\exlexfitpar"), tex.index("\\newcommand{\\voce}"))
            self.assertEqual(1, tex.count("\\newcommand\\exlexfitpar"))
            self.assertIn("\\newcommand\\expapercell", tex)

    def test_a_vertical_column_is_never_longer_than_the_page_in_large_print(self):
        # its height is in ems, which grow with the print: at 20 pt a
        # height=40 column that fits the page at 11 pt ran off the paper
        md = "---\ntitle: Tate\ntarget: ja\n---\n\n[\n縦書き\n]{tl vertical height=40}\n"
        self.assertIn("\\tlvertical{40}{", paper(md))
        self.assertIn("\\begin{minipage}{#1em}%", paper(md))
        for size in (14, 17, 20):
            self.assertIn("\\begin{minipage}{\\dimexpr\\ifdim#1em>\\dimexpr\\textheight-4\\baselineskip"
                          "\\relax\\textheight-4\\baselineskip\\else#1em\\fi\\relax}%", paper(md, font_size=size))

    def test_only_the_four_sizes_are_taken(self):
        md = document({"yes-no": SAMPLES["yes-no"]})
        for size in (10, 12, 13, 21):
            with self.assertRaises(ValueError):
                paper(md, font_size=size)

    def test_a_run_kept_whole_is_no_longer_than_a_line_of_its_size_allows(self):
        # a run of up to four words is one box (\\pe) at 11 pt; a line of
        # large print holds fewer words, by the ratio of the sizes, and four
        # Italian words in one box ran off the paper at 20 pt
        md = "---\ntitle: T\ntarget: it\n---\n\nOrder [un caffè, per favore]{tl}, or [un caffè]{tl}.\n"
        self.assertIn("\\pe{un caffè, per favore}", paper(md))
        for size in (14, 17, 20):
            tex = paper(md, font_size=size)
            self.assertIn("\\pel{un caffè, per favore}", tex, size)
            self.assertIn("\\pe{un caffè}", tex, size)
        # the page asks at its own size, whatever PDF the thread built last
        self.assertFalse(texgen.run_is_long("un caffè, per favore"))
        # characters, for a language written without spaces
        md = "---\ntitle: T\ntarget: zh\n---\n\nSay 我有两个好哥哥 twice.\n"
        self.assertIn("\\pe{我有两个好哥哥}", paper(md))
        self.assertIn("\\pel{我有两个好哥哥}", paper(md, font_size=14))

    def test_a_blank_between_characters_is_a_place_a_line_can_end(self):
        # Chinese and Japanese break a line between any two characters: a
        # blank is one more, and a sentence of short runs and blanks was one
        # unbreakable line (115 pt past the frame at 20 pt)
        md = document({"fill-blanks": "prompt: Fill.\ntext: 我有两[[1]]哥哥，还有一[[2]]猫。\n- [1] 个\n- [2] 只"})
        md = md.replace("target: fa", "target: zh")
        self.assertIn("\\pe{我有两}\\allowbreak\\rule{5em}{0.4pt}\\allowbreak \\pe{哥哥，还有一}"
                      "\\allowbreak\\rule{5em}{0.4pt}\\allowbreak \\pe{猫。}", paper(md))
        self.assertIn("\\pe{我有两}\\allowbreak\\rule{5em}{0.7pt}\\allowbreak \\pel{哥哥，还有一}",
                      paper(md, font_size=20))
        # a blank beside a space has its break already, and one inside a
        # word of a spaced language is part of the word
        tex = paper(document({"fill-blanks": "prompt: Fill.\ntext: I [[a]] books, un[[b]]able.\n"
                                             "- [a] read\n- [b] believ"}).replace("target: fa", "target: en"))
        self.assertIn("I \\rule{5em}{0.4pt} books, un\\rule{5em}{0.4pt}able.", tex)
        self.assertNotIn("\\allowbreak", tex[tex.index("\\begin{document}"):])

    def test_a_blank_is_no_place_to_end_a_line_beside_a_closing_or_opening_mark(self):
        # a line of Chinese or Japanese never begins with 。，？ ）」, the small
        # kana, ー or 々, nor ends with （「 or a currency sign; a break written
        # beside a blank set "？" alone at the head of a line, at every size.
        # The break is on the blank's other side instead, and it is looked
        # for past the LaTeX the sentence is in (\\pe{，对吗}, \\textbf{...})
        for size, rule in ((11, "\\rule{5em}{0.4pt}"), (20, "\\rule{5em}{0.7pt}")):
            md = document({"fill-blanks": "prompt: Fill.\ntext: 他说[[1]]，对吗[[2]]？（[[3]]）"
                                          "价格是¥[[4]]元。**[[5]]**。\n- [1] 好\n- [2] 吗\n- [3] 对\n"
                                          "- [4] 五\n- [5] 好"}).replace("target: fa", "target: zh")
            self.assertIn("\\pe{他说}\\allowbreak" + rule + "\\pe{，对吗}\\allowbreak" + rule
                          + "\\pe{？（}" + rule + "\\pe{）价格是}¥" + rule + "\\allowbreak \\pe{元。}"
                          "\\textbf{\\allowbreak" + rule + "}\\pe{。}", paper(md, font_size=size))
            md = document({"fill-blanks": "prompt: Fill.\ntext: 「[[1]]」とコーヒ[[2]]ーを、人[[3]]々と[[4]]ょうも。\n"
                                          "- [1] は\n- [2] イ\n- [3] 人\n- [4] き"}).replace("target: fa", "target: ja")
            tex = paper(md, font_size=size)
            self.assertIn("\\pe{「}" + rule + "\\pe", tex)
            self.assertIn("とコーヒ}\\allowbreak" + rule + "\\pe{ーを、人}\\allowbreak" + rule
                          + "\\pe{々と}\\allowbreak" + rule + "\\pe{ょうも。}", tex)

    def test_large_print_prefers_a_loose_line_to_one_into_the_margin(self):
        md = document({"yes-no": SAMPLES["yes-no"]})
        self.assertNotIn("\\emergencystretch=3em", paper(md))
        for size in (14, 17, 20):
            tex = paper(md, font_size=size)
            # after the template's own, which it overrides
            self.assertLess(tex.index("\\tolerance=2000 \\emergencystretch=2.2em"),
                            tex.index("\\emergencystretch=3em"), size)


class LatinInTheTargetTex(unittest.TestCase):
    """Latin words inside the target's own text: in a face that has their
    letters (\\tllatin), next to each other one island in right-to-left
    text, a space after it (tests/test_studio_pdf_glyphs.py builds them)."""

    def setUp(self):
        self.addCleanup(texgen.set_target, None)

    def test_right_to_left_text(self):
        texgen.set_target("ar")
        self.assertEqual("أرسلت \\beginL {\\tllatin PDF}\\endL{} إلى \\beginL {\\tllatin Good} "
                         "{\\tllatin morning} 17\\endL{} سنة \\newline \\beginL {\\tllatin e-mail}،\\endL{} "
                         "ثم \\beginL 2024\\endL{}",
                         texgen.rtl_fragment("أرسلت PDF إلى Good morning 17 سنة ⏎ e-mail، ثم 2024"))

    def test_left_to_right_text(self):
        texgen.set_target("hi")
        self.assertEqual("मैंने {\\tllatin PDF} भेजा, 100\\% {\\tllatin café}",
                         texgen.ltr_fragment("मैंने PDF भेजा, 100% café"))
        # a Latin-script target's run is Latin all through, as it was
        texgen.set_target("it")
        self.assertEqual("un caffè, 100\\%", texgen.ltr_fragment("un caffè, 100%"))

    def test_the_macro_only_where_it_is_used(self):
        with_latin = paper("---\ntitle: T\ntarget: ar\n---\n\nA [ملف PDF]{tl}.\n")
        self.assertIn("{\\tlfont\\beginR ملف \\beginL {\\tllatin PDF}\\endL{}\\endR}", with_latin)
        self.assertIn("\\protected\\def\\tllatin{\\iffontchar\\font`A \\else", with_latin)
        # after the faces it wraps, before anything sets text in them
        self.assertLess(with_latin.index("\\newfontfamily\\tlfont"), with_latin.index("\\let\\exlex@tlfont\\tlfont"))
        self.assertLess(with_latin.index("\\let\\exlex@tlfont\\tlfont"), with_latin.index("\\begin{document}"))
        self.assertNotIn("tllatin", paper("---\ntitle: T\ntarget: ar\n---\n\nA [ملف]{tl}.\n"))
        self.assertNotIn("tllatin", paper("---\ntitle: T\ntarget: it\n---\n\nA [bello PDF]{tl}.\n"))


class NastaliqBlockTex(unittest.TestCase):

    def test_a_nastaliq_block_without_a_tint(self):
        # the block's first word was read into \\selectfont's name, and the
        # build stopped on an undefined control sequence
        tex = paper("---\ntitle: T\ntarget: fa\n---\n\n[این یک شعر است]{tl font=nastaliq}\n")
        self.assertIn("\\begin{fapar}\\tlalt\\linespread{1.8}\\selectfont این یک شعر است\\end{fapar}", tex)
        self.assertIn("\\begin{fapar}این یک شعر است\\end{fapar}",
                      paper("---\ntitle: T\ntarget: fa\n---\n\n[این یک شعر است]{tl}\n"))


class BlackAndWhiteTests(unittest.TestCase):
    """The build's black and white: every colour black, every tint white,
    and nothing written inline in a colour."""

    MD = ("---\ntitle: Colours\ntarget: fa\n---\n\n"
          "A [کتاب]{teal} mark, a [قلم]{#8E2B34} one, a [تند]{#AA3377 translit:tond} one.\n\n"
          "## [آهسته]{#1E7A3C} | âheste | a coloured lemma\n\n"
          "> A box.\n\n[متن]{tl bg=quote}\n\nA tinted [واژه]{tl bg=sand} in a line.\n\n"
          ":::exercise single-choice\nprompt: Broken.\n- [x] one\n- [x] two\n:::\n")

    def test_colour_is_what_it_was(self):
        tex = paper(self.MD)
        for colour in ("\\textcolor{fateal}", "\\textcolor[HTML]{8E2B34}", "\\textcolor[HTML]{AA3377}",
                       "\\color[HTML]{1E7A3C}", "\\color{red}Exercise needs attention",
                       "\\colorbox{boxbg}", "\\colorbox{rtlbgquote}", "\\colorbox{rtlbgsand}"):
            self.assertIn(colour, tex)
        self.assertNotIn("\\definecolor{accent}{HTML}{000000}", tex)

    def test_black_and_white_writes_no_colour_at_all(self):
        tex = paper(self.MD, mono=True)
        # every ink of the template redefined black, every tint white
        for ink in ("accent", "accentlt", "rulec", "graytx", "linkc", "faungram", "faok",
                    "facrimson", "faindigo", "fateal", "faviolet", "faamber"):
            self.assertIn("\\definecolor{%s}{HTML}{000000}" % ink, tex)
        for tint in ("boxbg", "rtlbgquote", "rtlbgsand", "rtlbgrose", "rtlbgsage", "rtlbglilac"):
            self.assertIn("\\definecolor{%s}{HTML}{FFFFFF}" % tint, tex)
        self.assertIn("\\hypersetup{allcolors=linkc}", tex)
        # and after the colour definitions they replace
        self.assertLess(tex.index("\\definecolor{rtlbglilac}{HTML}{EFEAF6}"),
                        tex.index("\\definecolor{rtlbglilac}{HTML}{FFFFFF}"))
        # nothing written inline in a colour: the text stays, the colour goes
        body = tex[tex.index("\\begin{document}"):]
        self.assertNotRegex(body, r"\\textcolor|\\color\[|\\color\{(red|fa)")
        self.assertIn("\\pe{کتاب}", tex)
        self.assertIn("{\\bfseries Exercise needs attention in the Markdown source.}", tex)
        # a tinted panel keeps what set it off: a thin black frame on white
        self.assertNotIn("\\colorbox{", tex)
        self.assertIn("\\fcolorbox{rulec}{white}{\\begin{minipage}{0.93\\linewidth}", tex)
        self.assertIn("\\fcolorbox{rulec}{white}{\\begin{minipage}{\\dimexpr\\linewidth-1.6em\\relax}"
                      "\\vspace{0.6ex}{\\tlfont", tex)
        self.assertIn("\\fcolorbox{rulec}{white}{{\\tlfont\\beginR واژه\\endR}}", tex)
        self.assertNotIn("%%", tex)

    def test_both_options_together(self):
        tex = paper(self.MD, font_size=20, mono=True)
        self.assertIn("\\documentclass[20pt,a4paper]{extarticle}", tex)
        self.assertIn("\\setlength{\\fboxrule}{0.7pt}", tex)
        self.assertIn("\\definecolor{boxbg}{HTML}{FFFFFF}", tex)


class BuildOptionRouteTests(unittest.TestCase):
    """POST /api/docs/<id>/build takes the print options, checks them, and
    hands them to build_pdf -- which is replaced here: the real build is
    tests/test_studio_pdf_print.py's."""

    class Fake:
        def __init__(self, body):
            self.body, self.sent = body, None

        def _json_body(self):
            return self.body

        def send_json(self, payload, status=200):
            self.sent = (status, payload)

    def setUp(self):
        self.calls = []
        real = studio_server.build_pdf

        def fake(doc_id, scale, size=11, mono=False):
            self.calls.append((doc_id, scale, size, mono))
            return {"status": "ok", "size": size, "mono": mono}
        studio_server.build_pdf = fake
        self.addCleanup(setattr, studio_server, "build_pdf", real)

    def build(self, body):
        h = self.Fake(body)
        studio_server.api_build(h, "doc-1")
        return h.sent

    def test_absent_options_are_the_normal_build(self):
        self.assertEqual(200, self.build({"scale": 1.52})[0])
        self.assertEqual(("doc-1", 1.52, 11, False), self.calls[-1])

    def test_the_options_reach_the_build(self):
        for size in (11, 14, 17, 20, 17.0):
            self.assertEqual(200, self.build({"scale": 1.2, "size": size, "mono": True})[0])
            self.assertEqual(("doc-1", 1.2, int(size), True), self.calls[-1])
            self.assertIs(type(self.calls[-1][2]), int)

    def test_anything_else_is_refused_before_a_build(self):
        for body in ({"size": 12}, {"size": "14"}, {"size": True}, {"size": 14.5},
                     {"size": float("nan")}, {"mono": "yes"}, {"mono": 1}, {"size": 14, "mono": "false"}):
            status, answer = self.build(body)
            self.assertEqual(400, status, body)
            self.assertIn("error", answer)
        self.assertEqual([], self.calls)


class PaperLayoutTests(unittest.TestCase):
    """The printed layouts of the exercises a student writes on: matching,
    construct-the-sentence, true/false and yes/no.  Only the PDF: the page's
    markup of the same exercises is pinned to what it was."""

    def exercise(self, subtype, body, target="fa", **options):
        md = ("---\ntitle: Paper\ntarget: %s\n---\n\n:::exercise %s\nprompt: Do it.\n%s\n:::\n"
              % (target, subtype, body))
        tex = paper(md, **options)
        return tex, tex[tex.index("\\begin{document}"):]

    def test_every_matching_entry_is_framed_and_the_right_column_still_shuffled(self):
        tex, body = self.exercise("match-translations",
                                  "- [سلام]{tl} => hello\n- [خداحافظ]{tl} => goodbye\n"
                                  "- ![snow](images/snow.png) => [برف]{tl}")
        self.assertIn("\\newcommand\\expaperpair", tex)
        self.assertNotIn("p{0.46\\linewidth}", body)
        # an RTL entry flush right in one right-to-left segment, a Latin one
        # flush left; the right column rotated by one, as it always was; the
        # \\hspace{0pt} lets TeX hyphenate an entry's first word
        self.assertIn("\\expaperpair{\\raggedleft\\noindent\\hspace{0pt}\\beginR {\\tlfont\\beginR سلام\\endR}\\endR}"
                      "{\\raggedright\\noindent\\hspace{0pt}goodbye}", body)
        self.assertIn("\\expaperpair{\\raggedleft\\noindent\\hspace{0pt}\\beginR {\\tlfont\\beginR خداحافظ\\endR}\\endR}"
                      "{\\raggedleft\\noindent\\hspace{0pt}\\beginR {\\tlfont\\beginR برف\\endR}\\endR}", body)
        self.assertIn("\\expaperpair{\\raggedright\\noindent\\hspace{0pt}\\includegraphics[width=0.60\\linewidth,"
                      "height=0.12\\textheight,keepaspectratio]{images/snow.png}}"
                      "{\\raggedright\\noindent\\hspace{0pt}hello}", body)
        self.assertEqual(3, body.count("\\expaperpair{"))
        # a target run in an entry may break (\\pel, not the one box of a \\pe)
        for subtype in ("match-opposites", "match-definitions"):
            self.assertIn("\\expaperpair{\\raggedright\\noindent\\hspace{0pt}\\pel{hot}}"
                          "{\\raggedright\\noindent\\hspace{0pt}\\pel{cold}}",
                          self.exercise(subtype, "- [hot]{tl} => [cold]{tl}", target="en")[1])

    def test_a_cell_asked_to_run_left_to_right_does(self):
        _tex, body = self.exercise("match-translations",
                                   "content-direction: ltr\n- [سلام]{tl} => hello")
        self.assertIn("\\expaperpair{\\raggedright\\noindent\\hspace{0pt}{\\tlfont\\beginR سلام\\endR}}", body)

    def test_true_false_marks_have_a_column_of_their_own(self):
        tex, body = self.exercise("true-false",
                                  "- [پدر لیلا تکنولوژی را دوست دارد.]{tl} => false\n"
                                  "- An English statement. => true")
        self.assertIn("\\newcommand\\expaperbool", tex)
        self.assertNotIn("\\hfill", body)
        self.assertIn("\\expaperboolmarks{True / False}"
                      "\\expaperbool{\\raggedleft\\noindent\\hspace{0pt}\\beginR {\\tlfont\\beginR پدر لیلا تکنولوژی را "
                      "دوست دارد.\\endR}\\endR}{True / False}\n"
                      "\\expaperbool{\\raggedright\\noindent\\hspace{0pt}An English statement.}{True / False}", body)
        _tex, body = self.exercise("yes-no", "- Is it? => yes", target="en")
        self.assertIn("\\expaperboolmarks{Yes / No}\\expaperbool{\\raggedright\\noindent\\hspace{0pt}Is it?}{Yes / No}",
                      body)
        # the column is one box that nothing breaks, set at one width for all
        self.assertIn("\\makebox[\\expapermarks][r]{#2}", tex)

    def test_no_entry_or_statement_crosses_its_column(self):
        # each is set by \\exlexfitpar, scaled down only when a word in it
        # cannot break; defined once, with the exercises' own macros
        rows = "- [hot]{tl} => [cold]{tl}"
        for size in (11, 20):
            tex, _body = self.exercise("match-opposites", rows, target="en", font_size=size)
            self.assertEqual(1, tex.count("\\newcommand\\exlexfitpar"), size)
            self.assertIn("\\newcommand\\expapercell[1]{%\n  \\exlexfitpar{", tex)
            self.assertIn("\\par\\noindent\\exlexfitpar{\\dimexpr\\linewidth-\\expapermarks\\relax}{#1}", tex)
            self.assertIn("\\XeTeXinterchartoks\\exlexfitparslash 0 = {\\allowbreak}", tex)
        # a document with no such exercise has none of it at the normal size
        self.assertNotIn("exlexfitpar", paper("---\ntitle: Paper\ntarget: en\n---\n\nJust text.\n"))

    def test_construct_the_sentence_is_a_row_of_chunks_over_lines_to_write_on(self):
        rows = "- [1] [من]{tl}\n- [2] [هر روز]{tl}\n- [3] [قهوه می نوشم]{tl}"
        tex, body = self.exercise("construct-sentence", rows)
        self.assertIn("\\newcommand\\expaperwritelines", tex)
        # shuffled as before (the first chunk last), flowing right to left
        self.assertIn("\\expaperchunks{r}{\\raggedleft\\noindent\\beginR "
                      "\\expaperchunk{{\\tlfont\\beginR هر روز\\endR}}\\expaperchunkgap "
                      "\\expaperchunk{{\\tlfont\\beginR قهوه می نوشم\\endR}}\\expaperchunkgap "
                      "\\expaperchunk{{\\tlfont\\beginR من\\endR}}\\endR\\par}\\expaperwritelines", body)
        self.assertNotIn("\\begin{itemize}", body)
        # every chunk is in the .tex once: its width is added up as it is set
        self.assertEqual(1, body.count("قهوه می نوشم"))
        # the answer's direction, when it is given, over the target's
        _tex, body = self.exercise("construct-sentence", "answer-direction: ltr\n" + rows)
        self.assertIn("\\expaperchunks{l}{\\raggedright\\noindent \\expaperchunk{", body)
        _tex, body = self.exercise("construct-sentence", "- [1] [I]{tl}\n- [2] [drink]{tl}", target="en")
        self.assertIn("\\expaperchunks{l}{\\raggedright\\noindent \\expaperchunk{\\pe{drink}}"
                      "\\expaperchunkgap \\expaperchunk{\\pe{I}}\\par}\\expaperwritelines", body)
        _tex, body = self.exercise("construct-sentence", "answer-direction: rtl\n- [1] [I]{tl}\n- [2] [drink]{tl}",
                                   target="en")
        self.assertIn("\\expaperchunks{r}{\\raggedleft\\noindent\\beginR \\expaperchunk{\\pe{drink}}", body)
        # N = ceil(3W / 2L), in TeX's integers, at least one line
        self.assertIn("\\global\\expaperlinecount=\\numexpr(3*(\\expapersentence/16))/(2*(\\linewidth/16))\\relax",
                      tex)
        self.assertIn("\\ifnum\\expaperlinecount<1 \\global\\expaperlinecount=1 \\fi", tex)
        self.assertIn("\\hrule height 0.4pt", tex)
        self.assertIn("\\hrule height 0.6pt", self.exercise("construct-sentence", rows, font_size=17)[0])

    def test_order_the_sentences_is_left_as_it_was(self):
        _tex, body = self.exercise("order-sentences", "- [1] one\n- [2] two", target="en")
        self.assertIn("\\begin{itemize}\\item two\\item one\\end{itemize}", body)
        # in the box every exercise has, and nothing else of the paper's
        self.assertNotIn("\\expaper", body.replace("\\expaperexercise{", "", 1))

    def test_the_web_rendering_is_untouched(self):
        # the page's own markup for the same four exercises (htmlgen)
        html = htmlgen.render_document(document({
            "match-translations": SAMPLES["match-translations"], "true-false": SAMPLES["true-false"],
            "construct-sentence": SAMPLES["construct-sentence"]}))["html"]
        self.assertIn('<div class="ex-pairs">', html)
        self.assertIn('class="ex-sequence ex-sequence-inline" dir="rtl"', html)
        self.assertIn('<div class="ex-choice-group" data-choice="single"><div class="ex-question">', html)
        self.assertNotIn("expaper", html)


# ------------------------------------------------------------ follow-up questions (a0.5.4)

FRONT = "---\ntitle: D\ntarget: it\n---\n\n"
CHAIN = """:::exercise follow-up
prompt: Read, then answer.
explanation-correct: Fine.
::::exercise single-choice
prompt: Where?
- [ ] home
- [x] station
::::
::::exercise true-false
- Late. => true
::::
::::exercise flashcard
card-type: vocab
target: [binario]{tl}
meaning: platform
::::
:::
"""
AFTER = ":::exercise single-choice\nprompt: After.\n- [x] a\n- [ ] b\n:::\n"
TWO = "::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n"


class FollowUpDialectTests(unittest.TestCase):
    """The fourteenth exercise type: a chain of exercises answered in order, each step one fence deeper."""

    def parse(self, src):
        return mdparser.parse(FRONT + src)[1]

    def errors(self, src):
        block = self.parse(src)[0]
        return block["errors"], [s["errors"] for s in block.get("steps", [])]

    def test_a_follow_up_is_a_chain_of_the_exercises_written_inside_it(self):
        chain, after = self.parse(CHAIN + "\n" + AFTER)
        self.assertEqual([], chain["errors"])
        self.assertEqual(("follow-up", "chain"), (chain["subtype"], chain["primitive"]))
        self.assertEqual(["single-choice", "true-false", "flashcard"], [s["subtype"] for s in chain["steps"]])
        self.assertEqual([[], [], []], [s["errors"] for s in chain["steps"]])
        self.assertEqual("Read, then answer.", chain["fields"]["prompt"])
        # the exercise after it is an exercise of its own, whole
        self.assertEqual(("single-choice", []), (after["subtype"], after["errors"]))
        self.assertNotIn("steps", after)

    def test_a_step_reads_as_the_exercise_it_would_be_on_its_own(self):
        step = self.parse(CHAIN)[0]["steps"][0]
        self.assertEqual(":::exercise single-choice\nprompt: Where?\n- [ ] home\n- [x] station\n:::", step["source"])
        # the same exercise written at the top level is the same block
        alone = self.parse(step["source"])[0]
        self.assertEqual((alone["fields"], alone["items"]), (step["fields"], step["items"]))

    def test_the_steps_lines_are_the_documents_lines(self):
        chain = self.parse(CHAIN)[0]
        # FRONT has 5 lines (0-4); the follow-up opens on line 5 and closes on 21
        self.assertEqual((5, 21), (chain["_line"], chain["_end_line"]))
        self.assertEqual([(8, 12), (13, 15), (16, 20)], [(s["_line"], s["_end_line"]) for s in chain["steps"]])

    def test_what_a_follow_up_refuses_it_says(self):
        self.assertEqual((["follow-up needs at least two steps"], [[]]),
                         self.errors(":::exercise follow-up\n::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n:::"))
        self.assertEqual((["follow-up needs at least two steps"], []), self.errors(":::exercise follow-up\n:::"))
        self.assertEqual((["follow-up has no answer rows; write its steps"], [[], []]),
                         self.errors(":::exercise follow-up\n- a row\n" + TWO + ":::"))
        self.assertEqual((["a follow-up cannot hold a follow-up"], [["follow-up needs at least two steps"], []]),
                         self.errors(":::exercise follow-up\n::::exercise follow-up\n::::\n"
                                     "::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n:::"))

    def test_a_step_that_is_wrong_is_named_by_its_number(self):
        errors, steps = self.errors(":::exercise follow-up\n::::exercise single-choice\n- [ ] a\n- [ ] b\n::::\n"
                                    "::::exercise nonsense\n- [x] a\n::::\n:::")
        self.assertEqual(["step 1: single-choice exercise needs exactly one [x] answer",
                          "step 2: unknown exercise type: nonsense"], errors)
        self.assertEqual([["single-choice exercise needs exactly one [x] answer"], ["unknown exercise type: nonsense"]], steps)

    def test_a_step_never_closed_does_not_swallow_the_follow_ups_end(self):
        errors, steps = self.errors(":::exercise follow-up\n::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n"
                                    "::::exercise single-choice\n- [x] a\n- [ ] b\n:::")
        self.assertEqual(["step 2: step is missing its closing :::: line"], errors)
        self.assertEqual([[], ["step is missing its closing :::: line"]], steps)
        # …and what comes after the follow-up is still read
        blocks = self.parse(":::exercise follow-up\n::::exercise single-choice\n- [x] a\n- [ ] b\n:::\n\n" + AFTER)
        self.assertEqual(["exercise", "exercise"], [b["type"] for b in blocks])
        self.assertEqual([], blocks[1]["errors"])

    def test_a_drawing_in_a_step_is_one_colon_more(self):
        src = (":::exercise follow-up\n::::exercise single-choice\nprompt: |\n  Which?\n  :::::latex chemistry {width=40}\n"
               "  \\ce{H2O}\n  :::::\n- [x] a\n- [ ] b\n::::\n::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n:::")
        chain = self.parse(src)[0]
        self.assertEqual(([], [[], []]), (chain["errors"], [s["errors"] for s in chain["steps"]]))
        # the step is the exercise as it reads at the top level: its drawing is the four-colon one
        self.assertIn("  ::::latex chemistry {width=40}\n  \\ce{H2O}\n  ::::\n", chain["steps"][0]["source"])
        html = htmlgen.render_document(FRONT + src)["html"]
        self.assertIn('data-latex-src="\\ce{H2O}"', html)

    def test_a_drawing_written_as_on_its_own_does_not_end_the_step(self):
        # four colons are what a drawing is taught everywhere else; its closing line is the step's own, and used to end
        # the step at the drawing ("unrecognized line: ::::", "choice exercise has no alternatives")
        src = (":::exercise follow-up\n::::exercise single-choice\nprompt: |\n  Which?\n  ::::latex chemistry {width=40}\n"
               "  \\ce{H2O}\n  ::::\n- [x] a\n- [ ] b\n::::\n::::exercise true-false\nprompt: |\n  Then?\n  :::::latex\n"
               "  \\textbf{x}\n  :::::\n- yes => true\n::::\n:::\n\n" + AFTER)
        chain, after = self.parse(src)
        self.assertEqual(([], [[], []]), (chain["errors"], [s["errors"] for s in chain["steps"]]))
        self.assertEqual(["single-choice", "true-false"], [s["subtype"] for s in chain["steps"]])
        # each step is the exercise as it reads on its own, whichever way its drawing was written
        for step in chain["steps"]:
            self.assertEqual(1, step["source"].count("::::latex"))
            self.assertNotIn(":::::", step["source"])
        self.assertIn("  ::::latex chemistry {width=40}\n  \\ce{H2O}\n  ::::\n", chain["steps"][0]["source"])
        self.assertEqual([], after["errors"])
        html = htmlgen.render_document(FRONT + src)["html"]
        self.assertIn('data-latex-src="\\ce{H2O}"', html)
        self.assertIn('data-latex-src="\\textbf{x}"', html)
        self.assertNotIn("ex-invalid", html)

    def test_a_drawing_never_closed_in_a_step_is_refused_and_ends_with_the_follow_up(self):
        # its closing line is taken for the drawing's, so the step swallows the one after it: the follow-up says it
        # has fewer than two steps, and what comes after the follow-up is still an exercise of its own
        md = (":::exercise follow-up\n::::exercise single-choice\nprompt: |\n  ::::latex\n  \\x\n- [x] a\n- [ ] b\n::::\n"
              "::::exercise true-false\n- yes => true\n::::\n:::\n\n" + AFTER)
        chain, after = self.parse(md)
        self.assertTrue(chain["errors"])
        self.assertEqual([], after["errors"])
        self.assertEqual("single-choice", after["subtype"])

    def test_a_drawing_in_an_exercise_knows_its_place_in_the_document(self):
        # the editor's pencil rewrites the lines the drawing is on: it used to be told a number counted from the start
        # of the prompt it sits in, and rewrote the front matter of the page
        plain = ":::exercise single-choice\nprompt: |\n\n  Which?\n  ::::latex\n  \\x\n  ::::\n- [x] a\n- [ ] b\n:::\n"
        deep = (":::exercise follow-up\n::::exercise single-choice\nprompt: |\n  Which?\n  :::::latex\n  \\x\n  :::::\n- [x] a\n"
                "- [ ] b\n::::\n::::exercise true-false\n- yes => true\n::::\n:::\n")
        for src, fence in ((plain, "::::latex"), (deep, ":::::latex")):
            md = FRONT + "Intro.\n\n" + src
            lines = md.split("\n")
            at = next(i for i, l in enumerate(lines) if l.strip().startswith(fence))
            html = htmlgen.render_document(md)["html"]
            self.assertEqual([str(at)], re.findall(r'data-latex-src="[^"]*"[^>]*data-src-line="(\d+)"', html), fence)

    def test_a_block_in_a_prompt_is_not_given_a_line_it_has_not(self):
        md = FRONT + ":::exercise single-choice\nprompt: |\n  - one\n  - two\n- [x] a\n- [ ] b\n:::\n"
        html = htmlgen.render_document(md)["html"]
        prompt = html[html.index('class="ex-prompt"'):html.index('class="ex-body"')]
        self.assertNotIn("data-src-line", prompt)

    def test_the_page_draws_one_step_to_a_wrapper_and_numbers_every_exercise(self):
        out = htmlgen.render_document(FRONT + CHAIN + "\n" + AFTER)
        html = out["html"]
        self.assertEqual(1, html.count('class="exercise ex-chain"'))
        self.assertIn('data-subtype="follow-up" data-primitive="chain" data-scored="0"', html)
        self.assertIn('data-steps="3" data-step="1"', html)
        self.assertEqual(['1', '2', '3', '4', '5'], re.findall(r'data-exercise="(\d+)"', html))
        self.assertEqual(['scored', 'scored', 'card'], re.findall(r'class="ex-step" data-step="\d" data-kind="(\w+)"', html))
        self.assertIn(">Step 1 of 3<", html)
        self.assertEqual(3, html.count('class="btn ex-step-check"') + html.count('class="btn ex-step-show"'))
        self.assertIn("Follow-up questions", html)
        # the chain is not scored, its two scored steps and the one after it are
        self.assertEqual(3, html.count('data-scored="1"'))

    def test_a_follow_up_with_a_mistake_is_drawn_as_the_error_it_is(self):
        html = htmlgen.render_document(FRONT + ":::exercise follow-up\n" + TWO[:TWO.index("::::exercise", 5)] + ":::")["html"]
        self.assertIn("ex-invalid", html)
        self.assertNotIn("ex-chain", html)

    def test_nesting_an_exercise_is_what_reading_a_step_undoes(self):
        alone = (":::exercise single-choice\nprompt: |\n  Which?\n  ::::latex chemistry\n  \\ce{H2O}\n  ::::\n"
                 "- [x] a\n- [ ] b\n:::")
        nested = mdparser.nest_step(alone)
        self.assertEqual(["::::exercise single-choice", "  :::::latex chemistry", "  :::::", "::::"],
                         [l for l in nested.split("\n") if l.lstrip().startswith("::")])
        self.assertEqual(alone, "\n".join(mdparser._denest(l) for l in nested.split("\n")))
        # a chain made of two nested exercises reads back as the same two
        chain = self.parse(":::exercise follow-up\n" + nested + "\n" + mdparser.nest_step(AFTER) + "\n:::")[0]
        self.assertEqual(([], [alone, AFTER.strip()]), (chain["errors"], [s["source"] for s in chain["steps"]]))

    def test_the_decks_rule_is_one_exercise_the_pages_is_every_step(self):
        import decks
        _fm, blocks = mdparser.parse(FRONT + CHAIN)
        self.assertEqual(["follow-up"], [b["subtype"] for b in decks._walk(blocks, steps=False)])
        self.assertEqual(["follow-up", "single-choice", "true-false", "flashcard"], [b["subtype"] for b in decks._walk(blocks)])

    def test_a_jolly_card_in_a_step_is_a_card_for_the_word_scan_too(self):
        # the lines a card draws as blocks are the document's own lines, steps or not
        card = "card-type: jolly\nfront-primary: |\n  one\n\n  two\nback-primary: x\n"
        alone = mdparser.card_spans(FRONT + ":::exercise flashcard\n" + card + ":::\n")
        chain = mdparser.card_spans(FRONT + ":::exercise follow-up\n::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n"
                                    "::::exercise flashcard\n" + card + "::::\n:::\n")
        self.assertEqual([(8, 0), (9, 0), (10, 0)], alone)
        self.assertEqual([(13, 0), (14, 0), (15, 0)], chain)

    def test_the_paper_has_a_frame_for_each_step(self):
        fm, blocks = mdparser.parse(FRONT + CHAIN)
        tex = texgen.generate(fm, blocks, colophon=False)
        body = tex[tex.index("\\begin{document}"):]
        self.assertEqual(3, body.count("\\expaperstep{"))
        self.assertEqual(1, body.count("\\expaperexercise{"))
        for n, label in ((1, "Choose one answer"), (2, "True / False"), (3, "Flashcard")):
            self.assertIn("%d.\\enspace %s" % (n, label), body)
        self.assertIn("\\expaperboolmarks{True / False}", body)          # a step keeps what its type puts on paper
        self.assertIn("\\expapercardsize{120}", body)                     # and a card its front and back
        self.assertEqual(1, body.count("\\begin{itemize}"))                # the choice's; the true/false is its own frame


if __name__ == "__main__":
    unittest.main()
