#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""What serve.bat runs on Windows: a setup wizard the first time, then the server.

    python lib/launcher.py            first time: the wizard; then start, and open the browser
    python lib/launcher.py 9000       ... on another port, this once
    python lib/launcher.py setup      the wizard again
    python lib/launcher.py stop       stop a running server (the stop button on any page does too)
    python lib/launcher.py status     is it running, and where
    python lib/launcher.py cert       a fresh certificate, e.g. after the addresses changed
    python lib/launcher.py readers    every book's reader and the library page, as ./build.sh --html
    --no-browser                      start without opening a browser window

On Linux and macOS ./serve.sh does this job -- the server in the background,
a log file, a pidfile -- and ./install.sh is the wizard's counterpart.  On
Windows there is no setsid and no terminal session to lose, so the server
simply runs in the console window this was started from: that window is the
log, and closing it, Ctrl-C, or the stop button on any page stops the server.
Every line the server prints is ALSO written to serve.log, the run before kept
as serve.log.1, exactly as serve.sh keeps them (lib/faultlog.py, TO-DO 5.31):
the window is what a person watches, the file is what Settings > About reads.
Nothing here is Windows-only in principle; it is just that serve.sh is the
better tool where it runs.

The wizard checks what install.sh checks -- a Python 3 (serve.bat found one),
the bundled web fonts (and a Japanese font on the machine when there is
Japanese content), openssl for the certificate, each book with its language,
its narration and alignment -- and the environment everything else needs, with
every package environment.yml lists (lib/runtime.py): it offers to make the
environment in this folder, or to add what an older one lacks, and carries on
in it.  It offers to install what winget can, builds the readers and the
library page the way ./build.sh --html does, compiles the HTML guide as
install.bat does, and makes the certificate.  Serving itself needs only the
standard library.

