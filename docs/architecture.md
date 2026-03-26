# Architecture

## Pipeline

1. Collect repository metadata from GitHub
2. Fetch repositories locally
3. Scan repository contents
4. Score repositories using explicit rules
5. Generate deterministic reviews
6. Rank repositories for portfolio decisions
7. Export data for dashboard / site use

## Core design principles

- deterministic-first
- evidence-based
- modular scanners
- typed models
- transparent scoring

## Main boundaries

### Collectors
External API integration and metadata normalization.

### Fetchers
Local repository clone / update orchestration.

### Scanners
Facts extraction layer. No business decisions here.

### Scoring
Transforms raw scan facts into explainable scores.

### Reviewing
Transforms scores and issues into human-readable critiques.

### Ranking
Converts scores into prioritization and portfolio decisions.

### Exports / site
Presentation layer only.
