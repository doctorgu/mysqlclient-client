"""client_util"""

import json
from datetime import date, datetime
from typing import Literal

from .query_util import (
    get_conditional,
    get_include,
    replace_en_ko_column_alias,
)
from .settings import Settings


class Query:
    """query"""

    def __init__(self, qry_settings: Settings):
        self.qry_settings = qry_settings

    def get_query_by_key(
        self,
        qry_key: str,
        params: dict,
        func_type: Literal["update", "read", "csv"],
        en: bool = False,
    ) -> str:
        """get query string by qry_key"""

        def serial_date(obj):
            """JSON serializer for objects not serializable by default json code"""

            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return str(obj)

        query = self.qry_settings.all_query.get(qry_key)
        if not query or not isinstance(query, str):
            raise KeyError(f"{qry_key} not exists")

        cond_params = (
            params[0]
            if isinstance(params, (list, tuple))
            and params
            and isinstance(params[0], dict)
            else (params if isinstance(params, dict) else {})
        )
        info_params = (
            f"[executemany: {len(params)} rows]"
            if isinstance(params, (list, tuple)) and len(params) > 1
            else params
        )

        info = {
            "qry_key": qry_key,
            "params": info_params,
            "func_type": func_type,
            "en": en,
        }

        if "#include" in query:
            query = get_include(query, self.qry_settings.all_query)
        if self.qry_settings.use_en_ko_column_alias and isinstance(en, bool):
            query = replace_en_ko_column_alias(query, en)
        if self.qry_settings.use_conditional and "#if" in query:
            query = get_conditional(query, cond_params)

        info_str = json.dumps(info, ensure_ascii=False, default=serial_date)
        return f"/* {info_str.replace('%', '{percent}')} */{query}"
