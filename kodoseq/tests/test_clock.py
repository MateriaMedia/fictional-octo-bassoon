"""Tests for ClockEngine."""

import time
import threading
import pytest

from kodoseq.state import ClockState
from kodoseq.core.clock.clock_engine import ClockEngine


def test_clock_default_state():
    state = ClockState()
    clock = ClockEngine(state)
    assert state.bpm == 120.0
    assert state.swing == 0.0
    assert state.step_resolution == 16
    assert not clock.is_running()


def test_set_bpm_valid():
    clock = ClockEngine(ClockState())
    clock.set_bpm(140.0)
    assert clock.state.bpm == 140.0


def test_set_bpm_invalid():
    clock = ClockEngine(ClockState())
    with pytest.raises(ValueError):
        clock.set_bpm(0)
    with pytest.raises(ValueError):
        clock.set_bpm(-10)


def test_set_swing_valid():
    clock = ClockEngine(ClockState())
    clock.set_swing(0.3)
    assert clock.state.swing == 0.3


def test_set_swing_invalid():
    clock = ClockEngine(ClockState())
    with pytest.raises(ValueError):
        clock.set_swing(0.6)
    with pytest.raises(ValueError):
        clock.set_swing(-0.1)


def test_set_step_resolution():
    clock = ClockEngine(ClockState())
    clock.set_step_resolution(32)
    assert clock.state.step_resolution == 32
    with pytest.raises(ValueError):
        clock.set_step_resolution(0)


def test_set_loop_bars():
    clock = ClockEngine(ClockState())
    clock.set_loop_bars(8)
    assert clock.state.loop_bars == 8
    with pytest.raises(ValueError):
        clock.set_loop_bars(0)


def test_step_events_fired():
    """Clock fires step events during playback."""
    state = ClockState(bpm=600.0, step_resolution=4)
    clock = ClockEngine(state)
    steps_fired = []

    clock.on_step(lambda step, step_in_bar: steps_fired.append(step))
    clock.start()
    time.sleep(0.3)
    clock.stop()

    # At 600 BPM with 4 steps/bar: 600/60 * 4 = 40 steps/sec → ~12 steps in 0.3s
    assert len(steps_fired) >= 1


def test_bar_events_fired():
    """Clock fires bar events at bar boundaries."""
    state = ClockState(bpm=600.0, step_resolution=4)
    clock = ClockEngine(state)
    bars_fired = []

    clock.on_bar(lambda bar: bars_fired.append(bar))
    clock.start()
    time.sleep(0.5)
    clock.stop()

    assert len(bars_fired) >= 1


def test_clock_start_stop():
    clock = ClockEngine(ClockState())
    assert not clock.is_running()
    clock.start()
    assert clock.is_running()
    clock.stop()
    assert not clock.is_running()


def test_clock_no_double_start():
    """Starting an already-running clock is a no-op."""
    clock = ClockEngine(ClockState())
    clock.start()
    thread = clock._thread
    clock.start()  # should not create a new thread
    assert clock._thread is thread
    clock.stop()


def test_seconds_per_step():
    state = ClockState(bpm=120.0, step_resolution=16)
    clock = ClockEngine(state)
    # 120 BPM, 16 steps/bar: 4 beats/bar → 4*(60/120)/16 = 4*0.5/16 = 0.125s
    assert abs(clock.seconds_per_step() - 0.125) < 1e-9


def test_callback_exception_does_not_crash_clock():
    """Exceptions in callbacks must not crash the clock thread."""
    state = ClockState(bpm=600.0, step_resolution=4)
    clock = ClockEngine(state)

    def bad_cb(step, step_in_bar):
        raise RuntimeError("intentional error")

    clock.on_step(bad_cb)
    clock.start()
    time.sleep(0.2)
    clock.stop()
    assert not clock.is_running()
