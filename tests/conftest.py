import nest_asyncio
import pytest

# Apply nested asyncio patch to allow re-entrant event loops
# This is critical on Windows when plugins like Playwright and Pytest-Asyncio fight for control
nest_asyncio.apply()


def pytest_configure(config):
    """Ensure nest_asyncio is applied during configuration."""
    nest_asyncio.apply()


@pytest.fixture(scope="session", autouse=True)
def setup_nest_asyncio():
    """Ensure nest_asyncio is applied at the fixture level as well."""
    nest_asyncio.apply()
    yield
