from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_score import RepoScore

_GENERIC_NAME_TOKENS = {
    "app",
    "application",
    "code",
    "dashboard",
    "demo",
    "github",
    "portfolio",
    "project",
    "repo",
    "repository",
    "site",
    "tool",
    "website",
}

# Common stopwords to strip before TF-IDF vectorisation
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "that", "this", "it", "its", "as", "i", "my", "your", "our", "their",
    "using", "based", "built", "use", "used", "uses", "simple", "small",
    "new", "old", "python", "js", "ts",
}


# ---------------------------------------------------------------------------
# Data classes (unchanged public contract)
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class OverlapPair:
    repo_full_name_a: str
    repo_full_name_b: str
    overlap_score: float
    severity: str
    shared_name_tokens: tuple[str, ...]
    shared_topics: tuple[str, ...]
    same_primary_language: bool
    description_similarity: float
    reasons: tuple[str, ...]

    def touches(self, repo_full_name: str) -> bool:
        return repo_full_name in {self.repo_full_name_a, self.repo_full_name_b}

    def other(self, repo_full_name: str) -> str:
        if repo_full_name == self.repo_full_name_a:
            return self.repo_full_name_b
        if repo_full_name == self.repo_full_name_b:
            return self.repo_full_name_a
        raise ValueError(f"Repository {repo_full_name!r} is not part of this pair")

    def to_dict(self) -> dict:
        return {
            "repo_full_name_a": self.repo_full_name_a,
            "repo_full_name_b": self.repo_full_name_b,
            "overlap_score": self.overlap_score,
            "severity": self.severity,
            "shared_name_tokens": list(self.shared_name_tokens),
            "shared_topics": list(self.shared_topics),
            "same_primary_language": self.same_primary_language,
            "description_similarity": self.description_similarity,
            "reasons": list(self.reasons),
        }


@dataclass(slots=True, frozen=True)
class OverlapCluster:
    cluster_id: str
    representative_repo_full_name: str
    repo_full_names: tuple[str, ...]
    overlap_candidate_count: int
    average_overlap_score: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "representative_repo_full_name": self.representative_repo_full_name,
            "repo_full_names": list(self.repo_full_names),
            "overlap_candidate_count": self.overlap_candidate_count,
            "average_overlap_score": self.average_overlap_score,
            "reasons": list(self.reasons),
        }


@dataclass(slots=True, frozen=True)
class RepoOverlapStatus:
    repo_full_name: str
    cluster_id: str | None
    representative_repo_full_name: str | None
    overlap_candidate_count: int
    strongest_overlap_score: float
    redundancy_status: str
    redundancy_reason: str | None

    def to_dict(self) -> dict:
        return {
            "repo_full_name": self.repo_full_name,
            "cluster_id": self.cluster_id,
            "representative_repo_full_name": self.representative_repo_full_name,
            "overlap_candidate_count": self.overlap_candidate_count,
            "strongest_overlap_score": self.strongest_overlap_score,
            "redundancy_status": self.redundancy_status,
            "redundancy_reason": self.redundancy_reason,
        }


@dataclass(slots=True, frozen=True)
class RedundancyAnalysis:
    overlap_pairs: list[OverlapPair]
    overlap_clusters: list[OverlapCluster]
    repo_statuses: dict[str, RepoOverlapStatus]

    def status_for(self, repo_full_name: str) -> RepoOverlapStatus:
        status = self.repo_statuses.get(repo_full_name)
        if status is None:
            return RepoOverlapStatus(
                repo_full_name=repo_full_name,
                cluster_id=None,
                representative_repo_full_name=None,
                overlap_candidate_count=0,
                strongest_overlap_score=0.0,
                redundancy_status="UNIQUE",
                redundancy_reason=None,
            )
        return status

    def to_dict(self) -> dict:
        return {
            "overlap_pairs": [pair.to_dict() for pair in self.overlap_pairs],
            "overlap_clusters": [cluster.to_dict() for cluster in self.overlap_clusters],
            "repo_statuses": {
                key: value.to_dict() for key, value in sorted(self.repo_statuses.items())
            },
        }


