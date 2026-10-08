// SPDX-License-Identifier: GPL-3.0-or-later
/* THE MODEL'S ANSWERS, ONE BY ONE (a0.5.1).  What a review method says about the words it was asked
   about -- a chatbot's pasted answer, a connected model, LM likelihood, a second look by Whisper -- and
   the walk through it that asks, for each, whether to take it.

   FOUR OUTCOMES, so that nothing a model decided goes unsaid:
     change   the model proposes another word (it says how sure it is, where the method asks it to)
     agree    the model looked and says Whisper's word is right
     unsure   the model kept Whisper's word without agreeing: it could not tell
     none     no answer for the word: the answer left it out, was malformed, or the call failed
   A word the model kept used to vanish: the importer dropped every row that left the word as it was,
   with its reason, and the review showed no mark.  Now each one is listed, marked and explained.

   READ LOOSELY is not a fifth outcome but a note on any of them.  A pasted answer is read generously
   -- a line picked out of a reply of several, a row without its "sure", a change reaching past the word
   -- and wherever that generosity was used the word says so (`result.allowances`, {word id: [say]}),
   wears a ≈, and can be asked again by itself.  A person who skims such a word sees that the answer
   was not a clean one; a word whose answer was clean carries nothing.

   THE WALK is a card at a time, in the order of the transcript: the caption with the word marked, what
   Whisper heard and how sure it was, what the model says and why, and the choices -- Accept, Keep
   Whisper's, Write my own, Skip, Back.  By default it stops at what needs a decision or a doubt (every
   proposal, every "not sure", every "no answer"); the words the model agrees with are listed, with its
   reason, and a switch adds them to the walk.  Two buttons take the model's edits all at once -- all of
   them, or only those it was sure of, leaving the walk for the rest.

   It owns no data.  A choice goes into the review's own draft (asrreview.js: `decisions` for a
   proposal taken, `manualEdits` for a word written, the fixed words) and the two things only the walk
   knows -- the words kept and the words skipped -- are kept in the draft with them (`walk`).  The page
   gives it what it needs through `api` (see create()). */
