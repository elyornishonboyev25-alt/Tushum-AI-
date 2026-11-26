"""Validated spreadsheet previews and transactional, repeatable imports."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO, StringIO

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .domain import add_debt, event, money, now, phone, today, uid

ALIASES = {
    "name": ["ism", "mijoz", "mijozismi", "name", "fio", "имя"],
    "phone": ["telefon", "telefonraqami", "phone", "tel", "телефон"],
    "telegram_username": [
        "telegram",
        "telegramusername",
        "username",
        "telegramuser",
        "телеграм",
    ],
    "amount": ["summa", "qarz", "qarzsummasi", "amount", "сумма"],
    "due_on": [
        "muddat",
        "qarzsanasi",
        "tolovmuddati",
        "tolovsanasi",
        "due",
        "dueon",
        "срок",
    ],
    "issued_on": ["savdosanasi", "issuedon", "issued", "sana"],
    "reference": ["hujjat", "hujjatraqami", "reference", "invoice", "id"],
    "company": ["korxona", "company", "biznes"],
    "note": ["izoh", "note", "comment"],
}


def normalize_header(value) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", str(value).lower())


def telegram_username(value) -> str:
    target = str(value or "").strip()
    if not target:
        return ""
    if not re.fullmatch(r"@?[A-Za-z][A-Za-z0-9_]{4,31}", target):
        raise ValueError(
            "Telegram username’ni @akmal_namuna kabi yozing: 5–32 ta harf, raqam yoki pastki chiziq."
        )
    return target.removeprefix("@").lower()


def contact_customer(connection, business_id, number, target):
    """Resolve both identifiers without merging unrelated customer records."""
    matches = []
    if number:
        matches = connection.execute(
            "SELECT * FROM customers WHERE business_id=? AND phone=?",
            (business_id, number),
        ).fetchall()
        if len(matches) > 1:
            raise ValueError(
                "Bu raqam bir nechta mijozda bor. Yozuvni qo‘lda kiriting."
            )
    if target:
        linked = connection.execute(
            "SELECT c.* FROM voice_contacts v JOIN customers c ON c.id=v.customer_id "
            "WHERE v.business_id=? AND c.business_id=? AND v.target=?",
            (business_id, business_id, target),
        ).fetchone()
        if linked:
            matches.append(linked)
    by_id = {row["id"]: dict(row) for row in matches}
    if len(by_id) > 1:
        raise ValueError(
            "Telefon va Telegram username turli mijozlarga tegishli. Kontaktlarni tekshiring."
        )
    customer = next(iter(by_id.values()), None)
    if customer:
        if customer["archived"]:
            raise ValueError("Avval mijozni arxivdan tiklang.")
        if number and customer["phone"] and number != customer["phone"]:
            raise ValueError(
                "Bu Telegram username boshqa telefon raqamli mijozga ulangan."
            )
        existing_target = connection.execute(
            "SELECT target FROM voice_contacts WHERE business_id=? AND customer_id=?",
            (business_id, customer["id"]),
        ).fetchone()
        if target and existing_target and existing_target["target"] != target:
            raise ValueError(
                "Mijozga boshqa Telegram username ulangan. Avval mijoz ma’lumotlarini tekshiring."
            )
    return customer


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
                if (
                    sum(item.file_size for item in package.infolist())
                    > 40 * 1024 * 1024
                ):
                    raise HTTPException(
                        413, "Jadval ochilgandagi hajm katta. Faylni qismlarga bo‘ling."
                    )
            book = load_workbook(BytesIO(content), read_only=True, data_only=True)
            rows = []
            try:
                for index, row in enumerate(book.active.iter_rows(values_only=True)):
                    if index > 2000:
                        raise HTTPException(
                            422, "Bir importda 2000 qatorgacha yuklang."
                        )
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


def preview(
    connection, actor: dict, content: bytes, filename: str, mapping: dict
) -> dict:
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
    missing = [
        field for field in ("name", "amount", "due_on") if field not in positions
    ]
    if not any(field in positions for field in ("phone", "telegram_username")):
        missing.append("contact")
    if missing:
        return {
            "needs_mapping": True,
            "headers": headers,
            "mapping": {field: headers[index] for field, index in positions.items()},
            "required": ["name", "amount", "due_on"],
            "contact_fields": ["telegram_username", "phone"],
        }
    digest = hashlib.sha256(
        content + json.dumps(positions, sort_keys=True).encode()
    ).hexdigest()
    existing = connection.execute(
        "SELECT * FROM imports WHERE business_id=? AND file_hash=?",
        (actor["business_id"], digest),
    ).fetchone()
    if existing:
        return import_view(dict(existing))
    rows = []
    seen_references = set()
    for index, row in enumerate(raw_rows):
        if all(value is None or str(value).strip() == "" for value in row):
            continue

        def cell(field, row=row):
            position = positions.get(field)
            return (
                row[position] if position is not None and position < len(row) else None
            )

        item = {"index": index, "line": index + 2, "error": "", "warning": ""}
        try:
            item.update(
                {
                    "name": str(cell("name") or "").strip(),
                    "phone": phone(str(cell("phone")))
                    if str(cell("phone") or "").strip()
                    else "",
                    "telegram_username": telegram_username(cell("telegram_username")),
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
            if not item["phone"] and not item["telegram_username"]:
                raise ValueError("Telegram username yoki telefon raqamini kiriting.")
            if (
                len(item["reference"]) > 100
                or len(item["note"]) > 2000
                or len(item["company"]) > 120
            ):
                raise ValueError("Hujjat, izoh yoki korxona matni juda uzun.")
            if item["due_on"] < item["issued_on"] or item["issued_on"] > today():
                raise ValueError("Savdo va to‘lov sanalarini tekshiring.")
            customer = contact_customer(
                connection,
                actor["business_id"],
                item["phone"],
                item["telegram_username"],
            )
            if customer:
                item["customer_id"] = customer["id"]
                if customer["name"].casefold() != item["name"].casefold():
                    item["warning"] = (
                        f"Kontakt mavjud mijozga tegishli — {customer['name']}."
                    )
                duplicate = connection.execute(
                    "SELECT id FROM debts WHERE customer_id=? AND amount=? AND issued_on=? AND due_on=?",
                    (
                        customer["id"],
                        money(item["amount"]),
                        item["issued_on"],
                        item["due_on"],
                    ),
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
        "SELECT * FROM imports WHERE id=? AND business_id=?",
        (import_id, actor["business_id"]),
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
            raise HTTPException(
                422, "Xatoli qator tanlangan. Importni qayta tekshiring."
            )
        if item["warning"] and index not in accepted:
            raise HTTPException(409, "Ogohlantirishli qatorlarni alohida tasdiqlang.")
        target = item.get("telegram_username", "")
        try:
            customer = contact_customer(
                connection, actor["business_id"], item["phone"], target
            )
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        if item.get("customer_id") and (
            not customer or customer["id"] != item["customer_id"]
        ):
            raise HTTPException(
                409, "Mijoz kontakti yangilangan. Faylni qayta tekshiring."
            )
        if customer:
            customer_id = customer["id"]
            if (
                customer["name"].casefold() != item["name"].casefold()
                and index not in accepted
            ):
                raise HTTPException(
                    409,
                    "Kontakt boshqa ismli mijozga tegishli. Faylni qayta tekshiring.",
                )
            duplicate = connection.execute(
                "SELECT id FROM debts WHERE customer_id=? AND amount=? AND issued_on=? AND due_on=?",
                (customer_id, money(item["amount"]), item["issued_on"], item["due_on"]),
            ).fetchone()
            if duplicate and index not in accepted:
                raise HTTPException(
                    409,
                    f"{item['line']}-qatorda o‘xshash yozuv mavjud. Qayta ko‘rib chiqing.",
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
        if target:
            connection.execute(
                "INSERT INTO voice_contacts(business_id,target,customer_id,created_at) VALUES (?,?,?,?) "
                "ON CONFLICT(business_id,target) DO NOTHING",
                (actor["business_id"], target, customer_id, now()),
            )
        if customer and item["phone"] and not customer["phone"]:
            connection.execute(
                "UPDATE customers SET phone=?,updated_at=? WHERE id=? AND business_id=?",
                (item["phone"], now(), customer_id, actor["business_id"]),
            )
        data = dict(
            item,
            customer_id=customer_id,
            title=item["reference"] or "Import qilingan nasiya",
        )
        created.append(add_debt(connection, actor, data))
    result = {"count": len(created), "debt_ids": created}
    connection.execute(
        "UPDATE imports SET committed=1,result_json=? WHERE id=?",
        (json.dumps(result), import_id),
    )
    event(
        connection,
        actor,
        "import",
        "Excel importi yakunlandi",
        f"{len(created)} ta nasiya yozuvi",
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
