// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the studio's exercises (app.js, app.css): answering and
// checking, the editor's exercise form (pictures, recordings, jolly markdown,
// `key: |` blocks read as mdparser reads them), the library's download menu,
// "+ Deck" and "+ Add all exercises" against stand-in routes, and flashcards
// holding blocks and recordings served by a real HTTP server (Range and all:
// a player never loads from an intercepted route).  ffmpeg writes the tones.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/exercises.mjs
//   PARSEH_TEST_ARTIFACTS=<dir> also saves screenshots
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const md = `---
title: Browser exercises
target: ar
---

:::exercise fill-blanks
prompt: Complete [أنا]{tl}.
text: I [[v]] books.
- [v] read
- [ ] write
explanation-correct: Read is correct.
:::

:::exercise single-choice
prompt: Pick one.
- [ ] wrong
- [x] right
explanation-correct: The second answer is right.
explanation-incorrect: The first answer is wrong because it contradicts the page.
:::

:::exercise choose-all
prompt: Pick both.
- [x] a
- [ ] b
- [x] c
:::

:::exercise match-translations
prompt: Match.
- [سلام]{tl} => hello
- [كتاب]{tl} => book
:::

:::exercise construct-sentence
prompt: Order.
- [1] one
- [2] two
- [3] three
:::

:::exercise flashcard
card-type: jolly
front-primary: سؤال
front-secondary: suʾāl
back-primary: question
back-secondary: noun
:::`;

async function renderedDoc(preview=false, text=md, deckButton=false, assetBase=null) {
  const base = assetBase ? `'${assetBase}'` : 'None';
  const code = `import sys,json;sys.path[:0]=['markdown/exlex','markdown/app','lib'];import htmlgen;print(json.dumps(htmlgen.render_document(sys.argv[1],editor_preview=${preview?'True':'False'},deck_button=${deckButton?'True':'False'},asset_base=${base})['html']))`;
  const out = await new Deno.Command(python, {args:['-c',code,text],stdout:'piped',stderr:'piped'}).output();
  if (!out.success) throw Error(new TextDecoder().decode(out.stderr));
  return {html:JSON.parse(new TextDecoder().decode(out.stdout)),lang:'en',target:'ar',target_error:'',
    lang_record:{code:'ar',name:'Arabic',native:'العربية',dir:'rtl',script:'arabic',reading:false,vertical:false,word_sep:' ',translit_label:'transliteration',fonts:{}}};
}
const rendered = async preview => (await renderedDoc(preview)).html;

const browser = await chromium.launch({executablePath:Deno.env.get('CHROME_BIN'),headless:true});
const appScript = (await Deno.readTextFile(root+'/markdown/app/static/app.js'))
  .replace('__FOLD__', '(s => String(s).toLowerCase())');
// the studio's sheet and its chrome: /static/app.css answers with both, and
// since the split (2026-09-23) the disk holds them apart -- an exercise drawn
// with the chrome alone has none of the rules that lay a document out
const appCss = (await Deno.readTextFile(root+'/markdown/app/static/sheet.css'))
  + '\n' + (await Deno.readTextFile(root+'/markdown/app/static/app.css'));
const langsCss = await Deno.readTextFile(root+'/lib/langs.css');
// Every file of the studio's own that the editor page links, answered as the
// server answers it (app.js with its case fold spliced in, app.css as sheet +
// chrome).  The page was split into app.js + exform.js + editor.js and given a
// {{STUDIO}} prefix after this suite was written; a route list that knew only
// app.js left the editor with no editor at all, and no `.ex-edit` ever drawn.
const studioFiles = {
  '/static/app.js': [appScript, 'text/javascript'],
  '/static/app.css': [appCss, 'text/css'],
  '/static/langs.css': [langsCss, 'text/css'],
  '/static/exform.js': [await Deno.readTextFile(root+'/markdown/app/static/exform.js'), 'text/javascript'],
  '/static/editor.js': [await Deno.readTextFile(root+'/markdown/app/static/editor.js'), 'text/javascript'],
  '/static/promptpick.js': [await Deno.readTextFile(root+'/markdown/app/static/promptpick.js'), 'text/javascript'],
  '/static/mathjax.js': [await Deno.readTextFile(root+'/lib/mathjax.js'), 'text/javascript'],
  '/static/mathjax.css': [await Deno.readTextFile(root+'/lib/mathjax.css'), 'text/css'],
  '/static/mobile.css': [await Deno.readTextFile(root+'/markdown/app/static/mobile.css'), 'text/css'],
  '/static/mode.js': [await Deno.readTextFile(root+'/markdown/app/static/mode.js'), 'text/javascript'],
  '/static/latexwait.js': [await Deno.readTextFile(root+'/markdown/app/static/latexwait.js'), 'text/javascript'],
  '/lib/llmrow.js': [await Deno.readTextFile(root+'/lib/llmrow.js'), 'text/javascript'],
};
const studioFile = (route, u, path=u.pathname) => {
  const f = studioFiles[path];
  return f ? route.fulfill({body:f[0], contentType:f[1]}) : null;
};
// the three snippets every studio page carries in its head and its bar (the
// interface mode, the switch, the app tags), the very text deckroutes fills in
const pageSnippets = JSON.parse(new TextDecoder().decode((await new Deno.Command(python,{
  args:['-c',"import sys,json;sys.path[:0]=['markdown/app','markdown/exlex','lib'];import deckroutes as d;print(json.dumps({'MODE_SCRIPT':d.MODE_SCRIPT,'MODE_SWITCH':d.MODE_SWITCH,'APP_HEAD':d.APP_HEAD}))"],
  stdout:'piped',stderr:'piped'}).output()).stdout));
// and the recordings the editor's Audio button takes, as server._edit_mapping writes them
const audioKeys = JSON.parse(new TextDecoder().decode((await new Deno.Command(python,{
  args:['-c',"import sys,json;sys.path[:0]=['markdown/app','markdown/exlex','lib'];import htmlgen,audiofile;print(json.dumps({'AUDIO_ACCEPT':htmlgen.esc(audiofile.ACCEPT),'AUDIO_HUMAN':htmlgen.esc(audiofile.HUMAN)}))"],
  stdout:'piped',stderr:'piped'}).output()).stdout));
