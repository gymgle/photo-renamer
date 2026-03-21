import os
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import ANY, patch

import photo_renamer


class PhotoRenamerTests(unittest.TestCase):
    def setUp(self):
        photo_renamer.date_format = '%Y-%m-%d %H.%M.%S'
        photo_renamer.preview = False
        photo_renamer.force_rename = False
        photo_renamer.disable_regex = False
        photo_renamer.regex_offset = 0
        self.repo_root = os.path.dirname(os.path.dirname(__file__))

    def _close_logger_handlers(self):
        for handler in list(photo_renamer.logger.handlers):
            photo_renamer.logger.removeHandler(handler)
            handler.close()

    def test_resolve_target_path_avoids_multiple_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, 'IMG_20240316_101520.jpg')
            open(source_path, 'wb').close()
            open(os.path.join(tmp_dir, '2024-03-16 10.15.20.jpg'), 'wb').close()
            open(os.path.join(tmp_dir, '2024-03-16 10.15.20_IMG_20240316_101520.jpg'), 'wb').close()

            new_path = photo_renamer.resolve_target_path(source_path, '2024-03-16 10.15.20')

            self.assertEqual(
                new_path,
                os.path.join(tmp_dir, '2024-03-16 10.15.20_1_IMG_20240316_101520.jpg'),
            )

    def test_force_rename_does_not_skip_prefixed_filename(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, '2024-03-16 10.15.20_IMG_1.jpg')
            open(source_path, 'wb').close()

            photo_renamer.force_rename = True

            result = photo_renamer.rename_with_datetime(source_path, datetime(2024, 3, 17, 10, 15, 20))

            self.assertTrue(result)
            self.assertFalse(os.path.exists(source_path))
            self.assertTrue(os.path.exists(os.path.join(tmp_dir, '2024-03-17 10.15.20.jpg')))

    def test_linux_fallback_uses_mtime_instead_of_ctime(self):
        fake_stat = SimpleNamespace(st_ctime=500, st_mtime=100)

        with patch('photo_renamer.os.stat', return_value=fake_stat), \
                patch('photo_renamer.platform.system', return_value='Linux'), \
                patch('photo_renamer.datetime_from_filename', return_value=None):
            fallback = photo_renamer.get_fallback_datetime('/tmp/example.mp4')

        self.assertEqual(fallback, datetime.fromtimestamp(100))

    def test_datetime_from_filename_treats_three_digits_as_milliseconds(self):
        parsed = photo_renamer.datetime_from_filename('20240316_101520666_iOS.heic')

        self.assertEqual(parsed, datetime(2024, 3, 16, 10, 15, 20, 666000))

    def test_parse_extensions_supports_spaces_and_dots(self):
        parsed = photo_renamer.parse_extensions('jpg, png, .MOV ,, heic')

        self.assertEqual(parsed, ['.jpg', '.png', '.mov', '.heic'])

    def test_test_func_accepts_extensions_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            photo_renamer.dir_path = tmp_dir
            photo_renamer.log_path = ''
            photo_renamer.extensions = 'jpg, png'

            ok, err = photo_renamer.test_func()

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

            photo_renamer.extensions = 'jpg, png'
            photo_renamer.only_image = False
            photo_renamer.only_video = False
            photo_renamer.recursion = False

            with patch('photo_renamer.rename_photo') as rename_photo, patch('photo_renamer.rename_video') as rename_video:
                stats = photo_renamer.auto_rename(tmp_dir)

            self.assertEqual(stats.total_files, 2)
            self.assertEqual(stats.processed_files, 2)
            rename_photo.assert_any_call(jpg_path, ANY)
            rename_photo.assert_any_call(png_path, ANY)
            self.assertEqual(rename_photo.call_count, 2)
            rename_video.assert_not_called()

    def test_collect_media_files_respects_recursion_and_filters(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            nested_dir = os.path.join(tmp_dir, 'nested')
            os.mkdir(nested_dir)
            open(os.path.join(tmp_dir, 'root.jpg'), 'wb').close()
            open(os.path.join(nested_dir, 'child.mov'), 'wb').close()
            open(os.path.join(nested_dir, 'ignore.txt'), 'wb').close()

            config = photo_renamer.RunConfig(dir_path=tmp_dir, recursion=True, only_image=False, only_video=False)
            files, directories = photo_renamer.collect_media_files(tmp_dir, config)

        self.assertEqual(directories, 2)
        self.assertEqual(len(files), 2)
        self.assertTrue(any(path.endswith('root.jpg') for path in files))
        self.assertTrue(any(path.endswith('child.mov') for path in files))

    def test_auto_rename_collects_failures_in_stats(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            jpg_path = os.path.join(tmp_dir, 'photo.jpg')
            open(jpg_path, 'wb').close()

            config = photo_renamer.RunConfig(dir_path=tmp_dir)

            with patch('photo_renamer.rename_photo', side_effect=RuntimeError('broken metadata')):
                stats = photo_renamer.auto_rename(tmp_dir, config)

        self.assertEqual(stats.total_files, 1)
        self.assertEqual(stats.processed_files, 1)
        self.assertEqual(stats.failed_files, 1)
        self.assertEqual(len(stats.error_messages), 1)
        self.assertIn('broken metadata', stats.error_messages[0])

    def test_resolve_dropped_directory_supports_bytes_and_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_file = os.path.join(tmp_dir, 'sample.jpg')
            open(sample_file, 'wb').close()

            resolved = photo_renamer.resolve_dropped_directory([sample_file.encode()])

        self.assertEqual(resolved, tmp_dir)

    def test_format_stats_summary_includes_error_excerpt(self):
        stats = photo_renamer.RunStats(
            total_files=3,
            processed_files=3,
            previewed_files=2,
            failed_files=1,
            directories_scanned=1,
            error_messages=['photo.jpg: broken metadata'],
        )

        summary = photo_renamer.format_stats_summary(stats, preview_mode=True)

        self.assertIn('匹配文件: 3', summary)
        self.assertIn('预览结果: 2', summary)
        self.assertIn('photo.jpg: broken metadata', summary)

    def test_format_stats_summary_supports_english(self):
        stats = photo_renamer.RunStats(
            total_files=2,
            processed_files=2,
            renamed_files=1,
            skipped_files=1,
            directories_scanned=1,
        )

        summary = photo_renamer.format_stats_summary(stats, preview_mode=False, language='en-US')

        self.assertIn('Scanned folders: 1', summary)
        self.assertIn('Matched files: 2', summary)
        self.assertIn('Renamed: 1', summary)

    def test_translate_falls_back_to_default_language(self):
        translated = photo_renamer.translate('fr-FR', 'run_button')

        self.assertEqual(translated, '开始处理')

    def test_translation_keys_match_between_languages(self):
        zh_keys = set(photo_renamer.TRANSLATIONS['zh-CN'])
        en_keys = set(photo_renamer.TRANSLATIONS['en-US'])

        self.assertSetEqual(zh_keys, en_keys)

    def test_mode_display_name_supports_english(self):
        translated = photo_renamer.mode_display_name('en-US', 'pro')

        self.assertEqual(translated, 'Pro')

    def test_localize_validation_message_supports_english(self):
        translated = photo_renamer.localize_validation_message('file path need to be specified with -d argument', 'en-US')

        self.assertEqual(translated, 'Please choose a folder to process first.')

    def test_init_logger_skips_missing_console_sink(self):
        self._close_logger_handlers()

        with tempfile.TemporaryDirectory() as tmp_dir, \
                patch.object(photo_renamer.sys, 'stdout', None), \
                patch.object(photo_renamer.sys, 'stderr', None):
            photo_renamer.init_logger(target_log_path=tmp_dir, extra_sink=lambda message: None)

            self.assertEqual(len(photo_renamer.logger.handlers), 2)
            self.assertTrue(any(isinstance(handler, photo_renamer.CallbackLogHandler) for handler in photo_renamer.logger.handlers))
            self.assertTrue(any(isinstance(handler, RotatingFileHandler) for handler in photo_renamer.logger.handlers))
            self._close_logger_handlers()

    def test_init_logger_emits_plain_messages_to_gui_sink(self):
        emitted_messages = []

        with tempfile.TemporaryDirectory() as tmp_dir, \
                patch.object(photo_renamer.sys, 'stdout', None), \
                patch.object(photo_renamer.sys, 'stderr', None):
            photo_renamer.init_logger(target_log_path=tmp_dir, extra_sink=emitted_messages.append)
            photo_renamer.logger.info('Started processing...')

            self.assertTrue(emitted_messages)
            self.assertEqual(emitted_messages[-1], 'Started processing...')
            self._close_logger_handlers()

    def test_main_without_args_launches_gui(self):
        with patch('photo_renamer.launch_gui', return_value=0) as launch_gui:
            result = photo_renamer.main()

        self.assertEqual(result, 0)
        launch_gui.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()