"""Accounting rules shared by API writes, reports, exports, and imports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import sqlite3
from uuid import uuid4

from fastapi import HTTPException, Request

from . import database, usms

LOCAL_TZ = timezone(timedelta(hours=5), name="Asia/Tashkent")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def today() -> str:
    return datetime.now(LOCAL_TZ).date().isoformat()


def uid() -> str:
    return str(uuid4())


def money(value: str) -> int:
    try:
        cleaned = str(value).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        amount = Decimal(cleaned)
        if not amount.is_finite() or amount <= 0 or amount > Decimal("1000000000000"):
            raise ValueError
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise ValueError
        return int(cents)
    except (InvalidOperation, ValueError):
        raise HTTPException(
            422, "Summani musbat son bilan, ko‘pi bilan 2 kasr xonasida kiriting."
        )


def phone(value: str) -> str:
    if not re.fullmatch(r"\+?[\d\s()\-]+", value, flags=re.ASCII):
        raise HTTPException(422, "Telefonni +998 va 9 ta raqam bilan kiriting.")
    digits = "".join(char for char in value if char.isascii() and char.isdigit())
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        raise HTTPException(422, "Telefonni +998 va 9 ta raqam bilan kiriting.")
    return "+" + digits


def scoped(connection, table: str, resource_id: str, business_id: str) -> dict:
    # Table names are internal constants supplied by routes, never request values.
    row = connection.execute(
        f"SELECT * FROM {table} WHERE id=? AND business_id=?",
        (resource_id, business_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Yozuv topilmadi.")
    return dict(row)


def version_matches(row: dict, version: int) -> None:
    if row["version"] != version:
        raise HTTPException(
            409, "Yozuv yangilangan. Ma’lumotni yangilab, qayta tekshiring."
        )


def event(
    connection,
    actor: dict,
    kind: str,
    title: str,
    details: str = "",
    *,
    customer_id=None,
    debt_id=None,
    amount=None,
):
    connection.execute(
        "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            uid(),
            actor["business_id"],
            actor["id"],
            customer_id,
            debt_id,
            kind,
            title,
            details,
            amount,
            now(),
        ),
    )


def perform(
    actor: dict, request: Request, action: str, payload: dict, callback, *, owner=False
):
    operation_id = request.headers.get("X-Operation-Id", "")
    if not 8 <= len(operation_id) <= 100:
        raise HTTPException(
            400, "Amal identifikatori kerak. Ilovani yangilab qayta urinib ko‘ring."
        )
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    payload_hash = hashlib.sha256(canonical.encode()).hexdigest()
    try:
        with database.write() as connection:
            current_user = connection.execute(
                "SELECT * FROM users WHERE id=? AND active=1", (actor["id"],)
            ).fetchone()
            if current_user is None:
                raise HTTPException(401, "Sessiya yakunlandi. Qayta kiring.")
            required_roles = ("owner",) if owner else ("owner", "manager")
            if current_user["role"] not in required_roles:
                raise HTTPException(
                    403,
                    "Ushbu amal uchun biznes egasi yoki vakolatli menejerga murojaat qiling.",
                )
            previous = connection.execute(
                "SELECT * FROM operations WHERE business_id=? AND operation_id=?",
                (actor["business_id"], operation_id),
            ).fetchone()
            if previous:
                if (
                    previous["action"] != action
                    or previous["payload_hash"] != payload_hash
                    or previous["user_id"] != actor["id"]
                ):
                    raise HTTPException(
                        409, "Amal identifikatori boshqa so‘rovga tegishli."
                    )
                return json.loads(previous["result"])
            result = callback(connection)
            connection.execute(
                "INSERT INTO operations VALUES (?,?,?,?,?,?,?)",
                (
                    actor["business_id"],
                    operation_id,
                    actor["id"],
                    action,
                    payload_hash,
                    json.dumps(result, default=str, ensure_ascii=False),
                    now(),
                ),
            )
            return result
    except sqlite3.IntegrityError as error:
        raise HTTPException(
            409, "Bu telefon yoki hujjat raqami avval ishlatilgan. Yozuvni tekshiring."
        ) from error


def debt_paid(connection, debt_id: str) -> int:
    paid = connection.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE debt_id=?", (debt_id,)
    ).fetchone()[0]
    refunded = connection.execute(
        "SELECT COALESCE(SUM(r.amount),0) FROM refunds r JOIN payments p ON p.id=r.payment_id WHERE p.debt_id=?",
        (debt_id,),
    ).fetchone()[0]
    return paid - refunded


def promise_paid(connection, promise_id: str) -> int:
    return connection.execute(
        "SELECT COALESCE(SUM(amount-reversed_amount),0) FROM promise_allocations WHERE promise_id=?",
        (promise_id,),
    ).fetchone()[0]


def add_debt(connection, actor: dict, data: dict) -> str:
    customer = scoped(
        connection, "customers", data["customer_id"], actor["business_id"]
    )
    if customer["archived"]:
        raise HTTPException(409, "Avval mijozni arxivdan tiklang.")
    issued = str(data["issued_on"])
    due = str(data["due_on"])
    if due < issued or issued > today():
        raise HTTPException(
            422,
            "Savdo sanasi bugungacha, to‘lov muddati esa savdo sanasidan keyin bo‘lsin.",
        )
    amount = money(data["amount"])
    debt_id = uid()
    connection.execute(
        "INSERT INTO debts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            debt_id,
            actor["business_id"],
            customer["id"],
            data["title"],
            amount,
            issued,
            due,
            data.get("reference", "").strip() or None,
            data.get("note", ""),
            0,
            1,
            now(),
            now(),
        ),
    )
    event(
        connection,
        actor,
        "debt",
        "Nasiya qo‘shildi",
        data["title"],
        customer_id=customer["id"],
        debt_id=debt_id,
        amount=amount,
    )
    return debt_id


def add_payment(connection, actor: dict, data: dict) -> str:
    debt = scoped(connection, "debts", data["debt_id"], actor["business_id"])
    amount = money(data["amount"])
    balance = debt["amount"] - debt_paid(connection, debt["id"])
    if debt["archived"] or amount > balance:
        raise HTTPException(
            422, "To‘lov joriy qarz qoldig‘idan oshmasin. Ma’lumotni yangilang."
        )
    paid_on = str(data["paid_on"])
    if not debt["issued_on"] <= paid_on <= today():
        raise HTTPException(
            422, "To‘lov sanasini savdo sanasi va bugun oralig‘ida kiriting."
        )
    payment_id = uid()
    connection.execute(
        "INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?)",
        (
            payment_id,
            actor["business_id"],
            debt["id"],
            amount,
            paid_on,
            data["method"],
            data.get("note", ""),
            actor["id"],
            now(),
        ),
    )
    unallocated = amount
    promises = connection.execute(
        "SELECT * FROM promises WHERE debt_id=? AND cancelled=0 ORDER BY due_on,created_at",
        (debt["id"],),
    ).fetchall()
    for promise in promises:
        outstanding = promise["amount"] - promise_paid(connection, promise["id"])
        allocated = min(outstanding, unallocated)
        if allocated > 0:
            connection.execute(
                "INSERT INTO promise_allocations VALUES (?,?,?,?,0)",
                (uid(), payment_id, promise["id"], allocated),
            )
            unallocated -= allocated
        if unallocated == 0:
            break
    event(
        connection,
        actor,
        "payment",
        "To‘lov qayd etildi",
        data.get("note", ""),
        customer_id=debt["customer_id"],
        debt_id=debt["id"],
        amount=amount,
    )
    return payment_id


def add_promise(connection, actor: dict, data: dict) -> str:
    debt = scoped(connection, "debts", data["debt_id"], actor["business_id"])
    amount = money(data["amount"])
    remaining = debt["amount"] - debt_paid(connection, debt["id"])
    reserved = connection.execute(
        "SELECT p.amount-COALESCE((SELECT SUM(a.amount-a.reversed_amount) FROM promise_allocations a WHERE a.promise_id=p.id),0) AS remaining FROM promises p WHERE p.debt_id=? AND p.cancelled=0",
        (debt["id"],),
    ).fetchall()
    available = remaining - sum(item["remaining"] for item in reserved)
    if debt["archived"] or amount > available:
        raise HTTPException(
            422, "Va’dalar yig‘indisi ochiq qarz qoldig‘iga mos bo‘lsin."
        )
    due = str(data["due_on"])
    if due < today():
        raise HTTPException(422, "Va’da sanasini bugundan boshlab tanlang.")
    promise_id = uid()
    connection.execute(
        "INSERT INTO promises VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            promise_id,
            actor["business_id"],
            debt["id"],
            amount,
            due,
            data.get("note", ""),
            0,
            1,
            now(),
            now(),
        ),
    )
    event(
        connection,
        actor,
        "promise",
        "To‘lov va’dasi qayd etildi",
        due,
        customer_id=debt["customer_id"],
        debt_id=debt["id"],
        amount=amount,
    )
    return promise_id


def snapshot(connection, actor: dict) -> dict:
    from . import voice

    business_id = actor["business_id"]
    customers = [
        dict(row)
        for row in connection.execute(
            "SELECT c.*,COALESCE(v.target,'') AS telegram_username FROM customers c LEFT JOIN voice_contacts v ON v.customer_id=c.id AND v.business_id=c.business_id WHERE c.business_id=? ORDER BY c.name COLLATE NOCASE",
            (business_id,),
        )
    ]
    debts = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM debts WHERE business_id=? ORDER BY due_on,created_at DESC",
            (business_id,),
        )
    ]
    payments = [
        dict(row)
        for row in connection.execute(
            "SELECT p.*,u.name AS recorded_by_name,COALESCE((SELECT SUM(r.amount) FROM refunds r WHERE r.payment_id=p.id),0) AS refunded FROM payments p JOIN users u ON u.id=p.recorded_by WHERE p.business_id=? ORDER BY paid_on DESC,p.created_at DESC",
            (business_id,),
        )
    ]
    refunds = [
        dict(row)
        for row in connection.execute(
            "SELECT r.*,p.debt_id FROM refunds r JOIN payments p ON p.id=r.payment_id WHERE r.business_id=? ORDER BY r.created_at DESC",
            (business_id,),
        )
    ]
    promises = [
        dict(row)
        for row in connection.execute(
            "SELECT p.*,COALESCE((SELECT SUM(a.amount-a.reversed_amount) FROM promise_allocations a WHERE a.promise_id=p.id),0) AS paid FROM promises p WHERE p.business_id=? ORDER BY due_on,created_at",
            (business_id,),
        )
    ]
    disputes = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM disputes WHERE business_id=? ORDER BY created_at DESC",
            (business_id,),
        )
    ]
    debt_map = {row["id"]: row for row in debts}
    customer_map = {row["id"]: row for row in customers}
    handoffs = [
        dict(row)
        for row in connection.execute(
            "SELECT h.*,c.name AS customer_name,v.target FROM voice_handoffs h JOIN customers c ON c.id=h.customer_id JOIN voice_calls v ON v.id=h.call_id WHERE h.business_id=? ORDER BY h.created_at DESC",
            (business_id,),
        )
    ]
    disputed_ids = {item["debt_id"] for item in disputes if not item["resolved"]}
    disputed_ids.update(
        item["debt_id"]
        for item in handoffs
        if not item["resolved"] and item["kind"] == "disputed"
    )
    for debt in debts:
        debt["paid"] = 0
        debt["balance"] = debt["amount"]
        debt["disputed"] = debt["id"] in disputed_ids
    for payment in payments:
        debt = debt_map[payment["debt_id"]]
        debt["paid"] += payment["amount"] - payment["refunded"]
        debt["balance"] -= payment["amount"] - payment["refunded"]
    for debt in debts:
        debt["customer_name"] = customer_map[debt["customer_id"]]["name"]
        debt["overdue"] = debt["balance"] > 0 and debt["due_on"] < today()
    for customer in customers:
        customer.update(balance=0, overdue=0, disputed=False, debt_count=0)
    for debt in debts:
        customer = customer_map[debt["customer_id"]]
        customer["balance"] += debt["balance"]
        customer["overdue"] += debt["balance"] if debt["overdue"] else 0
        customer["disputed"] = customer["disputed"] or debt["disputed"]
        customer["debt_count"] += int(debt["balance"] > 0)
    for promise in promises:
        promise["customer_id"] = debt_map[promise["debt_id"]]["customer_id"]
        if promise["cancelled"]:
            promise["status"] = "cancelled"
        elif promise["paid"] >= promise["amount"]:
            promise["status"] = "fulfilled"
        elif promise["due_on"] < today():
            promise["status"] = "broken"
        elif promise["paid"] > 0:
            promise["status"] = "partial"
        else:
            promise["status"] = "active"
    events = [
        dict(row)
        for row in connection.execute(
            "SELECT e.*,u.name AS actor_name,c.name AS customer_name FROM events e JOIN users u ON u.id=e.user_id LEFT JOIN customers c ON c.id=e.customer_id WHERE e.business_id=? ORDER BY e.created_at DESC LIMIT 500",
            (business_id,),
        )
    ]
    read_keys = {
        row[0]
        for row in connection.execute(
            "SELECT notification_key FROM notification_reads WHERE user_id=?",
            (actor["id"],),
        )
    }
    notifications = []
    for item in handoffs:
        if item["resolved"]:
            continue
        key = f"voice:{item['id']}"
        notifications.append(
            {
                "key": key,
                "kind": "voice",
                "title": "AI murojaatini ko‘rib chiqing",
                "customer_id": item["customer_id"],
                "customer_name": item["customer_name"],
                "amount": debt_map[item["debt_id"]]["balance"],
                "date": item["created_at"][:10],
                "read": key in read_keys,
            }
        )
    for promise in promises:
        if (
            promise["status"] in ("fulfilled", "cancelled")
            or promise["due_on"] > today()
        ):
            continue
        key = f"promise:{promise['id']}:{promise['version']}:{promise['status']}"
        notifications.append(
            {
                "key": key,
                "kind": "promise",
                "title": "Va’da muddati keldi"
                if promise["due_on"] == today()
                else "Va’da muddati o‘tdi",
                "customer_id": promise["customer_id"],
                "customer_name": customer_map[promise["customer_id"]]["name"],
                "amount": promise["amount"] - promise["paid"],
                "date": promise["due_on"],
                "read": key in read_keys,
            }
        )
    for debt in debts:
        if debt["disputed"] or (debt["balance"] > 0 and debt["due_on"] <= today()):
            key = f"debt:{debt['id']}:{debt['version']}:{int(debt['disputed'])}"
            notifications.append(
                {
                    "key": key,
                    "kind": "dispute" if debt["disputed"] else "debt",
                    "title": "E’tirozni ko‘rib chiqing"
                    if debt["disputed"]
                    else "Nasiya muddatini tekshiring",
                    "customer_id": debt["customer_id"],
                    "customer_name": debt["customer_name"],
                    "amount": debt["balance"],
                    "date": debt["due_on"],
                    "read": key in read_keys,
                }
            )
    return {
        "business": dict(
            connection.execute(
                "SELECT * FROM businesses WHERE id=?", (business_id,)
            ).fetchone()
        ),
        "me": public_user(actor),
        "customers": customers,
        "debts": debts,
        "payments": payments,
        "refunds": refunds,
        "promises": promises,
        "disputes": disputes,
        "voice_handoffs": handoffs,
        "events": events,
        "notifications": notifications,
        "today": today(),
        "server_time": now(),
        "voice": voice.describe(connection, actor),
        "capabilities": {
            "calls": voice.enabled_for(connection, business_id),
            "sms": usms.enabled_for(business_id),
            "online_payments": False,
        },
    }


def public_user(user) -> dict:
    return {
        key: user[key]
        for key in ("id", "business_id", "name", "phone", "role", "active")
    }
