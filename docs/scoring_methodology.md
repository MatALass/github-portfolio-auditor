# Scoring Methodology

## Purpose

The auditor separates three different layers that should not be confused:

1. **Score**: measured repository quality from observable evidence.
2. **Portfolio decision**: recommendation for how the repository should be used in a portfolio.
3. **Ranking**: ordering of repositories for portfolio curation.

This separation is intentional. A repository can have a decent technical score and still be a weak portfolio candidate because of redundancy, unclear positioning, or poor delivery readiness.

## Layer 1 — Repository score

The final score is out of 100 and is computed from weighted dimensions:

- Architecture & Structure: 20
- Documentation & Delivery: 20
- Testing & Reliability: 15
- Technical Depth: 15
- Portfolio Relevance & Storytelling: 20
- Maintainability & Cleanliness: 10

The score is evidence-based and should always be explainable from repository facts:

- file presence
- folder structure
- workflow files
- tests
- documentation sections
- packaging configuration
- repository hygiene

### What the score is allowed to represent

The score measures **repository quality as delivered**.
It is not supposed to directly encode portfolio strategy such as:

- whether two repositories overlap too much
- whether one repository is the best representative of a cluster
- whether a weak repository should remain public as an archive

Those decisions belong to downstream layers.

## Layer 2 — Portfolio decision

Portfolio decision is a discrete recommendation derived from score + delivery blockers + narrative signals.

The current decision set is:

- `FEATURE_NOW`
- `KEEP_AND_IMPROVE`
- `MERGE_OR_REPOSITION`
- `ARCHIVE_PUBLIC`
- `MAKE_PRIVATE`

### Methodological intent

- `FEATURE_NOW` means the repository is already safe to showcase.
- `KEEP_AND_IMPROVE` means the repository is worth keeping visible, but should not be treated as finished.
- `MERGE_OR_REPOSITION` means the repository has some value, but is not differentiated or complete enough on its own.
- `ARCHIVE_PUBLIC` means the repository is below feature quality but still has archive or narrative value.
- `MAKE_PRIVATE` means the repository is currently more harmful than helpful.

### Important clarification

`ARCHIVE_PUBLIC` should be reachable only for repositories that are weak **but not actively harmful**:

- README exists
- no severe hygiene failure such as committed virtualenv or committed `__pycache__`
- some narrative value still exists (description, architecture/results section, screenshots, or homepage)

Without those signals, the safer recommendation is `MAKE_PRIVATE`.

## Layer 3 — Ranking

Ranking is not a second score.
It is a **portfolio ordering strategy**.

The ranking should be defensible and readable:

1. decision tier first
2. repository score second
3. confidence as tie-breaker
4. redundancy penalty applied because overlap is external to the raw repository score

### Why this is more defensible

A previous ranking formula can easily become hard to justify when it adds together:

- score
- decision bonus
- confidence bonus
- blocker penalty
- redundancy penalty

That mixes different concepts into one arithmetic number and creates hidden double counting.

The current recommendation is:

- keep score as the main quantitative signal
- use decision tier as an explicit ordering layer
- keep confidence as a tie-breaker, not as a large additive score boost
- apply redundancy as a targeted portfolio penalty because it reflects cross-repository overlap

## Penalties

Typical penalties include:

- committed build artifacts
- missing README
- missing tests
- missing CI
- weak install/usage documentation
- poor delivery cleanliness

Penalties should remain tied to observable evidence and not be used to encode subjective taste.

## Confidence

Confidence measures how reliable the audit evidence is, not how good the repository is.

Examples that increase confidence:

- local clone available
- multiple scanners fired
- README detected
- tests detected
- CI detected
- sufficient evidence items collected

Confidence should therefore influence ranking only lightly.
It should not dominate the ordering of repositories that already have a strong score difference.

## Current limitations

The methodology is still deterministic and intentionally simple.
That makes it explainable, but it also creates limits:

- evidence is mostly structural, not semantic
- code quality is inferred from delivery signals, not deep code understanding
- portfolio storytelling is approximated through metadata and documentation signals
- redundancy detection is heuristic, not embedding-based
- score thresholds remain normative rather than empirically calibrated

## Recommended future improvements

1. Calibrate thresholds on a labeled benchmark set of repositories.
2. Separate raw quality score and showcase readiness score explicitly.
3. Make redundancy category-aware with stronger representative selection logic.
4. Introduce light longitudinal stability signals once historical snapshots accumulate.
5. Keep the method deterministic unless a clearly better and auditable alternative exists.
