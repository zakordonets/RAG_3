#!/usr/bin/env python3
"""
Диагностика проблем с кодировками
"""
import sys
import os
from loguru import logger

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_text_encoding(text: str, source: str = "unknown"):
    """Проверяет кодировку текста"""
    try:
        # Пробуем разные кодировки
        encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'iso-8859-1', 'windows-1252']

        for encoding in encodings:
            try:
                encoded = text.encode(encoding)
                decoded = encoded.decode(encoding)
                if decoded == text:
                    logger.success(f"✅ {source}: Текст корректно кодируется в {encoding}")
                    return encoding
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

        # Простая проверка на проблемные символы
        try:
            text.encode('utf-8')
            logger.info(f"✅ {source}: Текст корректно кодируется в UTF-8")
        except UnicodeEncodeError as e:
            logger.warning(f"⚠️  {source}: Проблемы с UTF-8: {e}")

        return None

    except Exception as e:
        logger.error(f"❌ {source}: Ошибка проверки кодировки: {e}")
        return None

def find_problematic_texts():
    """Находит проблемные тексты в кеше"""
    logger.info("🔍 Поиск проблемных текстов в кеше...")

    try:
        from ingestion.crawl_cache import CrawlCache

        cache = CrawlCache()
        problematic_pages = []

        # Проверяем первые 10 страниц из кеша
        for i, (url, page_data) in enumerate(list(cache.pages.items())[:10]):
            try:
                content = page_data.get('content', '')
                if content:
                    encoding = check_text_encoding(content, f"URL {i+1}")
                    if not encoding:
                        problematic_pages.append({
                            'url': url,
                            'content_preview': content[:200],
                            'content_length': len(content)
                        })
            except Exception as e:
                logger.error(f"Ошибка обработки URL {url}: {e}")

        logger.info(f"Найдено {len(problematic_pages)} проблемных страниц")
        return problematic_pages

    except Exception as e:
        logger.error(f"Ошибка доступа к кешу: {e}")
        return []

def test_encoding_fixes():
    """Тестирует исправления кодировок"""
    logger.info("🧪 Тестирование исправлений кодировок...")

    # Тестовые строки с проблемными символами
    test_strings = [
        "Обычный текст",
        "Текст с символами: ©®™€£¥",
        "Текст с переносами строк\nи табуляциями\t",
        "Текст с необычными символами: ñáéíóú",
        "Текст с эмодзи: 😀🎉🚀",
        "Текст с HTML: <p>Привет</p>",
        "Текст с URL: https://example.com/path?param=value",
    ]

    for i, test_text in enumerate(test_strings):
        encoding = check_text_encoding(test_text, f"Тест {i+1}")
        if encoding:
            logger.info(f"   Тест {i+1}: {encoding} - OK")
        else:
            logger.warning(f"   Тест {i+1}: Проблемы с кодировкой")

def check_system_encoding():
    """Проверяет системные настройки кодировки"""
    logger.info("🖥️  Проверка системных настроек кодировки...")

    # Python настройки
    logger.info(f"sys.getdefaultencoding(): {sys.getdefaultencoding()}")
    logger.info(f"sys.stdout.encoding: {sys.stdout.encoding}")
    logger.info(f"sys.stderr.encoding: {sys.stderr.encoding}")

    # Переменные окружения
    encoding_vars = ['PYTHONIOENCODING', 'LC_ALL', 'LANG', 'LC_CTYPE']
    for var in encoding_vars:
        value = os.environ.get(var, 'не установлено')
        logger.info(f"{var}: {value}")

    # Windows специфичные настройки
    if os.name == 'nt':
        logger.info("Windows detected:")
        logger.info(f"  os.environ.get('PYTHONIOENCODING'): {os.environ.get('PYTHONIOENCODING', 'не установлено')}")

        # Проверяем кодовую страницу
        import subprocess
        try:
            result = subprocess.run(['chcp'], capture_output=True, text=True, shell=True)
            logger.info(f"  Кодовая страница: {result.stdout.strip()}")
        except:
            logger.warning("  Не удалось определить кодовую страницу")

def suggest_encoding_fixes():
    """Предлагает исправления для проблем с кодировкой"""
    logger.info("💡 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ КОДИРОВОК:")

    logger.info("1. Установите переменную окружения:")
    logger.info("   set PYTHONIOENCODING=utf-8")

    logger.info("2. Для Windows PowerShell:")
    logger.info("   $env:PYTHONIOENCODING='utf-8'")

    logger.info("3. Добавьте в начало Python скриптов:")
    logger.info("   import os")
    logger.info("   os.environ['PYTHONIOENCODING'] = 'utf-8'")

    logger.info("4. Для обработки текста используйте:")
    logger.info("   text.encode('utf-8', errors='ignore').decode('utf-8')")

def main():
    """Основная функция диагностики"""
    logger.info("🔍 ДИАГНОСТИКА ПРОБЛЕМ С КОДИРОВКАМИ")

    check_system_encoding()
    test_encoding_fixes()
    problematic_pages = find_problematic_texts()

    if problematic_pages:
        logger.warning(f"⚠️  Найдено {len(problematic_pages)} проблемных страниц:")
        for page in problematic_pages[:3]:  # Показываем первые 3
            logger.warning(f"   URL: {page['url']}")
            logger.warning(f"   Превью: {page['content_preview'][:100]}...")

    suggest_encoding_fixes()

if __name__ == "__main__":
    main()
