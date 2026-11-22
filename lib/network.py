# SPDX-License-Identifier: GPL-3.0-or-later
"""Who may reach this Parseh, and on which port (TO-DO §1.1, §3.3, §3.4, and
the owner's decisions of 2026-09-23).

Parseh is one person's toolbox on one person's computer, and every route in
it can delete a book, overwrite an edition or stop the server.  Until today
it bound every interface and asked nobody who they were: anybody on the same
Wi-Fi could do all three.  What follows is the door, and it is a door with
three positions rather than a lock:

  * **this computer** -- always, and never asked anything.  With both doors
    below shut this is not a rule but a closed socket: the server binds
    127.0.0.1 and there is nothing on the network to knock at.
  * **a VPN** -- Tailscale's own range (and any range or name added to
    `extra`), trusted with no ceremony, because a device is on that network
    only if this person's own account put it there.  On by default.
  * **the Wi-Fi** -- shut on a fresh install.  Opened, a device on it still
    has to be LET IN ONCE, by typing a short code shown on the computer;
    then it is remembered by a token in a long-lived cookie.

Anything else -- a public address, somebody who found the port from outside
-- is refused at the socket, before a byte of HTTP is read.

    config/network.json
    {"port": 7654,
     "vpn": true, "lan": false,
     "extra": ["10.8.0.0/24", "laptop.example.ts.net"],
     "cert": {"cert": "/etc/ssl/mine.pem", "key": "/etc/ssl/mine.key"},
     "devices": {"<token>": {"name": "Android phone · Chrome",
                             "at": 1758531600.0, "seen": 1758531600.0,
                             "ip": "192.168.1.20"}}}

THE FILE IS THIS MACHINE'S.  Like `config/prefs.json` beside it, it is in no
bundle and in no backup and it is gitignored: it says who may reach THIS
computer, which means nothing anywhere else, and the tokens in it are as
good as keys.  It is written whole through a temporary file, so a request
reading it while a save is in flight gets the old file or the new one and
never half of either.

THE PAIRING CODE IS NOT IN IT.  A code lives in this process and for
fifteen minutes; it is printed when the server starts and shown on the
Settings page, where a button makes a fresh one.  A code retires the moment
a device uses it -- it lets ONE device in -- and a run of wrong guesses
retires it too, rather than letting a thousand tries a second wear a
six-character code down.

WHAT THIS MODULE DOES NOT DO.  It never binds, never answers a request and
never speaks HTTP: `serve.py` asks it who is knocking (`may_connect`,
`let_in`) and what to bind (`bind_host`, `port`), and writes the page.  That
is what makes it testable without a server (tests/test_network.py).
"""
import copy
import errno
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
import time

import storeguard

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "config", "network.json")
# the shape of STORE, as a number (lib/version.py FORMATS): RAISE IT when the
# shape changes so that the Parseh before this one would read the file wrong
STORE_FORMAT = 1

# THE PORT.  8765 was Parseh's from the start, and it is also AnkiConnect's
# (TO-DO §2.14): an Anki user with the add-on running could not start Parseh
# at all, and the message said only that the address was in use.  7654 is out
# of that range and out of the way of everything else this toolbox meets; the
# owner chose it on 2026-09-23.  A port below 1024 is refused, not because
# Parseh dislikes it but because binding one asks the operating system for
# administrator rights, which a double-clicked toolbox does not have.
DEFAULT_PORT = 7654
LOWEST_PORT = 1024
ANKICONNECT_PORT = 8765

# A VPN'S OWN ADDRESSES.  Tailscale hands every device an address in
# 100.64.0.0/10 (the carrier-grade NAT range, which is why nothing else on a
# home network uses it) and an IPv6 one under fd7a:115c:a1e0::/48.  A device
# holding one of these got it from this person's own tailnet, so it is
# trusted with no code.  Another VPN puts its own range in `extra`.
VPN_RANGES = ("100.64.0.0/10", "fd7a:115c:a1e0::/48")

