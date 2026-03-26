# GitHub Portfolio Auditor

A deterministic-first repository auditing system that analyzes GitHub repositories for portfolio quality, technical maturity, delivery cleanliness, and hiring relevance.

## Objectives

This project helps you:

- collect metadata from GitHub repositories
- clone repositories locally for deep inspection
- scan structure, documentation, testing, CI, packaging, and delivery hygiene
- compute explainable portfolio scores
- generate deterministic reviews and optional LLM-based qualitative summaries
- rank repositories to decide which ones to feature, improve, merge, archive, or make private
- export data to JSON / CSV
- visualize results in a Streamlit dashboard

## Product philosophy

The system is intentionally built around these principles:

1. **Deterministic first**
   - scores should come from explicit rules, not subjective prompts

2. **Evidence based**
   - every issue, penalty, and recommendation should be traceable to observable facts

3. **LLM last**
   - language models are optional and only used after structured audit results exist

4. **Portfolio oriented**
   - the final output is not just “code quality”; it is “portfolio decision quality”

## Current state

This repository is a **V2 production scaffold**:
- project structure is complete
- core domain models are implemented
- a working CLI is provided
- key scanners and a scoring engine are included
- export and dashboard paths are ready
- several modules are intentionally lightweight and designed for iterative extension

This is the correct base to continue implementation in a robust way.

## Architecture overview

```text
collect -> fetch -> scan -> score -> review -> rank -> export -> dashboard
```

### Main modules

- `collectors/github/`: GitHub API collection
- `fetchers/`: local clone / repo cache management
- `scanners/`: repository inspection
- `scoring/`: explainable scoring engine
- `reviewing/`: deterministic and optional LLM review
- `ranking/`: prioritization and portfolio decisions
- `exports/`: JSON / CSV / site exports
- `dashboard/`: Streamlit visualization

## Quick start

### 1. Create environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 2. Install the project

```bash
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

### 3. Configure environment

Copy `.env.example` to `.env` and set:

```env
GITHUB_TOKEN=your_github_token
GITHUB_OWNER=MatALass
OPENAI_API_KEY=
```

`OPENAI_API_KEY` is optional. The project works without it.

### 4. Run a metadata collection

```bash
portfolio-auditor collect --owner MatALass
```

### 5. Clone repositories locally

```bash
portfolio-auditor fetch --owner MatALass
```

### 6. Scan local repositories

```bash
portfolio-auditor scan --owner MatALass
```

### 7. Score repositories

```bash
portfolio-auditor score
```

### 8. Generate deterministic reviews

```bash
portfolio-auditor review
```

### 9. Rank repositories

```bash
portfolio-auditor rank
```

### 10. Export outputs

```bash
portfolio-auditor export --format json --format csv
```

### 11. Run dashboard

```bash
streamlit run dashboard/app.py
```

## Expected outputs

```text
data/
├── raw/
│   ├── github/
│   │   └── repos_raw.json
│   └── clones/
├── interim/
│   ├── scans/
│   ├── scores/
│   └── reviews/
└── processed/
    ├── repos_master_table.csv
    ├── repos_site_data.json
    ├── portfolio_shortlist.json
    └── ranking.json
```

## Scoring model

The default score is out of 100:

- Architecture & Structure: 20
- Documentation & Delivery: 20
- Testing & Reliability: 15
- Technical Depth: 15
- Portfolio Relevance & Storytelling: 20
- Maintainability & Cleanliness: 10

## Portfolio decisions

The engine classifies repositories into:

- `FEATURE_NOW`
- `KEEP_AND_IMPROVE`
- `MERGE_OR_REPOSITION`
- `ARCHIVE_PUBLIC`
- `MAKE_PRIVATE`

## Example workflow

```bash
portfolio-auditor full-run --owner MatALass --skip-llm
```

## Roadmap

### High priority
- extend scanner coverage for frontend / data / notebook / security signals
- enrich GitHub collector with README and workflow metadata
- add duplicate-detection heuristics based on repo purpose and structure
- add SQLite export for richer querying
- add optional OpenAI review summarization

### Medium priority
- add historical snapshots
- compare score evolution over time
- add “top actions per repo” planning mode
- support organizations in addition to user scope
- add site API layer for Next.js front-end

### Longer term
- deploy a public dashboard
- add recruiter-view and engineering-view modes
- add portfolio curation workflows

## Recommended delivery standards

This project is intended to be maintained as a serious software/data engineering repository:
- keep generated artifacts out of version control
- keep scoring rules explicit and documented
- prefer typed, modular, testable code
- version outputs and methodology separately

## License

MIT
