// SPDX-License-Identifier: GPL-3.0-or-later
/* The studio's EXERCISE FORM: the sheet that writes one (TO-DO §4.8).

   Lifted out of app.js, which every page of the studio used to carry whole,
   although only the pages that WRITE an exercise need this: the edit page,
   and the deck pages (decks.js opens it to add an exercise to a deck or to
   correct one).  What an exercise IS on the page -- how it is drawn, how it
   is answered -- stays in app.js, since a document being read, a deck, and
   studying and cramming all show one.

   A classic script, loaded after app.js, reading its top-level names in one
   shared global scope.  Nothing here is new: the lines are the lines that
   were in app.js, moved.
*/
/* ---------------- the exercise form ------------------------------- */

const defaultPrompts = {
  "fill-blanks": "Drag the blocks into the blanks.",
  "order-sentences": "Put the sentences in the correct order.",
  "match-translations": "Match each item with its translation.",
  "match-opposites": "Match each item with its opposite.",
  "match-definitions": "Match each word with its definition.",
  "yes-no": "Answer each question Yes or No.",
  "true-false": "Decide whether each statement is True or False.",
  "single-choice": "Choose the correct answer.",
  "construct-sentence": "Build the complete sentence.",
  "incorrect-part": "Select the segment containing the error.",
  "choose-all": "Choose every correct answer.",
  "odd-one-out": "Choose the item that does not belong.",
  "follow-up": "Answer these questions one after the other.",
};

function splitExercisePair(text) {
  for (let i = 0; i < text.length - 1; i++) {
    if (text[i] === "=" && text[i + 1] === ">" && (i === 0 || text[i - 1] !== "\\"))
      return [text.slice(0, i).trim().replaceAll("\\=>", "=>"),
              text.slice(i + 2).trim().replaceAll("\\=>", "=>")];
  }
  return [text.trim(), ""];
}

/* The text under a `key: |` field, as mdparser.parse_exercise keeps it for
   a card's blocks: Python's textwrap.dedent of the lines (a line of blanks
   is empty; the longest indentation every other line starts with goes),
   the blank lines at either end dropped.  The same text both sides, or a
   list nested by its indentation or a table would come back changed from
   the form. */
function dedentBlock(lines, keepEdges) {
  const text = lines.map(l => /^[ \t]+$/.test(l) ? "" : l);
  let margin = null;
  for (const l of text) {
    if (!l) continue;
    const indent = l.match(/^[ \t]*/)[0];
    if (margin === null) margin = indent;
    else {
      let k = 0;
      while (k < margin.length && k < indent.length && margin[k] === indent[k]) k++;
      margin = margin.slice(0, k);
    }
  }
  const out = text.map(l => margin && l.startsWith(margin) ? l.slice(margin.length) : l);
  // a field going on over the lines under it keeps the blank line that
  // parts two paragraphs, wherever it stands (Python's textwrap.dedent)
  if (!keepEdges) {
    while (out.length && !out[0].trim()) out.shift();
    while (out.length && !out[out.length - 1].trim()) out.pop();
  }
  return out.join("\n");
}

/* the four fields of a jolly card, which hold blocks of the page's markdown
   (mdparser.JOLLY_FIELDS) */
const JOLLY_KEYS = ["front-primary", "front-secondary", "back-primary", "back-secondary"];
/* which side a flashcard shows first (mdparser.FLASHCARD_DIRECTIONS) */
const CARD_DIRECTIONS = [["forward", "Front"], ["reverse", "Back"],
                         ["both-random", "Both (random)"], ["both-repeat", "Both (repeat)"]];
/* the fields of a vocab or opposites card that go on the side the card turns
   to, or on the side shown first when their `-side` says `question`
   (mdparser.CARD_EXTRAS, CARD_SIDES) */
const CARD_EXTRAS = ["context", "notes", "source"];

function parseExerciseSource(source, flat) {
  const lines = String(source || "").replaceAll("\r\n", "\n").split("\n");
  // a deck item may come with blank lines around it; the editor's slice
  // always starts on the opening line
  while (lines.length > 1 && !lines[0].trim()) lines.shift();
  const opening = (lines[0] || "").trim().match(/^:::exercise(?:\s+([a-z][a-z0-9-]*))?/i);
  // a follow-up holds exercises of its own, one fence deeper: read it as its fields and its steps
  if (!flat && opening && /^follow-up$/i.test(opening[1] || "")) return parseChainSource(source);
  const model = {subtype: opening && opening[1] ? opening[1].toLowerCase() : "",
                 fields: {}, rows: []};
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const raw = lines[i], s = raw.trim();
    if (s === ":::") break;
    if (!s || s.startsWith("<!--")) continue;
    const fm = s.match(/^([a-z][a-z0-9-]*):\s*(.*)$/i);
    if (fm && !s.startsWith("-")) {
      const key = fm[1].toLowerCase();
      // mdparser.parse_exercise: `type:` names the subtype when the
      // opening line does not
      if (key === "type" && !model.subtype) {
        model.subtype = fm[2].trim().toLowerCase();
        continue;
      }
      if (fm[2].trim() === "|") {
        const value = [];
        while (i + 1 < lines.length && lines[i + 1].trim() !== ":::"
               && (!lines[i + 1].trim() || /^[ \t]/.test(lines[i + 1])))
          value.push(lines[++i]);
        model.fields[key] = dedentBlock(value);
      } else if (JOLLY_KEYS.includes(key)) {
        // a jolly field simply goes on: the lines under it, until another
        // field or a row, are its own, written `key: |` or not (mdparser
        // parse_exercise, carry_on)
        const value = [fm[2].trim()];
        while (i + 1 < lines.length) {
          const next = lines[i + 1], t = next.trim();
          if (t === ":::" || /^-/.test(t) || (/^[a-z][a-z0-9-]*:\s/i.test(t) && !/^[ \t]/.test(next))) break;
          value.push(lines[++i]);
        }
        while (value.length > 1 && !value[value.length - 1].trim()) value.pop();
        model.fields[key] = value.length > 1
          ? [value[0]].concat(dedentBlock(value.slice(1), true).split("\n")).join("\n")
          : value[0];
      } else model.fields[key] = fm[2].trim();
      continue;
    }
    if (s.startsWith("-")) rows.push(s);
  }
  // The row reader follows the subtype, as in mdparser: a matching or
  // yes/no row is ALWAYS `left => right`, so `- [سلام]{tl} => hello` is a
  // pair whose left side happens to open with a bracket, not a mark.
  const def = EXERCISE_DEFINITIONS.find(d => d.subtype === model.subtype);
  const pairs = def ? ["matching", "boolean"].includes(def.editor) : null;
  for (const s of rows) {
    const marked = pairs ? null : s.match(/^-\s*\[([^\]]*)\]\s*(.*)$/);
    if (marked) model.rows.push({mark: marked[1].trim(), text: marked[2].trim()});
    else {
      const pair = splitExercisePair(s.replace(/^-\s*/, ""));
      model.rows.push({left: pair[0], right: pair[1]});
    }
  }
  if (model.fields.explanation && !model.fields["explanation-correct"])
    model.fields["explanation-correct"] = model.fields.explanation;
  model.cardType = (model.fields["card-type"] || "vocab").toLowerCase();
  return model;
}

function newExerciseModel(def) {
  const model = {subtype: def.subtype, cardType: def.cardType || "", fields: {}, rows: []};
  if (def.subtype !== "flashcard") model.fields.prompt = defaultPrompts[def.subtype] || "";
  if (def.editor === "fill") {
    model.parts = [{kind: "text", text: ""}, {kind: "blank", answer: ""},
                   {kind: "text", text: ""}];
    model.distractors = [];
  } else if (def.editor === "matching") {
    model.rows = [{left: "", right: ""}, {left: "", right: ""}];
    if (def.subtype === "match-translations") model.fields.direction = "target-to-translation";
    if (def.subtype === "match-definitions") model.fields.direction = "word-to-definition";
  } else if (def.editor === "boolean") {
    model.rows = [{left: "", right: def.subtype === "yes-no" ? "yes" : "true"}];
  } else if (def.editor === "choice") {
    model.rows = [{text: "", correct: true}, {text: "", correct: false}];
  } else if (def.editor === "order") {
    model.rows = [{text: ""}, {text: ""}, {text: ""}];
  } else if (def.editor === "chain") {
    model.steps = [];
  } else if (def.editor === "flashcard") {
    model.fields["card-type"] = def.cardType;
    model.fields.direction = "forward";
    if (def.cardType === "jolly") {
      for (const key of ["front-primary", "front-secondary", "back-primary", "back-secondary"])
        model.fields[key] = "";
    }
  }
  return model;
}

function definitionFor(model) {
  return EXERCISE_DEFINITIONS.find(d => d.subtype === model.subtype &&
    (model.subtype !== "flashcard" || d.cardType === model.cardType));
}

/* `[من بابک [[slot]]]{tl}` -> `[من بابک]{tl} [[slot]]`: the visual editor's
   half of texgen.spread_slots, which the renderers apply when the document
   is parsed.  A mark's content holds no brackets, so a sentence written as
   one mark with blanks in it is spread over the pieces round each blank --
   here too, or the editor would show the mark's own brackets as text to be
   typed over, and `[[[slot]]` would come apart at the wrong bracket. */
const SLOT_RE = /\[\[([^\[\]]+)\]\]/;
const SLOT_SPLIT_RE = /(\[\[[^\[\]]+\]\])/;

function spreadSlots(text) {
  const L = lang(), markers = ["tl", L.code].concat(L.code === "fa" ? ["rtl"] : []);
  const rx = new RegExp("\\[((?:[^\\[\\]]|\\[\\[[^\\[\\]]+\\]\\])+)\\]\\{\\s*(" +
                        markers.join("|") + ")\\b([^{}]*)\\}", "g");
  return String(text || "").replace(rx, (whole, content, marker, attrs) => {
    if (!SLOT_RE.test(content)) return whole;
    return content.split(SLOT_SPLIT_RE).filter(Boolean).map(piece => {
      if (new RegExp("^" + SLOT_SPLIT_RE.source + "$").test(piece)) return piece;
      const core = piece.trim();
      if (!core) return piece;
      const lead = piece.slice(0, piece.length - piece.trimStart().length);
      const trail = piece.slice(piece.trimEnd().length);
      return `${lead}[${core}]{${marker}${attrs}}${trail}`;
    }).join("");
  });
}

function prepareExerciseModel(model) {
  const def = definitionFor(model);
  if (!def) throw new Error("This exercise type is not supported by the visual editor");
  if (def.editor === "choice")
    model.rows = model.rows.map(r => ({text: r.text || "", correct: /^(x|yes|true|correct)$/i.test(r.mark || "")}));
  if (def.editor === "order")
    model.rows = model.rows.slice().sort((a, b) => (+a.mark || 0) - (+b.mark || 0)).map(r => ({text: r.text || ""}));
  if (def.editor === "fill") {
    const answers = new Map(model.rows.filter(r => r.mark).map(r => [r.mark, r.text]));
    const text = spreadSlots(model.fields.text || "");
    model.parts = text.split(SLOT_SPLIT_RE).filter(Boolean).map(part => {
      const m = part.match(new RegExp("^" + SLOT_RE.source + "$"));
      return m ? {kind: "blank", answer: answers.get(m[1]) || ""} : {kind: "text", text: part};
    });
    if (!model.parts.length) model.parts = [{kind: "text", text: ""}, {kind: "blank", answer: ""}];
    model.distractors = model.rows.filter(r => !r.mark).map(r => r.text || "");
  }
  return {model, def};
}

function sourceField(lines, key, value) {
  value = String(value || "");
  if (!value.trim()) return;
  if (value.includes("\n") || value.trim() === "|") {
    // the block as written: its first line's indentation is part of it (a
    // nested list may open it), so only the blank lines around it go
    const block = value.split("\n");
    while (!block[0].trim()) block.shift();
    while (!block[block.length - 1].trim()) block.pop();
    lines.push(key + ": |");
    block.forEach(x => lines.push(x.trim() ? "  " + x : ""));
  } else lines.push(key + ": " + value.trim());
}

/* A flashcard field that names a file: `-image` a picture, `-audio` a
   recording; null for a field of text. */
function mediaKind(key) {
  // image, image-answer, front-image, back-image -- and the recordings by
  // the same rule, audio and audio-answer among them
  return /(^|-)image(-answer)?$/.test(key) ? "image"
       : /(^|-)audio(-answer)?$/.test(key) ? "audio" : null;
}

/* The pictures every exercise but a flashcard may carry: one with the
   question, one shown once it has been answered (mdparser
   EXERCISE_IMAGE_FIELDS).  Each takes the layout a figure line takes --
   `images/map.png {width=50 align=center}` -- with a figure's defaults. */
const EXERCISE_IMAGES = [
  ["image", "Picture with the question"],
  ["image-answer", "Picture shown after the answer"],
];
const EXERCISE_IMAGE_VALUE_RE = /^(images\/[A-Za-z0-9][A-Za-z0-9._\-]*)\s*(?:\{([^{}]*)\})?$/;
const EXERCISE_IMAGE_WIDTH = 60, EXERCISE_IMAGE_ALIGN = "left";
function splitExerciseImage(value) {
  const text = String(value || "").trim();
  const m = EXERCISE_IMAGE_VALUE_RE.exec(text);
  const out = {path: m ? m[1] : text, width: EXERCISE_IMAGE_WIDTH, align: EXERCISE_IMAGE_ALIGN};
  for (const hit of ((m && m[2]) || "").matchAll(/([a-z]+)\s*=\s*(-?[\w.]+)/g)) {
    const [, key, value] = hit;
    if (key === "width") {
      const n = Math.round(+value);
      if (Number.isFinite(n)) out.width = Math.max(5, Math.min(100, n));
    } else if (key === "align" && ["left", "center", "right"].includes(value)) out.align = value;
  }
  return out;
}
function joinExerciseImage(parts) {
  const path = String(parts.path || "").trim();
  if (!path) return "";
  const n = Math.round(+parts.width), attrs = [];
  if (Number.isFinite(n) && n !== EXERCISE_IMAGE_WIDTH)
    attrs.push("width=" + Math.max(5, Math.min(100, n)));
  if (parts.align && parts.align !== EXERCISE_IMAGE_ALIGN) attrs.push("align=" + parts.align);
  return attrs.length ? `${path} {${attrs.join(" ")}}` : path;
}

/* The recordings every exercise but a flashcard may carry, the pictures'
   twins: one with the question, one played once it has been answered
   (mdparser EXERCISE_AUDIO_FIELDS).  Written exactly as a picture is, which
   is this dialect's rule for recordings everywhere -- the same width and
   side, and the clip a recording line takes:
   `audio/word.mp3 {width=40 start=1:05.2 end=1:09}`.  The times are kept as
   the author wrote them, clock or seconds; the parser reads both. */
