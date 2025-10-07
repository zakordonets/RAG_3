# Как проверить PR


1. Установить dev-зависимости:
```bash
pip install -r requirements-dev.txt
```

2. Запустить линтеры/тесты:
```bash
pytest -q
```

3. Проверить два примера URL из тестов (tests/test_pathing.py).

4. Прогоним локально ingestion:
``` bash
python -m ingestion.run --source docusaurus --config ingestion/config.yaml --reindex changed --category-filter АРМ_adm
```

5. Убедиться, что в Qdrant появились поинты с payload.category = выбранной категории и корректными site_url.

---


## ingestion/config.yaml (фрагмент для добавления)
```yaml
docusaurus:
enabled: true
docs_root: "C:\\CC_RAG\\docs"
site_base_url: "https://docs-chatcenter.edna.ru"
site_docs_prefix: "/docs"
include_file_extensions: [".md", ".mdx"]
exclude_globs: ["**/_category_.json", "**/node_modules/**", "**/.docusaurus/**"]
default_category: "UNSPECIFIED"
cleaning:
remove_html_comments: true
strip_imports: true
strip_custom_components: true
strip_admonitions: true
normalize_whitespace: true
chunk:
max_tokens: 600
overlap_tokens: 120
split_by: "markdown"
routing:
drop_numeric_prefix_in_first_level: true
add_trailing_slash: false
indexing:
upsert: true
delete_missing: false
