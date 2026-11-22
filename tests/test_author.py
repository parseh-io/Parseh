# SPDX-License-Identifier: GPL-3.0-or-later
"""The author's signature (a0.4.1, lib/author.py): his name and two links,
in a few places and no more.

    python3 -m unittest discover -s tests -p test_author.py

WHAT THE OWNER DECIDED (2026-09-28): the foot of the hub (the browser layout
and the mobile one), of the guide (every page, and its hand-written front
page) and of the Settings hub carry ONLY two links, whose visible words are
"GitHub" and "imbrunoursino.net"; the Licences page and the README's License
section carry his name beside "the author", the two links and the line
"Copyright (c) 2026 Bruno Ursino".  Never in what a person makes or keeps --
a book's reader, a document, a deck, a card, a PDF, an exported page.  Links
only: nothing is fetched from either address.
The installation's About settings page also carries his name and the two
links; it is Parseh's own chrome, rather than user-authored content.

AND, ON 2026-10-06: at a FOOT the word "GitHub" leads to PARSEH's repository
(lib/project.py), and a screen reader and a hover say "Parseh on GitHub"; his
own profile stays where his name stands as the author -- the Licences page,
About and the README -- as "Bruno Ursino on GitHub".

Here: the two addresses and the name live once, and the author's is a person's
while the project's is an organisation's, handed to a foot by the page that
draws it; the module needs nothing but the standard library, and neither does
the guide's compiler that imports it; every foot says the two words and names
only for a screen reader and a hover; and no page of what a person makes
carries any of it.  What the pages DO with the links -- their colour in the
three themes, a finger's height on a phone, no request before a click, a new
tab at the address -- is driven in a browser by tests/signature.mjs.  The
foots' exact markup is pinned where each foot is already tested
(test_version.py, test_licences.py, test_mobile_mode.py, test_html_guide.py).
"""
import ast
import re
import subprocess
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import author                                                  # noqa: E402
import project                                                 # noqa: E402

NAME = "Bruno Ursino"
GITHUB = "https://github.com/Addicted2BayesianEpistemology"      # HIS profile: the author line's
PROJECT = "https://github.com/parseh-io/Parseh"                  # PARSEH's repository: a foot's
SITE = "https://imbrunoursino.net/"
WEBSITE = "https://parseh.io/"                                   # PARSEH's website: a foot's middle link (a0.5.0)
PROJECT_LABEL = "Parseh on GitHub"
PERSON_LABEL = "Bruno Ursino on GitHub"
SITE_LABEL = "imbrunoursino.net, Bruno Ursino's website"
WEBSITE_LABEL = "parseh.io, Parseh's website"


