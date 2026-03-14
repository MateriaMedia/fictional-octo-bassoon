"""Tests for RandomizationEngine."""

import pytest
import random

from kodoseq.state import (
    RandomState, PatternState, MelodyState, DrumState, HarmonyState
)
from kodoseq.core.randomizer.randomization_engine import RandomizationEngine


def _make_randomizer(chaos=0.8, seed=42):
    state = RandomState(chaos=chaos, seed=seed)
    return RandomizationEngine(state, seed=seed)


def test_reseed_reproducibility():
    rng = _make_randomizer(chaos=1.0, seed=100)
    pattern1 = PatternState()
    rng.randomize_pattern(pattern1)

    rng.reseed(100)
    pattern2 = PatternState()
    rng.randomize_pattern(pattern2)

    probs1 = [s.probability for s in pattern1.melody_track.steps]
    probs2 = [s.probability for s in pattern2.melody_track.steps]
    assert probs1 == probs2


def test_randomize_pattern_stays_in_velocity_range():
    rng = _make_randomizer(chaos=1.0)
    pattern = PatternState()
    rng.randomize_pattern(pattern)
    for step in pattern.melody_track.steps:
        assert 0 <= step.velocity <= 127


def test_randomize_melody_density_bounds():
    rng = _make_randomizer(chaos=1.0)
    for _ in range(50):
        melody = MelodyState()
        rng.randomize_melody(melody)
        assert rng.DENSITY_CLAMP[0] <= melody.density <= rng.DENSITY_CLAMP[1]


def test_randomize_melody_direction_valid():
    rng = _make_randomizer(chaos=1.0)
    valid_directions = {"ascending", "descending", "random", "pendulum"}
    for _ in range(50):
        melody = MelodyState()
        rng.randomize_melody(melody)
        assert melody.direction in valid_directions


def test_randomize_drums_probabilities_in_range():
    rng = _make_randomizer(chaos=1.0)
    drum = DrumState()
    rng.randomize_drums(drum)
    for ch in [drum.kick, drum.snare, drum.hihat, drum.percussion]:
        for prob in ch.steps:
            assert 0.0 <= prob <= 1.0


def test_mutation_rate_clamping():
    state = RandomState()
    rng = RandomizationEngine(state)
    rng.set_mutation_rate(1.5)
    assert state.mutation_rate == 1.0
    rng.set_mutation_rate(-0.5)
    assert state.mutation_rate == 0.0


def test_chaos_clamping():
    state = RandomState()
    rng = RandomizationEngine(state)
    rng.set_chaos(2.0)
    assert state.chaos == 1.0
    rng.set_chaos(-1.0)
    assert state.chaos == 0.0


def test_morph_pattern_blends_states():
    rng = _make_randomizer(chaos=0.5, seed=7)
    src = PatternState()
    tgt = PatternState()

    # Set target to all active, src to all inactive
    for step in src.melody_track.steps:
        step.active = False
        step.probability = 0.0
    for step in tgt.melody_track.steps:
        step.active = True
        step.probability = 1.0

    rng.morph_pattern(src, tgt, amount=1.0)
    # At amount=1.0, all src steps should become target
    assert all(s.active for s in src.melody_track.steps)


def test_morph_amount_zero_no_change():
    rng = _make_randomizer()
    src = PatternState()
    original_probs = [s.probability for s in src.melody_track.steps]
    tgt = PatternState()
    for step in tgt.melody_track.steps:
        step.probability = 0.5
    rng.morph_pattern(src, tgt, amount=0.0)
    assert [s.probability for s in src.melody_track.steps] == original_probs


def test_randomize_harmony_valid_scale():
    from kodoseq.core.harmony.harmony_engine import SCALES
    rng = _make_randomizer(chaos=1.0)
    harmony = HarmonyState()
    for _ in range(20):
        rng.randomize_harmony(harmony)
        assert harmony.scale in SCALES


def test_chaos_burst_does_not_break_state():
    rng = _make_randomizer(chaos=0.3)
    pattern = PatternState()
    melody = MelodyState()
    original_chaos = rng.state.chaos

    rng.chaos_burst(pattern, melody)

    # Chaos should be restored after burst
    assert rng.state.chaos == original_chaos

    # Pattern should still be valid
    for step in pattern.melody_track.steps:
        assert 0.0 <= step.probability <= 1.0
        assert 0 <= step.velocity <= 127
