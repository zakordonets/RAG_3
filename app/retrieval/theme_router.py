from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional

import yaml
from loguru import logger
from app.services.core.llm_router import (
    DEFAULT_LLM,
    _yandex_complete,
    _gpt5_complete,
    _deepseek_complete,
)


THEMES_CONFIG_ENV = "THEMES_CONFIG_PATH"
DEFAULT_THEMES_CONFIG = Path(__file__).resolve().parent.parent / "config" / "themes.yaml"


@dataclass(frozen=True)
class Theme:
    theme_id: str
    display_name: str
    domain: str
    section: Optional[str] = None
    platform: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None


class ThemeRoutingResult(Dict[str, Any]):
    """
    Результат маршрутизации запроса по тематикам.

    Используется как обычный словарь с предсказуемыми полями:
    - themes: список идентификаторов тематик в порядке убывания релевантности
    - primary_theme: идентификатор основной (наиболее релевантной) тематики или None
    - scores: словарь {theme_id: score}, где score ∈ [0, 1] — относительная уверенность
    - requires_disambiguation: флаг, что нужно уточнение тематики у пользователя
    - preferred_sections / preferred_platforms / preferred_domains:
      подсказки для фильтрации и лёгкого бустинга на этапе поиска.
    """


class ThemesProvider:
    """
    Провайдер тематик: загружает определения из themes.yaml и предоставляет доступ к ним.

    Особенности:
    - путь к конфигу можно переопределить через переменную окружения THEMES_CONFIG_PATH;
    - при ошибках загрузки конкретной темы она пропускается, но остальные продолжают работать;
    - результат кэшируется в памяти на время жизни процесса.
    """
    def __init__(self, config_path: Optional[Path] = None):
        path_env = os.getenv(THEMES_CONFIG_ENV)
        self.config_path = Path(path_env) if path_env else (config_path or DEFAULT_THEMES_CONFIG)
        self._themes = self._load()

    def _load(self) -> Dict[str, Theme]:
        if not self.config_path.exists():
            logger.warning("Themes config %s not found", self.config_path)
            return {}
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        themes_data = data.get("themes", {})
        themes: Dict[str, Theme] = {}
        for theme_id, cfg in themes_data.items():
            try:
                themes[theme_id] = Theme(
                    theme_id=theme_id,
                    display_name=cfg.get("display_name", theme_id),
                    domain=cfg.get("domain"),
                    section=cfg.get("section"),
                    platform=cfg.get("platform"),
                    role=cfg.get("role"),
                    description=cfg.get("description"),
                )
            except Exception as exc:
                logger.warning("Failed to load theme %s: %s", theme_id, exc)
        return themes

    def list_themes(self) -> List[Theme]:
        return list(self._themes.values())

    def get_theme(self, theme_id: str) -> Optional[Theme]:
        return self._themes.get(theme_id)


THEMES_PROVIDER = ThemesProvider()
KEYWORD_MAP = {
    "android": ["android", "gradle", "apk", "kotlin", "java"],
    "ios": ["ios", "swift", "xcode", "cocoapods"],
    "web": ["javascript", "widget", "web", "iframe"],
    "admin": ["админ", "администратор", "тег", "теги", "тегирование", "label", "tag"],
    "agent": ["агент", "оператор"],
    "supervisor": ["супервайзер", "supervisor"],
    "api": ["api", "swagger", "rest", "webhook", "интеграция"],
}


def route_query(query: str, user_metadata: Optional[Dict[str, Any]] = None) -> ThemeRoutingResult:
    """
    Маршрутизирует пользовательский запрос к одной или нескольким тематикам.

    Порядок работы:
    1) при включённом THEME_ROUTER_USE_LLM сначала пробует LLM‑классификацию;
    2) при ошибке LLM или пустом результате падает обратно на простую эвристику;
    3) возвращает ThemeRoutingResult, который дальше используется поиском и оркестратором.
    """
    llm_result = None
    if _is_llm_routing_enabled():
        llm_result = _try_llm_routing(query, user_metadata)
    if llm_result:
        return llm_result
    return _heuristic_routing(query, user_metadata)


def _score_by_keywords(query_lower: str, theme: Theme) -> float:
    """
    Считает вклад ключевых слов в общий скор тематики.

    Использует KEYWORD_MAP:
    - совпадения по platform дают больший вес;
    - совпадения по section дают меньший вес;
    - дополнительные бонусы для доменов (sdk_docs, chatcenter_user_docs).
    """
    score = 0.0
    if theme.platform and theme.platform in KEYWORD_MAP:
        if any(word in query_lower for word in KEYWORD_MAP[theme.platform]):
            score += 1.0
    if theme.section and theme.section in KEYWORD_MAP:
        if any(word in query_lower for word in KEYWORD_MAP[theme.section]):
            score += 0.7
    if theme.domain == "sdk_docs" and "sdk" in query_lower:
        score += 0.5
    if theme.domain == "chatcenter_user_docs" and any(word in query_lower for word in ["арм", "рабочее место", "интерфейс"]):
        score += 0.5
    return score


