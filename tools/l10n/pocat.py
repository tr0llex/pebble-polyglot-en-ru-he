"""Минимальный разбор и сборка .po для языкового пака Pebble.

Каталог `tintin.po` из прошивки — источник структуры: комментарии, ссылки на
исходники и порядок записей сохраняются как есть. Меняются только msgstr.
Ключ записи — (msgctxt, msgid); msgid_plural в каталоге Pebble не встречается.
"""

import re

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            out.append(_ESCAPES.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def escape(s):
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return s.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")


def _collect(lines, start):
    """Собрать значение поля, начиная со строки `msgid "..."`, вместе с
    продолжениями вида `"..."`. Возвращает (значение, индекс следующей строки)."""
    first = re.match(r'^\w+(?:\[\d+\])?\s+"(.*)"\s*$', lines[start])
    parts = [first.group(1)]
    i = start + 1
    while i < len(lines) and re.match(r'^\s*"(.*)"\s*$', lines[i]):
        parts.append(re.match(r'^\s*"(.*)"\s*$', lines[i]).group(1))
        i += 1
    return unescape("".join(parts)), i


class Entry:
    def __init__(self, lines):
        self.lines = lines  # исходный блок целиком
        self.ctx = None
        self.msgid = None
        self.msgstr = None
        self._msgstr_span = None
        i = 0
        while i < len(lines):
            ln = lines[i]
            if ln.startswith("msgctxt "):
                self.ctx, i = _collect(lines, i)
            elif ln.startswith("msgid "):
                self.msgid, i = _collect(lines, i)
            elif ln.startswith("msgstr "):
                start = i
                self.msgstr, i = _collect(lines, i)
                self._msgstr_span = (start, i)
            else:
                i += 1

    @property
    def key(self):
        return (self.ctx or "") + "\x04" + (self.msgid or "")

    @property
    def is_header(self):
        return self.msgid == "" and self.ctx is None

    def refs(self):
        out = []
        for ln in self.lines:
            if ln.startswith("#:"):
                out.extend(ln[2:].split())
        return out

    def render(self, translation=None):
        """Блок в текстовом виде; при заданном translation msgstr заменяется."""
        if translation is None or self._msgstr_span is None:
            return list(self.lines)
        a, b = self._msgstr_span
        if "\n" in translation:
            # Многострочные значения пишем как в gettext: пустая первая строка,
            # дальше по строке на каждый перевод строки.
            chunks = translation.split("\n")
            body = ['msgstr ""']
            for n, chunk in enumerate(chunks):
                suffix = "\\n" if n < len(chunks) - 1 else ""
                body.append(f'"{escape(chunk)}{suffix}"')
        else:
            body = [f'msgstr "{escape(translation)}"']
        return list(self.lines[:a]) + body + list(self.lines[b:])


def parse(path):
    with open(path, encoding="utf-8") as source:
        text = source.read()
    entries = []
    for block in text.split("\n\n"):
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue
        if not any(ln.startswith("msgid ") for ln in lines):
            continue
        entries.append(Entry(lines))
    return entries


def write(path, entries, translations):
    """translations: dict key -> перевод. Записи без перевода остаются как есть."""
    blocks = []
    for e in entries:
        blocks.append("\n".join(e.render(translations.get(e.key))))
    with open(path, "w", encoding="utf-8", newline="\n") as output:
        output.write("\n\n".join(blocks) + "\n")
