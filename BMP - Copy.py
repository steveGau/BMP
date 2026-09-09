#!/usr/bin/env python3
"""Digital metronome (BMP player) with a dark-theme GUI."""

from __future__ import annotations

import ctypes
import io
import math
import os
import queue
import struct
import threading
import time
import tkinter as tk
from typing import Callable, List, Optional, Sequence, Tuple
import wave
from ctypes import wintypes

try:
    import winsound
except ImportError:
    winsound = None  # type: ignore[assignment]

SAMPLE_RATE = 22050
WHDR_PREPARED = 0x00000002


class _WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class _WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_void_p),
        ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD),
        ("dwUser", ctypes.c_void_p),
        ("dwFlags", wintypes.DWORD),
        ("dwLoops", wintypes.DWORD),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_void_p),
    ]


BG = "#1E1E1E"
BG_RAISED = "#2A2A2A"
ARC = "#3A3A3A"
DOT_OFF = "#3A3A3A"
ACCENT = "#E74C3C"
TEXT = "#FFFFFF"
MUTED = "#8A8A8A"
COMBO_FG = "#E74C3C"
COMBO_BG = "#2A2A2A"

TIME_SIGNATURES = (
    "1/4",
    "2/4",
    "3/4",
    "4/4",
    "5/4",
    "6/4",
    "7/4",
    "3/8",
    "6/8",
    "9/8",
    "12/8",
)
SOUND_PATTERNS = (
    "1 Beat 1 Sound",
    "1 Beat 1 2 Sound",
    "1 Beat 1 2 3 Sound",
    "1 Beat 1 2 3 4 Sound",
)
ACCENT_OPTIONS = ("Accent On", "Accent Off")

MIN_BPM = 30
MAX_BPM = 300
DEFAULT_BPM = 120
TAP_RESET_GAP_SEC = 2.5
TAP_HISTORY = 8
BEEP_FREQ = {"accent": 1320, "beat": 880, "sub": 660}
MIN_RATIO_PART = 1
MAX_RATIO_PART = 10
LATER_SOUND_GAIN = 0.2
N_TO_ONE_RATIOS = tuple(f"{n}:1" for n in range(2, MAX_RATIO_PART + 1))


def parse_time_signature(value: str) -> Tuple[int, int]:
    parts = value.strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid time signature: {value}")
    numerator = int(parts[0])
    denominator = int(parts[1])
    if numerator < 1 or denominator < 1:
        raise ValueError(f"Invalid time signature: {value}")
    return numerator, denominator


def beat_interval_sec(bpm: int) -> float:
    if bpm <= 0:
        raise ValueError("BPM must be positive")
    return 60.0 / float(bpm)


def subdivisions_for_pattern(pattern: str) -> int:
    body = pattern.replace("1 Beat", "", 1).replace("Sound", "", 1).strip()
    parts = [p for p in body.split() if p]
    return max(1, len(parts))


def clamp_bpm(bpm: float, lo: int = MIN_BPM, hi: int = MAX_BPM) -> int:
    return int(min(hi, max(lo, round(bpm))))


def clamp_ratio_part(value: float) -> int:
    return int(min(MAX_RATIO_PART, max(MIN_RATIO_PART, round(value))))


def default_sound_levels(n: int, count: int) -> Tuple[int, ...]:
    n = int(min(MAX_RATIO_PART, max(2, n)))
    count = max(1, min(4, count))
    if count == 1:
        return (n,)
    if count == 2:
        return (n, 1)
    if count == 3:
        return (n, max(1, int(round(n / 2))), 1)
    return (n, max(1, int(round(n / 2))), max(1, int(round(3 * n / 10))), 1)


def resize_sound_levels(levels: Sequence[int], n: int, count: int) -> Tuple[int, ...]:
    n = int(min(MAX_RATIO_PART, max(2, n)))
    count = max(1, min(4, count))
    if count == 1:
        return (n,)
    defaults = default_sound_levels(n, count)
    out = [n]
    for index in range(1, count):
        if index < len(levels):
            out.append(max(1, min(n, int(levels[index]))))
        else:
            out.append(defaults[index])
    return tuple(out)


def default_loudness_ratio(subdivisions: int) -> Tuple[int, ...]:
    count = max(1, min(4, subdivisions))
    if count == 1:
        return (1,)
    return default_sound_levels(2, count)


def format_loudness_ratio(parts: Sequence[int]) -> str:
    return ":".join(str(int(part)) for part in parts)


def parse_loudness_ratio(value: str) -> Tuple[int, ...]:
    tokens = [token.strip() for token in value.split(":") if token.strip()]
    if not tokens:
        raise ValueError(f"Invalid loudness ratio: {value}")
    parts = tuple(clamp_ratio_part(int(token)) for token in tokens)
    if any(part < 1 for part in parts):
        raise ValueError(f"Invalid loudness ratio: {value}")
    return parts


