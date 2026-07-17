import hashlib
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "text_event_web_v1.json"
REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "source",
    "published_at",
    "collected_at",
    "text",
    "language",
    "author_id",
    "url",
    "asset_mentions",
    "metrics",
    "provenance",
    "content_hash",
}


def test_golden_web_contract_fixture_is_self_consistent() -> None:
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    canonical = {
        key: event[key]
        for key in ("author_id", "published_at", "source", "text", "url")
    }
    content_hash = hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    assert set(event) == REQUIRED_FIELDS
    assert event["schema_version"] == "1.0.0"
    assert event["source"] == "google_news"
    assert event["event_id"].startswith("google_news:")
    assert event["content_hash"] == content_hash
