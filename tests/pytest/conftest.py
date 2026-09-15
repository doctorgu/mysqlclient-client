"""call pytest_configure"""


def pytest_configure():
    """
    pytest provides special function called `pytest_configure`
    called when pytest initialized for configuring custom settings
    """
    # os.environ["APP_ENV"] = "test"
