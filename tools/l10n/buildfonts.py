#!/usr/bin/env python3
"""Собрать кириллические расширения системных шрифтов родным fontgen прошивки.

Расширение рисуется в одну строку с латиницей базового шрифта, поэтому важны две
вещи, которых не сделал сторонний сборщик прежнего пака:

* пиксельный размер подобран так, чтобы высота прописных совпала с латинской
  (подбор — tools/l10n/fontfit.py, цифры зашиты в SLOTS ниже);
* базовая линия передаётся от базового шрифта, иначе строка «прыгает»
  (resource_generator_font.py делает ровно это для extended-шрифтов).

* вес жирных начертаний берётся с вариативной оси wght и подобран так, чтобы
  штрих совпал с латинским (подбор — tools/l10n/weightsweep.py), а не
  подделывается утолщением, как в прежнем паке.

    bash tools/l10n/buildfonts.sh
"""

import argparse
import json
import os
import sys
import tempfile
import freetype

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FW_SOURCE = os.environ.get("PEBBLE_SRC", os.path.join(ROOT, "pebbleos"))
sys.path.insert(0, os.path.join(FW_SOURCE, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "l10n"))

from font.fontgen import MAX_GLYPHS_EXTENDED, Font  # noqa: E402

import glyphs  # noqa: E402
import width as widthmod  # noqa: E402

MAX_GLYPH_SIZE = 256  # pebble_sdk_platform.py, emery

# Одна вариативная гарнитура на все слоты: вес берётся с оси wght, а не
# подделывается утолщением, как это делал прежний пак.
ROBOTO_COND = os.path.join(ROOT, "l10n", "fonts", "RobotoCondensed-Variable.ttf")
#: Ноту берём вариативной: у Bitham есть Light, Medium, Bold и Black, и вес
#: приходится ставить по оси, а не выбирать из готовых файлов.
NOTO = os.path.join(ROOT, "l10n", "fonts", "NotoSans-Variable.ttf")
#: Эти три гарнитуры лежат в самой прошивке — из них она и собирает базовые
#: начертания. Значит расширение строится ТОЙ ЖЕ гарнитурой, а не похожей, и
#: кириллица встаёт рядом с латиницей без подмены рисунка.
FW_TTF = os.path.join(FW_SOURCE, "resources", "normal", "base", "ttf")
DROID_SERIF_BOLD = os.path.join(FW_TTF, "DroidSerif-Bold.ttf")
ROBOTO_CONDENSED = os.path.join(FW_TTF, "Roboto-Condensed.ttf")
ROBOTO_BOLD = os.path.join(FW_TTF, "Roboto-Bold.ttf")

# слот пака -> (пиксельный размер, вес). Размер подобран fontfit.py по высоте
# прописных, вес — weightsweep.py по толщине штриха соседней латиницы.
# Вес обычных начертаний подобран по плотности заливки (tools/l10n/weightfit.py):
# на 400 кириллица в слотах 18 и 24 выходила на девять процентных пунктов плотнее
# соседней латиницы — правая стойка «Н» вставала в два пикселя против одного, и
# латинское слово в русской строке выглядело набранным другим, более тонким
# шрифтом. У слотов 14 и 28 растр совпадает уже на 400.
SLOTS = {
    # слот: (px, вес по оси или None, гарнитура)
    "GOTHIC_14":      (12, 400, ROBOTO_COND),
    "GOTHIC_14_BOLD": (13, 700, ROBOTO_COND),
    "GOTHIC_18":      (15, 375, ROBOTO_COND),
    "GOTHIC_18_BOLD": (15, 700, ROBOTO_COND),
    "GOTHIC_24":      (20, 325, ROBOTO_COND),
    "GOTHIC_24_BOLD": (20, 500, ROBOTO_COND),
    "GOTHIC_28":      (25, 400, ROBOTO_COND),
    "GOTHIC_28_BOLD": (25, 700, ROBOTO_COND),
    # 36-й кегль используется только при самом крупном системном размере
    # текста. Без этих слотов пак разъезжался с прошивкой на две позиции.
    "GOTHIC_36":      (30, 350, ROBOTO_COND),
    "GOTHIC_36_BOLD": (30, 700, ROBOTO_COND),

    # Дальше — начертания, которые прежде брались готовыми из чужого пака. В
    # них не было «», — и №, а в BITHAM_18 буква «ф» вылезала за объявленную
    # высоту и обрезалась. Собираем сами: размеры и веса подобраны замером
    # (tools/l10n/fitslots.py) по высоте прописных, базовой линии, штриху и
    # плотности заливки — тем же четырём величинам, что и у слотов GOTHIC.
    #
    # Bitham в дереве прошивки нет: она несёт только готовые .pbf. Донором взят
    # Noto Sans — гротеск близкой пропорции с полным кириллическим блоком.
    "BITHAM_18_LIGHT_SUBSET":   (18, 300, NOTO),
    "BITHAM_30_BLACK":          (30, 900, NOTO),
    "BITHAM_34_LIGHT_SUBSET":   (35, 300, NOTO),
    "BITHAM_34_MEDIUM_NUMBERS": (33, 500, NOTO),
    "BITHAM_42_BOLD":           (40, 700, NOTO),
    "BITHAM_42_LIGHT":          (40, 250, NOTO),
    # Единственный слот, где точного попадания нет: нужна высота 30, на 40px
    # выходит 29, а на 41px редкие буквы кириллического блока перерастают предел
    # SDK в 256 байт на глиф. Пиксель расхождения на цифровом начертании,
    # которым кириллицу почти не набирают, дешевле отсутствия букв вовсе.
    "BITHAM_42_MEDIUM_NUMBERS": (40, 500, NOTO),

    # Эти три прошивка собирает из TTF, лежащих рядом. Гарнитура та же самая,
    # поэтому подбирать нечего: размер записан в самом имени слота.
    "DROID_SERIF_28_BOLD":  (28, None, DROID_SERIF_BOLD),
    "ROBOTO_CONDENSED_21":  (21, None, ROBOTO_CONDENSED),
    "ROBOTO_BOLD_SUBSET_49": (49, None, ROBOTO_BOLD),
}

