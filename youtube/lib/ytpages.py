#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The video player's pages and endpoints, as functions the Parseh server calls.

This used to be youtube/serve.py, a server of its own on port 8770.  Since
the whole toolbox is served by ../../serve.py under one https address, the
player lives at BASE (= /youtube) and this module only *assembles* things:
the channel index, a channel's page, a video's player page, and the Anki
endpoints both readers share (the store itself is lib/anki_store.py).

Every function that answers a request takes the handler `h`, which offers
send_html / send_json / send_bytes, the pre-read request body in h._raw,
and the parsed query string in h.query -- the same small interface the
studio's route functions use, so one server can drive all three.

Pages are assembled per request from the directories under videos/:
drop a new  videos/<folder>/<id>/  (the folder is the language's, from
lib/languages.json: persian, japanese, ...) with a video.json and an
annotations.json and it appears on the index, with no build step and no
restart.  The index groups channels by language; a video's URL carries only
its id (/youtube/v/<id>/), since ids are unique across languages, and the
player page is told which folder to fetch from.
"""
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
import urllib.parse
import urllib.request

LIB = os.path.dirname(os.path.realpath(__file__))
HERE = os.path.dirname(LIB)                      # youtube/
ROOT = os.path.dirname(HERE)                     # the toolbox
TOOLBOX_LIB = os.path.join(ROOT, "lib")
VIDEOS = os.path.join(HERE, "videos")
ANKI = os.path.join(HERE, "anki")
# where an .apkg exported from Anki is dropped by the sync wizard.  It sits
# beside the decks but is not one: anki_store.decks() only sees directories
# holding a deck.json, so this can never be mistaken for a deck.
INBOX = os.path.join(ANKI, "inbox")
BASE = "/youtube"                                # where the server mounts us

for _p in (LIB, TOOLBOX_LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import bundle       # noqa: E402  which file of a video's own is its film
import chunker      # noqa: E402  the two ways a draft may be cut
import languages    # noqa: E402  the registry: folders, names, scripts, chips
import promptkit    # noqa: E402  the three parts every prompt is made of
import prompts      # noqa: E402  the prompts a person wrote, chosen by their id
import words        # noqa: E402  a word line proposed where an answer left one out
import wordline     # noqa: E402  and proved against the checker before it is given
import make_index   # noqa: E402  the bundle panel both index pages share
import anki_export  # noqa: E402  (stdlib-only)
import anki_store   # noqa: E402  the deck store, shared with the book reader
import import_apkg  # noqa: E402  bootstrap a deck the store has never held
import sync_apkg    # noqa: E402  pull Anki-side edits home before exporting
import check_annotations as CA  # noqa: E402  the transcript parser and the checks
import tidy as tidier          # noqa: E402  an automatic transcript, cut into sentences
import texwrite      # noqa: E402  NOT_TEXT and Refused -- edit_meta reuses both rather
                     # than restating them (its own docstring says why)
import wavefile      # noqa: E402  the shape of a sound a transcription held for a video
import filmkind      # noqa: E402  what a video's own media is, and a playable copy of a sound

APP_NAME = "Parseh"


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


_NOTED = set()          # placement notes already printed (once per process)


def _note(key, msg):
    if key not in _NOTED:
        _NOTED.add(key)
        print("note: " + msg, file=sys.stderr)


def video_dirs():
    """(folder, id, path) for every video directory, in a stable order.

    The layout is videos/<folder>/<id>/ -- the folder being a language's
    (lib/languages.json), the id the YouTube id.  A video.json found
    directly under videos/<name>/ is the layout before languages: still
    read, with a note to move it, its folder None.  Dot-directories
    (videos/.trash/, where a replaced video goes) are never content.
    """
    if not os.path.isdir(VIDEOS):
        return
    for name in sorted(os.listdir(VIDEOS)):
        top = os.path.join(VIDEOS, name)
        if name.startswith(".") or not os.path.isdir(top):
            continue
        if os.path.isfile(os.path.join(top, "video.json")):
            yield None, name, top                    # legacy: videos/<id>/
            continue
        for sub in sorted(os.listdir(top)):
            p = os.path.join(top, sub)
            if not sub.startswith(".") and os.path.isfile(os.path.join(p, "video.json")):
                yield name, sub, p


def _load_video(folder, name, path):
    """The meta of one directory, with the fields the pages need computed:
    "_dir" (what the player fetches: "<folder>/<id>"), "_lang" (the
    registry code), "_gloss" (the code its meanings are written in), the
    caption counts.  None when there is no usable video.json."""
    meta = read_json(os.path.join(path, "video.json"))
    if not isinstance(meta, dict) or "id" not in meta:
        return None
    # the JSON's language wins for rendering, the folder for the URL; the
    # two are expected to agree, and a disagreement is said once.  The
    # code goes through CA.lang_code: a malformed value (a number, a list)
    # must be an unknown language, not a crash that takes the index down
    L = languages.get_or_default(CA.lang_code(meta.get("language")))
    if folder is None:
        _note("flat:" + name, "youtube/videos/%s/ lies directly under videos/ -- "
              "move it to videos/%s/%s/" % (name, L.folder, name))
    elif languages.by_folder(folder) and folder != L.folder:
        _note("folder:" + name, "youtube/videos/%s/%s/ is filed under %s/ but its "
              "video.json says language %s (videos/%s/)" % (folder, name, folder, L.code, L.folder))
    ann = read_json(os.path.join(path, "annotations.json"))
    segs = ann.get("segments") if isinstance(ann, dict) else None
    segs = segs if isinstance(segs, list) else []
    meta["_dir"] = name if folder is None else folder + "/" + name
    meta["_lang"] = L.code
    # what the meanings are WRITTEN in, which is not what the video
    # teaches.  A code nobody can set is reported once and read as English:
    # an index that refused to draw because one video.json has a typo in a
    # field only the player uses would be the wrong trade, and
    # check_annotations.py makes the same typo an error, which is where
    # whoever wrote it meets it.
    try:
        meta["_gloss"] = languages.gloss(
            CA.lang_code(meta.get("gloss")) or None).code
    except KeyError:
        meta["_gloss"] = languages.DEFAULT_GLOSS
        _note("gloss:" + name, "youtube/videos/%s/video.json says \"gloss\": %r, "
              "which is not a language a gloss may be written in -- read as "
              "English" % (meta["_dir"], meta.get("gloss")))
    meta["_segments"] = len(segs)
    # a caption with chunks is one somebody glossed; the rest are the
    # video's own English, filled in from the transcript
    meta["_glossed"] = sum(1 for s in segs if isinstance(s, dict) and s.get("chunks"))
    # Which counts a video STARTED EMPTY as finished work: it has a chunk
    # under every caption and not a word written in one of them.  So the
    # cards ask the checker instead of deciding for themselves -- gloss_state
    # hands back how many chunks are still blank and how many were ever
    # asked for a gloss (a plain caption's, a chunk marked plain and a run of
    # the video's own English are legitimately blank and are not counted).
    meta["_blank"], meta["_glossable"] = CA.gloss_state(path)
    # "audio" for a sound with no picture, which the shelf's card says
    meta["_kind"] = bundle.film_kind(path, meta)
    return meta


def list_videos():
    """Every video that carries a video.json, newest first."""
    out = []
    for folder, name, path in video_dirs():
        meta = _load_video(folder, name, path)
        if meta is not None:
            out.append(meta)
    out.sort(key=lambda m: m.get("added", ""), reverse=True)
    return out


def find_video(vid):
    """The one video with this id, wherever its folder: (meta, path) or
    (None, None).  Ids are unique across languages, so the URL needs no
    folder; the first match in folder order wins if a copy was left behind.

    The directory name is the id, and is what the cards link; a directory
    named otherwise (check_annotations tolerates it with a warning) is
    still found by the id its video.json declares, so the YouTube id
    typed into a URL opens it too."""
    if not vid or "/" in vid or vid.startswith("."):
        return None, None
    for folder, name, path in video_dirs():
        if name == vid:
            meta = _load_video(folder, name, path)
            if meta is not None:
                return meta, path
    for folder, name, path in video_dirs():
        meta = _load_video(folder, name, path)
        if meta is not None and meta.get("id") == vid:
            return meta, path
    return None, None


def native_title(m):
    """The display title in the video's own language: title_native, or the
    legacy spelling title_fa that every Persian video.json still uses."""
    return m.get("title_native") or m.get("title_fa") or ""


def channel_slug(name):
    """A stable URL slug for a channel name.

    A name with no Latin letters or digits at all must not collapse to
    the constant "channel" -- two differently-named channels would
    silently share one page -- so a name that strips to nothing keeps
    itself unique via a short hash of the original.
    """
    s = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:60]
    if not s:
        s = "channel-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return s


def list_channels():
    """Every (language, channel) with at least one video, alphabetised
    within the language, languages in registry order.

    Each video already belongs to exactly one channel (its own "channel"
    field) and one language, so this is a pure grouping of list_videos()
    -- no separate channel data is stored anywhere.  A channel with videos
    in two languages appears once per language, under the same slug: the
    slug is the channel's, the entry's "lang" says which group it is in,
    and /youtube/c/<slug>/ lists the channel's videos of every language.
    """
    groups = {}
    for m in list_videos():
        name = m.get("channel") or "Unknown channel"
        slug = channel_slug(name)
        key = (m["_lang"], slug)
        g = groups.setdefault(key, {"slug": slug, "name": name, "lang": m["_lang"],
                                    "videos": []})
        g["videos"].append(m)
    order = {code: i for i, code in enumerate(languages.CODES)}
    chans = list(groups.values())
    chans.sort(key=lambda c: (order.get(c["lang"], len(order)), c["name"].lower()))
    return chans


def esc(s):
    return html.escape(str(s or ""), quote=True)


def inbox_files():
    """The .apkg exports dropped by the wizard, newest first."""
    out = []
    if not os.path.isdir(INBOX):
        return out
    for name in sorted(os.listdir(INBOX), reverse=True):
        if not name.endswith(".apkg"):
            continue
        try:
            st = os.stat(os.path.join(INBOX, name))
        except OSError:
            continue
        out.append({"file": name, "bytes": st.st_size,
                    "when": time.strftime("%Y-%m-%d %H:%M",
                                          time.localtime(st.st_mtime))})
    return out


def inbox_path(name):
    """The full path of an uploaded file, or None.

    A name that arrived over the wire never chooses a path: it must be a
    plain basename that is actually sitting in the inbox.
    """
    name = str(name or "")
    if not name or os.path.basename(name) != name or not name.endswith(".apkg"):
        return None
    path = os.path.join(INBOX, name)
    return path if os.path.isfile(path) else None


def _explain(e):
    """Turn the few failures that actually happen into something a person
    can act on, instead of a bare traceback string."""
    msg = str(e)
    if isinstance(e, ModuleNotFoundError) and "zstandard" in msg:
        return ("this export is in Anki's modern compressed format, which "
                "needs the zstandard package:  conda run -n ilya-frank pip "
                "install zstandard  (or re-export with 'Support older Anki "
                "versions' ticked)")
    if "not a database" in msg or "no usable collection" in msg:
        return ("that file is not an Anki deck export -- export with "
                "File > Export > Anki Deck Package (.apkg)")
    return msg


# ---------------------------------------------------------------- pages
def bar(where_html):
    """The brand strip every hub-level page opens with."""
    return (
        '<div class="parseh-bar">\n'
        '  <a class="home" href="/" title="the hub"><span class="glyph">پ</span>%s</a>\n'
        '  <span class="where">%s</span>\n'
        '  <span class="sp"></span>\n'
        '  <button type="button" data-parseh-theme title="theme">&#9680;</button>\n'
        '  <button type="button" class="stop" data-parseh-stop '
        'title="stop the server">&#9211; stop</button>\n'
        '</div>\n' % (APP_NAME, where_html))


def page_head(title_text, h1_html, sub_html, where_html, body_class="index",
              also=""):
    # body_class defaults to what every caller but the add page wants: the
    # add page asks for "index wizard" so that it and /books/add/ sit at the
    # same body.wizard main{max-width:820px} (lib/style.css), which already
    # has its matching footer rule.  Two sibling pages at two widths was an
    # accident of one hardcoded class.
    return (
        '<!doctype html>\n<html lang="en"><head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>%s &mdash; %s</title>\n'
        '<link rel="stylesheet" href="/lib/parseh.css">\n'
        '<link rel="stylesheet" href="%s/lib/style.css">\n'
        '<link rel="stylesheet" href="/lib/langs.css">\n'
        '<script src="/lib/parseh.js"></script>\n'
        '%s'
        '</head><body class="%s">\n%s<main>\n  <h1 class="idx">%s</h1>\n'
        '%s'
        % (esc(title_text), APP_NAME, BASE, also, esc(body_class),
           bar(where_html), h1_html,
           # a page with nothing to say under its title draws no line there
           '  <p class="sub">%s</p>\n' % sub_html if sub_html else ""))


PAGE_FOOT = """  <footer class="idx">
    %s
  </footer>
</main>
</body></html>
"""

FOOT_NOTE = (
    'Each video is a directory <code>youtube/videos/&lt;language&gt;/&lt;id&gt;/</code> '
    'with a <code>video.json</code> and an <code>annotations.json</code>. '
    'To add one, follow <code>youtube/PROMPT.md</code>.')

# the one place the Anki round-trip is explained and driven; linked from
# the index so it is found BEFORE a rebuild overwrites an edit, not after
SYNC_CARD = (
    '<a class="book sync" href="/anki/sync/">\n'
    '  <div class="chname">&#8646; Sync with Anki</div>\n'
    '  <div class="blurb">Edited your cards inside Anki? Pull those edits '
    'home first, then rebuild &mdash; so re-importing adds your new cards '
    'without overwriting anything you changed there.</div>\n'
    '</a>')


def video_card(m):
    # the link names the directory, as it always did: that is what the
    # player page looks up first, and it is the id unless someone renamed
    # the folder (check_annotations warns about that, and still passes)
    vid = m["_dir"].rsplit("/", 1)[-1]
    L = languages.get_or_default(m.get("_lang"))
    pending = m["_segments"] == 0
    tags = []
    if m.get("level"):
        tags.append('<span class="tag">%s</span>' % esc(m["level"]))
    if m.get("duration"):
        tags.append('<span class="tag">%s</span>' % esc(m["duration"]))
    if m.get("_kind") == "audio":
        # a sound has no thumbnail to be: the card says what it is
        tags.append('<span class="tag">&#9834; a sound</span>')
    if pending:
        tags.append('<span class="tag no">no annotations yet</span>')
    elif m.get("_blank"):
        # chunks, not captions: a video with blanks in it is being written,
        # and a caption counted as done because it has chunks under it would
        # say "6 captions glossed" over six empty ones
        tags.append('<span class="tag on">%d of %d chunks glossed</span>'
                    % (m["_glossable"] - m["_blank"], m["_glossable"]))
    elif m.get("_glossed", 0) < m["_segments"]:
        tags.append('<span class="tag on">%d of %d captions glossed</span>'
                    % (m["_glossed"], m["_segments"]))
    else:
        tags.append('<span class="tag on">%d captions glossed</span>' % m["_segments"])
    if m.get("added"):
        tags.append('<span class="tag">%s</span>' % esc(m["added"]))
    # data-lang on the card: the chip row filters by it and langs.css gives
    # it the language's font token; the native title says its own lang/dir
    # the x that takes it off the shelf, inside the card's own <a> as the
    # studio's is; parseh.js catches it in the capture phase, so the click
    # never follows the link, and the body names the video the route wants
    delete_btn = ('<button type="button" class="card-del" title="take this '
                  'video off the shelf" data-del="%s/api/delete" '
                  'data-what="%s" data-body=\'%s\'>&#10005;</button>'
                  % (BASE, esc(m.get("title") or vid),
                     esc(json.dumps({"video": vid}))))
    return (
        '<a class="book%s" href="%s/v/%s/" data-lang="%s">\n'
        '  %s\n'
        '  <div class="fa" lang="%s" dir="%s">%s</div>\n'
        '  <div class="by">%s</div>\n'
        '  <div class="lat">%s <i>&mdash; %s</i></div>\n'
        '  <div class="blurb">%s</div>\n'
        '  <div class="tags">%s</div>\n'
        '</a>' % (
            " pending" if pending else "", BASE, esc(vid), L.code, delete_btn,
            L.code, L.dir, esc(native_title(m) or m.get("title") or vid),
            esc(m.get("channel") or ""),
            esc(m.get("title") or vid), esc(m.get("channel") or "?"),
            esc(m.get("blurb") or ""),
            "".join(tags)))


def channel_card(c):
    n = len(c["videos"])
    # "fully glossed" has to mean no chunk left blank, or a video started
    # empty -- which has a chunk under every caption and nothing written in
    # one -- would be counted here as finished work
    glossed_videos = sum(1 for m in c["videos"] if m["_segments"] and
                        m["_glossed"] >= m["_segments"] and not m["_blank"])
    levels = sorted({m["level"] for m in c["videos"] if m.get("level")})
    tags = ['<span class="tag on">%d video%s</span>' % (n, "" if n == 1 else "s")]
    if glossed_videos:
        tags.append('<span class="tag">%d fully glossed</span>' % glossed_videos)
    for lvl in levels:
        tags.append('<span class="tag">%s</span>' % esc(lvl))
    return (
        '<a class="book chan" href="%s/c/%s/" data-lang="%s">\n'
        '  <div class="chname">%s</div>\n'
        '  <div class="tags">%s</div>\n'
        '</a>' % (BASE, esc(c["slug"]), esc(c["lang"]), esc(c["name"]), "".join(tags)))


def lang_head(L, n):
    """The heading a language's group of cards sits under -- the same
    markup as the books' library page (lib/make_index.py), styled by
    parseh.css: the English name, the native name in the language's own
    face, the count of videos.  It carries data-lang like the cards, so
    the chip row hides it together with them."""
    return ('<h2 class="lang-head" data-lang="%s"><span class="name">%s</span>'
            '<bdi class="native"%s>%s</bdi><span class="n">%d</span></h2>'
            % (esc(L.code), esc(L.name), L.html_attrs(), esc(L.native), n))


ADD_CARD = (
    '<a class="book sync add" href="%s/add/">\n'
    '  <div class="chname">&#65291; Add a video</div>\n'
    '  <div class="blurb">From YouTube, or a video or a sound already on this machine. '
    'The page asks where the video is and who writes the glosses &mdash; an '
    'LLM whose answer it checks, or you, in the player.</div>\n'
    '</a>' % BASE)


def index_page():
    """The channels, grouped under one heading per language, in registry
    order, with the shared chip row (lib/parseh.js filters the cards and
    the headings by the picked language and remembers the choice)."""
    chans = list_channels()
    counts = {}
    for c in chans:
        counts[c["lang"]] = counts.get(c["lang"], 0) + len(c["videos"])
    if not chans:
        body = '<p class="sub">No videos yet &mdash; add one below.</p>'
    else:
        # a.book[data-lang], not a.book: the add and sync cards carry no
        # language and must stay whatever chip is picked
        parts = [languages.chips_html(counts, selector="a.book[data-lang], .lang-head")]
        for L in languages.LANGS.values():
            mine = [c for c in chans if c["lang"] == L.code]
            if not mine:
                continue
            parts.append(lang_head(L, counts.get(L.code, 0)))
            parts.extend(channel_card(c) for c in mine)
        body = "\n".join(parts)
    head = page_head(
        "Videos", "Videos", "", "videos")
    pending = ''
    import asrpending
    for row in asrpending.listing():
        pending += ('<a class="book add" data-layout="browser" href="%s/add/?pending=%s"><div class="chname">Continue pending transcription</div><div class="blurb">%s · %s</div></a>'
                    % (BASE, esc(row['job']), esc(row['title']), esc(row['lang'])))
    return (head + body + ADD_CARD + pending + SYNC_CARD
            + make_index.bundle_panel("video", BASE + "/api/upload")
            + make_index.shelf_panel("video", BASE + "/api/backup",
                                     BASE + "/api/restore")
            + (PAGE_FOOT % FOOT_NOTE))


def channel_page(slug):
    """One channel's videos, of every language it has them in (each card
    says its language; the chip row is not repeated here -- a channel is a
    small list, and the language groups were the index's job)."""
    mine = [c for c in list_channels() if c["slug"] == slug]
    if not mine:
        return None
    name = mine[0]["name"]
    videos = [m for c in mine for m in c["videos"]]
    videos.sort(key=lambda m: m.get("added", ""), reverse=True)
    head = page_head(
        name, esc(name),
        '<a class="crumb" href="%s/">&lsaquo; all channels</a>' % BASE,
        '<a href="%s/">videos</a> &rsaquo; %s' % (BASE, esc(name)))
    body = "\n".join(video_card(m) for m in videos)
    return head + body + (PAGE_FOOT % FOOT_NOTE)


