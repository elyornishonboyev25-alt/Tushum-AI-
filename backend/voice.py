"""Tenant-scoped Telegram call queue, transcripts and confirmed agreements."""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import database
from .domain import (
    add_debt,
    add_promise,
    debt_paid,
    event,
    money,
    now,
    perform,
    phone,
    scoped,
    today,
    uid,
)
from .security import current_user
from .voice_policy import POLICY_VERSION

router = APIRouter(prefix="/api/voice", tags=["voice"])
Actor = Annotated[dict, Depends(current_user)]
ACTIVE = ("queued", "dialing", "connected")
TERMINAL = ("completed", "cancelled", "failed", "no_answer")
SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_profiles (
 business_id TEXT PRIMARY KEY REFERENCES businesses(id), business_name TEXT NOT NULL,
 manager_name TEXT NOT NULL, phone TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_handoffs (
 id TEXT PRIMARY KEY, call_id TEXT NOT NULL UNIQUE REFERENCES voice_calls(id),
 business_id TEXT NOT NULL REFERENCES businesses(id), customer_id TEXT NOT NULL REFERENCES customers(id),
 debt_id TEXT NOT NULL REFERENCES debts(id), kind TEXT NOT NULL, summary TEXT NOT NULL,
 resolved INTEGER NOT NULL DEFAULT 0, resolution TEXT NOT NULL DEFAULT '',
 resolved_by TEXT REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS voice_handoff_business ON voice_handoffs(business_id,resolved,created_at DESC);
CREATE TABLE IF NOT EXISTS voice_binding (
 id INTEGER PRIMARY KEY CHECK(id=1), business_id TEXT NOT NULL REFERENCES businesses(id),
 user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_contacts (
 business_id TEXT NOT NULL REFERENCES businesses(id), target TEXT NOT NULL,
 customer_id TEXT NOT NULL UNIQUE REFERENCES customers(id), created_at TEXT NOT NULL,
 PRIMARY KEY(business_id,target)
);
CREATE TABLE IF NOT EXISTS voice_calls (
 id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
 user_id TEXT NOT NULL REFERENCES users(id), customer_id TEXT NOT NULL REFERENCES customers(id),
 debt_id TEXT NOT NULL REFERENCES debts(id), target TEXT NOT NULL, status TEXT NOT NULL,
 outcome TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '', error_code TEXT NOT NULL DEFAULT '',
 context_json TEXT NOT NULL, proposal_json TEXT, promise_id TEXT REFERENCES promises(id),
 cancel_requested INTEGER NOT NULL DEFAULT 0, policy_version TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT, ended_at TEXT,
 first_audio_ms INTEGER, slot INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS voice_one_active ON voice_calls(slot)
 WHERE status IN ('queued','dialing','connected');
CREATE INDEX IF NOT EXISTS voice_business ON voice_calls(business_id,created_at DESC);
CREATE TABLE IF NOT EXISTS voice_transcript (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL REFERENCES voice_calls(id),
 utterance_id TEXT NOT NULL, speaker TEXT NOT NULL, text TEXT NOT NULL,
 is_final INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(call_id,utterance_id)
);
"""

# Runtime details contain safe codes, never credentials or provider exception messages.
runtime = {"ready": False, "state": "not_configured", "caller": "", "model": ""}
log = logging.getLogger("uvicorn.error")


def configured_owner_phone():
    value = os.getenv("TUSHUM_VOICE_OWNER_PHONE", "").strip()
    return phone(value) if value else ""


def initialize():
    with database.read() as c:
        c.executescript(SCHEMA)
        owner_phone = configured_owner_phone()
        if owner_phone:
            owner = c.execute(
                "SELECT * FROM users WHERE phone=? AND role='owner' AND active=1",
                (owner_phone,),
            ).fetchone()
            if owner:
                c.execute(
                    "INSERT INTO voice_binding VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE SET business_id=excluded.business_id,user_id=excluded.user_id,created_at=excluded.created_at",
                    (owner["business_id"], owner["id"], now()),
                )
                log.info("Voice binding is ready for the configured owner account")
            else:
                log.warning(
                    "Configured voice owner account was not found or is inactive"
                )
            return
        business_id = os.getenv("TUSHUM_VOICE_BUSINESS_ID", "")
        if business_id:
            owner = c.execute(
                "SELECT id FROM users WHERE business_id=? AND role='owner' AND active=1 ORDER BY created_at LIMIT 1",
                (business_id,),
            ).fetchone()
            if owner:
                c.execute(
                    "INSERT OR IGNORE INTO voice_binding VALUES (1,?,?,?)",
                    (business_id, owner["id"], now()),
                )


def targets() -> list[str]:
    return [
        x.strip().lstrip("@").lower()
        for x in os.getenv("TUSHUM_VOICE_TARGETS", "nishonboyv7").split(",")
        if x.strip()
    ]


def enabled_for(c, business_id):
    binding = c.execute(
        "SELECT b.*,u.phone,u.role,u.active FROM voice_binding b JOIN users u ON u.id=b.user_id WHERE b.id=1 AND b.business_id=?",
        (business_id,),
    ).fetchone()
    owner_phone = configured_owner_phone()
    return bool(
        binding
        and binding["active"]
        and binding["role"] == "owner"
        and (not owner_phone or binding["phone"] == owner_phone)
    )


def custom_targets_enabled():
    return os.getenv("TUSHUM_VOICE_CUSTOM_TARGETS", "0") == "1"


def target_allowed(c, business_id, target):
    return enabled_for(c, business_id) and (
        custom_targets_enabled() or target in targets()
    )


def describe(c, actor):
    bound = enabled_for(c, actor["business_id"])
    return {
        "bound": bound,
        "ready": bound and runtime["ready"],
        "state": runtime["state"] if bound else "not_linked",
        "caller": runtime["caller"] if bound else "",
        "model": runtime["model"] if bound else "",
        "targets": targets() if bound else [],
        "custom_targets": bound and custom_targets_enabled(),
        "policy_version": POLICY_VERSION,
        "transport": "telegram",
        "max_seconds": 300,
        "profile": business_profile(c, actor),
    }


def business_profile(c, actor):
    row = c.execute(
        "SELECT * FROM voice_profiles WHERE business_id=?", (actor["business_id"],)
    ).fetchone()
    if row:
        return dict(row) | {"complete": True}
    business = c.execute(
        "SELECT * FROM businesses WHERE id=?", (actor["business_id"],)
    ).fetchone()
    return {
        "complete": False,
        "business_name": business["name"],
        "manager_name": actor["name"],
        "phone": business["phone"],
    }


class VoiceProfile(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    business_name: str = Field(min_length=2, max_length=120)
    manager_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=9, max_length=24)


@router.put("/profile")
def save_profile(data: VoiceProfile, request: Request, actor: Actor):
    def change(c):
        if c.execute(
            "SELECT 1 FROM voice_calls WHERE business_id=? AND status IN ('queued','dialing','connected')",
            (actor["business_id"],),
        ).fetchone():
            raise HTTPException(409, "Suhbat tugagach biznes ma’lumotlarini yangilang.")
        c.execute(
            "INSERT INTO voice_profiles VALUES (?,?,?,?,?) ON CONFLICT(business_id) DO UPDATE SET business_name=excluded.business_name,manager_name=excluded.manager_name,phone=excluded.phone,updated_at=excluded.updated_at",
            (
                actor["business_id"],
                data.business_name,
                data.manager_name,
                phone(data.phone),
                now(),
            ),
        )
        return business_profile(c, actor)

    return perform(
        actor, request, "voice.profile", data.model_dump(), change, owner=True
    )


class HandoffResolution(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    resolution: str = Field(min_length=3, max_length=600)


@router.post("/handoffs/{handoff_id}/resolve")
def resolve_handoff(
    handoff_id: str, data: HandoffResolution, request: Request, actor: Actor
):
    def change(c):
        row = scoped(c, "voice_handoffs", handoff_id, actor["business_id"])
        if row["resolved"]:
            raise HTTPException(409, "Bu murojaat ko‘rib chiqilgan.")
        c.execute(
            "UPDATE voice_handoffs SET resolved=1,resolution=?,resolved_by=?,updated_at=? WHERE id=?",
            (data.resolution, actor["id"], now(), handoff_id),
        )
        event(
            c,
            actor,
            "voice",
            "AI murojaati ko‘rib chiqildi",
            data.resolution,
            customer_id=row["customer_id"],
            debt_id=row["debt_id"],
        )
        return {"id": handoff_id, "resolved": True}

    return perform(
        actor, request, "voice.resolve:" + handoff_id, data.model_dump(), change
    )


def public_call(row):
    result = dict(row)
    context = json.loads(result.pop("context_json", "{}"))
    result["brief"] = {
        key: context.get(key, "")
        for key in (
            "business",
            "manager_name",
            "customer",
            "debt_title",
            "balance_som",
            "due_on",
            "issued_on",
            "reference",
        )
    }
    proposal = result.pop("proposal_json", None)
    result["proposal"] = json.loads(proposal) if proposal else None
    result.pop("slot", None)
    return result


@router.get("")
def list_calls(actor: Actor):
    with database.read() as c:
        calls = c.execute(
            "SELECT v.*,c.name AS customer_name FROM voice_calls v JOIN customers c ON c.id=v.customer_id "
            "WHERE v.business_id=? ORDER BY v.created_at DESC LIMIT 100",
            (actor["business_id"],),
        ).fetchall()
        return {
            "connection": describe(c, actor),
            "calls": [public_call(r) for r in calls],
        }


class Activation(BaseModel):
    code: str = Field(min_length=16, max_length=150)


@router.post("/activate")
def activate(data: Activation, actor: Actor):
    if actor["role"] != "owner":
        raise HTTPException(403, "Ulanishni faqat biznes egasi sozlaydi.")
    if configured_owner_phone() and actor["phone"] != configured_owner_phone():
        raise HTTPException(403, "Ovozli xizmat boshqa hisob egasi uchun sozlangan.")
    expected = os.getenv("TUSHUM_VOICE_SETUP_CODE", "")
    if not expected or not hmac.compare_digest(data.code, expected):
        raise HTTPException(403, "Ulash kodi mos kelmadi.")
    with database.write() as c:
        existing = c.execute("SELECT * FROM voice_binding WHERE id=1").fetchone()
        if existing and existing["business_id"] != actor["business_id"]:
            raise HTTPException(409, "Telegram akkaunti boshqa biznesga ulangan.")
        c.execute(
            "INSERT OR IGNORE INTO voice_binding VALUES (1,?,?,?)",
            (actor["business_id"], actor["id"], now()),
        )
        return describe(c, actor)


class StartCall(BaseModel):
    debt_id: str = Field(min_length=1, max_length=100)
    target: str = Field(
        min_length=5, max_length=33, pattern=r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$"
    )
    consent: bool


def context_for(c, actor, debt):
    customer = scoped(c, "customers", debt["customer_id"], actor["business_id"])
    remaining = debt["amount"] - debt_paid(c, debt["id"])
    reserved = c.execute(
        "SELECT COALESCE(SUM(p.amount-COALESCE((SELECT SUM(a.amount-a.reversed_amount) FROM promise_allocations a "
        "WHERE a.promise_id=p.id),0)),0) FROM promises p WHERE p.debt_id=? AND p.cancelled=0",
        (debt["id"],),
    ).fetchone()[0]
    profile = business_profile(c, actor)
    if not profile["complete"]:
        raise HTTPException(
            422,
            "Avval qo‘ng‘iroq uchun do‘kon yoki korxona nomi va mas’ul menejer ma’lumotlarini tasdiqlang.",
        )
    return customer, {
        "business": profile["business_name"],
        "manager_name": profile["manager_name"],
        "business_phone": profile["phone"],
        "customer": customer["name"],
        "today": today(),
        "timezone": "Asia/Tashkent",
        "debt_title": debt["title"],
        "issued_on": debt["issued_on"],
        "reference": debt["reference"] or "",
        "due_on": debt["due_on"],
        "balance_som": f"{remaining / 100:.2f}",
        "available_promise_som": f"{max(0, remaining - reserved) / 100:.2f}",
        "existing_promises_som": f"{reserved / 100:.2f}",
        "currency": "UZS",
    }


@router.post("/calls")
def start_call(data: StartCall, request: Request, actor: Actor):
    return perform(
        actor,
        request,
        "voice.start",
        data.model_dump(),
        lambda c: queue_call(c, actor, data.debt_id, data.target, data.consent),
    )


def queue_call(c, actor, debt_id, target, consent):
    if not enabled_for(c, actor["business_id"]):
        raise HTTPException(403, "Avval Telegram ulanishini sozlang.")
    if not runtime["ready"]:
        raise HTTPException(
            503, "Ovozli xizmat hali tayyor emas. Ulanish holatini tekshiring."
        )
    target = target.lstrip("@").lower()
    if not target_allowed(c, actor["business_id"], target):
        raise HTTPException(
            403, "Bu akkaunt sinov uchun ruxsat etilgan ro‘yxatda yo‘q."
        )
    debt = scoped(c, "debts", debt_id, actor["business_id"])
    customer, context = context_for(c, actor, debt)
    if not consent or not customer["contact_allowed"] or customer["archived"]:
        raise HTTPException(
            422, "Suhbat va uni matnga aylantirishga mijoz roziligi kerak."
        )
    if debt["archived"] or debt["amount"] <= debt_paid(c, debt["id"]):
        raise HTTPException(422, "Yopilgan nasiya uchun qo‘ng‘iroq boshlanmaydi.")
    if c.execute(
        "SELECT 1 FROM voice_calls WHERE status IN ('queued','dialing','connected')"
    ).fetchone():
        raise HTTPException(409, "Bitta suhbat davom etmoqda. Avval uni yakunlang.")
    recent = (date.fromisoformat(today()) - timedelta(days=1)).isoformat()
    if (
        c.execute(
            "SELECT COUNT(*) FROM voice_calls WHERE business_id=? AND created_at>?",
            (actor["business_id"], recent),
        ).fetchone()[0]
        >= 50
    ):
        raise HTTPException(429, "Sinov qo‘ng‘iroqlari limiti tugadi.")
    call_id = uid()
    stamp = now()
    c.execute(
        "INSERT INTO voice_calls(id,business_id,user_id,customer_id,debt_id,target,status,context_json,policy_version,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,'queued',?,?,?,?)",
        (
            call_id,
            actor["business_id"],
            actor["id"],
            customer["id"],
            debt["id"],
            target,
            json.dumps(context, ensure_ascii=False),
            POLICY_VERSION,
            stamp,
            stamp,
        ),
    )
    event(
        c,
        actor,
        "voice",
        "AI suhbat navbatga qo‘yildi",
        "@" + target,
        customer_id=customer["id"],
        debt_id=debt["id"],
    )
    return {"id": call_id}


class QuickCall(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    name: str = Field(min_length=2, max_length=100)
    target: str = Field(
        min_length=5, max_length=33, pattern=r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$"
    )
    amount: str = Field(min_length=1, max_length=30)
    due_on: date | None = None
    consent: bool


def quick_plan(c, actor, data):
    target = data.target.lstrip("@").lower()
    if not enabled_for(c, actor["business_id"]) or not custom_targets_enabled():
        raise HTTPException(
            403, "Bu hisob uchun erkin Telegram username orqali qo‘ng‘iroq yoqilmagan."
        )
    profile = business_profile(c, actor)
    if not profile["complete"]:
        raise HTTPException(
            422, "Avval qo‘ng‘iroq uchun biznes ma’lumotlarini tasdiqlang."
        )
    amount = money(data.amount)
    contact = c.execute(
        "SELECT c.* FROM voice_contacts v JOIN customers c ON c.id=v.customer_id WHERE v.business_id=? AND v.target=?",
        (actor["business_id"], target),
    ).fetchone()
    due = data.due_on.isoformat() if data.due_on else today()
    result = {
        "action": "new",
        "name": data.name,
        "target": target,
        "amount": amount,
        "due_on": due,
        "business": profile["business_name"],
        "manager_name": profile["manager_name"],
    }
    if contact:
        if not contact["contact_allowed"] or contact["archived"]:
            raise HTTPException(
                422, "Mijoz bilan aloqaga ruxsat yo‘q yoki u arxivlangan."
            )
        if " ".join(contact["name"].casefold().split()) != " ".join(
            data.name.casefold().split()
        ):
            raise HTTPException(
                409,
                f"Bu username {contact['name']} nomi bilan saqlangan. Mavjud mijozni tanlang yoki uning kartasini tahrirlang.",
            )
        debts = [
            dict(row)
            for row in c.execute(
                "SELECT * FROM debts WHERE customer_id=? AND business_id=? AND archived=0 ORDER BY created_at",
                (contact["id"], actor["business_id"]),
            )
        ]
        open_debts = [d for d in debts if d["amount"] > debt_paid(c, d["id"])]
        if len(open_debts) != 1:
            raise HTTPException(
                409,
                "Bu mijoz uchun mavjud nasiyani tanlang. Yangi nasiya kerak bo‘lsa, mijoz kartasidan qo‘shing.",
            )
        debt = open_debts[0]
        balance = debt["amount"] - debt_paid(c, debt["id"])
        if amount != balance:
            raise HTTPException(
                409,
                f"Saqlangan qarz qoldig‘i {balance / 100:g} so‘m. Shu summani kiriting yoki mavjud nasiyani tanlang. Yangi qarz qo‘shilmadi.",
            )
        result.update(
            action="reuse",
            customer_id=contact["id"],
            debt_id=debt["id"],
            due_on=debt["due_on"],
        )
    elif due < today():
        raise HTTPException(
            422, "Yangi nasiya uchun muddatni bugundan boshlab tanlang."
        )
    return result


@router.post("/quick-preview")
def quick_preview(data: QuickCall, actor: Actor):
    if actor["role"] not in ("owner", "manager"):
        raise HTTPException(403, "Qo‘ng‘iroqni biznes egasi yoki menejer boshlaydi.")
    with database.read() as c:
        c.execute("BEGIN")
        return quick_plan(c, actor, data)


@router.post("/quick-calls")
def quick_call(data: QuickCall, request: Request, actor: Actor):
    def save(c):
        if not data.consent:
            raise HTTPException(
                422,
                "Mijoz qo‘ng‘iroq va suhbatni matnga aylantirishga rozi bo‘lishi kerak.",
            )
        plan = quick_plan(c, actor, data)
        if plan["action"] == "new":
            customer_id, stamp = uid(), now()
            c.execute(
                "INSERT INTO customers(id,business_id,name,phone,company,note,contact_allowed,archived,created_at,updated_at) VALUES (?,?,?,'','','',1,0,?,?)",
                (customer_id, actor["business_id"], data.name, stamp, stamp),
            )
            c.execute(
                "INSERT INTO voice_contacts VALUES (?,?,?,?)",
                (actor["business_id"], plan["target"], customer_id, stamp),
            )
            event(
                c,
                actor,
                "customer",
                "Telegram mijozi qo‘shildi",
                "@" + plan["target"],
                customer_id=customer_id,
            )
            debt_id = add_debt(
                c,
                actor,
                {
                    "customer_id": customer_id,
                    "title": "Nasiya",
                    "amount": data.amount,
                    "issued_on": today(),
                    "due_on": plan["due_on"],
                    "note": "Telegram orqali kiritilgan nasiya",
                },
            )
        else:
            customer_id, debt_id = plan["customer_id"], plan["debt_id"]
        result = queue_call(c, actor, debt_id, plan["target"], data.consent)
        return {
            **result,
            "customer_id": customer_id,
            "debt_id": debt_id,
            "reused": plan["action"] == "reuse",
        }

    return perform(
        actor, request, "voice.quick_start", data.model_dump(mode="json"), save
    )


@router.get("/calls/{call_id}")
def call_detail(call_id: str, actor: Actor):
    with database.read() as c:
        row = scoped(c, "voice_calls", call_id, actor["business_id"])
        result = public_call(row)
        handoff = c.execute(
            "SELECT * FROM voice_handoffs WHERE call_id=? AND business_id=?",
            (call_id, actor["business_id"]),
        ).fetchone()
        result["handoff"] = dict(handoff) if handoff else None
        result["transcript"] = [
            dict(r)
            for r in c.execute(
                "SELECT * FROM voice_transcript WHERE call_id=? ORDER BY seq",
                (call_id,),
            )
        ]
        return result


@router.post("/calls/{call_id}/cancel")
def cancel_call(call_id: str, request: Request, actor: Actor):
    def save(c):
        row = scoped(c, "voice_calls", call_id, actor["business_id"])
        if row["status"] in ACTIVE:
            c.execute(
                "UPDATE voice_calls SET cancel_requested=1,updated_at=? WHERE id=?",
                (now(), call_id),
            )
        return {"id": call_id}

    return perform(actor, request, "voice.cancel", {"id": call_id}, save)


def transcript(call_id, utterance_id, speaker, text, final=False):
    if not text.strip():
        return
    with database.write() as c:
        c.execute(
            "INSERT INTO voice_transcript(call_id,utterance_id,speaker,text,is_final,created_at,updated_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(call_id,utterance_id) DO UPDATE SET text=excluded.text,is_final=excluded.is_final,updated_at=excluded.updated_at",
            (call_id, utterance_id, speaker, text[:8000], int(final), now(), now()),
        )


def change_status(call_id, status, *, error_code="", latency=None):
    with database.write() as c:
        row = c.execute(
            "SELECT status FROM voice_calls WHERE id=?", (call_id,)
        ).fetchone()
        if not row or row["status"] in TERMINAL:
            return
        c.execute(
            "UPDATE voice_calls SET status=?,error_code=?,updated_at=?,started_at=CASE WHEN ?='connected' THEN COALESCE(started_at,?) ELSE started_at END,"
            "ended_at=CASE WHEN ? IN ('completed','cancelled','failed','no_answer') THEN ? ELSE ended_at END,first_audio_ms=COALESCE(first_audio_ms,?) WHERE id=?",
            (status, error_code, now(), status, now(), status, now(), latency, call_id),
        )
        if status == "completed":
            c.execute(
                "UPDATE voice_calls SET outcome='no_agreement',summary='Suhbat yakunlandi. Tasdiqlangan kelishuv qayd etilmadi.' WHERE id=? AND outcome=''",
                (call_id,),
            )


def execute_tool(call_id: str, name: str, args: dict) -> dict:
    """All model actions pass through accounting and conversation-state validation."""
    try:
        with database.write() as c:
            call = dict(
                c.execute("SELECT * FROM voice_calls WHERE id=?", (call_id,)).fetchone()
            )
            if call["status"] != "connected" or call["cancel_requested"]:
                return {"error": "Suhbat faol emas."}
            actor = c.execute(
                "SELECT * FROM users WHERE id=? AND active=1 AND role IN ('owner','manager')",
                (call["user_id"],),
            ).fetchone()
            if not actor:
                return {"error": "Vakolat bekor qilingan."}
            if name in ("propose_promise", "propose_schedule"):
                if call["promise_id"]:
                    return {
                        "error": "Kelishuv allaqachon saqlangan. O‘zgartirishni menejer ko‘rib chiqadi."
                    }
                raw = (
                    args.get("installments", [])
                    if name == "propose_schedule"
                    else [args]
                )
                if (
                    not isinstance(raw, list)
                    or not 1 <= len(raw) <= 6
                    or not all(isinstance(part, dict) for part in raw)
                ):
                    return {"error": "Jadval 1–6 ta to‘lovdan iborat bo‘lsin."}
                installments = []
                for part in raw:
                    part_amount = money(part.get("amount", ""))
                    due = date.fromisoformat(part.get("due_on", ""))
                    if (
                        not date.fromisoformat(today())
                        <= due
                        <= date.fromisoformat(today()) + timedelta(days=365)
                    ):
                        return {
                            "error": "Bugundan keyingi 365 kun ichida aniq sanani so‘rang."
                        }
                    installments.append(
                        {"amount": part_amount, "due_on": due.isoformat()}
                    )
                installments.sort(key=lambda part: part["due_on"])
                amount = sum(part["amount"] for part in installments)
                utterances = [
                    row["text"]
                    for row in c.execute(
                        "SELECT text FROM voice_transcript WHERE call_id=? AND speaker='customer' AND is_final=1 ORDER BY seq DESC LIMIT 20",
                        (call_id,),
                    )
                ]
                customer_words = re.sub(r"[^\w\s]", "", " ".join(utterances).lower())
                # The assistant repeating the balance is not a customer's payment offer.
                has_amount = re.search(
                    r"\b(ming|million|mln|som|yarmini|yarim|yarmi|hammasini|hammasi|toliq|qolganini|тысяч|миллион|сум|половину|всю)\b|\b\d{4,}\b",
                    customer_words,
                )
                latest_words = (
                    re.sub(r"[^\w\s]", "", utterances[0].lower()) if utterances else ""
                )
                if not has_amount or re.search(
                    r"summa.*kelishmadik|summani.*aytmadim", latest_words
                ):
                    return {
                        "error": "Mijoz hali qancha to‘lashini aytmadi. Summani o‘zingiz taxmin qilmang. Avval muloyim so‘rang."
                    }
                debt = scoped(c, "debts", call["debt_id"], call["business_id"])
                _, context = context_for(c, actor, debt)
                if amount > money(context["available_promise_som"]):
                    return {
                        "error": "Summa bo‘sh qoldiqdan katta. Mavjud va’dani o‘zgartirishni menejer ko‘rib chiqadi."
                    }
                latest = c.execute(
                    "SELECT COALESCE(MAX(seq),0) FROM voice_transcript WHERE call_id=?",
                    (call_id,),
                ).fetchone()[0]
                proposal = {
                    "id": uid(),
                    "amount": amount,
                    "due_on": installments[-1]["due_on"],
                    "installments": installments,
                    "after_seq": latest,
                }
                c.execute(
                    "UPDATE voice_calls SET proposal_json=?,updated_at=? WHERE id=?",
                    (json.dumps(proposal), now(), call_id),
                )
                return {
                    "proposal_id": proposal["id"],
                    "amount_som": f"{amount / 100:.2f}",
                    "installments": [
                        {
                            "amount_som": f"{p['amount'] / 100:.2f}",
                            "due_on": p["due_on"],
                        }
                        for p in installments
                    ],
                    "instruction": "HAR BIR summa va sanani ovoz chiqarib ayting. Keyin yangi aniq tasdiqni kuting. Hali saqlanmadi.",
                }
            if name == "confirm_promise":
                if call["promise_id"]:
                    return {"saved": True, "promise_id": call["promise_id"]}
                proposal = json.loads(call["proposal_json"] or "{}")
                if not proposal or proposal.get("id") != args.get("proposal_id"):
                    return {"error": "Avval to‘lov loyihasini yarating."}
                rows = c.execute(
                    "SELECT * FROM voice_transcript WHERE call_id=? AND seq>? ORDER BY seq",
                    (call_id, proposal["after_seq"]),
                ).fetchall()
                spoken = next(
                    (r for r in rows if r["speaker"] == "ai" and r["text"].strip()),
                    None,
                )
                answer = next(
                    (
                        r
                        for r in reversed(rows)
                        if r["speaker"] == "customer" and r["is_final"]
                    ),
                    None,
                )
                normalized = (
                    re.sub(r"[^\w\s]", "", answer["text"].lower()) if answer else ""
                )
                positive = re.search(
                    r"\b(ha|xa|mayli|roziman|tasdiqlayman|togri|boladi|boldi|kelishdik|xop|hop|xoop|да|согласен|подтверждаю)\b",
                    normalized,
                )
                negative = re.search(
                    r"\b(yoq|yo‘q|emas|lekin|ammo|нет|но|ertaga|bugun)\b", normalized
                )
                # Numbers and conditions in a confirmation may be a correction.
                allowed_words = {
                    "boldi",
                    "kelishdik",
                    "xop",
                    "hop",
                    "xoop",
                    "yaxshi",
                    "aka",
                    "opa",
                    "ha",
                    "xa",
                    "mayli",
                    "roziman",
                    "tasdiqlayman",
                    "togri",
                    "boladi",
                    "albatta",
                    "shunday",
                    "shu",
                    "kelishuvni",
                    "tushunarli",
                    "tushundim",
                    "tushundingiz",
                    "rahmat",
                    "men",
                    "hammasi",
                    "да",
                    "согласен",
                    "подтверждаю",
                    "верно",
                    "хорошо",
                }
                conditional = any(
                    word not in allowed_words for word in normalized.split()
                )
                if (
                    not spoken
                    or not answer
                    or answer["seq"] <= spoken["seq"]
                    or not positive
                    or negative
                    or conditional
                ):
                    return {
                        "error": "Qayta o‘qishdan keyingi aniq tasdiq yo‘q. Faqat 'ha, tasdiqlayman' kabi aniq javobni so‘rang."
                    }
                schedule = proposal.get(
                    "installments",
                    [{"amount": proposal["amount"], "due_on": proposal["due_on"]}],
                )
                # If another employee changed the balance, all installments fail atomically.
                c.execute("SAVEPOINT voice_schedule")
                try:
                    promise_ids = [
                        add_promise(
                            c,
                            dict(actor),
                            {
                                "debt_id": call["debt_id"],
                                "amount": f"{part['amount'] / 100:.2f}",
                                "due_on": part["due_on"],
                                "note": "Telegram AI suhbati orqali tasdiqlandi. "
                                + call_id,
                            },
                        )
                        for part in schedule
                    ]
                except HTTPException:
                    c.execute("ROLLBACK TO voice_schedule")
                    c.execute("RELEASE voice_schedule")
                    raise
                c.execute("RELEASE voice_schedule")
                promise_id = promise_ids[0]
                proposal["promise_ids"] = promise_ids
                summary = (
                    "Tasdiqlangan jadval — "
                    + "; ".join(
                        f"{p['amount'] / 100:g} so‘m, {p['due_on']}" for p in schedule
                    )
                    + ". To‘lov hali qayd etilmadi."
                )
                c.execute(
                    "UPDATE voice_calls SET promise_id=?,proposal_json=?,outcome='promise',summary=?,updated_at=? WHERE id=?",
                    (promise_id, json.dumps(proposal), summary, now(), call_id),
                )
                return {
                    "saved": True,
                    "promise_id": promise_id,
                    "promise_ids": promise_ids,
                    "instruction": "Rahmat ayting, kelishuv saqlandi. Xayrlashing.",
                }
            if name == "finish_call":
                existing_handoff = c.execute(
                    "SELECT * FROM voice_handoffs WHERE call_id=?", (call_id,)
                ).fetchone()
                if existing_handoff:
                    return {
                        "finish": True,
                        "outcome": existing_handoff["kind"],
                        "handoff_id": existing_handoff["id"],
                        "instruction": "Murojaat avval saqlangan. Faqat muloyim xayrlashing.",
                    }
                outcome = args.get("outcome")
                allowed = {
                    "promise",
                    "no_agreement",
                    "payment_claimed",
                    "disputed",
                    "wrong_person",
                    "opt_out",
                    "callback",
                    "human_requested",
                }
                if outcome not in allowed or (
                    outcome == "promise" and not call["promise_id"]
                ):
                    return {
                        "error": "Natija mos kelmadi. Saqlanmagan va’dani tasdiqlangan deb aytmang."
                    }
                # A saved promise and a later objection can both be true. Keep the
                # promise, but never hide the objection behind a successful outcome.
                if call["promise_id"] and outcome == "no_agreement":
                    outcome = "promise"
                summary = (
                    call["summary"]
                    if outcome == "promise"
                    else str(args.get("summary", ""))[:600]
                )
                if not summary.strip():
                    return {"error": "Mijoz aytgan holatni qisqa xulosada yozing."}
                handoff_id = None
                if outcome in {
                    "disputed",
                    "payment_claimed",
                    "human_requested",
                    "callback",
                    "wrong_person",
                    "opt_out",
                    "no_agreement",
                }:
                    handoff_id = uid()
                    c.execute(
                        "INSERT OR IGNORE INTO voice_handoffs(id,call_id,business_id,customer_id,debt_id,kind,summary,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            handoff_id,
                            call_id,
                            call["business_id"],
                            call["customer_id"],
                            call["debt_id"],
                            outcome,
                            summary,
                            now(),
                            now(),
                        ),
                    )
                    handoff_id = c.execute(
                        "SELECT id FROM voice_handoffs WHERE call_id=?", (call_id,)
                    ).fetchone()[0]
                c.execute(
                    "UPDATE voice_calls SET outcome=?,summary=?,updated_at=? WHERE id=?",
                    (outcome, summary, now(), call_id),
                )
                if outcome == "opt_out":
                    c.execute(
                        "UPDATE customers SET contact_allowed=0,updated_at=? WHERE id=?",
                        (now(), call["customer_id"]),
                    )
                event(
                    c,
                    dict(actor),
                    "voice",
                    "AI suhbat natijasi",
                    summary,
                    customer_id=call["customer_id"],
                    debt_id=call["debt_id"],
                )
                return {
                    "finish": True,
                    "outcome": outcome,
                    "handoff_id": handoff_id,
                    "instruction": "Natija saqlandi. Murojaat menejerga yuborilgan bo‘lsa, shuni ayting. Hozir mijozga muloyim xayrlashing, masalan: Rahmat, yaxshi qoling. Jim qolmang.",
                }
            return {"error": "Bunday vosita mavjud emas."}
    except (ValueError, TypeError, KeyError):
        return {"error": "Summa yoki sana formati mos emas. Aniqlashtiring."}
    except HTTPException as exc:
        return {"error": exc.detail}
