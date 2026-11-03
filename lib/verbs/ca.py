# SPDX-License-Identifier: GPL-3.0-or-later
"""Catalan: the \\vb a verb hit offers, read off the rows Wiktionary wrote.

    \\vb{parlar}{}{parlo}{}{parlat}{}{to speak}
    \\vb{tenir}{}{tinc}{}{tingut}{}{to have (fut. \\pw{tindré})}
    \\vb{dormir}{}{dormo}{dòrmo}{dormit}{}{to sleep}
    \\vb{llevar-se}{}{em llevo}{em llévo}{llevat}{}{to get up}
    \\vb{caldre}{}{cal}{}{calgut}{}{to be needed}

    python3 lib/verbs/__init__.py ca "es va llevar d'hora"

WHAT docs/lang/ca.md ASKS FOR, and all this file makes: the infinitive, the
first person present and the masculine singular past participle -- the
registry's `pres.` and `p.p.` -- then the meaning, then, in one parenthesis
and only where it is irregular, the first person future (`fut. tindré`).  No
auxiliary: every Catalan perfect is made with haver.  A pronominal verb is the
infinitive with its pronoun written on, the present with its own before it
and the participle bare; an impersonal verb gives the third person.

WHERE EACH FORM COMES FROM.  A Catalan verb page's head line (ca-verb) gives
`first-person present singular`, `first-person preterite singular` and
`participle past`, joined with spaces and WITHOUT `indicative`; the generated
table after it says `indicative`, and getdict drops a table cell the head line
already spelled.  So each cell is asked for by its exact tag set, the head's
first, then the table's, then a pointer page's (the same tags, comma-joined).
The first row is the editors' first form: haver's head line gives he before
hec and hac, ser's estat before sigut -- `estat` is what docs/lang/ca.md
prints for ser.  An impersonal verb's head line has `present singular
third-person` and no first person (caldre: cal), and that is taken.

THE SOUND SLOTS ARE THE HARD PART, and here the source is short.
docs/lang/ca.md fills a form's sound only where its stressed vowel is an e or
an o the spelling does not mark, and then marks it as Central Catalan says
it: pèrdo, fét, servèixo, sóc.  The stressed vowel is found from the spelling
(_stressed: Catalan writes an accent exactly where its stress rule would be
wrong, so an unmarked word is read by the rule).  WHICH e or o is another
matter: the dictionary built on 2026-11-03 keeps the FIRST pronunciation
Wiktionary lists, and for Catalan that is mostly the Northern one, whose e̞
and o̞ say nothing of open or closed: of the verb pronunciations stressing an
e or an o, 1 of 172 entries' and 98 of 2 833 form rows' say which.  So the
quality is read only where something says it, and otherwise the slot goes in
empty and `missing` names it:

  * a pronunciation of exactly that form (the entry's for slot 1, a row of
    the same spelling for the others) whose stressed vowel is ɛ e ɔ or o --
    menjo [ˈmeɲ.ʒu] today; nearly every one once the dictionary keeps
    Central's (lib/lang/ca.ipa.json asking for it, as fa's does);
  * the head line's `root stress`, for the 1st person present of a verb
    whose present keeps the infinitive's stem, and for an infinitive stressed
    on that stem (_root_stress, measured below);
  * the infinitive's own written accent on the same root vowel: conèixer ->
    conèc, témer -> témo, córrer -> córro;
  * the -eix- of an -ir verb, which is open in Central wherever it is
    stressed: serveixo -> servèixo.

WHICH VERB THE CHUNK HAS is decided here, because only the chunk says it and
a lookup is one word at a time.  `es lleva` and `es va llevar` reach llevar,
"to remove", and the verb is llevar-se, "to get up": a weak pronoun of the
verb's own person before it (em, m', et, es, s', ens, us -- or written on
after an infinitive, -se, 's) makes the \\vb the pronominal one
(_pronominal).  A bare third-person es is as often impersonal (`es diu`, one
says), so the pronominal verb is drafted and `missing` says it is a question.
And `va` before an infinitive is not "to go": `va dir` is the past of dir,
whose own hit carries the \\vb, so `va` there offers none.

NOTHING IS GUESSED: what cannot be read goes in `missing`, in the registry's
words for the slot.
"""
import re
import unicodedata

