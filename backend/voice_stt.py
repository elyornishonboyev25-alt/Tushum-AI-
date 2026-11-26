"""Audio-only recognition, isolated from the conversational model and ledger.

No system prompt, chat history, customer name or expected amount is sent to STT.
Only committed VERBATIM input_transcription events become customer utterances.
"""

import asyncio
import time
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

import numpy as np
from google.genai.errors import APIError
from websockets.exceptions import ConnectionClosed

STT_MODEL = "gemini-3.5-transcribe-live"
STT_SOURCE = "dedicated_stt_verbatim"


def transcription_config():
    return {
        "response_modalities": ["TEXT"],
        "input_audio_transcription": {
            "mode": "VERBATIM",
            "language_codes": ["uz-UZ", "ru-RU"],
        },
        "realtime_input_config": {
            "automatic_activity_detection": {
                "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH",
                "end_of_speech_sensitivity": "END_SENSITIVITY_LOW",
                "prefix_padding_ms": 320,
                "silence_duration_ms": 900,
            },
        },
    }


class RecognitionError(RuntimeError):
    """A safe code; provider error payloads must not enter transcripts/logs."""


@dataclass(frozen=True)
class RecognizedSpeech:
    text: str
    final: bool


class AudioEvidence:
    """Reject unsolicited text over silence; this is not semantic confidence.

    Quiet or very brief audio is left unconfirmed, never replaced with a guess.
    This lightweight signal check is additional to the provider's speech VAD.
    """

    def __init__(self):
        self.voiced_seconds = 0.0
        self.last_voice_at = None

    def observe(self, pcm: bytes, now: float | None = None):
        if not pcm or len(pcm) % 2:
            raise RecognitionError("stt_audio_format")
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
        rms = float(np.sqrt(np.mean(samples * samples)))
        if rms >= 120:  # about -49 dBFS; never amplifies/mutates the audio
            self.voiced_seconds = min(30.0, self.voiced_seconds + len(samples) / 16000)
            self.last_voice_at = time.monotonic() if now is None else now
            return True
        return False

    def supported(self, now: float | None = None):
        now = time.monotonic() if now is None else now
        return (
            self.last_voice_at is not None
            and now - self.last_voice_at < 15
            and self.voiced_seconds >= 0.12
        )

    def consume(self, now: float | None = None):
        supported = self.supported(now)
        self.voiced_seconds = 0.0
        self.last_voice_at = None
        return supported


class RecognitionStream:
    def __init__(self, session):
        self.session = session
        self.evidence = AudioEvidence()
        self.accepted = 0
        self.rejected = 0
        self.finalized = asyncio.Event()
        self.sent_audio = False
        self.speech_active = False
        self.silence_seconds = 0.0
        self.preroll = b""
        self.pending_since = None
        self.repair_requested = False

    async def send(self, pcm: bytes):
        from google.genai import types

        voiced = self.evidence.observe(pcm)
        if not self.speech_active:
            self.preroll = (self.preroll + pcm)[-10240:]  # 320 ms at 16 kHz
            if not voiced:
                return
            pcm = self.preroll
            self.preroll = b""
            self.speech_active = True
            self.repair_requested = False
        self.silence_seconds = (
            0.0 if voiced else self.silence_seconds + len(pcm) / 32000
        )
        self.sent_audio = True
        try:
            await self.session.send_realtime_input(
                audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000")
            )
        except (APIError, ConnectionClosed, OSError, TimeoutError) as exc:
            raise RecognitionError("stt_unavailable") from exc
        if self.silence_seconds >= 1.0:
            # Explicitly finalize after a real pause; continuous Telegram silence
            # must not keep a caller's complete sentence provisional indefinitely.
            self.pending_since = time.monotonic()
            await self.session.send_realtime_input(audio_stream_end=True)
            self.speech_active = False
            self.silence_seconds = 0.0

    def event(self, content):
        """Ignore model_turn/output_transcription: they are never caller speech."""
        if content is None:
            return []
        result = []
        committed = content.input_transcription
        provisional = content.interim_input_transcription
        if committed is not None:
            self.pending_since = None
            words = committed.text or ""
            # Empty final clears the current hypothesis; do not reuse a preview.
            if words.strip():
                if len(words) <= 8000 and self.evidence.consume():
                    self.accepted += 1
                    result.append(RecognizedSpeech(words, True))
                else:
                    self.rejected += 1
                    self.pending_since = time.monotonic()
            elif self.evidence.supported():
                self.rejected += 1
                self.pending_since = time.monotonic()
            self.finalized.set()
        elif provisional is not None and provisional.text and self.evidence.supported():
            result.append(RecognizedSpeech(provisional.text, False))
        return result

    def repair_due(self, now: float | None = None):
        now = time.monotonic() if now is None else now
        if self.pending_since is None or self.repair_requested or self.speech_active:
            return False
        if now - self.pending_since < 6:
            return False
        self.repair_requested = True
        return True

    async def receive(self):
        try:
            while True:
                async for event in self.session.receive():
                    for speech in self.event(event.server_content):
                        yield speech
        except (APIError, ConnectionClosed, OSError, TimeoutError) as exc:
            raise RecognitionError("stt_unavailable") from exc

    async def finish(self):
        if not self.sent_audio or not self.evidence.supported():
            return
        self.finalized.clear()
        await self.session.send_realtime_input(audio_stream_end=True)
        try:
            await asyncio.wait_for(self.finalized.wait(), 5)
        except TimeoutError:
            # A remaining provisional hypothesis is deliberately not promoted.
            self.rejected += 1


@asynccontextmanager
async def open_recognition(client):
    async with AsyncExitStack() as stack:
        try:
            session = await stack.enter_async_context(
                client.aio.live.connect(model=STT_MODEL, config=transcription_config())
            )
        except (APIError, ConnectionClosed, OSError, TimeoutError) as exc:
            raise RecognitionError("stt_unavailable") from exc
        yield RecognitionStream(session)
