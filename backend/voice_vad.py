"""CPU speech detection and complete utterances, with no audio files or DSP edits."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np


@lru_cache(maxsize=1)
def _session():
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.inter_op_num_threads = 1
    options.intra_op_num_threads = 1
    return ort.InferenceSession(
        str(Path(__file__).parent / "models" / "silero_vad.onnx"),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )


class SpeechDetector:
    """Silero's 16 kHz ONNX interface. Recurrent state belongs to ONE call."""

    def __init__(self):
        self.session = _session()
        self.reset()

    def reset(self):
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)

    def probability(self, pcm):
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)[None, :] / 32768
        if samples.shape != (1, 512):
            raise ValueError("vad_frame_format")
        audio = np.concatenate((self.context, samples), axis=1)
        output, self.state = self.session.run(
            None,
            {
                "input": audio,
                "state": self.state,
                "sr": np.array(16000, dtype=np.int64),
            },
        )
        self.context = audio[:, -64:].copy()
        return float(output[0, 0])


@dataclass(frozen=True)
class SpeechBoundary:
    kind: str
    audio: bytes = b""


class UtteranceBuffer:
    """32 ms frames, 320 ms preroll and 1.28 s pause tolerance.

    A pause shorter than the endpoint keeps corrections and complete numbers in
    one utterance. The returned bytes are the ORIGINAL PCM, not denoised speech.
    Silence/noise without speech never starts recognition. At most 30 s retained.
    """

    frame_bytes = 1024
    max_bytes = 30 * 32000

    def __init__(self, detector=None):
        self.detector = detector if detector is not None else SpeechDetector()
        self.pending = b""
        self.preroll = b""
        self.audio = bytearray()
        self.active = False
        self.start_frames = 0
        self.quiet_frames = 0
        self.voiced_frames = 0
        self.discarding = False

    def feed(self, pcm):
        if not pcm or len(pcm) % 2:
            raise ValueError("stt_audio_format")
        self.pending += pcm
        events = []
        while len(self.pending) >= self.frame_bytes:
            frame, self.pending = self.pending[:1024], self.pending[1024:]
            probability = self.detector.probability(frame)
            if self.discarding:
                self.quiet_frames = self.quiet_frames + 1 if probability < 0.35 else 0
                if self.quiet_frames >= 40:
                    self.discarding = False
                    self.quiet_frames = 0
                continue
            if not self.active:
                self.preroll = (self.preroll + frame)[-10240:]
                self.start_frames = self.start_frames + 1 if probability >= 0.5 else 0
                if self.start_frames < 2:
                    continue
                self.active = True
                self.voiced_frames = self.start_frames
                self.audio = bytearray(self.preroll)
                self.preroll = b""
                self.quiet_frames = 0
                events.append(SpeechBoundary("start"))
                continue
            self.audio.extend(frame)
            if probability >= 0.35:
                self.quiet_frames = 0
                self.voiced_frames += 1
            else:
                self.quiet_frames += 1
            if len(self.audio) > self.max_bytes:
                self.clear()
                self.discarding = True
                events.append(SpeechBoundary("too_long"))
            elif self.quiet_frames >= 40:
                # Keep 320 ms after speech rather than transmitting the entire
                # endpoint wait. Never trim the first or last voiced phonemes.
                trim = max(0, self.quiet_frames - 10) * self.frame_bytes
                audio = bytes(self.audio[:-trim] if trim else self.audio)
                self.clear()
                events.append(SpeechBoundary("end", audio))
        return events

    def clear(self):
        self.audio.clear()
        self.active = False
        self.start_frames = self.quiet_frames = self.voiced_frames = 0

    def finish(self):
        if not self.active:
            return None
        # Include remaining genuine bytes, then release the bounded memory.
        audio = bytes(self.audio) + self.pending
        self.pending = b""
        self.clear()
        return SpeechBoundary("end", audio)
