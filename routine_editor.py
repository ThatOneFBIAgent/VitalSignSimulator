import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from simulation import ECG_RHYTHMS, ECG_AILMENTS, ECG_AILMENT_CONFLICTS


class RoutineEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VitalSign Pro - Routine & Rhythm Layer Editor")
        self.geometry("1120x760")

        self.params = {
            "hr": {"color": "red", "min": 0, "max": 250, "default": 70},
            "spo2": {"color": "cyan", "min": 50, "max": 100, "default": 100},
            "rr": {"color": "white", "min": 0, "max": 60, "default": 16},
            "bp_sys": {"color": "orange", "min": 20, "max": 250, "default": 120},
            "bp_dia": {"color": "#ffb060", "min": 10, "max": 160, "default": 80},
            "etco2": {"color": "yellow", "min": 0, "max": 100, "default": 38},
            "temp": {"color": "#ff80c0", "min": 30, "max": 44, "default": 36.8},
        }

        self.curves = {p: [(0, spec["default"])] for p, spec in self.params.items()}
        self.base_rhythm_events = [(0, "[Norm] Sinus Rhythm")]
        self.ailment_events = []

        self.current_param = tk.StringVar(self, value="hr")
        self.max_time = 120
        self._drag_idx = None

        self._build_ui()
        self._redraw_canvas()

    def _build_ui(self):
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=(10, 6))

        ttk.Label(ctrl_frame, text="Editing Parameter:").pack(side=tk.LEFT)
        self.param_combo = ttk.Combobox(
            ctrl_frame,
            textvariable=self.current_param,
            values=list(self.params.keys()),
            state="readonly",
            width=12,
        )
        self.param_combo.pack(side=tk.LEFT, padx=8)
        self.param_combo.bind("<<ComboboxSelected>>", lambda _e: self._redraw_canvas())

        ttk.Label(ctrl_frame, text="Timeline (s):").pack(side=tk.LEFT, padx=(12, 4))
        self.max_time_var = tk.StringVar(self, value=str(self.max_time))
        ttk.Entry(ctrl_frame, textvariable=self.max_time_var, width=6).pack(side=tk.LEFT)
        ttk.Button(ctrl_frame, text="Apply", command=self._apply_max_time).pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_frame, text="Clear Curve", command=self._clear_curve).pack(side=tk.LEFT, padx=12)
        ttk.Button(ctrl_frame, text="Export to TOML", command=self._export_toml).pack(side=tk.RIGHT, padx=10)

        rhythm_frame = ttk.LabelFrame(self, text="Hard Rhythm Switches")
        rhythm_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(rhythm_frame, text="Time:").pack(side=tk.LEFT, padx=5)
        self.rhythm_time_var = tk.StringVar(self, value="0")
        ttk.Entry(rhythm_frame, textvariable=self.rhythm_time_var, width=6).pack(side=tk.LEFT)

        self.rhythm_combo = ttk.Combobox(rhythm_frame, values=ECG_RHYTHMS, state="readonly", width=34)
        self.rhythm_combo.set("[Norm] Sinus Rhythm")
        self.rhythm_combo.pack(side=tk.LEFT, padx=8)

        ttk.Button(rhythm_frame, text="Add Switch", command=self._add_base_rhythm).pack(side=tk.LEFT)
        ttk.Button(rhythm_frame, text="Clear Switches", command=self._clear_base_rhythms).pack(side=tk.LEFT, padx=8)

        layer_frame = ttk.LabelFrame(self, text="ECG Ailments / Severity")
        layer_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(layer_frame, text="Time:").pack(side=tk.LEFT, padx=5)
        self.layer_time_var = tk.StringVar(self, value="0")
        ttk.Entry(layer_frame, textvariable=self.layer_time_var, width=6).pack(side=tk.LEFT)

        self.layer_combo = ttk.Combobox(layer_frame, values=ECG_AILMENTS, state="readonly", width=34)
        self.layer_combo.set(ECG_AILMENTS[0])
        self.layer_combo.pack(side=tk.LEFT, padx=8)

        ttk.Label(layer_frame, text="Progress %:").pack(side=tk.LEFT)
        self.layer_progress_var = tk.DoubleVar(self, value=50)
        ttk.Scale(layer_frame, from_=5, to=100, variable=self.layer_progress_var, length=130).pack(side=tk.LEFT, padx=6)
        self.layer_progress_entry = ttk.Entry(layer_frame, width=5)
        self.layer_progress_entry.insert(0, "50")
        self.layer_progress_entry.pack(side=tk.LEFT)
        ttk.Button(layer_frame, text="Add Ailment Event", command=self._add_layer_event).pack(side=tk.LEFT, padx=8)
        ttk.Button(layer_frame, text="Clear Ailment Events", command=self._clear_layer_events).pack(side=tk.LEFT)

        self.canvas = tk.Canvas(self, bg="#202020", height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)

        ttk.Label(
            self,
            text="Left click/drag: add or move curve points | Right click: delete nearby point",
        ).pack(pady=(0, 8))

    def _apply_max_time(self):
        try:
            self.max_time = max(10, int(float(self.max_time_var.get())))
        except ValueError:
            self.max_time = 120
            self.max_time_var.set(str(self.max_time))
        self._redraw_canvas()

    def _clear_curve(self):
        p = self.current_param.get()
        self.curves[p] = [(0, self.curves[p][0][1])]
        self._redraw_canvas()

    def _clear_base_rhythms(self):
        self.base_rhythm_events = [(0, "[Norm] Sinus Rhythm")]
        self._redraw_canvas()

    def _clear_layer_events(self):
        self.ailment_events = []
        self._redraw_canvas()

    def _clamped_time(self, text):
        t = int(float(text))
        return max(0, min(self.max_time, t))

    def _add_base_rhythm(self):
        try:
            t = self._clamped_time(self.rhythm_time_var.get())
        except ValueError:
            return
        rhythm = self.rhythm_combo.get()
        self.base_rhythm_events = [(et, er) for et, er in self.base_rhythm_events if et != t]
        self.base_rhythm_events.append((t, rhythm))
        self.base_rhythm_events.sort(key=lambda x: x[0])
        self._redraw_canvas()

    def _add_layer_event(self):
        try:
            t = self._clamped_time(self.layer_time_var.get())
            progress = float(self.layer_progress_entry.get())
        except ValueError:
            progress = float(self.layer_progress_var.get())
        progress = max(5.0, min(100.0, progress))
        rhythm = self.layer_combo.get()
        self.ailment_events = [
            (et, er, ep) for et, er, ep in self.ailment_events
            if not (et == t and er == rhythm)
        ]
        self.ailment_events.append((t, rhythm, progress / 100.0))
        self.ailment_events.sort(key=lambda x: (x[0], x[1]))
        self._redraw_canvas()

    def _get_coords(self, t, v, p):
        w = self.canvas.winfo_width() or 1080
        h = self.canvas.winfo_height() or 500
        if w <= 1:
            w = 1080
        if h <= 1:
            h = 500

        p_min = self.params[p]["min"]
        p_max = self.params[p]["max"]
        x = (t / self.max_time) * w
        y = h - ((v - p_min) / (p_max - p_min)) * h
        return x, y

    def _get_val_from_coords(self, x, y, p):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        p_min = self.params[p]["min"]
        p_max = self.params[p]["max"]
        t = (x / w) * self.max_time
        v = p_min + ((h - y) / h) * (p_max - p_min)
        return max(0, min(self.max_time, t)), max(p_min, min(p_max, v))

    def _redraw_canvas(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1:
            w = 1080
        if h <= 1:
            h = 500

        for t in range(0, self.max_time + 1, 10):
            x = (t / self.max_time) * w
            self.canvas.create_line(x, 0, x, h, fill="#303030")
            self.canvas.create_text(x, h - 10, text=f"{t}s", fill="#707070")

        p = self.current_param.get()
        pts = sorted(self.curves[p], key=lambda x: x[0])
        color = self.params[p]["color"]

        if len(pts) > 1:
            coords = []
            for t, v in pts:
                coords.extend(self._get_coords(t, v, p))
            self.canvas.create_line(*coords, fill=color, width=2)

        for i, (t, v) in enumerate(pts):
            cx, cy = self._get_coords(t, v, p)
            self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=color, tags=f"pt_{i}")
            self.canvas.create_text(cx, cy - 15, text=f"{v:.1f}" if p == "temp" else f"{int(v)}", fill=color)

        for t, rhythm in self.base_rhythm_events:
            x = (t / self.max_time) * w
            self.canvas.create_line(x, 0, x, h, fill="#0088ff", dash=(4, 4))
            self.canvas.create_text(x + 5, 20, text=rhythm, fill="#55aaff", anchor="w")

        layer_rows = {}
        for t, rhythm, progress in self.ailment_events:
            layer_rows[t] = layer_rows.get(t, 0) + 1
            y = 48 + (layer_rows[t] - 1) * 18
            x = (t / self.max_time) * w
            pct = int(progress * 100)
            self.canvas.create_line(x, 0, x, h, fill="#ff40b0", dash=(2, 5))
            self.canvas.create_text(x + 5, y, text=f"{rhythm} {pct}%", fill="#ff80c8", anchor="w")

    def _on_canvas_click(self, event):
        p = self.current_param.get()
        t, v = self._get_val_from_coords(event.x, event.y, p)
        pts = self.curves[p]

        for i, (pt_t, pt_v) in enumerate(pts):
            cx, cy = self._get_coords(pt_t, pt_v, p)
            if abs(event.x - cx) < 10 and abs(event.y - cy) < 10:
                self._drag_idx = i
                return

        pts.append((t, v))
        self._drag_idx = len(pts) - 1
        self._redraw_canvas()

    def _on_canvas_drag(self, event):
        if self._drag_idx is None:
            return
        p = self.current_param.get()
        t, v = self._get_val_from_coords(event.x, event.y, p)
        self.curves[p][self._drag_idx] = (t, v)
        self._redraw_canvas()

    def _on_canvas_release(self, _event):
        p = self.current_param.get()
        self.curves[p].sort(key=lambda x: x[0])
        self._drag_idx = None
        self._redraw_canvas()

    def _on_canvas_right_click(self, event):
        p = self.current_param.get()
        pts = self.curves[p]
        if len(pts) <= 1:
            return
        for i, (pt_t, pt_v) in enumerate(pts):
            cx, cy = self._get_coords(pt_t, pt_v, p)
            if abs(event.x - cx) < 10 and abs(event.y - cy) < 10:
                del pts[i]
                self._redraw_canvas()
                return

    def _build_timeline(self):
        timeline = {}
        times = set()
        for pts in self.curves.values():
            times.update(int(t) for t, _ in pts)
        times.update(int(t) for t, _ in self.base_rhythm_events)
        times.update(int(t) for t, _, _ in self.ailment_events)

        active_ailments = {}
        ailment_events_by_time = {}
        for t, rhythm, progress in self.ailment_events:
            ailment_events_by_time.setdefault(int(t), []).append((rhythm, progress))

        for t in sorted(times):
            state = {}
            for p, pts in self.curves.items():
                for pt_t, pt_v in pts:
                    if int(pt_t) == t:
                        state[p] = round(float(pt_v), 1) if p == "temp" else int(pt_v)

            for rt, rhythm in self.base_rhythm_events:
                if int(rt) == t:
                    state["ecg_rhythm"] = rhythm

            if t in ailment_events_by_time:
                for rhythm, progress in ailment_events_by_time[t]:
                    if progress <= 0.001:
                        active_ailments.pop(rhythm, None)
                    else:
                        for conflict in ECG_AILMENT_CONFLICTS.get(rhythm, set()):
                            active_ailments.pop(conflict, None)
                        for other, conflicts in ECG_AILMENT_CONFLICTS.items():
                            if rhythm in conflicts:
                                active_ailments.pop(other, None)
                        active_ailments[rhythm] = progress
                state["ecg_ailments"] = dict(active_ailments)

            if state:
                timeline[t] = state
        return timeline

    def _format_toml_value(self, value):
        if isinstance(value, str):
            return '"' + value.replace('"', '\\"') + '"'
        if isinstance(value, dict):
            if not value:
                return "{}"
            pairs = []
            for key, val in value.items():
                pairs.append(f'"{key}" = {float(val):.2f}')
            return "{ " + ", ".join(pairs) + " }"
        return str(value)

    def _export_toml(self):
        timeline = self._build_timeline()
        out = '["Custom Routine"]\n'
        for t in sorted(timeline.keys()):
            out += "  [[Custom Routine.steps]]\n"
            out += f"  t = {t}\n"
            out += "  [Custom Routine.steps.state]\n"
            for key, value in timeline[t].items():
                out += f"  {key} = {self._format_toml_value(value)}\n"
            out += "\n"

        fn = filedialog.asksaveasfilename(defaultextension=".toml", filetypes=[("TOML files", "*.toml")])
        if fn:
            with open(fn, "w", encoding="utf-8") as f:
                f.write(out)
            messagebox.showinfo("Exported", f"Routine saved to {fn}")


if __name__ == "__main__":
    app = RoutineEditor()
    app.mainloop()
