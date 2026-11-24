"""Typed scientific records shared by adapters, audits, API, and reports."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"
    ERROR = "ERROR"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Provenance(BaseModel):
    source: str
    source_url: str | None = None
    dataset_revision: str | None = None
    retrieved_at: datetime | None = None
    ingestion_commit: str | None = None
    content_checksum: str | None = None
    quality_status: str | None = None


class Shot(BaseModel):
    model_config = ConfigDict(extra="allow")
    shot_id: int
    machine: str = "MAST"
    source_level: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class SignalMetadata(BaseModel):
    name: str
    original_name: str
    source: str
    units: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    shape: list[int] = Field(default_factory=list)
    diagnostic: str | None = None
    quality_status: str | None = None


class Finding(BaseModel):
    rule_id: str
    rule_version: str = "1.0.0"
    outcome: Outcome
    severity: Severity
    summary: str
    explanation: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    affected_interval: tuple[float, float] | None = None
    source: str | None = None


class AuditReport(BaseModel):
    shot_id: int
    dataset: str
    audited_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    findings: list[Finding]
    rules_evaluated: int
    rules_not_evaluated: int
    limitations: list[str] = Field(default_factory=list)
    provenance: Provenance


class TimeAxisResult(BaseModel):
    sample_count: int
    finite_count: int
    duplicate_count: int
    nonmonotonic_count: int
    median_interval: float | None = None
    irregularity_fraction: float | None = None
    negative_time_count: int
