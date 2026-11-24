# SPDX-License-Identifier: GPL-3.0-or-later
"""A temporary Parseh tree for the sync foundations' tests (tests/test_sync_*.py).

Every store the change log looks at is pointed into a fresh temporary folder
for as long as one test runs -- the shelves (lib/syncunits.py SHELVES), the
personal config stores (prefs, prompts, latex, analysis, speech, languages)
and the language files -- so nothing here reads the checkout's shelves or
writes its config/ (tests/configguard.py).  config/sync/ follows prefs.STORE.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIB = os.path.join(ROOT, "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import analysisconfig   # noqa: E402
import langprompts      # noqa: E402
import languages        # noqa: E402
import latexthemes      # noqa: E402
import prefs            # noqa: E402
import prompts          # noqa: E402
import speechconfig     # noqa: E402
import synclock         # noqa: E402
import synclog          # noqa: E402
import synctouch        # noqa: E402
import syncunits        # noqa: E402

_PATCH = ((prefs, "STORE", "config/prefs.json"), (prompts, "STORE", "config/prompts.json"),
          (latexthemes, "STORE", "config/latex.json"), (analysisconfig, "STORE", "config/analysis.json"),
          (speechconfig, "CONFIG", "config/speech.json"), (languages, "PERSONAL", "config/languages.json"),
          (langprompts, "LANG_FILES", "lib/lang"), (langprompts, "LANG_DOCS", "docs/lang"),
          (langprompts, "STARTERS", "markdown/exlex/starters"))


class SyncTree(unittest.TestCase):
    """setUp makes the tree; self.t is its root; self.w(rel, text) writes a file."""

    def setUp(self):
        self.t = tempfile.mkdtemp(prefix="parseh-sync-")
        self._was = []
        for mod, attr, rel in _PATCH:
            self._was.append((mod, attr, getattr(mod, attr)))
            p = os.path.join(self.t, *rel.split("/"))
            setattr(mod, attr, type(getattr(mod, attr))(p) if not isinstance(getattr(mod, attr), str) else p)
        self._shelves = dict(syncunits.SHELVES)
        for k, rel in (("books", "books"), ("videos", "youtube/videos"), ("anki", "youtube/anki"),
                       ("library", "markdown/library"), ("exercises", "exercises"), ("clips", "clips")):
            syncunits.SHELVES[k] = os.path.join(self.t, *rel.split("/"))
            os.makedirs(syncunits.SHELVES[k])
        os.makedirs(os.path.join(self.t, "config"))
        synclog.close()
        synclog.HOME = None
        synctouch.drain()

    def tearDown(self):
        synclog.close()
        synctouch.drain()
        for mod, attr, v in self._was:
            setattr(mod, attr, v)
        syncunits.SHELVES.clear()
        syncunits.SHELVES.update(self._shelves)
        with synclock._LOCK:
            synclock._LEASES.clear()
            synclock._WRITING.clear()
        shutil.rmtree(self.t, ignore_errors=True)

    def p(self, rel):
        return os.path.join(self.t, *rel.split("/"))

    def w(self, rel, text="x", binary=False):
        p = self.p(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return p

    def wj(self, rel, doc):
        return self.w(rel, json.dumps(doc, ensure_ascii=False))

    def ids(self):
        return sorted(u.id for u in syncunits.walk())
