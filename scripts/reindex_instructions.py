"""
Скрипт для запуска переиндексации с включением конкретной страницы
"""
import sys
sys.path.insert(0, '.')

print("=" * 80)
print("🔄 ПЕРЕИНДЕКСАЦИЯ ДОКУМЕНТАЦИИ")
print("=" * 80)
print()
print("📋 Рекомендации:")
print()
print("1. Запустить полную переиндексацию:")
print("   python -m ingestion.run")
print()
print("2. Или использовать web crawler для конкретной страницы:")
print("   (создать адаптер для веб-сайта)")
print()
print("3. Проверить логи индексации:")
print("   tail -f logs/app.log")
print()
print("4. После индексации повторить диагностику:")
print("   python scripts/test_retrieval_for_url.py")
print()
print("=" * 80)
print()
print("⚠️  ВНИМАНИЕ: Текущая конфигурация использует Docusaurus файлы из:")
print("   C:\\CC_RAG\\docs")
print()
print("   Если вам нужно проиндексировать веб-сайт, измените конфигурацию:")
print("   1. Создайте website adapter в ingestion/adapters/")
print("   2. Или используйте старый crawler из ingestion/crawlers/")
print()
print("=" * 80)

# Проверяем, существует ли путь к docs
import os
docs_path = "C:\\CC_RAG\\docs"
if os.path.exists(docs_path):
    print(f"\n✅ Путь существует: {docs_path}")
    # Ищем файл whatis
    for root, dirs, files in os.walk(docs_path):
        for file in files:
            if 'whatis' in file.lower() or 'what-is' in file.lower():
                full_path = os.path.join(root, file)
                print(f"   📄 Найден файл: {full_path}")
else:
    print(f"\n❌ Путь НЕ существует: {docs_path}")
    print("   Нужно использовать web crawler для индексации с сайта")

print("\n" + "=" * 80)
