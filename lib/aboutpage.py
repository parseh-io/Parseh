# SPDX-License-Identifier: GPL-3.0-or-later
"""Installation information, rendered with host-native paths on every OS, a
few rough, friendly numbers about what is on the shelves (lib/aboutstats.py),
and, on the computer Parseh runs on, the server's log and a fault report
(lib/faultlog.py)."""
import platform
import time
from pathlib import Path
import aboutstats
import author
import faultlog
import languages
import network
import project
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


def _logbox(title, text, missing):
    esc = settingspage.esc
    if text is None:
        return '<details class="log"><summary>%s</summary><p class="help">%s</p></details>' % (esc(title), esc(missing))
    last = faultlog.tail(text)
    n = len(last.splitlines()) if last else 0
    return ('<details class="log"><summary>%s <small>(the last %d lines)</small></summary>'
            '<pre tabindex="0">%s</pre></details>' % (esc(title), n, esc(last) if last else '(empty)'))


FAULT_TEXT = (
    '<p class="help">If %(name)s stopped, or did something wrong, copy a report and paste it on %(issues)s '
    'with a line about what you were doing. The report says which version and which parts are installed, '
    'and the last error in the logs. Device keys, the pairing code, this network&rsquo;s addresses and your '
    'home folder are taken out of it.</p>'
    '<div class="actions"><button type="button" class="go" data-copy-report>Copy a report</button>'
    '<a class="plain" href="%(issues_url)s" target="_blank" rel="noopener">Open the issue page</a>'
    '<span class="msg" role="status" data-report-said></span></div>'
    '<details class="log"><summary>What the report says</summary>'
    '<pre tabindex="0" data-report>%(report)s</pre></details>%(this_run)s%(previous)s')


def fault_section(root, where):
    """When something goes wrong (TO-DO 5.31): the server's log, this run's and
    the run before's, and Copy a report -- ON THE COMPUTER PARSEH RUNS ON ONLY.
    A log names this computer's folders, the devices let in and the code that
    lets one in, so another device is told where to read it instead.  The page
    is drawn for each request, and what is not drawn is not sent: there is no
    route of its own to gate."""
    esc = settingspage.esc
    issues = '<a href="%s" target="_blank" rel="noopener">the issue page</a>' % esc(project.ISSUES_URL)
    head = '<h2 class="part" id="fault">When something goes wrong</h2>'
    if where != network.SELF:
        return (head + '<p class="help" data-fault-elsewhere>The server&rsquo;s log and the fault report are shown '
                'on the computer %s runs on only, because a log names that computer&rsquo;s folders and the '
                'devices let in. Open this page there to copy a report for %s.</p>' % (settingspage.NAME, issues))
    now, before, cur = faultlog.logs(root)
    if cur:
        this_run = _logbox("This run", now, "Its log file cannot be read.")
    else:
        this_run = ('<details class="log"><summary>This run</summary><p class="help">This run was started from '
                    'a terminal and writes its log there, not to a file. Started with serve.sh or serve.bat, '
                    'it keeps one.</p></details>')
    previous = _logbox("The run before", before, "There is no log of a run before this one.")
    text = faultlog.report(root, settingspage.parseh_version())
    return head + FAULT_TEXT % {"name": settingspage.NAME, "issues": issues, "issues_url": esc(project.ISSUES_URL),
                                "report": esc(text), "this_run": this_run, "previous": previous}


COPY_SCRIPT = """<script>(function () {
  var b = document.querySelector('[data-copy-report]');
  if (!b) return;
  b.addEventListener('click', function () {
    var text = document.querySelector('[data-report]').textContent;
    var m = document.querySelector('[data-report-said]');
    var done = function () { m.textContent = 'Copied: paste it on the issue page.'; };
    var by_hand = function () { m.textContent = 'Open "What the report says", select it and copy it.'; };
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(done, function () {
      var t = document.createElement('textarea');
      t.value = text; document.body.appendChild(t); t.select();
      try { if (document.execCommand('copy')) done(); else by_hand(); } catch (e) { by_hand(); }
      document.body.removeChild(t);
    });
  });
})();</script>"""


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
%s
<p class="foot">Free software under the GNU GPL, version 3 or later.
<a href="/guide/">User guide</a> &middot; <a href="/licences/">Licences</a> &middot;
<a href="/settings/update/">Updating Parseh</a><br>%s</p></main>''' % (
        settingspage.settings_doors(PAGE), table, story(root), fault_section(root, where), author.links())
    return settingspage.frame('About &mdash; %s settings' % settingspage.NAME,
        '<a href="/settings/">settings</a> &middot; about', 'About', '/guide/', main,
        style='.tools dl{display:grid;grid-template-columns:minmax(8rem,auto) minmax(0,1fr);gap:14px 20px;margin:24px 0;padding:18px;border:1px solid var(--rule);border-radius:10px;background:var(--card)}.tools dt{font-weight:600;font-size:14px}.tools dd{margin:0;overflow-wrap:anywhere;font-size:14px}.tools dd code{font-size:13px}@media(max-width:620px){.tools dl{grid-template-columns:minmax(0,1fr);gap:4px}.tools dt:not(:first-child){margin-top:12px}}'
              '.tools .part{font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:30px 0 10px}'
              '.tools .story{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr));gap:12px}'
              '.tools .story li{display:flex;flex-direction:column;gap:2px;padding:14px 16px;border:1px solid var(--rule);border-radius:10px;background:var(--card);min-width:0}'
              '.tools .story b{font-size:26px;font-weight:600;line-height:1.15;color:var(--accent);overflow-wrap:anywhere}'
              '.tools .story span{font-size:14px}.tools .story small{font-size:12.5px;color:var(--dim);line-height:1.4}'
              '.tools .since{margin:14px 0 0;font-size:14px}'
              '.tools details.log{border:1px solid var(--rule);border-radius:9px;background:var(--card);margin:12px 0}'
              '.tools details.log>summary{cursor:pointer;padding:11px 14px;font-size:14px;font-weight:600}'
              '.tools details.log small{font-weight:400;color:var(--dim)}'
              '.tools details.log>.help{padding:0 14px}'
              '.tools details.log pre{margin:0;padding:10px 14px 14px;max-height:24rem;overflow:auto;font-size:12px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere;direction:ltr;text-align:left}'
              '.tools .actions .msg{align-self:center;font-size:13.5px;color:var(--dim)}',
        script=COPY_SCRIPT, extra_head='<link rel="stylesheet" href="/lib/settings-tools.css">')
