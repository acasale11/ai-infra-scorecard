"""The integrity validator: good data passes, each kind of break is caught."""

import csv
import json

import validate_data as vd

HEADER = vd.SCORECARD_HEADER
RUN = "2026-11-02"


def write(path, rows, header=HEADER):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def good_row(**kw):
    base = {"date": "2026-11-02", "entity": "x", "entity_class": "open_weights",
            "metric": "provider_price_min", "value": "0.20",
            "unit": "usd_per_mtok", "source": "OpenRouter endpoints API",
            "source_url": "https://example", "notes": ""}
    base.update(kw)
    return base


def run_check(path):
    fails = []
    vd.check_file(str(path), RUN, fails)
    return fails


def test_good_file_passes(tmp_path):
    p = tmp_path / "open_source_share.csv"
    write(p, [good_row(metric="provider_price_min"),
              good_row(metric="provider_price_max", value="9.0")])
    assert run_check(p) == []


def test_bad_header_is_caught(tmp_path):
    p = tmp_path / "open_source_share.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write("date,value\n2026-11-02,1\n")
    assert any("header" in f for f in run_check(p))


def test_duplicate_key_is_caught(tmp_path):
    p = tmp_path / "elasticity_prices.csv"
    write(p, [good_row(entity="m", metric="openrouter_price_input"),
              good_row(entity="m", metric="openrouter_price_input")])
    assert any("duplicate" in f for f in run_check(p))


def test_future_date_is_caught(tmp_path):
    p = tmp_path / "open_source_share.csv"
    write(p, [good_row(date="2027-01-01")])
    assert any("future" in f for f in run_check(p))


def test_unit_switch_is_caught(tmp_path):
    p = tmp_path / "open_source_share.csv"
    write(p, [good_row(metric="provider_price_min", unit="usd_per_mtok"),
              good_row(metric="provider_price_min", unit="ratio",
                       entity="y")])
    assert any("unit" in f for f in run_check(p))


def test_non_numeric_value_is_caught(tmp_path):
    p = tmp_path / "open_source_share.csv"
    write(p, [good_row(value="cheap")])
    assert any("not a number" in f for f in run_check(p))


def test_empty_source_url_on_non_derived_is_caught(tmp_path):
    p = tmp_path / "open_source_share.csv"
    write(p, [good_row(source_url="")])
    assert any("source_url" in f for f in run_check(p))


def test_derived_row_may_omit_source_url(tmp_path):
    p = tmp_path / "elasticity.csv"
    write(p, [good_row(metric="price_advantage_midtier_fp8", unit="x",
                       entity="mid_tier", entity_class="aggregate",
                       value="2.5", source="derived from data/price_bases.csv",
                       source_url="")])
    assert run_check(p) == []


def test_date_valued_metric_accepts_a_date(tmp_path):
    p = tmp_path / "credit.csv"
    write(p, [good_row(metric="instrument_maturity_date", unit="date",
                       value="2031-06-18", source="SEC XBRL instance document",
                       source_url="https://sec")])
    assert run_check(p) == []


def test_credit_fred_duplicate_is_caught(tmp_path):
    p = tmp_path / "credit.csv"
    write(p, [good_row(metric="ig_oas", unit="bps", value="80", entity="",
                       entity_class="", source="FRED", source_url="https://fred"),
              good_row(metric="ig_oas", unit="bps", value="80", entity="",
                       entity_class="", source="FRED", source_url="https://fred")])
    assert any("FRED" in f and "duplicate" in f for f in run_check(p))


def test_credit_issuer_facts_may_repeat_across_filings(tmp_path):
    # Same instrument, same date and metric, different accession in notes.
    # This is two filings, not a double-run, and must not be flagged.
    p = tmp_path / "credit.csv"
    common = dict(metric="instrument_rate_stated", unit="pct", value="6.75",
                  entity="APLD:NoteMember", entity_class="borrower",
                  source="SEC XBRL instance document", source_url="https://sec")
    write(p, [good_row(notes="10-Q acc-1 filed 2026-07; collected 2026-08-01",
                       **common),
              good_row(notes="10-Q acc-2 filed 2026-10; collected 2026-11-02",
                       **common)])
    assert run_check(p) == []


def test_merged_instrument_rate_metric_is_caught(tmp_path):
    p = tmp_path / "credit.csv"
    write(p, [good_row(metric="instrument_rate", unit="pct", value="7",
                       source="SEC XBRL instance document",
                       source_url="https://sec")])
    assert any("instrument_rate" in f for f in run_check(p))


# ---- core KPI presence and freshness -----------------------------------

def test_core_kpi_fresh_passes(tmp_path, monkeypatch):
    credit = tmp_path / "credit.csv"
    write(credit, [good_row(metric="ig_oas", unit="bps", value="80",
                            source="FRED", source_url="https://fred")])
    cfg = {"pillars": {"credit": {"weekly": [
        {"metric": "ig_oas", "unit": "bps", "source_file": str(credit),
         "staleness_days": 10}]}}}
    cfg_path = tmp_path / "core.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(vd, "CORE_KPIS", str(cfg_path))
    fails = []
    vd.check_core_kpis(RUN, fails)
    assert fails == []


def test_core_kpi_stale_is_caught(tmp_path, monkeypatch):
    credit = tmp_path / "credit.csv"
    write(credit, [good_row(date="2026-10-01", metric="ig_oas", unit="bps",
                            value="80", source="FRED", source_url="https://f")])
    cfg = {"pillars": {"credit": {"weekly": [
        {"metric": "ig_oas", "unit": "bps", "source_file": str(credit),
         "staleness_days": 10}]}}}
    cfg_path = tmp_path / "core.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(vd, "CORE_KPIS", str(cfg_path))
    fails = []
    vd.check_core_kpis(RUN, fails)
    assert any("stale" in f for f in fails)


def test_core_kpi_missing_is_caught(tmp_path, monkeypatch):
    credit = tmp_path / "credit.csv"
    write(credit, [good_row(metric="bbb_oas", unit="bps", value="80",
                            source="FRED", source_url="https://fred")])
    cfg = {"pillars": {"credit": {"weekly": [
        {"metric": "ig_oas", "unit": "bps", "source_file": str(credit),
         "staleness_days": 10}]}}}
    cfg_path = tmp_path / "core.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(vd, "CORE_KPIS", str(cfg_path))
    fails = []
    vd.check_core_kpis(RUN, fails)
    assert any("missing" in f for f in fails)
