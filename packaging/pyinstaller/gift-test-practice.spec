# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Gift Test Practice
Builds standalone executables for Windows, macOS, and Linux
"""

import sys
from pathlib import Path

block_cipher = None

# Determine icon and data files based on platform
icon_file = None
if sys.platform == 'win32':
    icon_file = 'assets/icon.ico'
elif sys.platform == 'darwin':
    icon_file = 'assets/icon.icns'

a = Analysis(
    ['gift_test_practice.py'],
    pathex=[],
    binaries=[],
    datas=[('data', 'data')],
    hiddenimports=['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.QtWebEngineWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
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
    name='GiftTestPractice' if sys.platform == 'win32' else 'gift-test-practice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='GiftTestPractice.app',
        icon=icon_file,
        bundle_identifier='com.gifttest.practice',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
        },
    )
