# SPDX-License-Identifier: GPL-3.0-or-later
"""No page tells anyone to type a command (TO-DO §5, "GUI first", a0.6.3 lane J1).

    python3 -m unittest tests.test_no_terminal

Each test reads what a page says -- the reader's script, the library page, the
add-a-book page, the studio's refusals, the video pages -- and holds it to the
rule: where a step is needed a button does it, where something must be
installed a Settings door is named, and never a command.  The buttons
themselves are driven in tests/no_terminal.mjs."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib", ROOT):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

# what a terminal instruction looks like, in a page's words
COMMAND = re.compile(r"python3? [\w/.-]+\.py|\./(?:serve|build)\.sh|pip install|conda run")


def _source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class TheReader(unittest.TestCase):
    """5.2: the reader's script (lib/tex2html.py) names no serve.py to run."""

    def test_no_serve_py_on_the_reader(self):
        src = _source("lib/tex2html.py")
        for said in ("served by python3 serve.py", "restart python3 serve.py",
                     "serve it with ' +\n      '<code>python3 serve.py</code>",
                     "is this page served by serve.py?", "needs the page served by serve.py"):
            self.assertNotIn(said, src)

    def test_says_what_to_do_from_the_pages(self):
        src = _source("lib/tex2html.py")
        self.assertIn("needs this page opened from Parseh while it runs; nothing was written", src)
        self.assertIn("start Parseh again the way you started it before and reload this page", src)
        self.assertIn("open this book from ' +\n      'Parseh’s library", src)


if __name__ == "__main__":
    unittest.main()
