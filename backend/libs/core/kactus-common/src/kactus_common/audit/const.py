"""Audit constants."""

from __future__ import annotations

from enum import StrEnum


class AuditOutcome(StrEnum):
    """Whether the audited action succeeded or failed."""

    SUCCESS = "success"
    FAILURE = "failure"
