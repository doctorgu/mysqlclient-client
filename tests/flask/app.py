"""flask app"""

from datetime import UTC, datetime

from flask import Flask, Response, jsonify, render_template

from mysqlclient_client.client import Client
from tests.db_client import DbClient
from tests.db_settings import db_settings

app = Flask(__name__)


def get_json(
    *,
    fn_name: str,
    message: str | int | dict | None | list[str] | list[int] | list[dict],
):
    """return json"""
    return jsonify({"fn_name": fn_name, "message": message})


@app.route("/")
def home():
    """home"""

    return render_template("index.html")


@app.route("/create-tables")
def create_tables():
    """create tables"""

    db_client = Client(db_settings=db_settings)
    db_client.update("create_tables", {})
    return get_json(fn_name=create_tables.__name__, message="table created")


@app.route("/upsert-user")
def upsert_user():
    """upsert user"""

    db_client = Client(db_settings=db_settings)

    row_count = db_client.update(
        "upsert_user",
        {"user_id": "gildong.hong", "user_name": "홍길똥", "user_rank": 1},
    )

    # affected row count: 1
    return get_json(
        fn_name=upsert_user.__name__, message=f"affected row count: {row_count}"
    )


@app.route("/upsert-user-params-out")
def upsert_user_params_out():
    """upsert user and get parameters"""

    db_client = Client(db_settings=db_settings)

    params_out = {"user_name": "", "user_rank": 0}
    db_client.update(
        "upsert_user",
        {"user_id": "gildong.hong", "user_name": "홍길동", "user_rank": 0},
        params_out,
    )

    # user_name, user_rank after update: 홍길동
    return get_json(
        fn_name=upsert_user_params_out.__name__,
        message=(
            f"user_name after update:"
            f" {params_out['user_name']}, {params_out['user_rank']}"
        ),
    )


@app.route("/upsert-user-list")
def upsert_user_list():
    """upsert user list (one transaction)"""

    db_client = Client(db_settings=db_settings)

    qry_list = [
        (
            "upsert_user",
            {"user_id": "sunja.kim", "user_name": "김순자", "user_rank": 2},
        ),
        (
            "upsert_user",
            {"user_id": "malja.kim", "user_name": "김말자", "user_rank": 3},
        ),
    ]
    row_counts = db_client.updates(qry_list)

    # [1, 1]
    return get_json(fn_name=upsert_user_list.__name__, message=row_counts)


@app.route("/upsert-delete-user-with")
def upsert_delete_user_with():
    """upsert user and delete in with (one transaction)"""

    with Client(db_settings=db_settings) as db_client:
        id_ = "youngja.lee"
        user_name = "이영자"
        user_rank = 4
        db_client.update(
            "upsert_user",
            {"user_id": id_, "user_name": user_name, "user_rank": user_rank},
        )

        row_count = db_client.update("delete_user", {"user_id": id_})

        # affected row count: 1
        return get_json(
            fn_name=upsert_delete_user_with.__name__,
            message=f"affected row count: {row_count}",
        )


@app.route("/read-user-one-row")
def read_user_one_row():
    """read first one row"""

    db_client = Client(db_settings=db_settings)

    row = db_client.read_row("read_user_id_all", {})

    # {'user_id': 'gildong.hong'}
    return get_json(fn_name=read_user_one_row.__name__, message=row)


@app.route("/read-user-all-rows")
def read_user_all_rows():
    """read all rows"""

    db_client = Client(db_settings=db_settings)

    rows = db_client.read_rows("read_user_id_all", {})

    # [
    #   {'user_id': 'gildong.hong'},
    #   {'user_id': 'sunja.kim'},
    #   {'user_id': 'malja.kim'}
    # ]
    return get_json(fn_name=read_user_all_rows.__name__, message=rows)


@app.route("/read-csv-partial")
def read_csv_partial():
    """read csv partial"""

    db_client = Client(db_settings=db_settings)
    filename = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.csv"

    return Response(
        db_client.read_csv_partial("read_csv_partial", {}),
        mimetype="text/csv",
        headers={
            # if FE and BE are on different origins,
            # server must expose the Content-Disposition header
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Content-Disposition": f'attachment; filename="{filename}"',
            # Very important for progressive saving in many browsers
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",  # Important if using nginx
            "Transfer-Encoding": "chunked",
        },
    )


@app.route("/read-using-en-ko1")
def read_using_en_ko1():
    """set column user_name, user_rank by en variable"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id "Id", user_name "Name", user_rank "Rank"
    # FROM    t_user
    # WHERE   user_id = %(user_id)s
    rows = db_client.read_rows("read_user_alias", {"user_id": "gildong.hong"}, en=True)
    # [{"Id": "gildong.hong", "Name": "홍길동", "Rank": 1}]
    return get_json(fn_name=read_using_en_ko1.__name__, message=rows)


@app.route("/read-using-en-ko2")
def read_using_en_ko2():
    """set column user_name by en variable"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id "아이디", user_name "이름", user_rank "순위"
    # FROM    t_user
    # WHERE   user_id = %(user_id)s
    rows = db_client.read_rows("read_user_alias", {"user_id": "gildong.hong"}, en=False)
    # [{"아이디": "gildong.hong", "이름": "홍길동", "순위": 1}]
    return get_json(fn_name=read_using_en_ko2.__name__, message=rows)