import lookup
import verbs
from verbs import Parts, tl

# ------------------------------------------------------------- the cells
PRES1_H = frozenset(("first-person", "present", "singular"))
PRES1_T = PRES1_H | {"indicative"}
PRES3_H = frozenset(("present", "singular", "third-person"))
PRES3_T = PRES3_H | {"indicative"}
PP = frozenset(("participle", "past"))
FUT1 = frozenset(("first-person", "future", "indicative", "singular"))
FUT3 = frozenset(("future", "indicative", "singular", "third-person"))
# what makes an entry a verb's table (the cells a \vb prints)
_SLOT_NOTES = ("first-person present singular", "participle past",
               "present singular third-person",
               "first-person indicative present singular")


def _fold(s):
    """Lower case, no accents, one apostrophe: comparisons only."""
    s = (s or "").replace("’", "'").lower()
    return "".join(ch for ch in unicodedata.normalize("NFD", s)
                   if unicodedata.category(ch) != "Mn")


def _cell(t, *cells):
    """The first row for a cell: the head line's tags, then the table's,
    then a pointer page's -- each exactly, so `obsolete` and `Balearic`
    cousins (haver's hec, fer's fais) never come before the plain form."""
    for own in (True, False):
        for c in cells:
            r = t.pick(exact=c, own=own)
            if r is not None:
                return r
    return None


# ------------------------------------------------------------- the stress
_V = set("aeiouàèéíòóúïü")
_ACCENTED = "àèéíòóú"


def _stressed(word):
    """The index of the stressed vowel letter of one word, or None.

    A written accent is the stress.  Without one, Catalan stresses the
    next-to-last syllable of a word ending in a vowel, a vowel + s, -en or
    -in, and the last of any other -- the rule the accents are written
    against.  A syllable is counted by its vowel: an i or u after a vowel is
    the end of a diphthong (veu-re, ser-vei-xo), the u of gu, qu and gü is no
    syllable, and the i of a final -ir is one (obeir, the infinitive's)."""
    raw = (word or "").lower()
    for i, ch in enumerate(raw):
        if ch in _ACCENTED:
            return i
    nuclei = []
    for i, ch in enumerate(raw):
        if ch not in _V:
            continue
        prev = raw[i - 1] if i else ""
        nxt = raw[i + 1] if i + 1 < len(raw) else ""
        if ch in "uü" and prev in ("g", "q") and nxt in _V:
            continue
        if ch in "iu" and prev in _V and not (ch == "i" and raw[i:] == "ir"):
            continue
        if ch in "iu" and i == 0 and nxt in _V:
            continue
        nuclei.append(i)
    if not nuclei:
        return None
    end = raw
    if end.endswith("s") and len(end) > 1 and end[-2] in _V:
        end = end[:-1]
    elif end.endswith(("en", "in")):
        end = end[:-1]
    if len(nuclei) > 1 and len(end) - 1 in nuclei:
        return nuclei[-2]
    return nuclei[-1]


_MARK = {("e", "ɛ"): "è", ("e", "e"): "é", ("o", "ɔ"): "ò", ("o", "o"): "ó"}


def _ipa_quality(ipa):
    """'ɛ', 'e', 'ɔ' or 'o': the stressed vowel of a pronunciation, where it
    says which -- not the Northern e̞ and o̞ (U+031E), which do not."""
    s = (ipa or "").strip("[]/")
    k = s.find("ˈ")
    if k < 0:
        return None
    for i in range(k + 1, len(s)):
        ch = s[i]
        if ch in "aeiouɛɔəɐæɑɪʊ":
            if ch in "eoɛɔ" and not (i + 1 < len(s) and s[i + 1] in "̞̝"):
                return ch
            return None
    return None


