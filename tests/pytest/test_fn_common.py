"""common function for all datalake test"""

import json
import re
from typing import Literal

from mysqlclient_client.client import ClientPool
from tests.pytest.mock_data.data_all import (
    get_out_by_params,
    get_rows_by_params,
)


def patch_mysqlclient(mocker):
    """patch mysqlclient"""

    class CursorMock:
        """CursorMock"""

        def __init__(self):
            self.qry_str = ""
            self.qry_key = ""
            self.func_type: Literal["update", "read", "csv"] = "read"
            self.params: dict[str, any] = {}  # type: ignore
            self.en: bool = False

            self.rows: list[dict] = []
            self.row: dict | None = None
            self.rowcount: int = 0
            self.description: list[tuple] | None = None
            self._first_fetch_csv: bool = True

        def execute(self, qry_str: str, params: dict[str, any]):  # type: ignore
            """execute"""

            def get_header() -> dict[Literal["qry_key", "func_type", "en"], any]:  # type: ignore
                ret = re.match(r"/\*(.+)\*/", qry_str)
                if not ret:
                    raise ValueError("no header in query")

                header = ret.group(1)
                info = json.loads(header)
                return info

            def set_test_info(
                qry_key: str,
                func_type: Literal["update", "read", "csv"],
                en: bool = False,
            ):
                """set info for test only"""

                self.qry_key = qry_key
                self.func_type = func_type
                self.en = en
                if func_type in ("read", "csv"):
                    rows = get_rows_by_params(self.qry_key, self.params, self.en)
                    row = rows[0] if rows else None
                    self.rows = rows
                    self.row = row
                    if row:
                        self.description = [(k,) for k in row.keys()]
                    else:
                        self.description = None
                elif func_type == "update":
                    params_out, row_count = get_out_by_params(self.qry_key, self.params)
                    self.row = params_out
                    self.rowcount = row_count
                    if params_out:
                        self.rows = [params_out]
                        self.description = [(k,) for k in params_out.keys()]
                    else:
                        self.rows = []
                        self.description = None

            self.qry_str = qry_str
            self.params = params

            header = get_header()
            set_test_info(header["qry_key"], header["func_type"], header["en"])

        def executemany(self, qry_str: str, params: list[dict]):
            for p in params:
                self.execute(qry_str, p)

        def fetchall(self) -> list[dict]:
            """return rows"""
            if self.func_type == "csv":
                if self._first_fetch_csv:
                    self._first_fetch_csv = False
                    return self.rows
                else:
                    return []

            return self.rows

        def fetchmany(self, size: int = 1) -> list[dict]:
            """return rows"""
            if self.func_type == "csv":
                if self._first_fetch_csv:
                    self._first_fetch_csv = False
                    return self.rows
                else:
                    return []

            return self.rows[:size]

        def fetchone(self) -> dict | None:
            """return row"""
            if self.func_type == "csv":
                if self._first_fetch_csv:
                    self._first_fetch_csv = False
                    return self.row
                else:
                    return None

            return self.row

        def close(self):
            """close"""

    class ConnectionMock:
        """ConnectionMock"""

        def __enter__(self):
            """enter"""
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            """exit"""

        def cursor(self, *_, **__) -> CursorMock:
            """return CursorMock"""
            return CursorMock()

        def commit(self):
            """commit"""

        def rollback(self):
            """rollback"""

        def ping(self, reconnect=True):
            """ping"""

        def close(self):
            """close"""

    conn_mock = ConnectionMock()

    mocker.patch.object(ClientPool, "getconn", return_value=conn_mock)
    mocker.patch.object(ClientPool, "_create_connection", return_value=conn_mock)
    mocker.patch.object(ClientPool, "putconn", return_value=None)
    mocker.patch.object(ClientPool, "closeall", return_value=None)


patch_psycopg2 = patch_mysqlclient
