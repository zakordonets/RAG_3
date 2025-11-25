from __future__ import annotations
import time
import asyncio
from datetime import datetime, timezone
from loguru import logger

from typing import Any, Dict, List, Optional
from qdrant_client.models import Filter, FieldCondition, MatchValue
from app.services.core.query_processing import process_query
from app.services.core.embeddings import embed_unified, embed_dense_optimized, embed_sparse_optimized, embed_dense
from app.config import CONFIG
from app.retrieval.retrieval import hybrid_search, auto_merge_neighbors
from app.retrieval.rerank import rerank
from app.services.core.llm_router import generate_answer
from app.services.core.context_optimizer import context_optimizer
from app.infrastructure import get_metrics_collector
from app.infrastructure.query_logging import log_query_interaction
from app.services.quality.quality_manager import quality_manager
from app.retrieval import route_query
from app.retrieval.theme_router import get_theme, infer_theme_label, infer_theme_id


class RAGError(Exception):
    """Базовый класс для ошибок RAG системы."""
    pass


class EmbeddingError(RAGError):
    """Ошибка при создании эмбеддингов."""
    pass


class SearchError(RAGError):
    """Ошибка при поиске в векторной базе."""
    pass


class LLMError(RAGError):
    """Ошибка при обращении к LLM."""
    pass