def ratio_presets_for(_subdivisions: int = 2) -> Tuple[str, ...]:
    return N_TO_ONE_RATIOS


def expand_loudness_ratio(n_to_one: int, subdivisions: int) -> Tuple[int, ...]:
    count = max(1, min(4, subdivisions))
    if count <= 1:
        return (1,)
    return default_sound_levels(n_to_one, count)


def n_from_ratio_text(value: str) -> int:
    parts = parse_loudness_ratio(value)
    return int(min(MAX_RATIO_PART, max(2, parts[0])))


def loudness_gain(ratio: Sequence[int], subdivision: int) -> float:
    """Volume of a click: 1st is 1.0; later sounds are (k / N) * 0.2."""
    if not ratio:
        return 1.0
    peak = float(ratio[0])
    if peak <= 0:
        return 1.0
    index = min(max(0, subdivision), len(ratio) - 1)
    linear = max(0.0, min(1.0, ratio[index] / peak))
    if index == 0:
        return 1.0
    return max(0.002, linear * LATER_SOUND_GAIN)


def ratio_fraction_labels(parts: Sequence[int]) -> Tuple[str, ...]:
    if not parts:
        return ()
    peak = max(parts)
    labels = []
    for part in parts:
        if part == peak:
            labels.append("1")
            continue
        divisor = math.gcd(int(part), int(peak))
        labels.append(f"{part // divisor}/{peak // divisor}")
    return tuple(labels)


def format_ratio_fractions(parts: Sequence[int]) -> str:
    return "  ·  ".join(ratio_fraction_labels(parts))


def tap_tempo_from_times(
    timestamps: Sequence[float],
    max_gap: float = TAP_RESET_GAP_SEC,
) -> Optional[int]:
    if len(timestamps) < 2:
        return None
    intervals: List[float] = []
    for earlier, later in zip(timestamps, timestamps[1:]):
        delta = later - earlier
        if delta <= 0 or delta > max_gap:
            return None
        intervals.append(delta)
    average = sum(intervals) / len(intervals)
    return clamp_bpm(60.0 / average)


def should_accent(beat: int, subdivision: int, accent_on: bool) -> bool:
    return accent_on and beat == 1 and subdivision == 0


def next_beat(beat: int, beats_per_measure: int) -> int:
    if beats_per_measure < 1:
        raise ValueError("beats_per_measure must be >= 1")
    if beat >= beats_per_measure:
        return 1
    return beat + 1


class TapTempo:
    def __init__(self, max_gap: float = TAP_RESET_GAP_SEC, history: int = TAP_HISTORY):
        self.max_gap = max_gap
        self.history = history
        self.times: List[float] = []

    def reset(self) -> None:
        self.times.clear()

    def tap(self, now: Optional[float] = None) -> Optional[int]:
        stamp = time.perf_counter() if now is None else now
        if self.times and stamp - self.times[-1] > self.max_gap:
            self.times = [stamp]
            return None
        self.times.append(stamp)
        if len(self.times) > self.history:
            self.times = self.times[-self.history :]
        return tap_tempo_from_times(self.times, self.max_gap)


def _raw_pcm(freq: float, duration_ms: int, volume: float, sample_rate: int = SAMPLE_RATE) -> bytes:
    count = max(1, int(sample_rate * duration_ms / 1000.0))
    samples = bytearray()
    decay = 48.0
    for index in range(count):
        t = index / sample_rate
        envelope = math.exp(-t * decay)
        value = int(32767 * volume * envelope * math.sin(2.0 * math.pi * freq * t))
        samples.extend(struct.pack("<h", max(-32767, min(32767, value))))
    return bytes(samples)


