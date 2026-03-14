"""Tests for HarmonyEngine."""

import pytest

from kodoseq.state import HarmonyState
from kodoseq.core.harmony.harmony_engine import HarmonyEngine, SCALES


def test_default_harmony():
    engine = HarmonyEngine(HarmonyState())
    notes = engine.allowed_notes()
    assert len(notes) > 0
    # All notes must be in MIDI range
    assert all(0 <= n <= 127 for n in notes)


def test_major_scale_intervals():
    """C major should contain C, D, E, F, G, A, B (no accidentals)."""
    state = HarmonyState(root=60, scale="major", octave_range=1)
    engine = HarmonyEngine(state)
    notes = engine.allowed_notes()
    # Check that note classes include {0,2,4,5,7,9,11}
    note_classes = {n % 12 for n in notes}
    assert note_classes == {0, 2, 4, 5, 7, 9, 11}


def test_minor_scale_intervals():
    state = HarmonyState(root=60, scale="minor", octave_range=1)
    engine = HarmonyEngine(state)
    notes = engine.allowed_notes()
    note_classes = {n % 12 for n in notes}
    assert note_classes == {0, 2, 3, 5, 7, 8, 10}


def test_all_scales_produce_valid_notes():
    for scale in SCALES:
        state = HarmonyState(root=60, scale=scale)
        engine = HarmonyEngine(state)
        notes = engine.allowed_notes()
        assert len(notes) > 0
        assert all(0 <= n <= 127 for n in notes)


def test_set_root():
    engine = HarmonyEngine(HarmonyState(root=60))
    engine.set_root(62)
    assert engine.state.root == 62
    notes = engine.allowed_notes()
    assert all(0 <= n <= 127 for n in notes)


def test_set_root_invalid():
    engine = HarmonyEngine(HarmonyState())
    with pytest.raises(ValueError):
        engine.set_root(-1)
    with pytest.raises(ValueError):
        engine.set_root(128)


def test_set_scale_invalid():
    engine = HarmonyEngine(HarmonyState())
    with pytest.raises(ValueError):
        engine.set_scale("nonexistent_scale")


def test_set_chord_mode_invalid():
    engine = HarmonyEngine(HarmonyState())
    with pytest.raises(ValueError):
        engine.set_chord_mode("invalid_mode")


def test_notes_in_range():
    engine = HarmonyEngine(HarmonyState(root=60, scale="major"))
    notes = engine.notes_in_range(60, 72)
    assert all(60 <= n <= 72 for n in notes)
    assert len(notes) > 0


def test_nearest_in_scale():
    engine = HarmonyEngine(HarmonyState(root=60, scale="major"))
    # C# (61) is not in C major; nearest should be C (60) or D (62)
    nearest = engine.nearest_in_scale(61)
    assert nearest in engine.allowed_notes()


def test_chord_notes_triad():
    engine = HarmonyEngine(HarmonyState(root=60, scale="major", chord_mode="triad"))
    chord = engine.chord_notes()
    # C major triad: C(60), E(64), G(67)
    assert 60 in chord  # root
    assert 64 in chord  # major third
    assert 67 in chord  # fifth


def test_chord_notes_seventh():
    engine = HarmonyEngine(HarmonyState(root=60, scale="major", chord_mode="seventh"))
    chord = engine.chord_notes()
    assert len(chord) >= 4


def test_octave_range():
    state = HarmonyState(root=60, scale="major", octave_range=1)
    engine_small = HarmonyEngine(state)
    notes_small = engine_small.allowed_notes()

    state2 = HarmonyState(root=60, scale="major", octave_range=3)
    engine_large = HarmonyEngine(state2)
    notes_large = engine_large.allowed_notes()

    assert len(notes_large) > len(notes_small)


def test_available_scales():
    engine = HarmonyEngine(HarmonyState())
    scales = engine.available_scales()
    assert "major" in scales
    assert "minor" in scales
    assert len(scales) >= 7


def test_available_chord_modes():
    engine = HarmonyEngine(HarmonyState())
    modes = engine.available_chord_modes()
    assert "triad" in modes
    assert "seventh" in modes
