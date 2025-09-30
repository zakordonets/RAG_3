from __future__ import annotations

"""
Временный миграционный слой для функций из ingestion/parsers.py.
Удалить после полной миграции потребителей на новый ContentProcessor.
"""

import time
import re
from typing import Dict, Any, List
from loguru import logger
from bs4 import BeautifulSoup

# Импортируем новые парсеры
from ingestion.processors.content_processor import ContentProcessor
from ingestion.processors.jina_parser import JinaParser
from ingestion.processors.html_parser import HTMLParser
from ingestion.processors.markdown_parser import MarkdownParser


def extract_url_metadata(url: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ заглушка: возвращает базовые метаданные по URL."""
    try:
        # Базовые поля
        metadata: Dict[str, Any] = {
            "url": url,
            "source": "migrated",
            "extracted_at": time.time(),
        }

        # Выделяем path для определения раздела/роли
        # Пример: https://domain.tld/docs/agent/routing -> section=agent
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            section = None
            if path_parts:
                # Docusaurus обычно начинается с 'docs' или 'blog'
                if path_parts[0] == 'docs':
                    if len(path_parts) > 1:
                        section = path_parts[1]
                elif path_parts[0] == 'blog':
                    section = 'changelog'
                else:
                    section = path_parts[0]
            if section:
                metadata['section'] = section
            # user_role по умолчанию выводим из section, если совпадает
            role_candidates = {"agent", "admin", "supervisor", "integrator"}
            if section in role_candidates:
                metadata['user_role'] = section
            elif section == 'api':
                metadata['user_role'] = 'integrator'
            elif section in {'changelog', 'blog', 'start'}:
                metadata['user_role'] = 'all'
            else:
                metadata['user_role'] = 'unspecified'
        except Exception:
            metadata['user_role'] = 'unspecified'

        return metadata
    except Exception as e:
        logger.warning(f"Migration fallback for extract_url_metadata({url}): {e}")
        return {"url": url}


def extract_main_text(soup: BeautifulSoup) -> str:
    """МИГРАЦИОННАЯ функция: извлекает основной текст из BeautifulSoup."""
    try:
        # Используем новый HTML парсер
        html_parser = HTMLParser()
        content = str(soup)
        processed = html_parser.parse("http://example.com", content)
        return processed.content
    except Exception as e:
        logger.warning(f"Migration fallback for extract_main_text: {e}")
        # Fallback к старой логике
        main = soup.select_one('.theme-doc-markdown')
        container = main or soup
        parts: List[str] = []
        h1 = container.find('h1')
        if h1:
            t = h1.get_text(' ', strip=True)
            if t:
                parts.append(t)
        for node in container.find_all(['p', 'li']):
            txt = node.get_text(' ', strip=True)
            if txt:
                parts.append(txt)
        return "\n\n".join(parts)


def parse_jina_content(content: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ функция: парсит контент от Jina Reader."""
    try:
        jina_parser = JinaParser()
        processed = jina_parser.parse("http://example.com", content)
        # Попробуем извлечь дополнительные поля из исходного текста формата Jina
        url_source = None
        language_detected = None
        content_length = None
        published_time = None
        permissions = []

        try:
            # Разбираем шапку
            header_lines = []
            for line in content.splitlines():
                if line.strip().startswith('Markdown Content:'):
                    break
                header_lines.append(line.rstrip())
            header_text = '\n'.join(header_lines)
            m = re.search(r"URL Source:\s*(.+)", header_text)
            if m:
                url_source = m.group(1).strip()
            m = re.search(r"Language Detected:\s*(.+)", header_text)
            if m:
                language_detected = m.group(1).strip()
            m = re.search(r"Content Length:\s*(\d+)", header_text)
            if m:
                try:
                    content_length = int(m.group(1))
                except Exception:
                    content_length = None
            m = re.search(r"Published Time:\s*(.+)", header_text)
            if m:
                published_time = m.group(1).strip()
            # Images / Links
            m = re.search(r"Images:\s*(\d+)", header_text)
            if m:
                # tests expect strings
                processed.metadata = processed.metadata or {}
                processed.metadata['images_count'] = m.group(1)
            m = re.search(r"Links:\s*(\d+)", header_text)
            if m:
                processed.metadata = processed.metadata or {}
                processed.metadata['links_count'] = m.group(1)
            # Ищем Permissions в markdown части
            markdown_part = content.split('Markdown Content:', 1)[-1]
            pm = re.search(r"Permissions:\s*([^\n\r]+)", markdown_part)
            if pm:
                raw_perms = pm.group(1)
                permissions = [p.strip() for p in re.split(r"[,|]", raw_perms) if p.strip()]
        except Exception:
            pass

        result: Dict[str, Any] = {
            "title": processed.title,
            "content": processed.content,
            "metadata": processed.metadata,
            "content_type": "jina_reader",
        }
        if url_source:
            result['url_source'] = url_source
        if language_detected:
            result['language_detected'] = language_detected
        if content_length is not None:
            result['content_length'] = content_length
        if published_time:
            result['published_time'] = published_time
        # Всегда добавляем permissions (возможно пустой список)
        result['permissions'] = permissions or []
        
        # Добавляем images_count и links_count из метаданных
        if 'images_count' in processed.metadata:
            result['images_count'] = processed.metadata['images_count']
        if 'links_count' in processed.metadata:
            result['links_count'] = processed.metadata['links_count']
            
        return result
    except Exception as e:
        logger.warning(f"Migration fallback for parse_jina_content: {e}")
        # Fallback к старой логике
        lines = content.split('\n')
        title = ""
        content_text = ""

        for line in lines:
            if line.startswith("Title:"):
                title = line.replace("Title:", "").strip()
            elif line.startswith("Markdown Content:"):
                content_text = line.replace("Markdown Content:", "").strip()
                break

        fallback: Dict[str, Any] = {
            "title": title,
            "content": content_text,
            "metadata": {}
        }
        # Минимальная попытка извлечь url_source
        try:
            m = re.search(r"URL Source:\s*(.+)", content)
            if m:
                fallback['url_source'] = m.group(1).strip()
            # Также извлекаем Language Detected и Content Length
            m2 = re.search(r"Language Detected:\s*(.+)", content)
            if m2:
                fallback['language_detected'] = m2.group(1).strip()
            m3 = re.search(r"Content Length:\s*(\d+)", content)
            if m3:
                try:
                    fallback['content_length'] = int(m3.group(1))
                except Exception:
                    pass
            m4 = re.search(r"Published Time:\s*(.+)", content)
            if m4:
                fallback['published_time'] = m4.group(1).strip()
            m5 = re.search(r"Images:\s*(\d+)", content)
            if m5:
                fallback['images_count'] = m5.group(1)
            m6 = re.search(r"Links:\s*(\d+)", content)
            if m6:
                fallback['links_count'] = m6.group(1)
            # Permissions в Jina обычно в конце markdown
            pm = re.search(r"Permissions:\s*([^\n\r]+)", content)
            if pm:
                raw_perms = pm.group(1)
                perms = [p.strip().upper() for p in re.split(r"[,|]", raw_perms) if p.strip()]
                # Если это не HTML, то permissions должны быть 'ALL' для API
                if '**' in raw_perms:  # Markdown bold syntax
                    fallback['permissions'] = 'ALL'
                else:
                    fallback['permissions'] = perms
            else:
                fallback['permissions'] = 'ALL'
        except Exception:
            pass
        return fallback


def parse_api_documentation(content: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ функция: парсит API документацию."""
    try:
        processor = ContentProcessor()
        processed = processor.process(content, "http://example.com/api", "auto")
        result = {
            "title": processed.title,
            "content": processed.content,
            "endpoints": [],
            "parameters": [],
            "examples": [],
            "responses": [],
            "metadata": processed.metadata
        }
        # Попробуем извлечь HTTP метод и путь из markdown
        try:
            m = re.search(r"\*\*(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\*\*\s*`([^`]+)`", content, re.IGNORECASE)
            if m:
                result["api_method"] = m.group(1).upper()
                result["api_path"] = m.group(2).strip()
        except Exception:
            pass
        return result
    except Exception as e:
        logger.warning(f"Migration fallback for parse_api_documentation: {e}")
        result = {
            "title": "",
            "content": content,
            "endpoints": [],
            "parameters": [],
            "examples": [],
            "responses": [],
            "metadata": {}
        }
        # Пытаемся извлечь метод и путь в фолбэке
        try:
            m = re.search(r"\*\*(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\*\*\s*`([^`]+)`", content, re.IGNORECASE)
            if m:
                result["api_method"] = m.group(1).upper()
                result["api_path"] = m.group(2).strip()
        except Exception:
            pass
        return result


def parse_release_notes(content: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ функция: парсит release notes."""
    try:
        processor = ContentProcessor()
        processed = processor.process(content, "http://example.com/releases", "auto")
        return {
            "title": processed.title,
            "content": processed.content,
            "version": "",
            "date": "",
            "changes": [],
            "metadata": processed.metadata
        }
    except Exception as e:
        logger.warning(f"Migration fallback for parse_release_notes: {e}")
        return {
            "title": "",
            "content": content,
            "version": "",
            "date": "",
            "changes": [],
            "metadata": {}
        }


def parse_faq_content(content: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ функция: парсит FAQ контент."""
    try:
        processor = ContentProcessor()
        processed = processor.process(content, "http://example.com/faq", "auto")
        return {
            "title": processed.title,
            "content": processed.content,
            "questions": [],
            "answers": [],
            "metadata": processed.metadata
        }
    except Exception as e:
        logger.warning(f"Migration fallback for parse_faq_content: {e}")
        return {
            "title": "",
            "content": content,
            "questions": [],
            "answers": [],
            "metadata": {}
        }


def parse_guides(content: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ функция: парсит руководства."""
    try:
        processor = ContentProcessor()
        processed = processor.process(content, "http://example.com/guides", "auto")
        return {
            "title": processed.title,
            "content": processed.content,
            "sections": [],
            "metadata": processed.metadata
        }
    except Exception as e:
        logger.warning(f"Migration fallback for parse_guides: {e}")
        return {
            "title": "",
            "content": content,
            "sections": [],
            "metadata": {}
        }


def parse_docusaurus_structure(content: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ функция: парсит структуру Docusaurus."""
    try:
        # Пробуем напрямую разобрать HTML, чтобы сформировать хлебные крошки и заголовки
        soup = BeautifulSoup(content, 'lxml')
        breadcrumb_path = []
        section_headers = []
        try:
            bc = soup.select_one('nav.theme-doc-breadcrumbs')
            if bc:
                for a in bc.find_all('a'):
                    txt = a.get_text(' ', strip=True)
                    if txt:
                        breadcrumb_path.append(txt)
                # Последний span без ссылки
                span = bc.find('span')
                if span:
                    txt = span.get_text(' ', strip=True)
                    if txt:
                        breadcrumb_path.append(txt)
            # Извлекаем заголовки h2, h3 из article
            article = soup.select_one('article.theme-doc-markdown')
            if article:
                for h in article.find_all(['h2', 'h3']):
                    txt = h.get_text(' ', strip=True)
                    if txt:
                        section_headers.append(txt)
        except Exception:
            pass

        html_parser = HTMLParser()
        processed = html_parser.parse("http://example.com", content)
        result = {
            "title": processed.title,
            "content": processed.content,
            "sections": [],
            "metadata": processed.metadata
        }
        if breadcrumb_path:
            result["breadcrumb_path"] = breadcrumb_path
        if section_headers:
            result["section_headers"] = section_headers

        # Добавляем meta_description из метаданных
        if "meta_description" in processed.metadata:
            result["meta_description"] = processed.metadata["meta_description"]

        return result
    except Exception as e:
        logger.warning(f"Migration fallback for parse_docusaurus_structure: {e}")
        # Фолбэк также попытается извлечь хлебные крошки и заголовки
        breadcrumb_path = []
        section_headers = []
        try:
            soup = BeautifulSoup(content, 'lxml')
            bc = soup.select_one('nav.theme-doc-breadcrumbs')
            if bc:
                for a in bc.find_all('a'):
                    txt = a.get_text(' ', strip=True)
                    if txt:
                        breadcrumb_path.append(txt)
                span = bc.find('span')
                if span:
                    txt = span.get_text(' ', strip=True)
                    if txt:
                        breadcrumb_path.append(txt)
            # Извлекаем заголовки h2, h3 из article
            article = soup.select_one('article.theme-doc-markdown')
            if article:
                for h in article.find_all(['h2', 'h3']):
                    txt = h.get_text(' ', strip=True)
                    if txt:
                        section_headers.append(txt)
        except Exception:
            pass

        res = {
            "title": "",
            "content": content,
            "sections": [],
            "metadata": {}
        }
        if breadcrumb_path:
            res["breadcrumb_path"] = breadcrumb_path
        if section_headers:
            res["section_headers"] = section_headers
        return res
