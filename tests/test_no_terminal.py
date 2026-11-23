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


class MissingPackages(unittest.TestCase):
    """5.3, 5.13: a missing rapidfuzz or zstandard points at Settings > Updating
    Parseh, whose section lists what is missing and has the button that adds it."""

    def test_both_are_in_the_lists_the_installers_read(self):
        import runtime
        names = {n for _m, n, _w in runtime.PACKAGES}
        self.assertIn("rapidfuzz", names)
        self.assertIn("zstandard", names)
        spec = {name for name, _s in runtime.env_spec()["pip"]}
        self.assertIn("rapidfuzz", spec)
        self.assertIn("zstandard", spec)

    def test_the_narration_panel_points_at_the_door(self):
        src = _source("lib/tex2html.py")
        self.assertNotIn("pip install rapidfuzz", src)
        self.assertIn('href="/settings/update/#packages"', src)

    def test_the_anki_page_points_at_the_door(self):
        import ytpages
        said = ytpages._explain(ModuleNotFoundError("No module named 'zstandard'"))
        self.assertNotRegex(said, COMMAND)
        self.assertNotIn("conda", said)
        self.assertIn("/settings/update/#packages", said)

    def test_the_update_page_lists_them_with_a_button(self):
        import updatepage
        pk = {"missing": [{"name": "rapidfuzz", "what": "aligning a narration"}], "job": {}}
        html = updatepage._packages_section(pk, True)
        self.assertIn('id="packages"', html)
        self.assertIn("<b>rapidfuzz</b>", html)
        self.assertIn("data-pk-add", html)
        # another device sees the list and no button it would be refused
        self.assertNotIn("data-pk-add", updatepage._packages_section(pk, False))
        # nothing missing, nothing running: no section at all
        self.assertEqual(updatepage._packages_section({"missing": [], "job": {}}, True), "")

    def test_the_route_is_the_computers_alone(self):
        import settingspage
        self.assertEqual(settingspage.ROUTES["/settings/api/update/packages"], ("parseh.update",))

    def test_start_refuses_without_an_environment_and_adds_with_one(self):
        from unittest import mock
        import envpackages
        import runtime
        with mock.patch.object(runtime, "find_env", lambda: (None, None)):
            answer, status = envpackages.start()
        self.assertEqual(status, 409)
        self.assertNotRegex(answer["error"], COMMAND)
        added = []
        state = {"have": False}

        def status_now():
            return {"packages": [{"name": "rapidfuzz", "what": "x", "have": state["have"]}]}

        def complete(prefix, python, report):
            added.append((prefix, python))
            report.log("pip says it installed rapidfuzz")
            state["have"] = True
            return True
        with mock.patch.object(runtime, "find_env", lambda: ("/env", "/env/bin/python")), \
                mock.patch.object(runtime, "status", status_now), \
                mock.patch.object(runtime, "complete_env", complete):
            answer, status = envpackages.start()
            self.assertEqual((status, answer.get("running")), (200, True))
            import time
            for _ in range(100):
                if not envpackages.job().get("running"):
                    break
                time.sleep(0.02)
            job = envpackages.job()
            self.assertTrue(job["ok"], job)
            self.assertEqual(job["log"], ["pip says it installed rapidfuzz"])
            self.assertEqual(added, [("/env", "/env/bin/python")])
            self.assertEqual(envpackages.start()[0].get("nothing"), True)


class TheLibraryPage(unittest.TestCase):
    """5.5: the library page names no make_index.py or build.sh; a button writes
    the list again (POST /books/__relist)."""

    def _page(self):
        import tempfile
        from unittest import mock
        import languages
        import make_index
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(make_index, "BOOKS_DIR", tmp), \
                mock.patch.object(make_index, "all_books", lambda: []), \
                mock.patch.object(languages, "write_css", lambda *a, **k: None):
            make_index.main()
            return Path(tmp, "index.html").read_text(encoding="utf-8")

    def test_the_page_has_the_button_and_no_command(self):
        html = self._page()
        self.assertIn("data-relist>write the list again</button>", html)
        self.assertIn("fetch('/books/__relist'", html)
        self.assertNotIn("./build.sh", html)
        self.assertNotIn("make_index.py", html)
        self.assertNotRegex(html, COMMAND)

    def test_the_route_is_named_for_the_activity_list(self):
        import serve
        self.assertEqual(serve.long_work("POST", "/books/__relist", {})[:2],
                         ("build", "Writing the list of books again"))


class TheAddABookPage(unittest.TestCase):
    """5.6: the add-a-book page says the PDF comes from a button, never ./build.sh."""

    def test_no_build_sh(self):
        import newbook
        html = newbook.page()
        self.assertNotIn("build.sh", html)
        self.assertNotIn("serve.sh", html)
        self.assertNotRegex(html, COMMAND)
        self.assertIn("<b>build the PDF now</b> in the answer", html)
        self.assertNotIn("build.sh", newbook.MAIN_TEX)


if __name__ == "__main__":
    unittest.main()
