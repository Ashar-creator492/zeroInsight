from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app
from backend.app.routers import chat


REVIEW = {"id": "internal", "source_id": "7", "product_id": "luna-smartwatch", "review_text": "The battery lasts all day.", "title": None, "rating": 5, "review_date": None, "source_url": "https://example.test/reviews", "similarity": 0.7}


def test_chat_requires_relevant_evidence_and_valid_citations(monkeypatch):
    calls = []
    class FakeChat:
        def __init__(self, **kwargs): pass
        def with_structured_output(self, *args, **kwargs): return self
        def invoke(self, messages):
            calls.append(messages)
            return chat.GroundedAnswer(claims=[chat.Claim(text="A customer said the battery lasts all day.", review_ids=["7"], evidence_quote="battery lasts all day")])
    monkeypatch.setattr(chat, "retrieve_reviews", lambda *args: [REVIEW])
    monkeypatch.setattr(chat, "get_settings", lambda: SimpleNamespace(groq_api_key="test-key", groq_model="test-model"))
    monkeypatch.setattr(chat, "ChatGroq", FakeChat)
    app.dependency_overrides[get_db] = lambda: None
    try:
        client = TestClient(app)
        result = client.post('/api/chat', json={'question': 'battery life'}).json()
        assert result['claims'][0]['review_ids'] == ['7'] and result['sources'][0]['source_id'] == '7'
        assert len(calls) == 1
        monkeypatch.setattr(FakeChat, 'invoke', lambda self, messages: chat.GroundedAnswer(claims=[chat.Claim(text='Invented.', review_ids=['99'], evidence_quote='invented')]))
        assert client.post('/api/chat', json={'question': 'battery life'}).json()['claims'] == []
        monkeypatch.setattr(FakeChat, 'invoke', lambda self, messages: chat.GroundedAnswer(claims=[chat.Claim(text='Wrong quote.', review_ids=['7'], evidence_quote='not in the review')]))
        assert client.post('/api/chat', json={'question': 'battery life'}).json()['claims'] == []
        monkeypatch.setattr(chat, 'retrieve_reviews', lambda *args: [{**REVIEW, 'similarity': 0.1}])
        assert 'insufficient' in client.post('/api/chat', json={'question': 'battery life'}).json()['message']
        assert 'Urdu-script' in client.post('/api/chat', json={'question': 'بیٹری'}).json()['message']
        assert len(calls) == 1
    finally:
        app.dependency_overrides.clear()


def test_chat_reports_model_error_without_leaking_details(monkeypatch):
    class BrokenChat:
        def __init__(self, **kwargs): raise RuntimeError('private detail')
    monkeypatch.setattr(chat, 'retrieve_reviews', lambda *args: [REVIEW])
    monkeypatch.setattr(chat, 'get_settings', lambda: SimpleNamespace(groq_api_key='test-key', groq_model='test-model'))
    monkeypatch.setattr(chat, 'ChatGroq', BrokenChat)
    app.dependency_overrides[get_db] = lambda: None
    try:
        response = TestClient(app).post('/api/chat', json={'question': 'battery'})
        assert response.status_code == 503 and 'private detail' not in response.text
    finally:
        app.dependency_overrides.clear()
