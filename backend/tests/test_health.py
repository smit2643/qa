def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data

def test_api_docs_accessible(client):
    response = client.get("/api/docs")
    assert response.status_code == 200

def test_openapi_schema(client):
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Bug0 API"
