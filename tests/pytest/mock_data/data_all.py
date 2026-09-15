"""all data"""

import json
import re
from collections.abc import Callable
from datetime import datetime

from tests.pytest.mock_data.data_mock_model import (
    ReadRowsMock,
    UpdatesMock,
)
from tests.pytest.mock_data.data_read import (
    out_list as out_read,
)
from tests.pytest.mock_data.data_read import (
    rows_list as rows_read,
)
from tests.pytest.mock_data.data_update import (
    out_list as out_update,
)
from tests.pytest.mock_data.data_update import (
    rows_list as rows_update,
)

rows_combined = rows_read + rows_update
out_combined = out_read + out_update


def convert_type_dict(item: dict) -> dict:
    """convert datetime formatted string to datetime"""

    # "2024-05-10T08:23:14.316220"
    iso_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}"

    item_new = {}
    for k, v in item.items():
        if isinstance(v, str) and re.fullmatch(iso_pattern, v):
            item_new[k] = datetime.fromisoformat(v)
        else:
            item_new[k] = v
    return item_new


def convert_type_rows(data: ReadRowsMock) -> ReadRowsMock:
    """convert string to datetime if it was from datetime"""

    params_new = convert_type_dict(data.params)

    rows_new: list[dict] = []
    for item in data.rows:
        item_new = convert_type_dict(item)
        rows_new.append(item_new)

    data_new = ReadRowsMock(
        qry_key=data.qry_key,
        params=params_new,
        en=data.en,
        params_ignore=data.params_ignore,
        params_replace=data.params_replace,
        rows=rows_new,
    )
    return data_new


def convert_type_out(data: UpdatesMock) -> UpdatesMock:
    """convert string to datetime if it was from datetime"""

    params_new = convert_type_dict(data.params)
    params_out_new = convert_type_dict(data.params_out)

    data_new = UpdatesMock(
        qry_key=data.qry_key,
        params=params_new,
        params_ignore=data.params_ignore,
        params_replace=data.params_replace,
        params_out=params_out_new,
        row_count=data.row_count,
    )
    return data_new


def check_dup(
    lst: list[ReadRowsMock] | list[UpdatesMock],
    item_new: ReadRowsMock | UpdatesMock,
):
    """if duplicated raise error"""
    dup = next(
        (
            cur
            for cur in lst
            if cur.qry_key == item_new.qry_key
            and cur.params == item_new.params
            and cur.en == item_new.en
        ),
        None,
    )
    if dup:
        raise ValueError(f"duplicated keys: {dup.qry_key}")


def get_unique_rows_list() -> list[ReadRowsMock]:
    """get unique rows list from all rows_list"""

    rows_new: list[ReadRowsMock] = []
    for cur_combined in rows_combined:
        cur_new = convert_type_rows(cur_combined)

        check_dup(rows_new, cur_new)

        rows_new.append(cur_new)

    return rows_new


def get_unique_out_list() -> list[UpdatesMock]:
    """get unique out list from all out_list"""

    out_new: list[UpdatesMock] = []
    for cur_combined in out_combined:
        cur_new = convert_type_out(cur_combined)

        check_dup(out_new, cur_new)

        out_new.append(cur_new)

    return out_new


rows_list = get_unique_rows_list()
out_list = get_unique_out_list()


def filter_params_ignore(params: dict, params_ignore: list[str]) -> dict:
    """exclude params_ignore to ignore when filtering"""
    params_new = {k: v for k, v in params.items() if k not in params_ignore}
    return params_new


def replace_params(params: dict, params_replace: Callable | None) -> dict:
    """replace params by params_replace function"""
    if not params_replace:
        return params

    return params_replace(params)


def get_rows_by_params(qry_key: str, params: dict, en: bool = False) -> list[dict]:
    """get rows by qry_key and params (called from patch_psycopg2)"""

    qry_key_found = False
    params_data_candidate: list[dict] = []
    for data_cur in rows_list:
        params_in = filter_params_ignore(params, data_cur.params_ignore)
        params_in = replace_params(params_in, data_cur.params_replace)
        params_data = filter_params_ignore(data_cur.params, data_cur.params_ignore)

        is_qry_key_same = data_cur.qry_key == qry_key
        if not qry_key_found:
            qry_key_found = is_qry_key_same

        if is_qry_key_same:
            params_data_candidate.append(params_data)

        if not is_qry_key_same or params_data != params_in or data_cur.en != en:
            continue

        return data_cur.rows

    description = ""
    if not qry_key_found:
        description = (
            f"{qry_key} not exists in rows_list: {[item.qry_key for item in rows_list]}"
        )
    else:
        description = (
            f"Not found by {qry_key}"
            f" and {json.dumps(params, default=str, ensure_ascii=False)} and en:{en}"
            f"\nCandidate:"
            f" {json.dumps(params_data_candidate, default=str, ensure_ascii=False)}"
        )
    raise ValueError(description)


def get_out_by_params(qry_key: str, params: dict) -> tuple[dict, int]:
    """get params_out, row_count by qry_key and params (called from patch_psycopg2)"""

    qry_key_found = False
    params_data_candidate: list[dict] = []
    for data_cur in out_list:
        params_in = filter_params_ignore(params, data_cur.params_ignore)
        params_in = replace_params(params_in, data_cur.params_replace)
        params_data = filter_params_ignore(data_cur.params, data_cur.params_ignore)

        is_qry_key_same = data_cur.qry_key == qry_key
        if not qry_key_found:
            qry_key_found = is_qry_key_same

        if is_qry_key_same:
            params_data_candidate.append(params_data)

        if not is_qry_key_same or params_data != params_in:
            continue

        return (data_cur.params_out, data_cur.row_count)

    description = ""
    if not qry_key_found:
        description = (
            f"{qry_key} not exists in out_list: {[item.qry_key for item in out_list]}"
        )
    else:
        description = (
            f"Not found by {qry_key}"
            f" and {json.dumps(params, default=str, ensure_ascii=False)}"
            f"\nCandidate:"
            f" {json.dumps(params_data_candidate, default=str, ensure_ascii=False)}"
        )
    raise ValueError(description)
