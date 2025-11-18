import os
from pathlib import Path

import pytest

from app.config.boosting_config import BoostingConfig, get_boosting_config, reset_boosting_config_cache, BOOSTING_CONFIG_ENV
from app.retrieval.boosting import boost_hits, boost_score


def test_boost_hits_prioritizes_overview():
    cfg = BoostingConfig(page_type_boosts={"overview": 2.0})
    hits = [
        {"rrf_score": 1.0, "payload": {"page_type": "overview"}},
        {"rrf_score": 1.0, "payload": {"page_type": "other"}},
    ]

    boosted = boost_hits(hits, cfg, context={})
    assert boosted[0]["payload"]["page_type"] == "overview"
    assert boosted[0]["boosted_score"] > boosted[1]["boosted_score"]


def test_boost_score_uses_section_and_platform():
    cfg = BoostingConfig(section_boosts={"sdk": 1.2}, platform_boosts={"android": 1.1})
    payload = {"section": "sdk", "platform": "android"}
    boosted = boost_score(1.0, payload, cfg, context={})
    assert boosted == pytest.approx(1.32)


def test_get_boosting_config_reads_external_file(tmp_path, monkeypatch):
    config_text = "page_type_boosts:\n  overview: 1.7\n"
    cfg_path = Path(tmp_path) / "boosting.yaml"
    cfg_path.write_text(config_text, encoding="utf-8")

    monkeypatch.setenv(BOOSTING_CONFIG_ENV, str(cfg_path))
    reset_boosting_config_cache()
    cfg = get_boosting_config()
    assert cfg.page_type_boosts["overview"] == pytest.approx(1.7)

    monkeypatch.delenv(BOOSTING_CONFIG_ENV, raising=False)
    reset_boosting_config_cache()
