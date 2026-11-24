# SPDX-License-Identifier: GPL-3.0-or-later
"""The rest of sync's foundations (docs/sync.md): identity, locks, the one-day store.

    python3 -m unittest tests/test_sync_foundations.py

  * IDENTITY (lib/syncid.py): made once, the same at the next call, a name
    that starts as the host's and that the person can change, a key pair whose
    fingerprint is the certificate's, made by openssl and by an injected
    minter (a phone's), an identity with no key when no way can make one,
    reset() a new id with the name kept; the private key readable by this
    user only; all of it in config/sync/ beside prefs.STORE.
  * LOCKS (lib/synclock.py): an editor's lease keeps sync out and sync's write
    keeps an editor out (Busy, with retry_after); a lease runs out; the last
    editor closing calls on_close; two units never wait for each other.
  * THE ONE-DAY STORE (lib/synckeep.py): a file unit and a setting kept,
    listed, put back (recorded as this computer's change), cleaned after a
    day and not before; the diff files written, listed, deleted only by name;
    a unified diff and a fields diff.
"""
import json
import os
import stat
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synctree import SyncTree   # noqa: E402
import syncid                   # noqa: E402
import synckeep                 # noqa: E402
import synclock                 # noqa: E402
import synclog                  # noqa: E402


class Identity(SyncTree):
    def tearDown(self):
        syncid.MINTER = None
        super().tearDown()

    def test_made_once_named_and_renamed(self):
        a = syncid.identity()
        self.assertRegex(a["install"], r"^[0-9a-f]{32}$")
        self.assertEqual(syncid.identity()["install"], a["install"])
        self.assertEqual(a["name"], syncid.default_name())
        self.assertEqual(a["protocol"], syncid.PROTOCOL)
        self.assertEqual(syncid.set_name("  Desk   upstairs "), "Desk upstairs")
        self.assertEqual(syncid.name(), "Desk upstairs")
        self.assertEqual(syncid.set_name(""), syncid.default_name())
        self.assertTrue(syncid.paths()["identity"].startswith(os.path.join(self.t, "config", "sync")))

    def test_key_pair_with_openssl(self):
        syncid.MINTER = syncid._mint_openssl
        doc = syncid.ensure()
        p = syncid.paths()
        self.assertEqual(doc["key"]["fingerprint"], syncid.fingerprint(p["cert"]))
        self.assertRegex(doc["key"]["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(stat.S_IMODE(os.stat(p["key"]).st_mode), 0o600)
        with open(p["cert"]) as fh:
            self.assertIn("BEGIN CERTIFICATE", fh.read())
        self.assertEqual(syncid.ensure()["key"], doc["key"])               # made once
        old = doc["install"]
        syncid.set_name("Kept")
        new = syncid.reset()
        self.assertNotEqual(new["install"], old)
        self.assertEqual(new["name"], "Kept")
        self.assertNotEqual(new["key"]["fingerprint"], doc["key"]["fingerprint"])

    def test_injected_minter_and_none_at_all(self):
        def phone(key_path, cert_path, cn):
            with open(key_path, "w") as fh:
                fh.write("KEY")
            with open(cert_path, "w") as fh:
                fh.write("-----BEGIN CERTIFICATE-----\nQUJD\n-----END CERTIFICATE-----\n")
        syncid.MINTER = phone
        doc = syncid.ensure()
        import hashlib
        self.assertEqual(doc["key"]["fingerprint"], hashlib.sha256(b"ABC").hexdigest())

        def broken(*a):
            raise RuntimeError("no way here")
        syncid.MINTER = broken
        os.unlink(syncid.paths()["key"])
        doc2 = syncid.reset()
        self.assertIsNone(doc2["key"])                                      # still an identity


class Locks(SyncTree):
    U = "doc:persian/d"

    def test_editor_and_sync_exclude_each_other(self):
        tok = synclock.open_editor(self.U, "studio")
        self.assertEqual(synclock.editing(self.U), ["studio"])
        with self.assertRaises(synclock.Busy) as cm:
            with synclock.sync_write(self.U):
                pass
        self.assertEqual(cm.exception.by, ["studio"])
        with synclock.sync_write("doc:persian/other"):                    # another unit: no wait
            pass
        closed = []
        synclock.on_close(closed.append)
        try:
            self.assertEqual(synclock.close_editor(tok), self.U)
            self.assertEqual(closed, [self.U])
            with synclock.sync_write(self.U):
                self.assertTrue(synclock.writing(self.U))
                with self.assertRaises(synclock.Busy) as cm:
                    synclock.open_editor(self.U, "studio")
                self.assertEqual(cm.exception.retry_after, synclock.RETRY)
            self.assertFalse(synclock.writing(self.U))
        finally:
            synclock._CLOSED.remove(closed.append)

    def test_lease_runs_out(self):
        tok = synclock.open_editor(self.U, "form", lease=0.05)
        self.assertTrue(synclock.keep(tok, lease=0.05))
        time.sleep(0.1)
        self.assertFalse(synclock.keep(tok))
        self.assertEqual(synclock.editing(self.U), [])
        with synclock.sync_write(self.U):
            pass

    def test_sync_write_holds_the_books_pathlock(self):
        import pathlock
        import threading
        os.makedirs(self.p("books/persian/b"))
        u = "book:persian/b"
        got = []
        with synclock.sync_write(u):
            t = threading.Thread(target=lambda: got.append(
                pathlock.lock(self.p("books/persian/b")).acquire(timeout=0.1)))
            t.start()
            t.join()
        self.assertEqual(got, [False])


class Keep(SyncTree):
    def test_file_unit_kept_put_back_and_cleaned(self):
        self.w("markdown/library/persian/d/source.md", "mine")
        self.w("markdown/library/persian/d/meta.json", "{}")
        synclog.scan()
        e = synckeep.keep("doc:persian/d", "incoming", partner="laptop")
        self.assertEqual(e["files"], ["meta.json", "source.md"])
        self.assertEqual(e["until"] - e["at"], synckeep.KEEP_FOR)
        self.w("markdown/library/persian/d/source.md", "theirs")
        self.w("markdown/library/persian/d/images/new.png", "x")
        self.assertEqual([x["id"] for x in synckeep.entries()], [e["id"]])
        synckeep.put_back(e["id"])
        with open(self.p("markdown/library/persian/d/source.md")) as fh:
            self.assertEqual(fh.read(), "mine")
        self.assertFalse(os.path.exists(self.p("markdown/library/persian/d/images/new.png")))
        row = synclog.get("doc:persian/d")
        self.assertEqual(row["hash"], e["hash"])                          # the same content again
        self.assertEqual(synckeep.clean(now=e["at"] + 3600), 0)           # not before a day
        self.assertEqual(synckeep.clean(now=e["at"] + synckeep.KEEP_FOR + 1), 1)
        self.assertEqual(synckeep.entries(), [])

    def test_setting_kept_and_put_back(self):
        self.wj("config/prefs.json", {"settings": {"parseh_theme": {"v": "dark", "at": 1, "by": "a"}}})
        e = synckeep.keep("setting:parseh_theme", "choice")
        self.wj("config/prefs.json", {"settings": {"parseh_theme": {"v": "light", "at": 2, "by": "b"}}})
        held = synclock.open_editor("setting:parseh_theme", "x")
        with self.assertRaises(synclock.Busy):
            synckeep.put_back(e["id"])
        synclock.close_editor(held)
        synckeep.put_back(e["id"])
        with open(self.p("config/prefs.json")) as fh:
            self.assertEqual(json.load(fh)["settings"]["parseh_theme"]["v"], "dark")
        self.assertIsNone(synckeep.keep("setting:bk_rate", "choice"))     # nothing to keep
        with self.assertRaises(ValueError):
            synckeep.keep("setting:parseh_theme", "because")
        with self.assertRaises(KeyError):
            synckeep.put_back("../../etc")

    def test_diffs(self):
        d = synckeep.text_diff("a\nb\n", "a\nc\n", "this computer", "laptop")
        self.assertEqual(d.splitlines()[:2], ["--- this computer", "+++ laptop"])
        self.assertIn("-b", d.splitlines())
        self.assertIn("+c", d.splitlines())
        self.assertEqual(synckeep.fields_diff({"a": 1, "b": {"c": 2}}, {"a": 1, "b": {"c": 3}, "d": 0}),
                         ["b.c: 2 → 3", "d: (none) → 0"])
        got = synckeep.write_diff("doc:persian/d", d)
        got2 = synckeep.write_diff("doc:persian/d", d, now=os.stat(got["path"]).st_mtime)
        self.assertTrue(got["name"].endswith("-doc-persian-d.diff"))
        self.assertEqual(sorted(x["name"] for x in synckeep.diffs()), sorted([got["name"], got2["name"]]))
        self.assertEqual(synckeep.clean(now=time.time() + 10 * 86400), 0)  # diffs are never cleaned
        self.assertTrue(synckeep.delete_diff(got["name"]))
        with self.assertRaises(KeyError):
            synckeep.delete_diff("../log.sqlite")
        self.assertEqual(len(synckeep.diffs()), 1)


if __name__ == "__main__":
    unittest.main()
