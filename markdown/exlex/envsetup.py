# SPDX-License-Identifier: GPL-3.0-or-later
"""envsetup — make a bare container able to build exlex documents.

Idempotent; every step checks before acting.  Three concerns:

  1. python deps  : pymupdf (verification), fontTools+brotli (only if
                    the fonts ever need re-deriving from .woff2);
  2. fonts        : the TTFs a build carries with it live in assets/fonts.
                    They are copied from the toolbox's own lib/fonts first
                    (Vazirmatn, Noto Naskh Arabic, Noto Nastaliq Urdu travel
                    with Parseh, so a machine with no network still builds);
                    only what is still missing afterwards is fetched -- the
                    official Vazirmatn release zip, whose .woff2 is
                    decompressed (no TeX engine reads woff2).  Japanese and
                    Chinese use the system's CJK fonts, nothing bundled;
  3. hyphenation  : Italian patterns are NOT in every TeX Live.  XeTeX
                    can only load patterns at format-build time, so we
                    install assets/hyph into the user texmf tree,
                    register the language, and rebuild the xelatex
                    format once.  The loader must set
                    \\lccode"0027="0027 (apostrophe) or INITEX dies
                    with "! Nonletter." — see README, "Hyphenation".
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB_FONTS = HERE.parent.parent / "lib" / "fonts"
# what a build's fonts/ must hold: the file name in assets/fonts and the
# name it has in lib/fonts (the nastaliq TTF keeps the short name the
# template has always used)
FONT_FILES = ["Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf"]
BUNDLED = {
    "Vazirmatn-Regular.ttf": "Vazirmatn-Regular.ttf",
    "Vazirmatn-Bold.ttf": "Vazirmatn-Bold.ttf",
    "NotoNaskhArabic-Regular.ttf": "NotoNaskhArabic-Regular.ttf",
    "NotoNaskhArabic-Bold.ttf": "NotoNaskhArabic-Bold.ttf",
    "NotoNastaliqUrdu.ttf": "NotoNastaliqUrdu-Regular.ttf",
}
VAZIR_ZIP = ("https://github.com/rastikerdar/vazirmatn/releases/download/"
             "v33.003/vazirmatn-v33.003.zip")


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ensure_python_deps(verbose=True):
    for mod, pipname in [("pymupdf", "pymupdf")]:
        try:
            __import__(mod)
        except ImportError:
            if verbose:
                print(f"[envsetup] installing {pipname} ...")
            _run([sys.executable, "-m", "pip", "install", pipname,
                  "--break-system-packages", "-q"])


# One copy at a time in this process: the server's provisioning thread and
# every build's request thread call copy_bundled_fonts, and on a fresh
# install they all find the same files missing.
_COPY_LOCK = threading.Lock()


def _place(dst, write):
    """Make the font file dst whole or not at all: `write` fills a temporary
    file of its own beside dst's folder (assets/, not assets/fonts/, which
    a build copies whole), and that is renamed into place."""
    fd, part = tempfile.mkstemp(prefix=".font-", suffix=".part", dir=str(dst.parent.parent))
    os.close(fd)
    try:
        write(part)
        try:
            os.replace(part, dst)
        except OSError:
            # another process put it there first (Windows refuses to replace
            # a file a build is copying): it is there
            if not dst.exists():
                raise
    finally:
        if os.path.exists(part):
            os.unlink(part)


def copy_bundled_fonts(verbose=True):
    """Copy every bundled face lib/fonts has into assets/fonts, when not
    already there.  Offline first: this is where a build's fonts come
    from on any machine that has the toolbox.

    Every TrueType file of lib/fonts goes, under its own name unless
    BUNDLED gives it another.  The generator asks lib/fonts which faces the
    toolbox carries (texgen.bundled_font_files) and writes the build's
    ./fonts/ path for them; a face missing from this table was then missing
    from the build: Hindi's Noto Serif Devanagari was, and a Hindi PDF was
    set in whatever Devanagari face the system had, or in none.

    A build copies assets/fonts whole into its own folder, so a file there
    is either whole or absent (_place), and the copies are made one caller
    at a time.  A shared `<name>.part` in the folder raced: of six Hindi
    builds at once on a fresh install, one crashed in copytree on a .part
    another had just renamed, or one copied the folder before Noto Serif
    Devanagari was in it and was set in Noto Sans."""
    fdir = HERE / "assets" / "fonts"
    fdir.mkdir(parents=True, exist_ok=True)
    names = dict(BUNDLED)
    renamed = set(BUNDLED.values())
    for src in sorted(LIB_FONTS.glob("*.ttf")):
        if src.name not in renamed:
            names.setdefault(src.name, src.name)
    with _COPY_LOCK:
        for dst_name, src_name in names.items():
            dst, src = fdir / dst_name, LIB_FONTS / src_name
            if dst.exists() or not src.exists():
                continue
            _place(dst, lambda part: shutil.copy(src, part))
            if verbose:
                print(f"[envsetup]   lib/fonts/{src_name} -> assets/fonts/{dst_name}")
    return fdir


def ensure_fonts(verbose=True):
    fdir = copy_bundled_fonts(verbose)
    if all((fdir / f).exists() for f in FONT_FILES):
        return fdir
    if verbose:
        print("[envsetup] fonts missing — fetching Vazirmatn release ...")
    for mod in ("fontTools", "brotli"):
        try:
            __import__(mod)
        except ImportError:
            _run([sys.executable, "-m", "pip", "install", mod.lower(),
                  "--break-system-packages", "-q"])
    import io
    import urllib.request
    import zipfile
    from fontTools.ttLib import TTFont
    data = urllib.request.urlopen(VAZIR_ZIP, timeout=120).read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    fdir.mkdir(parents=True, exist_ok=True)
    for name in FONT_FILES:
        w2 = name.replace(".ttf", ".woff2")
        member = next(m for m in zf.namelist()
                      if m.endswith("fonts/webfonts/" + w2))
        raw = zf.read(member)
        ft = TTFont(io.BytesIO(raw))
        ft.flavor = None
        _place(fdir / name, ft.save)
        if verbose:
            print(f"[envsetup]   {w2} -> {name}")
    return fdir


def _italian_registered():
    """Cheap probe: is \\l@italian defined in the xelatex format?"""
    probe = HERE / ".probe.tex"
    probe.write_text(
        "\\ifcsname l@italian\\endcsname\\message{EXLEX-IT-OK}\\fi\\csname"
        " @@end\\endcsname\\end\n", encoding="utf-8")
    ok = False
    r = _run(["xelatex", "-interaction=batchmode",
              "-output-directory", str(HERE), str(probe)])
    for ext in (".probe.log", ".probe.aux", ".probe.pdf", ".probe.tex"):
        p = HERE / ext
        if ext == ".probe.log" and p.exists():
            ok = "EXLEX-IT-OK" in p.read_text(errors="replace")
        if p.exists():
            p.unlink()
    return ok


def ensure_italian_hyphenation(verbose=True):
    if shutil.which("xelatex") is None:
        raise RuntimeError("xelatex not found — install TeX Live first")
    if _italian_registered():
        return True
    if verbose:
        print("[envsetup] Italian hyphenation not in format — installing ...")

    texmfhome = _run(["kpsewhich", "-var-value", "TEXMFHOME"]).stdout.strip()
    texmfcfg = _run(["kpsewhich", "-var-value", "TEXMFCONFIG"]).stdout.strip()
    pat_dst = Path(texmfhome) / "tex/generic/hyph-utf8/patterns/tex"
    pat_dst.mkdir(parents=True, exist_ok=True)
    for f in ("hyph-it.tex", "loadhyph-it.tex"):
        shutil.copy(HERE / "assets" / "hyph" / f, pat_dst / f)

    sysdat = _run(["kpsewhich", "language.dat"]).stdout.strip()
    cfgdat = Path(texmfcfg) / "tex/generic/config/language.dat"
    cfgdat.parent.mkdir(parents=True, exist_ok=True)
    if not cfgdat.exists():
        shutil.copy(sysdat, cfgdat)
    if "loadhyph-it.tex" not in cfgdat.read_text():
        with open(cfgdat, "a") as fh:
            fh.write("italian loadhyph-it.tex\n")

    _run(["mktexlsr", texmfhome, texmfcfg])
    r = _run(["fmtutil-sys", "--byfmt", "xelatex"])
    if r.returncode != 0:
        r = _run(["fmtutil", "--user", "--byfmt", "xelatex"])
    ok = _italian_registered()
    if verbose:
        print("[envsetup] format rebuild:",
              "OK, Italian patterns active" if ok
              else "FAILED — documents will compile without hyphenation")
    return ok


NASTALIQ_TTF = "NotoNastaliqUrdu.ttf"
NASTALIQ_URL = ("https://github.com/google/fonts/raw/main/ofl/"
                "notonastaliqurdu/NotoNastaliqUrdu%5Bwght%5D.ttf")


def ensure_nastaliq(verbose=True):
    """Provide Noto Nastaliq Urdu for the optional `{tl font=nastaliq}`
    styling: a static-instanced TTF in assets/fonts (XeLaTeX reads no
    woff2/variable reliably).  lib/fonts carries it, so the download is
    only for a checkout that lost it.  Returns True when the font is
    available."""
    fdir = copy_bundled_fonts(verbose=False)
    dst = fdir / NASTALIQ_TTF
    if dst.exists():
        return True
    try:
        import io
        import urllib.request
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
        if verbose:
            print("[envsetup] fetching Noto Nastaliq Urdu ...")
        req = urllib.request.Request(NASTALIQ_URL,
                                     headers={"User-Agent": "exlex"})
        data = urllib.request.urlopen(req, timeout=120).read()
        ft = TTFont(io.BytesIO(data))
        if "fvar" in ft:
            instantiateVariableFont(ft, {"wght": 400}, inplace=True)
        fdir.mkdir(parents=True, exist_ok=True)
        _place(dst, ft.save)
        if verbose:
            print("[envsetup]   -> %s" % dst.name)
        return True
    except Exception as e:
        if verbose:
            print("[envsetup] Nastaliq unavailable (%s) — "
                  "font=nastaliq will fall back to the main face" % e)
        return False


def stage_images(images, outdir):
    """Put a document's images beside its .tex, ready for XeLaTeX.

    Both build doors need this and neither may skip it: the studio's own
    build and `exlex.py build` write the same .tex, so a document with a
    figure that only one of them can compile is a document whose PDF
    depends on which door you came through.  It lived only in the studio
    until now, which is why `exlex.py build` could not build the feature
    test.

    XeLaTeX reads no SVG, so each becomes the sibling `.svg.pdf` that
    texgen's \\includegraphics points at; nor WebP nor GIF, so each becomes a
    sibling `.webp.png` / `.gif.png` (texgen.tex_picture), a GIF its first
    frame.  Raises if a conversion fails -- the caller knows what that means
    to whoever asked.  Returns whether there were any images at all.
    """
    images = Path(images)
    if not images.is_dir():
        return False
    dst = Path(outdir) / "images"
    shutil.copytree(images, dst, dirs_exist_ok=True)
    for svg in sorted(dst.glob("*.svg")):
        import pymupdf
        with pymupdf.open(str(svg)) as sd:
            svg.with_name(svg.name + ".pdf").write_bytes(sd.convert_to_pdf())
    for pic in sorted(list(dst.glob("*.webp")) + list(dst.glob("*.gif"))):
        png_twin(pic, pic.with_name(pic.name + ".png"))
    return True


def png_twin(src, out):
    """Write a WebP's or a GIF's first frame to `out` as a PNG, for paper.

    Needs Pillow (environment.yml); without it the words say so plainly,
    as the PDF build's error, rather than a traceback."""
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "%s is a %s picture, and printing one needs the package Pillow, which the Python "
            "running Parseh does not have. It is one of the packages Parseh's installer adds, "
            "and an update from Settings adds it too; until then the page shows the picture, "
            "and the PDF cannot" % (Path(src).name, Path(src).suffix[1:].upper().replace("WEBP", "WebP")))
    with Image.open(str(src)) as im:
        im.seek(0)                      # an animated one: its first frame
        im.load()
        frame = im.convert("RGBA" if ("transparency" in im.info or im.mode in ("RGBA", "LA", "PA"))
                           else "RGB")
    frame.save(str(out), "PNG")


def ensure_all(verbose=True):
    ensure_python_deps(verbose)
    fdir = ensure_fonts(verbose)
    ensure_nastaliq(verbose)
    hyph = ensure_italian_hyphenation(verbose)
    return {"fonts": fdir, "hyphenation": hyph}


if __name__ == "__main__":
    print(ensure_all())
