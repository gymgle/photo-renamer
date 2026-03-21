import os
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

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

    def test_test_func_returns_structured_error_for_missing_dir(self):
        photo_renamer.dir_path = ''

        ok, err = photo_renamer.test_func()

        self.assertFalse(ok)
        self.assertEqual(err, photo_renamer.ValidationError('missing_dir'))

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

    def test_localize_validation_message_supports_structured_error_in_english(self):
        translated = photo_renamer.localize_validation_message(photo_renamer.ValidationError('missing_dir'), 'en-US')

        self.assertEqual(translated, 'Please choose a folder to process first.')

    def test_localize_validation_message_translates_missing_target_dir_to_chinese(self):
        translated = photo_renamer.localize_validation_message('D:/missing-folder is not exist', 'zh-CN')

        self.assertEqual(translated, '要处理的文件夹不存在: D:/missing-folder')

    def test_localize_validation_message_translates_structured_missing_target_dir_to_chinese(self):
        translated = photo_renamer.localize_validation_message(
            photo_renamer.ValidationError('dir_not_exist', 'D:/missing-folder'),
            'zh-CN',
        )

        self.assertEqual(translated, '要处理的文件夹不存在: D:/missing-folder')

    def test_localize_validation_message_translates_missing_target_dir_to_english(self):
        translated = photo_renamer.localize_validation_message('D:/missing-folder is not exist', 'en-US')

        self.assertEqual(translated, 'The folder to process does not exist: D:/missing-folder')

    def test_localize_validation_message_translates_structured_missing_log_dir_to_english(self):
        translated = photo_renamer.localize_validation_message(
            photo_renamer.ValidationError('missing_log_dir', 'D:/missing-log-dir'),
            'en-US',
        )

        self.assertEqual(translated, 'The selected log folder does not exist: D:/missing-log-dir')

    def test_localize_validation_message_translates_legacy_missing_log_dir_to_chinese(self):
        translated = photo_renamer.localize_validation_message('log path D:/missing-log-dir is not exist', 'zh-CN')

        self.assertEqual(translated, '日志保存位置不存在: D:/missing-log-dir')

    def test_execute_returns_localized_validation_error(self):
        config = photo_renamer.RunConfig(dir_path='')

        with patch('photo_renamer.init_logger'), patch.object(photo_renamer.logger, 'error') as mock_error:
            ok, err = photo_renamer.execute(config, language='en-US')

        self.assertFalse(ok)
        self.assertEqual(err, 'Please choose a folder to process first.')
        mock_error.assert_called_once_with('Please choose a folder to process first.')

    def test_execute_returns_localized_missing_log_dir_with_path(self):
        config = photo_renamer.RunConfig(dir_path='D:/ok', log_to_file=True, log_path='D:/missing-log-dir')

        with patch('photo_renamer.init_logger'), \
                patch('photo_renamer.os.path.exists', side_effect=lambda path: path == 'D:/ok'), \
                patch.object(photo_renamer.logger, 'error') as mock_error:
            ok, err = photo_renamer.execute(config, language='en-US')

        self.assertFalse(ok)
        self.assertEqual(err, 'The selected log folder does not exist: D:/missing-log-dir')
        mock_error.assert_called_once_with('The selected log folder does not exist: D:/missing-log-dir')

    def test_test_func_ignores_missing_log_dir_when_file_logging_disabled(self):
        config = photo_renamer.RunConfig(dir_path='D:/ok', log_to_file=False, log_path='D:/missing-log-dir')

        with patch('photo_renamer.os.path.exists', side_effect=lambda path: path == 'D:/ok'):
            ok, err = photo_renamer.test_func(config)

        self.assertTrue(ok)
        self.assertEqual(err, 'tests passed')

    def test_format_about_message_contains_version_and_repo_url(self):
        message = photo_renamer.format_about_message('zh-CN')

        self.assertIn('photo-renamer', message)
        self.assertIn(f'版本: {photo_renamer.Version}', message)
        self.assertIn(photo_renamer.OPEN_SOURCE_URL, message)

    def test_format_about_message_supports_english(self):
        message = photo_renamer.format_about_message('en-US')

        self.assertIn(f'Version: {photo_renamer.Version}', message)
        self.assertIn(f'Open source: {photo_renamer.OPEN_SOURCE_URL}', message)

    def test_apply_window_icon_sets_default_and_current_icon(self):
        window = Mock()

        with patch('photo_renamer.app_icon_path', return_value='C:/tmp/icon.ico'), \
                patch('photo_renamer.os.path.exists', return_value=True):
            photo_renamer.apply_window_icon(window)

        window.iconbitmap.assert_any_call(default='C:/tmp/icon.ico')
        window.iconbitmap.assert_any_call('C:/tmp/icon.ico')
        self.assertEqual(window.iconbitmap.call_count, 2)

    def test_center_window_places_window_in_screen_center(self):
        window = Mock()
        window.winfo_width.return_value = 740
        window.winfo_height.return_value = 640
        window.winfo_reqwidth.return_value = 740
        window.winfo_reqheight.return_value = 640
        window.winfo_screenwidth.return_value = 1920
        window.winfo_screenheight.return_value = 1080
        window.winfo_rootx.return_value = 8
        window.winfo_x.return_value = 0
        window.winfo_rooty.return_value = 31
        window.winfo_y.return_value = 0

        photo_renamer.center_window(window)

        window.update_idletasks.assert_called_once_with()
        window.geometry.assert_called_once_with('740x640+582+200')

    def test_center_child_window_places_dialog_relative_to_parent(self):
        window = Mock()
        window.winfo_width.return_value = 420
        window.winfo_height.return_value = 180
        window.winfo_reqwidth.return_value = 420
        window.winfo_reqheight.return_value = 180
        window.winfo_rootx.return_value = 8
        window.winfo_x.return_value = 0
        window.winfo_rooty.return_value = 31
        window.winfo_y.return_value = 0

        parent = Mock()
        parent.winfo_rootx.return_value = 300
        parent.winfo_rooty.return_value = 200
        parent.winfo_width.return_value = 740
        parent.winfo_height.return_value = 640

        photo_renamer.center_child_window(window, parent)

        window.update_idletasks.assert_called_once_with()
        parent.update_idletasks.assert_called_once_with()
        window.geometry.assert_called_once_with('+452+410')

    def test_center_child_window_uses_parent_frame_for_hidden_dialog(self):
        window = Mock()
        window.winfo_width.return_value = 420
        window.winfo_height.return_value = 180
        window.winfo_reqwidth.return_value = 420
        window.winfo_reqheight.return_value = 180
        window.winfo_rootx.return_value = 0
        window.winfo_x.return_value = 0
        window.winfo_rooty.return_value = 0
        window.winfo_y.return_value = 0

        parent = Mock()
        parent.winfo_rootx.return_value = 300
        parent.winfo_x.return_value = 292
        parent.winfo_rooty.return_value = 200
        parent.winfo_y.return_value = 169
        parent.winfo_width.return_value = 740
        parent.winfo_height.return_value = 640

        photo_renamer.center_child_window(window, parent)

        window.geometry.assert_called_once_with('+452+410')

    def test_present_modal_dialog_centers_before_showing(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        gui.root = Mock()

        dialog = Mock()
        focus_widget = Mock()

        with patch('photo_renamer.center_child_window') as center_child_window:
            gui._present_modal_dialog(dialog, focus_widget=focus_widget, wait=True)

        center_child_window.assert_called_once_with(dialog, gui.root)
        dialog.deiconify.assert_called_once_with()
        dialog.lift.assert_called_once_with(gui.root)
        focus_widget.focus_set.assert_called_once_with()
        gui.root.wait_window.assert_called_once_with(dialog)

    def test_present_root_window_reveals_after_centering(self):
        window = Mock()

        with patch('photo_renamer.center_window') as center_window:
            photo_renamer.present_root_window(window)

        center_window.assert_called_once_with(window)
        window.attributes.assert_any_call('-alpha', 0.0)
        window.deiconify.assert_called_once_with()
        window.attributes.assert_any_call('-alpha', 1.0)

    def test_dialog_wraplength_respects_min_and_max_width(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        fake_font = Mock()
        fake_font.measure.side_effect = lambda text: len(text) * 10

        with patch('photo_renamer.tkfont.nametofont', return_value=fake_font):
            short_wrap = gui._dialog_wraplength('short')
            long_wrap = gui._dialog_wraplength('x' * 200)

        self.assertEqual(short_wrap, 280)
        self.assertEqual(long_wrap, 560)

    def test_dialog_wraplength_uses_custom_min_width(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        fake_font = Mock()
        fake_font.measure.side_effect = lambda text: len(text) * 10

        with patch('photo_renamer.tkfont.nametofont', return_value=fake_font):
            wrap = gui._dialog_wraplength('done', min_width=420)

        self.assertEqual(wrap, 420)

    def test_show_input_error_uses_custom_modal_dialog(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        gui._append_log = Mock()
        gui._show_message_dialog = Mock()
        gui._text = lambda key, **kwargs: {'dialog_input_title': 'Invalid input'}[key]

        gui._show_input_error('Bad value')

        gui._append_log.assert_called_once_with('Invalid input: Bad value')
        gui._show_message_dialog.assert_called_once_with('Invalid input', 'Bad value')

    def test_show_message_dialog_applies_dialog_min_width(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        dialog = Mock()
        ok_button = Mock()
        content = Mock()
        actions = Mock()
        gui._create_modal_dialog = Mock(return_value=dialog)
        gui._dialog_wraplength = Mock(return_value=420)
        gui._present_modal_dialog = Mock()

        with patch('photo_renamer.ttk.Frame', side_effect=[content, actions]), \
                patch('photo_renamer.ttk.Label') as mock_label, \
                patch('photo_renamer.ttk.Button', return_value=ok_button):
            gui._show_message_dialog('Finished', 'Summary', min_width=420)

        dialog.minsize.assert_called_once_with(420, 1)
        gui._dialog_wraplength.assert_called_once_with('Summary', min_width=420)
        mock_label.return_value.pack.assert_called_once_with(anchor='w', fill='x')
        gui._present_modal_dialog.assert_called_once_with(dialog, focus_widget=ok_button, wait=True)

    def test_start_job_uses_custom_modal_dialog_when_busy(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        gui.worker = Mock()
        gui.worker.is_alive.return_value = True
        gui._show_message_dialog = Mock()
        gui._text = lambda key, **kwargs: {
            'dialog_busy_title': 'Processing',
            'dialog_busy_message': 'Please wait.',
        }[key]

        gui._start_job()

        gui._show_message_dialog.assert_called_once_with('Processing', 'Please wait.')

    def test_update_done_metric_label_uses_run_state_not_checkbox_state(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        gui.metric_labels = [Mock(), Mock(), Mock(), Mock(), Mock(), Mock()]
        gui.done_metric_preview_mode = False
        gui.preview_var = Mock()
        gui.preview_var.get.return_value = True
        gui._text = lambda key, **kwargs: key

        gui._update_done_metric_label()

        gui.metric_labels[3].configure.assert_called_once_with(text='metric_done_renamed')

    def test_start_job_updates_done_metric_label_from_current_preview_choice(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        gui.worker = None
        gui._clear_log_output = Mock()
        config = photo_renamer.RunConfig(dir_path='D:/photos', preview=True)
        gui._build_config = Mock(return_value=config)
        gui._show_input_error = Mock()
        gui.language_var = Mock()
        gui.language_var.get.return_value = 'zh-CN'
        gui._reset_progress_view = Mock()
        gui._refresh_run_button = Mock()
        gui._append_log = Mock()
        gui._run_job = Mock()
        gui._update_done_metric_label = Mock()
        gui.done_metric_preview_mode = False
        gui._text = lambda key, **kwargs: {'log_start': '开始处理...'}[key]

        with patch('photo_renamer.test_func', return_value=(True, 'tests passed')), \
                patch('photo_renamer.Thread') as thread_cls:
            thread_instance = Mock()
            thread_cls.return_value = thread_instance

            gui._start_job()

        self.assertTrue(gui.done_metric_preview_mode)
        gui._update_done_metric_label.assert_called_once_with()

    def test_init_logger_skips_missing_console_sink(self):
        self._close_logger_handlers()

        with tempfile.TemporaryDirectory() as tmp_dir, \
                patch.object(photo_renamer.sys, 'stdout', None), \
                patch.object(photo_renamer.sys, 'stderr', None):
            photo_renamer.init_logger(target_log_path=tmp_dir, extra_sink=lambda message: None, log_to_file_enabled=True)

            self.assertEqual(len(photo_renamer.logger.handlers), 2)
            self.assertTrue(any(isinstance(handler, photo_renamer.CallbackLogHandler) for handler in photo_renamer.logger.handlers))
            self.assertTrue(any(isinstance(handler, RotatingFileHandler) for handler in photo_renamer.logger.handlers))
            self._close_logger_handlers()

    def test_init_logger_skips_file_handler_when_file_logging_disabled(self):
        self._close_logger_handlers()

        with patch.object(photo_renamer.sys, 'stdout', None), \
                patch.object(photo_renamer.sys, 'stderr', None):
            photo_renamer.init_logger(extra_sink=lambda message: None, log_to_file_enabled=False)

            self.assertEqual(len(photo_renamer.logger.handlers), 1)
            self.assertTrue(any(isinstance(handler, photo_renamer.CallbackLogHandler) for handler in photo_renamer.logger.handlers))
            self.assertFalse(any(isinstance(handler, RotatingFileHandler) for handler in photo_renamer.logger.handlers))
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

    def test_build_config_includes_log_to_file_toggle(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        gui.media_mode_var = Mock()
        gui.media_mode_var.get.return_value = 'all'
        gui.regex_offset_var = Mock()
        gui.regex_offset_var.get.return_value = ''
        gui.dir_var = Mock()
        gui.dir_var.get.return_value = 'D:/photos'
        gui.format_var = Mock()
        gui.format_var.get.return_value = ''
        gui.recursion_var = Mock()
        gui.recursion_var.get.return_value = True
        gui.preview_var = Mock()
        gui.preview_var.get.return_value = False
        gui.disable_regex_var = Mock()
        gui.disable_regex_var.get.return_value = False
        gui.extension_var = Mock()
        gui.extension_var.get.return_value = 'jpg'
        gui.force_rename_var = Mock()
        gui.force_rename_var.get.return_value = True
        gui.log_level_var = Mock()
        gui.log_level_var.get.return_value = 'INFO'
        gui.log_to_file_var = Mock()
        gui.log_to_file_var.get.return_value = True
        gui.log_path_var = Mock()
        gui.log_path_var.get.return_value = 'D:/logs'

        config = gui._build_config()

        self.assertTrue(config.log_to_file)
        self.assertEqual(config.log_path, 'D:/logs')

    def test_update_log_file_controls_grays_out_log_path_when_disabled(self):
        gui = object.__new__(photo_renamer.PhotoRenamerGUI)
        gui.log_to_file_var = Mock()
        gui.log_to_file_var.get.return_value = False
        gui.log_dir_label = Mock()
        gui.log_dir_entry = Mock()
        gui.log_dir_button = Mock()

        gui._update_log_file_controls()

        gui.log_dir_label.configure.assert_called_once_with(foreground='#9ca3af')
        gui.log_dir_entry.configure.assert_called_once_with(state='disabled')
        gui.log_dir_button.configure.assert_called_once_with(state='disabled')

    def test_main_without_args_launches_gui(self):
        with patch('photo_renamer.launch_gui', return_value=0) as launch_gui:
            result = photo_renamer.main()

        self.assertEqual(result, 0)
        launch_gui.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()