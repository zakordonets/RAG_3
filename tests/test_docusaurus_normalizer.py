from ingestion.normalizers.docusaurus import DocusaurusNormalizer
from ingestion.adapters.base import ParsedDoc


def test_normalizer_sets_title_from_heading():
    normalizer = DocusaurusNormalizer()
    text = """---
sidebar_position: 1
---
# Подключение

Содержимое статьи
"""
    parsed = ParsedDoc(text=text, format="markdown", frontmatter={"sidebar_position": 1}, metadata={})
    result = normalizer.process(parsed)
    assert result.metadata["title"] == "Подключение"


def test_normalizer_respects_frontmatter_title():
    normalizer = DocusaurusNormalizer()
    text = """# Заголовок из тела"""
    parsed = ParsedDoc(text=text, format="markdown", frontmatter={"title": "Из frontmatter"}, metadata={})
    result = normalizer.process(parsed)
    assert result.metadata["title"] == "Из frontmatter"
