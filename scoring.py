"""
scoring.py
----------
Weighted evidence accumulator with decay and hysteresis. Mode changes
only when the score crosses an upper/lower threshold, and an empty
room (both pads clear) past EMPTY_ROOM_MINUTES forces "unoccupied".
A rule-based "relax" mode overrides study/sleep when someone is awake
in bed with the light on, or at the desk with loud sound.
"""

import datetime
from config import (
    WEIGHTS,
    SCORE_UPPER_THRESHOLD,
    SCORE_LOWER_THRESHOLD,
    SCORE_DECAY,
    EMPTY_ROOM_MINUTES,
    LIGHT_DARK_RAW_MIN,
    LIGHT_BRIGHT_RAW_MAX,
    STUDY_HOURS_START,
    STUDY_HOURS_END,
    TEMP_STUDY_LOW_C,
    TEMP_STUDY_HIGH_C,
)


class ModeScorer:
    """Running score and current mode across repeated polls."""

    def __init__(self):
        self.score = 0.0
        self.mode = "unoccupied"
        self._empty_minutes = 0.0
        self._last_shown = "unoccupied"

    def update(self, bed_occupied, desk_occupied, light_raw, sound_state,
               temp_c, at_hour=None, poll_minutes=1.0):
        """Mode to show. While both pads are empty but the empty-room
        timeout has not run out, the last SHOWN mode is held, so a hidden
        underlying mode (e.g. sleep under relax) never flashes up as
        someone gets out of bed."""
        mode = self._evaluate(bed_occupied, desk_occupied, light_raw,
                              sound_state, temp_c, at_hour, poll_minutes)
        if (not bed_occupied and not desk_occupied
                and self._empty_minutes < EMPTY_ROOM_MINUTES):
            mode = self._last_shown
        self._last_shown = mode
        return mode

    def _evaluate(self, bed_occupied: bool, desk_occupied: bool,
               light_raw: float, sound_state: str, temp_c,
               at_hour: float = None, poll_minutes: float = 1.0) -> str:
        """
        light_raw: 0-255, higher = darker.
        sound_state: debounced "quiet"/"active" from SoundDebouncer.
        temp_c: None if the sensor didn't read this poll.
        at_hour: overrides the clock, for simulate_day.py.
        poll_minutes: duration this poll represents, drives the
            empty-room timeout.
        """
        nudge = 0.0

        if bed_occupied:
            nudge += WEIGHTS["bed_occupied"]
        if desk_occupied:
            nudge += WEIGHTS["desk_occupied"]

        if light_raw <= LIGHT_BRIGHT_RAW_MAX:
            nudge += WEIGHTS["light_bright"]
        elif light_raw >= LIGHT_DARK_RAW_MIN:
            nudge += WEIGHTS["light_dark"]

        if sound_state == "quiet":
            nudge += WEIGHTS["sound_quiet"]

        if temp_c is not None:
            if temp_c < TEMP_STUDY_LOW_C or temp_c > TEMP_STUDY_HIGH_C:
                nudge += WEIGHTS["temp_outside_study_range"]

        hour = at_hour if at_hour is not None else datetime.datetime.now().hour
        if STUDY_HOURS_START <= hour < STUDY_HOURS_END:
            nudge += WEIGHTS["time_of_day_study_hours"]
        else:
            nudge += WEIGHTS["time_of_day_sleep_hours"]

        self.score = self.score * SCORE_DECAY + nudge
        clamp = max(abs(SCORE_UPPER_THRESHOLD), abs(SCORE_LOWER_THRESHOLD)) * 2
        self.score = max(-clamp, min(clamp, self.score))

        both_empty = not bed_occupied and not desk_occupied
        self._empty_minutes = self._empty_minutes + poll_minutes if both_empty else 0.0

        if both_empty:
            # No one is in the room, so ambient evidence means nothing.
            # Keep the score at 0 and let the mode hold until the
            # empty-room timeout below switches it to "unoccupied".
            self.score = 0.0
        elif self.mode == "unoccupied":
            # Someone is in the room: leave "unoccupied" straight away.
            # The direction of this poll's evidence picks the mode.
            self.mode = "sleep" if nudge < 0 else "study"

        if self._empty_minutes >= EMPTY_ROOM_MINUTES:
            self.mode = "unoccupied"
            self.score = 0.0
        elif self.score >= SCORE_UPPER_THRESHOLD:
            self.mode = "study"
        elif self.score <= SCORE_LOWER_THRESHOLD:
            self.mode = "sleep"

        # "relax" is a rule-based override on top of the score, not part
        # of it, so the study/sleep hysteresis above is left untouched
        # and resumes as soon as the relax condition clears. It never
        # overrides "unoccupied".
        if self.mode != "unoccupied":
            if bed_occupied and light_raw <= LIGHT_BRIGHT_RAW_MAX:
                return "relax"      # awake in bed, light on
            if desk_occupied and sound_state == "active":
                return "relax"      # at the desk, loud (above typing level)

        return self.mode