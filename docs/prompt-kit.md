# The prompt kit

`lib/promptkit.py` assembles every copyable prompt Parseh hands to a chatbot.
It writes the prompt, and the relevant feature checks and files the answer.
Parseh holds no connection to a model service (the one it had for the ASR review
went with a0.6.3): a prompt reaches a model only through a person's copy and
paste, or a skill. This page is for whoever changes a copyable prompt.

## A surface, and its three parts

A **surface** is one place a prompt comes from. Each has ONE readable template
file, and the file is the whole prompt.

| surface | template | assembled by |
|---|---|---|
| `studio-doc` | `markdown/exlex/PROMPT.md` (after its first `---`) | `markdown/app/server.py` `studio_prompt` |
| `studio-exercises` | `markdown/exlex/EXERCISES_PROMPT.md` | `server.py` `exercise_prompt` |
| `video-new` | `youtube/docs/chat-prompt.md` + `conventions.md` | `ytpages.assembled_chat`, `assembled_full` |
| `video-region`, `book-region` | `docs/region-prompt.md` | `glossregion.assembled` |
| `book-new` | `docs/new-book-prompt.md`, made from the parts in `docs/book-method/` | `making.instructions_text`: the folder's `AGENTS.md`, the page's preview and the `parseh-book` skill |
| `transcript-tidy` | `PROMPT` in `youtube/lib/tidy.py` | `tidy.assembled` |
| `ask` | `lib/llm.js` | the browser |
| `asr-suspect`, `asr-full`, `asr-workspace` | `docs/asr-*-prompt.md` | `asrexternal.assembled` |

Every prompt has three parts, in this order:

1. the **instructions**: how to do the job. Parseh's, or a person's own;
2. the **answer contract**: the shape of the answer and how to send it (one
   fence, the JSON, several messages, the later block wins, file or fence).
   Always Parseh's, for every prompt whose answer Parseh reads back;
3. the **data**: captions, chunks, page, question. Always Parseh's, last.

In a template, `{{?contract}}…{{/contract}}` and `{{?data}}…{{/data}}` mark the
second and third part; everything else is the instructions. A mark sits against
its words on the side its whitespace belongs to, so taking the marks out gives
the file as it was (`promptkit.flat`). A contract may be several blocks, and a
sentence may be split from its paragraph: the kit joins the blocks with a blank line.

## Blocks and placeholders

