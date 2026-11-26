"""Call boundaries, financial confirmation, cancellation and tenant isolation."""

import os
import unittest
from datetime import date, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from . import voice
from .domain import today
from .main import app


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "TUSHUM_DATABASE": self.directory.name + "/voice.db",
                "TUSHUM_VOICE_SETUP_CODE": "test-activation-secret-12345",
                "TUSHUM_VOICE_TARGETS": "nishonboyv7",
                "TUSHUM_VOICE_LOCAL": "0",
                "TUSHUM_TELEGRAM_SESSION": "",
                "TUSHUM_VOICE_OWNER_PHONE": "",
                "TUSHUM_VOICE_CUSTOM_TARGETS": "0",
            },
        )
        self.env.start()
        self.client = TestClient(app).__enter__()
        self.auth = self.client.post(
            "/api/auth/register",
            json={
                "name": "Owner",
                "business_name": "Test Savdo",
                "phone": "+998901234567",
                "password": "Password12345",
            },
        ).json()
        self.token = self.auth["token"]
        self.business_id = self.auth["user"]["business_id"]
        self.customer = self.post(
            "/api/customers", {"name": "Test Mijoz", "phone": "+998901111111"}
        ).json()["id"]
        self.debt = self.post(
            "/api/debts",
            {
                "customer_id": self.customer,
                "title": "Qurilish mollari",
                "amount": "1000000",
                "issued_on": today(),
                "due_on": today(),
            },
        ).json()["id"]
        result = self.post(
            "/api/voice/activate", {"code": "test-activation-secret-12345"}
        )
        self.assertEqual(result.status_code, 200, result.text)
        result = self.client.put(
            "/api/voice/profile",
            json={
                "business_name": "Test Savdo",
                "manager_name": "Owner",
                "phone": "+998901234567",
            },
            headers=self.headers(),
        )
        self.assertEqual(result.status_code, 200, result.text)
        voice.runtime.update(ready=True, state="ready")

    def tearDown(self):
        voice.runtime.update(ready=False, state="not_configured")
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.directory.cleanup()

    def headers(self, operation=None):
        return {
            "Authorization": "Bearer " + self.token,
            "X-Operation-Id": operation or str(uuid4()),
        }

    def post(self, path, body, operation=None):
        return self.client.post(path, json=body, headers=self.headers(operation))

    def start(self, **overrides):
        payload = {
            "debt_id": self.debt,
            "target": "@nishonboyv7",
            "consent": True,
        } | overrides
        response = self.post("/api/voice/calls", payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def propose(self, call):
        voice.change_status(call, "connected")
        voice.transcript(call, "user-0", "customer", "Yarmini bugun to‘layman", True)
        result = voice.execute_tool(
            call, "propose_promise", {"amount": "500000", "due_on": today()}
        )
        self.assertIn("proposal_id", result)
        return result["proposal_id"]

    def test_confirmation_creates_one_promise_and_never_a_payment(self):
        call = self.start()
        proposal = self.propose(call)
        self.assertIn(
            "error",
            voice.execute_tool(call, "confirm_promise", {"proposal_id": proposal}),
        )
        voice.transcript(
            call,
            "ai-1",
            "ai",
            "500 ming so‘m bugun. Shu kelishuvni tasdiqlaysizmi?",
            True,
        )
        voice.transcript(call, "user-1", "customer", "Ha, tasdiqlayman", True)
        result = voice.execute_tool(call, "confirm_promise", {"proposal_id": proposal})
        self.assertTrue(result.get("saved"), result)
        duplicate = voice.execute_tool(
            call, "confirm_promise", {"proposal_id": proposal}
        )
        self.assertEqual(result["promise_id"], duplicate["promise_id"])
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(len(data["promises"]), 1)
        self.assertEqual(data["promises"][0]["amount"], 50000000)
        self.assertEqual(data["payments"], [])
        self.assertEqual(data["debts"][0]["balance"], 100000000)

    def test_model_cannot_change_the_customers_spoken_amount(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(
            call,
            "offer",
            "customer",
            "Bugun besh yuz ming so‘m beraman.",
            True,
            source="dedicated_stt_verbatim",
        )
        wrong = voice.execute_tool(
            call, "propose_promise", {"amount": "600000", "due_on": today()}
        )
        self.assertIn("error", wrong)
        correct = voice.execute_tool(
            call, "propose_promise", {"amount": "500000", "due_on": today()}
        )
        self.assertIn("proposal_id", correct)

    def test_native_captions_with_cyrillic_uzbek_amount_can_propose(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(
            call, "offer", "customer", "Беш юз минг сўмни бугун тўлайман.", True
        )
        result = voice.execute_tool(
            call, "propose_promise", {"amount": "500000", "due_on": today()}
        )
        self.assertIn("proposal_id", result)

    def test_native_captions_with_cyrillic_half_balance_can_propose(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(call, "offer", "customer", "Ярмини бугун тўлайман.", True)
        result = voice.execute_tool(
            call, "propose_promise", {"amount": "500000", "due_on": today()}
        )
        self.assertIn("proposal_id", result)

    def test_corrected_amount_cannot_be_replaced_with_the_rejected_number(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(
            call,
            "offer",
            "customer",
            "Sakkiz yuz ming emas, ikki yuz ming so‘m beraman.",
            True,
            source="dedicated_stt_verbatim",
        )
        wrong = voice.execute_tool(
            call, "propose_promise", {"amount": "800000", "due_on": today()}
        )
        self.assertIn("error", wrong)
        correct = voice.execute_tool(
            call, "propose_promise", {"amount": "200000", "due_on": today()}
        )
        self.assertIn("proposal_id", correct)

    def test_refusal_partial_transcript_and_correction_are_not_confirmation(self):
        call = self.start()
        proposal = self.propose(call)
        voice.transcript(call, "ai-1", "ai", "Kelishuvni tasdiqlaysizmi?", True)
        for answer, final in [
            ("Ha, lekin ertaga", True),
            ("Yo‘q", True),
            ("Ha, tasdiqlayman", False),
            ("Bilmadim", True),
            ("Да, но если получится", True),
            ("Да, не подтверждаю", True),
            ("Да?", True),
            ("Тўғри?", True),
        ]:
            voice.transcript(call, "user-1", "customer", answer, final)
            self.assertIn(
                "error",
                voice.execute_tool(call, "confirm_promise", {"proposal_id": proposal}),
                answer,
            )
        self.assertIn(
            "error",
            voice.execute_tool(call, "confirm_promise", {"proposal_id": "invented"}),
        )

    def test_natural_russian_confirmation_saves_only_the_agreed_promise(self):
        call = self.start()
        proposal = self.propose(call)
        voice.transcript(
            call, "ai-1", "ai", "Пятьсот тысяч сумов сегодня. Всё верно?", True
        )
        voice.transcript(
            call, "user-1", "customer", "Да, всё правильно, спасибо.", True
        )
        result = voice.execute_tool(call, "confirm_promise", {"proposal_id": proposal})
        self.assertTrue(result.get("saved"), result)
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(data["promises"][0]["amount"], 50000000)
        self.assertEqual(data["payments"], [])

    def test_transcript_provenance_keeps_agent_and_customer_separate(self):
        call = self.start()
        voice.transcript(call, "ai-0", "ai", "Tushundim.", True, source="agent_output")
        words = "Hali va’da bermadim, sanani aytmadim."
        voice.transcript(
            call, "stt-0", "customer", words, True, source="dedicated_stt_verbatim"
        )
        row = self.client.get("/api/voice/calls/" + call, headers=self.headers()).json()
        self.assertEqual(
            [(t["speaker"], t["source"]) for t in row["transcript"]],
            [("ai", "agent_output"), ("customer", "dedicated_stt_verbatim")],
        )
        self.assertEqual(row["transcript"][1]["text"], words)
        with self.assertRaises(ValueError):
            voice.transcript(
                call, "wrong", "customer", "Tushundim", True, source="agent_output"
            )
        with self.assertRaises(ValueError):
            voice.transcript(
                call,
                "partial",
                "customer",
                "Ha",
                False,
                source="dedicated_stt_verbatim",
            )

    def test_existing_transcript_migration_keeps_original_text_and_is_idempotent(self):
        from . import database

        call = self.start()
        voice.transcript(
            call, "old-user", "customer", "Oldingi matn o‘zgarmasin.", True
        )
        with database.read() as c:
            c.execute("ALTER TABLE voice_transcript DROP COLUMN source")
        voice.initialize()
        voice.initialize()
        row = self.client.get(
            "/api/voice/calls/" + call, headers=self.headers()
        ).json()["transcript"][0]
        self.assertEqual(row["text"], "Oldingi matn o‘zgarmasin.")
        self.assertEqual(row["source"], "legacy")

    def test_spoken_russian_half_million_does_not_require_digits(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(
            call, "user-0", "customer", "Полмиллиона сегодня переведу.", True
        )
        result = voice.execute_tool(
            call, "propose_promise", {"amount": "500000", "due_on": today()}
        )
        self.assertIn("proposal_id", result)

    def test_invalid_amounts_dates_and_fake_payment(self):
        call = self.start()
        voice.change_status(call, "connected")
        for payload in [
            {"amount": "2000000", "due_on": today()},
            {"amount": "-1", "due_on": today()},
            {"amount": "NaN", "due_on": today()},
            {"amount": "1", "due_on": "2020-01-01"},
            {"amount": "1", "due_on": "tomorrow"},
        ]:
            self.assertIn("error", voice.execute_tool(call, "propose_promise", payload))
        self.assertIn(
            "error",
            voice.execute_tool(
                call, "finish_call", {"outcome": "promise", "summary": "To‘ladi"}
            ),
        )
        self.assertTrue(
            voice.execute_tool(
                call,
                "finish_call",
                {
                    "outcome": "payment_claimed",
                    "summary": "Mijoz to‘laganini aytdi. Tekshirish kerak.",
                },
            )["finish"]
        )
        self.assertIn(
            "error", voice.execute_tool(call, "add_payment", {"amount": "1000000"})
        )

    def test_one_active_call_idempotency_and_cancellation(self):
        key = str(uuid4())
        payload = {"debt_id": self.debt, "target": "nishonboyv7", "consent": True}
        first = self.post("/api/voice/calls", payload, key)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            first.json(), self.post("/api/voice/calls", payload, key).json()
        )
        self.assertEqual(self.post("/api/voice/calls", payload).status_code, 409)
        call = first.json()["id"]
        self.assertEqual(
            self.post(f"/api/voice/calls/{call}/cancel", {}).status_code, 200
        )
        voice.change_status(call, "connected")
        self.assertIn(
            "error",
            voice.execute_tool(
                call, "propose_promise", {"amount": "1", "due_on": today()}
            ),
        )

    def test_unapproved_targets_and_contact_opt_out(self):
        self.assertEqual(
            self.post(
                "/api/voice/calls",
                {"debt_id": self.debt, "target": "another_user", "consent": True},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                "/api/voice/calls",
                {"debt_id": self.debt, "target": "nishonboyv7", "consent": False},
            ).status_code,
            422,
        )
        call = self.start()
        voice.change_status(call, "connected")
        result = voice.execute_tool(
            call,
            "finish_call",
            {"outcome": "opt_out", "summary": "Boshqa qo‘ng‘iroq qilmaslikni so‘radi."},
        )
        self.assertTrue(result["finish"])
        voice.change_status(call, "completed")
        self.assertEqual(
            self.post(
                "/api/voice/calls",
                {"debt_id": self.debt, "target": "nishonboyv7", "consent": True},
            ).status_code,
            422,
        )

    def test_other_business_cannot_access_or_take_over(self):
        call = self.start()
        other = self.client.post(
            "/api/auth/register",
            json={
                "name": "Other Owner",
                "business_name": "Other Savdo",
                "phone": "+998901234568",
                "password": "Password12345",
            },
        ).json()
        self.token = other["token"]
        self.assertEqual(
            self.client.get(
                f"/api/voice/calls/{call}", headers=self.headers()
            ).status_code,
            404,
        )
        self.assertEqual(
            self.post(f"/api/voice/calls/{call}/cancel", {}).status_code, 404
        )
        self.assertEqual(
            self.post(
                "/api/voice/activate", {"code": "test-activation-secret-12345"}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.get("/api/voice", headers=self.headers()).json()["calls"], []
        )

    def test_installments_saved_together_and_summary_cannot_invent_payments(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(
            call,
            "customer-offer",
            "customer",
            "Yarmini bugun, qolganini ertaga to‘layman",
            True,
        )
        tomorrow = (date.fromisoformat(today()) + timedelta(days=1)).isoformat()
        result = voice.execute_tool(
            call,
            "propose_schedule",
            {
                "installments": [
                    {"amount": "500000", "due_on": today()},
                    {"amount": "500000", "due_on": tomorrow},
                ]
            },
        )
        self.assertIn("proposal_id", result)
        voice.transcript(
            call,
            "ai-readback",
            "ai",
            "Yarmini bugun va qolganini ertaga. Tasdiqlaysizmi?",
            True,
        )
        voice.transcript(call, "customer-yes", "customer", "Ha, tasdiqlayman", True)
        result = voice.execute_tool(
            call, "confirm_promise", {"proposal_id": result["proposal_id"]}
        )
        self.assertEqual(len(result["promise_ids"]), 2)
        voice.execute_tool(
            call,
            "finish_call",
            {"outcome": "promise", "summary": "Mijoz hammasini to‘ladi!"},
        )
        detail = self.client.get(
            f"/api/voice/calls/{call}", headers=self.headers()
        ).json()
        self.assertNotIn("hammasini to‘ladi", detail["summary"])
        self.assertIn(tomorrow, detail["summary"])
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(len(data["promises"]), 2)
        self.assertEqual(data["payments"], [])

    def test_installment_confirmation_rolls_back_if_balance_changes(self):
        from . import database
        from .domain import add_payment

        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(
            call,
            "customer-offer",
            "customer",
            "Yarmini bugun, qolganini bugun keyinroq to‘layman",
            True,
        )
        result = voice.execute_tool(
            call,
            "propose_schedule",
            {
                "installments": [
                    {"amount": "500000", "due_on": today()},
                    {"amount": "500000", "due_on": today()},
                ]
            },
        )
        with database.write() as c:
            actor = dict(
                c.execute(
                    "SELECT * FROM users WHERE id=?", (self.auth["user"]["id"],)
                ).fetchone()
            )
            add_payment(
                c,
                actor,
                {
                    "debt_id": self.debt,
                    "amount": "250000",
                    "paid_on": today(),
                    "method": "cash",
                },
            )
        voice.transcript(call, "ai-readback", "ai", "Tasdiqlaysizmi?", True)
        voice.transcript(call, "customer-yes", "customer", "Ha", True)
        self.assertIn(
            "error",
            voice.execute_tool(
                call, "confirm_promise", {"proposal_id": result["proposal_id"]}
            ),
        )
        self.assertEqual(
            self.client.get("/api/workspace", headers=self.headers()).json()[
                "promises"
            ],
            [],
        )

    def test_repeat_or_date_only_cannot_become_a_payment_offer(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(call, "ai-balance", "ai", "Hisobda bir million so‘m bor", True)
        voice.transcript(
            call,
            "customer-repeat",
            "customer",
            "Eshitmay qoldim. Sekinroq ayting.",
            True,
        )
        self.assertIn(
            "error",
            voice.execute_tool(
                call, "propose_promise", {"amount": "1000000", "due_on": today()}
            ),
        )

        voice.transcript(
            call,
            "customer-date",
            "customer",
            "Ikki kundan keyin. Summa haqida hali kelishmadik.",
            True,
        )
        self.assertIn(
            "error",
            voice.execute_tool(
                call, "propose_promise", {"amount": "1000000", "due_on": today()}
            ),
        )

    def test_health_exposes_readiness_without_account_credentials(self):
        result = self.client.get("/api/health").json()
        self.assertEqual(result["voice"], {"ready": True, "state": "ready"})
        self.assertNotIn("session", str(result))
        self.assertNotIn("api_key", str(result))

    def enable_quick_calls(self):
        os.environ["TUSHUM_VOICE_CUSTOM_TARGETS"] = "1"
        os.environ["TUSHUM_VOICE_OWNER_PHONE"] = "+998901234567"
        voice.initialize()

    def quick_payload(self, **changes):
        return {
            "name": "Telegram Mijoz",
            "target": "@custom_client",
            "amount": "750000.50",
            "due_on": today(),
            "consent": True,
        } | changes

    def test_quick_preview_does_not_create_financial_records(self):
        self.enable_quick_calls()
        before = self.client.get("/api/workspace", headers=self.headers()).json()
        result = self.post("/api/voice/quick-preview", self.quick_payload())
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["amount"], 75000050)
        self.assertEqual(result.json()["action"], "new")
        after = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(before["customers"], after["customers"])
        self.assertEqual(before["debts"], after["debts"])

    def test_quick_call_creates_contact_debt_and_one_job_atomically(self):
        self.enable_quick_calls()
        operation = str(uuid4())
        response = self.post("/api/voice/quick-calls", self.quick_payload(), operation)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            self.post("/api/voice/quick-calls", self.quick_payload(), operation).json(),
        )
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(len(data["customers"]), 2)
        self.assertEqual(len(data["debts"]), 2)
        customer = next(
            c for c in data["customers"] if c["id"] == response.json()["customer_id"]
        )
        self.assertEqual(customer["phone"], "")
        self.assertEqual(customer["telegram_username"], "custom_client")
        self.assertEqual(customer["balance"], 75000050)
        detail = self.client.get(
            "/api/voice/calls/" + response.json()["id"], headers=self.headers()
        ).json()
        self.assertEqual(detail["target"], "custom_client")
        self.assertEqual(detail["status"], "queued")
        backup = self.client.get("/api/backup", headers=self.headers()).json()
        self.assertEqual(backup["voice_contacts"][0]["target"], "custom_client")

    def test_repeat_call_reuses_existing_ledger_and_rejects_changes(self):
        self.enable_quick_calls()
        first = self.post("/api/voice/quick-calls", self.quick_payload()).json()
        voice.change_status(first["id"], "completed")
        mismatch = self.post(
            "/api/voice/quick-calls", self.quick_payload(amount="900000")
        )
        self.assertEqual(mismatch.status_code, 409, mismatch.text)
        wrong_name = self.post(
            "/api/voice/quick-calls", self.quick_payload(name="Boshqa Mijoz")
        )
        self.assertEqual(wrong_name.status_code, 409)
        repeated = self.post(
            "/api/voice/quick-calls", self.quick_payload(target="CUSTOM_CLIENT")
        )
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertTrue(repeated.json()["reused"])
        self.assertEqual(first["debt_id"], repeated.json()["debt_id"])
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(len(data["customers"]), 2)
        self.assertEqual(len(data["debts"]), 2)

    def test_failed_quick_calls_leave_no_new_customer_or_debt(self):
        self.enable_quick_calls()
        for payload, expected in [
            (self.quick_payload(consent=False), 422),
            (self.quick_payload(amount="-1"), 422),
            (self.quick_payload(target="bad target"), 422),
        ]:
            self.assertEqual(
                self.post("/api/voice/quick-calls", payload).status_code, expected
            )
        voice.runtime["ready"] = False
        self.assertEqual(
            self.post("/api/voice/quick-calls", self.quick_payload()).status_code, 503
        )
        voice.runtime["ready"] = True
        self.start()
        self.assertEqual(
            self.post("/api/voice/quick-calls", self.quick_payload()).status_code, 409
        )
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(len(data["customers"]), 1)
        self.assertEqual(len(data["debts"]), 1)

    def test_quick_calls_respect_opt_out_and_paid_accounts(self):
        from . import database
        from .domain import add_payment

        self.enable_quick_calls()
        first = self.post("/api/voice/quick-calls", self.quick_payload()).json()
        voice.change_status(first["id"], "completed")
        with database.write() as c:
            actor = dict(
                c.execute(
                    "SELECT * FROM users WHERE id=?", (self.auth["user"]["id"],)
                ).fetchone()
            )
            add_payment(
                c,
                actor,
                {
                    "debt_id": first["debt_id"],
                    "amount": "750000.50",
                    "paid_on": today(),
                    "method": "cash",
                },
            )
        self.assertEqual(
            self.post("/api/voice/quick-calls", self.quick_payload()).status_code, 409
        )
        with database.write() as c:
            c.execute(
                "UPDATE customers SET contact_allowed=0 WHERE id=?",
                (first["customer_id"],),
            )
        self.assertEqual(
            self.post("/api/voice/quick-calls", self.quick_payload()).status_code, 422
        )

    def test_custom_targets_do_not_grant_other_businesses_access(self):
        self.enable_quick_calls()
        response = self.client.post(
            "/api/auth/register",
            json={
                "name": "Other Owner",
                "business_name": "Other Savdo",
                "phone": "+998901234568",
                "password": "Password12345",
            },
        ).json()
        self.token = response["token"]
        self.assertEqual(
            self.post("/api/voice/quick-preview", self.quick_payload()).status_code, 403
        )
        self.assertEqual(
            self.post("/api/voice/quick-calls", self.quick_payload()).status_code, 403
        )
        self.assertEqual(
            self.post(
                "/api/voice/activate", {"code": "test-activation-secret-12345"}
            ).status_code,
            403,
        )
        self.assertFalse(
            self.client.get("/api/voice", headers=self.headers()).json()["connection"][
                "custom_targets"
            ]
        )

    def test_owner_configuration_moves_only_voice_binding(self):
        from . import database

        other = self.client.post(
            "/api/auth/register",
            json={
                "name": "Other Owner",
                "business_name": "Other Savdo",
                "phone": "+998901234568",
                "password": "Password12345",
            },
        ).json()
        os.environ["TUSHUM_VOICE_OWNER_PHONE"] = "+998901234568"
        os.environ["TUSHUM_VOICE_CUSTOM_TARGETS"] = "1"
        voice.initialize()
        old = self.client.get("/api/voice", headers=self.headers()).json()
        self.assertFalse(old["connection"]["bound"])
        self.token = other["token"]
        self.assertTrue(
            self.client.get("/api/voice", headers=self.headers()).json()["connection"][
                "custom_targets"
            ]
        )
        with database.read() as c:
            self.assertEqual(
                c.execute(
                    "SELECT COUNT(*) FROM customers WHERE business_id=?",
                    (self.business_id,),
                ).fetchone()[0],
                1,
            )
        os.environ["TUSHUM_VOICE_OWNER_PHONE"] = "+998909999999"
        voice.initialize()
        self.assertFalse(
            self.client.get("/api/voice", headers=self.headers()).json()["connection"][
                "bound"
            ]
        )

    def test_quick_calls_require_custom_target_configuration(self):
        self.assertEqual(
            self.post("/api/voice/quick-preview", self.quick_payload()).status_code, 403
        )
        self.assertEqual(
            self.post("/api/voice/quick-calls", self.quick_payload()).status_code, 403
        )

    def test_resolved_usernames_accept_active_aliases_and_reject_bots(self):
        from types import SimpleNamespace

        from .voice_runtime import resolved_target_matches

        user = SimpleNamespace(
            username="Main_Name",
            bot=False,
            usernames=[
                SimpleNamespace(username="another_name", active=True),
                SimpleNamespace(username="old_name", active=False),
            ],
        )
        self.assertTrue(resolved_target_matches(user, "main_name"))
        self.assertTrue(resolved_target_matches(user, "ANOTHER_NAME"))
        self.assertFalse(resolved_target_matches(user, "old_name"))
        self.assertFalse(resolved_target_matches(user, "unrelated_name"))
        user.bot = True
        self.assertFalse(resolved_target_matches(user, "main_name"))

    def test_profile_required_and_context_uses_confirmed_business(self):
        from . import database

        with database.write() as c:
            c.execute("DELETE FROM voice_profiles")
        response = self.post(
            "/api/voice/calls",
            {"debt_id": self.debt, "target": "nishonboyv7", "consent": True},
        )
        self.assertEqual(response.status_code, 422)
        response = self.client.put(
            "/api/voice/profile",
            json={
                "business_name": "Baraka Do‘koni",
                "manager_name": "Anvar",
                "phone": "+998901234567",
            },
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        call = self.start()
        brief = self.client.get(
            "/api/voice/calls/" + call, headers=self.headers()
        ).json()["brief"]
        self.assertEqual(brief["business"], "Baraka Do‘koni")
        self.assertEqual(brief["manager_name"], "Anvar")
        self.assertEqual(brief["balance_som"], "1000000.00")
        self.assertEqual(brief["debt_title"], "Qurilish mollari")
        response = self.client.put(
            "/api/voice/profile",
            json={
                "business_name": "Other Shop",
                "manager_name": "Anvar",
                "phone": "+998901234567",
            },
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 409)

    def test_denial_creates_one_manager_task_and_leaves_ledger_unchanged(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.transcript(
            call, "u0", "customer", "Menda qarz yo‘q, hisobni tekshiring", True
        )
        args = {
            "outcome": "disputed",
            "summary": "Mijoz qarzi yo‘qligini aytdi. Hisobni tekshirish kerak.",
        }
        first = voice.execute_tool(call, "finish_call", args)
        self.assertTrue(first["finish"])
        other = self.client.post("/api/auth/demo").json()
        denied = self.client.post(
            "/api/voice/handoffs/" + first["handoff_id"] + "/resolve",
            json={"resolution": "Other tenant attempt"},
            headers={
                "Authorization": "Bearer " + other["token"],
                "X-Operation-Id": str(uuid4()),
            },
        )
        self.assertEqual(denied.status_code, 404)
        self.assertEqual(
            voice.execute_tool(call, "finish_call", args)["handoff_id"],
            first["handoff_id"],
        )
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(len(data["voice_handoffs"]), 1)
        self.assertTrue(
            next(d for d in data["debts"] if d["id"] == self.debt)["disputed"]
        )
        self.assertEqual(len(data["payments"]), 0)
        self.assertEqual(len(data["promises"]), 0)
        self.assertTrue(any(n["kind"] == "voice" for n in data["notifications"]))
        response = self.post(
            "/api/voice/handoffs/" + first["handoff_id"] + "/resolve",
            {"resolution": "Menejer hisobni tekshirdi, mijoz bilan gaplashdi."},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(data["voice_handoffs"][0]["resolved"], 1)
        self.assertEqual(
            next(d for d in data["debts"] if d["id"] == self.debt)["balance"], 100000000
        )
        self.assertFalse(any(n["kind"] == "voice" for n in data["notifications"]))

    def test_claimed_payment_creates_review_not_payment(self):
        call = self.start()
        voice.change_status(call, "connected")
        voice.execute_tool(
            call,
            "finish_call",
            {
                "outcome": "payment_claimed",
                "summary": "Kecha to‘laganini aytdi, tushumni tekshirish kerak.",
            },
        )
        data = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(data["voice_handoffs"][0]["kind"], "payment_claimed")
        self.assertEqual(data["payments"], [])

    def test_bilingual_recognition_and_turn_policy(self):
        from .voice_runtime import live_config

        config = live_config({"business": "Baraka", "customer": "Ali"})
        self.assertEqual(
            config["input_audio_transcription"]["language_codes"],
            ["uz-UZ", "ru-RU"],
        )
        self.assertNotIn("custom_vocabulary", config["input_audio_transcription"])
        self.assertIn("LIVE AUDIO CONVERSATION", config["system_instruction"])
        self.assertEqual(config["speech_config"]["language_code"], "uz-UZ")
        self.assertIn("ALWAYS answer", config["system_instruction"])
        self.assertNotIn("switch to natural Russian", config["system_instruction"])
        self.assertIn("TWO SEPARATE TURNS", config["system_instruction"])


if __name__ == "__main__":
    unittest.main()
