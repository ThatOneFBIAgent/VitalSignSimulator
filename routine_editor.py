import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

class RoutineEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VitalSign Pro - Routine & Curve Editor")
        self.geometry("1000x700")

        self.params = {
            "hr": {"color": "red", "min": 0, "max": 250},
            "spo2": {"color": "cyan", "min": 50, "max": 100},
            "rr": {"color": "white", "min": 0, "max": 60},
            "bp_sys": {"color": "orange", "min": 20, "max": 250},
            "etco2": {"color": "yellow", "min": 0, "max": 100}
        }
        
        self.rhythms = [
            "[Norm] Sinus Rhythm", "[Atrial] AFib", "[Atrial] AFlutter", 
            "[Vent] PVCs", "[Vent] VTach", "[Vent] VFib", "[Vent] Torsades", 
            "[Block] 1st Deg AV", "[Block] Wenckebach", "[Block] 3rd Deg AV", 
            "[Arrest] Asystole", "[Arrest] PEA"
        ]

        # Data structure: param_name -> list of (time, value)
        self.curves = {p: [(0, self.params[p]["max"] if p=="spo2" else 70)] for p in self.params}
        self.rhythm_events = [(0, "[Norm] Sinus Rhythm")] # (time, rhythm)
        
        self.current_param = tk.StringVar(self, value="hr")
        self.max_time = 120 # seconds

        self._build_ui()
        self._redraw_canvas()

    def _build_ui(self):
        # Top Control Frame
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(ctrl_frame, text="Editing Parameter:").pack(side=tk.LEFT)
        self.param_combo = ttk.Combobox(ctrl_frame, textvariable=self.current_param, values=list(self.params.keys()), state="readonly")
        self.param_combo.pack(side=tk.LEFT, padx=10)
        self.param_combo.bind("<<ComboboxSelected>>", lambda e: self._redraw_canvas())

        ttk.Button(ctrl_frame, text="Clear Current Curve", command=self._clear_curve).pack(side=tk.LEFT, padx=10)
        ttk.Button(ctrl_frame, text="Export to TOML", command=self._export_toml).pack(side=tk.RIGHT, padx=10)
        
        # Rhythm Event Controls
        rhythm_frame = ttk.LabelFrame(self, text="Rhythm Events (Select time on canvas, then Add)")
        rhythm_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(rhythm_frame, text="Time (s):").pack(side=tk.LEFT, padx=5)
        self.rhythm_time_var = tk.StringVar(self, value="0")
        ttk.Entry(rhythm_frame, textvariable=self.rhythm_time_var, width=5).pack(side=tk.LEFT)
        
        self.rhythm_combo = ttk.Combobox(rhythm_frame, values=self.rhythms, state="readonly", width=25)
        self.rhythm_combo.set(self.rhythms[0])
        self.rhythm_combo.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(rhythm_frame, text="Add Rhythm Event", command=self._add_rhythm).pack(side=tk.LEFT)
        ttk.Button(rhythm_frame, text="Clear Rhythm Events", command=self._clear_rhythms).pack(side=tk.LEFT, padx=10)

        # Canvas
        self.canvas = tk.Canvas(self, bg="#202020", height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)

        # Bottom Info
        ttk.Label(self, text="Left Click: Add/Move Point | Right Click: Delete Point").pack(pady=5)

    def _clear_curve(self):
        p = self.current_param.get()
        self.curves[p] = [(0, self.curves[p][0][1])]
        self._redraw_canvas()
        
    def _clear_rhythms(self):
        self.rhythm_events = [(0, "[Norm] Sinus Rhythm")]
        self._redraw_canvas()
        
    def _add_rhythm(self):
        try:
            t = int(self.rhythm_time_var.get())
            if t < 0: t = 0
            if t > self.max_time: t = self.max_time
            r = self.rhythm_combo.get()
            self.rhythm_events.append((t, r))
            self.rhythm_events.sort(key=lambda x: x[0])
            self._redraw_canvas()
        except ValueError:
            pass

    def _get_coords(self, t, v, p):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1: w = 980
        if h <= 1: h = 500
        
        p_min = self.params[p]["min"]
        p_max = self.params[p]["max"]
        
        x = (t / self.max_time) * w
        y = h - ((v - p_min) / (p_max - p_min)) * h
        return x, y

    def _get_val_from_coords(self, x, y, p):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        p_min = self.params[p]["min"]
        p_max = self.params[p]["max"]
        
        t = (x / w) * self.max_time
        v = p_min + ((h - y) / h) * (p_max - p_min)
        return max(0, min(self.max_time, t)), max(p_min, min(p_max, v))

    def _redraw_canvas(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        if w <= 1: w = 980
        h = self.canvas.winfo_height()
        if h <= 1: h = 500

        # Grid
        for t in range(0, self.max_time + 1, 10):
            x = (t / self.max_time) * w
            self.canvas.create_line(x, 0, x, h, fill="#303030")
            self.canvas.create_text(x, h-10, text=str(t)+"s", fill="#606060")

        p = self.current_param.get()
        pts = sorted(self.curves[p], key=lambda x: x[0])
        color = self.params[p]["color"]

        # Draw lines
        if len(pts) > 1:
            coords = []
            for t, v in pts:
                cx, cy = self._get_coords(t, v, p)
                coords.extend([cx, cy])
            self.canvas.create_line(*coords, fill=color, width=2)

        # Draw points
        for i, (t, v) in enumerate(pts):
            cx, cy = self._get_coords(t, v, p)
            self.canvas.create_oval(cx-4, cy-4, cx+4, cy+4, fill=color, tags=f"pt_{i}")
            self.canvas.create_text(cx, cy-15, text=f"{int(v)}", fill=color)
            
        # Draw rhythm markers
        for t, r in self.rhythm_events:
            x = (t / self.max_time) * w
            self.canvas.create_line(x, 0, x, h, fill="#0088ff", dash=(4,4))
            self.canvas.create_text(x+5, 20, text=r, fill="#0088ff", anchor="w")

    def _on_canvas_click(self, event):
        p = self.current_param.get()
        t, v = self._get_val_from_coords(event.x, event.y, p)
        
        # Check if clicking near existing point to drag
        pts = self.curves[p]
        for i, (pt_t, pt_v) in enumerate(pts):
            cx, cy = self._get_coords(pt_t, pt_v, p)
            if abs(event.x - cx) < 10 and abs(event.y - cy) < 10:
                self._drag_idx = i
                return
                
        # Otherwise add new point
        self.curves[p].append((t, v))
        self._drag_idx = len(self.curves[p]) - 1
        self._redraw_canvas()

    def _on_canvas_drag(self, event):
        if hasattr(self, '_drag_idx'):
            p = self.current_param.get()
            t, v = self._get_val_from_coords(event.x, event.y, p)
            self.curves[p][self._drag_idx] = (t, v)
            self._redraw_canvas()

    def _export_toml(self):
        # Build timeline
        timeline = {}
        
        # Collect all unique times
        times = set()
        for p, pts in self.curves.items():
            for t, _ in pts:
                times.add(int(t))
        for t, _ in self.rhythm_events:
            times.add(int(t))
            
        for t in sorted(list(times)):
            state = {}
            for p, pts in self.curves.items():
                # Find exact match
                for pt_t, pt_v in pts:
                    if int(pt_t) == t:
                        state[p] = int(pt_v)
            for rt, r in self.rhythm_events:
                if int(rt) == t:
                    state["ecg_rhythm"] = r
            if state:
                timeline[t] = state

        # Generate TOML
        out = '["Custom Routine"]\n'
        for t in sorted(timeline.keys()):
            out += f"  [[Custom Routine.steps]]\n"
            out += f"  t = {t}\n"
            out += f"  [Custom Routine.steps.state]\n"
            for k, v in timeline[t].items():
                if isinstance(v, str):
                    out += f'  {k} = "{v}"\n'
                else:
                    out += f'  {k} = {v}\n'
            out += "\n"

        fn = filedialog.asksaveasfilename(defaultextension=".toml", filetypes=[("TOML files", "*.toml")])
        if fn:
            with open(fn, "w") as f:
                f.write(out)
            messagebox.showinfo("Exported", f"Routine saved to {fn}\n\nYou can load this using a TOML parser in routines.py!")

if __name__ == "__main__":
    app = RoutineEditor()
    app.mainloop()
