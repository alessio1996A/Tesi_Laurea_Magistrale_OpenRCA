"""Candidate uniform C/K text extraction policy; OFFLINE, not wired to live.

A response made of text fragments must not acquire new characters solely
because a transport exposes boundaries. This module never repairs malformed
JSON, parses payloads, reads GT, constructs provider SDKs, or sends API calls.

This is a successor *candidate*. The frozen f0b64 source and G4E/G4L scientific
release remain authoritative for the existing records; do not activate live
stages using this module without an explicitly separated version/release.
"""
from __future__ import annotations

from typing import NamedTuple


MAX_BLOCKS = 256
POLICY = "rq2_ck_exact_text_fragments_candidate_v1"
TEXT_KINDS = (None, "text", "text_delta")


class VisibleText(NamedTuple):
    raw_text: str
    content_kind: str
    text_blocks: int
    other_blocks: int


class CKTextExtractionBlocked(ValueError):
    """Invalid or excessive content-block envelope; no guessing."""


def extract_visible_ck_text(content: object) -> VisibleText:
    """Return only visible text, concatenating fragments without separators.

    The block boundary is transport metadata, not permission to insert a
    newline or space. Pre-existing whitespace and invalid syntax are kept
    exactly. Distinct independent messages must not be passed as one list.
    No reasoning/signature/tool-use content is exposed.
    """
    if isinstance(content, str):
        return VisibleText(content, "str", int(bool(content)), 0)
    if not isinstance(content, list):
        return VisibleText("", "unsupported", 0, 0)
    if len(content) > MAX_BLOCKS:
        raise CKTextExtractionBlocked("Excessive C/K content blocks")

    fragments: list[str] = []
    other_count = 0
    for block in content:
        if isinstance(block, str):
            fragments.append(block)
        elif (
            isinstance(block, dict)
            and block.get("type") in TEXT_KINDS
            and isinstance(block.get("text"), str)
        ):
            fragments.append(block["text"])
        else:
            other_count += 1

    return VisibleText("".join(fragments), "list", len(fragments), other_count)