AN UPDATE FROM SETTINGS RUNS IN THIS WINDOW (lib/updater.py, TO-DO §13.16).
The server is started knowing that this window waits on it (PARSEH_LAUNCHER),
and when it stops to be updated it leaves with updater.LAUNCHER_EXIT: this
window then runs the update's helper -- its lines are this window's log like
everything else -- and starts the new version in the same window.  A new
version that does not come up is undone and the old one started again.  And
an update that did not finish (the power cut) is finished or undone first
thing, before this file imports anything else of Parseh's, as serve.py does.
"""
import http.client
import json
import os
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(LIB, ".."))
sys.path.insert(0, LIB)
# AN UPDATE THAT DID NOT FINISH IS FINISHED FIRST, before anything else of
# Parseh's is imported from files it may have left half replaced
# (lib/updater.py; serve.py asks the same as it starts)
import updater                       # noqa: E402  updating in place, from Settings (TO-DO §13.16)
if __name__ == "__main__":
    updater.finish_first(ROOT)
from books import all_books          # noqa: E402  where the books are (two levels: books/<language>/<slug>/)
import faultlog                      # noqa: E402  the log file, the run before kept (TO-DO 5.31)
import guidebuild                    # noqa: E402  the HTML guide: whether its pages are compiled, and from what
import languages                     # noqa: E402  the registry: which web fonts travel, which language needs a system font
import network                       # noqa: E402  the port Parseh keeps, and who may reach it
import runtime                       # noqa: E402  what the environment is, where it is, how it is made

NAME = "Parseh"
ENVNAME = "ilya-frank"
# The port is Parseh's own setting, kept in config/network.json and moved from
# its Settings > Network page (lib/network.py): this window must not be a
# second place that decides it, only the place that reads it.  A number on the
# command line still wins for that one start.
DEFAULT_PORT = network.DEFAULT_PORT
MARKER = os.path.join(ROOT, ".setup-done")   # written once the wizard has run through
TLS_DIR = os.path.join(ROOT, ".tls")
WIN = os.name == "nt"


# ------------------------------------------------------------------ talking
counts = {"ok": 0, "miss": 0}


def say(s=""):
    print(s, flush=True)       # flushed: the server writes to the same console


def good(s):
    counts["ok"] += 1
    print("  ok    " + s, flush=True)


def bad(s):
    counts["miss"] += 1
    print("  MISS  " + s, flush=True)


def skip(s):
    print("  --    " + s, flush=True)


def interactive():
    return sys.stdin.isatty()


def pause(msg="Press Enter to continue"):
    if not interactive():
        return
    try:
        input("\n  " + msg + " ")
    except EOFError:
        pass


def ask(question, default=True):
    """A yes/no question; Enter takes the default, and so does a non-terminal."""
    if not interactive():
        return default
    try:
        a = input("  %s %s " % (question, "[Y/n]" if default else "[y/N]")).strip().lower()
    except EOFError:
        return default
    return a.startswith("y") if a else default


def banner(step, total, title):
    line = "=" * 66
    print("\n" + line)
    print("  %s -- setup, step %d of %d: %s" % (NAME, step, total, title))
    print(line + "\n", flush=True)


# ------------------------------------------------------------------ what the machine has
def env_dir(*names):
    """The first of several environment variables that is set, or ''."""
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return ""


def openssl_dirs():
    """Where Windows keeps an openssl.exe that is not on the PATH."""
    if not WIN:
        return []
    pf = env_dir("ProgramFiles") or r"C:\Program Files"
    pf86 = env_dir("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    local = env_dir("LOCALAPPDATA")
    home = env_dir("USERPROFILE")
    pdata = env_dir("ProgramData") or r"C:\ProgramData"
    dirs = [
        os.path.join(sys.prefix, "Library", "bin"),        # a conda Python brings its own
        os.path.join(pf, "Git", "usr", "bin"),              # Git for Windows brings one too
        os.path.join(pf, "Git", "mingw64", "bin"),
        os.path.join(local, "Programs", "Git", "usr", "bin"),
        os.path.join(local, "Programs", "Git", "mingw64", "bin"),
        os.path.join(pf86, "Git", "usr", "bin"),
        os.path.join(pf, "OpenSSL-Win64", "bin"),           # what winget installs (Shining Light)
        os.path.join(pf, "OpenSSL", "bin"),
        os.path.join(pf, "FireDaemon OpenSSL 3", "bin"),
    ]
    for root in (home, local, pdata, os.path.join(local, "Programs")):
        for conda in ("miniconda3", "anaconda3", "miniforge3", "mambaforge"):
            dirs.append(os.path.join(root, conda, "Library", "bin"))
    return dirs


def find_openssl():
    """openssl on the PATH, or in one of the places Windows keeps it -- which
    is then put on the PATH, so that serve.py finds it as well."""
    exe = shutil.which("openssl")
    if exe:
        return exe
    for d in openssl_dirs():
        exe = os.path.join(d, "openssl.exe")
        if os.path.isfile(exe):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            return exe
    return None


def find_tailscale():
    """The tailscale CLI, so the server can print (and certify) the tailnet
    address; on Windows it is installed off the PATH."""
    if shutil.which("tailscale"):
        return True
    if WIN:
        d = os.path.join(env_dir("ProgramFiles") or r"C:\Program Files", "Tailscale")
        if os.path.isfile(os.path.join(d, "tailscale.exe")):
            os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + d
            return True
    return False


def importable(module):
    try:
        __import__(module)
        return True
    except Exception:
        return False


def bundled_web_fonts():
    """The woff2 files the registry says travel with the toolbox (Persian's
    two faces, the Arabic naskh) -- the list is the registry's, not ours."""
    return sorted(set(f for L in languages.LANGS.values()
                      for f in (L.fonts.get("web_files") or [])))


# THE LANGUAGES WHOSE FACES ARE NOT BUNDLED.  A CJK font is tens of
# megabytes, so it is the one the toolbox asks the machine for rather than
# shipping -- and it is asked for by the registry's `tex.script`, not by
# name, because Chinese arrived and a check written for Japanese alone said
# nothing about a machine holding only Chinese books.
def cjk_codes():
    return [L.code for L in languages.LANGS.values()
            if (getattr(L, "tex", None) or {}).get("script") == "CJK"]


def cjk_content():
    """WHICH of those languages there is a book or a video in, not merely
    whether there is one.

    The difference matters twice over: a machine with only Chinese content
    should be told about Chinese and not about Japanese, and the font it is
    asked for has to be one that covers the script it actually holds -- the
    Japanese and Chinese font sets on a Linux machine overlap but are not the
    same, and IPAexMincho answers for Japanese while covering no simplified
    Chinese at all.
    """
    out = []
    books_by_lang = {b.language for b in all_books()}
    for code in cjk_codes():
        if code in books_by_lang:
            out.append(code)
            continue
        vids = os.path.join(ROOT, "youtube", "videos",
                            languages.get(code).folder)
        try:
            if any(os.path.isdir(os.path.join(vids, d)) for d in os.listdir(vids)):
                out.append(code)
        except OSError:
            continue
    return out


