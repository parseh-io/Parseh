# SPDX-License-Identifier: GPL-3.0-or-later
"""Two (or more) Parseh installs in one process, wired together directly, for
the exchange's tests (tests/test_sync_exchange.py).

Each Install is a temporary tree with its own shelves, its own personal
config stores and its own config/sync/ (so its own identity and change log).
`world.on(inst)` points every module's stores at that tree; a call from one
install to another (the fake `syncpeer.call`) switches to the partner's tree,
runs the handler lane B registered through the fake `syncroutes.register`,
and switches back.  Payloads and answers go through JSON, as on the wire.

The fakes stand in for lane A's lib/syncpeer.py and lib/syncroutes.py (the
contract in docs/sync.md); they are put into sys.modules only while a World
is open, and taken out again after.  Nothing here touches the checkout's
config/ (tests/configguard.py) or its shelves.
"""
import contextlib
import json
import os
import shutil
import sys
import tempfile
import threading
import types
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "lib"), os.path.join(ROOT, "markdown", "app")):
    if p not in sys.path:
        sys.path.insert(0, p)

import analysisconfig   # noqa: E402
import clips            # noqa: E402
import decks            # noqa: E402
import langprompts      # noqa: E402
import languages        # noqa: E402
import latexdraw        # noqa: E402
import latexthemes      # noqa: E402
import prefs            # noqa: E402
import prompts          # noqa: E402
import speechconfig     # noqa: E402
import store            # noqa: E402
import syncexchange     # noqa: E402
import syncid           # noqa: E402
import synclock         # noqa: E402
import synclog          # noqa: E402
import synctouch        # noqa: E402
import syncunits        # noqa: E402

_FILES = ((prefs, "STORE", "config/prefs.json"), (prompts, "STORE", "config/prompts.json"),
          (latexthemes, "STORE", "config/latex.json"), (analysisconfig, "STORE", "config/analysis.json"),
          (speechconfig, "CONFIG", "config/speech.json"), (languages, "PERSONAL", "config/languages.json"),
          (langprompts, "LANG_FILES", "lib/lang"), (langprompts, "LANG_DOCS", "docs/lang"),
          (langprompts, "STARTERS", "markdown/exlex/starters"),
          (clips, "DIR", "clips"), (store, "LIB", "markdown/library"), (decks, "DIR", "exercises"),
          (decks, "CLIPS_DIR", "clips"), (store, "CLIPS_DIR", "clips"),
          (latexdraw, "DRAWN", "markdown/latex"))
_SHELVES = (("books", "books"), ("videos", "youtube/videos"), ("anki", "youtube/anki"),
            ("library", "markdown/library"), ("exercises", "exercises"), ("clips", "clips"))


class Unreachable(Exception):
    pass


class Refused(Exception):
    def __init__(self, reason=""):
        super().__init__(reason)
        self.reason = reason


class Install:
    def __init__(self, world, name):
        self.world, self.name = world, name
        self.root = tempfile.mkdtemp(prefix="parseh-sync-%s-" % name.lower())
        for _, rel in _SHELVES:
            os.makedirs(self.p(rel), exist_ok=True)
        os.makedirs(self.p("config"), exist_ok=True)
        self.id = None

    def p(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def w(self, rel, data="x"):
        p = self.p(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return p

    def read(self, rel):
        with open(self.p(rel), "rb") as fh:
            return fh.read()

    def apply(self):
        for mod, attr, rel in _FILES:
            cur = getattr(mod, attr)
            setattr(mod, attr, Path(self.p(rel)) if isinstance(cur, Path) else self.p(rel))
        for k, rel in _SHELVES:
            syncunits.SHELVES[k] = self.p(rel)
        synclog.HOME = None
        synctouch.drain()          # a touch is a hint; the exchange always scans


class World:
    """with World("A", "B") as w: w.A, w.B are installs; with w.on(w.A): ..."""

    def __init__(self, *names):
        self.names = names or ("A", "B")
        self.fail = None           # fail(caller, target, op, payload) may raise Unreachable
        self.calls = []            # (caller name, target name, op)
        self.reachable = {}
        self._stack = []
        self._lock = threading.RLock()

    # -- the fake transport
    def _modules(self):
        peer = types.ModuleType("syncpeer")
        peer.Unreachable, peer.Refused = Unreachable, Refused
        peer.call = self.call
        peer.partners = self.partners
        routes = types.ModuleType("syncroutes")
        routes.ROUTES = {}
        routes.register = lambda op, handler: routes.ROUTES.__setitem__(op, handler)
        return peer, routes

    def __enter__(self):
        self._was_mods = {n: sys.modules.get(n) for n in ("syncpeer", "syncroutes")}
        self.peer, self.routes = self._modules()
        sys.modules["syncpeer"], sys.modules["syncroutes"] = self.peer, self.routes
        self._was = [(mod, attr, getattr(mod, attr)) for mod, attr, _ in _FILES]
        self._was_shelves = dict(syncunits.SHELVES)
        self._was_home = synclog.HOME
        self._was_chunk = syncexchange.CHUNK
        syncexchange.register()
        self.installs = []
        for n in self.names:
            inst = Install(self, n)
            setattr(self, n, inst)
            self.installs.append(inst)
            with self.on(inst):
                inst.id = syncid.install_id()
            self.reachable[inst.id] = True
        return self

    def __exit__(self, *exc):
        syncexchange.stop()
        synclog.close()
        syncexchange.close()
        for mod, attr, v in self._was:
            setattr(mod, attr, v)
        syncunits.SHELVES.clear()
        syncunits.SHELVES.update(self._was_shelves)
        synclog.HOME = self._was_home
        syncexchange.CHUNK = self._was_chunk
        syncexchange._PLOCKS.clear()
        syncexchange._STATUS.clear()
        syncexchange._INDEX.update(key=None, map=None)
        with synclock._LOCK:
            synclock._LEASES.clear()
            synclock._WRITING.clear()
        synctouch.drain()
        for n, m in self._was_mods.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m
        for inst in self.installs:
            shutil.rmtree(inst.root, ignore_errors=True)
        return False

    @contextlib.contextmanager
    def on(self, inst):
        with self._lock:
            self._stack.append(inst)
            inst.apply()
            try:
                yield inst
            finally:
                self._stack.pop()
                if self._stack:
                    self._stack[-1].apply()

    def by_id(self, pid):
        for inst in self.installs:
            if inst.id == pid:
                return inst
        raise Refused("not a partner")

    def call(self, partner_id, op, payload, *, body=None, timeout=30.0):
        caller = self._stack[-1]
        target = self.by_id(partner_id)
        if not self.reachable.get(partner_id, True):
            raise Unreachable("nothing answered")
        if self.fail is not None:
            self.fail(caller, target, op, payload)
        self.calls.append((caller.name, target.name, op))
        handler = self.routes.ROUTES.get(op)
        if handler is None:
            raise Refused("no such operation")
        payload = json.loads(json.dumps(payload))
        with self.on(target):
            got, data = handler(caller.id, payload, body)
        return json.loads(json.dumps(got)), data

    def partners(self):
        me = self._stack[-1]
        return [{"id": i.id, "name": i.name, "last_seen": None, "reachable": self.reachable.get(i.id, True)}
                for i in self.installs if i is not me]
