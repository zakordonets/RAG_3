from qdrant_client.models import Filter

from app.services.infrastructure import orchestrator


def test_build_theme_filter_returns_filter():
    routing_result = {
        "primary_theme": "sdk_android",
        "requires_disambiguation": False,
    }
    flt = orchestrator._build_theme_filter(routing_result)
    assert isinstance(flt, Filter)
    keys = [cond.key for cond in flt.must]
    assert "domain" in keys
    assert "section" in keys
    assert "platform" in keys


def test_build_clarification_message_lists_themes():
    routing_result = {
        "requires_disambiguation": True,
        "themes": ["sdk_android", "user_admin"],
    }
    msg = orchestrator._build_clarification_message(routing_result)
    assert "SDK для Android" in msg
    assert "АРМ администратора" in msg


def test_attach_theme_labels_sets_label():
    docs = [
        {"payload": {"domain": "sdk_docs", "section": "sdk", "platform": "android"}},
    ]
    orchestrator._attach_theme_labels(docs)
    assert docs[0]["payload"]["theme_label"]
