#!/usr/bin/env bash
# Сборка русского языкового пака: ru.json -> ru_RU.po -> STRINGS.mo -> ru_RU.pbl
#
# Запускать из Windows:
#   wsl -d Ubuntu -- bash "/mnt/c/.../tools/l10n/build.sh"
#
# Requires gettext, Python 3 and the matching PebbleOS source checkout.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
: "${PEBBLE_SRC:?Set PEBBLE_SRC to the matching PebbleOS checkout}"

BUILD="$ROOT/l10n/build"
mkdir -p "$BUILD"

python3 "$ROOT/tools/l10n/apply.py" "$@"

# Кириллические расширения шрифтов (нужно отдельное окружение с freetype-py).
#
# Собираются каждый раз, а не только когда каталога нет. Пересборка «если
# файла нет» означала, что правка SLOTS или обновление базовых начертаний
# апстримом до пака не доезжают: на диске лежат вчерашние .ext, и всё
# выглядит собранным. И падение сборки шрифтов больше не проглатывается —
# запасного варианта у нас нет с тех пор, как мы собираем все двадцать
# начертаний сами.
bash "$ROOT/tools/l10n/buildfonts.sh"

msgfmt --check-header -o "$BUILD/STRINGS.mo" "$BUILD/ru_RU.min.po"
# Считаем только записи с непустым msgid: пустой — это служебный заголовок
# домена, и их четыре. Строка «непереведённых записей: 4» держалась на экране
# при полностью переведённом каталоге и означала ровно ничего.
echo "непереведённых записей: $(msgattrib --untranslated --no-wrap "$ROOT/l10n/ru_RU.po" | grep -c '^msgid "."' || true)"

python3 "$ROOT/tools/l10n/repack.py" \
    --mo "$BUILD/STRINGS.mo" \
    --out "$BUILD/ru_RU.pbl"

# Разбор собранного пака по ресурсам: CRC каждого, разбор каждого шрифта,
# наличие всех букв. Испорченный ресурс даёт кашу ровно на тех экранах, где
# используется этот шрифт, а остальное выглядит здоровым — и причину потом
# ищешь где угодно, только не в паке.
#
# Вывод режем до хвоста, но код возврата берём у самой проверки. Здесь стоял
# конвейер `verify-pack.py | tail -2`, и код возврата отдавал tail: сломанный
# пак собирался «успешно». Та же ошибка уже стоила нам сборки ветки прошивки.
check() {
    local out status
    out="$("$@" 2>&1)" && status=0 || status=$?
    printf '%s\n' "$out" | tail -"$TAIL"
    if [ "$status" -ne 0 ]; then
        printf '%s\n' "$out" >&2
        echo "ОШИБКА: проверка не прошла — $*" >&2
        exit "$status"
    fi
}
TAIL=2 check python3 "$ROOT/tools/l10n/verify-pack.py" "$BUILD/ru_RU.pbl"
TAIL=2 check python3 "$ROOT/tools/l10n/check-header.py" "$BUILD/ru_RU.pbl"

# Приёмка перевода: у каждого символа есть глиф, и ни один пункт меню не шире
# экрана. Пункт шире 176 px обрезается на часах, и узнаём мы об этом по
# фотографии: так «Напоминать о движении» (206 px) доехало до владельца.
TAIL=3 check python3 "$ROOT/tools/l10n/check.py"

# Отпечаток выпущенного пака — последним шагом, когда пак уже прошёл всё.
#
# Раньше его писала сама сборка пака (repack.py), до проверок. Упавшая проверка
# оставляла в отпечатке новый sha под прежним номером, и следующая сборка — уже
# исправленная — падала с «пак изменился, а номер прежний». Номер приходилось
# поднимать за сборку, которая никуда не уехала. За одну сессию наступили дважды.
python3 "$ROOT/tools/l10n/repack.py" --stamp --mo "$BUILD/STRINGS.mo" --out "$BUILD/ru_RU.pbl"
