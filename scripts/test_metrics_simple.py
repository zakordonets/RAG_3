#!/usr/bin/env python3
"""
Simple metrics test
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
import requests

def test_simple_metrics():
    """Test simple metrics recording"""
    print("🧪 Testing Simple Metrics...")

    try:
        # Test recording a simple metric
        print("📊 Recording RAGAS score...")
        get_metrics_collector().record_ragas_score("test_metric", 0.8, "test")

        print("📈 Recording combined quality score...")
        get_metrics_collector().record_combined_quality_score(0.8)

        print("🔄 Recording quality interaction...")
        get_metrics_collector().record_quality_interaction("test_interaction", "test", "test")

        print("✅ Metrics recorded!")

        # Check metrics endpoint
        print("\n🔍 Checking metrics endpoint...")
        response = requests.get("http://localhost:9002/metrics")
        if response.status_code == 200:
            content = response.text
            print(f"✅ Metrics endpoint accessible")
            print(f"Content length: {len(content)}")

            # Look for our test metrics
            if "rag_ragas_score" in content:
                print("✅ rag_ragas_score found in metrics")
                lines = content.split('\n')
                for line in lines:
                    if 'rag_ragas_score' in line and 'test_metric' in line:
                        print(f"Found: {line}")
            else:
                print("❌ rag_ragas_score NOT found in metrics")

            if "rag_combined_quality_score" in content:
                print("✅ rag_combined_quality_score found in metrics")
            else:
                print("❌ rag_combined_quality_score NOT found in metrics")

            if "rag_quality_interactions_total" in content:
                print("✅ rag_quality_interactions_total found in metrics")
            else:
                print("❌ rag_quality_interactions_total NOT found in metrics")

        else:
            print(f"❌ Failed to get metrics: {response.status_code}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_metrics()
