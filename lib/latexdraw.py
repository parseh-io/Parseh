# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing a latex block: compiled on its own, kept, and explained when it
fails (TO-DO §8.39, a0.4.0).

ON ITS OWN (the owner, 2026-09-24, settled).  A block is compiled in a
`standalone` document of its own, under its theme's preamble
(lib/latexthemes.py) and its theme's compiler, and what comes out is a PDF
cropped to the drawing.  The screen shows an SVG made from that very PDF
(PyMuPDF, the glyphs as outlines, as the studio's PDF figures have always
been shown: store.ensure_pdf_twin), and paper includes the PDF itself -- so
the two show the same drawing by construction, and a package added for
chemistry can never move a `:::math` formula, which never comes here.

COMPILED ONCE, KEPT IN markdown/latex/ -- derived, in no release, rebuilt at
will (.gitignore, lib/release.py NEVER).  A drawing is found again by its
KEY, the hash of everything that decides what it looks like:

  * the block's own LaTeX;
  * the resolved theme -- its preamble as it now is and its compiler, never
    its name: renaming a theme redraws nothing, editing it redraws exactly
    the blocks that name it;
  * the TeX installation: the compiler's own version, and the packages
    installed or removed through Parseh (the owner, 2026-09-25), so that a
    TeX upgraded or a package added draws afresh;
  * RENDERER, this module's own number, raised when the way a block is drawn
    changes -- never the version of Parseh, which would redraw everything on
    every release and call every kept page "updated".

A stale picture nobody can explain is the worst thing this feature can do,
worse than a slow compile: if in doubt, it is in the key.

