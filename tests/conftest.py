"""Shared fixtures and utilities for the test suite."""

from __future__ import annotations

import os
import random
from datetime import datetime, timezone
from typing import Dict
from unittest.mock import patch

import pytest
from freezegun import freeze_time

try:  # Optional dependency: used in some integration paths only.
    import numpy as np
except ImportError:  # pragma: no cover - numpy is optional for light profiles.
    np = None

try:  # Optional dependency: available in ML profiles.
    import torch
except ImportError:  # pragma: no cover - torch is optional outside ML jobs.
    torch = None


DEFAULT_SEED = 42
DEFAULT_FREEZE_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)
ENV_SEED_KEY = "PYTEST_GLOBAL_SEED"
ENV_FREEZE_KEY = "PYTEST_FREEZE_TIME"


def _normalized_freeze_target(value: str) -> str:
    """Accept ISO timestamps with optional trailing Z."""
    return value.replace("Z", "+00:00") if value.endswith("Z") else value


def _freeze_target_from_env() -> datetime:
    """Resolve the freeze timestamp from environment variables."""
    target = os.getenv(ENV_FREEZE_KEY)
    if not target:
        return DEFAULT_FREEZE_TIME

    normalized = _normalized_freeze_target(target)
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return DEFAULT_FREEZE_TIME


@pytest.fixture(autouse=True)
def global_seed() -> None:
    """Provide deterministic seeds for Python, NumPy and Torch RNGs."""
    seed_raw = os.getenv(ENV_SEED_KEY, str(DEFAULT_SEED))
    try:
        seed = int(seed_raw)
    except ValueError:
        seed = DEFAULT_SEED

    random.seed(seed)

    if np is not None:
        np.random.seed(seed)

    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    yield


@pytest.fixture(autouse=True)
def frozen_clock():
    """Freeze time globally to keep datetime-sensitive tests stable.

    Дополнительно:
    - ignore=['transformers'] — предотвращает ленивые импорты внутри transformers при сканировании модулей freezegun
    - tick=True — делает время монотонным и ненулевым для производственных тестов, которые измеряют длительность
    """
    freeze_value = _freeze_target_from_env()
    with freeze_time(freeze_value, tz_offset=0, ignore=["transformers"], tick=True) as frozen:
        yield frozen


@pytest.fixture
def mock_requests_get():
    """Fixture for mocking requests.get."""
    with patch("requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def mock_qdrant_client():
    """Fixture for mocking the Qdrant client."""
    with patch("app.services.search.retrieval.client") as mock_client:
        yield mock_client


@pytest.fixture
def sample_jina_content():
    """Sample payload emulating Jina Reader output."""
    return """Title: Demo Page
URL Source: https://example.org/docs/start/overview
Content Length: 2456
Language Detected: English
Published Time: 2024-07-24T10:30:00Z
Images: 3
Links: 12
Markdown Content:

# Heading

Page contents.
"""


@pytest.fixture
def sample_html_content():
    """Sample HTML document."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>Demo Page</title>
</head>
<body>
    <h1>Heading</h1>
    <p>Page contents.</p>
</body>
</html>"""


@pytest.fixture
def sample_markdown_content():
    """Sample Markdown document."""
    return """# Heading

Page contents.

## Subheading

More contents.
"""


@pytest.fixture
def test_urls() -> Dict[str, str]:
    """Collection of reference URLs used across tests."""
    return {
        "guide": "https://example.org/docs/start/overview",
        "api": "https://example.org/docs/api/messages",
        "faq": "https://example.org/faq",
        "changelog": "https://example.org/blog/release-6-16",
        "admin": "https://example.org/docs/admin/widget",
        "supervisor": "https://example.org/docs/supervisor/threadcontrol",
        "agent": "https://example.org/docs/agent/routing",
    }


class TestDataFactory:
    """Helper factory for building sample content."""

    @staticmethod
    def create_jina_content(
        title: str = "Demo Page",
        url: str = "https://example.org/docs/start/overview",
        content: str = "# Heading\n\nPage contents.",
    ) -> str:
        """Create a string payload similar to Jina Reader output."""
        return f"""Title: {title}
URL Source: {url}
Content Length: 2456
Language Detected: English
Published Time: 2024-07-24T10:30:00Z
Images: 3
Links: 12
Markdown Content:

{content}
"""

    @staticmethod
    def create_html_content(
        title: str = "Demo Page",
        content: str = "<h1>Heading</h1><p>Page contents.</p>",
    ) -> str:
        """Create an HTML snippet."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
</head>
<body>
    {content}
</body>
</html>"""

    @staticmethod
    def create_markdown_content(
        title: str = "Heading",
        content: str = "Page contents.",
    ) -> str:
        """Create a Markdown snippet."""
        return f"""# {title}

{content}

## Subheading

More contents.
"""


@pytest.fixture
def test_data_factory() -> TestDataFactory:
    """Expose the test data factory for convenience."""
    return TestDataFactory()
