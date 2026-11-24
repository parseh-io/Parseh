# SPDX-License-Identifier: GPL-3.0-or-later
"""The partners this Parseh syncs with, and how it speaks to them (a0.7.0,
lane A: pairing and transport; docs/sync.md "Pairing and transport").

PAIRING.  One install shows a six-character code (and a QR payload, for the
phones later); the other types it, with the first one's address.  The code
follows docs/network.md's rules -- fifteen minutes, spent when used, thrown
away at the eighth wrong guess -- but it is a code of its own: letting a phone's
browser in and pairing a partner are two different acts.  The two installs
exchange their sync certificates (lib/syncid.py: the install's own authority,
EC P-256, CA:TRUE), install ids, names and PROTOCOL; a partner speaking another
PROTOCOL is told so, in words, and nothing is kept.

    config/peers.json   {"format": 1, "partners": {"<install id>": {
                            "id", "name", "cert" (PEM), "fingerprint", "protocol",
                            "addresses": ["host:port", ...], "last_ok": "host:port" | null,
                            "paired": t, "last_seen": t | null}}}

It sits beside prefs.STORE, as config/sync/ does, so a harness that points
prefs at a temporary tree points this there too.  It is this device's: never
synced, never in a settings backup.

MUTUAL TLS, PINNED.  Partners speak only TLS, and each side accepts only a
certificate that chains to the other's pinned authority -- in practice the
authority itself: the certificate an install presents to its partners is its
syncid certificate, a chain of one.  The browsers' certificate (.tls/, or the
person's own, network.own_cert) is never used between partners.

HOW ONE PORT SERVES BOTH (the choice, docs/sync.md): BY THE NAME IN THE
ClientHello (SNI).  A partner always asks for the name SNI below, which no
browser ever asks for (".invalid" is reserved, RFC 6761).  serve.py's
Server.finish_request peeks at the ClientHello before any handshake (it already
peeks at the first byte to tell TLS from plain http), reads that name with
`hello_name`, and wraps the connection in this module's context instead of the
browsers'.  So:
  * one port: nothing new to open in a firewall, a VPN or a router, and a phone
    -- which will never listen on the network -- only has to CALL a computer;
  * the browsers are never asked for a client certificate (a CertificateRequest
    makes some browsers show a certificate picker), and never see this one;
  * the choice is made before the handshake, so the partners' context has its
    own verify mode -- OpenSSL's SNI callback would swap the certificate but
    keep the browsers' verify mode.
A separate sync port was the alternative; it would have needed a second door in
every firewall and a second number to find, and gains nothing.

Silence is not refusal (lib/offline.py): every call has its own deadline, and
a partner that answers nothing is "unreachable", quickly.  Standard library
only (`ssl`, `http.client`): the phones will run this module.
"""
import base64
import hashlib
import hmac
import http.client
import json
import os
import re
import secrets
import socket
import ssl
import sys
import threading
import time

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import network                                                 # noqa: E402
import storeguard                                              # noqa: E402
import syncid                                                  # noqa: E402

NAME = "Parseh"
FORMAT = 1
SNI = "sync.parseh.invalid"     # the name only a partner asks for (see above)
STORE = None                    # config/peers.json beside prefs.STORE, unless set (tests)
PAIR_PATH = "/sync/pair"
API = "/sync/api/"
CODE_LIFE = network.CODE_LIFE   # fifteen minutes
CODE_TRIES = network.CODE_TRIES  # thrown away at the eighth wrong guess
ALPHABET = network.ALPHABET
TRY_EACH = 3.0                  # the most one address may take to answer the handshake
HELLO_WAIT = 3.0                # the most a ClientHello may take to arrive whole
MAX_BODY = 64 << 20             # one call's body (lane B moves files in chunks below this)
SEEN_EVERY = 60                 # last_seen is written at most once a minute per partner
QR_SCHEME = "parseh-pair"

WHERE = None     # serve.py: function() -> {"port": int, "names": [host or address, ...]}

