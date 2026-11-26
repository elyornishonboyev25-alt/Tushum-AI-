"""Noise suppression, speech onset, pauses and playback-based microphone locks."""

import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
from google.genai import types

from . import database, test_voice
from .voice_input import ListeningGate, NoiseReducer, SpeechInput
from .voice_runtime import VoiceRuntime, live_config
from .voice_vad import SpeechDetector


class Detector:
    def __init__(self, probability=0.0):
        self.value = probability

    def reset(self):
        pass

    def probability(self, pcm):
        return self.value


class Passthrough:
    def reset(self):
        pass

    def process(self, pcm, probability):
        return pcm


class InputTests(unittest.TestCase):
    def setUp(self):
        self.detector = Detector()
        self.pipeline = SpeechInput(self.detector, Passthrough())
        self.now = 0.0
        self.frame = np.full(512, 1200, dtype="<i2").tobytes()

    def feed(self, probability, count):
        self.detector.value = probability
        events = []
        for _ in range(count):
            self.now += 0.032
            events.extend(self.pipeline.feed(self.frame, self.now))
        return events

    def test_noise_and_two_frame_click_never_open_a_model_turn(self):
        self.assertEqual(self.feed(0.05, 100), [])
        self.assertEqual(self.feed(0.95, 2), [])
        self.assertEqual(self.feed(0.05, 40), [])
        self.assertFalse(self.pipeline.active)

    def test_short_real_word_passes_and_keeps_pre_speech_phonemes(self):
        self.feed(0.1, 8)
        events = self.feed(0.9, 3)
        self.assertEqual([e.kind for e in events], ["start", "audio"])
        self.assertEqual(events[1].audio, self.frame * 10)

    def test_thinking_pause_keeps_correction_in_the_same_turn(self):
        events = self.feed(0.9, 5)
        events += self.feed(0.1, 25)  # 800 ms, then "emas..."
        events += self.feed(0.9, 8)
        self.assertEqual(sum(e.kind == "start" for e in events), 1)
        self.assertFalse(any(e.kind == "end" for e in events))
        self.assertEqual(self.feed(0.1, 40)[-1].kind, "end")

    def test_dtx_waits_then_flushes_partial_block_and_filter_tail_once(self):
        self.feed(0.9, 4)
        self.pipeline.feed(self.frame[:320], self.now)
        self.assertEqual(self.pipeline.idle(self.now + 1.1), [])
        events = self.pipeline.idle(self.now + 1.3)
        self.assertEqual([e.kind for e in events], ["audio", "end"])
        self.assertTrue(events[0].audio.startswith(self.frame[:320]))
        self.assertEqual(self.pipeline.idle(self.now + 3), [])

    def test_reset_discards_overlap_instead_of_replaying_it_after_ai(self):
        self.feed(0.9, 4)
        self.pipeline.reset()
        self.assertFalse(self.pipeline.active)
        self.assertEqual(self.feed(0.1, 40), [])
        events = self.feed(0.9, 3)
        self.assertEqual(events[1].audio, self.frame * 10)

    def test_configuration_uses_explicit_activity_and_disables_barge_in(self):
        config = live_config({})["realtime_input_config"]
        self.assertEqual(config["activity_handling"], "NO_INTERRUPTION")
        self.assertEqual(config["automatic_activity_detection"], {"disabled": True})

    def test_real_silero_rejects_fan_noise_hum_and_short_clicks(self):
        pipeline = SpeechInput()
        rng = np.random.default_rng(881)
        t = np.arange(16000 * 3) / 16000
        noise = rng.normal(0, 400, len(t)) + 600 * np.sin(2 * np.pi * 50 * t)
        noise[6000:6016] += 12000
        pcm = np.clip(noise, -32768, 32767).astype("<i2").tobytes()
        events = []
        for i in range(0, len(pcm) - 1023, 1024):
            events += pipeline.feed(pcm[i : i + 1024], i / 32000)
        self.assertEqual(events, [])
        # State is per call even when the shared ONNX session is cached.
        self.assertIsNot(pipeline.detector.state, SpeechDetector().state)


class NoiseTests(unittest.TestCase):
    def test_untrained_filter_preserves_waveform_with_only_16ms_delay(self):
        reducer = NoiseReducer()
        rng = np.random.default_rng(42)
        samples = rng.integers(-8000, 8000, 512 * 20, dtype=np.int16)
        output = b"".join(
            reducer.process(samples[i : i + 512].astype("<i2").tobytes(), 0.9)
            for i in range(0, len(samples), 512)
        )
        result = np.frombuffer(output, dtype="<i2")[256:]
        self.assertLessEqual(np.max(abs(result.astype(int) - samples[:-256])), 1)

    def test_stationary_noise_is_reduced_without_silencing_the_waveform(self):
        reducer = NoiseReducer()
        rng = np.random.default_rng(42)
        samples = rng.normal(0, 1000, 512 * 100).astype("<i2")
        output = b"".join(
            reducer.process(samples[i : i + 512].tobytes(), 0.05)
            for i in range(0, len(samples), 512)
        )
        result = np.frombuffer(output, dtype="<i2").astype(float)[16000:]
        reduction = 20 * np.log10(np.std(result) / np.std(samples[16000:]))
        self.assertLess(reduction, -2)
        self.assertGreater(reduction, -9)

    def test_noise_profile_freezes_during_speech_and_audio_stays_finite(self):
        reducer = NoiseReducer()
        reducer.process(np.full(512, 250, dtype="<i2").tobytes(), 0.05)
        noise = reducer.noise.copy()
        frame = np.full(512, 32767, dtype="<i2").tobytes()
        for _ in range(50):
            result = reducer.process(frame, 0.9)
            self.assertEqual(len(result), 1024)
        np.testing.assert_array_equal(reducer.noise, noise)


