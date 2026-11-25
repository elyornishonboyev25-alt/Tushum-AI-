"""Regression coverage for money, tenant isolation, imports, and retries."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from .domain import today
from .main import app


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        os.environ["TUSHUM_DATABASE"] = self.directory.name + "/test.sqlite3"
        self.client = TestClient(app)
        self.client.__enter__()
        self.day = today()
        registration = self.client.post(
            "/api/auth/register",
            json={
                "name": "Test Owner",
                "phone": "+998901111111",
                "password": "TestPassword123",
                "business_name": "Test Savdo",
            },
        )
        self.assertEqual(registration.status_code, 200, registration.text)
        self.token = registration.json()["token"]
        self.customer_id = self.post(
            "/api/customers", {"name": "Akmal Test", "phone": "+998902222222"}
        ).json()["id"]
        self.debt_id = self.post(
            "/api/debts",
            {
                "customer_id": self.customer_id,
                "title": "Test hisob",
                "amount": "1000",
                "issued_on": self.day,
                "due_on": self.day,
            },
        ).json()["id"]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.directory.cleanup()

    def headers(self, operation_id=None):
        return {
            "Authorization": "Bearer " + self.token,
            "X-Operation-Id": operation_id or str(uuid4()),
        }

    def post(self, path, payload, operation_id=None):
        return self.client.post(path, json=payload, headers=self.headers(operation_id))

    def workspace(self):
        response = self.client.get("/api/workspace", headers=self.headers())
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def pay(self, amount, key=None):
        return self.post(
            "/api/payments",
            {"debt_id": self.debt_id, "amount": amount, "paid_on": self.day, "method": "cash"},
            key,
        )

    def promise(self, amount):
        return self.post(
            "/api/promises", {"debt_id": self.debt_id, "amount": amount, "due_on": self.day}
        )

    def test_retry_is_applied_once(self):
        key = str(uuid4())
        first = self.pay("300", key)
        second = self.pay("300", key)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        data = self.workspace()
        self.assertEqual(data["debts"][0]["balance"], 70000)
        self.assertEqual(len(data["payments"]), 1)
        self.assertEqual(self.pay("301", key).status_code, 409)

    def test_concurrent_overpayment_is_rejected(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.pay("700"), range(2)))
        self.assertEqual(sorted(item.status_code for item in results), [200, 422])
        self.assertEqual(self.workspace()["debts"][0]["balance"], 30000)

    def test_money_validation(self):
        for invalid in ("NaN", "Infinity", "-1", "0", "1.001", "1000000000001"):
            self.assertEqual(self.pay(invalid).status_code, 422)
        self.assertEqual(self.pay("1.25").status_code, 200)
        self.assertEqual(self.workspace()["debts"][0]["balance"], 99875)

    def test_promise_does_not_reduce_balance(self):
        self.assertEqual(self.promise("600").status_code, 200)
        data = self.workspace()
        self.assertEqual(data["debts"][0]["balance"], 100000)
        self.assertEqual(data["promises"][0]["paid"], 0)
        self.assertEqual(self.promise("500").status_code, 422)

    def test_payment_and_refund_update_promises(self):
        self.promise("600")
        payment = self.pay("800").json()["id"]
        self.assertEqual(self.workspace()["promises"][0]["status"], "fulfilled")
        response = self.post(
            "/api/payments/" + payment + "/refund",
            {"amount": "300", "refunded_on": self.day, "reason": "Qisman qaytarim"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = self.workspace()
        self.assertEqual(data["debts"][0]["balance"], 50000)
        self.assertEqual(data["promises"][0]["paid"], 50000)
        self.assertEqual(data["promises"][0]["status"], "partial")
        self.assertEqual(
            self.post(
                "/api/payments/" + payment + "/refund",
                {"amount": "501", "refunded_on": self.day, "reason": "Ortiqcha qaytarim"},
            ).status_code,
            422,
        )

    def test_multiple_promises_allocate_once(self):
        self.promise("400")
        self.promise("600")
        self.pay("500")
        promises = self.workspace()["promises"]
        self.assertEqual(sum(item["paid"] for item in promises), 50000)
        self.assertEqual(sorted(item["paid"] for item in promises), [10000, 40000])

    def test_tenant_isolation(self):
        second = self.client.post(
            "/api/auth/register",
            json={
                "name": "Other Owner",
                "phone": "+998903333333",
                "password": "OtherPassword123",
                "business_name": "Other Savdo",
            },
        )
        self.token = second.json()["token"]
        self.assertEqual(self.workspace()["customers"], [])
        result = self.post(
            "/api/payments",
            {"debt_id": self.debt_id, "amount": "10", "paid_on": self.day, "method": "cash"},
        )
        self.assertEqual(result.status_code, 404)

    def test_archive_requires_closed_debt_and_refund_restores(self):
        self.assertEqual(
            self.post(
                "/api/customers/" + self.customer_id + "/archive", {"archived": True}
            ).status_code,
            422,
        )
        payment_id = self.pay("1000").json()["id"]
        self.assertEqual(
            self.post(
                "/api/customers/" + self.customer_id + "/archive", {"archived": True}
            ).status_code,
            200,
        )
        self.post(
            "/api/payments/" + payment_id + "/refund",
            {"amount": "1", "refunded_on": self.day, "reason": "Tuzatish"},
        )
        self.assertEqual(self.workspace()["customers"][0]["archived"], 0)

    def test_stale_edits_are_rejected(self):
        payload = {
            "customer_id": self.customer_id,
            "title": "Yangi hisob",
            "amount": "1000",
            "issued_on": self.day,
            "due_on": self.day,
            "version": 1,
        }
        response = self.client.patch(
            "/api/debts/" + self.debt_id, json=payload, headers=self.headers()
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.patch(
            "/api/debts/" + self.debt_id, json=payload, headers=self.headers()
        )
        self.assertEqual(response.status_code, 409)

    def test_dispute_lifecycle(self):
        response = self.post(
            "/api/disputes", {"debt_id": self.debt_id, "reason": "Summa qayta tekshirilsin"}
        )
        dispute_id = response.json()["id"]
        self.assertTrue(self.workspace()["debts"][0]["disputed"])
        self.assertEqual(
            self.post(
                "/api/disputes", {"debt_id": self.debt_id, "reason": "Yana tekshirilsin"}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.post(
                "/api/disputes/" + dispute_id + "/resolve",
                {"resolution": "Hisoblar tekshirildi", "version": 1},
            ).status_code,
            200,
        )
        self.assertFalse(self.workspace()["debts"][0]["disputed"])

    def test_import_is_atomic_and_retry_safe(self):
        content = f"Ism,Telefon,Summa,Muddat,Hujjat\nImport Mijoz,+998904444444,1500,{self.day},IMP-1\n".encode()
        response = self.client.post(
            "/api/imports/preview",
            files={"file": ("sample.csv", content, "text/csv")},
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        self.assertFalse(preview["rows"][0]["error"])
        commit = self.post("/api/imports/" + preview["id"] + "/commit", {"rows": [0]})
        self.assertEqual(commit.status_code, 200, commit.text)
        repeat = self.post("/api/imports/" + preview["id"] + "/commit", {"rows": [0]})
        self.assertEqual(repeat.json(), commit.json())
        self.assertEqual(len(self.workspace()["debts"]), 2)
        second_preview = self.client.post(
            "/api/imports/preview", files={"file": ("same.csv", content)}, headers=self.headers()
        ).json()
        self.assertTrue(second_preview["committed"])

    def test_invalid_import_leaves_database_intact(self):
        content = f"Ism,Telefon,Summa,Muddat\nValid,+998904444444,100,{self.day}\nBad,123,10,{self.day}\n".encode()
        preview = self.client.post(
            "/api/imports/preview", files={"file": ("sample.csv", content)}, headers=self.headers()
        ).json()
        self.assertTrue(preview["rows"][1]["error"])
        response = self.post("/api/imports/" + preview["id"] + "/commit", {"rows": [0, 1]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(self.workspace()["customers"]), 1)

    def test_duplicate_rows_require_explicit_acceptance(self):
        content = f"Ism,Telefon,Summa,Muddat\nAkmal Test,+998902222222,1000,{self.day}\n".encode()
        preview = self.client.post(
            "/api/imports/preview", files={"file": ("same.csv", content)}, headers=self.headers()
        ).json()
        self.assertTrue(preview["rows"][0]["warning"])
        self.assertEqual(
            self.post("/api/imports/" + preview["id"] + "/commit", {"rows": [0]}).status_code, 409
        )
        self.assertEqual(
            self.post(
                "/api/imports/" + preview["id"] + "/commit", {"rows": [0], "accept_duplicates": [0]}
            ).status_code,
            200,
        )

    def test_viewer_permissions(self):
        self.post(
            "/api/team",
            {
                "name": "Viewer",
                "phone": "+998905555555",
                "password": "ViewerPassword123",
                "role": "viewer",
            },
        )
        response = self.client.post(
            "/api/auth/login", json={"phone": "+998905555555", "password": "ViewerPassword123"}
        )
        self.token = response.json()["token"]
        self.assertEqual(len(self.workspace()["customers"]), 1)
        self.assertEqual(self.pay("100").status_code, 403)
        self.assertEqual(self.client.get("/api/backup", headers=self.headers()).status_code, 403)

    def test_password_change_revokes_other_sessions(self):
        response = self.client.post(
            "/api/auth/login", json={"phone": "+998901111111", "password": "TestPassword123"}
        )
        other_token = response.json()["token"]
        self.assertEqual(
            self.post(
                "/api/auth/password",
                {"current_password": "TestPassword123", "new_password": "ChangedPassword123"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/api/workspace", headers={"Authorization": "Bearer " + other_token}
            ).status_code,
            401,
        )
        self.assertEqual(self.client.get("/api/workspace", headers=self.headers()).status_code, 200)

    def test_excel_text_is_literal(self):
        self.post("/api/customers", {"name": "=1+1", "phone": "+998906666666"})
        exported = self.client.get("/api/export", headers=self.headers())
        self.assertEqual(exported.status_code, 200)
        book = load_workbook(BytesIO(exported.content))
        cells = [
            cell for row in book["Mijozlar"].iter_rows() for cell in row if cell.value == "=1+1"
        ]
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0].data_type, "s")

    def test_archived_customer_cannot_reopen_debt_through_edit(self):
        self.pay("1000")
        self.assertEqual(
            self.post(f"/api/customers/{self.customer_id}/archive", {"archived": True}).status_code,
            200,
        )
        debt = self.workspace()["debts"][0]
        response = self.client.patch(
            f"/api/debts/{self.debt_id}",
            json={
                "customer_id": self.customer_id,
                "title": debt["title"],
                "amount": "2000",
                "issued_on": debt["issued_on"],
                "due_on": debt["due_on"],
                "version": debt["version"],
                "reason": "Qo‘shimcha savdo",
            },
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.workspace()["customers"][0]["balance"], 0)

    def test_activity_pages_are_complete_and_isolated(self):
        for index in range(103):
            self.assertEqual(
                self.post(
                    f"/api/customers/{self.customer_id}/notes", {"text": f"Izoh {index}"}
                ).status_code,
                200,
            )
        first = self.client.get("/api/activity?kind=note", headers=self.headers()).json()
        self.assertEqual(len(first["items"]), 100)
        second = self.client.get(
            "/api/activity?kind=note&before=" + first["next"], headers=self.headers()
        ).json()
        self.assertEqual(len(second["items"]), 3)
        self.assertIsNone(second["next"])
        ids = [row["id"] for row in first["items"] + second["items"]]
        self.assertEqual(len(set(ids)), 103)
        self.assertEqual(
            self.client.get("/api/activity?before=unknown", headers=self.headers()).status_code, 404
        )

    def test_reports_net_refunds(self):
        payment = self.pay("500").json()["id"]
        self.post(
            "/api/payments/" + payment + "/refund",
            {"amount": "125.50", "refunded_on": self.day, "reason": "Qaytarish"},
        )
        report = self.client.get("/api/reports", headers=self.headers()).json()
        self.assertEqual(report["net_received"], 37450)
        self.assertEqual(report["current_balance"], 62550)


if __name__ == "__main__":
    unittest.main()
