# SPDX-License-Identifier: GPL-3.0-or-later
"""One version, kept in one place, read by everything and shown (TO-DO §16.1).

    python3 -m unittest tests/test_version.py

VERSION at the root is one line; lib/version.py is the only Python that reads
it, and says how two versions compare.  Held here: the file's shape; the
order (a0.3.10 after a0.3.9, every b after every a, a missing number a zero);
that the Server headers, the bundle's stamp, the four downloaders' user agents,
the startup line and the hub's foot in both layouts all say the file's
version and nothing else; that no source writes a version by hand into a
stamp any more; the data formats (formats()) read from the source, and
complete -- a stamp written anywhere, or a store kept in config/, with no row
is a failure; the changelog's reader (lib/changelog.py), whose refusals are
the point of it; and the promise that outlives every version: a bundle an
older Parseh wrote, stamped "Parseh/1.0", still installs
(tests/fixtures/bundles/, written by a0.3.0's own code).
"""
import ast
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in ("markdown/exlex", "markdown/app", "youtube/lib", "lib", "."):
    if str(ROOT / folder) not in sys.path:
        sys.path.insert(0, str(ROOT / folder))
import changelog  # noqa: E402
import version    # noqa: E402

V = version.VERSION
OLD = ROOT / "tests" / "fixtures" / "bundles"


def sources():
    """Every Python file of Parseh's own, tracked or new -> [relative path]."""
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard",
                          "*.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(p for p in set(out.split("\n"))
                  if p and not p.startswith(("tests/", "html-guide/site/")) and (ROOT / p).is_file())


# ------------------------------------------------------------------ the file
class TheFile(unittest.TestCase):
    def test_it_is_one_lf_line_holding_a_version(self):
        raw = (ROOT / "VERSION").read_bytes()
        self.assertEqual(raw, V.encode("ascii") + b"\n")
        version.parse(V)
        self.assertEqual(version.read(ROOT), V)

    def test_git_keeps_it_lf_on_every_system(self):
        rules = (ROOT / ".gitattributes").read_text(encoding="utf-8").split("\n")
        self.assertIn("VERSION text eol=lf", rules)

    def test_a_tree_without_one_is_refused_in_words(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "install it again from a release"):
                version.read(td)
            for text, said in (("a0.3.1\na0.3.0\n", "one line"), ("v0.3.1\n", "not a version"),
                               ("\n", "not a version"), ("", "holds 0")):
                Path(td, "VERSION").write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, said):
                    version.read(td)
            Path(td, "VERSION").write_bytes(b"a0.3.1\r\n")      # a checkout that ignored the rule
            self.assertEqual(version.read(td), "a0.3.1")


# ------------------------------------------------------------------ the order
class TheOrder(unittest.TestCase):
    def test_the_numbers_are_compared_as_numbers(self):
        self.assertEqual(version.compare("a0.3.10", "a0.3.9"), 1)
        self.assertEqual(version.compare("a0.3.9", "a0.3.10"), -1)
        self.assertEqual(version.compare("a0.10.0", "a0.9.9"), 1)
        self.assertEqual(version.compare("a0.3.1", "a0.3.1"), 0)

    def test_the_stage_comes_before_the_numbers(self):
        self.assertEqual(version.compare("b0.1", "a0.9.9"), 1)
        self.assertEqual(version.compare("1.0", "b9.9"), 1)
        self.assertEqual(version.compare("a9.0", "b0.1"), -1)

    def test_a_missing_number_is_a_zero(self):
        self.assertEqual(version.compare("a1.0", "a1.0.0"), 0)
        self.assertEqual(version.parse("a1.0"), version.parse("a1.0.0"))
        self.assertEqual(version.compare("a1.0.1", "a1.0"), 1)

    def test_a_shuffled_list_sorts_into_the_order_releases_come_in(self):
        order = ["a0.2.0", "a0.3.0", "a0.3.1", "a0.3.9", "a0.3.10", "a0.4.0", "a1.0",
                 "b0.1", "b1.0.2", "1.0", "1.0.1", "2.0"]
        self.assertEqual(sorted(reversed(order), key=version.parse), order)
        self.assertEqual(sorted(order[::2] + order[1::2], key=version.parse), order)

    def test_anything_else_is_refused(self):
        for bad in ("", "a", "a1", "v0.3.1", "a0.03.1", "a0.3.1rc1", "c1.0",
                    "A0.3.1", " a0.3.1", "a0.3.", "a.0.3", "a0..3", "ab0.1", "a0.3.1\n",
                    # a rehearsal is -rc and a number from 1, and nothing else
                    "a0.3.1-rc", "a0.3.1-rc0", "a0.3.1-rc01", "a0.3.1-RC1", "a0.3.1-beta1",
                    "a0.3.1-rc1-rc2", "a0.3.1.rc1", "a0.3.1-rc1\n", "a0.3.1_rc1",
                    None, 1.0, 3):
            for ask in (version.parse, version.rc, version.base,
                        lambda v: version.compare(v, "a0.3.1")):
                with self.assertRaises(ValueError, msg=repr(bad)):
                    ask(bad)


