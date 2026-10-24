# Russian interface pack v24

`dist/russkiy-pt2-v24.pbl` contains 882 translated entries and 29 Cyrillic font
extensions for the Pebble Time 2. It is the pack tested with PebbleOS
v4.42.3-ru51, based on upstream `f7970c34522cb34294cb980e9a72880a2999d599`
plus the localization changes in tr0llex/PebbleOS. Firmware font-slot order
must match: this artifact is not a drop-in replacement for older 18-slot packs.

SHA-256: `a82298724b316ac7cfd64d62b17740587a2afb2501a1fb2ec737de354f30b20a`.

The Russian pack replaces the active language pack when installed. The original
`pebble-EN-RU-HE.pbl` remains available separately; Hebrew is not included in v24.

## Rebuild and check

On Linux/WSL, install Python 3 (tested with 3.12 and 3.14), gettext (`msgfmt`
and `msgattrib`), FreeType, and a C compiler for the firmware tooling.
Use the matching, initialized PebbleOS checkout with its source fonts and
Python build dependencies installed. A checkout alone is not a firmware SDK.

```bash
export PEBBLE_SRC=/absolute/path/to/PebbleOS
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-fonts.txt
bash tools/l10n/build.sh
python3 -m unittest discover -s tools/tests -v
cmp l10n/build/ru_RU.pbl dist/russkiy-pt2-v24.pbl
```

`FONT_PYTHON` can select an existing Python environment containing freetype-py.
The build validates the compact MO header, positional font-slot map, resource
CRC and bounds, font records, alphabet coverage and menu label widths. Only a
successful build records the release hash. The regression suite rejects malformed
headers, resource-table overlaps, corrupt fonts and stale release stamps.
Changing translations or font rasters requires incrementing the version in
`tools/l10n/apply.py`; never reuse a released version for different bytes.

`l10n/ru.json` is the editable catalog. `l10n/ru_RU.po` is generated from the
preserved upstream template. `scan-source.py` compares the catalog with live
firmware sources. Font order is read from the firmware resource map, not a stale
copy in this repository. The expanded translation buffer and Russian plural rules
require the companion firmware localization PR.

## Provenance

The catalog and build/validation tools are maintained in this fork. Historical
PebbleOS templates in `l10n/upstream/` retain their Apache-2.0 license. Noto Sans
and Roboto Condensed fonts use SIL OFL 1.1; the corresponding license notices are
next to the font files. Base Droid/Roboto fonts and fontgen are read from PebbleOS
and retain their upstream licenses. The original multilingual donor pack and its
license are unchanged. The current build supplies every one of the 29 extensions.
