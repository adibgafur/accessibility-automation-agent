# Installation Guide - Accessibility Automation Agent

## Quick Start (5 minutes)

### Prerequisites
- Windows 7 or later
- Python 3.10 or 3.11
- 4GB RAM minimum
- USB webcam and microphone

### Installation Steps

1. **Install Python**
   - Download from [python.org](https://www.python.org/downloads/)
   - Check "Add Python to PATH"

2. **Clone the Repository**
   ```bash
   git clone https://github.com/adibgafur/accessibility-automation-agent.git
   cd accessibility-automation-agent
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**
   ```bash
   python -m src.main --language en
   ```

---

## Detailed Installation

### Step 1: Install Python

#### Download
1. Visit https://www.python.org/downloads/
2. Click "Download Python 3.11" (or 3.10)
3. Select Windows 64-bit installer

#### Install
1. Run the installer
2. **IMPORTANT**: Check ☑️ "Add Python to PATH"
3. Click "Install Now"
4. Wait for installation to complete

#### Verify
Open Command Prompt and type:
```bash
python --version
pip --version
```

Both should display version numbers.

---

### Step 2: Get the Source Code

#### Option A: Using Git (Recommended)

Install Git if you don't have it: https://git-scm.com/download/win

```bash
git clone https://github.com/adibgafur/accessibility-automation-agent.git
cd accessibility-automation-agent
```

#### Option B: Download ZIP

1. Visit: https://github.com/adibgafur/accessibility-automation-agent
2. Click "Code" button (green button)
3. Click "Download ZIP"
4. Extract ZIP file to your desired location
5. Open Command Prompt in that folder

---

### Step 3: Install Dependencies

Navigate to the project directory in Command Prompt:

```bash
pip install -r requirements.txt
```

This will install:
- **PyQt6**: Graphical User Interface
- **Whisper**: Speech Recognition
- **MediaPipe**: Eye Tracking
- **Selenium**: Browser Automation
- **OpenCV**: Computer Vision
- **PyAutoGUI**: Mouse/Keyboard Control
- **Loguru**: Logging
- **Torch/TensorFlow**: Machine Learning
- Plus 15+ other dependencies

**Note**: First installation takes 10-15 minutes. Subsequent installs are faster.

---

### Step 4: Download ML Models (First Run)

The first time you run the app, it will download:
- Whisper speech recognition model (1.4GB)
- MediaPipe eye tracking models (~50MB)
- GUIrilla GUI detection model (~2GB)

**Total**: ~3.5GB

**Requirements**:
- Fast internet connection (broadband recommended)
- Sufficient disk space (4GB free)
- Allow 30-60 minutes for download

These are cached locally after download.

---

### Step 5: Launch the Application

#### GUI Mode (Recommended)
```bash
python -m src.main --language en
```

For Bengali interface:
```bash
python -m src.main --language bn
```

#### Headless Mode (No GUI)
```bash
python -m src.main --headless --language en
```

#### Debug Mode (Troubleshooting)
```bash
python -m src.main --log-level DEBUG
```

---

## Installation Troubleshooting

### Issue: "Python is not recognized"

**Cause**: Python not added to PATH

**Solution**:
1. Uninstall Python (Control Panel → Programs)
2. Reinstall and **CHECK** "Add Python to PATH"
3. Restart Command Prompt

**Alternative**: Use full path
```bash
C:\Users\YourName\AppData\Local\Programs\Python\Python311\python.exe -m src.main
```

### Issue: "ModuleNotFoundError"

**Cause**: Dependencies not installed

**Solution**:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If specific module fails:
```bash
pip install PyQt6 --force-reinstall
```

### Issue: "CUDA out of memory" or GPU errors

**Cause**: Using GPU when not enough VRAM

**Solution**:
```bash
# Force CPU mode (default)
python -m src.main
```

Or edit `config/default_settings.yaml`:
```yaml
voice:
  device: "cpu"
```

### Issue: Microphone not detected

**Troubleshooting**:
```bash
# List available microphones
python -c "import sounddevice; sounddevice.query_devices()"
```

Check Windows Settings:
1. Settings → Privacy & Security → Microphone
2. Enable microphone access
3. Restart application

### Issue: Camera not working

**Troubleshooting**:
```bash
# Test camera
python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"
```

**Solutions**:
1. Check camera connection (USB cameras)
2. Disable other apps using camera (Zoom, Skype, etc.)
3. Update camera drivers
4. Try different camera index: 0, 1, 2, etc.

### Issue: Slow startup or performance

**Causes**: Low RAM, other apps running

**Solutions**:
1. Close unnecessary applications
2. Run in headless mode: `--headless`
3. Disable GUI effects in Settings
4. Increase virtual memory (Windows)
5. Restart computer

---

## System-Specific Guides

### Windows 10

✅ Fully supported. Recommended version.

1. Install Python 3.11
2. Follow standard installation
3. Ensure Windows is updated (Settings → Update)

### Windows 11

✅ Fully supported. Works great.

1. Install Python 3.11
2. Follow standard installation
3. May need to allow app through Windows Defender

### Windows 7

⚠️ Supported but older. May have compatibility issues.

1. Install Python 3.10 (some 3.11 packages may not support Win7)
2. Follow standard installation
3. May need Windows 7 Service Pack 1

### Low-Spec Hardware (4GB RAM)

💡 Application is optimized for low-spec hardware!

**Recommendations**:
1. Use headless mode: `--headless`
2. Disable GUI: Use voice commands only
3. Disable eye tracking if not needed
4. Close browser and other heavy apps
5. Use Whisper "tiny" or "base" model (not "large")

---

## GPU Acceleration (Optional)

For NVIDIA GPUs, install CUDA:

1. Download NVIDIA CUDA Toolkit
2. Install CUDA
3. Install cuDNN
4. Update requirements:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

---

## Building Executable (.exe)

### Prerequisites
```bash
pip install pyinstaller
```

### Build
```bash
pyinstaller build.spec
```

### Output
- Windows executable: `dist/AccessibilityAgent/AccessibilityAgent.exe`
- Size: ~500MB (includes all dependencies and models)

### Distribute
1. Create installer using NSIS: https://nsis.sourceforge.io/
2. Or zip the `dist/AccessibilityAgent/` folder
3. Users can run `AccessibilityAgent.exe` directly

---

## Verification

Run tests to verify installation:

```bash
python -m pytest tests/ -v
```

Expected output:
```
===== test session starts =====
platform win32 -- Python 3.11.0
collected 800+ items

tests/test_integration.py ........................ PASSED
tests/test_performance.py ........................ PASSED
...

===== 800+ passed in 45s =====
```

If tests fail, check:
1. All dependencies installed: `pip list`
2. No conflicting Python installations
3. Sufficient disk space and RAM
4. Internet connection (for downloading models)

---

## Post-Installation Setup

1. **Calibrate Eye Tracker**
   - Launch app
   - Go to Eye Tracking tab
   - Click "Calibrate"
   - Follow on-screen instructions

2. **Test Voice Commands**
   - Go to Voice Control tab
   - Click "Start Listening"
   - Say "Click" or "Open Notepad"

3. **Configure Settings**
   - Go to Settings tab
   - Choose language, theme, microphone, camera

4. **Create First Macro**
   - Go to Macro tab
   - Click "Start Recording"
   - Perform actions
   - Click "Stop Recording"

---

## Support

If you encounter issues:

1. Check [USER_GUIDE_EN.md](USER_GUIDE_EN.md) - Troubleshooting section
2. Check logs: `%APPDATA%\accessibility-agent\logs\`
3. Create GitHub issue: https://github.com/adibgafur/accessibility-automation-agent/issues

---

## Next Steps

After installation:
1. Read [USER_GUIDE_EN.md](USER_GUIDE_EN.md) or [USER_GUIDE_BN.md](USER_GUIDE_BN.md)
2. Explore features in the UI
3. Record custom macros for your workflow
4. Give feedback or contribute improvements!

---

**Version**: 0.1.0
**Last Updated**: February 2026
