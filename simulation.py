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

ECG_RHYTHMS = [
    "[Norm] Sinus Rhythm", "[Atrial] AFib", "[Atrial] AFlutter", 
    "[Vent] PVCs", "[Vent] VTach", "[Vent] VFib", "[Vent] Torsades", 
    "[Block] 1st Deg AV", "[Block] Wenckebach", "[Block] 3rd Deg AV", 
    "[Arrest] Asystole", "[Arrest] PEA"
]
RESP_PATTERNS = ["Eupnea (Normal)", "Hyperpnea", "Bradypnea", "Tachypnea", "Apnea", "Cheyne-Stokes", "Biot", "Kussmaul"]


class PhysioSim:
    def __init__(self, sample_rate=250):
        self.sample_rate = sample_rate
        self.dt = 1.0 / sample_rate

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
        self.ecg_rhythm = "Normal Sinus"
        self._beat_counter = 0
        self._pvc_interval = random.randint(4, 10)
        self._in_pvc = False
        self._afib_rr_mod = 1.0
        self._vfib_t = 0.0

        # --- Internal Phase Accumulators ---
        self.phase_ecg = 0.0
        self.phase_resp = 0.0
        self.point_accum = 0.0
        self._resp_time = 0.0

        # --- Features & Probes ---
        self.resp_pattern = "Regular"
        self.probe_etco2 = True
        self.probe_temp = True

        # --- R-wave detection for beep ---
        self.r_wave_detected = False
        self._prev_ecg = 0.0

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
                self.hr = 0.0
            else:
                self.hr = self._drift(self.hr, "hr")
            self.spo2 = 0.0
            self.rr = 0.0
            self.bp_sys *= 0.90
            self.bp_dia *= 0.90
            self.etco2 *= 0.90
        else:
            self.hr = self._drift(self.hr, "hr")
            self.spo2 = self._drift(self.spo2, "spo2")
            
            # Respiratory overrides
            if self.resp_pattern == "Tachypnea":
                self.rr = 35.0 + random.gauss(0, 0.5)
            elif self.resp_pattern == "Bradypnea":
                self.rr = 8.0 + random.gauss(0, 0.2)
            elif self.resp_pattern == "Kussmaul":
                self.rr = 28.0 + random.gauss(0, 0.5)
            elif self.resp_pattern == "Apnea":
                self.rr = 0.0
            else:
                self.rr = self._drift(self.rr, "rr")
                
            self.bp_sys = self._drift(self.bp_sys, "bp_sys")
            self.bp_dia = self._drift(self.bp_dia, "bp_dia")
            self.etco2 = self._drift(self.etco2, "etco2")

        self.bp_map = self.bp_dia + (self.bp_sys - self.bp_dia) / 3.0
        self.temp = self._drift(self.temp, "temp")
        self._smooth_display()

    # ──── ECG Waveform Generators ────

    def _ecg_normal(self, phase):
        """Standard Lead II: P-QRS-T complex."""
        p   =  0.12 * np.exp(-((phase - 0.12)**2) / (2 * 0.015**2))
        q   = -0.06 * np.exp(-((phase - 0.36)**2) / (2 * 0.004**2))
        r   =  1.00 * np.exp(-((phase - 0.38)**2) / (2 * 0.004**2))
        s   = -0.18 * np.exp(-((phase - 0.40)**2) / (2 * 0.006**2))
        t_w =  0.22 * np.exp(-((phase - 0.62)**2) / (2 * 0.035**2))
        return p + q + r + s + t_w + random.gauss(0, 0.006)

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
        self._vfib_t += self.dt * 2.0
        env = 0.6 + 0.4 * np.sin(self._vfib_t)
        r = env * 0.9 * np.exp(-((phase - 0.30)**2) / (2 * 0.018**2))
        s = -env * 0.7 * np.exp(-((phase - 0.50)**2) / (2 * 0.016**2))
        return r + s + random.gauss(0, 0.02)

    def _ecg_1st_deg(self, phase):
        p = 0.12 * np.exp(-((phase - 0.05)**2) / (2 * 0.015**2))
        q = -0.06 * np.exp(-((phase - 0.36)**2) / (2 * 0.004**2))
        r = 1.00 * np.exp(-((phase - 0.38)**2) / (2 * 0.004**2))
        s = -0.18 * np.exp(-((phase - 0.40)**2) / (2 * 0.006**2))
        t_w = 0.22 * np.exp(-((phase - 0.62)**2) / (2 * 0.035**2))
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

    def _get_ecg_point(self, phase):
        """Dispatch to the active rhythm's ECG generator."""
        rhythm = self.ecg_rhythm
        if rhythm == "[Norm] Sinus Rhythm":
            return self._ecg_normal(phase)
        elif rhythm == "[Atrial] AFib":
            return self._ecg_afib(phase)
        elif rhythm == "[Atrial] AFlutter":
            return self._ecg_aflutter(phase)
        elif rhythm == "[Vent] PVCs":
            if self._in_pvc:
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
        elif rhythm == "[Block] 3rd Deg AV":
            return self._ecg_3rd_deg(phase)
        elif rhythm == "[Arrest] Asystole":
            return self._ecg_asystole()
        elif rhythm == "[Arrest] PEA":
            return self._ecg_normal(phase)
        return self._ecg_normal(phase)

    # ──── Other Waveforms ────

    def _pleth_point(self, ecg_phase):
        if "VFib" in self.ecg_rhythm or "Asystole" in self.ecg_rhythm or "PEA" in self.ecg_rhythm or "Torsades" in self.ecg_rhythm:
            return random.gauss(0, 0.01)
        p = (ecg_phase - 0.18) % 1.0
        systolic = 0.7 * np.exp(-((p - 0.35)**2) / (2 * 0.06**2))
        notch    = 0.22 * np.exp(-((p - 0.52)**2) / (2 * 0.03**2))
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
            return amp * np.sin(np.pi * phase / 0.4)
        else:
            return amp * np.sin(np.pi * (1.0 - (phase - 0.4) / 0.6))

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
            return 2.0 + t * (self.etco2 - 2.0)
        elif phase < 0.85:
            return self.etco2 + random.gauss(0, 0.2)
        elif phase < 0.92:
            t = (phase - 0.85) / 0.07
            return self.etco2 * (1.0 - t) + 2.0 * t
        else:
            return 2.0

    # ──── Main Step ────

    def step(self, seconds):
        self.point_accum += seconds * self.sample_rate
        num_points = int(self.point_accum)
        self.point_accum -= num_points

        ecg_out, pleth_out, resp_out, abp_out, co2_out = [], [], [], [], []
        self.r_wave_detected = False

        for _ in range(num_points):
            self._resp_time += self.dt
            # --- Phase advancement (rhythm-dependent) ---
            hr_rate = (self.hr / 60.0) * self.dt

            if "AFib" in self.ecg_rhythm:
                hr_rate *= self._afib_rr_mod
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

            # Generate ECG
            ecg_val = self._get_ecg_point(self.phase_ecg)

            # R-wave detection (phase crossing)
            r_peak_phase = 0.38
            if "PVCs" in self.ecg_rhythm and self._in_pvc:
                r_peak_phase = 0.35
            elif "VTach" in self.ecg_rhythm:
                r_peak_phase = 0.30
            elif "3rd Deg" in self.ecg_rhythm:
                r_peak_phase = 0.35
            
            # If phase just crossed the peak (and didn't wrap around in the same step)
            if old_phase < r_peak_phase <= self.phase_ecg:
                self.r_wave_detected = True

            ecg_out.append(ecg_val)
            pleth_out.append(self._pleth_point(self.phase_ecg))
            resp_out.append(self._resp_point(self.phase_resp))
            abp_out.append(self._abp_point(self.phase_ecg))
            co2_out.append(self._co2_point(self.phase_resp))

        return {
            "ecg": ecg_out, "pleth": pleth_out, "resp": resp_out,
            "abp": abp_out, "co2": co2_out,
        }

    def _on_new_beat(self):
        """Called when a new cardiac cycle begins (phase wraps)."""
        self._beat_counter += 1

        # AFib: pick a new random R-R modifier for the next beat
        if "AFib" in self.ecg_rhythm:
            self._afib_rr_mod = random.uniform(0.65, 1.45)

        # PVCs: determine if next beat is a PVC
        if "PVCs" in self.ecg_rhythm:
            if self._in_pvc:
                self._in_pvc = False
                self._pvc_interval = random.randint(4, 10)
                self._beat_counter = 0
            elif self._beat_counter >= self._pvc_interval:
                self._in_pvc = True
