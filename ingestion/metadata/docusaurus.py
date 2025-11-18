from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional


NUM_PREFIX_RE = re.compile(r"^\d+-")


def _clean_segment(value: str) -> str:
    """Удаляет числовой префикс '01-' и приводит сегмент к нижнему регистру."""
    return NUM_PREFIX_RE.sub("", value or "").lower()


@dataclass
class DocusaurusMetadataMapper:
    """Простейший маппер тематических метаданных для Docusaurus источников."""

    domain: str
    section_by_dir: Dict[str, str] = field(default_factory=dict)
    role_by_section: Dict[str, str] = field(default_factory=dict)
    platform_by_dir: Dict[str, str] = field(default_factory=dict)
    page_type_by_dir: Dict[str, str] = field(default_factory=dict)
    fixed_section: Optional[str] = None
    fixed_role: Optional[str] = None
    fixed_platform: Optional[str] = None
    default_section: Optional[str] = None
    default_role: Optional[str] = None
    default_platform: Optional[str] = None

    def map_metadata(self, rel_path: str, dir_meta: Dict[str, str]) -> Dict[str, str]:
        """Возвращает словарь с тематическими полями для конкретного файла."""
        segments = rel_path.split("/") if rel_path else []
        top_segment = _clean_segment(segments[0]) if segments else ""

        section = self.fixed_section or self.section_by_dir.get(top_segment) or self.default_section
        platform = self.fixed_platform or self.platform_by_dir.get(top_segment) or self.default_platform
        role = self.fixed_role or self._role_from_section(section) or self.default_role
        page_type = self.page_type_by_dir.get(top_segment)

        result: Dict[str, str] = {"domain": self.domain}
        if section:
            result["section"] = section
        if platform:
            result["platform"] = platform
        if role:
            result["role"] = role
        if page_type:
            result["page_type"] = page_type

        # Если top_level_dir уже вычислен, добавляем его в понятном виде.
        if "top_level_dir" in dir_meta and "top_level_dir" not in result:
            result["top_level_dir"] = _clean_segment(str(dir_meta["top_level_dir"]))

        return result

    def _role_from_section(self, section: Optional[str]) -> Optional[str]:
        if not section:
            return None
        return self.role_by_section.get(section)
