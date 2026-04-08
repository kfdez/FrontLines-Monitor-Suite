# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# Get the directory where this spec file is located
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

# Data files to include
datas = [
    # Icon files
    ('app.ico', '.'),
    ('Bag_Safari_Ball_SV_Sprite.png', '.'),
]

# Add data directories if they exist
data_dirs = ['hv_monitor_data', 'shopify_monitor_data', 'skutto_data']
for d in data_dirs:
    if os.path.exists(d):
        datas.append((d, d))

a = Analysis(
    ['main.py'],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'discord',
        'googleapiclient',
        'google_auth_oauthlib',
        'requests',
        'PIL',
        'pystray',
        'PIL.Image',
        'PIL.ImageTk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'test',
        'tests',
        'pytest',
        '_pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FrontLinesMonitorSuite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FrontLinesMonitorSuite',
)
