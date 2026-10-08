# SPDX-License-Identifier: GPL-3.0-or-later
"""Speech settings: a shared model catalogue and independent optional audio tools.

The server owns catalogue validation and installation. This page renders its
status, including unavailable packages, without inventing model compatibility.
All mutations follow settingspage's admitted-device rules. Download rows reuse
lookuppage's progress and focus helpers; nothing is installed when the page opens.
"""
import html
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import getstt                                                # noqa: E402
import languages                                             # noqa: E402
import lookuppage                                            # noqa: E402
import settingspage                                          # noqa: E402
import speechconfig

PAGE = "/settings/speech/"
GUIDE = getstt.GUIDE
# the three settings this page's buttons are, and only these
KEYS = ("speech.get", "speech.remove", "speech.stop", "speech.preferences")


def esc(s):
    return html.escape(str(s), quote=True)


def door_tags():
    """What the Settings hub says under this door: which models are ready, or
    that nothing is installed -- a door that says so is doing its job."""
    ready = [k for k in getstt.MODELS if getstt.model_ready(k)] if getstt.runtime_ready() else []
    if not ready:
        return '<span class="tag">not installed</span>'
    return "".join('<span class="tag on">%s</span>' % esc(k) for k in ready)


def credits():
    """The licence line of each part: {"speech:runtime": {who, licence}, ...}."""
    import notices
    return {k: {"who": v[0], "licence": v[1]} for k, v in notices.speech_credits().items()}


def view(jobs=None, where="", device=""):
    """Everything the page draws, in one answer: drawn from it when it opens and
    from the next one every time it asks how things stand (`speech` with
    {"full": true}, or `speechcheck`)."""
    st = getstt.status()
    kept = (st["runtime"]["size"] + sum(m["size"] for m in st["models"].values())
            + sum(a["size"] for a in st.get("aligners", {}).values()))
    try:
        free = lookuppage.disk_free(getstt.STT_DIR)
    except OSError:
        free = None
    return {"ok": True, "speech": st,
            "preferences": speechconfig.load(),
            "jobs": {"speech": jobs or {}},
            "sizes": {"speech:%s" % k: getstt.plan(k) for k in getstt.PARTS},
            "credits": credits(),
            "languages": [{"code": L.code, "name": L.name, "native": L.native,
                           "rtl": L.dir == "rtl", "whisper": L.code in getstt.WHISPER_LANGUAGES}
                          for L in languages.LANGS.values()],
            "kept": kept, "free": free, "where": where or "", "device": device or "",
            "may": {k: settingspage.may(k, where) for k in KEYS}}


def page(jobs=None, where="", device=""):
    """/settings/speech/, the whole page."""
    v = view(jobs, where, device)
    main = """<main class="settings rh sp tools">
%(doors)s
<h1 class="idx">speech to text</h1>
<p class="whomay">%(gate)s <span>Transcription runs on this computer; your audio stays here. Install only what you need. Downloads are checked before use.</span></p>
<div id="sp-band" class="band"></div>
<section class="shared about" id="sp-second" hidden><label><input type="checkbox" id="sp_second_pass"%(second_checked)s>
Automatically run a second Whisper pass</label>
<p>Recheck suspect words after transcription. You can also run it later for a section or a single word.</p>
<p id="sp_preferences_status" role="status" aria-live="polite"></p></section>
<div id="sp"><p class="rh-wait">Reading what is here&hellip;</p></div>
<p class="foot">Use these tools in <a href="/youtube/add/">Add a video</a>.
Captured sound is kept privately until you use or discard the pending transcript.
<a href="%(guide)s" data-guide>Speech to text guide</a> &middot;
<a href="/licences/">Licences</a></p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "gate": settingspage.gate(KEYS),
              "name": settingspage.NAME, "guide": esc(GUIDE),
              "second_checked": ' checked' if v['preferences']['second_pass'] else ''}
    script = ('<script id="sp-state" type="application/json">%s</script>\n<script>%s</script>'
              % (settingspage._in_script(v), SCRIPT))
    return settingspage.frame("Speech to text &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; speech to text',
                              "Speech to text", GUIDE, main,
                              style=lookuppage.STYLE + STYLE, script=script,
                              extra_head='<link rel="stylesheet" href="/lib/settings-tools.css">')


STYLE = r"""
#sp_second_pass{width:auto;margin-inline-end:.5rem}
.sp .catalogue-controls{display:flex;align-items:end;gap:12px;flex-wrap:wrap;padding:14px 16px;border-bottom:1px solid var(--rule)}
.sp .catalogue-controls label{display:flex;flex-direction:column;gap:5px;font-size:13px;margin:0;min-width:0}
.sp .catalogue-controls select{max-width:100%;min-width:180px}
.sp .catalogue-controls .installed-filter{flex-direction:row;align-items:center;padding-bottom:8px}
.sp .catalogue-controls input[type=checkbox]{width:auto;margin-inline-end:5px}
.sp .catalogue-section{font-size:13px;font-weight:600;color:var(--dim);padding:10px 16px;margin:0;border-top:1px solid var(--rule)}
.sp .catalogue-section:first-child{border-top:0}
.sp .catalogue-empty{padding:14px 16px;color:var(--dim);font-size:14px}
.sp .catalogue-selection{padding:12px 16px;border-top:1px solid var(--rule);font-size:13px}
.sp .catalogue-selection label{display:flex;align-items:center;flex-wrap:wrap;gap:8px}
.sp .catalogue-selection select{max-width:100%;width:auto}
.sp .catalogue-selection p{margin:6px 0 0;color:var(--dim)}
.sp .whomay{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap;margin:.2rem 0 1rem;font-size:13.5px;color:var(--dim)}
.sp .whomay .gate{flex:none}
.sp section.about{padding:14px 16px}
.sp .shared>.about{padding:12px 16px}
.sp .about a{color:var(--accent)}
.sp .about p{margin:.35rem 0;font-size:14px}
.sp .about ul{margin:.4rem 0 .2rem;padding-inline-start:1.25rem;font-size:14px}
.sp .about li{margin:.15rem 0}
.sp .tagline{display:inline-block;font-size:12.5px;color:var(--accent);border:1px solid var(--rule);border-radius:20px;
  padding:1px 9px;margin-inline-start:8px;white-space:nowrap;vertical-align:middle;background:var(--boxbg)}
