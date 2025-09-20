#!/usr/bin/env python3
"""
Скрипт для очистки старых скриптов индексации

Этот скрипт удаляет устаревшие скрипты индексации, которые заменены
единым модулем scripts/indexer.py
"""

import os
import sys
from pathlib import Path

def main():
    """Удаляет старые скрипты индексации"""

    # Список скриптов для удаления (заменены на scripts/indexer.py)
    scripts_to_remove = [
        "scripts/reindex.py",
        "scripts/full_reindex.py",
        "scripts/full_reindex_with_titles.py",
        "scripts/run_full_reindex.py"
    ]

    print("🧹 Очистка старых скриптов индексации...")
    print("=" * 50)

    removed_count = 0
    for script_path in scripts_to_remove:
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
                print(f"✅ Удален: {script_path}")
                removed_count += 1
            except Exception as e:
                print(f"❌ Ошибка при удалении {script_path}: {e}")
        else:
            print(f"⏭️ Не найден: {script_path}")

    print(f"\n📊 Удалено {removed_count} файлов")
    print("\n💡 Теперь используйте единый модуль:")
    print("   python scripts/indexer.py --help")
    print("\n🔄 Основные команды:")
    print("   python scripts/indexer.py status")
    print("   python scripts/indexer.py reindex --mode full")
    print("   python scripts/indexer.py init")

if __name__ == "__main__":
    main()
