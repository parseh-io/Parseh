#!/usr/bin/env python3
"""The Anki round trip, for every language at once.

    python3 tests/fixtures/anki/roundtrip.py

This directory IS a fixture card store, laid out exactly as the real one
(docs/languages.md sections 2 and 4): one deck per language, under its
language's folder, each holding that language's vocab and opposites card.

    tests/fixtures/anki/persian/parseh-test-fa/    fa-vocab, fa-opp
    tests/fixtures/anki/arabic/parseh-test-ar/     …
    tests/fixtures/anki/italian/parseh-test-it/
    tests/fixtures/anki/japanese/parseh-test-ja/
    tests/fixtures/anki/french/parseh-test-fr/
    tests/fixtures/anki/german/parseh-test-de/
    tests/fixtures/anki/turkish/parseh-test-tr/

Every deck is NAMED "Parseh::Test": two languages may hold a deck of
the same name, and therefore of the same slug, because they sit in
different folders -- that is the property this fixture pins, and it is
pinned harder the more languages there are.

What is checked, in order:

  * the store reads: anki_store.decks() finds one deck per language, in
    registry order, each with its folder, slug and path, and a legacy deck
    lying directly under anki/ is read as Persian and reported once;
  * the package: every deck's cards gathered into one
    deck (a mixed deck is what an import from Anki can make) builds to a
    collection holding one note type per entry of anki_export.MODELS --
    the Persian two with their historical ids and fields byte for byte,
    a reading language's (Japanese) with their Reading fields, every note
    holding exactly as many fields as its note type;
  * the previews: the kana where a card has one, `direction: rtl` only
    for the right-to-left languages;
  * one deck of each language builds on its own, to its own
    anki/build/<folder>-<slug>.apkg -- two languages' decks of one name
    cannot overwrite each other -- carrying only its language's note types;
  * the writing side: a Japanese card and a Persian card posted to the
    same deck name land in two different folders, and the answer says
    when a card was filed under its own language rather than the deck the
    dashboard named;
  * the package is imported back into an empty store with
    import_apkg.import_all (the pkg-<guid> path a Parseh-built package
    takes): the deck is created under a language folder and the cards
    carry the language and the kana they went in with; notetypes.snapshot
    on the built collection reports every note type;
  * finally the Persian models are compared to what the exporter in git
    HEAD writes, when git can show it: those two note types may never
    change shape (anki/README.md).

Nothing here counts languages by hand: the expected note types are
whatever the registry declares (docs/languages.md section 10 -- add a
language, run the tests).  A registry language the fixture store has no
deck for gets a synthetic vocab and opposites card in the temporary copy
the build runs on, so the fixture on disk need not be extended for the
round trip to cover a fifth language; extend it anyway when the language
has conventions worth pinning (the Japanese kana values below are pinned
that way).

Standard library only, like everything under the server.  Exits non-zero
on the first failed check and says which.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
for p in (os.path.join(ROOT, "lib"), os.path.join(ROOT, "youtube", "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import anki_export as ax      # noqa: E402
import anki_store             # noqa: E402
import import_apkg            # noqa: E402
import languages              # noqa: E402
import notetypes              # noqa: E402

STORE = HERE                  # this directory is the fixture collection
FA_V, FA_O = 1724563200001, 1724563200002
FA_V_FIELDS = ["Persian", "Transliteration", "English", "Context", "Notes",
               "FrontImage", "BackImage", "Source", "Reverse", "ReverseOnly"]
FA_O_FIELDS = ["Persian", "Transliteration", "Opposite", "OppositeTr",
               "Notes", "FrontImage", "BackImage", "Source", "Reverse"]


def check(cond, what):
    if not cond:
        sys.exit("FAIL: " + what)
    print("ok   " + what)


def fixture_cards():
    """Every card in the fixture store, by id, whichever deck it sits in."""
    out = {}
    for d in anki_store.decks(STORE):
        for c in ax.load_cards(os.path.join(STORE, d["path"])):
            out[c["id"]] = c
    return out


def synthetic_card(L, kind):
    """A vocab or opposites card of this language shaped exactly like the
    fixture's, for a registry language the fixture store does not cover."""
    reading = L.reading
    card = {"id": "%s-%s" % (L.code, "opp" if kind == "opposites" else "vocab"),
            "guid": "fx-%s-%s" % (L.code, "opp" if kind == "opposites" else "vocab"),
            "kind": kind, "lang": L.code, "created": "2026-09-03 10:00:00",
            "video": "fixture-" + L.code if kind == "vocab" else "",
            "book": "fixture-" + L.code if kind != "vocab" else "",
            "time": 0, "context": "", "notes": "", "bidirectional": True,
            "reverse_only": False, "img_front": None, "img_back": None,
            "fa": "%s word" % L.name, "kana": "reading" if reading else "",
            "tr": "translit", "en": "house" if kind == "vocab" else "",
            "opp": "%s opposite" % L.name if kind == "opposites" else "",
            "opp_kana": "opposite reading" if (reading and kind == "opposites") else "",
            "opp_tr": "opp translit" if kind == "opposites" else "",
            "tags": ["%s-%s" % (L.tag, "youtube" if kind == "vocab" else "book")],
            "source": {"label": "fixture", "url": ""}}
    return card


