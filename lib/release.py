#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A release of Parseh: the zip people download, and the manifest inside it.

    python3 lib/release.py build [--ref REF] [--tag TAG] [--out DIR]
        dist/parseh-<version>.zip, made from the commit REF (HEAD when not
        given), with its .sha256 and a copy of its manifest beside it; named
        by TAG instead when one is given -- a rehearsal's, a0.3.2-rc1, makes
        dist/parseh-a0.3.2-rc1.zip, whose manifest says a0.3.2-rc1
    python3 lib/release.py notes VERSION
        that version's section of CHANGELOG.md: the release's notes (a
        rehearsal's tag is given its version's)
    python3 lib/release.py check TAG [--ref REF]
        refuses unless TAG, VERSION, CHANGELOG.md's newest heading and the
        guide's What's new name the same version, and -- for a version's own
        tag, not a rehearsal's -- both carry the day it is released
    python3 lib/release.py guide [--ref REF]
        refuses unless the compiled guide (html-guide/site/) was compiled
        from the sources there are now
    python3 lib/release.py prerelease TAG
        "true" for a rehearsal's tag, "false" for a version's: how GitHub
        is to mark the draft
    python3 lib/release.py compare A B
        whether two builds -- two zips, two manifests, or one of each -- ship
        the same files; a zip is first held to its own manifest
    python3 lib/release.py links [--expect TAG] [--old]
        what every address Parseh names answers, asked live, by hand: the
        update feed, the site, the guide and its icons, the addresses the
        documents give; non-zero when one of them is wrong

A DEVELOPER'S TOOL.  Releasing is a developer's act, so this is a command of
one line; nobody who uses Parseh ever runs it.  docs/releasing.md says when
to run which.

ONE BUILDER.  GitHub builds a release when a tag is pushed
(.github/workflows/release.yml runs `check` and `guide`, then `build`), and
the developer builds the very same zip on his own machine before any tag
exists: to install it, find a fault, fix it and build the same number
again.  Both run this file, because a local build made any other way would
prove nothing about CI's.

WHAT A RELEASE IS.  `git archive` of one commit, less what .gitattributes
marks export-ignore.  Only what is committed: a file changed or made since,
and not committed, is not in it, and a build from HEAD names every such file
so that nobody installs a fix that is not there.  The zip is written here,
in Python, from git archive's tar, not by `git archive --format=zip`: that
would need --add-virtual-file to put the manifest in, which an older git (a
CI runner's, say) lacks, and each git version would make the zip's entries
its own way.  Here they are made one way everywhere: Unix modes, so
install.sh and serve.sh stay runnable once unzipped; the commit's time on
every entry and the commit's id as the zip's comment, as git's own zip has;
the same compression.  Git runs with what could make two machines disagree
switched off -- core.autocrlf (a Windows git's default would turn every text
file CRLF), core.eol, tar.umask, a personal or a system-wide attributes file
-- so the bytes are the commit's as .gitattributes shapes them: the .bat
files CRLF, since cmd.exe misreads bare LF, and every other file as
committed.

THE MANIFEST, .parseh-release.json in the zip's one folder, beside
install.sh, and so at the root of every install made from it:

    {"format": "parseh-release/1",
     "version": "<VERSION at that commit, or the rehearsal's tag built>",
     "commit": "<the commit's full id>",
     "built": "<the commit's time, UTC, ISO 8601>",
     "data_formats": {<lib/version.formats() of that tree>},
     "environment": {"conda": {"<name>": "<the line environment.yml gives>"},
                     "pip":   {"<name>": "<the line environment.yml gives>"}},
     "files": {"<path from the install's root>":
                   {"sha256": "<hex>", "size": <bytes>, "mode": "0644" | "0755"}}}

It is made FROM THE ARCHIVE, after export-ignore has had its say, so it can
never disagree with what ships: every file of the zip is in "files" (all but
the manifest itself), hashed as archived.  A .bat is hashed as its CRLF
bytes, which is what an unpacked install holds; git's own blob ids are of
the LF text and would never match it.  "built" is the commit's time and not
the clock's, so two builds of one commit make the same manifest -- and, where
the two machines' zlib agree, the same zip.  "data_formats" and
"environment" are what an update from Settings (TO-DO §13.16) compares: to
know whether a step back may lose data, and whether the environment must
change.  Both are read from the archived tree itself, by its own
lib/version.py and its own lib/runtime.env_spec, in a separate Python that
sees nothing else -- so they are that commit's, whatever checkout builds it,
and whatever they need has to be the standard library, since CI has nothing
more.  No release without one: the builder puts the manifest in the zip or
writes no zip.

WHAT A BUILD REFUSES: the traps that have bitten somebody, checked on the
archive itself, so that a careless edit of .gitattributes fails here and not
in somebody's install (audit() below; tests/test_release.py holds
.gitattributes' own list):
  - a folder Parseh writes into, missing -- git archive keeps no empty
    folder, and clips/README.md, exercises/README.md and the .gitkeeps are
    why they exist -- or a file a release cannot do without;
  - a .bat with a bare LF, or a launcher that lost its executable bit;
  - anything personal and any content (TO-DO §18: Parseh ships none): .tls/,
    and in config/, books/, youtube/videos/, markdown/library/, exercises/,
    clips/, youtube/anki/, dict/, corpus/, mt/, components/, stt/ and arasaac/
    anything but a .gitkeep or a README.md;
  - tests/, or a GIF in docs/, which export-ignore keeps out;
  - a link (Windows unpacks one as a small text file), or a committed
    .parseh-release.json.

THE CHANGELOG.  CHANGELOG.md's headings read "## [aX.Y.Z] - YYYY-MM-DD",
newest first, with "unreleased" in place of the date until release day, and
lib/changelog.py is the one reader of them: `notes` cuts a release's notes
with it, word for word, and `check` holds the newest heading to VERSION and
the tag with it, so a heading the guide's test accepts is one a release
accepts.  The guide's What's new says the same versions on the same days in
its own words, and is read by the same module; `check` holds the tagged
version's heading there too, since CI runs no test suite (the owner,
2026-09-25) and a release whose guide still says "not yet released" would
ship saying so.  VERSION is read by lib/version.py, its one reader, and
compared by its one rule.

REHEARSALS (the owner, 2026-09-25).  A release is tried out on GitHub first
under a rehearsal's tag, `aX.Y.Z-rcN` (lib/version.py's rule 4: it sorts
before aX.Y.Z), while VERSION and both headings already say aX.Y.Z:
`check` passes it with the headings still undated, `build --tag` names the
zip, its folder and its manifest's version by the tag, and the workflow
marks its draft a prerelease, which GitHub's "latest" -- what Settings asks
for -- never answers with.  The draft and the tag are deleted once looked
at, and the version's own tag follows (docs/releasing.md).

THE GUIDE.  html-guide/site/ is committed, compiled, and ships as it is: a
release never compiles it.  `guide` refuses when the sources a compile reads
-- the pages and their pictures, the engine, the studio's renderer (the
engine's own fingerprint.py says which) -- are not what the committed
site/build.json was compiled from, or when that compile had errors; asked
of the tree's own engine in a Python of its own, as the data formats are.

