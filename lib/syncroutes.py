# SPDX-License-Identifier: GPL-3.0-or-later
"""The sync routes, /sync/api/<op>, answered to a paired partner only (a0.7.0,
lane A; docs/sync.md "Pairing and transport").

    register(op, handler)      handler(partner_id, payload: dict, body: bytes | None)
                                   -> (dict, bytes | None)
                               raise Refuse("in words") to say no; anything else
                               raised is a failure the caller hears as Refused too.

serve.py's Handler._dispatch calls `answer(handler, method)` first, for every
request.  On a connection made in the partners' TLS context (lib/syncpeer.py,
chosen by SNI) it answers everything -- /sync/pair, and /sync/api/<op> to a
partner whose pinned certificate the handshake carried -- and nothing else is
served there.  On any other connection a path under /sync/ is refused, whatever
the Wi-Fi and VPN doors let browsers do.

THE WIRE.  POST, body = JSON then the raw bytes, `X-Parseh-Json` saying how long
the JSON is, `X-Parseh-Protocol` saying syncid.PROTOCOL, `X-Parseh-Device` what
this device says of itself (syncid.device()); the answer the same way.
"""
import os
import re
import sys
import threading
import time
import traceback

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import syncid                                                  # noqa: E402
import syncpeer                                                # noqa: E402

PREFIX = "/sync/"
_OPS = {}
_LOCK = threading.Lock()


class Refuse(Exception):
    """A handler's no, in words; the caller's syncpeer.call raises Refused(reason)."""


def register(op, handler):
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", str(op or "")):
        raise ValueError("an op is a short lower-case name")
    with _LOCK:
        _OPS[op] = handler


def unregister(op):
    with _LOCK:
        _OPS.pop(op, None)


def ops():
    with _LOCK:
        return sorted(_OPS)


def _hello(partner_id, payload, body):
    """Who is there: reachability, the name, the protocol and what this device
    says of itself ("send only", "holds little"); what the caller says of
    itself, when it says it, is kept in its record."""
    syncpeer.note_device(partner_id, payload.get("device"))
    ident = syncid.identity()
    return {"ok": True, "install": ident["install"], "name": ident["name"],
            "protocol": syncpeer.protocol(), "time": time.time(),
            "device": syncid.device()}, None


def _removed(partner_id, payload, body):
    """The partner removed this computer: marked "removed you" here, never
    forgotten by itself (Settings → Devices offers to remove it too)."""
    syncpeer.removed_by(partner_id, payload.get("name"))
    return {"ok": True}, None


def _echo(partner_id, payload, body):
    """The payload and the body back, and who asked: the transport's own test op."""
    return {"ok": True, "payload": payload, "partner": partner_id,
            "size": len(body or b"")}, body


register("hello", _hello)
register("echo", _echo)
register("removed", _removed)


def _send(h, status, doc, body=None):
    data, jlen = syncpeer.frame(doc, body)
    h._status = status                           # serve.py's activity bookkeeping
    h.send_response(status)
    h.send_header("Content-Type", "application/x-parseh-sync")
    h.send_header("Content-Length", str(len(data)))
    h.send_header("X-Parseh-Json", str(jlen))
    h.send_header("X-Parseh-Protocol", str(syncpeer.protocol()))
    h.send_header("X-Parseh-Device", syncpeer.device_header())
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    if h.command != "HEAD":
        h.wfile.write(data)


def _no(h, status, why, read=True):
    """A refusal, and the connection closed after it.  A small body still
    unread is read first: closing a TLS socket with bytes left unread sends a
    reset, which can overtake the answer and leave the caller with nothing
    but a dropped connection."""
    h.close_connection = True
    if read and h.command in ("POST", "PUT", "PATCH"):
        try:
            n = int(h.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if 0 < n <= (1 << 16):
            try:
                h.rfile.read(n)
            except OSError:
                pass
    _send(h, status, {"ok": False, "error": why})
    return True


def answer(h, method):
    """-> True when this request was a sync connection's or a sync path's (and
    has been answered); False lets serve.py go on as before."""
    path = h.path.split("?", 1)[0]
    conn = h.connection
    sync = syncpeer.is_sync_context(getattr(conn, "context", None))
    if not sync:
        if path == "/sync" or path.startswith(PREFIX):
            return _no(h, 403, "the sync routes answer a paired partner only, over its own "
                               "pinned connection")
        return False
    if method != "POST" or not (path == syncpeer.PAIR_PATH or path.startswith(syncpeer.API)):
        return _no(h, 404 if method == "POST" else 405,
                   "a partner's connection carries the sync routes and nothing else")
    try:
        n = int(h.headers.get("Content-Length") or 0)
        jlen = int(h.headers.get("X-Parseh-Json") or n)
    except ValueError:
        return _no(h, 400, "bad lengths")
    if n < 0 or n > syncpeer.MAX_BODY + (1 << 20) or not 0 <= jlen <= n:
        return _no(h, 413, "too much in one call (at most %d bytes)" % syncpeer.MAX_BODY)
    raw = h.rfile.read(n) if n else b""
    try:
        payload, body = syncpeer.unframe(raw, jlen)
    except (ValueError, UnicodeDecodeError):
        return _no(h, 400, read=False, why="the request could not be read")
    ip = (h.client_address or ("",))[0]
    pid = syncpeer.partner_of(conn)
    if path == syncpeer.PAIR_PATH:
        if pid is None and conn.getpeercert(binary_form=True):
            return _no(h, 403, read=False, why="a certificate nobody paired")    # cannot happen: the handshake refuses it
        st, doc = syncpeer.accept(payload, ip)
        _send(h, st, doc)
        return True
    if pid is None:
        return _no(h, 403, read=False, why="this computer is not paired with yours: pair them on Settings, Devices")
    try:
        theirs = int(h.headers.get("X-Parseh-Protocol") or 0)
    except ValueError:
        theirs = 0
    if theirs != syncpeer.protocol():
        # said from the CALLER's side, since the caller is who shows it
        return _no(h, 409, read=False, why=syncpeer.protocol_said(theirs, syncpeer.protocol(), syncid.name()))
    syncpeer.heard_device(pid, h.headers.get("X-Parseh-Device"))
    op = path[len(syncpeer.API):]
    with _LOCK:
        fn = _OPS.get(op)
    if fn is None:
        return _no(h, 404, read=False, why="the other computer does not know the sync step %r: is it an older "
                           "Parseh?" % op[:64])
    syncpeer._saw(pid, True, None)
    try:
        doc, out = fn(pid, payload, body)
    except Refuse as e:
        return _no(h, 409, read=False, why=str(e) or "refused")
    except Exception as e:                              # noqa: BLE001 -- said to the caller, logged here
        traceback.print_exc()
        return _no(h, 500, read=False, why="the other computer failed at %s: %s: %s" % (op, type(e).__name__, e))
    if not isinstance(doc, dict):
        doc = {"ok": True, "value": doc}
    _send(h, 200, doc, out)
    return True
