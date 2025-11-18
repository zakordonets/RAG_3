import tempfile
from pathlib import Path

from ingestion.adapters.docusaurus import DocusaurusAdapter
from ingestion.metadata.docusaurus import DocusaurusMetadataMapper


def _create_markdown_file(root: Path, relative: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Title", encoding="utf-8")


def test_metadata_mapper_applies_section_role(tmp_path: Path):
    docs_root = tmp_path / "docs"
    _create_markdown_file(docs_root, "01-agent/intro.md")

    mapper = DocusaurusMetadataMapper(
        domain="chatcenter_user_docs",
        section_by_dir={"agent": "agent"},
        role_by_section={"agent": "operator"},
        default_role="unspecified",
    )

    adapter = DocusaurusAdapter(
        docs_root=str(docs_root),
        metadata_mapper=mapper,
    )

    docs = list(adapter.iter_documents())
    assert len(docs) == 1
    meta = docs[0].meta
    assert meta["domain"] == "chatcenter_user_docs"
    assert meta["section"] == "agent"
    assert meta["role"] == "operator"


def test_metadata_mapper_applies_platform(tmp_path: Path):
    docs_root = tmp_path / "sdk"
    _create_markdown_file(docs_root, "android/getting-started.md")

    mapper = DocusaurusMetadataMapper(
        domain="sdk_docs",
        fixed_section="sdk",
        fixed_role="integrator",
        platform_by_dir={"android": "android"},
    )

    adapter = DocusaurusAdapter(
        docs_root=str(docs_root),
        metadata_mapper=mapper,
    )

    docs = list(adapter.iter_documents())
    assert len(docs) == 1
    meta = docs[0].meta
    assert meta["domain"] == "sdk_docs"
    assert meta["section"] == "sdk"
    assert meta["platform"] == "android"
    assert meta["role"] == "integrator"
