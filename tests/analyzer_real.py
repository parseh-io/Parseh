# SPDX-License-Identifier: GPL-3.0-or-later
"""The real analyzers on small sentences, for a person to read: run by hand, given a folder with
lib/getanalysis.py's runtime/ and models/ in it.

    python3 tests/analyzer_real.py <analysis folder>

Not a unit test: what a model says changes with the model, and is no universal truth.  It fails
only where a result cannot be proved against its text.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import analyzer     # noqa: E402
import chunker      # noqa: E402
import evidence     # noqa: E402
import getanalysis  # noqa: E402

SENTENCES = {
    "en": ["She didn't give up on it. He looked it up!", "The old man has been reading the book in the garden."],
    "de": ["Ich rufe dich morgen an. Zum Haus gehen wir.", "Der alte Mann steht langsam von seinem Stuhl auf."],
    "es": ["Dámelo ahora. Voy al mercado del pueblo.", "La vieja casa de mi abuela está junto al río."],
    "fr": ["Je vais au marché. L'homme l'a vu.", "La vieille maison de ma grand-mère est près de la rivière."],
    "it": ["Vado al mercato. Dammelo subito.", "La vecchia casa di mia nonna è vicino al fiume."],
    "hi": ["राम घर से स्कूल को गया।", "बूढ़ा आदमी बगीचे में किताब पढ़ रहा है।"],
    "fa": ["کتاب‌ها را نمی‌خوانم.  او به خانه رفته است.", "مرد پیر در باغ کتاب بزرگی می‌خواند."],
    "ar": ["ذهب الولد إلى المدرسة وكتب الدرس. وذهب الولد.", "قرأ الرجل العجوز كتابا كبيرا في الحديقة."],
    "tr": ["Evlerimizden geldim, teşekkür ederim. İstanbul'da 😀 yaşıyorum.",
           "Yaşlı adam bahçede büyük bir kitap okuyordu."],
}


def main(folder):
    getanalysis.FOLDER = folder
    bad = 0
    for code, texts in SENTENCES.items():
        for text in texts:
            t0 = time.time()
            r = analyzer.analyze(code, text, syntax=True)
            took = time.time() - t0
            print("\n## %s %s %s %.3fs %s" % (code, r.outcome, r.backend, took, list(r.diagnostics)[:2]))
            print("  ", text)
            if not r.ok:
                bad += 1
                continue
            analyzer.validate(r)
            for t in r.tokens:
                p = t.parsed()
                print("   %-14s %-28s %-14s %s%s" % (t.surface, ", ".join(t.lemmas()[:3]), ",".join(w.upos or "" for w in p),
                                                     ",".join(w.relation or "" for w in p),
                                                     " [%d]" % len(t.candidates) if t.candidates else ""))
            print("   old  ", " | ".join(chunker.chunk(text, code, "phrase")))
            print("   with ", " | ".join(chunker.chunk(text, code, "phrase", lambda x: analyzer.analyze(code, x, syntax=True))))
            print("   evidence", sum(len(s["analysis"]) for s in evidence.for_text(code, text)["sentences"]), "entries")
    getanalysis.stop_worker()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
