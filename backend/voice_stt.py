"""Complete-utterance recognition, cross-checked independently of conversation.

Only caller PCM goes to the listeners: no ledger, expected numbers, names or
agent replies. No provisional words are saved. Bounded audio stays in memory.
"""

import asyncio
import logging
import time
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from google.genai.errors import APIError
from websockets.exceptions import ConnectionClosed

from .voice_evidence import agreement, word_similarity
from .voice_vad import UtteranceBuffer

STT_MODEL = "gemini-3.5-transcribe-live"
STT_REVIEW_MODEL = "gemini-3.8-live"
STT_SOURCE = "dedicated_stt_verbatim"
RECOGNITION_TIMEOUT = 18
log = logging.getLogger(__name__)


def transcription_config(*, uzbek_only=False):
    return {
        "response_modalities": ["TEXT"],
        "input_audio_transcription": {
            "mode": "VERBATIM",
            "language_codes": ["uz-UZ"] if uzbek_only else ["uz-UZ", "ru-RU"],
        },
        "realtime_input_config": {"automatic_activity_detection": {"disabled": True}},
    }


def review_config():
    # Read ONLY this session's INPUT transcription. The tiny generated reply
    # makes the native-audio turn complete; its output/audio is always ignored.
    return {
        "response_modalities": ["AUDIO"],
        "input_audio_transcription": {},
        "system_instruction": "After hearing the person, reply only with the Uzbek word Mayli.",
        "speech_config": {"language_code": "uz-UZ"},
        "realtime_input_config": {"automatic_activity_detection": {"disabled": True}},
    }


class RecognitionError(RuntimeError):
    """A safe code; provider payloads must not enter transcripts or logs."""


@dataclass(frozen=True)
class RecognizedSpeech:
    text: str
    final: bool
    generation: int = 0


