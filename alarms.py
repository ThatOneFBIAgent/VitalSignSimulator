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
    BEEP_FILE = "beep.wav"

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
        beep_path = os.path.join(asset_dir, self.BEEP_FILE)

        self.alarm_med_sound = None
        self.alarm_high_sound = None
        self.beep_sound = None

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
            
        if os.path.exists(beep_path):
            self.beep_sound = pygame.mixer.Sound(beep_path)
            self.beep_sound.set_volume(0.25)
            print(f"[Audio] Loaded {self.BEEP_FILE}")
        else:
            print(f"[Audio] WARNING: {beep_path} not found — hardware beep disabled")

        # Mixer channels
        self.ch_pulse = pygame.mixer.Channel(0)
        self.ch_alarm = pygame.mixer.Channel(1)
        self.ch_beep = pygame.mixer.Channel(2)

        self.alarm_playing = None   # "high" | "low" | None
        self.muted = False
        self.silence_timer = 0.0    # Silences current alarm for a duration

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

    def stop_alarm(self):
        if self.ch_alarm.get_busy():
            self.ch_alarm.fadeout(250)
        self.alarm_playing = None

    def update(self, dt, priority):
        if self.silence_timer > 0:
            self.silence_timer -= dt

        if self.muted or not priority or self.silence_timer > 0:
            if self.alarm_playing:
                self.stop_alarm()
            return

        if priority in ("high", "low"):
            if self.alarm_playing != priority:
                self.stop_alarm()
                sound = self.alarm_high_sound if priority == "high" else self.alarm_med_sound
                if sound:
                    self.ch_alarm.play(sound, loops=-1, fade_ms=250)
                self.alarm_playing = priority
        else:
            # warning priorities do not loop an audio file
            if self.alarm_playing in ("high", "low"):
                self.stop_alarm()
            self.alarm_playing = priority

    def play_beep(self):
        if self.muted or not self.beep_sound:
            return
        # Use dedicated channel and prevent overlapping/drowning out
        if not self.ch_beep.get_busy():
            self.ch_beep.play(self.beep_sound)

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self.ch_pulse.stop()
            self.stop_alarm()
        return self.muted

    def acknowledge(self):
        """Stop current alarm and silence for 2 minutes."""
        self.stop_alarm()
        self.silence_timer = 120.0



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
            "temp_high": 38.5, "temp_low": 35.0,
        }
        self.active_alarm = None   # None | "low" | "high" | "warning_vfib" | "warning_vitals"
        self.alarm_message = ""
        self.flash_state = False
        self._flash_timer = 0.0
        self.t = 0.0
        self.vfib_timer = 0.0
        self.unack_timer = 0.0
        self.selftest_timer = 20.0
        self.selftest_active = False
        self.selftest_duration = 0.0
        self.high_hold_timer = 0.0
        self.high_hold_msg = ""
        self.low_hold_timer = 0.0
        self.low_hold_msg = ""
        self.led_left = None
        self.led_right = None
        self.play_beep = False

        # Hysteresis: once an alarm triggers, the value must move back into
        # range by this much before the alarm clears. Use per-check bands so
        # slow, narrow values like temperature are not treated like HR/BP.
        self._hysteresis = {
            "default": 2.0,
            "temp_hi": 0.3,
            "temp_lo": 0.3,
        }
        self._active_params = set()  # Track which specific checks are firing
        self.alarming_params = {}     # Maps key -> "high" | "low" | None

    def _hysteresis_for(self, key):
        return self._hysteresis.get(key, self._hysteresis["default"])

    def _check_high(self, key, value, threshold, above=True):
        """Check a threshold with hysteresis. above=True means alarm when value >= threshold."""
        hyst = self._hysteresis_for(key)
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
        self.t += dt
        
        hr, spo2, rr = sim.hr, sim.spo2, sim.rr
        sys, co2 = sim.bp_sys, sim.etco2
        temp = getattr(sim, "temp", 37.0)

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
        w_temp_hi = self._check_high("temp_hi", temp, self.thresholds["temp_high"], True)
        w_temp_lo = self._check_high("temp_lo", temp, self.thresholds["temp_low"], False)
        w_irreg = getattr(sim, "hr_irregular", False)

        # 2. Pick Top Priority Message
        prev_priority = self.active_alarm
        priority = None
        msg = ""

        # High Priority
        is_vfib = False
        is_asystole = False
        is_apnea = False
        if hr == 0.0:
            if getattr(sim, "ecg_amplitude", 0.0) > 0.4:
                is_vfib = True
            else:
                is_asystole = True
                
        if rr < 2.0:
            is_apnea = True
                
        if is_vfib:
            self.vfib_timer += dt
        else:
            self.vfib_timer = 0.0

        if is_vfib:
            if self.vfib_timer < 2.0:
                priority, msg = "warning_vfib", "** CHECK V-FIB **"
            else:
                priority, msg = "high", "*** V-FIB / V-TACH ***"
        elif is_asystole:
            priority, msg = "high", "*** ASYSTOLE ***"
        elif is_apnea:
            priority, msg = "high", "*** APNEA ***"
        elif c_hr_hi: priority, msg = "high", f"*** TACHYCARDIA  HR {int(hr)} ***"
        elif c_hr_lo: priority, msg = "high", f"*** BRADYCARDIA  HR {int(hr)} ***"
        elif c_spo2_lo: priority, msg = "high", f"*** DESAT  SpO2 {int(spo2)}% ***"

        # Low/Warning Priority (if no high)
        if priority is None:
            if w_hr_hi or w_hr_lo: priority, msg = "low", f"HR {int(hr)} OUT OF RANGE"
            elif w_spo2_lo: priority, msg = "low", f"SpO2 {int(spo2)}% LOW"
            elif w_rr_hi or w_rr_lo: priority, msg = "low", f"RR {int(rr)} OUT OF RANGE"
            elif w_bp_hi: priority, msg = "low", f"ABP SYS {int(sys)} HIGH"
            elif w_bp_lo: priority, msg = "low", f"ABP SYS {int(sys)} LOW"
            elif w_co2_hi: priority, msg = "low", f"EtCO2 {int(co2)} HIGH"
            elif w_co2_lo: priority, msg = "low", f"EtCO2 {int(co2)} LOW"
            elif w_irreg: priority, msg = "warning_irreg", "*** CHECK IRREG. RHYTHM ***"
            elif w_temp_hi or w_temp_lo: priority, msg = "warning_vitals", f"TEMP {temp:.1f} OUT OF RANGE"

        # Priority Debouncing (prevents audio restarting / UI stuttering)
        if priority == "high":
            self.high_hold_timer = 3.0
            self.high_hold_msg = msg
        elif self.high_hold_timer > 0.0:
            self.high_hold_timer -= dt
            priority = "high"
            msg = getattr(self, "high_hold_msg", msg)
            
        if priority == "low":
            self.low_hold_timer = 2.0
            self.low_hold_msg = msg
        elif priority is None and self.low_hold_timer > 0.0:
            self.low_hold_timer -= dt
            priority = "low"
            msg = getattr(self, "low_hold_msg", msg)

        # Selftest logic (runs periodically when no alarms are active)
        if priority is None and prev_priority is None:
            self.selftest_timer -= dt
            if self.selftest_timer <= 0:
                self.selftest_active = True
                self.selftest_timer = 45.0  # Run every 45 seconds
                self.selftest_duration = 2.0
                
        if getattr(self, "selftest_active", False):
            self.selftest_duration -= dt
            if self.selftest_duration <= 0:
                self.selftest_active = False

        # After-alarm (Unacknowledged) state
        if priority is None and prev_priority in ("high", "low"):
            self.unack_timer = 15.0  # 15 seconds of after-alarm beeps
            
        if priority is not None:
            self.unack_timer = 0.0
            
        if priority is None and self.unack_timer > 0.0:
            self.unack_timer -= dt
            priority = "warning_unack"
            msg = "ALARM CLEARED - CHECK PT"

        # 3. Individual tracking for visual indicators
        self.alarming_params = {
            "hr":    "high" if (c_hr_hi or w_hr_hi) else ("low" if (c_hr_lo or w_hr_lo) else None),
            "spo2":  "low" if (c_spo2_lo or w_spo2_lo) else None,
            "rr":    "high" if w_rr_hi else ("low" if w_rr_lo else None),
            "abp":   "high" if w_bp_hi else ("low" if w_bp_lo else None),
            "etco2": "high" if w_co2_hi else ("low" if w_co2_lo else None),
            "temp":  "high" if w_temp_hi else ("low" if w_temp_lo else None),
        }

        self.active_alarm = priority
        self.alarm_message = msg

        # Store previous state for beep synchronization
        prev_left = self.led_left
        prev_right = self.led_right

        # Hardware LEDs
        self.led_left = None
        self.led_right = None
        
        if priority == "high":
            if "ASYSTOLE" in msg or "V-FIB" in msg:
                # Critical: Rapid Strobe (3 quick flashes, pause)
                strobe_cycle = (self.t * 8) % 4
                if strobe_cycle < 3:
                    self.led_left = (255, 0, 0)
                    self.led_right = (255, 0, 0)
            elif "APNEA" in msg:
                # Apnea: Alternating Red/White "Emergency" sweep
                if int(self.t * 6) % 2 == 0:
                    self.led_left = (255, 255, 255)
                    self.led_right = (255, 0, 0)
                else:
                    self.led_left = (255, 0, 0)
                    self.led_right = (255, 255, 255)
            elif "DESAT" in msg:
                # SpO2: Rapid Cyan/Red flip
                if int(self.t * 5) % 2 == 0:
                    self.led_left = (255, 0, 0)
                    self.led_right = (0, 255, 255)
                else:
                    self.led_left = (0, 255, 255)
                    self.led_right = (255, 0, 0)
            else:
                # Standard High: Fast alternating Red
                if int(self.t * 5) % 2 == 0:
                    self.led_left = (255, 0, 0)
                else:
                    self.led_right = (255, 0, 0)
        elif priority == "low":
            # Low-priority: Alternating amber sweep synced to alarm_med cadence
            cycle = int(self.t * 2) % 2
            if "SpO2" in msg:
                # SpO2 low: Alternating Cyan / Amber
                if cycle == 0:
                    self.led_left = (255, 180, 0)
                    self.led_right = None
                else:
                    self.led_left = None
                    self.led_right = (0, 220, 255)
            elif "ABP" in msg:
                # BP: Alternating Magenta / Amber
                if cycle == 0:
                    self.led_left = (255, 0, 255)
                    self.led_right = None
                else:
                    self.led_left = None
                    self.led_right = (255, 180, 0)
            else:
                # Default Low: Alternating amber L/R sweep
                if cycle == 0:
                    self.led_left = (255, 180, 0)
                    self.led_right = None
                else:
                    self.led_left = None
                    self.led_right = (255, 180, 0)
        elif priority == "warning_vfib":
            # "Caution" strobe: Double-tap amber then red burst
            cycle = self.t % 2.0
            if cycle < 0.15 or (0.3 <= cycle < 0.45):
                self.led_left = (255, 180, 0)
                self.led_right = (255, 180, 0)
            elif 1.0 <= cycle < 1.15:
                self.led_left = (255, 0, 0)
                self.led_right = (255, 0, 0)
        elif priority == "warning_irreg":
            # Scanning Amber L-R
            cycle = self.t % 1.2
            if cycle < 0.25:
                self.led_left = (255, 180, 0)
            elif 0.6 <= cycle < 0.85:
                self.led_right = (255, 180, 0)
        elif priority == "warning_vitals":
            # Slow simultaneous amber pulse
            if int(self.t * 1.5) % 2 == 0:
                self.led_left = (255, 180, 0)
                self.led_right = (255, 180, 0)
        elif priority == "warning_unack":
            # Slow alternating amber sweep
            if int(self.t * 3) % 2 == 0:
                self.led_left = (255, 180, 0)
            else:
                self.led_right = (255, 180, 0)
        elif priority is None and getattr(self, "selftest_active", False):
            # Silent periodic diagnostic sequence
            cycle = 2.0 - self.selftest_duration
            if cycle < 0.15:
                self.led_left = (0, 255, 100)
            elif 0.25 <= cycle < 0.4:
                self.led_right = (0, 255, 100)
            elif 0.5 <= cycle < 0.65:
                self.led_left = (0, 100, 255)
            elif 0.75 <= cycle < 0.9:
                self.led_right = (0, 100, 255)
            elif 1.2 <= cycle < 1.4:
                self.led_left = (0, 255, 100)
                self.led_right = (0, 255, 100)

        # Beep sync: trigger on LEFT amber LED rising edge only (prevents double beeps)
        self.play_beep = False
        if priority and "warning" in priority:
            if self.led_left == (255, 180, 0) and prev_left != (255, 180, 0):
                self.play_beep = True
        
        # Anti-Polyphony: Suppress the mechanical beep if a loop is already playing
        if priority in ("high", "low"):
            self.play_beep = False

        # Flash timing for boxes
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
