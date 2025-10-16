from __future__ import annotations

from dataclasses import dataclass
from typing import List
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hypothesis import HealthCheck, given, settings, strategies as st

from app.services.core.llm_router import apply_url_whitelist, _normalize_url


BASE_DOMAINS = [f"site{idx}.example.com" for idx in range(1, 20)]
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BARE_URL_RE = re.compile(r"https?://[^\s)]+")


@dataclass
class WhitelistScenario:
    answer_md: str
    sources: List[dict[str, str]]
    allowed_present: set[str]
    allowed_markdown_snippets: List[str]
    disallowed_present: set[str]


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


@st.composite
def whitelist_scenarios(draw: st.DrawFn) -> WhitelistScenario:
    allowed_domains = draw(
        st.sets(st.sampled_from(BASE_DOMAINS), min_size=1, max_size=5)
    )
    remaining = [d for d in BASE_DOMAINS if d not in allowed_domains]
    disallowed_domains = draw(
        st.sets(st.sampled_from(remaining or BASE_DOMAINS), min_size=1, max_size=4)
    )

    def build_url(domain: str) -> str:
        scheme = draw(st.sampled_from(["http", "https"]))
        path = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/-_", min_size=0, max_size=12))
        suffix = "/" if draw(st.booleans()) else ""
        raw_domain = domain if draw(st.booleans()) else domain.upper()
        return f"{scheme}://{raw_domain}/{path}".rstrip("/") + suffix

    allowed_urls = [build_url(domain) for domain in allowed_domains]
    disallowed_urls = [build_url(domain) for domain in disallowed_domains]

    sources = [{"url": url} for url in allowed_urls]

    segments: list[str] = []
    allowed_present: set[str] = set()
    allowed_markdown_snippets: list[str] = []
    disallowed_present: set[str] = set()

    text_chunks = draw(
        st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=4, max_size=20),
            min_size=1,
            max_size=4,
        )
    )
    segments.extend(text_chunks)

    for url in allowed_urls:
        variant = draw(st.sampled_from(["markdown", "bare", "list"]))
        label = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=3, max_size=20))
        normalized = _normalize_url(url)
        if variant == "markdown":
            segment = f"[{label.strip()}]({url})"
            allowed_markdown_snippets.append(segment)
        elif variant == "list":
            segment = f"- [{label.strip()}]({url})"
            allowed_markdown_snippets.append(segment.split(" ", 1)[1])
        else:
            segment = url
        segments.append(segment)
        allowed_present.add(normalized)

    for url in disallowed_urls:
        variant = draw(st.sampled_from(["markdown", "bare", "paragraph"]))
        label = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=3, max_size=20))
        normalized = _normalize_url(url)
        if variant == "markdown":
            segments.append(f"[{label.strip()}]({url})")
        elif variant == "paragraph":
            segments.append(f"{label.strip()} {url}")
        else:
            segments.append(url)
        disallowed_present.add(normalized)

    answer_md = "\n\n".join(segment.strip() for segment in segments if segment.strip())

    return WhitelistScenario(
        answer_md=answer_md,
        sources=sources,
        allowed_present=allowed_present,
        allowed_markdown_snippets=allowed_markdown_snippets,
        disallowed_present=disallowed_present,
    )


def extract_urls(markdown: str) -> set[str]:
    urls = {_normalize_url(match[1]) for match in MARKDOWN_LINK_RE.findall(markdown)}
    urls |= {_normalize_url(match) for match in BARE_URL_RE.findall(markdown)}
    return {url for url in urls if url}


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(whitelist_scenarios())
def test_apply_url_whitelist_never_leaks_disallowed_links(scenario: WhitelistScenario) -> None:
    sanitized = apply_url_whitelist(scenario.answer_md, scenario.sources)

    present_urls = extract_urls(sanitized)

    assert present_urls <= scenario.allowed_present, "Sanitized markdown must only contain whitelisted URLs"

    for url in scenario.disallowed_present:
        assert url not in present_urls, f"Disallowed URL {url} should be removed"


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(whitelist_scenarios())
def test_apply_url_whitelist_preserves_allowed_markdown_structure(scenario: WhitelistScenario) -> None:
    sanitized = apply_url_whitelist(scenario.answer_md, scenario.sources)

    for snippet in scenario.allowed_markdown_snippets:
        normalized_snippet = _normalize_text(snippet)
        sanitized_normalized = _normalize_text(sanitized)
        assert normalized_snippet in sanitized_normalized, "Approved markdown links should remain intact"