# Newer firmware appends LECO extensions without changing the older resource IDs.
# Match cap height and baseline to the actual firmware PBFs.
LECO_SLOTS = {
    "LECO_20_BOLD_NUMBERS": (20, 900, ROBOTO_COND),
    "LECO_26_BOLD_NUMBERS_AM_PM": (25, 900, ROBOTO_COND),
    "LECO_32_BOLD_NUMBERS": (32, 900, ROBOTO_COND),
    "LECO_36_BOLD_NUMBERS": (35, 750, ROBOTO_COND),
    "LECO_38_BOLD_NUMBERS": (38, 750, ROBOTO_COND),
    "LECO_42_NUMBERS": (41, 850, ROBOTO_COND),
    "LECO_28_LIGHT_NUMBERS": (28, 350, ROBOTO_COND),
    "LECO_60_NUMBERS_AM_PM": (59, 850, ROBOTO_COND),
    "LECO_60_BOLD_NUMBERS_AM_PM": (59, 900, ROBOTO_COND),
}
SLOTS.update({name: metrics for name, metrics in LECO_SLOTS.items()
              if name in widthmod.LANG_MAP_FONTS})


# Весь кириллический блок: пак нужен не только нашему интерфейсу, но и русским
# уведомлениям с телефона, где встретится любая буква.
CODEPOINTS = os.path.join(
    ROOT, "l10n", "upstream", "ru_RU", "codepoints.json")

# Знаки вне кириллического блока, которых нет в базовых шрифтах, но которые
# встречаются в русском тексте. Рубль вылез на экране уведомления: «Списание
# 1 249 ₽» рисовалось с квадратом вместо знака.
EXTRA_CODEPOINTS = {
    0x2116: "№",
    0x20BD: "₽",
    # Кавычки-ёлочки и тире: в русском тексте они основные, а в наборе
    # прошивки их нет — он собран под латиницу, где кавычки другие. Пока
    # расширения брались готовыми из чужого пака, их не было ни там, ни тут, и
    # «Погода» в кавычках рисовалась с квадратами по краям.
    0x00AB: "«",
    0x00BB: "»",
    0x2014: "—",
}


#: Слоты, которым расхождение прощается, с причиной. Всё остальное валит
#: сборку: разошедшаяся высота прописных или базовая линия видна на экране как
#: прыгающая строка, и узнавать о ней из строчки в логе поздно.
KNOWN_MISMATCH = {
    # Нужна высота 30, на 40px выходит 29, а на 41px редкие буквы кириллицы
    # перерастают предел SDK в 256 байт на глиф. Начертание цифровое,
    # кириллицей его почти не набирают.
    "BITHAM_42_MEDIUM_NUMBERS": "пиксель по высоте, упирается в предел глифа",
    "LECO_60_BOLD_NUMBERS_AM_PM": "нет кириллического донора с таким же сверхжирным штрихом",
}

# Насколько плотность кириллицы может разойтись с латиницей, в процентных
# пунктах. Растр однобитный, попасть точка в точку получается не всегда.
DENSITY_TOLERANCE = 3.0

