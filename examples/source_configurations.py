"""
Примеры конфигураций для различных типов источников данных.
"""

from app.sources_registry import SourceConfig, SourceType


# Пример 1: Документационный сайт (Docusaurus)
DOCUSAURUS_CONFIG = SourceConfig(
    name="docusaurus_docs",
    base_url="https://docs.example.com/",
    source_type=SourceType.DOCS_SITE,
    strategy="jina",  # Jina Reader для сложных сайтов
    use_cache=True,
    sitemap_path="/sitemap.xml",
    seed_urls=[
        "https://docs.example.com/",
        "https://docs.example.com/docs/",
        "https://docs.example.com/blog/",
    ],
    crawl_deny_prefixes=[
        "https://docs.example.com/api/",
        "https://docs.example.com/admin/",
        "https://docs.example.com/search/",
    ],
    metadata_patterns={
        r'/docs/start/': {
            'section': 'start',
            'user_role': 'all',
            'page_type': 'guide'
        },
        r'/docs/agent/': {
            'section': 'agent',
            'user_role': 'agent',
            'page_type': 'guide'
        },
        r'/docs/admin/': {
            'section': 'admin',
            'user_role': 'admin',
            'page_type': 'guide'
        },
        r'/docs/api/': {
            'section': 'api',
            'user_role': 'developer',
            'page_type': 'api'
        },
        r'/blog/': {
            'section': 'news',
            'user_role': 'all',
            'page_type': 'blog'
        }
    },
    timeout_s=30,
    crawl_delay_ms=1000,
    user_agent="DocsBot/1.0 (+https://example.com/bot)",
)


# Пример 2: API документация (Swagger/OpenAPI)
API_DOCS_CONFIG = SourceConfig(
    name="swagger_api",
    base_url="https://api.example.com/docs/",
    source_type=SourceType.API_DOCS,
    strategy="http",  # Простой HTTP для API docs
    use_cache=True,
    seed_urls=[
        "https://api.example.com/docs/",
        "https://api.example.com/docs/api/",
    ],
    custom_headers={
        "Authorization": "Bearer your-api-token",
        "Accept": "application/json",
    },
    metadata_patterns={
        r'/docs/': {
            'section': 'api',
            'user_role': 'developer',
            'page_type': 'api'
        }
    },
    timeout_s=15,
    crawl_delay_ms=500,
)


# Пример 3: Блог или новости
BLOG_CONFIG = SourceConfig(
    name="company_blog",
    base_url="https://blog.example.com/",
    source_type=SourceType.BLOG,
    strategy="jina",  # Jina для сложных блогов
    use_cache=True,
    sitemap_path="/sitemap.xml",
    seed_urls=[
        "https://blog.example.com/",
    ],
    crawl_deny_prefixes=[
        "https://blog.example.com/author/",
        "https://blog.example.com/tag/",
        "https://blog.example.com/category/",
    ],
    metadata_patterns={
        r'/': {
            'section': 'blog',
            'user_role': 'all',
            'page_type': 'blog'
        }
    },
    timeout_s=30,
    crawl_delay_ms=2000,  # Более медленный краулинг для блогов
    user_agent="BlogBot/1.0 (+https://example.com/bot)",
)


# Пример 4: FAQ страницы
FAQ_CONFIG = SourceConfig(
    name="faq_pages",
    base_url="https://help.example.com/",
    source_type=SourceType.FAQ,
    strategy="http",  # Простой HTTP для FAQ
    use_cache=True,
    seed_urls=[
        "https://help.example.com/",
        "https://help.example.com/faq/",
    ],
    metadata_patterns={
        r'/faq/': {
            'section': 'help',
            'user_role': 'all',
            'page_type': 'faq'
        }
    },
    timeout_s=20,
    crawl_delay_ms=1000,
)


