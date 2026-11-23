# SPDX-License-Identifier: GPL-3.0-or-later
"""WebP, GIF and HEIC pictures (TO-DO 8.19, a0.6.3): taken wherever a picture
is added, a HEIC turned into a JPEG as it comes in, a WebP's or a GIF's PNG
made for the studio's PDF -- and, where Pillow or pillow-heif is missing,
plain words instead of a crash.

    python3 -m unittest tests.test_picture_formats

The fixtures are made here: a WebP and a two-frame GIF as bytes, a HEIC with
pillow-heif when this Python has it (skipped otherwise, saying so).  No
socket: a deck's upload door is driven through a fake handler, in a
temporary studio library and exercises folder."""
import base64
import io
import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import decks       # noqa: E402
import deckroutes  # noqa: E402
import envsetup    # noqa: E402
import mdparser    # noqa: E402
import store       # noqa: E402
import texgen      # noqa: E402

# 4 x 2, red, lossless
WEBP = base64.b64decode("UklGRh4AAABXRUJQVlA4TBEAAAAvA0AAAAdQjyLXo/+BiOh/AAA=")
# 3 x 3, two frames: red, then blue
GIF = base64.b64decode(
    "R0lGODlhAwADAIEAAP8AAAAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQACgAAACwAAAAAAwADAAAIBwAB"
    "CBw4MCAAIfkEAQoAAQAsAAAAAAMAAwCBAAD/AAAAAAAAAAAACAcAAQgcODAgADs=")
PNG = b"\x89PNG\r\n\x1a\n" + b"pixels"
# an AVIF opens with the same box a HEIF does, and must not pass for one
AVIF_HEAD = (b"\x00\x00\x00\x20ftypavif\x00\x00\x00\x00avifmif1miafMA1B" + b"\x00" * 32)

try:
    from PIL import Image
except ImportError:
    Image = None
try:
    import pillow_heif
except ImportError:
    pillow_heif = None

NO_PILLOW = "Pillow is not in this Python (environment.yml lists it; the installer adds it)"
NO_HEIF = "pillow-heif is not in this Python, so no HEIC can be made to test with"


