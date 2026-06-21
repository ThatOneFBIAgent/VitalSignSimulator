"""
VitalSign Pro — High-Fidelity Patient Monitor Replica.
Main monitor renderer — authentic hospital patient monitor layout.
Handles waveform sweep rendering, numeric panel, info bar, and all integration.

⚖️ LEGAL DISCLAIMER:
THIS SOFTWARE IS FOR SIMULATION AND EDUCATIONAL THEATER PURPOSES ONLY.
IT IS NOT A MEDICAL DEVICE. NEVER USE FOR REAL PATIENT MONITORING OR DIAGNOSIS.
THE AUTHOR ASSUMES NO LIABILITY FOR MISUSE.
"""
import pygame
import time
import math
import numpy as np
import threading
from datetime import datetime

from simulation import PhysioSim, ECG_LEADS
from alarms import AudioSystem, AlarmLogic
from effects import Effects
from config_menu import ConfigMenu
from routines import RoutineManager
from config_window import ConfigWindow
from diagnostics_window import DiagnosticsWindow

class MonitorDSP:
    """
    The 'Computer' side. Decouples the simulation (the 'leads') from the UI.
    Receives raw signals and R-wave events, and computes measured vitals.
    """
    def __init__(self):
        self.hr = 0.0
        self.spo2 = 100.0
        self.rr = 16.0
        self.bp_sys = 120.0
        self.bp_dia = 80.0
        self.bp_map = 93.0
        self.etco2 = 38.0
        self.temp = 37.0
        
        self._rr_intervals = []
        self._time_since_last_r = 0.0
        self.ecg_amplitude = 0.0
        self.hr_irregular = False

    def update(self, sim, dt, ecg_buffer):
        # Calculate HR from R-waves
        self._time_since_last_r += dt
        
        if sim.r_wave_detected:
            if self._time_since_last_r > 0.2: # blanking period
                self._rr_intervals.append(self._time_since_last_r)
                if len(self._rr_intervals) > 6:
                    self._rr_intervals.pop(0)
            self._time_since_last_r = 0.0
            
        if self._time_since_last_r > 2.5:
            # Asystole / No pulse
            self.hr = 0.0
            self._rr_intervals.clear()
            self.hr_irregular = False
        elif len(self._rr_intervals) > 0:
            avg_rr = sum(self._rr_intervals) / len(self._rr_intervals)
            self.hr = 60.0 / avg_rr
            
            if len(self._rr_intervals) >= 4:
                variance = sum((x - avg_rr)**2 for x in self._rr_intervals) / len(self._rr_intervals)
                if variance > 0.015:
                    self.hr_irregular = True
                elif variance < 0.005:
                    self.hr_irregular = False

        # Low-pass filter for other vitals to simulate sensor delay
        alpha = 0.05
        self.spo2 = self.spo2 * (1 - alpha) + sim.spo2 * alpha
        self.rr = self.rr * (1 - alpha) + sim.rr * alpha
        self.bp_sys = self.bp_sys * (1 - alpha) + sim.bp_sys * alpha
        self.bp_dia = self.bp_dia * (1 - alpha) + sim.bp_dia * alpha
        self.etco2 = self.etco2 * (1 - alpha) + sim.etco2 * alpha
        self.temp = self.temp * (1 - 0.01) + sim.temp * 0.01
        
        self.bp_map = self.bp_dia + (self.bp_sys - self.bp_dia) / 3.0
        
        # Calculate ECG amplitude for VFib detection
        valid_ecg = ecg_buffer[~np.isnan(ecg_buffer)]
        if len(valid_ecg) > 0:
            self.ecg_amplitude = np.max(valid_ecg) - np.min(valid_ecg)
        else:
            self.ecg_amplitude = 0.0

# ─── Layout Constants ───
WIDTH, HEIGHT = 1920, 1080
FPS = 60
INFO_BAR_H = 48
PANEL_W = 420
WAVE_W = WIDTH - PANEL_W   # 1500
WAVE_AREA_H = HEIGHT - INFO_BAR_H  # 1032

# ─── Colors (Defaults for standard theme) ───
from constants import THEMES

C_INFO_BG   = (16, 16, 24)
C_INFO_TXT  = (120, 120, 150)
C_DIM       = (60, 60, 80)

# ─── Waveform channel definitions ───
CHANNELS = [
    {"name": "II",    "key": "ecg",   "scale": 180, "offset": 0.0, "line_w": 3, "range": (-1.4, 1.6)},
    {"name": "Pleth", "key": "pleth", "scale": 150, "offset": 0.0, "line_w": 3, "range": (-0.1, 1.2)},
    {"name": "Resp",  "key": "resp",  "scale": 120, "offset": 0.0, "line_w": 2, "range": (-0.9, 0.9)},
    {"name": "ABP",   "key": "abp",   "scale": 1.1, "offset":-95,  "line_w": 3, "range": (20.0, 220.0)},
    {"name": "CO2",   "key": "co2",   "scale": 3.75, "offset":-15, "line_w": 3, "range": (0.0, 80.0)},
]


