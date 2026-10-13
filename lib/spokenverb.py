#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The verb of the spoken pass (layer 7 of the note's section 12): a spoken verb form taken apart into its prefix, its stem and
its ending, and written again the way the formal tables write it.

    verbs = spokenverb.Verbs(path, fold)         # the stems of lib/lang/fa.spoken.verbs.tsv
    verbs.analyze("میگم")                        # -> [VForm("می‌گویم", "the spoken stem گ for گوی", <گفتن>)]

THE ANALYSIS, NOT A LIST OF FORMS.  A spoken form is a prefix (می- نمی- ب- ن- or none), a stem (the spoken present or past stem of a
verb, as speech writes it: گ for گوی, اومد for آمد) and an ending (-e -in -an for the formal -ad -id -and).  The stems are the table;
the prefixes, the endings, the glide a prefix takes before a vowel (بیا, نیومد, می‌یاد), the bare imperative (کن for بکن) are the
rules; and what comes out is the formal STRING, which the caller looks up in the dictionary: a form counts only if the dictionary's own
conjugation table has it.  So the same code reads a verb the table gives a contracted stem to, and one it does not know is checked by
the old affix rules (and by the sound rules of layer 8) as it always was.

The formal strings are made the way Persian's tables write them (می‌گویم, نمی‌دانم, بیاورم, بنشین, برمی‌دارم): the formal stems and the
few things a verb does its own way (`formal`: the subjunctive's stem with its ب-, the negative's, the imperative) are in the table.
What this file knows about Persian's writing is that: where a ZWNJ goes after می- and where a preverb stands.
"""
import re

ZW = "‌"
VOWELS = "اآ"
# spoken ending -> the formal ending, for the present and the subjunctive, and for the past
PRESENT_ENDINGS = [("م", "م"), ("ی", "ی"), ("ه", "د"), ("د", "د"), ("یم", "یم"), ("ین", "ید"), ("ید", "ید"), ("ن", "ند"), ("ند", "ند")]
PAST_ENDINGS = [("م", "م"), ("ی", "ی"), ("", ""), ("یم", "یم"), ("ین", "ید"), ("ید", "ید"), ("ن", "ند"), ("ند", "ند")]
IMPERATIVE_ENDINGS = [("", ""), ("ین", "ید"), ("ید", "ید")]
PERSON = {"م": "1s", "ی": "2s", "ه": "3s", "د": "3s", "": "3s", "یم": "1p", "ین": "2p", "ید": "2p", "ن": "3p", "ند": "3p"}


class Verb:
    __slots__ = ("inf", "past", "pres", "sp_pres", "sp_past", "formal", "flags", "src")

    def __init__(self, row):
        self.inf, self.past, self.pres = row["infinitive"], row["past"], row["present"]
        self.sp_pres = [x for x in (row.get("spoken_present") or "").split("|") if x]
        self.sp_past = [x for x in (row.get("spoken_past") or "").split("|") if x]
        self.formal = dict(p.split("=", 1) for p in (row.get("formal") or "").split(";") if "=" in p)
        self.flags = {}
        for part in (row.get("flags") or "").split(","):
            part = part.strip()
            if part:
                k, _, v = part.partition("=")
                self.flags[k] = v or True
        self.src = row.get("src") or ""


class VForm:
    """One reading of a spoken verb form: the formal string it stands for, and why, in words."""
    __slots__ = ("formal", "why", "verb", "kind", "person", "negative", "auto")

    def __init__(self, formal, why, verb, kind, person, negative=False, auto=False):
        self.formal, self.why, self.verb, self.kind, self.person, self.negative, self.auto = formal, why, verb, kind, person, negative, auto


class Verbs:
    def __init__(self, path, fold, text):
        self.fold, self.text = fold, text
        self.verbs = {}
        self.base = {}              # prefixed stem (folded) -> [(verb, kind, prefix class, formal stem, spoken stem, changed)]
        self.special = {}           # a spoken imperative that is a word of its own -> [(formal, verb)]
        self.infinitive = {}        # a spoken infinitive -> [(formal infinitive, verb)]
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
                v = Verb(dict(zip(header, cells)))
                if v.inf and v.past and v.pres:
                    self.verbs[v.inf] = v
                    self._index(v)

    # ------------------------------------------------------------------------------------------------ the index
    @staticmethod
    def _auto_present(stem):
        """The spoken present stems a formal one makes by the sound change alone: -ān → -un (رسان → رسون, مان → مون)."""
        out = []
        if stem.endswith("ان") and len(stem) > 3 and stem[-3] not in "وا":
            out.append(stem[:-2] + "ون")
        return out

    @staticmethod
    def _auto_past(stem):
        out = []
        if stem.endswith("اند") and len(stem) > 4:
            out.append(stem[:-3] + "وند")
        return out

    def _glides(self, stem):
        """What a stem is written as after a prefix: itself, and, where it begins with an alef, without it (میومد), with the glide
        a yeh makes (بیا, نیومد, می‌یاد) and both."""
        out = [stem]
        if stem and stem[0] in VOWELS:
            out += ["ی" + stem] + ([stem[1:], "ی" + stem[1:]] if len(stem) > 2 else [])   # a two-letter stem keeps its alef (ار is not ر)
        return out

    def _add(self, key, entry):
        self.base.setdefault(self.fold(key), []).append(entry)

    def _index(self, v):
        pre = v.flags.get("pre") or ""
        spoken_pre = {"بر": ["ور", "بر"], "در": ["در"], "باز": ["وا", "باز"], "فرا": ["فرا"], "فرو": ["فرو"]}.get(pre, [pre] if pre else [""])
        P, S = v.past, v.pres
        # the spoken present stems: the formal one, the table's, the sound change's
        listed = set([S, P] + v.sp_pres + v.sp_past)
        pres = list(dict.fromkeys([S] + v.sp_pres + self._auto_present(S)))
        past = list(dict.fromkeys([P] + v.sp_past + self._auto_past(P)))
        short = []                                   # the t of -st lost before an ending: خواسم, تونسی
        for p in past:
            if p.endswith(("ست", "شت", "فت")) and len(p) > 3:
                short.append(p[:-1])
        subj = v.formal.get("subj") or ("ب" + S)
        neg = v.formal.get("neg") or ("ن" + S)
        neg_past = v.formal.get("neg_past") or ("ن" + P)
        for sp_pre in spoken_pre:
            formal_pre = pre
            for s in pres:
                changed = s != S
                for g in self._glides(s):
                    for mi, mi_formal in (("می", "می" + ZW), ("نمی", "نمی" + ZW)):
                        self._add(sp_pre + mi + g, (v, "present", mi, formal_pre + mi_formal + S, s, changed, False, s not in listed))
                    # می- reduced to م- in chats (مخوام, نمدونم): a present with an ending, of a stem that does not begin with a vowel
                    if g[0] not in VOWELS and not sp_pre:
                        for reduced, mi_formal in (("م", "می" + ZW), ("نم", "نمی" + ZW)):
                            self._add(reduced + g, (v, "present", reduced, formal_pre + mi_formal + S, s, changed, False, True, "verb_mi_short"))
                    # the subjunctive and the imperative: ب-, formally written with the stem the tables give (بیا, بینداز, بنشین)
                    self._add(sp_pre + "ب" + g, (v, "subjunctive", "ب", formal_pre + subj if not pre else pre + S, s, changed, False, s not in listed))
                    # the ب- of the imperative written بی- or بو- (بیگیر, بوخور): a spelling of the same prefix, said with a vowel
                    for vowel in ("ی", "و") if len(g) > 1 else ():
                        self._add(sp_pre + "ب" + vowel + g, (v, "subjunctive", "ب", formal_pre + subj if not pre else pre + S, s, changed, False,
                                                             s not in listed, "verb_prefix_vowel"))
                    self._add(sp_pre + "ن" + g, (v, "negative", "ن", formal_pre + neg if not pre else pre + "ن" + S, s, changed, False, s not in listed))
                    self._add(sp_pre + g, (v, "bare", "", S, s, changed, False, s not in listed))
            for p in past + short:
                changed = p != P
                needs_ending = p in short
                for g in self._glides(p):
                    auto = p not in listed or needs_ending
                    self._add(sp_pre + g, (v, "past", "", formal_pre + P, p, changed, needs_ending, auto))
                    self._add(sp_pre + "ن" + g, (v, "negative past", "ن", formal_pre + neg_past if not pre else pre + "ن" + P, p, changed, needs_ending, auto))
                    for mi, mi_formal in (("می", "می" + ZW), ("نمی", "نمی" + ZW)):
                        self._add(sp_pre + mi + g, (v, "imperfect", mi, formal_pre + mi_formal + P, p, changed, needs_ending, auto))
        if v.flags.get("mi_stem"):
            self._add(v.flags["mi_stem"], (v, "present", "می", "می" + ZW + S, v.flags["mi_stem"], True, False, False))
        if v.flags.get("spoken_imp"):
            self.special.setdefault(self.fold(v.flags["spoken_imp"]), []).append((v.formal.get("imp") or ("ب" + S), v))
        # the spoken infinitive: a spoken past stem and a nun (اومدن, خوندن, رسوندن)
        for p in past:
            if p != P:
                self.infinitive.setdefault(self.fold(p + "ن"), []).append((v.inf, v, p))

    # ---------------------------------------------------------------------------------------------- the analysis
    def analyze(self, word):
        """Every formal string a spoken verb form can be, as VForm, best first.  `word` is as the text writes it."""
        key = self.fold(word)
        out, seen = [], set()

        def add(formal, why, v, kind, person, negative=False, auto=False):
            if formal and formal not in seen:
                seen.add(formal)
                out.append(VForm(formal, why, v, kind, person, negative, auto))
        for formal, v in self.special.get(key, []):
            add(formal, self._say("verb_stem", spoken=key, formal=formal), v, "imperative", "2s")
        for formal, v, p in self.infinitive.get(key, []):
            add(formal, self._say("verb_inf", spoken=key, formal=formal), v, "infinitive", "")
        pres_map, past_map, imp_map = dict(PRESENT_ENDINGS), dict(PAST_ENDINGS), dict(IMPERATIVE_ENDINGS)
        # (the endings of this kind of form, and what they make): a tense, an imperative, or a present written with no می-
        modes = {"present": [(pres_map, "tense")],
                 "subjunctive": [(pres_map, "tense"), (imp_map, "imperative")],
                 "negative": [(pres_map, "tense"), (imp_map, "imperative")],
                 "bare": [(imp_map, "imperative"), (pres_map, "bare present")],
                 "past": [(past_map, "tense")], "negative past": [(past_map, "tense")], "imperfect": [(past_map, "tense")]}
        for e in sorted({e for table in (pres_map, past_map, imp_map) for e in table}, key=len, reverse=True):
            fe = self.fold(e)
            if fe and not key.endswith(fe):
                continue
            stem_key = key[:len(key) - len(fe)] if fe else key
            for entry in self.base.get(stem_key, []):
                v, kind, prefix, formal_stem, spoken_stem, changed = entry[:6]
                if len(entry) > 6 and entry[6] and not e:
                    continue                  # the stem without its t only stands before an ending
                auto = len(entry) > 7 and entry[7]
                note = entry[8] if len(entry) > 8 else ""
                for table, mode in modes[kind]:
                    if e not in table:
                        continue
                    f = table[e]
                    if mode == "tense":
                        if kind in ("present", "subjunctive", "negative") and not e:
                            continue
                        plain = v.past if "past" in kind or kind == "imperfect" else v.pres
                        self._emit(add, v, kind, formal_stem + f, spoken_stem, changed, e, f, plain, auto, note)
                    elif mode == "bare present":
                        if not e:
                            continue
                        stem = v.pres if v.flags.get("bare") else "می" + ZW + v.pres
                        self._emit(add, v, "present", ("" if not v.flags.get("pre") else v.flags["pre"]) + stem + f, spoken_stem, changed, e, f, v.pres, True)
                    else:
                        self._imperative(add, v, kind, spoken_stem, changed, e, f, auto, note)
        # a past before a present written with no می-, the stem the table lists before one a rule made, a form with no ending first
        order = {"infinitive": 0, "past": 1, "negative past": 1, "imperfect": 2, "present": 3, "subjunctive": 3, "negative": 3, "imperative": 4}
        # an imperative singular (بشین) is the first thing such a form is said to be; then the tense, the singular before the rest
        out.sort(key=lambda x: (1 if x.auto else 0, 0 if (x.kind == "imperative" and x.person == "2s") else order.get(x.kind, 5),
                                0 if x.person in ("3s", "2s") else 1))
        return out

    def _emit(self, add, v, kind, formal, spoken_stem, changed, e, f, plain, auto=False, note=""):
        why = [self._say(note)] if note else []
        if changed:
            why.append(self._say("verb_stem", spoken=spoken_stem, formal=plain))
        if e != f:
            why.append(self._say("verb_ending", spoken=e or "∅", formal=f or "∅"))
        add(formal, "; ".join(why) or self._say("verb_plain"), v, kind, PERSON.get(e, ""), kind in ("negative", "negative past"), auto)

    def _imperative(self, add, v, kind, spoken_stem, changed, e, f, auto=False, note=""):
        """The imperative, singular and plural, with or without the ب- the spoken one drops (کن for بکن)."""
        S = v.pres
        pre = v.flags.get("pre") or ""
        if kind in ("subjunctive", "bare"):
            subj = v.formal.get("subj") or (pre + ("" if pre else "ب") + S)
            base = ([v.formal["imp"]] if v.formal.get("imp") and not f else []) + [subj]
            if S.endswith("وی") and not f:
                base.append(subj[:-1])
        else:
            neg = v.formal.get("neg") or (pre + "ن" + S)
            base = ([v.formal["negimp"]] if v.formal.get("negimp") and not f else []) + [neg]
            if S.endswith("وی") and not f:
                base.append(neg[:-1])
        why = [self._say(note)] if note else []
        if kind == "bare":
            why.append(self._say("verb_bare_imp"))
        if changed:
            why.append(self._say("verb_stem", spoken=spoken_stem, formal=S))
        if e != f:
            why.append(self._say("verb_ending", spoken=e or "∅", formal=f or "∅"))
        for b in base:
            add(b + f, "; ".join(why) or self._say("verb_plain"), v, "imperative", "2p" if f else "2s", kind == "negative", auto)

    def _say(self, key, **kw):
        return (self.text.get(key) or key).format(**kw)

    # ---------------------------------------------------------------------------------------- the perfect, collapsed
    def perfect(self, infinitive, person):
        """The present perfect of a verb, which speech says like its simple past (note C5): رفتن, 1s -> رفته‌ام."""
        participle = infinitive[:-1] + "ه" if infinitive.endswith("ن") else ""
        ending = {"1s": ZW + "ام", "2s": ZW + "ای", "3s": " است", "1p": ZW + "ایم", "2p": ZW + "اید", "3p": ZW + "اند"}.get(person)
        return participle + ending if participle and ending else ""
