"""Parsing for the Artificial Analysis collector, no network."""

import collect_aa_index as C


def test_variant_parsed_from_name():
    assert C.variant_of("GPT-6 Sol (High)") == "High"
    assert C.variant_of("Claude Haiku 5.5") == ""


def test_creator_name_handles_dict_or_string():
    assert C.creator_name({"model_creator": {"name": "OpenAI"}}) == "OpenAI"
    assert C.creator_name({"model_creator": "Anthropic"}) == "Anthropic"
    assert C.creator_name({}) == ""


def test_build_rows_keeps_scored_and_parses_fields():
    models = [
        {"slug": "gpt-6-sol-high", "name": "GPT-6 Sol (High)",
         "model_creator": {"name": "OpenAI"},
         "evaluations": {"artificial_analysis_intelligence_index": 55}},
        {"slug": "unscored", "name": "Unscored Model",
         "model_creator": "Nobody", "evaluations": {}},
    ]
    rows, scored = C.build_rows(models, 5, "2026-11-04", "2026-11-04T00:00:00Z")
    assert scored == 1
    assert len(rows) == 1
    r = rows[0]
    assert r["intelligence_index"] == 55
    assert r["reasoning_variant"] == "High"
    assert r["index_version"] == 5
    assert r["model_creator"] == "OpenAI"
    assert r["date"] == "2026-11-04"