SAFELY.  A theme and a document may come from somebody else, so a compile
runs with no shell escape, may read and write only its own temporary folder
and TeX's own files (openin_any / openout_any = p), is stopped after the
time Settings allows (30 seconds unless changed), runs in a folder wiped
after every compile (Formulae's way), and is killed when the server stops.

A FAILURE IS SAID IN WORDS, beside the block, with the line of the block it
happened on where TeX says one -- and the log's own line under it for
whoever wants it.  A failure is remembered as long as its key stands, so a
package installed since, or a theme changed, draws it again.

THE .tex AND THE .log OF A COMPILE ARE KEPT WITH ITS DRAWING (a0.5.4, the
owner, 2026-10-25): "it is difficult otherwise to understand when something
doesn't work, why it doesn't work".  The exact document TeX was given
(<key>.tex, what source() made, byte for byte) and the complete log it wrote
(<key>.log, at most LOG_MAX bytes, with a line saying so where it was cut) stay
beside the picture -- and beside a failure, which has no picture -- for as
long as the key stands, and are asked for by their address (/latex/<key>.tex,
/latex/<key>.log) wherever a drawing is shown.  Nothing is built a second time
to show them: what is shown is what was compiled.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import latexthemes                                           # noqa: E402

DRAWN = os.path.join(ROOT, "markdown", "latex")
FONTS = os.path.join(ROOT, "lib", "fonts")
RENDERER = 3      # 2, 2026-09-27: an inline drawing's key also carries "inline" (TO-DO §8.39's L8)
                  # 3, 2026-10-26: the .tex and the .log are kept beside every drawing (a drawing kept before has none)
LOG_MAX = 512 * 1024
URL = "/latex/"
KEY_RE = re.compile(r"^[0-9a-f]{64}$")
DESIGN_PT = 10.0            # standalone's size: a drawing's natural width is w/10 em
# A preview belongs to the editing moment, not to the library.  It has its
# own small LRU cache under the derived drawings folder and vanishes when the
# server next starts.  A saved source promotes its exact key into DRAWN.
PREVIEW_DIR = ".preview"
PREVIEW_MAX_DRAWINGS = 32
PREVIEW_MAX_BYTES = 16 * 1024 * 1024
OWNERS_FILE = "owners.json"
REPAIR_OWNER = "__repair__"     # the last repair's snapshot, kept as one owner
OWNER_GRACE_SECONDS = 24 * 60 * 60
REPAIR_SECONDS = 5 * 60
PRUNE_DAYS = 30
WIN = os.name == "nt"

_LOCK = threading.RLock()
_RUNNING = set()            # the TeX processes running now, killed when the server stops
_BUSY = {}                  # key -> Event: one compile of a key at a time
_FAILED = {}                # key -> the failure, while its key stands
_TOOLS = {}                 # compiler -> {"path", "version", "miktex"} or None
_POOL = ThreadPoolExecutor(max_workers=max(1, min(4, (os.cpu_count() or 2) // 2)))


# ------------------------------------------------------------ the compilers
def compiler(name, fresh=False):
    """{"path", "version", "miktex"} of a compiler this computer has, or None."""
    with _LOCK:
        if name in _TOOLS and not fresh:
            return _TOOLS[name]
    path = shutil.which(name)
    info = None
    if path:
        try:
            r = subprocess.run([path, "--version"], capture_output=True, text=True,
                               timeout=20, stdin=subprocess.DEVNULL)
            first = (r.stdout or r.stderr or "").strip().splitlines()
            version = first[0].strip() if first else name
            info = {"path": path, "version": version,
                    "miktex": "miktex" in (r.stdout or "").lower()}
        except (OSError, subprocess.SubprocessError):
            info = None
    with _LOCK:
        _TOOLS[name] = info
    return info


def compilers(fresh=False):
    """Every compiler Parseh offers, and whether this computer has it."""
    return {c: compiler(c, fresh) for c in latexthemes.COMPILERS}


def tex_state(name):
    """What the TeX installation contributes to a key: the compiler's version
    and the packages Parseh installed or removed (lib/texpackages.py)."""
    info = compiler(name)
    try:
        import texpackages
        packages = texpackages.state()
    except Exception:                                        # noqa: BLE001
        packages = ""
    return "%s|%s" % ((info or {}).get("version", ""), packages)


def key_of(tex, resolved, state, inline=False):
    # "inline" is in the key, not only RENDERER: an inline drawing carries a
    # depth ("d") a block's meta never has, measured by a second, hbox'd
    # compile a block never runs (TO-DO §8.39's L8) -- the same tex under the
    # same theme must never answer one shape's request with the other's meta.
    blob = json.dumps({"renderer": RENDERER, "compiler": resolved["compiler"],
                       "preamble": resolved["preamble"], "tex": tex, "tex-state": state,
                       "inline": bool(inline)},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ the cache
def _dir(key):
    return os.path.join(DRAWN, key[:2])


def _cache_dir(key, preview=False):
    return os.path.join(DRAWN, PREVIEW_DIR, key[:2]) if preview else _dir(key)


def paths(key, preview=False):
    """The persistent path by default; a temporary preview path when asked."""
    d = _cache_dir(key, preview)
    return {"svg": os.path.join(d, key + ".svg"), "pdf": os.path.join(d, key + ".pdf"),
            "meta": os.path.join(d, key + ".json"), "fail": os.path.join(d, key + ".fail.json"),
            "tex": os.path.join(d, key + ".tex"), "log": os.path.join(d, key + ".log")}


def _owners_path():
    return os.path.join(DRAWN, OWNERS_FILE)


def cached(key, preview=False):
    """One drawing's facts ({"w", "h"} in points), or None.

    Preview hits are deliberately touched on every use: their metadata is
    their LRU clock.  Kept drawings retain the older once-a-day touch, which
    avoids needless metadata writes while preserving the old prune rule.
    """
    p = paths(key, preview)
    try:
        with open(p["meta"], encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    if not (os.path.exists(p["svg"]) and os.path.exists(p["pdf"])):
        return None
    # used: a drawing asked for is not pruned (its meta's time says when)
    try:
        if preview or time.time() - os.path.getmtime(p["meta"]) > 86400:
            os.utime(p["meta"], None)
    except OSError:
        pass
    return meta


def _write_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def url_of(key):
    return URL + key + ".svg"


def file_of(name):
    """/latex/<key>.svg, .pdf, .tex or .log -> the file on this disk, or None."""
    m = re.match(r"^([0-9a-f]{64})\.(svg|pdf|tex|log)$", name or "")
    if not m:
        return None
    for preview in (False, True):
        p = paths(m.group(1), preview)[m.group(2)]
        if os.path.isfile(p):
            return p
    return None


def read_text(key, kind):
    """The .tex or the .log a drawing's compile kept (kind "tex" or "log"), as text, or None when
    there is none: the key was drawn before they were kept, or it never reached a compile."""
    if kind not in ("tex", "log") or not KEY_RE.match(key or ""):
        return None
    for preview in (False, True):
        try:
            with open(paths(key, preview)[kind], encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            continue
    return None


def _capped(log):
    """A compile's log as it is kept: whole up to LOG_MAX bytes, then cut, with a line that says so
    (a runaway log is a thing)."""
    raw = log.encode("utf-8", "replace")
    if len(raw) <= LOG_MAX:
        return log
    kept = raw[:LOG_MAX].decode("utf-8", "ignore")
    kept = kept[:kept.rfind("\n") + 1] if "\n" in kept else kept
    return (kept + "\n[Parseh kept the first %d KB of this log; it went on for %d bytes more.]\n"
            % (LOG_MAX // 1024, len(raw) - len(kept.encode("utf-8", "replace"))))


# what a compiler prints that its log does not hold: the helpers it starts for a font it cannot find (kpathsea, mktextfm,
# METAFONT) and the driver xelatex ends with (xdvipdfmx).  The lines of the terminal that only repeat the log, wrapped
# otherwise, are not these.
_HELPER_LINE = re.compile(r"^kpathsea:|mktex[a-z]*:|/web2c/mktex|^mf-nowin|^This is METAFONT|^(?:x?dvipdfmx)\b|"
                          r"^! |^<\*>|^Please type|^Transcript written on (?!d\.log)|^grep:", re.I)


def _with_program_output(log, out):
    """The log, and under it what the program printed besides it (_HELPER_LINE): where a font a document asked for is
    looked for and not made, and what xelatex's driver could not find."""
    seen = set(log.splitlines())
    extra = [l for l in (out or "").splitlines() if l.strip() and l not in seen and _HELPER_LINE.search(l)]
    if not extra:
        return log
    return log.rstrip("\n") + "\n\n[what the program printed besides this log]\n" + "\n".join(extra) + "\n"


def _keep_compile(key, preview, doc, log):
    """The document and the log of one compile, written beside where its drawing is or would be."""
    p = paths(key, preview)
    try:
        _write_atomic(p["tex"], doc.encode("utf-8"))
        _write_atomic(p["log"], _capped(log).encode("utf-8"))
    except OSError:
        pass


# ------------------------------------------------------------------ drawing
def plan(tex, theme_name, theme=None, inline=False, local=True):
    """What drawing a block would be -> {"key", "resolved", "compiler"} or a
    failure ({"ok": False, ...}) that no compile can mend: no such theme, no
    such compiler on this computer, or a package of the theme's own that
    Parseh has not got (texpackages.local_rule; `local=False` lets the
    computer's TeX answer for it, for a drawing made beforehand elsewhere,
    as the guide's are)."""
    if theme is not None:
        resolved = {"name": theme.get("name") or "", "compiler": theme["compiler"],
                    "preamble": latexthemes.preamble(theme), "theme": theme,
                    "languages": theme.get("languages")}
    else:
        resolved = latexthemes.resolve(theme_name)
    if resolved is None:
        name = theme_name or latexthemes.default_name()
        return {"ok": False, "kind": "theme", "theme": name,
                "said": 'This drawing asks for the theme "%s", which this Parseh does not have.'
                        % name,
                "fix": {"kind": "theme-missing", "theme": name}}
    lack = _lacks(resolved) if local else []
    if lack:
        names = [n for _p, tl in lack for n in tl]
        ids = [p for p, _tl in lack]
        return {"ok": False, "kind": "package", "theme": resolved["name"],
                "said": '%s %s not among Parseh\'s own TeX packages yet: the theme "%s" '
                        'uses %s, and a theme\'s packages beyond the base are used only '
                        'once Parseh has got them.'
                        % (_and(ids), "is" if len(ids) == 1 else "are", resolved["name"],
                           "it" if len(ids) == 1 else "them"),
                "fix": {"kind": "install", "package": ",".join(dict.fromkeys(names))}}
    info = compiler(resolved["compiler"])
    if info is None:
        return {"ok": False, "kind": "compiler", "theme": resolved["name"],
                "said": "This drawing is made with %s, which this computer does not have."
                        % resolved["compiler"],
                "fix": {"kind": "theme", "theme": resolved["name"]}}
    state = tex_state(resolved["compiler"])
    return {"ok": True, "key": key_of(tex, resolved, state, inline), "resolved": resolved,
            "compiler": info}


def _and(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _lacks(resolved):
    import texpackages
    theme = resolved.get("theme")
    if not theme or not texpackages.local_rule():
        return []
    got = texpackages.manifest()["packages"]
    out = []
    for p in latexthemes.own_packages(theme):
        want = [n for n in latexthemes.PACKAGES[p]["tl"] if n not in got]
        if want:
            out.append((p, want))
    return out


def peek(tex, theme_name, inline=False):
    """A block's drawing (or an inline mark's) if it is kept, without
    compiling anything -> the result draw() would give, or {"ok": None,
    "key"} when it is not drawn yet.  A saved page's peek promotes the
    editor's preview of the same drawing, as draw() does."""
    p = plan(tex, theme_name, inline=inline)
    if not p["ok"]:
        return p
    if _promote(p["key"]):
        _mark_unowned(p["key"])
    meta = cached(p["key"])
    if meta:
        return _ok(p["key"], meta)
    with _LOCK:
        if p["key"] in _FAILED:
            return _FAILED[p["key"]]
    fail = _read_fail(p["key"])
    if fail:
        return fail
    return {"ok": None, "key": p["key"]}


def _ok(key, meta, preview=False):
    # "d", the depth in points (how far the drawing reaches below its own
    # baseline): only an inline drawing's meta ever has one (_compile,
    # inline=True); a block's picture sits on nothing but the page, so its
    # meta has none, and this is None for it, same as before this existed.
    return {"ok": True, "key": key, "url": url_of(key), "w": meta.get("w"), "h": meta.get("h"),
            "d": meta.get("d"), "pdf": paths(key, preview)["pdf"],
            "svg": paths(key, preview)["svg"]}


def _read_fail(key):
    try:
        with open(paths(key)["fail"], encoding="utf-8") as fh:
            f = json.load(fh)
        return f if isinstance(f, dict) and f.get("ok") is False else None
    except (OSError, ValueError):
        return None


def _promote(key):
    """Make a preview into the kept drawing with the same content key.

    Copying rather than renaming leaves an already-open preview URL valid.
    The source key makes this a safe promotion: there is no user-controlled
    filename or mutable asset involved.
    """
    source, target = paths(key, True), paths(key)
    if cached(key):
        return True
    if not cached(key, True):
        return False
    try:
        for kind in ("pdf", "svg", "meta"):
            with open(source[kind], "rb") as fh:
                _write_atomic(target[kind], fh.read())
        return True
    except OSError:
        return False


def draw(tex, theme_name, theme=None, limit=None, inline=False, preview=False, local=True):
    """A block drawn -- from the cache when it is there, compiled when not ->
    {"ok": True, "key", "url", "w", "h", "d", "pdf", "svg"} or {"ok": False,
    "kind", "said", "line"?, "detail"?, "fix"?}.  `inline=True` (TO-DO
    §8.39's L8) is a drawing meant to sit inside a line of running text: its
    "d" is the depth to sit it on that line's baseline (`vertical-align`,
    `\\raisebox`), measured by a second, small compile of the same content
    boxed rather than typeset -- so a block's own compile, and everything a
    block already promises, are exactly as they were."""
    p = plan(tex, theme_name, theme, inline, local)
    if not p["ok"]:
        return p
    key = p["key"]
    # A saved page always gets the kept entry.  When its editor has just
    # drawn the same thing, promote that bounded preview instead of compiling
    # a second time.
    if not preview:
        if _promote(key):
            _mark_unowned(key)
    meta = cached(key, preview)
    if meta:
        return _ok(key, meta, preview)
    limit = limit or latexthemes.timeout()
    while True:
        with _LOCK:
            if not preview and key in _FAILED and _FAILED[key].get("limit", limit) >= limit:
                return _FAILED[key]
            ev = _BUSY.get(key)
            if ev is None:
                ev = _BUSY[key] = threading.Event()
                mine = True
            else:
                mine = False
        if not mine:
            ev.wait(limit + 30)
            meta = cached(key, preview)
            if meta:
                return _ok(key, meta, preview)
            continue
        try:
            # A failed keystroke is as transient as its preview.  A failure
            # for saved content remains cached, as before, until something
            # that could mend it changes.
            fail = None if preview else _read_fail(key)
            if fail:
                with _LOCK:
                    _FAILED[key] = fail
                return fail
            out = _compile(tex, p["resolved"], p["compiler"], key, limit, inline, preview)
            if out.get("ok"):
                return out
            if not preview:
                with _LOCK:
                    _FAILED[key] = dict(out, limit=limit)
            if not preview and out.get("kind") != "timeout":
                try:
                    _write_atomic(paths(key)["fail"], json.dumps(out).encode("utf-8"))
                except OSError:
                    pass
            return out
        finally:
            with _LOCK:
                _BUSY.pop(key, None)
            ev.set()


def draw_all(pairs, inline=False, preview=False):
    """Many blocks (or many inline drawings: `inline=True`, one call for
    each, never mixed) at once, several compiles side by side ->
    [result, ...] in the order of `pairs` ((tex, theme name), ...)."""
    futures = [_POOL.submit(draw, tex, name, inline=inline, preview=preview) for tex, name in pairs]
    return [f.result() for f in futures]


def _preexec():
    # on Linux the drawing dies with the server even when the server is
    # killed outright (PR_SET_PDEATHSIG); elsewhere the server's own stop
    # ends it (stop_all), and the time limit ends it in any case
    try:
        import ctypes
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGKILL)
    except Exception:                                        # noqa: BLE001
        pass


def _tex_env(work):
    env = dict(os.environ, openin_any="p", openout_any="p")
    try:
        import texpackages
        tree = texpackages.tree()
    except Exception:                                        # noqa: BLE001
        tree = None
    if tree and os.path.isdir(tree):
        env["TEXMFAUXTREES"] = tree.replace("\\", "/") + ","
    return env


def _run_tex(work, filename, info, limit):
    """One compile of `filename` in `work`, already written -> (returncode or
    None on a timeout, the process's own combined output, seconds spent)."""
    cmd = [info["path"], "-interaction=nonstopmode", "-halt-on-error", "-file-line-error"]
    cmd += (["-disable-write18", "-disable-installer"] if info.get("miktex")
            else ["-no-shell-escape"])
    cmd.append(filename)
    kw = {"cwd": work, "env": _tex_env(work), "stdin": subprocess.DEVNULL,
          "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT}
    if WIN:
        kw["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                               | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kw["start_new_session"] = True
        if sys.platform.startswith("linux"):
            kw["preexec_fn"] = _preexec
    started = time.time()
    try:
        proc = subprocess.Popen(cmd, **kw)
    except OSError as e:
        return "spawn", str(e), 0.0
    with _LOCK:
        _RUNNING.add(proc)
    try:
        out, _ = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        _kill(proc)
        proc.communicate()
        return None, "", time.time() - started
    finally:
        with _LOCK:
            _RUNNING.discard(proc)
    return proc.returncode, (out or b"").decode("utf-8", "replace"), time.time() - started


def _inline_depth(tex, resolved, info, work, limit):
    """The depth (pt, below the baseline) an inline drawing of `tex` would
    have, from a second compile that boxes it rather than typesets it --
    None when the probe itself cannot be trusted (its own failure, its own
    timeout, or a line it could not parse), never raised: an inline drawing
    without a depth still draws, only sitting on its own bottom edge, as a
    block already does."""
    pre = resolved["preamble"]
    doc = (pre + "\\begin{document}\n\\setbox0=\\hbox{" + tex + "}\n"
           "\\newwrite\\parsehdepth\\immediate\\openout\\parsehdepth=pdepth.txt\n"
           "\\immediate\\write\\parsehdepth{\\the\\dp0}\\immediate\\closeout\\parsehdepth\n"
           "\\box0\n\\end{document}\n")
    with open(os.path.join(work, "p.tex"), "w", encoding="utf-8") as fh:
        fh.write(doc)
    rc, _log, _took = _run_tex(work, "p.tex", info, min(limit, 20))
    if rc != 0:
        return None
    try:
        with open(os.path.join(work, "pdepth.txt"), encoding="utf-8") as fh:
            raw = fh.read().strip()
        return round(float(raw[:-2]) + latexthemes.BORDER_PT, 2) if raw.endswith("pt") else None
    except (OSError, ValueError):
        return None


def source(tex, resolved):
    """The whole LaTeX file a block is compiled from: its theme's preamble, then the block.  One place makes it, so that the file
    a person is given to compile or change (the studio's LaTeX zip) is the one the drawing really came from."""
    return resolved["preamble"] + "\\begin{document}\n" + tex + "\n\\end{document}\n"


def _compile(tex, resolved, info, key, limit, inline=False, preview=False):
    work = tempfile.mkdtemp(prefix="parseh-latex-")
    try:
        pre = resolved["preamble"]
        doc = source(tex, resolved)
        first_body = pre.count("\n") + 2           # the line the block's first line is on
        with open(os.path.join(work, "d.tex"), "w", encoding="utf-8") as fh:
            fh.write(doc)
        if resolved.get("languages"):
            os.makedirs(os.path.join(work, "fonts"), exist_ok=True)
            for name in os.listdir(FONTS) if os.path.isdir(FONTS) else ():
                if name.lower().endswith((".ttf", ".otf")):
                    src, dst = os.path.join(FONTS, name), os.path.join(work, "fonts", name)
                    try:
                        os.link(src, dst)
                    except OSError:
                        shutil.copy(src, dst)
        started = time.time()
        rc, out, _took = _run_tex(work, "d.tex", info, limit)
        if rc == "spawn":
            return {"ok": False, "kind": "compiler", "said": "%s could not be started: %s"
                    % (resolved["compiler"], out), "fix": {"kind": "theme", "theme": resolved["name"]}}
        # what TeX wrote of itself, whole: the log beside the document it read
        try:
            with open(os.path.join(work, "d.log"), encoding="utf-8", errors="replace") as fh:
                log = fh.read()
        except OSError:
            log = out or ""
        log = _with_program_output(log, out)
        _keep_compile(key, preview, doc, log)
        if rc is None:
            return {"ok": False, "kind": "timeout", "key": key,
                    "said": "The drawing did not finish in %d seconds, and was stopped. "
                            "Settings \u2192 LaTeX drawings says how long a drawing may take."
                            % limit}
        pdf = os.path.join(work, "d.pdf")
        if rc != 0 or not os.path.exists(pdf):
            return dict(explain(log, first_body, tex, resolved), key=key)
        try:
            import pymupdf
        except ImportError:
            try:
                import fitz as pymupdf                       # an older PyMuPDF
            except ImportError:
                return {"ok": False, "kind": "tool",
                        "said": "Drawings are shown on the screen by PyMuPDF, which the "
                                "environment Parseh installs has; this Parseh is running "
                                "without it."}
        with open(pdf, "rb") as fh:
            pdf_bytes = fh.read()
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
            if not d.page_count:
                return {"ok": False, "kind": "empty", "key": key, "said": "The drawing came out empty."}
            page = d[0]
            svg = page.get_svg_image(text_as_path=True)
            w, h = round(page.rect.width, 2), round(page.rect.height, 2)
        meta = {"w": w, "h": h, "compiler": resolved["compiler"],
                "theme": resolved["name"], "drawn": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "took": round(time.time() - started, 2), "renderer": RENDERER}
        if inline:
            meta["d"] = _inline_depth(tex, resolved, info, work, limit)
        p = paths(key, preview)
        _write_atomic(p["pdf"], pdf_bytes)
        _write_atomic(p["svg"], svg.encode("utf-8"))
        _write_atomic(p["meta"], json.dumps(meta).encode("utf-8"))
        if preview:
            prune_previews()
        else:
            _mark_unowned(key)
        return _ok(key, meta, preview)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _kill(proc):
    try:
        if WIN:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass


def stop_all():
    """Every drawing being made, stopped: the server is stopping."""
    with _LOCK:
        running = list(_RUNNING)
    for proc in running:
        _kill(proc)


# ------------------------------------------------------------- in words
# the commands a theme's checkbox gives, so that a command TeX does not know
# can be said with the box that would make it known
_COMMANDS = {
    "ce": "mhchem", "cee": "mhchem", "cf": "mhchem", "chemfig": "chemfig",
    "SI": "siunitx", "si": "siunitx", "qty": "siunitx", "unit": "siunitx", "num": "siunitx",
    "ang": "siunitx", "mathscr": "mathrsfs", "mathds": "dsfont", "vv": "esvect",
    "llbracket": "stmaryrd", "rrbracket": "stmaryrd", "male": "wasysym", "female": "wasysym",
    "smiley": "wasysym", "Yen": "marvosym", "Mundus": "marvosym", "cancel": "cancel",
    "bcancel": "cancel", "cancelto": "cancel", "slashed": "slashed", "mathlarger": "relsize",
    "mathsmaller": "relsize", "newtheorem": "amsthm", "bm": "bm", "textcolor": "xcolor",
    "color": "xcolor", "colorbox": "xcolor", "coloneqq": "mathtools", "mathbb": "amssymb",
    "mathfrak": "amsfonts", "dv": "physics", "pdv": "physics", "abs": "physics",
    "norm": "physics", "bra": "physics", "ket": "physics", "braket": "physics",
    "draw": "tikz", "node": "tikz", "fill": "tikz", "path": "tikz", "usetikzlibrary": "tikz",
    "addplot": "pgfplots", "lstinline": "listings", "text": "amsmath", "tfrac": "amsmath",
    "dfrac": "amsmath", "binom": "amsmath", "operatorname": "amsmath", "iint": "amsmath",
}
_ENVIRONMENTS = {
    "tikzpicture": "tikz", "axis": "pgfplots", "tikzcd": "tikz-cd", "circuitikz": "circuitikz",
    "lstlisting": "listings", "algorithm": "algorithm2e", "proof": "amsthm",
    "pmatrix": "amsmath", "bmatrix": "amsmath", "vmatrix": "amsmath", "matrix": "amsmath",
    "align": "amsmath", "align*": "amsmath", "aligned": "amsmath", "cases": "amsmath",
    "gather": "amsmath", "multline": "amsmath", "split": "amsmath",
}


def _where(line_no, first_body, tex):
    """TeX's line -> (the line of the block, or None when it is in the theme)."""
    if line_no is None:
        return None
    n = line_no - first_body + 1
    return n if 1 <= n <= tex.count("\n") + 1 else None


# A MESSAGE FROM ANY FILE, in the form -file-line-error gives it: `d.tex:7: Undefined control sequence.` for the document
# and `/…/skak.sty:1774: Font … not loadable: …` for a package it loaded.  Only the document's line is the block's.
_FILE_LINE = re.compile(r"^(?:\./)?(?P<file>(?:[A-Za-z]:)?[^\s:][^:\n]*?\.[A-Za-z0-9]+):(?P<n>\d+): (?P<msg>.*)$")
# the fonts a package brings that TeX Live keeps in a package of their own (a font TeX cannot make for itself here:
# a compile runs with no shell, so nothing is made on the fly)
FONT_PACKAGES = {"skaknew": "skaknew"}
_STATS = re.compile(r"words of memory|multiletter control sequences|words of font info|hyphenation exceptions|"
                    r"stack positions|strings out of|string characters out of|how much of TeX's memory", re.I)
_NOT_LOADABLE = re.compile(r"Font\s+(?:\S+=)?(\S+?)(?:\s+at\s+[\d.]+pt)?\s+not loadable")


def _no_message(lines, tex):
    """What to say of a log with no error line in it.  One that ends "No pages of output." is not silent:
    TeX ran to its end and nothing it was given made a page."""
    kept = [l for l in lines if l.strip() and not _STATS.search(l)]
    tail = "\n".join(kept[-6:])[:1200]
    none = [i for i, l in enumerate(lines) if "No pages of output" in l]
    if none:
        if not (tex or "").strip():
            cause = "the block is empty"
        else:
            cause = ("nothing in the block put anything on a page -- a command that typesets nothing, "
                     "or a package that went quiet before it could: the whole log says which")
        return {"kind": "empty", "said": "LaTeX made no page: %s." % cause, "detail": tail,
                "marks": [none[0] + 1]}
    return {"said": "LaTeX stopped without saying why.", "detail": tail}


def _own_page_words(path):
    return os.path.basename((path or "").replace("\\", "/"))


def explain(log, first_body, tex, resolved):
    """LaTeX's log -> the failure in ordinary words: what went wrong, on which
    line of the block when TeX says one, and what would mend it.  `marks` are the
    lines of the log this read (1-based), which the whole log shows marked."""
    theme = resolved.get("name") or ""
    lines = log.splitlines()
    msg, line_no, ctx, source = None, None, "", ""
    marks = []
    for i, l in enumerate(lines):
        m = _FILE_LINE.match(l)
        if m:
            source, msg = _own_page_words(m.group("file")), m.group("msg")
            if source == "d.tex":
                line_no = int(m.group("n"))
            ctx = "\n".join(lines[i:i + 4])
            marks.append(i + 1)
            for j, later in enumerate(lines[i + 1:i + 12]):
                if re.match(r"^l\.(\d+) ", later):
                    marks.append(i + j + 2)
                    break
            break
        if l.startswith("! "):
            msg = l[2:]
            ctx = "\n".join(lines[i:i + 4])
            marks.append(i + 1)
            # which file TeX was reading: the next line of the form FILE:LINE: (an "Emergency stop" carries it)
            for later in lines[i + 1:i + 14]:
                mf = _FILE_LINE.match(later)
                if mf:
                    source = _own_page_words(mf.group("file"))
                    break
            for j, later in enumerate(lines[i:i + 12]):
                mm = re.match(r"^l\.(\d+) ", later)
                if mm:
                    # the line TeX shows is in the file it was reading: the document's only when it was the document
                    if source in ("", "d.tex"):
                        line_no = int(mm.group(1))
                    marks.append(i + j + 1)
                    break
            break
    at = _where(line_no, first_body, tex)
    where = (" on line %d of the block" % at) if at else (
        " in the theme's preamble" if line_no else (" in %s" % source if source and source != "d.tex" else ""))
    out = {"ok": False, "kind": "latex", "line": at, "detail": ctx.strip()[:1200],
           "theme": theme, "marks": marks}
    if msg is None:
        out.update(_no_message(lines, tex))
        return out
    m = _NOT_LOADABLE.search(msg)
    if m:
        font = m.group(1)
        pkg = next((v for k, v in FONT_PACKAGES.items() if font.lower().startswith(k)), None)
        said = 'The font "%s" is not on this computer%s.' % (font, where)
        if pkg:
            said += (' It comes with the TeX Live package %s: get it in Settings → LaTeX drawings.' % pkg)
            out.update(kind="package", fix={"kind": "install", "package": pkg})
        else:
            said += (" Parseh runs LaTeX with no shell, so a missing font is not made on the fly: install "
                     "the package that has it, or choose another font.")
        out.update(said=said)
        return out
    m = re.search(r"File [`'](.+?)' not found", msg)
    if m:
        pkg = re.sub(r"\.(sty|cls|tex)$", "", m.group(1))
        out.update(kind="package", said="The package %s is not installed on this computer%s."
                   % (pkg, where), fix={"kind": "install", "file": m.group(1), "package": pkg})
        return out
    m = re.search(r'The font "(.+?)" cannot be found', msg)
    if m:
        out.update(said='The font "%s" is not on this computer: choose another for the theme '
                        '"%s" in Settings \u2192 LaTeX drawings.' % (m.group(1), theme),
                   fix={"kind": "theme", "theme": theme})
        return out
    if "Undefined control sequence" in msg:
        cs = None
        for l in ctx.splitlines():
            mm = re.match(r"^l\.\d+ (.*)$", l)
            if mm:
                found = re.findall(r"\\([A-Za-z@]+)", mm.group(1))
                cs = found[-1] if found else None
                break
        pkg = _COMMANDS.get(cs or "")
        if cs and pkg:
            out.update(said="\\%s is not a command the theme \"%s\" knows%s. It comes with "
                            "%s: tick %s in the theme, in Settings \u2192 LaTeX drawings."
                            % (cs, theme, where, pkg, pkg),
                       fix={"kind": "theme", "theme": theme, "package": pkg})
        elif cs:
            out.update(said="\\%s is not a command LaTeX knows here%s: a typing slip, or a "
                            "package the theme \"%s\" does not load." % (cs, where, theme))
        else:
            out.update(said="A command LaTeX does not know%s." % where)
        return out
    m = re.search(r"Environment (\S+) undefined", msg)
    if m:
        env = m.group(1)
        pkg = _ENVIRONMENTS.get(env)
        said = "\\begin{%s} names something the theme \"%s\" does not know%s." % (env, theme, where)
        if pkg:
            said += " It comes with %s: tick %s in the theme, in Settings \u2192 LaTeX drawings." % (pkg, pkg)
            out["fix"] = {"kind": "theme", "theme": theme, "package": pkg}
        out.update(said=said)
        return out
    if "Missing $ inserted" in msg:
        out.update(said="Mathematics outside a formula%s: put it between \\( and \\), or "
                        "between $ and $." % where)
        return out
    if re.search(r"Missing \} inserted|Extra \}|Runaway argument|File ended while scanning|"
                 r"Missing \{ inserted|Extra alignment tab", msg):
        out.update(said="A brace is missing, or there is one too many%s." % where)
        return out
    m = re.search(r"I do not know the key '([^']+)'", msg)
    if m:
        out.update(said="TikZ does not know the option \"%s\"%s." % (m.group(1).split("/")[-1], where))
        return out
    m = re.search(r"Undefined color `?'?([^'`]+)'", msg)
    if m:
        out.update(said="The colour \"%s\" is not one LaTeX knows%s." % (m.group(1), where))
        return out
    if "Emergency stop" in msg or "Fatal" in msg:
        out.update(said="LaTeX gave up%s." % where)
        return out
    out.update(said="LaTeX stopped%s: %s" % (where, msg.strip().rstrip(".") + "."))
    return out


# ------------------------------------------------------------ what is kept
def _owner_doc():
    try:
        with open(_owners_path(), encoding="utf-8") as fh:
            doc = json.load(fh)
        if isinstance(doc, dict) and isinstance(doc.get("owners"), dict):
            doc.setdefault("format", 1)
            doc.setdefault("unowned", {})
            return doc
    except (OSError, ValueError):
        pass
    return {"format": 1, "owners": {}, "unowned": {}, "repaired": 0}


def _save_owner_doc(doc):
    safe = {"format": 1,
            "owners": {str(owner): sorted({key for key in keys if KEY_RE.match(key)})
                       for owner, keys in (doc.get("owners") or {}).items()},
            "unowned": {str(key): float(at) for key, at in (doc.get("unowned") or {}).items()
                        if KEY_RE.match(str(key)) and isinstance(at, (int, float))},
            "repaired": float(doc.get("repaired") or 0)}
    _write_atomic(_owners_path(), json.dumps(safe, sort_keys=True).encode("utf-8"))


def _persistent_keys():
    """Keys that actually have a kept SVG; temporary previews never count."""
    if not os.path.isdir(DRAWN):
        return set()
    out = set()
    for here, dirs, files in os.walk(DRAWN):
        if PREVIEW_DIR in dirs:
            dirs.remove(PREVIEW_DIR)
        for name in files:
            if name.endswith(".svg") and KEY_RE.match(name[:-4]):
                out.add(name[:-4])
    return out


def _owned(doc):
    return {key for keys in (doc.get("owners") or {}).values() for key in keys}


def _remove_kept(key):
    for p in paths(key).values():
        try:
            os.unlink(p)
        except OSError:
            pass
    with _LOCK:
        _FAILED.pop(key, None)


def _reconcile_owners(doc, candidates=(), now=None):
    """Start the grace period for lost keys and delete expired orphans."""
    now = time.time() if now is None else now
    live = _owned(doc)
    pending = doc.setdefault("unowned", {})
    for key in set(candidates):
        if key in live:
            pending.pop(key, None)
        elif KEY_RE.match(key):
            pending.setdefault(key, now)
    for key in list(pending):
        if key in live:
            pending.pop(key, None)
        elif now - pending[key] >= OWNER_GRACE_SECONDS:
            _remove_kept(key)
            pending.pop(key, None)


def _source_keys(markdown):
    """Keys a saved source names, including L8 inline marks.

    Planning is enough: a newly saved source may not have been rendered yet,
    but its future content key is already known and is protected before the
    first page view compiles it.
    """
    pairs = []
    for block in latexthemes.blocks_in(markdown or ""):
        if not block.get("errors") and block.get("closed"):
            pairs.append((block.get("tex", ""), block.get("theme") or None, False))
    pairs += [(tex, theme, True) for tex, theme in latexthemes.inline_latex_pairs(markdown or "")]
    keys = set()
    for tex, theme, inline in pairs:
        p = plan(tex, theme, inline=inline)
        if p.get("ok"):
            keys.add(p["key"])
    return keys


def own_source(owner, markdown):
    """Record what one saved document/card owns and promote its previews.

    `owner` is an internal stable path-and-id string, never a display name.
    A direct save updates just that entry; `repair_owners` below is the
    throttled safety net if a process died between a save and this call.
    """
    keys = _source_keys(markdown)
    with _LOCK:
        doc = _owner_doc()
        before = set(doc["owners"].get(owner, []))
        doc["owners"][owner] = sorted(keys)
        for key in keys:
            _promote(key)
        _reconcile_owners(doc, before | keys)
        _save_owner_doc(doc)
    return keys


def forget_owner(owner, also=()):
    """A deleted document/card owns nothing from now; grace makes this safe.

    `also` are keys its source named that owners.json may not record (a
    source saved before ownership was, or by a save that failed to record
    it).  The repair's snapshot names every key live when it last ran,
    this owner's among them, and would otherwise go on holding them: the
    day's grace would then start only at the next repair, not at the delete."""
    with _LOCK:
        doc = _owner_doc()
        old = set(doc["owners"].pop(owner, [])) | {k for k in also if KEY_RE.match(k)}
        if REPAIR_OWNER in doc["owners"]:
            doc["owners"][REPAIR_OWNER] = [k for k in doc["owners"][REPAIR_OWNER] if k not in old]
        _reconcile_owners(doc, old)
        _save_owner_doc(doc)


def repair_owners(used, force=False):
    """Throttled mark-and-sweep repair from every saved source the server sees.

    The scan is intentionally a fallback rather than the save path: a large
    library is not walked for every keystroke.  It gives an interrupted save
    or a lost owners.json the conservative answer -- keep known source keys,
    then let anything else have the same 24-hour grace.
    """
    now = time.time()
    with _LOCK:
        doc = _owner_doc()
        if not force and now - float(doc.get("repaired") or 0) < REPAIR_SECONDS:
            return False
        old = _owned(doc) | _persistent_keys()
        doc["owners"][REPAIR_OWNER] = sorted({key for key in used if KEY_RE.match(key)})
        doc["repaired"] = now
        _reconcile_owners(doc, old | set(used), now)
        _save_owner_doc(doc)
    return True


def _mark_unowned(key):
    """A kept result made outside a save is eligible after the grace period."""
    with _LOCK:
        doc = _owner_doc()
        _reconcile_owners(doc, (key,))
        _save_owner_doc(doc)


def prune_previews():
    """Keep only the newest bounded preview cache; it is never in size().  A key counts as one
    entry whatever it holds -- a drawing, or the .tex and .log of a failure that has no picture."""
    root = os.path.join(DRAWN, PREVIEW_DIR)
    seen = {}
    for here, _dirs, files in os.walk(root):
        for name in files:
            key = name.split(".")[0]
            if KEY_RE.match(key):
                try:
                    seen[key] = max(seen.get(key, 0), os.path.getmtime(os.path.join(here, name)))
                except OSError:
                    pass
    rows = []
    for key, at in seen.items():
        rows.append((at, key, sum(os.path.getsize(p) for p in paths(key, True).values()
                                  if os.path.isfile(p))))
    rows.sort(reverse=True)
    total, kept, gone = 0, 0, 0
    for at, key, bytes_ in rows:
        if kept >= PREVIEW_MAX_DRAWINGS or total + bytes_ > PREVIEW_MAX_BYTES:
            for p in paths(key, True).values():
                try:
                    os.unlink(p)
                except OSError:
                    pass
            gone += 1
        else:
            total += bytes_
            kept += 1
    return gone


def size():
    """Only saved drawings -- never a live editor's bounded previews."""
    n, total = 0, 0
    for here, dirs, files in os.walk(DRAWN):
        if PREVIEW_DIR in dirs:
            dirs.remove(PREVIEW_DIR)
        for f in files:
            if f == OWNERS_FILE:
                continue
            if f.endswith(".svg"):
                n += 1
            try:
                total += os.path.getsize(os.path.join(here, f))
            except OSError:
                pass
    return {"drawings": n, "bytes": total}


def prune(days=PRUNE_DAYS):
    """Startup cleanup: discard old temporary previews and expired orphans.

    An owned drawing is never removed merely because a phone or a document
    did not open it recently.  The former 30-day access-time pruning remains
    only as a conservative fallback for old caches with no ownership record.
    """
    shutil.rmtree(os.path.join(DRAWN, PREVIEW_DIR), ignore_errors=True)
    with _LOCK:
        doc = _owner_doc()
        _reconcile_owners(doc, _persistent_keys())
        _save_owner_doc(doc)
        owned = _owned(doc)
        waiting = set(doc.get("unowned") or {})
    cut = time.time() - days * 86400
    gone = 0
    for here, dirs, files in os.walk(DRAWN):
        if PREVIEW_DIR in dirs:
            dirs.remove(PREVIEW_DIR)
        for f in files:
            if not f.endswith(".json") or f.endswith(".fail.json"):
                continue
            if f == OWNERS_FILE:
                continue
            meta = os.path.join(here, f)
            try:
                if os.path.getmtime(meta) >= cut:
                    continue
            except OSError:
                continue
            key = f[:-5]
            if key in owned or key in waiting:
                continue
            _remove_kept(key)
            gone += 1
    return gone


def forget_unused(used):
    """Every drawing whose key is not in `used`, removed -> how many, and
    how many bytes that freed.  Settings' "Forget drawings nothing uses"."""
    gone, freed = 0, 0
    for here, dirs, files in os.walk(DRAWN):
        if PREVIEW_DIR in dirs:
            dirs.remove(PREVIEW_DIR)
        for f in files:
            key = f.split(".")[0]
            if KEY_RE.match(key) and key not in used:
                p = os.path.join(here, f)
                try:
                    freed += os.path.getsize(p)
                    os.unlink(p)
                    if f.endswith(".svg"):
                        gone += 1
                except OSError:
                    pass
    for here, dirs, files in os.walk(DRAWN, topdown=False):
        if here != DRAWN and PREVIEW_DIR not in here.split(os.sep) and not dirs and not files:
            try:
                os.rmdir(here)
            except OSError:
                pass
    with _LOCK:
        doc = _owner_doc()
        doc["owners"] = {owner: [key for key in keys if key in used]
                         for owner, keys in doc["owners"].items()}
        doc["owners"] = {owner: keys for owner, keys in doc["owners"].items() if keys}
        for key in list(doc["unowned"]):
            if key not in used:
                doc["unowned"].pop(key, None)
        _save_owner_doc(doc)
    with _LOCK:
        _FAILED.clear()
    return {"drawings": gone, "bytes": freed}


def forget_failures():
    """Every failure remembered, forgotten: a package installed, a compiler
    found, a limit changed -- anything that may mend one."""
    with _LOCK:
        _FAILED.clear()
        for name in list(_TOOLS):
            _TOOLS.pop(name, None)
    for here, dirs, files in os.walk(DRAWN):
        if PREVIEW_DIR in dirs:
            dirs.remove(PREVIEW_DIR)
        have = {f[:-4] for f in files if f.endswith(".svg")}
        for f in files:
            key = f.split(".")[0]
            # a failure, and the document and log that went with it -- a key with a drawing keeps its own
            if f.endswith(".fail.json") or (f.endswith((".tex", ".log")) and key not in have):
                try:
                    os.unlink(os.path.join(here, f))
                except OSError:
                    pass
