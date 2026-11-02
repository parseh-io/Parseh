#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server tests/analysis_door.mjs drives: Parseh's real handler, its real Settings -> Linguistic
analysis page and routes, on a TEMPORARY tree.

    python3 tests/analysis_harness.py                 fake analyzers, no network
    python3 tests/analysis_harness.py --as-phone      the same, for another device let in
    python3 tests/analysis_harness.py --real <folder> the real analyzers, really fetched into <folder>
                                                      and kept there: nothing in config/ is touched

Prints `READY {json}` once listening.  SIGTERM removes the temp tree."""
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
import analysispins     # noqa: E402
import analyzer         # noqa: E402
import getanalysis      # noqa: E402
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
REAL = sys.argv[sys.argv.index("--real") + 1] if "--real" in sys.argv[1:] else ""
tmp = Path(tempfile.mkdtemp(prefix="parseh-analysis-door-test-"))
network.STORE = str(tmp / "config" / "network.json")
prefs.STORE = str(tmp / "config" / "prefs.json")
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
prompts.STORE = str(tmp / "config" / "prompts.json")
latexthemes.STORE = str(tmp / "config" / "latex.json")
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")
speechconfig.CONFIG = tmp / "config" / "speech.json"
analysisconfig.STORE = str(tmp / "config" / "analysis.json")
getanalysis.FOLDER = REAL or str(tmp / "analysis")
serve.Handler.log_request = lambda self, *a, **k: None
serve.Handler.log_message = lambda self, *a: None
if AS_PHONE:
    for patched in (mock.patch.object(network, "where", lambda ip, doc=None: network.LAN),
                    mock.patch.object(network, "may_connect", lambda ip, doc=None: True),
                    mock.patch.object(network, "let_in", lambda *a, **k: True)):
        patched.start()


LEMMAS = {"Männer": "mann"}


class FakeBackend:
    """What getanalysis would register, reading the folder as it does and answering from no program."""
    def __init__(self, name, codes):
        self.name, self.codes = name, codes

    def languages(self):
        return self.codes

    def status(self, code):
        have = getanalysis.package_here(self.name)
        if self.name == "udpipe":
            have = have and getanalysis.model_here(code)
        return {"package": have, "resource": have, "usable": have, "loaded": False, "version": "fake",
                "resource_id": "fake", "why": "" if have else "not here"}

    def analyze(self, code, text, syntax=False, context=""):
        spans = analyzer.source_tokens(text)
        tokens = []
        for i, (s, e) in enumerate(spans):
            word = analyzer.Word(id="s0.w%d" % (i + 1), token="t%d" % i, source=self.name, status=analyzer.CONTEXTUAL,
                                 lemma=LEMMAS.get(text[s:e], text[s:e].lower()), upos="NOUN", start=s, end=e, surface=text[s:e])
            tokens.append(analyzer.Token(id="t%d" % i, start=s, end=e, surface=text[s:e], sentence="s0", words=(word,)))
        return analyzer.Result(language=code, text=text, outcome=analyzer.OK, backend=self.name,
                               sentences=(("s0", 0, len(text)),), tokens=tuple(tokens))


def fake_build(items, say=print):
    """Each item as the real one leaves it, with a pause to be seen in, and a failure on asking for Hindi."""
    release.wait(10)
    if "udpipe:hi" in items:
        raise getanalysis.AnalysisError("pip stopped: a fake failure")
    site = os.path.join(getanalysis.runtime_dir(), "lib", "python3.12", "site-packages")
    for item in items:
        name = item.split(":")[0]
        for d in analysispins.PACKAGES[name]:
            os.makedirs(os.path.join(site, d), exist_ok=True)
        if ":" in item:
            code = item.split(":")[1]
            os.makedirs(getanalysis.models_dir(), exist_ok=True)
            with open(getanalysis.model_path(code), "wb") as f:
                f.truncate(analysispins.UDPIPE_MODELS[code]["bytes"])


def small_dictionary():
    """A real small dictionary for the lookup route: `andare` is found only under its lemma."""
    import lookup
    lookup.DICT_DIR = str(tmp / "dict")
    c = lookup.create(os.path.join(lookup.DICT_DIR, "de.db"))
    cur = c.execute("INSERT INTO entry (headword, translit, ipa, pos, sense, sense_tags) VALUES (?,?,?,?,?,?)",
                    ("mann", "", "", "noun", "man", ""))
    c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)", ("mann", cur.lastrowid, ""))
    c.commit()
    c.close()


small_dictionary() if not REAL else None
release = threading.Event()
release.set()
if not REAL:
    getanalysis.build = fake_build
    analyzer.reset([FakeBackend("udpipe", tuple(analysispins.UDPIPE_MODELS)), FakeBackend("farahidi", ("ar",)),
                    FakeBackend("starlang", ("tr",))])


def command(line):
    c = json.loads(line)
    what = c.get("cmd")
    if what == "hold":
        release.clear()
    elif what == "release":
        release.set()
    elif what == "lookup":
        # the one call the book's __lookup and the player's api/lookup both make, on its real body
        h = serve.Handler.__new__(serve.Handler)
        h.send_json = lambda out, code=200: out
        return h._lookup("de", {"text": c["text"], "sentence": c.get("sentence", "")}, "en")["words"]
    elif what == "choices":
        return analysisconfig.load()
    else:
        raise ValueError("no such command: %r" % what)
    return None


def main():
    srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("READY " + json.dumps({"port": srv.server_address[1], "folder": getanalysis.FOLDER, "real": bool(REAL)}), flush=True)

    def bye(*_a):
        getanalysis.stop_worker()
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
