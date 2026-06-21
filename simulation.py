"""
Physiological simulation engine.
Generates ECG, SpO2 Pleth, Respiration, ABP, and Capnography waveforms.
Supports multiple ECG rhythm modes: Normal Sinus, AFib, PVCs, VTach, VFib.

⚖️ LEGAL DISCLAIMER:
THIS SOFTWARE IS FOR SIMULATION AND EDUCATIONAL THEATER PURPOSES ONLY.
IT IS NOT A MEDICAL DEVICE. NEVER USE FOR REAL PATIENT MONITORING OR DIAGNOSIS.
THE AUTHOR ASSUMES NO LIABILITY FOR MISUSE.
"""
import numpy as np
import random
import time
import hashlib
import sys

ECG_RHYTHMS = [
    "[Norm] Sinus Rhythm", "[Sinus] Bradycardia", "[Sinus] Tachycardia",
    "[Sinus] Arrhythmia", "[Sinus] IST",
    "[Atrial] SVT", "[Atrial] AFib", "[Atrial] AFlutter", "[Atrial] PACs",
    "[Junctional] Rhythm", "[Junctional] Accelerated",
    "[Vent] PVCs", "[Vent] Bigeminy", "[Vent] Trigeminy", "[Vent] VTach",
    "[Vent] VFib", "[Vent] Torsades",
    "[Block] 1st Deg AV", "[Block] Wenckebach", "[Block] Mobitz II",
    "[Block] 3rd Deg AV", "[Block] RBBB", "[Block] LBBB",
    "[Preexcitation] WPW", "[Repol] Long QT", "[Repol] Hyperkalemia",
    "[Ischemia] Anterior STEMI", "[Ischemia] Inferior STEMI",
    "[Arrest] Asystole", "[Arrest] PEA"
]
RESP_PATTERNS = ["Eupnea (Normal)", "Hyperpnea", "Bradypnea", "Tachypnea", "Apnea", "Cheyne-Stokes", "Biot", "Kussmaul"]
ECG_LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
ECG_DISPLAY_LEADS = ["Clean"] + ECG_LEADS


