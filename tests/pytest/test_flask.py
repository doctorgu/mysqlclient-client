"""test Flask"""

from tests.flask.app import app
from tests.pytest.test_fn_common import patch_mysqlclient


def test_flask(mocker):
    """test flask"""

    patch_mysqlclient(mocker)

    routes = [
        "/",
        "/create-tables",
        "/upsert-user",
        "/upsert-user-params-out",
        "/upsert-user-list",
        "/upsert-delete-user-with",
        "/read-user-one-row",
        "/read-user-all-rows",
        "/read-using-conditional1",
        "/read-using-conditional2",
        "/read-using-include1",
        "/read-using-include2",
        "/read-using-include3",
        "/read-using-en-ko1",
        "/read-using-en-ko2",
        "/use-db-client",
    ]

    app.config["TESTING"] = True
    with app.test_client() as client:
        for route in routes:
            response = client.get(route)
            assert response.status_code == 200
            print("succeeded:", route)
