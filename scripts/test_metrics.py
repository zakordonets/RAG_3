#!/usr/bin/env python3
"""
Test metrics recording
"""
import os
# Не поднимать локальный экспортер метрик из теста
os.environ.setdefault("START_METRICS_SERVER", "false")

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.metrics import get_metrics_collector
from app.config import CONFIG

def test_metrics():
    """Test metrics recording"""
    print("🧪 Testing Metrics Recording...")
    print("=" * 50)

    print(f"ENABLE_QUALITY_METRICS: {CONFIG.enable_quality_metrics}")

    try:
        # Test recording RAGAS scores
        print("\n📊 Recording RAGAS scores...")
        get_metrics_collector().record_ragas_score("faithfulness", 0.8)
        get_metrics_collector().record_ragas_score("context_precision", 0.9)
        get_metrics_collector().record_ragas_score("answer_relevancy", 0.7)
        get_metrics_collector().record_ragas_score("overall_score", 0.8)

        # Test recording combined quality score
        print("📈 Recording combined quality score...")
        get_metrics_collector().record_combined_quality_score(0.8)

        # Test recording quality interaction
        print("🔄 Recording quality interaction...")
        get_metrics_collector().record_quality_interaction("ragas_evaluation", "api", "completed")
        get_metrics_collector().record_quality_interaction("user_feedback", "api", "positive")

        print("✅ All metrics recorded successfully!")

        # Check if metrics are available
        print("\n🔍 Checking metrics endpoint...")
        import requests
        response = requests.get("http://localhost:9002/metrics")
        if response.status_code == 200:
            content = response.text
            if "rag_ragas_score" in content and "0.8" in content:
                print("✅ Metrics found in endpoint!")
            else:
                print("❌ Metrics not found in endpoint")
                print("Content preview:", content[:500])
        else:
            print(f"❌ Failed to get metrics: {response.status_code}")

    except Exception as e:
        print(f"❌ Error recording metrics: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_metrics()