THE LIVE CHECK, `links` (docs/releasing.md says when).  It is the one command
here that asks the internet, and is therefore run BY HAND: never by a
workflow that gates a release (a site that is down must not stop a release)
and never by the unit suite (tests/test_release_links.py drives it offline,
and over a local socket).  Every address lib/project.py names is asked and
printed with the chain that answered -- the first hop and where it ends --
and the command exits non-zero when one of these is wrong: the update feed
(its tag_name is --expect's tag, when one is given) and the latest-release
page; the site; the guide, which must END at the guide's own address with 200
without leaving the domain (the one hop allowed is GitHub's own from /guide to
/guide/, and a person's http:// or www. is sent to https and the bare
domain); a deep link into the guide, 200 at its own address, with the
published bar in it and, with a tag, the tag's version; the four icons the
phone app is installed with, each 200 image/png with NO redirect at all, since
a machine fetches those and a failure there is silent; and every address of
the project written in README.md, docs/ and the guide's sources, 200 at its
end.  It REPORTS, and never fails on, what the organisation site's own address
for the guide and the old repository's path under the domain answer, and with
--old what the OLD places answer now (how GitHub's redirect after the move is
proved).  Redirects are followed here, by hand, so the chain can be printed
and judged; each request has 15 seconds, at most six redirects are followed,
nothing is retried, and one failure never stops the rest.

Standard library only: CI runs it with a bare Python.  Of Parseh's own modules
it reads lib/version.py and lib/changelog.py as always, and lib/project.py,
only inside `links`.
"""
import argparse
import collections
import datetime
import hashlib
import http.client
import io
import json
import os
import re
import socket
import ssl
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(LIB, ".."))

MANIFEST = ".parseh-release.json"
FORMAT = "parseh-release/1"
CHANGELOG = "CHANGELOG.md"
VERSION_FILE = "VERSION"
TAG_PREFIX = "refs/tags/"
GUIDE_BUILT = "html-guide/site/build.json"

# THE FOLDERS PARSEH WRITES INTO, which a fresh install must already have, and
# the folders the owner decided ship: each must hold at least one file.
MUST_HOLD = ("books/", "youtube/videos/", "markdown/library/", "exercises/", "clips/",
             "config/", "dict/", "html-guide/site/", "lib/fonts/", "lib/mathjax/", "docs/lang/")
# the files a release cannot do without
MUST_SHIP = ("LICENSE", VERSION_FILE, "environment.yml", "install.sh", "install.bat",
             "serve.sh", "serve.bat", "serve.py", "html-guide/index.html",
             "lib/fonts/OFL.txt", "lib/fonts/GUST-FONT-LICENSE.txt",
             "clips/README.md", "exercises/README.md", "config/.gitkeep", "dict/.gitkeep")
# what a person runs by name or by a double click: executable, when shipped
RUNNABLE = ("install.sh", "serve.sh", "build.sh", "Parseh.command", "serve.py")
# where a person's own things live: a release carries only the scaffolding
CONTENT = ("books/", "youtube/videos/", "markdown/library/", "exercises/", "clips/",
           "youtube/anki/", "config/", "dict/", "corpus/", "mt/", "components/", "texmf/",
           "stt/", "llm-scoring/", "arasaac/", "analysis/")
SCAFFOLDING = (".gitkeep", "README.md")
# never in a release, whatever .gitattributes says
NEVER = (".tls/", "tests/", ".github/", ".runtime/", ".parseh-update/", "dist/",
         ":memory:.ses",
         "docs/lm-likelihood-evaluation.md",
         "tools/", ".speech-release-build/",
         # the LaTeX drawings, made from their blocks and made again at will
         "markdown/latex/",
         "old stuff/", "test for books/", "Parseh-Personal/")
NEVER_LIKE = (re.compile(r"^docs/[^/]*\.gif$", re.I),)

# THE PROBE, run in a Python of its own in the unpacked tree: that tree's own
# data formats and environment, from its own code.  -I keeps the builder's
# own lib/ and any PYTHONPATH out of it.
PROBE = r"""
import json, os, sys
tree = sys.argv[1]
sys.path.insert(0, os.path.join(tree, "lib"))
import runtime, version
spec = runtime.env_spec(os.path.join(tree, "environment.yml"))
json.dump({"data_formats": version.formats(),
           "environment": {kind: dict(pairs) for kind, pairs in spec.items()}},
          sys.stdout, sort_keys=True)
"""

# THE GUIDE'S PROBE, the same way: what a compile of that tree's guide would
# read, hashed by that tree's own engine (html-guide/engine/fingerprint.py,
# the rule the compile itself writes into site/build.json)
GUIDE_PROBE = r"""
import os, sys
guide = os.path.join(sys.argv[1], "html-guide")
sys.path.insert(0, guide)
from engine.fingerprint import fingerprint
sys.stdout.write(fingerprint(guide))
"""


class Refused(Exception):
    """What the builder will not do, in words for the person who asked."""


# ------------------------------------------------------------------ git
def _git(root, *args, binary=False, env=None):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, env=env)
    if r.returncode:
        words = [a for i, a in enumerate(args) if a != "-c" and (i == 0 or args[i - 1] != "-c")]
        raise Refused("git %s failed: %s" % (words[0] if words else "",
                                             r.stderr.decode("utf-8", "replace").strip()))
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def commit_of(ref, root=ROOT):
    """REF -> the full id of the commit it names, or Refused."""
    r = subprocess.run(["git", "-C", root, "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                       capture_output=True)
    if r.returncode:
        raise Refused("%r names no commit in %s" % (ref, root))
    return r.stdout.decode().strip()


def read_file(path, ref=None, root=ROOT):
    """A file's text: at the commit REF, or in the working tree when REF is
    None.  None when it is not there."""
    if ref is None:
        try:
            with open(os.path.join(root, path), encoding="utf-8", newline="") as f:
                return f.read()
        except FileNotFoundError:
            return None
    r = subprocess.run(["git", "-C", root, "show", "%s:%s" % (ref, path)], capture_output=True)
    return r.stdout.decode("utf-8") if r.returncode == 0 else None


def not_committed(root=ROOT):
    """(changed, new): the tracked files changed in the working tree and the
    new files nobody committed -- all of them left out of a build of HEAD."""
    out = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    changed, new = [], []
    entries = out.split("\0")
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        xy, path = e[:2], e[3:]
        if xy == "??":
            new.append(path)
        else:
            changed.append(path)
            if "R" in xy or "C" in xy:       # a rename carries its old name next
                i += 1
    return changed, new


# ------------------------------------------------------------------ versions
def _version():
    """lib/version.py -- the one reader of VERSION, and the one rule for what
    a version is and how two compare -> the module.  It reads this
    checkout's own VERSION as it loads, and where it will not, nothing here
    can say what a version is: Refused, in its words."""
    if LIB not in sys.path:
        sys.path.insert(0, LIB)
    try:
        import version
    except ValueError as e:
        raise Refused("lib/version.py will not load: %s" % e)
    return version


def _changelog():
    """lib/changelog.py, the one reader of CHANGELOG.md and of the guide's
    What's new -> the module."""
    _version()                                # its words first, when it is the trouble
    import changelog
    return changelog


def checked_version(text, where):
    """VERSION's text, read at `where` (the working tree, or a commit) -> the
    version, or Refused saying what is wrong.  Read by lib/version.spelt, as
    every VERSION is: what it accepts is a stage letter, digits, dots and
    nothing else, so the name is safe as a tag, a folder and a file too."""
    if text is None:
        raise Refused("%s has no %s file: a release is named by it" % (where, VERSION_FILE))
    try:
        return _version().spelt(text, "%s's %s" % (where, VERSION_FILE))
    except ValueError as e:
        raise Refused(str(e))


def _tag(tag):
    return tag[len(TAG_PREFIX):] if tag.startswith(TAG_PREFIX) else tag


def named(tag, version):
    """The tag a build is named by, held to the VERSION of the commit built
    -> (the tag, whether it is a rehearsal's).  A version's own tag must be
    VERSION as it is spelt; a rehearsal's, aX.Y.Z-rcN, must rehearse it."""
    V = _version()
    try:
        rehearsal = V.rc(tag) is not None
    except ValueError as e:
        raise Refused("the tag %s is not a version's: %s" % (tag, e))
    if V.base(tag) != version:
        if rehearsal:
            raise Refused("the tag %s rehearses %s, but %s says %s"
                          % (tag, V.base(tag), VERSION_FILE, version))
        raise Refused("the tag is %s, but %s says %s" % (tag, VERSION_FILE, version))
    return tag, rehearsal


def prerelease(tag):
    """"true" for a rehearsal's tag (aX.Y.Z-rcN), "false" for a version's:
    how the workflow marks the draft on GitHub, spelt as gh reads a flag."""
    tag = _tag(tag)
    try:
        return "true" if _version().rc(tag) is not None else "false"
    except ValueError as e:
        raise Refused("the tag %s is not a version's: %s" % (tag, e))


# ------------------------------------------------------------------ the changelog
def _sections(ref, root):
    """CHANGELOG.md, in the working tree or at REF, read by lib/changelog.py
    -> [Section, ...], newest first; Refused with its words when it will not
    read it."""
    changelog = _changelog()
    text = read_file(CHANGELOG, ref, root)
    if text is None:
        raise Refused("%s has no %s" % ("the commit %s" % ref if ref else root, CHANGELOG))
    try:
        return changelog.parse(text, where=CHANGELOG if ref is None else "%s at %s" % (CHANGELOG, ref))
    except changelog.ChangelogError as e:
        raise Refused(str(e))


def _guide_headings(ref, root):
    """The guide's What's new, in the working tree or at REF, read by
    lib/changelog.py -> [Heading, ...]; Refused with its words."""
    changelog = _changelog()
    page = changelog.GUIDE_PAGE
    text = read_file(page, ref, root)
    if text is None:
        raise Refused("%s has no %s, the guide's What's new, which names every version and "
                      "the day it was released" % ("the commit %s" % ref if ref else root, page))
    try:
        return changelog.whats_new(text, where=page if ref is None else "%s at %s" % (page, ref))[0]
    except changelog.ChangelogError as e:
        raise Refused(str(e))


def says_something(section):
    """Whether a section has a line of its own under its headings: one that
    says only "### Added" would make empty notes."""
    return any(line.strip() and not line.lstrip().startswith("#") for line in section.body.splitlines())


def notes(version, ref=None, root=ROOT):
    """The CHANGELOG section of VERSION, word for word: a release's notes.  A
    rehearsal's tag is given the section of the version it rehearses."""
    sections = _sections(ref, root)
    try:
        version = _version().base(_tag(version))
    except ValueError:
        pass                                  # not a version: "no section for" says so
    for s in sections:
        if s.version == version:
            if not says_something(s):
                raise Refused("%s's section for %s is empty" % (CHANGELOG, version))
            return s.body + "\n"
    raise Refused("%s has no section for %s (it has: %s)"
                  % (CHANGELOG, version, ", ".join(s.version for s in sections)))


def check(tag, ref=None, root=ROOT):
    """The tag, VERSION, CHANGELOG.md's newest heading and the guide's What's
    new, held together -> the version they agree on, or Refused naming every
    disagreement.

    For a version's own tag both headings must carry the day it is released,
    and the same day: "unreleased" (and the guide's "not yet released") is
    for a version still being made, never for one being tagged.  A
    rehearsal's tag, aX.Y.Z-rcN, is held to everything else -- it rehearses
    VERSION's version, which has its section and its heading -- but may come
    before the day is written: it is how the release is tried out before
    that day (the owner, 2026-09-25)."""
    tag = _tag(tag)
    where = "the commit %s" % ref if ref else "the working tree"
    version = checked_version(read_file(VERSION_FILE, ref, root), where)
    problems, top = [], None
    try:
        _, rehearsal = named(tag, version)
    except Refused as e:
        problems.append(str(e))
        try:
            rehearsal = _version().rc(tag) is not None
        except ValueError:
            rehearsal = False
    try:
        top = _sections(ref, root)[0]
    except Refused as e:
        problems.append(str(e))
    else:
        if top.version != version:
            problems.append("%s's newest section is %s, but %s says %s"
                            % (CHANGELOG, top.version, VERSION_FILE, version))
        if not top.released and not rehearsal:
            problems.append("%s's %s section still says 'unreleased': give its heading the "
                            "release's date, '## [%s] - YYYY-MM-DD', before tagging"
                            % (CHANGELOG, top.version, top.version))
        if not says_something(top):
            problems.append("%s's %s section is empty: it becomes the release's notes"
                            % (CHANGELOG, top.version))
    try:
        heads = _guide_headings(ref, root)
    except Refused as e:
        problems.append(str(e))
    else:
        page = _changelog().GUIDE_PAGE
        mine = [h for h in heads if h.version == version]
        if not mine:
            problems.append("the guide's What's new (%s) has no heading for %s" % (page, version))
        elif not rehearsal and not mine[0].released:
            # THE DAY SUGGESTED IS THE CHANGELOG'S, OR NONE: a real-looking day
            # here ("24 September 2026") would be copied as it stands by
            # whoever follows the message blindly, and tag the wrong day
            dated = top is not None and top.version == version and top.released
            day = ("'%s — %s'" % (version, _changelog().said(top.date)) if dated else
                   "'%s — D Month YYYY', the day as the guide writes one (5 October 2026, "
                   "no leading zero), and the changelog's" % version)
            problems.append("the guide's What's new still says '%s — not yet released' (%s:%d): "
                            "give it the release's day, %s, before tagging"
                            % (version, page, mine[0].line, day))
        elif (not rehearsal and top is not None and top.version == version and top.released
              and mine[0].date != top.date):
            problems.append("the guide's What's new says %s was released on %s (%s:%d), and "
                            "%s says %s" % (version, _changelog().said(mine[0].date), page,
                                            mine[0].line, CHANGELOG, top.date))
    if problems:
        raise Refused("Not released: " + "; ".join(problems) + ".")
    return version


# ------------------------------------------------------------------ the guide
def guide(ref=None, root=ROOT):
    """Whether the compiled guide is in step with its sources, in the working
    tree or at the commit REF -> what its site/build.json says (pages,
    warnings ...), or Refused saying what is out of step and what to do."""
    if ref is None:
        return _guide_in(root, "the working tree")
    commit = commit_of(ref, root)
    prefix = "parseh/"
    with tempfile.TemporaryDirectory(prefix="parseh-release-") as td:
        _unpack_to(unpack(archive(commit, prefix, root), prefix), td)
        return _guide_in(td, "the commit %s" % commit[:12])


def _guide_in(tree, where):
    todo = ("compile the guide (the button on the guide's own front page, or "
            "python3 html-guide/build.py) and commit html-guide/site/ with the release")
    try:
        with open(os.path.join(tree, *GUIDE_BUILT.split("/")), encoding="utf-8") as f:
            info = json.load(f)
    except FileNotFoundError:
        raise Refused("Not in step: %s has no compiled guide (%s is missing): %s."
                      % (where, GUIDE_BUILT, todo))
    except ValueError:
        raise Refused("Not in step: %s's %s cannot be read: %s." % (where, GUIDE_BUILT, todo))
    r = subprocess.run([sys.executable, "-I", "-B", "-c", GUIDE_PROBE, tree], cwd=tree,
                       capture_output=True, timeout=300)
    if r.returncode:
        err = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise Refused("the guide's engine could not say what a compile of it reads "
                      "(html-guide/engine/fingerprint.py): %s"
                      % (err[-1] if err else "exit %d" % r.returncode))
    problems = []
    if not isinstance(info, dict) or info.get("fingerprint") != r.stdout.decode("ascii", "replace"):
        problems.append("the compiled guide (html-guide/site/) is not what %s's sources compile "
                        "to: a page, a picture, the guide's engine or the studio's renderer "
                        "changed after the last compile" % where)
    elif info.get("errors"):
        problems.append("its last compile had %s error(s)" % info["errors"])
    if problems:
        raise Refused("Not in step: %s; %s." % ("; ".join(problems), todo))
    return info


# ------------------------------------------------------------------ building
def archive(commit, prefix, root=ROOT):
    """The commit as git archive's tar, every file under PREFIX -- with the
    settings that could make two machines' archives differ switched off."""
    with tempfile.TemporaryDirectory(prefix="parseh-release-") as td:
        env = dict(os.environ, GIT_ATTR_NOSYSTEM="1")
        return _git(root, "-c", "core.autocrlf=false", "-c", "core.eol=lf", "-c", "tar.umask=0022",
                    "-c", "core.attributesFile=" + os.path.join(td, "none"),
                    "archive", "--format=tar", "--prefix=" + prefix, commit, binary=True, env=env)


def unpack(tar, prefix):
    """git archive's tar -> [(path from the install's root, bytes, mode)], in
    the archive's order.  Only files: a folder is where its files are."""
    files = []
    with tarfile.open(fileobj=io.BytesIO(tar), mode="r:") as tf:
        for m in tf:
            if m.isdir() and (m.name.rstrip("/") + "/").startswith(prefix):
                continue                                   # tarfile names a folder without its "/"
            if not m.name.startswith(prefix):
                raise Refused("the archive holds %r, outside %s" % (m.name, prefix))
            rel = m.name[len(prefix):]
            if not m.isfile():
                raise Refused("%s is a link: a release ships files, since Windows unpacks a link as "
                              "a small text file" % rel)
            if rel.startswith("/") or ".." in rel.split("/"):
                raise Refused("the archive holds a path that leaves its folder: %r" % rel)
            files.append((rel, tf.extractfile(m).read(), 0o755 if m.mode & 0o111 else 0o644))
    return files


def audit(files):
    """What is wrong with a release made of FILES, in words: [] when nothing."""
    paths = {rel: (data, mode) for rel, data, mode in files}
    problems = []
    for folder in MUST_HOLD:
        if not any(p.startswith(folder) for p in paths):
            problems.append("%s is missing: git archive keeps no empty folder, so it needs a file "
                            "(a .gitkeep or a README.md) that is not export-ignored" % folder)
    for name in MUST_SHIP:
        if name not in paths:
            problems.append("%s is missing" % name)
    if MANIFEST in paths:
        problems.append("%s is committed: the builder writes it" % MANIFEST)
    for name in RUNNABLE:
        if name in paths and paths[name][1] != 0o755:
            problems.append("%s is not executable (git update-index --chmod=+x %s)" % (name, name))
    for rel, (data, _mode) in paths.items():
        if rel.lower().endswith(".bat") and (re.search(rb"(?<!\r)\n", data) or b"\r\n" not in data):
            problems.append("%s has bare LF line endings, which cmd.exe misreads "
                            "(.gitattributes: *.bat text eol=crlf)" % rel)
        if any(rel.startswith(n) for n in NEVER) or any(r.match(rel) for r in NEVER_LIKE):
            problems.append("%s must never ship" % rel)
        elif any(rel.startswith(c) for c in CONTENT) and rel.rsplit("/", 1)[-1] not in SCAFFOLDING:
            problems.append("%s is somebody's content or settings, and Parseh ships none" % rel)
    return problems


def describe(tree):
    """{"data_formats", "environment"} of the tree unpacked at TREE, said by
    its own code in a Python of its own."""
    r = subprocess.run([sys.executable, "-I", "-B", "-c", PROBE, tree], cwd=tree,
                       capture_output=True, timeout=300)
    if r.returncode:
        err = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise Refused("the tree could not say its data formats and environment "
                      "(lib/version.formats(), lib/runtime.env_spec()): %s"
                      % (err[-1] if err else "exit %d" % r.returncode))
    try:
        said = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        raise Refused("the tree's data formats and environment came back as something other than "
                      "JSON: does lib/version.py print when it is imported?")
    if not isinstance(said.get("data_formats"), dict) or not said["data_formats"]:
        raise Refused("lib/version.formats() said no data formats: a release must say which it writes")
    return said


def _unpack_to(files, dest):
    for rel, data, mode in files:
        path = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        os.chmod(path, mode)


def manifest_of(files, version, commit, when, described):
    return {"format": FORMAT,
            "version": version,
            "commit": commit,
            "built": datetime.datetime.fromtimestamp(when, datetime.timezone.utc)
                                      .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_formats": described["data_formats"],
            "environment": described["environment"],
            "files": {rel: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                            "mode": "%04o" % mode}
                      for rel, data, mode in files}}