# Пример 5: Внешний сайт
EXTERNAL_CONFIG = SourceConfig(
    name="external_docs",
    base_url="https://external-docs.example.com/",
    source_type=SourceType.EXTERNAL,
    strategy="jina",  # Jina для внешних сайтов
    use_cache=True,
    sitemap_path="/sitemap.xml",
    seed_urls=[
        "https://external-docs.example.com/",
    ],
    crawl_deny_prefixes=[
        "https://external-docs.example.com/admin/",
        "https://external-docs.example.com/login/",
    ],
    metadata_patterns={
        r'/': {
            'section': 'external',
            'user_role': 'all',
            'page_type': 'external'
        }
    },
    timeout_s=45,
    crawl_delay_ms=3000,  # Очень медленный краулинг для внешних сайтов
    user_agent="ExternalBot/1.0 (+https://example.com/bot)",
)


# Пример 6: Локальная папка с документами
LOCAL_FOLDER_CONFIG = SourceConfig(
    name="local_docs",
    base_url="file:///path/to/docs/",
    source_type=SourceType.LOCAL_FOLDER,
    local_path="/path/to/docs/",
    file_extensions=['.md', '.rst', '.txt', '.html'],
    strategy="auto",  # Автоматическое определение типа
    use_cache=True,
    metadata_patterns={
        r'/guides/': {
            'section': 'guides',
            'user_role': 'all',
            'page_type': 'guide'
        },
        r'/api/': {
            'section': 'api',
            'user_role': 'developer',
            'page_type': 'api'
        }
    }
)


# Пример 7: Коллекция файлов
FILE_COLLECTION_CONFIG = SourceConfig(
    name="file_collection",
    base_url="file:///path/to/files/",
    source_type=SourceType.FILE_COLLECTION,
    local_path="/path/to/files/",
    file_extensions=['.pdf', '.doc', '.docx', '.txt'],
    strategy="auto",
    use_cache=True,
    metadata_patterns={
        r'/manuals/': {
            'section': 'manuals',
            'user_role': 'all',
            'page_type': 'manual'
        },
        r'/specs/': {
            'section': 'specs',
            'user_role': 'developer',
            'page_type': 'specification'
        }
    }
)


# Пример 8: Конфигурация для тестирования
TEST_CONFIG = SourceConfig(
    name="test_source",
    base_url="https://httpbin.org/",  # Тестовый сайт
    source_type=SourceType.EXTERNAL,
    strategy="http",
    use_cache=False,  # Отключаем кеш для тестов
    seed_urls=["https://httpbin.org/"],
    timeout_s=10,
    crawl_delay_ms=100,
    max_pages=5,  # Ограничиваем для тестов
)


# Словарь всех конфигураций для удобного доступа
ALL_CONFIGS = {
    "docusaurus": DOCUSAURUS_CONFIG,
    "api_docs": API_DOCS_CONFIG,
    "blog": BLOG_CONFIG,
    "faq": FAQ_CONFIG,
    "external": EXTERNAL_CONFIG,
    "local_folder": LOCAL_FOLDER_CONFIG,
    "file_collection": FILE_COLLECTION_CONFIG,
    "test": TEST_CONFIG,
}


def get_config_by_name(name: str) -> SourceConfig:
    """Получить конфигурацию по имени"""
    if name not in ALL_CONFIGS:
        raise ValueError(f"Unknown config name: {name}. Available: {list(ALL_CONFIGS.keys())}")
    return ALL_CONFIGS[name]


def list_available_configs() -> list[str]:
    """Получить список доступных конфигураций"""
    return list(ALL_CONFIGS.keys())


# Пример использования
if __name__ == "__main__":
    print("Available configurations:")
    for name in list_available_configs():
        config = get_config_by_name(name)
        print(f"- {name}: {config.source_type.value} ({config.base_url})")
    
    print("\nExample usage:")
    print("from examples.source_configurations import get_config_by_name")
    print("config = get_config_by_name('docusaurus')")
    print("print(config)")
