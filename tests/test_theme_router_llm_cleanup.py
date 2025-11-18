import pytest

from app.retrieval.theme_router import _strip_code_fence


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("```json\n[{\"theme_id\": \"sdk_android\"}]\n```", '[{"theme_id": "sdk_android"}]'),
        ("JSON [{\"theme_id\": \"sdk_ios\"}]", '[{"theme_id": "sdk_ios"}]'),
        ("   [{\"theme_id\": \"user_admin\"}]  ", '[{"theme_id": "user_admin"}]'),
    ],
)
def test_strip_code_fence(raw, expected):
    assert _strip_code_fence(raw) == expected
