#!/usr/bin/env python3
"""Проверить, что кириллица в паке рисуется, а не превращается в кашу.

На часах бывает, что часть букв в слове выходит нечитаемым пятном. Причина
обычно одна из трёх: глифа нет вовсе и рисуется заглушка; у глифа поехали
метрики — ширина не совпадает с растром; или слот в паке пустой.

Кто выигрывает, базовый шрифт или расширение, решает prv_font_res_for_codepoint
в src/fw/applib/graphics/text_resources.c: латиница (до U+02AF), символы
U+2000–U+2BFF, эмодзи и служебные U+E0A0–U+E0A2 ищутся в базовом, всё
остальное — сначала в расширении. Кириллица, значит, всегда наша, даже если
такой же код есть в базовом шрифте. Мы на этом обожглись в обратную сторону:
приняли посторонний глиф в базовом GOTHIC_36 за причину испорченной «з», хотя
прошивка до него даже не доходит.

Скрипт проходит по всем нашим расширениям и по всему русскому алфавиту и
докладывает, где чего не хватает.

    python3 tools/l10n/check-glyphs.py
    python3 tools/l10n/check-glyphs.py GOTHIC_28
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "l10n"))

import width as widthmod  # noqa: E402
from glyphs import parse_font, render, stats  # noqa: E402

def _routed_to_base(cp):
    """Ищет ли прошивка этот код сначала в базовом шрифте.

    Повторяет codepoint_is_latin / codepoint_is_special из
    src/fw/applib/fonts/codepoint.c. Эмодзи сюда не входят: они уходят в
    отдельный шрифт, а не в базовый слот пака.
    """
    return cp <= 0x02AF or 0x2000 <= cp <= 0x2BFF or 0xE0A0 <= cp <= 0xE0A2


ALPHABET = ("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
            "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
            "«»—…№")


def base_font(name):
    for d in widthmod.PBF_DIRS:
        p = os.path.join(d, name + ".pbf")
        if os.path.exists(p):
            return parse_font(open(p, "rb").read())
    return None, 0, {}


def check(name):
    max_h_base, _feat_base, base = base_font(name)
    res = widthmod._pack_resources(widthmod.PACK)
    blob = res[1 + widthmod.LANG_MAP_FONTS.index(name)]
    if not blob:
        # Пустой слот уже назван в check_layout(), тут просто нечего разбирать.
        print("%-18s слот пустой" % name)
        return []
    max_h_ext, _feat_ext, ext = parse_font(blob)

    missing, broken = [], []
    for ch in ALPHABET:
        cp = ord(ch)
        # Прошивка сначала смотрит туда, куда код относит классификация, а при
        # промахе — во второй ресурс того же шрифта. Значит важно одно: есть ли
        # глиф хоть где-то. Если он в базовом шрифте — это не «перекрытие», а
        # штатный путь: кавычки и тире там и должны браться.
        in_base, in_ext = cp in base, cp in ext
        if not in_base and not in_ext:
            missing.append(ch)
            continue
        if not in_ext:
            continue  # рисуется базовым шрифтом, мерить нечего

        rows, (w, h, _left, _bottom, adv) = render(*ext[cp])
        ink, _density, _stem = stats(rows)
        if ink == 0:
            broken.append((ch, "пустой растр"))
        elif w > adv + 2:
            broken.append((ch, "растр %d шире шага %d" % (w, adv)))
        elif h > max_h_ext and not in_base:
            broken.append((ch, "высота %d больше max_height %d" % (h, max_h_ext)))

    problems = []
    print("%-18s база max_height=%s, расширение max_height=%s, глифов %d"
          % (name, max_h_base, max_h_ext, len(ext)))
    if missing:
        problems.append("нет ни в базовом шрифте, ни в расширении: " + "".join(missing))
    for ch, why in broken:
        problems.append("«%s»: %s" % (ch, why))
    for p in problems:
        print("   * " + p)
    return problems


def check_layout():
    """Число ресурсов в паке обязано совпадать с тем, что ждёт прошивка.

    Прошивка разбирает пак по позициям. Если слотов меньше, чем в её карте
    ресурсов, все шрифты после пропущенного читаются как соседние — и текст
    на части экранов превращается в кашу. Мы так потеряли GOTHIC_36 и
    GOTHIC_36_BOLD, и всё после них уехало на два слота.
    """
    res = widthmod._pack_resources(widthmod.PACK)
    expected = 1 + len(widthmod.LANG_MAP_FONTS)
    print("ресурсов в паке: %d, прошивка ждёт: %d" % (len(res), expected))
    if len(res) != expected:
        print("   * РАСКЛАДКА СЪЕХАЛА: шрифты после пропущенного слота "
              "будут прочитаны как соседние")
        return 1
    empty = [widthmod.LANG_MAP_FONTS[i - 1] for i in range(1, len(res)) if not res[i]]
    if empty:
        print("   * пустые слоты: %s — кириллицы в этих шрифтах не будет"
              % ", ".join(empty))
    return 0


def main():
    names = sys.argv[1:] or widthmod.LANG_MAP_FONTS
    bad = check_layout()
    print()
    for name in names:
        if name not in widthmod.LANG_MAP_FONTS:
            print("%s: не наше расширение, пропускаю" % name)
            continue
        bad += len(check(name))
    print()
    print("проблем: %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
