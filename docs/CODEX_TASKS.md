# Tasks


## T1: Path Mapping Utils
**File:** `ingestion/utils/docusaurus_utils.py` (функция `fs_to_url`)
**Implement:**
- `clean_segment(seg: str, drop_numeric_prefix: bool=True) -> str`
- `fs_to_url(docs_root: Path, abs_path: Path, site_base: str, docs_prefix: str, drop_prefix_all_levels: bool=True, add_trailing_slash: bool=False) -> str`
**Given/Then Examples:**
- `40-admin/02-widget/01-page.md` → `/docs/admin/widget/page`
- См. `tests/test_pathing.py`.


## T2: Cleaning Utils
**File:** `ingestion/utils/docusaurus_utils.py` (функция `clean`)
**Implement:** `clean(text: str) -> str`
**Rules:** см. Brief → Cleaning rules.
**Edge:** пустой результат → вернуть `""`.
**Tests:** `tests/test_clean.py` (включая блоки :::tip и JSX).


## T3: ContentRef Resolver
**File:** `ingestion/utils/docusaurus_utils.py` (функция `replace_contentref`)
**Implement:** `replace_contentref(text: str, site_base: str) -> str`
**Example:** `<ContentRef url="/docs/x/y">Label</ContentRef>` → `Label (см. https://host/docs/x/y)`


## T4: Crawler
**File:** `ingestion/crawlers/docusaurus_fs_crawler.py`
**Implement:** рекурсивный обход, чтение `_category_.json` по пути, сбор `abs_path`, `rel_path`, `dir_meta`, `mtime`, `site_url`.


## T5: Processor
**File:** `ingestion/processors/docusaurus_markdown_processor.py`
**Implement:**
- парс фронтматтера (`title`, `category`),
- очистка и резолв ссылок,
- markdown-aware чанкинг,
- формирование payload.


## T6: Qdrant Writer Integration
**File:** `ingestion/indexers/qdrant_writer.py` (или расширение существующего)
**Implement:** upsert `chunk_id`, батчи, индексы payload.


## T7: CLI Wire-up
**File:** `ingestion/run.py`
**Implement:** `--source docusaurus`, `--reindex`, `--category-filter`, чтение `ingestion/config.yaml`.
