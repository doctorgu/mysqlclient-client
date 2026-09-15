"""database client"""

import atexit
import csv
import io
import queue
import threading
import time
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime

import MySQLdb
import MySQLdb.cursors

from .query_by_key.query import Query
from .query_by_key.query_util import (
    get_query_with_value,
)
from .query_by_key.settings import Settings as QrySettings
from .settings import Settings

connection = MySQLdb.Connection


class ClientPool:
    """database connection pool"""

    def __init__(self, db_settings_pool: Settings):
        self.db_settings_pool = db_settings_pool
        self._lock = threading.Lock()
        self._pool: queue.Queue[MySQLdb.Connection] = queue.Queue(
            maxsize=db_settings_pool.maxconn
        )
        self._all_conns: list[MySQLdb.Connection] = []
        self._closed = False

        for _ in range(db_settings_pool.minconn):
            conn = self._create_connection()
            self._pool.put(conn)
            self._all_conns.append(conn)

        print(datetime.now(UTC), self.__class__.__name__, self.__init__.__name__)

    def _create_connection(self) -> MySQLdb.Connection:
        conn = MySQLdb.connect(
            host=self.db_settings_pool.host,
            port=self.db_settings_pool.port,
            user=self.db_settings_pool.user,
            passwd=self.db_settings_pool.password,
            db=self.db_settings_pool.database,
            connect_timeout=self.db_settings_pool.connect_timeout,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=MySQLdb.cursors.DictCursor,
            ssl_mode="REQUIRED",
        )
        return conn

    def __exit__(self, exc_type, exc_value, traceback):
        """Close the shared connection pool."""
        self.closeall()
        print(datetime.now(UTC), self.__class__.__name__, self.__exit__.__name__)

    def getconn(self) -> MySQLdb.Connection:
        """return conn_pool"""
        with self._lock:
            if self._closed:
                raise RuntimeError("Connection pool is closed")
            try:
                conn = self._pool.get_nowait()
                try:
                    conn.ping(True)
                except Exception:
                    conn = self._create_connection()
                return conn
            except queue.Empty:
                if len(self._all_conns) < self.db_settings_pool.maxconn:
                    conn = self._create_connection()
                    self._all_conns.append(conn)
                    return conn
        try:
            conn = self._pool.get(timeout=self.db_settings_pool.connect_timeout)
            try:
                conn.ping(True)
            except Exception:
                conn = self._create_connection()
            return conn
        except queue.Empty:
            raise TimeoutError("Timeout waiting for connection from pool") from None

    def putconn(self, conn: MySQLdb.Connection):
        """putconn"""
        with self._lock:
            if self._closed:
                try:
                    conn.close()
                except Exception:
                    pass
                return
            try:
                self._pool.put_nowait(conn)
            except queue.Full:
                try:
                    conn.close()
                except Exception:
                    pass
                if conn in self._all_conns:
                    self._all_conns.remove(conn)

    def closeall(self):
        """close all connections in pool"""
        with self._lock:
            self._closed = True
            for conn in self._all_conns:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_conns.clear()
            while not self._pool.empty():
                try:
                    self._pool.get_nowait()
                except queue.Empty:
                    break


db_set_and_pool: dict[str, ClientPool] = {}


def cleanup():
    for pool_inst in db_set_and_pool.values():
        try:
            pool_inst.closeall()
        except Exception:
            pass


atexit.register(cleanup)


