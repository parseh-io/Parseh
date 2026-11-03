#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Immutable public Parseh CTC-aligner artifacts, checked 2026-09-30 (Catalan 2026-11-03).

Only the int8 ONNX runtime artifact is distributed.  The smaller supporting
JSON/licence files are hash checked as well; their size is deliberately not a
second network probe, while each model's measured size powers Settings' plan.
"""

_LICENSE = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
_PRE = {"zh": "c403ce09975b90dff0dd8302c42d422e9de1f166cd7772df23490069893cb0cf",
        "ja": "ffc72f475cd79680d5d659fbaefc691cdbcee5c9703a15faf708a5e91452a8d8",
        "hi": "8f9f560daa144e525174a9ce159ac4d168e010006d6c3e46cad02cae72a6c5ad",
        "ar": "c403ce09975b90dff0dd8302c42d422e9de1f166cd7772df23490069893cb0cf",
        "fa": "c403ce09975b90dff0dd8302c42d422e9de1f166cd7772df23490069893cb0cf",
        "tr": "94c00f2bccbdbf4891a1ed8be371e59debaedd03d64f5e8313cedfa4c60da22b",
        "es": "ca5999a45e98bb76ea87a461ba28a23ad32a5bb9f733b8e0f6546ff38b6c612d",
        "de": "ca5999a45e98bb76ea87a461ba28a23ad32a5bb9f733b8e0f6546ff38b6c612d",
        "fr": "ca5999a45e98bb76ea87a461ba28a23ad32a5bb9f733b8e0f6546ff38b6c612d",
        "it": "ca5999a45e98bb76ea87a461ba28a23ad32a5bb9f733b8e0f6546ff38b6c612d",
        "en": "ca5999a45e98bb76ea87a461ba28a23ad32a5bb9f733b8e0f6546ff38b6c612d",
        "ca": "c403ce09975b90dff0dd8302c42d422e9de1f166cd7772df23490069893cb0cf"}

# code: public-repo commit, source licence, model sha/bytes, vocab sha,
# meta sha, NOTICE sha.  The source commits/preprocessing contract are inside
# the separately hash-checked meta.json fetched with these files.
_ROWS = {
 "zh": ("920ed68179700a9380364a119744e046e04fb14d", "apache-2.0", "a2ed0362fec4989a81854b0485b61b551ef3dd9d3761a489960848a07acae985", 378078776, "e2fa9e1f77e7b4c26d31d60dca783175cb82da4227c6695e76fcf616829a41a8", "465deb42030d968c1df163a7bc31f9f3e5027d11d2db0f83c8c0ce8f4a3657c3", "0b7b225d6921d1e07569174e058c52f53f819ffea55eaf49f7086d3a5c9326cb"),
 "ja": ("66eb48c224294f16a5aae3500964b756d9d23354", "apache-2.0", "90b0e01385f90809f7818ffcc14d7ba18070b63e58af0aa64cc86cb3e703a24c", 359313382, "223300c979885b08b6a44f18b6b76cae49099c6de1a0bc2d5694a32827b3a7ab", "6e4c288df8d20dcc6c015452b3a193b61b328a38f068b40fdcd175a70b775199", "350699e5b7964e11ca27a9cf9f79ba830e9263f9f4929715212d4c57a198261f"),
 "hi": ("354cfa698b7f74497de06606053ddd2e6cf9625a", "apache-2.0", "2499aa855f4a6d76ba583909f53e677fce3cb54f82104291d2afe80b41eea169", 356334100, "0c61b05b008701ae1662361276bb65e93433a052b523113a8811b3da6e88b767", "3cca0ad53c37fa74568151da7514c8af0f5f626fef6ef6d7123d523c0387ed7e", "d0161482752162ab9f8d4bae7522703fa4a8aa83f7d54b265d84c7f3bff7f568"),
 "ar": ("088bb8afed49b11e2a29a7a9b947b479e9ef3eaa", "apache-2.0", "b9829586625dca46c28eaf6654c7e4d6956738eb3b128c77fcb3ef9df31e5b75", 356303343, "96a92ff9bd106f825c878f502fe341f9f0488ace92d3c76dc40a6b30296efedd", "11db53fe59ba173625d65f04a80f457806cbf7c39882d0736a14bb2484ad5e76", "5e1341f75bd7eb203f1434dc866a7b9ee514d11ba237d56bdb7a9e3ed654674f"),
 "fa": ("65462671895cd12adb5a28e1724fc3abdd76c311", "apache-2.0", "b1f2c0687378a71a27567bcaa8e7b374dd81a5adbe12352fc68e43f83e67129f", 356319798, "d1691d3d4a072da1ddc1703ca8ee142f8e0fc0f64fa50f4b76963008262c9f94", "e2aef5d2a7b30e388f6aac36ee89727a5b87d91766e3f8de66acd57034d3b2fc", "ea0cd82d42c96bb066a52c5597a094232de77ccf8ae788b2cb32a6c0867dada8"),
 "tr": ("fc4d78dbc2d076eb21477cee46b826678b50d1ac", "cc-by-4.0", "6ba1e92e5bdeb2d9b4c23d555728f18313c89fe630bf9c55f9d0e09a62c87c74", 356292447, "6641ad4761f75bbba7ca2591b1eaef57d1ab444762bf6a51f2ddbd70bfe3ee2f", "2ae007849038116de688bb77efddfd00d168d4d8452140e595f3ecb1193b135e", "d193ea8d7e0ddc528988a1d75e2300b0e41faffa9aab0316eb65193b258542a6"),
 "es": ("d2b70028033dac453897da0cafaa98ce3a6121b9", "apache-2.0", "6531e09eb1646c7789e90f7d606c23e533e8570c3e6983ae99c0c4a5dfaee775", 356293089, "7aea8bcd8ba1c176f12cc96c1e8f45247548f4de3218106f7352e3d833cfafdc", "df92f631333986701c27877ef743d4ec4046cdfd37ede57fed7f54a00134b791", "fb35e3cc27be526781382a61865019a4d4f5137e865696646b754bbee4a4b631"),
 "de": ("b7d6adf4917ea43121044d99edc72fd4018f55d2", "apache-2.0", "df581a4ef6059fb6058060b06af271c9096b82fad4f0b8ba1f33c8eea027df69", 356289918, "31d0914432f4492a24ce83abfd767421844afe5cef20346a48c6c877dee28378", "dce4b74d3d9a1836212ee35fd79f4ce3d70171b1bf318bc65ff5173fda512d75", "886de150a4ee320f313c4a6e3a6fd866c8d257a883696ad6dab77066dac528dc"),
 "fr": ("c8781e16f7ddf98b43972401061bfc8fb9aee7be", "apache-2.0", "efd4d759980e6351c0e6610644b733a1bc36f30840b31de29274274fb888cec7", 356311445, "e83a3c849e480757fabd9fe927b870581e926407bcc7e1b6dcc8bda1e78a8d78", "bf3e37122369535c84ced3d6d9ea99d0f5baceb690bcd59e81bbbedced02d6f8", "3eeddfbfb63cf3c0ef1b511ae9f1bb15bd35c35d106b2098299d3e63e2459fea"),
 "it": ("e2785517cb23ef5825e64fa87ca7a75546401731", "apache-2.0", "94009e742d5fa40976eb5594e038199e3a3ca81eee21de28c9b86493e7325da5", 356296099, "deee9194b91e4e4f628ff37da6226a9c9cfe564810c917ae545920458723c58e", "0e02772836f5684c5a12df8cb5fe43b4b64174d72109a9f6241053c4dd7d384a", "75328a6c30ae3d2d82ffa19093c7928cf499679af3ba65aabe5f84d21da2233c"),
 "en": ("c0f8960268a23db8e3705ef24d3236e419739975", "apache-2.0", "731ccae6a5d1cddce647cd7c4a2faef9fb31d4a12eab64714e9ff7b6048e7d7b", 356284613, "1ec5eeced764da0e4a4d2e95c1c3470c3235222db0182088beac3e7c67eda8ff", "d03e90d8481c71e1a6251372f601c3691d8a91ca2c7366b8a37e319944a8496e", "8b9f7db8a44110821da1e3211f450e5d4fbbd5582dc96ef4a72a6bf4d76aed8b"),
 # Catalan, published 2026-11-03: from ccoreilly/wav2vec2-large-xlsr-catala@a4467e83 (Apache-2.0; Common Voice ca, CC0, and
 # ParlamentParla, CC-BY-4.0), converted and checked in a folder of its own beside the checkout (Parseh-aligner-ca/)
 "ca": ("89844115311debda6cccc6b9e63e81f9a8f2d01c", "apache-2.0", "1de4a90f79f79bd6eeaad53afbf52a51500d93421f3cebfc5bf2eb1138f798c7", 356294063, "55922b0b9b4c25c14091d212d9e3f117383add0d53a502a5ca6c7fd43f8092cf", "bf96b7120e13cb9116ad01853e2e9868d7db97cfcd168e9d0e3a3793bb838cf4", "5adb99796557bd632515843dd7dbd8d9ecda28a22717236753a881f37ad2ba94"),
}

ALIGN_PINS = {}
for _code, (_revision, _licence, _model, _size, _vocab, _meta, _notice) in _ROWS.items():
    ALIGN_PINS[_code] = {
        "repo": "parseh/aligner-%s" % _code, "revision": _revision, "licence": _licence,
        "files": {"model.int8.onnx": (_model, _size), "vocab.json": (_vocab, None),
                  "preprocessor_config.json": (_PRE[_code], None), "meta.json": (_meta, None),
                  "LICENSE": (_LICENSE if _code != "tr" else "9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411", None),
                  "NOTICE": (_notice, None)}}
