#!/usr/bin/env python3
"""
Optimized pipeline with abstractions and improved architecture
"""

from __future__ import annotations

import time
from typing import List, Dict, Any, Optional
from loguru import logger
from tqdm import tqdm

from app.abstractions.data_source import DataSourceBase, Page, CrawlResult, plugin_manager
from app.services.metadata_aware_indexer import MetadataAwareIndexer
from ingestion.chunker import chunk_text
from ingestion.adaptive_chunker import adaptive_chunk_text
from ingestion.parsers_migration import extract_url_metadata
from ingestion.processors.content_processor import ContentProcessor
from app.config import CONFIG
from app.tokenizer import count_tokens
from app.metrics import (
    chunk_created_total,
    chunk_size_words_hist,
    chunk_size_tokens_hist,
    chunk_optimal_ratio_gauge,
    indexing_last_pages,
    indexing_last_chunks,
    get_metrics_collector,
)

# Import data sources to register them with plugin_manager
import app.sources.edna_docs_source


class OptimizedPipeline:
    """Optimized indexing pipeline with improved architecture"""

    def __init__(self):
        self.indexer = MetadataAwareIndexer()
        self.processor = ContentProcessor()  # Новый процессор контента
        self.processed_chunks = 0
        self.errors = []
        self.metrics_collector = get_metrics_collector()  # Initialize metrics collector

    def index_from_source(
        self,
        source_name: str,
        source_config: Dict[str, Any],
        max_pages: Optional[int] = None,
        chunk_strategy: str = None
    ) -> Dict[str, Any]:
        """Index documents from a specific data source"""

        logger.info(f"Starting indexing from source: {source_name}")
        start_time = time.time()

        try:
            # Get data source - поддержка как объекта, так и dict
            if isinstance(source_config, dict):
                source_config_dict = source_config
            else:
                source_config_dict = {
                    'base_url': getattr(source_config, 'base_url', None),
                    'strategy': getattr(source_config, 'strategy', None),
                    'use_cache': getattr(source_config, 'use_cache', True),
                    'max_pages': getattr(source_config, 'max_pages', None),
                    'crawl_deny_prefixes': getattr(source_config, 'crawl_deny_prefixes', None),
                    'sitemap_path': getattr(source_config, 'sitemap_path', None),
                    'seed_urls': getattr(source_config, 'seed_urls', None),
                    'metadata_patterns': getattr(source_config, 'metadata_patterns', None)
                }
            source = plugin_manager.get_source(source_name, source_config_dict)

            # Fetch pages
            logger.info("Fetching pages from data source...")
            crawl_result = source.fetch_pages(max_pages)

            if not crawl_result.pages:
                logger.warning("No pages fetched from data source")
                return {
                    "success": False,
                    "error": "No pages fetched",
                    "pages": 0,
                    "chunks": 0,
                    "duration": time.time() - start_time
                }

            logger.info(f"Fetched {crawl_result.successful_pages} pages in {crawl_result.duration_seconds:.2f}s")

            # Resolve chunk strategy (config default if not provided)
            strategy = (chunk_strategy or CONFIG.chunk_strategy).lower()

            # Process pages into chunks
            logger.info("Processing pages into chunks...")
            chunks = self._process_pages_to_chunks(crawl_result.pages, strategy)

            if not chunks:
                logger.warning("No chunks generated from pages")
                return {
                    "success": False,
                    "error": "No chunks generated",
                    "pages": crawl_result.successful_pages,
                    "chunks": 0,
                    "duration": time.time() - start_time
                }

            # Record metrics (pre-indexing)
            try:
                indexing_last_pages.set(crawl_result.successful_pages)
                indexing_last_chunks.set(len(chunks))
            except Exception:
                pass

            # Index chunks with enhanced metadata
            logger.info(f"Indexing {len(chunks)} chunks...")
            indexed_count = self.indexer.index_chunks_with_metadata(chunks)

            duration = time.time() - start_time

            # Log statistics
            self._log_indexing_stats(crawl_result, indexed_count, duration)

            return {
                "success": True,
                "pages": crawl_result.successful_pages,
                "chunks": indexed_count,
                "errors": len(self.errors),
                "duration": duration,
                "source": source_name
            }

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Indexing failed: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)

            return {
                "success": False,
                "error": error_msg,
                "pages": 0,
                "chunks": 0,
                "duration": duration
            }

    def _process_pages_to_chunks(
        self,
        pages: List[Page],
        chunk_strategy: str = "adaptive"
    ) -> List[Dict[str, Any]]:
        """Process pages into chunks with optimized memory usage"""

        chunks = []
        total_chunks = 0

        with tqdm(total=len(pages), desc="Processing pages", unit="page", disable=True) as pbar:
            for page in pages:
                try:
                    # Use adaptive chunking based on strategy
                    if chunk_strategy == "adaptive":
                        page_chunks = self._adaptive_chunk_page(page)
                    else:
                        page_chunks = self._standard_chunk_page(page)

                    # Metrics per-chunk
                    # Используем унифицированный токенайзер

                    try:
                        for ch in page_chunks:
                            payload = ch.get("payload", {})
                            ctype = payload.get("chunk_type", "unknown")
                            ptype = payload.get("page_type", "unknown")
                            strategy_label = "adaptive" if chunk_strategy == "adaptive" else "simple"
                            chunk_created_total.labels(strategy=strategy_label, chunk_type=ctype, page_type=str(ptype)).inc()

                            text = ch.get("text", "")
                            words = len(text.split())
                            if words > 0:
                                chunk_size_words_hist.observe(words)

                            if text:
                                try:
                                    tokens = count_tokens(text)
                                    chunk_size_tokens_hist.observe(tokens)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    chunks.extend(page_chunks)
                    total_chunks += len(page_chunks)

                except Exception as e:
                    error_msg = f"Failed to process page {page.url}: {e}"
                    logger.warning(error_msg)
                    self.errors.append(error_msg)

                pbar.update(1)

        logger.info(f"Generated {total_chunks} chunks from {len(pages)} pages")

        # Compute optimal ratio for BGE-M3 по токенам (512±20% -> 410–614 tokens)
        try:
            token_counts = []
            for ch in chunks:
                text = ch.get("text", "")
                if text:
                    token_counts.append(count_tokens(text))

            if token_counts:
                optimal = sum(1 for t in token_counts if 410 <= t <= 614)
                ratio = optimal / max(1, len(token_counts))
                chunk_optimal_ratio_gauge.labels(model="bge-m3").set(ratio)

                # Record last run metrics
                self.metrics_collector.record_last_run_optimal_chunk_ratio(
                    run_type=chunk_strategy,
                    model="bge-m3",
                    ratio=ratio
                )
        except Exception:
            pass

        # Record last run summary metrics
        self.metrics_collector.record_last_run_duration(
            run_type=chunk_strategy,
            duration_seconds=0.0  # TODO: calculate actual duration
        )

        success_rate = 1.0 - (len(self.errors) / max(1, len(pages)))
        self.metrics_collector.record_last_run_success_rate(
            run_type=chunk_strategy,
            success_rate=success_rate
        )

        self.metrics_collector.record_last_run_error_count(
            run_type=chunk_strategy,
            error_count=len(self.errors)
        )

        return chunks

    def _adaptive_chunk_page(self, page: Page) -> List[Dict[str, Any]]:
        """Adaptive chunking based on page type and content using ContentProcessor and AdaptiveChunker"""

        # Process page content with new processor
        try:
            processed_page = self.processor.process(page.content, page.url, "auto")

            # Extract URL metadata
            url_metadata = extract_url_metadata(page.url)

            # Prepare metadata for adaptive chunker
            chunker_metadata = {
                **processed_page.metadata,
                **url_metadata,
                "page_type": processed_page.page_type,
                "source": page.source,
                "language": page.language,
                "last_modified": page.last_modified,
                "size_bytes": page.size_bytes,
                **page.metadata,
            }

            # Use adaptive chunker for intelligent chunking
            adaptive_chunks = adaptive_chunk_text(processed_page.content, chunker_metadata)

            # Convert to our format
            chunks = []
            for adaptive_chunk in adaptive_chunks:
                chunk_content = adaptive_chunk['content']
                chunk_metadata = adaptive_chunk['metadata']
                
                # Calculate token count using unified tokenizer
                token_count = count_tokens(chunk_content)

                chunk = {
                    "text": chunk_content,
                    "payload": {
                        "url": processed_page.url,
                        "title": processed_page.title,
                        "page_type": processed_page.page_type,
                        "source": page.source,
                        "language": page.language,
                        "content_length": len(chunk_content),
                        "token_count": token_count,
                        "last_modified": page.last_modified,
                        "size_bytes": page.size_bytes,
                        **chunk_metadata,
                        "adaptive_chunking": True
                    }
                }
                chunks.append(chunk)

            logger.debug(f"Adaptive chunking for {page.url}: {len(chunks)} chunks, types: {[c['payload'].get('chunk_type', 'unknown') for c in chunks]}")
            return chunks

        except Exception as e:
            logger.warning(f"ContentProcessor failed for {page.url}, using fallback: {e}")
            # Fallback to original method
            return self._standard_chunk_page(page)

    def _standard_chunk_page(self, page: Page) -> List[Dict[str, Any]]:
        """Standard chunking using configuration defaults"""

        chunks_text = chunk_text(page.content)

        # Extract URL metadata
        url_metadata = extract_url_metadata(page.url)

        chunks = []
        for i, chunk_text_content in enumerate(chunks_text):
            # Calculate token count using unified tokenizer
            token_count = count_tokens(chunk_text_content)
            
            chunk = {
                "text": chunk_text_content,
                "payload": {
                    "url": page.url,
                    "title": page.title,
                    "page_type": page.page_type.value,
                    "source": page.source,
                    "language": page.language,
                    "chunk_index": i,
                    "content_length": len(chunk_text_content),
                    "token_count": token_count,
                    "chunk_type": "simple_chunk",
                    "adaptive_chunking": False,
                    **page.metadata,
                    **url_metadata  # Добавляем URL метаданные
                }
            }
            chunks.append(chunk)

        return chunks

    def _get_optimal_chunk_size(self, page: Page) -> int:
        """Get optimal chunk size based on page characteristics"""

        base_size = CONFIG.chunk_max_tokens

        # Adjust based on page type
        if page.page_type.value == "api":
            return min(int(base_size * 1.5), 1200)
        elif page.page_type.value == "guide":
            return min(int(base_size * 1.2), 1000)
        elif page.page_type.value == "faq":
            return min(int(base_size * 0.8), 600)

        # Adjust based on content length
        if page.size_bytes and page.size_bytes > 50000:  # Large page
            return min(int(base_size * 0.9), 800)

        return base_size

    def _log_indexing_stats(
        self,
        crawl_result: CrawlResult,
        indexed_count: int,
        duration: float
    ) -> None:
        """Log comprehensive indexing statistics"""

        logger.info("=" * 60)
        logger.info("INDEXING COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Source: {crawl_result.pages[0].source if crawl_result.pages else 'unknown'}")
        logger.info(f"Pages processed: {crawl_result.successful_pages}")
        logger.info(f"Chunks indexed: {indexed_count}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Pages/second: {crawl_result.successful_pages / duration:.2f}")
        logger.info(f"Chunks/second: {indexed_count / duration:.2f}")

        if crawl_result.errors:
            logger.warning(f"Errors encountered: {len(crawl_result.errors)}")
            for error in crawl_result.errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")

        if self.errors:
            logger.warning(f"Processing errors: {len(self.errors)}")
            for error in self.errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")

        # Page type distribution
        page_types = {}
        for page in crawl_result.pages:
            page_type = page.page_type.value
            page_types[page_type] = page_types.get(page_type, 0) + 1

        if page_types:
            logger.info("Page type distribution:")
            for page_type, count in page_types.items():
                logger.info(f"  {page_type}: {count}")

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get comprehensive collection statistics"""
        return self.indexer.get_collection_metadata_stats()

    def list_available_sources(self) -> List[str]:
        """List all available data sources"""
        return plugin_manager.list_sources()


def create_edna_docs_config() -> Dict[str, Any]:
    """Create configuration for edna docs source"""
    return {
        "base_url": CONFIG.crawl_start_url,
        "strategy": CONFIG.crawler_strategy,
        "use_cache": True,
        "max_pages": CONFIG.crawl_max_pages if CONFIG.crawl_max_pages > 0 else None
    }


def run_optimized_indexing(
    source_name: str = "edna_docs",
    max_pages: Optional[int] = None,
    chunk_strategy: str = "adaptive"
) -> Dict[str, Any]:
    """Run optimized indexing with the new pipeline"""

    pipeline = OptimizedPipeline()

    # Create source configuration
    if source_name == "edna_docs":
        source_config = create_edna_docs_config()
        if max_pages:
            source_config["max_pages"] = max_pages
    else:
        # Generic configuration for other sources
        source_config = {
            "base_url": "https://example.com",
            "max_pages": max_pages
        }

    return pipeline.index_from_source(
        source_name=source_name,
        source_config=source_config,
        max_pages=max_pages,
        chunk_strategy=chunk_strategy
    )
