#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import platform
import re
import subprocess
import sys
import time
import webbrowser
import gc
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from logging.handlers import RotatingFileHandler
from multiprocessing import freeze_support
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable, cast

import exifread
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, ttk
except ImportError:  # pragma: no cover
    tk = cast(Any, None)
    tkfont = cast(Any, None)
    filedialog = cast(Any, None)
    ttk = cast(Any, None)

try:
    import windnd
except ImportError:  # pragma: no cover
    windnd = cast(Any, None)

Version = '1.0.0'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H.%M.%S'
OPEN_SOURCE_URL = 'https://github.com/gymgle/photo-renamer/'

Photos = ['.jpg', '.jpeg', '.heic', '.png', '.gif', '.nef']
Videos = ['.mp4', '.mov']
SUPPORTED_MEDIA = set(Photos + Videos)

LOGGER_FORMAT = '%(levelname)s | %(message)s'

logger = logging.getLogger('photo-renamer')
logger.propagate = False


class CallbackLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        self.callback(record.getMessage())

LANGUAGE_OPTIONS = {
    'zh-CN': '简体中文',
    'en-US': 'English',
}

APP_DISPLAY_NAMES = {
    'zh-CN': '照片重命名助手',
    'en-US': 'Photo Renamer',
}

UI_MODE_OPTIONS = ('simple', 'pro')

TRANSLATIONS = {
    'zh-CN': {
        'app_tagline': '根据拍摄时间重命名你的照片和视频',
        'mode_label': '界面模式',
        'mode_simple': '简洁模式',
        'mode_pro': '专业模式',
        'language_label': '界面语言',
        'about_button': '关于',
        'settings_frame': '处理设置',
        'advanced_frame': '更多设置',
        'target_dir': '要处理的文件夹',
        'browse': '浏览',
        'show_more_settings': '展开更多设置',
        'hide_more_settings': '收起更多设置',
        'filename_format': '新文件名格式',
        'extension_filter': '只处理这些格式',
        'time_offset': '文件名时间偏移',
        'log_level': '日志详细程度',
        'log_to_file': '同时写入日志文件',
        'log_dir': '日志保存位置（默认当前文件夹）',
        'include_subdirs': '包含子文件夹',
        'preview_only': '仅预览新名字，不执行重命名',
        'disable_filename_time': '不从文件名里找时间',
        'force_rename': '即使文件名看起来已正确也重新处理',
        'scope_frame': '处理范围',
        'scope_all': '全部',
        'scope_images': '仅图片',
        'scope_videos': '仅视频',
        'progress_frame': '处理进度',
        'metric_dirs': '扫描目录',
        'metric_total': '找到文件',
        'metric_processed': '已处理',
        'metric_done_preview': '预览结果',
        'metric_done_renamed': '已重命名',
        'metric_skipped': '跳过',
        'metric_failed': '失败',
        'log_frame': '处理记录',
        'open_log_dir': '打开日志目录',
        'open_log_dir_missing': '当前没有可打开的日志目录。',
        'open_log_dir_failed': '无法打开日志目录: {value}',
        'footer_tip': '💡 建议先勾选“仅预览新名字”，确认结果后再正式执行。',
        'run_button': '开始处理',
        'run_button_running': '处理中...',
        'drop_hint_no_dnd': '可以点击“浏览”选择文件夹。安装 windnd 后也可以直接拖进窗口。',
        'drop_hint_dnd': '可以把文件夹或文件直接拖到窗口中，拖入文件时会自动使用它所在的文件夹。',
        'select_target_dir': '选择要处理的文件夹',
        'select_log_dir': '选择日志保存位置',
        'progress_idle': '未开始',
        'progress_scanning': '已开始处理，正在查找文件...',
        'progress_none': '没有找到符合当前条件的照片或视频',
        'progress_done': '处理完成: {processed}/{total}',
        'progress_running': '正在处理: {processed}/{total}',
        'current_file': '当前文件: {name}',
        'dialog_busy_title': '正在处理',
        'dialog_busy_message': '当前任务还没有完成，请稍等。',
        'dialog_input_title': '输入有误',
        'dialog_offset_error': '“文件名时间偏移”必须填写数字。',
        'log_start': '开始处理...',
        'dialog_done_title': '处理完成',
        'dialog_failed_title': '处理失败',
        'drag_selected_dir': '已通过拖拽选择目录: {path}',
        'summary_dirs': '扫描目录: {value}',
        'summary_total': '匹配文件: {value}',
        'summary_processed': '已处理: {value}',
        'summary_skipped': '跳过: {value}',
        'summary_failed': '失败: {value}',
        'summary_previewed': '预览结果: {value}',
        'summary_renamed': '已重命名: {value}',
        'summary_log_file': '日志文件: {value}',
        'summary_errors': '错误摘要:',
        'summary_error_item': '- {message}',
        'summary_more_errors': '- 还有 {value} 条未展示',
        'language_switched': '界面语言已切换为简体中文。',
        'about_title': '关于',
        'about_version': '版本: {version}',
        'about_open_source': '开源地址: {url}',
        'validation_missing_dir': '请先选择要处理的文件夹。',
        'validation_dir_not_exist': '要处理的文件夹不存在: {value}',
        'validation_missing_log_dir': '日志保存位置不存在。',
        'validation_log_dir_not_exist': '日志保存位置不存在: {value}',
        'validation_invalid_format': '新文件名格式无效。',
        'validation_invalid_extension': '包含不支持的文件格式: {value}',
        'validation_conflicting_media': '不能同时只处理图片和只处理视频。',
    },
    'en-US': {
        'app_tagline': 'Rename your photos and videos by capture time',
        'mode_label': 'Mode',
        'mode_simple': 'Simple',
        'mode_pro': 'Pro',
        'language_label': 'Language',
        'about_button': 'About',
        'settings_frame': 'Settings',
        'advanced_frame': 'More settings',
        'target_dir': 'Folder to process',
        'browse': 'Browse',
        'show_more_settings': 'Show more settings',
        'hide_more_settings': 'Hide more settings',
        'filename_format': 'New filename format',
        'extension_filter': 'Only these formats',
        'time_offset': 'Filename time offset',
        'log_level': 'Log detail',
        'log_to_file': 'Also save logs to file',
        'log_dir': 'Log save location (default current folder)',
        'include_subdirs': 'Include subfolders',
        'preview_only': 'Preview only, will not rename',
        'disable_filename_time': 'Do not read time from filename',
        'force_rename': 'Reprocess even if the name already looks correct',
        'scope_frame': 'Scope',
        'scope_all': 'All',
        'scope_images': 'Images only',
        'scope_videos': 'Videos only',
        'progress_frame': 'Progress',
        'metric_dirs': 'Scanned folders',
        'metric_total': 'Files found',
        'metric_processed': 'Processed',
        'metric_done_preview': 'Preview results',
        'metric_done_renamed': 'Renamed',
        'metric_skipped': 'Skipped',
        'metric_failed': 'Failed',
        'log_frame': 'Activity log',
        'open_log_dir': 'Open Log Folder',
        'open_log_dir_missing': 'There is no log folder to open yet.',
        'open_log_dir_failed': 'Failed to open log folder: {value}',
        'footer_tip': '💡 It is safer to keep “Preview only” enabled first, confirm the results before renaming.',
        'run_button': 'Start',
        'run_button_running': 'Processing...',
        'drop_hint_no_dnd': 'Click Browse to choose a folder. If windnd is installed, you can also drag files or folders into the window.',
        'drop_hint_dnd': 'Drag a folder or file into the window. If you drop a file, its parent folder will be used.',
        'select_target_dir': 'Choose a folder to process',
        'select_log_dir': 'Choose where to save logs',
        'progress_idle': 'Not started',
        'progress_scanning': 'Started. Looking for files...',
        'progress_none': 'No photo or video matched the current filters',
        'progress_done': 'Completed: {processed}/{total}',
        'progress_running': 'Processing: {processed}/{total}',
        'current_file': 'Current file: {name}',
        'dialog_busy_title': 'Processing',
        'dialog_busy_message': 'The current job is still running. Please wait.',
        'dialog_input_title': 'Invalid input',
        'dialog_offset_error': '“Filename time offset” must be a number.',
        'log_start': 'Started processing...',
        'dialog_done_title': 'Finished',
        'dialog_failed_title': 'Failed',
        'drag_selected_dir': 'Selected folder by drag and drop: {path}',
        'summary_dirs': 'Scanned folders: {value}',
        'summary_total': 'Matched files: {value}',
        'summary_processed': 'Processed: {value}',
        'summary_skipped': 'Skipped: {value}',
        'summary_failed': 'Failed: {value}',
        'summary_previewed': 'Preview results: {value}',
        'summary_renamed': 'Renamed: {value}',
        'summary_log_file': 'Log file: {value}',
        'summary_errors': 'Error summary:',
        'summary_error_item': '- {message}',
        'summary_more_errors': '- {value} more not shown',
        'language_switched': 'Switched interface language to English.',
        'about_title': 'About',
        'about_version': 'Version: {version}',
        'about_open_source': 'Open source: {url}',
        'validation_missing_dir': 'Please choose a folder to process first.',
        'validation_dir_not_exist': 'The folder to process does not exist: {value}',
        'validation_missing_log_dir': 'The selected log folder does not exist.',
        'validation_log_dir_not_exist': 'The selected log folder does not exist: {value}',
        'validation_invalid_format': 'The filename format is invalid.',
        'validation_invalid_extension': 'Contains unsupported file format: {value}',
        'validation_conflicting_media': 'You cannot select both images only and videos only at the same time.',
    },
}


