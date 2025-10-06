"""
Initialize Quality Database for RAGAS evaluation
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from app.config import CONFIG
from app.models.quality_interaction import quality_db, QualityInteractionData
from app.services.quality.quality_manager import quality_manager
from datetime import datetime

async def create_quality_tables():
    """Create quality database tables"""
    logger.info("Initializing quality database...")
    
    try:
        await quality_db.initialize()
        logger.info("✅ Quality database initialized successfully")
        logger.info(f"Database URL: {CONFIG.database_url}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize quality database: {e}")
        return False
    
    return True

async def verify_database_schema():
    """Verify database schema"""
    logger.info("Verifying database schema...")
    
    try:
        # Create test interaction
        test_data = QualityInteractionData(
            interaction_id="test_initialization",
            query="Test query for database initialization",
            response="Test response for database initialization",
            contexts=["Test context 1", "Test context 2"],
            sources=["https://example.com/doc1", "https://example.com/doc2"],
            ragas_faithfulness=0.8,
            ragas_context_precision=0.7,
            ragas_answer_relevancy=0.9,
            ragas_overall_score=0.8,
            combined_score=0.8,
            created_at=datetime.utcnow()
        )
        
        success = await quality_db.save_interaction(test_data)
        if success:
            logger.info("✅ Database schema verification successful")
            logger.info("Test interaction created and verified")
            return True
        else:
            logger.error("❌ Failed to create test interaction")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database schema verification failed: {e}")
        return False

async def show_database_info():
    """Show database information"""
    logger.info("📊 Database Information:")
    logger.info(f"   Database URL: {CONFIG.database_url}")
    
    try:
        recent_interactions = await quality_db.get_recent_interactions(limit=5)
        logger.info(f"   Total interactions: {len(recent_interactions)}")
        
        if recent_interactions:
            logger.info("📝 Recent interactions:")
            for interaction in recent_interactions:
                logger.info(f"   - {interaction.interaction_id}: {interaction.query[:50]}...")
        
        # Show quality statistics
        stats = await quality_manager.get_quality_statistics(days=7)
        if stats and "error" not in stats:
            logger.info("📈 Quality trends (7 days): {} data points".format(stats.get('total_interactions', 0)))
        
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")

async def main():
    """Main function"""
    logger.info("🚀 Quality Database Initialization")
    logger.info("=" * 50)
    
    # Show configuration
    logger.info("Configuration:")
    logger.info(f"   Quality DB Enabled: {CONFIG.quality_db_enabled}")
    logger.info(f"   Database URL: {CONFIG.database_url}")
    logger.info(f"   RAGAS Evaluation: {CONFIG.enable_ragas_evaluation}")
    logger.info(f"   Quality Metrics: {CONFIG.enable_quality_metrics}")
    logger.info("")
    
    # Initialize database
    if not await create_quality_tables():
        return
    
    # Verify schema
    if not await verify_database_schema():
        return
    
    logger.info("")
    
    # Show database info
    await show_database_info()
    
    logger.info("")
    logger.info("🎉 Quality database is ready to use!")
    logger.info("")
    logger.info("Next steps:")
    logger.info("   1. Start RAG API with quality evaluation enabled")
    logger.info("   2. Test with some queries to generate quality data")
    logger.info("   3. Check Grafana dashboard for quality metrics")

if __name__ == "__main__":
    asyncio.run(main())