const EXERCISE_AUDIOS = [
  ["audio", "Recording with the question"],
  ["audio-answer", "Recording played after the answer"],
];
const EXERCISE_AUDIO_VALUE_RE = /^(audio\/[A-Za-z0-9][A-Za-z0-9._\-]*)\s*(?:\{([^{}]*)\})?$/;
function splitExerciseAudio(value) {
  const text = String(value || "").trim();
  const m = EXERCISE_AUDIO_VALUE_RE.exec(text);
  const out = {path: m ? m[1] : text, width: EXERCISE_IMAGE_WIDTH,
               align: EXERCISE_IMAGE_ALIGN, start: "", end: ""};
  for (const hit of ((m && m[2]) || "").matchAll(/([a-z]+)\s*=\s*(-?[\w.:]+)/g)) {
    const [, key, value] = hit;
    if (key === "width") {
      const n = Math.round(+value);
      if (Number.isFinite(n)) out.width = Math.max(5, Math.min(100, n));
    } else if (key === "align" && ["left", "center", "right"].includes(value)) out.align = value;
    else if (key === "start" || key === "end") out[key] = value;
  }
  return out;
}
function joinExerciseAudio(parts) {
  const path = String(parts.path || "").trim();
  if (!path) return "";
  const n = Math.round(+parts.width), attrs = [];
  if (Number.isFinite(n) && n !== EXERCISE_IMAGE_WIDTH)
    attrs.push("width=" + Math.max(5, Math.min(100, n)));
  if (parts.align && parts.align !== EXERCISE_IMAGE_ALIGN) attrs.push("align=" + parts.align);
  for (const key of ["start", "end"]) {
    const v = String(parts[key] || "").trim();
    if (v) attrs.push(`${key}=${v}`);
  }
  return attrs.length ? `${path} {${attrs.join(" ")}}` : path;
}

function exerciseSource(model, def) {
  const f = model.fields, lines = [":::exercise " + model.subtype];
  sourceField(lines, "prompt", f.prompt);
  if (model.subtype !== "flashcard") sourceField(lines, "content-direction", f["content-direction"]);
  if (model.subtype === "construct-sentence") sourceField(lines, "answer-direction", f["answer-direction"]);
  const rowText = value => String(value || "").replace(/\r?\n/g, " ⏎ ").trim();
  const pairText = value => rowText(value).replace(/(^|[^\\])=>/g, "$1\\=>");
  if (def.editor === "fill") {
    let slot = 0, sentence = "";
    const answers = [];
    model.parts.forEach(part => {
      if (part.kind === "blank") {
        const name = "blank" + (++slot);
        sentence += "[[" + name + "]]";
        answers.push([name, part.answer]);
      } else sentence += part.text || "";
    });
    sourceField(lines, "text", sentence);
    answers.forEach(([name, answer]) => lines.push(`- [${name}] ${rowText(answer)}`));
    model.distractors.forEach(answer => lines.push(`- [ ] ${rowText(answer)}`));
  } else if (def.editor === "matching") {
    sourceField(lines, "direction", f.direction);
    model.rows.forEach(r => lines.push(`- ${pairText(r.left)} => ${pairText(r.right)}`));
  } else if (def.editor === "boolean") {
    model.rows.forEach(r => lines.push(`- ${pairText(r.left)} => ${r.right}`));
  } else if (def.editor === "choice") {
    model.rows.forEach(r => lines.push(`- [${r.correct ? "x" : " "}] ${rowText(r.text)}`));
  } else if (def.editor === "order") {
    model.rows.forEach((r, i) => lines.push(`- [${i + 1}] ${rowText(r.text)}`));
  } else if (def.editor === "chain") {
    // its fields are written below, and its steps after them
  } else {
    sourceField(lines, "card-type", model.cardType);
    const keys = flashcardFields(model.cardType).map(x => x[0]);
    keys.forEach(key => sourceField(lines, key, f[key]));
    for (const key of keys.filter(k => !mediaKind(k))) {
      if (!String(f[key] || "").trim()) continue;
      const base = flashDefaults(key);
      if (f[key + "-size"] && String(f[key + "-size"]) !== String(base.size))
        sourceField(lines, key + "-size", f[key + "-size"]);
      if (f[key + "-shade"] && f[key + "-shade"] !== base.shade)
        sourceField(lines, key + "-shade", f[key + "-shade"]);
      // A SIDE IS WRITTEN ONLY WHEN IT IS SET: `answer` is what a field says
      // when it says nothing; any other value, a mistaken one too, is kept as
      // written, for the parser to name
      const side = String(f[key + "-side"] || "").trim();
      if (CARD_EXTRAS.includes(key) && side && side.toLowerCase() !== "answer")
        sourceField(lines, key + "-side", side);
    }
    sourceField(lines, "direction", f.direction);
    // not in the form, but kept: a card sheet writes it, and a card opened
    // here and saved again still says it
    if (model.cardType !== "jolly") sourceField(lines, "bidirectional", f.bidirectional);
  }
  if (model.subtype !== "flashcard") {
    for (const [key] of EXERCISE_IMAGES) sourceField(lines, key, f[key]);
    for (const [key] of EXERCISE_AUDIOS) sourceField(lines, key, f[key]);
    sourceField(lines, "explanation-correct", f["explanation-correct"]);
    sourceField(lines, "explanation-incorrect", f["explanation-incorrect"]);
  }
  // a follow-up's steps come last, each one fence deeper, and the chain's own closing line after them
  if (def.editor === "chain") model.steps.forEach(step => lines.push(nestStep(step.source)));
  lines.push(":::");
  return lines.join("\n");
}

function flashcardFields(kind) {
  if (kind === "jolly") return [
    ["front-primary", "Front — primary text"], ["front-secondary", "Front — secondary text"],
    ["back-primary", "Back — primary text"], ["back-secondary", "Back — secondary text"],
  ];
  if (kind === "opposites") return [
    ["target", "Word or expression"], ["reading", "Reading"], ["transliteration", "Transliteration"],
    ["opposite", "Opposite"], ["opposite-reading", "Opposite reading"],
    ["opposite-transliteration", "Opposite transliteration"], ["notes", "Notes"],
    ["source", "Source"], ["front-image", "Front image path"], ["back-image", "Back image path"],
    ["front-audio", "Front recording path"], ["back-audio", "Back recording path"],
  ];
  return [
    ["target", "Word or expression"], ["reading", "Reading"], ["transliteration", "Transliteration"],
    ["meaning", "Meaning"], ["context", "Example or context"], ["notes", "Notes"], ["source", "Source"],
    ["front", "Custom front (replaces the word fields)"], ["back", "Custom back (replaces the meaning fields)"],
    ["front-image", "Front image path"], ["back-image", "Back image path"],
    ["front-audio", "Front recording path"], ["back-audio", "Back recording path"],
  ];
}

function flashDefaults(key) {
  const secondary = ["front-secondary", "back-secondary", "reading", "transliteration", "context", "notes",
    "source", "opposite-reading", "opposite-transliteration"].includes(key);
  return {size: secondary ? 88 : 120, shade: secondary ? "subdued" : "primary"};
}

