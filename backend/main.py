"""HTTP API for the Tushum AI receivables application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import database, imports, schemas, sms, voice, web_updates
from .domain import (
    add_debt,
    add_payment,
    add_promise,
    debt_paid,
    event,
    money,
    now,
    perform,
    phone,
    promise_paid,
    public_user,
    scoped,
    snapshot,
    today,
    uid,
    version_matches,
)
from .security import (
    check_attempts,
    create_session,
    current_user,
    hash_password,
    token_hash,
    verify_password,
)

Actor = Annotated[dict, Depends(current_user)]


@asynccontextmanager
async def lifespan(application):
    database.initialize()
    voice.initialize()
    from .voice_runtime import manager

    await manager.start()
    try:
        yield
    finally:
        await manager.stop()


app = FastAPI(title="Tushum AI", version="1.0.0", lifespan=lifespan)
app.include_router(sms.router)
app.include_router(voice.router)
app.include_router(web_updates.router)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Operation-Id"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    fields = ", ".join(str(item["loc"][-1]) for item in error.errors()[:3])
    return JSONResponse(
        status_code=422,
        content={
            "detail": f"Maydonlarni tekshiring — {fields}. Kiritilgan qiymat yoki sana formati mos kelmadi."
        },
    )


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/") or request.url.path in (
        "/",
        "/index.html",
        "/flutter_bootstrap.js",
        "/main.dart.js",
    ):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "Tushum AI",
        "version": "1.0.0",
        "today": today(),
        "voice": {"ready": voice.runtime["ready"], "state": voice.runtime["state"]},
    }


def new_account(
    connection, *, name: str, number: str, password: str, business_name: str, demo=False
):
    business_id, user_id = uid(), uid()
    connection.execute(
        "INSERT INTO businesses(id,name,sector,phone,address,created_at,is_demo) VALUES (?,?,?,?,?,?,?)",
        (business_id, business_name, "", number, "", now(), int(demo)),
    )
    connection.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?,1,?)",
        (user_id, business_id, name, number, hash_password(password), "owner", now()),
    )
    actor = dict(
        connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    )
    return actor, create_session(connection, user_id)


@app.post("/api/auth/register")
def register(data: schemas.Registration, request: Request):
    number = phone(data.phone)
    check_attempts("register:" + (request.client.host if request.client else "local"))
    try:
        with database.write() as connection:
            actor, token = new_account(
                connection,
                name=data.name,
                number=number,
                password=data.password,
                business_name=data.business_name,
            )
            event(
                connection,
                actor,
                "account",
                "Biznes akkaunti yaratildi",
                data.business_name,
            )
            return {"token": token, "user": public_user(actor)}
    except sqlite3.IntegrityError:
        raise HTTPException(
            409, "Bu telefon bilan akkaunt ochilgan. Kirish bo‘limidan foydalaning."
        )


@app.post("/api/auth/login")
def login(data: schemas.Login, request: Request):
    number = phone(data.phone)
    identifier = (request.client.host if request.client else "local") + ":" + number
    check_attempts(identifier)
    with database.write() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE phone=? AND active=1", (number,)
        ).fetchone()
        encoded = (
            row["password_hash"]
            if row
            else "scrypt$00000000000000000000000000000000$" + "0" * 64
        )
        valid = verify_password(data.password, encoded)
        if not row or not valid:
            raise HTTPException(401, "Telefon yoki parol mos kelmadi.")
        connection.execute(
            "DELETE FROM login_attempts WHERE identifier=?", (identifier,)
        )
        return {
            "token": create_session(connection, row["id"]),
            "user": public_user(row),
        }


@app.post("/api/auth/demo")
def demo(request: Request):
    check_attempts("demo:" + (request.client.host if request.client else "local"))
    with database.write() as connection:
        number = "+99800" + str(secrets.randbelow(10_000_000)).zfill(7)
        actor, token = new_account(
            connection,
            name="Demo tadbirkor",
            number=number,
            password=secrets.token_urlsafe(24),
            business_name="Baraka Stroy",
            demo=True,
        )
        day = date.fromisoformat(today())
        sample = [
            ("Akmal Yo‘ldoshev", "Qurilish savdo", "4500000", -5),
            ("Sardor Aliyev", "Sardor Market", "2800000", 0),
            ("Nodira Karimova", "Karimova Savdo", "1900000", -2),
            ("Rustam Ergashev", "Rustam Qurilish", "3200000", -12),
            ("Dilshod Nazarov", "Nazarov Do‘koni", "850000", 7),
            ("Aziza To‘xtayeva", "Aziza Savdo", "6500000", -35),
            ("Javohir Sobirov", "JS Trade", "1200000", 4),
            ("Malika Rasulova", "Malika Market", "3700000", -8),
        ]
        for index, (name, company, amount, offset) in enumerate(sample):
            customer_id = uid()
            stamp = now()
            connection.execute(
                "INSERT INTO customers VALUES (?,?,?,?,?,?,1,0,?,?)",
                (
                    customer_id,
                    actor["business_id"],
                    name,
                    "+99890000" + str(index + 1).zfill(4),
                    company,
                    "Sun’iy demo ma’lumoti",
                    stamp,
                    stamp,
                ),
            )
            issued = (day - timedelta(days=max(45, abs(offset) + 5))).isoformat()
            debt_id = add_debt(
                connection,
                actor,
                {
                    "customer_id": customer_id,
                    "title": "Qurilish mollari",
                    "amount": amount,
                    "issued_on": issued,
                    "due_on": (day + timedelta(days=offset)).isoformat(),
                    "reference": f"DEMO-{1042 + index}",
                    "note": "Demo hisob",
                },
            )
            if index in (3, 5, 7):
                payment_id = add_payment(
                    connection,
                    actor,
                    {
                        "debt_id": debt_id,
                        "amount": "1000000",
                        "paid_on": (day - timedelta(days=1)).isoformat(),
                        "method": "cash",
                        "note": "Demo qisman to‘lov",
                    },
                )
            if index in (0, 3):
                add_promise(
                    connection,
                    actor,
                    {
                        "debt_id": debt_id,
                        "amount": "1000000",
                        "due_on": (day + timedelta(days=1)).isoformat(),
                        "note": "Telefon orqali qo‘lda qayd etilgan demo va’da",
                    },
                )
            if index == 2:
                connection.execute(
                    "INSERT INTO disputes VALUES (?,?,?,?,?,0,1,?,?)",
                    (
                        uid(),
                        actor["business_id"],
                        debt_id,
                        "Mijoz yetkazilgan mahsulot miqdorini tekshirishni so‘radi.",
                        "",
                        now(),
                        now(),
                    ),
                )
        event(
            connection,
            actor,
            "account",
            "Demo ma’lumotlar tayyorlandi",
            "Bu akkauntdagi yozuvlar sun’iy.",
        )
        return {"token": token, "user": public_user(actor)}


@app.post("/api/auth/logout")
def logout(actor: Actor, request: Request):
    token = request.headers.get("Authorization", "")[7:]
    with database.write() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE token_hash=? AND user_id=?",
            (token_hash(token), actor["id"]),
        )
    return {"ok": True}


@app.post("/api/auth/password")
def change_password(data: schemas.PasswordChange, request: Request, actor: Actor):
    def change(connection):
        user = connection.execute(
            "SELECT * FROM users WHERE id=?", (actor["id"],)
        ).fetchone()
        if not verify_password(data.current_password, user["password_hash"]):
            raise HTTPException(422, "Amaldagi parol mos kelmadi.")
        connection.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(data.new_password), actor["id"]),
        )
        token = request.headers.get("Authorization", "")[7:]
        connection.execute(
            "DELETE FROM sessions WHERE user_id=? AND token_hash<>?",
            (actor["id"], token_hash(token)),
        )
        event(connection, actor, "account", "Parol yangilandi")
        return {"ok": True}

    # A viewer may also change their own password.
    with database.write() as connection:
        return change(connection)


@app.get("/api/workspace")
def workspace(actor: Actor):
    with database.read() as connection:
        connection.execute("BEGIN")
        return snapshot(connection, actor)


@app.patch("/api/business")
def update_business(data: schemas.BusinessUpdate, request: Request, actor: Actor):
    def change(connection):
        connection.execute(
            "UPDATE businesses SET name=?,phone=?,sector=?,address=? WHERE id=?",
            (
                data.name,
                phone(data.phone),
                data.sector,
                data.address,
                actor["business_id"],
            ),
        )
        event(connection, actor, "settings", "Biznes profili yangilandi", data.name)
        return {"ok": True}

    return perform(actor, request, "business", data.model_dump(), change, owner=True)


@app.get("/api/team")
def team(actor: Actor):
    if actor["role"] != "owner":
        raise HTTPException(403, "Jamoani biznes egasi boshqaradi.")
    with database.read() as connection:
        return [
            public_user(row)
            for row in connection.execute(
                "SELECT * FROM users WHERE business_id=? ORDER BY created_at",
                (actor["business_id"],),
            )
        ]


@app.post("/api/team")
def add_team_member(data: schemas.TeamInput, request: Request, actor: Actor):
    def change(connection):
        user_id = uid()
        connection.execute(
            "INSERT INTO users VALUES (?,?,?,?,?,?,1,?)",
            (
                user_id,
                actor["business_id"],
                data.name,
                phone(data.phone),
                hash_password(data.password),
                data.role,
                now(),
            ),
        )
        event(connection, actor, "team", "Xodim qo‘shildi", data.name)
        return {"id": user_id}

    return perform(actor, request, "team:add", data.model_dump(), change, owner=True)


@app.patch("/api/team/{user_id}")
def update_team_member(
    user_id: str, data: schemas.TeamUpdate, request: Request, actor: Actor
):
    def change(connection):
        user = scoped(connection, "users", user_id, actor["business_id"])
        if user["role"] == "owner":
            raise HTTPException(422, "Biznes egasining vakolati alohida boshqariladi.")
        connection.execute(
            "UPDATE users SET role=?,active=? WHERE id=?",
            (data.role, int(data.active), user_id),
        )
        if not data.active:
            connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        event(connection, actor, "team", "Xodim vakolati yangilandi", user["name"])
        return {"ok": True}

    return perform(
        actor, request, "team:" + user_id, data.model_dump(), change, owner=True
    )


@app.post("/api/customers")
def create_customer(data: schemas.CustomerInput, request: Request, actor: Actor):
    def change(connection):
        customer_id = uid()
        connection.execute(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?,0,?,?)",
            (
                customer_id,
                actor["business_id"],
                data.name,
                phone(data.phone),
                data.company,
                data.note,
                int(data.contact_allowed),
                now(),
                now(),
            ),
        )
        event(
            connection,
            actor,
            "customer",
            "Mijoz qo‘shildi",
            data.name,
            customer_id=customer_id,
        )
        return {"id": customer_id}

    return perform(actor, request, "customer:add", data.model_dump(), change)


@app.patch("/api/customers/{customer_id}")
def update_customer(
    customer_id: str, data: schemas.CustomerInput, request: Request, actor: Actor
):
    def change(connection):
        scoped(connection, "customers", customer_id, actor["business_id"])
        connection.execute(
            "UPDATE customers SET name=?,phone=?,company=?,note=?,contact_allowed=?,updated_at=? WHERE id=?",
            (
                data.name,
                phone(data.phone),
                data.company,
                data.note,
                int(data.contact_allowed),
                now(),
                customer_id,
            ),
        )
        event(
            connection,
            actor,
            "customer",
            "Mijoz ma’lumoti yangilandi",
            data.name,
            customer_id=customer_id,
        )
        return {"id": customer_id}

    return perform(actor, request, "customer:" + customer_id, data.model_dump(), change)


@app.post("/api/customers/{customer_id}/archive")
def archive_customer(
    customer_id: str, data: schemas.ArchiveInput, request: Request, actor: Actor
):
    def change(connection):
        customer = scoped(connection, "customers", customer_id, actor["business_id"])
        debts = connection.execute(
            "SELECT * FROM debts WHERE customer_id=?", (customer_id,)
        ).fetchall()
        if data.archived and any(
            row["amount"] - debt_paid(connection, row["id"]) > 0 for row in debts
        ):
            raise HTTPException(
                422, "Mijozni arxivlash uchun avval ochiq qarzlarni yoping."
            )
        connection.execute(
            "UPDATE customers SET archived=?,updated_at=? WHERE id=?",
            (int(data.archived), now(), customer_id),
        )
        event(
            connection,
            actor,
            "customer",
            "Mijoz arxivlandi" if data.archived else "Mijoz arxivdan tiklandi",
            customer["name"],
            customer_id=customer_id,
        )
        return {"ok": True}

    return perform(
        actor, request, "customer:archive:" + customer_id, data.model_dump(), change
    )


@app.post("/api/customers/{customer_id}/notes")
def add_note(customer_id: str, data: schemas.NoteInput, request: Request, actor: Actor):
    def change(connection):
        scoped(connection, "customers", customer_id, actor["business_id"])
        event(
            connection,
            actor,
            "note",
            "Izoh qo‘shildi",
            data.text,
            customer_id=customer_id,
        )
        return {"ok": True}

    return perform(actor, request, "note:" + customer_id, data.model_dump(), change)


@app.post("/api/debts")
def create_debt(data: schemas.DebtInput, request: Request, actor: Actor):
    return perform(
        actor,
        request,
        "debt:add",
        data.model_dump(),
        lambda connection: {"id": add_debt(connection, actor, data.model_dump())},
    )


@app.patch("/api/debts/{debt_id}")
def update_debt(debt_id: str, data: schemas.DebtUpdate, request: Request, actor: Actor):
    def change(connection):
        debt = scoped(connection, "debts", debt_id, actor["business_id"])
        version_matches(debt, data.version)
        customer = scoped(
            connection, "customers", debt["customer_id"], actor["business_id"]
        )
        if customer["archived"]:
            raise HTTPException(409, "Avval mijozni arxivdan tiklang.")
        if data.customer_id != debt["customer_id"] or debt["archived"]:
            raise HTTPException(
                422, "Hisob egasini saqlang va arxiv holatini tekshiring."
            )
        amount = money(data.amount)
        paid = debt_paid(connection, debt_id)
        reserved = connection.execute(
            "SELECT COALESCE(SUM(p.amount-COALESCE((SELECT SUM(a.amount-a.reversed_amount) FROM promise_allocations a WHERE a.promise_id=p.id),0)),0) FROM promises p WHERE p.debt_id=? AND p.cancelled=0",
            (debt_id,),
        ).fetchone()[0]
        if amount < paid + reserved:
            raise HTTPException(
                422, "Yangi summa to‘lovlar va amaldagi va’dalarni qoplashi kerak."
            )
        if amount != debt["amount"] and len(data.reason) < 3:
            raise HTTPException(422, "Summa tuzatilishining sababini kiriting.")
        has_payments = connection.execute(
            "SELECT 1 FROM payments WHERE debt_id=? LIMIT 1", (debt_id,)
        ).fetchone()
        if str(data.issued_on) != debt["issued_on"] and has_payments:
            raise HTTPException(422, "To‘lovli hisobning savdo sanasini saqlang.")
        if data.due_on < data.issued_on or str(data.issued_on) > today():
            raise HTTPException(422, "Savdo va to‘lov sanalarini tekshiring.")
        connection.execute(
            "UPDATE debts SET title=?,amount=?,issued_on=?,due_on=?,reference=?,note=?,version=version+1,updated_at=? WHERE id=?",
            (
                data.title,
                amount,
                str(data.issued_on),
                str(data.due_on),
                data.reference or None,
                data.note,
                now(),
                debt_id,
            ),
        )
        event(
            connection,
            actor,
            "debt",
            "Nasiya yozuvi yangilandi",
            data.reason or data.title,
            customer_id=debt["customer_id"],
            debt_id=debt_id,
            amount=amount - debt["amount"],
        )
        return {"id": debt_id}

    return perform(actor, request, "debt:" + debt_id, data.model_dump(), change)


@app.post("/api/debts/{debt_id}/archive")
def archive_debt(
    debt_id: str, data: schemas.ArchiveInput, request: Request, actor: Actor
):
    def change(connection):
        debt = scoped(connection, "debts", debt_id, actor["business_id"])
        if data.archived and debt["amount"] != debt_paid(connection, debt_id):
            raise HTTPException(422, "Hisobni arxivlash uchun qoldiqni yoping.")
        connection.execute(
            "UPDATE debts SET archived=?,version=version+1,updated_at=? WHERE id=?",
            (int(data.archived), now(), debt_id),
        )
        event(
            connection,
            actor,
            "debt",
            "Hisob arxiv holati yangilandi",
            customer_id=debt["customer_id"],
            debt_id=debt_id,
        )
        return {"ok": True}

    return perform(actor, request, "debt:archive:" + debt_id, data.model_dump(), change)


@app.post("/api/payments")
def create_payment(data: schemas.PaymentInput, request: Request, actor: Actor):
    return perform(
        actor,
        request,
        "payment:add",
        data.model_dump(),
        lambda connection: {"id": add_payment(connection, actor, data.model_dump())},
    )


@app.post("/api/payments/{payment_id}/refund")
def refund_payment(
    payment_id: str, data: schemas.RefundInput, request: Request, actor: Actor
):
    def change(connection):
        payment = scoped(connection, "payments", payment_id, actor["business_id"])
        amount = money(data.amount)
        refunded = connection.execute(
            "SELECT COALESCE(SUM(amount),0) FROM refunds WHERE payment_id=?",
            (payment_id,),
        ).fetchone()[0]
        if amount > payment["amount"] - refunded:
            raise HTTPException(
                422, "Qaytarim to‘lovning qaytarilmagan qismidan oshmasin."
            )
        if not payment["paid_on"] <= str(data.refunded_on) <= today():
            raise HTTPException(
                422, "Qaytarim sanasini to‘lov sanasi va bugun oralig‘ida tanlang."
            )
        allocations = connection.execute(
            "SELECT * FROM promise_allocations WHERE payment_id=? ORDER BY rowid DESC",
            (payment_id,),
        ).fetchall()
        allocated = sum(row["amount"] - row["reversed_amount"] for row in allocations)
        remaining_to_reverse = max(
            0, amount - (payment["amount"] - refunded - allocated)
        )
        for allocation in allocations:
            take = min(
                remaining_to_reverse,
                allocation["amount"] - allocation["reversed_amount"],
            )
            if take:
                connection.execute(
                    "UPDATE promise_allocations SET reversed_amount=reversed_amount+? WHERE id=?",
                    (take, allocation["id"]),
                )
                remaining_to_reverse -= take
        refund_id = uid()
        connection.execute(
            "INSERT INTO refunds VALUES (?,?,?,?,?,?,?,?)",
            (
                refund_id,
                actor["business_id"],
                payment_id,
                amount,
                str(data.refunded_on),
                data.reason,
                actor["id"],
                now(),
            ),
        )
        debt = scoped(connection, "debts", payment["debt_id"], actor["business_id"])
        connection.execute(
            "UPDATE debts SET archived=0,version=version+1 WHERE id=?", (debt["id"],)
        )
        connection.execute(
            "UPDATE customers SET archived=0 WHERE id=?", (debt["customer_id"],)
        )
        event(
            connection,
            actor,
            "refund",
            "To‘lov qaytarimi qayd etildi",
            data.reason,
            customer_id=debt["customer_id"],
            debt_id=debt["id"],
            amount=-amount,
        )
        return {"id": refund_id}

    return perform(
        actor, request, "refund:" + payment_id, data.model_dump(), change, owner=True
    )


@app.post("/api/promises")
def create_promise(data: schemas.PromiseInput, request: Request, actor: Actor):
    return perform(
        actor,
        request,
        "promise:add",
        data.model_dump(),
        lambda connection: {"id": add_promise(connection, actor, data.model_dump())},
    )


@app.patch("/api/promises/{promise_id}")
def update_promise(
    promise_id: str, data: schemas.PromiseUpdate, request: Request, actor: Actor
):
    def change(connection):
        promise = scoped(connection, "promises", promise_id, actor["business_id"])
        version_matches(promise, data.version)
        if promise["cancelled"] or promise["debt_id"] != data.debt_id:
            raise HTTPException(422, "Va’da hisobini va holatini tekshiring.")
        paid = promise_paid(connection, promise_id)
        amount = money(data.amount)
        debt = scoped(connection, "debts", data.debt_id, actor["business_id"])
        others = connection.execute(
            "SELECT * FROM promises WHERE debt_id=? AND id<>? AND cancelled=0",
            (data.debt_id, promise_id),
        ).fetchall()
        reserved = sum(
            row["amount"] - promise_paid(connection, row["id"]) for row in others
        )
        if amount < paid or amount - paid + reserved > debt["amount"] - debt_paid(
            connection, debt["id"]
        ):
            raise HTTPException(
                422, "Va’da summasini to‘lovlar va qolgan qarz bilan moslang."
            )
        if str(data.due_on) < today():
            raise HTTPException(422, "Va’da sanasini bugundan boshlab tanlang.")
        connection.execute(
            "UPDATE promises SET amount=?,due_on=?,note=?,version=version+1,updated_at=? WHERE id=?",
            (amount, str(data.due_on), data.note, now(), promise_id),
        )
        event(
            connection,
            actor,
            "promise",
            "To‘lov va’dasi yangilandi",
            str(data.due_on),
            customer_id=debt["customer_id"],
            debt_id=debt["id"],
            amount=amount,
        )
        return {"id": promise_id}

    return perform(actor, request, "promise:" + promise_id, data.model_dump(), change)


@app.post("/api/promises/{promise_id}/cancel")
def cancel_promise(
    promise_id: str, data: schemas.VersionInput, request: Request, actor: Actor
):
    def change(connection):
        promise = scoped(connection, "promises", promise_id, actor["business_id"])
        version_matches(promise, data.version)
        connection.execute(
            "UPDATE promises SET cancelled=1,version=version+1,updated_at=? WHERE id=?",
            (now(), promise_id),
        )
        debt = scoped(connection, "debts", promise["debt_id"], actor["business_id"])
        event(
            connection,
            actor,
            "promise",
            "Va’da bekor qilindi",
            customer_id=debt["customer_id"],
            debt_id=debt["id"],
        )
        return {"ok": True}

    return perform(
        actor, request, "promise:cancel:" + promise_id, data.model_dump(), change
    )


@app.post("/api/disputes")
def create_dispute(data: schemas.DisputeInput, request: Request, actor: Actor):
    def change(connection):
        debt = scoped(connection, "debts", data.debt_id, actor["business_id"])
        if connection.execute(
            "SELECT id FROM disputes WHERE debt_id=? AND resolved=0", (debt["id"],)
        ).fetchone():
            raise HTTPException(
                409, "Bu hisobda ochiq e’tiroz bor. Uni ko‘rib chiqing."
            )
        dispute_id = uid()
        connection.execute(
            "INSERT INTO disputes VALUES (?,?,?,?,?,0,1,?,?)",
            (
                dispute_id,
                actor["business_id"],
                debt["id"],
                data.reason,
                "",
                now(),
                now(),
            ),
        )
        event(
            connection,
            actor,
            "dispute",
            "E’tiroz qayd etildi",
            data.reason,
            customer_id=debt["customer_id"],
            debt_id=debt["id"],
        )
        return {"id": dispute_id}

    return perform(actor, request, "dispute:add", data.model_dump(), change)


@app.post("/api/disputes/{dispute_id}/resolve")
def resolve_dispute(
    dispute_id: str, data: schemas.ResolutionInput, request: Request, actor: Actor
):
    def change(connection):
        dispute = scoped(connection, "disputes", dispute_id, actor["business_id"])
        version_matches(dispute, data.version)
        if dispute["resolved"]:
            raise HTTPException(409, "E’tiroz avval yopilgan.")
        connection.execute(
            "UPDATE disputes SET resolution=?,resolved=1,version=version+1,updated_at=? WHERE id=?",
            (data.resolution, now(), dispute_id),
        )
        debt = scoped(connection, "debts", dispute["debt_id"], actor["business_id"])
        event(
            connection,
            actor,
            "dispute",
            "E’tiroz hal qilindi",
            data.resolution,
            customer_id=debt["customer_id"],
            debt_id=debt["id"],
        )
        return {"ok": True}

    return perform(
        actor, request, "dispute:resolve:" + dispute_id, data.model_dump(), change
    )


@app.post("/api/notifications/read")
def mark_notifications(data: schemas.NotificationRead, actor: Actor):
    with database.write() as connection:
        for key in data.keys:
            if len(key) > 200:
                raise HTTPException(422, "Bildirishnoma identifikatorini tekshiring.")
            connection.execute(
                "INSERT OR IGNORE INTO notification_reads VALUES (?,?)",
                (actor["id"], key),
            )
    return {"ok": True}


@app.post("/api/imports/preview")
async def import_preview(
    actor: Actor, file: UploadFile = File(...), mapping: str = Form(default="{}")
):
    if actor["role"] == "viewer":
        raise HTTPException(403, "Importni biznes egasi yoki menejer bajaradi.")
    content = await file.read(10 * 1024 * 1024 + 1)
    try:
        selected_mapping = json.loads(mapping)
        if not isinstance(selected_mapping, dict):
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(422, "Ustunlar mosligini tekshiring.")
    with database.write() as connection:
        return imports.preview(
            connection, actor, content, file.filename or "", selected_mapping
        )


@app.post("/api/imports/{import_id}/commit")
def import_commit(
    import_id: str, data: schemas.ImportCommit, request: Request, actor: Actor
):
    return perform(
        actor,
        request,
        "import:" + import_id,
        data.model_dump(),
        lambda connection: imports.commit_import(
            connection, actor, import_id, data.rows, data.accept_duplicates
        ),
    )


@app.get("/api/imports/template")
def import_template(actor: Actor):
    return spreadsheet(
        imports.workbook_bytes(
            {
                "Nasiyalar": [
                    [
                        "Mijoz ismi",
                        "Telegram username",
                        "Do‘kon",
                        "Summa",
                        "To‘lov muddati",
                    ],
                    [
                        "Akmal Namuna",
                        "@akmal_namuna",
                        "Baraka Market",
                        1500000,
                        (date.fromisoformat(today()) + timedelta(days=7)).isoformat(),
                    ],
                ]
            }
        ),
        "tushum-import-namuna.xlsx",
    )


def spreadsheet(content: bytes, filename: str):
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def report_data(data: dict, start: str, end: str) -> dict:
    if start > end:
        raise HTTPException(422, "Davr boshlanishi yakunidan oldin bo‘lsin.")
    payments = [item for item in data["payments"] if start <= item["paid_on"] <= end]
    refunds = [item for item in data["refunds"] if start <= item["refunded_on"] <= end]
    open_debts = [item for item in data["debts"] if item["balance"] > 0]
    due_promises = [
        item
        for item in data["promises"]
        if start <= item["due_on"] <= end and not item["cancelled"]
    ]
    trend = {}
    methods = {"cash": 0, "transfer": 0, "terminal": 0, "other": 0}
    for item in payments:
        trend[item["paid_on"]] = trend.get(item["paid_on"], 0) + item["amount"]
        methods[item["method"]] += item["amount"]
    payment_map = {item["id"]: item for item in data["payments"]}
    for item in refunds:
        trend[item["refunded_on"]] = trend.get(item["refunded_on"], 0) - item["amount"]
        methods[payment_map[item["payment_id"]]["method"]] -= item["amount"]
    aging = {
        "Muddati kelmagan": 0,
        "1–7 kun": 0,
        "8–30 kun": 0,
        "31–60 kun": 0,
        "60 kundan ko‘p": 0,
    }
    current_day = date.fromisoformat(data["today"])
    for debt in open_debts:
        age = (current_day - date.fromisoformat(debt["due_on"])).days
        bucket = (
            "Muddati kelmagan"
            if age <= 0
            else "1–7 kun"
            if age <= 7
            else "8–30 kun"
            if age <= 30
            else "31–60 kun"
            if age <= 60
            else "60 kundan ko‘p"
        )
        aging[bucket] += debt["balance"]
    return {
        "start": start,
        "end": end,
        "gross_received": sum(item["amount"] for item in payments),
        "refunded": sum(item["amount"] for item in refunds),
        "net_received": sum(item["amount"] for item in payments)
        - sum(item["amount"] for item in refunds),
        "current_balance": sum(item["balance"] for item in open_debts),
        "current_overdue": sum(
            item["balance"] for item in open_debts if item["overdue"]
        ),
        "payment_count": len(payments),
        "promise_count": len(due_promises),
        "fulfilled_promises": sum(
            item["status"] == "fulfilled" for item in due_promises
        ),
        "trend": [
            {"date": day, "amount": value} for day, value in sorted(trend.items())
        ],
        "aging": aging,
        "methods": methods,
    }


@app.get("/api/reports")
def reports(actor: Actor, start: date | None = None, end: date | None = None):
    with database.read() as connection:
        connection.execute("BEGIN")
        data = snapshot(connection, actor)
    return report_data(
        data,
        str(start or date.fromisoformat(today()).replace(day=1)),
        str(end or today()),
    )


@app.get("/api/export")
def export(actor: Actor):
    with database.read() as connection:
        connection.execute("BEGIN")
        data = snapshot(connection, actor)
    customer_map = {item["id"]: item for item in data["customers"]}
    debt_map = {item["id"]: item for item in data["debts"]}
    sheets = {
        "Mijozlar": [
            ["ID", "Ism", "Telefon", "Korxona", "Qoldiq UZS", "Izoh", "Arxiv"]
        ],
        "Nasiyalar": [
            [
                "ID",
                "Mijoz",
                "Hujjat",
                "Nasiya",
                "Summa UZS",
                "To‘langan UZS",
                "Qoldiq UZS",
                "Savdo sanasi",
                "Muddat",
                "Izoh",
            ]
        ],
        "Tolovlar": [
            [
                "ID",
                "Mijoz",
                "Hisob ID",
                "Summa UZS",
                "Qaytarim UZS",
                "Sana",
                "Usul",
                "Tasdiqlagan",
                "Izoh",
            ]
        ],
        "Vadalar": [
            ["ID", "Mijoz", "Summa UZS", "Bajarilgan UZS", "Sana", "Holat", "Izoh"]
        ],
        "Qaytarimlar": [["ID", "To‘lov ID", "Summa UZS", "Sana", "Sabab"]],
    }
    for item in data["customers"]:
        sheets["Mijozlar"].append(
            [
                item["id"],
                item["name"],
                item["phone"],
                item["company"],
                item["balance"] / 100,
                item["note"],
                bool(item["archived"]),
            ]
        )
    for item in data["debts"]:
        sheets["Nasiyalar"].append(
            [
                item["id"],
                item["customer_name"],
                item["reference"],
                item["title"],
                item["amount"] / 100,
                item["paid"] / 100,
                item["balance"] / 100,
                item["issued_on"],
                item["due_on"],
                item["note"],
            ]
        )
    for item in data["payments"]:
        debt = debt_map[item["debt_id"]]
        sheets["Tolovlar"].append(
            [
                item["id"],
                debt["customer_name"],
                debt["id"],
                item["amount"] / 100,
                item["refunded"] / 100,
                item["paid_on"],
                item["method"],
                item["recorded_by_name"],
                item["note"],
            ]
        )
    for item in data["promises"]:
        sheets["Vadalar"].append(
            [
                item["id"],
                customer_map[item["customer_id"]]["name"],
                item["amount"] / 100,
                item["paid"] / 100,
                item["due_on"],
                item["status"],
                item["note"],
            ]
        )
    for item in data["refunds"]:
        sheets["Qaytarimlar"].append(
            [
                item["id"],
                item["payment_id"],
                item["amount"] / 100,
                item["refunded_on"],
                item["reason"],
            ]
        )
    return spreadsheet(imports.workbook_bytes(sheets), f"tushum-hisobot-{today()}.xlsx")


@app.get("/api/activity")
def activity(actor: Actor, before: str = "", kind: str = "", customer_id: str = ""):
    conditions = ["e.business_id=?"]
    parameters = [actor["business_id"]]
    with database.read() as connection:
        if before:
            cursor = scoped(connection, "events", before, actor["business_id"])
            conditions.append("(e.created_at < ? OR (e.created_at = ? AND e.id < ?))")
            parameters.extend(
                [cursor["created_at"], cursor["created_at"], cursor["id"]]
            )
        if kind:
            conditions.append("e.kind=?")
            parameters.append(kind)
        if customer_id:
            scoped(connection, "customers", customer_id, actor["business_id"])
            conditions.append("e.customer_id=?")
            parameters.append(customer_id)
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT e.*,u.name AS actor_name,c.name AS customer_name "
                "FROM events e JOIN users u ON u.id=e.user_id "
                "LEFT JOIN customers c ON c.id=e.customer_id WHERE "
                + " AND ".join(conditions)
                + " ORDER BY e.created_at DESC,e.id DESC LIMIT 101",
                parameters,
            )
        ]
    return {"items": rows[:100], "next": rows[99]["id"] if len(rows) > 100 else None}


@app.get("/api/backup")
def backup(actor: Actor):
    if actor["role"] != "owner":
        raise HTTPException(403, "Zaxira nusxasini biznes egasi yuklaydi.")
    with database.read() as connection:
        connection.execute("BEGIN")
        data = snapshot(connection, actor)
        data["events"] = [
            dict(row)
            for row in connection.execute(
                "SELECT e.*,u.name AS actor_name,c.name AS customer_name FROM events e "
                "JOIN users u ON u.id=e.user_id LEFT JOIN customers c ON c.id=e.customer_id "
                "WHERE e.business_id=? ORDER BY e.created_at DESC,e.id DESC",
                (actor["business_id"],),
            )
        ]
        data["team"] = [
            public_user(row)
            for row in connection.execute(
                "SELECT * FROM users WHERE business_id=? ORDER BY created_at",
                (actor["business_id"],),
            )
        ]
        data["sms_messages"] = [
            sms.public_message(dict(row))
            for row in connection.execute(
                "SELECT * FROM sms_messages WHERE business_id=? ORDER BY created_at DESC",
                (actor["business_id"],),
            )
        ]
        data["voice_calls"] = [
            voice.public_call(row)
            for row in connection.execute(
                "SELECT * FROM voice_calls WHERE business_id=? ORDER BY created_at DESC",
                (actor["business_id"],),
            )
        ]
        data["voice_transcript"] = [
            dict(row)
            for row in connection.execute(
                "SELECT t.* FROM voice_transcript t JOIN voice_calls v ON v.id=t.call_id WHERE v.business_id=? ORDER BY t.seq",
                (actor["business_id"],),
            )
        ]
        data["voice_contacts"] = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM voice_contacts WHERE business_id=?",
                (actor["business_id"],),
            )
        ]
        data["voice_profiles"] = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM voice_profiles WHERE business_id=?",
                (actor["business_id"],),
            )
        ]
        data["voice_handoffs"] = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM voice_handoffs WHERE business_id=?",
                (actor["business_id"],),
            )
        ]
    data["format_version"] = 1
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="tushum-backup-{today()}.json"'
        },
    )


WEB_BUILD = Path(__file__).resolve().parents[1] / "mobile" / "build" / "web"
if WEB_BUILD.exists():
    app.mount("/", StaticFiles(directory=WEB_BUILD, html=True), name="mobile-preview")
