from __future__ import annotations

import re
from typing import Dict, Any
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

    # Собираем дополнительные метаданные
    metadata = {"title": title, "content": content}
    
    # Извлекаем дополнительные метаданные из заголовков
    for line in lines[:20]:  # Первые 20 строк содержат метаданные
        line = line.strip()
        if line.startswith("URL Source:"):
            metadata['url_source'] = line[11:].strip()
        elif line.startswith("Content Length:"):
            try:
                metadata['content_length'] = int(line[15:].strip())
            except ValueError:
                pass
        elif line.startswith("Language Detected:"):
            metadata['language_detected'] = line[18:].strip()
        elif line.startswith("Published Time:"):
            metadata['published_time'] = line[15:].strip()
        elif line.startswith("Images:"):
            metadata['images_count'] = line[7:].strip()
        elif line.startswith("Links:"):
            metadata['links_count'] = line[6:].strip()
    
    return metadata


def extract_url_metadata(url: str) -> Dict[str, str]:
    """Извлекает метаданные из URL паттернов edna docs."""
    metadata = {}
    
    # Паттерны для определения секции и роли пользователя
    patterns = {
        r'/docs/start/': {'section': 'start', 'user_role': 'all', 'page_type': 'guide'},
        r'/docs/agent/': {'section': 'agent', 'user_role': 'agent', 'page_type': 'guide'},
        r'/docs/supervisor/': {'section': 'supervisor', 'user_role': 'supervisor', 'page_type': 'guide'},
        r'/docs/admin/': {'section': 'admin', 'user_role': 'admin', 'page_type': 'guide'},
        r'/docs/api/': {'section': 'api', 'user_role': 'integrator', 'page_type': 'api-reference'},
        r'/blog/': {'section': 'changelog', 'user_role': 'all', 'page_type': 'release-notes'},
        r'/faq': {'section': 'faq', 'user_role': 'all', 'page_type': 'faq'},
    }
    
    # Проверяем паттерны
    for pattern, meta in patterns.items():
        if re.search(pattern, url):
            metadata.update(meta)
            break
    
    # Определяем подтипы API
    if 'api' in metadata.get('section', ''):
        api_patterns = {
            r'/create': {'api_method': 'POST'},
            r'/get|/retrieve': {'api_method': 'GET'},
            r'/update|/modify': {'api_method': 'PUT'},
            r'/delete|/remove': {'api_method': 'DELETE'},
        }
        
        for pattern, meta in api_patterns.items():
            if re.search(pattern, url):
                metadata.update(meta)
                break
    
    # Определяем разрешения
    if 'admin' in url:
        metadata['permissions'] = 'ADMIN'
    elif 'supervisor' in url:
        metadata['permissions'] = 'SUPERVISOR'
    elif 'agent' in url:
        metadata['permissions'] = 'AGENT'
    else:
        metadata['permissions'] = 'ALL'
    
    return metadata


def parse_docusaurus_structure(soup: BeautifulSoup) -> Dict[str, Any]:
    """Извлекает структурные метаданные из Docusaurus HTML."""
    metadata = {}
    
    # Breadcrumb navigation
    breadcrumb_elements = soup.select('.theme-doc-breadcrumbs a')
    if breadcrumb_elements:
        metadata['breadcrumb_path'] = [link.get_text().strip() for link in breadcrumb_elements]
    
    # Sidebar category
    sidebar_active = soup.select('.theme-doc-sidebar-item-category-level-1.menu__list-item--collapsed')
    if sidebar_active:
        metadata['sidebar_category'] = sidebar_active[0].get_text().strip()
    
    # Section headers (H1-H6)
    headers = soup.select('h1, h2, h3, h4, h5, h6')
    if headers:
        metadata['section_headers'] = [h.get_text().strip() for h in headers]
        metadata['headers_h1'] = [h.get_text().strip() for h in soup.select('h1')]
        metadata['headers_h2'] = [h.get_text().strip() for h in soup.select('h2')]
        metadata['headers_h3'] = [h.get_text().strip() for h in soup.select('h3')]
    
    # Meta description
    meta_desc = soup.select_one('meta[name="description"]')
    if meta_desc:
        metadata['meta_description'] = meta_desc.get('content', '').strip()
    
    # API specific data - permissions
    permissions_elements = soup.select('blockquote')
    for element in permissions_elements:
        text = element.get_text().lower()
        if 'permissions' in text or 'разрешения' in text:
            # Извлекаем разрешения из текста
            permissions = []
            if 'integrator' in text:
                permissions.append('INTEGRATOR')
            if 'supervisor' in text:
                permissions.append('SUPERVISOR')
            if 'agent' in text:
                permissions.append('AGENT')
            if 'admin' in text:
                permissions.append('ADMIN')
            if permissions:
                metadata['permissions'] = permissions
            break
    
    # Извлекаем каналы из контента
    content_text = soup.get_text().lower()
    channels = []
    if 'telegram' in content_text:
        channels.append('telegram')
    if 'whatsapp' in content_text:
        channels.append('whatsapp')
    if 'viber' in content_text:
        channels.append('viber')
    if 'веб-виджет' in content_text or 'web-widget' in content_text:
        channels.append('web-widget')
    if 'мобильное приложение' in content_text or 'mobile' in content_text:
        channels.append('mobile')
    if channels:
        metadata['channels'] = channels
    
    # Извлекаем функции из контента
    features = []
    feature_keywords = ['маршрутизация', 'routing', 'бот', 'bot', 'вебхук', 'webhook', 'интеграция', 'integration']
    for keyword in feature_keywords:
        if keyword in content_text:
            features.append(keyword)
    if features:
        metadata['features'] = features
    
    return metadata


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
    
    # Базовый результат
    result = {"title": title, "content": text}
    
    # Добавляем структурные метаданные Docusaurus
    docusaurus_metadata = parse_docusaurus_structure(soup)
    result.update(docusaurus_metadata)
    
    return result
