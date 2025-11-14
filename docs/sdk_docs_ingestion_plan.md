## План реализации поддержки SDK-документации (Android/iOS/Web/Main)

### 1. Цели и ограничения
- Добавить второй корпус Docusaurus (`C:\CC_RAG\SDK_docs\docs`) с URL `https://docs-sdk.edna.ru/`, сохранив существующую индексацию ChatCenter.
- Не дублировать код: переиспользовать crawler/adapter, расширив их метаданными и конфигом.
- Гарантировать корректные ссылки без `/docs` префикса, аккуратно обрабатывать `_category_.json` только там, где они есть.

### 2. Обновления crawler & утилит
1. `docusaurus_utils.fs_to_url`
   - Поддержать пустой `site_docs_prefix`, избегая лишних `/`.
   - Дополнить тесты (новые кейсы в `tests/test_docusaurus_crawler.py` или отдельный модуль для utils).
2. `crawl_docs` (`ingestion/crawlers/docusaurus_fs_crawler.py`)
   - Новый аргумент `top_level_meta: Optional[Dict[str, Dict[str, str]]] = None`.
   - При обходе каждого файла определять верхний сегмент (`rel_path.split("/", 1)[0]`).
   - В `dir_meta` всегда добавлять `top_level_dir`, а если сегмент есть в `top_level_meta`, мержить словарь (без перезаписи `_category_.json` полей, если их названия совпали — предпочтение у top-level данных).
   - Обновить `CrawlerItem.dir_meta` описание (docstring + type hints).
   - Расширить unit-тесты crawler: структура `android/getting-started/installation.md` + `_category_.json` внутри вложенной папки, проверяем URL/метаданные.

### 3. Адаптер и нормализация
1. `ingestion/adapters/docusaurus.py`
   - Принимать `top_level_meta` в конструктор, пробрасывать в `crawl_docs`.
   - В `RawDoc.meta` добавлять явно: `top_level_dir`, `sdk_platform` (если пришёл из meta), остальные ключи из `top_level_meta`.
   - Улучшить логирование: вывести список платформенных папок при старте.
2. Проверить, что `DocusaurusNormalizer`/`URLMapper` не завязаны на `/docs`; при необходимости дать им доступ к `site_docs_prefix` (уже есть аргументы — просто убедиться, что из конфига передаём пустую строку).

### 4. Конфигурация и пайплайн
1. `ingestion/config.yaml`
   - Добавить новый источник `docusaurus_sdk` с параметрами:
     - `enabled: true/false` (по умолчанию true, если нужно).
     - `docs_root: "C:\\CC_RAG\\SDK_docs\\docs"`, `site_base_url: "https://docs-sdk.edna.ru"`, `site_docs_prefix: ""`.
     - `top_level_meta` блок:
       ```yaml
       android:
         sdk_platform: "android"
         product: "sdk"
       ios:
         sdk_platform: "ios"
         product: "sdk"
       web:
         sdk_platform: "web"
         product: "sdk"
       main:
         sdk_platform: "main"
         product: "sdk"
       ```
   - При необходимости скорректировать chunking/Qdrant коллекцию (либо использовать ту же).
2. `ingestion/run.py` (или где загружается конфиг):
   - На этапе построения DAG перебрать все источники типа `docusaurus` (включая новый) и запускать адаптер для каждого (либо объединять).
   - Обеспечить возможность выбора конкретного источника через CLI/флаги, если ранее была жёсткая привязка к одному.

### 5. Тестирование
- Unit:
  - `tests/test_docusaurus_crawler.py`: кейсы на `top_level_meta`, отсутствие `_category_.json` в корне, пустой `site_docs_prefix`.
  - Новый тест в utilах на `fs_to_url`.
- Интеграция:
  - Смоук-тест адаптера с временной директорией из 4 файлов (по одной платформе), проверяющий `site_url` и метаданные.
  - (Опционально) e2e запуск `ingestion/run.py` с моками Qdrant writer (или реальным тестовым стендом) для двух источников.

### 6. Операционные инструкции
- README/доки: описать, как включить оба источника (пример команд `python ingestion/run.py --source docusaurus --docs-root ...` и указание на новый блок в YAML).
- Уточнить процедуру обновления SDK-доков: копировать свежие файлы в `C:\CC_RAG\SDK_docs\docs`, поддерживать структуру `android|ios|web|main`, при расширении списка платформ обновлять `top_level_meta`.

### 7. Оценка трудозатрат и рисков
- Обновление утилит + тесты: ~0.5 дня.
- Адаптер и конфиг + мульти-источники: ~0.5 дня.
- Документация и проверка пайплайна: ~0.25 дня.
- Основные риски: различия в структуре `_category_.json`, возможные коллизии ключей в `dir_meta`, пропуск новых платформ (минимизируется конфигом).