def _wav_from_pcm(pcm: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    return buffer.getvalue()


def _pcm_wav(freq: float, duration_ms: int, volume: float) -> bytes:
    return _wav_from_pcm(_raw_pcm(freq, duration_ms, volume))


def _scale_pcm(pcm: bytes, gain: float) -> bytes:
    gain = max(0.0, min(1.0, gain))
    if gain >= 0.999:
        return pcm
    scaled = bytearray()
    for index in range(0, len(pcm), 2):
        sample = struct.unpack_from("<h", pcm, index)[0]
        value = int(sample * gain)
        scaled.extend(struct.pack("<h", max(-32767, min(32767, value))))
    return bytes(scaled)


class ClickPlayer:
    """Keep the Windows audio device open so clicks do not die after a few plays."""

    def __init__(self) -> None:
        self._pcm = {
            "accent": _raw_pcm(1320, 42, 0.95),
            "beat": _raw_pcm(880, 42, 0.9),
            "sub": _raw_pcm(880, 42, 0.9),
        }
        self._wav = {
            "accent": _pcm_wav(1320, 42, 0.95),
            "beat": _pcm_wav(880, 42, 0.9),
            "sub": _pcm_wav(880, 42, 0.9),
        }
        self._queue: "queue.Queue[Optional[Tuple[str, float]]]" = queue.Queue(maxsize=4)
        self._alive = True
        self.play_count = 0
        self.fail_count = 0
        self._lock = threading.Lock()
        self._handle = ctypes.c_void_p()
        self._wave_ok = False
        self._winmm = None
        self._live_buffers: List[Tuple[ctypes.Array, _WAVEHDR]] = []
        self._open_device()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _open_device(self) -> None:
        if os.name != "nt":
            return
        try:
            winmm = ctypes.windll.winmm
        except (AttributeError, OSError):
            return
        fmt = _WAVEFORMATEX(1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16, 0)
        err = winmm.waveOutOpen(
            ctypes.byref(self._handle),
            ctypes.c_uint(0xFFFFFFFF),
            ctypes.byref(fmt),
            0,
            0,
            0,
        )
        self._wave_ok = err == 0
        self._winmm = winmm if self._wave_ok else None

    def play(self, kind: str, gain: float = 1.0) -> None:
        if not self._alive:
            return
        item = (kind, max(0.008, min(1.0, gain)))
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                pass

    def close(self) -> None:
        self._alive = False
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        with self._lock:
            if self._wave_ok and getattr(self, "_winmm", None) is not None:
                try:
                    self._winmm.waveOutReset(self._handle)
                    self._winmm.waveOutClose(self._handle)
                except OSError:
                    pass
                self._wave_ok = False

    def _worker(self) -> None:
        while self._alive:
            item = self._queue.get()
            if item is None or not self._alive:
                return
            kind, gain = item
            self._play_one(kind, gain)

    def _play_one(self, kind: str, gain: float = 1.0) -> None:
        if self._play_waveout(kind, gain):
            self.play_count += 1
            return
        if self._play_winsound(kind, gain):
            self.play_count += 1
            return
        if self._play_beep(kind):
            self.play_count += 1
            return
        self.fail_count += 1

    def _play_waveout(self, kind: str, gain: float = 1.0) -> bool:
        if not self._wave_ok or getattr(self, "_winmm", None) is None:
            return False
        pcm = _scale_pcm(self._pcm.get(kind, self._pcm["beat"]), gain)
        buf = ctypes.create_string_buffer(pcm, len(pcm))
        hdr = _WAVEHDR()
        hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
        hdr.dwBufferLength = len(pcm)
        hdr.dwFlags = 0
        with self._lock:
            if not self._wave_ok:
                return False
            self._reap_buffers()
            if self._winmm.waveOutPrepareHeader(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr)) != 0:
                return False
            if self._winmm.waveOutWrite(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr)) != 0:
                self._winmm.waveOutUnprepareHeader(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                return False
            self._live_buffers.append((buf, hdr))
        return True

    def _reap_buffers(self) -> None:
        keep: List[Tuple[ctypes.Array, _WAVEHDR]] = []
        for buf, hdr in self._live_buffers:
            if hdr.dwFlags & WHDR_PREPARED and not (hdr.dwFlags & 1):
                keep.append((buf, hdr))
                continue
            try:
                self._winmm.waveOutUnprepareHeader(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
            except OSError:
                pass
        self._live_buffers = keep[-6:]

    def _play_winsound(self, kind: str, gain: float = 1.0) -> bool:
        if winsound is None:
            return False
        pcm = _scale_pcm(self._pcm.get(kind, self._pcm["beat"]), gain)
        data = _wav_from_pcm(pcm)
        try:
            winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            return True
        except RuntimeError:
            return False

    def _play_beep(self, kind: str) -> bool:
        if winsound is None:
            return False
        freq = BEEP_FREQ.get(kind, 880)
        try:
            winsound.Beep(max(37, min(32767, freq)), 25)
            return True
        except RuntimeError:
            return False


class MetronomeEngine:
    def __init__(self, on_click: Callable[[int, int, str], None]) -> None:
        self.on_click = on_click
        self.bpm = DEFAULT_BPM
        self.beats_per_measure = 2
        self.subdivisions = 1
        self.accent_on = True
        self.playing = False
        self.beat = 1
        self.subdivision = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._stop.set()
        self._thread: Optional[threading.Thread] = None

    def configure(
        self,
        bpm: Optional[int] = None,
        beats_per_measure: Optional[int] = None,
        subdivisions: Optional[int] = None,
        accent_on: Optional[bool] = None,
    ) -> None:
        with self._lock:
            if bpm is not None:
                self.bpm = clamp_bpm(bpm)
            if beats_per_measure is not None:
                self.beats_per_measure = max(1, beats_per_measure)
            if subdivisions is not None:
                self.subdivisions = max(1, subdivisions)
            if accent_on is not None:
                self.accent_on = accent_on

    def start(self) -> None:
        self.stop()
        old = self._thread
        if old is not None and old.is_alive() and old is not threading.current_thread():
            old.join(timeout=1.0)
        self._stop.clear()
        with self._lock:
            self.playing = True
            self.beat = 1
            self.subdivision = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self.playing = False
            self.beat = 1
            self.subdivision = 0
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _snapshot(self) -> Tuple[bool, int, int, int, int, int, bool]:
        with self._lock:
            return (
                self.playing,
                self.bpm,
                self.beats_per_measure,
                self.subdivisions,
                self.beat,
                self.subdivision,
                self.accent_on,
            )

    def _advance(self) -> Tuple[int, int]:
        with self._lock:
            self.subdivision += 1
            if self.subdivision >= self.subdivisions:
                self.subdivision = 0
                self.beat = next_beat(self.beat, self.beats_per_measure)
            return self.beat, self.subdivision

    def _run(self) -> None:
        next_tick = time.perf_counter()
        first = True
        while not self._stop.is_set():
            playing, bpm, _beats, subdivisions, beat, subdivision, accent_on = self._snapshot()
            if not playing:
                return
            if first:
                first = False
            else:
                beat, subdivision = self._advance()
                playing, bpm, _beats, subdivisions, beat, subdivision, accent_on = self._snapshot()
                if not playing or self._stop.is_set():
                    return
            if should_accent(beat, subdivision, accent_on):
                kind = "accent"
            elif subdivision == 0:
                kind = "beat"
            else:
                kind = "sub"
            self.on_click(beat, subdivision, kind)
            interval = beat_interval_sec(bpm) / float(subdivisions)
            next_tick += interval
            self._wait_until(next_tick)

    def _wait_until(self, deadline: float) -> None:
        while not self._stop.is_set():
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return
            time.sleep(min(0.01, remaining))


class DropCombo(tk.Frame):
    """Closed combo shows one value; the menu lists every option."""

    def __init__(
        self,
        parent: tk.Widget,
        values: Sequence[str],
        default: str,
        command: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent, bg=COMBO_BG, highlightthickness=1, highlightbackground="#3A3A3A")
        self.values = list(values)
        self.command = command
        self.var = tk.StringVar(value=default)
        self._popup: Optional[tk.Toplevel] = None
        self._listbox: Optional[tk.Listbox] = None
        self._enabled = True

        self.display = tk.Label(
            self,
            textvariable=self.var,
            fg=COMBO_FG,
            bg=COMBO_BG,
            anchor="w",
            font=("Segoe UI", 12),
            cursor="hand2",
        )
        self.arrow = tk.Label(
            self,
            text="▾",
            fg=COMBO_FG,
            bg=COMBO_BG,
            font=("Segoe UI", 11),
            cursor="hand2",
            padx=8,
        )
        self.display.pack(side="left", fill="x", expand=True, padx=10, pady=7)
        self.arrow.pack(side="right")
        for widget in (self, self.display, self.arrow):
            widget.bind("<Button-1>", self._toggle)

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        if value not in self.values:
            self.values.append(value)
        self.var.set(value)

    def set_values(self, values: Sequence[str], selected: Optional[str] = None) -> None:
        self.close_dropdown()
        self.values = list(values)
        if not self.values:
            raise ValueError("Combo needs at least one value")
        if selected is None:
            selected = self.var.get() if self.var.get() in self.values else self.values[0]
        elif selected not in self.values:
            self.values.insert(0, selected)
        self.var.set(selected)

    def set_enabled(self, enabled: bool) -> None:
        color = COMBO_FG if enabled else MUTED
        cursor = "hand2" if enabled else "arrow"
        self.display.config(fg=color, cursor=cursor)
        self.arrow.config(fg=color, cursor=cursor)
        self._enabled = enabled

    def select(self, value: str) -> None:
        self.set(value)
        self.close_dropdown()
        if self.command:
            self.command(value)

    def dropdown_item_count(self) -> int:
        if self._listbox is None:
            return 0
        return int(self._listbox.size())

    def dropdown_values(self) -> List[str]:
        if self._listbox is None:
            return []
        return list(self._listbox.get(0, "end"))

    def open_dropdown(self) -> tk.Listbox:
        if self._popup is None:
            self._open()
        assert self._listbox is not None
        return self._listbox

    def close_dropdown(self) -> None:
        self._close()

    def _toggle(self, _event: Optional[tk.Event] = None) -> None:
        if not getattr(self, "_enabled", True):
            return
        if self._popup is not None:
            self._close()
        else:
            self._open()

    def _open(self) -> None:
        self.update_idletasks()
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.configure(bg="#3A3A3A")
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        width = max(self.winfo_width(), 160)
        popup.geometry(f"{width}x{self._menu_height()}+{x}+{y}")

        listbox = tk.Listbox(
            popup,
            bg=COMBO_BG,
            fg=COMBO_FG,
            selectbackground=ACCENT,
            selectforeground=TEXT,
            activestyle="none",
            font=("Segoe UI", 12),
            highlightthickness=0,
            bd=0,
            exportselection=False,
            height=min(len(self.values), 12),
        )
        for item in self.values:
            listbox.insert("end", item)
        current = self.get()
        if current in self.values:
            index = self.values.index(current)
            listbox.selection_set(index)
            listbox.see(index)
        listbox.pack(fill="both", expand=True)
        listbox.bind("<ButtonRelease-1>", self._choose)
        listbox.bind("<Return>", self._choose)
        popup.bind("<Escape>", lambda _e: self._close())
        listbox.focus_set()
        self._popup = popup
        self._listbox = listbox

    def _menu_height(self) -> int:
        rows = min(len(self.values), 12)
        return max(28, rows * 26 + 4)

    def _choose(self, _event: Optional[tk.Event] = None) -> None:
        if self._listbox is None:
            return
        selection = self._listbox.curselection()
        if not selection:
            return
        value = self._listbox.get(selection[0])
        self.select(str(value))

    def _close(self) -> None:
        popup = self._popup
        self._popup = None
        self._listbox = None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass


class BpmDial(tk.Frame):
    """Horizontal dial/slider for BPM 30-300. Shows the current value."""

    def __init__(
        self,
        parent: tk.Widget,
        value: int = DEFAULT_BPM,
        command: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__(parent, bg=BG)
        self.command = command
        self._syncing = False
        self.var = tk.IntVar(value=clamp_bpm(value))

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text="BPM", fg=COMBO_FG, bg=BG, font=("Segoe UI", 11, "bold")).pack(side="left")
        self.value_label = tk.Label(
            header,
            text=str(self.var.get()),
            fg=COMBO_FG,
            bg=BG,
            font=("Segoe UI", 11, "bold"),
        )
        self.value_label.pack(side="right")

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", pady=(2, 0))
        tk.Label(row, text=str(MIN_BPM), fg=MUTED, bg=BG, font=("Segoe UI", 9)).pack(side="left")
        self.scale = tk.Scale(
            row,
            from_=MIN_BPM,
            to=MAX_BPM,
            orient="horizontal",
            resolution=1,
            showvalue=0,
            variable=self.var,
            command=self._on_scale,
            bg=BG,
            fg=COMBO_FG,
            troughcolor="#3A3A3A",
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
            activebackground=ACCENT,
            length=240,
            cursor="hand2",
        )
        self.scale.pack(side="left", fill="x", expand=True, padx=6)
        tk.Label(row, text=str(MAX_BPM), fg=MUTED, bg=BG, font=("Segoe UI", 9)).pack(side="right")
        self.scale.bind("<Button-1>", self._on_body_click)
        self.scale.bind("<MouseWheel>", self._on_wheel)
        self.scale.bind("<Button-4>", self._on_wheel)
        self.scale.bind("<Button-5>", self._on_wheel)

    def get(self) -> int:
        return int(self.var.get())

    def set_bpm(self, bpm: int, notify: bool = True) -> None:
        value = clamp_bpm(bpm)
        self._syncing = True
        try:
            self.var.set(value)
            self.value_label.config(text=str(value))
        finally:
            self._syncing = False
        if notify and self.command:
            self.command(value)

    def _on_scale(self, raw: str) -> None:
        value = clamp_bpm(int(float(raw)))
        self.value_label.config(text=str(value))
        if self._syncing:
            return
        if self.command:
            self.command(value)

    def _on_body_click(self, event: tk.Event) -> Optional[str]:
        """Click trough left/right of the handle for ±1 BPM; leave handle drag alone."""
        element = self.scale.identify(event.x, event.y)
        if element == "trough1":
            self.set_bpm(self.get() - 1)
            return "break"
        if element == "trough2":
            self.set_bpm(self.get() + 1)
            return "break"
        return None

    def _on_wheel(self, event: tk.Event) -> str:
        delta = 1
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            delta = -1
        self.set_bpm(self.get() + delta)
        return "break"


SOUND_BAR_TITLES = ("1st Sound", "2nd Sound", "3rd Sound", "4th Sound")


class SoundBar(tk.Frame):
    """One loudness bar: 1st is 1:1; later sounds are N:k of the 1st."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        index: int,
        command: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        super().__init__(parent, bg=BG)
        self.index = index
        self.command = command
        self._syncing = False
        self._n = MAX_RATIO_PART
        self._locked = index == 0
        self.var = tk.IntVar(value=MAX_RATIO_PART)

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x")
        self.title_label = tk.Label(
            header,
            text=title,
            fg=COMBO_FG,
            bg=BG,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        self.title_label.pack(side="left")
        self.ratio_label = tk.Label(
            header,
            text="1:1",
            fg=COMBO_FG,
            bg=BG,
            font=("Segoe UI", 10, "bold"),
        )
        self.ratio_label.pack(side="right")

        self.scale = tk.Scale(
            self,
            from_=1,
            to=MAX_RATIO_PART,
            orient="horizontal",
            resolution=1,
            showvalue=0,
            variable=self.var,
            command=self._on_scale,
            bg=BG,
            fg=COMBO_FG,
            troughcolor="#3A3A3A",
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
            activebackground=ACCENT,
            length=260,
            cursor="hand2",
        )
        self.scale.pack(fill="x", pady=(0, 4))
        self.scale.bind("<MouseWheel>", self._on_wheel)
        self.scale.bind("<Button-4>", self._on_wheel)
        self.scale.bind("<Button-5>", self._on_wheel)

    def get(self) -> int:
        return int(self.var.get())

    def set_level(self, k: int, notify: bool = True) -> None:
        if self._locked:
            return
        value = max(1, min(self._n, int(k)))
        self._syncing = True
        try:
            self.var.set(value)
            self._refresh_label()
        finally:
            self._syncing = False
        if notify and self.command:
            self.command(self.index, value)

    def configure_bar(self, n: int, k: int, locked: bool) -> None:
        self._n = int(min(MAX_RATIO_PART, max(2, n)))
        self._locked = locked
        k = max(1, min(self._n, int(k)))
        self._syncing = True
        try:
            self.scale.config(from_=1, to=self._n, state="disabled" if locked else "normal")
            self.var.set(self._n if locked else k)
            self._refresh_label()
        finally:
            self._syncing = False

    def _refresh_label(self) -> None:
        if self._locked:
            self.ratio_label.config(text="1:1")
        else:
            self.ratio_label.config(text=f"{self._n}:{self.get()}")

    def _on_scale(self, raw: str) -> None:
        if self._locked:
            return
        value = max(1, min(self._n, int(round(float(raw)))))
        self._refresh_label()
        if self._syncing:
            return
        if self.command:
            self.command(self.index, value)

    def _on_wheel(self, event: tk.Event) -> str:
        if self._locked or str(self.scale.cget("state")) == "disabled":
            return "break"
        delta = 1
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            delta = -1
        value = max(1, min(self._n, self.get() + delta))
        self._syncing = True
        try:
            self.var.set(value)
            self._refresh_label()
        finally:
            self._syncing = False
        if self.command:
            self.command(self.index, value)
        return "break"


class MetronomeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BMP Player")
        self.root.configure(bg=BG)
        self.root.geometry("420x1000")
        self.root.minsize(380, 880)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.clicks = ClickPlayer()
        self.engine = MetronomeEngine(self._on_engine_click)
        self.tapper = TapTempo()
        self._closed = False
        self._swing_right = True
        self._beat_started = 0.0
        self._beat_span = beat_interval_sec(DEFAULT_BPM)
        self._current_beat = 1
        self._playing_visual = False
        self._anim_id: Optional[str] = None
        self._syncing_ratio = False
        self._ratio: Tuple[int, ...] = (1,)

        self._build()
        self._apply_settings()
        self._redraw_gauge()
        self._tick_animation()

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(22, 8))
        tk.Label(
            header,
            text="Metronome",
            fg=TEXT,
            bg=BG,
            font=("Segoe UI", 28, "bold"),
        ).pack()

        combos = tk.Frame(self.root, bg=BG)
        combos.pack(fill="x", padx=36, pady=(8, 4))

        self.sig_box = DropCombo(combos, TIME_SIGNATURES, "2/4", command=self._on_settings_changed)
        self.sound_box = DropCombo(combos, SOUND_PATTERNS, SOUND_PATTERNS[0], command=self._on_sound_changed)
        self.accent_box = DropCombo(combos, ACCENT_OPTIONS, "Accent On", command=self._on_settings_changed)
        self.sig_box.pack(fill="x", pady=(0, 8))
        self.sound_box.pack(fill="x", pady=(0, 8))
        self.accent_box.pack(fill="x", pady=(0, 8))

        tk.Label(combos, text="Loudness", fg=COMBO_FG, bg=BG, font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        self.ratio_box = DropCombo(combos, N_TO_ONE_RATIOS, "10:1", command=self._on_ratio_combo)
        self.ratio_box.pack(fill="x", pady=(2, 6))
        self.sound_bars_frame = tk.Frame(combos, bg=BG)
        self.sound_bars_frame.pack(fill="x", pady=(0, 8))
        self.sound_bars = [
            SoundBar(self.sound_bars_frame, title, index, command=self._on_sound_bar)
            for index, title in enumerate(SOUND_BAR_TITLES)
        ]
        self._sync_ratio_controls(reset=True)

        self.bpm_dial = BpmDial(combos, value=DEFAULT_BPM, command=self._on_bpm_dial)
        self.bpm_dial.pack(fill="x", pady=(0, 10))

        self.gauge = tk.Canvas(self.root, bg=BG, highlightthickness=0, height=320)
        self.gauge.pack(fill="both", expand=True, padx=12, pady=(4, 8))
        self.gauge.bind("<Configure>", lambda _e: self._redraw_gauge())
        self.gauge.bind("<MouseWheel>", self._on_gauge_wheel)

        bar = tk.Frame(self.root, bg=BG_RAISED, height=88)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.tap_btn = tk.Label(
            bar,
            text="TAP",
            fg=TEXT,
            bg=BG_RAISED,
            font=("Segoe UI", 16, "bold"),
            cursor="hand2",
        )
        self.tap_btn.pack(side="left", padx=28)
        self.tap_btn.bind("<Button-1>", lambda _e: self._on_tap())

        self.play_canvas = tk.Canvas(bar, width=64, height=64, bg=BG_RAISED, highlightthickness=0, cursor="hand2")
        self.play_canvas.pack(side="left", expand=True)
        self.play_canvas.bind("<Button-1>", lambda _e: self._toggle_play())

        self.beat_label = tk.Label(
            bar,
            text="1",
            fg=TEXT,
            bg=BG_RAISED,
            font=("Segoe UI", 22, "bold"),
            width=3,
        )
        self.beat_label.pack(side="right", padx=28)
        self._draw_play_button(playing=False)

    def _beats_per_measure(self) -> int:
        numerator, _denominator = parse_time_signature(self.sig_box.get())
        return numerator

    def _apply_settings(self) -> None:
        bpm = self.bpm_dial.get()
        self.engine.configure(
            bpm=bpm,
            beats_per_measure=self._beats_per_measure(),
            subdivisions=subdivisions_for_pattern(self.sound_box.get()),
            accent_on=self.accent_box.get() == "Accent On",
        )
        self._beat_span = beat_interval_sec(bpm)

    def _on_sound_changed(self, _value: str = "") -> None:
        self._sync_ratio_controls(reset=True)
        self._on_settings_changed(_value)

    def _on_ratio_combo(self, value: str) -> None:
        if self._syncing_ratio:
            return
        n = n_from_ratio_text(value)
        count = subdivisions_for_pattern(self.sound_box.get())
        self._ratio = resize_sound_levels(self._ratio, n, count)
        self._refresh_sound_bars()

    def _on_sound_bar(self, index: int, value: int) -> None:
        if self._syncing_ratio or index <= 0:
            return
        levels = list(self._ratio)
        if index >= len(levels):
            return
        n = n_from_ratio_text(self.ratio_box.get())
        levels[index] = max(1, min(n, value))
        self._ratio = tuple(levels)
        self._refresh_sound_bars()

    def _sync_ratio_controls(self, reset: bool = False) -> None:
        count = subdivisions_for_pattern(self.sound_box.get())
        selected = self.ratio_box.get() if self.ratio_box.get() in N_TO_ONE_RATIOS else "10:1"
        n = n_from_ratio_text(selected)
        if reset:
            self._ratio = default_sound_levels(n, count)
        else:
            self._ratio = resize_sound_levels(self._ratio, n, count)
        self._syncing_ratio = True
        try:
            self.ratio_box.set_values(N_TO_ONE_RATIOS, selected)
            self.ratio_box.set_enabled(count >= 2)
        finally:
            self._syncing_ratio = False
        self._refresh_sound_bars()

    def _refresh_sound_bars(self) -> None:
        count = subdivisions_for_pattern(self.sound_box.get())
        n = n_from_ratio_text(self.ratio_box.get()) if self.ratio_box.get() in N_TO_ONE_RATIOS else 10
        levels = resize_sound_levels(self._ratio, n, count)
        self._ratio = levels
        for index, bar in enumerate(self.sound_bars):
            if index < count:
                bar.configure_bar(n, levels[index], locked=(index == 0))
                if not bar.winfo_ismapped():
                    bar.pack(fill="x", pady=(0, 2))
            else:
                bar.pack_forget()

    def _on_settings_changed(self, _value: str = "") -> None:
        self._apply_settings()
        if not self.engine.playing:
            self._current_beat = 1
            self.beat_label.config(text="1")
        self._redraw_gauge()

    def _on_bpm_dial(self, bpm: int) -> None:
        self.engine.configure(bpm=bpm)
        self._beat_span = beat_interval_sec(bpm)
        self._redraw_gauge()

    def _toggle_play(self) -> None:
        if self.engine.playing:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        self._apply_settings()
        self._current_beat = 1
        self._swing_right = True
        self._beat_started = time.perf_counter()
        self._playing_visual = True
        self.engine.start()
        self._draw_play_button(playing=True)
        self.beat_label.config(text="1")
        self._redraw_gauge()

    def _stop(self) -> None:
        self.engine.stop()
        self._playing_visual = False
        self._current_beat = 1
        self._swing_right = True
        self._draw_play_button(playing=False)
        self.beat_label.config(text="1")
        self._redraw_gauge()

    def _on_tap(self) -> None:
        bpm = self.tapper.tap()
        if bpm is None:
            return
        self.bpm_dial.set_bpm(bpm)

    def _on_gauge_wheel(self, event: tk.Event) -> str:
        delta = 1
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            delta = -1
        self.bpm_dial.set_bpm(self.bpm_dial.get() + delta)
        return "break"

    def _on_engine_click(self, beat: int, subdivision: int, kind: str) -> None:
        self.clicks.play(kind, loudness_gain(self._ratio, subdivision))
        if self._closed:
            return
        try:
            self.root.after(0, lambda b=beat, s=subdivision: self._ui_click(b, s))
        except (tk.TclError, RuntimeError):
            return

    def _ui_click(self, beat: int, subdivision: int) -> None:
        if self._closed or not self.engine.playing:
            return
        if subdivision == 0:
            if beat != self._current_beat:
                self._swing_right = not self._swing_right
            self._current_beat = beat
            self._beat_started = time.perf_counter()
            self._beat_span = beat_interval_sec(self.engine.bpm)
            self.beat_label.config(text=str(beat))

    def _pendulum_progress(self) -> float:
        if not self._playing_visual:
            return 0.0
        elapsed = time.perf_counter() - self._beat_started
        t = min(1.0, max(0.0, elapsed / max(self._beat_span, 0.001)))
        eased = (1.0 - math.cos(math.pi * t)) / 2.0
        return eased if self._swing_right else 1.0 - eased

    def _gauge_geometry(self) -> Tuple[float, float, float, float, float]:
        width = max(self.gauge.winfo_width(), 300)
        height = max(self.gauge.winfo_height(), 280)
        cx = width / 2.0
        cy = height * 0.62
        radius = min(width * 0.38, height * 0.48)
        return width, height, cx, cy, radius

    def _redraw_gauge(self) -> None:
        self.gauge.delete("all")
        width, height, cx, cy, radius = self._gauge_geometry()
        pad = 8
        self.gauge.create_arc(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            start=200,
            extent=-220,
            style="arc",
            outline=ARC,
            width=4,
        )

        progress = self._pendulum_progress()
        angle = math.radians(200 - 220 * progress)
        dot_x = cx + radius * math.cos(angle)
        dot_y = cy - radius * math.sin(angle)
        r = 7
        self.gauge.create_oval(dot_x - r, dot_y - r, dot_x + r, dot_y + r, fill=ACCENT, outline=ACCENT)

        bpm_text = str(self.bpm_dial.get())
        self.gauge.create_text(cx, cy - 28, text=bpm_text, fill=TEXT, font=("Segoe UI", 56, "bold"))
        self.gauge.create_text(cx, cy + 18, text="BPM", fill=MUTED, font=("Segoe UI", 14))

        beats = self._beats_per_measure()
        spacing = 22
        total = (beats - 1) * spacing
        start_x = cx - total / 2.0
        y = min(cy + 58, height - pad - 18)
        for index in range(beats):
            x = start_x + index * spacing
            color = ACCENT if (index + 1) == self._current_beat else DOT_OFF
            self.gauge.create_oval(x - 6, y - 6, x + 6, y + 6, fill=color, outline=color)

    def _draw_play_button(self, playing: bool) -> None:
        canvas = self.play_canvas
        canvas.delete("all")
        canvas.create_oval(4, 4, 60, 60, fill=TEXT, outline=TEXT)
        if playing:
            canvas.create_rectangle(22, 20, 42, 44, fill=BG, outline=BG)
        else:
            canvas.create_polygon(24, 18, 24, 46, 46, 32, fill=BG, outline=BG)

    def _tick_animation(self) -> None:
        if self._closed:
            return
        if self._playing_visual:
            self._redraw_gauge()
        self._anim_id = self.root.after(16, self._tick_animation)

    def _on_close(self) -> None:
        self._closed = True
        if self._anim_id is not None:
            try:
                self.root.after_cancel(self._anim_id)
            except tk.TclError:
                pass
        self.engine.stop()
        self.clicks.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    MetronomeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
