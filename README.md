# VitalSign Pro — High-Fidelity Patient Monitor Simulator

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Pygame](https://img.shields.io/badge/UI-Pygame-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-Production--Ready-brightgreen.svg)

**VitalSign Pro** is a high-fidelity, interactive patient monitor simulation designed for clinical education, medical theater, and emergency response training. It provides a realistic representation of modern bedside monitors with dynamic physiological waveforms, a robust scenario engine, and a fully detached configuration panel for clean OBS/stream capture.

---

### ⚖️ MANDATORY LEGAL & MEDICAL DISCLAIMER

**THIS SOFTWARE IS FOR SIMULATION, EDUCATIONAL THEATER, AND ENTERTAINMENT PURPOSES ONLY.**

1. **NOT A MEDICAL DEVICE**: VitalSign Pro is **NOT** a medical device, diagnostic tool, or clinical monitoring system. It has not been cleared or approved by any health authority (e.g., FDA, EMA).
2. **NO CLINICAL USE**: This software must **NEVER** be used in a real clinical setting, for monitoring actual patients, for medical diagnosis, or for making life-altering medical decisions.
3. **APPROXIMATION ONLY**: The physiological models, waveforms, and data generated are mathematical approximations designed for training scenarios. They do not represent real-time medical accuracy.
4. **NO LIABILITY**: The author(s) and contributors of this project assume **ZERO LIABILITY** for any injury, death, property damage, or legal consequences resulting from the misuse of this software in real-world medical situations or any other context.
5. **USER ASSUMPTION OF RISK**: By running this software, you acknowledge and agree that you use it at your own risk and that you are solely responsible for ensuring it is not used for real patient care.

---

## ✨ Key Features

- **Dynamic Waveforms**: Real-time 12 lead ECG, Plethysmograph (SpO2), Respiration, ABP, and EtCO2 with phosphor persistence and CRT effects.
- **30 ECG Rhythms**: Sinus variants, SVT/IST, AFib/AFlutter/PACs, junctional rhythms, PVC patterns, VT/VFib/Torsades, AV blocks, bundle branch blocks, WPW, long QT, hyperkalemia, STEMI patterns, Asystole, and PEA.
- **8 Respiratory Patterns**: Eupnea, Hyperpnea, Bradypnea, Tachypnea, Apnea, Cheyne-Stokes, Biot, and Kussmaul.
- **Cascading Physiology**: Respiratory failure → hypoxia → tachycardia → cardiac arrest. Vitals interact realistically.
- **Scenario Engine**: Time-based routines with keyframed clinical events (Code Blue, RSI, Anaphylaxis, etc.) plus a graphical Routine Editor for authoring custom TOML scenarios.
- **16 Clinical Presets**: One-click scenarios from Healthy Adult to Cardiac Arrest, Opioid Overdose, Malignant Hyperthermia, and more.
- **Multi-Brand Themes**: Philips-style, Nihon Kohden, GE Carescape, Mindray, Legacy CRT, and others.1
- **Priority Alarm System**: Audible and visual alarms with hysteresis, per-parameter flashing, acknowledgement support, and hardware-synced LED diagnostic patterns.
- **OBS-Friendly Config Panel**: Fully detached dark-themed configuration window — OBS captures only the monitor while you control everything from a separate window.

## ⌨️ Controls & Shortcuts

| Key | Action |
|-----|--------|
| **TAB** | Open Configuration Panel (separate window) |
| **SPACE** | Start/Pause Selected Routine |
| **B** | Reset Simulation to Healthy Baseline |
| **A** | Acknowledge / Silence Active Alarm |
| **S** | Mute/Unmute Alarm Audio |
| **U** | Toggle UI Overlay (Vitals only) |
| **G** | Toggle ECG Grid |
| **F11** | Toggle Fullscreen |
| **ESC** | Exit Application |

## 🎥 OBS / Streaming Setup

VitalSign Pro is designed for clean recording and streaming:

1. Press **TAB** to open the configuration panel — it launches as a **separate OS window**.
2. In OBS, use **Window Capture** and select only the **VitalSign Simulator** window.
3. The config panel can be moved to a second monitor or kept off-screen — changes apply instantly to the main monitor.
4. Status bar shows reduced hints (Ack, Fullscreen, Exit) while the config panel is open.

## 🚀 Installation & Build

### Requirements
- Python 3.8+
- Pygame
- Numpy

### Quick Start
```bash
pip install pygame numpy
python main.py
```

### Building the Executable
To package the application for Windows:
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name VitalSignPro main.py
```
> [!IMPORTANT]
> When using the `.exe`, ensure that your `.wav` sound files are placed in the **same directory** as the executable. The application looks for these files locally at startup to initialize the audio system.


## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.


1- GE, Phillips, or any other mentioned brands are not affiliated with this program. If you'd like file a takedown please open an issue on github.