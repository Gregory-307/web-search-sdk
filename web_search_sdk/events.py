"""Convert structured web results to the suite's versioned TextEvent record."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    field_validator,
    model_validator,
)

from .models import SearchItem

type JsonScalar = str | int | float | bool | None

_SECRET_KEYS = {
    "access_token",
    "api_key",
    "auth_token",
    "authorization",
    "cookie",
    "cookies",
    "passwd",
    "password",
    "refresh_token",
    "secret",
}


def _check_json(value: JsonValue | JsonScalar, *, path: str) -> None:
    """Reject secret-shaped keys and non-finite values recursively."""

    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            snake_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
            normalized_key = re.sub(r"[^a-z0-9]+", "_", snake_key.lower()).strip("_")
            if normalized_key in _SECRET_KEYS:
                raise ValueError(f"{path}.{key} is a prohibited secret-bearing field")
            _check_json(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_json(child, path=f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} must contain only finite numbers")


def _utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _utc_text(value: datetime | None) -> str | None:
    return (
        None
        if value is None
        else _utc(value, field_name="published_at").isoformat().replace("+00:00", "Z")
    )


def _content_hash(
    *,
    source: str,
    published_at: datetime | None,
    text: str,
    author_id: str | None,
    url: str | HttpUrl | None,
) -> str:
    payload = {
        "author_id": author_id,
        "published_at": _utc_text(published_at),
        "source": source,
        "text": text,
        "url": str(url) if url is not None else None,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class TextEventRecord(BaseModel):
    """Producer-side representation of the sentiment suite's TextEvent v1."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: Literal["1.0.0"] = "1.0.0"
    event_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*:[A-Za-z0-9][A-Za-z0-9._~:-]*$")
    source: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    published_at: datetime | None
    collected_at: datetime
    text: str = Field(min_length=1)
    language: str | None = Field(default=None, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    author_id: str | None = None
    url: HttpUrl | None = None
    asset_mentions: list[str] = Field(default_factory=list)
    metrics: dict[str, JsonScalar] = Field(default_factory=dict)
    provenance: dict[str, JsonValue]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("published_at")
    @classmethod
    def _normalize_published(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value, field_name="published_at")

    @field_validator("collected_at")
    @classmethod
    def _normalize_collected(cls, value: datetime) -> datetime:
        return _utc(value, field_name="collected_at")

    @field_validator("text")
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text cannot be blank")
        return value

    @field_validator("author_id")
    @classmethod
    def _reject_blank_author(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("author_id cannot be blank")
        return value

    @field_validator("asset_mentions")
    @classmethod
    def _normalize_assets(cls, value: list[str]) -> list[str]:
        normalized = {
            asset.strip().upper().removeprefix("$")
            for asset in value
            if asset.strip().removeprefix("$")
        }
        for asset in normalized:
            if not re.fullmatch(r"^[A-Z0-9][A-Z0-9._-]*$", asset):
                raise ValueError(f"invalid asset mention: {asset!r}")
        return sorted(normalized)

    @field_validator("metrics")
    @classmethod
    def _validate_metrics(cls, value: dict[str, JsonScalar]) -> dict[str, JsonScalar]:
        if any(not key.strip() for key in value):
            raise ValueError("metric names cannot be blank")
        _check_json(value, path="metrics")
        return value

    @field_validator("provenance")
    @classmethod
    def _validate_provenance(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        _check_json(value, path="provenance")
        for key in ("provider", "parser_version"):
            if not isinstance(value.get(key), str) or not str(value[key]).strip():
                raise ValueError(f"provenance.{key} is required")
        return value

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> TextEventRecord:
        if self.event_id.partition(":")[0] != self.source:
            raise ValueError("event_id namespace must match source")
        if (
            self.published_at is None
            and self.provenance.get("event_time_fallback") != "collected_at"
        ):
            raise ValueError("missing published_at requires a recorded collection-time fallback")
        expected = _content_hash(
            source=self.source,
            published_at=self.published_at,
            text=self.text,
            author_id=self.author_id,
            url=self.url,
        )
        if self.content_hash != expected:
            raise ValueError("content_hash does not match canonical content")
        return self


def text_event_from_search_item(
    item: SearchItem,
    *,
    collected_at: datetime,
    asset_mentions: list[str] | None = None,
    language: str | None = "en",
    provider_id: str | None = None,
    query_alias: str,
    parser_version: str = "web-search-sdk/0.2.1",
    asset_extraction_version: str = "1.0.0",
    extra_metrics: Mapping[str, JsonScalar] | None = None,
) -> TextEventRecord:
    """Build a deterministic TextEvent without importing a sibling repository."""

    content_hash = _content_hash(
        source=item.source,
        published_at=item.published_at,
        text=item.text,
        author_id=None,
        url=item.url,
    )
    identifier = provider_id.strip() if provider_id is not None else content_hash[:32]
    provenance: dict[str, JsonValue] = {
        "provider": item.source,
        "parser_version": parser_version,
        "query_alias": query_alias,
        "asset_extraction_version": asset_extraction_version,
    }
    if item.published_at is None:
        provenance["event_time_fallback"] = "collected_at"
    metrics: dict[str, JsonScalar] = {"rank": item.rank}
    metrics.update(extra_metrics or {})
    return TextEventRecord(
        event_id=f"{item.source}:{identifier}",
        source=item.source,
        published_at=item.published_at,
        collected_at=collected_at,
        text=item.text,
        language=language,
        author_id=None,
        url=item.url,
        asset_mentions=asset_mentions or [],
        metrics=metrics,
        provenance=provenance,
        content_hash=content_hash,
    )


__all__ = ["TextEventRecord", "text_event_from_search_item"]
