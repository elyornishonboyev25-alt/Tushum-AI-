"""Paid-message regression coverage using a simulated provider."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from . import database, usms
from .main import app


class SmsTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.environment = patch.dict(
            os.environ,
            {
                "TUSHUM_DATABASE": self.directory.name + "/sms.sqlite3",
                "USMS_LOGIN": "test-login",
                "USMS_SECRET": "test-secret",
                "USMS_SENDER": "4546",
            },
        )
        self.environment.start()
        self.client = TestClient(app).__enter__()
        result = self.client.post(
            "/api/auth/register",
            json={
                "name": "SMS Owner",
                "business_name": "SMS Savdo",
                "phone": "+998901234567",
                "password": "Password12345",
            },
        ).json()
        self.token = result["token"]
        self.business_id = result["user"]["business_id"]
        os.environ["USMS_BUSINESS_ID"] = self.business_id
        self.customer_id = self.post(
            "/api/customers", {"name": "Test Mijoz", "phone": "+998901111111"}
        ).json()["id"]
        self.provider_calls = []
        self.price = 120
        self.balance = 1000
        self.provider = patch("backend.usms.request", side_effect=self.fake_request)
        self.provider_mock = self.provider.start()

    def tearDown(self):
        self.provider.stop()
        self.client.__exit__(None, None, None)
        self.environment.stop()
        self.directory.cleanup()

    def headers(self):
        return {"Authorization": "Bearer " + self.token, "X-Operation-Id": str(uuid4())}

    def post(self, path, body=None):
        return self.client.post(path, json=body or {}, headers=self.headers())

    def fake_request(self, method, path, payload=None):
        self.provider_calls.append((method, path, payload))
        if path.startswith("/templates"):
            return {
                "items": [
                    {
                        "id": 1,
                        "title": "Eslatma",
                        "text": "Salom, {name}.",
                        "kind": "service",
                        "variables": [
                            {"key": "name", "type": "text", "max_length": 80}
                        ],
                    }
                ]
            }
        if path == "/balance":
            return {"balance": self.balance}
        if path == "/quote":
            return {"price": self.price, "parts": 1}
        if path == "/send":
            return {"id": 1001, "status": "sent", "price": self.price, "parts": 1}
        return {"id": 1001, "status": "delivered", "price": str(self.price), "parts": 1}

    def preview(self):
        result = self.post(
            f"/api/customers/{self.customer_id}/sms/preview",
            {"template_id": 1, "params": {"name": "Akmal"}},
        )
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def send(self, message):
        return self.post(f"/api/sms/{message['id']}/send")

    def test_preview_and_duplicate_send_and_delivery(self):
        message = self.preview()
        self.assertEqual(message["price"], 12000)
        self.assertEqual(message["text"], "Salom, Akmal.")
        estimate = next(
            body for _, path, body in self.provider_calls if path == "/quote"
        )
        self.assertEqual(
            estimate,
            {"phone": "998901111111", "text": "Salom, Akmal.", "kind": "service"},
        )
        self.assertFalse(any(path == "/send" for _, path, _ in self.provider_calls))
        self.assertEqual(self.send(message).json()["status"], "sent")
        self.assertEqual(self.send(message).json()["status"], "sent")
        sends = [body for _, path, body in self.provider_calls if path == "/send"]
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0]["phone"], "998901111111")
        self.assertEqual(sends[0]["idem_key"], "tushum-" + message["id"])
        receipt = self.client.get(
            f"/api/sms/{message['id']}", headers=self.headers()
        ).json()
        self.assertEqual(receipt["status"], "delivered")
        workspace = self.client.get("/api/workspace", headers=self.headers()).json()
        self.assertEqual(workspace["payments"], [])
        self.assertTrue(workspace["capabilities"]["sms"])
        backup = self.client.get("/api/backup", headers=self.headers()).json()
        self.assertEqual(backup["sms_messages"][0]["status"], "delivered")

    def test_zero_balance_blocks_send(self):
        self.balance = 0
        result = self.send(self.preview()).json()
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(any(path == "/send" for _, path, _ in self.provider_calls))

    def test_price_increase_requires_new_preview(self):
        message = self.preview()
        self.price = 150
        self.assertEqual(self.send(message).json()["status"], "rejected")
        self.assertFalse(any(path == "/send" for _, path, _ in self.provider_calls))

    def test_concurrent_sends_issue_one_provider_request(self):
        message = self.preview()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.send(message), range(2)))
        self.assertTrue(all(result.status_code == 200 for result in results))
        self.assertEqual(sum(path == "/send" for _, path, _ in self.provider_calls), 1)

    def test_timeout_retry_uses_same_persisted_payload(self):
        message = self.preview()
        original = self.fake_request
        sends = []

        def timeout_once(method, path, payload=None):
            if path == "/send":
                sends.append(payload.copy())
                if len(sends) == 1:
                    raise HTTPException(504, "USMS timeout")
            return original(method, path, payload)

        self.provider_mock.side_effect = timeout_once
        self.assertEqual(self.send(message).json()["status"], "uncertain")
        self.assertEqual(self.send(message).json()["status"], "sent")
        self.assertEqual(sends[0], sends[1])

    def test_other_business_cannot_use_balance_or_receipt(self):
        message = self.preview()
        result = self.client.post(
            "/api/auth/register",
            json={
                "name": "Other Owner",
                "business_name": "Other Savdo",
                "phone": "+998902345678",
                "password": "Password12345",
            },
        ).json()
        self.token = result["token"]
        self.assertEqual(
            self.client.get("/api/sms/account", headers=self.headers()).status_code, 403
        )
        self.assertEqual(self.send(message).status_code, 403)
        os.environ["USMS_BUSINESS_ID"] = result["user"]["business_id"]
        self.assertEqual(
            self.client.get(
                f"/api/sms/{message['id']}", headers=self.headers()
            ).status_code,
            404,
        )

    def test_revoked_consent_and_changed_phone_block_approved_preview(self):
        message = self.preview()
        with database.write() as connection:
            connection.execute(
                "UPDATE customers SET contact_allowed=0 WHERE id=?", (self.customer_id,)
            )
        self.assertEqual(self.send(message).status_code, 409)
        with database.write() as connection:
            connection.execute(
                "UPDATE customers SET contact_allowed=1,phone='+998902222222' WHERE id=?",
                (self.customer_id,),
            )
        self.assertEqual(self.send(message).status_code, 409)
        self.assertFalse(any(path == "/send" for _, path, _ in self.provider_calls))

    def test_credentials_and_raw_provider_errors_are_not_exposed(self):
        self.provider.stop()
        with patch("httpx.Client.request") as request:
            import httpx

            request.return_value = httpx.Response(401, json={"error": "test-secret"})
            with self.assertRaises(HTTPException) as result:
                usms.request("GET", "/balance")
            self.assertEqual(result.exception.status_code, 401)
            self.assertNotIn("test-secret", result.exception.detail)
        self.provider.start()

    def test_amount_parser_rejects_invalid_provider_values(self):
        self.assertEqual(usms.cents("120.50"), 12050)
        for invalid in ("NaN", "Infinity", "-1", None, "120.001"):
            with self.assertRaises(HTTPException):
                usms.cents(invalid)
