"""db_client_test"""

import json

from mysqlclient_client.client import Client
from tests.db_client import DbClient
from tests.db_settings import db_settings


def create_tables():
    """create tables"""

    db_client = Client(db_settings=db_settings)
    db_client.update("create_tables", {})


def upsert_user():
    """upsert user"""

    db_client = Client(db_settings=db_settings)

    row_count = db_client.update(
        "upsert_user",
        {"user_id": "gildong.hong", "user_name": "홍길똥", "user_rank": 1},
    )

    # affected row count: 1
    print(upsert_user.__name__, "affected row count:", row_count)


def upsert_user_params_out():
    """upsert user and get parameters"""

    db_client = Client(db_settings=db_settings)

    params_out = {"user_name": "", "user_rank": 0}
    db_client.update(
        "upsert_user",
        {"user_id": "gildong.hong", "user_name": "홍길동", "user_rank": 1},
        params_out,
    )

    # user_name, user_rank after update: 홍길동
    print(
        upsert_user_params_out.__name__,
        "user_name after update:",
        params_out["user_name"],
        params_out["user_rank"],
    )


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
    print(upsert_user_list.__name__, row_counts)


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
        print(upsert_delete_user_with.__name__, "affected row count:", row_count)


def read_user_one_row():
    """read first one row"""

    db_client = Client(db_settings=db_settings)

    row = db_client.read_row("read_user_id_all", {})

    # {'user_id': 'gildong.hong'}
    print(read_user_one_row.__name__, row)


def read_user_all_rows():
    """read all rows"""

    db_client = Client(db_settings=db_settings)

    rows = db_client.read_rows("read_user_id_all", {})

    # [
    #   {'user_id': 'gildong.hong'},
    #   {'user_id': 'sunja.kim'},
    #   {'user_id': 'malja.kim'}
    # ]
    print(read_user_all_rows.__name__, rows)


def read_csv_partial():
    """read csv partial"""

    db_client = Client(db_settings=db_settings)

    for chunk in db_client.read_csv_partial("read_csv_partial", {}):
        # b'\xef\xbb\xbf1,2001\xb3\xe2 01\xbf\xfd 01\xc0\xcf\r\n2,2001\xb3\xe2 ...
        print(read_csv_partial.__name__, chunk[:50])


def read_using_en_ko():
    """set column user_name, user_rank by en variable"""

    db_client = Client(db_settings=db_settings)

    # SELECT  user_id "Id", user_name "Name", user_rank "Rank"
    # FROM    t_user
    # WHERE   user_id = %(user_id)s
    rows = db_client.read_rows("read_user_alias", {"user_id": "gildong.hong"}, en=True)
    # [{"Id": "gildong.hong", "Name": "홍길동", "Rank": 1}]
    print(read_using_en_ko.__name__, rows)

    # SELECT  user_id "아이디", user_name "이름", user_rank "순위"
    # FROM    t_user
    # WHERE   user_id = %(user_id)s
    rows = db_client.read_rows("read_user_alias", {"user_id": "gildong.hong"}, en=False)
    # [{"아이디": "gildong.hong", "이름": "홍길동", "순위": 1}]
    print(read_using_en_ko.__name__, rows)


def read_using_conditional():
    """read using conditional (#if #elif #endif)"""

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
    print(read_using_conditional.__name__, [row["user_name"] for row in rows])

    # SELECT  user_id, user_name, user_rank, insert_time, update_time
    # FROM    t_user
    # WHERE   1 = 1
    #         AND user_name LIKE %(user_name)s
    rows = db_client.read_rows(
        "read_user_search", {"user_id": "", "user_name": "%김%", "user_rank": 0}
    )
    # ['김순자', '김말자']
    print(read_using_conditional.__name__, [row["user_name"] for row in rows])

    # SELECT  user_id, user_name, user_rank, insert_time, update_time
    # FROM    t_user
    # WHERE   1 = 1
    #         AND user_rank <= %(user_rank)s
    rows = db_client.read_rows(
        "read_user_search", {"user_id": "", "user_name": "", "user_rank": 3}
    )
    # ['홍길동', '김순자', '김말자']
    print(read_using_conditional.__name__, [row["user_name"] for row in rows])


def use_db_client():
    """use inherited class to not use db_settings every time"""

    db_client = DbClient()
    row = db_client.read_row("read_user_id_all", {})

    # {"user_id": "gildong.hong"}
    print(use_db_client.__name__, row)


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
        print(use_with.__name__, "len:", len(rows))


def insert_python_join():
    """insert python join"""

    with open("tests/console/python_join.json", encoding="utf-8") as f:
        params_list = json.load(f)

    db_client = DbClient()
    qry_list = [("insert_python_join", params) for params in params_list]
    row_counts = db_client.updates(qry_list)
    print(insert_python_join.__name__, len(row_counts))


if __name__ == "__main__":
    create_tables()

    upsert_user()
    upsert_user_params_out()
    upsert_user_list()
    upsert_delete_user_with()

    read_user_one_row()
    read_user_all_rows()
    read_using_en_ko()
    read_using_conditional()

    use_db_client()
    use_with()

    read_csv_partial()
