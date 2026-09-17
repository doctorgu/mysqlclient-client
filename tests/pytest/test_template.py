"""test template substitution (${param})"""

import pytest

from mysqlclient_client.query_by_key.query import Query
from mysqlclient_client.query_by_key.query_util import get_template
from mysqlclient_client.query_by_key.settings import Settings


def test_template_basic():
    """test basic ${param} replacement"""
    qry = "SELECT id FROM ${table_name}"
    params = {"table_name": "t_user"}
    assert get_template(qry, params) == "SELECT id FROM t_user"


def test_template_multiple_placeholders():
    """test multiple ${param} placeholders"""
    qry = "SELECT ${col1}, ${col2} FROM ${table}"
    params = {"col1": "id", "col2": "name", "table": "t_user"}
    assert get_template(qry, params) == "SELECT id, name FROM t_user"


def test_template_spaces_inside_braces():
    """test spaces inside braces e.g. ${ param }"""
    qry = "SELECT id FROM ${ table_name }"
    params = {"table_name": "t_user"}
    assert get_template(qry, params) == "SELECT id FROM t_user"


def test_template_nested_dot_notation():
    """test nested dot notation e.g. ${config.table}"""
    qry = "SELECT id FROM ${config.table}"
    params = {"config": {"table": "t_user"}}
    assert get_template(qry, params) == "SELECT id FROM t_user"


def test_template_missing_key_raises_key_error():
    """test missing key raises KeyError"""
    qry = "SELECT id FROM ${table_name}"
    params = {}
    with pytest.raises(KeyError, match="'table_name' not in params"):
        get_template(qry, params)


def test_template_none_value_raises_value_error():
    """test None value raises ValueError"""
    qry = "SELECT id FROM ${table_name}"
    params = {"table_name": None}
    with pytest.raises(ValueError, match="'table_name' value in params cannot be None"):
        get_template(qry, params)


def test_template_with_query_class():
    """test template integration through Query class"""
    all_query = {
        "read_dynamic": ("SELECT id FROM ${table_name} WHERE user_id = %(user_id)s")
    }
    query = Query(
        qry_settings=Settings(
            use_en_ko_column_alias=False,
            use_conditional=True,
            all_query=all_query,
        )
    )
    result = query.get_query_by_key(
        "read_dynamic",
        {"table_name": "t_user", "user_id": "user1"},
        "read",
    )
    assert "SELECT id FROM t_user WHERE user_id = %(user_id)s" in result


def test_template_combined_with_if():
    """test template combined with #if conditional"""
    all_query = {
        "read_dyn_if": (
            "SELECT id FROM ${table}\n#if ${active}\nWHERE is_active = 1\n#endif"
        )
    }
    query = Query(
        qry_settings=Settings(
            use_en_ko_column_alias=False,
            use_conditional=True,
            all_query=all_query,
        )
    )
    res_active = query.get_query_by_key(
        "read_dyn_if",
        {"table": "t_user", "active": True},
        "read",
    )
    assert "FROM t_user" in res_active
    assert "WHERE is_active = 1" in res_active

    res_inactive = query.get_query_by_key(
        "read_dyn_if",
        {"table": "t_user", "active": False},
        "read",
    )
    assert "FROM t_user" in res_inactive
    assert "WHERE is_active = 1" not in res_inactive


def test_if_raw_variable_raises_error():
    """test that raw variables without ${} in #if raise ValueError"""
    all_query = {
        "read_raw_if": (
            "SELECT id FROM t_user\n#if active\nWHERE is_active = 1\n#endif"
        ),
        "read_raw_comp": (
            "SELECT id FROM t_user\n#if target == 'korea'\nWHERE country = 'KR'\n#endif"
        ),
        "read_raw_rev": (
            "SELECT id FROM t_user\n#if 'korea' == target\nWHERE country = 'KR'\n#endif"
        ),
        "read_raw_val": (
            "SELECT id FROM t_user\n"
            "#if ${target} == korea\n"
            "WHERE country = 'KR'\n"
            "#endif"
        ),
        "read_fn_call": (
            "SELECT id FROM t_user\n"
            "#if len(${targets}) > 0\n"
            "WHERE country = 'KR'\n"
            "#endif"
        ),
    }
    query = Query(
        qry_settings=Settings(
            use_en_ko_column_alias=False,
            use_conditional=True,
            all_query=all_query,
        )
    )
    with pytest.raises(ValueError, match="Raw variable"):
        query.get_query_by_key("read_raw_if", {"active": True}, "read")

    with pytest.raises(ValueError, match="Raw variable"):
        query.get_query_by_key("read_raw_comp", {"target": "korea"}, "read")

    with pytest.raises(ValueError, match="Raw variable"):
        query.get_query_by_key("read_raw_rev", {"target": "korea"}, "read")

    with pytest.raises(ValueError, match="Raw variable"):
        query.get_query_by_key("read_raw_val", {"target": "korea"}, "read")

    with pytest.raises(ValueError, match="Raw variable"):
        query.get_query_by_key("read_fn_call", {"targets": ["A"]}, "read")


def test_if_template_variable():
    """test #if with comparison and containment using ${param}"""
    all_query = {
        "read_comp": (
            "SELECT id FROM t_user\n"
            "#if ${target} == 'korea'\n"
            "WHERE country = 'KR'\n"
            "#elif 'A' in ${targets}\n"
            "WHERE country = 'A'\n"
            "#endif"
        )
    }
    query = Query(
        qry_settings=Settings(
            use_en_ko_column_alias=False,
            use_conditional=True,
            all_query=all_query,
        )
    )
    res_kr = query.get_query_by_key(
        "read_comp",
        {"target": "korea", "targets": []},
        "read",
    )
    assert "WHERE country = 'KR'" in res_kr

    res_a = query.get_query_by_key(
        "read_comp",
        {"target": "japan", "targets": ["A", "B"]},
        "read",
    )
    assert "WHERE country = 'A'" in res_a


def test_template_combined_with_include():
    """test template combined with #include"""
    all_query = {
        "_sub_from": "FROM ${table}",
        "read_dyn_inc": "SELECT id\n#include _sub_from",
    }
    query = Query(
        qry_settings=Settings(
            use_en_ko_column_alias=False,
            use_conditional=True,
            all_query=all_query,
        )
    )
    res = query.get_query_by_key(
        "read_dyn_inc",
        {"table": "t_user"},
        "read",
    )
    assert "SELECT id\nFROM t_user" in res


def test_template_escaped():
    """test escaped \\${param} unescapes to literal ${param}"""
    qry = r"SELECT '\${not_a_param}' FROM ${table}"
    params = {"table": "t_user"}
    assert get_template(qry, params) == "SELECT '${not_a_param}' FROM t_user"
