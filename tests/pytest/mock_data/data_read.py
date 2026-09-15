"""mock data for common"""

from tests.pytest.mock_data.data_mock_model import (
    ReadRowsMock,
    UpdatesMock,
)

rows_list: list[ReadRowsMock] = []
out_list: list[UpdatesMock] = []
params_ignore_common = ["insert_time", "update_time"]

rows_list.append(
    ReadRowsMock(
        qry_key="read_user_id_all",
        params={},
        params_ignore=params_ignore_common,
        rows=[
            {"user_id": "gildong.hong"},
            {"user_id": "sunja.kim"},
            {"user_id": "malja.kim"},
        ],
    )
)

rows_list.append(
    ReadRowsMock(
        qry_key="read_user_search",
        params={"user_id": "gildong.hong", "user_name": "", "user_rank": 0},
        params_ignore=params_ignore_common,
        rows=[{"user_name": "홍길동"}],
    )
)
rows_list.append(
    ReadRowsMock(
        qry_key="read_user_search",
        params={"user_id": "", "user_name": "%김%", "user_rank": 0},
        params_ignore=params_ignore_common,
        rows=[{"user_name": "김순자"}, {"user_name": "김말자"}],
    )
)
rows_list.append(
    ReadRowsMock(
        qry_key="read_user_search",
        params={"user_id": "", "user_name": "", "user_rank": 3},
        params_ignore=params_ignore_common,
        rows=[
            {"user_name": "홍길동"},
            {"user_name": "김순자"},
            {"user_name": "김말자"},
        ],
    )
)

rows_list.append(
    ReadRowsMock(
        qry_key="read_user_alias",
        params={"user_id": "gildong.hong"},
        en=True,
        params_ignore=params_ignore_common,
        rows=[{"Id": "gildong.hong", "Name": "홍길동", "Rank": 1}],
    )
)
rows_list.append(
    ReadRowsMock(
        qry_key="read_user_alias",
        params={"user_id": "gildong.hong"},
        en=False,
        params_ignore=params_ignore_common,
        rows=[{"아이디": "gildong.hong", "이름": "홍길동", "순위": 1}],
    )
)
