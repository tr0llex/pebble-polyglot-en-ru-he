#!/usr/bin/env python3
"""Все строки, помеченные для перевода в исходниках, против нашего каталога.

`scan.py` берёт список из `.pot`, а тот собирается вместе с прошивкой и несёт
только то, что попало в сборку при той конфигурации. Целое приложение погоды
из-за этого не показывалось как непереведённое: строки в нём размечены,
каталог их не знает, и на часах они остаются английскими — а проверка молчит.

Здесь список берётся из самих исходников: любой литерал внутри i18n_noop(),
i18n_get() и i18n_get_with_buffer(). Так проверка не зависит от того, что было
включено при сборке.

    python3 tools/l10n/scan-source.py             # чего нет в каталоге
    python3 tools/l10n/scan-source.py --by-file   # с группировкой по файлам
"""

import argparse
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FW_ROOT = os.environ.get("PEBBLE_SRC", os.path.join(ROOT, "pebbleos"))
SRC = os.path.join(FW_ROOT, "fw" if os.path.isdir(os.path.join(FW_ROOT, "fw")) else "src/fw")
CATALOG = os.path.join(ROOT, "l10n", "ru.json")

#: Заводские экраны (PRF) на часы владельца не попадают, переводить их незачем.
SKIP_DIRS = ("apps/prf", "apps/demo")

STRING = r'"(?:[^"\\]|\\.)*"'
#: Между соседними литералами бывает не только пробел, но и перенос строки
#: через обратную косую — так записаны все длинные подсказки. Без этого
#: склейка обрывалась на первом куске, и целая строка числилась
#: непереведённой, хотя перевод есть. Проверка, которая врёт, хуже
#: отсутствующей.
JOIN = r'(?:\s|\\)*'
CALL = re.compile(
    r'\bi18n_(?:noop|get|get_with_buffer)\s*\(' + JOIN +
    r'((?:' + STRING + JOIN + r')+)')
CTX_CALL = re.compile(
    r'\bi18n_ctx_(?:noop|get|get_with_buffer)\s*\(' + JOIN +
    r'((?:' + STRING + JOIN + r')+),' + JOIN +
    r'((?:' + STRING + JOIN + r')+)')
LITERAL = re.compile(STRING)


def unescape(text):
    return text.encode("ascii", "backslashreplace").decode("unicode_escape")


def collect(src):
    """{msgctxt\\x04msgid: [файл:строка, ...]} по всем исходникам."""
    if not os.path.isdir(src):
        raise ValueError("нет дерева исходников: " + str(src))
    found = {}
    for dirpath, _dirs, files in os.walk(src):
        rel_dir = os.path.relpath(dirpath, src).replace(os.sep, "/")
        if any(rel_dir.startswith(skip) for skip in SKIP_DIRS):
            continue
        for name in sorted(files):
            if not name.endswith((".c", ".h", ".def")):
                continue
            path = os.path.join(dirpath, name)
            with io.open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            for m in CALL.finditer(text):
                parts = [p[1:-1] for p in LITERAL.findall(m.group(1))]
                literal = unescape("".join(parts))
                if not literal:
                    continue
                where = "%s/%s:%d" % (rel_dir, name, text.count("\n", 0, m.start()) + 1)
                found.setdefault(literal, []).append(where)
            for m in CTX_CALL.finditer(text):
                context, literal = (
                    unescape("".join(p[1:-1] for p in LITERAL.findall(group)))
                    for group in m.groups())
                if not literal:
                    continue
                where = "%s/%s:%d" % (rel_dir, name, text.count("\n", 0, m.start()) + 1)
                found.setdefault(context + "\x04" + literal, []).append(where)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--by-file", action="store_true", help="сгруппировать по файлам")
    ap.add_argument("--src", default=SRC)
    args = ap.parse_args()

    with io.open(CATALOG, encoding="utf-8") as f:
        catalog = json.load(f)
    known = set(catalog)

    try:
        found = collect(args.src)
    except ValueError as exc:
        ap.error(str(exc))
    if not found:
        ap.error("в дереве не найдено ни одной строки i18n: " + args.src)
    missing = {s: where for s, where in found.items() if s not in known}

    print("помечено в исходниках: %d" % len(found))
    print("нет в каталоге: %d" % len(missing))
    if not missing:
        return 0

    if args.by_file:
        by_file = {}
        for text, wheres in missing.items():
            by_file.setdefault(wheres[0].rsplit(":", 1)[0], []).append(text)
        for path in sorted(by_file):
            print("\n%s" % path)
            for text in sorted(by_file[path]):
                print("    %r" % text)
    else:
        for text in sorted(missing):
            print("  %-46r %s" % (text[:44], missing[text][0]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
