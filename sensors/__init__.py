"""
sensors/__init__.py
--------------------
Selects mock or real sensor module based on config.USE_REAL_HARDWARE.
Falls back to mock if real_sensors fails to import - and alerts the
team on Discord when that happens, since running on fake data without
anyone noticing would be far worse than the import failure itself.
"""

from config import USE_REAL_HARDWARE
from alerts import send_alert

if USE_REAL_HARDWARE:
    try:
        from . import real_sensors as active
    except Exception as e:
        msg = f"real_sensors failed to import ({e}) - running on MOCK data instead."
        print(f"[WARN] {msg}")
        send_alert(msg)
        from . import mock_sensors as active
else:
    from . import mock_sensors as active