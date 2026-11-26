"""Real API voice/ASR regression samples. No Telegram connection or ledger writes.

Run with GEMINI_API_KEY, or --credentials pointing to an ignored local JSON file.
Audio is synthetic test material; it does not measure real-speaker accuracy.
"""

import argparse
import asyncio
import io
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import soxr
from google import genai
from google.genai import types
from google.genai.errors import APIError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.voice_stt import open_recognition

SCRIPT = (
    "Assalomu alaykum. Men Baraka Savdoning Tushum AI yordamchisiman. "
    "Hisobda ikki million yuz ming so‘m qolgan ekan. Qachon to‘lash sizga qulay? "
    "Хорошо, можем по-русски. Осталось два миллиона сто тысяч сумов. "
    "В какой день вам удобно оплатить?"
)
CASES = [
    (
        "uz",
        "Aka, hozir pulim yo‘q, lekin ertaga tushdan keyin ikki million yuz ming so‘m beraman.",
    ),
    (
        "ru",
        "Сейчас денег нет, но завтра после обеда переведу два миллиона сто тысяч сумов.",
    ),
    (
        "mixed",
        "Aka, давайте так, ertaga besh yuz ming so‘m to‘layman, остальное потом.",
    ),
    ("uz-negation", "Men ertaga to‘lamayman. Hozir va’da bera olmayman."),
    ("ru-correction", "Не два миллиона, а двести тысяч сумов. Дату пока не обещаю."),
    ("uz-ambiguous", "Ikkida beraman, lekin summani hali aytmadim."),
]


def wav_bytes(pcm, rate=24000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(pcm)
    return buffer.getvalue()


async def synthesize(client, text, voice):
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": (
            "Read only the supplied script verbatim, with the relaxed, connected speech "
            "of a fluent native Uzbek/Russian bilingual in Uzbekistan. Use natural Uzbek "
            "word stress and clear q, x, o‘, g‘; use fluent Russian in Russian phrases. "
            "A conversational colleague, not an announcer. No introduction or commentary."
        ),
        "speech_config": {
            "voice_config": {"prebuilt_voice_config": {"voice_name": voice}}
        },
        "output_audio_transcription": {},
    }
    chunks = []
    transcript = ""
    first = None
    start = time.monotonic()
    async with client.aio.live.connect(
        model="gemini-3.8-live", config=config
    ) as session:
        await session.send_client_content(
            turns={
                "role": "user",
                "parts": [
                    {
                        "text": "Read this ENTIRE script verbatim in both languages, not a conversational answer: "
                        + text
                    }
                ],
            },
            turn_complete=True,
        )
        async with asyncio.timeout(70):
            async for response in session.receive():
                content = response.server_content
                if not content:
                    continue
                if content.output_transcription:
                    transcript += content.output_transcription.text or ""
                if content.model_turn:
                    for part in content.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            if first is None:
                                first = round(time.monotonic() - start, 3)
                            chunks.append(part.inline_data.data)
                if content.turn_complete:
                    break
    pcm = b"".join(chunks)
    if not pcm:
        raise RuntimeError("No synthesized audio")
    return pcm, {
        "transcript": transcript,
        "first_audio_seconds": first,
        "duration_seconds": round(len(pcm) / 48000, 3),
    }


async def judge(client, pcm):
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            "Assess this SYNTHETIC voice sample for a business assistant in Uzbekistan. "
            "Rate naturalness, Uzbek pronunciation, Russian pronunciation from 1 (poor) to 5 (excellent). "
            "Listen to the audio, not presumed voice identity. Give concrete audible errors. "
            "Expected script: " + SCRIPT,
            types.Part.from_bytes(data=wav_bytes(pcm), mime_type="audio/wav"),
        ],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": {
                "type": "object",
                "properties": {
                    "naturalness": {"type": "integer", "minimum": 1, "maximum": 5},
                    "uzbek_pronunciation": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "russian_pronunciation": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "audible_issues": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "naturalness",
                    "uzbek_pronunciation",
                    "russian_pronunciation",
                    "audible_issues",
                ],
            },
        },
    )
    return json.loads(response.text)


async def recognize(client, pcm, noisy=False):
    signal = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    signal = soxr.resample(signal, 24000, 16000)
    if noisy:
        # A narrow-band, 20 dB SNR condition, not a real Telegram recording.
        signal = soxr.resample(soxr.resample(signal, 16000, 8000), 8000, 16000)
        rms = float(np.sqrt(np.mean(signal**2)))
        signal += np.random.default_rng(9).normal(0, rms / 10, len(signal))
    audio = np.clip(signal, -32768, 32767).astype("<i2").tobytes() + bytes(32000)
    events = []
    parts = []
    async with open_recognition(client) as recognizer:

        async def receive():
            async for speech in recognizer.receive():
                events.append({"text": speech.text, "final": speech.final})
                if speech.final:
                    parts.append(speech.text)

        receiver = asyncio.create_task(receive())
        try:
            for offset in range(0, len(audio), 2560):
                await recognizer.send(audio[offset : offset + 2560])
                await asyncio.sleep(0.08)
            await recognizer.finish()
            await asyncio.sleep(0.5)
            if receiver.done():
                await receiver
        finally:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
    return {
        "text": " ".join(parts),
        "events": events,
        "noisy": noisy,
        "source": "dedicated_stt_verbatim",
    }


async def main(args):
    key = os.getenv("GEMINI_API_KEY")
    if args.credentials:
        key = json.loads(Path(args.credentials).read_text(encoding="utf-8-sig"))[
            "api_key"
        ]
    if not key:
        raise SystemExit("GEMINI_API_KEY or --credentials is required")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=key, http_options={"api_version": "v1beta"})
    semaphore = asyncio.Semaphore(2)
    report = {
        "synthetic_audio_only": True,
        "judge_is_automated": True,
        "voices": [],
        "asr": [],
    }

    async def voice_case(name):
        async with semaphore:
            pcm, metrics = await synthesize(client, SCRIPT, name)
            (out / f"voice-{name}.wav").write_bytes(wav_bytes(pcm))
            metrics.update(voice=name)
            report["voices"].append(metrics)
            try:
                metrics["automated_review"] = await judge(client, pcm)
            except (APIError, TimeoutError, json.JSONDecodeError) as exc:
                metrics["review_error"] = type(exc).__name__
            print(json.dumps(metrics, ensure_ascii=True), flush=True)

    async def asr_case(label, text):
        async with semaphore:
            pcm, _ = await synthesize(client, text, "Kore")
            (out / f"input-{label}.wav").write_bytes(wav_bytes(pcm))
            result = {
                "case": label,
                "expected": text,
                "clean": await recognize(client, pcm),
            }
            if label in ("uz", "ru"):
                result["telephone_noise"] = await recognize(client, pcm, True)
            report["asr"].append(result)
            print(json.dumps(result, ensure_ascii=True), flush=True)

    try:
        if args.mode in ("all", "voices"):
            await asyncio.gather(*(voice_case(v) for v in args.voices.split(",")))
        if args.mode in ("all", "asr"):
            await asyncio.gather(*(asr_case(label, text) for label, text in CASES))
    finally:
        (out / f"report-{args.mode}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        await client.aio.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials")
    parser.add_argument("--out", default="backend/data/voice-evaluation")
    parser.add_argument("--voices", default="Aoede,Iapetus,Charon,Kore")
    parser.add_argument("--mode", choices=["all", "voices", "asr"], default="all")
    asyncio.run(main(parser.parse_args()))
