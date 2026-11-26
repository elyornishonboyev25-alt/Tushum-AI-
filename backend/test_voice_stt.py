"""Recognition boundaries: no chat completions, no silence guesses, no rewrites."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import numpy as np

from .voice_stt import AudioEvidence, RecognitionStream, transcription_config


def content(*, final=None, preview=None, agent=None):
    return NS(
        input_transcription=NS(text=final) if final is not None else None,
        interim_input_transcription=NS(text=preview) if preview is not None else None,
        output_transcription=NS(text=agent) if agent is not None else None,
        model_turn=NS(parts=[NS(text=agent)]),
    )


class RecognitionTests(unittest.TestCase):
    def stream(self):
        stream = RecognitionStream(None)
        stream.evidence.observe(np.full(4800, 600, dtype="<i2").tobytes())
        return stream

    def test_stt_has_no_prompt_ledger_or_conversation_context(self):
        cfg = transcription_config()
        self.assertEqual(cfg["response_modalities"], ["TEXT"])
        self.assertNotIn("system_instruction", cfg)
        self.assertNotIn("tools", cfg)
        self.assertNotIn("custom_vocabulary", cfg["input_audio_transcription"])
        self.assertEqual(cfg["input_audio_transcription"]["mode"], "VERBATIM")

    def test_agent_acknowledgment_cannot_become_customer_text(self):
        stream = self.stream()
        self.assertEqual(
            stream.event(content(agent="Tushundim. Ertaga to‘laysiz.")), []
        )
        self.assertEqual(stream.accepted, 0)
        text = "Aka, ikki million emas, ikki yuz ming. Sanani aytmadim."
        result = stream.event(content(final=text, agent="Tushundim"))
        self.assertEqual([(r.text, r.final) for r in result], [(text, True)])

    def test_silence_and_low_level_noise_cannot_confirm_any_words(self):
        for pcm in [
            bytes(32000),
            np.random.default_rng(4).integers(-30, 30, 16000, dtype=np.int16).tobytes(),
        ]:
            stream = RecognitionStream(None)
            stream.evidence.observe(pcm)
            self.assertEqual(stream.event(content(final="Ha, tasdiqlayman.")), [])
            self.assertEqual(stream.rejected, 1)

    def test_partial_correction_is_replaced_not_joined_or_committed(self):
        stream = self.stream()
        draft = stream.event(content(preview="Ha, ertaga ikki million."))
        self.assertFalse(draft[0].final)
        words = "Yo‘q, ertaga to‘lamayman."
        result = stream.event(content(final=words))
        self.assertEqual(result[0].text, words)
        self.assertTrue(result[0].final)
        self.assertEqual(stream.accepted, 1)

    def test_empty_final_does_not_reuse_draft(self):
        stream = self.stream()
        stream.event(content(preview="Ha, tasdiqlayman"))
        self.assertEqual(stream.event(content(final="")), [])
        self.assertEqual(stream.accepted, 0)

    def test_genuine_customer_tushundim_is_preserved_not_blacklisted(self):
        stream = self.stream()
        self.assertEqual(
            stream.event(content(final="Tushundim, lekin va’da bermayman."))[0].text,
            "Tushundim, lekin va’da bermayman.",
        )

    def test_different_turns_preserve_corrections_and_number_boundaries(self):
        stream = self.stream()
        for words in [
            "100 000 emas, 1 000 000.",
            "Не два миллиона, а двести тысяч.",
            "Keyin beraman. Sana aytmadim.",
        ]:
            stream.evidence.observe(np.full(4800, 600, dtype="<i2").tobytes())
            self.assertEqual(stream.event(content(final=words))[0].text, words)

    def test_audio_evidence_expires_and_is_single_use(self):
        evidence = AudioEvidence()
        evidence.observe(np.full(3200, 500, dtype="<i2").tobytes(), now=1)
        self.assertFalse(evidence.supported(now=17))
        self.assertTrue(evidence.consume(now=2))
        self.assertFalse(evidence.consume(now=2))

    def test_unbounded_provider_text_rejected_without_truncating_meaning(self):
        stream = self.stream()
        self.assertEqual(stream.event(content(final="x" * 8001)), [])
        self.assertEqual(stream.rejected, 1)

    def test_missing_final_requests_repeat_once_without_promoting_partial(self):
        stream = self.stream()
        stream.pending_since = 1
        self.assertFalse(stream.repair_due(now=6.9))
        self.assertTrue(stream.repair_due(now=7))
        self.assertFalse(stream.repair_due(now=20))
        self.assertEqual(stream.accepted, 0)


class StreamBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_silence_sends_no_audio_and_never_opens_a_chat_turn(self):
        session = NS(send_realtime_input=AsyncMock())
        stream = RecognitionStream(session)
        for _ in range(30):
            await stream.send(bytes(2560))
        session.send_realtime_input.assert_not_awaited()

    async def test_endpoint_flushes_once_and_next_speech_keeps_preroll(self):
        session = NS(send_realtime_input=AsyncMock())
        stream = RecognitionStream(session)
        for _ in range(3):
            await stream.send(bytes(2560))
        audio = np.full(1280, 600, dtype="<i2").tobytes()
        await stream.send(audio)
        first = session.send_realtime_input.await_args_list[0].kwargs["audio"]
        self.assertTrue(first.data.endswith(audio))
        self.assertEqual(first.mime_type, "audio/pcm;rate=16000")
        for _ in range(30):
            await stream.send(bytes(2560))
        self.assertEqual(
            sum(
                c.kwargs.get("audio_stream_end") is True
                for c in session.send_realtime_input.await_args_list
            ),
            1,
        )
        before = session.send_realtime_input.await_count
        await stream.send(audio)
        self.assertEqual(session.send_realtime_input.await_count, before + 1)
