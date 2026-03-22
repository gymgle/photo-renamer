# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import platform


project_root = Path(SPECPATH)
assets_dir = project_root / 'assets'
system_name = platform.system().lower()

data_files = []
for icon_file in ('icon.ico', 'icon.icns'):
    icon_path = assets_dir / icon_file
    if icon_path.exists():
        data_files.append((str(icon_path), 'assets'))

iconset_dir = assets_dir / 'icon.iconset'
if iconset_dir.exists():
    for iconset_file in sorted(iconset_dir.glob('*.png')):
        data_files.append((str(iconset_file), 'assets/icon.iconset'))

exe_icon = None
bundle_icon = None

windows_icon = assets_dir / 'icon.ico'
macos_icon = assets_dir / 'icon.icns'

if system_name == 'darwin':
    if macos_icon.exists():
        exe_icon = str(macos_icon)
        bundle_icon = str(macos_icon)
elif windows_icon.exists():
    exe_icon = str(windows_icon)


a = Analysis(
    ['photo_renamer.py'],
    pathex=[],
    binaries=[],
    datas=data_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='photo-renamer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)

if system_name == 'darwin':
    app = BUNDLE(
        exe,
        name='photo-renamer.app',
        icon=bundle_icon,
        bundle_identifier='com.gymgle.photo-renamer',
    )
