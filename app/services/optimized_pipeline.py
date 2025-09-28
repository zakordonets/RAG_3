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
from app.config import CONFIG


class OptimizedPipeline:
    """Optimized indexing pipeline with improved architecture"""

    def __init__(self):
        self.indexer = MetadataAwareIndexer()
        self.processed_chunks = 0
        self.errors = []

    def index_from_source(
        self,
        source_name: str,
        source_config: Dict[str, Any],
        max_pages: Optional[int] = None,
        chunk_strategy: str = "adaptive"
    ) -> Dict[str, Any]:
        """Index documents from a specific data source"""

        logger.info(f"Starting indexing from source: {source_name}")
        start_time = time.time()

        try:
            # Get data source
            source = plugin_manager.get_source(source_name, source_config)

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

            # Process pages into chunks
            logger.info("Processing pages into chunks...")
            chunks = self._process_pages_to_chunks(crawl_result.pages, chunk_strategy)

            if not chunks:
                logger.warning("No chunks generated from pages")
                return {
                    "success": False,
                    "error": "No chunks generated",
                    "pages": crawl_result.successful_pages,
                    "chunks": 0,
                    "duration": time.time() - start_time
                }

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

        with tqdm(total=len(pages), desc="Processing pages", unit="page") as pbar:
            for page in pages:
                try:
                    # Use adaptive chunking based on strategy
                    if chunk_strategy == "adaptive":
                        page_chunks = self._adaptive_chunk_page(page)
                    else:
                        page_chunks = self._standard_chunk_page(page)

                    chunks.extend(page_chunks)
                    total_chunks += len(page_chunks)

                except Exception as e:
                    error_msg = f"Failed to process page {page.url}: {e}"
                    logger.warning(error_msg)
                    self.errors.append(error_msg)

                pbar.update(1)

        logger.info(f"Generated {total_chunks} chunks from {len(pages)} pages")
        return chunks

    def _adaptive_chunk_page(self, page: Page) -> List[Dict[str, Any]]:
        """Adaptive chunking based on page type and content"""

        # Determine optimal chunk size based on page type and content
        optimal_size = self._get_optimal_chunk_size(page)

        # Chunk the text
        chunks_text = chunk_text(page.content, max_tokens=optimal_size)

        # Create chunk objects with enhanced metadata
        chunks = []
        for i, chunk_text_content in enumerate(chunks_text):
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
                    "last_modified": page.last_modified,
                    "size_bytes": page.size_bytes,
                    **page.metadata
                }
            }
            chunks.append(chunk)

        return chunks

    def _standard_chunk_page(self, page: Page) -> List[Dict[str, Any]]:
        """Standard chunking using configuration defaults"""

        chunks_text = chunk_text(page.content)

        chunks = []
        for i, chunk_text_content in enumerate(chunks_text):
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
                    **page.metadata
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
