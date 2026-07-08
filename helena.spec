# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'reportlab.graphics.barcode',
    'xlrd',
]
hiddenimports += collect_submodules('app.modules')

if sys.platform == 'win32':
    hiddenimports += ['webview.platforms.edgechromium', 'webview.platforms.winforms', 'clr']
elif sys.platform == 'darwin':
    hiddenimports += ['webview.platforms.cocoa']
else:
    hiddenimports += ['webview.platforms.gtk', 'webview.platforms.qt']

a = Analysis(
    ['app/main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=[
        ('app/frontend/dist', 'frontend/dist'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NeoCaixa',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='NeoCaixa.app',
        icon=None,
        bundle_identifier='com.neocaixa.app',
        info_plist={
            'CFBundleName': 'Neo Caixa',
            'CFBundleDisplayName': 'Neo Caixa',
            'CFBundleShortVersionString': '0.1.0',
            'NSHighResolutionCapable': True,
        },
    )
