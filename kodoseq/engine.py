"""KODOSEQ Main Engine

Coordinates all subsystems into a unified instrument engine:
- Clock → drives Pattern and Drum engines via step events
- Pattern → feeds Melody Generator with triggers
- Harmony → constrains Melody Generator note selection
- Drum → independent rhythmic pattern generation
- MIDI → dispatches note_on/off to hardware
- Randomizer → mutates patterns on demand or automatically
- Presets → state serialization / recall

All subsystems communicate via the central EngineState.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from kodoseq.state import EngineState, PatternTrackState, StepState
from kodoseq.core.clock.clock_engine import ClockEngine
from kodoseq.core.pattern.pattern_engine import PatternEngine
from kodoseq.core.harmony.harmony_engine import HarmonyEngine
from kodoseq.core.generators.melody_generator import MelodyGenerator
from kodoseq.core.drums.drum_generator import DrumGenerator
from kodoseq.core.randomizer.randomization_engine import RandomizationEngine
from kodoseq.core.midi.midi_engine import MidiEngine, MidiBackend, MockMidiBackend
from kodoseq.core.presets.preset_system import PresetManager


class KodoSeq:
    """Top-level KODOSEQ engine.

    Usage:
        engine = KodoSeq()
        engine.start()
        # ... adjust parameters
        engine.stop()
    """

    def __init__(
        self,
        state: Optional[EngineState] = None,
        midi_backend: Optional[MidiBackend] = None,
        preset_dir: str = "presets",
    ) -> None:
        self._state = state or EngineState()
        self._auto_mutate_bars = 0

        # Instantiate all subsystems
        self._clock = ClockEngine(self._state.clock)
        self._harmony = HarmonyEngine(self._state.harmony)
        self._pattern = PatternEngine(self._state.pattern, seed=self._state.random.seed)
        self._melody = MelodyGenerator(self._state.melody, self._harmony)
        self._drums = DrumGenerator(self._state.drum, seed=self._state.random.seed)
        self._randomizer = RandomizationEngine(self._state.random)
        self._midi = MidiEngine(
            self._state.midi_routing,
            backend=midi_backend or MockMidiBackend(),
        )
        self._presets = PresetManager(preset_dir)

        # Active note scheduling: track note-off times
        self._active_melody_note: Optional[int] = None
        self._active_melody_channel: int = 0
        self._note_off_thread: Optional[threading.Thread] = None
        self._note_off_lock = threading.Lock()

        # Wire events
        self._clock.on_step(self._on_step)
        self._clock.on_bar(self._on_bar)
        self._pattern.on_trigger(self._on_melody_trigger)
        self._drums.on_trigger(self._on_drum_trigger)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._midi.open()
        self._pattern.reset()
        self._drums.reset()
        self._melody.reset()
        self._auto_mutate_bars = 0
        self._clock.start()

    def stop(self) -> None:
        self._clock.stop()
        self._midi.all_notes_off()
        self._active_melody_note = None

    def panic(self) -> None:
        """Immediate silence on all channels."""
        self._clock.stop()
        self._midi.panic()
        self._active_melody_note = None

    def is_running(self) -> bool:
        return self._clock.is_running()

    # ------------------------------------------------------------------
    # Parameter control
    # ------------------------------------------------------------------

    def set_bpm(self, bpm: float) -> None:
        self._clock.set_bpm(bpm)

    def set_swing(self, swing: float) -> None:
        self._clock.set_swing(swing)

    def set_root(self, root: int) -> None:
        self._harmony.set_root(root)

    def set_scale(self, scale: str) -> None:
        self._harmony.set_scale(scale)

    def set_chord_mode(self, mode: str) -> None:
        self._harmony.set_chord_mode(mode)

    def set_density(self, density: float) -> None:
        self._melody.set_density(density)

    def set_direction(self, direction: str) -> None:
        self._melody.set_direction(direction)

    def set_melody_range(self, low: int, high: int) -> None:
        self._melody.set_range(low, high)

    # ------------------------------------------------------------------
    # Randomization
    # ------------------------------------------------------------------

    def randomize(self) -> None:
        """One-shot: apply controlled randomization to patterns and melody."""
        self._randomizer.randomize_pattern(self._state.pattern)
        self._randomizer.randomize_melody(self._state.melody)
        self._randomizer.randomize_drums(self._state.drum)

    def mutate(self) -> None:
        """Apply a single mutation step at the current mutation rate."""
        rate = self._state.random.mutation_rate
        self._randomizer.randomize_pattern(self._state.pattern)
        self._drums.mutate(rate)

    def enable_auto_mutate(self, interval_bars: int = 4) -> None:
        self._state.random.auto_mutate = True
        self._state.random.mutate_interval_bars = max(1, interval_bars)

    def disable_auto_mutate(self) -> None:
        self._state.random.auto_mutate = False

    # ------------------------------------------------------------------
    # Drums
    # ------------------------------------------------------------------

    def activate_fill(self) -> None:
        self._drums.activate_fill()

    def deactivate_fill(self) -> None:
        self._drums.deactivate_fill()

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    def save_preset(self, name: str, overwrite: bool = False) -> None:
        self._presets.save(name, self._state, overwrite=overwrite)

    def load_preset(self, name: str) -> None:
        was_running = self.is_running()
        if was_running:
            self.stop()

        new_state = self._presets.load(name)
        self._apply_state(new_state)

        if was_running:
            self.start()

    def list_presets(self):
        return self._presets.list_presets()

    def reset_to_defaults(self) -> None:
        was_running = self.is_running()
        if was_running:
            self.stop()
        self._apply_state(EngineState())
        if was_running:
            self.start()

    # ------------------------------------------------------------------
    # State access
    # ------------------------------------------------------------------

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def clock(self) -> ClockEngine:
        return self._clock

    @property
    def harmony(self) -> HarmonyEngine:
        return self._harmony

    @property
    def pattern(self) -> PatternEngine:
        return self._pattern

    @property
    def melody(self) -> MelodyGenerator:
        return self._melody

    @property
    def drums(self) -> DrumGenerator:
        return self._drums

    @property
    def randomizer(self) -> RandomizationEngine:
        return self._randomizer

    @property
    def midi(self) -> MidiEngine:
        return self._midi

    # ------------------------------------------------------------------
    # Internal event handlers
    # ------------------------------------------------------------------

    def _on_step(self, global_step: int, step_in_bar: int) -> None:
        self._pattern.on_step(global_step, step_in_bar)
        self._drums.on_step(global_step, step_in_bar)

    def _on_bar(self, bar: int) -> None:
        if not self._state.random.auto_mutate:
            return
        interval = self._state.random.mutate_interval_bars
        self._auto_mutate_bars += 1
        if self._auto_mutate_bars >= interval:
            self._auto_mutate_bars = 0
            self.mutate()

    def _on_melody_trigger(self, step: int, velocity: int, track_id: int) -> None:
        result = self._melody.generate(step, velocity)
        if result is None:
            return
        note, vel, duration_fraction = result
        channel = self._midi.melody_channel
        step_secs = self._clock.seconds_per_step()
        note_dur = step_secs * duration_fraction

        # Release previous note if still active
        if self._active_melody_note is not None:
            self._midi.note_off(channel, self._active_melody_note)

        self._midi.note_on(channel, note, vel)
        self._active_melody_note = note
        self._active_melody_channel = channel

        # Schedule note_off in background thread
        threading.Thread(
            target=self._schedule_note_off,
            args=(channel, note, note_dur),
            daemon=True,
        ).start()

    def _schedule_note_off(self, channel: int, note: int, delay: float) -> None:
        time.sleep(max(0.0, delay))
        with self._note_off_lock:
            if self._active_melody_note == note:
                self._midi.note_off(channel, note)
                self._active_melody_note = None

    def _on_drum_trigger(self, trigger) -> None:
        self._midi.note_on(trigger.midi_channel, trigger.midi_note, trigger.velocity)
        # Drum notes are short; schedule note_off after 50ms
        threading.Thread(
            target=self._schedule_note_off,
            args=(trigger.midi_channel, trigger.midi_note, 0.05),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Internal: state application
    # ------------------------------------------------------------------

    def _apply_state(self, new_state: EngineState) -> None:
        self._state = new_state
        self._clock = ClockEngine(new_state.clock)
        self._harmony = HarmonyEngine(new_state.harmony)
        self._pattern = PatternEngine(new_state.pattern, seed=new_state.random.seed)
        self._melody = MelodyGenerator(new_state.melody, self._harmony)
        self._drums = DrumGenerator(new_state.drum, seed=new_state.random.seed)
        self._randomizer = RandomizationEngine(new_state.random)
        self._midi = MidiEngine(new_state.midi_routing, backend=self._midi.backend)

        self._clock.on_step(self._on_step)
        self._clock.on_bar(self._on_bar)
        self._pattern.on_trigger(self._on_melody_trigger)
        self._drums.on_trigger(self._on_drum_trigger)
        self._auto_mutate_bars = 0
