"""
Entry point for PyInstaller packaging.
Ensures proper module imports when bundled as executable.
"""

import sys
from pathlib import Path

# Add current package to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import and run main
from main import main

if __name__ == "__main__":
    sys.exit(main())
