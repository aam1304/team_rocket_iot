"""
main.py
-------
Room-mode monitor main loop: read sensors, sample sound, score,
drive LED/LCD, log. Runs against mock sensors by default.

    python3 main.py

Ctrl+C to stop. Sensor read failures fall back to the last good
value; unexpected loop errors are logged and the loop retries after
a short delay rather than crashing.
"""

import time

from config import (
    SOUND_WINDOW_SAMPLES, SOUND_WINDOW_SAMPLE_DELAY,
    LOOP_ERROR_ALERT_THRESHOLD, DHT22_FAILURE_ALERT_THRESHOLD,
)
from sensors import active as sensors
from occupancy import PadDebouncer
from scoring import ModeScorer
from actuators import set_led_for_mode
from lcd import update_lcd
from sound_state import sample_sound_window, SoundDebouncer
from alerts import send_alert
import logger

LOOP_ERROR_RETRY_SECONDS = 5
REAL_POLL_MINUTES = (SOUND_WINDOW_SAMPLES * SOUND_WINDOW_SAMPLE_DELAY) / 60


def main():
    logger.init_log()
    logger.init_transitions_log()
    scorer = ModeScorer()
    sound_debouncer = SoundDebouncer()
    bed_debouncer = PadDebouncer()
    desk_debouncer = PadDebouncer()

    last_good = {"bed": 0.0, "desk": 0.0, "light": 0.0}
    last_mode = scorer.mode

    # Alert-tracking state: counts consecutive failures of each kind,
    # alerts once per "episode" rather than spamming Discord on every
    # single poll while a problem persists.
    consecutive_loop_errors = 0
    loop_error_alerted = False
    consecutive_temp_failures = 0
    temp_failure_alerted = False

    print("Starting Team Rocket room-mode monitor.")
    print(f"Logging to {logger.DEFAULT_LOG_PATH}")
    print("Each cycle takes ~5 seconds. Ctrl+C to stop.\n")

    try:
        while True:
            try:
                try:
                    bed_raw = sensors.read_bed_pressure_raw()
                    last_good["bed"] = bed_raw
                except Exception as e:
                    print(f"[WARN] bed pad read failed: {e}")
                    bed_raw = last_good["bed"]

                try:
                    desk_raw = sensors.read_desk_pressure_raw()
                    last_good["desk"] = desk_raw
                except Exception as e:
                    print(f"[WARN] desk pad read failed: {e}")
                    desk_raw = last_good["desk"]

                try:
                    light_raw = sensors.read_light_level()
                    last_good["light"] = light_raw
                except Exception as e:
                    print(f"[WARN] light read failed: {e}")
                    light_raw = last_good["light"]

                bed = bed_debouncer.update(bed_raw)
                desk = desk_debouncer.update(desk_raw)

                try:
                    spread, instant_state = sample_sound_window(sensors.read_sound_level)
                except Exception as e:
                    print(f"[WARN] sound sampling failed: {e}")
                    spread, instant_state = 0.0, "gap"
                committed_sound_state = sound_debouncer.update(instant_state)

                try:
                    temp, humidity = sensors.read_temperature_humidity()
                    temp_read_ok = temp is not None
                except Exception as e:
                    print(f"[WARN] temperature/humidity read failed: {e}")
                    temp, humidity, temp_read_ok = None, None, False

                if temp_read_ok:
                    consecutive_temp_failures = 0
                    temp_failure_alerted = False
                else:
                    consecutive_temp_failures += 1
                    if (consecutive_temp_failures >= DHT22_FAILURE_ALERT_THRESHOLD
                            and not temp_failure_alerted):
                        send_alert(f"DHT22 has failed {consecutive_temp_failures} "
                                   f"reads in a row - temperature/humidity may be dead.")
                        temp_failure_alerted = True

                mode = scorer.update(bed, desk, light_raw, committed_sound_state,
                                      temp, poll_minutes=REAL_POLL_MINUTES)

                if mode != last_mode:
                    logger.log_mode_transition(last_mode, mode)
                    last_mode = mode

                logger.log_row(bed_raw, desk_raw, bed, desk,
                                light_raw,
                                spread, instant_state, committed_sound_state,
                                temp, humidity, temp_read_ok,
                                scorer.score, mode,
                                label="" if sensors.__name__.endswith("real_sensors") else "MOCK")

                set_led_for_mode(mode)
                update_lcd(mode, bed, desk)

                temp_str = f"{temp:4.1f}C" if temp is not None else " N/A "
                print(f"bed={bed!s:<5} desk={desk!s:<5} light_raw={light_raw:5.1f} "
                      f"sound_spread={spread:4.1f}({instant_state:<6}->{committed_sound_state:<6}) "
                      f"temp={temp_str} score={scorer.score:6.2f} mode={mode}")

                # Made it through a full iteration cleanly - reset the
                # loop-error streak so a past problem doesn't keep
                # counting against a future, unrelated one.
                consecutive_loop_errors = 0
                loop_error_alerted = False

            except Exception as loop_err:
                consecutive_loop_errors += 1
                print(f"[ERROR] loop error ({consecutive_loop_errors} in a row), "
                      f"retrying in {LOOP_ERROR_RETRY_SECONDS}s: {loop_err}")

                if (consecutive_loop_errors >= LOOP_ERROR_ALERT_THRESHOLD
                        and not loop_error_alerted):
                    send_alert(f"Main loop has failed {consecutive_loop_errors} times "
                               f"in a row: {loop_err}")
                    loop_error_alerted = True

                time.sleep(LOOP_ERROR_RETRY_SECONDS)

    except KeyboardInterrupt:
        print(f"\nStopped. Data in {logger.DEFAULT_LOG_PATH}")


if __name__ == "__main__":
    main()