class Rehearsals(unittest.TestCase):
    """aX.Y.Z-rcN, the tag a release is rehearsed under (the owner,
    2026-09-25): after every earlier version, before the one it rehearses,
    the rehearsals among themselves by their number."""

    def test_a_rehearsal_comes_before_its_version_and_after_the_one_before(self):
        order = ["a0.3.1", "a0.3.2-rc1", "a0.3.2-rc2", "a0.3.2-rc10", "a0.3.2", "a0.3.3-rc1",
                 "a0.3.3", "a0.3.10-rc1", "a0.3.10", "a1.0-rc1", "a1.0", "b0.1-rc1", "b0.1",
                 "1.0-rc1", "1.0"]
        self.assertEqual(sorted(reversed(order), key=version.parse), order)
        self.assertEqual(sorted(order[::2] + order[1::2], key=version.parse), order)
        self.assertEqual(version.compare("a0.3.2-rc1", "a0.3.2"), -1)
        self.assertEqual(version.compare("a0.3.2-rc2", "a0.3.2-rc1"), 1)
        self.assertEqual(version.compare("a0.3.2-rc9", "a0.3.2-rc10"), -1)    # as numbers
        self.assertEqual(version.compare("a0.3.2-rc1", "a0.3.1"), 1)
        self.assertEqual(version.compare("a1.0-rc1", "a1.0.0-rc1"), 0)        # the zero rule holds

    def test_its_number_and_the_version_it_rehearses(self):
        self.assertEqual((version.rc("a0.3.2-rc2"), version.base("a0.3.2-rc2")), (2, "a0.3.2"))
        self.assertEqual((version.rc("a0.3.2"), version.base("a0.3.2")), (None, "a0.3.2"))
        self.assertEqual(version.base("1.0-rc3"), "1.0")

    def test_version_never_names_one(self):
        # a rehearsal is a tag's name: VERSION says the version rehearsed
        with self.assertRaisesRegex(ValueError, "a rehearsal's name: it names the version being "
                                                "rehearsed, a0.3.2, and only the tag carries -rc1"):
            version.spelt("a0.3.2-rc1\n", "VERSION")
        with tempfile.TemporaryDirectory() as td:
            Path(td, "VERSION").write_text("a0.3.2-rc1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "rehearsal"):
                version.read(td)
        self.assertEqual(version.spelt("a0.3.2\n"), "a0.3.2")

    def test_the_updater_goes_forward_from_a_rehearsal_to_its_version(self):
        # an install made from a rehearsal's zip carries the tag in its
        # manifest; the version itself is newer, the next rehearsal too
        import updater
        self.assertEqual(updater.direction_of("a0.3.2-rc1", "a0.3.2"), "newer")
        self.assertEqual(updater.direction_of("a0.3.2-rc1", "a0.3.2-rc2"), "newer")
        self.assertEqual(updater.direction_of("a0.3.2", "a0.3.2-rc1"), "older")
        self.assertEqual(updater.direction_of("a0.3.1", "a0.3.2-rc1"), "newer")


# ------------------------------------------------------------------ who reads it
class EverythingSaysIt(unittest.TestCase):
    def test_the_two_servers_announce_it(self):
        import serve
        import server as studio_server
        self.assertEqual(serve.Handler.server_version, "Parseh/" + V)
        self.assertEqual(studio_server.Handler.server_version, "exlex-studio/" + V)

    def test_the_real_server_sends_it_in_its_header(self):
        import http.client
        import threading
        import serve
        with mock.patch.object(serve.Handler, "log_request", lambda *a, **k: None):
            srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=60)
                c.request("GET", "/licences/")
                r = c.getresponse()
                r.read()
                c.close()
            finally:
                srv.shutdown()
                srv.server_close()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.getheader("Server").split(" ")[0], "Parseh/" + V)

    def test_the_startup_line_leads_with_it(self):
        import serve
        out = io.StringIO()
        with mock.patch.dict(serve.RUN, host="127.0.0.1", port=7999, scheme="http", forced_host=""), \
                mock.patch.object(serve, "ADDRESSES", []), \
                mock.patch.object(serve.network, "settings", lambda: {"lan": False}), \
                mock.patch.object(serve.settingspage, "doors_said", lambda doc: "this computer"), \
                contextlib.redirect_stdout(out):
            serve._announce(None, False)
        first = out.getvalue().split("\n")[0]
        self.assertEqual(first, "Parseh %s: serving %s on 127.0.0.1:7999 (http)" % (V, serve.ROOT))

    def test_a_bundle_is_stamped_with_it(self):
        import bundle
        self.assertEqual(bundle.SOFTWARE, "Parseh/" + V)
        with tempfile.TemporaryDirectory() as td:
            book = Path(td) / "books" / "english" / "mini-en"
            shutil.copytree(ROOT / "tests" / "fixtures" / "books" / "english" / "mini-en", book,
                            ignore=shutil.ignore_patterns("reader"))
            data, _name = bundle.pack_book(str(book))
            self.assertEqual(bundle.inspect(data, root=td)["software"], "Parseh/" + V)
        man = json.loads(zipfile.ZipFile(io.BytesIO(data)).read(bundle.MANIFEST))
        self.assertEqual(man["software"], "Parseh/" + V)

    def test_every_downloader_says_it_to_the_servers_it_asks(self):
        import getcorpus
        import getdecomposition
        import getmt
        import getstt
        import getsyn
        for mod in (getmt, getsyn, getcorpus, getdecomposition, getstt):
            self.assertTrue(mod.UA.startswith("Parseh/%s (" % V), (mod.__name__, mod.UA))

    def test_the_hub_says_it_in_both_layouts(self):
        import serve
        with mock.patch.object(serve, "book_stats", lambda: []), \
                mock.patch.object(serve.studio.store, "list_docs", lambda: []), \
                mock.patch.object(serve.ytpages, "stats", lambda: {"channels": 0, "videos": 0, "decks": 0,
                                                                   "cards": 0, "by_lang": {}}), \
                mock.patch.object(serve.studio.decks, "hub_stats",
                                  lambda *a, **k: {"decks": 0, "due": 0, "by_lang": {}}):
            html = serve.hub_page()
        browser = html[html.index('class="hub-browser"'):html.index('class="hub-mobile"')]
        mobile = html[html.index('class="hub-mobile"'):]
        foot = browser[browser.index('<div class="foot">'):]
        self.assertIn('Parseh <span class="ver">%s</span> is free software' % V, foot)
        self.assertIn('<p class="m-ver">Parseh %s</p>' % V, mobile)
        # and the licence line a test of its own pins is left as it was
        self.assertIn('<p class="m-foot">Free software, GPL 3 or later &middot; '
                      '<a href="/licences/">Licences</a></p>\n', mobile)
        # and the foot's two links come after them, in both layouts (a0.4.1,
        # lib/author.py): the browser foot's last line, the mobile hub's last --
        # GitHub is PARSEH's repository (the owner, 2026-10-06), not his profile
        import author
        import project
        self.assertIn('<a href="/licences/">licences</a>.<br>\n    %s\n  </div>'
                      % author.foot_links(project.GITHUB_URL, project.NAME, project.WEBSITE_URL), foot)
        self.assertLess(mobile.index('<p class="m-ver">'), mobile.index('<p class="m-by">'))
        self.assertIn('<p class="m-by">%s</p>\n' % author.foot_row(project.GITHUB_URL, project.NAME, project.WEBSITE_URL), mobile)

    def test_no_source_writes_a_version_into_a_stamp_by_hand(self):
        # "Parseh/1.0" was written in seven places, and each said a number no
        # release ever had; a string like it anywhere in the code is the same
        # mistake coming back.  Every such stamp is made from version.VERSION.
        # Strings only -- a comment or a docstring may say what used to be.
        hand = re.compile(r"(?:Parseh|exlex-studio)/[ab]?[0-9]")
        found = []
        for rel in sources():
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8", errors="replace"))
            docs = {id(n.body[0].value) for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.body and isinstance(n.body[0], ast.Expr)
                    and isinstance(n.body[0].value, ast.Constant)}
            found += ["%s:%d" % (rel, n.lineno) for n in ast.walk(tree)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)
                      and id(n) not in docs and hand.search(n.value)]
        self.assertEqual(found, [])

    def test_the_readme_names_no_version_and_sends_to_the_newest_release(self):
        # README.md's "Version a0.3.1" was the one place nobody remembered: it
        # still said a0.3.1 while VERSION said a0.3.2.  It names no version
        # now -- it links to GitHub's newest release, which is right whatever
        # is released, and the hub's foot says which one is running -- so it
        # cannot go stale, and a version written back into it fails here
        # instead of being forgotten on the next release day.
        import project
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"\b[ab]\d+\.\d+(?:\.\d+)?\b", readme), [],
                         "README.md names a version: link to the newest release instead")
        self.assertIn(project.LATEST_URL, readme)