try {
  const page = await browser.newPage();
  const errors=[]; page.on('pageerror', e=>errors.push(e.message));
  await page.setContent(`<body data-page="noop"><article id="sheet" class="sheet" data-lang="ar">${await rendered()}</article><div id="modal-root"></div></body>`);
  await page.addStyleTag({content:appCss});
  await page.addStyleTag({path:root+'/lib/langs.css'});
  await page.addScriptTag({content:appScript});
  const result = await page.evaluate(() => {
    const assert=(v,m)=>{if(!v)throw Error(m)};
    const sheet=document.querySelector('#sheet'); bindExercises(sheet);
    assert(document.querySelectorAll('[data-scored="1"]').length===5,'flashcard excluded from scoring');
    assert(document.querySelector('.fa[dir="rtl"][lang="ar"]'),'RTL target run preserved');
    const sentenceSequence=document.querySelector('[data-subtype="construct-sentence"] .ex-sequence');
    const sequenceStyle=getComputedStyle(sentenceSequence);
    assert(sequenceStyle.flexDirection==='row'&&sequenceStyle.flexWrap==='wrap',
      'sentence chunks flow horizontally and wrap');
    assert(getComputedStyle(sentenceSequence.querySelector('.ex-item')).width!==sequenceStyle.width,
      'sentence chunks do not expand into full-width rows');

    const fill=document.querySelector('[data-subtype="fill-blanks"]');
    fill.querySelector('[data-item="i0"]').click(); fill.querySelector('.ex-blank').click();
    const one=document.querySelector('[data-subtype="single-choice"]');
    one.querySelector('[data-correct="1"]').click();
    const all=document.querySelector('[data-subtype="choose-all"]');
    all.querySelectorAll('[data-correct="1"]').forEach(x=>x.click());
    const match=document.querySelector('[data-subtype="match-translations"]');
    match.querySelectorAll('.ex-match-drop').forEach(drop=>{
      match.querySelector(`[data-item="${drop.dataset.answer}"]`).click(); drop.click();
    });
    const order=document.querySelector('[data-subtype="construct-sentence"] .ex-sequence');

    // THE ARROWS, the way through where dragging will not do: every box in a
    // sequence carries two, each moves it one place, and the box at either
    // end says so.  What they do is what a drag does -- the order IS the
    // answer -- so the exercise is put right with them here.
    const names=()=>[...order.querySelectorAll('.ex-item')].map(x=>x.dataset.item);
    assert(order.querySelector('.ex-item').tagName==='DIV',
      'a box with arrows is a div: a button cannot hold buttons');
    assert(order.querySelector('.ex-item').getAttribute('role')==='button'
      &&order.querySelector('.ex-item').tabIndex===0,
      'and it is still a button to anyone reading the page');
    assert(order.querySelector('.ex-item .ex-move[data-move="earlier"]').disabled
      &&!order.querySelector('.ex-item .ex-move[data-move="later"]').disabled,
      'the first box cannot go earlier, and can go later');
    assert([...order.querySelectorAll('.ex-item')].pop().querySelector('[data-move="later"]').disabled,
      'and the last cannot go later');
    // This fixture is `target: ar`, so its line runs right to left and the
    // arrows point the way the box will really go: "earlier" is to the RIGHT
    // (→), "later" to the left (←).  The left-to-right line is checked below,
    // outside this page, on a document whose target is English.
    const glyph=el=>getComputedStyle(el,'::before').content;
    assert(getComputedStyle(order).direction==='rtl','the Arabic line runs right to left');
    assert(glyph(order.querySelector('[data-move="earlier"]'))==='"→"'
      &&glyph(order.querySelector('[data-move="later"]'))==='"←"',
      'a line of chunks that runs right to left points its arrows along the line: earlier is →, later is ←');
    // the second box, moved one place earlier, changes places with the first
    const was=names();
    order.querySelectorAll('.ex-item')[1].querySelector('[data-move="earlier"]').click();
    assert(names().join()===[was[1],was[0],...was.slice(2)].join(),
      'an arrow moves the box one place: '+was.join()+' -> '+names().join());
    assert(names().length===was.length,'and nothing else moves');
    // put it right with the arrows alone, never touching a drag
    order.dataset.answer.split(',').forEach((id,want)=>{
      const item=order.querySelector(`[data-item="${id}"]`);
      for(let at=names().indexOf(id);at>want;at--)
        item.querySelector('[data-move="earlier"]').click();
    });
    assert(names().join()===order.dataset.answer,
      'the whole sentence can be built with the arrows: '+names().join());
    document.querySelector('.ex-correct-all').click();
    assert(document.querySelector('.ex-score').textContent==='5 / 5 correct','central score');
    assert(document.querySelectorAll('.exercise.correct').length===5,'exercise feedback');
    assert(!fill.querySelector('.ex-explanation').hidden,'explanation revealed');
    assert(fill.querySelector('.ex-explanation-neutral'),'single explanation is neutral');
    assert(!one.querySelector('[data-explanation-for="correct"]').hidden,'correct-result explanation shown');
    assert(one.querySelector('[data-explanation-for="incorrect"]').hidden,'incorrect-result explanation hidden after success');
    one.querySelector('[data-correct="0"]').click();
    assert(document.querySelector('.ex-score').hidden,'answer change invalidates score');
    assert(!one.classList.contains('correct'),'answer change clears stale feedback');
    document.querySelector('.ex-correct-all').click();
    assert(one.classList.contains('incorrect'),'changed answer judged incorrect');
    assert(one.querySelector('[data-explanation-for="correct"]').hidden,'correct explanation hidden after error');
    assert(!one.querySelector('[data-explanation-for="incorrect"]').hidden,'incorrect-result explanation shown');

    const card=document.querySelector('.ex-flashcard'); card.click();
    assert(card.classList.contains('flipped')&&!card.querySelector('.ex-card-back').hidden,'Jolly flips');

    // ⤢ Enlarge: the card large over the page, and turning it there turns the card on the page
    const zooms=[...document.querySelectorAll('.ex-card-zoom')];
    assert(zooms.length===1&&zooms[0].closest('.exercise').dataset.primitive==='flashcard','one Enlarge, on the flashcard');
    let heard=0; document.addEventListener('keydown',()=>heard++);
    zooms[0].click();
    const win=document.querySelector('.ex-zoom-overlay .ex-zoom-modal');
    assert(win,'Enlarge opens a window over the page');
    const box=win.getBoundingClientRect();
    assert(box.width>=innerWidth*0.9&&box.height>=innerHeight*0.85,'nearly as big as the screen: '+box.width+'x'+box.height);
    const big=()=>win.querySelector('.ex-flashcard');
    assert(big().classList.contains('flipped')&&!big().querySelector('.ex-card-back').hidden,'the enlarged card is the card as it is: turned');
    // and larger -- magnified whole, so it is measured where it is drawn: its
    // text is laid out at the page's own size, and only then made bigger
    const drawn=el=>el.getBoundingClientRect(), a=drawn(card), b=drawn(big());
    assert(b.width>a.width*1.3&&b.height>a.height*1.3,'and larger: '+a.width+'x'+a.height+' on the page, '+b.width+'x'+b.height+' enlarged');
    big().click();
    assert(!card.classList.contains('flipped')&&!big().classList.contains('flipped'),'a click on it turns the card on the page too');
    win.dispatchEvent(new KeyboardEvent('keydown',{key:' ',bubbles:true}));
    assert(card.classList.contains('flipped')&&big().classList.contains('flipped'),'Space turns it');
    win.dispatchEvent(new KeyboardEvent('keydown',{key:'x',bubbles:true}));
    assert(heard===0,'the page underneath hears no key while it is open');
    win.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    assert(!document.querySelector('.ex-zoom-overlay'),'Escape closes it');
    return 'reader interactions, correction, invalidation, RTL, Jolly and the enlarged card passed';
  });
  console.log(result);
  if (Deno.env.get('PARSEH_TEST_ARTIFACTS'))
    await page.screenshot({path:Deno.env.get('PARSEH_TEST_ARTIFACTS')+'/exercises.png',fullPage:true});

  // THE ARROWS ON A LINE THAT RUNS LEFT TO RIGHT.  The page above is Arabic,
  // where "earlier" is to the right; a Spanish document runs the other way, so
  // there "earlier" is ← and "later" is →, and a list of lines (not a line of
  // chunks) points up and down whichever language it is in.
  const ltrDoc = `---
title: Left to right
target: es
---

:::exercise construct-sentence
prompt: Order.
- [1] uno
- [2] dos
- [3] tres
:::

:::exercise order-sentences
prompt: Order the lines.
- [1] uno
- [2] dos
:::`;
  await page.setContent(`<body data-page="noop"><article id="sheet" class="sheet" data-lang="es">${(await renderedDoc(false, ltrDoc)).html}</article><div id="modal-root"></div></body>`);
  await page.addStyleTag({content:appCss});
  await page.addStyleTag({path:root+'/lib/langs.css'});
  console.log(await page.evaluate(() => {
    const assert=(v,m)=>{if(!v)throw Error(m)};
    const glyph=el=>getComputedStyle(el,'::before').content;
    const line=document.querySelector('[data-subtype="construct-sentence"] .ex-sequence');
    const list=document.querySelector('[data-subtype="order-sentences"] .ex-sequence');
    assert(line&&list,'the Spanish page has a line of chunks and a list of lines');
    assert(getComputedStyle(line).direction==='ltr','the Spanish line runs left to right');
    assert(glyph(line.querySelector('[data-move="earlier"]'))==='"←"'
      &&glyph(line.querySelector('[data-move="later"]'))==='"→"',
      'a line of chunks that runs left to right points its arrows along the line: earlier is ←, later is →');
    assert(glyph(list.querySelector('[data-move="earlier"]'))==='"↑"'
      &&glyph(list.querySelector('[data-move="later"]'))==='"↓"',
      'a list of lines points them up and down');
    return 'arrows along a left-to-right line, and up and down in a list, passed';
  }));

  const plainPrompt = `---
title: Prompt weight
target: fa
---
:::exercise true-false
prompt: |
  Decide whether each statement is True or False.
  [[دیروز دو شنبه بود.⏎امروز سه شنبه است.]{tl}]{no-bold}
- [فردا چهار شنبه است.]{tl} => true
:::`;
  const promptPage = await browser.newPage();
  await promptPage.setContent(`<article class="sheet" data-lang="fa">${(await renderedDoc(false, plainPrompt)).html}</article>`);
  await promptPage.addStyleTag({content:appCss});
  console.log(await promptPage.evaluate(() => {
    const instruction=document.querySelector('.ex-prompt .ex-field-line');
    const passage=document.querySelector('.ex-prompt .ex-no-bold .fa');
    const question=document.querySelector('.ex-question .fa');
    const block=document.querySelector('.ex-prompt .ex-target-block');
    if(!instruction||!passage||!question||!block)throw Error('prompt pieces are missing');
    const a=getComputedStyle(instruction), b=getComputedStyle(passage), c=getComputedStyle(question);
    if(Number(a.fontWeight)<=Number(b.fontWeight)||b.fontWeight!==c.fontWeight
       ||b.fontFamily!==c.fontFamily||b.fontSize!==c.fontSize)
      throw Error('the unbolded prompt passage must match an exercise question');
    if(getComputedStyle(block).direction!=='rtl'||block.querySelectorAll('br').length!==1)
      throw Error('the prompt passage must keep its RTL direction and line break');
    return 'a nested {no-bold} prompt passage matches the question style and stays RTL';
  }));
  await promptPage.close();

  // A sentence in an RTL target must wrap from the right edge even when the
  // surrounding activity is LTR. The answer-direction field overrides that
  // target default independently of content-direction.
  const wrapSource = `---\ntitle: Wrap\ntarget: ar\n---\n\n:::exercise construct-sentence\ncontent-direction: ltr\nprompt: Build it.\n- [1] [الأول]{tl}\n- [2] [الثاني]{tl}\n- [3] [الثالث]{tl}\n- [4] [الرابع]{tl}\n:::`;
  const wrapPage = await browser.newPage();
  await wrapPage.setContent(`<article class="sheet" data-lang="ar">${(await renderedDoc(true, wrapSource)).html}</article>`);
  await wrapPage.addStyleTag({content:appCss});
  const wrapped = await wrapPage.evaluate(() => {
    const seq = document.querySelector('.ex-sequence-inline');
    seq.style.width = '380px';
    [...seq.children].forEach(item => { item.style.minWidth = '175px'; });
    const rects = [...seq.children].map(item => item.getBoundingClientRect());
    const next = rects.find(r => r.top > rects[0].top + 2);
    return {dir:getComputedStyle(seq).direction, wrapped:!!next,
            edge:next ? Math.abs(rects[0].right-next.right) : 999};
  });
  if(wrapped.dir!=='rtl'||!wrapped.wrapped||wrapped.edge>2)
    throw Error('the RTL sentence answer did not wrap at the right edge: '+JSON.stringify(wrapped));
  await wrapPage.close();

  const translitSource = `---\ntitle: Cards\ntarget: fa\n---\n\n:::exercise flashcard\ncard-type: vocab\ntarget: [کتاب]{tl}\nreading: reading\ntransliteration: ketāb\nmeaning: book\n:::\n\n:::exercise flashcard\ncard-type: opposites\ntarget: گرم\ntransliteration: garm\nopposite: سرد\nopposite-transliteration: sard\n:::\n\n:::exercise flashcard\ncard-type: vocab\ntarget: ماه\nmeaning: moon\n:::`;
  const translitPage = await browser.newPage();
  await translitPage.setContent(`<body data-page="noop"><article id="sheet" class="sheet" data-lang="fa">${(await renderedDoc(false, translitSource)).html}</article></body>`);
  await translitPage.addStyleTag({content:appCss});
  await translitPage.addScriptTag({content:appScript});
  const translitToggle = await translitPage.evaluate(() => {
    bindExercises(document.querySelector('#sheet'));
    const buttons = [...document.querySelectorAll('.ex-translit-switch')];
    const fields = [...document.querySelectorAll('.ex-card-transliteration')];
    const reading = document.querySelector('.ex-card-front .ex-card-field.secondary:not(.ex-card-transliteration)');
    if(buttons.length!==2||fields.length!==3||!reading)return 'wrong flashcard controls or fields';
    buttons[0].click();
    if(!document.body.classList.contains('ex-hide-transliteration')
       ||!fields.every(x=>getComputedStyle(x).display==='none')
       ||getComputedStyle(reading).display==='none'
       ||!buttons.every(x=>x.textContent==='Show transliterations'))return 'hide did not affect all cards';
    buttons[1].click();
    if(fields.some(x=>getComputedStyle(x).display==='none')
       ||!buttons.every(x=>x.textContent==='Hide transliterations'))return 'show did not restore all cards';
    return 'ok';
  });
  if(translitToggle!=='ok')throw Error('flashcard transliteration toggle: '+translitToggle);
  await translitPage.close();

  // A FINGER IS NOT A MOUSE.  Where the pointer is coarse, dragging a block
  // of a sequence starts turned off and the arrows are the way through --
  // and because that is a guess about the machine, a switch in the head says
  // which it is and is remembered.  An exercise with no arrows (a bank and
  // its blanks) is never touched by it.
  const phoneCtx = await browser.newContext({hasTouch:true, isMobile:true, viewport:{width:390,height:780}});
  const phone = await phoneCtx.newPage();
  const phoneErrors=[]; phone.on('pageerror', e=>phoneErrors.push(e.message));
  const phoneBody = html => `<body data-page="noop"><article id="sheet" class="sheet" data-lang="ar">${html}</article><div id="modal-root"></div></body>`;
  const seqDoc = await rendered();
  await phone.setContent(phoneBody(seqDoc));
  await phone.addStyleTag({content:appCss});
  await phone.addScriptTag({content:appScript});
  console.log(await phone.evaluate(() => {
    const assert=(v,m)=>{if(!v)throw Error(m)};
    bindExercises(document.querySelector('#sheet'));
    assert(matchMedia('(pointer: coarse)').matches,'the test is run as a touch screen');
    const seq=document.querySelector('.ex-sequence'), bank=document.querySelector('.ex-bank .ex-item');
    const sw=document.querySelector('.ex-drag-switch');
    assert(sw&&!sw.hidden,'a sequence carries the switch, and the page shows it');
    assert(!document.querySelector('[data-subtype="fill-blanks"] .ex-drag-switch'),
      'an exercise with no arrows carries none');
    assert(sw.textContent.includes('off')&&sw.getAttribute('aria-pressed')==='false',
      'and it says dragging is off: '+sw.textContent);
    assert(!seq.querySelector('.ex-item').draggable,'a block of a sequence cannot be dragged');
    assert(bank.draggable,'a block with no arrows still can, here as anywhere');
    // a tap does nothing to a block the arrows rule, and the arrows still move it
    seq.querySelector('.ex-item').click();
    assert(!seq.querySelector('.ex-item.picked'),'a tap does not pick it up');
    const was=[...seq.querySelectorAll('.ex-item')].map(x=>x.dataset.item).join();
    seq.querySelectorAll('.ex-item')[1].querySelector('[data-move="earlier"]').click();
    assert([...seq.querySelectorAll('.ex-item')].map(x=>x.dataset.item).join()!==was,
      'and the arrows still move it');
    // the switch turns dragging back on, for every sequence on the page
    sw.click();
    assert(sw.textContent.includes('on')&&sw.getAttribute('aria-pressed')==='true','the switch says on');
    assert(seq.querySelector('.ex-item').draggable,'and the blocks can be dragged again');
    // this page has no address of its own, so the browser refuses to keep
    // anything for it: the switch holds all the same, which is what a
    // private window gets (what it says is kept is tried below, on a served
    // page)
    return 'a touch screen gets the arrows alone, and the switch says so, storage or no storage passed';
  }));
  if(phoneErrors.length)throw Error(phoneErrors.join('\n'));
  await phoneCtx.close();

  // and it is remembered: a page served from a real address, where a browser
  // keeps what a page stores, opens the next time the way it was left
  const dragServer = Deno.serve({port:0,hostname:'127.0.0.1',onListen:()=>{}}, req=>{
    const path=new URL(req.url).pathname;
    if(path==='/app.js')return new Response(appScript,{headers:{'Content-Type':'text/javascript'}});
    if(path==='/app.css')return new Response(appCss,{headers:{'Content-Type':'text/css'}});
    return new Response(`<!doctype html><html><head><link rel="stylesheet" href="/app.css"></head>
      ${phoneBody(seqDoc)}<script src="/app.js"></script></html>`,{headers:{'Content-Type':'text/html; charset=utf-8'}});
  });
  const keptCtx = await browser.newContext({hasTouch:true, isMobile:true, viewport:{width:390,height:780}});
  const kept = await keptCtx.newPage();
  const keptErrors=[]; kept.on('pageerror', e=>keptErrors.push(e.message));
  await kept.goto(`http://127.0.0.1:${dragServer.addr.port}/`);
  await kept.evaluate(() => {
    bindExercises(document.querySelector('#sheet'));
    document.querySelector('.ex-drag-switch').click();      // dragging on
  });
  await kept.reload();
  console.log(await kept.evaluate(() => {
    const assert=(v,m)=>{if(!v)throw Error(m)};
    bindExercises(document.querySelector('#sheet'));
    const sw=document.querySelector('.ex-drag-switch');
    assert(localStorage.getItem('parseh_exercise_drag')==='1','the browser wrote it down');
    assert(sw.textContent.includes('on'),'the page opens with what was said: '+sw.textContent);
    assert(document.querySelector('.ex-sequence .ex-item').draggable,'and its blocks can be dragged');
    return 'and a touch screen told otherwise stays told, page after page passed';
  }));
  if(keptErrors.length)throw Error(keptErrors.join('\n'));
  await keptCtx.close();
  await dragServer.shutdown();

  const preview = await browser.newPage();
  await preview.setContent(`<body data-page="noop"><article id="sheet">${await rendered(true)}</article><div id="modal-root"></div></body>`);
  await preview.addScriptTag({content:appScript});
  console.log(await preview.evaluate(()=>{
    const sheet=document.querySelector('#sheet'); bindExercises(sheet,{preview:true});
    if(!document.querySelector('.exercise.correct')||!document.querySelector('.ex-option.selected'))throw Error('preview not solved');
    if(!document.querySelector('.ex-blank .ex-item')||!document.querySelector('.ex-match-drop .ex-item'))throw Error('preview placement not solved');
    return 'solved editor preview passed';
  }));
  console.log(await preview.evaluate(()=>{
    const none=bindExercises(document.createElement('div'));
    if(none.exercises.length!==0||none.judge()!==false)throw Error('no exercises: an inert judge expected');
    const sheet=document.querySelector('#sheet'), run=bindExercises(sheet,{preview:true});
    if(run.exercises.length!==sheet.querySelectorAll('.exercise').length)throw Error('bindExercises did not return its exercises');
    if(run.judge(sheet.querySelector('[data-subtype="single-choice"]'))!==true)throw Error('judge(ex) is not true on a solved exercise');
    return 'bindExercises returns {judge, exercises} passed';
  }));

  const index = await browser.newPage();
  const indexErrors=[]; index.on('pageerror',e=>indexErrors.push(e.message));
  let lastDocsQuery='';
  const allDocs=[
    {id:'a',target:'en',title:'A',title_html:'A',tags:['grammar','hard']},
    {id:'b',target:'en',title:'B',title_html:'B',tags:['grammar']},
    {id:'c',target:'en',title:'C',title_html:'C',tags:['vocabulary']},
    {id:'d',target:'ar',title:'D',title_html:'D',tags:['vocabulary']},
  ];
  let indexHtml=(await Deno.readTextFile(root+'/markdown/app/templates/index.html'))
    .replaceAll('{{BASE}}','').replace('{{LANG_CHIPS}}','<div class="parseh-langs"><button class="chip on" data-pick="all">all<span class="n">3</span></button><button class="chip" data-pick="en" data-lang="en"><span class="native">English</span><span class="n">3</span></button></div>')
    .replace('{{LANGS_JSON}}','[{"code":"en","name":"English","native":"English","dir":"ltr"},{"code":"ar","name":"Arabic","native":"العربية","dir":"rtl"}]');
  let downloadAnswer='zip';
  // the uploads: a markdown file without its header is answered with what it lacks
  const uploads=[], zipPosts=[];
  const HEADER_ANSWER={ok:false,header_needed:true,error:'the header is missing title, subtitle, note, lang, target',
    present:false,missing:['title','subtitle','note','lang','target'],values:{},
    defaults:{title:'Owls',subtitle:'',note:'',lang:'en',target:'fa'},
    langs:[{code:'en',name:'English'},{code:'it',name:'Italian'}],
    targets:[{code:'fa',name:'Persian'},{code:'ar',name:'Arabic'},{code:'en',name:'English'}]};
  await index.route('**/*',route=>{
    const u=new URL(route.request().url());
    if(u.pathname==='/')return route.fulfill({body:indexHtml,contentType:'text/html'});
    // the form's POST answers into a hidden frame: a zip is saved as a file,
    // a refusal is JSON, and a server that is gone answers nothing at all
    if(u.pathname==='/api/download'){
      if(downloadAnswer==='gone')return route.abort('connectionrefused');
      if(downloadAnswer==='refuse')return route.fulfill({status:400,json:{ok:false,error:'no documents to download'}});
      return route.fulfill({status:200,body:'PK\x05\x06'+'\0'.repeat(18),contentType:'application/zip',
        headers:{'Content-Disposition':'attachment; filename="studio-3-documents-20260914-1200.zip"'}});
    }
    if(u.pathname==='/static/app.js')return route.fulfill({body:appScript,contentType:'text/javascript'});
    if(u.pathname==='/static/app.css')return route.fulfill({body:appCss,contentType:'text/css'});
    if(u.pathname==='/api/tags')return route.fulfill({json:{tags:[{tag:'grammar',count:2},{tag:'hard',count:1},{tag:'vocabulary',count:1}]}});
    if(u.pathname==='/api/status')return route.fulfill({json:{docs:3,xelatex:true,hyphenation:true,library:'test'}});
    if(u.pathname==='/api/docs'&&route.request().method()==='POST'){
      const b=route.request().postDataJSON(); uploads.push(b);
      if(b.check_header&&!b.markdown.startsWith('---'))return route.fulfill({status:422,json:HEADER_ANSWER});
      return route.fulfill({status:201,json:{meta:{id:'owls-abc123',title:'Owls'}}});
    }
    if(u.pathname==='/api/docs/zip'){
      const headers=u.searchParams.get('headers'); zipPosts.push(headers);
      if(!headers)return route.fulfill({status:422,json:Object.assign({},HEADER_ANSWER,{files:[
        {name:'notes/bee.md',present:true,missing:['subtitle','note'],values:{title:'Bee',lang:'en',target:'it'},
         defaults:{title:'Bee',subtitle:'',note:'',lang:'en',target:'it'}},
        {name:'c.md',present:false,missing:['title','subtitle','note','lang','target'],values:{},
         defaults:{title:'C',subtitle:'',note:'',lang:'en',target:'fa'}}]})});
      return route.fulfill({status:201,json:{ok:true,docs:[{id:'bee-111111',title:'Bee'},{id:'ants-222222',title:'Ants'}],
        warnings:['notes/bee.md: images/gone.png is not in the zip']}});
    }
    if(u.pathname.startsWith('/doc/'))return route.fulfill({body:'<!doctype html><title>a document</title>',contentType:'text/html'});
    if(u.pathname==='/api/docs'){
      lastDocsQuery=u.search;
      const inc=(u.searchParams.get('tags')||'').split(',').filter(Boolean);
      const exc=(u.searchParams.get('exclude_tags')||'').split(',').filter(Boolean);
      const docs=allDocs.filter(d=>inc.every(t=>d.tags.includes(t))&&!exc.some(t=>d.tags.includes(t)));
      return route.fulfill({json:{docs}});
    }
    return route.fulfill({body:'',contentType:'text/css'});
  });
  await index.goto('http://parseh.test/');
  await index.waitForSelector('.tagchip');
  await index.locator('.tagchip').filter({hasText:'grammar'}).click();
  await index.locator('.tagchip').filter({hasText:'hard'}).click({modifiers:['Shift']});
  await index.waitForFunction(()=>document.querySelectorAll('.card').length===1);
  if(await index.locator('.card h3').textContent()!=='B')throw Error('include/exclude composition failed');
  if(!lastDocsQuery.includes('tags=grammar')||!lastDocsQuery.includes('exclude_tags=hard'))throw Error('tag query missing include/exclude');
  if(!await index.locator('.tagchip').filter({hasText:'hard'}).evaluate(e=>e.classList.contains('excluded')))throw Error('excluded tag styling missing');
  if(indexErrors.length)throw Error(indexErrors.join('\n'));
  console.log('composable include/exclude tag filtering passed');

  // (B) the download menu counts the cards every filter pass leaves
  // shown, and posts their ids in display order.  Its button is the
  // <summary> of a menu (Markdown, or Markdown + media), which takes no
  // disabled attribute: with nothing shown the menu is shut and made
  // unclickable instead (.dropdown.disabled)
  const downloadShows=(label,disabled=false)=>index.waitForFunction(([l,d])=>{
    const b=document.querySelector('#btn-download-shown'), box=document.querySelector('#download-shown');
    return b&&box&&b.tagName==='SUMMARY'&&b.textContent===l&&box.classList.contains('disabled')===d;
  },[label,disabled]);
  const downloadShown=async()=>{
    await index.locator('#btn-download-shown').click();
    await index.locator('#dl-shown-md').click();
  };
  const tag=name=>index.locator('.tagchip').filter({hasText:name});
  await downloadShows('Download 1 shown');
  await tag('grammar').click(); await tag('grammar').click(); await tag('hard').click();
  await index.waitForFunction(()=>document.querySelectorAll('.card').length===4);
  await downloadShows('Download 4 shown');
  if(await index.locator('#btn-download-shown').getAttribute('title')!=='Download the 4 documents shown')
    throw Error('download title does not name the count: '+await index.locator('#btn-download-shown').getAttribute('title'));
  await index.locator('.parseh-langs .chip[data-pick="ar"]').click();
  await downloadShows('Download 1 shown');
  await index.locator('.parseh-langs .chip[data-pick="en"]').click();
  await downloadShows('Download 3 shown');
  const posted=index.waitForRequest(r=>new URL(r.url()).pathname==='/api/download');
  const saved=index.waitForEvent('download',{timeout:5000});
  await downloadShown();
  const downloadRequest=await posted;
  if(downloadRequest.method()!=='POST')throw Error('download is not a POST');
  const downloadForm=new URLSearchParams(downloadRequest.postData()||'');
  if(downloadForm.get('ids')!=='a,b,c'||downloadForm.get('shape')!=='md')
    throw Error('download posted '+downloadRequest.postData());
  if(await index.locator('#download-shown').evaluate(d=>d.open))throw Error('the download menu stayed open');
  if((await saved).suggestedFilename()!=='studio-3-documents-20260914-1200.zip')throw Error('the zip was not saved as a file');
  await index.waitForTimeout(150);
  const libraryStays=async what=>{
    if(new URL(index.url()).pathname!=='/'||await index.locator('.card').count()!==4||!await index.locator('#search').count())
      throw Error(what+' navigated away from the library');
  };
  await libraryStays('the download');
  if(!await index.locator('#toast').isHidden())throw Error('a saved zip was reported: '+await index.locator('#toast').textContent());
  // a refusal (every shown document gone meanwhile) is told, not shown as a page
  downloadAnswer='refuse';
  await downloadShown();
  await index.waitForFunction(()=>!document.querySelector('#toast').hidden&&document.querySelector('#toast').classList.contains('err'),null,{timeout:5000})
    .catch(()=>{throw Error('a refused download was not reported')});
  if(await index.locator('#toast').textContent()!=='Could not download: no documents to download')
    throw Error('refused download toast: '+await index.locator('#toast').textContent());
  await libraryStays('a refused download');
  // a second refusal leaves the tab's history alone, so Back still leaves the page
  const historyBefore=await index.evaluate(()=>history.length);
  await index.evaluate(()=>{const t=document.querySelector('#toast');t.hidden=true;t.textContent='';});
  await downloadShown();
  await index.waitForFunction(()=>document.querySelector('#toast').textContent.includes('no documents to download'),null,{timeout:5000})
    .catch(()=>{throw Error('a second refused download was not reported')});
  if(await index.evaluate(()=>history.length)!==historyBefore)
    throw Error('a refused download added an entry to the tab history');
  if(await index.locator('#download-sink').count()!==1)throw Error('the download frame was multiplied, not replaced');
  downloadAnswer='gone';
  await index.evaluate(()=>{const t=document.querySelector('#toast');t.hidden=true;t.textContent='';});
  await downloadShown();
  await index.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Could not download'),null,{timeout:5000})
    .catch(()=>{throw Error('a download nobody answered was not reported')});
  await libraryStays('a download nobody answered');
  downloadAnswer='zip';
  // nothing shown: the one "hard" document, and "grammar" (which it has)
  // excluded -- the row offers only a tag that still counts something
  await tag('hard').click(); await tag('grammar').click({modifiers:['Shift']});
  await index.waitForFunction(()=>document.querySelectorAll('.card').length===0);
  await downloadShows('Download 0 shown',true);
  if(await index.locator('#btn-download-shown').evaluate(b=>getComputedStyle(b).pointerEvents)!=='none')
    throw Error('with nothing shown the download menu can still be opened');
  if(indexErrors.length)throw Error(indexErrors.join('\n'));
  console.log('download of the shown documents passed');

  // (C) uploads: a markdown file without its header is asked for it before it goes in
  const owls={name:'owls.md',mimeType:'text/markdown',buffer:Buffer.from('# Owls\n\nhoot\n')};
  await index.setInputFiles('#file-upload',owls);
  await index.waitForSelector('.header-modal');
  const chipNow=await index.evaluate(()=>sharedLang());
  const askedFor=await index.evaluate(()=>[...document.querySelectorAll('.header-modal [data-key]')].map(i=>[i.dataset.key,i.tagName,i.value]));
  const targetFirst=['fa','ar','en'].includes(chipNow)?chipNow:'fa';
  if(JSON.stringify(askedFor)!==JSON.stringify([['title','INPUT','Owls'],['subtitle','INPUT',''],['note','INPUT',''],['lang','SELECT','en'],['target','SELECT',targetFirst]]))
    throw Error('the header dialog asks for: '+JSON.stringify(askedFor));
  if(!(await index.locator('.header-preview').textContent()).startsWith('---\ntitle: Owls\nsubtitle:\nnote:\nlang: en\n'))
    throw Error('the header it will add: '+await index.locator('.header-preview').textContent());
  await index.locator('.header-modal [data-key="subtitle"]').fill('night birds');
  await index.locator('.header-modal [data-key="target"]').selectOption('fa');
  await Promise.all([index.waitForURL('**/doc/owls-abc123'),index.locator('.header-modal [data-x="ok"]').click()]);
  // the file's name goes with the header too: a title taken is asked about
  // next, and the name-conflict dialog says which file it is (tests/doclinks.mjs)
  if(JSON.stringify(uploads)!==JSON.stringify([{markdown:'# Owls\n\nhoot\n',check_header:true,name:'owls.md'},
      {markdown:'# Owls\n\nhoot\n',header:{title:'Owls',subtitle:'night birds',note:'',lang:'en',target:'fa'},name:'owls.md'}]))
    throw Error('the upload requests: '+JSON.stringify(uploads));
  // skipped: nothing more is sent, and the library stays
  await index.goto('http://parseh.test/');
  await index.setInputFiles('#file-upload',owls);
  await index.waitForSelector('.header-modal');
  await index.locator('.header-modal [data-x="skip"]').click();
  await index.waitForTimeout(200);
  if(uploads.length!==3||await index.locator('.header-modal').count()||new URL(index.url()).pathname!=='/')
    throw Error('a skipped file went on: '+JSON.stringify(uploads.slice(2)));
  // a complete header goes straight in, asked nothing
  await Promise.all([index.waitForURL('**/doc/owls-abc123'),index.setInputFiles('#file-upload',{name:'full.md',mimeType:'text/markdown',
    buffer:Buffer.from('---\ntitle: Owls\nsubtitle: s\nnote: n\nlang: en\ntarget: fa\nauthor: me\n---\n\nhoot\n')})]);
  if(uploads.length!==4||uploads[3].header||!uploads[3].check_header)throw Error('a complete header was asked about: '+JSON.stringify(uploads[3]));
  // a zip: each file with an incomplete header asked about in turn, one skipped
  await index.goto('http://parseh.test/');
  await index.setInputFiles('#file-upload',{name:'pack.zip',mimeType:'application/zip',buffer:Buffer.from('PK\x05\x06'+'\0'.repeat(18),'binary')});
  await index.waitForSelector('.header-modal');
  const zipAsk=await index.evaluate(()=>({head:document.querySelector('.header-modal h3').textContent,
    keys:[...document.querySelectorAll('.header-modal [data-key]')].map(i=>i.dataset.key),preview:document.querySelector('.header-preview').textContent}));
  if(zipAsk.head!=='“notes/bee.md, in pack.zip”: the header is incomplete'||zipAsk.keys.join()!=='subtitle,note'||zipAsk.preview!=='+ subtitle:\n+ note:')
    throw Error('the zip\'s first file is asked: '+JSON.stringify(zipAsk));
  await index.locator('.header-modal [data-key="subtitle"]').fill('bees');
  await index.locator('.header-modal [data-x="ok"]').click();
  await index.waitForFunction(()=>{const h=document.querySelector('.header-modal h3');return h&&h.textContent.startsWith('“c.md');});
  await index.locator('.header-modal [data-x="skip"]').click();
  await index.waitForFunction(()=>document.querySelector('#toast').textContent.includes('2 documents imported'));
  const zipToast=await index.locator('#toast').textContent();
  if(!zipToast.includes('notes/bee.md: images/gone.png is not in the zip'))throw Error('the zip import says: '+zipToast);
  if(JSON.stringify(zipPosts)!==JSON.stringify([null,JSON.stringify({'notes/bee.md':{subtitle:'bees',note:''},'c.md':null})]))
    throw Error('the zip requests: '+JSON.stringify(zipPosts));
  if(indexErrors.length)throw Error(indexErrors.join('\n'));
  console.log('uploads: a missing header asked for, a skipped file left, a complete header untouched, a zip file by file passed');

  const editor = await browser.newPage();
  const editorErrors=[]; editor.on('pageerror', e=>editorErrors.push(e.message));
  let editHtml=await Deno.readTextFile(root+'/markdown/app/templates/edit.html');
  const initial=`---\ntitle: Authoring\ntarget: ar\n---\n\n:::exercise single-choice\nprompt: Existing question\n- [x] answer\n- [ ] distractor\n:::`;
  const previewDoc=await renderedDoc(true, initial);
  // every {{KEY}} server.py's page_edit fills: STUDIO is the studio's own
  // prefix (empty here, where the studio is the whole site), PROSE_JSON the
  // `lang:` record, and the three that say there is no shelf of decks or notes
  const replacements={BASE:'',STUDIO:'',TITLE:'Authoring',DOC_ID:'',TARGET:'ar',MARKDOWN:initial,
    LANG_JSON:JSON.stringify(previewDoc.lang_record),LANGS_JSON:JSON.stringify([previewDoc.lang_record]),
    PROSE_JSON:JSON.stringify({code:'en',name:'English',native:'English',dir:'ltr',babel:'english',taught:true}),
    DECKS_BASE:'',NOTES_SOURCE:'',NAMES_MARK:'',...audioKeys};
  for(const [key,value] of Object.entries(replacements))editHtml=editHtml.replaceAll(`{{${key}}}`,()=>value);
  // a key the template gained and this page does not fill would be served as
  // literal braces, and a script path with braces in it is a file that is never found
  if(/\{\{[A-Z_]+\}\}/.test(editHtml))throw Error('edit template placeholder left: '+editHtml.match(/\{\{[A-Z_]+\}\}/)[0]);
  await editor.route('**/*',async route=>{
    const u=new URL(route.request().url());
    if(u.pathname==='/edit')return route.fulfill({body:editHtml,contentType:'text/html'});
    if(studioFile(route,u))return;
    if(u.pathname==='/api/preview'){
      const request=route.request().postDataJSON();
      return route.fulfill({json:{ok:true,doc:await renderedDoc(true,request.markdown)}});
    }
    if(u.pathname==='/api/exercise-decks')return route.fulfill({json:{decks:[{path:'arabic/known',name:'Known',language:'Arabic',cards:3}]}});
    if(u.pathname==='/api/exercise-prompt')return route.fulfill({json:{prompt:'complete prompt',vocabulary:3}});
    return route.fulfill({json:{}});
  });
  await editor.goto('http://parseh.test/edit');
  await editor.waitForSelector('.ex-edit');
  await editor.locator('.ex-edit').first().click();
  if(!await editor.locator('.ex-form-modal').count())throw Error('preview edit did not reopen visual exercise form');
  if(!await editor.locator('.ex-form-modal textarea').first().inputValue().then(v=>v.includes('Existing question')))throw Error('existing prompt missing from visual form');
  if(await editor.locator('.ex-form-modal textarea').evaluateAll(xs=>xs.some(x=>x.value.includes(':::exercise'))))throw Error('visual editor exposed raw exercise source');
  await editor.waitForSelector('.ex-form-preview [data-subtype="single-choice"]');
  if(await editor.locator('.ex-form-preview .ex-edit').count())throw Error('nested exercise preview exposed an edit control');
  if(!await editor.locator('.ex-form-preview-status').textContent().then(v=>v.includes('Correct answer shown')))
    throw Error('exercise form preview did not finish rendering');
  await editor.locator('.ex-form-modal [data-x="cancel"]').last().click();
  // the menu shuts as an entry is pressed (the dialog opens over it), so
  // every use of it opens it first, as a hand does
  const exMenu=async id=>{
    const d=editor.locator('details.dropdown').filter({has:editor.locator('#btn-exercise')});
    if(!await d.evaluate(e=>e.open))await d.locator('summary').click();
    await editor.locator(id).click();
  };
  await exMenu('#btn-exercise');
  const typeCount=await editor.locator('.ex-type').count();
  if(typeCount<12)throw Error('exercise type selection incomplete');
  // Every pedagogical type, including the three embedded-card forms, must
  // open a named-field editor rather than a fenced-Markdown textarea.
  for(let i=0;i<typeCount;i++){
    await editor.locator('.ex-type').nth(i).click();
    if(!await editor.locator('.ex-form-modal').count())throw Error(`exercise type ${i} did not open a form`);
    if(!await editor.locator('.ex-form-modal textarea,.ex-form-modal input,.ex-form-modal select').count())throw Error(`exercise type ${i} has no fields`);
    if(await editor.locator('.ex-form-modal textarea').evaluateAll(xs=>xs.some(x=>x.value.includes(':::exercise'))))throw Error(`exercise type ${i} exposed source`);
    await editor.locator('.ex-form-modal [data-x="cancel"]').last().click();
    await exMenu('#btn-exercise');
  }
  await editor.locator('.ex-type').filter({hasText:'Choose one'}).click();
  if(!await editor.locator('.ex-form-modal').count())throw Error('type did not open visual exercise editor');
  const choiceRows=editor.locator('.ex-form-modal .ex-form-row textarea');
  await choiceRows.nth(0).fill('Correct option');
  await choiceRows.nth(1).fill('Distractor');
  const why=editor.locator('.ex-form-section').filter({hasText:'Explanation after checking'}).locator('textarea');
  await why.nth(0).fill('You understood the distinction.');
  await why.nth(1).fill('Review the distinction in the note.');
  await editor.waitForFunction(() =>
    document.querySelector('.ex-form-preview-status')?.textContent.includes('Correct answer shown') &&
    document.querySelector('.ex-form-preview')?.textContent.includes('Correct option'));
  if(Deno.env.get('PARSEH_TEST_ARTIFACTS'))
    await editor.screenshot({path:Deno.env.get('PARSEH_TEST_ARTIFACTS')+'/exercise-editor.png',fullPage:true});
  await editor.locator('.ex-form-modal [data-x="save"]').click();
  const savedSource=await editor.locator('#src').inputValue();
  if(!savedSource.includes('prompt: Choose the correct answer.')||!savedSource.includes('- [x] Correct option'))throw Error('visual exercise was not serialized');
  if(!savedSource.includes('explanation-correct: You understood')||!savedSource.includes('explanation-incorrect: Review'))throw Error('separate explanations were not serialized');
  if((await renderedDoc(true, savedSource)).html.includes('Exercise needs attention'))throw Error('visual editor generated invalid exercise Markdown');
  await exMenu('#btn-exercise-prompt');
  await editor.waitForSelector('.ex-deck');
  if(!await editor.locator('.ex-deck').textContent().then(v=>v.includes('Known')))throw Error('Anki deck chooser missing');
  console.log('exercise authoring, re-edit, and optional Anki deck workflow passed');
  if(editorErrors.length)throw Error(editorErrors.join('\n'));

  // The form reads rows by the subtype, as mdparser does: a matching row
  // whose left side opens with a bracket ([x]{tl}) is still a pair, and a
  // `type:` field names the subtype when the opening line does not.
  const pairsPage = await browser.newPage();
  const pairsErrors=[]; pairsPage.on('pageerror', e=>pairsErrors.push(e.message));
  const pairsDoc=`---\ntitle: Pairs\ntarget: ar\n---\n\n:::exercise match-translations\nprompt: Match.\n- [سلام]{tl} => hello\n- [x]{tl} => the letter x\n:::\n\n:::exercise\ntype: true-false\nprompt: Judge.\n- The sky is green. => false\n:::\n\n:::exercise fill-blanks\nprompt: Complete.\ntext: [أنا هنا [[slot]]]{tl}\n- [slot] [الآن]{tl}\n- [ ] [غداً]{tl}\n:::`;
  if((await renderedDoc(true, pairsDoc)).html.includes('Exercise needs attention'))throw Error('pairs fixture is not valid');
  let pairsHtml=await Deno.readTextFile(root+'/markdown/app/templates/edit.html');
  for(const [key,value] of Object.entries(Object.assign({},replacements,{TITLE:'Pairs',MARKDOWN:pairsDoc})))
    pairsHtml=pairsHtml.replaceAll(`{{${key}}}`,()=>value);
  await pairsPage.route('**/*',async route=>{
    const u=new URL(route.request().url());
    if(u.pathname==='/edit')return route.fulfill({body:pairsHtml,contentType:'text/html'});
    if(studioFile(route,u))return;
    if(u.pathname==='/api/preview')
      return route.fulfill({json:{ok:true,doc:await renderedDoc(true,route.request().postDataJSON().markdown)}});
    return route.fulfill({json:{}});
  });
  await pairsPage.goto('http://parseh.test/edit');
  await pairsPage.waitForFunction(()=>document.querySelectorAll('#sheet .ex-edit').length===3);
  await pairsPage.locator('#sheet .ex-edit').nth(0).click();
  const pairValues=await pairsPage.locator('.ex-form-modal .ex-field-cols textarea').evaluateAll(xs=>xs.map(x=>x.value));
  if(JSON.stringify(pairValues)!==JSON.stringify(['[سلام]{tl}','hello','[x]{tl}','the letter x']))
    throw Error('bracketed left sides lost their pairs: '+JSON.stringify(pairValues));
  const directionFields = await pairsPage.evaluate(() => {
    const form = document.querySelector('.ex-form-modal');
    const boxes = [...form.querySelectorAll('.ex-author-field textarea, .ex-author-field input[type=text]')];
    const buttons = [...form.querySelectorAll('.ex-author-field > .ex-text-direction')];
    const prompt = form.querySelector('.ex-form-section textarea');
    const other = form.querySelector('.ex-field-cols textarea');
    const before = [prompt.value, other.value, other.dir];
    const toggle = prompt.closest('.ex-author-field').querySelector('.ex-text-direction');
    toggle.click();
    const rtl = prompt.dir === 'rtl' && getComputedStyle(prompt).direction === 'rtl'
      && other.dir === before[2] && prompt.value === before[0];
    toggle.click();
    return {boxes:boxes.length, buttons:buttons.length, rtl,
            restored:prompt.dir === 'ltr' && prompt.value === before[0] && other.value === before[1]};
  });
  if(!directionFields.boxes||directionFields.boxes!==directionFields.buttons
     ||!directionFields.rtl||!directionFields.restored)
    throw Error('each exercise text box needs an independent RTL/LTR switch: '+JSON.stringify(directionFields));
  await pairsPage.locator('.ex-form-section').filter({hasText:'Instructions'}).locator('textarea').fill('Match again.');
  await pairsPage.locator('.ex-form-modal [data-x="save"]').click();
  if(await pairsPage.locator('.ex-form-modal').count())throw Error('re-saving the pairs was refused');
  const pairsSource=await pairsPage.locator('#src').inputValue();
  for(const line of ['prompt: Match again.','- [سلام]{tl} => hello','- [x]{tl} => the letter x'])
    if(!pairsSource.includes(line))throw Error('re-saved pairs lack '+line);
  if((await renderedDoc(true, pairsSource)).html.includes('Exercise needs attention'))throw Error('re-saved pairs are invalid');
  await pairsPage.locator('#sheet .ex-edit').nth(1).click();
  if(!await pairsPage.locator('.ex-form-modal h3').textContent().then(t=>t.includes('True / False')))
    throw Error('a type: field did not name the subtype');
  if(await pairsPage.locator('.ex-form-modal .ex-form-row textarea').first().inputValue()!=='The sky is green.')
    throw Error('the type: exercise lost its statement');
  await pairsPage.locator('.ex-form-modal [data-x="cancel"]').last().click();

  // A BLANK INSIDE A TARGET-LANGUAGE MARK.  The sentence is written as one
  // marked sentence; the mark is spread over the pieces round the blank, so
  // the form shows a whole mark as the text that stays visible -- never the
  // bracket that opened it -- and the sentence is laid out right-to-left,
  // with the blank where it is read.
  const fillBox=await pairsPage.locator('#sheet .ex-fill').first();
  if(await fillBox.getAttribute('dir')!=='rtl')
    throw Error('a marked fill sentence is not laid out in the target direction');
  await pairsPage.locator('#sheet .ex-edit').nth(2).click();
  const fillValues=await pairsPage.locator('.ex-form-modal .ex-form-row textarea')
    .evaluateAll(xs=>xs.map(x=>x.value));
  if(!fillValues.includes('[أنا هنا]{tl} '))
    throw Error('the form broke the mark round the sentence: '+JSON.stringify(fillValues));
  await pairsPage.locator('.ex-form-modal [data-x="save"]').click();
  if(await pairsPage.locator('.ex-form-modal').count())throw Error('re-saving the fill was refused');
  const fillSource=await pairsPage.locator('#src').inputValue();
  if(!fillSource.includes('text: [أنا هنا]{tl} [[blank1]]'))
    throw Error('the re-saved sentence lost its mark: '+fillSource);
  if((await renderedDoc(true, fillSource)).html.includes('Exercise needs attention'))
    throw Error('the re-saved fill is invalid');
  console.log('bracketed pair rows, type: fields and a blank inside a mark survive the form passed');

  // the form as the decks use it: their markdown, their preview, an async save
  console.log(await pairsPage.evaluate(async()=>{
    const wait=ms=>new Promise(r=>setTimeout(r,ms));
    const until=async(test,what)=>{for(let i=0;i<150;i++){if(test())return;await wait(20);}throw Error('timed out: '+what);};
    const toastText=()=>document.querySelector('#toast').textContent;
    if(openExerciseMarkdown(':::exercise nonsense\n:::',{onSave:()=>{}})!==false||document.querySelector('.ex-form-modal'))
      throw Error('an unsupported exercise opened a form');
    if(!toastText().includes('not supported'))throw Error('an unsupported exercise was not reported');
    const saved=[]; let calls=0;
    const opened=openExerciseMarkdown('\n:::exercise single-choice\nprompt: Which?\n- [x] this\n- [ ] that\n:::\n',{
      preview:async markdown=>`<section class="exercise" data-exercise="1" data-subtype="single-choice" data-primitive="choice"><div class="ex-head"><span class="ex-kicker">Deck</span><button type="button" class="ex-to-deck">+ Deck</button></div><div class="ex-body">custom preview of ${markdown.split('\n')[0]}</div></section><p class="dropped">not the exercise</p>`,
      onSave:async markdown=>{calls++;await wait(40);if(calls===1)throw Error('the deck refused it');saved.push(markdown);},
      saveLabel:'Save to deck'});
    if(!opened)throw Error('a deck item did not open');
    await until(()=>document.querySelector('.ex-form-preview')?.textContent.includes('custom preview of :::exercise single-choice'),'custom preview');
    if(document.querySelector('.ex-form-preview .dropped,.ex-form-preview .ex-to-deck'))throw Error('the form kept more than the exercise');
    const save=document.querySelector('.ex-form-modal [data-x="save"]');
    if(save.textContent!=='Save to deck')throw Error('saveLabel ignored');
    save.click(); save.click();
    await until(()=>!save.disabled,'the first save settles');
    if(calls!==1)throw Error('a double click saved twice');
    if(!document.querySelector('.ex-form-modal'))throw Error('a refused save closed the form');
    if(!toastText().includes('the deck refused it'))throw Error('a refused save was not reported');
    save.click();
    await until(()=>!document.querySelector('.ex-form-modal'),'the second save closes the form');
    if(saved.length!==1||!saved[0].startsWith(':::exercise single-choice\n')||!saved[0].includes('- [x] this'))
      throw Error('saved markdown: '+saved[0]);
    openExercisePicker({onSave:markdown=>saved.push(markdown),preview:async()=>''});
    [...document.querySelectorAll('.ex-type')].find(b=>b.textContent.includes('Odd one out')).click();
    const head=document.querySelector('.ex-form-modal h3').textContent;
    if(head!=='Add Odd one out'||document.querySelector('.ex-form-modal [data-x="save"]').textContent!=='Insert exercise')
      throw Error('the picker opened '+head);
    document.querySelector('.ex-form-modal [data-x="cancel"]').click();
    return 'reusable exercise form (markdown, picker, async save) passed';
  }));
  if(pairsErrors.length)throw Error(pairsErrors.join('\n'));

  // a deck's form uploads a flashcard's pictures; the editor's (no option) stays paths only
  const openFlashcard=withUpload=>pairsPage.evaluate(withUpload=>{
    window.uploads=[]; window.previews=[];
    const opts={onSave:()=>{},preview:async markdown=>{previews.push(markdown);return '';}};
    if(withUpload)opts.uploadImage=async file=>{
      uploads.push(file.name); await new Promise(r=>setTimeout(r,30));
      if(file.name==='broken.png')throw Error('only PNG, JPEG, SVG and PDF figures are supported');
      return 'images/'+file.name.replace('.png','-2.png');
    };
    openExercisePicker(opts);
    [...document.querySelectorAll('.ex-type')].find(b=>b.textContent.includes('Embedded vocabulary flashcard')).click();
  },withUpload);
  const pickPicture=async name=>{
    const chooser=pairsPage.waitForEvent('filechooser',{timeout:5000});
    await pairsPage.locator('.ex-form-modal .ex-upload').first().click();
    await (await chooser).setFiles({name,mimeType:'image/png',buffer:Buffer.from([0x89,0x50,0x4e,0x47])});
  };
  await openFlashcard(true);
  if(await pairsPage.locator('.ex-form-modal .ex-upload').count()!==2)
    throw Error('picture fields with an Upload button: '+await pairsPage.locator('.ex-form-modal .ex-upload').count());
  if(await pairsPage.locator('.ex-form-modal input[type=file]').evaluateAll(xs=>xs.map(x=>x.accept+(x.hidden?'':' shown')).join())!=='.png,.jpg,.jpeg,.svg,.pdf,.png,.jpg,.jpeg,.svg,.pdf')
    throw Error('the picture pickers accept the wrong files, or show');
  const frontImage=pairsPage.locator('.ex-form-modal .ex-author-field').filter({hasText:'Front image path'}).locator('input:not([type=file])');
  await pickPicture('cat.png');
  await pairsPage.waitForFunction(()=>window.previews.some(m=>m.includes('front-image: images/cat-2.png')),null,{timeout:5000})
    .catch(()=>{throw Error('an uploaded picture did not reach the preview')});
  if(await frontImage.inputValue()!=='images/cat-2.png')throw Error('the uploaded picture path is not in its field: '+await frontImage.inputValue());
  await pickPicture('broken.png');
  await pairsPage.waitForFunction(()=>document.querySelector('#toast').textContent.includes('only PNG, JPEG'),null,{timeout:5000})
    .catch(()=>{throw Error('a refused upload was not reported')});
  await pairsPage.waitForFunction(()=>!document.querySelector('.ex-form-modal .ex-upload').disabled);
  if(!await pairsPage.locator('.ex-form-modal').count())throw Error('a refused upload closed the form');
  if(await frontImage.inputValue()!=='images/cat-2.png')throw Error('a refused upload changed the field');
  if(JSON.stringify(await pairsPage.evaluate(()=>window.uploads))!=='["cat.png","broken.png"]')throw Error('uploads: '+await pairsPage.evaluate(()=>JSON.stringify(window.uploads)));
  await pairsPage.locator('.ex-form-modal [data-x="cancel"]').last().click();
  await openFlashcard(false);
  if(await pairsPage.locator('.ex-form-modal .ex-upload, .ex-form-modal input[type=file]').count())throw Error('a form without uploadImage offers an upload');
  if(await pairsPage.locator('.ex-form-modal .ex-author-field').filter({hasText:'Front image path'}).locator('input').getAttribute('placeholder')!=='images/example.png')
    throw Error('the picture path field changed without uploadImage');
  await pairsPage.locator('.ex-form-modal [data-x="cancel"]').last().click();
  if(pairsErrors.length)throw Error(pairsErrors.join('\n'));
  console.log('flashcard pictures upload from the form (uploadImage) passed');

  // Every exercise but a flashcard carries two pictures of its own: one with
  // the question, one kept for the answer.  The form writes both, and the
  // page shows the second one only once the exercise has been answered.
  const picsDoc = `---
title: Pictures
target: ar
---

:::exercise single-choice
prompt: Where is it?
image: images/map.png {width=40 align=center}
image-answer: images/key.png
audio: audio/where.mp3 {start=2 end=4}
audio-answer: audio/answer.mp3
explanation-correct: Yes, north.
explanation-incorrect: No, north.
- [x] north
- [ ] south
:::`;
  // a real server: an <img> of an intercepted route never finishes loading
  const PNG_1PX = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==','base64');
  const picsHtml = (await renderedDoc(false,picsDoc,false,'/media/x/')).html;
  const picsServer = Deno.serve({port:0,hostname:'127.0.0.1',onListen:()=>{}}, req=>{
    const path=new URL(req.url).pathname;
    if(path==='/page')return new Response(`<!doctype html><html><head><link rel="stylesheet" href="/app.css"></head>
      <body data-page="noop"><article id="sheet" class="sheet" data-lang="ar">${picsHtml}</article>
      <div id="modal-root"></div><div id="toast" class="toast" hidden></div>
      <script src="/app.js"></script><script src="/exform.js"></script></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8'}});
    if(path==='/app.js')return new Response(appScript,{headers:{'Content-Type':'text/javascript'}});
    // the exercise form (openExercisePicker, openExerciseMarkdown) is exform.js's since the split
    if(path==='/exform.js')return new Response(studioFiles['/static/exform.js'][0],{headers:{'Content-Type':'text/javascript'}});
    if(path==='/app.css')return new Response(appCss,{headers:{'Content-Type':'text/css'}});
    if(/^\/media\/x\/images\/[a-z]+\.png$/.test(path))return new Response(PNG_1PX,{headers:{'Content-Type':'image/png'}});
    return new Response('no',{status:404});
  });
  const picsPage = await browser.newPage();
  const picsErrors=[]; picsPage.on('pageerror', e=>picsErrors.push(e.message));
  await picsPage.goto(`http://127.0.0.1:${picsServer.addr.port}/page`);
  console.log(await picsPage.evaluate(async()=>{
    const assert=(v,m)=>{if(!v)throw Error(m)};
    const wait=ms=>new Promise(r=>setTimeout(r,ms));
    bindExercises(document.querySelector('#sheet'));
    const ex=document.querySelector('.exercise');
    const shown=ex.querySelector('.ex-image-prompt'), answer=ex.querySelector('.ex-image-answer');
    const body=ex.querySelector('.ex-body'), why=ex.querySelector('[data-explanation-for="correct"]');
    const after=(a,b)=>!!(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING);
    assert(after(ex.querySelector('.ex-prompt'),shown)&&after(shown,body),'the question picture sits between the prompt and the activity');
    assert(after(body,answer)&&after(answer,why),'the answer picture sits after the activity and above the explanations');
    const drawn=async el=>{const img=el.querySelector('img');
      for(let i=0;i<100&&!(img.complete&&img.naturalWidth);i++)await wait(20);
      const r=img.getBoundingClientRect();
      return img.complete&&img.naturalWidth>0&&r.width>0&&r.height>0&&r.top<innerHeight;};
    assert(await drawn(shown),'the question picture is drawn');
    const img=shown.querySelector('img'), col=shown.getBoundingClientRect(), box=img.getBoundingClientRect();
    assert(Math.abs(box.width-col.width*0.4)<=3,`the question picture takes the width it asks for (${Math.round(box.width)} of ${Math.round(col.width)})`);
    assert(Math.abs((box.left-col.left)-(col.right-box.right))<=3,'and is centred in the column');
    const wide=answer.querySelector('img').getBoundingClientRect(), answerCol=answer.getBoundingClientRect();
    assert(Math.abs(wide.width-answerCol.width*0.6)<=3,`the answer picture, which says nothing, takes the 60% a figure takes (${Math.round(wide.width)} of ${Math.round(answerCol.width)})`);
    assert(wide.left-answerCol.left<=3,'and sits on the left, where a figure sits');
    assert(answer.hidden,'the answer picture is kept back until the exercise is answered');
    ex.querySelector('[data-correct="1"]').click();
    document.querySelector('.ex-correct-all').click();
    assert(!answer.hidden&&await drawn(answer),'a right answer shows the answer picture');
    assert(!why.hidden,'and its explanation');
    ex.querySelector('[data-correct="0"]').click();
    assert(answer.hidden,'changing the answer keeps it back again');
    document.querySelector('.ex-correct-all').click();
    assert(!answer.hidden,'a wrong answer shows it too');
    assert(!ex.querySelector('[data-explanation-for="incorrect"]').hidden&&why.hidden,'with the explanation of a wrong answer');
    // and the recordings, which are the same two fields over again
    const heard=ex.querySelector('.ex-audio-prompt'), heardAnswer=ex.querySelector('.ex-audio-answer');
    assert(after(shown,heard)&&after(heard,body),'the question recording sits with the question picture, before the activity');
    assert(after(body,heardAnswer)&&after(heardAnswer,why),'the answer recording sits after the activity and above the explanations');
    assert(heard.querySelector('audio').getAttribute('src').endsWith('#t=2,4'),'its clip is a media fragment');
    assert(heard.dataset.start==='2'&&heard.dataset.end==='4','and the box carries the window app.js stops at');
    assert(!heardAnswer.hidden,'a wrong answer shows the answer recording too');
    ex.querySelector('[data-correct="1"]').click();
    assert(heardAnswer.hidden&&answer.hidden,'changing the answer keeps both back again');
    return 'an exercise\'s own pictures and recordings: the question\'s drawn, the answer\'s kept back until it is answered either way passed';
  }));
  if(picsErrors.length)throw Error(picsErrors.join('\n'));

  // the form: both picture fields, uploaded like a card's, written into the markdown
  await picsPage.evaluate(()=>{
    window.saved=[]; window.previews=[];
    openExercisePicker({onSave:m=>{saved.push(m)},preview:async m=>{previews.push(m);return ''},
      uploadImage:async file=>({path:'images/'+file.name,url:'/media/x/images/'+file.name}),
      uploadAudio:async file=>({path:'audio/'+file.name,url:'/media/x/audio/'+file.name})});
    [...document.querySelectorAll('.ex-type')].find(b=>b.textContent.includes('Choose one answer')).click();
  });
  const picBox=label=>picsPage.locator('.ex-form-modal .ex-author-field').filter({hasText:label}).first();
  const picField=label=>picBox(label).locator('input[placeholder="images/example.png"]');
  if(await picsPage.locator('.ex-form-modal .ex-upload').count()!==4)
    throw Error('a scored exercise offers '+await picsPage.locator('.ex-form-modal .ex-upload').count()+' picture and recording uploads');
  for(const [i,[label,name]] of [['Picture with the question','map.png'],['Picture shown after the answer','key.png']].entries()){
    const chooser=picsPage.waitForEvent('filechooser',{timeout:5000});
    await picsPage.locator('.ex-form-modal .ex-upload').nth(i).click();
    await (await chooser).setFiles({name,mimeType:'image/png',buffer:PNG_1PX});
    await picsPage.waitForFunction(n=>window.previews.some(m=>m.includes(n)),'images/'+name,{timeout:5000})
      .catch(()=>{throw Error('an uploaded '+name+' did not reach the preview')});
    if(await picField(label).inputValue()!=='images/'+name)throw Error(label+': '+await picField(label).inputValue());
  }
  await picsPage.locator('.ex-form-modal .ex-author-field').filter({hasText:'Choice 1'}).locator('input,textarea').first().fill('north');
  await picsPage.locator('.ex-form-modal .ex-author-field').filter({hasText:'Choice 2'}).locator('input,textarea').first().fill('south');
  await picsPage.locator('.ex-form-modal .ex-correct-toggle input').first().click();
  await picField('Picture with the question').fill('map.png');
  await picsPage.locator('.ex-form-modal [data-x="save"]').last().click();
  await picsPage.waitForFunction(()=>document.querySelector('#toast').textContent.includes('under images/'),null,{timeout:5000})
    .catch(()=>{throw Error('a path that is not under images/ was accepted')});
  await picField('Picture with the question').fill('images/map.png');
  await picBox('Picture with the question').locator('.ex-field-style summary').click();
  const widthField=picBox('Picture with the question').locator('input[type=number]');
  if(await widthField.inputValue()!=='60')throw Error('a picture with nothing said starts at '+await widthField.inputValue()+'%');
  await widthField.fill('35');
  await picBox('Picture with the question').locator('select').selectOption('center');
  await picsPage.waitForFunction(()=>window.previews.some(m=>m.includes('{width=35 align=center}')),null,{timeout:5000})
    .catch(()=>{throw Error('the size and the side did not reach the preview')});
  await picsPage.locator('.ex-form-modal [data-x="save"]').last().click();
  await picsPage.waitForFunction(()=>window.saved.length===1,null,{timeout:5000});
  const savedPics=await picsPage.evaluate(()=>window.saved[0]);
  if(!/\nimage: images\/map\.png \{width=35 align=center\}\n/.test(savedPics)||!/\nimage-answer: images\/key\.png\n/.test(savedPics))
    throw Error('the form wrote: '+savedPics);
  // and reads them back: the block opened again shows what it says
  const reopened=await picsPage.evaluate(async md=>{
    openExerciseMarkdown(md,{onSave:()=>{},preview:async()=>''});
    await new Promise(r=>setTimeout(r,60));
    const box=[...document.querySelectorAll('.ex-form-modal .ex-author-field')]
      .find(l=>l.textContent.includes('Picture with the question'));
    return {path:box.querySelector('input[placeholder="images/example.png"]').value,
            width:box.querySelector('input[type=number]').value,
            align:box.querySelector('select').value};
  },savedPics);
  if(reopened.path!=='images/map.png'||reopened.width!=='35'||reopened.align!=='center')
    throw Error('the form read the layout back as '+JSON.stringify(reopened));
  await picsPage.locator('.ex-form-modal [data-x="cancel"]').last().click();

  // THE RECORDINGS ARE THE SAME TWO FIELDS OVER AGAIN, with one thing more
  // to say: the stretch of a longer file to play.
  await picsPage.evaluate(()=>{
    window.saved=[]; window.previews=[];
    openExercisePicker({onSave:m=>{saved.push(m)},preview:async m=>{previews.push(m);return ''},
      uploadImage:async file=>({path:'images/'+file.name,url:'/media/x/images/'+file.name}),
      uploadAudio:async file=>({path:'audio/'+file.name,url:'/media/x/audio/'+file.name})});
    [...document.querySelectorAll('.ex-type')].find(b=>b.textContent.includes('Choose one answer')).click();
  });
  const recBox=label=>picsPage.locator('.ex-form-modal .ex-author-field').filter({hasText:label}).first();
  const recField=label=>recBox(label).locator('input[placeholder="audio/example.mp3"]');
  const recChooser=picsPage.waitForEvent('filechooser',{timeout:5000});
  await picsPage.locator('.ex-form-modal .ex-upload').nth(2).click();
  await (await recChooser).setFiles({name:'where.mp3',mimeType:'audio/mpeg',buffer:Buffer.from('ID3')});
  await picsPage.waitForFunction(()=>window.previews.some(m=>m.includes('audio/where.mp3')),null,{timeout:5000})
    .catch(()=>{throw Error('an uploaded recording did not reach the preview')});
  if(await recField('Recording with the question').inputValue()!=='audio/where.mp3')
    throw Error('the upload did not fill the recording field');
  await picsPage.locator('.ex-form-modal .ex-author-field').filter({hasText:'Choice 1'}).locator('input,textarea').first().fill('north');
  await picsPage.locator('.ex-form-modal .ex-author-field').filter({hasText:'Choice 2'}).locator('input,textarea').first().fill('south');
  await picsPage.locator('.ex-form-modal .ex-correct-toggle input').first().click();
  await recField('Recording played after the answer').fill('where.mp3');
  await picsPage.locator('.ex-form-modal [data-x="save"]').last().click();
  await picsPage.waitForFunction(()=>document.querySelector('#toast').textContent.includes('under audio/'),null,{timeout:5000})
    .catch(()=>{throw Error('a path that is not under audio/ was accepted')});
  await recField('Recording played after the answer').fill('audio/slow.mp3');
  await recBox('Recording with the question').locator('.ex-field-style summary').click();
  const clipFrom=recBox('Recording with the question').locator('input[placeholder="1:05.2"]');
  await clipFrom.fill('1:05.2');
  await recBox('Recording with the question').locator('input[placeholder="1:09"]').fill('1:09');
  await picsPage.waitForFunction(()=>window.previews.some(m=>m.includes('{start=1:05.2 end=1:09}')),null,{timeout:5000})
    .catch(()=>{throw Error('the clip did not reach the preview')});
  await picsPage.locator('.ex-form-modal [data-x="save"]').last().click();
  await picsPage.waitForFunction(()=>window.saved.length===1,null,{timeout:5000});
  const savedRecs=await picsPage.evaluate(()=>window.saved[0]);
  if(!/\naudio: audio\/where\.mp3 \{start=1:05\.2 end=1:09\}\n/.test(savedRecs)||!/\naudio-answer: audio\/slow\.mp3\n/.test(savedRecs))
    throw Error('the form wrote: '+savedRecs);
  const reread=await picsPage.evaluate(async md=>{
    openExerciseMarkdown(md,{onSave:()=>{},preview:async()=>''});
    await new Promise(r=>setTimeout(r,60));
    const box=[...document.querySelectorAll('.ex-form-modal .ex-author-field')]
      .find(l=>l.textContent.includes('Recording with the question'));
    return {path:box.querySelector('input[placeholder="audio/example.mp3"]').value,
            from:box.querySelector('input[placeholder="1:05.2"]').value,
            to:box.querySelector('input[placeholder="1:09"]').value};
  },savedRecs);
  if(reread.path!=='audio/where.mp3'||reread.from!=='1:05.2'||reread.to!=='1:09')
    throw Error('the form read the clip back as '+JSON.stringify(reread));
  await picsPage.locator('.ex-form-modal [data-x="cancel"]').last().click();
  if(picsErrors.length)throw Error(picsErrors.join('\n'));
  await picsPage.close();
  await picsServer.shutdown();
  console.log('the picture and recording fields of a scored exercise upload from the form and are written into its markdown passed');

  // a flashcard's recordings: -audio fields beside the -image ones, each kind
  // with its own uploader and file picker, and a ▶ that plays what is named
  const pyRun = async (code, ...args) => {
    const out = await new Deno.Command(python, {args: ['-c', code, ...args], stdout: 'piped', stderr: 'piped'}).output();
    if (!out.success) throw Error(new TextDecoder().decode(out.stderr));
    return JSON.parse(new TextDecoder().decode(out.stdout));
  };
  const AUDIO_ACCEPT_PY = await pyRun(`import sys,json;sys.path.insert(0,'lib');import audiofile;print(json.dumps(audiofile.ACCEPT))`);
  const openCard = (label, withImage, withAudio) => pairsPage.evaluate(([label, withImage, withAudio]) => {
    window.uploads = []; window.previews = []; window.saved = null;
    const opts = {onSave: m => { window.saved = m; }, preview: async markdown => { previews.push(markdown); return ''; }};
    const fake = kind => async file => {
      uploads.push(kind + ':' + file.name); await new Promise(r => setTimeout(r, 20));
      if (file.name.startsWith('broken')) throw Error(kind === 'audio' ? 'only MP3, M4A, AAC, Ogg, Opus, WAV, FLAC and WebM recordings are supported' : 'only PNG, JPEG, SVG and PDF figures are supported');
      // an uploader may answer the path, or the path and where it is served
      return kind === 'audio' ? {path: 'audio/' + file.name, url: '/media/doc/audio/' + file.name} : 'images/' + file.name;
    };
    if (withImage) opts.uploadImage = fake('image');
    if (withAudio) opts.uploadAudio = fake('audio');
    openExercisePicker(opts);
    [...document.querySelectorAll('.ex-type')].find(b => b.textContent.includes(label)).click();
  }, [label, withImage, withAudio]);
  const MP3 = Buffer.from('ID3\x03\x00\x00\x00\x00\x00\x00 not really a recording', 'binary');
  const fieldOf = label => pairsPage.locator('.ex-form-modal .ex-author-field').filter({has: pairsPage.locator(`:scope > span:text-is("${label}")`)});
  const choose = async (button, name, mimeType) => {
    const chooser = pairsPage.waitForEvent('filechooser', {timeout: 5000});
    await button.click();
    await (await chooser).setFiles({name, mimeType, buffer: MP3});
  };
  await openCard('Embedded vocabulary flashcard', true, true);
  const pickers = await pairsPage.locator('.ex-form-modal input[type=file]').evaluateAll(xs => xs.map(x => x.accept + (x.hidden ? '' : ' shown')));
  if (JSON.stringify(pickers) !== JSON.stringify(['.png,.jpg,.jpeg,.svg,.pdf', '.png,.jpg,.jpeg,.svg,.pdf', AUDIO_ACCEPT_PY, AUDIO_ACCEPT_PY]))
    throw Error('the pickers of a card with both uploaders: ' + JSON.stringify(pickers) + ' (audiofile.ACCEPT is ' + AUDIO_ACCEPT_PY + ')');
  // what else app.js knows of recordings is made from that one list: a file
  // name a drop takes, and the path a card's recording field takes, answer
  // as lib/audiofile.py does for every extension it has and a few it has not
  const audioVerdicts = await pyRun(`import sys,json,re;sys.path.insert(0,'lib');import audiofile
names=[s+e for e in audiofile.EXTS for s in ('word.','Word.')]+['word.'+e.upper() for e in audiofile.EXTS]+['word.mp4','word.ogv','word.wma','word.mp3x','mp3','word.mp3.txt']
paths=['audio/'+n for n in names]+['images/word.mp3','audio/-word.mp3','audio/sub/word.mp3','sounds/word.mp3']
name_re=re.compile(r'\\.(?:%s)$' % '|'.join(audiofile.EXTS), re.I)
print(json.dumps({'names':[[n,bool(name_re.search(n))] for n in names],'paths':[[p,bool(audiofile.PATH_RE.match(p))] for p in paths]}))`);
  const audioVerdictsJs = await pairsPage.evaluate(py => ({
    names: py.names.map(([n]) => [n, AUDIO_NAME_RE.test(n)]),
    paths: py.paths.map(([p]) => {
      const model = {subtype: 'flashcard', cardType: 'vocab', fields: {target: 'x', 'front-audio': p}, rows: []};
      let refused = false;
      try { validateExercise(model, definitionFor(model)); } catch (e) { refused = e.message === 'front-audio must name a file under audio/ (e.g. audio/word.mp3)'; }
      return [p, !refused];
    }),
  }), audioVerdicts);
  if (JSON.stringify(audioVerdictsJs) !== JSON.stringify(audioVerdicts))
    throw Error('app.js and audiofile disagree about recordings: ' + JSON.stringify(audioVerdictsJs) + ' vs ' + JSON.stringify(audioVerdicts));
  if (await pairsPage.locator('.ex-form-modal .ex-upload').count() !== 4 || await pairsPage.locator('.ex-form-modal .ex-audio-play').count() !== 2)
    throw Error('a vocabulary card has 4 uploads and 2 players: ' + await pairsPage.locator('.ex-form-modal .ex-upload').count());
  const frontAudio = fieldOf('Front recording path');
  if (await frontAudio.locator('input:not([type=file])').getAttribute('placeholder') !== 'audio/example.mp3') throw Error('the recording field has no audio placeholder');
  if (await frontAudio.locator('details').count()) throw Error('a recording path has a text appearance');
  await choose(frontAudio.locator('.ex-upload'), 'word.mp3', 'audio/mpeg');
  await pairsPage.waitForFunction(() => window.previews.some(m => m.includes('front-audio: audio/word.mp3')), null, {timeout: 5000})
    .catch(() => { throw Error('an uploaded recording did not reach the preview'); });
  if (await frontAudio.locator('input:not([type=file])').inputValue() !== 'audio/word.mp3') throw Error('the uploaded recording is not in its field');
  await choose(fieldOf('Back recording path').locator('.ex-upload'), 'broken.mp3', 'audio/mpeg');
  await pairsPage.waitForFunction(() => document.querySelector('#toast').textContent.startsWith('Could not upload the recording: only MP3'), null, {timeout: 5000})
    .catch(async () => { throw Error('a refused recording was not reported: ' + await pairsPage.locator('#toast').textContent()); });
  if (JSON.stringify(await pairsPage.evaluate(() => window.uploads)) !== '["audio:word.mp3","audio:broken.mp3"]') throw Error('uploads: ' + await pairsPage.evaluate(() => JSON.stringify(window.uploads)));
  await fieldOf('Word or expression').locator('textarea').first().fill('[کتاب]{tl}');
  await fieldOf('Back recording path').locator('input:not([type=file])').fill('sounds/word.mp3');
  await pairsPage.locator('.ex-form-modal [data-x="save"]').click();
  await pairsPage.waitForFunction(() => document.querySelector('#toast').textContent === 'back-audio must name a file under audio/ (e.g. audio/word.mp3)')
    .catch(async () => { throw Error('a recording path outside audio/ was not refused: ' + await pairsPage.locator('#toast').textContent()); });
  await fieldOf('Back recording path').locator('input:not([type=file])').fill('');
  await pairsPage.locator('.ex-form-modal [data-x="save"]').click();
  await pairsPage.waitForFunction(() => window.saved);
  const vocabSaved = await pairsPage.evaluate(() => window.saved);
  if (!vocabSaved.includes('\nfront-audio: audio/word.mp3\n') || /-(audio|image)-(size|shade)/.test(vocabSaved)) throw Error('the saved card: ' + vocabSaved);
  await openCard('Embedded opposites flashcard', false, false);
  if (await pairsPage.locator('.ex-form-modal .ex-upload, .ex-form-modal input[type=file]').count() || await pairsPage.locator('.ex-form-modal .ex-audio-play').count() !== 2
      || !await fieldOf('Front recording path').count() || !await fieldOf('Back recording path').count())
    throw Error('an opposites card without uploaders: recording paths and players, no upload');
  await fieldOf('Front recording path').locator('.ex-audio-play').click();
  await pairsPage.waitForFunction(() => document.querySelector('#toast').textContent.includes('No recording named yet'))
    .catch(() => { throw Error('▶ with no path said nothing'); });
  await pairsPage.locator('.ex-form-modal [data-x="cancel"]').last().click();

  // a jolly card: four fields of markdown, "Image…" and "Recording…" put a line in at the cursor, one field a side is enough
  await openCard('Embedded Jolly flashcard', true, true);
  const jollyFields = await pairsPage.locator('.ex-form-modal .ex-author-field:has(> textarea.ex-jolly-text)').evaluateAll(xs => xs.map(x =>
    [x.querySelector(':scope > span').textContent, x.querySelector(':scope > small').textContent,
     x.querySelectorAll('.ex-insert-image').length, x.querySelectorAll('.ex-insert-audio').length]));
  const HELP = 'Any studio markdown: paragraphs, lists, tables, > boxes, images, recordings';
  if (JSON.stringify(jollyFields) !== JSON.stringify(['Front — primary text', 'Front — secondary text', 'Back — primary text', 'Back — secondary text'].map(l => [l, HELP, 1, 1])))
    throw Error('the jolly fields: ' + JSON.stringify(jollyFields));
  const frontPrimary = fieldOf('Front — primary text').locator('textarea');
  await frontPrimary.fill('### سلام\nsaid on arriving');
  await frontPrimary.evaluate(t => t.setSelectionRange(t.value.indexOf('\n'), t.value.indexOf('\n')));   // the end of the heading
  await choose(fieldOf('Front — primary text').locator('.ex-insert-audio'), 'word.mp3', 'audio/mpeg');
  await pairsPage.waitForFunction(() => document.querySelector('.ex-form-modal textarea.ex-jolly-text').value.includes('audio/'), null, {timeout: 5000});
  if (await frontPrimary.inputValue() !== '### سلام\n![](audio/word.mp3)\nsaid on arriving') throw Error('Recording… put in: ' + JSON.stringify(await frontPrimary.inputValue()));
  await frontPrimary.evaluate(t => t.setSelectionRange(t.value.length, t.value.length));
  await choose(fieldOf('Front — primary text').locator('.ex-insert-image'), 'cat.png', 'image/png');
  await pairsPage.waitForFunction(() => document.querySelector('.ex-form-modal textarea.ex-jolly-text').value.includes('images/'), null, {timeout: 5000});
  if (await frontPrimary.inputValue() !== '### سلام\n![](audio/word.mp3)\nsaid on arriving\n![](images/cat.png)') throw Error('Image… put in: ' + JSON.stringify(await frontPrimary.inputValue()));
  await pairsPage.evaluate(() => { document.querySelector('#toast').textContent = ''; });
  await pairsPage.locator('.ex-form-modal [data-x="save"]').click();
  await pairsPage.waitForFunction(() => document.querySelector('#toast').textContent === 'Fill in at least one field on the back')
    .catch(async () => { throw Error('a card with no back was not refused: ' + await pairsPage.locator('#toast').textContent()); });
  if (!await pairsPage.locator('.ex-form-modal').count()) throw Error('a refused card closed the form');
  await fieldOf('Back — secondary text').locator('textarea').fill('- hello\n    - hi there\n\n| a | b |\n|---|---|\n| 1 | 2 |');
  await pairsPage.locator('.ex-form-modal [data-x="save"]').click();
  await pairsPage.waitForFunction(() => window.saved);
  const jollySaved = await pairsPage.evaluate(() => window.saved);
  const jollyParsed = await pyRun(`import sys,json;sys.path[:0]=['markdown/exlex','lib'];import mdparser;b=mdparser.parse(sys.argv[1])[1][-1];print(json.dumps([b['errors'],b['raw_fields']]))`, jollySaved);
  if (jollyParsed[0].length || jollyParsed[1]['front-primary'] !== '### سلام\n![](audio/word.mp3)\nsaid on arriving\n![](images/cat.png)'
      || jollyParsed[1]['back-secondary'] !== '- hello\n    - hi there\n\n| a | b |\n|---|---|\n| 1 | 2 |' || jollySaved.includes('front-secondary') || jollySaved.includes('back-primary'))
    throw Error('the jolly card saved with one field a side: ' + jollySaved + '\n' + JSON.stringify(jollyParsed));
  if (pairsErrors.length) throw Error(pairsErrors.join('\n'));
  console.log('flashcard recordings and jolly markdown in the form (uploadAudio, Image… and Recording…, one field a side) passed');

  // `key: |` read alike by the form and by mdparser: Python's dedent, not "strip two spaces"
  const blockSource = [':::exercise flashcard', 'card-type: jolly',
    'front-primary: |', '    ### سلام', '    ![](audio/word.mp3){width=50 align=center offset=0}', '',
    'back-primary: |', '    **hello**', '  ', '    | Persian | English |', '    |---|---|', '    | سلام | hello |', '',
    '    - said on arriving', '    - answered', '        - nested once', '          and continued', '\t',
    'back-secondary: |', '\t- a tab-indented list', '\t- second', ':::'].join('\n');
  const pyCard = text => pyRun(`import sys,json;sys.path[:0]=['markdown/exlex','markdown/app','lib'];import mdparser,htmlgen
b=mdparser.parse(sys.argv[1])[1][-1];h=htmlgen.render_document('---\\ntitle: t\\ntarget: fa\\n---\\n\\n'+sys.argv[1],asset_base='/m/')['html']
print(json.dumps({'errors':b['errors'],'raw':b['raw_fields'],'card':h[h.index('<div class="ex-flashcard'):h.index('<small class="ex-card-hint">')]}))`, text);
  const fromPython = await pyCard(blockSource);
  const roundTrip = await pairsPage.evaluate(text => {
    const model = parseExerciseSource(text);
    const fields = Object.assign({}, model.fields);
    const {model: prepared, def} = prepareExerciseModel(parseExerciseSource(text));
    const out = exerciseSource(prepared, def);
    return {fields, out, again: parseExerciseSource(out).fields};
  }, blockSource);
  const fromPythonAgain = await pyCard(roundTrip.out);
  for (const key of ['front-primary', 'back-primary', 'back-secondary']) {
    if (roundTrip.fields[key] !== fromPython.raw[key]) throw Error(`the form reads ${key} otherwise than mdparser: ${JSON.stringify(roundTrip.fields[key])} vs ${JSON.stringify(fromPython.raw[key])}`);
    if (roundTrip.again[key] !== fromPython.raw[key]) throw Error(`${key} changed on its way through the form: ${JSON.stringify(roundTrip.again[key])}`);
  }
  if (fromPython.errors.length || fromPythonAgain.errors.length || JSON.stringify(fromPythonAgain.raw) !== JSON.stringify(fromPython.raw))
    throw Error('mdparser reads the form\'s card otherwise: ' + JSON.stringify([fromPython, fromPythonAgain]));
  if (fromPythonAgain.card !== fromPython.card) throw Error('the card the form wrote renders otherwise:\n' + fromPython.card + '\n' + fromPythonAgain.card);
  if (!fromPython.card.includes('<ul><li>said on arriving</li><li>answered<ul><li>nested once')) throw Error('the nested list did not nest: ' + fromPython.card);
  console.log('a `key: |` block (nested list, table, tabs, blank lines) round-trips through the form as mdparser reads it passed');

  const sentenceDirection = await pairsPage.evaluate(() => {
    const text = ':::exercise construct-sentence\ncontent-direction: ltr\nanswer-direction: rtl\n- [1] one\n- [2] two\n:::';
    const {model, def} = prepareExerciseModel(parseExerciseSource(text));
    const saved = exerciseSource(model, def);
    return {saved, fields:parseExerciseSource(saved).fields};
  });
  if(!sentenceDirection.saved.includes('answer-direction: rtl')
     ||sentenceDirection.fields['answer-direction']!=='rtl'
     ||sentenceDirection.fields['content-direction']!=='ltr')
    throw Error('the form lost the separate sentence answer direction: '+JSON.stringify(sentenceDirection));

  // Correct an existing answer that was entered in the opposite reading order.
  await pairsPage.evaluate(() => {
    window.reverseSaved = null;
    openExerciseMarkdown(':::exercise construct-sentence\nprompt: Make a sentence.\n- [1] first\n- [2] middle\n- [3] last\n:::',
      {onSave: markdown => { window.reverseSaved = markdown; }, preview: async () => ''});
  });
  const correctOrder = pairsPage.locator('.ex-form-section').filter({hasText:'Words or chunks in the correct order'});
  await correctOrder.getByRole('button', {name:'Reverse order'}).click();
  const reversedFields = await correctOrder.locator('.ex-form-row textarea').evaluateAll(inputs => inputs.map(input => input.value));
  if (JSON.stringify(reversedFields) !== JSON.stringify(['last', 'middle', 'first']))
    throw Error('reversing the correct answer showed '+JSON.stringify(reversedFields));
  await pairsPage.locator('.ex-form-modal [data-x="save"]').click();
  await pairsPage.waitForFunction(() => window.reverseSaved !== null);
  const reversedSource = await pairsPage.evaluate(() => window.reverseSaved);
  if (!reversedSource.includes('- [1] last\n- [2] middle\n- [3] first'))
    throw Error('reversing the correct answer saved '+reversedSource);
  console.log('reversing the correct order of an existing construct-sentence exercise passed');

  // a jolly field written by hand simply going on over the lines under it,
  // no `|` in sight: the form must read it as mdparser reads it
  const carriedOn = [':::exercise flashcard', 'card-type: jolly',
    'front-primary: 今日は', 'いい 天気ですね',
    'front-secondary: kyō wa ii tenki desu ne',
    'back-primary: It is fine weather today.', '',
    '| word | meaning |', '|---|---|', '| 天気 | weather |',
    'back-secondary: b', ':::'].join('\n');
  const carriedPython = await pyCard(carriedOn);
  const carriedForm = await pairsPage.evaluate(text => {
    const model = parseExerciseSource(text);
    const {model: prepared, def} = prepareExerciseModel(parseExerciseSource(text));
    return {fields: Object.assign({}, model.fields), out: exerciseSource(prepared, def)};
  }, carriedOn);
  if (carriedPython.errors.length) throw Error('mdparser refused the card: ' + JSON.stringify(carriedPython.errors));
  for (const [key, want] of [['front-primary', '今日は\nいい 天気ですね'],
                             ['front-secondary', 'kyō wa ii tenki desu ne'],
                             ['back-primary', 'It is fine weather today.\n\n| word | meaning |\n|---|---|\n| 天気 | weather |']]) {
    if ((carriedPython.raw[key] || carriedPython.fields?.[key]) !== want && key !== 'front-secondary')
      throw Error(`mdparser read ${key} as ${JSON.stringify(carriedPython.raw[key])}`);
    if (carriedForm.fields[key] !== want)
      throw Error(`the form read ${key} as ${JSON.stringify(carriedForm.fields[key])}, not ${JSON.stringify(want)}`);
  }
  // and writing it back gives the same card, now with its `|` blocks
  const carriedAgain = await pyCard(carriedForm.out);
  if (carriedAgain.errors.length || carriedAgain.card !== carriedPython.card)
    throw Error('the card written back renders otherwise:\n' + carriedPython.card + '\n' + carriedAgain.card);
  if (!carriedPython.card.includes('<table')) throw Error('the hand-written table did not draw: ' + carriedPython.card);
  console.log('a jolly field written by hand over several lines, without `|`, reads and writes back the same passed');

  // "+ Deck" on a document page, against a stand-in for the deck API
  const docPage = await browser.newPage();
  const docErrors=[]; docPage.on('pageerror', e=>docErrors.push(e.message));
  docPage.on('dialog', d=>d.accept());
  const docRender=await renderedDoc(false, md, true);
  const docMeta={id:'browser-doc-abc123',uid:'0123456789ab',title:'Browser exercises',tags:[],
    created:'2026-09-01T10:00:00',updated:'2026-09-01T10:00:00',build:{status:'none'}};
  let docHtml=await Deno.readTextFile(root+'/markdown/app/templates/doc.html');
  const docMap={...pageSnippets,BASE:'',STUDIO:'',DECKS_BASE:'/exercises',NOTES_SOURCE:'',LIVE:'',LIVE_SCRIPT:'',DOC_ID:docMeta.id,TITLE:docMeta.title,TARGET:'ar',TARGET_NAME:'Arabic',
    LANG:'en',ARTICLE:docRender.html,TOC:'',BACKLINKS:'',BACKLINKS_N:'0',META_JSON:JSON.stringify(docMeta),LANG_JSON:JSON.stringify(docRender.lang_record),
    LANGS_JSON:JSON.stringify([docRender.lang_record]),
    GLOSSES_JSON:JSON.stringify([{fa:'كتاب',kana:'',translit:'kitāb',tr:'book',guessed:false,lemma:false}])};
  // the same page as a note beside a book, whose decks read it from that shelf
  let notesHtml=docHtml, plainHtml=docHtml;
  for(const [key,value] of Object.entries(docMap))docHtml=docHtml.replaceAll(`{{${key}}}`,()=>value);
  // and a page no deck store answers for
  for(const [key,value] of Object.entries(Object.assign({},docMap,{DECKS_BASE:''})))
    plainHtml=plainHtml.replaceAll(`{{${key}}}`,()=>value);
  for(const [key,value] of Object.entries(Object.assign({},docMap,{BASE:'/books/arabic/grammar/notes',
      NOTES_SOURCE:'/books/arabic/grammar/notes'})))notesHtml=notesHtml.replaceAll(`{{${key}}}`,()=>value);
  if(/\{\{[A-Z_]+\}\}/.test(docHtml))throw Error('doc template placeholder left: '+docHtml.match(/\{\{[A-Z_]+\}\}/)[0]);
  const deckCalls=[];
  const deckList=[
    {id:'aaaaaaaaaaaa',name:'Arabic basics',lang:'ar',folder:'arabic',slug:'arabic-basics',path:'arabic/arabic-basics',counts:{total:2}},
    {id:'bbbbbbbbbbbb',name:'Verbs',lang:'ar',folder:'arabic',slug:'verbs',path:'arabic/verbs',counts:{total:1}},
  ];
  await docPage.route('**/*',async route=>{
    const req=route.request(), u=new URL(req.url());
    if(u.pathname==='/doc')return route.fulfill({body:docHtml,contentType:'text/html'});
    if(u.pathname==='/plain')return route.fulfill({body:plainHtml,contentType:'text/html'});
    if(u.pathname==='/books/arabic/grammar/notes/doc')return route.fulfill({body:notesHtml,contentType:'text/html'});
    const asset=u.pathname.replace(/^\/books\/arabic\/grammar\/notes(?=\/)/,'');
    if(studioFile(route,u,asset))return;
    if(asset==='/api/tags')return route.fulfill({json:{tags:[]}});
    if(u.pathname.startsWith('/exercises/')){
      const body=req.postData()?req.postDataJSON():null;
      deckCalls.push({method:req.method(),path:u.pathname+u.search,body});
      if(req.method()==='GET'&&u.pathname==='/exercises/api/decks')return route.fulfill({json:{ok:true,decks:deckList}});
      if(req.method()==='POST'&&u.pathname==='/exercises/api/decks'){
        const slug=body.name.toLowerCase().replace(/\s+/g,'-');
        return route.fulfill({status:201,json:{ok:true,deck:{id:'cccccccccccc',name:body.name,lang:body.lang,folder:'arabic',slug,path:'arabic/'+slug,counts:{total:0}}}});
      }
      if(req.method()==='DELETE'&&/^\/exercises\/api\/decks\/arabic\/(new-one|refused|kept|bulk-new)$/.test(u.pathname))
        return route.fulfill(u.pathname.endsWith('/kept')?{status:500,json:{ok:false,error:'disk full'}}:{json:{ok:true}});
      if(u.pathname==='/exercises/api/decks/arabic/verbs/copy')
        return route.fulfill(body.force
          ?{status:201,json:{ok:true,item:{id:'dddddddddddd'},warnings:['images/cat.png is missing'],deck:{name:'Verbs'}}}
          :{status:409,json:{ok:false,error:'already in this deck',conflict:'duplicate'}});
      if(u.pathname==='/exercises/api/decks/arabic/new-one/copy')
        return route.fulfill({status:409,json:{ok:false,error:'the document changed',conflict:'stale'}});
      if(/^\/exercises\/api\/decks\/arabic\/(refused|kept)\/copy$/.test(u.pathname))
        return route.fulfill({status:400,json:{ok:false,error:'the exercise needs attention: no answer'}});
      if(u.pathname==='/exercises/api/decks/arabic/arabic-basics/copy')
        return route.fulfill({status:201,json:{ok:true,item:{id:'eeeeeeeeeeee'},warnings:[],deck:{name:'Arabic basics'}}});
      // "+ Add all exercises": the second exercise is in the deck already, the
      // fourth is refused, the flashcard's picture is missing
      if(u.pathname==='/exercises/api/decks/arabic/bulk/copy'){
        if(body.ordinal===2&&!body.force)return route.fulfill({status:409,json:{ok:false,error:'already in this deck',conflict:'duplicate'}});
        if(body.ordinal===4)return route.fulfill({status:400,json:{ok:false,error:'the exercise needs attention: no answer'}});
        return route.fulfill({status:201,json:{ok:true,item:{id:'ffffffffffff'},
          warnings:body.ordinal===6?['images/cat.png is missing']:[],deck:{name:'Bulk'}}});
      }
      if(u.pathname==='/exercises/api/decks/arabic/bulk-new/copy')
        return route.fulfill({status:409,json:{ok:false,error:'the document changed',conflict:'stale'}});
      return route.fulfill({status:404,json:{ok:false,error:'no such endpoint'}});
    }
    return route.fulfill({json:{}});
  });
  await docPage.goto('http://parseh.test/doc');
  await docPage.waitForSelector('#sheet .ex-to-deck');
  const deckCounts=await docPage.evaluate(()=>['.exercise','.ex-to-deck','.ex-edit'].map(s=>document.querySelectorAll('#sheet '+s).length).join());
  if(deckCounts!=='6,6,0')throw Error('exercises, + Deck buttons, edit buttons: '+deckCounts);
  const flash=docPage.locator('#sheet [data-subtype="flashcard"]');
  await flash.locator('.ex-to-deck').click();
  await docPage.waitForSelector('.ex-to-deck-modal select option[value="arabic/verbs"]',{state:'attached'});
  if(await flash.locator('.ex-flashcard.flipped').count())throw Error('+ Deck flipped the card it sits on');
  if(!deckCalls.some(c=>c.method==='GET'&&c.path==='/exercises/api/decks?lang=ar'))throw Error('the decks were not asked for in the page language');
  if(await docPage.locator('.ex-to-deck-modal select').inputValue()!=='arabic/arabic-basics')throw Error('the first deck is not preselected');
  if(!await docPage.locator('.ex-to-deck-modal [data-x="new-field"]').isHidden())throw Error('a new-deck name is asked for an existing deck');
  await docPage.locator('.ex-to-deck-modal select').selectOption('arabic/verbs');
  await docPage.locator('.ex-to-deck-modal [data-x="copy"]').click();
  await docPage.waitForFunction(()=>!document.querySelector('.ex-to-deck-modal'));
  const copied=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/verbs/copy').map(c=>JSON.stringify(c.body));
  const wanted={doc_id:'browser-doc-abc123',ordinal:6,subtype:'flashcard',updated:'2026-09-01T10:00:00'};
  if(copied.join('|')!==[JSON.stringify(wanted),JSON.stringify(Object.assign({},wanted,{force:true}))].join('|'))
    throw Error('copy requests: '+copied.join(' | '));
  const copiedToast=await docPage.locator('#toast').textContent();
  if(!copiedToast.includes('Copied into “Verbs”')||!copiedToast.includes('images/cat.png is missing'))throw Error('copy toast: '+copiedToast);
  if(await docPage.evaluate(()=>localStorage.getItem('parseh_deck_last_ar'))!=='arabic/verbs')throw Error('the last deck is not remembered');
  const single=docPage.locator('#sheet [data-subtype="single-choice"]');
  await single.locator('.ex-to-deck').click();
  await docPage.waitForSelector('.ex-to-deck-modal select option[value="arabic/verbs"]',{state:'attached'});
  if(await docPage.locator('.ex-to-deck-modal select').inputValue()!=='arabic/verbs')throw Error('the last used deck is not preselected');
  await docPage.locator('.ex-to-deck-modal select').selectOption('');
  await docPage.locator('.ex-to-deck-modal [data-x="copy"]').click();
  await docPage.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Give the new deck a name'));
  if(deckCalls.some(c=>c.method==='POST'&&c.path==='/exercises/api/decks'))throw Error('a nameless deck was created');
  await docPage.locator('.ex-to-deck-modal [data-x="name"]').fill('New one');
  await docPage.locator('.ex-to-deck-modal [data-x="copy"]').click();
  await docPage.waitForFunction(()=>!document.querySelector('.ex-to-deck-modal'));
  const created=deckCalls.filter(c=>c.method==='POST'&&c.path==='/exercises/api/decks');
  if(created.length!==1||JSON.stringify(created[0].body)!==JSON.stringify({name:'New one',lang:'ar'}))throw Error('deck creation: '+JSON.stringify(created));
  const staleCopy=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/new-one/copy');
  if(staleCopy.length!==1||staleCopy[0].body.ordinal!==2||staleCopy[0].body.subtype!=='single-choice')throw Error('stale copy: '+JSON.stringify(staleCopy));
  if(!(await docPage.locator('#toast').textContent()).includes('out of date — reload it, then copy'))throw Error('a stale copy was not reported');
  if(await single.locator('.ex-option.selected').count())throw Error('+ Deck answered the exercise it sits on');
  // the deck made for that copy is gone again, and only after the copy failed
  const deletes=()=>deckCalls.filter(c=>c.method==='DELETE').map(c=>c.path);
  if(deletes().join()!=='/exercises/api/decks/arabic/new-one')throw Error('the deck made for a stale copy was not removed: '+deletes().join());
  if(deckCalls.findIndex(c=>c.method==='DELETE')<deckCalls.findIndex(c=>c.path==='/exercises/api/decks/arabic/new-one/copy'))
    throw Error('the new deck was removed before its copy was tried');
  // a refused copy into a new deck: the deck goes, the modal stays, back to "+ New deck"
  const modalSelect=docPage.locator('.ex-to-deck-modal select');
  const copyButton=docPage.locator('.ex-to-deck-modal [data-x="copy"]');
  const settled=()=>docPage.waitForFunction(()=>{const b=document.querySelector('.ex-to-deck-modal [data-x="copy"]');return b&&!b.disabled;});
  await docPage.locator('#sheet [data-subtype="fill-blanks"] .ex-to-deck').click();
  await docPage.waitForSelector('.ex-to-deck-modal select option[value="arabic/verbs"]',{state:'attached'});
  await modalSelect.selectOption('');
  await docPage.locator('.ex-to-deck-modal [data-x="name"]').fill('Refused');
  await copyButton.click();
  await docPage.waitForFunction(()=>document.querySelector('#toast').textContent.includes('needs attention'));
  await settled();
  if(!await docPage.locator('.ex-to-deck-modal').count())throw Error('a refused copy closed the modal');
  if(!deletes().includes('/exercises/api/decks/arabic/refused'))throw Error('the deck made for a refused copy was not removed');
  if(await docPage.locator('.ex-to-deck-modal select option[value="arabic/refused"]').count())throw Error('the removed deck is still offered');
  if(await modalSelect.inputValue()!=='')throw Error('the deck select did not go back to + New deck: '+await modalSelect.inputValue());
  if(await docPage.locator('.ex-to-deck-modal [data-x="new-field"]').isHidden())throw Error('the new-deck name is hidden after a refusal');
  // a deck that cannot be removed stays selected, so a retry makes no second one
  await docPage.locator('.ex-to-deck-modal [data-x="name"]').fill('Kept');
  await docPage.evaluate(()=>{document.querySelector('#toast').textContent='';});
  await copyButton.click();
  await docPage.waitForFunction(()=>document.querySelector('#toast').textContent.includes('needs attention'));
  await settled();
  if(await modalSelect.inputValue()!=='arabic/kept')throw Error('a deck that could not be removed was unselected');
  await copyButton.click();
  await docPage.waitForTimeout(150); await settled();
  const keptMade=deckCalls.filter(c=>c.method==='POST'&&c.path==='/exercises/api/decks'&&c.body.name==='Kept').length;
  const keptCopies=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/kept/copy').length;
  if(keptMade!==1||keptCopies!==2)throw Error(`a retry after a failed removal: ${keptMade} decks made, ${keptCopies} copies`);
  if(deletes().filter(p=>p.endsWith('/kept')).length!==1)throw Error('an existing deck was removed on a retry');
  await docPage.locator('.ex-to-deck-modal [data-x="cancel"]').click();
  if(docErrors.length)throw Error(docErrors.join('\n'));
  console.log('+ Deck removes a deck it made for a copy that failed passed');

  // the same page as a note beside a book: the copy names the shelf it reads from
  await docPage.goto('http://parseh.test/books/arabic/grammar/notes/doc');
  await docPage.waitForSelector('#sheet .ex-to-deck');
  await docPage.locator('#sheet [data-subtype="choose-all"] .ex-to-deck').click();
  await docPage.waitForSelector('.ex-to-deck-modal select option[value="arabic/arabic-basics"]',{state:'attached'});
  await modalSelect.selectOption('arabic/arabic-basics');
  await copyButton.click();
  await docPage.waitForFunction(()=>!document.querySelector('.ex-to-deck-modal'));
  const fromNotes=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/arabic-basics/copy').map(c=>JSON.stringify(c.body));
  const wantedNotes={doc_id:'browser-doc-abc123',ordinal:3,subtype:'choose-all',updated:'2026-09-01T10:00:00',source:'/books/arabic/grammar/notes'};
  if(fromNotes.join('|')!==JSON.stringify(wantedNotes))throw Error('copy from a note: '+fromNotes.join(' | '));
  if(docErrors.length)throw Error(docErrors.join('\n'));
  console.log('+ Deck copy from a document page passed');

  // "+ Add all exercises" on a note: the copies name the shelf they read from
  const allModal=docPage.locator('.ex-all-modal');
  const openAll=async deck=>{
    await docPage.locator('#btn-add-all').click();
    await docPage.waitForSelector(`.ex-all-modal select option[value="${deck}"]`,{state:'attached'});
  };
  await docPage.waitForSelector('#btn-add-all:not([hidden])');
  await openAll('arabic/arabic-basics');
  await allModal.locator('[data-x="none"]').click();
  await allModal.locator('.ex-all-item').first().locator('input').check();
  await allModal.locator('select').selectOption('arabic/arabic-basics');
  await allModal.locator('[data-x="add"]').click();
  await docPage.waitForFunction(()=>!document.querySelector('.ex-all-modal'));
  const notesAll=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/arabic-basics/copy').pop().body;
  if(JSON.stringify(notesAll)!==JSON.stringify({doc_id:'browser-doc-abc123',ordinal:1,subtype:'fill-blanks',
      updated:'2026-09-01T10:00:00',source:'/books/arabic/grammar/notes'}))throw Error('add all from a note: '+JSON.stringify(notesAll));

  // on a document: every exercise listed, in the page's order, all ticked
  deckList.push({id:'ffffffffffff',name:'Bulk',lang:'ar',folder:'arabic',slug:'bulk',path:'arabic/bulk',counts:{total:0}});
  await docPage.goto('http://parseh.test/doc');
  await docPage.waitForSelector('#btn-add-all:not([hidden])');
  await openAll('arabic/bulk');
  const listed=await docPage.evaluate(()=>[...document.querySelectorAll('.ex-all-modal .ex-all-item:not([hidden])')].map(r=>
    [r.querySelector('input').checked,r.querySelector('.ex-all-num').textContent,r.querySelector('.ex-all-kind').textContent,r.querySelector('.ex-all-text').textContent]));
  if(listed.length!==6||!listed.every(r=>r[0]))throw Error('every exercise listed and ticked: '+JSON.stringify(listed));
  if(listed.map(r=>r[1]).join()!=='1,2,3,4,5,6')throw Error('the list is not in the page order: '+JSON.stringify(listed));
  if(listed[1][2]!==await docPage.locator('#sheet [data-subtype="single-choice"] .ex-kicker').textContent()
     ||listed[1][3]!=='Pick one.'||!listed[5][3].includes('سؤال'))
    throw Error('each exercise is named by its kind and its prompt or its card: '+JSON.stringify(listed));
  const addButton=allModal.locator('[data-x="add"]'), counted=()=>allModal.locator('[data-x="count"]').textContent();
  if(await addButton.textContent()!=='Add 6 exercises'||await counted()!=='6 of 6 selected')throw Error('all six to add: '+await addButton.textContent());
  await allModal.locator('[data-x="none"]').click();
  if(await addButton.textContent()!=='Add 0 exercises'||!await addButton.isDisabled())throw Error('nothing ticked, and still something to add');
  await allModal.locator('[data-x="all"]').click();
  await allModal.locator('.ex-all-item').nth(2).locator('input').uncheck();
  if(await counted()!=='5 of 6 selected'||await addButton.textContent()!=='Add 5 exercises')throw Error('one unticked: '+await counted());
  await allModal.locator('select').selectOption('arabic/bulk');
  await addButton.click();
  await docPage.waitForFunction(()=>!document.querySelector('.ex-all-modal'));
  const bulk=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/bulk/copy').map(c=>c.body);
  if(bulk.map(b=>b.ordinal+':'+b.subtype).join()!=='1:fill-blanks,2:single-choice,4:match-translations,5:construct-sentence,6:flashcard'
     ||bulk.some(b=>b.force||b.source||b.updated!=='2026-09-01T10:00:00'||b.doc_id!=='browser-doc-abc123'))
    throw Error('add all requests, the unticked one left out: '+JSON.stringify(bulk));
  const bulkToast=await docPage.locator('#toast').textContent();
  for(const want of ['Added 3 exercises to “Bulk”','1 already there, left out','1 refused (4: the exercise needs attention: no answer)','images/cat.png is missing'])
    if(!bulkToast.includes(want))throw Error(`the add all confirmation lacks "${want}": ${bulkToast}`);
  if(await docPage.evaluate(()=>localStorage.getItem('parseh_deck_last_ar'))!=='arabic/bulk')throw Error('add all does not remember its deck');

  // the one already there: left out, the dialog stays; then added again
  await openAll('arabic/bulk');
  if(await allModal.locator('select').inputValue()!=='arabic/bulk')throw Error('add all does not preselect the last deck');
  await allModal.locator('[data-x="none"]').click();
  await allModal.locator('.ex-all-item').nth(1).locator('input').check();
  await addButton.click();
  await docPage.waitForFunction(()=>document.querySelector('#toast').textContent.includes('already in “Bulk” — tick “Add again”'));
  await docPage.waitForFunction(()=>{const b=document.querySelector('.ex-all-modal [data-x="add"]');return b&&!b.disabled;});
  await allModal.locator('[data-x="again"]').check();
  await addButton.click();
  await docPage.waitForFunction(()=>!document.querySelector('.ex-all-modal'));
  const again=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/bulk/copy').slice(-2).map(c=>[c.body.ordinal,!!c.body.force]);
  if(JSON.stringify(again)!=='[[2,false],[2,true]]')throw Error('adding again: '+JSON.stringify(again));
  if(!(await docPage.locator('#toast').textContent()).includes('Added 1 exercise to “Bulk”'))throw Error('the add again confirmation');

  // into a new deck, from a page gone stale: the run stops at once, and the deck it made goes
  await openAll('arabic/bulk');
  await allModal.locator('select').selectOption('');
  await allModal.locator('[data-x="name"]').fill('Bulk new');
  await addButton.click();
  await docPage.waitForFunction(()=>!document.querySelector('.ex-all-modal'));
  const staleRun=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/bulk-new/copy');
  if(staleRun.length!==1||staleRun[0].body.ordinal!==1)throw Error('a stale page does not stop the run: '+JSON.stringify(staleRun));
  if(!deletes().includes('/exercises/api/decks/arabic/bulk-new'))throw Error('the deck made for a run that added nothing was not removed');
  if(!(await docPage.locator('#toast').textContent()).includes('out of date — reload it, then add'))throw Error('a stale run was not reported');

  // an exercise that needs attention has no + Deck, and is not offered
  await docPage.evaluate(()=>document.querySelector('#sheet [data-subtype="choose-all"] .ex-to-deck').remove());
  await openAll('arabic/bulk');
  const offeredNow=await docPage.evaluate(()=>[document.querySelectorAll('.ex-all-modal .ex-all-item:not([hidden])').length,
    document.querySelector('.ex-all-modal p').textContent]);
  if(offeredNow[0]!==5||!offeredNow[1].includes('1 exercise that needs attention is not offered'))
    throw Error('an exercise without + Deck: '+JSON.stringify(offeredNow));
  await allModal.locator('[data-x="cancel"]').click();
  if(await allModal.count())throw Error('cancel left the dialog open');

  // The gloss cards are optional rows, copied through the same deck picker.
  await openAll('arabic/bulk');
  if(await allModal.locator('.ex-all-item:not([hidden])').count()!==5)
    throw Error('gloss flashcards were included before asking for them');
  await allModal.locator('[data-x="glosses"]').click();
  if(await allModal.locator('.ex-all-item:not([hidden])').count()!==6
     ||await allModal.locator('.ex-all-item').last().locator('.ex-all-kind').textContent()!=='Gloss flashcard')
    throw Error('Show gloss flashcards did not reveal the gloss row');
  await allModal.locator('[data-x="none"]').click();
  await allModal.locator('.ex-all-item').last().locator('input').check();
  await allModal.locator('select').selectOption('arabic/bulk');
  await addButton.click();
  await docPage.waitForFunction(()=>!document.querySelector('.ex-all-modal'));
  const glossCopy=deckCalls.filter(c=>c.path==='/exercises/api/decks/arabic/bulk/copy').at(-1).body;
  if(glossCopy.subtype!=='gloss-flashcard'||glossCopy.ordinal!==1
     ||glossCopy.doc_id!=='browser-doc-abc123'||glossCopy.updated!=='2026-09-01T10:00:00')
    throw Error('gloss flashcard copy payload: '+JSON.stringify(glossCopy));

  // and no button where no deck store answers
  await docPage.goto('http://parseh.test/plain');
  await docPage.waitForSelector('#sheet .exercise');
  if(!await docPage.locator('#btn-add-all').isHidden())throw Error('+ Add all exercises shown where no deck store answers');
  if(docErrors.length)throw Error(docErrors.join('\n'));
  console.log('+ Add all exercises: listed and ticked, unticked left out, duplicates and refusals counted, adding again, a stale run stopped, no button without decks passed');

  // ---------------- (D) cards that hold blocks and recordings ----------------
  // A REAL HTTP SERVER, not an intercepted route: a recording is fetched with
  // a Range header, and media answered by a route fulfilment never finishes
  // loading (readyState stays 0), so nothing about playing could be seen.
  const MEDIA_DIR = await Deno.makeTempDir({prefix: 'parseh-cards-'});
  const ffmpeg = async (...args) => {
    const o = await new Deno.Command('ffmpeg', {args: ['-y', '-loglevel', 'error', ...args], stdout: 'piped', stderr: 'piped'}).output();
    if (!o.success) throw Error('ffmpeg: ' + new TextDecoder().decode(o.stderr));
  };
  await ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=440:duration=4', '-c:a', 'libmp3lame', `${MEDIA_DIR}/word.mp3`);
  await ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=660:duration=4', '-c:a', 'libmp3lame', `${MEDIA_DIR}/other.mp3`);
  const cardsMd = `---
title: Cards with recordings
target: fa
---

![A recording on the page](audio/word.mp3){width=50 align=center offset=0}

:::exercise flashcard
card-type: jolly
front-primary: |
  ### سلام
  ![](audio/word.mp3)

  [ A Latin block on the card ]{la}
front-secondary: salâm
back-primary: |
  **hello**, the everyday greeting, as [the dictionary](https://example.org/) says.

  | Persian | English |
  |---|---|
  | سلام | hello |
  | خداحافظ | goodbye |

  - said on arriving
  - answered with سلام too
      - or with علیک سلام
back-secondary: |
  ![A recording on the back](audio/other.mp3){width=80 align=center offset=0}
:::

:::exercise flashcard
card-type: vocab
target: خداحافظ
meaning: goodbye
front-audio: audio/other.mp3
back-audio: audio/word.mp3
:::`;
  const renderWithMedia = async (text, preview) => {
    const code = `import sys,json;sys.path[:0]=['markdown/exlex','markdown/app','lib'];import htmlgen;print(json.dumps(htmlgen.render_document(sys.argv[1],asset_base='/media/',editor_preview=${preview ? 'True' : 'False'})['html']))`;
    const out = await new Deno.Command(python, {args: ['-c', code, text], stdout: 'piped', stderr: 'piped'}).output();
    if (!out.success) throw Error(new TextDecoder().decode(out.stderr));
    return JSON.parse(new TextDecoder().decode(out.stdout));
  };
  const cardsHtml = await renderWithMedia(cardsMd, false), cardsPreviewHtml = await renderWithMedia(cardsMd, true);
  const cardsPage = html => `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/langs.css"></head>
    <body data-page="cards"><main class="readpane"><article id="sheet" class="sheet" lang="en" data-lang="fa">${html}</article></main>
    <div id="modal-root"></div><div id="toast" class="toast" hidden></div>
    <script src="/app.js"></script><script>
      const sheet = document.querySelector('#sheet');
      window.__saves = [];
      bindImageLayout(sheet, {save: async s => { __saves.push(['figure', s]); }});
      bindLaLayout(sheet, {save: async s => { __saves.push(['la', s]); }});
      bindExercises(sheet, {preview: location.search === '?preview'});
    </script></body></html>`;
  const mediaServer = Deno.serve({port: 0, hostname: '127.0.0.1', onListen: () => {}}, async req => {
    const path = new URL(req.url).pathname;
    if (path === '/cards') return new Response(cardsPage(new URL(req.url).search === '?preview' ? cardsPreviewHtml : cardsHtml), {headers: {'Content-Type': 'text/html; charset=utf-8'}});
    if (path === '/app.js') return new Response(appScript, {headers: {'Content-Type': 'text/javascript'}});
    if (path === '/app.css') return new Response(appCss, {headers: {'Content-Type': 'text/css'}});
    if (path === '/langs.css') return new Response(langsCss, {headers: {'Content-Type': 'text/css'}});
    const m = /^\/media\/audio\/([a-z]+\.mp3)$/.exec(path);
    if (!m) return new Response('no', {status: 404});
    const bytes = await Deno.readFile(`${MEDIA_DIR}/${m[1]}`);
    const range = /bytes=(\d+)-(\d*)/.exec(req.headers.get('range') || '');
    if (range) {
      const from = +range[1], to = range[2] ? Math.min(+range[2], bytes.length - 1) : bytes.length - 1;
      return new Response(bytes.slice(from, to + 1), {status: 206, headers: {'Content-Type': 'audio/mpeg',
        'Accept-Ranges': 'bytes', 'Content-Range': `bytes ${from}-${to}/${bytes.length}`}});
    }
    return new Response(bytes, {headers: {'Content-Type': 'audio/mpeg', 'Accept-Ranges': 'bytes'}});
  });
  try {
    const cards = await browser.newPage({viewport: {width: 1100, height: 900}});
    const cardErrors = []; cards.on('pageerror', e => cardErrors.push(e.message));
    const cardsUrl = `http://127.0.0.1:${mediaServer.addr.port}/cards`;
    await cards.goto(cardsUrl);
    // a link on a card opens nothing here: the test stays on its page
    await cards.evaluate(() => document.addEventListener('click', e => { if (e.target.closest('a')) e.preventDefault(); }, true));
    const jolly = cards.locator('#sheet .ex-flashcard[data-card-type="jolly"]'), vocab = cards.locator('#sheet .ex-flashcard[data-card-type="vocab"]');
    const state = card => card.evaluate(c => ({flipped: c.classList.contains('flipped'), pressed: c.getAttribute('aria-pressed'),
      front: !c.querySelector(':scope > .ex-card-front').hidden, back: !c.querySelector(':scope > .ex-card-back').hidden,
      hint: c.querySelector(':scope > .ex-card-hint').textContent}));
    const markup = await cards.evaluate(() => ({buttons: document.querySelectorAll('button.ex-flashcard').length,
      cards: [...document.querySelectorAll('.ex-flashcard')].map(c => [c.tagName, c.getAttribute('role'), c.tabIndex, c.querySelectorAll(':scope > .ex-card-hint').length])}));
    if (markup.buttons || JSON.stringify(markup.cards) !== JSON.stringify([['DIV', 'button', 0, 1], ['DIV', 'button', 0, 1]]))
      throw Error('the cards are not focusable divs with a hint: ' + JSON.stringify(markup));

    // laid out on the page: the blocks at the page's weight and size, a player inside its figure
    const frontLayout = await jolly.evaluate(c => {
      const field = c.querySelector('.ex-card-front .ex-card-blocks'), fig = field.querySelector('figure.audio');
      const r = x => x.getBoundingClientRect();
      const inside = (a, b) => r(a).left >= r(b).left - 1 && r(a).right <= r(b).right + 1 && r(a).top >= r(b).top - 1 && r(a).bottom <= r(b).bottom + 1;
      return {weight: getComputedStyle(field).fontWeight, size: parseFloat(getComputedStyle(field).fontSize),
        cardSize: parseFloat(getComputedStyle(c).fontSize), align: getComputedStyle(field).textAlign,
        audioInFigure: inside(fig.querySelector('audio'), fig), figureInCard: inside(fig, c), fieldInCard: inside(field, c),
        audioWidth: r(fig.querySelector('audio')).width, figureWidth: r(fig).width};
    });
    if (frontLayout.weight !== '400' || Math.abs(frontLayout.size - frontLayout.cardSize) > 0.5 || frontLayout.align !== 'start')
      throw Error('a primary field of blocks is not at the page text weight and size: ' + JSON.stringify(frontLayout));
    if (!frontLayout.audioInFigure || !frontLayout.figureInCard || !frontLayout.fieldInCard || Math.abs(frontLayout.audioWidth - frontLayout.figureWidth) > 1)
      throw Error('the recording does not fit its figure on the card: ' + JSON.stringify(frontLayout));
    const oneLine = await vocab.evaluate(c => getComputedStyle(c.querySelector('.ex-card-field.primary')).fontWeight);
    if (oneLine !== '700') throw Error('a one-line primary field lost its weight: ' + oneLine);

    // 🔊 plays its recording and does not turn the card
    const vocabAudio = () => vocab.evaluate(c => { const a = c.querySelector('.ex-card-front audio'); return {paused: a.paused, ready: a.readyState, t: a.currentTime}; });
    await vocab.locator('.ex-card-front .ex-card-play').click();
    await cards.waitForFunction(() => { const a = document.querySelector('#sheet [data-card-type="vocab"] .ex-card-front audio'); return !a.paused && a.readyState >= 2 && a.currentTime > 0.1; }, null, {timeout: 8000})
      .catch(async () => { throw Error('🔊 did not play its recording: ' + JSON.stringify(await vocabAudio())); });
    if ((await state(vocab)).flipped) throw Error('🔊 turned the card');
    if (!await vocab.locator('.ex-card-front .ex-card-play').evaluate(b => b.classList.contains('playing'))) throw Error('🔊 does not show it is playing');
    // the player on the jolly card: a real click on its play control plays it, turns nothing, and hushes the other card
    const jollyPlayer = jolly.locator('.ex-card-front figure.audio audio');
    const box = await jollyPlayer.boundingBox();
    await cards.mouse.click(box.x + 20, box.y + box.height / 2);
    await cards.waitForFunction(() => !document.querySelector('#sheet [data-card-type="jolly"] .ex-card-front audio').paused, null, {timeout: 8000})
      .catch(() => { throw Error('a click on the card\'s player did not play it'); });
    if ((await state(jolly)).flipped) throw Error('a click on a player turned the card');
    await cards.waitForFunction(() => document.querySelector('#sheet [data-card-type="vocab"] .ex-card-front audio').paused, null, {timeout: 3000})
      .catch(() => { throw Error('two cards speak at once'); });
    if (await vocab.locator('.ex-card-front .ex-card-play').evaluate(b => b.classList.contains('playing'))) throw Error('a paused 🔊 still shows playing');
    // a click on the words turns it, and what played on the side now hidden stops
    await jolly.locator('.ex-card-front h3').click();
    let st = await state(jolly);
    if (!st.flipped || st.front || !st.back || st.pressed !== 'true' || st.hint !== 'tap to see front') throw Error('a click on the card did not turn it: ' + JSON.stringify(st));
    if (!await jolly.evaluate(c => c.querySelector('.ex-card-front audio').paused)) throw Error('the hidden side still plays');
    // the back: a table, a link and a player -- the link and the player are theirs, the table turns it
    const back = await jolly.evaluate(c => {
      const b = c.querySelector('.ex-card-back'), r = x => x.getBoundingClientRect();
      const inside = (a, o) => r(a).left >= r(o).left - 1 && r(a).right <= r(o).right + 1;
      const p = getComputedStyle(b.querySelector('.ex-card-blocks > p')), td = getComputedStyle(b.querySelector('td'));
      return {table: inside(b.querySelector('table'), c), list: inside(b.querySelector('ul ul'), c), figure: inside(b.querySelector('figure.audio'), c),
        tableWeight: td.fontWeight,
        // a paragraph of the field against a cell of the same field: size, colour, space under it
        paragraph: [+(parseFloat(p.fontSize) / parseFloat(td.fontSize)).toFixed(2), p.color === td.color, +(parseFloat(p.marginBottom) / parseFloat(p.fontSize)).toFixed(2)]};
    });
    if (!back.table || !back.list || !back.figure || back.tableWeight !== '400') throw Error('the back is not laid out inside the card: ' + JSON.stringify(back));
    if (back.paragraph[0] !== 1 || !back.paragraph[1] || !(back.paragraph[2] > 0.5)) throw Error('the back\'s paragraph is not the page\'s text: ' + JSON.stringify(back));
    await jolly.locator('.ex-card-back a').click();
    if (!(await state(jolly)).flipped) throw Error('a click on a link turned the card');
    const backPlayer = jolly.locator('.ex-card-back figure.audio audio');
    const bb = await backPlayer.boundingBox();
    await cards.mouse.click(bb.x + 20, bb.y + bb.height / 2);
    await cards.waitForFunction(() => !document.querySelector('#sheet [data-card-type="jolly"] .ex-card-back audio').paused, null, {timeout: 8000})
      .catch(() => { throw Error('the player on the back did not play'); });
    if (!(await state(jolly)).flipped) throw Error('a link or a player on the back turned the card');
    await jolly.locator('.ex-card-back td').first().click();
    st = await state(jolly);
    if (st.flipped || !st.front || st.back || st.hint !== 'tap to reveal') throw Error('a click on the table did not turn the card: ' + JSON.stringify(st));
    if (!await jolly.evaluate(c => c.querySelector('.ex-card-back audio').paused)) throw Error('the back went out of sight still playing');

    // the keys: Enter and Space on the card itself turn it, without scrolling; Enter on its 🔊 plays
    await jolly.focus();
    const scrolled = await cards.evaluate(() => scrollY);
    await cards.keyboard.press('Enter');
    if (!(await state(jolly)).flipped) throw Error('Enter did not turn the focused card');
    await cards.keyboard.press(' ');
    if ((await state(jolly)).flipped || await cards.evaluate(() => scrollY) !== scrolled) throw Error('Space did not turn the card, or scrolled the page');
    await vocab.locator('.ex-card-front .ex-card-play').focus();
    await cards.keyboard.press('Enter');
    await cards.waitForFunction(() => !document.querySelector('#sheet [data-card-type="vocab"] .ex-card-front audio').paused, null, {timeout: 8000})
      .catch(() => { throw Error('Enter on 🔊 did not play'); });
    if ((await state(vocab)).flipped) throw Error('Enter on 🔊 turned the card');
    const ring = await jolly.evaluate(c => { c.focus(); return getComputedStyle(c).outlineStyle; });
    await cards.keyboard.press('Tab'); await cards.keyboard.press('Shift+Tab');
    const focusRing = await cards.evaluate(() => { const c = document.activeElement; return c.classList.contains('ex-flashcard') ? getComputedStyle(c).outlineStyle + ' ' + getComputedStyle(c).outlineWidth : 'focus on ' + c.className; });
    if (!/^solid [1-9]/.test(focusRing)) throw Error('a card reached with the keyboard shows no focus ring: ' + focusRing + ' (' + ring + ')');

    // ⤢ Enlarge: the originals hushed, the copy with players of its own under the same rules
    await vocab.locator('.ex-card-front .ex-card-play').evaluate(b => b.closest('.ex-flashcard').querySelector('.ex-card-front audio').paused || true);
    await cards.locator('[data-exercise="2"] .ex-card-zoom').click();
    await cards.waitForSelector('.ex-zoom-overlay .ex-flashcard');
    if (!await vocab.evaluate(c => [...c.querySelectorAll('audio')].every(a => a.paused))) throw Error('Enlarge left the card on the page playing');
    const bigPlay = cards.locator('.ex-zoom-overlay .ex-card-front .ex-card-play');
    if (await bigPlay.evaluate(b => b.classList.contains('playing'))) throw Error('the copy says it plays before it does');
    await bigPlay.click();
    await cards.waitForFunction(() => { const a = document.querySelector('.ex-zoom-overlay .ex-card-front audio'); return a && !a.paused && a.readyState >= 2; }, null, {timeout: 8000})
      .catch(() => { throw Error('🔊 on the enlarged card did not play'); });
    if (await cards.locator('.ex-zoom-overlay .ex-flashcard.flipped').count() || (await state(vocab)).flipped) throw Error('🔊 on the enlarged card turned it');
    if (!await vocab.evaluate(c => c.querySelector('.ex-card-front audio').paused)) throw Error('the copy played the card on the page');
    await cards.keyboard.press(' ');
    if (!(await state(vocab)).flipped || !await cards.locator('.ex-zoom-overlay .ex-flashcard.flipped').count()) throw Error('Space did not turn the enlarged card');
    if (await cards.evaluate(() => [...document.querySelectorAll('.ex-zoom-overlay audio')].some(a => !a.paused))) throw Error('the turned copy still plays its front');
    await cards.keyboard.press('Escape');
    // the jolly card enlarged: a table and a player on it, the player plays and turns nothing
    await cards.locator('[data-exercise="1"] .ex-card-zoom').click();
    await cards.waitForSelector('.ex-zoom-overlay .ex-flashcard');
    const zoomed = await cards.evaluate(() => {
      const c = document.querySelector('.ex-zoom-overlay .ex-flashcard'), r = x => x.getBoundingClientRect();
      const f = c.querySelector('.ex-card-front figure.audio');
      return {figure: !!f, fits: f && r(f.querySelector('audio')).right <= r(f).right + 1 && r(f).right <= r(c).right + 1,
        window: r(document.querySelector('.ex-zoom-modal')).width >= innerWidth * 0.9};
    });
    if (!zoomed.figure || !zoomed.fits || !zoomed.window) throw Error('the enlarged jolly card: ' + JSON.stringify(zoomed));
    // a player just drawn takes a moment to lay its controls out
    await cards.waitForFunction(() => document.querySelector('.ex-zoom-overlay .ex-card-front audio').readyState >= 1);
    await cards.waitForTimeout(400);
    const zp = await cards.locator('.ex-zoom-overlay .ex-card-front figure.audio audio').boundingBox();
    await cards.mouse.click(zp.x + 20, zp.y + zp.height / 2);
    await cards.waitForFunction(() => !document.querySelector('.ex-zoom-overlay .ex-card-front audio').paused, null, {timeout: 8000})
      .catch(async () => { throw Error('the player on the enlarged jolly card did not play ' + JSON.stringify(zp) + JSON.stringify(await cards.evaluate(() => { const a = document.querySelector('.ex-zoom-overlay .ex-card-front audio'); const e = document.elementFromPoint(a.getBoundingClientRect().x + 20, a.getBoundingClientRect().y + 20); return [a.readyState, a.paused, e && e.tagName, e && e.className]; }))); });
    if (await cards.locator('.ex-zoom-overlay .ex-flashcard.flipped').count()) throw Error('a player on the enlarged card turned it');
    // the keyboard on that player: Space plays it, as on the page, turns nothing, and the page underneath hears nothing
    await cards.evaluate(() => {
      document.querySelector('.ex-zoom-overlay .ex-card-front audio').pause();
      window.__pageKeys = 0;
      document.addEventListener('keydown', () => { window.__pageKeys++; });
      window.addEventListener('keydown', () => { window.__pageKeys++; });
    });
    await cards.locator('.ex-zoom-overlay .ex-card-front figure.audio audio').focus();
    await cards.keyboard.press(' ');
    await cards.waitForFunction(() => !document.querySelector('.ex-zoom-overlay .ex-card-front audio').paused, null, {timeout: 8000})
      .catch(async () => { throw Error('Space on the focused player of the enlarged card did not play it (focus on ' + await cards.evaluate(() => document.activeElement.tagName) + ')'); });
    if (await cards.locator('.ex-zoom-overlay .ex-flashcard.flipped').count() || (await state(jolly)).flipped) throw Error('Space on a player of the enlarged card turned it');
    if (await cards.evaluate(() => window.__pageKeys)) throw Error('a key on a player of the enlarged card reached the page underneath');
    await cards.locator('.ex-zoom-overlay .ex-card-front h3').click();
    if (!await cards.locator('.ex-zoom-overlay .ex-flashcard.flipped').count() || !(await state(jolly)).flipped) throw Error('a click on the enlarged words did not turn it');
    if (await cards.evaluate(() => [...document.querySelectorAll('.ex-zoom-overlay audio')].some(a => !a.paused))) throw Error('the turned copy still plays its front');
    await cards.keyboard.press(' ');
    if (await cards.evaluate(() => window.__pageKeys)) throw Error('Space on the enlarged card reached the page underneath');
    await cards.keyboard.press(' ');
    // enlarged, the back's paragraph is drawn as on the page: a dialog's own grey small print is not the card's
    const bigBack = await cards.evaluate(() => {
      const b = document.querySelector('.ex-zoom-overlay .ex-card-back');
      const p = getComputedStyle(b.querySelector('.ex-card-blocks > p')), td = getComputedStyle(b.querySelector('td'));
      return [+(parseFloat(p.fontSize) / parseFloat(td.fontSize)).toFixed(2), p.color === td.color, +(parseFloat(p.marginBottom) / parseFloat(p.fontSize)).toFixed(2)];
    });
    if (JSON.stringify(bigBack) !== JSON.stringify(back.paragraph))
      throw Error('the enlarged back\'s paragraph is not drawn as on the page: ' + JSON.stringify(bigBack) + ' on the page ' + JSON.stringify(back.paragraph));
    await cards.keyboard.press('Escape');
    if (cardErrors.length) throw Error(cardErrors.join('\n'));

    // the page's layout panels: a recording on the page opens its own from ⚙ (a clip in
    // hundredths); a Latin block or a player on a card opens none -- a click there turns the card
    if ((await state(jolly)).flipped) { await jolly.focus(); await cards.keyboard.press('Enter'); }
    const panelShown = () => cards.evaluate(() => [...document.querySelectorAll('.imgpanel')].some(p => p.style.display === 'block'));
    await jolly.locator('.ex-card-front .la-par').click();
    if (await panelShown() || !(await state(jolly)).flipped) throw Error('a Latin block on a card opened a layout panel, or did not turn the card');
    if (await cards.locator('.ex-flashcard .audio-edit, .ex-flashcard .video-edit, .ex-flashcard figure[data-idx]').count())
      throw Error('a figure on a card has a layout handle or index');
    const pageFigure = cards.locator('#sheet > figure.audio');
    await pageFigure.hover();
    await pageFigure.locator('.audio-edit').click();
    if (!await panelShown() || await cards.locator('.imgpanel .panel-head span').first().textContent() !== 'Recording layout'
        || await cards.locator('.imgpanel .times-row').first().isHidden())
      throw Error('⚙ on a recording on the page did not open its layout panel with a clip');
    await cards.locator('.imgpanel [data-t="start"]').fill('1:00.5');
    await cards.locator('.imgpanel [data-t="start"]').press('Tab');
    await cards.waitForFunction(() => __saves.length === 1);
    const figureSave = await cards.evaluate(() => __saves[0]);
    if (JSON.stringify(figureSave) !== JSON.stringify(['figure', {index: 0, width: 50, align: 'center', offset: 0, start: 60.5, end: null}])
        || await cards.locator('.imgpanel [data-t="start"]').inputValue() !== '1:00.5'
        || !(await pageFigure.locator('audio').getAttribute('src')).endsWith('/media/audio/word.mp3#t=60.5'))
      throw Error('a recording\'s clip start in hundredths: ' + JSON.stringify(figureSave));
    await cards.locator('.imgpanel [data-t="end"]').fill('1:00.5.5');
    await cards.locator('.imgpanel [data-t="end"]').press('Tab');
    if (!(await cards.locator('#toast').textContent()).startsWith('Time as seconds or m:ss, to the hundredth (e.g. 65.25 or 1:05.25)')) throw Error('a bad time was not refused');
    await cards.keyboard.press('Escape');
    if (await cards.evaluate(() => __saves.some(s => s[0] === 'la'))) throw Error('a Latin block on a card was saved');

    // a phone: every side, table, list and player inside its card; the editor's preview with both sides
    for (const [url, what] of [[cardsUrl, 'page'], [cardsUrl + '?preview', 'preview']]) {
      const phone = await browser.newPage({viewport: {width: 400, height: 800}});
      await phone.goto(url);
      const out = await phone.evaluate(() => {
        const bad = [];
        document.querySelectorAll('.ex-flashcard').forEach((c, i) => {
          const cr = c.getBoundingClientRect();
          if (cr.right > innerWidth + 1) bad.push(`card ${i} wider than the window`);
          c.querySelectorAll('.ex-card-front, .ex-card-back, .ex-card-field, table, ul, figure, audio, .ex-card-play').forEach(x => {
            if (x.closest('[hidden]') || !x.getClientRects().length) return;   // a card's own <audio> has no box
            const r = x.getBoundingClientRect();
            if (r.left < cr.left - 1 || r.right > cr.right + 1) bad.push(`card ${i} ${x.tagName}.${x.className}: ${r.left}-${r.right} not in ${cr.left}-${cr.right}`);
          });
          c.querySelectorAll('figure.audio').forEach(f => {
            if (f.closest('[hidden]')) return;
            const a = f.querySelector('audio').getBoundingClientRect(), fr = f.getBoundingClientRect();
            if (a.left < fr.left - 1 || a.right > fr.right + 1) bad.push(`card ${i}: a player sticks out of its figure`);
          });
        });
        return {bad, scroll: document.documentElement.scrollWidth <= innerWidth + 1};
      });
      if (out.bad.length || !out.scroll) throw Error(`at 400px (${what}): ` + out.bad.join('; ') + (out.scroll ? '' : '; the page scrolls sideways'));
      if (Deno.env.get('PARSEH_TEST_ARTIFACTS'))
        await phone.screenshot({path: `${Deno.env.get('PARSEH_TEST_ARTIFACTS')}/cards-400-${what}.png`, fullPage: true});
      await phone.close();
    }
    if (Deno.env.get('PARSEH_TEST_ARTIFACTS')) await cards.screenshot({path: Deno.env.get('PARSEH_TEST_ARTIFACTS') + '/cards.png', fullPage: true});
    console.log('cards with blocks and recordings: 🔊 plays and one card speaks at a time, players and links never turn a card, a table does, Enter and Space turn it, the hidden side stops, Enlarge with players (Space on one plays it and the page hears nothing, paragraphs drawn as on the page), laid out at 400px passed');
  } finally {
    await mediaServer.shutdown();
    await Deno.remove(MEDIA_DIR, {recursive: true});
  }


  if(errors.length) throw Error(errors.join('\n'));
} finally { await browser.close(); }
