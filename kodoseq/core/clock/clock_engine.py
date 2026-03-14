"""KODOSEQ Clock Engine

High-resolution, deterministic timing engine.
Drives all pattern generators via event callbacks.

Design:
- Runs in a dedicated thread; never blocks the caller.
- Emits tick, step, and bar events to registered callbacks.
- Swing is applied as a per-step fractional delay on odd steps.
- All timing uses monotonic clock to prevent drift.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List

from kodoseq.state import ClockState

TickCallback = Callable[[int], None]    # (absolute_tick)
StepCallback = Callable[[int, int], None]  # (absolute_step, step_in_bar)
BarCallback = Callable[[int], None]     # (bar_number)


class ClockEngine:
    """Realtime BPM clock that emits tick/step/bar events.

    All callbacks are invoked from the clock thread.
    Callbacks must be fast and non-blocking.
    """

    PPQN = 24  # pulses per quarter note (MIDI standard)

    def __init__(self, state: ClockState) -> None:
        self._state = state
        self._tick_callbacks: List[TickCallback] = []
        self._step_callbacks: List[StepCallback] = []
        self._bar_callbacks: List[BarCallback] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> ClockState:
        return self._state

    def set_bpm(self, bpm: float) -> None:
        if bpm <= 0:
            raise ValueError("BPM must be positive")
        with self._lock:
            self._state.bpm = bpm

    def set_swing(self, swing: float) -> None:
        if not 0.0 <= swing <= 0.5:
            raise ValueError("Swing must be in [0.0, 0.5]")
        with self._lock:
            self._state.swing = swing

    def set_step_resolution(self, steps_per_bar: int) -> None:
        if steps_per_bar < 1:
            raise ValueError("Step resolution must be >= 1")
        with self._lock:
            self._state.step_resolution = steps_per_bar

    def set_loop_bars(self, bars: int) -> None:
        if bars < 1:
            raise ValueError("loop_bars must be >= 1")
        with self._lock:
            self._state.loop_bars = bars

    def on_tick(self, cb: TickCallback) -> None:
        self._tick_callbacks.append(cb)

    def on_step(self, cb: StepCallback) -> None:
        self._step_callbacks.append(cb)

    def on_bar(self, cb: BarCallback) -> None:
        self._bar_callbacks.append(cb)

    def start(self) -> None:
        if self._state.running:
            return
        self._stop_event.clear()
        self._state.running = True
        self._state.tick = 0
        self._state.step = 0
        self._state.bar = 0
        self._thread = threading.Thread(target=self._run, daemon=True, name="kodoseq-clock")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._state.running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def is_running(self) -> bool:
        return self._state.running

    # ------------------------------------------------------------------
    # Internal clock loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main clock loop. Runs in the clock thread."""
        tick = 0
        step = 0
        bar = 0
        step_in_bar = 0

        # Pre-compute how many PPQN ticks per step at current resolution.
        # For 4/4 time: 1 bar = 4 beats = 4 * PPQN ticks.
        # Steps per bar determined by state.step_resolution.

        next_tick_time = time.monotonic()

        while not self._stop_event.is_set():
            with self._lock:
                bpm = self._state.bpm
                step_resolution = self._state.step_resolution
                swing = self._state.swing
                loop_bars = self._state.loop_bars

            # Seconds per quarter note
            seconds_per_beat = 60.0 / bpm
            # Seconds per PPQN tick
            seconds_per_tick = seconds_per_beat / self.PPQN
            # Ticks per step (at current step_resolution steps per bar)
            # 4 beats per bar, so 4 * PPQN ticks per bar
            ticks_per_bar = 4 * self.PPQN
            ticks_per_step = ticks_per_bar / step_resolution

            # Emit tick event
            self._emit_tick(tick)

            # Check if this tick aligns to a step boundary
            if ticks_per_step >= 1.0:
                if tick % max(1, round(ticks_per_step)) == 0:
                    self._emit_step(step, step_in_bar)
                    step_in_bar += 1

                    if step_in_bar >= step_resolution:
                        step_in_bar = 0
                        self._emit_bar(bar)
                        bar += 1

                        if loop_bars > 0 and bar >= loop_bars:
                            bar = 0
                            step = 0

                    step += 1
                    with self._lock:
                        self._state.step = step
                        self._state.bar = bar

            tick += 1
            with self._lock:
                self._state.tick = tick

            # Compute swing offset: odd steps within a beat are delayed
            swing_offset = 0.0
            if swing > 0.0 and (step_in_bar % 2 == 1):
                swing_offset = swing * seconds_per_beat / (step_resolution / 4)

            next_tick_time += seconds_per_tick + swing_offset

            # Sleep until next tick, compensating for processing overhead
            now = time.monotonic()
            sleep_duration = next_tick_time - now
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            else:
                # We're behind; reset anchor to prevent spiral drift
                next_tick_time = time.monotonic()

    # ------------------------------------------------------------------
    # Event dispatch
    # ------------------------------------------------------------------

    def _emit_tick(self, tick: int) -> None:
        for cb in self._tick_callbacks:
            try:
                cb(tick)
            except Exception:
                pass

    def _emit_step(self, step: int, step_in_bar: int) -> None:
        for cb in self._step_callbacks:
            try:
                cb(step, step_in_bar)
            except Exception:
                pass

    def _emit_bar(self, bar: int) -> None:
        for cb in self._bar_callbacks:
            try:
                cb(bar)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def seconds_per_step(self) -> float:
        """Return duration of a single step in seconds (at current BPM/resolution)."""
        bpm = self._state.bpm
        step_resolution = self._state.step_resolution
        seconds_per_beat = 60.0 / bpm
        return (seconds_per_beat * 4) / step_resolution