class Client:
    """database client"""

    # Class-level shared connection pool
    _conn_pool: ClientPool

    def __init__(self, db_settings: Settings):
        self.conn: connection
        self.in_with_block = False
        self.db_settings = db_settings
        self.qry = Query(
            qry_settings=QrySettings(
                use_en_ko_column_alias=db_settings.use_en_ko_column_alias,
                use_conditional=db_settings.use_conditional,
                all_query=db_settings.all_query,
            )
        )
        self.query_recent = ""

        db_set_key = db_settings.key
        if db_set_key not in db_set_and_pool:
            client_pool = ClientPool(db_settings)
            db_set_and_pool[db_set_key] = client_pool
            Client._conn_pool = client_pool

    def __enter__(self):
        # Called when entering the 'with' block
        self.conn = Client._conn_pool.getconn()
        self.in_with_block = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Called when exiting the 'with' block
        try:
            if exc_type is None:
                # No exception, commit the transaction
                self.conn.commit()
            else:
                # Exception occurred, roll back the transaction
                self.conn.rollback()
        finally:
            Client._conn_pool.putconn(self.conn)
            self.in_with_block = False

    def read_row(
        self,
        qry_key: str,
        params: dict,
        *,
        en: bool = False,
    ) -> dict | None:
        """Return single row"""

        rows = self.read_rows(qry_key, params, en=en)
        if not rows:
            return None

        return rows[0]

    def read_rows(
        self,
        qry_key: str,
        params: dict,
        *,
        en: bool = False,
    ) -> list[dict]:
        """Return all rows"""

        def read_rows_by_param(
            qry_key: str,
            params: dict,
            *,
            en: bool = False,
            cursor: MySQLdb.cursors.DictCursor,
        ) -> list[dict]:
            if not isinstance(params, dict):
                params = vars(params)

            qry_str = self.qry.get_query_by_key(qry_key, params, "read", en)
            self.query_recent = qry_str

            start = 0
            if self.db_settings.before_read_execute:
                self.db_settings.before_read_execute(
                    qry_key,
                    params,
                    qry_str,
                    get_query_with_value(qry_str, params),
                )
                start = time.time()

            cursor.execute(qry_str, params)
            rows = cursor.fetchall()

            if self.db_settings.after_read_execute:
                duration = round((time.time() - start) * 1000)
                self.db_settings.after_read_execute(qry_key, duration)

            if not rows:
                return []

            return list(rows)

        rows: list[dict] = []
        if self.in_with_block:
            cursor = self.conn.cursor(MySQLdb.cursors.DictCursor)
            rows = read_rows_by_param(qry_key, params, en=en, cursor=cursor)
            cursor.close()
        else:
            conn_pool = Client._conn_pool
            conn = conn_pool.getconn()
            try:
                cursor = conn.cursor(MySQLdb.cursors.DictCursor)
                rows = read_rows_by_param(qry_key, params, en=en, cursor=cursor)
                cursor.close()
            finally:
                conn_pool.putconn(conn)

        return rows

    async def read_csv_partial_async(
        self,
        qry_key: str,
        params: dict,
        *,
        row_count_partial: int = 100,
        en: bool = False,
    ) -> AsyncGenerator[bytes]:
        """Return rows partially in batches with async

        Arguments:
            qry_key: key of the Dictionary registered in the clients/queries folder
            params: key, value pairs to pass as parameters to the SQL query.
            row_count_partial: Number of rows to return at a time

        Returns:
            CSV format converted to UTF-8-BOM
        """

        async def read_csv_partial_async_by_param(
            qry_key: str,
            params: dict,
            *,
            row_count_partial: int = 100,
            en: bool = False,
            cursor: MySQLdb.cursors.DictCursor,
        ) -> AsyncGenerator[bytes]:
            if not isinstance(params, dict):
                params = vars(params)

            qry_str = self.qry.get_query_by_key(qry_key, params, "csv", en)

            is_second = False

            # without UTF-8 BOM, hangul will be broken.
            utf8_bom = b"\xef\xbb\xbf"
            yield utf8_bom

            start = 0
            if self.db_settings.before_read_execute:
                self.db_settings.before_read_execute(
                    qry_key,
                    params,
                    qry_str,
                    get_query_with_value(qry_str, params),
                )
                start = time.time()

            cursor.execute(qry_str, params)
            while True:
                rows = (
                    cursor.fetchmany(row_count_partial)
                    if hasattr(cursor, "fetchmany")
                    else cursor.fetchall()
                )

                if not is_second and self.db_settings.after_read_execute:
                    duration = round((time.time() - start) * 1000)
                    self.db_settings.after_read_execute(qry_key, duration)

                if not rows:
                    break

                csv_out = io.StringIO()
                csv_w = csv.writer(csv_out)
                if not is_second and cursor.description:
                    column_names = [desc[0] for desc in cursor.description]
                    csv_w.writerow(column_names)
                csv_w.writerows(
                    [list(r.values()) if isinstance(r, dict) else r for r in rows]
                )

                yield csv_out.getvalue().encode("utf-8")

                is_second = True

        if self.in_with_block:
            cursor = self.conn.cursor(MySQLdb.cursors.DictCursor)
            try:
                async for value in read_csv_partial_async_by_param(
                    qry_key,
                    params,
                    row_count_partial=row_count_partial,
                    en=en,
                    cursor=cursor,
                ):
                    yield value
            finally:
                cursor.close()
        else:
            conn_pool = Client._conn_pool
            conn = conn_pool.getconn()
            try:
                cursor = conn.cursor(MySQLdb.cursors.DictCursor)
                try:
                    async for value in read_csv_partial_async_by_param(
                        qry_key,
                        params,
                        row_count_partial=row_count_partial,
                        en=en,
                        cursor=cursor,
                    ):
                        yield value
                finally:
                    cursor.close()
            finally:
                conn_pool.putconn(conn)

    def read_csv_partial(
        self,
        qry_key: str,
        params: dict,
        *,
        row_count_partial: int = 100,
        en: bool = False,
    ) -> Generator[bytes]:
        """Return rows partially in batches

        Arguments:
            qry_key: key of the Dictionary registered in the clients/queries folder
            params: key, value pairs to pass as parameters to the SQL query.
            row_count_partial: Number of rows to return at a time

        Returns:
            CSV format converted to UTF-8-BOM
        """

        def read_csv_partial_by_param(
            qry_key: str,
            params: dict,
            *,
            row_count_partial: int = 100,
            en: bool = False,
            cursor: MySQLdb.cursors.DictCursor,
        ) -> Generator[bytes]:
            if not isinstance(params, dict):
                params = vars(params)

            qry_str = self.qry.get_query_by_key(qry_key, params, "csv", en)

            is_second = False

            # without UTF-8 BOM, hangul will be broken.
            utf8_bom = b"\xef\xbb\xbf"
            yield utf8_bom

            start = 0
            if self.db_settings.before_read_execute:
                self.db_settings.before_read_execute(
                    qry_key,
                    params,
                    qry_str,
                    get_query_with_value(qry_str, params),
                )
                start = time.time()

            cursor.execute(qry_str, params)
            while True:
                rows = (
                    cursor.fetchmany(row_count_partial)
                    if hasattr(cursor, "fetchmany")
                    else cursor.fetchall()
                )

                if not is_second and self.db_settings.after_read_execute:
                    duration = round((time.time() - start) * 1000)
                    self.db_settings.after_read_execute(qry_key, duration)
                if not rows:
                    break

                csv_out = io.StringIO()
                csv_w = csv.writer(csv_out)
                if not is_second and cursor.description:
                    column_names = [desc[0] for desc in cursor.description]
                    csv_w.writerow(column_names)
                csv_w.writerows(
                    [list(r.values()) if isinstance(r, dict) else r for r in rows]
                )

                yield csv_out.getvalue().encode("utf-8")

                is_second = True

        if self.in_with_block:
            cursor = self.conn.cursor(MySQLdb.cursors.DictCursor)
            try:
                yield from read_csv_partial_by_param(
                    qry_key,
                    params,
                    row_count_partial=row_count_partial,
                    en=en,
                    cursor=cursor,
                )
            finally:
                cursor.close()
        else:
            conn_pool = Client._conn_pool
            conn = conn_pool.getconn()
            try:
                cursor = conn.cursor(MySQLdb.cursors.DictCursor)
                try:
                    yield from read_csv_partial_by_param(
                        qry_key,
                        params,
                        row_count_partial=row_count_partial,
                        en=en,
                        cursor=cursor,
                    )
                finally:
                    cursor.close()
            finally:
                conn_pool.putconn(conn)

    def update(
        self,
        qry_key: str,
        params: dict,
        params_out: dict | None = None,
    ) -> int:
        """call updates"""

        params_out_used = params_out if params_out is not None else {}
        row_counts = self.updates([(qry_key, params, params_out_used)])
        return row_counts[0]

    def updates(
        self,
        qry_key_params_list: list[tuple[str, dict, dict]] | list[tuple[str, dict]],
    ) -> list[int]:
        """Executes a list of SQL statements within a single transaction.
        If all SQL commands succeed, returns a list of the number of rows affected
        by each qry_key.
        If any command fails, an error is raised.

        Arguments:
            qry_key_params_list: A list of tuples, each containing following two values:
                qry_key: key of the dictionary registered in the clients/queries folder
                params: key, value pairs to pass as parameters to the SQL query.

        Returns:
            The number of rows affected by the last SQL query.
        """

        def normalize_qry_key_params_list(
            qry_key_params_list: list[tuple[str, dict, dict]] | list[tuple[str, dict]],
        ) -> list[tuple[str, dict, dict]]:
            qry_key_params_list_new: list[tuple[str, dict, dict]] = []
            for item in qry_key_params_list:
                if len(item) == 2:
                    qry_key, params = item
                    params_out = {}
                else:
                    qry_key, params, params_out = item

                if not isinstance(params, (dict, list, tuple)):
                    params = vars(params)

                qry_key_params_list_new.append((qry_key, params, params_out))

            return qry_key_params_list_new

        def updates_by_param(
            qry_key_params_list: list[tuple[str, dict, dict]] | list[tuple[str, dict]],
            cursor: MySQLdb.cursors.DictCursor,
        ) -> list[int]:
            row_counts: list[int] = []
            qry_strs: list[str] = []

            qry_key_params_list_new = normalize_qry_key_params_list(qry_key_params_list)

            for item in qry_key_params_list_new:
                qry_key, params, params_out = item

                qry_str = self.qry.get_query_by_key(qry_key, params, "update")

                start = 0
                if self.db_settings.before_update_execute:
                    self.db_settings.before_update_execute(
                        qry_key,
                        params,
                        params_out,
                        qry_str,
                        get_query_with_value(qry_str, params),
                    )
                    start = time.time()

                if isinstance(params, (list, tuple)):
                    cursor.executemany(qry_str, params)
                else:
                    cursor.execute(qry_str, params)

                row_count = cursor.rowcount

                if params_out and cursor.description:
                    row = cursor.fetchone()
                    if row:
                        for k, v in row.items():
                            if k in params_out:
                                params_out[k] = v

                if self.db_settings.after_update_execute:
                    duration = round((time.time() - start) * 1000)
                    self.db_settings.after_update_execute(
                        qry_key, row_count, params_out, duration
                    )

                row_counts.append(row_count)
                qry_strs.append(qry_str)

            return row_counts

        row_counts: list[int] = []
        if self.in_with_block:
            cursor = self.conn.cursor(MySQLdb.cursors.DictCursor)
            try:
                row_counts = updates_by_param(qry_key_params_list, cursor)
            finally:
                cursor.close()
        else:
            conn_pool = Client._conn_pool
            conn = conn_pool.getconn()
            try:
                cursor = conn.cursor(MySQLdb.cursors.DictCursor)
                try:
                    row_counts = updates_by_param(qry_key_params_list, cursor)
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    cursor.close()
            finally:
                conn_pool.putconn(conn)

        return row_counts
