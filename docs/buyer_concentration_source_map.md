# Buyer concentration pillar source map

Drafted 2026-11-04. Nothing collected yet and no collector built. This records
where the data is, what each source can and cannot give, and what is known
structurally as opposed to read from a filing. It is a proposal for the owner
to approve or change before any collection starts, in the same way the credit
pillar was mapped first. See the credit source map in `methodology.md` for the
pattern.

## What the pillar is testing

The thesis: AI infrastructure loses if a few frontier labs dominate compute
buying. So the pillar measures how concentrated each seller's revenue and
backlog is on a small number of AI-lab buyers. A neocloud whose revenue is
three quarters one customer is a different credit and a different business
than one serving fifty, and the thesis turns on which way that goes over time.

The buyers in question are the frontier labs: OpenAI, Anthropic, and arguably
xAI and Meta's internal lab. The sellers are the neoclouds and hyperscalers in
the coverage universe.

## The core difficulty, stated first

The buyers are private. OpenAI and Anthropic do not file, so their spend is
never disclosed from their side. Concentration has to be read from the
**sellers'** filings, and a seller names a customer only when it chooses to or
when accounting rules force it. Two further ambiguities follow:

1. **Pass-through buyers.** Microsoft contracts large amounts of CoreWeave
   capacity, some of it to serve OpenAI. Is that buyer Microsoft or OpenAI?
   The filing says Microsoft. Treating Microsoft as a frontier-lab proxy is a
   judgement, not a disclosure, and must be tagged as one if made at all.
2. **Named versus unnamed.** Most 10-Ks disclose that "one customer was X% of
   revenue" without naming it, or name it only in a risk factor. The percent
   and the name often live in two different places in the same filing.

The honest version of this pillar reports what the filing states, tags any
proxy assumption separately, and never converts an unnamed concentration into
a named one.

## Proposed metrics

Standard scorecard columns. Numeric values only; the counterparty name lives
in `entity` and `notes`, never smuggled into the metric name.

| metric | unit | what it is |
| --- | --- | --- |
| `customer_concentration_top1_pct` | pct | largest single customer as a share of period revenue |
| `customer_concentration_top2_pct` | pct | top two customers combined, where disclosed |
| `customers_over_10pct_count` | count | how many customers each exceeded 10% of revenue, a figure accounting rules often force out |
| `rpo_total_usd_mm` | usd_mm | remaining performance obligations, the contracted backlog |
| `rpo_largest_counterparty_pct` | pct | a named counterparty's share of RPO, where the filing gives it |

`entity` carries the seller and, where named, the counterparty, for example
`CRWV:Microsoft`. Where the filing gives only an unnamed concentration,
`entity` is the seller alone and `notes` records that the customer was not
named. Revenue-period basis (quarter or trailing year) goes in `notes`, since
mixing the two would be the same error the credit pillar made with rates.

## Sellers in scope and what each discloses

From the coverage universe. The neoclouds are the heart of this pillar, for
the same reason they are the heart of the credit pillar: they are small,
single-purpose, and heavily contracted to a few buyers, and they file.

| seller | CIK | likely disclosure | limit |
| --- | --- | --- | --- |
| CoreWeave (CRWV) | 0001769628 | Strong. Customer concentration footnote and risk factors; RPO disclosed. Historically a majority of revenue from a single customer. | The single-customer identity and the pass-through question above. |
| Nebius (NBIS) | 0001513845 | Thin. Foreign private issuer, 20-F and 6-K, less granular concentration detail. | No quarterly US-style concentration footnote. |
| IREN | 0001878848 | Moderate. Shifting from bitcoin to AI cloud; concentration detail is emerging. | Mixed-business revenue makes the AI-lab share hard to isolate. |
| Applied Digital (APLD) | 0001144879 | Moderate to strong. Large contracted leases with named hyperscaler tenants; RPO or contracted-revenue backlog disclosed. | Tenant vs AI-lab distinction; leases are to hyperscalers, not labs directly. |
| Cipher Mining (CIFR) | 0001819989 | Emerging. AI/HPC contracts being signed; concentration detail thin so far. | Still largely bitcoin; AI backlog nascent. |
| TeraWulf (WULF) | 0001083301 | Emerging. HPC hosting contracts with named counterparties announced in 8-Ks. | Small AI revenue base today. |
| Microsoft, Alphabet, Amazon, Meta, Oracle | various | Weak for this pillar. Hyperscalers do not break out AI-lab revenue; Oracle discloses RPO growth and has named large AI contracts in 8-Ks and calls. | Buyer concentration is buried inside segments far too large to isolate. Oracle RPO is the one usable series. |

The read: this pillar is mostly a **neocloud** pillar, led by CoreWeave and
Applied Digital, with Oracle's RPO as the one usable hyperscaler series. The
hyperscalers are in scope but will mostly contribute context, not metrics.

## Sources, in order of preference

1. **10-K and 10-Q concentration footnotes and risk factors**, via the same
   SEC EDGAR access the credit pillar already uses (`scripts/sec_client.py`).
   The revenue-concentration percent is sometimes an XBRL fact and sometimes
   narrative only; expect to read the narrative, not just the instance
   document.
2. **8-Ks announcing large contracts**, for RPO and named counterparties. A
   dated contract announcement is the cleanest named-counterparty evidence the
   pillar will get.
3. **Earnings-call transcripts**, for RPO and concentration colour not yet in
   a filing. Lower in the order because they are commentary, not audited.

All free, all public, all already reachable. No new access or account is
needed, which is the opposite of the credit pillar's TRACE gap.

## What this pillar cannot do, written down before collecting

- It cannot measure OpenAI's or Anthropic's total spend or its distribution
  across providers. Only the sellers' side is visible.
- It cannot cleanly separate a hyperscaler buying for itself from a
  hyperscaler buying to resell to a lab. Any such split is an assumption and
  is tagged as one.
- The XBRL concentration fact, where it exists, is often unnamed. Naming it
  requires the risk factor or an 8-K, and if neither names it the row stays
  unnamed.

## Open questions for the owner

- Whether to treat Microsoft as an OpenAI proxy at all, or to report only what
  filings name and leave the pass-through unquantified.
- Whether xAI and Meta's internal lab count as frontier-lab buyers for this
  pillar, or only the merchant labs OpenAI and Anthropic.
- Whether to collect quarterly, matching filing cadence, or only after each
  earnings season, matching the credit pillar's rhythm.
- Whether RPO belongs in this pillar or deserves splitting out, given it is a
  backlog measure that also speaks to the credit pillar.
