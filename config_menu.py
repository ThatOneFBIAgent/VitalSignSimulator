"""
In-app configuration overlay menu.
Opened with TAB, navigated with arrow keys.
Sections: Vitals | Alarms | Display | Presets
"""
import pygame
from simulation import ECG_RHYTHMS, RESP_PATTERNS

# ─── Color constants ───
C_BG       = (18, 18, 24, 220)
C_HEADER   = (80, 200, 255)
C_LABEL    = (180, 180, 200)
C_VALUE    = (255, 255, 255)
C_SELECTED = (0, 255, 130)
C_TAB_ACT  = (0, 255, 130)
C_TAB_INACT= (100, 100, 120)
C_DIVIDER  = (50, 50, 70)

PRESETS = {
    "Healthy Adult": {
        "hr": 72, "spo2": 98, "rr": 16,
        "bp_sys": 120, "bp_dia": 80, "temp": 36.8, "etco2": 38,
    },
    "Tachycardia": {
        "hr": 155, "spo2": 95, "rr": 22,
        "bp_sys": 140, "bp_dia": 90, "temp": 37.2, "etco2": 32,
    },
    "Bradycardia": {
        "hr": 38, "spo2": 96, "rr": 12,
        "bp_sys": 100, "bp_dia": 65, "temp": 36.5, "etco2": 40,
    },
    "Hypoxia": {
        "hr": 115, "spo2": 82, "rr": 28,
        "bp_sys": 130, "bp_dia": 85, "temp": 37.0, "etco2": 28,
    },
    "Sepsis": {
        "hr": 125, "spo2": 91, "rr": 26,
        "bp_sys": 85, "bp_dia": 50, "temp": 39.2, "etco2": 30,
    },
    "Hypertensive Crisis": {
        "hr": 95, "spo2": 97, "rr": 18,
        "bp_sys": 210, "bp_dia": 130, "temp": 37.0, "etco2": 36,
    },
    "Cardiac Arrest": {
        "hr": 0, "spo2": 50, "rr": 0,
        "bp_sys": 20, "bp_dia": 10, "temp": 35.8, "etco2": 0,
    },
    "Anaphylaxis": {
        "hr": 140, "spo2": 88, "rr": 32,
        "bp_sys": 70, "bp_dia": 40, "temp": 37.5, "etco2": 45,
    },
    "Hypovolemic Shock": {
        "hr": 135, "spo2": 94, "rr": 24,
        "bp_sys": 75, "bp_dia": 45, "temp": 35.5, "etco2": 30,
    },
    "Opioid Overdose": {
        "hr": 55, "spo2": 80, "rr": 6,
        "bp_sys": 95, "bp_dia": 60, "temp": 36.0, "etco2": 55,
    },
    "Asthma Exacerbation": {
        "hr": 130, "spo2": 89, "rr": 35,
        "bp_sys": 145, "bp_dia": 95, "temp": 37.4, "etco2": 25,
    },
    "Malignant Hyperthermia": {
        "hr": 150, "spo2": 95, "rr": 30,
        "bp_sys": 80, "bp_dia": 45, "temp": 40.5, "etco2": 80,
    },
    "Pulmonary Embolism": {
        "hr": 125, "spo2": 84, "rr": 28,
        "bp_sys": 90, "bp_dia": 55, "temp": 37.1, "etco2": 20,
    },
    "Cushing's Triad (ICP)": {
        "hr": 42, "spo2": 98, "rr": 8,
        "bp_sys": 210, "bp_dia": 110, "temp": 36.8, "etco2": 45,
    },
    "SVT": {
        "hr": 210, "spo2": 97, "rr": 22,
        "bp_sys": 95, "bp_dia": 60, "temp": 37.0, "etco2": 35,
    },
    "Mild Hypothermia": {
        "hr": 50, "spo2": 95, "rr": 10,
        "bp_sys": 105, "bp_dia": 65, "temp": 34.0, "etco2": 42,
    }
}


class ConfigItem:
    def __init__(self, key, label, min_v, max_v, step, fmt=".0f",
                 getter=None, setter=None):
        self.key = key
        self.label = label
        self.min_v = min_v
        self.max_v = max_v
        self.step = step
        self.fmt = fmt
        self.getter = getter
        self.setter = setter

    def get_value(self):
        return self.getter() if self.getter else 0

    def adjust(self, direction):
        """direction: +1 or -1"""
        v = self.get_value() + direction * self.step
        v = max(self.min_v, min(self.max_v, v))
        if self.setter:
            self.setter(v)


