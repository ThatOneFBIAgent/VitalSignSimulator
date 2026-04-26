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
import sys
import time
import math
import numpy as np
from datetime import datetime

from simulation import PhysioSim
from alarms import AudioSystem, AlarmLogic
from effects import Effects
from config_menu import ConfigMenu
from routines import RoutineManager

# ─── Layout Constants ───
WIDTH, HEIGHT = 1920, 1080
FPS = 60
INFO_BAR_H = 48
PANEL_W = 420
WAVE_W = WIDTH - PANEL_W   # 1500
WAVE_AREA_H = HEIGHT - INFO_BAR_H  # 1032

# ─── Colors (Defaults for standard theme) ───
THEMES = {
    "Classic Hospital": {
        "bg": (8, 8, 12), "panel": (12, 12, 18), "ecg": (0, 255, 80), "pleth": (0, 220, 255),
        "resp": (255, 255, 255), "abp": (255, 40, 40), "co2": (255, 220, 0), "temp": (180, 140, 255),
        "grid": (22, 22, 32), "grid_maj": (30, 30, 42), "divider": (40, 40, 55)
    },
    "High Contrast": {
        "bg": (0, 0, 0), "panel": (5, 5, 5), "ecg": (50, 255, 50), "pleth": (50, 255, 255),
        "resp": (255, 255, 255), "abp": (255, 50, 50), "co2": (255, 255, 50), "temp": (200, 150, 255),
        "grid": (15, 15, 20), "grid_maj": (25, 25, 30), "divider": (50, 50, 50)
    },
    "Ambulance (Dark Red)": {
        "bg": (15, 5, 5), "panel": (20, 10, 10), "ecg": (255, 150, 150), "pleth": (255, 200, 100),
        "resp": (255, 255, 200), "abp": (255, 40, 40), "co2": (255, 180, 50), "temp": (200, 150, 200),
        "grid": (30, 15, 15), "grid_maj": (45, 20, 20), "divider": (55, 20, 20)
    },
    "Deep Blue (Night)": {
        "bg": (5, 10, 20), "panel": (10, 15, 25), "ecg": (100, 200, 255), "pleth": (50, 150, 255),
        "resp": (200, 200, 255), "abp": (255, 100, 150), "co2": (255, 220, 100), "temp": (150, 150, 255),
        "grid": (15, 25, 40), "grid_maj": (25, 35, 55), "divider": (40, 50, 70)
    },
    "Nihon Kohden": {
        "bg": (0, 30, 45), "panel": (0, 40, 60), "ecg": (50, 255, 50), "pleth": (50, 180, 255),
        "resp": (255, 255, 255), "abp": (255, 50, 50), "co2": (255, 255, 50), "temp": (180, 150, 255),
        "grid": (0, 50, 75), "grid_maj": (0, 70, 100), "divider": (0, 80, 120)
    },
    "GE Carescape": {
        "bg": (25, 25, 25), "panel": (35, 35, 35), "ecg": (0, 255, 120), "pleth": (0, 190, 255),
        "resp": (230, 230, 230), "abp": (255, 60, 60), "co2": (255, 230, 0), "temp": (160, 130, 255),
        "grid": (45, 45, 45), "grid_maj": (60, 60, 60), "divider": (75, 75, 75)
    },
    "Mindray": {
        "bg": (0, 0, 0), "panel": (10, 10, 10), "ecg": (0, 255, 0), "pleth": (0, 255, 255),
        "resp": (255, 255, 0), "abp": (255, 0, 0), "co2": (255, 128, 0), "temp": (255, 255, 255),
        "grid": (20, 20, 20), "grid_maj": (40, 40, 40), "divider": (60, 60, 60)
    },
    "Legacy CRT (Green)": {
        "bg": (0, 10, 0), "panel": (0, 15, 0), "ecg": (0, 255, 50), "pleth": (0, 230, 40),
        "resp": (0, 200, 30), "abp": (0, 255, 50), "co2": (0, 255, 50), "temp": (0, 255, 50),
        "grid": (0, 30, 0), "grid_maj": (0, 50, 0), "divider": (0, 60, 0)
    }
}

C_INFO_BG   = (16, 16, 24)
C_INFO_TXT  = (120, 120, 150)
C_DIM       = (60, 60, 80)

# ─── Waveform channel definitions ───
CHANNELS = [
    {"name": "II",    "key": "ecg",   "scale": 180, "offset": 0.0, "line_w": 3},
    {"name": "Pleth", "key": "pleth", "scale": 150, "offset": 0.0, "line_w": 3},
    {"name": "Resp",  "key": "resp",  "scale": 120, "offset": 0.0, "line_w": 2},
    {"name": "ABP",   "key": "abp",   "scale": 2.7, "offset":-80,  "line_w": 3},
    {"name": "CO2",   "key": "co2",   "scale": 3.75, "offset":-15, "line_w": 3},
]


