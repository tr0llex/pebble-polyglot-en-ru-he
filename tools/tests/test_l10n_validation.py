"""Reject corrupted packs and translations before recording a release stamp."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/l10n'))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools/l10n' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


header = load('check_header', 'check-header.py')
apply = load('apply_l10n', 'apply.py')
verify = load('verify_pack', 'verify-pack.py')
repack = load('repack_l10n', 'repack.py')


class HeaderTests(unittest.TestCase):
    def check(self, value):
        with redirect_stdout(io.StringIO()):
            return header.check(value)

    def test_current_header_and_po_roundtrip(self):
        self.assertEqual(self.check(apply.HEADER), [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'ru.po')
            entry = apply.pocat.Entry(['msgid ""', 'msgstr ""'])
            apply.pocat.write(path, [entry], {'\x04': apply.HEADER})
            self.assertEqual(header.header_from_po(path), apply.HEADER)

    def test_fields_reserve_nul_byte(self):
        for field, limit in [('Language', 6), ('Name', 30), ('Project-Id-Version', 10)]:
            text = 'Language: ru_RU\nName: Русский\nProject-Id-Version: 24\n'
            lines = [f'{field}: ' + '1' * limit if line.startswith(field + ':') else line
                     for line in text.splitlines()]
            with self.subTest(field=field):
                self.assertTrue(self.check('\n'.join(lines) + '\n'))

    def test_missing_newline_and_invalid_version(self):
        self.assertTrue(self.check('Language: ru_RU\nProject-Id-Version: 24'))
        for value in ('0', '-1', '65536', '24x', '024'):
            self.assertTrue(self.check(apply.HEADER.replace('Version: 24', 'Version: ' + value)))

    def test_printf_argument_order(self):
        entry = apply.synthesize('\x04%s: %d')
        self.assertTrue(apply.check_formats([entry], {entry.key: '%d: %s'}))
        self.assertEqual(apply.check_formats([entry], {entry.key: '%s: %d'}), [])

    def test_strftime_can_reorder_fields(self):
        entry = apply.synthesize('\x04%B %d')
        self.assertEqual(apply.check_formats([entry], {entry.key: '%e %B'}), [])


class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Build a complete small pack in memory: no dependency on ignored dist/ files.
        metadata = apply.HEADER.encode('utf-8')
        mo = (struct.pack('<7I', 0x950412DE, 0, 1, 28, 36, 0, 0)
              + struct.pack('<4I', 0, 44, len(metadata), 45) + b'\0' + metadata + b'\0')
        # A one-bucket v2 font: all required letters share a one-pixel glyph.
        letters = verify.PROBE
        font = (struct.pack('<BBHHBB', 2, 1, len(letters), 0, 1, 2)
                + struct.pack('<BBH', 0, len(letters), 0)
                + b''.join(struct.pack('<HI', ord(ch), 1) for ch in letters)
                + b'\0' + struct.pack('<BBbbbB', 1, 1, 0, 0, 1, 1))
        pack = repack.pbpack.ResourcePack(False)
        pack.add_resource(mo)
        for _ in verify.LANG_MAP_FONTS:
            pack.add_resource(font)
        stream = io.BytesIO()
        pack.serialize(stream)
        cls.pack = stream.getvalue()

    def check(self, data):
        with redirect_stdout(io.StringIO()):
            return verify.verify(data)

    def test_valid_pack(self):
        self.assertEqual(self.check(self.pack), 0)

    def test_manifest_crc_must_fail_even_when_resource_crcs_pass(self):
        data = bytearray(self.pack)
        data[4] ^= 1
        self.assertEqual(self.check(data), 1)

    def test_manifest_and_table_corruption(self):
        for offset, value in ((0, 0), (0, 257), (12, 2), (16, len(self.pack)),
                              (32, 0), (20, 0)):
            with self.subTest(offset=offset, value=value):
                data = bytearray(self.pack)
                struct.pack_into('<I', data, offset, value)
                self.assertEqual(self.check(data), 1)

    def test_truncated_pack(self):
        for length in (0, 11, 100, len(self.pack) - 16):
            self.assertEqual(self.check(self.pack[:length]), 1)

    def test_stamp_rejects_downgrade_and_same_version_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'pack.pbl')
            path.write_bytes(self.pack)
            digest = hashlib.sha256(self.pack).hexdigest()
            with patch.object(repack, 'read_stamp', return_value={'version': 24, 'sha256': digest}):
                self.assertEqual(repack.check_version_bumped(path, 24), digest)
                with self.assertRaises(SystemExit):
                    repack.check_version_bumped(path, 23)
                path.write_bytes(self.pack + b'x')
                with self.assertRaises(SystemExit):
                    repack.write_stamp(path)
                self.assertTrue(repack.check_version_bumped(path, 25))


if __name__ == '__main__':
    unittest.main()
