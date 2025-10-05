# Changelog

Все значимые изменения в проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Планируется
- Web интерфейс для взаимодействия с системой
- Поддержка других мессенджеров (WhatsApp, Viber)
- A/B тестирование ответов
- Аналитика использования и метрики
- Многоязычная поддержка
- Voice интерфейс
- Real-time обучение на основе обратной связи

## [2.6.0] - 2025-09-28

### Добавлено (Автотесты и CI/CD)
- **🧪 Comprehensive Test Suite**: Полный набор автотестов для end-to-end проверки pipeline
- **🚀 CI/CD Pipeline**: GitHub Actions для автоматического тестирования
- **⚡ Makefile Commands**: Удобные команды для разработки и тестирования
- **📊 Test Coverage**: Отчеты о покрытии кода
- **🔧 Development Tools**: Линтинг, форматирование, проверка типов
- **🏗️ Plugin Architecture**: Система плагинов для источников данных
- **📈 Enhanced Metadata**: Обогащение метаданных документов
- **🔄 Optimized Pipeline**: Оптимизированный pipeline индексации

### Исправлено
- **🐛 Jina Reader Parsing**: Исправлен парсинг контента от Jina Reader во всех парсерах
- **🐛 Data Source Registration**: Автоматическая регистрация источников данных в тестах
- **🐛 Qdrant Search**: Исправлен поиск тестовых данных в Qdrant
- **🐛 Configuration Validation**: Добавлена валидация конфигурации
- **🐛 Legacy Code Cleanup**: Удален устаревший код (Ollama, deprecated sparse service)
- **🐛 Connection Pooling**: Исправлен deprecated параметр `method_whitelist`

### Технические улучшения
- **End-to-End Tests**: Полное тестирование от извлечения до записи в Qdrant
- **Plugin System**: Абстракции для источников данных с автоматической регистрацией
- **Enhanced Metadata**: complexity_score, semantic_density, boost_factor
- **Connection Pool**: HTTP connection pooling для эффективного crawling
- **Configuration Management**: Валидация и типизация конфигурации
- **Memory Optimization**: Оптимизация использования памяти в chunker
- **Async Support**: Поддержка async/await где возможно

### Документация
- **📖 Autotests Integration Report**: [docs/autotests_integration_report.md](docs/autotests_integration_report.md)
- **🧪 Testing Guide**: Обновлены инструкции по автотестам
- **⚙️ Development Setup**: Настройка среды разработки
- **🔧 CI/CD Documentation**: Документация GitHub Actions
- **📊 Makefile Commands**: Описание команд разработки

### Файлы добавлены
- `tests/test_end_to_end_pipeline.py` - End-to-end тесты
- `pytest.ini` - Конфигурация pytest
- `Makefile` - Команды разработки
- `requirements-dev.txt` - Зависимости для разработки
- `scripts/run_tests.py` - Скрипт запуска тестов
- `.github/workflows/ci.yml` - CI/CD pipeline
- `app/abstractions/` - Система абстракций
- `app/sources/` - Источники данных
- `app/services/optimized_pipeline.py` - Оптимизированный pipeline
- `app/services/connection_pool.py` - HTTP connection pool
- `app/services/metadata_aware_indexer.py` - Enhanced metadata indexer

### Файлы обновлены
- `README.md` - Добавлена документация по автотестам
- `ingestion/parsers.py` - Поддержка Jina Reader во всех парсерах
- `app/config.py` - Валидация конфигурации и новые параметры
- `app/sources/edna_docs_source.py` - Реализация источника данных
- `ingestion/pipeline.py` - Интеграция с оптимизированным pipeline

## [2.5.0] - 2025-09-23

