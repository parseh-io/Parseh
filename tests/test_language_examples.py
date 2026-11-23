#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The worked Example of every language's conventions (docs/lang/<code>.md, `## Example`: a0.4.2
brief 6.4, lane D2): a few chunks of the language in the shape an answer takes, which the region
prompts and the add page's prompt carry in place of a video from a shelf.

    python3 -m unittest tests/test_language_examples.py

WHAT IS HELD: that it is ONE block of JSON in the shape of an answer, in every state a prompt can be in
(a book or a video, the usual scheme or IPA, the short vowels asked for or not); that every `voc` line of
it is one the real checkers take, as a book's line and as a video's; that with IPA chosen it shows IPA and
never the usual scheme (a model imitates the example it is shown over the rule it was told: lane T found
this with a stand-in chatbot); that with the short vowels asked for it adds marks and nothing else; and
that a language whose example the owner cannot read says so in a note no prompt carries.

A language is tested once its file HAS an Example: the six of lane D2b are skipped, saying so, until
their files are merged, and the five of lane D2a are required.
"""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _p in ("youtube/lib", "lib"):
    sys.path.insert(0, os.path.join(ROOT, _p))
import check_annotations                                        # noqa: E402
import languages                                                # noqa: E402
import promptkit as K                                           # noqa: E402
import texparse                                                 # noqa: E402
import texwrite                                                 # noqa: E402

D2A = ("fa", "ar", "hi", "ja", "zh")
OWNER_READS = ("fa", "it", "en")
SURFACES = ("video-new", "book-new", "video-region", "book-region")
# a language whose Example has no sound that depends on the scheme (Turkish: its `tr` line is the stress, the same
# string in both): tests/test_example_per_scheme.py names it too and holds that nothing of the usual scheme is shown
SCHEME_FREE = ("tr",)
KEYS = {"fa", "kana", "tr", "voc", "en", "words"}
# WHAT ONLY THE USUAL SCHEME WRITES, by language: a sign of it that an IPA example must never carry and that
# the usual one does (so that the list cannot rot).  The six languages of lane D2b add theirs where their
# files are merged; a language with no entry is held to the other checks only.
USUAL_ONLY = {"fa": ("š", "č", "ž", "ā"),
              "ar": ("ḏ", "ṭ", "ṣ", "ḍ", "ẓ", "ḥ", "ḫ", "ġ", "ṯ", "š", "ʿ", "ʾ", "ā", "ī", "ū"),
              "hi": ("ā", "ī", "ū", "ṅ", "ñ", "ṭ", "ḍ", "ṇ", "ś", "ṁ", "ṛ"),
              "ja": ("ō", "ū", "sh", "ch")}
# what an IPA line has and the usual scheme never does
IPA_SIGNS = "ʃʒɒæɯɕɾɡɢʔʕħðθɣχʁɪʊɛɔəɑɲŋɴɽʈɖʰʱˤː"


def _file(code):
    with open(os.path.join(K.LANG_DOCS, code + ".md"), encoding="utf-8") as f:
        return f.read()


def has_example(code):
    return re.search(r"^## Example$", _file(code), re.M) is not None


def states(code):
    """[(surface, options)] a prompt of this language can be in."""
    L = languages.get(code)
    out = []
    for surface in SURFACES:
        for translit in (("classic", "ipa") if L.ipa == "offered" else ("classic",)):
            for marks in (("0", "1") if L.strip_range else (None,)):
                asked = {"translit": translit}
                if marks is not None:
                    asked["marks"] = marks
                out.append((surface, asked))
    return out


def example_of(code, surface, asked):
    secs = dict(K.language_sections(surface, code, options=asked))
    return secs.get("Example")


def chunks_of(text):
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    assert len(blocks) == 1, "%d json blocks, not one" % len(blocks)
    return json.loads(blocks[0])["chunks"]


class TheExample(unittest.TestCase):
    def with_example(self):
        return [c for c in languages.CODES if has_example(c)]

    def test_the_five_languages_of_lane_d2a_have_one(self):
        self.assertEqual([c for c in D2A if not has_example(c)], [])

    def test_every_language_has_one_the_others_are_waited_for(self):
        lacking = [c for c in languages.CODES if not has_example(c)]
        if lacking:
            self.skipTest("still without an Example: %s (lane D2b: it fr de tr en es)" % " ".join(lacking))

    def test_it_is_one_block_of_json_in_the_shape_of_an_answer_in_every_state(self):
        for code in self.with_example():
            L = languages.get(code)
            for surface, asked in states(code):
                with self.subTest(language=code, surface=surface, asked=asked):
                    text = example_of(code, surface, asked)
                    self.assertTrue(text, "no Example reaches %s" % surface)
                    self.assertNotIn("{{", text)
                    chunks = chunks_of(text)
                    self.assertTrue(2 <= len(chunks) <= 4, "%d chunks" % len(chunks))
                    for ch in chunks:
                        self.assertLessEqual(set(ch), KEYS)
                        self.assertTrue(all(isinstance(v, str) for v in ch.values()))
                        self.assertTrue(ch.get("fa", "").strip() and ch.get("en", "").strip())
                        self.assertEqual(bool(L.reading), "kana" in ch, "kana is the reading languages'")
                        self.assertEqual(bool(L.words), "words" in ch, "words is the word languages'")
                        if L.require_tr:
                            self.assertTrue(ch.get("tr", "").strip(), "a language that romanises every chunk")

    def test_no_prompt_that_takes_the_example_carries_a_comment_or_the_note(self):
        for code in self.with_example():
            for surface in SURFACES:
                with self.subTest(language=code, surface=surface):
                    self.assertNotIn("<!--", K.language_text(surface, code))
                    self.assertNotIn("reviewed", example_of(code, surface, {}))

    def test_the_studio_never_takes_it(self):
        for code in self.with_example():
            for surface in ("studio-doc", "studio-exercises"):
                self.assertNotIn("Example", [n for n, _ in K.language_sections(surface, code)], (code, surface))

    def test_every_vocabulary_line_of_it_passes_the_checkers_of_a_book_and_of_a_video(self):
        for code in self.with_example():
            for surface, asked in states(code):
                for i, ch in enumerate(chunks_of(example_of(code, surface, asked))):
                    where = "%s %s %s chunk %d" % (code, surface, asked, i)
                    with self.subTest(where):
                        for field in ("fa", "kana", "tr", "en"):
                            if field in ch:
                                texwrite._value(field, ch[field], languages.get(code), where)   # what a book door takes
                        if ch.get("voc"):
                            texwrite._check_voc(ch["voc"], where)          # a book's line
                            texparse.parse_voc(ch["voc"], code)
                        if "words" in ch:                                  # a book's word line, at a book's door
                            texwrite._check_words(ch["words"], languages.get(code), where)
                            self.assertEqual(texwrite._words_fit(ch, languages.get(code), False, where), [])
                        errors, warnings = [], []
                        check_annotations.check_chunk(ch, where, errors.append, warnings.append, lang=code)
                        self.assertEqual(errors, [], "a video's chunk")

    def test_with_ipa_chosen_it_shows_ipa_and_never_the_usual_scheme(self):
        for code in self.with_example():
            L = languages.get(code)
            if L.ipa != "offered" or code in SCHEME_FREE:
                continue
            for surface in SURFACES:
                for marks in (("0", "1") if L.strip_range else (None,)):
                    asked = {"marks": marks} if marks is not None else {}
                    with self.subTest(language=code, surface=surface, marks=marks):
                        usual = chunks_of(example_of(code, surface, dict(asked, translit="classic")))
                        ipa = chunks_of(example_of(code, surface, dict(asked, translit="ipa")))
                        self.assertEqual(len(usual), len(ipa))
                        self.assertNotEqual([c.get("tr") for c in usual], [c.get("tr") for c in ipa],
                                            "the IPA example is the usual one")
                        said = json.dumps([{k: v for k, v in c.items() if k not in ("fa", "kana", "words", "en")}
                                           for c in ipa], ensure_ascii=False)
                        self.assertTrue(any(s in said for s in IPA_SIGNS), "no IPA sign in the IPA example")
                        for sign in USUAL_ONLY.get(code, ()):
                            self.assertNotIn(sign, said, "the IPA example shows the usual scheme (%s)" % sign)
                        if code in USUAL_ONLY:
                            usual_said = json.dumps([c.get("tr", "") + c.get("voc", "") for c in usual],
                                                    ensure_ascii=False)
                            self.assertTrue(any(s in usual_said for s in USUAL_ONLY[code]),
                                            "the list of the usual scheme's signs names none of the usual example's")

    def test_with_the_short_vowels_asked_for_it_adds_marks_and_nothing_else(self):
        for code in self.with_example():
            L = languages.get(code)
            if not L.strip_range:
                continue
            marks = re.compile("[%s]" % L.strip_range)
            for surface in SURFACES:
                with self.subTest(language=code, surface=surface):
                    bare = chunks_of(example_of(code, surface, {"marks": "0"}))
                    vowelled = chunks_of(example_of(code, surface, {"marks": "1"}))
                    self.assertEqual([marks.sub("", c["fa"]) for c in vowelled], [c["fa"] for c in bare],
                                     "more than the marks differs")
                    self.assertTrue(all(not marks.search(c["fa"]) for c in bare), "a mark in the bare example")
                    self.assertTrue(all(marks.search(c["fa"]) for c in vowelled), "a chunk with no mark")
                    # the sounds and the meanings do not move with the marks
                    self.assertEqual([(c.get("tr"), c["en"]) for c in vowelled], [(c.get("tr"), c["en"]) for c in bare])

    def test_a_language_the_owner_cannot_read_says_in_a_note_that_no_speaker_has_reviewed_it(self):
        for code in self.with_example():
            if code in OWNER_READS:
                continue
            with self.subTest(language=code):
                section = _file(code).split("\n## Example", 1)[1]
                notes = re.findall(r"\{\{\?note\}\}(.*?)\{\{/note\}\}", section, re.S)
                self.assertTrue(any("reviewed" in n for n in notes), "no note in the Example")


if __name__ == "__main__":
    unittest.main()
