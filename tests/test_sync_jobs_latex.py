# SPDX-License-Identifier: GPL-3.0-or-later
"""A studio document's PDF and the LaTeX drawings no computer made yet, lent
to a paired computer (lib/syncjobs.py "doc-build" and "latex-draw", a0.7.0
lane J; docs/sync.md "Jobs").

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_jobs_latex.py

Two installs in one process (tests/syncfake.py).  B has no TeX; A has.

  * "doc-build": the studio's build_pdf on A is stood in for by a DOC_BUILD
    that does what its end does -- writes build/main.pdf and main.tex, says in
    meta.json that it built (store.set_build) and records its source
    (syncbuilds.record).  The rest is real: the offer, A holding B's version,
    the PDF and .tex back as files, meta.json back through the exchange, and
    the record of the source on B.
  * "latex-draw": the REAL runner and the real lib/latexdraw.py on both
    sides; only TeX itself is stood in for (latexdraw.compiler answers for A
    alone, and _compile writes a drawing as a compile does).
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_sync_jobs import Jobs  # noqa: E402
import latexdraw                 # noqa: E402
import latexthemes               # noqa: E402
import store                     # noqa: E402
import syncbuilds as SB          # noqa: E402
import syncjobs as J             # noqa: E402
import syncunits                 # noqa: E402

DOC = "doc:english/a-doc"
D = "markdown/library/english/a-doc/"
MD = ("---\ntitle: A doc\ntarget: en\n---\n\nText.\n\n::::latex\n\\draw (0,0) -- (1,1);\n::::\n\n"
      "::::latex\n\\draw (0,0) circle (1);\n::::\n")
TEX = {"path": "/usr/bin/tex", "version": "TeX 3.14", "miktex": False}


def doc(inst):
    inst.w(D + "source.md", MD)
    inst.w(D + "meta.json", json.dumps({"id": "a-doc", "title": "A doc"}))
    return DOC


def fake_build_pdf(folder, args):
    """What studio.build_pdf leaves behind, on the computer it ran on."""
    doc_id = os.path.basename(folder)
    os.makedirs(os.path.join(folder, "build"), exist_ok=True)
    with open(os.path.join(folder, "build", "main.pdf"), "wb") as fh:
        fh.write(b"%PDF built on " + J.syncid.name().encode() + b" at scale %.2f\n" % args["scale"])
    with open(os.path.join(folder, "build", "main.tex"), "w") as fh:
        fh.write("\\documentclass{exlex}\n")
    with open(os.path.join(folder, "build", "main.aux"), "w") as fh:
        fh.write("never travels\n")
    build = store.set_build(doc_id, {"status": "ok", "scale": args["scale"], "pages": 1})["build"]
    SB.record(folder, ["pdf"])
    return build


class DocBuild(Jobs):
    def setUp(self):
        super().setUp()
        self.was_build = J.DOC_BUILD
        J.DOC_BUILD = fake_build_pdf
        J.CAPS_FORCE[self.A.id]["compilers"] = ["lualatex", "xelatex"]
        J.CAPS_FORCE[self.B.id]["compilers"] = []
        self.switch(self.B, send=True)
        self.switch(self.A, accept=True)

    def tearDown(self):
        J.DOC_BUILD = self.was_build
        super().tearDown()

    def test_who_can_build_a_documents_pdf(self):
        with self.on(self.B):
            can, why = J.can_here("doc-build", {})
            self.assertFalse(can)
            self.assertIn("XeLaTeX", why)
            self.assertEqual([(p["id"], p["can"]) for p in J.who_can("doc-build", {})], [(self.A.id, True)])
        with self.on(self.A):
            self.assertEqual(J.can_here("doc-build", {}), (True, ""))

    def test_the_pdf_built_on_A_arrives_on_B_with_the_source_it_was_built_from(self):
        doc(self.B)
        with self.on(self.B):
            jid = J.ask("doc-build", {"scale": 1.6, "size": 11, "mono": False}, "Build the PDF of “A doc”",
                        unit=DOC, prefer=self.A.id)["id"]
        self.step(self.B, 5)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "done", st)
        self.assertEqual(st["result"]["build"]["status"], "ok", st)
        self.assertEqual(self.B.read(D + "build/main.pdf"), b"%PDF built on A at scale 1.60\n")
        self.assertEqual(self.B.read(D + "build/main.tex"), b"\\documentclass{exlex}\n")
        self.assertFalse(os.path.exists(self.B.p(D + "build/main.aux")), "only the PDF part travels")
        # meta.json, which says it was built, came back through the exchange
        meta = json.loads(self.B.read(D + "meta.json"))
        self.assertEqual((meta["build"]["status"], meta["build"]["scale"]), ("ok", 1.6), meta)
        with self.on(self.B):
            u = syncunits.locate(DOC)
            rec = SB.read_record(u)
            self.assertEqual(rec["pdf"]["source"], SB.source_hash(u), "the PDF names B's source as it is now")
            self.assertFalse(SB.is_out_of_date(DOC))
            self.assertEqual(J.waiting_here(), [])

    def test_a_build_that_fails_on_A_comes_back_in_words(self):
        doc(self.B)
        J.DOC_BUILD = lambda folder, args: {"status": "error", "error": "! Undefined control sequence."}
        with self.on(self.B):
            jid = J.ask("doc-build", {"scale": 1.5}, "Build", unit=DOC)["id"]
        self.step(self.B, 5)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "failed", st)
        self.assertIn("Undefined control sequence", st["reason"])
        self.assertFalse(os.path.exists(self.B.p(D + "build/main.pdf")))


class LatexDraw(Jobs):
    def setUp(self):
        super().setUp()
        self.was_tex = (latexdraw.compiler, latexdraw._compile, dict(latexdraw._TOOLS))
        a_root = self.A.root

        def compiler(name, fresh=False):         # TeX on A alone
            return dict(TEX) if latexdraw.DRAWN.startswith(a_root) else None

        def compile_(tex, resolved, info, key, limit, inline=False, preview=False):
            p = latexdraw.paths(key, preview)
            meta = {"w": 20.0, "h": 10.0, "compiler": resolved["compiler"], "theme": resolved["name"]}
            latexdraw._write_atomic(p["pdf"], b"%PDF drawing of " + tex.encode())
            latexdraw._write_atomic(p["svg"], ("<svg><!-- %s --></svg>" % tex).encode())
            latexdraw._write_atomic(p["tex"], tex.encode())
            latexdraw._write_atomic(p["meta"], json.dumps(meta).encode())
            latexdraw._alias(latexdraw.content_key(tex, resolved, inline), key, resolved["compiler"])
            return latexdraw._ok(key, meta, preview)
        latexdraw.compiler = compiler
        latexdraw._compile = compile_
        J.CAPS_FORCE[self.A.id]["compilers"] = list(latexthemes.COMPILERS)
        J.CAPS_FORCE[self.B.id]["compilers"] = []
        self.switch(self.B, send=True)
        self.switch(self.A, accept=True)

    def tearDown(self):
        latexdraw.compiler, latexdraw._compile = self.was_tex[:2]
        latexdraw._TOOLS.clear()
        latexdraw._TOOLS.update(self.was_tex[2])
        latexdraw._FAILED.clear()
        super().tearDown()

    def missing(self):
        """What the studio's door finds on B (markdown/app/server.py _undrawable): the blocks whose
        compiler B lacks, by their content keys."""
        out = []
        for block in latexthemes.blocks_in(MD):
            p = latexdraw.plan(block["tex"], block["theme"])
            self.assertEqual((p["ok"], p["kind"]), (False, "compiler"))
            resolved = latexthemes.resolve(block["theme"])
            out.append({"tex": block["tex"], "theme": block["theme"], "inline": False,
                        "ck": latexdraw.content_key(block["tex"], resolved), "compiler": resolved["compiler"]})
        return out

    def test_the_drawings_nobody_made_are_made_on_A_and_found_on_B_by_their_content(self):
        doc(self.B)
        with self.on(self.B):
            blocks = self.missing()
            self.assertEqual(len(blocks), 2)
            args = {"blocks": blocks}
            self.assertFalse(J.can_here("latex-draw", args)[0])
            self.assertEqual([(p["id"], p["can"]) for p in J.who_can("latex-draw", args)], [(self.A.id, True)])
            jid = J.ask("latex-draw", args, "Draw the LaTeX of “A doc”", prefer=self.A.id)["id"]
        self.step(self.B, 4)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "done", st)
        self.assertEqual(sorted(st["result"]["drawn"]), sorted(b["ck"] for b in blocks))
        self.assertEqual(st["result"]["failed"], {})
        with self.on(self.B):
            for block in latexthemes.blocks_in(MD):
                pl = latexdraw.plan(block["tex"], block["theme"])
                self.assertEqual((pl["ok"], pl.get("elsewhere")), (True, True), pl)
                drawn = latexdraw.draw(block["tex"], block["theme"])
                self.assertEqual((drawn["ok"], drawn["w"]), (True, 20.0), drawn)
                self.assertTrue(drawn["svg"].startswith(self.B.root), "filed in B's own markdown/latex/")
                with open(drawn["svg"], "rb") as fh:
                    self.assertEqual(fh.read(), ("<svg><!-- %s --></svg>" % block["tex"]).encode())
                with open(latexdraw.paths(drawn["key"])["tex"], "rb") as fh:
                    self.assertEqual(fh.read(), block["tex"].encode())
        with self.on(self.A):
            self.assertEqual(J.jobs(), [], "the finished job was dropped on A once its result was here")

    def test_a_block_whose_theme_differs_on_A_is_said_and_the_others_still_come(self):
        doc(self.B)
        with self.on(self.B):
            blocks = self.missing()
        blocks[1]["ck"] = "0" * 64                  # B's theme resolves this block to another content
        with self.on(self.B):
            jid = J.ask("latex-draw", {"blocks": blocks}, "Draw")["id"]
        self.step(self.B, 4)
        st = self.state(self.B, jid)
        self.assertEqual(st["state"], "done", st)
        self.assertEqual(list(st["result"]["drawn"]), [blocks[0]["ck"]])
        self.assertIn("is not the same on A", st["result"]["failed"]["0" * 64])

    def test_a_partner_without_the_compiler_is_never_offered_it(self):
        J.CAPS_FORCE[self.A.id]["compilers"] = []
        doc(self.B)
        with self.on(self.B):
            args = {"blocks": self.missing()}
            self.assertEqual([p["can"] for p in J.who_can("latex-draw", args)], [False])
            jid = J.ask("latex-draw", args, "Draw")["id"]
        self.step(self.B, 3)
        self.assertEqual(self.state(self.B, jid)["state"], "waiting")


if __name__ == "__main__":
    unittest.main(verbosity=2)
