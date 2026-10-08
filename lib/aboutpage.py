# SPDX-License-Identifier: GPL-3.0-or-later
"""Installation information, rendered with host-native paths on every OS, and a
few rough, friendly numbers about what is on the shelves (lib/aboutstats.py)."""
import platform
import time
from pathlib import Path
import aboutstats
import author
import languages
import settingspage

PAGE = '/settings/about/'
_KEPT = {}          # root -> (when counted, the numbers): counting reads every deck's answers, so not on every look
KEEP_SECONDS = 60


def stats(root):
    got = _KEPT.get(str(root))
    if got and time.monotonic() - got[0] < KEEP_SECONDS:
        return got[1]
    counted = aboutstats.collect(root)
    _KEPT[str(root)] = (time.monotonic(), counted)
    return counted


def story(root):
    """The section 'Your time with Parseh': four numbers, the day it began, and what the numbers are."""
    s = stats(root)
    names = {L.folder: L.name for L in languages.LANGS.values()}
    esc = settingspage.esc
    tiles = ''.join('<li><b>%s</b><span>%s</span><small>%s</small></li>' % (esc(n), esc(what), esc(note))
                    for n, what, note in aboutstats.tiles(s, names))
    since = aboutstats.since_line(s)
    return ('<h2 class="part">Your time with Parseh</h2><ul class="story">%s</ul>%s'
            '<p class="foot">Counted from what is on this computer, roughly: a deck that was deleted took its answers with it, '
            'and the hours are the videos&rsquo; lengths, not the time spent watching them.</p>'
            % (tiles, '<p class="since">%s</p>' % esc(since) if since else ''))


def page(where):
    root = Path(settingspage.ROOT)
    esc = settingspage.esc
    rows = [('Version', settingspage.parseh_version()), ('Author', author.NAME),
            ('Operating system', platform.system() + ' ' + platform.release()),
            ('Python', platform.python_version()), ('Installation folder', str(root)),
            ('serve.sh location', str(root / 'serve.sh')),
            ('Windows launcher', str(root / 'serve.bat')),
            ('Python launcher', str(root / 'serve.py')),
            ('Settings folder', str(root / 'config'))]
    table = ''.join('<dt>%s</dt><dd><code>%s</code></dd>' % (esc(k), esc(v)) for k, v in rows)
    main = '''<main class="settings tools">%s<h1 class="idx">About Parseh</h1>
<dl>%s</dl><p>Use serve.sh on Linux and macOS, or serve.bat on Windows. These paths belong to the computer running Parseh.</p>
%s
<p class="foot">Free software under the GNU GPL, version 3 or later.
<a href="/guide/">User guide</a> &middot; <a href="/licences/">Licences</a> &middot;
<a href="/settings/update/">Updating Parseh</a><br>%s</p></main>''' % (
        settingspage.settings_doors(PAGE), table, story(root), author.links())
    return settingspage.frame('About &mdash; %s settings' % settingspage.NAME,
        '<a href="/settings/">settings</a> &middot; about', 'About', '/guide/', main,
        style='.tools dl{display:grid;grid-template-columns:minmax(8rem,auto) minmax(0,1fr);gap:14px 20px;margin:24px 0;padding:18px;border:1px solid var(--rule);border-radius:10px;background:var(--card)}.tools dt{font-weight:600;font-size:14px}.tools dd{margin:0;overflow-wrap:anywhere;font-size:14px}.tools dd code{font-size:13px}@media(max-width:620px){.tools dl{grid-template-columns:minmax(0,1fr);gap:4px}.tools dt:not(:first-child){margin-top:12px}}'
              '.tools .part{font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:30px 0 10px}'
              '.tools .story{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr));gap:12px}'
              '.tools .story li{display:flex;flex-direction:column;gap:2px;padding:14px 16px;border:1px solid var(--rule);border-radius:10px;background:var(--card);min-width:0}'
              '.tools .story b{font-size:26px;font-weight:600;line-height:1.15;color:var(--accent);overflow-wrap:anywhere}'
              '.tools .story span{font-size:14px}.tools .story small{font-size:12.5px;color:var(--dim);line-height:1.4}'
              '.tools .since{margin:14px 0 0;font-size:14px}',
        extra_head='<link rel="stylesheet" href="/lib/settings-tools.css">')
