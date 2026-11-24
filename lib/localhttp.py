# SPDX-License-Identifier: GPL-3.0-or-later
"""This computer on plain http://localhost (a0.7.0, W5).

WHY.  Parseh used to answer this computer as it answers a phone: over TLS,
with a certificate signed by an authority it made itself, so every browser
on the computer warned once.  A browser treats `http://localhost` and
`http://127.0.0.1` as secure contexts -- the clipboard, screen and tab
capture, a service worker and an installed app all work there -- so the
computer does not need TLS at all, and without it there is no warning.
Every other device still gets TLS: its connection crosses a network.

ONE PORT, TWO WAYS IN.  serve.py's Server.finish_request already peeks at
each connection's first byte (a TLS ClientHello starts with 0x16).  A plain
connection is now SERVED when it comes from loopback, and from anywhere
else is answered with nothing but a redirect to the https address -- no page,
no data, no route -- and closed.  The other choice, a second plain listener
on 127.0.0.1, was not taken:

  * it would need a second port: 127.0.0.1:7654 cannot be bound beside
    0.0.0.0:7654 on Linux without SO_REUSEPORT, and Windows lets the two
    overlap in ways that differ by version -- so the computer's address and
    a phone's would differ by more than the scheme;
  * main's loop is the only place that binds, closes and re-binds (Settings
    can move the port), and a second socket would have to follow every move;
  * the updater's progress page (lib/updater.py) holds the same port while
    the server is down, and would have to hold two.

One port keeps one address for everybody (`localhost:<port>` here, the
same port elsewhere) and one socket to bind.

DNS REBINDING.  TLS used to shut a door this opens: a page on another site
whose name is made to point at 127.0.0.1 would talk to Parseh as its own
origin.  Over TLS the certificate never matches such a name; over plain
http nothing would stop it.  So a plain request from loopback must name
this computer in its Host -- `localhost`, `127.x.y.z` or `[::1]` -- or it is
refused (`host_is_loopback`).

THE MOVE OF ORIGIN.  `https://localhost:7654` and `http://localhost:7654`
are two origins: what the browser kept for the old one the new one cannot
see.  What it kept, measured over the pages (2026-11-24):

  * localStorage -- the settings that follow a person are on the server
    already (lib/prefs.py), but much is the device's alone: the reader's
    unsaved timing edits (`bk_edits:<page>`), every reading place before the
    toolbox learnt it, the levels open, the text size, the player's widths,
    the exercise decks' choices, the studio's own keys.  ALL of it is
    carried, once, below;
  * IndexedDB -- none: no page of Parseh opens one;
  * the service worker's caches -- copies of what the server has (the
    phone's kept books, the app shell); on the computer they are never the
    only copy, so they are not carried, and are emptied on the old origin
    once the carry has gone through;
  * an installed app -- it opens the old address, and an app cannot be moved
    by a page.  The person is told, once, to install it again.

THE CARRY.  A NAVIGATION that arrives over TLS from this computer, naming
this computer (`localhost` or `127.x`), is answered with a small page on the
OLD origin (`handover_page`).  It reads its localStorage and posts it to the
server (`/__move`, same-origin), which holds it for a few minutes under a
random token; then it goes to `http://localhost:<port>/__move?t=<token>`,
where the NEW origin's page (`arrive_page`) takes it back (once) and writes
each key the new origin does not have yet, and goes on to the address that
was asked for.  The old origin is given a cookie saying it has moved, so its
later navigations -- bookmarks, an old tab, the installed app -- are simply
redirected.  Scripts on the old origin (a tab left open, its worker) are
still answered as before, until they are navigated.
"""

import ipaddress
import json
import os
import re
import secrets
import threading
import time

NAME = "Parseh"
MOVE = "/__move"                      # the old origin posts here; the new one arrives here
MOVE_TAKE = "/__move/take"            # the new origin takes the record, once
HOLD = 600                            # seconds a carried record waits to be taken
MOVED_COOKIE = "parseh_moved_%d"      # per port: a cookie does not know the port

_HELD = {}
_LOCK = threading.Lock()