function validateExercise(model, def) {
  const filled = value => !!String(value || "").trim();
  if (def.editor === "fill") {
    const blanks = model.parts.filter(x => x.kind === "blank");
    if (!blanks.length) throw new Error("Add at least one blank");
    if (blanks.some(x => !filled(x.answer))) throw new Error("Every blank needs its correct movable block");
    if (model.distractors.some(x => !filled(x))) throw new Error("Complete or delete every distractor");
  } else if (["matching", "boolean"].includes(def.editor)) {
    if (!model.rows.length || model.rows.some(r => !filled(r.left) || !filled(r.right)))
      throw new Error("Complete both fields in every row");
  } else if (["choice", "order"].includes(def.editor)) {
    if (!model.rows.length || model.rows.some(r => !filled(r.text))) throw new Error("Complete every item");
    if (def.editor === "choice") {
      const correct = model.rows.filter(r => r.correct).length;
      if (model.subtype === "choose-all" ? correct < 1 : correct !== 1)
        throw new Error(model.subtype === "choose-all" ? "Mark at least one correct answer" : "Mark exactly one correct answer");
    }
  } else if (def.editor === "chain") {
    if (model.steps.length < 2) throw new Error("A follow-up needs at least two steps");
    model.steps.forEach((step, k) => {
      const d = describeStep(step.source);
      if (d.error) throw new Error(`Step ${k + 1}: ${d.error}`);
    });
  } else if (model.cardType === "jolly") {
    // one field a side is a card; the secondary ones are there when wanted
    if (!filled(model.fields["front-primary"]) && !filled(model.fields["front-secondary"]))
      throw new Error("Fill in at least one field on the front");
    if (!filled(model.fields["back-primary"]) && !filled(model.fields["back-secondary"]))
      throw new Error("Fill in at least one field on the back");
  } else if (model.cardType === "opposites") {
    if (!filled(model.fields.target) || !filled(model.fields.opposite))
      throw new Error("Enter the word and its opposite");
  } else if (!filled(model.fields.target) && !filled(model.fields.front)) {
    throw new Error("Enter the word or a custom front");
  }
  if (def.editor !== "flashcard") {
    // what mdparser says of a picture path, said before the exercise is saved
    for (const [key] of EXERCISE_IMAGES) {
      const value = String(model.fields[key] || "").trim();
      if (value && !EXERCISE_IMAGE_VALUE_RE.test(value))
        throw new Error(`${key} must name a file under images/ (e.g. images/map.png)`);
    }
    // and of a recording path, the same words for the same mistake
    for (const [key] of EXERCISE_AUDIOS) {
      const value = String(model.fields[key] || "").trim();
      if (value && !(EXERCISE_AUDIO_VALUE_RE.test(value)
                     && AUDIO_PATH_RE.test(EXERCISE_AUDIO_VALUE_RE.exec(value)[1])))
        throw new Error(`${key} must name a file under audio/ (e.g. audio/word.mp3)`);
    }
  }
  if (def.editor === "flashcard") {
    // what mdparser says of a recording path, said before the card is saved
    for (const [key] of flashcardFields(model.cardType).filter(([k]) => mediaKind(k) === "audio")) {
      const path = String(model.fields[key] || "").trim();
      if (path && !AUDIO_PATH_RE.test(path))
        throw new Error(`${key} must name a file under audio/ (e.g. audio/word.mp3)`);
    }
    for (const [key] of flashcardFields(model.cardType).filter(([k]) => !mediaKind(k))) {
      if (!filled(model.fields[key])) continue;
      const size = +(model.fields[key + "-size"] || flashDefaults(key).size);
      const shade = model.fields[key + "-shade"] || flashDefaults(key).shade;
      if (!Number.isFinite(size) || size < 50 || size > 250)
        throw new Error("Text sizes must be between 50% and 250%");
      if (!new Set(["primary", "subdued", "muted", "accent"]).has(shade) && !/^#[0-9a-f]{6}$/i.test(shade))
        throw new Error("Choose one of the available color treatments");
      // what mdparser says of a side: the box under Text appearance writes only these
      const side = String(model.fields[key + "-side"] || "").trim().toLowerCase();
      if (CARD_EXTRAS.includes(key) && side && side !== "answer" && side !== "question")
        throw new Error(`The side of the ${key} must be answer or question: tick or untick its box under Text appearance`);
    }
  }
}

/* ---------------------------------------------------------------------------
   FOLLOW-UP QUESTIONS (a0.5.4): the chain's form.

   On the page a step is an exercise written ONE FENCE DEEPER (mdparser.py):
   `::::exercise <type>` … `::::`, and inside it every fence has one more
   colon than it would have on its own (a drawing is `:::::latex` … `:::::`).
   Here a step is kept as the exercise it is on its own -- the ordinary
   `:::exercise` block, which the ordinary form reads and writes -- and is
   nested only when the chain is written (nestStep) and un-nested when one is
   read (splitChain).  Nothing about a type is written twice.
   ------------------------------------------------------------------------- */
const STEP_OPEN_RE = /^::::exercise(?:\s+([a-z][a-z0-9-]*))?\s*$/i;
const FENCE_LINE_RE = /^(\s*)(:{3,})(?=\s*$|[A-Za-z])/;
const DEEP_FENCE_RE = /^(\s*)(:{4,})(?=\s*$|[A-Za-z])/;

/* a step as the chain holds it: one colon more on every fence line */
function nestStep(source) {
  return String(source || "").replaceAll("\r\n", "\n").split("\n")
    .map(l => l.replace(FENCE_LINE_RE, (m, ws, colons) => ws + colons + ":")).join("\n");
}

/* A chain's block -> {head, steps}: the lines that are the chain's own (its opening line, its fields, its closing
   `:::`) and each step as the exercise it is on its own.  A step never closed ends where the chain does, and is
   closed here: saving puts the missing line right. */
function splitChain(source) {
  const lines = String(source || "").replaceAll("\r\n", "\n").split("\n");
  while (lines.length > 1 && !lines[0].trim()) lines.shift();
  const head = [lines[0]], steps = [];
  let i = 1;
  while (i < lines.length) {
    const s = lines[i].trim();
    if (s === ":::") { head.push(lines[i]); break; }
    if (!STEP_OPEN_RE.test(s)) { head.push(lines[i++]); continue; }
    let end = i + 1, drawing = false, closed = false;
    for (; end < lines.length; end++) {
      const t = lines[end].trim();
      if (drawing) { drawing = t !== ":::::"; continue; }
      if (/^:::::latex\b/i.test(t)) { drawing = true; continue; }
      if (t === "::::") { closed = true; break; }
      if (t === ":::") break;                 // the chain's own closing: this step was never closed
    }
    const body = lines.slice(i, closed ? end + 1 : end)
      .map(l => l.replace(DEEP_FENCE_RE, (m, ws, colons) => ws + colons.slice(1)));
    if (!closed) body.push(":::");
    steps.push(body.join("\n"));
    i = closed ? end + 1 : end;
  }
  return {head, steps};
}

/* the words a person reads of a step in a list: marks and markup taken off */
function plainWords(text, max = 90) {
  const t = String(text || "")
    .replace(/\[\[[^\[\]]*\]\]/g, "…")
    .replace(/\[([^\[\]]*)\]\{[^{}]*\}/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/[*_`]+/g, "")
    .replace(/\s*⏎\s*/g, " ").replace(/\s+/g, " ").trim();
  return t.length > max ? t.slice(0, max - 1).trimEnd() + "…" : t;
}

/* What a list says of one exercise's source: its type's label, its opening words, a mark for a picture or a recording,
   and what is wrong with it (what the type's own form would refuse to save). */
function describeStep(source) {
  let prepared;
  try { prepared = prepareExerciseModel(parseExerciseSource(source)); }
  catch (e) {
    const open = String(source || "").match(/^\s*:::exercise\s+([a-z][a-z0-9-]*)/i);
    return {label: open ? open[1] : "Exercise", words: "", error: e.message, picture: false, recording: false};
  }
  const {model, def} = prepared;
  if (def.editor === "chain")
    return {label: def.label, words: plainWords(model.fields.prompt), error: "A follow-up cannot hold a follow-up", chain: true,
            picture: false, recording: false};
  let error = "";
  try { validateExercise(model, def); } catch (e) { error = e.message; }
  const f = model.fields, row = model.rows[0] || {};
  const words = [f.prompt, f.target, f.front, f["front-primary"], f["front-secondary"], f.text, row.text, row.left]
    .map(v => plainWords(v)).find(Boolean) || "";
  const some = re => Object.keys(f).some(k => re.test(k) && String(f[k] || "").trim());
  const jolly = JOLLY_KEYS.map(k => String(f[k] || "")).join("\n");
  return {label: def.label, words, error,
          picture: some(/(^|-)image(-answer)?$/) || /!\[[^\]]*\]\(images\//.test(jolly),
          recording: some(/(^|-)audio(-answer)?$/) || /\(audio\//.test(jolly)};
}

/* A chain's block -> the model the form edits: the chain's own fields, and its steps (each `{source}`) */
function parseChainSource(source) {
  const {head, steps} = splitChain(source);
  const model = parseExerciseSource(head.join("\n"), true);
  model.subtype = "follow-up";
  model.steps = steps.map(source => ({source}));
  return model;
}

/* THE STEPS OF A FOLLOW-UP, in the form: a list in which each row says its place, its type and its opening words, and
   can be dragged, moved by arrows or by a number, edited, copied, deleted (with an Undo that stays six seconds) or put
   back on the page as an exercise of its own; any of them can be ticked and moved or deleted together.  Two ways to
   put one in: a new step (the type grid, then that type's own form on top of this one) and exercises the page already
   has.  `ctx`: {inherit: the preview and uploads the steps' forms are given, schedule: redraw the chain's preview,
   fromPage: {noun, list(), removeLabel} or null, putBackWhere}. */
function buildChainSteps(area, model, ctx) {
  const steps = model.steps;
  model.putBack = model.putBack || [];
  const mk = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const described = new WeakMap();
  const about = step => {
    let d = described.get(step);
    if (!d || d.source !== step.source) {
      d = Object.assign({source: step.source}, describeStep(step.source));
      described.set(step, d);
    }
    return d;
  };

  const hint = mk("p", "ex-steps-hint");
  const tools = mk("div", "ex-steps-tools");
  const list = mk("ol", "ex-steps-list");
  list.setAttribute("aria-label", "The steps of this follow-up, in the order they are answered");
  const undo = mk("div", "ex-steps-undo");
  undo.hidden = true;
  const live = mk("span", "ex-steps-live");
  live.setAttribute("role", "status");
  const adding = mk("div", "row ex-add-row");
  // steps taken from the page: whether their originals go when the chain is saved, for all of them at once
  const originals = mk("label", "ex-steps-originals");
  originals.hidden = true;
  const originalsBox = mk("input");
  originalsBox.type = "checkbox";
  originals.append(originalsBox, mk("span", "", ctx.fromPage ? ctx.fromPage.removeLabel || "" : ""));
  originalsBox.addEventListener("change", () => {
    steps.forEach(s => { if (s.fromKey != null) s.remove = originalsBox.checked; });
    render();
  });
  area.append(hint, tools, list, undo, live, originals, adding);

  const toolButton = (x, text, title, fn) => {
    const b = mk("button", "btn small ghost", text);
    b.type = "button"; b.dataset.x = x; b.title = title;
    b.addEventListener("click", fn);
    return b;
  };
  const picked = mk("span", "ex-steps-picked");
  const bulk = [
    toolButton("up-picked", "Move up", "Move the ticked steps one place earlier", () => shift(-1)),
    toolButton("down-picked", "Move down", "Move the ticked steps one place later", () => shift(1)),
    toolButton("delete-picked", "Delete", "Delete the ticked steps", () =>
      remove(steps.map((s, k) => s.picked ? k : -1).filter(k => k >= 0))),
  ];
  tools.append(toolButton("all", "Select all", "Tick every step", () => tick(true)),
               toolButton("none", "Select none", "Untick every step", () => tick(false)), picked, ...bulk);
  const say = text => { live.textContent = ""; setTimeout(() => { live.textContent = text; }, 30); };

  function tick(on) { steps.forEach(s => { s.picked = on; }); render(); }

  function move(from, to, focus) {
    if (from === to || to < 0 || to >= steps.length) return;
    const [s] = steps.splice(from, 1);
    steps.splice(to, 0, s);
    render({i: to, x: focus});
    say(`Moved to place ${to + 1} of ${steps.length}`);
  }
  function shift(dir) {
    if (dir < 0) { for (let k = 1; k < steps.length; k++)
      if (steps[k].picked && !steps[k - 1].picked) [steps[k - 1], steps[k]] = [steps[k], steps[k - 1]]; }
    else { for (let k = steps.length - 2; k >= 0; k--)
      if (steps[k].picked && !steps[k + 1].picked) [steps[k + 1], steps[k]] = [steps[k], steps[k + 1]]; }
    render();
  }
  function duplicate(i) {
    steps.splice(i + 1, 0, {source: steps[i].source});
    render({i: i + 1, x: "edit"});
    say(`Step ${i + 1} copied: the copy is step ${i + 2}`);
  }

  let undoTimer = 0, removed = null;
  function remove(indexes, note, queued) {
    if (!indexes.length) return;
    const gone = indexes.map(at => ({step: steps[at], at}));
    for (const at of indexes.slice().sort((a, b) => b - a)) steps.splice(at, 1);
    removed = {gone, queued};
    undo.hidden = false;
    undo.replaceChildren(mk("span", "", (note || (gone.length === 1 ? `Step ${gone[0].at + 1} removed.` : `${gone.length} steps removed.`))));
    const back = mk("button", "btn small", "Undo");
    back.type = "button"; back.dataset.x = "undo";
    back.addEventListener("click", () => {
      if (!removed) return;
      for (const {step, at} of removed.gone) steps.splice(Math.min(at, steps.length), 0, step);
      if (removed.queued) removed.queued.forEach(src => {
        const k = model.putBack.lastIndexOf(src);
        if (k >= 0) model.putBack.splice(k, 1);
      });
      removed = null; clearTimeout(undoTimer); undo.hidden = true;
      render();
      say("Put back in the chain");
    });
    undo.append(" ", back);
    clearTimeout(undoTimer);
    undoTimer = setTimeout(() => { undo.hidden = true; removed = null; }, 6000);
    render();
    say(undo.firstChild.textContent);
  }
  function putBack(i) {
    const step = steps[i];
    if (step.fromKey != null) {
      // it was taken from the page and its original is still there (or was to be taken off it): leaving the chain is all
      remove([i], `Step ${i + 1} is out of the chain; the original stays ${ctx.putBackWhere}.`);
    } else {
      model.putBack.push(step.source);
      remove([i], `Step ${i + 1} goes back ${ctx.putBackWhere} as an exercise of its own, after the chain, when you save.`, [step.source]);
    }
  }

  function editStep(i) {
    const step = steps[i];
    openExerciseMarkdown(step.source, Object.assign({}, ctx.inherit, {
      mode: "edit", host: {step: i + 1, of: steps.length},
      onSave: text => { step.source = text; render({i: steps.indexOf(step), x: "edit"}); },
    }));
  }
  function newStep() {
    openExercisePicker(Object.assign({}, ctx.inherit, {
      host: {step: steps.length + 1, of: steps.length + 1},
      onSave: text => { steps.push({source: text}); render({i: steps.length - 1, x: "edit"}); say(`Step ${steps.length} added`); },
    }));
  }
  function fromPage() {
    const from = ctx.fromPage;
    openStepsFromPage({
      noun: from.noun, items: from.list(), removeLabel: from.removeLabel,
      taken: steps.map(s => s.fromKey).filter(k => k != null),
      onAdd: (chosen, drop) => {
        chosen.forEach(c => steps.push({source: c.source, fromKey: c.key, remove: drop}));
        render({i: steps.length - 1, x: "grip"});
        say(`${chosen.length} added`);
      },
    });
  }

  function row(step, i) {
    const d = about(step), n = steps.length;
    const li = mk("li", "ex-step-row" + (d.error ? " bad" : "") + (step.picked ? " picked" : ""));
    li.dataset.i = String(i);
    const pick = mk("input", "ex-step-pick");
    pick.type = "checkbox"; pick.checked = !!step.picked;
    pick.setAttribute("aria-label", `Tick step ${i + 1}`);
    pick.addEventListener("change", () => {
      step.picked = pick.checked;
      li.classList.toggle("picked", pick.checked);
      counts();
    });
    const grip = mk("button", "ex-step-grip", "⋮⋮");
    grip.type = "button";
    grip.title = "Drag to move this step; with the keyboard, ↑ and ↓ on this handle";
    grip.setAttribute("aria-label", `Move step ${i + 1}: drag it, or press the up and down arrow keys`);
    grip.addEventListener("keydown", e => {
      if (e.key === "ArrowUp") { e.preventDefault(); move(i, i - 1, "grip"); }
      else if (e.key === "ArrowDown") { e.preventDefault(); move(i, i + 1, "grip"); }
    });
    const no = mk("input", "ex-step-no");
    no.type = "number"; no.min = "1"; no.max = String(n); no.value = String(i + 1);
    no.setAttribute("aria-label", `Place of step ${i + 1}: type a number to move it there`);
    no.title = "Type a number to move this step to that place";
    no.addEventListener("change", () => {
      const to = Math.max(1, Math.min(n, Math.round(+no.value) || i + 1)) - 1;
      if (to !== i) move(i, to, "no"); else no.value = String(i + 1);
    });
    no.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); no.blur(); } });

    const main = mk("div", "ex-step-main");
    const of = mk("div", "ex-step-of");
    of.append(`Step ${i + 1} of ${n}`, mk("span", "ex-step-kind", d.label));
    if (d.picture) { const m = mk("span", "ex-step-mark", "🖼"); m.title = "Has a picture"; m.setAttribute("aria-label", "has a picture"); of.append(m); }
    if (d.recording) { const m = mk("span", "ex-step-mark", "🔊"); m.title = "Has a recording"; m.setAttribute("aria-label", "has a recording"); of.append(m); }
    const words = mk("div", "ex-step-words", d.words || "(no words)");
    words.dir = "auto"; words.lang = lang().code;
    main.append(of, words);
    if (d.error) main.append(mk("div", "ex-step-err", d.error));
    if (step.fromKey != null) {
      const where = "the " + (ctx.fromPage ? ctx.fromPage.noun : "page");
      main.append(mk("div", "ex-step-from", step.remove ? `Taken from ${where}: the original goes when you save.`
                                                         : `Copied from ${where}: the original stays.`));
    }

    const acts = mk("div", "ex-step-actions");
    const btn = (x, text, title, fn) => {
      const b = mk("button", "btn small ghost ex-step-" + x, text);
      b.type = "button"; b.dataset.x = x; b.title = title;
      b.setAttribute("aria-label", `${title}: step ${i + 1}`);
      b.addEventListener("click", fn);
      return b;
    };
    const up = btn("up", "↑", "Move earlier", () => move(i, i - 1, "up")); up.disabled = i === 0;
    const down = btn("down", "↓", "Move later", () => move(i, i + 1, "down")); down.disabled = i === n - 1;
    const more = mk("div", "ex-step-more");
    more.append(btn("duplicate", "Duplicate", "Copy this step just after itself", () => duplicate(i)));
    if (ctx.putBackWhere) more.append(btn("putback", "⤴ Put back", `Take this step out of the chain and put it back ${ctx.putBackWhere} as an exercise of its own`, () => putBack(i)));
    more.append(btn("delete", "Delete", "Delete this step", () => remove([i])));
    const toggle = btn("toggle", "⋯", "More for this step", () => {
      const open = li.classList.toggle("more-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    toggle.setAttribute("aria-expanded", "false");
    acts.append(up, down, btn("edit", "✎ Edit", "Edit this step", () => editStep(i)), toggle, more);
    li.append(pick, grip, no, main, acts);
    return li;
  }

  function counts() {
    const n = steps.filter(s => s.picked).length;
    picked.textContent = n ? `${n} ticked` : "";
    bulk.forEach(b => { b.disabled = !n; });
  }
  function render(focus) {
    list.replaceChildren(...steps.map(row));
    counts();
    hint.textContent = steps.length >= 2 ? `${steps.length} steps, answered in this order.`
      : steps.length ? "A follow-up needs at least two steps: add one more."
      : "A follow-up needs at least two steps. Add them below" + (ctx.fromPage ? ", or make the chain of exercises that are already here." : ".");
    hint.classList.toggle("short", steps.length < 2);
    const taken = steps.filter(s => s.fromKey != null);
    originals.hidden = !taken.length || !(ctx.fromPage && ctx.fromPage.removeLabel);
    originalsBox.checked = taken.length > 0 && taken.every(s => s.remove);
    if (focus) {
      const li = list.children[focus.i];
      const target = li && (li.querySelector(focus.x === "no" ? ".ex-step-no" : `.ex-step-${focus.x}`));
      const usable = target && !target.disabled ? target : li && li.querySelector(".ex-step-grip");
      if (usable) usable.focus({preventScroll: false});
    }
    ctx.schedule();
  }

  /* DRAGGING, by the handle alone: a finger on the rest of a row scrolls the form.  The row under the pointer is
     where the step goes; the form's body scrolls by itself near its edges. */
  list.addEventListener("pointerdown", e => {
    const grip = e.target.closest(".ex-step-grip");
    if (!grip || (e.button && e.button !== 0)) return;
    const li = grip.closest(".ex-step-row"), from = +li.dataset.i;
    e.preventDefault();
    grip.setPointerCapture(e.pointerId);
    li.classList.add("dragging");
    const scroller = list.closest(".ex-form-body") || document.scrollingElement;
    let to = from, y = e.clientY, raf = 0;
    const mark = () => {
      [...list.children].forEach((r, k) => {
        r.classList.toggle("drop-before", k === to && to < from);
        r.classList.toggle("drop-after", k === to && to > from);
      });
    };
    const where = () => {
      const rows = [...list.children];
      let k = rows.findIndex(r => y < r.getBoundingClientRect().bottom);
      to = k < 0 ? rows.length - 1 : k;
      mark();
    };
    const tick = () => {
      const box = scroller.getBoundingClientRect ? scroller.getBoundingClientRect() : {top: 0, bottom: innerHeight};
      if (y < box.top + 36) scroller.scrollTop -= 12;
      else if (y > box.bottom - 36) scroller.scrollTop += 12;
      where();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    const finish = commit => {
      cancelAnimationFrame(raf);
      grip.removeEventListener("pointermove", onMove);
      grip.removeEventListener("pointerup", onUp);
      grip.removeEventListener("pointercancel", onCancel);
      li.classList.remove("dragging");
      [...list.children].forEach(r => r.classList.remove("drop-before", "drop-after"));
      if (commit && to !== from) move(from, to, "grip");
    };
    const onMove = ev => { y = ev.clientY; where(); };
    const onUp = () => finish(true);
    const onCancel = () => finish(false);
    grip.addEventListener("pointermove", onMove);
    grip.addEventListener("pointerup", onUp);
    grip.addEventListener("pointercancel", onCancel);
  });

  adding.append(toolButton("new-step", "+ New step…", "Choose a type of exercise and write a new step", newStep));
  if (ctx.fromPage) adding.append(toolButton("from-page", "+ From this " + ctx.fromPage.noun + "…",
    `Make steps of exercises this ${ctx.fromPage.noun} already has`, fromPage));
  render();
}

/* THE EXERCISES A PAGE OR A DECK ALREADY HAS, to make steps of: each with its type, its opening words and a tick; a
   filter; all or none; the steps in the order the page has them or in the order they were ticked; and, where the
   original can be taken away, a box for that (ticked: "make these five exercises a chain" is one action).  An exercise
   that needs attention, one that is a follow-up, one already a step of this chain is listed greyed, with why.
   `items`: an array, or a promise of one, of {key, source, disabled?}. */
function openStepsFromPage({noun, items, removeLabel, taken = [], onAdd}) {
  const root = $("#modal-root");
  const ov = document.createElement("div"); ov.className = "modal-overlay";
  ov.dataset.lang = lang().code;
  ov.innerHTML = `<div class="modal ex-from-page" role="dialog" aria-modal="true" aria-label="Exercises from this ${noun}">
    <h3></h3><p class="ex-from-lead"></p>
    <div class="ex-from-tools"><input type="search" class="ex-from-filter" aria-label="Filter the exercises" placeholder="Filter…">
      <button type="button" class="btn small ghost" data-x="all">Select all</button>
      <button type="button" class="btn small ghost" data-x="none">Select none</button>
      <span class="ex-from-count" role="status"></span></div>
    <div class="ex-from-list" role="group"></div>
    <fieldset class="ex-from-order"><legend>Put them in the chain</legend>
      <label><input type="radio" name="ex-from-order" value="page" checked> in the order they are on the ${noun}</label>
      <label><input type="radio" name="ex-from-order" value="ticked"> in the order I ticked them</label></fieldset>
    <label class="ex-from-remove" hidden><input type="checkbox" checked> <span></span></label>
    <div class="row"><button type="button" class="btn" data-x="cancel">Cancel</button>
      <button type="button" class="btn primary" data-x="add" disabled>Add the ticked ones</button></div></div>`;
  $("h3", ov).textContent = "Steps from this " + noun;
  $(".ex-from-lead", ov).textContent =
    `Tick the exercises this ${noun} already has that are to be steps of the chain. ` +
    "An exercise that needs attention, or that is a follow-up itself, cannot be one.";
  const list = $(".ex-from-list", ov), count = $(".ex-from-count", ov), addButton = $('[data-x="add"]', ov);
  const removeBox = $(".ex-from-remove", ov);
  if (removeLabel) { removeBox.hidden = false; $("span", removeBox).textContent = removeLabel; }
  const rows = [];                    // {entry, input, li, order}
  let ticks = 0;
  const refresh = () => {
    const n = rows.filter(r => r.input.checked).length;
    count.textContent = n ? `${n} ticked` : "";
    addButton.disabled = !n;
  };
  const close = () => { if (ov.parentNode) root.removeChild(ov); };
  Promise.resolve(items).then(entries => {
    if (!ov.isConnected) return;
    if (!entries.length) { list.textContent = `This ${noun} has no exercise to make a step of.`; return; }
    entries.forEach(entry => {
      const d = describeStep(entry.source);
      const why = taken.includes(entry.key) ? "already a step of this chain"
        : entry.disabled ? entry.disabled
        : d.chain ? "a follow-up cannot be a step of another"
        : d.error ? "needs attention: " + d.error : "";
      const li = document.createElement("label"); li.className = "ex-from-item" + (why ? " off" : "");
      const input = document.createElement("input"); input.type = "checkbox"; input.disabled = !!why;
      input.setAttribute("aria-label", `${d.label}: ${d.words || "(no words)"}`);
      const kind = document.createElement("span"); kind.className = "ex-from-kind"; kind.textContent = d.label;
      const words = document.createElement("span"); words.className = "ex-from-words"; words.dir = "auto";
      words.lang = lang().code; words.textContent = d.words || "(no words)";
      li.append(input, kind, words);
      if (why) { const note = document.createElement("small"); note.className = "ex-from-note"; note.textContent = why; li.append(note); }
      input.addEventListener("change", () => { row.order = input.checked ? ++ticks : 0; refresh(); });
      const row = {entry, input, li, order: 0, text: (d.label + " " + d.words).toLowerCase()};
      rows.push(row);
      list.append(li);
    });
    refresh();
  }).catch(e => { list.textContent = "Could not read the exercises: " + e.message; });
  $(".ex-from-filter", ov).addEventListener("input", e => {
    const q = e.target.value.trim().toLowerCase();
    rows.forEach(r => { r.li.hidden = !!q && !r.text.includes(q); });
  });
  const tickAll = on => rows.forEach(r => {
    if (r.input.disabled || r.li.hidden || r.input.checked === on) return;
    r.input.checked = on;
    r.order = on ? ++ticks : 0;
  });
  $('[data-x="all"]', ov).addEventListener("click", () => { tickAll(true); refresh(); });
  $('[data-x="none"]', ov).addEventListener("click", () => { tickAll(false); refresh(); });
  addButton.addEventListener("click", () => {
    const chosen = rows.filter(r => r.input.checked);
    if (!chosen.length) return;
    if ($('input[name="ex-from-order"]:checked', ov).value === "ticked") chosen.sort((a, b) => a.order - b.order);
    close();
    onAdd(chosen.map(r => r.entry), !!removeLabel && $("input", removeBox).checked);
  });
  $$('[data-x="cancel"]', ov).forEach(b => b.addEventListener("click", close));
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  ov.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); close(); } });
  root.appendChild(ov);
  $(".ex-from-filter", ov).focus();
}

/* The top-level exercises of a text, found by their fences alone: [{key (the line it opens on), line, endLine,
   source}].  A boxed one (`> :::exercise`) is not offered: the form cannot edit it either.  The text a chain's steps
   hold is the chain's own. */
function exerciseBlocksIn(text) {
  const lines = String(text || "").replaceAll("\r\n", "\n").split("\n");
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const drawn = lines[i].trim().match(/^(:{4,})latex\b/i);
    if (drawn) {                                  // a drawing of the page's own: nothing in it is an exercise
      for (i++; i < lines.length && lines[i].trim() !== drawn[1]; i++);
      continue;
    }
    if (!/^:::exercise(?:\s+[a-z][a-z0-9-]*)?\s*$/i.test(lines[i])) continue;
    let end = i + 1, fence = "";
    for (; end < lines.length; end++) {
      const u = lines[end].trim();
      if (fence) { if (u === fence) fence = ""; continue; }
      const m = u.match(/^(:{4,})latex\b/i);
      if (m) { fence = m[1]; continue; }
      if (u === ":::") break;
    }
    if (end >= lines.length) break;
    out.push({key: i, line: i, endLine: end, source: lines.slice(i, end + 1).join("\n")});
    i = end;
  }
  return out;
}

/* What the form shows as its preview when the caller brings none: the
   editor's own renderer, with the document's images and links. */
/* THE PROSE THE OPEN DOCUMENT IS WRITTEN IN.  The preview below renders
   from a front matter this file writes, and it never carried a `lang:` at
   all: the exercise was previewed in whatever a document that declares
   nothing gets, never in the prose of the document it is being written
   into, so the two hyphenated differently and a screen reader read them out
   in two different languages.  The sheet of the page carries the answer --
   the server writes it on a document page, and the editor writes it back
   after every preview -- and a page with no sheet (a deck) falls back to
   what an undeclared document gets. */
function openProseLang() {
  const sheet = document.getElementById("sheet");
  const code = (sheet && sheet.lang) || "";
  return /^[A-Za-z]{2,3}(-[A-Za-z0-9]+)*$/.test(code) ? code : "en";
}

async function defaultExercisePreview(markdown) {
  const target = String(lang().code || "fa").replace(/[^a-z0-9-]/gi, "") || "fa";
  const prose = openProseLang();
  const data = await api("/api/preview", {method: "POST",
    json: {markdown: `---\ntitle: Exercise preview\ntarget: ${target}\nlang: ${prose}\n---\n\n${markdown}`,
           doc_id: DOC_ID}});
  if (!data.ok) throw new Error(data.error);
  return {html: data.doc.html, lang: data.doc.lang, target: data.doc.target};
}

/* ---------------------------------------------------------------------------
   THE PICTOGRAM PICKER, pointed at the studio (lib/pictograms.js, a0.5.3).

   The frame is one for the Settings door, the editor and this form; what is
   handed to it here is where the studio answers (its own two routes, which
   read what lib/getarasaac.py keeps), the language the document is in, and
   where the pictograms are got when none are here.  `door` is the hub's page
   and the studio run on its own has no such page, so it is told by the mount:
   LATEX_BASE is "" only when the studio is the whole site.  The picture
   reaches a document through the uploader the caller already has -- the
   document's images/, a deck's -- so a copy is made as for any picture and
   nothing here writes a file of its own.

   NO PAGE LINKS THE PICKER'S SCRIPT.  It is fetched here, the first time a
   Pictogram… button is pressed.  A tag in the page, async or not, is a
   request the page's `load` waits for, and a deck kept on a phone and opened
   with the computer answering nothing sat on it for thirty seconds (the page
   itself was drawn from its copy: tests/mobile_pages.mjs, b2).  What only a
   search needs is asked for when a search is wanted, and with a deadline. */
let pictogramsLoading = null;
function loadPictograms() {
  if (window.ParsehPictograms && window.ParsehPictograms.open) return Promise.resolve(window.ParsehPictograms);
  if (!pictogramsLoading) {
    pictogramsLoading = new Promise((ok, no) => {
      const tag = document.createElement("script");
      const fail = why => { clearTimeout(timer); tag.remove(); no(new Error(why)); };
      const timer = setTimeout(() => fail("The pictogram picker did not come: is the computer that runs Parseh reachable?"), 10000);
      tag.src = "/lib/pictograms.js";
      tag.onload = () => {
        clearTimeout(timer);
        if (window.ParsehPictograms && window.ParsehPictograms.open) ok(window.ParsehPictograms);
        else fail("The pictogram picker did not start.");
      };
      tag.onerror = () => fail("The pictogram picker could not be fetched: is the computer that runs Parseh reachable?");
      document.head.append(tag);
    });
    pictogramsLoading.catch(() => { pictogramsLoading = null; });        // asked for again at the next press
  }
  return pictogramsLoading;
}
// was a pictogram put in through the frame since this page loaded?  (nothing was, if the frame never came)
const pictogramsUsed = text => !!(window.ParsehPictograms && window.ParsehPictograms.used(text));
// does a text name a copy of a pictogram (images/arasaac-<number>.png)?  A pure question: it needs no script
const pictogramsNamed = text => /images\/arasaac-\d+(?:-\d+)?\.png/.test(String(text || ""));
function pictogramOptions(extra) {
  return Object.assign({
    search: LATEX_BASE + "/api/arasaac/search",
    picture: id => LATEX_BASE + "/arasaac/" + id + ".png",
    lang: lang().code,
    door: LATEX_BASE ? "/settings/arasaac/" : null,
  }, extra);
}
async function openPictograms(extra) {
  let picker;
  try { picker = await loadPictograms(); } catch (e) { toast(e.message, true); return null; }
  return picker.open(pictogramOptions(extra));
}
// what a pictogram is written as, by where it goes (docs/arasaac.md 5.5): the path alone for a card's side, the path
// with a width and a side for an exercise's picture, a small picture inside a line of text, and on a line of its own
// -- a figure -- in a jolly card's blocks
const PICTOGRAM_PICTURE = {width: 20, align: "center"};
const PICTOGRAM_FIGURE = "{width=18 align=center}";
const pictogramInline = (path, pick) => `![${pick.alt || ""}](${path})`;
const pictogramFigure = (path, pick) => `![${pick.alt || ""}](${path})${PICTOGRAM_FIGURE}`;
/* A small picture put into the line the cursor is in, a space either side where it would touch a word. */
function putPictogramInline(input, markup, at, to) {
  const value = String(input.value);
  at = at == null ? value.length : at;
  to = to == null ? at : to;
  const before = value.slice(0, at), after = value.slice(to);
  const pre = before && !/\s$/.test(before) ? " " : "";
  const post = after && !/^\s/.test(after) ? " " : "";
  input.value = before + pre + markup + post + after;
  const end = (before + pre + markup + post).length;
  input.focus();
  input.setSelectionRange(end, end);
  input.dispatchEvent(new Event("input", {bubbles: true}));
  return end;
}

/* The visual exercise form, for the editor and for the exercise decks.
   `onSave(markdown)` receives the one `:::exercise` block; it may be async,
   and when it throws the message is shown and the form stays open.
   `preview(markdown)` resolves to rendered document html (a string, or
   {html, lang, target}); the form keeps the first exercise of it.
   `title` and `saveLabel` override the headings an editor caller gets.
   `uploadImage(file)`, when given, resolves to the stored picture's path
   ("images/<name>"), and `uploadAudio(file)` to a recording's
   ("audio/<name>") -- or either to {path, url}: each picture or recording
   field of a flashcard then gets an "Upload…" button that fills it in, and
   a jolly card's fields "Image…" and "Recording…" buttons that put the
   line in at the cursor.  Without them the fields are paths.  A pictogram
   (lib/pictograms.js) is stored by the same `uploadImage`, and `pictureHome`
   names where that is, for what the frame says ("this page", "this deck").

   A FOLLOW-UP's form is this form with a Steps list in it.  `fromPage`, when the caller can offer one, is what
   "+ From this page…" lists: {noun ("page" / "deck"), list() -> the exercises it has, [{key, source}] or a promise of
   them, removeLabel (the words of the box that takes the originals away, or "" when it cannot), putBackWhere ("on the
   page" / "in the deck": where "Put back" puts a step, or "" when it cannot)}.  `onSave(markdown, extra)` is then told,
   as `extra`, which originals to take away ({remove: [keys]}) and which steps are to become exercises of their own
   ({putBack: [markdown]}).  `host` says this form is a STEP of a follow-up -- {step, of} -- and changes only what a
   step must: it opens over the chain's form instead of taking its place, its title says "Step 2 — …", its button
   says Add to the chain / Save step, and a card's "both (repeat)" is not offered. */
function openExerciseForm({model, def, mode = "add", onSave, preview, title, saveLabel,
                           uploadImage: upload, uploadAudio, directions, pictureHome = "this page",
                           host = null, fromPage = null}) {
  const adding = mode !== "edit";
  const renderPreview = preview || defaultExercisePreview;
  const root = $("#modal-root");
  if (!host) root.innerHTML = "";
  if (host && !directions) directions = ["forward", "reverse", "both-random"];
  const ov = document.createElement("div"); ov.className = "modal-overlay";
  ov.dataset.lang = lang().code;
  ov.innerHTML = `<div class="modal ex-form-modal" role="dialog" aria-modal="true">
    <div class="ex-form-head"><div><h3></h3><p></p></div><button type="button" class="btn ghost" data-x="cancel" title="Close">✕</button></div>
    <div class="ex-form-body"></div>
    <div class="row ex-form-actions">
    <button class="btn ghost" data-x="latex" title="A drawing made by LaTeX itself -- chemistry, TikZ, units -- put in the field you were last in. It belongs in a Jolly card's four fields, which take blocks.">LaTeX drawing…</button>
    <button class="btn ghost" data-x="math" title="Write a formula with its picture beside it and put it in the field you were last in — the same sheet the document editor uses. In an exercise a formula may sit in the prompt, in the sentence, in an answer or on a card; it may not sit inside a blank.">∑ Maths…</button>
    <button class="btn ghost" data-x="pictogram" hidden title="Look for an ARASAAC pictogram by a word and put it in the field you were last in: a small picture inside the text, or its path in a picture field. It is copied into this page's own pictures.">Pictogram…</button>
    <span class="ex-form-spacer"></span>
    <button class="btn" data-x="cancel">Cancel</button>
    <button class="btn primary" data-x="save"></button></div></div>`;
  $("h3", ov).textContent = title || (host ? `Step ${host.step} — ${def.label}` : adding ? "Add " + def.label : "Edit " + def.label);
  $(".ex-form-head p", ov).textContent = def.description;
  $('[data-x="save"]', ov).textContent = saveLabel
    || (host ? (adding ? "Add to the chain" : "Save step") : adding ? "Insert exercise" : "Save exercise");
  if (host) ov.classList.add("ex-step-frame");
  const body = $(".ex-form-body", ov);
  let scheduleExercisePreview = () => {};
  let stopPlayer = () => {};

  const section = title => {
    const s = document.createElement("section"); s.className = "ex-form-section";
    const h = document.createElement("h4"); h.textContent = title; s.appendChild(h); body.appendChild(s); return s;
  };
  const field = (box, label, value, change, options = {}) => {
    const lab = document.createElement("label"); lab.className = "ex-author-field";
    const name = document.createElement("span"); name.textContent = label; lab.appendChild(name);
    const input = document.createElement(options.single ? "input" : "textarea");
    if (options.single) input.type = options.type || "text";
    input.value = value || ""; input.spellcheck = options.spellcheck !== false;
    if (options.placeholder) input.placeholder = options.placeholder;
    input.addEventListener("input", () => {
      change(input.value);
      scheduleExercisePreview();
    });
    if (input.tagName === "TEXTAREA" || input.type === "text") {
      lab.classList.add("ex-dir-field");
      lab.appendChild(exerciseTextDirectionButton(input));
    }
    lab.appendChild(input);
    if (options.help) { const help = document.createElement("small"); help.textContent = options.help; lab.appendChild(help); }
    box.appendChild(lab); return input;
  };
  const select = (box, label, value, choices, change) => {
    const lab = document.createElement("label"); lab.className = "ex-author-field";
    const name = document.createElement("span"); name.textContent = label; lab.appendChild(name);
    const input = document.createElement("select");
    choices.forEach(([v, text]) => { const o = document.createElement("option"); o.value = v; o.textContent = text; input.appendChild(o); });
    input.value = value || choices[0][0]; input.addEventListener("change", () => {
      change(input.value);
      scheduleExercisePreview();
    });
    lab.appendChild(input); box.appendChild(lab); return input;
  };
  const miniButton = (text, title, fn) => {
    const b = document.createElement("button"); b.type = "button"; b.className = "btn small ghost";
    b.textContent = text; b.title = title; b.addEventListener("click", () => {
      fn();
      scheduleExercisePreview();
    }); return b;
  };
  const removeMoveButtons = (bar, rows, i, rerender) => {
    bar.append(miniButton("↑", "Move earlier", () => { if (i) [rows[i - 1], rows[i]] = [rows[i], rows[i - 1]]; rerender(); }),
               miniButton("↓", "Move later", () => { if (i < rows.length - 1) [rows[i + 1], rows[i]] = [rows[i], rows[i + 1]]; rerender(); }),
               miniButton("Delete", "Delete this item", () => { rows.splice(i, 1); rerender(); }));
  };

  // A field that names a file -- a card's picture or recording, an
  // exercise's own picture -- with the file picker behind its Upload…
  const uploaders = {image: upload, audio: uploadAudio};
  const MEDIA = {
    image: {accept: IMAGE_ACCEPT, placeholder: "images/example.png", what: "picture"},
    audio: {accept: AUDIO_ACCEPT, placeholder: "audio/example.mp3", what: "recording"},
  };
  const urls = {};                   // what an upload said a path is served at
  // a picture field's way of taking a pictogram: the Pictogram… beside its Upload…, and the one in the action bar
  // when the hand was last in it (path, then the pick, which says the word)
  const pictureTakers = new WeakMap();
  const lineTakers = new WeakMap();    // and a jolly card's blocks: a figure on a line of its own
  const canPictogram = () => typeof uploaders.image === "function";
  // a pictogram is chosen in the frame, and stored by the form's own uploader as any picture is
  const keepPictogram = async pick => {
    const got = await uploaders.image(await pick.file());
    const path = typeof got === "string" ? got : got && got.path;
    if (!path) throw new Error("the upload named no file");
    if (got && got.url) urls[path] = got.url;
    return path;
  };
  const pictogramButton = (label, title, cls, done) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "btn small ghost " + cls;
    button.textContent = label; button.title = title;
    button.addEventListener("click", () => openPictograms({
      title: "A pictogram for this picture",
      note: `A copy goes into ${pictureHome}'s pictures, and its path into the field.`,
      addLabel: "Use this pictogram",
      onPick: async pick => {
        const path = await keepPictogram(pick);
        if (previewClosed) return;
        done(path, pick);
      },
    }));
    return button;
  };
  const uploadButton = (kind, label, title, cls, done) => {
    const pick = document.createElement("input");
    pick.type = "file"; pick.accept = MEDIA[kind].accept; pick.hidden = true;
    const button = document.createElement("button");
    button.type = "button"; button.className = "btn small ghost " + cls;
    button.textContent = label; button.title = title;
    button.addEventListener("click", () => pick.click());
    pick.addEventListener("change", async () => {
      const file = pick.files && pick.files[0];
      if (!file || button.disabled) return;
      button.disabled = true; button.textContent = "Uploading…";
      try {
        const got = await uploaders[kind](file);
        const path = typeof got === "string" ? got : got && got.path;
        if (!path) throw new Error("the upload named no file");
        if (got && got.url) urls[path] = got.url;
        if (previewClosed) return;
        done(path);
      } catch (e) {
        toast(`Could not upload the ${MEDIA[kind].what}: ` + e.message, true);
      } finally {
        button.disabled = false; button.textContent = label; pick.value = "";
      }
    });
    return [button, pick];
  };
  // a path field with its Upload… beside it, when the caller can store one
  const mediaField = (box, key, label, kind, help, part) => {
    const change = part ? part.change : (v => model.fields[key] = v);
    const input = field(box, label, part ? part.value : model.fields[key], change,
      {single: true, spellcheck: false, placeholder: MEDIA[kind].placeholder, help});
    if (typeof uploaders[kind] !== "function") return input;
    const row = document.createElement("div"); row.className = "ex-upload-row";
    input.dataset.media = kind;
    input.replaceWith(row); row.append(input);
    row.append(...uploadButton(kind, "Upload…", `Upload a ${MEDIA[kind].what} for this exercise`,
      "ex-upload", path => {
        input.value = path;
        if (part) part.uploaded(path); else model.fields[key] = path;
        scheduleExercisePreview();
      }));
    if (kind === "image" && canPictogram()) {
      const taken = (path, pick) => {
        input.value = path;
        if (part && part.pictogram) part.pictogram(path, pick);
        else if (part) part.uploaded(path);
        else model.fields[key] = path;
        scheduleExercisePreview();
      };
      pictureTakers.set(input, taken);
      row.append(pictogramButton("Pictogram…", "Look for an ARASAAC pictogram and use it as this picture", "ex-pictogram", taken));
    }
    return input;
  };

  if (model.subtype !== "flashcard") {
    const common = section("Instructions");
    field(common, "Prompt shown to the learner", model.fields.prompt,
          v => model.fields.prompt = v, {placeholder: defaultPrompts[model.subtype]});
    select(common, "Writing direction of the activity", model.fields["content-direction"] || "",
      [["", "Automatic"], ["target", `Use ${lang().name} direction`], ["rtl", "Right to left"], ["ltr", "Left to right"]],
      v => model.fields["content-direction"] = v);
  }

  if (def.editor === "fill") {
    const area = section("Sentence and blanks");
    const list = document.createElement("div"); list.className = "ex-form-list"; area.appendChild(list);
    const buttons = document.createElement("div"); buttons.className = "row ex-add-row"; area.appendChild(buttons);
    const render = () => {
      list.innerHTML = "";
      model.parts.forEach((part, i) => {
        const row = document.createElement("div"); row.className = "ex-form-row";
        const bar = document.createElement("div"); bar.className = "ex-row-head";
        const title = document.createElement("strong"); title.textContent = part.kind === "blank" ? `Blank ${model.parts.slice(0, i + 1).filter(x => x.kind === "blank").length}` : "Sentence text";
        bar.appendChild(title); removeMoveButtons(bar, model.parts, i, render); row.appendChild(bar);
        field(row, part.kind === "blank" ? "Correct movable word or chunk" : "Text that stays visible",
              part.kind === "blank" ? part.answer : part.text,
              v => part.kind === "blank" ? part.answer = v : part.text = v,
              {placeholder: part.kind === "blank" ? "Correct answer" : "Include spaces and punctuation exactly as they should appear"});
        list.appendChild(row);
      });
    };
    buttons.append(miniButton("+ Add sentence text", "Add visible sentence text", () => { model.parts.push({kind: "text", text: ""}); render(); }),
                   miniButton("+ Add blank", "Add a blank with its correct block", () => { model.parts.push({kind: "blank", answer: ""}); render(); }));
    render();
    const dist = section("Extra movable blocks (optional distractors)");
    const dlist = document.createElement("div"); dlist.className = "ex-form-list"; dist.appendChild(dlist);
    const renderDist = () => {
      dlist.innerHTML = "";
      model.distractors.forEach((value, i) => {
        const row = document.createElement("div"); row.className = "ex-form-row compact";
        field(row, `Distractor ${i + 1}`, value, v => model.distractors[i] = v);
        row.appendChild(miniButton("Delete", "Delete this distractor", () => { model.distractors.splice(i, 1); renderDist(); }));
        dlist.appendChild(row);
      });
    };
    const add = miniButton("+ Add distractor", "Add an incorrect movable block", () => { model.distractors.push(""); renderDist(); });
    dist.appendChild(add); renderDist();
  } else if (def.editor === "order") {
    const area = section(model.subtype === "construct-sentence" ? "Words or chunks in the correct order" : "Sentences in the correct order");
    if (model.subtype === "construct-sentence")
      select(area, "Direction of the answer (including wrapped lines)", model.fields["answer-direction"] || "",
        [["", `Automatic (${lang().dir === "rtl" ? "right to left" : "left to right"})`],
         ["rtl", "Right to left"], ["ltr", "Left to right"]],
        v => model.fields["answer-direction"] = v);
    const list = document.createElement("div"); list.className = "ex-form-list"; area.appendChild(list);
    const render = () => {
      list.innerHTML = "";
      model.rows.forEach((item, i) => {
        const row = document.createElement("div"); row.className = "ex-form-row";
        const bar = document.createElement("div"); bar.className = "ex-row-head";
        const title = document.createElement("strong"); title.textContent = `Correct position ${i + 1}`; bar.appendChild(title);
        removeMoveButtons(bar, model.rows, i, render); row.appendChild(bar);
        field(row, model.subtype === "construct-sentence" ? "Word or chunk" : "Sentence", item.text, v => item.text = v);
        list.appendChild(row);
      });
    };
    area.appendChild(miniButton(model.subtype === "construct-sentence" ? "+ Add word or chunk" : "+ Add sentence", "Add another item", () => { model.rows.push({text: ""}); render(); }));
    if (model.subtype === "construct-sentence")
      area.appendChild(miniButton("Reverse order", "Reverse the correct order of all words or chunks", () => { model.rows.reverse(); render(); }));
    render();
  } else if (def.editor === "matching") {
    const area = section("Pairs");
    if (model.subtype === "match-translations")
      select(area, "What the learner sees on the left", model.fields.direction || "target-to-translation",
        [["target-to-translation", "Word or sentence"], ["translation-to-target", "Translation"]], v => model.fields.direction = v);
    if (model.subtype === "match-definitions")
      select(area, "What the learner sees on the left", model.fields.direction || "word-to-definition",
        [["word-to-definition", "Word"], ["definition-to-word", "Definition"]], v => model.fields.direction = v);
    const labels = model.subtype === "match-translations" ? ["Word, phrase, or sentence", "Translation"]
      : model.subtype === "match-opposites" ? ["Word or expression", "Its opposite"] : ["Word", "Its definition"];
    const list = document.createElement("div"); list.className = "ex-form-list"; area.appendChild(list);
    const render = () => {
      list.innerHTML = "";
      model.rows.forEach((item, i) => {
        const row = document.createElement("div"); row.className = "ex-form-row";
        const bar = document.createElement("div"); bar.className = "ex-row-head";
        const title = document.createElement("strong"); title.textContent = `Pair ${i + 1}`; bar.appendChild(title);
        removeMoveButtons(bar, model.rows, i, render); row.appendChild(bar);
        const cols = document.createElement("div"); cols.className = "ex-field-cols"; row.appendChild(cols);
        field(cols, labels[0], item.left, v => item.left = v); field(cols, labels[1], item.right, v => item.right = v);
        list.appendChild(row);
      });
    };
    area.appendChild(miniButton("+ Add pair", "Add another matching pair", () => { model.rows.push({left: "", right: ""}); render(); }));
    render();
  } else if (def.editor === "boolean") {
    const area = section(model.subtype === "yes-no" ? "Questions and answers" : "Statements and answers");
    const list = document.createElement("div"); list.className = "ex-form-list"; area.appendChild(list);
    const answers = model.subtype === "yes-no" ? [["yes", "Yes"], ["no", "No"]] : [["true", "True"], ["false", "False"]];
    const render = () => {
      list.innerHTML = "";
      model.rows.forEach((item, i) => {
        const row = document.createElement("div"); row.className = "ex-form-row";
        const bar = document.createElement("div"); bar.className = "ex-row-head";
        const title = document.createElement("strong"); title.textContent = `${model.subtype === "yes-no" ? "Question" : "Statement"} ${i + 1}`; bar.appendChild(title);
        removeMoveButtons(bar, model.rows, i, render); row.appendChild(bar);
        field(row, model.subtype === "yes-no" ? "Question" : "Statement", item.left, v => item.left = v);
        select(row, "Correct answer", item.right, answers, v => item.right = v); list.appendChild(row);
      });
    };
    area.appendChild(miniButton(model.subtype === "yes-no" ? "+ Add question" : "+ Add statement", "Add another item", () => { model.rows.push({left: "", right: answers[0][0]}); render(); }));
    render();
  } else if (def.editor === "choice") {
    const area = section(model.subtype === "incorrect-part" ? "Sentence segments" : "Answer choices");
    const list = document.createElement("div"); list.className = "ex-form-list"; area.appendChild(list);
    const multiple = model.subtype === "choose-all";
    const render = () => {
      list.innerHTML = "";
      model.rows.forEach((item, i) => {
        const row = document.createElement("div"); row.className = "ex-form-row";
        const bar = document.createElement("div"); bar.className = "ex-row-head";
        const check = document.createElement("label"); check.className = "ex-correct-toggle";
        const input = document.createElement("input"); input.type = multiple ? "checkbox" : "radio"; input.name = "exercise-correct";
        input.checked = !!item.correct; input.addEventListener("change", () => {
          if (!multiple) model.rows.forEach(x => x.correct = false);
          item.correct = input.checked; render(); scheduleExercisePreview();
        });
        check.append(input, document.createTextNode(model.subtype === "incorrect-part" ? " This is the incorrect segment" : " Correct answer"));
        bar.appendChild(check); removeMoveButtons(bar, model.rows, i, render); row.appendChild(bar);
        field(row, model.subtype === "incorrect-part" ? `Sentence segment ${i + 1}` : `Choice ${i + 1}`,
              item.text, v => item.text = v); list.appendChild(row);
      });
    };
    area.appendChild(miniButton(model.subtype === "incorrect-part" ? "+ Add segment" : "+ Add choice", "Add another option", () => { model.rows.push({text: "", correct: false}); render(); }));
    render();
  } else if (def.editor === "chain") {
    buildChainSteps(section("Steps"), model, {
      schedule: () => scheduleExercisePreview(),
      inherit: {preview, uploadImage: upload, uploadAudio, pictureHome},
      fromPage, putBackWhere: fromPage ? fromPage.putBackWhere : "",
    });
  } else {
    const card = section("Card content");
    const textKeys = flashcardFields(model.cardType);
    const jolly = model.cardType === "jolly";
    // A recording field's ▶: the file its path names, from the upload that
    // stored it or from the card the preview drew (whose players have the
    // address of the deck or the document the form belongs to).
    const player = new Audio();
    player.preload = "auto";
    const audioUrl = path => {
      if (urls[path]) return urls[path];
      const drawn = $$("audio", previewStage).find(a =>
        (a.getAttribute("src") || "").replace(/#.*$/, "").endsWith("/" + path));
      return drawn ? drawn.getAttribute("src").replace(/#.*$/, "") : "";
    };
    let playing = null;
    const playButton = input => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "btn small ghost ex-audio-play";
      button.textContent = "▶"; button.title = "Play the recording";
      button.setAttribute("aria-label", "Play the recording");
      button.addEventListener("click", () => {
        if (playing === button && !player.paused) { player.pause(); return; }
        const path = input.value.trim(), url = path && audioUrl(path);
        if (!url) {
          toast(path ? `Nothing to play: the preview shows no ${path}` : "No recording named yet", true);
          return;
        }
        if (player.getAttribute("src") !== url) player.src = url;
        playing = button;
        player.currentTime = 0;
        player.play().catch(e => { if (e.name !== "AbortError") toast("Could not play the recording: " + e.message, true); });
      });
      return button;
    };
    const showPlaying = () => $$(".ex-audio-play", card).forEach(b => {
      const on = b === playing && !player.paused;
      b.textContent = on ? "❚❚" : "▶";
      b.classList.toggle("playing", on);
    });
    for (const type of ["play", "pause", "ended", "emptied"]) player.addEventListener(type, showPlaying);
    stopPlayer = () => { player.pause(); player.removeAttribute("src"); player.load(); };

    textKeys.forEach(([key, label]) => {
      const kind = mediaKind(key);
      const input = field(card, label, model.fields[key], v => model.fields[key] = v,
        {single: !!kind, spellcheck: !kind, placeholder: kind ? MEDIA[kind].placeholder : "",
         help: jolly ? "Any studio markdown: paragraphs, lists, tables, > boxes, images, recordings" : ""});
      const lab = input.parentElement;
      if (kind === "image" || kind === "audio") {
        const canUpload = typeof uploaders[kind] === "function";
        if (canUpload || kind === "audio") {
          const row = document.createElement("div"); row.className = "ex-upload-row";
          input.replaceWith(row);
          row.append(input);
          input.dataset.media = kind;
          if (canUpload) row.append(...uploadButton(kind, "Upload…",
            `Upload a ${MEDIA[kind].what} for this side of the card`, "ex-upload", path => {
              input.value = path; model.fields[key] = path;
              scheduleExercisePreview();
            }));
          if (kind === "image" && canPictogram()) {
            const taken = path => { input.value = path; model.fields[key] = path; scheduleExercisePreview(); };
            pictureTakers.set(input, taken);
            row.append(pictogramButton("Pictogram…", "Look for an ARASAAC pictogram and put it on this side of the card",
                                       "ex-pictogram", taken));
          }
          if (kind === "audio") row.append(playButton(input));
        }
        return;
      }
      if (jolly) {
        // the jolly field is markdown of any kind: written on several lines,
        // and a picture or a recording put in on a line of its own
        input.classList.add("ex-jolly-text");
        input.rows = 4;
        const put = (path, text) => {
          const at = input.selectionStart ?? input.value.length;
          const to = input.selectionEnd ?? at;
          const before = input.value.slice(0, at), after = input.value.slice(to);
          const line = text || `![](${path})`;
          const pre = before && !before.endsWith("\n") ? "\n" : "";
          const post = after && !after.startsWith("\n") ? "\n" : "";
          input.value = before + pre + line + post + after;
          const end = (before + pre + line).length;
          input.focus();
          input.setSelectionRange(end, end);
          input.dispatchEvent(new Event("input"));
        };
        const inserts = document.createElement("div"); inserts.className = "ex-insert-row";
        for (const kind2 of ["image", "audio"]) {
          if (typeof uploaders[kind2] !== "function") continue;
          inserts.append(...uploadButton(kind2, kind2 === "image" ? "Image…" : "Recording…",
            kind2 === "image" ? "Upload a picture and put it in this field, on a line of its own, at the cursor"
                              : "Upload a recording and put it in this field, on a line of its own, at the cursor",
            kind2 === "image" ? "ex-insert-image" : "ex-insert-audio", put));
        }
        if (canPictogram()) {
          // the card's blocks are the page's markdown: a pictogram goes on a line of its own, as a figure, where the
          // cursor was (a box keeps its selection while the frame has the focus); the action bar's button writes
          // through the same `put`
          lineTakers.set(input, (path, pick) => put(path, pictogramFigure(path, pick)));
          inserts.append(pictogramButton("Pictogram…",
            "Look for an ARASAAC pictogram and put it in this field, on a line of its own, at the cursor",
            "ex-insert-pictogram", (path, pick) => put(path, pictogramFigure(path, pick))));
        }
        if (inserts.children.length) input.after(inserts);
      }
      {
        const style = document.createElement("details"); style.className = "ex-field-style";
        const summary = document.createElement("summary"); summary.textContent = "Text appearance"; style.appendChild(summary);
        const cols = document.createElement("div"); cols.className = "ex-field-cols"; style.appendChild(cols);
        const defaults = flashDefaults(key);
        const sizeInput = field(cols, "Text size (%)", model.fields[key + "-size"] || defaults.size,
          v => model.fields[key + "-size"] = v, {single: true, type: "number", spellcheck: false,
          help: "50–250%; 100% is the surrounding text size"});
        sizeInput.min = "50"; sizeInput.max = "250";
        const shade = model.fields[key + "-shade"] || defaults.shade;
        const isCustom = /^#[0-9a-f]{6}$/i.test(shade);
        const shadeSelect = select(cols, "Color treatment", isCustom ? "custom" : shade,
          [["primary", "Primary text"], ["subdued", "Subdued"], ["muted", "Muted"],
           ["accent", "Accent color"], ["custom", "Custom color"]], value => {
            colorInput.parentElement.hidden = value !== "custom";
            model.fields[key + "-shade"] = value === "custom" ? colorInput.value : value;
          });
        const colorInput = field(cols, "Custom color", isCustom ? shade : "#4466aa",
          v => model.fields[key + "-shade"] = v, {single: true, type: "color", spellcheck: false});
        colorInput.parentElement.hidden = shadeSelect.value !== "custom";
        if (CARD_EXTRAS.includes(key)) {
          // not a size or a colour but where the field goes: with the answer
          // unless ticked (mdparser.card_extras)
          const check = document.createElement("label"); check.className = "ex-correct-toggle ex-side-toggle";
          const box = document.createElement("input"); box.type = "checkbox";
          box.checked = String(model.fields[key + "-side"] || "").trim().toLowerCase() === "question";
          box.addEventListener("change", () => {
            model.fields[key + "-side"] = box.checked ? "question" : "";
            scheduleExercisePreview();
          });
          check.append(box, document.createTextNode("Show on the side shown first"));
          const help = document.createElement("small");
          help.textContent = "Unticked, it goes on the other side, the one the card turns to.";
          style.append(check, help);
        }
        lab.appendChild(style);
      }
    });
    // `directions` (an array of values) narrows what the form offers: a
    // deck's card is asked from one side or drawn, never "both (repeat)"; a
    // value the card already has stays offered, so opening it changes nothing
    let now = String(model.fields.direction || "forward").trim().toLowerCase();
    if (!CARD_DIRECTIONS.some(([v]) => v === now)) now = model.fields.direction = "forward";
    const sides = CARD_DIRECTIONS.filter(([v]) => v === now || !directions || directions.includes(v));
    select(card, "Which side appears first", now, sides, v => model.fields.direction = v);
  }

  if (model.subtype !== "flashcard") {
    const pics = section("Pictures (optional)");
    // the path, and under it the width and the side the picture sits on,
    // which are written into the same field the way a figure line writes them
    const pictureField = (key, label, help) => {
      const parts = splitExerciseImage(model.fields[key]);
      const write = () => { model.fields[key] = joinExerciseImage(parts); };
      let widthInput = null, alignSelect = null;
      const input = mediaField(pics, key, label, "image", help,
        {value: parts.path,
         change: v => { parts.path = v.trim(); write(); },
         uploaded: path => { parts.path = path; write(); },
         // a pictogram is 300 pixels of line drawing: drawn at the 60 % a picture takes it is soft and huge
         // (docs/arasaac.md, 3), so it comes with the width and the side that suit it, and the boxes say so
         pictogram: path => {
           parts.path = path;
           parts.width = PICTOGRAM_PICTURE.width; parts.align = PICTOGRAM_PICTURE.align;
           if (widthInput) widthInput.value = String(parts.width);
           if (alignSelect) alignSelect.value = parts.align;
           write();
         }});
      const style = document.createElement("details");
      style.className = "ex-field-style";
      const summary = document.createElement("summary");
      summary.textContent = "Size and position"; style.appendChild(summary);
      const cols = document.createElement("div"); cols.className = "ex-field-cols";
      style.appendChild(cols);
      const width = widthInput = field(cols, "Width (% of the column)", parts.width,
        v => { parts.width = v; write(); },
        {single: true, type: "number", spellcheck: false,
         help: "5–100; 60 is what a picture takes when nothing is said"});
      width.min = "5"; width.max = "100";
      alignSelect = select(cols, "Where it sits", parts.align,
        [["left", "Left"], ["center", "Centre"], ["right", "Right"]],
        v => { parts.align = v; write(); });
      // under the path and its Upload…, not inside the row they share
      (input.closest(".ex-author-field") || input.parentElement).appendChild(style);
    };
    pictureField("image", EXERCISE_IMAGES[0][1], "Shown between the prompt and the activity");
    pictureField("image-answer", EXERCISE_IMAGES[1][1],
                 "Shown once the exercise has been answered, right or wrong, above the explanations");

    // and the recordings, which are the same two fields over again: the same
    // width and side, and the clip a recording line takes.  The preview
    // below plays them, so there is no ▶ here to duplicate it.
    const recs = section("Recordings (optional)");
    const recordingField = (key, label, help) => {
      const parts = splitExerciseAudio(model.fields[key]);
      const write = () => { model.fields[key] = joinExerciseAudio(parts); };
      const input = mediaField(recs, key, label, "audio", help,
        {value: parts.path,
         change: v => { parts.path = v.trim(); write(); },
         uploaded: path => { parts.path = path; write(); }});
      const style = document.createElement("details");
      style.className = "ex-field-style";
      const summary = document.createElement("summary");
      summary.textContent = "Size, position and clip"; style.appendChild(summary);
      const cols = document.createElement("div"); cols.className = "ex-field-cols";
      style.appendChild(cols);
      const width = field(cols, "Width (% of the column)", parts.width,
        v => { parts.width = v; write(); },
        {single: true, type: "number", spellcheck: false,
         help: "5–100; 60 is what a player takes when nothing is said"});
      width.min = "5"; width.max = "100";
      select(cols, "Where it sits", parts.align,
        [["left", "Left"], ["center", "Centre"], ["right", "Right"]],
        v => { parts.align = v; write(); });
      field(cols, "Play from", parts.start, v => { parts.start = v.trim(); write(); },
            {single: true, spellcheck: false, placeholder: "1:05.2",
             help: "Left empty, from the beginning"});
      field(cols, "Play to", parts.end, v => { parts.end = v.trim(); write(); },
            {single: true, spellcheck: false, placeholder: "1:09",
             help: "Left empty, to the end"});
      (input.closest(".ex-author-field") || input.parentElement).appendChild(style);
    };
    recordingField("audio", EXERCISE_AUDIOS[0][1], "Played between the prompt and the activity");
    recordingField("audio-answer", EXERCISE_AUDIOS[1][1],
                   "Shown once the exercise has been answered, right or wrong, above the explanations");
  }

  if (model.subtype !== "flashcard") {
    const why = section("Explanation after checking (optional)");
    field(why, "Shown when the answer is correct", model.fields["explanation-correct"],
      v => model.fields["explanation-correct"] = v,
      {help: "If the next field is empty, this becomes one neutral explanation shown after either result."});
    field(why, "Shown when the answer is incorrect", model.fields["explanation-incorrect"],
      v => model.fields["explanation-incorrect"] = v,
      {help: "Once this is filled, the two explanations are selected according to the learner's result."});
  }

  const previewSection = section("Preview");
  const previewStatus = document.createElement("small");
  previewStatus.className = "pv-status ex-form-preview-status";
  previewStatus.textContent = "Rendering preview…";
  const previewStage = document.createElement("div");
  previewStage.className = "sheet ex-form-preview";
  previewStage.dataset.lang = lang().code;
  previewSection.append(previewStatus, previewStage);
  let previewTimer = 0, previewRequest = 0, previewClosed = false;
  const renderExercisePreview = async () => {
    const request = ++previewRequest;
    previewStatus.textContent = "Rendering preview…";
    previewStatus.classList.remove("err");
    const target = String(lang().code || "fa").replace(/[^a-z0-9-]/gi, "") || "fa";
    try {
      const out = await renderPreview(exerciseSource(model, def));
      if (previewClosed || request !== previewRequest) return;
      const doc = typeof out === "string" ? {html: out} : (out || {});
      previewStage.innerHTML = doc.html || "";
      previewStage.lang = doc.lang || openProseLang();
      previewStage.dataset.lang = doc.target || target;
      const exercise = $(".exercise", previewStage);
      if (exercise) previewStage.replaceChildren(exercise);
      $$(".ex-edit,.ex-to-deck", previewStage).forEach(x => x.remove());
      bindExercises(previewStage, {preview: true});
      // a follow-up is looked over whole: every step unfolded, as Show every step does
      const all = def.editor === "chain" ? $(".ex-showall", previewStage) : null;
      if (all && all.getAttribute("aria-pressed") !== "true") all.click();
      previewStatus.textContent = "Correct answer shown as it will appear in the editor preview.";
    } catch (e) {
      if (previewClosed || request !== previewRequest) return;
      previewStage.innerHTML = "";
      previewStatus.textContent = "Preview unavailable: " + e.message;
      previewStatus.classList.add("err");
    }
  };
  scheduleExercisePreview = () => {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(renderExercisePreview, 180);
  };

  const close = () => {
    previewClosed = true;
    stopPlayer();
    clearTimeout(previewTimer);
    previewRequest++;
    if (ov.parentNode) root.removeChild(ov);
  };
  $$('[data-x="cancel"]', ov).forEach(x => x.addEventListener("click", close));
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  ov.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); close(); } });
  const saveButton = $('[data-x="save"]', ov);
  let saving = false;
  saveButton.addEventListener("click", async () => {
    if (saving) return;                  // a deck save is a round trip
    saving = true;
    saveButton.disabled = true;
    try {
      validateExercise(model, def);
      const extra = def.editor === "chain"
        ? {remove: model.steps.filter(s => s.fromKey != null && s.remove).map(s => s.fromKey),
           putBack: (model.putBack || []).slice()}
        : undefined;
      await onSave(exerciseSource(model, def), extra);
      close();
    } catch (e) { toast(e.message, true); }
    finally { saving = false; saveButton.disabled = false; }
  });
  /* A FORMULA GOES INTO THE FIELD THE HAND WAS LAST IN.  The form is a
     dozen boxes and a formula belongs in one of them; pressing the button
     takes the focus off whichever it was, so the form remembers it as the
     focus moves rather than asking afterwards.  Writing goes through the
     box's own `input` event, which is what makes the form's preview
     redraw -- the same seam the jolly field's `put` uses. */
  let lastField = null;
  ov.addEventListener("focusin", e => {
    const t = e.target;
    if (t && (t.tagName === "TEXTAREA" || (t.tagName === "INPUT" && t.type === "text")))
      lastField = t;
  });
  const latexBtn = $('[data-x="latex"]', ov);
  if (latexBtn) latexBtn.addEventListener("click", () => {
    const into = lastField || $("textarea,input", body);
    if (!into) { toast("Put the cursor in a field first.", true); return; }
    openLatexOverlay({
      offset: false,         // a card's pictures have no offset, and neither has a drawing on one
      onSave: text => {
        const at = into.selectionStart == null ? into.value.length : into.selectionStart;
        const before = into.value.slice(0, at), after = into.value.slice(into.selectionEnd == null ? at : into.selectionEnd);
        const block = (before && !before.endsWith("\n") ? "\n\n" : "") + text + (after && !after.startsWith("\n") ? "\n\n" : "");
        into.value = before + block + after;
        into.dispatchEvent(new Event("input", {bubbles: true}));
      },
    });
  });
  const mathBtn = $('[data-x="math"]', ov);
  if (mathBtn) mathBtn.addEventListener("click", () => {
    const into = lastField || $("textarea,input", body);
    if (!into) { toast("Put the cursor in a field first.", true); return; }
    if (typeof openMathOverlay !== "function") {
      toast("The maths sheet is only in the document editor.", true);
      return;
    }
    const a = into.selectionStart, b = into.selectionEnd;
    const picked = (a == null || a === b) ? "" : String(into.value).slice(a, b).trim();
    openMathOverlay({
      tex: picked,
      // a field of an exercise is a line of prose: a formula in it sits in
      // that line, and a fence would be a block inside a field that has no
      // room for one
      display: false,
      blockAllowed: false,
      title: "Mathematics in this field",
      onSave: tex => {
        const mark = "[" + tex + "]{math}";
        const at = (a == null ? String(into.value).length : a);
        const to = (b == null ? at : b);
        into.value = String(into.value).slice(0, at) + mark + String(into.value).slice(to);
        into.selectionStart = into.selectionEnd = at + mark.length;
        into.focus();
        into.dispatchEvent(new Event("input", {bubbles: true}));
      },
    });
  });

  /* A PICTOGRAM GOES INTO THE FIELD THE HAND WAS LAST IN, like a formula: a small picture inside the line of a
     text field (an option, a side of a pair, the prompt, the sentence, a card's meaning), on a line of its own in
     a jolly card's blocks, and as the path of a picture field (which has its own Pictogram… as well).  The cursor
     is taken before the frame opens, because opening it takes the focus, and moves on past each picture put in. */
  const pictoBtn = $('[data-x="pictogram"]', ov);
  if (pictoBtn && canPictogram()) {
    pictoBtn.hidden = false;
    pictoBtn.addEventListener("click", () => {
      const into = lastField || $("textarea,input", body);
      if (!into) { toast("Put the cursor in a field first.", true); return; }
      if (into.dataset.media === "audio") {
        toast("That field takes a recording: put the cursor in a text field or a picture field.", true);
        return;
      }
      const taker = pictureTakers.get(into);
      const liner = lineTakers.get(into);
      let at = into.selectionStart, to = into.selectionEnd;
      openPictograms({
        title: taker ? "A pictogram for this picture" : "A pictogram for this field",
        note: taker ? `A copy goes into ${pictureHome}'s pictures, and its path into the field.`
                    : `A copy goes into ${pictureHome}'s pictures, and a small picture into the text at the cursor.`,
        addLabel: taker ? "Use this pictogram" : "Put it in the text",
        keepLabel: taker ? "" : "Put it in, keep looking",
        onPick: async pick => {
          const path = await keepPictogram(pick);
          if (previewClosed) return;
          if (taker) return taker(path, pick);
          if (liner) return liner(path, pick);
          at = to = putPictogramInline(into, pictogramInline(path, pick), at, to);
        },
      });
    });
  }

  root.appendChild(ov);
  scheduleExercisePreview();
  $("textarea,input", body)?.focus();
}