class ToggleItem:
    def __init__(self, key, label, getter, setter):
        self.key = key
        self.label = label
        self.getter = getter
        self.setter = setter

    def get_value(self):
        return self.getter()

    def toggle(self):
        self.setter(not self.getter())


class CycleItem:
    """Cycles through a list of string options with Left/Right or Enter."""
    def __init__(self, key, label, options, getter, setter):
        self.key = key
        self.label = label
        self.options = options
        self.getter = getter
        self.setter = setter

    def get_value(self):
        return self.getter()

    def cycle(self, direction=1):
        current = self.getter()
        idx = self.options.index(current) if current in self.options else 0
        idx = (idx + direction) % len(self.options)
        self.setter(self.options[idx])


class PresetItem:
    def __init__(self, name, preset_data, apply_fn):
        self.key = name
        self.label = name
        self.preset_data = preset_data
        self.apply_fn = apply_fn

    def apply(self):
        self.apply_fn(self.preset_data)

class ActionItem:
    def __init__(self, key, label, action_fn, get_label_fn=None):
        self.key = key
        self.label = label
        self.action_fn = action_fn
        self.get_label_fn = get_label_fn

    def action(self):
        self.action_fn()
        
    def get_value_str(self):
        return self.get_label_fn() if self.get_label_fn else "[ENTER]"


