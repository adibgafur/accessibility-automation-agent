# Accessibility Automation Agent - User Guide (English)

## Table of Contents

1. [Introduction](#introduction)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Getting Started](#getting-started)
5. [Features & Usage](#features--usage)
6. [Configuration](#configuration)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Introduction

**Accessibility Automation Agent** is an AI-powered desktop automation tool designed for users without hands or with limited mobility. It enables hands-free control of your computer through:

- **Voice Commands**: Speak natural commands to control your computer
- **Eye Tracking**: Control mouse cursor with your eyes
- **Blink Detection**: Click by blinking your eyes
- **Macro Recording**: Record and replay complex workflows
- **Browser Automation**: Search, navigate, and interact with web pages
- **Application Launcher**: Launch applications with voice commands
- **GUI Detection**: Automatically detect interactive elements on screen

### Key Benefits

✅ **Hands-Free Control**: Complete desktop automation without keyboard or mouse
✅ **Bilingual Support**: English and Bengali interface and voice commands
✅ **Low-Spec Friendly**: Optimized for computers with 4GB RAM and Intel i3 processors
✅ **Error Recovery**: Automatically recovers from failures
✅ **Customizable**: Record and save custom macros for your workflows

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Windows 7 or later (Windows 10/11 recommended) |
| **RAM** | 4GB minimum (8GB recommended) |
| **CPU** | Intel i3 or equivalent (i5+ recommended) |
| **Storage** | 2GB free disk space |
| **Webcam** | USB webcam or built-in camera for eye tracking |
| **Microphone** | USB microphone or built-in mic for voice commands |

### Hardware Recommendations for Best Performance

- Windows 10 or Windows 11
- 8GB or more RAM
- Intel i5/i7 or AMD equivalent
- SSD (faster startup and loading)
- 1080p USB webcam
- Noise-canceling microphone

### Network

- Internet connection for initial setup and model downloading
- Offline mode available after setup

---

## Installation

### Step 1: Download and Install Python

1. Visit [python.org](https://www.python.org/downloads/)
2. Download **Python 3.10** or **3.11** (Windows 64-bit)
3. Run the installer and **check "Add Python to PATH"**
4. Click "Install Now"

Verify installation:
```bash
python --version
```

### Step 2: Download the Application

**Option A: Using Git (Recommended)**
```bash
git clone https://github.com/adibgafur/accessibility-automation-agent.git
cd accessibility-automation-agent
```

**Option B: Download ZIP**
1. Visit [GitHub Repository](https://github.com/adibgafur/accessibility-automation-agent)
2. Click "Code" → "Download ZIP"
3. Extract the ZIP file to your desired location

### Step 3: Install Dependencies

Open Command Prompt in the project directory and run:

```bash
pip install -r requirements.txt
```

This will install:
- PyQt6 (User Interface)
- Whisper (Voice Recognition)
- MediaPipe (Eye Tracking)
- Selenium (Browser Automation)
- OpenCV (Computer Vision)
- And other dependencies

**Note**: First-time setup may take 10-15 minutes as large models are downloaded.

### Step 4: Download ML Models

On first run, the application will automatically download:
- Whisper model (1.4GB) - for voice recognition
- MediaPipe models (~50MB) - for eye tracking
- GUIrilla model (~2GB) - for GUI detection

**Total: ~3.5GB** - Ensure you have sufficient internet bandwidth and disk space.

### Step 5: Verify Installation

Run the test suite to ensure everything is working:

```bash
python -m pytest tests/ -v
```

All tests should pass. If there are failures, see [Troubleshooting](#troubleshooting).

---

## Getting Started

### First Time Setup

#### 1. Launch the Application

**GUI Mode** (Recommended):
```bash
python -m src.main --language en
```

**Headless Mode** (Voice + Eye Tracking only):
```bash
python -m src.main --headless --language en
```

#### 2. Calibrate Eye Tracker

1. Click on the "Eye Tracking" tab
2. Click "Start Calibration"
3. Follow the on-screen instructions
4. Look at the calibration points as they appear
5. Complete the calibration sequence

#### 3. Test Voice Commands

1. Click on the "Voice Control" tab
2. Click "Start Listening"
3. Say a simple command like "Click" or "Open Notepad"
4. The system will execute the command

#### 4. Configure Settings

1. Go to "Settings" tab
2. Choose your preferred:
   - **Language**: English or Bengali
   - **Theme**: Light, Dark, or High Contrast
   - **Audio Feedback**: Enable/Disable text-to-speech
   - **Microphone**: Select your microphone device
   - **Camera**: Select your camera for eye tracking

---

## Features & Usage

### 1. Voice Control

#### Voice Commands

| Command | Function |
|---------|----------|
| **"Click"** | Click at current eye gaze position |
| **"Double click"** | Double-click at current position |
| **"Right click"** | Right-click at current position |
| **"Search [term]"** | Search the web for the given term |
| **"Open [app name]"** | Launch an application |
| **"Record macro"** | Start recording a macro |
| **"Stop recording"** | Stop recording current macro |
| **"Play [macro name]"** | Replay a saved macro |

#### Custom Voice Commands

To add custom voice commands:
1. Edit `config/default_settings.yaml`
2. Add your command to the `voice_commands` section
3. Restart the application

Example:
```yaml
voice_commands:
  custom_email:
    - "open email"
    - "open gmail"
    action: "open_app('Gmail')"
```

### 2. Eye Tracking

#### Features

- **Smooth Tracking**: Real-time eye position tracking
- **Blink Detection**: Single or double-blink for clicking
- **Calibration**: 9-point calibration for accuracy
- **Jitter Filtering**: Reduces cursor shake from eye tremors

#### Usage

1. Enable eye tracking from the UI
2. Complete calibration when prompted
3. Look at the screen to move the cursor
4. Blink to click at the current position

#### Blink Settings

Configure blink detection in Settings:
- **Single Blink**: Click once
- **Double Blink**: Double-click
- **Blink Duration**: Adjust sensitivity for false positives

### 3. Macro Recording & Playback

#### Recording a Macro

1. Click "Macro" tab
2. Enter macro name (e.g., "email_workflow")
3. Click "Start Recording"
4. Perform your actions (clicks, typing, navigation)
5. Click "Stop Recording"
6. Your macro is saved automatically

#### Playing a Macro

1. Select a saved macro from the list
2. Set playback speed (0.5x to 2x)
3. Set loop count (how many times to repeat)
4. Click "Play Macro"
5. Watch as the actions are replayed

#### Macro Examples

**Example 1: Open Email**
1. Click email application icon
2. Wait for application to open
3. Stop recording
4. Name it "open_email"
5. Play anytime to open email quickly

**Example 2: Compose Email**
1. Record: Open email → Click "Compose" → Type standard greeting
2. Name it "email_template"
3. Play to start composing with template

### 4. Browser Automation

#### Features

- **Web Search**: Voice-controlled web searching
- **Tab Management**: Open, close, switch tabs
- **Form Filling**: Auto-fill common form fields
- **Navigation**: Back, forward, reload pages

#### Usage Examples

**Search Google**
- Say: "Search python tutorial"
- The application opens Chrome and searches for "python tutorial"

**Navigate Websites**
- Say: "Open Google"
- Application launches Google in your browser

**Fill Forms** (Manual)
- Use eye tracking to look at form fields
- Say: "Click" to select field
- Say voice commands or use text-to-speech to have text typed

### 5. Application Launcher

#### Features

- **Auto-Discovery**: Finds installed applications
- **Quick Launch**: Launch apps with voice commands
- **Recent Apps**: Quick access to frequently used apps

#### Usage

**Launch Application**
- Say: "Open Notepad"
- Say: "Open Excel"
- Say: "Open Chrome"

**List Available Apps**
- Click "App Launcher" tab
- See all discoverable applications
- Click to launch, or use voice command

#### Supported Applications

- **Office**: Word, Excel, PowerPoint, OneNote
- **Browsers**: Chrome, Firefox, Edge, IE
- **Editors**: Notepad, VS Code, Visual Studio
- **Media**: VLC, Windows Media Player
- **Communication**: Outlook, Gmail (web)
- And hundreds more...

### 6. Mouse & Keyboard Control

#### Mouse Actions

- **Click**: Single left-click at current position
- **Right-click**: Context menu
- **Double-click**: Open files/applications
- **Drag**: Move and drop items
- **Scroll**: Scroll up/down on web pages

#### Text Input

- Use voice to dictate text
- All Unicode characters supported (English, Bengali, etc.)
- Special characters available through commands

---

## Configuration

### Configuration Files

Location: `config/` directory

**Main Configuration**: `config/default_settings.yaml`

```yaml
application:
  name: "Accessibility Automation Agent"
  version: "0.1.0"

voice:
  enabled: true
  language: "en"  # "en" or "bn"
  confidence_threshold: 0.5
  timeout: 10

eye_tracking:
  enabled: true
  camera_index: 0  # 0 for default camera
  fps: 30
  smoothing_factor: 0.7

ui:
  theme: "dark"  # "light", "dark", "high_contrast"
  font_size: 12
  language: "en"

accessibility:
  text_to_speech: true
  high_contrast: false
```

### Command Line Options

```bash
# Set language
python -m src.main --language bn

# Set log level
python -m src.main --log-level DEBUG

# Run in headless mode
python -m src.main --headless

# Disable text-to-speech
python -m src.main --no-tts

# Use custom config file
python -m src.main --config /path/to/config.yaml
```

### Adjusting Settings in UI

1. Open the application
2. Go to "Settings" tab
3. Adjust:
   - **Theme**: Light/Dark/High Contrast (WCAG AAA compliant)
   - **Language**: English/Bengali
   - **Font Size**: 10-20pt
   - **Microphone**: Select your input device
   - **Camera**: Select your camera
   - **Audio Feedback**: Enable/Disable TTS

---

## Troubleshooting

### Common Issues

#### 1. Application Won't Start

**Error**: "ModuleNotFoundError: No module named 'PyQt6'"

**Solution**:
```bash
pip install -r requirements.txt
```

**Error**: "CUDA out of memory" or GPU errors

**Solution**: 
- Use CPU mode (default)
- Close other applications using GPU
- Edit `config/default_settings.yaml` and set `device: "cpu"`

#### 2. Voice Recognition Not Working

**Issue**: Voice commands not recognized

**Troubleshooting**:

```bash
# Test microphone
python -c "import sounddevice; print(sounddevice.default_device)"
```

1. Check microphone is not muted
2. Check microphone permissions in Windows Settings
3. Test microphone volume is sufficient (at least 50%)
4. Try different microphone if available
5. Set language correctly in Settings
6. Check confidence threshold is not too high

#### 3. Eye Tracking Issues

**Issue**: Eye cursor is shaky or inaccurate

**Solutions**:
1. Re-calibrate: Click "Calibrate" in Eye Tracking tab
2. Ensure adequate lighting
3. Clean camera lens
4. Adjust camera position for better angle
5. Increase `smoothing_factor` in config (0.5-0.9)
6. Reduce `jitter_threshold` value

**Issue**: Camera not detected

**Solutions**:
```bash
# Check available cameras
python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"
```
1. Check camera connection (USB cameras)
2. Disable other applications using camera
3. Update camera drivers
4. Try different camera index (0, 1, 2) in Settings

#### 4. Browser Automation Issues

**Issue**: Browser automation not working

**Solutions**:
1. Install Chrome or Firefox
2. Ensure Selenium WebDriver is properly installed
3. Check internet connection
4. Try restarting the browser
5. Check for browser security dialogs blocking automation

#### 5. High Memory Usage

**Issue**: Application using more than 1GB RAM

**Solutions**:
1. Close other applications
2. Reduce cache size in config
3. Disable eye tracking if not needed
4. Use headless mode instead of GUI
5. Restart application periodically

#### 6. Poor Performance on Low-Spec Hardware

**Issue**: Application is slow on 4GB RAM machine

**Solutions**:
1. Use headless mode: `python -m src.main --headless`
2. Disable GUI: Reduce visual effects in theme settings
3. Close unnecessary applications
4. Increase virtual memory/page file
5. Use smaller Whisper model (tiny or base)

### Debug Mode

Enable debug logging:

```bash
python -m src.main --log-level DEBUG
```

Logs are saved to:
- Windows: `%APPDATA%\accessibility-agent\logs\`
- Linux: `~/.config/accessibility-agent/logs/`

### Getting Help

1. Check [FAQ](#faq) section
2. Review logs in debug mode
3. Visit [GitHub Issues](https://github.com/adibgafur/accessibility-automation-agent/issues)
4. Create a new issue with:
   - Error message and logs
   - Steps to reproduce
   - System specifications
   - Screenshots if applicable

---

## FAQ

### General Questions

**Q: Is this application free?**
A: Yes, it's open-source under the MIT license.

**Q: What languages are supported?**
A: English (en) and Bengali (bn). More languages can be added.

**Q: Can I use this offline?**
A: Yes, after initial setup. Models are cached locally.

**Q: Is my privacy protected?**
A: Yes. All processing happens locally on your computer. No data is sent to external servers.

**Q: Can I modify or extend the application?**
A: Yes! The source code is open. You can fork and contribute improvements.

### Technical Questions

**Q: What camera do I need?**
A: Any USB camera or built-in webcam (1280x720 minimum recommended).

**Q: What microphone do I need?**
A: USB microphone or built-in mic (16kHz, mono minimum).

**Q: Does it work on Mac or Linux?**
A: Currently Windows only. Mac/Linux support can be added by the community.

**Q: How accurate is eye tracking?**
A: Typically 95%+ accuracy after calibration. Varies by camera quality and lighting.

**Q: How long is the voice command latency?**
A: 0.5-2 seconds depending on hardware and model.

### Usage Questions

**Q: Can I create custom voice commands?**
A: Yes, edit `config/default_settings.yaml` and add custom commands.

**Q: Can I record macros with delays?**
A: Not yet, but features like "wait 5 seconds" can be added.

**Q: Can I save macros to the cloud?**
A: Currently saved locally. Cloud sync can be implemented.

**Q: Can multiple users share the same computer?**
A: Yes, each user can have separate calibrations and macro libraries.

### Performance Questions

**Q: Will this work on my 4GB RAM laptop?**
A: Yes! It's optimized for low-spec hardware. Performance may be slower on background tasks.

**Q: How much disk space do I need?**
A: ~2GB for models and application code. Additional space for macro libraries.

**Q: Can I run this on a Chromebook?**
A: Not directly, but you can use remote desktop to a Windows machine.

### Accessibility Questions

**Q: Is the UI accessible for people with visual impairments?**
A: UI has high-contrast modes. Screen reader support can be added.

**Q: Can I use this with head tracking instead of eye tracking?**
A: Not yet, but it can be added as a module.

**Q: What about speech recognition in noisy environments?**
A: Whisper model handles background noise well. Consider using a noise-canceling microphone for best results.

---

## Additional Resources

- **GitHub**: [github.com/adibgafur/accessibility-automation-agent](https://github.com/adibgafur/accessibility-automation-agent)
- **Documentation**: See `docs/` directory for technical documentation
- **Issues & Feedback**: [GitHub Issues](https://github.com/adibgafur/accessibility-automation-agent/issues)

---

## License

This project is licensed under the **MIT License**. See `LICENSE` file for details.

---

## Support

For issues, questions, or feature requests:
1. Check the [FAQ](#faq)
2. Search existing [GitHub Issues](https://github.com/adibgafur/accessibility-automation-agent/issues)
3. Create a new issue with detailed information

---

**Version**: 0.1.0
**Last Updated**: February 2026
**Status**: Production Ready (Phase 10 Integrated, Phase 11 Complete)
