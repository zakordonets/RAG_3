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
    # Проверяем, является ли контент от Jina Reader
    if content.startswith("Title:") and "URL Source:" in content:
        parsed = parse_jina_content(content)
        return {
            "title": parsed["title"],
            "content": parsed["content"],
            "endpoints": [],
            "parameters": [],
            "examples": [],
            "responses": [],
        }

    soup = BeautifulSoup(content, "lxml")
    return {
        "endpoints": [],
        "parameters": [],
        "examples": [],
        "responses": [],
    }


def parse_release_notes(content: str) -> dict:
    # Проверяем, является ли контент от Jina Reader
    if content.startswith("Title:") and "URL Source:" in content:
        parsed = parse_jina_content(content)
        return {
            "title": parsed["title"],
            "text": parsed["content"],
            "version": None,
            "features": [],
            "fixes": [],
            "breaking_changes": [],
        }

    soup = BeautifulSoup(content, "lxml")
    return {
        "version": None,
        "features": [],
        "fixes": [],
        "breaking_changes": [],
    }


def parse_faq_content(content: str) -> list[dict]:
    # Проверяем, является ли контент от Jina Reader
    if content.startswith("Title:") and "URL Source:" in content:
        parsed = parse_jina_content(content)
        return [{"title": parsed["title"], "content": parsed["content"]}]

    soup = BeautifulSoup(content, "lxml")
    return []


def parse_jina_content(jina_content: str) -> dict:
    """Парсит контент от Jina Reader"""
    if not jina_content:
        return {"title": "", "content": ""}

    # Извлекаем заголовок из первой строки
    title = ""
    content = ""

    lines = jina_content.split('\n')

    # Ищем заголовок в формате "Title: ..."
    for line in lines:
        if line.startswith("Title:"):
            title_part = line.split("Title:")[1].strip()
            if "|" in title_part:
                title = title_part.split("|")[0].strip()
            else:
                title = title_part
            break

    # Ищем начало контента после "Markdown Content:"
    content_started = False
    content_lines = []
    skip_next_empty = False

    for line in lines:
        if line.startswith("Markdown Content:"):
            content_started = True
            skip_next_empty = True
            continue

        if content_started:
            # Пропускаем первую пустую строку после "Markdown Content:"
            if skip_next_empty and not line.strip():
                skip_next_empty = False
                continue

            # Останавливаемся на следующем заголовке или URL Source или Published Time
            if (line.startswith("Title:") or
                line.startswith("URL Source:") or
                line.startswith("Published Time:")):
                break

            content_lines.append(line)

    if content_lines:
        content = '\n'.join(content_lines).strip()

    # Если не нашли через "Markdown Content:", берем все после заголовка
    if not content and title:
        # Ищем контент после заголовка
        title_found = False
        content_lines = []

        for line in lines:
            if line.startswith("Title:"):
                title_found = True
                continue

            # Останавливаемся на URL Source или следующем заголовке
            if line.startswith("URL Source:") or (title_found and line.startswith("Title:")):
                break

            if title_found and line.strip():
                content_lines.append(line)

        if content_lines:
            content = '\n'.join(content_lines).strip()

    return {"title": title, "content": content}


def parse_guides(content: str) -> dict:
    # Проверяем, является ли контент от Jina Reader
    if content.startswith("Title:") and "URL Source:" in content:
        parsed = parse_jina_content(content)
        return {"title": parsed["title"], "content": parsed["content"]}

    # Обычная обработка HTML
    soup = BeautifulSoup(content, "lxml")
    # Docusaurus заголовок часто в <title> и внутри markdown h1
    title = None
    h1 = soup.select_one('.theme-doc-markdown h1')
    if h1:
        title = h1.get_text(' ', strip=True)
    if not title and soup.title:
        title = soup.title.get_text(' ', strip=True)
    text = extract_main_text(soup)
    return {"title": title, "content": text}
