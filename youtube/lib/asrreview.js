// SPDX-License-Identifier: GPL-3.0-or-later
/* Pending browser review. All text is textContent; source offsets are Unicode code points. */
(function () {
  'use strict';
  function el(tag, text, cls) { var n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; }
  function btn(text, fn) { var b = el('button', text, 'wbtn small quiet'); b.type = 'button'; b.addEventListener('click', fn); return b; }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function time(n) { return typeof n === 'number' ? n.toFixed(2) + ' s' : 'unavailable'; }
  function estimate(n) { return typeof n === 'number' ? n.toFixed(2) : 'unavailable'; }
  function captionTime(n) {
    if (typeof n !== 'number') return 'Time unavailable';
    var total = Math.max(0, Math.round(n * 100)), seconds = Math.floor(total / 100), fraction = total % 100;
    var minutes = Math.floor(seconds / 60), hours = Math.floor(minutes / 60);
    function two(value) { return String(value).padStart(2, '0'); }
    return (hours ? hours + ':' + two(minutes % 60) : String(minutes)) + ':' + two(seconds % 60) + (fraction ? '.' + two(fraction) : '');
  }
  function mount(root, opts) {
    var result = null, phase = '', config = null, decisions = {}, manualEdits = {}, suggestions = {}, words = {}, selected = null;
    var choice, inspect, details, preview, status, use, responses, retry, useSkill = false, useBusy = false, disabledBefore = [];
    var wordButtons = {}, captions = {}, captionRows = [], filter = 'all', search = '', summary, activeCaption = null;
    var dictionaryCache = new Map(), editRanges = {};
    // the model's answers, walked through one by one (asrwalk.js): which it kept as Whisper wrote them and which it skipped
    var walkState = {kept: {}, skipped: {}, includeAgree: false}, walkCtl = null, walkHost = null;
    var locked = {}, selection = [], selecting = false, scope = 'all', phonetic = true, scopeNote, saveTimer, saveQueue = Promise.resolve(), hydrated = false;
    function snapshot() { return {decisions: Object.assign({}, decisions), manual_edits: Object.assign({}, manualEdits), locked_word_ids: Object.keys(locked), selection: selection.length === 2 ? selection.slice() : [], scope: scope, selected_word: selected, phonetic_filter: phonetic, external_drafts: Object.assign({}, externalDrafts),
      walk: {kept: Object.keys(walkState.kept), skipped: Object.keys(walkState.skipped), include_agree: !!walkState.includeAgree}}; }
    function saveNow() {
      if (saveTimer) clearTimeout(saveTimer);
      if (!opts.save || !result) return Promise.resolve();
      var snap = snapshot();
      saveQueue = saveQueue.catch(function () {}).then(function () { return opts.save(snap); });
      return saveQueue;
    }
    function autosave() {
      if (!opts.save || !result || phase === 'correcting') return;
      if (saveTimer) clearTimeout(saveTimer);
      saveTimer = setTimeout(function () { saveNow().catch(function (e) { if (status) status.textContent = e.message || 'Draft could not be saved. Keep this page open.'; }); }, 400);
    }
    function inScope(w) {
      var bounds = selection.length === 2 ? selection.map(function (id) { return words[id].span_start; }).sort(function (a,b) { return a-b; }) : null;
      return scope !== 'selection' || bounds && w.span_start >= bounds[0] && w.span_start <= bounds[1];
    }
    function targetIds(task, one) {
      return Object.keys(words).filter(function (id) {
        var w = words[id];
        return w.reviewable && !locked[id] && (!one || id === one) &&
          (one || inScope(w)) &&
          (one || task === 'full' || task === 'workspace' || suspect(w));
      });
    }
    function keepAccepted() {
      Object.keys(decisions).forEach(function (id) { var proposal = suggestions[id];
        if (proposal && proposal.candidates[decisions[id]]) {
          var ids = proposal.word_ids || [id], value = proposal.candidates[decisions[id]].text;
          manualEdits[id] = ids.length > 1 ? {text:value,word_ids:ids.slice()} : value;
        }
      }); decisions = {};
    }
    function runMethod(mode, task, one) {
      var ids = targetIds(task, one);
      if (mode === 'whisper-second' && !one) ids = ids.filter(function (id) { return !words[id].second_pass || words[id].second_pass.state !== 'complete'; });
      if (ids && !ids.length) { status.textContent = 'No unlocked words to review in this section.'; return; }
      keepAccepted();
      saveNow().then(function () { if (opts.choose) opts.choose(mode, task === 'workspace' ? false : useSkill, task, ids, {phonetic_filter:phonetic}); }, function (e) { status.textContent = e.message || 'Save the draft before starting another method.'; });
    }
    function selectBest() {
      if (result.review.last_method === 'whisper-second') {
        (result.review.last_word_ids || []).forEach(function (id) {
          var w = words[id], best = w && w.second_pass && w.second_pass.best_candidate;
          if (!w || locked[id] || !best || w.second_pass.state !== 'complete') return;
          clearOverlaps([id]); manualEdits[id] = best;
        }); updateDraft(); if (selected) detail(words[selected]); return;
      }
      var reviewed = result.review.result || {}, latest = new Set(reviewed.latest_word_ids || reviewed.reviewed_word_ids || Object.keys(suggestions));
      var done = new Set();
      Object.keys(suggestions).forEach(function (id) { var proposal = suggestions[id], anchor = proposal.word_id, ids = proposal.word_ids || [anchor];
        if (done.has(anchor) || !ids.some(function (member) { return latest.has(member); }) || ids.some(function (member) { return locked[member]; })) return;
        done.add(anchor);
        if (proposal.likelihood && proposal.likelihood.coverage.state !== 'complete') return;
        var index = proposal.candidates.findIndex(function (candidate) { return proposal.likelihood ? candidate.applicable && candidate.rank === 1 : true; });
        if (index < 0 || proposal.likelihood && proposal.likelihood.tied_best.length > 1) return;
        clearOverlaps(ids); decisions[anchor] = index;
      }); updateDraft(); if (selected) detail(words[selected]);
      if (status) status.textContent = 'First choices selected in the pending draft. Check them before using the transcript; locked words and incomplete or tied comparisons were kept.';
    }
    var externalBusy = false, externalTask = 'suspect', externalDivide = false, externalDrafts = {}, externalRow = null, externalAttempt = 0, externalTimer = null;
    function keepExternal(ext) {
      if (externalTimer) clearInterval(externalTimer);
      externalTimer = null;
      if (!ext || ext.finished || !opts.external) return;
      externalTimer = setInterval(function () {
        if (!result || !result.review.external || result.review.external.id !== ext.id || opts.current && !opts.current()) {
          clearInterval(externalTimer); externalTimer = null; return;
        }
        if (externalBusy) return;
        opts.external('keep-alive', {session: ext.id}).catch(function () {
          if (!result || !result.review.external || result.review.external.id !== ext.id) return;
          clearInterval(externalTimer); externalTimer = null;
          var message = root.querySelector('#stt_external_status');
          if (message) message.textContent = 'The pending review could not be kept on the server. Your pasted draft is still here; reconnect before importing.';
        });
      }, 4 * 60 * 1000);
    }
    function externalRequest(action, values, message) {
      if (externalBusy || !opts.external) return;
      externalBusy = true; disableControls(true);
      if (externalRow) externalRow.disable('Preparing external review…');
      var source = result.review.evidence.source_sha256, attempt = ++externalAttempt;
      message.textContent = action === 'answer' ? 'Checking the pasted answer…' : 'Preparing the external review…';
      var ready = Promise.resolve();
      if (action === 'start') { keepAccepted(); ready = saveNow(); }
      ready.then(function () { return opts.external(action, values); }).then(function (view) {
        if (attempt !== externalAttempt) return;
        externalBusy = false; disableControls(false);
        if (!result || result.review.evidence.source_sha256 !== source) return;
        handle.show(view.res, view.state, view.connection);
      }, function (error) {
        if (attempt !== externalAttempt) return;
        externalBusy = false; disableControls(false);
        if (externalRow) externalRow.enable();
        if (root.contains(message)) message.textContent = error.message || 'The external answer could not be imported. Your draft and transcript box are unchanged.';
      });
    }
    function externalControls() {
      var ext = result.review && result.review.external;
      var panel = el('details', null, 'stt-review-external'); panel.id = 'stt_external';
      panel.setAttribute('data-review-disclosure', 'external'); panel.open = !!(ext && !ext.finished);
      panel.appendChild(el('summary', 'Use an external chatbot · copy & paste'));
      panel.appendChild(el('p', 'Choose any chatbot yourself. Copy the prompt, paste its answer below, then go through what it says. This sends text only when you paste or attach it to that service. No configured endpoint is needed.'));
      // WHERE YOU ARE, in five steps: what was one ritual spread over this panel
      var steps = el('ol', null, 'stt-steps'); steps.id = 'stt_external_steps';
      var stepNames = ['Choose the method and prepare the prompt', 'Copy the prompt into your chatbot', 'Paste its answer here and import it', 'Go through the answers', 'Use this transcript'];
      var stepItems = stepNames.map(function (name) { var li = el('li', name); steps.appendChild(li); return li; });
      function setStep(at) {
        stepItems.forEach(function (li, i) { li.className = i < at ? 'done' : i === at ? 'now' : ''; if (i === at) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current'); });
      }
      setStep(!ext ? 0 : ext.finished ? 3 : 1);
      panel.appendChild(steps);
      var label = el('label', 'Review method '), select = el('select'); select.id = 'stt_external_task';
      [['suspect', 'Suspect words · experimental'], ['full', 'Whole text · experimental'], ['workspace', 'Reasoning workspace · experimental']].forEach(function (option) { var node = el('option', option[1]); node.value = option[0]; select.appendChild(node); });
      select.value = ext ? ext.task : externalTask; select.disabled = phase === 'correcting';
      label.appendChild(select); panel.appendChild(label);
      // A reasoning workspace is handed over whole -- its ZIP holds the entire transcript, which is what a workspace is for --
      // unless a person asks for it in pieces: for a chatbot that cannot open files, whose evidence has to be in the prompts
      var divideLabel = el('label', 'Divide into several prompts '), divide = el('input'); divide.type = 'checkbox'; divide.id = 'stt_external_divide';
      divide.checked = externalDivide; divide.disabled = phase === 'correcting'; divideLabel.appendChild(divide);
      var divideNote = el('p', 'Off: one prompt, and the workspace ZIP holds the whole transcript, for a chatbot that can open files. On: the evidence is in the prompts themselves, a part at a time, for a chatbot that cannot. It applies to the next review you prepare.', 'fieldnote');
      function showDivide() { divideLabel.hidden = divideNote.hidden = select.value !== 'workspace'; }
      divide.addEventListener('change', function () { externalDivide = divide.checked; });
      select.addEventListener('change', function () { externalTask = select.value; showDivide(); });
      showDivide(); panel.appendChild(divideLabel); panel.appendChild(divideNote);
      var message = el('p', '', 'stt-review-status'); message.id = 'stt_external_status'; message.setAttribute('role', 'status'); message.setAttribute('aria-live', 'polite');
      var start = btn(ext ? 'Start new external review' : 'Prepare external prompt', function () { externalRequest('start', {task: select.value, word_ids: targetIds(select.value), divide: select.value === 'workspace' && externalDivide}, message); }); start.id = 'stt_external_start'; start.disabled = phase === 'correcting' || !opts.external || !result.review || !result.review.evidence
      panel.appendChild(start);
      if (ext) panel.appendChild(el('p', 'Starting a new review replaces the model’s proposals. Your own edits in the draft stay.', 'fieldnote'));
      if (!result.review || !result.review.evidence) panel.appendChild(el('p', 'This older result has no mapped word evidence. Transcribe again to prepare external review prompts.'));
      // what has come in so far, in the four outcomes (asrwalk.js)
      function answersSoFar() {
        if (!walkCtl) return null;
        var n = walkCtl.counts(), line = el('p', null, 'stt-external-result'); line.id = 'stt_external_result';
        line.appendChild(el('strong', ParsehAsrWalk.MARK.change + ' ' + n.change + ' edits proposed · ' + ParsehAsrWalk.MARK.agree + ' ' + n.agree + ' agree with Whisper · ' + ParsehAsrWalk.MARK.unsure + ' ' + n.unsure + ' not sure either way · ' + ParsehAsrWalk.MARK.none + ' ' + n.none + ' with no answer'));
        return n.change + n.agree + n.unsure + n.none ? line : null;
      }
      if (ext && !ext.finished && ext.batches) {
        var whole = ext.task === 'workspace' && ext.divided === false;
        panel.appendChild(el('p', (whole ? 'The whole transcript' : 'Prompt ' + (ext.index + 1) + ' of ' + ext.batches) + ' · ' + ext.words_done + ' / ' + ext.words_total + ' ASR words processed' + (ext.submitted.indexOf(ext.index) >= 0 ? ' · Answer already imported; pasting again replaces ' + (whole ? 'its' : 'this batch’s') + ' proposals.' : '.')));
        var progress = el('progress'); progress.max = ext.words_total || 1; progress.value = ext.words_done;
        progress.setAttribute('aria-label', 'External review word progress'); panel.appendChild(progress);
        var promptLabel = el('label', whole ? 'Prompt for this review' : 'Prompt for this batch'), prompt = el('textarea'); prompt.id = 'stt_external_prompt'; prompt.readOnly = true; prompt.dir = 'auto'; prompt.value = ext.prompt; prompt.rows = 7; promptLabel.appendChild(prompt); panel.appendChild(promptLabel);
        var row = el('div'); panel.appendChild(row);
        if (window.ParsehLLMRow) {
          externalRow = ParsehLLMRow.mount(row, {surface: 'asr-' + ext.task, box: function () { return prompt; },
            getText: function () { return !opts.current || opts.current() ? ext.prompt : ''; },
            fresh: function () { return !externalBusy && root.contains(prompt) && (!opts.current || opts.current()); },
            label: 'Copy review prompt', cls: 'wbtn small quiet', ids: {copy: 'stt_external_copy'},
            remind: 'Paste this into your chosen chatbot. Bring its complete answer back to the box below.'}); externalRow.update(ext.prompt);
        }
        if (ext.task === 'workspace') {
          var download = el('a', 'Download transcript & CSV workspace'); download.id = 'stt_external_files';
          download.href = '/youtube/api/transcribe/external-files?' + new URLSearchParams({job: opts.job(), source_sha256: result.review.evidence.source_sha256, session: ext.id, index: ext.index}).toString();
          download.download = 'parseh-review-workspace.zip'; download.addEventListener('click', function (event) { if (opts.current && !opts.current()) event.preventDefault(); }); panel.appendChild(download);
          panel.appendChild(el('p', whole ? 'Attach the ZIP to a chatbot with file/code tools: it holds the whole transcript and its evidence, which the prompt does not repeat. A chatbot without file tools needs the review divided into several prompts: tick that box and prepare a new review. Paste the resulting proposals CSV below. Audio and host paths are excluded.'
            : 'Attach the ZIP to a chatbot with file/code tools, or use the region and CSV evidence in the prompt. Paste the resulting proposals CSV below. Audio and host paths are excluded.'));
        }
        var answerLabel = el('label', ext.task === 'workspace' ? 'Paste proposals CSV' : 'Paste the labeled sentence answers');
        var answer = el('textarea'), key = ext.id + ':' + ext.index; answer.id = 'stt_external_answer'; answer.rows = 7; answer.dir = 'auto'; answer.maxLength = 131072; answer.value = externalDrafts[key] || '';
        answerLabel.appendChild(answer); panel.appendChild(answerLabel);
        var submit = btn('Import answer into review', function () { externalRequest('answer', {session: ext.id, index: ext.index, answer: answer.value}, message); }); submit.id = 'stt_external_import'; submit.disabled = !answer.value.trim();
        setStep(answer.value.trim() ? 2 : 1);
        answer.addEventListener('input', function () { externalDrafts[key] = answer.value; Object.keys(externalDrafts).slice(0, -4).forEach(function (old) { delete externalDrafts[old]; }); autosave(); submit.disabled = !answer.value.trim() || externalBusy; setStep(answer.value.trim() ? 2 : 1); }); panel.appendChild(submit);
        // an answer that came in: what it said, and the choice -- go through it now, or fetch the next prompt first
        var got = ext.submitted.length ? answersSoFar() : null;
        if (got) {
          panel.appendChild(el('p', ext.submitted.length === 1 ? 'An answer is imported. It says:' : plural(ext.submitted.length, 'answer is', 'answers are') + ' imported. Together they say:', 'fieldnote')); panel.appendChild(got);
          var after = el('div', null, 'stt-review-actions');
          var through = btn('Go through these answers', function () { if (walkCtl) { walkCtl.open(); if (walkHost) walkHost.scrollIntoView({block: 'start'}); } }); through.id = 'stt_external_walk'; after.appendChild(through);
          if (ext.batches > 1 && ext.submitted.indexOf(ext.index) < 0) after.appendChild(el('span', 'The prompt above is the next one, ready to copy.', 'fieldnote'));
          panel.appendChild(after);
        }
        var navigation = el('div', null, 'stt-review-actions');
        var previous = btn('Previous prompt', function () { externalRequest('prompt', {session: ext.id, index: ext.index - 1}, message); }); previous.disabled = ext.index === 0; if (!whole) navigation.appendChild(previous);
        var next = btn('Next prompt', function () { externalRequest('prompt', {session: ext.id, index: ext.index + 1}, message); }); next.disabled = ext.index + 1 >= ext.batches; if (!whole) navigation.appendChild(next);
        panel.appendChild(el('p', 'You can stop here: the words with no answer stay as Whisper wrote them, and “Retry remaining suspect words” asks again for them later.', 'fieldnote'));
        navigation.appendChild(btn('Finish with the answers received so far', function () { externalRequest('finish', {session: ext.id}, message); }));
        navigation.appendChild(btn('Cancel external review', function () { externalRequest('cancel', {session: ext.id}, message); })); panel.appendChild(navigation);
      } else if (ext) {
        if (!ext.batches) panel.appendChild(el('p', 'There are no mapped words to review with this method. Inspect the Whisper result below; only Use this transcript fills the transcript box.'));
        else {
          var finished = answersSoFar();
          panel.appendChild(el('p', 'All the answers are in. The model said:', 'fieldnote'));
          if (finished) panel.appendChild(finished);
          panel.appendChild(el('p', 'Go through them above, one by one, or look at any word in the transcript. Only Use this transcript fills the transcript box.'));
          var again = btn('Go through the answers', function () { if (walkCtl) { walkCtl.open(); if (walkHost) walkHost.scrollIntoView({block: 'start'}); } }); again.id = 'stt_external_walk'; panel.appendChild(again);
        }
      }
      if (ext && ext.prompt_error) message.textContent = ext.prompt_error;
      panel.appendChild(message); root.appendChild(panel);
    }
    function suspect(w) { return w.low_asr_score || w.dictionary_miss; }
    function dictionaryCard(box, data) {
      box.textContent = '';
      if (!data || data.state === 'failed') { box.appendChild(el('p', 'Dictionary lookup could not finish.')); return; }
      if (data.state === 'unavailable') { box.appendChild(el('p', 'No dictionary is installed for this language.')); return; }
      if (data.state === 'not-word') { box.appendChild(el('p', 'No lexical word to look up.')); return; }
      if (data.state === 'missing') box.appendChild(el('p', '◇ No meaning found. Names and rare words may be absent from this dictionary.'));
      (data.words || []).forEach(function (row) {
        (row.hits || []).forEach(function (hit) {
          var title = el('p'), head = el('bdi', hit.headword); head.dir = 'auto'; title.appendChild(head);
          if (hit.pos) title.appendChild(document.createTextNode(' · ' + hit.pos)); box.appendChild(title);
          if (hit.note) box.appendChild(el('p', hit.note, 'fieldnote'));
          var senses = el('ul'); (hit.senses || []).forEach(function (sense) { var meaning = el('li', sense); meaning.dir = 'auto'; senses.appendChild(meaning); }); box.appendChild(senses);
        });
        if (!row.hits.length && row.tried.length) box.appendChild(el('p', 'Forms checked: ' + row.tried.join(', '), 'fieldnote'));
      });
      if (data.source) box.appendChild(el('p', data.source + ' · Meanings in ' + data.senses_language, 'fieldnote'));
    }
    function dictionaryDetails(w, originalBox, candidateBoxes, asrBoxes, proposal) {
      if (!opts.dictionary) {
        [originalBox].concat(candidateBoxes, asrBoxes).forEach(function (box) { dictionaryCard(box, null); }); return;
      }
      var key = result.review.evidence.source_sha256 + ':' + w.word_id + ':' + JSON.stringify([w.asr_alternatives, proposal && proposal.candidates || []]);
      var promise = dictionaryCache.get(key);
      if (!promise) {
        promise = opts.dictionary(w.word_id).catch(function () { return null; });
        dictionaryCache.set(key, promise);
        if (dictionaryCache.size > 200) dictionaryCache.delete(dictionaryCache.keys().next().value);
      }
      promise.then(function (data) {
        if (!root.contains(originalBox)) return;
        var expected = proposal ? proposal.original : w.text;
        dictionaryCard(originalBox, data && data.original && data.original.text === expected ? data.original : null);
        candidateBoxes.forEach(function (box, i) {
          var candidate = data && (data.candidates || [])[i];
          dictionaryCard(box, candidate && candidate.text === proposal.candidates[i].text ? candidate : null);
        });
        asrBoxes.forEach(function (box, i) {
          var alternative = data && (data.asr_alternatives || [])[i];
          dictionaryCard(box, alternative && alternative.text === w.asr_alternatives[i].text ? alternative : null);
        });
      });
    }

    function skillControls() {
      var box = el('details'); box.setAttribute('data-review-disclosure', 'skill'); box.appendChild(el('summary', 'Correction skill'));
      var download = el('a', 'Download suspect-word correction skill'); download.href = '/lib/asrskill/parseh-asr-correction.zip'; download.download = 'parseh-asr-correction.zip'; box.appendChild(download);
      var auditDownload = el('a', 'Download whole-text review skill'); auditDownload.href = '/lib/asrskill/parseh-asr-audit.zip'; auditDownload.download = 'parseh-asr-audit.zip'; box.appendChild(el('p')).appendChild(auditDownload);
      var workspaceDownload = el('a', 'Download reasoning workspace skill'); workspaceDownload.href = '/lib/asrskill/parseh-asr-workspace.zip'; workspaceDownload.download = 'parseh-asr-workspace.zip'; box.appendChild(el('p')).appendChild(workspaceDownload);
      box.appendChild(el('p', 'Workspace review loads its bundled skill automatically and supplies isolated file/Python tools. The installed-skill checkbox below applies to the two sentence review methods.'));
      var skillTask = el('select'); ['Suspect words', 'Whole text'].forEach(function (label, i) { var op = el('option', label); op.value = i ? 'audit-' : ''; skillTask.appendChild(op); }); var skillLabel = el('label', 'Skill to check or install '); skillLabel.appendChild(skillTask); box.appendChild(skillLabel);
      box.appendChild(el('p', 'For Unsloth Studio, extract the skill folder into .agents/skills on the endpoint computer, or install it below. Enable it in Studio. Other software must support Agent Skills through its API.'));
      var enabled = !!(config && config.configured && config.adapter === 'unsloth-agent-skills');
      if (!enabled) useSkill = false;
      var label = el('label', 'Use installed skill for the chosen review '), check = el('input'); check.id = 'stt_use_skill'; check.type = 'checkbox'; check.checked = useSkill;
      check.disabled = !enabled || phase === 'correcting'; check.addEventListener('change', function () { useSkill = check.checked; }); label.appendChild(check); box.appendChild(label);
      box.appendChild(el('p', enabled ? 'Skill requests ask Unsloth to load @parseh-asr-correction; only read_skill is enabled, with MCP off. Skills supply instructions to the same model.' : 'Select the Unsloth Agent Skills adapter in LLM Integration to use an installed skill. The short prompt remains available.'));
      var state = el('p'); state.setAttribute('role', 'status'); state.setAttribute('aria-live', 'polite');
      var inspectSkill, install;
      function operation(name) {
        inspectSkill.disabled = install.disabled = true; state.textContent = name === 'skill-install' ? 'Installing the correction skill at the saved endpoint…' : 'Checking the installed skill…';
        fetch('/settings/api/llm/' + skillTask.value + name, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})
          .then(function (r) { return r.json(); }).then(function (j) {
            if (!j.ok) throw new Error(j.error);
            state.textContent = j.ready ? 'Selected skill is installed and enabled. Select Use installed skill before starting its review.' : j.installed ? 'Skill exists; enable it in Unsloth Studio.' : 'Selected skill is not installed.';
          }).catch(function (e) { state.textContent = e.message || 'The endpoint did not answer.'; })
          .finally(function () { inspectSkill.disabled = !enabled || phase === 'correcting' || useBusy; install.disabled = !enabled || !config.can_install_skill || phase === 'correcting' || useBusy; });
      }
      inspectSkill = btn('Check installed skill', function () { operation('skill-status'); }); inspectSkill.disabled = !enabled || phase === 'correcting'; box.appendChild(inspectSkill);
      install = btn('Install in saved endpoint', function () { operation('skill-install'); }); install.disabled = !enabled || !config.can_install_skill || phase === 'correcting'; box.appendChild(install);
      box.appendChild(state); root.appendChild(box);
    }

    function showResponses(history, clipped) {
      if (!responses) return;
      var open = {};
      Array.prototype.forEach.call(responses.querySelectorAll('[data-response-key]'), function (n) { open[n.getAttribute('data-response-key')] = n.open; });
      responses.textContent = '';
      responses.appendChild(el('summary', 'Review diagnostics (' + history.length + ')'));
      responses.appendChild(el('p', 'Actual prompts and model output for this review. Kept temporarily with this job; never written to logs or synced. Reasoning is shown separately when the endpoint supplies it.'));
      if (clipped) responses.appendChild(el('p', 'Older or oversized diagnostics were clipped to keep this review bounded.'));
      if (!history.length) responses.appendChild(el('p', phase === 'correcting' ? 'Waiting for the first model response…' : 'No model responses for this review.'));
      history.forEach(function (trace, i) {
        var entry = el('details');
        var traceKey = trace.run + ':' + trace.sentence_id + ':' + trace.attempt;
        entry.setAttribute('data-response-key', traceKey); entry.open = !!open[traceKey];
        if (trace.kind === 'likelihood') {
          entry.appendChild(el('summary', 'LM likelihood · ' + trace.sentence_id + ' · ' + trace.state + ' · ' + trace.elapsed_seconds + ' s'));
          entry.appendChild(el('p', 'Numerical evaluation diagnostics, not chatbot output. No full-vocabulary logits are stored.'));
          var scoreData = el('pre', JSON.stringify(trace.scores, null, 2)); scoreData.dir = 'auto'; entry.appendChild(scoreData);
          responses.appendChild(entry); return;
        }
        entry.appendChild(el('summary', 'Response ' + (i + 1) + ' · ' + (trace.word_ids || []).length + ' words' + (trace.phase ? ' · ' + trace.phase : '') + ' · ' + trace.state +
          ' · ' + (trace.elapsed_seconds == null ? '' : trace.elapsed_seconds + ' s') + (trace.finish_reason ? ' · finish: ' + trace.finish_reason : '')));
        if (trace.error) entry.appendChild(el('p', trace.error, 'warn'));
        entry.appendChild(el('h4', 'Whisper region'));
        var original = el('pre', trace.source || ''); original.dir = 'auto'; entry.appendChild(original);
        entry.appendChild(el('h4', trace.phase ? 'Assistant text (optional for tool calls)' : 'Final answer'));
        var answer = el('pre', trace.answer || (trace.tool_calls && trace.tool_calls.length ? '(The model called workspace tools)' : '(No final answer returned)')); answer.dir = 'auto'; entry.appendChild(answer);
        if (trace.raw_answer && trace.raw_answer !== trace.answer) {
          var raw = el('details'); raw.appendChild(el('summary', 'Raw answer content'));
          var rawText = el('pre', trace.raw_answer); rawText.dir = 'auto'; raw.appendChild(rawText); entry.appendChild(raw);
        }
        if (trace.reasoning) {
          var reasoning = el('details'); reasoning.appendChild(el('summary', 'Reasoning returned by the endpoint'));
          var thought = el('pre', trace.reasoning); thought.dir = 'auto'; reasoning.appendChild(thought); entry.appendChild(reasoning);
        }
        if (trace.tool_calls && trace.tool_calls.length) {
          var calls = el('details'); calls.appendChild(el('summary', 'Workspace tool calls'));
          trace.tool_calls.forEach(function (call) { calls.appendChild(el('h4', call.function.name)); var args = el('pre', call.function.arguments); args.dir = 'auto'; calls.appendChild(args); });
          (trace.tool_results || []).forEach(function (result) { calls.appendChild(el('h4', result.name + ' result')); var output = el('pre', result.output); output.dir = 'auto'; calls.appendChild(output); }); entry.appendChild(calls);
        }
        var prompt = el('details'); prompt.appendChild(el('summary', 'Exact request messages'));
        (trace.prompt || []).forEach(function (message) { prompt.appendChild(el('h4', message.role)); var text = el('pre', message.content || (message.tool_calls ? JSON.stringify(message.tool_calls) : '')); text.dir = 'auto'; prompt.appendChild(text); });
        entry.appendChild(prompt);
        if (trace.ignored_edits && trace.ignored_edits.length) {
          entry.appendChild(el('p', trace.ignored_edits.length + ' changes outside flagged words or across ambiguous spans were ignored. Caption text is only changed by accepted word edits.'));
          trace.ignored_edits.forEach(function (edit) { entry.appendChild(el('p', edit.original + ' → ' + edit.replacement + ' · ' + edit.reason)); });
        }
        if (trace.response_clipped) entry.appendChild(el('p', 'Long raw output was clipped for display.'));
        responses.appendChild(entry);
      });
    }
    function disableControls(on) {
      if (on) {
        disabledBefore = Array.prototype.slice.call(root.querySelectorAll('button, input, select, textarea')).filter(function (b) { return b.id !== 'stt_review_cancel'; })
          .map(function (b) { var old = [b, b.disabled]; b.disabled = true; return old; });
      } else {
        disabledBefore.forEach(function (old) { old[0].disabled = old[1]; }); disabledBefore = [];
      }
    }
    function idsFor(id) {
      var manual = manualEdits[id];
      return manual != null ? typeof manual === 'object' ? manual.word_ids : [id] : suggestions[id] && suggestions[id].word_ids || [id];
    }
    function clearOverlaps(ids) {
      Object.keys(decisions).forEach(function (id) { if (idsFor(id).some(function (member) { return ids.indexOf(member) >= 0; })) delete decisions[id]; });
      Object.keys(manualEdits).forEach(function (id) { if (idsFor(id).some(function (member) { return ids.indexOf(member) >= 0; })) delete manualEdits[id]; });
    }
    function accepted(id) {
      return Object.keys(decisions).concat(Object.keys(manualEdits)).some(function (key) { return idsFor(key).indexOf(id) >= 0; });
    }
    function draft() {
      var chars = Array.from(result.text), edits = [];
      Object.keys(decisions).forEach(function (id) {
        var w = words[id], s = suggestions[id];
        if (w && s) edits.push({a: s.span_start == null ? w.span_start : s.span_start, b: s.span_end == null ? w.span_end : s.span_end, text: s.candidates[decisions[id]].text});
      });
      Object.keys(manualEdits).forEach(function (id) {
        var w = words[id];
        if (w) { var value = manualEdits[id], ids = idsFor(id); edits.push({a: w.span_start, b: words[ids[ids.length - 1]].span_end, text: typeof value === 'object' ? value.text : value}); }
      });
      edits.sort(function (a, b) { return b.a - a.a; });
      edits.forEach(function (e) { chars.splice.apply(chars, [e.a, e.b - e.a].concat(Array.from(e.text))); });
      return chars.join('');
    }
    function updateDraft() {
      preview.textContent = draft();
      status.textContent = Object.keys(decisions).length + ' suggestions accepted and ' + Object.keys(manualEdits).length + ' word choices saved in this draft. The transcript box has not changed.';
      var applied = {}, suppressed = {};
      Object.keys(decisions).concat(Object.keys(manualEdits)).forEach(function (id) {
        var ids = idsFor(id), manual = manualEdits[id];
        applied[id] = manual != null ? typeof manual === 'object' ? manual.text : manual : suggestions[id].candidates[decisions[id]].text;
        ids.slice(1).forEach(function (member) { suppressed[member] = true; });
      });
      if (walkCtl) outcomeMap = walkCtl.marks();
      Object.keys(wordButtons).forEach(function (id) {
        var button = wordButtons[id], changed = applied[id] != null || suppressed[id];
        button.classList.toggle('asr-agree', outcomeOf(id) === 'agree'); button.classList.toggle('asr-unsure', outcomeOf(id) === 'unsure'); button.classList.toggle('asr-noanswer', outcomeOf(id) === 'none');
        button.classList.toggle('asr-accepted', !!changed);
        button.classList.toggle('asr-locked', !!locked[id]);
        var ends = selection.map(function (member) { return words[member].span_start; }).sort(function (a,b) { return a-b; });
        button.classList.toggle('asr-selected', ends.length === 2 && words[id].span_start >= ends[0] && words[id].span_start <= ends[1]);
        button.setAttribute('aria-pressed', locked[id] ? 'true' : 'false');
        button.hidden = !!suppressed[id];
        button.textContent = applied[id] == null ? words[id].text : applied[id];
        button.setAttribute('aria-label', words[id].text + (applied[id] != null ? applied[id] === words[id].text ? ', original retained in draft' : ', changed in draft to ' + applied[id] : '') +
          (words[id].low_asr_score ? ', low Whisper ASR score' : '') + (suggestions[id] ? suggestions[id].likelihood ? ', LM likelihood evaluation available' : ', LLM edit proposed' : ''));
        if (words[id].dictionary_miss) button.setAttribute('aria-label', button.getAttribute('aria-label') + ', no dictionary meaning found');
        if (locked[id]) button.setAttribute('aria-label', button.getAttribute('aria-label') + ', locked');
      });
      autosave();
      if (walkCtl && walkHost && walkHost.isConnected) walkCtl.repaint();
      if (scopeNote) scopeNote.textContent = selection.length === 2 ? 'Selected section: ' + words[selection[0]].text + ' … ' + words[selection[1]].text : selecting ? 'Choose the first word, then the last word of the section.' : 'Methods review unlocked words. Select a section to limit their targets.';
      if (retry) { var remaining = retryWords(); retry.textContent = 'Retry remaining suspect words (' + remaining.length + ')'; retry.hidden = !result.review.result || result.review.last_method === 'whisper-second'; var configured = result.review.choice === 'likelihood' ? config && config.likelihood && config.likelihood.available : config && config.configured; retry.disabled = phase !== 'review' || !remaining.length || (result.review.choice !== 'external' && !configured); }
      var all = Object.keys(words), low = all.filter(function (id) { return words[id].low_asr_score; }).length;
      var missing = all.filter(function (id) { return words[id].dictionary_miss; }).length;
      if (summary) summary.textContent = low + ' low-score words · ' + missing + ' dictionary misses · ' + Object.keys(suggestions).length + (result.review.choice === 'likelihood' ? ' words reviewed · ' : ' words with proposals · ') +
        (Object.keys(decisions).length + Object.keys(manualEdits).length) + ' edits saved';
      applyFilter();
    }
    // what the walk (asrwalk.js) needs of this review, and nothing else of it
    var walkApi = {
      data: function () { return {words: words, suggestions: suggestions, result: result.review.result, review: result.review, locked: locked, decisions: decisions, manualEdits: manualEdits, text: result.text}; },
      walk: function () { return walkState; },
      touched: function (ids) {
        var took = Object.keys(decisions).some(function (key) { return (suggestions[key] && suggestions[key].word_ids || [key]).some(function (id) { return ids.indexOf(id) >= 0; }); });
        if (took) return 'accepted';
        return Object.keys(manualEdits).some(function (key) { return idsFor(key).some(function (id) { return ids.indexOf(id) >= 0; }); }) ? 'own' : null;
      },
      accept: function (item, index) {
        clearOverlaps(item.ids);
        if (item.proposal) decisions[item.key] = index; else manualEdits[item.anchor] = item.candidates[0].text;
      },
      keep: function (item) { clearOverlaps(item.ids); },
      own: function (item, text) { clearOverlaps(item.ids); manualEdits[item.anchor] = item.ids.length > 1 ? {text: text, word_ids: item.ids.slice()} : text; },
      undo: function (item) { clearOverlaps(item.ids); },
      changed: function () { updateDraft(); },
      caption: function (id) { return captions[id]; },
      // the card's word: marked in the transcript, its evidence in the panel beside it, the player parked at it
      show: function (w) {
        var b = w && wordButtons[w.word_id];
        if (b) { b.scrollIntoView({block: 'nearest'}); Object.keys(wordButtons).forEach(function (id) { wordButtons[id].classList.toggle('asr-walking', id === w.word_id); }); }
        if (w) detail(w);
      },
      listen: function (w) { if (w && opts.select && captions[w.word_id]) opts.select(w, captions[w.word_id], true); },
      use: function () { if (use && !use.disabled) use.click(); },
      phase: function () { return phase; },
      clock: function (w) { var seg = captions[w.word_id]; return seg ? captionTime(seg.start) : ''; }
    };
    // the mark each word wears for what the model said of it (asrwalk.js outcomes)
    var outcomeMap = {};
    function outcomeOf(id) { return outcomeMap[id] ? outcomeMap[id].kind : null; }
    function retryWords() { return Object.keys(words).filter(function (id) { return words[id].reviewable && !locked[id] && inScope(words[id]) && (suspect(words[id]) || result.review.result && (result.review.result.failed_word_ids || []).indexOf(id) >= 0) && !accepted(id); }); }
    function detail(w, hover) {
      if (!w || useBusy) return;
      if (!hover) {
        if (selected && wordButtons[selected]) wordButtons[selected].removeAttribute('aria-current');
        selected = w.word_id;
        if (wordButtons[selected]) wordButtons[selected].setAttribute('aria-current', 'true');
        if (opts.select && captions[selected]) opts.select(w, captions[selected], false);
      }
      details.textContent = '';
      var heading = el('h3', 'Review word'); heading.tabIndex = -1;
      details.appendChild(heading);
      var original = el('bdi', w.text); original.dir = 'auto'; details.appendChild(original);
      if (opts.select && captions[w.word_id]) details.appendChild(btn('Listen to this word', function () { detail(w); opts.select(w, captions[w.word_id], true); }));
      var wordActions = el('div', null, 'stt-word-actions'); details.appendChild(wordActions);
      if (w.reviewable && phase === 'review') {
        var recheck = btn(w.second_pass && w.second_pass.state === 'complete' ? 'Whisper second pass · again' : 'Whisper second pass · this word', function () { runMethod('whisper-second', 'whisper-second', w.word_id); });
        recheck.id = 'stt_whisper_word'; recheck.disabled = !!locked[w.word_id] || !result.review.second_pass_available;
        wordActions.appendChild(recheck);
      }
      var said = outcomeMap[w.word_id];
      if (said) {
        var verdict = el('p', null, 'stt-walk-wordnote stt-walk-' + said.kind);
        verdict.appendChild(el('strong', ParsehAsrWalk.MARK[said.kind] + ' ' + ParsehAsrWalk.HEAD[said.kind](said) + (said.rating ? ' · ' + (said.rating === 'sure' ? 'sure' : 'not sure') : '') + '. '));
        if (said.reason) { var why = el('bdi', said.reason); why.dir = 'auto'; verdict.appendChild(why); }
        details.appendChild(verdict);
      }
      var evidenceDetails = el('details'); evidenceDetails.appendChild(el('summary', 'Recognition details'));
      var usualDetails = details; details = evidenceDetails;
      details.appendChild(el('p', 'Whisper timestamp: ' + time(w.start) + ' – ' + time(w.end) +
        ' · Whisper ASR score: ' + estimate(w.asr_confidence)));
      if (w.low_asr_score) details.appendChild(el('p', '⚠ Low ASR score: below ' + result.review.evidence.low_score_threshold + '. This is recognition evidence, not proof the word is wrong.'));
      if (w.dictionary_miss) details.appendChild(el('p', '◇ No meaning found in the installed dictionary. This word is also a suspect-word review target. Names and rare words can be valid.'));
      if (w.asr_confidence == null) details.appendChild(el('p', 'Whisper supplied no word score.'));
      if (w.second_pass && w.second_pass.state === 'failed') details.appendChild(el('p', 'Whisper second pass could not safely process this word. Its original evidence is intact; you can still review or edit it.', 'warn'));
      usualDetails.appendChild(evidenceDetails); details = usualDetails;
      var s = suggestions[w.word_id], manualKey = Object.keys(manualEdits).find(function (key) { return idsFor(key).indexOf(w.word_id) >= 0; });
      var originalDictionary = el('div', 'Looking up the Whisper word…', 'stt-review-dictionary'), candidateDictionaries = [];
      originalDictionary.setAttribute('role', 'status');
      details.appendChild(el('h4', 'Whisper dictionary meanings')); details.appendChild(originalDictionary);
      var asrDictionaries = [];
      if (!w.alternatives_available) details.appendChild(el('p', 'ASR alternatives are unavailable from this recognizer.'));
      else {
        details.appendChild(el('p', 'Other words heard by Whisper:'));
        var list = el('ul');
        w.asr_alternatives.forEach(function (a) {
          var item = el('li'), surface = el('bdi', a.text); surface.dir = 'auto'; item.appendChild(surface);
          if ((a.origins || []).some(function (origin) { return origin.kind === 'whisper-second-pass'; })) item.appendChild(el('span', ' · Whisper second pass', 'fieldnote'));
          if (w.reviewable && phase === 'review') {
            var choose = btn('Use this Whisper alternative', function () { clearOverlaps([w.word_id]); manualEdits[w.word_id] = a.text; updateDraft(); detail(w); });
            choose.disabled = !!locked[w.word_id]; item.appendChild(choose);
          }

          var meaning = el('div', 'Looking up this Whisper alternative…', 'stt-review-dictionary'); meaning.setAttribute('role', 'status');
          item.appendChild(meaning); asrDictionaries.push(meaning); list.appendChild(item);
        });
        if (!w.asr_alternatives.length) list.appendChild(el('li', 'No unambiguous word alternatives returned.'));
        details.appendChild(list);
      }
      if (!w.reviewable) details.appendChild(el('p', 'This word could not be matched to an exact transcript span. Review it manually.'));
      if (!s && result.review.result && (result.review.result.storage_failed_word_ids || []).indexOf(w.word_id) >= 0) details.appendChild(el('p', 'This target exceeded the bounded numerical-review storage. Its candidate coverage is incomplete; the Whisper alternatives above are intact. Reduce optional search/context bounds and start a new review, or edit it manually.', 'warn'));
      var proposalId = s ? s.word_id : w.word_id, proposalIds = s && s.word_ids || [w.word_id];
      var editIds = (editRanges[w.word_id] || (manualKey ? idsFor(manualKey) : proposalIds)).slice(), editId = editIds[0];
      if (!locked[w.word_id] && editIds.some(function (id) { return locked[id]; })) { editIds = [w.word_id]; editId = w.word_id; }
      var sourceSpan = Array.from(result.text).slice(words[editIds[0]].span_start, words[editIds[editIds.length - 1]].span_end).join('');
      if (s && phase === 'review') {
        if (s.likelihood && s.likelihood.coverage.state !== 'complete') details.appendChild(el('p', 'Comparison incomplete: some alternatives could not be checked. You can retry or choose a word yourself.', 'warn'));
        if (proposalIds.length > 1) { details.appendChild(el('p', 'Proposed source span: ' + s.original)); (s.asr_evidence || []).forEach(function (piece) { details.appendChild(el('p', piece.text + ' · Whisper ASR score: ' + estimate(piece.asr_confidence) + ' · ' + time(piece.start) + ' – ' + time(piece.end))); }); }
        details.appendChild(el('p', s.likelihood ? 'Suggested words' : 'Suggested correction' + (s.error_likelihood == null ? '' : ' · Error likelihood (model estimate): ' + estimate(s.error_likelihood))));
        if (s.likelihood) {
          var numerical = el('details'); numerical.appendChild(el('summary', 'Technical details'));
          usualDetails = details; details = numerical;
          var coverage = s.likelihood.coverage;
          details.appendChild(el('p', 'Model: ' + s.likelihood.model + ' · Mandatory coverage: ' + coverage.mandatory_scored + ' / ' + coverage.mandatory_total + ' · ' + coverage.state + ' · ' + s.likelihood.elapsed_seconds + ' s'));
          details.appendChild(el('p', 'Raw sum log P(candidate + fixed following context | original preceding context). Scores are not probabilities of correct transcription. Best among ' + s.likelihood.winner_scope + '.'));
          if (s.likelihood.context) details.appendChild(el('p', 'Context: ' + s.likelihood.context.preceding_chars + ' preceding / ' + s.likelihood.context.following_chars + ' following characters. Boundary backoff: ' + s.likelihood.retokenized_preceding_bytes + ' preceding bytes included.'));
          if (s.likelihood.hardware) { var hw = s.likelihood.hardware; details.appendChild(el('p', 'Execution: ' + hw.backend.toUpperCase() + (hw.device ? ' · ' + hw.device.description + ' · GPU device ' + hw.gpu_device : '') + ' · ' + hw.offloaded_layers + ' layers offloaded · ' + hw.context_tokens + ' context tokens')); }
          if (s.likelihood.tied_best && s.likelihood.tied_best.length > 1) details.appendChild(el('p', 'Tied highest scores: ' + s.likelihood.tied_best.join(' · ')));
          if (s.likelihood.discovery_error) details.appendChild(el('p', 'Additional-candidate search: ' + s.likelihood.discovery_error));
          if (s.likelihood.discovery_note) details.appendChild(el('p', s.likelihood.discovery_note));
          usualDetails.appendChild(numerical); details = usualDetails;
        }
        if (s.reason && !s.likelihood) details.appendChild(el('p', s.reason));
        var alternatives = el('ol');
        s.candidates.forEach(function (c, i) {
          var li = el('li'), surface = el('bdi', c.text); surface.dir = 'auto'; li.appendChild(surface);
          if (s.likelihood) {
            if (c.rank === 1) li.appendChild(el('span', c.text === w.text ? ' Keep original' : s.likelihood.coverage.state === 'complete' && s.likelihood.tied_best.length === 1 ? ' Best suggestion' : ' Suggested choice', 'fieldnote'));
            var diagnostic = el('details'); diagnostic.appendChild(el('summary', 'Technical details'));
            diagnostic.appendChild(el('p', (c.rank == null ? 'Unscored' : 'Rank ' + c.rank) + ' · Origins: ' + c.origins.map(function (o) { return o.kind === 'original' ? 'original Whisper' : o.kind === 'whisper' ? 'Whisper alternative ' + (o.alternative_index + 1) : 'LM beam search'; }).join(', ') + ' · Raw log likelihood: ' + (c.log_likelihood == null ? 'unavailable' : c.log_likelihood.toFixed(6)) + ' · Difference from original: ' + (c.delta_original == null ? 'unavailable' : c.delta_original.toFixed(6)) + ' · Evaluated tokens: ' + (c.evaluated_tokens == null ? 'unavailable' : c.evaluated_tokens)));
            li.appendChild(diagnostic);
            if (c.error) li.appendChild(el('p', c.error, 'warn'));
          }
          if (c.confidence != null || c.reason) li.appendChild(el('p', (c.confidence == null ? '' : 'Confidence (model estimate): ' + estimate(c.confidence) + '. ') + (c.reason || '')));
          var candidateDictionary = el('div', 'Looking up this alternative…', 'stt-review-dictionary'); candidateDictionary.setAttribute('role', 'status');
          li.appendChild(candidateDictionary); candidateDictionaries.push(candidateDictionary);
          var accept = btn(decisions[proposalId] === i ? 'Accepted in draft' : 'Accept this alternative', function () {
            clearOverlaps(proposalIds); decisions[proposalId] = i; updateDraft(); detail(w);
          }); accept.disabled = !!s.likelihood && !c.applicable || proposalIds.some(function (id) { return locked[id]; }); li.appendChild(accept);
          alternatives.appendChild(li);
        });
        details.appendChild(alternatives);
        var reject = btn('Reject this edit / keep Whisper word', function () { delete decisions[proposalId]; updateDraft(); detail(w); });
        reject.disabled = proposalIds.some(function (id) { return locked[id]; }); details.appendChild(reject);
      } else if (suspect(w) && !said) details.appendChild(el('p', 'No review method has said anything about this word yet. It stays as Whisper wrote it.'));
      dictionaryDetails(w, originalDictionary, candidateDictionaries, asrDictionaries, s);
      if (w.reviewable && phase === 'review') {
        var contextDetails = details; details = wordActions;
        var lock = btn(locked[w.word_id] ? 'Unlock word' : 'I’m sure · lock word', function () {
          keepAccepted();
          var savedKey = Object.keys(manualEdits).find(function (key) { return idsFor(key).indexOf(w.word_id) >= 0; });
          var lockIds = savedKey ? idsFor(savedKey) : [w.word_id];
          if (locked[w.word_id]) lockIds.forEach(function (id) { delete locked[id]; }); else lockIds.forEach(function (id) { locked[id] = true; });
          updateDraft(); detail(w);
        }); lock.id = 'stt_lock_word'; details.appendChild(lock);
        var one = btn('Review this word with LM likelihood · experimental', function () { runMethod('likelihood', 'likelihood', w.word_id); }); one.id = 'stt_likelihood_word';
        one.disabled = !!locked[w.word_id] || !config || !config.likelihood || !config.likelihood.available; details.appendChild(one);
        one.hidden = !config || !config.likelihood || !config.likelihood.available;
        if (locked[w.word_id]) { details.appendChild(el('p', 'Locked words are kept when you run another method. Unlock to edit or review this word.')); details = contextDetails; return; }
        var label = el('label'), labelText = document.createTextNode(''), input = el('input'); label.appendChild(labelText);
        input.type = 'text'; input.id = 'stt_manual_word'; input.dir = 'auto'; input.maxLength = 200;
        var manual = manualEdits[editId], sameProposal = editIds.join(' ') === proposalIds.join(' ');
        input.value = manual != null ? typeof manual === 'object' ? manual.text : manual : s && sameProposal && decisions[proposalId] != null ? s.candidates[decisions[proposalId]].text : sourceSpan; label.appendChild(input); details.appendChild(label);
        var note = el('p', 'If Whisper split a word, include its neighbor and type the joined word.'); note.setAttribute('role', 'status'); details.appendChild(note);
        var spanDisplay = el('bdi', null, 'stt-edit-span'); spanDisplay.dir = 'auto'; spanDisplay.id = 'stt_manual_span';
        var range = el('div', null, 'stt-edit-range'), captionWords = (captions[w.word_id] || {}).words || [w];
        function neighbor(direction) {
          var edge = editIds[direction < 0 ? 0 : editIds.length - 1];
          var at = captionWords.findIndex(function (member) { return member.word_id === edge; });
          return at < 0 ? null : captionWords[at + direction];
        }
        function canInclude(member) { return member && member.reviewable && !locked[member.word_id] && editIds.length < 8; }
        function updateRange(resetInput) {
          editId = editIds[0]; sourceSpan = Array.from(result.text).slice(words[editId].span_start, words[editIds[editIds.length - 1]].span_end).join('');
          editRanges[w.word_id] = editIds.slice(); spanDisplay.textContent = sourceSpan;
          labelText.nodeValue = editIds.length > 1 ? 'Enter the corrected words ' : 'Enter the correct word ';
          saveWord.textContent = editIds.length > 1 ? 'Save correction in draft' : 'Save word in draft';
          restoreWord.textContent = editIds.length > 1 ? 'Restore Whisper words' : 'Restore Whisper word';
          previous.disabled = !canInclude(neighbor(-1)); next.disabled = !canInclude(neighbor(1));
          reset.disabled = editIds.length === 1 && editId === w.word_id;
          var hasLock = editIds.some(function (id) { return locked[id]; }); saveWord.disabled = hasLock; restoreWord.disabled = hasLock; input.disabled = hasLock;
          Object.keys(wordButtons).forEach(function (id) { wordButtons[id].classList.toggle('asr-editing', editIds.indexOf(id) >= 0); });
          if (resetInput) { input.value = sourceSpan; note.textContent = 'Only these original words will change when you save.'; input.focus(); }
        }
        function include(direction) { var member = neighbor(direction); if (!canInclude(member)) return; if (direction < 0) editIds.unshift(member.word_id); else editIds.push(member.word_id); updateRange(true); }
        var previous = btn('Include previous word', function () { include(-1); }); previous.id = 'stt_manual_previous';
        var next = btn('Include next word', function () { include(1); }); next.id = 'stt_manual_next';
        var reset = btn('This word only', function () { editIds = [w.word_id]; updateRange(true); }); reset.id = 'stt_manual_reset';
        range.appendChild(el('span', 'Words to replace', 'fieldnote')); range.appendChild(spanDisplay);
        [previous, next, reset].forEach(function (node) { range.appendChild(node); });
        function saveManual() {
          var value = input.value.trim();
          if (editIds.some(function (id) { return locked[id]; })) { note.textContent = 'Unlock the words before changing this span.'; return; }
          if (!value || editIds.length === 1 && /\s/.test(value) || Array.from(value).length > 200 || /[\x00-\x1f]/.test(value)) { note.textContent = 'Enter a nonempty word or selected short span, without line breaks.'; return; }
          clearOverlaps(editIds);
          if (value !== sourceSpan) manualEdits[editId] = editIds.length > 1 ? {text: value, word_ids: editIds.slice()} : value;
          updateDraft(); note.textContent = 'Correction saved in the pending draft. Caption times are kept; changed word timings need review.';
        }
        input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); saveManual(); } });
        var saveWord = btn('Save word in draft', saveManual);
        var restoreWord = btn('Restore Whisper word', function () { clearOverlaps(editIds); updateDraft(); detail(w); });
        var editor = el('div', null, 'stt-word-editor');
        [range, label, note, saveWord, restoreWord].forEach(function (node) { editor.appendChild(node); });
        details.insertBefore(editor, details.firstChild);
        updateRange(false);
        details = contextDetails;
      }
      if (phase !== 'review') details.appendChild(el('p', 'You can listen and inspect the evidence while this tool works. Stop it or wait for it to finish before editing.'));
    }
    function applyFilter() {
      var query = search.trim().toLocaleLowerCase(), visible = 0;
      captionRows.forEach(function (item) {
        var seg = item.segment, relevant = filter === 'all' || seg.words.some(function (w) {
          return filter === 'proposals' ? !!suggestions[w.word_id] : suspect(w) || !!suggestions[w.word_id] ||
            result.review.result && (result.review.result.failed_word_ids || []).indexOf(w.word_id) >= 0;
        });
        item.row.hidden = !relevant || !!query && seg.text.toLocaleLowerCase().indexOf(query) < 0;
        if (!item.row.hidden) visible++;
      });
      var empty = root.querySelector('.stt-review-empty');
      if (empty) empty.hidden = !captionRows.length || visible > 0;
    }
    function navigateIssue(direction) {
      var ids = Object.keys(wordButtons).filter(function (id) {
        return !wordButtons[id].hidden && !wordButtons[id].closest('.stt-caption').hidden && (suspect(words[id]) || suggestions[id]);
      });
      if (!ids.length) return;
      var at = ids.indexOf(selected), next = ids[(at < 0 ? direction > 0 ? 0 : ids.length - 1 : (at + direction + ids.length) % ids.length)];
      wordButtons[next].focus({preventScroll: true});
      wordButtons[next].scrollIntoView({block: 'nearest'});
      detail(words[next]);
      if (opts.select) opts.select(words[next], captions[next], true);
    }
    function render() {
      if (externalRow) { externalRow.destroy(); externalRow = null; }
      var scroll = inspect ? inspect.scrollTop : 0, opened = {};
      Array.prototype.forEach.call(root.querySelectorAll('[data-review-disclosure]'), function (box) { opened[box.getAttribute('data-review-disclosure')] = box.open; });
      root.textContent = ''; root.hidden = false; wordButtons = {}; captions = {}; captionRows = []; activeCaption = null;
      if (!walkCtl && window.ParsehAsrWalk) walkCtl = ParsehAsrWalk.create(walkApi);
      outcomeMap = walkCtl ? walkCtl.marks() : {};
      var top = el('div', null, 'stt-review-head');
      top.appendChild(el('h3', 'Transcript workspace'));
      summary = el('p', '', 'fieldnote'); top.appendChild(summary); root.appendChild(top);
      top.appendChild(el('p', 'Edit words directly, lock checked choices, or try tools in any order. Your draft stays here until you use it.', 'fieldnote'));
      var toolbox = el('section', null, 'stt-review-toolbox'); root.appendChild(toolbox);
      toolbox.appendChild(el('h4', 'Review tools'));
      choice = el('div', null, 'stt-review-tool-buttons'); toolbox.appendChild(choice);
      var llm = btn('Suspect words · experimental', function () { runMethod('llm', 'suspect'); });
      var audit = btn('Whole-text review · experimental', function () { runMethod('llm', 'full'); }); audit.id = 'stt_review_full';
      var workspace = btn('Reasoning workspace · experimental', function () { runMethod('llm', 'workspace'); }); workspace.id = 'stt_review_workspace';
      var likelihood = btn('LM likelihood · experimental', function () { runMethod('likelihood', 'likelihood'); }); likelihood.id = 'stt_review_likelihood';
      likelihood.disabled = !config || !config.likelihood || !config.likelihood.available || phase === 'correcting';
      workspace.disabled = !config || !config.configured || !config.workspace || !config.workspace.available || phase === 'correcting';
      audit.disabled = !config || !config.configured || phase === 'correcting';
      llm.id = 'stt_review_llm'; llm.disabled = !config || !config.configured || phase === 'correcting';
      var second = btn('Whisper second pass', function () { runMethod('whisper-second', 'whisper-second'); }); second.id = 'stt_review_second_pass';
      var remainingSecond = targetIds('whisper-second').filter(function (id) { return !words[id].second_pass || words[id].second_pass.state !== 'complete'; });
      second.disabled = phase === 'correcting' || !result.review.second_pass_available || !remainingSecond.length;
      second.title = remainingSecond.length ? 'Recheck remaining suspect words in the chosen section. Locked words stay unchanged.' : 'Suspect words in this section have already been checked. Select a word to run it again.';
      [second, llm, audit, workspace, likelihood].forEach(function (button) { choice.appendChild(button); });
      var destination = el('p', config && config.configured ? 'LLM destination: ' + config.base_url + ' · Audio is never sent.' : 'Connected LLM tools are not configured. You can edit, use Whisper rechecks, or copy prompts to an external chatbot.', 'stt-review-destination');
      var settings = el('a', 'LLM settings'); settings.href = '/settings/llm/'; settings.target = '_blank'; settings.rel = 'noopener';
      destination.appendChild(document.createTextNode(' ')); destination.appendChild(settings);
      toolbox.appendChild(destination);
      var advanced = el('details', null, 'stt-review-options'); advanced.setAttribute('data-review-disclosure', 'options');
      advanced.appendChild(el('summary', 'Models, preferences & skills'));
      var optionsDock = el('div', null, 'stt-review-options-dock'); root.appendChild(optionsDock); optionsDock.appendChild(advanced);
      if (config && config.configured) ['suspect', 'full', 'workspace'].forEach(function (task) {
        var setting = config.review_models && config.review_models[task];
        advanced.appendChild(el('p', (task === 'workspace' ? 'Reasoning workspace review' : task === 'full' ? 'Whole-text review' : 'Suspect-word review') + ': ' + (setting ? setting.model_id : config.selected_model) +
          ' · experimental' + (setting && setting.profile_id ? ' · Saved Studio profile loads when this review starts.' : '')));
      });
      advanced.appendChild(el('p', 'LM likelihood: ' + (config && config.likelihood && config.likelihood.model || 'No model selected') + ' · experimental'));
      var likelihoodSettings = el('a', 'Choose local model'); likelihoodSettings.href = '/settings/lm-likelihood/'; likelihoodSettings.target = '_blank'; likelihoodSettings.rel = 'noopener'; advanced.appendChild(likelihoodSettings);
      advanced.appendChild(el('p', 'Whisper rechecks use the original transcription model: ' + result.model + '.'));
      if (result.model_revision) advanced.appendChild(el('p', 'Whisper model version: ' + result.model_revision));
      var speechSettings = el('a', 'Whisper models'); speechSettings.href = '/settings/speech/'; speechSettings.target = '_blank'; speechSettings.rel = 'noopener'; advanced.appendChild(speechSettings);
      skillControls(); advanced.appendChild(root.lastChild);
      externalControls();
      if (optionsDock) optionsDock.appendChild(root.lastChild);
      var c = result.review && result.review.correction || {};
      if (result.review.save_error) root.appendChild(el('p', result.review.save_error, 'warn'));
      if (c.error) root.appendChild(el('p', c.error + ' Your draft is intact. Retry a tool or edit words directly.', 'warn'));
      var failedSecond = Object.keys(words).filter(function (id) { return words[id].second_pass && words[id].second_pass.state === 'failed'; });
      if (failedSecond.length) root.appendChild(el('p', 'Whisper could not safely recheck ' + failedSecond.length + ' words. Their original evidence is intact; retry them or edit directly.', 'warn'));
      var reviewed = result.review && result.review.result;
      if (reviewed && reviewed.failed_word_ids && reviewed.failed_word_ids.length) root.appendChild(el('p', 'No answer came back for ' + plural(reviewed.failed_word_ids.length, 'word', 'words') + '. Their Whisper text is intact. Retry the unresolved words or edit them yourself.', 'warn'));
      if (reviewed && !reviewed.suggestions.length) root.appendChild(el('p', reviewed.assessment === 'no_flagged_words' ? 'No reviewable words had a low ASR score or a dictionary miss. No text was sent to the LLM.' : reviewed.assessment === 'no_reviewable_words' ? 'No source words could be mapped for LLM edits. Review the Whisper text.' : reviewed.failed_word_ids && reviewed.failed_word_ids.length ? 'Some sentences could not be reviewed. Their words remain unchanged.' : reviewed.assessment === 'uncertain' ? 'The model could not determine a correction. No words have changed.' : 'The model kept the words unchanged. This does not establish that they are correct.'));
      var sectionControls = el('div', null, 'stt-review-tools');
      var scopeLabel = el('label', 'Review '), scopeSelect = el('select'); scopeSelect.id = 'stt_review_scope';
      [['all','All text'],['selection','Selected section']].forEach(function (item) { var option=el('option',item[1]); option.value=item[0]; scopeSelect.appendChild(option); });
      scopeSelect.value=scope; scopeSelect.addEventListener('change',function () {scope=scopeSelect.value;updateDraft();render();}); scopeLabel.appendChild(scopeSelect); sectionControls.appendChild(scopeLabel);
      var pickSection=btn(selecting ? 'Cancel section selection' : 'Select a section',function () {selecting=!selecting; if(selecting)selection=[]; updateDraft(); render();}); pickSection.id='stt_select_section'; pickSection.disabled=phase==='correcting'; sectionControls.appendChild(pickSection);
      sectionControls.appendChild(btn('Clear selection',function () {selection=[];selecting=false;scope='all';updateDraft();render();}));
      var soundLabel=el('label','Similar-sounding words '), sound=el('input');sound.type='checkbox';sound.id='stt_phonetic_filter';sound.checked=phonetic;soundLabel.title='LM likelihood: prefer similar-sounding candidates when pronunciation is available';soundLabel.hidden=!config || !config.likelihood || !config.likelihood.available;sound.addEventListener('change',function () {phonetic=sound.checked;autosave();});soundLabel.appendChild(sound);sectionControls.appendChild(soundLabel);
      scopeNote=el('p','','fieldnote');sectionControls.appendChild(scopeNote); root.insertBefore(sectionControls, toolbox);
      walkHost = null;
      if (walkCtl) { walkHost = el('section', null, 'stt-walk'); walkHost.id = 'stt_walk'; walkHost.setAttribute('aria-label', 'The model’s answers'); root.appendChild(walkHost); }
      var toolbar = el('div', null, 'stt-review-tools');
      var filterLabel = el('label', 'Show '), picker = el('select'); picker.id = 'stt_review_filter';
      [['all', 'All captions'], ['attention', 'Needs attention'], ['proposals', result.review.choice === 'likelihood' ? 'Reviewed words' : 'Suggested changes']].forEach(function (option) { var n = el('option', option[1]); n.value = option[0]; picker.appendChild(n); });
      picker.value = filter; picker.addEventListener('change', function () { filter = picker.value; applyFilter(); }); filterLabel.appendChild(picker);
      var searchBox = el('input'); searchBox.type = 'search'; searchBox.placeholder = 'Find text…'; searchBox.value = search;
      searchBox.setAttribute('aria-label', 'Find text in captions'); searchBox.addEventListener('input', function () { search = searchBox.value; applyFilter(); });
      toolbar.appendChild(filterLabel); toolbar.appendChild(searchBox);
      toolbar.appendChild(btn('Previous issue', function () { navigateIssue(-1); })); toolbar.appendChild(btn('Next issue', function () { navigateIssue(1); })); root.appendChild(toolbar);
      var legend = el('p', '⚠ Check · ◇ No definition · ✎ Model suggests · ✔ Model agrees · ? Model not sure · ✗ No answer · ✓ In your draft · 🔒 Locked', 'stt-review-legend'); root.appendChild(legend);
      if (result.review.evidence.dictionary && result.review.evidence.dictionary.failed) root.appendChild(el('p', 'Some dictionary lookups could not finish. Those failures do not flag words as incorrect.', 'fieldnote'));
      var body = el('div', null, 'stt-review-body');
      inspect = el('div', null, 'stt-review-text'); inspect.setAttribute('role', 'region'); inspect.setAttribute('aria-label', 'Timestamped transcript');
      details = el('aside', 'Select any word to inspect its evidence or enter a correction.', 'stt-review-details');
      details.id = 'stt_review_details'; details.setAttribute('role', 'region'); details.setAttribute('aria-label', 'Word evidence and proposed edits');
      var evidence = result.review && result.review.evidence;
      if (evidence) inspect.lang = evidence.language;
      if (evidence) evidence.segments.forEach(function (seg) {
        var row = el('div', null, 'stt-caption'), timestamp = btn(captionTime(seg.start), function () {
          if (seg.words.length && opts.select) { detail(seg.words[0]); opts.select(seg.words[0], seg, false); }
          if (opts.seek) opts.seek(seg.start, true, typeof seg.end === 'number' ? seg.end + .6 : null);
        });
        timestamp.className = 'stt-review-clock'; timestamp.setAttribute('aria-label', 'Play caption at ' + time(seg.start));
        row.appendChild(timestamp); row.setAttribute('data-review-segment', seg.segment_id);
        var text = el('p'), cursor = 0; text.dir = 'auto';
        seg.words.forEach(function (w) {
          var at = seg.text.indexOf(w.text, cursor); if (at < 0) return;
          text.appendChild(document.createTextNode(seg.text.slice(cursor, at)));
          var s = suggestions[w.word_id];
          if (w.reviewable || suspect(w) || s) {
            var b = btn(w.text, function () {
              if (selecting) { selection.push(w.word_id); if (selection.length === 2) {selecting=false;scope='selection';} updateDraft(); if (!selecting) render(); return; }
              detail(w); if (opts.select) opts.select(w, seg, true); });
            b.className = 'stt-review-word' + (w.low_asr_score ? ' asr-low' : '') + (w.dictionary_miss ? ' asr-dictionary' : '') +
              (outcomeOf(w.word_id) === 'change' || s && !outcomeOf(w.word_id) ? ' asr-proposal' : '') + (outcomeOf(w.word_id) === 'agree' ? ' asr-agree' : '') +
              (outcomeOf(w.word_id) === 'unsure' ? ' asr-unsure' : '') + (outcomeOf(w.word_id) === 'none' ? ' asr-noanswer' : '') + (s && s.likelihood ? ' asr-likelihood' : '');
            b.setAttribute('data-review-word', w.word_id); b.setAttribute('aria-controls', details.id);
            b.addEventListener('focus', function () { detail(w); });
            b.addEventListener('keydown', function (e) {
              if (e.key === 'Enter') {
                if (selecting) { e.preventDefault(); b.click(); return; }
                e.preventDefault(); detail(w); if (opts.select) opts.select(w, seg, true);
                var target = details.querySelector('input') || details.querySelector('h3'); if (target) target.focus();
              }
            });
            b.addEventListener('mouseenter', function () { if (!details.contains(document.activeElement)) detail(w, true); });
            b.addEventListener('mouseleave', function () { if (selected && words[selected] && !details.contains(document.activeElement)) detail(words[selected]); });
            wordButtons[w.word_id] = b; captions[w.word_id] = seg; text.appendChild(b);
          } else text.appendChild(document.createTextNode(w.text));
          cursor = at + w.text.length;
        });
        text.appendChild(document.createTextNode(seg.text.slice(cursor))); row.appendChild(text); inspect.appendChild(row);
        captionRows.push({row: row, segment: seg});
      });
      else inspect.appendChild(el('pre', result.text));
      var empty = el('p', 'No captions match this filter. Choose All captions or clear the search.', 'stt-review-empty'); empty.hidden = true; inspect.appendChild(empty);
      body.appendChild(inspect); body.appendChild(details); root.appendChild(body);
      var footer = el('div', null, 'stt-review-footer');
      status = el('p', '', 'stt-review-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); footer.appendChild(status);
      var actions = el('div', null, 'stt-review-actions');
      var cancelled = btn(phase === 'correcting' ? 'Stop current tool' : 'Discard review', opts.cancel); cancelled.id = 'stt_review_cancel'; actions.appendChild(cancelled);
      retry = btn('Retry remaining suspect words', function () {
        var task = result.review.result && result.review.result.task || 'suspect';
        if (result.review.choice === 'external') externalRequest('start', {task: task, word_ids: retryWords(), divide: task === 'workspace' && !!(result.review.external && result.review.external.divided)}, root.querySelector('#stt_external_status'));
        else if (opts.retry) { var ids=retryWords();keepAccepted();saveNow().then(function () {opts.retry(ids,useSkill,task,{phonetic_filter:phonetic});},function(e){status.textContent=e.message;}); }
      }); retry.id = 'stt_review_retry'; actions.appendChild(retry);
      var best = btn('Select best for all', selectBest); best.id='stt_select_best'; best.disabled=phase!=='review' || (!Object.keys(suggestions).length && !(result.review.last_method === 'whisper-second' && (result.review.last_word_ids || []).some(function (id) { return words[id] && words[id].second_pass && words[id].second_pass.best_candidate; }))); actions.appendChild(best);
      if (opts.pause) { var pause=btn('Save & pause',function () {saveNow().then(opts.pause).catch(function (e) {status.textContent=e.message || 'The review could not be paused. Keep this page open and try again.';});});pause.id='stt_pause';pause.disabled=false;actions.appendChild(pause); }
      use = btn('Use this transcript', function () { opts.use(Object.assign({}, decisions), Object.assign({}, manualEdits)); }); use.id = 'stt_use'; use.classList.add('go'); use.disabled = phase !== 'review'; actions.appendChild(use);
      footer.appendChild(actions); root.appendChild(footer);
      var previewBox = el('details', null, 'stt-review-options'); previewBox.setAttribute('data-review-disclosure', 'draft'); previewBox.appendChild(el('summary', 'Preview the complete pending transcript'));
      preview = el('pre'); preview.dir = 'auto'; previewBox.appendChild(preview); root.appendChild(previewBox);
      responses = el('details', null, 'stt-llm-responses'); responses.id = 'stt_llm_responses'; responses.setAttribute('data-review-disclosure', 'responses'); root.appendChild(responses);
      showResponses(result.review && result.review.diagnostics || [], result.review && result.review.diagnostics_clipped);
      if (walkCtl && walkHost) walkCtl.mount(walkHost, true);
      updateDraft();
      if (phase === 'review') status.textContent = 'Your draft is ready to edit. Use a tool if useful, or use the transcript directly.';
      if (phase === 'correcting') status.textContent = 'A review tool is running. You can listen and inspect the original evidence while it works.';
      if (phase === 'review' && result.review.choice === 'likelihood') status.textContent = result.review.correction && result.review.correction.state === 'partial' ? 'Some words could not be reviewed. Retry them, edit them yourself, or keep the originals.' : 'Review finished. Choose suggested words or keep the originals, then use the transcript.';
      if (phase === 'external') status.textContent = 'Copy a prompt and paste the answer above. Finish importing to accept the draft; the transcript box has not changed.';
      Array.prototype.forEach.call(root.querySelectorAll('[data-review-disclosure]'), function (box) { if (box.getAttribute('data-review-disclosure') === 'external' && result.review.external && !result.review.external.finished) box.open = true; else box.open = !!opened[box.getAttribute('data-review-disclosure')]; });
      inspect.scrollTop = scroll;
      if (selected && words[selected]) detail(words[selected]);
      if (useBusy) disableControls(true);
    }
    var handle = {
      show: function (res, state, connection) {
        var before = result && result.review && result.review.evidence && result.review.evidence.source_sha256;
        var after = res.review && res.review.evidence && res.review.evidence.source_sha256;
        var previousExternal = result && result.review && result.review.external;
        var nextExternal = res.review && res.review.external;
        if ((previousExternal && previousExternal.id) !== (nextExternal && nextExternal.id)) externalDrafts = {};
        if (before !== after) { decisions = {}; manualEdits = {}; locked = {}; selection = []; selected = null; editRanges = {}; externalDrafts = {}; hydrated = false; walkState = {kept: {}, skipped: {}, includeAgree: false}; }
        if (before !== after) { filter = 'all'; search = ''; }
        var previousSuggestions = suggestions; result = res; phase = res.review && res.review.external && !res.review.external.finished ? 'external' : state === 'choice' ? 'review' : state; config = connection; suggestions = {}; words = {};
        keepExternal(res.review && res.review.external);
        ((res.review && res.review.result && res.review.result.suggestions) || []).forEach(function (s) { (s.word_ids || [s.word_id]).forEach(function (id) { suggestions[id] = s; }); });
        ((res.review && res.review.evidence && res.review.evidence.segments) || []).forEach(function (s) { s.words.forEach(function (w) { words[w.word_id] = w; }); });
        Object.keys(decisions).forEach(function (id) { if (JSON.stringify(previousSuggestions[id]) !== JSON.stringify(suggestions[id])) delete decisions[id]; });
        if (!hydrated) {
          var saved = res.review && res.review.draft || {};
          decisions = saved.decisions || {}; manualEdits = saved.manual_edits || {};
          selection = saved.selection || []; scope = saved.scope || (selection.length === 2 ? 'selection' : 'all');
          var defaultSound = config && config.likelihood && config.likelihood.phonetic_filter;
          phonetic = typeof saved.phonetic_filter === 'boolean' ? saved.phonetic_filter : typeof defaultSound === 'boolean' ? defaultSound : true;
          externalDrafts = saved.external_drafts || {}; selected = saved.selected_word || selected;
          var savedWalk = saved.walk || {}; walkState = {kept: {}, skipped: {}, includeAgree: !!savedWalk.include_agree};
          (savedWalk.kept || []).forEach(function (id) { walkState.kept[id] = true; }); (savedWalk.skipped || []).forEach(function (id) { walkState.skipped[id] = true; });
          (saved.locked_word_ids || []).forEach(function (id) { locked[id] = true; }); hydrated = true;
        }
        render();
      },
      playhead: function (at) {
        var item = captionRows.find(function (entry) { return at >= entry.segment.start && at < entry.segment.end; });
        var next = item && item.row;
        if (next === activeCaption) return;
        if (activeCaption) activeCaption.classList.remove('asr-playing');
        activeCaption = next; if (next) next.classList.add('asr-playing');
      },
      progress: function (say) { if (status) status.textContent = say; },
      diagnostics: function (history, clipped) { showResponses(history || [], clipped); },
      resetProposals: keepAccepted,
      snapshot: snapshot, flush: saveNow,
      disableUse: function (on) { useBusy = on; disableControls(on); },
      clear: function () { if(saveTimer)clearTimeout(saveTimer);hydrated=false;locked={};selection=[];editRanges={};keepExternal(null); if (externalRow) externalRow.destroy(); externalRow = null; externalAttempt++; externalBusy = false; externalDrafts = {}; walkState = {kept: {}, skipped: {}, includeAgree: false}; result = null; decisions = {}; manualEdits = {}; dictionaryCache.clear(); useBusy = false; disabledBefore = []; root.textContent = ''; root.hidden = true; }
    };
    return handle;
  }
  window.ParsehAsrReview = {mount: mount};
})();