class Visible(HTMLParser):
    """The words a page SHOWS, tag by tag: the text nodes, and for each <a>
    its address and the attributes a screen reader and a hover read."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.links, self._open = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._open = dict(attrs)
            self._open["text"] = ""
            self.links.append(self._open)

    def handle_endtag(self, tag):
        if tag == "a":
            self._open = None

    def handle_data(self, data):
        self.text.append(data)
        if self._open is not None:
            self._open["text"] += data


def read(fragment):
    p = Visible()
    p.feed(fragment)
    return p


def external(fragment):
    return [a for a in read(fragment).links if re.match(r"https?://", a.get("href", ""))]


def hub_html():
    import serve
    with mock.patch.object(serve, "book_stats", lambda: []), \
            mock.patch.object(serve.studio.store, "list_docs", lambda: []), \
            mock.patch.object(serve.ytpages, "stats", lambda: {"channels": 0, "videos": 0, "decks": 0,
                                                               "cards": 0, "by_lang": {}}), \
            mock.patch.object(serve.studio.decks, "hub_stats",
                              lambda *a, **k: {"decks": 0, "due": 0, "by_lang": {}}):
        html = serve.hub_page()
    return html[html.index('class="hub-browser"'):html.index('class="hub-mobile"')], \
        html[html.index('class="hub-mobile"'):]


class TheModule(unittest.TestCase):
    def test_the_name_and_the_two_addresses_are_the_owner_s(self):
        self.assertEqual((author.NAME, author.GITHUB_URL, author.SITE_URL), (NAME, GITHUB, SITE))
        self.assertEqual((author.GITHUB_TEXT, author.SITE_TEXT), ("GitHub", "imbrunoursino.net"))
        self.assertEqual((author.GITHUB_LABEL, author.SITE_LABEL),
                         ("Bruno Ursino on GitHub", "imbrunoursino.net, Bruno Ursino's website"))
        self.assertEqual(author.YEAR, 2026)

    def test_the_author_s_address_is_a_person_s_and_the_project_s_an_organisation_s(self):
        import webexport
        # since a0.4.4 the project lives in an organisation (lib/project.py); the author's link is HIS profile
        # and stays where he is, so the two are no longer the same account's
        self.assertNotEqual(author.GITHUB_URL.split("/")[3], project.ORG)
        self.assertFalse(project.GITHUB_URL.startswith(author.GITHUB_URL + "/"))
        self.assertFalse(author.GITHUB_URL.startswith(project.GITHUB_URL))
        self.assertEqual(project.GITHUB_URL, PROJECT)
        # and the export's footer links the project, never the person
        self.assertEqual(webexport.GITHUB, project.GITHUB_URL)
        self.assertNotEqual(webexport.GITHUB, author.GITHUB_URL)

    def test_the_author_module_knows_no_address_of_the_project_it_is_handed_one(self):
        # a foot's GitHub is the project's, and the project's address is lib/project.py's alone: this
        # file is standard library only and imports no other module of Parseh, so it cannot read it --
        # and it must not copy it either, or the next move of the project would be two edits
        src = (ROOT / "lib" / "author.py").read_text(encoding="utf-8")
        self.assertNotIn("parseh-io", src)
        self.assertNotIn(project.GITHUB_URL, src)
        self.assertFalse(hasattr(author, "PROJECT_URL"))

    def test_a_link_opens_apart_tells_the_site_nothing_and_names_the_person(self):
        for a, url, text, label in ((author.github_link(), GITHUB, "GitHub", "Bruno Ursino on GitHub"),
                                    (author.site_link(), SITE, "imbrunoursino.net", "imbrunoursino.net, Bruno Ursino&#x27;s website")):
            self.assertEqual(a, '<a href="%s" target="_blank" rel="noopener noreferrer" aria-label="%s" '
                                'title="%s">%s</a>' % (url, label, label, text))
        two = read(author.links()).links
        self.assertEqual([(a["href"], a["text"]) for a in two],
                         [(GITHUB, "GitHub"), (SITE, "imbrunoursino.net")])
        for a in two:
            self.assertEqual((a["target"], a["rel"]), ("_blank", "noopener noreferrer"))
            self.assertEqual(a["aria-label"], a["title"])
        self.assertEqual([a["title"] for a in two], [PERSON_LABEL, SITE_LABEL])
        # the words a line SHOWS are the two names and the dot between them
        self.assertEqual("".join(read(author.links()).text), "GitHub · imbrunoursino.net")

    def test_a_foot_s_first_link_is_the_project_s_the_second_the_person_s(self):
        # the same words as the author line's, another address and another label (the owner, 2026-10-06)
        want = ('<a href="%s" target="_blank" rel="noopener noreferrer" aria-label="%s" title="%s">GitHub</a>'
                % (PROJECT, PROJECT_LABEL, PROJECT_LABEL))
        self.assertEqual(author.project_link(project.GITHUB_URL, project.NAME), want)
        web = author.website_link(project.WEBSITE_URL, project.NAME)
        foot = author.foot_links(project.GITHUB_URL, project.NAME, project.WEBSITE_URL)
        self.assertEqual(foot, want + author.SEP + web + author.SEP + author.site_link())
        three = read(foot).links
        self.assertEqual([(a["href"], a["text"]) for a in three], [(PROJECT, "GitHub"), (WEBSITE, "parseh.io"), (SITE, "imbrunoursino.net")])
        for a in three:
            self.assertEqual((a["target"], a["rel"]), ("_blank", "noopener noreferrer"))
            self.assertEqual(a["aria-label"], a["title"])
        self.assertEqual([a["title"] for a in three], [PROJECT_LABEL, WEBSITE_LABEL, SITE_LABEL])
        # what a foot SHOWS is the author line's two words with the website's between them: the label names whose address it is, the words do not
        self.assertEqual("".join(read(foot).text), "GitHub · parseh.io · imbrunoursino.net")
        self.assertEqual("".join(read(author.links()).text), "GitHub · imbrunoursino.net")
        self.assertNotIn(GITHUB, foot)
        self.assertNotIn(PERSON_LABEL, foot)
        # the label says the project's name as it was handed it, and still CONTAINS the words the link shows
        other = read(author.project_link("https://example.test/x", "Thing")).links[0]
        self.assertEqual((other["href"], other["aria-label"], other["title"]),
                         ("https://example.test/x", "Thing on GitHub", "Thing on GitHub"))
        self.assertIn(author.GITHUB_TEXT, other["aria-label"])
        site = read(author.website_link("https://example.test/y", "Thing")).links[0]
        self.assertEqual((site["href"], site["text"], site["aria-label"]), ("https://example.test/y", "example.test", "example.test, Thing's website"))

    def test_a_foot_s_row_is_the_same_three_links_with_the_dots_items_of_their_own(self):
        row = author.foot_row(project.GITHUB_URL, project.NAME, project.WEBSITE_URL)
        dot = '<span aria-hidden="true">&middot;</span>'
        self.assertEqual(row, author.project_link(project.GITHUB_URL, project.NAME) + dot
                         + author.website_link(project.WEBSITE_URL, project.NAME) + dot + author.site_link())
        self.assertEqual([a["href"] for a in read(row).links], [PROJECT, WEBSITE, SITE])

    def test_a_link_fetches_nothing(self):
        # a link is followed when it is clicked: no picture, icon, script, sheet
        # or font comes with it
        for tag in ("<img", "<script", "<link", "<iframe", "<svg", "src=", "srcset=", "url(", "@import"):
            self.assertNotIn(tag, author.links())
        self.assertEqual(len(re.findall(r"<a ", author.links())), 2)
        foot = author.foot_links(project.GITHUB_URL, project.NAME, project.WEBSITE_URL)
        for tag in ("<img", "<script", "<link", "<iframe", "<svg", "src=", "srcset=", "url(", "@import"):
            self.assertNotIn(tag, foot)
        self.assertEqual(len(re.findall(r"<a ", foot)), 3)

    def test_what_is_written_into_a_link_is_escaped(self):
        self.assertEqual(author.link('https://x.test/?a=1&b="2"', "<b>", "it's"),
                         '<a href="https://x.test/?a=1&amp;b=&quot;2&quot;" target="_blank" '
                         'rel="noopener noreferrer" aria-label="it&#x27;s" title="it&#x27;s">&lt;b&gt;</a>')

    def test_the_licences_line(self):
        self.assertEqual(author.copyright_line(), "Copyright &copy; 2026 Bruno Ursino")
        self.assertEqual(author.notice("Parseh"),
                         "Copyright &copy; 2026 Bruno Ursino, the author of Parseh &mdash; " + author.links())

    def test_it_needs_nothing_but_the_standard_library(self):
        tree = ast.parse((ROOT / "lib" / "author.py").read_text(encoding="utf-8"))
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imported.add((n.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertLessEqual(imported, set(sys.stdlib_module_names), imported)
        # and it is the FIRST thing the file says that it is Parseh's own
        self.assertEqual((ROOT / "lib" / "author.py").read_text(encoding="utf-8").splitlines()[0],
                         "# SPDX-License-Identifier: GPL-3.0-or-later")

    def test_the_guide_s_compiler_that_imports_it_needs_nothing_else(self):
        # -I -S: no site-packages, no user site, no PYTHONPATH -- the standard
        # library and the checkout, which is all a guide exported with
        # `build.py --export` has (engine/vendor/)
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "import engine.site as s; a = s.author; p = s.project; "
                "print(a.__file__.replace(chr(92), '/').rsplit('/', 2)[-2:], p.__file__.replace(chr(92), '/').rsplit('/', 2)[-2:], "
                "a.NAME, a.links() == a.github_link() + a.SEP + a.site_link(), "
                "a.foot_links(p.GITHUB_URL, p.NAME, p.WEBSITE_URL) == a.project_link(p.GITHUB_URL, p.NAME) + a.SEP + "
                "a.website_link(p.WEBSITE_URL, p.NAME) + a.SEP + a.site_link())")
        r = subprocess.run([sys.executable, "-I", "-S", "-c", code, str(ROOT / "html-guide")],
                           capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "['lib', 'author.py'] ['lib', 'project.py'] Bruno Ursino True True")

    def test_the_guide_lists_it_and_the_address_it_is_handed_among_the_modules_it_takes_from_parseh(self):
        sys.path.insert(0, str(ROOT / "html-guide"))
        from engine import manifest
        self.assertIn("lib/author.py", manifest.MODULE_FILES)
        self.assertIn("lib/project.py", manifest.MODULE_FILES)
        for rel in manifest.MODULE_FILES:
            self.assertTrue((ROOT / rel).is_file(), rel)


class TheFoots(unittest.TestCase):
    def check_two(self, fragment, where, first=(PROJECT, PROJECT_LABEL)):
        """The two links of a place: `first` is (the address, the label) of the GitHub one -- a FOOT's, which is
        Parseh's repository, unless the place is the author line's, where it is his profile."""
        links = external(fragment)
        self.assertEqual([(a["href"], a["text"]) for a in links],
                         [(first[0], "GitHub"), (SITE, "imbrunoursino.net")], where)
        for a in links:
            self.assertEqual((a["target"], a["rel"]), ("_blank", "noopener noreferrer"), where)
        self.assertEqual([a["aria-label"] for a in links], [first[1], SITE_LABEL], where)
        self.assertEqual([a["title"] for a in links], [first[1], SITE_LABEL], where)
        return read(fragment)

    def check_foot(self, fragment, where):
        """The three links of a FOOT: Parseh's repository, Parseh's website, his."""
        links = external(fragment)
        self.assertEqual([(a["href"], a["text"]) for a in links],
                         [(PROJECT, "GitHub"), (WEBSITE, "parseh.io"), (SITE, "imbrunoursino.net")], where)
        for a in links:
            self.assertEqual((a["target"], a["rel"]), ("_blank", "noopener noreferrer"), where)
        self.assertEqual([a["aria-label"] for a in links], [PROJECT_LABEL, WEBSITE_LABEL, SITE_LABEL], where)
        self.assertEqual([a["title"] for a in links], [PROJECT_LABEL, WEBSITE_LABEL, SITE_LABEL], where)
        return read(fragment)

    def test_the_browser_hub_s_foot_says_the_three_words_and_nothing_of_the_name(self):
        browser, _ = hub_html()
        foot = browser[browser.index('<div class="foot">'):]
        parsed = self.check_foot(foot, "hub foot")
        shown = "".join(parsed.text)
        self.assertNotIn("Bruno", shown)
        self.assertNotIn("Ursino", shown)
        self.assertTrue(shown.rstrip().endswith("GitHub · parseh.io · imbrunoursino.net"), shown[-80:])
        # the foot's other items stay as they were, and the three links come last
        self.assertLess(foot.index('<a href="/licences/">licences</a>'), foot.index(PROJECT))
        # and the person's own profile is not what the foot's GitHub leads to
        self.assertNotIn(GITHUB, browser)

    def test_the_mobile_hub_s_last_line_is_the_three_links_and_nothing_else(self):
        _, mobile = hub_html()
        line = re.search(r'<p class="m-by">(.*?)</p>', mobile, re.S).group(1)
        parsed = self.check_foot(line, "mobile hub")
        self.assertEqual("".join(parsed.text), "GitHub\u00b7parseh.io\u00b7imbrunoursino.net")
        self.assertEqual(line.count('<span aria-hidden="true">&middot;</span>'), 2)
        # after the version, and the last thing in the hub
        self.assertLess(mobile.index('<p class="m-ver">'), mobile.index('<p class="m-by">'))
        self.assertEqual(mobile.count('<p class="m-by">'), 1)
        rest = mobile[mobile.index('<p class="m-by">'):]
        self.assertEqual(len(re.findall(r"<a ", rest)), 3, "nothing after it but the three links")
        # and not under the class a phone's tests keep the browser's words out of
        self.assertNotIn('class="m-by foot"', mobile)
        # every link the mobile hub has to another site is these three
        self.assertEqual([a["href"] for a in external(mobile)], [PROJECT, WEBSITE, SITE])
        self.assertNotIn(GITHUB, mobile)

    def test_the_hub_names_him_nowhere_in_words_but_a_screen_reader_reads_it(self):
        browser, mobile = hub_html()
        for part in (browser, mobile):
            shown = "".join(read(part).text)
            self.assertNotIn("Bruno Ursino", shown)
            self.assertNotIn("the author", shown)

    def test_the_mobile_sheet_draws_the_line_in_dim_and_a_finger_high(self):
        css = (ROOT / "lib" / "mobile.css").read_text(encoding="utf-8")
        line = re.search(r"\.m-by\{([^}]*)\}", css).group(1)
        link = re.search(r"\.m-by a\{([^}]*)\}", css).group(1)
        self.assertIn("flex-wrap:wrap", line)
        self.assertIn("color:var(--dim)", link)
        # only the dot between them, which is decoration, is left in --faint
        self.assertNotIn("--faint", link)
        self.assertIn("color:var(--faint)", line)
        self.assertIn("min-height:48px", link)

    def test_the_settings_hub_ends_with_the_three_links_and_the_frame_adds_none(self):
        import settingspage
        page = settingspage.hub()
        main = page[page.index('<main class="settings">'):page.index("</main>")]
        self.assertEqual(main.count('<p class="foot">'), 1)
        foot = re.search(r'<p class="foot">(.*?)</p>', main, re.S).group(1)
        self.assertEqual(foot, author.foot_links(project.GITHUB_URL, project.NAME, project.WEBSITE_URL))
        self.check_foot(foot, "settings hub")
        self.assertTrue(main.rstrip().endswith("</p>"), "the foot is the last thing in the page")
        self.assertEqual(page.count('href="%s"' % PROJECT), 1)
        self.assertEqual(page.count(GITHUB), 0, "his profile is not at the Settings hub's foot")
        self.assertEqual(page.count(SITE), 1)
        # the foot is the hub's own: the frame every page of Settings is drawn
        # through does not add it (tests/signature.mjs opens the others)
        self.assertNotIn(PROJECT, settingspage.frame("t", "w", "m", "/guide/", '<main class="settings"></main>'))

    def test_the_licences_page_names_him_beside_the_author_and_links_both(self):
        import notices
        page = notices.page()
        self.assertIn('<p class="by">Copyright &copy; 2026 Bruno Ursino, the author of Parseh &mdash; %s</p>' % author.links(), page)
        self.assertEqual(len(external(page[page.index("<h2>Parseh</h2>"):page.index("<h2>What it carries</h2>")])), 2)
        # beside his name as the author, GitHub is HIS profile: "Bruno Ursino on GitHub"
        line = re.search(r'<p class="by">(.*?)</p>', page, re.S).group(1)
        self.check_two(line, "licences", first=(GITHUB, PERSON_LABEL))

    def test_about_names_the_author_and_links_both_on_its_own_page(self):
        import aboutpage
        page = aboutpage.page('host')
        main = page[page.index('<main class="settings tools">'):page.index('</main>')]
        # the fault section (TO-DO 5.31) links the PROJECT's issue page and nothing else outside Parseh;
        # it is taken out before the author line's links are counted
        at = main.index('<h2 class="part" id="fault">')
        fault = main[at:main.index('<p class="foot">', at)]
        import project
        self.assertEqual(set(re.findall(r'href="(https?://[^"]*)"', fault)), {project.ISSUES_URL})
        main = main.replace(fault, '')
        self.assertIn('<dt>Author</dt><dd><code>' + author.NAME + '</code></dd>', main)
        # his name stands there as the author, so GitHub is HIS profile: "Bruno Ursino on GitHub"
        self.check_two(main, 'About settings', first=(GITHUB, PERSON_LABEL))
        self.assertEqual(page.count(GITHUB), 1)
        self.assertEqual(page.count(SITE), 1)

    def test_the_readme_says_it_in_its_license_section(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        head, licence = readme.split("\n## License", 1)
        self.assertNotIn("Bruno Ursino", head)
        self.assertIn("Copyright © 2026 Bruno Ursino, the author of Parseh —\n"
                      "[GitHub](%s) ·\n[imbrunoursino.net](%s)." % (GITHUB, SITE), licence)
        # no version in it (test_version.py keeps README free of one)
        self.assertNotRegex(licence, r"\b[ab]\d+\.\d+")


class NotInWhatAPersonMakes(unittest.TestCase):
    """The signature is Parseh's own chrome.  A book, a document, a deck, a
    card, a printed page and an exported page are their writer's."""

    NEEDLES = ("Bruno Ursino", "imbrunoursino", "import author")

    def has(self, text):
        found = [n for n in self.NEEDLES if n in text]
        # the account, whatever follows: an export links to the project, which is not under it any more, and a
        # stale address of the old place would only have been hidden by an exception here
        if re.search(r"github\.com/Addicted2BayesianEpistemology", text):
            found.append("the account's address")
        return found

    def test_the_sources_that_write_what_a_person_keeps_carry_none_of_it(self):
        for rel in ("lib/tex2html.py", "lib/texparse.py", "lib/make_index.py", "lib/newbook.py",
                    "markdown/exlex/texgen.py", "markdown/exlex/template.tex", "markdown/exlex/mdparser.py",
                    "markdown/app/htmlgen.py", "markdown/app/webexport.py", "markdown/app/decks.py",
                    "markdown/app/templates/export_doc.html", "markdown/app/templates/export_deck.html",
                    "youtube/lib/player.html", "youtube/lib/anki_export.py", "youtube/lib/ytpages.py"):
            path = ROOT / rel
            if path.is_file():
                self.assertEqual(self.has(path.read_text(encoding="utf-8")), [], rel)

    # THE FILES THAT MAY IMPORT lib/author.py, and no others: Parseh's own chrome (the hub, the
    # Settings hub, About and Licences pages) and the guide's compiler. The signature's words live in that
    # one module, so a writer of what a person keeps -- a shelf's backup, a bundle, a PDF's source, a
    # deck -- could add it by importing it, and contain none of the words the list above looks for.
    # Widening this list is the owner's decision.
    IMPORTERS = {"serve.py", "lib/notices.py", "lib/settingspage.py", "lib/aboutpage.py",
                 "html-guide/engine/studio.py", "html-guide/engine/site.py"}

    @staticmethod
    def imports_author(source):
        """Does a module's source import `author`: `import author`, `from author import x`, a name
        `author` taken from another module, or importlib's import_module("author")?"""
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import) and any(a.name.split(".")[-1] == "author" for a in node.names):
                return True
            if isinstance(node, ast.ImportFrom) and ((node.module or "").split(".")[-1] == "author"
                                                     or any(a.name == "author" for a in node.names)):
                return True
            if isinstance(node, ast.Call):
                f = node.func
                called = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                first = node.args[0] if node.args else None
                if called in ("import_module", "__import__") and isinstance(first, ast.Constant) \
                        and first.value == "author":
                    return True
        return False

    def test_the_scan_for_who_imports_the_signature_sees_every_way_to(self):
        for source in ("import author", "def f():\n    import author as a\n", "from author import links",
                       "from .studio import GUIDE, author, find_font",
                       "import importlib\nimportlib.import_module('author')",
                       "from importlib import import_module\nimport_module(\"author\")", "__import__('author')"):
            self.assertTrue(self.imports_author(source), source)
        for source in ("import authors", "from authorship import links", "import json",
                       "def f(name):\n    return __import__(name)", "author = 'the person'"):
            self.assertFalse(self.imports_author(source), source)

    def test_only_parsehs_own_chrome_and_the_guides_compiler_import_the_signature(self):
        found = set()
        for path in sorted(ROOT.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(("tests/", ".claude/", "html-guide/site/", ".git/")) or rel == "lib/author.py":
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if self.imports_author(source):
                found.add(rel)
        self.assertEqual(found, self.IMPORTERS,
                         "a module that writes what a person keeps may not carry the author's signature: "
                         "if the owner has widened where it goes, this list is where that is said")

    def test_an_exported_document_carries_none_of_it(self):
        import webexport
        _n, data = webexport.document_html("plain-0a1b2c", {"title": "Plain"},
                                           "---\ntitle: Plain\ntarget: it\n---\n\nUn testo.\n", lambda p: None)
        page = data.decode("utf-8")
        self.assertIn("This page was exported from Parseh.", page)
        self.assertEqual(self.has(page), [])

    def test_a_document_drawn_by_the_studio_carries_none_of_it(self):
        import htmlgen
        md = "---\ntitle: Plain\ntarget: it\n---\n\nUn testo.\n"
        for colophon in (False, True):
            doc = htmlgen.render_document(md, colophon=colophon)
            self.assertEqual(self.has(doc["html"]), [], "colophon=%s" % colophon)

    def test_a_built_reader_carries_none_of_it(self):
        readers = sorted((ROOT / "tests" / "fixtures" / "books").glob("*/*/reader/index.html"))
        if not readers:
            self.skipTest("no fixture book has been built here (prepare the worktree)")
        for path in readers:
            self.assertEqual(self.has(path.read_text(encoding="utf-8")), [], str(path.relative_to(ROOT)))


class TheAddressesAreWrittenInAFewPlacesOnly(unittest.TestCase):
    """Two addresses and a name, in the places the owner named and in their
    documentation: a stray copy anywhere else fails here."""

    ALLOWED = ("lib/author.py", "README.md", "html-guide/index.html", "html-guide/site/",
               "html-guide/markdown/getting-started/the-hub.md",
               "html-guide/markdown/getting-started/this-guide.md",
               "html-guide/markdown/reference/licences.md", "tests/")

    def tracked(self):
        try:
            r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                               cwd=ROOT, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        return sorted(set(r.stdout.split("\n")) - {""}) if r.returncode == 0 else None

    def test_the_name_and_the_addresses_appear_only_where_they_were_asked_for(self):
        files = self.tracked()
        if files is None:
            self.skipTest("not a git checkout")
        stray = []
        for rel in files:
            if rel.startswith(self.ALLOWED) or not (ROOT / rel).is_file():
                continue
            if rel.endswith((".png", ".gif", ".jpg", ".jpeg", ".ico", ".woff2", ".ttf", ".otf", ".pdf",
                             ".zip", ".mp3", ".ogg", ".wav", ".mp4", ".webm", ".svg", ".gz", ".xz")):
                continue
            try:
                text = (ROOT / rel).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if (re.search(r"imbrunoursino|Bruno Ursino", text)
                    or re.search(r"github\.com/Addicted2BayesianEpistemology(?![/\w])", text)):
                stray.append(rel)
        self.assertEqual(stray, [])


if __name__ == "__main__":
    unittest.main()
