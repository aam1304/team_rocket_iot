"""
mock_sensors.py
----------------
Fake sensor readings for development without hardware. Function names
and ranges match the real sensors.
"""

import random
import datetime


def _current_hour(at_hour) -> float:
    return at_hour if at_hour is not None else datetime.datetime.now().hour


def read_bed_pressure_raw(at_hour: float = None) -> float:
    """
    Matches Nicole's confirmed real pad range: empty=0, sitting=1-4.
    Occasionally drifts to 1-2 even when "empty", same as the real
    pad - this is what the debounce in occupancy.py exists to handle.
    """
    hour = _current_hour(at_hour)
    is_night = hour >= 23 or hour < 7
    expect_occupied = is_night if random.random() > 0.05 else not is_night
    if expect_occupied:
        return float(random.randint(1, 4))
    if random.random() < 0.15:
        return float(random.randint(1, 2))  # "empty" but drifting
    return 0.0


def read_desk_pressure_raw(at_hour: float = None) -> float:
    """Same real range and drift behaviour as the bed pad, flipped for daytime."""
    hour = _current_hour(at_hour)
    is_daytime = 8 <= hour < 22
    expect_occupied = is_daytime if random.random() > 0.05 else not is_daytime
    if expect_occupied:
        return float(random.randint(1, 4))
    if random.random() < 0.15:
        return float(random.randint(1, 2))
    return 0.0


def read_light_level(at_hour: float = None) -> float:
    hour = _current_hour(at_hour)
    base = 30 if 8 <= hour < 20 else 230
    return max(0.0, min(255.0, base + random.uniform(-25, 25)))


def read_sound_level(at_hour: float = None) -> float:
    hour = _current_hour(at_hour)
    daytime = 8 <= hour < 22
    base = 120 if daytime else 15
    spread_width = 40 if daytime else 3
    return max(0.0, min(255.0, base + random.uniform(-spread_width, spread_width)))


def read_temperature_humidity():
    if random.random() < 0.05:
        return None, None
    temp = 21.0 + random.uniform(-2, 2)
    humidity = 45.0 + random.uniform(-5, 5)
    return temp, humidity