def manifest_bytes(manifest):
    """The manifest as it is written: JSON, one line for each file, so that
    two of them can be read side by side, and the same bytes every time."""
    head = json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=1, ensure_ascii=False)
    files = ",\n".join("  %s: %s" % (json.dumps(path, ensure_ascii=False), json.dumps(entry))
                       for path, entry in manifest["files"].items())
    return (head[:-2] + ',\n "files": {\n' + files + "\n }\n}\n").encode("utf-8")


def zip_bytes(files, manifest, prefix, when, commit):
    """The release's zip: every file under PREFIX with its mode and the
    commit's time, a folder entry before the first file in it, the manifest
    last, and the commit's id as the zip's comment."""
    stamp = time.gmtime(max(when, 315532800))[:6]          # a zip cannot say before 1980
    buf = io.BytesIO()
    made = set()

    def entry(name, mode):
        zi = zipfile.ZipInfo(name, stamp)
        zi.create_system = 3                                # Unix: unzip applies the modes
        zi.external_attr = mode << 16
        # the time again, as Unix time: the DOS time above is the commit's
        # in UTC (the builder's own zone would make two builds differ), and
        # an unzip that reads this shows it in the person's own zone
        if 0 <= when < 2 ** 31:
            zi.extra = struct.pack("<HHBI", 0x5455, 5, 1, when)
        return zi

    with zipfile.ZipFile(buf, "w") as z:
        z.comment = commit.encode("ascii")

        def folders(rel):
            parts = (prefix + rel).split("/")[:-1]
            for i in range(1, len(parts) + 1):
                d = "/".join(parts[:i]) + "/"
                if d not in made:
                    made.add(d)
                    zi = entry(d, 0o40755)
                    zi.external_attr |= 0x10                # and MS-DOS's own folder flag
                    z.writestr(zi, b"")

        for rel, data, mode in files + [(MANIFEST, manifest_bytes(manifest), 0o644)]:
            folders(rel)
            zi = entry(prefix + rel, 0o100000 | mode)
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, data, compresslevel=9)
    return buf.getvalue()


