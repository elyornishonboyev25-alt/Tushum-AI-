"""Tenant-scoped SMS previews, explicit sends, persistent retries and receipts."""

import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from . import database, schemas, usms
from .domain import event, now, phone, scoped, uid
from .security import current_user

router = APIRouter(prefix="/api", tags=["SMS"])
Actor = Annotated[dict, Depends(current_user)]


class PreviewInput(schemas.Contract):
    template_id: int = Field(gt=0)
    params: dict[str, str] = Field(default_factory=dict, max_length=30)


def owner(actor: dict, *, connected=True):
    if actor["role"] != "owner":
        raise HTTPException(403, "SMS xizmatini biznes egasi boshqaradi.")
    if connected and not usms.enabled_for(actor["business_id"]):
        raise HTTPException(
            403, "USMS hisobi ushbu biznesga bog‘lanmagan. SMS sozlamalarini oching."
        )
    with database.read() as connection:
        business = connection.execute(
            "SELECT * FROM businesses WHERE id=?", (actor["business_id"],)
        ).fetchone()
        if business["is_demo"]:
            raise HTTPException(403, "SMS xizmatini o‘z biznes akkauntingizda oching.")


def recipient(connection, actor: dict, customer_id: str) -> dict:
    customer = scoped(connection, "customers", customer_id, actor["business_id"])
    if customer["archived"] or not customer["contact_allowed"]:
        raise HTTPException(
            409,
            "SMS uchun mijoz faol bo‘lishi va bog‘lanishga roziligi qayd etilishi kerak.",
        )
    return customer


def public_message(row: dict) -> dict:
    return {
        key: row[key]
        for key in (
            "id",
            "customer_id",
            "phone",
            "sender",
            "text",
            "status",
            "provider_id",
            "price",
            "parts",
            "error",
            "created_at",
            "updated_at",
        )
    }


@router.get("/sms/config")
def config(actor: Actor):
    owner(actor, connected=False)
    return {
        "configured": usms.configured(),
        "enabled": usms.enabled_for(actor["business_id"]),
        "business_id": actor["business_id"],
        "sender": usms.sender(),
    }


@router.get("/sms/account")
def account(actor: Actor):
    owner(actor)
    balance = usms.request("GET", "/balance")
    templates = usms.request("GET", "/templates?include=base")
    return {
        "balance": usms.cents(balance.get("balance")),
        "sender": usms.sender(),
        "templates": [
            {
                key: row.get(key)
                for key in ("id", "title", "text", "variables", "kind", "base")
            }
            for row in templates.get("items", [])
            if row.get("kind") == "service"
        ],
    }


@router.get("/customers/{customer_id}/sms")
def history(customer_id: str, actor: Actor):
    owner(actor)
    with database.read() as connection:
        scoped(connection, "customers", customer_id, actor["business_id"])
        rows = connection.execute(
            "SELECT * FROM sms_messages WHERE business_id=? AND customer_id=? AND status!='draft' "
            "ORDER BY created_at DESC LIMIT 50",
            (actor["business_id"], customer_id),
        ).fetchall()
    return {"items": [public_message(dict(row)) for row in rows]}


@router.post("/customers/{customer_id}/sms/preview")
def preview(customer_id: str, data: PreviewInput, actor: Actor):
    owner(actor)
    with database.read() as connection:
        customer = recipient(connection, actor, customer_id)
    templates = usms.request("GET", "/templates?include=base").get("items", [])
    template = next(
        (row for row in templates if str(row.get("id")) == str(data.template_id)), None
    )
    if template is None or template.get("kind") != "service":
        raise HTTPException(
            422, "USMS ro‘yxatidan tasdiqlangan servis shablonini tanlang."
        )
    text = template.get("text", "")
    keys = set(re.findall(r"\{(\w+)\}", text))
    if keys != set(data.params):
        raise HTTPException(422, "Shablonning barcha o‘zgaruvchilarini to‘ldiring.")
    rules = {item["key"]: item for item in template.get("variables", [])}
    for key, value in data.params.items():
        rule = rules.get(key, {})
        if (
            not value
            or len(value) > min(int(rule.get("max_length") or 80), 80)
            or any(char in value for char in "\r\n")
        ):
            raise HTTPException(
                422, f"{key} qiymatini shablon talabiga mos, 80 belgigacha kiriting."
            )
        if rule.get("type") == "digits" and not re.fullmatch(r"[0-9]+", value):
            raise HTTPException(422, f"{key} qiymatida faqat raqamlar bo‘lsin.")
        if rule.get("max_words") and len(value.split()) > int(rule["max_words"]):
            raise HTTPException(422, f"{key} qiymatidagi so‘zlar sonini kamaytiring.")
    rendered = re.sub(r"\{(\w+)\}", lambda match: data.params[match[1]], text)
    payload = {
        "phone": phone(customer["phone"])[1:],
        "template_id": data.template_id,
        "params": data.params,
    }
    estimate = usms.request(
        "POST",
        "/quote",
        {"phone": payload["phone"], "text": rendered, "kind": "service"},
    )
    amount = usms.cents(estimate.get("price"))
    parts = int(estimate.get("parts", 0))
    if parts < 1:
        raise HTTPException(502, "USMS xabar qismlari sonini qaytarmadi.")
    if usms.sender():
        payload["from"] = usms.sender()
    message_id = uid()
    payload["idem_key"] = "tushum-" + message_id
    with database.write() as connection:
        current = recipient(connection, actor, customer_id)
        if current["phone"] != customer["phone"]:
            raise HTTPException(
                409, "Mijoz telefoni yangilandi. SMS narxini qayta tekshiring."
            )
        stamp = now()
        connection.execute(
            "INSERT INTO sms_messages(id,business_id,customer_id,user_id,phone,sender,text,payload,account_key,"
            "status,price,parts,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,'draft',?,?,?,?)",
            (
                message_id,
                actor["business_id"],
                customer_id,
                actor["id"],
                customer["phone"],
                usms.sender(),
                rendered,
                json.dumps(payload, ensure_ascii=False),
                account_key(),
                amount,
                parts,
                stamp,
                stamp,
            ),
        )
        row = scoped(connection, "sms_messages", message_id, actor["business_id"])
    return public_message(row)