### Добавлено (Phase 2: Production-Ready RAGAS Quality System)
- **🎯 Production-Ready RAGAS System**: Полностью стабилизированная система оценки качества
- **⚡ Performance Optimization**: Таймауты RAGAS (25s) с автоматическим fallback
- **🧪 Comprehensive Testing**: Полное покрытие тестами (5 passed, 1 skipped)
- **📊 Enhanced Analytics**: Расширенная аналитика качества с корреляционным анализом
- **🔧 Configuration Management**: Гибкая конфигурация через переменные окружения
- **📈 Grafana Integration**: Обновленные дашборды для мониторинга качества
- **🔄 Telegram Feedback**: Inline кнопки для сбора пользовательского фидбека
- **📚 Complete Documentation**: Полная документация Phase 2 системы

### Исправлено
- **🐛 RAGAS Timeout Issues**: Устранены зависания при длительной RAGAS evaluation
- **🐛 Test Reliability**: Исправлены таймауты в интеграционных тестах
- **🐛 Database JSON Serialization**: Безопасное хранение contexts/sources через JSON
- **🐛 LangChain Wrapper Stability**: Стабилизированы обертки для детерминизма
- **🐛 Metrics Collection**: Исправлены конфликты портов Prometheus сервера
- **🐛 API Endpoints**: Корректная регистрация quality endpoints

### Технические улучшения
- **RAGAS Evaluator**: Добавлены таймауты и fallback механизмы
- **Quality Manager**: Расширенные методы для статистики и трендов
- **Database Model**: Безопасная JSON сериализация сложных структур
- **Metrics System**: Thread-safe singleton pattern для Prometheus
- **Test Suite**: Мокирование LLM для стабильных тестов
- **Configuration**: Переменная `RAGAS_EVALUATION_SAMPLE_RATE` для контроля

### Документация
- **📖 Phase 2 Documentation**: [docs/phase2_ragas_quality_system.md](docs/phase2_ragas_quality_system.md)
- **🧪 Testing Guide**: Обновлены инструкции по тестированию
- **⚙️ Configuration Guide**: Подробная документация переменных окружения
- **🔧 Troubleshooting**: Расширенное руководство по решению проблем
- **📊 Monitoring Guide**: Инструкции по настройке Grafana дашбордов

### Breaking Changes
- **Environment Variables**: Добавлены новые переменные для Phase 2
- **Database Schema**: Обновлена схема для JSON полей
- **API Endpoints**: Новые quality endpoints с измененными URL
- **Metrics Port**: Изменен порт метрик с 9001 на 9002

### Migration Guide
1. Обновить переменные окружения (.env)
2. Пересоздать базу данных качества
3. Обновить Grafana дашборды
4. Перезапустить все сервисы

## [2.4.0] - 2025-09-21

### Добавлено
- **RAGAS Quality System**: Автоматическая оценка качества ответов
- **Quality Database**: SQLAlchemy ORM для хранения взаимодействий
- **Fallback Scores**: Умные эвристики для оценки качества без OpenAI
- **User Feedback**: Система сбора пользовательских оценок (👍/👎)
- **Quality Metrics**: Prometheus метрики для мониторинга качества
- **Correlation Analysis**: Анализ корреляции между автоматическими и пользовательскими оценками
- **Comprehensive Documentation**: Полная документация RAGAS системы

### Технические детали
- **RAGAS Integration**: Интеграция с RAGAS 0.1.21 для оценки качества
- **LangChain Wrappers**: Кастомные обертки для YandexGPT и BGE embeddings
- **Database Schema**: Полная схема для хранения quality interactions
- **Error Handling**: Graceful fallback при ошибках RAGAS
- **Performance**: Оптимизированная обработка с батчами и таймаутами

### Ограничения
- **OpenAI Dependency**: RAGAS требует OpenAI API ключ для полного функционала
- **Version Compatibility**: Требуются точные версии LangChain (0.2.16) и RAGAS (0.1.21)
- **Performance**: RAGAS evaluation занимает 2-5 секунд на взаимодействие

