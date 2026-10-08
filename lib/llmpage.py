# SPDX-License-Identifier: GPL-3.0-or-later
"""Browser Settings -> LLM Integration; endpoint runtime remains its owner's."""
import llmconfig
import settingspage

PAGE = "/settings/llm/"


def page(where):
    can = settingspage.may("llm.connection", where)
    lock = settingspage.lockline("llm.connection", where)
    main = '''<main class="settings tools" data-layout="browser">
%s
<h1 class="idx">LLM Integration</h1>
%s
<form id="llm_form" data-configure="%s">
<details class="options" id="llm_connection_setup"><summary>Connection setup</summary><fieldset %s>
<legend>Connection</legend>
<div class="form-grid"><label>Connection type <select id="llm_adapter"><option value="openai-compatible">OpenAI-compatible text</option>
<option value="unsloth-studio">Unsloth Studio + installed-model profiles</option>
<option value="unsloth-agent-skills">Unsloth Agent Skills + compatible text</option></select></label>
<label>Provider <select id="llm_provider"><option value="ollama">Ollama</option>
<option value="unsloth">Unsloth</option><option value="generic">Generic OpenAI-compatible</option></select></label>
<label class="wide">Server URL <input id="llm_url" type="url" maxlength="2048" required placeholder="http://127.0.0.1:11434/v1"></label></div>
<p class="field"><label>API key <select id="llm_key_action"><option value="keep">Keep saved key</option>
<option value="replace">Replace key</option><option value="clear">Clear key</option></select></label>
<input id="llm_key" type="password" maxlength="4096" autocomplete="new-password" aria-label="Replacement API key" hidden>
<span id="llm_key_status"></span></p>
<details><summary>Request limits</summary><div class="form-grid"><label>Timeout (seconds) <input id="llm_timeout" type="number" min="1" max="300" value="60" required></label>
<label>Context size (tokens) <input id="llm_context" type="number" min="4096" max="131072" value="8192" required></label></div>
<p class="help">Use a context size supported by your server.</p></details>

<details><summary>Import Unsloth run settings</summary>
<p><label>Studio share link <input id="llm_link" type="url" maxlength="4096"></label>
<button type="button" class="plain" id="llm_import">Read settings link</button></p>
<p class="help" id="llm_import_note">Read the server and model from a Studio link. Save a profile below to apply its model options.</p>
<a id="llm_studio" target="_blank" rel="noopener noreferrer" hidden>Open these settings in Unsloth Studio</a>
</details>
<p class="actions"><button class="go" type="submit">Save connection</button>
<button class="plain" type="button" id="llm_reset">Clear connection</button></p>
</fieldset></details>
<fieldset><legend>Model selection</legend>
<p class="help">You can change the model from any admitted device. Server and API key changes belong to the Parseh computer.</p>
<div class="form-grid"><label class="wide">Available models <select id="llm_model_list"><option value="">Enter a model ID below</option></select></label>
<label class="wide">Model ID <input id="llm_model" type="text" maxlength="512" required></label></div>
<p class="help">Select an advertised model, or enter its exact ID when discovery is unavailable.</p>

<p class="actions"><button type="button" class="go" id="llm_select_model">Save model selection</button>
<button type="button" class="plain" id="llm_models">Refresh models</button>
<button class="plain" type="button" id="llm_test">Test saved connection</button></p>
</fieldset></form>
<details class="options" data-layout="browser"><summary>Saved Unsloth model profiles</summary><div class="option-body">
<p>Save a Studio share link to switch between installed models and their settings.</p>
<div class="form-grid"><label>Profile name <input id="llm_profile_name" type="text" maxlength="100" placeholder="Qwen 4B Q4_1"></label>
<label class="wide">Studio share link <input id="llm_profile_link" type="url" maxlength="4096"></label></div>
<p class="actions"><button type="button" class="plain" id="llm_profile_save">Save profile link</button></p>
<p class="field"><label>Saved profile <select id="llm_profile_list"><option value="">Choose a profile</option></select></label>
<button type="button" class="go" id="llm_profile_apply">Load selected profile</button>
<button type="button" class="plain" id="llm_profile_remove">Remove profile</button></p>
<p class="help" id="llm_profile_info"></p>
</div></details>
<details class="options" data-layout="browser"><summary>Models for experimental review methods</summary><div class="option-body">
<p class="help">Choose a different model for a method, or leave its ID empty to use your general selection.</p>
<h3>Suspect-word review</h3><div class="form-grid"><label>Saved profile <select id="llm_task_suspect_profile"></select></label>
<label>Model ID <input id="llm_task_suspect_model" type="text" maxlength="512"></label></div>
<p class="actions"><button id="llm_task_suspect_save" type="button" class="plain">Save suspect-word model</button></p>
<h3>Whole-text review</h3><div class="form-grid"><label>Saved profile <select id="llm_task_full_profile"></select></label>
<label>Model ID <input id="llm_task_full_model" type="text" maxlength="512"></label></div>
<p class="actions"><button id="llm_task_full_save" type="button" class="plain">Save whole-text model</button></p>
<h3>Reasoning workspace</h3><div class="form-grid"><label>Saved profile <select id="llm_task_workspace_profile"></select></label>
<label>Model ID <input id="llm_task_workspace_model" type="text" maxlength="512"></label></div>
<p class="actions"><button id="llm_task_workspace_save" type="button" class="plain">Save workspace model</button></p>

</div></details>
<div class="connection-status"><p id="llm_destination"></p>
<p id="llm_status" role="status" aria-live="polite"></p>
<p class="help" id="llm_last_test"></p></div>
<p class="privacy">Reviews send transcript text to the saved destination. Audio stays on the Parseh computer. Your API key is saved only on that computer.</p>
<p class="foot">What is set here is kept on the Parseh computer, in <code>config/llm.json</code>, and an
update keeps it. <a href="/guide/site/lookup-and-languages/llm-integration.html">LLM Integration guide</a> &middot;
<a href="/settings/lm-likelihood/">Local LM likelihood model (experimental)</a> &middot;
<a href="/licences/">Licences</a></p>
</main><p data-layout="mobile">LLM Integration is configured in the Browser interface. Switch to Browser using the interface control above.</p>''' % (settingspage.settings_doors(PAGE), lock, "true" if can else "false", "" if can else "disabled")
    return settingspage.frame("LLM Integration &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; llm integration',
                              "LLM Integration", "/guide/", main,
                              style=".tools h3{font-size:14px;margin:18px 0 8px;} .tools #llm_profile_info{overflow-wrap:anywhere}",
                              extra_head='<link rel="stylesheet" href="/lib/settings-tools.css"><script defer src="/lib/llmsettings.js"></script>')