.sp .need{margin:.35rem 0 .1rem;padding-inline-start:1.25rem;font-size:13.5px}
.sp .need li{margin:.1rem 0}
.sp .need a{color:var(--accent)}
.sp .it .mem{color:var(--dim);font-size:12.5px}
.sp details.tech{margin-top:8px;font-size:12.5px;color:var(--dim)}
.sp details.tech summary{cursor:pointer;color:var(--dim);width:max-content;max-width:100%}
.sp details.tech dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:2px 14px;margin:6px 0 0}
.sp details.tech dt{color:var(--dim)}
.sp details.tech dd{margin:0;overflow-wrap:anywhere;font-variant-numeric:tabular-nums;color:var(--ink)}
.sp .modes{margin:0;padding:12px 16px 14px;border-top:1px solid var(--rule);font-size:13.5px}
.sp .modes dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:4px 14px;margin:.3rem 0 0}
.sp .modes dt{font-weight:600}
.sp .modes dd{margin:0;color:var(--dim)}
.sp .langs{display:flex;flex-wrap:wrap;gap:6px 8px;padding:12px 16px 14px}
.sp .sp-aligners{border-top:1px solid var(--rule);margin-top:2px}
.sp .lang-chip{display:inline-flex;align-items:baseline;gap:7px;border:1px solid var(--rule);border-radius:8px;
  padding:3px 10px;font-size:13.5px;background:var(--boxbg)}
