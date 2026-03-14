"""Tests for MidiEngine and MockMidiBackend."""

import pytest

from kodoseq.state import MidiRoutingState
from kodoseq.core.midi.midi_engine import MidiEngine, MockMidiBackend, MidiMessage


def _make_engine():
    state = MidiRoutingState()
    backend = MockMidiBackend()
    engine = MidiEngine(state, backend)
    engine.open()
    return engine, backend


def test_note_on_sends_message():
    engine, backend = _make_engine()
    engine.note_on(0, 60, 100)
    msgs = backend.flush()
    assert len(msgs) == 1
    assert msgs[0].status == "note_on"
    assert msgs[0].data1 == 60
    assert msgs[0].data2 == 100


def test_note_off_sends_message():
    engine, backend = _make_engine()
    engine.note_on(0, 60, 100)
    backend.flush()
    engine.note_off(0, 60)
    msgs = backend.flush()
    assert len(msgs) == 1
    assert msgs[0].status == "note_off"
    assert msgs[0].data1 == 60


def test_retrigger_sends_note_off_first():
    engine, backend = _make_engine()
    engine.note_on(0, 60, 100)
    backend.flush()
    engine.note_on(0, 60, 80)  # retrigger same note
    msgs = backend.flush()
    assert msgs[0].status == "note_off"
    assert msgs[1].status == "note_on"


def test_all_notes_off_releases_active():
    engine, backend = _make_engine()
    engine.note_on(0, 60, 100)
    engine.note_on(0, 64, 100)
    engine.note_on(1, 67, 100)
    backend.flush()
    engine.all_notes_off()
    msgs = backend.flush()
    # Three note_off messages expected
    assert len(msgs) == 3
    assert all(m.status == "note_off" for m in msgs)


def test_panic_clears_all_notes():
    engine, backend = _make_engine()
    engine.note_on(0, 60, 100)
    engine.note_on(0, 62, 90)
    backend.flush()
    engine.panic()
    msgs = backend.flush()
    assert len(msgs) == 2
    assert all(m.status == "note_off" for m in msgs)
    # After panic, active notes should be empty
    assert len(engine._active_notes) == 0


def test_control_change():
    engine, backend = _make_engine()
    engine.control_change(0, 74, 64)
    msgs = backend.flush()
    assert len(msgs) == 1
    assert msgs[0].status == "cc"
    assert msgs[0].data1 == 74
    assert msgs[0].data2 == 64


def test_invalid_note_clamped():
    engine, backend = _make_engine()
    engine.note_on(0, -1, 100)  # invalid note, should be ignored
    engine.note_on(0, 128, 100)  # invalid note
    msgs = backend.flush()
    assert len(msgs) == 0


def test_invalid_cc_clamped():
    engine, backend = _make_engine()
    engine.control_change(0, -1, 64)
    engine.control_change(0, 128, 64)
    msgs = backend.flush()
    assert len(msgs) == 0


def test_velocity_zero_does_not_add_to_active():
    engine, backend = _make_engine()
    engine.note_on(0, 60, 0)  # velocity 0 = note off in MIDI
    assert (0, 60) not in engine._active_notes


def test_channel_routing():
    state = MidiRoutingState(melody_channel=3, bass_channel=7)
    backend = MockMidiBackend()
    engine = MidiEngine(state, backend)
    engine.open()
    assert engine.melody_channel == 3
    assert engine.bass_channel == 7


def test_mock_backend_available_ports():
    backend = MockMidiBackend()
    ports = backend.available_ports()
    assert len(ports) >= 1


def test_close_clears_active_notes():
    engine, backend = _make_engine()
    engine.note_on(0, 60, 100)
    engine.close()
    msgs = backend.flush()
    # close() calls all_notes_off()
    note_offs = [m for m in msgs if m.status == "note_off"]
    assert len(note_offs) >= 1
