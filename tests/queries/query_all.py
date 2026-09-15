"""query collection"""

from pathlib import Path

import yaml

dir_current = Path(__file__).parent
all_query: dict[str, str] = {}

for yml_path in sorted(
    p for p in dir_current.iterdir() if p.suffix in (".yml", ".yaml")
):
    with open(yml_path, encoding="utf-8") as f:
        items = yaml.safe_load(f) or []

    qry_cur: dict[str, str] = {}
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and "name" in item and "value" in item:
                val = item["value"].strip()
                qry_cur[item["name"]] = f"\n{val}\n"
    elif isinstance(items, dict):
        for k, v in items.items():
            val = str(v).strip()
            qry_cur[k] = f"\n{val}\n"

    dup = all_query.keys() & qry_cur.keys()
    if dup:
        raise ValueError(
            f"duplicated keys: {dup} in {all_query.keys()} and {qry_cur.keys()}"
        )

    all_query |= qry_cur