@app.route("/read-using-conditional1")
def read_using_conditional1():
    """read using conditional 1 (#if #elif #endif)"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id, user_name, user_rank, insert_time, update_time
    # FROM    t_user
    # WHERE   1 = 1
    #         AND user_id = %(user_id)s
    rows = db_client.read_rows(
        "read_user_search",
        {"user_id": "gildong.hong", "user_name": "", "user_rank": 0},
    )
    # ['홍길동']
    return get_json(
        fn_name=read_using_conditional1.__name__,
        message=[row["user_name"] for row in rows],
    )


@app.route("/read-using-conditional2")
def read_using_conditional2():
    """read using conditional 2 (#if #elif #endif)"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id, user_name, user_rank, insert_time, update_time
    # FROM    t_user
    # WHERE   1 = 1
    #         AND user_name LIKE %(user_name)s
    rows = db_client.read_rows(
        "read_user_search", {"user_id": "", "user_name": "%김%", "user_rank": 0}
    )
    # ['김순자', '김말자']
    return get_json(
        fn_name=read_using_conditional2.__name__,
        message=[row["user_name"] for row in rows],
    )


@app.route("/read-using-conditional3")
def read_using_conditional3():
    """read using conditional 3 (#if #elif #endif)"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id, user_name, user_rank, insert_time, update_time
    # FROM    t_user
    # WHERE   1 = 1
    #         AND user_rank <= %(user_rank)s
    rows = db_client.read_rows(
        "read_user_search", {"user_id": "", "user_name": "", "user_rank": 3}
    )
    # ['홍길동', '김순자', '김말자']
    return get_json(
        fn_name=read_using_conditional3.__name__,
        message=[row["user_name"] for row in rows],
    )


@app.route("/read-using-include1")
def read_using_include1():
    """read using include 1 (#include)"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id
    # FROM    t_user
    # WHERE   1 = 1
    #         AND user_id = %(user_id)s
    rows = db_client.read_rows(
        "read_user_by_key",
        {"user_id": "gildong.hong", "user_name": "", "user_rank": 0},
    )
    # ['gildong.hong']
    return get_json(
        fn_name=read_using_include1.__name__,
        message=[row["user_id"] for row in rows],
    )


@app.route("/read-using-include2")
def read_using_include2():
    """read using include 2 (#include)"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id
    # FROM    t_user
    # WHERE   1 = 1
    #         AND user_name LIKE %(user_name)s
    rows = db_client.read_rows(
        "read_user_by_key", {"user_id": "", "user_name": "%김%", "user_rank": 0}
    )
    # ['sunja.kim', 'malja.kim']
    return get_json(
        fn_name=read_using_include2.__name__,
        message=[row["user_id"] for row in rows],
    )


@app.route("/read-using-include3")
def read_using_include3():
    """read using include 3 (#include)"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id
    # FROM    t_user
    # WHERE   1 = 1
    #         AND user_rank <= %(user_rank)s
    rows = db_client.read_rows(
        "read_user_by_key", {"user_id": "", "user_name": "", "user_rank": 3}
    )
    # ['gildong.hong', 'sunja.kim', 'malja.kim']
    return get_json(
        fn_name=read_using_include3.__name__,
        message=[row["user_id"] for row in rows],
    )


@app.route("/use-db-client")
def use_db_client():
    """use inherited class to not use db_settings every time"""

    db_client = DbClient()
    row = db_client.read_row("read_user_id_all", {})

    # {"user_id": "gildong.hong"}
    return get_json(fn_name=use_db_client.__name__, message=row)


@app.route("/use-with")
def use_with():
    """use with to use transaction (all or nothing)"""

    try:
        with DbClient() as db_client:
            for i in range(3):
                db_client.update(
                    "upsert_user",
                    {
                        "user_id": f"{i}.오",
                        "user_name": f"오{i}",
                        "user_rank": f"{i}",
                    },
                )
                rows = db_client.read_rows(
                    "read_user_search",
                    {"user_id": "", "user_name": "오%", "user_rank": 0},
                )
                print(use_with.__name__, "len:", len(rows))

                if i == 2:
                    raise RuntimeError("to cancel 3 upsert")
    except RuntimeError:
        rows = DbClient().read_rows(
            "read_user_search", {"user_id": "", "user_name": "오%", "user_rank": 0}
        )
        # 0 because rolled back all upsert_user
        return get_json(fn_name=use_with.__name__, message=f"len: {len(rows)}")


# flask --app .\tests\flask\app.py run --debug
