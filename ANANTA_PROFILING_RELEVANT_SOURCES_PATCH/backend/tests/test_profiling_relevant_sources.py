from app.services.profiling import (
    _canonicalize_url,
    _select_relevant_sources,
    _select_sources_for_synthesis,
)


def test_canonicalize_url_removes_tracking_and_fragment():
    url = "https://example.com/news/item/?utm_source=openai&b=2&a=1#section"
    assert _canonicalize_url(url) == "https://example.com/news/item?a=1&b=2"


def test_catalog_prefers_official_and_respects_limit():
    sources = [
        {"url": "https://random.example.com/profile/dedi-prasetyo", "title": "Dedi Prasetyo", "kind": "web"},
        {"url": "https://tribratanews.polri.go.id/blog/dedi-prasetyo", "title": "Dedi Prasetyo", "kind": "web"},
        {"url": "https://music.apple.com/us/artist/dedi/1", "title": "Dedi", "kind": "web"},
    ]
    selected = _select_sources_for_synthesis(
        sources,
        target={"name": "Dedi Prasetyo"},
        research_text="",
        limit=2,
    )
    assert len(selected) == 2
    assert selected[0]["url"].startswith("https://tribratanews.polri.go.id")
    assert [item["id"] for item in selected] == ["S1", "S2"]


def test_only_referenced_sources_are_returned_and_per_fact_is_capped():
    sources = [
        {"id": "S1", "url": "https://polri.go.id/a", "title": "A", "kind": "web"},
        {"id": "S2", "url": "https://polri.go.id/b", "title": "B", "kind": "web"},
        {"id": "S3", "url": "https://example.com/c", "title": "C", "kind": "web"},
        {"id": "S4", "url": "https://example.com/d", "title": "D", "kind": "web"},
    ]
    profile = {
        "identity": {
            "full_name": {
                "value": "Dedi Prasetyo",
                "status": "confirmed",
                "confidence": 0.95,
                "source_ids": ["S1", "S2", "S3", "S4"],
            }
        },
        "education": [
            {"status": "confirmed", "confidence": 0.9, "source_ids": ["S2"]}
        ],
    }

    cleaned, relevant = _select_relevant_sources(
        profile,
        sources,
        target={"name": "Dedi Prasetyo"},
        limit=2,
    )

    assert len(relevant) == 2
    allowed = {item["id"] for item in relevant}
    assert set(cleaned["identity"]["full_name"]["source_ids"]).issubset(allowed)
    assert len(cleaned["identity"]["full_name"]["source_ids"]) <= 3
    assert all(item["id"] in {"S1", "S2", "S3", "S4"} for item in relevant)
