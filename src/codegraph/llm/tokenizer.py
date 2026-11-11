"""Tokenizer Profile Engine for CodeGraph.

Provides deterministic BPE token counting using tiktoken with:
- o200k_base (GPT-4o, modern frontier models)
- cl100k_base (GPT-4, Claude approximations)
- Fast character-ratio fallback (3.6 chars/token) if tiktoken is absent.
- 92% safety multiplier: effective_cap = floor(max_tokens * 0.92) to guarantee
  cross-tokenizer variance never breaches requested caps.
"""
from __future__ import annotations

import functools
import json
import math
from typing import Any

SAFETY_MULTIPLIER: float = 0.92
CHAR_RATIO_FALLBACK: float = 3.6
DEFAULT_PROFILE: str = "o200k_base"
SUPPORTED_PROFILES: frozenset[str] = frozenset({"o200k_base", "cl100k_base"})


@functools.lru_cache(maxsize=4)
def _get_tiktoken_encoding(profile: str) -> Any | None:
    """Retrieve and cache tiktoken encoding object if available."""
    try:
        import tiktoken

        return tiktoken.get_encoding(profile)
    except Exception:
        return None


def get_effective_cap(max_tokens: int) -> int:
    """Apply the 92% safety multiplier to compute effective token cap.

    effective_cap = floor(max_tokens * 0.92)
    """
    if max_tokens <= 0:
        return 0
    return math.floor(max_tokens * SAFETY_MULTIPLIER)


def count_tokens(text: str, profile: str = DEFAULT_PROFILE) -> int:
    """Count tokens in text deterministically using tiktoken or ratio fallback.

    Args:
        text: Input string to tokenize.
        profile: Tokenizer profile name ('o200k_base' or 'cl100k_base').

    Returns:
        Exact or fallback token count.
    """
    if not text:
        return 0

    encoding = _get_tiktoken_encoding(profile)
    if encoding is not None:
        try:
            return len(encoding.encode(text))
        except Exception:
            pass

    # Fast character-ratio fallback (3.6 chars/token)
    return max(1, math.ceil(len(text) / CHAR_RATIO_FALLBACK))


def count_json_tokens(data: Any, profile: str = DEFAULT_PROFILE) -> int:
    """Serialize data to compact JSON and count its tokens."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return count_tokens(payload, profile=profile)


def encode(text: str, profile: str = DEFAULT_PROFILE) -> list[int]:
    """Encode text into token IDs."""
    if not text:
        return []
    encoding = _get_tiktoken_encoding(profile)
    if encoding is not None:
        try:
            return list(encoding.encode(text))
        except Exception:
            pass
    # Fallback byte representation if tiktoken is missing
    return list(text.encode("utf-8"))


def decode(tokens: list[int], profile: str = DEFAULT_PROFILE) -> str:
    """Decode token IDs back into string."""
    if not tokens:
        return ""
    encoding = _get_tiktoken_encoding(profile)
    if encoding is not None:
        try:
            return str(encoding.decode(tokens))
        except Exception:
            pass
    try:
        return bytes(tokens).decode("utf-8", errors="replace")
    except Exception:
        return ""
