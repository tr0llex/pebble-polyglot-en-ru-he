#!/usr/bin/env python3
"""Разобрать собранный языковой пак и проверить каждый ресурс по отдельности.

Пак — это pbpack: манифест, таблица из записей «смещение, длина, CRC» и тело.
Прошивка читает ресурсы по номеру и сверяет CRC; если хоть один разъехался, на
экране будет каша ровно там, где этот шрифт используется, а остальное будет
выглядеть здоровым — то есть искать причину будешь где угодно, только не здесь.

    python3 tools/l10n/verify-pack.py dist/russkiy-pt2-v13.pbl
"""

import os
import gettext
import io
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.environ.get("PEBBLE_SRC", os.path.join(ROOT, "pebbleos")), "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "l10n"))

import stm32_crc  # noqa: E402

import glyphs  # noqa: E402
from width import LANG_MAP_FONTS  # noqa: E402

TABLE_ENTRY = 16
MANIFEST = 12
CONTENT_START = 0x100C

#: Буквы, без которых русский текст не нарисуешь. Проверяем не «есть хоть
#: что-то кириллическое», а именно их: обрезанный по размеру шрифт может нести
#: начало блока и не нести конца.
PROBE = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"


def verify(data):
    if len(data) < CONTENT_START:
        print("пак короче манифеста и таблицы ресурсов")
        return 1
    num_files, crc, timestamp = struct.unpack_from("<III", data, 0)
    print("  ресурсов в манифесте: %d, метка времени %d" % (num_files, timestamp))
    names = ["STRINGS"] + list(LANG_MAP_FONTS)
    if num_files != len(names) or num_files > 256:
        print("неверное число ресурсов: ожидалось %d" % len(names))
        return 1
    bad = []

    body = data[CONTENT_START:]
    if stm32_crc.crc32(body) != crc:
        bad.append("CRC тела")
        print("  CRC ТЕЛА НЕ СХОДИТСЯ: в манифесте %08x, посчитано %08x"
              % (crc, stm32_crc.crc32(body)))
    else:
        print("  CRC тела сходится")

    ranges = set()
    for i in range(num_files):
        entry = data[MANIFEST + i * TABLE_ENTRY:MANIFEST + (i + 1) * TABLE_ENTRY]
        file_id, offset, length, want_crc = struct.unpack("<IIII", entry)
        blob = body[offset:offset + length]
        got_crc = stm32_crc.crc32(blob)
        name = names[i] if i < len(names) else "?"

        problems = []
        if file_id != i + 1:
            problems.append("неверный номер ресурса")
        region = (offset, offset + length)
        # pbpack shares identical resources between slots; exact aliases are valid.
        if any(region != prior and offset < prior[1] and region[1] > prior[0]
               for prior in ranges):
            problems.append("ресурсы частично пересекаются")
        if not length or offset + length > len(body):
            problems.append("ресурс пуст или выходит за границы тела")
        ranges.add(region)
        if len(blob) != length:
            problems.append("тело короче, чем обещает таблица")
        if got_crc != want_crc:
            problems.append("CRC %08x вместо %08x" % (got_crc, want_crc))

        detail = ""
        if i == 0:
            try:
                gettext.GNUTranslations(io.BytesIO(blob))
            except (OSError, ValueError, struct.error, UnicodeError) as ex:
                problems.append("каталог .mo не разбирается: %s" % ex)
            detail = "каталог строк"
        else:
            try:
                max_h, feat, table = glyphs.parse_font(blob)
                missing = [c for c in PROBE if ord(c) not in table]
                detail = "высота %d, глифов %d" % (max_h, len(table))
                if missing:
                    problems.append("нет букв: %s" % "".join(missing))
            except Exception as ex:
                problems.append("шрифт не разбирается: %s" % ex)

        mark = "  <-- " + "; ".join(problems) if problems else ""
        if problems:
            bad.append(name)
        print("  %2d %-26s %7d байт  %s%s" % (i, name, length, detail, mark))

    print()
    if bad:
        print("испорчены ресурсы:", ", ".join(bad))
        return 1
    print("все ресурсы целы: CRC сходятся, шрифты разбираются, буквы на месте")
    return 0


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "l10n", "build", "ru_RU.pbl")
    with open(path, "rb") as source:
        data = source.read()
    print("%s: %d байт" % (os.path.basename(path), len(data)))
    return verify(data)


if __name__ == "__main__":
    sys.exit(main())