def _root_stress(t):
    """'ɛ', 'e', 'ɔ' or 'o': the Central quality of the verb's stressed root
    vowel, from the head line's `root stress`, or None.

    The rows lose the head line's region labels: `root stress: (Northern)
    /e̞/; (Balearic) /ə/; (Central) /ɛ/; (Northwestern, Valencia) /e/` is
    kept as `e̞`, `/ə/`, `/ɛ/`, `/e/`.  When the source lists every region in
    its own order the first row is the Northern one (e̞, o̞ or u), Balearic's
    reduced /ə/ may follow, and the next is Central's; a page that names its
    regions itself may put Valencia first, and is not read.  Measured on the
    kaikki extract of 2026-11-03 against the labelled head lines: 1 504 of
    the 1 528 verbs with a root stress read this way, all of them Central's
    vowel; the rest (a region-named list, besar's doubled informal one) give
    None."""
    rows = [f.form for f in t.picks(exact={"canonical"}, own=True)]
    if "root stress:" not in rows:
        return None
    vals = rows[rows.index("root stress:") + 1:]
    if not vals or vals[0] not in ("e̞", "o̞", "u"):
        return None
    rest = [v.strip("/") for v in vals[1:] if v.strip("/") != "ə"]
    if not rest or any("̞" in v for v in rest):
        return None
    return rest[0] if rest[0] in ("ɛ", "e", "ɔ", "o") else None


def _stem(head):
    """The infinitive's stem, folded: parl(ar), perd(re), coneix(er), dorm(ir)."""
    w = _fold(_bare_inf(head))
    for end in ("re", "ar", "er", "ir", "r"):
        if w.endswith(end):
            return w[:-len(end)]
    return w


def _bare_inf(head):
    """A pronominal headword without its pronoun: llevar-se -> llevar,
    perdre's -> perdre, anar-se'n -> anar."""
    h = (head or "").replace("’", "'").split(" ")[0]
    return re.sub(r"(?:-se'n|-se|'s)$", "", h)


def _sound(t, form, slot, ipa=""):
    """(the sound for a slot, a missing item or '').

    `form` may carry pronouns (em llevo, m'adono, me'n vaig, llevar-se,
    perdre's): its last word, without a pronoun elided onto its front or
    written onto its end, is the verb word, and the mark goes there."""
    words = (form or "").split(" ")
    vw = words[-1] if words else ""
    m = re.match(r"^((?:[a-z]{1,2}['’])?)(.*?)((?:-[a-z'’]+|['’][a-z]{1,2})*)$", vw, re.I)
    pre, core, post = m.groups()
    i = _stressed(core)
    if i is None or core[i] not in "eo":
        return "", ""
    letter = core[i]
    q = _ipa_quality(ipa)
    if q is None and slot in (1, 2):
        head = t.entry["headword"] or ""
        inf, stem = _bare_inf(head), _stem(head)
        acc = next((k for k, ch in enumerate(inf) if ch in "èéòó"), None)
        f = _fold(core)
        if slot == 1 or f.startswith(stem):
            rs = _root_stress(t)
            if rs and i < len(stem):
                q = rs
        if q is None and slot == 2 and acc is not None and acc == i \
                and f[:i + 1] == _fold(inf)[:i + 1]:
            q = {"è": "ɛ", "é": "e", "ò": "ɔ", "ó": "o"}[inf[acc]]
        if q is None and slot == 2 and _fold(inf).endswith("ir") \
                and f[i:i + 3] == "eix":
            q = "ɛ"                    # Central's inchoative -eix- is open
    mark = _MARK.get((letter, q))
    if mark is None:
        return "", "sound of %s (open or closed %s)" % (form, letter)
    words[-1] = pre + core[:i] + mark + core[i + 1:] + post
    return " ".join(words), ""


def _ipa_of(t, form):
    """The pronunciation a row of this entry gives for exactly this form."""
    for f in t.rows:
        if f.form == form and f.ipa:
            return f.ipa
    return ""


