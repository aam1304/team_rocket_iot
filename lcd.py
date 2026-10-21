"""
lcd.py
------
16x2 status display. Backlight off in sleep mode.
"""

from config import USE_REAL_HARDWARE

_real_lcd = None
if USE_REAL_HARDWARE:
    try:
        from RPLCD.i2c import CharLCD
        _real_lcd = CharLCD('PCF8574', 0x3f, cols=16, rows=2)
    except Exception as e:
        print(f"[WARN] CharLCD init failed ({e}); falling back to print mode.")
        _real_lcd = None


def update_lcd(mode: str, bed_occupied: bool, desk_occupied: bool) -> None:
    line1 = f"Mode: {mode.capitalize()}"
    line2 = f"Bed {int(bed_occupied)} Desk {int(desk_occupied)}"

    if _real_lcd is not None:
        _real_lcd.clear()
        _real_lcd.write_string(line1)
        _real_lcd.cursor_pos = (1, 0)
        _real_lcd.write_string(line2)
        _real_lcd.backlight_enabled = (mode != "sleep")
    else:
        backlight = "OFF" if mode == "sleep" else "ON"
        print(f'[LCD] "{line1}" / "{line2}"  (backlight {backlight})')