def build(ref="HEAD", out=None, root=ROOT, say=print, tag=None):
    """Build the release of the commit REF into OUT (dist/ by default) ->
    {"zip", "sha256", "manifest", "manifest_file", "sha256_file"}.

    Named by the commit's VERSION -- or by TAG, when one is given, which must
    be VERSION's own or a rehearsal of it (named()): the zip, the folder in
    it and the manifest's "version" all say the tag, so that a rehearsal's
    install says it was one, and an update from it to the version itself
    goes forward (lib/version.py's rule 4)."""
    commit = commit_of(ref, root)
    head = commit == commit_of("HEAD", root)
    rehearsal = False
    try:
        version = checked_version(read_file(VERSION_FILE, commit, root), "the commit %s" % commit[:12])
        if tag is not None:
            version, rehearsal = named(_tag(tag), version)
        prefix = "parseh-%s/" % version
        when = int(_git(root, "log", "-1", "--format=%ct", commit).strip())
        files = unpack(archive(commit, prefix, root), prefix)
        problems = audit(files)
        if problems:
            raise Refused("Not built -- the release of %s would be wrong:\n  - %s"
                          % (commit[:12], "\n  - ".join(problems)))
        with tempfile.TemporaryDirectory(prefix="parseh-release-") as td:
            _unpack_to(files, td)
            described = describe(td)
    except Refused as e:
        # the likeliest reason, when the working tree is ahead of its commit
        changed, new = not_committed(root) if head else ([], [])
        if changed or new:
            raise Refused("%s\n(%d files are changed or new and not committed: a release is built "
                          "from a commit, so commit first)" % (e, len(changed) + len(new)))
        raise
    manifest = manifest_of(files, version, commit, when, described)
    data = zip_bytes(files, manifest, prefix, when, commit)

    out = os.path.abspath(out or os.path.join(root, "dist"))
    os.makedirs(out, exist_ok=True)
    name = "parseh-%s.zip" % version
    dest = os.path.join(out, name)
    part = dest + ".part"
    with open(part, "wb") as f:
        f.write(data)
    os.replace(part, dest)
    digest = hashlib.sha256(data).hexdigest()
    sha_file = dest + ".sha256"
    with open(sha_file, "w", encoding="utf-8", newline="\n") as f:
        f.write("%s  %s\n" % (digest, name))             # the form `sha256sum -c` reads
    man_file = os.path.join(out, "parseh-%s.manifest.json" % version)
    with open(man_file, "wb") as f:
        f.write(manifest_bytes(manifest))

    try:
        shown = os.path.relpath(dest)
    except ValueError:                                     # another drive, on Windows
        shown = dest
    say("Built %s: %d files, %.1f MB, from commit %s (%s)."
        % (shown, len(files), len(data) / 1e6, commit[:12], manifest["built"]))
    if rehearsal:
        say("A rehearsal of %s: its manifest says %s, and an install made from it updates "
            "forward to %s." % (_version().base(version), version, _version().base(version)))
    say("sha256 %s" % digest)
    if head:
        changed, new = not_committed(root)
        if changed or new:
            say("NOT IN THIS BUILD, because not committed (git archive takes the commit alone):")
            for label, paths in (("changed", changed), ("new", new)):
                for p in paths[:12]:
                    say("  %s  %s" % (label, p))
                if len(paths) > 12:
                    say("  ... and %d more %s" % (len(paths) - 12, label))
    # the one attributes file git archive cannot be told to leave alone
    info = os.path.join(root, _git(root, "rev-parse", "--git-path", "info/attributes").strip())
    if os.path.isfile(info):
        with open(info, encoding="utf-8", errors="replace") as f:
            if any(line.strip() and not line.lstrip().startswith("#") for line in f):
                say("NOTE: .git/info/attributes has rules of its own, which this build obeyed "
                    "and CI's will not: compare the two builds' manifests.")
    return {"zip": dest, "sha256": digest, "manifest": manifest,
            "manifest_file": man_file, "sha256_file": sha_file}