.sp .lang-chip .nat{font-size:16px;color:var(--accent)}
.sp .lang-chip.no{border-style:dashed;color:var(--dim)}
.sp .lang-chip.no .nat{color:var(--dim)}
.sp .lang-chip i{font-style:normal;font-weight:700;font-size:12px;color:var(--ok)}
.sp .lang-chip.no i{color:var(--dim)}
.sp a.plain{text-decoration:none}
.sp .band .who a{color:var(--accent)}
@media (max-width:620px){
  .sp .it-act a.plain,.sp .it-act button{flex:1 1 auto}
  .sp details.tech dl{grid-template-columns:1fr;gap:0}
  .sp details.tech dt{margin-top:4px}
  .sp .modes dl{grid-template-columns:1fr;gap:0}
  .sp .modes dt{margin-top:6px}
}
"""

SCRIPT = r"""
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('sp-state').textContent);
  var root = document.getElementById('sp');
  var band = document.getElementById('sp-band');
  var asking = {};         // a row's question: {kind: 'remove'|'bad'|'wait', said}
  var checking = false;    // the graphics card is being looked at
  var checked = false;     // ...and was, once, on opening
  var polling = null;
  var catalogueLanguage = '', installedOnly = false, preferenceSay = '';
  var uploads = {};
  var secondPass = document.getElementById('sp_second_pass');
  var second = document.getElementById('sp-second');     // its box (a page that has no such box keeps the bare checkbox)
  secondPass.addEventListener('change', function () {
    var previous = S.preferences.second_pass;
    secondPass.disabled = true;
    document.getElementById('sp_preferences_status').textContent = 'Saving…';
    fetch('/settings/api/speech/save', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({second_pass:secondPass.checked})}).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) throw new Error(j.error || 'Could not save this preference.');
      S.preferences = j.preferences;
      document.getElementById('sp_preferences_status').textContent = 'Saved. Applies to new transcriptions.';
    }).catch(function (e) {
      secondPass.checked = previous;
      document.getElementById('sp_preferences_status').textContent = e.message || 'Could not save this preference.';
    }).then(function () { secondPass.disabled = false; });
  });
  /*ROW_JS*/

  var J = function () { return (S.jobs || {}).speech || {}; };
  function may(setting) { return !S.may || S.may[setting] !== false; }
  function size(id) { return (S.sizes || {})['speech:' + id] || {}; }
  function built(s) {
    if (!s) return '';
    var d = new Date(String(s).slice(0, 10) + 'T12:00:00');
    return 'built ' + (isNaN(d) ? esc(s) : d.toLocaleDateString('en-GB', {day: 'numeric', month: 'long', year: 'numeric'}));
  }
  // an error is the sentence the manager gave, without its own name in front of it
  function said(e) { return String(e || '').replace(/^getstt:\s*/, ''); }
  function GB(n) { return n == null ? '' : (n >= 1e9 ? (n / 1e9).toFixed(1) + ' GB' : MB(n)); }

  function lower(s) { s = String(s || ''); return s.charAt(0).toLowerCase() + s.slice(1); }

  /* ---- what each state of a part is called, in words a person reads */
  var OLD = {older: 'Built by an older Parseh', newer: 'Built by a newer Parseh', other_python: 'Built for another Python',
             broken: 'Incomplete'};
  function stateOf(r) {
    var j = r.job;
    if (j && j.running) {
      var pc = j.total ? Math.min(99, Math.floor(100 * j.done / j.total)) : null;
      return {cls: 'run', glyph: j.phase === 'build' ? '↻' : '↓',
              word: (j.phase === 'upload' ? 'Uploading' : j.phase === 'build' ? 'Installing' : 'Downloading') + (pc != null ? ' · ' + pc + '%' : '')};
    }
    if (r.withModel) return {cls: 'run', glyph: '↓', word: 'Comes first, with the model'};
    if (r.na) return {cls: 'na', glyph: '–', word: 'Not available'};
    if (j && (j.error || j.stopped) && !r.have) return {cls: 'bad', glyph: '!', word: 'Stopped'};
    if (r.have && OLD[r.state]) return {cls: r.state === 'broken' ? 'bad' : 'old', glyph: r.state === 'broken' ? '!' : '↻', word: OLD[r.state]};
    if (r.have) return {cls: 'ok', glyph: '✓', word: 'Installed'};
    return {cls: 'not', glyph: '○', word: 'Not yet'};
  }

  /* ---- rows drawn from the shared catalogue */
  function parts() {
    var sp = S.speech, rt = sp.runtime, lic = S.credits || {}, rows = [];
    var rtPlan = size('runtime');
    rows.push({id: 'runtime', name: 'The speech program', 'for': 'What runs a model: faster-whisper, with the libraries it needs, in a folder of its own. ' +
               'It is fetched with the first model, and it is not part of ' + 'Parseh' + '’s own installation.',
               have: rt.have, state: rt.state, why: rt.why, na: rt.state === 'unavailable', credit: lic['speech:runtime'],
               facts: rt.have ? 'faster-whisper ' + esc(rt.version) + ' · CTranslate2 ' + esc(rt.ctranslate2) + ' · ' + GB(rt.size) : '',
               kept: rt.size, reinstall: rt.state !== 'absent', noResume: true});
    Object.keys(sp.models).forEach(function (id) {
      var m = sp.models[id];
      var description = m.language ? 'For ' + languageName(m.language) + ' speech.' :
        (id === 'large-v3-turbo' ? 'A fast multilingual choice for everyday transcription.' : 'A larger multilingual model. Uses more memory and takes longer.');
      rows.push({id: id, name: m.label, tag: m.tag, 'for': description, description: m.hint, have: m.have, state: m.state, why: m.why,
                 languages: m.languages || (m.language ? [m.language] : []), available: m.available !== false,
                 option: m.option, limitations: m.limitations || [],
                 source:typeof m.source === 'string' ? {repo:m.source,revision:m.revision} : m.source,
                 distribution:m.distribution, package:m.package, packageImported:!!m.package_imported,
                 packageRevision: m.package_revision || m.revision, compatibility: m.compatibility,
                 fullyCompatible: m.fully_compatible,
                 na: m.available === false || rt.state === 'unavailable' && !m.have,
                 naWhy: m.availability_reason || m.why || rt.why,
                 credit: lic['speech:' + id] || (m.licence ? {who:esc(m.source && m.source.repo || m.repo || m.label),licence:esc(m.licence)} : null),
                 facts: m.have ? GB(m.size) + ' · ' + esc(m.repo) + (m.built ? ' · ' + built(m.built) : '') : '',
                 kept: m.size, needsProgram: !rt.ready, memory: m.memory});
    });
    rows.forEach(function (r) { r.job = uploads[r.id] || J()[r.id] || null; });
    // the program comes first when a model is fetched: its own row says where it is
    var first = Object.keys(sp.models).concat(Object.keys(sp.aligners || {}).map(function (code) {
      return 'align-' + code;
    })).filter(function (id) { var j = J()[id]; return j && j.running; })[0];
    if (first && !rt.ready && !rows[0].job) rows[0].withModel = first;
    rows.forEach(function (r) { r.usable = r.id === 'runtime' || rt.ready; });
    return rows;
  }

  function alignerParts() {
    var sp = S.speech, rt = sp.runtime, lic = S.credits || {}, rows = [];
    Object.keys(sp.aligners || {}).forEach(function (code) {
      var a = sp.aligners[code], native = a.native && a.native !== a.name ? ' — ' + a.native : '';
      rows.push({id: a.id || ('align-' + code), name: 'Exact word times · ' + a.name + native,
                 'for': a.hint || 'Optional — Whisper works without it; this makes word times exact.',
                 have: a.have, state: a.state, why: a.why,
                 na: rt.state === 'unavailable' && !a.have, naWhy: rt.why,
                 credit: lic['speech:' + (a.id || ('align-' + code))],
                 facts: a.have ? GB(a.size) + ' · ' + esc(a.repo) + (a.built ? ' · ' + built(a.built) : '') : '',
                 kept: a.size, needsProgram: !rt.ready});
    });
    rows.forEach(function (r) { r.job = J()[r.id] || null; r.usable = rt.ready; });
    return rows;
  }

  function languageName(code) {
    var found = (S.languages || []).filter(function (L) { return L.code === code; })[0];
    return found ? found.name : code;
  }
  function modelMatches(r, code) { return !code || !r.languages.length || r.languages.indexOf(code) >= 0; }
  function catalogue(rows) {
    var models = rows.filter(function (r) { return r.id !== 'runtime'; });
    var offered = {};
    models.forEach(function (r) { r.languages.forEach(function (code) { offered[code] = true; }); });
    var options = '<option value="">All languages</option>' + Object.keys(offered).sort(function (a,b) { return languageName(a).localeCompare(languageName(b)); }).map(function (code) {
      return '<option value="' + esc(code) + '"' + (code === catalogueLanguage ? ' selected' : '') + '>' + esc(languageName(code)) + '</option>';
    }).join('');
    var shown = models.filter(function (r) { return modelMatches(r, catalogueLanguage) && (!installedOnly || r.have || r.job && r.job.running); });
    var standard = shown.filter(function (r) { return !r.languages.length; }), specific = shown.filter(function (r) { return r.languages.length; });
    var html = '<h2 class="part">Whisper models</h2><section class="shared"><div class="catalogue-controls">' +
      '<label for="sp_language">Language<select id="sp_language" data-model-language>' + options + '</select></label>' +
      '<label class="installed-filter"><input type="checkbox" id="sp_installed_only" data-installed-only' + (installedOnly ? ' checked' : '') + '>Installed only</label></div>';
    if (standard.length) html += '<h3 class="catalogue-section">Standard models · all supported languages</h3>' + standard.map(row).join('');
    if (specific.length) html += '<h3 class="catalogue-section">Language-specific models</h3>' + specific.map(row).join('');
    if (!shown.length) html += '<p class="catalogue-empty">No installed model matches this filter. Turn off “Installed only” to see the available choices.</p>';
    if (catalogueLanguage) {
      var choices = models.filter(function (r) { return modelMatches(r, catalogueLanguage) && r.have && r.usable && r.state === 'ready'; });
      var selected = ((S.preferences || {}).models_by_language || {})[catalogueLanguage] || '';
      html += '<div class="catalogue-selection"><label for="sp_preferred_model">Preferred model for ' + esc(languageName(catalogueLanguage)) +
        '<select id="sp_preferred_model" data-preferred-model' + (!choices.length ? ' disabled' : '') + '><option value="">Choose when transcribing</option>' +
        choices.map(function (r) { return '<option value="' + esc(r.id) + '"' + (r.id === selected ? ' selected' : '') + '>' + esc(r.name) + '</option>'; }).join('') + '</select></label>' +
        '<p>' + (choices.length ? 'Used for new transcriptions. You can choose another model on Add a video.' : 'Install a model above to select it.') + '</p>' +
        '<p id="sp_model_preference_status" role="status" aria-live="polite">' + esc(preferenceSay) + '</p></div>';
    }
    html += '</section><p class="foot">Fast and accuracy choices describe intended trade-offs; a larger model can still make mistakes. Unavailable packages stay listed so their limits are clear.</p>';
    return html;
  }
  /* ---- the size line of a part not installed: measured, said before anything starts */
  function sizeLine(r) {
    var p = size(r.id), bits = [];
    if (p.download != null) {
      var dl = '<b>' + GB(p.download) + '</b> to download';
      if (p.kept != null) dl += ', kept as about <b>' + GB(p.kept) + '</b>';
      bits.push(dl);
      if (r.needsProgram) bits.push('this includes ' + (r.programLabel || 'the speech program') + ', which comes first');
      if (p.disk_peak != null && p.disk_peak > (p.download || 0) * 1.1)
        bits.push('needs about ' + GB(p.disk_peak) + ' free while it is fetched');
    }
    if (p.have) bits.push(GB(p.have) + ' of it already here, from a download that was stopped');
    if (r.memory) bits.push('needs ' + esc(r.memory) + ' of memory to run');
    return bits.join(' · ');
  }

  function row(r) {
    var st = stateOf(r), j = r.job || {}, id = r.id, facts = '', note = '', act = '', q = asking[id];
    if (j.running) {
      sample(id, j);
      var bits = [];
      if (j.phase === 'build') bits.push('putting the program in place');
      else bits.push(j.total ? GB(j.done) + ' of ' + GB(j.total) : GB(j.done || 0) + ' so far');
      var lt = left(id, j);
      if (lt) bits.push('<b>' + lt + '</b>');
      else if (j.total && j.phase !== 'build') bits.push('<span class="q">working out the time left</span>');
      facts = bits.join(' · ');
      var pc = j.total ? Math.min(100, 100 * j.done / j.total) : null;
      note = '<div class="bar' + (pc == null ? ' loose' : '') + '" role="progressbar" aria-label="' + esc(r.name) + '"' +
        (pc != null ? ' aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round(pc) + '"><i style="width:' + pc.toFixed(1) + '%"></i>' : '><i></i>') + '</div>' +
        (j.say ? '<div class="note">' + esc(j.say) + '</div>' : '');
      act = may('speech.stop') ? '<button class="plain" type="button" ' + (uploads[id] ? 'data-upload-stop' : 'data-stop') + '="' + esc(id) + '" aria-label="Stop getting ' + esc(r.name) + '">Stop</button>' : '';
    } else if (r.withModel) {
      note = '<div class="note">It is installed first, as part of getting ' + esc(r.withModel) + ': see the bar below.</div>';
    } else if (r.na) {
      note = '<div class="note">' + esc(r.naWhy || r.why || 'Not available on this computer.') + '</div>';
      // a program that is here and cannot run (a folder brought to another kind of computer) is still
      // the person's to take away: nothing to get, but the room it holds can be given back
      if (r.have && may('speech.remove')) act += '<button class="plain" type="button" data-remove="' + esc(id) + '" aria-label="Remove ' + esc(r.name) + '">Remove…</button>';
    } else if (r.have) {
      facts = r.facts;
      if (!r.usable && !OLD[r.state]) note = '<div class="note">It cannot be used until the speech program is installed again.</div>';
      if (OLD[r.state]) {
        note = '<div class="note' + (r.state === 'broken' ? ' bad' : '') + '">' + esc(r.why) + '</div>';
        act += may('speech.get') ? '<button class="go" type="button" data-get="' + esc(id) + '">' +
          (r.noResume ? 'Install it again' : 'Get it again') + '</button>' : '';
      }
      if (j.error) note += '<div class="note bad">The last try stopped: ' + esc(said(j.error)) + '</div>';
      else if (j.stopped) note += '<div class="note">You stopped the last try; what is here is unchanged.</div>';
      if (may('speech.remove')) act += '<button class="plain" type="button" data-remove="' + esc(id) + '" aria-label="Remove ' + esc(r.name) + '">Remove…</button>';
    } else {
      facts = sizeLine(r);
      if (r.distribution === 'local-package' && r.package && !r.packageImported) {
        facts = esc(r.package.name || 'Prepared model ZIP') + ' · ' + GB(r.package.size);
        note = '<div class="note">Choose the prepared package ZIP. Parseh checks it, then installs the model without conversion tools.</div>';
        act = may('speech.get') ? '<button class="go" type="button" data-import="' + esc(id) + '">Import &amp; install…</button>' : '';
      } else {
      if (r.noResume && !j.stopped && !j.error)
        note = '<div class="note">It is installed by pip, which cannot carry on a half-fetched file: if you stop it, it starts again from the beginning.</div>';
      if (j.stopped) {
        note = '<div class="note bad">You stopped it' + (j.done ? ' at ' + GB(j.done) : '') + '. ' +
          (r.noResume ? 'The program starts again from the beginning.' : 'Getting it again carries on from there.') + '</div>';
        act = '<button class="go" type="button" data-get="' + esc(id) + '">' + (r.noResume ? 'Try again' : 'Carry on') + '</button>';
      } else if (j.error) {
        note = '<div class="note bad">' + esc(said(j.error)) + '</div>';
        act = '<button class="go" type="button" data-get="' + esc(id) + '">Try again</button>';
      } else {
        // (the name begins with the words the button shows: a voice that says "click Get it" finds it)
        act = '<button class="go" type="button" data-get="' + esc(id) + '" aria-label="Get it: ' + esc(lower(r.name)) + '">Get it</button>';
      }
      if (!may('speech.get')) act = '';
      }
    }
    if (q) note += ask(q, id);
    var credit = r.credit ? '<div class="it-lic">' + r.credit.who + ' · ' + r.credit.licence + '</div>' : '';
    if (r.source || r.limitations && r.limitations.length || r.compatibility) {
      var detail = '<details class="tech"><summary>Model details and limitations</summary>';
      if (r.description) detail += '<p>' + esc(r.description) + '</p>';
      if (r.limitations && r.limitations.length) detail += '<ul class="need">' + r.limitations.map(function (text) { return '<li>' + esc(text) + '</li>'; }).join('') + '</ul>';
      if (r.compatibility && r.fullyCompatible === false && r.available !== false)
        detail += '<p>Package files are verified. Recording-specific timing and transcription quality still need evaluation.</p>';
      detail += '<dl>';
      if (r.source) detail += '<dt>Source</dt><dd>' + esc(r.source.repo || '') + '</dd><dt>Source version</dt><dd>' + esc(r.source.revision || 'Not published') + '</dd>';
      if (r.packageRevision) detail += '<dt>Package version</dt><dd>' + esc(r.packageRevision) + '</dd>';
      detail += '</dl></details>';
      note += detail;
    }
    return '<div class="it' + (j.running ? ' busy' : '') + '" data-row="' + esc(id) + '"><div class="it-main"><div class="it-head">' +
      '<span class="it-name">' + esc(r.name) + '</span>' + (r.tag ? '<span class="tagline">' + esc(r.tag) + '</span>' : '') +
      pill(st.cls, st.glyph, st.word) + '</div>' +
      '<div class="it-for">' + esc(r['for']) + '</div>' +
      (facts ? '<div class="it-facts">' + facts + '</div>' : '') + note + credit + '</div>' +
      '<span></span><div class="it-act">' + (q ? '' : act) + '</div></div>';
  }
  function ask(q, id) {
    if (q.kind === 'wait') return '<div class="ask"><span class="said">' + esc(q.said) + '</span></div>';
    if (q.kind === 'bad') return '<div class="ask bad"><span class="said">' + esc(q.said) + '</span>' +
      '<button class="plain" type="button" data-cancel="' + esc(id) + '">All right</button></div>';
    return '<div class="ask"><span class="said">' + q.said + '</span>' +
      '<button class="danger" type="button" data-yes="' + esc(id) + '">Remove</button>' +
      '<button class="plain" type="button" data-cancel="' + esc(id) + '">Keep it</button></div>';
  }

  /* ---- the processor: the CPU, which always works, and the graphics card, which is used only when proved */
  function needs() {
    return (S.speech.requirements || []).map(function (n) {
      return '<li>' + (n.link ? '<a href="' + esc(n.link) + '" rel="noopener" target="_blank">' + esc(n.what) + '</a>' : esc(n.what)) + '</li>';
    }).join('');
  }
  function tech(hw) {
    var c = hw.cuda, cpu = hw.cpu, sp = S.speech, rt = sp.runtime, dl = [];
    function add(k, v) { if (v) dl.push('<dt>' + esc(k) + '</dt><dd>' + v + '</dd>'); }
    add('Program', rt.ready ? 'faster-whisper ' + esc(rt.version) + ', CTranslate2 ' + esc(rt.ctranslate2) + ', for Python ' + esc(rt.python.replace(/^cp(\d)(\d+)$/, '$1.$2')) : 'not installed yet');
    add('CPU', esc(cpu.compute) + ', ' + cpu.threads + ' thread' + (cpu.threads === 1 ? '' : 's') + ' of ' + cpu.logical + ' logical');
    add('Graphics card', c.name ? esc(c.name) + (c.memory ? ', ' + GB(c.memory) : '') : (c.state === 'none' ? 'none found' : 'not looked at yet'));
    add('Driver', c.driver ? esc(c.driver) : '');
    add('Computes in', c.compute ? esc(c.compute) : (c.ready ? '' : 'not decided until the card is ready'));
    add('cuBLAS', c.cublas_dir ? esc(c.cublas_dir) : '');
    add('Looked at', hw.at ? new Date(hw.at * 1000).toLocaleString('en-GB') : 'not yet');
    add('Kind of computer', esc(sp.platform || 'unknown'));
    return '<details class="tech"><summary>technical details</summary><dl>' + dl.join('') + '</dl></details>';
  }
  function processor() {
    var sp = S.speech, hw = sp.hardware, c = hw.cuda, cpu = hw.cpu, guide = esc(sp.pin.help);
    // WHERE THE PROGRAM CANNOT RUN the processor promises nothing: the program's own row, just
    // below, says Not available and why, and this one gives the reason too and not "ready"
    var na = sp.runtime.state === 'unavailable';
    var cpuRow = '<div class="it" data-row="cpu"><div class="it-main"><div class="it-head"><span class="it-name">Processor</span>' +
      (na ? pill('na', '–', 'CPU · not usable here') : pill('ok', '✓', 'CPU · ready')) + '</div>' +
      '<div class="it-for">' + (na ? 'Speech to text cannot run on this computer: ' + esc(sp.runtime.why) :
        'Speech to text will work on this computer. A compatible NVIDIA graphics card can make it considerably faster, but one is not required.') + '</div>' +
      '<div class="it-facts">' + esc(cpu.said) + '</div></div><span></span><div class="it-act"></div></div>';
    var st, body = '', name = 'Graphics card', act = '';
    var check = '<button class="plain" type="button" data-check title="Look at the graphics card again, for after you have installed something it needed">' +
      (checking ? 'Looking…' : 'Check again') + '</button>';
    if (checking) {
      st = pill('run', '…', 'Looking'); body = 'Looking at the graphics card…';
    } else if (c.state === 'ready') {
      st = pill('ok', '✓', 'GPU acceleration ready');
      name = 'Graphics card · ' + esc(c.name || 'NVIDIA');
      body = 'Automatic mode will use the graphics card for faster transcription. You can still choose CPU if you prefer.';
      act = check;
    } else if (c.state === 'found-not-ready') {
      st = pill('old', '!', 'Found, not ready');
      name = 'Graphics card · ' + esc(c.name || 'NVIDIA');
      body = '<b>NVIDIA GPU found, but speech-to-text acceleration is not ready.</b> CPU transcription will still work.' +
        '<div class="note bad">Missing: ' + c.missing.map(esc).join('; ') + '.</div>' +
        '<div class="note">For GPU acceleration this installation needs:</div><ul class="need">' + needs() + '</ul>' +
        (sp.requirements_note ? '<div class="note">' + esc(sp.requirements_note) + '</div>' : '');
      act = '<a class="plain" href="' + guide + '" data-guide>How to enable GPU acceleration</a>' + check;
    } else if (c.state === 'none') {
      st = pill('not', '○', 'No NVIDIA graphics card');
      body = esc(c.why || 'No NVIDIA graphics card was found on this computer.');
      act = c.supported_build === false ? '' : check;
    } else {
      st = pill('not', '○', 'Not looked at yet');
      body = 'Parseh has not looked at the graphics card yet.';
      act = check;
    }
    var gpuRow = '<div class="it" data-row="gpu"><div class="it-main"><div class="it-head"><span class="it-name">' + name + '</span>' + st + '</div>' +
      '<div class="it-for">' + body + '</div>' + tech(hw) + '</div><span></span><div class="it-act">' + act + '</div></div>';
    var modes = '<div class="modes"><b>Processing</b>, chosen when you add a video:<dl>' +
      '<dt>Automatic — recommended</dt><dd>Uses the graphics card when Parseh can prove it is usable, and the CPU otherwise. Right now: <b>' +
        (c.ready ? esc(c.name || 'the NVIDIA graphics card') : 'the CPU') + '</b>.</dd>' +
      '<dt>CPU</dt><dd>' + (na ? 'Not usable on this computer: the speech program cannot run here.' :
        'Always the CPU, int8. Works on every computer, with or without a card.') + '</dd>' +
      '<dt>NVIDIA GPU</dt><dd>Offered only where the card is ready' + (c.ready ? '' : ' — not on this computer yet') + '.</dd></dl></div>';
    return '<h2 class="part">Processor</h2><section class="shared">' + cpuRow + gpuRow + modes + '</section>';
  }

  function languages(aligners) {
    var chips = S.languages.map(function (L) {
      return '<span class="lang-chip' + (L.whisper ? '' : ' no') + '"><span class="nat" lang="' + esc(L.code) + '"' + (L.rtl ? ' dir="rtl"' : '') + '>' +
        esc(L.native) + '</span><span>' + esc(L.name) + '</span><i>' + (L.whisper ? '✓' : 'not offered') + '</i></span>';
    }).join('');
    var some = S.languages.filter(function (L) { return !L.whisper; });
    return '<h2 class="part">Languages <span class="aside">— every language Parseh has' +
      (some.length ? '; Whisper does not list ' + some.map(function (L) { return esc(L.name); }).join(', ') : '') + '</span></h2>' +
      '<section class="shared"><div class="langs">' + chips + '</div>' +
      (aligners && aligners.length ? '<div class="sp-aligners">' + aligners.map(row).join('') + '</div>' : '') +
      '</section>';
  }

  var ROWS = {};
  var drawn = null;        // what was drawn last: an answer that changes nothing is not drawn again
  var held = null;         // the control that had the keyboard when a press began (see draw)
  // WHICH CONTROL HAS THE KEYBOARD: its first data-… attribute names it, and the row it is in
  function focusToken(el) {
    if (!el || !el.attributes) return null;
    var at = el.closest && el.closest('[data-row]');
    for (var i = 0; i < el.attributes.length; i++) {
      if (el.attributes[i].name.indexOf('data-') === 0)
        return {name: el.attributes[i].name, value: el.attributes[i].value, row: at && at.getAttribute('data-row')};
    }
    return null;
  }
  // ...and where it goes when the page is drawn again: the same control if it is still there, else
  // the safe answer of the row's question ("Keep it", never "Remove"), else the row's first button
  function refocus(tok) {
    var found = null, at = null;
    Array.prototype.forEach.call(root.querySelectorAll('[' + tok.name + ']'), function (el) {
      if (!found && el.getAttribute(tok.name) === tok.value) found = el;
    });
    if (!found && tok.row) {
      Array.prototype.forEach.call(root.querySelectorAll('[data-row]'), function (el) { if (el.getAttribute('data-row') === tok.row) at = el; });
      if (at) {
        found = at.querySelector('.ask [data-cancel]') || at.querySelector('button');
        // a row with nothing to press for a moment (the card is being looked at) keeps the keyboard's
        // place, and gives it back to the button when the button is drawn again
        if (!found) { held = tok; return; }
      }
    }
    found = found || root.querySelector('button');
    try { if (found) found.focus({preventScroll: true}); } catch (e) {}
  }
  function draw() {
    ROWS = {};
    var rows = parts();
    var alignRows = alignerParts();
    rows.concat(alignRows).forEach(function (r) { ROWS[r.id] = r; });
    // THE PROGRAM COMES FIRST: every model below runs on it, and a model is fetched together with it.
    // The choice about the second pass is a choice about those models, so it follows the program.
    var html = '<h2 class="part">Whisper program</h2><section class="shared">' + row(rows[0]) + '</section>' +
      '<div id="sp-second-slot"></div>' + catalogue(rows) + processor() + languages(alignRows);
    drawBand();
    if (html === drawn) return;
    drawn = html;
    // THE KEYBOARD STAYS WHERE IT WAS: drawing replaces every control, once a second while
    // something is fetched and after every press, and a keyboard user would lose the button they
    // were on (a pressed button is disabled at once, which takes the keyboard from it: `held`)
    var now = document.activeElement, inside = now && root.contains(now) && now !== root;
    var tok = inside ? focusToken(now) : (!now || now === document.body ? held : null);
    held = null;
    // the box of the second pass is not drawn here: it is a page element with its own listener, moved into
    // its place under the program each time, with the keyboard if it had it
    var kept = second && second.contains(document.activeElement) ? document.activeElement : null;
    root.innerHTML = html;
    var slot = root.querySelector('#sp-second-slot');
    if (second && slot) { slot.appendChild(second); second.hidden = false; }
    if (kept) { try { kept.focus({preventScroll: true}); } catch (e) {} }
    else if (tok) refocus(tok);
  }
  function drawBand() {
    var who = S.where === 'self' ? 'You are on <b>the computer Parseh runs on</b>.' :
      'You are on <b>' + esc(S.device || 'another device') + '</b>, ' + (S.where === 'vpn' ? 'on a VPN' : 'let in over the Wi-Fi') + '.';
    who += ' ' + (may('speech.get') && may('speech.remove') ? 'You may get, remove and stop anything on this page.' : 'Some of this page is changed on the computer Parseh runs on.');
    band.innerHTML = '<div><div class="n">' + (S.kept ? MB(S.kept) : '0 MB') + '</div><div class="l">kept for speech to text</div></div>' +
      (S.free != null ? '<div><div class="n">' + MB(S.free) + '</div><div class="l">free on this computer</div></div>' : '<div></div>') +
      '<div class="who">' + who + '</div>';
  }

  /* ---- asking the server */
  function post(what, body) {
    return fetch('/lookup/api/' + what, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})})
      .then(function (r) { return r.json().then(function (j) { j.status = r.status; return j; }); });
  }
  function savePreference(url, body) {
    return fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
      .then(function (r) { return r.json(); }).then(function (j) {
        if (!j.ok) throw new Error(j.error || 'Could not save this preference.');
        S.preferences = j.preferences;
        return j;
      });
  }
  function busy() {
    return Object.keys(J()).some(function (k) { return J()[k].running || J()[k].waiting; });
  }
  function refresh() {
    return post('speech', {full: true}).then(function (j) {
      if (!j || !j.ok) return;
      var was = busy();
      S = j;
      draw();
      if (busy() || was) schedule(busy() ? 1000 : 0);
      if (was && !busy() && window.ParsehActivity) ParsehActivity.poke(200);
    // ONE FAILED ANSWER IS NEVER A VERDICT (a phone's Wi-Fi for a moment, a 502): while something was
    // being fetched the next look is asked for all the same, or the bar would stop and say Downloading for ever
    }).catch(function () { if (busy()) schedule(2000); });
  }
  // a request that did not arrive: said, and the row drawn again, which gives its button back
  function lost(id) { asking[id] = {kind: 'bad', said: 'The server did not answer.'}; drawn = null; draw(); }
  function schedule(ms) { clearTimeout(polling); if (ms) polling = setTimeout(refresh, ms); }
  function kick() {
    if (window.ParsehActivity) ParsehActivity.poke(200);
    refresh().then(function () { schedule(1000); });
  }
  function importPackage(id) {
    var r = ROWS[id];
    if (!r || !r.package || uploads[id]) return;
    var input = document.createElement('input'); input.type = 'file'; input.accept = '.zip,application/zip';
    input.style.display = 'none'; document.body.appendChild(input);
    input.addEventListener('change', function () {
      var file = input.files && input.files[0]; input.remove();
      if (!file) return;
      if (r.package.size && file.size !== r.package.size) {
        asking[id] = {kind:'bad',said:'This ZIP does not match the expected package size. Choose ' + (r.package.name || 'the prepared model package') + '.'}; drawn=null; draw(); return;
      }
      delete asking[id];
      var xhr = new XMLHttpRequest(), job = uploads[id] = {running:true,phase:'upload',done:0,total:file.size,say:'Uploading the prepared package…',request:xhr};
      xhr.open('POST', '/settings/api/speech/import-package?model=' + encodeURIComponent(id));
      xhr.setRequestHeader('Content-Type', 'application/zip'); xhr.responseType = 'json'; xhr.timeout = 600000;
      xhr.upload.addEventListener('progress', function (event) {
        if (!uploads[id]) return;
        job.done=event.loaded; job.total=event.lengthComputable ? event.total : file.size;
        if (job.done >= job.total) job.say='Checking the package before installation…';
        draw();
      });
      function finish(error) {
        delete uploads[id];
        if (error) asking[id]={kind:'bad',said:error};
        drawn=null; draw();
        if (!error) kick();
      }
      xhr.addEventListener('load', function () {
        var answer = xhr.response;
        if (xhr.status >= 200 && xhr.status < 300 && answer && answer.ok) finish();
        else finish(answer && answer.error || 'The prepared package could not be imported. The existing model is unchanged.');
      });
      xhr.addEventListener('error', function () { finish('The package upload did not finish. Choose it again to retry.'); });
      xhr.addEventListener('timeout', function () { finish('The package upload timed out. Choose it again to retry.'); });
      xhr.addEventListener('abort', function () { finish('Package upload cancelled. The existing model is unchanged.'); });
      drawn=null; draw(); xhr.send(file);
    }, {once:true});
    input.addEventListener('cancel', function () { input.remove(); }, {once:true});
    input.click();
  }
  function check() {
    if (checking) return;
    checking = true; draw();
    post('speechcheck', {}).then(function (j) { checking = false; if (j && j.ok) { S = j; } draw(); },
                                 function () { checking = false; draw(); });
  }

  root.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b || b.disabled) return;
    var id;
    // (a pressed button is disabled by hand, which takes the keyboard from it, and the next
    // drawing must not be skipped as "nothing changed": it is what gives the button back)
    function press() { held = document.activeElement === b ? focusToken(b) : null; drawn = null; b.disabled = true; }
    if (b.hasAttribute('data-check')) { check(); return; }
    if ((id = b.getAttribute('data-import'))) { importPackage(id); return; }
    if ((id = b.getAttribute('data-upload-stop'))) {
      if (uploads[id]) {
        post('stopspeech', {key:id}).then(function () { refresh(); }, function () {});
        uploads[id].request.abort();
      }
      return;
    }
    if ((id = b.getAttribute('data-get'))) {
      press(); delete asking[id];
      post('getspeech', {key: id}).then(function (j) {
        if (!j.ok) { asking[id] = {kind: 'bad', said: j.error || 'That was refused.'}; draw(); return; }
        kick();
      }).catch(function () { lost(id); });
      return;
    }
    if ((id = b.getAttribute('data-remove'))) {
      var r = ROWS[id], what = id === 'runtime' ? 'the speech program'
        : id.indexOf('align-') === 0 ? 'exact word times for ' + id.slice(6)
        : 'the ' + id + ' model';
      asking[id] = {kind: 'remove', said: 'Remove ' + esc(what) + '? It frees ' + (GB(r.kept) || 'a little room') +
                    '; getting it back is a ' + GB(size(id).download) + ' download.' +
                    (id === 'runtime' ? ' The models stay, but cannot be used until the program is back.' : '')};
      draw(); return;
    }
    if ((id = b.getAttribute('data-cancel'))) { delete asking[id]; draw(); return; }
    if ((id = b.getAttribute('data-stop'))) {
      press();
      post('stopspeech', {key: id}).then(kick, function () { lost(id); });
      return;
    }
    if ((id = b.getAttribute('data-yes'))) {
      press(); delete asking[id];
      post('dropspeech', {key: id}).then(function (j) {
        if (!j.ok) { asking[id] = {kind: 'bad', said: j.error || 'That was refused.'}; draw(); return; }
        refresh();
      }).catch(function () { lost(id); });
    }
  });
  root.addEventListener('change', function (e) {
    var control = e.target;
    if (control.hasAttribute('data-model-language')) {
      catalogueLanguage = control.value; preferenceSay = ''; draw(); return;
    }
    if (control.hasAttribute('data-installed-only')) {
      installedOnly = control.checked; draw(); return;
    }
    if (control.hasAttribute('data-preferred-model')) {
      var code = catalogueLanguage, old = ((S.preferences || {}).models_by_language || {})[code] || '';
      control.disabled = true; preferenceSay = 'Saving…';
      savePreference('/settings/api/speech/select-model', {language:code,model:control.value}).then(function () {
        preferenceSay = 'Saved for ' + languageName(code) + '.'; drawn = null; draw();
      }).catch(function (err) {
        control.value = old; preferenceSay = err.message || 'Could not save this choice.'; drawn = null; draw();
      });
      return;
    }
  });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) refresh(); });

  draw();
  if (busy()) schedule(1000);
  // the graphics card is looked at once, on opening, where it has not been (a child, 0.2 s, no model loaded)
  if (!S.speech.hardware.checked && S.speech.hardware.cuda.supported_build !== false && !checked) { checked = true; check(); }
})();
""".replace("/*ROW_JS*/", lookuppage.ROW_JS)