(function () {
  'use strict';
  function el(tag, text, cls) { var n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; }
  function btn(text, fn, cls) { var b = el('button', text, 'wbtn small quiet' + (cls ? ' ' + cls : '')); b.type = 'button'; b.addEventListener('click', fn); return b; }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function score(w) { return typeof w.asr_confidence === 'number' ? w.asr_confidence.toFixed(2) : 'no score'; }
  var LOOSE = '≈';
  // why Whisper's second look could not be made (lib/whispersecond.py REASONS)
  var SECOND = {
    'missing-timestamps': 'The first pass did not give this word a usable time.',
    'no-word-result': 'The second look did not return any word.',
    'ambiguous-alignment': 'What the second look heard could not be safely matched to this word.',
    'transcription-failed': 'Whisper could not transcribe this stretch of the sound.',
    'worker-stopped': 'The second-pass worker stopped before it reached this word.'
  };
  function quoted(t) { return '“' + t + '”'; }

  /* THE WORDS WHOSE ANSWER WAS READ LOOSELY: {word id: [say]}.  From the importers (`result.allowances`), and from a comparison
     by LM likelihood that could not be finished, whose winner is then one among the candidates that could be scored. */
  function loose(m) {
    var res = m.result || null, out = {};
    if (!res) return out;
    var scope = res.latest_word_ids || res.reviewed_word_ids, latest = null;
    if (scope) { latest = {}; scope.forEach(function (id) { latest[id] = true; }); }
    function add(id, say) {
      if (!m.words[id] || m.locked[id] || latest && !latest[id]) return;
      var list = out[id] = out[id] || [];
      if (list.indexOf(say) < 0) list.push(say);
    }
    Object.keys(res.allowances || {}).forEach(function (id) { (res.allowances[id] || []).forEach(function (say) { add(id, say); }); });
    Object.keys(m.suggestions || {}).forEach(function (key) {
      var s = m.suggestions[key], c = s.likelihood && s.likelihood.coverage;
      if (!c || c.state === 'complete') return;
      var omitted = c.omitted || [], texts = omitted.map(function (o) { return quoted(o.text); }).join(', ');
      var say = 'the comparison was not finished' + (omitted.length ? ': ' + texts + ' could not be scored, so the winner is only the best of the others' + (omitted[0].reason ? ' (' + omitted[0].reason + ')' : '') : '');
      (s.word_ids || [s.word_id]).forEach(function (id) { add(id, say); });
    });
    return out;
  }

  /* WHAT BECAME OF EACH WORD.  m = {words: {id: word}, suggestions: {id: proposal}, result, review, locked}
     -> [item] in the order of the transcript.  An item is {kind, anchor, ids, word, candidates, rating,
     reason, sure, implicit, key}: `candidates` the texts the model offers (for a change), `rating` what
     the model said of itself ('sure', 'unsure' or null), `sure` that as true, false or null (not rated),
     `key` where the draft keeps a choice about it (the proposal's word id, or the word's own). */
  function outcomes(m) {
    var res = m.result || null, review = m.review || {}, words = m.words, out = [], covered = {};
    if (!res && review.last_method !== 'whisper-second') return out;
    function at(id) { return words[id] ? words[id].span_start : 0; }
    function free(ids) { return !ids.some(function (id) { return m.locked[id] || covered[id]; }); }
    function take(ids) { ids.forEach(function (id) { covered[id] = true; }); }
    function suspect(w) { return w && (w.low_asr_score || w.dictionary_miss); }
    if (review.last_method === 'whisper-second') {
      // a second look by Whisper: a better word it heard, or the same word again, or a failure
      (review.last_word_ids || []).forEach(function (id) {
        var w = words[id], p = w && w.second_pass;
        if (!w || !p || m.locked[id] || covered[id]) return;
        take([id]);
        if (p.state === 'failed') { out.push({kind: 'none', anchor: id, ids: [id], word: w, candidates: [], rating: null, reason: SECOND[p.reason] || '', sure: null, key: id}); return; }
        if (p.state !== 'complete') return;
        var best = p.best_candidate;
        out.push(!best || best === w.text
          ? {kind: 'agree', anchor: id, ids: [id], word: w, candidates: [], rating: null, reason: 'Whisper heard the same word again on a second pass.', sure: null, implicit: true, key: id}
          : {kind: 'change', anchor: id, ids: [id], word: w, candidates: [{text: best, reason: ''}], rating: null, sure: null, second: true, key: id,
             reason: 'Whisper heard this word differently on a second pass.'});
      });
    } else {
      // the words the latest method covered (an older result that says nothing of it covers them all)
      var scope = res.latest_word_ids || res.reviewed_word_ids, latest = null;
      if (scope) { latest = {}; scope.forEach(function (id) { latest[id] = true; }); }
      var seen = {};
      Object.keys(m.suggestions).forEach(function (id) {
        var s = m.suggestions[id], anchor = s.word_id, ids = s.word_ids || [anchor];
        if (seen[anchor] || latest && !ids.some(function (x) { return latest[x]; }) || !free(ids)) return;
        seen[anchor] = true; take(ids);
        var w = words[anchor], candidates = s.candidates.map(function (c) { return {text: c.text, reason: c.reason || '', rank: c.rank, applicable: c.applicable}; });
        var rating = s.rating || null, sure = rating === 'sure' ? true : rating === 'unsure' ? false : null, kind = 'change', reason = s.reason || (candidates[0] && candidates[0].reason) || '';
        if (s.likelihood) {
          // LM likelihood ranks candidates, the original among them: its winner is the answer, and a tie or an
          // incomplete comparison is not a clear one
          var clear = s.likelihood.coverage.state === 'complete' && s.likelihood.tied_best.length === 1;
          var winner = candidates.filter(function (c) { return c.applicable && c.rank === 1; })[0];
          sure = clear && !!winner;
          rating = null;
          if (winner && w && winner.text === w.text) kind = clear ? 'agree' : 'unsure';
          else if (!winner) kind = 'unsure';
          reason = reason || (kind === 'agree' ? 'Its likelihood is the highest of the candidates.' : clear ? 'Its likelihood is the highest of the candidates.' : 'No clear winner: a tie, or a comparison that could not be finished.');
          if (winner) candidates = [winner].concat(candidates.filter(function (c) { return c !== winner; }));
        }
        out.push({kind: kind, anchor: anchor, ids: ids.slice(), word: w, proposal: s, candidates: candidates, rating: rating, reason: reason, sure: sure, key: anchor});
      });
      (res.kept || []).forEach(function (k) {
        var ids = k.word_ids || [], anchor = ids[0];
        if (!ids.length || !words[anchor] || !free(ids)) return;
        take(ids);
        out.push({kind: k.rating === 'sure' ? 'agree' : 'unsure', anchor: anchor, ids: ids.slice(), word: words[anchor], candidates: [], rating: k.rating || null,
          reason: k.reason || '', sure: k.rating === 'sure' ? true : k.rating === 'unsure' ? false : null, noRating: !k.rating, key: anchor});
      });
      (res.failed_word_ids || []).forEach(function (id) {
        var w = words[id];
        if (!w || m.locked[id] || covered[id]) return;
        take([id]);
        out.push({kind: 'none', anchor: id, ids: [id], word: w, candidates: [], rating: null, reason: (res.failed_reasons || {})[id] || '', sure: null, key: id});
      });
      // the sentence methods return a sentence, not a row for each word: a flagged word they gave back unchanged is
      // one they let stand
      if (res.task === 'suspect' || res.task === 'full') {
        (res.reviewed_word_ids || []).forEach(function (id) {
          var w = words[id];
          if (!w || !suspect(w) || m.locked[id] || covered[id]) return;
          take([id]);
          out.push({kind: 'agree', anchor: id, ids: [id], word: w, candidates: [], rating: null, reason: 'The model gave this word back unchanged.', sure: null, implicit: true, key: id});
        });
      }
    }
    // what each answer was read loosely for
    var notes = loose(m);
    out.forEach(function (i) {
      i.notes = [];
      i.ids.forEach(function (id) { (notes[id] || []).forEach(function (say) { if (i.notes.indexOf(say) < 0) i.notes.push(say); }); });
    });
    return out.sort(function (a, b) { return at(a.anchor) - at(b.anchor); });
  }

  var HEAD = {
    change: function (i) { return i.sure === true ? 'The model corrects this word, and is sure' : i.sure === false ? 'The model suggests a correction, but is not sure' : 'The model suggests a correction'; },
    agree: function (i) { return i.implicit ? 'The model left this word as Whisper wrote it' : 'The model says Whisper’s word is right'; },
    unsure: function (i) { return i.proposal ? 'The model could not decide between the candidates' : 'The model kept Whisper’s word but is not sure of it'; },
    none: function () { return 'The model gave no answer for this word'; }
  };
  var MARK = {change: '✎', agree: '✔', unsure: '?', none: '✗', loose: LOOSE};

  /* THE WALK.  api = {
       data()                 -> {words, suggestions, result, review, locked, decisions, manualEdits}, fresh each time
       walk()                 -> {kept: {id: true}, skipped: {id: true}, includeAgree: bool}, the page's own object (it is saved)
       touched(ids)           -> 'accepted' | 'own' | null: what the draft already says of these words
       accept(item, index)    take the candidate; keep(item) keep Whisper's word; own(item, text); undo(item) take back any choice
       changed()              the draft moved: repaint the words, save it
       caption(wordId)        the caption {text, start, end, words} the word is in
       show(word), listen(word)   put the word in view; play it
       ask(ids)               ask the model again for these words only (the page chooses how: the pasted-answer prompt, the endpoint...)
       use()                  press "Use this transcript"
       phase()                'review', 'external', 'correcting'...
     } */
  function create(api) {
    var st = {open: false, ending: false, history: [], revisit: false, chip: null, writing: false, error: '', note: '', signature: '', host: null};

    function all() { return outcomes(api.data()); }
    function looseWords() { return loose(api.data()); }
    function counts(list) {
      var n = {change: 0, agree: 0, unsure: 0, none: 0, sure: 0, notsure: 0, rated: 0, loose: Object.keys(looseWords()).length};
      list.forEach(function (i) {
        n[i.kind]++;
        if (i.kind !== 'agree' && i.kind !== 'none') { if (i.sure === true) n.sure++; else n.notsure++; }
        if (i.sure !== null) n.rated++;
      });
      return n;
    }
    function status(item) {
      var w = api.walk(), d = api.touched(item.ids);
      return w.kept[item.anchor] ? 'kept' : d || (w.skipped[item.anchor] ? 'skipped' : null);
    }
    function wanted(item) { return item.kind !== 'agree' || api.walk().includeAgree; }
    function pending(list) {
      return list.filter(function (i) { var s = status(i); return wanted(i) && (!s || (s === 'skipped' && st.revisit)); });
    }
    function bestIndex(item) { return item.candidates.length ? 0 : -1; }
    function proposalIndex(item) {
      // the candidate's place among the proposal's own, for the draft
      if (!item.proposal) return 0;
      var texts = item.proposal.candidates.map(function (c) { return c.text; });
      return Math.max(0, texts.indexOf(item.candidates[0] && item.candidates[0].text));
    }

    /* ---------------- what a choice does ---------------- */
    function done(item, how, index) {
      var w = api.walk();
      delete w.skipped[item.anchor]; delete w.kept[item.anchor];
      if (how === 'accept') api.accept(item, index);
      else if (how === 'keep') { api.keep(item); w.kept[item.anchor] = true; }
      else if (how === 'skip') w.skipped[item.anchor] = true;
      st.history.push(item.anchor); st.writing = false; st.error = '';
      api.changed(); paint(); focusCard();
    }
    function back() {
      var list = all(), anchor = st.history.pop();
      if (anchor === undefined) return;
      var item = list.filter(function (i) { return i.anchor === anchor; })[0];
      if (item) { api.undo(item); delete api.walk().kept[anchor]; delete api.walk().skipped[anchor]; }
      st.writing = false; st.error = '';
      api.changed(); paint(); focusCard();
    }
    function bulk(onlySure) {
      var list = all(), n = 0;
      list.forEach(function (i) {
        // a "sure" whose answer was read loosely is not taken for the person: it stays to be looked at
        if (i.kind !== 'change' || status(i) || (onlySure && (i.sure !== true || i.notes.length))) return;
        api.accept(i, proposalIndex(i)); n++;
      });
      api.changed(); st.history = []; st.chip = null; st.note = n ? 'Accepted ' + plural(n, 'edit', 'edits') + ' into the draft. ' + (onlySure ? 'The rest are for you to look at.' : '') : 'Nothing to accept.';
      // all of them: what is left is not an edit, so the walk ends at once, with what will change; only the sure
      // ones: the walk goes on with the rest
      st.open = true; st.ending = !onlySure || !pending(all()).length; paint(); focusCard();
    }
    function ask(ids) { st.open = false; st.ending = false; st.note = ''; paint(); api.ask(ids); }
    function start(revisit) { st.revisit = !!revisit; st.open = true; st.ending = false; st.chip = null; st.history = []; st.note = ''; paint(); focusCard(); }
    function focusCard() { var c = st.host && st.host.querySelector('.stt-walk-card'); if (c) c.focus({preventScroll: false}); }

    /* ---------------- drawing ---------------- */
    function captionLine(item) {
      var seg = api.caption(item.anchor), line = el('p', null, 'stt-walk-caption'); line.dir = 'auto';
      var lang = api.data().review && api.data().review.evidence && api.data().review.evidence.language; if (lang) line.lang = lang;
      if (!seg) { line.appendChild(el('mark', item.word.text)); return line; }
      var cursor = 0, marked = {};
      item.ids.forEach(function (id) { marked[id] = true; });
      seg.words.forEach(function (w) {
        var at = seg.text.indexOf(w.text, cursor); if (at < 0) return;
        line.appendChild(document.createTextNode(seg.text.slice(cursor, at)));
        line.appendChild(marked[w.word_id] ? el('mark', w.text) : document.createTextNode(w.text));
        cursor = at + w.text.length;
      });
      line.appendChild(document.createTextNode(seg.text.slice(cursor)));
      return line;
    }
    // what a reply had to be forgiven for, in the words of the importer: shown wherever the word is looked at
    function looseBlock(says, lead) {
      var box = el('div', null, 'stt-loosenote');
      box.appendChild(el('p', LOOSE + ' ' + lead + ':', 'stt-loosenote-head'));
      var ul = el('ul');
      says.forEach(function (say) { var li = el('li'), b = el('bdi', say.charAt(0).toUpperCase() + say.slice(1) + (/[.!?]$/.test(say) ? '' : '.')); b.dir = 'auto'; li.appendChild(b); ul.appendChild(li); });
      box.appendChild(ul);
      box.appendChild(el('p', 'If the word matters, ask again for it by itself.', 'fieldnote'));
      return box;
    }
    function card(list, todo) {
      var item = todo[0], w = item.word, box = el('div', null, 'stt-walk-card'), d = api.data();
      box.tabIndex = -1; box.setAttribute('role', 'group');
      var total = todo.length + st.history.length, at = st.history.length + 1;
      box.setAttribute('aria-label', 'Answer ' + at + ' of ' + total);
      var tally = {accepted: 0, kept: 0, skipped: 0};
      list.forEach(function (i) { var s = status(i); if (s === 'accepted' || s === 'own') tally.accepted++; else if (s === 'kept') tally.kept++; else if (s === 'skipped') tally.skipped++; });
      box.appendChild(el('p', 'Answer ' + at + ' of ' + total + ' · ' + tally.accepted + ' taken · ' + tally.kept + ' kept as Whisper wrote them · ' + tally.skipped + ' skipped', 'stt-walk-count'));
      var bar = el('progress'); bar.max = total; bar.value = at - 1; bar.setAttribute('aria-label', 'Answers looked at'); box.appendChild(bar);
      var head = el('h4', MARK[item.kind] + ' ' + HEAD[item.kind](item), 'stt-walk-head stt-walk-' + item.kind); box.appendChild(head);
      box.appendChild(captionLine(item));
      var heard = el('p', null, 'stt-walk-heard'); heard.appendChild(document.createTextNode('Whisper heard '));
      var said = el('bdi', item.ids.length > 1 && item.proposal ? item.proposal.original : w.text); said.dir = 'auto'; heard.appendChild(said);
      var facts = [];
      if (item.ids.length === 1) facts.push('score ' + score(w));
      if (w.low_asr_score) facts.push('⚠ low score');
      if (w.dictionary_miss) facts.push('◇ not in the dictionary');
      heard.appendChild(document.createTextNode(' · ' + facts.join(' · ')));
      box.appendChild(heard);
      if (item.kind === 'change' || (item.kind === 'unsure' && item.candidates.length)) {
        var offer = el('ul', null, 'stt-walk-offers');
        item.candidates.forEach(function (c, n) {
          var li = el('li'), t = el('bdi', c.text); t.dir = 'auto'; t.className = 'stt-walk-offer';
          li.appendChild(document.createTextNode(n === 0 ? 'The model proposes ' : 'Another candidate '));
          li.appendChild(t);
          if (n === 0 && item.rating) li.appendChild(el('span', item.rating === 'sure' ? ' · sure' : ' · not sure', 'stt-walk-rating stt-walk-' + item.rating));
          if (n > 0 || item.kind === 'unsure') li.appendChild(btn('Use this one', function () { done(item, 'accept', item.proposal ? Math.max(0, item.proposal.candidates.map(function (x) { return x.text; }).indexOf(c.text)) : 0); }));
          offer.appendChild(li);
        });
        box.appendChild(offer);
      } else if (item.rating) box.appendChild(el('p', 'The model is ' + (item.rating === 'sure' ? 'sure' : 'not sure') + ' of this.', 'stt-walk-rating stt-walk-' + item.rating));
      else if (item.noRating) box.appendChild(el('p', 'The model gave no confidence for this word, so it counts as not sure.', 'fieldnote'));
      if (item.reason) { var why = el('p', null, 'stt-walk-reason'); why.appendChild(el('span', item.kind === 'none' ? 'Why there is no answer: ' : 'Why: ', 'fieldnote')); var r = el('bdi', item.reason); r.dir = 'auto'; why.appendChild(r); box.appendChild(why); }
      if (item.notes.length) box.appendChild(looseBlock(item.notes, 'The model’s answer for this word was read loosely'));
      if (item.kind === 'none') box.appendChild(el('p', 'Whisper’s word stays unless you change it here. “Ask again for this word” asks the model for it alone.', 'fieldnote'));
      var actions = el('div', null, 'stt-walk-actions');
      var listen = btn('▶ Listen (P)', function () { api.listen(w); }); listen.setAttribute('aria-keyshortcuts', 'P'); actions.appendChild(listen);
      if (item.kind === 'change' && item.candidates.length) {
        var accept = btn('Accept “' + item.candidates[0].text + '” (A)', function () { done(item, 'accept', proposalIndex(item)); }, 'go'); accept.setAttribute('aria-keyshortcuts', 'A'); actions.appendChild(accept);
      }
      var keep = btn(item.kind === 'agree' ? 'Keep it (K)' : 'Keep Whisper’s word (K)', function () { done(item, 'keep'); }); keep.setAttribute('aria-keyshortcuts', 'K'); actions.appendChild(keep);
      var write = btn('Write my own (W)', function () { st.writing = !st.writing; st.error = ''; paint(); var input = st.host.querySelector('.stt-walk-own input'); if (input) input.focus(); });
      write.setAttribute('aria-keyshortcuts', 'W'); actions.appendChild(write);
      var skip = btn('Skip (S)', function () { done(item, 'skip'); }); skip.setAttribute('aria-keyshortcuts', 'S'); actions.appendChild(skip);
      if (item.notes.length || item.kind === 'none') {
        var again = btn('Ask again for this word (R)', function () { ask(item.ids); }); again.id = 'stt_walk_ask'; again.setAttribute('aria-keyshortcuts', 'R'); actions.appendChild(again);
      }
      var undo = btn('← Back', back); undo.disabled = !st.history.length; undo.setAttribute('aria-keyshortcuts', 'ArrowLeft'); actions.appendChild(undo);
      box.appendChild(actions);
      if (st.writing) {
        var own = el('div', null, 'stt-walk-own'), label = el('label', item.ids.length > 1 ? 'Enter the corrected words ' : 'Enter the correct word '), input = el('input');
        input.type = 'text'; input.dir = 'auto'; input.maxLength = 200; input.value = item.candidates[0] ? item.candidates[0].text : (item.ids.length > 1 && item.proposal ? item.proposal.original : w.text);
        label.appendChild(input); own.appendChild(label);
        var say = el('p', st.error, 'stt-walk-error'); say.setAttribute('role', 'status'); say.setAttribute('aria-live', 'polite');
        function use() {
          var value = input.value.trim();
          if (!value || item.ids.length === 1 && /\s/.test(value) || Array.from(value).length > 200 || /[\x00-\x1f]/.test(value)) { st.error = 'Enter a nonempty word, without line breaks.'; say.textContent = st.error; return; }
          if (value === (item.ids.length > 1 && item.proposal ? item.proposal.original : w.text)) { done(item, 'keep'); return; }
          api.own(item, value); st.history.push(item.anchor); st.writing = false; st.error = ''; api.changed(); paint(); focusCard();
        }
        input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); use(); } else if (e.key === 'Escape') { e.preventDefault(); st.writing = false; paint(); } });
        own.appendChild(btn('Use this word', use)); own.appendChild(btn('Cancel', function () { st.writing = false; paint(); })); own.appendChild(say);
        box.appendChild(own);
      }
      return box;
    }
    function ending(list) {
      var box = el('div', null, 'stt-walk-card stt-walk-end'), n = {accepted: 0, own: 0, kept: 0, skipped: 0, none: 0};
      box.tabIndex = -1; box.setAttribute('role', 'group'); box.setAttribute('aria-label', 'All answers looked at');
      list.forEach(function (i) { var s = status(i); if (s) n[s]++; else if (i.kind === 'none') n.none++; });
      box.appendChild(el('h4', 'All the answers have been looked at', 'stt-walk-head'));
      box.appendChild(el('p', plural(n.accepted, 'edit', 'edits') + ' taken from the model · ' + plural(n.own, 'word', 'words') + ' written by you · ' +
        n.kept + ' kept as Whisper wrote ' + (n.kept === 1 ? 'it' : 'them') + ' · ' + n.skipped + ' skipped · ' + n.none + ' with no answer left as they are.', 'stt-walk-count'));
      var edits = draftEdits();
      if (edits.length) {
        box.appendChild(el('p', 'This is what will change in the transcript:'));
        var ul = el('ul', null, 'stt-walk-changes');
        edits.forEach(function (e) {
          var li = el('li'), from = el('bdi', e.from), to = el('bdi', e.to); from.dir = to.dir = 'auto';
          li.appendChild(el('span', e.clock + ' ', 'stt-review-clock')); li.appendChild(from); li.appendChild(document.createTextNode(' → ')); li.appendChild(to);
          ul.appendChild(li);
        });
        box.appendChild(ul);
      } else box.appendChild(el('p', 'Nothing will change in the transcript.'));
      var wobbly = Object.keys(looseWords());
      if (wobbly.length) box.appendChild(el('p', LOOSE + ' ' + plural(wobbly.length, 'word', 'words') + ' had an answer that was read loosely (marked ' + LOOSE + ' in the transcript). You can use the transcript as it is, or ask again for ' + (wobbly.length === 1 ? 'it' : 'them') + '.', 'fieldnote'));
      var actions = el('div', null, 'stt-walk-actions');
      var use = btn('Use this transcript', function () { api.use(); }, 'go'); use.id = 'stt_walk_use'; use.disabled = api.phase() === 'correcting'; actions.appendChild(use);
      if (n.skipped) actions.appendChild(btn('Go back to the ' + n.skipped + ' skipped', function () { start(true); }));
      if (wobbly.length) { var askLoose = btn('Ask again for the ' + plural(wobbly.length, 'word', 'words') + ' read loosely', function () { ask(wobbly); }); askLoose.id = 'stt_walk_ask_ending'; actions.appendChild(askLoose); }
      if (!api.walk().includeAgree && list.some(function (i) { return i.kind === 'agree' && !status(i); })) actions.appendChild(btn('Look at the words the model agrees with', function () { api.walk().includeAgree = true; api.changed(); start(false); }));
      actions.appendChild(btn('Close', function () { st.open = false; paint(); }));
      box.appendChild(actions);
      return box;
    }
    function draftEdits() {
      var d = api.data(), res = [], chars = d.text || '';
      function span(a, b) { return Array.from(chars).slice(a, b).join(''); }
      Object.keys(d.decisions).forEach(function (id) {
        var w = d.words[id], s = d.suggestions[id]; if (!w || !s || !s.candidates[d.decisions[id]]) return;
        var a = s.span_start == null ? w.span_start : s.span_start, b = s.span_end == null ? w.span_end : s.span_end;
        res.push({at: a, clock: api.clock(w), from: span(a, b), to: s.candidates[d.decisions[id]].text});
      });
      Object.keys(d.manualEdits).forEach(function (id) {
        var w = d.words[id], v = d.manualEdits[id]; if (!w) return;
        var ids = typeof v === 'object' ? v.word_ids : [id], last = d.words[ids[ids.length - 1]];
        res.push({at: w.span_start, clock: api.clock(w), from: span(w.span_start, last.span_end), to: typeof v === 'object' ? v.text : v});
      });
      return res.sort(function (a, b) { return a.at - b.at; });
    }
    // the words whose answer was read loosely, each with what it was forgiven for and its own "ask again"
    function looseList() {
      var map = looseWords(), words = api.data().words, ids = Object.keys(map).sort(function (a, b) { return words[a].span_start - words[b].span_start; });
      var box = el('div', null, 'stt-walk-list stt-walk-loose-list');
      if (!ids.length) { box.appendChild(el('p', 'None.', 'fieldnote')); return box; }
      var every = btn('Ask again for these ' + plural(ids.length, 'word', 'words'), function () { ask(ids); }, 'go'); every.id = 'stt_walk_ask_all'; box.appendChild(every);
      var ul = el('ul');
      ids.forEach(function (id) {
        var li = el('li'), open = btn(LOOSE + ' ' + words[id].text, function () { api.show(words[id]); api.listen(words[id]); }, 'stt-walk-word');
        li.appendChild(open);
        var r = el('bdi', ' — ' + map[id].join('; ')); r.dir = 'auto'; li.appendChild(r);
        li.appendChild(btn('Ask again', function () { ask([id]); }));
        ul.appendChild(li);
      });
      box.appendChild(ul);
      return box;
    }
    function chipList(list, kind) {
      if (kind === 'loose') return looseList();
      var box = el('div', null, 'stt-walk-list'), rows = list.filter(function (i) { return kind === 'notsure' ? (i.kind !== 'agree' && i.kind !== 'none' && i.sure !== true) : kind === 'sure' ? (i.kind === 'change' && i.sure === true) : i.kind === kind; });
      if (!rows.length) { box.appendChild(el('p', 'None.', 'fieldnote')); return box; }
      var ul = el('ul');
      rows.forEach(function (i) {
        var li = el('li'), open = btn(MARK[i.kind] + ' ' + (i.word ? i.word.text : ''), function () { api.show(i.word); api.listen(i.word); }, 'stt-walk-word');
        li.appendChild(open);
        if (i.kind === 'change' && i.candidates[0]) li.appendChild(document.createTextNode(' → ' + i.candidates[0].text));
        if (i.rating) li.appendChild(el('span', ' · ' + (i.rating === 'sure' ? 'sure' : 'not sure'), 'stt-walk-rating stt-walk-' + i.rating));
        if (i.reason) { var r = el('bdi', ' — ' + i.reason); r.dir = 'auto'; li.appendChild(r); }
        var s = status(i); if (s) li.appendChild(el('span', ' · ' + (s === 'accepted' ? 'taken' : s === 'own' ? 'your word' : s === 'kept' ? 'kept' : 'skipped'), 'fieldnote'));
        ul.appendChild(li);
      });
      box.appendChild(ul);
      return box;
    }
    function paint() {
      var host = st.host; if (!host) return;
      // a repaint (the draft moved, a choice was made) replaces the card: a person who was on it stays on it
      var onCard = host.contains(document.activeElement) && document.activeElement.classList.contains('stt-walk-card');
      host.textContent = '';
      var list = all();
      host.hidden = !list.length && !Object.keys(looseWords()).length;
      if (host.hidden) return;
      var n = counts(list), todo = pending(list);
      host.appendChild(el('h4', 'The model’s answers'));
      var sum = el('p', null, 'stt-walk-summary');
      sum.appendChild(document.createTextNode(plural(list.length, 'word', 'words') + ' checked: '));
      [['change', plural(n.change, 'edit', 'edits') + ' proposed' + (n.rated ? ' (' + n.sure + ' sure, ' + (n.change - n.sure) + ' not sure)' : '')], ['agree', n.agree + ' agree with Whisper'],
       ['unsure', n.unsure + ' not sure either way'], ['none', n.none + ' with no answer']].concat(n.loose ? [['loose', n.loose + ' read loosely']] : []).forEach(function (c, at) {
        var chip = btn(MARK[c[0]] + ' ' + c[1], function () { st.chip = st.chip === c[0] ? null : c[0]; paint(); }, 'stt-walk-chip stt-walk-' + c[0]);
        chip.setAttribute('aria-pressed', st.chip === c[0] ? 'true' : 'false'); chip.disabled = !n[c[0]]; sum.appendChild(chip);
      });
      host.appendChild(sum);
      if (st.chip) host.appendChild(chipList(list, st.chip));
      var bar = el('div', null, 'stt-walk-bulk'), editable = api.phase() !== 'correcting', open = list.filter(function (i) { return i.kind === 'change' && !status(i); });
      var walking = st.open && !st.ending && todo.length;
      var go = btn(todo.length ? 'Go through the answers (' + todo.length + ')' : 'Go through the answers', function () { start(false); }, 'go'); go.id = 'stt_walk_start'; go.disabled = !editable || !todo.length && !list.some(function (i) { return status(i) === 'skipped'; }); go.hidden = !!walking; bar.appendChild(go);
      var sure = open.filter(function (i) { return i.sure === true && !i.notes.length; });
      // each button is there while it has something to do
      if (n.rated && sure.length) { var some = btn('Accept the ' + sure.length + ' sure ' + (sure.length === 1 ? 'edit' : 'edits') + ', then look at the rest', function () { bulk(true); }); some.id = 'stt_walk_sure'; some.disabled = !editable; bar.appendChild(some); }
      if (open.length) { var every = btn('Accept all ' + open.length + ' ' + (open.length === 1 ? 'edit' : 'edits') + ' the model proposed', function () { bulk(false); }); every.id = 'stt_walk_all'; every.disabled = !editable; bar.appendChild(every); }
      var agree = el('label', 'Also walk through the words the model agrees with '), box = el('input'); box.type = 'checkbox'; box.id = 'stt_walk_agree'; box.checked = !!api.walk().includeAgree;
      box.addEventListener('change', function () { api.walk().includeAgree = box.checked; api.changed(); paint(); }); agree.appendChild(box); bar.appendChild(agree);
      host.appendChild(bar);
      if (st.note) host.appendChild(el('p', st.note, 'fieldnote stt-walk-note'));
      if (st.open) {
        var shown = st.ending ? [] : pending(list);
        host.appendChild(shown.length ? card(list, shown) : ending(list));
        if (shown.length) api.show(shown[0].word);
      }
      if (onCard) focusCard();
    }
    return {
      /* draw into `host` (hidden when the review has nothing the model said); `fresh` is a result that has just
         come in: the walk opens by itself, once, when there is something to decide */
      mount: function (host, fresh) {
        st.host = host;
        host.addEventListener('keydown', function (e) {
          if (!st.open || e.ctrlKey || e.metaKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
          var list = all(), todo = pending(list), item = todo[0];
          if (!item) return;
          var key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
          if (key === 'a' && item.kind === 'change' && item.candidates.length) done(item, 'accept', proposalIndex(item));
          else if (key === 'k') done(item, 'keep');
          else if (key === 's') done(item, 'skip');
          else if (key === 'w') { st.writing = true; paint(); var input = host.querySelector('.stt-walk-own input'); if (input) input.focus(); }
          else if (key === 'r' && (item.notes.length || item.kind === 'none')) ask(item.ids);
          else if (key === 'p') api.listen(item.word);
          else if (key === 'ArrowLeft') back();
          else return;
          e.preventDefault();
        });
        var sig = all().map(function (i) { return i.kind + i.anchor; }).join(',');
        var isNew = fresh && sig !== st.signature && sig !== '';
        st.signature = sig;
        if (isNew && api.phase() === 'review' && pending(all()).length) { st.open = true; st.ending = false; st.revisit = false; st.history = []; st.note = ''; paint(); focusCard(); return; }
        paint();
      },
      repaint: paint, outcomes: all, counts: function () { return counts(all()); },
      // {word id: item} for the words the model said something about, made once for a repaint of the transcript
      marks: function () { var m = {}; all().forEach(function (i) { i.ids.forEach(function (id) { m[id] = i; }); }); return m; },
      // {word id: [say]} for the words whose answer was read loosely, whether or not the model's outcome for them is a card
      loose: looseWords,
      open: function () { start(false); },
      // the list of one kind of word (a chip of the summary), shown without walking
      show: function (kind) { st.chip = kind; paint(); }
    };
  }
  window.ParsehAsrWalk = {create: create, outcomes: outcomes, loose: loose, MARK: MARK, HEAD: HEAD, LOOSE: LOOSE};
})();
