// SPDX-License-Identifier: GPL-3.0-or-later
/* A vocabulary line, read and drawn in the page: lib/texparse.py's parse_voc,
 * lib/tex2html.py's render_voc and texparse.voc_text in JavaScript.
 *
 *   \vb{دیدن}{didan}{بین}{bin}{دید}{did}{to see}; \dw{کتاب}{ketāb} book
 *
 * A book's vocabulary line is written with four macros (\dw \vb \bw \pw, and
 * \textit \emph \nobreak beside them) and the reader draws it.  A video's line
 * may hold the same macros now, and the player draws them the way the reader
 * does -- which is this file.  lib/texparse.py is the authority;
 * tests/fixtures/vocline.json holds the two to the same runs, the same HTML
 * and the same plain text, and tests/test_vocline.py runs them.
 *
 *   ParsehVocline.isMacro(line)        -> is this a macro line (below)?
 *   ParsehVocline.parse(line, lang)    -> [[kind, text], ...]  (throws {code, message})
 *   ParsehVocline.render(line, lang)   -> the HTML the reader draws (throws as parse does)
 *   ParsehVocline.flatten(line, lang)  -> the line as plain text, as a card's notes hold it
 *
 * kind is 'fa' (a word of the language: the key is named after Persian, like
 * everywhere else), 'em' (its romanisation, in italics) or 'txt'.  `lang` is
 * the registry record a page embeds (LANG, CFG.lang): a \vb prints the two
 * labels of vb_labels, and the words are isolated with its code and direction.
 */
