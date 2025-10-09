"""
Диагностический скрипт для проверки, попадает ли конкретная страница в результаты поиска.
Использование: python scripts/test_retrieval_for_url.py
"""
import sys
sys.path.insert(0, '.')

from app.config import CONFIG
from app.services.core.embeddings import embed_unified
from app.services.search.retrieval import hybrid_search, client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue
from loguru import logger

def check_url_in_collection(target_url: str) -> list[dict]:
    """Проверяет, есть ли URL в коллекции Qdrant."""
    try:
        # Проверяем оба поля: url и canonical_url
        results_url = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="url", match=MatchValue(value=target_url))]
            ),
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        
        results_canonical = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="canonical_url", match=MatchValue(value=target_url))]
            ),
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        
        # Объединяем результаты
        points = []
        if results_url and results_url[0]:
            points.extend(results_url[0])
        if results_canonical and results_canonical[0]:
            points.extend(results_canonical[0])
        
        return [
            {
                "id": point.id,
                "payload": point.payload
            }
            for point in points
        ]
    except Exception as e:
        logger.error(f"Ошибка при поиске URL в коллекции: {e}")
        return []


def test_retrieval_for_query(query: str, target_url: str, top_k: int = 30):
    """
    Тестирует retrieval для конкретного запроса и проверяет, попадает ли целевой URL.

    Args:
        query: Текст запроса
        target_url: URL страницы, которую ищем
        top_k: Количество результатов для проверки
    """
    print("=" * 80)
    print(f"🔍 ДИАГНОСТИКА RETRIEVAL")
    print("=" * 80)
    print(f"Запрос: {query}")
    print(f"Целевой URL: {target_url}")
    print(f"Проверяем топ-{top_k} результатов")
    print("=" * 80)

    # 1. Проверяем, есть ли URL в коллекции вообще
    print("\n📦 ШАГ 1: Проверка наличия URL в коллекции")
    print("-" * 80)

    indexed_chunks = check_url_in_collection(target_url)

    if not indexed_chunks:
        print(f"❌ URL не найден в коллекции: {target_url}")
        print("   Возможные причины:")
        print("   - Страница не была проиндексирована")
        print("   - URL записан в другом формате")
        print("   - Коллекция пустая или используется другое имя")

        # Попробуем найти похожие URL
        print("\n🔎 Поиск похожих URL...")
        try:
            all_points = client.scroll(
                collection_name=COLLECTION,
                limit=10,
                with_payload=True,
                with_vectors=False
            )
            if all_points[0]:
                print(f"   Найдено {len(all_points[0])} документов. Примеры URL:")
                for i, point in enumerate(all_points[0][:5], 1):
                    url = point.payload.get('url', point.payload.get('site_url', 'N/A'))
                    print(f"   {i}. {url}")
        except Exception as e:
            print(f"   Ошибка: {e}")

        return False

    print(f"✅ URL найден! Количество чанков: {len(indexed_chunks)}")
    for i, chunk in enumerate(indexed_chunks[:3], 1):
        payload = chunk['payload']
        print(f"\n   Чанк {i}:")
        print(f"   - ID: {chunk['id']}")
        print(f"   - chunk_index: {payload.get('chunk_index', 'N/A')}")
        print(f"   - title: {payload.get('title', 'N/A')[:80]}")
        text_preview = payload.get('text', '')[:150].replace('\n', ' ')
        print(f"   - text: {text_preview}...")

    # 2. Генерируем embeddings для запроса
    print("\n\n🧬 ШАГ 2: Генерация embeddings для запроса")
    print("-" * 80)

    try:
        embedding_result = embed_unified(
            query,
            max_length=CONFIG.embedding_max_length_query,
            return_dense=True,
            return_sparse=CONFIG.use_sparse,
            return_colbert=False,
            context="query"
        )

        q_dense = embedding_result.get('dense_vecs', [[]])[0]

        q_sparse = {"indices": [], "values": []}
        if CONFIG.use_sparse and embedding_result.get('lexical_weights'):
            lex_weights = embedding_result['lexical_weights'][0]
            if lex_weights:
                q_sparse = {
                    "indices": [int(k) for k in lex_weights.keys()],
                    "values": [float(v) for k, v in lex_weights.items()]
                }

        print(f"✅ Embeddings сгенерированы:")
        print(f"   - Dense вектор: размерность {len(q_dense)}")
        print(f"   - Sparse вектор: {len(q_sparse.get('indices', []))} ненулевых элементов")

    except Exception as e:
        print(f"❌ Ошибка генерации embeddings: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 3. Выполняем гибридный поиск
    print("\n\n🔎 ШАГ 3: Выполнение гибридного поиска")
    print("-" * 80)

    try:
        results = hybrid_search(
            query_dense=q_dense,
            query_sparse=q_sparse,
            k=top_k
        )

        print(f"✅ Поиск выполнен: получено {len(results)} результатов")

    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. Проверяем, есть ли целевой URL в результатах
    print("\n\n📊 ШАГ 4: Анализ результатов")
    print("-" * 80)

    target_found = False
    target_positions = []

    for idx, hit in enumerate(results, 1):
        payload = hit.get('payload', {})
        url = payload.get('url', payload.get('canonical_url', payload.get('site_url', '')))
        
        if url == target_url:
            target_found = True
            target_positions.append(idx)

            print(f"\n✅ ЦЕЛЕВОЙ URL НАЙДЕН на позиции #{idx}!")
            print(f"   - Score (RRF): {hit.get('rrf_score', 'N/A'):.4f}")
            print(f"   - Score (Boosted): {hit.get('boosted_score', 'N/A'):.4f}")
            print(f"   - Title: {payload.get('title', 'N/A')}")
            print(f"   - chunk_index: {payload.get('chunk_index', 'N/A')}")
            text_preview = payload.get('text', '')[:200].replace('\n', ' ')
            print(f"   - Text: {text_preview}...")

    if not target_found:
        print(f"\n❌ ЦЕЛЕВОЙ URL НЕ НАЙДЕН в топ-{top_k} результатах")
        print("\n🔝 Топ-5 результатов:")

        for idx, hit in enumerate(results[:5], 1):
            payload = hit.get('payload', {})
            url = payload.get('url', payload.get('canonical_url', payload.get('site_url', 'N/A')))
            title = payload.get('title', 'N/A')

            print(f"\n   #{idx} (score: {hit.get('boosted_score', 0):.4f}):")
            print(f"   - URL: {url}")
            print(f"   - Title: {title[:80]}")
            text_preview = payload.get('text', '')[:150].replace('\n', ' ')
            print(f"   - Text: {text_preview}...")

        # Анализ причин
        print("\n\n💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
        print("   1. Семантическое несоответствие между запросом и текстом страницы")
        print("   2. Другие страницы имеют более высокий score по boosting")
        print("   3. Недостаточный k (попробуйте увеличить top_k)")
        print("   4. Проблема с индексацией (проверьте качество чанков)")

        # Проверяем, есть ли ключевые слова из запроса в тексте
        query_words = set(query.lower().split())
        print("\n   🔍 Анализ чанков целевого URL:")
        for i, chunk in enumerate(indexed_chunks[:3], 1):
            text = chunk['payload'].get('text', '').lower()
            matched_words = query_words & set(text.split())
            print(f"   Чанк {i}: совпадений слов = {len(matched_words)}/{len(query_words)}")
            if matched_words:
                print(f"           Совпадающие слова: {', '.join(list(matched_words)[:5])}")

    else:
        print(f"\n\n✅ РЕЗУЛЬТАТ: URL найден на позициях {target_positions}")
        if target_positions[0] <= 10:
            print("   👍 Отлично! URL в топ-10")
        elif target_positions[0] <= 20:
            print("   ⚠️  URL в топ-20, но не в топ-10. Возможно стоит улучшить boosting")
        else:
            print("   ⚠️  URL за пределами топ-20. Рекомендуется проверить boosting и индексацию")

    print("\n" + "=" * 80)
    return target_found


if __name__ == "__main__":
    # Ваш тестовый запрос
    QUERY = "какие каналы я могу подключить?"
    TARGET_URL = "https://docs-chatcenter.edna.ru/docs/start/whatis"
    TOP_K = 30  # Проверяем топ-30 результатов

    result = test_retrieval_for_query(QUERY, TARGET_URL, TOP_K)

    print("\n" + "=" * 80)
    if result:
        print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА: URL НАЙДЕН")
    else:
        print("❌ ДИАГНОСТИКА ЗАВЕРШЕНА: URL НЕ НАЙДЕН или НЕ ПРОИНДЕКСИРОВАН")
    print("=" * 80)
