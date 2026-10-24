#!/usr/bin/env python3
"""Точный замер ширины строки в пикселях на часах.

Ширина считается не по метрикам TTF, а по реальным глифам: латиница и цифры
берутся из системного шрифта прошивки (.pbf), кириллица — из расширения в
языковом паке. Именно так текст и рисуется на часах: базовый шрифт, при
отсутствии глифа — расширение (text_resources.c).

    python3 tools/l10n/width.py GOTHIC_24_BOLD "Не беспокоить"
    python3 tools/l10n/width.py --budget            # доступная ширина по ролям
"""

import io
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Меряем по тому паку, который поедет на часы; пока он не собран — по исходному.
PACK = os.path.join(ROOT, "l10n", "build", "ru_RU.pbl")
if not os.path.exists(PACK):
    PACK = os.path.join(ROOT, "pebble-EN-RU-HE.pbl")
# Базовые шрифты берём из того же дерева, что и список слотов (см. _fw_roots):
# метрики кириллицы подгоняются под ту прошивку, которая поедет на часы.
PBF_DIRS = []

# Порядок ресурсов языкового пака = порядок шрифтов в lang_map.json.
# Ресурс №1 — строки, дальше 18 расширений.
# Прошивка разбирает пак по позициям: ресурс 0 — каталог строк, дальше шрифты
# ровно в том порядке, в каком они перечислены в файле «lang» карты ресурсов.
# Держать этот список копией в коде нельзя: у нас он однажды отстал от прошивки
# на два слота (не было GOTHIC_36 и GOTHIC_36_BOLD), и все шрифты после них
# уехали — прошивка читала наш BITHAM_18 как GOTHIC_36, и текст на части
# экранов превращался в кашу. Поэтому читаем список у самой прошивки.
def _fw_roots():
    """Где искать дерево прошивки: сначала тот клон, из которого её собрали.

    Копия в проекте отстаёт от клона (клон тянет свежий main каждой сборкой),
    а раскладка пака обязана совпадать именно с той прошивкой, которая поедет
    на часы. Читать список слотов из отставшей копии — это ровно тот способ,
    которым мы уже потеряли два слота.
    """
    roots = []
    src = os.environ.get("PEBBLE_SRC") or os.path.expanduser("~/pebbleos")
    if os.path.isdir(src):
        roots.append(src)
    roots.append(ROOT and os.path.join(ROOT, "pebbleos"))
    return [r for r in roots if r and os.path.isdir(r)]


def _slots_from(root):
    path = os.path.join(root, "resources", "normal", "base", "resource_map.json")
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as f:
        entries = [e for e in json.load(f)["files"] if e["name"] == "lang"]
    if not entries:
        return None
    suffix = "_EXTENDED"
    names = [r[:-len(suffix)] if r.endswith(suffix) else r for r in entries[0]["resources"]]
    if names[0] != "STRINGS":
        raise SystemExit("первый ресурс пака должен быть STRINGS, а не " + names[0])
    return names[1:]


def _lang_slots():
    found = [(root, _slots_from(root)) for root in _fw_roots()]
    found = [(root, slots) for root, slots in found if slots]
    if not found:
        raise SystemExit("не нашёл карту ресурсов прошивки — из чего собирать пак, непонятно")
    root, slots = found[0]
    # Расхождение между клоном и копией в проекте — это сигнал, что пак собран
    # не под ту прошивку. Молчать тут нельзя: на часах это выглядит как
    # случайные глифы, а не как понятная ошибка.
    for other_root, other in found[1:]:
        if other != slots:
            print("ВНИМАНИЕ: списки слотов расходятся. %s: %d слотов, "
                  "%s: %d слотов. Беру первый; копию в проекте стоит обновить"
                  % (root, len(slots), other_root, len(other)), file=sys.stderr)
    return slots


LANG_MAP_FONTS = _lang_slots()

for _root in _fw_roots():
    for _kind in ("common", "normal"):
        _dir = os.path.join(_root, "resources", _kind, "base", "pbf")
        if os.path.isdir(_dir):
            PBF_DIRS.append(_dir)

# Экран Pebble Time 2 — 200x228. Доступная ширина под текст по ролям:
# отступы меню и полоса прокрутки съедают часть строки.
BUDGETS = {
    "пункт меню": 176,
    "подпись под пунктом": 176,
    "заголовок окна": 168,
    "кнопка действия": 150,
    "текст во всю ширину": 192,
}


def _parse_pbf(data):
    """Вернуть {codepoint: horiz_advance}."""
    ver, _max_h, _n, _wild = struct.unpack_from("<BBHH", data, 0)
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
    glyphs_at = tables
    # Конец таблиц смещений = начало таблицы глифов: считаем по максимуму.
    ends = []
    out = {}
    raw = []
    for i in range(hts):
        _h, cnt, o = struct.unpack_from("<BBH", data, off + i * 4)
        for j in range(cnt):
            p = tables + o + j * entry
            cp = struct.unpack_from("<H" if cpb == 2 else "<I", data, p)[0]
            go = struct.unpack_from("<H" if off_bytes == 2 else "<I", data, p + cpb)[0]
            raw.append((cp, go))
            ends.append(p + entry)
    glyphs_at = max(ends) if ends else tables
    for cp, go in raw:
        if go == 0:
            continue
        pos = glyphs_at + go
        if pos + 5 > len(data):
            continue
        _w, _h, _l, _t, adv = struct.unpack_from("<BBbbb", data, pos)
        out[cp] = adv
    return out


def _pack_resources(path):
    data = open(path, "rb").read()
    num = struct.unpack_from("<I", data, 0)[0]
    out = []
    for n in range(num):
        _fid, o, ln, _c = struct.unpack_from("<IIII", data, 12 + n * 16)
        out.append(data[0x100C + o:0x100C + o + ln])
    return out


_fonts = {}


def font_metrics(name):
    """Слить метрики базового шрифта и расширения из пака."""
    if name in _fonts:
        return _fonts[name]
    metrics = {}
    for d in PBF_DIRS:
        p = os.path.join(d, name + ".pbf")
        if os.path.exists(p):
            metrics.update(_parse_pbf(open(p, "rb").read()))
            break
    else:
        raise SystemExit(f"нет базового шрифта {name}.pbf")
    if name in LANG_MAP_FONTS:
        res = _pack_resources(PACK)
        ext = res[1 + LANG_MAP_FONTS.index(name)]
        for cp, adv in _parse_pbf(ext).items():
            metrics.setdefault(cp, adv)  # базовый шрифт имеет приоритет
    _fonts[name] = metrics
    return metrics


def text_width(name, text):
    m = font_metrics(name)
    missing = [c for c in text if ord(c) not in m]
    width = sum(m.get(ord(c), 0) for c in text)
    return width, missing


def main():
    if "--budget" in sys.argv:
        for role, px in BUDGETS.items():
            print(f"{px:4d} px  {role}")
        return
    if len(sys.argv) < 3:
        print(__doc__)
        return
    name, text = sys.argv[1], sys.argv[2]
    width, missing = text_width(name, text)
    print(f"{name}: {text!r} = {width} px")
    if missing:
        print("нет глифов для:", "".join(missing))


if __name__ == "__main__":
    main()
