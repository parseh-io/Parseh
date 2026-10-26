// SPDX-License-Identifier: GPL-3.0-or-later
/* What the browser suites that touch a book's reader share about its gear (lib/gear-reader.js, a0.5.0): open
   the ⚙, find a row, flip a switch, choose from a menu, shut it again -- the way a person does, by a tap on a
   phone (a suite marks its touch pages with `page.touch`, as tests/mobile_pages.mjs does) and by a click with a
   mouse.  The reader's own controls are still on the page and a few of them still drawn; what the gear took
   off the page -- the passes' numbers, ⋯, hover ⏸, stop at a change, the definitions -- is reached only here.

   ON A PHONE THE SHEET IS TWO STAGES (a0.5.4): it opens on an index of the page's themes and a tap on one slides it
   to that theme alone, so a row can only be reached once its theme is on stage.  `gearOpen(page, group)` ENTERS the
   theme (a tap on its row of the index, ‹ first where another theme is up); `gearReach(page, rowId)` finds the
   row's theme from the DOM -- every row is built whichever theme is on stage -- and enters it; gearSwitch and
   gearSelect reach their row first.  On a popover (a computer) nothing is entered: the group is scrolled to. */
const press = async (page, l) => { if (page.touch) await l.tap(); else await l.click(); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

export const GEAR = '[data-parseh-gear]';
export const gearUp = page => page.evaluate(() => {
  const p = document.querySelector('.pg-panel');
  return !!p && !p.hidden;
});
const sheetUp = page => page.evaluate(() => {
  const p = document.querySelector('.pg-panel');
  return !!p && !p.hidden && p.classList.contains('pg-sheet');
});
// the stage the sheet is on: 'index', the id of a theme, or null (a popover, or shut)
export const gearStage = page => page.evaluate(() => {
  const p = document.querySelector('.pg-panel');
  return p && !p.hidden && p.classList.contains('pg-sheet') ? p.getAttribute('data-pg-stage') : null;
});
// the gear open (its button pressed unless it already is), and, where a group is named, that group in view: on the
// sheet its theme entered (and given the slide's 0.16 s to arrive), on a popover scrolled to
export async function gearOpen(page, group) {
  if (!(await gearUp(page))) {
    await page.waitForSelector(GEAR, {state: 'visible', timeout: 15000});
    await press(page, page.locator(GEAR).first());
    await page.waitForFunction(() => { const p = document.querySelector('.pg-panel'); return !!p && !p.hidden; });
    await sleep(120);
  }
  if (!group) return;
  if (await sheetUp(page)) {
    if ((await gearStage(page)) === group) return;
    if ((await gearStage(page)) !== 'index') {
      await press(page, page.locator('.pg-panel .pg-back'));
      await page.waitForFunction(() => document.querySelector('.pg-panel').getAttribute('data-pg-stage') === 'index');
      await sleep(240);
    }
    const row = page.locator(`.pg-panel .pg-irow[data-pg-index="${group}"]`);
    if (await row.count() && await row.isVisible()) {
      await press(page, row);
      await page.waitForFunction(g => document.querySelector('.pg-panel').getAttribute('data-pg-stage') === g, group);
      await sleep(240);
    }
    return;
  }
  await page.evaluate(g => {
    const b = document.querySelector('.pg-panel .pg-body'), e = document.querySelector('.pg-panel [data-pg-group="' + g + '"]');
    if (b && e && !e.hidden) b.scrollTop = Math.max(0, e.offsetTop - 8);
  }, group);
}
// the theme a row belongs to (every row is built, whichever theme is on stage), or null
export const gearGroupOf = (page, id) => page.evaluate(id => {
  const r = document.querySelector(`.pg-panel [data-pg-row="${id}"]`), g = r && r.closest('[data-pg-group]');
  return g ? g.getAttribute('data-pg-group') : null;
}, id);
// the gear open with the theme of THIS ROW on stage (nothing to do on a popover, which draws every row)
export async function gearReach(page, id) {
  await gearOpen(page);
  const g = await gearGroupOf(page, id);
  if (g) await gearOpen(page, g);
}
export async function gearClose(page) {
  if (!(await gearUp(page))) return;
  await press(page, page.locator('.pg-panel .pg-x'));
  await page.waitForFunction(() => document.querySelector('.pg-panel').hidden);
  await sleep(80);
}
export const gearRow = (page, id) => page.locator(`.pg-panel [data-pg-row="${id}"]`);
// whether a row is drawn right now (the gear is open): its row is not hidden and has a box
export const rowDrawn = (page, id) => page.evaluate(id => {
  const r = document.querySelector(`.pg-panel [data-pg-row="${id}"]`), g = r && r.closest('[data-pg-group]');
  if (!r || r.hidden || (g && g.hidden)) return false;
  // the sheet draws one theme at a time: a row of another theme is drawn where its theme is (not hidden by the page)
  const sheet = document.querySelector('.pg-panel').classList.contains('pg-sheet');
  return sheet ? true : r.getClientRects().length > 0;
}, id);
// a switch row's state, and the state it is flipped to: opened, flipped if it is not so already, shut
export async function gearSwitch(page, id, want) {
  await gearReach(page, id);
  const sw = gearRow(page, id).locator('button.pg-switch');
  await sw.scrollIntoViewIfNeeded();
  const on = (await sw.getAttribute('aria-checked')) === 'true';
  if (on !== !!want) { await press(page, sw); await sleep(150); }
  await gearClose(page);
}
// a menu row ("choice" drawn as a <select>): its value set by name or value, the page's handler run
export async function gearSelect(page, id, value) {
  await gearReach(page, id);
  const s = gearRow(page, id).locator('select.pg-select');
  await s.scrollIntoViewIfNeeded();
  await s.selectOption({label: String(value)}).catch(() => s.selectOption(String(value)));
  await sleep(150);
  await gearClose(page);
}
