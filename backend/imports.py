"""Validated spreadsheet previews and transactional, repeatable imports."""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
import hashlib
from io import BytesIO, StringIO
import json
import re
import zipfile

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .domain import add_debt, event, money, now, phone, today, uid

ALIASES = {
    "name": ["ism", "mijoz", "mijozismi", "name", "fio", "имя"],
    "phone": ["telefon", "telefonraqami", "phone", "tel", "телефон"],
    "amount": ["summa", "qarz", "qarzsummasi", "amount", "сумма"],
    "due_on": ["muddat", "tolovsanasi", "due", "dueon", "срок"],
    "issued_on": ["savdosanasi", "issuedon", "issued", "sana"],
    "reference": ["hujjat", "hujjatraqami", "reference", "invoice", "id"],
    "company": ["korxona", "company", "biznes"],
    "note": ["izoh", "note", "comment"],
}


def normalize_header(value) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", str(value).lower())


def parse_date(value, default=None) -> str:
    if value is None or str(value).strip() == "":
        if default:
            return default
        raise ValueError("To‘lov sanasi kerak.")
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Sanani YYYY-MM-DD yoki DD.MM.YYYY formatida kiriting.")


def read_sheet(content: bytes, filename: str) -> tuple[list[str], list[list]]:
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Faylni 10 MB gacha hajmda yuklang.")
    try:
        if filename.lower().endswith(".xlsx"):
            with zipfile.ZipFile(BytesIO(content)) as package:
                if sum(item.file_size for item in package.infolist()) > 40 * 1024 * 1024:
                    raise HTTPException(
                        413, "Jadval ochilgandagi hajm katta. Faylni qismlarga bo‘ling."
                    )
            book = load_workbook(BytesIO(content), read_only=True, data_only=True)
            rows = []
            try:
                for index, row in enumerate(book.active.iter_rows(values_only=True)):
                    if index > 2000:
                        raise HTTPException(422, "Bir importda 2000 qatorgacha yuklang.")
                    rows.append(list(row[:40]))
            finally:
                book.close()
        elif filename.lower().endswith(".csv"):
            text = content.decode("utf-8-sig")
            try:
                dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = list(csv.reader(StringIO(text), dialect))
            if len(rows) > 2001:
                raise HTTPException(422, "Bir importda 2000 qatorgacha yuklang.")
        else:
            raise HTTPException(422, "XLSX yoki UTF-8 CSV faylini tanlang.")
        if len(rows) < 2:
            raise HTTPException(422, "Sarlavha va kamida bitta ma’lumot qatori kerak.")
        headers = [str(value or "").strip() for value in rows[0]]
        return headers, rows[1:]
    except HTTPException:
        raise
    except (ValueError, UnicodeError, zipfile.BadZipFile, KeyError, OSError) as error:
        raise HTTPException(
            422, "Jadval ochilmadi. Faylni XLSX yoki UTF-8 CSV sifatida qayta saqlang."
        ) from error


def preview(connection, actor: dict, content: bytes, filename: str, mapping: dict) -> dict:
    headers, raw_rows = read_sheet(content, filename)
    positions = {}
    for field, aliases in ALIASES.items():
        chosen = mapping.get(field)
        for index, header in enumerate(headers):
            if (chosen is not None and chosen == header) or (
                chosen is None and normalize_header(header) in aliases
            ):
                positions[field] = index
                break
    missing = [field for field in ("name", "phone", "amount", "due_on") if field not in positions]
    if missing:
        return {
            "needs_mapping": True,
            "headers": headers,
            "mapping": {field: headers[index] for field, index in positions.items()},
            "required": ["name", "phone", "amount", "due_on"],
        }
    digest = hashlib.sha256(content + json.dumps(positions, sort_keys=True).encode()).hexdigest()
    existing = connection.execute(
        "SELECT * FROM imports WHERE business_id=? AND file_hash=?", (actor["business_id"], digest)
    ).fetchone()
    if existing:
        return import_view(dict(existing))
    rows = []
    seen_references = set()
    for index, row in enumerate(raw_rows):
        if all(value is None or str(value).strip() == "" for value in row):
            continue

        def cell(field):
            position = positions.get(field)
            return row[position] if position is not None and position < len(row) else None

        item = {"index": index, "line": index + 2, "error": "", "warning": ""}
        try:
            item.update(
                {
                    "name": str(cell("name") or "").strip(),
                    "phone": phone(str(cell("phone") or "")),
                    "amount": str(Decimal(money(str(cell("amount") or ""))) / 100),
                    "due_on": parse_date(cell("due_on")),
                    "issued_on": parse_date(cell("issued_on"), today()),
                    "reference": str(cell("reference") or "").strip(),
                    "company": str(cell("company") or "").strip(),
                    "note": str(cell("note") or "").strip(),
                }
            )
            if not 2 <= len(item["name"]) <= 120:
                raise ValueError("Mijoz ismi 2–120 belgi bo‘lsin.")
            if (
                len(item["reference"]) > 100
                or len(item["note"]) > 2000
                or len(item["company"]) > 120
            ):
                raise ValueError("Hujjat, izoh yoki korxona matni juda uzun.")
            if item["due_on"] < item["issued_on"] or item["issued_on"] > today():
                raise ValueError("Savdo va to‘lov sanalarini tekshiring.")
            matches = connection.execute(
                "SELECT id,name,archived FROM customers WHERE business_id=? AND phone=?",
                (actor["business_id"], item["phone"]),
            ).fetchall()
            if len(matches) > 1:
                raise ValueError("Bu raqam bir nechta mijozda bor. Yozuvni qo‘lda kiriting.")
            if matches and matches[0]["archived"]:
                raise ValueError("Avval mijozni arxivdan tiklang.")
            if matches:
                item["customer_id"] = matches[0]["id"]
                if matches[0]["name"].casefold() != item["name"].casefold():
                    item["warning"] = f"Raqam mavjud mijozga tegishli — {matches[0]['name']}."
                duplicate = connection.execute(
                    "SELECT id FROM debts WHERE customer_id=? AND amount=? AND issued_on=? AND due_on=?",
                    (matches[0]["id"], money(item["amount"]), item["issued_on"], item["due_on"]),
                ).fetchone()
                if duplicate:
                    item["warning"] = "Shu summa va sanalarga o‘xshash nasiya mavjud."
            if item["reference"]:
                if (
                    item["reference"] in seen_references
                    or connection.execute(
                        "SELECT id FROM debts WHERE business_id=? AND reference=?",
                        (actor["business_id"], item["reference"]),
                    ).fetchone()
                ):
                    raise ValueError("Hujjat raqami avval ishlatilgan.")
                seen_references.add(item["reference"])
        except HTTPException as error:
            item["error"] = str(error.detail)
        except ValueError as error:
            item["error"] = str(error)
        rows.append(item)
    import_id = uid()
    connection.execute(
        "INSERT INTO imports VALUES (?,?,?,?,?,?,0,NULL,?)",
        (
            import_id,
            actor["business_id"],
            digest,
            filename[:160],
            json.dumps(headers, ensure_ascii=False),
            json.dumps(rows, ensure_ascii=False),
            now(),
        ),
    )
    return {
        "id": import_id,
        "headers": headers,
        "rows": rows,
        "committed": False,
        "result": None,
        "needs_mapping": False,
    }


