"""
VitalSign Pro — Standalone Configuration Panel
Fully custom dark-themed control window for OBS-friendly recording.
Runs in a separate thread so it doesn't interfere with the main monitor.
"""
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import os

from simulation import ECG_RHYTHMS, RESP_PATTERNS, ECG_DISPLAY_LEADS, ECG_AILMENTS
from constants import THEMES, PRESETS

# ─── Design Tokens ───
BG        = "#0c0c14"
SURFACE   = "#131320"
SURFACE2  = "#1a1a2a"
HOVER     = "#24243a"
SELECTED  = "#0a2a18"
ACCENT    = "#00ff82"
CYAN      = "#50c8ff"
RED       = "#ff5050"
YELLOW    = "#ffcc00"
TEXT      = "#d0d0e4"
TEXT2     = "#8888a4"
DIM       = "#404058"
BORDER    = "#2a2a3e"
DIVIDER   = "#222236"

FONT      = "Consolas"
WIN_W     = 700
WIN_H     = 680

HELP_TEXT = {
    "ECG Rhythm": "Selects the cardiac rhythm waveform and rate behavior.",
    "Displayed Lead": "Chooses the main monitor ECG lead; Clean combines all leads.",
    "Resp Pattern": "Changes the breathing pattern used for respiration and CO2.",
    "EtCO2 Connected": "Shows or disconnects the capnography probe.",
    "Temp Connected": "Shows or disconnects the temperature probe.",
    "ECG Lead Artifacts": "Adds ECG drift, mains noise, motion, and lead pops.",
    "Artifact Level": "Sets how strong ECG sensor artifacts appear.",
    "EtCO2 Variability": "Adds breath-to-breath capnography variation.",
    "Heart Rate": "Target heart rate; rhythm modes may clamp it to plausible ranges.",
    "SpO2": "Target oxygen saturation.",
    "Resp Rate": "Target respiratory rate.",
    "BP Systolic": "Target systolic arterial pressure.",
    "BP Diastolic": "Target diastolic arterial pressure.",
    "Temperature": "Target patient temperature.",
    "EtCO2": "Target end-tidal CO2.",
    "Min": "Lower bound for natural drift around the target.",
    "Max": "Upper bound for natural drift around the target.",
    "Alarm": "Sets the threshold that triggers this alarm.",
    "Display Theme": "Changes the monitor color palette.",
    "Institution": "Changes the top-bar institution label.",
    "Department": "Changes the top-bar department label.",
    "Bed / Unit": "Changes the top-bar bed or unit label.",
    "Alarm Box Style": "Changes how numeric alarm boxes are drawn.",
    "Differentiate High/Low": "Uses different visual behavior for high and low alarms.",
    "Diagnostics Window": "Opens the separate signal and alarm diagnostics view.",
    "Show 'REC' Status": "Shows routine playback status in the top bar.",
    "Dim Watermark": "Dims the simulation-only watermark while keeping it visible.",
    "CRT": "Toggles the selected display effect.",
    "Mute Audio": "Mutes pulse and alarm sounds.",
    "Audio Signal Mode": "Maps a WAV file into traces and synthetic numbers.",
    "Choose WAV": "Selects the WAV file used by audio signal mode.",
    "Audio Input Device": "Selects which live audio input feeds signal mode.",
    "Live Input": "Starts or stops live audio capture for signal mode.",
    "Active Routine": "Selects the scripted scenario to preview and run.",
}


