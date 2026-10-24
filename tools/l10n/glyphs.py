#!/usr/bin/env python3
"""Сравнить глифы системного шрифта и расширения из языкового пака.

Шрифты Pebble — однобитные растры (fontgen грузит freetype с FT_LOAD_MONOCHROME),
поэтому «сглаженности» в смысле сглаживания краёв не бывает ни у английского, ни
у русского. Разница, которая читается как «жирно и резко», — это метрики: высота
знака, толщина штриха и плотность заливки. Их и меряем.

    python3 tools/l10n/glyphs.py GOTHIC_24_BOLD HН
"""

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "l10n"))

import width as widthmod  # noqa: E402


def parse_font(data):
    """Вернуть (features, {codepoint: (header, bitmap_bytes)})."""
    ver, max_h, _n, _wild = struct.unpack_from("<BBHH", data, 0)
    off, hts, cpb, feat = 6, 255, 2, 0
    if ver >= 2:
        hts, cpb = struct.unpack_from("<BB", data, 6)
        off = 8
    if ver >= 3:
        _size, feat = struct.unpack_from("<BB", data, 8)
        off = 10
    off_bytes = 2 if (feat & 1) else 4
    entry = cpb + off_bytes
    tables = off + hts * 4
    raw, ends = [], []
    for i in range(hts):
        _h, cnt, o = struct.unpack_from("<BBH", data, off + i * 4)
        for j in range(cnt):
            p = tables + o + j * entry
            cp = struct.unpack_from("<H" if cpb == 2 else "<I", data, p)[0]
            go = struct.unpack_from("<H" if off_bytes == 2 else "<I", data, p + cpb)[0]
            raw.append((cp, go))
            ends.append(p + entry)
    glyphs_at = max(ends) if ends else tables
    out = {}
    for cp, go in raw:
        if go == 0:
            continue
        pos = glyphs_at + go
        out[cp] = (struct.unpack_from("<BBbbb", data, pos), data[pos + 5:pos + 5 + 512])
    return max_h, feat, out


def render(header, blob):
    """ASCII-картинка глифа. Биты идут сплошным потоком, младший — первый."""
    w, h, left, bottom, adv = header
    rows = []
    for y in range(h):
        row = ""
        for x in range(w):
            i = y * w + x
            bit = (blob[i // 8] >> (i % 8)) & 1 if i // 8 < len(blob) else 0
            row += "#" if bit else "."
        rows.append(row)
    return rows, (w, h, left, bottom, adv)


def stats(rows):
    ink = sum(r.count("#") for r in rows)
    cells = sum(len(r) for r in rows) or 1
    stems = []
    for r in rows:
        run = 0
        for ch in r:
            if ch == "#":
                run += 1
            elif run:
                stems.append(run)
                run = 0
        if run:
            stems.append(run)
    stem = min(stems) if stems else 0
    return ink, round(100 * ink / cells), stem


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "GOTHIC_24_BOLD"
    chars = sys.argv[2] if len(sys.argv) > 2 else "HН"

    base_path = None
    for d in widthmod.PBF_DIRS:
        p = os.path.join(d, name + ".pbf")
        if os.path.exists(p):
            base_path = p
            break
    max_h_base, feat_base, base = parse_font(open(base_path, "rb").read())

    res = widthmod._pack_resources(widthmod.PACK)
    ext_blob = res[1 + widthmod.LANG_MAP_FONTS.index(name)]
    max_h_ext, feat_ext, ext = parse_font(ext_blob)

    print(f"{name}: базовый max_height={max_h_base} RLE={bool(feat_base & 2)}, "
          f"расширение max_height={max_h_ext} RLE={bool(feat_ext & 2)}")

    for ch in chars:
        cp = ord(ch)
        source, table = ("база", base) if cp in base else ("пак", ext)
        if cp not in table:
            print(f"  {ch!r}: нет глифа")
            continue
        rows, (w, h, left, bottom, adv) = render(*table[cp])
        ink, density, stem = stats(rows)
        print(f"\n  {ch!r} ({source}): {w}x{h}, отступ слева {left}, "
              f"низ {bottom}, шаг {adv}, чернил {ink} ({density}%), тонкий штрих {stem}px")
        for r in rows:
            print("      " + r)


if __name__ == "__main__":
    main()
