# content of conftest.py
import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--variables", action="store", nargs="+", help="*.variable files to preload into test cases"
    )
    parser.addoption(
        "--organization_id", action="store", help="Organization ID to preload into test cases"
    )

    


@pytest.fixture(scope="class")
def bot_variables(request):
    request.cls.bot_variables = request.config.getoption("--variables")

@pytest.fixture(scope="class")
def organization_id(request):
    organization_id = request.config.getoption("--organization_id")
    request.cls.organization_id = int(organization_id) if organization_id is not None else None
        