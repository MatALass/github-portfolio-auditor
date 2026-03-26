from __future__ import annotations

import argparse
import sys

from portfolio_auditor.audit_runner import AuditRunner
from portfolio_auditor.settings import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full GitHub portfolio audit pipeline.",
    )
    parser.add_argument(
        "--owner",
        required=True,
        help="GitHub username or organization to audit.",
    )
    parser.add_argument(
        "--refresh-clones",
        action="store_true",
        help="Delete existing local clones and re-clone from GitHub.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    runner = AuditRunner(settings)

    try:
        artifacts = runner.run(
            owner=args.owner,
            refresh_clones=args.refresh_clones,
            enrich=True,
            export=True,
        )
    except Exception as exc:
        print(f"[ERROR] Audit failed: {exc}", file=sys.stderr)
        return 1
    finally:
        runner.close()

    print("")
    print("Audit completed successfully.")
    print(f"Repositories analyzed: {len(artifacts.repos)}")
    print(f"Scores generated: {len(artifacts.scores)}")
    print(f"Reviews generated: {len(artifacts.reviews)}")
    print(f"Exports directory: {(settings.processed_dir / args.owner).resolve()}")

    if artifacts.scores:
        print("")
        print("Top repositories:")
        for item in sorted(artifacts.scores, key=lambda score: score.global_score, reverse=True)[:5]:
            print(f"  - {item.repo_full_name}: {item.global_score:.2f}/100 ({item.score_label})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())