# THE WI-FI, and every other private network the computer is on: the three
# private IPv4 ranges, link-local (what a cable between two machines gets
# when there is no DHCP), and their IPv6 counterparts.  A device here is
# "on the same network as the computer" -- which is not the same as "mine".
LAN_RANGES = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
              "fc00::/7", "fe80::/10")

# where(ip) answers one of these four
SELF, VPN, LAN, AWAY = "self", "vpn", "lan", "away"
WHERE_SAID = {SELF: "this computer", VPN: "a VPN", LAN: "the Wi-Fi",
              AWAY: "somewhere else"}

# A name in `extra` is looked up again this often: a VPN that hands out names
# rather than a fixed range (and re-uses them as devices come and go) is then
# followed within five minutes, and a name that stops resolving stops letting
# anybody in within five minutes too.
RESOLVE_EVERY = 300
MAX_EXTRA = 40                  # ranges and names somebody may add, together
MAX_DEVICES = 200               # remembered devices; the oldest go

# THE CODE.  Six characters out of an alphabet with no I, O, 0 or 1 in it --
# a billion of them -- read off a screen and typed into a phone once.  It is
# short because it is typed by hand and long because it is the only thing
# between a stranger on the Wi-Fi and this person's books; what makes the two
# agree is that it lives fifteen minutes and dies at the eighth wrong guess.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LIFE = 15 * 60
CODE_TRIES = 8

MAX_NAME = 60                   # a device names itself; this is all that is kept


class NetworkError(ValueError):
    """A refusal written to be read by whoever pressed the button."""


# --------------------------------------------------------------- the file
def _blank():
    return {"port": DEFAULT_PORT, "vpn": True, "lan": False, "extra": [],
            "cert": {}, "devices": {}}


# THE FILE IS READ ONCE PER CHANGE, not once per request.  Every connection
# asks who is knocking and every request asks whether it has been let in, so
# a page with forty pictures on it would be eighty reads of the same four
# lines; the file is small enough that this hardly matters and often enough
# that it should not be done anyway.  The key is the file's own mtime and
# size, so a save -- which replaces the file -- is picked up at once, by this
# process and by any other.  What is handed out is a copy, because the caller
# that saves edits what it was given.
_CACHE = {"key": None, "doc": None}


def _read():
    try:
        st = os.stat(STORE)
        key = (STORE, st.st_mtime_ns, st.st_size)
    except OSError:
        key = (STORE, None, None)
    if _CACHE["key"] == key and _CACHE["doc"] is not None:
        return copy.deepcopy(_CACHE["doc"])
    doc = _parse()
    _CACHE["key"], _CACHE["doc"] = key, doc
    return copy.deepcopy(doc)


def _parse():
    doc = _blank()
    try:
        with open(STORE, "r", encoding="utf-8") as fh:
            said = json.load(fh)
    except (OSError, ValueError):
        return doc
    if not isinstance(said, dict):
        return doc
    try:
        doc["port"] = int(said.get("port") or DEFAULT_PORT)
    except (TypeError, ValueError):
        pass
    if not LOWEST_PORT <= doc["port"] <= 65535:
        doc["port"] = DEFAULT_PORT
    for k in ("vpn", "lan"):
        if isinstance(said.get(k), bool):
            doc[k] = said[k]
    if isinstance(said.get("extra"), list):
        doc["extra"] = [str(e)[:100] for e in said["extra"] if str(e).strip()][:MAX_EXTRA]
    if isinstance(said.get("cert"), dict):
        cert, key = said["cert"].get("cert"), said["cert"].get("key")
        if cert and key:
            doc["cert"] = {"cert": str(cert), "key": str(key)}
    if isinstance(said.get("devices"), dict):
        for token, rec in said["devices"].items():
            if isinstance(rec, dict) and isinstance(token, str):
                doc["devices"][token] = rec
    return doc


