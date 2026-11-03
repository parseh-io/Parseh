// SPDX-License-Identifier: GPL-3.0-or-later
/* The four buttons that write a vocabulary entry, and what each says of itself.
 *
 *   word  \dw{}{}     verb  \vb{…}     compound  \bw{}{}{}     word in a meaning  \pw{}
 *
 * A book's chunk sheet (lib/tex2html.py, #chins) and a video's ✎ form
 * (youtube/lib/player.js) both have them.  Each shows the KIND of entry it
 * writes with its skeleton small under it; pointing at one, or tabbing to it,
 * shows what it is for, what goes in each pair of braces, and what it looks
 * like once shown -- an example in the language, drawn by lib/vocline.js, the
 * renderer the reader and the player draw a vocabulary line with.  The same
 * words are the button's title.
 *
 * WHY HERE AND NOT IN THE SHEET.  A reader is a page built for its book, and
 * what is baked into it reaches an old book only when it is built again.  This
 * file is loaded beside lib/parseh.js into every reader, however old, and
 * dresses the buttons the reader already has (each carries data-ins), so the
 * new words need no rebuild; the player's form calls it itself.
 *
 *   ParsehVocButtons.mount(box, {lang, gloss}) dresses the buttons in `box`
 *   ParsehVocButtons.insert(textarea, kind)     puts a kind's skeleton at the cursor
 *   ParsehVocButtons.explain(kind, lang, gloss) -> {name, skel, what, braces, example, title}
 *   ParsehVocButtons.EXAMPLES                   the examples, by language code
 *
 * `lang` is the registry record a page embeds (LANG, CFG.lang), `gloss` the
 * gloss language's (its name).  A language somebody added has no example of
 * its own, and its buttons explain themselves without one.
 */
