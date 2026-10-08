# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings -> Skills for your chatbot (brief §9.5, a0.4.2): each skill Parseh can make for a chatbot that keeps
skills, its size, its version and its hash, a button that downloads it, and under them how to install it and use
it, tool by tool.

A SKILL IS MADE WHEN IT IS ASKED FOR, from the same parts as Parseh's own prompts (lib/skills.py), and kept nowhere:
the page shows what it would be now and the download builds the zip the moment it is pressed.  EVERY DEVICE LET IN
MAY READ AND DOWNLOAD (nothing here changes anything Parseh runs: there is no setting behind this door), and there
is NO INSTALL BUTTON: installing a skill is always the person's own step in the chatbot, whatever the tool.

THE STEPS BELOW ARE WHAT THE CHECKED FACTS SAY (2026-09-29, from each tool's own help pages) and nothing more; each
tool has a link to its own help, and nothing is fetched.  Where a fact is not known the page says that it is not.
"""
import html
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import settingspage                                          # noqa: E402
import skills                                                # noqa: E402

PAGE = "/settings/skills/"
GUIDE = "/guide/site/studio/skills.html"
DOWNLOAD = "/settings/api/skills/download?name="
# what the browser remembers of the skill it downloaded last: lib/llmrow.js reads the same key
KEY = "parseh_skill_"


def esc(s):
    return html.escape(str(s), quote=True)


def kb(n):
    return "%s KB" % format(max(1, int(round(n / 1024.0))), ",")


def view():
    """What the page draws, in one answer."""
    return {"ok": True, "skills": skills.catalog(), "version": skills.version.VERSION}


def _card(c):
    name = c["name"]
    if not c.get("available", True):
        return ('<section class="sk" data-skill="%s" data-unavailable><h2><code>%s</code></h2><p class="what">%s</p>'
                '<p class="old">This skill cannot be made now: %s</p></section>'
                % (esc(name), esc(name), esc(c["what"]), esc(c["why"])))
    return """<section class="sk" data-skill="%(name)s" data-hash="%(hash)s">
<h2><code>%(name)s</code></h2>
<p class="what">%(what)s</p>
<p class="facts">Parseh <b>%(version)s</b> &middot; hash <code data-hash-shown>%(hash)s</code> &middot; %(files)d files,
<span data-size>%(zip)s</span> as a zip (%(chars)s characters of instructions, the largest file %(biggest)s)</p>
<p class="old" data-old hidden>You downloaded this skill before, and this Parseh makes another one now: your skill may be
older than this Parseh &mdash; download it again.</p>
<div class="row"><a class="primary" href="%(href)s" download="%(name)s.zip" data-download>download (.zip)</a>
<span class="said" data-said></span></div>
</section>""" % {"name": esc(name), "hash": esc(c["hash"]), "what": esc(c["what"]), "version": esc(c["version"]),
                 "files": c["files"], "zip": kb(c["zip"]), "chars": format(c["chars"], ","),
                 "biggest": format(c["biggest"], ",") + " characters", "href": esc(DOWNLOAD + name)}


# ONE PLACE FOR THE WORDS OF EACH TOOL, so that the page and the guide (html-guide/markdown/studio/skills.md) say the
# same: what the checked facts say, tool by tool, with the tool's own help
TOOLS = (
    ("claude.ai and the Claude desktop app",
     "Open <b>Customize &rarr; Skills</b>, press <b>+</b>, then <b>Create skill</b> and <b>Upload a skill</b>, and choose "
     "the zip. Skills need code execution: turn on <b>Settings &rarr; Capabilities &rarr; Code execution and file "
     "creation</b> first, and check the skill's switch is on afterwards. On a Team or Enterprise plan an Owner decides "
     "whether skills are allowed. Some people still see the older wording, <b>Settings &rarr; Capabilities</b>. "
     "Uploading the same name again may ask you to replace the one you have.",
     (("Use skills in Claude", "https://support.claude.com/en/articles/12512180-use-skills-in-claude"),
      ("How to create custom skills", "https://support.claude.com/en/articles/12512198-how-to-create-custom-skills"))),
    ("Claude Code",
     "Unzip the zip and put its folder in <code>.claude/skills/</code> inside your home folder to have it in every "
     "project, or inside one project's folder to have it there. A skill you uploaded to claude.ai reaches a Claude Code "
     "that is signed in to the same account (version 2.1.273 or newer) by itself.",
     (("Claude Code: skills", "https://code.claude.com/docs/en/skills"),)),
    ("Codex, Gemini CLI, Cursor, GitHub Copilot and VS Code",
     "Unzip the zip and put its folder in <code>.agents/skills/</code>, inside your home folder for every project or "
     "inside a project's folder for one. Claude Code does <b>not</b> read <code>.agents/skills/</code>; Copilot, VS Code "
     "and Cursor also read <code>.claude/skills/</code>.",
     (("Codex", "https://learn.chatgpt.com/docs/build-skills"),
      ("Gemini CLI", "https://geminicli.com/docs/cli/skills/"),
      ("Cursor", "https://cursor.com/docs/skills"),
      ("GitHub Copilot", "https://docs.github.com/en/copilot/concepts/agents/about-agent-skills"),
      ("VS Code", "https://code.visualstudio.com/docs/agent-customization/agent-skills"))),
    ("The Gemini app",
     "<b>Settings &rarr; Skills &rarr; Upload</b>, and choose the zip. Uploading is done on the web or in the Mac app; "
     "the mobile app can use a skill once it is uploaded. Google says it is for personal accounts, 18 or older.",
     (("Gemini: skills", "https://support.google.com/gemini/answer/17102773"),)),
    ("ChatGPT",
     "Only on the workspace plans (Business, Enterprise, Healthcare and Edu): <b>Plugins &rarr; Skills &rarr; Create "
     "&rarr; Upload from your computer</b>. OpenAI's pages do not name an upload for the Free, Plus or Pro plans.",
     (("Skills in ChatGPT", "https://help.openai.com/en/articles/20001066-skills-in-chatgpt"),)),
    ("A phone",
     "Install the skill on the web or in the desktop app: a skill belongs to your account and not to one device. What "
     "the tools say about <b>using</b> one on a phone is only that Claude's Cowork sessions do; whether a plain chat on a "
     "phone does is not documented, so nothing more is promised here.",
     (("Cowork on web, desktop and mobile",
       "https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile"),)),
    ("A chatbot with no skills",
     "Use <b>copy the prompt</b> instead: it is the same instructions in one paste. A project or a Gem keeps files, but "
     "loads them whole, so the files of a skill are not free there.",
     ()),
)


def _tools():
    out = []
    for name, steps, links in TOOLS:
        out.append('<div class="tool"><h3>%s</h3><p>%s</p>%s</div>' % (
            name, steps, ('<p class="links">%s</p>' % " &middot; ".join(
                '<a href="%s" target="_blank" rel="noopener">%s</a>' % (esc(u), esc(t)) for t, u in links))
            if links else ""))
    return "".join(out)


def page(where=""):
    """/settings/skills/, the whole page."""
    cards = "".join(_card(c) for c in skills.catalog())
    main = """<main class="settings sk-page">
%(doors)s
<h1 class="idx">skills for your chatbot</h1>
<p class="whomay">%(gate)s <span>Any device that has been let in may read this page and download a skill. Installing
one is always your own step, in the chatbot: there is no install button.</span></p>
%(cards)s
<section><h2>Installing a skill</h2>
<p class="why">Download the zip above, then do what your chatbot's own help says &mdash; here is what each tool says today,
with its help page. A chat opens the skill's files only when it needs them, so the many files cost nothing until a
request names one.</p>
%(tools)s
<p class="why">Some tools (Microsoft 365 Copilot's Cowork and Agent Builder) want SKILL.md at the root of the zip and not
inside a folder: unzip it, and zip the folder's <i>contents</i>.</p>
</section>
<section><h2>Using it</h2>
<p class="why">Beside <b>copy the prompt</b>, wherever %(name)s hands a prompt out for a skill, is
<b>copy the request for the skill</b>: one line that names the skill and the language, the mode and what you ticked,
and then only the text to work on. Paste it in a chat where the skill is installed. In a chat where it is not, the line
itself tells the chatbot to say so, and <b>copy the prompt</b> is the way. If a request is for a newer %(name)s than the
skill you installed, the chat says so in one line: download the skill again here.</p>
<p class="why">A prompt of yours that is <i>added</i> to %(name)s&rsquo;s goes after the request's first line; one <i>in place
of</i> %(name)s&rsquo;s cannot travel in it, because the skill carries %(name)s&rsquo;s instructions.</p>
</section>
<p class="foot">Made when you ask, from the same parts as the prompts, and kept nowhere. <a href="%(guide)s">Skills for
your chatbot</a>, in the guide.</p>
</main>""" % {"doors": settingspage.settings_doors(PAGE), "gate": settingspage.gate(settingspage.door_keys(PAGE)), "name": settingspage.NAME,
              "cards": cards, "tools": _tools(), "guide": esc(GUIDE)}
    return settingspage.frame("Skills for your chatbot &mdash; %s settings" % settingspage.NAME,
                              '<a href="/settings/">settings</a> &middot; skills for your chatbot',
                              "Skills for your chatbot", GUIDE, main, style=STYLE, script="<script>%s</script>" % SCRIPT)


STYLE = r"""
.sk-page .whomay{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap;margin:.2rem 0 1rem;font-size:13.5px;color:var(--dim)}
.sk-page .whomay .gate{flex:none}
.sk-page .sk{border:1px solid var(--rule);border-radius:10px;padding:10px 14px;margin:10px 0;background:var(--card)}
.sk-page .sk h2{margin:0 0 4px;font-size:17px;overflow-wrap:anywhere}
.sk-page .what{margin:.2rem 0}
.sk-page .facts{color:var(--dim);font-size:13px;margin:.3rem 0}
.sk-page .old{margin:6px 0 0;font-size:13.5px;border-inline-start:3px solid var(--warn);padding:2px 0 2px 10px}
.sk-page .row{display:flex;gap:8px 12px;flex-wrap:wrap;align-items:center;margin-top:8px}
.sk-page a.primary{display:inline-block;padding:.45rem .9rem;border-radius:8px;border:1px solid var(--accent,#be3455);
  background:var(--accent,#be3455);color:var(--accent-fg,#fff);text-decoration:none;font-weight:600}
.sk-page a.primary:hover{filter:brightness(1.08)}
.sk-page .said{font-size:13.5px;min-height:1.4em}
.sk-page .tool{margin:.7rem 0;padding:.1rem 0 .1rem 12px;border-inline-start:3px solid var(--rule)}
.sk-page .tool h3{margin:.1rem 0;font-size:15px}
.sk-page .tool p{margin:.2rem 0;font-size:14px}
.sk-page .tool .links{color:var(--dim);font-size:13px}
.sk-page .tool .links a,.sk-page .foot a{color:var(--accent,#be3455);text-decoration:underline}
.sk-page code{overflow-wrap:anywhere}
"""

SCRIPT = r"""
(function () {
  'use strict';
  var KEY = '%s';
  function get(name) { try { return localStorage.getItem(KEY + name); } catch (e) { return null; } }
  function put(name, hash) { try { localStorage.setItem(KEY + name, hash); return true; } catch (e) { return false; } }
  Array.prototype.forEach.call(document.querySelectorAll('[data-skill]:not([data-unavailable])'), function (card) {
    var name = card.getAttribute('data-skill'), hash = card.getAttribute('data-hash');
    var old = get(name);
    // WHAT THIS DEVICE DOWNLOADED LAST is remembered (in try: storage may be refused), and said when it is not what
    // Parseh would make now
    card.querySelector('[data-old]').hidden = !(old && old !== hash);
    card.querySelector('[data-download]').addEventListener('click', function () {
      put(name, hash);
      card.querySelector('[data-old]').hidden = true;
      card.querySelector('[data-said]').textContent = 'downloading ' + name + '.zip — install it in your chatbot as below';
    });
  });
})();
""" % KEY
