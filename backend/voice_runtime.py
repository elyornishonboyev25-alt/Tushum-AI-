"""Full-duplex Telegram PCM ↔ Gemini Live bridge. No audio files are retained."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import time
from contextlib import suppress
from pathlib import Path

from . import database, voice
from .voice_audio import SpeechOutput
from .voice_policy import TOOLS, instructions
from .voice_transcription import CustomerTranscription
from .voice_turns import ClosingGate, OpeningGate

log = logging.getLogger(__name__)


def configuration():
    config = {
        "api_id": os.getenv("TELEGRAM_API_ID"),
        "api_hash": os.getenv("TELEGRAM_API_HASH"),
        "session": os.getenv("TUSHUM_TELEGRAM_SESSION"),
        "api_key": os.getenv("GEMINI_API_KEY"),
        "model": os.getenv("TUSHUM_VOICE_MODEL", "gemini-3.8-live"),
        "caller": os.getenv("TUSHUM_VOICE_CALLER", "nishonboyev7"),
    }
    if os.getenv("TUSHUM_VOICE_LOCAL") == "1":
        private = Path(__file__).parent / "data" / "telegram"
        telegram = json.loads(
            (private / "credentials.json").read_text(encoding="utf-8-sig")
        )
        gemini = json.loads((private / "gemini.json").read_text(encoding="utf-8-sig"))
        config.update(
            api_id=telegram["api_id"],
            api_hash=telegram["api_hash"],
            session=str(private / "caller.session"),
            api_key=gemini["api_key"],
            local=True,
        )
    return (
        config
        if all(config.get(k) for k in ("api_id", "api_hash", "session", "api_key"))
        else None
    )


def live_config(context, model="gemini-3.8-live", *, voice_name=None):
    tools = copy.deepcopy(TOOLS)
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": instructions(context),
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name or os.getenv("TUSHUM_VOICE_NAME", "Kore")
                }
            }
        },
        "input_audio_transcription": {
            "language_codes": ["uz-UZ", "ru-RU"],
            "custom_vocabulary": [
                "Tushum AI",
                "nasiya",
                "so‘m",
                "qarzdorlik",
                "to‘lov",
                "va’da",
                "muddat",
                "tasdiqlayman",
                "bo‘lib to‘lash",
                "qayta qo‘ng‘iroq",
                "задолженность",
                "оплата",
                "рассрочка",
                "подтверждаю",
                "сум",
                str(context.get("business", ""))[:120],
                str(context.get("customer", ""))[:100],
            ],
        },
        "output_audio_transcription": {},
        "tools": tools,
        "realtime_input_config": {
            "automatic_activity_detection": {
                "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH",
                "end_of_speech_sensitivity": "END_SENSITIVITY_LOW",
                "prefix_padding_ms": 320,
                "silence_duration_ms": 900,
            }
        },
    }
    if "extended-thinking" in model:
        config["thinking_config"] = {"thinking_level": "low"}
        for tool in tools[0]["function_declarations"]:
            tool["behavior"] = "NON_BLOCKING"
    return config


def resolved_target_matches(peer, target):
    if getattr(peer, "bot", False):
        return False
    names = [getattr(peer, "username", None)]
    names.extend(
        getattr(alias, "username", None)
        for alias in getattr(peer, "usernames", None) or []
        if getattr(alias, "active", False)
    )
    return target.lower() in {name.lower() for name in names if name}


class VoiceRuntime:
    def __init__(self):
        self.task = None
        self.client = None
        self.calls = None
        self.active_peer = None
        self.incoming = asyncio.Queue(maxsize=80)
        self.output = SpeechOutput()
        self.input_overflow = False

    async def start(self):
        self.incoming = asyncio.Queue(maxsize=80)
        # Calls interrupted by a process restart are never automatically redialled.
        with database.write() as c:
            c.execute(
                "UPDATE voice_calls SET status='failed',error_code='server_restarted',ended_at=?,updated_at=? "
                "WHERE status IN ('queued','dialing','connected')",
                (voice.now(), voice.now()),
            )
        if configuration():
            self.task = asyncio.create_task(self.supervise(), name="tushum-voice")

    async def supervise(self):
        while True:
            try:
                await self.run()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - optional native SDK boundary
                voice.runtime.update(ready=False, state="telegram_unavailable")
                log.warning("Voice worker failed (%s)", type(exc).__name__)
            if voice.runtime["state"] in ("telegram_login_required", "caller_mismatch"):
                return
            await asyncio.sleep(30)

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def run(self):
        from pytgcalls import PyTgCalls, filters
        from pytgcalls.types import Direction, StreamFrames
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        config = configuration()
        session = (
            config["session"]
            if config.get("local")
            else StringSession(config["session"])
        )
        self.client = TelegramClient(
            session,
            int(config["api_id"]),
            config["api_hash"],
            device_model="Tushum AI Voice",
            flood_sleep_threshold=0,
        )
        voice.runtime.update(state="connecting", model=config["model"])
        try:
            await asyncio.wait_for(self.client.connect(), 30)
            if not await self.client.is_user_authorized():
                voice.runtime.update(state="telegram_login_required")
                return
            me = await self.client.get_me()
            if (me.username or "").lower() != config["caller"].lower() or me.bot:
                voice.runtime.update(state="caller_mismatch")
                return
            self.calls = PyTgCalls(self.client)

            @self.calls.on_update(filters.stream_frame(directions=Direction.INCOMING))
            async def receive_audio(_, update: StreamFrames):
                if update.chat_id != self.active_peer:
                    return
                for frame in update.frames:
                    if self.incoming.full():
                        self.input_overflow = True
                        return
                    self.incoming.put_nowait(frame.frame)

            await self.calls.start()
            voice.runtime.update(ready=True, state="ready", caller="@" + me.username)
            while True:
                with database.read() as c:
                    row = c.execute(
                        "SELECT * FROM voice_calls WHERE status='queued' ORDER BY created_at LIMIT 1"
                    ).fetchone()
                if row:
                    await self.converse(dict(row), config)
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - provider boundary must not stop the HTTP app
            voice.runtime.update(state="telegram_unavailable")
            log.warning("Voice runtime unavailable (%s)", type(exc).__name__)
        finally:
            voice.runtime["ready"] = False
            if self.active_peer and self.calls:
                with suppress(Exception):
                    await self.calls.leave_call(self.active_peer)
            await self.client.disconnect()

    async def converse(self, call, config):
        from google import genai
        from google.genai import types
        from pytgcalls.types import (
            CallConfig,
            Device,
            ExternalMedia,
            MediaStream,
            RecordStream,
        )
        from pytgcalls.types.raw import AudioParameters

        call_id = call["id"]
        if call["cancel_requested"]:
            voice.change_status(call_id, "cancelled")
            return
        with database.read() as c:
            actor = c.execute(
                "SELECT * FROM users WHERE id=? AND active=1 AND role IN ('owner','manager')",
                (call["user_id"],),
            ).fetchone()
            customer = c.execute(
                "SELECT * FROM customers WHERE id=? AND business_id=?",
                (call["customer_id"], call["business_id"]),
            ).fetchone()
            debt = c.execute(
                "SELECT * FROM debts WHERE id=? AND business_id=?",
                (call["debt_id"], call["business_id"]),
            ).fetchone()
            if (
                not actor
                or not customer
                or not customer["contact_allowed"]
                or customer["archived"]
                or not debt
                or debt["archived"]
                or debt["amount"] <= voice.debt_paid(c, debt["id"])
                or not voice.enabled_for(c, call["business_id"])
            ):
                voice.change_status(call_id, "failed", error_code="permission_changed")
                return
            _, fresh_context = voice.context_for(c, dict(actor), dict(debt))
        call["context_json"] = json.dumps(fresh_context, ensure_ascii=False)
        voice.change_status(call_id, "dialing")
        self.output.reset()
        self.input_overflow = False
        while not self.incoming.empty():
            self.incoming.get_nowait()
        stop = asyncio.Event()
        finish = asyncio.Event()
        state = {
            "user": "",
            "ai": "",
            "user_index": 0,
            "ai_index": 0,
            "turn": 0,
            "first_audio": False,
            "finish_at": None,
        }
        tasks = []
        opening = OpeningGate()
        closing = ClosingGate()
        customer_transcription = CustomerTranscription()
        ai = genai.Client(
            api_key=config["api_key"], http_options={"api_version": "v1beta"}
        )
        try:
            peer = await self.client.get_entity(call["target"])
            if (
                getattr(peer, "is_self", False)
                or (getattr(peer, "username", "") or "").lower()
                == config["caller"].lower()
            ):
                raise ValueError("self_call")
            # Resolve the username immediately before dialling and retain this exact peer.
            with database.read() as c:
                permitted = voice.target_allowed(c, call["business_id"], call["target"])
            if not resolved_target_matches(peer, call["target"]) or not permitted:
                raise ValueError("target_mismatch")
            self.active_peer = peer.id
            async with ai.aio.live.connect(
                model=config["model"],
                config=live_config(json.loads(call["context_json"]), config["model"]),
            ) as live:
                dial = asyncio.create_task(
                    self.calls.play(
                        peer.id,
                        MediaStream(
                            ExternalMedia.AUDIO,
                            audio_parameters=AudioParameters(48000, 1),
                        ),
                        CallConfig(timeout=40),
                    )
                )
                dial_started = time.monotonic()
                # Cancellation also applies while the receiving phone is ringing.
                while not dial.done():
                    with database.read() as c:
                        cancelled = c.execute(
                            "SELECT cancel_requested FROM voice_calls WHERE id=?",
                            (call_id,),
                        ).fetchone()[0]
                    if cancelled:
                        dial.cancel()
                        with suppress(asyncio.CancelledError, Exception):
                            await dial
                        voice.change_status(call_id, "cancelled")
                        return
                    if time.monotonic() - dial_started > 55:
                        dial.cancel()
                        with suppress(asyncio.CancelledError, Exception):
                            await dial
                        raise TimeoutError("telegram_connection_timeout")
                    await asyncio.sleep(0.2)
                await dial
                await self.calls.record(
                    peer.id,
                    RecordStream(
                        audio=True, audio_parameters=AudioParameters(16000, 1)
                    ),
                )
                voice.change_status(call_id, "connected")
                connected_at = time.monotonic()

                def flush(who):
                    if who == "user":
                        # Output audio/tool messages do not make an interim user
                        # hypothesis final. Input and output arrive independently.
                        return
                    content = state[who]
                    if content:
                        voice.transcript(
                            call_id,
                            f"{who}-{state[who + '_index']}",
                            "customer" if who == "user" else "ai",
                            content,
                            True,
                        )
                        state[who] = ""
                        state[who + "_index"] += 1

                async def send_input():
                    while True:
                        data = await self.incoming.get()
                        if self.input_overflow:
                            raise RuntimeError("audio_input_overflow")
                        await live.send_realtime_input(
                            audio=types.Blob(
                                data=data, mime_type="audio/pcm;rate=16000"
                            )
                        )

                async def play_output():
                    next_tick = time.monotonic()
                    while True:
                        frame = self.output.read_frame()
                        is_generated_audio = self.output.last_read_was_audio
                        await self.calls.send_frame(peer.id, Device.MICROPHONE, frame)
                        if is_generated_audio and not state["first_audio"]:
                            state["first_audio"] = True
                            voice.change_status(
                                call_id,
                                "connected",
                                latency=int((time.monotonic() - connected_at) * 1000),
                            )
                        next_tick += 0.01
                        await asyncio.sleep(max(0, next_tick - time.monotonic()))
                        if time.monotonic() - next_tick > 0.15:
                            next_tick = time.monotonic()

                async def receive_model():
                    while True:
                        async for message in live.receive():
                            content = message.server_content
                            if content:
                                if content.interrupted:
                                    self.output.reset()
                                    flush("ai")
                                    state["turn"] += 1
                                if (
                                    content.interim_input_transcription
                                    and content.interim_input_transcription.text
                                ):
                                    opening.recipient_answered = True
                                    index, words, final = (
                                        customer_transcription.preview(
                                            content.interim_input_transcription.text
                                        )
                                    )
                                    voice.transcript(
                                        call_id,
                                        f"user-{index}",
                                        "customer",
                                        words,
                                        final,
                                    )
                                if (
                                    content.input_transcription
                                    and content.input_transcription.text
                                ):
                                    opening.recipient_answered = True
                                    index, words, final = customer_transcription.accept(
                                        content.input_transcription.text,
                                        content.input_transcription.finished,
                                    )
                                    voice.transcript(
                                        call_id,
                                        f"user-{index}",
                                        "customer",
                                        words,
                                        final,
                                    )
                                if (
                                    content.output_transcription
                                    and content.output_transcription.text
                                ):
                                    flush("user")
                                    state["ai"] += content.output_transcription.text
                                    voice.transcript(
                                        call_id,
                                        f"ai-{state['ai_index']}",
                                        "ai",
                                        state["ai"],
                                    )
                                if content.model_turn:
                                    flush("user")
                                    for part in content.model_turn.parts or []:
                                        if part.inline_data and part.inline_data.data:
                                            closing.output()
                                            self.output.write(
                                                part.inline_data.data,
                                                part.inline_data.mime_type
                                                or "audio/pcm;rate=24000",
                                            )
                                if content.generation_complete:
                                    # Audio generation can finish before the full
                                    # interaction: release the final filter samples now.
                                    self.output.finish()
                                if content.turn_complete:
                                    flush("user")
                                    flush("ai")
                                    self.output.finish()
                                    state["turn"] += 1
                                    opening.greeting_complete = True
                                    if closing.requested_at is not None:
                                        closing.turn_complete = True
                            if message.tool_call:
                                flush("user")
                                flush("ai")
                                responses = []
                                for tool in message.tool_call.function_calls:
                                    result = voice.execute_tool(
                                        call_id, tool.name, dict(tool.args or {})
                                    )
                                    responses.append(
                                        types.FunctionResponse(
                                            id=tool.id, name=tool.name, response=result
                                        )
                                    )
                                    if result.get("finish"):
                                        finish.set()
                                        state["finish_at"] = time.monotonic()
                                        # Gemini may say goodbye immediately before
                                        # the tool or after its response. Support both.
                                        with database.read() as c:
                                            last_ai = c.execute(
                                                "SELECT text FROM voice_transcript WHERE call_id=? AND speaker='ai' ORDER BY seq DESC LIMIT 1",
                                                (call_id,),
                                            ).fetchone()
                                        farewell = (
                                            last_ai[0] if last_ai else ""
                                        ).casefold()
                                        closing.request(
                                            time.monotonic(),
                                            any(
                                                word in farewell
                                                for word in (
                                                    "yaxshi qoling",
                                                    "xayr",
                                                    "salomat bo",
                                                    "до свидания",
                                                    "всего доброго",
                                                    "хорошего дня",
                                                )
                                            ),
                                        )
                                await live.send_tool_response(
                                    function_responses=responses
                                )

                async def monitor():
                    while time.monotonic() - connected_at < 300:
                        with database.read() as c:
                            row = c.execute(
                                "SELECT cancel_requested FROM voice_calls WHERE id=?",
                                (call_id,),
                            ).fetchone()
                        if row[0]:
                            voice.change_status(call_id, "cancelled")
                            stop.set()
                            return
                        drained = self.output.drained
                        if closing.ready(time.monotonic(), drained):
                            stop.set()
                            return
                        if (
                            opening.introduction_due(time.monotonic(), drained)
                            and not finish.is_set()
                        ):
                            await live.send_client_content(
                                turns={
                                    "role": "user",
                                    "parts": [
                                        {
                                            "text": "Salomlashuvdan keyingi kutish tugadi. Endi o‘zingizni biznes nomi va AI yordamchi ekaningiz bilan bir marta tanishtiring. Mijozning kimligini aniqlang. Qarz summasini hozircha aytmang."
                                        }
                                    ],
                                },
                                turn_complete=True,
                            )
                        # Remote hangups are detected by the native call inventory.
                        if peer.id not in await self.calls.calls:
                            stop.set()
                            return
                        await asyncio.sleep(0.25)
                    stop.set()

                tasks = [
                    asyncio.create_task(f())
                    for f in (send_input, play_output, receive_model, monitor)
                ]
                tasks.append(asyncio.create_task(stop.wait()))
                await live.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [
                            {
                                "text": "Qo‘ng‘iroq ulandi. Hozir FAQAT ‘Assalomu alaykum.’ deng. Boshqa hech narsa qo‘shmang. Keyin tinglang; mijoz javob bersa keyingi navbatda tanishtirasiz, sukut bo‘lsa serverdan keyingi ishorani kuting."
                            }
                        ],
                    },
                    turn_complete=True,
                )
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    if not task.cancelled() and task.exception():
                        raise task.exception()
                flush("user")
                flush("ai")
                voice.change_status(call_id, "completed")
        except asyncio.CancelledError:
            voice.change_status(call_id, "failed", error_code="server_stopped")
            raise
        except Exception as exc:  # noqa: BLE001 - isolate a failed provider call from the queue
            name = type(exc).__name__
            code = (
                "no_answer"
                if name in ("TimedOutAnswer", "CallDeclined", "CallDiscarded")
                else "connection_failed"
            )
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                code = "ai_quota"
            elif "403" in str(exc) or "401" in str(exc):
                code = "ai_access"
            elif (
                name in ("UsernameNotOccupiedError", "UsernameInvalidError")
                or isinstance(exc, ValueError)
                and str(exc) == "target_mismatch"
            ):
                code = "target_unavailable"
            elif name in (
                "UserPrivacyRestrictedError",
                "UserIsBlockedError",
                "UserNotMutualContactError",
            ):
                code = "telegram_privacy"
            elif isinstance(exc, ValueError) and str(exc) == "self_call":
                code = "self_call"
            elif str(exc) in (
                "audio_input_overflow",
                "audio_backlog",
                "unsupported_audio_format",
                "incomplete_pcm_sample",
            ):
                code = "audio_quality"
            voice.change_status(
                call_id,
                "no_answer" if code == "no_answer" else "failed",
                error_code=code,
            )
            log.warning("Voice call ended with code %s (%s)", code, name)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if self.active_peer:
                with suppress(Exception):
                    await self.calls.leave_call(self.active_peer)
            self.active_peer = None
            await ai.aio.aclose()


manager = VoiceRuntime()
