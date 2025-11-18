from __future__ import annotations
import time
import asyncio
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
from app.services.quality.quality_manager import quality_manager
from app.retrieval import route_query
from app.retrieval.theme_router import get_theme, infer_theme_label


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

    # Инициализация метрик
    error_type = None
    status = "success"

    try:
        # 1. Query Processing
        try:
            qp = process_query(message)
            normalized = qp["normalized_text"]
            boosts = qp.get("boosts", {})
            group_boosts = qp.get("group_boosts", {})
            logger.info(f"Query processed in {time.time() - start:.2f}s")
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "error": "query_processing_failed",
                "message": "Ошибка обработки запроса. Попробуйте переформулировать вопрос.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        routing_result = route_query(normalized, user_metadata=None)
        theme_filter = _build_theme_filter(routing_result)
        if routing_result.get("requires_disambiguation"):
            clarification = _build_clarification_message(routing_result)
            return {
                "answer_markdown": clarification,
                "sources": [],
                "channel": channel,
                "chat_id": chat_id,
                "clarification_required": True,
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
                get_metrics_collector().record_embedding_duration("unified", embedding_duration)

            else:
                # Legacy separate embedding generation (ONNX-only mode)
                q_dense = embed_dense_optimized(normalized, max_length=CONFIG.embedding_max_length_query)
                embedding_duration_dense = time.time() - embedding_start
                get_metrics_collector().record_embedding_duration("dense", embedding_duration_dense)

                if CONFIG.use_sparse:
                    sparse_start = time.time()
                    q_sparse = embed_sparse_optimized(normalized, max_length=CONFIG.embedding_max_length_query)
                    sparse_duration = time.time() - sparse_start
                    get_metrics_collector().record_embedding_duration("sparse", sparse_duration)
                else:
                    q_sparse = {"indices": [], "values": []}

                embedding_duration = time.time() - embedding_start
                logger.info(f"Legacy embeddings in {embedding_duration:.2f}s")

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            error_type = "embedding_failed"
            get_metrics_collector().record_error("embedding_failed", "embedding_generation")
            return {
                "error": "embedding_failed",
                "message": "Сервис эмбеддингов временно недоступен. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

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
            get_metrics_collector().record_search_duration("hybrid", search_duration)

            if not candidates:
                logger.warning("No candidates found in search")
                error_type = "no_results"
                get_metrics_collector().record_error("no_results", "search")
                return {
                    "error": "no_results",
                    "message": "К сожалению, не удалось найти релевантную информацию по вашему запросу. Попробуйте переформулировать вопрос или использовать другие ключевые слова.",
                    "sources": [],
                    "channel": channel,
                    "chat_id": chat_id
                }
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            error_type = "search_failed"
            get_metrics_collector().record_error("search_failed", "hybrid_search")
            return {
                "error": "search_failed",
                "message": "Ошибка поиска в базе знаний. Попробуйте позже.",
                "sources": [],
                "channel": channel,
                "chat_id": chat_id
            }

        # 5. Reranking
        try:
            # Пакетная обработка reranker: batch_size=20, усечение текста до 384 симв.
            top_docs = rerank(normalized, candidates, top_n=6, batch_size=20, max_length=384)  # Оптимизировано по Codex
            logger.info(f"Rerank in {time.time() - start:.2f}s")
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, using original candidates")
            top_docs = candidates[:6]  # Согласованно с оптимизацией

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
            if merged_docs != top_docs:
                reduction = len(top_docs) - len(merged_docs)
                efficiency = 100 * (1 - len(merged_docs) / len(top_docs)) if top_docs else 0
                logger.debug(
                    f"Auto-merge: {len(top_docs)} -> {len(merged_docs)} окон "
                    f"(лимит={merge_limit} токенов, экономия={reduction} чанков, эффективность={efficiency:.1f}%)"
                )
            top_docs = merged_docs

        # 6. Context Optimization - управление размером токенов для LLM
        try:
            optimized_docs = context_optimizer.optimize_context(normalized, top_docs)
            logger.info(f"Context optimized: {len(top_docs)} -> {len(optimized_docs)} documents")
        except Exception as e:
            logger.warning(f"Context optimization failed: {e}, using original documents")
            optimized_docs = top_docs

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
            get_metrics_collector().record_llm_duration("default", llm_duration)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            error_type = "llm_failed"
            get_metrics_collector().record_error("llm_failed", "llm_generation")
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
        get_metrics_collector().record_query(channel, status, error_type)
        get_metrics_collector().record_query_duration("total", total_time)
        get_metrics_collector().record_search_results("hybrid", len(candidates))

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
        get_metrics_collector().record_query(channel, status, error_type)
        get_metrics_collector().record_error(error_type, "orchestrator")

        return {
            "error": "internal_error",
            "message": "Произошла внутренняя ошибка. Попробуйте позже или обратитесь в поддержку.",
            "sources": [],
            "channel": channel,
            "chat_id": chat_id
        }


def _build_theme_filter(routing_result: Dict[str, Any] | None) -> Optional[Filter]:
    if not routing_result or routing_result.get("requires_disambiguation"):
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


def _build_clarification_message(routing_result: Dict[str, Any]) -> str:
    themes = routing_result.get("themes", [])[:3]
    if not themes:
        return "Нужно уточнить, какую тематику вы имеете в виду."
    lines = ["Я нашёл несколько тематик, уточните, что вам нужно:"]
    for idx, theme_id in enumerate(themes, start=1):
        theme = get_theme(theme_id)
        if theme:
            lines.append(f"{idx}. {theme.display_name}")
    return "\n".join(lines)


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
