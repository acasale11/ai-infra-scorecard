# Routing experiment

## Question

Does an open-weight model with a router that escalates hard requests to a
frontier model match a frontier model used alone, at meaningfully lower cost?

This feeds the `elasticity` and `open_source_share` pillars. If routing works,
the price a buyer actually pays per unit of useful work falls much faster than
headline frontier token prices, and open-weight share of served tokens rises
faster than it looks.

## Design

Not yet built. Before any code, the following need to be written down and
committed, in this order, so the result cannot be fitted after the fact:

1. Task set. Fixed, public, and sized so one run is affordable to repeat. Record
   the exact set and its source.
2. Grading. How a response is scored, by what, and who or what breaks ties.
   Committed before the first run.
3. Routing rule. The escalation trigger, stated precisely enough to reimplement
   from the description alone.
4. Cost accounting. Tokens in and out at each tier, priced at the published
   rates on the run date. Rates get snapshotted into the results file.
5. Success criterion. The quality threshold and the cost saving that together
   count as a win, written before the first run.

## Results

Each run writes a dated CSV here. Runs are never overwritten. A rerun on a new
date is a new file, and the comparison between them is itself a data point,
since model versions and prices move underneath the experiment.
