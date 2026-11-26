"""Streaming PCM conversion and bounded playout buffering, without audio retention."""

import re
from collections import deque

import numpy as np
import soxr


class SpeechOutput:
    """24 kHz model PCM -> 48 kHz Telegram PCM, preserving packet boundaries.

    The 180 ms startup buffer absorbs network bursts. An underrun increases
    the refill target rather than repeatedly resuming on a tiny packet. soxr retains filter
    history across packets; flushing a turn keeps its final consonants intact.
    """

    frame_bytes = 960  # 10 ms, signed 16-bit little-endian mono at 48 kHz
    startup_frames = 18
    max_startup_frames = 40
    max_frames = 2000

    def __init__(self):
        self.frames = deque()
        self.reset()

    def reset(self):
        self.frames.clear()
        self.pending = b""
        self.odd_byte = b""
        self.stream = soxr.ResampleStream(
            24000, 48000, 1, dtype="float32", quality="HQ"
        )
        self.finished = False
        self.started = False
        self.has_input = False
        self.underruns = 0
        self.refill_frames = self.startup_frames
        self.last_read_was_audio = False

    @property
    def drained(self):
        return (
            not self.frames
            and not self.pending
            and (not self.has_input or self.finished)
        )

    def _append(self, data):
        data = self.pending + data
        complete = len(data) // self.frame_bytes * self.frame_bytes
        if len(self.frames) + complete // self.frame_bytes > self.max_frames:
            raise RuntimeError("audio_backlog")
        self.frames.extend(
            data[i : i + self.frame_bytes] for i in range(0, complete, self.frame_bytes)
        )
        self.pending = data[complete:]

    def write(self, data: bytes, mime_type: str = "audio/pcm;rate=24000"):
        if not data:
            return
        rate = re.search(r"rate=(\d+)", mime_type or "")
        if (
            not (mime_type or "").startswith("audio/pcm")
            or rate
            and int(rate[1]) != 24000
        ):
            raise ValueError("unsupported_audio_format")
        if self.finished:
            self.stream = soxr.ResampleStream(
                24000, 48000, 1, dtype="float32", quality="HQ"
            )
            self.finished = False
        data = self.odd_byte + data
        aligned = len(data) // 2 * 2
        self.odd_byte = data[aligned:]
        if aligned:
            self.has_input = True
            samples = np.frombuffer(data[:aligned], dtype="<i2").astype(np.float32)
            converted = self.stream.resample_chunk(samples)
            self._append(
                np.clip(np.rint(converted), -32768, 32767).astype("<i2").tobytes()
            )

    def finish(self):
        if self.finished:
            return
        if self.odd_byte:
            raise ValueError("incomplete_pcm_sample")
        if self.has_input:
            tail = self.stream.resample_chunk(np.empty(0, dtype=np.float32), last=True)
            self._append(np.clip(np.rint(tail), -32768, 32767).astype("<i2").tobytes())
        if self.pending:
            if len(self.frames) >= self.max_frames:
                raise RuntimeError("audio_backlog")
            self.frames.append(self.pending.ljust(self.frame_bytes, b"\0"))
            self.pending = b""
        self.finished = True

    def read_frame(self):
        self.last_read_was_audio = False
        if not self.started:
            if len(self.frames) >= self.refill_frames or self.finished and self.frames:
                self.started = True
            else:
                return bytes(self.frame_bytes)
        if self.frames:
            self.last_read_was_audio = True
            return self.frames.popleft()
        if not self.finished and self.has_input:
            self.underruns += 1
            self.refill_frames = min(self.max_startup_frames, self.refill_frames + 10)
        self.started = False
        return bytes(self.frame_bytes)
