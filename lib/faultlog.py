#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server's log, kept for one run more, and a fault report made from it (TO-DO §5.31).

    python3 lib/faultlog.py rotate serve.log     what serve.sh does before it starts the server

THE LOG OF THE RUN BEFORE IS KEPT.  serve.sh used to empty serve.log at every
start, so the traceback that made somebody restart Parseh was erased by the
restart.  Now a start moves serve.log to serve.log.1 (the run before, at most
KEEP_BYTES of its end) and begins an empty serve.log; one run back is kept,
no more.  On Windows the launcher (lib/launcher.py) does the same and copies
every line the server prints into serve.log as well as into its window --
the window stays the log a person watches, the file is the one the page reads.

WHICH FILE IS THIS RUN'S.  serve.sh and the launcher put the path in the
server's environment (LOG_ENV); a server started any other way -- `python3
serve.py` in a terminal -- writes to that terminal, and the page says so.

THE REPORT is plain text a person pastes into an issue: the version, the
system, the Python, which optional parts are installed, and the last
traceback in the logs.  It is REDACTED before it leaves the page: the tokens
of the devices let in, the pairing code, anything that looks like a secret,
the addresses of this network, and the home folder (written ~).  The panel
that shows it is drawn on the computer Parseh runs on only (lib/aboutpage.py).

Standard library only at the top: serve.sh runs this file with whatever
Python it found, and the launcher imports it before the server exists.
"""
import getpass
import os
import platform
import re
import socket
import sys

LOG_ENV = "PARSEH_LOG"
LOG_NAME = "serve.log"
KEEP_BYTES = 1024 * 1024            # the run before: its last megabyte is plenty for a traceback
TAIL_LINES = 60
HIDDEN = "[hidden]"


def log_path(root):
    return os.path.join(root, LOG_NAME)


def previous(path):
    return path + ".1"


# ------------------------------------------------------------------ rotation
def rotate(path, keep=KEEP_BYTES):
    """Before a run: serve.log -> serve.log.1 (its last `keep` bytes, cut at a
    line), and serve.log left empty.  An empty or missing log leaves the run
    before it where it is: a start that wrote nothing is not a run worth the
    one before.  Never raises: a log is never a reason not to start."""
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    try:
        if size > 0:
            old = previous(path)
            if size <= keep:
                os.replace(path, old)
            else:
                with open(path, "rb") as f:
                    f.seek(size - keep)
                    data = f.read()
                nl = data.find(b"\n")
                if 0 <= nl < len(data) - 1:
                    data = data[nl + 1:]
                with open(old + ".part", "wb") as f:
                    f.write(b"[... the start of this log was cut: only its last %d KB are kept]\n"
                            % (keep // 1024))
                    f.write(data)
                os.replace(old + ".part", old)
        with open(path, "wb"):
            pass
        return True
    except OSError:
        try:
            with open(path, "wb"):
                pass
        except OSError:
            pass
        return False


# ------------------------------------------------------------------ the copy (Windows)
def pump(src, console=None, path=None):
    """Copy every line of `src` (a binary pipe: the server's output) to the
    console AND to the log file at `path`, flushing both at every line, until
    the pipe ends.  The launcher's thread on Windows; on Linux it is tested as
    it is.  A console that cannot be written (closed, a strange encoding) does
    not stop the file, nor the file the console."""
    if console is None:
        console = getattr(sys.stdout, "buffer", sys.stdout)
    f = None
    if path:
        try:
            f = open(path, "ab")
        except OSError:
            f = None
    try:
        for line in iter(src.readline, b""):
            for out in (console, f):
                if out is None:
                    continue
                try:
                    out.write(line)
                    out.flush()
                except (OSError, ValueError, TypeError):
                    pass
    finally:
        if f:
            f.close()
        try:
            src.close()
        except (OSError, AttributeError):
            pass


# ------------------------------------------------------------------ reading
def read(path):
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return None


def tail(text, n=TAIL_LINES):
    if not text:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def current_log():
    """The file this run writes to, or None when it writes to a terminal."""
    p = os.environ.get(LOG_ENV) or ""
    return p if p else None


_TB_START = "Traceback (most recent call last):"
_CHAINS = ("During handling of the above exception, another exception occurred:",
           "The above exception was the direct cause of the following exception:")


def _block(lines, i):
    """The traceback starting at lines[i] -> (its lines, the index after it).
    Its frames are indented; it ends with the first line that is not, the
    exception itself (with any indented lines after it, as SyntaxError has)."""
    out = [lines[i]]
    j = i + 1
    while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
        if not lines[j].strip() and j + 1 < len(lines) and not lines[j + 1].startswith((" ", "\t")):
            break
        out.append(lines[j])
        j += 1
    if j < len(lines) and lines[j].strip():
        out.append(lines[j])
        j += 1
        while j < len(lines) and lines[j].startswith((" ", "\t")) and not lines[j].lstrip().startswith("File "):
            out.append(lines[j])
            j += 1
    while out and not out[-1].strip():
        out.pop()
    return out, j


def last_traceback(text):
    """The last Python traceback in `text`, with the ones it was chained to
    ("During handling of the above exception..."), or "" when there is none."""
    if not text:
        return ""
    lines = text.splitlines()
    blocks = []                         # (start, end, lines)
    i = 0
    while i < len(lines):
        if lines[i].strip() == _TB_START:
            got, j = _block(lines, i)
            blocks.append((i, j, got))
            i = max(j, i + 1)
        else:
            i += 1
    if not blocks:
        return ""
    k = len(blocks) - 1
    chain = [blocks[k][2]]
    while k > 0:
        between = [ln.strip() for ln in lines[blocks[k - 1][1]:blocks[k][0]] if ln.strip()]
        if len(between) == 1 and between[0] in _CHAINS:
            chain.insert(0, blocks[k - 1][2] + ["", between[0], ""])
            k -= 1
        else:
            break
    return "\n".join(ln for part in chain for ln in part).rstrip()


# ------------------------------------------------------------------ redaction
# a value after one of these names is a secret whatever it looks like
_NAMED = re.compile(r"(?i)\b(token|secret|password|passwd|api[_-]?key|authorization|cookie|parseh_device)"
                    r"(\"?'?\s*[=:]\s*(?:bearer\s+)?\"?'?)([^\s\"'&;,]+)")
# the pairing code: six of lib/network.py's ALPHABET after the word "code"
_CODE = re.compile(r"(?i)(\bcode\b[^\n]{0,12}?)(?<![A-Z0-9])([A-HJ-NP-Z2-9]{6})(?![A-Za-z0-9])")
# a long random run, as secrets.token_urlsafe makes: letters AND digits, 32 or more
_LONG = re.compile(r"(?<![A-Za-z0-9_-])(?=[A-Za-z0-9_-]*[0-9])(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])")
_IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
_TSNET = re.compile(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net\b")


def _ipv4(m):
    parts = [int(g) for g in m.groups()]
    if any(p > 255 for p in parts):
        return m.group(0)
    if parts[0] == 127 or parts == [0, 0, 0, 0] or parts[0] == 255:
        return m.group(0)                 # loopback, any, broadcast: nobody's address
    return "[address]"


def known_secrets(root):
    """The secrets this Parseh holds that a log could name: the devices' tokens
    and the pairing code of the moment.  Read without making a code."""
    out = []
    try:
        import network
        doc = network._read()
        out.extend(t for t in (doc.get("devices") or {}) if isinstance(t, str) and t)
        c = (getattr(network, "_CODE", None) or {}).get("code")
        if c:
            out.append(c)
    except Exception:                    # noqa: BLE001 -- a report is made even when this cannot be read
        pass
    return out


def redact(text, home=None, user=None, secrets=(), host=None):
    """`text` with what is nobody else's business taken out."""
    if not text:
        return text or ""
    for s in sorted({s for s in secrets if s and len(s) >= 4}, key=len, reverse=True):
        text = text.replace(s, HIDDEN)
        if len(s) >= 16:
            text = text.replace(s[:8], HIDDEN)     # the id Settings shows for a device
    text = _NAMED.sub(lambda m: m.group(1) + m.group(2) + HIDDEN, text)
    text = _CODE.sub(lambda m: m.group(1) + HIDDEN, text)
    text = _LONG.sub(HIDDEN, text)
    text = _TSNET.sub("[address]", text)
    text = _IPV4.sub(_ipv4, text)
    if home:
        home = home.rstrip("/\\")
        if len(home) > 1:
            for h in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
                text = re.sub(re.escape(h) + r"(?=[/\\]|\b|$)", "~", text)
    if user and len(user) >= 2:
        # the account's name where it stands as a folder of its own, outside
        # the home folder too (/run/media/<user>/..., /Volumes, C:\Users)
        text = re.sub(r"(?<=[/\\])" + re.escape(user) + r"(?=[/\\])", "<user>", text)
    if host and len(host) >= 3 and host.lower() not in ("localhost",):
        text = re.sub(r"(?i)(?<![A-Za-z0-9-])" + re.escape(host) + r"(?![A-Za-z0-9-])", "[computer]", text)
    return text


def redactor(root):
    """redact() with this computer's own home, user, host and secrets."""
    try:
        user = getpass.getuser()
    except Exception:                    # noqa: BLE001
        user = None
    try:
        host = socket.gethostname().split(".")[0]
    except Exception:                    # noqa: BLE001
        host = None
    home = os.path.expanduser("~")
    secrets = known_secrets(root)
    return lambda text: redact(text, home=home, user=user, secrets=secrets, host=host)


# ------------------------------------------------------------------ what is installed
def _yesno(v):
    return "yes" if v else "no"


def optional_parts(root):
    """-> [(name, what)]: which optional parts are installed, as Settings knows
    them.  Each is asked on its own, and one that cannot be asked says so."""
    import shutil
    out = []

    def ask(name, fn):
        try:
            out.append((name, fn()))
        except Exception as e:           # noqa: BLE001 -- the report says it could not tell
            out.append((name, "could not tell (%s)" % type(e).__name__))

    def stt():
        import getstt
        r = getstt.runtime()
        if not r.get("ready"):
            return "no" if r.get("state") == "absent" else "not ready (%s)" % r.get("state")
        models = getstt.installed()
        return "yes, %s%s" % (r.get("version") or "", (" -- models: " + ", ".join(models)) if models else " -- no model")

    def analyzers():
        import analysispins
        import getanalysis
        have = [w for w in analysispins.PACKAGES if getanalysis.package_here(w)]
        return ", ".join(have) if have else "none"

    def tex():
        found = [p for p in ("lualatex", "xelatex", "pdflatex") if shutil.which(p)]
        return ", ".join(found) if found else "no"

    def ffmpeg():
        import audiofile
        return _yesno(audiofile.have_ffmpeg())

    def dictionaries():
        import languages
        import lookup
        have = [L.code for L in languages.LANGS.values() if lookup.about(L.code)]
        return ", ".join(have) if have else "none"

    def translation():
        import getmt
        have = ["%s-%s" % p for p in getmt.installed()]
        return ", ".join(have) if have else "none"

    def corpora():
        import corpus
        have = ["%s-%s" % p for p in corpus.installed()]
        return ", ".join(have) if have else "none"

    def synonyms():
        import getsyn
        return _yesno(getsyn.installed())

    def pictograms():
        import getarasaac
        return _yesno(getarasaac.installed())

    def environment():
        import runtime
        prefix, _py = runtime.find_env()
        return prefix or "none (the computer's own Python)"

    ask("Environment", environment)
    ask("Speech to text", stt)
    ask("Word analyzers", analyzers)
    ask("TeX", tex)
    ask("ffmpeg", ffmpeg)
    ask("Dictionaries", dictionaries)
    ask("Translation models", translation)
    ask("Corpora", corpora)
    ask("Synonyms (English)", synonyms)
    ask("Pictograms", pictograms)
    return out


def how_started():
    if os.environ.get("PARSEH_LAUNCHER") == "1":
        return "serve.bat (the Windows launcher)"
    if os.environ.get(LOG_ENV):
        return "serve.sh"
    return "directly (python serve.py), writing to its terminal"


# ------------------------------------------------------------------ the report
def logs(root):
    """-> (this run's text or None, the run before's text or None, this run's path or None)."""
    cur = current_log()
    path = cur or log_path(root)
    now = read(cur) if cur else None
    before = read(previous(path))
    return now, before, cur


def report(root, version, parts=None, redact_with=None):
    """The plain text Copy a report copies, already redacted."""
    now, before, cur = logs(root)
    tb, where = "", ""
    for text, said in ((now, "this run's log"), (before, "the previous run's log")):
        tb = last_traceback(text or "")
        if tb:
            where = said
            break
    if parts is None:
        parts = optional_parts(root)
    lines = ["Parseh fault report", "",
             "What happened (write it here, in your own words):", "", "",
             "Parseh: %s" % version,
             "System: %s %s (%s)" % (platform.system(), platform.release(), platform.machine()),
             "Python: %s (%s)" % (platform.python_version(), sys.executable),
             "Started by: %s" % how_started(),
             "", "Optional parts installed:"]
    lines += ["  %s: %s" % (k, v) for k, v in parts]
    lines += [""]
    if tb:
        lines += ["The last error in the logs (%s):" % where, "", tb]
    else:
        lines += ["No error (Python traceback) in %s." % (
            "this run's log or the previous run's" if cur else "the log files")]
    if not cur:
        lines += ["", "This run writes to the terminal it was started from, not to a file."]
    text = "\n".join(lines) + "\n"
    red = redact_with or redactor(root)
    return red(text)


def _cli(argv):
    if len(argv) >= 3 and argv[1] == "rotate":
        rotate(argv[2])
        return 0
    print(__doc__.split("\n\n")[0])
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
