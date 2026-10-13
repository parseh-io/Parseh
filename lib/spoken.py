#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The spoken pass of the dictionary lookup: a word as speech, chat and subtitles write it, read back to the
formal word the dictionary has.

    import lookup
    lookup.look_up("fa", "اونا میگن اینجوری")     # lib/lookup.py calls this module; nothing else does

THE SPECIFICATION is TODOs/NOTE-fa-colloquial-normaliser.md (the families A-I, the layers of its section 12, what
the reader is told in 13, the traps of 14) and the design TODOs/DESIGN-fa-colloquial-normaliser.md; the contract
the code is built against is tests/fixtures/fa_colloquial/ and tests/test_fa_colloquial.py.  This file holds
LAYERS 1 AND 2 of those: the writing level (character variants, tanwin, held letters, spacing and gluing,
figures, hashtags, a hamza on another carrier) and the whole-word tables (the closed sets, the word pairs, the
fixed formulas, the first parts of compound verbs, the echo words).  The language's own rules and words are
data, in lib/lang/<code>.lookup.json (`spoken`) and the tables it names, and a language with no `spoken`
section is not touched.  What is not data is said where it stands, because it is about Persian's script: the
tanwin, the alef that a written-together word drops (ازین = از + این), the number words, the Arabic-script
letters of what a colloquial page says (`_OWN`).  A second language brings its own.

WHAT IT PROMISES, and every line of it is a test:

  * IT ONLY ADDS ROUTES.  A word the dictionary knows keeps its answer, in its order.  The pass looks at
    the text's words as they are and changes nothing on the page.
  * EVERY RESULT LANDS ON SOMETHING THE DICTIONARY STANDS BEHIND.  A rule's answer counts only if it is a real
    entry (or a form of one); a table row counts only if its formal word is there (a `standalone` row, a
    colloquial word with no formal twin, carries its own gloss and is told apart as such).  So the exceptions of
    the forward sound change need no list: the backward rule simply does not land.
  * IT IS MARKED.  Every hit it makes has a `spoken` object: what kind of answer it is, the formal word it was
    read as, the reason in words, the pieces of a composed answer, and the sound.  A guess cannot be taken for
    an entry.
  * IT DOES NOT RUN WHERE IT IS NOT WANTED.  The rules run only for a word the dictionary has not found, or
    found only through a one-letter ending (a guess of the old rules); the tables are asked always, but a
    table reading stands BESIDE a word the dictionary knows only where the table says so (`show`).
