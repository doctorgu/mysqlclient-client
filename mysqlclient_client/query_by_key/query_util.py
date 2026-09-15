"""client_util"""

import re
from datetime import datetime


def get_conditional(qry_str: str, params: dict) -> str:
    """
    return true or false part by condition.
    `#if target == 'korea' ... #elif target == 'vietnam' ... #else ... #endif`
    """

    def eval_safe(to_eval: str, params: dict) -> bool:
        """
        # assert eval_safe('%(target)s != ""', {"target": ""}) is False
        # assert eval_safe('"A" in %(targets)s', {"targets": ["A", "B"]}) is True
        # assert eval_safe('"A" not in %(targets)s', {"targets": ["A", "B"]}) is False
        # assert eval_safe("%(t)s in [i for i in range(10)]", {"t": 1}) is True
        """

        # remove '%(' and ')s' from %(target)s
        to_eval = re.sub(r"%\((.*?)\)s", r"\1", to_eval)

        # allow below:
        # - string inside quotes
        # - digit
        to_check = re.sub(r"""(".*?"|'.*?'|\b\d+\b)""", "", to_eval)

        param_set = {key for key in params}
        op_set = {
            "==",
            "!=",
            ">=",
            "<=",
            ">",
            "<",
            "in",
            "not",
            "and",
            "or",
            "[",
            "]",
            "(",
            ")",
            ",",
        }

        eval_set = set(to_check.split())
        diff = eval_set - (param_set | op_set)
        if diff:
            raise ValueError(f"'{diff}' not in {param_set | op_set}")

        is_include = bool(eval(to_eval, {}, params.copy()))
        return is_include

    lines = qry_str.split("\n")
    rets = []
    is_include = True
    is_checked = False
    for line in lines:
        line_strip = line.strip()
        if line_strip.startswith(("#if", "#elif")):
            if not is_checked:
                _, condition = line_strip.split(maxsplit=1)
                is_include = eval_safe(condition, params.copy())
                if is_include:
                    is_checked = True
            else:
                is_include = False
        elif line_strip.startswith("#else"):
            is_include = not is_checked
        elif line_strip.startswith("#endif"):
            is_include = True
            is_checked = False
        elif is_include:
            rets.append(line)

    return "\n".join(rets)


def rep_kv(query: str, tab_count: int, **kwargs) -> str:
    """
    replace {key} with value when `rev_ky("WHERE user_name = {key}", key="u.user_name")`
    """

    ret = query
    ret = re.sub(r"^", " " * 4 * tab_count, ret, flags=re.MULTILINE)
    for k, v in kwargs.items():
        ret = ret.replace("{" + k + "}", str(v))

    return ret


def get_query_with_value(qry_str: str, params: dict) -> str:
    """replace raw query to value filled query"""

    def escape_literal(value) -> str:
        ret = ""
        if isinstance(value, str):
            ret = "'" + value.replace("'", "''") + "'"
        elif isinstance(value, datetime):
            ret = f"'{value.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
        elif isinstance(value, (list, tuple)):
            ret = str(value)
        elif value is None:
            ret = "NULL"
        else:
            ret = str(value)
        return ret

    if isinstance(params, (list, tuple)):
        if not params:
            return qry_str
        params = params[0] if isinstance(params[0], dict) else {}

    query_replaced = qry_str
    for key, value in params.items():
        find = f"%({key})s"
        if find in query_replaced:
            replace = escape_literal(value)
            query_replaced = query_replaced.replace(find, replace)
    # %% -> % : mysqlclient / db-api
    # {{}} -> {} : python
    query_replaced = (
        query_replaced.replace("%%", "%").replace("{{", "{").replace("}}", "}")
    )

    return query_replaced


def replace_en_ko_column_alias(qry_str: str, en: bool) -> str:
    """ "
    return en part or ko part separated by '|' using en variable
    ex:
    tbl.obj_nm "File Name|파일명"
    ->
    tbl.obj_nm "File Name"
    """

    pattern = r'(?P<ws>\s)"(?P<en>[^"]+)\|(?P<ko>[^"]+)"'
    en_ko = "en" if en else "ko"
    repl = rf'\g<ws>"\g<{en_ko}>"'
    qry_str_new = re.sub(pattern, repl, qry_str, flags=re.MULTILINE | re.IGNORECASE)
    return qry_str_new
