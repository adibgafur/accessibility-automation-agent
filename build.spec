# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Accessibility Automation Agent.

Build command:
    pyinstaller build.spec

This creates a Windows executable with all dependencies bundled.
Output: dist/AccessibilityAgent.exe
"""

import sys
import os
from pathlib import Path

block_cipher = None

# Get project root (current working directory is the project root)
project_root = os.getcwd()

a = Analysis(
    ['src/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('docs', 'docs'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'loguru',
        'whisper',
        'mediapipe',
        'cv2',
        'selenium',
        'selenium.webdriver',
        'numpy',
        'librosa',
        'sounddevice',
        'pyautogui',
        'pyttsx3',
    ],
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
    name='AccessibilityAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    icon='assets/icon.ico',  # Application icon (optional)
    entitlements=None,
)

# Optionally create a directory for distribution
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AccessibilityAgent',
)
