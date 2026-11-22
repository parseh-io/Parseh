#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the three transcript-review skill ZIPs from their folders, byte for byte the same every time.

    python3 lib/asrskill/build.py           write lib/asrskill/<skill>.zip
    python3 lib/asrskill/build.py --check   exit 1 when a ZIP differs from what its folder builds

Each ZIP, stored without compression, holds the skill's folder (its SKILL.md first, then every other file, sorted) and this folder's
README.txt at the root.  Every entry has the same date and mode, so the bytes depend only on the files:
run it after editing a SKILL.md or scripts/review.py (tests/test_asr_skill_zips.py fails until then).
"""
import io
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = ("parseh-asr-correction", "parseh-asr-audit", "parseh-asr-workspace")
DATE = (2026, 11, 22, 0, 0, 0)


def entries(skill):
    folder = HERE / skill
    files = sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.sort(key=lambda p: p.name != "SKILL.md")
    out = [(skill + "/" + p.relative_to(folder).as_posix(), p.read_bytes()) for p in files]
    out.append(("README.txt", (HERE / "README.txt").read_bytes()))
    return out


def build(skill):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in entries(skill):
            info = zipfile.ZipInfo(name, DATE)
            info.compress_type = zipfile.ZIP_STORED     # deflate differs between zlib builds (zlib-ng)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return stream.getvalue()


def main(argv):
    stale = []
    for skill in SKILLS:
        data, path = build(skill), HERE / (skill + ".zip")
        if "--check" in argv:
            if not path.is_file() or path.read_bytes() != data:
                stale.append(path.name)
        else:
            path.write_bytes(data)
            print("wrote", path.name, len(data), "bytes")
    if stale:
        print("out of date:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