def bundle_bytes(video_dir):
    """What the player's ⤓ hands over, in bytes, or None where it cannot be
    said (a video.json the bundle would refuse, a directory gone)."""
    try:
        return bundle.payload_bytes("video", video_dir, bundle.video_mode(video_dir))
    except (bundle.BundleError, OSError):
        return None


def player_page(vid):
    """The player for one video, found across the language folders.

    The page is told everything its script needs about the language in
    window.YTFRANK.lang -- the registry record (languages.Lang.as_json),
    embedded, never fetched -- and where the annotations are:
    BASE/videos/<folder>/<id>/annotations.json, which serve.py's static
    prefix covers.  <html> carries data-lang (the font token from
    /lib/langs.css keys on it) and data-dir; the content elements set their
    own lang/dir attributes from the record, so the page's chrome stays
    left-to-right whatever the language reads.

    Beside it, window.YTFRANK.gloss: the language the meanings are written
    in (languages.Gloss.as_json), which may be a language the toolbox does
    not teach -- somebody may gloss Persian in Spanish -- and which the
    script uses for exactly the same job on the other half of a gloss
    cloud, the label and the lang/dir of every line that is prose rather
    than target text.
    """
    meta, _path = find_video(vid)
    if meta is None:
        return None
    L = languages.get_or_default(meta.get("_lang"))
    G = languages.gloss_or_default(meta.get("_gloss"))
    film = bundle.film_at(_path)
    with open(os.path.join(LIB, "player.html"), encoding="utf-8") as f:
        page = f.read()
    cfg = {"id": meta.get("id", vid),
           "ann": "%s/videos/%s/annotations.json" % (BASE, meta["_dir"]),
           # the video's own notes, served by the studio over this video's
           # markdown/ directory (markdown/app/notes.py)
           "notes": "%s/v/%s/notes" % (BASE, meta.get("id", vid)),
           "lang": L.as_json(), "gloss": G.as_json(),
           # THE FILM, where the video is a file on this machine rather than
           # an address on YouTube.  Nothing in video.json says so: the file
           # being there IS the fact, which is one less field to keep true.
           # It is served by the ordinary static route, which answers Range,
           # and that is what lets the element seek at all.
           "media": (("%s/videos/%s/%s" % (BASE, meta["_dir"], film))
                     if film else ""),
           # WHICH KIND OF VIDEO THIS IS, which `media` alone cannot say: a
           # local video whose film has been moved or deleted has no media
           # either, and without this the page reached for YouTube and tried
           # to play a video at an id YouTube has never heard of.  The id
           # says it (a local one is a slug and six hex), and a video written
           # before local ones existed has a URL and is not one.
           "local": bool(film) or (is_local_id(meta.get("id", ""))
                                   and not (meta.get("url") or "").strip()),
           # A SOUND WITH NO PICTURE says "audio": video.json's "kind", decided
           # once when the film was attached, or the extension for a video
           # made before there was one (bundle.film_kind).  The player draws a
           # bar with the waveform in place of a frame for it.
           # (A sound whose file has gone says so all the same, so that the page
           # is the bar's small box and not a black frame with nothing in it.)
           "kind": bundle.film_kind(_path, meta)
                   or ("audio" if meta.get("kind") == "audio" else "video"),
           # what the box that sends a film or a sound again may offer
           "accept": "audio/*,video/*," + ",".join(bundle.MEDIA_EXTS),
           # HOW BIG THE ⤓ DOWNLOAD IS: what the bundle will carry in the
           # shape the button asks for (lib/bundle.py's payload) -- for a
           # film on this machine, the film, which may be gigabytes and
           # which a browser will start downloading without a word
           "bundle_bytes": bundle_bytes(_path),
           # A TEXT READ OUT OF ITS WRITTEN ORDER (kanbun): video.json's
           # "reorders", the checker's flag, which says the words' readings
           # in a row are not the chunk's reading and are not to be held to it
           "reorders": bool(meta.get("reorders")),
           # video.json's own fields, by their own names, for the video-info
           # sheet -- __TITLE__/__TITLE_NATIVE__/__CHANNEL__ below are static
           # HTML, baked in once at page-render time, and cannot be read back
           # out of the DOM the way a form field can; edit_meta's own concern
           # is keeping this in step with what it just wrote
           "editable": {"title": meta.get("title", ""),
                       "title_native": meta.get("title_native", ""),
                       "channel": meta.get("channel", ""),
                       "level": meta.get("level", ""),
                       "blurb": meta.get("blurb", ""),
                       "reorders": bool(meta.get("reorders"))}}
    # inside a <script>, the one sequence that could end it early
    cfg_js = json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")
    for key, val in (("__ID__", meta.get("id", vid)),
                     ("__DIR__", meta["_dir"]),
                     ("__TITLE__", meta.get("title", vid)),
                     ("__TITLE_NATIVE__", native_title(meta)),
                     ("__CHANNEL__", meta.get("channel", "")),
                     ("__CHANSLUG__", channel_slug(meta.get("channel") or "Unknown channel")),
                     ("__URL__", meta.get("url", "")),
                     ("__LANG__", L.code),
                     ("__LANG_NAME__", L.name),
                     ("__LANG_DIR__", L.dir),
                     ("__KIND__", cfg["kind"]),
                     ("__GLOSS_NAME__", G.name)):
        page = page.replace(key, esc(val))
    return (page.replace("__YTFRANK__", cfg_js)
                .replace("__BASE__", BASE).replace("__APP__", APP_NAME))


def sync_page():
    with open(os.path.join(LIB, "sync.html"), encoding="utf-8") as f:
        return f.read().replace("__BASE__", BASE).replace("__APP__", APP_NAME)


def not_found_page(what, back_href, back_text):
    return page_head(
        "not found", "not found",
        '<a class="crumb" href="%s">&lsaquo; %s</a>' % (esc(back_href), esc(back_text)),
        "videos") + '<p class="sub">%s</p>' % esc(what) + (PAGE_FOOT % "")


# ------------------------------------------------------------ the Anki endpoints
# Shared by the book reader and the video player: both dashboards POST to
# these same paths, against the same store.
def anki_decks(h):
    """Every deck in the store, or -- with ?lang=<code> -- one language's.

    The dashboards ask for their own language's decks first (a card goes
    to a deck of its language, so those are the ones worth offering), and
    a page that asks for a language nobody has a deck in must get an
    empty list, not a 500: an unknown code is simply no language.
    """
    code = (h.query.get("lang") or [""])[0].strip().lower()
    if code and code not in languages.LANGS:
        return h.send_json([])
    h.send_json(anki_store.decks(ANKI, code or None))


def anki_build(h, slug, folder=None):
    """Build a deck's .apkg and hand it over as a download.

    /anki/build/<folder>/<slug>.apkg names the deck exactly.  The older
    /anki/build/<slug>.apkg (a bookmarked link, a page from before the
    languages) still works while the slug picks out ONE deck; when two
    languages hold a deck of that name the answer says so and names them,
    because building "whichever came first" would hand over the wrong
    language's cards without a word.
    """
    deck, hits = anki_store.find_deck(ANKI, slug, folder)
    if deck is None:
        if len(hits) > 1:
            return h.send_json(
                {"ok": False,
                 "error": "%d decks are called %r -- say which language: %s"
                          % (len(hits), slug,
                             ", ".join("/anki/build/%s/%s.apkg" % (d["folder"], d["slug"])
                                       for d in hits)),
                 "candidates": hits}, 409)
        return h.send_json({"ok": False, "error": "no deck %r here" % slug}, 404)
    try:
        out = anki_export.build_deck(os.path.join(ANKI, deck["path"]))
    except (OSError, ValueError, KeyError) as e:
        return h.send_json({"ok": False, "error": str(e)}, 404)
    with open(out, "rb") as f:
        blob = f.read()
    h.send_bytes(blob, "application/octet-stream", 200,
                 {"Content-Disposition": 'attachment; filename="%s"'
                  % os.path.basename(out)})


def _json_in(h, cap=12 * 1024 * 1024):
    raw = h._raw or b""
    if not 0 < len(raw) <= cap:
        raise ValueError("bad size (%d bytes)" % len(raw))
    try:
        data = json.loads(raw.decode("utf-8"))
    except RecursionError:
        raise ValueError("the request nests too deep to be read")
    # A lone surrogate in any text of the body -- a JSON escape a browser
    # sends for a broken paste -- is no character: every file here is
    # written in UTF-8, so it would fail at the first write, after the
    # staging directory was made, as a 500.  Refused before anything is
    # written, as serve.Handler._json_body refuses it for every other route.
    import glossregion      # lib/, on sys.path since the top of this file
    if glossregion.broken(data):
        raise ValueError("the request carries a broken character (an unpaired "
                         "surrogate) -- copy the text again")
    return data


def anki_preview(h):
    """The card rendered as the .apkg will show it -- lib/anki_store.py."""
    try:
        obj, status = anki_store.preview(_json_in(h), ANKI)
        return h.send_json(obj, status)
    except Exception as e:
        # never drop the socket with no answer: a wrong-shaped body must
        # come back as JSON the page can print, not a NetworkError
        return h.send_json({"ok": False, "error": str(e)}, 400)


def anki_add_card(h):
    """Store one card in the shared deck store -- lib/anki_store.py."""
    try:
        obj, status = anki_store.add_card(ANKI, _json_in(h))
        return h.send_json(obj, status)
    except Exception as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)


def sync_inbox(h):
    h.send_json({"ok": True, "files": inbox_files()})


def sync_upload(h):
    """Take the .apkg the wizard dropped and put it in anki/inbox/.

    This is the answer to "how do I get the export into the folder":
    the browser hands over the bytes, the server names the file (never
    the client -- a name from outside must never choose a path) and
    keeps it beside the decks.
    """
    try:
        raw = (h.query.get("name") or [""])[0]
        blob = h._raw or b""
        if not blob:
            return h.send_json({"ok": False, "error": "empty upload"}, 400)
        if blob[:2] != b"PK":
            return h.send_json(
                {"ok": False, "error": "that is not an .apkg (an Anki "
                 "package is a zip; this file does not start like one)"},
                400)
        stem = re.sub(r"[^A-Za-z0-9._ -]", "_", os.path.basename(raw))
        stem = re.sub(r"\.apkg$", "", stem, flags=re.I).strip() or "deck"
        name = "%s-%s.apkg" % (time.strftime("%Y%m%d-%H%M%S"), stem[:60])
        os.makedirs(INBOX, exist_ok=True)
        path = os.path.join(INBOX, name)
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, path)          # never a half file under a real name
        return h.send_json({"ok": True, "file": name, "bytes": len(blob),
                            "path": os.path.join("youtube", "anki", "inbox", name)})
    except Exception as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)


def sync_run(h):
    """Preview (dry) or apply the merge -- lib/sync_apkg.py."""
    try:
        data = _json_in(h, 1 << 20)
        path = inbox_path(data.get("file"))
        if path is None:
            return h.send_json({"ok": False, "error": "no such uploaded file"}, 404)
        dry = bool(data.get("dry", True))
        res = sync_apkg.run_sync(path, ANKI, dry_run=dry,
                                 delete_missing=bool(data.get("delete")))
        res["ok"] = True
        return h.send_json(res)
    except Exception as e:
        return h.send_json({"ok": False, "error": _explain(e)}, 400)


def sync_bootstrap(h):
    """Bring in a deck the store has never held -- lib/import_apkg.py."""
    try:
        data = _json_in(h, 1 << 20)
        path = inbox_path(data.get("file"))
        if path is None:
            return h.send_json({"ok": False, "error": "no such uploaded file"}, 404)
        dids = data.get("dids")
        dids = [int(d) for d in dids] if isinstance(dids, list) else None
        res = import_apkg.import_all(path, ANKI, only_dids=dids,
                                     merge_held=bool(data.get("merge")))
        res["ok"] = True
        return h.send_json(res)
    except Exception as e:
        return h.send_json({"ok": False, "error": _explain(e)}, 400)


def stats():
    """What the hub says about the videos and the decks: the totals, and
    per language ("by_lang": {code: {"videos", "channels"}}) for the hub's
    chip row.  "channels" counts distinct channels; a channel with videos
    in two languages is one channel in the total and one in each
    language's count."""
    chans = list_channels()
    videos = sum(len(c["videos"]) for c in chans)
    by_lang = {}
    for c in chans:
        b = by_lang.setdefault(c["lang"], {"videos": 0, "channels": 0})
        b["videos"] += len(c["videos"])
        b["channels"] += 1
    decks = anki_store.decks(ANKI)
    cards = sum(int(d.get("cards") or 0) for d in decks)
    return {"channels": len({c["slug"] for c in chans}), "videos": videos,
            "decks": len(decks), "cards": cards, "by_lang": by_lang}


# ============================================================ adding a video from the page
# The studio has a prompt page: copy the prompt, ask any LLM, paste the
# answer back.  This is the same loop for a video.  The page prepares the
# prompt from the pasted transcript (the captions numbered, with their start
# times, the plain English ones marked so the LLM leaves them alone), and
# then takes the LLM's JSON answer, checks it with the very tools the
# pipeline uses, and writes videos/<folder>/<id>/ -- transcript.txt
# verbatim, video.json, parts/*.json -- before running merge_parts and
# check_annotations on the result exactly as PROMPT.md prescribes, and then
# dropping the batches, which have no second job to do (see api_add).  The
# language comes from the page's select (the shared preference is its
# default); it decides which captions are plain, what the prompt says, and
# which folder the video is filed under.
DOCS = os.path.join(HERE, "docs")
YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
LEVELS = ("beginner", "lower-intermediate", "intermediate",
          "upper-intermediate", "advanced")
PART_SIZE = 25


def video_id(url):
    """The 11-character id out of any of the ways a YouTube URL is written."""
    u = (url or "").strip()
    if YT_ID.match(u):
        return u
    m = re.search(r"(?:[?&]v=|youtu\.be/|/shorts/|/embed/|/live/|/v/)([A-Za-z0-9_-]{11})", u)
    return m.group(1) if m else None


# A LOCAL VIDEO'S ID.  It becomes a directory name under videos/ and a
# segment of a URL, so it is the same shape lib/bundle.py's LEAF allows and
# for the same reasons: ASCII, no slashes, and never opening with a dot,
# which is how this toolbox hides its own scratch.  A YouTube id is eleven
# characters and this is a slug with six hex after it, so the two are not
# mistaken for one another by eye; nothing anywhere parses one as the other.
LOCAL_ID = re.compile(r"^(?!\.)[A-Za-z0-9][A-Za-z0-9._-]{2,80}$")


def is_local_id(s):
    return bool(s) and bool(LOCAL_ID.match(s)) and not YT_ID.match(s)


def local_id(seed, taken=None):
    """A fresh id for a video that is a file on this machine.

    Named after whatever the person called it -- the film or the title --
    so a directory listing reads as something, with six hex characters after
    it so that two lessons both called `lesson 1` are two videos.
    """
    base = unicodedata.normalize("NFKD", (seed or "").strip())
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:40].strip("-")
    base = base or "video"
    if not base[0].isalnum():
        base = "v" + base
    taken = set(taken or [])
    for _ in range(200):
        # SIX HEX, OR SEVEN.  A local id must not be shaped like a YouTube
        # one -- eleven characters of [A-Za-z0-9_-] -- because `is_local_id`
        # refuses those, and a four-letter slug plus a dash plus six hex is
        # exactly eleven.  So `test.mp4`, `film.mp4` and `demo.mp4` could
        # never be added at all: every candidate was refused and the loop
        # ran out.  One more character is the whole of the fix.
        vid = "%s-%s" % (base, uuid.uuid4().hex[:6])
        if len(vid) == 11:
            vid = "%s-%s" % (base, uuid.uuid4().hex[:7])
        if vid not in taken and is_local_id(vid):
            return vid
    raise ValueError("could not name this video")