# ------------------------------------------------------------ the entries
def _has_table(conn, eid):
    return conn.execute(
        "SELECT 1 FROM form WHERE entry_id = ? AND note IN (%s) LIMIT 1"
        % ",".join("?" * len(_SLOT_NOTES)), (eid,) + _SLOT_NOTES).fetchone() is not None


def _verb_entry(conn, headword, table=True):
    """The first verb entry by that headword (with a table, if asked)."""
    for (eid,) in conn.execute("SELECT id FROM entry WHERE headword = ? AND "
                               "pos = 'verb' ORDER BY id", (headword,)):
        if not table or _has_table(conn, eid):
            return eid
    return None


# "only used in s'... adonar, syntactic variant of adonar-se, infinitive of
# adonar-se": 52 of the 64 verb entries without a table say this
_ONLY_IN = re.compile(r"(?i)^only used in .*?syntactic variant of (\S+?),")
_FORM_WORDS = re.compile(r"(?i)\b(?:first|second|third)[- ]person\b|\bparticiple\b|"
                         r"\bgerund\b|\binflection of\b|\bform of\b")
_OF = re.compile(r"(?i)\bof ([^\s,;:.()]+)")


def _target(ctx):
    """The Ctx whose table describes this verb, or None.  Itself when it has
    a table; the -se verb an "only used in" page names; the verb a form page
    names ("eres: second-person singular present ... of ser"); an infinitive
    with no table is a verb all the same, with what it lacks in `missing`."""
    if _has_table(ctx.conn, ctx.entry["id"]):
        return ctx
    first = next((s.strip() for s in ctx.senses if s.strip()), "")
    m = _ONLY_IN.match(first)
    names = [m.group(1)] if m else (
        list(reversed(_OF.findall(first))) if _FORM_WORDS.search(first) else [])
    for name in names:
        eid = _verb_entry(ctx.conn, name)
        if eid:
            return ctx.other(eid)
    if names:
        return None
    head = _fold(_bare_inf(ctx.entry["headword"] or ""))
    return ctx if re.search(r"(?:ar|er|ir|re)$", head) else None


# ------------------------------------------------- the pronoun and the past
# The weak pronouns that make a verb pronominal, and the person each is.
_PRON = {"em": (1, "sg"), "m'": (1, "sg"), "me": (1, "sg"),
         "et": (2, "sg"), "t'": (2, "sg"), "te": (2, "sg"),
         "es": (3, None), "s'": (3, None), "se": (3, None),
         "ens": (1, "pl"), "us": (2, "pl"),
         "me'n": (1, "sg"), "te'n": (2, "sg"), "se'n": (3, None)}
# THE TWO AUXILIARIES A PRONOUN STANDS BEFORE instead of the verb -- `es va
# llevar`, `s'ha llevat` -- with their persons.  A closed list of the
# grammar's: anar's present that makes the past, haver's present and
# imperfect that make the perfect and the pluperfect.
_AUX = {"vaig": (1, "sg"), "vas": (2, "sg"), "vares": (2, "sg"), "va": (3, "sg"),
        "vam": (1, "pl"), "varem": (1, "pl"), "vau": (2, "pl"), "vareu": (2, "pl"),
        "van": (3, "pl"), "varen": (3, "pl"),
        "he": (1, "sg"), "has": (2, "sg"), "ha": (3, "sg"), "hem": (1, "pl"),
        "heu": (2, "pl"), "han": (3, "pl"), "havia": (3, "sg"), "havies": (2, "sg"),
        "haviem": (1, "pl"), "havieu": (2, "pl"), "havien": (3, "pl")}
_GO_PAST = ("vaig", "vas", "vares", "va", "vam", "varem", "vau", "vareu", "van", "varen")


def _persons(t, word):
    """{(person, number)} the rows of this entry say the word is; number
    None for an infinitive or a gerund, which agree with any pronoun."""
    out = set()
    for f in t.rows:
        if _fold(f.form) != word:
            continue
        p = next((n for n, x in ((1, "first-person"), (2, "second-person"),
                                  (3, "third-person")) if x in f.tags), None)
        n = "pl" if "plural" in f.tags else "sg" if "singular" in f.tags else None
        if p:
            out.add((p, n))
        elif f.tags & {"infinitive", "gerund"} or f.note in ("", "canonical"):
            out.add((0, None))
    return out