def handle_query(channel: str, chat_id: str, message: str) -> dict[str, Any]:
    """
    Обрабатывает пользовательский запрос с comprehensive error handling.

    Args:
        channel: Канал связи (telegram, web, etc.)
        chat_id: ID чата
        message: Текст сообщения

    Returns:
        Словарь с ответом, источниками и метаданными

    Raises:
        RAGError: При критических ошибках системы
    """
    start = time.time()
    logger.info(f"Processing query: {message[:100]}...")

    metrics = get_metrics_collector()
    log_data = _init_query_log(channel, chat_id, message)
    timings: Dict[str, Optional[float]] = {
        "total": None,
        "query_processing": None,
        "routing": None,
        "embeddings": None,
        "search": None,
        "search_no_filter": None,
        "rerank": None,
        "context_optimization": None,
        "llm_generation": None,
    }
    max_log_candidates = CONFIG.query_log_max_candidates
    text_prefix_len = CONFIG.query_log_text_prefix_len

    error_type = None
    status = "success"

    try:
        # 1. Query Processing
        qp_start = time.time()
        try:
            qp = process_query(message)
            normalized = qp["normalized_text"]
            boosts = qp.get("boosts", {})
            group_boosts = qp.get("group_boosts", {})
            qp_duration = time.time() - qp_start
            logger.info(f"Query processed in {qp_duration:.2f}s")
            metrics.record_query_duration("query_processing", qp_duration)
            timings["query_processing"] = qp_duration
            log_data["request"].update({
                "normalized": normalized,
                "boosts": boosts,
                "group_boosts": group_boosts,
            })
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            log_data["status"] = "error"
            log_data["error_type"] = "query_processing_failed"
            timings["total"] = time.time() - start
            _finalize_query_log(log_data, timings)
            return {
                "error": "query_processing_failed",
                "message": "Ошибка обработки запроса. Попробуйте переформулировать вопрос.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        routing_start = time.time()
        routing_result = route_query(normalized, user_metadata=None)
        routing_duration = time.time() - routing_start
        logger.info(
            f"Theme routing in {routing_duration:.2f}s "
            f"(primary={routing_result.get('primary_theme')}, "
            f"via_llm={routing_result.get('router', 'unknown')}, "
            f"disambiguation={routing_result.get('requires_disambiguation')})"
        )
        metrics.record_query_duration("routing", routing_duration)
        timings["routing"] = routing_duration
        log_data["routing"] = _serialize_routing_result(routing_result)
        theme_filter = _build_theme_filter(routing_result)
        log_data["search"] = {
            "theme_filter_applied": theme_filter is not None,
            "theme_filter_conditions": _describe_theme_filter(theme_filter),
            "fallback_without_filter": False,
            "candidates_total": 0,
            "candidates_before_theme_boost": [],
            "candidates_after_theme_boost": [],
            "candidates_after_rerank": [],
        }

        # 2. Unified Embeddings Generation
        try:
            embedding_start = time.time()

            # Import optimal strategy detection
            from app.services.core.embeddings import _get_optimal_backend_strategy
            optimal_backend = _get_optimal_backend_strategy()

            # Choose embedding strategy based on optimal backend
            if optimal_backend in ["bge", "hybrid"]:
                # Use unified BGE-M3 embedding generation
                embedding_result = embed_unified(
                    normalized,
                    max_length=CONFIG.embedding_max_length_query,
                    return_dense=True,
                    return_sparse=CONFIG.use_sparse,
                    return_colbert=False,  # Not needed for search
                    context="query"
                )

                # Extract results
                q_dense = embedding_result['dense_vecs'][0] if embedding_result.get('dense_vecs') else []

                q_sparse = {"indices": [], "values": []}
                if CONFIG.use_sparse and embedding_result.get('lexical_weights'):
                    lex_weights = embedding_result['lexical_weights'][0]
                    if lex_weights and isinstance(lex_weights, dict):  # Check if not empty and is dict
                        # Convert BGE-M3 lexical_weights format to Qdrant format
                        indices = [int(k) for k in lex_weights.keys()]  # Ensure integers
                        values = [float(lex_weights[k]) for k in lex_weights.keys()]  # Ensure floats
                        q_sparse = {
                            "indices": indices,
                            "values": values
                        }

                embedding_duration = time.time() - embedding_start
                logger.info(f"Unified embeddings (dense+sparse) in {embedding_duration:.2f}s")
                metrics.record_embedding_duration("unified", embedding_duration)

            else:
                # Legacy separate embedding generation (ONNX-only mode)
                q_dense = embed_dense_optimized(normalized, max_length=CONFIG.embedding_max_length_query)
                embedding_duration_dense = time.time() - embedding_start
                metrics.record_embedding_duration("dense", embedding_duration_dense)

                if CONFIG.use_sparse:
                    sparse_start = time.time()
                    q_sparse = embed_sparse_optimized(normalized, max_length=CONFIG.embedding_max_length_query)
                    sparse_duration = time.time() - sparse_start
                    metrics.record_embedding_duration("sparse", sparse_duration)
                else:
                    q_sparse = {"indices": [], "values": []}

                embedding_duration = time.time() - embedding_start
                logger.info(f"Legacy embeddings in {embedding_duration:.2f}s")

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            error_type = "embedding_failed"
            metrics.record_error("embedding_failed", "embedding_generation")
            log_data["status"] = "error"
            log_data["error_type"] = "embedding_failed"
            timings["total"] = time.time() - start
            _finalize_query_log(log_data, timings)
            return {
                "error": "embedding_failed",
                "message": "Сервис эмбеддингов временно недоступен. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }
        metrics.record_query_duration("embeddings", embedding_duration)
        timings["embeddings"] = embedding_duration

        # 3. Hybrid Search
        try:
            search_start = time.time()
            candidates = hybrid_search(
                q_dense,
                q_sparse,
                k=20,
                boosts=boosts,
                group_boosts=group_boosts,
                routing_result=routing_result,
                metadata_filter=theme_filter,
            )
            search_duration = time.time() - search_start
            logger.info(f"Hybrid search in {search_duration:.2f}s")
            metrics.record_search_duration("hybrid", search_duration)
            metrics.record_query_duration("search", search_duration)
            timings["search"] = search_duration

            # Fallback: если поиск с фильтром не дал результатов, пробуем без фильтра
            if not candidates and theme_filter is not None:
                logger.warning("No candidates found with theme filter, trying without filter")
                search_start = time.time()
                candidates = hybrid_search(
                    q_dense,
                    q_sparse,
                    k=20,
                    boosts=boosts,
                    group_boosts=group_boosts,
                    routing_result=routing_result,
                    metadata_filter=None,
                )
                search_duration = time.time() - search_start
                logger.info(f"Hybrid search (without filter) in {search_duration:.2f}s")
                metrics.record_search_duration("hybrid_no_filter", search_duration)
                metrics.record_query_duration("search_no_filter", search_duration)
                timings["search_no_filter"] = search_duration
                log_data["search"]["fallback_without_filter"] = True
                if candidates:
                    logger.info(f"Found {len(candidates)} candidates without theme filter")

            candidate_count = len(candidates) if candidates else 0
            log_data["search"]["candidates_total"] = candidate_count
            log_data["search"]["candidates_before_theme_boost"] = _prepare_log_candidates(
                candidates or [],
                max_log_candidates,
                text_prefix_len,
            )

            if not candidates:
                logger.warning("No candidates found in search")
                error_type = "no_results"
                metrics.record_error("no_results", "search")
                log_data["status"] = "no_results"
                log_data["error_type"] = "no_results"
                timings["total"] = time.time() - start
                _finalize_query_log(log_data, timings)
                return {
                    "error": "no_results",
                    "message": "К сожалению, не удалось найти релевантную информацию по вашему запросу. Попробуйте переформулировать вопрос или использовать другие ключевые слова.",
                    "answer": "К сожалению, не удалось найти релевантную информацию по вашему запросу. Попробуйте переформулировать вопрос или использовать другие ключевые слова.",
                    "answer_markdown": "К сожалению, не удалось найти релевантную информацию по вашему запросу. Попробуйте переформулировать вопрос или использовать другие ключевые слова.",
                    "sources": [],
                    "channel": channel,
                    "chat_id": chat_id
                }
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            error_type = "search_failed"
            metrics.record_error("search_failed", "hybrid_search")
            log_data["status"] = "error"
            log_data["error_type"] = "search_failed"
            timings["total"] = time.time() - start
            _finalize_query_log(log_data, timings)
            return {
                "error": "search_failed",
                "message": "Ошибка поиска в базе знаний. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        candidates = _apply_theme_boost(candidates, routing_result)
        log_data["search"]["candidates_after_theme_boost"] = _prepare_log_candidates(
            candidates,
            max_log_candidates,
            text_prefix_len,
        )

        # 5. Reranking
        rerank_start = time.time()
        try:
            # Пакетная обработка reranker: batch_size=20, усечение текста до 384 симв.
            top_docs = rerank(normalized, candidates, top_n=6, batch_size=20, max_length=384)  # Оптимизировано по Codex
            rerank_duration = time.time() - rerank_start
            logger.info(f"Rerank completed in {rerank_duration:.2f}s")
            metrics.record_query_duration("rerank", rerank_duration)
            timings["rerank"] = rerank_duration
        except Exception as e:
            rerank_duration = time.time() - rerank_start
            logger.warning(f"Reranking failed after {rerank_duration:.2f}s: {e}, using original candidates")
            metrics.record_query_duration("rerank", rerank_duration)
            timings["rerank"] = rerank_duration
            top_docs = candidates[:6]  # Согласованно с оптимизацией

        log_data["search"]["candidates_after_rerank"] = _prepare_log_candidates(
            top_docs,
            max_log_candidates,
            text_prefix_len,
        )

        # 5b. Авто-слияние соседних чанков на этапе выдачи
        if CONFIG.retrieval_auto_merge_enabled and top_docs:
            try:
                max_ctx_tokens = getattr(context_optimizer, "max_context_tokens", CONFIG.retrieval_auto_merge_max_tokens)
                reserve = getattr(context_optimizer, "reserve_for_response", 0.35)
                available = max(1, int(max_ctx_tokens * (1 - reserve)))
                merge_limit = min(CONFIG.retrieval_auto_merge_max_tokens, available)
            except Exception:
                merge_limit = CONFIG.retrieval_auto_merge_max_tokens

            merged_docs = auto_merge_neighbors(top_docs, max_window_tokens=merge_limit)
            log_data["context"]["auto_merge_before"] = len(top_docs)
            if merged_docs != top_docs:
                reduction = len(top_docs) - len(merged_docs)
                efficiency = 100 * (1 - len(merged_docs) / len(top_docs)) if top_docs else 0
                logger.debug(
                    f"Auto-merge: {len(top_docs)} -> {len(merged_docs)} окон "
                    f"(лимит={merge_limit} токенов, экономия={reduction} чанков, эффективность={efficiency:.1f}%)"
                )
                log_data["context"]["auto_merge_applied"] = True
                log_data["context"]["auto_merge_after"] = len(merged_docs)
            top_docs = merged_docs
            log_data["context"].setdefault("auto_merge_after", len(top_docs))
        else:
            log_data["context"]["auto_merge_before"] = len(top_docs) if top_docs else 0
            log_data["context"]["auto_merge_after"] = len(top_docs) if top_docs else 0

        # 6. Context Optimization - управление размером токенов для LLM
        context_start = time.time()
        try:
            optimized_docs = context_optimizer.optimize_context(normalized, top_docs)
            context_duration = time.time() - context_start
            logger.info(f"Context optimized: {len(top_docs)} -> {len(optimized_docs)} documents in {context_duration:.2f}s")
            metrics.record_query_duration("context_optimization", context_duration)
            timings["context_optimization"] = context_duration
        except Exception as e:
            context_duration = time.time() - context_start
            logger.warning(f"Context optimization failed after {context_duration:.2f}s: {e}, using original documents")
            metrics.record_query_duration("context_optimization", context_duration)
            timings["context_optimization"] = context_duration
            optimized_docs = top_docs
        log_data["context"]["optimized_docs"] = len(optimized_docs) if optimized_docs else 0

        # 7. LLM Generation
        _attach_theme_labels(top_docs)

        theme_instruction = _build_theme_instruction(routing_result)

        try:
            llm_start = time.time()
            policy: Dict[str, Any] = {}
            if theme_instruction:
                policy["theme_instruction"] = theme_instruction
            answer_payload = generate_answer(normalized, optimized_docs, policy=policy)
            llm_duration = time.time() - llm_start
            logger.info(f"LLM generation in {llm_duration:.2f}s")
            metrics.record_llm_duration("default", llm_duration)
            metrics.record_query_duration("llm_generation", llm_duration)
            timings["llm_generation"] = llm_duration
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            error_type = "llm_failed"
            metrics.record_error("llm_failed", "llm_generation")
            llm_duration = time.time() - llm_start
            metrics.record_query_duration("llm_generation", llm_duration)
            timings["llm_generation"] = llm_duration
            log_data["status"] = "error"
            log_data["error_type"] = "llm_failed"
            timings["total"] = time.time() - start
            _finalize_query_log(log_data, timings)
            return {
                "error": "llm_failed",
                "message": "Сервис генерации ответов временно недоступен. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        total_time = time.time() - start
        logger.info(f"Total processing time: {total_time:.2f}s")

        # Записываем метрики успешного запроса
        metrics.record_query(channel, status, error_type)
        metrics.record_query_duration("total", total_time)
        metrics.record_search_results("hybrid", len(candidates))

        # Создаем quality interaction асинхронно в фоне (неблокирующе)
        interaction_id = None
        if CONFIG.enable_ragas_evaluation:
            try:
                # Подготавливаем данные для quality evaluation
                contexts = [doc.get("payload", {}).get("text", "") for doc in top_docs]
                source_urls = [source.get("url", "") for source in answer_payload.get("sources", [])]
                interaction_id = quality_manager.generate_interaction_id()

                # Запускаем RAGAS оценку в фоне через ThreadPoolExecutor
                import concurrent.futures
                import threading

                def run_ragas_evaluation():
                    """Запускает RAGAS оценку в отдельном event loop"""
                    try:
                        # Создаем новый event loop для этого потока
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        # Запускаем оценку
                        result = loop.run_until_complete(quality_manager.evaluate_interaction(
                            query=normalized,
                            response=answer_payload.get("answer_markdown", ""),
                            contexts=contexts,
                            sources=source_urls,
                            interaction_id=interaction_id
                        ))
                        return result
                    except Exception as e:
                        logger.error(f"RAGAS evaluation failed in background: {e}")
                        return None
                    finally:
                        try:
                            if not loop.is_closed():
                                # Аккуратно закрываем loop, завершая оставшиеся таски
                                pending = asyncio.all_tasks(loop=loop)
                                for task in pending:
                                    task.cancel()
                                if pending:
                                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                                loop.close()
                        except Exception as close_err:
                            logger.warning(f"Error while closing RAGAS loop: {close_err}")

                # Запускаем в фоне
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_ragas_evaluation)
                    # Не ждем результат - это должно быть неблокирующим
                    logger.info(f"RAGAS evaluation started in background (interaction_id={interaction_id})")

            except Exception as e:
                logger.warning(f"Failed to start quality interaction: {e}")

        answer_markdown = answer_payload.get("answer_markdown", "")
        sources = answer_payload.get("sources", [])
        meta = answer_payload.get("meta", {})
        log_data["answer"] = {
            "text": answer_markdown,
            "sources": sources,
            "meta": meta,
        }
        log_data["status"] = "success"
        log_data["error_type"] = None
        timings["total"] = total_time
        _finalize_query_log(log_data, timings)

        return {
            "answer": answer_markdown,  # временная совместимость с клиентами
            "answer_markdown": answer_markdown,
            "sources": sources,
            "meta": meta,
            "channel": channel,
            "chat_id": chat_id,
            "processing_time": total_time,
            "interaction_id": interaction_id
        }

    except Exception as e:
        logger.error(f"Unexpected error in handle_query: {e}", exc_info=True)

        # Записываем метрики ошибки
        error_type = type(e).__name__
        status = "error"
        metrics.record_query(channel, status, error_type)
        metrics.record_error(error_type, "orchestrator")
        log_data["status"] = "error"
        log_data["error_type"] = error_type
        timings["total"] = time.time() - start
        _finalize_query_log(log_data, timings)

        return {
            "error": "internal_error",
            "message": "Произошла внутренняя ошибка. Попробуйте позже или обратитесь в поддержку.",
            "sources": [],
            "channel": channel,
            "chat_id": chat_id
        }


def _build_theme_filter(routing_result: Dict[str, Any] | None) -> Optional[Filter]:
    if not routing_result:
        return None
    if not _is_theme_filter_allowed(routing_result):
        return None
    primary_theme = routing_result.get("primary_theme")
    if not primary_theme:
        return None
    theme = get_theme(primary_theme)
    if not theme:
        return None
    conditions = []
    if theme.domain:
        conditions.append(FieldCondition(key="domain", match=MatchValue(value=theme.domain)))
    if theme.section:
        conditions.append(FieldCondition(key="section", match=MatchValue(value=theme.section)))
    if theme.platform:
        conditions.append(FieldCondition(key="platform", match=MatchValue(value=theme.platform)))
    if theme.role:
        conditions.append(FieldCondition(key="role", match=MatchValue(value=theme.role)))
    if not conditions:
        return None
    return Filter(must=conditions)


def _is_theme_filter_allowed(routing_result: Dict[str, Any]) -> bool:
    router_kind = routing_result.get("router")
    top_score = float(routing_result.get("top_score") or 0.0)
    second_score = float(routing_result.get("second_score") or 0.0)
    if router_kind == "llm":
        return top_score >= 0.9
    if router_kind == "heuristic":
        return top_score >= 0.85 and (top_score - second_score) >= 0.35
    return False


def _build_theme_instruction(routing_result: Dict[str, Any] | None) -> Optional[str]:
    if not routing_result:
        return None
    themes = routing_result.get("themes", [])[:2]
    if len(themes) < 2:
        return None
    names = []
    for theme_id in themes:
        theme = get_theme(theme_id)
        if theme:
            names.append(theme.display_name)
    if len(names) < 2:
        return None
    return (
        "Если ответ затрагивает несколько тематик, сформируй отдельные разделы "
        f"соответственно: {', '.join(names)}."
    )


def _attach_theme_labels(docs: List[Dict[str, Any]]) -> None:
    for doc in docs:
        payload = doc.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("theme_label"):
            continue
        label = infer_theme_label(payload)
        if label:
            payload["theme_label"] = label


def _apply_theme_boost(docs: List[Dict[str, Any]], routing_result: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    if not docs or not routing_result:
        return docs
    primary_theme = routing_result.get("primary_theme")
    if not primary_theme:
        return docs
    secondary_themes = routing_result.get("themes", [])[1:3]
    for doc in docs:
        payload = doc.get("payload") or {}
        theme_id = infer_theme_id(payload)
        if not theme_id:
            continue
        base_score = doc.get("boosted_score", doc.get("score", 0.0))
        if theme_id == primary_theme:
            doc["boosted_score"] = base_score + 0.08
        elif theme_id in secondary_themes:
            doc["boosted_score"] = base_score + 0.04
        else:
            doc.setdefault("boosted_score", base_score)
    docs.sort(key=lambda item: item.get("boosted_score", item.get("score", 0.0)), reverse=True)
    return docs


def _init_query_log(channel: str, chat_id: str, raw_message: str) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "chat_id": chat_id,
        "status": "pending",
        "error_type": None,
        "request": {
            "raw": raw_message,
            "normalized": None,
            "boosts": {},
            "group_boosts": {},
        },
        "routing": None,
        "search": {
            "theme_filter_applied": False,
            "theme_filter_conditions": [],
            "fallback_without_filter": False,
            "candidates_total": 0,
            "candidates_before_theme_boost": [],
            "candidates_after_theme_boost": [],
            "candidates_after_rerank": [],
        },
        "context": {
            "auto_merge_enabled": CONFIG.retrieval_auto_merge_enabled,
            "auto_merge_applied": False,
            "auto_merge_before": 0,
            "auto_merge_after": 0,
            "optimized_docs": 0,
        },
        "answer": {},
        "timings": {},
    }


def _serialize_routing_result(routing_result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not routing_result:
        return None
    return {
        "router": routing_result.get("router"),
        "primary_theme": routing_result.get("primary_theme"),
        "themes": routing_result.get("themes", []),
        "top_score": routing_result.get("top_score"),
        "second_score": routing_result.get("second_score"),
        "requires_disambiguation": routing_result.get("requires_disambiguation", False),
        "ambiguous_themes": routing_result.get("ambiguous_themes", []),
    }


def _describe_theme_filter(theme_filter: Optional[Filter]) -> List[Dict[str, Any]]:
    if not theme_filter or not getattr(theme_filter, "must", None):
        return []
    description: List[Dict[str, Any]] = []
    for condition in theme_filter.must:
        if isinstance(condition, FieldCondition):
            value = None
            match = getattr(condition, "match", None)
            if isinstance(match, MatchValue):
                value = match.value
            description.append(
                {
                    "field": condition.key,
                    "value": value,
                }
            )
    return description


def _prepare_log_candidates(
    candidates: List[Dict[str, Any]],
    max_count: int,
    text_prefix_len: int,
) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    skip_fields = {
        "vector",
        "dense_vector",
        "sparse_vector",
        "embedding",
        "dense_embeddings",
        "sparse_embeddings",
        "lexical_weights",
        "sparse_data",
        "sparse",
        "sparse_values",
        "sparse_indices",
    }

    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    prepared: List[Dict[str, Any]] = []
    for doc in candidates[:max(0, max_count)]:
        payload = doc.get("payload") or {}
        metadata = {k: v for k, v in payload.items() if k not in skip_fields and k != "text"}
        text_value = payload.get("text", "")
        if not isinstance(text_value, str):
            text_value = str(text_value) if text_value is not None else ""
        entry = {
            "id": doc.get("id") or doc.get("point_id") or metadata.get("chunk_id") or metadata.get("doc_id"),
            "score": _to_float(doc.get("score")),
            "boosted_score": _to_float(doc.get("boosted_score")),
            "metadata": metadata,
            "text_prefix": text_value[:max(0, text_prefix_len)],
        }
        prepared.append(entry)
    return prepared


def _finalize_query_log(log_data: Dict[str, Any], timings: Dict[str, Optional[float]]) -> None:
    try:
        log_data["timings"] = {
            name: round(value, 4)
            for name, value in (timings or {}).items()
            if value is not None
        }
        if not log_data.get("timestamp"):
            log_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_query_interaction(log_data)
    except Exception as exc:
        logger.warning(f"Failed to finalize query log: {exc}")
