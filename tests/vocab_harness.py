#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The toolbox tests/vocab_list.mjs drives: tests/later_harness.py's tree (the
mini readers of English, Persian, Arabic, Japanese, Hindi and Chinese, the
three-chapter Persian and English books whose later chapters arrive on demand,
the videos), with what the vocabulary list is driven on added:

  * the REST OF THE MINI FIXTURE BOOKS built as readers -- Italian, French,
    German, Spanish, Turkish, Catalan -- so that every language's mini book is
    on the shelf;
  * a PERSIAN VIDEO whose vocabulary lines are in the books' macros, one word
    of it in three captions with two meanings, and a verb;
  * an ARABIC one the same way, right to left with its own verb labels.

    python3 tests/vocab_harness.py build <tmp>     prints one line of JSON
    python3 tests/vocab_harness.py serve <tmp> <port>

Never touches the real books/, config/ or videos (later_harness serves through
tests/cardkit_harness.py's serve_it, which points every store at the tree).
"""
import contextlib
import io
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "lib"))

FA_MACRO = "persian-words-b2c3d4"
AR_MACRO = "arabic-words-e5f6a7"
# [text, meaning, vocabulary line]
FA_CAPS = [
    (0, "کتاب را دیدم", [("کتاب را", "the book", r"\dw{کتاب}{ketāb} book"),
                          ("دیدم", "I saw", r"\vb{دیدن}{didan}{بین}{bin}{دید}{did}{to see}")]),
    (2, "دوستم را دیدم", [("دوستم را", "my friend", r"\dw{دوست}{dust} friend"),
                           ("دیدم", "I met", r"\vb{دیدن}{didan}{بین}{bin}{دید}{did}{to meet}")]),
    (4, "كتاب خوب است", [("كتاب خوب", "a good book", r"\dw{كتاب}{ketāb} book; \dw{خوب}{xub} good"),
                          ("است", "is", "")]),
    (6, "باز دیدم", [("باز", "again", r"\pw{باز} again"),
                      ("دیدم", "I saw", r"\vb{دیدن}{didan}{بین}{bin}{دید}{did}{to see}")]),
]
AR_CAPS = [
    (0, "خرج الثعلب", [("خرج", "went out", r"\vb{خَرَجَ}{ḫaraja}{يَخْرُجُ}{yaḫruju}{خُرُوج}{ḫurūj}{to go out}"),
                        ("الثعلب", "the fox", r"\dw{ثَعْلَب}{ṯaʿlab} fox, pl. \pw{ثَعَالِب}")]),
    (3, "رأى الثعلب", [("رأى", "saw", r"\vb{رَأَى}{raʾā}{يَرَى}{yarā}{رُؤْيَة}{ruʾya}{to see}"),
                        ("الثعلب", "the fox", r"\dw{ثعلب}{ṯaʿlab} fox")]),
]


def build(tmp):
    os.chdir(str(REPO))
    import books
    import later_harness
    import mobile_harness
    with contextlib.redirect_stdout(io.StringIO()) as said:
        later_harness.build(tmp)
    made = json.loads(said.getvalue().strip().splitlines()[-1])
    root = tmp / "root"
    for folder in ("italian", "french", "german", "spanish", "turkish", "catalan"):
        src = next((REPO / "tests/fixtures/books" / folder).iterdir())
        dst = root / "books" / folder / src.name
        if not dst.exists():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("reader", "audio"))
        mobile_harness.built_reader(dst)
        made["readers"][books.Book(str(dst)).lang.code] = "/books/%s/%s/reader/" % (folder, src.name)

    videos = root / "youtube" / "videos"
    film = videos / "english" / made["video"] / "media.mp4"

    def video(folder, vid, title, lang, caps):
        d = videos / folder / vid
        d.mkdir(parents=True, exist_ok=True)
        os.symlink(str(film), str(d / "media.mp4"))
        (d / "video.json").write_text(json.dumps(
            {"id": vid, "url": "", "title": title, "title_native": title, "channel": "",
             "language": lang, "gloss": "en", "duration": "0:08"}), encoding="utf-8")
        segs = []
        for start, text, chunks in caps:
            segs.append({"start": start, "text": text, "chunks": [
                dict({"fa": c[0], "en": c[1]}, **({"voc": c[2]} if c[2] else {})) for c in chunks]})
        (d / "annotations.json").write_text(json.dumps(
            {"video": vid, "language": lang, "segments": segs}, ensure_ascii=False), encoding="utf-8")

    video("persian", FA_MACRO, "Persian words", "fa", FA_CAPS)
    video("arabic", AR_MACRO, "Arabic words", "ar", AR_CAPS)
    made.update({"fa_macro": FA_MACRO, "ar_macro": AR_MACRO})
    print(json.dumps(made, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "build":
        build(Path(sys.argv[2]))
    elif len(sys.argv) >= 4 and sys.argv[1] == "serve":
        os.chdir(str(REPO))
        import later_harness
        later_harness.serve(Path(sys.argv[2]), int(sys.argv[3]))
    else:
        raise SystemExit(__doc__)
