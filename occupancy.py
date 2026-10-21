"""
occupancy.py
------------
Turns a pad's raw reading into an occupied/not flag, debounced across
several polls so one stray reading can't flip it on its own.
"""

from config import PAD_OCCUPIED_THRESHOLD, PAD_DEBOUNCE_POLLS
 
 
class PadDebouncer:
    """
    Keeps its own running state. Call .update(raw) every poll - the
    occupied flag only flips once the raw reading has agreed with
    itself (above or below threshold) for PAD_DEBOUNCE_POLLS polls
    running.
    """
 
    def __init__(self):
        self.occupied = False
        self._candidate = None
        self._count = 0
 
    def update(self, raw: float) -> bool:
        instantaneous = raw >= PAD_OCCUPIED_THRESHOLD
 
        if instantaneous == self._candidate:
            self._count += 1
        else:
            self._candidate = instantaneous
            self._count = 1
 
        if self._candidate != self.occupied and self._count >= PAD_DEBOUNCE_POLLS:
            self.occupied = self._candidate
 
        return self.occupied
 