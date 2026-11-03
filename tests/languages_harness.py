#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parseh's REAL handler for Settings -> Languages (lib/languagespage.py) on a temporary tree, for
tests/languages_door.mjs.

Everything the page may write goes to the temporary folder and nowhere else: this machine's
language table (config/languages.json), the language files (copies of lib/lang/, docs/lang/ and the
studio's starters, so that Parseh's own languages are still read and a new one is written beside
them), the three content folders newlang.py makes, and lib/langs.css, which languages.reload()
would write again.  Prints READY {port}; reads one JSON command a line: {"what": "features",
"code": ...} -> the language's features, {"what": "files", "code": ...} -> which of its files exist.
"""
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", ".", "tests"):
    sys.path.insert(0, str(ROOT / p))
import analysisconfig   # noqa: E402
import langfeatures     # noqa: E402
import langprompts      # noqa: E402
import languages        # noqa: E402
import latexthemes      # noqa: E402
import network          # noqa: E402
import newlang          # noqa: E402
import offline          # noqa: E402
import prefs            # noqa: E402
import prompts          # noqa: E402
import serve            # noqa: E402
import speechconfig     # noqa: E402

AS_PHONE = "--as-phone" in sys.argv[1:]
tmp = Path(tempfile.mkdtemp(prefix="parseh-languages-door-test-"))
network.STORE = str(tmp / "config" / "network.json")
prefs.STORE = str(tmp / "config" / "prefs.json")
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
prompts.STORE = str(tmp / "config" / "prompts.json")
latexthemes.STORE = str(tmp / "config" / "latex.json")
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")
speechconfig.CONFIG = tmp / "config" / "speech.json"
analysisconfig.STORE = str(tmp / "config" / "analysis.json")
# the language files: copies, so that a new language is written beside Parseh's own and Parseh's own are read
LANG, DOCS, STARTERS = tmp / "lib-lang", tmp / "docs-lang", tmp / "starters"
shutil.copytree(ROOT / "lib" / "lang", LANG)
shutil.copytree(ROOT / "docs" / "lang", DOCS)
shutil.copytree(ROOT / "markdown" / "exlex" / "starters", STARTERS)
newlang.LANG_TEX, newlang.LANG_DOCS = str(LANG), str(DOCS)
langprompts.LANG_FILES, langprompts.LANG_DOCS, langprompts.STARTERS = str(LANG), str(DOCS), str(STARTERS)
langfeatures.LANG_FILES, langfeatures.LANG_DOCS, langfeatures.STARTERS = str(LANG), str(DOCS), str(STARTERS)
newlang.content_dirs = lambda folder: [str(tmp / door / folder) for door in ("books", "videos", "library")]
languages.write_css = lambda path=None: str(tmp / "langs.css")
serve.Handler.log_request = lambda self, *a, **k: None
serve.Handler.log_message = lambda self, *a: None
if AS_PHONE:
    for patched in (mock.patch.object(network, "where", lambda ip, doc=None: network.LAN),
                    mock.patch.object(network, "may_connect", lambda ip, doc=None: True),
                    mock.patch.object(network, "let_in", lambda *a, **k: True)):
        patched.start()


def command(line):
    c = json.loads(line)
    what = c.get("what")
    if what == "features":
        return [f.as_json() for f in langfeatures.features(c["code"])]
    if what == "files":
        code = c["code"]
        return {"tex": (LANG / (code + ".tex")).is_file(), "md": (DOCS / (code + ".md")).is_file(),
                "chunk": (LANG / (code + ".chunk.json")).is_file(),
                "row": code in languages.read_store(languages.PERSONAL),
                "checkout": (ROOT / "lib" / "lang" / (code + ".tex")).exists()
                            or (ROOT / "docs" / "lang" / (code + ".md")).exists()}
    raise ValueError("no such command: %r" % what)


def main():
    srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("READY " + json.dumps({"port": srv.server_address[1]}), flush=True)

    def bye(*_a):
        shutil.rmtree(tmp, ignore_errors=True)
        os._exit(0)
    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)
    for line in sys.stdin:
        try:
            out = command(line)
            print("OK" + ((" " + json.dumps(out)) if out is not None else ""), flush=True)
        except Exception as e:      # noqa: BLE001
            print("ERR %s" % e, flush=True)
    bye()


if __name__ == "__main__":
    main()
