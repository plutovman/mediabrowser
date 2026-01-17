# -*- mode: python ; coding: utf-8 -*-
# PyInstaller injects these names at runtime
# type: ignore

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get the current directory
spec_root = os.path.abspath(SPECPATH)
path_other = '/tmp/app'
path_dist = os.path.join(path_other, 'dist')
path_build = os.path.join(path_other, 'build')
if not os.path.exists(path_dist):
    os.makedirs(path_dist)
if not os.path.exists(path_build):
    os.makedirs(path_build)

# Override default DISTPATH and BUILDPATH
if not os.environ.get('_MEIPASS'):  # Only set if not running from frozen app
    import PyInstaller.config
    PyInstaller.config.CONF['distpath'] = os.path.join(path_other, 'dist')
    PyInstaller.config.CONF['workpath'] = os.path.join(path_other, 'build')

# Collect CustomTkinter data files
customtkinter_datas = collect_data_files('customtkinter')

# Additional data files to include
added_files = [
    # Logo image
    (os.path.join(spec_root, 'resources', 'foxlito.png'), 'resources'),
    # Icon files
    (os.path.join(spec_root, 'resources', 'foxlito_sqr.ico'), 'resources'),
    (os.path.join(spec_root, 'resources', 'foxlito_sqr.png'), 'resources'),
    # MediaBrowser script (required by launchpad)
    (os.path.join(spec_root, 'mediabrowser.py'), '.'),
    # Templates directory (required by Flask)
    (os.path.join(spec_root, 'templates', '*.html'), 'templates'),
]

# Collect hidden imports
hidden_imports = [
    'customtkinter',
    'PIL',
    'PIL._tkinter_finder',
    'flask',
    'sqlite3',
    'vpr_jobtools',
    'db_jobtools',
]

block_cipher = None

a = Analysis(
    [os.path.join(spec_root, 'launchpad.py')],
    pathex=[spec_root],
    binaries=[],
    datas=added_files + customtkinter_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='app_launchpad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # --windowed: No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(spec_root, 'resources', 'foxlito_sqr.ico'),  # Application icon
)