#!/usr/bin/env python3
"""
Проверка содержимого кэша Redis
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import redis
from app.config import CONFIG
import json

def check_redis_cache():
    """Проверить содержимое кэша Redis"""
    print("🔍 Проверка содержимого кэша Redis")
    print("=" * 50)

    try:
        # Подключаемся к Redis
        r = redis.from_url(CONFIG.redis_url, decode_responses=True)

        # Проверяем подключение
        r.ping()
        print("✅ Подключение к Redis успешно")

        # Получаем информацию о базе данных
        info = r.info()
        print(f"\n📊 Информация о Redis:")
        print(f"   Версия: {info.get('redis_version', 'N/A')}")
        print(f"   Используемая память: {info.get('used_memory_human', 'N/A')}")
        print(f"   Количество ключей: {info.get('db0', {}).get('keys', 0)}")

        # Получаем все ключи
        keys = r.keys("*")
        print(f"\n🔑 Найдено {len(keys)} ключей в кэше:")

        # Группируем ключи по типам
        key_types = {}
        for key in keys:
            key_type = r.type(key)
            if key_type not in key_types:
                key_types[key_type] = []
            key_types[key_type].append(key)

        for key_type, key_list in key_types.items():
            print(f"\n   {key_type.upper()} ключи ({len(key_list)}):")
            for key in sorted(key_list)[:10]:  # Показываем первые 10
                ttl = r.ttl(key)
                ttl_str = f"TTL: {ttl}s" if ttl > 0 else "Без TTL" if ttl == -1 else "Истек"
                print(f"      • {key} ({ttl_str})")

            if len(key_list) > 10:
                print(f"      ... и еще {len(key_list) - 10} ключей")

        # Проверяем ключи, связанные с эмбеддингами
        print(f"\n🔍 Поиск ключей, связанных с эмбеддингами:")
        embedding_keys = [key for key in keys if 'embed' in key.lower()]

        if embedding_keys:
            print(f"   Найдено {len(embedding_keys)} ключей эмбеддингов:")
            for key in embedding_keys[:5]:
                ttl = r.ttl(key)
                ttl_str = f"TTL: {ttl}s" if ttl > 0 else "Без TTL" if ttl == -1 else "Истек"
                print(f"      • {key} ({ttl_str})")

                # Показываем пример содержимого
                try:
                    value = r.get(key)
                    if value:
                        if len(value) > 100:
                            print(f"        Содержимое: {value[:100]}...")
                        else:
                            print(f"        Содержимое: {value}")
                except:
                    print(f"        Не удалось прочитать содержимое")
        else:
            print("   Ключи эмбеддингов не найдены")

        # Проверяем ключи поиска
        print(f"\n🔍 Поиск ключей, связанных с поиском:")
        search_keys = [key for key in keys if any(term in key.lower() for term in ['search', 'query', 'result'])]

        if search_keys:
            print(f"   Найдено {len(search_keys)} ключей поиска:")
            for key in search_keys[:5]:
                ttl = r.ttl(key)
                ttl_str = f"TTL: {ttl}s" if ttl > 0 else "Без TTL" if ttl == -1 else "Истек"
                print(f"      • {key} ({ttl_str})")
        else:
            print("   Ключи поиска не найдены")

        return r, keys

    except Exception as e:
        print(f"❌ Ошибка при работе с Redis: {e}")
        return None, []

def clear_redis_cache(r, keys):
    """Очистить кэш Redis"""
    print(f"\n🧹 Очистка кэша Redis")
    print("=" * 50)

    if not r or not keys:
        print("❌ Нет подключения к Redis или ключей для очистки")
        return False

    try:
        # Очищаем все ключи
        deleted_count = r.flushdb()
        print(f"✅ Успешно очищено {deleted_count} ключей из кэша")

        # Проверяем, что кэш действительно пустой
        remaining_keys = r.keys("*")
        print(f"📊 Осталось ключей: {len(remaining_keys)}")

        if len(remaining_keys) == 0:
            print("✅ Кэш полностью очищен")
            return True
        else:
            print(f"⚠️  В кэше остались ключи: {remaining_keys}")
            return False

    except Exception as e:
        print(f"❌ Ошибка при очистке кэша: {e}")
        return False

def main():
    """Основная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Проверка и очистка кэша Redis')
    parser.add_argument('--clear', action='store_true',
                       help='Очистить кэш Redis')

    args = parser.parse_args()

    # Проверяем кэш
    r, keys = check_redis_cache()

    if args.clear:
        if r and keys:
            print(f"\n⚠️  ВНИМАНИЕ: Будет очищен весь кэш Redis!")
            response = input("Продолжить? (y/N): ")
            if response.lower() in ['y', 'yes', 'да']:
                clear_redis_cache(r, keys)
            else:
                print("❌ Очистка отменена")
    else:
        print(f"\n💡 Для очистки кэша используйте: python scripts/check_redis_cache.py --clear")

if __name__ == "__main__":
    main()