"""
import collections
import os
import re
import unicodedata

import spokenpeel
import spokensound
import spokenverb

ZW = "‌"
_DIGITS = {}
for _i, _c in enumerate("۰۱۲۳۴۵۶۷۸۹"):
    _DIGITS[_c] = _i
for _i, _c in enumerate("٠١٢٣٤٥٦٧٨٩"):
    _DIGITS[_c] = _i
for _i, _c in enumerate("0123456789"):
    _DIGITS[_c] = _i
_ONES = ["صفر", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده", "یازده", "دوازده", "سیزده",
         "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"]
_TENS = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
_HUNDREDS = ["", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"]

# a reading's rank: the order in which the answers of one word stand, by what they rest on (the note's section 12:
# whole-word tables before rules, closed sets before the open sound changes, one rewrite before two)
R_ENTRY, R_TABLE, R_CLEAN, R_RULE, R_LENGTH, R_SWAP = 0, 1, 2, 3, 4, 5
FIRST, AFTER = -2.0, 20.0     # the `_tier` a spoken hit takes: before every direct one, or after (lookup._by_use keeps it)
MAX_SPOKEN = 6                # the most hits a word may hold once readings are added

Row = collections.namedtuple("Row", "spoken formal kind flags gloss note src tokens")


class Reading:
    """One reading of a word: the hits it comes to, how much it rests on (`rank`) and what it says of itself."""
    __slots__ = ("rank", "hits", "weak", "twin")

    def __init__(self, rank, hits, weak=False, twin=False):
        self.rank, self.hits, self.weak, self.twin = rank, hits, weak, twin


_RULES = {}


def rules(lk, L):
    """The spoken rules of this language, or None where it has none (every language but Persian, today)."""
    if L.code not in _RULES:
        S = lk.rules(L.code).get("spoken")
        _RULES[L.code] = Rules(lk, L, S) if S else None
    return _RULES[L.code]


def forget():
    """Drop what was read (the tests change the tables)."""
    _RULES.clear()


class Rules:
    def __init__(self, lk, L, S):
        self.L, self.S = L, S
        self.text = S.get("text") or {}
        clean = S.get("clean") or {}
        self.clean_map = clean.get("map") or {}
        self.clean_what = clean.get("what") or {}
        self.clean_drop = set(clean.get("drop") or [])
        self.noise_re = [re.compile(p) for p in S.get("noise") or []]
        self.words, self.multi, self.cv, self.policy = {}, {}, {}, {}
        for name in S.get("tables") or []:
            self._load(lk, os.path.join(lk.LANG_DIR, name))
        self.join_first = {lk._fold(w, L) for w in (S.get("join") or {}).get("first") or []}
        self._numbers = {}
        self.peeler = spokenpeel.Peeler(self) if S.get("peel") else None
        self.sounds = spokensound.Sounds(S["sound"], self.text) if S.get("sound") else None
        self.verbs = None
        if S.get("verbs"):
            self.verbs = spokenverb.Verbs(os.path.join(lk.LANG_DIR, S["verbs"]), lambda w: lk._fold(w, L), self.text)

    # ------------------------------------------------------------------------------------------ the tables
    def _load(self, lk, path):
        try:
            f = open(path, encoding="utf-8")
        except OSError:
            return
        with f:
            header = None
            for line in f:
                line = line.rstrip("\n")
                if not line.strip() or line.startswith("#"):
                    continue
                cells = line.split("\t")
                if header is None:
                    header = cells
                    continue
                cells += [""] * (len(header) - len(cells))
                r = dict(zip(header, cells))
                flags = {}
                for part in (r.get("flags") or "").split(","):
                    part = part.strip()
                    if part:
                        k, _, v = part.partition("=")
                        flags[k] = v or True
                tokens = tuple(lk._fold(t, self.L) for t in r["spoken"].split() if t)
                if not tokens or not r.get("formal"):
                    continue
                row = Row(r["spoken"], r["formal"], r.get("kind") or "word", flags, r.get("gloss") or "",
                          r.get("note") or "", r.get("src") or "", tokens)
                if row.kind == "policy":
                    self.policy.setdefault(" ".join(tokens), row)
                elif row.kind == "cv":
                    self.cv.setdefault(tokens[0], row)
                elif len(tokens) > 1:
                    self.multi.setdefault(tokens[0], []).append(row)
                else:
                    self.words.setdefault(tokens[0], []).append(row)
        for rows in self.multi.values():
            rows.sort(key=lambda r: -len(r.tokens))

    # ---------------------------------------------------------------------------------------------- small things
    def noise(self, raw):
        """Laughter, a link, an @name, an emoticon: nothing is looked up for them."""
        w = raw.strip()
        return any(p.search(w) for p in self.noise_re)

    def clean(self, w):
        """The word with characters that are not Persian's put right: what, in words, is the second answer."""
        notes, out = [], []
        for ch in w:
            if ch in self.clean_drop:
                if "invisible" not in notes:
                    notes.append("invisible")
                continue
            o = ord(ch)
            if 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
                n = unicodedata.normalize("NFKC", ch)
                if n != ch:
                    notes.append("presentation")
                    out.append(n)
                    continue
            if ch in self.clean_map:
                notes.append(ch)
                out.append(self.clean_map[ch])
                continue
            out.append(ch)
        return "".join(out), notes

    def _say(self, key, **kw):
        return (self.text.get(key) or key).format(**kw)

    # ------------------------------------------------------------------------------------ what the dictionary says
    def _hits(self, lk, c, L, formal):
        f = lk._fold(formal, L)
        return lk._hits_for(c, f) if f else []

    def _strength(self, lk, entry):
        """How much the direct answer stands on: 0 nothing, 1 a one-letter ending or a letter of the alphabet (a guess),
        2 a longer ending of a rule of the language, 3 the word is the entry or one of its forms."""
        hits = entry.get("hits") or []
        if not hits:
            return 0
        if entry.get("kind") == "affix":
            rule = entry.get("_rule") or {}
            return 1 if len(rule.get("suffix") or rule.get("prefix") or "") <= 1 else 2
        return 3 if min(h.get("_tier", 0) for h in hits) <= lk.T_FORM else 1

    def _known(self, lk, c, forms):
        forms = list(dict.fromkeys(f for f in forms if f))
        found = set()
        for k in range(0, len(forms), 400):
            part = forms[k:k + 400]
            for (f,) in c.execute("SELECT DISTINCT form FROM form WHERE form IN (%s)" % ",".join("?" * len(part)), part):
                found.add(f)
        return found

    def _piece(self, lk, c, L, token, loose=False, pos=None, glue=False):
        """One piece of a split or a phrase as (hit, formal spelling), or None: the word as the dictionary has it,
        or the table's reading of it; with `loose`, a word read through an ending of the language's will do as well;
        with `pos`, the first hit that is that part of speech (a verb form that is also a noun)."""
        token = lk._bare(token, L)
        if not token:
            return None

        def pick(hits):
            for h in hits:
                # of a given part of speech, the word must BE that entry or a form of it, not its bare stem
                if not pos or (h.get("pos") == pos and h.get("_tier", 0) <= lk.T_FORM):
                    return h
            return None
        key = lk._fold(token, L)
        entries = lk._resolve(c, token, [], L, False)
        ent = entries[0] if entries else None
        strength = self._strength(lk, ent) if ent else 0
        if ent and strength == 3 and pick(ent["hits"]):
            return pick(ent["hits"]), token
        for row in self.words.get(key, []):
            # in a word written together only the rows that say they may be a piece (the demonstratives: اون, اینا ...):
            # the open table is a list of words, and a list of words is where a split finds its inventions
            if row.kind == "standalone" or (glue and not row.flags.get("glue")):
                continue
            hit = pick(self._formal_hits(lk, c, L, row.formal))
            if hit:
                return hit, row.formal
        for vf, hits in self.verb_readings(lk, c, L, token):
            hit = pick(hits)
            if hit and vf.verb.inf == hit.get("headword") or hit and not pos:
                return hit, vf.formal
        if ent and loose and strength >= 1 and pick(ent["hits"]):
            return pick(ent["hits"]), token
        return None

    def verb_readings(self, lk, c, L, word):
        """[(VForm, hits)]: the formal verb forms a spoken word can be that the dictionary has (a form of a verb, strongly)."""
        if not self.verbs:
            return []
        key = lk._fold(word, L)
        out = []
        for vf in self.verbs.analyze(word)[:12]:
            if lk._fold(vf.formal, L) == key:
                continue                         # the word as it stands: the dictionary's own answer
            # the verb the spoken stem is of: می‌شویم is a form of شدن and of شستن, and میشورم is only the second
            hits = [h for h in self._hits(lk, c, L, vf.formal) if h.get("pos") == "verb" and h.get("_tier", 0) <= lk.T_FORM
                    and h.get("headword") == vf.verb.inf]
            if hits:
                out.append((vf, hits))
        return out

    def _formal_word(self, lk, c, L, word):
        """The hits of one formal word: an entry or a form of one, or the word with an ending of the language's off it
        (خودشان is خود and an ending, as a text writes it)."""
        hits = self._hits(lk, c, L, word)
        if hits:
            return hits
        entries = lk._resolve(c, word, [], L, False)
        ent = entries[0] if entries else None
        return ent["hits"] if ent and self._strength(lk, ent) >= 2 else []

    def _formal_hits(self, lk, c, L, formal):
        """The hits of a formal word, or of each of its words where it is two or three and no entry is the whole."""
        hits = self._hits(lk, c, L, formal)
        if hits or " " not in formal.strip():
            return hits or self._formal_word(lk, c, L, formal)
        out = []
        for part in formal.split():
            h = self._formal_word(lk, c, L, part)
            if not h:
                return []
            out.append(h[0])
        return out

    def _pseudo(self, row):
        """A colloquial word the dictionary has no entry for: the table's gloss is the whole answer."""
        pos = row.flags.get("pos")
        return {"entry": None, "headword": row.formal, "spelled": "", "translit": "", "of_form": "", "said": "",
                "ipa": "", "head_sound": "", "reading": "", "pos": pos if isinstance(pos, str) else "",
                "senses": [row.gloss] if row.gloss else [], "marks": [""] if row.gloss else [], "buried": 0, "note": ""}

    def _mark(self, hit, kind, formal, why, parts=None, pieces=None, gloss="", sound=None, readings=None, same=False, note=True):
        s = {"kind": kind, "as": formal, "why": why}
        if same:
            s["same"] = True
        if parts:
            s["parts"] = list(parts)
        if pieces:
            s["pieces"] = pieces
        if readings:
            s["readings"] = readings
        if gloss:
            s["gloss"] = gloss
        s["sound"] = sound or hit.get("translit") or hit.get("head_sound") or ""
        s["sound_kind"] = "spoken" if sound else "formal"
        hit["spoken"] = s
        # a panel that does not know `spoken` yet still prints a hit's note beside its headword: the reason, in words
        if note:
            hit["note"] = "%s; %s" % (why, hit["note"]) if hit.get("note") else why
        return hit

    def _reading(self, rank, kind, formal, why, hits, parts=None, pieces=None, gloss="", sound=None, readings=None):
        if not hits:
            return None
        seen, out = set(), []
        for h in hits:
            key = h.get("entry") if h.get("entry") is not None else h.get("headword")
            if key in seen:
                continue
            seen.add(key)
            out.append(self._mark(dict(h), kind, formal, why, parts, pieces, gloss, sound, readings))
        return Reading(rank, out)

    # -------------------------------------------------------------------------------------------- the context
    class Context:
        """What the chunk says of its own register: the page's hint, and the words nobody but speech writes."""

        def __init__(self, rules, lk, c, L, tokens, register):
            self.rules, self.lk, self.c, self.L = rules, lk, c, L
            self.raw = list(tokens)
            self.keys = [lk._fold(lk._bare(t, L), L) for t in tokens]
            self.hint = register == "spoken"
            self._certain = {}

        def is_certain(self, j):
            k = self.keys[j]
            if k not in self._certain:
                rows = self.rules.words.get(k, [])
                certain = bool(rows) and any(r.flags.get("certain") for r in rows) and not self.rules._known(self.lk, self.c, [k])
                if not certain and self.rules.verbs and not self.rules._known(self.lk, self.c, [k]):
                    # a verb form that only speech writes: the formal one it stands for is in the dictionary and it is not
                    # (a bare imperative alone, دار for بدار, is written in formal text too: it says nothing)
                    bare_imp = self.rules._say("verb_bare_imp")
                    certain = any(vf.why != self.rules._say("verb_plain") and not vf.why.startswith(bare_imp)
                                  for vf, _h in self.rules.verb_readings(self.lk, self.c, self.L, self.raw[j]))
                self._certain[k] = certain
            return self._certain[k]

        def evidence(self, i):
            return self.hint or any(self.is_certain(j) for j in range(len(self.keys)) if j != i)

    def context(self, lk, c, L, tokens, register):
        return Rules.Context(self, lk, c, L, tokens, register)

    # ------------------------------------------------------------------------------------------- one word
    def augment(self, lk, c, L, entry, ctx, i):
        """The answer for one word, with the spoken readings added where they belong (see the module's promises)."""
        raw = entry.get("word") or ""
        strength = self._strength(lk, entry)
        direct = entry.get("hits") or []
        bare = lk._bare(raw, L)
        w, cleaned = self.clean(bare)
        key = lk._fold(w, L)
        first, after = [], []

        # the dictionary's own colloquial pages: before any rule (and given up where a path of endings reads the same page
        # with the endings said: کوچیکه is the page of کوچیک and the copula)
        own = self._own(lk, c, L, direct)

        # the whole-word tables
        for rd, row in self._table(lk, c, L, key, ctx, i):
            if strength == 3:
                show = row.flags.get("show")
                if show is None or show == "never" or (show == "spoken" and not ctx.evidence(i)):
                    continue
                (first if (row.flags.get("likelier") == "spoken" and ctx.evidence(i)) else after).append(rd)
            else:
                first.append(rd)

        # the same word with its characters put right (an Arabic yeh, a ھ for ه) comes before any taking apart
        if not first and not after and strength <= 1:
            first.extend(self._clean_stage(lk, c, L, bare, w, cleaned))
        # a compound verb's first part written on its verb (پاشو is پا شو, rather than پا + ش + و): a closed list and a verb the
        # dictionary lists with it, so it comes before the endings are taken off
        if not first and not after and strength <= 2:
            first.extend(self._cv_glued(lk, c, L, bare, w, strength))

        # layers 3 to 6: a word taken apart from the outside in (lib/spokenpeel.py).  A pish or a zir alone is read whatever the
        # dictionary says of the word; a path of endings only where the answer so far stands on a guess (or a trap row asks)
        same_lines = []
        if self.peeler:
            policy = self.policy.get(key)
            marks = self.peeler.read_marks(lk, c, L, w, ctx, i)
            if marks:
                first.extend(self._readings_of(lk, c, L, marks, R_RULE))
            elif policy is not None or (strength <= 2 and not first and not after) or (strength <= 2 and own and not after):
                cands = self.peeler.read(lk, c, L, self._nomarks(L, w), ctx, i, with_formal=policy is not None,
                                         direct={h.get("entry") for h in direct})
                readings = self._readings_of(lk, c, L, cands, R_RULE)
                if policy is None:
                    # a word the old rules reached through an ending of two letters or more keeps that answer first
                    # where the spoken reading is only a table word with a formal ending on it
                    for rd in readings:
                        (after if (strength == 2 and rd.weak) else first).append(rd)
                else:
                    show = policy.flags.get("show")
                    if show == "always" or (show == "spoken" and ctx.evidence(i)):
                        direct_ids = {h.get("entry") for h in direct}
                        for rd in readings:
                            ids = {h.get("entry") for h in rd.hits}
                            if ids and ids <= direct_ids and (strength == 3 or rd.twin):
                                same_lines.append(rd)
                            elif strength <= 2 or (policy.flags.get("likelier") == "spoken" and ctx.evidence(i)):
                                first.append(rd)        # over a guess of the old rules, or where the page says it is speech
                            else:
                                after.append(rd)

        # the rules of the writing level, for a word the dictionary has not found
        if not first and not after and not same_lines and strength <= 1:
            first.extend(self._rules(lk, c, L, bare, w, cleaned, strength))

        # the same word read a second way by a trap's row: a second line on the dictionary's own hit, not another hit
        for rd in same_lines:
            sp = rd.hits[0]["spoken"]
            for h in direct:
                if h.get("entry") in {x.get("entry") for x in rd.hits}:
                    self._mark(h, sp["kind"], sp["as"], sp["why"], sp.get("parts"), sp.get("pieces"), readings=sp.get("readings"),
                               same=True, note=False)
                    break

        if own:
            read = {h.get("entry") for rd in first for h in rd.hits}
            first = [rd for rd in own if not {h.get("entry") for h in rd.hits} <= read] + first
        if not first and not after:
            self._perfect(lk, L, entry, key, ctx, i)
            self._doubled(lk, L, entry, ctx, i)
            return entry
        first.sort(key=lambda r: r.rank)
        spoken_first = [h for rd in first for h in rd.hits]
        spoken_after = [h for rd in after for h in rd.hits]
        have = {h.get("entry") for h in spoken_first if h.get("entry") is not None}
        have_head = {h["headword"] for h in spoken_first if h.get("entry") is None}
        kept = [h for h in direct if h.get("entry") not in have and h["headword"] not in have_head] if spoken_first else list(direct)
        later = [h for h in spoken_after if h.get("entry") is None or h.get("entry") not in {k.get("entry") for k in kept}]
        for h in spoken_first + spoken_after:
            self._sound_note(lk, L, w, h)
        for h in spoken_first:
            self._modal(lk, L, key, h)
        for n, h in enumerate(spoken_first):
            h["_tier"] = FIRST + n / 1000.0
        for n, h in enumerate(later):
            h["_tier"] = AFTER + n / 1000.0
        hits = (spoken_first + kept + later)[:max(lk.MAX_HITS, MAX_SPOKEN)]
        entry["hits"] = hits
        self._perfect(lk, L, entry, key, ctx, i)
        if spoken_first:
            entry["via"] = self._say("via", why=spoken_first[0]["spoken"]["why"])
            entry["kind"] = "spoken"
        return entry

    def _doubled(self, lk, L, entry, ctx, i):
        """A clitic on a verb that repeats the object the sentence already names (سارا رو دیدمش, note C7): the formal reading stands,
        and the word says the clitic is no new object.  The old affix rules answered it; nothing is rewritten."""
        rule = entry.get("_rule") or {}
        clitics = set(((self.S.get("peel") or {}).get("clitics") or {}).get("formal") or [])
        if entry.get("kind") != "affix" or rule.get("suffix") not in clitics or ctx is None or not i:
            return
        marker = {lk._fold(m, self.L) for m in (self.S.get("peel") or {}).get("object_markers") or []}
        if not any(k in marker for k in ctx.keys[max(0, i - 3):i]):
            return
        for h in entry.get("hits") or []:
            if h.get("pos") == "verb" and not h.get("spoken") and h.get("_tier", 9) <= lk.T_FORM:
                why = self._say("clitic_double")
                self._mark(h, "rule", entry.get("word") or "", why, pieces=[{"text": rule["suffix"], "role": "clitic", "note": why}])
                return

    def _modal(self, lk, L, key, hit):
        """میشه, نمیشه: the verb شدن said as a question or a request is also what may, or may not, be done."""
        sp = hit.get("spoken")
        modal = (self.S.get("modals") or {}).get(key)
        if not sp or not modal or hit.get("headword") != modal.get("verb"):
            return
        readings = sp.get("readings") or [{"as": sp["as"], "why": sp["why"]}]
        for formal in modal.get("as") or []:
            if all(r["as"] != formal for r in readings):
                readings.append({"as": formal, "why": self._say("modal", formal=formal)})
        sp["readings"] = readings

    def _sound_note(self, lk, L, word, hit):
        """The sound change that says a word was written for another, told on its hit (note B): which one, in words, and how the
        word is said (xāne -> xune).  Only for a word read as ONE other word: a path of endings has the stem's change in its reason."""
        sp = hit.get("spoken")
        if not sp or not self.sounds or sp.get("parts") or sp.get("same") or sp.get("kind") not in ("table", "entry", "rule"):
            return
        formal = sp.get("as") or ""
        if not formal or " " in formal:
            return
        rules = self.sounds.explain(word, formal, lambda s: lk._fold(s, L))
        if not rules:
            return
        note = self.sounds.note(rules)
        if note and note not in sp["why"]:
            old = sp["why"]
            sp["why"] = "%s (%s)" % (old, note)
            if (hit.get("note") or "").startswith(old):
                hit["note"] = sp["why"] + hit["note"][len(old):]
        spoken = self.sounds.spoken_sound(hit.get("translit") or hit.get("head_sound") or "", rules)
        if spoken:
            sp["sound"], sp["sound_kind"] = spoken, "spoken"

    def _perfect(self, lk, L, entry, key, ctx, i):
        """The perfect collapsed into the simple past (note C5): a second reading, named, only where the page is speech."""
        if not self.verbs or ctx is None or not ctx.evidence(i):
            return
        for h in entry.get("hits") or []:
            if h.get("pos") != "verb" or h.get("_tier", 9) > lk.T_FORM:
                continue
            for formal, person in self._perfect_lines(lk, L, h, key):
                why = self._say("perfect", formal=formal)
                sp = h.get("spoken")
                if sp is None:
                    self._mark(h, "rule", formal, why, readings=[{"as": formal, "why": why}], same=True, note=False)
                elif all(r.get("as") != formal for r in sp.get("readings") or []) and sp.get("as") != formal:
                    sp.setdefault("readings", [{"as": sp.get("as"), "why": sp.get("why")}]).append({"as": formal, "why": why})

    def _perfect_lines(self, lk, L, hit, key):
        """[(the perfect, its person)] a word that is a simple past (or the infinitive that is its 3rd plural) can also be."""
        head = hit.get("headword") or ""
        if lk._fold(head, L) == key:
            return [(self.verbs.perfect(head, "3p"), "3p")] if key.endswith("ن") else []
        tags = set(re.split(r"[ ,]+", hit.get("note") or ""))
        if "past" not in tags or tags & {"negative", "perfect", "progressive", "participle"} or "indicative" not in tags:
            return []
        person = None
        for t, p in (("first-person", "1"), ("second-person", "2"), ("third-person", "3")):
            if t in tags:
                person = p
        number = "p" if "plural" in tags else "s" if "singular" in tags else None
        # the 3rd person singular perfect (رفته است) collapses into the participle, not into the past (رفت)
        if not person or not number or person + number == "3s":
            return []
        perfect = self.verbs.perfect(head, person + number)
        return [(perfect, person + number)] if perfect else []

    @staticmethod
    def _nomarks(L, w):
        return L._strip_re.sub("", w) if L._strip_re is not None else w

    def _readings_of(self, lk, c, L, cands, rank):
        """The Candidates of the peeler as Readings: those that lead to the same entries are ONE reading with the others
        beside it (`readings`), those that lead to other entries are readings of their own, in the order they came."""
        groups = collections.OrderedDict()
        for cand in cands:
            key = tuple(sorted(str(h.get("entry") if h.get("entry") is not None else h.get("headword")) for h in cand.hits))
            groups.setdefault(key, []).append(cand)
        out = []
        for group in list(groups.values())[:3]:
            primary = group[0]
            why = "; ".join(dict.fromkeys(w for w in primary.whys if w))
            alts = list(primary.alts)
            for other in group[1:]:
                alts.append((other.formal, "; ".join(dict.fromkeys(w for w in other.whys if w))))
                alts.extend(other.alts)
            seen, readings = {primary.formal}, [{"as": primary.formal, "why": why}]
            for formal, reason in alts:
                if formal not in seen:
                    seen.add(formal)
                    readings.append({"as": formal, "why": reason})
            kind = "entry" if primary.kind == "entry" else "rule"
            rd = self._reading(rank, kind, primary.formal, why, primary.hits[:MAX_SPOKEN],
                               parts=primary.parts if len(primary.parts) > 1 else None, pieces=primary.pieces or None,
                               readings=readings if len(readings) > 1 else None)
            if rd:
                rd.weak = not primary.by_rule       # spoken only through a row of the table it ends in: a formal ending on a spoken word
                rd.twin = primary.twin
                out.append(rd)
        return out

    # ------------------------------------------------------------------ the dictionary's own colloquial pages
    _OWN = re.compile(r"(?:colloquial|informal|spoken|dialectal)\b[^.;]*?\b(?:form|spelling|pronunciation|variant)\s+of\s+"
                      r"([؀-ۿ" + ZW + r"]+)", re.I)

    def _own(self, lk, c, L, direct):
        out = []
        for h in direct:
            if h.get("_tier", 9) > lk.T_FORM:
                continue
            for sense in h.get("senses") or []:
                m = self._OWN.search(sense)
                if not m:
                    continue
                target = m.group(1).strip(ZW)
                hits = [t for t in self._hits(lk, c, L, target) if t.get("entry") != h.get("entry")]
                rd = self._reading(R_ENTRY, "entry", target, self._say("entry", formal=target), hits[:1])
                if rd:
                    out.append(rd)
                break
        return out

    # ----------------------------------------------------------------------------------------- the word table
    def _table(self, lk, c, L, key, ctx, i):
        """[(Reading, Row)]: the table's readings of this word."""
        out = []
        for row in self.words.get(key, []):
            # a row of a one-letter word (ب for به) or of a word that is only speech's by its neighbours (بسم): only where the chunk says it is speech
            if row.flags.get("needs") == "spoken" and not (ctx is not None and ctx.evidence(i)):
                continue
            if row.kind == "standalone":
                hit = self._pseudo(row)
                rd = self._reading(R_TABLE, "table", row.formal, self._say("standalone"), [hit], gloss=row.gloss)
            else:
                hits = self._formal_hits(lk, c, L, row.formal)
                parts = row.formal.split() if len(row.formal.split()) > 1 and len(hits) > 1 else None
                why = row.note or self._say("table", formal=row.formal)
                rd = self._reading(R_TABLE, "table", row.formal, why, hits[:MAX_SPOKEN], parts=parts, gloss=row.gloss)
            if rd:
                out.append((rd, row))
        return out

    # ---------------------------------------------------------------------------------------------- the rules
    def _rules(self, lk, c, L, bare, w, cleaned, strength):
        """The writing-level rules, in the order of the note: the first that lands on something wins."""
        out = []
        for stage in (self._manner, self._digits, self._hashtag, self._glue, self._cv_glued, self._tanwin, self._lengthened,
                      self._swaps, self._run_together):
            got = stage(lk, c, L, bare, w, strength)
            if got:
                return got
        return out

    def _clean_stage(self, lk, c, L, bare, w, cleaned):
        """The word written with letters that are not Persian's, read as the Persian spelling: the first thing a word is asked."""
        if w == bare:
            return []
        ent = lk._resolve(c, w, [], L, False)
        ent = ent[0] if ent else None
        if ent and self._strength(lk, ent) >= 2:
            what = ", ".join(self.clean_what.get(n, n) for n in dict.fromkeys(cleaned))
            why = self._say("clean_ezafe") if "ۀ" in bare else self._say("clean", what=what)
            rd = self._reading(R_CLEAN, "rule", w, why, ent["hits"][:1])
            if rd:
                return [rd]
        return []

    def _first_hits(self, lk, c, L, forms):
        """Of these candidate spellings, in order, the ones the dictionary has: [(form, hits)]."""
        keyed = [(lk._fold(f, L), f) for f in forms]
        found = self._known(lk, c, [k for k, _f in keyed])
        out = []
        for k, f in keyed:
            if k in found:
                hits = lk._hits_for(c, k)
                if hits:
                    out.append((f, hits))
        return out

    # ----- tanwin
    def _tanwin(self, lk, c, L, bare, w, strength=0):
        cfg = self.S.get("tanwin") or {}
        m = re.search("(?:اً|ًا|ً)$", w)
        if m:
            base = w[:m.start()]
            if len(base) >= cfg.get("min_stem", 2):
                ent = lk._resolve(c, base, [], L, False)
                ent = ent[0] if ent else None
                if ent and self._strength(lk, ent) == 3:
                    rd = self._reading(R_RULE, "rule", base, self._say("tanwin_mark", base=base), ent["hits"][:1])
                    if rd:
                        return [rd]
        k = lk._fold(w, L)
        if k.endswith("ن") and len(k) >= cfg.get("min_word", 4):
            for form, hits in self._first_hits(lk, c, L, [k[:-1] + "ا"]):
                adv = [h for h in hits if (h.get("headword") or "").endswith("اً")]
                rd = self._reading(R_RULE, "rule", adv[0]["headword"] if adv else form, self._say("tanwin_n"), adv[:1])
                if rd:
                    return [rd]
        return []

    # ----- letters held long
    def _lengthened(self, lk, c, L, bare, w, strength=0):
        cfg = self.S.get("lengthened") or {}
        runs = [(m.start(), m.end()) for m in re.finditer(r"(.)\1{%d,}" % (cfg.get("min_run", 3) - 1), w)]
        if not runs or len(runs) > 4:
            return []
        cands = []
        for choice in range(2 ** len(runs)):
            out, last = [], 0
            for n, (a, b) in enumerate(runs):
                out.append(w[last:a])
                out.append(w[a] * (2 if (choice >> n) & 1 else 1))
                last = b
            out.append(w[last:])
            cand = "".join(out)
            if len(cand) >= cfg.get("min_word", 2):
                cands.append((len(cand), choice, cand))
        cands = [x[2] for x in sorted(cands)]
        for form, hits in self._first_hits(lk, c, L, cands):
            rd = self._reading(R_LENGTH, "rule", form, self._say("lengthened"), hits[:1])
            if rd:
                return [rd]
        return []

    # ----- another carrier of the hamza, another of two accepted spellings, a keyboard's letters
    def _swaps(self, lk, c, L, bare, w, strength=0):
        n = len(w)
        for group in self.S.get("swaps") or []:
            if n < group.get("min_word", 3):
                continue
            # a `set` swaps any of its letters for another; a `pair` swaps the first for the second only where the group
            # is `one_way` (a keyboard types ب for پ, never the other way), and every way where it is not
            one_way = group.get("one_way")
            sets = [list(s) for s in group.get("sets") or []]
            pairs = [list(p) for p in group.get("pairs") or []]
            at = group.get("at", "any")
            cands = []
            for pos, ch in enumerate(w):
                if (at == "initial" and pos != 0) or (at == "final" and pos != n - 1):
                    continue
                for s in sets:
                    if ch in s:
                        for other in s:
                            if other != ch:
                                cands.append(w[:pos] + other + w[pos + 1:])
                for first, second in pairs:
                    if ch == first:
                        cands.append(w[:pos] + second + w[pos + 1:])
                    elif ch == second and not one_way:
                        cands.append(w[:pos] + first + w[pos + 1:])
            for form, hits in self._first_hits(lk, c, L, cands):
                rd = self._reading(R_SWAP, "rule", form, self._say("swap", what=group.get("what", ""), formal=form), hits[:1])
                if rd:
                    return [rd]
        return []

    # ----- words run together
    def _run_together(self, lk, c, L, bare, w, strength=0):
        """Two or more full words written with no space (تورادوست‌دارم): split only where every piece is a word of the dictionary, and where
        what is left says it is more than a coincidence of letters (two function words, or three pieces one of which is one)."""
        cfg = self.S.get("run_together") or {}
        k = lk._fold(w, L)
        if not cfg or len(k) < cfg.get("min_word", 6) or len(k) > cfg.get("max_word", 24):
            return []
        lo, most = cfg.get("min_piece", 2), cfg.get("max_pieces", 4)
        spans = {(a, b): k[a:b] for a in range(len(k)) for b in range(a + lo, len(k) + 1)}
        known = self._known(lk, c, list(set(spans.values())))
        function = {lk._fold(x, L) for x in cfg.get("function_words") or []}
        best = []

        def split(start, pieces):
            if start == len(k):
                best.append(list(pieces))
                return
            if len(pieces) >= most:
                return
            for end in range(len(k), start + lo - 1, -1):
                piece = spans.get((start, end))
                if piece in known:
                    pieces.append(piece)
                    split(end, pieces)
                    pieces.pop()
        split(0, [])
        for pieces in sorted(best, key=lambda p: (len(p), [-len(x) for x in p])):
            fn = [p for p in pieces if p in function]
            if not (len(fn) >= 2 or (len(pieces) >= 3 and fn and all(len(p) >= 3 for p in pieces if p not in function))):
                continue
            hits = []
            for p in pieces:
                got = [h for h in self._hits(lk, c, L, p) if h.get("_tier", 0) <= lk.T_FORM]
                if not got:
                    hits = []
                    break
                hits.append(got[0])
            if hits:
                rd = self._reading(R_RULE, "rule", " ".join(pieces), self._say("run_together", parts=" ".join(pieces)), hits, parts=pieces)
                if rd:
                    return [rd]
        return []

    # ----- figures and hashtags
    def _number_words(self, n):
        """The words a whole number is said with, in order, e.g. 21 -> [بیست, یک]; None past a million."""
        if n in self._numbers:
            return self._numbers[n]
        if n < 0 or n >= 1000000:
            return None
        parts = []

        def below_thousand(m):
            out = []
            if m >= 100:
                out.append(_HUNDREDS[m // 100])
                m %= 100
            if m >= 20:
                out.append(_TENS[m // 10])
                m %= 10
                if m:
                    out.append(_ONES[m])
            elif m or not out:
                out.append(_ONES[m])
            return out
        thousands, rest = divmod(n, 1000)
        if thousands:
            parts.extend(below_thousand(thousands) if thousands > 1 else [])
            parts.append("هزار")
        if rest or not thousands:
            parts.extend(below_thousand(rest))
        out = []
        for p in parts:
            if out:
                out.append("و")
            out.append(p)
        if n == 0:
            out = ["صفر"]
        self._numbers[n] = out
        return out

    def _digits(self, lk, c, L, bare, w, strength=0):
        m = re.match(r"^([0-9۰-۹٠-٩]+)(\D.*)$", lk._fold(w, L))
        if not m:
            return []
        words = self._number_words(int("".join(str(_DIGITS[d]) for d in m.group(1))))
        rest = m.group(2)
        if not words or not rest:
            return []
        said = " ".join(words)
        cfg = self.S.get("digits") or {}
        # one word with the rest (۴شنبه = چهارشنبه, ۲ست = دوست, an ordinal ۱۰م = دهم)
        if len(words) == 1:
            base = words[0]
            joined = [base + rest]
            if rest in ("م", "ام", ZW + "ام"):
                joined = [cfg.get("special", {}).get(base)] if base in (cfg.get("special") or {}) else []
                joined += [base + "م", base + ZW + "ام", base + "ام"]
            for form, hits in self._first_hits(lk, c, L, [j for j in joined if j]):
                rd = self._reading(R_RULE, "rule", form, self._say("digits", formal=form), hits[:1])
                if rd:
                    return [rd]
        # the number's words, and the rest as a word of its own
        piece = self._piece(lk, c, L, rest)
        if piece:
            hits = []
            for word in words:
                if word == "و":
                    continue
                h = self._piece(lk, c, L, word)
                if not h:
                    return []
                hits.append(h[0])
            hits.append(piece[0])
            rd = self._reading(R_RULE, "rule", said + " " + piece[1], self._say("digits", formal=said + " " + piece[1]), hits,
                               parts=[x for x in words if x != "و"] + [piece[1]])
            if rd:
                return [rd]
        return []

    def _hashtag(self, lk, c, L, bare, w, strength=0):
        if not w.startswith("#") and "_" not in w:
            return []
        body = w.lstrip("#")
        parts = [p for p in re.split(r"[_" + ZW + r"]+", body) if p]
        if len(parts) < 2:
            return []
        hits = []
        for p in parts:
            got = self._piece(lk, c, L, p)
            if not got:
                return []
            hits.append(got[0])
        rd = self._reading(R_RULE, "rule", " ".join(parts), self._say("hashtag"), hits, parts=parts)
        return [rd] if rd else []

    # ----- words written together
    def _glue(self, lk, c, L, bare, w, strength=0, only=None):
        g = self.S.get("glue") or {}
        k = lk._fold(w, L)
        # را written on the word before it (آنرا)
        om = g.get("object_marker") or {}
        suf = om.get("suffix")
        if only != "numbers" and suf and k.endswith(suf) and len(k) - len(suf) >= om.get("min_stem", 2):
            stem = k[:-len(suf)]
            piece = self._piece(lk, c, L, stem, glue=True)
            if piece and (piece[0].get("pos") in om.get("after", [])):
                hit = self._piece(lk, c, L, om.get("word", suf), glue=True)
                if hit:
                    return self._glued(lk, c, L, [piece[1], om.get("word", suf)], [piece[0], hit[0]])
        # numbers together with و (بیستویک), and a number with its counter (دوتا)
        na = g.get("number_and") or {}
        letter = na.get("letter")
        if letter and len(k) >= 5:
            for p in range(2, len(k) - 2):
                if k[p] == letter:
                    left, right = self._piece(lk, c, L, k[:p], glue=True), self._piece(lk, c, L, k[p + 1:], glue=True)
                    if left and right and left[0].get("pos") in na.get("pos", []) and right[0].get("pos") in na.get("pos", []):
                        return self._glued(lk, c, L, [left[1], right[1]], [left[0], right[0]])
        classifiers = g.get("classifiers") or []
        for p in range(len(k) - 1, 1, -1):
            if k[p:] in classifiers:
                left = self._piece(lk, c, L, k[:p], glue=True)
                if left and left[0].get("pos") == "num":
                    right = self._piece(lk, c, L, (g.get("classifier_formal") or {}).get(k[p:], k[p:]), glue=True)
                    if right:
                        return self._glued(lk, c, L, [left[1], right[1]], [left[0], right[0]])
        if only == "numbers":
            return []
        # a short word in front of another: از + این, ب + خاطر, چ + خبر, ی + روز.  The alef of the second word is
        # often not written when the first ends the way از does (ازین, ازون): both spellings of what is left are tried.
        for table, rest_pos, min_rest in ((g.get("prepositions"), g.get("prepositions_rest_pos"), g.get("prepositions_min_rest", 3)),
                                          (g.get("what"), g.get("what_rest_pos"), 2),
                                          (g.get("one"), None, g.get("one_min_rest", 3))):
            for first in sorted(table or {}, key=len, reverse=True):
                if not k.startswith(first) or len(k) - len(first) < 2:
                    continue
                tail = k[len(first):]
                formal = table[first]
                for rest_text in dict.fromkeys([tail, "ا" + tail]):
                    if len(rest_text) < min_rest:
                        continue
                    phrase = formal + " " + rest_text
                    whole = [h for h in self._hits(lk, c, L, phrase) if lk._fold(h.get("headword") or "", L) == lk._fold(phrase, L)]
                    if whole:
                        return self._glued(lk, c, L, [formal, rest_text], [], whole)
                    rest = self._piece(lk, c, L, rest_text, glue=True)
                    if not rest and self.peeler and table is g.get("prepositions"):
                        rest = self.peeler.stem_piece(lk, c, L, rest_text)      # بنظرم: the word that follows may carry a clitic
                    if rest and (not rest_pos or rest[0].get("pos") in rest_pos):
                        head = self._piece(lk, c, L, formal, glue=True)
                        if head:
                            return self._glued(lk, c, L, [formal, rest[1]], [head[0], rest[0]])
        return []

    def _glued(self, lk, c, L, formals, hits, whole=None):
        """The pieces of a word written together as one reading: the phrase itself where the dictionary has it."""
        phrase = " ".join(formals)
        whole = whole or [h for h in self._hits(lk, c, L, phrase) if lk._fold(h.get("headword") or "", L) == lk._fold(phrase, L)]
        if whole:
            rd = self._reading(R_RULE, "rule", phrase, self._say("glued", parts=phrase), whole[:1])
        else:
            rd = self._reading(R_RULE, "rule", phrase, self._say("glued", parts=phrase), hits, parts=formals)
        return [rd] if rd else []

    # ----- spoken -جوری / -طوری
    def _manner(self, lk, c, L, bare, w, strength=0):
        cfg = self.S.get("manner") or {}
        k = lk._fold(w, L)
        for suffix in cfg.get("suffixes") or []:
            if not k.endswith(suffix):
                continue
            base = k[:-len(suffix)]
            for b in cfg.get("bases") or []:
                if base not in [lk._fold(x, L) for x in b["spoken"]]:
                    continue
                stem = suffix[:-1]
                compound = b.get("compound") or (b["formal"] + ZW + "طور")
                hits = self._hits(lk, c, L, compound)
                if hits:
                    readings = None
                    if compound == "چطور" and suffix.startswith("طور"):
                        readings = [{"as": compound + " " + "هستی", "why": self._say("manner_how")},
                                    {"as": compound, "why": self._say("manner", formal=compound)}]
                    rd = self._reading(R_RULE, "rule", compound, self._say("manner", formal=compound), hits[:1], readings=readings)
                else:
                    first = self._piece(lk, c, L, b["formal"])
                    second = self._piece(lk, c, L, stem)
                    if not (first and second):
                        continue
                    rd = self._reading(R_RULE, "rule", b["formal"] + " " + stem, self._say("manner", formal=b["formal"] + " " + stem),
                                       [first[0], second[0]], parts=[b["formal"], stem])
                if rd:
                    return [rd]
        return []

    # ------------------------------------------------------------------------------------------------ windows
    def window(self, lk, c, L, tokens, i, ctx):
        """Two or three words of the chunk that are one thing: (the answer for them, how many words it took), or None.

        A phrase of the tables, the first part of a compound verb beside its verb (نیگا کن), a word beside
        its echo (کتاب متاب) or its repeat (یواش یواش), a word the text writes apart from the one it
        belongs to (بی شعور).  The words of the chunk go on being what they are anywhere else."""
        left = len(tokens) - i
        if left < 2:
            return None
        got = self._spaced_window(lk, c, L, tokens, i)
        if got:
            return got
        bare = [lk._bare(t, L) for t in tokens[i:i + 3]]
        if not bare[0] or not bare[1]:
            return None
        keys = [lk._fold(b, L) for b in bare]
        for row in self.multi.get(keys[0], []):
            n = len(row.tokens)
            if n <= left and tuple(keys[:n]) == row.tokens and all(bare[:n]):
                rd = self._phrase(lk, c, L, row, bare[:n])
                if rd:
                    return self._window_entry(tokens[i:i + n], rd), n
        for stage in (self._cv_window, self._join_window, self._echo_window):
            got = stage(lk, c, L, bare, keys)
            if got:
                return self._window_entry(tokens[i:i + 2], got), 2
        got = self._suffix_window(lk, c, L, bare, keys, ctx, i)
        if got:
            return got, 2
        got = self._psych_window(lk, c, L, bare, keys, ctx, i)
        if got:
            return self._window_entry(tokens[i:i + 2], got), 2
        got = self._clitic_compound_window(lk, c, L, bare, keys, ctx, i)
        if got:
            return self._window_entry(tokens[i:i + 2], got), 2
        got = self._progressive_window(lk, c, L, bare, keys, ctx, i)
        if got:
            return self._window_entry(tokens[i:i + 2], got), 2
        return None

    def _spaced_window(self, lk, c, L, tokens, i):
        """Letters spaced out for emphasis (ن ه, ب ر و): a run of single letters that is a word of the dictionary's own."""
        cfg = self.S.get("spaced_letters") or {}
        if not cfg:
            return None
        letters = []
        for t in tokens[i:i + cfg.get("max", 4)]:
            b = lk._bare(t, L)
            if len(b) != 1 or not b.isalpha():
                break
            letters.append(b)
        for n in range(len(letters), 1, -1):
            joined = "".join(letters[:n])
            ent = lk._resolve(c, joined, [], L, False)
            ent = ent[0] if ent else None
            if ent and self._strength(lk, ent) == 3:
                rd = self._reading(R_RULE, "rule", joined, self._say("spaced_letters", word=joined), ent["hits"][:MAX_SPOKEN])
                if rd:
                    return self._window_entry(tokens[i:i + n], rd), n
        return None

    def _progressive_window(self, lk, c, L, bare, keys, ctx, i):
        """داره میاد, داشتم میگفتم: the helper داشتن and a verb with می-: one verb, said as it goes on (note C4)."""
        if not self.verbs:
            return None
        aux = self._piece(lk, c, L, bare[0], loose=True, pos="verb")
        if not aux or aux[0].get("headword") != "داشتن":
            return None
        main = self._piece(lk, c, L, bare[1], loose=True, pos="verb")
        if not main or main[0].get("headword") == "داشتن" or not lk._fold(main[1], L).startswith(("می", "نمی")):
            return None
        why = self._say("progressive", aux=bare[0])
        piece = {"text": bare[0], "role": "progressive", "note": why}
        return self._reading(R_RULE, "rule", main[1], why, [main[0]], pieces=[piece])

    def _clitic_compound_window(self, lk, c, L, bare, keys, ctx, i):
        """A compound verb with a clitic on its nominal part (پیداش کردم = پیدا کردم: the clitic is the object): the two words are
        asked as the compound the dictionary lists."""
        if not self.peeler or len(keys[0]) < 3 or len(keys[1]) < 2:
            return None
        clitics = list((self.S.get("peel") or {}).get("clitics", {}).get("formal") or []) + \
            list((self.S.get("peel") or {}).get("clitics", {}).get("spoken_plural") or [])
        verb = self._piece(lk, c, L, bare[1], loose=True, pos="verb")
        if not verb:
            return None
        said = verb[1]
        for s, rest in self.peeler._ends(keys[0], clitics):
            if len(rest) < 2:
                continue
            row = self.cv.get(lk._fold(rest, L))
            # (the closed first part and a clitic make a word of the dictionary's own more than once: دوست is دوس + ت, and is دوست)
            if row and self._known(lk, c, [keys[0]]):
                row = None
            for restore, stem in [("", rest), ("ه", rest + "ه")] + ([("cv", row.formal)] if row else []):
                # the compound as the tables list it: apart (ول بکن), or with its preverb joined and no ب- (بر + بدار is بردار)
                forms = [stem + " " + said, stem + said, stem + (said[1:] if said.startswith("ب") else said)]
                hits = [h for f in forms for h in self._hits(lk, c, L, f)
                        if h.get("pos") == "verb" and ((" " in (h.get("headword") or "")) or (h.get("headword") or "").startswith(stem))]
                if hits:
                    why = self._say("clitic_compound", stem=rest + (restore if restore == "ه" else ""), ending=s)
                    piece = {"text": s, "role": "clitic", "note": why}
                    return self._reading(R_RULE, "rule", hits[0]["headword"], why, hits[:1], pieces=[piece])
        return None

    def _psych_window(self, lk, c, L, bare, keys, ctx, i):
        """A feeling said with a clitic and a verb or an adjective after it: یادم رفت, حالم بده, خوشم میاد (note C8)."""
        pairs = (self.S.get("psych") or {}).get("pairs") or []
        if not pairs or not self.peeler:
            return None
        first = self.peeler.stem_piece(lk, c, L, bare[0], ctx, i)
        if not first:
            return None
        stem = first[0].get("headword")
        wanted = [p[1] for p in pairs if lk._fold(p[0], L) == lk._fold(stem or "", L)]
        if not wanted:
            return None
        entries = lk._resolve(c, bare[1], [], L, False)
        second = self.augment(lk, c, L, dict(entries[0], word=bare[1]) if entries else {"word": bare[1], "hits": [], "via": "", "tried": [], "kind": ""},
                              ctx, (i or 0) + 1)
        for h in second.get("hits") or []:
            if h.get("headword") in wanted:
                why = self._say("psych", stem=stem, **{"with": h["headword"]})
                return self._reading(R_RULE, "rule", first[1] + " " + bare[1], why, [first[0], h], parts=[stem, h["headword"]])
        return None

    def _suffix_window(self, lk, c, L, bare, keys, ctx, i):
        """A word and its plural written apart (کتاب ها, بچه هاشون): the two read as the one word they are."""
        if keys[1] not in {lk._fold(w, L) for w in (self.S.get("join") or {}).get("suffix_words") or []}:
            return None
        joined = bare[0] + ZW + bare[1]
        ent = lk._resolve(c, joined, [], L, False)
        ent = ent[0] if ent else None
        if not ent or not ent["hits"]:
            return None
        ent["word"] = bare[0] + " " + bare[1]
        ent = self.augment(lk, c, L, dict(ent, word=joined), ctx, i)
        why = self._say("spaced", parts=bare[0] + " " + bare[1])
        hits = [self._mark(dict(h), "rule", joined, why, readings=None) if not h.get("spoken") else h for h in ent["hits"][:MAX_SPOKEN]]
        for n, h in enumerate(hits):
            h["_tier"] = FIRST + n / 1000.0
        return {"word": bare[0] + " " + bare[1], "hits": hits, "via": self._say("via", why=why), "tried": [], "kind": "spoken"}

    def _window_entry(self, raw_tokens, reading):
        hits = reading.hits
        for n, h in enumerate(hits):
            h["_tier"] = FIRST + n / 1000.0
        return {"word": " ".join(raw_tokens), "hits": hits, "via": self._say("via", why=hits[0]["spoken"]["why"]), "tried": [],
                "kind": "spoken"}

    def _phrase(self, lk, c, L, row, bare):
        if row.kind == "standalone":
            return self._reading(R_TABLE, "table", row.formal, self._say("standalone"), [self._pseudo(row)], gloss=row.gloss)
        if row.kind == "phrase":
            hits = self._formal_hits(lk, c, L, row.formal)
            parts = row.formal.split() if len(hits) > 1 else None
            return self._reading(R_TABLE, "table", row.formal, row.note or self._say("table", formal=row.formal), hits[:MAX_SPOKEN],
                                 parts=parts, gloss=row.gloss)
        # a formula is read word by word, and means what it means as a whole
        hits = []
        for t in bare:
            got = self._piece(lk, c, L, t, loose=True)
            if not got:
                return None
            hits.append(got[0])
        return self._reading(R_TABLE, "table", row.formal, row.note or self._say("formula"), hits, gloss=row.gloss,
                             parts=[x for x in row.formal.split()] if len(row.formal.split()) == len(hits) else None)

    def _cv_window(self, lk, c, L, bare, keys):
        row = self.cv.get(keys[0])
        if not row:
            return None
        verb = self._piece(lk, c, L, bare[1], loose=True, pos="verb")
        if not verb:
            return None
        return self._cv_reading(lk, c, L, row, bare[1], verb)

    def _cv_reading(self, lk, c, L, row, verb_text, verb):
        light = row.flags.get("with")
        vhead = verb[0].get("headword") or ""
        verb_text = verb[1] or verb_text                  # the verb as the formal tables write it: کن is بکن
        compound = row.formal + " " + vhead
        said = row.formal + " " + verb_text               # ... and what the two words are said as: نگاه بکن
        # the compound as the dictionary lists it, with the verb's own form: نگاه کن is a form of نگاه کردن
        hits = self._hits(lk, c, L, row.formal + " " + verb_text) or self._hits(lk, c, L, compound)
        hits = [h for h in hits if h.get("headword") == compound] or [h for h in hits if (h.get("pos") or "") == "verb" and " " in (h.get("headword") or "")][:1]
        if not hits:
            # a preverb written on its verb, as one word (بر + داشتن is برداشتن)
            joined = row.formal + vhead
            hits = [h for h in self._hits(lk, c, L, joined) + self._hits(lk, c, L, row.formal + verb_text.lstrip("ب"))
                    if (h.get("pos") or "") == "verb" and lk._fold(h.get("headword") or "", L) == lk._fold(joined, L)][:1]
            if hits:
                compound, said = joined, row.formal + verb_text
        why = self._say("compound", formal=compound)
        if hits:
            return self._reading(R_TABLE, "table", said, why, hits[:1], parts=[row.formal, vhead])
        if light and vhead == light and row.gloss:
            pseudo = self._pseudo(Row(compound, compound, "standalone", {"pos": "verb"}, row.gloss, "", row.src, ()))
            return self._reading(R_TABLE, "table", compound, why, [pseudo], parts=[row.formal, vhead], gloss=row.gloss)
        if row.spoken == row.formal and not row.gloss and vhead in (self.S.get("cv_light") or []):
            first = self._piece(lk, c, L, row.formal)
            if first:
                return self._reading(R_TABLE, "table", compound, self._say("loan", formal=row.formal), [first[0], verb[0]],
                                     parts=[row.formal, vhead])
        return None

    def _cv_glued(self, lk, c, L, bare, w, strength=0):
        """The first part of a compound verb written on its verb as one word: پاشدم, واکرد, دوسدارم."""
        k = lk._fold(w, L)
        for n in range(len(k) - 2, 1, -1):
            row = self.cv.get(k[:n])
            if not row:
                continue
            rest = k[n:]
            verb = self._piece(lk, c, L, rest, pos="verb")
            if verb:
                rd = self._cv_reading(lk, c, L, row, rest, verb)
                if rd:
                    return [rd]
        return []

    def _join_window(self, lk, c, L, bare, keys):
        if keys[0] not in self.join_first:
            return None
        cfg = self.S.get("join") or {}
        if len(keys[1]) < cfg.get("min_rest", 2):
            return None
        for glue in (ZW, ""):
            formal = bare[0] + glue + bare[1]
            hits = self._hits(lk, c, L, formal)
            hits = [h for h in hits if lk._fold(h.get("headword") or "", L) == lk._fold(formal, L)]
            if hits:
                return self._reading(R_TABLE, "rule", hits[0]["headword"], self._say("joined", parts=bare[0] + " " + bare[1],
                                                                                      formal=hits[0]["headword"]), hits[:1])
        return None

    def _echo_window(self, lk, c, L, bare, keys):
        cfg = self.S.get("echo") or {}
        a, b = keys[0], keys[1]
        if len(a) < cfg.get("min_word", 3) or not a.isalpha():
            return None
        if a == b:
            first = self._piece(lk, c, L, bare[0])
            if first:
                return self._reading(R_RULE, "rule", first[1], self._say("twice"), [first[0]], parts=[first[1]],
                                     pieces=[{"text": bare[1], "role": "repeat", "note": self._say("twice")}])
            return None
        letter = cfg.get("letter", "م")
        if a[0] != letter and b == letter + a[1:]:
            first = self._piece(lk, c, L, bare[0])
            if first:
                return self._reading(R_RULE, "rule", first[1], self._say("echo", echo=bare[1]), [first[0]], parts=[first[1]],
                                     pieces=[{"text": bare[1], "role": "echo", "note": self._say("echo", echo=bare[1])}])
        return None