# ------------------------------------------------------------------ reading and comparing
def read_manifest(path):
    """A zip's manifest, or a manifest's own file -> (manifest, problems):
    for a zip, what in it disagrees with its own manifest ([] when all is
    well; a manifest's own file cannot be held to anything)."""
    if not zipfile.is_zipfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f), []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.count("/") == 1 and n.endswith("/" + MANIFEST)]
        if len(names) != 1:
            raise Refused("%s has no %s in one folder at its top: not a release of Parseh"
                          % (path, MANIFEST))
        prefix = names[0][:-len(MANIFEST)]
        manifest = json.loads(z.read(names[0]).decode("utf-8"))
        listed = manifest.get("files", {})
        problems, seen = [], set()
        for zi in z.infolist():
            if zi.is_dir() or zi.filename == names[0]:
                continue
            if not zi.filename.startswith(prefix):
                problems.append("%s is outside %s" % (zi.filename, prefix))
                continue
            rel = zi.filename[len(prefix):]
            seen.add(rel)
            want = listed.get(rel)
            if want is None:
                problems.append("%s is in the zip and not in its manifest" % rel)
            elif hashlib.sha256(z.read(zi)).hexdigest() != want.get("sha256"):
                problems.append("%s is not the file its manifest hashed" % rel)
            elif zi.create_system != 3 or "%04o" % ((zi.external_attr >> 16) & 0o777) != want.get("mode"):
                # a zip packed again on Windows keeps the bytes and loses
                # the modes: install.sh would no longer run
                problems.append("%s has lost the mode its manifest gives it (%s)" % (rel, want.get("mode")))
        problems += ["%s is in the manifest and not in the zip" % rel for rel in listed if rel not in seen]
    return manifest, problems


def compare(a, b):
    """Two builds -> (agree, [what was found, in words])."""
    ma, pa = read_manifest(a)
    mb, pb = read_manifest(b)
    # each named as briefly as tells them apart: dist/parseh-X.zip and the
    # one downloaded from the draft share a name
    na, nb = os.path.basename(a), os.path.basename(b)
    if na == nb:
        na, nb = a, b
    said, differ = [], []
    for name, problems in ((na, pa), (nb, pb)):
        for p in problems[:20]:
            differ.append("%s: %s" % (name, p))
        if len(problems) > 20:
            differ.append("%s: ... and %d more" % (name, len(problems) - 20))
    for key in ("format", "version", "commit", "data_formats", "environment"):
        if ma.get(key) != mb.get(key):
            differ.append("%s: %s against %s" % (key, json.dumps(ma.get(key)), json.dumps(mb.get(key))))
    fa, fb = ma.get("files", {}), mb.get("files", {})
    for label, only in (("only in " + na, [p for p in fa if p not in fb]),
                        ("only in " + nb, [p for p in fb if p not in fa]),
                        ("not the same file", [p for p in fa if p in fb and fa[p] != fb[p]])):
        for p in only[:20]:
            differ.append("%s: %s" % (label, p))
        if len(only) > 20:
            differ.append("%s: ... and %d more" % (label, len(only) - 20))
    if differ:
        return False, differ
    said.append("They agree: %s at commit %s, %d files, every path, hash and mode the same."
                % (ma.get("version"), (ma.get("commit") or "")[:12], len(fa)))
    if zipfile.is_zipfile(a) and zipfile.is_zipfile(b):
        same = _sha256_of(a) == _sha256_of(b)
        said.append("The two zips are byte for byte the same file." if same else
                    "The two zip files differ as files (compression is each machine's zlib's); "
                    "what they unpack to is the same.")
    return True, said


def _sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ------------------------------------------------------------------ links: what every address answers, asked live
# THE OLD PLACE, written here and ONLY here, and in halves: a test keeps the old
# account's name out of the whole tree (tests/test_project.py), and this command
# alone has to ask the old addresses what they answer now -- `--old`, the proof
# that GitHub's redirect after the transfer works and that the old Pages
# address is dead.  Never write it whole.
OLD_ACCOUNT = "Addicted2" + "Bayesian" + "Epistemology"

REDIRECTS = (301, 302, 303, 307, 308)     # the answers that send a request on
HOP_LIMIT = 6              # redirects followed by hand; a seventh is a fault
TIMEOUT = 15               # seconds for each request
PAUSE = 0.25               # seconds between two requests: courtesy, never a retry
PAGE_KEEP = 256 * 1024     # how much of a page is read: its first part holds the bar
FEED_KEEP = 1 << 20        # and of the feed's JSON
BAR_WITHIN = 8000          # the bar is a link to the site this far into the page's body
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# THE PHONE APP'S ICONS and the side of each, which `links` asks for under
# project.ICONS_URL.  lib/mobile.py names them and lib/icons/ holds them
# (tests/test_release_links.py holds the three lists to one another).
ICON_FILES = {"parseh-192.png": 192, "parseh-512.png": 512,
              "parseh-maskable-512.png": 512, "apple-touch-icon.png": 180}
DEEP_LINK = "site/reference/whats-new.html"     # a page of the published guide, under project.SITE
LINK_TEXT = (".md", ".html", ".txt")

# one answer: the address asked, its status (None: nobody answered), the
# Location of a redirect, the media type, and in words what went wrong, if
# anything did
Hop = collections.namedtuple("Hop", "url status location ctype error")


class Answer:
    """What one address answered: EVERY hop of the chain, in order, and the
    body of the last one, as much of it as was asked for."""

    def __init__(self, hops, body=b""):
        self.hops = hops
        self.body = body

    @property
    def last(self):
        return self.hops[-1]

    @property
    def redirects(self):
        return len(self.hops) - 1


class _NoFollow(urllib.request.HTTPRedirectHandler):
    """urllib's opener without its following: a 3xx is handed back as it is,
    to be followed -- or judged -- here, by hand."""

    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoFollow)


