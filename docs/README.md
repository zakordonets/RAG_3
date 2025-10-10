# 📚 Документация RAG-системы для edna Chat Center

Добро пожаловать в документацию интеллектуального помощника на базе RAG (Retrieval-Augmented Generation) для технической поддержки продукта edna Chat Center.

## 🚀 Быстрый старт

### Новичкам
- 📖 [Quickstart Guide](quickstart.md) - Первые шаги с системой
- 💡 [Примеры использования](examples.md) - Практические примеры и код
- ❓ [FAQ](faq.md) - Часто задаваемые вопросы

### Разработчикам
- 🛠️ [Development Guide](development_guide.md) - Руководство разработчика
- 🧪 [Testing Strategy](testing_strategy.md) - Стратегия тестирования
- 📝 [API Reference](api_reference.md) - Полный справочник публичного API
- 🔧 [Internal API](internal_api.md) - Документация внутренних сервисов и компонентов

### Администраторам
- 🚀 [Deployment Guide](deployment_guide.md) - Руководство по развертыванию
- 📊 [Monitoring Setup](monitoring_setup.md) - Настройка мониторинга
- 🔄 [Reindexing Guide](reindexing-guide.md) - Руководство по переиндексации

## 📖 Архитектура

### Основные документы
- 🏗️ [**Architecture Overview**](architecture.md) - **Главный документ архитектуры системы**
  - Текущая версия: v4.3.0
  - Единая DAG архитектура индексации
  - Гибридный поиск (dense + sparse)
  - Quality System с RAGAS метриками

- 📋 [Technical Specification](technical_specification.md) - Детальная техническая спецификация
  - Компоненты системы
  - API endpoints
  - Конфигурация и параметры

### Архитектурные решения (ADR)
- 📄 [ADR-001: BGE-M3 Unified Embeddings](adr-001-bge-m3-unified-embeddings.md)
  - Обоснование выбора BGE-M3
  - Hybrid CPU+GPU стратегия
  - Производительность и качество

- 📄 [ADR-002: Adaptive Chunking](adr-002-adaptive-chunking.md)
  - Структурно-осознанный чанкинг
  - Оптимальные размеры чанков (150-300 токенов)
  - Сохранение семантики документов

- 📄 [Auto-Merge System](AUTO_MERGE.md)
  - Автоматическое объединение соседних чанков
  - Расширение контекста для LLM
  - TTL-кеширование документов

## 📚 Руководства

### Для разработчиков
- 🛠️ [Development Guide](development_guide.md) - Настройка окружения, структура проекта
- 🔄 [Migration Guide](migration_guide.md) - Миграция между версиями
- ➕ [Adding Data Sources](adding_data_sources.md) - Добавление новых источников данных
- 📥 [Data Loading](data_loading.md) - Загрузка и индексация данных

### Для администраторов
- 🚀 [Deployment Guide](deployment_guide.md) - Docker, Kubernetes, конфигурация
- 🔄 [Reindexing Guide](reindexing-guide.md) - Полная и инкрементальная индексация
- 📊 [Monitoring Setup](monitoring_setup.md) - Prometheus, Grafana, метрики
- 🚦 [Monitoring Quickstart](monitoring_quickstart.md) - Быстрый старт мониторинга
- 📊 [Indexing and Data Structure](indexing_and_data_structure.md) - Структура данных в Qdrant

## 🔧 API Документация

### Основные ресурсы
- 📘 [API Reference](api_reference.md) - Полный справочник всех endpoints
- 📖 [API Documentation](api_documentation.md) - Детальная документация API с примерами

