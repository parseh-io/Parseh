# SPDX-License-Identifier: GPL-3.0-or-later
"""Who this Parseh is, to the other Parseh it syncs with (a0.7.0, docs/sync.md).

At its first start every install gets:

  * an INSTALL ID -- 32 random hex digits, made once and never changed, which
    names this install in every version vector of the change log
    (lib/synclog.py) and in every partner's list;
  * a KEY PAIR -- an EC P-256 private key and a self-signed certificate
    carrying the install id -- which pairing (lane A) shows to the partner as
    a fingerprint, and which mutual TLS between partners pins;
  * a NAME the person chooses on Settings → Devices, which starts as this
    computer's own name (the host name, without a ".local" or a domain).

    config/sync/identity.json   {"format": 1, "install": "9f…", "name": "desk",
                                 "created": 1763900000.0,
                                 "key": {"fingerprint": "sha256 hex of the DER",
                                         "made": 1763900000.0} | null}
    config/sync/identity.key    the private key, readable by this user only
    config/sync/identity.crt    the certificate

All three are this device's: never synced, never in a settings backup (they
are not among lib/configbackup.py's STORES), and an install copied whole to
another computer must be paired again -- the copy's id would be the same, so
`reset()` makes a new one (lane E's page offers it).

THE KEY IS MADE WITHOUT ASSUMING A SUBPROCESS.  The `cryptography` package
when this Python has it (the phones' builds will), else `openssl`, the way
serve.py already makes the https certificate (environment.yml carries it on
every computer).  MINTER may be set to any function(key_path, cert_path,
common_name).  When neither can run, the identity is still made, with no key
yet: `ensure()` says so and tries again at the next start; pairing waits.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import storeguard                                              # noqa: E402

FORMAT = 1
PROTOCOL = 1          # the version of the sync protocol this Parseh speaks (lane A says it at pairing)
MAX_NAME = 60
_LOCK = threading.RLock()
MINTER = None


def _home():
    import synclog
    return synclog.home()


def paths():
    h = _home()
    return {"identity": os.path.join(h, "identity.json"), "key": os.path.join(h, "identity.key"),
            "cert": os.path.join(h, "identity.crt")}


def default_name():
    """This computer's name, as the person would recognise it."""
    try:
        n = socket.gethostname() or ""
    except OSError:
        n = ""
    n = n.split(".")[0].strip()
    return n[:MAX_NAME] or "Parseh"


def _ok(doc):
    return (isinstance(doc, dict) and isinstance(doc.get("install"), str)
            and re.fullmatch(r"[0-9a-f]{32}", doc["install"]) is not None)


def _read():
    try:
        with open(paths()["identity"], encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    return doc if _ok(doc) else None


def _write(doc):
    storeguard.write_json(paths()["identity"], doc, ok=_ok, private=True)


def identity(make=True):
    """{"install", "name", "created", "key": {...} | None, "protocol"}; made on
    the first call (with no key: that is ensure()'s)."""
    with _LOCK:
        doc = _read()
        if doc is None:
            if not make:
                return None
            doc = {"format": FORMAT, "install": secrets.token_hex(16), "name": default_name(),
                   "created": time.time(), "key": None}
            _write(doc)
        out = dict(doc)
        out["protocol"] = PROTOCOL
        return out


def install_id():
    return identity()["install"]


def name():
    return identity()["name"]


def set_name(new):
    """The person's name for this install -> the name kept.  Empty: the default."""
    new = re.sub(r"\s+", " ", str(new or "")).strip()[:MAX_NAME] or default_name()
    with _LOCK:
        doc = identity()
        doc.pop("protocol", None)
        doc["name"] = new
        _write(doc)
    return new


# ------------------------------------------------------------------ the key pair
def _mint_cryptography(key_path, cert_path, cn):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    import datetime
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(key, hashes.SHA256()))
    storeguard.write_text(key_path, key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode("ascii"), private=True)
    storeguard.write_text(cert_path, cert.public_bytes(serialization.Encoding.PEM).decode("ascii"))


def _mint_openssl(key_path, cert_path, cn):
    tmp_key, tmp_cert = key_path + ".new.tmp", cert_path + ".new.tmp"
    try:
        old = os.umask(0o077)
        try:
            r = subprocess.run(["openssl", "req", "-x509", "-newkey", "ec",
                                "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-sha256",
                                "-days", "3650", "-subj", "/CN=%s" % cn,
                                "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0",
                                "-keyout", tmp_key, "-out", tmp_cert],
                               capture_output=True, text=True, timeout=60)
        finally:
            os.umask(old)
        if r.returncode != 0:
            raise RuntimeError("openssl: %s" % (r.stderr.strip().splitlines() or ["failed"])[-1])
        with open(tmp_key, encoding="ascii") as fh:
            storeguard.write_text(key_path, fh.read(), private=True)
        with open(tmp_cert, encoding="ascii") as fh:
            storeguard.write_text(cert_path, fh.read())
    finally:
        for p in (tmp_key, tmp_cert):
            try:
                os.unlink(p)
            except OSError:
                pass


def _minters():
    if MINTER is not None:
        return [MINTER]
    out = []
    try:
        import cryptography  # noqa: F401
        out.append(_mint_cryptography)
    except ImportError:
        pass
    out.append(_mint_openssl)
    return out


def fingerprint(cert_path):
    """sha256 of the certificate's DER bytes, in hex (what pairing shows)."""
    with open(cert_path, encoding="ascii") as fh:
        pem = fh.read()
    m = re.search(r"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", pem, re.S)
    if not m:
        raise ValueError("no certificate in %s" % cert_path)
    return hashlib.sha256(base64.b64decode("".join(m.group(1).split()))).hexdigest()


def ensure():
    """The identity, with its key pair made if it has none -> the identity.
    Called at the server's start (lib/synclog.start); quick after the first."""
    with _LOCK:
        doc = identity()
        p = paths()
        if doc.get("key") and os.path.isfile(p["key"]) and os.path.isfile(p["cert"]):
            return doc
        why = []
        for mint in _minters():
            try:
                mint(p["key"], p["cert"], "Parseh %s" % doc["install"])
                break
            except Exception as e:                    # noqa: BLE001 -- the next way, then words
                why.append(str(e) or e.__class__.__name__)
        else:
            print("!! sync: this install has no key pair yet (%s); pairing waits for it, "
                  "and the next start tries again" % "; ".join(why), flush=True)
            return doc
        doc.pop("protocol", None)
        doc["key"] = {"fingerprint": fingerprint(p["cert"]), "made": time.time()}
        _write(doc)
        doc["protocol"] = PROTOCOL
        return doc


def reset():
    """A new install id and a new key pair (an install copied to another
    computer is not that computer).  The name stays.  The change log's vectors
    keep the old id's counters, which is right: they are history."""
    with _LOCK:
        old = _read() or {}
        p = paths()
        for k in ("key", "cert"):
            try:
                os.unlink(p[k])
            except OSError:
                pass
        doc = {"format": FORMAT, "install": secrets.token_hex(16),
               "name": old.get("name") or default_name(), "created": time.time(), "key": None}
        _write(doc)
    return ensure()