def _ctype(headers):
    return (headers.get("Content-Type") or "").split(";")[0].strip().lower()


def _why(error, timeout):
    """A failed request, in a few words."""
    reason = getattr(error, "reason", error)
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return "no answer within %g s" % timeout
    if isinstance(reason, socket.gaierror):
        return "the name does not resolve"
    if isinstance(reason, ConnectionRefusedError):
        return "connection refused"
    if isinstance(reason, ssl.SSLError):
        return "TLS: %s" % reason
    return "%s: %s" % (type(reason).__name__, reason) if str(reason) else type(reason).__name__


def _once(url, keep=0, agent=None, timeout=TIMEOUT):
    """ONE request, followed nowhere -> (the Hop, as much of the body as KEEP
    bytes).  Never raises for the network's sake: a failure is a hop with
    nothing but its reason."""
    try:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return Hop(url, None, None, "", "not an http or https address"), b""
        req = urllib.request.Request(url, headers={"User-Agent": agent or "Parseh", "Accept": "*/*"})
        with _OPENER.open(req, timeout=timeout) as r:
            return Hop(url, r.status, None, _ctype(r.headers), None), (r.read(keep) if keep else b"")
    except urllib.error.HTTPError as e:           # every answer that is not a 2xx, a redirect included
        hop = Hop(url, e.code, e.headers.get("Location") if e.code in REDIRECTS else None, _ctype(e.headers), None)
        e.close()
        return hop, b""
    except (OSError, http.client.HTTPException, ValueError) as e:
        return Hop(url, None, None, "", _why(e, timeout)), b""


def fetch(url, keep=0, agent=None, timeout=TIMEOUT, once=_once):
    """URL -> its Answer: the redirects are followed here, by hand, at most
    HOP_LIMIT of them, and every hop is kept so that the chain can be printed
    and judged.  KEEP is how many bytes of the last body to read (0: none).
    A chain that loops, has no Location to follow or does not end is a last
    hop that says so.  Nothing is retried: a failure is the answer."""
    hops, seen, body = [], set(), b""
    for _ in range(HOP_LIMIT + 1):
        hop, body = once(url, keep, agent, timeout)
        hops.append(hop)
        seen.add(url)
        if hop.status not in REDIRECTS:
            return Answer(hops, body)
        if not hop.location:
            hops[-1] = hop._replace(error="a redirect with no Location")
            return Answer(hops)
        url = urllib.parse.urljoin(url, hop.location)
        if url in seen:
            hops[-1] = hop._replace(error="a redirect loop: %s was asked already" % url)
            return Answer(hops)
    hops[-1] = hops[-1]._replace(error="more than %d redirects" % HOP_LIMIT)
    return Answer(hops)


# -------------------------------------------------- judging: pure, over an Answer
def _end(ans):
    """Why a chain does not end in 200, in words; [] when it does."""
    last = ans.last
    if last.status is None:
        return ["no answer: %s" % last.error]
    if last.error:
        return [last.error]
    if last.status != 200:
        return ["answers %d%s, not 200" % (last.status, " at %s" % last.url if ans.redirects else "")]
    return []


def _sent_on(ans):
    return "it was sent on (%d redirect%s)" % (ans.redirects, "" if ans.redirects == 1 else "s")


def _bare(netloc):
    netloc = netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _allowed_step(a, b):
    """May the guide's address send a request from A to B?  Only by what
    GitHub itself does: http to https, www to the bare domain, and /guide to
    /guide/ -- any of the three, or all, and nothing else."""
    pa, pb = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    host = pa.netloc.lower()
    return (a != b
            and pb.scheme in {pa.scheme, "https" if pa.scheme == "http" else pa.scheme}
            and pb.netloc.lower() in {host, _bare(host)}
            and pb.path in {pa.path, pa.path if pa.path.endswith("/") else pa.path + "/"}
            and pb.query == pa.query)


def _tag_name(ans):
    """The tag_name of a release's JSON, or None."""
    try:
        data = json.loads(ans.body.decode("utf-8"))
    except ValueError:                                 # not JSON, not even text
        return None
    tag = data.get("tag_name") if isinstance(data, dict) else None
    return tag if isinstance(tag, str) and tag else None


def _base_version(tag):
    """A tag's version: a rehearsal's is its version's (lib/version.py's rule)."""
    try:
        return _version().base(tag)
    except (ValueError, Refused):
        return tag


def _has_bar(text, website):
    """Does the page carry the published guide's bar -- a link to the site, in
    the first part of its body?"""
    start = max(text.find("<body"), 0)
    return re.search(r"<a\b[^>]*\bhref\s*=\s*[\"']%s[\"']" % re.escape(website),
                     text[start:start + BAR_WITHIN]) is not None


def _names(text, version):
    return re.search(r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % re.escape(version), text) is not None


class Result:
    """One address, what answered, and the verdict: PROBLEMS (empty: it is as
    it should be), NOTES (facts worth a line) and whether it is only
    REPORTED, which never fails."""

    def __init__(self, section, label, url, answer=None, problems=(), notes=(), report=False):
        self.section, self.label, self.url, self.answer, self.report = section, label, url, answer, report
        self.notes = list(notes) + (list(problems) if report else [])
        self.problems = [] if report else list(problems)

    @property
    def failed(self):
        return bool(self.problems)


def _check_feed(ask, project, expect):
    ans = ask(project.FEED, FEED_KEEP)
    problems, notes = _end(ans), []
    if ans.redirects:
        problems.append("the update road leans on a redirect: the feed must answer where it is written, "
                        "and %s" % _sent_on(ans))
    tag = _tag_name(ans) if ans.last.status == 200 else None
    if ans.last.status == 200:
        if tag is None:
            problems.append("the answer is not a release: it has no tag_name")
        else:
            notes.append("tag_name %s" % tag)
    if expect and tag and tag != expect:
        problems.append("tag_name is %s, not %s" % (tag, expect))
    return ans, problems, notes


def _check_latest(ask, project, expect):
    ans = ask(project.LATEST_URL)
    problems = _end(ans)
    if (expect and ans.last.status == 200
            and not urllib.parse.urlsplit(ans.last.url).path.endswith("/releases/tag/" + expect)):
        problems.append("the latest release is not %s: it ends at %s" % (expect, ans.last.url))
    return ans, problems, []


def _check_site(ask, project):
    ans = ask(project.WEBSITE_URL)
    problems = _end(ans)
    if ans.redirects:
        problems.append("the site's own address must answer 200 itself, and %s" % _sent_on(ans))
    return ans, problems, []


def _check_guide(ask, project, url):
    """The guide's address must END at project.SITE with 200, by nothing but
    GitHub's own hops, and never leave the domain."""
    ans = ask(url)
    domain = _bare(urllib.parse.urlsplit(project.SITE).netloc)
    problems = []
    for a, b in zip(ans.hops, ans.hops[1:]):
        if _bare(urllib.parse.urlsplit(b.url).netloc) != domain:
            problems.append("it leaves %s for %s: %s -> %s" % (domain, urllib.parse.urlsplit(b.url).netloc,
                                                              a.url, b.url))
        elif not _allowed_step(a.url, b.url):
            problems.append("a hop it may not make: %s -> %s (only http to https, www to the bare "
                            "domain and /guide to /guide/ are GitHub's own)" % (a.url, b.url))
    if ans.last.status == 200 and urllib.parse.urldefrag(ans.last.url)[0] != project.SITE:
        problems.append("it ends at %s, not at %s" % (ans.last.url, project.SITE))
    return ans, problems + _end(ans), []


def _variants(project):
    """The guide as a person may type it, when it is on an https domain of its own."""
    site = urllib.parse.urlsplit(project.SITE)
    if site.scheme != "https" or ":" in site.netloc or not project.GUIDE_URL.startswith("https://"):
        return []
    return [("guide typed with http", "http://" + project.GUIDE_URL[len("https://"):]),
            ("guide typed with www", "https://www." + project.SITE[len("https://"):])]