def _agrees(pron, persons):
    p, n = _PRON[pron]
    return any(q == 0 or (q == p and (n is None or m == n)) for q, m in persons)


def _pronominal(ctx, t):
    """(the pronoun, 'n' when it carries en) when the chunk makes this verb
    pronominal, else None.  The word itself may carry it (s'alça, rentar-se,
    llevant-se); else the word before it, or before an auxiliary before it."""
    w = _fold(ctx.word)
    m = re.match(r"^([mts]')(.+)$", w)
    if m:
        return (m.group(1), "") if _agrees(m.group(1), _persons(t, m.group(2))) else None
    m = re.match(r"^(.+?)(-se'n|-se|'s)$", w)
    if m:
        return ("es", "n" if m.group(2) == "-se'n" else "")
    toks = [_fold(lookup._bare(x, ctx.L)) for x in ctx.L.split_words(ctx.text or "")]
    for i, x in enumerate(toks):
        if x != w or i == 0:
            continue
        before, who = toks[i - 1], _persons(t, w)
        a = re.match(r"^([mts]')(.+)$", before)
        if a and a.group(2) in _AUX:                     # s'ha llevat
            return (a.group(1), "") if _agrees(a.group(1), {_AUX[a.group(2)]}) else None
        if before in _AUX and i >= 2:                     # es va llevar
            before, who = toks[i - 2], {_AUX[before]}
        if before in _PRON and _agrees(before, who):
            return before, ("n" if before.endswith("'n") else "")
    return None


def _go_past(ctx, t):
    """Is this `va` (vaig, van ...) the auxiliary of the past -- before an
    infinitive, with no `a` between (`vaig a parlar` IS going to)?"""
    if _fold(t.entry["headword"]) != "anar" or _fold(ctx.word) not in _GO_PAST:
        return False
    toks = [_fold(lookup._bare(x, ctx.L)) for x in ctx.L.split_words(ctx.text or "")]
    for i, x in enumerate(toks[:-1]):
        if x == _fold(ctx.word):
            nxt = re.sub(r"(?:-[a-z']+|'[a-z]+)+$", "", toks[i + 1])
            if _verb_entry(ctx.conn, nxt, table=False) and nxt != "anar":
                return True
    return False


def _with_pronoun(form, n=""):
    """The first person with its pronoun before it: em llevo, m'adono,
    me'n vaig, me n'aniré -- the elision is the spelling's, before a vowel
    or an h."""
    vowel = bool(re.match(r"(?i)^h?[aeiouàèéíòóú]", form or ""))
    if n:
        return ("me n'" if vowel else "me'n ") + form
    return ("m'" if vowel else "em ") + form


def _pron_head(inf, n=""):
    """llevar -> llevar-se, perdre -> perdre's, anar (+ en) -> anar-se'n."""
    if n:
        return inf + "-se'n"
    return inf + ("'s" if inf[-1:] in "aeiou" else "-se")


# ----------------------------------------------------------- the meaning
_REFL = frozenset(("reflexive", "pronominal"))


def _meaning(t, refl):
    """The first ranked sense that is (refl) or is not (plain) the verb's
    pronominal use, else the first; brackets off, one equivalent."""
    ranked = lookup.rank_senses([s for s in t.senses if s.strip()],
                                (t.entry["sense_tags"] or "").split("\n"))
    pick = next((s for s, tags, _ in ranked
                 if bool(_REFL & set(tags.split(","))) == refl), None)
    if pick is None and ranked:
        pick = ranked[0][0]
    m = verbs.trim_meaning(pick or "")
    m = re.sub(r"\s*\[[^\[\]]*\]", "", m)
    m = re.sub(r"\s*\[.*$", "", m).strip(" ,;:")
    return verbs.one_equivalent(m)


