from __future__ import annotations

from typing import Dict, Any, List

from app.config.boosting_config import BoostingConfig


def boost_hits(hits: List[dict], cfg: BoostingConfig, context: Dict[str, Any] | None = None) -> List[dict]:
    """
    Применяет boosting ко всему списку результатов поиска и пересортировывает их.

    Логика:
    - для каждого документа выбирается базовый score (rrf_score → score → 0.0);
    - рассчитывается итоговый boosted_score через boost_score;
    - список сортируется по boosted_score по убыванию.

    Параметр context позволяет передавать:
    - boosts: временные бусты по page_type (ручная настройка для одного запроса);
    - group_boosts: бусты по логическим группам документов;
    - routing_result: результат тематического роутинга (используется внутри boost_score).
    """
    if not hits:
        return hits
    context = context or {}
    for item in hits:
        base_score = item.get("rrf_score", item.get("score", 0.0)) or 0.0
        payload = item.get("payload", {}) or {}
        item["boosted_score"] = boost_score(base_score, payload, cfg, context)
    hits.sort(key=lambda x: x.get("boosted_score", 0.0), reverse=True)
    return hits


def boost_score(base_score: float, payload: Dict[str, Any], cfg: BoostingConfig, context: Dict[str, Any] | None = None) -> float:
    """
    Применяет набор правил boosting к одному документу.

    Правила независимы и применяются последовательно, небольшими коэффициентами:
    - тип страницы (page_type);
    - раздел / платформа (section/platform);
    - тематика от роутера (theme_boost);
    - группы (group_boosts);
    - URL‑паттерны;
    - ключевые слова в заголовке;
    - длина текста (оптимальная зона / слишком длинные);
    - структура (наличие примеров, подзаголовков и т.п.);
    - источник (source);
    - штраф за глубину URL (слишком глубокие вложения).

    Все коэффициенты задаются в boosting.yaml и должны быть «мягкими» (близко к 1.0),
    чтобы boosting лишь слегка перестраивал выдачу, не ломая RRF/базовый скор.
    """
    context = context or {}
    s = float(base_score or 0.0)
    s = _apply_page_type_boost(s, payload, cfg, context)
    s = _apply_section_platform_boost(s, payload, cfg)
    s = _apply_theme_boost_from_routing(s, payload, cfg, context)
    s = _apply_group_boost(s, payload, context)
    s = _apply_url_pattern_boost(s, payload, cfg)
    s = _apply_title_boost(s, payload, cfg)
    s = _apply_length_boost(s, payload, cfg)
    s = _apply_structure_boost(s, payload, cfg)
    s = _apply_source_boost(s, payload, cfg)
    s = _apply_depth_penalty(s, payload, cfg)
    return s


def _apply_page_type_boost(s: float, payload: Dict[str, Any], cfg: BoostingConfig, context: Dict[str, Any]) -> float:
    """
    Буст по типу страницы (page_type).

    Источники коэффициентов:
    - runtime_boosts из context["boosts"] — можно задать на один запрос;
    - cfg.page_type_boosts из boosting.yaml — постоянные настройки.
    """
    page_type = str(payload.get("page_type") or "").lower()
    if not page_type:
        return s
    runtime_boosts = context.get("boosts") or {}
    if page_type in runtime_boosts:
        try:
            s *= float(runtime_boosts[page_type])
        except (TypeError, ValueError):
            pass
    cfg_boost = cfg.page_type_boosts.get(page_type)
    if cfg_boost:
        s *= cfg_boost
    return s


def _apply_section_platform_boost(s: float, payload: Dict[str, Any], cfg: BoostingConfig) -> float:
    """
    Буст по разделу и платформе (section/platform).

    Используется для лёгкого предпочтения, например:
    - admin / agent / supervisor разделов;
    - android / ios / web платформ в SDK.
    """
    section = str(payload.get("section") or "").lower()
    platform = str(payload.get("platform") or payload.get("sdk_platform") or "").lower()
    if section:
        boost = cfg.section_boosts.get(section)
        if boost:
            s *= boost
    if platform:
        boost = cfg.platform_boosts.get(platform)
        if boost:
            s *= boost
    return s