def cjk_font(code):
    """The name of a font installed for THIS language, or None.

    Asked per language, because the sets differ: fc-list :lang=ja answers
    with IPAexMincho on a machine that has no simplified Chinese face at all,
    so a single :lang=ja probe told a reader with Chinese books that they
    were covered.  fontconfig takes the same two-letter codes the registry
    uses.  Windows has shipped Yu Mincho and Meiryo since 8.1, so there it is
    taken as given (Python's standard library cannot ask).
    """
    if WIN:
        return "Yu Mincho / Meiryo (Windows ships them)"
    if not shutil.which("fc-list"):
        return None
    try:
        r = subprocess.run(["fc-list", ":lang=%s" % code, "family"],
                           capture_output=True,
                           encoding="utf-8", errors="replace", timeout=20)
    except Exception:
        return None
    for line in r.stdout.splitlines():
        if line.strip():
            return line.split(",")[0].strip()
    return None


def winget_install(pkg_id):
    """winget install <id>; Windows asks to allow the installer itself."""
    return subprocess.call(["winget", "install", "-e", "--id", pkg_id,
                            "--accept-source-agreements", "--accept-package-agreements"]) == 0


# ------------------------------------------------------------------ the server
def server_url(port):
    """The address a server on this port answers at (https, or http when it
    was started with --http), or None when nothing answers."""
    for scheme in ("https", "http"):
        try:
            if scheme == "https":
                c = http.client.HTTPSConnection("127.0.0.1", port, timeout=2,
                                                context=ssl._create_unverified_context())
            else:
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            c.request("GET", "/")
            c.getresponse().read()
            c.close()
            return "%s://localhost:%d/" % (scheme, port)
        except Exception:
            continue
    return None


def have_cert():
    return all(os.path.isfile(os.path.join(TLS_DIR, f)) for f in ("cert.pem", "key.pem"))


def run_tool(args, cwd=ROOT):
    """One of the lib/ tools under this same Python, its output indented."""
    r = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True,
                       encoding="utf-8", errors="replace")
    for line in (r.stdout + r.stderr).splitlines():
        print("       " + line, flush=True)
    return r.returncode == 0


def make_cert():
    """serve.py --cert: a fresh certificate in .tls/, signed by the authority
    Parseh keeps for this machine alone."""
    return run_tool(["serve.py", "--cert"]) and have_cert()


def build_readers():
    """What ./build.sh --html does: every book's reader, then the library page.
    No cache keys here -- build.sh keeps those, and a missing key only ever
    costs a rebuild, never a stale page."""
    all_ok = True
    for b in all_books():
        if not os.path.isfile(b.main):
            say("     %s (%s): no %s yet, skipping"
                % (b.rel_from_books(), b.lang.name, os.path.basename(b.main)))
            continue
        say("     %s (%s)" % (b.rel_from_books(), b.lang.name))
        if os.path.isfile(os.path.join(b.dir, "timings.json")):
            # a regenerated batch loses its % @par comments; the sidecar restores them
            subprocess.run([sys.executable, os.path.join(LIB, "timestamp.py"),
                            "--from-sidecar", "--book", b.dir], cwd=b.dir, capture_output=True)
        if not run_tool([os.path.join(LIB, "tex2html.py"), "--book", b.dir], cwd=b.dir):
            say("       reader FAILED for %s" % b.slug)
            all_ok = False
    if not run_tool([os.path.join(LIB, "make_index.py")]):
        all_ok = False
    return all_ok


def compile_guide():
    """The HTML guide, html-guide/markdown/ compiled into html-guide/site/,
    what the hub's guide button opens -- install.bat's `guide` step.  Every
    time the wizard runs, and not only when it installs the environment
    (whose install compiles it on the way): a machine whose environment was
    complete would otherwise be left with a guide never compiled, or one
    compiled from older pages.  A guide already compiled from these very
    pages is left as it is (guidebuild.status, the hash of its sources);
    the compile is standard-library Python, so this Python does it."""
    build = os.path.join(ROOT, "html-guide", "build.py")
    if not os.path.isfile(build):
        skip("the guide (no html-guide/ in this checkout)")
        return True
    st = guidebuild.status()
    if st.get("built") and st.get("stale") is False:
        good("the guide, already compiled from these pages (html-guide/site/)")
        return True
    if run_tool([build]):
        good("the guide compiled (html-guide/site/)")
        return True
    bad("the guide did not compile -- the lines above say why; its front page, "
        "served, compiles it again")
    return False


