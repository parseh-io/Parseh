# SPDX-License-Identifier: GPL-3.0-or-later
"""The server's part of the editor's preview in a tab of its own (a0.5.1): the reading page opened with
`?live=1`, and the preview route asked for the finished page (`page`).  The two tabs talking, the
double-click that lands on the text and the window given to the source are tests/studio_live.mjs.

    python3 -m unittest discover -s tests -p test_studio_live.py

No socket: the routes are driven through a fake handler, in a temporary studio library."""
import re
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import server  # noqa: E402
import store   # noqa: E402

MARKDOWN = """---
title: A lesson
lang: en
target: fa
---

Some prose.

## A section

:::exercise true-false
prompt: True or false?
- [پدر لیلا تکنولوژی را دوست دارد.]{tl} => false
:::
"""


class Fake:
    """What the page and preview routes use of a handler."""

    def __init__(self, body=None, query=""):
        self.body = body
        self.query = urllib.parse.parse_qs(query)
        self.sent = None

    def _json_body(self):
        return self.body

    def send_html(self, text, code=200):
        self.sent = (code, text)

    def send_json(self, payload, status=200):
        self.sent = (status, payload)


class LiveTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        was = store.use_library(Path(td.name))
        self.addCleanup(store.use_library, was)
        self.id = store.create(MARKDOWN)["id"]

    def page(self, query=""):
        h = Fake(query=query)
        server.page_doc(h, self.id)
        self.assertEqual(h.sent[0], 200)
        self.assertNotIn("{{", h.sent[1], "every value of the template is filled in")
        return h.sent[1]

    def preview(self, **extra):
        h = Fake(dict({"markdown": MARKDOWN, "doc_id": self.id}, **extra))
        server.api_preview(h)
        status, answer = h.sent
        self.assertEqual((status, answer["ok"]), (200, True))
        return answer["doc"]

    def test_the_reading_page_is_the_reading_page_it_was(self):
        for query in ("", "live=0", "live="):
            html = self.page(query)
            self.assertIn('data-live=""', html, query)
            self.assertIsNone(re.search(r'<script src="[^"]*live\.js"', html), query)
        # its strip is in the page and shut, for the script to open
        self.assertIn('id="livebar" hidden', self.page())

    def test_live_one_loads_the_script_and_says_so_on_the_body(self):
        html = self.page("live=1")
        self.assertIn('data-live="1"', html)
        self.assertEqual(len(re.findall(r'<script src="[^"]*/static/live\.js"></script>', html)), 1)

    def test_the_editors_own_preview_is_the_solved_half_page(self):
        doc = self.preview()
        self.assertIn('class="exercise correct"', doc["html"], "an exercise is drawn solved in the editor")
        self.assertNotIn("glosses", doc, "and the half page has no glossary to bind")

    def test_a_preview_asked_for_the_page_is_the_reading_page_of_the_text(self):
        doc = self.preview(page=True)
        self.assertNotIn('class="exercise correct"', doc["html"], "an exercise is there to be answered")
        self.assertIn('class="exercise"', doc["html"])
        self.assertIn("data-src-line", doc["html"], "its blocks say which line of the text they are")
        self.assertIn("toc", doc, "the contents are drawn beside it")
        self.assertIsInstance(doc["glosses"], list, "and the glossary its button opens")
        self.assertEqual(doc["prose"]["code"], "en")

    def test_the_unsaved_text_is_drawn_and_nothing_is_written(self):
        before = store.get(self.id)[1]
        doc = self.preview(page=True, markdown=MARKDOWN.replace("Some prose.", "Typed, unsaved prose."))
        self.assertIn("Typed, unsaved prose.", doc["html"])
        self.assertEqual(store.get(self.id)[1], before, "the document on disk is what it was")

    def test_a_text_that_does_not_render_says_why_and_does_not_throw(self):
        h = Fake({"markdown": MARKDOWN, "doc_id": self.id, "page": True})
        original = server.htmlgen.render_document
        server.htmlgen.render_document = lambda *a, **k: (_ for _ in ()).throw(ValueError("broken on purpose"))
        try:
            server.api_preview(h)
        finally:
            server.htmlgen.render_document = original
        status, answer = h.sent
        self.assertFalse(answer["ok"])
        self.assertIn("broken on purpose", answer["error"])


if __name__ == "__main__":
    unittest.main()
