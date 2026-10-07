#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""/later/: every chunk a person flagged to review later, across every book
and video (a0.5.0).

The page the hub's "Review later" door opens.  It lists the flags grouped by
book or video -- the title, the language, how many -- each with the chunk, its
gloss, where it is and how long ago it was flagged, and a link that opens the
book or the video AT the chunk (`<reader path>#later=<id>`, `<player
path>#later=<id>`: the reader and the player open their own list on that
item and go to it).  "Test myself" and "Copy the list" work here as they do
in a book's own sidebar.

THE PAGE IS AN EMPTY FRAME.  What is in it is drawn by lib/later.js from the
door (/__later) AND from the device's own copy, so it is live, it lists what a
phone flagged away from the computer, and it opens with the computer away: the
frame is in the phone's offline shell (lib/offline.py, SHELL_PAGES) and the
flags are in its localStorage.

BOTH LAYOUTS IN ONE PAGE, as the licences are (lib/notices.py): the bar is
written twice, `data-layout="browser"` and `data-layout="mobile"`, and one
column under it serves both -- rows a finger's height under the mobile mode
(lib/later.css).  Nothing on it edits a book or a video: removing a flag, and
the list itself, are the person's own and the phone may do them.
"""
import html
import json

import languages
import mobile

APP = mobile.APP_NAME


def languages_said():
    """What the script needs to name a language and set its direction, for
    every language the registry holds (a language a person added is there):
    {code: {name, native, dir}}."""
    return {L.code: {"name": L.name, "native": L.native, "dir": L.dir}
            for L in languages.LANGS.values()}


def page():
    """/later/, the whole page."""
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review later &mdash; %(app)s</title>
%(apphead)s
<link rel="stylesheet" href="/lib/parseh.css">
<link rel="stylesheet" href="/lib/langs.css">
<link rel="stylesheet" href="/lib/mobile.css">
<link rel="stylesheet" href="/lib/later.css">
<script src="/lib/parseh.js"></script>
<script src="/lib/later.js" defer></script>
</head><body class="index" data-mobile-page>
<div class="parseh-bar" data-layout="browser">
  <a class="home" href="/"><span class="glyph" lang="fa">&#x67E;</span><span class="word">%(app)s</span></a>
  <span class="where">review later</span>
  <span class="sp"></span>
  %(modes)s
  <a class="parseh-btn" href="/guide/" title="the guide: how to use Parseh">guide</a>
  <button type="button" data-parseh-theme title="theme">&#9680;</button>
</div>
<div class="parseh-bar m-bar" data-layout="mobile">
  <a class="home" href="/"><span class="glyph" lang="fa">&#x67E;</span><span class="word">%(app)s</span></a>
  <span class="m-where">Review later</span>
  <span class="sp"></span>
  %(modes)s
  <button type="button" data-parseh-theme title="theme">&#9680;</button>
</div>
<main class="lp-main" data-later-page data-langs="%(langs)s">
  <h1 class="idx">review later</h1>
  <div id="lp-root"></div>
  <noscript><p class="sub">This list is drawn by a script, and this browser is not running it.</p></noscript>
</main>
</body></html>
""" % {"app": APP, "apphead": mobile.app_head(), "modes": mobile.mode_switch(),
       "langs": html.escape(json.dumps(languages_said(), sort_keys=True), quote=True)}
