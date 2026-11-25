"""Request contracts. Money crosses the API as decimal strings in UZS."""

from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Contract):
    phone: str = Field(min_length=9, max_length=24)
    password: str = Field(min_length=8, max_length=128)


class Registration(Login):
    name: str = Field(min_length=2, max_length=100)
    business_name: str = Field(min_length=2, max_length=120)


class BusinessUpdate(Contract):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=9, max_length=24)
    sector: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=300)


class CustomerInput(Contract):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=9, max_length=24)
    company: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=2000)
    contact_allowed: bool = True


class DebtInput(Contract):
    customer_id: str
    title: str = Field(min_length=2, max_length=160)
    amount: str = Field(min_length=1, max_length=30)
    issued_on: date
    due_on: date
    reference: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=2000)


class DebtUpdate(DebtInput):
    version: int = Field(ge=1)
    reason: str = Field(default="", max_length=500)


class ArchiveInput(Contract):
    archived: bool


class PaymentInput(Contract):
    debt_id: str
    amount: str = Field(min_length=1, max_length=30)
    paid_on: date
    method: Literal["cash", "transfer", "terminal", "other"]
    note: str = Field(default="", max_length=2000)


class RefundInput(Contract):
    amount: str = Field(min_length=1, max_length=30)
    refunded_on: date
    reason: str = Field(min_length=3, max_length=1000)


class PromiseInput(Contract):
    debt_id: str
    amount: str = Field(min_length=1, max_length=30)
    due_on: date
    note: str = Field(default="", max_length=2000)


class PromiseUpdate(PromiseInput):
    version: int = Field(ge=1)


class VersionInput(Contract):
    version: int = Field(ge=1)


class DisputeInput(Contract):
    debt_id: str
    reason: str = Field(min_length=3, max_length=2000)


class ResolutionInput(Contract):
    resolution: str = Field(min_length=3, max_length=2000)
    version: int = Field(ge=1)


class NoteInput(Contract):
    text: str = Field(min_length=1, max_length=3000)


class PasswordChange(Contract):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TeamInput(Login):
    name: str = Field(min_length=2, max_length=100)
    role: Literal["manager", "viewer"]


class TeamUpdate(Contract):
    role: Literal["manager", "viewer"]
    active: bool


class ImportCommit(Contract):
    rows: list[int] = Field(min_length=1, max_length=2000)
    accept_duplicates: list[int] = Field(default_factory=list, max_length=2000)


class NotificationRead(Contract):
    keys: list[str] = Field(max_length=500)
