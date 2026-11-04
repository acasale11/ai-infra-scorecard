"""The pure readers in check_alerts: FRED series, mid-tier gap, rows added."""

import csv

import check_alerts as ca

SCORECARD_HEADER = ["date", "entity", "entity_class", "metric", "value",
                    "unit", "source", "source_url", "notes"]


def write_scorecard(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SCORECARD_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in SCORECARD_HEADER})


def write_bases(path, rows):
    header = ["date", "model_id", "weight_class", "intelligence_index",
              "cheapest_fp8_output"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_fred_series_only_reads_fred_rows(tmp_path):
    p = tmp_path / "credit.csv"
    write_scorecard(p, [
        {"date": "2026-11-01", "metric": "ig_oas", "value": "80", "source": "FRED"},
        {"date": "2026-11-02", "metric": "ig_oas", "value": "82", "source": "FRED"},
        {"date": "2026-11-02", "metric": "instrument_rate_stated", "value": "7",
         "source": "SEC XBRL instance document"},
    ])
    series = ca.fred_series(str(p))
    assert series["ig_oas"] == {"2026-11-01": 80.0, "2026-11-02": 82.0}
    assert "instrument_rate_stated" not in series


def test_mid_tier_gap_ratio_above_floor(tmp_path):
    p = tmp_path / "bases.csv"
    write_bases(p, [
        {"date": "2026-11-02", "model_id": "o", "weight_class": "open_weights",
         "intelligence_index": "30", "cheapest_fp8_output": "0.20"},
        {"date": "2026-11-02", "model_id": "c", "weight_class": "closed_weights",
         "intelligence_index": "30", "cheapest_fp8_output": "0.50"},
        {"date": "2026-11-02", "model_id": "dumb", "weight_class": "open_weights",
         "intelligence_index": "5", "cheapest_fp8_output": "0.01"},
    ])
    assert ca.mid_tier_gap(str(p), "2026-11-02") == 2.5


def test_mid_tier_gap_none_when_a_side_missing(tmp_path):
    p = tmp_path / "bases.csv"
    write_bases(p, [
        {"date": "2026-11-02", "model_id": "o", "weight_class": "open_weights",
         "intelligence_index": "30", "cheapest_fp8_output": "0.20"},
    ])
    assert ca.mid_tier_gap(str(p), "2026-11-02") is None


def test_rows_added_counts_the_run_date(tmp_path):
    p = tmp_path / "prices.csv"
    write_scorecard(p, [
        {"date": "2026-11-02", "metric": "openrouter_price_input", "value": "1"},
        {"date": "2026-11-02", "metric": "openrouter_price_output", "value": "2"},
        {"date": "2026-10-30", "metric": "openrouter_price_input", "value": "1"},
    ])
    assert ca.rows_added(str(p), "2026-11-02") == 2
