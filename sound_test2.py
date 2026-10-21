import time, statistics
from sensors import real_sensors as s

def window():
    r = []
    for _ in range(100):
        r.append(s.read_sound_level())
        time.sleep(0.05)
    r.sort()
    return max(r) - min(r), r[90] - r[10], statistics.pstdev(r)

for label in ["SILENT (hands off)", "TYPING normally", "MUSIC or talking"]:
    input(f"\nNext: {label}. Press Enter, then wait 5 seconds, then do it...")
    time.sleep(5)
    window()
    rows = []
    for i in range(8):
        sp, band, sd = window()
        rows.append((sp, band, sd))
        print(f"  window {i+1}: spread={sp:.0f}  band={band:.0f}  stdev={sd:.1f}")
    for name, k in [("spread", 0), ("band", 1), ("stdev", 2)]:
        vals = [x[k] for x in rows]
        print(f"  {label} {name}: lowest {min(vals):.1f}, highest {max(vals):.1f}")
