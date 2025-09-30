#!/usr/bin/env python3
"""
Check configuration values
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import CONFIG

def check_config():
    """Check configuration values"""
    print("🔍 Configuration Check")
    print("=" * 50)
    
    print(f"ENABLE_RAGAS_EVALUATION: {CONFIG.enable_ragas_evaluation}")
    print(f"QUALITY_DB_ENABLED: {CONFIG.quality_db_enabled}")
    print(f"ENABLE_QUALITY_METRICS: {CONFIG.enable_quality_metrics}")
    print(f"QUALITY_PREDICTION_THRESHOLD: {CONFIG.quality_prediction_threshold}")
    
    print("\n📊 Quality Configuration:")
    print(f"RAGAS_EVALUATION_SAMPLE_RATE: {CONFIG.ragas_evaluation_sample_rate}")
    print(f"RAGAS_BATCH_SIZE: {CONFIG.ragas_batch_size}")
    print(f"RAGAS_ASYNC_TIMEOUT: {CONFIG.ragas_async_timeout}")
    print(f"RAGAS_LLM_MODEL: {CONFIG.ragas_llm_model}")
    
    print("\n🗄️ Database Configuration:")
    print(f"DATABASE_URL: {CONFIG.database_url}")

if __name__ == "__main__":
    check_config()