def _check_deep(ask, project, expect):
    """A page deep in the guide: 200 at its own address, the bar in it, and --
    with a tag -- the release's version, which says the guide published is the
    one of that release."""
    ans = ask(project.SITE + DEEP_LINK, PAGE_KEEP)
    problems, notes = _end(ans), []
    if ans.redirects:
        problems.append("a deep link must answer 200 at its own address, and %s" % _sent_on(ans))
    elif ans.last.status == 200:
        text = ans.body.decode("utf-8", "replace")
        if _has_bar(text, project.WEBSITE_URL):
            notes.append("the bar is there: a link to %s near the top of the page" % project.WEBSITE_URL)
        elif expect:
            problems.append("no bar: there is no link to %s in the first part of the page" % project.WEBSITE_URL)
        else:
            notes.append("no bar (a failure only when --expect is given)")
        if expect:
            version = _base_version(expect)
            if _names(text, version):
                notes.append("the page names %s" % version)
            else:
                problems.append("the page does not name %s: the guide published is older than the release"
                                % version)
    return ans, problems, notes


def _check_icon(ask, project, name, side):
    """An icon is fetched by a MACHINE (Chrome's WebAPK server): 200 image/png
    as written, no redirect at all, and the PNG it says it is."""
    ans = ask(project.ICONS_URL + name, 64)
    problems, notes = [], ["redirects: %d" % ans.redirects]
    if ans.redirects:
        problems.append("a machine fetches this: no redirect may stand before it, and %s" % _sent_on(ans))
    problems += _end(ans)
    if ans.last.status == 200:
        if ans.last.ctype != "image/png":
            problems.append("it is %s, not image/png" % (ans.last.ctype or "of no type"))
        if not ans.body.startswith(PNG_SIGNATURE) or len(ans.body) < 24:
            problems.append("the bytes are not those of a PNG")
        else:
            wide, high = struct.unpack(">II", ans.body[16:24])
            if (wide, high) == (side, side):
                notes.append("%dx%d" % (wide, high))
            else:
                problems.append("it is %dx%d, not %dx%d" % (wide, high, side, side))
    return ans, problems, notes


def _addresses_in(text, bases):
    """The addresses of the project written in a text: those that start with
    one of BASES and go on as a path, an anchor or a query -> a list of
    addresses, anchors cut off.  A pattern is no address (<version>, ${TAG},
    ..., an ellipsis), and nor is another place's that quotes one."""
    found = []
    for base in bases:
        for m in re.finditer(r"""(?<![A-Za-z0-9/_.-])%s[^\s<>"'`()\[\]{}|\\^]*""" % re.escape(base), text):
            raw = m.group(0)
            if raw[len(base):len(base) + 1] not in ("", "/", "#", "?"):
                continue                                  # a longer name: <repository>-fork
            token = raw.rstrip(".,;:!?*")                 # a sentence's or an emphasis's end
            if (text[m.end():m.end() + 1] in ("<", "{") or "$" in token or "*" in token
                    or raw.rstrip("*").endswith("...") or not token.isascii()):
                continue
            address = token.split("#", 1)[0].rstrip(".,;:!?*")
            if address and address not in found:
                found.append(address)
    return found


def link_files(root):
    """The files whose addresses are held to the live check: README.md and the
    other documents at the top, docs/, and the guide's sources (its pages, its
    README and its hand-written front page) -- never the compiled guide."""
    found = [n for n in sorted(os.listdir(root))
             if n.endswith((".md", ".html")) and os.path.isfile(os.path.join(root, n))]
    for base in ("docs", "html-guide/markdown"):
        for folder, dirs, names in os.walk(os.path.join(root, base)):
            dirs.sort()
            found += [os.path.relpath(os.path.join(folder, n), root).replace(os.sep, "/")
                      for n in sorted(names) if n.endswith(LINK_TEXT)]
    found += [n for n in ("html-guide/README.md", "html-guide/index.html")
              if os.path.isfile(os.path.join(root, n))]
    return found


def scan_links(root, project):
    """{address: [the files that write it]}, by address: every address based
    on the repository or on the domain (the site and the guide under it).

    Two kinds are left out, because a document names them without promising a
    page: the icons' FOLDER (it has no page of its own; its files are asked
    one by one) and the addresses that are only reported (Parseh's own Pages
    path is expected to answer 404)."""
    bases = (project.GITHUB_URL, project.WEBSITE_URL.rstrip("/"))
    no_page = {project.ICONS_URL.rstrip("/")} | {a.rstrip("/") for _, a, _ in report_addresses(project)}
    where = {}
    for rel in link_files(root):
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
            for address in _addresses_in(f.read(), bases):
                if address.rstrip("/") not in no_page:
                    where.setdefault(address, []).append(rel)
    return dict(sorted(where.items()))


def _check_link(ask, address, files):
    ans = ask(address)
    named = ", ".join(files[:3]) + (" and %d more" % (len(files) - 3) if len(files) > 3 else "")
    return ans, _end(ans), ["written in %s" % named]


def report_addresses(project):
    """What is REPORTED and never judged: [(label, address, what is expected)]."""
    pages_host = project.SITE_REPO.split("/", 1)[1]        # the organisation site's own Pages address
    guide_path = project.GUIDE_REPO.split("/", 1)[1]
    return [("default Pages address", "https://%s/%s/" % (pages_host, guide_path),
             "a redirect to the domain (%s)" % project.SITE),
            ("Parseh's Pages path", project.WEBSITE_URL + project.NAME + "/",
             "404 once Pages is switched off in %s" % project.NAME)]


def old_addresses(project):
    """The OLD places, for --old: [(label, address, what is expected, read the tag)]."""
    name = project.NAME
    return [("old repository", "https://github.com/%s/%s" % (OLD_ACCOUNT, name),
             "a redirect to the new repository, ending in 200 at %s" % project.GITHUB_URL),
            ("old feed", "https://api.github.com/repos/%s/%s/releases/latest" % (OLD_ACCOUNT, name),
             "a 301 from the API to .../repositories/<id>/releases/latest, then 200", True),
            ("old guide address", "https://%s.github.io/%s/" % (OLD_ACCOUNT.lower(), name),
             "404 (GitHub does not redirect Pages: the old guide address is dead)")]


def _asker(fetcher, agent, pause):
    """ask(url, keep) -> Answer: each address is asked once (asked again with
    a longer KEEP only if more of its body is wanted), PAUSE seconds after the
    one before."""
    memo, state = {}, {"asked": False}

    def ask(url, keep=0):
        known = memo.get(url)
        if known and known[0] >= keep:
            return known[1]
        if pause and state["asked"]:
            time.sleep(pause)
        state["asked"] = True
        memo[url] = (keep, fetcher(url, keep=keep, agent=agent))
        return memo[url][1]
    return ask


