// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome deno run --allow-all tests/words.mjs
// The word layer in the page: Parseh.readings().renderWords / wordControls
// and Parseh.wordstrip, over lib/wordline.js.  No book is built; the two
// registry records are the ones lib/languages.py hands a page.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const py = await new Deno.Command(Deno.env.get('PARSEH_PYTHON') || 'python3', {
  args:['-c','import json,sys; sys.path.insert(0,"lib"); import languages as L; '+
        'print(json.dumps({c: L.LANGS[c].as_json() for c in ("ja","zh")}))'],
  stdout:'piped', stderr:'piped'
}).output();
if (!py.success) throw Error(new TextDecoder().decode(py.stderr));
const LANGS = JSON.parse(new TextDecoder().decode(py.stdout));
const browser = await chromium.launch({executablePath:Deno.env.get('CHROME_BIN'),headless:true});
try {
const page = await browser.newPage();
const errors=[]; page.on('pageerror', e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
// parseh.js loads its own layers beside itself -- the activity list, the
// preferences this machine keeps, keeping on this phone, the ? that explains
// the buttons, the page zoom (a0.5.0), the jobs and sync layers (a0.7.0).  This page has no server behind it, so each is simply NOT
// FOUND rather than answered with the page, which a browser reads as a
// script full of syntax errors ("Unexpected token '<'").
const LAYERS = ['activity.js', 'prefs.js', 'keep.js', 'explain.js', 'pagezoom.js',
                'narrctl.js', 'wordtouch.js', 'mobileplayer.js', 'guidelink.js', 'jobs.js', 'syncpage.js'];
const isLayer = p => LAYERS.some(n => p.endsWith('/' + n));
await page.route(u => u.href.startsWith('http://parseh.test/') && isLayer(u.pathname),
                 route => route.fulfill({status:404, body:''}));
await page.route(u => u.href.startsWith('http://parseh.test/') && !isLayer(u.pathname),
                 route => route.fulfill({contentType:'text/html',
  body:'<!doctype html><html data-lang="ja"><body><div class="p1" id="text"></div><div class="p1" id="more"></div>'+
       '<div id="cloud"><div class="mkrow"></div></div><div id="cloud2"></div><div id="strips"></div></body></html>'}));
await page.goto('http://parseh.test/');
await page.addScriptTag({path: root+'/lib/parseh.js'});
await page.addStyleTag({path: root+'/lib/parseh.css'});
// a readings() made before wordline.js is on the page reads its word store on first use
await page.evaluate(()=>{
 localStorage.setItem('parseh_known_word:book:ja:early', JSON.stringify(['本(ほん)']));
 window.early=Parseh.readings({scope:'book:ja:early',kind:'book',selector:'.p1'});
});
await page.addScriptTag({path: root+'/lib/wordline.js'});

console.log(await page.evaluate(()=>{
 const assert=(v,m)=>{if(!v)throw Error(m)};
 const text=document.querySelector('#text');
 const r=Parseh.readings({scope:'book:ja:words',kind:'book',selector:'.p1'});
 const fa='山へ柴刈りに、', line='山(やま) へ 柴刈り(しばかり) に 、';
 assert(r.renderWords(text,fa,line)===true,'renderWords draws a good line');
 const wds=[...text.querySelectorAll('.wd')];
 assert(wds.length===5,'one .wd per word');
 assert(wds.map(w=>w.dataset.w).join('|')==='山(やま)|へ|柴刈り(しばかり)|に|、','data-w is the token: '+wds.map(w=>w.dataset.w));
 assert(wds.map(w=>w.dataset.k).join('')==='01234','data-k numbers the words');
 assert(text.querySelectorAll('ruby').length===2 && wds[2].querySelector('rt').textContent==='しばかり','a ruby where a word has a reading');
 assert(!wds[1].querySelector('ruby') && wds[1].textContent==='へ','a word without one is its text');
 assert(Parseh.baseText(text)===fa,'the text survives the words');
 r.renderWords(text,'私は 本を','私(わたし) は 本(ほん) を');
 const nodes=[...text.childNodes];
 assert(nodes.length===5 && nodes[2].nodeType===3 && nodes[2].data===' ','whitespace is a text node between words');
 assert(Parseh.baseText(text)==='私は 本を','whitespace kept');
 r.renderWords(text,'(注)','((注))');
 assert(text.querySelector('.wd').dataset.w==='((注))' && text.textContent==='(注)','a literal parenthesis: key is the escaped token');
 assert(r.renderWords(text,'𠮷野家','𠮷(よし) 野家(のや)') && text.querySelectorAll('.wd')[1].dataset.k==='1'
        && Parseh.baseText(text)==='𠮷野家','a character outside the basic plane is one character');
 assert(r.renderWords(text,'山へ','山(やま)')===false,'a line that does not rejoin the text falls back');
 assert(text.textContent==='山へ' && text.classList.contains('words-bad') && !text.querySelector('.wd'),'fallback: the plain text, marked');
 assert(r.renderWords(text,'山へ','山(やま')===false && text.textContent==='山へ','a line that does not parse falls back');
 assert(r.renderWords(text,'山へ','山(やま) へ') && !text.classList.contains('words-bad'),'a good line clears the mark');
 // 山(( parses, as 山( with no reading, and has no token to be known by
 assert(r.renderWords(text,'山(','山((')===false && text.textContent==='山(' && text.classList.contains('words-bad'),'a word with no token falls back');
 const W=window.ParsehWordline; delete window.ParsehWordline;
 try { assert(r.renderWords(text,'山へ','山(やま) へ')===false && text.textContent==='山へ','without lib/wordline.js the text is drawn plain'); }
 finally { window.ParsehWordline=W; }
 const e=document.createElement('div');
 assert(early.renderWords(e,'本','本(ほん)') && e.querySelector('ruby.reading-known'),'the word store is read after wordline.js arrives');
 return 'renderWords: ruby per word, whitespace, keys, fallback: passed';
}));

console.log(await page.evaluate(()=>{
 const assert=(v,m)=>{if(!v)throw Error(m)};
 const KW='parseh_known_word:book:ja:words', KK='parseh_known_kanji:book:ja:words';
 const text=document.querySelector('#text'), more=document.querySelector('#more'), cloud=document.querySelector('#cloud');
 const known=el=>[...el.querySelectorAll('.wd[data-w]')].filter(w=>w.querySelector('ruby.reading-known')).map(w=>w.dataset.w);
 const r=Parseh.readings({scope:'book:ja:words',kind:'book',selector:'.p1'});
 const line='本(ほん) を 読む(よむ) 本(ほん)';
 r.renderWords(text,'本を読む本',line);
 const row=r.wordControls(cloud,line);
 const btns=[...cloud.querySelectorAll('[data-known-word]')];
 assert(btns.map(b=>b.dataset.knownWord).join('|')==='本(ほん)|読む(よむ)','one button per distinct word with a reading');
 assert(btns[0].textContent==='本: I know this' && btns[0].getAttribute('aria-pressed')==='false','label before');
 assert(row.nextElementSibling===cloud.querySelector('.mkrow'),'inserted before .mkrow');
 assert(row.querySelector('small').textContent==='For this book. A word marked here hides its reading wherever it appears.','hint');
 btns[1].click();
 assert(JSON.parse(localStorage.getItem(KW)).includes('読む(よむ)'),'the word store is saved');
 assert(known(text).join('|')==='読む(よむ)','only the marked word hides');
 assert(getComputedStyle(text.querySelector('.reading-known rt')).visibility==='hidden','hidden by the stylesheet');
 assert(btns[1].textContent==='読む: show reading' && btns[1].getAttribute('aria-pressed')==='true','label after');
 btns[0].click();
 assert(known(text).filter(w=>w==='本(ほん)').length===2,'a repeated word is one word: every appearance hides');
 btns[0].click(); btns[1].click();
 assert(!known(text).length && JSON.parse(localStorage.getItem(KW)).length===0,'unmarking restores');
 // the same text with another reading is another word
 r.renderWords(more,'山山','山(やま) 山(さん)');
 r.wordControls(document.querySelector('#cloud2'),'山(やま) 山(さん)');
 assert(document.querySelectorAll('#cloud2 [data-known-word]').length===2,'山(やま) and 山(さん) are two buttons');
 document.querySelector('#cloud2 [data-known-word="山(やま)"]').click();
 assert(known(more).join('|')==='山(やま)','山(さん) keeps its reading');
 // a stray button nobody's row made is not this instance's to relabel
 const stray=document.createElement('button'); stray.dataset.knownWord='山(やま)'; stray.textContent='untouched';
 document.body.appendChild(stray); r.apply();
 assert(stray.textContent==='untouched','the button lookup stays inside its rows');
 // the kanji a person marked before words existed still count
 localStorage.setItem(KK,JSON.stringify(['川','見']));
 window.dispatchEvent(new StorageEvent('storage',{key:KK}));
 r.renderWords(more,'山川を見るテレビ山川','山(やま) 川(かわ) を 見る(みる) テレビ(てれび) 山川(やまかわ)');
 assert(known(more).join('|')==='山(やま)|川(かわ)|見る(みる)','kanji store OR word store; kana needs the word store; every kanji must be known: '+known(more));
 const r2=Parseh.readings({scope:'book:ja:words',kind:'book',selector:'.p1'});
 const legacy=r2.wordControls(document.querySelector('#cloud2'),'川(かわ)');
 const lb=legacy.querySelector('button');
 assert(lb.textContent==='川: show reading' && lb.getAttribute('aria-pressed')==='true','a kanji-known word shows as known');
 lb.click();
 assert(!JSON.parse(localStorage.getItem(KW)).includes('川(かわ)') && known(more).includes('川(かわ)'),'its button does not unmark a kanji nor write a redundant word');
 // the storage event covers the word store
 localStorage.setItem(KW,JSON.stringify(['テレビ(てれび)']));
 window.dispatchEvent(new StorageEvent('storage',{key:KW}));
 assert(known(more).includes('テレビ(てれび)') && !known(more).includes('山(やま)'),'another tab marking a word reaches this one');
 assert(document.querySelector('#cloud2 [data-known-word="山(やま)"]').textContent==='山: I know this','its buttons follow');
 // load: strings that parse as exactly one word -- not the kanji filter
 localStorage.setItem(KK,'[]');
 localStorage.setItem(KW,JSON.stringify(['本(ほん)',' 読む(よむ) ','x y','山(やま) 川(かわ)','山(やま',42,null,{}]));
 const fresh=Parseh.readings({scope:'book:ja:words',kind:'book',selector:'.p1'});
 fresh.renderWords(text,'本読む山川','本(ほん) 読む(よむ) 山(やま) 川(かわ)');
 assert(known(text).join('|')==='本(ほん)|読む(よむ)','only one-word tokens load: '+known(text));
 const other=Parseh.readings({scope:'book:ja:other',kind:'book',selector:'.other'});
 const el=document.createElement('div'); other.renderWords(el,'本','本(ほん)');
 assert(!el.querySelector('.reading-known'),'scope isolation');
 // a row built before it is placed is labelled, and followed once it is
 const loose=document.createElement('div');
 const lrow=other.wordControls(loose,'本(ほん) を');
 assert(lrow && lrow.querySelector('button').textContent==='本: I know this','a row built off the page is labelled');
 document.body.appendChild(loose); other.apply();
 lrow.querySelector('button').click();
 assert(lrow.querySelector('button').textContent==='本: show reading','and follows once placed');
 lrow.querySelector('button').click(); loose.remove();
 const off=()=>document.createElement('div');
 assert(other.wordControls(off(),'へ に')===null && other.wordControls(off(),'本(ほん')===null,'no row without a reading, nor for a line that does not parse');
 assert(other.wordControls(off(),'山(( 本(ほん)')===null,'nor for a line with a word that has no token');
 // the stylesheet hides a known word's reading outside .p1 and in Chinese too,
 // and leaves the plain .wd both readers already draw as it was
 localStorage.setItem('parseh_known_word:video:zh:t',JSON.stringify(['茶(chá)']));
 const zr=Parseh.readings({scope:'video:zh:t',kind:'video',selector:'.seg .fa'});
 const zel=document.createElement('div'); document.body.appendChild(zel);
 zr.renderWords(zel,'一杯茶','一(yì) 杯(bēi) 茶(chá)');
 assert(zel.querySelectorAll('ruby.reading-known').length===1 && getComputedStyle(zel.querySelector('ruby.reading-known rt')).visibility==='hidden','pinyin over a known word hides');
 zel.innerHTML='<span class="wd"><ruby class="reading-known">本<rt>ほん</rt></ruby></span>';
 const prt=getComputedStyle(zel.querySelector('rt'));
 assert(prt.visibility==='visible' && prt.userSelect!=='none','a .wd without data-w is styled as before');
 zel.remove();
 // the old store, for a chunk without words, is as it was
 localStorage.setItem(KK,JSON.stringify(['本']));
 const old=Parseh.readings({scope:'book:ja:words',kind:'book',selector:'.p1'});
 old.render(more,'本を読む','ほんをよむ');
 assert(more.querySelectorAll('ruby.reading-known').length===1,'kanji readings for chunks without words');
 return 'Known words: the word store, the kanji OR, a repeated word, controls and sync: passed';
}));

// ---- the word strip ----
await page.evaluate(L=>{
 window.LANGS=L; window.changes=[]; window.arrows=0;
 document.addEventListener('keydown',e=>{ if(/^Arrow/.test(e.key)) arrows++; });
 const s=Parseh.wordstrip({lang:L.ja,fa:'山へ柴刈りに、',value:'山(やま) へ 柴刈り(しばかり) に 、',
   reading:'やまへしばかりに',reorders:false,door:'book',onchange:(line,res)=>changes.push({line,res})});
 window.strip=s; document.querySelector('#strips').appendChild(s.el);
},LANGS);
const chips=page.locator('#strips .ws-chip');
const value=()=>page.evaluate(()=>strip.value());
const state=()=>page.evaluate(()=>({
 value:strip.value(),
 surfaces:[...strip.el.querySelectorAll('.ws-surf')].map(s=>s.textContent),
 readings:[...strip.el.querySelectorAll('.ws-read')].map(s=>s.value),
 text:strip.el.querySelector('.ws-text').value,
 errors:[...strip.el.querySelectorAll('.ws-note .ws-err')].map(e=>e.textContent),
 warnings:[...strip.el.querySelectorAll('.ws-note .ws-warn')].map(e=>e.textContent),
 note:strip.el.querySelector('.ws-note').hidden?'':strip.el.querySelector('.ws-note').textContent,
 focus:document.activeElement.className,
 focusChip:[...strip.el.querySelectorAll('.ws-chip')].indexOf(document.activeElement.closest('.ws-chip')),
 changes:changes.length, stale:strip.el.querySelector('.ws-chips').classList.contains('ws-stale')
}));
const eq=(got,want,msg)=>{ if(JSON.stringify(got)!==JSON.stringify(want)) throw Error(msg+': got '+JSON.stringify(got)+' want '+JSON.stringify(want)); };
let s=await state();
eq(s.surfaces,['山','へ','柴刈り','に','、'],'one chip per word, the chip text is the word');
eq([s.readings,s.note,s.text],[['やま','','しばかり','',''],'','山(やま) へ 柴刈り(しばかり) に 、'],'readings, a clean note, the line in the box');
eq(await page.evaluate(()=>[strip.el.dataset.lang,strip.el.querySelector('.ws-chips').dir,strip.el.querySelector('.ws-read').placeholder,
  strip.el.querySelector('.ws-text').hidden,strip.el.querySelector('.ws-propose').hidden]),['ja','ltr','kana',true,true],
  'language, direction, placeholder; text box closed; no propose without a proposer');

// cut
await page.mouse.move(1,1);
eq(await page.evaluate(()=>getComputedStyle(strip.el.querySelectorAll('.ws-chip')[2].querySelector('.ws-cut')).visibility),'hidden','cut points hide off the chip');
await chips.nth(2).hover();
eq(await chips.nth(2).locator('.ws-cut').count(),2,'a cut point between each two characters');
await chips.nth(2).locator('.ws-cut').first().click();
s=await state();
eq([s.value,s.surfaces,s.focus,s.focusChip,s.changes],['山(やま) へ 柴(しばかり) 刈り に 、',['山','へ','柴','刈り','に','、'],'ws-read',3,1],
   'cut: the reading stays on the first, the second\'s reading is empty and focused');
eq([s.errors.length,s.warnings.length,s.text===s.value],[0,1,true],'the note warns of the reading-less word');
eq(await page.evaluate(()=>changes[0].line+'|'+changes[0].res.warnings.map(w=>w.code)),'山(やま) へ 柴(しばかり) 刈り に 、|no_reading','onchange(line, check result)');
await page.keyboard.type('かり');
eq(await value(),'山(やま) へ 柴(しばかり) 刈り(かり) に 、','typing a reading rewrites the line');

// join
await page.locator('#strips .ws-join').nth(2).click();
s=await state();
eq([s.value,s.focus,s.focusChip],['山(やま) へ 柴刈り(しばかりかり) に 、','ws-read',2],'join: surfaces and readings run together');

// nudge
const before=await page.evaluate(()=>arrows);
await page.locator('#strips .ws-surf').nth(3).focus();
await page.keyboard.press('ArrowLeft');
s=await state();
eq([s.value,s.focus,s.focusChip],['山(やま) へ 柴刈(しばかりかり) りに 、','ws-surf',3],'← takes a character from the word before');
await page.keyboard.press('ArrowRight');
eq(await value(),'山(やま) へ 柴刈り(しばかりかり) に 、','→ gives it back');
await page.keyboard.press('ArrowRight');
eq(await value(),'山(やま) へ 柴刈り(しばかりかり) に 、','a one-character word keeps its character');
await page.locator('#strips .ws-surf').nth(1).focus();
await page.keyboard.press('ArrowLeft');
eq(await value(),'山(やま) へ 柴刈り(しばかりかり) に 、','nor is the word before ever emptied');
await page.locator('#strips .ws-surf').nth(0).focus();
await page.keyboard.press('ArrowLeft');
eq(await value(),'山(やま) へ 柴刈り(しばかりかり) に 、','the first word has no boundary to move');
eq(await page.evaluate(()=>arrows),before,'the arrows stay in the strip');

// the text box and the chips
await page.locator('#strips .ws-astext').click();
eq(await page.evaluate(()=>strip.el.querySelector('.ws-text').hidden),false,'edit as text opens the box');
let n=(await state()).changes;
await page.locator('#strips .ws-text').fill('山(やま) へ 柴刈り(しばかり) に、');
s=await state();
eq([s.surfaces,s.value,s.stale,s.changes>n],[['山','へ','柴刈り','に、'],'山(やま) へ 柴刈り(しばかり) に、',false,true],'typing a line that parses redraws the chips');
eq(s.warnings.length===1 && s.errors.length===0,true,'punctuation run into a word is a warning');
await page.locator('#strips .ws-text').fill('山(やま');
s=await state();
eq([s.surfaces.length,s.value,s.stale,s.errors.length],[4,'山(やま',true,1],'a line that does not parse keeps the chips, dimmed, and says why');
await page.locator('#strips .ws-read').nth(0).fill('さん');
s=await state();
eq([s.text,s.stale],['山(さん) へ 柴刈り(しばかり) に、',false],'the chips rewrite the box');

// the note, and set()
n=(await state()).changes;
await page.evaluate(()=>strip.set('山(やま) へ'));
s=await state();
eq([s.errors.length,s.surfaces,s.changes],[1,['山','へ'],n],'a line that does not rejoin the text is an error; set() runs no onchange');
if(!/do not reproduce/.test(s.errors[0]))throw Error('the reproduce error: '+s.errors[0]);
await page.evaluate(()=>strip.set('山(やま) へ 柴刈り(しばかり) に 、'));
s=await state();
eq([s.note,s.errors,s.warnings],['',[],[]],'a good line: nothing in the note');

// empty: divide by hand
await page.evaluate(()=>strip.set(''));
s=await state();
eq([s.surfaces,s.note,await page.evaluate(()=>strip.el.querySelector('.ws-hand').hidden)],[[],'This chunk has no words yet.',false],'an empty strip says so and offers divide by hand');
await page.locator('#strips .ws-hand').click();
s=await state();
eq([s.value,s.surfaces,s.errors,s.focus],['山へ柴刈りに、',['山へ柴刈りに、'],[],'ws-surf'],'divide by hand: one chip, the whole text');
eq(await page.evaluate(()=>strip.el.querySelector('.ws-hand').hidden),true,'divide by hand goes once there are words');
eq(await page.evaluate(()=>{
 const t=Parseh.wordstrip({lang:LANGS.ja,fa:'私は 本を　読む',value:'',door:'video'});
 document.querySelector('#strips').appendChild(t.el); t.el.querySelector('.ws-hand').click();
 const v=t.value(); t.destroy(); return [v,t.el.isConnected];
}),['私は本を読む',false],'divide by hand drops the whitespace; destroy() takes the strip away');

// a character outside the basic plane
await page.evaluate(()=>{
 window.big=Parseh.wordstrip({lang:LANGS.ja,fa:'𠮷野家',value:'𠮷野家(よしのや)',door:'book'});
 document.querySelector('#strips').appendChild(big.el);
});
const bigChip=page.locator('#strips .wordstrip').nth(1).locator('.ws-chip');
await bigChip.first().hover();
eq(await bigChip.first().locator('.ws-cut').count(),2,'𠮷野家 is three characters');
await bigChip.first().locator('.ws-cut').first().click();
eq(await page.evaluate(()=>big.value()),'𠮷(よしのや) 野家','cut after 𠮷, not inside it');
await page.locator('#strips .wordstrip').nth(1).locator('.ws-surf').nth(1).focus();
await page.keyboard.press('ArrowLeft');
eq(await page.evaluate(()=>big.value()),'𠮷(よしのや) 野家','𠮷 is a word of one character');
await page.keyboard.press('ArrowRight');
eq(await page.evaluate(()=>big.value()),'𠮷野(よしのや) 家','→ moves 野 across');

// propose (Chinese, a video)
await page.evaluate(()=>{
 window.confirms=0; window.answer=true; window.confirm=()=>(confirms++,answer);
 window.proposal='我(wǒ) 想(xiǎng) 要(yào) 一(yì) 杯(bēi) 茶(chá)';
 window.zh=Parseh.wordstrip({lang:LANGS.zh,fa:'我想要一杯茶',value:'',reading:'wǒ xiǎng yào yì bēi chá',door:'video',
   propose:async()=>proposal, onchange:(l,r)=>{window.zhLast={l,r};}});
 document.querySelector('#strips').appendChild(zh.el);
});
const Z=page.locator('#strips .wordstrip').nth(2);
eq(await page.evaluate(()=>[zh.el.querySelector('.ws-propose').hidden,zh.el.dataset.lang]),[false,'zh'],'propose is offered');
await Z.locator('.ws-propose').click();
await page.waitForFunction(()=>zh.value()!=='');
eq(await page.evaluate(()=>[zh.value(),confirms,zh.el.querySelectorAll('.ws-chip').length,zh.el.querySelector('.ws-read').placeholder,
  zhLast.r.errors.length,zhLast.r.warnings.length,zh.el.querySelector('.ws-note').hidden]),
  ['我(wǒ) 想(xiǎng) 要(yào) 一(yì) 杯(bēi) 茶(chá)',0,6,'pinyin',0,0,true],'a proposal fills an empty strip without asking');
await Z.locator('.ws-propose').click();
await page.waitForFunction(()=>!zh.el.querySelector('.ws-propose').disabled);
eq(await page.evaluate(()=>confirms),0,'an untouched proposal is replaced without asking');
await Z.locator('.ws-read').nth(0).fill('wo');
await page.evaluate(()=>{answer=false;});
await Z.locator('.ws-propose').click();
eq(await page.evaluate(()=>[confirms,zh.value()]),[1,'我(wo) 想(xiǎng) 要(yào) 一(yì) 杯(bēi) 茶(chá)'],'a touched strip asks, and a no keeps it');
await page.evaluate(()=>{answer=true; proposal='';});
await Z.locator('.ws-propose').click();
await page.waitForFunction(()=>/nothing was proposed/.test(zh.el.querySelector('.ws-say').textContent));
eq(await page.evaluate(()=>[confirms,zh.value()]),[2,'我(wo) 想(xiǎng) 要(yào) 一(yì) 杯(bēi) 茶(chá)'],'an empty proposal changes nothing');
await Z.locator('.ws-join').nth(1).click();
eq(await page.evaluate(()=>zh.value()),'我(wo) 想要(xiǎngyào) 一(yì) 杯(bēi) 茶(chá)','a join runs the pinyin together');
// pinyin is compared without its tone marks: yī and yì agree, yuè does not
await page.evaluate(()=>zh.set('我(wǒ) 想(xiǎng) 要(yào) 一(yī) 杯(bēi) 茶(chá)'));
eq(await page.evaluate(()=>zh.el.querySelector('.ws-note').hidden),true,'a changed tone is not a disagreement');
await page.evaluate(()=>zh.set('我(wǒ) 想(xiǎng) 要(yuè) 一(yì) 杯(bēi) 茶(chá)'));
eq(await page.evaluate(()=>[...zh.el.querySelectorAll('.ws-note .ws-warn')].length),1,'words that read otherwise than the chunk warn');
await page.evaluate(()=>{ const t=Parseh.wordstrip({lang:LANGS.ja,fa:'山',value:'山(やま',door:'book'});
  if(!t.el.querySelector('.ws-chips').classList.contains('ws-stale')||!t.el.querySelector('.ws-note .ws-err'))throw Error('an unparseable value on open');
  const u=Parseh.wordstrip({lang:LANGS.ja,fa:'山',value:'',door:'book'});
  u.el.querySelector('.ws-hand').click();
  u.el.querySelector('.ws-read').value='(や'; u.el.querySelector('.ws-read').dispatchEvent(new Event('input'));
  if(!/cannot be written/.test(u.el.querySelector('.ws-note .ws-err').textContent))throw Error('a reading that cannot be written: '+u.el.querySelector('.ws-note').textContent);
});
// right to left, → takes and ← gives
await page.evaluate(()=>{
 window.rtl=Parseh.wordstrip({lang:Object.assign({},LANGS.ja,{dir:'rtl'}),fa:'山川へ',value:'山川 へ',door:'book'});
 document.querySelector('#strips').appendChild(rtl.el);
});
eq(await page.evaluate(()=>rtl.el.querySelector('.ws-chips').dir),'rtl','the chips run the language\'s way');
await page.locator('#strips .wordstrip').nth(3).locator('.ws-surf').nth(1).focus();
await page.keyboard.press('ArrowRight');
eq(await page.evaluate(()=>rtl.value()),'山 川へ','right to left, → takes a character from the word before');
await page.keyboard.press('ArrowLeft');
eq(await page.evaluate(()=>rtl.value()),'山川 へ','and ← gives it back');
await page.evaluate(async()=>{
 const p=Parseh.wordstrip({lang:LANGS.zh,fa:'茶',value:'',door:'video',propose:async()=>{throw Error('no analyzer here');}});
 p.el.querySelector('.ws-propose').click();
 await new Promise(r=>setTimeout(r,0));
 const say=p.el.querySelector('.ws-say');
 if(!say.classList.contains('err')||say.textContent!=='no analyzer here'||p.value()!==''||p.el.querySelector('.ws-propose').disabled)
  throw Error('a refused proposal says why and changes nothing: '+say.textContent);
 const W=window.ParsehWordline; delete window.ParsehWordline;
 try {
  const q=Parseh.wordstrip({lang:LANGS.ja,fa:'山',value:'山(やま)',door:'book'});
  if(!/wordline\.js/.test((q.el.querySelector('.ws-note .ws-err')||{}).textContent))throw Error('no checker on the page is an error, not a clean note');
 } finally { window.ParsehWordline=W; }
});
if(Deno.env.get('WORDS_SHOT'))await page.screenshot({path:Deno.env.get('WORDS_SHOT')});
console.log('Word strip: cut, join, nudge, text box, note, divide by hand, propose: passed');
if(errors.length)throw Error(errors.join('\n'));
} finally { await browser.close(); }