def translate(language: str, key: str, **kwargs) -> str:
    fallback_language = 'zh-CN'
    template = TRANSLATIONS.get(language, {}).get(key)
    if template is None:
        template = TRANSLATIONS[fallback_language].get(key, key)
    return template.format(**kwargs)


def mode_display_name(language: str, mode: str) -> str:
    return translate(language, f'mode_{mode}')


def app_display_name(language: str) -> str:
    return APP_DISPLAY_NAMES.get(language, APP_DISPLAY_NAMES['zh-CN'])


def format_about_message(language: str) -> str:
    return '\n'.join([
        app_display_name(language),
        translate(language, 'about_version', version=Version),
        translate(language, 'about_open_source', url=OPEN_SOURCE_URL),
    ])


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def app_icon_path() -> str:
    return resource_path(os.path.join('assets', 'icon.ico'))


def apply_window_icon(window) -> None:
    icon_path = app_icon_path()
    if not os.path.exists(icon_path):
        return

    try:
        window.iconbitmap(default=icon_path)
    except Exception:
        pass

    try:
        window.iconbitmap(icon_path)
    except Exception:
        pass


def center_window(window) -> None:
    window.update_idletasks()

    width = window.winfo_width() or window.winfo_reqwidth()
    height = window.winfo_height() or window.winfo_reqheight()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    frame_width = max(window.winfo_rootx() - window.winfo_x(), 0)
    titlebar_height = max(window.winfo_rooty() - window.winfo_y(), 0)
    outer_width = width + frame_width * 2
    outer_height = height + titlebar_height + frame_width

    x_pos = max((screen_width - outer_width) // 2, 0)
    y_pos = max((screen_height - outer_height) // 2, 0)

    window.geometry(f'{width}x{height}+{x_pos}+{y_pos}')


def center_child_window(window, parent) -> None:
    window.update_idletasks()
    parent.update_idletasks()

    width = window.winfo_width() or window.winfo_reqwidth()
    height = window.winfo_height() or window.winfo_reqheight()

    frame_width = max(window.winfo_rootx() - window.winfo_x(), 0)
    titlebar_height = max(window.winfo_rooty() - window.winfo_y(), 0)
    if frame_width == 0 and titlebar_height == 0:
        frame_width = max(parent.winfo_rootx() - parent.winfo_x(), 0)
        titlebar_height = max(parent.winfo_rooty() - parent.winfo_y(), 0)

    outer_width = width + frame_width * 2
    outer_height = height + titlebar_height + frame_width

    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()

    x_pos = max(parent_x + (parent_width - outer_width) // 2, 0)
    y_pos = max(parent_y + (parent_height - outer_height) // 2, 0)

    window.geometry(f'+{x_pos}+{y_pos}')


def present_root_window(window) -> None:
    try:
        window.attributes('-alpha', 0.0)
    except Exception:
        pass

    window.deiconify()
    center_window(window)

    try:
        window.attributes('-alpha', 1.0)
    except Exception:
        pass


def localize_validation_message(message: 'ValidationError | str', language: str) -> str:
    if isinstance(message, ValidationError):
        if message.code == 'missing_dir':
            return translate(language, 'validation_missing_dir')
        if message.code == 'dir_not_exist':
            return translate(language, 'validation_dir_not_exist', value=message.value)
        if message.code == 'missing_log_dir':
            if message.value:
                return translate(language, 'validation_log_dir_not_exist', value=message.value)
            return translate(language, 'validation_missing_log_dir')
        if message.code == 'invalid_format':
            return translate(language, 'validation_invalid_format')
        if message.code == 'invalid_extension':
            return translate(language, 'validation_invalid_extension', value=message.value)
        if message.code == 'conflicting_media':
            return translate(language, 'validation_conflicting_media')
        return message.value or message.code

    if message == 'file path need to be specified with -d argument':
        return translate(language, 'validation_missing_dir')
    if message.endswith(' is not exist') and not message.startswith('log path '):
        missing_path = message[:-len(' is not exist')]
        return translate(language, 'validation_dir_not_exist', value=missing_path)
    if message.startswith('log path ') and message.endswith(' is not exist'):
        missing_path = message[len('log path '):-len(' is not exist')]
        return translate(language, 'validation_log_dir_not_exist', value=missing_path)
    if message.startswith('date format invalid:'):
        return translate(language, 'validation_invalid_format')
    if message.startswith('extension ') and message.endswith(' is not supported'):
        ext_name = message[len('extension '):-len(' is not supported')]
        return translate(language, 'validation_invalid_extension', value=ext_name)
    if message == 'only-image and only-video cannot be enabled together':
        return translate(language, 'validation_conflicting_media')
    return message


@dataclass(slots=True)
class RunConfig:
    dir_path: str = ''
    date_format: str = DEFAULT_DATE_FORMAT
    recursion: bool = False
    preview: bool = False
    disable_regex: bool = False
    extensions: str = ''
    force_rename: bool = False
    log_level: str = 'INFO'
    log_to_file: bool = False
    log_path: str = ''
    regex_offset: float = 0
    only_image: bool = False
    only_video: bool = False


@dataclass(slots=True)
class RunStats:
    total_files: int = 0
    processed_files: int = 0
    renamed_files: int = 0
    previewed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    directories_scanned: int = 0
    current_file: str = ''
    log_file_path: str = ''
    error_messages: list[str] = field(default_factory=list)

    @property
    def completion_ratio(self) -> float:
        if self.total_files <= 0:
            return 0.0
        return self.processed_files / self.total_files

    def snapshot(self) -> 'RunStats':
        return RunStats(
            total_files=self.total_files,
            processed_files=self.processed_files,
            renamed_files=self.renamed_files,
            previewed_files=self.previewed_files,
            skipped_files=self.skipped_files,
            failed_files=self.failed_files,
            directories_scanned=self.directories_scanned,
            current_file=self.current_file,
            log_file_path=self.log_file_path,
            error_messages=list(self.error_messages),
        )


@dataclass(slots=True, frozen=True)
class ValidationError:
    code: str
    value: str = ''


dir_path = ''
date_format = DEFAULT_DATE_FORMAT
recursion = False
preview = False
disable_regex = False
extensions = ''
force_rename = False
log_level = 'INFO'
log_to_file = False
log_path = ''
regex_offset = 0
only_image = False
only_video = False


def runtime_config() -> RunConfig:
    return RunConfig(
        dir_path=dir_path,
        date_format=date_format,
        recursion=recursion,
        preview=preview,
        disable_regex=disable_regex,
        extensions=extensions,
        force_rename=force_rename,
        log_level=log_level,
        log_to_file=log_to_file,
        log_path=log_path,
        regex_offset=regex_offset,
        only_image=only_image,
        only_video=only_video,
    )


def apply_runtime_config(config: RunConfig) -> None:
    global dir_path
    global date_format
    global recursion
    global preview
    global disable_regex
    global extensions
    global force_rename
    global log_level
    global log_to_file
    global log_path
    global regex_offset
    global only_image
    global only_video

    dir_path = config.dir_path
    date_format = config.date_format
    recursion = config.recursion
    preview = config.preview
    disable_regex = config.disable_regex
    extensions = config.extensions
    force_rename = config.force_rename
    log_level = config.log_level
    log_to_file = config.log_to_file
    log_path = config.log_path
    regex_offset = config.regex_offset
    only_image = config.only_image
    only_video = config.only_video


def parse_extensions(extension_string: str) -> list[str]:
    normalized_extensions = []
    for ext in extension_string.lower().split(','):
        cleaned_ext = ext.strip().lstrip('.')
        if cleaned_ext:
            normalized_extensions.append(f'.{cleaned_ext}')
    return normalized_extensions


def resolve_target_path(filepath: str, date_taken: str) -> str:
    file_dir = os.path.dirname(filepath)
    file_ext = os.path.splitext(filepath)[-1]
    original_filename = os.path.basename(filepath)
    preferred_name = f'{date_taken}{file_ext}'
    preferred_path = os.path.join(file_dir, preferred_name)
    if filepath == preferred_path or not os.path.exists(preferred_path):
        return preferred_path

    fallback_name = f'{date_taken}_{original_filename}'
    fallback_path = os.path.join(file_dir, fallback_name)
    if filepath == fallback_path or not os.path.exists(fallback_path):
        return fallback_path

    suffix = 1
    while True:
        fallback_name = f'{date_taken}_{suffix}_{original_filename}'
        fallback_path = os.path.join(file_dir, fallback_name)
        if filepath == fallback_path or not os.path.exists(fallback_path):
            return fallback_path
        suffix += 1


def get_fallback_datetime(filepath: str) -> datetime:
    file_stat = os.stat(filepath)
    timestamp_candidates = []
    system_name = platform.system().lower()

    birthtime = getattr(file_stat, 'st_birthtime', None)
    if birthtime and int(birthtime) > 0:
        timestamp_candidates.append(int(birthtime))
    elif system_name == 'windows' and int(file_stat.st_ctime) > 0:
        timestamp_candidates.append(int(file_stat.st_ctime))

    if int(file_stat.st_mtime) > 0:
        timestamp_candidates.append(int(file_stat.st_mtime))

    if system_name not in ('windows', 'linux') and int(file_stat.st_ctime) > 0:
        timestamp_candidates.append(int(file_stat.st_ctime))

    _, filename = os.path.split(filepath)
    dt_from_filename = datetime_from_filename(filename, 0)
    if dt_from_filename:
        timestamp_candidates.append(int(dt_from_filename.timestamp()))

    if not timestamp_candidates:
        raise ValueError(f'no fallback timestamp found for {filepath}')

    return datetime.fromtimestamp(min(timestamp_candidates))


def should_process_file(file_ext: str, config: RunConfig) -> bool:
    normalized_ext = file_ext.lower()
    if normalized_ext not in SUPPORTED_MEDIA:
        return False

    if config.only_image and normalized_ext not in Photos:
        return False

    if config.only_video and normalized_ext not in Videos:
        return False

    specified_ext_list = parse_extensions(config.extensions) if config.extensions else []
    if specified_ext_list and normalized_ext not in specified_ext_list:
        return False

    return True


def collect_media_files(file_path: str, config: RunConfig) -> tuple[list[str], int]:
    matched_files: list[str] = []
    directory_count = 0

    if config.recursion:
        for current_dir, _, filenames in os.walk(file_path):
            directory_count += 1
            for filename in filenames:
                abs_filename = os.path.join(current_dir, filename)
                file_ext = os.path.splitext(filename)[-1].lower()
                if should_process_file(file_ext, config):
                    matched_files.append(abs_filename)
    else:
        directory_count = 1
        for filename in os.listdir(file_path):
            abs_filename = os.path.join(file_path, filename)
            if not os.path.isfile(abs_filename):
                continue
            file_ext = os.path.splitext(filename)[-1].lower()
            if should_process_file(file_ext, config):
                matched_files.append(abs_filename)

    matched_files.sort()
    return matched_files, directory_count


def update_stats_for_outcome(stats: RunStats, outcome: str) -> None:
    if outcome == 'renamed':
        stats.renamed_files += 1
    elif outcome == 'previewed':
        stats.previewed_files += 1
    elif outcome == 'skipped':
        stats.skipped_files += 1
    elif outcome == 'failed':
        stats.failed_files += 1


def format_stats_summary(
    stats: RunStats,
    preview_mode: bool,
    max_errors: int = 5,
    language: str = 'zh-CN',
    include_log_file: bool = True,
) -> str:
    summary_lines = [
        translate(language, 'summary_dirs', value=stats.directories_scanned),
        translate(language, 'summary_total', value=stats.total_files),
        translate(language, 'summary_processed', value=stats.processed_files),
        translate(language, 'summary_skipped', value=stats.skipped_files),
        translate(language, 'summary_failed', value=stats.failed_files),
    ]

    if preview_mode:
        summary_lines.append(translate(language, 'summary_previewed', value=stats.previewed_files))
    else:
        summary_lines.append(translate(language, 'summary_renamed', value=stats.renamed_files))

    if include_log_file and stats.log_file_path:
        summary_lines.append(translate(language, 'summary_log_file', value=stats.log_file_path))

    if stats.error_messages:
        summary_lines.append(translate(language, 'summary_errors'))
        for message in stats.error_messages[:max_errors]:
            summary_lines.append(translate(language, 'summary_error_item', message=message))
        remaining_errors = len(stats.error_messages) - max_errors
        if remaining_errors > 0:
            summary_lines.append(translate(language, 'summary_more_errors', value=remaining_errors))

    return '\n'.join(summary_lines)


def resolve_dropped_directory(dropped_items) -> str | None:
    for item in dropped_items:
        candidate = os.fsdecode(item).strip()
        if not candidate:
            continue
        normalized = candidate.strip('{}').strip('"')
        if os.path.isdir(normalized):
            return normalized
        if os.path.isfile(normalized):
            return os.path.dirname(normalized)
    return None


def auto_rename(
    file_path: str,
    config: RunConfig | None = None,
    progress_callback: Callable[[RunStats], None] | None = None,
) -> RunStats:
    active_config = config or runtime_config()
    matched_files, directory_count = collect_media_files(file_path, active_config)
    stats = RunStats(total_files=len(matched_files), directories_scanned=directory_count)

    if progress_callback is not None:
        progress_callback(stats.snapshot())

    if not matched_files:
        logger.warning('no supported media files matched the current filters')
        return stats

    logger.info(f'found {stats.total_files} matching files in {stats.directories_scanned} directories')

    for abs_filename in matched_files:
        stats.current_file = abs_filename
        file_ext = os.path.splitext(abs_filename)[-1].lower()

        try:
            if file_ext in Photos:
                outcome = rename_photo(abs_filename, active_config)
            else:
                outcome = rename_video(abs_filename, active_config)
        except Exception as exc:
            outcome = 'failed'
            error_message = f'{os.path.basename(abs_filename)}: {exc}'
            stats.error_messages.append(error_message)
            logger.error(f'failed to rename {os.path.basename(abs_filename)}: {exc}')

        update_stats_for_outcome(stats, outcome)
        stats.processed_files += 1

        if progress_callback is not None:
            progress_callback(stats.snapshot())

    return stats


def rename_photo(filepath: str, config: RunConfig | None = None) -> str:
    active_config = config or runtime_config()

    filename_result = rename_with_datetime_from_filename(filepath, active_config)
    if filename_result:
        return filename_result

    with open(filepath, 'rb') as file_obj:
        try:
            tags = exifread.process_file(file_obj)
        except Exception as exc:
            logger.warning('get exif tags from %s error: %s' % (filepath, exc))
            tags = dict()

    if 'EXIF DateTimeOriginal' in tags and str(tags['EXIF DateTimeOriginal']):
        exif_date = str(tags['EXIF DateTimeOriginal'])
        return rename_with_datetime(filepath, datetime.strptime(exif_date, '%Y:%m:%d %H:%M:%S'), active_config)

    return rename_media(filepath, active_config)


def rename_video(filepath: str, config: RunConfig | None = None) -> str:
    active_config = config or runtime_config()

    filename_result = rename_with_datetime_from_filename(filepath, active_config)
    if filename_result:
        return filename_result

    return rename_media(filepath, active_config)


def rename_media(filepath: str, config: RunConfig | None = None) -> str:
    parser = None
    metadata = None
    try:
        parser = createParser(filepath)
        if parser is None:
            raise ValueError(f'failed to create parser for {filepath}')

        with parser:
            metadata = extractMetadata(parser)

        if metadata is None:
            raise ValueError(f'failed to extract metadata for {filepath}')

        exif_dict = metadata.exportDictionary().get('Metadata', {})
        exif_date = str(exif_dict.get('Creation date', '1904-01-01 00:00:00'))
        timestamp = datetime.strptime(exif_date, '%Y-%m-%d %H:%M:%S').timestamp()
    except Exception:
        timestamp = 0.0
        exif_date = ''
    finally:
        metadata = None
        parser = None
        if platform.system().lower() == 'windows':
            gc.collect()

    if timestamp > 0:
        utc_time = datetime.strptime(exif_date, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        local_time = utc_time.astimezone(datetime.now().astimezone().tzinfo)
    else:
        local_time = get_fallback_datetime(filepath)

    return rename_with_datetime(filepath, local_time, config)


def rename_with_datetime_from_filename(filepath: str, config: RunConfig | None = None) -> str | None:
    active_config = config or runtime_config()
    _, filename = os.path.split(filepath)

    if not active_config.force_rename:
        name, _ = os.path.splitext(filename)
        if is_given_format(name, active_config.date_format):
            logger.info(f'skip: {filename}')
            return 'skipped'

    if not active_config.disable_regex:
        dt = datetime_from_filename(filename, active_config.regex_offset)
        if dt:
            return rename_with_datetime(filepath, dt, active_config)
    return None


def is_windows_file_lock_error(exc: OSError) -> bool:
    return platform.system().lower() == 'windows' and getattr(exc, 'winerror', None) == 32


def rename_file_with_retries(source_path: str, target_path: str, attempts: int = 5, delay_seconds: float = 0.2) -> None:
    last_error = None

    for attempt in range(attempts):
        try:
            if platform.system().lower() == 'windows':
                gc.collect()
            os.rename(source_path, target_path)
            return
        except PermissionError as exc:
            if not is_windows_file_lock_error(exc) or attempt == attempts - 1:
                raise
            last_error = exc
            time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error


def rename_with_datetime(filepath: str, exif_date: datetime, config: RunConfig | None = None) -> str:
    active_config = config or runtime_config()
    date_taken = exif_date.strftime(active_config.date_format)
    new_path = resolve_target_path(filepath, date_taken)
    desired_path = os.path.join(os.path.dirname(filepath), date_taken + os.path.splitext(filepath)[-1])
    if filepath == new_path:
        logger.warning(f'skip: {os.path.basename(filepath)}')
        return 'skipped'
    if not active_config.force_rename and os.path.basename(filepath).startswith(date_taken):
        logger.warning(f'skip: {os.path.basename(filepath)}')
        return 'skipped'
    if active_config.preview:
        logger.info(f'{os.path.basename(filepath)} -> {os.path.basename(new_path)}')
        return 'previewed'

    if filepath != desired_path and active_config.force_rename and os.path.basename(filepath).startswith(date_taken):
        new_path = desired_path if not os.path.exists(desired_path) else resolve_target_path(filepath, date_taken)

    rename_file_with_retries(filepath, new_path)
    logger.info(f'{os.path.basename(filepath)} -> {os.path.basename(new_path)}')
    return 'renamed'


def datetime_from_filename(filename: str, offset_hours: float | None = None) -> datetime | None:
    pattern = r'([12]\d{3})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[_\-\s]?([01]\d|2[0-3])([0-5]\d)([0-5]\d)(\d{3})?'
    match = re.search(pattern, filename)

    if not match:
        return None

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))
    second = int(match.group(6))
    millisecond = int(match.group(7)) if match.group(7) else 0
    microsecond = millisecond * 1000

    try:
        dt = datetime(year, month, day, hour, minute, second, microsecond)
        effective_offset = regex_offset if offset_hours is None else offset_hours
        if effective_offset:
            dt = dt + timedelta(hours=effective_offset)
        return dt
    except ValueError:
        return None


def is_given_format(filename_without_ext: str, expected_format: str | None = None) -> bool:
    try:
        datetime.strptime(filename_without_ext, expected_format or date_format)
        return True
    except ValueError:
        return False


def test_func(config: RunConfig | None = None) -> tuple[bool, ValidationError | str]:
    active_config = config or runtime_config()

    if not active_config.dir_path:
        return False, ValidationError('missing_dir')

    if not os.path.exists(active_config.dir_path):
        return False, ValidationError('dir_not_exist', active_config.dir_path)

    if active_config.log_to_file and active_config.log_path and not os.path.exists(active_config.log_path):
        return False, ValidationError('missing_log_dir', active_config.log_path)

    try:
        datetime.now().strftime(active_config.date_format)
    except ValueError as exc:
        return False, ValidationError('invalid_format', f'{active_config.date_format}, {exc}')

    if active_config.only_image and active_config.only_video:
        return False, ValidationError('conflicting_media')

    if active_config.extensions:
        for ext_with_dot in parse_extensions(active_config.extensions):
            if ext_with_dot not in Photos + Videos:
                return False, ValidationError('invalid_extension', ext_with_dot.lstrip('.'))

    return True, 'tests passed'


def init_logger(level: str = 'INFO', target_log_path: str = '', extra_sink=None, log_to_file_enabled: bool = False) -> str:
    close_logger_handlers()

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    log_file = ''

    console_sink = sys.stdout or sys.stderr
    if console_sink is not None:
        console_handler = logging.StreamHandler(console_sink)
        console_handler.setFormatter(logging.Formatter(LOGGER_FORMAT))
        logger.addHandler(console_handler)

    if extra_sink is not None:
        callback_handler = CallbackLogHandler(extra_sink)
        logger.addHandler(callback_handler)

    if log_to_file_enabled:
        log_filename = f'photo-renamer_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log'
        log_file = os.path.join(target_log_path, log_filename) if target_log_path else log_filename
        log_file = os.path.abspath(log_file)
        file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(LOGGER_FORMAT))
        logger.addHandler(file_handler)

    return log_file


def close_logger_handlers() -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def open_directory_in_file_manager(directory_path: str) -> None:
    if platform.system().lower() == 'windows' and hasattr(os, 'startfile'):
        os.startfile(directory_path)
        return

    if platform.system().lower() == 'darwin':
        subprocess.Popen(['open', directory_path])
        return

    subprocess.Popen(['xdg-open', directory_path])


def print_version() -> None:
    print(f'version {Version}')


def execute(
    config: RunConfig,
    extra_sink=None,
    progress_callback: Callable[[RunStats], None] | None = None,
    language: str = 'zh-CN',
) -> tuple[bool, RunStats | str]:
    apply_runtime_config(config)
    log_file_path = init_logger(config.log_level, config.log_path, extra_sink=extra_sink, log_to_file_enabled=config.log_to_file)
    try:
        ok, err = test_func(config)
        if not ok:
            localized_error = localize_validation_message(err, language)
            logger.error(localized_error)
            return False, localized_error

        stats = auto_rename(config.dir_path, config, progress_callback=progress_callback)
        stats.log_file_path = log_file_path
        logger.info('task summary:\n' + format_stats_summary(stats, config.preview, language=language))
        return True, stats
    finally:
        close_logger_handlers()


class PhotoRenamerGUI:
    def __init__(self, root):
        self.root = root
        self.root.geometry('740x640')
        self.root.minsize(700, 620)

        self.event_queue: Queue[tuple[str, Any]] = Queue()
        self.worker: Thread | None = None

        defaults = runtime_config()
        self.dir_var = tk.StringVar(value=defaults.dir_path)
        self.format_var = tk.StringVar(value=defaults.date_format)
        self.extension_var = tk.StringVar(value=defaults.extensions)
        self.log_path_var = tk.StringVar(value=defaults.log_path)
        self.regex_offset_var = tk.StringVar(value=str(defaults.regex_offset))
        self.log_level_var = tk.StringVar(value=defaults.log_level)
        self.log_to_file_var = tk.BooleanVar(value=defaults.log_to_file)
        self.recursion_var = tk.BooleanVar(value=defaults.recursion)
        self.preview_var = tk.BooleanVar(value=True)
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.disable_regex_var = tk.BooleanVar(value=defaults.disable_regex)
        self.force_rename_var = tk.BooleanVar(value=defaults.force_rename)
        self.ui_mode_var = tk.StringVar(value='simple')
        self.ui_mode_display_var = tk.StringVar(value='')
        self.language_var = tk.StringVar(value='zh-CN')
        self.language_display_var = tk.StringVar(value='')
        self.media_mode_var = tk.StringVar(value='all')
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value='')
        self.current_file_var = tk.StringVar(value='')
        self.drop_hint_var = tk.StringVar(value='')
        self.directories_var = tk.StringVar(value='0')
        self.total_var = tk.StringVar(value='0')
        self.processed_var = tk.StringVar(value='0')
        self.renamed_var = tk.StringVar(value='0')
        self.skipped_var = tk.StringVar(value='0')
        self.failed_var = tk.StringVar(value='0')
        self.last_run_config = defaults
        self.done_metric_preview_mode = self.preview_var.get()
        self.last_stats: RunStats | None = None
        self.last_log_file_path = ''
        self.job_running = False

        self._build_layout()
        self._enable_drag_and_drop()
        self._apply_language(initial=True)
        self.root.after(120, self._flush_event_queue)

    def _text(self, key: str, **kwargs) -> str:
        return translate(self.language_var.get(), key, **kwargs)

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill='both', expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(3, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        header.columnconfigure(0, weight=1)

        self.subtitle_label = ttk.Label(header, text='', font=('Segoe UI', 10))
        self.subtitle_label.grid(row=0, column=0, sticky='w')

        self.mode_label = ttk.Label(header, text='')
        self.mode_label.grid(row=0, column=1, sticky='e', padx=(8, 6))
        self.mode_combo = ttk.Combobox(
            header,
            textvariable=self.ui_mode_display_var,
            values=tuple(),
            state='readonly',
            width=10,
        )
        self.mode_combo.grid(row=0, column=2, sticky='e')
        self.mode_combo.bind('<<ComboboxSelected>>', self._on_mode_changed)

        self.language_label = ttk.Label(header, text='')
        self.language_label.grid(row=0, column=3, sticky='e', padx=(8, 6))
        self.language_combo = ttk.Combobox(
            header,
            textvariable=self.language_display_var,
            values=tuple(),
            state='readonly',
            width=10,
        )
        self.language_combo.grid(row=0, column=4, sticky='e')
        self.language_combo.bind('<<ComboboxSelected>>', self._on_language_changed)

        self.about_link = tk.Label(
            header,
            text='',
            fg='#2563eb',
            cursor='hand2',
            font=('Segoe UI', 9, 'underline'),
        )
        self.about_link.grid(row=0, column=5, sticky='e', padx=(8, 0))
        self.about_link.bind('<Button-1>', lambda _event: self._show_about_dialog())
        self.about_link.bind('<Enter>', lambda _event: self.about_link.configure(fg='#1d4ed8'))
        self.about_link.bind('<Leave>', lambda _event: self.about_link.configure(fg='#2563eb'))

        self.form_frame = ttk.LabelFrame(container, text='', padding=10)
        form = self.form_frame
        form.grid(row=1, column=0, sticky='ew')
        for column in range(3):
            form.columnconfigure(column, weight=1)
        form.columnconfigure(3, weight=0)

        self.target_dir_label = ttk.Label(form, text='')
        self.target_dir_label.grid(row=0, column=0, sticky='w')
        self.dir_entry = ttk.Entry(form, textvariable=self.dir_var)
        self.dir_entry.grid(row=1, column=0, columnspan=3, sticky='ew', padx=(0, 8))
        self.dir_button = ttk.Button(form, text='', command=self._pick_dir, width=8)
        self.dir_button.grid(row=1, column=3, sticky='w')
        self.drop_hint_label = ttk.Label(form, textvariable=self.drop_hint_var, foreground='#4b5563')
        self.drop_hint_label.grid(row=2, column=0, columnspan=4, sticky='w', pady=(4, 0))

        option_frame = ttk.Frame(form)
        option_frame.grid(row=3, column=0, columnspan=4, sticky='ew', pady=(10, 0))
        for column in range(4):
            option_frame.columnconfigure(column, weight=1)

        self.recursion_check = ttk.Checkbutton(option_frame, text='', variable=self.recursion_var)
        self.recursion_check.grid(row=0, column=0, sticky='w')
        self.preview_check = ttk.Checkbutton(option_frame, text='', variable=self.preview_var)
        self.preview_check.grid(row=0, column=1, sticky='w')

        self.media_frame = ttk.LabelFrame(form, text='', padding=8)
        media_frame = self.media_frame
        media_frame.grid(row=4, column=0, columnspan=4, sticky='ew', pady=(10, 0))
        self.scope_all_radio = ttk.Radiobutton(media_frame, text='', value='all', variable=self.media_mode_var)
        self.scope_all_radio.pack(side='left', padx=(0, 16))
        self.scope_images_radio = ttk.Radiobutton(media_frame, text='', value='image', variable=self.media_mode_var)
        self.scope_images_radio.pack(side='left', padx=(0, 16))
        self.scope_videos_radio = ttk.Radiobutton(media_frame, text='', value='video', variable=self.media_mode_var)
        self.scope_videos_radio.pack(side='left')

        self.advanced_toggle_button = ttk.Button(form, text='', command=self._toggle_advanced_settings)
        self.advanced_toggle_button.grid(row=5, column=0, sticky='w', pady=(10, 0))

        self.advanced_frame = ttk.LabelFrame(form, text='', padding=8)
        advanced = self.advanced_frame
        advanced.grid(row=6, column=0, columnspan=4, sticky='ew', pady=(8, 0))
        for column in range(3):
            advanced.columnconfigure(column, weight=1)
        advanced.columnconfigure(3, weight=0)

        self.filename_format_label = ttk.Label(advanced, text='')
        self.filename_format_label.grid(row=0, column=0, sticky='w')
        ttk.Entry(advanced, textvariable=self.format_var).grid(row=1, column=0, sticky='ew', padx=(0, 8))

        self.extension_filter_label = ttk.Label(advanced, text='')
        self.extension_filter_label.grid(row=0, column=1, sticky='w')
        ttk.Entry(advanced, textvariable=self.extension_var).grid(row=1, column=1, sticky='ew', padx=(0, 8))

        self.time_offset_label = ttk.Label(advanced, text='')
        self.time_offset_label.grid(row=0, column=2, sticky='w')
        ttk.Entry(advanced, textvariable=self.regex_offset_var).grid(row=1, column=2, sticky='ew', padx=(0, 8))

        self.log_level_label = ttk.Label(advanced, text='')
        self.log_level_label.grid(row=0, column=3, sticky='w')
        ttk.Combobox(advanced, textvariable=self.log_level_var, values=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'), state='readonly').grid(row=1, column=3, sticky='ew')

        self.log_to_file_check = ttk.Checkbutton(
            advanced,
            text='',
            variable=self.log_to_file_var,
            command=self._update_log_file_controls,
        )
        self.log_to_file_check.grid(row=2, column=0, sticky='w', pady=(8, 0))

        self.disable_regex_check = ttk.Checkbutton(advanced, text='', variable=self.disable_regex_var)
        self.disable_regex_check.grid(row=2, column=1, sticky='w', pady=(8, 0))

        self.force_rename_check = ttk.Checkbutton(advanced, text='', variable=self.force_rename_var)
        self.force_rename_check.grid(row=2, column=2, columnspan=2, sticky='w', pady=(8, 0))

        self.log_dir_label = ttk.Label(advanced, text='')
        self.log_dir_label.grid(row=3, column=0, sticky='w', pady=(8, 0))
        self.log_dir_entry = ttk.Entry(advanced, textvariable=self.log_path_var)
        self.log_dir_entry.grid(row=4, column=0, columnspan=3, sticky='ew', padx=(0, 8))
        self.log_dir_button = ttk.Button(advanced, text='', command=self._pick_log_dir, width=8)
        self.log_dir_button.grid(row=4, column=3, sticky='w')

        self._apply_advanced_visibility()

        self.progress_frame = ttk.LabelFrame(container, text='', padding=10)
        progress_frame = self.progress_frame
        progress_frame.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        progress_frame.columnconfigure(0, weight=1)

        ttk.Label(progress_frame, textvariable=self.progress_text_var, font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w')
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100).grid(row=1, column=0, sticky='ew', pady=(6, 4))
        ttk.Label(progress_frame, textvariable=self.current_file_var, foreground='#4b5563').grid(row=2, column=0, sticky='w')

        metric_frame = ttk.Frame(progress_frame)
        metric_frame.grid(row=3, column=0, sticky='ew', pady=(8, 6))
        for column in range(6):
            metric_frame.columnconfigure(column, weight=1)

        self.metric_labels = []
        self.metric_labels.append(self._create_metric(metric_frame, 0, self.directories_var))
        self.metric_labels.append(self._create_metric(metric_frame, 1, self.total_var))
        self.metric_labels.append(self._create_metric(metric_frame, 2, self.processed_var))
        self.metric_labels.append(self._create_metric(metric_frame, 3, self.renamed_var))
        self.metric_labels.append(self._create_metric(metric_frame, 4, self.skipped_var))
        self.metric_labels.append(self._create_metric(metric_frame, 5, self.failed_var))

        self.output_frame = ttk.LabelFrame(container, text='', padding=10)
        output = self.output_frame
        output.grid(row=3, column=0, sticky='nsew', pady=(10, 0))
        output.columnconfigure(0, weight=1)
        output.rowconfigure(0, weight=1)

        self.log_text = tk.Text(output, wrap='word', font=('Consolas', 10), state='disabled', bg='#111827', fg='#f9fafb')
        self.log_text.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(output, orient='vertical', command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.log_text.configure(yscrollcommand=scrollbar.set)

        action_bar = ttk.Frame(container)
        action_bar.grid(row=4, column=0, sticky='ew', pady=(10, 0))
        action_bar.columnconfigure(0, weight=1)

        self.footer_label = ttk.Label(action_bar, text='')
        self.footer_label.grid(row=0, column=0, sticky='w')
        self.open_log_dir_button = ttk.Button(action_bar, text='', command=self._open_log_dir)
        self.open_log_dir_button.grid(row=0, column=1, sticky='e', padx=(8, 0))
        self.run_button = ttk.Button(action_bar, text='', command=self._start_job)
        self.run_button.grid(row=0, column=2, sticky='e', padx=(8, 0))

    def _create_metric(self, parent, column: int, variable):
        metric = ttk.Frame(parent, padding=(0, 0, 12, 0))
        metric.grid(row=0, column=column, sticky='ew')
        title_label = ttk.Label(metric, text='', foreground='#6b7280')
        title_label.pack(anchor='w')
        ttk.Label(metric, textvariable=variable, font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        return title_label

    def _refresh_run_button(self) -> None:
        button_key = 'run_button_running' if self.job_running else 'run_button'
        self.run_button.configure(text=self._text(button_key), state='disabled' if self.job_running else 'normal')

    def _apply_language(self, initial: bool = False) -> None:
        app_name = app_display_name(self.language_var.get())
        self.root.title(f'{app_name} v{Version}')
        self.subtitle_label.configure(text=self._text('app_tagline'))
        self.mode_label.configure(text=self._text('mode_label'))
        self.mode_combo.configure(values=[mode_display_name(self.language_var.get(), mode) for mode in UI_MODE_OPTIONS])
        self.ui_mode_display_var.set(mode_display_name(self.language_var.get(), self.ui_mode_var.get()))
        self.language_label.configure(text=self._text('language_label'))
        self.language_combo.configure(values=[f'{code} | {name}' for code, name in LANGUAGE_OPTIONS.items()])
        current_code = self.language_var.get()
        self.language_display_var.set(f'{current_code} | {LANGUAGE_OPTIONS.get(current_code, current_code)}')
        self.about_link.configure(text=self._text('about_button'))

        self.form_frame.configure(text=self._text('settings_frame'))
        self.target_dir_label.configure(text=self._text('target_dir'))
        self.dir_button.configure(text=self._text('browse'))
        self.advanced_frame.configure(text=self._text('advanced_frame'))
        self.filename_format_label.configure(text=self._text('filename_format'))
        self.extension_filter_label.configure(text=self._text('extension_filter'))
        self.time_offset_label.configure(text=self._text('time_offset'))
        self.log_level_label.configure(text=self._text('log_level'))
        self.log_to_file_check.configure(text=self._text('log_to_file'))
        self.log_dir_label.configure(text=self._text('log_dir'))
        self.log_dir_button.configure(text=self._text('browse'))
        self.recursion_check.configure(text=self._text('include_subdirs'))
        self.preview_check.configure(text=self._text('preview_only'))
        self.disable_regex_check.configure(text=self._text('disable_filename_time'))
        self.force_rename_check.configure(text=self._text('force_rename'))
        self.advanced_toggle_button.configure(
            text=self._text('hide_more_settings' if self.show_advanced_var.get() else 'show_more_settings')
        )
        self._apply_mode_layout()

        self.media_frame.configure(text=self._text('scope_frame'))
        self.scope_all_radio.configure(text=self._text('scope_all'))
        self.scope_images_radio.configure(text=self._text('scope_images'))
        self.scope_videos_radio.configure(text=self._text('scope_videos'))

        self.progress_frame.configure(text=self._text('progress_frame'))
        metric_keys = ['metric_dirs', 'metric_total', 'metric_processed', '', 'metric_skipped', 'metric_failed']
        for label, key in zip(self.metric_labels, metric_keys, strict=False):
            if key:
                label.configure(text=self._text(key))
        self._update_done_metric_label()

        self.output_frame.configure(text=self._text('log_frame'))
        self.footer_label.configure(text=self._text('footer_tip'))
        self.open_log_dir_button.configure(text=self._text('open_log_dir'))
        self._refresh_run_button()
        self._refresh_open_log_dir_button()

        if windnd is None:
            self.drop_hint_var.set(self._text('drop_hint_no_dnd'))
        else:
            self.drop_hint_var.set(self._text('drop_hint_dnd'))

        if self.last_stats is not None:
            self._update_progress(self.last_stats)
        else:
            self._reset_progress_view()

        if not initial:
            self._append_log(self._text('language_switched'))

        self._update_log_file_controls()

    def _on_language_changed(self, _event=None) -> None:
        selected_value = self.language_combo.get().split(' | ')[0].strip()
        if selected_value in LANGUAGE_OPTIONS:
            self.language_var.set(selected_value)
        self._apply_language()

    def _create_modal_dialog(self, title: str) -> Any:
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title(title)
        apply_window_icon(dialog)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.protocol('WM_DELETE_WINDOW', dialog.destroy)
        return dialog

    def _dialog_wraplength(self, *texts: str, min_width: int = 280, max_width: int = 560) -> int:
        if tkfont is None:
            return max_width

        default_font = tkfont.nametofont('TkDefaultFont')
        measured_width = min_width
        for text in texts:
            for line in text.splitlines() or ['']:
                measured_width = max(measured_width, default_font.measure(line) + 24)
        return max(min_width, min(measured_width, max_width))

    def _present_modal_dialog(self, dialog, focus_widget=None, wait: bool = False) -> None:
        center_child_window(dialog, self.root)
        dialog.deiconify()
        dialog.lift(self.root)
        if focus_widget is not None:
            focus_widget.focus_set()
        if wait:
            self.root.wait_window(dialog)

    def _show_message_dialog(self, title: str, message: str, min_width: int = 200) -> None:
        dialog = self._create_modal_dialog(title)
        dialog.minsize(min_width, 1)
        wraplength = self._dialog_wraplength(message, min_width=min_width)

        content = ttk.Frame(dialog, padding=16)
        content.pack(fill='both', expand=True)

        ttk.Label(content, text=message, wraplength=wraplength, justify='left').pack(anchor='w', fill='x')

        actions = ttk.Frame(content)
        actions.pack(fill='x', pady=(12, 0))

        ok_button = ttk.Button(actions, text='OK', command=dialog.destroy)
        ok_button.pack(side='right')

        self._present_modal_dialog(dialog, focus_widget=ok_button, wait=True)

    def _show_about_dialog(self) -> None:
        dialog = self._create_modal_dialog(self._text('about_title'))
        open_source_label = translate(self.language_var.get(), 'about_open_source', url='')
        wraplength = self._dialog_wraplength(
            app_display_name(self.language_var.get()),
            translate(self.language_var.get(), 'about_version', version=Version),
            open_source_label,
            OPEN_SOURCE_URL,
        )

        content = ttk.Frame(dialog, padding=16)
        content.pack(fill='both', expand=True)

        ttk.Label(content, text=app_display_name(self.language_var.get()), font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(content, text=translate(self.language_var.get(), 'about_version', version=Version)).pack(anchor='w', pady=(8, 0))
        ttk.Label(content, text=open_source_label, wraplength=wraplength, justify='left').pack(anchor='w', pady=(4, 0))

        repo_link = tk.Label(
            content,
            text=OPEN_SOURCE_URL,
            fg='#2563eb',
            cursor='hand2',
            font=('Segoe UI', 9, 'underline'),
            justify='left',
            wraplength=wraplength,
        )
        repo_link.pack(anchor='w')
        repo_link.bind('<Button-1>', lambda _event: webbrowser.open(OPEN_SOURCE_URL))
        repo_link.bind('<Enter>', lambda _event: repo_link.configure(fg='#1d4ed8'))
        repo_link.bind('<Leave>', lambda _event: repo_link.configure(fg='#2563eb'))

        actions = ttk.Frame(content)
        actions.pack(fill='x', pady=(12, 0))

        ok_button = ttk.Button(actions, text='OK', command=dialog.destroy)
        ok_button.pack(side='right')

        self._present_modal_dialog(dialog, focus_widget=ok_button)

    def _on_mode_changed(self, _event=None) -> None:
        selected_value = self.mode_combo.get().strip()
        for mode in UI_MODE_OPTIONS:
            if selected_value == mode_display_name(self.language_var.get(), mode):
                self.ui_mode_var.set(mode)
                break
        self._apply_mode_layout()

    def _update_done_metric_label(self) -> None:
        done_key = 'metric_done_preview' if self.done_metric_preview_mode else 'metric_done_renamed'
        self.metric_labels[3].configure(text=self._text(done_key))

    def _apply_advanced_visibility(self) -> None:
        if self.show_advanced_var.get():
            self.advanced_frame.grid()
        else:
            self.advanced_frame.grid_remove()

    def _apply_mode_layout(self) -> None:
        if self.ui_mode_var.get() == 'pro':
            self.advanced_toggle_button.grid_remove()
            self.advanced_frame.grid()
            return

        self.advanced_toggle_button.grid()
        self._apply_advanced_visibility()

    def _toggle_advanced_settings(self) -> None:
        self.show_advanced_var.set(not self.show_advanced_var.get())
        self._apply_mode_layout()
        self.advanced_toggle_button.configure(
            text=self._text('hide_more_settings' if self.show_advanced_var.get() else 'show_more_settings')
        )

    def _enable_drag_and_drop(self) -> None:
        if windnd is None:
            self.drop_hint_var.set(self._text('drop_hint_no_dnd'))
            return

        self.drop_hint_var.set(self._text('drop_hint_dnd'))
        for widget in (self.root, self.dir_entry):
            windnd.hook_dropfiles(widget, func=self._on_drop_files)

    def _on_drop_files(self, dropped_items) -> None:
        resolved_dir = resolve_dropped_directory(dropped_items)
        if resolved_dir:
            self.dir_var.set(resolved_dir)
            self._queue_event('log', self._text('drag_selected_dir', path=resolved_dir))

    def _pick_dir(self) -> None:
        selected_dir = filedialog.askdirectory(title=self._text('select_target_dir'))
        if selected_dir:
            self.dir_var.set(selected_dir)

    def _pick_log_dir(self) -> None:
        selected_dir = filedialog.askdirectory(title=self._text('select_log_dir'))
        if selected_dir:
            self.log_path_var.set(selected_dir)

    def _update_log_file_controls(self) -> None:
        enabled = self.log_to_file_var.get()
        state = 'normal' if enabled else 'disabled'
        self.log_dir_label.configure(foreground='' if enabled else '#9ca3af')
        self.log_dir_entry.configure(state=state)
        self.log_dir_button.configure(state=state)

        if hasattr(self, 'open_log_dir_button'):
            if enabled:
                self.open_log_dir_button.grid()
            else:
                self.open_log_dir_button.grid_remove()

        self._refresh_open_log_dir_button()

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state='normal')
        self.log_text.insert('end', message + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _refresh_open_log_dir_button(self) -> None:
        if not hasattr(self, 'open_log_dir_button'):
            return

        last_log_file_path = getattr(self, 'last_log_file_path', '')
        job_running = getattr(self, 'job_running', False)
        has_log_dir = bool(last_log_file_path and os.path.isdir(os.path.dirname(last_log_file_path)))
        state = 'normal' if has_log_dir and not job_running else 'disabled'
        self.open_log_dir_button.configure(state=state)

    def _open_log_dir(self) -> None:
        log_file_path = self.last_log_file_path.strip()
        log_dir = os.path.dirname(log_file_path) if log_file_path else ''
        if not log_dir or not os.path.isdir(log_dir):
            message = self._text('open_log_dir_missing')
            self._append_log(message)
            self._show_message_dialog(self._text('dialog_failed_title'), message)
            return

        try:
            open_directory_in_file_manager(log_dir)
        except Exception as exc:
            message = self._text('open_log_dir_failed', value=str(exc))
            self._append_log(message)
            self._show_message_dialog(self._text('dialog_failed_title'), message)

    def _clear_log_output(self) -> None:
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    def _show_input_error(self, message: str) -> None:
        self._append_log(f'{self._text("dialog_input_title")}: {message}')
        self._show_message_dialog(self._text('dialog_input_title'), message)

    def _queue_event(self, kind: str, payload: Any) -> None:
        self.event_queue.put((kind, payload))

    def _emit_log(self, message) -> None:
        rendered = str(message).rstrip()
        if rendered:
            self._queue_event('log', rendered)

    def _emit_progress(self, stats: RunStats) -> None:
        self._queue_event('progress', stats)

    def _flush_event_queue(self) -> None:
        try:
            while True:
                kind, payload = self.event_queue.get_nowait()
                if kind == 'log':
                    self._append_log(payload)
                elif kind == 'progress':
                    self._update_progress(payload)
        except Empty:
            pass
        self.root.after(120, self._flush_event_queue)

    def _build_config(self) -> RunConfig:
        media_mode = self.media_mode_var.get()
        regex_offset_value = self.regex_offset_var.get().strip() or '0'
        return RunConfig(
            dir_path=self.dir_var.get().strip(),
            date_format=self.format_var.get().strip() or DEFAULT_DATE_FORMAT,
            recursion=self.recursion_var.get(),
            preview=self.preview_var.get(),
            disable_regex=self.disable_regex_var.get(),
            extensions=self.extension_var.get().strip(),
            force_rename=self.force_rename_var.get(),
            log_level=self.log_level_var.get(),
            log_to_file=self.log_to_file_var.get(),
            log_path=self.log_path_var.get().strip(),
            regex_offset=float(regex_offset_value),
            only_image=media_mode == 'image',
            only_video=media_mode == 'video',
        )

    def _reset_progress_view(self, show_scanning: bool = False) -> None:
        self.progress_var.set(0)
        self.progress_text_var.set(self._text('progress_scanning') if show_scanning else self._text('progress_idle'))
        self.current_file_var.set(self._text('current_file', name='-'))
        self.directories_var.set('0')
        self.total_var.set('0')
        self.processed_var.set('0')
        self.renamed_var.set('0')
        self.skipped_var.set('0')
        self.failed_var.set('0')
        self._refresh_open_log_dir_button()

    def _update_progress(self, stats: RunStats) -> None:
        self.last_stats = stats
        if stats.log_file_path:
            self.last_log_file_path = stats.log_file_path
        self.progress_var.set(round(stats.completion_ratio * 100, 1))
        self.directories_var.set(str(stats.directories_scanned))
        self.total_var.set(str(stats.total_files))
        self.processed_var.set(str(stats.processed_files))
        completed_value = stats.previewed_files if self.last_run_config.preview else stats.renamed_files
        self.renamed_var.set(str(completed_value))
        self.skipped_var.set(str(stats.skipped_files))
        self.failed_var.set(str(stats.failed_files))

        if stats.total_files == 0:
            self.progress_text_var.set(self._text('progress_none'))
        elif stats.processed_files >= stats.total_files:
            self.progress_text_var.set(self._text('progress_done', processed=stats.processed_files, total=stats.total_files))
        else:
            self.progress_text_var.set(self._text('progress_running', processed=stats.processed_files, total=stats.total_files))

        current_label = os.path.basename(stats.current_file) if stats.current_file else '-'
        self.current_file_var.set(self._text('current_file', name=current_label))
        self._refresh_open_log_dir_button()

    def _start_job(self) -> None:
        if self.worker and self.worker.is_alive():
            self._show_message_dialog(self._text('dialog_busy_title'), self._text('dialog_busy_message'))
            return

        self._clear_log_output()

        try:
            config = self._build_config()
        except ValueError:
            self._show_input_error(self._text('dialog_offset_error'))
            return

        ok, err = test_func(config)
        if not ok:
            self._show_input_error(localize_validation_message(err, self.language_var.get()))
            return

        self.last_run_config = config
        self.done_metric_preview_mode = config.preview
        self.last_log_file_path = ''
        self._update_done_metric_label()
        self._reset_progress_view(show_scanning=True)
        self.job_running = True
        self._refresh_run_button()
        self._refresh_open_log_dir_button()
        self._append_log(self._text('log_start'))

        self.worker = Thread(target=self._run_job, args=(config,), daemon=True)
        self.worker.start()

    def _run_job(self, config: RunConfig) -> None:
        try:
            success, result = execute(config, extra_sink=self._emit_log, progress_callback=self._emit_progress, language=self.language_var.get())
            if success and isinstance(result, RunStats):
                self._queue_event('progress', result)
                summary_message = format_stats_summary(result, config.preview, language=self.language_var.get(), include_log_file=False)
                self.root.after(0, lambda: self._show_message_dialog(self._text('dialog_done_title'), summary_message))
            else:
                self.root.after(0, lambda: self._show_message_dialog(self._text('dialog_failed_title'), str(result)))
        except Exception as exc:  # pragma: no cover
            self._queue_event('log', f'未处理异常: {exc}')
            self.root.after(0, lambda: self._show_message_dialog(self._text('dialog_failed_title'), str(exc)))
        finally:
            self.root.after(0, self._finish_job)

    def _finish_job(self) -> None:
        self.job_running = False
        self._refresh_run_button()
        self._refresh_open_log_dir_button()


def launch_gui() -> int:
    if tk is None or ttk is None or filedialog is None:
        print('tkinter is not available in this Python environment', file=sys.stderr)
        return 1

    root = tk.Tk()
    root.withdraw()
    apply_window_icon(root)
    PhotoRenamerGUI(root)
    root.after(0, lambda: present_root_window(root))
    root.mainloop()
    return 0


def main() -> int:
    freeze_support()
    return launch_gui()


if __name__ == '__main__':
    raise SystemExit(main())
