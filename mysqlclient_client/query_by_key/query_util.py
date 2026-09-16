"""client_util"""

import re
from datetime import datetime


def get_conditional(qry_str: str, params: dict) -> str:
    """
    return true or false part by condition.
    `#if target == 'korea' ... #elif target == 'vietnam' ... #else ... #endif`
    """

    def eval_safe(condition: str, params: dict) -> bool:
        """
        allow only ${param} and operators for condition to call eval safely
        """

        op_set = {
            "==",
            "!=",
            ">=",
            "<=",
            ">",
            "<",
            "+",
            "-",
            "*",
            "/",
            "//",
            "%",
            "**",
            "in",
            "not",
            "and",
            "or",
            "is",
            "True",
            "False",
            "None",
            "[",
            "]",
            "(",
            ")",
            ",",
        }

        # Check for raw variables outside of quotes, numbers, and ${param}
        to_check = re.sub(r"""(".*?"|'.*?'|\b\d+(?:\.\d+)?\b)""", "", condition)
        to_check = re.sub(r"\$\{\s*([a-zA-Z0-9_.]+)\s*\}", "", to_check)
        to_check = re.sub(r"([()[\],])", r" \1 ", to_check)

        eval_set = set(to_check.split())
        diff = eval_set - op_set
        if diff:
            raise ValueError(
                f"Raw variable or invalid syntax '{diff}' not allowed in condition. "
                "Only '${param}' syntax is supported."
            )

        pattern_param = r"\$\{\s*([a-zA-Z0-9_.]+)\s*\}"
        used_params = re.findall(pattern_param, condition)

        def get_val(key: str):
            if key in params:
                return params[key]
            if "." in key:
                parts = key.split(".")
                curr = params
                for p in parts:
                    if isinstance(curr, dict) and p in curr:
                        curr = curr[p]
                    else:
                        raise KeyError(f"'{key}' not in params")
                return curr
            raise KeyError(f"'{key}' not in params")

        eval_dict = {}
        param_map = {}
        for idx, p in enumerate(used_params):
            if p not in param_map:
                var_name = f"__p_{idx}"
                param_map[p] = var_name
                eval_dict[var_name] = get_val(p)

        def replace_var(m: re.Match) -> str:
            return param_map[m.group(1).strip()]

        to_eval = re.sub(pattern_param, replace_var, condition)
        return bool(eval(to_eval, {"__builtins__": {}}, eval_dict))

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


def get_include(qry_str: str, all_query: dict, max_depth: int = 10) -> str:
    """
    replace #include name or #include name(key) with query string or snippet.

    ex:
    #include name
    #include name(key)
    """

    pattern = re.compile(
        r"^#include\s+([a-zA-Z0-9_]+)(?:\(\s*([a-zA-Z0-9_]+)\s*\))?$"
    )
    current_qry = qry_str

    for _ in range(max_depth):
        lines = current_qry.splitlines()
        has_include = False
        rets = []

        for line in lines:
            line_strip = line.strip()
            if "#include" in line:
                if not line_strip.startswith("#include"):
                    raise ValueError(f"inline #include is not allowed: '{line}'")

                has_include = True
                m = pattern.match(line_strip)
                if not m:
                    raise ValueError(f"invalid #include syntax: '{line_strip}'")

                name, key = m.group(1), m.group(2)
                if name not in all_query:
                    raise KeyError(f"'{name}' not in all_query")

                target = all_query[name]
                if key is not None:
                    if not isinstance(target, dict):
                        raise ValueError(
                            f"'{name}' does not have sub keys, "
                            f"but parameter '{key}' was passed"
                        )
                    if key not in target:
                        raise KeyError(f"sub key '{key}' not in '{name}'")
                    val = target[key]
                else:
                    if isinstance(target, dict):
                        raise ValueError(
                            f"'{name}' has sub keys, "
                            "but no sub key parameter was passed"
                        )
                    val = target

                for sub_line in str(val).strip("\r\n").splitlines():
                    rets.append(sub_line)
            else:
                rets.append(line)

        current_qry = "\n".join(rets)
        if not has_include:
            break
    else:
        if any(
            line.strip().startswith("#include")
            for line in current_qry.splitlines()
        ):
            raise ValueError("Circular or too deep #include detected")

    return current_qry


def get_template(qry_str: str, params: dict) -> str:
    """
    replace ${param} with value from params.
    supports mybatis-style template substitution.

    ex:
    SELECT id FROM ${table_name}
    ->
    SELECT id FROM t_user
    """

    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        if key in params:
            val = params[key]
            if val is None:
                raise ValueError(f"'{key}' value in params cannot be None")
            return str(val)

        if "." in key:
            parts = key.split(".")
            curr = params
            for p in parts:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                else:
                    break
            else:
                if curr is None:
                    raise ValueError(f"'{key}' value in params cannot be None")
                return str(curr)

        raise KeyError(f"'{key}' not in params")

    replaced = re.sub(r"(?<!\\)\$\{\s*([a-zA-Z0-9_.]+)\s*\}", replacer, qry_str)
    return replaced.replace(r"\${", "${")


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
