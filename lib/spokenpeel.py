#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Layers 3 to 6 of the spoken pass: a word taken apart from the outside in, and read back as a formal one.

    peeler = spokenpeel.Peeler(rules)            # lib/spoken.py's Rules, which owns the tables
    peeler.read(lk, c, L, word, ctx, i)          # -> [Cand] of the word, or []

THE ORDER IS THE NOTE'S (TODOs/NOTE-fa-colloquial-normaliser.md, section 12): the endings that stand outside the
clitics come off first (the emphatic -ā, the vocative, the enclitic هم, the object marker), then the verb's clitic,
the copula or the verb's personal ending, then the pronominal clitics, then the definite -e and the plural.  A rule
takes one thing off the end of the word and says what it stands for in formal Persian; what is left is taken apart
by the rules DEEPER than it (a path never goes back up, so it cannot loop), until it is a word the dictionary has --
an entry, a form of one, a row of the word table.  Every path is checked against the dictionary at its end, with the
part of speech the rules on it ask for (a personal ending needs a verb form of that person, a plural a noun): that is
why the exceptions of the forward sound change need no list.

THE FORMAL ENDINGS ARE RULES TOO, and they compete.  The plural -hā, the clitics -m -t -sh on a word that ends in a
consonant, the ezafe and indefinite -i, the comparative, the copula -am -i -im: a path made of them says nothing, and
the old affix rules of the rule file answer for it.  But they are searched for beside the spoken ones, so that
`صدای` (the ezafe of `صدا`) is not read as `صد` and a plural, and `دستشان` not as `دسته` and a clitic: a spoken
reading is offered only if no formal one with as few rules comes to another entry.  Where the two come to the SAME
entry (مامانم: my mum, or mum too) the spoken one is kept only if it is of a kind that adds a reading (`adds`), and
the formal one stands beside it.

WHAT A PATH SAYS.  The formal word it comes to (`formal`), the formal pieces in the order of the reading (`parts`), the
pieces with no formal word of their own, named (`pieces`: the emphatic -ā, the redundant -sh, the definite -e), the
reasons in words (`whys`), the other readings of the same word (`alts`), and whether any of its rules (`by_rule`) or
only the table row it ends in (`spoken`) is spoken.

