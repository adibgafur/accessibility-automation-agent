# Accessibility Automation Agent

**An AI-powered desktop automation application for users without hands**

[![GitHub](https://img.shields.io/badge/GitHub-adibgafur%2Faccessibility--automation--agent-blue?logo=github)](https://github.com/adibgafur/accessibility-automation-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/downloads/)

## Overview

**Accessibility Automation Agent** is a comprehensive desktop automation solution designed for users with disabilities, particularly those without hand mobility. It combines:

- **Voice Control** - Natural language commands in English and Bengali
- **Eye/Nose Tracking** - Using your nose as a cursor pointer
- **Blink Actions** - Single blink for left-click, double-blink for right-click
- **Hybrid GUI Detection** - UFO2 (primary) + GUIrilla (fallback) for reliable automation
- **Browser Automation** - Voice-controlled web browsing (Gmail, Google, Docs, etc.)
- **Macro Recording** - Record and replay complex workflows
- **Accessible UI** - Large buttons, high-contrast, keyboard navigation

## Key Features

### 🎤 Voice Control
- Speech-to-text using OpenAI's Whisper
- Support for English and Bengali
- Natural language command parsing
- Offline processing (no internet required)

### 👁️ Eye Tracking
- Real-time nose position detection
- Cursor movement following your nose
- Single-blink for left-click
- Double-blink for right-click
- Customizable sensitivity and smoothing

### 🖥️ Smart GUI Automation
- **UFO2 (Primary)**: Microsoft's Windows UIA detector
- **GUIrilla (Fallback)**: Visual detection when UI changes
- Automatic engine switching
- Handles app updates gracefully

### 🌐 Browser Control
- Selenium-based automation
- Voice commands: "Open Gmail", "Search for...", "Click link..."
- Form filling and text input
- Tab management and navigation

### 🔄 Macro System
- Record complex workflows
- Save and replay with hotkeys
- Pre-built templates for common tasks
- Variable support for reusable macros

### ♿ Accessibility
- **No hands required** - Fully voice and eye-controlled
- **Large UI elements** - 64x64px minimum buttons
- **High contrast** - WCAG AAA compliance
- **Keyboard navigation** - Tab, Enter, Arrow keys
- **Screen reader support** - ARIA-like labels
- **Bengali language** - Full support for Bengali users

## System Requirements

### Minimum (Low-Spec)
- **OS**: Windows 10/11
- **RAM**: 4GB
- **Processor**: Intel i3 or equivalent
- **Webcam**: Required for eye tracking
- **Microphone**: Required for voice control

### Recommended
- **RAM**: 8GB
- **Processor**: Intel i5 or better
- **GPU**: NVIDIA CUDA-capable (optional, for faster processing)

## Installation

### Quick Start (Windows)

1. **Clone the repository**
   ```bash
   git clone https://github.com/adibgafur/accessibility-automation-agent.git
   cd accessibility-automation-agent
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python src/main.py
   ```

### Full Installation Guide
See [SETUP.md](docs/SETUP.md) for detailed installation instructions.

## Usage

### Basic Voice Commands

**Navigation:**
- "Open Chrome"
- "Open Gmail"
- "Go to Google"
- "Click link [name]"

**Text Input:**
- "Type [text]"
- "Search for [query]"
- "Select all"
- "Copy"
- "Paste"

**System:**
- "Screenshot"
- "Volume up/down"
- "Next tab"
- "Go back"

For complete command reference, see [VOICE_COMMANDS.md](docs/VOICE_COMMANDS.md)

### Eye Tracking

1. Click "Calibrate" in Eye Tracker Panel
2. Follow on-screen instructions
3. Look at your nose and move head naturally
4. Blink to click

### Macro Recording

1. Click "Start Recording" in Automation Panel
2. Perform your workflow (voice + blinks)
3. Click "Stop Recording"
4. Name and save macro
5. Play back anytime with hotkey

## Architecture

```
┌─────────────────────────────────────────────┐
│     Voice Control + Eye Tracking             │
│  (Whisper + MediaPipe/OpenCV)              │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│   GUI Automation Layer (Hybrid)              │
│  • UFO2 (primary - native Windows)          │
│  • GUIrilla (fallback - visual detection)   │
└─────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│     Action Execution Layer                  │
│  • pyautogui (mouse/keyboard)              │
│  • Selenium (browser control)              │
│  • Macro recording/playback                │
└─────────────────────────────────────────────┘
```

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture.

## Development Phases

The project is organized into 11 phases:

| Phase | Feature | Status |
|-------|---------|--------|
| 0 | Git & Repository | ✅ Complete |
| 1 | Foundation & Setup | 🚀 In Progress |
| 2 | Hybrid GUI Detection | ⏳ Pending |
| 3 | Eye/Nose Tracking | ⏳ Pending |
| 4 | Voice Control | ⏳ Pending |
| 5 | Mouse & Keyboard | ⏳ Pending |
| 6 | Browser Automation | ⏳ Pending |
| 7 | App Launcher | ⏳ Pending |
| 8 | Macro System | ⏳ Pending |
| 9 | PyQt6 UI | ⏳ Pending |
| 10 | Integration & Optimization | ⏳ Pending |
| 11 | Documentation & Deployment | ⏳ Pending |

## Contributing

Contributions are welcome! This project is designed to be accessible for people with disabilities.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Technologies Used

- **Python 3.11+** - Core language
- **PyQt6** - Accessible desktop UI
- **Whisper** - Speech-to-text (English + Bengali)
- **MediaPipe** - Eye and face tracking
- **OpenCV** - Computer vision
- **UFO2** - Microsoft's Windows automation framework
- **GUIrilla** - Visual GUI detection
- **Selenium** - Browser automation
- **pyautogui** - Mouse/keyboard control

## Documentation

- [User Guide](docs/USER_GUIDE.md) (English)
- [User Guide](docs/USER_GUIDE_BN.md) (বাংলা)
- [Voice Commands](docs/VOICE_COMMANDS.md)
- [Setup Guide](docs/SETUP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Microsoft UFO2 framework for GUI automation
- OpenAI Whisper for speech recognition
- Google MediaPipe for computer vision
- The accessibility community for inspiration

## Support

- 📖 [Documentation](docs/)
- 🐛 [Report Issues](https://github.com/adibgafur/accessibility-automation-agent/issues)
- 💬 [Discussions](https://github.com/adibgafur/accessibility-automation-agent/discussions)

## Roadmap

- ✅ Phase 0-1: Project foundation
- 🚀 Phase 2-6: Core automation features
- 📋 Phase 7-9: UI and macro system
- 🔧 Phase 10-11: Optimization and deployment

---

**Made with ❤️ for accessibility and inclusion**

Status: **Active Development** 🚀

Last Updated: 2026-02-25
