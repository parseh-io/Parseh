# SPDX-License-Identifier: GPL-3.0-or-later
"""A recording on an Anki card, with no note-type change.

    python3 -m unittest discover -s tests -p test_anki_audio.py

The card sheet cuts a clip into the tray (lib/clips.py) and sends the card
with `"clip": {"side", "name"}`.  What has to hold, from the store to Anki
and back (youtube/lib/anki_store.py, anki_export.py, import_apkg.py,
sync_apkg.py):

  * the store copies the clip to media/<id>-<side>-audio.<ext> and records
    it as snd_front / snd_back -- and refuses, writing nothing, a name the
    tray does not hold;
  * the note carries it as `[sound:<file>]` in FrontImage / BackImage, after
    the picture, and the field LIST is exactly what it was;
  * the .apkg packs the file: in the media map and as a numbered member,
    byte for byte;
  * the package comes back in (import_apkg) with snd_* restored and the file
    extracted, and a sync of an export from Anki keeps them, follows an edit
    made inside Anki, and does not take a card from before recordings for an
    edited one;
  * a picture or sound name in a note that is no bare file name (an absolute
    path, a climb out of media/) comes in as no media at all, and a build
    never reads it -- not even from a card an older import already wrote;
  * the dashboard's preview plays the clip straight from the tray.
"""
import base64
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "youtube" / "lib", ROOT / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import anki_export as ax  # noqa: E402
import anki_store         # noqa: E402
import clips              # noqa: E402
import import_apkg        # noqa: E402
import sync_apkg          # noqa: E402

# the bytes do not have to play for the store; they have to arrive intact
MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + bytes(range(256)) * 4
MP3_B = b"ID3\x04\x00\x00\x00\x00\x00\x00" + bytes(reversed(range(256))) * 3
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x01" * 200


