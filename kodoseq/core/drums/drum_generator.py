"""KODOSEQ Drum Generator

Dedicated rhythmic percussion pattern engine.

Channels: kick, snare, hihat, percussion
Each channel has independent:
- Pattern length (polyrhythm support)
- Per-step probability
- Velocity variation
- Microtiming offset (fraction of step)
- Accent probability

Supports:
- Probability-based fills
- Pattern mutation
- Polyrhythm across channels
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, NamedTuple, Optional

from kodoseq.state import DrumChannelState, DrumState


class DrumTrigger(NamedTuple):
    channel_name: str
    midi_note: int
    midi_channel: int
    velocity: int
    microtiming: float  # fractional step offset (-0.5 to 0.5)


class DrumChannel:
    """Single drum instrument channel with its own pattern."""

    def __init__(self, name: str, state: DrumChannelState, rng: random.Random) -> None:
        self.name = name
        self._state = state
        self._rng = rng
        self._position: int = 0
        self._fill_active: bool = False

    @property
    def state(self) -> DrumChannelState:
        return self._state

    def reset(self) -> None:
        self._position = 0
        self._fill_active = False

    def advance(self) -> Optional[DrumTrigger]:
        """Advance one step. Returns DrumTrigger if step fires."""
        length = self._state.pattern_length
        if length == 0:
            return None

        idx = self._position % length
        step_prob = self._state.steps[idx] if idx < len(self._state.steps) else 0.0
        self._position = (self._position + 1) % length

        # Fill mode: temporarily increase density
        effective_prob = min(1.0, step_prob * (1.5 if self._fill_active else 1.0))

        if self._rng.random() > effective_prob:
            return None

        # Velocity: base + variation, accent handling
        base_vel = self._state.velocity
        variation = self._state.velocity_variation
        velocity = base_vel
        if variation > 0:
            delta = self._rng.randint(-variation, variation)
            velocity = max(1, min(127, base_vel + delta))

        if self._rng.random() < self._state.accent_probability:
            velocity = min(127, self._state.accent_velocity)

        # Microtiming: random offset within configured range
        mt = self._state.microtiming_offset
        microtiming = 0.0
        if mt != 0.0:
            microtiming = self._rng.uniform(-abs(mt), abs(mt))

        return DrumTrigger(
            channel_name=self.name,
            midi_note=self._state.midi_note,
            midi_channel=self._state.midi_channel,
            velocity=velocity,
            microtiming=microtiming,
        )

    def set_step(self, idx: int, probability: float) -> None:
        """Set step trigger probability (0.0 = never, 1.0 = always)."""
        self._ensure_steps()
        if not 0 <= idx < self._state.pattern_length:
            raise IndexError(f"Step index {idx} out of range [0, {self._state.pattern_length - 1}]")
        self._state.steps[idx] = max(0.0, min(1.0, probability))

    def set_length(self, length: int) -> None:
        if length < 1:
            raise ValueError("Pattern length must be >= 1")
        current = len(self._state.steps)
        if length > current:
            self._state.steps.extend([0.0] * (length - current))
        else:
            self._state.steps = self._state.steps[:length]
        self._state.pattern_length = length
        self._position = self._position % length

    def activate_fill(self) -> None:
        self._fill_active = True

    def deactivate_fill(self) -> None:
        self._fill_active = False

    def _ensure_steps(self) -> None:
        needed = self._state.pattern_length
        if len(self._state.steps) < needed:
            self._state.steps.extend([0.0] * (needed - len(self._state.steps)))


class DrumGenerator:
    """Generates polyrhythmic drum triggers across all channels.

    Channels run at independent pattern lengths for polyrhythm.
    """

    CHANNEL_NAMES = ["kick", "snare", "hihat", "percussion"]

    def __init__(self, state: DrumState, seed: int = 0) -> None:
        self._state = state
        self._rng = random.Random(seed)
        self._channels: Dict[str, DrumChannel] = {
            "kick":       DrumChannel("kick",       state.kick,       self._rng),
            "snare":      DrumChannel("snare",      state.snare,      self._rng),
            "hihat":      DrumChannel("hihat",      state.hihat,      self._rng),
            "percussion": DrumChannel("percussion", state.percussion, self._rng),
        }
        self._trigger_callbacks: List = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_trigger(self, cb) -> None:
        self._trigger_callbacks.append(cb)

    def on_step(self, global_step: int, step_in_bar: int) -> None:
        """Called by the clock on each step event."""
        triggers = []
        for channel in self._channels.values():
            t = channel.advance()
            if t is not None:
                triggers.append(t)

        for trigger in triggers:
            self._dispatch(trigger)

    def reset(self) -> None:
        for ch in self._channels.values():
            ch.reset()

    def reseed(self, seed: int) -> None:
        self._rng.seed(seed)

    def channel(self, name: str) -> DrumChannel:
        if name not in self._channels:
            raise KeyError(f"No drum channel '{name}'. Available: {self.CHANNEL_NAMES}")
        return self._channels[name]

    def activate_fill(self) -> None:
        for ch in self._channels.values():
            ch.activate_fill()

    def deactivate_fill(self) -> None:
        for ch in self._channels.values():
            ch.deactivate_fill()

    def mutate(self, mutation_rate: float) -> None:
        """Randomly adjust step probabilities within all channels.

        mutation_rate: 0.0 = no change, 1.0 = aggressive mutation.
        Preserves structural rhythm while adding variation.
        """
        for ch in self._channels.values():
            state = ch.state
            for i in range(state.pattern_length):
                if self._rng.random() < mutation_rate * 0.3:
                    current = state.steps[i] if i < len(state.steps) else 0.0
                    delta = self._rng.uniform(-0.3, 0.3)
                    state.steps[i] = max(0.0, min(1.0, current + delta))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dispatch(self, trigger: DrumTrigger) -> None:
        for cb in self._trigger_callbacks:
            try:
                cb(trigger)
            except Exception:
                pass
