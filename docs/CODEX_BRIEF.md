# Docusaurus → Qdrant Ingestion (Brief)


## Goal
Индексировать Docusaurus .md/.mdx из `C:\\CC_RAG\\docs` в Qdrant, с очисткой MDX, правильным URL-маппингом, фронтматтер-метаданными (`title`, `category`), `_category_.json` → `group_labels`, и фильтрами по `category`.


## Input
- FS root: `C:\\CC_RAG\\docs` (конфиг).
- Файлы: `.md`, `.mdx`.
- `_category_.json` в директориях: `{"label": "..."}`.
- Локальные ссылки `<ContentRef url="/docs/...">…</ContentRef>`.


## Output (per chunk)
- vector + payload (JSON):
- `doc_id` (sha1 от `site_url` или `rel_path`)
- `chunk_id`, `chunk_index`, `chunk_count`
- `site_url`, `rel_path`, `abs_path`, `mtime`
- `title`, `category`, `group_labels`, `groups_path`, `breadcrumbs`
- `heading_path`, `content_type="markdown"`, `lang="ru"`


## URL rules
- База: `https://docs-chatcenter.edna.ru` + `/docs`.
- Для сегментов с префиксом `^\d+-` — удалить (минимум на первом уровне).
- Имя файла без расширения → хвост URL.
- Пример:
`C:\\CC_RAG\\docs\\40-admin\\02-widget\\01-admin-widget-features.md`
→ `https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features`


## Cleaning rules
- Удалить `import/export` строки, HTML-комменты.
- Удалить/расплющить JSX-компоненты (`<SupportButton />`, `<Tabs>`…).
- `:::tip|note|info|warning|caution|danger ... :::` → оставить внутренний текст.
- `<ContentRef url="/abs/or/rel">text</ContentRef>` → `text (см. {ABS_URL})`.
- Схлопнуть лишние пробелы/пустые строки.


## Chunking
- Markdown-aware: разрез по заголовкам H1–H3, ~600 токенов, overlap ~120.
- В чанк добавить `heading_path`.


## Qdrant
- Коллекция: `docs_chatcenter` (конфиг).
- Индексы payload: `category` (keyword), `groups_path` (keyword[]), `title` (fulltext).
- Upsert по `chunk_id`, GC опционально.


## CLI
python -m ingestion.run --source docusaurus --config ingestion/config.yaml --reindex changed --category-filter АРМ_adm

## Definition of Done
- Прогоны тестов зелёные.
- Для 2 эталонных путей URL совпадают с примерами.
- Фильтр `category=АРМ_adm` не возвращает документы `АРМ_sv`.
- `<ContentRef>` стал абсолютной ссылкой в тексте чанка.
