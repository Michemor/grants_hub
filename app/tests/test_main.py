# app/tests/test_main.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json() == {"message": "Daystar Grant hub is live"}