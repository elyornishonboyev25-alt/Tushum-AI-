import asyncio
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from .voice_memory import CallMemory, MemoryPublisher, question_fields
from .voice_turns import ClosingGate

CONTEXT = {"customer": "Akmal Karimov", "balance_som": "3000000"}


class MemoryTests(unittest.TestCase):
    def test_volunteered_name_and_availability_are_remembered_without_reasking(self):
        memory = CallMemory(CONTEXT)
        words = "Ha, men Akmal Karimovman. Hozir gaplashish qulay."
        self.assertTrue(memory.customer(words))
        self.assertEqual(memory.answers["identity"], words)
        self.assertEqual(memory.answers["availability"], words)

    def test_amount_and_date_survive_side_questions_and_new_confirmation(self):
        memory = CallMemory(CONTEXT)
        memory.customer("Ikki million yuz ming so‘mni ertaga beraman.")
        memory.assistant("Shu kelishuv to‘g‘rimi?")
        memory.customer("Ha, tasdiqlayman.")
        self.assertIn("yuz ming", memory.answers["amount"])
        self.assertIn("ertaga", memory.answers["date"])

    def test_amount_is_not_forgotten_while_waiting_for_a_separate_date_answer(self):
        memory = CallMemory(CONTEXT)
        memory.customer("Besh yuz ming so‘m beraman.")
        amount = memory.answers["amount"]
        memory.assistant("Qaysi kuni to‘laysiz?")
        memory.customer("Ertaga tushdan keyin.")
        self.assertEqual(memory.answers["amount"], amount)
        self.assertEqual(memory.answers["date"], "Ertaga tushdan keyin.")

    def test_correction_replaces_the_old_number_without_erasing_identity(self):
        memory = CallMemory(CONTEXT)
        memory.customer("Men Akmal Karimovman, ertaga ikki million so‘m beraman.")
        correction = "Ikki million emas, ikki yuz ming so‘mni ertaga beraman."
        memory.customer(correction)
        self.assertEqual(memory.answers["amount"], correction)
        self.assertIn("identity", memory.answers)

    def test_a_request_to_repeat_does_not_become_an_identity_answer(self):
        memory = CallMemory(CONTEXT)
        memory.assistant("Akmal Karimov, o‘zingizmisiz?")
        memory.customer("Ha, lekin eshitmadim, qaytaring.")
        self.assertNotIn("identity", memory.answers)

    def test_payment_readback_is_not_another_request_for_the_same_amount_or_date(self):
        self.assertEqual(
            question_fields("Ertaga ikki million yuz ming so‘m berasiz. To‘g‘rimi?"),
            set(),
        )
        self.assertEqual(question_fields("Qachon to‘lash sizga qulay?"), {"date"})

    def test_memory_is_bounded_and_separate_for_each_call(self):
        first = CallMemory(CONTEXT)
        second = CallMemory(CONTEXT)
        for _ in range(20):
            first.assistant("Qachon to‘laysiz?")
        self.assertEqual(first.asked["date"], 3)
        self.assertEqual(second.snapshot()["caller_words_already_given"], {})


class PublisherTests(unittest.IsolatedAsyncioTestCase):
    async def test_fact_updates_do_not_send_a_synthetic_user_turn_or_audio(self):
        memory = CallMemory(CONTEXT)
        memory.customer("Men Akmal Karimovman. Hozir gaplashish qulay.")
        session = NS(
            send_context_update=AsyncMock(),
            send_client_content=AsyncMock(),
            send_realtime_input=AsyncMock(),
        )
        publisher = MemoryPublisher(session, CONTEXT, memory, json.dumps, ClosingGate())
        task = asyncio.create_task(publisher.run())
        try:
            publisher.changed.set()
            await asyncio.sleep(0.06)
            session.send_context_update.assert_awaited_once()
            payload = json.loads(
                session.send_context_update.await_args.kwargs["system_instruction"]
            )
            self.assertIn(
                "identity", payload["conversation_memory"]["caller_words_already_given"]
            )
            publisher.changed.set()
            await asyncio.sleep(0.06)
            session.send_context_update.assert_awaited_once()
            session.send_client_content.assert_not_awaited()
            session.send_realtime_input.assert_not_awaited()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_memory_update_failure_does_not_end_the_native_audio_call(self):
        session = NS(
            send_context_update=AsyncMock(side_effect=OSError("test disconnect"))
        )
        publisher = MemoryPublisher(
            session, CONTEXT, CallMemory(CONTEXT), json.dumps, ClosingGate()
        )
        task = asyncio.create_task(publisher.run())
        try:
            publisher.changed.set()
            await asyncio.sleep(0.06)
            self.assertTrue(publisher.disabled)
            self.assertFalse(task.done())
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