def _write(doc):
    """Written whole, through a temporary file beside it, as lib/prefs.py
    writes its own store: a request asking who may come in while a save is in
    flight reads the old file or the new one, never half of either."""
    # private: the tokens in it are as good as keys, nobody else's business
    # even on a computer with more than one account.  A file there that does
    # not parse is set aside under a dated name first, never written over
    # (lib/storeguard.py, TO-DO §2.29); and every write has a temporary name
    # of its own, fsync'd before it is moved in.
    storeguard.write_json(STORE, doc, ok=lambda d: isinstance(d, dict), private=True,
                          indent=1, sort_keys=True)
    return doc


def settings():
    """Everything, as the Settings page asks for it."""
    return _read()


def port():
    return _read()["port"]


def bind_host(doc=None):
    """The address to bind: a genuinely closed socket when neither door is
    open, and every interface otherwise.

    "This computer only" is not enforced by turning requests away -- it is
    enforced by there being nothing to send a request to.  That is the one
    position of this door that does not depend on a line of Parseh's code
    being right."""
    doc = doc or _read()
    return "0.0.0.0" if (doc["vpn"] or doc["lan"]) else "127.0.0.1"


def own_cert(doc=None):
    """The certificate and key this person told Parseh to use, or None.

    Parseh never writes to either: a certificate of somebody's own -- from
    Tailscale, from Let's Encrypt, from a company's authority -- is theirs to
    renew, and a toolbox that quietly replaced it would be a toolbox that
    broke it."""
    doc = doc or _read()
    cert, key = (doc["cert"].get("cert"), doc["cert"].get("key"))
    return (cert, key) if cert and key else None


# ------------------------------------------------------- where a knock is from
def _net(text):
    """One entry of `extra`, or one of the ranges above, as a network."""
    try:
        return ipaddress.ip_network(text.strip(), strict=False)
    except ValueError:
        return None


_RESOLVED = {}                  # name -> (when, [addresses])
_RESOLVE_LOCK = threading.Lock()


def _addresses_of(name):
    """The addresses a name in `extra` stands for, looked up again every few
    minutes.  A lookup that fails leaves the last answer standing until it in
    turn goes stale: a VPN's DNS is down more often than a VPN is."""
    now = time.time()
    with _RESOLVE_LOCK:
        was = _RESOLVED.get(name)
        if was and now - was[0] < RESOLVE_EVERY:
            return was[1]
    found = []
    try:
        for info in socket.getaddrinfo(name, None):
            ip = info[4][0].split("%", 1)[0]
            if ip not in found:
                found.append(ip)
    except (OSError, UnicodeError):
        found = was[1] if was else []
    with _RESOLVE_LOCK:
        _RESOLVED[name] = (now, found)
    return found


def _clean_ip(ip):
    """The address socketserver hands over, as an address object.

    A machine with IPv6 on reports an IPv4 client as ::ffff:192.168.1.20 --
    the same device, and it must be judged as the IPv4 address it is, or the
    Wi-Fi door would look shut to it and open to nobody."""
    text = str(ip or "").split("%", 1)[0]
    try:
        a = ipaddress.ip_address(text)
    except ValueError:
        return None
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a


def where(ip, doc=None):
    """Which of the four places a knock comes from: SELF, VPN, LAN or AWAY."""
    a = _clean_ip(ip)
    if a is None:
        return AWAY
    if a.is_loopback:
        return SELF
    for r in VPN_RANGES:
        net = _net(r)
        if net and a.version == net.version and a in net:
            return VPN
    doc = doc or _read()
    for entry in doc["extra"]:
        net = _net(entry)
        if net is not None:
            if a.version == net.version and a in net:
                return VPN
            continue
        # not a range: a name, whose addresses are looked up
        for found in _addresses_of(entry):
            if _clean_ip(found) == a:
                return VPN
    for r in LAN_RANGES:
        net = _net(r)
        if net and a.version == net.version and a in net:
            return LAN
    return AWAY