def _score_by_user_metadata(user_metadata: Optional[Dict[str, Any]], theme: Theme) -> float:
    """
    Считает вклад пользовательских метаданных (role/platform) в скор тематики.

    Совпадение role и platform с темой добавляет небольшой позитивный вес,
    чтобы слегка подстроить выбор темы под профиль пользователя, но не жёстко.
    """
    if not user_metadata:
        return 0.0
    score = 0.0
    preferred_role = str(user_metadata.get("role") or "").lower()
    preferred_platform = str(user_metadata.get("platform") or "").lower()
    if preferred_role and theme.role and preferred_role == theme.role.lower():
        score += 0.5
    if preferred_platform and theme.platform and preferred_platform == theme.platform.lower():
        score += 0.5
    return score


def get_theme(theme_id: str) -> Optional[Theme]:
    """Удобный помощник для получения Theme по идентификатору (обёртка над провайдером)."""
    return THEMES_PROVIDER.get_theme(theme_id)


def infer_theme_label(payload: Dict[str, Any]) -> Optional[str]:
    """
    Пытается определить человекочитаемую тему для документа по его метаданным.

    Использует связку domain/section/platform/role из payload и конфигурацию themes.yaml
    для поиска первой подходящей Theme и возвращает её display_name. Если ничего
    не подходит, возвращает None и документ считается «без явной тематики».
    """
    domain = str(payload.get("domain") or "").lower()
    section = str(payload.get("section") or "").lower()
    platform = str(payload.get("platform") or payload.get("sdk_platform") or "").lower()
    role = str(payload.get("role") or "").lower()

    for theme in THEMES_PROVIDER.list_themes():
        if theme.domain and domain and theme.domain != domain:
            continue
        if theme.section and section and theme.section != section:
            continue
        if theme.platform and platform and theme.platform != platform:
            continue
        if theme.role and role and theme.role != role:
            continue
        return theme.display_name
    return None


def _heuristic_routing(query: str, user_metadata: Optional[Dict[str, Any]]) -> ThemeRoutingResult:
    """
    Простая эвристическая маршрутизация по ключевым словам и пользовательским метаданным.

    Логика:
    - для каждой темы суммируются баллы по ключевым словам и user_metadata;
    - темы сортируются по убыванию score;
    - вычисляется primary_theme и проверяется, нужно ли уточнение (requires_disambiguation)
      если все скоры нулевые или разница между топ‑1 и топ‑2 слишком мала.
    """
    query_lower = (query or "").lower()
    themes = THEMES_PROVIDER.list_themes()
    scores: Dict[str, float] = {}
    for theme in themes:
        score = 0.0
        score += _score_by_keywords(query_lower, theme)
        score += _score_by_user_metadata(user_metadata, theme)
        scores[theme.theme_id] = score

    sorted_themes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary_theme = sorted_themes[0][0] if sorted_themes else None
    top_score = sorted_themes[0][1] if sorted_themes else 0.0
    second_score = sorted_themes[1][1] if len(sorted_themes) > 1 else 0.0
    requires_disambiguation = bool(
        (top_score == 0.0)
        or (second_score and (top_score - second_score) < 0.2)
    )

    preferred_sections = []
    preferred_platforms = []
    preferred_domains = []
    if primary_theme:
        theme_obj = THEMES_PROVIDER.get_theme(primary_theme)
        if theme_obj:
            if theme_obj.section:
                preferred_sections = [theme_obj.section]
            if theme_obj.platform:
                preferred_platforms = [theme_obj.platform]
            if theme_obj.domain:
                preferred_domains = [theme_obj.domain]

    return ThemeRoutingResult(
        themes=[theme_id for theme_id, _ in sorted_themes],
        primary_theme=primary_theme,
        scores=scores,
        requires_disambiguation=requires_disambiguation,
        preferred_sections=preferred_sections,
        preferred_platforms=preferred_platforms,
        preferred_domains=preferred_domains,
    )


