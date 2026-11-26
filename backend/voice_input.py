"""Speech-only native audio, gentle noise reduction and patient turn boundaries.

No speech recognizer or text-to-speech step is used. Audio stays in bounded RAM.
The VAD sees original PCM; the model receives conservatively filtered PCM.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np

from .voice_vad import SpeechDetector


class NoiseReducer:
    """16 ms overlap/add, learning stationary noise only outside likely speech.

    Attenuation is capped at 8 dB. No learned noise means unity gain, so a quiet
    speaker is never removed merely for being quiet. Stream delay is 16 ms.
    """

    hop = 256

    def __init__(self):
        self.window = np.sqrt(np.hanning(513)[:-1]).astype(np.float32)
        self.noise = np.zeros(257, dtype=np.float32)
        self.learned = False
        self.reset()

    def reset(self):
        self.previous = np.zeros(self.hop, dtype=np.float32)
        self.overlap = np.zeros(self.hop, dtype=np.float32)
        self.gain = np.ones(257, dtype=np.float32)

    def process(self, pcm, probability):
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
        if len(samples) != 512:
            raise ValueError("vad_frame_format")
        output = []
        for chunk in (samples[:256], samples[256:]):
            analysis = np.concatenate((self.previous, chunk)) * self.window
            spectrum = np.fft.rfft(analysis)
            power = np.abs(spectrum) ** 2
            if probability < 0.15:
                if not self.learned:
                    self.noise = power.copy()
                    self.learned = True
                else:
                    self.noise = 0.96 * self.noise + 0.04 * power
            target = np.sqrt(np.maximum(0.16, 1 - self.noise / (power + 1e-6)))
            # Smooth across frequency and time to avoid metallic noise artifacts.
            target = np.convolve(
                np.pad(target, (2, 2), mode="edge"), np.ones(5) / 5, "valid"
            )
            self.gain = 0.6 * self.gain + 0.4 * target
            reconstructed = np.fft.irfft(spectrum * self.gain, n=512) * self.window
            output.append(reconstructed[:256] + self.overlap)
            self.overlap = reconstructed[256:]
            self.previous = chunk.copy()
        return (
            np.clip(np.rint(np.concatenate(output)), -32768, 32767)
            .astype("<i2")
            .tobytes()
        )


@dataclass(frozen=True)
class InputEvent:
    kind: str
    audio: bytes = b""


class SpeechInput:
    """Stream speech after 96 ms evidence, preserving 320 ms of onset context.

    Wait 1.28 s through thinking pauses, including Telegram DTX (missing silence
    packets). Clicks/noise do not open a model turn. Short words such as ha/alo
    still pass. Humming that resembles speech is handled by the native model.
    """

    frame_bytes = 1024
    frame_seconds = 0.032
    pause_seconds = 1.28
    start_frames = 3
    quiet_limit = 40

    def __init__(self, detector=None, reducer=None):
        self.detector = detector if detector is not None else SpeechDetector()
        self.reducer = reducer if reducer is not None else NoiseReducer()
        self.preroll = deque(maxlen=10)
        self.reset()

    def reset(self):
        self.pending = b""
        self.preroll.clear()
        self.active = False
        self.start_count = 0
        self.quiet_count = 0
        self.last_voiced_at = None
        self.detector.reset()
        self.reducer.reset()

    @staticmethod
    def _audio(events, audio):
        if events and events[-1].kind == "audio":
            audio = events.pop().audio + audio
        events.append(InputEvent("audio", audio))

    def feed(self, pcm, now):
        if not pcm or len(pcm) % 2:
            raise ValueError("stt_audio_format")
        self.pending += pcm
        events = []
        while len(self.pending) >= self.frame_bytes:
            frame, self.pending = self.pending[:1024], self.pending[1024:]
            probability = self.detector.probability(frame)
            filtered = self.reducer.process(frame, probability)
            if not self.active:
                self.preroll.append(filtered)
                self.start_count = self.start_count + 1 if probability >= 0.6 else 0
                if self.start_count < self.start_frames:
                    continue
                self.active = True
                self.last_voiced_at = now
                events.append(InputEvent("start"))
                self._audio(events, b"".join(self.preroll))
                self.preroll.clear()
                continue
            self._audio(events, filtered)
            if probability >= 0.35:
                self.quiet_count = 0
                self.last_voiced_at = now
            else:
                self.quiet_count += 1
            if self.quiet_count >= self.quiet_limit:
                events.append(InputEvent("end"))
                self.active = False
                self.start_count = self.quiet_count = 0
                self.last_voiced_at = None
        return events

    def idle(self, now):
        if not self.active or now - self.last_voiced_at < self.pause_seconds:
            return []
        # DTX may stop before a partial PCM block and the 16 ms filter tail.
        # Flush both before ending activity; never lose a final consonant.
        filtered = self.reducer.process(self.pending.ljust(1024, b"\0"), 0.5)
        tail = self.reducer.process(bytes(1024), 0.5)
        events = [InputEvent("audio", filtered + tail[:512]), InputEvent("end")]
        self.reset()
        return events


@dataclass
class ListeningGate:
    """Keep the microphone closed through generation, buffering and last playout."""

    last_played_at: float | None = None
    tail_seconds: float = 0.20

    def blocked(self, now, *, generating, drained, closing=False):
        return bool(
            closing
            or generating
            or not drained
            or self.last_played_at is not None
            and now - self.last_played_at < self.tail_seconds
        )
