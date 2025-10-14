# Makefile для управления автотестами и разработкой

.PHONY: help install test test-unit test-integration test-e2e test-slow test-fast clean lint format coverage-extended ci-test ci-test-all

# Цвета для вывода
GREEN=\033[0;32m
YELLOW=\033[1;33m
RED=\033[0;31m
NC=\033[0m # No Color

help: ## Показать справку
	@echo "$(GREEN)Доступные команды:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Установить зависимости
	@echo "$(GREEN)Установка зависимостей...$(NC)"
	python -m pip install -r requirements.txt
	@echo "$(GREEN)Зависимости установлены!$(NC)"

test: ## Запустить все тесты
	@echo "$(GREEN)Запуск всех тестов...$(NC)"
	python -m pytest tests/ -v

test-unit: ## Запустить только unit тесты
	@echo "$(GREEN)Запуск unit тестов...$(NC)"
	python -m pytest tests/ -m "not slow and not integration" -v

test-integration: ## Запустить интеграционные тесты
	@echo "$(GREEN)Запуск интеграционных тестов...$(NC)"
	python -m pytest tests/ -m "integration" -v

test-e2e: ## Запустить end-to-end тесты
	@echo "$(GREEN)Запуск end-to-end тестов...$(NC)"
	python -m pytest tests/ -m "e2e" -v

test-slow: ## Запустить медленные тесты
	@echo "$(GREEN)Запуск медленных тестов...$(NC)"
	python -m pytest tests/ -m "slow" -v

test-fast: ## Запустить только быстрые тесты
	@echo "$(GREEN)Запуск быстрых тестов...$(NC)"
	python -m pytest tests/ -m "not slow" -n auto -v

test-pipeline: ## Запустить тесты pipeline
	@echo "$(GREEN)Запуск тестов pipeline...$(NC)"
	python -m pytest tests/test_unified_pipeline.py -v

test-quality: ## Запустить тесты системы качества
	@echo "$(GREEN)Запуск тестов системы качества...$(NC)"
	python -m pytest tests/test_integration_phase2.py -v

test-loading: ## Запустить тесты загрузки данных
	@echo "$(GREEN)Запуск тестов загрузки данных...$(NC)"
	python -m pytest tests/test_universal_loader.py -v

test-metadata: ## Запустить тесты метаданных
	@echo "$(GREEN)Запуск тестов метаданных...$(NC)"
	python -m pytest tests/test_indexing_quality.py -v

test-all-loading: ## Запустить все тесты загрузки и метаданных
	@echo "$(GREEN)Запуск всех тестов загрузки...$(NC)"
	python -m pytest tests/test_universal_loader.py tests/test_indexing_quality.py -v

test-coverage: ## Запустить тесты с покрытием кода
	@echo "$(GREEN)Запуск тестов с покрытием...$(NC)"
	python -m pytest tests/ --cov=app --cov-report=html --cov-report=term

coverage-extended: ## Расширенное покрытие с порогом отказа
	@echo "$(GREEN)Запуск расширенного покрытия...$(NC)"
	python -m pytest tests/ --cov=app --cov=ingestion --cov=adapters --cov-report=term-missing --cov-report=xml --cov-report=html --cov-fail-under=70 -q

lint: ## Проверить код линтером
	@echo "$(GREEN)Проверка кода...$(NC)"
	python -m flake8 app/ tests/ scripts/ --max-line-length=120 --ignore=E203,W503
	python -m mypy app/ --ignore-missing-imports

format: ## Форматировать код
	@echo "$(GREEN)Форматирование кода...$(NC)"
	python -m black app/ tests/ scripts/ --line-length=120
	python -m isort app/ tests/ scripts/

clean: ## Очистить временные файлы
	@echo "$(GREEN)Очистка временных файлов...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/

# Команды для разработки
dev-setup: install ## Настроить среду разработки
	@echo "$(GREEN)Настройка среды разработки...$(NC)"
	python -m pip install -r requirements-dev.txt 2>/dev/null || echo "requirements-dev.txt не найден"
	@echo "$(GREEN)Среда разработки настроена!$(NC)"

# Команды для CI/CD
ci-test: ## Тесты для CI (без медленных тестов)
	@echo "$(GREEN)Запуск CI тестов...$(NC)"
	python -m pytest tests/ -m "not slow" -n auto --tb=short --maxfail=5

ci-test-all: ## Все тесты для CI
	@echo "$(GREEN)Запуск всех CI тестов...$(NC)"
	python -m pytest tests/ -n auto --tb=short --maxfail=3

# Команды для мониторинга
check-services: ## Проверить статус сервисов
	@echo "$(GREEN)Проверка сервисов...$(NC)"
	@echo "Redis: $$(python -c "import redis; r=redis.from_url('redis://localhost:6379'); print('✅ OK' if r.ping() else '❌ Ошибка')" 2>/dev/null || echo "❌ Недоступен")"
	@echo "Qdrant: $$(python -c "from qdrant_client import QdrantClient; c=QdrantClient('localhost'); print('✅ OK' if c.get_collections() else '❌ Ошибка')" 2>/dev/null || echo "❌ Недоступен")"

# Команды для индексации
reindex: ## Полная переиндексация через ingestion pipeline
	@echo "$(GREEN)Запуск полной переиндексации...$(NC)"
	python -m ingestion.run --source-type docusaurus --reindex-mode full --clear-collection

reindex-incremental: ## Инкрементальная переиндексация
	@echo "$(GREEN)Запуск инкрементальной переиндексации...$(NC)"
	python -m ingestion.run --source-type docusaurus --reindex-mode changed

# Команды для отладки
debug-collection: ## Отладка коллекции Qdrant
	@echo "$(GREEN)Отладка коллекции...$(NC)"
	python scripts/check_file_indexed.py

debug-pipeline: ## Отладка unified pipeline
	@echo "$(GREEN)Отладка pipeline...$(NC)"
	python -m pytest tests/test_unified_pipeline.py -v

debug-retrieval: ## Отладка поиска по URL
	@echo "$(GREEN)Отладка retrieval...$(NC)"
	python scripts/test_retrieval_for_url.py

# Показать информацию о проекте
info: ## Показать информацию о проекте
	@echo "$(GREEN)Информация о проекте:$(NC)"
	@echo "Python версия: $$(python --version)"
	@echo "Pytest версия: $$(python -m pytest --version)"
	@echo "Количество тестов: $$(python -m pytest --collect-only -q | grep -c 'test session starts' || echo '0')"
	@echo "Размер проекта: $$(du -sh . 2>/dev/null | cut -f1 || echo 'N/A')"
