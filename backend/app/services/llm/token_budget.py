"""backend/app/services/llm/token_budget.py"""
"""Cheap token estimates. For exact numbers, use the usage metadata the API returns."""


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)      # ~4 characters per token for English


def fits(text: str, max_tokens: int) -> bool:
    return estimate_tokens(text) <= max_tokens


def trim_to_tokens(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " …"