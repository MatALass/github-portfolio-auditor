from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

try:
    __version__ = version("github-portfolio-auditor")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = ["AuditArtifacts", "AuditRunner", "__version__"]


def __getattr__(name: str) -> Any:
    if name in {"AuditArtifacts", "AuditRunner"}:
        from portfolio_auditor.audit_runner import AuditArtifacts, AuditRunner

        mapping = {
            "AuditArtifacts": AuditArtifacts,
            "AuditRunner": AuditRunner,
        }
        return mapping[name]
    raise AttributeError(f"module 'portfolio_auditor' has no attribute {name!r}")