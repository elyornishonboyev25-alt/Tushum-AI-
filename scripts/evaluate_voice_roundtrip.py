"""Synthetic PCM conversation through real Gemini + isolated accounting tools.

No Telegram session is used; the existing database and accounts are untouched.
"""

import argparse
import asyncio
import json
import os
import sys
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import numpy as np
import soxr
from fastapi.testclient import TestClient
from google import genai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import voice
from backend.main import app
from scripts.evaluate_voice_quality import synthesize, wav_bytes


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("GEMINI_API_KEY")
    if args.credentials:
        key = json.loads(Path(args.credentials).read_text(encoding="utf-8"))["api_key"]
    ai = genai.Client(api_key=key, http_options={"api_version": "v1beta"})
    texts = (
        [
            "Давайте по-русски. Да, я Акмал Каримов. Сейчас удобно говорить.",
            "Завтра после обеда два миллиона сто тысяч сумов переведу.",
            "Не расслышал сумму. Пожалуйста повторите по-русски.",
            "Да, всё правильно, подтверждаю.",
        ]
        if args.language == "ru"
        else [
            "Ha, men Akmal Karimovman. Hozir gaplashish qulay.",
            "Ertaga tushdan keyin ikki million yuz ming so‘m beraman.",
            "Eshitmay qoldim, iltimos kelishuvni qaytarib ayting.",
            "Ha, to‘g‘ri, tasdiqlayman.",
        ]
    )
    inputs = []
    for i, text in enumerate(texts):
        variant = "-language-request" if args.language == "ru" and i in (0, 2) else ""
        path = out / f"roundtrip-{args.language}-input-{i}{variant}.wav"
        if path.exists():
            with wave.open(str(path), "rb") as w:
                pcm = w.readframes(w.getnframes())
        else:
            pcm, _ = await synthesize(ai, text, "Aoede")
            path.write_bytes(wav_bytes(pcm))
        inputs.append(
            soxr.resample(
                np.frombuffer(pcm, dtype="<i2").astype(np.float32), 24000, 16000
            )
            .astype("<i2")
            .tobytes()
        )
    with TemporaryDirectory() as tmp:
        os.environ.update(
            TUSHUM_DATABASE=tmp + "/qa.db",
            TUSHUM_VOICE_LOCAL="0",
            TUSHUM_TELEGRAM_SESSION="",
            TUSHUM_VOICE_OWNER_PHONE="",
            TUSHUM_VOICE_BUSINESS_ID="",
            TUSHUM_VOICE_TARGETS="voice_quality_test",
            TUSHUM_VOICE_SETUP_CODE="isolated-voice-quality-code",
        )
        with TestClient(app) as http:
            auth = http.post(
                "/api/auth/register",
                json={
                    "name": "QA owner",
                    "business_name": "Baraka Savdo",
                    "phone": "+998901234567",
                    "password": "QualityTest12345",
                },
            ).json()

            def headers():
                return {
                    "Authorization": "Bearer " + auth["token"],
                    "X-Operation-Id": str(uuid4()),
                }

            def post(path, payload):
                r = http.post(path, json=payload, headers=headers())
                r.raise_for_status()
                return r.json()

            post("/api/voice/activate", {"code": "isolated-voice-quality-code"})
            http.put(
                "/api/voice/profile",
                json={
                    "business_name": "Baraka Savdo",
                    "manager_name": "QA owner",
                    "phone": "+998901234567",
                },
                headers=headers(),
            ).raise_for_status()
            customer = post(
                "/api/customers", {"name": "Akmal Karimov", "phone": "+998901111111"}
            )["id"]
            day = voice.today()
            debt = post(
                "/api/debts",
                {
                    "customer_id": customer,
                    "title": "Sinov nasiya",
                    "amount": "3000000",
                    "issued_on": day,
                    "due_on": day,
                },
            )["id"]
            voice.runtime["ready"] = True
            call = post(
                "/api/voice/calls",
                {"debt_id": debt, "target": "voice_quality_test", "consent": True},
            )["id"]
            voice.change_status(call, "connected")
            # Only the Telegram transport is simulated. Run the REAL voice
            # runtime, recognizers, reply guard, playout and accounting tools.
            from types import SimpleNamespace
            from unittest.mock import AsyncMock

            from backend import database
            from backend.voice_reply import uzbek_reply
            from backend.voice_runtime import VoiceRuntime

            runtime = VoiceRuntime()
            runtime.client = SimpleNamespace(
                get_entity=AsyncMock(
                    return_value=SimpleNamespace(
                        id=987654321,
                        username="voice_quality_test",
                        usernames=[],
                        bot=False,
                        is_self=False,
                    )
                )
            )
            recorded = asyncio.Event()
            inventory = {987654321: True}
            source = asyncio.Queue()
            played = bytearray()

            class Transport:
                async def play(self, *unused):
                    return None

                async def record(self, *unused):
                    recorded.set()

                async def send_frame(self, peer, device, frame):
                    played.extend(frame)

                async def leave_call(self, peer):
                    inventory.clear()

                @property
                def calls(self):
                    async def current():
                        return inventory

                    return current()

            runtime.calls = Transport()

            def snapshot():
                with database.read() as conn:
                    row = dict(
                        conn.execute(
                            "SELECT * FROM voice_calls WHERE id=?", (call,)
                        ).fetchone()
                    )
                    rows = [
                        dict(r)
                        for r in conn.execute(
                            "SELECT * FROM voice_transcript WHERE call_id=? ORDER BY seq",
                            (call,),
                        )
                    ]
                return row, rows

            async def feed():
                await recorded.wait()
                while True:
                    if not source.empty():
                        await runtime.incoming.put(source.get_nowait())
                    await asyncio.sleep(0.08)

            async def wait_reply(previous, require_proposal=False):
                quiet_at = None
                async with asyncio.timeout(60):
                    while True:
                        row, rows = snapshot()
                        if row["status"] in ("failed", "no_answer", "cancelled"):
                            raise AssertionError("Runtime failed: " + row["error_code"])
                        replies = [
                            r for r in rows if r["speaker"] == "ai" and r["is_final"]
                        ]
                        latest = replies[-1]["seq"] if replies else 0
                        proposal = json.loads(row["proposal_json"] or "{}")
                        eligible = latest > previous and runtime.output.drained
                        if require_proposal:
                            eligible = (
                                eligible
                                and bool(proposal)
                                and latest > proposal.get("after_seq", 0)
                            )
                        if eligible:
                            if quiet_at is None:
                                quiet_at = asyncio.get_running_loop().time()
                            if asyncio.get_running_loop().time() - quiet_at >= 0.4:
                                return latest
                        else:
                            quiet_at = None
                        await asyncio.sleep(0.05)

            async def speak():
                previous = 0
                for index, pcm in enumerate(inputs):
                    previous = await wait_reply(previous, require_proposal=index == 2)
                    for offset in range(0, len(pcm), 2560):
                        source.put_nowait(
                            pcm[offset : offset + 2560].ljust(2560, b"\0")
                        )
                    # wait_reply must not reuse the preceding AI turn while the
                    # caller audio is queued/in flight.
                    while not source.empty():
                        await asyncio.sleep(0.05)

            with database.read() as conn:
                queued = dict(
                    conn.execute(
                        "SELECT * FROM voice_calls WHERE id=?", (call,)
                    ).fetchone()
                )
            voice.change_status(call, "queued")
            config = {
                "api_key": key,
                "model": "gemini-3.8-live",
                "caller": "isolated_qa_caller",
            }
            sender = asyncio.create_task(feed())
            speaker = asyncio.create_task(speak())
            bridge = asyncio.create_task(runtime.converse(queued, config))
            try:
                async with asyncio.timeout(240):
                    done, _ = await asyncio.wait(
                        [speaker, bridge], return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        await task
                    if bridge in done and not speaker.done():
                        row, _ = snapshot()
                        raise AssertionError("Bridge ended early: " + row["error_code"])
                    await speaker
                    await bridge
            finally:
                for task in (speaker, sender, bridge):
                    task.cancel()
                await asyncio.gather(speaker, sender, bridge, return_exceptions=True)
                row, history = snapshot()
                (out / f"roundtrip-{args.language}-history.json").write_text(
                    json.dumps(
                        {
                            "call_status": row["status"],
                            "error_code": row["error_code"],
                            "outcome": row["outcome"],
                            "transcript": history,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                (out / f"roundtrip-{args.language}-played.wav").write_bytes(
                    wav_bytes(bytes(played), 48000)
                )
            replies = [r["text"] for r in history if r["speaker"] == "ai"]
            assert replies and all(uzbek_reply(t) for t in replies), replies
            data = http.get("/api/workspace", headers=headers()).json()
            promises = data["promises"]
            assert len(promises) == 1 and promises[0]["amount"] == 210000000, promises
            assert data["payments"] == []
            print(
                "PASS: one confirmed 2 100 000 UZS promise; no payment or Telegram call.",
                flush=True,
            )
            voice.runtime["ready"] = False
    await ai.aio.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials")
    parser.add_argument("--out", default="backend/data/voice-evaluation")
    parser.add_argument("--language", choices=["uz", "ru"], default="uz")
    asyncio.run(run(parser.parse_args()))
