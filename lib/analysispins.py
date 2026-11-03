# SPDX-License-Identifier: GPL-3.0-or-later
"""The exact programs and models the optional analyzers are, checked 2026-11-02 (Catalan 2026-11-03).

Standard library only and no logic: lib/getanalysis.py fetches by these,
lib/analyzer_udpipe.py finds its files by these, and docs/analyzers.md says what
was verified about them and how to move a pin.

The models are UDPipe 1's, for Universal Dependencies 2.5 (handle 11234/1-3131
at LINDAT).  The repository's old file addresses now answer a web page with
status 200, so what is pinned is each file's bitstream id and its hash.  They are
CC BY-NC-SA 4.0, which is not Parseh's licence and not Parseh's to waive: nothing
of them is in the repository or in a release, and the page says so before
anybody presses a button.
"""

UDPIPE_VERSION = "1.4.0.1"
FARAHIDI_VERSION = "0.4.0"
STARLANG_VERSION = "1.0.36"

MODEL_HOST = "https://lindat.mff.cuni.cz/repository/server/api/core/bitstreams/%s/content"
MODEL_PAGE = "https://hdl.handle.net/11234/1-3131"
MODEL_LICENCE = "CC BY-NC-SA 4.0"
MODEL_LICENCE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
MODEL_CREDIT = ("Milan Straka and Jana Straková, Universal Dependencies 2.5 Models for UDPipe "
                "(2019-12-06), LINDAT/CLARIAH-CZ, Institute of Formal and Applied Linguistics, "
                "Charles University")


def _model(treebank, uuid, size, sha256):
    return {"treebank": treebank, "file": "%s-ud-2.5-191206.udpipe" % treebank, "bitstream": uuid,
            "bytes": size, "sha256": sha256, "licence": MODEL_LICENCE}


UDPIPE_MODELS = {
    "en": _model("english-ewt", "8d51e3d3-1f87-47fe-8975-c197ddf7907b", 16309608,
                 "784bd0fa85e3d831fd02a55290d0acfd05c953159dc38cc33d52e1b28add9957"),
    "de": _model("german-gsd", "9aacee5d-a347-42ac-89cf-f509511f8592", 21301225,
                 "3a14db4ff1a7fa6eee756537d579b49c0a000e4fc9bed474b681e31e73f02274"),
    "es": _model("spanish-ancora", "52474ca8-939b-4fcf-80b0-228679464582", 20400504,
                 "eb7c37977de18072d1f63740c06c588620d48b51dc0c0d0a3604a21db12600fc"),
    "fr": _model("french-gsd", "75091a21-f175-4a57-8bbd-8f9a12a7d417", 23811948,
                 "3b10b4c87e7667ac4cf5b301fa075720303c6a1d101cd11a62abde670bebea30"),
    "it": _model("italian-isdt", "ee10c62a-01c5-42cb-a8b6-b7751c5da12c", 19298761,
                 "dad54daaa01c250f39ec0ae7d29b3f3830c1eea066db4e3a92c39b41f2dd1a40"),
    "hi": _model("hindi-hdtb", "08ffe51d-1072-4884-90e1-58693a198390", 25857814,
                 "d7a77399e6eccee9103d8df9b441ec25ba6ba9f4db453eed3f4ddb77acdd7f2a"),
    "fa": _model("persian-seraji", "c3694916-0193-448d-8d42-856a4c241d19", 11499413,
                 "c0f1f4f694a30de1689abb2549512ec1a92d6d12cee46ce613876ad0050db7af"),
    "ar": _model("arabic-padt", "950d4077-bd61-4e5c-af05-ac9de11ddb39", 19752087,
                 "5637b73cc30ebd231ccad7ee4ee57d7c8367f6b1883aae09128e656b760e7be3"),
    "ca": _model("catalan-ancora", "af6b22b0-9e1f-4af8-80b9-95fa911d5987", 18142787,
                 "a706a200017c3968e2c23ee229d7680d22140d948358e5a667cdece4a997d8ad"),
    "tr": _model("turkish-imst", "9308edfd-6a11-4774-8dac-c64f13778d2a", 8396624,
                 "195f5646d96663c788d66ea29bb26862b17457aa7a8d95bf3d852d75522a5fed"),
}

# the dist-info folder pip leaves when a package is whole: how `status` knows
# without importing anything.  Each name as pip writes it, in lower case.
PACKAGES = {
    "udpipe": ("ufal_udpipe-%s.dist-info" % UDPIPE_VERSION,),
    "farahidi": ("farahidi-%s.dist-info" % FARAHIDI_VERSION,),
    "starlang": ("nlptoolkit_morphologicalanalysis_cy-%s.dist-info" % STARLANG_VERSION,),
}

# what each costs on the disk, measured in a fresh environment on Linux x86-64
PROGRAM_MB = {"udpipe": 3, "farahidi": 12, "starlang": 75}