class ConfigMenu:
    def __init__(self, sim, alarm_logic, effects, audio, routine_manager=None, theme_callback=None, initial_theme="Classic Hospital", monitor_ref=None):
        self.visible = False
        self.sim = sim
        self.alarm_logic = alarm_logic
        self.effects = effects
        self.audio = audio
        self.routine_manager = routine_manager
        self.theme_callback = theme_callback
        self.active_theme_name = initial_theme
        self.monitor = monitor_ref
        self.scroll_offset = 0

        self.tabs = ["Vitals", "Alarms", "Display", "Presets", "Routines"]
        self.current_tab = 0
        self.current_row = 0

        # Build sections
        self.sections = {
            "Vitals": self._build_vitals(),
            "Alarms": self._build_alarms(),
            "Display": self._build_display(),
            "Presets": self._build_presets(),
            "Routines": self._build_routines(),
        }

        # Fonts
        self.font_tab = None
        self.font_label = None
        self.font_value = None
        self._fonts_ready = False

    def _ensure_fonts(self):
        if not self._fonts_ready:
            self.font_tab = pygame.font.SysFont("Consolas", 30, bold=True)
            self.font_label = pygame.font.SysFont("Consolas", 27)
            self.font_value = pygame.font.SysFont("Consolas", 27, bold=True)
            self.font_title = pygame.font.SysFont("Consolas", 21)
            self._fonts_ready = True

    def _build_vitals(self):
        s = self.sim
        t = s.targets
        items = []

        # ECG Rhythm selector (first item)
        items.append(CycleItem(
            "ecg_rhythm", "ECG Rhythm", ECG_RHYTHMS,
            getter=lambda: s.ecg_rhythm,
            setter=lambda v: setattr(s, 'ecg_rhythm', v),
        ))
        
        # Respiratory Pattern selector
        items.append(CycleItem(
            "resp_pattern", "Resp Pattern", RESP_PATTERNS,
            getter=lambda: s.resp_pattern,
            setter=lambda v: setattr(s, 'resp_pattern', v),
        ))
        
        # Probe toggles
        items.append(ToggleItem(
            "probe_etco2", "Probe: EtCO2 Connected",
            getter=lambda: s.probe_etco2,
            setter=lambda v: setattr(s, 'probe_etco2', v),
        ))
        items.append(ToggleItem(
            "probe_temp", "Probe: Temp Connected",
            getter=lambda: s.probe_temp,
            setter=lambda v: setattr(s, 'probe_temp', v),
        ))

        for key, label, lo, hi, step, fmt in [
            ("hr",     "Heart Rate (target)",  10, 300, 1, ".0f"),
            ("spo2",   "SpO2 (target)",        30, 100, 1, ".0f"),
            ("rr",     "Resp Rate (target)",    2,  60, 1, ".0f"),
            ("bp_sys", "BP Systolic (target)",  40, 300, 5, ".0f"),
            ("bp_dia", "BP Diastolic (target)", 20, 200, 5, ".0f"),
            ("temp",   "Temperature (target)", 30.0, 44.0, 0.1, ".1f"),
            ("etco2",  "EtCO2 (target)",         5, 100, 1, ".0f"),
        ]:
            items.append(ConfigItem(
                key, label, lo, hi, step, fmt,
                getter=lambda k=key: t[k]["value"],
                setter=lambda v, k=key: self._set_vital_target(k, v),
            ))
        # Range items (min/max for fluctuation)
        items.append(ConfigItem(
            "hr_min", "HR Fluctuation Min", 10, 300, 1, ".0f",
            getter=lambda: t["hr"]["min"],
            setter=lambda v: t["hr"].__setitem__("min", v),
        ))
        items.append(ConfigItem(
            "hr_max", "HR Fluctuation Max", 10, 300, 1, ".0f",
            getter=lambda: t["hr"]["max"],
            setter=lambda v: t["hr"].__setitem__("max", v),
        ))
        items.append(ConfigItem(
            "spo2_min", "SpO2 Fluctuation Min", 30, 100, 1, ".0f",
            getter=lambda: t["spo2"]["min"],
            setter=lambda v: t["spo2"].__setitem__("min", v),
        ))
        items.append(ConfigItem(
            "spo2_max", "SpO2 Fluctuation Max", 30, 100, 1, ".0f",
            getter=lambda: t["spo2"]["max"],
            setter=lambda v: t["spo2"].__setitem__("max", v),
        ))
        return items

    def _set_vital_target(self, key, value):
        t = self.sim.targets[key]
        old = t["value"]
        t["value"] = value
        # Also set the live value directly for instant response
        setattr(self.sim, key, float(value))
        if key in self.sim.display:
            self.sim.display[key] = float(value)
        # Shift fluctuation window to follow the target
        delta = value - old
        t["min"] += delta
        t["max"] += delta

    def _build_alarms(self):
        a = self.alarm_logic.thresholds
        items = []
        for key, label, lo, hi, step in [
            ("hr_high",      "HR High Alarm",       50, 250, 5),
            ("hr_low",       "HR Low Alarm",        20, 100, 5),
            ("hr_crit_high", "HR Critical High",    80, 300, 5),
            ("hr_crit_low",  "HR Critical Low",     10,  60, 5),
            ("spo2_low",     "SpO2 Low Alarm",      70, 100, 1),
            ("spo2_crit_low","SpO2 Critical Low",   50, 100, 1),
            ("rr_high",      "RR High Alarm",       15,  60, 1),
            ("rr_low",       "RR Low Alarm",         2,  20, 1),
            ("bp_sys_high",  "ABP Sys High Alarm",  90, 250, 5),
            ("bp_sys_low",   "ABP Sys Low Alarm",   40, 120, 5),
            ("etco2_high",   "EtCO2 High Alarm",    35,  80, 1),
            ("etco2_low",    "EtCO2 Low Alarm",      5,  35, 1),
        ]:
            items.append(ConfigItem(
                key, label, lo, hi, step, ".0f",
                getter=lambda k=key: a[k],
                setter=lambda v, k=key: a.__setitem__(k, v),
            ))
        return items

    def _build_display(self):
        e = self.effects
        items = []
        
        if self.theme_callback:
            items.append(CycleItem(
                "theme", "Display Theme",
                ["Classic Hospital", "High Contrast", "Ambulance (Dark Red)", "Deep Blue (Night)", 
                 "Nihon Kohden", "GE Carescape", "Mindray", "Legacy CRT (Green)"],
                getter=lambda: self.active_theme_name,
                setter=lambda v: self._set_theme(v)
            ))
            
        if self.monitor:
            items.append(ToggleItem(
                "show_rec", "Show 'REC' Status at Top",
                getter=lambda: self.monitor.show_rec_status,
                setter=lambda v: setattr(self.monitor, 'show_rec_status', v)
            ))
            
            # Info bar customization
            items.append(CycleItem(
                "hosp", "Institution Name",
                ["Patient Monitor", "General Hospital", "St. Jude Medical", "Stat Simulation", "Trauma Center"],
                getter=lambda: self.monitor.hospital_name,
                setter=lambda v: setattr(self.monitor, 'hospital_name', v)
            ))
            items.append(CycleItem(
                "dept", "Department",
                ["ICU", "ER", "OR", "Post-Op", "Triage", "Pediatrics", "Cardiac Care"],
                getter=lambda: self.monitor.dept_name,
                setter=lambda v: setattr(self.monitor, 'dept_name', v)
            ))
            items.append(CycleItem(
                "bed", "Bed / Unit",
                ["Bed 1", "Bed 2", "Bed 3", "Bed 4", "Bed 5", "Unit A", "Unit B", "Stat 1"],
                getter=lambda: self.monitor.bed_name,
                setter=lambda v: setattr(self.monitor, 'bed_name', v)
            ))

        for key, label in [
            ("scanlines", "CRT Scanlines"),
            ("vignette", "Vignette"),
            ("glow", "Number Glow"),
            ("phosphor", "Phosphor Persistence"),
        ]:
            items.append(ToggleItem(
                key, label,
                getter=lambda k=key: e.enabled[k],
                setter=lambda v, k=key: e.enabled.__setitem__(k, v),
            ))
        # Audio mute
        items.append(ToggleItem(
            "mute", "Mute Audio",
            getter=lambda: self.audio.muted,
            setter=lambda v: setattr(self.audio, 'muted', v),
        ))
        return items
        
    def _set_theme(self, name):
        self.active_theme_name = name
        if self.theme_callback:
            self.theme_callback(name)

    def _build_presets(self):
        items = []
        for name, data in PRESETS.items():
            items.append(PresetItem(name, data, self._apply_preset))
        return items

    def _build_routines(self):
        items = []
        if not self.routine_manager:
            return items

        rm = self.routine_manager
        routines = rm.get_routine_names()
        
        if not routines:
            return items
            
        # Select Routine
        items.append(CycleItem(
            "active_routine", "Selected Routine", routines,
            getter=lambda: rm.active_routine_name if rm.active_routine_name else routines[0],
            setter=lambda v: rm.set_routine(v)
        ))
        
        # Play/Stop
        def get_play_label():
            return "[ STOP ]" if rm.is_playing else "[ PLAY ]"
            
        items.append(ActionItem(
            "play_routine", "Playback Control",
            action_fn=lambda: rm.toggle_play(),
            get_label_fn=get_play_label
        ))
        return items

    def _apply_preset(self, data):
        self.sim.set_preset(data)

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            pygame.key.set_repeat(300, 40)  # Enable held-key repeat
            self.current_row = 0
        else:
            pygame.key.set_repeat(0)  # Disable repeat

    def handle_key(self, key):
        if not self.visible:
            return
        tab_name = self.tabs[self.current_tab]
        items = self.sections[tab_name]

        if items and self.current_row < len(items):
            item = items[self.current_row]
        else:
            item = None

        if key == pygame.K_LEFT:
            if isinstance(item, ConfigItem):
                item.adjust(-1)
            elif isinstance(item, CycleItem):
                item.cycle(-1)
            else:
                self.current_tab = (self.current_tab - 1) % len(self.tabs)
                self.current_row = 0
                self.scroll_offset = 0
        elif key == pygame.K_RIGHT:
            if isinstance(item, ConfigItem):
                item.adjust(+1)
            elif isinstance(item, CycleItem):
                item.cycle(+1)
            else:
                self.current_tab = (self.current_tab + 1) % len(self.tabs)
                self.current_row = 0
                self.scroll_offset = 0
        elif key == pygame.K_UP:
            if items:
                self.current_row = (self.current_row - 1) % len(items)
        elif key == pygame.K_DOWN:
            if items:
                self.current_row = (self.current_row + 1) % len(items)
        elif key == pygame.K_RETURN:
            if isinstance(item, ToggleItem):
                item.toggle()
            elif isinstance(item, PresetItem):
                item.apply()
            elif isinstance(item, CycleItem):
                item.cycle(+1)
            elif isinstance(item, ActionItem):
                item.action()
        elif key == pygame.K_1:
            self.current_tab = 0; self.current_row = 0; self.scroll_offset = 0
        elif key == pygame.K_2:
            self.current_tab = 1; self.current_row = 0; self.scroll_offset = 0
        elif key == pygame.K_3:
            self.current_tab = 2; self.current_row = 0; self.scroll_offset = 0
        elif key == pygame.K_4:
            self.current_tab = 3; self.current_row = 0; self.scroll_offset = 0
        elif key == pygame.K_5:
            if len(self.tabs) > 4:
                self.current_tab = 4; self.current_row = 0; self.scroll_offset = 0

    def draw(self, screen, width, height):
        if not self.visible:
            return
        self._ensure_fonts()

        # Panel dimensions — centered overlay
        pw, ph = min(1200, width - 60), min(870, height - 60)
        px = (width - pw) // 2
        py = (height - ph) // 2

        # Background
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill(C_BG)
        screen.blit(bg, (px, py))

        # Border
        pygame.draw.rect(screen, C_HEADER, (px, py, pw, ph), 1)

        # Title
        title = self.font_tab.render("CONFIGURATION", True, C_HEADER)
        screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 12))

        # Tab bar
        tab_y = py + 52
        tab_w = pw // len(self.tabs)
        for i, tab in enumerate(self.tabs):
            color = C_TAB_ACT if i == self.current_tab else C_TAB_INACT
            tx = px + i * tab_w
            label = self.font_label.render(f"[{i+1}] {tab}", True, color)
            # Center the label within the tab slot
            label_x = tx + (tab_w - label.get_width()) // 2
            screen.blit(label, (label_x, tab_y))
        # Divider under tabs
        pygame.draw.line(screen, C_DIVIDER, (px, tab_y + 37), (px + pw, tab_y + 37))

        # Items
        tab_name = self.tabs[self.current_tab]
        items = self.sections[tab_name]
        start_y = tab_y + 52
        row_h = 42

        # Scrolling logic
        max_visible = (py + ph - 65 - start_y) // row_h
        
        if self.current_row < self.scroll_offset:
            self.scroll_offset = self.current_row
        elif self.current_row >= self.scroll_offset + max_visible:
            self.scroll_offset = self.current_row - max_visible + 1

        for i, item in enumerate(items[self.scroll_offset:]):
            i_actual = i + self.scroll_offset
            y = start_y + i * row_h
            if y + row_h > py + ph - 60:
                break  # Clip

            selected = (i_actual == self.current_row)
            label_color = C_SELECTED if selected else C_LABEL

            # Selection indicator
            if selected:
                sel_rect = pygame.Surface((pw - 30, row_h - 3), pygame.SRCALPHA)
                sel_rect.fill((0, 255, 130, 25))
                screen.blit(sel_rect, (px + 15, y))
                # Arrow
                arrow = self.font_label.render(">", True, C_SELECTED)
                screen.blit(arrow, (px + 18, y + 3))

            # Label
            lbl = self.font_label.render(item.label, True, label_color)
            screen.blit(lbl, (px + 45, y + 3))

            # Value
            if isinstance(item, ConfigItem):
                v = item.get_value()
                fmt_str = f"{v:{item.fmt}}"
                val = self.font_value.render(f"< {fmt_str} >", True, C_VALUE)
                screen.blit(val, (px + pw - val.get_width() - 22, y + 3))
            elif isinstance(item, CycleItem):
                v = item.get_value()
                val = self.font_value.render(f"< {v} >", True, (100, 220, 255))
                screen.blit(val, (px + pw - val.get_width() - 22, y + 3))
            elif isinstance(item, ToggleItem):
                v = item.get_value()
                txt = "ON" if v else "OFF"
                color = (0, 255, 130) if v else (255, 80, 80)
                val = self.font_value.render(f"[{txt}]", True, color)
                screen.blit(val, (px + pw - val.get_width() - 22, y + 3))
            elif isinstance(item, PresetItem):
                val = self.font_value.render("[ENTER]", True, (100, 180, 255))
                screen.blit(val, (px + pw - val.get_width() - 22, y + 3))
            elif isinstance(item, ActionItem):
                color = (255, 100, 100) if "STOP" in item.get_value_str() else (100, 255, 100)
                val = self.font_value.render(item.get_value_str(), True, color)
                screen.blit(val, (px + pw - val.get_width() - 22, y + 3))

        # Footer
        footer = self.font_title.render(
            "Arrows: Adjust  |  Enter: Apply  |  TAB: Close",
            True, (80, 80, 100)
        )
        screen.blit(footer, (px + pw // 2 - footer.get_width() // 2, py + ph - 55))
        disclaimer = self.font_title.render(
            "SIMULATION ONLY — NOT A MEDICAL DEVICE",
            True, (150, 50, 50)
        )
        screen.blit(disclaimer, (px + pw // 2 - disclaimer.get_width() // 2, py + ph - 30))
