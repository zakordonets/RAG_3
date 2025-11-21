from qdrant_client.models import Filter

from app.orchestration import orchestrator


def test_build_theme_filter_returns_filter():
    routing_result = {
        "primary_theme": "sdk_android",
        "requires_disambiguation": False,
        "router": "heuristic",
        "top_score": 0.9,
        "second_score": 0.1,
        "themes": ["sdk_android"],
    }
    flt = orchestrator._build_theme_filter(routing_result)
    assert isinstance(flt, Filter)
    keys = [cond.key for cond in flt.must]
    assert "domain" in keys
    assert "section" in keys
    assert "platform" in keys


def test_attach_theme_labels_sets_label():
    docs = [
        {"payload": {"domain": "sdk_docs", "section": "sdk", "platform": "android"}},
    ]
    orchestrator._attach_theme_labels(docs)
    assert docs[0]["payload"]["theme_label"]


def test_apply_theme_boost_prioritizes_primary_theme():
    routing_result = {
        "primary_theme": "sdk_android",
        "themes": ["sdk_android"],
        "router": "heuristic",
        "top_score": 0.9,
        "second_score": 0.3,
    }
    docs = [
        {"score": 0.55, "payload": {"domain": "chatcenter_user_docs", "section": "admin"}},
        {"score": 0.5, "payload": {"domain": "sdk_docs", "section": "sdk", "platform": "android"}},
    ]
    orchestrator._apply_theme_boost(docs, routing_result)
    # Документ SDK должен подняться выше благодаря бусту
    assert docs[0]["payload"]["domain"] == "sdk_docs"
