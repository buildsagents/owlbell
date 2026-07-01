"""Audit request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, field_validator


class AuditRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    website: HttpUrl | None = None
    contact_name: str | None = Field(default=None, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    service_area: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return value.lower()


class AuditLeak(BaseModel):
    area: str
    finding: str
    recommended_module: str


class AuditResponse(BaseModel):
    id: str
    status: str
    company_name: str
    summary: str
    likely_leaks: list[AuditLeak]
    next_step: str
