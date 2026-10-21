"""
config.py
---------
Thresholds and weights for the room-mode scoring system.
"""

import os

# --- Alerts (Discord webhook) ---
# Set the DISCORD_WEBHOOK_URL environment variable rather than
# hardcoding the real URL here - anyone with the URL can post to the
# channel, so it must never be committed to the repo. If it's not
# set, alerts.py just prints locally instead of posting - useful for
# dev/testing without a real webhook configured.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

LOOP_ERROR_ALERT_THRESHOLD = 3       # consecutive loop errors before alerting
DHT22_FAILURE_ALERT_THRESHOLD = 20   # consecutive failed temp reads before alerting

# --- Hardware switch ---
USE_REAL_HARDWARE = True  # False: mock sensors + print-based LED/LCD

# --- Pressure pads (0-5) ---
PAD_OCCUPIED_THRESHOLD = 1  # confirmed by Nicole: empty reads 0, sitting reads 1-4,
                             # so the halfway point (0.5) rounds to 1 on whole numbers

# A single stray reading shouldn't flip the occupied flag on its own -
# Nicole's bench tests found an empty pad can drift to 1-2. Require
# the raw reading to agree for this many polls before the flag
# actually changes. At main.py's ~5s/poll pace, 3 polls is ~15 seconds.
PAD_DEBOUNCE_POLLS = 3

# --- Ambient light (0-255, higher = darker) ---
LIGHT_DARK_RAW_MIN = 220
LIGHT_BRIGHT_RAW_MAX = 150

# --- Ambient sound (0-255 raw; spread across a window, not one reading) ---
SOUND_QUIET_MAX = 6
SOUND_ACTIVE_MIN = 8
SOUND_WINDOW_SAMPLES = 100
SOUND_WINDOW_SAMPLE_DELAY = 0.05   # 100 x 0.05s = 5s window
SOUND_HOLD_WINDOWS = 6            # consecutive windows before committing

# --- Temperature (°C) ---
TEMP_STUDY_LOW_C = 22.0
TEMP_STUDY_HIGH_C = 24.0

# --- Time of day ---
STUDY_HOURS_START = 8
STUDY_HOURS_END = 22

# --- Evidence weights (+study / -sleep) ---
WEIGHTS = {
    "bed_occupied": -3,
    "desk_occupied": 3,
    "light_bright": 2,
    "light_dark": -2,
    "sound_quiet": -1,
    "temp_outside_study_range": 0,  # disabled: DHT22 reliability, see report future work
    "time_of_day_study_hours": 1,
    "time_of_day_sleep_hours": -1,
}

# --- Hysteresis ---
SCORE_UPPER_THRESHOLD = 5
SCORE_LOWER_THRESHOLD = -5
SCORE_DECAY = 0.9  # per-poll retention of previous score

# --- Empty room handling ---
EMPTY_ROOM_MINUTES = 1  # both pads clear this long -> force unoccupied, reset score

# --- LED colours (RGB module: GPIO17=R, GPIO27=G, GPIO22=B) ---
# Provisional. Pending final mapping from Nicole.
LED_COLORS = {
    "study": (0, 1, 0),
    "sleep": (0, 0, 1),
    "unoccupied": (1, 0, 0),
    "relax": (1, 0.35, 0),   # orange
}

POLL_INTERVAL_SECONDS = 2