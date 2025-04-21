import logging
import os
from pathlib import Path

import pytest

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@pytest.fixture(scope="session")
def results_dir():
    """Create and return path to results directory."""
    dir_path = Path(__file__).parent / "results"
    dir_path.mkdir(exist_ok=True)
    return dir_path


@pytest.fixture(scope="session")
def api_host():
    """Get API host from environment or use default."""
    return os.environ.get("API_HOST", "http://localhost:8000")