def may_connect(ip, doc=None):
    """Is this address one Parseh will talk to at all?

    Asked once per connection, before any HTTP is read, so that a refusal
    costs a closed socket and nothing else.  It answers the RANGE question
    only -- whether a Wi-Fi device has been let in is a question about a
    cookie, and a cookie arrives in a request, not in a connection."""
    doc = doc or _read()
    place = where(ip, doc)
    if place == SELF:
        return True
    if place == VPN:
        return bool(doc["vpn"])
    if place == LAN:
        return bool(doc["lan"])
    return False


def may_save(ip):
    """Only the computer itself may change these settings.

    A phone may READ the page -- it is useful to see which door is open from
    the device that is knocking at it -- but the door is opened from the side
    it protects.  Were it otherwise, one device that had been let in could
    let the whole Wi-Fi in."""
    return where(ip) == SELF


def needs_code(ip, doc=None):
    """Must this address be let in by hand before it is served?"""
    return where(ip, doc or _read()) == LAN


# ------------------------------------------------------- the devices let in
def _touch(token):
    """A device's `seen`, kept roughly rather than exactly: writing the file
    on every request from every device would be a disk write per picture in a
    book.  Five minutes is close enough to answer "when was this last used"
    on the Settings page.

    Read again from disk before it is written, so that a save made in the
    same second -- the file is written whole -- is never rolled back by a
    timestamp."""
    doc = _read()
    rec = doc["devices"].get(token)
    if rec is None or time.time() - float(rec.get("seen") or 0) <= 300:
        return
    rec["seen"] = time.time()
    try:
        _write(doc)
    except OSError:
        pass                            # a read-only disk must not shut the door


def let_in(token, ip=None, doc=None):
    """Has this device been let in?  `token` is what the cookie carries."""
    token = str(token or "")
    # what a cookie carries is whatever somebody put in it: a token of ours
    # is url-safe base64 and nothing else, and compare_digest refuses a
    # string with anything outside ASCII in it
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", token):
        return False
    doc = doc or _read()
    for known in doc["devices"]:
        # the token is the whole of the secret, so it is compared the way a
        # secret is compared, however small the difference that makes here
        if hmac.compare_digest(known, token):
            _touch(known)
            return True
    return False


def devices(doc=None):
    """What the Settings page lists: the name, when it was let in, when it
    was last seen -- never the token, which is the device's own to keep."""
    doc = doc or _read()
    out = []
    for token, rec in doc["devices"].items():
        out.append({"id": token[:8], "name": rec.get("name") or "a device",
                    "at": rec.get("at") or 0, "seen": rec.get("seen") or 0,
                    "ip": rec.get("ip") or ""})
    out.sort(key=lambda d: -float(d["at"] or 0))
    return out


def remember(name, ip=""):
    """Let a device in for good, and hand back the token it will carry."""
    doc = _read()
    token = secrets.token_urlsafe(32)
    now = time.time()
    doc["devices"][token] = {"name": _clean(name) or "a device", "at": now,
                             "seen": now, "ip": str(ip or "")[:45]}
    if len(doc["devices"]) > MAX_DEVICES:
        old = sorted(doc["devices"].items(), key=lambda kv: float(kv[1].get("seen") or 0))
        for k, _ in old[:len(doc["devices"]) - MAX_DEVICES]:
            doc["devices"].pop(k, None)
    _write(doc)
    return token


def forget(what):
    """Take a device's right to come in away again.  `what` is the short id
    the Settings page shows, or the token itself; "" forgets every device,
    which is what "let nobody in any more" means."""
    doc = _read()
    what = str(what or "")
    if not what:
        if not doc["devices"]:
            return 0
        gone = len(doc["devices"])
        doc["devices"] = {}
        _write(doc)
        return gone
    for token in list(doc["devices"]):
        if token == what or token[:8] == what:
            doc["devices"].pop(token)
            _write(doc)
            return 1
    return 0


def _clean(s, limit=MAX_NAME):
    s = "" if s is None else str(s)
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()
    return s[:limit]


