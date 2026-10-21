# SPDX-License-Identifier: GPL-3.0-or-later
"""A small, INSTALLED set of ARASAAC pictograms for the pictogram picker's tests (a0.5.3): the folder lib/getarasaac.py
leaves, written directly instead of fetched, with real words in English, Spanish and Persian, real PNG pictures (a coloured
disc inside a black ring, a different colour for each number, on nothing) and the flags ARASAAC gives (a schematic drawing, one
about sex, one about violence).

    import pictogram_world
    pictogram_world.install(path_of_an_arasaac_folder)          # the whole world, complete
    pictogram_world.install(path, complete=False, pictures=12)  # a download that was stopped

Used by tests/studio_harness.py (--pictograms), which the picker's browser suite drives, and by nothing that reaches a
network.  Nothing here is ARASAAC's: the words are common ones written by hand and the pictures are discs."""
import json
import os
import struct
import zlib

CREDIT = ("Pictograms author: Sergio Palao. Origin: ARASAAC (http://www.arasaac.org). "
          "License: CC (BY-NC-SA). Owner: Government of Aragon (Spain)")

# id: (English words, Spanish words, Persian words, meaning, flags).  The first English word is the pictogram's caption.
NAMED = {
    2317: (["house", "home"], ["casa", "hogar"], ["خانه"], "a building where people live", ()),
    2318: (["detached house"], ["casa unifamiliar"], ["خانه ویلایی"], "a house standing alone", ()),
    2319: (["house"], ["casa"], ["خانه"], "a simple drawing of a house", ("schematic",)),
    2400: (["tree"], ["árbol"], ["درخت"], "a tall plant with a trunk and branches", ()),
    2401: (["dog"], ["perro"], ["سگ"], "a domestic animal that barks", ()),
    2402: (["cat"], ["gato"], ["گربه"], "a domestic animal that purrs", ()),
    2403: (["bread"], ["pan"], ["نان"], "food baked from flour", ()),
    2404: (["water"], ["agua"], ["آب"], "the liquid we drink", ()),
    2405: (["book"], ["libro"], ["کتاب"], "pages bound together to be read", ()),
    2406: (["school"], ["escuela", "colegio"], ["مدرسه"], "a place where children learn", ()),
    2407: (["to eat", "eat"], ["comer"], ["خوردن"], "to take food in", ()),
    2408: (["to drink", "drink"], ["beber"], ["نوشیدن"], "to take a liquid in", ()),
    2409: (["big", "large"], ["grande"], ["بزرگ"], "of great size", ()),
    2410: (["small", "little"], ["pequeño"], ["کوچک"], "of little size", ()),
    2411: (["red"], ["rojo"], ["قرمز"], "the colour of blood", ()),
    2412: (["ice cream"], ["helado"], ["بستنی"], "a frozen sweet food", ()),
    2413: (["sun"], ["sol"], ["خورشید"], "the star the Earth goes round", ()),
    2414: (["moon"], ["luna"], ["ماه"], "the satellite of the Earth", ()),
    2415: (["car"], ["coche"], ["ماشین"], "a vehicle with four wheels", ()),
    2416: (["apple"], ["manzana"], ["سیب"], "a round fruit", ()),
    2500: (["kiss"], ["beso"], ["بوسه"], "to touch with the lips", ("sex",)),
    2501: (["war"], ["guerra"], ["جنگ"], "fighting between armies", ("violence",)),
}
FLAG_BITS = ("schematic", "aac", "aacColor", "skin", "hair", "violence", "sex")      # getarasaac.FLAGS
ANIMALS = ["ant", "bee", "bird", "cow", "duck", "fish", "frog", "goat", "hen", "lion", "mouse", "pig", "sheep", "snake",
           "tiger", "turtle", "whale", "wolf", "zebra", "horse"]
FILLER = 3000                                                           # filler pictograms: "animal-ant" ... for paging


def png(pid, size):
    """A whole RGBA PNG: a disc in a colour of this number's own, a black ring round it, transparent outside."""
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)
    r, g, b = (pid * 67) % 200 + 30, (pid * 131) % 200 + 30, (pid * 29) % 200 + 30
    c = size / 2.0
    ring, rad = max(2.0, size * 0.04), size * 0.4
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            d2 = (x + .5 - c) ** 2 + (y + .5 - c) ** 2
            if d2 <= (rad - ring) ** 2:
                row += bytes((r, g, b, 255))
            elif d2 <= rad ** 2:
                row += bytes((0, 0, 0, 255))
            else:
                row += bytes((0, 0, 0, 0))
        rows.append(bytes(row))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"".join(rows)))
            + chunk(b"IEND", b""))


def entries(words, meaning):
    out = []
    for i, w in enumerate(words):
        e = {"k": w, "t": 2}
        if i == 0:
            e["p"] = w + "s"
            e["m"] = meaning
        out.append(e)
    return out


def world(fillers=70):
    """-> {id: (en, es, fa, meaning, flags)}: the named pictograms and `fillers` more, for a list long enough to page."""
    out = dict(NAMED)
    for i in range(fillers):
        name = ANIMALS[i % len(ANIMALS)]
        out[FILLER + i] = (["animal %s %02d" % (name, i)], ["animal %s %02d" % (name, i)], [], "a filler animal", ())
    return out


def install(folder, complete=True, resolution=300, fillers=70, pictures=None, locales=("en", "es", "fa")):
    """Write the folder `lib/getarasaac.py` would leave.  `pictures` is how many of the pictures to write (the first
    ones by number), else all; `complete` False writes the manifest of a download that did not finish."""
    here = world(fillers)
    os.makedirs(os.path.join(folder, "pictograms"), exist_ok=True)
    for loc, at in zip(("en", "es", "fa"), range(3)):
        if loc not in locales:
            continue
        words = {str(pid): entries(v[at], v[3]) for pid, v in here.items() if v[at]}
        with open(os.path.join(folder, "index.%s.json" % loc), "w", encoding="utf-8") as f:
            json.dump({"format": 1, "words": words}, f, ensure_ascii=False, separators=(",", ":"))
    facts = {}
    for pid, v in here.items():
        bits = sum(1 << FLAG_BITS.index(name) for name in v[4])
        facts[str(pid)] = {"u": "2024-0%d-1%dT10:00:00.000Z" % (1 + pid % 9, pid % 9), "f": bits}
    ids = sorted(here)
    written = ids if pictures is None else ids[:pictures]
    for pid in written:
        size = 160 if pid < FILLER else 40
        with open(os.path.join(folder, "pictograms", "%d.png" % pid), "wb") as f:
            f.write(png(pid, size))
    if not complete:
        for pid in ids[len(written):]:
            facts[str(pid)]["p"] = 1
    with open(os.path.join(folder, "pictograms.json"), "w", encoding="utf-8") as f:
        json.dump({"format": 1, "pictograms": facts}, f, separators=(",", ":"))
    mine = {"format": 1, "complete": bool(complete), "resolution": resolution, "pictograms": len(ids),
            "finished": "2026-10-20T10:00:00Z" if complete else None,
            "locales": {loc: {"fetched": "2026-10-20T10:00:00Z", "words": len(here), "covered": len(here)} for loc in locales}}
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(mine, f)
    with open(os.path.join(folder, "LICENSE-ARASAAC.txt"), "w", encoding="utf-8") as f:
        f.write(CREDIT + "\n")
    return {"ids": ids, "named": sorted(NAMED), "pictures": len(written)}


if __name__ == "__main__":
    import sys
    print(json.dumps(install(sys.argv[1])))
