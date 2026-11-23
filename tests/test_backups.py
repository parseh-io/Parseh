# SPDX-License-Identifier: GPL-3.0-or-later
"""The backups of a0.6.3 (TO-DO §13.19): config/ backed up and merged back (lib/configbackup.py), the backup of
everything (lib/wholebackup.py), the day of each backup (lib/backupdays.py).

    python3 -m unittest tests.test_backups

Every store is pointed at a temporary folder for the length of each test; nothing here reads or writes the
checkout's config/.
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in ("lib", "youtube/lib"):
    if str(ROOT / p) not in sys.path:
        sys.path.insert(0, str(ROOT / p))
import analysisconfig   # noqa: E402
import backupdays       # noqa: E402
import configbackup     # noqa: E402
import langprompts      # noqa: E402
import languages        # noqa: E402
import later            # noqa: E402
import latexthemes      # noqa: E402
import prefs            # noqa: E402
import prompts          # noqa: E402
import scratch          # noqa: E402
import shelf            # noqa: E402
import speechconfig     # noqa: E402
import wholebackup      # noqa: E402

READER = "/books/english/mini-en/reader/"
FLAG = "later:book:%s:1.1-abc123:2:x9" % READER
GONE = "later:book:%s:1.2-def456:1:y7" % READER


class Tree(unittest.TestCase):
    """Every store of config/, and the language files, in a temporary folder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="parseh-test-backups-"))
        self.cfg = self.tmp / "config"
        self.lang = self.tmp / "lang"
        for d in (self.cfg, self.lang, self.tmp / "docs", self.tmp / "starters"):
            d.mkdir(parents=True)
        self.patches = [
            mock.patch.object(prefs, "STORE", str(self.cfg / "prefs.json")),
            mock.patch.object(prompts, "STORE", str(self.cfg / "prompts.json")),
            mock.patch.object(languages, "PERSONAL", str(self.cfg / "languages.json")),
            mock.patch.object(latexthemes, "STORE", str(self.cfg / "latex.json")),
            mock.patch.object(analysisconfig, "STORE", str(self.cfg / "analysis.json")),
            mock.patch.object(speechconfig, "CONFIG", self.cfg / "speech.json"),
            mock.patch.object(langprompts, "LANG_FILES", str(self.lang)),
            mock.patch.object(langprompts, "LANG_DOCS", str(self.tmp / "docs")),
            mock.patch.object(langprompts, "STARTERS", str(self.tmp / "starters")),
            mock.patch.object(languages, "write_css", lambda path=None: None)]
        for p in self.patches:
            p.start()
        self.addCleanup(self._down)

    def _down(self):
        for p in reversed(self.patches):
            p.stop()
        languages.reload()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def seed(self):
        now = time.time()
        prefs.set_settings({"bk_rate": {"v": "1.25", "at": now - 500},
                            "bk_lvl:fa:vocal": {"v": "Mine", "at": now - 500}})
        prefs.set_place(READER, 4, "1.4", at=now - 500)
        later.apply_ops([{"op": "add", "record": {"id": FLAG, "kind": "book", "ref": READER, "text": "the clock",
                                                  "at": now - 500}},
                         {"op": "add", "record": {"id": GONE, "kind": "book", "ref": READER, "text": "the bell",
                                                  "at": now - 400}}])
        self.prompt = prompts.save({"surface": "ask", "name": "brief", "text": "Answer in one line."})
        row = dict(json.loads((ROOT / "lib" / "languages.json").read_text(encoding="utf-8"))["it"],
                   name="Basque", native="Euskara", folder="basque", tag="eu")
        languages.write_store({"eu": row})
        (self.lang / "eu.tex").write_text("% Basque\n", encoding="utf-8")
        latexthemes.save(dict(latexthemes.find("default"), name="mine", preamble="% mine"))
        analysisconfig.save({"lookup": "show"})
        speechconfig.save({"second_pass": False})

    def backup(self):
        path, _name = configbackup.pack()
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        with open(path, "rb") as f:
            return f.read()

    def wipe(self):
        shutil.rmtree(self.cfg)
        self.cfg.mkdir()
        for p in self.lang.iterdir():
            p.unlink()
        languages.reload()


