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

  root.ParsehVocline = {isMacro: isMacro, parse: parse, render: render, flatten: flatten,
                        entries: entries, key: key, MACROS: MACROS};
})(typeof globalThis !== 'undefined' ? globalThis : this);