def _apply_theme_boost_from_routing(s: float, payload: Dict[str, Any], cfg: BoostingConfig, context: Dict[str, Any]) -> float:
    """
    Тематический буст на основе результата роутинга.

    - При совпадении domain/section/platform с primary темой применяется primary_boost.
    - Дополнительно учитывается числовой score тематики от роутера как мягкий фактор.
    - Если документ не попадает в основную тематику, буст не применяется.
    """
    routing_result = context.get("routing_result")
    if not routing_result:
        return s
    preferred_sections = routing_result.get("preferred_sections") or []
    preferred_platforms = routing_result.get("preferred_platforms") or []
    preferred_domains = routing_result.get("preferred_domains") or []
    section = str(payload.get("section") or "").lower()
    platform = str(payload.get("platform") or payload.get("sdk_platform") or "").lower()
    domain = str(payload.get("domain") or "").lower()

    primary_boost = cfg.theme_boost.get("primary_boost", 1.0)
    secondary_boost = cfg.theme_boost.get("secondary_boost", 1.0)

    boosted = False
    if preferred_domains and domain in [d.lower() for d in preferred_domains]:
        s *= primary_boost
        boosted = True

    if preferred_sections and section in [sec.lower() for sec in preferred_sections]:
        s *= primary_boost
        boosted = True

    if preferred_platforms and platform in [plat.lower() for plat in preferred_platforms]:
        s *= secondary_boost if boosted else primary_boost
        boosted = True

    scores = routing_result.get("scores") or {}
    if not boosted and scores:
        primary_theme = routing_result.get("primary_theme")
        theme_score = None
        if primary_theme and primary_theme in scores:
            theme_score = scores[primary_theme]
        if theme_score:
            try:
                factor = max(1.0, float(theme_score))
                s *= min(primary_boost, factor)
            except (TypeError, ValueError):
                pass

    return s


def _apply_group_boost(s: float, payload: Dict[str, Any], context: Dict[str, Any]) -> float:
    """
    Буст по логическим группам документов.

    - Группы берутся из payload["groups_path"] или payload["group_labels"].
    - context["group_boosts"] содержит словарь {подстрока: коэффициент}.
    - Если имя группы содержит подстроку ключа, применяется соответствующий boost.
    """
    group_boosts = context.get("group_boosts") or {}
    if not group_boosts:
        return s
    groups = payload.get("groups_path") or payload.get("group_labels") or []
    if isinstance(groups, str):
        groups = [groups]
    for group in groups:
        group_norm = str(group).lower().strip()
        for key, factor in group_boosts.items():
            if key and key in group_norm:
                try:
                    s *= float(factor)
                except (TypeError, ValueError):
                    pass
                return s
    return s


def _apply_url_pattern_boost(s: float, payload: Dict[str, Any], cfg: BoostingConfig) -> float:
    """
    Буст по URL‑паттернам.

    Позволяет тонко поднять/опустить конкретные ветки документации по подстрокам пути,
    например, приоритизировать /android/intro или понизить /legacy/.
    """
    if not cfg.url_patterns:
        return s
    url = str(payload.get("url") or payload.get("canonical_url") or payload.get("site_url") or "").lower()
    if not url:
        return s
    for pattern in cfg.url_patterns:
        if any(path in url for path in pattern.get("paths", [])):
            boost = pattern.get("boost")
            if isinstance(boost, (int, float)):
                s *= float(boost)
    return s


