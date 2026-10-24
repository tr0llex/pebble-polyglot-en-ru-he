#!/usr/bin/env python3
"""Проверить заголовок каталога так же, как это делает прошивка.

Заголовок разбирает `prv_parse_header` в src/fw/services/i18n/i18n.c, и рамки
там жёсткие. Нарушишь — пак отбрасывается целиком и молча, без единого
сообщения на часах: язык просто откатывается к английскому, а в «Настройки →
Система → Информация» остаётся «en_US, v1».

Мы на этом обожглись: написали в Project-Id-Version «russkiy-pt2 2.0» вместо
числа, и часы перестали принимать русификатор — причём вернуть язык из настроек
было уже нельзя, потому что рабочий пак оказался затёрт нерабочим.

    python3 tools/l10n/check-header.py l10n/build/ru_RU.pbl
    python3 tools/l10n/check-header.py l10n/ru_RU.po
"""

import os
import re
import struct
import sys
import pocat

# Пределы из i18n.c и i18n.h.
HEADER_BUFFER_SIZE = 400
VERSION_FIELD_SIZE = 10
LOCALE_NAME_LENGTH = 30
ISO_LOCALE_LENGTH = 6


def header_from_po(path):
    """Заголовок .po — это msgstr пустого msgid."""
    return next((entry.msgstr for entry in pocat.parse(path) if entry.is_header), None)


def header_from_mo(data):
    """Заголовок .mo — перевод пустой строки, первая запись таблицы."""
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic not in (0x950412DE, 0xDE120495):
        raise ValueError("неверная сигнатура .mo")
    endian = "<" if magic == 0x950412DE else ">"
    count, otable, ttable = struct.unpack_from(endian + "III", data, 8)
    for i in range(count):
        olen, ooff = struct.unpack_from(endian + "II", data, otable + i * 8)
        if olen == 0:
            tlen, toff = struct.unpack_from(endian + "II", data, ttable + i * 8)
            if toff + tlen >= len(data) or data[toff + tlen] != 0:
                raise ValueError("оборванный заголовок .mo")
            return data[toff:toff + tlen].decode("utf-8")
    return None


def header_from_pbl(path):
    """Первый ресурс пака — скомпилированный каталог .mo."""
    data = open(path, "rb").read()
    num = struct.unpack_from("<I", data, 0)[0]
    if not num:
        return None
    _fid, off, length, _crc = struct.unpack_from("<IIII", data, 12)
    # content_start пака: таблица на 256 записей плюс заголовок.
    start = 0x100C + off
    return header_from_mo(data[start:start + length])


def check(header):
    problems = []
    size = len(header.encode("utf-8"))
    print("заголовок: %d байт из %d" % (size, HEADER_BUFFER_SIZE))
    if size >= HEADER_BUFFER_SIZE:
        problems.append("заголовок длиннее %d байт — прошивка его не прочитает"
                        % HEADER_BUFFER_SIZE)

    def field(name, limit):
        match = re.search("^%s([^\n]*)\n" % re.escape(name), header, re.M)
        if not match:
            return None
        value = match.group(1)
        raw = len(value.encode("utf-8"))
        print("  %-22s %-24s %d байт" % (name, value, raw))
        # prv_get_property отвергает значение длиннее буфера целиком.
        if raw >= limit:
            problems.append("«%s» не оставляет места для NUL в %d байтах" % (name.strip(), limit))
        return value

    locale = field("Language: ", ISO_LOCALE_LENGTH)
    if locale is None:
        problems.append("нет поля «Language» — без него пак отбрасывается")

    field("Name: ", LOCALE_NAME_LENGTH)

    version = field("Project-Id-Version: ", VERSION_FIELD_SIZE)
    if version is None:
        problems.append("нет поля «Project-Id-Version» — без него пак отбрасывается")
    elif not re.fullmatch(r"[1-9][0-9]*", version) or not 1 <= int(version) <= 65535:
        problems.append("«Project-Id-Version» должен быть числом от 1 до 65535")

    return problems


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]

    try:
        if path.endswith(".po"):
            header = header_from_po(path)
        elif path.endswith(".mo"):
            header = header_from_mo(open(path, "rb").read())
        else:
            header = header_from_pbl(path)
    except (OSError, ValueError, struct.error) as ex:
        print("не удалось прочитать заголовок: %s" % ex)
        return 1

    if not header:
        sys.exit("не нашёл заголовок в %s" % path)

    print("== %s" % os.path.basename(path))
    problems = check(header)

    if problems:
        print("\nпрошивка такой пак не примет:")
        for p in problems:
            print("  * %s" % p)
        return 1
    print("\nзаголовок прошивку устроит")
    return 0


if __name__ == "__main__":
    sys.exit(main())