def heic(width=4, height=2, orientation=6):
    """A HEIC of a picture `width` x `height`, its left half red and its right
    half blue, whose EXIF says it is to be shown turned (6: 90 degrees
    clockwise) -- what a phone writes for a photo taken upright."""
    im = Image.new("RGB", (width, height), (255, 0, 0))
    im.paste((0, 0, 255), (width // 2, 0, width, height))
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x8825] = {2: (45.0, 30.0, 0.0)}      # a GPS position, which must not travel
    pillow_heif.register_heif_opener()
    out = io.BytesIO()
    im.save(out, "HEIF", exif=exif.tobytes(), quality=95)
    return out.getvalue()


class Library(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        self.old_dir = decks.set_dir(root / "exercises")
        self.old_lib = store.use_library(root / "library")
        self.old_tray = decks.set_clips_dir(root / "clips")
        self.root = root

    def tearDown(self):
        decks.set_dir(self.old_dir)
        store.use_library(self.old_lib)
        decks.set_clips_dir(self.old_tray)
        self.td.cleanup()

    def doc(self, body=""):
        return store.create("---\ntitle: Pictures\ntarget: fa\n---\n\n%s" % body)["id"]


class Kinds(unittest.TestCase):
    def test_the_bytes_say_the_kind(self):
        self.assertEqual(store._img_kind(WEBP), ".webp")
        self.assertEqual(store._img_kind(GIF), ".gif")
        self.assertEqual(store._img_kind(b"GIF87a" + b"\x00" * 10), ".gif")
        self.assertIsNone(store._img_kind(b"RIFF\x00\x00\x00\x00WAVEfmt "), "a WAV is not a WebP")
        self.assertFalse(store._is_heif(AVIF_HEAD), "an AVIF is not a HEIC")
        self.assertIsNone(store._img_kind(AVIF_HEAD))
        for name in ("cat.webp", "cat.gif"):
            self.assertTrue(store.IMG_NAME_RE.match(name), name)
        self.assertFalse(store.IMG_NAME_RE.match("cat.heic"), "no picture is stored as a HEIC")
        for twin in ("cat.webp.png", "cat.gif.png"):
            self.assertTrue(store.DERIVED_RE.search(twin), twin)

    @unittest.skipIf(pillow_heif is None or Image is None, NO_HEIF)
    def test_a_heic_is_known_by_its_box(self):
        data = heic()
        self.assertTrue(store._is_heif(data))
        self.assertIsNone(store._img_kind(data), "a HEIC is converted, never kept as it is")

    def test_tex_picture(self):
        self.assertEqual(texgen.tex_picture("images/a.webp"), "images/a.webp.png")
        self.assertEqual(texgen.tex_picture("images/a.GIF"), "images/a.GIF.png")
        self.assertEqual(texgen.tex_picture("images/a.svg"), "images/a.svg.pdf")
        self.assertEqual(texgen.tex_picture("images/a.jpg"), "images/a.jpg")


class StudioIntake(Library):
    def test_webp_and_gif_are_kept_as_they_came(self):
        doc = self.doc()
        self.assertEqual(store.save_image(doc, "Photo.WEBP", WEBP), "photo.webp")
        self.assertEqual(store.save_image(doc, "Moving.gif", GIF), "moving.gif")
        self.assertEqual((store.images_dir(doc) / "photo.webp").read_bytes(), WEBP)
        self.assertEqual((store.images_dir(doc) / "moving.gif").read_bytes(), GIF)
        self.assertEqual(store.save_image(doc, "photo.webp", WEBP), "photo.webp", "same bytes: reused")
        # the bytes, not the name: a WebP called .png is stored as .webp
        self.assertEqual(store.save_image(doc, "liar.png", WEBP), "liar.webp")
        listed = {i["name"] for i in store.list_images(doc)}
        self.assertTrue({"photo.webp", "moving.gif"} <= listed, listed)

    def test_refused_in_words(self):
        doc = self.doc()
        with self.assertRaises(store.StoreError) as e:
            store.save_image(doc, "x.bmp", b"BM" + b"\x00" * 50)
        self.assertIn("WebP, GIF, HEIC", str(e.exception))
        with self.assertRaises(store.StoreError) as e:
            store.save_image(doc, "x.avif", AVIF_HEAD)
        with mock.patch.object(store, "IMG_MAX", 10):
            with self.assertRaises(store.StoreError) as e:
                store.save_image(doc, "big.webp", WEBP)
        self.assertIn("larger than", str(e.exception))

    @unittest.skipIf(pillow_heif is None or Image is None, NO_HEIF)
    def test_a_heic_becomes_an_upright_jpeg(self):
        doc = self.doc()
        data = heic()
        name = store.save_image(doc, "IMG_0042.HEIC", data)
        self.assertEqual(name, "img_0042.jpg")
        stored = (store.images_dir(doc) / name).read_bytes()
        self.assertTrue(stored.startswith(b"\xff\xd8\xff"))
        with Image.open(io.BytesIO(stored)) as im:
            self.assertEqual(im.size, (2, 4), "turned upright, as the EXIF says")
            self.assertEqual(im.getexif().get(0x0112) in (None, 1), True,
                             "no orientation left to turn it twice")
            self.assertNotIn(0x8825, im.getexif(), "where it was taken stays behind")
            # 90 degrees clockwise: the left half (red) is on top now
            r, g, b = im.convert("RGB").getpixel((1, 0))
            self.assertGreater(r, 150)
            self.assertLess(b, 100)
        self.assertEqual(sorted(p.name for p in store.images_dir(doc).iterdir()), ["img_0042.jpg"],
                         "the original is not kept")
        self.assertEqual(store.save_image(doc, "IMG_0042.HEIC", data), "img_0042.jpg",
                         "the same HEIC again is the same JPEG, stored once")

    @unittest.skipIf(pillow_heif is None or Image is None, NO_HEIF)
    def test_a_heic_without_the_packages_is_refused_in_words(self):
        doc = self.doc()
        data = heic()
        for missing, words in (("PIL", "Pillow"), ("pillow_heif", "pillow-heif")):
            with mock.patch.dict(sys.modules, {missing: None}):
                with self.assertRaises(store.StoreError) as e:
                    store.save_image(doc, "photo.heic", data)
            self.assertIn("needs the package %s" % words, str(e.exception))
            self.assertIn("update from Settings", str(e.exception))
        self.assertFalse(store.images_dir(doc).exists() and any(store.images_dir(doc).iterdir()))


class DeckIntake(Library):
    def deck(self):
        s = decks.create_deck("Pictures", "fa")
        return s["folder"], s["slug"]

    def upload(self, fs, name, data):
        """The deck's upload door, as a page calls it."""
        sent = {}

        class H:
            query = {"name": [name]}
            path = "/api/decks/%s/%s/images?name=%s" % (fs[0], fs[1], urllib.parse.quote(name))

            def _body(self):
                return data

            def send_json(self, obj, status=200, *a, **k):
                sent.update(obj=obj, status=status)

        try:
            with mock.patch.object(deckroutes, "_q1", lambda h, k, d="": h.query.get(k, [d])[0]):
                deckroutes.api_image_upload(H(), *fs)
        except decks.DeckError as e:
            return 400, {"ok": False, "error": str(e)}
        return sent["status"], sent["obj"]

    def test_webp_and_gif(self):
        fs = self.deck()
        status, obj = self.upload(fs, "Cat.webp", WEBP)
        self.assertEqual((status, obj["path"]), (201, "images/cat.webp"))
        status, obj = self.upload(fs, "cat.gif", GIF)
        self.assertEqual((status, obj["path"]), (201, "images/cat.gif"))
        self.assertEqual(decks.image_file(*fs, "cat.webp").read_bytes(), WEBP)
        # a card naming them is not warned of
        self.assertEqual(decks._missing_media(decks.deck_dir(*fs),
                                              "front-image: images/cat.webp\nback-image: images/cat.gif"),
                         [])

    def test_refused(self):
        status, obj = self.upload(self.deck(), "x.avif", AVIF_HEAD)
        self.assertEqual(status, 400)
        self.assertIn("PNG, JPEG, WebP, GIF, HEIC, SVG and PDF", obj["error"])

    @unittest.skipIf(pillow_heif is None or Image is None, NO_HEIF)
    def test_heic(self):
        fs = self.deck()
        status, obj = self.upload(fs, "IMG_7.heic", heic())
        self.assertEqual((status, obj["path"]), (201, "images/img_7.jpg"))
        with Image.open(decks.image_file(*fs, "img_7.jpg")) as im:
            self.assertEqual(im.size, (2, 4))
        with mock.patch.dict(sys.modules, {"pillow_heif": None}):
            status, obj = self.upload(fs, "IMG_8.heic", heic(6, 2))
        self.assertEqual(status, 400)
        self.assertIn("pillow-heif", obj["error"])


class Paper(Library):
    @unittest.skipIf(Image is None, NO_PILLOW)
    def test_the_build_stages_a_png_of_each(self):
        doc = self.doc()
        store.save_image(doc, "still.webp", WEBP)
        store.save_image(doc, "moving.gif", GIF)
        out = self.root / "build"
        self.assertTrue(envsetup.stage_images(store.images_dir(doc), out))
        with Image.open(out / "images" / "still.webp.png") as im:
            self.assertEqual((im.format, im.size), ("PNG", (4, 2)))
        with Image.open(out / "images" / "moving.gif.png") as im:
            self.assertEqual(im.format, "PNG")
            self.assertEqual(im.convert("RGB").getpixel((0, 0)), (255, 0, 0), "the first frame")
        # the twins live in the build only, never among the document's pictures
        self.assertEqual(sorted(p.name for p in store.images_dir(doc).iterdir()),
                         ["moving.gif", "still.webp"])

    def test_without_pillow_the_build_says_why(self):
        doc = self.doc()
        store.save_image(doc, "still.webp", WEBP)
        with mock.patch.dict(sys.modules, {"PIL": None}):
            with self.assertRaises(RuntimeError) as e:
                envsetup.stage_images(store.images_dir(doc), self.root / "build")
        self.assertIn("still.webp is a WebP picture", str(e.exception))
        self.assertIn("needs the package Pillow", str(e.exception))

    def test_the_tex_points_at_the_twins(self):
        md = ("---\ntitle: P\ntarget: fa\n---\n\n![a](images/still.webp)\n\n![b](images/moving.gif)\n\n"
              "![c](images/photo.jpg)\n")
        fm, blocks = mdparser.parse(md)
        tex = texgen.generate(fm, blocks)
        self.assertIn("{images/still.webp.png}", tex)
        self.assertIn("{images/moving.gif.png}", tex)
        self.assertIn("{images/photo.jpg}", tex)
        self.assertNotIn("{images/still.webp}", tex)


if __name__ == "__main__":
    unittest.main()
