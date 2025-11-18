from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

import yaml
from loguru import logger


@dataclass(frozen=True)
class BoostingConfig:
    """
    Нормализованная конфигурация бустинга поиска.

    Все значения здесь уже приведены к удобному для кода виду и не содержат «сырого» YAML:
    - ключи словарей нормализованы (строки, обычно в lower);
    - коэффициенты приведены к float;
    - сложные структуры (url_patterns, title_keywords и т.д.) приведены к единообразному формату.

    Поля:
    - page_type_boosts: бусты по типу страницы (page_type);
    - section_boosts: бусты по разделу (section);
    - platform_boosts: бусты по платформе (platform/sdk_platform);
    - url_patterns: список правил вида {"paths": [...], "boost": float};
    - title_keywords: ключевые слова в заголовке с весами;
    - length: параметры длины текста (optimal_min/max, boosts);
    - structure: маркеры структурированности текста и соответствующие boosts;
    - source_boosts: бусты по источнику (source);
    - depth_penalty: штраф за глубину URL (min_depth, factor);
    - theme_boost: бусты, связанные с тематическим роутингом (primary/secondary).
    """

    page_type_boosts: Dict[str, float] = field(default_factory=dict)
    section_boosts: Dict[str, float] = field(default_factory=dict)
    platform_boosts: Dict[str, float] = field(default_factory=dict)
    url_patterns: List[Dict[str, Any]] = field(default_factory=list)
    title_keywords: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    length: Dict[str, float] = field(default_factory=dict)
    structure: Dict[str, Any] = field(default_factory=dict)
    source_boosts: Dict[str, float] = field(default_factory=dict)
    depth_penalty: Dict[str, float] = field(default_factory=dict)
    theme_boost: Dict[str, float] = field(default_factory=dict)


DEFAULT_BOOSTING_CONFIG_PATH = Path(__file__).with_name("boosting.yaml")
BOOSTING_CONFIG_ENV = "BOOSTING_CONFIG_PATH"
_BOOSTING_CONFIG_CACHE: Optional[BoostingConfig] = None


def get_boosting_config(reload: bool = False) -> BoostingConfig:
    """
    Возвращает текущую конфигурацию бустинга, загруженную из boosting.yaml.

    Особенности:
    - по умолчанию результат кешируется в памяти, чтобы не читать файл на каждый запрос;
    - путь к файлу можно переопределить через переменную окружения BOOSTING_CONFIG_PATH;
    - при ошибках чтения/парсинга возвращается пустая BoostingConfig без выброса исключения.

    Параметр reload=True принудительно сбрасывает кеш и перечитывает конфиг (удобно в тестах).
    """
    global _BOOSTING_CONFIG_CACHE
    if _BOOSTING_CONFIG_CACHE is not None and not reload:
        return _BOOSTING_CONFIG_CACHE

    config = _load_boosting_config()
    _BOOSTING_CONFIG_CACHE = config
    return config


def reset_boosting_config_cache() -> None:
    """Сбрасывает кеш BoostingConfig (используется в тестах и при hot‑reload)."""
    global _BOOSTING_CONFIG_CACHE
    _BOOSTING_CONFIG_CACHE = None


def _load_boosting_config() -> BoostingConfig:
    """
    Непосредственно читает boosting.yaml с диска и нормализует его в BoostingConfig.

    Здесь не используется кеширование — оно реализовано на уровне get_boosting_config.
    """
    cfg_path_str = os.getenv(BOOSTING_CONFIG_ENV)
    cfg_path = Path(cfg_path_str) if cfg_path_str else DEFAULT_BOOSTING_CONFIG_PATH
    if not cfg_path.exists():
        logger.warning("Boosting config %s not found, using defaults", cfg_path)
        return BoostingConfig()
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse boosting config %s: %s", cfg_path, exc)
        return BoostingConfig()

    return BoostingConfig(
        page_type_boosts=_coerce_float_dict(data.get("page_type_boosts")),
        section_boosts=_coerce_float_dict(data.get("section_boosts")),
        platform_boosts=_coerce_float_dict(data.get("platform_boosts")),
        url_patterns=_normalize_url_patterns(data.get("url_patterns")),
        title_keywords=_normalize_title_keywords(data.get("title_keywords")),
        length=_normalize_length_config(data.get("length")),
        structure=_normalize_structure_config(data.get("structure")),
        source_boosts=_coerce_float_dict(data.get("source_boosts")),
        depth_penalty=_normalize_depth_penalty(data.get("depth_penalty")),
        theme_boost=_normalize_theme_boost(data.get("theme_boost")),
    )


