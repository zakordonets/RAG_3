from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "loguru" not in sys.modules:
    dummy_logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        debug=lambda *args, **kwargs: None,
        success=lambda *args, **kwargs: None,
    )
    sys.modules["loguru"] = types.SimpleNamespace(logger=dummy_logger)

if "tqdm" not in sys.modules:
    class _DummyTqdm:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, *args, **kwargs):
            return None

    sys.modules["tqdm"] = types.SimpleNamespace(tqdm=_DummyTqdm)


def _register_stub(name: str, module: types.ModuleType) -> None:
    sys.modules[name] = module


_register_stub("ingestion.crawler", types.ModuleType("ingestion.crawler"))
sys.modules["ingestion.crawler"].crawl_with_sitemap_progress = lambda *args, **kwargs: []
sys.modules["ingestion.crawler"].crawl_mkdocs_index = lambda *args, **kwargs: []
sys.modules["ingestion.crawler"].crawl_sitemap = lambda *args, **kwargs: []
sys.modules["ingestion.crawler"].crawl = lambda *args, **kwargs: []


chunker_module = types.ModuleType("ingestion.chunker")
chunker_module.chunk_text = lambda text, *args, **kwargs: [text] if text else []
chunker_module.text_hash = lambda text: f"hash-{len(text)}"
_register_stub("ingestion.chunker", chunker_module)


content_processor_module = types.ModuleType("ingestion.processors.content_processor")


@dataclass
class _ProcessedPage:
    url: str
    title: str
    content: str
    page_type: str
    metadata: dict | None = None


class _StubContentProcessor:
    def process(self, raw_content: str, url: str, strategy: str) -> _ProcessedPage:
        content = raw_content if strategy in {"html", "markdown"} else ""
        return _ProcessedPage(
            url=url,
            title="Stub Title",
            content=content,
            page_type="stub",
            metadata={}
        )


content_processor_module.ContentProcessor = _StubContentProcessor
content_processor_module.ProcessedPage = _ProcessedPage
_register_stub("ingestion.processors.content_processor", content_processor_module)


sources_module = types.ModuleType("app.sources_registry")
sources_module.extract_url_metadata = lambda url: {}
sources_module.get_source_config = lambda name: types.SimpleNamespace(strategy=None, use_cache=None, max_pages=None)
_register_stub("app.sources_registry", sources_module)


indexer_module = types.ModuleType("ingestion.indexer")
indexer_module.upsert_chunks = lambda *args, **kwargs: None
_register_stub("ingestion.indexer", indexer_module)


metadata_indexer_module = types.ModuleType("app.services.metadata_aware_indexer")


class _StubMetadataAwareIndexer:
    def index_chunks_with_metadata(self, chunks):
        return len(chunks)


metadata_indexer_module.MetadataAwareIndexer = _StubMetadataAwareIndexer
_register_stub("app.services.metadata_aware_indexer", metadata_indexer_module)


optimized_pipeline_module = types.ModuleType("app.services.optimized_pipeline")
optimized_pipeline_module.run_optimized_indexing = lambda *args, **kwargs: {"success": False}
_register_stub("app.services.optimized_pipeline", optimized_pipeline_module)

from ingestion.pipeline import crawl_and_index


def test_pipeline_html_fallback_produces_chunks():
    html_content = """
    <html>
      <head><title>Fallback HTML Page</title></head>
      <body>
        <h1>Fallback Content</h1>
        <p>This is a fallback HTML page that should be parsed via HTML parser.</p>
      </body>
    </html>
    """

    fallback_pages = [
        {
            "url": "https://example.com/fallback",
            "text": "",
            "html": html_content,
            "title": "Fallback HTML Page",
        }
    ]

    with (
        patch("ingestion.pipeline.crawl_with_sitemap_progress", return_value=[]),
        patch("ingestion.pipeline.crawl_mkdocs_index", return_value=fallback_pages),
        patch("ingestion.pipeline.crawl", return_value=[]),
        patch("ingestion.pipeline.MetadataAwareIndexer.index_chunks_with_metadata") as mock_index,
    ):
        mock_index.return_value = 1

        result = crawl_and_index(strategy="jina", use_cache=False, max_pages=1)

    mock_index.assert_called_once()

    # Вызов indexer получает список чанков первым аргументом
    (chunks,) = mock_index.call_args[0]

    assert len(chunks) > 0, "Fallback HTML page should produce chunks"

    payload = chunks[0]["payload"]
    assert payload["content_type"] == "html"
    assert payload["indexed_via"] == "html"

    assert result == {"pages": 1, "chunks": 1}


def test_pipeline_plain_text_mkdocs_fallback_switches_to_markdown():
    plain_text_content = "Plain text fallback without HTML markup"

    fallback_pages = [
        {
            "url": "https://example.com/plain-text",
            "text": plain_text_content,
            "html": plain_text_content,
            "title": "Plain Text Page",
        }
    ]

    with (
        patch("ingestion.pipeline.crawl_with_sitemap_progress", return_value=[]),
        patch("ingestion.pipeline.crawl_mkdocs_index", return_value=fallback_pages),
        patch("ingestion.pipeline.crawl", return_value=[]),
        patch("ingestion.pipeline.MetadataAwareIndexer.index_chunks_with_metadata") as mock_index,
    ):
        mock_index.return_value = 1

        result = crawl_and_index(strategy="jina", use_cache=False, max_pages=1)

    mock_index.assert_called_once()

    (chunks,) = mock_index.call_args[0]

    assert len(chunks) > 0, "Plain text fallback page should produce chunks"

    payload = chunks[0]["payload"]
    assert payload["content_type"] == "markdown"
    assert payload["indexed_via"] == "markdown"

    assert result == {"pages": 1, "chunks": 1}