_LOCK = threading.RLock()
_CODE = {"code": "", "made": 0.0, "wrong": 0}
_SEEN = {}       # partner id -> (when, reachable: bool), this run's memory
_CTX = {"key": None, "ctx": None}
_PROTOCOL_TEST = None   # tests: speak another protocol than syncid.PROTOCOL


class Unreachable(Exception):
    """The partner answered nothing (or nothing that is it) within the deadline."""


class Refused(Exception):
    """The partner answered, and said no -- `reason` says why, in words."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def protocol():
    return _PROTOCOL_TEST if _PROTOCOL_TEST is not None else syncid.PROTOCOL


def protocol_said(mine, theirs, them="the other computer"):
    """A mismatch, in words a person can act on (said by either side)."""
    try:
        older = "this computer's" if int(mine) < int(theirs) else "%s's" % them
    except (TypeError, ValueError):
        older = "the older"
    return ("This computer speaks version %s of the sync protocol and %s speaks version %s, so "
            "they cannot sync. Update %s Parseh to the same version as the other, then pair "
            "them again." % (mine, them, theirs, older))


# ------------------------------------------------------------------ the store
def store():
    if STORE:
        return STORE
    import prefs
    return os.path.join(os.path.dirname(os.path.abspath(prefs.STORE)), "peers.json")


def _ok(doc):
    return isinstance(doc, dict) and isinstance(doc.get("partners"), dict)


def _read():
    try:
        with open(store(), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        doc = None
    if not _ok(doc):
        doc = {"format": FORMAT, "partners": {}}
    return doc


def _write(doc):
    storeguard.write_json(store(), doc, ok=_ok, private=True)


def partner(pid):
    with _LOCK:
        p = _read()["partners"].get(pid)
        return dict(p) if p else None


def partners():
    """[{"id", "name", "last_seen", "reachable", "fingerprint", "addresses",
    "last_ok", "paired", "protocol"}] -- reachable: True / False / None (not
    tried in this run)."""
    with _LOCK:
        out = []
        for pid, p in sorted(_read()["partners"].items(), key=lambda kv: kv[1].get("name", "")):
            seen = _SEEN.get(pid)
            out.append({"id": pid, "name": p.get("name") or pid[:8],
                        "last_seen": p.get("last_seen"),
                        "reachable": seen[1] if seen else None,
                        "fingerprint": p.get("fingerprint"),
                        "addresses": list(p.get("addresses") or []),
                        "last_ok": p.get("last_ok"), "paired": p.get("paired"),
                        "protocol": p.get("protocol")})
        return out


def has_partners():
    try:
        return bool(_read()["partners"])
    except Exception:                                   # noqa: BLE001 -- never stops a bind
        return False


def remove(pid):
    """Forget a partner -> True when there was one.  From this moment it is
    refused: its certificate leaves the context, and a request still arriving
    on a connection it had open is refused by id (syncroutes)."""
    with _LOCK:
        doc = _read()
        gone = doc["partners"].pop(str(pid or ""), None)
        if gone is None:
            return False
        _write(doc)
        _SEEN.pop(pid, None)
        _CTX["key"] = None
        return True


def _keep(rec):
    with _LOCK:
        doc = _read()
        doc["partners"][rec["id"]] = rec
        _write(doc)
        _CTX["key"] = None


def _saw(pid, ok, address=None):
    """A call's outcome: this run's memory, and last_seen / last_ok on disk
    (at most once a minute, or when the address that works changed)."""
    now = time.time()
    with _LOCK:
        _SEEN[pid] = (now, bool(ok))
        if not ok:
            return
        doc = _read()
        p = doc["partners"].get(pid)
        if not p:
            return
        if address and p.get("last_ok") != address:
            p["last_ok"] = address
            if address not in p.setdefault("addresses", []):
                p["addresses"].insert(0, address)
        elif now - (p.get("last_seen") or 0) < SEEN_EVERY:
            return
        p["last_seen"] = now
        _write(doc)


# ------------------------------------------------------------ the pairing code
def _fresh():
    return "".join(secrets.choice(ALPHABET) for _ in range(6))


def code(fresh=False):
    """{"code", "left"}: the code being shown, made again when asked or run out."""
    with _LOCK:
        now = time.time()
        if fresh or not _CODE["code"] or now - _CODE["made"] > CODE_LIFE:
            _CODE["code"], _CODE["made"], _CODE["wrong"] = _fresh(), now, 0
        return {"code": _CODE["code"], "left": int(max(0, CODE_LIFE - (now - _CODE["made"])))}


def code_live():
    with _LOCK:
        return bool(_CODE["code"]) and time.time() - _CODE["made"] <= CODE_LIFE


def _check_code(given):
    """-> "" when right (and the code is spent), else why, in words."""
    given = re.sub(r"[^A-Za-z0-9]", "", str(given or "")).upper()
    with _LOCK:
        if not code_live():
            return ("that code has run out, or none is shown: ask for a new one on the other "
                    "computer's Settings, Devices")
        if not given:
            return "type the code the other computer shows"
        if not hmac.compare_digest(_CODE["code"], given):
            _CODE["wrong"] += 1
            if _CODE["wrong"] >= CODE_TRIES:
                _CODE["code"], _CODE["made"], _CODE["wrong"] = "", 0.0, 0
                return ("that code is wrong, and it has now been tried too often: the other "
                        "computer has thrown it away. Ask it for a new one")
            return "that code is wrong (%d tries left)" % (CODE_TRIES - _CODE["wrong"])
        _CODE["code"], _CODE["made"], _CODE["wrong"] = "", 0.0, 0
        return ""


def stop_offer():
    with _LOCK:
        _CODE["code"], _CODE["made"], _CODE["wrong"] = "", 0.0, 0


def _where():
    try:
        w = WHERE() if WHERE else {}
    except Exception:                                   # noqa: BLE001
        w = {}
    port = int(w.get("port") or network.port())
    names = []
    for n in w.get("names") or []:
        n = str(n).strip()
        if n and n not in names and len(names) < 20:
            names.append(n)
    return {"port": port, "names": names}


def _addr(host, port):
    return "[%s]:%d" % (host, port) if ":" in host else "%s:%d" % (host, port)


def offer():
    """Start pairing on this side: {"code", "said", "left", "addresses", "qr",
    "fingerprint", "name"}.  The QR payload carries the code, the addresses
    and the full fingerprint, so a device that scans it pins this computer
    before it sends a byte (typing the code pins it by the answer instead)."""
    ident = syncid.ensure()
    if not ident.get("key"):
        raise Refused("this computer has no sync key yet (Parseh makes it at start); "
                      "start Parseh again and try once more")
    c = code(fresh=True)
    w = _where()
    addrs = [_addr(n, w["port"]) for n in w["names"]]
    fp = ident["key"]["fingerprint"]
    qr = "%s:%d?code=%s&fp=%s&at=%s" % (QR_SCHEME, protocol(), c["code"], fp,
                                       ",".join(addrs))
    return {"code": c["code"], "said": network.say_code(c["code"]), "left": c["left"],
            "addresses": addrs, "qr": qr, "fingerprint": fp, "name": ident["name"],
            "protocol": protocol()}


def parse_address(text, port=None):
    """"desk.local", "192.168.1.5:7654", "https://desk.local:7654/x", "[fe80::1]:7654"
    -> (host, port); ValueError in words."""
    t = str(text or "").strip()
    t = re.sub(r"^[a-z]+://", "", t, flags=re.I).split("/", 1)[0]
    m = re.fullmatch(r"\[([0-9A-Fa-f:.%]+)\](?::(\d{1,5}))?", t) or \
        re.fullmatch(r"([A-Za-z0-9._%-]+)(?::(\d{1,5}))?", t)
    if not m or not m.group(1):
        raise ValueError("type the other computer's address, as its Settings, Devices shows it "
                         "(for example desk.local:7654)")
    p = int(m.group(2) or port or network.DEFAULT_PORT)
    if not 0 < p < 65536:
        raise ValueError("that port is not a port")
    return m.group(1), p


# ------------------------------------------------------------- TLS contexts
def _pem_der(pem):
    m = re.search(r"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", pem or "", re.S)
    if not m:
        raise ValueError("no certificate")
    return base64.b64decode("".join(m.group(1).split()))


def _fp_der(der):
    return hashlib.sha256(der).hexdigest()


def _own():
    ident = syncid.ensure()
    p = syncid.paths()
    if not ident.get("key") or not os.path.isfile(p["cert"]):
        raise Refused("this computer has no sync key yet")
    return p["cert"], p["key"]


def server_context():
    """The partners' context: this install's syncid certificate, and a client
    certificate asked for and checked against every pinned partner's
    authority.  CERT_OPTIONAL: a caller with NO certificate is let through the
    handshake for one thing only, the pairing request (syncroutes refuses it
    everything else); a caller with a certificate no partner's authority
    signed fails the handshake -- refused before any handler runs.  Made
    again whenever the partners or the key change."""
    cert, key = _own()
    try:
        st = os.stat(store())
        sk = (st.st_mtime_ns, st.st_size)
    except OSError:
        sk = None
    k = (sk, os.stat(cert).st_mtime_ns)
    with _LOCK:
        if _CTX["key"] == k and _CTX["ctx"] is not None:
            return _CTX["ctx"]
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
        ctx.verify_mode = ssl.CERT_OPTIONAL
        pems = [p.get("cert") for p in _read()["partners"].values() if p.get("cert")]
        if pems:
            ctx.load_verify_locations(cadata="\n".join(pems))
        ctx._parseh_sync = True                     # is_sync_context
        _CTX["key"], _CTX["ctx"] = k, ctx
        return ctx


def is_sync_context(ctx):
    return bool(getattr(ctx, "_parseh_sync", False))


def _client_context(pinned_pem=None):
    """Calling a partner: this install's certificate shown, the partner's
    pinned authority the only one trusted.  With no pin (pairing), nothing is
    shown and nothing trusted yet: the answer is checked against the
    certificate the handshake carried (pair_with)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = False      # partners are pinned by authority, not by a name a DNS can lie about
    if pinned_pem:
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cadata=pinned_pem)
        ctx.load_cert_chain(*_own())
    else:
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def partner_of(sslsock):
    """The paired partner on this TLS connection -> id, or None."""
    try:
        der = sslsock.getpeercert(binary_form=True)
    except (AttributeError, ValueError, OSError):
        return None
    if not der:
        return None
    fp = _fp_der(der)
    with _LOCK:
        for pid, p in _read()["partners"].items():
            if p.get("fingerprint") and hmac.compare_digest(p["fingerprint"], fp):
                return pid
    return None


# ------------------------------------------------------- the ClientHello's name
def hello_name(sock, wait=HELLO_WAIT):
    """The server name (SNI) a TLS ClientHello asks for, read with MSG_PEEK so
    the handshake that follows sees every byte -> str, or None (no name, not a
    ClientHello, or not whole in `wait` seconds)."""
    end = time.monotonic() + wait
    need, data = 5, b""
    while True:
        try:
            data = sock.recv(max(need, 5), socket.MSG_PEEK)
        except (OSError, ValueError):
            return None
        if len(data) >= 5 and need == 5:
            if data[0] != 0x16:
                return None
            need = 5 + int.from_bytes(data[3:5], "big")
        if len(data) >= need and need > 5:
            break
        if not data or time.monotonic() > end:
            return None
        time.sleep(0.01)
    try:
        return _sni(data[5:need])
    except (IndexError, ValueError):
        return None


def _sni(hs):
    if hs[0] != 1:                      # not a ClientHello
        return None
    i = 4 + 2 + 32                      # type, length, version, random
    i += 1 + hs[i]                      # session id
    i += 2 + int.from_bytes(hs[i:i + 2], "big")     # cipher suites
    i += 1 + hs[i]                      # compression
    end = i + 2 + int.from_bytes(hs[i:i + 2], "big")
    i += 2
    while i + 4 <= min(end, len(hs)):
        typ = int.from_bytes(hs[i:i + 2], "big")
        ln = int.from_bytes(hs[i + 2:i + 4], "big")
        body = hs[i + 4:i + 4 + ln]
        if typ == 0:                    # server_name
            j = 2
            while j + 3 <= len(body):
                kind = body[j]
                n = int.from_bytes(body[j + 1:j + 3], "big")
                if kind == 0:
                    return body[j + 3:j + 3 + n].decode("ascii", "replace")
                j += 3 + n
            return None
        i += 4 + ln
    return None


