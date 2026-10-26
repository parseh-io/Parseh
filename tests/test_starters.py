# SPDX-License-Identifier: GPL-3.0-or-later
"""What every language's starter shows (markdown/exlex/starters/<code>.md).

    python3 -m unittest discover -s tests -p test_starters.py

A new document opens on its language's starter, and the starter is a tour of
the whole dialect: each thing a note can do, done once on real examples, so
that a new user learns it by reading the page and its source side by side.
A thing the dialect documents and no starter shows is one nobody meets, and
a thing only some languages show is one their users alone meet -- so each
of these is asked of every starter, from the markdown it is written in to
the page htmlgen draws of it.  (smoke.py asks the rest: that each starter
declares its language, marks its runs as its script asks, and numbers them
as the store does; test_starter_media.py that every file one names ships.)
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app", ROOT / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import htmlgen    # noqa: E402
import mdparser   # noqa: E402
import texgen     # noqa: E402

STARTERS = ROOT / "markdown" / "exlex" / "starters"
PICTURE = re.compile(r"^images/starter-[a-z-]+\.svg\b")
RECORDING = re.compile(r"^audio/starter-[a-z-]+\.mp3\b")


class EveryStarter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {}
        for path in sorted(STARTERS.glob("*.md")):
            md = path.read_text(encoding="utf-8")
            fm, blocks = mdparser.parse(md)
            # drawn as a saved document draws it, with an asset base, so a
            # picture or a recording is an <img> or an <audio>, not the
            # placeholder of a document that has no files yet
            html = htmlgen.render_document(md, asset_base="/media/starter/", docs={})["html"]
            cls.pages[path.stem] = (md, blocks, html)
        assert len(cls.pages) >= 11, sorted(cls.pages)

    def exercises(self, blocks):
        return [b for b in blocks if b["type"] == "exercise"]

    def test_an_exercise_keeps_a_picture_and_a_recording_for_the_answer(self):
        # image-answer and audio-answer: shown once the exercise has been
        # answered (docs/studio-exercises.md, Pictures)
        for code, (md, blocks, html) in self.pages.items():
            with self.subTest(code):
                held = [b for b in self.exercises(blocks)
                        if b["subtype"] != "flashcard" and not b.get("errors")
                        and PICTURE.match(b["fields"].get("image-answer", ""))
                        and RECORDING.match(b["fields"].get("audio-answer", ""))]
                self.assertTrue(held, "no exercise with both image-answer and audio-answer")
                self.assertRegex(html, r'class="ex-image ex-image-answer[^"]*"[^>]*><img ')
                self.assertRegex(html, r'class="ex-audio ex-audio-answer[^"]*"[^>]*><audio ')

    def test_a_card_has_a_recording_of_its_own(self):
        # a vocabulary or opposites card's front-audio or back-audio: the
        # 🔊 that plays without turning the card
        for code, (md, blocks, html) in self.pages.items():
            with self.subTest(code):
                cards = [b for b in self.exercises(blocks)
                         if b["subtype"] == "flashcard" and not b.get("errors")
                         and b["fields"].get("card-type") in ("vocab", "opposites")
                         and any(RECORDING.match(b["fields"].get(k, ""))
                                 for k in ("front-audio", "back-audio"))]
                self.assertTrue(cards, "no vocab or opposites card with front-audio or back-audio")
                self.assertIn('class="ex-card-audio"', html)

    def test_a_recording_line_plays_a_clip(self):
        # `start=` and `end=` on a recording line: a player that plays that
        # stretch and no more, its address carrying it as a media fragment
        for code, (md, blocks, html) in self.pages.items():
            with self.subTest(code):
                clipped = [b for b in blocks if b["type"] == "audio" and b.get("valid")
                           and (b.get("start") is not None or b.get("end") is not None)]
                self.assertTrue(clipped, "no recording line with start= or end=")
                self.assertRegex(html, r'<audio [^>]*src="[^"]*starter-chime\.mp3#t=')

    def test_a_bullet_sits_one_level_down(self):
        # an item indented by two spaces: one level of nesting, drawn as a
        # list inside the item above it
        for code, (md, blocks, html) in self.pages.items():
            with self.subTest(code):
                nested = [b for b in blocks if b["type"] == "list"
                          and any(level for level, _ in b["items"])]
                self.assertTrue(nested, "no list with an indented item")
                self.assertRegex(html, r"<li>(?:(?!</li>).)*<ul><li>", "no <ul> inside an <li>")

    def test_the_arrow_is_typed_as_well(self):
        # `->` is the same arrow as `→`, on the screen and on paper, so a
        # starter shows it typed: in the markdown a `->` of the prose (not
        # the `\=>` of an exercise row), on the page an arrow wherever one
        # was typed, and in the .tex no `->` left over
        for code, (md, blocks, html) in self.pages.items():
            with self.subTest(code):
                typed = [b for b in blocks if b["type"] in ("para", "list")
                         and "->" in str(b.get("text", b.get("items")))]
                self.assertTrue(typed, "no -> typed in a paragraph or a list")
                self.assertNotIn("-&gt;", html)
                tex = texgen.generate(*mdparser.parse(md), colophon=False)
                body = tex.split("\\begin{document}", 1)[1]
                self.assertNotIn("->", body)
                self.assertNotIn("-\\textgreater", body)

    def test_a_follow_up_shows_its_steps_in_the_words_of_its_language(self):
        # a chain of exercises answered one after the other (a0.5.4): one in each starter, about language, of
        # steps of different types -- drawn as a strip of steps on the page and as numbered frames on paper
        for code, (md, blocks, html) in self.pages.items():
            with self.subTest(code):
                chains = [b for b in self.exercises(blocks) if b["subtype"] == "follow-up"]
                self.assertEqual(1, len(chains), "one follow-up in the starter")
                chain = chains[0]
                self.assertEqual([], chain["errors"])
                self.assertGreaterEqual(len(chain["steps"]), 2)
                self.assertGreaterEqual(len({s["subtype"] for s in chain["steps"]}), 3, "steps of different types")
                self.assertEqual(1, html.count('class="exercise ex-chain"'))
                self.assertEqual(len(chain["steps"]), html.count('class="ex-step"'))
                self.assertNotIn("ex-invalid", html)
                tex = texgen.generate(*mdparser.parse(md), colophon=False)
                body = tex.split("\\begin{document}", 1)[1]
                self.assertEqual(len(chain["steps"]), body.count("\\expaperstep{"))


if __name__ == "__main__":
    unittest.main()