/* THE MATHS SHEET: the notation on the left, the picture under it, and
   the choice of whether it sits in the line or on its own.

   The preview is drawn HERE and not asked of the server, which is the one
   way this differs from the exercise form's stage.  A formula is drawn by
   MathJax in this very page, so a round trip would add a tenth of a
   second to every keystroke and tell us less: MathJax does not throw on a
   mistake, it draws it and marks it, and ParsehMath.svg hands back that
   mark as a sentence -- "Missing close brace" -- which is the thing an
   author can act on and the thing a server preview would have swallowed.

   Escape closes it.  openTlOverlay, which this is otherwise modelled on,
   has no Escape handler; every other dialog in the studio does, and a box
   you cannot leave by the key everything else leaves by is a small
   cruelty. */
function openMathOverlay(opts) {
  opts = opts || {};
  const root = $("#modal-root");
  // IT OPENS OVER WHATEVER IS ALREADY THERE, and does not clear the root
  // as the other sheets do: as often as not it is opened FROM the exercise
  // form, and clearing would take that form -- and the half-written
  // exercise in it -- away with it.  Only a maths sheet left over from
  // before is removed, so pressing the button twice leaves one.
  $$(".math-overlay", root).forEach(n => n.remove());
  const was = document.activeElement;
  const ov = document.createElement("div");
  ov.className = "modal-overlay math-overlay";
  ov.innerHTML = `<div class="modal math-modal" role="dialog" aria-modal="true"
      aria-label="Mathematics">
    <h3></h3>
    <p>LaTeX notation — the same you would write on paper. Neither
    <code>$</code> nor <code>\[</code> is a marker here: the block is
    <code>[ … ]{math}</code> in a line, or a <code>:::math</code> fence on
    its own.</p>
    <textarea class="mathbox" rows="5" spellcheck="false" dir="ltr"
      placeholder="\frac{-b \pm \sqrt{b^2-4ac}}{2a}"></textarea>
    <div class="row math-opts">
      <label><input type="radio" name="mathwhere" value="inline"> in the line</label>
      <label><input type="radio" name="mathwhere" value="block"> on its own</label>
    </div>
    <div class="math-stage-wrap">
      <small class="pv-status math-status"></small>
      <div class="sheet math-stage"></div>
    </div>
    <div class="row">
      <button class="btn" data-x="cancel">Cancel</button>
      <button class="btn primary" data-x="ok"></button>
    </div></div>`;
  const box = $(".math-modal", ov);
  const ta = $(".mathbox", ov);
  const stage = $(".math-stage", ov);
  const status = $(".math-status", ov);
  const ok = $('[data-x="ok"]', ov);
  $("h3", ov).textContent = opts.title || "Mathematics";
  ok.textContent = opts.okLabel || "Insert";
  ta.value = opts.tex || "";
  const radios = $$('input[name="mathwhere"]', ov);
  radios.forEach(r => { r.checked = (r.value === (opts.display ? "block" : "inline")); });
  // a field of an exercise has no room for a block, so the choice is not
  // offered there rather than offered and then refused
  if (opts.blockAllowed === false) {
    $(".math-opts", ov).hidden = true;
    radios.forEach(r => { r.checked = (r.value === "inline"); });
  }
  const isBlock = () => $$('input[name="mathwhere"]', ov).some(r => r.checked && r.value === "block");

  let closed = false, drawing = 0;
  const draw = async () => {
    const mine = ++drawing;
    const tex = ta.value.trim();
    if (!tex) {
      stage.innerHTML = "";
      status.textContent = "Nothing to draw yet.";
      status.classList.remove("err");
      ok.disabled = true;
      return;
    }
    if (!window.ParsehMath) {
      status.textContent = "The maths renderer did not load.";
      status.classList.add("err");
      ok.disabled = false;         // the notation is still worth keeping
      return;
    }
    try {
      const out = await ParsehMath.svg(tex, isBlock());
      if (closed || mine !== drawing) return;
      if (out.error) {
        // what MathJax itself calls the mistake, in its own words
        status.textContent = out.error;
        status.classList.add("err");
        stage.innerHTML = "";
      } else {
        status.textContent = "";
        status.classList.remove("err");
        stage.innerHTML = '<div class="math ' + (isBlock() ? "mathblock" : "")
          + '" data-drawn="yes">' + out.svg + "</div>";
      }
    } catch (e) {
      if (closed || mine !== drawing) return;
      status.textContent = (e && e.message) || "That could not be drawn.";
      status.classList.add("err");
      stage.innerHTML = "";
    }
    ok.disabled = false;
  };
  const later = debounce(draw, 150);
  ta.addEventListener("input", later);
  radios.forEach(r => r.addEventListener("change", draw));

  const close = () => {
    if (closed) return;
    closed = true;
    if (ov.parentNode) root.removeChild(ov);
    // WHERE THE CARET GOES BACK TO.  Into the box it came from when it
    // came from one -- a field of the exercise form, say, where the
    // formula is being written into that field and the hand is still
    // there -- and otherwise into the document, because this is an
    // editor and a caret parked on a toolbar button types nothing.
    const box = was && (was.tagName === "TEXTAREA" || was.tagName === "INPUT");
    const back = box ? was : (opts.backTo || null);
    if (back && back.focus) { try { back.focus(); } catch (e) { /* gone */ } }
  };
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  ov.addEventListener("keydown", e => {
    if (e.key === "Escape") { e.preventDefault(); close(); }
    // the box is for a formula, so Enter is a newline in it; the sheet is
    // sent with the modifier every other box here is sent with
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); ok.click(); }
  });
  $('[data-x="cancel"]', ov).addEventListener("click", close);

  let busy = false;
  ok.addEventListener("click", async () => {
    if (busy) return;
    const tex = ta.value.trim();
    if (!tex) { close(); return; }
    busy = true; ok.disabled = true;
    try {
      await opts.onSave(tex, isBlock(), close);
    } catch (e) {
      toast((e && e.message) || "That could not be inserted.", true);
      busy = false; ok.disabled = false;
      return;
    }
    close();
  });

  root.appendChild(ov);
  box.focus ? ta.focus() : null;
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  draw();
}

