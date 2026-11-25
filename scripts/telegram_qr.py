"""Authorize the demo caller with Telegram's normal device-linking QR flow."""

import argparse
import asyncio
import queue
import threading
import tkinter as tk
from concurrent.futures import CancelledError
from tkinter import ttk

import qrcode
from connect_telegram import SESSION_PATH, credentials
from PIL import ImageTk
from telethon import TelegramClient, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--password-only", action="store_true")
    arguments = parser.parse_args()
    api_id, api_hash = credentials()
    updates = queue.Queue()
    state = {}
    window = tk.Tk()
    window.title("Tushum AI - Telegram akkauntini ulash")
    window.geometry("640x780")
    window.configure(background="#f4f7f8")
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(
        frame, text="Telegram akkauntini ulash", font=("Segoe UI", 22, "bold")
    ).pack(pady=12)
    ttk.Label(
        frame,
        text=(
            "@nishonboyev7 akkauntiga kirish kodi tasdiqlandi.\n"
            "Telegram ikki bosqichli parolingizni\n"
            "quyidagi maxfiy maydonga kiriting."
        )
        if arguments.password_only
        else (
            "Telefoningizda @nishonboyev7 akkauntini oching.\n"
            "Sozlamalar > Qurilmalar > Kompyuterga ulash\n"
            "bo'limidan quyidagi QR kodni skaner qiling."
        ),
        justify="center",
        font=("Segoe UI", 12),
    ).pack(pady=12)
    qr_label = ttk.Label(frame, anchor="center")
    qr_label.pack(pady=12)
    status = tk.StringVar(value="Telegram serveriga ulanmoqda...")
    ttk.Label(
        frame,
        textvariable=status,
        wraplength=560,
        justify="center",
        font=("Segoe UI", 12),
    ).pack(pady=12)
    password_frame = ttk.Frame(frame)
    ttk.Label(password_frame, text="Telegram ikki bosqichli paroli").pack()
    password_entry = ttk.Entry(password_frame, show="*", width=36)
    password_entry.pack(pady=8)

    def submit_password():
        future = state.get("password_future")
        if future is not None and not future.done():
            password = password_entry.get()
            if password:
                password_entry.delete(0, "end")
                state["loop"].call_soon_threadsafe(future.set_result, password)
                password_frame.pack_forget()
                status.set("Parol tekshirilmoqda...")

    ttk.Button(
        password_frame, text="Kirishni tasdiqlash", command=submit_password
    ).pack()
    password_entry.bind("<Return>", lambda _: submit_password())

    async def enter_password(client):
        while not await client.is_user_authorized():
            state["password_future"] = asyncio.get_running_loop().create_future()
            updates.put(("password", "Ikki bosqichli parolni shu oynaga kiriting."))
            password = await state["password_future"]
            try:
                await client.sign_in(password=password)
            except errors.PasswordHashInvalidError:
                updates.put(("status", "Parol mos kelmadi. Qayta kiriting."))

    async def authorize():
        client = TelegramClient(
            str(SESSION_PATH),
            api_id,
            api_hash,
            device_model="Tushum AI Demo",
            app_version="1.0.0",
            connection_retries=1,
            request_retries=1,
            flood_sleep_threshold=0,
        )
        client.session.save_entities = False
        try:
            await asyncio.wait_for(client.connect(), timeout=30)
            if arguments.password_only and not await client.is_user_authorized():
                await enter_password(client)
            elif not await client.is_user_authorized():
                login = await client.qr_login()
                while not await client.is_user_authorized():
                    updates.put(("qr", qrcode.make(login.url).resize((380, 380))))
                    try:
                        await login.wait(timeout=30)
                    except TimeoutError:
                        await login.recreate()
                    except errors.SessionPasswordNeededError:
                        await enter_password(client)
            account = await client.get_me()
            if (
                not account
                or account.bot
                or (account.username or "").lower() != "nishonboyev7"
            ):
                updates.put(
                    (
                        "finished",
                        "Ulangan akkaunt @nishonboyev7 ga mos kelmadi. Akkauntni tekshiring.",
                    )
                )
                return
            updates.put(
                ("finished", "@nishonboyev7 ulandi. Mahalliy sessiya saqlandi.")
            )
        except errors.FloodWaitError as error:
            updates.put(
                (
                    "finished",
                    f"Telegram {error.seconds} soniya kutishni so'radi. Keyin qayta oching.",
                )
            )
        except (TimeoutError, OSError):
            updates.put(
                (
                    "finished",
                    "Telegramga ulanish yakunlanmadi. Internetni tekshirib qayta oching.",
                )
            )
        except errors.RPCError as error:
            updates.put(
                (
                    "finished",
                    f"Telegram tasdig'i yakunlanmadi ({type(error).__name__}).",
                )
            )
        finally:
            await client.disconnect()

    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        state["loop"] = loop
        task = loop.create_task(authorize())
        state["task"] = task
        try:
            loop.run_until_complete(task)
        except (asyncio.CancelledError, CancelledError):
            pass
        except Exception:  # noqa: BLE001 - Provider errors must not expose auth details.
            updates.put(
                ("finished", "Ulanish to'xtadi. Oynani qayta ochib davom ettiring.")
            )
        finally:
            loop.close()

    def close():
        task = state.get("task")
        loop = state.get("loop")
        if task is not None and loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)
        window.destroy()

    def render_updates():
        while not updates.empty():
            kind, value = updates.get_nowait()
            if kind == "qr":
                qr_label.image = ImageTk.PhotoImage(value)
                qr_label.configure(image=qr_label.image)
                status.set(
                    "Telefoningiz orqali QR kodni skaner qiling. Kod avtomatik yangilanadi."
                )
            elif kind == "password":
                qr_label.configure(image="")
                password_frame.pack(pady=8)
                password_entry.focus_set()
                status.set(value)
            elif kind == "finished":
                qr_label.configure(image="")
                password_frame.pack_forget()
                status.set(value)
            else:
                status.set(value)
        window.after(150, render_updates)

    ttk.Button(frame, text="Yopish", command=close).pack(side="bottom", pady=8)
    window.protocol("WM_DELETE_WINDOW", close)
    threading.Thread(target=worker, daemon=True).start()
    window.after(150, render_updates)
    window.mainloop()


if __name__ == "__main__":
    main()
