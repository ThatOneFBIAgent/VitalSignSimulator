class RoutineManager:
    def __init__(self, sim):
        self.sim = sim
        self.active_routine_name = None
        self.active_routine = None
        self.elapsed = 0.0
        self.current_step = 0
        self.is_playing = False

    def get_routine_names(self):
        return list(ROUTINES.keys())

    def set_routine(self, name):
        if name in ROUTINES:
            self.active_routine_name = name
            self.active_routine = ROUTINES[name]
            self.elapsed = 0.0
            self.current_step = 0
            self.is_playing = False

    def toggle_play(self):
        if not self.active_routine:
            if self.get_routine_names():
                self.set_routine(self.get_routine_names()[0])
        
        if self.active_routine:
            self.is_playing = not self.is_playing
            if self.is_playing and self.current_step >= len(self.active_routine):
                # restart if finished
                self.elapsed = 0.0
                self.current_step = 0

    def update(self, dt):
        if not self.is_playing or not self.active_routine:
            return

        self.elapsed += dt
        
        while self.current_step < len(self.active_routine):
            step = self.active_routine[self.current_step]
            if self.elapsed >= step["t"]:
                state = step.get("state", {})
                for k, v in state.items():
                    if k in self.sim.targets:
                        self.sim.targets[k]["value"] = v
                    elif hasattr(self.sim, k):
                        setattr(self.sim, k, v)
                self.current_step += 1
            else:
                break
        
        if self.current_step >= len(self.active_routine):
            self.is_playing = False

ROUTINES = {
    "Code Blue (VTach -> VFib -> Asystole)": [
        {"t": 0,  "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 85}},
        {"t": 10, "state": {"hr": 160}},
        {"t": 15, "state": {"ecg_rhythm": "[Vent] VTach"}},
        {"t": 30, "state": {"ecg_rhythm": "[Vent] VFib"}},
        {"t": 50, "state": {"ecg_rhythm": "[Arrest] Asystole"}}
    ],
    "Malignant Hyperthermia Onset": [
        {"t": 0,  "state": {"temp": 37.0, "etco2": 40, "hr": 90}},
        {"t": 10, "state": {"temp": 38.5, "etco2": 65, "hr": 130}},
        {"t": 30, "state": {"temp": 40.0, "etco2": 85, "hr": 160, "bp_sys": 80}}
    ],
    "Rapid Sequence Intubation (RSI)": [
        {"t": 0,  "state": {"hr": 110, "spo2": 95, "rr": 20, "resp_pattern": "Tachypnea", "probe_etco2": True}},
        {"t": 5,  "state": {"resp_pattern": "Apnea", "rr": 0}},
        {"t": 15, "state": {"spo2": 85}},
        {"t": 30, "state": {"spo2": 70, "hr": 140}},
        {"t": 40, "state": {"resp_pattern": "Eupnea (Normal)", "rr": 16}}, # Intubated & bagged
        {"t": 45, "state": {"spo2": 99, "hr": 95}}
    ],
    "Progressive Hypoxia": [
        {"t": 0,  "state": {"spo2": 98, "hr": 80}},
        {"t": 20, "state": {"spo2": 88, "hr": 110, "resp_pattern": "Tachypnea"}},
        {"t": 40, "state": {"spo2": 75, "hr": 130, "ecg_rhythm": "[Vent] PVCs"}},
        {"t": 60, "state": {"spo2": 60, "hr": 45, "ecg_rhythm": "[Norm] Sinus Rhythm", "resp_pattern": "Bradypnea"}},
        {"t": 80, "state": {"ecg_rhythm": "[Arrest] PEA", "resp_pattern": "Apnea"}}
    ],
    "Recovery from VFib (Defibrillation)": [
        {"t": 0,  "state": {"ecg_rhythm": "[Vent] VFib", "hr": 0}},
        {"t": 10, "state": {"ecg_rhythm": "[Arrest] Asystole"}}, # Shock delivered
        {"t": 13, "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 120, "bp_sys": 80, "bp_dia": 50, "spo2": 85}},
        {"t": 30, "state": {"hr": 95, "bp_sys": 110, "bp_dia": 70, "spo2": 96}}
    ]
}
