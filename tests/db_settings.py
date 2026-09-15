"""db settings"""

import os

from dotenv import load_dotenv

from mysqlclient_client.settings import Settings
from tests.queries.query_all import all_query

load_dotenv()

db_settings = Settings(
    password=os.getenv("DB_PASSWORD", "0000"),
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_DATABASE", "test"),
    user=os.getenv("DB_USER", "root"),
    minconn=3,
    maxconn=6,
    connect_timeout=3,
    use_en_ko_column_alias=True,
    use_conditional=True,
    all_query=all_query,
    before_read_execute=lambda qry_key, params, qry_str, qry_with_value: print(
        f'READ_ROWS_START, QRY_KEY: "{qry_key}", QRY_WITH_VALUE: {qry_with_value}'
    ),
    after_read_execute=lambda qry_key, duration: print(
        f'READ_ROWS_END, QRY_KEY: "{qry_key}", DURATION: {duration}'
    ),
    before_update_execute=lambda qry_key, params, params_out, qry_str, qry_with_value: (
        print(f'UPDATES_START, QRY_KEY: "{qry_key}", QRY_WITH_VALUE: {qry_with_value}')
    ),
    after_update_execute=lambda qry_key, row_count, params_out, duration: print(
        f'UPDATES_END, QRY_KEY: "{qry_key}", DURATION: {duration}'
    ),
)