def stop(port):
    url = server_url(port)
    if not url:
        say("not running on port %d" % port)
        return 0
    req = urllib.request.Request(url + "__shutdown", data=b"", method="POST")
    try:
        urllib.request.urlopen(req, timeout=5, context=ssl._create_unverified_context()).read()
    except Exception as e:
        say("could not ask it to stop: %s" % e)
        return 1
    for _ in range(40):
        if not server_url(port):
            say("stopped")
            return 0
        time.sleep(0.25)
    say("asked it to stop, but port %d still answers" % port)
    return 1


def serve_logged(cmd, rotate=True, log=None, console=None, env=None):
    """Start the server with its output copied to this window AND to serve.log
    -> (the process, the thread that copies).  `rotate` keeps the run before as
    serve.log.1 first; after an update the same run goes on in the same file,
    as it does where serve.sh started it (lib/updater.py appends).  The file is
    named in the server's environment, so its About page reads this one.

    The server's stdout is a pipe now, not the console; Ctrl-C still reaches
    it, because it is still attached to the console, and a window closed takes
    both.  `log`, `console` and `env` are for the tests."""
    log = log or faultlog.log_path(ROOT)
    if rotate:
        faultlog.rotate(log)
    env = dict(env if env is not None else os.environ, PARSEH_LAUNCHER="1")
    env[faultlog.LOG_ENV] = log
    # A PIPE IS NOT THE CONSOLE (a0.6.3 G5).  Writing to the console, Python
    # speaks UTF-16 to Windows whatever the code page; writing to a pipe it
    # encodes with the ANSI code page (cp1252 ...) unless told otherwise -- and
    # a Persian title in a server line would then end the server.  serve.bat
    # sets PYTHONIOENCODING, a launcher started any other way may not: the
    # copy below takes the bytes as UTF-8, so the server is told to write
    # UTF-8, never to fail on a character.
    env["PYTHONIOENCODING"] = "utf-8:backslashreplace"
    # No creationflags: the server stays in this console's process group
    # (no CREATE_NEW_PROCESS_GROUP), so a Ctrl-C or a Ctrl-Break in the window
    # reaches it as it reaches this launcher.
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    copier = threading.Thread(target=faultlog.pump, args=(proc.stdout, console, log), daemon=True)
    copier.start()
    return proc, copier


def _reap(proc, timeout=10):
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return proc.wait()


def _wait_after_interrupt(proc):
    """After a Ctrl-C (or a Ctrl-Break) in the window -> the server's exit
    status.  The console sent it to every process attached to it, the server
    among them, which stops by itself; one that has not after 10 s is ended.
    A server stopped this way stopped as asked: 0, not a failure, so that
    serve.bat does not hold the window with "press any key"."""
    try:
        rc = proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        _reap(proc, 5)
        return 0
    except KeyboardInterrupt:                  # a second Ctrl-C: do not wait any more
        proc.terminate()
        _reap(proc, 5)
        return 0
    # Windows reports a process ended by the console's Ctrl-C as
    # STATUS_CONTROL_C_EXIT (0xC000013A); POSIX as -SIGINT
    return 0 if rc in (0, 0xC000013A, -2, 130) else rc


