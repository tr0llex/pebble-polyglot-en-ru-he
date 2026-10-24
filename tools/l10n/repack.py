#!/usr/bin/env python3
"""Собрать языковой пак .pbl: наш .mo вместо строкового ресурса, шрифты — из
готового пака.

Языковой пак — это pbpack (table_size 256, content_start 0x100C): ресурс №1
хранит скомпилированный каталог .mo, ресурсы №2… — расширения системных шрифтов
с кириллицей. Шрифты берём из проверенного на живых PT2 пака
polyglot/pebble-EN-RU-HE.pbl и не трогаем.

    python3 tools/l10n/repack.py --mo l10n/build/STRINGS.mo --out l10n/build/ru_RU.pbl
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.environ.get("PEBBLE_SRC", os.path.join(ROOT, "pebbleos")), "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "l10n"))

import pbpack  # noqa: E402

from width import LANG_MAP_FONTS  # noqa: E402

# Порядок слотов в паке-источнике polyglot: он собран для прошивки, где ещё не
# было GOTHIC_36. Нужен, чтобы разложить его шрифты по именам, а не по счёту.
SOURCE_SLOTS = [
    "GOTHIC_14", "GOTHIC_14_BOLD", "GOTHIC_18", "GOTHIC_18_BOLD",
    "GOTHIC_24", "GOTHIC_24_BOLD", "GOTHIC_28", "GOTHIC_28_BOLD",
    "BITHAM_18_LIGHT_SUBSET", "BITHAM_30_BLACK", "BITHAM_34_LIGHT_SUBSET",
    "BITHAM_34_MEDIUM_NUMBERS", "BITHAM_42_BOLD", "BITHAM_42_LIGHT",
    "BITHAM_42_MEDIUM_NUMBERS", "ROBOTO_CONDENSED_21", "ROBOTO_BOLD_SUBSET_49",
    "DROID_SERIF_28_BOLD",
]

FONT_SOURCE = os.path.join(ROOT, "pebble-EN-RU-HE.pbl")
EXT_DIR = os.path.join(ROOT, "l10n", "build", "fonts")


def read_resources(path):
    """Вернуть список ресурсов пака в порядке file_id."""
    data = open(path, "rb").read()
    num = struct.unpack_from("<I", data, 0)[0]
    pack = pbpack.ResourcePack(False)
    out = []
    for n in range(num):
        _fid, off, length, _crc = struct.unpack_from("<IIII", data, 12 + n * 16)
        start = pack.content_start + off
        out.append(data[start:start + length])
    return out


#: Отпечаток выпущенного пака рядом с его номером.
#:
#: Часы сверяют паки ТОЛЬКО по номеру версии: пак с прежним номером для них тот
#: же самый, и он молча не встанет. На часах остаётся старый пак, а мы смотрим
#: на правильный в dist и не понимаем, почему на экране старое. Так уже было
#: дважды, и оба раза мы узнали об этом от владельца, а не от сборки.
#:
#: Сборка пака отпечаток НЕ пишет, а только сверяется с ним. Пишет его
#: отдельный шаг в самом конце build.sh — `repack.py --stamp`, — когда пак уже
#: прошёл verify-pack.py и check.py. Раньше отпечаток писался прямо здесь, и
#: упавшая проверка оставляла в нём новый sha под прежним номером: следующая
#: сборка, уже исправленная, падала с «пак изменился, а номер прежний», и номер
#: приходилось поднимать за сборку, которая никуда не уехала.
STAMP = os.path.join(ROOT, "l10n", "pack-version.json")


def pack_version(mo_path):
    """Номер версии из заголовка каталога (Project-Id-Version)."""
    with open(mo_path, "rb") as source:
        blob = source.read()
    m = re.search(br"Project-Id-Version:\s*(\d+)", blob)
    if not m:
        sys.exit("в каталоге нет числового Project-Id-Version — такой пак "
                 "прошивка отбрасывает целиком")
    return int(m.group(1))


def read_stamp():
    try:
        with open(STAMP, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_stamp(pack_path):
    """Запомнить выпущенный пак. Звать только после всех проверок."""
    version = pack_version(pack_path)
    digest = check_version_bumped(pack_path, version)
    known = read_stamp()
    if known and known.get("version") == version and known.get("sha256") == digest:
        print("отпечаток пака на месте: v%d" % version)
        return
    with open(STAMP, "w", encoding="utf-8") as f:
        json.dump({"version": version, "sha256": digest}, f,
                  ensure_ascii=False, indent=2)
        f.write("\n")
    print("отпечаток пака записан: v%d" % version)


def check_version_bumped(out_path, version):
    """Содержимое изменилось — номер обязан вырасти. Отпечаток не трогаем."""
    with open(out_path, "rb") as source:
        digest = hashlib.sha256(source.read()).hexdigest()
    known = read_stamp()

    if known and version < known["version"]:
        sys.exit("номер пака не может уменьшаться: %d < %d" % (version, known["version"]))
    if known and known.get("version") == version and known.get("sha256") != digest:
        sys.exit(
            "пак изменился, а номер версии остался прежним (%d).\n"
            "  Часы сверяют паки по этому числу: новый пак они сочтут уже\n"
            "  установленным и молча оставят старый.\n"
            "  Подними Project-Id-Version в tools/l10n/apply.py и пересобери."
            % version)
    return digest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mo", required=True, help="скомпилированный каталог .mo")
    ap.add_argument("--fonts", default=FONT_SOURCE, help="пак-источник шрифтов")
    ap.add_argument("--ext-dir", default=EXT_DIR,
                    help="каталог со своими расширениями <СЛОТ>.ext")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stamp", action="store_true",
                    help="не собирать, а запомнить уже проверенный пак из --out")
    args = ap.parse_args()

    # Отдельный шаг в конце build.sh: пак к этому моменту прошёл все проверки,
    # и только теперь его не стыдно записать как выпущенный.
    if args.stamp:
        write_stamp(args.out)
        return

    source = read_resources(args.fonts)
    if len(source) < 2:
        sys.exit(f"в {args.fonts} нет шрифтов")
    # Пак-источник собран для прошивки со своим набором слотов: в polyglot их
    # 18, у нашей прошивки — 20. Класть его шрифты подряд нельзя, иначе всё
    # после лишнего слота уедет. Поэтому раскладываем по именам.
    source_fonts = source[1:]
    source_by_name = dict(zip(SOURCE_SLOTS, source_fonts))

    replaced = []
    borrowed = []
    empty = []
    fonts = []
    for slot in LANG_MAP_FONTS:
        path = os.path.join(args.ext_dir, slot + ".ext")
        if os.path.exists(path):
            with open(path, "rb") as f:
                fonts.append(f.read())
            replaced.append(slot)
        elif slot in source_by_name:
            fonts.append(source_by_name[slot])
            borrowed.append(slot)
        else:
            # Пустой ресурс класть нельзя: прошивка берёт слот по индексу и
            # разбирает его как шрифт, а на нулевой длине читает мусор — на
            # экране получаются случайные глифы вместо букв. Лучше отказаться
            # собирать пак, чем отдать такой.
            empty.append(slot)

    if empty:
        sys.exit("нет данных для слотов: %s. Пустой слот прошивка читает как "
                 "испорченный шрифт, и на экране выходят случайные глифы вместо "
                 "букв. Собери расширения: bash tools/l10n/buildfonts.sh"
                 % ", ".join(empty))

    mo = open(args.mo, "rb").read()
    if struct.unpack_from("<I", mo, 0)[0] != 0x950412DE:
        sys.exit(f"{args.mo} не похож на .mo")

    pack = pbpack.ResourcePack(False)
    pack.add_resource(mo)
    for font in fonts:
        pack.add_resource(font)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as f:
        pack.serialize(f)

    size = os.path.getsize(args.out)
    strings_n = struct.unpack_from("<I", mo, 8)[0]
    print(f"собран {args.out}")
    print(f"  ресурсов: {1 + len(fonts)} (строки + {len(fonts)} шрифтов)")
    if replaced:
        print(f"  свои расширения: {len(replaced)} ({', '.join(replaced)})")
    if borrowed:
        print(f"  взято из {os.path.basename(args.fonts)}: {len(borrowed)}")

    print(f"  строк в каталоге: {strings_n}")
    print(f"  каталог: {len(mo)} байт, пак: {size} байт")

    version = pack_version(args.mo)
    check_version_bumped(args.out, version)
    print(f"  версия пака: {version}")


if __name__ == "__main__":
    main()