class ConfigWindow:
    """Standalone configuration window running in a separate OS-level window."""

    def __init__(self, sim, alarm_logic, effects, audio, routine_manager=None, monitor=None):
        self.sim = sim
        self.alarm_logic = alarm_logic
        self.effects = effects
        self.audio = audio
        self.routine_manager = routine_manager
        self.monitor = monitor

        self.root = None
        self.thread = None
        self.is_starting = False
        self.is_running = False
        self.is_ready = False
        self._restore_requested = threading.Event()
        self._close_requested = threading.Event()
        self._closed = threading.Event()

        self._tab_buttons = {}
        self._tab_frames = {}
        self._active_tab = None
        self._refresh_jobs = []  # List of (widget, getter_func, update_func)
        self._help_label = None

    def show(self):
        if self.is_running or self.is_starting:
            self._restore_requested.set()
            return
        self._close_requested.clear()
        self._closed.clear()
        self.is_starting = True
        self.thread = threading.Thread(target=self._run, daemon=False)
        self.thread.start()

    def close(self):
        if self.is_running or self.is_starting:
            self._close_requested.set()

    def wait_closed(self, timeout=3.0):
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)
        return not (self.thread and self.thread.is_alive())

    # ─── Window Lifecycle ───

    def _run(self):
        try:
            self.is_starting = False
            self.is_running = True
            self.is_ready = False
            self._restore_requested.clear()
            self._refresh_jobs = []
            self._tab_buttons = {}
            self._tab_frames = {}
            self._active_tab = None
            self._help_label = None
            self.root = tk.Tk()
            self.root.withdraw()
            self.root.title("VitalSign Pro Configuration")
            self.root.minsize(600, 520)
            self.root.resizable(True, True)
            self.root.configure(bg=BG)

            # Position to the right of screen
            self.root.update_idletasks()
            sx = self.root.winfo_screenwidth()
            sy = self.root.winfo_screenheight()
            x = sx - WIN_W - 50
            y = (sy - WIN_H) // 2
            self.root.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        # ─── TTK Theming ───
            style = ttk.Style(self.root)
            style.theme_use("clam")
            style.configure("TCombobox", fieldbackground=SURFACE2, background=SURFACE2,
                            foreground=CYAN, arrowcolor=CYAN, borderwidth=1,
                            relief="flat")
            style.map("TCombobox",
                      fieldbackground=[("readonly", SURFACE2)],
                      foreground=[("readonly", CYAN)],
                      selectbackground=[("readonly", SURFACE2)],
                      selectforeground=[("readonly", CYAN)])
            style.configure("Vertical.TScrollbar", background=SURFACE, troughcolor=BG,
                            borderwidth=0, arrowcolor=TEXT2)
            self.root.option_add("*TCombobox*Listbox.background", SURFACE2)
            self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
            self.root.option_add("*TCombobox*Listbox.selectBackground", HOVER)
            self.root.option_add("*TCombobox*Listbox.selectForeground", ACCENT)
            self.root.option_add("*TCombobox*Listbox.font", (FONT, 10))

            border = tk.Frame(self.root, bg=BORDER)
            border.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
            inner = tk.Frame(border, bg=BG)
            inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

            self._build_title_bar(inner)
            self._build_tab_bar(inner)
            self._build_content_area(inner)
            self._build_footer(inner)

            self._switch_tab("Vitals")
            self.root.deiconify()
            self._restore_window()
            self.is_ready = True
            self._periodic_refresh()

            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            self.root.mainloop()
        finally:
            self._refresh_jobs = []
            self._tab_buttons = {}
            self._tab_frames = {}
            self._active_tab = None
            self._help_label = None
            self.is_ready = False
            self.is_running = False
            self.is_starting = False
            self.root = None
            self._closed.set()

    def _restore_window(self):
        if not self.root:
            return
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(150, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

    def _on_close(self):
        self.is_ready = False
        self.is_running = False
        try:
            self.root.destroy()
        except Exception:
            pass

    # ─── Title Bar ───

    def _build_title_bar(self, parent):
        bar = tk.Frame(parent, bg=SURFACE, height=34)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        title = tk.Label(bar, text="  CONFIGURATION", font=(FONT, 10, "bold"),
                         bg=SURFACE, fg=CYAN, anchor="w")
        title.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        tk.Label(bar, text="DETACHED", font=(FONT, 8, "bold"),
                 bg=SURFACE2, fg=ACCENT, padx=8, pady=2).pack(side=tk.RIGHT, padx=14)

        # Native OS chrome now handles minimize/close reliably.
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X)

    def _minimize(self):
        if self.root:
            self.root.iconify()

    # ─── Tab Bar ───

    def _build_tab_bar(self, parent):
        bar = tk.Frame(parent, bg=BG, height=46)
        bar.pack(fill=tk.X, padx=16, pady=(10, 0))

        tabs = ["Vitals", "Alarms", "Display", "Presets", "Routines"]
        for i, name in enumerate(tabs):
            frame = tk.Frame(bar, bg=BG)
            frame.pack(side=tk.LEFT, padx=(0, 4))

            num_lbl = tk.Label(frame, text=f"[{i+1}]", font=(FONT, 10),
                               bg=BG, fg=DIM)
            num_lbl.pack(side=tk.LEFT)

            tab_lbl = tk.Label(frame, text=f" {name}", font=(FONT, 11, "bold"),
                               bg=BG, fg=DIM, cursor="hand2", padx=6, pady=4)
            tab_lbl.pack(side=tk.LEFT)

            underline = tk.Frame(frame, bg=BG, height=2)
            underline.pack(fill=tk.X, side=tk.BOTTOM)

            self._tab_buttons[name] = (tab_lbl, num_lbl, underline)
            tab_lbl.bind("<Button-1>", lambda e, n=name: self._switch_tab(n))
            tab_lbl.bind("<Enter>", lambda e, n=name: self._tab_hover(n, True))
            tab_lbl.bind("<Leave>", lambda e, n=name: self._tab_hover(n, False))

        tk.Frame(parent, bg=DIVIDER, height=1).pack(fill=tk.X, padx=16, pady=(4, 0))

    def _tab_hover(self, name, entering):
        if name == self._active_tab:
            return
        lbl, num, _ = self._tab_buttons[name]
        lbl.config(fg=TEXT2 if entering else DIM)

    def _switch_tab(self, name):
        # Deactivate all
        for n, (lbl, num, ul) in self._tab_buttons.items():
            lbl.config(fg=DIM)
            num.config(fg=DIM)
            ul.config(bg=BG)
        # Activate selected
        lbl, num, ul = self._tab_buttons[name]
        lbl.config(fg=ACCENT)
        num.config(fg=ACCENT)
        ul.config(bg=ACCENT)
        # Show/hide frames
        for n, f in self._tab_frames.items():
            if n == name:
                f.pack(fill=tk.BOTH, expand=True)
            else:
                f.pack_forget()
        self._active_tab = name

    # ─── Content Area ───

    def _build_content_area(self, parent):
        container = tk.Frame(parent, bg=BG)
        container.pack(fill=tk.BOTH, expand=True, padx=0, pady=(2, 0))

        for name, builder in [
            ("Vitals", self._build_vitals),
            ("Alarms", self._build_alarms),
            ("Display", self._build_display),
            ("Presets", self._build_presets),
            ("Routines", self._build_routines),
        ]:
            frame = tk.Frame(container, bg=BG)
            self._tab_frames[name] = frame
            builder(frame)

    # ─── Footer ───

    def _build_footer(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X, padx=16)
        foot = tk.Frame(parent, bg=BG)
        foot.pack(fill=tk.X, padx=18, pady=(5, 6))

        self._help_label = tk.Label(foot, text="", font=(FONT, 8),
                                    bg=BG, fg=TEXT2, anchor="w")
        self._help_label.pack(fill=tk.X, pady=(0, 2))

        legal_row = tk.Frame(foot, bg=BG)
        legal_row.pack(fill=tk.X)
        tk.Label(legal_row, text="SIMULATION ONLY — NOT A MEDICAL DEVICE",
                 font=(FONT, 8), bg=BG, fg="#5a2020").pack(side=tk.LEFT)
        tk.Label(legal_row, text="VitalSign Pro",
                 font=(FONT, 8), bg=BG, fg=DIM).pack(side=tk.RIGHT)

    # ─── Scrollable helper ───

    def _make_scroll_frame(self, parent):
        """Returns a scrollable inner frame with dark-themed scrolling."""
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, bd=0)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.pack(side="left", fill="both", expand=True, padx=(18, 8), pady=12)

        # Thin custom scroll indicator track
        track = tk.Canvas(parent, bg=BG, width=6, highlightthickness=0, bd=0)
        track.pack(side="right", fill="y", padx=(0, 10), pady=16)

        def _update_track(*args):
            canvas.yview(*args)

        def _draw_indicator(*_):
            track.delete("thumb")
            if not canvas.bbox("all"):
                return
            # Get scroll position
            top, bottom = canvas.yview()
            th = track.winfo_height()
            if th < 1:
                return
            if bottom - top >= 1.0:
                return  # No scrolling needed, everything fits
            y1 = int(top * th)
            y2 = int(bottom * th)
            y2 = max(y2, y1 + 16)  # Minimum thumb size
            track.create_rectangle(1, y1, 5, y2, fill=SURFACE2, outline="",
                                   tags="thumb")

        canvas.configure(yscrollcommand=lambda *a: (canvas.update_idletasks(),
                                                     _draw_indicator()))

        # Scoped mousewheel scrolling
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            _draw_indicator()
        def _bind_wheel(e):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_wheel(e):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)
        return inner

    # ─── Widget Helpers ───

    def _section_header(self, parent, text):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill=tk.X, pady=(14, 4))
        tk.Label(f, text=text, font=(FONT, 11, "bold"), bg=BG, fg=CYAN).pack(side=tk.LEFT)
        tk.Frame(f, bg=DIVIDER, height=1).pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(10, 0), pady=1)

    def _make_row(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=tk.X, pady=4)
        return row

    def _help_for(self, label, fallback=""):
        for key, text in HELP_TEXT.items():
            if key in label:
                return text
        return fallback or "Adjusts this simulator setting."

    def _bind_help(self, widget, text):
        if not text:
            return

        def enter(_):
            if self._help_label:
                self._help_label.config(text=text)

        def leave(_):
            if self._help_label:
                self._help_label.config(text="")

        widgets = [widget]
        try:
            widgets.extend(widget.winfo_children())
        except Exception:
            pass
        for child in widgets:
            child.bind("<Enter>", enter, add="+")
            child.bind("<Leave>", leave, add="+")

    def _add_slider(self, parent, label, live_getter, lo, hi, step, on_change, fmt=".0f", help_text=None):
        row = self._make_row(parent)
        tk.Label(row, text=label, font=(FONT, 11), bg=BG, fg=TEXT, anchor="w",
                 width=22).pack(side=tk.LEFT)
        self._bind_help(row, help_text or self._help_for(label))

        initial = live_getter()
        val_lbl = tk.Label(row, text=f"◀ {initial:{fmt}} ▶", font=(FONT, 11, "bold"),
                           bg=BG, fg="#ffffff", width=12, anchor="e")
        val_lbl.pack(side=tk.RIGHT)

        def _on_slide(v, lbl=val_lbl, f=fmt, cb=on_change):
            val = float(v)
            lbl.config(text=f"◀ {val:{f}} ▶")
            cb(val)

        s = tk.Scale(row, from_=lo, to=hi, resolution=step, orient=tk.HORIZONTAL,
                     bg=SURFACE2, fg=SURFACE2, highlightthickness=0, troughcolor=SURFACE2,
                     activebackground=ACCENT, sliderrelief="raised", sliderlength=22,
                     width=12, showvalue=0, bd=1, cursor="hand2",
                     command=_on_slide)
        s.set(initial)
        s.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 8))

        # Register refresh job
        def _refresh_slider(v, sl=s, lb=val_lbl, f=fmt):
            if abs(sl.get() - v) > 0.001:
                sl.set(v)
                lb.config(text=f"◀ {v:{f}} ▶")
        self._refresh_jobs.append((None, live_getter, _refresh_slider))
        self._bind_help(row, help_text or self._help_for(label))
        
        return s, val_lbl

    def _add_toggle(self, parent, label, live_getter, on_change, help_text=None):
        row = self._make_row(parent)
        tk.Label(row, text=label, font=(FONT, 11), bg=BG, fg=TEXT, anchor="w",
                 width=26).pack(side=tk.LEFT)
        self._bind_help(row, help_text or self._help_for(label))

        initial = live_getter()
        state = {"on": initial}
        indicator = tk.Label(row, font=(FONT, 11, "bold"), width=6, anchor="center",
                             cursor="hand2", bd=0)

        def update_visual():
            if state["on"]:
                indicator.config(text="[ON]", fg="#00ff82", bg=SURFACE2)
            else:
                indicator.config(text="[OFF]", fg=RED, bg=SURFACE2)

        def toggle(e=None):
            state["on"] = not state["on"]
            update_visual()
            on_change(state["on"])

        update_visual()
        indicator.pack(side=tk.RIGHT, padx=4)
        indicator.bind("<Button-1>", toggle)

        def _refresh_toggle(v):
            if state["on"] != v:
                state["on"] = v
                update_visual()
        self._refresh_jobs.append((None, live_getter, _refresh_toggle))
        self._bind_help(row, help_text or self._help_for(label))

        return indicator

    def _add_dropdown(self, parent, label, options, live_getter, on_change, help_text=None):
        row = self._make_row(parent)
        tk.Label(row, text=label, font=(FONT, 11), bg=BG, fg=TEXT, anchor="w",
                 width=18).pack(side=tk.LEFT)
        self._bind_help(row, help_text or self._help_for(label))

        initial = live_getter()
        combo = ttk.Combobox(row, values=options, state="readonly",
                             width=28, font=(FONT, 10))
        combo.set(initial)
        combo.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 4))
        combo.bind("<<ComboboxSelected>>", lambda e, c=combo: on_change(c.get()))

        def _refresh_dropdown(v, c=combo):
            if c.get() != v:
                c.set(v)
        self._refresh_jobs.append((None, live_getter, _refresh_dropdown))
        self._bind_help(row, help_text or self._help_for(label))

        return combo

    # ─── Tab Builders (stubs — filled next) ───

    def _build_vitals(self, parent):
        inner = self._make_scroll_frame(parent)
        self._section_header(inner, "Rhythm & Pattern")

        self._add_dropdown(inner, "ECG Rhythm", ECG_RHYTHMS,
                           lambda: self.sim.ecg_rhythm,
                           lambda v: setattr(self.sim, 'ecg_rhythm', v))

        self._section_header(inner, "ECG Ailments")
        add_row = self._make_row(inner)
        tk.Label(add_row, text="Add Ailment", font=(FONT, 11), bg=BG, fg=TEXT, anchor="w",
                 width=18).pack(side=tk.LEFT)
        ailment_combo = ttk.Combobox(add_row, values=ECG_AILMENTS, state="readonly",
                                     width=32, font=(FONT, 10))
        ailment_combo.set(ECG_AILMENTS[0])
        ailment_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        add_btn = tk.Label(add_row, text="[Add]", font=(FONT, 10, "bold"),
                           bg=SURFACE2, fg=ACCENT, padx=10, pady=4, cursor="hand2")
        add_btn.pack(side=tk.RIGHT)
        self._bind_help(add_row, "Adds a morphology ailment layer to the active ECG rhythm.")

        active_ailments = tk.Frame(inner, bg=BG)
        active_ailments.pack(fill=tk.X, pady=(0, 8))

        def ailment_label(name):
            return name.replace("[", "").replace("]", "")

        def redraw_ailments(_value=None):
            for child in active_ailments.winfo_children():
                child.destroy()
            active = dict(getattr(self.sim, "ecg_ailments", {}))
            if not active:
                tk.Label(active_ailments, text="No active ECG ailments.",
                         font=(FONT, 10), bg=BG, fg=TEXT2, anchor="w").pack(fill=tk.X, padx=18, pady=4)
                return

            for ailment, progress in sorted(active.items()):
                row = tk.Frame(active_ailments, bg=BG, pady=3)
                row.pack(fill=tk.X, padx=18)
                tk.Label(row, text=ailment_label(ailment), font=(FONT, 10),
                         bg=BG, fg=TEXT, anchor="w", width=28).pack(side=tk.LEFT)
                val_lbl = tk.Label(row, text=f"{int(progress * 100)}%", font=(FONT, 10, "bold"),
                                   bg=BG, fg="#ffffff", width=5, anchor="e")
                val_lbl.pack(side=tk.RIGHT, padx=(8, 0))
                remove_btn = tk.Label(row, text="[X]", font=(FONT, 10, "bold"),
                                      bg=SURFACE2, fg=RED, padx=7, pady=2, cursor="hand2")
                remove_btn.pack(side=tk.RIGHT, padx=(6, 0))
                scale = tk.Scale(row, from_=5, to=100, resolution=5, orient=tk.HORIZONTAL,
                                 bg=SURFACE2, fg=SURFACE2, highlightthickness=0, troughcolor=SURFACE2,
                                 activebackground=ACCENT, sliderrelief="raised", sliderlength=20,
                                 width=10, showvalue=0, bd=1, cursor="hand2")
                scale.set(progress * 100.0)
                scale.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 4))

                def update(v, a=ailment, lbl=val_lbl):
                    pct = float(v)
                    lbl.config(text=f"{int(pct)}%")
                    self.sim.set_ailment_progress(a, pct / 100.0)

                def remove(_e=None, a=ailment):
                    self.sim.set_ailment_progress(a, 0.0)
                    redraw_ailments()

                scale.config(command=update)
                remove_btn.bind("<Button-1>", remove)

        def add_ailment(_e=None):
            self.sim.set_ailment_progress(ailment_combo.get(), 0.5)
            redraw_ailments()

        add_btn.bind("<Button-1>", add_ailment)
        redraw_ailments()
        last_ailments = {"value": tuple(sorted(getattr(self.sim, "ecg_ailments", {}).keys()))}

        def refresh_ailments(value):
            if value == last_ailments["value"]:
                return
            last_ailments["value"] = value
            redraw_ailments(value)

        self._refresh_jobs.append((
            None,
            lambda: tuple(sorted(getattr(self.sim, "ecg_ailments", {}).keys())),
            refresh_ailments,
        ))

        self._add_dropdown(inner, "Displayed Lead", ECG_DISPLAY_LEADS,
                           lambda: self.sim.ecg_display_lead,
                           lambda v: setattr(self.sim, 'ecg_display_lead', v))
        self._add_dropdown(inner, "Resp Pattern", RESP_PATTERNS,
                           lambda: self.sim.resp_pattern,
                           lambda v: setattr(self.sim, 'resp_pattern', v))

        self._section_header(inner, "Probe Status")
        self._add_toggle(inner, "EtCO2 Connected", lambda: self.sim.probe_etco2,
                         lambda v: setattr(self.sim, 'probe_etco2', v))
        self._add_toggle(inner, "Temp Connected", lambda: self.sim.probe_temp,
                         lambda v: setattr(self.sim, 'probe_temp', v))
        self._add_toggle(inner, "ECG Lead Artifacts", lambda: self.sim.enable_lead_artifacts,
                         lambda v: setattr(self.sim, 'enable_lead_artifacts', v))
        self._add_slider(inner, "Artifact Level",
                         lambda: self.sim.lead_artifact_level, 0.0, 1.0, 0.05,
                         lambda v: setattr(self.sim, 'lead_artifact_level', v), ".2f")
        self._add_slider(inner, "EtCO2 Variability",
                         lambda: self.sim.etco2_variability, 0.0, 0.35, 0.01,
                         lambda v: setattr(self.sim, 'etco2_variability', v), ".2f")

        self._section_header(inner, "Vital Targets")
        params = [
            ("Heart Rate",    "hr",     10, 300, 1,   ".0f", "bpm"),
            ("SpO2",          "spo2",   30, 100, 1,   ".0f", "%"),
            ("Resp Rate",     "rr",      2,  60, 1,   ".0f", "rpm"),
            ("BP Systolic",   "bp_sys", 40, 300, 5,   ".0f", "mmHg"),
            ("BP Diastolic",  "bp_dia", 20, 200, 5,   ".0f", "mmHg"),
            ("Temperature",   "temp",   30,  44, 0.1, ".1f", "°C"),
            ("EtCO2",         "etco2",   5, 100, 1,   ".0f", "mmHg"),
        ]
        for label, key, lo, hi, step, fmt, unit in params:
            def make_setter(k=key):
                def setter(val):
                    t = self.sim.targets[k]
                    old = t["value"]
                    t["value"] = val
                    setattr(self.sim, k, float(val))
                    if k in self.sim.display:
                        self.sim.display[k] = float(val)
                    delta = val - old
                    t["min"] += delta
                    t["max"] += delta
                return setter
            self._add_slider(inner, f"{label} ({unit})",
                             lambda k=key: self.sim.targets[k]["value"], lo, hi, step,
                             make_setter(), fmt)

        self._section_header(inner, "Fluctuation Range")
        for label, key, sub, lo, hi in [
            ("HR Min", "hr", "min", 10, 300),
            ("HR Max", "hr", "max", 10, 300),
            ("SpO2 Min", "spo2", "min", 30, 100),
            ("SpO2 Max", "spo2", "max", 30, 100),
            ("RR Min", "rr", "min", 0, 60),
            ("RR Max", "rr", "max", 0, 60),
            ("BP Sys Min", "bp_sys", "min", 40, 300),
            ("BP Sys Max", "bp_sys", "max", 40, 300),
            ("BP Dia Min", "bp_dia", "min", 20, 200),
            ("BP Dia Max", "bp_dia", "max", 20, 200),
            ("EtCO2 Min", "etco2", "min", 0, 100),
            ("EtCO2 Max", "etco2", "max", 0, 100),
        ]:
            self._add_slider(inner, label,
                             lambda k=key, s=sub: self.sim.targets[k][s], lo, hi, 1,
                             lambda v, k=key, s=sub: self.sim.targets[k].__setitem__(s, v))

    def _build_alarms(self, parent):
        inner = self._make_scroll_frame(parent)
        a = self.alarm_logic.thresholds
        groups = [
            ("Heart Rate Alarms", [
                ("HR High Alarm",     "hr_high",      50, 250, 5),
                ("HR Low Alarm",      "hr_low",       20, 100, 5),
                ("HR Critical High",  "hr_crit_high", 80, 300, 5),
                ("HR Critical Low",   "hr_crit_low",  10,  60, 5),
            ]),
            ("SpO2 Alarms", [
                ("SpO2 Low Alarm",      "spo2_low",      70, 100, 1),
                ("SpO2 Critical Low",   "spo2_crit_low", 50, 100, 1),
            ]),
            ("Respiratory Alarms", [
                ("RR High Alarm", "rr_high", 15, 60, 1),
                ("RR Low Alarm",  "rr_low",   2, 20, 1),
            ]),
            ("Blood Pressure Alarms", [
                ("ABP Sys High", "bp_sys_high", 90, 250, 5),
                ("ABP Sys Low",  "bp_sys_low",  40, 120, 5),
            ]),
            ("EtCO2 Alarms", [
                ("EtCO2 High", "etco2_high", 35, 80, 1),
                ("EtCO2 Low",  "etco2_low",   5, 35, 1),
            ]),
        ]
        for section, items in groups:
            self._section_header(inner, section)
            for label, key, lo, hi, step in items:
                self._add_slider(inner, label, lambda k=key: a[k], lo, hi, step,
                                 lambda v, k=key: a.__setitem__(k, v))

    def _build_display(self, parent):
        inner = self._make_scroll_frame(parent)

        self._section_header(inner, "Theme")
        if self.monitor:
            self._add_dropdown(inner, "Display Theme", list(THEMES.keys()),
                               lambda: self.monitor.theme_name,
                               lambda v: self.monitor.set_theme(v))

        self._section_header(inner, "Monitor Info")
        if self.monitor:
            self._add_dropdown(inner, "Institution",
                ["Patient Monitor", "General Hospital", "St. Jude Medical",
                 "Stat Simulation", "Trauma Center"],
                lambda: self.monitor.hospital_name,
                lambda v: setattr(self.monitor, 'hospital_name', v))
            self._add_dropdown(inner, "Department",
                ["ICU", "ER", "OR", "Post-Op", "Triage", "Pediatrics", "Cardiac Care"],
                lambda: self.monitor.dept_name,
                lambda v: setattr(self.monitor, 'dept_name', v))
            self._add_dropdown(inner, "Bed / Unit",
                ["Bed 1", "Bed 2", "Bed 3", "Bed 4", "Bed 5",
                 "Unit A", "Unit B", "Stat 1"],
                lambda: self.monitor.bed_name,
                lambda v: setattr(self.monitor, 'bed_name', v))

        self._section_header(inner, "Alarm Appearance")
        if self.monitor:
            self._add_dropdown(inner, "Alarm Box Style",
                ["Red outline", "Colored outline", "Inverted red", "Inverted colored"],
                lambda: self.monitor.alarm_box_style,
                lambda v: setattr(self.monitor, 'alarm_box_style', v))
            self._add_toggle(inner, "Differentiate High/Low",
                lambda: self.monitor.differentiate_alarms,
                lambda v: setattr(self.monitor, 'differentiate_alarms', v))

        self._section_header(inner, "Toggles")
        if self.monitor:
            self._add_toggle(inner, "Diagnostics Window", lambda: self.monitor.show_diagnostics_window,
                lambda v: self.monitor.set_diagnostics_window_visible(v))
            self._add_toggle(inner, "Show 'REC' Status", lambda: self.monitor.show_rec_status,
                lambda v: setattr(self.monitor, 'show_rec_status', v))
            self._add_toggle(inner, "Dim Watermark", lambda: self.monitor.watermark_dim,
                lambda v: setattr(self.monitor, 'watermark_dim', v))

        self._section_header(inner, "Visual Effects")
        for key in ["scanlines", "vignette", "glow", "phosphor"]:
            self._add_toggle(inner, f"CRT: {key.capitalize()}",
                lambda k=key: self.effects.enabled[k],
                lambda v, k=key: self.effects.enabled.__setitem__(k, v))

        self._section_header(inner, "Audio")
        self._add_toggle(inner, "Mute Audio", lambda: self.audio.muted,
            lambda v: setattr(self.audio, 'muted', v))

        self._section_header(inner, "Secret Audio Mode")

        def set_audio_mode(enabled):
            if enabled:
                if self.sim.audio_mode_source == "wav" and len(self.sim._audio_samples) > 0:
                    self.sim.audio_mode_enabled = True
                    self.audio.play_audio_mode_file(self.sim.audio_mode_path)
                elif self.sim.audio_mode_source == "live":
                    self.audio.stop_audio_mode_file()
                    if self.sim._audio_live_stream is None:
                        self.sim.start_live_audio_stream(self.sim.audio_mode_live_device)
                    else:
                        self.sim.audio_mode_enabled = True
                else:
                    self.sim.audio_mode_enabled = False
            else:
                self.sim.audio_mode_enabled = False
                self.audio.stop_audio_mode_file()
                if self.sim.audio_mode_source == "live":
                    self.sim.stop_live_audio_stream()

        self._add_toggle(inner, "Audio Signal Mode",
            lambda: self.sim.audio_mode_enabled,
            set_audio_mode,
            "Maps audio into monitor traces and disables clinical alarms.")

        row = self._make_row(inner)
        tk.Label(row, text="Audio WAV", font=(FONT, 11), bg=BG, fg=TEXT, anchor="w",
                 width=18).pack(side=tk.LEFT)
        path_lbl = tk.Label(row, text="No WAV selected", font=(FONT, 9),
                            bg=BG, fg=TEXT2, anchor="w")
        path_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        choose_btn = tk.Label(row, text="[Choose WAV]", font=(FONT, 10, "bold"),
                              bg=SURFACE2, fg=CYAN, padx=10, pady=4, cursor="hand2")
        choose_btn.pack(side=tk.RIGHT)
        self._bind_help(row, self._help_for("Choose WAV"))

        device_options = self.sim.list_live_audio_devices()
        if not device_options:
            device_options = [("Default input", None)]
        device_by_label = {label: device for label, device in device_options}

        device_row = self._make_row(inner)
        tk.Label(device_row, text="Audio Input Device", font=(FONT, 11), bg=BG, fg=TEXT, anchor="w",
                 width=18).pack(side=tk.LEFT)
        device_combo = ttk.Combobox(
            device_row,
            values=list(device_by_label.keys()),
            state="readonly" if self.sim.audio_mode_live_available else "disabled",
            width=32,
            font=(FONT, 10),
        )
        current_label = self.sim.audio_mode_live_device_label
        if current_label not in device_by_label:
            current_label = "Default input"
        device_combo.set(current_label)
        device_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 4))
        self.sim.audio_mode_live_device_label = current_label
        self.sim.audio_mode_live_device = device_by_label.get(current_label)
        self._bind_help(device_row, self._help_for("Audio Input Device"))

        def select_live_device(_=None):
            label = device_combo.get() or "Default input"
            self.sim.audio_mode_live_device_label = label
            self.sim.audio_mode_live_device = device_by_label.get(label)
            if self.sim.audio_mode_source == "live" and self.sim.audio_mode_enabled:
                self.sim.start_live_audio_stream(self.sim.audio_mode_live_device)
            refresh_live()

        device_combo.bind("<<ComboboxSelected>>", select_live_device)

        live_row = self._make_row(inner)
        tk.Label(live_row, text="Live Input", font=(FONT, 11), bg=BG, fg=TEXT, anchor="w",
                 width=18).pack(side=tk.LEFT)
        live_status = tk.Label(live_row, text="", font=(FONT, 9),
                               bg=BG, fg=TEXT2, anchor="w")
        live_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        live_btn = tk.Label(live_row, text="[Start Live]", font=(FONT, 10, "bold"),
                            bg=SURFACE2, fg=CYAN, padx=10, pady=4, cursor="hand2")
        live_btn.pack(side=tk.RIGHT)
        self._bind_help(live_row, self._help_for("Live Input"))

        def refresh_path():
            if self.sim.audio_mode_path:
                path_lbl.config(text=os.path.basename(self.sim.audio_mode_path), fg=ACCENT)
            else:
                path_lbl.config(text="No WAV selected", fg=TEXT2)

        def refresh_live():
            if not self.sim.audio_mode_live_available:
                live_status.config(text=self.sim.audio_mode_live_error, fg=RED)
                live_btn.config(text="[Unavailable]", fg=DIM)
            elif self.sim.audio_mode_source == "live" and self.sim.audio_mode_enabled:
                live_status.config(text=f"Live: {self.sim.audio_mode_live_device_label}", fg=ACCENT)
                live_btn.config(text="[Stop Live]", fg=RED)
            elif self.sim.audio_mode_live_error:
                live_status.config(text=self.sim.audio_mode_live_error, fg=RED)
                live_btn.config(text="[Start Live]", fg=CYAN)
            else:
                live_status.config(text=f"Ready: {self.sim.audio_mode_live_device_label}", fg=TEXT2)
                live_btn.config(text="[Start Live]", fg=CYAN)

        def choose_audio(_=None):
            path = filedialog.askopenfilename(
                title="Choose audio signal WAV",
                filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")]
            )
            if not path:
                return
            try:
                self.sim.stop_live_audio_stream()
                self.sim.load_audio_stream(path)
                self.audio.play_audio_mode_file(path)
                refresh_path()
                refresh_live()
            except Exception as exc:
                self.sim.clear_audio_stream()
                self.audio.stop_audio_mode_file()
                path_lbl.config(text=f"Could not load WAV: {exc}", fg=RED)

        choose_btn.bind("<Button-1>", choose_audio)

        def toggle_live(_=None):
            if not self.sim.audio_mode_live_available:
                refresh_live()
                return
            if self.sim.audio_mode_source == "live" and self.sim.audio_mode_enabled:
                self.sim.audio_mode_enabled = False
                self.sim.stop_live_audio_stream()
            else:
                self.audio.stop_audio_mode_file()
                self.sim.start_live_audio_stream(self.sim.audio_mode_live_device)
            refresh_live()

        live_btn.bind("<Button-1>", toggle_live)
        refresh_path()
        refresh_live()

        def refresh_audio_path(_):
            refresh_path()
            refresh_live()

        self._refresh_jobs.append((None, lambda: (
            self.sim.audio_mode_path,
            self.sim.audio_mode_enabled,
            self.sim.audio_mode_source,
            self.sim.audio_mode_live_error,
            self.sim.audio_mode_live_device_label,
        ), refresh_audio_path))

    def _build_presets(self, parent):
        inner = self._make_scroll_frame(parent)
        self._section_header(inner, "Clinical Presets")
        tk.Label(inner, text="Click a preset to instantly apply it.",
                 font=(FONT, 9), bg=BG, fg=TEXT2).pack(anchor="w", pady=(0, 8))

        for name, data in PRESETS.items():
            btn = tk.Label(inner, text=f"  ▸  {name}", font=(FONT, 12),
                           bg=SURFACE, fg=TEXT, anchor="w", cursor="hand2",
                           padx=12, pady=8)
            btn.pack(fill=tk.X, pady=2)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=HOVER, fg=ACCENT))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=SURFACE, fg=TEXT))
            btn.bind("<Button-1>", lambda e, d=data, b=btn: self._apply_preset(d, b))

    def _apply_preset(self, data, btn):
        self.sim.set_preset(data)
        # Flash confirmation
        btn.config(bg="#0a3a1a", fg=ACCENT)
        self.root.after(400, lambda: btn.config(bg=SURFACE, fg=TEXT))

    def _build_routines(self, parent):
        inner = self._make_scroll_frame(parent)
        rm = self.routine_manager
        if not rm:
            tk.Label(inner, text="Routine Manager not available.",
                     font=(FONT, 11), bg=BG, fg=TEXT2).pack(pady=20)
            return

        routines = rm.get_routine_names()
        if not routines:
            tk.Label(inner, text="No routines found.",
                     font=(FONT, 11), bg=BG, fg=TEXT2).pack(pady=20)
            return

        self._section_header(inner, "Routine Selection")
        self._add_dropdown(inner, "Active Routine", routines,
            lambda: rm.active_routine_name if rm.active_routine_name else routines[0],
            lambda v: rm.set_routine(v))

        self._section_header(inner, "Playback")
        play_btn = tk.Label(inner, text="▶  START ROUTINE", font=(FONT, 14, "bold"),
                            bg="#0a2a18", fg=ACCENT, cursor="hand2",
                            padx=20, pady=14, anchor="center")
        play_btn.pack(fill=tk.X, pady=8)

        if rm.is_playing:
            play_btn.config(text="■  STOP ROUTINE", bg="#2a0a0a", fg=RED)

        def toggle(e=None):
            rm.toggle_play()
            if rm.is_playing:
                play_btn.config(text="■  STOP ROUTINE", bg="#2a0a0a", fg=RED)
            else:
                play_btn.config(text="▶  START ROUTINE", bg="#0a2a18", fg=ACCENT)

        play_btn.bind("<Button-1>", toggle)

    # ─── Periodic Refresh ───

    def _build_routines(self, parent):
        rm = self.routine_manager
        if not rm:
            tk.Label(parent, text="Routine Manager not available.",
                     font=(FONT, 11), bg=BG, fg=TEXT2).pack(pady=20)
            return

        routines = rm.get_routine_names()
        if not routines:
            tk.Label(parent, text="No routines found.",
                     font=(FONT, 11), bg=BG, fg=TEXT2).pack(pady=20)
            return

        if not rm.active_routine_name:
            rm.set_routine(routines[0])

        header = tk.Frame(parent, bg=BG)
        header.pack(fill=tk.X, padx=18, pady=(14, 6))
        self._section_header(header, "Routine Selection")

        row = tk.Frame(header, bg=BG)
        row.pack(fill=tk.X, pady=4)
        tk.Label(row, text="Active Routine", font=(FONT, 11), bg=BG, fg=TEXT,
                 anchor="w", width=18).pack(side=tk.LEFT)
        combo = ttk.Combobox(row, values=routines, state="readonly",
                             width=34, font=(FONT, 10))
        combo.set(rm.active_routine_name)
        combo.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 4))
        self._bind_help(row, self._help_for("Active Routine"))

        preview_wrap = tk.Frame(parent, bg=BG)
        preview_wrap.pack(fill=tk.BOTH, expand=True, padx=18, pady=(4, 8))
        self._section_header(preview_wrap, "Timeline Preview")

        canvas = tk.Canvas(preview_wrap, bg=BG, highlightthickness=0, bd=0)
        preview_inner = tk.Frame(canvas, bg=BG)
        preview_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=preview_inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(preview_wrap, orient="vertical", command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scrollbar.set)

        footer = tk.Frame(parent, bg=BG)
        footer.pack(fill=tk.X, padx=18, pady=(0, 12))
        play_btn = tk.Label(footer, text="START ROUTINE", font=(FONT, 13, "bold"),
                            bg="#0a2a18", fg=ACCENT, cursor="hand2",
                            padx=20, pady=14, anchor="center")
        play_btn.pack(fill=tk.X, pady=8)
        self._bind_help(play_btn, "Starts or stops the selected routine.")

        labels = {
            "ecg_rhythm": "ECG rhythm",
            "ecg_ailments": "ECG ailments",
            "rhythm_mix": "Rhythm layers",
            "resp_pattern": "Resp pattern",
            "probe_etco2": "EtCO2 probe",
            "probe_temp": "Temp probe",
            "hr": "HR",
            "spo2": "SpO2",
            "rr": "RR",
            "bp_sys": "BP sys",
            "bp_dia": "BP dia",
            "temp": "Temp",
            "etco2": "EtCO2",
        }

        def format_time(seconds):
            seconds = int(seconds)
            return f"{seconds // 60:02d}:{seconds % 60:02d}"

        def state_text(state):
            parts = []
            for key, value in state.items():
                if key in ("ecg_ailments", "rhythm_mix") and isinstance(value, dict):
                    if value:
                        mix = ", ".join(f"{rhythm}: {int(float(progress) * 100)}%" for rhythm, progress in value.items())
                    else:
                        mix = "clear"
                    parts.append(f"{labels.get(key, key)} -> {mix}")
                    continue
                parts.append(f"{labels.get(key, key)} -> {value}")
            return "; ".join(parts) if parts else "No state change"

        def redraw_preview():
            for child in preview_inner.winfo_children():
                child.destroy()

            routine = rm.active_routine or []
            if not routine:
                tk.Label(preview_inner, text="No steps in this routine.",
                         font=(FONT, 10), bg=BG, fg=TEXT2).pack(anchor="w", pady=8)
                return

            for idx, step in enumerate(routine):
                active = rm.is_playing and idx == rm.current_step
                done = rm.is_playing and idx < rm.current_step
                color = ACCENT if active else TEXT2 if done else TEXT
                bg = SELECTED if active else BG
                row_frame = tk.Frame(preview_inner, bg=bg)
                row_frame.pack(fill=tk.X, pady=2)
                tk.Label(row_frame, text=format_time(step.get("t", 0)),
                         font=(FONT, 10, "bold"), bg=bg, fg=color,
                         width=7, anchor="w").pack(side=tk.LEFT, padx=(2, 8), pady=5)
                tk.Label(row_frame, text=state_text(step.get("state", {})),
                         font=(FONT, 10), bg=bg, fg=color, anchor="w",
                         justify=tk.LEFT, wraplength=520).pack(side=tk.LEFT, fill=tk.X, expand=True, pady=5)

        def update_play_button():
            hooked = True if not self.monitor else self.monitor.patient_hooked_up
            if rm.is_playing:
                play_btn.config(text="STOP ROUTINE", bg="#2a0a0a", fg=RED)
            elif not hooked:
                play_btn.config(text="HOOK UP PATIENT FIRST", bg=SURFACE2, fg=DIM)
            else:
                play_btn.config(text="START ROUTINE", bg="#0a2a18", fg=ACCENT)

        def select_routine(_=None):
            rm.set_routine(combo.get())
            update_play_button()
            redraw_preview()

        def toggle(_=None):
            if self.monitor and not self.monitor.patient_hooked_up:
                rm.is_playing = False
                update_play_button()
                redraw_preview()
                return
            rm.toggle_play()
            update_play_button()
            redraw_preview()

        combo.bind("<<ComboboxSelected>>", select_routine)
        play_btn.bind("<Button-1>", toggle)
        update_play_button()
        redraw_preview()

        last_seen = {"value": None}

        def refresh_key():
            hooked = True if not self.monitor else self.monitor.patient_hooked_up
            return (rm.active_routine_name, rm.current_step, rm.is_playing, int(rm.elapsed), hooked)

        def refresh_routines(value):
            if value == last_seen["value"]:
                return
            last_seen["value"] = value
            if combo.get() != (rm.active_routine_name or ""):
                combo.set(rm.active_routine_name or routines[0])
            update_play_button()
            redraw_preview()

        self._refresh_jobs.append((None, refresh_key, refresh_routines))

    def _periodic_refresh(self):
        if not self.root or not self.is_running:
            return
        try:
            if self._close_requested.is_set():
                self._close_requested.clear()
                self._on_close()
                return
            if self._restore_requested.is_set():
                self._restore_requested.clear()
                self._restore_window()
            for _, getter, updater in self._refresh_jobs:
                try:
                    val = getter()
                    updater(val)
                except Exception:
                    pass
            self.root.after(500, self._periodic_refresh)
        except Exception:
            pass