`{{?flag}}…{{/flag}}` is kept where the flag is true. `{{NAME}}` is filled from
what the caller gives; `placeholders(surface)` lists the names with a line each
(the editor of a person's own prompt shows it). Both are the same everywhere:
templates, the language files, a person's instructions.

- **A resolved prompt never carries `{{`**: the kit refuses one that does, and a
  block whose flag nobody gave, in words (`PromptError`). It is a bug.
- **`verbatim`** values and the **data** are never looked into: a caption or a
  title may say `{{`. Parseh's own text put in by hand (`lead`, `extras`) is
  looked into with `promptkit.check(text, surface)`, which is `assemble`'s test.
- Flags of every text of a surface: `book`, `video`, `studio`, `region`, `new`
  and the options' `ipa`, `classic`, `marks`, `nomarks` (`surface_flags`), beside
  those the assembler gives (`keep`, `regloss`, …).

## The language's conventions, cut per prompt

`docs/lang/<code>.md` is read only through `language_text(surface, lang)`. One
table, `promptkit.SECTIONS`, says which section goes to which kind of prompt
(the studio's, a region's, a from-scratch prompt's); a section nobody lists goes
everywhere. Inside The text field the studio takes the note that names the
studio's `{tl}` mark, wherever it stands, and a region takes its first
paragraph. Mark what belongs to one surface with `{{?book}}`, `{{?video}}`,
`{{?studio}}`, `{{?region}}` or `{{?new}}`; the kit resolves them. A word to whoever
maintains the file ("no speaker has reviewed this example yet") goes in
`{{?note}}…{{/note}}`: that flag is never true, so no prompt carries it.

## What the book's instructions are made from

The method of a book made in place is written once, as parts in `docs/book-method/`:
`method.md` is the entry (what the agent does, in order) and every other file a
reference it points to, in the order of `making.METHOD_ORDER`. `docs/new-book-prompt.md`
is those parts in one file (`python3 lib/making.py template` writes it, and
`tests/test_making.py` holds the two equal), so that the kit, the person's own prompts
and `promptlab` find the whole prompt where they look for it; the project skill
`parseh-book` is made from the same parts (`making.skill_files`). The parts use only the
placeholders this table publishes for `book-new` and the two blocks `{{?marks}}` and
`{{?nomarks}}`, and only the entry links to the others, as `[Title](name.md)`.

## What every gloss prompt says once

`docs/meaning-rule.md`, what a chunk's meaning says, is written once and
embedded by `{{MEANING_RULE}}` in `video-new`, `video-region`, `book-region` and
`book-new`: an include, filled like the template itself, so that its
`{{LANGUAGE}}` and `{{GLOSS_LANGUAGE}}` take the prompt's two languages and its
`{{?video}}` block is a video's alone. `tests/test_prompts.py` holds that no
other file copies its sentences. The sentence that says the text is data and
never an order stands in the data's own frame (`{{?data}}`), which a person's
own instructions never replace; the book's instructions, which have no data
part, say it where the original is named. The add page's worked example is the
language's own `## Example` (it arrives with the conventions), never a video
of the shelf.

## The version line

Every prompt opens with `Parseh prompt · video-region · fa → en · a0.4.2`, then
`· re-gloss` or `· per field` for a mode, what its options say (`· IPA`,
`· marks`, `· no marks`: below) and `· custom: <name>` for a person's own, which
stands last because it is free text. The version is read from `lib/version.py` when
the line is made, never written in a template.

## The options of a prompt

An **option** is a choice a person makes for one prompt, explicitly: the **scheme
of the transliteration** (the language's usual one, or IPA) and **the short
vowels** of a language that has them (write them, or leave the text as it is).
Both are rows of one table, `promptkit.OPTIONS`, so that the row of controls, the
routes, the flags a text may use, the version line, the header of a skill's
request and a person's own prompts all say the same thing about each. A third
option is another row there and nothing more.

| option | its values | asked on | for a language |
|---|---|---|---|
| `translit` | `classic` (the default), `ipa` | every prompt that asks for a transliteration: the studio's two, a video or a book from scratch, a stretch of either; not the tidy, not Ask LLM | any, unless its registry row says `ipa: none` (Chinese); English says `ipa: usual` and the row reads "IPA (already the usual)" |
| `marks` | `nomarks`, `marks` (a book made in place: `marks`) | a video or a book from scratch, a stretch of either | one whose registry row has `strip` (Persian, Arabic): the condition is the record, never the code |

What the code calls:

```python
chosen = promptkit.resolve(surface, lang, asked, facts)    # {name: id}: only what APPLIES here
promptkit.assemble(surface, lang, gloss, ..., options=asked)   # the Assembled carries .options
promptkit.describe(surface, lang, asked, facts)                # what a page draws, from the server
promptkit.header_fields(surface, lang, asked)                  # ['translit: ipa', 'marks: on'] (lane G)
promptkit.given(body_or_query)                                 # the options a request named
```

- A request names an option by its name (`translit=ipa`, `marks=1`; JSON `true` and
  `"on"` also mean `marks`). A value that is none of the option's is **refused in
  words** (`OptionError`, a `PromptError`) wherever it is meant; an option that
  does **not apply** (the short vowels of Italian, IPA for Chinese, either on the
  tidy) is left out instead, so that what a device remembers of one prompt cannot
  stop another, and the answer's `options` says what each came to.
- `facts` are what a book's or a video's own record says (`book.json`, `video.json`:
  `"translit": "ipa"`). They are the default; what a request says wins. A page that
  asks about a book or a video that exists passes the key even when the record has no
  value (`{"translit": None}`): the descriptor's `record` is then true, because a record
  that says nothing says the usual scheme, and the row tells a person who asks for IPA
  for a stretch that the book would mix the two, and offers to make IPA the book's. A
  page that asks about none (the add page, the studio) passes no facts.
- **Flags**: `ipa` and `classic`, `marks` and `nomarks`, in every text of a prompt
  (a template, a language file, a person's own): `{{?ipa}}…{{/ipa}}`. The first of
  each pair is true by default; where the language has no short vowels neither of the
  second pair is, and where IPA is not offered the usual scheme stands.
- **Placeholders**: `{{TR_LABEL}}` is "IPA" when the prompt asks for it, `{{TR_SCHEME}}`
  names the scheme ("IPA", or "the usual rōmaji scheme for Japanese"), `{{MARKS_RULE}}`
  says what is asked of the short vowels (empty where the language has none).
- **A language file with no `{{?ipa}}` block** of its own is given a general paragraph in
  front of its conventions when IPA is chosen (it says what holds for any language), so that
  the setting works for every language, a person's own among them; a file's own note
  replaces it.
- **The version line** ends with what the options say, before a person's own prompt's name:
  `· IPA`, `· marks` or `· no marks` (only where the language has short vowels).
- **The row** (`lib/llmrow.js`) draws them as "rōmaji: [usual scheme ▾]" from
  `GET /__prompt/options?surface=…&lang=…[&book=…|&video=…]`; a page puts what the row
  says in the request that makes the prompt (`row.options()`) and gets `options` back.
  A choice is remembered on this device per language (the scheme) or per surface (the marks).
- **The short vowels are also a contract with the answer.** With `marks` the templates of a
  stretch (`docs/region-prompt.md`) and of a video from scratch (`youtube/docs/chat-prompt.md`) say
  that `fa` may come back with its short vowels added and nothing else changed; the apply routes
  take the same `marks` and `lib/glossregion.py` decides again, from the request and the language's
  record, what may be written: the answer's `fa`, with the gloss it lands with, only when it is the
  page's own text with marks added and nothing else, and only into a chunk that has none, through the
  doors of a hand edit. The report counts `vowelled` and says why a chunk's marks were kept out.
- **The book's or the video's own record**: `translit` is written when a book is made
  (`making.make`) or a video added (`ytpages.api_add`) with IPA chosen, and changed through
  `bookmeta.edit_meta` and `ytpages.edit_meta`. It is an optional key an older Parseh ignores, so no
  format number is raised. The checks written for the usual scheme step aside for it
  (`lib/check_batch.py`, `lib/normalize_batch.py`).

## For a person's own instructions

`assemble(surface, lang, gloss, instructions=text, …)` puts the person's text in
place of Parseh's; the contract and the data come after it and are Parseh's.
`parts(surface)`, `instructions(surface)` and `contract(surface)` give a
template's raw parts. A person's text may not carry the marks of the parts.

## Your own prompts

`lib/prompts.py` keeps the prompts a person wrote, in `config/prompts.json`
(`STORE_FORMAT`; a prompt is exported as a file in `EXPORT_FORMAT`; both have a
row in `lib/version.py` `FORMATS`). Parseh's own prompts are not in it, so no
route can delete or overwrite one. A prompt has an `id` (what a route is given,
never the name), a `name` (one per place, ignoring case), a `surface`, a `kind`,
its `text`, `languages` (`[]` for every language, or one code) and, for the kind
`replace`, `based_on`: the surface, the version and the text of Parseh's
instructions it began from.

| kind | the kit is handed | a new one begins as |
|---|---|---|
| `added` (the default) | Parseh's raw instructions, then the person's text | empty |
| `replace` | the person's text alone | a copy of Parseh's raw instructions |

Either way the contract and the data are Parseh's, after the text. For `ask` and
`book-new` nothing is read back, so nothing is locked (`parseh(surface)["locked"]`
is false) and the whole text may be the person's; `ask`'s words are held in
`prompts.ASK` (the page builds its prompt in JavaScript) and a test holds them to
`lib/llm.js`. A text is checked when it is saved (`check_text`): a placeholder the
kit does not publish for that place (`known_names`), a block it does not know, the
marks of a part, a double brace that is none of these: refused in words, with the
kit's own dry run as the last word.

### What the code calls

```python
chosen = prompts.resolve(surface, prompt_id, lang)       # None: Parseh's own
promptkit.assemble(surface, lang, gloss, ...,
                   instructions=chosen and chosen.instructions,
                   custom=chosen and chosen.name)          # the version line ends `· custom: <name>`
```

`resolve` refuses in words an id that is gone (`prompts.NotFound`, status 404) and
one for another place or another language (`prompts.PromptsError`, status 400).
`Chosen` is `(id, name, kind, text, instructions)`: `instructions` is what the kit is
handed, `text` the person's own words alone, `kind` what Lane G needs (an `added`
prompt travels in a skill's short request, a `replace` cannot).
`prompts.instructions_for(surface, id, lang)` is the same for a caller that wants
the string alone; for `book-new` it is the whole prompt as the page fills it.

The doors take `prompt=<id>` in their body: `POST /youtube/api/region/prompt` and
`<book>/__region/prompt` (the id goes to `glossregion.book_prompt` and
`video_prompt`, which resolve it against the stretch's language), `/youtube/api/prepare`
(`ytpages.assembled_full`), `/youtube/api/transcript` with `prompt` an id where
`true` is Parseh's own (`tidy.assembled`). The answer then carries
`custom: {id, name, kind}`. The studio's two routes take it too: `GET /api/prompt?target=fa&prompt=<id>`
and `POST /api/exercise-prompt` with `prompt` in the body (`markdown/app/server.py`
`studio_prompt(..., chosen=)` and `exercise_prompt(..., chosen=)`). Their answer's `custom` is
what THIS answer was made from, `false` for Parseh's own and `{id, name, kind}` for a person's, and
a request that names no prompt gets Parseh's own, whatever the page used to keep (the one custom
prompt the studio kept before a0.4.2 is a prompt among the others now, chosen like them). A
prompt of kind `added` goes after Parseh's instructions and takes the boxes (and, for the
exercises, the types) like Parseh's own; one `replace` takes them only if its text carries their
`{{?id}}` blocks (`promptboxes.has_box_marks`; for exercises also a type's `{{?type_…}}`), and is
otherwise copied whole: every box this language is offered, and every type, then says
`disabled: "<the one sentence>"` (`server.INERT`) and the page draws it once above them. Where the
kit refuses a prompt of yours at the door (it named something Parseh no longer fills in), say it
with `prompts.unmade(chosen, error)`: the kit's words speak of a bug in a template, which a
person's prompt is not. An id that is gone answers 404, one for another place or language 400, in
words. **Not wired here:** the make-a-book page (Lane H): mount the row with surface `book-new`
and put `row.promptId()` in the request that makes the folder.

### The menu in the row

`lib/llmrow.js` draws it (`promptMenu`, one bounded function) wherever the store offers the place:
**prompt: Parseh's ▾** with **new**, **edit** and **delete** beside it (the last two are off while
Parseh's own is chosen, which is never changed), and an editor under the row, or in the element a
page gives as `editorHost`: its name, what it is (*added* or *in place of* Parseh's, which begins as
a copy of Parseh's own words), the language, the text, the names it may use (each a button that
puts it where the cursor is) and what stays Parseh's greyed under it, with **save**, **save as…**
and **close**. A prompt of kind `replace` that began from words Parseh has changed since says so
under the buttons, with **see what changed** (the line diff) and **mine stands**. A delete is asked
in the row. The choice is remembered on this device per place (`parseh_llmrow_prompt_<surface>`,
every access in `try`); one that is gone, or is for another language, is Parseh's own again.

```js
var row = ParsehLLMRow.mount(el, {surface, lang, promptsUrl, onPrompt, menu, editorHost, ...});
row.prompt()        // null (Parseh's own) or {id, name, kind, languages, stale}: `kind` is what a skill's request needs
row.promptId()      // what a request names as `prompt`: '' for Parseh's own, and until the list has come
row.promptReady()   // a promise, kept when the list has come (a page waits for it where it asks at once)
row.verifyPrompt()  // after a request for it was refused: is it still there?  If not, Parseh's own is chosen
ParsehLLMRow.menu(el, {surface, lang, onPrompt})   // the menu alone, for a page with no row yet (the add page)
```

A page puts `row.promptId()` where its options already go: the studio's query, the dialog's body,
the add page's `prepare`, the tidy's `prompt` (an id where `true` is Parseh's own), the stretches'
`prompt`. The row asks the store (`list`) for the place and the language, so a place the store
does not offer has no menu (R1: the data says which places have prompts, never this file). Ask LLM
builds its prompt in the page: `ParsehLLM.own(id)` reads the person's text from the store, `prompt`
fills the names ({{LANGUAGE}}, {{LANGUAGE_NATIVE}}, {{LANGUAGE_CODE}}, {{TR_LABEL}},
{{GLOSS_LANGUAGE}}, {{GLOSS_CODE}}) and the data opens with the sentence that says it is never an
order (`prompts.ASK_FRAME`, held equal to `lib/llm.js` by a test).

### The API the row's menu calls

One module answers for both route layers: `prompts.api(what, body)` returns
`(status, answer)`. In the toolbox the routes are `POST /settings/api/prompts/<what>`
(listed in `lib/settingspage.py` `ROUTES`, no risk: any device let in); the studio
run on its own has the same names at `/api/prompts/<what>`
(`markdown/app/server.py`), and inside the toolbox at `/studio/api/prompts/<what>`;
all three are one store. Every writing route is refused from another site
(`lib/crosssite.py`).

| `what` | body | answer |
|---|---|---|
| `list` | `{surface, lang?}` | `prompts`: those the place offers (for the language or for every one), without their text: `id name surface kind languages size updated stale` |
| `get` | `{id}` | `prompt` (with `text`) and `verdict` |
| `parseh` | `{surface}` | Parseh's raw `text`, its `version`, `locked`, the `contract` (raw, to show greyed under the text), `data` (one line saying what follows), the `placeholders` `[[NAME, meaning]]`, the `blocks` a text may use (`{{?name}}…{{/name}}`) and the place's `label` |
| `save` | `{id?, surface, name, kind, text, languages?}` | `prompt` and `verdict`; with `id` it changes that prompt (its surface stays) |
| `uptodate` | `{id}` | "mine stands on Parseh's as it is now": records the current version, `prompt` and `verdict` |
| `delete` | `{id}` | `{ok}` |
| `import` | `{data}` (an exported file's text) | `prompt`, and `renamed_from` when the name was taken |
| `state` | `{}` | every prompt, the places and the languages: what Settings draws |

`GET .../export?id=<id>` downloads the file. Every refusal is `{ok: false, error}`
in words, with 400 (404 for an id that is gone). `verdict` is `null` for a prompt
that is added, `{known, stale, was, now, diff}` for one in place of Parseh's;
`diff` is a line diff of what changed in Parseh's own since, `[{op: "+" | "-" | " ",
text} | {op: "…", skipped: n}]`, and `known` is false where nothing was recorded of
what it began from (the studio's old prompt, from before a0.4.2). `stale` is on
every listed prompt too, so a menu can say it without asking for the diff.

The placeholders the page fills for `ask` are the kit's four and `{{GLOSS_LANGUAGE}}`
and `{{GLOSS_CODE}}` (`prompts.EXTRA`: the kit publishes a name only for the prompts
it fills itself, and its tests pin that).

### The studio's old prompt

The custom prompt the studio kept as `markdown/library/_prompt.md` moves into the store
once, at the first start (`store.move_prompt`, from `server.migrate_library`), as
"my studio prompt (from before a0.4.2)", surface `studio-doc`, kind `replace`, with no
record of what it began from. The store's marker (`moved`) makes it once and only once:
the file's return, written by an older Parseh, is never moved again. The studio's old
single-prompt routes (`GET/PUT/DELETE /api/prompt`) keep working on that prompt.

## Skills

`lib/skills.py` makes the prompts again as **skills** for a chatbot that keeps them (`parseh-gloss`,
`parseh-markdown`, `parseh-book`), when one is asked for and from the same parts, never from a copy.
The kit lets it leave open what only a request knows: a flag given `promptkit.Open(words)` stays in the
text as `⟦if words⟧ … ⟦end words⟧`, a placeholder given one as `⟨name⟩`; `render` and `take_out` do the same
for a piece of a template (the studio's box blocks become files of their own). What the person chooses
(the language, the options) is a file already resolved, so a model never reads two variants and picks.
`skills.read_*` does what a skill tells a model to do, mechanically, and `tests/test_skills.py` holds its
result to the prompt road for every surface, language, mode, box and exercise type.

The short request is `Parseh request · <skill> · <version> · <hash> · …` (`parse_header`), then the data;
`for_region`, `for_new_video`, `for_studio`, `for_exercises` and `for_book` make it from a prompt's own
`Assembled`, and the routes that hand a prompt out answer with it as `skill`. A prompt of the person's of
kind `added` follows the header; one in place of Parseh's cannot travel (`available: false`). A book made in
place keeps its own copy of the book's skill in its folder (`skills.build_for_book(L, G, options, values).files`:
every mark settled for that book, only its language's file), where an agent that looks for a skill finds it.
A skill is checked by `skills.validate` (front matter with `name` and `description` only; a description of 200
characters at most, no `<` or `>`; SKILL.md under 500 lines; every reference named in it) and its zip by
`skills.check_zip`. Do not scan, list or touch `lib/asrskill/`: those skills are the a0.4.3 branch's own.

## Adding a surface

1. Write its template, marking the contract and the data.
2. Name it in `SURFACES` and `TEMPLATES` (or `register()` a template held in code),
   add its placeholders to `_PLACEHOLDERS`, and its row to `LAYOUT`/`KIND` if it
   takes the language's conventions.
3. Write its assembler: build the values, call `assemble`, return the `Assembled`.
4. Teach `lib/promptlab.py` `build` to make one, and add its row to `SIZES`
   and to `MEASURED` in `tests/test_prompts.py` when using a measured fixture
   budget. The three ASR surfaces use the explicit UTF-8 prompt limit and
   bounded batches instead.

## The lab and the tests

`python3 lib/promptlab.py <surface> <language> [--mode regloss] [--sizes]`
prints a prompt as a chatbot receives it and the sizes of its parts.
`tests/test_prompts.py` builds every surface in every language (and one added
by `newlang.py`) with it and runs the table `CHECKS`. A size is one row of
`SIZES`: change the measured number and its budget together, on purpose. A row
marked `PENDING("D")` or `PENDING("E")` is skipped with its reason and fails the
day it passes everywhere, so the lane that made it true takes the mark off.
