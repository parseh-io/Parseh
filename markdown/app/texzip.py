# SPDX-License-Identifier: GPL-3.0-or-later
"""A document's LaTeX as a zip that compiles anywhere: Overleaf, another computer, a printer's.

The `.tex` a document downloads as is one file, and it cannot be compiled alone: it includes the document's pictures
(`images/…`), the LaTeX drawings its latex blocks became (`latex/<key>.pdf`) and the fonts it asks for (`fonts/…`).  This
zip carries those beside it, laid out as the build had them, so that

    * `main.tex` compiles at once with XeLaTeX (Overleaf: Menu, Compiler, XeLaTeX);
    * every drawing is there TWICE: the compiled `latex/<key>.pdf` main.tex includes, and the `latex/<key>.tex` it was
      compiled from, which is the file to change to change the drawing -- compile it, put the PDF in its place;
    * the fonts come with their licence, as every font Parseh gives away does (lib/fonts/README.md).

It is what the LAST BUILD made, as the plain .tex is (both are greyed out until a PDF has been built): the folder it is
read from is the studio's own `build/`, never anything the page sends.
"""
import io
import os
import re
import zipfile
from pathlib import Path

import htmlgen
import latexdraw
import store

# what main.tex (and a drawing's own source) says of a file it includes: a path under images/ or latex/
REFERENCE = re.compile(r"(?<![\w/])(images|latex)/([^\s{}\\%\[\],]+)")
DRAWING_PDF = re.compile(r"^([0-9a-f]{64})\.pdf$")
FONT_FILES = (".ttf", ".otf")
LICENCES = (("OFL.txt", ("noto", "vazir")), ("GUST-FONT-LICENSE.txt", ("texgyre",)))   # the licence file, the faces under it


class NotBuilt(Exception):
    """There is no LaTeX yet: a PDF has to be built first."""


def _inside(folder, name):
    """folder/name, if it is a file that really is inside `folder`."""
    try:
        path = (folder / name).resolve()
        path.relative_to(folder.resolve())
    except (ValueError, OSError):
        return None
    return path if path.is_file() else None


def _readme(title, drawings, lost, fonts, images):
    lines = ["%s -- LaTeX, from Parseh" % title, "",
             "main.tex   the document. Compile it with XeLaTeX.",
             "           In Overleaf: upload this zip as a project, then Menu > Compiler > XeLaTeX."]
    if images:
        lines.append("images/    the pictures main.tex includes.")
    if drawings or lost:
        lines.append("latex/     the LaTeX drawings of the document, each as a PDF and as the LaTeX it was made from (see below).")
    lines.append("fonts/     the fonts main.tex asks for, with their licence." if fonts else
                 "           (no font of Parseh's is asked for: it is set in fonts every TeX has.)")
    lines.append("")
    if drawings:
        lines += ["THE DRAWINGS",
                  "main.tex includes each drawing as a compiled PDF, latex/<key>.pdf, so that it compiles anywhere. The LaTeX each",
                  "was compiled from is beside it, latex/<key>.tex. To change a drawing, change its .tex, compile it with the",
                  "compiler named here (a file of its own, not a part of main.tex), and put the PDF it makes in place of the old one.", ""]
        for key, theme, compiler in drawings:
            lines.append("  latex/%s.tex   theme \"%s\", compiled with %s" % (key, theme or "default", compiler))
        lines.append("")
    if lost:
        lines += ["WITHOUT THEIR LaTeX",
                  "The document changed after this PDF was built, so the LaTeX of these drawings could not be found; their PDFs are here:", ""]
        lines += ["  latex/%s.pdf" % key for key in lost] + [""]
    lines += ["This is what the last PDF was built from. Changing the document afterwards, in Parseh, is not in it: build the PDF again."]
    return "\n".join(lines) + "\n"


def tex_zip(doc_id, title, markdown):
    """-> the zip's bytes.  Raises NotBuilt when no PDF was ever built."""
    build = store.doc_dir(doc_id) / "build"
    main = build / "main.tex"
    if not main.is_file():
        raise NotBuilt()
    tex = main.read_text(encoding="utf-8")
    out = {}                    # name in the zip -> bytes
    out["main.tex"] = tex.encode("utf-8")

    # the pictures and drawings main.tex names, each only if the build really has it
    used = {"images": set(), "latex": set()}
    for kind, name in REFERENCE.findall(tex):
        used[kind].add(name)
    for name in sorted(used["images"]):
        path = _inside(build / "images", name)
        if path:
            out["images/" + name] = path.read_bytes()
    keys = []
    for name in sorted(used["latex"]):
        m = DRAWING_PDF.match(name)
        path = _inside(build / "latex", name) if m else None
        if path:
            out["latex/" + name] = path.read_bytes()
            keys.append(m.group(1))

    # the LaTeX each drawing was compiled from: planned again from the document, which gives the same key for the same drawing
    sources, drawings = {}, []
    wanted = set(keys)
    for block, theme, inline in htmlgen.latex_wanted(markdown):
        plan = latexdraw.plan(block, theme, inline=inline)
        if plan["ok"] and plan["key"] in wanted and plan["key"] not in sources:
            sources[plan["key"]] = latexdraw.source(block, plan["resolved"])
            drawings.append((plan["key"], plan["resolved"]["name"], plan["resolved"]["compiler"]))
            out["latex/%s.tex" % plan["key"]] = sources[plan["key"]].encode("utf-8")
    lost = [key for key in keys if key not in sources]

    # the fonts any of those files names, and the licences they travel with
    text = tex + "\n".join(sources.values())
    fonts = []
    folder = build / "fonts"
    for name in sorted(os.listdir(folder)) if folder.is_dir() else ():
        path = _inside(folder, name)
        if path and name.lower().endswith(FONT_FILES) and name in text:
            out["fonts/" + name] = path.read_bytes()
            fonts.append(name)
    for licence, families in LICENCES:
        if any(f.lower().startswith(families) for f in fonts):
            path = _inside(Path(latexdraw.FONTS), licence)
            if path:
                out["fonts/" + licence] = path.read_bytes()

    out["README.txt"] = _readme(title, drawings, lost, fonts, any(n.startswith("images/") for n in out)).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ["main.tex", "README.txt"] + sorted(n for n in out if n not in ("main.tex", "README.txt")):
            zf.writestr(name, out[name])
    return buf.getvalue()