### Интерактивная документация
- 🌐 [Swagger UI](http://localhost:9000/apidocs) - Интерактивное тестирование API (при запущенной системе)
- 📄 [OpenAPI Spec](http://localhost:9000/apispec_1.json) - OpenAPI 2.0 спецификация

### Ключевые endpoints
```
POST /v1/chat/query          # Отправка запроса
GET  /v1/admin/health        # Проверка здоровья системы
GET  /v1/admin/metrics       # Prometheus метрики
POST /v1/admin/reindex       # Запуск переиндексации
```

## 🧪 Тестирование

### Документация
- 📋 [Testing Strategy](testing_strategy.md) - Стратегия и подходы к тестированию
- 🧪 [Autotests Guide](autotests_guide.md) - Руководство по автоматическим тестам

### Быстрые команды
```bash
# Запуск всех тестов
make test

# Только быстрые тесты
make test-fast

# Тесты с покрытием
make test-coverage

# Unit тесты
make test-unit
```

## 📊 Мониторинг и качество

### Мониторинг системы
- 📊 [Monitoring Setup](monitoring_setup.md) - Полная настройка Prometheus и Grafana
- 🚦 [Monitoring Quickstart](monitoring_quickstart.md) - Быстрый старт мониторинга
- 📈 [Grafana Quality Dashboard](grafana_quality_dashboard.md) - Dashboard для мониторинга качества

### Система качества RAGAS
- 🎯 [RAGAS Quality System](ragas_quality_system.md) - Полное описание системы качества
- 🚀 [RAGAS Quickstart](ragas_quickstart.md) - Быстрый старт с RAGAS
- 📖 [RAGAS README](README_RAGAS.md) - Основная информация о RAGAS

### Метрики качества
- **Faithfulness** - точность ответов относительно источников
- **Context Precision** - релевантность найденного контекста
- **Answer Relevancy** - релевантность ответа вопросу

## 📝 Справочные материалы

### Технические справочники
- 📊 [Indexing and Data Structure](indexing_and_data_structure.md) - Структура индекса в Qdrant
- ✨ [Complete Features](complete_features.md) - Полный список возможностей системы
- 🔧 [Auto-Merge Optional Deps](AUTO_MERGE_OPTIONAL_DEPS.md) - Опциональные зависимости Auto-Merge

### Для разработки
- 📋 [PR Instructions](README_PR_INSTRUCTIONS.md) - Инструкции для создания Pull Request

## 🎯 Основные возможности

### Многоканальность
- ✅ Telegram Bot (long polling) - готово
- 🔜 Web Widget - планируется
- 🔜 Email интеграция - планируется

### Поиск и индексация
- ✅ Гибридный поиск (dense + sparse векторы)
- ✅ RRF (Reciprocal Rank Fusion)
- ✅ ML-реранкинг (bge-reranker-v2-m3)
- ✅ Auto-merge соседних чанков
- ✅ Инкрементальная индексация
- ✅ Поддержка Docusaurus и веб-сайтов

### Embeddings и LLM
- ✅ BGE-M3 (ONNX + DirectML для GPU)
- ✅ Локальная генерация sparse векторов
- ✅ LLM роутер (YandexGPT → GPT-5 → Deepseek)
- ✅ Circuit Breaker для надежности

### Production-ready
- ✅ Comprehensive error handling
- ✅ Redis кеширование
- ✅ Rate limiting
- ✅ Prometheus метрики
- ✅ Grafana дашборды
- ✅ Quality System с RAGAS
- ✅ Валидация и санитизация
- ✅ Docker и Kubernetes

## 📈 Версионирование

### Текущая версия: v4.3.0 (2025-10-08)

**Критические исправления:**
- 🔧 Исправлено дублирование текста (chunk_text удален)
- ⚙️ Исправлены параметры чанкинга из .env
- 🔗 Исправлена обработка ContentRef ссылок
- 📊 Улучшено логирование прогресса индексации
- 🐳 Восстановлен Redis контейнер

### Предыдущие версии
- **v4.2.0** - Критические исправления QdrantWriter, sparse векторы
- **v4.1.0** - Единая DAG архитектура индексации
- **v4.0.0** - Система качества RAGAS, пользовательский фидбек

См. [CHANGELOG.md](../CHANGELOG.md) для полной истории изменений.

## 🆘 Получение помощи

### Документация
1. Начните с [Quickstart Guide](quickstart.md)
2. Изучите [Architecture Overview](architecture.md)
3. Посмотрите [Examples](examples.md)
4. Проверьте [FAQ](faq.md)

### Проблемы и вопросы
- 🐛 Нашли баг? Создайте issue в репозитории
- 💡 Есть идея? Обсудите в discussions
- 📖 Нужна помощь? Проверьте FAQ и документацию

## 🗺️ Структура документации

```
docs/
├── README.md (этот файл)           # Главная страница документации
├── quickstart.md                   # Быстрый старт
│
├── 📖 АРХИТЕКТУРА
│   ├── architecture.md             # Главный документ архитектуры ⭐
│   ├── technical_specification.md  # Техническая спецификация
│   ├── adr-001-*.md               # Архитектурные решения
│   ├── adr-002-*.md
│   └── AUTO_MERGE.md
│
├── 📚 РУКОВОДСТВА
│   ├── development_guide.md        # Для разработчиков
│   ├── deployment_guide.md         # Для администраторов
│   ├── migration_guide.md          # Миграция версий
│   ├── adding_data_sources.md      # Добавление источников
│   ├── reindexing-guide.md        # Переиндексация
│   └── data_loading.md            # Загрузка данных
│
├── 🔧 API
│   ├── api_reference.md            # Справочник API
│   └── api_documentation.md        # Документация API
│
├── 🧪 ТЕСТИРОВАНИЕ
│   ├── testing_strategy.md         # Стратегия тестирования
│   └── autotests_guide.md         # Руководство по тестам
│
├── 📊 МОНИТОРИНГ
│   ├── monitoring_setup.md         # Настройка мониторинга
│   ├── monitoring_quickstart.md    # Быстрый старт
│   └── grafana_quality_dashboard.md
│
├── 🎯 КАЧЕСТВО
│   ├── ragas_quality_system.md     # Система качества
│   ├── ragas_quickstart.md        # Быстрый старт RAGAS
│   └── README_RAGAS.md
│
├── 📝 СПРАВОЧНИКИ
│   ├── indexing_and_data_structure.md
│   ├── complete_features.md
│   ├── AUTO_MERGE_OPTIONAL_DEPS.md
│   ├── examples.md
│   └── faq.md
│
└── 🔨 РАЗРАБОТКА
    └── README_PR_INSTRUCTIONS.md
```

## 🔗 Полезные ссылки

### Внутренние
- [Главная документация](../README.md) - README проекта
- [CHANGELOG](../CHANGELOG.md) - История изменений
- [Contributing Guidelines](../CONTRIBUTING.md) - Руководство для контрибьюторов

### Внешние
- [edna Chat Center](https://edna.ru/chat-center/) - Официальный сайт продукта
- [Документация продукта](https://docs-chatcenter.edna.ru/) - Документация edna Chat Center
- [Qdrant](https://qdrant.tech/) - Векторная база данных
- [RAGAS](https://github.com/explodinggradients/ragas) - Framework для оценки RAG систем

---

**Последнее обновление**: Октябрь 2025
**Версия документации**: 4.3.0
**Статус**: ✅ Актуально
