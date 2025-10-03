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

    # Embeddings Configuration
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1024"))

    # BGE-M3 Embeddings Configuration
    embeddings_backend: str = os.getenv("EMBEDDINGS_BACKEND", "auto").lower()  # auto|onnx|bge|hybrid
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "auto").lower()  # auto|cpu|cuda|directml
    embedding_max_length_query: int = int(os.getenv("EMBEDDING_MAX_LENGTH_QUERY", "512"))
    embedding_max_length_doc: int = int(os.getenv("EMBEDDING_MAX_LENGTH_DOC", "2048"))
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
    sparse_batch_size: int = int(os.getenv("SPARSE_BATCH_SIZE", "32"))
    dense_batch_size: int = int(os.getenv("DENSE_BATCH_SIZE", "16"))
    adaptive_batching: bool = os.getenv("ADAPTIVE_BATCHING", "true").lower() in ("1", "true", "yes")
    embedding_normalize: bool = os.getenv("EMBEDDING_NORMALIZE", "true").lower() in ("1", "true", "yes")
    embedding_use_colbert: bool = os.getenv("EMBEDDING_USE_COLBERT", "false").lower() in ("1", "true", "yes")
    embedding_use_fp16: bool = os.getenv("EMBEDDING_USE_FP16", "true").lower() in ("1", "true", "yes")

    # Sparse vectors configuration (handled by BGE-M3)
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
    yandex_api_url: str = os.getenv("YANDEX_API_URL", "https://llm.api.cloud.yandex.net/foundationModels/v1")
    yandex_catalog_id: str = os.getenv("YANDEX_CATALOG_ID", "")
    yandex_api_key: str = os.getenv("YANDEX_API_KEY", "")
    yandex_model: str = os.getenv("YANDEX_MODEL", "yandexgpt/rc")
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
    chunk_min_tokens: int = int(os.getenv("CHUNK_MIN_TOKENS", "410"))  # 512 - 20% для BGE-M3
    chunk_max_tokens: int = int(os.getenv("CHUNK_MAX_TOKENS", "500"))  # Оптимизировано по рекомендациям Codex

    # Chunking strategy selection
    chunk_strategy: str = os.getenv("CHUNK_STRATEGY", "adaptive").lower()  # adaptive|simple

    # Adaptive chunker parameters
    adaptive_short_threshold: int = int(os.getenv("ADAPTIVE_SHORT_THRESHOLD", "300"))
    adaptive_long_threshold: int = int(os.getenv("ADAPTIVE_LONG_THRESHOLD", "1000"))
    adaptive_medium_size: int = int(os.getenv("ADAPTIVE_MEDIUM_SIZE", "512"))
    adaptive_medium_overlap: int = int(os.getenv("ADAPTIVE_MEDIUM_OVERLAP", "100"))
    adaptive_long_size: int = int(os.getenv("ADAPTIVE_LONG_SIZE", "800"))
    adaptive_long_overlap: int = int(os.getenv("ADAPTIVE_LONG_OVERLAP", "160"))
    adaptive_merge_short_paragraph_tokens: int = int(os.getenv("ADAPTIVE_MERGE_SHORT_PARAGRAPH_TOKENS", "50"))
    adaptive_chunk_min_merge_tokens: int = int(os.getenv("ADAPTIVE_CHUNK_MIN_MERGE_TOKENS", "50"))

    # RAGAS Quality Evaluation
    enable_ragas_evaluation: bool = os.getenv("ENABLE_RAGAS_EVALUATION", "false").lower() in ("1", "true", "yes")
    ragas_evaluation_sample_rate: float = float(os.getenv("RAGAS_EVALUATION_SAMPLE_RATE", "0.2"))
    ragas_batch_size: int = int(os.getenv("RAGAS_BATCH_SIZE", "5"))
    ragas_async_timeout: int = int(os.getenv("RAGAS_ASYNC_TIMEOUT", "60"))
    ragas_llm_model: str = os.getenv("RAGAS_LLM_MODEL", "yandexgpt")

    # Document Boosting Configuration
    boost_overview_docs: float = float(os.getenv("BOOST_OVERVIEW_DOCS", "1.4"))
    boost_faq_guides: float = float(os.getenv("BOOST_FAQ_GUIDES", "1.2"))
    boost_technical_docs: float = float(os.getenv("BOOST_TECHNICAL_DOCS", "1.1"))
    boost_release_notes: float = float(os.getenv("BOOST_RELEASE_NOTES", "0.8"))
    boost_well_structured: float = float(os.getenv("BOOST_WELL_STRUCTURED", "1.15"))
    boost_optimal_length: float = float(os.getenv("BOOST_OPTIMAL_LENGTH", "1.2"))
    boost_reliable_source: float = float(os.getenv("BOOST_RELIABLE_SOURCE", "1.1"))

    # Quality Database
    quality_db_enabled: bool = os.getenv("QUALITY_DB_ENABLED", "false").lower() in ("1", "true", "yes")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/rag_quality")

    # Enhanced Chunker Configuration
    semantic_chunker_model: str = os.getenv("SEMANTIC_CHUNKER_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    semantic_chunker_threshold: float = float(os.getenv("SEMANTIC_CHUNKER_THRESHOLD", "0.7"))
    semantic_chunker_overlap_size: int = int(os.getenv("SEMANTIC_CHUNKER_OVERLAP_SIZE", "50"))

    # Enhanced Crawler Configuration
    crawler_strategy: str = os.getenv("CRAWLER_STRATEGY", "jina")  # jina|http|browser
    crawler_max_retries: int = int(os.getenv("CRAWLER_MAX_RETRIES", "3"))
    crawler_backoff_factor: float = float(os.getenv("CRAWLER_BACKOFF_FACTOR", "1.5"))
    crawler_rate_limit_requests_per_second: float = float(os.getenv("CRAWLER_RATE_LIMIT_RPS", "2.0"))
    crawler_rate_limit_burst: int = int(os.getenv("CRAWLER_RATE_LIMIT_BURST", "5"))
    max_crawl_duration_minutes: int = int(os.getenv("MAX_CRAWL_DURATION_MINUTES", "60"))

    # Quality and Validation Settings
    min_chunk_words: int = int(os.getenv("MIN_CHUNK_WORDS", "5"))
    max_paragraph_tokens: int = int(os.getenv("MAX_PARAGRAPH_TOKENS", "1000"))
    deduplication_enabled: bool = os.getenv("DEDUPLICATION_ENABLED", "true").lower() in ("1", "true", "yes")

    # Security and Limits
    max_page_size_mb: int = int(os.getenv("MAX_PAGE_SIZE_MB", "10"))
    max_total_pages: int = int(os.getenv("MAX_TOTAL_PAGES", "10000"))
    max_memory_usage_mb: int = int(os.getenv("MAX_MEMORY_USAGE_MB", "2048"))

    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_config()

    def _validate_config(self):
        """Validate critical configuration parameters"""
        errors = []

        # Validate chunk configuration
        if self.chunk_min_tokens >= self.chunk_max_tokens:
            errors.append("chunk_min_tokens must be less than chunk_max_tokens")

        if self.chunk_min_tokens <= 0:
            errors.append("chunk_min_tokens must be positive")

        # Validate embedding configuration
        if self.embedding_max_length_doc <= 0:
            errors.append("embedding_max_length_doc must be positive")

        if self.embedding_batch_size <= 0:
            errors.append("embedding_batch_size must be positive")

        # Validate crawler configuration
        if self.crawler_strategy not in ["jina", "http", "browser"]:
            errors.append("crawler_strategy must be one of: jina, http, browser")

        if self.crawler_max_retries < 0:
            errors.append("crawler_max_retries must be non-negative")

        if self.crawler_rate_limit_requests_per_second <= 0:
            errors.append("crawler_rate_limit_requests_per_second must be positive")

        # Validate limits
        if self.max_page_size_mb <= 0:
            errors.append("max_page_size_mb must be positive")

        if self.max_total_pages <= 0:
            errors.append("max_total_pages must be positive")

        # Validate semantic chunker
        if not (0.0 <= self.semantic_chunker_threshold <= 1.0):
            errors.append("semantic_chunker_threshold must be between 0.0 and 1.0")

        if self.semantic_chunker_overlap_size < 0:
            errors.append("semantic_chunker_overlap_size must be non-negative")

        # Validate boost factors
        if self.boost_overview_docs <= 0:
            errors.append("boost_overview_docs must be positive")

        if self.boost_release_notes <= 0:
            errors.append("boost_release_notes must be positive")

        # Validate chunk strategy
        if self.chunk_strategy not in ["adaptive", "simple"]:
            errors.append("chunk_strategy must be one of: adaptive, simple")

        # Validate adaptive thresholds
        if self.adaptive_short_threshold <= 0 or self.adaptive_long_threshold <= 0:
            errors.append("adaptive thresholds must be positive")
        if self.adaptive_short_threshold >= self.adaptive_long_threshold:
            errors.append("ADAPTIVE_SHORT_THRESHOLD must be less than ADAPTIVE_LONG_THRESHOLD")
        if self.adaptive_medium_size <= 0 or self.adaptive_long_size <= 0:
            errors.append("adaptive chunk sizes must be positive")
        if self.adaptive_medium_overlap < 0 or self.adaptive_long_overlap < 0:
            errors.append("adaptive overlaps must be non-negative")
        if self.adaptive_merge_short_paragraph_tokens < 0:
            errors.append("ADAPTIVE_MERGE_SHORT_PARAGRAPH_TOKENS must be non-negative")

        # Raise validation errors
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)

    # Quality Metrics
    enable_quality_metrics: bool = os.getenv("ENABLE_QUALITY_METRICS", "false").lower() in ("1", "true", "yes")
    quality_prediction_threshold: float = float(os.getenv("QUALITY_PREDICTION_THRESHOLD", "0.7"))


CONFIG = AppConfig()
