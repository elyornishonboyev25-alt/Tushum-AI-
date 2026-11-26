"""Telephone teardown must precede potentially slow model socket cleanup."""

import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
from google.genai import types

from . import database, test_voice
from .voice_runtime import VoiceRuntime


class DisconnectTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_voice.VoiceTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    async def exercise(self, *, provider_end):
        call_id = self.fixture.start()
        with database.read() as c:
            call = dict(
                c.execute("SELECT * FROM voice_calls WHERE id=?", (call_id,)).fetchone()
            )
        events = asyncio.Queue()
        hung_up = asyncio.Event()
        frames = []
        last_audio_at = None
        disconnected_at = None

        class Session:
            send_realtime_input = AsyncMock()
            send_context_update = AsyncMock()
            send_tool_response = AsyncMock()

            async def send_client_content(self, **kwargs):
                await events.put(
                    types.LiveServerMessage(
                        server_content={
                            "output_transcription": {"text": "Rahmat, yaxshi qoling."},
                            "model_turn": {
                                "parts": [
                                    {
                                        "inline_data": {
                                            "data": np.full(
                                                4800, 1200, dtype="<i2"
                                            ).tobytes(),
                                            "mime_type": "audio/pcm;rate=24000",
                                        }
                                    }
                                ]
                            },
                            "generation_complete": provider_end,
                            "turn_complete": provider_end,
                        }
                    )
                )

            async def receive(self):
                while True:
                    yield await events.get()

        session = Session()
        fixture_case = self

        class Connection:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *unused):
                fixture_case.assertTrue(
                    hung_up.is_set(),
                    "Phone stayed connected until model socket cleanup",
                )
                await asyncio.sleep(0.2)  # Simulated delayed websocket handshake.

        client = NS(
            aio=NS(live=NS(connect=Mock(return_value=Connection())), aclose=AsyncMock())
        )

        class Calls:
            play = AsyncMock()
            record = AsyncMock()

            async def send_frame(self, peer, device, frame):
                nonlocal last_audio_at
                frames.append(frame)
                if any(frame):
                    last_audio_at = asyncio.get_running_loop().time()

            async def leave_call(self, peer):
                nonlocal disconnected_at
                disconnected_at = asyncio.get_running_loop().time()
                hung_up.set()

            @property
            def calls(self):
                async def inventory():
                    return {123: True}

                return inventory()

        runtime = VoiceRuntime()
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
        with patch("google.genai.Client", return_value=client):
            await asyncio.wait_for(
                runtime.converse(
                    call,
                    {
                        "api_key": "test-key",
                        "model": "gemini-3.8-live",
                        "caller": "qa_sender",
                    },
                ),
                5,
            )
        self.assertTrue(hung_up.is_set())
        # Cold native-SDK import/setup time is not goodbye latency. Measure the
        # actual last delivered audio frame -> telephone disconnect interval.
        self.assertIsNotNone(last_audio_at)
        self.assertIsNotNone(disconnected_at)
        self.assertLess(disconnected_at - last_audio_at, 0.8)
        self.assertGreaterEqual(sum(any(frame) for frame in frames), 19)
        # No finish tool was sent: a spoken goodbye alone must release the call.
        session.send_tool_response.assert_not_awaited()

    def test_spoken_goodbye_disconnects_without_waiting_for_a_finish_tool(self):
        asyncio.run(self.exercise(provider_end=True))

    def test_missing_model_end_signal_does_not_leave_telephone_connected(self):
        asyncio.run(self.exercise(provider_end=False))
