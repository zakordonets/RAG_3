from pathlib import Path
import importlib.util

MODULE_PATH = Path(__file__).resolve().parents[2] / "adapters" / "telegram" / "polling.py"
spec = importlib.util.spec_from_file_location("telegram_polling_module", MODULE_PATH)
telegram_polling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(telegram_polling)
extract_interaction_id = telegram_polling.extract_interaction_id


def test_extract_interaction_id_positive():
    interaction_id = extract_interaction_id("feedback_positive_interaction_deadbeef_123")
    assert interaction_id == "interaction_deadbeef_123"

    interaction_id = extract_interaction_id("feedback_negative_interaction_deadbeef")
    assert interaction_id == "interaction_deadbeef"


def test_extract_interaction_id_invalid():
    assert extract_interaction_id("feedback_interaction_only") is None
    assert extract_interaction_id("irrelevant_payload") is None