def shot(side):
    return {"side": side, "data": "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()}


class Base(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)
        self.anki = str(self.tmp / "anki")
        os.makedirs(self.anki)
        was = clips.DIR
        clips.set_dir(self.tmp / "clips")
        self.addCleanup(clips.set_dir, was)
        os.makedirs(clips.DIR)
        self.front = self.put("clock-a1b2c3.mp3", MP3)
        self.back = self.put("wind-d4e5f6.mp3", MP3_B)

    def put(self, name, data):
        (Path(clips.DIR) / name).write_bytes(data)
        return name

    def card(self, **kw):
        c = {"lang": "en", "kind": "vocab", "fa": "clock", "tr": "klɒk", "en": "orologio",
             "context": "The clock struck one.", "tags": ["english-book"],
             "source": {"label": "The Clock and the Wind — 1.1", "url": ""}}
        c.update(kw)
        return c

    def add(self, deck="English::Clips", **body):
        cdir = os.path.join(self.anki, "english", "english-clips", "cards")
        had = set(os.listdir(cdir)) if os.path.isdir(cdir) else set()
        # the same front again and again, each time with other recordings: "add it again" (`force`), since a card
        # a deck already has is asked about first (TO-DO 10.7)
        res, status = anki_store.add_card(self.anki, dict({"deck": deck, "deck_lang": "en",
                                                           "card": self.card(), "force": True}, **body))
        self.assertEqual(status, 200, res)
        self.assertEqual(res["deck"]["path"], "english/english-clips")
        (made,) = set(os.listdir(cdir)) - had
        with open(os.path.join(cdir, made), encoding="utf-8") as f:
            return res, json.load(f)

    def deck_dir(self, res):
        return os.path.join(self.anki, res["deck"]["path"])


class AddCard(Base):
    def test_the_clip_is_copied_beside_the_card(self):
        res, card = self.add(clip={"side": "front", "name": self.front})
        media = os.path.join(self.deck_dir(res), "media")
        want = "%s-front-audio.mp3" % card["id"]
        self.assertEqual(card["snd_front"], want)
        self.assertIsNone(card["snd_back"])
        self.assertEqual(os.listdir(media), [want])
        self.assertEqual(Path(media, want).read_bytes(), MP3)
        self.assertTrue((Path(clips.DIR) / self.front).exists(), "copied, not moved out of the tray")
        self.assertFalse(want.startswith("_"), "a leading underscore is Anki's static media")

    def test_a_picture_and_a_recording_on_one_side_and_the_other(self):
        res, card = self.add(clip={"side": "back", "name": self.back}, shot=shot("back"))
        self.assertEqual((card["img_back"], card["snd_back"]),
                         ("%s-back.jpg" % card["id"], "%s-back-audio.mp3" % card["id"]))
        self.assertEqual((card["img_front"], card["snd_front"]), (None, None))
        fields = dict(zip(ax.MODELS[ax.model_for(card)]["fields"], ax.note_fields(card)))
        self.assertEqual(fields["BackImage"],
                         '<img src="%s-back.jpg">[sound:%s-back-audio.mp3]' % (card["id"], card["id"]))
        self.assertEqual(fields["FrontImage"], "")

    def test_a_card_without_a_clip_is_what_it_always_was(self):
        res, card = self.add()
        self.assertEqual((card["snd_front"], card["snd_back"]), (None, None))
        self.assertEqual(os.listdir(os.path.join(self.deck_dir(res), "media")), [])
        legacy = {k: v for k, v in card.items() if not k.startswith("snd_")}
        self.assertEqual(ax.note_fields(legacy), ax.note_fields(card))

    def test_refusals_write_nothing(self):
        for clip, why in (({"side": "front", "name": "gone-000000.mp3"}, "no longer in the clip tray"),
                          ({"side": "front", "name": "../../serve.py"}, "must be a clip"),
                          ({"side": "back", "name": "frame-abcdef.png"}, "must be a clip")):
            with self.subTest(clip["name"]):
                res, status = anki_store.add_card(self.anki, {"deck": "English::Clips", "deck_lang": "en",
                                                              "card": self.card(), "clip": clip})
                self.assertEqual(status, 400)
                self.assertFalse(res["ok"])
                self.assertIn(why, res["error"])
        self.assertEqual(os.listdir(self.anki), [], "not even a deck directory")

    def test_the_route_passes_the_clip_through(self):
        import ytpages

        class H:
            def __init__(self, body):
                self._raw = json.dumps(body).encode("utf-8")
                self.sent = []

            def send_json(self, obj, code=200):
                self.sent.append((code, obj))

        was = ytpages.ANKI
        ytpages.ANKI = self.anki
        try:
            h = H({"deck": "English::Clips", "deck_lang": "en", "card": self.card(),
                   "clip": {"side": "front", "name": self.front}})
            ytpages.anki_add_card(h)
            self.assertEqual(h.sent[-1][0], 200, h.sent)
            h = H({"card": self.card(), "clip": {"side": "back", "name": self.back}})
            ytpages.anki_preview(h)
            code, obj = h.sent[-1]
            self.assertEqual(code, 200)
            self.assertIn('<audio controls src="/clips/media/%s"></audio>' % self.back, obj["html"])
        finally:
            ytpages.ANKI = was
        (card,) = ax.load_cards(os.path.join(self.anki, "english", "english-clips"))
        self.assertTrue(card["snd_front"].endswith("-front-audio.mp3"))


class Preview(Base):
    def test_the_clip_plays_from_the_tray(self):
        out, status = anki_store.preview({"card": self.card(), "clip": {"side": "front", "name": self.front},
                                          "shot": shot("front")}, self.anki)
        self.assertEqual(status, 200)
        html = out["html"]
        tag = '<audio controls src="/clips/media/%s"></audio>' % self.front
        self.assertIn(tag, html)
        self.assertNotIn("[sound:", html, "no tag is left for the reader to see")
        self.assertIn('<img src="data:image/jpeg;base64,', html)
        # both directions of a bidirectional card show the front side's media
        self.assertEqual(html.count(tag), 2)

    def test_a_clip_that_is_not_there_previews_without_it(self):
        out, status = anki_store.preview({"card": self.card(), "clip": {"side": "front", "name": "x-000000.mp3"}},
                                         self.anki)
        self.assertEqual(status, 200)
        self.assertNotIn("<audio", out["html"])

    def test_a_stored_card_previews_its_own_file(self):
        res, card = self.add(clip={"side": "back", "name": self.back})
        html = ax.preview_html(card)
        self.assertIn('<audio controls src="%s-back-audio.mp3"></audio>' % card["id"], html)


class BuildImportSync(Base):
    def setUp(self):
        super().setUp()
        self.res, self.c1 = self.add(clip={"side": "front", "name": self.front}, shot=shot("front"))
        _, self.c2 = self.add(clip={"side": "back", "name": self.back})
        _, self.c3 = self.add()
        self.deck = self.deck_dir(self.res)
        self.apkg = str(self.tmp / "clips.apkg")
        ax.build_deck(self.deck, self.apkg)

    def package(self, path=None):
        with zipfile.ZipFile(path or self.apkg) as z:
            media = json.loads(z.read("media").decode("utf-8"))
            members = {m: z.read(m) for m in z.namelist()}
        return media, members

    def notes(self, path=None):
        with zipfile.ZipFile(path or self.apkg) as z:
            db = self.tmp / "peek.anki2"
            db.write_bytes(z.read("collection.anki2"))
        con = sqlite3.connect(str(db))
        try:
            return {guid: flds.split("\x1f") for guid, flds in con.execute("select guid, flds from notes")}
        finally:
            con.close()
            db.unlink()

    def test_the_package_carries_the_recordings(self):
        media, members = self.package()
        by_name = {name: num for num, name in media.items()}
        for card, side, data in ((self.c1, "front", MP3), (self.c2, "back", MP3_B)):
            fn = card["snd_" + side]
            self.assertIn(fn, by_name, "in the media map")
            self.assertEqual(members[by_name[fn]], data, "and the numbered member is its bytes")
        self.assertEqual(members[by_name[self.c1["img_front"]]], JPEG)
        self.assertEqual(len(media), 3, "two recordings and a picture: no font for English")
        self.assertEqual(sorted(members), sorted(["collection.anki2", "media"] + list(media)))
        names = ax.MODELS[ax.model_for(self.c1)]["fields"]
        notes = self.notes()
        f1 = dict(zip(names, notes[self.c1["guid"]]))
        self.assertEqual(f1["FrontImage"], '<img src="%s">[sound:%s]' % (self.c1["img_front"], self.c1["snd_front"]))
        self.assertEqual(f1["BackImage"], "")
        f2 = dict(zip(names, notes[self.c2["guid"]]))
        self.assertEqual((f2["FrontImage"], f2["BackImage"]), ("", "[sound:%s]" % self.c2["snd_back"]))
        self.assertTrue(all(len(v) == len(names) for v in notes.values()), "the field list did not grow")

    def test_a_recording_gone_from_media_is_dropped_quietly(self):
        os.remove(os.path.join(self.deck, "media", self.c2["snd_back"]))
        out = ax.build_deck(self.deck, str(self.tmp / "again.apkg"))
        media, _ = self.package(out)
        self.assertNotIn(self.c2["snd_back"], media.values())
        names = ax.MODELS[ax.model_for(self.c2)]["fields"]
        self.assertEqual(dict(zip(names, self.notes(out)[self.c2["guid"]]))["BackImage"], "")

    def test_the_package_comes_back_in_with_its_recordings(self):
        other = str(self.tmp / "other-anki")
        os.makedirs(other)
        res = import_apkg.import_all(self.apkg, other)
        self.assertEqual(res["media"]["missing"], [])
        self.assertEqual(res["media"]["copied"], 3)
        (deck,) = res["decks"]
        ddir = os.path.join(other, deck["path"])
        back = {c["guid"]: c for c in ax.load_cards(ddir)}
        for card, side, data in ((self.c1, "front", MP3), (self.c2, "back", MP3_B)):
            got = back[card["guid"]]
            self.assertEqual(got["snd_" + side], card["snd_" + side])
            self.assertIsNone(got["snd_" + ("back" if side == "front" else "front")])
            self.assertEqual(Path(ddir, "media", card["snd_" + side]).read_bytes(), data)
            self.assertNotEqual(got.get("anki"), "owned", "a sound tag is not formatting the store cannot hold")
        self.assertEqual(back[self.c1["guid"]]["img_front"], self.c1["img_front"])
        self.assertEqual((back[self.c3["guid"]]["snd_front"], back[self.c3["guid"]]["snd_back"]), (None, None))
        # built again from what came in, the notes are the same notes
        rebuilt = ax.build_deck(ddir, str(self.tmp / "rebuilt.apkg"))
        self.assertEqual(self.notes(rebuilt), self.notes())

    def anki_export(self, edit=None, add_media=None):
        """The package as Anki would export it: no build stamp, the notes
        (optionally) edited inside Anki, the media it holds."""
        out = str(self.tmp / "exported.apkg")
        work = self.tmp / "work"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir()
        with zipfile.ZipFile(self.apkg) as z:
            z.extractall(work)
        con = sqlite3.connect(str(work / "collection.anki2"))
        (conf,) = con.execute("select conf from col").fetchone()
        conf = json.loads(conf)
        conf.pop("frankStoreBuild")
        con.execute("update col set conf=?", (json.dumps(conf),))
        for guid, flds in (edit or {}).items():
            con.execute("update notes set flds=? where guid=?", ("\x1f".join(flds), guid))
        con.commit()
        con.close()
        media = json.loads((work / "media").read_text())
        for name, data in (add_media or {}).items():
            num = str(len(media))
            media[num] = name
            (work / num).write_bytes(data)
        (work / "media").write_text(json.dumps(media))
        with zipfile.ZipFile(out, "w") as z:
            z.write(work / "collection.anki2", "collection.anki2")
            z.write(work / "media", "media")
            for num in media:
                z.write(work / num, num)
        return out

    def test_a_sync_keeps_them(self):
        # a card written before recordings existed carries no snd_* keys at all
        c3_path = os.path.join(self.deck, "cards", self.c3["id"] + ".json")
        legacy = {k: v for k, v in self.c3.items() if not k.startswith("snd_")}
        anki_store.write_json(c3_path, legacy)
        before = {fn: Path(self.deck, "cards", fn).read_bytes() for fn in os.listdir(os.path.join(self.deck, "cards"))}
        rep = sync_apkg.run_sync(self.anki_export(), self.anki, dry_run=False)
        (deck,) = rep["decks"]
        self.assertEqual(deck["unchanged"], 3, deck)
        self.assertEqual((deck["updated"], deck["kept"], deck["media_missing"]), ([], [], []))
        after = {fn: Path(self.deck, "cards", fn).read_bytes() for fn in os.listdir(os.path.join(self.deck, "cards"))}
        self.assertEqual(after, before, "not one card file rewritten")

    def test_a_sync_follows_an_edit_made_inside_anki(self):
        names = ax.MODELS[ax.model_for(self.c1)]["fields"]
        notes = self.notes()
        f1 = dict(zip(names, notes[self.c1["guid"]]))
        f1["FrontImage"] = '<img src="%s">[sound:recorded-in-anki.mp3]' % self.c1["img_front"]
        f2 = dict(zip(names, notes[self.c2["guid"]]))
        f2["BackImage"] = ""                    # the recording removed in Anki
        edited = self.anki_export(edit={self.c1["guid"]: [f1[n] for n in names],
                                        self.c2["guid"]: [f2[n] for n in names]},
                                  add_media={"recorded-in-anki.mp3": b"ID3 made in anki"})
        dry = sync_apkg.run_sync(edited, self.anki, dry_run=True)
        self.assertEqual(sorted(dry["decks"][0]["updated"]),
                         sorted([self.c1["id"] + ".json", self.c2["id"] + ".json"]))
        rep = sync_apkg.run_sync(edited, self.anki, dry_run=False)
        self.assertEqual(rep["decks"][0]["media_missing"], [])
        cards = {c["guid"]: c for c in ax.load_cards(self.deck)}
        self.assertEqual(cards[self.c1["guid"]]["snd_front"], "recorded-in-anki.mp3")
        self.assertEqual(cards[self.c1["guid"]]["img_front"], self.c1["img_front"])
        self.assertEqual(Path(self.deck, "media", "recorded-in-anki.mp3").read_bytes(), b"ID3 made in anki")
        self.assertIsNone(cards[self.c2["guid"]]["snd_back"])
        self.assertEqual(cards[self.c1["guid"]]["id"], self.c1["id"], "the same file, the same card")
        again = sync_apkg.run_sync(edited, self.anki, dry_run=False)
        self.assertEqual(again["decks"][0]["unchanged"], 3, "and a second run changes nothing")

    def test_a_media_name_that_leaves_media_is_never_read(self):
        # a package from anyone may name, in a picture or a sound tag, a file
        # anywhere on this machine; none of it may come in, be looked for, or
        # be packed into the deck built again from what came in
        secret = self.tmp / "secret.txt"
        secret.write_bytes(b"SECRET-OUTSIDE-THE-DECK")
        climb = "../../../../secret.txt"      # from <anki>/english/<deck>/media
        self.assertTrue(Path(self.deck, "media", climb).resolve().is_file(), "the climb does reach it")
        names = ax.MODELS[ax.model_for(self.c1)]["fields"]
        notes = self.notes()
        f1 = dict(zip(names, notes[self.c1["guid"]]))
        f1["FrontImage"] = '<img src="%s">[sound:%s]' % (secret, secret)
        f1["BackImage"] = '<img src="%s">[sound:%s]' % (climb, climb.replace("/", "&#47;"))
        f2 = dict(zip(names, notes[self.c2["guid"]]))
        f2["BackImage"] = "[sound:..\\..\\..\\..\\secret.txt]"
        evil = self.anki_export(edit={self.c1["guid"]: [f1[n] for n in names],
                                      self.c2["guid"]: [f2[n] for n in names]},
                                add_media={str(secret): b"a member under that name",
                                           climb: b"and one under this"})

        def packed(apkg):
            media, members = self.package(apkg)
            self.assertEqual([m for m, data in members.items() if b"SECRET-OUTSIDE" in data], [],
                             "no member of the package holds the file's bytes")
            return sorted(media.values())

        # the bootstrap import
        other = str(self.tmp / "other-anki")
        os.makedirs(other)
        res = import_apkg.import_all(evil, other)
        (deck,) = res["decks"]
        ddir = os.path.join(other, deck["path"])
        back = {c["guid"]: c for c in ax.load_cards(ddir)}
        for guid in (self.c1["guid"], self.c2["guid"]):
            for key in ax.MEDIA_KEYS:
                self.assertIsNone(back[guid][key], (guid, key))
        self.assertEqual(os.listdir(os.path.join(ddir, "media")), [],
                         "no card names a file, so none is copied out of the package")
        self.assertEqual(res["media"], {"copied": 0, "missing": []})
        rebuilt = ax.build_deck(ddir, str(self.tmp / "rebuilt.apkg"))
        self.assertEqual(packed(rebuilt), [], "no card of this package names a file it may carry")

        # the sync of an export from Anki, into the deck the store holds
        rep = sync_apkg.run_sync(evil, self.anki, dry_run=False)
        self.assertEqual(rep["decks"][0]["media_missing"], [])
        cards = {c["guid"]: c for c in ax.load_cards(self.deck)}
        self.assertEqual({k: cards[self.c1["guid"]][k] for k in ax.MEDIA_KEYS},
                         dict.fromkeys(ax.MEDIA_KEYS))
        self.assertIsNone(cards[self.c2["guid"]]["snd_back"])
        self.assertEqual(packed(ax.build_deck(self.deck, str(self.tmp / "synced.apkg"))), [])
        self.assertEqual(secret.read_bytes(), b"SECRET-OUTSIDE-THE-DECK", "and nothing wrote over it")

    def test_a_store_already_holding_such_a_name_builds_without_it(self):
        secret = self.tmp / "secret.txt"
        secret.write_bytes(b"SECRET-OUTSIDE-THE-DECK")
        path = os.path.join(self.deck, "cards", self.c3["id"] + ".json")
        anki_store.write_json(path, dict(self.c3, snd_front=str(secret), img_front=str(secret),
                                         snd_back="../../../../secret.txt", img_back="media"))
        out = ax.build_deck(self.deck, str(self.tmp / "again.apkg"))
        media, members = self.package(out)
        self.assertEqual([m for m, data in members.items() if b"SECRET-OUTSIDE" in data], [],
                         "no member of the package holds the file's bytes")
        self.assertEqual(sorted(media.values()),
                         sorted([self.c1["img_front"], self.c1["snd_front"], self.c2["snd_back"]]))
        names = ax.MODELS[ax.model_for(self.c3)]["fields"]
        f3 = dict(zip(names, self.notes(out)[self.c3["guid"]]))
        self.assertEqual((f3["FrontImage"], f3["BackImage"]), ("", ""))

    def test_only_a_bare_file_name_is_a_media_name(self):
        for good in ("clock-a1b2c3.mp3", "20260917-165317-ab12-front-audio.mp3", "x.jpg",
                     "leçon un.ogg", ".hidden.mp3"):
            self.assertEqual(ax.media_name(good), good)
        for bad in ("/etc/hostname", "../x.mp3", "a/b.mp3", "..", ".", "", None, 3,
                    "..\\x.mp3", "C:x.mp3", "C:\\x.mp3", "x\x00.mp3", "say \"hi\".mp3", "<b>.mp3"):
            self.assertIsNone(ax.media_name(bad), repr(bad))
        self.assertEqual(import_apkg.un_sound("[sound:/etc/hostname]"), None)
        self.assertEqual(import_apkg.un_sound("[sound:..&#47;x.mp3]"), None)
        self.assertEqual(import_apkg.un_img('<img src="https://example.org/x.png">'), None)
        self.assertEqual(import_apkg.un_img('<img src="x.png">[sound:y.mp3]'), "x.png")
        self.assertEqual(import_apkg.un_sound('<img src="x.png">[sound:y.mp3]'), "y.mp3")
        self.assertIs(import_apkg.SOUND_RE, ax.SOUND_RE, "one sound tag, read and played alike")


if __name__ == "__main__":
    unittest.main()