def _is_llm_routing_enabled() -> bool:
    """
    Проверяет, включена ли LLM‑маршрутизация по переменной окружения THEME_ROUTER_USE_LLM.

    Любое из значений {\"1\", \"true\", \"yes\"} (без учёта регистра) считается включением.
    """
    return os.getenv("THEME_ROUTER_USE_LLM", "false").lower() in {"1", "true", "yes"}


def _try_llm_routing(query: str, user_metadata: Optional[Dict[str, Any]]) -> Optional[ThemeRoutingResult]:
    """
    Пытается классифицировать запрос по тематикам с помощью LLM.

    Порядок:
    - собирает список доступных тематик и формирует промпт с их описанием;
    - вызывает провайдеры LLM по очереди (DEFAULT_LLM → GPT5 → DEEPSEEK);
    - ожидает строгий JSON‑ответ (список объектов с theme_id и score);
    - при успехе строит ThemeRoutingResult, аналогичный эвристике;
    - при любой ошибке логирует предупреждение и возвращает None
      (что означает: надо fallback'нуться на _heuristic_routing).
    """
    try:
        themes = THEMES_PROVIDER.list_themes()
        if not themes:
            return None

        system_prompt = (
            "Ты классифицируешь пользовательские запросы по предопределённым тематикам документации. "
            "Возвращай JSON массив объектов {\"theme_id\": \"...\", \"score\": 0..1, \"reason\": \"...\"}. "
            "score должен отражать уверенность. От 1 до 3 объектов."
        )
        themes_desc = "\n".join(
            f"- {theme.theme_id}: {theme.display_name} "
            f"(domain={theme.domain}, section={theme.section}, platform={theme.platform}, role={theme.role})"
            for theme in themes
        )
        user_meta_desc = f"User metadata: {user_metadata}\n" if user_metadata else ""
        prompt = (
            f"{user_meta_desc}"
            f"Темы:\n{themes_desc}\n\n"
            f"Запрос: {query}\n\n"
            "Ответь JSON списком вида [{\"theme_id\": \"...\", \"score\": 0.0-1.0, \"reason\": \"...\"}]."
        )

        order = [DEFAULT_LLM, "GPT5", "DEEPSEEK"]
        raw_answer = None
        last_provider = None
        for provider in order:
            try:
                last_provider = provider
                if provider == "YANDEX":
                    raw_answer = _yandex_complete(prompt, max_tokens=400, temperature=0.0, top_p=0.9, system_prompt=system_prompt)
                elif provider == "GPT5":
                    raw_answer = _gpt5_complete(prompt, max_tokens=400, system_prompt=system_prompt)
                else:
                    raw_answer = _deepseek_complete(prompt, max_tokens=400, system_prompt=system_prompt)
                if raw_answer:
                    break
            except Exception as exc:
                logger.warning(f"Theme router LLM provider {provider} failed: {exc}")
        if not raw_answer:
            return None

        cleaned = _strip_code_fence(str(raw_answer))
        if not cleaned:
            logger.warning("Theme router empty LLM response from %s", last_provider)
            return None
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("Theme router LLM JSON decode error from %s: %s", last_provider, exc)
            logger.debug("Raw LLM response: %r", raw_answer[:500])
            return None
        if not isinstance(parsed, list):
            return None
        scores = {item["theme_id"]: float(item.get("score", 0.0)) for item in parsed if "theme_id" in item}
        sorted_themes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if not sorted_themes:
            return None
        primary_theme = sorted_themes[0][0]
        requires_disambiguation = sorted_themes[0][1] < 0.5
        preferred_sections = []
        preferred_platforms = []
        preferred_domains = []
        theme_obj = THEMES_PROVIDER.get_theme(primary_theme)
        if theme_obj:
            if theme_obj.section:
                preferred_sections = [theme_obj.section]
            if theme_obj.platform:
                preferred_platforms = [theme_obj.platform]
            if theme_obj.domain:
                preferred_domains = [theme_obj.domain]
        return ThemeRoutingResult(
            themes=[theme_id for theme_id, _ in sorted_themes],
            primary_theme=primary_theme,
            scores=scores,
            requires_disambiguation=requires_disambiguation,
            preferred_sections=preferred_sections,
            preferred_platforms=preferred_platforms,
            preferred_domains=preferred_domains,
        )
    except Exception as exc:
        logger.warning(f"LLM routing failed, fallback to heuristics: {exc}")
        return None


def _strip_code_fence(answer: str) -> str:
    """
    Очищает ответ LLM от обёрток вида ```json ... ``` и префикса `JSON`.

    Нужен для того, чтобы json.loads смог корректно распарсить ответ,
    даже если модель вернула его в виде markdown‑блока кода.
    """
    cleaned = answer.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.strip("`")
    return cleaned.strip()
