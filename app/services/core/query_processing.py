from __future__ import annotations

from typing import Any


def extract_entities(text: str) -> list[str]:
    if not text:
        return []
    # Простая эвристика (позже заменить ML-экстракцией/словари домена)
    candidates = ["арм агента", "арм супервайзера", "арм администратора", "api", "faq", "release notes", "чат-боты"]
    lowered = text.lower()
    return [c for c in candidates if c in lowered]


def rewrite_query(text: str) -> str:
    if not text:
        return text
    # Нормализация: базовая замена синонимов/аббревиатур
    normalized = text.replace("РН", "Release Notes")
    return normalized


def maybe_decompose(text: str, max_depth: int = 3) -> list[str]:
    if not text:
        return []
    # Простая декомпозиция по " и ":
    parts = [p.strip() for p in text.split(" и ") if p.strip()]
    return parts[:max_depth]


def process_query(text: str) -> dict[str, Any]:
    entities = extract_entities(text)
    normalized = rewrite_query(text)
    subqueries = maybe_decompose(normalized)
    boosts = {"faq": 1.2 if any(w in normalized.lower() for w in ["как", "что", "почему"]) else 1.0}
    return {"normalized_text": normalized, "entities": entities, "boosts": boosts, "subqueries": subqueries}