class ListeningTests(unittest.TestCase):
    def test_no_microphone_during_generation_buffering_or_last_playout_tail(self):
        gate = ListeningGate()
        self.assertTrue(gate.blocked(1, generating=True, drained=True))
        self.assertTrue(gate.blocked(1, generating=False, drained=False))
        gate.last_played_at = 1
        self.assertTrue(gate.blocked(1.1, generating=False, drained=True))
        self.assertFalse(gate.blocked(1.21, generating=False, drained=True))
        self.assertTrue(gate.blocked(1.3, generating=False, drained=True, closing=True))


class RuntimeListeningTests(unittest.TestCase):
    def test_overlap_is_discarded_and_microphone_reopens_after_playout(self):
        self.run_case(hesitation=False)

    def test_humming_cannot_play_a_repeated_question_and_real_speech_still_works(self):
        self.run_case(hesitation=True)

    def run_case(self, *, hesitation):
        fixture = test_voice.VoiceTests()
        fixture.setUp()
        try:
            asyncio.run(self.exercise(fixture, hesitation=hesitation))
        finally:
            fixture.tearDown()

    async def exercise(self, fixture, *, hesitation):
        call_id = fixture.start()
        with database.read() as c:
            call = dict(
                c.execute("SELECT * FROM voice_calls WHERE id=?", (call_id,)).fetchone()
            )
        events = asyncio.Queue()
        received = []
        runtime = VoiceRuntime()
        test_case = self

        async def output(text, *, complete=True):
            await events.put(
                types.LiveServerMessage(
                    server_content={
                        "output_transcription": {"text": text},
                        "model_turn": {
                            "parts": [
                                {
                                    "inline_data": {
                                        "data": np.full(
                                            12000, 1200, dtype="<i2"
                                        ).tobytes(),
                                        "mime_type": "audio/pcm;rate=24000",
                                    }
                                }
                            ]
                        },
                        "generation_complete": complete,
                        "turn_complete": complete,
                    }
                )
            )

        class Session:
            send_context_update = AsyncMock()
            send_tool_response = AsyncMock()

            async def send_client_content(self, **kwargs):
                await output("Assalomu alaykum.")

            async def send_realtime_input(self, **kwargs):
                test_case.assertFalse(runtime.input_muted)
                received.append(kwargs)
                if "activity_end" in kwargs:
                    count = sum("activity_end" in x for x in received)
                    await events.put(
                        types.LiveServerMessage(
                            server_content={
                                "input_transcription": {
                                    "text": "Хм."
                                    if hesitation and count == 1
                                    else "Alo. Yaxshi qoling."
                                },
                            }
                        )
                    )
                    await output(
                        "Nima dedingiz?"
                        if hesitation and count == 1
                        else "Rahmat, yaxshi qoling.",
                        complete=not (hesitation and count == 1),
                    )

            async def receive(self):
                while True:
                    yield await events.get()

        session = Session()

        class Connection:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *args):
                pass

        class Calls:
            play = AsyncMock()
            record = AsyncMock()
            send_frame = AsyncMock()
            leave_call = AsyncMock()

            @property
            def calls(self):
                async def inventory():
                    return {123: True}

                return inventory()

        runtime.calls = Calls()
        runtime.client = NS(
            get_entity=AsyncMock(
                return_value=NS(
                    id=123,
                    username="nishonboyv7",
                    usernames=[],
                    bot=False,
                    is_self=False,
                )
            )
        )
        client = NS(
            aio=NS(live=NS(connect=Mock(return_value=Connection())), aclose=AsyncMock())
        )

        async def caller():
            while runtime.output.drained:
                await asyncio.sleep(0.01)
            # Inject overlapping caller speech while the generated audio plays.
            for _ in range(8):
                runtime.incoming.put_nowait(bytes(2560))
                await asyncio.sleep(0.025)
            test_case.assertEqual(received, [])
            while runtime.input_muted:
                await asyncio.sleep(0.01)
            runtime.incoming.put_nowait(np.full(1536, 1200, dtype="<i2").tobytes())
            if hesitation:
                while not any("activity_end" in x for x in received):
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.2)
                runtime.incoming.put_nowait(np.full(1536, 1200, dtype="<i2").tobytes())

        pipeline = SpeechInput(Detector(0.95), Passthrough())
        with (
            patch("google.genai.Client", return_value=client),
            patch("backend.voice_runtime.SpeechInput", return_value=pipeline),
        ):
            await asyncio.wait_for(
                asyncio.gather(
                    runtime.converse(
                        call,
                        {
                            "api_key": "test",
                            "model": "gemini-3.8-live",
                            "caller": "qa_sender",
                        },
                    ),
                    caller(),
                ),
                9,
            )
        expected = 2 if hesitation else 1
        self.assertEqual(sum("activity_start" in x for x in received), expected)
        self.assertEqual(sum("activity_end" in x for x in received), expected)
        self.assertFalse(any("audio_stream_end" in x for x in received))
        runtime.calls.leave_call.assert_awaited_once()
        with database.read() as c:
            ai_text = " ".join(
                r[0]
                for r in c.execute(
                    "SELECT text FROM voice_transcript WHERE call_id=? AND speaker='ai'",
                    (call_id,),
                )
            )
        self.assertNotIn("Nima dedingiz", ai_text)