def start(port, open_browser=True, updated="", append=False):
    """Start the server in this window and wait on it.  `updated` names an
    update this window has just applied: a new version that does not come
    up is undone, and the old one started in its place.  `append` goes on in
    the same serve.log (the version started again after such an undo: the
    log of the one that failed is the reason, and stays where it is)."""
    url = server_url(port)
    if url:
        say("already running: %s" % url)
        if open_browser:
            webbrowser.open(url)
        return 0
    find_tailscale()
    cmd = [sys.executable, "-u", "serve.py", str(port)]
    if not have_cert() and not find_openssl():
        say("no openssl on this computer, so no certificate yet: serving plain http.")
        say("(The clipboard and screen capture then work on localhost only.  Install")
        say(" OpenSSL or Git for Windows -- `serve.bat setup` offers to -- and restart.)")
        say("")
        cmd.append("--http")
    say("starting:  " + " ".join(cmd))
    say("")
    # the server is told who waits on it: when it stops to be updated it
    # leaves with updater.LAUNCHER_EXIT, and this window runs the update
    proc, copier = serve_logged(cmd, rotate=not (updated or append))
    url = None
    try:
        for _ in range(80):                    # up to 20 s: the first start mints the certificate
            if proc.poll() is not None:
                break
            url = server_url(port)
            if url:
                break
            time.sleep(0.25)
    except KeyboardInterrupt:
        # Ctrl-C while it was still starting: the console sent it to the
        # server too.  Stopped, as after it was up -- not a traceback.
        _wait_after_interrupt(proc)
        copier.join(5)
        say("stopped.")
        return 0
    if not url:
        if proc.poll() is None:
            proc.terminate()
        # its last lines into serve.log, and the file let go of, before
        # anything else: on Windows a file still open cannot be renamed
        _reap(proc)
        copier.join(5)
        say("")
        say("failed to start -- the messages above say why")
        if updated:
            say("It was just updated, so the update is undone and the version before it started.")
            helper = os.path.join(ROOT, updater.WORK, "helper.py")
            if os.path.isfile(helper):
                subprocess.call([sys.executable, helper, "rollback", ROOT], cwd=ROOT)
                return start(port, open_browser=False, append=True)
        return 1
    say("")
    say("%s is up at %s -- this window is its log.  Close it, press Ctrl-C," % (NAME, url))
    say("or use the stop button on any page to stop the server.")
    if open_browser:
        webbrowser.open(url)
    try:
        rc = proc.wait()
    except KeyboardInterrupt:                  # the console sent Ctrl-C to the server too
        rc = _wait_after_interrupt(proc)
    copier.join(5)                             # the last lines into the file before anything else is said
    if rc == updater.LAUNCHER_EXIT:
        # IT STOPPED TO BE UPDATED (Settings > Updating Parseh).  The update
        # runs here, in this window, which stays the log; then the new
        # version starts in it as the old one did -- without a browser
        # window, since the page that asked comes back by itself.
        say("")
        say("%s stopped to be updated; this window starts it again when that is done." % NAME)
        job = updater.running(ROOT)
        updater.run_helper(ROOT)
        say("")
        return start(port, open_browser=False, updated=job)
    say("stopped.")
    return rc


