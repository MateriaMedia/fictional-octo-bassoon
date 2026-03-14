# KODOSEQ

**Generative MIDI Sequencer Engine**

KODOSEQ is a realtime generative MIDI sequencer designed as a creative instrument for live performance and studio use. It generates musical structures using algorithmic pattern generation, probabilistic triggers, harmonic rules, and controlled randomness.

---

## Architecture

```
kodoseq/
├── core/
│   ├── clock/          # BPM clock, swing, step/bar events
│   ├── pattern/        # Step sequencer, polyrhythm, probability gates
│   ├── harmony/        # Scale/mode engine, chord voicings
│   ├── generators/     # Melody generator (direction, density, motifs)
│   ├── drums/          # Drum pattern engine, fills, polyrhythm
│   ├── randomizer/     # Constrained mutation, pattern morphing
│   ├── midi/           # MIDI output (rtmidi + mock backend)
│   └── presets/        # JSON preset save/load/overwrite
├── state.py            # Central EngineState dataclasses
├── engine.py           # KodoSeq main coordinator
└── tests/              # Pytest test suite
```

## Design Principles

- **Realtime first** — no blocking in critical loops, clock runs in a dedicated thread
- **Musical control over randomness** — all randomization respects scale, harmony, and density limits
- **Modular architecture** — each subsystem is independently testable with clean interfaces
- **No stuck notes** — MIDI engine tracks all active notes and can panic/release at any time
- **Portable presets** — complete state serialized as JSON

## Modules

### Clock Engine
- BPM control, swing, step resolution (steps/bar), loop length
- Emits tick, step, and bar events to registered callbacks
- Deterministic monotonic timing with drift compensation

### Harmony Engine
- Root note + scale (major, minor, dorian, phrygian, mixolydian, lydian, locrian, pentatonic, chromatic)
- Chord voicings: triad, seventh, extended, sus, add
- Provides `allowed_notes()`, `notes_in_range()`, `nearest_in_scale()`

### Pattern Engine
- Variable pattern length per track (polyrhythm)
- Per-step: active flag, probability, velocity, velocity variation, skip
- Multiple tracks at independent lengths

### Melody Generator
- Directions: ascending, descending, random, pendulum
- Density gate, repetition bias, note range
- Motif generation and constrained note mutation

### Drum Generator
- Channels: kick, snare, hihat, percussion
- Per-channel: pattern length, per-step probability, velocity variation, accent, microtiming
- Fill mode (density boost), pattern mutation, polyrhythm

### Randomization Engine
- Pattern randomization, melody parameter randomization, drum randomization
- Pattern morphing (gradual blend between states)
- Chaos burst for controlled momentary chaos
- All mutations constrained to musical boundaries

### MIDI Engine
- Abstract `MidiBackend` interface → `MockMidiBackend` (tests) or `RtMidiBackend` (real hardware)
- Multi-channel routing (melody, bass, drums)
- Stuck note prevention via active note tracking
- Retrigger handling (note_off before note_on on same channel/note)

### Preset System
- Save/load/overwrite/delete presets as `.kseq` JSON files
- Full `EngineState` roundtrip serialization
- Schema versioning for forward compatibility

## Quick Start

```python
from kodoseq import KodoSeq

engine = KodoSeq()
engine.set_bpm(120)
engine.set_scale("dorian")
engine.set_root(62)      # D
engine.set_density(0.7)
engine.start()

# ... live parameter control ...

engine.save_preset("my_groove")
engine.stop()
```

## Requirements

- Python 3.9+
- No required runtime dependencies (stdlib only)
- Optional: `python-rtmidi` for real MIDI hardware output

## Development

```bash
pip install -e ".[dev]"
pytest kodoseq/tests/
```

## Testing

104 tests covering:
- Clock accuracy and event dispatch
- Harmony scale/mode correctness
- Pattern engine probability, polyrhythm, velocity
- Melody direction, density, scale constraints
- Drum channel probability, accents, fills, polyrhythm
- Randomization boundary enforcement
- MIDI engine stuck-note prevention, retrigger
- Preset save/load/overwrite/roundtrip integrity

---

&copy; 2025 KODOSEQ &bull; [MIT License](LICENSE)