# ---------------------------------------------------------------------------
# TF-IDF cosine similarity helpers
# ---------------------------------------------------------------------------


def _tokenise_text(text: str) -> list[str]:
    """Lower-case word tokens, strip stopwords, keep tokens of length >= 3."""
    return [
        token
        for token in re.split(r"[^a-z0-9]+", text.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    ]


def _tfidf_vectors(
    corpus: list[str],
) -> list[dict[str, float]]:
    """
    Compute TF-IDF vectors for a corpus of documents.

    Returns one dict per document mapping token → tfidf weight.
    Falls back to an empty dict for empty documents.
    """
    n_docs = len(corpus)
    tokenised = [_tokenise_text(doc) for doc in corpus]

    # Document frequency: how many docs contain each token
    df: Counter[str] = Counter()
    for tokens in tokenised:
        df.update(set(tokens))

    vectors: list[dict[str, float]] = []
    for tokens in tokenised:
        if not tokens:
            vectors.append({})
            continue
        tf = Counter(tokens)
        total = len(tokens)
        vec: dict[str, float] = {}
        for token, count in tf.items():
            tf_val = count / total
            idf_val = math.log((1 + n_docs) / (1 + df[token])) + 1.0
            vec[token] = tf_val * idf_val
        # L2-normalise
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm > 0:
            vec = {k: v / norm for k, v in vec.items()}
        vectors.append(vec)

    return vectors


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    shared = set(vec_a.keys()) & set(vec_b.keys())
    return round(sum(vec_a[t] * vec_b[t] for t in shared), 4)


class _DescriptionSimilarityIndex:
    """
    Pre-computes TF-IDF vectors for all repo descriptions so that pairwise
    cosine similarity can be retrieved in O(vocab) instead of rebuilding the
    corpus each time.
    """

    def __init__(self, repos: list[RepoMetadata]) -> None:
        self._full_names: list[str] = [r.full_name for r in repos]
        descriptions = [r.description or "" for r in repos]
        vectors = _tfidf_vectors(descriptions)
        self._vectors: dict[str, dict[str, float]] = dict(zip(self._full_names, vectors))

    def cosine(self, full_name_a: str, full_name_b: str) -> float:
        return _cosine_similarity(
            self._vectors.get(full_name_a, {}),
            self._vectors.get(full_name_b, {}),
        )


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------


class RedundancyDetector:
    """
    Deterministic repository overlap detector — v2.

    Improvements over v1:
    - Description similarity now uses **TF-IDF cosine similarity** in addition
      to ``SequenceMatcher``. The cosine score captures semantic overlap even
      when descriptions are worded differently (e.g. "data pipeline" vs
      "ETL automation"), while SequenceMatcher catches near-exact rephrasing.
      The final description score is the *max* of the two, so either signal can
      flag the pair.
    - README/topic text is included in the TF-IDF corpus when descriptions are
      sparse (< 10 tokens), using topic tags as a fallback signal.
    """

    high_threshold: float = 0.72
    medium_threshold: float = 0.58
    cluster_threshold: float = 0.58

    def analyze(
        self,
        *,
        repos: list[RepoMetadata],
        scores: list[RepoScore],
        reviews: list[RepoReview],
    ) -> RedundancyAnalysis:
        repo_index = {repo.full_name: repo for repo in repos}
        score_index = {score.repo_full_name: score for score in scores}
        review_index = {review.repo_full_name: review for review in reviews}

        full_names = sorted(set(repo_index) & set(score_index) & set(review_index))

        # Build TF-IDF index once across the whole corpus for richer descriptions
        desc_index = _DescriptionSimilarityIndex(
            [repo_index[fn] for fn in full_names]
        )

        pairs: list[OverlapPair] = []
        for left_index, left_name in enumerate(full_names):
            for right_name in full_names[left_index + 1 :]:
                pair = self._build_pair(
                    left=repo_index[left_name],
                    right=repo_index[right_name],
                    desc_index=desc_index,
                )
                if pair is not None:
                    pairs.append(pair)

        pairs.sort(
            key=lambda item: (
                -item.overlap_score,
                item.repo_full_name_a.lower(),
                item.repo_full_name_b.lower(),
            )
        )

        clusters = self._build_clusters(
            pairs=pairs,
            repo_index=repo_index,
            score_index=score_index,
            review_index=review_index,
        )
        statuses = self._build_repo_statuses(clusters=clusters, pairs=pairs)

        return RedundancyAnalysis(
            overlap_pairs=pairs,
            overlap_clusters=clusters,
            repo_statuses=statuses,
        )

    def _build_pair(
        self,
        *,
        left: RepoMetadata,
        right: RepoMetadata,
        desc_index: _DescriptionSimilarityIndex,
    ) -> OverlapPair | None:
        left_name_tokens = _tokenize_name(left.name)
        right_name_tokens = _tokenize_name(right.name)
        shared_name_tokens = tuple(sorted(left_name_tokens & right_name_tokens))
        name_token_score = _jaccard(left_name_tokens, right_name_tokens)
        name_similarity = _sequence_similarity(left.name, right.name)

        left_topics = set(left.topics.items)
        right_topics = set(right.topics.items)
        shared_topics = tuple(sorted(left_topics & right_topics))
        topic_score = _jaccard(left_topics, right_topics)

        # v2: use max(SequenceMatcher, TF-IDF cosine) for description similarity
        seq_sim = _sequence_similarity(left.description, right.description)
        cosine_sim = desc_index.cosine(left.full_name, right.full_name)
        description_similarity = max(seq_sim, cosine_sim)

        left_language = left.language or left.language_stats.primary_language
        right_language = right.language or right.language_stats.primary_language
        same_primary_language = bool(
            left_language and right_language and left_language == right_language
        )

        overlap_score = (
            max(name_token_score, name_similarity) * 0.40
            + topic_score * 0.25
            + description_similarity * 0.20
            + (0.15 if same_primary_language else 0.0)
        )
        overlap_score = round(min(1.0, overlap_score), 4)

        if overlap_score < self.medium_threshold:
            return None

        reasons: list[str] = []
        if shared_name_tokens:
            reasons.append(f"Shared repo naming tokens: {', '.join(shared_name_tokens)}")
        elif name_similarity >= 0.78:
            reasons.append("Repository names are highly similar")

        if shared_topics:
            reasons.append(f"Shared portfolio topics: {', '.join(shared_topics)}")
        if cosine_sim >= 0.65:
            reasons.append(
                f"Descriptions are semantically similar (TF-IDF cosine {cosine_sim:.2f})"
            )
        elif description_similarity >= 0.72:
            reasons.append("Descriptions suggest very similar project positioning")
        if same_primary_language:
            reasons.append(f"Same primary language: {left_language}")

        severity = "high" if overlap_score >= self.high_threshold else "medium"
        if not reasons:
            reasons.append("Technical and naming signals indicate significant overlap")

        return OverlapPair(
            repo_full_name_a=left.full_name,
            repo_full_name_b=right.full_name,
            overlap_score=overlap_score,
            severity=severity,
            shared_name_tokens=shared_name_tokens,
            shared_topics=shared_topics,
            same_primary_language=same_primary_language,
            description_similarity=round(description_similarity, 4),
            reasons=tuple(reasons),
        )

    def _build_clusters(
        self,
        *,
        pairs: list[OverlapPair],
        repo_index: dict[str, RepoMetadata],
        score_index: dict[str, RepoScore],
        review_index: dict[str, RepoReview],
    ) -> list[OverlapCluster]:
        relevant_pairs = [pair for pair in pairs if pair.overlap_score >= self.cluster_threshold]
        if not relevant_pairs:
            return []

        parent: dict[str, str] = {}

        def find(item: str) -> str:
            parent.setdefault(item, item)
            if parent[item] != item:
                parent[item] = find(parent[item])
            return parent[item]

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        for pair in relevant_pairs:
            union(pair.repo_full_name_a, pair.repo_full_name_b)

        groups: dict[str, list[str]] = {}
        for name in parent:
            groups.setdefault(find(name), []).append(name)

        clusters: list[OverlapCluster] = []
        for index, repo_names in enumerate(
            sorted(groups.values(), key=lambda items: sorted(items)[0]), start=1
        ):
            cluster_repo_names = tuple(sorted(repo_names))
            cluster_pairs = [
                pair
                for pair in relevant_pairs
                if pair.repo_full_name_a in cluster_repo_names
                and pair.repo_full_name_b in cluster_repo_names
            ]
            representative = max(
                cluster_repo_names,
                key=lambda full_name: self._representative_value(
                    repo=repo_index[full_name],
                    score=score_index[full_name],
                    review=review_index[full_name],
                ),
            )
            all_reasons: list[str] = []
            for pair in cluster_pairs:
                for reason in pair.reasons:
                    if reason not in all_reasons:
                        all_reasons.append(reason)
            average_overlap = round(
                sum(pair.overlap_score for pair in cluster_pairs) / len(cluster_pairs),
                4,
            )
            clusters.append(
                OverlapCluster(
                    cluster_id=f"cluster_{index:03d}",
                    representative_repo_full_name=representative,
                    repo_full_names=cluster_repo_names,
                    overlap_candidate_count=len(cluster_repo_names) - 1,
                    average_overlap_score=average_overlap,
                    reasons=tuple(all_reasons),
                )
            )

        return clusters

    def _build_repo_statuses(
        self,
        *,
        clusters: list[OverlapCluster],
        pairs: list[OverlapPair],
    ) -> dict[str, RepoOverlapStatus]:
        cluster_by_repo: dict[str, OverlapCluster] = {}
        for cluster in clusters:
            for repo_full_name in cluster.repo_full_names:
                cluster_by_repo[repo_full_name] = cluster

        touched_pairs_by_repo: dict[str, list[OverlapPair]] = {}
        for pair in pairs:
            touched_pairs_by_repo.setdefault(pair.repo_full_name_a, []).append(pair)
            touched_pairs_by_repo.setdefault(pair.repo_full_name_b, []).append(pair)

        statuses: dict[str, RepoOverlapStatus] = {}
        for repo_full_name, cluster in cluster_by_repo.items():
            touched_pairs = touched_pairs_by_repo.get(repo_full_name, [])
            strongest_pair = max(touched_pairs, key=lambda item: item.overlap_score)
            strongest_score = strongest_pair.overlap_score
            if cluster.representative_repo_full_name == repo_full_name:
                status = "REPRESENTATIVE"
                reason = (
                    f"Representative repository for {cluster.cluster_id}; "
                    "keep this as the primary portfolio entry."
                )
            else:
                status = "OVERLAP_CANDIDATE"
                reason = (
                    f"Strong overlap with {cluster.representative_repo_full_name}; "
                    "likely better merged, repositioned, or deprioritized."
                )
            statuses[repo_full_name] = RepoOverlapStatus(
                repo_full_name=repo_full_name,
                cluster_id=cluster.cluster_id,
                representative_repo_full_name=cluster.representative_repo_full_name,
                overlap_candidate_count=len(cluster.repo_full_names) - 1,
                strongest_overlap_score=round(strongest_score, 4),
                redundancy_status=status,
                redundancy_reason=reason,
            )

        return statuses

    @staticmethod
    def _representative_value(
        *,
        repo: RepoMetadata,
        score: RepoScore,
        review: RepoReview,
    ) -> float:
        stars_bonus = min(2.0, repo.engagement.stargazers_count * 0.1)
        blocker_penalty = min(4.0, len(review.blockers) * 1.0)
        action_penalty = min(3.0, len(review.priority_actions) * 0.35)
        return score.global_score + score.confidence * 2.0 + stars_bonus - blocker_penalty - action_penalty


# ---------------------------------------------------------------------------
# Pure utility functions
# ---------------------------------------------------------------------------


def _tokenize_name(name: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", name.lower())
        if token and len(token) >= 3 and token not in _GENERIC_NAME_TOKENS
    }


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _sequence_similarity(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left.lower().strip(), right.lower().strip()).ratio()
