"""Matching OpenRouter ids to Artificial Analysis scores: highest variant, safe."""

import aa_match as M


def row(slug, name, idx, variant=""):
    return {"aa_slug": slug, "aa_name": name, "reasoning_variant": variant,
            "intelligence_index": idx}


def test_base_name_strips_reasoning_variant():
    assert M.base_name("GPT-6 Sol (High)") == "GPT-6 Sol"
    assert M.base_name("Claude Haiku 5.5") == "Claude Haiku 5.5"


def test_family_of_drops_org_and_suffix():
    assert M.family_of("openai/gpt-6-sol:free") == "gpt-6-sol"


def test_lookup_picks_highest_variant():
    rows = [row("gpt-6-sol-low", "GPT-6 Sol (Low)", "40", "Low"),
            row("gpt-6-sol-high", "GPT-6 Sol (High)", "55", "High"),
            row("gpt-6-sol-med", "GPT-6 Sol (Medium)", "48", "Medium")]
    lookup = M.build_lookup(rows)
    idx, ev = M.match_model("openai/gpt-6-sol", lookup)
    assert idx == 55.0
    assert "High" in ev


def test_lookup_reachable_by_any_variant_slug():
    rows = [row("gpt-6-sol-low", "GPT-6 Sol (Low)", "40", "Low"),
            row("gpt-6-sol-high", "GPT-6 Sol (High)", "55", "High")]
    lookup = M.build_lookup(rows)
    # Even matching against the low-variant slug returns the model's ceiling.
    idx, _ = M.match_model("vendor/gpt-6-sol-low", lookup)
    assert idx == 55.0


def test_normalized_match_ignores_punctuation_and_case():
    rows = [row("claude-haiku-5-5", "Claude Haiku 5.5", "33")]
    lookup = M.build_lookup(rows)
    idx, _ = M.match_model("anthropic/claude-haiku-5.5", lookup)
    assert idx == 33.0


def test_override_forces_a_match():
    rows = [row("mistral-large-4", "Mistral Large 4", "50")]
    lookup = M.build_lookup(rows)
    # Snapshot suffix would not match on its own.
    assert M.match_model("mistralai/mistral-large-4-0", lookup)[0] is None
    idx, ev = M.match_model("mistralai/mistral-large-4-0", lookup,
                            {"mistral-large-4-0": "Mistral Large 4"})
    assert idx == 50.0
    assert "override" in ev


def test_unmatched_returns_none_not_a_guess():
    rows = [row("claude-haiku-5-5", "Claude Haiku 5.5", "33")]
    lookup = M.build_lookup(rows)
    idx, ev = M.match_model("upstage/solar-pro4", lookup)
    assert idx is None
    assert "no AA match" in ev


def test_rows_without_index_are_skipped():
    rows = [row("a", "A", ""), row("b", "B", None)]
    assert M.build_lookup(rows) == {}
