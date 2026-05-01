# GitHub Portfolio Auditor

A deterministic, policy-driven system to audit, score, and optimize a GitHub portfolio.

---

## 1. Context

When reviewing GitHub profiles, one recurring issue appears: there is no objective, structured way to evaluate the quality of a portfolio.

Most repositories:
- vary widely in quality
- lack clear positioning
- overlap in purpose
- fail to communicate technical depth

As a result, even strong candidates often present portfolios that underperform.

This project was built to solve that problem with a deterministic and explainable approach.

---

## 2. What this project does

GitHub Portfolio Auditor is a system that:

1. Collects repositories from GitHub
2. Scans each repository (structure, documentation, testing, CI, signals)
3. Scores them using a configurable policy
4. Generates deterministic reviews (no LLM dependency)
5. Ranks repositories for portfolio visibility
6. Recommends which repositories to:
   - feature
   - improve
   - merge
   - archive
   - make private
7. Provides a dashboard to explore and optimize decisions

---

## 3. Example workflow

1. Run an audit on a GitHub account
2. Get a scored and ranked list of repositories
3. Identify weak or redundant projects
4. Apply prioritized improvements
5. Re-run the audit and measure impact

---

## 4. Screenshots

### Portfolio overview
![Overview](assets/screenshots/overview.png)

### Repository ranking and filtering
![Repository Table](assets/screenshots/repository_table.png)

### Portfolio decision engine
![Portfolio Selection](assets/screenshots/portfolio_selection.png)

### Optimization engine (ROI-based actions)
![Optimizer](assets/screenshots/optimizer_focus.png)

---

## 5. Architecture

The system is structured as follows:

```
src/
  portfolio_auditor/
    collectors/        GitHub API
    scanners/          repository analysis
    scoring/           policy-driven scoring
    reviewing/         deterministic review
    ranking/           ranking and selection
    dashboard/         Streamlit UI
    models/            domain models

configs/
  scoring.yaml               score dimension weights
  action_impact_rules.yaml   optimizer ROI rules (effort, category per action)
  portfolio_rules.yaml       portfolio decision thresholds

tests/
  unit/
  integration/
  golden/                    snapshot tests
  smoke/

docs/
  scoring_methodology.md
  portfolio_decision_rules.md
```

---

## 6. Key design principles

**Deterministic first**
All outputs are reproducible and explainable.

**Policy-driven**
Scoring rules and optimizer effort estimates are externalized in YAML — no code change required to tune them.

**Separation of concerns**
Scanning, scoring, reviewing and ranking are distinct layers.

**Portfolio-oriented**
This is not a generic repo scorer, but a portfolio optimization tool.

---

## 7. Local setup

### Prerequisites

- Python 3.11 or 3.12
- Git

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/github-portfolio-auditor.git
cd github-portfolio-auditor

# 2. Create and activate a virtual environment
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# 3. Install the package and dev dependencies
pip install -e .[dev]

# 4. Create a .env file with your GitHub token
cp .env.example .env
# Then edit .env and set GITHUB_TOKEN=your_token_here
```

---

## 8. Configuration

The `.env` file supports the following variables:

```env
GITHUB_TOKEN=your_token_here          # required for private repos and higher rate limits
GITHUB_OWNER=your_github_username     # optional — sets a default owner for CLI and dashboard
GITHUB_EXCLUDED_REPO_NAMES=repo1,repo2  # optional — comma-separated repos to exclude
WORKSPACE_DIR=data                    # optional — root of the data directory tree
```

Scoring weights are in `configs/scoring.yaml`.
Optimizer action rules (effort estimates, categories) are in `configs/action_impact_rules.yaml`.

---

## 9. Usage

### Run a full audit

```bash
portfolio-auditor full-run --owner <github-username>
```

Use `--refresh-clones` to force re-cloning even if local clones already exist.

### Launch the dashboard

```bash
# Linux / macOS
PYTHONPATH=src streamlit run src/portfolio_auditor/dashboard/app.py

# Windows (PowerShell)
$env:PYTHONPATH = "src"
streamlit run src/portfolio_auditor/dashboard/app.py
```

The dashboard reads from `data/processed/<owner>/` — run the audit first.

---

## 10. Tests

```bash
# Full test suite with coverage
pytest --cov=portfolio_auditor --cov-report=term-missing --cov-fail-under=72

# By category
pytest tests/unit -q
pytest tests/golden -q
pytest tests/smoke -q
```

---

## 11. Code quality

```bash
# Formatting check
ruff format --check .

# Lint
ruff check .

# Auto-fix lint issues
ruff check --fix .
```

---

## 12. Impact

This project enables:

- objective evaluation of a GitHub portfolio
- structured prioritization of improvements
- reduction of redundancy between projects
- stronger technical signaling
- measurable portfolio progression

It transforms a portfolio from a collection of repositories into a curated, intentional system.

---

## 13. Limitations

- heuristic-based scoring
- no empirical calibration yet
- redundancy detection is approximate
- dashboard depends on generated artifacts

---

## 14. Roadmap

See [docs/roadmap.md](docs/roadmap.md).

---

## 15. Author

Mathieu
Data / BI / Analytics Engineering