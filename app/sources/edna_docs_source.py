#!/usr/bin/env python3
"""
Edna documentation data source implementation
"""

from __future__ import annotations

import time
from typing import List, Dict, Any, Optional
from loguru import logger

from app.abstractions.data_source import (
    DataSourceBase, Page, PageType, CrawlResult, register_data_source
)
from ingestion.crawler import crawl_with_sitemap_progress
from ingestion.parsers import parse_api_documentation, parse_release_notes, parse_faq_content, parse_guides


@register_data_source("edna_docs")
class EdnaDocsDataSource(DataSourceBase):
    """Data source for edna documentation website"""

    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get("base_url", "https://docs-chatcenter.edna.ru/")
        self.strategy = config.get("strategy", "jina")
        self.use_cache = config.get("use_cache", True)
        self.max_pages = config.get("max_pages")
        super().__init__(config)

    def get_source_name(self) -> str:
        return "edna-docs"

    def fetch_pages(self, max_pages: Optional[int] = None) -> CrawlResult:
        """Fetch pages from edna documentation"""
        logger.info(f"Starting crawl of {self.base_url} with strategy {self.strategy}")
        start_time = time.time()

        try:
            # Use existing crawler with progress tracking
            pages_data = crawl_with_sitemap_progress(
                strategy=self.strategy,
                use_cache=self.use_cache,
                max_pages=max_pages or self.max_pages
            )

            pages: List[Page] = []
            errors: List[str] = []

            for page_data in pages_data:
                try:
                    page = self._parse_page_data(page_data)
                    pages.append(page)
                except Exception as e:
                    error_msg = f"Failed to parse page {page_data.get('url', 'unknown')}: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            duration = time.time() - start_time

            return CrawlResult(
                pages=pages,
                total_pages=len(pages_data),
                successful_pages=len(pages),
                failed_pages=len(errors),
                errors=errors,
                duration_seconds=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Failed to crawl {self.base_url}: {e}"
            logger.error(error_msg)

            return CrawlResult(
                pages=[],
                total_pages=0,
                successful_pages=0,
                failed_pages=1,
                errors=[error_msg],
                duration_seconds=duration
            )

    def classify_page(self, page: Page) -> PageType:
        """Enhanced page classification based on content and URL"""
        url_lower = page.url.lower()
        title_lower = page.title.lower()
        content_lower = page.content.lower()

        # FAQ detection
        if "faq" in url_lower or "faq" in title_lower:
            return PageType.FAQ

        # API documentation detection
        if "api" in url_lower or "api" in title_lower:
            return PageType.API

        # Release notes detection
        if any(keyword in url_lower for keyword in ["release", "changelog", "version"]):
            return PageType.RELEASE_NOTES

        # Blog detection
        if "blog" in url_lower or any(keyword in content_lower for keyword in ["новость", "обновление", "релиз"]):
            return PageType.BLOG

        # Default to guide
        return PageType.GUIDE

    def _parse_page_data(self, page_data: Dict[str, Any]) -> Page:
        """Parse raw page data into Page object"""
        url = page_data["url"]
        html = page_data["html"]

        # Parse content based on URL
        parsed_content = self._parse_content(url, html)

        # Extract metadata
        metadata = {
            "indexed_via": self.strategy,
            "indexed_at": time.time(),
            "content_length": len(parsed_content.get("text", "")),
        }

        return self._create_page(
            url=url,
            title=parsed_content.get("title", ""),
            content=parsed_content.get("text", ""),
            metadata=metadata
        )

    def _parse_content(self, url: str, html: str) -> Dict[str, str]:
        """Parse HTML content using appropriate parser"""
        url_lower = url.lower()

        try:
            if "faq" in url_lower:
                return parse_faq_content(html)
            elif "api" in url_lower:
                return parse_api_documentation(html)
            elif any(keyword in url_lower for keyword in ["release", "changelog", "blog"]):
                return parse_release_notes(html)
            else:
                return parse_guides(html)
        except Exception as e:
            logger.warning(f"Parser failed for {url}, using fallback: {e}")
            # Fallback to basic parsing
            return {"text": html, "title": ""}

    def _validate_config(self) -> None:
        """Validate edna docs specific configuration"""
        if not self.base_url:
            raise ValueError("base_url is required for edna docs source")

        if self.strategy not in ["jina", "http", "browser"]:
            raise ValueError(f"Invalid strategy: {self.strategy}. Must be one of: jina, http, browser")


@register_data_source("generic_web")
class GenericWebDataSource(DataSourceBase):
    """Generic web data source for any website"""

    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get("base_url")
        self.allowed_domains = config.get("allowed_domains", [])
        self.max_depth = config.get("max_depth", 3)
        super().__init__(config)

    def get_source_name(self) -> str:
        return "generic-web"

    def fetch_pages(self, max_pages: Optional[int] = None) -> CrawlResult:
        """Fetch pages from generic web source"""
        # Implementation would go here
        # For now, return empty result
        return CrawlResult(
            pages=[],
            total_pages=0,
            successful_pages=0,
            failed_pages=0,
            errors=["Generic web source not yet implemented"],
            duration_seconds=0.0
        )

    def classify_page(self, page: Page) -> PageType:
        """Classify page using default URL-based classification"""
        return self.classify_page_by_url(page.url)

    def _validate_config(self) -> None:
        """Validate generic web source configuration"""
        if not self.base_url:
            raise ValueError("base_url is required for generic web source")
