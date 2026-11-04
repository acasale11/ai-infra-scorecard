"""Rebuild the SQLite database from the CSVs.

The CSVs under data/ are the canonical record. This database is derived,
disposable and gitignored. It exists so the monthly brief can run queries
instead of parsing five files by hand.

The script drops and rebuilds from scratch every time. Nothing is ever
written back to the CSVs, and nothing in the database survives that the CSVs
do not already hold. If the two disagree, the CSVs are right.

Usage:
    python scripts/build_db.py
    python scripts/build_db.py --db data/research.db
"""

import argparse
import csv
import glob
import os
import sqlite3

SCORECARD_GLOB = "data/scorecard/*.csv"
TABLES = {
    "claims": "data/claims_ledger.csv",
    "coverage": "data/coverage_universe.csv",
    "model_classification": "data/model_classification.csv",
    "price_verification": "data/price_verification.csv",
    "price_bases": "data/price_bases.csv",
    "elasticity_prices": "data/elasticity_prices.csv",
    "credit_unmapped": "data/credit_unmapped.csv",
}
DEFAULT_DB = "data/research.db"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rdr = csv.DictReader(fh)
        return rdr.fieldnames or [], list(rdr)


def create_from_header(con, table, fields, real_columns=()):
    cols = ", ".join(
        '"%s" %s' % (f, "REAL" if f in real_columns else "TEXT") for f in fields)
    con.execute('DROP TABLE IF EXISTS "%s"' % table)
    con.execute('CREATE TABLE "%s" (%s)' % (table, cols))


def insert(con, table, fields, rows):
    if not rows:
        return 0
    sql = 'INSERT INTO "%s" (%s) VALUES (%s)' % (
        table,
        ", ".join('"%s"' % f for f in fields),
        ", ".join("?" for _ in fields),
    )
    con.executemany(sql, [[r.get(f) for f in fields] for r in rows])
    return len(rows)


def build_scorecard(con):
    """One table for all five pillar files, with a pillar column."""
    paths = sorted(glob.glob(SCORECARD_GLOB))
    if not paths:
        return 0, []

    headers = {}
    for p in paths:
        fields, _ = read_csv(p)
        headers[os.path.basename(p)] = tuple(fields)
    distinct = set(headers.values())
    if len(distinct) > 1:
        raise SystemExit(
            "scorecard files disagree on columns, refusing to build:\n  " +
            "\n  ".join("%s: %s" % (k, list(v)) for k, v in headers.items()))

    fields = list(next(iter(distinct)))
    create_from_header(con, "scorecard", ["pillar"] + fields,
                       real_columns=("value",))

    total, per_pillar = 0, []
    for p in paths:
        pillar = os.path.splitext(os.path.basename(p))[0]
        _, rows = read_csv(p)
        for r in rows:
            r["pillar"] = pillar
        n = insert(con, "scorecard", ["pillar"] + fields, rows)
        per_pillar.append((pillar, n))
        total += n
    return total, per_pillar


def build_views(con):
    con.execute("DROP VIEW IF EXISTS claims_open")
    con.execute("""
        CREATE VIEW claims_open AS
        SELECT claim_id, pillar, claim_type, horizon_date, claim_text
        FROM claims WHERE status = 'pending' ORDER BY horizon_date
    """)
    con.execute("DROP VIEW IF EXISTS latest_by_metric")
    con.execute("""
        CREATE VIEW latest_by_metric AS
        SELECT pillar, entity, entity_class, metric, unit, value, date
        FROM scorecard s
        WHERE date = (SELECT MAX(date) FROM scorecard x
                      WHERE x.metric = s.metric AND x.entity IS s.entity)
    """)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    args = ap.parse_args()

    if os.path.exists(args.db):
        os.remove(args.db)
    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)

    con = sqlite3.connect(args.db)
    try:
        summary = []
        for table, path in TABLES.items():
            if not os.path.exists(path):
                continue
            fields, rows = read_csv(path)
            create_from_header(con, table, fields)
            summary.append((table, insert(con, table, fields, rows)))

        total, per_pillar = build_scorecard(con)
        build_views(con)
        con.commit()
    finally:
        con.close()

    print("rebuilt %s" % args.db)
    for table, n in summary:
        print("  %-12s %5d rows" % (table, n))
    print("  %-12s %5d rows" % ("scorecard", total))
    for pillar, n in per_pillar:
        print("      %-22s %5d" % (pillar, n))


if __name__ == "__main__":
    main()
