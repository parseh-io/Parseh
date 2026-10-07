// SPDX-License-Identifier: GPL-3.0-or-later
// Offline browser checks. It makes its own fixtures (tests/lm_likelihood_fixture.py).
// PLAYWRIGHT_CORE=/path/to/playwright-core/index.mjs node tests/lm_likelihood.mjs
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_CORE || 'npm:playwright-core@1.52.0');
const browser = await chromium.launch({executablePath: process.env.CHROME_BIN || '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox']});
// the fixtures are made here, every run: a suite that waits for whoever ran the script last fails on a machine whose /tmp was
// cleared since (release step 1 runs every suite and no script before it)
const made = await new Deno.Command(Deno.env.get('PARSEH_PYTHON') || 'python3', {args: ['tests/lm_likelihood_fixture.py'], stdout: 'piped', stderr: 'piped'}).output();
if (!made.success) throw new Error('tests/lm_likelihood_fixture.py failed: ' + new TextDecoder().decode(made.stderr).slice(-600));
const fixture = JSON.parse(await readFile('/tmp/parseh-likelihood-browser-fixture.json', 'utf8'));
let checks = 0;
function ok(condition, message) { assert.ok(condition, message); checks++; }
try {
  const page = await browser.newPage();
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.setContent('<textarea id="transcript">existing draft</textarea><div id="review"></div>');
  await page.addScriptTag({path: 'youtube/lib/asrreview.js'});
  await page.evaluate(data => {
    window.calls = []; window.view = data;
    window.connection = {configured: false, likelihood: {configured: true, available: true, revision: 'saved-revision', model: 'tiny-installed'}};
    window.review = ParsehAsrReview.mount(document.getElementById('review'), {
      choose: (...args) => calls.push(['choose', ...args]), retry: (...args) => calls.push(['retry', ...args]),
      cancel: () => calls.push(['cancel']),
      pause: () => Promise.reject(new Error('The review could not be stopped.')),
      use: (decisions, edits) => { calls.push(['use', decisions, edits]); document.getElementById('transcript').value = 'explicit application'; }
    });
    review.show(data, 'choice', connection);
  }, fixture);
  for(const id of ['stt_review_llm','stt_review_full','stt_review_workspace','stt_review_likelihood'])
    ok((await page.locator('#'+id).textContent()).includes('experimental'),'correction method is visibly experimental: '+id);
  ok(await page.locator('#stt_review_whisper').count()===0,'review needs no separate Whisper-only choice');
  ok((await page.locator('#stt_external_task option').allTextContents()).every(text=>text.includes('experimental')),'external correction options are marked experimental');
  ok(await page.locator('#stt_review_likelihood').isEnabled(), 'numeric method works without a chat connection');
  await page.locator('#stt_review_likelihood').click();
  ok((await page.evaluate(() => calls[0]))[1] === 'likelihood', 'explicit numeric method choice');
  await page.evaluate(() => review.show(view, 'review', connection));
  await page.locator('[data-review-word="s0w1"]').focus();
  ok(await page.locator('#stt_review_details details').count() > 0, 'technical data stays behind disclosures');
  await page.locator('#stt_review_details details').filter({has:page.getByText('Technical details',{exact:true})}).first().locator('summary').click();
  ok((await page.locator('#stt_review_details').textContent()).includes('LM beam search'), 'extra-candidate origins are displayed');
  ok((await page.locator('#stt_review_details').textContent()).includes('original Whisper'), 'original is displayed alongside alternatives');
  await page.evaluate(() => { view.review.result.suggestions[0].likelihood.hardware = {backend:'cuda',gpu_device:0,offloaded_layers:2,context_tokens:256,device:{description:'Local test GPU'}}; review.show(view, 'review', connection); });
  await page.locator('[data-review-word="s0w1"]').focus();
  ok((await page.locator('#stt_review_details').textContent()).includes('2 layers offloaded'), 'actual GPU offload diagnostics are displayed');
  await page.locator('#stt_review_details').getByRole('button', {name:'Accept this alternative', exact:true}).nth(1).click();
  ok(await page.locator('#transcript').inputValue() === 'existing draft', 'accept modifies only pending draft');
  await page.locator('#stt_use').click();
  ok(await page.locator('#transcript').inputValue() === 'explicit application', 'explicit Use invokes application');
  await page.evaluate(() => { document.getElementById('transcript').value = 'kept'; view.review.result.suggestions[0].candidates[0].applicable = false; view.review.result.suggestions[0].candidates[0].error = 'timeout'; view.review.result.suggestions[0].likelihood.coverage.state = 'partial'; review.show(view, 'review', connection); });
  await page.locator('[data-review-word="s0w1"]').click();
  ok(await page.locator('#stt_review_details').getByRole('button', {name:'Accept this alternative', exact:true}).first().isDisabled(), 'unscored candidate cannot be applied');
  await page.locator('#stt_review_cancel').click();
  ok(await page.locator('#transcript').inputValue() === 'kept', 'cancel leaves transcript untouched');
  await page.evaluate(() => review.show(view, 'correcting', connection));
  ok(await page.locator('#stt_use').isDisabled(), 'cannot apply in-flight results');
  ok(await page.locator('#stt_review_likelihood').isDisabled(), 'cannot start overlapping likelihood run');
  await page.evaluate(() => { view.review.result.suggestions[0].candidates[0].text = '<img src=x onerror="window.injected=true">'; review.show(view, 'review', connection); });
  await page.locator('[data-review-word="s0w1"]').click();
  ok(await page.locator('#stt_review_details img').count() === 0, 'candidate text is escaped');
  await page.evaluate(() => { view.review.evidence.language = 'fa'; document.documentElement.dir = 'rtl'; review.show(view, 'review', connection); });
  ok(await page.locator('[data-review-word="s0w1"]').count() === 1, 'RTL keeps stable IDs and accessible word controls');
  ok(errors.length === 0, 'review has no JavaScript errors');

  await page.evaluate(() => {view.review.result.suggestions[0].candidates[0].applicable=true;view.review.result.suggestions[0].likelihood.coverage.state='complete';review.show(view,'review',connection);});
  await page.locator('#stt_select_best').click();
  ok(Object.keys(await page.evaluate(() => review.snapshot().decisions)).length===1,'bulk best updates pending choices');
  await page.locator('[data-review-word="s0w1"]').click();
  await page.locator('#stt_lock_word').click();
  ok((await page.evaluate(() => review.snapshot().locked_word_ids)).includes('s0w1'),'word lock is persisted in snapshot');
  ok(await page.locator('#stt_likelihood_word').isDisabled(),'locked word cannot start another method');
  await page.locator('#stt_select_best').click();
  ok(Object.keys(await page.evaluate(() => review.snapshot().decisions)).length===0,'bulk selection preserves locked manual choice');
  await page.locator('#stt_lock_word').click();
  ok(await page.locator('#stt_likelihood_word').isEnabled(),'unlocked word can be reviewed alone');
  const beforeSingle=await page.evaluate(()=>calls.length);
  await page.locator('#stt_likelihood_word').click();
  await page.waitForFunction(n=>calls.length>n,beforeSingle);
  ok(JSON.stringify((await page.evaluate(()=>calls.at(-1)))[4])===JSON.stringify(['s0w1']),'single-word call contains only that stable target');
  await page.evaluate(()=>{view.review.result.suggestions[0].likelihood.tied_best=['x!','y!'];review.show(view,'review',connection);});
  await page.locator('#stt_select_best').click();
  ok(Object.keys(await page.evaluate(()=>review.snapshot().decisions)).length===0,'bulk choice leaves tied comparisons for manual review');
  await page.evaluate(()=>{view.review.result.suggestions[0].likelihood.tied_best=['y!'];view.review.result.latest_word_ids=[];review.show(view,'review',connection);});
  await page.locator('#stt_select_best').click();
  ok(Object.keys(await page.evaluate(()=>review.snapshot().decisions)).length===0,'bulk choice ignores results outside the last run');
  await page.evaluate(()=>{view.review.result.latest_word_ids=['s0w1'];review.show(view,'review',connection);});
  await page.locator('#stt_select_section').click();
  await page.locator('[data-review-word="s0w0"]').click();
  ok((await page.evaluate(()=>review.snapshot().selection)).length===0,'unfinished section selection is not saved as an invalid range');
  await page.locator('[data-review-word="s0w1"]').click();
  ok((await page.evaluate(() => review.snapshot().selection)).length===2,'section uses stable word endpoints');
  ok(await page.locator('#stt_review_scope').inputValue()==='selection','section becomes active review scope');
  ok(await page.locator('#stt_phonetic_filter').isChecked(),'similar-sound filter defaults on');
  const previousCallCount=await page.evaluate(() => calls.length);
  await page.locator('#stt_review_likelihood').click();
  await page.waitForFunction(n=>calls.length>n,previousCallCount);
  ok((await page.evaluate(() => calls.at(-1)))[4].length===1,'selected scope targets suspects only');
  ok((await page.locator('[data-review-disclosure="options"]').textContent()).includes('LM likelihood: tiny-installed'),'model preferences includes numerical model');

  await page.evaluate(() => review.show(view,'correcting',connection));
  await page.locator('#stt_pause').click();
  await page.waitForFunction(()=>document.getElementById('review').textContent.includes('The review could not be stopped.'));
  ok(await page.locator('[data-review-word="s0w1"]').count()===1,'failed pause keeps the review open');
  ok(await page.locator('#transcript').inputValue()==='kept','failed pause leaves the transcript box unchanged');
  ok(errors.length===0,'pause rejection is handled without a script error');

  const settings = await browser.newPage();
  const defaults = JSON.parse(await readFile('/tmp/parseh-likelihood-browser-defaults.json', 'utf8'));
  await settings.route('http://parseh.test/**', async route => {
    if (!route.request().url().includes('/settings/api/')) return route.fulfill({status:200, contentType:'text/html', body:route.request().isNavigationRequest() ? await readFile('/tmp/parseh-likelihood-settings-host.html','utf8') : ''});
    const action = route.request().url().split('/').pop();
    if(action==='save')Object.assign(defaults,route.request().postDataJSON());
    const data = action === 'models' ? {models:[{id:'installed-id',model_id:'installed Qwen / Q4_1',architecture:'qwen3',bytes:1000}],errors:[]} : {configured:true,available:true,model:'installed Qwen / Q4_1',runtime:{available:true,gpu_devices:[{backend:'cuda',index:0,description:'Local test GPU',free_bytes:1073741824,total_bytes:4294967296}]},settings:defaults,install:{state:'not-requested'},loaded_workers:0};
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,...data})});
  });
  await settings.goto('http://parseh.test/settings/lm-likelihood/');
  await settings.addScriptTag({path:'lib/lmlikelihoodsettings.js'});
  await settings.waitForFunction(() => document.getElementById('lm_devices').textContent.includes('CUDA device 0'));
  ok((await settings.locator('#lm_devices').textContent()).includes('Local test GPU'), 'runtime-discovered device and memory are displayed');
  ok(await settings.locator('#lm_gpu_device').inputValue() === '0', 'saved GPU selection is populated');
  ok(await settings.locator('#lm_probability_preset').inputValue()==='0.1','saved suggested cutoff is selected');
  ok((await settings.locator('#lm_probability_note').textContent()).includes('preliminary experiments'),'cutoff recommendation names its preliminary evidence');
  await settings.selectOption('#lm_probability_preset','0');
  let cutoffSave=settings.waitForRequest(req=>req.url().endsWith('/save'));
  await settings.getByRole('button',{name:'Save review options',exact:true}).click();
  ok((await cutoffSave).postDataJSON().minimum_candidate_probability===0,'no-cutoff choice saves zero instead of forcing 0.1');
  await settings.reload();await settings.addScriptTag({path:'lib/lmlikelihoodsettings.js'});
  await settings.waitForFunction(()=>document.getElementById('lm_probability_preset').value==='0');
  ok(await settings.locator('#lm_minimum_candidate_probability').inputValue()==='0','no-cutoff choice survives reload');
  await settings.selectOption('#lm_probability_preset','custom');
  await settings.fill('#lm_minimum_candidate_probability','0.025');
  cutoffSave=settings.waitForRequest(req=>req.url().endsWith('/save'));
  await settings.getByRole('button',{name:'Save review options',exact:true}).click();
  ok((await cutoffSave).postDataJSON().minimum_candidate_probability===0.025,'custom cutoff is sent as the selected number');
  await settings.waitForFunction(()=>document.getElementById('lm_probability_preset').value==='custom' && document.getElementById('lm_minimum_candidate_probability').value==='0.025');
  ok(await settings.locator('#lm_minimum_candidate_probability').isVisible(),'custom cutoff remains editable after save');
  await settings.selectOption('#lm_probability_preset','0.1');
  cutoffSave=settings.waitForRequest(req=>req.url().endsWith('/save'));
  await settings.getByRole('button',{name:'Save review options',exact:true}).click();
  ok((await cutoffSave).postDataJSON().minimum_candidate_probability===0.1,'suggested cutoff can be explicitly selected again');
  await settings.locator('#lm_refresh').click();
  await settings.waitForFunction(() => document.getElementById('lm_models').value === 'installed-id');
  ok((await settings.locator('#lm_models').textContent()).includes('installed Qwen / Q4_1'), 'installed model selector is populated');
  const saved = settings.waitForRequest(req => req.url().endsWith('/select'));
  await settings.locator('#lm_select').click();
  ok(JSON.stringify((await saved).postDataJSON()) === JSON.stringify({id:'installed-id'}), 'selection sends inventory ID only');
  await settings.setContent(await readFile('/tmp/parseh-likelihood-settings-remote.html','utf8'));
  ok(await settings.locator('#lm_path').isDisabled(), 'remote browser cannot set arbitrary local path');
  ok(await settings.locator('#lm_gpu_device').isDisabled(), 'remote browser cannot alter worker hardware');
  ok(await settings.locator('#lm_models').isEnabled(), 'remote browser can select discovered models');
  ok(await settings.locator('#lm_probability_preset').isDisabled(),'remote browser follows the existing host-only worker settings rule');
  console.log(`${checks} browser checks passed`);
} finally { await browser.close(); }