# Пары букв для замера плотности. По одной судить нельзя: на «Н» вес ложится
# иначе, чем на «О», и слот, совпадающий по «Н», может разойтись по остальным.
DENSITY_PAIRS = [("H", "Н"), ("K", "К"), ("O", "О"), ("E", "Е"), ("T", "Т")]


def mean_density(table, letters):
    """Средняя плотность заливки по набору букв, в процентах."""
    values = []
    for letter in letters:
        if ord(letter) not in table:
            continue
        rows, _metrics = glyphs.render(*table[ord(letter)])
        _ink, density, _stem = glyphs.stats(rows)
        values.append(density)
    return sum(values) / len(values) if values else 0.0


#: Латиница, которой хватает для замера базового начертания, собранного из TTF.
BASE_PROBE = [ord(c) for c in "HEFTIKLMNPRBhknmi0123456789"]


def base_from_ttf(slot):
    """Метрики базового начертания, собранного из той же TTF, что и в прошивке.

    Нужно для слотов без готового .pbf. Гарнитура и размер берутся из SLOTS —
    те же, что использует прошивка, — поэтому расширение совпадёт с базой не по
    подбору, а по построению.
    """
    px, weight, font_path = SLOTS[slot]
    font = Font(font_path, px, MAX_GLYPHS_EXTENDED, MAX_GLYPH_SIZE, False)
    if weight is not None:
        font.face.set_var_design_coords([weight])
    font.face.set_pixel_sizes(0, px)
    # set_codepoint_list берёт путь к файлу, а не список.
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"codepoints": BASE_PROBE}, f)
        probe_path = f.name
    try:
        font.set_codepoint_list(probe_path)
        font.build_tables()
    finally:
        os.unlink(probe_path)
    max_h, _feat, table = glyphs.parse_font(font.bitstring())
    ref = next((c for c in "HEFTIKLMNPRB" if ord(c) in table), None)
    if ref is None:
        raise SystemExit(f"{slot}: в собранной базе нет буквы для эталона")
    rows, (_w, cap_h, _left, bottom, _adv) = glyphs.render(*table[ord(ref)])
    _ink, _density, stem = glyphs.stats(rows)
    density = mean_density(table, [lat for lat, _cyr in DENSITY_PAIRS])
    return max_h, cap_h, bottom, stem, density


def base_font_metrics(slot):
    """Метрики эталонной латинской буквы из .pbf прошивки.

    Возвращает высоту слота, высоту буквы, базовую линию, штрих и плотность.
    """
    for d in widthmod.PBF_DIRS:
        path = os.path.join(d, slot + ".pbf")
        if os.path.exists(path):
            break
    else:
        # Готового .pbf нет: часть начертаний прошивка строит из TTF при сборке
        # (ROBOTO_CONDENSED_21, ROBOTO_BOLD_SUBSET_49). Собираем базовое сами —
        # той же гарнитурой и тем же размером, что и она, — и меряем по нему.
        return base_from_ttf(slot)
    max_h, _feat, table = glyphs.parse_font(open(path, "rb").read())

    # Эталон — прописная, но она есть не везде: BITHAM_18_LIGHT_SUBSET несёт
    # ровно «-/hikmn», а начертания «…_NUMBERS» — одни цифры. Тогда идут
    # строчные, потом цифры: высота цифры совпадает с высотой прописной, и как
    # эталон строки она годится.
    ref = next((c for c in "HEFTIKLMNPRB" if ord(c) in table), None)
    if ref is None:
        ref = next((c for c in "hknmi" if ord(c) in table), None)
    if ref is None:
        ref = next((c for c in "0123456789" if ord(c) in table), None)
    if ref is None:
        raise SystemExit(f"в {slot}.pbf не нашлось буквы для эталона")

    rows, (_w, cap_h, _left, bottom, _adv) = glyphs.render(*table[ord(ref)])
    _ink, _density, stem = glyphs.stats(rows)
    density = mean_density(table, [lat for lat, _cyr in DENSITY_PAIRS])
    return max_h, cap_h, bottom, stem, density