### Документация
- **RAGAS Quality System**: [docs/ragas_quality_system.md](docs/ragas_quality_system.md)
- **Quick Start Guide**: [docs/ragas_quickstart.md](docs/ragas_quickstart.md)
- **Configuration**: Обновлен `env.example` с RAGAS параметрами
- **Scripts**: `init_quality_db.py`
- **Tests**: `test_ragas_quality.py`, `test_simple_ragas.py`

## [2.3.0] - 2025-09-20

### Добавлено
- **Полный мониторинг**: Grafana + Prometheus для визуализации метрик
- **Готовые дашборды**: Автоматическое создание "RAG System Overview" дашборда
- **Docker мониторинг**: `docker-compose.monitoring.yml` для быстрого запуска
- **Скрипты запуска**: `start_monitoring.ps1` и `start_monitoring.bat`
- **Автоматическая конфигурация**: Provisioning для Grafana и Prometheus
- **Windows WSL поддержка**: Правильная конфигурация для Windows окружения

### Изменено
- **Документация**: Обновлены `architecture.md`, `deployment_guide.md`, `development_guide.md`
- **README**: Добавлен раздел мониторинга с быстрым стартом
- **Порты**: Grafana доступен на порту 8080 (из-за конфликтов с портом 3000)

### Технические детали
- Prometheus: порт 9090, сбор метрик с RAG API (порт 9002)
- Grafana: порт 8080, логин admin/admin123
- Автоматическое создание дашбордов через provisioning
- Поддержка Windows WSL с правильными IP адресами
- **Исправление**: Конфигурация Prometheus для подключения к RAG API через `host.docker.internal`
- **Исправление**: Конфликт портов метрик - перенесены с 9001 на 9002 для устранения конфликтов
- **Исправление**: Метрики теперь корректно отображаются в Grafana после устранения конфликта портов
- **Исправление**: ModuleNotFoundError при запуске Telegram бота - добавлен автоматический поиск корневой директории проекта
- **Улучшение**: Добавлены удобные скрипты запуска (`start_telegram_bot.bat`, `start_telegram_bot.ps1`)

## [2.2.0] - 2025-09-20

### Добавлено
- **Sparse векторы**: Полная поддержка sparse векторов через BGE-M3
- **Гибридный поиск**: 100% покрытие sparse векторами (512/512 точек)
- **Единый модуль индексации**: Production-ready модуль `scripts/indexer.py` для замены множества скриптов
- **Управление коллекциями**: Скрипты для полной замены и переиндексации
- **Проверка покрытия**: Автоматическая верификация sparse векторов
- **Детальное тестирование**: Comprehensive тесты для sparse поиска
- **YandexGPT RC**: Обновлен API для использования модели yandexgpt/rc
- **Миграционный гид**: Подробное руководство по переходу на новый модуль

### Изменено
- **Структура Qdrant**: Переход на named vectors (dense + sparse)
- **Embedding pipeline**: Hybrid стратегия (DirectML для dense, CPU для sparse)
- **Конфигурация**: Добавлена поддержка 'auto' backend для sparse векторов
- **Чанкинг**: Оптимизирован размер чанков (60-250 токенов)
- **Интерфейс индексации**: Упрощен до единого модуля с автоматическим выбором настроек

### Исправлено
- **Sparse поиск**: Исправлена структура данных для корректной работы с Qdrant
- **Индексация**: Исправлено преобразование lexical_weights в SparseVector
- **Backend поддержка**: Добавлена поддержка 'auto' в условие обработки sparse векторов

### Удалено
- **Внешний sparse сервис**: Убран отдельный сервис на FlagEmbedding
- **Ollama зависимости**: Заменены на локальную генерацию через BGE-M3
- **Старые скрипты индексации**: `reindex.py`, `full_reindex.py`, `full_reindex_with_titles.py`, `run_full_reindex.py`

### Технические детали
- Полная переиндексация 516 чанков с sparse векторами
- Время переиндексации: ~50 минут
- Средний размер sparse вектора: 64-101 индекс
- 100% покрытие sparse векторами в коллекции

