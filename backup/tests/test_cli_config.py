import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, Mock
from ingestion.run import load_config, merge_config_with_args, _merge_profile_config


def test_load_config():
    """Тест загрузки конфигурации из YAML файла"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_file = temp_path / "test_config.yaml"

        # Создаем тестовую конфигурацию
        test_config = {
            "global": {
                "qdrant": {
                    "url": "http://test:6333",
                    "collection": "test_collection"
                }
            },
            "sources": {
                "docusaurus": {
                    "docs_root": "/test/docs",
                    "site_base_url": "https://test.com"
                }
            }
        }

        config_file.write_text(yaml.dump(test_config), encoding="utf-8")

        # Загружаем конфигурацию
        loaded_config = load_config(str(config_file))

        # Проверяем результат
        assert loaded_config["global"]["qdrant"]["url"] == "http://test:6333"
        assert loaded_config["sources"]["docusaurus"]["docs_root"] == "/test/docs"


def test_load_config_file_not_found():
    """Тест загрузки несуществующего файла конфигурации"""
    try:
        load_config("/nonexistent/config.yaml")
        assert False, "Должно было быть исключение FileNotFoundError"
    except FileNotFoundError as e:
        assert "не найден" in str(e)


def test_merge_config_with_args():
    """Тест объединения конфигурации с аргументами командной строки"""
    # Создаем тестовую конфигурацию
    config = {
        "global": {
            "qdrant": {
                "collection": "config_collection"
            },
            "indexing": {
                "batch_size": 128,
                "reindex_mode": "all"
            }
        },
        "sources": {
            "docusaurus": {
                "docs_root": "/config/docs",
                "site_base_url": "https://config.com",
                "filters": {
                    "category_filter": "CONFIG_CAT"
                }
            }
        }
    }

    # Создаем mock аргументов
    args = Mock()
    args.docs_root = "/args/docs"
    args.site_base_url = None  # Не переопределяем
    args.site_docs_prefix = None
    args.collection = "args_collection"
    args.category_filter = "ARGS_CAT"
    args.reindex = "changed"
    args.batch_size = 256

    # Объединяем конфигурацию
    merged = merge_config_with_args(config, args)

    # Проверяем результат
    assert merged["docs_root"] == "/args/docs"  # Переопределено аргументом
    assert merged["site_base_url"] == "https://config.com"  # Из конфигурации
    assert merged["collection_name"] == "args_collection"  # Переопределено аргументом
    assert merged["category_filter"] == "ARGS_CAT"  # Переопределено аргументом
    assert merged["reindex_mode"] == "changed"  # Переопределено аргументом
    assert merged["batch_size"] == 256  # Переопределено аргументом


def test_merge_profile_config():
    """Тест объединения профиля конфигурации"""
    base_config = {
        "global": {
            "qdrant": {
                "url": "http://base:6333",
                "collection": "base_collection"
            }
        },
        "sources": {
            "docusaurus": {
                "docs_root": "/base/docs",
                "site_base_url": "https://base.com"
            }
        }
    }

    profile_config = {
        "global": {
            "qdrant": {
                "collection": "profile_collection"  # Переопределяем только collection
            }
        },
        "sources": {
            "docusaurus": {
                "docs_root": "/profile/docs"  # Переопределяем docs_root
            }
        }
    }

    # Объединяем конфигурации
    merged = _merge_profile_config(base_config, profile_config)

    # Проверяем результат
    assert merged["global"]["qdrant"]["url"] == "http://base:6333"  # Остается из базовой
    assert merged["global"]["qdrant"]["collection"] == "profile_collection"  # Переопределено профилем
    assert merged["sources"]["docusaurus"]["docs_root"] == "/profile/docs"  # Переопределено профилем
    assert merged["sources"]["docusaurus"]["site_base_url"] == "https://base.com"  # Остается из базовой


def test_merge_config_defaults():
    """Тест значений по умолчанию при отсутствии конфигурации"""
    # Пустая конфигурация
    config = {}

    # Аргументы без переопределений
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

    # Проверяем значения по умолчанию
    assert merged["docs_root"] == "C:\\CC_RAG\\docs"
    assert merged["site_base_url"] == "https://docs-chatcenter.edna.ru"
    assert merged["site_docs_prefix"] == "/docs"
    assert merged["collection_name"] == "docs_chatcenter"
    assert merged["category_filter"] is None
    assert merged["reindex_mode"] == "changed"
    assert merged["batch_size"] == 256


def test_config_with_profile():
    """Тест конфигурации с профилем"""
    config = {
        "global": {
            "qdrant": {
                "url": "http://base:6333",
                "collection": "base_collection"
            }
        },
        "sources": {
            "docusaurus": {
                "docs_root": "/base/docs"
            }
        },
        "profiles": {
            "development": {
                "global": {
                    "qdrant": {
                        "collection": "dev_collection"
                    }
                },
                "sources": {
                    "docusaurus": {
                        "filters": {
                            "category_filter": "DEV_CAT"
                        }
                    }
                }
            }
        }
    }

    # Применяем профиль development
    profile_config = config["profiles"]["development"]
    merged = _merge_profile_config(config, profile_config)

    # Проверяем результат
    assert merged["global"]["qdrant"]["url"] == "http://base:6333"  # Остается из базовой
    assert merged["global"]["qdrant"]["collection"] == "dev_collection"  # Из профиля
    assert merged["sources"]["docusaurus"]["docs_root"] == "/base/docs"  # Остается из базовой
    assert merged["sources"]["docusaurus"]["filters"]["category_filter"] == "DEV_CAT"  # Из профиля


def test_yaml_config_structure():
    """Тест структуры YAML конфигурации"""
    # Создаем полную конфигурацию как в реальном файле
    config = {
        "global": {
            "qdrant": {
                "url": "http://localhost:6333",
                "api_key": None,
                "collection": "docs_chatcenter"
            },
            "embeddings": {
                "backend": "auto",
                "device": "auto",
                "max_length_query": 512,
                "max_length_doc": 1024,
                "batch_size": 16,
                "use_sparse": True
            },
            "indexing": {
                "batch_size": 256,
                "reindex_mode": "changed"
            }
        },
        "sources": {
            "docusaurus": {
                "type": "docusaurus",
                "docs_root": "C:\\CC_RAG\\docs",
                "site_base_url": "https://docs-chatcenter.edna.ru",
                "site_docs_prefix": "/docs",
                "drop_prefix_all_levels": True,
                "processing": {
                    "default_category": "UNSPECIFIED",
                    "chunk_max_tokens": 600,
                    "chunk_overlap_tokens": 120
                },
                "filters": {
                    "category_filter": None,
                    "file_extensions": [".md", ".mdx"]
                },
                "url_mapping": {
                    "remove_numeric_prefixes": True,
                    "add_trailing_slash": False
                }
            }
        },
        "profiles": {
            "development": {
                "global": {
                    "qdrant": {
                        "collection": "docs_dev"
                    }
                },
                "sources": {
                    "docusaurus": {
                        "filters": {
                            "category_filter": "АРМ_adm"
                        }
                    }
                }
            }
        }
    }

    # Проверяем, что конфигурация корректно структурирована
    assert "global" in config
    assert "sources" in config
    assert "profiles" in config
    assert "docusaurus" in config["sources"]
    assert "development" in config["profiles"]

    # Проверяем ключевые поля
    assert config["sources"]["docusaurus"]["docs_root"] == "C:\\CC_RAG\\docs"
    assert config["sources"]["docusaurus"]["site_base_url"] == "https://docs-chatcenter.edna.ru"
    assert config["global"]["qdrant"]["collection"] == "docs_chatcenter"
