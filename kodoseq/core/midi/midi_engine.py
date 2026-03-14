"""KODOSEQ MIDI Engine

Handles MIDI output with stuck-note prevention, multi-channel routing,
and an abstract interface that supports both real (rtmidi) and mock backends.

Architecture:
- MidiBackend: abstract interface for MIDI output
- MockMidiBackend: in-memory backend for testing
- RtMidiBackend: rtmidi-based backend for real hardware
- MidiEngine: high-level engine that manages note state and routing
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

from kodoseq.state import MidiRoutingState


class MidiMessage(NamedTuple):
    channel: int    # 0-indexed (0–15)
    status: str     # "note_on" | "note_off" | "cc"
    data1: int      # note or CC number
    data2: int      # velocity or CC value


class MidiBackend(ABC):
    """Abstract MIDI output backend."""

    @abstractmethod
    def send(self, channel: int, status: str, data1: int, data2: int) -> None: ...

    @abstractmethod
    def open(self, port_name: str = "") -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def available_ports(self) -> List[str]: ...


class MockMidiBackend(MidiBackend):
    """In-memory MIDI backend for testing and offline use."""

    def __init__(self) -> None:
        self.messages: List[MidiMessage] = []
        self._open = False

    def open(self, port_name: str = "") -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def available_ports(self) -> List[str]:
        return ["Mock MIDI Port"]

    def send(self, channel: int, status: str, data1: int, data2: int) -> None:
        self.messages.append(MidiMessage(channel, status, data1, data2))

    def flush(self) -> List[MidiMessage]:
        msgs = list(self.messages)
        self.messages.clear()
        return msgs


class RtMidiBackend(MidiBackend):
    """rtmidi-based MIDI backend for real hardware output.

    Requires the optional 'python-rtmidi' package.
    """

    def __init__(self) -> None:
        try:
            import rtmidi  # type: ignore
            self._rtmidi = rtmidi
        except ImportError as exc:
            raise ImportError(
                "python-rtmidi is required for real MIDI output. "
                "Install it with: pip install python-rtmidi"
            ) from exc

        self._midi_out = self._rtmidi.MidiOut()
        self._port_open = False

    def available_ports(self) -> List[str]:
        return self._midi_out.get_ports()

    def open(self, port_name: str = "") -> None:
        ports = self.available_ports()
        if not ports:
            self._midi_out.open_virtual_port("KODOSEQ")
            self._port_open = True
            return

        if port_name:
            for i, name in enumerate(ports):
                if port_name in name:
                    self._midi_out.open_port(i)
                    self._port_open = True
                    return
            raise ValueError(f"MIDI port '{port_name}' not found. Available: {ports}")
        else:
            self._midi_out.open_port(0)
            self._port_open = True

    def close(self) -> None:
        if self._port_open:
            self._midi_out.close_port()
            self._port_open = False

    def send(self, channel: int, status: str, data1: int, data2: int) -> None:
        if not self._port_open:
            return

        ch = channel & 0x0F
        if status == "note_on":
            self._midi_out.send_message([0x90 | ch, data1 & 0x7F, data2 & 0x7F])
        elif status == "note_off":
            self._midi_out.send_message([0x80 | ch, data1 & 0x7F, 0])
        elif status == "cc":
            self._midi_out.send_message([0xB0 | ch, data1 & 0x7F, data2 & 0x7F])


# Active note tracking tuple
_ActiveNote = Tuple[int, int]  # (channel, note)


class MidiEngine:
    """High-level MIDI engine with stuck-note prevention.

    Wraps a MidiBackend and tracks all active notes so they can be
    silenced safely on stop or panic.
    """

    def __init__(self, state: MidiRoutingState, backend: Optional[MidiBackend] = None) -> None:
        self._state = state
        self._backend: MidiBackend = backend or MockMidiBackend()
        self._active_notes: Set[_ActiveNote] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        self._backend.open(self._state.output_port)

    def close(self) -> None:
        self.all_notes_off()
        self._backend.close()

    def panic(self) -> None:
        """Immediate all-notes-off on all channels."""
        with self._lock:
            for channel, note in list(self._active_notes):
                self._backend.send(channel, "note_off", note, 0)
            self._active_notes.clear()

    def all_notes_off(self) -> None:
        """Release all currently active notes gracefully."""
        self.panic()

    # ------------------------------------------------------------------
    # Note control
    # ------------------------------------------------------------------

    def note_on(self, channel: int, note: int, velocity: int) -> None:
        if not (0 <= note <= 127) or not (0 <= velocity <= 127):
            return
        with self._lock:
            key: _ActiveNote = (channel, note)
            if key in self._active_notes:
                # Retrigger: send note_off first
                self._backend.send(channel, "note_off", note, 0)
            self._backend.send(channel, "note_on", note, velocity)
            if velocity > 0:
                self._active_notes.add(key)
            else:
                self._active_notes.discard(key)

    def note_off(self, channel: int, note: int) -> None:
        with self._lock:
            key: _ActiveNote = (channel, note)
            self._backend.send(channel, "note_off", note, 0)
            self._active_notes.discard(key)

    def control_change(self, channel: int, cc: int, value: int) -> None:
        if not (0 <= cc <= 127) or not (0 <= value <= 127):
            return
        self._backend.send(channel, "cc", cc, value)

    # ------------------------------------------------------------------
    # Routing helpers
    # ------------------------------------------------------------------

    @property
    def melody_channel(self) -> int:
        return self._state.melody_channel

    @property
    def bass_channel(self) -> int:
        return self._state.bass_channel

    @property
    def backend(self) -> MidiBackend:
        return self._backend

    def available_ports(self) -> List[str]:
        return self._backend.available_ports()
