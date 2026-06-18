# CONTEXT: GitHub Portfolio Auditor

## Why this project?

This project was born from a concrete need during my apprenticeship search in March 2026:
- I wanted to **build a portfolio** to showcase my projects.
- But I didn't know **which projects to highlight**, nor **which ones to improve or archive**.
- No existing solution allowed me to **audit a GitHub portfolio in an objective and reproducible way**.

The goal was to create a tool that:
1. Analyzes each repository (structure, documentation, tests, CI, etc.).
2. Scores projects based on configurable criteria.
3. Ranks repositories by relevance for a portfolio.
4. Recommends concrete actions (improve, merge, archive, etc.).

---

## Origin and context

- **Timeframe**: Started in mid-March 2026, developed over **about two intensive weeks** (roughly 4 hours per day).
- **Motivation**:
  - **Professional**: Prepare for my apprenticeship search by having a coherent and impactful portfolio.
  - **Personal**: I am meticulous and like things to be well-structured and clean.
- **Target audience**: Primarily myself (for now), as the tool uses a confidential GitHub API key.
- **Usage**:
  - I applied this tool to **all my projects** to identify inconsistencies, redundancies, and areas for improvement.
  - Result: I was able to **prioritize which projects to improve** and **archive or delete those that didn't add value**.

---

## Key learnings

- **Software architecture**:
  - Design of a **modular system** (collectors, scanners, scorers, rankers).
  - **Policy-driven approach** (scoring rules externalized in YAML files).
- **Advanced Python development**:
  - Extensive use of `dataclasses`, `pydantic`, and `Protocol` for typing interfaces.
  - Dependency and error management in a data pipeline.
- **Data engineering**:
  - Building a complete pipeline: collection → processing → scoring → visualization.
- **Testing**:
  - Implementation of unit tests, integration tests, and **golden tests** (snapshots) to ensure score stability.
- **GitHub API**:
  - Managing API calls, rate limits, and network errors.
- **Streamlit**:
  - Creating an interactive interface to explore results.

---
## Key technical decisions

- **Deterministic approach**:
  - Deliberate choice **not to use LLMs** to ensure reproducibility, avoid costs, and limit environmental impact.
  - The scoring model based on rules was **the most complex to design**: it required many iterations to balance relevance and simplicity.

- **External configuration**:
  - Scoring weights and optimization rules are **modifiable via YAML files**, without touching the code.

- **Abandoning LLM analysis**:
  - Initially considered for generating automatic reviews, this feature was discarded due to:
    - **Costs** (paid API calls).
    - **Non-determinism** (variable results).
    - **Environmental impact** (unnecessary calls).

---
## Impact and results

- **On my portfolio**:
  - Identification of **several redundant projects** to merge or archive.
  - **Clear prioritization** of projects to improve (e.g., add tests, improve documentation).
  - Time saved: **a few hours** to audit all my repositories (compared to days manually).

- **On personal development**:
  - Better understanding of **open-source project quality criteria**.
  - Ability to **objectively evaluate** my own work.

---
## Evolution and roadmap

- **Future improvements**:
  - Add **business rules** to evaluate the consistency between a project's business needs and its implementation.
  - Integrate **additional metrics** (e.g., cyclomatic complexity, code coverage).
  - **Open-source the project** (if GitHub key management can be secured).

- **Abandoned features**:
  - LLM analysis (see "Key technical decisions" section).

---
## Why this project matters to me

This is the project where I **learned the most about software architecture and data engineering**, while solving a **concrete and personal problem**.
Unlike my other repositories (often school exercises or tests), this one is:
- **100% autonomous** (no critical external dependencies).
- **Tested and reliable** (72% coverage, golden tests).
- **Used in production** (even if only by me for now).