/* how a formula is written into the document, in either shape */
function mathMarkup(tex, block) {
  return block ? ":::math\n" + tex + "\n:::" : "[" + tex + "]{math}";
}


/* An existing `:::exercise` block, reopened in the form -- or, with
   `opts.mode` "add", a pasted one opened as a new exercise.  A shape the
   form cannot show (an unknown type, a card type it has no fields for) is
   said in a toast rather than thrown: the caller is usually a click
   handler. */
function openExerciseMarkdown(markdown, opts = {}) {
  let prepared;
  try {
    prepared = prepareExerciseModel(parseExerciseSource(markdown));
  } catch (e) {
    toast(e.message, true);
    return false;
  }
  if (opts.host && prepared.def.editor === "chain") {
    toast("A follow-up cannot hold a follow-up: use its steps one by one.", true);
    return false;
  }
  openExerciseForm(Object.assign({}, opts,
    {model: prepared.model, def: prepared.def, mode: opts.mode === "add" ? "add" : "edit"}));
  return true;
}

/* The one `:::exercise` block of a text pasted into the picker -- a card
   sheet's "copy markdown", a block copied out of a document -- from its
   opening line to its closing `:::`; what is around it is left out.  An
   Error says why there is none to open. */
function pastedExercise(text) {
  const lines = String(text || "").replace(/\r\n?/g, "\n").split("\n");
  const starts = [];
  lines.forEach((line, i) => { if (/^\s*:::exercise(?:\s|$)/.test(line)) starts.push(i); });
  if (!starts.length)
    throw new Error("There is no :::exercise block to open: paste one whole, from its :::exercise line to its closing :::");
  if (starts.length > 1)
    throw new Error(`That is ${starts.length} exercises: paste one at a time`);
  const end = lines.findIndex((line, i) => i > starts[0] && line.trim() === ":::");
  if (end < 0) throw new Error("The exercise has no closing ::: line: paste it whole");
  return lines.slice(starts[0], end + 1).join("\n");
}

