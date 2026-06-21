"""
Detached diagnostics display for the simulator.
Shows 12 ECG leads, body/computer signal gates, and alarm trigger state.
"""
import threading
import tkinter as tk
import math

from simulation import ECG_LEADS

BG = "#05070a"
SURFACE = "#0d1218"
BORDER = "#263642"
GRID = "#18242b"
TEXT = "#c7d4dc"
TEXT2 = "#71818a"
ECG = "#00ff66"
CYAN = "#50c8ff"
YELLOW = "#ffd84a"
RED = "#ff5050"
ORANGE = "#ffad40"
PURPLE = "#b490ff"
FONT = "Consolas"


def _rgb(color):
    if not color:
        return "#202830"
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


class DiagnosticsWindow:
    def __init__(self, monitor):
        self.monitor = monitor
        self.root = None
        self.canvas = None
        self.thread = None
        self.is_running = False
        self.is_starting = False
        self._restore_requested = threading.Event()
        self._close_requested = threading.Event()

    def show(self):
        if self.is_running or self.is_starting:
            self._restore_requested.set()
            return
        self._close_requested.clear()
        self.is_starting = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def close(self):
        if self.is_running or self.is_starting:
            self._close_requested.set()

    def _run(self):
        self.is_starting = False
        self.is_running = True
        self._restore_requested.clear()
        self.root = tk.Tk()
        self.root.title("VitalSign Diagnostics")
        self.root.minsize(980, 720)
        self.root.geometry("1180x820")
        self.root.configure(bg=BG)
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tick()
        self.root.mainloop()
        self.root = None
        self.canvas = None
        self.is_running = False
        self.is_starting = False

    def _on_close(self):
        self.monitor.show_diagnostics_window = False
        try:
            self.root.destroy()
        except Exception:
            pass

    def _restore_window(self):
        if not self.root:
            return
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def _tick(self):
        if not self.root or not self.canvas:
            return
        if self._close_requested.is_set():
            self._on_close()
            return
        if self._restore_requested.is_set():
            self._restore_requested.clear()
            self._restore_window()

        snapshot = self.monitor.get_diagnostics_snapshot()
        self._draw(snapshot)
        self.root.after(80, self._tick)

    def _draw(self, snapshot):
        c = self.canvas
        c.delete("all")
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())

        c.create_text(18, 16, text="VITALSIGN DIAGNOSTICS", fill=CYAN,
                      font=(FONT, 13, "bold"), anchor="nw")
        c.create_text(w - 18, 16, text="SIMULATION DEBUG WINDOW", fill=TEXT2,
                      font=(FONT, 9), anchor="ne")

        alarm_w = 285
        left_w = max(620, w - alarm_w - 34)
        self._draw_12_leads(c, 18, 46, left_w, int(h * 0.43), snapshot)
        self._draw_signal_tests(c, 18, int(h * 0.43) + 62, left_w, h - int(h * 0.43) - 84, snapshot)
        self._draw_alarm_panel(c, left_w + 28, 46, alarm_w, h - 68, snapshot)

    def _panel(self, c, x, y, w, h, title):
        c.create_rectangle(x, y, x + w, y + h, fill=SURFACE, outline=BORDER)
        c.create_text(x + 10, y + 8, text=title, fill=TEXT, font=(FONT, 10, "bold"), anchor="nw")

    def _draw_12_leads(self, c, x, y, w, h, snapshot):
        self._panel(c, x, y, w, h, "12 LEADS")
        leads = snapshot.get("leads", {})
        cols, rows = 4, 3
        cell_w = (w - 20) / cols
        cell_h = (h - 36) / rows
        for idx, lead in enumerate(ECG_LEADS):
            col = idx % cols
            row = idx // cols
            cx = x + 10 + col * cell_w
            cy = y + 30 + row * cell_h
            rect = (cx + 34, cy + 6, cell_w - 44, cell_h - 12)
            c.create_rectangle(cx, cy, cx + cell_w - 8, cy + cell_h - 7, outline=GRID)
            c.create_text(cx + 8, cy + 8, text=lead, fill=ECG, font=(FONT, 9, "bold"), anchor="nw")
            self._draw_trace(c, rect, leads.get(lead, []), ECG, (-1.4, 1.6))

    def _draw_signal_tests(self, c, x, y, w, h, snapshot):
        self._panel(c, x, y, w, h, "BODY -> COMPUTER SIGNALS")
        signals = snapshot.get("signals", {})
        rows = [
            ("Body ECG", ECG, (-1.4, 1.6)),
            ("Monitor ECG", YELLOW, (-1.4, 1.6)),
            ("R Gate", CYAN, (-0.1, 1.2)),
            ("Body CO2", "#ffe860", (0.0, 80.0)),
            ("CO2 Gate", "#8cff9a", (-0.1, 1.2)),
            ("Insp Gate", PURPLE, (-0.1, 1.2)),
        ]
        row_h = max(32, (h - 34) / len(rows))
        for i, (name, color, value_range) in enumerate(rows):
            ry = y + 28 + i * row_h
            c.create_text(x + 12, ry + 8, text=name, fill=color, font=(FONT, 9), anchor="nw")
            rect = (x + 122, ry + 4, w - 136, row_h - 8)
            self._draw_trace(c, rect, signals.get(name, []), color, value_range)

    def _draw_alarm_panel(self, c, x, y, w, h, snapshot):
        self._panel(c, x, y, w, h, "ALARM TRIGGERS")
        alarm = snapshot.get("alarm", {})
        priority = alarm.get("priority") or "none"
        msg = alarm.get("message") or "No active alarm"
        color = RED if priority == "high" else ORANGE if priority == "low" else CYAN if "warning" in priority else TEXT2
        c.create_text(x + 14, y + 34, text=f"Priority: {priority}", fill=color,
                      font=(FONT, 11, "bold"), anchor="nw")
        c.create_text(x + 14, y + 58, text=msg, fill=TEXT, font=(FONT, 9),
                      anchor="nw", width=w - 28)

        led_l = _rgb(alarm.get("led_left"))
        led_r = _rgb(alarm.get("led_right"))
        c.create_text(x + 14, y + 104, text="LEDs", fill=TEXT2, font=(FONT, 9), anchor="nw")
        c.create_rectangle(x + 70, y + 104, x + 116, y + 119, fill=led_l, outline=BORDER)
        c.create_rectangle(x + 126, y + 104, x + 172, y + 119, fill=led_r, outline=BORDER)

        c.create_text(x + 14, y + 140, text="Active params", fill=TEXT2, font=(FONT, 9), anchor="nw")
        params = alarm.get("params", {})
        names = ["hr", "spo2", "rr", "abp", "etco2", "temp"]
        py = y + 166
        for name in names:
            state = params.get(name)
            state_text = state.upper() if state else "OK"
            state_color = RED if state == "high" else ORANGE if state == "low" else "#5f7f6c"
            c.create_text(x + 18, py, text=name.upper(), fill=TEXT, font=(FONT, 10), anchor="nw")
            c.create_text(x + w - 20, py, text=state_text, fill=state_color,
                          font=(FONT, 10, "bold"), anchor="ne")
            py += 26

        vitals = snapshot.get("vitals", {})
        c.create_text(x + 14, py + 10, text="Computer vitals", fill=TEXT2, font=(FONT, 9), anchor="nw")
        py += 36
        for label, value in [
            ("HR", f"{vitals.get('hr', 0):.0f} bpm"),
            ("SpO2", f"{vitals.get('spo2', 0):.0f} %"),
            ("RR", f"{vitals.get('rr', 0):.0f} rpm"),
            ("ABP", f"{vitals.get('bp_sys', 0):.0f}/{vitals.get('bp_dia', 0):.0f}"),
            ("EtCO2", f"{vitals.get('etco2', 0):.0f} mmHg"),
            ("Temp", f"{vitals.get('temp', 0):.1f} C"),
        ]:
            c.create_text(x + 18, py, text=label, fill=TEXT, font=(FONT, 10), anchor="nw")
            c.create_text(x + w - 20, py, text=value, fill=CYAN, font=(FONT, 10), anchor="ne")
            py += 24

    def _draw_trace(self, c, rect, samples, color, value_range):
        x, y, w, h = rect
        if w <= 2 or h <= 2:
            return
        c.create_rectangle(x, y, x + w, y + h, outline=GRID)
        c.create_line(x, y + h / 2, x + w, y + h / 2, fill=GRID)
        if not samples or len(samples) < 2:
            return

        lo, hi = value_range
        span = max(0.001, hi - lo)
        pts = []
        n = len(samples)
        for i, val in enumerate(samples):
            if val is None or not math.isfinite(float(val)):
                if len(pts) >= 4:
                    c.create_line(*pts, fill=color, width=1)
                pts = []
                continue
            px = x + (i / max(1, n - 1)) * w
            frac = max(0.0, min(1.0, (float(val) - lo) / span))
            py = y + h - 2 - frac * (h - 4)
            pts.extend((px, py))
        if len(pts) >= 4:
            c.create_line(*pts, fill=color, width=1)
