"""query_by_key_util"""

import re
from datetime import datetime


def get_conditional(qry_str: str, params: dict) -> str:
    """
    return true or false part by condition.

    ex:
    SELECT  *
    FROM
    #if ${target} == 'en'
            tbl_en
    #else
            tbl_ko
    #endif
    ->
    SELECT  *
    FROM
            tbl_en
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

    rets = []
    lines = qry_str.splitlines()

    is_include = True
    is_checked = False
    foreach_depth = 0
    for line in lines:
        line_strip = line.strip()
        if line_strip.startswith("#foreach"):
            foreach_depth += 1
            if is_include:
                rets.append(line)
            continue
        elif line_strip.startswith(("#endfor", "#endforeach")):
            if foreach_depth > 0:
                foreach_depth -= 1
            if is_include:
                rets.append(line)
            continue

        if foreach_depth > 0:
            if is_include:
                rets.append(line)
            continue

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

    pattern = re.compile(r"^#include\s+([a-zA-Z0-9_]+)(?:\(\s*([a-zA-Z0-9_]+)\s*\))?$")
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
            line.strip().startswith("#include") for line in current_qry.splitlines()
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


def get_foreach(
    qry_str: str,
    params: dict,
    dialect: str = "mysql",
    _loop_counter: list[int] | None = None,
) -> str:
    """
    replace #foreach ... #endfor / #endforeach with expanded query items.
    mimics mybatis <foreach> tag with parameter binding and template substitution.

    supports:
    - Pythonic: #foreach item in ${ids} [open="("] [separator=","] [close=")"]
    - With index: #foreach idx, item in ${ids} [open="("] [separator=","]
    - Bound placeholders: #{item}, #{item.prop}, :item, %(item)s, #{index}
    - Template substitutions: ${item}, ${item.prop}, ${index}
    """
    if "#foreach" not in qry_str:
        return qry_str

    pattern_tag = re.compile(r"#foreach\b((?:(?!#(?:endfor|endforeach)\b)[^\r\n])*)")
    pattern_token = re.compile(r"#foreach\b[^\r\n]*|#(?:endfor|endforeach)\b")
    loop_counter = _loop_counter if _loop_counter is not None else [0]

    def render_item_block(tag_str: str, body: str, loop_id: int) -> str:
        if "\n" in tag_str or "\r" in tag_str:
            raise ValueError(
                f"#foreach directive must be on a single line: '{tag_str}'"
            )
        content = tag_str[len("#foreach") :].strip()
        py_match = re.match(
            r"^(?:([a-zA-Z0-9_]+)\s*,\s*)?([a-zA-Z0-9_]+)\s+in\s+(?:\$\{([a-zA-Z0-9_.]+)\}|([a-zA-Z0-9_.]+))(.*)$",
            content,
        )
        if not py_match:
            raise ValueError(
                f"Invalid #foreach syntax: '{tag_str}'. "
                "Expected '#foreach item in ${collection}' or "
                "'#foreach idx, item in ${collection}'"
            )

        index_var = py_match.group(1)
        item_var = py_match.group(2)
        collection_key = py_match.group(3) or py_match.group(4)
        rest = py_match.group(5)

        attr_matches = re.findall(
            r'([a-zA-Z0-9_]+)\s*=\s*(["\'])(.*?)\2', rest
        )
        attrs = {m[0]: m[2] for m in attr_matches}

        open_str = attrs.get("open", "")
        separator = attrs.get("separator", "")
        close_str = attrs.get("close", "")

        # Resolve collection
        if collection_key in params:
            coll = params[collection_key]
        elif "." in collection_key:
            parts = collection_key.split(".")
            curr = params
            for p in parts:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                elif hasattr(curr, p):
                    curr = getattr(curr, p)
                else:
                    raise KeyError(f"'{collection_key}' not in params")
            coll = curr
        else:
            raise KeyError(f"'{collection_key}' not in params")

        if coll is None:
            raise ValueError(f"'{collection_key}' value in params cannot be None")
        if not coll:
            return ""

        if isinstance(coll, dict):
            items_list = list(coll.items())
        elif isinstance(coll, (list, tuple, set)):
            items_list = list(enumerate(coll))
        else:
            raise TypeError(
                f"'{collection_key}' must be a list, tuple, set, or dict, "
                f"got {type(coll).__name__}"
            )

        # Extract meaningful body lines (trim leading/trailing blank lines)
        all_lines = body.splitlines()
        first = 0
        while first < len(all_lines) and not all_lines[first].strip():
            first += 1
        last = len(all_lines) - 1
        while last >= 0 and not all_lines[last].strip():
            last -= 1

        body_lines = all_lines[first : last + 1] if first <= last else []
        is_single_line = len(body_lines) <= 1
        body_template = "\n".join(body_lines)

        is_comma_sep = separator.strip() == ","
        is_clause_wrapped = (open_str.endswith("(") or open_str.endswith("[")) and (
            close_str.startswith(")") or close_str.startswith("]")
        )

        rendered_items = []

        for idx, (idx_val, val) in enumerate(items_list):
            if is_single_line and (is_clause_wrapped or not is_comma_sep):
                item_text = body_template.strip()
            else:
                item_text = body_template

            iter_params = params.copy()
            if index_var:
                iter_params[index_var] = idx_val
            iter_params[item_var] = val

            # Nested #foreach
            if "#foreach" in item_text:
                item_text = get_foreach(
                    item_text,
                    iter_params,
                    dialect=dialect,
                    _loop_counter=loop_counter,
                )
                for k, v in iter_params.items():
                    if k.startswith("__f_"):
                        params[k] = v

            # Evaluate conditional #if inside #foreach body if present
            if "#if" in item_text:
                item_text = get_conditional(item_text, iter_params)
                if not item_text.strip():
                    continue

            def get_prop(prop: str | None, v):
                if not prop:
                    return v
                curr = v
                for p in prop.split("."):
                    if isinstance(curr, dict) and p in curr:
                        curr = curr[p]
                    elif hasattr(curr, p):
                        curr = getattr(curr, p)
                    else:
                        raise KeyError(f"Property '{p}' not found in {curr}")
                return curr

            # 1. Template literal ${index} and bound placeholders for index
            if index_var:
                item_text = re.sub(
                    rf"\$\{{\s*{re.escape(index_var)}\s*\}}",
                    str(idx_val),
                    item_text,
                )
                p_name = f"__f_{index_var}_{loop_id}_{idx}"
                params[p_name] = idx_val
                target = f":{p_name}" if dialect == "sqlite" else f"%({p_name})s"
                item_text = re.sub(
                    rf"#\{{\s*{re.escape(index_var)}\s*\}}", target, item_text
                )
                item_text = re.sub(rf":{re.escape(index_var)}\b", target, item_text)
                item_text = re.sub(rf"%\({re.escape(index_var)}\)s", target, item_text)

            # 2. Template literal ${item} or ${item.prop}
            pat_tpl = rf"\$\{{\s*{re.escape(item_var)}(?:\.([a-zA-Z0-9_.]+))?\s*\}}"
            item_text = re.sub(
                pat_tpl,
                lambda m, cur_val=val: str(get_prop(m.group(1), cur_val)),
                item_text,
            )

            # 3. Bound parameter placeholders: #{item}, #{item.prop}, :item, %(item)s
            def repl(m: re.Match, cur_idx=idx, cur_val=val) -> str:
                prop = m.group(1)
                prop_suffix = f"_{prop.replace('.', '_')}" if prop else ""
                p_name = f"__f_{item_var}{prop_suffix}_{loop_id}_{cur_idx}"
                params[p_name] = get_prop(prop, cur_val)
                return f":{p_name}" if dialect == "sqlite" else f"%({p_name})s"

            item_text = re.sub(
                rf"#\{{\s*{re.escape(item_var)}(?:\.([a-zA-Z0-9_.]+))?\s*\}}",
                repl,
                item_text,
            )
            if dialect == "sqlite":
                item_text = re.sub(
                    rf":{re.escape(item_var)}(?:\.([a-zA-Z0-9_.]+))?\b",
                    repl,
                    item_text,
                )
            else:
                item_text = re.sub(
                    rf"%\({re.escape(item_var)}(?:\.([a-zA-Z0-9_.]+))?\)s",
                    repl,
                    item_text,
                )

            rendered_items.append(item_text)

        if not rendered_items:
            return ""

        if is_single_line and (is_clause_wrapped or not is_comma_sep):
            sep = separator
        else:
            sep = (
                f"{separator}\n"
                if is_comma_sep and not separator.endswith("\n")
                else separator
            )

        return f"{open_str}{sep.join(rendered_items)}{close_str}"

    def process_blocks(text: str) -> str:
        res = []
        idx = 0
        while True:
            m = pattern_tag.search(text, idx)
            if not m:
                res.append(text[idx:])
                break
            line_start = text.rfind("\n", idx, m.start())
            prefix_start = line_start + 1 if line_start != -1 else idx
            prefix = text[prefix_start : m.start()]
            if prefix.strip() == "":
                res.append(text[idx:prefix_start])
            else:
                res.append(text[idx : m.start()])
            tag = m.group(0)
            pos = m.end()
            depth = 1
            for tok in pattern_token.finditer(text, pos):
                if tok.group(0).startswith("#foreach"):
                    depth += 1
                else:
                    depth -= 1
                    if depth == 0:
                        body = text[pos : tok.start()]
                        rendered = render_item_block(tag, body, loop_counter[0])
                        loop_counter[0] += 1
                        res.append(rendered)
                        idx = tok.end()
                        break
            else:
                raise ValueError(f"Unclosed #foreach starting at: '{tag}'")
        return "".join(res)

    return process_blocks(qry_str)


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