/* The type grid, then the form for a new exercise of the chosen type --
   or "Paste markdown…": an exercise copied as markdown (a book's or a
   video's card sheet gives one) pasted in and opened in the form as a new
   exercise, to look over before it goes where `onSave` puts it.  Ctrl+V on
   the grid does the same at once.  `onPaste(text)`, when given, is told
   what was pasted before the form opens (the editor brings the clips it
   names in from the clip tray, so the form's preview plays them). */
function openExercisePicker(opts = {}) {
  const root = $("#modal-root");
  if (!opts.host) root.innerHTML = "";               // a step's grid opens over the chain's form
  const ov = document.createElement("div"); ov.className = "modal-overlay";
  ov.dataset.lang = lang().code;
  // two steps in one dialog, each a set of its children (a wrapper would
  // take the grid out of the dialog's column, which is what scrolls it)
  ov.innerHTML = `<div class="modal ex-picker" role="dialog" aria-modal="true" aria-label="Add an exercise" tabindex="-1">
    <h3 data-step="types">Add an exercise</h3>
    <p data-step="types">Choose the activity the learner will see. You can edit every field in the next step.
      Paste markdown… opens an exercise copied as markdown instead.</p>
    <div class="ex-type-grid" data-step="types"></div>
    <div class="row" data-step="types"><button class="btn" data-x="paste" title="Paste one :::exercise block copied as markdown (a card sheet's “copy markdown” gives one) and open it in the form">Paste markdown…</button>
      <button class="btn" data-x="cancel">Cancel</button></div>
    <h3 data-step="paste" hidden>Paste an exercise</h3>
    <p data-step="paste" hidden>One :::exercise block, as “copy markdown” on a book's or a video's card sheet gives it.
      It opens in the form, to look over before it goes in; the recordings and pictures it names come along from the
      clip tray.</p>
    <textarea class="ex-paste" data-step="paste" hidden spellcheck="false" aria-label="The exercise's markdown"
      placeholder=":::exercise flashcard&#10;card-type: jolly&#10;front-primary: …&#10;back-primary: …&#10;:::"></textarea>
    <div class="row" data-step="paste" hidden><button class="btn" data-x="back">Back</button>
      <button class="btn" data-x="cancel">Cancel</button>
      <button class="btn primary" data-x="open">Open in the form</button></div></div>`;
  const grid = $(".ex-type-grid", ov), area = $(".ex-paste", ov);
  const pasteDirection = exerciseTextDirectionButton(area);
  pasteDirection.dataset.step = "paste";
  pasteDirection.hidden = true;
  area.before(pasteDirection);
  let step = "types";
  const toStep = name => {
    step = name;
    $$("[data-step]", ov).forEach(x => { x.hidden = x.dataset.step !== name; });
  };
  if (opts.host) {
    $("h3", ov).textContent = "Add a step";
    $("p", ov).textContent = "Choose the activity this step of the follow-up will be. You can edit every field in the next step.";
  }
  EXERCISE_DEFINITIONS.forEach(def => {
    if (opts.host && def.editor === "chain") return;      // a follow-up cannot hold a follow-up
    const b = document.createElement("button");
    b.type = "button"; b.className = "ex-type";
    const strong = document.createElement("strong"); strong.textContent = def.label;
    const small = document.createElement("small"); small.textContent = def.description;
    b.append(strong, small);
    b.addEventListener("click", () => {
      close();
      const model = newExerciseModel(def);
      openExerciseForm(Object.assign({}, opts, {model, def, mode: "add"}));
    });
    grid.appendChild(b);
  });
  const onKeyPaste = e => {
    if (!ov.isConnected) { document.removeEventListener("paste", onKeyPaste); return; }
    // Ctrl+V anywhere on the grid; in the paste step the box takes it
    if (step !== "types") return;
    const text = e.clipboardData && e.clipboardData.getData("text/plain");
    if (!text || !/:::exercise/.test(text)) return;
    e.preventDefault();
    showPaste(text);
    openPasted();
  };
  const close = () => {
    document.removeEventListener("paste", onKeyPaste);
    if (ov.parentNode) root.removeChild(ov);
  };
  const showPaste = text => {
    toStep("paste");
    if (text !== undefined) area.value = text;
    area.focus();
  };
  let opening = false;
  async function openPasted() {
    if (opening) return;
    let block;
    try { block = pastedExercise(area.value); } catch (e) { toast(e.message, true); area.focus(); return; }
    opening = true;
    try {
      if (opts.onPaste) {
        try { await opts.onPaste(block); }
        catch (e) { toast("Could not bring the clips in: " + e.message, true); }
      }
      if (!ov.isConnected) return;               // closed meanwhile
      // the form takes the dialog's place; one it cannot show leaves the text here
      if (openExerciseMarkdown(block, Object.assign({}, opts, {mode: "add"})))
        document.removeEventListener("paste", onKeyPaste);
      else area.focus();
    } finally { opening = false; }
  }
  $('[data-x="paste"]', ov).addEventListener("click", () => showPaste());
  $('[data-x="back"]', ov).addEventListener("click", () => {
    toStep("types");
    $('[data-x="paste"]', ov).focus();
  });
  $('[data-x="open"]', ov).addEventListener("click", openPasted);
  area.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); openPasted(); }
  });
  $$('[data-x="cancel"]', ov).forEach(b => b.addEventListener("click", close));
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  ov.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); close(); } });
  document.addEventListener("paste", onKeyPaste);
  root.appendChild(ov);
  $(".ex-picker", ov).focus({preventScroll: true});
}