def _apply_title_boost(s: float, payload: Dict[str, Any], cfg: BoostingConfig) -> float:
    """
    Буст по ключевым словам в заголовке.

    В boosting.yaml задаются группы ключевых слов с отдельными коэффициентами;
    если хоть одно ключевое слово встречается в title, применяется указанный boost.
    """
    if not cfg.title_keywords:
        return s
    title = str(payload.get("title") or "").lower()
    if not title:
        return s
    for entry in cfg.title_keywords.values():
        words = entry.get("words") or []
        boost = entry.get("boost")
        if not isinstance(boost, (int, float)):
            continue
        if any(word in title for word in words):
            s *= float(boost)
    return s


def _apply_length_boost(s: float, payload: Dict[str, Any], cfg: BoostingConfig) -> float:
    """
    Буст по длине текста.

    - оптимальная зона (optimal_min..optimal_max) получает небольшой положительный boost;
    - слишком длинные документы могут получать понижающий коэффициент;
    - длина берётся из payload["content_length"] или по длине текста.
    """
    length_cfg = cfg.length
    if not length_cfg:
        return s
    text = payload.get("text", "") or ""
    content_length = payload.get("content_length") or len(text)
    try:
        content_length = int(content_length)
    except (TypeError, ValueError):
        return s
    optimal_min = length_cfg.get("optimal_min")
    optimal_max = length_cfg.get("optimal_max")
    optimal_boost = length_cfg.get("optimal_boost")
    long_boost = length_cfg.get("long_boost")

    if optimal_min and optimal_max and optimal_boost and optimal_min <= content_length <= optimal_max:
        s *= optimal_boost
    elif optimal_max and long_boost and content_length > optimal_max:
        s *= long_boost
    return s


def _apply_structure_boost(s: float, payload: Dict[str, Any], cfg: BoostingConfig) -> float:
    """
    Буст по структурированности текста.

    Проверяются маркеры хорошей структуры и наличия примеров (well_structured_markers,
    example_markers) в тексте; при совпадении применяются соответствующие boost’ы.
    """
    structure_cfg = cfg.structure or {}
    text = str(payload.get("text") or "").lower()
    if not text:
        return s
    markers = structure_cfg.get("well_structured_markers") or []
    if any(marker in text for marker in markers):
        boost = structure_cfg.get("well_structured_boost")
        if isinstance(boost, (int, float)):
            s *= float(boost)
    example_markers = structure_cfg.get("example_markers") or []
    if any(marker in text for marker in example_markers):
        boost = structure_cfg.get("example_boost")
        if isinstance(boost, (int, float)):
            s *= float(boost)
    return s


def _apply_source_boost(s: float, payload: Dict[str, Any], cfg: BoostingConfig) -> float:
    """
    Буст по источнику документа (payload.source).

    Удобно, когда нужно слегка приоритизировать конкретный источник или, наоборот,
    немного опустить менее надёжный канал документации.
    """
    source = str(payload.get("source") or "").lower()
    if not source:
        return s
    boost = cfg.source_boosts.get(source)
    if boost:
        s *= boost
    return s


def _apply_depth_penalty(s: float, payload: Dict[str, Any], cfg: BoostingConfig) -> float:
    """
    Штраф за глубину URL.

    Если путь документа содержит больше сегментов, чем min_depth,
    применяется понижающий коэффициент factor. Это позволяет слегка
    понизить очень «глубокие» страницы относительно верхнеуровневых.
    """
    depth_cfg = cfg.depth_penalty or {}
    min_depth = depth_cfg.get("min_depth")
    factor = depth_cfg.get("factor")
    if not min_depth or not factor:
        return s
    try:
        min_depth = int(min_depth)
        factor = float(factor)
    except (TypeError, ValueError):
        return s
    if min_depth <= 0 or factor <= 0:
        return s
    url = str(payload.get("url") or payload.get("canonical_url") or payload.get("site_url") or "").strip("/")
    if not url:
        return s
    depth = len([seg for seg in url.split("/") if seg])
    if depth > min_depth:
        s *= factor
    return s
