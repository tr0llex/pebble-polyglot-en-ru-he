#!/usr/bin/env python3
"""Собрать l10n/ru_RU.po из шаблона прошивки и словаря переводов l10n/ru.json.

Шаблон — resources/normal/base/lang/ru_RU/tintin.po из PebbleOS: в нём все 684
строки со ссылками на исходники, но msgstr там дублирует английский оригинал.
Наши переводы лежат отдельно в JSON, ключ — "msgctxt\\x04msgid" (для строк без
контекста msgctxt пустой).

    python3 tools/l10n/apply.py [--report]
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "l10n"))

import pocat  # noqa: E402

TEMPLATE = os.path.join(
    ROOT, "l10n", "upstream", "ru_RU", "tintin.po"
)
TRANSLATIONS = os.path.join(ROOT, "l10n", "ru.json")
OUTPUT = os.path.join(ROOT, "l10n", "ru_RU.po")
MINIMAL = os.path.join(ROOT, "l10n", "build", "ru_RU.min.po")

# Заголовок читает прошивка (services/i18n/i18n.c, prv_parse_header), и он у
# неё с жёсткими рамками:
#   * весь заголовок должен уместиться в 400 байт;
#   * «Project-Id-Version» обязан быть ЧИСЛОМ длиной до 10 байт — это версия
#     пака, и её надо поднимать при КАЖДОМ изменении содержимого. Часы сверяют
#     паки по этому числу: с прежним номером новый пак для них тот же самый, и
#     он молча не встанет. Мы уже выпустили пак с изменённым набором строк под
#     старым номером 10 — на часах он не обновился.
#     пака, её показывают в «Информации» как «ru_RU, vN». Не число или строка
#     длиннее — и пак отбрасывается целиком, язык откатывается к английскому;
#   * «Name» — до 30 байт, это подпись в «Настройки → Язык»;
#   * «Language» — до 6 байт.
# Мы один раз написали сюда «russkiy-pt2 2.0», и часы перестали принимать пак.
# Лишних полей тут нет намеренно: заголовок и так занимает почти весь буфер
# прошивки, а Plural-Forms в нём — самая длинная строка и выкинуть её нельзя.
#: Сколько байт прошивка отводит под один перевод (i18n_get, буфер translated).
#: Апстрим держит 200 — под английский; наша правка поднимает до 256
#: (tools/fw/apply-fixes.py, «i18n: буфер перевода рассчитан на английский»).
#: Всё, что длиннее, прошивка молча обрежет по середине слова: она пишет об этом
#: в лог, но на экран уходит обрубок, и узнаём мы об этом по фотографии часов.
I18N_BUFFER = 256


def check_lengths(table):
    """Перевод, который не влезет в буфер прошивки, — это обрезка на экране."""
    too_long = [(len(v.encode("utf-8")), k, v)
                for k, v in table.items()
                if len(v.encode("utf-8")) >= I18N_BUFFER]
    if not too_long:
        return
    print("переводы длиннее буфера прошивки (%d байт):" % I18N_BUFFER, file=sys.stderr)
    for size, key, value in sorted(too_long, reverse=True):
        print("  %d байт  %r" % (size, value[:60]), file=sys.stderr)
    sys.exit("укоротите их или поднимите буфер в tools/fw/apply-fixes.py")


HEADER = """Project-Id-Version: 24
Last-Translator: Alexey Samoylov
Language: ru_RU
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit
Name: Русский PT2
Plural-Forms: nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);
"""



def synthesize(key):
    """Собрать запись каталога для строки, которой нет в шаблоне.

    xgettext видит только литералы прямо в вызове i18n. Строки, которые код
    отдаёт через переменную (например day_picker.c: i18n_noop(prv_kind_strings[kind])),
    в .pot не попадают — но прошивка ищет перевод по самому оригиналу, поэтому
    достаточно положить запись в каталог руками.
    """
    ctx, _, msgid = key.partition("\x04")
    lines = ["#. Добавлено вручную: xgettext не извлекает эту строку из кода"]
    if ctx:
        lines.append(f'msgctxt "{pocat.escape(ctx)}"')
    lines.append(f'msgid "{pocat.escape(msgid)}"')
    lines.append('msgstr ""')
    return pocat.Entry(lines)


def check_formats(entries, table):
    """Сверить подстановки. xgettext помечает c-format и строки strftime, где мы
    сознательно меняем порядок (%B %d -> %e %B), поэтому msgfmt --check-format
    нам не годится: проверяем только printf-подстановки."""
    import re
    pattern = re.compile(r"%(?:%|[-#0-9.*+ ]*(?:hh|h|ll|l|z|j|t)?[diouxXsc])")
    # %B, %A, %H и подобные бывают только в strftime: там %d — день месяца,
    # а не подстановка printf, и порядок мы меняем намеренно.
    strftime_only = re.compile(r"%[ABHMSRlaeyYpjZ]")
    bad = []
    for e in entries:
        tr = table.get(e.key)
        # Сначала выкусываем printf-подстановки: иначе %l из "%lu" считался
        # признаком strftime, и такие строки вообще не проверялись.
        residual = pattern.sub("", e.msgid)
        if tr is None or strftime_only.search(residual):
            continue
        # printf consumes arguments in order: swapping %s and %d is not safe.
        a = [x for x in pattern.findall(e.msgid) if x != "%%"]
        b = [x for x in pattern.findall(tr) if x != "%%"]
        if a != b:
            bad.append((e.msgid, tr, a, b))
    return bad

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="показать прогресс перевода")
    args = ap.parse_args()

    entries = pocat.parse(TEMPLATE)
    with open(TRANSLATIONS, encoding="utf-8") as f:
        translations = json.load(f)

    check_lengths(translations)

    # В JSON ключ — просто msgid; строки с контекстом пишутся как "ctxmsgid".
    table = {(k if "\x04" in k else "\x04" + k): v for k, v in translations.items()}
    table["\x04"] = HEADER  # заголовок каталога

    known = {e.key for e in entries}
    extra = [synthesize(k) for k in table if k not in known and k != "\x04"]
    if extra:
        print(f"добавлено вручную, вне шаблона: {len(extra)}")
        for e in extra:
            print(f"   {e.msgid!r}")
    entries += extra

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    os.makedirs(os.path.dirname(MINIMAL), exist_ok=True)
    pocat.write(OUTPUT, entries, table)

    body = [e for e in entries if not e.is_header]
    done = [e for e in body if e.key in table]

    # В пак кладём только переведённое: для остального прошивка и так покажет
    # исходную английскую строку, а каталог не раздувается.
    pocat.write(MINIMAL, [e for e in entries if e.is_header or e.key in table], table)

    bad = check_formats(body, table)
    if bad:
        print(f"РАСХОЖДЕНИЕ ПОДСТАНОВОК в {len(bad)} строках:", file=sys.stderr)
        for msgid, tr, a, b in bad:
            print(f"  {msgid!r} {a} -> {tr!r} {b}", file=sys.stderr)
        sys.exit(1)

    print(f"записано {OUTPUT}")
    print(f"переведено {len(done)} из {len(body)}")

    if args.report:
        missing = [e for e in body if e.key not in table]
        by_file = {}
        for e in missing:
            for r in e.refs():
                f = r.split(":")[0].replace("../src/fw/", "")
                by_file[f] = by_file.get(f, 0) + 1
                break
        for f, n in sorted(by_file.items(), key=lambda kv: -kv[1]):
            print(f"  {n:4d}  {f}")


if __name__ == "__main__":
    main()