def may_knock(ip):
    """May an address the doors do not let in still reach the server, to be
    told apart by its ClientHello?  Only from this computer, a VPN or the
    local network, and only while there is a partner or a pairing code."""
    if network.where(ip) not in (network.SELF, network.VPN, network.LAN):
        return False
    return code_live() or has_partners()


def wants_network():
    """network.BIND_WANTED: listen beyond 127.0.0.1 while there is a partner
    or a pairing code, whatever the browsers' doors say (docs/sync.md)."""
    return code_live() or has_partners()


def serve(server, request, client_address):
    """One partner's connection, after the ClientHello asked for SNI: the
    handshake in the partners' context, then serve.py's own Handler (whose
    _dispatch hands the request to lib/syncroutes.py first)."""
    tls = None
    try:
        tls = server_context().wrap_socket(request, server_side=True,
                                           do_handshake_on_connect=False)
        tls.settimeout(30)
        tls.do_handshake()
    except (ssl.SSLError, OSError, Refused):
        try:
            (tls or request).close()
        except OSError:
            pass
        return
    try:
        server.RequestHandlerClass(tls, client_address, server)
    finally:
        try:
            tls.close()
        except OSError:
            pass


# --------------------------------------------------------------- the wire
def frame(doc, body=None):
    """-> (bytes, json length): the JSON, then the raw body."""
    j = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return j + (body or b""), len(j)


