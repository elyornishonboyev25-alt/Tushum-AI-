"""Recognition must preserve complete statements and reject contradictory evidence."""

import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import numpy as np

from .voice_evidence import agreement, number_values
from .voice_stt import (
    AudioTranscriber,
    LiveListener,
    ManagedListener,
    RecognitionError,
    RecognitionStream,
    transcription_config,
)
from .voice_vad import SpeechDetector, UtteranceBuffer


class Detector:
    def probability(self, pcm):
        return 0.95 if np.any(np.frombuffer(pcm, dtype="<i2")) else 0.01


def voice_frames(count=8):
    return np.full(512 * count, 600, dtype="<i2").tobytes()


class EvidenceTests(unittest.TestCase):
    def test_formatting_and_word_numbers_do_not_change_financial_value(self):
        for words, expected in [
            ("ikki million yuz ming", [2100000]),
            ("2 million 100 ming", [2100000]),
            ("2.100.000", [2100000]),
            ("2 100 000", [2100000]),
            ("два миллиона сто тысяч", [2100000]),
            ("bir yarim million", [1500000]),
            ("полтора миллиона", [1500000]),
            ("Не 2 млн, а 200.000 сумов.", [2000000, 200000]),
            ("0 so‘m", [0]),
            ("yigirma yettinchi kuni", [27]),
        ]:
            with self.subTest(words=words):
                self.assertEqual(number_values(words), expected)

    def test_agreement_does_not_infer_money_date_or_confirmation(self):
        self.assertTrue(
            agreement(
                "Ertaga ikki million yuz ming so‘m beraman.",
                "Ertaga 2 100 000 so'm beraman.",
            )
        )
        self.assertTrue(
            agreement("Ha, to‘g‘ri, tasdiqlayman.", "Ha to'g'ri tasdiqlayman.")
        )
        for left, right in [
            ("Ertaga 2100000 so‘m beraman.", "Ertaga 2000000 so‘m beraman."),
            ("Men ertaga to‘lamayman.", "Men ertaga to‘layman."),
            ("Ha, tasdiqlayman.", "Yo‘q, tasdiqlamayman."),
            ("Balki ertaga beraman.", "Ertaga beraman."),
            ("Ertaga beraman.", "Bugun beraman."),
            ("Hozir pulim yo‘q.", "Tushundim."),
            ("Ikkida beraman.", "Ikki daqiqa beraman."),
            ("Ha, tasdiqlayman.", "Ha, tasdiqlayman?"),
            ("", "Ha, tasdiqlayman."),
        ]:
            with self.subTest(left=left):
                self.assertFalse(agreement(left, right))

    def test_dedicated_recognition_receives_no_ledger_or_chat_prompt(self):
        config = transcription_config()
        self.assertEqual(config["input_audio_transcription"]["mode"], "VERBATIM")
        self.assertEqual(
            config["input_audio_transcription"]["language_codes"], ["uz-UZ", "ru-RU"]
        )
        self.assertNotIn("system_instruction", config)
        self.assertNotIn("tools", config)


class UtteranceTests(unittest.TestCase):
    def buffer(self):
        return UtteranceBuffer(Detector())

    def test_sentence_with_natural_pause_and_correction_is_one_utterance(self):
        buffer = self.buffer()
        first, second = voice_frames(), voice_frames(6)
        silence = bytes(1024 * 25)  # 800 ms, less than the endpoint
        events = buffer.feed(first + silence + second)
        self.assertEqual([event.kind for event in events], ["start"])
        final = buffer.feed(bytes(1024 * 40))
        self.assertEqual([event.kind for event in final], ["end"])
        self.assertIn(first + silence + second, final[0].audio)
        self.assertFalse(buffer.active)

    def test_arbitrary_even_packet_sizes_preserve_original_samples(self):
        buffer = self.buffer()
        original = voice_frames(9)
        events = []
        for offset in range(0, len(original), 122):
            events.extend(buffer.feed(original[offset : offset + 122]))
        final = buffer.finish()
        self.assertEqual(final.audio, original)
        self.assertEqual([event.kind for event in events], ["start"])

    def test_silence_does_not_open_an_utterance(self):
        buffer = self.buffer()
        self.assertEqual(buffer.feed(bytes(32000 * 4)), [])
        self.assertIsNone(buffer.finish())
        self.assertLessEqual(len(buffer.preroll), 10240)

    def test_long_audio_is_rejected_without_unbounded_memory(self):
        buffer = self.buffer()
        events = buffer.feed(voice_frames(1000))
        self.assertIn("too_long", [event.kind for event in events])
        self.assertLessEqual(len(buffer.audio), buffer.max_bytes)

    def test_real_neural_detector_rejects_silence_and_white_noise(self):
        detector = SpeechDetector()
        rng = np.random.default_rng(8)
        scores = []
        for _ in range(60):
            scores.append(detector.probability(bytes(1024)))
        for _ in range(60):
            scores.append(
                detector.probability(
                    rng.integers(-2000, 2000, 512, dtype=np.int16).tobytes()
                )
            )
        self.assertLess(max(scores), 0.5)


