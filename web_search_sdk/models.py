"""Truthful structured output models shared by web-search providers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class SearchStatus(StrEnum):
    """Provider outcome without conflating absence, blocking, and failure."""

    SUCCESS = "success"
    EMPTY = "empty"
    BLOCKED = "blocked"
    ERROR = "error"


class SearchItem(BaseModel):
    """One provider result before conversion to a sentiment text event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    title: str | None = None
    text: str = Field(min_length=1)
    url: HttpUrl | None = None
    published_at: datetime | None = None
    publisher: str | None = None
    rank: int = Field(ge=1)

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("title", "publisher")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("text")
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text cannot be blank")
        return value

    @field_validator("published_at")
    @classmethod
    def _normalize_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        return value.astimezone(UTC)


class SearchResponse(BaseModel):
    """Normalized provider response plus an explicit outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    query: str = Field(min_length=1)
    status: SearchStatus
    items: list[SearchItem] = Field(default_factory=list)
    top_words: list[str] = Field(default_factory=list)
    error: str | None = None
    blocked_reason: str | None = None

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("query")
    @classmethod
    def _reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query cannot be blank")
        return value

    @field_validator("top_words")
    @classmethod
    def _normalize_words(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(word.strip().lower() for word in value if word.strip()))

    @model_validator(mode="after")
    def _validate_status_details(self) -> Self:
        if self.status == SearchStatus.SUCCESS and not self.items:
            raise ValueError("success requires at least one item")
        if self.status != SearchStatus.SUCCESS and self.items:
            raise ValueError("non-success status cannot contain items")
        if self.status == SearchStatus.BLOCKED and not self.blocked_reason:
            raise ValueError("blocked requires blocked_reason")
        if self.status == SearchStatus.ERROR and not self.error:
            raise ValueError("error requires an error category")
        if self.status != SearchStatus.BLOCKED and self.blocked_reason is not None:
            raise ValueError("blocked_reason is valid only for blocked status")
        if self.status != SearchStatus.ERROR and self.error is not None:
            raise ValueError("error is valid only for error status")
        return self

    def as_dict(self, **legacy_fields: object) -> dict[str, object]:
        """Serialize canonical fields and explicitly supplied compatibility fields."""

        result = self.model_dump(mode="json")
        result.update(legacy_fields)
        return result


__all__ = ["SearchItem", "SearchResponse", "SearchStatus"]