(function (root) {
  'use strict';

  // texparse.VOC_MACROS: how many groups each macro takes.  \nobreak takes
  // none and prints nothing.
  var MACROS = {dw: 2, vb: 7, bw: 3, pw: 1, textit: 1, emph: 1};

  // A LINE IS A MACRO LINE when it holds one of these, and any other line is
  // plain text -- drawn exactly as it always was, so that every video glossed
  // before macros existed looks the same.  \nobreak alone does not make one:
  // it is not an entry, and no plain line has ever held a backslash on purpose.
  var MACRO_LINE = ['\\dw{', '\\vb{', '\\bw{', '\\pw{', '\\textit{', '\\emph{'];
  function isMacro(s) {
    s = typeof s === 'string' ? s : '';
    return MACRO_LINE.some(function (m) { return s.indexOf(m) >= 0; });
  }

  // Python's str.isspace, which is what its `\s` and str.strip() go by:
  // JavaScript's \s is not the same set (it has U+FEFF and lacks U+001C-1F and
  // U+0085), and the two must cut a line in the same places.
  var SP = '\\t-\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
  var SPACES = new RegExp('[' + SP + ']+', 'g');
  var ENDS = new RegExp('^[' + SP + ']+|[' + SP + ']+$', 'g');
  function strip(s) { return s.replace(ENDS, ''); }
  function blank(s) { return s.replace(SPACES, '') === ''; }

  // what is wrong with a line the parser cannot read, in words and with a
  // code: 'groups' (a macro without all its braces) or 'unclosed' (a { with
  // no }).  texparse raises AssertionError / IndexError and ValueError for the
  // same two, and the fixture compares by code.
  function problem(code, message) {
    var e = new Error(message);
    e.code = code;
    return e;
  }

  // texparse.read_group: s[i] must be '{'; returns [contents, index just past
  // the matching '}'].  A backslash steps over the next character, so \{ is
  // not a brace.
  function readGroup(s, i) {
    if (i >= s.length || s.charAt(i) !== '{') throw problem('groups', '');
    var depth = 0, j = i;
    while (j < s.length) {
      var c = s.charAt(j);
      if (c === '\\') { j += 2; continue; }
      if (c === '{') depth++;
      else if (c === '}') {
        depth--;
        if (depth === 0) return [s.slice(i + 1, j), j + 1];
      }
      j++;
    }
    throw problem('unclosed', '');
  }

  // texparse.read_args: n groups from i, whitespace between them skipped.
  // The macro's name and `want` (what it takes in all, where n is only the
  // first of them: \bw's probe reads two of its three) are what the message
  // says the line is short of.
  function readArgs(s, i, n, name, want) {
    var args = [];
    want = want || n;
    for (var k = 0; k < n; k++) {
      while (i < s.length && ' \t\r\n'.indexOf(s.charAt(i)) >= 0) i++;
      var g;
      try { g = readGroup(s, i); }
      catch (e) {
        throw problem(e.code, e.code === 'unclosed'
          ? 'a { after \\' + name + ' is never closed'
          : '\\' + name + ' needs ' + want + ' group' + (want === 1 ? '' : 's') +
            ' in braces {…} and has ' + k);
      }
      args.push(g[0]);
      i = g[1];
    }
    return [args, i];
  }

  // texparse._voc_runs: the walk parse tidies.  Called again on the free-text
  // slots -- the meaning of a \vb, the phrase of a \bw -- because those carry
  // the same macros as the rest of the line.
  function runs(s, lang) {
    var out = [], i = 0, buf = '';
    function push(kind, text) { if (text) out.push([kind, text]); }
    function quoted(text) {          // a \bw's phrase, in the single quotes the PDF prints
      push('txt', ' ‘');
      Array.prototype.push.apply(out, runs(text, lang));
      push('txt', '’');
    }
    var word = /\\([a-zA-Z]+)/y;
    while (i < s.length) {
      var c = s.charAt(i);
      if (c !== '\\') { buf += c; i++; continue; }
      word.lastIndex = i;
      var m = word.exec(s);
      if (!m) {                      // \, \  and friends: thin spaces
        var two = s.slice(i, i + 2);
        buf += (two === '\\,' || two === '\\ ') ? ' ' : '';
        i += 2;
        continue;
      }
      var name = m[1];
      i += m[0].length;
      if (name === 'nobreak') continue;
      if (!MACROS.hasOwnProperty(name)) continue;   // unknown control word: drop it, keep the text
      var nArgs = MACROS[name], args;
      if (name === 'bw') {
        // \bw{x}{y} meaning, the meaning as loose text: LaTeX would swallow
        // the next CHARACTER as the third argument, so the phrase is
        // recovered, and the reader shows what was meant
        var probe = readArgs(s, i, 2, name, 3), j = probe[1];
        while (j < s.length && (s.charAt(j) === ' ' || s.charAt(j) === '\t')) j++;
        if (j < s.length && s.charAt(j) !== '{') {
          var end = s.indexOf(';', j);
          end = end >= 0 ? end : s.length;
          i = end;
          push('txt', buf); buf = '';
          push('txt', ' · '); push('fa', probe[0][0]); push('em', probe[0][1]);
          quoted(strip(s.slice(j, end)));
          continue;
        }
      }
      var got = readArgs(s, i, nArgs, name);
      args = got[0]; i = got[1];
      push('txt', buf); buf = '';
      if (name === 'pw') {
        push('fa', args[0]);
      } else if (name === 'dw') {
        push('fa', args[0]); push('em', args[1]);
      } else if (name === 'bw') {
        push('txt', ' · '); push('fa', args[0]); push('em', args[1]);
        quoted(args[2]);
      } else if (name === 'vb') {
        // a pair without a form is not printed, and takes its label with it
        // (the preamble's \ifblank): that is how a Chinese verb gives its
        // split and no "can't" form.  The sound alone is never tested.
        var labels = (lang && lang.vb_labels) || ['pres.', 'past'];
        push('fa', args[0]); push('em', args[1]);
        if (strip(args[2])) { push('txt', ' · ' + labels[0] + ' '); push('fa', args[2]); push('em', args[3]); }
        if (strip(args[4])) { push('txt', ' · ' + labels[1] + ' '); push('fa', args[4]); push('em', args[5]); }
        if (strip(args[6])) {
          push('txt', ' · ');
          Array.prototype.push.apply(out, runs(args[6], lang));
        }
      } else {                        // textit, emph
        push('em', args[0]);
      }
    }
    push('txt', buf);
    return out;
  }

  // texparse.parse_voc
  function parse(s, lang) {
    if (typeof s !== 'string') s = s == null ? '' : String(s);
    return runs(s, lang).map(function (r) { return [r[0], r[1].replace(SPACES, ' ')]; })
                        .filter(function (r) { return !blank(r[1]); });
  }

  // The join rule of texparse.voc_text and render_voc: a space between two
  // runs unless the first ends in a space, an opening bracket, an opening
  // quote or a slash, or the second starts with the punctuation that closes a
  // phrase -- so `aux. \pw{avere}/\pw{essere}` is "avere/essere", as the PDF
  // prints it, and not "avere / essere".
  function joins(prev, text) {
    return !/[ (‘\/]$/.test(prev) && !/^[ ,;).’:\/]/.test(text);
  }

  // what html.escape(s, quote=True) makes of a string, so the two renderers
  // give the same bytes
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;'}[c];
    });
  }

  // tex2html.render_voc: each word of the language isolated, as \pw does in
  // the PDF (its own lang and dir, and the class the sheets set its face by),
  // and the romanisation in italics.  \dw and \vb put a real space between
  // the word and its romanisation; the join rule keeps it, or the two collide.
  function render(s, lang) {
    var attrs = ' lang="' + lang.code + '" dir="' + lang.dir + '"';
    var out = '', prev = '', first = true;
    parse(s, lang).forEach(function (r) {
      if (!first && joins(prev, r[1])) out += ' ';
      if (r[0] === 'fa') out += '<bdi' + attrs + ' class="v">' + esc(r[1]) + '</bdi>';
      else if (r[0] === 'em') out += '<i>' + esc(r[1]) + '</i>';
      else out += esc(r[1]);
      prev = r[1];
      first = false;
    });
    return out;
  }

  // texparse.voc_text: the line as the plain text a video used to store, and
  // as a card's notes should hold it: the runs joined, and the few escapes
  // the field may carry undone.
  function flatten(s, lang) {
    s = (typeof s === 'string' ? s : s == null ? '' : String(s))
      .split('\\&').join('&').split('\\%').join('%').split('\\#').join('#')
      .split('\\_').join('_').split('~').join(' ').split('---').join('—')
      .split('--').join('–');
    var out = '', prev = '', first = true;
    parse(s, lang).forEach(function (r) {
      if (!first && joins(prev, r[1])) out += ' ';
      out += r[1];
      prev = r[1];
      first = false;
    });
    return strip(out.replace(SPACES, ' '));
  }

  /* texparse.voc_entries: the line cut into ENTRIES, for the vocabulary list
     (TO-DO 11.14).  Each \dw \vb \bw at the top of the line starts one, and a
     \pw that opens a stretch of it (its start, or after a `;`); a \pw after
     other text is a word inside a meaning and stays there.  The meaning is the
     text after the entry up to the next `;` or entry, as flatten reads it, a
     \vb's own last group and a \bw's phrase first.  Throws as parse does. */
  var LEAD = /^[ ,:;·—–]+/, TRAIL = /[ ,]+$/;
  function entries(s, lang) {
    if (typeof s !== 'string') s = s == null ? '' : String(s);
    parse(s, lang);                  // a line that cannot be read throws here, as parse does
    var out = [], cur = null, i = 0, stretch = 0;
    var word = /\\([a-zA-Z]+)/y;
    function close(end) {
      if (!cur) return;
      var src = cur.lead + s.slice(cur.tail, end);
      delete cur.lead; delete cur.tail;
      cur.meaning = flatten(src, lang).replace(LEAD, '').replace(TRAIL, '');
      out.push(cur);
    }
    while (i < s.length) {
      var c = s.charAt(i);
      if (c === ';') { close(i); cur = null; i++; stretch = i; continue; }
      if (c !== '\\') { i++; continue; }
      word.lastIndex = i;
      var m = word.exec(s);
      if (!m) { i += 2; continue; }
      var name = m[1], at = i;
      i += m[0].length;
      if (!MACROS.hasOwnProperty(name) || name === 'nobreak') continue;
      var starts = name === 'dw' || name === 'vb' || name === 'bw' || (name === 'pw' && blank(s.slice(stretch, at)));
      if (name === 'bw') {
        var probe = readArgs(s, i, 2, name, 3), j = probe[1];
        while (j < s.length && (s.charAt(j) === ' ' || s.charAt(j) === '\t')) j++;
        if (j < s.length && s.charAt(j) !== '{') {
          var end = s.indexOf(';', j);
          end = end >= 0 ? end : s.length;
          close(at);
          cur = entry('bw', probe[0][0], probe[0][1], lang, s.slice(j, end), end);
          i = end;
          continue;
        }
      }
      var got = readArgs(s, i, MACROS[name], name), args = got[0];
      i = got[1];
      if (!starts) continue;
      close(at);
      if (name === 'vb')
        cur = entry('vb', args[0], args[1], lang, args[6], i,
                    '\\vb{' + args.slice(0, 6).join('}{') + '}{}');
      else if (name === 'bw') cur = entry('bw', args[0], args[1], lang, args[2], i);
      else if (name === 'dw') cur = entry('dw', args[0], args[1], lang, '', i);
      else cur = entry('pw', args[0], '', lang, '', i);
    }
    close(s.length);
    return out;
  }
  function entry(kind, w, r, lang, lead, tail, head) {
    var word = flatten(w, lang);
    return {kind: kind, word: word, rom: flatten(r, lang),
            head: parse(head || '\\dw{' + w + '}{' + r + '}', lang),
            key: key(word, lang), lead: lead, tail: tail};
  }

  /* texparse.vocab_key: the form two entries are compared by -- NFC, the
     language's own marks off (its `strip` range), the zero-width joiners off,
     Persian's ي ى ك as ی ی ک, Turkish's two i's, lower case, the spaces
     tidied.  Same key, same word. */
  var stripRes = {};
  function key(w, lang) {
    w = typeof w === 'string' ? w : w == null ? '' : String(w);
    try { w = w.normalize('NFC'); } catch (e) {}
    var range = lang && lang.strip;
    if (range) {
      if (!stripRes[range]) stripRes[range] = new RegExp('[' + range + ']', 'g');
      w = w.replace(stripRes[range], '');
    }
    w = w.replace(/[‌‍]/g, '');
    var code = lang && lang.code;
    if (code === 'fa') w = w.replace(/[يى]/g, 'ی').replace(/ك/g, 'ک');
    if (code === 'tr') w = w.replace(/İ/g, 'i').replace(/I/g, 'ı');
    return strip(w.toLowerCase().replace(SPACES, ' '));
  }

  /* texparse.voc_plain_entries: a PLAIN-TEXT line (a video glossed before the
     macros) cut into entries by its shape -- read texparse's comment above
     voc_is_note for the rules; this is the same walk, step for step, held
     equal to it by tests/fixtures/vocline.json's `plain` cases.  `text` is the
     chunk's own text (a Latin-script line's word must be in it, or end at a
     separator), `tr` its transliteration (what vouches for a bare
     romanisation).  Never throws: what it cannot read is in no entry. */
  var ENTRY_MACRO = /\\(?:dw|vb|bw|pw)(?![a-zA-Z])/, ITALIC = /\\(?:textit|emph)\{([^{}]*)\}/g;
  var LAT = 'A-Za-z\\u00C0-\\u024F\\u0250-\\u02FF\\u1E00-\\u1EFF';
  var LAT_RE = new RegExp('[' + LAT + ']'), ROM_START = new RegExp('^[' + LAT + "'\\u2019]");
  var IPA = /[\u0250-\u02AF\u02C8\u02CC\u02D0\u03B8\u03B2\u03C7\u00E6\u00F0\u00E3\u00F5\u1EBD\u0129\u0169]/, TONE = 'āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ';
  var WTRAIL = ' ,:;،؛', SEPS = [' · ', ' – ', ' — ', ' = ', ': ', ' - ', ' (', ' [', ' *', ' /'];
  var TOK = new RegExp('[^' + SP + ']+', 'g'), LEADWS = new RegExp('^[' + SP + ']*');
  var PLAIN_LEAD = new RegExp('^[' + SP + ',:;·—–]+'), NEXT_CH = new RegExp('^[' + SP + ']+([^' + SP + '])');
  var WORDCH = /[\p{L}\p{M}\p{N}'’-]/u, ALPHA = /^\p{L}/u, MN = /\p{Mn}/u;
  function rstripChars(s, chars) {
    var e = s.length;
    while (e > 0 && chars.indexOf(s.charAt(e - 1)) >= 0) e--;
    return s.slice(0, e);
  }
  function tidy(s) { return strip(s.replace(SPACES, ' ')); }
  function toks(s) {
    var out = [], m;
    TOK.lastIndex = 0;
    while ((m = TOK.exec(s))) out.push([m.index, m.index + m[0].length, m[0]]);
    return out;
  }
  function closeOf(s, j, o, c) {
    var depth = 0;
    for (var k = j; k < s.length; k++) {
      if (s.charAt(k) === o) depth++;
      else if (s.charAt(k) === c) { depth--; if (depth === 0) return k; }
    }
    return -1;
  }
  function foldWords(t, lang) {
    var k = key(t, lang), out = '';
    for (var i = 0; i < k.length; i++) out += WORDCH.test(k.charAt(i)) ? k.charAt(i) : ' ';
    return tidy(out);
  }
  function isNote(s) { return strip(typeof s === 'string' ? s : '').slice(0, 2) === '//'; }
  function plainItems(s, sc) {
    var out = [], start = 0, depth = 0;
    for (var i = 0; i < s.length; i++) {
      var c = s.charAt(i);
      if (c === '(' || c === '[') depth++;
      else if (c === ')' || c === ']') depth = Math.max(0, depth - 1);
      else if (depth === 0 && (c === ';' || c === '\n')) { out.push(s.slice(start, i)); start = i + 1; }
      else if (depth === 0 && c === '·' && sc && i > 0 && (s.charAt(i - 1) === ' ' || s.charAt(i - 1) === '\t')) {
        var m = NEXT_CH.exec(s.slice(i + 1));
        if (m && sc.test(m[1])) { out.push(s.slice(start, i)); start = i + 1; }
      }
    }
    out.push(s.slice(start));
    return out.map(strip).filter(function (x) { return x; });
  }
  function trWords(tr, lang) {
    var out = {};
    foldWords(tr || '', lang).split(' ').forEach(function (w) {
      if (!w) return;
      out[w] = 1;
      w.split('-').forEach(function (p) { if (p) out[p] = 1; });
    });
    return out;
  }
  // texparse._AR_CONS / _AR_OPTIONAL / _arabic_fits: a bare romanisation's
  // consonants against the letters of the Arabic-script word beside it
  var AR_CONS = {'ب': 'b', 'پ': 'p', 'ت': 't', 'ط': 't', 'ث': 'st', 'ج': 'jg', 'چ': 'c',
                 'ح': 'h', 'خ': 'xhk', 'د': 'd', 'ذ': 'zd', 'ر': 'r', 'ز': 'z', 'ژ': 'z',
                 'ض': 'zd', 'ظ': 'z', 'س': 's', 'ص': 's', 'ش': 's', 'غ': 'gq', 'ق': 'qgk',
                 'ف': 'f', 'ک': 'k', 'ك': 'k', 'گ': 'g', 'ل': 'l', 'م': 'm', 'ن': 'n'};
  var AR_OPTIONAL = {'ا': '', 'آ': '', 'أ': '', 'إ': '', 'ٱ': '', 'ء': '', 'ئ': '', 'ؤ': '',
                     'ع': '', 'و': '', 'ی': '', 'ي': '', 'ى': '', 'ة': 'ht', 'ه': 'h', 'ً': 'n'};
  var AR_SKIP = 'ٌٍَُِّْٰـ‌‍‑-';
  function romConsonants(core) {
    var s = core.toLowerCase(), out = '';
    try { s = s.normalize('NFD'); } catch (e) {}
    for (var i = 0; i < s.length; i++) if (!MN.test(s.charAt(i))) out += s.charAt(i);
    out = out.replace(/kh/g, 'x').replace(/sh/g, 's').replace(/ch/g, 'c').replace(/zh/g, 'z').replace(/gh/g, 'g');
    out = out.replace(/(.)\1/g, '$1');
    return out.replace(/[^bcdfghjklmnpqrstxz]/g, '');
  }
  function arabicFits(word, core) {
    var letters = [];
    word = word || '';
    for (var i = 0; i < word.length; i++) {
      var ch = word.charAt(i);
      if (AR_SKIP.indexOf(ch) >= 0) continue;
      if (AR_CONS.hasOwnProperty(ch)) letters.push([AR_CONS[ch], false]);
      else if (AR_OPTIONAL.hasOwnProperty(ch)) letters.push([AR_OPTIONAL[ch], true]);
      else return false;
    }
    var rom = romConsonants(core), seen = {};
    if (!letters.length || !rom) return false;
    function fit(i, j) {
      var id = i + ',' + j;
      if (seen.hasOwnProperty(id)) return seen[id];
      var ok;
      if (i === letters.length) ok = j === rom.length;
      else ok = (j < rom.length && letters[i][0].indexOf(rom.charAt(j)) >= 0 && fit(i + 1, j + 1)) ||
                (letters[i][1] && fit(i + 1, j));
      seen[id] = ok;
      return ok;
    }
    return fit(0, 0);
  }
  function vouched(core, trw, lang, wt) {
    for (var i = 0; i < core.length; i++)
      if (core.charCodeAt(i) > 127 && LAT_RE.test(core.charAt(i))) return true;
    var f = foldWords(core, lang).replace(/ /g, '');
    if (f && (trw.hasOwnProperty(f) || f.split('-').every(function (p) { return !p || trw.hasOwnProperty(p); })))
      return true;
    return !!(lang && lang.script === 'arabic') && arabicFits(wt, core);
  }
  function romAfter(s, end, need, sc, lang, trw, wtoks, sure) {
    var j = end + LEADWS.exec(s.slice(end))[0].length;
    if (j >= s.length) return ['', end];
    var c = s.charAt(j);
    if ('([/*'.indexOf(c) >= 0) {
      var close = {'(': ')', '[': ']', '/': '/', '*': '*'}[c];
      var k = (c === '(' || c === '[') ? closeOf(s, j, c, close) : s.indexOf(close, j + 1);
      if (k > j + 1) {
        var inner = strip(s.slice(j + 1, k));
        var ok = LAT_RE.test(inner) && !(sc && sc.test(inner));
        if (ok && c === '(')
          ok = inner.length > 2 && !/[.,;:+=()0-9]/.test(inner) && toks(inner).length <= Math.max(need, 1) + 2;
        if (ok) return [inner.replace(SPACES, ' '), k + 1];
      }
      return ['', end];
    }
    if (!sc) {                         // a Latin script: words in IPA, as many as the word has
      var lt = toks(s.slice(end)), lstop = end;
      for (var q = 0; q < lt.length; q++) {
        var lc = rstripChars(lt[q][2], ',:;');
        if (q >= need || !lc || !IPA.test(lc)) break;
        lstop = end + lt[q][0] + lc.length;
        if (lc !== lt[q][2]) break;
      }
      if (lstop === end) return ['', end];
      return [strip(s.slice(end, lstop)).replace(SPACES, ' '), lstop];
    }
    var taken = [], ts = toks(s.slice(end));
    for (var n = 0; n < ts.length; n++) {
      var tk = ts[n][2], cr = rstripChars(tk, ',:;');
      if (!cr || !ROM_START.test(cr) || sc.test(cr)) break;
      if (taken.length >= need && !(lang.word_sep === '' && (cr.split('').some(function (x) { return TONE.indexOf(x) >= 0; }) ||
                                                              trw.hasOwnProperty(foldWords(cr, lang)))))
        break;
      taken.push([cr, end + ts[n][0] + cr.length]);
      if (cr !== tk) break;
    }
    if (!taken.length) return ['', end];
    var after = strip(s.slice(taken[taken.length - 1][1]));
    if (after && after.charAt(0) !== '·' && !sure) {
      var m = 0;
      while (m < taken.length && vouched(taken[m][0], trw, lang, m < wtoks.length ? wtoks[m] : '')) m++;
      taken = taken.slice(0, m);
      if (!taken.length) return ['', end];
    }
    var stop = taken[taken.length - 1][1];
    return [strip(s.slice(end, stop)).replace(SPACES, ' '), stop];
  }
  function scriptHead(s, sc, rd, lang, trw) {
    var words = [], ts = toks(s);
    for (var i = 0; i < ts.length; i++) {
      var t = ts[i][2];
      if (!sc.test(t.charAt(0))) break;
      words.push(ts[i]);
      if (WTRAIL.indexOf(t.charAt(t.length - 1)) >= 0) break;
    }
    if (!words.length) return null;
    var allRd = function (w) { for (var k = 0; k < w.length; k++) if (!rd.test(w.charAt(k))) return false; return true; };
    var kana = '', word, need, end;
    if (rd && words.length === 2 && allRd(words[1][2]) && !allRd(words[0][2])) {
      kana = rstripChars(words[1][2], WTRAIL);
      word = rstripChars(words[0][2], WTRAIL);
      need = 1; end = words[1][0] + kana.length;
    } else {
      word = rstripChars(s.slice(words[0][0], words[words.length - 1][1]), WTRAIL);
      need = words.length; end = words[0][0] + word.length;
    }
    // after a kana reading (`私 わたし watashi`) the Latin word is the reading's
    var r = romAfter(s, end, need, sc, lang, trw, words.map(function (w) { return rstripChars(w[2], WTRAIL); }), !!kana);
    return [word.replace(SPACES, ' '), kana, r[0], r[1]];
  }
  function latinHead(s, lang, text) {
    var ts = toks(s);
    if (!ts.length || !ALPHA.test(ts[0][2])) return null;
    var word = null, end = 0, hay = foldWords(text || '', lang);
    hay = ' ' + hay + ' ' + hay.replace(/['\u2019]/g, ' ') + ' ';     // `d'autre` holds autre
    if (strip(hay)) {
      var upto = 0;
      for (var i = 0; i < Math.min(4, ts.length); i++) {
        var t = ts[i][2];
        if (!(ALPHA.test(t) || t.charAt(0) === "'" || t.charAt(0) === '’')) break;
        upto++;
        if (',;:.'.indexOf(t.charAt(t.length - 1)) >= 0) break;
      }
      for (var k = upto; k > 0; k--) {
        var cand = rstripChars(s.slice(ts[0][0], ts[k - 1][1]), ',;:.'), f = foldWords(cand, lang);
        if (f && hay.indexOf(' ' + f + ' ') >= 0) { word = cand; end = ts[0][0] + cand.length; break; }
      }
    }
    if (word === null) {
      var best = null;
      SEPS.forEach(function (sep) {
        var p = s.indexOf(sep);
        if (p > 0 && (!best || p < best[0])) best = [p, sep];
      });
      if (!best) return null;
      var c2 = rstripChars(s.slice(0, best[0]), ' ,');
      var tail = c2 ? ipaTail(c2) : ['', ''];
      if (!tail[0] || toks(tail[0]).length > 3) return null;
      word = tail[0];
      end = best[1] === ' - ' ? best[0] + best[1].length : best[0];
      if (tail[1]) return [word, '', tail[1], end];
    }
    var r = romAfter(s, end, toks(word).length, null, lang, {}, []);
    return [word.replace(SPACES, ' '), '', r[0], r[1]];
  }
  // texparse._ipa_tail: `get gɛt` -> ['get', 'gɛt']
  function ipaTail(cand) {
    var ws = toks(cand).map(function (t) { return t[2]; }), k = ws.length;
    while (k > 1 && IPA.test(ws[k - 1])) k--;
    return [ws.slice(0, k).join(' '), ws.slice(k).join(' ')];
  }
  function plainVerb(rest, sc, rd, lang, trw) {
    rest = rest.replace(LEADWS, '');
    var labels = lang.vb_labels || [];
    if (rest.charAt(0) !== '·' || !labels.length) return null;
    var parts = [], start = 1, depth = 0;
    for (var i = 1; i < rest.length; i++) {
      var c = rest.charAt(i);
      if (c === '(' || c === '[') depth++;
      else if (c === ')' || c === ']') depth = Math.max(0, depth - 1);
      else if (c === '·' && depth === 0) { parts.push(strip(rest.slice(start, i))); start = i + 1; }
    }
    parts.push(strip(rest.slice(start)));
    var stems = [], k = 0;
    labels.forEach(function (lab) {
      var got = null;
      if (k < parts.length && parts[k].indexOf(lab + ' ') === 0) {
        var body = strip(parts[k].slice(lab.length + 1));
        if (sc) {
          var h = scriptHead(body, sc, rd, lang, trw);
          if (h && !strip(body.slice(h[3]))) got = [h[0], h[2]];
        } else if (toks(body).length > 0 && toks(body).length <= 4 && ALPHA.test(body)) {
          got = ipaTail(body);
        }
      }
      if (got) k++;
      stems.push(got);
    });
    if (!stems.some(function (x) { return x; })) return null;
    return [stems, parts.slice(k).join(' · ')];
  }
  function plainEntries(s, lang, text, tr) {
    s = typeof s === 'string' ? s : s == null ? '' : String(s);
    lang = lang || {};
    if (isNote(s)) return [];
    s = s.replace(ITALIC, '*$1*');
    var sc = lang.chars ? new RegExp('[' + lang.chars + ']') : null;
    var rd = lang.reading_chars ? new RegExp('[' + lang.reading_chars + ']') : null;
    var trw = trWords(tr, lang), out = [];
    plainItems(s, sc).forEach(function (item) {
      var h = sc ? scriptHead(item, sc, rd, lang, trw) : latinHead(item, lang, text);
      if (!h) return;
      var word = h[0], kana = h[1], rom = h[2], k = key(word, lang);
      if (!k) return;
      var head = [['fa', word]];
      if (kana) head.push(['fa', kana]);
      if (rom) head.push(['em', rom]);
      var kind = 'plain', rest = item.slice(h[3]), v = plainVerb(rest, sc, rd, lang, trw);
      if (v) {
        kind = 'vb'; rest = v[1];
        (lang.vb_labels || []).forEach(function (lab, i) {
          var st = v[0][i];
          if (!st) return;
          head.push(['txt', ' · ' + lab + ' '], ['fa', st[0]]);
          if (st[1]) head.push(['em', st[1]]);
        });
      }
      var meaning = rstripChars(tidy(rest).replace(PLAIN_LEAD, ''), ' ,');
      out.push({kind: kind, word: word, rom: rom, head: head, key: k, meaning: meaning});
    });
    return out;
  }
  /* texparse.voc_line_entries: any line -- a line with a \dw \vb \bw \pw by
     entries (and throwing as it does), any other by plainEntries */
  function lineEntries(s, lang, text, tr) {
    if (ENTRY_MACRO.test(typeof s === 'string' ? s : '')) return entries(s, lang);
    return plainEntries(s, lang, text, tr);
  }

  root.ParsehVocline = {isMacro: isMacro, parse: parse, render: render, flatten: flatten,
                        entries: entries, key: key, plainEntries: plainEntries, lineEntries: lineEntries,
                        isNote: isNote, MACROS: MACROS};
})(typeof globalThis !== 'undefined' ? globalThis : this);
