from app.services import profiling


def _fact(value=None, status="not_found", confidence=0.0):
    return {"value": value, "status": status, "confidence": confidence}


def _profile():
    return {
        "identity": {
            "full_name": _fact("Dedi Prasetyo", "confirmed", 0.99),
            "current_position": _fact("Wakapolri", "confirmed", 0.98),
            "rank_or_class": _fact("Komjen Pol.", "confirmed", 0.98),
            "institution": _fact("Polri", "confirmed", 0.99),
            "region": _fact("Indonesia", "confirmed", 0.99),
            "identity_match_status": "confirmed",
            "identity_match_reason": "Nama, jabatan, dan instansi konsisten.",
            "identity_confidence": 0.99,
        },
        "photo": {
            "direct_image_url": "https://cdn.example/foto.jpg",
            "source_page_url": "https://example.com/sumber",
            "description": "Foto resmi target.",
            "status": "confirmed",
            "confidence": 0.95,
        },
        "personal_information": {
            "birth_place": _fact(None),
            "birth_date": _fact(None),
            "nrp_or_nip": _fact(None),
        },
        "education": [],
        "career_history": [],
        "awards": [],
        "wealth_reports": [],
        "public_news": [],
        "social_media": [],
        "public_family": [],
        "confirmed_summary": ["Target teridentifikasi dengan baik."],
        "unconfirmed_summary": [],
        "conflicts": [],
        "missing_information": [],
        "quality_notes": [],
    }


def _contains_source_ids(node):
    if isinstance(node, dict):
        if "source_ids" in (node.get("properties") or {}):
            return True
        return any(_contains_source_ids(value) for value in node.values())
    if isinstance(node, list):
        return any(_contains_source_ids(value) for value in node)
    return False


def test_schema_has_no_source_ids():
    assert not _contains_source_ids(profiling.PROFILE_SCHEMA_NO_REFERENCES)


def test_render_document_hides_all_references_and_photo_urls():
    text = profiling._render_document(
        _profile(),
        [{"id": "S1", "title": "Sumber", "url": "https://example.com"}],
    )
    assert "SUMBER" not in text
    assert "[S1]" not in text
    assert "https://" not in text
    assert "URL gambar" not in text
    assert "Halaman sumber" not in text


def test_one_pass_defaults_are_lightweight():
    assert profiling.settings.PROFILING_SEARCH_CONTEXT_SIZE == "low"
    assert profiling.settings.PROFILING_OPENAI_EFFORT == "medium"
    assert profiling.settings.PROFILING_OPENAI_MAX_RETRIES == 0


def test_generate_profile_uses_single_lightweight_call(monkeypatch):
    import asyncio
    import json

    profile = _profile()
    calls = []

    async def fake_post(payload):
        calls.append(payload)
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": json.dumps(profile)}
                    ],
                }
            ]
        }

    monkeypatch.setattr(profiling, "_post_responses", fake_post)
    result = asyncio.run(
        profiling.generate_profile({"name": "Dedi Prasetyo"}, include_images=True)
    )

    assert len(calls) == 1
    payload = calls[0]
    assert payload["tools"][0]["search_context_size"] == "low"
    assert "search_content_types" not in payload["tools"][0]
    assert "include" not in payload
    assert result["sources"] == []
    assert "SUMBER" not in result["document_text"]
    assert "https://" not in result["document_text"]