/* ---------------------------------------------------------------------------
   THE LaTeX DRAWING SHEET (TO-DO §8.39): a block drawn by LaTeX itself, with
   a theme's packages -- chemistry, TikZ, units -- written with its drawing
   beside it, made by the computer as it is typed.  What it writes is a
   `::::latex` block: the theme's name after the fence (none for the
   default), the figure's layout in braces, the LaTeX, a line `::::`.  Four
   colons, so that it may go into a jolly card's field too.  */
const LATEX_BASE = (function () {
  const s = document.currentScript && document.currentScript.src || "";
  const m = s.match(/^(?:https?:\/\/[^/]+)?(.*)\/static\/exform\.js/);
  return m ? m[1] : "/studio";
})();

function latexMarkup(tex, theme, layout) {
  const parts = [];
  if (layout && layout.width) parts.push("width=" + layout.width);
  if (layout && layout.align && layout.align !== "center") parts.push("align=" + layout.align);
  if (layout && layout.offset) parts.push("offset=" + layout.offset);
  // the dialect has no escape inside the quotes: a typed " becomes ”, a newline a space
  const caption = layout && layout.caption ? String(layout.caption).replace(/"/g, "”").replace(/\s+/g, " ").trim() : "";
  if (caption) parts.push('caption="' + caption + '"');
  return "::::latex" + (theme ? " " + theme : "") + (parts.length ? " {" + parts.join(" ") + "}" : "")
    + "\n" + String(tex || "").replace(/\s+$/, "") + "\n::::";
}

function openLatexOverlay(opts) {
  opts = opts || {};
  const root = document.body;
  $$(".latex-overlay", root).forEach(n => n.remove());
  const ov = document.createElement("div");
  const lay = opts.layout || {};
  // A new drawing has no layout to change.  An existing one that somebody
  // deliberately sized, moved, or put at a side opens that small section so
  // its current shape is not hidden from them.
  const hasLayout = !!lay.width || (lay.align && lay.align !== "center")
    || Number(lay.offset || 0) !== 0;
  ov.className = "modal-overlay latex-overlay";
  ov.innerHTML = `<div class="modal latex-modal" role="dialog" aria-modal="true" aria-label="LaTeX drawing" tabindex="-1">
    <header class="latex-modal-head">
      <h3>LaTeX drawing</h3>
      <p>Drawn by LaTeX itself, with a theme's packages: chemistry, TikZ, units. A formula
      MathJax can draw is better written with ∑ Maths, which works everywhere.</p>
    </header>
    <div class="latex-modal-body">
      <section class="lx-preview-pane" aria-label="Preview">
        <div class="lx-preview-head"><b>Preview</b></div>
        <small class="pv-status lx-status" aria-live="polite"></small>
        <div class="sheet lx-stage" aria-label="Drawing preview"></div>
      </section>
      <section class="lx-editor-pane">
        <label class="lx-field"><span>Theme</span><select class="lx-theme"></select></label>
        <label class="lx-field lx-source-field"><span>LaTeX</span><textarea class="lx-src" rows="7" spellcheck="false" dir="ltr"
          placeholder="\\ce{2H2 + O2 -> 2H2O}"></textarea></label>
        <label class="lx-field lx-caption-field"><span>Caption <small>(optional)</small></span>
          <input type="text" class="lx-caption" maxlength="400" autocomplete="off"
          placeholder="A line under the drawing, as under a picture"></label>
        <details class="lx-layout"${hasLayout ? " open" : ""}>
          <summary>Size and position</summary>
          <p>Leave this at its natural size unless the drawing needs a particular place in the page.</p>
          <div class="lx-layout-fields">
            <label class="lx-natural-field"><input type="checkbox" class="lx-natural"> use its natural size</label>
            <label>Width of the column <span><output class="lx-wv">60</output>%</span><input type="range" class="lx-width" min="5" max="100" value="60"></label>
            <label>Where it sits <select class="lx-align"><option value="center">center</option><option value="left">left</option><option value="right">right</option></select></label>
            <label class="lx-off">Shift sideways <input type="number" class="lx-offset" min="-100" max="100" value="0"></label>
          </div>
        </details>
      </section>
    </div>
    <footer class="latex-modal-actions"><button type="button" class="btn" data-x="cancel">Cancel</button>
      <button type="button" class="btn primary" data-x="ok">${opts.okLabel || "Insert"}</button></footer></div>`;
  const q = s => $(s, ov);
  const ta = q(".lx-src"), sel = q(".lx-theme"), status = q(".lx-status"), stage = q(".lx-stage");
  ta.value = opts.tex || "";
  q(".lx-natural").checked = !lay.width;
  q(".lx-width").value = lay.width || 60;
  q(".lx-wv").textContent = lay.width || 60;
  q(".lx-align").value = lay.align || "center";
  q(".lx-offset").value = lay.offset || 0;
  q(".lx-caption").value = lay.caption || "";
  q(".lx-caption").addEventListener("input", e => {
    const cap = e.target, at = cap.selectionStart, plain = cap.value.replace(/"/g, "”");
    if (plain !== cap.value) { cap.value = plain; cap.setSelectionRange(at, at); }
  });
  if (opts.offset === false) q(".lx-off").hidden = true;
  // the Get link opens Settings in a new tab: the drawing being written is not left behind
  let missing = {}, settings = null;
  const installLink = pkg => settings && pkg
    ? ` <a href="${escAttr(settings)}?install=${encodeURIComponent(pkg)}" target="_blank" rel="noopener">Get ${escAttr(pkg.split(",").filter(Boolean).join(", "))}…</a>` : "";
  const say = (text, fix) => {
    status.innerHTML = escAttr(text) + (fix && fix.kind === "install" ? installLink(fix.package) : "");
  };
  const needs = name => {
    const ids = (missing[name] || []).map(m => m.id);
    return ids.slice(0, 3).join(", ") + (ids.length > 3 ? ` and ${ids.length - 3} more` : "");
  };
  // the block's own theme is chosen before the list arrives, so that a save before it keeps it
  sel.innerHTML = `<option value="">the default</option>` +
    (opts.theme ? `<option value="${escAttr(opts.theme)}">${escAttr(opts.theme)}</option>` : "");
  sel.value = opts.theme || "";
  fetch(LATEX_BASE + "/api/latex/themes").then(r => r.json()).then(j => {
    missing = j.missing || {};
    settings = j.settings || null;
    const chosen = sel.value;
    const lack = n => needs(n) ? ` — needs ${needs(n)}, not installed` : "";
    sel.innerHTML = `<option value="">${escAttr(`the default (${j.default})${lack(j.default)}`)}</option>` +
      j.themes.map(n => `<option value="${escAttr(n)}">${escAttr(n + lack(n))}</option>`).join("");
    if (opts.theme && !j.themes.some(n => n.toLowerCase() === opts.theme.toLowerCase()))
      sel.insertAdjacentHTML("beforeend", `<option value="${escAttr(opts.theme)}">${escAttr(opts.theme)} (not on this Parseh)</option>`);
    sel.value = (chosen && j.themes.find(n => n.toLowerCase() === chosen.toLowerCase())) || chosen;
    draw();
  }).catch(() => { status.textContent = "The themes could not be read."; });
  let asked = 0;
  const draw = async () => {
    const mine = ++asked, tex = ta.value.trim();
    if (!tex) { stage.innerHTML = ""; status.textContent = "Nothing to draw yet."; return; }
    status.textContent = "Drawing…";
    try {
      const r = await fetch(LATEX_BASE + "/api/latex/preview", {method: "POST",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify({tex, theme: sel.value})});
      const j = await r.json();
      if (mine !== asked) return;
      if (j.ok) {
        status.textContent = "";
        // scaled to fill the pane, never past 12 times the drawing's own size (a point read as a pixel)
        stage.innerHTML = `<img class="lx-preview-image" src="${escAttr(j.url)}" alt="the drawing"${j.w ? ` style="--lx-w:${+j.w}"` : ""}>`;
      } else {
        say(j.said || j.error || "It could not be drawn.", j.fix);
        // and, for a compile that took place, what the words were made from (app.js, openLatexView): the document TeX
        // was given and the whole log it wrote, each in a frame on top
        const kept = j.key ? LATEX_BASE + "/latex/" + j.key : "";
        stage.innerHTML = (j.detail ? `<pre class="lx-preview-detail">${escAttr(j.detail)}</pre>` : "") +
          (kept ? `<p class="lx-preview-views"><button type="button" class="btn" data-latex-view="tex" data-latex-url="${escAttr(kept + ".tex")}">The .tex that was compiled</button> ` +
                  `<button type="button" class="btn" data-latex-view="log" data-latex-url="${escAttr(kept + ".log")}" data-latex-marks="${escAttr((j.marks || []).join(","))}">The whole log</button></p>` : "");
      }
    } catch (e) { if (mine === asked) status.textContent = "The computer did not answer."; }
  };
  const later = debounce(draw, 700);
  ta.addEventListener("input", later);
  sel.addEventListener("change", draw);
  q(".lx-width").addEventListener("input", () => { q(".lx-wv").textContent = q(".lx-width").value; q(".lx-natural").checked = false; });
  const close = () => { ov.remove(); if (opts.backTo && opts.backTo.focus) opts.backTo.focus(); };
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  ov.addEventListener("keydown", e => {
    if (e.key === "Escape") { e.preventDefault(); close(); }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); q('[data-x="ok"]').click(); }
  });
  q('[data-x="cancel"]').addEventListener("click", close);
  q('[data-x="ok"]').addEventListener("click", () => {
    const tex = ta.value.trim();
    if (!tex) { close(); return; }
    const layout = {width: q(".lx-natural").checked ? null : +q(".lx-width").value,
                    align: q(".lx-align").value,
                    offset: opts.offset === false ? 0 : (+q(".lx-offset").value || 0),
                    caption: q(".lx-caption").value};
    opts.onSave(latexMarkup(tex, sel.value, layout));
    close();
  });
  root.appendChild(ov);
  ta.focus();
}
