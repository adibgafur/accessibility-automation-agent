# -*- coding: utf-8 -*-
"""
Hook for PyQt6 to ensure all submodules are included in PyInstaller builds.
"""
from PyInstaller.utils.hooks import collect_submodules, get_module_file_attribute

binaries = []
datas = []
hiddenimports = collect_submodules('PyQt6') + [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
]
