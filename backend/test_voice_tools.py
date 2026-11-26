import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

from .voice_tools import LiveTools


class LiveToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_late_caption_retries_evidence_once_without_blocking_audio_receiver(
        self,
    ):
        sequence = 0
        execute = Mock(
            side_effect=[{"error_code": "amount_required"}, {"proposal_id": "draft"}]
        )
        sent = asyncio.Event()

        async def respond(results):
            self.assertEqual(results[0][1], {"proposal_id": "draft"})
            sent.set()

        worker = LiveTools(execute, respond, Mock(), lambda: sequence)
        task = asyncio.create_task(worker.run())
        try:
            worker.submit([NS(id="1", name="propose_promise", args={})])
            await asyncio.sleep(0.01)
            sequence = 1
            worker.caption()
            await asyncio.wait_for(sent.wait(), 1)
            self.assertEqual(execute.call_count, 2)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_cancellation_prevents_queued_action_and_response(self):
        execute = Mock()
        respond = AsyncMock()
        worker = LiveTools(execute, respond, Mock(), lambda: 0)
        worker.submit([NS(id="1", name="confirm_promise", args={})])
        worker.cancel(["1"])
        task = asyncio.create_task(worker.run())
        try:
            await asyncio.sleep(0.02)
            execute.assert_not_called()
            respond.assert_not_awaited()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_cancellation_during_caption_wait_never_confirms(self):
        execute = Mock(return_value={"error_code": "confirmation_required"})
        respond = AsyncMock()
        worker = LiveTools(execute, respond, Mock(), lambda: 0)
        task = asyncio.create_task(worker.run())
        try:
            worker.submit([NS(id="1", name="confirm_promise", args={})])
            await asyncio.sleep(0.01)
            worker.cancel(["1"])
            worker.caption()
            await asyncio.sleep(0.02)
            execute.assert_called_once()
            respond.assert_not_awaited()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_no_caption_does_not_retry_or_fabricate_evidence(self):
        execute = Mock(return_value={"error_code": "amount_required"})
        sent = asyncio.Event()

        async def respond(results):
            self.assertEqual(results[0][1]["error_code"], "amount_required")
            sent.set()

        worker = LiveTools(execute, respond, Mock(), lambda: 0, grace=0.02)
        task = asyncio.create_task(worker.run())
        try:
            worker.submit([NS(id="1", name="propose_promise", args={})])
            await asyncio.wait_for(sent.wait(), 1)
            execute.assert_called_once()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
