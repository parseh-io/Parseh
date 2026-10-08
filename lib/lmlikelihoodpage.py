# SPDX-License-Identifier: GPL-3.0-or-later
"""Browser-only standalone scoring settings, separate from chat generation."""
import settingspage

PAGE = '/settings/lm-likelihood/'


def page(where):
    can = settingspage.may('likelihood.worker', where)
    main = '''<main class="settings tools" data-layout="browser">%s
<h1 class="idx">LM likelihood · experimental</h1>
%s
<section><h2>Model</h2><p class="help">You can change this selection from any admitted device.</p>
<label class="field">Installed model <select id="lm_models"><option value="">Refresh to find installed models</option></select></label>
<p class="actions"><button class="go" id="lm_select" type="button">Use selected model</button>
<button class="plain" id="lm_refresh" type="button">Refresh installed models</button></p>
<p class="selected-model" id="lm_selected"></p><p class="help" id="lm_inventory"></p>
<button class="plain" id="lm_unload" type="button">Stop review and free model memory</button></section>
<form id="likelihood_form" data-host="%s">
<fieldset %s><legend>Review options</legend>
<label class="field">Extra suggestion cutoff <select id="lm_probability_preset" required aria-describedby="lm_probability_note">
<option value="" disabled selected>Choose on the Parseh computer</option>
<option value="0">No cutoff</option>
<option value="0.1">0.1 — suggested by preliminary experiments</option>
<option value="custom">Custom cutoff</option></select></label>
<p id="lm_probability_custom" hidden><label class="field">Custom cutoff <input id="lm_minimum_candidate_probability" type="number" min="0" max="1" step="any" aria-describedby="lm_probability_note"></label></p>
<p class="help" id="lm_probability_note">0.1 is suggested by preliminary experiments. This limits extra model suggestions; Whisper’s original word and alternatives are always compared.</p>
<p><label><input id="lm_phonetic_filter" type="checkbox"> Prefer words with a similar sound</label></p>
<p class="help">Turn this off for a wider search on words that still need attention.</p>
<p class="actions"><button class="go" type="submit">Save review options</button></p>
</fieldset>
<details class="options"><summary>Local worker setup</summary><fieldset %s><legend>Setup on the Parseh computer</legend>
<div class="form-grid"><label>Installed models from <select id="lm_source"><option value="unsloth">Unsloth Studio</option><option value="ollama">Ollama</option><option value="path">A local GGUF file</option></select></label>
<label>Ollama server URL <input id="lm_manager_url" type="url" maxlength="2048"></label>
<label class="wide">Local GGUF file path <input id="lm_path" type="text" maxlength="4096" placeholder="Optional; overrides the source when saved"></label></div>
<p class="help">Model files must be accessible on this computer. Parseh reads installed weights in place; install or download them in your model application.</p>
<div class="form-grid"><label>Run on <select id="lm_backend"><option value="cpu">CPU</option><option value="cuda">NVIDIA GPU (CUDA)</option><option value="metal">Apple GPU (Metal)</option><option value="vulkan">GPU (Vulkan)</option></select></label>
<label>CPU threads <input id="lm_threads" type="number" min="1" max="128"></label>
<label>GPU layers <input id="lm_gpu_layers" type="number" min="-1" max="1000"></label>
<label>GPU device <input id="lm_gpu_device" type="number" min="0" max="63"></label></div>
<p class="help">GPU layers: 0 uses the CPU; −1 uses all layers. Choose fewer layers if GPU memory is limited.</p>
<p class="help" id="lm_devices"></p>
<details><summary>Runtime installation requirements</summary>
<p class="help">The separate runtime builds llama-cpp-python 0.3.35. CPU builds need a C/C++ compiler; GPU builds also need their backend SDK. CUDA requires a compatible NVIDIA driver and compiler. Another application’s loaded model still uses its own memory.</p>
<p class="help">Only complete single-file GGUF text models are supported. Split weights and required adapters are refused; optional vision projectors are unused.</p></details>
<details><summary>Compiler and Python paths</summary><div class="form-grid">
<label class="wide">Worker Python <input id="lm_python" type="text" maxlength="4096"></label>
<label class="wide">CUDA C++ compiler (optional) <input id="lm_cuda_host_compiler" type="text" maxlength="4096"></label>
<label class="wide">CUDA architectures <input id="lm_cuda_architectures" type="text" maxlength="80"></label></div>
<p><label><input id="lm_cuda_force_mmq" type="checkbox"> Use CUDA quantized matrix kernels (MMQ)</label></p>
<p class="help">Use native for the current GPU. For GTX 1650/1660, try 61-virtual;80-virtual with MMQ and a compatible CUDA toolkit. An installed compatible compiler under llm-scoring/toolchain is used when no compiler path is entered.</p></details>
<p class="actions"><button class="go" type="submit">Save worker settings</button>
<button type="button" class="plain" id="lm_install">Install or rebuild runtime</button></p>
</fieldset></details>
<details class="options"><summary>Advanced search limits</summary><fieldset %s><legend>Search limits</legend>
<p class="help">These bounds affect only extra model suggestions. The original and every Whisper alternative remain included.</p>
<div class="form-grid"><label>Context size (tokens) <input id="lm_context_tokens" type="number" min="128" max="16384"></label>
<label>Search paths (beam width) <input id="lm_beam_width" type="number" min="1" max="16"></label>
<label>Context before word (characters) <input id="lm_preceding_chars" type="number" min="0" max="8000"></label>
<label>Context after word (characters) <input id="lm_following_chars" type="number" min="1" max="8000"></label>
<label>Extra candidates <input id="lm_candidate_count" type="number" min="1" max="64"></label>
<label>Replacement length (tokens) <input id="lm_replacement_tokens" type="number" min="1" max="16"></label>
<label>Replacement length (characters) <input id="lm_replacement_chars" type="number" min="1" max="200"></label>
<label>Sound similarity limit <input id="lm_phonetic_similarity" type="number" min="0" max="1" step="0.05"></label>
<label>Time per word (seconds) <input id="lm_target_seconds" type="number" min="1" max="600"></label>
<label>Model loading timeout (seconds) <input id="lm_load_seconds" type="number" min="1" max="600"></label></div>
<p class="actions"><button class="go" type="submit">Save search limits</button></p>
</fieldset></details></form>
<div class="connection-status"><p id="lm_status" role="status" aria-live="polite"></p></div>
<p class="privacy">Reviews run locally and need free RAM or GPU memory. A higher-ranked suggestion still needs your review.</p>
<p class="foot">What is set here is kept on the Parseh computer, in <code>config/lm-likelihood.json</code>, and an
update keeps it. The models stay where your model application keeps them: Parseh only reads them.
<a href="/guide/site/lookup-and-languages/lm-likelihood.html">LM likelihood guide</a> &middot;
<a href="/settings/llm/">Connected LLM settings</a> &middot;
<a href="/licences/">Licences</a></p>
</main><p data-layout="mobile">LM likelihood is available in the Browser interface. Switch to Browser using the interface control above.</p>''' % (settingspage.settings_doors(PAGE), settingspage.lockline('likelihood.worker', where),
    'true' if can else 'false', '' if can else 'disabled', '' if can else 'disabled', '' if can else 'disabled')
    return settingspage.frame('LM likelihood &middot; experimental &mdash; %s settings' % settingspage.NAME,
        '<a href="/settings/">settings</a> &middot; lm likelihood &middot; experimental', 'LM likelihood', '/guide/', main,
        extra_head='<link rel="stylesheet" href="/lib/settings-tools.css"><script defer src="/lib/lmlikelihoodsettings.js"></script>')
