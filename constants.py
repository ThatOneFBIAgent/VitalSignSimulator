# Shared constants and themes to avoid circular imports

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