def check_film(raw):
    """The path a request names, made absolute and checked -> (path, ext).

    Raises ValueError with a sentence for the page.  A film is named by a
    PATH and never by an upload's filename, and it is read here and nowhere
    else: what a URL carries is the video's id, and the film is found by
    listing the video's own directory.  A SOUND is named the same way and is
    accepted wherever a film is (bundle.MEDIA_EXTS).
    """
    if raw is not None and not isinstance(raw, str):
        raise ValueError("the film's path has to be text, and that is a %s"
                         % type(raw).__name__)
    raw = (raw or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("name the film: the path to a file on this machine")
    path = os.path.abspath(os.path.expanduser(raw))
    ext = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path):
        raise ValueError("no file at %s" % path)
    if ext not in bundle.MEDIA_EXTS:
        raise ValueError("%s is not a video this can play, nor a sound (videos: %s; "
                         "sounds: %s)" % (ext or "that", ", ".join(bundle.VIDEO_EXTS),
                                          ", ".join(e for e in bundle.SOUND_EXTS
                                                    if e not in bundle.VIDEO_EXTS)))
    return path, ext


def attach_film(video_dir, path):
    """Put the film beside the transcript, as `media.<ext>`.

    HARDLINKED where the filesystem allows it, which costs no disk and no
    time even for a two-hour film; copied where it does not (another
    filesystem has no link to make).  Either way what lands is a real file,
    so the bundle the download button writes carries it like any other
    content, and the video plays on the machine that unpacks it.

    A SOUND goes the same way, and what is decided about it -- whether it is a
    sound at all, whether a browser plays it, the playable copy where one is
    needed -- is decided here, once, by youtube/lib/filmkind.py.
    """
    path, ext = check_film(path)
    into = os.path.join(video_dir, "media" + ext)
    # THE NEW FILM ARRIVES BEFORE THE OLD ONE LEAVES.  It is linked under a
    # part name and renamed into place, so a link that fails half way -- no
    # space, no permission -- leaves the video with the film it already had
    # rather than with none.  Nothing here is ever a half file under a real
    # name, which is the rule the narration upload keeps too.
    part = into + ".part"
    if os.path.exists(part):
        os.unlink(part)
    how = "linked"
    try:
        os.link(path, part)
    except OSError:
        shutil.copy2(path, part)
        how = "copied"
    try:
        got = filmkind.settle(video_dir, part)
    except (OSError, ValueError):
        if os.path.exists(part):
            os.unlink(part)
        raise
    # a film that was SENT waited in .incoming/ for this: it is the video's now
    filmkind.release(path, VIDEOS)
    return {"film": got["film"], "how": how, "bytes": got["bytes"], "kind": got["kind"],
            "converted": got["converted"], "original": got["original"], "note": got["note"]}


def local_target(data, taken=None):
    """The id a request about a local film should use -> (path, ext, id).

    The id the page was given by `prepare` is kept if it is one, so that the
    prompt's `id:` line and the directory finally written agree; otherwise a
    fresh one is named after the film.
    """
    path, ext = check_film(data.get("path"))
    want = (data.get("id") or "").strip()
    if is_local_id(want):
        return path, ext, want
    seed = (data.get("title") or "").strip() or os.path.splitext(os.path.basename(path))[0]
    return path, ext, local_id(seed, taken)


def oembed(vid):
    """The real title and channel, from YouTube's oEmbed answer (best effort)."""
    try:
        q = urllib.parse.urlencode({"url": "https://www.youtube.com/watch?v=" + vid,
                                    "format": "json"})
        with urllib.request.urlopen("https://www.youtube.com/oembed?" + q,
                                    timeout=6) as r:
            d = json.loads(r.read().decode("utf-8"))
        return {"title": str(d.get("title") or ""),
                "channel": str(d.get("author_name") or "")}
    except Exception:
        return {}


def parse_transcript_text(text, lang="fa"):
    """parse_transcript reads a file; the page has the text in hand.  `lang`
    is a registry code or a Lang; it decides which captions are plain.

    The checker's own, which is the point: the panel this page reads and the
    panel the pipeline reads are read by one function.  (It used to write a
    temp file to borrow the file version; the checker now splits the two.)"""
    return CA.parse_transcript_text(text, lang)


# A subtitle cue: `00:00:06,000 --> 00:00:09,000`, with or without the hour,
# a comma (SubRip) or a dot (WebVTT), and whatever alignment settings WebVTT
# put after it.
CUE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*"
                 r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
# `<i>`, `<c.colorE5E5E5>`, and the inline word timings YouTube's automatic
# captions carry: `<00:00:07.199><c> سیب</c>`
TAGS = re.compile(r"<[^>]*>")


