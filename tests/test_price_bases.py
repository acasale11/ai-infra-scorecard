"""The elasticity aggregate: mid-tier floor, cheapest per class, ratio."""

import price_bases as pb


def row(date, model, cls, index, fp8_out):
    return {"date": date, "model_id": model, "weight_class": cls,
            "intelligence_index": str(index), "cheapest_fp8_output": fp8_out}


def test_cheapest_per_class_above_the_floor():
    rows = [
        row("2026-11-02", "open-cheap-but-dumb", "open_weights", 10, "0.01"),
        row("2026-11-02", "open-midtier", "open_weights", 30, "0.20"),
        row("2026-11-02", "open-dearer", "open_weights", 40, "0.40"),
        row("2026-11-02", "closed-midtier", "closed_weights", 35, "0.50"),
    ]
    agg = pb.midtier_aggregate(rows, "2026-11-02")
    # The below-floor open model is ignored even though it is cheapest.
    assert agg == (0.20, "open-midtier", 0.50, "closed-midtier")


def test_other_dates_are_ignored():
    rows = [
        row("2026-10-30", "open", "open_weights", 30, "0.10"),
        row("2026-11-02", "open", "open_weights", 30, "0.20"),
        row("2026-11-02", "closed", "closed_weights", 30, "0.50"),
    ]
    agg = pb.midtier_aggregate(rows, "2026-11-02")
    assert agg[0] == 0.20


def test_missing_a_side_returns_none():
    rows = [row("2026-11-02", "open", "open_weights", 30, "0.20")]
    assert pb.midtier_aggregate(rows, "2026-11-02") is None


def test_pillar_rows_carry_the_ratio_and_are_derived():
    agg = (0.20, "open-midtier", 0.50, "closed-midtier")
    rows = pb.elasticity_pillar_rows(agg, "2026-11-02")
    assert len(rows) == 3
    ratio = [r for r in rows if r["metric"] == "price_advantage_midtier_fp8"][0]
    assert ratio["value"] == "2.5000"
    assert ratio["unit"] == "x"
    # Derived rows have no source_url, by design.
    assert all(r["source"].startswith("derived") for r in rows)
    assert all(r["source_url"] == "" for r in rows)
