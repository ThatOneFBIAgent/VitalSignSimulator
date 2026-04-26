# VitalSign Pro — High-Fidelity Patient Monitor Simulator

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Pygame](https://img.shields.io/badge/UI-Pygame-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-Production--Ready-brightgreen.svg)

**VitalSign Pro** is a high-fidelity, interactive patient monitor simulation designed for clinical education, medical theater, and emergency response training. It provides a realistic representation of modern bedside monitors with dynamic physiological waveforms and a robust scenario engine.

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
- **Dynamic Waveforms**: Real-time rendering of Lead II ECG, Plethysmograph (SpO2), Respiration, Arterial Blood Pressure (ABP), and EtCO2.
- **Scenario Macro Engine**: Scripted clinical events (Routines) with time-based keyframes to simulate complex patient deteriorations (e.g., Code Blue, RSI, Anaphylaxis).
- **Multi-Brand Themes**: Authentic visual styles mimicking industry leaders like Philips IntelliVue, Nihon Kohden, GE Carescape, and Mindray.
- **Interactive Alarms**: Priority-based audible and visual alarms with hysteresis and per-parameter flashing indicators.
- **Full Customization**: Adjustable alarm limits, patient metadata (Bed/Unit/Hospital), and physiological parameters via a live configuration menu.

## ⌨️ Controls & Shortcuts

| Key | Action |
|-----|--------|
| **TAB** | Open/Close Configuration Menu |
| **SPACE** | Start/Pause Selected Routine |
| **B** | Reset Simulation to Healthy Baseline (Clear Routine) |
| **S** | Mute/Unmute Alarm Audio |
| **U** | Toggle UI Overlay (Vitals only) |
| **F11** | Toggle Fullscreen |
| **1 - 5** | Jump to Config Menu Tabs |
| **ESC** | Exit Application |

## 🚀 Installation & Build

### Requirements
- Python 3.8+
- Pygame
- Numpy

### Quick Start
1. Place your pulse and alarm sounds in the root directory:
   - `pulse_tone.wav`
   - `alarm_med.wav`
   - `alarm_high.wav`
2. Run the application:
   ```bash
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
