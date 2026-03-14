"""KODOSEQ Randomization Engine

Handles all generative mutation and controlled chaos.
Randomization is always constrained by current parameters,
scale, pattern length, and density limits.

Operations:
- Randomize pattern step probabilities
- Randomize melody parameters within safe bounds
- Reseed the RNG for reproducible sequences
- Pattern morphing: gradual transition toward a target state
- Controlled chaos: brief spike in randomness
"""

from __future__ import annotations

import random
from typing import Optional

from kodoseq.state import (
    RandomState,
    PatternState,
    MelodyState,
    DrumState,
    HarmonyState,
)
from kodoseq.core.harmony.harmony_engine import SCALES


class RandomizationEngine:
    """Constrained generative mutation engine.

    All operations respect musical structure:
    - Notes are never placed outside the active scale
    - Pattern density stays within configured bounds
    - Velocity always remains in MIDI range [1, 127]
    """

    DENSITY_CLAMP = (0.05, 0.95)
    VELOCITY_MIN = 20
    VELOCITY_MAX = 120

    def __init__(self, state: RandomState, seed: Optional[int] = None) -> None:
        self._state = state
        effective_seed = seed if seed is not None else state.seed
        self._rng = random.Random(effective_seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> RandomState:
        return self._state

    def reseed(self, seed: int) -> None:
        self._state.seed = seed
        self._rng.seed(seed)

    def set_mutation_rate(self, rate: float) -> None:
        self._state.mutation_rate = max(0.0, min(1.0, rate))

    def set_chaos(self, chaos: float) -> None:
        self._state.chaos = max(0.0, min(1.0, chaos))

    # ------------------------------------------------------------------
    # Pattern randomization
    # ------------------------------------------------------------------

    def randomize_pattern(self, pattern: PatternState) -> None:
        """Randomize step probabilities in both pattern tracks."""
        chaos = self._state.chaos
        for track in [pattern.melody_track, pattern.bass_track]:
            for step in track.steps:
                if self._rng.random() < chaos:
                    step.probability = self._rng.uniform(0.0, 1.0)
                    step.velocity = self._rng.randint(
                        self.VELOCITY_MIN, self.VELOCITY_MAX
                    )

    def randomize_pattern_track_steps(
        self, pattern: PatternState, track_id: int
    ) -> None:
        """Randomize one track's step probability layout."""
        tracks = [pattern.melody_track, pattern.bass_track]
        if track_id >= len(tracks):
            return
        track = tracks[track_id]
        for step in track.steps:
            step.active = self._rng.random() < self._state.chaos
            step.probability = self._rng.uniform(0.3, 1.0) if step.active else 0.0

    # ------------------------------------------------------------------
    # Melody randomization
    # ------------------------------------------------------------------

    def randomize_melody(self, melody: MelodyState) -> None:
        """Randomize melody generator parameters within safe bounds."""
        chaos = self._state.chaos
        directions = ["ascending", "descending", "random", "pendulum"]

        if self._rng.random() < chaos:
            melody.density = self._rng.uniform(*self.DENSITY_CLAMP)

        if self._rng.random() < chaos * 0.5:
            melody.direction = self._rng.choice(directions)

        if self._rng.random() < chaos * 0.3:
            melody.repetition_bias = self._rng.uniform(0.0, 0.6)

    # ------------------------------------------------------------------
    # Drum randomization
    # ------------------------------------------------------------------

    def randomize_drums(self, drum: DrumState) -> None:
        """Randomize drum step probabilities while preserving groove."""
        chaos = self._state.chaos
        channels = [drum.kick, drum.snare, drum.hihat, drum.percussion]

        for ch in channels:
            for i in range(ch.pattern_length):
                if self._rng.random() < chaos * 0.4:
                    current = ch.steps[i] if i < len(ch.steps) else 0.0
                    # Bias toward existing hits to preserve groove
                    if current > 0.5:
                        ch.steps[i] = self._rng.uniform(0.4, 1.0)
                    else:
                        ch.steps[i] = self._rng.uniform(0.0, 0.4)

    # ------------------------------------------------------------------
    # Harmony randomization
    # ------------------------------------------------------------------

    def randomize_harmony(self, harmony: HarmonyState) -> None:
        """Randomize scale (root stays fixed by default)."""
        if self._rng.random() < self._state.chaos * 0.5:
            available = list(SCALES.keys())
            harmony.scale = self._rng.choice(available)

    # ------------------------------------------------------------------
    # Pattern morphing
    # ------------------------------------------------------------------

    def morph_pattern(
        self, pattern: PatternState, target: PatternState, amount: float
    ) -> None:
        """Gradually morph pattern toward target state.

        amount: 0.0 = no change, 1.0 = replace fully with target.
        """
        amount = max(0.0, min(1.0, amount))
        pairs = [
            (pattern.melody_track, target.melody_track),
            (pattern.bass_track,   target.bass_track),
        ]
        for src_track, tgt_track in pairs:
            for i, (src_step, tgt_step) in enumerate(
                zip(src_track.steps, tgt_track.steps)
            ):
                if self._rng.random() < amount:
                    src_step.active = tgt_step.active
                    src_step.probability = _lerp(
                        src_step.probability, tgt_step.probability, amount
                    )
                    src_step.velocity = int(
                        _lerp(src_step.velocity, tgt_step.velocity, amount)
                    )

    # ------------------------------------------------------------------
    # Controlled chaos burst
    # ------------------------------------------------------------------

    def chaos_burst(
        self,
        pattern: PatternState,
        melody: MelodyState,
        duration_steps: int = 4,
    ) -> None:
        """Apply a burst of high chaos for a number of steps.

        This temporarily randomizes pattern and melody parameters
        at a high rate. The caller is responsible for restoring
        state afterward using a saved snapshot.
        """
        saved_chaos = self._state.chaos
        self._state.chaos = min(1.0, saved_chaos + 0.5)
        self.randomize_pattern(pattern)
        self.randomize_melody(melody)
        self._state.chaos = saved_chaos


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
