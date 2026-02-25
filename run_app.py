"""
Root-level entry point for PyInstaller packaging.
This script properly initializes the Python path and runs the main application.
"""

import sys
from pathlib import Path

# Add src directory to Python path so imports work correctly in packaged executable
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Now import and run the main module
from main import main

if __name__ == "__main__":
    sys.exit(main())
