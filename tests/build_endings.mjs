// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/build_endings.mjs
//
// A BUILD'S LAST WORDS, ON THE PAGE (TO-DO §5.8).  build.sh speaks to a
// terminal as well: "NO LOG … lualatex did not run", "Serve everything with:
// ./serve.sh", and a hyphenation warning whose fix was "./install.sh --pdf".
// A build started from a page reaches it through lib/bookbuild.py's job log,
// which now says those things in plain words.  Here a real bookbuild job is
// fed build.sh's own lines (its runner, as tests/test_book_build.py feeds it),
// and the log it keeps is what the page's status route answers; lib/parseh.js's
// buildBook is driven on a page and its toast read:
//   - a build that failed because LaTeX did not run says so, and that Parseh
//     cannot install LaTeX from its pages yet -- no command, no NO LOG;
//   - a build that ended well but without hyphenation patterns says "built"
//     and why its lines break where English words would -- no ./install.sh;
//   - while it runs, no line of it tells anyone to serve or install anything.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };

// a real bookbuild job, fed build.sh's own words -> the log its status answers
async function jobLog(lines, code) {
  const o = await new Deno.Command(PY, {args: ['-c', String.raw`
import json, os, sys, tempfile, time
sys.path.insert(0, 'lib')
import bookbuild
lines, code = json.loads(sys.argv[1]), int(sys.argv[2])
book = os.path.join(tempfile.mkdtemp(), 'books', 'german', 'tale')
os.makedirs(book)
def runner(cmd, say):
    for l in lines:
        say(l)
    return code
bookbuild.start(book, 'pdf', runner=runner)
while bookbuild.status(book)['state'] == 'running':
    time.sleep(0.02)
print(json.dumps(bookbuild.status(book)))
`, JSON.stringify(lines), String(code)], cwd: root, stdout: 'piped', stderr: 'piped'}).output();
  if (o.code) throw Error(td.decode(o.stderr));
  return JSON.parse(td.decode(o.stdout));
}

const NO_LATEX = ['== tale', '   NO LOG at /books/german/tale/main.log -- lualatex did not run',
                  '   the PDF did not build -- writing the reader anyway', '', '0 book(s) built, 0 unchanged',
                  'Serve everything with:  ./serve.sh', 'at least one PDF did not build; its reader was written, see above'];
const NO_HYPHEN = ['== tale', '   pdf: 0 overfull boxes, 12 pages',
                   '   NO HYPHENATION PATTERNS for ngerman -- every line was broken at ENGLISH',
                   '   points.  The PDF is sound and the line breaks are wrong; fix it with',
                   '   ./install.sh --pdf and rebuild with --force.', '', '1 book(s) built, 0 unchanged',
                   'Serve everything with:  ./serve.sh'];

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
try {
  for (const [name, lines, code] of [['no LaTeX', NO_LATEX, 1], ['no hyphenation patterns', NO_HYPHEN, 0]]) {
    const done = await jobLog(lines, code);
    const page = await browser.newPage();
    const toasts = [];
    let polls = 0;
    await page.route('**/*', async route => {
      const url = new URL(route.request().url()), p = url.pathname;
      if (url.hostname !== 'parseh.test') return route.abort();
      if (p === '/books/') return route.fulfill({contentType: 'text/html', body:
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><script src="/lib/parseh.js"></script></head><body></body></html>'});
      if (p === '/books/german/tale/__build') return route.fulfill({json: {ok: true, state: 'running', what: 'pdf', log: []}});
      if (p === '/books/german/tale/__build/status')
        return route.fulfill({json: ++polls < 2 ? {ok: true, state: 'running', what: 'pdf', log: done.log.slice(0, -1)} : done});
      if (p.startsWith('/lib/')) return route.fulfill({path: root + p});
      return route.fulfill({status: 404, body: ''});
    });
    await page.goto('http://parseh.test/books/');
    await page.waitForFunction(() => window.Parseh && window.Parseh.buildBook);
    await page.evaluate(() => new Promise(res => {
      window.Parseh.buildBook('/books/german/tale/__build', 'the PDF', {
        say: (m, err) => { window.__said = (window.__said || []).concat([[m, !!err]]); },
        done: () => res(), failed: () => res()});
    }));
    const said = await page.evaluate(() => window.__said);
    console.log(`\n${name}:`);
    said.forEach(s => console.log('   said' + (s[1] ? ' (as an error)' : '') + ': ' + s[0]));
    const all = said.map(s => s[0]).join('\n');
    for (const terminal of ['./serve.sh', './install.sh', 'NO LOG', 'NO HYPHENATION', '--force', 'Serve everything'])
      assert(!all.includes(terminal), `${name}: nothing the page says names ${JSON.stringify(terminal)}`);
    const last = said[said.length - 1];
    if (code) {
      assert(last[1] && /^the PDF: the build failed — the PDF was not made -- LaTeX could not run: LuaLaTeX is not on this computer/.test(last[0]) &&
             /Parseh cannot install LaTeX from its pages yet/.test(last[0]),
             `${name}: the failure says LaTeX did not run, and that it cannot be installed from the pages yet`);
    } else {
      assert(!last[1] && /^the PDF: built — no hyphenation patterns for German on this computer: the PDF is sound, but its lines are broken where an English word would break\. Parseh cannot install the patterns from its pages yet\.$/.test(last[0]),
             `${name}: "built", and the warning in plain words beside it`);
    }
    await page.close();
  }
  console.log(`\nbuild_endings: ${passed} checks passed`);
} finally {
  await browser.close();
}
