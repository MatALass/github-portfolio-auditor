# Potential methodology

The base audit answers "how good is this repository today?". The potential audit answers
two other questions:

1. How good can this repository become, for a given role, and at what cost?
2. Which set of repositories shows the widest range of that role's skills, without
   repeating the same subject?

Everything below is configured in `src/portfolio_auditor/potential/policies/potential_v1.yaml`.

## 1. Profile

For each local clone the profiler reads files, dependency manifests, Python imports
(notebooks included) and the README, and produces:

- **skill domains**: a 0..1 strength per domain (BI, SQL, pipeline, ML, decision and
  simulation, statistics, data app, NoSQL, automation, software, game, web). Evidence comes
  from file extensions, dependencies, paths and README keywords. README keywords alone can
  reach at most `keyword_cap` of a domain: a strong domain needs evidence in the code.
  Every strength keeps its evidence list (`repo_profiles.json`).
- **theme**: the subject (esports, football, education, cybersecurity...). Two projects on
  the same subject tell a recruiter the same story, whatever their technique.
- **real-world signals**: keywords (open data, client, production...) and the number of
  concrete figures in the README (60,921 rows, 100 000 kills). A project that reports real
  numbers was run on real data.
- **delivery facts**: tests, CI, visuals or demo link, src layout, notebook-only analysis,
  tracked size, days since last commit, share of commits by the owner.
- **personal data**: tracked CSV files whose header contains at least two personal columns
  (name, email, student id...). Ignored files do not count: only what git tracks can leak.

## 2. Potential score

| Component | Meaning | Default weight |
|---|---|---|
| role relevance | best domain strength x its role weight, plus a little breadth | 30 |
| realness | real data, real question, real stakeholder | 20 |
| substance | log-scaled volume of real work already there | 15 |
| current level | base audit score: a head start is worth something | 15 |
| feasibility | 1 - effort / max effort | 15 |
| recency | fresher context is cheaper to resume | 5 |

Effort is a sum of named items (missing README, tests, CI, visuals, notebook-only, flat
layout, heavy repository, stale context, personal data tracked, plus overrides). The same
items become the first steps of the improvement prompt.

A repository is not eligible when it is excluded by an override, when the owner made less
than `min_owner_commit_share` of its commits, or when its role relevance is too low.

## 3. Diverse selection

Greedy, one slot at a time. The candidate with the highest gain wins:

```
gain = potential x (1 - penalty x max similarity to picked) x (1 + bonus x new core domains)
```

Hard rules: at most `max_per_theme` per subject, at most `max_per_primary_domain` per
primary domain, and the primary domain must matter for the role (`min_primary_role_weight`).
Similarity is the cosine of squared domain vectors, so shared weak signals count less than
each project's strong domains. `diverse_portfolio.json` records every step and every
candidate skipped for diversity, with the reason.

## 4. Overrides

Some facts cannot be read from files: a real client, a project that is a copy of a team
repository, a wrong theme, two repositories that should become one. They go in an
overrides YAML (see `configs/potential_overrides.example.yaml`): `exclude`, `theme`,
`primary_domain`, `realness_bonus`, `merge_into`, `extra_effort`, `note`. Keep the file
outside the repository if it names private projects.

## 5. Limits

- Detection is heuristic. A well-written README helps a project; a bad one hurts it.
- Greedy selection can miss the best combination. With six slots the steps stay easy to
  read and argue with, which matters more here.
- The tool does not know the target companies. Use `realness_bonus` or a note when a
  subject fits a sector you aim for.
