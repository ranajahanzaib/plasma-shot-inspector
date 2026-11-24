import pytest
from fastapi.testclient import TestClient

from plasma_inspector.api import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_health(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "plasma-shot-inspector-api"}


def test_api_datasets(client: TestClient) -> None:
    resp = client.get("/api/v1/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    ids = {d["id"] for d in data}
    assert "fair-mast-l1" in ids
    assert "fair-mast-l2" in ids


def test_api_machines(client: TestClient) -> None:
    resp = client.get("/api/v1/machines")
    assert resp.status_code == 200
    data = resp.json()
    assert any(m["id"] == "mast" for m in data)


def test_api_rules(client: TestClient) -> None:
    resp = client.get("/api/v1/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 30
    rule_ids = {r["id"] for r in data}
    assert "TIME-STRUCTURE-001" in rule_ids
    assert "SIGNAL-FINITE-001" in rule_ids
    assert "EQ-GRID-001" in rule_ids


def test_api_audits_list(client: TestClient) -> None:
    resp = client.get("/api/v1/audits?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_api_audit_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/audits/non-existent-uuid")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["code"] == "audit_not_found"