class SettingsRoundTrip(Tree):
    def test_back_up_wipe_load_gives_everything_back(self):
        self.seed()
        data = self.backup()
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        for n in ("config/prefs.json", "config/prompts.json", "config/languages.json", "config/latex.json",
                  "config/analysis.json", "config/speech.json", "lang/eu.tex", configbackup.MANIFEST):
            self.assertIn(n, names)
        before = (prefs._read(), prompts.all_of(), languages.read_store())
        self.wipe()
        got = configbackup.read(data)
        out = configbackup.apply(got)
        self.assertEqual(set(out["wrote"]), set(configbackup.NAMES))
        self.assertEqual(prefs._read(), before[0])
        self.assertEqual([p["text"] for p in prompts.all_of()], [p["text"] for p in before[1]])
        self.assertEqual(languages.read_store(), before[2])
        self.assertTrue((self.lang / "eu.tex").is_file())
        self.assertIsNotNone(languages.by_folder("basque"), "a language loaded is known at once")
        self.assertEqual(latexthemes.find("mine")["preamble"], "% mine")
        self.assertEqual(analysisconfig.load()["lookup"], "show")
        self.assertFalse(speechconfig.load()["second_pass"])

    def test_the_left_out_stores_are_never_in_it(self):
        self.seed()
        (self.cfg / "network.json").write_text('{"devices": {"x": {"token": "secret"}}}', encoding="utf-8")
        with mock.patch.object(configbackup, "STORES", configbackup.STORES):
            data = self.backup()
        self.assertNotIn(b"secret", data)
        self.assertFalse(any("network" in n for n in zipfile.ZipFile(io.BytesIO(data)).namelist()))

    def test_loading_twice_changes_nothing_the_second_time(self):
        self.seed()
        got = configbackup.read(self.backup())
        out = configbackup.apply(got)
        self.assertEqual(out["wrote"], [])
        self.assertTrue(all(not s["rows"] for s in out["stores"]))