def is_loopback(ip):
    """Is this peer address this computer?"""
    try:
        a = ipaddress.ip_address((ip or "").split("%", 1)[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_loopback


def host_name(host):
    """The name in a Host header, without its port and brackets, lower case."""
    host = (host or "").strip().lower()
    if host.startswith("["):
        return host[1:].split("]", 1)[0]
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.rstrip(".")


def host_is_loopback(host):
    """Does a Host header name this computer?  (DNS rebinding, above.)"""
    name = host_name(host)
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def home(port):
    """This computer's address for Parseh: the one every launcher, script,
    shortcut and printed line names."""
    return "http://localhost:%d/" % int(port)


def address_for(scheme, host, port):
    """The address a person types for this host: this computer on plain
    http://localhost, anything else as the server speaks."""
    if host in ("localhost", "::1") or str(host).startswith("127."):
        return home(port)
    return "%s://%s:%d/" % (scheme, host, int(port))


# ------------------------------------------------------------ the carry
def put(record):
    """Hold what the old origin handed over; -> its token."""
    now = time.time()
    token = secrets.token_hex(16)
    with _LOCK:
        for t in [t for t, (at, _) in _HELD.items() if now - at > HOLD]:
            del _HELD[t]
        if len(_HELD) > 50:            # nothing but this computer can post here
            _HELD.clear()
        _HELD[token] = (now, record)
    return token


def take(token):
    """The record a token names, once; None when there is none (any more)."""
    with _LOCK:
        got = _HELD.pop(token or "", None)
    if not got or time.time() - got[0] > HOLD:
        return None
    return got[1]


def clean_record(obj):
    """What the old origin posted, kept to the shape the new one writes."""
    if not isinstance(obj, dict):
        return None
    ls = obj.get("ls")
    out = {"ls": {}, "app": bool(obj.get("app")), "worker": bool(obj.get("worker"))}
    if isinstance(ls, dict):
        for k, v in ls.items():
            if isinstance(k, str) and isinstance(v, str):
                out["ls"][k] = v
    return out


def safe_next(target):
    """Where to go after the carry: a path on this server, never elsewhere."""
    target = target or "/"
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/"
    if target.split("?", 1)[0] in (MOVE, MOVE_TAKE):
        return "/"
    return target


def moved_cookie(port):
    return ("%s=1; Path=/; Max-Age=%d; SameSite=Lax; Secure"
            % (MOVED_COOKIE % int(port), 10 * 365 * 86400))


def _page(title, body, script):
    return ("<!doctype html><html lang=en><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=color-scheme content='light dark'>"
            "<title>%s</title><style>body{font:17px/1.5 system-ui,sans-serif;"
            "max-width:36rem;margin:3rem auto;padding:0 1.2rem}"
            "p.s{opacity:.75}code{font-size:.95em}button{font:inherit;padding:.4em 1em}"
            "</style><body>%s<script>%s</script></body></html>" % (title, body, script))


def handover_page(port, target):
    """The page the OLD origin (https://localhost) is answered with: it hands
    what this browser kept for it to the new one, then goes there."""
    nxt = json.dumps(safe_next(target))
    to = json.dumps(home(port).rstrip("/"))
    script = """
(async function () {
  var next = %s, to = %s, rec = {ls: {}, app: false, worker: false};
  try { rec.app = matchMedia('(display-mode: standalone)').matches
                  || matchMedia('(display-mode: window-controls-overlay)').matches; } catch (e) {}
  try {
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      rec.ls[k] = localStorage.getItem(k);
    }
  } catch (e) {}
  var regs = [];
  try { regs = await navigator.serviceWorker.getRegistrations(); } catch (e) {}
  rec.worker = regs.length > 0;
  var token = '';
  try {
    var r = await fetch('%s', {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(rec)});
    token = (await r.json()).token || '';
  } catch (e) {}
  if (token) {
    // the old origin's copies: the server has every one of them
    for (var j = 0; j < regs.length; j++) { try { await regs[j].unregister(); } catch (e) {} }
    try { var ks = await caches.keys(); for (var c = 0; c < ks.length; c++) await caches.delete(ks[c]); }
    catch (e) {}
  }
  location.replace(to + '%s?t=' + encodeURIComponent(token) + '&next=' + encodeURIComponent(next));
})();
""" % (nxt, to, MOVE, MOVE)
    body = ("<h1>%s has moved on this computer</h1><p>It now opens at "
            "<a id=to href='%s'>%s</a>, with no warning from the browser. "
            "What this browser kept for the old address is being carried there.</p>"
            % (NAME, home(port), home(port)))
    return _page("%s has moved" % NAME, body, script)


def arrive_page(port):
    """The page the NEW origin (http://localhost) is answered with at /__move:
    it takes what was carried and writes what it does not have yet."""
    script = """
(async function () {
  var q = new URLSearchParams(location.search), t = q.get('t') || '', next = q.get('next') || '/';
  if (!/^\\/(?!\\/)/.test(next) || next.indexOf('\\\\') >= 0) next = '/';
  var rec = null, n = 0;
  if (t) {
    try { rec = await (await fetch('%s?t=' + encodeURIComponent(t), {cache: 'no-store'})).json(); }
    catch (e) {}
  }
  if (rec && rec.ls) {
    for (var k in rec.ls) {
      try { if (localStorage.getItem(k) === null) { localStorage.setItem(k, rec.ls[k]); n++; } }
      catch (e) {}
    }
  }
  try { localStorage.setItem('parseh_moved_from', String(Date.now())); } catch (e) {}
  document.getElementById('carried').textContent = String(n);
  if (rec && (rec.app || rec.worker)) {
    document.getElementById(rec.app ? 'app' : 'maybe').hidden = false;
    document.getElementById('go').hidden = false;
    document.getElementById('go').href = next;
    return;
  }
  location.replace(next);
})();
""" % MOVE_TAKE
    here = home(port)
    body = ("<h1>%s now opens at <code>%s</code></h1>"
            "<p>The browser no longer warns about it on this computer. "
            "<span id=carried>0</span> things this browser kept for the old address were carried "
            "over.</p>"
            "<p id=app hidden><b>One thing to do:</b> this window is the app you installed from "
            "the old address, and it will keep opening that one. Install %s again from "
            "<code>%s</code> (the install button in the browser's address bar, or its menu), "
            "then remove the old app.</p>"
            "<p id=maybe hidden>If you installed %s as an app on this computer, install it "
            "again from <code>%s</code> (the install button in the browser's address bar, or its "
            "menu) and remove the old one: it still opens the old address.</p>"
            "<p><a id=go hidden href='/'>Go on</a></p>"
            % (NAME, here, NAME, here, NAME, here))
    return _page("%s has moved" % NAME, body, script)
