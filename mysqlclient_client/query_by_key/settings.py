"""settings"""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Settings:
    """query by key settings"""

    use_en_ko_column_alias: bool
    """SELECT file_name "File Name|파일명" """

    all_query: dict[str, str | dict[str, str]]
    """all query information"""
