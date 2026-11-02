# SPDX-License-Identifier: GPL-3.0-or-later
"""Before and after, for a person to read: the phrases and the dictionary without and with the real analyzers.
Reads a folder of analyzers and a folder of dictionaries, and writes nothing.

    python3 tests/analysis_review.py <analysis folder> <dict folder>

Original sentences only.  What it prints is for inspection: no line of it is a pass or a fail.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import analyzer        # noqa: E402
import chunker         # noqa: E402
import evidence        # noqa: E402
import getanalysis     # noqa: E402
import lookup          # noqa: E402
import lookupassist    # noqa: E402

SENTENCES = {
    # ezafe, negative written apart, light verbs, the same word as two things
    "fa": ["کتاب‌های قدیمی را نمی سوزانند.", "دیروز با دوستم به خانه‌ی بزرگی رفته بودیم.", "من از او خیلی تشکر کردم و برگشتم.",
           "شیر را خورد و شیر در جنگل خوابید.", "خانه‌ی پدر من کوچک است.", "دخترک به مادرش نگاه کرد."],
    # clitics, an initial capital that is a verb, a contraction
    "it": ["La vecchia signora non ci andò mai più.", "Seppe la verità e tornò a casa.", "Gliel'ho detto ieri sera, ma non mi ha creduto.",
           "Dammelo subito, per favore!", "I cani dei miei vicini abbaiavano tutta la notte."],
    # separable verbs, contractions
    "de": ["Der alte Mann steht langsam von seinem Stuhl auf.", "Ich rufe dich morgen an.", "Zum Glück hat sie das Buch gelesen.",
           "Er machte die Tür schnell zu.", "Die Kinder spielten gestern im Garten."],
    # phrasal verbs, auxiliaries
    "en": ["She didn't give up on it.", "The old man has been reading the book in the garden.", "He looked it up in a dictionary.",
           "They ran out of milk this morning."],
    # clitics on the verb, contractions
    "es": ["Dámelo ahora, por favor.", "La vieja casa de mi abuela está junto al río.", "Quiero decírtelo mañana por la tarde.", "Fuimos al mercado del pueblo."],
    "fr": ["L'homme l'a vu au marché.", "La vieille maison de ma grand-mère est près de la rivière.", "Je ne lui en ai jamais parlé."],
    # postpositions, compound verbs
    "hi": ["राम घर से स्कूल को गया।", "बूढ़ा आदमी बगीचे में किताब पढ़ रहा है।", "उसने मेरी मदद की।", "लड़के ने दरवाज़ा खोल दिया।"],
    # attached conjunctions, prepositions, articles and pronouns; active or passive; unvowelled, partly and fully vowelled
    "ar": ["ذهب الولد إلى المدرسة وكتب الدرس.", "قرأ الرجل العجوز كتابا كبيرا في الحديقة.", "كتب الولد الكتب.", "وبالكتاب تعلمنا الكثير.",
           "رأيت مدرسته وكتابهم.", "كُتِبَ الدرس في المدرسة.", "ضرب الولد الكرة.", "يكتب المعلم على اللوح."],
    # agglutination, derivation, light verbs, the dotted and dotless I, an ambiguous word
    "tr": ["Evlerimizden geldim, teşekkür ederim.", "Yaşlı adam bahçede büyük bir kitap okuyordu.", "Yardım etmedik, çünkü yüz kişi gelmişti.",
           "Yüzü çok güzel, ama yüz metre yüzemedi.", "Alışveriş yaptıktan sonra eve dönerek uyudum.", "Kitaplarımızı okuyamadılar.",
           "İstanbul'da ısındık.", "Gelen adamı görmemişler."],
    "ja": ["寒い朝に窓を開ける。"], "zh": ["我今天去学校。"],
}


def main(folder, dicts):
    getanalysis.FOLDER = folder
    lookup.DICT_DIR = dicts
    only = sys.argv[3:]
    for code, texts in SENTENCES.items():
        if only and code not in only:
            continue
        print("\n# %s  about: %s" % (code, {k: (v or {}).get("usable") for k, v in analyzer.about(code).items() if k != "language"}))
        for text in texts:
            print("\n  %s" % text)
            r = analyzer.analyze(code, text, syntax=True)
            print("    outcome", r.outcome, r.backend, list(r.diagnostics)[:1])
            before = chunker.chunk(text, code, "phrase")
            after = chunker.chunk(text, code, "phrase", (lambda t: r) if r.ok else None)
            print("    chunks before:", " | ".join(before))
            print("    chunks  after:", " | ".join(after) if after != before else "(the same)")
            if r.ok and not chunker.exact(after, text):
                print("    !! NOT AN EXACT SLICE")
            if lookup.available(code):
                old = lookup.look_up(code, text) or {}
                new = lookup.look_up(code, text) or {}
                lookupassist.apply(code, new, text, text, "assist")
                for a, b in zip(old.get("words") or [], new.get("words") or []):
                    fit = [h["headword"] + "/" + h.get("pos", "") for h in b.get("hits") or [] if h.get("fits")]
                    if fit:
                        print("    FITS %s [%s] of %s: %s" % (a["word"], (b.get("machine") or {}).get("pos"),
                                                               [h["headword"] + "/" + h.get("pos", "") for h in a.get("hits") or []][:4], fit))
                    x = [h["headword"] for h in a.get("hits") or []]
                    y = [h["headword"] for h in b.get("hits") or []]
                    if x != y:
                        print("    lookup %s: %s -> %s  [%s]" % (a["word"], x[:3], y[:3], b.get("via")))
                    elif not x:
                        print("    lookup %s: still nothing; analyzer: %s" % (a["word"], (b.get("machine") or {}).get("lemma")))
                    else:
                        print("    lookup %s: %s, the same; analyzer: %s" % (a["word"], x[:2], (b.get("machine") or {}).get("lemma")))
            if r.ok and code in evidence.LANGUAGES:
                for s in evidence.for_text(code, text)["sentences"]:
                    print("    evidence %d entries, %d chars" % (len(s["analysis"]), len(str(s["analysis"]))))
    getanalysis.stop_worker()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
