"""test #foreach directive mimicking mybatis <foreach"""

import pytest

from mysqlclient_client.query_by_key.query import Query
from mysqlclient_client.query_by_key.query_util import (
    get_conditional,
    get_foreach,
    get_query_with_value,
)
from mysqlclient_client.query_by_key.settings import Settings as QrySettings


def test_foreach_basic_in_clause():
    """test basic IN clause with #{item}"""
    sql = """
    SELECT user_id, user_name
    FROM t_user
    WHERE user_id IN
    #foreach item in ${user_ids} open="(" separator="," close=")"
        #{item}
    #endfor
    """
    params = {"user_ids": ["gildong.hong", "sunja.kim"]}
    res = get_foreach(sql, params, dialect="mysql")

    assert "WHERE user_id IN" in res
    assert "(%(__f_item_0_0)s,%(__f_item_0_1)s)" in res
    assert params["__f_item_0_0"] == "gildong.hong"
    assert params["__f_item_0_1"] == "sunja.kim"

    filled = get_query_with_value(res, params)
    assert "('gildong.hong','sunja.kim')" in filled


def test_foreach_mybatis_style_not_supported():
    """test that MyBatis attribute style is not supported and raises ValueError"""
    sql = (
        "SELECT * FROM t_user\nWHERE user_id IN\n"
        '#foreach collection="user_ids" item="u_id" index="idx" '
        'open="(" separator=", " close=")"\n'
        "    #{u_id}\n"
        "#endforeach"
    )
    params = {"user_ids": [10, 20, 30]}
    with pytest.raises(ValueError, match="Invalid #foreach syntax"):
        get_foreach(sql, params, dialect="mysql")


def test_foreach_endforeach_tag():
    """test #endforeach closing tag with pythonic syntax"""
    sql = """
    SELECT * FROM t_user
    WHERE user_id IN
    #foreach item in ${user_ids} open="(" separator="," close=")"
        #{item}
    #endforeach
    """
    params = {"user_ids": ["a", "b"]}
    res = get_foreach(sql, params, dialect="mysql")
    assert "(%(__f_item_0_0)s,%(__f_item_0_1)s)" in res


def test_foreach_native_mysql_placeholder():
    """test using native %(item)s placeholder inside #foreach"""
    sql = """
    SELECT * FROM t_user
    WHERE user_id IN
    #foreach item in user_ids open="(" separator="," close=")"
        %(item)s
    #endfor
    """
    params = {"user_ids": ["a", "b"]}
    res = get_foreach(sql, params, dialect="mysql")

    assert "(%(__f_item_0_0)s,%(__f_item_0_1)s)" in res
    assert params["__f_item_0_0"] == "a"
    assert params["__f_item_0_1"] == "b"


def test_foreach_batch_insert_dict_properties():
    """test multi-row insert with dict property access #{user.prop}"""
    sql = """
    INSERT INTO t_user (user_id, user_name, user_rank) VALUES
    #foreach user in ${users} separator=","
        (#{user.user_id}, #{user.user_name}, #{user.user_rank})
    #endfor;
    """
    params = {
        "users": [
            {"user_id": "user1", "user_name": "Alice", "user_rank": 1},
            {"user_id": "user2", "user_name": "Bob", "user_rank": 2},
        ]
    }
    res = get_foreach(sql, params, dialect="mysql")

    assert "%(__f_user_user_id_0_0)s" in res
    assert "%(__f_user_user_name_0_0)s" in res
    assert "%(__f_user_user_rank_0_0)s" in res
    assert "%(__f_user_user_id_0_1)s" in res
    assert "%(__f_user_user_name_0_1)s" in res
    assert "%(__f_user_user_rank_0_1)s" in res

    filled = get_query_with_value(res, params)
    assert "('user1', 'Alice', 1),\n        ('user2', 'Bob', 2);" in filled


def test_foreach_with_index():
    """test index variable in #foreach (${idx} and #{idx})"""
    sql = """
    SELECT * FROM t_log WHERE (step, val) IN
    #foreach idx, item in ${items} open="(" separator="," close=")"
        (${idx}, #{item})
    #endfor
    """
    params = {"items": ["first", "second"]}
    res = get_foreach(sql, params, dialect="mysql")

    assert "(0, %(__f_item_0_0)s),(1, %(__f_item_0_1)s)" in res
    filled = get_query_with_value(res, params)
    assert "(0, 'first'),(1, 'second')" in filled


def test_foreach_dict_map_iteration():
    """test iterating dictionary/map key-value pairs"""
    sql = """
    SELECT * FROM t_config
    WHERE
    #foreach k, v in ${configs} separator=" AND "
        ${k} = #{v}
    #endfor
    """
    params = {"configs": {"env": "prod", "region": "kr"}}
    res = get_foreach(sql, params, dialect="mysql")

    assert "env = %(__f_v_0_0)s AND region = %(__f_v_0_1)s" in res
    filled = get_query_with_value(res, params)
    assert "env = 'prod' AND region = 'kr'" in filled


