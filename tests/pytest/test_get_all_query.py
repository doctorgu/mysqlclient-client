"""test get_all_query"""

from pathlib import Path

import pytest

from mysqlclient_client.client import Client
from tests.db_settings import db_settings


def test_get_all_query_from_settings():
    """test get_all_query loaded during Client init"""
    client = Client(db_settings)
    assert "read_user_id_all" in client.all_query
    assert "create_tables" in client.all_query
    assert "_filter_by_key" in client.all_query
    assert isinstance(client.all_query["_filter_by_key"], dict)


def test_get_all_query_explicit_dir():
    """test get_all_query with explicit directory"""
    client = Client(db_settings)
    queries_dir = Path(__file__).parent.parent / "queries"
    queries = client.get_all_query(queries_dir)
    assert "read_user_id_all" in queries


def test_get_all_query_not_found(tmp_path):
    """test get_all_query raises FileNotFoundError on missing dir"""
    client = Client(db_settings)
    missing_dir = tmp_path / "non_existent"
    with pytest.raises(FileNotFoundError):
        client.get_all_query(missing_dir)


def test_get_all_query_duplicate_key(tmp_path):
    """test get_all_query raises ValueError on duplicate query keys across files"""
    client = Client(db_settings)
    q1 = tmp_path / "q1.yml"
    q2 = tmp_path / "q2.yml"
    q1.write_text("- name: dup_key\n  value: SELECT 1\n", encoding="utf-8")
    q2.write_text("- name: dup_key\n  value: SELECT 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicated keys"):
        client.get_all_query(tmp_path)