class PhysioSim:
    def __init__(self, sample_rate=250):
        self.sample_rate = sample_rate
        self.dt = 1.0 / sample_rate

        self._safety_verified = False
        self._verify_safety()

        # --- Configurable Targets & Ranges ---
        self.targets = {
            "hr":     {"value": 72.0,  "min": 62.0,  "max": 82.0,  "drift": 0.15},
            "spo2":   {"value": 98.0,  "min": 96.0,  "max": 100.0, "drift": 0.03},
            "rr":     {"value": 16.0,  "min": 13.0,  "max": 19.0,  "drift": 0.08},
            "bp_sys": {"value": 120.0, "min": 112.0, "max": 130.0, "drift": 0.1},
            "bp_dia": {"value": 80.0,  "min": 72.0,  "max": 88.0,  "drift": 0.05},
            "temp":   {"value": 36.8,  "min": 36.6,  "max": 37.0,  "drift": 0.002},
            "etco2":  {"value": 38.0,  "min": 35.0,  "max": 41.0,  "drift": 0.05},
        }

        # --- Live Values (raw) ---
        self.hr = 72.0
        self.spo2 = 98.0
        self.rr = 16.0
        self.bp_sys = 120.0
        self.bp_dia = 80.0
        self.bp_map = 93.0
        self.temp = 36.8
        self.etco2 = 38.0

        # --- Smoothed Display Values (for numeric readout) ---
        self.display = {
            "hr": 72.0, "spo2": 98.0, "rr": 16.0,
            "bp_sys": 120.0, "bp_dia": 80.0, "bp_map": 93.0,
            "temp": 36.8, "etco2": 38.0,
        }

        # --- ECG Rhythm ---
        self.ecg_rhythm = "[Norm] Sinus Rhythm"
        self._beat_counter = 0
        self._pvc_interval = random.randint(4, 10)
        self._pac_interval = random.randint(5, 12)
        self._in_pvc = False
        self._in_pac = False
        self._afib_rr_mod = 1.0
        self._sinus_arrhythmia_mod = 1.0
        self._vfib_t = 0.0
        self.ecg_display_lead = "Clean"

        # --- Internal Phase Accumulators ---
        self.phase_ecg = 0.0
        self.phase_resp = 0.0
        self.point_accum = 0.0
        self._resp_time = 0.0
        self._artifact_time = 0.0

        # --- Features & Probes ---
        self.resp_pattern = "Regular"
        self.probe_etco2 = True
        self.probe_temp = True
        self.enable_lead_artifacts = True
        self.lead_artifact_level = 0.18
        self.etco2_variability = 0.12
        self.etco2_breath_variation = 1.0
        self._lead_pop_until = {lead: 0.0 for lead in ECG_LEADS}
        self._lead_pop_value = {lead: 0.0 for lead in ECG_LEADS}
        self._motion_burst_until = 0.0
        self._r_gate_until = 0.0

        # --- R-wave detection for beep ---
        self.r_wave_detected = False
        self._prev_ecg = 0.0
        self._aflutter_hr = 100.0
        
        self.cal_time = 6.0  # Startup calibration timer
        self.variation_factor = 1.0
        self.resp_variation = 1.0
        self.pleth_variation = 1.0
        self.hr_irregular = False

    def set_preset(self, preset: dict):
        """Apply a preset dictionary to targets and live values."""
        # Reset rhythm and probe overrides to baseline
        self.ecg_rhythm = "[Norm] Sinus Rhythm"
        self.resp_pattern = "Eupnea (Normal)"
        self.probe_etco2 = True
        self.probe_temp = True

        for key, val in preset.items():
            if key in self.targets:
                t = self.targets[key]
                t["value"] = val
                setattr(self, key, float(val))
                if key in self.display:
                    self.display[key] = float(val)
                # Auto-expand fluctuation range around new target
                padding = max(abs(val * 0.08), 2.0)
                t["min"] = val - padding
                t["max"] = val + padding
        self.bp_map = self.bp_dia + (self.bp_sys - self.bp_dia) / 3.0
        self.display["bp_map"] = self.bp_map

    def _drift(self, current, key):
        """Ornstein-Uhlenbeck drift — smooth mean-reversion with gentle noise."""
        t = self.targets[key]
        target = t["value"]
        drift_rate = t["drift"]
        lo, hi = t["min"], t["max"]

        # Auto-expand bounds to always include the target
        lo = min(lo, target - 1.0)
        hi = max(hi, target + 1.0)

        # Smooth mean-reversion (theta) with reduced noise
        theta = 0.008
        noise = random.gauss(0, drift_rate * 0.12)
        delta = theta * (target - current) + noise

        return max(lo, min(hi, current + delta))

    def _smooth_display(self):
        """Exponentially smooth display values to prevent jitter in readouts."""
        # Use faster smoothing (faster crash) if in cardiac arrest
        a = 0.2 if self.ecg_rhythm in ("VFib", "Asystole") else 0.06
        self.display["hr"]     = self.display["hr"]     * (1 - a) + self.hr * a
        self.display["spo2"]   = self.display["spo2"]   * (1 - a) + self.spo2 * a
        self.display["rr"]     = self.display["rr"]     * (1 - a) + self.rr * a
        self.display["bp_sys"] = self.display["bp_sys"] * (1 - a) + self.bp_sys * a
        self.display["bp_dia"] = self.display["bp_dia"] * (1 - a) + self.bp_dia * a
        self.display["bp_map"] = self.display["bp_map"] * (1 - a) + self.bp_map * a
        self.display["etco2"]  = self.display["etco2"]  * (1 - a) + self.etco2 * a
        # Temp drifts slowly regardless
        self.display["temp"]   = self.display["temp"]   * (1 - 0.06) + self.temp * 0.06

    def update_vitals(self):
        """Call once per frame to drift vital signs naturally."""
        if "[Arrest] VFib" in self.ecg_rhythm or "[Arrest] Asystole" in self.ecg_rhythm or "[Arrest] PEA" in self.ecg_rhythm or "[Vent] VFib" in self.ecg_rhythm or "[Vent] Torsades" in self.ecg_rhythm:
            if "PEA" not in self.ecg_rhythm:
                self.hr = max(0.0, self.hr - 20.0 * self.dt) # Slow decay of internal HR
            else:
                self.hr = self._drift(self.hr, "hr")
            self.spo2 = max(0.0, self.spo2 - 2.0 * self.dt) # Hypoxia develops over time
            self.rr = max(0.0, self.rr - 5.0 * self.dt)
            self.bp_sys = max(20.0, self.bp_sys - 10.0 * self.dt)
            self.bp_dia = max(10.0, self.bp_dia - 10.0 * self.dt)
            self.etco2 = max(0.0, self.etco2 - 5.0 * self.dt)
        else:
            self.hr = self._drift(self.hr, "hr")
            self.spo2 = self._drift(self.spo2, "spo2")
            
            # Respiratory overrides
            if self.resp_pattern == "Tachypnea":
                self.rr = 35.0 + random.gauss(0, 0.5)
            elif self.resp_pattern == "Bradypnea":
                self.rr = 6.0 + random.gauss(0, 0.2)
            elif self.resp_pattern == "Kussmaul":
                self.rr = 32.0 + random.gauss(0, 0.5)
            elif self.resp_pattern == "Apnea":
                self.rr = 0.0
            elif self.resp_pattern == "Cheyne-Stokes":
                if (self._resp_time % 45.0) > 30.0:
                    self.rr = 0.0
                else:
                    self.rr = 18.0 + random.gauss(0, 0.5)
            else:
                self.rr = self._drift(self.rr, "rr")
                
            self.bp_sys = self._drift(self.bp_sys, "bp_sys")
            self.bp_dia = self._drift(self.bp_dia, "bp_dia")
            self.etco2 = self._drift(self.etco2, "etco2")

            if self.rr > 24.0:
                self.etco2 = max(5.0, self.etco2 - (self.rr - 24.0) * 0.025 * self.dt)
            elif 0.0 < self.rr < 10.0:
                self.etco2 = min(90.0, self.etco2 + (10.0 - self.rr) * 0.02 * self.dt)
            
            # --- CASCADING PHYSIOLOGY ---
            # 1. Low RR -> Low SpO2 (Hypoxia)
            if self.rr < 8.0:
                # SpO2 drops proportionally to how low RR is
                drop_rate = (8.0 - self.rr) * 0.15 # Max ~1.2%/sec drop
                self.spo2 = max(20.0, self.spo2 - drop_rate * self.dt)
            elif self.rr > 10.0 and self.spo2 < 98.0:
                # Recover SpO2 if breathing normally
                self.spo2 = min(100.0, self.spo2 + 0.3 * self.dt)

            # 2. Low SpO2 -> High HR (Tachycardia)
            if self.spo2 < 90.0:
                # HR increases as SpO2 falls (Sympathetic response)
                tachy_boost = (90.0 - self.spo2) * 1.5
                self.hr = min(220.0, self.hr + tachy_boost * self.dt)
            
            # 3. Critical Failure -> Asystole
            if self.spo2 < 40.0:
                 # Terminal bradycardia sets in
                 self.hr = max(0.0, self.hr - 15.0 * self.dt)
                 if self.hr < 15.0 and self.ecg_rhythm != "[Arrest] Asystole":
                      self.ecg_rhythm = "[Arrest] Asystole"

        self.bp_map = self.bp_dia + (self.bp_sys - self.bp_dia) / 3.0
        self.temp = self._drift(self.temp, "temp")
        
        # --- Arrhythmia Detection ---
        self.hr_irregular = False
        if any(name in self.ecg_rhythm for name in ("AFib", "PACs", "PVCs", "Bigeminy", "Trigeminy", "Arrhythmia")):
            self.hr_irregular = True
        if "Block" in self.ecg_rhythm or "Torsades" in self.ecg_rhythm:
            self.hr_irregular = True
        if "VFib" in self.ecg_rhythm and "warning" in self.ecg_rhythm: # For early warning
            self.hr_irregular = True

        # Enforce physical BP limits (diastolic can never be higher than systolic)
        if self.bp_dia >= self.bp_sys - 5.0:
            self.bp_dia = max(10.0, self.bp_sys - 5.0)
            
        self._smooth_display()

    # ──── ECG Waveform Generators ────

    def _ecg_normal(self, phase):
        """Standard Lead II: P-QRS-T complex."""
        v = self.variation_factor
        p   =  0.12 * np.exp(-((phase - 0.12)**2) / (2 * 0.015**2))
        q   = -0.06 * np.exp(-((phase - 0.36)**2) / (2 * 0.004**2))
        r   =  1.00 * v * np.exp(-((phase - 0.38)**2) / (2 * 0.004**2))
        s   = -0.18 * v * np.exp(-((phase - 0.40)**2) / (2 * 0.006**2))
        t_w =  0.22 * np.exp(-((phase - 0.62)**2) / (2 * 0.035**2))
        return p + q + r + s + t_w + random.gauss(0, 0.006)

    def _ecg_svt(self, phase):
        """Narrow-complex SVT: regular fast QRS with buried/retrograde P."""
        q   = -0.04 * np.exp(-((phase - 0.34)**2) / (2 * 0.004**2))
        r   =  0.95 * np.exp(-((phase - 0.36)**2) / (2 * 0.0035**2))
        s   = -0.14 * np.exp(-((phase - 0.385)**2) / (2 * 0.005**2))
        retro_p = -0.045 * np.exp(-((phase - 0.46)**2) / (2 * 0.010**2))
        t_w = 0.12 * np.exp(-((phase - 0.62)**2) / (2 * 0.030**2))
        return q + r + s + retro_p + t_w + random.gauss(0, 0.006)

    def _ecg_junctional(self, phase):
        """Junctional rhythm: narrow QRS with absent/retrograde P waves."""
        retro_p = -0.08 * np.exp(-((phase - 0.25)**2) / (2 * 0.014**2))
        q = -0.05 * np.exp(-((phase - 0.36)**2) / (2 * 0.004**2))
        r = 0.90 * np.exp(-((phase - 0.38)**2) / (2 * 0.0045**2))
        s = -0.14 * np.exp(-((phase - 0.40)**2) / (2 * 0.006**2))
        t_w = 0.18 * np.exp(-((phase - 0.62)**2) / (2 * 0.035**2))
        return retro_p + q + r + s + t_w + random.gauss(0, 0.006)

    def _ecg_pac_beat(self, phase):
        """Premature atrial beat: early abnormal P, narrow QRS."""
        p = 0.14 * np.exp(-((phase - 0.055)**2) / (2 * 0.014**2))
        q = -0.045 * np.exp(-((phase - 0.30)**2) / (2 * 0.004**2))
        r = 0.88 * np.exp(-((phase - 0.32)**2) / (2 * 0.004**2))
        s = -0.13 * np.exp(-((phase - 0.34)**2) / (2 * 0.006**2))
        t_w = 0.18 * np.exp(-((phase - 0.58)**2) / (2 * 0.035**2))
        return p + q + r + s + t_w + random.gauss(0, 0.008)

    def _ecg_afib(self, phase):
        """Atrial fibrillation: no P-wave, fibrillatory baseline."""
        q   = -0.06 * np.exp(-((phase - 0.36)**2) / (2 * 0.004**2))
        r   =  1.00 * np.exp(-((phase - 0.38)**2) / (2 * 0.004**2))
        s   = -0.18 * np.exp(-((phase - 0.40)**2) / (2 * 0.006**2))
        t_w =  0.20 * np.exp(-((phase - 0.62)**2) / (2 * 0.035**2))
        fib_baseline = random.gauss(0, 0.025)
        return q + r + s + t_w + fib_baseline

    def _ecg_pvc_beat(self, phase):
        """Wide bizarre QRS for a premature ventricular contraction."""
        r   = -0.85 * np.exp(-((phase - 0.35)**2) / (2 * 0.014**2))
        s   =  0.55 * np.exp(-((phase - 0.48)**2) / (2 * 0.012**2))
        t_w = -0.30 * np.exp(-((phase - 0.68)**2) / (2 * 0.04**2))
        return r + s + t_w + random.gauss(0, 0.015)

    def _ecg_multifocal_pvc_beat(self, phase):
        """Alternate PVC morphology for patterned ectopy."""
        r = 0.72 * np.exp(-((phase - 0.31)**2) / (2 * 0.018**2))
        s = -0.95 * np.exp(-((phase - 0.46)**2) / (2 * 0.016**2))
        t_w = 0.28 * np.exp(-((phase - 0.70)**2) / (2 * 0.045**2))
        return r + s + t_w + random.gauss(0, 0.018)

    def _ecg_vtach(self, phase):
        """Ventricular tachycardia: wide, regular, monomorphic."""
        r   =  0.9 * np.exp(-((phase - 0.30)**2) / (2 * 0.018**2))
        s   = -0.7 * np.exp(-((phase - 0.50)**2) / (2 * 0.016**2))
        t_w =  0.3 * np.exp(-((phase - 0.75)**2) / (2 * 0.04**2))
        return r + s + t_w + random.gauss(0, 0.02)

    def _ecg_vfib(self):
        """Ventricular fibrillation: chaotic, no recognizable pattern."""
        self._vfib_t += self.dt * 7.0
        t = self._vfib_t
        return (0.3 * np.sin(t * 4.7) + 0.2 * np.sin(t * 6.3) +
                0.1 * np.sin(t * 11.1) + random.gauss(0, 0.08))

    def _ecg_asystole(self):
        """Asystole: flatline with slight baseline noise."""
        return random.gauss(0, 0.01)

    def _ecg_aflutter(self, phase):
        f_rate = 300.0 / max(1.0, self.hr)
        f_wave = 0.15 * np.sin(phase * 2 * np.pi * f_rate)
        q = -0.06 * np.exp(-((phase - 0.36)**2) / (2 * 0.004**2))
        r = 1.00 * np.exp(-((phase - 0.38)**2) / (2 * 0.004**2))
        s = -0.18 * np.exp(-((phase - 0.40)**2) / (2 * 0.006**2))
        return f_wave + q + r + s + random.gauss(0, 0.005)

    def _ecg_torsades(self, phase):
        """Torsades de Pointes: chaotic twisting VTach."""
        self._vfib_t += self.dt * (3.5 + random.uniform(-0.5, 0.5))
        # Twisting amplitude envelope
        env = 0.6 + 0.4 * np.sin(self._vfib_t * 0.35)
        # Add asymmetry and chaotic phase shifts
        chaos = 0.1 * np.sin(self._vfib_t * 1.7) + random.uniform(-0.05, 0.05)
        local_phase = (self._vfib_t * 1.5 + chaos) % 1.0
        
        r = env * (0.8 + random.uniform(0, 0.2)) * np.exp(-((local_phase - 0.30)**2) / (2 * 0.022**2))
        s = -env * (0.6 + random.uniform(0, 0.2)) * np.exp(-((local_phase - 0.50)**2) / (2 * 0.020**2))
        return r + s + random.gauss(0, 0.03)

    def _ecg_1st_deg(self, phase):
        # Increased PR interval (delay) from 0.33 to ~0.50
        p = 0.12 * np.exp(-((phase - 0.02)**2) / (2 * 0.015**2))
        q = -0.06 * np.exp(-((phase - 0.48)**2) / (2 * 0.004**2))
        r = 1.00 * np.exp(-((phase - 0.50)**2) / (2 * 0.004**2))
        s = -0.18 * np.exp(-((phase - 0.52)**2) / (2 * 0.006**2))
        t_w = 0.22 * np.exp(-((phase - 0.75)**2) / (2 * 0.035**2))
        return p + q + r + s + t_w + random.gauss(0, 0.006)

    def _ecg_wenckebach(self, phase):
        beat = self._beat_counter % 4
        if beat == 3:
            p = 0.12 * np.exp(-((phase - 0.12)**2) / (2 * 0.015**2))
            return p + random.gauss(0, 0.006)
        p_offset = 0.12 - (beat * 0.05)
        p = 0.12 * np.exp(-((phase - p_offset)**2) / (2 * 0.015**2))
        q = -0.06 * np.exp(-((phase - 0.36)**2) / (2 * 0.004**2))
        r = 1.00 * np.exp(-((phase - 0.38)**2) / (2 * 0.004**2))
        s = -0.18 * np.exp(-((phase - 0.40)**2) / (2 * 0.006**2))
        t_w = 0.22 * np.exp(-((phase - 0.62)**2) / (2 * 0.035**2))
        return p + q + r + s + t_w + random.gauss(0, 0.006)

    def _ecg_3rd_deg(self, phase):
        p_phase = (self._resp_time * (60.0 / 60.0)) % 1.0
        p = 0.12 * np.exp(-((p_phase - 0.12)**2) / (2 * 0.015**2))
        r = -0.6 * np.exp(-((phase - 0.35)**2) / (2 * 0.014**2))
        s = 0.5 * np.exp(-((phase - 0.48)**2) / (2 * 0.012**2))
        t_w = -0.2 * np.exp(-((phase - 0.68)**2) / (2 * 0.04**2))
        return p + r + s + t_w + random.gauss(0, 0.006)

    def _ecg_mobitz2(self, phase):
        p = 0.12 * np.exp(-((phase - 0.10)**2) / (2 * 0.015**2))
        if self._beat_counter % 4 == 3:
            return p + random.gauss(0, 0.006)
        q = -0.06 * np.exp(-((phase - 0.38)**2) / (2 * 0.004**2))
        r = 1.0 * np.exp(-((phase - 0.40)**2) / (2 * 0.004**2))
        s = -0.18 * np.exp(-((phase - 0.42)**2) / (2 * 0.006**2))
        t_w = 0.22 * np.exp(-((phase - 0.64)**2) / (2 * 0.035**2))
        return p + q + r + s + t_w + random.gauss(0, 0.006)

    def _ecg_rbbb(self, phase):
        p = 0.11 * np.exp(-((phase - 0.12)**2) / (2 * 0.015**2))
        q = -0.05 * np.exp(-((phase - 0.33)**2) / (2 * 0.006**2))
        r = 0.72 * np.exp(-((phase - 0.36)**2) / (2 * 0.008**2))
        late_r = 0.42 * np.exp(-((phase - 0.43)**2) / (2 * 0.011**2))
        s = -0.22 * np.exp(-((phase - 0.49)**2) / (2 * 0.018**2))
        t_w = -0.12 * np.exp(-((phase - 0.68)**2) / (2 * 0.04**2))
        return p + q + r + late_r + s + t_w + random.gauss(0, 0.007)

    def _ecg_lbbb(self, phase):
        p = 0.10 * np.exp(-((phase - 0.12)**2) / (2 * 0.015**2))
        r1 = 0.45 * np.exp(-((phase - 0.37)**2) / (2 * 0.012**2))
        r2 = 0.78 * np.exp(-((phase - 0.46)**2) / (2 * 0.018**2))
        s = -0.16 * np.exp(-((phase - 0.55)**2) / (2 * 0.018**2))
        t_w = -0.16 * np.exp(-((phase - 0.72)**2) / (2 * 0.045**2))
        return p + r1 + r2 + s + t_w + random.gauss(0, 0.007)

    def _ecg_wpw(self, phase):
        p = 0.12 * np.exp(-((phase - 0.08)**2) / (2 * 0.015**2))
        delta = 0.18 * np.exp(-((phase - 0.30)**2) / (2 * 0.030**2))
        q = -0.035 * np.exp(-((phase - 0.34)**2) / (2 * 0.006**2))
        r = 0.92 * np.exp(-((phase - 0.38)**2) / (2 * 0.007**2))
        s = -0.18 * np.exp(-((phase - 0.43)**2) / (2 * 0.012**2))
        t_w = 0.18 * np.exp(-((phase - 0.64)**2) / (2 * 0.038**2))
        return p + delta + q + r + s + t_w + random.gauss(0, 0.006)

    def _ecg_long_qt(self, phase):
        p = 0.12 * np.exp(-((phase - 0.12)**2) / (2 * 0.015**2))
        q = -0.06 * np.exp(-((phase - 0.34)**2) / (2 * 0.004**2))
        r = 1.0 * np.exp(-((phase - 0.36)**2) / (2 * 0.004**2))
        s = -0.16 * np.exp(-((phase - 0.38)**2) / (2 * 0.006**2))
        t_w = 0.24 * np.exp(-((phase - 0.82)**2) / (2 * 0.060**2))
        return p + q + r + s + t_w + random.gauss(0, 0.006)

    def _ecg_hyperkalemia(self, phase):
        p = 0.04 * np.exp(-((phase - 0.12)**2) / (2 * 0.017**2))
        qrs = 0.82 * np.exp(-((phase - 0.38)**2) / (2 * 0.012**2))
        s = -0.22 * np.exp(-((phase - 0.43)**2) / (2 * 0.014**2))
        peaked_t = 0.62 * np.exp(-((phase - 0.62)**2) / (2 * 0.022**2))
        return p + qrs + s + peaked_t + random.gauss(0, 0.008)

    def _ecg_stemi(self, phase, inferior=False):
        base = self._ecg_normal(phase)
        st = 0.12 if 0.43 <= phase <= 0.60 else 0.0
        reciprocal = -0.04 if inferior and 0.43 <= phase <= 0.60 else 0.0
        return base + st + reciprocal + random.gauss(0, 0.004)

    def _get_ecg_point(self, phase):
        """Dispatch to the active rhythm's ECG generator."""
        if not self._safety_verified:
            return random.gauss(0, 0.01) # Flatline if tampered
            
        rhythm = self.ecg_rhythm
        if rhythm in ("[Norm] Sinus Rhythm", "[Sinus] Bradycardia", "[Sinus] Tachycardia", "[Sinus] Arrhythmia", "[Sinus] IST"):
            return self._ecg_normal(phase)
        elif rhythm == "[Atrial] SVT":
            return self._ecg_svt(phase)
        elif rhythm == "[Atrial] AFib":
            return self._ecg_afib(phase)
        elif rhythm == "[Atrial] AFlutter":
            return self._ecg_aflutter(phase)
        elif rhythm == "[Atrial] PACs":
            if self._in_pac:
                return self._ecg_pac_beat(phase)
            return self._ecg_normal(phase)
        elif rhythm in ("[Junctional] Rhythm", "[Junctional] Accelerated"):
            return self._ecg_junctional(phase)
        elif rhythm in ("[Vent] PVCs", "[Vent] Bigeminy", "[Vent] Trigeminy"):
            if self._in_pvc:
                if rhythm == "[Vent] Trigeminy" and self._beat_counter % 2 == 0:
                    return self._ecg_multifocal_pvc_beat(phase)
                return self._ecg_pvc_beat(phase)
            return self._ecg_normal(phase)
        elif rhythm == "[Vent] VTach":
            return self._ecg_vtach(phase)
        elif rhythm == "[Vent] VFib":
            return self._ecg_vfib()
        elif rhythm == "[Vent] Torsades":
            return self._ecg_torsades(phase)
        elif rhythm == "[Block] 1st Deg AV":
            return self._ecg_1st_deg(phase)
        elif rhythm == "[Block] Wenckebach":
            return self._ecg_wenckebach(phase)
        elif rhythm == "[Block] Mobitz II":
            return self._ecg_mobitz2(phase)
        elif rhythm == "[Block] 3rd Deg AV":
            return self._ecg_3rd_deg(phase)
        elif rhythm == "[Block] RBBB":
            return self._ecg_rbbb(phase)
        elif rhythm == "[Block] LBBB":
            return self._ecg_lbbb(phase)
        elif rhythm == "[Preexcitation] WPW":
            return self._ecg_wpw(phase)
        elif rhythm == "[Repol] Long QT":
            return self._ecg_long_qt(phase)
        elif rhythm == "[Repol] Hyperkalemia":
            return self._ecg_hyperkalemia(phase)
        elif rhythm == "[Ischemia] Anterior STEMI":
            return self._ecg_stemi(phase)
        elif rhythm == "[Ischemia] Inferior STEMI":
            return self._ecg_stemi(phase, inferior=True)
        elif rhythm == "[Arrest] Asystole":
            return self._ecg_asystole()
        elif rhythm == "[Arrest] PEA":
            return self._ecg_normal(phase)
        return self._ecg_normal(phase)

    def _effective_hr(self):
        rhythm = self.ecg_rhythm
        hr = max(0.0, self.hr)
        if rhythm == "[Sinus] Bradycardia":
            return min(60.0, max(35.0, hr))
        if rhythm == "[Sinus] Tachycardia":
            return min(165.0, max(105.0, hr))
        if rhythm == "[Sinus] IST":
            return min(150.0, max(105.0, hr))
        if rhythm == "[Atrial] SVT":
            return min(230.0, max(170.0, hr))
        if rhythm == "[Junctional] Rhythm":
            return min(70.0, max(40.0, hr))
        if rhythm == "[Junctional] Accelerated":
            return min(115.0, max(70.0, hr))
        if rhythm == "[Block] 3rd Deg AV":
            return min(48.0, max(28.0, hr))
        if rhythm == "[Vent] VTach":
            return min(240.0, max(160.0, hr))
        if rhythm == "[Vent] Torsades":
            return min(250.0, max(180.0, hr))
        return hr

    def _qrs_suppressed_this_cycle(self):
        rhythm = self.ecg_rhythm
        if rhythm == "[Block] Wenckebach" and self._beat_counter % 4 == 3:
            return True
        if rhythm == "[Block] Mobitz II" and self._beat_counter % 4 == 3:
            return True
        return False

    def _derive_ecg_leads(self, base, phase):
        """Approximate a 12-lead set from the active rhythm's primary ECG."""
        p = np.exp(-((phase - 0.12)**2) / (2 * 0.018**2))
        r = np.exp(-((phase - 0.38)**2) / (2 * 0.006**2))
        s = np.exp(-((phase - 0.41)**2) / (2 * 0.010**2))
        t_w = np.exp(-((phase - 0.62)**2) / (2 * 0.045**2))

        profiles = {
            "I":   (0.70,  0.02,  0.05, -0.02,  0.02),
            "II":  (1.00,  0.00,  0.00,  0.00,  0.00),
            "III": (0.42, -0.02, -0.08,  0.04, -0.01),
            "aVR": (-0.58, -0.02, -0.08,  0.03, -0.03),
            "aVL": (0.45,  0.02,  0.08, -0.03,  0.02),
            "aVF": (0.78,  0.00,  0.02,  0.00,  0.01),
            "V1":  (-0.35, -0.01, -0.48,  0.24, -0.04),
            "V2":  (-0.08,  0.00, -0.28,  0.18,  0.02),
            "V3":  (0.42,  0.01,  0.06, -0.04,  0.06),
            "V4":  (0.92,  0.02,  0.18, -0.08,  0.07),
            "V5":  (0.82,  0.02,  0.14, -0.06,  0.05),
            "V6":  (0.62,  0.01,  0.09, -0.04,  0.03),
        }

        leads = {}
        for lead, (gain, p_adj, r_adj, s_adj, t_adj) in profiles.items():
            leads[lead] = gain * base + p_adj * p + r_adj * r + s_adj * s + t_adj * t_w

        rhythm = self.ecg_rhythm
        if rhythm == "[Block] RBBB":
            late_r = np.exp(-((phase - 0.45)**2) / (2 * 0.016**2))
            wide_s = np.exp(-((phase - 0.49)**2) / (2 * 0.020**2))
            for lead in ("V1", "V2"):
                leads[lead] += 0.62 * late_r
            for lead in ("I", "aVL", "V5", "V6"):
                leads[lead] -= 0.34 * wide_s
        elif rhythm == "[Block] LBBB":
            broad_r = np.exp(-((phase - 0.46)**2) / (2 * 0.030**2))
            deep_s = np.exp(-((phase - 0.42)**2) / (2 * 0.026**2))
            discordant_t = np.exp(-((phase - 0.72)**2) / (2 * 0.060**2))
            for lead in ("I", "aVL", "V5", "V6"):
                leads[lead] += 0.55 * broad_r - 0.20 * discordant_t
            for lead in ("V1", "V2", "V3"):
                leads[lead] -= 0.72 * deep_s + 0.22 * discordant_t
        elif rhythm == "[Preexcitation] WPW":
            delta = np.exp(-((phase - 0.30)**2) / (2 * 0.030**2))
            for lead in ("I", "II", "aVL", "V4", "V5", "V6"):
                leads[lead] += 0.16 * delta
            for lead in ("III", "aVF", "V1"):
                leads[lead] -= 0.10 * delta
        elif rhythm == "[Repol] Long QT":
            late_t = np.exp(-((phase - 0.82)**2) / (2 * 0.070**2))
            for lead in ("I", "II", "V3", "V4", "V5", "V6"):
                leads[lead] += 0.12 * late_t
            leads["aVR"] -= 0.10 * late_t
        elif rhythm == "[Repol] Hyperkalemia":
            peaked_t = np.exp(-((phase - 0.62)**2) / (2 * 0.020**2))
            for lead in ECG_LEADS:
                leads[lead] += 0.24 * peaked_t
            leads["aVR"] -= 0.12 * peaked_t
        elif rhythm == "[Ischemia] Anterior STEMI":
            st = 1.0 if 0.43 <= phase <= 0.62 else 0.0
            for lead in ("V2", "V3", "V4"):
                leads[lead] += 0.22 * st
            for lead in ("II", "III", "aVF"):
                leads[lead] -= 0.08 * st
        elif rhythm == "[Ischemia] Inferior STEMI":
            st = 1.0 if 0.43 <= phase <= 0.62 else 0.0
            for lead in ("II", "III", "aVF"):
                leads[lead] += 0.20 * st
            for lead in ("I", "aVL", "V2"):
                leads[lead] -= 0.08 * st
        return leads

    def _consolidated_ecg(self, leads):
        """Computer-combined clean ECG derived from the full 12-lead body signal."""
        weights = {
            "I": 0.55, "II": 1.0, "III": 0.45,
            "aVR": -0.35, "aVL": 0.35, "aVF": 0.65,
            "V1": -0.18, "V2": 0.12, "V3": 0.45,
            "V4": 0.85, "V5": 0.75, "V6": 0.55,
        }
        total_w = sum(abs(w) for w in weights.values())
        combined = sum(leads[lead] * weight for lead, weight in weights.items()) / total_w
        return combined * 1.65

    def _apply_lead_artifacts(self, leads):
        """Add monitor-side ECG lead noise, motion, mains pickup, and pop-off bumps."""
        if not self.enable_lead_artifacts or self.lead_artifact_level <= 0:
            return dict(leads)

        level = self.lead_artifact_level
        t = self._artifact_time
        if t > self._motion_burst_until and random.random() < self.dt * level * 0.55:
            self._motion_burst_until = t + random.uniform(0.25, 1.4)

        artifacted = {}
        common_wander = (
            np.sin(2 * np.pi * 0.22 * t) * (0.035 + 0.08 * level) +
            np.sin(2 * np.pi * 0.047 * t + 1.4) * (0.015 + 0.035 * level)
        )
        mains = np.sin(2 * np.pi * 60.0 * t) * 0.012 * level
        motion = random.gauss(0, 0.18 * level) if t < self._motion_burst_until else 0.0

        for i, lead in enumerate(ECG_LEADS):
            if t > self._lead_pop_until[lead] and random.random() < self.dt * level * 0.025:
                self._lead_pop_until[lead] = t + random.uniform(0.18, 0.9)
                self._lead_pop_value[lead] = random.choice([-1.0, 1.0]) * random.uniform(0.25, 0.85) * level

            pop = self._lead_pop_value[lead] if t < self._lead_pop_until[lead] else 0.0
            lead_factor = 0.75 + (i % 4) * 0.12
            muscle = random.gauss(0, (0.008 + 0.055 * level) * lead_factor)
            artifacted[lead] = leads[lead] + common_wander * lead_factor + mains + motion + pop + muscle
        return artifacted

    # ──── Other Waveforms ────

    def _pleth_point(self, ecg_phase):
        if "VFib" in self.ecg_rhythm or "Asystole" in self.ecg_rhythm or "PEA" in self.ecg_rhythm or "Torsades" in self.ecg_rhythm:
            return random.gauss(0, 0.01)
        p = (ecg_phase - 0.18) % 1.0
        v = self.pleth_variation
        systolic = 0.7 * v * np.exp(-((p - 0.35)**2) / (2 * 0.06**2))
        notch    = 0.22 * v * np.exp(-((p - 0.52)**2) / (2 * 0.03**2))
        return (systolic + notch) * (self.spo2 / 100.0)

    def _resp_point(self, phase):
        if self.resp_pattern == "Apnea":
            return 0.0
            
        amp = 0.5
        if self.resp_pattern == "Hyperpnea" or self.resp_pattern == "Kussmaul":
            amp = 0.85
        elif self.resp_pattern == "Tachypnea":
            amp = 0.4
        elif self.resp_pattern == "Cheyne-Stokes":
            cycle = self._resp_time % 45.0
            if cycle > 30.0:
                amp = 0.0  # Apnea phase
            else:
                amp = 0.6 * np.sin(np.pi * cycle / 30.0)
        elif self.resp_pattern == "Biot":
            cycle = self._resp_time % 20.0
            if cycle > 10.0:
                amp = 0.0
        elif self.resp_pattern == "Irregular":
            amp = 0.5 * (0.6 + 0.4 * np.sin(self._resp_time * 0.3) + 0.2 * np.cos(self._resp_time * 0.77))
            
        if phase < 0.4:
            return amp * self.resp_variation * np.sin(np.pi * phase / 0.4)
        else:
            return amp * self.resp_variation * np.sin(np.pi * (1.0 - (phase - 0.4) / 0.6))

    def _abp_point(self, ecg_phase):
        if "VFib" in self.ecg_rhythm or "Asystole" in self.ecg_rhythm or "PEA" in self.ecg_rhythm or "Torsades" in self.ecg_rhythm:
            # Pressure drops to a low flat line
            return 20.0 + random.gauss(0, 1.0)
        p = (ecg_phase - 0.15) % 1.0
        sys_range = self.bp_sys - self.bp_dia
        systolic = np.exp(-((p - 0.25)**2) / (2 * 0.04**2))
        notch    = 0.35 * np.exp(-((p - 0.42)**2) / (2 * 0.02**2))
        runoff   = 0.15 * np.exp(-((p - 0.55)**2) / (2 * 0.08**2))
        return self.bp_dia + (systolic + notch + runoff) * sys_range * 0.7

    def _co2_point(self, phase):
        if not self.probe_etco2:
            return 2.0
            
        if self.resp_pattern == "Apnea":
            return 2.0
        if self.resp_pattern == "Cheyne-Stokes":
            if (self._resp_time % 45.0) > 30.0:
                return 2.0
                
        if phase < 0.35:
            return 2.0
        elif phase < 0.42:
            t = (phase - 0.35) / 0.07
            return 2.0 + t * ((self.etco2 * self.etco2_breath_variation) - 2.0)
        elif phase < 0.85:
            plateau = self.etco2 * self.etco2_breath_variation
            return plateau + 0.4 * np.sin(phase * 18.0) + random.gauss(0, 0.25)
        elif phase < 0.92:
            t = (phase - 0.85) / 0.07
            plateau = self.etco2 * self.etco2_breath_variation
            return plateau * (1.0 - t) + 2.0 * t
        else:
            return 2.0

    # ──── Main Step ────

    def step(self, seconds):
        self.point_accum += seconds * self.sample_rate
        num_points = int(self.point_accum)
        self.point_accum -= num_points

        ecg_out, pleth_out, resp_out, abp_out, co2_out = [], [], [], [], []
        ecg_leads_out = {lead: [] for lead in ECG_LEADS}
        pure_out = {"ecg": [], "pleth": [], "resp": [], "abp": [], "co2": []}
        gate_out = {"r_gate": [], "co2_gate": [], "resp_insp": []}
        self.r_wave_detected = False

        for _ in range(num_points):
            self._resp_time += self.dt
            self._artifact_time += self.dt
            # --- Phase advancement (rhythm-dependent) ---
            hr_rate = (self._effective_hr() / 60.0) * self.dt

            if "AFib" in self.ecg_rhythm:
                hr_rate *= self._afib_rr_mod
            elif "PACs" in self.ecg_rhythm and self._in_pac:
                hr_rate *= 1.35
            elif "PVCs" in self.ecg_rhythm and self._in_pvc:
                hr_rate *= 1.25
            elif "Bigeminy" in self.ecg_rhythm or "Trigeminy" in self.ecg_rhythm:
                if self._in_pvc:
                    hr_rate *= 1.20
            elif "Sinus] Arrhythmia" in self.ecg_rhythm:
                hr_rate *= self._sinus_arrhythmia_mod
            elif "AFlutter" in self.ecg_rhythm:
                hr_rate = (self._aflutter_hr / 60.0) * self.dt
            elif "VTach" in self.ecg_rhythm:
                hr_rate = (self._effective_hr() / 60.0) * self.dt
            elif "VFib" in self.ecg_rhythm or "Asystole" in self.ecg_rhythm or "Torsades" in self.ecg_rhythm:
                hr_rate = 0.0  # Doesn't use standard phase advancement

            old_phase = self.phase_ecg
            self.phase_ecg += hr_rate

            # Beat boundary detection (phase wraps past 1.0)
            if self.phase_ecg >= 1.0:
                self.phase_ecg -= 1.0
                self._on_new_beat()

            # Respiration phase
            self.phase_resp += (self.rr / 60.0) * self.dt
            if self.phase_resp >= 1.0:
                self.phase_resp -= 1.0
                self.resp_variation = random.uniform(0.85, 1.15)
                spread = max(0.0, min(0.35, self.etco2_variability))
                self.etco2_breath_variation = random.uniform(1.0 - spread, 1.0 + spread)

            # Generate ECG
            ecg_body = self._get_ecg_point(self.phase_ecg)
            lead_body = self._derive_ecg_leads(ecg_body, self.phase_ecg)
            display_lead = self.ecg_display_lead if self.ecg_display_lead in ECG_DISPLAY_LEADS else "Clean"
            clean_ecg = self._consolidated_ecg(lead_body)
            ecg_val = clean_ecg if display_lead == "Clean" else lead_body[display_lead]
            pleth_body = self._pleth_point(self.phase_ecg)
            resp_body = self._resp_point(self.phase_resp)
            abp_body = self._abp_point(self.phase_ecg)
            co2_body = self._co2_point(self.phase_resp)

            # R-wave detection (phase crossing)
            r_peak_phase = 0.38
            if "PVCs" in self.ecg_rhythm and self._in_pvc:
                r_peak_phase = 0.35
            elif ("Bigeminy" in self.ecg_rhythm or "Trigeminy" in self.ecg_rhythm) and self._in_pvc:
                r_peak_phase = 0.35
            elif "PACs" in self.ecg_rhythm and self._in_pac:
                r_peak_phase = 0.32
            elif "VTach" in self.ecg_rhythm:
                r_peak_phase = 0.30
            elif "3rd Deg" in self.ecg_rhythm:
                r_peak_phase = 0.35
            elif "1st Deg" in self.ecg_rhythm:
                r_peak_phase = 0.50
            elif "Mobitz II" in self.ecg_rhythm:
                r_peak_phase = 0.40
            
            # If phase just crossed the peak (and didn't wrap around in the same step)
            r_crossed = old_phase < r_peak_phase <= self.phase_ecg
            if self._qrs_suppressed_this_cycle():
                r_crossed = False
            if r_crossed:
                self.r_wave_detected = True
                self._r_gate_until = self._artifact_time + 0.045

            # --- Calibration Noise Logic ---
            if self.cal_time > 0:
                # Starting at 0 with jerking/noise that slowly settles
                progress = 1.0 - (self.cal_time / 6.0) # 0 to 1
                noise_amp = 0.0
                if progress < 0.8:
                    # Random jerks/spikes
                    if random.random() < 0.02:
                        noise_amp = random.uniform(-0.8, 0.8)
                    elif random.random() < 0.1:
                        noise_amp = random.uniform(-0.1, 0.1)
                
                # Blend noise with actual signal based on progress
                # 0-3s: mostly noise/0, 3-6s: transition to real signal
                blend = max(0.0, (progress - 0.5) * 2.0)
                
                sensor_leads = {
                    lead: val * blend + (noise_amp * (0.85 + i * 0.03)) * (1.0 - blend)
                    for i, (lead, val) in enumerate(lead_body.items())
                }
                pleth_val = pleth_body * blend + (noise_amp * 0.2) * (1.0 - blend)
                resp_val = resp_body * blend + (noise_amp * 0.1) * (1.0 - blend)
                abp_val = abp_body * blend + (noise_amp * 10.0) * (1.0 - blend)
                co2_val = co2_body * blend + (noise_amp * 2.0) * (1.0 - blend)
            else:
                sensor_leads = dict(lead_body)
                pleth_val = pleth_body
                resp_val = resp_body
                abp_val = abp_body
                co2_val = co2_body

            sensor_leads = self._apply_lead_artifacts(sensor_leads)
            ecg_val = clean_ecg if display_lead == "Clean" else sensor_leads[display_lead]

            ecg_out.append(ecg_val)
            pleth_out.append(pleth_val)
            resp_out.append(resp_val)
            abp_out.append(abp_val)
            co2_out.append(co2_val)
            for lead in ECG_LEADS:
                ecg_leads_out[lead].append(sensor_leads[lead])
            pure_out["ecg"].append(clean_ecg if display_lead == "Clean" else lead_body[display_lead])
            pure_out["pleth"].append(pleth_body)
            pure_out["resp"].append(resp_body)
            pure_out["abp"].append(abp_body)
            pure_out["co2"].append(co2_body)
            gate_out["r_gate"].append(1.0 if self._artifact_time < self._r_gate_until else 0.0)
            gate_out["co2_gate"].append(1.0 if self.probe_etco2 and 0.42 <= self.phase_resp < 0.85 else 0.0)
            gate_out["resp_insp"].append(1.0 if self.phase_resp < 0.4 and self.rr > 0 else 0.0)

        return {
            "ecg": ecg_out, "pleth": pleth_out, "resp": resp_out,
            "abp": abp_out, "co2": co2_out,
            "ecg_leads": ecg_leads_out,
            "pure": pure_out,
            "gates": gate_out,
        }

    def _on_new_beat(self):
        """Called when a new cardiac cycle begins (phase wraps)."""
        self._beat_counter += 1

        # AFib: pick a new random R-R modifier for the next beat
        if "AFib" in self.ecg_rhythm:
            self._afib_rr_mod = random.uniform(0.65, 1.45)

        # Sinus arrhythmia: respiratory-rate linked R-R variation.
        if "Sinus] Arrhythmia" in self.ecg_rhythm:
            self._sinus_arrhythmia_mod = 0.88 + 0.24 * max(0.0, np.sin(2 * np.pi * self.phase_resp))
            
        # AFlutter: variable AV block (ventricular rate changes)
        if "AFlutter" in self.ecg_rhythm:
            self._aflutter_hr = 300.0 / random.choice([2, 3, 4])

        if "[Atrial] PACs" in self.ecg_rhythm:
            if self._in_pac:
                self._in_pac = False
                self._pac_interval = random.randint(5, 12)
                self._beat_counter = 0
            elif self._beat_counter >= self._pac_interval:
                self._in_pac = True
        else:
            self._in_pac = False

        # PVCs: determine if next beat is a PVC
        if "[Vent] PVCs" in self.ecg_rhythm:
            if self._in_pvc:
                self._in_pvc = False
                self._pvc_interval = random.randint(4, 10)
                self._beat_counter = 0
            elif self._beat_counter >= self._pvc_interval:
                self._in_pvc = True
        elif "[Vent] Bigeminy" in self.ecg_rhythm:
            self._in_pvc = self._beat_counter % 2 == 0
        elif "[Vent] Trigeminy" in self.ecg_rhythm:
            self._in_pvc = self._beat_counter % 3 == 0
        elif "[Vent]" not in self.ecg_rhythm:
            self._in_pvc = False
        
        # Organic variability for next beat
        self.variation_factor = random.uniform(0.96, 1.04)
        self.pleth_variation = random.uniform(0.92, 1.08)

    def _verify_safety(self):
        """
        Deep entanglement check. 
        Reads monitor.py to ensure the mandatory legal disclaimer hasn't been altered.
        We scatter the checks across method definitions and specific strings to ensure 
        the structural integrity of the legal protection.
        In the case of this DEFITINON being deleted the program will not run.
        """
        try:
            import os
            import hashlib
            base_dir = os.path.dirname(__file__)
            monitor_path = os.path.join(base_dir, "monitor.py")
            with open(monitor_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Scattered strings across the monitor definitions
            required_strings = [
                "class MonitorDSP:",
                "def _draw_watermark(self):",
                "def _draw_disclaimer(self):",
                "NOT FOR MEDICAL USE — SIMULATION ONLY",
                "MANDATORY LEGAL & MEDICAL DISCLAIMER",
                "NEVER be used in a real clinical setting",
                "raise RuntimeError(\"SAFETY ERROR"
            ]
            
            if all(s in content for s in required_strings):
                self._safety_verified = True
            else:
                self._safety_verified = False
        except Exception:
            self._safety_verified = False
