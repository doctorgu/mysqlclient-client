"""test #include query functionality"""

import pytest

from mysqlclient_client.client import Client
from mysqlclient_client.query_by_key.query_util import get_include
from tests.db_settings import db_settings
from tests.pytest.test_fn_common import patch_mysqlclient


def test_get_include_success():
    """test get_include with valid parameters and string values"""
    all_query = {
        "_filter": {
            "by_id": "AND user_id = %(user_id)s",
            "by_name": "AND user_name = %(user_name)s",
        },
        "_from_clause": "FROM t_user",
        "read_user": """
SELECT  user_id
#include _from_clause
WHERE   1 = 1
#include _filter(by_id)
""",
    }

    result = get_include(all_query["read_user"], all_query)
    assert "FROM t_user" in result
    assert "AND user_id = %(user_id)s" in result


def test_get_include_nested():
    """test nested #include resolution"""
    all_query = {
        "_leaf": "SELECT  user_id, user_name",
        "_mid": """
#include _leaf
FROM    t_user
""",
        "main": """
#include _mid
WHERE 1 = 1
""",
    }
    result = get_include(all_query["main"], all_query)
    assert "SELECT  user_id, user_name" in result
    assert "FROM    t_user" in result


def test_get_include_missing_target():
    """test error when target does not exist"""
    all_query = {}
    with pytest.raises(KeyError, match="'_non_existent' not in all_query"):
        get_include("#include _non_existent", all_query)


def test_get_include_param_passed_to_str():
    """test error when parameter passed to a non-dict value"""
    all_query = {"_str_query": "SELECT 1"}
    with pytest.raises(ValueError, match="does not have sub keys"):
        get_include("#include _str_query(some_key)", all_query)


def test_get_include_missing_subkey():
    """test error when parameter passed does not exist in dict"""
    all_query = {"_dict_query": {"key_a": "val_a"}}
    with pytest.raises(KeyError, match="sub key 'key_b' not in '_dict_query'"):
        get_include("#include _dict_query(key_b)", all_query)


def test_get_include_no_param_for_dict():
    """test error when no parameter passed to a dict value"""
    all_query = {"_dict_query": {"key_a": "val_a"}}
    with pytest.raises(
        ValueError, match="has sub keys, but no sub key parameter was passed"
    ):
        get_include("#include _dict_query", all_query)


def test_get_include_inline_not_allowed():
    """test error when #include is used inline"""
    all_query = {"_cols": "user_id"}
    with pytest.raises(ValueError, match="inline #include is not allowed"):
        get_include("SELECT #include _cols FROM t_user", all_query)


def test_get_include_invalid_syntax_multiple_params():
    """test error when multiple parameters are passed"""
    all_query = {"_dict_query": {"key_a": "val_a"}}
    with pytest.raises(ValueError, match="invalid #include syntax"):
        get_include("#include _dict_query(key_a, key_b)", all_query)


def test_client_read_user_by_key(mocker):
    """test Client read_rows with read_user_by_key query containing #if and #include"""
    patch_mysqlclient(mocker)

    db = Client(db_settings=db_settings)

    # 1. user_id
    rows1 = db.read_rows(
        "read_user_by_key",
        {"user_id": "gildong.hong", "user_name": "", "user_rank": 0},
    )
    assert [r["user_id"] for r in rows1] == ["gildong.hong"]

    # 2. user_name
    rows2 = db.read_rows(
        "read_user_by_key",
        {"user_id": "", "user_name": "%김%", "user_rank": 0},
    )
    assert [r["user_id"] for r in rows2] == ["sunja.kim", "malja.kim"]

    # 3. user_rank
    rows3 = db.read_rows(
        "read_user_by_key",
        {"user_id": "", "user_name": "", "user_rank": 3},
    )
    assert [r["user_id"] for r in rows3] == [
        "gildong.hong",
        "sunja.kim",
        "malja.kim",
    ]