# ------------------------------------------------------------------ the wizard
def wizard():
    counts["ok"] = counts["miss"] = 0
    total = 5

    banner(1, total, "welcome")
    say("  %s serves the books, the videos, the studio, the exercise decks and" % NAME)
    say("  the Anki store from one https address on this computer,")
    say("  https://localhost:%d/, and from the same address on a phone or a" % DEFAULT_PORT)
    say("  laptop over Tailscale.")
    say("")
    say("  A fresh %s answers this computer and a VPN, and nothing else: the" % NAME)
    say("  Wi-Fi door is shut until you open it on its Settings > Network page,")
    say("  where a device on the Wi-Fi is then let in with a code shown here.")
    say("")
    say("  This wizard runs once.  It looks at what this computer has, builds the")
    say("  reading editions and compiles the guide, makes the certificate, and")
    say("  starts the server.  After that, double-clicking serve.bat just starts")
    say("  %s;  `serve.bat setup` brings the wizard back." % NAME)
    pause("Press Enter to begin")

    banner(2, total, "this computer")
    say("  Required to serve:")
    ver = "%d.%d.%d" % sys.version_info[:3]
    env_prefix, _env_python = runtime.find_env()
    if env_prefix and os.path.realpath(sys.prefix) == os.path.realpath(env_prefix):
        good("python %s -- the '%s' environment  (%s)" % (ver, ENVNAME, sys.executable))
    else:
        good("python %s  (%s)" % (ver, sys.executable))
    fonts = os.path.join(LIB, "fonts")
    wanted = bundled_web_fonts()
    lacking = [f for f in wanted if not os.path.isfile(os.path.join(fonts, f))]
    if not lacking:
        good("bundled web fonts (%s)" % ", ".join(wanted))
    else:
        bad("lib/fonts/ lacks %s -- copy them from a working checkout" % ", ".join(lacking))
    here = cjk_content()
    if here:
        for code in here:
            name = languages.get(code).name
            face = cjk_font(code)
            if face:
                good("a %s font (%s)" % (name, face))
            else:
                bad("no %s font -- there is %s content, and its faces are not"
                    " bundled; Debian/Ubuntu: sudo apt install fonts-noto-cjk;"
                    " Fedora: sudo dnf install google-noto-serif-cjk-fonts;"
                    " macOS: brew install --cask font-noto-serif-cjk"
                    % (name, name))
    else:
        skip("CJK font (no %s book or video yet)"
             % " or ".join(languages.get(c).name for c in cjk_codes()))

    say("")
    say("  Needed once, to make the certificate:")
    exe = find_openssl()
    if exe:
        good("openssl  (%s)" % exe)
    else:
        bad("openssl -- not on this computer")
        if WIN and shutil.which("winget"):
            say("        winget can install it (OpenSSL Light, from Shining Light Productions);")
            say("        Windows will ask to allow the installer.")
            if ask("Install OpenSSL with winget now?", True):
                winget_install("ShiningLight.OpenSSL.Light")
                exe = find_openssl()
                if exe:
                    good("openssl  (%s)" % exe)
                else:
                    bad("openssl still not found -- install Git for Windows or OpenSSL, then `serve.bat setup`")
        if not exe:
            say("        Without it %s serves plain http.  Everything works, but the clipboard" % NAME)
            say("        and screen capture then work on localhost only.  Git for Windows brings")
            say("        an openssl too, and this finds it there.")

    say("")
    say("  The environment -- rebuilding books, dividing Japanese and Chinese into")
    say("  words, opening Anki exports: everything environment.yml lists:")
    prefix, env_python = runtime.find_env()
    here = os.path.realpath(sys.executable)
    if prefix and os.path.realpath(env_python) == here:
        good("the '%s' environment  (%s)" % (ENVNAME, prefix))
    elif prefix:
        skip("the '%s' environment is at %s, and this is another Python" % (ENVNAME, prefix))
    else:
        skip("no '%s' environment yet" % ENVNAME)
    st = runtime.status()
    for p in st["packages"]:
        (good if p["have"] else skip)("%s -- %s" % (p["name"], p["what"]))
    for m in st["models"]:
        (good if m["have"] else skip)("pkuseg's %s -- for %s" % (m["what"], languages.get(m["language"]).name))
    if not prefix or st["missing"] or not all(m["have"] for m in st["models"]):
        say("        Serving works without them, and the pages say what they need.  The")
        say("        environment goes into this folder (.runtime\\), made with micromamba --")
        say("        a few hundred megabytes, once -- and whatever it lacks is added.")
        if ask("Install it now?", True):
            if runtime.install(runtime.Report(), readers=False):
                prefix, env_python = runtime.find_env()
                good("the environment is ready  (%s)" % prefix)
                if env_python and os.path.realpath(env_python) != here:
                    # everything from here on belongs to the environment's
                    # Python: the readers it builds, the server it starts
                    say("        Carrying on in it ...")
                    return "restart", env_python
            else:
                bad("the environment did not finish -- the lines above say why; install.bat tries again")

    say("")
    say("  Optional tools (only for rebuilding a PDF, re-aligning a narration, or cutting a card's recording):")
    for tool, what in (("lualatex", "rebuilding a book's PDF"),
                       ("xelatex", "a studio document's PDF, and the LaTeX drawings"),
                       ("pdflatex", "the LaTeX drawings of a theme that asks for it"),
                       ("ffmpeg", "snapping timings to silences, cutting a card's recording"),
                       ("pdftotext", "re-extracting a book's source")):
        (good if shutil.which(tool) else skip)("%s -- %s" % (tool, what))
    if find_tailscale():
        good("tailscale -- the tailnet address is printed and certified too")
    else:
        skip("tailscale (not installed; the local-network address still works)")
    pause()

    banner(3, total, "the books")
    books = all_books()
    if not books:
        skip("no book under books/ yet (books/<language>/<slug>/ with a book.json is all it takes)")
    for b in books:
        rel_b = b.rel_from_books()
        # where it is filed: books/<language>/<slug>/, the language folder
        # agreeing with book.json; the layout before languages is read but named
        if b.folder is None:
            bad("%s lies directly under books/ -- it reads as Persian; move it to books/%s/%s"
                % (rel_b, b.lang.folder, os.path.basename(b.dir)))
        elif b.folder != b.lang.folder:
            bad("%s is filed under books/%s/ but book.json says %s (books/%s/)"
                % (rel_b, b.folder, b.lang.name, b.lang.folder))
        else:
            good("book %s (%s)" % (rel_b, b.lang.name))
        # a narration is optional, and each book says in its book.json where its own is
        for key in ("audio", "transcript"):
            v = b.meta.get(key)
            if not v:
                continue
            f = os.path.normpath(os.path.join(b.dir, v))
            rel = os.path.relpath(f, ROOT)
            if os.path.isfile(f):
                good("%s  (%.1f MB)" % (rel, os.path.getsize(f) / 1e6))
            else:
                bad("%s -- %s declares it; copy it there, or use the picker in the page" % (rel, rel_b))
        if os.path.isfile(os.path.join(b.dir, "timings.json")):
            good("%s/timings.json (the alignment)" % rel_b)
        else:
            skip("%s/timings.json (no narration aligned yet)" % rel_b)
    say("")
    say("  Building the readers and the library page (what ./build.sh --html does):")
    if build_readers():
        good("readers and books/index.html built")
    else:
        bad("a reader did not build -- see above; the rest still serves")
    say("")
    say("  Compiling this guide, what the hub's guide button opens (what install.bat does):")
    compile_guide()
    pause()

    banner(4, total, "the certificate")
    if have_cert():
        good(".tls/ has a certificate  (`serve.bat cert` makes a fresh one)")
    elif find_openssl():
        say("  Making a certificate for every name and address this computer has:")
        if make_cert():
            good("certificate made in .tls/")
        else:
            bad("the certificate could not be made -- %s serves plain http until it is" % NAME)
    else:
        bad("no openssl, so no certificate yet -- %s serves plain http for now" % NAME)
    say("")
    say("  Every browser warns once about the certificate: it is ours, accept it")
    say("  (Chrome: Advanced, then Proceed).  And Windows Firewall will ask once whether")
    say("  Python may accept connections: allow it, or only this computer can reach %s." % NAME)
    pause()

    banner(5, total, "done")
    say("  %d checks passed, %d missing." % (counts["ok"], counts["miss"]))
    say("")
    say("  From now on:")
    say("    double-click serve.bat         starts %s and opens the browser on it" % NAME)
    say("    the stop button on any page    stops it (so do Ctrl-C and closing the window)")
    say("    serve.bat setup                runs this wizard again")
    say("    serve.bat stop | status | cert  as ./serve.sh has them")
    with open(MARKER, "w", encoding="utf-8") as f:
        json.dump({"when": time.strftime("%Y-%m-%dT%H:%M:%S"), "python": sys.executable,
                   "version": ver, "ok": counts["ok"], "missing": counts["miss"]}, f, indent=1)
        f.write("\n")
    say("")
    return ask("Start %s now?" % NAME, True)


