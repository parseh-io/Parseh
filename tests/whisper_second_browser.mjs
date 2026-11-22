// SPDX-License-Identifier: GPL-3.0-or-later
// Real browser + temporary server + fake Whisper. No model or external service.
import {readFile,writeFile,mkdir,mkdtemp,symlink,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {spawn} from 'node:child_process';
import {createServer} from 'node:net';
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_CORE || 'npm:playwright-core@1.52.0');
const root=resolve('.'), temp=await mkdtemp(join(tmpdir(),'parseh-whisper-second-'));
const tree=join(temp,'tree'), fake=join(temp,'fake'), install=join(tree,'root');
const python=process.env.PARSEH_PYTHON || 'python3';
let server,browser,checks=0,logs='';
const ok=(condition,message)=>{assert.ok(condition,message);checks++;};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const socket=createServer();await new Promise(r=>socket.listen(0,'127.0.0.1',r));const port=socket.address().port;await new Promise(r=>socket.close(r));
const base='http://127.0.0.1:'+port;
for(const folder of ['config','library','tray','exercises','anki','nodict','nocorpus','nomt','root/youtube/videos'])await mkdir(join(tree,folder),{recursive:true});
await mkdir(fake);await symlink(join(root,'lib'),join(install,'lib'));await symlink(join(root,'youtube/lib'),join(install,'youtube/lib'));
await writeFile(join(fake,'state.json'),JSON.stringify({runtime:true,models:['large-v3-turbo','large-v3'],cuda:{ready:false,name:'',why:''}}));
await writeFile(join(fake,'fake.json'),JSON.stringify({segments:[[0,4,' loro anno detto strano']],word_evidence:{anno:{score:.2},strano:{score:.2}},second_pass:[
  {segments:[[0,4,' loro hanno detto strano']],delay:2},
  {segments:[[0,4,' loro anno detto strana']],delay:2}
]}));
let boot=(await readFile('tests/add_stt.mjs','utf8')).match(/const BOOT = String.raw`([\s\S]*?)`;/)[1];
boot=boot.replace('import prefs, network, offline\n', "import prefs, network, offline, lmlikelihoodconfig\nlmlikelihoodconfig.CONFIG = tmp / 'config/lm-likelihood.json'\nlmlikelihoodconfig.runtime_status = lambda config: {'available': False, 'say': 'No model runtime in this test.'}\n");
async function phase(page,value){await page.waitForFunction(value=>document.getElementById('stt').dataset.state===value,value,{timeout:30000});}
try {
 const film=join(temp,'film.mp4');
 const audio=spawn(python,['-c',"import sys;sys.path.insert(0,'tests');import stt_fakes;stt_fakes.write_wav(sys.argv[1],4)",film],{cwd:root});
 assert.equal(await new Promise(r=>audio.on('exit',r)),0);
 server=spawn(python,['-c',boot,tree,String(port)],{cwd:root,stdio:['ignore','pipe','pipe']});
 server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
 for(let i=0;i<120;i++){try{const r=await fetch(base+'/lookup/api/speech',{method:'POST',body:'{}'});if(r.ok)break;}catch{}if(i===119)throw Error('Temporary server did not start: '+logs);await sleep(250);}
 browser=await chromium.launch({executablePath:process.env.CHROME_BIN || '/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 const context=await browser.newContext();await context.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/,route=>route.abort());
 const page=await context.newPage(), errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(base+'/youtube/add/?src=film&by=empty');await page.waitForSelector('#transcript',{state:'attached'});
 await page.selectOption('#lang','it');await page.fill('#path',film);await page.fill('#transcript','Existing manual transcript');await page.click('#stt_go');
 await page.waitForSelector('#stt_second_pass',{state:'visible'});
 ok(await page.locator('#stt_second_pass_label').textContent()==='Whisper second pass · 0 / 2 suspect words processed','distinct second-pass label counts suspect words');
 ok(await page.locator('#stt_bar').isHidden(),'first-pass bar gives way to distinct second-pass bar');
 ok(await page.locator('#stt_cancel').isVisible(),'cancellation remains available during second pass');
 ok(await page.inputValue('#transcript')==='Existing manual transcript','second pass leaves the transcript box untouched');
 await page.waitForFunction(()=>document.getElementById('stt_second_pass_bar').getAttribute('aria-valuenow')==='1');
 ok(await page.locator('#stt_second_pass_bar').getAttribute('aria-valuemax')==='2','accessible progress uses completed / total targets');
 await phase(page,'review');ok(await page.locator('#stt_second_pass').isHidden(),'second-pass bar ends before the draft opens');
 ok(await page.locator('#stt_review_whisper').count()===0,'no redundant Whisper-only gate');
 ok(await page.locator('#stt_use').isEnabled(),'draft can be used without choosing a correction tool');
 await page.locator('[data-review-word="s0w1"]').click();
 ok((await page.locator('#stt_review').textContent()).includes('hanno'),'new candidate is visible in Whisper-only review');
 ok(await page.inputValue('#transcript')==='Existing manual transcript','review still requires explicit final use');
 ok(errors.length===0,'no browser script errors');
 // A second run cancels in the native crop; late responses cannot open review.
 await page.click('#stt_review_cancel');await phase(page,'idle');
 await page.click('#stt_go');await page.waitForSelector('#stt_second_pass',{state:'visible'});await page.click('#stt_cancel');await phase(page,'idle');await sleep(2500);
 ok(await page.inputValue('#transcript')==='Existing manual transcript','cancelled work never changes transcript text');
 ok(await page.locator('#stt_second_pass').isHidden(),'cancel removes second-pass progress');
 const settings=await context.newPage();await settings.goto(base+'/settings/speech/');
 await settings.locator('#sp_second_pass').uncheck();
 await settings.waitForFunction(()=>document.getElementById('sp_preferences_status').textContent.startsWith('Saved.'));
 await settings.reload();ok(!(await settings.locator('#sp_second_pass').isChecked()),'optional automatic second pass persists in Settings');
 await page.click('#stt_go');await phase(page,'review');
 ok(await page.locator('#stt_review_second_pass').isEnabled(),'second pass is available as a later tool when skipped');
 await page.locator('[data-review-word="s0w0"]').click();await page.fill('#stt_manual_word','Loro');
 await page.getByRole('button',{name:'Save word in draft',exact:true}).click();await page.click('#stt_lock_word');
 await page.locator('[data-review-word="s0w1"]').click();await page.click('#stt_whisper_word');
 await page.waitForSelector('#stt_second_pass',{state:'visible'});
 ok((await page.locator('#stt_second_pass_label').textContent()).includes('0 / 1'),'one-word second pass uses one-word progress');
 await phase(page,'review');await page.locator('[data-review-word="s0w1"]').click();
 ok((await page.locator('#stt_review_details').textContent()).includes('hanno'),'later word recheck shows its safely mapped candidate');
 ok(await page.locator('[data-review-word="s0w0"]').textContent()==='Loro','manual choices survive tool use');
 ok(await page.locator('[data-review-word="s0w0"]').getAttribute('aria-pressed')==='true','locks survive tool use');
 // A selected section limits targets, while preserving the original phrase context.
 await page.click('#stt_select_section');
 await page.locator('[data-review-word="s0w2"]').click();await page.locator('[data-review-word="s0w3"]').click();
 ok(await page.inputValue('#stt_review_scope')==='selection','section selection is shared by the tools');
 await page.click('#stt_review_second_pass');await page.waitForSelector('#stt_second_pass',{state:'visible'});
 ok((await page.locator('#stt_second_pass_label').textContent()).includes('0 / 1'),'section recheck processes only its remaining suspect');
 await phase(page,'review');await page.locator('[data-review-word="s0w1"]').click();
 ok((await page.locator('#stt_review_details').textContent()).includes('hanno'),'section recheck retains earlier candidates outside the selection');
 if(process.env.PARSEH_REVIEW_SCREENSHOT)await page.screenshot({path:process.env.PARSEH_REVIEW_SCREENSHOT,fullPage:false});
 await page.click('#stt_whisper_word');await page.waitForSelector('#stt_second_pass',{state:'visible'});
 await page.click('#stt_review_cancel');await phase(page,'review');
 ok(await page.locator('[data-review-word="s0w0"]').textContent()==='Loro','stopping a later recheck preserves the pending draft');
 ok(await page.inputValue('#transcript')==='Existing manual transcript','all tools still leave the existing box untouched');
 ok(errors.length===0,'tool-based review has no script errors');
 console.log(`${checks} Whisper second-pass browser checks passed`);
} finally {
 if(browser)await browser.close();
 if(server && server.exitCode===null){const done=new Promise(r=>server.once('exit',r));server.kill('SIGTERM');await done;}
 await rm(temp,{recursive:true,force:true});
}
