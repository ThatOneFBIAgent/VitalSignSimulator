"""
Audio system using user-provided .wav files.
Three sounds:
  - pulse_tone.wav  → played on each heartbeat, pitch-modulated by HR
  - alarm_med.wav   → medium/low-priority alarm (looped)
  - alarm_high.wav  → high-priority alarm (looped)

Pitch modulation: pulse_tone is played faster/slower based on HR to create
a natural pitch shift. Normal pitch at ~72 bpm, higher pitch at high HR,
lower pitch at low HR, clamped to a reasonable range.
"""
import os
import numpy as np
import pygame


def _load_and_resample(filepath, speed_factor):
    """
    Load a wav file and resample it to change pitch by speed_factor.
    speed_factor > 1.0 = higher pitch, < 1.0 = lower pitch.
    Returns a pygame.mixer.Sound or None.
    """
    snd = pygame.mixer.Sound(filepath)
    arr = pygame.sndarray.array(snd)  # shape: (samples, channels)

    if abs(speed_factor - 1.0) < 0.01:
        return snd  # No change needed

    # Resample using linear interpolation
    orig_len = arr.shape[0]
    new_len = int(orig_len / speed_factor)
    if new_len < 10:
        return snd

    channels = arr.shape[1] if arr.ndim > 1 else 1
    old_indices = np.linspace(0, orig_len - 1, new_len)

    if channels > 1:
        new_arr = np.zeros((new_len, channels), dtype=np.int16)
        for c in range(channels):
            new_arr[:, c] = np.interp(old_indices, np.arange(orig_len), arr[:, c]).astype(np.int16)
    else:
        new_arr = np.interp(old_indices, np.arange(orig_len), arr).astype(np.int16)

    return pygame.sndarray.make_sound(new_arr.copy())


class AudioSystem:
    PULSE_FILE = "pulse_tone.wav"
    ALARM_MED_FILE = "alarm_med.wav"
    ALARM_HIGH_FILE = "alarm_high.wav"

    # HR reference point for normal pitch (speed_factor = 1.0)
    HR_NORMAL = 72.0
    # Pitch range: at HR=30 -> 0.7x speed, at HR=200 -> 1.5x speed
    PITCH_MIN = 0.7
    PITCH_MAX = 1.5
    HR_MIN = 30.0
    HR_MAX = 200.0

    def __init__(self, asset_dir="."):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

        self.asset_dir = asset_dir

        # --- Pre-generate pitch-shifted pulse tones ---
        pulse_path = os.path.join(asset_dir, self.PULSE_FILE)
        self.pulse_tones = {}
        self._has_pulse = os.path.exists(pulse_path)

        if self._has_pulse:
            # Pre-build tones for HR values 30 to 200 in steps of 2
            for hr in range(30, 201, 2):
                speed = self._hr_to_speed(hr)
                self.pulse_tones[hr] = _load_and_resample(pulse_path, speed)
            print(f"[Audio] Loaded {len(self.pulse_tones)} pitch variants from {self.PULSE_FILE}")
        else:
            print(f"[Audio] WARNING: {pulse_path} not found — pulse beep disabled")

        # --- Alarm sounds ---
        med_path = os.path.join(asset_dir, self.ALARM_MED_FILE)
        high_path = os.path.join(asset_dir, self.ALARM_HIGH_FILE)

        self.alarm_med_sound = None
        self.alarm_high_sound = None

        if os.path.exists(med_path):
            self.alarm_med_sound = pygame.mixer.Sound(med_path)
            print(f"[Audio] Loaded {self.ALARM_MED_FILE}")
        else:
            print(f"[Audio] WARNING: {med_path} not found — medium alarm disabled")

        if os.path.exists(high_path):
            self.alarm_high_sound = pygame.mixer.Sound(high_path)
            print(f"[Audio] Loaded {self.ALARM_HIGH_FILE}")
        else:
            print(f"[Audio] WARNING: {high_path} not found — high alarm disabled")

        # Mixer channels
        self.ch_pulse = pygame.mixer.Channel(0)
        self.ch_alarm = pygame.mixer.Channel(1)

        self.alarm_playing = None   # "high" | "low" | None
        self.muted = False

    def _hr_to_speed(self, hr):
        """Map heart rate to playback speed factor for pitch shifting."""
        # Linear interpolation: HR_MIN -> PITCH_MIN, HR_MAX -> PITCH_MAX
        t = (hr - self.HR_MIN) / (self.HR_MAX - self.HR_MIN)
        t = max(0.0, min(1.0, t))
        return self.PITCH_MIN + t * (self.PITCH_MAX - self.PITCH_MIN)

    def play_pulse(self, hr_value):
        """Play pitch-shifted pulse beep based on current heart rate."""
        if self.muted or not self._has_pulse:
            return
        # Snap to nearest pre-built tone (even number)
        idx = max(30, min(200, int(round(hr_value / 2) * 2)))
        tone = self.pulse_tones.get(idx)
        if tone and not self.ch_pulse.get_busy():
            self.ch_pulse.play(tone)

    def play_alarm(self, priority):
        """Start looping an alarm. priority: 'high' or 'low'."""
        if self.muted:
            return
        if self.alarm_playing == priority:
            return  # Already looping
        self.stop_alarm()
        if priority == "high" and self.alarm_high_sound:
            self.ch_alarm.play(self.alarm_high_sound, loops=-1, fade_ms=250)
            self.alarm_playing = "high"
        elif priority == "low" and self.alarm_med_sound:
            self.ch_alarm.play(self.alarm_med_sound, loops=-1, fade_ms=250)
            self.alarm_playing = "low"

    def stop_alarm(self):
        if self.ch_alarm.get_busy():
            self.ch_alarm.fadeout(250)
        self.alarm_playing = None

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self.ch_pulse.stop()
            self.stop_alarm()
        return self.muted


