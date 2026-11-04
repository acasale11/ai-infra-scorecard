"""Classification and row building for the OpenRouter collector, no network."""

import collect_openrouter as co


def test_classify_open_by_published_weights():
    cls, reason = co.classify({"id": "meta/llama-4", "hugging_face_id": "meta/llama-4"})
    assert cls == co.OPEN
    assert "hugging_face_id" in reason


def test_classify_closed_by_org_list():
    cls, reason = co.classify({"id": "openai/gpt-6"})
    assert cls == co.CLOSED


def test_classify_unknown_is_never_guessed():
    cls, reason = co.classify({"id": "someorg/mystery-model"})
    assert cls == co.UNKNOWN


def test_build_rows_two_per_model_and_unit_conversion():
    payload = {"data": [
        {"id": "openai/gpt-6",
         "pricing": {"prompt": "0.000002", "completion": "0.000008"}},
        {"id": "meta/llama-4", "hugging_face_id": "meta/llama-4",
         "pricing": {"prompt": "0.0000001", "completion": "0.0000004"}},
    ]}
    rows, skipped, counts, unclassified = co.build_rows(
        payload, "2026-11-02", "2026-11-02T00:00:00Z", "raw.json")
    assert len(rows) == 4  # two models, input and output each
    gpt_out = [r for r in rows if r["entity"] == "openai/gpt-6"
               and r["metric"] == "openrouter_price_output"][0]
    # USD per token to USD per million tokens.
    assert gpt_out["value"] == "8.000000"
    assert gpt_out["unit"] == "usd_per_mtok"
    assert gpt_out["entity_class"] == co.CLOSED


def test_build_rows_skips_aliases_and_variable_prices():
    payload = {"data": [
        {"id": "~alias/model", "pricing": {"prompt": "0.1", "completion": "0.1"}},
        {"id": "router/auto", "pricing": {"prompt": "-1", "completion": "-1"}},
        {"id": "x/novar", "pricing": {"prompt": None, "completion": None}},
    ]}
    rows, skipped, counts, unclassified = co.build_rows(
        payload, "2026-11-02", "2026-11-02T00:00:00Z", "raw.json")
    assert rows == []
    assert "~alias/model" in skipped["alias"]
    assert "router/auto" in skipped["variable_price"]
    assert "x/novar" in skipped["variable_price"]
