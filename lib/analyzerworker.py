#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The one program that imports the analyzers: UDPipe, Farahidi, Starlang.

    analysis/runtime/bin/python -I -u lib/analyzerworker.py <folder of the models>

lib/getanalysis.py starts it in the environment it made, the first time somebody
asks for an analysis, and stops it when nobody has for a while.  One JSON object
a line on each pipe, one answer for each request:

    {"op": "analyze", "backend": "udpipe", "code": "de", "text": "...", "syntax": true, "context": ""}
    {"op": "status", "backend": "udpipe", "code": "de"}

A program of its own because Starlang's modules are called `Math`, `Util` and
`Dictionary`, because a native library that falls over must not take the server
with it, and because this much memory (half a gigabyte with Farahidi's language
model) goes back to the machine when the program ends.

The environment's packages come first on the path and lib/ last, so that nothing
of Parseh's can stand in for a package of theirs.  Nothing here reads or writes
anything but the model files.
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import analyzer            # noqa: E402
import analyzer_farahidi   # noqa: E402
import analyzer_starlang   # noqa: E402
import analyzer_udpipe     # noqa: E402


def serve(models, stdin, stdout):
    backends = {"udpipe": analyzer_udpipe.Backend(models),
                "farahidi": analyzer_farahidi.Backend(),
                "starlang": analyzer_starlang.Backend()}
    for line in stdin:
        out = {"ok": False, "error": "no such request"}
        try:
            ask = json.loads(line)
            b = backends.get(ask.get("backend"))
            if b is not None and ask.get("op") == "status":
                out = {"ok": True, "status": b.status(ask.get("code"))}
            elif b is not None and ask.get("op") == "analyze":
                got = b.analyze(ask["code"], ask["text"], bool(ask.get("syntax")), ask.get("context") or "")
                out = {"ok": True, "result": analyzer.to_plain(got),
                       "loaded": {name: list(x.loaded()) for name, x in backends.items()}}
        except analyzer.BackendError as e:
            out = {"ok": False, "error": str(e)}
        except Exception as e:      # what the server has to be told, in place of a silent pipe
            out = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
        stdout.write(json.dumps(out, ensure_ascii=True) + "\n")
        stdout.flush()


if __name__ == "__main__":
    serve(sys.argv[1] if len(sys.argv) > 1 else ".", sys.stdin, sys.stdout)