class WaveformChannel:
    """Manages the sweep buffer for a single waveform channel."""

    def __init__(self, width, y_top, y_bot, color, scale, offset, line_w, value_range=None):
        self.width = width
        self.y_top = y_top
        self.y_bot = y_bot
        self.y_mid = (y_top + y_bot) // 2
        self.h = y_bot - y_top
        self.color = color
        self.scale = scale
        self.offset = offset
        self.line_w = line_w
        self.value_range = value_range

        # Circular buffer: NaN means no data / gap
        self.buffer = np.full(width, np.nan, dtype=np.float64)
        self.sweep_x = 0.0
        self.sub_pixel = 0.0  # fractional pixel accumulator

    def feed(self, samples, sweep_speed):
        """
        Feed new samples. sweep_speed = pixels/second.
        Maps samples onto the pixel buffer at the current sweep position.
        """
        if not samples:
            return
        n = len(samples)
        # How many pixels these samples span (based on time)
        # But we control sweep speed independently of sample count
        # We advance a fixed amount per pixel
        samples_per_px = max(1, n / max(1, sweep_speed / 60.0))
        px_to_draw = n / samples_per_px

        self.sub_pixel += px_to_draw
        px_count = int(self.sub_pixel)
        self.sub_pixel -= px_count

        for i in range(px_count):
            # Pick the sample for this pixel
            si = int(i * samples_per_px) % n
            val = samples[si]

            ix = int(self.sweep_x) % self.width
            self.buffer[ix] = val

            # Clear gap ahead
            gap = 37
            for g in range(1, gap + 1):
                gi = (ix + g) % self.width
                self.buffer[gi] = np.nan

            self.sweep_x = (self.sweep_x + 1) % self.width

    def draw(self, surface, phosphor=True):
        """Draw the waveform onto the given surface."""
        points = []
        sweep_int = int(self.sweep_x) % self.width

        for x in range(self.width):
            val = self.buffer[x]
            if np.isnan(val):
                # Draw collected segment
                if len(points) >= 2:
                    pygame.draw.lines(surface, self._color_for_segment(x, sweep_int, phosphor),
                                      False, points, self.line_w)
                points = []
                continue

            y = self._map_value_to_y(val)
            y = max(self.y_top + 2, min(self.y_bot - 2, y))
            points.append((x, y))

            # If at a color transition point, break segment
            if len(points) > 60:
                pygame.draw.lines(surface, self._color_for_segment(x, sweep_int, phosphor),
                                  False, points, self.line_w)
                points = [points[-1]]  # Continue from last point

        if len(points) >= 2:
            pygame.draw.lines(surface, self._color_for_segment(self.width, sweep_int, phosphor),
                              False, points, self.line_w)

    def _color_for_segment(self, x, sweep_x, phosphor):
        """Optionally dim older segments for phosphor persistence effect."""
        if not phosphor:
            return self.color
        # Calculate age: how far behind the sweep
        age = (sweep_x - x) % self.width
        # Fade factor: recent = bright, old = dim
        fade = max(0.3, 1.0 - (age / self.width) * 0.7)
        return (
            int(self.color[0] * fade),
            int(self.color[1] * fade),
            int(self.color[2] * fade),
        )

    def _map_value_to_y(self, val):
        if self.value_range:
            lo, hi = self.value_range
            span = max(0.001, hi - lo)
            margin = max(8, int(self.h * 0.08))
            frac = (val - lo) / span
            frac = max(0.0, min(1.0, frac))
            return int((self.y_bot - margin) - frac * (self.h - margin * 2))
        return self.y_mid - int((val + self.offset) * self.scale)


