from __future__ import annotations
import re


CONTENTREF_RE = re.compile(
    r"<ContentRef\s+url=['\"]([^'\"]+)['\"]>(.*?)</ContentRef>", re.DOTALL
)




def replace_contentref(text: str, site_base: str) -> str:
    """Заменяет <ContentRef url="...">Label</ContentRef> на
    "Label (см. ABS_URL)". Относительные URL (начинающиеся с '/')
    резолвятся через site_base.
    """


    def _sub(m):
        url = m.group(1)
        label = (m.group(2) or "").strip()
        abs_url = site_base.rstrip("/") + url if url.startswith("/") else url
        return f"{label} (см. {abs_url})"


    return CONTENTREF_RE.sub(_sub, text)
