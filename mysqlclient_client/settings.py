"""settings"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, kw_only=True)
class Settings:
    """db client settings"""

    host: str
    port: int
    database: str
    user: str
    password: str

    minconn: int
    maxconn: int
    connect_timeout: int

    use_en_ko_column_alias: bool
    """SELECT file_name "File Name|파일명" """
    use_conditional: bool
    """
    #if ${target} == 'korea'
        FROM tbl_korea
    #else
        FROM tbl_vietnam
    #endif
    """
    all_query: dict[str, str | dict[str, str]] = field(default_factory=dict)
    """all query information"""
    dir_queries: Path | str | None = None
    """queries directory path"""

    before_read_execute: Callable[[str, dict, str, str], None] = None
    """
    qry_key: str, params: dict, qry_str: str, qry_with_value: str
    """
    after_read_execute: Callable[[str, int], None] = None
    """
    qry_key: str, duration: int
    """
    before_update_execute: Callable[
        [str, dict, dict, str, str],
        None,
    ] = None
    """
    qry_key: str, params: dict, params_out: dict, qry_str: str, qry_with_value: str
    """
    after_update_execute: Callable[[str, int, dict, int], None] = None
    """
    qry_key: str, row_count: int, params_out: dict, duration: int
    """

    @property
    def key(self):
        """key for another dictionary"""

        return (
            f"{self.host},{self.port},{self.database},{self.user},{self.password}"
            f"{self.minconn},{self.maxconn},{self.connect_timeout}"
        )