# ------------------------------------------------------------ the recipe
def recipe(ctx):
    """The Parts of a Catalan verb hit, or None (see the module docstring)."""
    if (ctx.entry["pos"] or "") != "verb":
        return None
    t = _target(ctx)
    if t is None or _go_past(ctx, t):
        return None
    pro = None
    if not re.search(r"(?:-se|'s|-se'n)$", t.entry["headword"] or ""):
        pro = _pronominal(ctx, t)
    if pro is None:
        return _describe(ctx, t, t.entry["headword"] or "", "", [], refl=False)
    pron, n = pro
    inf = t.entry["headword"] or ""
    head = _pron_head(inf, n)
    doubt = []
    # THE PRONOMINAL VERB'S OWN PAGE, where it has a table, is the verb
    # (queixar-se: em queixo, queixat); else the plain verb's rows with the
    # pronoun written on, and its pronominal sense -- or the page's, where a
    # page without a table has one (anar-se'n "to go away").
    own = _verb_entry(t.conn, head)
    if own:
        return _describe(ctx, ctx.other(own), head, "", doubt, refl=True)
    page = _verb_entry(t.conn, head, table=False)
    if _PRON[pron][0] == 3 and "-" not in ctx.word and "'s" not in _fold(ctx.word)[-2:]:
        doubt.append("whether %s here makes it %s or is impersonal (%s)"
                     % (pron, head, inf))
    mean = _meaning(ctx.other(page), refl=True) if page else None
    return _describe(ctx, t, head, n or "-", doubt, refl=True, meaning=mean)


def _describe(ctx, t, head, pron, doubt, refl, meaning=None):
    """`pron` is '' for the verb as its rows spell it, '-' to write em/m'
    before the present, 'n' to write me'n."""
    forms = list(getattr(ctx.L, "vb_forms", None)
                 or ["infinitive", "1st sg. present", "past participle"])
    missing = list(doubt)
    # the infinitive's pronunciation is the entry's: perdre's is said as
    # perdre is, so a pronominal head made from it has the same one
    s1, gap = _sound(t, head, 1, t.entry["ipa"])
    missing += [gap] if gap else []

    third = False
    p2 = _cell(t, PRES1_H, PRES1_T)
    if p2 is None:
        p2 = _cell(t, PRES3_H, PRES3_T)        # impersonal: caldre, cal
        third = p2 is not None
    f2 = s2 = ""
    if p2 is None:
        missing.append(forms[1])
    else:
        f2 = p2.form
        if pron and not third:
            f2 = _with_pronoun(f2, "n" if pron == "n" else "")
        s2, gap = _sound(t, f2, 2, _ipa_of(t, p2.form))
        missing += [gap] if gap else []

    p3 = _cell(t, PP)
    f3 = s3 = ""
    if p3 is None:
        missing.append(forms[2])
    else:
        f3 = p3.form
        s3, gap = _sound(t, f3, 3, _ipa_of(t, f3))
        missing += [gap] if gap else []

    # the future, only where it is not the infinitive + its ending:
    # parlar parlaré, perdre perdré, conèixer coneixeré; tenir tindré
    extras = []
    fut = _cell(t, FUT3 if third else FUT1)
    if fut is not None:
        inf = _fold(_bare_inf(t.entry["headword"] or ""))
        stem = inf[:-1] if inf.endswith("re") else inf
        # judged on the verb word: a -se page's row is `em queixaré`
        verb = re.sub(r"^[a-z]{1,2}'", "", _fold(fut.form).split(" ")[-1])
        if verb != stem + ("a" if third else "e"):
            word = fut.form
            if pron and not third:
                word = _with_pronoun(word, "n" if pron == "n" else "")
            extras.append("fut. " + tl(word))

    if not verbs.gloss_is_en(ctx.gloss):
        meaning = ""
    elif meaning is None:
        meaning = _meaning(t, refl)
    return Parts(parts=[(head, s1), (f2, s2), (f3, s3)], meaning=meaning,
                 extras=extras, missing=missing)
