// SPDX-License-Identifier: GPL-3.0-or-later
// Local browser/server integration. No model, GPU, endpoint or network service.
import {readFile,writeFile,mkdir,mkdtemp,symlink,rm,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {spawn} from 'node:child_process';
import {createServer} from 'node:net';
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_CORE || 'npm:playwright-core@1.52.0');
const root=resolve('.'), temp=await mkdtemp(join(tmpdir(),'parseh-pending-browser-'));
const tree=join(temp,'tree'), fake=join(temp,'fake'), install=join(tree,'root'), videos=join(install,'youtube/videos');
const python=process.env.PARSEH_PYTHON || 'python3';
let server,browser,checks=0,logs='';
const ok=(condition,message)=>{assert.ok(condition,message);checks++;};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function port(){const socket=createServer();await new Promise(r=>socket.listen(0,'127.0.0.1',r));const p=socket.address().port;await new Promise(r=>socket.close(r));return p;}
const number=await port(), base='http://127.0.0.1:'+number;
for(const folder of [videos,join(tree,'config'),join(tree,'library'),join(tree,'tray'),join(tree,'exercises'),join(tree,'anki'),join(tree,'nodict'),join(tree,'nocorpus'),join(tree,'nomt'),fake])await mkdir(folder,{recursive:true});
await symlink(join(root,'lib'),join(install,'lib'));await symlink(join(root,'youtube/lib'),join(install,'youtube/lib'));
await writeFile(join(fake,'state.json'),JSON.stringify({runtime:true,models:['large-v3-turbo','large-v3'],cuda:{ready:false,name:'',why:''}}));
await writeFile(join(fake,'fake.json'),JSON.stringify({segments:[[0,2,' سلام دنیا'],[2.5,3,' خداحافظ']]}));
const old=await readFile('tests/add_stt.mjs','utf8');
let boot=old.match(/const BOOT = String.raw`([\s\S]*?)`;/)[1];
boot=boot.replace("import prefs, network, offline, llmconfig", "import prefs, network, offline, llmconfig, lmlikelihoodconfig\nlmlikelihoodconfig.CONFIG = tmp / 'config/lm-likelihood.json'\nlmlikelihoodconfig.runtime_status = lambda config: {'available': False, 'say': 'No model runtime in this test.'}");
async function start(){
 logs='';server=spawn(python,['-c',boot,tree,String(number)],{cwd:root,stdio:['ignore','pipe','pipe']});
 server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
 for(let i=0;i<120;i++){try{const r=await fetch(base+'/lookup/api/speech',{method:'POST',body:'{}'});if(r.ok)return;}catch{}await sleep(250);}
 throw Error('Temporary server did not start: '+logs);
}
async function stop(){if(!server || server.exitCode!==null)return;const done=new Promise(r=>server.once('exit',r));server.kill('SIGTERM');await done;}
async function newPage(url){const context=await browser.newContext();await context.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/,route=>route.abort());const page=await context.newPage();page.failures=[];page.on('pageerror',e=>page.failures.push(e.message));page.on('dialog',d=>d.accept());await page.goto(base+url);await page.waitForSelector('#transcript',{state:'attached'});return {page,context};}
async function phase(page,value){await page.waitForFunction(value=>document.getElementById('stt').dataset.state===value,value,{timeout:30000});}
try{
 const film=join(temp,'film.mp4');
 const audio=spawn('ffmpeg',['-y','-loglevel','error','-f','lavfi','-i','sine=frequency=440:duration=3','-ar','16000','-ac','1','-c:a','pcm_s16le','-f','wav',film]);
 assert.equal(await new Promise(r=>audio.on('exit',r)),0);
 await start();browser=await chromium.launch({executablePath:process.env.CHROME_BIN || '/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 let {page,context}=await newPage('/youtube/add/?src=film&by=empty');
 // A result is drawn at once and drawn AGAIN when the connection's status arrives a moment later (youtube/lib/addstt.js deliver): a word's
 // editor opened and typed in before that second drawing is drawn afresh under the typing.  Typing is kept now, but a click that lands in
 // the middle of the redraw is not delivered, so what a test types waits for the review to have settled.
 await page.selectOption('#lang','fa');await page.fill('#path',film);const status=page.waitForResponse(r=>r.url().includes('/settings/api/llm/status'));await page.click('#stt_go');await phase(page,'review');await status;await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>setTimeout(r,0)))));
 ok(await page.inputValue('#transcript')==='','Whisper never inserts a transcript automatically');
 await page.locator('[data-review-word="s0w0"]').click();await page.fill('#stt_manual_word','درود');
 await page.getByRole('button',{name:'Save word in draft',exact:true}).click();await page.click('#stt_lock_word');
 await page.click('#stt_select_section');await page.locator('[data-review-word="s0w0"]').click();await page.locator('[data-review-word="s0w1"]').click();
 await page.click('#stt_pause');await phase(page,'idle');
 const records=await readdir(join(videos,'.pending-transcriptions'));ok(records.length===1,'paused review is stored on disk');
 const token=records[0].slice(0,-5),saved=JSON.parse(await readFile(join(videos,'.pending-transcriptions',records[0]),'utf8'));
 ok(saved.job.review_draft.manual_edits.s0w0==='درود','manual choice is saved');
 ok(saved.job.review_draft.locked_word_ids.includes('s0w0'),'word lock is saved');
 ok(saved.job.review_draft.selection.length===2,'selection endpoints are saved');
 ok((await fetch(base+'/youtube/videos/.pending-transcriptions/'+records[0])).status>=400,'private draft file is not available through static HTTP');
 ok(await page.inputValue('#transcript')==='','pause leaves transcript box unchanged');
 ok(page.failures.length===0,'initial review has no script errors');await context.close();
 await stop();await start();
 const shelf=await fetch(base+'/youtube/').then(r=>r.text());ok(shelf.includes('Continue pending transcription') && shelf.includes(token),'Videos offers the saved review');
 ({page,context}=await newPage('/youtube/add/?pending='+token));await phase(page,'review');
 ok(await page.inputValue('#path')===film,'source restored after server restart');
 ok(await page.inputValue('#lang')==='fa','language restored');
 ok(await page.locator('[data-review-word="s0w0"]').textContent()==='درود','manual replacement restored in pending draft');
 ok(await page.locator('[data-review-word="s0w0"]').getAttribute('aria-pressed')==='true','lock restored');
 ok(await page.inputValue('#transcript')==='','resuming still requires explicit Use');
 if(process.env.PARSEH_REVIEW_SCREENSHOT){await page.locator('[data-review-word="s0w0"]').click();await page.screenshot({path:process.env.PARSEH_REVIEW_SCREENSHOT,fullPage:true});}
 await page.click('#stt_use');await phase(page,'idle');
 ok((await page.inputValue('#transcript')).includes('درود دنیا'),'explicit Use applies the exact edited span');
 ok((await readdir(join(videos,'.pending-transcriptions'))).length===0,'finished review returns to ordinary storage');
 ok(page.failures.length===0,'resumed review has no script errors');
 const about=await fetch(base+'/settings/about/').then(r=>r.text());ok(about.includes('serve.sh location') && about.includes('serve.bat'),'About includes cross-platform launch paths');
 console.log(`${checks} pending browser integration checks passed`);
 await context.close();
}finally{if(browser)await browser.close();await stop();await rm(temp,{recursive:true,force:true});}
