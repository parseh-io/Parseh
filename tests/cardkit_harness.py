#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The toolbox tests/cardkit.mjs drives: the REAL hub (serve.main) on a
temporary tree, with a narrated book and a film whose sound can be measured.

    python3 tests/cardkit_harness.py build <tmp>
        makes <tmp>/root: books/english/mini-en (the fixture) with a narration
        and its timings, the reader built, and audio/slow.wav (below);
        youtube/videos/english/<id> with a media.mp4.  Prints one line of JSON
        saying what is where.
    python3 tests/cardkit_harness.py serve <tmp> <port> [--no-ffmpeg] [--tray <name>]
        serve.main() on 127.0.0.1:<port> over <tmp>/root, the studio library,
        the exercise decks, the Anki store with its sync inbox and the clip
        tray (<tmp>/<name>, default tray) all inside <tmp>.  --no-ffmpeg makes the machine one
        without ffmpeg (audiofile.ffmpeg answers None), so the cut routes
        answer 409 {record: true} and the page records the clip itself.

THE SOUND IS A PATTERN, so a cut is measurable: a 440 Hz tone for 0.6 s at
every whole second from 1 to 7, silence between -- a clip [1.8, 3.3] starts
0.2 s before a tone and a clip that starts late or early says so by where its
first tone begins.  audio/slow.wav holds a tone at every whole second for
45 s, uncompressed, for the page to record under a throttled connection.
Never touches the real books/, clips/, exercises/ or markdown/library/.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for folder in ("markdown/exlex", "markdown/app", "youtube/lib", "lib", "."):
    sys.path.insert(0, str(REPO / folder))

VIDEO = "street-market-a1b2c3"
TONE = ("aevalsrc='if(gte(t\\,1)*lt(t\\,7.6)*lt(mod(t\\,1)\\,0.6)\\,"
        "0.8*sin(2*PI*440*t)\\,0)':s=44100:d=8")
SLOW = "aevalsrc='if(lt(mod(t\\,1)\\,0.6)\\,0.8*sin(2*PI*440*t)\\,0)':s=48000:d=45"


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + [str(a) for a in args], check=True)


def build(tmp):
    os.chdir(str(REPO))
    import books
    import texparse
    import timestamp as ts
    import serve
    root = tmp / "root"
    book = root / "books" / "english" / "mini-en"
    book.parent.mkdir(parents=True)
    shutil.copytree(REPO / "tests/fixtures/books/english/mini-en", book,
                    ignore=shutil.ignore_patterns("reader"))
    (book / "audio").mkdir()
    ff("-f", "lavfi", "-i", TONE, "-ac", "1", "-c:a", "libmp3lame", "-q:a", "2",
       book / "audio" / "part1.mp3")
    # 45 s of plain 48 kHz stereo WAV (1536 kbit/s) with a tone at every whole
    # second: a throttled connection loads it slower than it plays
    ff("-f", "lavfi", "-i", SLOW, "-ac", "2", "-c:a", "pcm_s16le", book / "audio" / "slow.wav")
    b = books.Book(str(book))
    subs = [x for ch in texparse.parse_book(b.main, b.lang) for pp in ch.paragraphs for x in pp.subs]
    serve.set_narrations(b, [{"id": "n1", "audio": "audio/part1.mp3", "transcript": "",
                              "from": subs[0].num, "to": ""}])
    b = books.Book(str(book))
    ts._bind(b)
    # the first sentence over the first three tones; the rest share the tail
    cuts = [0.8, 3.9] + [round(3.9 + 3.9 * (k + 1) / (len(subs) - 1), 2) for k in range(len(subs) - 1)]
    recs = {}
    for k, x in enumerate(subs):
        recs[ts.subkey(x)] = {"t0": cuts[k], "t1": cuts[k + 1], "conf": 1.0, "src": "manual",
                              "label": x.num}
    (book / "timings.json").write_text(json.dumps(
        {"audio": "audio/part1.mp3", "book": b.slug, "generated_by": "cardkit_harness",
         "subs": recs}, ensure_ascii=False, indent=1), encoding="utf-8")
    for cmd in (["lib/timestamp.py", "--book", str(book), "--from-sidecar"],
                ["lib/tex2html.py", "--book", str(book)]):
        r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True, cwd=str(REPO))
        if r.returncode:
            raise SystemExit(r.stderr or r.stdout)
    # The reader links lib/ relatively, from where it was built to where the
    # toolbox is; served from the temporary root that path climbs out of the
    # site, so it is written as the hub's own absolute one.
    out = book / "reader"
    climb = os.path.relpath(str(REPO), str(out)).replace(os.sep, "/") + "/"
    for page in out.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        page.write_text(text.replace(climb, "/"), encoding="utf-8")
    # the hub answers /lib/... and /youtube/lib/... off its root
    (root / "youtube").mkdir()
    os.symlink(str(REPO / "lib"), str(root / "lib"))
    os.symlink(str(REPO / "youtube" / "lib"), str(root / "youtube" / "lib"))
    vdir = root / "youtube" / "videos" / "english" / VIDEO
    vdir.mkdir(parents=True)
    ff("-f", "lavfi", "-i", "testsrc=duration=8:size=160x120:rate=10", "-f", "lavfi", "-i", TONE,
       "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "1",
       vdir / "media.mp4")
    (vdir / "video.json").write_text(json.dumps(
        {"id": VIDEO, "url": "", "title": "Street market", "title_native": "Street market",
         "channel": "", "language": "en", "gloss": "en", "duration": "0:07"}), encoding="utf-8")
    # The middle caption is GLOSSED -- its chunks joined with a space give its
    # text back, as check_annotations asks -- because a caption with no chunks
    # draws no phrases, and a phrase is the only thing in a transcript that can
    # be tapped for a gloss.  tests/mobile_pages.mjs needs one to drive the
    # subtitles over a video on the whole screen; the other two are left plain,
    # so both kinds of caption are drawn.
    (vdir / "annotations.json").write_text(json.dumps(
        {"video": VIDEO, "language": "en", "segments": [
            {"start": 0, "text": "Hello there."},
            {"start": 2, "text": "The market opens early.",
             "chunks": [{"fa": "The market", "en": "the market"},
                        {"fa": "opens early.", "en": "opens early"}]},
            {"start": 5, "text": "Bring a bag."}]}), encoding="utf-8")
    for d in ("library", "exercises", "anki"):
        (tmp / d).mkdir()
    print(json.dumps({"book": "/books/english/mini-en", "reader": "/books/english/mini-en/reader/",
                      "video": VIDEO, "labels": [x.num for x in subs], "times": cuts}))


