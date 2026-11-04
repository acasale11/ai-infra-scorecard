"""Verify each scored model's price against the model author's own endpoint.

Why this exists. The `pricing` field on OpenRouter's models list is the
cheapest endpoint across every provider serving that model. For a closed
model there is only one provider, so that is the author's list price. For an
open-weight model there are often forty, and the cheapest is a third-party
reseller, frequently at fp4 quantization. Comparing those two things puts a
discount reseller's quantized price against a frontier lab's list price and
calls the difference an open-weight discount. It is not like for like, and
the bias runs one way.

This collector pulls the endpoint list for every scored model and records the
first-party price: the endpoint operated by the organisation that made the
model. Both prices are kept, with the gap between them, so the distortion is
visible rather than silently corrected.

Spot checks against provider pricing pages on 2026-10-30 confirm the
first-party endpoint matches the published page:

    z-ai/glm-5.3-flash   Z.AI endpoint 0.15 / 0.50   docs.z.ai pricing 0.15 / 0.50
    z-ai/glm-5.3         Z.AI endpoint 1.40 / 4.40   docs.z.ai pricing 1.40 / 4.40
    anthropic/haiku-5.5  endpoint 0.10 / 0.50        claude.com/pricing 0.10 / 0.50
    anthropic/sonnet-5.5 endpoint 2.00 / 10.00       claude.com/pricing 2.00 / 10.00
    anthropic/opus-5.5   endpoint 4.00 / 20.00       claude.com/pricing 4.00 / 20.00

Writes data/price_verification.csv, one row per model per run date.

Usage:
    python scripts/verify_prices.py
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

CLASSES = "data/model_classification.csv"
# Raw per-model OpenRouter prices. Moved out of data/scorecard/elasticity.csv
# on 2026-11-03 so the pillar file holds only the mid-tier aggregate. See
# docs/decisions.md.
PRICES = "data/elasticity_prices.csv"
CACHE = "data/raw/openrouter_endpoints"
DEST = "data/price_verification.csv"
API = "https://openrouter.ai/api/v1/models/%s/endpoints"
UA = "ai-infra-scorecard research collector"

FIELDS = ["date", "model_id", "org", "weight_class",
          "headline_input", "headline_output", "headline_provider",
          "first_party_provider", "first_party_input", "first_party_output",
          "first_party_quantization", "output_gap_multiple",
          "endpoint_count", "zero_priced_endpoints", "flag", "notes"]

# OpenRouter organisation prefix -> how that organisation names its own
# endpoint. Only needed where the two differ by more than case and
# punctuation. Checkable against the endpoints response for any model.
PROVIDER_ALIASES = {
    "z-ai": "zai",
    "x-ai": "xai",
    "moonshotai": "moonshot",
    "bytedance-seed": "bytedance",
    "meta": "meta",
    "mistralai": "mistral",
    "qwen": "alibaba",
    "inclusionai": "alibaba",
    "thinkingmachines": "thinkingmachines",
    "aion-labs": "aionlabs",
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch(slug):
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:16]
    path = os.path.join(CACHE, "%s.json" % digest)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    req = urllib.request.Request(API % slug, headers={"User-Agent": UA})
    data = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as fh:
                data = json.loads(fh.read().decode("utf-8"))
            break
        except Exception:
            if attempt == 2:
                return None
            time.sleep(2 * (attempt + 1))
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()
    date = args.date

    with open(CLASSES, newline="", encoding="utf-8") as fh:
        cls = {r["model_id"]: r for r in csv.DictReader(fh)
               if r["date"] == date}
    price = {}
    with open(PRICES, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["date"] == date and r["metric"].startswith("openrouter_price_"):
                price.setdefault(r["entity"], {})[
                    r["metric"].replace("openrouter_price_", "")] = float(r["value"])

    targets = sorted(m for m, c in cls.items()
                     if ":" not in m and c["tier"] and m in price
                     and price[m]["output"] > 0)
    print("verifying %d scored base SKUs" % len(targets))

    rows = []
    for i, mid in enumerate(targets, 1):
        org = mid.split("/")[0]
        want = PROVIDER_ALIASES.get(org, norm(org))
        data = fetch(mid)
        head = price[mid]
        row = {
            "date": date, "model_id": mid, "org": org,
            "weight_class": cls[mid]["weight_class"],
            "headline_input": "%.6f" % head["input"],
            "headline_output": "%.6f" % head["output"],
            "headline_provider": "", "first_party_provider": "",
            "first_party_input": "", "first_party_output": "",
            "first_party_quantization": "", "output_gap_multiple": "",
            "endpoint_count": "", "zero_priced_endpoints": "",
            "flag": "", "notes": "",
        }
        if not data or "data" not in data:
            row["flag"] = "endpoints_unavailable"
            row["notes"] = "could not fetch %s" % (API % mid)
            rows.append(row)
            continue

        eps = data["data"].get("endpoints", [])
        row["endpoint_count"] = len(eps)
        priced = []
        zero = 0
        for e in eps:
            pr = e.get("pricing") or {}
            try:
                pi, po = float(pr.get("prompt")), float(pr.get("completion"))
            except (TypeError, ValueError):
                continue
            if pi < 0 or po < 0:
                continue
            if po == 0:
                zero += 1
                continue
            # service_tier is null on the standard endpoint and set on the
            # discounted or accelerated ones (flex, priority, ultrafast).
            # Batch is a separate model SKU and is already excluded upstream.
            # The tag suffix is NOT a tier marker: it usually denotes
            # quantization, and several authors serve only a quantized build
            # of their own model, so filtering on it would wrongly drop them.
            standard = e.get("service_tier") in (None, "", "standard")
            tag = e.get("tag") or ""
            priced.append((e.get("provider_name") or "", pi * 1e6, po * 1e6,
                           e.get("quantization") or "", standard, tag))
        row["zero_priced_endpoints"] = zero
        if not priced:
            row["flag"] = "no_priced_endpoint"
            rows.append(row)
            continue

        cheapest = min(priced, key=lambda t: t[2])
        row["headline_provider"] = "%s (%s)" % (cheapest[0], cheapest[5])

        fp = [t for t in priced if want and want in norm(t[0]) and t[4]]
        if not fp:
            row["flag"] = "no_first_party_endpoint"
            row["notes"] = ("no standard-tier endpoint operated by %s; "
                            "cheapest overall is %s" % (org, cheapest[0]))
            rows.append(row)
            continue

        best_fp = min(fp, key=lambda t: t[2])
        row["first_party_provider"] = "%s (%s)" % (best_fp[0], best_fp[5])
        row["first_party_input"] = "%.6f" % best_fp[1]
        row["first_party_output"] = "%.6f" % best_fp[2]
        row["first_party_quantization"] = best_fp[3]
        gap_out = best_fp[2] / head["output"] if head["output"] else 0
        gap_in = best_fp[1] / head["input"] if head["input"] else 0
        gap = max(gap_out, gap_in)
        row["output_gap_multiple"] = "%.2f" % gap_out
        if gap >= 1.5:
            row["flag"] = "headline_below_first_party"
            row["notes"] = ("headline is %s at %.3f in / %.3f out; author "
                            "standard tier is %.3f / %.3f (input %.1fx, "
                            "output %.1fx more)"
                            % (cheapest[0], head["input"], head["output"],
                               best_fp[1], best_fp[2], gap_in, gap_out))
        elif zero:
            row["flag"] = "zero_priced_endpoint_present"
        else:
            row["flag"] = "ok"
        rows.append(row)
        if i % 10 == 0:
            print("  %d/%d" % (i, len(targets)))

    exists = os.path.exists(DEST)
    if exists:
        with open(DEST, newline="", encoding="utf-8") as fh:
            if date in {r["date"] for r in csv.DictReader(fh)}:
                sys.exit("%s already has rows for %s. Existing rows are never "
                         "modified." % (DEST, date))
    with open(DEST, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(rows)

    from collections import Counter
    print("\nflags: %s" % dict(Counter(r["flag"] for r in rows)))
    big = sorted([r for r in rows if r["flag"] == "headline_below_first_party"],
                 key=lambda r: -float(r["output_gap_multiple"]))
    print("\nheadline price below the author's own price:")
    for r in big:
        print("  %-34s %-15s headline %-8s author %-8s %sx  (%s)"
              % (r["model_id"], r["weight_class"], r["headline_output"],
                 r["first_party_output"], r["output_gap_multiple"],
                 r["headline_provider"]))
    print("\nwrote %s" % DEST)


if __name__ == "__main__":
    main()