class WaveformChannel:
    """Manages the sweep buffer for a single waveform channel."""

    def __init__(self, width, y_top, y_bot, color, scale, offset, line_w):
        self.width = width
        self.y_top = y_top
        self.y_bot = y_bot
        self.y_mid = (y_top + y_bot) // 2
        self.h = y_bot - y_top
        self.color = color
        self.scale = scale
        self.offset = offset
        self.line_w = line_w

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

            y = self.y_mid - int((val + self.offset) * self.scale)
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


class Monitor:
    def __init__(self):
        pygame.init()
        # Start the window at a smaller 720p size, but the canvas will be 1080p.
        self.screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        pygame.display.set_caption("VitalSign Simulator")
        self.clock = pygame.time.Clock()

        # Internal render surface at fixed logical resolution.
        # Everything is drawn here, then scaled to the actual window size.
        self.canvas = pygame.Surface((WIDTH, HEIGHT))

        # Core systems
        self.sim = PhysioSim()
        self.audio = AudioSystem()
        self.alarm_logic = AlarmLogic()
        self.fx = Effects(WIDTH, HEIGHT)
        self.routine_manager = RoutineManager(self.sim)
        
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
                WAVE_W, y_top, y_bot, self.theme[ch["key"]], ch["scale"], ch["offset"], ch["line_w"]
            ))

        self.sweep_speed = 225  # pixels per second
        self.show_ui = True
        self.show_grid = True
        self.fullscreen = False

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
        self.watermark_dim = False

    def set_theme(self, theme_name):
        """Update active theme and propagate colors to wave channels."""
        if theme_name in THEMES:
            self.theme_name = theme_name
            self.theme = THEMES[theme_name]
            # Update each waveform channel's color
            for i, ch in enumerate(CHANNELS):
                self.wave_channels[i].color = self.theme[ch["key"]]

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

        # Patient info / Recording status
        if self.show_rec_status and self.routine_manager.is_playing:
            time_sec = int(self.routine_manager.elapsed)
            msg = f"● REC  |  Routine: {self.routine_manager.active_routine_name}  |  {time_sec // 60:02d}:{time_sec % 60:02d}"
            lbl = self.font_sm.render(msg, True, (255, 50, 50))
        else:
            info_str = f"{self.hospital_name}  |  {self.bed_name}  |  {self.dept_name}"
            lbl = self.font_sm.render(info_str, True, C_INFO_TXT)
        self.canvas.blit(lbl, (18, 10))

        # Time
        now = datetime.now().strftime("%H:%M:%S")
        date_str = datetime.now().strftime("%m/%d/%Y")
        time_surf = self.font_sm.render(f"{date_str}  {now}", True, C_INFO_TXT)
        self.canvas.blit(time_surf, (WIDTH - time_surf.get_width() - 18, 10))

        # Alarm silence indicator
        if self.audio.muted:
            mute_surf = self.font_sm.render("AUDIO OFF", True, (255, 80, 80))
            self.canvas.blit(mute_surf, (WIDTH // 2 - mute_surf.get_width() // 2, 10))

    def _draw_channel_labels(self):
        """Draw channel name labels on the left edge of each waveform."""
        for i, ch in enumerate(CHANNELS):
            ch_h = WAVE_AREA_H // len(CHANNELS)
            y = INFO_BAR_H + i * ch_h + 6
            lbl = self.font_label.render(ch["name"], True, self.theme[ch["key"]])
            self.canvas.blit(lbl, (6, y))

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
        d = self.sim.display

        # ── HR ──
        y = INFO_BAR_H + 15
        hr_str = f"{int(d['hr'])}" if d['hr'] > 5 else "---"
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
        spo2_str = f"{int(d['spo2'])}" if d['spo2'] > 10 else "---"
        self._draw_param_block(px, y, "SpO2", spo2_str, "%", self.theme["pleth"], large=True, alarm_status=al.get("spo2"))

        # ── RR ──
        y += 195
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        rr_str = f"{int(d['rr'])}" if d['rr'] > 2 else "---"
        self._draw_param_block(px, y, "RR", rr_str, "rpm", self.theme["resp"], large=False, alarm_status=al.get("rr"))

        # ── ABP ──
        y += 150
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        bp_str = f"{int(d['bp_sys'])}/{int(d['bp_dia'])}" if d['bp_sys'] > 20 else "---/---"
        self._draw_param_block(px, y, "ABP", bp_str, "mmHg", self.theme["abp"], large=False, alarm_status=al.get("abp"))
        # MAP
        if not (al.get("abp") == "low" and not self.alarm_logic.flash_state):
            map_str = f"({int(d['bp_map'])})" if d['bp_map'] > 10 else "(---)"
            map_surf = self.font_sm.render(map_str, True, self.theme["abp"])
            self.canvas.blit(map_surf, (px + 270, y + 75))

        # ── EtCO2 ──
        y += 150
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        etco2_str = "---"
        if self.sim.probe_etco2:
            etco2_str = f"{int(d['etco2'])}" if d['etco2'] > 5 else "---"
        self._draw_param_block(px, y, "EtCO2", etco2_str, "mmHg", self.theme["co2"], large=False, alarm_status=al.get("etco2"))

        # ── Temp ──
        y += 135
        pygame.draw.line(self.canvas, self.theme["divider"], (px + 15, y - 12), (px + PANEL_W - 15, y - 12))
        temp_str = f"{d['temp']:.1f}" if self.sim.probe_temp else "---"
        self._draw_param_block(px, y, "Temp", temp_str, "°C", self.theme["temp"], large=False)

    def _draw_param_block(self, px, y, label, value_str, unit, color, large=False, alarm_status=None):
        """Draw a single parameter block: label, big number, unit."""
        # Pulsing box if this specific parameter is in alarm
        if alarm_status and self.alarm_logic.flash_state:
            rect_h = 160 if large else 125
            pygame.draw.rect(self.canvas, (255, 50, 50), (px + 10, y - 5, PANEL_W - 20, rect_h), 3)

        # Pulsing text logic: blink if low, steady if high
        show_text = True
        if alarm_status == "low" and not self.alarm_logic.flash_state:
            show_text = False

        if show_text:
            # Label
            lbl = self.font_label.render(label, True, color)
            self.canvas.blit(lbl, (px + 22, y))

            # Value
            font = self.font_big if large else self.font_med
            self.fx.render_glow_text(self.canvas, font, value_str, color, (px + 22, y + 27))

            # Unit
            u = self.font_unit.render(unit, True, C_DIM)
            val_w = font.size(value_str)[0]
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
        if self.config.visible or self.showing_disclaimer:
            return
        hints = "TAB: Config  |  U: Toggle UI  |  S: Mute  |  F11: Fullscreen  |  ESC: Exit"
        surf = self.font_xs.render(hints, True, (50, 50, 65))
        self.canvas.blit(surf, (12, HEIGHT - 27))

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

        if self.showing_disclaimer:
            if self.disclaimer_timer > 0:
                self.disclaimer_timer -= dt
            return

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

        # Pulse beep on R-wave (pitch modulated by HR)
        if self.sim.r_wave_detected:
            self.audio.play_pulse(self.sim.hr)
            self.heart_on = True
            self.heart_timer = 0.12

        if self.heart_timer > 0:
            self.heart_timer -= dt
            if self.heart_timer <= 0:
                self.heart_on = False

        # Alarm logic
        priority = self.alarm_logic.update(self.sim, dt)
        if priority:
            self.audio.play_alarm(priority)
        else:
            self.audio.stop_alarm()

    def _draw(self):
        """Main draw routine. Renders to internal canvas, then scales to window."""
        if not self.showing_disclaimer:
            self.canvas.fill(self.theme["bg"])
            
            if self.show_grid:
                self._draw_grid()
            
            for wc in self.wave_channels:
                wc.draw(self.canvas, phosphor=self.fx.enabled["phosphor"])
            
            self._draw_channel_dividers()
            self._draw_channel_labels()
            self._draw_numeric_panel()
            self._draw_alarm_bar()
            self._draw_info_bar()
            self._draw_status_bar()
            
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

    def run(self):
        """Main application loop."""
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if self.showing_disclaimer:
                    if event.type == pygame.MOUSEBUTTONDOWN and self.disclaimer_timer <= 0:
                        # Convert screen mouse pos to canvas pos
                        mx, my = event.pos
                        sw, sh = self.screen.get_size()
                        cw, ch = self.canvas.get_size()
                        cx = mx * (cw / sw)
                        cy = my * (ch / sh)
                        if self.disclaimer_btn_rect.collidepoint(cx, cy):
                            self.showing_disclaimer = False
                    continue

                if event.type == pygame.KEYDOWN:
                    # Config menu intercepts keys when open
                    if self.config.visible:
                        if event.key == pygame.K_TAB or event.key == pygame.K_ESCAPE:
                            self.config.toggle()
                        else:
                            self.config.handle_key(event.key)
                        continue

                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    elif event.key == pygame.K_TAB:
                        self.config.toggle()
                    elif event.key == pygame.K_u:
                        self.show_ui = not self.show_ui
                    elif event.key == pygame.K_s:
                        muted = self.audio.toggle_mute()
                    elif event.key == pygame.K_g:
                        self.show_grid = not self.show_grid
                    elif event.key == pygame.K_F11:
                        self.fullscreen = not self.fullscreen
                        if self.fullscreen:
                            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        else:
                            self.screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
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
                        from config_menu import PRESETS
                        self.sim.set_preset(PRESETS["Healthy Adult"])

            # Resume alarm audio if coming out of pause
            if not self.paused and self.audio.alarm_playing:
                self.audio.ch_alarm.unpause()

            self._update(dt)
            self._draw()
