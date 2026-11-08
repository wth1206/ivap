"""Pytest fixtures: isolated SQLite database and temp upload directory."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="ivap-test-"))
os.environ["APP_ENV"] = "testing"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["MODEL_PRELOAD"] = "false"
# Never call a real LLM/embedding endpoint from the test suite.
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""
os.environ["LLM_MOCK"] = "true"
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["EMBEDDING_MODEL"] = "mock-embedding"
os.environ["EMBEDDING_DIM"] = "128"
os.environ["EMBEDDING_BATCH_SIZE"] = "8"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(_TEST_ROOT / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_TEST_ROOT / "uploads")
os.environ["VECTOR_DB_DIR"] = str(_TEST_ROOT / "vector_db")
os.environ["LOG_DIR"] = str(_TEST_ROOT / "logs")

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_engine, reset_engine_cache  # noqa: E402
from app.main import create_app  # noqa: E402
from app.rag.vector_store import reset_vector_store  # noqa: E402


@pytest.fixture()
def client():
    """Fresh schema, uploads and FAISS index for every test."""
    get_settings.cache_clear()
    reset_engine_cache()
    settings = get_settings()
    if settings.vector_db_dir.exists():
        shutil.rmtree(settings.vector_db_dir, ignore_errors=True)
    settings.vector_db_dir.mkdir(parents=True, exist_ok=True)
    reset_vector_store()

    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())

    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
