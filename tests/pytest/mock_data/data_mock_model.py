"""model for mock data"""

from collections.abc import Callable

from pydantic import BaseModel


class DataMock(BaseModel):
    """mock model for common"""

    qry_key: str
    params: dict
    en: bool = False
    params_ignore: list[str] = []
    params_replace: Callable | None = None


class ReadRowsMock(DataMock):
    """mock model for read_rows"""

    rows: list[dict]


class UpdatesMock(DataMock):
    """mock model for updates"""

    params_out: dict
    row_count: int
