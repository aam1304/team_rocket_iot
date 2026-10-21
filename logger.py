"""
logger.py
---------
CSV logging: one row per poll, plus a separate mode-transitions log.
Filenames include the run start time so a restart never appends to a
previous run's data.
"""

import csv
import os
import datetime

_RUN_START = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
# Logs go in a "logs" folder next to this file, whatever directory the
# program is started from.
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
DEFAULT_LOG_PATH = os.path.join(LOG_DIR, f"sensor_log_{_RUN_START}.csv")
DEFAULT_TRANSITIONS_PATH = os.path.join(LOG_DIR, f"mode_transitions_{_RUN_START}.csv")

_HEADER = [
    "timestamp",
    "bed_pad_raw", "desk_pad_raw", "bed_occupied", "desk_occupied",
    "light_raw",
    "sound_spread", "sound_instant_state", "sound_committed_state",
    "temperature_c", "humidity_pct", "temp_read_ok",
    "score", "mode", "label",
]

_TRANSITIONS_HEADER = ["timestamp", "old_mode", "new_mode"]


def init_log(path: str = None) -> None:
    path = path or DEFAULT_LOG_PATH
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(_HEADER)


def init_transitions_log(path: str = None) -> None:
    path = path or DEFAULT_TRANSITIONS_PATH
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(_TRANSITIONS_HEADER)


def log_row(bed_pad_raw, desk_pad_raw, bed_occupied, desk_occupied,
            light_raw, sound_spread, sound_instant_state, sound_committed_state,
            temp_c, humidity_pct, temp_read_ok,
            score, mode, label: str = "", path: str = None) -> None:
    path = path or DEFAULT_LOG_PATH
    temp_str = round(temp_c, 1) if temp_c is not None else ""
    humidity_str = round(humidity_pct, 1) if humidity_pct is not None else ""

    with open(path, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            bed_pad_raw, desk_pad_raw, bed_occupied, desk_occupied,
            round(light_raw, 1),
            round(sound_spread, 1), sound_instant_state, sound_committed_state,
            temp_str, humidity_str, temp_read_ok,
            round(score, 2), mode, label,
        ])


def log_mode_transition(old_mode: str, new_mode: str, path: str = None) -> None:
    path = path or DEFAULT_TRANSITIONS_PATH
    with open(path, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            old_mode, new_mode,
        ])