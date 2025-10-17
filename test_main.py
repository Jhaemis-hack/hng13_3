from .main import app
from fastapi.testclient import TestClient
# from core.error_handlers import register_error_handlers

client = TestClient(app)
# register_error_handlers(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Ok"
    }
