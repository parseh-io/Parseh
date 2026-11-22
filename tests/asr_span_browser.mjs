// SPDX-License-Identifier: GPL-3.0-or-later
// Focused review interactions: no server, recognizer, models or endpoint.
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
const {chromium} = await import(process.env.PLAYWRIGHT_CORE || 'npm:playwright-core@1.52.0');
const browser = await chromium.launch({executablePath:process.env.CHROME_BIN || '/usr/bin/google-chrome',
  headless:true,args:['--no-sandbox']});
let checks = 0;
function ok(value, message) { assert.ok(value, message); checks++; }
try {
  const page = await browser.newPage();
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.setContent('<main><textarea id="transcript">untouched</textarea><section id="review"></section></main>');
  await page.addScriptTag({content:await readFile(resolve('youtube/lib/asrreview.js'),'utf8')});
  async function setup(suggestion=false) {
    await page.evaluate(suggestion => {
      window.applied = null;
      const text = '0:00\n🙂 A note book arrived.\n0:05\nNext caption.\n';
      const segments = ['🙂 A note book arrived.', 'Next caption.'].map((caption, s) => {
        let at = text.indexOf(caption);
        return {segment_id:'s'+s,start:s*5,end:s*5+4,text:caption,words:caption.split(' ').map((surface,i) => {
          const start = text.indexOf(surface, at); at = start+surface.length;
          return {segment_id:'s'+s,word_id:'s'+s+'w'+i,text:surface,start:s*5+i*.3,end:s*5+i*.3+.2,
            asr_confidence:surface==='note' ? .2 : .95,low_asr_score:surface==='note',dictionary_miss:false,
            alternatives_available:false,asr_alternatives:[],reviewable:true,
            span_start:Array.from(text.slice(0,start)).length,span_end:Array.from(text.slice(0,at)).length};
        })};
      });
      const word = segments[0].words[2];
      const proposals = suggestion ? [{...word,original:'note',word_ids:[word.word_id],
        candidates:[{text:'noted',confidence:null,reason:''}]}] : [];
      const root = document.querySelector('#review');
      if (window.spanReview) window.spanReview.clear();
      window.spanReview = ParsehAsrReview.mount(root, {cancel:()=>{},choose:(mode,skill,task,ids)=>{window.reviewChosen=ids;},
        external:(action,values)=>{window.reviewChosen=values.word_ids;return Promise.reject(new Error('not prepared in this test'));},
        use:(decisions,manual)=>{window.applied={decisions,manual};},save:draft=>{window.saved=draft;return Promise.resolve();}});
      window.spanReview.show({text,model:'large-v3-turbo',review:{evidence:{source_sha256:suggestion?'source-2':'source',
        language:'en',low_score_threshold:.5,segments},result:{task:'workspace',suggestions:proposals}}},'review',{likelihood:null});
    }, suggestion);
  }
  await setup();
  await page.locator('[data-review-word="s0w2"]').click();
  await page.click('#stt_manual_next');
  ok(await page.locator('#stt_manual_span').textContent()==='note book','neighbor range is independent of suggestions');
  await page.fill('#stt_manual_word','notebook');
  await page.locator('#stt_manual_word').press('Enter');
  ok((await page.locator('#review pre').textContent()).includes('🙂 A notebook arrived.'),'merge changes only exact source span');
  ok(await page.locator('[data-review-word="s0w3"]').isHidden(),'joined second source word is hidden in pending draft');
  ok(await page.inputValue('#transcript')==='untouched' && await page.evaluate(()=>window.applied===null),'save never inserts transcript');
  await page.click('#stt_use');
  assert.deepEqual(await page.evaluate(()=>window.applied.manual),{s0w2:{text:'notebook',word_ids:['s0w2','s0w3']}});checks++;
  await page.click('#stt_manual_reset');await page.click('#stt_lock_word');
  // the whole-text method takes every unlocked word: prepared for a chatbot, by copy and paste
  await page.evaluate(()=>{document.getElementById('stt_external').open=true;});await page.selectOption('#stt_external_task','full');
  await page.click('#stt_external_start');await page.waitForFunction(()=>Array.isArray(window.reviewChosen));
  ok(await page.evaluate(()=>!window.reviewChosen.includes('s0w2') && !window.reviewChosen.includes('s0w3')),'locking after resetting editor scope protects both saved merge members');
  ok(await page.evaluate(()=>window.saved.locked_word_ids.includes('s0w2') && window.saved.locked_word_ids.includes('s0w3')),'multiword lock persists both stable source IDs');
  await page.click('#stt_lock_word');await page.click('#stt_manual_next');
  await page.getByRole('button',{name:'Restore Whisper words',exact:true}).click();
  ok((await page.locator('#review pre').textContent()).includes('note book') && await page.locator('[data-review-word="s0w3"]').isVisible(),'restore returns both original source words');
  await page.locator('[data-review-word="s0w3"]').click();await page.click('#stt_lock_word');
  await page.locator('[data-review-word="s0w2"]').click();
  ok(await page.locator('#stt_manual_next').isDisabled(),'locked neighbor cannot be included');
  await page.locator('[data-review-word="s0w4"]').click();
  ok(await page.locator('#stt_manual_next').isDisabled(),'range stops at caption boundary');
  await setup(true);
  await page.locator('[data-review-word="s0w2"]').click();await page.click('#stt_manual_next');
  await page.getByRole('button',{name:'Accept this alternative',exact:true}).click();
  const preview = await page.locator('#review pre').textContent();
  ok(preview.includes('noted book') && !preview.includes('noted arrived'),'model proposal keeps its own span after manual range expansion');
  await page.locator('[data-review-word="s0w3"]').click();await page.click('#stt_manual_previous');
  await page.fill('#stt_manual_word','notebook');await page.locator('#stt_manual_word').press('Enter');await page.click('#stt_use');
  assert.deepEqual(await page.evaluate(()=>window.applied),{decisions:{},manual:{s0w2:{text:'notebook',word_ids:['s0w2','s0w3']}}});checks++;
  ok((await page.locator('#review pre').textContent()).includes('0:05\nNext caption.'),'neighbor merge preserves subsequent caption text and clock');
  ok(errors.length===0,'no browser errors');
  console.log(`${checks} adjacent-span browser checks passed`);
} finally {await browser.close();}