def name_from_agent(ua):
    """A device, named by what it says it is -- "Android phone · Chrome" --
    exactly as lib/prefs.js names one for the reading place, so the same
    phone is called the same thing on both pages.  It is done here as well
    because a device being let in has not yet been served a script."""
    ua = str(ua or "")
    what = ("Android phone" if re.search(r"Android", ua, re.I) and "Mobile" in ua
            else "Android tablet" if re.search(r"Android", ua, re.I)
            else "iPhone" if re.search(r"iPhone", ua, re.I)
            else "iPad" if re.search(r"iPad", ua, re.I)
            else "Windows computer" if re.search(r"Windows", ua, re.I)
            else "Mac" if re.search(r"Macintosh|Mac OS", ua, re.I)
            else "Chromebook" if re.search(r"CrOS", ua, re.I)
            else "Linux computer" if re.search(r"Linux", ua, re.I)
            else "a device")
    who = ("Edge" if "Edg/" in ua else "Opera" if "OPR/" in ua
           else "Firefox" if "Firefox/" in ua else "Chrome" if "Chrome/" in ua
           else "Safari" if "Safari/" in ua else "")
    return "%s · %s" % (what, who) if who else what


# ------------------------------------------------------------ the pairing code
_LOCK = threading.Lock()
_CODE = {"code": "", "made": 0.0, "wrong": 0}


def _fresh():
    return "".join(secrets.choice(ALPHABET) for _ in range(6))


def code(fresh=False):
    """The code to type on the device being let in: {"code", "left"}.

    A code that has run out of its fifteen minutes is replaced by a new one
    the moment anybody asks for it, so the Settings page always shows one
    that works.  The one printed when the server started is therefore good
    for a quarter of an hour; after that the page is where to look, which is
    what the page says under it."""
    with _LOCK:
        now = time.time()
        if fresh or not _CODE["code"] or now - _CODE["made"] > CODE_LIFE:
            _CODE["code"], _CODE["made"], _CODE["wrong"] = _fresh(), now, 0
        return {"code": _CODE["code"],
                "left": int(max(0, CODE_LIFE - (now - _CODE["made"])))}


def say_code(c=None):
    """The code with a hyphen in the middle, which is how it is read off a
    screen and typed into a phone: KP4-R7M."""
    c = c or code()["code"]
    return "%s-%s" % (c[:3], c[3:])


def check_code(given, ip="", agent=""):
    """A device typing the code.  -> (token, "") when it was right, and
    ("", why) when it was not, in words the person at the phone can act on.

    The code is retired the instant it is used: it let ONE device in, which
    is what somebody reading a code off a screen means by it.  It is retired
    at the eighth wrong guess too -- a six-character code is a billion
    guesses deep, but a billion guesses is an afternoon for a program, and an
    afternoon is longer than this toolbox is open."""
    given = re.sub(r"[^A-Za-z0-9]", "", str(given or "")).upper()
    with _LOCK:
        now = time.time()
        live = _CODE["code"] and now - _CODE["made"] <= CODE_LIFE
        if not live:
            return "", ("that code has run out -- the Settings page on the "
                        "computer shows the one that works now")
        if not given:
            return "", "type the code shown on Parseh's computer"
        if not hmac.compare_digest(_CODE["code"], given):
            _CODE["wrong"] += 1
            if _CODE["wrong"] >= CODE_TRIES:
                _CODE["code"], _CODE["made"], _CODE["wrong"] = "", 0.0, 0
                return "", ("that code is wrong, and it has now been tried too "
                            "often: Parseh has thrown it away. Ask for a new one "
                            "on the computer's Settings page")
            return "", "that code is wrong (%d tries left)" % (CODE_TRIES - _CODE["wrong"])
        _CODE["code"], _CODE["made"], _CODE["wrong"] = "", 0.0, 0
    return remember(name_from_agent(agent), ip), ""


