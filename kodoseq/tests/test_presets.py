"""Tests for PresetSystem."""

import json
import pytest
from pathlib import Path

from kodoseq.state import EngineState, ClockState, HarmonyState
from kodoseq.core.presets.preset_system import PresetManager, PresetError


@pytest.fixture
def preset_dir(tmp_path):
    return tmp_path / "presets"


@pytest.fixture
def manager(preset_dir):
    return PresetManager(preset_dir)


def test_save_and_load(manager):
    state = EngineState()
    state.clock.bpm = 140.0
    state.harmony.root = 62

    manager.save("test_preset", state)
    loaded = manager.load("test_preset")

    assert loaded.clock.bpm == 140.0
    assert loaded.harmony.root == 62
    assert loaded.preset_name == "test_preset"


def test_save_no_overwrite_raises(manager):
    state = EngineState()
    manager.save("preset1", state)
    with pytest.raises(PresetError):
        manager.save("preset1", state, overwrite=False)


def test_save_overwrite_ok(manager):
    state = EngineState()
    manager.save("preset1", state)
    state.clock.bpm = 160.0
    manager.save("preset1", state, overwrite=True)
    loaded = manager.load("preset1")
    assert loaded.clock.bpm == 160.0


def test_overwrite_method(manager):
    state = EngineState()
    manager.save("mypreset", state)
    state.clock.bpm = 170.0
    manager.overwrite("mypreset", state)
    loaded = manager.load("mypreset")
    assert loaded.clock.bpm == 170.0


def test_load_nonexistent_raises(manager):
    with pytest.raises(PresetError):
        manager.load("does_not_exist")


def test_delete_preset(manager):
    state = EngineState()
    manager.save("to_delete", state)
    assert "to_delete" in manager.list_presets()
    manager.delete("to_delete")
    assert "to_delete" not in manager.list_presets()


def test_delete_nonexistent_raises(manager):
    with pytest.raises(PresetError):
        manager.delete("ghost")


def test_list_presets(manager):
    manager.save("alpha", EngineState())
    manager.save("beta", EngineState())
    manager.save("gamma", EngineState())
    listing = manager.list_presets()
    assert listing == ["alpha", "beta", "gamma"]


def test_reset_returns_default(manager):
    state = manager.reset("my_preset")
    assert state.clock.bpm == 120.0
    assert state.preset_name == "my_preset"


def test_load_or_default_missing(manager):
    state = manager.load_or_default("nonexistent")
    assert state.clock.bpm == 120.0
    assert state.preset_name == "nonexistent"


def test_load_or_default_existing(manager):
    s = EngineState()
    s.clock.bpm = 180.0
    manager.save("existing", s)
    loaded = manager.load_or_default("existing")
    assert loaded.clock.bpm == 180.0


def test_invalid_preset_name_raises(manager):
    state = EngineState()
    with pytest.raises(PresetError):
        manager.save("", state)


def test_json_file_is_valid(manager, preset_dir):
    state = EngineState()
    manager.save("check_json", state)
    path = preset_dir / "check_json.kseq"
    with open(path) as f:
        data = json.load(f)
    assert "_schema_version" in data
    assert "clock" in data
    assert "harmony" in data
    assert "drum" in data


def test_roundtrip_full_state(manager):
    """Complete state roundtrip: all fields preserved."""
    state = EngineState()
    state.clock.bpm = 137.5
    state.clock.swing = 0.25
    state.harmony.root = 55
    state.harmony.scale = "dorian"
    state.melody.density = 0.7
    state.melody.direction = "ascending"
    state.random.mutation_rate = 0.3
    state.random.chaos = 0.4
    state.drum.kick.velocity = 110
    state.midi_routing.melody_channel = 2

    manager.save("full_roundtrip", state)
    loaded = manager.load("full_roundtrip")

    assert loaded.clock.bpm == 137.5
    assert loaded.clock.swing == 0.25
    assert loaded.harmony.root == 55
    assert loaded.harmony.scale == "dorian"
    assert loaded.melody.density == 0.7
    assert loaded.melody.direction == "ascending"
    assert loaded.random.mutation_rate == 0.3
    assert loaded.random.chaos == 0.4
    assert loaded.drum.kick.velocity == 110
    assert loaded.midi_routing.melody_channel == 2


def test_corrupted_preset_raises(manager, preset_dir):
    preset_dir.mkdir(parents=True, exist_ok=True)
    bad_file = preset_dir / "broken.kseq"
    bad_file.write_text("{ not valid json }")
    with pytest.raises(PresetError):
        manager.load("broken")


def test_load_all(manager):
    manager.save("p1", EngineState())
    manager.save("p2", EngineState())
    bank = manager.load_all()
    assert "p1" in bank
    assert "p2" in bank
    assert isinstance(bank["p1"], EngineState)
