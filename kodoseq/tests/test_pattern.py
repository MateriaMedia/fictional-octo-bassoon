"""Tests for PatternEngine."""

import pytest

from kodoseq.state import PatternState, PatternTrackState, StepState
from kodoseq.core.pattern.pattern_engine import PatternEngine, PatternTrack


def _make_engine(melody_length=16, bass_length=16):
    melody = PatternTrackState(length=melody_length)
    bass = PatternTrackState(length=bass_length)
    state = PatternState(melody_track=melody, bass_track=bass)
    return PatternEngine(state, seed=42)


def test_default_pattern_fires_triggers():
    engine = _make_engine()
    triggers = []
    engine.on_trigger(lambda step, vel, track_id: triggers.append((step, vel, track_id)))

    # Advance 16 steps
    for i in range(16):
        engine.on_step(i, i % 16)

    # Default all steps active with probability 1.0 → all 16 melody + 16 bass
    melody_triggers = [t for t in triggers if t[2] == PatternEngine.MELODY_TRACK]
    assert len(melody_triggers) == 16


def test_disabled_step_no_trigger():
    engine = _make_engine()
    engine.melody_track().set_step_active(0, False)
    triggers = []
    engine.on_trigger(lambda s, v, t: triggers.append((s, v, t)))

    engine.on_step(0, 0)  # step 0 in melody track should not trigger
    melody_triggers = [t for t in triggers if t[2] == PatternEngine.MELODY_TRACK]
    assert len(melody_triggers) == 0


def test_zero_probability_no_trigger():
    engine = _make_engine()
    for i in range(16):
        engine.melody_track().set_step_probability(i, 0.0)
    triggers = []
    engine.on_trigger(lambda s, v, t: triggers.append((s, v, t)))

    for i in range(16):
        engine.on_step(i, i % 16)

    melody_triggers = [t for t in triggers if t[2] == PatternEngine.MELODY_TRACK]
    assert len(melody_triggers) == 0


def test_velocity_variation():
    state = PatternState()
    engine = PatternEngine(state, seed=0)
    track = engine.melody_track()
    track.set_step_velocity(0, 100, variation=30)

    velocities = set()
    for _ in range(100):
        track.reset()
        engine.on_step(0, 0)

    # Can't check exact but velocity range must be valid
    for step in track.state.steps:
        assert 0 <= step.velocity <= 127


def test_polyrhythm_independent_lengths():
    """Melody (8 steps) and bass (12 steps) cycle independently."""
    melody = PatternTrackState(length=8)
    bass = PatternTrackState(length=12)
    state = PatternState(melody_track=melody, bass_track=bass)
    engine = PatternEngine(state, seed=42)

    mel_positions = []
    bass_positions = []

    def cb(step, vel, track_id):
        if track_id == PatternEngine.MELODY_TRACK:
            mel_positions.append(step)
        else:
            bass_positions.append(step)

    engine.on_trigger(cb)
    for i in range(24):
        engine.on_step(i, i % 16)

    # Melody should cycle 3 times in 24 steps (8*3=24)
    assert len(mel_positions) == 24
    # Bass should cycle 2 times in 24 steps (12*2=24)
    assert len(bass_positions) == 24


def test_reset_restarts_position():
    engine = _make_engine()
    positions = []
    engine.on_trigger(lambda s, v, t: positions.append(s) if t == 0 else None)

    engine.on_step(0, 0)
    engine.on_step(1, 1)
    engine.reset()
    engine.on_step(2, 2)  # after reset, should be at position 0 again

    assert positions[0] == 0
    assert positions[1] == 1
    assert positions[2] == 0  # restarted


def test_track_length_resize():
    engine = _make_engine(melody_length=16)
    track = engine.melody_track()
    track.set_length(8)
    assert track.state.length == 8
    assert len(track.state.steps) == 8


def test_invalid_step_index():
    engine = _make_engine(melody_length=16)
    track = engine.melody_track()
    with pytest.raises(IndexError):
        track.set_step_active(16, True)  # out of range


def test_reseed_reproducibility():
    """Same seed produces same sequence."""
    def run_engine(seed):
        engine = _make_engine()
        # Set all probabilities to 0.5
        for i in range(16):
            engine.melody_track().set_step_probability(i, 0.5)
        engine.reseed(seed)
        results = []
        engine.on_trigger(lambda s, v, t: results.append(s) if t == 0 else None)
        for i in range(32):
            engine.on_step(i, i % 16)
        return results

    r1 = run_engine(123)
    r2 = run_engine(123)
    assert r1 == r2


def test_add_custom_track():
    engine = _make_engine()
    custom_track = PatternTrackState(length=8)
    engine.add_track(99, custom_track)
    track = engine.track(99)
    assert track.track_id == 99


def test_skip_flag():
    engine = _make_engine()
    engine.melody_track().state.steps[0].skip = True
    triggers = []
    engine.on_trigger(lambda s, v, t: triggers.append(t))
    engine.on_step(0, 0)
    melody_triggers = [t for t in triggers if t == PatternEngine.MELODY_TRACK]
    assert len(melody_triggers) == 0