def codepoint_file(out_dir):
    """Список кодовых точек прошивки плюс наши добавки, одним файлом."""
    with open(CODEPOINTS) as f:
        data = json.load(f)
    points = list(data["codepoints"])
    for cp in EXTRA_CODEPOINTS:
        if cp not in points:
            points.append(cp)
    data["codepoints"] = sorted(points)
    path = os.path.join(out_dir, "codepoints.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path, len(points)


def modern_codepoint_file(out_dir):
    """Только современная русская азбука плюс наши добавки.

    Запасной набор для крупных кеглей. Предел SDK — 256 байт на глиф, и на
    сорока девяти пикселях в него перестают влезать редкие буквы кириллического
    блока: Ѹ на ROBOTO_BOLD_SUBSET_49 занимает 315 байт. Терять из-за неё всю
    кириллицу неправильно — в русском тексте она не встречается вовсе.
    """
    points = [ord(c) for c in
              "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"]
    points += list(EXTRA_CODEPOINTS)
    path = os.path.join(out_dir, "codepoints_modern.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"codepoints": sorted(set(points))}, f)
    return path


def build(slot, px, weight, font_path, out_dir, codepoints):
    baseline, base_cap, base_top, base_stem, base_density = base_font_metrics(slot)

    def render(points):
        font = Font(font_path, px, MAX_GLYPHS_EXTENDED, MAX_GLYPH_SIZE, False,
                    baseline=baseline)
        # Вес ставится по оси только у вариативных гарнитур. У обычных её нет,
        # и начертание уже такое, какое нужно: DroidSerif-Bold жирный сам по
        # себе.
        if weight is not None:
            font.face.set_var_design_coords([weight])
        font.face.set_pixel_sizes(0, px)
        if slot.startswith("LECO_60"):
            # Keep the cap height while fitting wide Cyrillic glyphs in the SDK's
            # 256-byte bitmap limit. Do not silently drop letters from the pack.
            font.face.set_transform(freetype.Matrix(49152, 0, 0, 65536),
                                    freetype.Vector(0, 0))
        font.set_codepoint_list(points)
        font.build_tables()
        return font.bitstring()

    trimmed = False
    try:
        data = render(codepoints)
    except RuntimeError:
        data = render(modern_codepoint_file(out_dir))
        trimmed = True

    path = os.path.join(out_dir, slot + ".ext")
    with open(path, "wb") as f:
        f.write(data)

    # Проверка: кириллическая Н встаёт на ту же линию, что латинская H, и
    # заливается так же плотно. Одного самого тонкого штриха мало: он приходится
    # на левую стойку и совпадает даже тогда, когда правая выходит вдвое толще.
    _max_h, _feat, table = glyphs.parse_font(data)
    rows, (_w, cap_h, _left, top, adv) = glyphs.render(*table[ord("Н")])
    _ink, _n_density, stem = glyphs.stats(rows)
    density = mean_density(table, [cyr for _lat, cyr in DENSITY_PAIRS])
    # У цифровых и subset-начертаний латинских букв нет вовсе, сравнивать
    # плотность не с чем: базовая величина выходит нулём. Тогда её из проверки
    # исключаем, а высота и линия остаются обязательными.
    density_matters = base_density > 0
    # Высота прописных и базовая линия обязаны совпасть точно — иначе строка
    # прыгает. Штриху разрешён пиксель расхождения: у крупного жирного
    # начертания узкий Roboto набирает нужную плотность только штрихом на
    # пиксель толще, и выбирать приходится между этим и заметно более светлой
    # кириллицей. Плотность — то, что читается как «другой вес», поэтому она в
    # допуске жёстче.
    ok = (cap_h == base_cap and top == base_top
          and abs(stem - base_stem) <= 1
          and (not density_matters or abs(density - base_density) <= DENSITY_TOLERANCE))
    print(f"  {slot:16} {px:2}px wght {weight}  прописные {cap_h}/{base_cap}  "
          f"линия {top}/{base_top}  штрих {stem}/{base_stem}  "
          f"плотность {density:.0f}/{base_density:.0f}%  "
          f"{len(data):6} байт  {'OK' if ok else 'РАСХОЖДЕНИЕ'}"
          f"{'  (только современная азбука)' if trimmed else ''}")
    return path, ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "l10n", "build", "fonts"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    codepoints, count = codepoint_file(args.out)
    print(f"кодовых точек в наборе: {count} "
          f"(своих добавок: {''.join(EXTRA_CODEPOINTS.values())})")
    fonts = sorted({os.path.basename(f) for _px, _w, f in SLOTS.values()})
    print("гарнитуры: " + ", ".join(fonts))
    print()

    for _px, _w, font_path in SLOTS.values():
        if not os.path.exists(font_path):
            sys.exit(f"нет файла шрифта: {font_path}")
    total = 0
    bad = []
    for slot, (px, weight, font_path) in SLOTS.items():
        path, ok = build(slot, px, weight, font_path, args.out, codepoints)
        total += os.path.getsize(path)
        if not ok and slot not in KNOWN_MISMATCH:
            bad.append(slot)
    print(f"\nвсего {len(SLOTS)} расширений, {total} байт в {args.out}")

    if bad:
        # Напечатать расхождение и выйти с нулём — то же самое, что промолчать:
        # сборка идёт дальше, пак уезжает на часы, а строку в логе читает
        # только тот, кто и так знал, куда смотреть.
        print("расхождение с латиницей: " + ", ".join(bad), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
