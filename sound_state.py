"""
sound_state.py
----------------
Sound sensor handling: spread across a sampling window, debounced
across several windows before a state change commits.
"""

import time
from config import (
    SOUND_QUIET_MAX,
    SOUND_ACTIVE_MIN,
    SOUND_WINDOW_SAMPLES,
    SOUND_WINDOW_SAMPLE_DELAY,
    SOUND_HOLD_WINDOWS,
)


def sample_sound_window(read_fn, at_hour: float = None, real_delay: float = None):
    """Returns (spread, instant_state) for one sampling window.
    real_delay=0 skips the inter-sample wait, for simulate_day.py."""
    delay = SOUND_WINDOW_SAMPLE_DELAY if real_delay is None else real_delay
    readings = []
    last_good = 0.0
    for _ in range(SOUND_WINDOW_SAMPLES):
        try:
            value = read_fn(at_hour=at_hour) if at_hour is not None else read_fn()
            last_good = value
        except Exception as e:
            print(f"[WARN] sound sample failed, reusing last value: {e}")
            value = last_good
        readings.append(value)
        if delay:
            time.sleep(delay)

    # Percentile band (90th minus 10th) instead of max minus min: a lone
    # spike no longer decides the window. Logged as sound_spread.
    ordered = sorted(readings)
    n = len(ordered)
    spread = ordered[min(int(n * 0.9), n - 1)] - ordered[int(n * 0.1)]
    if spread <= SOUND_QUIET_MAX:
        state = "quiet"
    elif spread >= SOUND_ACTIVE_MIN:
        state = "active"
    else:
        state = "gap"

    return spread, state


class SoundDebouncer:
    """Commits to a new state only after it holds for several
    consecutive windows, so one borderline window can't flip the mode."""

    def __init__(self):
        self.committed_state = "quiet"
        self._candidate_state = None
        self._candidate_count = 0

    def update(self, instantaneous_state: str) -> str:
        if instantaneous_state == "gap":
            if self.committed_state == "active":
                # Leaving "active" is easier than entering it: a gap
                # window (below SOUND_ACTIVE_MIN) counts as quiet, so
                # typing and background noise can't hold "active" on.
                instantaneous_state = "quiet"
            else:
                # Staying "quiet": a gap (e.g. typing) changes nothing.
                return self.committed_state

        if instantaneous_state == self._candidate_state:
            self._candidate_count += 1
        else:
            self._candidate_state = instantaneous_state
            self._candidate_count = 1

        if (self._candidate_state != self.committed_state
                and self._candidate_count >= SOUND_HOLD_WINDOWS):
            self.committed_state = self._candidate_state

        return self.committed_state
