"""
Test RAGAS Integration
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from app.config import CONFIG
from app.services.quality.quality_manager import quality_manager
from app.services.quality.ragas_evaluator import ragas_evaluator

async def test_ragas_evaluation():
    """Test RAGAS evaluation"""
    logger.info("🧪 Testing RAGAS Evaluation")
    logger.info("=" * 40)
    
    # Test data
    query = "Как настроить маршрутизацию в edna Chat Center?"
    response = "Маршрутизация в edna Chat Center настраивается через API методы. Используйте transfer-thread для перенаправления диалога на оператора или очередь."
    contexts = [
        "Маршрутизация диалогов позволяет перенаправлять входящие сообщения на конкретных операторов или очереди.",
        "API метод transfer-thread используется для перенаправления диалога на оператора или очередь.",
        "Настройка кнопок клиента позволяет автоматизировать действия пользователей."
    ]
    sources = [
        "https://docs-chatcenter.edna.ru/docs/api/external-api/threads/transfer-thread",
        "https://docs-chatcenter.edna.ru/docs/advanced-settings/client-buttons"
    ]
    
    try:
        # Test RAGAS evaluation
        scores = await ragas_evaluator.evaluate_interaction(
            query=query,
            response=response,
            contexts=contexts,
            sources=sources
        )
        
        logger.info("✅ RAGAS Evaluation Results:")
        logger.info(f"   Faithfulness: {scores.get('faithfulness', 0.0):.3f}")
        logger.info(f"   Context Precision: {scores.get('context_precision', 0.0):.3f}")
        logger.info(f"   Answer Relevancy: {scores.get('answer_relevancy', 0.0):.3f}")
        logger.info(f"   Overall Score: {scores.get('overall_score', 0.0):.3f}")
        
        return scores
        
    except Exception as e:
        logger.error(f"❌ RAGAS evaluation failed: {e}")
        return None

async def test_quality_manager():
    """Test quality manager"""
    logger.info("🧪 Testing Quality Manager")
    logger.info("=" * 40)
    
    # Test data
    query = "Как создать бота в edna Chat Center?"
    response = "Для создания бота в edna Chat Center используйте API метод send-bot-answers для отправки ответов бота."
    contexts = [
        "Боты в edna Chat Center позволяют автоматизировать обработку сообщений.",
        "API метод send-bot-answers используется для отправки ответов от имени бота.",
        "Настройка ботов включает в себя создание правил и обработчиков сообщений."
    ]
    sources = [
        "https://docs-chatcenter.edna.ru/docs/api/external-api-bot/send-bot-answers"
    ]
    
    try:
        # Initialize quality manager
        await quality_manager.initialize()
        
        # Test interaction evaluation
        interaction_id = await quality_manager.evaluate_interaction(
            query=query,
            response=response,
            contexts=contexts,
            sources=sources
        )
        
        if interaction_id:
            logger.info(f"✅ Quality evaluation completed: {interaction_id}")
            
            # Test user feedback
            feedback_success = await quality_manager.add_user_feedback(
                interaction_id=interaction_id,
                feedback_type="positive",
                feedback_text="Отличный ответ, очень помог!"
            )
            
            if feedback_success:
                logger.info("✅ User feedback added successfully")
            else:
                logger.warning("⚠️ Failed to add user feedback")
            
            # Test statistics
            stats = await quality_manager.get_quality_statistics(days=7)
            if stats and "error" not in stats:
                logger.info("✅ Quality statistics retrieved:")
                logger.info(f"   Total interactions: {stats.get('total_interactions', 0)}")
                logger.info(f"   Avg RAGAS score: {stats.get('avg_ragas_score', 0.0):.3f}")
                logger.info(f"   Satisfaction rate: {stats.get('satisfaction_rate', 0.0):.1f}%")
            else:
                logger.warning("⚠️ Failed to get quality statistics")
                
        else:
            logger.error("❌ Quality evaluation failed")
            
    except Exception as e:
        logger.error(f"❌ Quality manager test failed: {e}")

async def test_user_feedback_simulation():
    """Simulate user feedback"""
    logger.info("🧪 Testing User Feedback Simulation")
    logger.info("=" * 40)
    
    try:
        # Simulate multiple interactions with feedback
        test_cases = [
            {
                "query": "Как настроить уведомления?",
                "response": "Уведомления настраиваются через панель администратора в разделе Настройки.",
                "contexts": ["Уведомления позволяют получать информацию о новых сообщениях и событиях."],
                "sources": ["https://docs-chatcenter.edna.ru/docs/settings/notifications"],
                "feedback": "positive"
            },
            {
                "query": "Как удалить пользователя?",
                "response": "Пользователи удаляются через API метод delete-user или через панель администратора.",
                "contexts": ["Удаление пользователей требует прав администратора."],
                "sources": ["https://docs-chatcenter.edna.ru/docs/api/user-management"],
                "feedback": "negative"
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            logger.info(f"Test case {i}: {case['query'][:30]}...")
            
            interaction_id = await quality_manager.evaluate_interaction(
                query=case["query"],
                response=case["response"],
                contexts=case["contexts"],
                sources=case["sources"]
            )
            
            if interaction_id:
                await quality_manager.add_user_feedback(
                    interaction_id=interaction_id,
                    feedback_type=case["feedback"],
                    feedback_text=f"Simulated {case['feedback']} feedback for test case {i}"
                )
                logger.info(f"✅ Test case {i} completed")
            else:
                logger.error(f"❌ Test case {i} failed")
        
        # Show final statistics
        stats = await quality_manager.get_quality_statistics(days=7)
        if stats and "error" not in stats:
            logger.info("📊 Final Statistics:")
            logger.info(f"   Total interactions: {stats.get('total_interactions', 0)}")
            logger.info(f"   Positive feedback: {stats.get('positive_feedback', 0)}")
            logger.info(f"   Negative feedback: {stats.get('negative_feedback', 0)}")
            logger.info(f"   Satisfaction rate: {stats.get('satisfaction_rate', 0.0):.1f}%")
            logger.info(f"   Avg RAGAS score: {stats.get('avg_ragas_score', 0.0):.3f}")
        
    except Exception as e:
        logger.error(f"❌ User feedback simulation failed: {e}")

async def main():
    """Main test function"""
    logger.info("🚀 RAGAS Integration Tests")
    logger.info("=" * 50)
    
    # Show configuration
    logger.info("Configuration:")
    logger.info(f"   RAGAS Evaluation: {CONFIG.enable_ragas_evaluation}")
    logger.info(f"   Quality DB Enabled: {CONFIG.quality_db_enabled}")
    logger.info(f"   Quality Metrics: {CONFIG.enable_quality_metrics}")
    logger.info("")
    
    # Test RAGAS evaluation
    await test_ragas_evaluation()
    logger.info("")
    
    # Test quality manager
    await test_quality_manager()
    logger.info("")
    
    # Test user feedback simulation
    await test_user_feedback_simulation()
    
    logger.info("")
    logger.info("🎉 RAGAS integration tests completed!")
    
    # Close connections
    await quality_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