# ------------------------------------------------------------------ the data's numbers
class DataFormats(unittest.TestCase):
    def test_formats_are_the_numbers_the_modules_hold(self):
        import books
        import bundle
        import check_annotations
        import decks
        import languages
        import network
        import offline
        import prefs
        import reading
        import serve
        import shelf
        import updater
        import anki_store
        import clips
        import corpus
        import getdecomposition
        import getsyn
        import lookup
        import merge_parts
        import store
        import timestamp
        import latexthemes
        import making
        import prompts
        import texpackages
        import analysisconfig
        import getarasaac
        import wordtimes
        import llmconfig
        import lmlikelihoodconfig
        import asrpending
        import speechconfig
        got = version.formats()
        self.assertEqual(set(got), set(version.FORMATS))
        held = {"parseh-speech": speechconfig.STORE_FORMAT, "parseh-pending-transcription": asrpending.FORMAT, "parseh-llm": llmconfig.STORE_FORMAT, "parseh-lm-likelihood": lmlikelihoodconfig.STORE_FORMAT,
                "parseh-timings": timestamp.TIMINGS_FORMAT, "parseh-review": timestamp.REVIEW_FORMAT,
                "parseh-parts": merge_parts.PARTS_FORMAT, "parseh-waveform": serve.WAVEFORM_FORMAT,
                "parseh-wordtimes": wordtimes.WORDTIMES_FORMAT,
                "parseh-library": store.LIBRARY_FORMAT, "parseh-anki": anki_store.STORE_FORMAT,
                "parseh-clips": clips.INFO_FORMAT, "parseh-dictionary": lookup.DB_FORMAT,
                "parseh-corpus": corpus.DB_FORMAT, "parseh-components": getdecomposition.PACK_FORMAT,
                "parseh-synonyms": getsyn.FORMAT,
                "parseh-bundle": bundle.FORMAT, "parseh-shelf": shelf.FORMAT,
                "parseh-narration": serve.NARR_FORMAT, "parseh-exercise-deck": decks.FORMAT,
                "parseh-exercise-shelf": decks.SHELF_FORMAT,
                "parseh-schedule": decks.SCHEDULE_FORMAT, "parseh-book": books.BOOK_FORMAT,
                "parseh-reading": reading.READING_FORMAT,
                "parseh-video": check_annotations.VIDEO_FORMAT,
                "parseh-annotations": check_annotations.ANNOTATIONS_FORMAT,
                "parseh-prefs": prefs.STORE_FORMAT, "parseh-network": network.STORE_FORMAT,
                "parseh-languages": languages.STORE_FORMAT,
                "parseh-digests": offline.DIGESTS_FORMAT, "parseh-wheres": offline.WHERES_FORMAT,
                "parseh-updates": updater.STORE_FORMAT,
                "parseh-latex": latexthemes.STORE_FORMAT,
                "parseh-latex-theme": latexthemes.EXPORT_FORMAT,
                "parseh-prompts": prompts.STORE_FORMAT, "parseh-prompt": prompts.EXPORT_FORMAT,
                "parseh-texmf": texpackages.MANIFEST_FORMAT,
                "parseh-arasaac": getarasaac.ARASAAC_FORMAT,
                "parseh-analysis": analysisconfig.STORE_FORMAT,
                "parseh-annot": making.ANNOT_FORMAT}
        self.assertEqual(set(held) - set(got), set(), "held here, with no row")
        self.assertEqual(set(got) - set(held), set(), "a row this test does not hold")
        for fmt, value in held.items():
            n = int(value.rpartition("/")[2]) if isinstance(value, str) else value
            self.assertEqual(got[fmt], n, fmt)
            if isinstance(value, str):
                self.assertEqual(value.rpartition("/")[0], fmt)      # the stamp is the name
            self.assertTrue(version.what(fmt))

    def test_every_stamp_written_anywhere_has_its_row(self):
        stamp = re.compile(r"""["'](parseh-[a-z-]+)/(\d+)["']""")
        got, found = version.formats(), {}
        for rel in sources():
            for m in stamp.finditer((ROOT / rel).read_text(encoding="utf-8", errors="replace")):
                found.setdefault(m.group(1), set()).add((int(m.group(2)), rel))
        # the one stamp that is not a store: a release's own manifest, which
        # every update replaces whole with the version it installs, so no
        # Parseh ever reads what a later one left behind in it
        found.pop("parseh-release", None)
        self.assertIn("parseh-bundle", found)
        for fmt, where in sorted(found.items()):
            self.assertIn(fmt, got, "a stamp with no row in lib/version.py FORMATS: %s" % sorted(where))
            for n, rel in where:
                self.assertEqual(n, got[fmt], "%s writes %s/%d" % (rel, fmt, n))

    def test_every_store_kept_in_config_has_its_row(self):
        # a file joined onto "config" -- os.path.join(..., "config", "x.json")
        # or a Path's / "config" / "x.json" -- is a store the updater keeps,
        # and an older Parseh may read it wrong: it needs a number
        kept = re.compile(r"""["']config["']\s*[,/]\s*["']([\w.-]+)["']""")
        said = " ".join(version.what(f) for f in version.FORMATS)
        found = {}
        for rel in sources():
            for m in kept.finditer((ROOT / rel).read_text(encoding="utf-8", errors="replace")):
                found.setdefault(m.group(1), set()).add(rel)
        self.assertIn("prefs.json", found)
        for name, where in sorted(found.items()):
            self.assertIn("config/" + name, said,
                          "config/%s (%s) has no row in lib/version.py FORMATS" % (name, sorted(where)))

    # WHERE A PERSON'S THINGS ARE KEPT -- lib/release.py's CONTENT, the
    # folders a release ships empty and an update never touches -- and the
    # rows that number what Parseh writes in each.  A folder added to that
    # list with no rows here fails: an update going back could not say what
    # in it may not survive.
    KEPT = {"books/": ("parseh-book", "parseh-reading", "parseh-timings", "parseh-review",
                       "parseh-annot"),
            "youtube/videos/": ("parseh-video", "parseh-annotations", "parseh-parts",
                                "parseh-waveform", "parseh-wordtimes", "parseh-pending-transcription"),
            "markdown/library/": ("parseh-library",),
            "exercises/": ("parseh-exercise-deck", "parseh-schedule"),
            "clips/": ("parseh-clips",),
            "youtube/anki/": ("parseh-anki",),
            "config/": ("parseh-analysis", "parseh-prefs", "parseh-network", "parseh-languages", "parseh-digests",
                        "parseh-wheres", "parseh-updates", "parseh-latex", "parseh-prompts", "parseh-llm", "parseh-lm-likelihood", "parseh-speech"),
            "texmf/": ("parseh-texmf",),
            "dict/": ("parseh-dictionary",),
            "corpus/": ("parseh-corpus",),
            "mt/": ("parseh-synonyms",),
            "components/": ("parseh-components",),
            # speech to text's program and models keep no store of Parseh's: the
            # program's folder is named by the pin it was made for, a model's has a
            # meta.json of the kind mt/'s have, and lib/getstt.py judges both (older,
            # newer, another Python) -- so there is no row, and a step back to a
            # version that lacks the folder has nothing to warn about
            "stt/": (),
            # Isolated numerical runtime/toolchain, with no Parseh data store.
            "llm-scoring/": (),
            # the ARASAAC pictograms keep a manifest, their facts and each language's words
            # in one shape, which an older Parseh does not know
            "arasaac/": ("parseh-arasaac",),
            "analysis/": ()}
    # the rows that are not a store but a file made to travel: each is read
    # back by its own stamp, whatever wrote it
    TRAVEL = {"parseh-bundle", "parseh-shelf", "parseh-narration", "parseh-exercise-shelf",
              "parseh-latex-theme", "parseh-prompt"}

    def test_every_place_a_person_s_things_are_kept_has_its_rows(self):
        import release
        self.assertEqual(set(self.KEPT), set(release.CONTENT))
        rows = set(version.FORMATS)
        placed = {fmt for fmts in self.KEPT.values() for fmt in fmts}
        self.assertEqual(placed - rows, set(), "named here, with no row")
        self.assertEqual(rows - placed - self.TRAVEL, set(), "a row kept nowhere this test knows")

    def test_the_two_lists_of_a_persons_things_are_one_list(self):
        # lib/updater.py PERSONAL (what no manifest may touch) and lib/release.py CONTENT
        # (what a release ships empty) name the same folders -- in a different order,
        # which is why this is a comparison of sets -- and nothing held them together
        import release
        import updater
        self.assertEqual(set(updater.PERSONAL), set(release.CONTENT))
        self.assertIn("stt/", updater.PERSONAL)
        self.assertIn("arasaac/", updater.PERSONAL)
        self.assertNotIn("arasaac/", updater.CONTENT, "somebody else's pictures: fetched again by a button")
        # updater.CONTENT is a third, different list: the folders whose SMALL files are
        # copied before a step back.  Speech to text's program and models are gigabytes
        # and no data format of Parseh's is kept in them
        self.assertNotIn("stt/", updater.CONTENT)

    def test_the_stores_the_owner_named_have_their_rows(self):
        # the owner, 2026-09-25: the studio's library and the Anki store; a
        # book's timings.json and review.json; a video's parts/*.json and
        # waveform.json; the optional tools' databases in dict/, corpus/ and
        # components/ -- each said, in the words the updater uses, by name
        for fmt, name in (("parseh-library", "markdown/library/"), ("parseh-anki", "youtube/anki/"),
                          ("parseh-timings", "timings.json"), ("parseh-review", "review.json"),
                          ("parseh-parts", "parts/*.json"), ("parseh-waveform", "waveform.json"),
                          ("parseh-wordtimes", "wordtimes.json"),
                          ("parseh-dictionary", "dict/"), ("parseh-corpus", "corpus/"),
                          ("parseh-components", "components/")):
            self.assertIn(name, version.what(fmt), fmt)
        # the one of them that writes its number into what it builds writes
        # the constant, so the two cannot differ
        src = (ROOT / "lib" / "getdecomposition.py").read_text(encoding="utf-8")
        self.assertIn("schema=PACK_FORMAT", src)
        self.assertNotRegex(src, r"schema=\d")

    def test_every_json_a_book_or_a_video_carries_has_its_row(self):
        # what a bundle carries is what one Parseh hands another; source/'s
        # chapter lists are derived from source/paras/ and made again
        # whenever that changes (lib/chapter_src.py), and a note under
        # markdown/ is a studio document (parseh-library)
        import bundle
        said = " ".join(version.what(f) for f in version.FORMATS)
        for kind, shape in bundle.SHAPE.items():
            for name in shape["files"]:
                if name.endswith(".json"):
                    self.assertIn(name, said, kind)
            for folder, exts in shape["dirs"].items():
                if ".json" in exts and folder not in ("source", bundle.NOTES_DIR):
                    self.assertIn("%s/*.json" % folder, said, kind)

    def test_read_from_the_tree_asked_about_without_running_it(self):
        with tempfile.TemporaryDirectory() as td:
            for fmt, (rel, _name, _what) in version.FORMATS.items():
                dest = Path(td, rel)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy(ROOT / rel, dest)
            # a tree whose modules would fail on import is still read
            Path(td, "serve.py").write_text(Path(td, "serve.py").read_text(encoding="utf-8")
                                            .replace("import threading\n", "raise SystemExit('ran')\n", 1),
                                            encoding="utf-8")
            prefs = Path(td, "lib", "prefs.py")
            prefs.write_text(prefs.read_text(encoding="utf-8").replace("STORE_FORMAT = 1", "STORE_FORMAT = 2"),
                             encoding="utf-8")
            bundle = Path(td, "lib", "bundle.py")
            bundle.write_text(bundle.read_text(encoding="utf-8").replace('"parseh-bundle/3"',
                                                                         '"parseh-bundle/4"'),
                              encoding="utf-8")
            theirs = version.formats(td)
            self.assertEqual((theirs["parseh-prefs"], theirs["parseh-bundle"]), (2, 4))
            ours = version.formats()
            self.assertEqual(version.lowered(theirs, ours), ["parseh-bundle", "parseh-prefs"])
            self.assertEqual(version.lowered(ours, theirs), [])
            self.assertEqual(version.lowered(ours, ours), [])
            # a store the other version has never heard of is not read there
            self.assertEqual(version.lowered(dict(ours, **{"parseh-new": 1}), ours), ["parseh-new"])
            # and a number that is not there is said, not guessed
            prefs.write_text(prefs.read_text(encoding="utf-8").replace("STORE_FORMAT = 2", "X = 2"),
                             encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no STORE_FORMAT at its top level"):
                version.formats(td)
            bundle.write_text(bundle.read_text(encoding="utf-8").replace('"parseh-bundle/4"',
                                                                         '"parseh-bundel/4"'),
                              encoding="utf-8")
            prefs.write_text(prefs.read_text(encoding="utf-8").replace("X = 2", "STORE_FORMAT = 2"),
                             encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "is not parseh-bundle/<number>"):
                version.formats(td)

    def test_the_command_line_prints_them_for_a_release_builder(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, str(ROOT / "lib" / "version.py"), "formats"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), version.formats())
        r = subprocess.run([sys.executable, str(ROOT / "lib" / "version.py")],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.stdout, V + "\n")