def import_view(row: dict) -> dict:
    return {
        "id": row["id"],
        "headers": json.loads(row["headers"]),
        "rows": json.loads(row["rows_json"]),
        "committed": bool(row["committed"]),
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "needs_mapping": False,
    }


def commit_import(
    connection, actor: dict, import_id: str, indexes: list[int], accepted: list[int]
) -> dict:
    row = connection.execute(
        "SELECT * FROM imports WHERE id=? AND business_id=?", (import_id, actor["business_id"])
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Import topilmadi.")
    if row["committed"]:
        return json.loads(row["result_json"])
    source = {item["index"]: item for item in json.loads(row["rows_json"])}
    selected = sorted(set(indexes))
    created = []
    for index in selected:
        item = source.get(index)
        if item is None or item["error"]:
            raise HTTPException(422, "Xatoli qator tanlangan. Importni qayta tekshiring.")
        if item["warning"] and index not in accepted:
            raise HTTPException(409, "Ogohlantirishli qatorlarni alohida tasdiqlang.")
        customers = connection.execute(
            "SELECT id,archived FROM customers WHERE business_id=? AND phone=?",
            (actor["business_id"], item["phone"]),
        ).fetchall()
        if len(customers) > 1 or (customers and customers[0]["archived"]):
            raise HTTPException(409, "Mijoz ma’lumoti yangilangan. Faylni qayta tekshiring.")
        if customers:
            customer_id = customers[0]["id"]
            duplicate = connection.execute(
                "SELECT id FROM debts WHERE customer_id=? AND amount=? AND issued_on=? AND due_on=?",
                (customer_id, money(item["amount"]), item["issued_on"], item["due_on"]),
            ).fetchone()
            if duplicate and index not in accepted:
                raise HTTPException(
                    409, f"{item['line']}-qatorda o‘xshash yozuv mavjud. Qayta ko‘rib chiqing."
                )
        else:
            customer_id = uid()
            connection.execute(
                "INSERT INTO customers VALUES (?,?,?,?,?,?,1,0,?,?)",
                (
                    customer_id,
                    actor["business_id"],
                    item["name"],
                    item["phone"],
                    item["company"],
                    "",
                    now(),
                    now(),
                ),
            )
            event(
                connection,
                actor,
                "customer",
                "Mijoz import qilindi",
                item["name"],
                customer_id=customer_id,
            )
        data = dict(
            item, customer_id=customer_id, title=item["reference"] or "Import qilingan nasiya"
        )
        created.append(add_debt(connection, actor, data))
    result = {"count": len(created), "debt_ids": created}
    connection.execute(
        "UPDATE imports SET committed=1,result_json=? WHERE id=?", (json.dumps(result), import_id)
    )
    event(
        connection, actor, "import", "Excel importi yakunlandi", f"{len(created)} ta nasiya yozuvi"
    )
    return result


def workbook_bytes(sheets: dict[str, list[list]]) -> bytes:
    book = Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.fill = PatternFill("solid", fgColor="0C5F69")
            cell.font = Font(color="FFFFFF", bold=True)
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                45, max(16, max(len(str(cell.value or "")) for cell in column) + 3)
            )
            for cell in column:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    output = BytesIO()
    book.save(output)
    return output.getvalue()
