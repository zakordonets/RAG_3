from __future__ import annotations

from bs4 import BeautifulSoup


def extract_main_text(soup: BeautifulSoup) -> str:
    # Docusaurus основная разметка
    main = soup.select_one('.theme-doc-markdown')
    container = main or soup
    parts: list[str] = []
    # Заголовок h1 внутри markdown
    h1 = container.find('h1')
    if h1:
        t = h1.get_text(' ', strip=True)
        if t:
            parts.append(t)
    # Остальной текст: параграфы и admonitions
    for node in container.find_all(['p', 'li']):
        txt = node.get_text(' ', strip=True)
        if txt:
            parts.append(txt)
    return "\n\n".join(parts)


def parse_api_documentation(content: str) -> dict:
    soup = BeautifulSoup(content, "lxml")
    return {
        "endpoints": [],
        "parameters": [],
        "examples": [],
        "responses": [],
    }


def parse_release_notes(content: str) -> dict:
    soup = BeautifulSoup(content, "lxml")
    return {
        "version": None,
        "features": [],
        "fixes": [],
        "breaking_changes": [],
    }


def parse_faq_content(content: str) -> list[dict]:
    soup = BeautifulSoup(content, "lxml")
    return []


def parse_guides(content: str) -> dict:
    soup = BeautifulSoup(content, "lxml")
    # Docusaurus заголовок часто в <title> и внутри markdown h1
    title = None
    h1 = soup.select_one('.theme-doc-markdown h1')
    if h1:
        title = h1.get_text(' ', strip=True)
    if not title and soup.title:
        title = soup.title.get_text(' ', strip=True)
    text = extract_main_text(soup)
    return {"title": title, "text": text}


