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
    ],

    # --- CARDIAC ---

    "Acute STEMI with Cardiogenic Shock": [
        {"t": 0,  "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 95, "bp_sys": 120, "bp_dia": 80}},
        {"t": 10, "state": {"ecg_rhythm": "[Block] 1st Deg AV", "hr": 85}},
        {"t": 20, "state": {"hr": 55, "bp_sys": 90, "bp_dia": 60}},
        {"t": 35, "state": {"ecg_rhythm": "[Block] 3rd Deg AV", "hr": 38, "bp_sys": 70, "bp_dia": 40}},
        {"t": 50, "state": {"ecg_rhythm": "[Arrest] PEA", "hr": 0, "spo2": 80}}
    ],

    "Torsades de Pointes Onset": [
        {"t": 0,  "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 75}},
        {"t": 10, "state": {"ecg_rhythm": "[Vent] PVCs", "hr": 90}},
        {"t": 20, "state": {"ecg_rhythm": "[Vent] Torsades", "hr": 220, "bp_sys": 70}},
        {"t": 35, "state": {"ecg_rhythm": "[Vent] VFib"}},
        {"t": 45, "state": {"ecg_rhythm": "[Arrest] Asystole", "hr": 0}}
    ],

    "AFib with RVR -> Rate Control": [
        {"t": 0,  "state": {"ecg_rhythm": "[Atrial] AFib", "hr": 155, "bp_sys": 100, "bp_dia": 65}},
        {"t": 15, "state": {"hr": 130}},
        {"t": 30, "state": {"hr": 105}},
        {"t": 50, "state": {"hr": 82, "bp_sys": 118, "bp_dia": 74}}
    ],

    "AFlutter with 2:1 Block -> Cardioversion": [
        {"t": 0,  "state": {"ecg_rhythm": "[Atrial] AFlutter", "hr": 150, "bp_sys": 105, "bp_dia": 70}},
        {"t": 20, "state": {"ecg_rhythm": "[Arrest] Asystole", "hr": 0}},   # Synchronized cardioversion
        {"t": 23, "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 88, "bp_sys": 120, "bp_dia": 78}}
    ],

    "Complete Heart Block (3rd Deg AV)": [
        {"t": 0,  "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 78}},
        {"t": 10, "state": {"ecg_rhythm": "[Block] Wenckebach", "hr": 65}},
        {"t": 25, "state": {"ecg_rhythm": "[Block] 3rd Deg AV", "hr": 38, "bp_sys": 85, "bp_dia": 55}},
        {"t": 45, "state": {"ecg_rhythm": "[Arrest] Asystole", "hr": 0}}
    ],

    # --- RESPIRATORY ---

    "Tension Pneumothorax": [
        {"t": 0,  "state": {"hr": 100, "spo2": 94, "rr": 22, "resp_pattern": "Tachypnea", "bp_sys": 115}},
        {"t": 15, "state": {"spo2": 85, "hr": 125, "bp_sys": 95}},
        {"t": 30, "state": {"spo2": 72, "hr": 145, "bp_sys": 70, "resp_pattern": "Bradypnea"}},
        {"t": 45, "state": {"ecg_rhythm": "[Arrest] PEA", "hr": 0, "resp_pattern": "Apnea"}}
    ],

    "Severe Bronchospasm / Status Asthmaticus": [
        {"t": 0,  "state": {"hr": 105, "spo2": 91, "rr": 28, "resp_pattern": "Tachypnea", "etco2": 30}},
        {"t": 15, "state": {"spo2": 83, "hr": 130, "etco2": 55}},   # CO2 retention / tiring out
        {"t": 30, "state": {"spo2": 74, "rr": 8, "resp_pattern": "Bradypnea", "etco2": 75}},
        {"t": 45, "state": {"resp_pattern": "Apnea", "rr": 0, "ecg_rhythm": "[Arrest] PEA"}}
    ],

    "Opioid Overdose -> Naloxone Reversal": [
        {"t": 0,  "state": {"hr": 58, "spo2": 78, "rr": 4, "resp_pattern": "Bradypnea", "etco2": 72}},
        {"t": 10, "state": {"spo2": 65, "resp_pattern": "Apnea", "rr": 0}},  # Pre-Narcan nadir
        {"t": 15, "state": {"rr": 10, "resp_pattern": "Tachypnea", "spo2": 82}},  # Naloxone given
        {"t": 25, "state": {"hr": 95, "spo2": 96, "rr": 18, "etco2": 40}}
    ],

    "Cheyne-Stokes (Neurological Deterioration)": [
        {"t": 0,  "state": {"hr": 88, "spo2": 96, "rr": 16, "resp_pattern": "Eupnea (Normal)"}},
        {"t": 15, "state": {"resp_pattern": "Cheyne-Stokes", "rr": 10, "spo2": 90}},
        {"t": 35, "state": {"spo2": 80, "hr": 110, "ecg_rhythm": "[Vent] PVCs"}},
        {"t": 55, "state": {"resp_pattern": "Apnea", "rr": 0, "ecg_rhythm": "[Arrest] PEA"}}
    ],

    "Kussmaul Breathing (DKA)": [
        {"t": 0,  "state": {"hr": 115, "spo2": 97, "rr": 28, "resp_pattern": "Kussmaul", "etco2": 18}},
        {"t": 20, "state": {"hr": 130, "bp_sys": 90, "bp_dia": 55}},          # Volume depletion
        {"t": 40, "state": {"ecg_rhythm": "[Vent] PVCs", "hr": 145}},          # Hyperkalemia effect
        {"t": 60, "state": {"ecg_rhythm": "[Vent] VFib", "hr": 0}}
    ],

    # --- HEMODYNAMIC ---

    "Anaphylaxis -> Cardiovascular Collapse": [
        {"t": 0,  "state": {"hr": 110, "bp_sys": 95, "bp_dia": 60, "spo2": 93, "resp_pattern": "Tachypnea"}},
        {"t": 10, "state": {"hr": 140, "bp_sys": 70, "bp_dia": 40, "spo2": 85}},
        {"t": 20, "state": {"ecg_rhythm": "[Vent] PVCs", "hr": 155, "bp_sys": 55}},
        {"t": 35, "state": {"ecg_rhythm": "[Arrest] PEA", "hr": 0, "resp_pattern": "Apnea"}}
    ],

    "Septic Shock Progression": [
        {"t": 0,  "state": {"hr": 118, "bp_sys": 95, "bp_dia": 55, "temp": 39.2, "rr": 24, "resp_pattern": "Tachypnea"}},
        {"t": 20, "state": {"hr": 135, "bp_sys": 80, "bp_dia": 45, "spo2": 90}},
        {"t": 40, "state": {"hr": 150, "bp_sys": 65, "bp_dia": 35, "spo2": 82, "etco2": 22}},
        {"t": 60, "state": {"ecg_rhythm": "[Arrest] PEA", "resp_pattern": "Apnea", "hr": 0}}
    ],

    "Hypovolemic Shock (Hemorrhage)": [
        {"t": 0,  "state": {"hr": 100, "bp_sys": 110, "bp_dia": 70, "spo2": 98}},
        {"t": 15, "state": {"hr": 125, "bp_sys": 90, "bp_dia": 60}},
        {"t": 30, "state": {"hr": 148, "bp_sys": 70, "bp_dia": 40, "spo2": 92}},
        {"t": 45, "state": {"ecg_rhythm": "[Arrest] PEA", "hr": 0, "bp_sys": 0, "spo2": 75}}
    ],

    # --- METABOLIC / TEMPERATURE ---

    "Hyperkalemia Cardiac Progression": [
        {"t": 0,  "state": {"ecg_rhythm": "[Block] 1st Deg AV", "hr": 72}},
        {"t": 15, "state": {"ecg_rhythm": "[Block] Wenckebach", "hr": 58}},
        {"t": 30, "state": {"ecg_rhythm": "[Vent] VTach", "hr": 180}},
        {"t": 45, "state": {"ecg_rhythm": "[Vent] VFib"}},
        {"t": 55, "state": {"ecg_rhythm": "[Arrest] Asystole", "hr": 0}}
    ],

    "Hypothermia Progression": [
        {"t": 0,  "state": {"temp": 35.0, "hr": 60, "ecg_rhythm": "[Norm] Sinus Rhythm", "rr": 14}},
        {"t": 15, "state": {"temp": 33.0, "hr": 48, "ecg_rhythm": "[Block] 1st Deg AV"}},
        {"t": 30, "state": {"temp": 30.0, "hr": 35, "ecg_rhythm": "[Vent] VFib", "resp_pattern": "Bradypnea"}},
        {"t": 50, "state": {"temp": 28.0, "ecg_rhythm": "[Arrest] Asystole", "hr": 0, "resp_pattern": "Apnea"}}
    ],

    "Thyroid Storm": [
        {"t": 0,  "state": {"hr": 140, "temp": 38.8, "bp_sys": 160, "bp_dia": 90, "ecg_rhythm": "[Atrial] AFib"}},
        {"t": 20, "state": {"hr": 170, "temp": 40.5, "bp_sys": 180, "bp_dia": 95}},
        {"t": 40, "state": {"ecg_rhythm": "[Vent] VTach", "hr": 200, "bp_sys": 85}},
        {"t": 55, "state": {"ecg_rhythm": "[Vent] VFib", "hr": 0}}
    ],

    # --- PROCEDURAL ---

    "Post-Intubation Right Mainstem Intubation": [
        {"t": 0,  "state": {"spo2": 99, "hr": 80, "resp_pattern": "Eupnea (Normal)", "rr": 14, "etco2": 38}},
        {"t": 5,  "state": {"spo2": 91, "etco2": 52}},   # Tube slips right
        {"t": 15, "state": {"spo2": 80, "hr": 115}},
        {"t": 25, "state": {"spo2": 95, "hr": 88, "etco2": 40}}  # Tube repositioned
    ],

    "Succinylcholine-Induced Bradycardia": [
        {"t": 0,  "state": {"hr": 90, "ecg_rhythm": "[Norm] Sinus Rhythm"}},
        {"t": 3,  "state": {"hr": 42, "ecg_rhythm": "[Block] 3rd Deg AV", "bp_sys": 75}},
        {"t": 8,  "state": {"ecg_rhythm": "[Arrest] Asystole", "hr": 0}},
        {"t": 12, "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 78, "bp_sys": 115}}  # Atropine response
    ],

    "Epidural-Induced Hypotension": [
        {"t": 0,  "state": {"hr": 78, "bp_sys": 125, "bp_dia": 80, "spo2": 99}},
        {"t": 5,  "state": {"bp_sys": 95, "bp_dia": 60, "hr": 88}},
        {"t": 15, "state": {"bp_sys": 72, "bp_dia": 45, "hr": 105}},
        {"t": 25, "state": {"bp_sys": 118, "bp_dia": 76, "hr": 80}}  # Ephedrine / fluid bolus
    ],

    "Intraoperative Cascade: Anesthetic Overdose → Arrest → ROSC → MH Crisis": [

    # === PHASE 1: Baseline (Patient awake, pre-induction) ===
    {"t": 0,   "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 88, "bp_sys": 128, "bp_dia": 82, "spo2": 98, "rr": 16, "resp_pattern": "Eupnea (Normal)", "temp": 36.8, "etco2": 38}},

    # === PHASE 2: Induction & Intubation ===
    {"t": 30,  "state": {"hr": 105, "resp_pattern": "Tachypnea", "rr": 22}},         # Pre-ox / anxiety
    {"t": 45,  "state": {"resp_pattern": "Apnea", "rr": 0}},                          # RSI drugs given
    {"t": 60,  "state": {"resp_pattern": "Eupnea (Normal)", "rr": 14, "etco2": 36}}, # Intubated, confirmed
    {"t": 75,  "state": {"hr": 72, "bp_sys": 115, "bp_dia": 74, "spo2": 99}},        # Stable under GA

    # === PHASE 3: Anesthetic Overdose (Volatile agent too high) ===
    {"t": 120, "state": {"bp_sys": 88, "bp_dia": 52, "hr": 58}},                      # BP dropping
    {"t": 140, "state": {"ecg_rhythm": "[Block] 1st Deg AV", "hr": 48, "bp_sys": 70, "bp_dia": 40}},
    {"t": 160, "state": {"ecg_rhythm": "[Block] 3rd Deg AV", "hr": 32, "bp_sys": 55, "bp_dia": 30, "spo2": 90}},
    {"t": 175, "state": {"ecg_rhythm": "[Arrest] PEA", "hr": 0, "bp_sys": 0, "spo2": 82}}, # Full arrest

    # === PHASE 4: CPR & ACLS ===
    {"t": 180, "state": {"ecg_rhythm": "[Vent] VFib"}},                               # Rhythm check — VFib!
    {"t": 195, "state": {"ecg_rhythm": "[Arrest] Asystole"}},                         # Shock #1 delivered
    {"t": 200, "state": {"ecg_rhythm": "[Vent] VFib"}},                               # Refibrillates
    {"t": 215, "state": {"ecg_rhythm": "[Arrest] Asystole"}},                         # Shock #2
    {"t": 222, "state": {"ecg_rhythm": "[Vent] PVCs", "hr": 35}},                    # Agonal beats
    {"t": 235, "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 55, "bp_sys": 68, "bp_dia": 38, "spo2": 78}}, # ROSC

    # === PHASE 5: Post-ROSC Stabilization ===
    {"t": 250, "state": {"hr": 72, "bp_sys": 88, "bp_dia": 55, "spo2": 88}},
    {"t": 270, "state": {"hr": 80, "bp_sys": 105, "bp_dia": 68, "spo2": 94, "etco2": 42}},
    {"t": 300, "state": {"hr": 85, "bp_sys": 118, "bp_dia": 74, "spo2": 97}},        # Team breathes

    # === PHASE 6: Malignant Hyperthermia Onset (Triggered by volatile agent exposure) ===
    {"t": 330, "state": {"temp": 37.9, "etco2": 58, "hr": 100}},                     # EtCO2 climbing — first sign
    {"t": 360, "state": {"temp": 38.8, "etco2": 74, "hr": 128, "resp_pattern": "Tachypnea", "rr": 26}},
    {"t": 390, "state": {"temp": 39.9, "etco2": 90, "hr": 152, "bp_sys": 85, "bp_dia": 50}},
    {"t": 420, "state": {"temp": 41.2, "etco2": 105, "ecg_rhythm": "[Vent] PVCs", "hr": 168}}, # Rigidity, acidosis
    {"t": 450, "state": {"ecg_rhythm": "[Vent] VTach", "hr": 195, "temp": 42.0, "bp_sys": 70}},

    # === PHASE 7: MH Treatment & Second Arrest ===
    {"t": 465, "state": {"ecg_rhythm": "[Vent] VFib", "hr": 0}},                     # Degenerates
    {"t": 475, "state": {"ecg_rhythm": "[Arrest] Asystole"}},                        # Shock #3
    {"t": 480, "state": {"ecg_rhythm": "[Norm] Sinus Rhythm", "hr": 110, "bp_sys": 82, "bp_dia": 48}}, # ROSC #2 (Dantrolene working)

    # === PHASE 8: Slow Recovery (Dantrolene, cooling, ICU handoff) ===
    {"t": 510, "state": {"temp": 41.0, "etco2": 78, "hr": 98}},
    {"t": 560, "state": {"temp": 39.5, "etco2": 55, "hr": 88, "bp_sys": 100, "bp_dia": 62}},
    {"t": 620, "state": {"temp": 38.2, "etco2": 42, "hr": 80, "bp_sys": 115, "bp_dia": 72, "spo2": 97}},
    {"t": 680, "state": {"temp": 37.4, "etco2": 38, "hr": 74, "bp_sys": 120, "bp_dia": 78, "spo2": 99, "resp_pattern": "Eupnea (Normal)"}} # Stable for ICU
],
}
