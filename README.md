# pebble-polyglot-en-ru-he

A **language pack for the Pebble Time 2** (and other modern Pebble watches) that adds
**Russian (Cyrillic)** and **Hebrew** letters on top of the built-in English — so text in
those languages shows real letters instead of boxes (`□□□`).

A ready-to-install pack is included: **`pebble-EN-RU-HE.pbl`**.

## What's in here

| File | What it is |
|------|-----------|
| `pebble-EN-RU-HE.pbl` | ⭐ the ready-to-install pack (English + Russian + Hebrew glyphs) |
| `lang/` | build configuration — which scripts and font sizes |
| `ttf/GoNotoKurrent-Regular.ttf` | source font (SIL OFL 1.1) |
| `OFL.txt` | the font's license |

## Install on the watch

1. Copy `pebble-EN-RU-HE.pbl` to your **Android phone** (USB / Drive / email).
2. Tap it → **open with the Pebble app** → confirm.
3. It **replaces** the currently-loaded language pack (the watch holds one at a time).
   English menus stay; Russian and Hebrew now render.

✅ Confirmed working on a real Pebble Time 2.

## ⚠️ Hebrew reads right-to-left — the watch doesn't

Pebble's firmware has no right-to-left support, so:

| Setup | Hebrew |
|-------|--------|
| `.pbl` + official Pebble app | letters appear, but **reversed** |
| `.pbl` + [Gadgetbridge](https://gadgetbridge.org/) (RTL Support on) | reads **correctly** |

Gadgetbridge (Android) reverses Hebrew before sending so it reads properly. Russian and
English are unaffected (they're left-to-right).

## Revert (safe)

A language pack is **data, not firmware** — it can't brick the watch. To undo: switch the
watch language back to English, or reinstall your previous pack.

## Rebuild

This repo ships the ready-to-use pack and the source config, but **not the build tool**
(it's GPL-licensed — kept separate). To rebuild:

1. Clone the builder: `git clone https://github.com/Pyxzure/pebble-lang-gen`
2. Copy this repo's `lang/` and `ttf/` into that clone (replacing its defaults).
3. Build:
   ```bash
   pip install freetype-py
   python build.py            # -> build/langpack.pbl
   ```

Scripts are configured in `lang/unicodes.json`:

- Cyrillic `0400`–`04FF` (Russian)
- Hebrew `0590`–`05FF`

Add another Unicode block there to support more scripts — the bundled Go Noto Kurrent font
covers a wide range.

## Credits & license

- **Font:** [Go Noto Kurrent](https://github.com/satbyy/go-noto-universal) (Google Noto),
  **SIL Open Font License 1.1** — see `OFL.txt`. The included `.pbl` contains glyphs rendered
  from this font.
- **Build tool:** [pebble-lang-gen](https://github.com/Pyxzure/pebble-lang-gen) (GPL-3.0) —
  not bundled here; clone it to rebuild.
- The configuration in this repo is provided as-is for personal use; add your own `LICENSE`
  if you want to set explicit terms for it.

## Russian interface pack for current PebbleOS

This fork also provides a separate **Russian interface pack v24** for the
29-font-slot PebbleOS layout. See [RUSSIAN.md](RUSSIAN.md) for compatibility,
rebuilding and validation. The original English/Russian/Hebrew pack above is
preserved; the new Russian pack does not provide Hebrew coverage.
