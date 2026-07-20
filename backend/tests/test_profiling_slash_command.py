from app.services.profiling_command import parse_profiling_command
from app.services import profiling


def test_parse_profiling_name_only():
    is_command, target = parse_profiling_command("/profiling Dedi Prasetyo")
    assert is_command is True
    assert target == {
        "name": "Dedi Prasetyo",
        "known_position": None,
        "institution": None,
        "region": None,
        "known_period": None,
        "extra_context": None,
    }


def test_parse_profling_alias_and_context():
    is_command, target = parse_profiling_command(
        "/profling Dedi Prasetyo | Wakapolri | Polri | Indonesia | 2025-sekarang"
    )
    assert is_command is True
    assert target["name"] == "Dedi Prasetyo"
    assert target["known_position"] == "Wakapolri"
    assert target["institution"] == "Polri"
    assert target["region"] == "Indonesia"
    assert target["known_period"] == "2025-sekarang"


def test_parse_profiling_without_name_returns_usage_state():
    is_command, target = parse_profiling_command("/profiling")
    assert is_command is True
    assert target is None


def test_regular_message_is_not_command():
    is_command, target = parse_profiling_command("Apa itu profiling?")
    assert is_command is False
    assert target is None


def test_confirmed_fact_without_valid_source_is_downgraded():
    profile = {
        "field": {
            "value": "Contoh",
            "status": "confirmed",
            "confidence": 0.99,
            "source_ids": ["S999"],
        }
    }
    cleaned = profiling._clean_source_ids(profile, {"S1"})
    assert cleaned["field"]["source_ids"] == []
    assert cleaned["field"]["status"] == "unconfirmed"
    assert cleaned["field"]["confidence"] <= 0.6
