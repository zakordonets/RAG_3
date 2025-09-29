#!/usr/bin/env python3
"""
Система валидации индексированных данных.
Проверяет качество загруженных данных, выявляет пустые страницы и проблемы с индексацией.
"""

import sys
from pathlib import Path
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from loguru import logger

# Добавляем корневую директорию проекта в путь
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from app.services.optimized_pipeline import run_optimized_indexing
from ingestion.universal_loader import load_content_universal
from ingestion.crawl_cache import get_crawl_cache


@dataclass
class ValidationResult:
    """Результат валидации данных."""
    total_pages: int
    valid_pages: int
    empty_pages: int
    error_pages: int
    quality_score: float
    issues: List[str]
    recommendations: List[str]


class DataValidator:
    """Валидатор данных индексации."""
    
    def __init__(self):
        self.client = client
        self.collection = COLLECTION
        self.issues = []
        self.recommendations = []
    
    def validate_collection_data(self) -> ValidationResult:
        """Валидация данных в коллекции Qdrant."""
        logger.info("🔍 Начинаем валидацию данных в коллекции...")
        
        try:
            # Получаем информацию о коллекции
            collection_info = self.client.get_collection(self.collection)
            total_points = collection_info.points_count
            
            logger.info(f"📊 Всего точек в коллекции: {total_points}")
            
            if total_points == 0:
                return ValidationResult(
                    total_pages=0,
                    valid_pages=0,
                    empty_pages=0,
                    error_pages=0,
                    quality_score=0.0,
                    issues=["Коллекция пуста"],
                    recommendations=["Запустите индексацию данных"]
                )
            
            # Выбираем случайную выборку для анализа
            sample_size = min(100, total_points)
            logger.info(f"📋 Анализируем выборку из {sample_size} точек...")
            
            # Получаем случайные точки
            scroll_result = self.client.scroll(
                collection_name=self.collection,
                limit=sample_size,
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0]
            validation_results = self._validate_points(points)
            
            # Экстраполируем результаты на всю коллекцию
            scale_factor = total_points / sample_size
            scaled_results = self._scale_results(validation_results, scale_factor)
            
            return scaled_results
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации коллекции: {e}")
            return ValidationResult(
                total_pages=0,
                valid_pages=0,
                empty_pages=0,
                error_pages=0,
                quality_score=0.0,
                issues=[f"Ошибка валидации: {e}"],
                recommendations=["Проверьте подключение к Qdrant"]
            )
    
    def _validate_points(self, points: List[Dict]) -> ValidationResult:
        """Валидация конкретных точек."""
        total_pages = len(points)
        valid_pages = 0
        empty_pages = 0
        error_pages = 0
        
        for point in points:
            payload = point.get('payload', {})
            
            # Проверяем наличие обязательных полей
            if self._is_valid_point(payload):
                valid_pages += 1
            elif self._is_empty_point(payload):
                empty_pages += 1
            else:
                error_pages += 1
        
        # Вычисляем качество
        quality_score = valid_pages / total_pages if total_pages > 0 else 0.0
        
        # Анализируем проблемы
        issues = self._analyze_issues(points)
        recommendations = self._generate_recommendations(issues, quality_score)
        
        return ValidationResult(
            total_pages=total_pages,
            valid_pages=valid_pages,
            empty_pages=empty_pages,
            error_pages=error_pages,
            quality_score=quality_score,
            issues=issues,
            recommendations=recommendations
        )
    
    def _is_valid_point(self, payload: Dict) -> bool:
        """Проверяет, является ли точка валидной."""
        required_fields = ['text', 'url', 'title']
        
        # Проверяем наличие обязательных полей
        for field in required_fields:
            if field not in payload or not payload[field]:
                return False
        
        # Проверяем качество текста
        text = payload.get('text', '')
        if len(text.strip()) < 50:  # Минимальная длина текста
            return False
        
        # Проверяем URL
        url = payload.get('url', '')
        if not url.startswith('http'):
            return False
        
        return True
    
    def _is_empty_point(self, payload: Dict) -> bool:
        """Проверяет, является ли точка пустой."""
        text = payload.get('text', '')
        return len(text.strip()) < 10
    
    def _analyze_issues(self, points: List[Dict]) -> List[str]:
        """Анализирует проблемы в данных."""
        issues = []
        
        # Статистика по полям
        field_stats = {}
        text_lengths = []
        
        for point in points:
            payload = point.get('payload', {})
            
            # Считаем поля
            for field in payload.keys():
                field_stats[field] = field_stats.get(field, 0) + 1
            
            # Считаем длину текста
            text = payload.get('text', '')
            text_lengths.append(len(text))
        
        # Анализируем отсутствующие поля
        required_fields = ['text', 'url', 'title', 'content_type', 'section']
        for field in required_fields:
            if field not in field_stats:
                issues.append(f"Отсутствует поле '{field}' в {len(points) - field_stats.get(field, 0)} точках")
        
        # Анализируем длину текста
        if text_lengths:
            avg_length = sum(text_lengths) / len(text_lengths)
            short_texts = sum(1 for length in text_lengths if length < 50)
            
            if avg_length < 100:
                issues.append(f"Средняя длина текста слишком мала: {avg_length:.1f} символов")
            
            if short_texts > len(text_lengths) * 0.1:  # Более 10% коротких текстов
                issues.append(f"Слишком много коротких текстов: {short_texts} из {len(text_lengths)}")
        
        # Анализируем типы контента
        content_types = {}
        for point in points:
            payload = point.get('payload', {})
            content_type = payload.get('content_type', 'unknown')
            content_types[content_type] = content_types.get(content_type, 0) + 1
        
        if 'unknown' in content_types:
            issues.append(f"Неопределенный тип контента в {content_types['unknown']} точках")
        
        return issues
    
    def _generate_recommendations(self, issues: List[str], quality_score: float) -> List[str]:
        """Генерирует рекомендации по улучшению."""
        recommendations = []
        
        if quality_score < 0.8:
            recommendations.append("Запустите полную переиндексацию для улучшения качества")
        
        if any("Отсутствует поле" in issue for issue in issues):
            recommendations.append("Проверьте настройки извлечения метаданных")
        
        if any("длина текста" in issue for issue in issues):
            recommendations.append("Настройте параметры chunking для увеличения размера чанков")
        
        if any("тип контента" in issue for issue in issues):
            recommendations.append("Улучшите определение типа контента в universal_loader")
        
        if not recommendations:
            recommendations.append("Данные в хорошем состоянии, регулярно проверяйте качество")
        
        return recommendations
    
    def _scale_results(self, results: ValidationResult, scale_factor: float) -> ValidationResult:
        """Масштабирует результаты на всю коллекцию."""
        return ValidationResult(
            total_pages=int(results.total_pages * scale_factor),
            valid_pages=int(results.valid_pages * scale_factor),
            empty_pages=int(results.empty_pages * scale_factor),
            error_pages=int(results.error_pages * scale_factor),
            quality_score=results.quality_score,
            issues=results.issues,
            recommendations=results.recommendations
        )
    
    def validate_crawl_cache(self) -> Dict[str, Any]:
        """Валидация кеша crawling."""
        logger.info("🔍 Валидация кеша crawling...")
        
        try:
            cache = get_crawl_cache()
            stats = cache.get_cache_stats()
            
            # Проверяем несколько страниц из кеша
            cached_urls = list(cache.get_cached_urls())[:10]  # Первые 10 URL
            
            valid_cached = 0
            empty_cached = 0
            
            for url in cached_urls:
                page = cache.get_page(url)
                if page:
                    if page.html and len(page.html.strip()) > 100:
                        valid_cached += 1
                    else:
                        empty_cached += 1
            
            return {
                "total_cached": stats['total_pages'],
                "cache_size_mb": stats['total_size_mb'],
                "valid_cached": valid_cached,
                "empty_cached": empty_cached,
                "cache_quality": valid_cached / (valid_cached + empty_cached) if (valid_cached + empty_cached) > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации кеша: {e}")
            return {"error": str(e)}
    
    def test_content_loading(self, test_urls: List[str]) -> Dict[str, Any]:
        """Тестирует загрузку контента для конкретных URL."""
        logger.info(f"🧪 Тестирование загрузки контента для {len(test_urls)} URL...")
        
        results = {
            "total_tested": len(test_urls),
            "successful": 0,
            "failed": 0,
            "empty_content": 0,
            "errors": []
        }
        
        for url in test_urls:
            try:
                # Тестируем с разными стратегиями
                strategies = ['auto', 'jina', 'html']
                
                for strategy in strategies:
                    try:
                        result = load_content_universal(url, "", strategy)
                        
                        if result.get('content') and len(result['content'].strip()) > 50:
                            results["successful"] += 1
                            break
                        elif not result.get('content') or len(result['content'].strip()) < 10:
                            results["empty_content"] += 1
                        else:
                            results["failed"] += 1
                            
                    except Exception as e:
                        results["errors"].append(f"{url} ({strategy}): {e}")
                        continue
                        
            except Exception as e:
                results["errors"].append(f"{url}: {e}")
                results["failed"] += 1
        
        return results


def print_validation_report(result: ValidationResult, cache_stats: Dict, loading_test: Dict):
    """Выводит отчет о валидации."""
    print("\n" + "="*80)
    print("📊 ОТЧЕТ О ВАЛИДАЦИИ ДАННЫХ")
    print("="*80)
    
    # Общая статистика
    print(f"\n📈 ОБЩАЯ СТАТИСТИКА:")
    print(f"   Всего страниц: {result.total_pages}")
    print(f"   Валидных страниц: {result.valid_pages} ({result.valid_pages/result.total_pages*100:.1f}%)")
    print(f"   Пустых страниц: {result.empty_pages} ({result.empty_pages/result.total_pages*100:.1f}%)")
    print(f"   Ошибочных страниц: {result.error_pages} ({result.error_pages/result.total_pages*100:.1f}%)")
    print(f"   Качество данных: {result.quality_score*100:.1f}%")
    
    # Качество кеша
    if "error" not in cache_stats:
        print(f"\n💾 КЕШ CRAWLING:")
        print(f"   Закешированных страниц: {cache_stats['total_cached']}")
        print(f"   Размер кеша: {cache_stats['cache_size_mb']} MB")
        print(f"   Качество кеша: {cache_stats['cache_quality']*100:.1f}%")
    
    # Тест загрузки
    print(f"\n🧪 ТЕСТ ЗАГРУЗКИ КОНТЕНТА:")
    print(f"   Протестировано URL: {loading_test['total_tested']}")
    print(f"   Успешно загружено: {loading_test['successful']}")
    print(f"   Пустой контент: {loading_test['empty_content']}")
    print(f"   Ошибки загрузки: {loading_test['failed']}")
    
    # Проблемы
    if result.issues:
        print(f"\n⚠️ ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ:")
        for i, issue in enumerate(result.issues, 1):
            print(f"   {i}. {issue}")
    
    # Рекомендации
    if result.recommendations:
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        for i, rec in enumerate(result.recommendations, 1):
            print(f"   {i}. {rec}")
    
    # Ошибки загрузки
    if loading_test['errors']:
        print(f"\n❌ ОШИБКИ ЗАГРУЗКИ:")
        for error in loading_test['errors'][:5]:  # Показываем первые 5
            print(f"   • {error}")
        if len(loading_test['errors']) > 5:
            print(f"   ... и еще {len(loading_test['errors']) - 5} ошибок")
    
    print("\n" + "="*80)


def main():
    """Основная функция валидации."""
    print("🚀 Запуск валидации индексированных данных\n")
    
    validator = DataValidator()
    
    # 1. Валидация коллекции
    print("1️⃣ Валидация коллекции Qdrant...")
    collection_result = validator.validate_collection_data()
    
    # 2. Валидация кеша
    print("2️⃣ Валидация кеша crawling...")
    cache_stats = validator.validate_crawl_cache()
    
    # 3. Тест загрузки контента
    print("3️⃣ Тест загрузки контента...")
    test_urls = [
        "https://docs-chatcenter.edna.ru/docs/start/whatis",
        "https://docs-chatcenter.edna.ru/docs/agent/quick-start",
        "https://docs-chatcenter.edna.ru/docs/api/index",
        "https://docs-chatcenter.edna.ru/faq",
        "https://docs-chatcenter.edna.ru/blog"
    ]
    loading_test = validator.test_content_loading(test_urls)
    
    # 4. Выводим отчет
    print_validation_report(collection_result, cache_stats, loading_test)
    
    # 5. Определяем общий статус
    overall_quality = collection_result.quality_score
    cache_quality = cache_stats.get('cache_quality', 0)
    loading_quality = loading_test['successful'] / loading_test['total_tested'] if loading_test['total_tested'] > 0 else 0
    
    overall_score = (overall_quality + cache_quality + loading_quality) / 3
    
    print(f"\n🎯 ОБЩАЯ ОЦЕНКА КАЧЕСТВА: {overall_score*100:.1f}%")
    
    if overall_score >= 0.9:
        print("✅ Отличное качество данных!")
    elif overall_score >= 0.7:
        print("⚠️ Хорошее качество, есть возможности для улучшения")
    elif overall_score >= 0.5:
        print("❌ Среднее качество, рекомендуется переиндексация")
    else:
        print("🚨 Плохое качество, необходима полная переиндексация")
    
    return overall_score >= 0.7


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
