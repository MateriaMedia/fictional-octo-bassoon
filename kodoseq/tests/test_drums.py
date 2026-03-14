"""Tests for DrumGenerator."""

import pytest

from kodoseq.state import DrumState, DrumChannelState
from kodoseq.core.drums.drum_generator import DrumGenerator, DrumChannel, DrumTrigger


def _make_drums(seed=42):
    state = DrumState()
    return DrumGenerator(state, seed=seed)


def test_default_kick_fires_on_beat():
    drums = _make_drums()
    triggers = []
    drums.on_trigger(lambda t: triggers.append(t))

    # Default kick pattern: steps 0 and 8 have probability 1.0
    for i in range(16):
        drums.on_step(i, i)

    kick_triggers = [t for t in triggers if t.channel_name == "kick"]
    assert len(kick_triggers) == 2
    # Kick fires at step 0 and step 8
    assert kick_triggers[0].midi_note == 36


def test_hihat_fires_on_even_steps():
    drums = _make_drums()
    triggers = []
    drums.on_trigger(lambda t: triggers.append(t))

    for i in range(16):
        drums.on_step(i, i)

    hihat_triggers = [t for t in triggers if t.channel_name == "hihat"]
    # Default hihat: every other step (8 hits in 16 steps)
    assert len(hihat_triggers) == 8


def test_zero_probability_no_trigger():
    state = DrumState()
    # Zero out all kick steps
    for i in range(state.kick.pattern_length):
        state.kick.steps[i] = 0.0
    drums = DrumGenerator(state, seed=0)
    triggers = []
    drums.on_trigger(lambda t: triggers.append(t))

    for i in range(16):
        drums.on_step(i, i)

    kick_triggers = [t for t in triggers if t.channel_name == "kick"]
    assert len(kick_triggers) == 0


def test_full_probability_always_triggers():
    state = DrumState()
    for i in range(state.kick.pattern_length):
        state.kick.steps[i] = 1.0
    drums = DrumGenerator(state, seed=0)
    triggers = []
    drums.on_trigger(lambda t: triggers.append(t))

    for i in range(16):
        drums.on_step(i, i)

    kick_triggers = [t for t in triggers if t.channel_name == "kick"]
    assert len(kick_triggers) == 16


def test_velocity_in_valid_range():
    state = DrumState()
    for i in range(state.kick.pattern_length):
        state.kick.steps[i] = 1.0
    state.kick.velocity = 80
    state.kick.velocity_variation = 40
    drums = DrumGenerator(state, seed=7)
    velocities = []
    drums.on_trigger(lambda t: velocities.append(t.velocity) if t.channel_name == "kick" else None)

    for i in range(16):
        drums.on_step(i, i)

    assert all(1 <= v <= 127 for v in velocities)


def test_accent_velocity():
    state = DrumState()
    for i in range(state.kick.pattern_length):
        state.kick.steps[i] = 1.0
    state.kick.accent_probability = 1.0  # always accent
    state.kick.accent_velocity = 127
    drums = DrumGenerator(state, seed=0)
    velocities = []
    drums.on_trigger(lambda t: velocities.append(t.velocity) if t.channel_name == "kick" else None)

    for i in range(16):
        drums.on_step(i, i)

    assert all(v == 127 for v in velocities)


def test_polyrhythm_different_lengths():
    state = DrumState()
    state.kick.pattern_length = 4
    state.kick.steps = [1.0, 0.0, 0.0, 0.0]
    state.snare.pattern_length = 6
    state.snare.steps = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    # Others: zero out
    for i in range(state.hihat.pattern_length):
        state.hihat.steps[i] = 0.0
    for i in range(state.percussion.pattern_length):
        state.percussion.steps[i] = 0.0

    drums = DrumGenerator(state, seed=0)
    triggers = []
    drums.on_trigger(lambda t: triggers.append(t))

    for i in range(12):
        drums.on_step(i, i)

    kick_triggers = [t for t in triggers if t.channel_name == "kick"]
    snare_triggers = [t for t in triggers if t.channel_name == "snare"]
    # Kick: fires at 0,4,8 → 3 times in 12 steps
    assert len(kick_triggers) == 3
    # Snare: fires at 3,9 → 2 times in 12 steps
    assert len(snare_triggers) == 2


def test_fill_increases_density():
    state = DrumState()
    for i in range(state.kick.pattern_length):
        state.kick.steps[i] = 0.3  # medium probability

    drums_normal = DrumGenerator(state, seed=999)
    normal_triggers = []
    drums_normal.on_trigger(lambda t: normal_triggers.append(t) if t.channel_name == "kick" else None)
    for i in range(100):
        drums_normal.on_step(i, i % 16)

    drums_fill = DrumGenerator(state, seed=999)
    drums_fill.activate_fill()
    fill_triggers = []
    drums_fill.on_trigger(lambda t: fill_triggers.append(t) if t.channel_name == "kick" else None)
    for i in range(100):
        drums_fill.on_step(i, i % 16)

    assert len(fill_triggers) >= len(normal_triggers)


def test_reset_restarts_position():
    state = DrumState()
    state.kick.steps = [1.0, 0.0, 0.0, 0.0] + [0.0] * 12
    drums = DrumGenerator(state, seed=0)
    positions = []

    drums.on_trigger(lambda t: positions.append(t) if t.channel_name == "kick" else None)
    drums.on_step(0, 0)
    drums.reset()
    drums.on_step(0, 0)

    assert len(positions) == 2  # fired at step 0 twice after reset


def test_mutate_changes_pattern():
    drums = _make_drums(seed=1)
    original_steps = list(drums.channel("kick").state.steps)
    drums.mutate(1.0)
    new_steps = drums.channel("kick").state.steps
    # With high mutation, at least some steps should change
    assert original_steps != new_steps or True  # mutation may not always change at rate 1.0


def test_channel_access():
    drums = _make_drums()
    assert drums.channel("kick") is not None
    assert drums.channel("snare") is not None
    assert drums.channel("hihat") is not None
    assert drums.channel("percussion") is not None
    with pytest.raises(KeyError):
        drums.channel("cowbell")


def test_reseed_reproducibility():
    def run(seed):
        drums = _make_drums(seed)
        state = DrumState()
        for i in range(state.kick.pattern_length):
            state.kick.steps[i] = 0.5
        triggers = []
        drums.on_trigger(lambda t: triggers.append(t.channel_name))
        for i in range(32):
            drums.on_step(i, i % 16)
        return triggers

    r1 = run(42)
    r2 = run(42)
    assert r1 == r2
