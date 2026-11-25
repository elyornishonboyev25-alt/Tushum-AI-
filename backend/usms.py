"""USMS HTTPS transport. Credentials stay in server environment variables."""

import os
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import HTTPException


def configured() -> bool:
    return bool(
        os.getenv("USMS_LOGIN", "").strip() and os.getenv("USMS_SECRET", "").strip()
    )


def enabled_for(business_id: str) -> bool:
    # Only the explicitly bound business can use the server owner's prepaid balance.
    return configured() and business_id == os.getenv("USMS_BUSINESS_ID", "").strip()


def sender() -> str:
    return os.getenv("USMS_SENDER", "").strip()


def cents(value) -> int:
    try:
        amount = Decimal(str(value)) * 100
        if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
            raise ValueError
        return int(amount)
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(502, "USMS javobidagi summa formati mos kelmadi.") from None


def request(method: str, path: str, payload: dict | None = None) -> dict:
    if not configured():
        raise HTTPException(503, "Serverda USMS login va maxfiy kaliti sozlanmagan.")
    credential = (
        os.environ["USMS_LOGIN"].strip() + ":" + os.environ["USMS_SECRET"].strip()
    )
    try:
        with httpx.Client(timeout=httpx.Timeout(12, connect=5)) as client:
            response = client.request(
                method,
                "https://usms.uz/api/v1" + path,
                headers={
                    "Authorization": "Bearer " + credential,
                    "Accept": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError:
        raise HTTPException(
            504, "USMS bilan aloqa uzildi. Xabar tarixidagi holatni tekshiring."
        ) from None
    errors = {
        400: "USMS so‘rov qiymatlarini qabul qilmadi. Shablon talablarini tekshiring.",
        401: "USMS login yoki maxfiy kaliti qabul qilinmadi. Railway sozlamalarini tekshiring.",
        402: "USMS balansida mablag‘ yetarli emas. Balansni to‘ldiring.",
        403: "USMS hisob, shablon yoki jo‘natuvchiga ruxsat bermadi. Kabinetdagi tasdiqlarni tekshiring.",
        404: "USMS yozuvi topilmadi. Shablon yoki xabarni kabinetda tekshiring.",
        409: "USMS so‘rovi avvalgi xabarga mos kelmadi. Xabar tarixini tekshiring.",
        422: "USMS shablon qiymatlarini qabul qilmadi. Tasdiqlangan shablon talablarini tekshiring.",
        429: "USMS so‘rovlar chegarasiga yetildi. Keyinroq qayta tekshiring.",
    }
    if response.status_code >= 400:
        raise HTTPException(
            response.status_code if response.status_code in errors else 502,
            errors.get(
                response.status_code,
                "USMS vaqtincha javob bermadi. Xabar holatini tekshiring.",
            ),
        )
    try:
        result = response.json(parse_float=Decimal)
    except ValueError:
        raise HTTPException(
            502, "USMS javobi ochilmadi. Xabar holatini tekshiring."
        ) from None
    if not isinstance(result, dict):
        raise HTTPException(502, "USMS javobi formati mos kelmadi.")
    return result