# ------------------------------------------------------------------ the changelog's reader
GOOD = """\
A preamble nobody reads.

## [a0.4.0] - unreleased
### Added
- a thing

## [a0.3.10] - 2026-10-02
### Fixed
- another

## [a0.3.9] - 2026-10-02
### Changed
- a third
"""


class TheChangelogsReader(unittest.TestCase):
    def test_sections_newest_first_with_their_days(self):
        got = changelog.parse(GOOD)
        self.assertEqual([(s.version, s.date, s.released) for s in got],
                         [("a0.4.0", None, False), ("a0.3.10", "2026-10-02", True),
                          ("a0.3.9", "2026-10-02", True)])
        self.assertEqual(got[0].body, "### Added\n- a thing")
        self.assertEqual(got[2].body, "### Changed\n- a third")
        self.assertEqual([s.line for s in got], [3, 7, 11])

    def test_a_heading_spelt_wrong_is_refused_not_skipped(self):
        for bad, said in (
                ("## [Unreleased]\n", "not a version's heading"),
                ("## a0.4.0 - 2026-10-01\n", "not a version's heading"),
                ("## [a0.4.0] – 2026-10-01\n", "not a version's heading"),
                ("## [a0.4.0] - 1 October 2026\n", "not a version's heading"),
                ("## [0.4.0a1] - 2026-10-01\n", "not a version"),
                ("## [a0.4.0-rc1] - unreleased\n", "a rehearsal's name, and a rehearsal has no "
                                                   "section of its own: it is a0.4.0's"),
                ("## [a0.4.0] - 2026-02-30\n", "not a day of the calendar"),
                ("## Notes\n", "not a version's heading")):
            with self.assertRaisesRegex(changelog.ChangelogError, said, msg=bad):
                changelog.parse(bad + GOOD)
            with self.assertRaisesRegex(changelog.ChangelogError, ":1: ", msg=bad):
                changelog.parse(bad + GOOD)

    def test_the_order_and_the_days_are_held(self):
        cases = (("## [a0.3.9] - unreleased\n## [a0.3.8] - 2026-01-01\n## [a0.3.7] - unreleased\n",
                  "only the top section may be unreleased"),
                 ("## [a0.3.9] - 2026-01-02\n## [a0.3.9] - 2026-01-01\n", "a0.3.9 has a section already"),
                 ("## [a0.3.9] - 2026-01-02\n## [a0.3.9.0] - 2026-01-01\n", "not earlier than it"),
                 ("## [a0.3.9] - 2026-01-02\n## [a0.3.10] - 2026-01-01\n", "not earlier than it"),
                 ("## [a0.3.9] - 2026-01-02\n## [a0.3.8] - 2026-01-03\n", "after a0.3.9 above it"),
                 ("# Changelog\nnothing yet\n", "no version's heading at all"))
        for text, said in cases:
            with self.assertRaisesRegex(changelog.ChangelogError, said, msg=text):
                changelog.parse(text)

    def test_a_day_is_said_the_way_the_guide_says_it(self):
        self.assertEqual(changelog.said("2026-09-24"), "24 September 2026")
        self.assertEqual(changelog.said("2027-01-05"), "5 January 2027")
        self.assertEqual(changelog.said(None), "not yet released")

    PAGE = ("---\ntitle: What changed\n---\n\n## a0.4.0 — not yet released\n\n### A thing\n\n"
            "```markdown\n## not a heading, an example\n```\n\n"
            "## a0.3.10 — 2 October 2026 {#a0310}\n\n## a0.3.9 — 1 October 2026\n\n"
            "## Before a0.3.9\n\nwhat came first\n")

    def test_the_guide_s_page_is_read_the_same_way(self):
        heads, before = changelog.whats_new(self.PAGE)
        self.assertEqual([(h.version, h.date, h.released, h.line) for h in heads],
                         [("a0.4.0", None, False, 5), ("a0.3.10", "2026-10-02", True, 13),
                          ("a0.3.9", "2026-10-01", True, 15)])
        self.assertEqual(before, "a0.3.9")
        # the day said back is the day read
        self.assertEqual([changelog.said(h.date) for h in heads],
                         ["not yet released", "2 October 2026", "1 October 2026"])
        self.assertEqual(changelog.whats_new(self.PAGE.replace("\n", "\r\n"))[0], heads)

    def test_the_guide_s_page_refuses_what_it_cannot_read(self):
        for old, new, said in (
                ("## a0.3.9 — 1 October 2026", "## a0.3.9 - 1 October 2026", "neither a version"),
                ("## a0.3.9 — 1 October 2026", "## a0.3.9 — 1 Oct 2026", "neither a day"),
                ("## a0.3.9 — 1 October 2026", "## a0.3.9 — 31 September 2026", "neither a day"),
                ("## a0.3.9 — 1 October 2026", "## a0.3.9 — soon", "neither a day"),
                ("## a0.3.9 — 1 October 2026", "## a0.3.9-rc1 — 1 October 2026", "rehearsal"),
                ("## a0.3.9 — 1 October 2026", "## v0.3.9 — 1 October 2026", "not a version"),
                ("what came first\n", "what came first\n\n## a0.3.8 — 1 September 2026\n",
                 "comes after 'Before a0.3.9'"),
                ("## Before a0.3.9", "## Before the start", "not a version")):
            with self.subTest(new=new):
                with self.assertRaisesRegex(changelog.ChangelogError, said):
                    changelog.whats_new(self.PAGE.replace(old, new))
        # and a page with no Before heading says so by None (the real page
        # is held to the changelog by tests/test_html_guide.py)
        self.assertIsNone(changelog.whats_new(self.PAGE.split("## Before")[0])[1])

    def test_the_real_changelog_reads_and_agrees_with_version(self):
        got = changelog.read()
        self.assertEqual(changelog.top(), got[0])
        self.assertEqual(changelog.find(got[-1].version), got[-1])
        with self.assertRaises(KeyError):
            changelog.find("a0.0.1")
        # VERSION names a version the changelog has: the one being made, or
        # the last one released -- and nothing released is newer than it
        mine = changelog.find(V)
        self.assertTrue(all(not s.released or version.compare(s.version, V) <= 0 for s in got))
        self.assertTrue(mine.body)