# ------------------------------------------------------------------ main
def main(argv):
    # the port Parseh keeps, unless this start names another one
    port, verb, browser = network.port(), "start", True
    for a in argv:
        if a in ("start", "setup", "stop", "status", "cert", "readers"):
            verb = a
        elif a.isdigit():
            port = int(a)
        elif a == "--no-browser":
            browser = False
        else:
            sys.exit("unknown argument: %s\n\n%s" % (a, __doc__))
    os.chdir(ROOT)
    if verb == "stop":
        return stop(port)
    if verb == "status":
        url = server_url(port)
        say("running: %s" % url if url else "not running on port %d" % port)
        return 0
    if verb == "cert":
        if not find_openssl():
            say("openssl is needed to make the certificate; `serve.bat setup` offers to install it")
            return 1
        if not make_cert():
            return 1
        if server_url(port):
            say("now: stop %s (the stop button, or `serve.bat stop`) and start it again" % NAME)
        return 0
    if verb == "readers":
        return 0 if build_readers() else 1
    first = not os.path.isfile(MARKER) or not os.path.isfile(os.path.join(ROOT, "books", "index.html"))
    if verb == "setup" or first:
        went = wizard()
        if isinstance(went, tuple) and went[0] == "restart":
            # the wizard made the environment: the rest of the wizard, and
            # the server, belong to the environment's own Python
            return subprocess.call([went[1], os.path.join(LIB, "launcher.py"), "setup"]
                                   + [a for a in argv if a not in ("start", "setup")])
        if not went:
            return 0
    return start(port, browser)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
