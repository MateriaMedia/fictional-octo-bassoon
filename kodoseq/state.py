"""
KODOSEQ — Central Engine State Model

Defines all state dataclasses used across the engine.
Preset serialization operates on this structure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------

@dataclass
class ClockState:
    bpm: float = 120.0
    swing: float = 0.0          # 0.0–0.5 (fractional delay on odd steps)
    step_resolution: int = 16   # steps per bar (16 = 1/16th notes)
    clock_division: int = 1     # subdivide each step (1 = no subdivision)
    loop_bars: int = 4
    running: bool = False
    tick: int = 0               # absolute tick counter
    step: int = 0               # absolute step counter
    bar: int = 0                # absolute bar counter


# ---------------------------------------------------------------------------
# Pattern
# ---------------------------------------------------------------------------

@dataclass
class StepState:
    active: bool = True
    probability: float = 1.0    # 0.0–1.0
    velocity: int = 100         # 0–127
    velocity_variation: int = 0 # ±variance
    skip: bool = False


@dataclass
class PatternTrackState:
    length: int = 16
    steps: List[StepState] = field(default_factory=lambda: [StepState() for _ in range(16)])

    def resize(self, length: int) -> None:
        if length < 1:
            raise ValueError("Pattern length must be >= 1")
        current = len(self.steps)
        if length > current:
            self.steps.extend(StepState() for _ in range(length - current))
        else:
            self.steps = self.steps[:length]
        self.length = length


@dataclass
class PatternState:
    melody_track: PatternTrackState = field(default_factory=PatternTrackState)
    bass_track: PatternTrackState = field(default_factory=PatternTrackState)


# ---------------------------------------------------------------------------
# Harmony
# ---------------------------------------------------------------------------

@dataclass
class HarmonyState:
    root: int = 60              # MIDI note number, C4
    scale: str = "major"        # scale name key (see harmony engine)
    octave: int = 4
    octave_range: int = 2       # number of octaves for note selection
    chord_mode: str = "triad"   # triad | seventh | extended | sus | add


# ---------------------------------------------------------------------------
# Melody Generator
# ---------------------------------------------------------------------------

@dataclass
class MelodyState:
    density: float = 0.5        # 0.0–1.0 probability of a step triggering
    note_low: int = 48          # MIDI note low bound
    note_high: int = 84         # MIDI note high bound
    direction: str = "random"   # ascending | descending | random | pendulum
    repetition_bias: float = 0.3  # 0.0–1.0: tendency to repeat the last note
    note_duration: float = 0.5  # fraction of step duration for note-on


# ---------------------------------------------------------------------------
# Drums
# ---------------------------------------------------------------------------

@dataclass
class DrumChannelState:
    midi_note: int = 36
    midi_channel: int = 9       # GM drums on channel 10 (0-indexed: 9)
    pattern_length: int = 16
    steps: List[float] = field(default_factory=lambda: [0.0] * 16)  # per-step probability
    velocity: int = 100
    velocity_variation: int = 20
    microtiming_offset: float = 0.0   # ±fraction of a step (-0.5 to 0.5)
    accent_probability: float = 0.15  # probability of an accent step
    accent_velocity: int = 127


@dataclass
class DrumState:
    kick: DrumChannelState = field(default_factory=lambda: DrumChannelState(
        midi_note=36,
        steps=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ))
    snare: DrumChannelState = field(default_factory=lambda: DrumChannelState(
        midi_note=38,
        steps=[0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
    ))
    hihat: DrumChannelState = field(default_factory=lambda: DrumChannelState(
        midi_note=42,
        steps=[1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0,
               1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
        velocity=80,
        velocity_variation=15,
    ))
    percussion: DrumChannelState = field(default_factory=lambda: DrumChannelState(
        midi_note=46,
        steps=[0.0] * 16,
        velocity=90,
    ))


# ---------------------------------------------------------------------------
# Randomization
# ---------------------------------------------------------------------------

@dataclass
class RandomState:
    seed: int = 0
    mutation_rate: float = 0.1  # 0.0–1.0: how aggressively patterns mutate
    chaos: float = 0.2          # 0.0–1.0: global randomness level
    auto_mutate: bool = False   # continuously mutate patterns during playback
    mutate_interval_bars: int = 4  # bars between automatic mutations


# ---------------------------------------------------------------------------
# MIDI Routing
# ---------------------------------------------------------------------------

@dataclass
class MidiRoutingState:
    melody_channel: int = 0     # 0-indexed
    bass_channel: int = 1
    drum_channels_enabled: bool = True
    output_port: str = ""       # empty = use first available port


# ---------------------------------------------------------------------------
# Top-level Engine State
# ---------------------------------------------------------------------------

@dataclass
class EngineState:
    clock: ClockState = field(default_factory=ClockState)
    pattern: PatternState = field(default_factory=PatternState)
    harmony: HarmonyState = field(default_factory=HarmonyState)
    melody: MelodyState = field(default_factory=MelodyState)
    drum: DrumState = field(default_factory=DrumState)
    random: RandomState = field(default_factory=RandomState)
    midi_routing: MidiRoutingState = field(default_factory=MidiRoutingState)
    preset_name: str = "Default"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EngineState":
        return _engine_state_from_dict(data)


# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------

def _engine_state_from_dict(data: dict) -> EngineState:
    state = EngineState()

    if "clock" in data:
        c = data["clock"]
        state.clock = ClockState(**{k: v for k, v in c.items() if k in ClockState.__dataclass_fields__})

    if "pattern" in data:
        p = data["pattern"]
        state.pattern = PatternState(
            melody_track=_pattern_track_from_dict(p.get("melody_track", {})),
            bass_track=_pattern_track_from_dict(p.get("bass_track", {})),
        )

    if "harmony" in data:
        h = data["harmony"]
        state.harmony = HarmonyState(**{k: v for k, v in h.items() if k in HarmonyState.__dataclass_fields__})

    if "melody" in data:
        m = data["melody"]
        state.melody = MelodyState(**{k: v for k, v in m.items() if k in MelodyState.__dataclass_fields__})

    if "drum" in data:
        d = data["drum"]
        state.drum = DrumState(
            kick=_drum_channel_from_dict(d.get("kick", {})),
            snare=_drum_channel_from_dict(d.get("snare", {})),
            hihat=_drum_channel_from_dict(d.get("hihat", {})),
            percussion=_drum_channel_from_dict(d.get("percussion", {})),
        )

    if "random" in data:
        r = data["random"]
        state.random = RandomState(**{k: v for k, v in r.items() if k in RandomState.__dataclass_fields__})

    if "midi_routing" in data:
        mr = data["midi_routing"]
        state.midi_routing = MidiRoutingState(**{k: v for k, v in mr.items() if k in MidiRoutingState.__dataclass_fields__})

    state.preset_name = data.get("preset_name", state.preset_name)
    state.created_at = data.get("created_at", state.created_at)

    return state


def _pattern_track_from_dict(data: dict) -> PatternTrackState:
    length = data.get("length", 16)
    raw_steps = data.get("steps", [])
    steps = [
        StepState(**{k: v for k, v in s.items() if k in StepState.__dataclass_fields__})
        for s in raw_steps
    ] if raw_steps else [StepState() for _ in range(length)]
    return PatternTrackState(length=length, steps=steps)


def _drum_channel_from_dict(data: dict) -> DrumChannelState:
    if not data:
        return DrumChannelState()
    fields = DrumChannelState.__dataclass_fields__
    return DrumChannelState(**{k: v for k, v in data.items() if k in fields})