# ------------------------------------------------------------------ bundles from before
class OldBundlesStillInstall(unittest.TestCase):
    """Bundles stamped "Parseh/1.0" -- every bundle written before the version
    lived in one place -- install as they did.  The two here were written by
    a0.3.0's own lib/bundle.py and are kept byte for byte (fixtures README)."""

    def install(self, name, kind, dest):
        import bundle
        data = (OLD / name).read_bytes()
        man = json.loads(zipfile.ZipFile(io.BytesIO(data)).read(bundle.MANIFEST))
        self.assertEqual((man["format"], man["software"]), ("parseh-bundle/1", "Parseh/1.0"))
        self.assertNotEqual(bundle.SOFTWARE, "Parseh/1.0")
        with tempfile.TemporaryDirectory() as td:
            what = bundle.inspect(data, root=td)
            self.assertEqual((what["problems"], what["kind"], what["software"]), ([], kind, "Parseh/1.0"))
            done = bundle.install(data, root=td)
            self.assertEqual((done["ok"], done["kind"], done["dir"]), (True, kind, dest))
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for entry in z.namelist():
                    if entry == bundle.MANIFEST or entry.endswith("/"):
                        continue
                    rel = entry.split("/", 1)[1]
                    self.assertEqual(Path(td, dest, rel).read_bytes(), z.read(entry), entry)
            # and again, over itself, when replacing is asked for
            again = bundle.install(data, replace=True, root=td)
            self.assertEqual((again["ok"], again["replaced"]), (True, dest))

    def test_a_book(self):
        self.install("mini-en-book.zip", "book", "books/english/mini-en")

    def test_a_video(self):
        self.install("eN5wX7zA9bC-video.zip", "video", "youtube/videos/english/eN5wX7zA9bC")


if __name__ == "__main__":
    unittest.main()
