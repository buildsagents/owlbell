"""api/schemas/business.py - Business settings, FAQ, hours schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BusinessAddress(BaseModel):
    model_config = ConfigDict(frozen=True)
    street: Optional[str] = Field(default=None, max_length=300)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)


class BusinessProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str = Field(..., max_length=200)
    slug: str = Field(..., max_length=100)
    description: Optional[str] = Field(default=None, max_length=5000)
    phone_number: str = Field(..., max_length=20)
    email: Optional[str] = Field(default=None, max_length=200)
    website: Optional[str] = Field(default=None, max_length=500)
    address: Optional[BusinessAddress] = Field(default=None)
    timezone: str
    industry: Optional[str] = Field(default=None, max_length=100)
    logo_url: Optional[str] = Field(default=None)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


# -- AI Configuration -----------------------------------------------------

class AIVoiceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    voice_id: str = Field(default="en_US-lessac-medium")
    greeting_template: str = Field(
        default="Hello, thank you for calling {business_name}. This is your AI assistant. How may I help you today?",
        max_length=1000,
    )
    personality: str = Field(default="professional_friendly")
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    language: str = Field(default="en")


class AICallHandlingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_call_duration_minutes: int = Field(default=30, ge=1, le=120)
    enable_call_recording: bool = Field(default=True)
    enable_transcript: bool = Field(default=True)
    take_messages_when: str = Field(default="always", pattern="^(always|unavailable|never)$")
    transfer_when: str = Field(default="on_request", pattern="^(on_request|never|urgent_only)$")
    attempt_human_transfer: bool = Field(default=True)
    transfer_targets: list[dict] = Field(default_factory=list)
    custom_instructions: Optional[str] = Field(default=None, max_length=10000)


class BusinessSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    profile: BusinessProfile
    ai_voice: AIVoiceConfig
    ai_handling: AICallHandlingConfig


# -- FAQ / Knowledge Base -------------------------------------------------

class FAQEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    question: str = Field(..., max_length=1000)
    answer: str = Field(..., max_length=10000)
    category: Optional[str] = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = Field(default=True)
    hit_count: int = Field(default=0)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


class FAQCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    question: str = Field(..., max_length=1000)
    answer: str = Field(..., max_length=10000)
    category: Optional[str] = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list)


class FAQUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    question: Optional[str] = Field(default=None, max_length=1000)
    answer: Optional[str] = Field(default=None, max_length=10000)
    category: Optional[str] = Field(default=None, max_length=100)
    tags: Optional[list[str]] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class FAQBulkImportRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    entries: list[FAQCreateRequest] = Field(..., max_length=100)
    replace_existing: bool = Field(default=False)


class FAQListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[FAQEntry]
    total: int
    categories: list[str]


# -- Settings Update Requests ---------------------------------------------

class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    phone_number: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=200)
    website: Optional[str] = Field(default=None, max_length=500)
    address: Optional[BusinessAddress] = Field(default=None)
    timezone: Optional[str] = Field(default=None)
    industry: Optional[str] = Field(default=None, max_length=100)


class AIVoiceUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    voice_id: Optional[str] = Field(default=None)
    greeting_template: Optional[str] = Field(default=None, max_length=1000)
    personality: Optional[str] = Field(default=None)
    speaking_rate: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    language: Optional[str] = Field(default=None)


class AIHandlingUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_call_duration_minutes: Optional[int] = Field(default=None, ge=1, le=120)
    enable_call_recording: Optional[bool] = Field(default=None)
    enable_transcript: Optional[bool] = Field(default=None)
    take_messages_when: Optional[str] = Field(default=None, pattern="^(always|unavailable|never)$")
    transfer_when: Optional[str] = Field(default=None, pattern="^(on_request|never|urgent_only)$")
    custom_instructions: Optional[str] = Field(default=None, max_length=10000)


# -- Routing Rules --------------------------------------------------------

class RoutingRule(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID
    tenant_id: UUID
    name: str = Field(..., max_length=200)
    condition: str = Field(..., max_length=500)
    action: str = Field(..., max_length=500)
    priority: int = Field(default=0, ge=0, le=1000)
    is_active: bool = Field(default=True)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


class RoutingRuleUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    rules: list[dict]
