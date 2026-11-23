#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The name a download is saved under, in any script (TO-DO §8.20).

    savename.disposition(name, fallback=None)   the Content-Disposition value
    savename.clean(title)                        a title made fit for a file name

A Content-Disposition header is ASCII, so a download named only by
`filename="..."` loses every letter that is not Latin: a studio document
called «گربه‌ها» came down as `doc.pdf`, one called 猫 the same.  RFC 6266
lets a header carry the name twice: `filename="..."`, an ASCII name every
browser understands, and `filename*=UTF-8''...` (RFC 5987, percent-encoded
UTF-8), the real name, which every browser of today prefers when it is there.
So the Persian, Arabic, Hindi, Chinese or Japanese title is what the file is
called, and a browser that reads only the first form still gets a name.

A name that is plain ASCII already goes out as before, `filename="..."` alone.
"""

import re
import unicodedata
import urllib.parse

# what no file system takes in a name, the header's own quote and backslash,
# and the control characters (a newline would end the header)
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]+')
_ASCII_OK = re.compile(r"^[A-Za-z0-9._ ()+,=@-]+$")


def clean(title, limit=80):
    """`title` with what a file name cannot hold turned into hyphens, its
    runs of white space made one space, and at most `limit` characters.
    Letters of every script are kept.  "" when nothing is left."""
    s = unicodedata.normalize("NFC", str(title or ""))
    s = _UNSAFE.sub("-", s)
    s = re.sub(r"\s+", " ", s).strip(" .-")
    return s[:limit].rstrip(" .-")


def _ascii(name):
    """`name` reduced to ASCII: accents folded away (é is e), any other
    letter dropped, runs of what is left over made one hyphen."""
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")


def disposition(name, fallback=None, kind="attachment"):
    """The Content-Disposition value for a download called `name`.

    `fallback` is the ASCII name for a browser that does not read
    `filename*` (the studio's slug, say); without one, `name` reduced to
    ASCII, and when nothing of its stem survives that, "download" with its
    extension."""
    name = clean(name, limit=200) or (fallback or "download")
    if _ASCII_OK.match(name) and not fallback:
        return '%s; filename="%s"' % (kind, name)
    plain = _ascii(fallback or name)
    stem, dot, ext = plain.rpartition(".")
    if not plain or (dot and not stem.strip("-.")):
        ext = name.rpartition(".")[2] if "." in name else ""
        ext = _ascii(ext)
        plain = "download" + ("." + ext if ext else "")
    if plain == name:
        return '%s; filename="%s"' % (kind, plain)
    return ("%s; filename=\"%s\"; filename*=UTF-8''%s"
            % (kind, plain, urllib.parse.quote(name, safe="")))
