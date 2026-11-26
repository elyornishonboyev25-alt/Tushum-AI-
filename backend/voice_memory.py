"""Bounded per-call facts from committed captions; never an extra recognizer.

Keep the caller's words as data, not guessed amounts/dates or payment consent.
Context updates change the existing audio session's instructions without a
synthetic user turn, interrupting playback or requiring a second model.
"""

import asyncio
import copy
import json
import logging
import re

from google.genai.errors import APIError
from websockets.exceptions import ConnectionClosed

from .voice_evidence import explicit_payment_values, latinized, normalized

log = logging.getLogger(__name__)


def question_fields(text):
    words = latinized(normalized(text))
    fields = set()
    for field, pattern in {
        "identity": r"ozingizmisiz|sizmisiz|ismingiz|kim bilan gaplash",
        "availability": r"gaplash.*(?:qulay|imkon|vaqt|bolad)|gaplasha ol|hozir.*qulay|bandmisiz",
        "amount": r"qancha|qanchadan|qaysi summa",
        "date": r"qachon|qaysi kun|qaysi sana|qaysi muddat",
    }.items():
        if re.search(pattern, words):
            fields.add(field)
    return fields


class CallMemory:
    def __init__(self, context):
        self.context = context
        self.answers = {}
        self.asked = {}
        self.last_questions = set()
        self.revision = 0

    def snapshot(self):
        return {
            "caller_words_already_given": dict(self.answers),
            "question_attempts": dict(self.asked),
        }

    def _update_revision(self, before):
        changed = before != self.snapshot()
        if changed:
            self.revision += 1
        return changed

    def assistant(self, text):
        before = self.snapshot()
        self.last_questions = question_fields(text)
        for field in self.last_questions:
            self.asked[field] = min(3, self.asked.get(field, 0) + 1)
        return self._update_revision(before)

    def customer(self, text):
        before = self.snapshot()
        words = latinized(normalized(text))
        repair = bool(
            re.search(
                r"qaytar|eshitmay|eshitmadim|nima dedi|tushunmadim|povtor|ne rasslish",
                words,
            )
        )
        expected = latinized(normalized(str(self.context.get("customer", ""))))
        yes = bool(re.search(r"\b(ha|xa|mayli|men|da)\b", words))
        wrong = bool(re.search(r"\b(emas|yoq|ukasi|akasi|opasi|singlisi|net)\b", words))
        if (
            not repair
            and not wrong
            and (
                "identity" in self.last_questions
                and yes
                or expected
                and expected in words
                and re.search(r"\b(men|ya)\b", words)
            )
        ):
            self.answers["identity"] = text[:500]
        if not repair and (
            "availability" in self.last_questions
            and re.search(r"\b(ha|mayli|yoq|da|net)\b", words)
            or re.search(
                r"gaplash.*(?:qulay|olaman)|gaplasha olmay|bandman|hozir qulay|udobno|zanyat",
                words,
            )
        ):
            self.answers["availability"] = text[:500]
        if not repair and explicit_payment_values(
            text, self.context.get("balance_som", "0")
        ):
            self.answers["amount"] = text[:500]
        if re.search(r"summani.*aytmadim|summa.*kelishmadik", words):
            self.answers.pop("amount", None)
        if not repair and re.search(
            r"\b(bugun|ertaga|indin\w*|dushanba\w*|seshanba\w*|chorshanba\w*|payshanba\w*|juma\w*|shanba\w*|yakshanba\w*|zavtra|segodnya|poslezavtra)\b|\d{4}-\d{2}-\d{2}|\b\w+ kundan keyin",
            words,
        ):
            self.answers["date"] = text[:500]
        if re.search(r"sanani.*aytmadim|qachon.*bilmayman|sana.*aniq emas", words):
            self.answers.pop("date", None)
        # Native model still hears the full conversation. These are only small
        # durable reminders, not a replacement transcript or financial authority.
        return self._update_revision(before)


class MemoryPublisher:
    def __init__(self, session, context, memory, instructions, closing):
        self.session, self.context, self.memory = session, context, memory
        self.instructions, self.closing = instructions, closing
        self.changed = asyncio.Event()
        self.disabled = False

    async def run(self):
        last = None
        while True:
            await self.changed.wait()
            self.changed.clear()
            await asyncio.sleep(0.02)  # coalesce caption/turn events
            snapshot = self.memory.snapshot()
            encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
            if (
                self.disabled
                or encoded == last
                or self.closing.requested_at is not None
            ):
                continue
            # Copies prevent a later correction changing the in-flight snapshot.
            context = {**self.context, "conversation_memory": copy.deepcopy(snapshot)}
            try:
                await self.session.send_context_update(
                    system_instruction=self.instructions(context)
                )
                last = encoded
            except (APIError, ConnectionClosed, OSError, TimeoutError):
                self.disabled = True
                log.warning("Voice memory update unavailable; native audio continues")
