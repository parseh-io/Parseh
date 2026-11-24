# SPDX-License-Identifier: GPL-3.0-or-later
"""A QR code as an SVG, for Settings -> Devices (a0.7.0): the pairing code a
phone or another computer can read off this screen.

    qrsvg.svg("parseh-pair:1?code=...")   -> '<svg ...>'   (byte mode, level M)
    qrsvg.matrix(text, ecl="M")           -> [[bool]]       (dark modules)

Standard library only, no network.  The encoder follows the layout of Project
Nayuki's "QR Code generator library" (MIT): byte mode, versions 1-40, the
four error-correction levels, the eight masks chosen by the standard's
penalty.  It is drawn ink on paper, with the four-module quiet zone, so it
reads in both themes.
"""

ECC_PER_BLOCK = {
    "L": (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "M": (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28,
          28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    "Q": (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "H": (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
}
BLOCKS = {
    "L": (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17,
          18, 19, 19, 20, 21, 22, 24, 25),
    "M": (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28,
          29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    "Q": (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38,
          40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    "H": (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42,
          45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
}
FORMAT_ECL = {"L": 1, "M": 0, "Q": 3, "H": 2}


def _raw_modules(ver):
    n = (16 * ver + 128) * ver + 64
    if ver >= 2:
        k = ver // 7 + 2
        n -= (25 * k - 10) * k - 55
        if ver >= 7:
            n -= 36
    return n


def _data_codewords(ver, ecl):
    return _raw_modules(ver) // 8 - ECC_PER_BLOCK[ecl][ver] * BLOCKS[ecl][ver]


def _gf_mul(x, y):
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z & 0xFF


def _rs_divisor(degree):
    r = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            r[j] = _gf_mul(r[j], root)
            if j + 1 < degree:
                r[j] ^= r[j + 1]
        root = _gf_mul(root, 0x02)
    return r


def _rs_remainder(data, div):
    r = [0] * len(div)
    for b in data:
        f = b ^ r.pop(0)
        r.append(0)
        for i, c in enumerate(div):
            r[i] ^= _gf_mul(c, f)
    return r


def _alignment(ver):
    if ver == 1:
        return []
    num = ver // 7 + 2
    step = (ver * 8 + num * 3 + 5) // (num * 4 - 4) * 2
    out = [ver * 4 + 10 - i * step for i in range(num - 1)] + [6]
    return sorted(out)


def _codewords(data, ver, ecl):
    nblocks, ecclen = BLOCKS[ecl][ver], ECC_PER_BLOCK[ecl][ver]
    raw = _raw_modules(ver) // 8
    short = nblocks - raw % nblocks
    shortlen = raw // nblocks
    div = _rs_divisor(ecclen)
    blocks, k = [], 0
    for i in range(nblocks):
        dat = data[k:k + shortlen - ecclen + (0 if i < short else 1)]
        k += len(dat)
        ecc = _rs_remainder(dat, div)
        if i < short:
            dat = dat + [0]
        blocks.append(dat + ecc)
    out = []
    for i in range(len(blocks[0])):
        for j, b in enumerate(blocks):
            if i != shortlen - ecclen or j >= short:
                out.append(b[i])
    return out


def matrix(text, ecl="M", mask=None):
    data = text.encode("utf-8") if isinstance(text, str) else bytes(text)
    for ver in range(1, 41):
        cc = 16 if ver >= 10 else 8
        need = 4 + cc + 8 * len(data)
        if need <= _data_codewords(ver, ecl) * 8:
            break
    else:
        raise ValueError("too long for a QR code")
    bits = [int(c) for c in format(0b0100, "04b") + format(len(data), "0%db" % cc)]
    for b in data:
        bits += [int(c) for c in format(b, "08b")]
    cap = _data_codewords(ver, ecl) * 8
    bits += [0] * min(4, cap - len(bits))
    bits += [0] * ((8 - len(bits) % 8) % 8)
    pad = 0xEC
    while len(bits) < cap:
        bits += [int(c) for c in format(pad, "08b")]
        pad ^= 0xEC ^ 0x11
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    allw = _codewords(words, ver, ecl)

    size = ver * 4 + 17
    m = [[False] * size for _ in range(size)]
    fn = [[False] * size for _ in range(size)]

    def setf(x, y, dark):
        m[y][x] = dark
        fn[y][x] = True

    for i in range(size):
        setf(6, i, i % 2 == 0)
        setf(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                d = max(abs(dx), abs(dy))
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    setf(x, y, d not in (2, 4))
    al = _alignment(ver)
    n = len(al)
    for i in range(n):
        for j in range(n):
            if (i == 0 and j == 0) or (i == 0 and j == n - 1) or (i == n - 1 and j == 0):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    setf(al[i] + dx, al[j] + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format(msk):
        d = FORMAT_ECL[ecl] << 3 | msk
        rem = d
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        b = (d << 10 | rem) ^ 0x5412
        bit = lambda i: (b >> i) & 1 == 1          # noqa: E731
        for i in range(0, 6):
            setf(8, i, bit(i))
        setf(8, 7, bit(6))
        setf(8, 8, bit(7))
        setf(7, 8, bit(8))
        for i in range(9, 15):
            setf(14 - i, 8, bit(i))
        for i in range(0, 8):
            setf(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            setf(8, size - 15 + i, bit(i))
        setf(8, size - 8, True)

    draw_format(0)
    if ver >= 7:
        rem = ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        b = ver << 12 | rem
        for i in range(18):
            dark = (b >> i) & 1 == 1
            a, c = size - 11 + i % 3, i // 3
            setf(a, c, dark)
            setf(c, a, dark)

    i = 0
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                upward = ((right + 1) & 2) == 0
                y = size - 1 - vert if upward else vert
                if not fn[y][x] and i < len(allw) * 8:
                    m[y][x] = (allw[i >> 3] >> (7 - (i & 7))) & 1 == 1
                    i += 1
        right -= 2

    masks = (lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
             lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
             lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
             lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0)

    def apply(msk):
        f = masks[msk]
        for y in range(size):
            for x in range(size):
                if not fn[y][x] and f(x, y):
                    m[y][x] = not m[y][x]

    if mask is None:
        best, bestp = 0, None
        for k in range(8):
            apply(k)
            draw_format(k)
            p = _penalty(m)
            if bestp is None or p < bestp:
                best, bestp = k, p
            apply(k)
        mask = best
    apply(mask)
    draw_format(mask)
    return m


def _penalty(m):
    size = len(m)
    res = 0

    def lines():
        for y in range(size):
            yield m[y]
        for x in range(size):
            yield [m[y][x] for y in range(size)]

    for line in lines():
        # runs of five or more
        run, last = 0, None
        for v in line:
            if v == last:
                run += 1
            else:
                if run >= 5:
                    res += run - 2
                run, last = 1, v
        if run >= 5:
            res += run - 2
        # finder-like patterns 1:1:3:1:1 with four light on one side
        s = "".join("1" if v else "0" for v in line)
        for pat in ("10111010000", "00001011101"):
            start = s.find(pat)
            while start != -1:
                res += 40
                start = s.find(pat, start + 1)
    for y in range(size - 1):
        for x in range(size - 1):
            c = m[y][x]
            if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                res += 3
    dark = sum(v for row in m for v in row)
    total = size * size
    k = (abs(dark * 20 - total * 10) + total - 1) // total - 1
    res += k * 10
    return res


def svg(text, ecl="M", module=4, label=""):
    """The code as an SVG: dark modules as one path on a light ground, with
    the quiet zone of four modules the standard asks."""
    m = matrix(text, ecl)
    size = len(m)
    q = 4
    full = (size + 2 * q) * module
    parts = []
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                parts.append("M%d %dh%dv%dh-%dz" % ((x + q) * module, (y + q) * module, module, module, module))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
            'aria-label="%s" shape-rendering="crispEdges"><rect width="100%%" height="100%%" fill="#fff"/>'
            '<path fill="#000" d="%s"/></svg>' % (full, full, full, full,
                                                  (label or "QR code").replace('"', "&quot;"), "".join(parts)))