WHICH RULES SAY WHAT is data (lib/lang/<code>.lookup.json, `spoken.peel`); the code here is the grammar they share,
and it is about Persian's writing (what ends in a vowel, where a ZWNJ goes before an ending): a second language
brings its own copy of the same few functions.
"""
import re

ZW = "‌"
T_STAGES = {"emphatic": 30, "vocative": 30, "affection": 30, "hem": 31, "object": 32,
            "vclitic": 40, "copula": 41, "vend": 45, "clitic": 50, "definite": 60, "yeh": 61, "plural": 62, "comparative": 64}
PISH, KASRA = "ُ", "ِ"
COPULA_FORMAL = {"1s": "هستم", "2s": "هستی", "3s": "است", "1p": "هستیم", "2p": "هستید", "3p": "هستند"}
SPOKEN_ONLY_PERSONS = {"1s", "2s", "1p"}       # the copula of these is said of a person, so of an adjective, an adverb or a pronoun
MAX_CANDIDATES = 80


class Cand:
    """One path: where it ended, what it reads as, and what it passed through."""
    __slots__ = ("hits", "formal", "parts", "pieces", "whys", "spoken", "by_rule", "kind", "rules", "alts", "stem_pos", "adds", "bias", "twin",
                 "weight")

    def __init__(self, hits, formal, parts=None, pieces=None, whys=None, spoken=False, kind="rule", rules=(), alts=None,
                 by_rule=False, adds=False, bias=0, weight=0):
        self.hits, self.formal = hits, formal
        self.parts = list(parts if parts is not None else [formal])
        self.pieces = list(pieces or [])
        self.whys = list(whys or [])
        self.spoken, self.kind, self.rules = spoken, kind, tuple(rules)
        self.alts = list(alts or [])      # [(as, why)] other readings of the same word that lead to the same hits
        self.by_rule, self.adds, self.bias = by_rule, adds, bias
        self.weight = weight              # what its sound change costs (lib/spokensound.py): a regular one 1, a broad guess 2
        self.twin = False                 # a formal reading of the same word comes to the same entries
        self.stem_pos = {h.get("pos") for h in hits}

    def entries(self):
        return frozenset(h.get("entry") if h.get("entry") is not None else h.get("headword") for h in self.hits)

    def grow(self, rule_id, hits=None, formal=None, part=None, piece=None, why=None, spoken=False, alts=None, kind=None, adds=False,
             bias=0):
        c = Cand(hits if hits is not None else self.hits, formal if formal is not None else self.formal, self.parts, self.pieces,
                 self.whys, self.spoken or spoken, kind or self.kind, self.rules + (rule_id,), self.alts,
                 self.by_rule or spoken, self.adds or adds, self.bias + bias, self.weight)
        if part:
            c.parts.append(part)
        if piece:
            c.pieces.append(piece)
        if why:
            c.whys.append(why)
        if alts:
            c.alts.extend(alts)
        return c


class Peeler:
    def __init__(self, rules):
        self.R = rules
        self.cfg = rules.S.get("peel") or {}
        self.text = rules.text
        h = self.cfg.get("hosts") or {}
        self.min_stem = self.cfg.get("min_stem", 2)
        self.max_depth = self.cfg.get("max_depth", 3)
        self.nominal = set(self.cfg.get("nominal_pos") or [])
        self.plural_pos = set(self.cfg.get("plural_pos") or [])
        self._hosts = {k: None for k in ("adverbial", "quantifier", "kinship", "possessive_pron", "persons", "hem_words")}
        self._host_lists = h
        self._separate = None
        self.pronouns = self.cfg.get("pronouns") or {}
        self.clitics = self.cfg.get("clitics") or {}
        self.copula = self.cfg.get("copula") or {}

    # -------------------------------------------------------------------------------------------- small helpers
    def _say(self, key, **kw):
        return (self.text.get(key) or key).format(**kw)

    def _host(self, lk, L, kind, word):
        if self._hosts[kind] is None:
            self._hosts[kind] = {lk._fold(w, L) for w in self._host_lists.get(kind) or []}
        return lk._fold(word, L) in self._hosts[kind]

    def _is_separate(self, lk, L, word):
        if self._separate is None:
            self._separate = {lk._fold(w, L) for w in self._host_lists.get("separate_preps") or []}
        return lk._fold(word, L) in self._separate

    @staticmethod
    def _last(word):
        w = word.rstrip(ZW)
        return w[-1:] if w else ""

    def _klass(self, word):
        """The last sound of the word, as the copula and the clitics see it: he, alef, yeh, vav or a consonant."""
        ch = self._last(word)
        if ch == "ه":
            return "he"
        if ch in "اآ":
            return "alef"
        if ch == "ی":
            return "yeh"
        if ch == "و":
            return "vav"
        return "cons"

    def _join_clitic(self, formal, clitic):
        """A formal clitic on a formal word: what the formal spelling puts between them."""
        k = self._klass(formal)
        base = formal.rstrip(ZW)
        if k == "he":
            return base + ZW + {"م": "ام", "ت": "ات", "ش": "اش"}.get(clitic, clitic)
        if k in ("alef", "vav") and clitic in ("م", "ت", "ش"):
            return base + "ی" + clitic
        return base + clitic

    def _person_ok(self, hits, person):
        """Does a hit's note say this form is of this person?  A note that says nothing of person is no objection."""
        want = {"3s": ("third-person", "singular"), "2p": ("second-person", "plural"), "3p": ("third-person", "plural")}.get(person)
        if not want:
            return True
        for h in hits:
            tags = set(re.split(r"[ ,]+", h.get("note") or ""))
            if not tags & {"first-person", "second-person", "third-person"}:
                return True
            if set(want) <= tags:
                return True
        return False

    # ------------------------------------------------------------------------------------------------ terminals
    def _terminal(self, lk, c, L, stem, cache, inner=True, plain=False):
        """The paths that END at this string: it is an entry or a form of one, the dictionary's own colloquial page,
        a row of the word table, a stem the peel names (چ for چه), or two number words written together.  `inner` is
        false for the whole word, which is not taken for a stem of its own."""
        if (stem, inner, plain) in cache:
            return cache[(stem, inner, plain)]
        R = self.R
        out = []
        key = lk._fold(stem, L)
        if key and plain:
            out = [Cand(hits, stem) for hits in [[h for h in lk._hits_for(c, key) if h.get("_tier", 0) <= lk.T_FORM]] if hits]
        elif key:
            hits = [h for h in lk._hits_for(c, key) if h.get("_tier", 0) <= lk.T_FORM]
            if hits:
                own = R._own(lk, c, L, hits)
                if own:
                    # the dictionary's own colloquial page: what it points at stands for it (کوچیک is کوچک)
                    out.append(Cand(own[0].hits, own[0].hits[0]["spoken"]["as"], spoken=True, kind="entry",
                                    whys=[own[0].hits[0]["spoken"]["why"]]))
                else:
                    out.append(Cand(hits, stem))
            if inner and key in {lk._fold(k, L) for k in (self.cfg.get("stems") or {})}:
                for spoken, formal in (self.cfg.get("stems") or {}).items():
                    if lk._fold(spoken, L) == key:
                        got = R._formal_hits(lk, c, L, formal)
                        if got:
                            out.append(Cand(got[:4], formal, whys=[self._say("table", formal=formal)], spoken=True, kind="table"))
            for row in R.words.get(key, []):
                if row.kind in ("standalone", "cv", "policy"):
                    continue
                got = R._formal_hits(lk, c, L, row.formal)
                if got:
                    why = row.note or self._say("table", formal=row.formal)
                    out.append(Cand(got[:4], row.formal, parts=row.formal.split() if len(got) > 1 else [row.formal],
                                    whys=[why], spoken=True, kind="table"))
            for vf, vhits in R.verb_readings(lk, c, L, stem):
                # a form the table's own stems make comes before one a rule of the table made; a verb after a noun with a clitic
                out.append(Cand(vhits[:4], vf.formal, whys=[vf.why], spoken=True, kind="rule", rules=("verb",), by_rule=True,
                                bias=2 if vf.auto else 1, weight=3 if vf.auto else 0))
            # a sound change speech writes down (note B), read one step back: for a stem nothing else reads, and for the whole
            # word of a trap's row (خون is blood, and خان said with the u of the spoken language)
            # (a word the dictionary has is not asked for its spellings by ear: only a stem nothing else reads is; a verb form the
            # table only guessed at -- خاب as بخواب -- is no reading of its own, so the spelling by ear is asked beside it)
            guessed = not any(x.rules != ("verb",) for x in out)
            if R.sounds and (guessed or (cache.get("__trap__") and not inner)):
                out.extend(self._sound(lk, c, L, stem, cache, stages=(9,) if out and guessed else (8, 9) if not out else (8,)))
            if not out:
                numbers = R._glue(lk, c, L, stem, stem, 0, only="numbers")
                if numbers:
                    sp = numbers[0].hits[0]["spoken"]
                    out.append(Cand(numbers[0].hits, sp["as"], parts=sp.get("parts") or [sp["as"]], whys=[sp["why"]], spoken=True,
                                    kind="glue"))
        cache[(stem, inner, plain)] = out
        return out

    def _sound(self, lk, c, L, stem, cache, stages=(8, 9)):
        """The paths that END at a stem the sound changes of speech hide (lib/spokensound.py): every word a rule makes of it that the
        dictionary has -- as an entry, a form of one, or an entry with the plural ending of animate nouns (آقایان is آقا + -ān)."""
        sounds = self.R.sounds
        if len(stem.replace(ZW, "")) < self.min_stem:
            return []
        if ("sound", stem, stages) in cache:
            return cache[("sound", stem, stages)]
        out = []
        for stage in stages:
            # the spellings by ear (9) are asked only of a stem the sound changes (8) found nothing for
            out = self._sound_stage(lk, c, L, stem, stage)
            if out:
                break
        cache[("sound", stem, stages)] = out
        return out

    def _sound_stage(self, lk, c, L, stem, stage):
        sounds = self.R.sounds
        folded = [(lk._fold(v, L), v, r) for v, r in sounds.raw(stem, stage)]
        bases = {}
        for fk, v, _r in folded:
            for tail in sounds.tails:
                if v.endswith(tail) and len(v.replace(ZW, "")) - len(tail) >= self.min_stem:
                    bases.setdefault(fk, lk._fold(v[:-len(tail)], L))
                    break
        known = self.R._known(lk, c, list({fk for fk, _v, _r in folded} | set(bases.values())))
        out = []
        for fk, v, r in folded:
            hits = [h for h in lk._hits_for(c, fk) if h.get("_tier", 0) <= lk.T_FORM] if fk in known else []
            if not hits and bases.get(fk) in known:
                hits = [h for h in lk._hits_for(c, bases[fk]) if h.get("_tier", 0) <= lk.T_FORM and h.get("pos") in self.nominal]
            if hits:
                out.append(Cand(hits[:4], v, whys=[self._say("sound", formal=v, note=r.note)], spoken=True, kind="rule",
                                rules=("sound",), by_rule=True, bias=2, weight=r.cost))
            if len(out) >= sounds.max_known:
                break
        return out

    # ---------------------------------------------------------------------------------------------- the search
    def _peel(self, lk, c, L, w, after, depth, path, cache, ctx, i):
        """The candidates for `w` as a stem and the endings deeper than stage `after`."""
        out = list(self._terminal(lk, c, L, w, cache, inner=depth > 0))
        if depth >= self.max_depth or len(w) < 2:
            return out
        for stage, gen in self._generators():
            if stage <= after:
                continue
            for item in gen(lk, c, L, w, path, ctx, i):
                stem, finish, rid = item[:3]
                ends_here = len(item) > 3 and item[3]
                if len(stem.rstrip(ZW)) < self.min_stem and stem not in (self.cfg.get("stems") or {}):
                    continue
                inners = (self._terminal(lk, c, L, stem, cache, plain=len(item) > 4 and item[4]) if ends_here else
                          self._peel(lk, c, L, stem, stage, depth + 1, path + (rid,), cache, ctx, i))
                for inner in inners:
                    got = finish(inner)
                    if got:
                        out.append(got)
                        if len(out) > MAX_CANDIDATES:
                            return out
        return out

    def _generators(self):
        return ((T_STAGES["emphatic"], self._g_emphatic), (T_STAGES["vocative"], self._g_vocative),
                (T_STAGES["affection"], self._g_affection), (T_STAGES["hem"], self._g_hem),
                (T_STAGES["object"], self._g_object), (T_STAGES["vclitic"], self._g_vclitic),
                (T_STAGES["copula"], self._g_copula), (T_STAGES["vend"], self._g_vend),
                (T_STAGES["clitic"], self._g_clitic), (T_STAGES["clitic"], self._g_contracted), (T_STAGES["definite"], self._g_definite),
                (T_STAGES["yeh"], self._g_yeh), (T_STAGES["plural"], self._g_plural),
                (T_STAGES["comparative"], self._g_comparative))

    def _ends(self, w, suffixes):
        short = set(self.cfg.get("stems") or {})
        for s in sorted(suffixes, key=len, reverse=True):
            if w.endswith(s) and (len(w) - len(s) >= self.min_stem or w[:len(w) - len(s)] in short):
                yield s, w[:len(w) - len(s)].rstrip(ZW)

    @staticmethod
    def _keep(cand, pos):
        """The candidate with only the hits of these parts of speech, or None when none is."""
        if cand.kind == "glue":
            return cand                  # two words written together: its hits are each of its words, and all of them stay
        hits = [h for h in cand.hits if h.get("pos") in pos]
        if not hits:
            return None
        if len(hits) == len(cand.hits):
            return cand
        return Cand(hits, cand.formal, cand.parts, cand.pieces, cand.whys, cand.spoken, cand.kind, cand.rules, cand.alts,
                    cand.by_rule, cand.adds, cand.bias, cand.weight)

    def _verbal(self, cand):
        return self._keep(cand, {"verb"})

    def _nominal(self, cand):
        return self._keep(cand, self.nominal)

    # ------------------------------------------------------------------------------------------- the outer layer
    def _g_emphatic(self, lk, c, L, w, path, ctx, i):
        """-ā (and -hā) on the end of a verb: it says nothing a formal word says, and is named."""
        for s, rest in self._ends(w, self.cfg.get("emphatic") or []):
            if len(rest) < 3:
                continue

            def finish(inner, s=s):
                v = self._verbal(inner)
                if not v:
                    return None
                piece = {"text": s, "role": "emphatic", "note": self._say("emphatic")}
                return v.grow("emphatic", piece=piece, why=self._say("emphatic"), spoken=True)
            yield rest, finish, "emphatic"

    def _g_vocative(self, lk, c, L, w, path, ctx, i):
        s = self.cfg.get("vocative")
        if s and w.endswith(s) and len(w) - len(s) >= self.min_stem and self._klass(w[:-len(s)]) == "alef":
            def finish(inner):
                n = self._keep(inner, {"noun", "name", "pron"})
                if not n:
                    return None
                piece = {"text": s, "role": "vocative", "note": self._say("vocative")}
                return n.grow("vocative", formal=n.formal + s, piece=piece, why=self._say("vocative"), spoken=True)
            yield w[:-len(s)], finish, "vocative"

    def _g_affection(self, lk, c, L, w, path, ctx, i):
        for s, rest in self._ends(w, self.cfg.get("affection") or []):
            def finish(inner, s=s):
                n = self._keep(inner, {"noun", "name"})
                if not n:
                    return None
                piece = {"text": s, "role": "affection", "note": self._say("affection")}
                return n.grow("affection", piece=piece, why=self._say("affection"), spoken=True)
            yield rest, finish, "affection"

    def _next_pos(self, lk, c, L, ctx, i):
        """The parts of speech of the word after this one in the chunk (what a letter that has two readings is read by)."""
        if ctx is None or i is None or i + 1 >= len(ctx.raw):
            return set()
        word = lk._bare(ctx.raw[i + 1], L)
        entries = lk._resolve(c, word, [], L, False)
        pos = {h.get("pos") for e in entries for h in e.get("hits") or []}
        piece = self.R._piece(lk, c, L, word, loose=True)
        return pos | ({piece[0].get("pos")} if piece else set())

    def _g_hem(self, lk, c, L, w, path, ctx, i):
        """The enclitic -m that is هم (also), beside the two other things the same letter is: I am, and my."""
        for s, rest in self._ends(w, ["ام", "م"]):
            if s == "ام" and self._klass(rest) == "cons":
                continue

            def finish(inner, s=s):
                n = self._nominal(inner)
                if not n:
                    return None
                only = n.stem_pos & {"noun", "name", "adj"} and not (n.stem_pos & {"pron", "adv", "num", "det", "intj"})
                if self._host(lk, L, "hem_words", n.formal):
                    only = False          # باز, هنوز, الان, فردا, اگر: the words the note lists, whatever the dictionary files them under
                elif "clitic" not in inner.rules:
                    if n.stem_pos & {"pron"} and self._host(lk, L, "possessive_pron", n.formal):
                        return None       # خودم is `myself`: a pronoun that takes a clitic of its own, and the -m is that
                    if only and not self._host(lk, L, "persons", n.formal):
                        return None       # باورم is `my belief`: only a word for a person is also `I am` and `too`
                else:
                    only = False          # خودمم: the clitic is there already, so the last -m is not a possessive
                if only and not (ctx and ctx.evidence(i)):
                    return None           # مامانم is `my mum` until something says the page is speech
                base = n.formal
                alts = [(base + " هم", self._say("hem")),
                        (base + " " + COPULA_FORMAL["1s"], self._say("hem_be", base=base, copula=COPULA_FORMAL["1s"]))]
                if n.stem_pos & {"noun", "name"}:
                    alts.append((base + "م", self._say("hem_my", base=base)))
                return n.grow("hem", formal=base + " هم", part="هم", why=self._say("hem"), spoken=True, alts=alts, adds=True)
            yield rest, finish, "hem"

    def _g_object(self, lk, c, L, w, path, ctx, i):
        """-o: the object marker را (and, said the same, و); -ro after a word that ends in a vowel."""
        cfg = self.cfg.get("object") or {}
        for s, rest in self._ends(w, cfg.get("suffixes") or []):
            def finish(inner, s=s):
                n = self._keep(inner, {"noun", "pron", "name", "num", "det"})
                if not n:
                    return None
                piece = {"text": s, "role": "object", "note": self._say("object")}
                if s == "و":
                    nxt = self._next_pos(lk, c, L, ctx, i)
                    if nxt & {"noun", "pron", "name"} and not nxt & {"verb"}:
                        # a noun or a pronoun after it favours `and`
                        return n.grow("object", formal=n.formal + " و", part="و", why=self._say("and"), spoken=True,
                                      alts=[(n.formal + " را", self._say("object"))], adds=True)
                    alts = [(n.formal + " و", self._say("and"))]
                else:
                    alts = []
                return n.grow("object", formal=n.formal + " را", part="را", piece=piece, why=self._say("object"), spoken=True,
                              alts=alts, adds=bool(alts))
            yield rest, finish, "object"

    # -------------------------------------------------------------------------------------------- the verb's own
    def _g_vclitic(self, lk, c, L, w, path, ctx, i):
        """A clitic on a verb: the object (-am -at -ash, and the spoken -emun -etun -eshun), and the redundant -sh."""
        spoken = list(self.clitics.get("spoken_plural") or [])
        formal = list(self.clitics.get("formal") or [])
        fo = self.clitics.get("formal_of") or {}
        for s, rest in self._ends(w, spoken + formal):
            def finish(inner, s=s):
                v = self._verbal(inner)
                if not v:
                    return None
                is_spoken = s in spoken
                base = fo.get(s, s)
                tags = [set(re.split(r"[ ,]+", h.get("note") or "")) for h in v.hits]
                third = [h for t, h in zip(tags, v.hits)
                         if {"third-person", "singular"} <= t and ("past" in t or h.get("headword") == "بودن")]
                form = v.formal + base
                if s == "ش" and third:
                    # a verb of the third person with -sh: its subject said again, or its object
                    piece = {"text": s, "role": "redundant", "note": self._say("redundant")}
                    return v.grow("vclitic", hits=third, formal=v.formal, piece=piece, why=self._say("redundant"), spoken=True,
                                  alts=[(form, self._say("clitic_spoken", ending=s, formal=base))], adds=True)
                why = self._say("clitic_spoken", ending=s, formal=base)
                return v.grow("vclitic", formal=form, part=base,
                              piece={"text": s, "role": "clitic", "note": why} if is_spoken else None,
                              why=why if is_spoken else None, spoken=is_spoken)
            yield rest, finish, "vclitic"

    def _g_vend(self, lk, c, L, w, path, ctx, i):
        """The spoken personal ending -e -in -an for the formal -ad -id -and, on a form the dictionary has."""
        pairs = [list(p) for p in self.cfg.get("verb_endings") or []]
        if "vclitic" in path:
            pairs.append(["ت", "د"])          # the 3rd person's -e is -t before a clitic: میبینتش
        tags = self.cfg.get("person_tags") or {}
        for s, add in pairs:
            if not w.endswith(s) or len(w) - len(s) < self.min_stem + 1:
                continue
            form = w[:len(w) - len(s)] + add

            def finish(inner, s=s, add=add, form=form):
                v = self._verbal(inner)
                if not v or not self._person_ok(v.hits, tags.get(s)):
                    return None
                piece = {"text": s, "role": "ending", "note": self._say("vending", ending=s, formal=add)}
                return v.grow("vend", formal=form, piece=piece, why=self._say("vending", ending=s, formal=add), spoken=True, bias=3)
            # the formal form is the whole word that is looked up: nothing is left to take apart beneath it
            yield form, finish, "vend", True, True

    # ---------------------------------------------------------------------------------------------- the copula
    def _g_copula(self, lk, c, L, w, path, ctx, i):
        """The spoken copula on a word that is not a verb (خوبه, خوبین, خسته‌م, اینجاس, عالیه, چیه), and the formal one
        (خوبم, خسته‌ام), which says nothing but is searched for beside it."""
        for klass in ("cons", "he", "alef", "yeh"):
            table = self.copula.get({"cons": "consonant", "he": "he", "alef": "alef", "yeh": "yeh"}[klass]) or {}
            for s, rest in self._ends(w, list(table)):
                if self._klass(rest) != klass:
                    continue
                person = table[s]

                def finish(inner, s=s, person=person):
                    n = self._keep(inner, self.nominal - {"name"})        # a name and a copula is a coincidence of letters (نامه)
                    if not n:
                        return None
                    if person in SPOKEN_ONLY_PERSONS and not (n.stem_pos & {"adj", "adv", "pron", "num", "det"}):
                        return None
                    formal = n.formal + " " + COPULA_FORMAL[person]
                    piece = {"text": s, "role": "copula", "note": self._say("copula", ending=s, formal=COPULA_FORMAL[person])}
                    bias = 0
                    if s == "ه" and klass == "cons" and self._definite_likelier(lk, c, L, ctx, i, n):
                        bias = 1
                    return n.grow("copula", formal=formal, part=COPULA_FORMAL[person], piece=piece,
                                  why=self._say("copula", ending=s, formal=COPULA_FORMAL[person]), spoken=True, bias=bias)
                yield rest, finish, "copula"
        # the same copula on a word whose final -e is not written (خونس is خونه‌س): the stem is asked with its -e put back
        for s, rest in self._ends(w, list(self.copula.get("he") or {})):
            if self._klass(rest) != "cons":
                continue
            person = self.copula["he"][s]

            def finish_restored(inner, s=s, person=person):
                n = self._keep(inner, self.nominal - {"name"})
                if not n or (person in SPOKEN_ONLY_PERSONS and not (n.stem_pos & {"adj", "adv", "pron", "num", "det"})):
                    return None
                piece = {"text": s, "role": "copula", "note": self._say("copula", ending=s, formal=COPULA_FORMAL[person])}
                why = self._say("copula", ending=s, formal=COPULA_FORMAL[person]) + "; " + self._say("restored", stem=n.formal)
                return n.grow("copula", formal=n.formal + " " + COPULA_FORMAL[person], part=COPULA_FORMAL[person], piece=piece, why=why,
                              spoken=True, bias=1)
            yield rest + "ه", finish_restored, "copula", True
        formal_sets = self.cfg.get("copula_formal") or {}
        for s, rest in self._ends(w, list(formal_sets.get("cons") or []) + list(formal_sets.get("vowel") or [])):
            allowed = formal_sets.get("cons") if self._klass(rest) == "cons" else formal_sets.get("vowel")
            if s not in (allowed or []):
                continue

            def finish_f(inner, s=s):
                n = self._keep(inner, self.nominal | ({"prep"} if "clitic" in inner.rules else set()))
                if not n:
                    return None
                if "clitic" in inner.rules:
                    # the copula straight on a clitic (عاشقتم) is not the formal one: it stands apart there
                    why = self._say("copula_after_clitic", formal=COPULA_FORMAL.get({"م": "1s", "ی": "2s", "یم": "1p", "ید": "2p",
                                                                                     "ند": "3p"}.get(s.lstrip("ا"), "1s"), s))
                    piece = {"text": s, "role": "copula", "note": why}
                    return n.grow("copula", formal=n.formal + " " + s, part=s, piece=piece, why=why, spoken=True)
                joined = n.formal.rstrip(ZW) + (ZW if self._klass(n.formal) == "he" and s.startswith("ا") else "") + s
                pronoun = {"م": "من", "ام": "من", "ی": "تو", "ای": "تو", "یم": "ما", "ایم": "ما", "ید": "شما", "اید": "شما",
                           "ند": "آن‌ها", "اند": "آن‌ها"}.get(s, "")
                return n.grow("copula_f", formal=(pronoun + " " if pronoun else "") + joined, part=s)
            yield rest, finish_f, "copula"

    # -------------------------------------------------------------------------------------- clitics on a noun
    def _g_clitic(self, lk, c, L, w, path, ctx, i):
        """A possessive or object clitic on a word that is not a verb: the spoken -mun -tun -shun, the bare -m -t -sh after
        a vowel, on a word that formally takes none (بعدش, نصفش), on a preposition (بهت, برام, باهاش), and a final -e
        that was not written before it (بچم)."""
        spoken_pl = list(self.clitics.get("spoken_plural") or [])
        formal = list(self.clitics.get("formal") or [])
        buffered = list(self.clitics.get("spoken_buffered") or [])
        fo = self.clitics.get("formal_of") or {}
        bare = ("م", "ت", "ش")
        # the formal clitic with the letters the formal spelling puts between it and a word that ends in a vowel (پایش, خانه‌اش): they
        # are searched for beside the bare ones, which are spoken, so that a formal word is not read as a spoken one
        formal_buffered = {"یم": "م", "یت": "ت", "یش": "ش", "ام": "م", "ات": "ت", "اش": "ش"}
        for s, rest in self._ends(w, list(formal_buffered)):
            k = self._klass(rest)
            if (s[0] == "ی" and k in ("alef", "vav")) or (s[0] == "ا" and k == "he"):
                def finish_buffered(inner, s=s):
                    n = self._nominal(inner)
                    return n.grow("clitic", formal=self._join_clitic(n.formal, formal_buffered[s]), part=formal_buffered[s]) if n else None
                yield rest, finish_buffered, "clitic"
        for s, rest in self._ends(w, spoken_pl + buffered + formal):
            for restore in ("", "ه", "ی"):
                # a final -e or -i that is not written is a thing the BARE and the spoken clitics do (بچم, روش): never the formal -mān
                if restore and not (s in bare or s in spoken_pl or s in buffered):
                    continue
                stem = rest + restore

                def finish(inner, s=s, restore=restore, rest=rest):
                    n = self._nominal(inner) or self._keep(inner, {"prep"})
                    if not n:
                        return None
                    prep = "prep" in n.stem_pos
                    is_buffered = s in buffered
                    if is_buffered and not prep:
                        return None
                    base = fo.get(s, s)
                    head = n.formal
                    spoken = False
                    why = None
                    k = self._klass(rest)
                    if s in spoken_pl or is_buffered:
                        spoken, why = True, self._say("clitic_spoken", ending=s, formal=base)
                    elif restore == "ه":
                        spoken, why = True, self._say("restored", stem=head)
                    elif restore == "ی":
                        if not prep:
                            return None
                        spoken, why = True, self._say("restored", stem=head)
                    elif s in bare and k in ("alef", "vav", "he"):
                        spoken = True
                        why = self._say("clitic_bare", ending=s, buffer="ی" if k in ("alef", "vav") else ZW + "ا")
                    elif s in bare and (prep or self._host(lk, L, "adverbial", head) or self._host(lk, L, "quantifier", head)):
                        spoken, why = True, self._say("clitic_host", ending=s, host=head, formal=base)
                    pron = self.pronouns.get(base, "") or self.pronouns.get(s, "")
                    if prep and (self._is_separate(lk, L, head) or is_buffered):
                        formal_text, part = head + " " + pron, pron
                    else:
                        formal_text, part = self._join_clitic(head, base), base
                    piece = {"text": s, "role": "clitic", "note": why or ""} if spoken else None
                    # a spoken-only word with its -e put back (خونه) before the dictionary's stem without it (خون, blood)
                    return n.grow("clitic", formal=formal_text, part=part, piece=piece, why=why, spoken=spoken,
                                  bias=-1 if restore == "ه" and n.kind == "table" else 0 if prep else 1)
                yield stem, finish, "clitic", bool(restore)

    def _g_contracted(self, lk, c, L, w, path, ctx, i):
        """After a word that ends in -e, `ام` is also the plural and the clitic said together: بچه‌ام = بچه‌هایم."""
        for s in ("ام", "ات", "اش"):
            if w.endswith(ZW + s) and len(w) - len(s) - 1 >= 3:
                rest = w[:len(w) - len(s) - 1]
                if self._klass(rest) != "he":
                    continue

                def finish(inner, s=s):
                    n = self._keep(inner, {"noun", "name"})
                    if not n or not (ctx and ctx.evidence(i)):
                        return None
                    clitic = {"ام": "م", "ات": "ت", "اش": "ش"}[s]
                    why = self._say("plural_contracted", ending=s)
                    piece = {"text": s, "role": "clitic", "note": why}
                    return n.grow("clitic", formal=n.formal + ZW + "ها" + "ی" + clitic, part="ها" + "ی" + clitic, piece=piece, why=why,
                                  spoken=True, adds=True)
                yield rest, finish, "clitic"

    # ---------------------------------------------------------------------------------------- the noun itself
    def _g_definite(self, lk, c, L, w, path, ctx, i):
        """-e: the definite (پسره: that boy), the ezafe written out (کتابه من), beside the copula the same letter is."""
        s = self.cfg.get("definite")
        if not s or not w.endswith(s) or len(w) - len(s) < 3:
            return
        rest = w[:-len(s)].rstrip(ZW)

        def finish(inner):
            n = self._keep(inner, {"noun", "adj", "pron", "num"})         # a name takes no definite (نام + ه is not نامه)
            if not n or "copula" in path:
                return None
            nxt = self._next_pos(lk, c, L, ctx, i)
            definite = ("definite", self._say("definite", formal=n.formal))
            ezafe = ("ezafe", self._say("ezafe"))
            first = ezafe if (nxt & {"noun", "pron", "name", "num"} and not (nxt & {"verb", "adj"})
                              and not self._object_marker_next(lk, L, ctx, i)) else definite
            other = definite if first is ezafe else ezafe
            piece = {"text": s, "role": first[0], "note": first[1]}
            return n.grow("definite", formal=n.formal + (ZW + "ی" if first is ezafe else ""), piece=piece, why=first[1], spoken=True,
                          alts=[(n.formal, other[1])], adds=True,
                          bias=0 if self._definite_likelier(lk, c, L, ctx, i, n) else 1)
        yield rest, finish, "definite"

    def _object_marker_next(self, lk, L, ctx, i):
        return (ctx is not None and i is not None and i + 1 < len(ctx.raw)
                and lk._fold(lk._bare(ctx.raw[i + 1], L), L) in ("رو", "را"))

    def _definite_likelier(self, lk, c, L, ctx, i, stem):
        """-e after a word: the definite or the ezafe rather than the copula?  When the object marker follows it, yes
        (بزرگه رو بده); when a noun or a pronoun follows it, yes (خوده خدا); a noun is, unless it stands at the end of the
        clause; an adjective or a pronoun at the end of it is the copula."""
        if self._object_marker_next(lk, L, ctx, i):
            return True
        nxt = self._next_pos(lk, c, L, ctx, i)
        if nxt & {"noun", "pron", "name", "num"} and not (nxt & {"verb", "adj"}):
            return True
        if stem.stem_pos & {"noun", "name"}:
            return bool(nxt)
        return False

    def _g_yeh(self, lk, c, L, w, path, ctx, i):
        """The formal ezafe or indefinite -i: it says nothing, and is searched for so that صدای stays صدا."""
        if w.endswith("ی") and len(w) - 1 >= self.min_stem:
            def finish(inner):
                n = self._nominal(inner)
                return n.grow("yeh", formal=n.formal + "ی", part="ی") if n else None
            yield w[:-1].rstrip(ZW), finish, "yeh"

    def _g_comparative(self, lk, c, L, w, path, ctx, i):
        for s, rest in self._ends(w, self.cfg.get("comparative_formal") or []):
            def finish(inner, s=s):
                n = self._keep(inner, {"adj", "adv"})
                return n.grow("comparative", formal=n.formal + ZW + s, part=s) if n else None
            yield rest, finish, "comparative"

    def _g_plural(self, lk, c, L, w, path, ctx, i):
        """The spoken plural -ā for -hā (کتابا, بچا, صندلیا), with the ezafe (کتابای), with the indefinite (چیزایی); the
        formal -hā beside it; the affective -i and the manner -ki."""
        for s, rest in self._ends(w, self.cfg.get("plural_formal") or []):
            def finish_f(inner, s=s):
                n = self._keep(inner, self.plural_pos)
                return n.grow("plural_f", formal=n.formal + ZW + s, part=s) if n else None
            yield rest, finish_f, "plural"
        for s in self.cfg.get("indefinite") or []:
            if w.endswith(s) and len(w) - len(s) >= 3:
                rest = w[:-len(s)]
                if s == "یی" and not rest.endswith("ا"):
                    continue
                stem = rest[:-1] if s == "یی" else rest

                def finish_ind(inner, s=s):
                    n = self._keep(inner, self.plural_pos - {"num"})
                    if not n:
                        return None
                    return n.grow("plural", formal=n.formal + ZW + "هایی", part="هایی", why=self._say("indefinite"),
                                  piece={"text": s, "role": "plural", "note": self._say("indefinite")}, spoken=True)
                yield stem.rstrip(ZW), finish_ind, "plural"
        for s in (self.cfg.get("plural_ezafe") or []) + (self.cfg.get("plural") or []):
            if not w.endswith(s) or len(w) - len(s) < 3:
                continue
            rest = w[:len(w) - len(s)].rstrip(ZW)
            for restore in ("", "ه"):
                def finish(inner, s=s, restore=restore):
                    n = self._keep(inner, self.plural_pos - {"num"})
                    if not n:
                        return None
                    suffix = ZW + "های" if s == "ای" else ZW + "ها"
                    why = self._say("plural")
                    if restore:
                        why += "; " + self._say("restored", stem=n.formal)
                    piece = {"text": s, "role": "plural", "note": self._say("plural")}
                    return n.grow("plural", formal=n.formal + suffix, part="های" if s == "ای" else "ها", why=why, piece=piece, spoken=True,
                                  bias=-1 if restore and n.kind == "table" else 0)
                yield rest + restore, finish, "plural", bool(restore)
        for s in self.cfg.get("manner_ki") or []:
            if w.endswith(s) and len(w) - len(s) >= 3:
                def finish_ki(inner, s=s):
                    n = self._keep(inner, {"adj", "adv"})
                    if not n:
                        return None
                    piece = {"text": s, "role": "manner", "note": self._say("manner_ki")}
                    return n.grow("plural", piece=piece, why=self._say("manner_ki"), spoken=True)
                yield w[:-len(s)], finish_ki, "plural"
        for s in self.cfg.get("affective") or []:
            if w.endswith(s) and len(w) - len(s) >= 3:
                def finish_i(inner, s=s):
                    n = self._keep(inner, {"noun", "name"})
                    if not n or not self._host(lk, L, "kinship", n.formal):
                        return None
                    piece = {"text": s, "role": "affective", "note": self._say("affective")}
                    return n.grow("plural", piece=piece, why=self._say("affective"), spoken=True, adds=True)
                yield w[:-len(s)], finish_i, "plural"

    def stem_piece(self, lk, c, L, text, ctx=None, i=None):
        """A word that may carry a clitic or a plural, as a piece of a word written together (بنظرم is به + نظرم): (hit, formal) or None."""
        cache = {}
        for cand in self._peel(lk, c, L, text, T_STAGES["clitic"] - 1, 1, ("clitic_piece",), cache, ctx, i):
            # a noun (or an adjective) of the dictionary's own, with a clitic and nothing else on it: no table word, no pronoun
            if cand.hits and cand.rules == ("clitic",) and cand.kind != "table" and not cand.stem_pos & {"pron", "adv", "prep"}:
                return cand.hits[0], cand.formal
        return None

    # --------------------------------------------------------------------------- what a single mark says
    def read_marks(self, lk, c, L, w, ctx, i):
        """A pish alone on the last letter is the object marker (کتابُ), a zir alone the copula where no word follows to take
        an ezafe (منِ): the marks are evidence, and for these they are the whole rule.  `w` still has its marks."""
        out = []
        cache = {}
        if w.endswith(PISH):
            for inner in self._terminal(lk, c, L, lk._unmarked(w[:-1], L), cache):
                n = self._nominal(inner)
                if n:
                    piece = {"text": PISH, "role": "object", "note": self._say("pish")}
                    out.append(n.grow("pish", formal=n.formal + " را", part="را", piece=piece, why=self._say("pish"), spoken=True))
        elif w.endswith(KASRA):
            if not (self._next_pos(lk, c, L, ctx, i) & self.nominal):
                for inner in self._terminal(lk, c, L, lk._unmarked(w[:-1], L), cache):
                    n = self._keep(inner, {"pron", "noun", "adj", "name"})
                    if n:
                        piece = {"text": KASRA, "role": "copula", "note": self._say("zir")}
                        out.append(n.grow("zir", formal=n.formal + " " + COPULA_FORMAL["3s"], part=COPULA_FORMAL["3s"], piece=piece,
                                          why=self._say("zir"), spoken=True))
        return out

    # ------------------------------------------------------------------------------------------- the entry point
    @staticmethod
    def cost(cand):
        """How many rewrites a path rests on, to rank the spoken readings of a word: each rule one, a sound change its own cost."""
        return len([r for r in cand.rules if r != "sound"]) + cand.weight

    @staticmethod
    def rules_against(cand):
        """The same, to weigh a spoken reading against a formal one: a sound change counts half (the dictionary decides it)."""
        return len([r for r in cand.rules if r != "sound"]) + (0.5 if "sound" in cand.rules else 0)

    def read(self, lk, c, L, w, ctx, i, with_formal=False, direct=()):
        """The spoken readings of this word as Candidates, best first, or [].  With `with_formal` (a trap's row) the formal
        readings that come to the same entries are added to each one's other readings, so that every reading of the letter is shown.
        `direct` are the entries the dictionary's own answer for the word already has: a trap's row adds nothing by a reading that
        only spells the same entry another way."""
        cands = [x for x in self._peel(lk, c, L, w, 0, 0, (), {"__trap__": with_formal}, ctx, i) if x.rules]
        spoken = [x for x in cands if x.spoken]
        if not spoken:
            return []
        formal = [x for x in cands if not x.spoken]
        if formal and not with_formal:
            best = min(formal, key=self.rules_against)
            same = best.entries()
            # a formal reading of as few rules, to another entry, is the reading; to the same entry, it stands beside a
            # spoken one that adds readings (مامانم) and the spoken one that only explains is not needed
            spoken = [x for x in spoken if self.rules_against(x) < self.rules_against(best) or (x.entries() == same and x.adds)]
            # a path through a sound change that comes to the entry the formal reading already comes to is a formal word taken
            # apart and put together again (خسته‌ام is not خست + -e + a sound that gives the -e back)
            spoken = [x for x in spoken if "sound" not in x.rules or x.entries() != same]
            if not spoken:
                return []
        spoken.sort(key=lambda x: (self.cost(x), 0 if self.rules_against(x) == 0.5 else 1, 0 if x.by_rule else 1, x.bias,
                                   0 if "verb" in x.stem_pos else 1, 0 if x.kind in ("rule", "entry") else 1))
        if with_formal:
            if direct:
                spoken = [x for x in spoken if not (x.rules == ("sound",) and x.entries() <= direct)]
            have = set()
            for x in spoken:
                have |= x.entries()
                for f in formal:
                    if f.entries() == x.entries():
                        x.twin = True
                        if f.formal != x.formal:
                            x.alts.append((f.formal, self._say("formal_reading")))
            # a trap's formal reading of another entry (بدم: بد + the copula) is a reading of the word too, and is told as one
            for f in formal:
                # (the formal reading of the letters as they stand, of what the dictionary's answer already has, is that answer)
                if direct and f.entries() <= direct and lk._fold(f.formal, L) == lk._fold(w, L):
                    continue
                if not f.entries() <= have and f.rules:
                    f.spoken = f.by_rule = True
                    f.whys.append(self._say("formal_reading"))
                    spoken.append(f)
                    have |= f.entries()
        return spoken
