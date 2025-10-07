import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock
from ingestion.run import load_config, merge_config_with_args


def test_updated_config_structure():
    """Тест новой структуры конфигурации согласно предложенному примеру"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_file = temp_path / "test_config.yaml"

        # Создаем конфигурацию в новом формате
        test_config = {
            "global": {
                "qdrant": {
                    "url": "http://localhost:6333",
                    "collection": "docs_chatcenter"
                },
                "indexing": {
                    "batch_size": 256,
                    "reindex_mode": "changed"
                }
            },
            "sources": {
                "docusaurus": {
                    "enabled": True,
                    "docs_root": "C:\\CC_RAG\\docs",
                    "site_base_url": "https://docs-chatcenter.edna.ru",
                    "site_docs_prefix": "/docs",
                    "include_file_extensions": [".md", ".mdx"],
                    "cleaning": {
                        "remove_html_comments": True,
                        "strip_imports": True,
                        "strip_custom_components": True,
                        "strip_admonitions": True
                    },
                    "chunk": {
                        "max_tokens": 600,
                        "overlap_tokens": 120
                    },
                    "routing": {
                        "drop_numeric_prefix_in_first_level": True,
                        "add_trailing_slash": False
                    },
                    "indexing": {
                        "upsert": True,
                        "delete_missing": False
                    }
                }
            }
        }

        config_file.write_text(yaml.dump(test_config), encoding="utf-8")

        # Загружаем конфигурацию
        loaded_config = load_config(str(config_file))

        # Проверяем структуру
        assert loaded_config["sources"]["docusaurus"]["enabled"] is True
        assert loaded_config["sources"]["docusaurus"]["docs_root"] == "C:\\CC_RAG\\docs"
        assert loaded_config["sources"]["docusaurus"]["site_base_url"] == "https://docs-chatcenter.edna.ru"
        assert loaded_config["sources"]["docusaurus"]["site_docs_prefix"] == "/docs"
        assert loaded_config["sources"]["docusaurus"]["include_file_extensions"] == [".md", ".mdx"]

        # Проверяем настройки очистки
        cleaning = loaded_config["sources"]["docusaurus"]["cleaning"]
        assert cleaning["remove_html_comments"] is True
        assert cleaning["strip_imports"] is True
        assert cleaning["strip_custom_components"] is True
        assert cleaning["strip_admonitions"] is True

        # Проверяем настройки чанкинга
        chunk = loaded_config["sources"]["docusaurus"]["chunk"]
        assert chunk["max_tokens"] == 600
        assert chunk["overlap_tokens"] == 120

        # Проверяем настройки маршрутизации
        routing = loaded_config["sources"]["docusaurus"]["routing"]
        assert routing["drop_numeric_prefix_in_first_level"] is True
        assert routing["add_trailing_slash"] is False

        # Проверяем настройки индексации
        indexing = loaded_config["sources"]["docusaurus"]["indexing"]
        assert indexing["upsert"] is True
        assert indexing["delete_missing"] is False


def test_merge_config_with_new_structure():
    """Тест объединения конфигурации с новой структурой"""
    config = {
        "sources": {
            "docusaurus": {
                "enabled": True,
                "docs_root": "C:\\CC_RAG\\docs",
                "site_base_url": "https://docs-chatcenter.edna.ru",
                "site_docs_prefix": "/docs",
                "cleaning": {
                    "remove_html_comments": True,
                    "strip_imports": True,
                    "strip_custom_components": True,
                    "strip_admonitions": True
                },
                "chunk": {
                    "max_tokens": 600,
                    "overlap_tokens": 120
                },
                "routing": {
                    "drop_numeric_prefix_in_first_level": True,
                    "add_trailing_slash": False
                },
                "indexing": {
                    "upsert": True,
                    "delete_missing": False
                }
            }
        }
    }

    # Создаем mock аргументов
    args = Mock()
    args.docs_root = None
    args.site_base_url = None
    args.site_docs_prefix = None
    args.collection = None
    args.category_filter = None
    args.reindex = None
    args.batch_size = None

    # Объединяем конфигурацию
    merged = merge_config_with_args(config, args)

    # Проверяем результат
    assert merged["docs_root"] == "C:\\CC_RAG\\docs"
    assert merged["site_base_url"] == "https://docs-chatcenter.edna.ru"
    assert merged["site_docs_prefix"] == "/docs"
    assert merged["chunk_max_tokens"] == 600
    assert merged["chunk_overlap_tokens"] == 120

    # Проверяем настройки очистки
    assert merged["cleaning"]["remove_html_comments"] is True
    assert merged["cleaning"]["strip_imports"] is True
    assert merged["cleaning"]["strip_custom_components"] is True
    assert merged["cleaning"]["strip_admonitions"] is True

    # Проверяем настройки маршрутизации
    assert merged["routing"]["drop_numeric_prefix_in_first_level"] is True
    assert merged["routing"]["add_trailing_slash"] is False

    # Проверяем настройки индексации
    assert merged["indexing"]["upsert"] is True
    assert merged["indexing"]["delete_missing"] is False


def test_disabled_source():
    """Тест отключенного источника"""
    config = {
        "sources": {
            "docusaurus": {
                "enabled": False,
                "docs_root": "C:\\CC_RAG\\docs"
            }
        }
    }

    args = Mock()
    args.docs_root = None
    args.site_base_url = None
    args.site_docs_prefix = None
    args.collection = None
    args.category_filter = None
    args.reindex = None
    args.batch_size = None

    # Объединяем конфигурацию
    merged = merge_config_with_args(config, args)

    # Проверяем, что используются значения по умолчанию
    assert merged["docs_root"] == "C:\\CC_RAG\\docs"  # Значение по умолчанию


def test_profile_with_new_structure():
    """Тест профиля с новой структурой"""
    config = {
        "sources": {
            "docusaurus": {
                "enabled": True,
                "docs_root": "C:\\CC_RAG\\docs",
                "chunk": {
                    "max_tokens": 600,
                    "overlap_tokens": 120
                },
                "cleaning": {
                    "strip_imports": True
                }
            }
        },
        "profiles": {
            "development": {
                "sources": {
                    "docusaurus": {
                        "chunk": {
                            "max_tokens": 300  # Переопределяем в профиле
                        },
                        "cleaning": {
                            "strip_imports": False  # Переопределяем в профиле
                        }
                    }
                }
            }
        }
    }

    # Применяем профиль development
    from ingestion.run import _merge_profile_config
    profile_config = config["profiles"]["development"]
    merged = _merge_profile_config(config, profile_config)

    # Проверяем результат
    assert merged["sources"]["docusaurus"]["chunk"]["max_tokens"] == 300  # Из профиля
    assert merged["sources"]["docusaurus"]["chunk"]["overlap_tokens"] == 120  # Из базовой
    assert merged["sources"]["docusaurus"]["cleaning"]["strip_imports"] is False  # Из профиля
    assert merged["sources"]["docusaurus"]["docs_root"] == "C:\\CC_RAG\\docs"  # Из базовой


def test_all_required_fields_present():
    """Тест, что все требуемые поля присутствуют в конфигурации"""
    # Загружаем реальную конфигурацию
    config_path = Path("ingestion/config.yaml")
    if config_path.exists():
        config = load_config(str(config_path))

        docusaurus_config = config["sources"]["docusaurus"]

        # Проверяем обязательные поля
        required_fields = [
            "enabled",
            "docs_root",
            "site_base_url",
            "site_docs_prefix",
            "include_file_extensions",
            "cleaning",
            "chunk",
            "routing",
            "indexing"
        ]

        for field in required_fields:
            assert field in docusaurus_config, f"Отсутствует обязательное поле: {field}"

        # Проверяем подполя
        assert "remove_html_comments" in docusaurus_config["cleaning"]
        assert "strip_imports" in docusaurus_config["cleaning"]
        assert "strip_custom_components" in docusaurus_config["cleaning"]
        assert "strip_admonitions" in docusaurus_config["cleaning"]

        assert "max_tokens" in docusaurus_config["chunk"]
        assert "overlap_tokens" in docusaurus_config["chunk"]

        assert "drop_numeric_prefix_in_first_level" in docusaurus_config["routing"]
        assert "add_trailing_slash" in docusaurus_config["routing"]

        assert "upsert" in docusaurus_config["indexing"]
        assert "delete_missing" in docusaurus_config["indexing"]