class MergeRules(Tree):
    def test_reading_places_and_settings_keep_the_later(self):
        self.seed()
        got = configbackup.read(self.backup())
        now = time.time()
        prefs.set_place(READER, 9, "3.1", at=now)                              # newer here
        prefs.set_place("/books/english/other/reader/", 2, "1.2", at=now)      # only here
        prefs.set_settings({"bk_rate": {"v": "2", "at": now - 900}})           # older here: refused by the store
        doc = prefs._read()
        doc["settings"]["bk_rate"] = {"v": "2", "at": now - 900, "by": ""}       # older than the backup's, set by hand
        prefs._write(doc)
        rows = {r["id"]: r for s in configbackup.plan(got)["stores"] for r in s["rows"]}
        self.assertEqual(rows["prefs.json:place:" + READER]["will"], "mine")
        self.assertEqual(rows["prefs.json:setting:bk_rate"]["will"], "backup")
        configbackup.apply(got)
        self.assertEqual(prefs.place(READER)["i"], 9, "the newer place stays")
        self.assertEqual(prefs.settings()["bk_rate"]["v"], "1.25", "the backup's later setting wins")
        self.assertIn("/books/english/other/reader/", prefs.places(), "what only this computer has stays")

    def test_flags_union_with_tombstones_respected_both_ways(self):
        self.seed()
        got = configbackup.read(self.backup())
        now = time.time()
        later.apply_ops([{"op": "remove", "id": GONE, "at": now}])           # removed here after the backup
        # and the backup removes one this computer flagged before the removal
        doc = got.stores["prefs.json"]
        doc["later"]["items"][FLAG] = {"gone": now - 100, "kind": "book", "ref": READER}
        prefs_doc = prefs._read()
        prefs_doc["later"]["items"][FLAG]["at"] = now - 200
        prefs._write(prefs_doc)
        new = "later:book:%s:2.1-fedcba:1:z1" % READER
        doc["later"]["items"][new] = {"kind": "book", "ref": READER, "text": "new one", "at": now - 50}
        configbackup.apply(got)
        live = {e["id"] for e in later.all_of()}
        self.assertNotIn(GONE, live, "removed here after the backup's flag: stays removed")
        self.assertNotIn(FLAG, live, "the backup removed it after it was flagged here: it goes")
        self.assertIn(new, live, "a flag only the backup has is added")

    def test_a_prompt_that_differs_is_the_person_s_choice(self):
        self.seed()
        got = configbackup.read(self.backup())
        prompts.save({"id": self.prompt["id"], "text": "Answer at length."})
        rid = "prompts.json:" + self.prompt["id"]
        plan = {r["id"]: r for s in configbackup.plan(got)["stores"] for r in s["rows"]}
        self.assertEqual(plan[rid]["will"], "choose")
        configbackup.apply(got)
        self.assertEqual(prompts.find(self.prompt["id"])["text"], "Answer at length.", "yours unless chosen")
        configbackup.apply(got, {rid: "backup"})
        self.assertEqual(prompts.find(self.prompt["id"])["text"], "Answer in one line.", "the backup's when chosen")

    def test_a_prompt_whose_name_is_taken_comes_in_renamed(self):
        self.seed()
        got = configbackup.read(self.backup())
        prompts.delete(self.prompt["id"])
        prompts.save({"surface": "ask", "name": "brief", "text": "Another of mine."})
        configbackup.apply(got)
        names = sorted(p["name"] for p in prompts.all_of())
        self.assertEqual(names, ["brief", "brief (2)"])

    def test_a_theme_and_a_language_that_differ_are_chosen(self):
        self.seed()
        got = configbackup.read(self.backup())
        latexthemes.save(dict(latexthemes.find("mine"), preamble="% changed here"), was="mine")
        (self.lang / "eu.tex").write_text("% changed here\n", encoding="utf-8")
        configbackup.apply(got)
        self.assertEqual(latexthemes.find("mine")["preamble"], "% changed here")
        self.assertEqual((self.lang / "eu.tex").read_text(encoding="utf-8"), "% changed here\n")
        configbackup.apply(got, {"latex.json:theme:mine": "backup", "languages.json:eu": "backup"})
        self.assertEqual(latexthemes.find("mine")["preamble"], "% mine")
        self.assertEqual((self.lang / "eu.tex").read_text(encoding="utf-8"), "% Basque\n")

    def test_a_language_parseh_now_ships_is_left_out(self):
        self.seed()
        got = configbackup.read(self.backup())
        got.stores["languages.json"]["it"] = got.stores["languages.json"]["eu"]
        rows = {r["id"]: r for s in configbackup.plan(got)["stores"] for r in s["rows"]}
        self.assertEqual(rows["languages.json:it"]["state"], "left out")

    def test_a_damaged_store_here_is_set_aside_not_written_over(self):
        self.seed()
        got = configbackup.read(self.backup())
        (self.cfg / "prefs.json").write_text("{not json", encoding="utf-8")
        configbackup.apply(got)
        aside = [p.name for p in self.cfg.iterdir() if p.name.startswith("prefs.json.damaged-")]
        self.assertEqual(len(aside), 1, "the unreadable file is kept under a dated name")
        self.assertEqual(prefs.place(READER)["i"], 4, "and the backup's places are what the store now holds")


