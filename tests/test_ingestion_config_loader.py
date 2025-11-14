import tempfile
from pathlib import Path
import textwrap
import yaml

from ingestion.run import load_sources_from_config


def test_load_sources_from_config_with_top_level_meta():
    config_text = """
        global:
          qdrant:
            collection: "test_collection"
        sources:
          docusaurus:
            enabled: true
            docs_root: "C:\\\\CC_RAG\\\\docs"
            site_base_url: "https://docs-chatcenter.edna.ru"
          docusaurus_sdk:
            enabled: true
            docs_root: "C:\\\\CC_RAG\\\\SDK_docs\\\\docs"
            site_base_url: "https://docs-sdk.edna.ru"
            site_docs_prefix: ""
            top_level_meta:
              android:
                sdk_platform: "android"
                product: "sdk"
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.yaml"
        config_path.write_text(textwrap.dedent(config_text), encoding="utf-8")
        sources = load_sources_from_config(str(config_path))
    assert len(sources) == 2

    sdk_source = next(src for src in sources if src["name"] == "docusaurus_sdk")
    sdk_config = sdk_source["config"]
    assert sdk_source["source_type"] == "docusaurus"
    assert sdk_config["site_base_url"] == "https://docs-sdk.edna.ru"
    assert sdk_config["site_docs_prefix"] == ""
    assert sdk_config["top_level_meta"]["android"]["sdk_platform"] == "android"
    assert sdk_config["collection_name"] == "test_collection"
    assert sdk_source["reindex_mode"] == "changed"


def test_load_sources_from_config_profile_override():
    config = {
        "global": {
            "qdrant": {"collection": "base"},
            "indexing": {"batch_size": 8, "reindex_mode": "changed"},
        },
        "sources": {
            "docusaurus": {
                "enabled": True,
                "docs_root": "C:\\\\docs",
                "site_base_url": "https://base",
            }
        },
        "profiles": {
            "production": {
                "global": {
                    "qdrant": {"collection": "prod"},
                    "indexing": {"batch_size": 4, "reindex_mode": "full"},
                },
                "sources": {
                    "docusaurus": {
                        "site_base_url": "https://prod",
                        "chunk": {"max_tokens": 700},
                    }
                },
            }
        },
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.yaml"
        config_path.write_text(
            yaml.dump(config, allow_unicode=True), encoding="utf-8"
        )
        sources = load_sources_from_config(str(config_path), profile="production")
    assert len(sources) == 1
    source = sources[0]
    assert source["reindex_mode"] == "full"
    cfg = source["config"]
    assert cfg["collection_name"] == "prod"
    assert cfg["batch_size"] == 4
    assert cfg["site_base_url"] == "https://prod"
    assert cfg["chunk_max_tokens"] == 700