def subtitles_to_transcript(text):
    """A .srt or .vtt file as the transcript this toolbox already reads.

    Everything downstream -- parse_transcript, the prompt, the checker, the
    blank-gloss draft -- works from a pasted YouTube panel: a timestamp on
    its own line, the caption under it.  A subtitle file says the same thing
    with a different punctuation, so it is TRANSLATED rather than parsed a
    second way, and one format stays the only one anything downstream knows.

    AUTOMATIC CAPTIONS ROLL, and only those are collapsed.  YouTube's own
    captions repeat the line before with one phrase added, and the two cues
    OVERLAP in time -- the first has not ended when the second begins.  That
    overlap is the signal, and it is the only licence taken here: where two
    cues overlap and the second merely extends or repeats the first, what is
    already said is dropped from it.  Where they do NOT overlap, a repeat is
    somebody saying the same words again -- a refrain, a correction, `no, no`
    -- and it is kept, because deleting a caption a person wrote is worse
    than showing one twice.

    Nothing else is dropped.  A caption that is only digits -- a year, a
    price, `1979` -- is a caption; SubRip's cue NUMBERS never reach here,
    being on the far side of the timestamp line the scan below looks for.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.lstrip("\ufeff")
    lines = text.split("\n")
    cues, i = [], 0
    while i < len(lines):
        m = CUE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        def secs(h, mm, ss, ms):
            return int(h or 0) * 3600 + int(mm) * 60 + int(ss) + int(ms or 0) / 1000.0
        start = secs(m.group(1), m.group(2), m.group(3), m.group(4))
        end = secs(m.group(5), m.group(6), m.group(7), m.group(8))
        i += 1
        said = []
        while i < len(lines) and lines[i].strip() and not CUE.match(lines[i].strip()):
            # SubRip counts its cues, and not every file puts a blank line
            # before the next number.  A number is that count only when a
            # timestamp follows it -- which is what tells `2` the cue number
            # from `1979` the caption.
            if (lines[i].strip().isdigit() and i + 1 < len(lines)
                    and CUE.match(lines[i + 1].strip())):
                break
            one = re.sub(r"\s{2,}", " ", TAGS.sub("", lines[i]).strip())
            if one:
                said.append(one)
            i += 1
        line = " ".join(said).strip()
        if line:
            cues.append((start, end, line))
    # a file whose cues are out of order is still a transcript of the video,
    # and the video's duration is read off the last of them
    cues.sort(key=lambda c: c[0])
    out, last, last_end = [], "", -1.0
    for start, end, line in cues:
        if last and line != last and line.startswith(last):
            # THE ROLLING SIGNATURE, and it needs no clock: this cue is the
            # last one with more said after it.  Nobody writes a subtitle
            # that way on purpose.
            line = line[len(last):].strip()
            if not line:
                continue
        elif last and line == last and start <= last_end:
            # the same words again with no gap -- YouTube's automatic
            # captions repeat the whole line in a ten-millisecond cue before
            # extending it.  Said again LATER is somebody saying it again,
            # and that is kept.
            continue
        out.append(CA.stamp_of(start))
        out.append(line)
        last, last_end = line, end
    return "\n".join(out) + ("\n" if out else "")


def as_transcript(text):
    """Whatever was pasted, as the transcript everything downstream reads.

    The add page invites a .srt or .vtt to be pasted whole, and all three of
    its buttons must honour that: only the blank-gloss road did, so the same
    file that made a video one way was told "no captions found -- paste the
    transcript as YouTube shows it" the other.
    """
    text = (text or "")
    return subtitles_to_transcript(text) if looks_like_subtitles(text) else text


def looks_like_subtitles(text):
    """Is this a subtitle file rather than a pasted panel?

    CUE is anchored, so it is asked of each LINE: `search` over the whole
    text only ever matched a file whose very first character began a cue,
    which a SubRip file -- numbered, so it begins with `1` -- never does.
    """
    head = (text or "")[:4000]
    if head.lstrip().upper().startswith("WEBVTT"):
        return True
    return any(CUE.match(ln.strip()) for ln in head.split("\n"))


def fmt_time(sec):
    sec = int(sec)
    return "%d:%02d" % (sec // 60, sec % 60)


def secs_str(x):
    """A number of seconds as the prompt writes it: `8`, and `8.4` where the
    caption begins on a fraction (check_annotations.stamp_of writes the panel
    the same way).  A model that answers with a caption's start instead of
    its number has to name what it was given."""
    v = round(float(x or 0), 3)
    return str(int(v)) if v == int(v) else ("%.3f" % v).rstrip("0")


def glossaries():
    """The per-video-family word lists under docs/, by their own titles."""
    out = []
    for p in sorted(os.listdir(DOCS)) if os.path.isdir(DOCS) else []:
        if not (p.startswith("glossary-") and p.endswith(".md")):
            continue
        try:
            with open(os.path.join(DOCS, p), encoding="utf-8") as f:
                first = f.readline().strip().lstrip("#").strip()
        except OSError:
            continue
        out.append({"slug": p[len("glossary-"):-3], "title": first or p})
    return out


def proposed_words(text, L):
    """The word line a pasted draft would get for this text (lib/words.py,
    held to the video door's checks), or "" where none can be proposed."""
    if not (L and L.words and words.available(L.code)):
        return ""
    line = words.line(text, L.code)
    if not line or wordline.check(text, line, L, door=wordline.VIDEO)[0]:
        return ""
    return line


def caption_lines(captions, lang=None):
    """The numbered list the LLM works from, plain captions and chapters shown
    for context only.  `i` counts the captions that want glossing, exactly as
    slice_part.py and merge_parts.py count them.

    Given a language divided into words, each caption to gloss is followed by
    the machine's division of it -- `    words: …`, what a pasted draft gets --
    which the LLM starts its chunks' words from and corrects."""
    L = None if lang is None else languages.get_or_default(
        lang if isinstance(lang, str) else lang.code)
    lines, i = [], 0
    for c in captions:
        if c.get("chapter"):
            lines.append("— chapter: %s —" % c["chapter"])
        if c["plain"]:
            lines.append("(plain — not annotated) %ss  %s" % (secs_str(c["start"]), c["text"]))
        else:
            lines.append("[%d] %ss  %s" % (i, secs_str(c["start"]), c["text"]))
            w = proposed_words(c["text"], L)
            if w:
                lines.append("    words: %s" % w)
            i += 1
    return "\n".join(lines)


def lang_conventions(L):
    """docs/lang/<code>.md, the language's own conventions (the docs agent
    writes them; docs/languages.md section 9), without its H1, as the video
    prompt takes them (lib/promptkit.py cuts each prompt's).  A missing file
    is a one-line placeholder rather than an error: the prompt must still be
    copyable the day a language is added."""
    return promptkit.language_text("video-new", L)


def assembled_chat(glossary=None, lang=None, gloss=None, data=None, instructions=None,
                   custom=None, options=None):
    """docs/chat-prompt.md with its placeholders filled: the language's
    name, the generic conventions verbatim (the binding spec, one copy of
    it), the language's own block -- which holds the language's worked
    example (docs/lang/<code>.md, Example) -- a word list, and the
    language the meanings are to be WRITTEN in, which the template names
    where it asks for them.  In its three parts (lib/promptkit.py), the
    `data` the last one, and the `instructions` a person's own where they
    are given (lib/prompts.py), named `custom` in the version line.  `options`
    is what the request chose of the scheme of the transliteration and the
    short vowels (promptkit.OPTIONS).
    -> promptkit.Assembled"""
    L = languages.get_or_default(lang if isinstance(lang, str) else (lang.code if lang else None))
    G = gloss if isinstance(gloss, languages.Gloss) \
        else languages.gloss_or_default(gloss)
    chosen = promptkit.resolve("video-new", L, options)
    with open(os.path.join(DOCS, "conventions.md"), encoding="utf-8") as f:
        conv = f.read()
    # its own H1 would break the prompt's outline; the rest is the spec
    conv = re.sub(r"^# .*\n+", "", conv, count=1).strip()
    gl = ""
    if glossary and re.match(r"^[a-z0-9-]+$", glossary):
        gp = os.path.join(DOCS, "glossary-%s.md" % glossary)
        if os.path.isfile(gp):
            with open(gp, encoding="utf-8") as f:
                gl = ("## The word list this video belongs to\n\n"
                      "Transliterate and gloss these words exactly as listed, so "
                      "the video reads like the others of its family.\n\n" +
                      re.sub(r"^# .*\n+", "", f.read(), count=1).strip() + "\n")
    # the fields a reading language adds, said where the shape is shown
    kana_line = ("- `kana`: the reading of the whole chunk in kana, on every "
                 "chunk of %s text (the language has a reading; see its "
                 "conventions).\n" % L.name) if L.reading else ""
    # and the word line a words language adds, with the example its own
    # conventions show under ## Words, so no language's example lives here.
    # Where this Python can divide the language, each caption comes with the
    # machine's division under it (caption_lines): the words start there, as
    # they do for a text pasted in by hand, and the LLM corrects them
    words_line = words_check = words_received = ""
    if L.words:
        m = re.search(r"^## Words\n(?:(?!## ).*\n)*?    (\S[^\n]*)",
                      lang_conventions(L), re.M)
        example = (" -- `%s` --" % m.group(1)) if m else ""
        proposing = words.available(L.code)
        start = (" **Start from the `words:` line under the caption**: cut the "
                 "caption into chunks only between its words, give each chunk the "
                 "part of that line it covers, and correct every word boundary and "
                 "every reading that is wrong -- the line is a machine's proposal, "
                 "and a chunk's `words` must say what its %s says."
                 % ("`kana`" if L.reading else "`tr`")) if proposing else ""
        words_line = ("- `words`: the chunk divided into words, each word's "
                      "reading after it in parentheses%s on every chunk of %s "
                      "text. The words joined with nothing between them must be "
                      "`fa` exactly; `kana` or `tr` stays the reading of the "
                      "whole chunk (see ## Words in the conventions).%s\n"
                      % (example, L.name, start))
        words_check = ("- `words` on every chunk of %s text, rejoining `fa` "
                       "exactly, each reading covering its whole word%s;\n"
                       % (L.name, ", started from the caption's `words:` line and "
                          "corrected" if proposing else ""))
        if proposing:
            words_received = ("\nUnder each caption of %s text comes a second line, "
                              "`    words: <the caption divided into words>`: the "
                              "software's own division of it, the one it gives a "
                              "text pasted in by hand, with each word's reading in "
                              "parentheses. It is not a caption and has no `[i]`; "
                              "it is where your `words` start (below).\n" % L.name)
    tr_rule = ("`tr` and `en` on every chunk of %s text" % L.name if L.require_tr
               else "`en` on every chunk of %s text (`tr` is optional here)" % L.name)
    if L.reading:
        tr_rule = "`kana`, " + tr_rule
    return promptkit.assemble(
        "video-new", L, G,
        values={"KANA_LINE": kana_line, "WORDS_LINE": words_line,
                "WORDS_CHECK": words_check, "WORDS_RECEIVED": words_received,
                "TR_RULE": tr_rule, "GLOSSARY": gl},
        includes={"CONVENTIONS": conv}, data=data, instructions=instructions, custom=custom,
        options=chosen)


def chat_prompt(glossary=None, lang=None, gloss=None, options=None):
    """The prompt for a video before its captions -> str (assembled_chat)."""
    return assembled_chat(glossary, lang, gloss, options=options).text


def full_prompt(vid, meta, captions, glossary=None, lang=None, gloss=None, instructions=None,
                custom=None, options=None):
    return assembled_full(vid, meta, captions, glossary, lang, gloss, instructions, custom,
                          options).text


def assembled_full(vid, meta, captions, glossary=None, lang=None, gloss=None, instructions=None,
                   custom=None, options=None):
    """The whole prompt of a video from scratch: its captions and the facts
    about the video are the data, the last part.  -> promptkit.Assembled"""
    L = languages.get_or_default(lang if isinstance(lang, str) else (lang.code if lang else None))
    G = gloss if isinstance(gloss, languages.Gloss) \
        else languages.gloss_or_default(gloss)
    want = [c for c in captions if not c["plain"]]
    head = ["## This video", "", "- id: `%s`" % vid]
    if not is_local_id(vid):
        head.append("- url: https://www.youtube.com/watch?v=%s" % vid)
    else:
        head.append("- a %s on the reader's own machine, not on YouTube"
                    % ("recording" if meta.get("kind") == "audio" else "film"))
    if meta.get("title"):
        head.append("- title: %s" % meta["title"])
    if meta.get("channel"):
        head.append("- channel: %s" % meta["channel"])
    head.append("- language: %s (`%s`)" % (L.name, L.code))
    # said in the prompt's own words as well as the template's, because it
    # is the one instruction a model steeped in English glosses will drift
    # away from over four hundred captions
    head.append("- gloss language: **%s** (`%s`) — every `en`, and every "
                "meaning inside a `voc`, is written in %s%s"
                % (G.name, G.code, G.name,
                   "" if G.code == languages.DEFAULT_GLOSS else ", not in English"))
    head.append("- %d captions, %d of them to annotate (the rest are plain), "
                "about %s long" % (len(captions), len(want),
                                   fmt_time(captions[-1]["start"]) if captions else "?"))
    head += ["", "## The captions", "", "```", caption_lines(captions, L), "```", "",
             "Now answer with the JSON, and nothing else."]
    return assembled_chat(glossary, L, G, data="\n".join(head), instructions=instructions,
                          custom=custom, options=options)


def _json_blocks(text):
    """Every JSON document in the pasted answer, in the order they stand.

    One rule for every door that takes an LLM's answer, and it lives in
    lib/glossregion.py (json_blocks), which the region fill of a video or a
    book already on the shelf reads its answers with: a ```json fence must
    hold JSON, and one that does not parse is an error; a fence with no
    label (or another) that does not parse is a model's prose -- a quoted
    sentence, its working shown -- and is passed over instead of refusing
    the whole answer; with no fence that counts, the whole text, else its
    outermost {...}.  Imported here and not at the top: glossregion is
    shared with the books and the player's own doors, and is needed by
    nothing else in this file -- the shelf and the player's page must not
    fail to load over it, nor the two modules over importing each other.

    That rule includes a fence glued to the one before it: this page's
    repair loop asks for the LLM's corrected captions to be pasted UNDER its
    first answer, with the cursor where that answer ended, right after its
    closing ```, so the second block's ```json can land on the same line --
    glossregion reads it as the block it is (its _GLUED).  An answer that is
    not text at all (a request sent by hand) is an empty one, refused in
    words, never a crash."""
    import glossregion      # lib/, on sys.path since the top of this file
    return glossregion.json_blocks(text)


def _merge_answer(docs):
    """One video object and one caption list out of one or several blocks.

    Returns (video, caps, blocks): `blocks` stands beside `caps` and says
    which block each caption came from (0 for the first), because a caption
    given again in a LATER block is the model's correction of it -- the page
    asks for exactly that: the lines that were refused, pasted back to the
    LLM, and its answer pasted under the first one -- while the same caption
    twice inside one block is a model that lost its place (_align_answer)."""
    video, caps, blocks = {}, [], []
    for n, d in enumerate(docs):
        if not isinstance(d, dict):
            raise ValueError("a JSON block is not an object")
        if isinstance(d.get("video"), dict) and not video:
            video = d["video"]
        for c in d.get("captions") or d.get("segments") or []:
            caps.append(c)
            blocks.append(n)
        if not d.get("captions") and not d.get("segments") and "chunks" in d:
            caps.append(d)              # a lone caption object
            blocks.append(n)
    return video, caps, blocks


def _align_answer(caps, captions, blocks=None):
    """The answer's captions matched to the transcript's, in transcript order.

    Returns (parts, problems, missing): parts is what merge_parts wants --
    one {start, chunks} per caption that wants glossing -- and problems
    names every caption the answer missed, doubled or invented.

    `blocks` is _merge_answer's: the block each caption came from (None is
    one block for all).  A caption a LATER block gives again REPLACES the
    one before it, and is said in a note: that is the repair the page asks
    for -- the refused lines go back to the LLM, and the captions it
    corrects are pasted under its first answer.  The same caption twice in
    ONE block is still a problem, since nothing says which of the two the
    model meant.  A later block answering by start alone takes a caption
    nobody has answered yet before one it would be correcting, so a
    continuation whose first caption shares its start with the last one
    answered (two captions in the same displayed second) is not read as a
    correction of it.
    """
    want = [c for c in captions if not c["plain"]]
    plain_starts = {c["start"] for c in captions if c["plain"]}
    if blocks is None or len(blocks) != len(caps):
        blocks = [0] * len(caps)
    by_i, from_block, problems, extra, fixed = {}, {}, [], 0, []
    for c, n in zip(caps, blocks):
        if not isinstance(c, dict):
            problems.append("an entry in captions is not an object")
            continue
        i, st = c.get("i"), c.get("start")
        if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(want):
            key = i
        elif isinstance(st, (int, float)):
            near = lambda a, b: abs(float(a) - float(b)) < 0.05
            if (any(near(x, st) for x in plain_starts)
                    and not any(near(w["start"], st) for w in want)):
                extra += 1               # a plain caption, annotated anyway
                continue
            # free first, then one an earlier block answered (a correction);
            # never one this block has already answered
            cands = sorted((k in by_i, k) for k, w in enumerate(want)
                           if near(w["start"], st) and from_block.get(k) != n)
            if not cands:
                problems.append("an entry with start %s matches no caption "
                                "that wants glossing" % st)
                continue
            key = cands[0][1]
        else:
            problems.append("an entry has neither a usable \"i\" nor a \"start\"")
            continue
        if key in by_i:
            if from_block[key] == n:
                problems.append("caption [%d] (start %s) appears twice in the answer"
                                "%s" % (key, secs_str(want[key]["start"]),
                                        " (in the same block)" if len(set(blocks)) > 1
                                        else ""))
                continue
            fixed.append(key)            # a later block's correction
        by_i[key] = c
        from_block[key] = n
    missing = [k for k in range(len(want)) if k not in by_i]
    if missing:
        show = ", ".join("[%d] %ss" % (k, secs_str(want[k]["start"])) for k in missing[:12])
        problems.append("%d caption(s) missing from the answer: %s%s"
                        % (len(missing), show, " …" if len(missing) > 12 else ""))
    parts = [{"start": want[k]["start"], "chunks": by_i[k].get("chunks")}
             for k in range(len(want)) if k in by_i]
    if fixed:
        fixed = sorted(set(fixed))
        show = ", ".join("[%d] %ss" % (k, secs_str(want[k]["start"])) for k in fixed[:12])
        problems.append("note: %d caption(s) given again in a later block -- the "
                        "later one was taken: %s%s"
                        % (len(fixed), show, " …" if len(fixed) > 12 else ""))
    if extra:
        problems.append("note: %d plain caption(s) were annotated and ignored" % extra)
    return parts, problems, missing


def _answer_words(parts, L):
    """The word lines of an aligned answer, seen to before anything is checked
    or written.  Returns (problems, proposed).

    A "words" that is not text is a problem named by the answer's own caption
    [i]: the checker would name a segment of a file nobody has yet, and the
    page hands these lines back to the LLM that numbered them.  `parts` comes
    from _align_answer with nothing missing, so its index IS that [i].

    A chunk of the language's text that arrives without words -- the model
    left them out -- is given the line lib/words.py proposes, straight after
    fa where the key stands, when this Python has the analyzers and the
    proposal is one the checker takes; otherwise it stays without the key,
    since a blank line is an error and a chunk without words is legal
    forever.  Words the model wrote are kept as written, for the checker to
    judge, and a chunk marked plain never gets any.  `proposed` counts the
    lines given; the chunk lists in `parts` are changed in place.
    """
    problems, todo = [], []
    for i, part in enumerate(parts):
        chunks = part.get("chunks")
        for j, ch in enumerate(chunks if isinstance(chunks, list) else []):
            if not isinstance(ch, dict):
                continue                          # the checker says so
            if "words" in ch:
                if not isinstance(ch["words"], str):
                    problems.append("caption [%d] (start %s) chunk %d: words must be "
                                    "text, not %s" % (i, part.get("start"), j,
                                                      type(ch["words"]).__name__))
                continue
            fa = ch.get("fa")
            # the language's text only, as check_chunk tells it: the prompt
            # asks no words of a run of the video's own framing
            if not ch.get("plain") and isinstance(fa, str) and fa.strip() \
                    and (L.has_script(fa) if L.chars else True):
                todo.append((chunks, j))
    if problems or not (L.words and todo and words.available(L.code)):
        return problems, 0
    proposed = 0
    for chunks, j in todo:
        fa = chunks[j]["fa"]
        # the answer's own kana (or pinyin) for the chunk reads its words
        said = chunks[j].get("kana" if L.reading else "tr")
        line = words.line(fa, L.code, said if isinstance(said, str) else "")
        # a proposal the checker refuses (a control character in the text,
        # which the analyzer keeps as a word) is not given: the chunk went in
        # without words before, and a line nobody wrote must not be what
        # turns the answer away
        if not line or wordline.check(fa, line, L, door=wordline.VIDEO)[0]:
            continue
        got = {}
        for k, v in chunks[j].items():
            got[k] = v
            if k == "fa":
                got["words"] = line
        chunks[j] = got
        proposed += 1
    return problems, proposed


# The checker's own name for a caption, "segment 7 (start 12)", counts EVERY
# caption, the plain ones included, because that is what annotations.json
# holds; the prompt counts only the captions that want glossing, as "[5]".
# The lines a refused answer is sent back with are pasted to the LLM, which
# has only the prompt's numbers.  Only the name a message OPENS with: the
# rest may quote a caption's own words, which may say "segment" too.
_SEGMENT_IN = re.compile(r"^segment (\d+)(?: \(start ([^)]*)\))?")


def _as_prompt_numbers(msg, captions):
    """A checker message about the staged answer, with the "segment N" it
    opens with said the way the prompt said it: "caption [i] (start S)",
    the start kept so a person can find it as well.  A plain caption has
    no [i] and is named by its start; a number the transcript does not
    have is left as the checker wrote it."""
    idx, i = {}, 0
    for n, c in enumerate(captions):
        if not c["plain"]:
            idx[n] = i
            i += 1

    def name(m):
        n = int(m.group(1))
        if n >= len(captions):
            return m.group(0)
        start = m.group(2) if m.group(2) is not None \
            else secs_str(captions[n]["start"])
        if n in idx:
            return "caption [%d] (start %s)" % (idx[n], start)
        return "the plain caption at %ss" % start
    return _SEGMENT_IN.sub(name, msg, count=1)


def _segments(parts, captions):
    """What merge_parts.py will write, built the same way, for checking first."""
    segs, it = [], iter(parts)
    for cap in captions:
        if cap["plain"]:
            sg = {"start": cap["start"], "plain": True}
        else:
            sg = dict(next(it))
        sg["text"] = cap["text"]
        if cap["chapter"]:
            sg["chapter"] = cap["chapter"]
        segs.append(sg)
    return segs


def posted_lang(value):
    """The language a request names, refused rather than defaulted.

    Nothing said still means the registry's default -- the page always sends
    one, so an empty field is a caller with no opinion.  A code that is not a
    language, though, is somebody's mistake, and answering it with Persian
    files the video under the wrong folder, calls the wrong captions plain
    and asks the prompt for the wrong script.  `/api/local` already refused
    it (draft.py raises); the two roads in now say the same thing.
    """
    code = CA.lang_code(value) or ""
    if code and code not in languages.LANGS:
        raise KeyError("%r is not a language this toolbox teaches (%s)"
                       % (value, ", ".join(languages.LANGS)))
    return languages.get_or_default(code)


def one_source(data):
    """A video is an address or a file, and saying both is a question.

    Given both, the URL used to win and the film was dropped without a word
    -- the person who typed a path and pasted a URL got a YouTube video and
    no sign that the file they named had been ignored.
    """
    if (data.get("url") or "").strip() and (data.get("path") or "").strip():
        raise ValueError("a video is either an address or a file on this "
                         "machine, and this names both -- clear whichever "
                         "one you did not mean")


def posted_gloss(value):
    """The gloss language a request names; nothing said means English, and
    a code no gloss may be written in raises KeyError with the registry's
    own sentence in it.  The value goes through CA.lang_code first, so a
    malformed one (a number, a list) is an unknown gloss language and not a
    traceback out of the registry's .strip()."""
    return languages.gloss(CA.lang_code(value) or None)


def _tidy_prompt(h, captions, L, asked):
    """The tidy's prompt, answered: Parseh's own where `asked` is true, and made
    from one of the person's where it is that prompt's id (lib/prompts.py)."""
    try:
        chosen = prompts.resolve("transcript-tidy", asked, L)
        made = tidier.prompt(captions, L.code, chosen and chosen.instructions,
                             chosen and chosen.name)
    except prompts.PromptsError as e:
        return h.send_json({"ok": False, "error": str(e)}, e.status)
    except promptkit.PromptError as e:
        return h.send_json({"ok": False, "error": prompts.unmade(chosen, e) if chosen else
                            "the prompt could not be made: %s" % e}, 400)
    out = {"ok": True, "prompt": made, "lang": L.code}
    if chosen:
        out["custom"] = {"id": chosen.id, "name": chosen.name, "kind": chosen.kind}
    return h.send_json(out)
def _word_document(data, lang, captions):
    """The held word tape, temporarily brought to the current editor panel.

    A job token is a capability minted by sttjobs.  It is never a pathname,
    and a pasted transcript without one remains exactly the old, panel-only
    road.  The document is saved only when the editor accepts its panel;
    tidy may therefore try a result and be undone without leaving a second
    source of truth on disk.
    """
    token = data.get("word_job")
    if not isinstance(token, str):
        return None
    try:
        import wordtimes
        doc = wordtimes.load(token)
        if doc is None or doc.get("language") != lang.code:
            return None
        doc = wordtimes.sync(doc, captions, lang.code)
        shift = data.get("word_shift")
        if shift not in (None, "", 0, 0.0):
            doc = wordtimes.shift_all(doc, shift)
        # The first open only asks to project held state; later editor calls
        # carry the complete authoritative pin set (including deliberate
        # removals after a confirmed structural edit).
        if "word_pins" in data:
            doc = wordtimes.set_pins(doc, data.get("word_pins") or [])
        return doc
    except (ValueError, TypeError):
        return None


def _word_starts(doc, captions):
    """Apply boundary pins/word starts to the panel projection in place."""
    if doc is None:
        return captions
    import wordtimes
    for caption, state in zip(captions, doc.get("captions") or []):
        start = wordtimes.caption_start(doc, state)
        if start is not None:
            caption["start"] = start
    return captions


def api_transcript(h):
    """The transcript the add page is editing, read or written.

    Both directions, because both are one pair of functions in the checker
    and there must not be a second spelling of the panel anywhere:

      {transcript, lang}  -> {captions, text}   what was pasted, parsed
                                                (a .srt or .vtt translated
                                                first, as every other road
                                                here does), and the panel
                                                written back from it
      {captions, lang}    -> {captions, text}   the captions being edited,
                                                written as a panel -- and
                                                read again from what was
                                                written, so the answer is
                                                what the pipeline will see
      ...with `tidy`      -> the same, the captions cut into sentences and
                             timed again first (youtube/lib/tidy.py), and
                             `notes` saying what it did
      ...with `prompt`    -> {prompt}: the same job written out for an LLM,
                             for whoever would rather have a model read the
                             transcript than an algorithm.  The answer comes
                             back into the box as an ordinary panel, by the
                             first form above.  `prompt` is true for Parseh's
                             own, or the id of one of the person's prompts
                             (lib/prompts.py), whose text goes after Parseh's
                             instructions or in place of them, as it says;
                             the contract and the transcript stay Parseh's.

    Every answer carries `can_tidy` and, where it cannot, `why`.  The tidy
    button is there for every language the toolbox teaches and works once
    that language's dictionary is installed; the prompt needs nothing
    installed at all.

    This is the ONLY door the subtitle editor has, and it writes nothing:
    the page puts `text` back in its box, and the roads that build a video
    go on reading that box as they always did.  Editing is a step of ADDING
    a video and of nothing else -- there is no route here that edits the
    transcript of a video already in the player.
    """
    try:
        data = _json_in(h, 8 << 20)
    except Exception as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    try:
        L = posted_lang(data.get("lang"))
    except KeyError as e:
        return h.send_json({"ok": False, "error": str(e.args[0])}, 400)
    notes = []
    word_doc = None
    given = data.get("captions")
    if given is not None:
        if not isinstance(given, list):
            return h.send_json({"ok": False, "error": "captions must be a list"}, 400)
        clean = []
        for i, c in enumerate(given):
            if not isinstance(c, dict):
                return h.send_json({"ok": False,
                                    "error": "caption %d is not an object" % i}, 400)
            start = c.get("start")
            if isinstance(start, bool) or not isinstance(start, (int, float)):
                return h.send_json({"ok": False, "error":
                                    "caption %d: start must be a number of seconds" % i}, 400)
            if not isinstance(c.get("text"), str):
                return h.send_json({"ok": False,
                                    "error": "caption %d: text must be text" % i}, 400)
            chapter = c.get("chapter")
            if chapter is not None and not isinstance(chapter, str):
                return h.send_json({"ok": False,
                                    "error": "caption %d: chapter must be text" % i}, 400)
            clean.append({"start": start, "text": c["text"], "chapter": chapter})
        if data.get("prompt"):
            return _tidy_prompt(h, clean, L, data["prompt"])
        word_doc = _word_document(data, L, clean)
        if data.get("tidy"):
            mode = data.get("tidy_mode") if isinstance(data.get("tidy_mode"), str) else "text"
            words = None
            if word_doc is not None:
                import wordtimes
                words = wordtimes.timed_stream(word_doc)
            clean, notes = tidier.tidy(clean, L.code, word_times=words, pause_mode=mode)
            if word_doc is not None:
                import wordtimes
                word_doc = wordtimes.sync(word_doc, clean, L.code)
        clean = _word_starts(word_doc, clean)
        text = CA.transcript_text(clean)
    else:
        if not isinstance(data.get("transcript"), str):
            return h.send_json({"ok": False, "error": "transcript must be text"}, 400)
        got = parse_transcript_text(as_transcript(data["transcript"]), L)
        if data.get("prompt"):
            return _tidy_prompt(h, got, L, data["prompt"])
        word_doc = _word_document(data, L, got)
        if data.get("tidy"):
            mode = data.get("tidy_mode") if isinstance(data.get("tidy_mode"), str) else "text"
            words = None
            if word_doc is not None:
                import wordtimes
                words = wordtimes.timed_stream(word_doc)
            got, notes = tidier.tidy(got, L.code, word_times=words, pause_mode=mode)
            if word_doc is not None:
                import wordtimes
                word_doc = wordtimes.sync(word_doc, got, L.code)
        got = _word_starts(word_doc, got)
        text = CA.transcript_text(got)
    captions = parse_transcript_text(text, L)
    if not captions:
        return h.send_json({"ok": False, "error": "no captions found -- paste the "
                            "transcript as YouTube shows it, timestamps included"}, 400)
    why = tidier.why_not(L.code)
    word_projection = None
    if word_doc is not None:
        import wordtimes
        # Canonical serialisation is the state bound to adoption.  The editor
        # commits it only when its Use button accepts this same panel.
        word_doc["panel_sha256"] = wordtimes.panel_hash(text)
        lost_pins = wordtimes.orphaned_pins(word_doc)
        if lost_pins:
            return h.send_json({"ok": False,
                                "error": "That change would make a person-set start fall inside a caption. "
                                         "Keep that boundary, move the start, or explicitly remove it first."}, 409)
        if data.get("word_commit"):
            try:
                wordtimes.save(data.get("word_job"), word_doc)
            except ValueError:
                pass
        word_projection = wordtimes.projection(word_doc)
    return h.send_json({"ok": True, "captions": captions, "text": text,
                        "lang": L.code, "notes": notes,
                        "can_tidy": not why, "why": why,
                        "wordtimes": word_projection})


def api_prepare(h):
    """The pasted transcript, parsed; the prompt, ready to copy."""
    try:
        data = _json_in(h, 4 << 20)
    except Exception as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    # A VIDEO IS EITHER AN ADDRESS OR A FILE.  Where no YouTube URL was
    # given, `path` names a film on this machine and the id is made here --
    # and handed back, so that the `id:` line of the prompt and the directory
    # `api_add` finally writes are the same id.
    try:
        one_source(data)
    except ValueError as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    vid = video_id(data.get("url"))
    local = False
    if not vid and (data.get("path") or "").strip():
        try:
            _p, _e, vid = local_target(data, [n for _f, n, _q in video_dirs()])
            local = True
        except ValueError as e:
            return h.send_json({"ok": False, "error": str(e)}, 400)
    if not vid:
        return h.send_json({"ok": False, "error": "that is not a YouTube URL (or id) "
                            "-- or name a film on this machine instead"}, 400)
    try:
        L = posted_lang(data.get("lang"))
    except KeyError as e:
        return h.send_json({"ok": False, "error": str(e.args[0])}, 400)
    # the gloss is refused rather than defaulted: the page always sends one,
    # so a code that is not a language means somebody is posting by hand,
    # and answering with a prompt that quietly asks for English would be
    # discovered only in the finished annotation
    try:
        G = posted_gloss(data.get("gloss"))
    except KeyError as e:
        return h.send_json({"ok": False, "error": str(e.args[0] if e.args else e)}, 400)
    captions = parse_transcript_text(as_transcript(data.get("transcript")), L)
    if not captions:
        return h.send_json({"ok": False, "error": "no captions found -- paste the "
                            "transcript as YouTube shows it, timestamps included"}, 400)
    want = [c for c in captions if not c["plain"]]
    if not want:
        return h.send_json({"ok": False, "error": "every caption is plain (not one "
                            "character of %s script) -- nothing to annotate; is the "
                            "language right?" % L.name}, 400)
    # THE PERSON'S OWN PROMPT, by its id (lib/prompts.py): refused in words when
    # it is gone, or is for another place or another language
    try:
        chosen = prompts.resolve("video-new", data.get("prompt"), L)
    except prompts.PromptsError as e:
        return h.send_json({"ok": False, "error": str(e)}, e.status)
    meta = {} if local else oembed(vid)
    # BY THE NAME ALONE, NEVER BY LOOKING INSIDE THE FILE: the page asks for this
    # prompt again and again as the person types, and an ffprobe on every ask made
    # the answer arrive after the next keystroke (tests/add_stt.mjs caught it).
    # The kind that counts is decided once, when the file is attached.
    if local and filmkind.kind_of(os.path.splitext(_p)[1].lower()) == "audio":
        meta = {"kind": "audio"}        # the prompt says "a recording", not "a film"
    exists = find_video(vid)[0] is not None
    try:
        made = assembled_full(vid, meta, captions, data.get("glossary") or None, L, G,
                              chosen and chosen.instructions, chosen and chosen.name,
                              promptkit.given(data))
    except promptkit.OptionError as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    except promptkit.PromptError as e:
        return h.send_json({"ok": False, "error": prompts.unmade(chosen, e) if chosen else
                            "the prompt could not be made: %s" % e}, 400)
    prompt = made.text
    import skills
    return h.send_json({"ok": True, "id": vid, "lang": L.code, "folder": L.folder,
                        # the short request for a chat that has the skill (lib/skills.py), made from the same prompt
                        "skill": skills.safe(lambda: skills.for_new_video(made, L, G, chosen,
                                                                          data.get("glossary") or None),
                                             "parseh-gloss"),
                        "options": promptkit.describe("video-new", L, made.options),
                        "custom": chosen and {"id": chosen.id, "name": chosen.name,
                                              "kind": chosen.kind},
                        "gloss": G.code, "gloss_name": G.name,
                        "url": "" if local else "https://www.youtube.com/watch?v=" + vid,
                        "local": local,
                        "title": meta.get("title", ""), "channel": meta.get("channel", ""),
                        "captions": len(captions), "want": len(want),
                        "plain": len(captions) - len(want),
                        "duration": fmt_time(captions[-1]["start"]),
                        "exists": exists, "prompt": prompt})


def _run(cmd):
    r = subprocess.run([sys.executable] + cmd, cwd=HERE, capture_output=True,
                       text=True, timeout=120)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def trash_video(path):
    """Move a video directory under videos/.trash/<name>-<stamp>/ and return
    where it went.  The name is made unique first: shutil.move into a
    directory that already exists puts the tree INSIDE it, so a second
    replace of the same id within one second (a double click) would bury
    the older copy one level down and the path reported for it would be
    wrong.  (import_old_video.py keeps the same rule.)"""
    trash = os.path.join(VIDEOS, ".trash")
    os.makedirs(trash, exist_ok=True)
    base = os.path.join(trash, "%s-%s" % (os.path.basename(os.path.normpath(path)),
                                          time.strftime("%Y%m%d-%H%M%S")))
    dest, n = base, 1
    while os.path.exists(dest):
        n += 1
        dest = "%s-%d" % (base, n)
    shutil.move(path, dest)
    return dest


# every field the player's book-info-style sheet may change, in the order
# the form shows them.  Unlike a book's title/author, none of these reach a
# build step -- a video is never run through LaTeX -- so there is no
# main.tex-style second copy to keep in step and nothing here refuses a
# LaTeX special; only texwrite.NOT_TEXT, the same control-character refusal
# every field in this toolbox answers to
EDITABLE_META = ("title", "title_native", "channel", "level", "blurb", "reorders", "translit")

# the ones of those that are a switch, not text: "reorders", a text read out
# of its written order (kanbun), whose words' readings are not held to the
# chunk's reading (lib/wordline.py's check).  true, or not written at all --
# check_annotations and the player read a missing key as false
SWITCHES_META = ("reorders",)

# ...and the one that is a choice among words: "translit", the scheme the video's
# transliteration is written in -- "ipa", or "" for the language's usual one,
# which is no key at all (the prompts and the checks read a missing key as the
# usual scheme).  An older Parseh ignores the key, so VIDEO_FORMAT stays
CHOICES_META = {"translit": ("", "ipa")}


def edit_meta(vdir, fields):
    """Rewrite video.json's own fields -- title, title_native, channel,
    level, blurb -- from the player, the way a video was mis-named by
    api_add's YouTube lookup (a mistitled oEmbed answer, a channel name
    YouTube would not give) is fixed without hand-editing the file.  And
    "reorders", true or false, which api_add never writes: a kanbun video
    is marked here rather than by hand.

    `fields` may name any subset of EDITABLE_META; a name it does not carry
    raises ValueError.  Returns the video's full, updated meta dict.  Unlike
    a book there is nothing to rebuild: the player reads the file the edit
    just wrote."""
    if not isinstance(fields, dict) or not fields:
        raise ValueError("nothing to change")
    unknown = sorted(set(fields) - set(EDITABLE_META))
    if unknown:
        raise ValueError("not an editable field: %s (editable: %s)"
                         % (", ".join(unknown), ", ".join(EDITABLE_META)))
    checked = {}
    for field, value in fields.items():
        if field in SWITCHES_META:
            if not isinstance(value, bool):
                raise texwrite.Refused("%s must be true or false, not %s"
                                       % (field, type(value).__name__))
            checked[field] = value
            continue
        if field in CHOICES_META:
            said = value.strip().lower() if isinstance(value, str) else None
            said = "" if said == "classic" else said
            if said not in CHOICES_META[field]:
                raise texwrite.Refused("%s is %s, not %r" % (
                    field, " or ".join(repr(c) for c in CHOICES_META[field]), value))
            checked[field] = said
            continue
        if not isinstance(value, str):
            raise texwrite.Refused("%s must be a string, not %s"
                                   % (field, type(value).__name__))
        m = texwrite.NOT_TEXT.search(value)
        if m:
            k, cp = m.start(), ord(m.group())
            why = ("an unpaired surrogate, which UTF-8 cannot encode"
                   if 0xd800 <= cp <= 0xdfff else "a control character")
            raise texwrite.Refused(
                "%s carries U+%04X at character %d, which is not text -- %s"
                % (field, cp, k, why))
        checked[field] = value.strip()
    if "title" in checked and not checked["title"]:
        raise texwrite.Refused("title may not be blank")
    if "level" in checked and checked["level"] and checked["level"] not in LEVELS:
        raise texwrite.Refused("level must be one of %s, not %r"
                               % (", ".join(LEVELS), checked["level"]))

    path = os.path.join(vdir, "video.json")
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)
    meta.update(checked)
    for field in SWITCHES_META:
        if checked.get(field) is False:         # a switch turned off is not written
            meta.pop(field, None)
    for field in CHOICES_META:
        if checked.get(field) == "":            # the usual way is no key at all
            meta.pop(field, None)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return meta