(function (root) {
  'use strict';
  if (root.ParsehVocButtons) return;

  // the four kinds, in the order the buttons stand; `skel` is what the button
  // shows small under its name, and SKELETON what it writes
  var KINDS = [
    {k: 'dw', name: 'word', skel: '\\dw{}{}'},
    {k: 'vb', name: 'verb', skel: '\\vb{…}'},
    {k: 'bw', name: 'compound', skel: '\\bw{}{}{}'},
    {k: 'pw', name: 'word in a meaning', skel: '\\pw{}'}
  ];
  // the arity is the part nobody remembers, and a \vb one group short is a
  // refusal rather than a gloss; the caret lands inside the first group
  var SKELETON = {dw: '\\dw{}{} ', vb: '\\vb{}{}{}{}{}{}{}', bw: '\\bw{}{}{}', pw: '\\pw{}'};

  // ONE EXAMPLE PER LANGUAGE AND KIND, in the language's own script and the
  // conventions of docs/lang/<code>.md, drawn by the renderer when shown.
  // FROZEN at the eleven languages of a0.6.0, for readers built before the
  // record carried them: a language added since writes its own in the
  // registry (`examples.macros` in lib/languages.json), and needs no edit here.  The
  // compound's is the entry it belongs to: the light verb's \vb with nothing
  // between it and the \bw where the language builds its compound verbs so
  // (Persian, Turkish, Hindi, French, and by the same pattern Italian, Spanish
  // and English), and the whole with its parts where it builds compound words
  // (German, Japanese, Chinese, Arabic).
  var EXAMPLES = {
    fa: {dw: '\\dw{کتاب}{ketāb} book',
         vb: '\\vb{دیدن}{didan}{بین}{bin}{دید}{did}{to see}',
         bw: '\\vb{کردن}{kardan}{کن}{kon}{کرد}{kard}{}\\bw{فکر}{fekr}{to think}',
         pw: '\\dw{کتاب}{ketāb} book, pl. \\pw{کتب}'},
    ar: {dw: '\\dw{كتاب}{kitāb} book',
         vb: '\\vb{كتب}{kataba (I)}{يكتب}{yaktubu}{كتابة}{kitāba}{to write}',
         bw: '\\dw{جواز السفر}{jawāz as-safar} passport\\bw{جواز}{jawāz}{permit}\\bw{سفر}{safar}{travel}',
         pw: '\\dw{كتاب}{kitāb} book, pl. \\pw{كتب}'},
    it: {dw: '\\dw{telefono}{telèfono} telephone',
         vb: '\\vb{parlare}{}{parlo}{}{parlato}{}{to speak}',
         bw: '\\vb{avere}{}{ho}{}{avuto}{}{}\\bw{fame}{}{to be hungry}',
         pw: '\\dw{uovo}{} egg, pl. \\pw{le uova}'},
    ja: {dw: '\\dw{本}{hon} book',
         vb: '\\vb{書く}{kaku}{書き}{kaki}{書いて}{kaite}{to write}',
         bw: '\\dw{天気予報}{tenki yohō} weather forecast\\bw{天気}{tenki}{weather}\\bw{予報}{yohō}{forecast}',
         pw: '\\dw{本}{hon} book; counted with \\pw{冊}'},
    fr: {dw: '\\dw{livre}{livr} book, m.',
         vb: '\\vb{regarder}{regardé}{regarde}{regard}{regardé}{regardé}{to look at}',
         bw: '\\vb{avoir}{avwar}{ai}{é}{eu}{ü}{}\\bw{peur}{peur}{to be afraid}',
         pw: '\\dw{œil}{œj} eye, pl. \\pw{yeux}'},
    de: {dw: '\\dw{der Tisch, -e}{} table',
         vb: '\\vb{gehen}{}{ging}{}{gegangen}{}{to go}',
         bw: '\\dw{Geschwindigkeitsbegrenzung}{} speed limit\\bw{Geschwindigkeit}{}{speed}\\bw{Begrenzung}{}{limit}',
         pw: '\\dw{das Kind, -er}{} child, pl. \\pw{Kinder}'},
    tr: {dw: '\\dw{kitap}{} book',
         vb: '\\vb{gelmek}{}{geliyor}{}{gelir}{}{to come}',
         bw: '\\vb{etmek}{}{ediyor}{}{eder}{}{}\\bw{teşekkür}{}{to thank}',
         pw: '\\dw{kitap}{} book, pl. \\pw{kitaplar}'},
    en: {dw: '\\dw{apple}{ˈæpəl} a round hard fruit',
         vb: '\\vb{sleep}{slip}{slept}{slɛpt}{slept}{slɛpt}{to rest with the eyes closed}',
         bw: '\\vb{take}{teɪk}{took}{tʊk}{taken}{ˈteɪkən}{}\\bw{care}{kɛr}{to look after}',
         pw: '\\dw{child}{tʃaɪld} a young person, pl. \\pw{children}'},
    hi: {dw: '\\dw{किताब}{kitāb} f. book',
         vb: '\\vb{पढ़ना}{paṛhnā}{पढ़}{paṛh}{पढ़ा}{paṛhā}{to read}',
         bw: '\\vb{करना}{karnā}{कर}{kar}{किया}{kiyā}{}\\bw{काम}{kām}{to work}',
         pw: '\\dw{किताब}{kitāb} f. book, pl. \\pw{किताबें}'},
    es: {dw: '\\dw{libro}{} book, m.',
         vb: '\\vb{hablar}{}{hablo}{}{habló}{}{to speak}',
         bw: '\\vb{tener}{}{tengo}{}{tuvo}{}{}\\bw{hambre}{}{to be hungry}',
         pw: '\\dw{libro}{} book, pl. \\pw{libros}'},
    zh: {dw: '\\dw{书}{shū} book',
         vb: '\\vb{睡觉}{shuìjiào}{睡了觉}{shuìle jiào}{}{}{to sleep}',
         bw: '\\dw{电话号码}{diànhuà hàomǎ} telephone number\\bw{电话}{diànhuà}{telephone}\\bw{号码}{hàomǎ}{number}',
         pw: '\\dw{书}{shū} book; counted with \\pw{本}'}
  };
  // the languages that build a compound as a whole with its parts, and not a
  // verb with the word it carries
  // (frozen like EXAMPLES: the record's `compounds` says it for any other)
  var PARTS = {de: 1, ja: 1, zh: 1, ar: 1};
  function parts(lang) { return !!(PARTS[lang.code] || lang.compounds === 'parts'); }

  // what each kind says of itself, in the words of the sheet it stands in: a
  // line on what it is and when to use it, and one on what goes in the braces
  function explain(kind, lang, gloss) {
    lang = lang || {};
    var k = KINDS.filter(function (x) { return x.k === kind; })[0];
    if (!k) return null;
    var glossName = (gloss && gloss.name) || 'gloss';
    // the second group is the language's own romanisation, called what the
    // registry calls it: a pronunciation for Italian, rōmaji for Japanese
    var roman = lang.translit_label || 'romanisation';
    var what, braces;
    if (kind === 'dw') {
      what = 'a word as a dictionary lists it, and what it means; use it for every word that is not a verb';
      braces = 'in the braces, in order: the word · its ' + roman + '; what it means follows them';
    } else if (kind === 'vb') {
      var forms = (lang.vb_forms || []).filter(Boolean).slice(0, 3);
      var labels = lang.vb_labels || ['pres.', 'past'];
      what = 'a verb with its principal parts; use it for every verb, whatever form the text has';
      braces = 'in the braces, in order: ' +
        (forms.length === 3 ? forms.join(' · ')
                            : 'the form it is listed under · its ' + labels[0] + ' form · its ' + labels[1] + ' form') +
        ', each with its ' + roman + ', then what it means; printed with the labels ‘' + labels[0] +
        '’ and ‘' + labels[1] + '’, and a form left empty is left out';
    } else if (kind === 'bw') {
      what = parts(lang)
        ? 'one part of a compound word, written after the entry of the whole, one for each part'
        : 'the base word of a compound verb, written right after the verb’s entry with nothing between them; ' +
          'the verb’s own meaning stays empty';
      braces = 'in the braces, in order: the word · its ' + roman + ' · what ' +
        (parts(lang) ? 'it means' : 'the compound means');
    } else {
      // where the meanings are in the language of the text, the mark says only
      // "this is a word of the text" (docs/lang/en.md)
      what = gloss && gloss.code && gloss.code === lang.code
        ? 'a word of the text inside a meaning or a note, marked as the text’s own'
        : 'a word of ' + (lang.name || 'the language') + ' inside a meaning or a note, so that it keeps its ' +
          'own script and direction among the ' + glossName + ' words';
      braces = 'in the braces: the word';
    }
    // the registry's own (examples.macros, in the record a page embeds), else
    // this table, which a reader of any age can ask for the eleven it holds
    var own = (lang.examples && lang.examples.macros) || EXAMPLES[lang.code] || {};
    var ex = own[kind] || '';
    var text = k.name + ' — ' + what + '\n' + braces;
    if (ex && root.ParsehVocline) {
      try { text += '\nlooks like: ' + root.ParsehVocline.flatten(ex, lang); } catch (e) { /* no example in the title */ }
    }
    return {name: k.name, skel: k.skel, what: what, braces: braces, example: ex, title: text};
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
    });
  }

  // the line under the buttons for one kind: what it is, the braces, and the
  // example drawn the way the reader draws it, its source small beneath
  function helpHTML(e, lang) {
    var h = '<div><b>' + esc(e.name) + '</b> — ' + esc(e.what) + '</div>' +
            '<div>' + esc(e.braces) + '</div>';
    if (e.example) {
      var drawn = '';
      try { drawn = root.ParsehVocline ? root.ParsehVocline.render(e.example, lang) : ''; } catch (x) { drawn = ''; }
      if (drawn)
        h += '<div class="vk-look"><span class="vk-cap">looks like</span> <span class="vk-drawn">' + drawn + '</span></div>';
      h += '<div class="vk-src"><code>' + esc(e.example) + '</code></div>';
    }
    return h;
  }

  var STYLE = [
    // the buttons: the kind, and its skeleton small under it
    '.vk-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}',
    '.vk-row button,#chins.vk-row .dbtn{display:flex;flex-direction:column;align-items:flex-start;gap:1px;',
    'font:inherit;font-size:12px;line-height:1.25;color:var(--dim);background:transparent;',
    'border:1px solid var(--rule);border-radius:10px;padding:4px 10px;cursor:pointer;text-align:start}',
    '.vk-row button:hover,.vk-row button:focus-visible,.vk-row button.vk-on,#chins.vk-row .dbtn:hover{',
    'border-color:var(--accent);color:var(--accent);outline:none}',
    '.vk-row .vk-skel{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:9.5px;opacity:.8}',
    // the line under them: ONE, in the body and fixed to the window, placed by
    // the script under whichever row is pointed at.  Inside the row it would be
    // cut by the form's own scrolling, and among its fields it would make the
    // form grow and shrink as the pointer crosses the four buttons.
    '.vk-help{position:fixed;z-index:200;box-sizing:border-box;padding:6px 9px;',
    'background:var(--card,var(--bg));border:1px solid var(--rule);border-radius:6px;',
    'box-shadow:0 6px 18px rgba(0,0,0,.18);font-size:11.5px;line-height:1.5;color:var(--dim);',
    'text-align:start;font-weight:400;overflow-y:auto}',
    '.vk-help[hidden]{display:none}',
    '.vk-help b{color:var(--ink);font-weight:600}',
    '.vk-help .vk-look{margin-top:3px}',
    '.vk-help .vk-cap{color:var(--faint);letter-spacing:.06em;text-transform:uppercase;font-size:10px}',
    '.vk-help bdi.v{font-family:var(--tl-font,serif);font-size:1.1em;font-style:normal}',
    '.vk-help i{color:var(--ink)}',
    '.vk-help .vk-src{margin-top:2px;color:var(--faint)}',
    '.vk-help .vk-src code{font-size:10.5px;word-break:break-all}'
  ].join('');
  function style() {
    if (document.getElementById('vk-style')) return;
    var s = document.createElement('style');
    s.id = 'vk-style';
    s.textContent = STYLE;
    (document.head || document.documentElement).appendChild(s);
  }

  // THE LINE UNDER THE BUTTONS is one element for the whole page, made when the
  // first is pointed at.
  var help = null, owner = null, ownerApi = null;
  function theHelp() {
    if (help) return help;
    help = document.createElement('div');
    help.id = 'vk-help';
    help.className = 'vk-help';
    help.hidden = true;
    help.setAttribute('role', 'status');
    help.setAttribute('lang', 'en');
    help.setAttribute('dir', 'ltr');
    document.body.appendChild(help);
    // the pointer on the line keeps it, for whichever row it is about
    help.addEventListener('mouseenter', function () { if (ownerApi) ownerApi.hold(true); });
    help.addEventListener('mouseleave', function () { if (ownerApi) ownerApi.hold(false); });
    // Esc closes the form the buttons are in, and a line left behind is a line
    // about buttons that are gone
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') hide(); }, true);
    return help;
  }
  function hide() {
    if (!help) return;
    help.hidden = true;
    if (owner) {
      Array.prototype.forEach.call(owner.querySelectorAll('[data-ins]'), function (b) { b.classList.remove('vk-on'); });
      owner = null;
    }
    ownerApi = null;
  }
  // Under the row, as wide as the row (not narrower than a line can be read
  // in, not wider than the window); above it where there is no room below,
  // and slid up where there is none above either.
  function place(box) {
    var r = box.getBoundingClientRect();
    var vw = document.documentElement.clientWidth || window.innerWidth;
    var vh = document.documentElement.clientHeight || window.innerHeight;
    var w = Math.min(Math.max(r.width, 280), 520, vw - 16);
    help.style.width = w + 'px';
    help.style.maxHeight = (vh - 16) + 'px';
    help.style.left = Math.max(8, Math.min(r.left, vw - w - 8)) + 'px';
    help.style.top = '0px';
    var h = help.offsetHeight, top = r.bottom + 4;
    if (top + h > vh - 8 && r.top - h - 4 >= 8) top = r.top - h - 4;
    else if (top + h > vh - 8) top = Math.max(8, vh - h - 8);
    help.style.top = top + 'px';
  }

  // Dress the buttons in `box`: each carries data-ins (dw, vb, bw, pw) and is
  // given its kind, its skeleton and its title.  Hovering or focusing one shows
  // the line, hovering wins, and it goes when neither is left -- a moment late,
  // and never while the pointer is on the line itself, so the pointer can cross
  // from one button to the next, or down to read the example, without the line
  // shutting and opening.
  function mount(box, o) {
    if (!box || box.getAttribute('data-vk')) return null;
    o = o || {};
    var lang = o.lang || {}, gloss = o.gloss || null;
    style();
    box.setAttribute('data-vk', '1');
    box.classList.add('vk-row');
    var over = null, focused = null, shown = null, holding = false, timer = null, id = 'vk-help';
    var api = {hold: function (v) { holding = v; show(); }};
    function show() {
      clearTimeout(timer);
      var kind = over || focused || (holding && owner === box ? shown : null);
      if (!kind) {
        timer = setTimeout(function () { if (owner === box) hide(); shown = null; }, 160);
        return;
      }
      var h = theHelp();
      if (owner && owner !== box) hide();
      owner = box;
      ownerApi = api;
      shown = kind;
      h.innerHTML = helpHTML(explain(kind, lang, gloss), lang);
      h.hidden = false;
      place(box);
      Array.prototype.forEach.call(box.querySelectorAll('[data-ins]'), function (b) {
        b.classList.toggle('vk-on', b.getAttribute('data-ins') === kind);
      });
    }
    // the titles carry the example in plain text, which lib/vocline.js works
    // out: a reader loads the two scripts side by side, in no set order, so
    // the titles are made again once everything has arrived
    function titles() {
      KINDS.forEach(function (k) {
        var b = box.querySelector('[data-ins="' + k.k + '"]');
        if (b) b.title = explain(k.k, lang, gloss).title;
      });
    }
    if (!root.ParsehVocline) window.addEventListener('load', titles);
    KINDS.forEach(function (k) {
      var b = box.querySelector('[data-ins="' + k.k + '"]');
      if (!b) return;
      b.innerHTML = '<span class="vk-kind">' + esc(k.name) + '</span><span class="vk-skel">' + esc(k.skel) + '</span>';
      // in the order of the kinds, whichever order the page was built in: the
      // sheet has always stood \dw \pw \bw \vb, and a verb is the second thing
      // a person reaches for
      box.appendChild(b);
      b.setAttribute('aria-describedby', id);
      b.addEventListener('mouseenter', function () { over = k.k; show(); });
      b.addEventListener('mouseleave', function () { over = null; show(); });
      b.addEventListener('focus', function () { focused = k.k; show(); });
      b.addEventListener('blur', function () { focused = null; show(); });
    });
    titles();
    return {help: theHelp()};
  }

  // a kind's skeleton in place of the selection, the caret inside its first
  // group; `input` is fired so a preview of the line moves with it
  function insert(ta, kind) {
    var skel = SKELETON[kind];
    if (!ta || !skel) return;
    var a = ta.selectionStart, b = ta.selectionEnd;
    ta.value = ta.value.slice(0, a) + skel + ta.value.slice(b);
    var caret = a + skel.indexOf('{') + 1;
    ta.focus();
    ta.setSelectionRange(caret, caret);
    ta.dispatchEvent(new Event('input', {bubbles: true}));
  }

  root.ParsehVocButtons = {mount: mount, insert: insert, explain: explain, KINDS: KINDS,
                           EXAMPLES: EXAMPLES, SKELETON: SKELETON};

  // A BOOK'S CHUNK SHEET, dressed as the page loads.  The reader's own script
  // has run by the time the parser is done, and its LANG and GLOSS are what the
  // book is in; a page with no #chins (the player, the hub) is left alone.
  function readerSheet() {
    var box = document.getElementById('chins');
    if (!box) return;
    var L = null, G = null;
    try { L = typeof LANG === 'object' ? LANG : null; } catch (e) { /* no reader here */ }
    try { G = typeof GLOSS === 'object' ? GLOSS : null; } catch (e) { /* the name is optional */ }
    if (L) mount(box, {lang: L, gloss: G});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', readerSheet);
  else readerSheet();
})(typeof globalThis !== 'undefined' ? globalThis : this);