def test_foreach_empty_collection():
    """test empty collection renders empty string without open/close"""
    sql = """
    SELECT * FROM t_user
    WHERE user_id IN
    #foreach item in ${user_ids} open="(" separator="," close=")"
        #{item}
    #endfor
    """
    params = {"user_ids": []}
    res = get_foreach(sql, params, dialect="mysql")
    assert res.strip() == "SELECT * FROM t_user\n    WHERE user_id IN"


def test_foreach_missing_key_raises_key_error():
    """test missing collection key raises KeyError"""
    sql = """
    #foreach item in ${missing_list} open="(" separator="," close=")"
        #{item}
    #endfor
    """
    with pytest.raises(KeyError, match="'missing_list' not in params"):
        get_foreach(sql, {}, dialect="mysql")


def test_foreach_none_value_raises_value_error():
    """test None collection value raises ValueError"""
    sql = """
    #foreach item in ${user_ids} open="(" separator="," close=")"
        #{item}
    #endfor
    """
    with pytest.raises(
        ValueError, match="'user_ids' value in params cannot be None"
    ):
        get_foreach(sql, {"user_ids": None}, dialect="mysql")


def test_foreach_invalid_type_raises_type_error():
    """test non-iterable/non-collection value raises TypeError"""
    sql = """
    #foreach item in ${user_ids} open="(" separator="," close=")"
        #{item}
    #endfor
    """
    with pytest.raises(
        TypeError, match="'user_ids' must be a list, tuple, set, or dict"
    ):
        get_foreach(sql, {"user_ids": 12345}, dialect="mysql")


def test_foreach_unclosed_raises_value_error():
    """test unclosed #foreach directive raises ValueError"""
    sql = """
    SELECT * FROM t_user
    WHERE id IN #foreach item in ${user_ids} open="(" separator="," close=")"
        #{item}
    """
    with pytest.raises(ValueError, match="Unclosed #foreach"):
        get_foreach(sql, {"user_ids": [1]}, dialect="mysql")


def test_foreach_nested_inside_if():
    """test #if wrapping #foreach directive"""
    sql = """
    SELECT * FROM t_user
    WHERE 1 = 1
    #if ${has_users}
        AND user_id IN
        #foreach item in ${user_ids} open="(" separator="," close=")"
            #{item}
        #endfor
    #endif
    """
    # 1. Condition is False: user_ids doesn't even need to exist in params
    params_f = {"has_users": False}
    step1_f = get_conditional(sql, params_f)
    step2_f = get_foreach(step1_f, params_f, dialect="mysql")
    assert "user_id IN" not in step2_f

    # 2. Condition is True: user_ids is expanded
    params_t = {"has_users": True, "user_ids": ["u1", "u2"]}
    step1_t = get_conditional(sql, params_t)
    step2_t = get_foreach(step1_t, params_t, dialect="mysql")
    assert "AND user_id IN" in step2_t
    assert "(%(__f_item_0_0)s,%(__f_item_0_1)s)" in step2_t


def test_foreach_with_inner_if():
    """test #if conditional inside #foreach body"""
    sql = """
    #foreach user in ${users} separator=","
        #if ${user.active}
        #{user.id}
        #endif
    #endfor
    """
    params = {
        "users": [
            {"id": 1, "active": True},
            {"id": 2, "active": False},
            {"id": 3, "active": True},
        ]
    }
    res = get_foreach(sql, params, dialect="mysql")
    assert "%(__f_user_id_0_0)s" in res
    assert "%(__f_user_id_0_2)s" in res
    filled = get_query_with_value(res, params)
    assert "1" in filled and "3" in filled
    assert "2" not in filled


def test_foreach_with_query_class():
    """test Query class get_query_by_key with #foreach"""
    all_query = {
        "read_users_in": """
        SELECT  user_id, user_name
        FROM    t_user
        WHERE   user_id IN
        #foreach id in ${user_ids} open="(" separator="," close=")"
            #{id}
        #endfor
        """
    }
    query = Query(
        qry_settings=QrySettings(
            use_en_ko_column_alias=False,
            use_conditional=True,
            all_query=all_query,
        )
    )
    params = {"user_ids": ["gildong.hong", "sunja.kim"]}
    res = query.get_query_by_key("read_users_in", params, "read")
    assert "(%(__f_id_0_0)s,%(__f_id_0_1)s)" in res
    assert params["__f_id_0_0"] == "gildong.hong"
    assert params["__f_id_0_1"] == "sunja.kim"
