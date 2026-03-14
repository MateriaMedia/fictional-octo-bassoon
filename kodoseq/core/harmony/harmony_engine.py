"""KODOSEQ Harmony Engine

Generates harmonically valid MIDI note sets based on root, scale, and mode.
Pattern generators consume this to constrain note selection.

Scale intervals are semitone offsets from root within one octave.
"""

from __future__ import annotations

from typing import List, Dict, Tuple

from kodoseq.state import HarmonyState

# Semitone intervals from root for each scale
SCALES: Dict[str, List[int]] = {
    "major":      [0, 2, 4, 5, 7, 9, 11],
    "minor":      [0, 2, 3, 5, 7, 8, 10],
    "dorian":     [0, 2, 3, 5, 7, 9, 10],
    "phrygian":   [0, 1, 3, 5, 7, 8, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "lydian":     [0, 2, 4, 6, 7, 9, 11],
    "locrian":    [0, 1, 3, 5, 6, 8, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "chromatic":  list(range(12)),
}

# Chord intervals (degrees above root, in scale tones; index into scale)
# Values are scale degree indices (0-based): triad = 1st, 3rd, 5th
CHORD_DEGREE_INDICES: Dict[str, List[int]] = {
    "triad":    [0, 2, 4],
    "seventh":  [0, 2, 4, 6],
    "extended": [0, 2, 4, 6, 1, 3],   # 9th, 11th folded in
    "sus":      [0, 3, 4],             # sus4: 1, 4, 5
    "add":      [0, 2, 4, 1],         # add9: 1, 3, 5, 9
}

MIDI_MIN = 0
MIDI_MAX = 127


class HarmonyEngine:
    """Computes harmonically valid MIDI note sets.

    The engine maintains an internal cache of allowed notes that is
    invalidated whenever root, scale, or chord_mode changes.
    """

    def __init__(self, state: HarmonyState) -> None:
        self._state = state
        self._cache: List[int] = []
        self._chord_cache: List[int] = []
        self._rebuild()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> HarmonyState:
        return self._state

    def set_root(self, root: int) -> None:
        if not MIDI_MIN <= root <= MIDI_MAX:
            raise ValueError(f"Root must be in [0, 127], got {root}")
        self._state.root = root
        self._rebuild()

    def set_scale(self, scale: str) -> None:
        if scale not in SCALES:
            raise ValueError(f"Unknown scale '{scale}'. Available: {list(SCALES)}")
        self._state.scale = scale
        self._rebuild()

    def set_chord_mode(self, mode: str) -> None:
        if mode not in CHORD_DEGREE_INDICES:
            raise ValueError(f"Unknown chord_mode '{mode}'. Available: {list(CHORD_DEGREE_INDICES)}")
        self._state.chord_mode = mode
        self._rebuild()

    def set_octave_range(self, octave_range: int) -> None:
        if octave_range < 1:
            raise ValueError("octave_range must be >= 1")
        self._state.octave_range = octave_range
        self._rebuild()

    def allowed_notes(self) -> List[int]:
        """All MIDI notes in scale across the configured octave range."""
        return list(self._cache)

    def chord_notes(self) -> List[int]:
        """Notes belonging to the current chord voicing (root octave only)."""
        return list(self._chord_cache)

    def nearest_in_scale(self, note: int) -> int:
        """Round a MIDI note to the nearest note in the current scale."""
        if not self._cache:
            return note
        return min(self._cache, key=lambda n: abs(n - note))

    def notes_in_range(self, low: int, high: int) -> List[int]:
        """Allowed notes within [low, high] MIDI range."""
        return [n for n in self._cache if low <= n <= high]

    def available_scales(self) -> List[str]:
        return list(SCALES.keys())

    def available_chord_modes(self) -> List[str]:
        return list(CHORD_DEGREE_INDICES.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        root = self._state.root
        scale_name = self._state.scale
        chord_mode = self._state.chord_mode
        octave_range = self._state.octave_range

        intervals = SCALES.get(scale_name, SCALES["major"])

        # Determine the base MIDI octave (keep root in its octave)
        root_class = root % 12
        base_octave_root = root - root_class  # e.g. C4=60 → 60

        notes = set()
        for octave_offset in range(-(octave_range // 2 + 1), octave_range + 1):
            for interval in intervals:
                note = base_octave_root + octave_offset * 12 + interval
                if MIDI_MIN <= note <= MIDI_MAX:
                    notes.add(note)

        self._cache = sorted(notes)

        # Chord notes: apply degree indices into scale within root octave
        chord_indices = CHORD_DEGREE_INDICES.get(chord_mode, CHORD_DEGREE_INDICES["triad"])
        chord_notes = set()
        for idx in chord_indices:
            scaled_idx = idx % len(intervals)
            octave_bump = idx // len(intervals)
            semitone = intervals[scaled_idx] + octave_bump * 12
            note = root + semitone
            if MIDI_MIN <= note <= MIDI_MAX:
                chord_notes.add(note)
        self._chord_cache = sorted(chord_notes)