# --------------------------------------------------------------- saving
def _check_extra(entries):
    out = []
    for raw in entries or []:
        e = _clean(raw, 100)
        if not e or e in out:
            continue
        if _net(e) is not None:
            out.append(e)
            continue
        # a name: it has to look like one, and it has to resolve to something
        # now, or somebody has typed it wrong and would never find out
        if not re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,98}[A-Za-z0-9])?", e):
            raise NetworkError("%r is neither an address range (10.8.0.0/24) nor a "
                               "name (laptop.example.ts.net)" % e)
        if not _addresses_of(e):
            raise NetworkError("this computer cannot look %s up, so Parseh could "
                               "never tell whether a device is it" % e)
        out.append(e)
    if len(out) > MAX_EXTRA:
        raise NetworkError("that is more than %d ranges and names" % MAX_EXTRA)
    return out


def _check_cert(cert):
    """"Use my own certificate": both files, readable, and left alone."""
    if not cert:
        return {}
    c, k = _clean(str(cert.get("cert") or ""), 500), _clean(str(cert.get("key") or ""), 500)
    if not c and not k:
        return {}
    if not c or not k:
        raise NetworkError("a certificate of your own needs both files: the "
                           "certificate and its key")
    for p, what in ((c, "certificate"), (k, "key")):
        if not os.path.isfile(p):
            raise NetworkError("there is no %s at %s" % (what, p))
        try:
            with open(p, "rb") as fh:
                fh.read(1)
        except OSError as e:
            raise NetworkError("Parseh cannot read the %s at %s: %s" % (what, p, e))
    return {"cert": c, "key": k}


def free_port(p, host="0.0.0.0"):
    """Is this port free to bind?  -> "" when it is, and why not when it is not.

    Asked BEFORE the settings are saved, because the page that asks is the
    only way back: a port saved and then refused by the operating system
    would leave Parseh bound to nothing, with its Settings page on an address
    that no longer exists (TO-DO §2.14)."""
    fam = socket.AF_INET6 if ":" in host else socket.AF_INET
    s = socket.socket(fam, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, p))
        return ""
    except OSError as e:
        if e.errno in (errno.EADDRINUSE,):
            return ("port %d is already taken by another program on this computer"
                    "%s -- pick another one" %
                    (p, " (Anki's AnkiConnect add-on uses it)"
                     if p == ANKICONNECT_PORT else ""))
        if e.errno in (errno.EACCES, errno.EPERM):
            return ("this computer does not let Parseh use port %d without "
                    "administrator rights -- pick one above %d" % (p, LOWEST_PORT))
        return "port %d cannot be used here: %s" % (p, e)
    finally:
        s.close()


def save(changes, check_port=True):
    """The Settings page's Save.  `changes` holds only what the page sends;
    anything it leaves out stays as it was.  Refusals are NetworkError, whose
    text is written to be shown to the person who pressed the button.

    The devices are NOT settable here: a device is let in by typing the code
    and forgotten by its own button, so a save can neither invent one nor
    lose one."""
    doc = _read()
    changes = changes or {}
    if "port" in changes:
        try:
            p = int(changes["port"])
        except (TypeError, ValueError):
            raise NetworkError("the port is a number")
        if not LOWEST_PORT <= p <= 65535:
            raise NetworkError("the port is a number between %d and 65535 "
                               "(below %d needs administrator rights)"
                               % (LOWEST_PORT, LOWEST_PORT))
        if p != doc["port"] and check_port:
            # tried on the address this save is about to bind, not on
            # another: a port free on 127.0.0.1 and taken on the Wi-Fi is
            # exactly the case this is here to catch
            why = free_port(p, bind_host(dict(doc, **{k: bool(changes[k])
                                                      for k in ("vpn", "lan")
                                                      if k in changes})))
            if why:
                raise NetworkError(why)
        doc["port"] = p
    for k in ("vpn", "lan"):
        if k in changes:
            doc[k] = bool(changes[k])
    if "extra" in changes:
        doc["extra"] = _check_extra(changes["extra"])
    if "cert" in changes:
        doc["cert"] = _check_cert(changes["cert"])
    _write(doc)
    return doc
