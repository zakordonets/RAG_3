from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    # Qdrant
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "chatcenter_docs")
    qdrant_grpc: bool = os.getenv("QDRANT_GRPC", "false").lower() in ("1", "true", "yes")
    qdrant_hnsw_m: int = int(os.getenv("QDRANT_HNSW_M", "16"))
    qdrant_hnsw_ef_construct: int = int(os.getenv("QDRANT_HNSW_EF_CONSTRUCT", "200"))
    qdrant_hnsw_ef_search: int = int(os.getenv("QDRANT_HNSW_EF_SEARCH", "200"))
    qdrant_hnsw_full_scan_threshold: int = int(os.getenv("QDRANT_HNSW_FULL_SCAN_THRESHOLD", "10000"))

    # Embeddings - Legacy (Ollama)
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    embedding_model_type: str = os.getenv("EMBEDDING_MODEL_TYPE", "BGE-M3")
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3:latest")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1024"))

    # BGE-M3 Embeddings Configuration
    embeddings_backend: str = os.getenv("EMBEDDINGS_BACKEND", "auto").lower()  # auto|onnx|bge|hybrid
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "auto").lower()  # auto|cpu|cuda|directml
    embedding_max_length_query: int = int(os.getenv("EMBEDDING_MAX_LENGTH_QUERY", "512"))
    embedding_max_length_doc: int = int(os.getenv("EMBEDDING_MAX_LENGTH_DOC", "1024"))
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
    embedding_normalize: bool = os.getenv("EMBEDDING_NORMALIZE", "true").lower() in ("1", "true", "yes")
    embedding_use_colbert: bool = os.getenv("EMBEDDING_USE_COLBERT", "false").lower() in ("1", "true", "yes")
    embedding_use_fp16: bool = os.getenv("EMBEDDING_USE_FP16", "true").lower() in ("1", "true", "yes")

    # Sparse service
    sparse_service_url: str = os.getenv("SPARSE_SERVICE_URL", "http://localhost:8001")
    use_sparse: bool = os.getenv("USE_SPARSE", "true").lower() in ("1", "true", "yes")

    # Retrieval/rerank
    hybrid_dense_weight: float = float(os.getenv("HYBRID_DENSE_WEIGHT", "0.5"))
    hybrid_sparse_weight: float = float(os.getenv("HYBRID_SPARSE_WEIGHT", "0.5"))
    rrf_k: int = int(os.getenv("RRF_K", "60"))
    rerank_top_n: int = int(os.getenv("RERANK_TOP_N", "10"))
    reranker_model: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    reranker_device: str = os.getenv("RERANKER_DEVICE", "cpu")
    reranker_threads: int = int(os.getenv("RERANKER_THREADS", "12"))

    # GPU Configuration
    gpu_enabled: bool = os.getenv("GPU_ENABLED", "false").lower() == "true"
    gpu_device: int = int(os.getenv("GPU_DEVICE", "0"))
    gpu_memory_fraction: float = float(os.getenv("GPU_MEMORY_FRACTION", "0.8"))

    # ONNX Runtime provider selection: auto|dml|cpu
    onnx_provider: str = os.getenv("ONNX_PROVIDER", "auto").lower()

    # LLMs
    default_llm: str = os.getenv("DEFAULT_LLM", "YANDEX").upper()
    deepseek_api_url: str = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    gpt5_api_url: str = os.getenv("GPT5_API_URL", "")
    gpt5_api_key: str = os.getenv("GPT5_API_KEY", "")
    gpt5_model: str = os.getenv("GPT5_MODEL", "")
    yandex_api_url: str = os.getenv("YANDEX_API_URL", "https://llm.api.cloud.yandex.net/v1")
    yandex_catalog_id: str = os.getenv("YANDEX_CATALOG_ID", "")
    yandex_api_key: str = os.getenv("YANDEX_API_KEY", "")
    yandex_model: str = os.getenv("YANDEX_MODEL", "yandexgpt")
    yandex_max_tokens: int = int(os.getenv("YANDEX_MAX_TOKENS", "4000"))

    # Telegram
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_poll_interval: float = float(os.getenv("TELEGRAM_POLL_INTERVAL", "1.0"))

    # Caching
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() in ("1", "true", "yes")

    # Ingestion
    crawl_start_url: str = os.getenv("CRAWL_START_URL", "https://docs-chatcenter.edna.ru/")
    crawl_concurrency: int = int(os.getenv("CRAWL_CONCURRENCY", "8"))
    crawl_timeout_s: int = int(os.getenv("CRAWL_TIMEOUT_S", "30"))
    crawl_max_pages: int = int(os.getenv("CRAWL_MAX_PAGES", "0"))  # 0 = без лимита
    crawl_delay_ms: int = int(os.getenv("CRAWL_DELAY_MS", "800"))
    crawl_jitter_ms: int = int(os.getenv("CRAWL_JITTER_MS", "400"))
    crawl_deny_prefixes: list[str] = field(default_factory=lambda: [p.strip() for p in os.getenv("CRAWL_DENY_PREFIXES", "/docs/api/").split(",") if p.strip()])
    chunk_min_tokens: int = int(os.getenv("CHUNK_MIN_TOKENS", "120"))
    chunk_max_tokens: int = int(os.getenv("CHUNK_MAX_TOKENS", "600"))


CONFIG = AppConfig()
