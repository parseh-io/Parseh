#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Layer 8 of the spoken pass: the sound changes that speech writes down, read backwards (the note's section B).

    sounds = spokensound.Sounds(config, text)
    sounds.raw("خونه")                           # -> [("خانه", rule), ...]: every word one rule makes of it, dictionary not asked
    sounds.explain("خونه", "خانه")               # -> [rule]: the rule that says the first is the second said aloud
    sounds.spoken_sound("xāne", rules)           # -> "xune": the formal romanisation, with the rules' sound changes put in

A SOUND RULE IS ONE STEP BACK, and only one (layer 9 adds the spellings by ear of A4 -- letters that sound the same, a silent و after
خ, a vowel written out as a letter -- as rules of a second STAGE that is asked only of a stem the first stage found nothing for): ون for ان, ـس for ـست, a ه or a ع not written, an extra ی between two
consonants, two letters that changed places.  The rule file gives each rule as what to find (`find`, a regular expression, with
its anchors where the rule is for the end or the start of a word) and what to put (`put`); this file applies it at every place it
fits, one place at a time, and says nothing of what the result is.  THE DICTIONARY SAYS THAT (lib/spokenpeel.py asks it of
every result): so the exceptions of the forward sound change need no list, a rule that does not land on a word does not land.

THE ORDER IS THE FILE'S, and the file's is the note's: B1, the largest family, first.  Two rules on one word are not tried (the
words that need two are in the word table: a closed set is a list, an open rule is a guess, and a guess upon a guess is where a
dictionary of seventeen thousand words invents things).

WHAT THE READER IS TOLD.  Each rule says in words what changed (`note`: "ā said u before a nasal"), and, where the sound of the
word changes in the way the spelling does, how its romanisation changes (`sound`: a pattern and what to put, applied to the
formal word's romanisation: xāne -> xune).  A rule with no `sound` leaves the formal sound, and the answer says it is the
formal one.

What is about Persian is data (lib/lang/fa.lookup.json, `spoken.sound`); a second language brings its own rules, and this file,
which only applies patterns, is the same.
"""
import re

ZW = "‌"
MAX_VARIANTS = 200


class Rule:
    __slots__ = ("id", "rx", "put", "sound", "note", "min", "swap", "cost", "stage")

    def __init__(self, spec):
        self.id = spec.get("id") or ""
        self.swap = bool(spec.get("swap"))
        self.rx = re.compile(spec["find"]) if spec.get("find") is not None else None
        self.put = spec.get("put", "")
        pair = spec.get("sound")
        self.sound = (re.compile(pair[0]), pair[1]) if pair else None
        self.note = spec.get("note") or ""
        self.min = spec.get("min", 2)
        self.cost = spec.get("cost", 1)         # what the rule adds to a path's rewrites: a broad guess costs more than a regular change
        self.stage = spec.get("stage", 8)       # 8: the sound changes of the note's B; 9: the spellings by ear of its A4, tried after them


def _expand(spec):
    """A `sets` rule (letters that sound the same) is one rule for each letter put for each other of its set."""
    if "sets" not in spec:
        return [spec]
    out = []
    for group in spec["sets"]:
        for a in group:
            for b in group:
                if a != b:
                    one = {k: v for k, v in spec.items() if k != "sets"}
                    one.update({"id": "%s-%s%s" % (spec.get("id", "sets"), a, b), "find": a, "put": b,
                                "note": (spec.get("note") or "{a} written for {b}").format(a=a, b=b)})
                    out.append(one)
    return out


class Sounds:
    def __init__(self, cfg, text):
        self.text = text or {}
        self.rules = [Rule(one) for r in cfg.get("rules") or [] for one in _expand(r)]
        self.tails = list(cfg.get("plural_tails") or [])
        self.cap = cfg.get("max_variants", MAX_VARIANTS)
        self.max_known = cfg.get("max_known", 8)

    @staticmethod
    def _letters(word):
        return len(word.replace(ZW, ""))

    def raw(self, word, stage=None):
        """[(variant, rule)]: what each rule makes of the word at each place it fits.  A variant comes once, from the first rule.
        With `stage` only the rules of that stage (8 the sound changes, 9 the spellings by ear); without, all of them."""
        out, seen = [], {word}
        for rule in self.rules:
            if self._letters(word) < rule.min or (stage is not None and rule.stage != stage):
                continue
            if rule.swap:
                # two letters that changed places: not a ZWNJ and not two of the same
                for i in range(len(word) - 1):
                    a, b = word[i], word[i + 1]
                    if a == b or ZW in (a, b):
                        continue
                    v = word[:i] + b + a + word[i + 2:]
                    if v not in seen:
                        seen.add(v)
                        out.append((v, rule))
                continue
            for m in rule.rx.finditer(word):
                v = word[:m.start()] + m.expand(rule.put) + word[m.end():]
                if v not in seen and v.replace(ZW, ""):
                    seen.add(v)
                    out.append((v, rule))
            if len(out) >= self.cap:
                break
        return out[:self.cap]

    def explain(self, word, formal, fold=None):
        """[rule]: the rule that makes `formal` of `word`, or [].  `fold` writes both the way the dictionary does."""
        fold = fold or (lambda s: s.replace(ZW, ""))
        goal = fold(formal)
        if not goal or fold(word) == goal:
            return []
        for variant, rule in self.raw(word):
            if fold(variant) == goal:
                return [rule]
        return []

    def note(self, rules):
        return "; ".join(dict.fromkeys(r.note for r in rules if r.note))

    @staticmethod
    def spoken_sound(translit, rules):
        """The formal romanisation with the sound changes of these rules put in, or "" where a rule has no sound change to give
        (the answer then says it is the formal one)."""
        if not translit or not rules or not all(r.sound for r in rules):
            return ""
        out = translit
        for r in rules:
            out = r.sound[0].sub(r.sound[1], out)
        return out if out != translit else ""
