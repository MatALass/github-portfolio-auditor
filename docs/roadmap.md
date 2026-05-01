# Roadmap

## Phase 1 — Foundation ✓
- GitHub collector with rate-limit fallback and normalized snapshots
- Clone manager (HTTPS / SSH)
- Domain models (Pydantic)
- CLI (`portfolio-auditor full-run`)

## Phase 2 — Analysis ✓
- Modular scanners: structure, documentation, testing, CI, cleanliness
- Policy-driven scoring engine (YAML weights)
- Deterministic reviewer (no LLM dependency)

## Phase 3 — Dashboard ✓
- Portfolio ranking and shortlist
- Streamlit dashboard (overview, repo table, portfolio view, optimizer, redundancy)
- ROI-based action optimizer
- Historical comparison (snapshot diff)

## Phase 4 — In progress

### Short term
- [ ] SQLite exporter — enable ad-hoc SQL queries on audit artifacts
- [ ] Empirical calibration of effort_units in action_impact_rules.yaml
- [ ] Improve redundancy detection (beyond TF-IDF: language + structure signals)
- [ ] Increase test coverage to 80% (currently targeting 72%)

### Medium term
- [ ] Optional LLM review layer (additive, not a replacement for deterministic scoring)
- [ ] Improved site export (richer JSON payload for portfolio website integration)
- [ ] Multi-owner support in the dashboard (compare portfolios across accounts)

### Long term
- [ ] Public scoring benchmark against a curated set of reference repositories
- [ ] Scoring policy versioning (track score changes across policy updates)