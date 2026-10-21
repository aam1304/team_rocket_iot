"""
actuators.py
------------
RGB LED status light (GPIO17/27/22).
"""

from config import LED_COLORS, USE_REAL_HARDWARE

_last_mode_shown = None

_COLOR_NAMES = {
    (0, 1, 0): "GREEN",
    (0, 0, 1): "BLUE",
    (1, 0, 0): "RED",
    (0, 0, 0): "OFF",
    (1, 0.35, 0): "ORANGE",
}

_real_led = None
if USE_REAL_HARDWARE:
    try:
        from gpiozero import RGBLED
        _real_led = RGBLED(red=17, green=27, blue=22, active_high=False)
    except Exception as e:
        print(f"[WARN] RGBLED init failed ({e}); falling back to print mode.")
        _real_led = None


def set_led_for_mode(mode: str) -> None:
    global _last_mode_shown
    if mode == _last_mode_shown:
        return

    rgb = LED_COLORS.get(mode, (0, 0, 0))

    if _real_led is not None:
        _real_led.color = rgb
    else:
        name = _COLOR_NAMES.get(rgb, f"RGB{rgb}")
        print(f"[LED] -> {name} (mode: {mode})")

    _last_mode_shown = mode