class AlarmLogic:
    """Checks vitals against thresholds and determines alarm priority."""

    def __init__(self):
        self.thresholds = {
            "hr_high":  150, "hr_low":   40,
            "hr_crit_high": 180, "hr_crit_low": 25,
            "spo2_low": 90, "spo2_crit_low": 85,
            "rr_high":  30, "rr_low":   8,
            "bp_sys_high": 160, "bp_sys_low": 90,
            "etco2_high": 50, "etco2_low": 30,
        }
        self.active_alarm = None   # None | "low" | "high"
        self.alarm_message = ""
        self.flash_state = False
        self._flash_timer = 0.0

        # Hysteresis: once an alarm triggers, the value must go this many
        # units past the threshold before the alarm clears. Prevents rapid
        # toggling when values hover near a boundary.
        self._hysteresis = 2
        self._active_params = set()  # Track which specific checks are firing
        self.alarming_params = {}     # Maps key -> "high" | "low" | None
        self.alarming_params = {}     # Maps key -> "high" | "low" | None

    def _check_high(self, key, value, threshold, above=True):
        """Check a threshold with hysteresis. above=True means alarm when value >= threshold."""
        hyst = self._hysteresis
        if key in self._active_params:
            # Already alarming — require clearance past hysteresis band
            if above and value < threshold - hyst:
                self._active_params.discard(key)
            elif not above and value > threshold + hyst:
                self._active_params.discard(key)
            return key in self._active_params
        else:
            # Not alarming — trigger at threshold
            if above and value >= threshold:
                self._active_params.add(key)
                return True
            elif not above and value <= threshold:
                self._active_params.add(key)
                return True
        return False

    def update(self, sim, dt):
        """Evaluate alarm conditions with hysteresis. Returns priority or None."""
        hr, spo2, rr = sim.hr, sim.spo2, sim.rr
        sys, co2 = sim.bp_sys, sim.etco2

        # 1. Update ALL active_params state (must run every frame for boxes/hysteresis to work)
        c_hr_hi = self._check_high("hr_crit_hi", hr, self.thresholds["hr_crit_high"], True)
        c_hr_lo = self._check_high("hr_crit_lo", hr, self.thresholds["hr_crit_low"], False)
        c_spo2_lo = self._check_high("spo2_crit", spo2, self.thresholds["spo2_crit_low"], False)
        
        w_hr_hi = self._check_high("hr_hi", hr, self.thresholds["hr_high"], True)
        w_hr_lo = self._check_high("hr_lo", hr, self.thresholds["hr_low"], False)
        w_spo2_lo = self._check_high("spo2_lo", spo2, self.thresholds["spo2_low"], False)
        w_rr_hi = self._check_high("rr_hi", rr, self.thresholds["rr_high"], True)
        w_rr_lo = self._check_high("rr_lo", rr, self.thresholds["rr_low"], False)
        w_bp_hi = self._check_high("bp_sys_hi", sys, self.thresholds["bp_sys_high"], True)
        w_bp_lo = self._check_high("bp_sys_lo", sys, self.thresholds["bp_sys_low"], False)
        w_co2_hi = self._check_high("etco2_hi", co2, self.thresholds["etco2_high"], True)
        w_co2_lo = self._check_high("etco2_lo", co2, self.thresholds["etco2_low"], False)

        # 2. Pick Top Priority Message
        priority = None
        msg = ""

        # High Priority
        if "[Arrest] Asystole" in sim.ecg_rhythm:
            priority, msg = "high", "*** ASYSTOLE ***"
        elif "[Vent] VFib" in sim.ecg_rhythm:
            priority, msg = "high", "*** V-FIB ***"
        elif "[Vent] Torsades" in sim.ecg_rhythm:
            priority, msg = "high", "*** TORSADES ***"
        elif c_hr_hi: priority, msg = "high", f"*** TACHYCARDIA  HR {int(hr)} ***"
        elif c_hr_lo: priority, msg = "high", f"*** BRADYCARDIA  HR {int(hr)} ***"
        elif c_spo2_lo: priority, msg = "high", f"*** DESAT  SpO2 {int(spo2)}% ***"

        # Low Priority (if no high)
        if priority is None:
            if w_hr_hi or w_hr_lo: priority, msg = "low", f"HR {int(hr)} OUT OF RANGE"
            elif w_spo2_lo: priority, msg = "low", f"SpO2 {int(spo2)}% LOW"
            elif w_rr_hi or w_rr_lo: priority, msg = "low", f"RR {int(rr)} OUT OF RANGE"
            elif w_bp_hi: priority, msg = "low", f"ABP SYS {int(sys)} HIGH"
            elif w_bp_lo: priority, msg = "low", f"ABP SYS {int(sys)} LOW"
            elif w_co2_hi: priority, msg = "low", f"EtCO2 {int(co2)} HIGH"
            elif w_co2_lo: priority, msg = "low", f"EtCO2 {int(co2)} LOW"

        # 3. Individual tracking for visual indicators
        self.alarming_params = {
            "hr":    "high" if (c_hr_hi or w_hr_hi) else ("low" if (c_hr_lo or w_hr_lo) else None),
            "spo2":  "low" if (c_spo2_lo or w_spo2_lo) else None,
            "rr":    "high" if w_rr_hi else ("low" if w_rr_lo else None),
            "abp":   "high" if w_bp_hi else ("low" if w_bp_lo else None),
            "etco2": "high" if w_co2_hi else ("low" if w_co2_lo else None),
        }

        self.active_alarm = priority
        self.alarm_message = msg

        # Flash timing
        if priority:
            interval = 0.25 if priority == "high" else 0.6
            self._flash_timer += dt
            if self._flash_timer >= interval:
                self.flash_state = not self.flash_state
                self._flash_timer = 0.0
        else:
            self.flash_state = False
            self._flash_timer = 0.0

        return priority
