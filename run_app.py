"""
Root-level entry point for PyInstaller packaging.
This ensures PyInstaller can see all required imports.
"""

import sys
from pathlib import Path

# CRITICAL: Import modules that PyInstaller needs to see at parse time
# This ensures they are included in the bundle
import PyQt6
import PyQt6.QtCore
import PyQt6.QtGui
import PyQt6.QtWidgets
import cv2
import numpy
import librosa
import sounddevice
import pyautogui
import pyttsx3
import yaml
import pydantic
from dotenv import load_dotenv
import loguru

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

# Import and run main from the src package (not the stale root main.py)
try:
    from src.main import main
    if __name__ == "__main__":
        sys.exit(main())
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