class TranscriberTests(unittest.IsolatedAsyncioTestCase):
    async def test_connection_failure_replays_same_audio_once_without_text_fallback(
        self,
    ):
        managed = ManagedListener(None, "test", {})
        first = NS(
            failed=False, decode=AsyncMock(side_effect=RecognitionError("stt_timeout"))
        )
        recovered = NS(
            failed=False,
            decode=AsyncMock(return_value="Ikki yuz ming emas, besh yuz ming."),
        )
        managed.listener = first

        async def close():
            managed.listener = None

        async def reopen():
            managed.listener = recovered

        managed.close = AsyncMock(side_effect=close)
        managed.open = AsyncMock(side_effect=reopen)
        pcm = voice_frames()
        self.assertIn("besh yuz ming", await managed.decode(pcm))
        first.decode.assert_awaited_once_with(pcm)
        recovered.decode.assert_awaited_once_with(pcm)
        managed.open.assert_awaited_once()

    async def test_quota_failure_is_not_retried_as_a_new_listener(self):
        managed = ManagedListener(None, "test", {})
        managed.listener = NS(
            failed=False, decode=AsyncMock(side_effect=RecognitionError("ai_quota"))
        )
        managed.open = AsyncMock()
        with self.assertRaisesRegex(RecognitionError, "ai_quota"):
            await managed.decode(voice_frames())
        managed.open.assert_not_awaited()

    async def test_cancelled_utterance_final_cannot_be_attached_to_next_utterance(self):
        queue = asyncio.Queue()

        class Session:
            send_realtime_input = AsyncMock()

            async def receive(self):
                while True:
                    yield await queue.get()

        session = Session()
        listener = LiveListener(session)

        async def wait_end(count):
            async with asyncio.timeout(2):
                while (
                    sum(
                        "activity_end" in call.kwargs
                        for call in session.send_realtime_input.await_args_list
                    )
                    < count
                ):
                    await asyncio.sleep(0.005)

        first = asyncio.create_task(listener.decode(voice_frames()))
        second = None
        try:
            await wait_end(1)
            first.cancel()
            await asyncio.gather(first, return_exceptions=True)
            second = asyncio.create_task(listener.decode(voice_frames()))
            await queue.put(
                NS(
                    server_content=NS(
                        input_transcription=NS(text="Ha, tasdiqlayman.", finished=None)
                    )
                )
            )
            await wait_end(2)
            await queue.put(
                NS(
                    server_content=NS(
                        input_transcription=NS(
                            text="Yo‘q, va’da bermayman.", finished=None
                        )
                    )
                )
            )
            self.assertEqual(
                await asyncio.wait_for(second, 2), "Yo‘q, va’da bermayman."
            )
        finally:
            if second is not None:
                second.cancel()
                await asyncio.gather(second, return_exceptions=True)
            await listener.close()

    async def test_review_listener_ignores_generated_acknowledgment(self):
        queue = asyncio.Queue()

        class Session:
            async def receive(self):
                while True:
                    yield await queue.get()

        listener = LiveListener(Session())
        try:
            await queue.put(
                NS(
                    server_content=NS(
                        input_transcription=None,
                        output_transcription=NS(text="Tushundim"),
                        model_turn=NS(parts=[NS(text="Tushundim")]),
                    )
                )
            )
            await asyncio.sleep(0)
            self.assertTrue(listener.results.empty())
            exact = "Hali va’da bermadim."
            await queue.put(
                NS(server_content=NS(input_transcription=NS(text=exact, finished=None)))
            )
            self.assertEqual(await asyncio.wait_for(listener.results.get(), 1), exact)
        finally:
            await listener.close()

    async def test_both_listeners_must_agree_before_customer_text_is_committed(self):
        transcriber = AudioTranscriber(None)
        transcriber.dedicated = AsyncMock(return_value="Ertaga 2100000 so‘m beraman.")
        transcriber.reviewer = AsyncMock(return_value="Ertaga 2000000 so‘m beraman.")
        self.assertIsNone(await transcriber.recognize(voice_frames()))
        self.assertEqual(transcriber.dedicated.await_count, 2)

    async def test_audio_is_redecoded_instead_of_rewriting_mixed_language_words(self):
        transcriber = AudioTranscriber(None)
        exact = "Aka, davayte tak, ertaga 500000 so‘m to‘layman, ostalnoye potom."
        transcriber.dedicated = AsyncMock(
            side_effect=["Аке, 500000 сум төлеймін.", exact]
        )
        transcriber.reviewer = AsyncMock(return_value=exact)
        self.assertEqual(await transcriber.recognize(voice_frames()), exact)
        calls = transcriber.dedicated.await_args_list
        self.assertEqual(calls[0].args[0], calls[1].args[0])
        self.assertTrue(calls[1].kwargs["uzbek_only"])

    async def test_genuine_customer_acknowledgment_is_preserved(self):
        transcriber = AudioTranscriber(None)
        words = "Tushundim, lekin va’da bermayman."
        transcriber.dedicated = AsyncMock(return_value=words)
        transcriber.reviewer = AsyncMock(return_value=words)
        self.assertEqual(await transcriber.recognize(voice_frames()), words)

    async def test_spelling_disagreement_redecodes_audio_instead_of_editing_text(self):
        transcriber = AudioTranscriber(None)
        exact = "Pul tushsa, harakat qilaman. Hozircha va’da bermayman."
        transcriber.dedicated = AsyncMock(
            side_effect=[exact.replace("Pul", "Pult"), exact]
        )
        transcriber.reviewer = AsyncMock(return_value=exact)
        self.assertEqual(await transcriber.recognize(voice_frames()), exact)
        calls = transcriber.dedicated.await_args_list
        self.assertEqual(calls[0].args[0], calls[1].args[0])

    async def test_no_model_can_fill_an_empty_recognition(self):
        transcriber = AudioTranscriber(None)
        transcriber.dedicated = AsyncMock(return_value="Ha, tasdiqlayman.")
        transcriber.reviewer = AsyncMock(return_value="")
        self.assertIsNone(await transcriber.recognize(voice_frames()))


