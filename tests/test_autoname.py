import os
import io
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import autoname


class AutonameTests(unittest.TestCase):
    def setUp(self):
        autoname.date_format = '%Y-%m-%d %H.%M.%S'
        autoname.preview = False
        autoname.force_rename = False
        autoname.disable_regex = False
        autoname.regex_offset = 0
        self.repo_root = os.path.dirname(os.path.dirname(__file__))

    def test_resolve_target_path_avoids_multiple_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, 'IMG_20240316_101520.jpg')
            open(source_path, 'wb').close()
            open(os.path.join(tmp_dir, '2024-03-16 10.15.20.jpg'), 'wb').close()
            open(os.path.join(tmp_dir, '2024-03-16 10.15.20_IMG_20240316_101520.jpg'), 'wb').close()

            new_path = autoname.resolve_target_path(source_path, '2024-03-16 10.15.20')

            self.assertEqual(
                new_path,
                os.path.join(tmp_dir, '2024-03-16 10.15.20_1_IMG_20240316_101520.jpg'),
            )

    def test_force_rename_does_not_skip_prefixed_filename(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, '2024-03-16 10.15.20_IMG_1.jpg')
            open(source_path, 'wb').close()

            autoname.force_rename = True

            result = autoname.rename_with_datetime(source_path, datetime(2024, 3, 17, 10, 15, 20))

            self.assertTrue(result)
            self.assertFalse(os.path.exists(source_path))
            self.assertTrue(os.path.exists(os.path.join(tmp_dir, '2024-03-17 10.15.20.jpg')))

    def test_linux_fallback_uses_mtime_instead_of_ctime(self):
        fake_stat = SimpleNamespace(st_ctime=500, st_mtime=100)

        with patch('autoname.os.stat', return_value=fake_stat), \
                patch('autoname.platform.system', return_value='Linux'), \
                patch('autoname.datetime_from_filename', return_value=None):
            fallback = autoname.get_fallback_datetime('/tmp/example.mp4')

        self.assertEqual(fallback, datetime.fromtimestamp(100))

    def test_only_image_and_only_video_are_mutually_exclusive(self):
        parser = autoname.create_parser()
        stderr = io.StringIO()

        with patch('sys.stderr', stderr):
            with self.assertRaises(SystemExit) as exc:
                parser.parse_args(['-oi', '-ov'])

        self.assertEqual(exc.exception.code, 2)
        self.assertIn('not allowed with argument', stderr.getvalue())

    def test_datetime_from_filename_treats_three_digits_as_milliseconds(self):
        parsed = autoname.datetime_from_filename('20240316_101520666_iOS.heic')

        self.assertEqual(parsed, datetime(2024, 3, 16, 10, 15, 20, 666000))

    def test_parse_extensions_supports_spaces_and_dots(self):
        parsed = autoname.parse_extensions('jpg, png, .MOV ,, heic')

        self.assertEqual(parsed, ['.jpg', '.png', '.mov', '.heic'])

    def test_test_func_accepts_extensions_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            autoname.dir_path = tmp_dir
            autoname.log_path = ''
            autoname.extensions = 'jpg, png'

            ok, err = autoname.test_func()

        self.assertTrue(ok)
        self.assertEqual(err, 'tests passed')

    def test_auto_rename_filters_files_with_spaced_extension_list(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            jpg_path = os.path.join(tmp_dir, 'photo.jpg')
            png_path = os.path.join(tmp_dir, 'image.png')
            mov_path = os.path.join(tmp_dir, 'video.mov')
            open(jpg_path, 'wb').close()
            open(png_path, 'wb').close()
            open(mov_path, 'wb').close()

            autoname.extensions = 'jpg, png'
            autoname.only_image = False
            autoname.only_video = False
            autoname.recursion = False

            with patch('autoname.rename_photo') as rename_photo, patch('autoname.rename_video') as rename_video:
                result = autoname.auto_rename(tmp_dir)

            self.assertTrue(result)
            rename_photo.assert_any_call(jpg_path)
            rename_photo.assert_any_call(png_path)
            self.assertEqual(rename_photo.call_count, 2)
            rename_video.assert_not_called()

    def test_cli_rejects_conflicting_media_filters(self):
        result = subprocess.run(
            [sys.executable, os.path.join(self.repo_root, 'autoname.py'), '-oi', '-ov'],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn('not allowed with argument', result.stderr)

    def test_cli_prints_version(self):
        result = subprocess.run(
            [sys.executable, os.path.join(self.repo_root, 'autoname.py'), '--version'],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), f'version {autoname.Version}')

    def test_cli_preview_reports_rename_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, 'IMG_20240316_101520.jpg')
            target_path = os.path.join(tmp_dir, '2024-03-16 10.15.20.jpg')
            open(source_path, 'wb').close()

            result = subprocess.run(
                [
                    sys.executable,
                    os.path.join(self.repo_root, 'autoname.py'),
                    '-d',
                    tmp_dir,
                    '-p',
                    '-lp',
                    tmp_dir,
                ],
                capture_output=True,
                text=True,
                cwd=self.repo_root,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn('IMG_20240316_101520.jpg -> 2024-03-16 10.15.20.jpg', result.stdout)
            self.assertTrue(os.path.exists(source_path))
            self.assertFalse(os.path.exists(target_path))


if __name__ == '__main__':
    unittest.main()