def live_checks(root, expect, old, fetcher, project, agent, pause=0.0, reports=None, olds=None):
    """Ask every address Parseh names -> [Result], in the order they are shown.
    FETCHER(url, keep=, agent=) -> Answer is injected: the judging above is
    pure, and a test gives it a table of answers."""
    expect = _tag(expect) if expect else None
    ask = _asker(fetcher, agent, pause)
    out = []

    def add(section, label, url, check, report=False):
        try:
            ans, problems, notes = check()
        except Exception as e:      # one broken check must not stop the others: it is a failure, said
            ans, problems, notes = None, ["the check itself failed: %s: %s" % (type(e).__name__, e)], []
        out.append(Result(section, label, url, ans, problems, notes, report))

    road = "The update road"
    add(road, "feed", project.FEED, lambda: _check_feed(ask, project, expect))
    add(road, "latest", project.LATEST_URL, lambda: _check_latest(ask, project, expect))
    site = "The site and the guide"
    add(site, "site", project.WEBSITE_URL, lambda: _check_site(ask, project))
    add(site, "guide", project.GUIDE_URL, lambda: _check_guide(ask, project, project.GUIDE_URL))
    add(site, "guide/", project.SITE, lambda: _check_guide(ask, project, project.SITE))
    for label, url in _variants(project):
        add(site, label, url, lambda url=url: _check_guide(ask, project, url))
    add(site, "deep link", project.SITE + DEEP_LINK, lambda: _check_deep(ask, project, expect))
    icons = "The phone app's icons (a machine fetches them: no redirect at all)"
    for name, side in ICON_FILES.items():
        add(icons, "icon " + name, project.ICONS_URL + name,
            lambda name=name, side=side: _check_icon(ask, project, name, side))
    where = scan_links(root, project)
    carriers = len({f for files in where.values() for f in files})
    docs = "Addresses written in the documents (%d, from %d file%s)" % (
        len(where), carriers, "" if carriers == 1 else "s")
    for address, files in where.items():
        add(docs, "link", address, lambda address=address, files=files: _check_link(ask, address, files))

    def report(section, entries):
        for label, url, expected, *more in entries:
            def look(url=url, expected=expected, more=more):
                ans = ask(url, FEED_KEEP if more and more[0] else 0)
                tag = _tag_name(ans) if more and more[0] and ans.last.status == 200 else None
                return ans, [], ["expected: %s" % expected] + (["tag_name %s" % tag] if tag else [])
            add(section, label, url, look, report=True)
    report("Reported, never failing", report_addresses(project) if reports is None else reports)
    if old:
        report("The old addresses (--old), reported, never failing",
               old_addresses(project) if olds is None else olds)
    return out


def _chain_lines(ans):
    """The chain, a line a hop: the status and where it sends, or what the last one is."""
    if ans is None:
        return []
    lines = []
    for hop in ans.hops:
        if hop.status is None:
            lines.append("no answer: %s" % hop.error)
        elif hop.status in REDIRECTS and hop.location:
            lines.append("%d -> %s" % (hop.status, urllib.parse.urljoin(hop.url, hop.location))
                         + (" (%s)" % hop.error if hop.error else ""))
        else:
            lines.append(("%d %s" % (hop.status, hop.ctype)).strip() + (" (%s)" % hop.error if hop.error else ""))
    end = ans.last
    if end.status is not None and end.status not in REDIRECTS:
        lines[-1] += ", no redirect" if not ans.redirects else ", %d redirect%s" % (
            ans.redirects, "" if ans.redirects == 1 else "s")
    return lines


def show(results, say=print):
    """The results as lines: a heading for each section, a line for each
    address (ok / FAIL / info), its chain, its facts, and what is wrong."""
    section = None
    for r in results:
        if r.section != section:
            section = r.section
            say("")
            say(section + ":")
        say("  %-5s %-30s %s" % ("info" if r.report else "FAIL" if r.failed else "ok", r.label, r.url))
        for line in _chain_lines(r.answer):
            say("        " + line)
        for note in r.notes:
            say("        - " + note)
        for problem in r.problems:
            say("        ! " + problem)


def _project():
    """lib/project.py -- where Parseh lives, every address it names -> the
    module.  Read here and nowhere else in this file."""
    if LIB not in sys.path:
        sys.path.insert(0, LIB)
    import project
    return project


def _own_version(root):
    """The version of this checkout, for the User-Agent."""
    text = read_file(VERSION_FILE, root=root)
    return text.strip() if text and text.strip() else "unknown"


def _links_tag(expect):
    """--expect's tag: a version's own, never a rehearsal's (GitHub's "latest"
    never answers with one) -> the tag, or None; Refused otherwise."""
    if not expect:
        return None
    tag = _tag(expect)
    if prerelease(tag) == "true":
        raise Refused("--expect takes a version's own tag: GitHub's latest release is never a "
                      "rehearsal's (%s)" % tag)
    return tag


def links(root=ROOT, expect=None, old=False, fetcher=None, project=None, agent=None, say=print,
          pause=0.0, reports=None, olds=None):
    """`release.py links`: ask every address Parseh names, print what answers,
    and say how many are wrong -> the exit code, 0 when none is."""
    project = project or _project()
    agent = agent or project.agent(_own_version(root))
    say("Asking every address Parseh names, live, as %s." % agent)
    say("Redirects are followed by hand (at most %d), %d s for each request, nothing is retried."
        % (HOP_LIMIT, TIMEOUT))
    if expect:
        say("Expecting the release %s." % expect)
    results = live_checks(root, expect, old, fetcher or fetch, project, agent, pause, reports, olds)
    show(results, say)
    bad = [r for r in results if r.failed]
    reported = sum(1 for r in results if r.report)
    say("")
    say("%d addresses asked, %d only reported, %d failed." % (len(results) - reported, reported, len(bad)))
    for r in bad:
        say("FAIL  %-30s %s: %s" % (r.label, r.url, r.problems[0]))
    return 1 if bad else 0


# ------------------------------------------------------------------ the command
def main(argv=None):
    ap = argparse.ArgumentParser(prog="release.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="build dist/parseh-<version>.zip from a commit")
    b.add_argument("--ref", default="HEAD", help="the commit, branch or tag to build (HEAD)")
    b.add_argument("--tag", default=None,
                   help="name the build by this tag: VERSION's own, or a rehearsal of it "
                        "(a0.3.2-rc1); VERSION's when not given")
    b.add_argument("--out", default=None, help="the folder to write into (dist/ in the checkout)")
    n = sub.add_parser("notes", help="print a version's section of CHANGELOG.md")
    n.add_argument("version")
    n.add_argument("--ref", default=None, help="read CHANGELOG.md at this commit, not in the working tree")
    c = sub.add_parser("check", help="refuse unless the tag, VERSION, CHANGELOG.md and What's new agree")
    c.add_argument("tag")
    c.add_argument("--ref", default=None, help="read the files at this commit, not in the working tree")
    g = sub.add_parser("guide", help="refuse unless the compiled guide is in step with its sources")
    g.add_argument("--ref", default=None, help="ask of this commit, not of the working tree")
    p = sub.add_parser("prerelease", help="print true for a rehearsal's tag (-rcN), false for a version's")
    p.add_argument("tag")
    m = sub.add_parser("compare", help="whether two builds (zips or manifests) ship the same files")
    m.add_argument("a")
    m.add_argument("b")
    k = sub.add_parser("links", help="ask, live, what every address Parseh names answers (by hand)")
    k.add_argument("--expect", metavar="TAG", default=None,
                   help="the release the feed, the latest-release page and the published guide must name "
                        "(a version's own tag, never a rehearsal's)")
    k.add_argument("--old", action="store_true",
                   help="also report what the OLD addresses answer now (the transfer's redirects)")
    args = ap.parse_args(argv)
    try:
        if args.command == "build":
            build(args.ref, args.out, tag=args.tag)
        elif args.command == "notes":
            sys.stdout.write(notes(_tag(args.version), args.ref))
        elif args.command == "check":
            v = check(args.tag, args.ref)
            tag = _tag(args.tag)
            if tag != v:
                print("Agreed: %s rehearses %s, which %s, %s's newest section and the guide's "
                      "What's new all say; a rehearsal may come before the day is written."
                      % (tag, v, VERSION_FILE, CHANGELOG))
            else:
                print("Agreed: the tag, %s, %s's newest section and the guide's What's new all "
                      "say %s, released on the same day." % (VERSION_FILE, CHANGELOG, v))
        elif args.command == "guide":
            info = guide(args.ref)
            print("In step: the compiled guide (%s pages) is what its sources compile to."
                  % info.get("pages", "?"))
        elif args.command == "prerelease":
            print(prerelease(args.tag))
        elif args.command == "links":
            return links(ROOT, _links_tag(args.expect), args.old, pause=PAUSE)
        else:
            agree, said = compare(args.a, args.b)
            print("\n".join(said if agree else ["They DISAGREE:"] + ["  " + s for s in said]))
            return 0 if agree else 1
    except Refused as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