def api_add(h):
    """The LLM's answer, checked and written as videos/<folder>/<id>/."""
    try:
        data = _json_in(h, 8 << 20)
    except Exception as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    try:
        one_source(data)
    except ValueError as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    vid = video_id(data.get("url"))
    film = ""
    if not vid and (data.get("path") or "").strip():
        # the film this video IS, and the id `prepare` already told the page
        try:
            film, _e, vid = local_target(data, [n for _f, n, _q in video_dirs()])
        except ValueError as e:
            return h.send_json({"ok": False, "error": str(e)}, 400)
    if not vid:
        return h.send_json({"ok": False, "error": "that is not a YouTube URL (or id) "
                            "-- or name a film on this machine instead"}, 400)
    try:
        L = posted_lang(data.get("lang"))
    except KeyError as e:
        return h.send_json({"ok": False, "error": str(e.args[0])}, 400)
    try:
        G = posted_gloss(data.get("gloss"))
    except KeyError as e:
        return h.send_json({"ok": False, "error": str(e.args[0] if e.args else e)}, 400)
    try:
        translit = promptkit.resolve("video-new", L, promptkit.given(data)).get("translit")
    except promptkit.OptionError as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    transcript = as_transcript(data.get("transcript")) \
        .replace("\r\n", "\n").replace("\r", "\n")
    captions = parse_transcript_text(transcript, L)
    if not captions:
        return h.send_json({"ok": False, "error": "no captions found in the transcript"}, 400)
    # the same refusal api_prepare makes: with the wrong language every
    # caption is plain, the answer's captions are all "annotated and
    # ignored" (a note, not a problem), and nothing would be left to write
    if not [c for c in captions if not c["plain"]]:
        return h.send_json({"ok": False, "error": "every caption is plain (not one "
                            "character of %s script) -- nothing to annotate; is the "
                            "language right?" % L.name}, 400)
    try:
        video, caps, blocks = _merge_answer(_json_blocks(data.get("answer")))
    except ValueError as e:
        return h.send_json({"ok": False, "error": str(e)}, 400)
    if not caps:
        return h.send_json({"ok": False, "error": "the answer holds no captions"}, 400)
    parts, problems, missing = _align_answer(caps, captions, blocks)
    hard = [p for p in problems if not p.startswith("note:")]
    if hard:
        return h.send_json({"ok": False, "error": "the answer does not cover the "
                            "transcript", "problems": problems}, 400)
    # the word lines, before the checks: one that is not text is refused by
    # the answer's own caption number, and one the model left out is proposed
    # here and so checked below with everything else
    bad, proposed = _answer_words(parts, L)
    if bad:
        return h.send_json({"ok": False, "error": "%d word line(s) in the answer are "
                            "not text -- nothing written" % len(bad),
                            "problems": problems + bad}, 400)
    # the same checks check_annotations.py will run, before anything is
    # written, and as strictly: a chunk the answer half glossed is an error
    # here (the default `half`), since nothing an LLM hands back is the
    # middle of anybody's work.  A chunk it left with no gloss at all is
    # legal, as it is everywhere, and is counted below.  What the checker
    # says is turned into the prompt's own numbering before the page shows
    # it, because those lines go back to the LLM as they are
    errors, warnings = [], []
    segs = _segments(parts, captions)
    CA.check_segments(segs, captions, errors.append, warnings.append, L)
    errors = [_as_prompt_numbers(e, captions) for e in errors]
    warnings = [_as_prompt_numbers(w, captions) for w in warnings]
    if errors:
        return h.send_json({"ok": False, "error": "%d error(s) in the annotation -- "
                            "nothing written" % len(errors),
                            "problems": problems + errors, "warnings": warnings}, 400)
    blank, _glossable = CA.gloss_count(segs, L)
    if blank:
        problems.append("note: %d chunk%s left without a gloss -- gloss %s "
                        "in the player" % (blank, "" if blank == 1 else "s",
                                           "it" if blank == 1 else "them"))

    ov = data.get("overrides") if isinstance(data.get("overrides"), dict) else {}
    ov = {k: str(v).strip() for k, v in ov.items() if isinstance(v, (str, int, float))}
    vmeta = video if isinstance(video, dict) else {}
    # an answer written to the older prompt says title_fa; it is the same field
    if isinstance(vmeta.get("title_fa"), str) and not vmeta.get("title_native"):
        vmeta["title_native"] = vmeta["title_fa"]
    fetched = {} if film else oembed(vid)

    def pick(key, *fallbacks):
        for src in (ov, vmeta, fetched):
            v = src.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for fb in fallbacks:
            if fb:
                return fb
        return ""
    level = pick("level", "beginner").lower()
    if level not in LEVELS:
        level = "beginner"
    # what a local film is called when nobody says: its own file name, and
    # the channel every film on this machine belongs to.  /api/local has
    # always said these; the two roads used to disagree about them, so the
    # same film added two ways came out with two names.
    stem = os.path.splitext(os.path.basename(film))[0] if film else ""
    meta = {
        "id": vid,
        # a film on this machine has no address, and is given none rather
        # than a link to a YouTube video that does not exist
        "url": "" if film else "https://www.youtube.com/watch?v=" + vid,
        "title": pick("title", stem, vid),
        "title_native": pick("title_native"),
        "channel": pick("channel", "on this machine" if film else "Unknown channel"),
        "language": L.code,
        # beside it and never confusable with it: "language" is what the
        # video TEACHES, "gloss" what its meanings are WRITTEN in.  Written
        # out even when it is English, the way "language" is written out
        # even when it is Persian -- absent is what the videos made before
        # the field existed say, not what a page that asked the question
        # says
        "gloss": G.code,
        "level": level,
        "duration": fmt_time(captions[-1]["start"]),
        "added": datetime.date.today().isoformat(),
        "blurb": pick("blurb"),
    }
    # THE SCHEME OF ITS TRANSLITERATION is a fact of the video, written when it is chosen and only when
    # it is not the usual one (a key an older Parseh ignores, like "reorders"): the player's prompts ask
    # for it from then on, so that one video does not mix two schemes
    if translit == "ipa":
        meta["translit"] = "ipa"

    vdir = os.path.join(VIDEOS, L.folder, vid)
    # the id may already be in the player -- under this folder, another
    # language's, or flat under videos/ from before languages; every copy
    # goes to the trash when the new one is in
    _old, old_path = find_video(vid)
    olds = list(dict.fromkeys(p for p in (old_path, vdir) if p and os.path.isdir(p)))
    if olds:
        rel_old = "videos/" + os.path.relpath(olds[0], VIDEOS)
        if not data.get("replace"):
            return h.send_json({"ok": False, "exists": True, "dir": rel_old,
                                "error": "%s/ already exists -- tick "
                                "\"replace\" to overwrite it (the old one is "
                                "kept under videos/.trash/)" % rel_old}, 409)
    # The tree is written to a staging directory and moved into place only
    # once merge_parts.py and check_annotations.py have passed on it: a
    # failure in either (a transcript the tools read differently, an
    # answer that slipped through the checks above) then leaves videos/
    # exactly as it was -- the old video stays on the index, no half-made
    # folder appears beside it.  The staging directory is a dot-directory
    # under videos/, which video_dirs never lists; its leaf is the id,
    # which check_annotations compares with video.json.
    #
    # THE BATCHES NEVER LEAVE THE STAGING DIRECTORY.  parts/ is cut here so
    # that merge_parts can fold it into annotations.json and the checker can
    # hold that against the transcript -- and then it is dropped, before the
    # video moves onto the shelf.  A video used to carry its batches for
    # ever, and they said what the answer had said and nothing of what was
    # done in the player afterwards; anybody who merged again -- the guide
    # told them how -- got the answer back and lost every gloss, colour and
    # correction made since, with no word said.  One source of truth for a
    # video's annotation, and it is annotations.json.
    os.makedirs(VIDEOS, exist_ok=True)
    waveform = None              # what the door says of the sound's shape, if it was asked
    film_got = None              # what became of the film or the sound, if there is one
    stage = tempfile.mkdtemp(prefix=".staging-", dir=VIDEOS)
    sdir = os.path.join(stage, vid)
    os.makedirs(os.path.join(sdir, "parts"))
    with open(os.path.join(sdir, "transcript.txt"), "w", encoding="utf-8") as f:
        f.write(transcript.strip("\n") + "\n")
    with open(os.path.join(sdir, "video.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    for n in range(0, len(parts), PART_SIZE):
        with open(os.path.join(sdir, "parts", "%02d.json" % (n // PART_SIZE + 1)),
                  "w", encoding="utf-8") as f:
            json.dump(parts[n:n + PART_SIZE], f, ensure_ascii=False, indent=1)
            f.write("\n")
    # the pipeline's own two steps, as PROMPT.md prescribes them
    rel = os.path.join("videos", L.folder, vid)
    srel = os.path.relpath(sdir, HERE)
    try:
        rc1, out1 = _run([os.path.join("lib", "merge_parts.py"), srel])
        rc2, out2 = (1, "(merge failed, not checked)")
        if rc1 == 0:
            rc2, out2 = _run([os.path.join("lib", "check_annotations.py"), srel])
        if rc1 == 0 and rc2 == 0:
            # the batches have done their one job, and both tools have
            # passed on what they built: nothing reads them again
            shutil.rmtree(os.path.join(sdir, "parts"), ignore_errors=True)
            # the film goes in while the tree is still staged, so that the
            # move into videos/ carries the whole video at once
            if film:
                try:
                    film_got = attach_film(sdir, film)
                except (OSError, ValueError) as e:
                    return h.send_json({"ok": False, "error": "the annotation is "
                                        "good, but the film could not be put "
                                        "beside it (%s) -- nothing was written"
                                        % e}, 400)
            # THE SHAPE OF THE SOUND its transcription recorded goes in beside
            # the rest, still staged, so it moves onto the shelf with the video
            # and is never on the shelf without one.  Only a YouTube video has
            # one to take (a film's is drawn from the film itself), and a
            # token that names nothing is no reason to refuse the video.
            if "wave" in data and not film:
                waveform = wavefile.adopt(data.get("wave"), sdir) or {"kept": False}
            for p in olds:
                trash_video(p)
            os.makedirs(os.path.dirname(vdir), exist_ok=True)
            shutil.move(sdir, vdir)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    # the tools were shown the staging path; the reader is told the real one
    out1, out2 = out1.replace(srel, rel), out2.replace(srel, rel)
    answer = {"ok": rc1 == 0 and rc2 == 0, "id": vid,
              "lang": L.code, "gloss": G.code, "dir": rel,
              "href": "%s/v/%s/" % (BASE, vid),
              "captions": len(captions), "glossed": len(parts),
              "proposed": proposed, "blank": blank,
              # how many batches the answer was cut into is not
              # said any more: the batches are gone by now, and a
              # number counting a folder nobody will find only
              # sends people looking for it
              "merge": out1.strip(), "check": out2.strip(),
              "problems": problems, "warnings": warnings, "video": meta}
    # said only where it was asked for, as the two other doors that make a video say it
    if waveform is not None:
        answer["waveform"] = waveform if answer["ok"] else {"kept": False}
    # and what became of the film or the sound, for the page to say
    if film_got is not None and answer["ok"]:
        answer["film"] = film_got
    return h.send_json(answer)


ADD_PAGE_HEAD = r'''
<div class="addvid">

<p class="qlab" id="q1lab">Where is the video?</p>
<div class="paths two" id="q1" role="radiogroup" aria-labelledby="q1lab">
  <button type="button" class="path" role="radio" aria-checked="false" tabindex="0" data-src="yt">
    <b>From YouTube</b>
    <span>An address. The title and the channel are fetched from YouTube.</span>
    <em>needs: the URL, and the transcript panel</em>
  </button>
  <button type="button" class="path" role="radio" aria-checked="false" tabindex="-1" data-src="film">
    <b>A video or a sound on this machine</b>
    <span>The file is linked beside the transcript and travels with it &mdash; the download
      button then hands over the video (or the sound) and the glosses as one zip.</span>
    <em>needs: the file&rsquo;s path, or the file sent, and a transcript or a .srt/.vtt</em>
  </button>
</div>

<p class="qlab" id="q2lab">Who writes the glosses?</p>
<div class="paths two" id="q2" role="radiogroup" aria-labelledby="q2lab">
  <button type="button" class="path" role="radio" aria-checked="false" tabindex="0" data-by="llm">
    <b>An LLM &mdash; I paste the answer back</b>
    <span>This page builds a prompt that needs nothing else. You paste the reply and it is
      checked before anything is written.</span>
    <em>two steps more: prepare, then the answer</em>
  </button>
  <button type="button" class="path" role="radio" aria-checked="false" tabindex="-1" data-by="empty">
    <b>Nobody &mdash; I gloss it in the player</b>
    <span>Every caption is cut into chunks with the meanings left blank, and the player opens
      on it.</span>
    <em>one step more: start it empty</em>
  </button>
</div>
<span class="fieldnote">A video is glossed in the player, never extended &mdash; there is no
  &ldquo;add to a video already here&rdquo;.</span>

<p class="pathnote" id="nopath">Answer both to go on.
  <span class="also">Already have an exported <code>&lt;id&gt;-video.zip</code>? Bring it back
    from <a href="__BASE__/">the videos page</a>.</span></p>

<div id="vbody" hidden>
<section class="step" id="step-1">
  <div class="shead"><span class="num">1</span><h2>The video</h2></div>
  <div class="sbody">

  <!-- BOTH source fields stay in the document whichever is chosen, and only
       one is ever shown.  They are read whichever is chosen -- restored from
       the saved form, written by save(), and who() focuses the empty one by
       its id; removing one would take the script down, and
       leaving a hidden one's VALUE in the body is what used to send both and
       earn the server's "this names both" refusal, naming a field no longer
       on screen.  The body is built from the chosen source alone. -->
  <div id="src-yt" hidden>
    <label>YouTube URL <input id="url" placeholder="https://www.youtube.com/watch?v=..." autocomplete="off"></label>
    <span class="fieldnote">watch?v=&hellip;, youtu.be/&hellip;, /shorts/&hellip;, /embed/&hellip;,
      or the bare 11-character id.</span>
  </div>
  <div id="src-film" hidden>
    <label>The video or sound <input id="path" placeholder="/home/you/films/lesson-1.mp4" autocomplete="off" spellcheck="false"></label>
    <span class="fieldnote">A video: <code>.mp4</code>, <code>.webm</code>, <code>.mkv</code>,
      <code>.mov</code> or <code>.m4v</code>. A sound: <code>.mp3</code>, <code>.m4a</code>,
      <code>.wav</code>, <code>.ogg</code>, <code>.flac</code> and the others listed below. It is
      <b>hardlinked</b> beside the transcript, so it costs no disk and no time even for a
      two-hour film.</span>
    <!-- what the path names, said once it is left: a video or a sound, how big, and what
         will be done about a sound a browser cannot play (youtube/lib/addfilm.js) -->
    <div id="filmlook" class="filmsay" aria-live="polite" hidden></div>
    <!-- and the option beside the path: send the file instead (the same script draws it) -->
    <div id="filmsend" class="filmsend" data-base="__BASE__" data-accept="__ACCEPT__"></div>
  </div>

  <div class="row">
    <label class="inline">Language <select id="lang">__LANGS__</select></label>
  </div>
  <span class="fieldnote">The language the video teaches &mdash; it decides which captions
    count as plain and the folder the video is filed under.</span>
  <div class="row">
    <label class="inline">Glossed in <select id="gloss">__GLOSSES__</select></label>
  </div>
  <span class="fieldnote">The language the meanings are written in &mdash; an Italian learning
    English wants them in Italian. Remembered for the next video.</span>

  <details><summary id="ovsum">Details the answer may not know (optional)</summary>
    <div class="grid">
      <label>Title <input id="ov_title" placeholder="fetched from YouTube when possible"></label>
      <label>Channel <input id="ov_channel" placeholder="fetched from YouTube when possible"></label>
      <label>Level <select id="ov_level"><option value="" id="ov_level_blank">from the answer</option><option>beginner</option><option>lower-intermediate</option><option>intermediate</option><option>upper-intermediate</option><option>advanced</option></select></label>
      <label><span id="ov_native_lab">Persian</span> title <input id="ov_title_native" placeholder="the title in the video's own language"></label>
      <label class="wide">Blurb <input id="ov_blurb" placeholder="one sentence, for the card"></label>
    </div>
  </details>

  <button type="button" class="hbtn" aria-expanded="false" aria-controls="how-film" id="filmhow" hidden>what happens to the film or the sound</button>
  <div class="hbox" id="how-film" hidden>
    <p><b>The file is hardlinked</b> beside the transcript as <code>media.&lt;ext&gt;</code>, so
      it costs no disk and no time; where the filesystem forbids a link (another disk) it is
      copied instead, and the answer says which happened.</p>
    <p><b>Either way it is part of the video</b> from then on, so a video that came out
      of one machine plays on the next.</p>
    <p><b>A sound is a video with no picture.</b> Any of <code>.mp3</code>, <code>.m4a</code>,
      <code>.aac</code>, <code>.ogg</code>, <code>.oga</code>, <code>.opus</code>,
      <code>.wav</code>, <code>.flac</code>, <code>.weba</code>, <code>.wma</code>,
      <code>.aiff</code>, <code>.aif</code>, <code>.amr</code>, <code>.mka</code> and
      <code>.caf</code> is taken. The player shows a bar with its waveform where a video shows a
      frame, a card takes the recording and no picture, and what the speech to text and the
      timings do with a video they do with a sound.</p>
    <p><b>A sound the browser cannot play</b> (<code>.wma</code>, <code>.aiff</code>,
      <code>.amr</code>, <code>.mka</code>, <code>.caf</code>) gets a playable copy made by
      ffmpeg when the video is added, and the original is kept beside it as
      <code>media-orig.&lt;ext&gt;</code>. Without ffmpeg the sound is added as it is, and this
      page says so before you go on.</p>
    <p><b>Sent, or named.</b> The path stays the way to name a file on this machine. The other
      way, <i>Choose a video or a sound</i>, sends the file from this device into this
      computer&rsquo;s disk and puts its path in the box; it works from another device and on
      Windows, and the only limit is the disk.</p>
  </div>
  </div>
</section>

<section class="step" id="step-2">
  <div class="shead"><span class="num">2</span><h2>The transcript</h2></div>
  <div class="sbody">
  <label>Transcript
    <textarea id="transcript" rows="9" dir="auto" placeholder="0:08&#10;Hello my friend &#x62F;&#x631;&#x648;&#x62F;&#10;0:32&#10;&#x646;&#x627;&#x646; &#x62A;&#x627;&#x632;&#x647; ...&#10;..."></textarea></label>
  <span class="fieldnote">On YouTube: <i>&hellip;more &rarr; Show transcript</i>, select the whole
    panel, copy. Paste it verbatim, timestamps included.<span id="subline" hidden> <b>Or</b>
    paste a <code>.srt</code> or <code>.vtt</code> file whole.</span></span>

  <!-- Speech to text is OPTIONAL and is drawn by /youtube/lib/addstt.js from what
       the computer says it has: this is only the place it goes.  Empty and
       hidden until then, so a page with no speech to text has no control for it
       at all -- and nothing dead in it. -->
  <div id="stt" class="stt" hidden></div>

  <div class="row">
    <button type="button" class="wbtn" id="subedit">Edit the transcript&hellip;</button>
    <span id="sestat" class="stat"></span>
  </div>
  <span class="fieldnote">Fix what YouTube heard and where it cut: the captions in a list,
    split and joined, and their times moved a second, a half or a <b>tenth</b> at a time
    with the video beside them to play each one against. Only here, while the video is being
    added: once it is in the player its transcript is what its glosses were checked
    against.</span>

  <button type="button" class="hbtn" aria-expanded="false" aria-controls="clean">the paste repeats a stray line on every caption?</button>
  <div class="hbox" id="clean" hidden>
    <div class="row cleanrow">
      <label class="inline">Drop pasted lines where line-number mod <input type="number" id="clnMod" min="2" value="3" class="tiny">
        equals <input type="number" id="clnRem" min="0" value="1" class="tiny"></label>
      <button type="button" class="wbtn small quiet" id="cleanlines">Remove those lines</button>
    </div>
    <p>Drops every pasted line at that position, counting the first as 0. It rewrites the box
      above &mdash; check the result.</p>
    <p>Some panels repeat an extra line on every caption in a form the parser does not already
      recognise: YouTube has been seen giving both a timestamp and a spoken-duration line for
      every caption, in a language whose digits it was not told to read as a duration.</p>
  </div>
  </div>
</section>

<!-- ---------------- the LLM's two further steps ---------------- -->
<section class="step" id="step-llm-3">
  <div class="shead"><span class="num">3</span><h2>The prompt</h2></div>
  <div class="sbody">
  <div class="row">
    <label class="inline">Word list <select id="glossary"><option value="">none</option>__GLOSSARIES__</select></label>
  </div>
  <span class="fieldnote">A per-family list that keeps the transliteration consistent with the
    videos already here. Only the prompt uses it.</span>
  <div id="pmenu"></div>
  <div id="popts"></div>
  <div class="row">
    <button type="button" class="wbtn" id="prepare">Prepare the prompt</button>
    <span id="pstat" class="stat"></span>
  </div>
  <div id="pinfo" class="note" aria-live="polite" hidden></div>
  <!-- copy the prompt and its size, which are said once it is prepared: drawn by
       /lib/llmrow.js, the one place these controls are built -->
  <div id="prow" hidden></div>
  <details id="pshow" hidden><summary>The prompt, as it will be copied</summary>
    <textarea id="prompt" rows="14" readonly spellcheck="false"></textarea>
  </details>
  </div>
</section>

<section class="step" id="step-llm-4">
  <div class="shead"><span class="num">4</span><h2>The answer</h2></div>
  <div class="sbody">
  <span class="fieldnote">Paste the LLM&rsquo;s whole reply &mdash; or several replies, one
    after another. Its <code>```</code> blocks are read in order, and a caption a later block
    gives again replaces the earlier one; a block that is not JSON is taken for the
    LLM&rsquo;s prose and passed over, unless it says <code>```json</code>.</span>
  <textarea id="answer" rows="10" spellcheck="false" placeholder='```json&#10;{"video": {...}, "captions": [ ... ]}&#10;```'></textarea>
  <div class="row">
    <button type="button" class="wbtn go" id="add">Check &amp; add the video</button>
    <label class="inline" id="replacerow" hidden><input type="checkbox" id="replace"> replace the existing <code id="existid"></code> (the old one is kept under <code>videos/.trash/</code>)</label>
    <span id="astat" class="stat"></span>
  </div>
  <div id="result" aria-live="polite" hidden></div>
  <button type="button" class="hbtn" aria-expanded="false" aria-controls="how-llm">how this works</button>
  <div class="hbox" id="how-llm" hidden>
    <p><b>The answer is checked before anything is written:</b> it is staged in a
      dot-directory, <code>merge_parts.py</code> and <code>check_annotations.py</code> run on
      it, and only then does it move into <code>videos/</code> &mdash; a failure leaves
      <code>videos/</code> untouched.</p>
    <p><b>The answer is folded in once.</b> It is cut into batches to be merged and
      checked, and the batches are dropped in the staging directory: the video goes on
      the shelf with <code>annotations.json</code> and nothing beside it to rebuild from.
      Everything you do in the player afterwards is written there. Adding the same video
      again with <i>replace</i> ticked writes a new one from the new answer: the old one,
      with everything done to it in the player, is moved to <code>videos/.trash/</code>,
      not merged.</p>
    <p><b>A chunk the answer leaves with no gloss</b> goes in blank, counted in a note, for
      you to gloss in the player; one it glosses only in part is refused, like any other
      error.</p>
    <p><b>An answer from an earlier session still works:</b> this step re-derives everything,
      so the prompt need not have been prepared just now.</p>
  </div>
  </div>
</section>

<!-- ---------------- or the one step that needs no answer ---------------- -->
<section class="step" id="step-empty-3">
  <div class="shead"><span class="num">3</span><h2>Start it empty</h2></div>
  <div class="sbody">
  <div class="row">
    <label class="inline">Cut the captions into <select id="how">__HOWS__</select></label>
  </div>
  <span class="fieldnote">A chunk is what a reader hovers. <b>Sense groups</b> needs this
    language&rsquo;s installed dictionary and falls back to one chunk per sentence without it
    &mdash; either way you can re-cut any chunk in the player.</span>
  <div class="row">
    <button type="button" class="wbtn" id="empty">Start it empty</button>
    <span id="estat" class="stat"></span>
  </div>
  <span class="fieldnote" id="emptynote" hidden>The film or the sound is linked beside the
    transcript as part of the video.</span>
  <div id="eresult" aria-live="polite" hidden></div>
  <button type="button" class="hbtn" aria-expanded="false" aria-controls="how-empty">how this works</button>
  <div class="hbox" id="how-empty" hidden>
    <p><b>No prompt and no LLM:</b> the transcript is taken as it stands, every
      <code>tr</code>, <code>voc</code> and <code>en</code> left blank for you to fill in the
      player.</p>
    <p><b>A chunk nobody has glossed yet is never a fault:</b> the checker counts the
      blank ones and asks nothing of them. The player saves a chunk a box at a time &mdash;
      the meaning typed, the transliteration still to come &mdash; and the checker lists
      such a half-glossed chunk until it is finished. Emptying every box of a chunk
      (&ldquo;delete gloss&rdquo;) makes it blank again.</p>
    <p><b>Started empty, a video cannot be re-started</b> &mdash; move or delete the old one
      first. Only the LLM way can replace.</p>
  </div>
  </div>
</section>
</div>
</div>
<style>
.addvid .step label{display:block;margin:10px 0 4px;font-size:13.5px;color:var(--dim)}
.addvid .step label.inline{display:flex;align-items:center;gap:8px;margin:0;flex-wrap:wrap}
.addvid input:not([type=checkbox]),.addvid select,.addvid textarea{width:100%;font:inherit;
  font-size:14px;padding:7px 10px;border:1px solid var(--rule);border-radius:7px;
  background:var(--bg);color:var(--ink)}
.addvid label.inline select{width:auto}
.addvid input.tiny{width:52px;display:inline-block;text-align:center}
.addvid .cleanrow{margin-top:2px}
.addvid textarea{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;line-height:1.5;resize:vertical}
/* the transcript and the prompt are set in the picked language's face: the
   script gives both textareas data-lang, and /lib/langs.css turns that into
   --tl-font (so no font is named here) */
.addvid #transcript,.addvid #prompt,.addvid #ov_title_native{font-family:var(--tl-font,inherit),ui-monospace,monospace;font-size:13.5px}
.addvid .grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 14px}
.addvid .grid .wide{grid-column:1/-1}
.addvid .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px}
.addvid .hint{font-size:12.5px;color:var(--faint)}
.addvid .stat{color:var(--accent);font-size:12.5px}
.addvid .stat.warn{color:var(--warn)}
.addvid details{margin-top:10px}
.addvid summary{cursor:pointer;color:var(--dim);font-size:13.5px}
.addvid pre{white-space:pre-wrap;font-size:12.5px;line-height:1.5;margin:6px 0 0}
.addvid .note pre{max-height:320px;overflow:auto}
.addvid code{font-family:ui-monospace,Menlo,monospace;font-size:12px}
.addvid .step{margin-bottom:14px}
/* a refusal may be several lines and must read as it was written */
.addvid .note.bad{white-space:pre-wrap}

/* ---------------- the two questions ----------------
   Not a <fieldset>/<legend>: a legend inside a display:grid fieldset is the
   one layout engines still disagree about, and one taken as a grid item
   steals the first card's cell.  A <p> named through aria-labelledby says
   the same to a screen reader and lays out the same everywhere.
   Neither question is locked behind the other: the two axes are orthogonal,
   all four combinations are real, and a greyed card with pointer-events
   taken away could not even say why it was grey. */
.addvid .qlab{display:block;margin:0 0 10px;font:400 13px/1.3 inherit;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint)}
.addvid .paths{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 6px}
.addvid .paths.two{grid-template-columns:repeat(2,minmax(0,1fr))}
@media (max-width:760px){.addvid .paths,.addvid .paths.two{grid-template-columns:1fr}}
.addvid .paths+.qlab{margin-top:22px}
.addvid .path{display:block;width:100%;text-align:start;font:inherit;cursor:pointer;
  background:var(--card);color:var(--ink);border:1px solid var(--rule);
  border-radius:12px;padding:14px 15px 12px;transition:border-color .12s,transform .12s}
.addvid .path:hover{border-color:var(--accentlt);transform:translateY(-1px)}
.addvid .path:focus-visible{outline:2px solid var(--accentlt);outline-offset:2px}
.addvid .path b{display:block;font-size:15px;font-weight:600;color:var(--ink)}
.addvid .path span{display:block;margin-top:4px;font-size:12.5px;line-height:1.5;color:var(--dim)}
.addvid .path em{display:block;margin-top:8px;font-style:normal;font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
/* "chosen" wears the chip row's own signature (parseh.css .chip.on) */
.addvid .path[aria-checked="true"]{border-color:var(--accent);background:var(--hl)}
.addvid .path[aria-checked="true"] em{color:var(--accent)}
.addvid .pathnote{max-width:34rem;margin:0 auto;padding:26px 0;text-align:center;
  color:var(--dim);font-size:13px;line-height:1.6}
.addvid .pathnote b{color:var(--ink)}
.addvid .pathnote a{color:var(--accent)}
.addvid .pathnote .also{display:block;margin-top:10px;color:var(--faint);font-size:12px}

/* ---------------- one sentence under one control ---------------- */
.addvid .fieldnote{display:block;margin-top:4px;font-size:12px;line-height:1.5;color:var(--faint)}
.addvid .fieldnote b{color:var(--dim)}
.addvid .fieldnote.warn{color:var(--warn)}
.addvid .whysmall{display:none}
@media (max-width:620px){.addvid .whysmall{display:block}}

/* ---------------- the disclosure ----------------
   The narration panel's device, in this page's tokens: what is read once and
   never again must not sit between a person and the buttons. */
.addvid .hbtn{font:inherit;font-size:13px;padding:5px 10px;border:1px solid var(--rule);
  background:transparent;color:var(--dim);border-radius:6px;cursor:pointer;margin-top:14px}
.addvid .hbtn:hover{border-color:var(--accentlt);color:var(--accent)}
.addvid .hbox{background:var(--boxbg);border:1px solid var(--rule);border-radius:10px;
  padding:10px 12px;margin-top:10px}
.addvid .hbox p{font-size:12.5px;line-height:1.55;color:var(--faint);margin:0 0 8px}
.addvid .hbox p:last-child{margin-bottom:0}
.addvid .hbox p b{color:var(--dim)}
.addvid .hbox label{margin-top:0}
</style>
'''

ADD_PAGE_JS = r'''
<script>
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var BASE = __BASE__;
  var LANGS = __LANGS_JSON__;      // {code: {name, dir}} in registry order, from the server
  var GLOSSES = __GLOSSES_JSON__;  // {code: {name, dir, taught}} -- what a gloss may be in
  var KEY = 'yt_add_draft';
  // The gloss language outlives one video: whoever glosses in Italian will
  // gloss the next one in Italian too, and the draft below is thrown away
  // the moment a video is added, so it cannot remember this.  Its own key,
  // and not the toolbox's shared parseh_lang, because that preference
  // answers "whose content am I looking at" and this one answers "what do
  // I write in" -- an Italian studying Persian sets them to two things.
  var GKEY = 'yt_add_gloss';
  // The two answers this page now asks for, and which endpoint each pair
  // reaches: {yt, llm} prepare+add | {film, llm} prepare+add with the film |
  // {yt, empty} /api/empty | {film, empty} /api/local.  All four are real
  // and all four were implemented; the source axis was chosen by NO control
  // at all, only by whether the URL box happened to be empty.
  var SRC = '', BY = '';
  var PROMPT = '';
  // THE ROW OF CONTROLS AROUND THE PROMPT (/lib/llmrow.js).  What a press of
  // "Prepare the prompt" makes is held by it: it says the size, and the press
  // on "copy the prompt" that follows puts on the clipboard the very text the
  // box below shows.  Without its script there is nothing to copy with, and
  // the page says so.
  var promptRow = window.ParsehLLMRow ? ParsehLLMRow.mount($('prow'), {
    surface: 'video-new', cls: 'wbtn', menu: false,
    ids: {copy: 'pcopy', size: 'psize', say: 'pcopysay'},
    remind: 'paste it into a chatbot, then paste its whole answer in step 4 below.',
    box: function () { $('pshow').open = true; return $('prompt'); }
  }) : (function () {
    $('prow').textContent = 'the prompt helper could not be loaded';
    var no = function () {};
    return {update: no, forget: no};
  }());
  // THE OPTIONS OF THE PROMPT (the scheme of the transliteration, the short vowels) are chosen BEFORE it
  // is prepared, so they sit above the button that prepares it and not in the row, which only appears
  // with a prompt.  They follow the language chosen above (langChanged); a prompt prepared for other
  // choices is out of date, like one prepared for another language
  var promptOpts = window.ParsehLLMRow && ParsehLLMRow.options ? ParsehLLMRow.options($('popts'), {
    surface: 'video-new',
    onOption: function () { forgetPrompt(); $('pinfo').hidden = true; }
  }) : {options: function () { return {}; }, setLang: function () {}};
  // THE PROMPT TO PREPARE, Parseh's or one of the person's own, is chosen above the button, as the options are
  // (the row has no prompt to hold until one is prepared): the choice goes into the request `prepare` makes,
  // the menu lists the prompts for the language chosen above, and a prompt prepared for another is out of date
  var promptMenu = window.ParsehLLMRow && ParsehLLMRow.menu ? ParsehLLMRow.menu($('pmenu'), {
    surface: 'video-new', lang: val('lang') || undefined,
    onPrompt: function () { forgetPrompt(); $('pinfo').hidden = true; }
  }) : {id: function () { return ''; }, setLang: function () {}};
  // The id a local film's video will have, given by `prepare` and handed
  // back to `add`, so the prompt's `id:` line and the directory finally
  // written are the same id.
  var LOCALID = '';
  // every field the page keeps, including the ones that used to be forgotten
  // on every reload: the film's path, the way of cutting, and the five
  // details.  Remembering that you chose "a film on this machine" and
  // forgetting WHICH film is worse than forgetting both.
  var SAVED = ['url', 'path', 'transcript', 'answer', 'glossary', 'lang', 'gloss', 'how',
               'ov_title', 'ov_channel', 'ov_level', 'ov_title_native', 'ov_blurb'];
  // every read is guarded, so a control that is not on this build of the
  // page can never take the whole script down with it
  function val(id, v) {
    var el = $(id);
    if (!el) return '';
    if (v !== undefined && v !== null) el.value = v;
    return el.value;
  }
  // The language select: its default is the toolbox's shared preference
  // (Parseh.lang, kept by /lib/parseh.js) when that names one language;
  // "all" or no preference leaves the first language (the registry's
  // order puts Persian first).  A draft's own choice wins over both.
  try {
    var pref = window.Parseh && Parseh.lang && Parseh.lang.get ? Parseh.lang.get() : '';
    if (pref && LANGS[pref]) val('lang', pref);
    var gpref = localStorage.getItem(GKEY);
    if (gpref && GLOSSES[gpref]) val('gloss', gpref);
  } catch (e) {}
  // a draft survives a reload: the transcript is long and the answer longer
  var saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(KEY) || '{}');
    SAVED.forEach(function (k) { if (saved[k]) val(k, saved[k]); });
    if (saved.lang && LANGS[saved.lang]) val('lang', saved.lang);
    if (saved.gloss && GLOSSES[saved.gloss]) val('gloss', saved.gloss);
  } catch (e) {}
  function save() {
    var o = {};
    SAVED.forEach(function (k) { o[k] = val(k); });
    o.src = SRC; o.by = BY;
    try { localStorage.setItem(KEY, JSON.stringify(o));
      localStorage.setItem(GKEY, val('gloss')); } catch (e) {}
  }
  SAVED.forEach(function (k) {
    var el = $(k);
    if (!el) return;
    el.addEventListener('input', function () { save(); ticks(); });
    el.addEventListener('change', function () { save(); ticks(); });
  });
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  // the three doors that take a while -- a prompt made, a video added, a
  // film put beside its captions -- are on the activity list while they run
  // (lib/activity.js, through parseh.js)
  var WORK = {'/api/prepare': 'Preparing the prompt', '/api/add': 'Adding the video',
              '/api/local': 'Adding the video from its file'};
  function post(path, body) {
    var act = WORK[path] && window.Parseh && Parseh.working ? Parseh.working(WORK[path])
      : {url: function (u) { return u; }, end: function () {}};
    return fetch(act.url(BASE + path), {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})
      .then(function (r) { return r.json(); })
      .then(function (j) { act.end(!!(j && j.ok)); return j; },
            function (e) { act.end(false); throw e; });
  }
  function overrides() {
    return {title: val('ov_title'), channel: val('ov_channel'),
            level: val('ov_level'), title_native: val('ov_title_native'),
            blurb: val('ov_blurb')};
  }
  // ANY PREPARED PROMPT IS OUT OF DATE.  It names the language and the gloss
  // language, and its head says whether the video is on YouTube or a film on
  // this machine -- so all three invalidate it, and the id minted for a film
  // goes with them.
  function forgetPrompt() {
    PROMPT = ''; $('pshow').hidden = true; $('pshow').open = false;
    $('prow').hidden = true; promptRow.forget();
  }
  // The prompt is built FROM the transcript, the video and the language, so
  // anything that changes one of them makes it stale -- typing in the box, an
  // edit made in the editor, a transcript made by speech to text.  What it said
  // about itself goes too (how many captions, "prepared").  ONE place, so no
  // road that changes the box can forget it.
  function invalidatePrepared() { forgetPrompt(); $('pinfo').hidden = true; }
  // the speech block (youtube/lib/addstt.js), once it is mounted at the end
  var stt = null;

  /* ---------------- the two questions ---------------- */
  function choose(src, by, push, focusIt) {
    if (src !== undefined && src !== null && src !== SRC) {
      // leaving a source behind CLEARS it.  A hidden input keeps its value,
      // and sending both is what earns "a video is either an address or a
      // file on this machine, and this names both" -- naming a field that is
      // no longer on screen to clear.
      if (SRC === 'yt') val('url', '');
      if (SRC === 'film') val('path', '');
      SRC = src; LOCALID = ''; forgetPrompt();
      if (stt) stt.sourceChanged();
    }
    if (by !== undefined && by !== null) BY = by;
    Array.prototype.forEach.call(document.querySelectorAll('#q1 .path'), function (b) {
      var on = b.dataset.src === SRC;
      b.setAttribute('aria-checked', String(on));
      b.tabIndex = on ? 0 : (SRC ? -1 : b.tabIndex);
    });
    Array.prototype.forEach.call(document.querySelectorAll('#q2 .path'), function (b) {
      var on = b.dataset.by === BY;
      b.setAttribute('aria-checked', String(on));
      b.tabIndex = on ? 0 : (BY ? -1 : b.tabIndex);
    });
    $('src-yt').hidden = SRC !== 'yt';
    $('src-film').hidden = SRC !== 'film';
    $('filmhow').hidden = SRC !== 'film';
    if (SRC !== 'film') $('how-film').hidden = true;
    $('subline').hidden = SRC !== 'film';
    $('emptynote').hidden = !(SRC === 'film' && BY === 'empty');
    $('step-llm-3').hidden = BY !== 'llm';
    $('step-llm-4').hidden = BY !== 'llm';
    $('step-empty-3').hidden = BY !== 'empty';
    // no oEmbed for a film: nobody is going to be asked for the title, and
    // the page has never said so
    var fetched = (SRC === 'yt');
    $('ov_title').placeholder = fetched ? 'fetched from YouTube when possible'
                                        : 'no YouTube to ask — the file\'s name is used';
    $('ov_channel').placeholder = fetched ? 'fetched from YouTube when possible'
                                          : 'on this machine';
    $('ov_level_blank').textContent = (BY === 'llm') ? 'from the answer' : 'not set';
    $('ovsum').textContent = (BY === 'llm' && fetched)
      ? 'Details the answer may not know (optional)'
      : 'Details this page cannot fetch (optional)';
    var both = !!(SRC && BY);
    $('vbody').hidden = !both;
    $('nopath').hidden = both;
    if (!both) {
      $('nopath').innerHTML = (!SRC && !BY) ? 'Answer both to go on.'
        : (!SRC ? 'Now say <b>where the video is</b>.' : 'Now say <b>who writes the glosses</b>.');
      $('nopath').innerHTML += '<span class="also">Already have an exported ' +
        '<code>&lt;id&gt;-video.zip</code>? Bring it back from <a href="' + BASE +
        '/">the videos page</a>.</span>';
    }
    ticks();
    save();
    if (push) {
      try {
        var q = [];
        if (SRC) q.push('src=' + SRC);
        if (BY) q.push('by=' + BY);
        history.replaceState(null, '', BASE + '/add/' + (q.length ? '?' + q.join('&') : ''));
      } catch (e) {}
    }
    if (focusIt && both) {
      var el = $('vbody').querySelector('input:not([hidden]),select,textarea');
      if (el) el.focus({preventScroll: true});
    }
  }
  function wireQ(box, attr) {
    Array.prototype.forEach.call(document.querySelectorAll(box + ' .path'), function (b) {
      b.addEventListener('click', function () {
        if (attr === 'src') choose(b.dataset.src, null, true, true);
        else choose(null, b.dataset.by, true, true);
      });
      b.addEventListener('keydown', function (e) {
        var keys = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1};
        if (!(e.key in keys)) return;
        e.preventDefault();
        var all = Array.prototype.slice.call(document.querySelectorAll(box + ' .path'));
        var next = all[(all.indexOf(b) + keys[e.key] + all.length) % all.length];
        next.focus();
        if (attr === 'src') choose(next.dataset.src, null, true, false);
        else choose(null, next.dataset.by, true, false);
      });
    });
  }
  wireQ('#q1', 'src');
  wireQ('#q2', 'by');
  function tick(id, ok) { var el = $(id); if (el) el.classList.toggle('ok', !!ok); }
  function ticks() {
    tick('step-1', !!source().trim());
    tick('step-2', !!val('transcript').trim());
  }
  // what follows the language: the native-title field's label and direction,
  // and the face the transcript and the prompt are shown in
  function langChanged() {
    var code = val('lang'), L = LANGS[code] || {name: code, dir: 'ltr'};
    $('ov_native_lab').textContent = L.name;
    ['transcript', 'prompt', 'ov_title_native'].forEach(function (id) { $(id).setAttribute('data-lang', code); });
    if (L.dir === 'rtl') $('ov_title_native').setAttribute('dir', 'rtl');
    else $('ov_title_native').removeAttribute('dir');
    forgetPrompt();          // the prompt was prepared for the previous language
    promptOpts.setLang(code); // and the choices for it are the new language's own
    promptMenu.setLang(code); // and so are the prompts of the person's own it is offered
    if (stt) stt.langChanged();
  }
  $('lang').addEventListener('change', langChanged);
  // the prompt names the gloss language and asks for the meanings in it,
  // so a prepared one is out of date the moment that changes
  $('gloss').addEventListener('change', forgetPrompt);
  // a prompt is prepared for one source, one transcript and one word list: a
  // change to any of them, made by typing, makes it stale (these used to be
  // forgotten only when the source CARD was changed)
  $('path').addEventListener('input', function () { LOCALID = ''; invalidatePrepared(); if (stt) stt.sourceChanged(); });
  $('url').addEventListener('input', function () { invalidatePrepared(); if (stt) stt.sourceChanged(); });
  $('transcript').addEventListener('input', function () { invalidatePrepared(); if (stt) stt.redraw(); });
  $('glossary').addEventListener('change', invalidatePrepared);

  /* ---------------- the chosen source, and nothing else ---------------- */
  function source() { return SRC === 'film' ? val('path') : val('url'); }
  // ONLY THE CHOSEN SOURCE TRAVELS.  one_source()'s refusal is now
  // unreachable from this page rather than merely caught: the key that was
  // not chosen is sent empty whatever the other box still holds.
  function who() {
    var film = SRC === 'film';
    var s = source().trim();
    if (!s) {
      Parseh.toast(film ? 'name the video or sound on this machine' : 'paste the URL', true);
      $(film ? 'path' : 'url').focus();
      return null;
    }
    return {url: film ? '' : s, path: film ? s : '', id: film ? LOCALID : ''};
  }
  function needTranscript() {
    if (val('transcript').trim()) return true;
    Parseh.toast('paste the transcript first', true);
    $('transcript').focus();
    return false;
  }
  // a body that is too big comes back as "bad size (N bytes)", which says
  // nothing about what to do; the likely cause is nameable
  function why(j) {
    var e = j.error || 'failed';
    if (/^bad size/.test(e))
      e += ' — the transcript and the answer together are too long for one request; ' +
           'add the answer in two goes, or shorten the transcript.';
    return e;
  }

  /* ---- the transcript, edited before anything is built from it ----
     The panel goes to the editor and comes back a panel, so every road out
     of this page reads it as it always did; the box is the only thing that
     changed.  A YouTube video is handed its id, and the editor plays it so a
     nudge can be answered by ear (it records nothing: the picture of the
     sound is the player's, and speech to text's recording is the block
     above the button); a film on this machine is not in the player yet, so it
     is edited by eye and by typing. */
  function ytId(u) {
    var m = /(?:youtube\.com\/(?:watch\?(?:[^&]*&)*v=|shorts\/|embed\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/.exec(u || '');
    if (m) return m[1];
    return /^[A-Za-z0-9_-]{11}$/.test((u || '').trim()) ? (u || '').trim() : '';
  }
  $('subedit').onclick = function () {
    if (!needTranscript()) return;
    if (!window.ParsehSubedit) { Parseh.toast('the transcript editor did not load', true); return; }
    // the editor plays its own copy of the video: not while another is being recorded
    var busy = stt && stt.guardEdit();
    if (busy) { Parseh.toast(busy, true); return; }
    var was = val('transcript');
    $('sestat').textContent = '';
    ParsehSubedit.open({
      base: BASE, lang: val('lang'),
      video: SRC === 'film' ? '' : ytId(val('url')),
      transcript: was,
      wordJob: stt && stt.words ? stt.words() : ''
    }).then(function (text) {
      if (text == null) { $('sestat').textContent = 'left as it was'; return; }
      val('transcript', text);
      $('sestat').textContent = text === was ? 'unchanged' : 'the transcript was edited';
      // whatever was prepared was prepared from the old panel
      invalidatePrepared();
      save(); ticks();
      if (stt) stt.redraw();
    }, function (err) {
      Parseh.toast((err && err.message) || String(err), true);
    });
  };

  $('prepare').onclick = function () {
    var w = who();
    if (!w) return;
    if (!needTranscript()) return;
    $('pstat').textContent = 'preparing…'; $('pinfo').hidden = true;
    post('/api/prepare', Object.assign({url: w.url, path: w.path, id: w.id,
                          transcript: val('transcript'), glossary: val('glossary'),
                          lang: val('lang'), gloss: val('gloss')}, promptOpts.options(),
                          promptMenu.id() ? {prompt: promptMenu.id()} : {}))
      .then(function (j) {
        $('pstat').textContent = '';
        if (!j.ok) { $('pinfo').hidden = false; $('pinfo').className = 'note bad';
          $('pinfo').textContent = why(j); return; }
        PROMPT = j.prompt;
        if (j.local) LOCALID = j.id;
        $('prompt').value = PROMPT; $('pshow').hidden = false;
        if (j.title && !val('ov_title')) $('ov_title').placeholder = j.title;
        if (j.channel && !val('ov_channel')) $('ov_channel').placeholder = j.channel;
        $('replacerow').hidden = !j.exists; $('existid').textContent = 'videos/' + j.folder + '/' + j.id + '/';
        $('pinfo').hidden = false; $('pinfo').className = 'note ' + (j.exists ? 'warn' : 'good');
        $('pinfo').innerHTML = '<b>' + esc(j.id) + '</b>' +
          (j.title ? ' — ' + esc(j.title) + (j.channel ? ' (' + esc(j.channel) + ')' : '') : '') +
          ': ' + j.captions + ' captions, ' + j.want + ' to annotate, ' + j.plain + ' plain, ~' +
          esc(j.duration) + '.' +
          (j.exists ? '<br>This video is already in the player — adding it again will replace it.' : '');
        // NOT COPIED HERE: the row says how long the prompt is first, and the
        // press on its button copies exactly what the box shows, as it is
        // (a prompt of numbered captions and fenced JSON keeps its line breaks)
        $('prow').hidden = false;
        promptRow.update(PROMPT);
        // the short request for a chat that has the skill was made with the prompt: the row holds it beside it
        if (promptRow.skillOf) promptRow.skillOf(j.skill);
      }).catch(function (e) { $('pstat').textContent = ''; Parseh.toast(String(e), true); });
  };
  // A stray line some copies of the transcript panel repeat on every
  // caption -- a second timestamp, a duration the parser's DURATION regex
  // does not recognise in that panel's language -- falls at the same
  // position in every group, so naming the group size and that position
  // (both counted from the first pasted line as 0) removes it everywhere
  // at once, in place, before anything downstream reads the box.
  $('cleanlines').onclick = function () {
    var mod = parseInt($('clnMod').value, 10), rem = parseInt($('clnRem').value, 10);
    if (!(mod >= 2)) { Parseh.toast('give a group size of at least 2', true); $('clnMod').focus(); return; }
    if (isNaN(rem)) rem = 0;
    rem = ((rem % mod) + mod) % mod;
    var lines = val('transcript').split('\n'), kept = [], removed = 0;
    for (var i = 0; i < lines.length; i++) {
      if (i % mod === rem) { removed++; continue; }
      kept.push(lines[i]);
    }
    if (!removed) { Parseh.toast('no pasted line sits at that position', true); return; }
    val('transcript', kept.join('\n'));
    invalidatePrepared();
    save();
    if (stt) stt.redraw();
    Parseh.toast(removed + ' line' + (removed === 1 ? '' : 's') + ' removed');
  };
  // No prompt and no answer: the transcript as it stands, cut into blank
  // chunks, to gloss in the player.  WHICH DOOR is the answer to question 1
  // -- a film goes down the road that puts the film beside the transcript --
  // instead of being decided by whether a box was left empty.
  $('empty').onclick = function () {
    var w = who();
    if (!w) return;
    if (!needTranscript()) return;
    var ov = overrides();
    $('estat').textContent = 'drafting…'; $('empty').disabled = true;
    var res = $('eresult'); res.hidden = true;
    var body = {url: w.url, path: w.path, id: w.id,
                lang: val('lang'), gloss: val('gloss'),
                transcript: val('transcript'),
                title: ov.title, title_native: ov.title_native,
                channel: ov.channel, level: ov.level, blurb: ov.blurb,
                how: val('how')};
    // the shape of the sound a transcription held for THIS video comes with it
    var held = stt && stt.wave();
    if (held) body.wave = held;
    var heldWords = stt && stt.words && stt.words();
    if (heldWords) body.wordtimes = heldWords;
    post(SRC === 'film' ? '/api/local' : '/api/empty', body)
      .then(function (j) {
        $('empty').disabled = false; $('estat').textContent = ''; res.hidden = false;
        if (!j.ok) {
          // the endpoint's own sentence, which says what is wrong with the
          // transcript or the language -- never "failed"
          res.innerHTML = '<div class="note bad"><b>' + esc(why(j)) + '</b></div>';
          res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
          return;
        }
        var href = BASE + '/v/' + encodeURIComponent(j.id) + '/';
        // a film that could not be LINKED was copied: on another disk that is
        // minutes of I/O and gigabytes, and it used to be reported in exactly
        // the same words as an instant hardlink
        var film = (j.how === 'copied')
          ? ' The film was copied (' + Math.round((j.bytes || 0) / 1048576) +
            ' MB) — this filesystem would not take a link.'
          : '';
        if (j.note) film += ' ' + j.note + '.';
        res.innerHTML = '<div class="note good"><b>Drafted.</b> ' + j.captions + ' captions, ' +
          j.glossed + ' to gloss, ' + j.plain + ' plain, ' + j.chunks + ' blank chunks, in <code>videos/' +
          esc(j.folder) + '/' + esc(j.id) + '/</code>.' + esc(film) + ' <a href="' + esc(href) +
          '"><b>Open the player &rarr;</b></a></div>';
        try { localStorage.removeItem(KEY); } catch (e) {}
        if (stt) stt.videoAdded();
        location.href = href;          // the glossing is done there, not here
      }).catch(function (e) { $('empty').disabled = false; $('estat').textContent = '';
        Parseh.toast(String(e), true); });
  };
  $('add').onclick = function () {
    var w = who();
    if (!w) return;
    if (!val('transcript').trim()) { Parseh.toast('the transcript is needed too', true); return; }
    if (!val('answer').trim()) { Parseh.toast('paste the answer first', true); $('answer').focus(); return; }
    $('astat').textContent = 'checking…'; $('add').disabled = true;
    var res = $('result'); res.hidden = true;
    // the scheme the prompt asked for is the video's own from now on (video.json "translit")
    var body = Object.assign({url: w.url, path: w.path, id: w.id,
                transcript: val('transcript'), answer: val('answer'),
                replace: $('replace').checked,
                overrides: overrides(), lang: val('lang'),
                gloss: val('gloss')}, promptOpts.options());
    var held = stt && stt.wave();
    if (held) body.wave = held;
    var heldWords = stt && stt.words && stt.words();
    if (heldWords) body.wordtimes = heldWords;
    post('/api/add', body)
      .then(function (j) {
        $('add').disabled = false; $('astat').textContent = '';
        res.hidden = false;
        var h = '';
        if (j.ok) {
          h += '<div class="note good"><b>Added.</b> ' + j.glossed + ' captions glossed, ' +
            j.captions + ' captions in all. ' +
            // the chunks the answer left blank: legal, and theirs to fill
            (j.blank ? j.blank + ' chunk' + (j.blank === 1 ? ' was' : 's were') +
              ' left without a gloss, to fill in the player. ' : '') +
            // the word lines the answer left out, which the server proposed
            (j.proposed ? j.proposed + ' chunk' + (j.proposed === 1 ? '' : 's') +
              ' had the words proposed by machine, to correct in the player. ' : '') +
            // the shape of the sound recorded while the transcript was made
            (j.waveform && j.waveform.kept ? 'Its waveform came with it. ' : '') +
            // what became of a sound a browser cannot play
            (j.film && j.film.note ? esc(j.film.note) + '. ' : '') +
            '<a href="' + esc(j.href) + '"><b>Open the video &rarr;</b></a></div>';
          try { localStorage.removeItem(KEY); } catch (e) {}
          if (stt) stt.videoAdded();
        } else {
          h += '<div class="note bad"><b>' + esc(why(j)) + '</b></div>';
          if (j.exists) { $('replacerow').hidden = false;
            // the server names where the existing copy sits (it may be under
            // another language's folder); the fallback is this language's
            // folder, never its code -- videos/japanese/, not videos/ja/
            var m = val('url').match(/[A-Za-z0-9_-]{11}/);
            $('existid').textContent = j.dir ? j.dir + '/' :
              'videos/' + ((LANGS[val('lang')] || {}).folder || val('lang')) + '/' + (m ? m[0] : '?') + '/'; }
        }
        var probs = (j.problems || []).filter(function (p) { return !/^note:/.test(p); });
        if (probs.length) h += '<div class="note bad"><b>To fix, then paste again:</b><pre>' +
          esc(probs.join('\n')) + '</pre>' +
          '<span class="fieldnote">Paste these lines to the LLM as they are: it answers with the corrected captions only, ' +
          'and that block goes under the first answer in the box above &mdash; a caption given again there replaces ' +
          'the first one.</span></div>';
        if (j.merge || j.check) h += '<details' + (j.ok ? '' : ' open') + '><summary>What the pipeline said</summary><pre>' +
          esc((j.merge || '') + '\n' + (j.check || '')) + '</pre></details>';
        var notes = (j.problems || []).filter(function (p) { return /^note:/.test(p); }).concat(j.warnings || []);
        if (notes.length) h += '<details><summary>' + notes.length + ' note(s)</summary><pre>' + esc(notes.join('\n')) + '</pre></details>';
        res.innerHTML = h;
        res.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      }).catch(function (e) { $('add').disabled = false; $('astat').textContent = ''; Parseh.toast(String(e), true); });
  };
  Array.prototype.forEach.call(document.querySelectorAll('.hbtn'), function (b) {
    b.onclick = function () {
      var box = $(b.getAttribute('aria-controls'));
      var open = box.hidden;
      box.hidden = !open;
      b.setAttribute('aria-expanded', String(open));
    };
  });
  langChanged();
  // the address wins over the draft, and an unknown value falls back to the
  // question rather than hiding everything
  var q = location.search;
  var qs = (q.match(/[?&]src=([a-z]+)/) || [])[1] || saved.src || '';
  var qb = (q.match(/[?&]by=([a-z]+)/) || [])[1] || saved.by || '';
  if (qs !== 'yt' && qs !== 'film') qs = '';
  if (qb !== 'llm' && qb !== 'empty') qb = '';
  // SRC is set directly, not through choose()'s source-change branch, so a
  // restored draft's own url/path is not cleared on the way in
  SRC = qs; BY = qb;
  choose(SRC, BY, false, false);
  // SPEECH TO TEXT, if this computer has it (youtube/lib/addstt.js draws the
  // block, asks the computer and does all of it): this page only tells it what
  // the chosen video, language and box are, and takes what it writes.  Mounted
  // last, so that the draft above has already put back what the person left.
  if (window.ParsehAddStt) {
    stt = ParsehAddStt.mount({
      root: $('stt'), base: BASE, toast: Parseh.toast,
      source: function () { return {kind: SRC, value: source().trim()}; },
      lang: function () {
        var c = val('lang'), L = LANGS[c] || {name: c, native: ''};
        return {code: c, name: L.name, native: L.native};
      },
      transcript: function () { return val('transcript'); },
      setTranscript: function (text) { val('transcript', text); save(); ticks(); },
      restorePending: function (src, lang, text) {
        choose(src.kind === 'film' ? 'film' : 'yt', BY === 'llm' ? 'llm' : 'empty', false, false);
        val(src.kind === 'film' ? 'path' : 'url', src.kind === 'film' ? src.path : 'https://www.youtube.com/watch?v=' + src.id);
        val('lang', lang); val('transcript', text || ''); save(); ticks();
      },
      invalidate: invalidatePrepared,
      focusSource: function () { $(SRC === 'film' ? 'path' : 'url').focus(); },
      // what may not change while a job runs: the video, its language
      lock: ['#q1', '#url', '#path', '#lang']
    });
  }
})();
</script>
'''

ADD_FOOT = ('The same loop, by hand: <code>youtube/PROMPT.md</code>. What the page writes '
            'is exactly what that prompt asks for &mdash; <code>transcript.txt</code>, '
            '<code>video.json</code>, <code>parts/*.json</code> &mdash; and it runs '
            '<code>merge_parts.py</code> and <code>check_annotations.py</code> on them, '
            'then drops the batches: a video on the shelf has no <code>parts/</code>.')


def add_page():
    hows = "".join('<option value="%s"%s>%s</option>'
                   % (w, " selected" if w == chunker.DEFAULT_WAY else "",
                      esc(chunker.WAY_LABEL[w])) for w in chunker.WAYS)
    gl = "".join('<option value="%s">%s</option>' % (esc(g["slug"]), esc(g["title"]))
                 for g in glossaries())
    # the languages in registry order; the page script picks the shared
    # preference, so no option is marked selected here
    langs = "".join('<option value="%s" lang="%s">%s &mdash; %s</option>'
                    % (L.code, L.code, esc(L.name), esc(L.native))
                    for L in languages.LANGS.values())
    langs_json = json.dumps({L.code: {"name": L.name, "native": L.native, "dir": L.dir,
                                      "folder": L.folder}
                             for L in languages.LANGS.values()}, ensure_ascii=False)
    # Every language a gloss may be written in, in two groups: the eight
    # the toolbox teaches (named by the registry, which is what names them
    # everywhere else on screen) and the prose-only ones it can still set.
    # The grouping is the honest label -- picking Spanish gets meanings in
    # Spanish and nothing else, no folder, no fonts, no note types.
    # English is marked selected HERE and not left to the page's script:
    # English is what a video that says nothing means, so the field must
    # already read it before any javascript has run.
    def gopt(G):
        return ('<option value="%s" lang="%s"%s>%s &mdash; %s</option>'
                % (esc(G.code), esc(G.code),
                   " selected" if G.code == languages.DEFAULT_GLOSS else "",
                   esc(G.name), esc(G.native)))
    glosses = ('<optgroup label="the languages this toolbox teaches">%s</optgroup>'
               '<optgroup label="prose only — not taught here">%s</optgroup>'
               % ("".join(gopt(G) for G in languages.GLOSSES.values() if G.taught),
                  "".join(gopt(G) for G in languages.GLOSSES.values() if not G.taught)))
    glosses_json = json.dumps({G.code: {"name": G.name, "native": G.native,
                                        "dir": G.dir, "taught": G.taught}
                               for G in languages.GLOSSES.values()},
                              ensure_ascii=False)
    # "index wizard", so this page and /books/add/ are one width
    # The transcript editor: the only page of this door that edits a panel,
    # and the only one that asks for it.  And speech to text, optional and
    # this page's alone: its block (addstt.js) is drawn from what the computer
    # says it has, and records a tab through tabcapture.js -- the page never
    # loads the card kit, which is the player's.
    head = page_head("Add a video", "Add a video",
                     "A video is glossed caption by caption, in the player.",
                     '<a href="%s/">videos</a> &rsaquo; add' % BASE,
                     "index wizard",
                     '<link rel="stylesheet" href="%s/lib/subedit.css">\n'
                     '<link rel="stylesheet" href="%s/lib/addstt.css">\n'
                     '<link rel="stylesheet" href="%s/lib/addfilm.css">\n'
                     '<script src="%s/lib/subedit.js"></script>\n'
                     '<script src="%s/lib/tabcapture.js"></script>\n'
                     '<script src="%s/lib/asrwalk.js"></script>\n'
                     '<script src="%s/lib/asrreview.js"></script>\n'
                     '<script src="%s/lib/addstt.js"></script>\n'
                     '<script src="%s/lib/addfilm.js"></script>\n'
                     '<script src="/lib/llmrow.js"></script>\n' % ((BASE,) * 9))
    return (head + ADD_PAGE_HEAD.replace("__GLOSSARIES__", gl)
                .replace("__HOWS__", hows).replace("__LANGS__", langs)
                                .replace("__GLOSSES__", glosses)
                                .replace("__ACCEPT__", esc("audio/*,video/*," + ",".join(bundle.MEDIA_EXTS)))
                                .replace("__BASE__", BASE)
            + ADD_PAGE_JS.replace("__BASE__", json.dumps(BASE))
                         .replace("__LANGS_JSON__", langs_json.replace("</", "<\\/"))
                         .replace("__GLOSSES_JSON__", glosses_json.replace("</", "<\\/"))
            + (PAGE_FOOT % ADD_FOOT))