def _rezip(data, change):
    """A copy of a zip, with `change(name, bytes) -> bytes` applied to each member."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zi, zipfile.ZipFile(out, "w") as zo:
        for i in zi.infolist():
            zo.writestr(i.filename, change(i.filename, zi.read(i)))
    return out.getvalue()


class Refusals(Tree):
    def test_a_damaged_file_refuses_the_whole_backup(self):
        self.seed()
        bad = _rezip(self.backup(), lambda n, b: b + b" " if n == "config/prompts.json" else b)
        with self.assertRaisesRegex(configbackup.BackupError, "config/prompts.json.*damaged"):
            configbackup.read(bad)

    def test_a_store_that_does_not_parse_is_refused_even_with_its_hash(self):
        self.seed()

        def change(n, b):
            if n == configbackup.MANIFEST:
                m = json.loads(b)
                m["files"]["config/latex.json"]["sha256"] = hashlib.sha256(b"{oops").hexdigest()
                return json.dumps(m).encode()
            return b"{oops" if n == "config/latex.json" else b
        with self.assertRaisesRegex(configbackup.BackupError, "latex.json.*not readable"):
            configbackup.read(_rezip(self.backup(), change))

    def test_a_newer_parseh_s_backup_is_refused_plainly(self):
        self.seed()

        def newer(n, b):
            if n == configbackup.MANIFEST:
                return json.dumps(dict(json.loads(b), format="parseh-config/9")).encode()
            return b
        with self.assertRaisesRegex(configbackup.BackupError, "newer Parseh"):
            configbackup.read(_rezip(self.backup(), newer))

    def test_a_store_from_a_newer_parseh_is_refused(self):
        self.seed()

        def change(n, b):
            if n == "config/prompts.json":
                b = json.dumps(dict(json.loads(b), format=7)).encode()
            if n == configbackup.MANIFEST:
                m = json.loads(b)
                return m
            return b
        data = self.backup()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            m = json.loads(zf.read(configbackup.MANIFEST))
            p = json.dumps(dict(json.loads(zf.read("config/prompts.json")), format=7)).encode()
        m["files"]["config/prompts.json"]["sha256"] = hashlib.sha256(p).hexdigest()
        bad = _rezip(data, lambda n, b: p if n == "config/prompts.json"
                     else json.dumps(m).encode() if n == configbackup.MANIFEST else b)
        with self.assertRaisesRegex(configbackup.BackupError, "prompts.json.*newer Parseh"):
            configbackup.read(bad)

    def test_not_a_backup(self):
        with self.assertRaisesRegex(configbackup.BackupError, "not a zip"):
            configbackup.read(b"hello")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("x.txt", "x")
        with self.assertRaisesRegex(configbackup.BackupError, "no parseh-config.json"):
            configbackup.read(buf.getvalue())


class Days(Tree):
    def test_marked_and_said(self):
        self.assertEqual(backupdays.view()["book"]["said"], "never")
        backupdays.mark("decks")
        v = backupdays.view()
        self.assertEqual(v["decks"]["said"], "today")
        self.assertIsNone(v["book"]["at"])
        backupdays.mark("everything")
        self.assertTrue(all(backupdays.days()[s] for s in backupdays.SHELVES))
        self.assertEqual(Path(backupdays.store()).parent, self.cfg, "kept beside prefs.json, wherever that is")

    def test_words(self):
        now = time.mktime((2026, 11, 23, 12, 0, 0, 0, 0, -1))
        self.assertEqual(backupdays.said(now - 3600, now), "today")
        self.assertEqual(backupdays.said(now - 86400, now), "yesterday")
        self.assertEqual(backupdays.said(now - 5 * 86400, now), "5 days ago")
        self.assertIn("2026", backupdays.said(now - 90 * 86400, now))

    def test_a_damaged_file_is_set_aside(self):
        Path(backupdays.store()).write_text("[", encoding="utf-8")
        backupdays.mark("book")
        self.assertTrue(any(p.name.startswith("backups.json.damaged-") for p in self.cfg.iterdir()))
        self.assertTrue(backupdays.days()["book"])


class Everything(Tree):
    """The backup of everything, through doors that are folders of a temporary tree."""

    def setUp(self):
        super().setUp()
        self.anki, self.clips = self.tmp / "anki", self.tmp / "clips"
        self.order = []
        self.shelves = {p: self.tmp / ("shelf-" + p) for p in wholebackup.PARTS[1:]}
        for d in self.shelves.values():
            d.mkdir()

        def packer(part):
            def pack():
                files = sorted(self.shelves[part].iterdir())
                if not files:
                    return None
                fd, path = tempfile.mkstemp(dir=self.tmp, suffix=".zip")
                os.close(fd)
                with zipfile.ZipFile(path, "w") as zf:
                    for f in files:
                        zf.write(f, f.name)
                return path, part + ".zip"
            return pack

        def restorer(part):
            def restore(path, replace):
                self.order.append((part, languages.by_folder("basque") is not None))
                got, kept = [], []
                with zipfile.ZipFile(path) as zf:
                    for n in zf.namelist():
                        dest = self.shelves[part] / n
                        if dest.exists() and not replace:
                            kept.append(n)
                            continue
                        dest.write_bytes(zf.read(n))
                        got.append(n)
                return {"restored": got, "kept": kept, "warnings": []}
            return restore
        self.env = wholebackup.Env({p: packer(p) for p in self.shelves}, {p: restorer(p) for p in self.shelves},
                                   str(self.anki), str(self.clips))

    def fill(self):
        self.seed()
        for p, d in self.shelves.items():
            (d / ("one-" + p)).write_text(p, encoding="utf-8")
        deck = self.anki / "english" / "market"
        (deck / "cards").mkdir(parents=True)
        (deck / "deck.json").write_text('{"name": "Market"}', encoding="utf-8")
        (deck / "cards" / "c1.json").write_text("{}", encoding="utf-8")
        (self.anki / "notetypes.json").write_text("{}", encoding="utf-8")
        (self.anki / "build").mkdir()
        (self.anki / "build" / "x.apkg").write_bytes(b"x")
        (self.anki / ".staging-crash").mkdir()
        self.clips.mkdir()
        (self.clips / "hello-abc123.png").write_bytes(b"png")
        (self.clips / "hello-abc123.png.json").write_text("{}", encoding="utf-8")

    def pack(self):
        path, name, notes = wholebackup.pack(self.env, "a0.6.3")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        self.assertEqual(notes, [])
        return path

    def wipe_all(self):
        self.wipe()
        for d in list(self.shelves.values()) + [self.anki, self.clips]:
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir()

    def test_round_trip_in_order(self):
        self.fill()
        path = self.pack()
        names = zipfile.ZipFile(path).namelist()
        self.assertIn("cards/english/market/deck.json", names)
        self.assertNotIn("cards/build/x.apkg", names)
        self.assertFalse(any(".staging" in n for n in names))
        self.wipe_all()
        out = wholebackup.load(path, self.env)
        self.assertEqual([p["part"] for p in out["parts"]],
                         ["settings", "books", "videos", "studio", "decks", "cards", "clips"])
        self.assertTrue(all(known for _p, known in self.order),
                        "the settings go back first: the person's language is known to every shelf after")
        for p, d in self.shelves.items():
            self.assertEqual((d / ("one-" + p)).read_text(encoding="utf-8"), p)
        self.assertTrue((self.anki / "english" / "market" / "cards" / "c1.json").is_file())
        self.assertTrue((self.clips / "hello-abc123.png").is_file())
        self.assertEqual(prefs.place(READER)["i"], 4)
        self.assertIsNotNone(out["token"])

    def test_what_is_here_is_kept_unless_replace(self):
        self.fill()
        path = self.pack()
        (self.anki / "english" / "market" / "deck.json").write_text('{"name": "Mine"}', encoding="utf-8")
        (self.anki / "notetypes.json").write_text('{"mine": 1}', encoding="utf-8")
        out = {p["part"]: p for p in wholebackup.load(path, self.env)["parts"]}
        self.assertEqual(sorted(out["cards"]["kept"]), ["english/market", "notetypes.json"])
        self.assertEqual(out["clips"]["kept"], ["hello-abc123.png"])
        self.assertIn('"Mine"', (self.anki / "english" / "market" / "deck.json").read_text(encoding="utf-8"))
        out = {p["part"]: p for p in wholebackup.load(path, self.env, replace=True)["parts"]}
        self.assertEqual(sorted(out["cards"]["restored"]), ["english/market", "notetypes.json"])
        self.assertIn('"Market"', (self.anki / "english" / "market" / "deck.json").read_text(encoding="utf-8"))

    def test_a_damaged_member_refuses_the_whole_and_writes_nothing(self):
        self.fill()
        path = self.pack()
        with open(path, "rb") as f:
            bad = _rezip(f.read(), lambda n, b: b + b"!" if n == "clips/hello-abc123.png" else b)
        badpath = self.tmp / "bad.zip"
        badpath.write_bytes(bad)
        self.wipe_all()
        with self.assertRaisesRegex(wholebackup.BackupError, "clips/hello-abc123.png.*damaged"):
            wholebackup.load(str(badpath), self.env)
        self.assertEqual(self.order, [])
        self.assertEqual(list(self.cfg.iterdir()), [])
        self.assertEqual(list(self.anki.iterdir()), [])

    def test_a_name_that_climbs_out_is_refused(self):
        self.fill()
        path = self.pack()
        with open(path, "rb") as f:
            data = f.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            m = json.loads(zf.read(wholebackup.MANIFEST))
        m["files"]["cards/../evil.txt"] = {"sha256": hashlib.sha256(b"x").hexdigest(), "size": 1}
        out = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as zi, zipfile.ZipFile(out, "w") as zo:
            for i in zi.infolist():
                zo.writestr(i.filename, json.dumps(m) if i.filename == wholebackup.MANIFEST else zi.read(i))
            zo.writestr("cards/../evil.txt", "x")
        bad = self.tmp / "climb.zip"
        bad.write_bytes(out.getvalue())
        with self.assertRaisesRegex(wholebackup.BackupError, "not something a backup of everything holds"):
            wholebackup.load(str(bad), self.env)
        self.assertFalse((self.tmp / "evil.txt").exists())

    def test_an_empty_shelf_is_named(self):
        self.seed()
        path = self.pack()
        with zipfile.ZipFile(path) as zf:
            m = json.loads(zf.read(wholebackup.MANIFEST))
        self.assertEqual(sorted(m["empty"]), sorted(["books", "videos", "studio", "decks", "cards", "clips"]))


class EverythingWithABook(Tree):
    """The backup of everything through the books' REAL shelf (lib/shelf.py): a book's recordings come back with it
    (TO-DO 6.16), and every temporary file is staged in the toolbox's .tmp/, never the system's temp folder."""

    def setUp(self):
        super().setUp()
        self.root = self.tmp / "root"
        book = self.root / "books" / "english" / "mini-en"
        shutil.copytree(ROOT / "tests" / "fixtures" / "books" / "english" / "mini-en", book)
        meta = json.loads((book / "book.json").read_text(encoding="utf-8"))
        meta["audio"] = "audio/voice.mp3"
        (book / "book.json").write_text(json.dumps(meta), encoding="utf-8")
        (book / "audio").mkdir()
        self.sound = b"ID3" + os.urandom(300000)
        (book / "audio" / "voice.mp3").write_bytes(self.sound)
        (book / "timings.json").write_text(json.dumps({"1.1": [0.0, 2.0]}), encoding="utf-8")
        self.book = book
        r = str(self.root)
        self.env = wholebackup.Env(
            {"books": lambda: shelf.pack("book", root=r) if shelf.items("book", r) else None,
             "videos": lambda: None, "studio": lambda: None, "decks": lambda: None},
            {"books": lambda path, replace: shelf.restore("book", path, replace=replace, root=r)},
            str(self.tmp / "anki"), str(self.tmp / "clips"))
        p = mock.patch.object(scratch, "ROOT", r)
        p.start()
        self.addCleanup(p.stop)

    def test_a_book_with_a_recording_survives_wipe_and_load(self):
        made = []
        real_stemp, real_dtemp = tempfile.mkstemp, tempfile.mkdtemp

        def stemp(*a, **k):
            made.append(k.get("dir"))
            return real_stemp(*a, **k)

        def dtemp(*a, **k):
            made.append(k.get("dir"))
            return real_dtemp(*a, **k)
        with mock.patch.object(tempfile, "mkstemp", stemp), mock.patch.object(tempfile, "mkdtemp", dtemp):
            path, _name, notes = wholebackup.pack(self.env, "a0.6.3")
            self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
            self.assertEqual(notes, [])
            self.assertEqual(os.path.dirname(path), str(self.root / ".tmp"))
            shutil.rmtree(self.root / "books")
            (self.root / "books").mkdir()
            out = wholebackup.load(path, self.env)
        books = next(p for p in out["parts"] if p["part"] == "books")
        self.assertEqual((books["restored"], books["warnings"]), (["mini-en"], []), out)
        self.assertEqual((self.book / "audio" / "voice.mp3").read_bytes(), self.sound)
        self.assertTrue((self.book / "timings.json").is_file())
        self.assertEqual(json.loads((self.book / "book.json").read_text(encoding="utf-8"))["audio"],
                         "audio/voice.mp3")
        inside = str(self.root.resolve()) + os.sep
        for d in made:
            self.assertIsNotNone(d, "a temporary file made in the system's temp folder")
            self.assertTrue((os.path.realpath(d) + os.sep).startswith(inside), d)
        self.assertEqual(sorted(os.listdir(self.root / ".tmp")), [os.path.basename(path)],
                         "nothing left in .tmp/ but the backup itself, which its caller deletes")


class TheServerMarksTheDay(unittest.TestCase):
    def test_which_address_is_which_backup(self):
        sys.path.insert(0, str(ROOT))
        import serve
        import ytpages
        self.assertEqual(serve.backup_shelf("/books/__backup"), "book")
        self.assertEqual(serve.backup_shelf(ytpages.BASE + "/api/backup"), "video")
        self.assertEqual(serve.backup_shelf("/studio/api/export"), "studio")
        self.assertEqual(serve.backup_shelf("/exercises/api/backup"), "decks")
        self.assertEqual(serve.backup_shelf("/settings/api/backups/everything"), "everything")
        # a book's notes have a studio of their own: its export is not the studio's backup
        self.assertIsNone(serve.backup_shelf("/books/english/x/notes/api/export"))


if __name__ == "__main__":
    unittest.main()
