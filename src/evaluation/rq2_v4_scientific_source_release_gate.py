"""RQ2-V4 source/release gate — DEFAULT NO-GO, until separately audited.

La V3 e i suoi hash sono congelati. La V4 ha identificativi nuovi e
non possiede ancora una release create-only. Riutilizzare una prova
o una release V3 sarebbe metodologicamente scorretto.

Non è un gate fittizio abilitante: perfino una chiamata con dictionary
plausibile fallisce prima di qualunque claim o richiesta ai provider.
"""
from __future__ import annotations

VERSION = "rq2_v4_scientific_source_release_gate_not_implemented_v0"
RELEASE_SCHEMA = "rq2_v4_scientific_release_v1"


class V4SourceReleaseBlocked(ValueError):
    """No verified V4 source/release: absolutely no V4 claims/API."""


def verify_v4_source_release(*, data_dir, repo_dir, release: dict,
                             expected_commit: str,
                             approved_release_sha256: str) -> dict:
    raise V4SourceReleaseBlocked(
        "V4 independent source inventory/runtime/release gate not implemented: "
        "NO RELEASE, NO CLAIM, NO API"
    )