class LiveListener:
    """Reuse a manual-endpointed STT connection for the whole call.

    A single worker drains each final even if its consumer was cancelled. This
    prevents a late result for an interrupted utterance becoming the NEXT turn.
    """

    def __init__(self, session):
        self.session = session
        self.results = asyncio.Queue(maxsize=16)
        self.requests = asyncio.Queue(maxsize=2)
        self.failed = False
        self.tasks = [
            asyncio.create_task(self._receive()),
            asyncio.create_task(self._work()),
        ]

    async def _receive(self):
        try:
            while True:
                async for message in self.session.receive():
                    content = message.server_content
                    final = content.input_transcription if content else None
                    if final is not None and final.finished is not False:
                        self.results.put_nowait(final.text or "")
        except Exception as exc:  # noqa: BLE001 - private provider boundary
            log.warning(
                "Recognition stream closed (%s, status=%s)",
                type(exc).__name__,
                getattr(exc, "code", None),
            )
            code = (
                "ai_quota" if getattr(exc, "code", None) == 429 else "stt_unavailable"
            )
            if not self.results.full():
                self.results.put_nowait(RecognitionError(code))
            self.failed = True

    async def _work(self):
        from google.genai import types

        while True:
            pcm, future = await self.requests.get()
            if future.cancelled():
                continue
            try:
                if self.failed:
                    raise RecognitionError("stt_unavailable")
                async with asyncio.timeout(8):
                    await self.session.send_realtime_input(
                        activity_start=types.ActivityStart()
                    )
                    for offset in range(0, len(pcm), 4096):
                        await self.session.send_realtime_input(
                            audio=types.Blob(
                                data=pcm[offset : offset + 4096],
                                mime_type="audio/pcm;rate=16000",
                            )
                        )
                        await asyncio.sleep(0.005)
                    await self.session.send_realtime_input(
                        activity_end=types.ActivityEnd()
                    )
                    result = await self.results.get()
                    if isinstance(result, Exception):
                        raise result
                if not future.done():
                    future.set_result(result)
            except Exception as exc:  # noqa: BLE001 - fail closed on an unsynchronised connection
                log.warning(
                    "Recognition utterance failed (%s, status=%s)",
                    type(exc).__name__,
                    getattr(exc, "code", None),
                )
                self.failed = True
                code = (
                    "ai_quota"
                    if getattr(exc, "code", None) == 429 or str(exc) == "ai_quota"
                    else "stt_timeout"
                    if isinstance(exc, TimeoutError)
                    else "stt_unavailable"
                )
                if not future.done():
                    future.set_exception(RecognitionError(code))

    async def decode(self, pcm):
        future = asyncio.get_running_loop().create_future()
        if self.requests.full():
            raise RecognitionError("stt_event_overflow")
        self.requests.put_nowait((pcm, future))
        return await future

    async def close(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        while not self.requests.empty():
            _, future = self.requests.get_nowait()
            future.cancel()


class ManagedListener:
    """Recover a broken connection once, replaying the same bounded audio."""

    def __init__(self, client, model, config):
        self.client, self.model, self.config = client, model, config
        self.stack = None
        self.listener = None
        self.lock = asyncio.Lock()

    async def open(self):
        stack = AsyncExitStack()
        try:
            session = await stack.enter_async_context(
                self.client.aio.live.connect(model=self.model, config=self.config)
            )
        except BaseException:
            await stack.aclose()
            raise
        self.listener = LiveListener(session)
        stack.push_async_callback(self.listener.close)
        self.stack = stack

    async def decode(self, pcm):
        async with self.lock:
            for attempt in range(2):
                if self.listener is None or self.listener.failed:
                    await self.close()
                    await self.open()
                try:
                    return await self.listener.decode(pcm)
                except RecognitionError as exc:
                    if str(exc) == "ai_quota" or attempt:
                        raise
                    await self.close()
            raise RecognitionError("stt_unavailable")

    async def close(self):
        if self.stack:
            await self.stack.aclose()
        self.stack = self.listener = None


class AudioTranscriber:
    def __init__(self, listeners=None):
        self.listeners = listeners or {}

    async def dedicated(self, pcm, *, uzbek_only=False):
        return await self.listeners[uzbek_only].decode(pcm)

    async def reviewer(self, pcm):
        return await self.listeners["review"].decode(pcm)

    async def recognize(self, pcm):
        tasks = [
            asyncio.create_task(self.dedicated(pcm)),
            asyncio.create_task(self.reviewer(pcm)),
        ]
        try:
            async with asyncio.timeout(RECOGNITION_TIMEOUT):
                primary, review = await asyncio.gather(*tasks)
                if len(primary) > 8000 or len(review) > 8000:
                    return None
                same_facts = agreement(primary, review)
                similarity = word_similarity(primary, review)
                if same_facts and similarity == 1:
                    return primary
                if not review.strip():
                    return None
                # Re-recognize the SAME complete audio with an Uzbek hint if
                # multilingual recognition disagrees. No text rewrite or ledger.
                try:
                    async with asyncio.timeout(4 if same_facts else 10):
                        retry = await self.dedicated(pcm, uzbek_only=True)
                except (TimeoutError, RecognitionError):
                    if same_facts:
                        return primary  # already cross-checked; optional spelling retry failed
                    raise
                if (
                    len(retry) <= 8000
                    and agreement(retry, review)
                    and (not same_facts or word_similarity(retry, review) > similarity)
                ):
                    return retry
                if same_facts:
                    return primary
                return None
        except TimeoutError:
            return None  # a partial result never becomes a confirmed transcript
        except RecognitionError as exc:
            if str(exc) == "stt_timeout":
                return None
            raise
        except (APIError, ConnectionClosed, OSError) as exc:
            code = (
                "ai_quota" if getattr(exc, "code", None) == 429 else "stt_unavailable"
            )
            raise RecognitionError(code) from exc
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


class RecognitionStream:
    """One in-flight utterance per call. Continuation invalidates old results."""

    def __init__(self, transcriber, *, buffer=None):
        self.transcriber = transcriber
        self.buffer = buffer if buffer is not None else UtteranceBuffer()
        self.events = asyncio.Queue(maxsize=8)
        self.accepted = self.rejected = 0
        self.generation = 0
        self.job = None
        self.jobs = set()
        self.pending_audio = None
        self.continuation_audio = b""
        self.pending_since = None
        self.repair_requested = False
        self.closed = False

    @property
    def speech_active(self):
        return self.buffer.active or self.buffer.discarding

    def _publish(self, event):
        if self.events.full():
            raise RecognitionError("stt_event_overflow")
        self.events.put_nowait(event)

    def _cancel_job(self):
        if self.job and not self.job.done():
            self.job.cancel()

    def _reject(self):
        self.rejected += 1
        self.pending_since = time.monotonic() - 6

    async def _recognize(self, pcm, generation):
        try:
            words = await self.transcriber.recognize(pcm)
            if generation != self.generation or self.closed:
                return
            if words is None or not words.strip():
                self.pending_audio = None
                self._reject()
            else:
                self._publish(RecognizedSpeech(words, True, generation))
        except RecognitionError as exc:
            if generation == self.generation and not self.closed:
                self._publish((generation, exc))
        except Exception:  # noqa: BLE001 - isolate SDK/transport errors without payloads
            if generation == self.generation and not self.closed:
                self._publish((generation, RecognitionError("stt_unavailable")))

    def _submit(self, audio):
        audio = self.continuation_audio + audio
        self.continuation_audio = b""
        if len(audio) > self.buffer.max_bytes:
            self.pending_audio = None
            self._reject()
            return
        self.pending_audio = audio
        self.job = asyncio.create_task(self._recognize(audio, self.generation))
        self.jobs.add(self.job)
        self.job.add_done_callback(self.jobs.discard)

    async def send(self, pcm):
        if self.closed:
            return
        try:
            events = self.buffer.feed(pcm)
        except ValueError as exc:
            raise RecognitionError("stt_audio_format") from exc
        for boundary in events:
            if boundary.kind == "start":
                self.generation += 1
                self._cancel_job()
                # A continuation during decoding replays the uncommitted words
                # with the new speech, so a late 'emas' cannot be ignored.
                if self.pending_audio:
                    self.continuation_audio = self.pending_audio
                self.pending_audio = None
                self.pending_since = None
                self.repair_requested = False
                self._publish(RecognizedSpeech("", False, self.generation))
            elif boundary.kind == "too_long":
                self.pending_audio = None
                self.continuation_audio = b""
                self._cancel_job()
                self._reject()
            elif boundary.kind == "end":
                self._submit(boundary.audio)
        if (
            len(self.continuation_audio) + len(self.buffer.audio)
            > self.buffer.max_bytes
        ):
            self.continuation_audio = b""
            self.buffer.clear()
            self.buffer.discarding = True
            self._reject()

    async def receive(self):
        while True:
            event = await self.events.get()
            if isinstance(event, tuple):
                generation, error = event
                if generation == self.generation:
                    raise error
                continue
            if event.generation != self.generation:
                continue
            if event.final:
                self.pending_audio = None
                self.pending_since = None
                self.accepted += 1
            yield event

    def repair_due(self, now=None):
        now = time.monotonic() if now is None else now
        if self.pending_since is None or self.repair_requested or self.speech_active:
            return False
        if now - self.pending_since < 6:
            return False
        self.repair_requested = True
        return True

    async def finish(self):
        boundary = self.buffer.finish()
        if boundary:
            self._submit(boundary.audio)
        if self.job:
            await self.job
        await asyncio.sleep(0)  # let the still-running receiver flush the final

    async def close(self):
        self.closed = True
        for job in list(self.jobs):
            job.cancel()
        await asyncio.gather(*self.jobs, return_exceptions=True)
        self.pending_audio = None
        self.continuation_audio = b""
        self.buffer.clear()
        self.buffer.pending = self.buffer.preroll = b""
        while not self.events.empty():
            self.events.get_nowait()


@asynccontextmanager
async def open_recognition(client):
    try:
        buffer = await asyncio.to_thread(UtteranceBuffer)
    except (ImportError, OSError, RuntimeError) as exc:
        raise RecognitionError("stt_unavailable") from exc
    async with AsyncExitStack() as stack:
        listeners = {}
        try:
            for key, model, config in (
                (False, STT_MODEL, transcription_config()),
                (True, STT_MODEL, transcription_config(uzbek_only=True)),
                ("review", STT_REVIEW_MODEL, review_config()),
            ):
                listener = ManagedListener(client, model, config)
                if key is not True:
                    await listener.open()
                stack.push_async_callback(listener.close)
                listeners[key] = listener
        except (APIError, ConnectionClosed, OSError, TimeoutError) as exc:
            code = (
                "ai_quota" if getattr(exc, "code", None) == 429 else "stt_unavailable"
            )
            raise RecognitionError(code) from exc
        recognizer = RecognitionStream(AudioTranscriber(listeners), buffer=buffer)
        try:
            yield recognizer
        finally:
            await recognizer.close()
