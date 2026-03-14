"""Tests for MelodyGenerator."""

import random
import pytest

from kodoseq.state import MelodyState, HarmonyState
from kodoseq.core.harmony.harmony_engine import HarmonyEngine
from kodoseq.core.generators.melody_generator import MelodyGenerator


def _make_generator(direction="random", density=1.0, seed=42):
    harmony = HarmonyEngine(HarmonyState(root=60, scale="major"))
    state = MelodyState(density=density, direction=direction, note_low=48, note_high=84)
    rng = random.Random(seed)
    return MelodyGenerator(state, harmony, rng)


def test_generate_returns_valid_note():
    gen = _make_generator()
    result = gen.generate(0, 100)
    assert result is not None
    note, vel, dur = result
    assert 48 <= note <= 84
    assert 0 < vel <= 127
    assert 0.0 < dur <= 1.0


def test_generate_note_in_scale():
    harmony = HarmonyEngine(HarmonyState(root=60, scale="major"))
    gen = _make_generator()
    allowed = set(harmony.allowed_notes())
    for step in range(32):
        result = gen.generate(step, 100)
        if result:
            note, _, _ = result
            assert note in allowed, f"Note {note} not in allowed set"


def test_zero_density_no_output():
    gen = _make_generator(density=0.0)
    for i in range(50):
        assert gen.generate(i, 100) is None


def test_full_density_always_output():
    gen = _make_generator(density=1.0)
    for i in range(20):
        result = gen.generate(i, 100)
        assert result is not None


def test_ascending_direction():
    """Ascending direction steps through notes in order (no repetition bias)."""
    harmony = HarmonyEngine(HarmonyState(root=60, scale="major"))
    state = MelodyState(density=1.0, direction="ascending", note_low=48, note_high=84,
                        repetition_bias=0.0)
    gen = MelodyGenerator(state, harmony, random.Random(42))
    allowed = harmony.notes_in_range(48, 84)
    notes = []
    for i in range(len(allowed)):
        result = gen.generate(i, 100)
        if result:
            notes.append(result[0])
    assert notes == allowed[:len(notes)]


def test_descending_direction():
    """Descending direction steps through notes in reverse (no repetition bias)."""
    harmony = HarmonyEngine(HarmonyState(root=60, scale="major"))
    state = MelodyState(density=1.0, direction="descending", note_low=48, note_high=84,
                        repetition_bias=0.0)
    gen = MelodyGenerator(state, harmony, random.Random(42))
    allowed = harmony.notes_in_range(48, 84)
    notes = []
    for i in range(len(allowed)):
        result = gen.generate(i, 100)
        if result:
            notes.append(result[0])
    assert notes == list(reversed(allowed))[:len(notes)]


def test_pendulum_direction():
    gen = _make_generator(direction="pendulum", density=1.0)
    notes = []
    for i in range(20):
        result = gen.generate(i, 100)
        if result:
            notes.append(result[0])
    # Pendulum should not monotonically increase or decrease forever
    assert len(notes) > 0
    if len(notes) >= 3:
        all_same = len(set(notes)) == 1
        assert not all_same


def test_repetition_bias_repeats_note():
    """High repetition bias should repeat the last note frequently."""
    gen = _make_generator(density=1.0, seed=0)
    gen.set_repetition_bias(1.0)  # Always repeat
    first = gen.generate(0, 100)
    assert first is not None
    note1 = first[0]

    repeats = 0
    for i in range(1, 20):
        result = gen.generate(i, 100)
        if result and result[0] == note1:
            repeats += 1
    assert repeats >= 15  # With bias=1.0, should almost always repeat


def test_invalid_direction():
    gen = _make_generator()
    with pytest.raises(ValueError):
        gen.set_direction("diagonal")


def test_invalid_range():
    gen = _make_generator()
    with pytest.raises(ValueError):
        gen.set_range(80, 60)  # low >= high


def test_generate_motif():
    gen = _make_generator(density=0.8)
    harmony = HarmonyEngine(HarmonyState(root=60, scale="major"))
    allowed = set(harmony.allowed_notes())
    motif = gen.generate_motif(8)
    assert len(motif) == 8
    for note in motif:
        if note is not None:
            assert note in allowed


def test_mutate_note_stays_in_scale():
    harmony = HarmonyEngine(HarmonyState(root=60, scale="major"))
    state = MelodyState(note_low=48, note_high=84)
    gen = MelodyGenerator(state, harmony, random.Random(0))
    allowed = set(harmony.allowed_notes())
    for note in harmony.notes_in_range(48, 84):
        mutated = gen.mutate_note(note, 1.0)
        assert mutated in allowed


def test_reset_clears_last_note():
    gen = _make_generator(density=1.0)
    gen.generate(0, 100)
    assert gen._last_note is not None
    gen.reset()
    assert gen._last_note is None


def test_notes_within_configured_range():
    gen = _make_generator()
    gen.set_range(60, 72)
    for i in range(20):
        result = gen.generate(i, 100)
        if result:
            note, _, _ = result
            assert 60 <= note <= 72