## [1.0.0] - 2025-01-16

### Добавлено
- **RAG-система**: Полнофункциональная система на базе Retrieval-Augmented Generation
- **Telegram бот**: Long polling бот с поддержкой MarkdownV2 форматирования
- **Flask API**: RESTful API с endpoints для чата и администрирования
- **Гибридный поиск**: Комбинация dense и sparse эмбеддингов с RRF
- **LLM роутинг**: Поддержка YandexGPT, GPT-5, Deepseek с fallback логикой
- **Векторная база данных**: Интеграция с Qdrant для хранения эмбеддингов
- **Парсинг документации**: Специализированные парсеры для разных типов контента
- **Чанкинг**: Умное разбиение документов с качественными гейтами
- **Реренкинг**: BGE-reranker-v2-m3 для улучшения качества поиска
- **Конфигурация**: Централизованная система настроек через .env
- **Логирование**: Структурированное логирование с loguru
- **Мониторинг**: Health checks и метрики производительности
- **Документация**: Подробная техническая документация и примеры

### Технические детали
- **Эмбеддинги**: BAAI/bge-m3 (1024 dim) для dense, sparse через FlagEmbedding
- **Поиск**: Hybrid search с весами Dense=0.7, Sparse=0.3
- **Реренкинг**: Top-20 → Top-10 с BGE-reranker-v2-m3
- **Форматирование**: telegramify-markdown для корректного MarkdownV2
- **Краулинг**: Jina Reader для обхода антибота
- **Производительность**: 60-120 сек время ответа, 100+ concurrent users

### API Endpoints
- `POST /v1/chat/query` - Обработка пользовательских запросов
- `GET /v1/admin/health` - Проверка состояния системы
- `POST /v1/admin/reindex` - Переиндексация документации

### Конфигурация
- Поддержка множественных LLM провайдеров
- Настраиваемые параметры поиска и реренкинга
- Гибкая система краулинга с разными стратегиями
- Детальные настройки таймаутов и лимитов

### Безопасность
- Переменные окружения для API ключей
- Валидация входных данных
- Обработка ошибок без утечки информации
- Подготовка к rate limiting и аутентификации

### Производительность
- Lazy loading моделей
- Batch обработка эмбеддингов
- Кэширование частых запросов
- Асинхронная обработка где возможно

### Мониторинг
- Подробное логирование каждого этапа
- Метрики времени выполнения
- Health checks для всех компонентов
- Готовность к Prometheus/Grafana

### Документация
- README с быстрым стартом
- Техническая спецификация
- API Reference
- Руководство по развертыванию
- Руководство по разработке
- Примеры использования
- FAQ и troubleshooting

### Тестирование
- Unit тесты для основных компонентов
- Integration тесты для API
- Load тестирование
- Подготовка к CI/CD pipeline

### Развертывание
- Docker Compose конфигурация
- Kubernetes манифесты
- Production настройки
- Nginx конфигурация
- SSL/TLS поддержка

## [0.1.0] - 2025-01-15

### Добавлено
- **Инициализация проекта**: Базовая структура проекта
- **Архитектурное планирование**: Документация архитектуры
- **Планирование реализации**: Детальный план разработки
- **Настройка окружения**: Базовые конфигурации и зависимости

### Технические детали
- Выбор технологического стека
- Проектирование API
- Планирование интеграций
- Определение метрик и KPI

---

## Легенда

- **Добавлено** - для новых функций
- **Изменено** - для изменений в существующей функциональности
- **Устарело** - для функций, которые будут удалены в будущих версиях
- **Удалено** - для удаленных функций
- **Исправлено** - для исправления ошибок
- **Безопасность** - для исправлений уязвимостей

## Ссылки

- [GitHub Releases](https://github.com/your-repo/releases)
- [API Documentation](docs/api_reference.md)
- [Deployment Guide](docs/deployment_guide.md)
- [Development Guide](docs/development_guide.md)