class RecognitionFlowTests(unittest.IsolatedAsyncioTestCase):
    def stream(self, result="Hozir va’da bermayman."):
        return RecognitionStream(
            NS(recognize=AsyncMock(return_value=result)),
            buffer=UtteranceBuffer(Detector()),
        )

    async def test_final_is_once_only_after_complete_utterance(self):
        stream = self.stream()
        try:
            await stream.send(voice_frames())
            stream.transcriber.recognize.assert_not_awaited()
            self.assertFalse((await anext(stream.receive())).final)
            await stream.send(bytes(1024 * 40))
            await stream.finish()
            final = await anext(stream.receive())
            self.assertTrue(final.final)
            self.assertEqual(final.text, "Hozir va’da bermayman.")
            self.assertEqual(stream.accepted, 1)
        finally:
            await stream.close()

    async def test_disagreement_requests_repeat_without_saving_preview(self):
        stream = self.stream(result=None)
        try:
            await stream.send(voice_frames() + bytes(1024 * 40))
            await stream.finish()
            self.assertTrue(stream.repair_due())
            self.assertFalse(stream.repair_due())
            self.assertEqual(stream.accepted, 0)
            self.assertEqual(stream.rejected, 1)
        finally:
            await stream.close()

    async def test_provider_failure_reaches_receiver_instead_of_hanging(self):
        stream = self.stream()
        stream.transcriber.recognize.side_effect = RecognitionError("stt_unavailable")
        try:
            await stream.send(voice_frames() + bytes(1024 * 40))
            await stream.finish()
            receiver = stream.receive()
            self.assertFalse((await anext(receiver)).final)
            with self.assertRaises(RecognitionError):
                await anext(receiver)
        finally:
            await stream.close()

    async def test_continuation_cancels_stale_result_and_keeps_both_phrases(self):
        stream = self.stream()
        never = asyncio.Event()
        calls = []

        async def decode(audio):
            calls.append(audio)
            if len(calls) == 1:
                await never.wait()
                return "Ertaga to‘layman."
            return "Ertaga to‘layman demadim, pulim yo‘q."

        stream.transcriber.recognize = decode
        try:
            first = voice_frames()
            await stream.send(first + bytes(1024 * 40))
            await asyncio.sleep(0)
            await stream.send(voice_frames(6))
            await stream.send(bytes(1024 * 40))
            await stream.finish()
            self.assertIn(first, calls[1])
            receiver = stream.receive()
            start = await anext(receiver)
            self.assertFalse(start.final)
            final = await anext(receiver)
            self.assertIn("demadim", final.text)
            self.assertEqual(stream.accepted, 1)
        finally:
            await stream.close()
        self.assertIsNone(stream.pending_audio)
        self.assertFalse(stream.buffer.audio)
