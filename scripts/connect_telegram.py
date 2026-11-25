"""Connect the demo caller account and retain its session only on this computer."""

import argparse
import asyncio
import getpass
import json
import logging
import re
import sys
from pathlib import Path

from telethon import TelegramClient, errors

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRECTORY = PROJECT_ROOT / "backend" / "data" / "telegram"
CREDENTIALS_PATH = PRIVATE_DIRECTORY / "credentials.json"
SESSION_PATH = PRIVATE_DIRECTORY / "caller.session"


def credentials():
    if CREDENTIALS_PATH.is_file():
        value = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8-sig"))
    else:
        value = {
            "api_id": input("Telegram api_id: ").strip(),
            "api_hash": getpass.getpass("Telegram api_hash (maxfiy): ").strip(),
        }
    api_id = str(value.get("api_id", "")).strip()
    api_hash = str(value.get("api_hash", "")).strip()
    if not re.fullmatch(r"[1-9][0-9]{3,11}", api_id):
        raise ValueError("api_id raqamlarini tekshiring.")
    if not re.fullmatch(r"[a-fA-F0-9]{32}", api_hash):
        raise ValueError("api_hash 32 ta harf va raqamdan iborat bo'lishi kerak.")
    PRIVATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(
        json.dumps({"api_id": int(api_id), "api_hash": api_hash}), encoding="utf-8"
    )
    return int(api_id), api_hash


async def connect_account(arguments):
    api_id, api_hash = credentials()
    client = TelegramClient(
        str(SESSION_PATH),
        api_id,
        api_hash,
        device_model="Tushum AI Demo",
        app_version="1.0.0",
        connection_retries=1,
        request_retries=1,
        flood_sleep_threshold=0,
        receive_updates=False,
    )
    client.session.save_entities = False
    try:
        await asyncio.wait_for(client.connect(), timeout=30)
        if not await client.is_user_authorized():
            if arguments.check:
                print("API sozlamalari tayyor. Akkauntga kirish tasdig'i kutilmoqda.")
                return 2
            number = (
                arguments.phone
                or input("@nishonboyev7 akkaunti telefoni (+998...): ").strip()
            )
            if not re.fullmatch(r"\+[1-9][0-9]{6,14}", number):
                raise ValueError("Telefonni xalqaro formatda kiriting, masalan +998...")
            sent = await client.send_code_request(number)
            print("Telegram ilovangizdagi kirish kodini tekshiring.")
            code = getpass.getpass("Telegram kirish kodi (maxfiy): ").strip()
            try:
                await client.sign_in(number, code, phone_code_hash=sent.phone_code_hash)
            except errors.SessionPasswordNeededError:
                password = getpass.getpass("Telegram ikki bosqichli paroli (maxfiy): ")
                await client.sign_in(password=password)
        account = await client.get_me()
        if not account or account.bot:
            raise ValueError("Demo uchun shaxsiy Telegram akkauntiga kiring.")
        username = (account.username or "").lower()
        if username != arguments.username.lstrip("@").lower():
            raise ValueError(
                "Ulangan akkaunt foydalanuvchi nomi kutilgan akkauntga mos kelmadi. "
                "Telegram sozlamalarini tekshiring."
            )
        print(f"Telegram akkaunti ulandi: @{username}")
        print(
            "Mahalliy sessiya saqlandi. AI va qo'ng'iroq integratsiyasi keyingi bosqich."
        )
        return 0
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the saved session.")
    parser.add_argument(
        "--username", default="nishonboyev7", help="Expected caller username."
    )
    parser.add_argument("--phone", help="Caller phone in international format.")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.CRITICAL)
    try:
        return asyncio.run(connect_account(arguments))
    except errors.FloodWaitError as error:
        print(f"Telegram {error.seconds} soniya kutishni so'radi. Keyin qayta oching.")
    except errors.PhoneCodeInvalidError:
        print("Kirish kodi mos kelmadi. Dasturni qayta ochib yangi kod bilan kiring.")
    except errors.PhoneCodeExpiredError:
        print("Kirish kodi muddati tugadi. Dasturni qayta oching.")
    except errors.PhoneNumberUnoccupiedError:
        print("Bu telefon raqamida Telegram akkaunti topilmadi.")
    except errors.PasswordHashInvalidError:
        print("Ikki bosqichli parol mos kelmadi. Parolni tekshirib qayta oching.")
    except errors.RPCError as error:
        print(f"Telegram ulanishi yakunlanmadi ({type(error).__name__}).")
    except (TimeoutError, OSError):
        print(
            "Ulanish yoki mahalliy fayl ochilmadi. Internet va fayl ruxsatlarini tekshiring."
        )
    except (ValueError, json.JSONDecodeError) as error:
        # Validation messages contain field names only, never supplied secrets.
        print(
            str(error)
            if not isinstance(error, json.JSONDecodeError)
            else "API sozlamasi ochilmadi."
        )
    except (KeyboardInterrupt, EOFError):
        print("Ulanish oynasi yopildi. Keyin qayta davom ettirishingiz mumkin.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
