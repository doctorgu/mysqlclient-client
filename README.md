# MysqlclientClient — Modern MySQL Helper for Python

A lightweight, opinionated wrapper around **mysqlclient** (`MySQLdb`) with built-in support for:

- Connection pooling (`minconn` / `maxconn`)
- Query dictionary management
- Conditional SQL (`#if` / `#elif` / `#endif`)
- Bilingual column aliases (`en|ko`)
- Simple transaction handling via context manager
- Safe parameter binding (`%(param)s` syntax)
- Streaming CSV export support

> Successor-friendly alternative to raw mysqlclient with better developer experience.

## Installation

```bash
pip install mysqlclient-client
```

> Note: `mysqlclient-client` is a custom helper class. See full source in repository.

## Quick Start

### 1. Define Queries

YAML format in `queries` folder (or dictionary):

```yaml
- name: read_user_id_all
  value: |
    SELECT  user_id
    FROM    t_user

- name: upsert_user
  value: |
    INSERT INTO t_user
        (
            user_id, user_name, user_rank
        )
    VALUES
        (
            %(user_id)s, %(user_name)s, %(user_rank)s
        )
    ON DUPLICATE KEY UPDATE
        user_name = %(user_name)s,
        user_rank = %(user_rank)s,
        update_time = CURRENT_TIMESTAMP
```

### 2. Configure Database Connection

```python
from mysqlclient_client.settings import Settings

db_settings = Settings(
    host="127.0.0.1",
    port=3306,
    database="test",
    user="root",
    password="password",
    minconn=3,
    maxconn=10,
    connect_timeout=5,
    use_en_ko_column_alias=True,
    use_conditional=True,
    all_query=qry_dic,
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
```

### 3. Basic Usage

```python
from mysqlclient_client.client import Client

db = Client(db_settings=db_settings)

# Read single row
row = db.read_row("read_user_id_all", {})
print(row)  # {'user_id': 'gildong.hong'}

# Read all rows
rows = db.read_rows("read_user_id_all", {})
print(rows[:2])
```

## Create / Update / Delete Operations

### `update()` — Single CUD Statement

Returns affected row count:

```python
affected = db.update(
    "upsert_user", {"user_id": "gildong.hong", "user_name": "홍길동", "user_rank": 1}
)
print("Affected rows:", affected)  # 1
```

### Capture Output Parameters

```python
params_out = {"user_name": "", "user_rank": 0}
db.update(
    "upsert_user",
    {"user_id": "gildong.hong", "user_name": "홍길동", "user_rank": 1},
    params_out=params_out,
)
print("Returned name:", params_out["user_name"], params_out["user_rank"])
```

### `updates()` — Batch Execution

```python
batch = [
    ("upsert_user", {"user_id": "sunja.kim", "user_name": "김순자", "user_rank": 2}),
    ("upsert_user", {"user_id": "malja.kim", "user_name": "김말자", "user_rank": 3}),
]

results = db.updates(batch)
print("Batch results:", results)  # [1, 1]
```

## Transaction Support with `with`

Automatically commits on success, rolls back on exception:

```python
with Client(db_settings=db_settings) as db:
    new_id = "youngja.lee"
    db.update("upsert_user", {"user_id": new_id, "user_name": "이영자", "user_rank": 4})
    db.update("delete_user", {"user_id": new_id})
    print("Committed successfully")
```

## Partially return CSV

Read rows partially and return immediately to client to show progress:

```python
# Flask
@app.route("/read-csv-partial")
def read_csv_partial():
    """read csv partial"""

    db_client = Client(db_settings=db_settings)
    filename = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.csv"

    return Response(
        db_client.read_csv_partial("read_csv_partial", {}),
        mimetype="text/csv",
        headers={
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )
```

## Bilingual Column Aliases (English ↔ Korean)

Enabled when `use_en_ko_column_alias=True` and `en` not omitted:

```yaml
- name: read_user_alias
  value: |
    SELECT  user_id "Id|아이디", user_name "Name|이름", user_rank "Rank|순위"
    FROM    t_user
    WHERE   user_id = %(user_id)s
```

### English mode (`en=True`)

```python
rows = db.read_rows("read_user_alias", {"user_id": "gildong.hong"}, en=True)
print(rows[0])
# {'Id': 'gildong.hong', 'Name': '홍길동', 'Rank': 1}
```

### Korean mode (`en=False`)

```python
rows = db.read_rows("read_user_alias", {"user_id": "gildong.hong"}, en=False)
print(rows[0])
# {'아이디': 'gildong.hong', '이름': '홍길동', '순위': 1}
```

## Conditional SQL (`#if`, `#elif`, `#endif`)

Enabled when `use_conditional=True`:

```yaml
- name: read_user_search
  value: |
    SELECT  user_id, user_name, user_rank, insert_time, update_time
    FROM    t_user
    WHERE   1 = 1
    #if user_id
            AND user_id = %(user_id)s
    #elif user_name
            AND user_name LIKE %(user_name)s
    #elif user_rank
            AND user_rank <= %(user_rank)s
    #endif
```

## Safety & Security

The `#if` preprocessor only allows parameter names, string literals, numbers, and basic boolean operators. Any attempt to inject raw SQL will raise a parsing error before execution.

## Features Summary

| Feature                       | Notes                                                                           |
| ----------------------------- | ------------------------------------------------------------------------------- |
| Connection pooling            | Thread-safe pool via `minconn` / `maxconn`                                      |
| Named queries                 | Stored in YAML / dictionary                                                     |
| Single-row / multi-row fetch  | `read_row()` / `read_rows()`                                                    |
| Single / batch CUD operations | `update()` / `updates()`                                                        |
| Output parameters             | Via `params_out` dict                                                           |
| Transactions via `with`       | Auto rollback on exception                                                      |
| Partially return CSV          | `read_csv_partial` / `read_csv_partial_async`                                   |
| Bilingual column aliases      | `"Name\|이름"` syntax                                                           |
| Conditional SQL               | `#if` / `#elif` / `#endif`                                                      |
| Logging support               | Before and after execute hooks via `before...` and `after...` callables         |
| SQL injection protection      | Strict parsing in conditionals                                                  |

## License

MIT