def account_key() -> str:
    return hashlib.sha256(os.environ.get("USMS_LOGIN", "").strip().encode()).hexdigest()


def save_receipt(connection, row: dict, result: dict) -> dict:
    provider_id = str(result.get("id") or row["provider_id"])
    state = str(result.get("status") or "unknown")
    if not provider_id:
        state = "uncertain"
    connection.execute(
        "UPDATE sms_messages SET provider_id=?,status=?,price=?,parts=?,error=?,updated_at=? WHERE id=?",
        (
            provider_id,
            state,
            usms.cents(result.get("price", Decimal(row["price"]) / 100)),
            int(result.get("parts", row["parts"])),
            str(result.get("status_note") or "")[:1000],
            now(),
            row["id"],
        ),
    )
    if state == "delivered" and row["status"] != "delivered":
        actor = dict(
            connection.execute(
                "SELECT * FROM users WHERE id=?", (row["user_id"],)
            ).fetchone()
        )
        event(
            connection,
            actor,
            "sms",
            "SMS yetkazildi",
            row["text"],
            customer_id=row["customer_id"],
        )
    return public_message(
        scoped(connection, "sms_messages", row["id"], row["business_id"])
    )


@router.post("/sms/{message_id}/send")
def send(message_id: str, actor: Actor):
    owner(actor)
    with database.write() as connection:
        row = scoped(connection, "sms_messages", message_id, actor["business_id"])
        if row["status"] not in ("draft", "uncertain", "submitting"):
            return public_message(row)
        if (
            row["status"] == "submitting"
            and row["updated_at"]
            > (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
        ):
            return public_message(row)
        customer = recipient(connection, actor, row["customer_id"])
        if customer["phone"] != row["phone"] or row["account_key"] != account_key():
            raise HTTPException(
                409, "Mijoz yoki USMS hisobi o‘zgardi. SMS tarixini tekshiring."
            )
        connection.execute(
            "UPDATE sms_messages SET status='submitting',error='',updated_at=? WHERE id=?",
            (now(), message_id),
        )
    payload = json.loads(row["payload"])
    submitted = False
    try:
        # Reprice fresh drafts, while retaining the exact original payload on uncertain retries.
        if row["status"] == "draft":
            estimate = usms.request(
                "POST",
                "/quote",
                {"phone": payload["phone"], "text": row["text"], "kind": "service"},
            )
            if usms.cents(estimate.get("price")) > row["price"]:
                raise HTTPException(
                    409, "SMS narxi oshdi. Yangidan narxni tekshirib tasdiqlang."
                )
            balance = usms.cents(usms.request("GET", "/balance").get("balance"))
            if balance < usms.cents(estimate.get("price")):
                raise HTTPException(
                    402, "USMS balansida mablag‘ yetarli emas. Balansni to‘ldiring."
                )
        submitted = True
        result = usms.request("POST", "/send", payload)
    except HTTPException as error:
        # A timeout or 5xx may follow an accepted, billable submission. Preserve its key.
        state = "uncertain" if submitted and error.status_code >= 500 else "rejected"
        with database.write() as connection:
            connection.execute(
                "UPDATE sms_messages SET status=?,error=?,updated_at=? WHERE id=?",
                (state, error.detail, now(), message_id),
            )
            return public_message(
                scoped(connection, "sms_messages", message_id, actor["business_id"])
            )
    with database.write() as connection:
        event(
            connection,
            actor,
            "sms",
            "SMS yuborish so‘rovi",
            row["text"],
            customer_id=row["customer_id"],
        )
        return save_receipt(connection, row, result)


@router.get("/sms/{message_id}")
def status(message_id: str, actor: Actor):
    owner(actor)
    with database.read() as connection:
        row = scoped(connection, "sms_messages", message_id, actor["business_id"])
    if not row["provider_id"] or row["status"] in ("delivered", "rejected", "failed"):
        return public_message(row)
    if row["account_key"] != account_key():
        raise HTTPException(409, "Xabar boshqa USMS hisobidan yuborilgan.")
    result = usms.request("GET", "/status/" + quote(row["provider_id"], safe=""))
    with database.write() as connection:
        current = scoped(connection, "sms_messages", message_id, actor["business_id"])
        if current["status"] in ("delivered", "rejected", "failed"):
            return public_message(current)
        return save_receipt(connection, current, result)
