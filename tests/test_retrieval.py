from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app


def test_retrieval_endpoint_forwards_filters(monkeypatch):
    calls = []
    def retrieve(db, question, product_id, rating, limit):
        calls.append((question, product_id, rating, limit))
        return [{"source_id": "1", "review_text": "The display is clear"}]
    monkeypatch.setattr("backend.app.routers.retrieval.retrieve_reviews", retrieve)
    app.dependency_overrides[get_db] = lambda: None
    try:
        client = TestClient(app)
        response = client.get("/api/retrieval/reviews", params={"q": "display", "product_id": "luna-smartwatch", "rating": 5, "limit": 3})
        assert response.status_code == 200
        assert response.json()["reviews"][0]["source_id"] == "1"
        assert calls == [("display", "luna-smartwatch", 5, 3)]
        assert client.get("/api/retrieval/reviews", params={"q": "x", "rating": 6}).status_code == 422
    finally:
        app.dependency_overrides.clear()
