"""Contact-aware import exercises real transactions in isolated databases."""

import os
import unittest
from datetime import date, timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from . import database
from .domain import today
from .main import app


class ImportContactTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.environment = patch.dict(
            os.environ,
            {
                "TUSHUM_DATABASE": self.directory.name + "/imports.sqlite3",
                "TUSHUM_VOICE_LOCAL": "0",
                "TUSHUM_TELEGRAM_SESSION": "",
                "TELEGRAM_API_ID": "",
                "TELEGRAM_API_HASH": "",
                "GEMINI_API_KEY": "",
                "TUSHUM_VOICE_OWNER_PHONE": "",
                "TUSHUM_VOICE_BUSINESS_ID": "",
            },
        )
        self.environment.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.token = self.register("+998901111111")
        self.day = today()
        self.due = (date.fromisoformat(self.day) + timedelta(days=7)).isoformat()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.environment.stop()
        self.directory.cleanup()

    def register(self, number):
        response = self.client.post(
            "/api/auth/register",
            json={
                "name": "Import Owner",
                "phone": number,
                "password": "ImportTest123",
                "business_name": "Import Savdo",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    def headers(self):
        return {"Authorization": "Bearer " + self.token, "X-Operation-Id": str(uuid4())}

    def preview(self, text, mapping=None):
        import json

        response = self.client.post(
            "/api/imports/preview",
            headers=self.headers(),
            files={"file": ("contacts.csv", text.encode("utf8"), "text/csv")},
            data={"mapping": json.dumps(mapping or {})},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def commit(self, preview, rows=None, accept=None):
        return self.client.post(
            "/api/imports/" + preview["id"] + "/commit",
            headers=self.headers(),
            json={
                "rows": rows if rows is not None else [0],
                "accept_duplicates": accept or [],
            },
        )

    def workspace(self):
        response = self.client.get("/api/workspace", headers=self.headers())
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_username_only_import_reuses_customer_and_is_retry_safe(self):
        preview = self.preview(
            "Mijoz ismi,Telegram username,Qarz summasi,Qarz sanasi,Hujjat\n"
            f"Akmal Karimov,@Akmal_Namuna,1500000,{self.due},TG-1\n"
            f"Akmal Karimov,akmal_namuna,500000,{self.due},TG-2\n"
        )
        self.assertFalse(preview["needs_mapping"])
        self.assertTrue(all(not row["error"] for row in preview["rows"]))
        self.assertEqual(preview["rows"][0]["telegram_username"], "akmal_namuna")
        result = self.commit(preview, [0, 1])
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.commit(preview, [0, 1]).json(), result.json())
        data = self.workspace()
        self.assertEqual(len(data["customers"]), 1)
        self.assertEqual(data["customers"][0]["phone"], "")
        self.assertEqual(data["customers"][0]["telegram_username"], "akmal_namuna")
        self.assertEqual(len(data["debts"]), 2)
        self.assertEqual(data["customers"][0]["balance"], 200000000)
        with database.read() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM voice_calls").fetchone()[0], 0
            )

    def test_phone_only_file_is_still_accepted(self):
        preview = self.preview(
            f"Ism,Telefon,Summa,Muddat\nAkmal,+998902222222,100,{self.due}\n"
        )
        self.assertFalse(preview["rows"][0]["error"])
        self.assertEqual(self.commit(preview).status_code, 200)
        self.assertEqual(self.workspace()["customers"][0]["phone"], "+998902222222")

    def test_invalid_username_or_missing_contact_cannot_commit_any_rows(self):
        for username in [
            "@bad",
            "https://t.me/someone",
            "@with space",
            "@@akmal_test",
            "",
        ]:
            with self.subTest(username=username):
                preview = self.preview(
                    "Ism,Telegram username,Summa,Muddat\n"
                    f"Akmal,@akmal_test,100,{self.due}\nNodira,{username},200,{self.due}\n"
                )
                self.assertTrue(preview["rows"][1]["error"])
                self.assertEqual(self.commit(preview, [0, 1]).status_code, 422)
                self.assertEqual(self.workspace()["customers"], [])

    def test_mixed_rows_allow_either_contact(self):
        preview = self.preview(
            "Ism,Telegram username,Telefon,Summa,Muddat\n"
            f"Akmal,@akmal_namuna,,100,{self.due}\n"
            f"Nodira,,+998903333333,200,{self.due}\n"
        )
        self.assertTrue(all(not row["error"] for row in preview["rows"]))
        self.assertEqual(self.commit(preview, [0, 1]).status_code, 200)
        self.assertEqual(len(self.workspace()["customers"]), 2)

    def test_contact_conflict_does_not_merge_or_relink_customers(self):
        first = self.preview(
            "Ism,Telegram username,Telefon,Summa,Muddat\n"
            f"Akmal,@akmal_namuna,+998902222222,100,{self.due}\n"
            f"Nodira,@nodira_namuna,+998903333333,200,{self.due}\n"
        )
        self.assertEqual(self.commit(first, [0, 1]).status_code, 200)
        for target, number in [
            ("@akmal_namuna", "+998903333333"),
            ("@new_username", "+998902222222"),
            ("@akmal_namuna", "+998904444444"),
        ]:
            preview = self.preview(
                "Ism,Telegram username,Telefon,Summa,Muddat\n"
                f"Akmal,{target},{number},300,{self.due}\n"
            )
            self.assertTrue(preview["rows"][0]["error"])
            self.assertEqual(self.commit(preview).status_code, 422)
        self.assertEqual(len(self.workspace()["debts"]), 2)

    def test_contact_changed_after_preview_rejects_entire_commit(self):
        seed = self.preview(
            f"Ism,Telefon,Summa,Muddat\nAkmal,+998902222222,100,{self.due}\n"
        )
        self.assertEqual(self.commit(seed).status_code, 200)
        pending = self.preview(
            "Ism,Telegram username,Telefon,Summa,Muddat\n"
            f"Akmal,@akmal_namuna,+998902222222,200,{self.due}\n"
        )
        customer = self.workspace()["customers"][0]
        with database.write() as c:
            c.execute(
                "INSERT INTO voice_contacts VALUES (?,?,?,?)",
                (
                    customer["business_id"],
                    "different_username",
                    customer["id"],
                    self.day,
                ),
            )
        self.assertEqual(self.commit(pending).status_code, 409)
        self.assertEqual(len(self.workspace()["debts"]), 1)

    def test_username_is_scoped_to_business(self):
        content = (
            f"Ism,Telegram username,Summa,Muddat\nAkmal,@same_username,100,{self.due}\n"
        )
        first_token = self.token
        self.assertEqual(self.commit(self.preview(content)).status_code, 200)
        first_id = self.workspace()["customers"][0]["id"]
        self.token = self.register("+998909999999")
        self.assertEqual(self.workspace()["customers"], [])
        self.assertEqual(self.commit(self.preview(content)).status_code, 200)
        self.assertNotEqual(self.workspace()["customers"][0]["id"], first_id)
        self.token = first_token
        self.assertEqual(len(self.workspace()["customers"]), 1)

    def test_repeated_username_with_different_names_is_not_silently_merged(self):
        preview = self.preview(
            "Ism,Telegram username,Summa,Muddat\n"
            f"Akmal,@akmal_namuna,100,{self.due}\n"
            f"Nodira,@akmal_namuna,200,{self.due}\n"
        )
        self.assertEqual(self.commit(preview, [0, 1]).status_code, 409)
        self.assertEqual(self.workspace()["customers"], [])

    def test_custom_mapping_and_template_round_trip(self):
        preview = self.preview(
            f"Client,Handle,Money,Deadline\nAkmal,@akmal_namuna,100,{self.due}\n"
        )
        self.assertTrue(preview["needs_mapping"])
        preview = self.preview(
            f"Client,Handle,Money,Deadline\nAkmal,@akmal_namuna,100,{self.due}\n",
            {
                "name": "Client",
                "telegram_username": "Handle",
                "amount": "Money",
                "due_on": "Deadline",
            },
        )
        self.assertFalse(preview["needs_mapping"])
        self.assertFalse(preview["rows"][0]["error"])
        response = self.client.get("/api/imports/template", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content))
        self.assertEqual(
            next(iter(book.active.values)),
            ("Mijoz ismi", "Telegram username", "Qarz summasi", "Qarz sanasi"),
        )
        uploaded = self.client.post(
            "/api/imports/preview",
            headers=self.headers(),
            files={"file": ("template.xlsx", response.content)},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        self.assertFalse(uploaded.json()["needs_mapping"])
        self.assertFalse(uploaded.json()["rows"][0]["error"])


if __name__ == "__main__":
    unittest.main()
