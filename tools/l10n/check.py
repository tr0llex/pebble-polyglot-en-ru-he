#!/usr/bin/env python3
"""Приёмка перевода: глифы и ширина.

1. Каждый символ каждого перевода должен существовать хотя бы в одном из
   системных шрифтов интерфейса — иначе на экране будет плашка. Латиница и
   пунктуация берутся из базового .pbf прошивки, кириллица — из расширения
   в языковом паке.
2. Однострочные подписи не должны выезжать за ширину экрана.

    python3 tools/l10n/check.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "l10n"))

import width  # noqa: E402

UI_FONTS = [
    "GOTHIC_14", "GOTHIC_14_BOLD", "GOTHIC_18", "GOTHIC_18_BOLD",
    "GOTHIC_24", "GOTHIC_24_BOLD", "GOTHIC_28", "GOTHIC_28_BOLD",
]
# Эмодзи рисуются отдельным шрифтом: fonts_get_system_emoji_font_for_size
# подставляет его для символов, которых нет в основном.
EMOJI_FONTS = ["EMOJI_14", "EMOJI_18", "EMOJI_24", "EMOJI_28"]
# Перенос строки и подстановки в тексте не рисуются.
IGNORE = set("\n\t")

# Строки шире пункта меню, но это не пункты меню: диалоги и подсказки
# переносятся по словам, заголовок окна рисуется мелким шрифтом строки
# состояния, формат strftime на экран не попадает. Проверено по коду.
ALLOW_WIDE = {
    "Check bluetooth connection",       # диалог bt_conn_dialog
    "%a %b %e %H:%M:%S %Y",             # формат strftime
    "Way to show us what you're made of 👊",
    "Feelin' hot? Cause you're on 🔥",
    "Keepin' that heart healthy! ❤",    # карточки инсайтов, текст переносится
    "Alarm dismissed",                  # всплывающий диалог
    "Snooze delay set to %d minutes",   # всплывающий диалог
    "Backlight Settings",               # заголовок окна, GOTHIC_14_BOLD
    "Update Failed",                    # всплывающий диалог
    "Snooze for %d minutes",            # всплывающий диалог
    "Add them in the app",              # подзаголовок пункта, мелкий шрифт
    # Замерено по месту отрисовки, а не по пункту меню:
    "Wave your arm in a figure eight",  # компас, GOTHIC_24_BOLD с переносом в 176 px
    "No HRV that night",                # готовность, GOTHIC_18: 176 px из 200
    "SAVED LOCATIONS",                  # погода, GOTHIC_18_BOLD: 144 px из 180
    # Предупреждения погоды склеиваются в предложение и переносятся по словам
    # (weather_app_layout.c, prv_build_forecast_desc).
    "Chance of sleet",
    "Sleet likely",
    "Feels below freezing",
    # Подставляется в «Хватит до %s» диалога батареи (battery_ui.c), а диалог
    # переносит текст по словам.
    "the foreseeable future",
}


def main():
    with open(os.path.join(ROOT, "l10n", "ru.json"), encoding="utf-8") as f:
        table = json.load(f)

    emoji = set()
    for font in EMOJI_FONTS:
        emoji |= set(width.font_metrics(font))

    missing = {}
    for font in UI_FONTS:
        metrics = width.font_metrics(font)
        for key, value in table.items():
            for ch in value:
                if ch in IGNORE or ord(ch) in metrics or ord(ch) in emoji:
                    continue
                missing.setdefault(ch, set()).add(font)

    print(f"переводов: {len(table)}")
    if missing:
        print("символы без глифа (будут плашками):")
        for ch, fonts in sorted(missing.items()):
            where = "во всех шрифтах" if len(fonts) == len(UI_FONTS) else ", ".join(sorted(fonts))
            print(f"  {ch!r} U+{ord(ch):04X}  {where}")
    else:
        print("все символы есть во всех шрифтах интерфейса")

    # Однострочные подписи: длинные тексты диалогов переносятся, их не меряем.
    over = []
    for key, value in table.items():
        # Диалоги и подсказки переносятся по словам — их ширина не ограничена.
        # Пункты меню и подписи — короткие строки без конечной пунктуации.
        if len(value) > 30 or "\n" in value or value.rstrip()[-1:] in ".?!":
            continue
        if key.split("\x04")[-1] in ALLOW_WIDE:
            continue
        w, _ = width.text_width("GOTHIC_24_BOLD", value)
        if w > 176:
            over.append((w, key.split("\x04")[-1], value))
    if over:
        print("шире 176 px (пункт меню, GOTHIC_24_BOLD):")
        for w, key, value in sorted(over, reverse=True):
            print(f"  {w:4d}  {key!r} -> {value!r}")
    else:
        print("все короткие подписи влезают в 176 px")

    # Широкий пункт — такая же поломка, как плашка вместо буквы: на часах его
    # обрезает. Раньше проверка про него только печатала и возвращала успех,
    # поэтому сборка пака пропускала то, что сама же нашла. Нарочно широкие
    # строки перечислены в ALLOW_WIDE с причиной.
    return 1 if (missing or over) else 0


if __name__ == "__main__":
    sys.exit(main())