def unframe(data, jlen):
    if jlen is None:
        jlen = len(data)
    doc = json.loads(data[:jlen].decode("utf-8") or "{}")
    rest = data[jlen:]
    return (doc if isinstance(doc, dict) else {}), (rest if rest else None)


class _Conn(http.client.HTTPConnection):
    """http.client over a pinned TLS socket that asks for SNI."""

    def __init__(self, host, port, ctx, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ctx = ctx

    def connect(self):
        super().connect()
        self.sock = self._ctx.wrap_socket(self.sock, server_hostname=SNI)


def _exchange(host, port, ctx, path, doc, body, deadline, connect_for):
    """One request to one address.  -> (status, doc, body, peer DER).
    socket.timeout / OSError: the address is silent or closed;
    ssl.SSLCertVerificationError: something else answers there;
    other ssl.SSLError: the partner refused us."""
    data, jlen = frame(doc, body)
    c = _Conn(host, port, ctx, timeout=max(0.05, min(connect_for, deadline - time.monotonic())))
    try:
        c.connect()
        der = c.sock.getpeercert(binary_form=True)
        c.sock.settimeout(max(0.05, deadline - time.monotonic()))
        c.putrequest("POST", path, skip_accept_encoding=True)
        c.putheader("Content-Type", "application/x-parseh-sync")
        c.putheader("Content-Length", str(len(data)))
        c.putheader("X-Parseh-Json", str(jlen))
        c.putheader("X-Parseh-Protocol", str(protocol()))
        c.endheaders(data)
        r = c.getresponse()
        raw = r.read(MAX_BODY + (1 << 20))
        try:
            rj = int(r.getheader("X-Parseh-Json") or len(raw))
        except ValueError:
            rj = len(raw)
        try:
            out, rest = unframe(raw, rj)
        except (ValueError, UnicodeDecodeError):
            out, rest = {"ok": False, "error": "the answer could not be read"}, None
        return r.status, out, rest, der
    finally:
        c.close()


def _targets(p):
    seen, out = set(), []
    for a in [p.get("last_ok")] + list(p.get("addresses") or []):
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def call(partner_id, op, payload, *, body=None, timeout):
    """Ask a paired partner to do `op` -> (dict, bytes | None).

    Tries the last address that worked, then every name and address the
    partner gave (its certificate's names, .local, .ts.net), each given at
    most TRY_EACH seconds to answer the handshake and all of them together at
    most `timeout`.  Raises Unreachable when none answers in time (silence),
    and Refused(reason) when the partner answered no: it does not know this
    computer any more, it speaks another protocol, or the op said no."""
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", str(op or "")):
        raise ValueError("an op is a short lower-case name")
    if not isinstance(payload, dict):
        raise ValueError("a payload is a dict")
    if body is not None and len(body) > MAX_BODY:
        raise ValueError("a body is at most %d bytes" % MAX_BODY)
    p = partner(partner_id)
    if p is None:
        raise Refused("that computer is not paired with this one")
    who = p.get("name") or partner_id[:8]
    deadline = time.monotonic() + float(timeout)
    ctx = _client_context(p.get("cert"))
    tried = []
    for a in _targets(p):
        if time.monotonic() >= deadline:
            break
        try:
            host, port = parse_address(a)
        except ValueError:
            continue
        try:
            st, out, rest, _der = _exchange(host, port, ctx, API + op, payload, body,
                                            deadline, TRY_EACH)
        except ssl.SSLCertVerificationError:
            tried.append("%s answers, but it is not %s" % (a, who))
            continue
        except ssl.SSLError as e:
            _saw(partner_id, True)
            raise Refused("%s no longer counts this computer as a partner (%s): pair them again"
                          % (who, getattr(e, "reason", None) or "TLS refused"))
        except (OSError, http.client.HTTPException) as e:
            tried.append("%s: %s" % (a, "no answer" if isinstance(e, (socket.timeout, TimeoutError))
                                     else (e.strerror or e.__class__.__name__)
                                     if isinstance(e, OSError) else e.__class__.__name__))
            continue
        if st == 200 and out.get("ok", True) is not False:
            _saw(partner_id, True, a)
            return out, rest
        _saw(partner_id, True)
        raise Refused(str(out.get("error") or "%s answered %d" % (who, st)))
    _saw(partner_id, False)
    raise Unreachable("%s did not answer within %.0f s (%s)"
                      % (who, float(timeout), "; ".join(tried) or "no address to try"))


# ------------------------------------------------------------- pairing, both sides
def _me():
    ident = syncid.ensure()
    w = _where()
    with open(syncid.paths()["cert"], encoding="ascii") as fh:
        pem = fh.read()
    return {"install": ident["install"], "name": ident["name"], "protocol": protocol(),
            "cert": pem, "port": w["port"], "names": w["names"]}


def accept(payload, ip):
    """The side that shows the code, answering POST /sync/pair -> (status, doc)."""
    theirs = payload.get("protocol")
    if theirs != protocol():
        return 409, {"ok": False, "protocol": protocol(),
                     "error": protocol_said(protocol(), theirs, "the computer typing the code")}
    try:
        pem = str(payload.get("cert") or "")
        der = _pem_der(pem)
        ssl.DER_cert_to_PEM_cert(der)
    except (ValueError, TypeError):
        return 400, {"ok": False, "error": "the other computer sent no certificate it could be pinned by"}
    install = str(payload.get("install") or "")
    if not re.fullmatch(r"[0-9a-f]{32}", install):
        return 400, {"ok": False, "error": "the other computer did not say who it is"}
    if install == syncid.install_id():
        return 409, {"ok": False, "error": "that is this very computer (or a copy of it: a "
                                           "copied install gets a new identity on Settings, Devices)"}
    why = _check_code(payload.get("code"))
    if why:
        return 403, {"ok": False, "error": why}
    try:
        port = int(payload.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    addrs = []
    if port and 0 < port < 65536:
        if ip and network.where(ip) != network.AWAY:
            addrs.append(_addr(ip, port))
        for n in payload.get("names") or []:
            n = str(n)
            if re.fullmatch(r"[A-Za-z0-9._:%-]{1,253}", n):
                a = _addr(n, port)
                if a not in addrs:
                    addrs.append(a)
    now = time.time()
    rec = {"id": install, "name": re.sub(r"\s+", " ", str(payload.get("name") or ""))[:syncid.MAX_NAME]
           or install[:8], "cert": ssl.DER_cert_to_PEM_cert(der), "fingerprint": _fp_der(der),
           "protocol": theirs, "addresses": addrs[:24], "last_ok": addrs[0] if addrs else None,
           "paired": now, "last_seen": now}
    _keep(rec)
    _SEEN[install] = (now, True)
    me = _me()
    me.pop("port", None)          # the caller knows it: it is the address it typed
    me["ok"] = True
    return 200, me


def pair_with(address, given_code, fingerprint=None, timeout=15.0):
    """The side that types the code: call `address` and pair -> the partner's
    record (as partners() shows it).  `fingerprint`, from a scanned QR code,
    pins the other side before anything is sent; without it, the answer must
    carry the very certificate the handshake showed."""
    host, port = parse_address(address)
    me = _me()
    me["code"] = given_code
    deadline = time.monotonic() + timeout
    try:
        st, out, _rest, der = _exchange(host, port, _client_context(None), PAIR_PATH, me, None,
                                        deadline, min(TRY_EACH * 2, timeout))
    except ssl.SSLError as e:
        raise Refused("the computer at %s did not accept a partner's connection (%s)"
                      % (_addr(host, port), getattr(e, "reason", None) or e))
    except (OSError, http.client.HTTPException) as e:
        raise Unreachable("nothing answered at %s (%s): check the address, and that Parseh is "
                          "running there" % (_addr(host, port),
                                             "no answer" if isinstance(e, (socket.timeout, TimeoutError))
                                             else getattr(e, "strerror", None) or e.__class__.__name__))
    if fingerprint and not hmac.compare_digest(_fp_der(der or b""), str(fingerprint).lower()):
        raise Refused("the computer at %s is not the one whose code was scanned" % _addr(host, port))
    if st != 200 or not out.get("ok"):
        raise Refused(str(out.get("error") or "the other computer answered %d" % st))
    if out.get("protocol") != protocol():
        raise Refused(protocol_said(protocol(), out.get("protocol"), out.get("name") or "the other computer"))
    try:
        pder = _pem_der(out.get("cert"))
    except ValueError:
        raise Refused("the other computer sent no certificate it could be pinned by")
    if not der or not hmac.compare_digest(_fp_der(pder), _fp_der(der)):
        raise Refused("the answer did not come from the computer that answered at %s: "
                      "something on the network is in between; pairing stopped" % _addr(host, port))
    install = str(out.get("install") or "")
    if not re.fullmatch(r"[0-9a-f]{32}", install):
        raise Refused("the other computer did not say who it is")
    addrs = [_addr(host, port)]
    for n in out.get("names") or []:
        a = _addr(str(n), port)
        if a not in addrs:
            addrs.append(a)
    now = time.time()
    rec = {"id": install, "name": str(out.get("name") or install[:8])[:syncid.MAX_NAME],
           "cert": ssl.DER_cert_to_PEM_cert(pder), "fingerprint": _fp_der(pder),
           "protocol": out.get("protocol"), "addresses": addrs[:24], "last_ok": addrs[0],
           "paired": now, "last_seen": now}
    _keep(rec)
    _SEEN[install] = (now, True)
    return next(p for p in partners() if p["id"] == install)


if wants_network not in network.BIND_WANTED:
    network.BIND_WANTED.append(wants_network)
