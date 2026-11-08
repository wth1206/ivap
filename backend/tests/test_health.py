"""P1/P2 contract tests: health, root, error envelope, request id, OpenAPI."""


def test_health_returns_ok(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "testing"
    assert payload["components"]["database"]["status"] == "ok"
    assert payload["components"]["database"]["dialect"] == "sqlite"
    assert payload["components"]["detector"]["status"] == "ok"
    assert payload["components"]["detector"]["model"] == "ECE-YOLO"
    assert payload["components"]["detector"]["loaded"] is False
    assert payload["components"]["llm"]["configured"] is False
    assert payload["components"]["vector_store"]["status"] == "ok"
    assert payload["components"]["vector_store"]["documents"] == 0
    assert payload["components"]["vector_store"]["vectors"] == 0
    assert payload["components"]["vector_store"]["embedding_model"] == "mock-embedding"
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Process-Time-Ms"]) >= 0.0


def test_health_alias_for_container_probe(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_returns_docs_and_health_links(client):
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["docs"] == "/docs"
    assert payload["health"] == "/api/v1/health"


def test_unknown_route_uses_unified_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]


def test_request_id_is_echoed(client):
    request_id = "test-request-001"
    response = client.get("/api/v1/health", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_openapi_is_available(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    assert "/api/v1/health" in payload["paths"]
    assert "/api/v1/detection/upload" in payload["paths"]
    assert "/api/v1/detection/predict" in payload["paths"]
    assert "/api/v1/detection/models" in payload["paths"]
    assert "/api/v1/analysis/{task_id}" in payload["paths"]
    assert "/api/v1/knowledge/upload" in payload["paths"]
    assert "/api/v1/knowledge/search" in payload["paths"]
    assert payload["info"]["version"] == "0.1.0"
