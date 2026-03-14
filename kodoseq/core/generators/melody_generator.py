"""KODOSEQ Melody Generator

Generates melodic sequences using harmonic constraints from the HarmonyEngine.

Features:
- Density-controlled step probability
- Note direction: ascending, descending, random, pendulum
- Repetition bias for motif-like behavior
- Controlled mutation for variation over time
- Note duration as fraction of step
"""

from __future__ import annotations

import random
from typing import List, Optional

from kodoseq.state import MelodyState
from kodoseq.core.harmony.harmony_engine import HarmonyEngine


class MelodyGenerator:
    """Generates melodic MIDI note values for triggered steps.

    Consumes triggers from PatternEngine and produces (note, velocity, duration)
    tuples using the HarmonyEngine's allowed note set.

    Direction modes:
    - random:     note selected randomly from allowed set in range
    - ascending:  step through notes upward, wrap at top
    - descending: step through notes downward, wrap at bottom
    - pendulum:   bounce between low and high
    """

    def __init__(
        self,
        state: MelodyState,
        harmony: HarmonyEngine,
        rng: Optional[random.Random] = None,
    ) -> None:
        self._state = state
        self._harmony = harmony
        self._rng = rng or random.Random()
        self._last_note: Optional[int] = None
        self._direction_idx: int = 0
        self._direction_sign: int = 1   # +1 or -1 for pendulum

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> MelodyState:
        return self._state

    def set_density(self, density: float) -> None:
        self._state.density = max(0.0, min(1.0, density))

    def set_range(self, low: int, high: int) -> None:
        if low >= high:
            raise ValueError("note_low must be < note_high")
        self._state.note_low = max(0, low)
        self._state.note_high = min(127, high)

    def set_direction(self, direction: str) -> None:
        valid = {"random", "ascending", "descending", "pendulum"}
        if direction not in valid:
            raise ValueError(f"Direction must be one of {valid}")
        self._state.direction = direction
        self._direction_idx = 0

    def set_repetition_bias(self, bias: float) -> None:
        self._state.repetition_bias = max(0.0, min(1.0, bias))

    def reset(self) -> None:
        self._last_note = None
        self._direction_idx = 0
        self._direction_sign = 1

    def generate(self, step: int, velocity: int) -> Optional[tuple]:
        """Generate (note, velocity, duration) for a triggered step.

        Returns None if density gate suppresses the step.
        """
        if self._rng.random() > self._state.density:
            return None

        allowed = self._harmony.notes_in_range(
            self._state.note_low, self._state.note_high
        )
        if not allowed:
            return None

        note = self._select_note(allowed)
        if note is None:
            return None

        self._last_note = note
        return (note, velocity, self._state.note_duration)

    def generate_motif(self, length: int) -> List[Optional[int]]:
        """Generate a melodic motif of the given length.

        Returns a list of MIDI notes (or None for rests).
        """
        allowed = self._harmony.notes_in_range(
            self._state.note_low, self._state.note_high
        )
        motif: List[Optional[int]] = []
        for _ in range(length):
            if self._rng.random() > self._state.density:
                motif.append(None)
            else:
                note = self._select_note(allowed)
                motif.append(note)
                if note is not None:
                    self._last_note = note
        return motif

    def mutate_note(self, note: int, mutation_rate: float) -> int:
        """Apply controlled mutation to a note — stays in scale.

        mutation_rate: 0.0 = no change, 1.0 = random walk within range.
        """
        if self._rng.random() > mutation_rate:
            return note

        allowed = self._harmony.notes_in_range(
            self._state.note_low, self._state.note_high
        )
        if not allowed:
            return note

        if len(allowed) == 1:
            return allowed[0]

        try:
            idx = allowed.index(note)
        except ValueError:
            return self._harmony.nearest_in_scale(note)

        step_range = max(1, int(mutation_rate * 3))
        delta = self._rng.randint(-step_range, step_range)
        new_idx = max(0, min(len(allowed) - 1, idx + delta))
        return allowed[new_idx]

    # ------------------------------------------------------------------
    # Internal note selection
    # ------------------------------------------------------------------

    def _select_note(self, allowed: List[int]) -> Optional[int]:
        if not allowed:
            return None

        # Repetition bias: chance to repeat last note
        if (
            self._last_note is not None
            and self._last_note in allowed
            and self._rng.random() < self._state.repetition_bias
        ):
            return self._last_note

        direction = self._state.direction

        if direction == "random":
            return self._rng.choice(allowed)

        elif direction == "ascending":
            self._direction_idx = self._direction_idx % len(allowed)
            note = allowed[self._direction_idx]
            self._direction_idx += 1
            return note

        elif direction == "descending":
            self._direction_idx = self._direction_idx % len(allowed)
            note = allowed[-(self._direction_idx + 1)]
            self._direction_idx += 1
            return note

        elif direction == "pendulum":
            self._direction_idx = max(0, min(len(allowed) - 1, self._direction_idx))
            note = allowed[self._direction_idx]
            # Reverse direction at boundaries
            if self._direction_idx >= len(allowed) - 1:
                self._direction_sign = -1
            elif self._direction_idx <= 0:
                self._direction_sign = 1
            self._direction_idx += self._direction_sign
            return note

        return self._rng.choice(allowed)