def deck_for_registry(tmp):
    """One deck under `tmp` holding a card per note type in
    anki_export.MODELS: the fixture's own where it has them, a synthetic
    one otherwise.  Mixing every language into one deck is deliberate --
    a deck imported from Anki may hold notes of any of them, and a
    package must carry every note type its cards use.  Returns
    (deck dir, ids of the synthetic cards)."""
    deck = os.path.join(tmp, "store", "persian", "parseh-test")
    os.makedirs(os.path.join(deck, "cards"))
    os.makedirs(os.path.join(deck, "media"))
    with open(os.path.join(deck, "deck.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "Parseh::Test", "lang": "fa", "id": 1998880123,
                   "created": "2026-09-03"}, f)
    cards = fixture_cards()
    have = {(c["lang"], c["kind"]) for c in cards.values()}
    made = []
    for mid, m in ax.MODELS.items():
        if (m["lang"], m["kind"]) in have:
            continue
        card = synthetic_card(languages.get(m["lang"]), m["kind"])
        cards[card["id"]] = card
        made.append(card["id"])
    for card in cards.values():
        with open(os.path.join(deck, "cards", card["id"] + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=1)
    return deck, made


def models_in(apkg, tmp):
    """{mid: model} out of a built package's collection."""
    d = tempfile.mkdtemp(dir=tmp)
    with zipfile.ZipFile(apkg) as z:
        z.extract("collection.anki2", d)
    con = sqlite3.connect(os.path.join(d, "collection.anki2"))
    (blob,) = con.execute("select models from col").fetchone()
    con.close()
    return {int(k): v for k, v in json.loads(blob).items()}


# ------------------------------------------------------------ the store
def test_layout():
    """decks(): one deck per language, in registry order, each under its
    own folder -- and a legacy deck read as Persian and reported once."""
    ds = anki_store.decks(STORE)
    codes = [d["lang"] for d in ds]
    # no count is written here: the registry decides how many languages there
    # are, and a language whose fixture deck has not been written yet is named
    # below rather than failing the run (docs/languages.md section 10 -- the
    # smoke test only tries what it has a fixture for)
    check(codes == [c for c in languages.CODES if c in codes]
          and len(codes) == len(set(codes)),
          "decks(): one deck per language, in registry order (%s)"
          % " ".join(codes))
    missing = [c for c in languages.CODES if c not in codes]
    if missing:
        print("note: no fixture deck for %s -- covered by a synthetic card only"
              % ", ".join(missing))
    for d in ds:
        L = languages.get(d["lang"])
        check(d["folder"] == L.folder and d["path"] == L.folder + "/" + d["slug"],
              "%s: folder %s, path %s" % (d["lang"], d["folder"], d["path"]))
        check(d["cards"] == 2 and not d["legacy"],
              "%s: two cards, not legacy" % d["lang"])
    check(len({d["name"] for d in ds}) == 1,
          "all %d decks share one name -- two languages may" % len(ds))
    check([d["lang"] for d in anki_store.decks(STORE, "ja")] == ["ja"],
          "decks(lang=…) narrows to one language")
    one, hits = anki_store.find_deck(STORE, "parseh-test-ja")
    check(one and one["lang"] == "ja" and len(hits) == 1,
          "find_deck resolves a slug only one language holds")

    with tempfile.TemporaryDirectory(prefix="anki-legacy-") as tmp:
        # the layout from before languages: a deck directly under anki/
        old = os.path.join(tmp, "old-deck")
        os.makedirs(os.path.join(old, "cards"))
        with open(os.path.join(old, "deck.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Old flashcards", "id": 1998880999}, f)
        card = fixture_cards()["fa-vocab"]
        with open(os.path.join(old, "cards", "fa-vocab.json"), "w",
                  encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False)
        said = []
        ds = anki_store.decks(tmp, say=said.append)
        check(len(ds) == 1 and ds[0]["lang"] == "fa" and ds[0]["legacy"]
              and ds[0]["path"] == "old-deck" and ds[0]["folder"] == "persian",
              "a legacy deck directly under anki/ is read as Persian")
        check(len(said) == 1 and "old-deck" in said[0]
              and "persian" in said[0],
              "and reported once, saying where it belongs (%s)"
              % (said[0] if said else "nothing said"))
        anki_store.decks(tmp, say=said.append)
        check(len(said) == 1, "the report is said once, not on every listing")
        out = ax.build_deck(old)
        check(os.path.basename(out) == "persian-old-deck.apkg"
              and os.path.dirname(out) == os.path.join(tmp, "build"),
              "a legacy deck builds to anki/build/persian-<slug>.apkg")


# ------------------------------------------------- one deck per language
def test_per_language_builds(tmp):
    """Every fixture deck builds on its own, to its own .apkg, carrying
    only the note types of its language."""
    store = os.path.join(tmp, "per-lang")
    shutil.copytree(STORE, store, ignore=shutil.ignore_patterns(
        "__pycache__", "*.py", "build"))
    decks = anki_store.decks(store)
    for d in decks:
        L = languages.get(d["lang"])
        out = ax.build_deck(os.path.join(store, d["path"]))
        check(os.path.basename(out) == "%s-%s.apkg" % (d["folder"], d["slug"]),
              "%s builds to %s" % (d["path"], os.path.basename(out)))
        check(os.path.dirname(out) == os.path.join(store, "build"),
              "%s: the package lands in the collection's build/" % d["lang"])
        mids = set(models_in(out, tmp))
        check(mids == {int(L.anki["vocab_model"]), int(L.anki["opposites_model"])},
              "%s: the package carries only %s's two note types"
              % (d["path"], L.name))
    built = sorted(os.listdir(os.path.join(store, "build")))
    check(len(built) == len(decks),
          "%d packages, one per deck: %s" % (len(decks), " ".join(built)))


# ------------------------------------------------------- the writing side
def test_add_card(tmp):
    """A card is filed under ITS OWN language, whatever deck was named:
    two cards of two languages posted to one deck name make two decks."""
    store = os.path.join(tmp, "written")
    os.makedirs(store)

    def post(lang, deck, deck_lang=None, **kw):
        card = {"lang": lang, "kind": "vocab", "fa": "text-" + lang,
                "tr": "tr", "en": "meaning", "tags": [], "source": {}}
        card.update(kw)
        body = {"deck": deck, "card": card}
        if deck_lang:
            body["deck_lang"] = deck_lang
        res, status = anki_store.add_card(store, body)
        check(status == 200 and res.get("ok"),
              "POST a %s card to %r -> %s" % (lang, deck, res.get("error", "ok")))
        return res

    r1 = post("fa", "Shared", kana="")
    check(r1["deck"]["path"] == "persian/shared" and "refiled" not in r1,
          "the Persian card lands in persian/shared, nothing refiled")
    # the dashboard offered the Persian deck; the card is Japanese
    r2 = post("ja", "Shared", deck_lang="fa", kana="かな")
    check(r2["deck"]["path"] == "japanese/shared",
          "the Japanese card lands in japanese/shared, not in the Persian deck")
    check(r2.get("refiled", {}).get("from") == "fa"
          and r2["refiled"]["to"] == "ja" and r2["refiled"].get("note"),
          "the answer says the card was refiled under its own language")
    # a different word: the same one again is asked about (10.7, anki_store.add_card answers 409)
    r3 = post("ja", "Shared", deck_lang="ja", fa="text-ja-2")
    check(r3["deck"]["path"] == "japanese/shared" and r3["deck"]["cards"] == 2
          and "refiled" not in r3,
          "a second Japanese card joins the same deck, nothing refiled")
    ds = anki_store.decks(store)
    check(len(ds) == 2 and {d["path"] for d in ds}
          == {"persian/shared", "japanese/shared"},
          "two decks, one name, one slug, two folders")
    check(len({d["slug"] for d in ds}) == 1 and len({d["name"] for d in ds}) == 1,
          "the slug and the name really are the same for both")
    metas = [anki_store.read_json(os.path.join(store, d["path"], "deck.json"))
             for d in ds]
    check(all(m.get("lang") == d["lang"] for m, d in zip(metas, ds)),
          "each deck.json records its language")
    # a deck of the same name in the same language reuses its directory
    r4 = post("fa", "Shared", fa="text-fa-2")
    check(r4["deck"]["path"] == "persian/shared" and r4["deck"]["cards"] == 2,
          "a second Persian card reuses persian/shared")
    outs = sorted(os.path.basename(ax.build_deck(os.path.join(store, d["path"])))
                  for d in ds)
    check(outs == ["japanese-shared.apkg", "persian-shared.apkg"],
          "both decks build, to two packages: %s" % " ".join(outs))
    # an unknown language is refused, not filed as Persian
    res, status = anki_store.add_card(
        store, {"deck": "Shared", "card": {"lang": "xx", "fa": "x"}})
    check(status == 400 and not res["ok"], "a card with an unknown lang is refused")


def main():
    # one note per note type: the number the registry implies, never a
    # count written by hand (a fifth language must pass without edits)
    N = len(ax.MODELS)
    test_layout()
    fixture = fixture_cards()
    check(all((c["lang"], c["kind"]) in {(m["lang"], m["kind"])
                                           for m in ax.MODELS.values()}
              for c in fixture.values()),
          "every fixture card is of a language with note types")
    check(len({(c["lang"], c["kind"]) for c in fixture.values()}) == len(fixture),
          "the fixture store holds at most one card per note type")

    with tempfile.TemporaryDirectory(prefix="anki-roundtrip-") as tmp:
        test_per_language_builds(tmp)
        test_add_card(tmp)
        deck, made = deck_for_registry(tmp)
        if made:
            print("note: synthetic cards for languages the fixture lacks: %s"
                  % ", ".join(made))
        cards = {c["id"]: c for c in ax.load_cards(deck)}
        check(len(cards) == N, "one card per note type (%d)" % N)
        out = ax.build_deck(deck, os.path.join(tmp, "parseh-test.apkg"))
        check(os.path.exists(out), "build_deck wrote %s" % os.path.basename(out))

        # ---- what the package says -----------------------------------
        with zipfile.ZipFile(out) as z:
            z.extract("collection.anki2", tmp)
            media = json.loads(z.read("media").decode("utf-8"))
        names = set(media.values())
        check("_Vazirmatn.woff2" in names, "Vazirmatn travels for fa")
        check("_NotoNaskhArabic.woff2" in names, "Noto Naskh Arabic travels for ar")
        # exactly the bundled faces of the languages that have one on disk
        bundled = {ax.font_media_name(L) for L in languages.LANGS.values()
                   if ax.font_path(L)}
        check({n for n in names if n.startswith("_")} == bundled,
              "no other font rides along (a language with no face in "
              "lib/fonts/ uses the device's)")
        con = sqlite3.connect(os.path.join(tmp, "collection.anki2"))
        (blob,) = con.execute("select models from col").fetchone()
        models = {int(k): v for k, v in json.loads(blob).items()}
        check(len(models) == N, "%d note types in the package" % N)
        check(set(models) == set(ax.MODELS), "the package's ids are MODELS' ids")
        check([f["name"] for f in models[FA_V]["flds"]] == FA_V_FIELDS
              and models[FA_V]["name"] == "Frank YouTube Persian",
              "Persian vocab: id, name and fields unchanged")
        check([f["name"] for f in models[FA_O]["flds"]] == FA_O_FIELDS
              and models[FA_O]["name"] == "Frank Persian Opposites",
              "Persian opposites: id, name and fields unchanged")
        # the Reading fields: on every reading language's pair, on no other
        for L in languages.LANGS.values():
            a = L.anki
            if not a.get("vocab_model"):
                continue
            fv = [f["name"] for f in models[a["vocab_model"]]["flds"]]
            fo = [f["name"] for f in models[a["opposites_model"]]["flds"]]
            field = ax.MODELS[a["vocab_model"]]["field"]
            if L.reading:
                check(fv[:2] == [field, "Reading"],
                      "%s vocab has a Reading field" % L.name)
                check("OppositeReading" in fo and fo.index("OppositeReading")
                      == fo.index("Opposite") + 1,
                      "%s opposites has OppositeReading right after Opposite" % L.name)
                check("{{Reading}}" in models[a["vocab_model"]]["tmpls"][0]["qfmt"],
                      "the reading line is in the %s templates" % L.name)
            else:
                check("Reading" not in fv and "OppositeReading" not in fo,
                      "%s has no Reading fields" % L.name)
                check("{{Reading}}" not in models[a["vocab_model"]]["tmpls"][0]["qfmt"],
                      "no reading line in the %s templates" % L.name)
        ja = languages.get("ja").anki
        jao = [f["name"] for f in models[ja["opposites_model"]]["flds"]]
        for mid, m in models.items():
            L = languages.get(ax.MODELS[mid]["lang"])
            check(("direction: rtl" in m["css"]) == L.rtl,
                  "%s: direction only for RTL" % m["name"])
            check(any(f["rtl"] for f in m["flds"]) == L.rtl,
                  "%s: rtl field flags only for RTL" % m["name"])
            check(len(m["tmpls"]) == 2 and m["req"][1][1] == "all"
                  and len(m["req"][1][2]) == 2,
                  "%s: two templates and a req per position" % m["name"])
            back = "Opposite" if ax.MODELS[mid]["kind"] == "opposites" else "English"
            fl = [f["name"] for f in m["flds"]]
            check(m["req"][1][2] == [fl.index(back), fl.index("Reverse")],
                  "%s: req names %s and Reverse by position" % (m["name"], back))
        ar_css = models[languages.get("ar").anki["vocab_model"]]["css"]
        check('url("_NotoNaskhArabic.woff2")' in ar_css and "Noto Naskh Arabic" in ar_css,
              "Arabic CSS loads the bundled face")
        for mid, m in models.items():
            check((".kana" in m["css"]) == languages.get(ax.MODELS[mid]["lang"]).reading,
                  "%s: the .kana rule only on a reading language's sheet" % m["name"])
        n = 0
        for mid, flds, sfld in con.execute("select mid, flds, sfld from notes"):
            vals = flds.split("\x1f")
            check(len(vals) == len(models[mid]["flds"]),
                  "note %r: %d fields for its model" % (sfld, len(vals)))
            n += 1
        check(n == N, "%d notes" % N)
        (jf,) = con.execute("select flds from notes where mid=?",
                            (ja["vocab_model"],)).fetchone()
        check(jf.split("\x1f")[:3] == ["家", "いえ", "ie"],
              "the Japanese note carries kanji, kana, romaji in that order")
        (jo,) = con.execute("select flds from notes where mid=?",
                            (ja["opposites_model"],)).fetchone()
        jo = dict(zip(jao, jo.split("\x1f")))
        check(jo["OppositeReading"] == "ちいさい" and jo["Reading"] == "おおきい",
              "the Japanese opposites note carries both readings")
        # notetypes.snapshot reads the same collection
        snap = notetypes.snapshot(con)
        check(set(snap) == set(ax.MODELS), "notetypes.snapshot returns every note type")
        for mid, s in snap.items():
            check(s["fields"] == ax.MODELS[mid]["fields"],
                  "snapshot of %s matches MODELS" % s["name"])
        con.close()

        # ---- the previews --------------------------------------------
        for cid, c in sorted(cards.items()):
            html = ax.preview_html(c)
            L = languages.get(c["lang"])
            check(("direction: rtl" in html) == L.rtl,
                  "preview %s: direction rtl only for RTL" % cid)
            check(('class="kana"' in html) == bool(c.get("kana")),
                  "preview %s: kana line only when the card has one" % cid)
            if c.get("kana"):
                check(c["kana"] in html, "preview %s shows the kana" % cid)
            if c.get("opp_kana"):
                check(c["opp_kana"] in html, "preview %s shows the opposite's kana" % cid)
            check(c["fa"] in html and 'lang="%s"' % c["lang"] in html,
                  "preview %s shows the text and names its language" % cid)
            if L.code == "ar":
                check('url("/lib/fonts/NotoNaskhArabic.woff2")' in html,
                      "preview %s loads the Arabic face from /lib/fonts" % cid)
            if L.code == "fa":
                check('url("/lib/fonts/Vazirmatn.woff2")' in html,
                      "preview %s loads Vazirmatn from /lib/fonts" % cid)
            if c["kind"] == "vocab":
                check("%s → English" % L.name in html,
                      "preview %s: labels name the language" % cid)
        night = ax.preview_html(cards["fa-vocab"], night=True,
                                font_url={"fa": "/x/v.woff2"})
        check('url("/x/v.woff2")' in night and "nightMode" in night,
              "preview takes a per-language font_url dict and the night flag")
        # the old single-URL convention could only ever mean Vazirmatn:
        # honoured for Persian, never applied to another language's face
        check('url("/x/v.woff2")' in ax.preview_html(cards["fa-vocab"],
                                                     font_url="/x/v.woff2"),
              "a plain font_url string still serves a Persian preview")
        check('url("/lib/fonts/NotoNaskhArabic.woff2")' in
              ax.preview_html(cards["ar-vocab"], font_url="/x/v.woff2"),
              "a plain font_url string is not applied to an Arabic preview")
        # a card whose `lang` is no registry code is refused, not filed
        # as Persian (it would lose its reading and its note type)
        for bad in ("xx", 5, ["ja"]):
            try:
                ax.model_for(dict(cards["ja-vocab"], lang=bad))
                sys.exit("FAIL: model_for accepted lang=%r" % (bad,))
            except ValueError:
                pass
        check(ax.model_for(dict(cards["fa-vocab"], lang=None)) == FA_V
              and ax.model_for(dict(cards["fa-vocab"], lang="")) == FA_V
              and ax.model_for(dict(cards["ja-vocab"], lang=" JA ")) ==
              ja["vocab_model"],
              "model_for: absent/empty lang is Persian, a code is forgiven case")

        # ---- back into an empty store --------------------------------
        store = os.path.join(tmp, "anki")
        os.makedirs(store)
        res = import_apkg.import_all(out, store)
        check(res["own_build"] == "parseh-test", "import sees the build stamp (pkg- path)")
        check(len(res["decks"]) == 1 and res["decks"][0]["cards"] == N
              and res["decks"][0]["kept"] == 0,
              "import_all writes %d plain cards into one deck" % N)
        d0 = res["decks"][0]
        check(d0["path"] == "%s/%s" % (d0["folder"], d0["slug"])
              and languages.get(d0["lang"]).folder == d0["folder"]
              and os.path.isdir(os.path.join(store, d0["path"])),
              "the imported deck is created under a language folder (%s)"
              % d0["path"])
        check(anki_store.decks(store)[0]["path"] == d0["path"],
              "and the store lists it there")
        check(not res["skipped"], "no note type was unknown to the importer")
        check(set(res["notetypes"] and {c["mid"] for c in res["notetypes"]})
              == set(ax.MODELS), "the import captured every note type")
        got = {}
        cdir = os.path.join(store, d0["path"], "cards")
        for fn in os.listdir(cdir):
            with open(os.path.join(cdir, fn), encoding="utf-8") as f:
                c = json.load(f)
            check(fn.startswith("pkg-"), "%s is filed as pkg-<guid>" % fn)
            got[c["guid"]] = c
        for cid, c in cards.items():
            r = got.get(c["guid"])
            check(r is not None, "%s came back" % cid)
            check(r["lang"] == c["lang"] and r["kind"] == c["kind"],
                  "%s: lang and kind round-tripped" % cid)
            check(r["fa"] == c["fa"] and r["tr"] == c["tr"],
                  "%s: text and transliteration round-tripped" % cid)
            if languages.get(c["lang"]).reading:
                check(r.get("kana") == c["kana"], "%s: kana round-tripped" % cid)
                if c["kind"] == "opposites":
                    check(r.get("opp_kana") == c["opp_kana"],
                          "%s: opp_kana round-tripped" % cid)
            else:
                check("kana" not in r, "%s: no kana key for a language without a reading" % cid)
            check(r["tags"] == c["tags"], "%s: tags round-tripped" % cid)
            check(r["bidirectional"] is True and r["reverse_only"] is False,
                  "%s: direction flags round-tripped" % cid)
        # the store-level shape check accepts the captured models
        ax.check_shape(ax.load_overrides(store))
        check(True, "check_shape accepts the captured note types")
        desc = notetypes.describe(store)
        check(len(desc) == N and all(d["matches_code"] for d in desc),
              "notetypes.describe: all %d match the code" % N)

    # ---- the Persian models against git HEAD --------------------------
    try:
        old_src = subprocess.run(
            ["git", "-C", ROOT, "show", "HEAD:youtube/lib/anki_export.py"],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print("skip the HEAD comparison (git could not show the old exporter)")
        return
    if "def model_json(now" not in old_src:
        print("skip the HEAD comparison (HEAD already has the generalised exporter)")
        return
    import importlib.util
    path = os.path.join(tempfile.gettempdir(), "old_anki_export_%d.py" % os.getpid())
    with open(path, "w", encoding="utf-8") as f:
        f.write(old_src)
    try:
        spec = importlib.util.spec_from_file_location("old_anki_export", path)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
    finally:
        os.unlink(path)
    now = 1700000000
    check(old.model_json(now, {}) == ax.model_json(FA_V, now, {}),
          "Persian vocab model JSON identical to HEAD's")
    check(old.opp_model_json(now, {}) == ax.model_json(FA_O, now, {}),
          "Persian opposites model JSON identical to HEAD's")
    check(old.CSS == ax.CSS, "Persian CSS identical to HEAD's")
    fa = fixture["fa-vocab"]
    check(old.note_fields(fa) == ax.note_fields(fa)
          and old.note_fields(fixture["fa-opp"]) == ax.note_fields(fixture["fa-opp"]),
          "Persian note fields identical to HEAD's")
    print("all good")


if __name__ == "__main__":
    main()
