"""KODOSEQ Pattern Engine

Core step sequencer. Manages pattern playback including:
- Variable pattern length
- Per-step probability gates
- Velocity variation
- Step skipping
- Polyrhythm (independent pattern lengths per track)

Pattern engine receives step events from the clock and fires triggers.
A trigger is emitted as a dict consumed by generators.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from kodoseq.state import PatternState, PatternTrackState, StepState

TriggerCallback = Callable[[int, int, int], None]  # (step_in_pattern, velocity, track_id)


@dataclass
class Trigger:
    step: int       # step index in pattern
    velocity: int   # 0–127
    track_id: int   # which track triggered


class PatternTrack:
    """Single polyrhythmic pattern track.

    Independently loops at its own pattern length.
    """

    def __init__(self, track_id: int, state: PatternTrackState, rng: random.Random) -> None:
        self.track_id = track_id
        self._state = state
        self._rng = rng
        self._position: int = 0

    @property
    def state(self) -> PatternTrackState:
        return self._state

    def reset(self) -> None:
        self._position = 0

    def advance(self) -> Optional[Trigger]:
        """Advance one step. Returns Trigger if step fires, else None."""
        length = self._state.length
        if length == 0:
            return None

        idx = self._position % length
        step = self._state.steps[idx] if idx < len(self._state.steps) else StepState()
        self._position = (self._position + 1) % length

        if step.skip or not step.active:
            return None

        if step.probability < 1.0 and self._rng.random() > step.probability:
            return None

        base_vel = step.velocity
        variation = step.velocity_variation
        if variation > 0:
            delta = self._rng.randint(-variation, variation)
            velocity = max(1, min(127, base_vel + delta))
        else:
            velocity = max(1, min(127, base_vel))

        return Trigger(step=idx, velocity=velocity, track_id=self.track_id)

    def set_step_probability(self, idx: int, probability: float) -> None:
        _validate_step_idx(idx, self._state)
        self._state.steps[idx].probability = max(0.0, min(1.0, probability))

    def set_step_active(self, idx: int, active: bool) -> None:
        _validate_step_idx(idx, self._state)
        self._state.steps[idx].active = active

    def set_step_velocity(self, idx: int, velocity: int, variation: int = 0) -> None:
        _validate_step_idx(idx, self._state)
        self._state.steps[idx].velocity = max(0, min(127, velocity))
        self._state.steps[idx].velocity_variation = max(0, min(64, variation))

    def set_length(self, length: int) -> None:
        self._state.resize(length)
        self._position = self._position % length if length > 0 else 0


class PatternEngine:
    """Manages multiple pattern tracks and dispatches triggers.

    Tracks can run at different pattern lengths (polyrhythm).
    Consumers register callbacks that fire when a step triggers.
    """

    MELODY_TRACK = 0
    BASS_TRACK = 1

    def __init__(self, state: PatternState, seed: int = 0) -> None:
        self._state = state
        self._rng = random.Random(seed)
        self._tracks: Dict[int, PatternTrack] = {}
        self._trigger_callbacks: List[TriggerCallback] = []

        self._tracks[self.MELODY_TRACK] = PatternTrack(
            self.MELODY_TRACK, state.melody_track, self._rng
        )
        self._tracks[self.BASS_TRACK] = PatternTrack(
            self.BASS_TRACK, state.bass_track, self._rng
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_trigger(self, cb: TriggerCallback) -> None:
        self._trigger_callbacks.append(cb)

    def on_step(self, global_step: int, step_in_bar: int) -> None:
        """Called by the clock on each step event."""
        for track in self._tracks.values():
            trigger = track.advance()
            if trigger is not None:
                self._dispatch(trigger)

    def reset(self) -> None:
        for track in self._tracks.values():
            track.reset()

    def reseed(self, seed: int) -> None:
        self._rng.seed(seed)

    def track(self, track_id: int) -> PatternTrack:
        if track_id not in self._tracks:
            raise KeyError(f"No track with id {track_id}")
        return self._tracks[track_id]

    def melody_track(self) -> PatternTrack:
        return self._tracks[self.MELODY_TRACK]

    def bass_track(self) -> PatternTrack:
        return self._tracks[self.BASS_TRACK]

    def add_track(self, track_id: int, state: PatternTrackState) -> PatternTrack:
        track = PatternTrack(track_id, state, self._rng)
        self._tracks[track_id] = track
        return track

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dispatch(self, trigger: Trigger) -> None:
        for cb in self._trigger_callbacks:
            try:
                cb(trigger.step, trigger.velocity, trigger.track_id)
            except Exception:
                pass


def _validate_step_idx(idx: int, track: PatternTrackState) -> None:
    if not 0 <= idx < track.length:
        raise IndexError(f"Step index {idx} out of range [0, {track.length - 1}]")