def _coerce_float_dict(value: Any) -> Dict[str, float]:
    """
    Приводит словарь произвольных значений к словарю {str(key).lower(): float(value)}.

    Невалидные записи пропускаются с логированием warning и не попадают в результат.
    """
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for key, raw in value.items():
        try:
            result[str(key).lower()] = float(raw)
        except (TypeError, ValueError):
            logger.warning("Invalid boost value for %s: %r", key, raw)
    return result


def _normalize_url_patterns(value: Any) -> List[Dict[str, Any]]:
    """
    Нормализует конфиг url_patterns из YAML в список правил с предсказуемой структурой.

    На выходе каждая запись имеет вид:
    {"paths": ["/docs/android", "/docs/ios"], "boost": 1.1}
    """
    if not isinstance(value, dict):
        return []
    patterns: List[Dict[str, Any]] = []
    for _, cfg in value.items():
        paths = cfg.get("paths") if isinstance(cfg, dict) else None
        boost = cfg.get("boost") if isinstance(cfg, dict) else None
        if not isinstance(paths, list) or boost is None:
            continue
        try:
            boost_value = float(boost)
        except (TypeError, ValueError):
            continue
        normalized_paths = [str(p).lower() for p in paths if isinstance(p, str)]
        if not normalized_paths:
            continue
        patterns.append({"paths": normalized_paths, "boost": boost_value})
    return patterns


def _normalize_title_keywords(value: Any) -> Dict[str, Dict[str, Any]]:
    """
    Нормализует блок title_keywords.

    Возвращает словарь:
    {
      "group_id": {
        "words": [слова в lower],
        "boost": float
      },
      ...
    }
    """
    if not isinstance(value, dict):
        return {}
    normalized: Dict[str, Dict[str, Any]] = {}
    for key, cfg in value.items():
        if not isinstance(cfg, dict):
            continue
        words = cfg.get("words")
        boost = cfg.get("boost")
        if not isinstance(words, list) or boost is None:
            continue
        try:
            boost_value = float(boost)
        except (TypeError, ValueError):
            continue
        normalized[str(key).lower()] = {
            "words": [str(w).lower() for w in words if isinstance(w, str)],
            "boost": boost_value,
        }
    return normalized


def _normalize_length_config(value: Any) -> Dict[str, float]:
    """
    Нормализует параметры длины текста.

    Оставляет только известные ключи (optimal_min, optimal_max, optimal_boost, long_boost)
    и приводит их значения к float, игнорируя невалидные записи.
    """
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for key in ("optimal_min", "optimal_max", "optimal_boost", "long_boost"):
        raw = value.get(key)
        if raw is None:
            continue
        try:
            result[key] = float(raw)
        except (TypeError, ValueError):
            continue
    return result


def _normalize_structure_config(value: Any) -> Dict[str, Any]:
    """
    Нормализует блок structure.

    - well_structured_markers / example_markers приводятся к спискам lower‑строк;
    - well_structured_boost / example_boost приводятся к float (по умолчанию 1.0).
    """
    if not isinstance(value, dict):
        return {}
    return {
        "well_structured_markers": [
            str(v).lower() for v in value.get("well_structured_markers", []) if isinstance(v, str)
        ],
        "example_markers": [
            str(v).lower() for v in value.get("example_markers", []) if isinstance(v, str)
        ],
        "well_structured_boost": float(value.get("well_structured_boost", 1.0)),
        "example_boost": float(value.get("example_boost", 1.0)),
    }


def _normalize_depth_penalty(value: Any) -> Dict[str, float]:
    """
    Нормализует штраф за глубину URL.

    Гарантирует наличие числовых min_depth (int) и factor (float) с безопасными дефолтами.
    """
    if not isinstance(value, dict):
        return {"min_depth": 0, "factor": 1.0}
    try:
        min_depth = int(value.get("min_depth", 0))
    except (TypeError, ValueError):
        min_depth = 0
    try:
        factor = float(value.get("factor", 1.0))
    except (TypeError, ValueError):
        factor = 1.0
    return {"min_depth": min_depth, "factor": factor}


def _normalize_theme_boost(value: Any) -> Dict[str, float]:
    """
    Нормализует настройки тематического буста.

    Возвращает словарь с ключами primary_boost и secondary_boost,
    оба приведены к float и имеют дефолт 1.0.
    """
    if not isinstance(value, dict):
        return {"primary_boost": 1.0, "secondary_boost": 1.0}
    try:
        primary = float(value.get("primary_boost", 1.0))
    except (TypeError, ValueError):
        primary = 1.0
    try:
        secondary = float(value.get("secondary_boost", 1.0))
    except (TypeError, ValueError):
        secondary = 1.0
    return {"primary_boost": primary, "secondary_boost": secondary}