def serve_it(tmp, port, no_ffmpeg, tray):
    import audiofile
    import clips
    import decks
    import store
    if no_ffmpeg:
        audiofile.ffmpeg = lambda: None
    clips.set_dir(tmp / tray)
    import serve
    import ytpages
    for st in {store, serve.studio.store}:
        st.LIB = tmp / "library"
        if hasattr(st, "set_clips_dir"):
            st.set_clips_dir(tmp / tray)
    decks.set_dir(tmp / "exercises")
    if hasattr(decks, "set_clips_dir"):
        decks.set_clips_dir(tmp / tray)
    # the reading place and the settings the toolbox keeps (lib/prefs.py):
    # into the temporary tree, never into the real checkout's config/
    import analysisconfig                                          # noqa: E402
    import prefs
    prefs.STORE = str(tmp / "config" / "prefs.json")
    analysisconfig.STORE = str(tmp / "config" / "analysis.json")
    # and the door that says who may reach Parseh (lib/network.py): into
    # the temporary tree too, so a suite can neither read the owner's own
    # settings nor shut his Wi-Fi door by running
    import network
    network.STORE = str(tmp / "config" / "network.json")
    # and the LaTeX drawings' themes, their drawings and their packages
    import latexthemes, latexdraw, texpackages
    latexthemes.STORE = str(tmp / "config" / "latex.json")
    # and the prompts a person wrote (lib/prompts.py)
    import prompts
    prompts.STORE = str(tmp / "config" / "prompts.json")
    latexdraw.DRAWN = str(tmp / "latex-drawn")
    texpackages.TREE = str(tmp / "texmf")
    import texmf_fixture  # what the themes add to the base, as if Parseh had got it
    texmf_fixture.pretend_got(texpackages, latexthemes)
    # and the two memories of what a phone may keep (lib/offline.py): the
    # checksums of files by absolute path, and where each kept thing lives.
    # Left pointing at the checkout's config/, every suite booted through
    # here (mobile_pages among them) wrote its temporary tree's paths into
    # the owner's own digests.json and wheres.json
    import offline
    offline.DIGESTS = str(tmp / "config" / "digests.json")
    offline.WHERES = str(tmp / "config" / "wheres.json")
    # and the languages added on this machine (lib/newlang.py keeps a copy of
    # lib/languages.py's path) and the speech settings
    import languages, newlang, speechconfig
    languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")
    speechconfig.CONFIG = tmp / "config" / "speech.json"
    serve.ROOT = str(tmp / "root")
    serve._AtRoot.directory = str(tmp / "root")
    ytpages.VIDEOS = str(tmp / "root" / "youtube" / "videos")
    serve.ANKI = ytpages.ANKI = str(tmp / "anki")
    # the sync wizard's inbox is worked out from the real anki/ when ytpages
    # is imported: an .apkg dropped on /anki/sync/ lands in the tree too
    ytpages.INBOX = str(tmp / "anki" / "inbox")
    sys.argv = ["serve.py", "--http", "--local", str(port)]
    serve.main()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "build":
        build(Path(sys.argv[2]))
    elif len(sys.argv) >= 4 and sys.argv[1] == "serve":
        args = sys.argv[4:]
        tray = args[args.index("--tray") + 1] if "--tray" in args else "tray"
        serve_it(Path(sys.argv[2]), int(sys.argv[3]), "--no-ffmpeg" in args, tray)
    else:
        sys.exit(__doc__)
