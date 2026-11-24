#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Only Parseh's own pages may change anything in it (TO-DO §3.1).

    why = crosssite.refusal(handler.headers)    # None, or the refusal in words
    if method not in crosssite.SAFE and why:    # asked before the body is read
        ...answer 403 {"ok": false, "error": why} and close the connection

THE HOLE THIS CLOSES.  Parseh answers on this computer's own address, and
the browser that shows its pages shows everybody else's too.  A page on any
site, open in another tab, can make that browser send a request to
http://localhost:7654/ -- a form, or a fetch() of the kind a browser sends
without asking first (text/plain, a form's body) -- and the browser attaches
nothing that would tell a server which has no login it was not Parseh's
own page.  Every route that writes was open to that: stopping the server,
deleting a book, emptying the clip tray, replacing Parseh itself.  The
network door (lib/network.py) does not help here, because the request comes
from this computer, the one place the door is always open.

WHAT THE BROWSER SAYS, AND WHICH OF IT IS BELIEVED.  Every browser marks
each request with `Sec-Fetch-Site` (Chrome since 2019, Firefox since 2021,
Safari since 2023), saying how the page that sent it stands to the address
it goes to, and a page's script can neither set nor change it:

    same-origin   the same scheme, name and port: Parseh's own page       yes
    none          the person typed the address or used a bookmark         yes
    same-site     the same name on ANOTHER PORT -- another program on
                  localhost is same-site to Parseh -- or a sibling name   no
    cross-site    any other site at all                                   no

A browser too old for that header still sends `Origin` with every request
that writes, and it is compared with the address the request was sent to
(`Host`): the same name and port (a missing port being the scheme's own),
or refused -- `Origin: null` included, which is a page with no address of
its own (a file opened from the disk, a sandboxed frame).  `Origin` is read
ONLY when `Sec-Fetch-Site` is absent: a page of Parseh's own that asks for
no referrer sends `Origin: null` on its own writes, and the browser has
already said, in the header it alone writes, that the request is same-origin.

A REQUEST WITH NEITHER HEADER IS LET THROUGH.  That is every caller that is
not a web page: serve.sh's `stop` (curl), the Windows launcher's stop
(lib/launcher.py, urllib), the test suites' own clients (http.client, Deno's
fetch, Playwright's API requests).  None of them is a browser, and none of
them could be made to send a request by a page on another site.

WHO WAS THOUGHT OF, AND IS NOT REFUSED.  Every Parseh page writes with a
relative address -- the reader, the player, the studio, the decks, the card
kit, Settings and its pairing door, the guide's Compile button, the uploads
(a book, a bundle, a backup, the updater's chosen zip) -- so each is
same-origin, on the computer, on a phone and in the installed app alike.
The service worker writes nothing (lib/sw.js lets every non-GET go by) and
its Background Fetch only reads.  A page exported to one HTML file and
opened from the disk never reaches the server: its relative addresses are
file:// ones.  Nothing here reads a request that only reads (GET, HEAD): a
link from another site to a Parseh page still opens it.

WHERE IT IS ASKED: at the top of the one method every writing verb goes
through, before the body is read -- serve.py's Handler._dispatch for the
whole toolbox (the studio, the decks and the video player's routes are
answered there too), and markdown/app/server.py's own Handler._dispatch
when the studio runs alone.  The helper's stand-in server during an update
(lib/updater.py _StatusServer) writes nothing and answers every POST 503.

    python3 -m unittest tests/test_cross_site.py
"""
import urllib.parse

NAME = "Parseh"

# Requests that only read: answered to anybody the network door lets in.
# Every other method writes, including any a later route might answer.
SAFE = ("GET", "HEAD")

# What Sec-Fetch-Site may say for a write to be let through.
OWN = ("same-origin", "none")

DEFAULT_PORT = {"http": 80, "https": 443}


def _host_port(netloc, scheme):
    """("name", port) of a Host header or an Origin's netloc, the port being
    the scheme's own when it is not written; None when it is not one."""
    try:
        parts = urllib.parse.urlsplit("//" + netloc.strip())
        name, port = parts.hostname, parts.port
    except ValueError:
        return None
    if not name:
        return None
    return name.lower().rstrip("."), port or DEFAULT_PORT.get(scheme)


def refusal(headers):
    """Why a request that writes cannot have come from one of Parseh's own
    pages, in words fit to show, or None when it may go on.  `headers` is
    anything with .get() -- a request's headers, or a dict in a test."""
    site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    if site:
        if site in OWN:
            return None
        return ("%s refused this: it came from another site (the browser says "
                "\"%s\"), and only %s's own pages may change anything in it."
                % (NAME, site, NAME))
    origin = (headers.get("Origin") or "").strip()
    if not origin:
        return None                 # not a browser: curl, the launcher, a test
    if origin.lower() == "null":
        return ("%s refused this: it came from a page with no address of its own "
                "(a file opened from the disk, or a sandboxed frame), and only "
                "%s's own pages may change anything in it." % (NAME, NAME))
    try:
        o = urllib.parse.urlsplit(origin)
        scheme = o.scheme.lower()
    except ValueError:
        o, scheme = None, ""
    theirs = _host_port(o.netloc, scheme) if o is not None else None
    ours = _host_port(headers.get("Host") or "", scheme)
    if theirs is None or ours is None or theirs != ours:
        return ("%s refused this: it came from %s, and only %s's own pages may "
                "change anything in it." % (NAME, origin[:200], NAME))
    return None
