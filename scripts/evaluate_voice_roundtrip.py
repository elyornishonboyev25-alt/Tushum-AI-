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
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import voice
from backend.main import app
from backend.voice_runtime import live_config
from backend.voice_transcription import CustomerTranscription
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
            "Да, я Акмал Каримов. Сейчас удобно говорить.",
            "Завтра после обеда два миллиона сто тысяч сумов переведу.",
            "Не расслышал, пожалуйста повторите условия.",
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
        path = out / f"roundtrip-{args.language}-input-{i}.wav"
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
            context = {
                "business": "Baraka Savdo",
                "customer": "Akmal Karimov",
                "today": day,
                "timezone": "Asia/Tashkent",
                "balance_som": "3000000.00",
                "available_promise_som": "3000000.00",
            }
            history = []
            recognition = CustomerTranscription()
            queue = asyncio.Queue()
            done = asyncio.Event()
            spoken = ""
            turn = 0
            audio = []
            async with ai.aio.live.connect(
                model="gemini-3.8-live", config=live_config(context)
            ) as session:

                async def feed():
                    while True:
                        data = queue.get_nowait() if not queue.empty() else bytes(2560)
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=data, mime_type="audio/pcm;rate=16000"
                            )
                        )
                        await asyncio.sleep(0.08)

                async def receive():
                    nonlocal spoken, turn
                    while True:
                        async for event in session.receive():
                            c = event.server_content
                            if c:
                                item = c.input_transcription
                                if item and item.text:
                                    index, words, final = recognition.accept(
                                        item.text, item.finished
                                    )
                                    voice.transcript(
                                        call, f"user-{index}", "customer", words, final
                                    )
                                    history.append({"customer": words, "final": final})
                                    print(
                                        json.dumps(
                                            {"customer": words, "final": final},
                                            ensure_ascii=True,
                                        ),
                                        flush=True,
                                    )
                                if (
                                    c.output_transcription
                                    and c.output_transcription.text
                                ):
                                    spoken += c.output_transcription.text
                                    voice.transcript(call, f"ai-{turn}", "ai", spoken)
                                for part in c.model_turn.parts if c.model_turn else []:
                                    if part.inline_data and part.inline_data.data:
                                        audio.append(part.inline_data.data)
                                if c.turn_complete:
                                    if spoken:
                                        voice.transcript(
                                            call, f"ai-{turn}", "ai", spoken, True
                                        )
                                        history.append({"ai": spoken})
                                        print(
                                            json.dumps(
                                                {"ai": spoken}, ensure_ascii=True
                                            ),
                                            flush=True,
                                        )
                                    if audio:
                                        (
                                            out
                                            / f"roundtrip-{args.language}-reply-{turn}.wav"
                                        ).write_bytes(wav_bytes(b"".join(audio)))
                                    audio.clear()
                                    spoken = ""
                                    turn += 1
                                    done.set()
                            if event.tool_call:
                                responses = []
                                for tool in event.tool_call.function_calls:
                                    result = voice.execute_tool(
                                        call, tool.name, dict(tool.args or {})
                                    )
                                    history.append(
                                        {"tool": tool.name, "result": result}
                                    )
                                    print(
                                        json.dumps(
                                            {"tool": tool.name, "result": result},
                                            ensure_ascii=True,
                                        ),
                                        flush=True,
                                    )
                                    responses.append(
                                        types.FunctionResponse(
                                            id=tool.id, name=tool.name, response=result
                                        )
                                    )
                                await session.send_tool_response(
                                    function_responses=responses
                                )

                receiver = asyncio.create_task(receive())
                sender = asyncio.create_task(feed())

                async def wait_reply():
                    wait = asyncio.create_task(done.wait())
                    try:
                        finished, _ = await asyncio.wait(
                            [receiver, wait],
                            timeout=45,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if receiver in finished:
                            await receiver
                        if not finished:
                            raise TimeoutError("No complete AI reply")
                    finally:
                        wait.cancel()
                        await asyncio.gather(wait, return_exceptions=True)

                try:
                    await session.send_client_content(
                        turns={
                            "role": "user",
                            "parts": [
                                {
                                    "text": "Qo‘ng‘iroq ulandi. Hozir faqat Assalomu alaykum deng, keyin tinglang."
                                }
                            ],
                        },
                        turn_complete=True,
                    )
                    await wait_reply()
                    for pcm in inputs:
                        done.clear()
                        for offset in range(0, len(pcm), 2560):
                            queue.put_nowait(
                                pcm[offset : offset + 2560].ljust(2560, b"\0")
                            )
                        await wait_reply()
                        await asyncio.sleep(0.5)
                finally:
                    receiver.cancel()
                    sender.cancel()
                    await asyncio.gather(receiver, sender, return_exceptions=True)
                    (out / f"roundtrip-{args.language}-history.json").write_text(
                        json.dumps(history, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
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