class Monitor:
    def __init__(self):
        pygame.init()
        # Use standard resizable window but strip caption for borderless look
        self.screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        
        # Remove WS_CAPTION to allow native OS resizing without the ugly title bar
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16) # GWL_STYLE
        WS_CAPTION = 0x00C00000
        ctypes.windll.user32.SetWindowLongW(hwnd, -16, style & ~WS_CAPTION)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x27) # SWP_FRAMECHANGED
        
        pygame.display.set_caption("VitalSign Simulator")
        self.clock = pygame.time.Clock()
        
        self._dragging = False
        self._drag_offset = (0, 0)

        # Internal render surface at fixed logical resolution.
        # Everything is drawn here, then scaled to the actual window size.
        self.canvas = pygame.Surface((WIDTH, HEIGHT))

        # Core systems
        self.sim = PhysioSim()
        self.audio = AudioSystem()
        self.alarm_logic = AlarmLogic()
        self.fx = Effects(WIDTH, HEIGHT)
        self.routine_manager = RoutineManager(self.sim)
        self.dsp = MonitorDSP()
        
        self.alarm_box_style = "Red outline"
        self.differentiate_alarms = False
        
        # Customizable info bar fields
        self.hospital_name = "Patient Monitor"
        self.bed_name = "Bed 1"
        self.dept_name = "ICU"
        self.show_rec_status = True

        self.config = ConfigMenu(
            self.sim, self.alarm_logic, self.fx, self.audio,
            self.routine_manager, theme_callback=self.set_theme,
            initial_theme="Classic Hospital",
            monitor_ref=self
        )
        
        # New Standalone Config Window (OBS-Friendly)
        self.config_win = ConfigWindow(
            self.sim, self.alarm_logic, self.fx, self.audio,
            self.routine_manager, monitor=self
        )

        # Fonts
        self.font_big = pygame.font.SysFont("Consolas", 93, bold=True)
        self.font_med = pygame.font.SysFont("Consolas", 45, bold=True)
        self.font_sm = pygame.font.SysFont("Consolas", 24)
        self.font_xs = pygame.font.SysFont("Consolas", 19)
        self.font_label = pygame.font.SysFont("Consolas", 21, bold=True)
        self.font_unit = pygame.font.SysFont("Consolas", 21)

        self.theme_name = "Classic Hospital"
        self.theme = THEMES[self.theme_name]

        # Waveform channels
        ch_h = WAVE_AREA_H // len(CHANNELS)
        self.wave_channels = []
        for i, ch in enumerate(CHANNELS):
            y_top = INFO_BAR_H + i * ch_h
            y_bot = y_top + ch_h
            self.wave_channels.append(WaveformChannel(
                WAVE_W, y_top, y_bot, self.theme[ch["key"]], ch["scale"], ch["offset"], ch["line_w"], ch.get("range")
            ))

        self.sweep_speed = 225  # pixels per second
        self.show_ui = True
        self.show_grid = True
        self.show_12_lead_view = False
        self.show_debug_signals = False
        self.show_diagnostics_window = False
        self.lead_preview = {lead: np.full(360, np.nan, dtype=np.float64) for lead in ECG_LEADS}
        self.debug_buffers = {
            "Body ECG": np.full(520, np.nan, dtype=np.float64),
            "Monitor ECG": np.full(520, np.nan, dtype=np.float64),
            "R Gate": np.full(520, np.nan, dtype=np.float64),
            "Body CO2": np.full(520, np.nan, dtype=np.float64),
            "CO2 Gate": np.full(520, np.nan, dtype=np.float64),
            "Insp Gate": np.full(520, np.nan, dtype=np.float64),
        }
        self._diagnostics_lock = threading.Lock()
        self._diagnostics_snapshot = {}
        self.diagnostics_win = DiagnosticsWindow(self)
        self.fullscreen = False
        self.maximized = False
        self._windowed_size = self.screen.get_size()
        self._windowed_pos = None

        # Heart blink
        self.heart_on = False
        self.heart_timer = 0.0

        # Resize-pause state
        self.paused = False
        self._resize_cooldown = 0.0

        # Disclaimer state
        self.showing_disclaimer = True
        self.disclaimer_timer = 7.0
        self.disclaimer_btn_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 + 220, 300, 60)
        self.window_focused = True
        self.config_loading_until = 0.0
        self.config_cooldown_until = 0.0
        
        # Window Controls
        self.close_btn_rect = pygame.Rect(WIDTH - 50, 0, 50, INFO_BAR_H)
        self.max_btn_rect = pygame.Rect(WIDTH - 100, 0, 50, INFO_BAR_H)
        self.min_btn_rect = pygame.Rect(WIDTH - 150, 0, 50, INFO_BAR_H)
        
        self.watermark_dim = False
        self.uptime = 0.0

    def set_theme(self, theme_name):
        """Update active theme and propagate colors to wave channels."""
        if theme_name in THEMES:
            self.theme_name = theme_name
            self.theme = THEMES[theme_name]
            # Update each waveform channel's color
            for i, ch in enumerate(CHANNELS):
                self.wave_channels[i].color = self.theme[ch["key"]]

    def set_diagnostics_window_visible(self, visible):
        self.show_diagnostics_window = bool(visible)
        if self.show_diagnostics_window:
            self.diagnostics_win.show()
        else:
            self.diagnostics_win.close()

    def get_diagnostics_snapshot(self):
        with self._diagnostics_lock:
            return {
                "leads": {k: list(v) for k, v in self._diagnostics_snapshot.get("leads", {}).items()},
                "signals": {k: list(v) for k, v in self._diagnostics_snapshot.get("signals", {}).items()},
                "alarm": dict(self._diagnostics_snapshot.get("alarm", {})),
                "vitals": dict(self._diagnostics_snapshot.get("vitals", {})),
            }

    def _set_diagnostics_snapshot(self):
        alarm_params = dict(self.alarm_logic.alarming_params)
        with self._diagnostics_lock:
            self._diagnostics_snapshot = {
                "leads": {lead: self.lead_preview[lead].tolist() for lead in ECG_LEADS},
                "signals": {name: values.tolist() for name, values in self.debug_buffers.items()},
                "alarm": {
                    "priority": self.alarm_logic.active_alarm,
                    "message": self.alarm_logic.alarm_message,
                    "flash": self.alarm_logic.flash_state,
                    "led_left": self.alarm_logic.led_left,
                    "led_right": self.alarm_logic.led_right,
                    "params": alarm_params,
                },
                "vitals": {
                    "hr": self.dsp.hr,
                    "spo2": self.dsp.spo2,
                    "rr": self.dsp.rr,
                    "bp_sys": self.dsp.bp_sys,
                    "bp_dia": self.dsp.bp_dia,
                    "bp_map": self.dsp.bp_map,
                    "etco2": self.dsp.etco2,
                    "temp": self.dsp.temp,
                },
            }

    def _render_fit_text(self, text, font, color, max_width):
        """Render text trimmed to fit a fixed-width status area."""
        surf = font.render(text, True, color)
        if surf.get_width() <= max_width:
            return surf

        trimmed = text
        suffix = "..."
        while trimmed:
            candidate = trimmed.rstrip() + suffix
            surf = font.render(candidate, True, color)
            if surf.get_width() <= max_width:
                return surf
            trimmed = trimmed[:-1]
        return font.render(suffix, True, color)

    def _draw_grid(self):
        """Draw ECG-style grid on the waveform area."""
        if not self.show_grid:
            return
        # Minor grid
        for x in range(0, WAVE_W, 37):
            pygame.draw.line(self.canvas, self.theme["grid"], (x, INFO_BAR_H), (x, HEIGHT))
        for y in range(INFO_BAR_H, HEIGHT, 37):
            pygame.draw.line(self.canvas, self.theme["grid"], (0, y), (WAVE_W, y))
        # Major grid
        for x in range(0, WAVE_W, 187):
            pygame.draw.line(self.canvas, self.theme["grid_maj"], (x, INFO_BAR_H), (x, HEIGHT))
        for y in range(INFO_BAR_H, HEIGHT, 187):
            pygame.draw.line(self.canvas, self.theme["grid_maj"], (0, y), (WAVE_W, y))

    def _draw_info_bar(self):
        """Top info bar with patient info and time."""
        if self.paused:
            # Paused state: amber background with PAUSED text
            pygame.draw.rect(self.canvas, (40, 30, 5), (0, 0, WIDTH, INFO_BAR_H))
            pygame.draw.line(self.canvas, (80, 60, 10), (0, INFO_BAR_H - 1), (WIDTH, INFO_BAR_H - 1))
            paused_surf = self.font_sm.render("PAUSED", True, (255, 180, 0))
            self.canvas.blit(paused_surf, (WIDTH // 2 - paused_surf.get_width() // 2, 10))
            return

        pygame.draw.rect(self.canvas, C_INFO_BG, (0, 0, WIDTH, INFO_BAR_H))
        pygame.draw.line(self.canvas, self.theme["divider"], (0, INFO_BAR_H - 1), (WIDTH, INFO_BAR_H - 1))

        # Reserve the center LED housing before drawing any status text.
        led_w, led_h = 50, 14
        led_spacing = 10
        center_x = WIDTH // 2
        bezel_w = (led_w * 2) + led_spacing + 12
        left_status_max_w = center_x - bezel_w // 2 - 36

        # Patient info / Recording status
        if self.show_rec_status and self.routine_manager.is_playing:
            time_sec = int(self.routine_manager.elapsed)
            msg = f"● REC  |  Routine: {self.routine_manager.active_routine_name}  |  {time_sec // 60:02d}:{time_sec % 60:02d}"
            lbl = self._render_fit_text(msg, self.font_sm, (255, 50, 50), left_status_max_w)
        else:
            info_str = f"{self.hospital_name}  |  {self.bed_name}  |  {self.dept_name}"
            lbl = self._render_fit_text(info_str, self.font_sm, C_INFO_TXT, left_status_max_w)
        self.canvas.blit(lbl, (18, 10))

        # Relocate LEDs to Center of Info Bar (Aesthetic Overhaul)
        led_w, led_h = 50, 14
        led_spacing = 10
        # Position centered in the top bar
        center_x = WIDTH // 2
        lx = center_x - led_w - led_spacing // 2
        rx = center_x + led_spacing // 2
        led_y = 17
        
        # Draw LED Bezel/Housing
        bezel_w = (led_w * 2) + led_spacing + 12
        bezel_h = led_h + 12
        pygame.draw.rect(self.canvas, (25, 25, 30), (center_x - bezel_w // 2, led_y - 6, bezel_w, bezel_h), border_radius=4)
        pygame.draw.rect(self.canvas, (45, 45, 55), (center_x - bezel_w // 2, led_y - 6, bezel_w, bezel_h), 1, border_radius=4)

        # Draw LEDs with internal glow
        def draw_led(x, y, color):
            # Base
            pygame.draw.rect(self.canvas, color, (x, y, led_w, led_h), border_radius=3)
            # Gloss / Inner highlight
            if color != (30, 30, 35):
                highlight = (min(255, color[0] + 60), min(255, color[1] + 60), min(255, color[2] + 60))
                pygame.draw.line(self.canvas, highlight, (x + 3, y + 2), (x + led_w - 3, y + 2), 2)
                # Outer glow if active
                glow_surf = pygame.Surface((led_w + 20, led_h + 20), pygame.SRCALPHA)
                for r in range(1, 10):
                    alpha = int(40 * (1 - r/10))
                    pygame.draw.rect(glow_surf, (*color, alpha), (10-r, 10-r, led_w+r*2, led_h+r*2), border_radius=3+r)
                self.canvas.blit(glow_surf, (x - 10, y - 10))

        color_l = self.alarm_logic.led_left if self.alarm_logic.led_left else (30, 30, 35)
        draw_led(lx, led_y, color_l)
        
        color_r = self.alarm_logic.led_right if self.alarm_logic.led_right else (30, 30, 35)
        draw_led(rx, led_y, color_r)

        # Time (Shifted left to clear window buttons)
        now = datetime.now().strftime("%H:%M:%S")
        date_str = datetime.now().strftime("%m/%d/%Y")
        time_surf = self.font_sm.render(f"{date_str}  {now}", True, C_INFO_TXT)
        self.canvas.blit(time_surf, (WIDTH - time_surf.get_width() - 170, 10))

        # Alarm silence indicator
        if self.audio.muted:
            mute_surf = self.font_sm.render("AUDIO OFF", True, (255, 80, 80))
            mute_x = center_x + bezel_w // 2 + 18
            self.canvas.blit(mute_surf, (mute_x, 10))
            
        # Close Button (X)
        mx, my = pygame.mouse.get_pos()
        # Convert screen pos to canvas pos
        sw, sh = self.screen.get_size()
        cx, cy = mx * (WIDTH / sw), my * (HEIGHT / sh)
        
        if self.close_btn_rect.collidepoint(cx, cy):
            pygame.draw.rect(self.canvas, (200, 50, 50), self.close_btn_rect)
        elif self.max_btn_rect.collidepoint(cx, cy):
            pygame.draw.rect(self.canvas, (60, 60, 75), self.max_btn_rect)
        elif self.min_btn_rect.collidepoint(cx, cy):
            pygame.draw.rect(self.canvas, (60, 60, 75), self.min_btn_rect)
        
        # Draw Icons
        close_txt = self.font_label.render("X", True, (255, 255, 255))
        self.canvas.blit(close_txt, (self.close_btn_rect.centerx - close_txt.get_width() // 2, 
                                     self.close_btn_rect.centery - close_txt.get_height() // 2))
        
        max_txt = self.font_label.render("□", True, (200, 200, 220))
        self.canvas.blit(max_txt, (self.max_btn_rect.centerx - max_txt.get_width() // 2, 
                                    self.max_btn_rect.centery - max_txt.get_height() // 2))
        
        min_txt = self.font_label.render("_", True, (200, 200, 220))
        self.canvas.blit(min_txt, (self.min_btn_rect.centerx - min_txt.get_width() // 2, 
                                    self.min_btn_rect.centery - min_txt.get_height() // 2 - 5))

    def _draw_channel_labels(self):
        """Draw channel name labels on the left edge of each waveform."""
        for i, ch in enumerate(CHANNELS):
            ch_h = WAVE_AREA_H // len(CHANNELS)
            y = INFO_BAR_H + i * ch_h + 6
            name = self.sim.ecg_display_lead if ch["key"] == "ecg" else ch["name"]
            lbl = self.font_label.render(name, True, self.theme[ch["key"]])
            self.canvas.blit(lbl, (6, y))

    def _append_debug_samples(self, key, samples, max_new=80):
        if key not in self.debug_buffers or not samples:
            return
        arr = self.debug_buffers[key]
        take = min(max_new, len(samples), len(arr))
        values = np.array(samples[-take:], dtype=np.float64)
        arr[:-take] = arr[take:]
        arr[-take:] = values

    def _append_lead_samples(self, lead, samples, max_new=60):
        if lead not in self.lead_preview or not samples:
            return
        arr = self.lead_preview[lead]
        take = min(max_new, len(samples), len(arr))
        values = np.array(samples[-take:], dtype=np.float64)
        arr[:-take] = arr[take:]
        arr[-take:] = values

    def _draw_trace_in_rect(self, rect, samples, color, value_range=(-1.2, 1.2), line_w=1):
        x, y, w, h = rect
        valid = samples[~np.isnan(samples)]
        if len(valid) < 2:
            return
        lo, hi = value_range
        span = max(0.001, hi - lo)
        points = []
        for i, val in enumerate(samples):
            if np.isnan(val):
                continue
            px = x + int((i / max(1, len(samples) - 1)) * (w - 1))
            frac = max(0.0, min(1.0, (val - lo) / span))
            py = y + h - 3 - int(frac * (h - 6))
            points.append((px, py))
        if len(points) >= 2:
            pygame.draw.lines(self.canvas, color, False, points, line_w)

    def _draw_12_lead_panel(self):
        if not self.show_12_lead_view:
            return

        panel_w, panel_h = 1120, 420
        x0 = 34
        y0 = INFO_BAR_H + 56
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((5, 7, 10, 205))
        self.canvas.blit(panel, (x0, y0))
        pygame.draw.rect(self.canvas, (80, 100, 115), (x0, y0, panel_w, panel_h), 1)

        title = self.font_xs.render("12-LEAD VIEW", True, (160, 210, 230))
        self.canvas.blit(title, (x0 + 12, y0 + 8))

        cols, rows = 4, 3
        cell_w = (panel_w - 28) // cols
        cell_h = (panel_h - 42) // rows
        for idx, lead in enumerate(ECG_LEADS):
            col = idx % cols
            row = idx // cols
            cx = x0 + 14 + col * cell_w
            cy = y0 + 34 + row * cell_h
            rect = (cx + 38, cy + 8, cell_w - 48, cell_h - 18)
            pygame.draw.rect(self.canvas, (28, 36, 42), (cx, cy, cell_w - 8, cell_h - 8), 1)
            lbl = self.font_xs.render(lead, True, self.theme["ecg"])
            self.canvas.blit(lbl, (cx + 8, cy + 9))
            mid_y = rect[1] + rect[3] // 2
            pygame.draw.line(self.canvas, (22, 31, 35), (rect[0], mid_y), (rect[0] + rect[2], mid_y), 1)
            self._draw_trace_in_rect(rect, self.lead_preview[lead], self.theme["ecg"], (-1.4, 1.6), 1)

    def _draw_debug_signals(self):
        if not self.show_debug_signals:
            return

        panel_w, panel_h = 760, 310
        x0 = 40
        y0 = HEIGHT - panel_h - 54
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((2, 5, 8, 218))
        self.canvas.blit(panel, (x0, y0))
        pygame.draw.rect(self.canvas, (90, 120, 135), (x0, y0, panel_w, panel_h), 1)

        title = self.font_xs.render("BODY -> COMPUTER TEST VIEW", True, (150, 220, 235))
        self.canvas.blit(title, (x0 + 12, y0 + 8))

        rows = [
            ("Body ECG", self.theme["ecg"], (-1.4, 1.6)),
            ("Monitor ECG", (255, 210, 130), (-1.4, 1.6)),
            ("R Gate", (80, 200, 255), (-0.1, 1.2)),
            ("Body CO2", self.theme["co2"], (0.0, 80.0)),
            ("CO2 Gate", (140, 255, 140), (-0.1, 1.2)),
            ("Insp Gate", (190, 160, 255), (-0.1, 1.2)),
        ]
        row_h = 43
        for i, (name, color, value_range) in enumerate(rows):
            y = y0 + 34 + i * row_h
            label = self.font_xs.render(name, True, color)
            self.canvas.blit(label, (x0 + 12, y + 8))
            rect = (x0 + 126, y + 5, panel_w - 144, row_h - 10)
            pygame.draw.line(self.canvas, (24, 34, 38), (rect[0], rect[1] + rect[3] // 2), (rect[0] + rect[2], rect[1] + rect[3] // 2), 1)
            self._draw_trace_in_rect(rect, self.debug_buffers[name], color, value_range, 1)

    def _draw_channel_dividers(self):
        """Draw horizontal separators between waveform channels."""
        ch_h = WAVE_AREA_H // len(CHANNELS)
        for i in range(1, len(CHANNELS)):
            y = INFO_BAR_H + i * ch_h
            pygame.draw.line(self.canvas, self.theme["divider"], (0, y), (WAVE_W, y))

    def _draw_numeric_panel(self):
        """Right-side numeric readout panel."""
        px = WAVE_W
        pygame.draw.rect(self.canvas, self.theme["panel"], (px, INFO_BAR_H, PANEL_W, WAVE_AREA_H))
        pygame.draw.line(self.canvas, self.theme["divider"], (px, INFO_BAR_H), (px, HEIGHT), 2)

        al = self.alarm_logic.alarming_params
        d = self.dsp

        # ── HR ──
        y = INFO_BAR_H + 15
        hr_str = f"{int(d.hr)}" if d.hr > 5 else "---"
        self._draw_param_block(px, y, "HR", hr_str, "bpm", self.theme["ecg"], large=True, alarm_status=al.get("hr"))
        # Heart blink indicator (moved down to avoid alarm bar)
        if self.heart_on:
            hx, hy = px + PANEL_W - 52, y + 62
            pygame.draw.circle(self.canvas, (255, 30, 30), (hx, hy), 12)
            pygame.draw.circle(self.canvas, (255, 30, 30), (hx + 15, hy), 12)
            pts = [(hx - 12, hy + 4), (hx + 7, hy + 27), (hx + 27, hy + 4)]
            pygame.draw.polygon(self.canvas, (255, 30, 30), pts)

        # ── SpO2 ──
        y += 195
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        spo2_str = f"{int(d.spo2)}" if d.spo2 > 10 else "---"
        self._draw_param_block(px, y, "SpO2", spo2_str, "%", self.theme["pleth"], large=True, alarm_status=al.get("spo2"))

        # ── RR ──
        y += 195
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        rr_str = f"{int(d.rr)}" if d.rr > 2 else "---"
        self._draw_param_block(px, y, "RR", rr_str, "rpm", self.theme["resp"], large=False, alarm_status=al.get("rr"))

        # ── ABP ──
        y += 150
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        bp_str = f"{int(d.bp_sys)}/{int(d.bp_dia)}" if d.bp_sys > 20 else "---/---"
        self._draw_param_block(px, y, "ABP", bp_str, "mmHg", self.theme["abp"], large=False, alarm_status=al.get("abp"))
        # MAP
        if not (al.get("abp") == "low" and not self.alarm_logic.flash_state):
            map_str = f"({int(d.bp_map)})" if d.bp_map > 10 else "(---)"
            map_surf = self.font_sm.render(map_str, True, self.theme["abp"])
            self.canvas.blit(map_surf, (px + 270, y + 75))

        # ── EtCO2 ──
        y += 150
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        etco2_str = "---"
        if self.sim.probe_etco2:
            etco2_str = f"{int(d.etco2)}" if d.etco2 > 5 else "---"
        self._draw_param_block(px, y, "EtCO2", etco2_str, "mmHg", self.theme["co2"], large=False, alarm_status=al.get("etco2"))

        # ── Temp ──
        y += 135
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        temp_str = f"{d.temp:.1f}" if self.sim.probe_temp else "---"
        self._draw_param_block(px, y, "Temp", temp_str, "°C", self.theme["temp"], large=False)

    def _draw_param_block(self, px, y, label, value_str, unit, color, large=False, alarm_status=None):
        """Draw a single parameter block: label, big number, unit."""
        rect_h = 160 if large else 125
        box_rect = (px + 10, y - 5, PANEL_W - 20, rect_h)
        bg_color = self.theme["panel"]
        
        is_inverted = self.alarm_box_style in ["Inverted red", "Inverted colored"]
        is_colored = self.alarm_box_style in ["Colored outline", "Inverted colored"]
        alarm_color = color if is_colored else (255, 50, 50)
        
        # Differentiate behavior: 
        # If enabled: High values = Solid box, Low values = Flickering box
        # If joined: Both flicker
        if self.differentiate_alarms and alarm_status == "high":
            draw_box = True
        else:
            draw_box = bool(alarm_status and self.alarm_logic.flash_state)
        
        # Pulsing text logic: blink if low, steady if high (standard clinical behavior)
        show_text = True
        if alarm_status == "low" and not self.alarm_logic.flash_state:
            show_text = False

        # Draw the alarm box background or outline
        if draw_box:
            if is_inverted:
                pygame.draw.rect(self.canvas, alarm_color, box_rect)
            else:
                pygame.draw.rect(self.canvas, alarm_color, box_rect, 3)

        if show_text:
            text_color = color
            lbl_color = color
            unit_color = C_DIM
            use_glow = True

            if draw_box and is_inverted:
                if alarm_status == "low":
                    # Text shaped cutout (text acts as a transparent hole to the panel background)
                    text_color = bg_color
                    lbl_color = bg_color
                    unit_color = bg_color
                    use_glow = False
                elif alarm_status == "high":
                    # Boxy cutout (draw a smaller background colored box inside the inverted box)
                    cutout_rect = (px + 18, y + 3, PANEL_W - 36, rect_h - 16)
                    pygame.draw.rect(self.canvas, bg_color, cutout_rect)
                    # Text colors remain standard

            # Label
            if draw_box and is_inverted and alarm_status == "low":
                # Thicker cutout for label
                lbl_surf = self.font_label.render(label, True, lbl_color)
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        self.canvas.blit(lbl_surf, (px + 22 + dx, y + dy))
            else:
                lbl = self.font_label.render(label, True, lbl_color)
                self.canvas.blit(lbl, (px + 22, y))

            # Value
            font = self.font_big if large else self.font_med
            if use_glow:
                self.fx.render_glow_text(self.canvas, font, value_str, text_color, (px + 22, y + 27))
            else:
                # Thicker cutout for value (3x3 grid of blits to bolden it)
                val_surf = font.render(value_str, True, text_color)
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        self.canvas.blit(val_surf, (px + 22 + dx, y + 27 + dy))

            # Unit
            val_w = font.size(value_str)[0]
            if draw_box and is_inverted and alarm_status == "low":
                # Thicker cutout for unit
                u_surf = self.font_unit.render(unit, True, unit_color)
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        self.canvas.blit(u_surf, (px + 30 + val_w + dx, y + (75 if large else 52) + dy))
            else:
                u = self.font_unit.render(unit, True, unit_color)
                self.canvas.blit(u, (px + 30 + val_w, y + (75 if large else 52)))



    def _draw_alarm_bar(self):
        """Draw alarm banner at top when alarm is active."""
        if not self.alarm_logic.active_alarm:
            return
        if not self.alarm_logic.flash_state:
            return

        is_high = self.alarm_logic.active_alarm == "high"
        color = (200, 0, 0) if is_high else (200, 180, 0)
        text_color = (255, 255, 255) if is_high else (0, 0, 0)

        bar_h = 54
        bar_y = INFO_BAR_H
        pygame.draw.rect(self.canvas, color, (0, bar_y, WIDTH, bar_h))
        msg = self.alarm_logic.alarm_message
        txt = self.font_med.render(msg, True, text_color)
        self.canvas.blit(txt, (WIDTH // 2 - txt.get_width() // 2, bar_y + 3))

    def _draw_status_bar(self):
        """Bottom-left status hints."""
        if self.showing_disclaimer:
            return
        if self.config_win.is_running:
            hints = "A: Ack  |  F11: Fullscreen  |  ESC: Exit"
        else:
            hints = "TAB: Config  |  A: Ack  |  S: Mute  |  U: Toggle UI  |  F11: Fullscreen  |  ESC: Exit"
        surf = self.font_xs.render(hints, True, (50, 50, 65))
        self.canvas.blit(surf, (12, HEIGHT - 27))

    def _draw_config_loading_overlay(self):
        if self.config_win.is_ready or time.monotonic() >= self.config_loading_until:
            return

        box_w, box_h = 420, 96
        x = WIDTH // 2 - box_w // 2
        y = INFO_BAR_H + 52
        panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        panel.fill((8, 8, 14, 230))
        self.canvas.blit(panel, (x, y))
        pygame.draw.rect(self.canvas, (80, 80, 105), (x, y, box_w, box_h), 2, border_radius=6)
        dots = "." * (int(time.monotonic() * 4) % 4)
        title = self.font_sm.render(f"LOADING SETTINGS{dots}", True, (80, 200, 255))
        sub = self.font_xs.render("Opening detached configuration panel", True, C_INFO_TXT)
        self.canvas.blit(title, (x + box_w // 2 - title.get_width() // 2, y + 22))
        self.canvas.blit(sub, (x + box_w // 2 - sub.get_width() // 2, y + 58))

    def _request_config_window(self):
        now = time.monotonic()
        self.config_loading_until = now + 1.4
        if now < self.config_cooldown_until:
            return

        self.config_cooldown_until = now + 0.8
        self.config_win.show()

    # --- START OF LEGAL PROTECTION BLOCK ---
    # The following functions are CRITICAL for the developer's legal protection.
    # Tampering with or removing the watermark or disclaimer code may expose
    # the modifier to severe legal liability if the software is subsequently
    # used in a clinical or real-world medical setting.
    
    def _draw_watermark(self):
        """
        Permanent watermark to remind users of the simulation nature.
        This must remain visible at all times during operation.
        """
        # Minimum visibility threshold enforced to prevent liability
        opacity = 65 if self.watermark_dim else 125
        
        color = (opacity, opacity, opacity)
        msg = "NOT FOR MEDICAL USE — SIMULATION ONLY"
        wm_surf = self.font_sm.render(msg, True, color)
        # Position at bottom right, slightly above the edge
        self.canvas.blit(wm_surf, (WIDTH - wm_surf.get_width() - 25, HEIGHT - 35))

    def _draw_disclaimer(self):
        """
        Mandatory legal disclaimer screen. 
        Requires explicit user acknowledgement before proceeding.
        """
        self.canvas.fill((5, 5, 8))
        
        # Border (Wider and taller to accommodate comprehensive legal text)
        pygame.draw.rect(self.canvas, (80, 80, 100), (WIDTH//2 - 650, HEIGHT//2 - 320, 1300, 640), 4)
        
        # Warning Header
        header = self.font_med.render("⚠️ MANDATORY LEGAL & MEDICAL DISCLAIMER", True, (255, 180, 0))
        self.canvas.blit(header, (WIDTH//2 - header.get_width()//2, HEIGHT//2 - 270))
        
        # Comprehensive legal text
        lines = [
            "THIS SOFTWARE IS FOR SIMULATION, EDUCATIONAL THEATER, AND ENTERTAINMENT PURPOSES ONLY.",
            "",
            "1. NOT A MEDICAL DEVICE: This software is NOT a medical device, diagnostic tool, or monitor.",
            "It has not been cleared or approved by any health authority (e.g., FDA, EMA).",
            "",
            "2. NO CLINICAL USE: This software must NEVER be used in a real clinical setting, for monitoring",
            "actual patients, for medical diagnosis, or for making clinical decisions.",
            "",
            "3. NO LIABILITY: The author(s) assume ZERO LIABILITY for any injury, death, or legal",
            "consequences resulting from the misuse or unauthorized modification of this software.",
            "",
            "4. USER ACKNOWLEDGEMENT: By clicking 'I UNDERSTAND', you accept all risks and agree",
            "that you are solely responsible for ensuring this software is not used for real patient care."
        ]
        
        for i, line in enumerate(lines):
            color = (255, 100, 100) if i == 0 else (210, 210, 220)
            surf = self.font_sm.render(line, True, color)
            self.canvas.blit(surf, (WIDTH//2 - surf.get_width()//2, HEIGHT//2 - 180 + i * 30))
            
        # Button
        btn_active = self.disclaimer_timer <= 0
        btn_color = (0, 140, 70) if btn_active else (45, 45, 50)
        txt_color = (255, 255, 255) if btn_active else (100, 100, 110)
        
        pygame.draw.rect(self.canvas, btn_color, self.disclaimer_btn_rect, border_radius=8)
        pygame.draw.rect(self.canvas, (180, 180, 180), self.disclaimer_btn_rect, 2, border_radius=8)
        
        btn_text = "I UNDERSTAND" if btn_active else f"READING... ({int(self.disclaimer_timer + 1)})"
        btn_surf = self.font_sm.render(btn_text, True, txt_color)
        self.canvas.blit(btn_surf, (self.disclaimer_btn_rect.centerx - btn_surf.get_width()//2, 
                                     self.disclaimer_btn_rect.centery - btn_surf.get_height()//2))
    # --- END OF LEGAL PROTECTION BLOCK ---

    def _update(self, dt):
        """Main update tick."""
        # Safety check: ensure mandatory safety watermark opacity hasn't been tampered with.
        # This is required to prevent the simulation from being misused for real medical care.
        if (65 if self.watermark_dim else 125) < 65:
            raise RuntimeError("SAFETY ERROR: The mandatory medical disclaimer watermark has been tampered with. "
                               "Simulation halted to prevent potential clinical misuse.")
        
        # Ensure the _verify_safety definition exists
        if not hasattr(self.sim.__class__, '_verify_safety') or not callable(getattr(self.sim.__class__, '_verify_safety', None)):
            raise RuntimeError("FATAL EXCEPTION: Mandatory safety verification method 'PhysioSim._verify_safety' has been deleted or tampered with. Execution halted to prevent unlawful modification.")

        if self.showing_disclaimer:
            if self.disclaimer_timer > 0 and self._is_window_foreground():
                self.disclaimer_timer -= dt
            return

        if self.sim.cal_time > 0:
            self.sim.cal_time -= dt

        # Handle resize cooldown
        if self._resize_cooldown > 0:
            self._resize_cooldown -= dt
            if self._resize_cooldown <= 0:
                self.paused = False
                self._resize_cooldown = 0.0

        if self.paused:
            return  # Skip all simulation while paused

        self.routine_manager.update(dt)
        self.sim.update_vitals()
        data = self.sim.step(dt)

        # Feed waveform channels
        for i, ch in enumerate(CHANNELS):
            samples = data.get(ch["key"], [])
            self.wave_channels[i].feed(samples, self.sweep_speed)

        lead_data = data.get("ecg_leads", {})
        for lead in ECG_LEADS:
            self._append_lead_samples(lead, lead_data.get(lead, []))

        pure = data.get("pure", {})
        gates = data.get("gates", {})
        self._append_debug_samples("Body ECG", pure.get("ecg", []))
        self._append_debug_samples("Monitor ECG", data.get("ecg", []))
        self._append_debug_samples("R Gate", gates.get("r_gate", []))
        self._append_debug_samples("Body CO2", pure.get("co2", []))
        self._append_debug_samples("CO2 Gate", gates.get("co2_gate", []))
        self._append_debug_samples("Insp Gate", gates.get("resp_insp", []))

        # Update DSP
        ecg_buffer = self.wave_channels[0].buffer
        self.dsp.update(self.sim, dt, ecg_buffer)

        self.uptime += dt

        # Pulse beep on R-wave (pitch modulated by HR)
        if self.sim.r_wave_detected:
            self.audio.play_pulse(self.dsp.hr)
            self.heart_on = True
            self.heart_timer = 0.12

        if self.heart_timer > 0:
            self.heart_timer -= dt
            if self.heart_timer <= 0:
                self.heart_on = False

        # Alarm logic
        prev_p = self.alarm_logic.active_alarm
        prev_m = self.alarm_logic.alarm_message
        priority = self.alarm_logic.update(self.dsp, dt)
        
        # If a NEW alarm type or message occurs, break the silence
        if priority != prev_p or self.alarm_logic.alarm_message != prev_m:
            if priority and "warning" not in priority:
                self.audio.silence_timer = 0.0
        
        # Suppress alarms during boot sequence
        if self.uptime < 6.0:
            priority = None
            self.alarm_logic.active_alarm = None
            self.alarm_logic.led_left = None
            self.alarm_logic.led_right = None
            self.alarm_logic.play_beep = False
            
        self.audio.update(dt, priority)
        
        if self.alarm_logic.play_beep:
            self.audio.play_beep()

        self._set_diagnostics_snapshot()

    def acknowledge(self):
        """Silences alarms and clears unacknowledged state."""
        self.alarm_logic.unack_timer = 0.0
        self.audio.acknowledge()
        # You could also add a 'silenced' flag to AlarmLogic if you wanted 
        # to prevent it from re-triggering for a duration.

    def _draw(self):
        """Main draw routine. Renders to internal canvas, then scales to window."""
        if not self.showing_disclaimer:
            self.canvas.fill(self.theme["bg"])
            
            if self.show_grid:
                self._draw_grid()
            
            for wc in self.wave_channels:
                wc.draw(self.canvas, phosphor=self.fx.enabled["phosphor"])

            self._draw_12_lead_panel()
            self._draw_debug_signals()
            
            # Boot-up Fade In Overlay (Faster)
            if self.uptime < 2.0:
                alpha = 255
                if self.uptime > 0.5:
                    alpha = int(255 * (1.0 - (self.uptime - 0.5) / 1.5))
                if alpha > 0:
                    overlay = pygame.Surface((WAVE_W, WAVE_AREA_H))
                    overlay.fill(self.theme["bg"])
                    overlay.set_alpha(alpha)
                    self.canvas.blit(overlay, (0, INFO_BAR_H))
            
            # Boot-up Calibrating Text
            if self.sim.cal_time > 0:
                dots = "." * (int(self.uptime * 3) % 4)
                cal_text = f"CALIBRATING{dots}"
                self.fx.render_glow_text(self.canvas, self.font_med, cal_text, (100, 255, 150), (WAVE_W // 2 - 120, INFO_BAR_H + WAVE_AREA_H // 2))
                
            self._draw_channel_dividers()
            self._draw_channel_labels()
            self._draw_numeric_panel()
            self._draw_alarm_bar()
            self._draw_info_bar()
            self._draw_status_bar()
            self._draw_config_loading_overlay()
            
            if self.config.visible:
                self.config.draw(self.canvas, WIDTH, HEIGHT)
                
            self._draw_watermark()

            # CRT effects
            self.fx.apply_scanlines(self.canvas)
            self.fx.apply_vignette(self.canvas)
        else:
            self._draw_disclaimer()


        # --- Scale canvas to fill the actual window ---
        win_w, win_h = self.screen.get_size()
        if (win_w, win_h) != (WIDTH, HEIGHT):
            scaled = pygame.transform.smoothscale(self.canvas, (win_w, win_h))
            self.screen.blit(scaled, (0, 0))
        else:
            self.screen.blit(self.canvas, (0, 0))

        pygame.display.flip()

    def _get_window_pos(self):
        import ctypes
        from ctypes import wintypes
        hwnd = pygame.display.get_wm_info()["window"]
        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top)

    def _set_window_pos(self, x, y):
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        # SWP_NOSIZE = 1, SWP_NOZORDER = 4
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)

    def _get_work_area(self):
        import ctypes
        from ctypes import wintypes

        hwnd = pygame.display.get_wm_info()["window"]
        user32 = ctypes.windll.user32
        monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            rect = info.rcWork
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top

        display = pygame.display.Info()
        return 0, 0, display.current_w, display.current_h

    def _is_window_foreground(self):
        try:
            import ctypes
            hwnd = pygame.display.get_wm_info()["window"]
            return ctypes.windll.user32.GetForegroundWindow() == hwnd
        except Exception:
            return self.window_focused and pygame.key.get_focused()

    def _trigger_native_drag(self):
        """Invoke Win32 native dragging — eliminates jitter."""
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        WM_NCLBUTTONDOWN = 0xA1
        HTCAPTION = 2
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)

    def _minimize_window(self):
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        ctypes.windll.user32.ShowWindow(hwnd, 6) # SW_MINIMIZE = 6

    def _toggle_maximize(self):
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        if getattr(self, "maximized", False):
            ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE = 9
            self.maximized = False
        else:
            ctypes.windll.user32.ShowWindow(hwnd, 3) # SW_MAXIMIZE = 3
            self.maximized = True

    def _apply_borderless_style(self):
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
        WS_CAPTION = 0x00C00000
        ctypes.windll.user32.SetWindowLongW(hwnd, -16, style & ~WS_CAPTION)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x27)

    def _toggle_fullscreen(self):
        if self.fullscreen:
            size = self._windowed_size or (1280, 720)
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
            self._apply_borderless_style()
            if self._windowed_pos:
                self._set_window_pos(*self._windowed_pos)
            self.fullscreen = False
            return

        self._windowed_size = self.screen.get_size()
        try:
            self._windowed_pos = self._get_window_pos()
        except Exception:
            self._windowed_pos = None

        x, y, w, h = self._get_work_area()
        self.screen = pygame.display.set_mode((w, h), pygame.NOFRAME)
        self._set_window_pos(x, y)
        self.fullscreen = True
        self.maximized = False

    def run(self):
        """Main application loop."""
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.1)  # Cap dt to prevent alarm spikes after dragging/freezes

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == getattr(pygame, "WINDOWFOCUSGAINED", -1):
                    self.window_focused = True
                elif event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
                    self.window_focused = False
                    
                if event.type == pygame.VIDEORESIZE:
                    if not self.fullscreen:
                        # Re-apply mode and remove WS_CAPTION to maintain custom resizable state
                        self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                        self._windowed_size = (event.w, event.h)
                        import ctypes
                        hwnd = pygame.display.get_wm_info()["window"]
                        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
                        WS_CAPTION = 0x00C00000
                        ctypes.windll.user32.SetWindowLongW(hwnd, -16, style & ~WS_CAPTION)
                        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x27)
                
                if self.showing_disclaimer:
                    if event.type == pygame.MOUSEBUTTONDOWN and self.disclaimer_timer <= 0:
                        mx, my = event.pos
                        sw, sh = self.screen.get_size()
                        cw, ch = self.canvas.get_size()
                        cx = mx * (cw / sw)
                        cy = my * (ch / sh)
                        if self.disclaimer_btn_rect.collidepoint(cx, cy):
                            self.showing_disclaimer = False
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    sw, sh = self.screen.get_size()
                            
                    cx, cy = mx * (WIDTH / sw), my * (HEIGHT / sh)
                    
                    if self.close_btn_rect.collidepoint(cx, cy):
                        running = False
                    elif self.max_btn_rect.collidepoint(cx, cy):
                        if self.fullscreen:
                            self._toggle_fullscreen()
                        else:
                            self._toggle_maximize()
                    elif self.min_btn_rect.collidepoint(cx, cy):
                        self._minimize_window()
                    elif cy < INFO_BAR_H and not self.fullscreen and not self.maximized:
                        self._trigger_native_drag()

                if event.type == pygame.KEYDOWN:
                    # Config menu intercepts keys when open
                    if self.config.visible:
                        if event.key == pygame.K_TAB or event.key == pygame.K_ESCAPE:
                            self.config.toggle()
                        else:
                            self.config.handle_key(event.key)
                        continue

                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_TAB:
                        self._request_config_window()
                    elif event.key == pygame.K_a:
                        self.acknowledge()
                    elif event.key == pygame.K_u:
                        self.show_ui = not self.show_ui
                    elif event.key == pygame.K_s:
                        muted = self.audio.toggle_mute()
                    elif event.key == pygame.K_g:
                        self.show_grid = not self.show_grid
                    elif event.key == pygame.K_F11:
                        self._toggle_fullscreen()
                    elif event.key == pygame.K_SPACE:
                        if not self.routine_manager.is_playing:
                            self.routine_manager.elapsed = 0
                            self.routine_manager.current_step = 0
                        self.routine_manager.toggle_play()
                    elif event.key == pygame.K_b:
                        # Reset routine and vitals to baseline
                        self.routine_manager.is_playing = False
                        self.routine_manager.elapsed = 0
                        self.routine_manager.current_step = 0
                        from constants import PRESETS
                        self.sim.set_preset(PRESETS["Healthy Adult"])

            # Resume alarm audio if coming out of pause
            if not self.paused and self.audio.alarm_playing:
                self.audio.ch_alarm.unpause()

            self._update(dt)
            self._draw()

        self.config_win.close()
        self.diagnostics_win.close()
        if self.config_win.thread and self.config_win.thread.is_alive():
            self.config_win.thread.join(timeout=1.0)
        if self.diagnostics_win.thread and self.diagnostics_win.thread.is_alive():
            self.diagnostics_win.thread.join(timeout=1.0)
        pygame.quit()
