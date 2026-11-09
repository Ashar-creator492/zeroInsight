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


def test_broad_evidence_uses_only_current_verified_classifications():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.app.database import Base
    from backend.app.models import Product, Review, ReviewClassification
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Product(id='luna-smartwatch', name='Luna'))
        for index in range(1, 5):
            db.add(Review(id=str(index), product_id='luna-smartwatch', source_id=str(index),
                          review_text='The display is clear', title=None, rating=5, review_date=None,
                          raw_date='', source_url='https://example.test', content_fingerprint='same'))
        db.flush()
        for index, version, status, quote in [(1, '8', 'completed', 'display is clear'),
                                              (2, '7', 'completed', 'display is clear'),
                                              (3, '8', 'failed', 'display is clear'),
                                              (4, '8', 'completed', 'invented')]:
            db.add(ReviewClassification(review_id=str(index), model_name='test-model', version=version,
                                        content_fingerprint='same', status=status,
                                        praised_features=[{'category': 'display', 'evidence_quote': quote}]))
        db.commit()
        assert chat.broad_kind('What do customers like most about Luna?') == 'praised_features'
        assert chat.broad_kind('What do customers like about battery life?') is None
        assert chat.broad_kind('What are the most common complaints about Luna?') == 'complaint_evidence'
        selected = chat.broad_review_evidence(db, 'test-model', 'luna-smartwatch', None, 'praised_features')
        assert [row['source_id'] for row in selected] == ['1']
        assert selected[0]['verified_quote'] == 'display is clear'
        assert chat.broad_review_evidence(db, 'test-model', 'luna-smartwatch', 1, 'praised_features') == []
    engine.dispose()


def test_broad_chat_uses_classified_evidence_with_existing_citation_checks(monkeypatch):
    calls = []
    class FakeChat:
        def __init__(self, **kwargs): pass
        def with_structured_output(self, *args, **kwargs): return self
        def invoke(self, messages):
            calls.append(messages)
            return chat.GroundedAnswer(claims=[chat.Claim(text='One customer praises battery life.', review_ids=['7'], evidence_quote='battery lasts all day')])
    monkeypatch.setattr(chat, 'broad_review_evidence', lambda *args: [{**REVIEW, 'verified_category': 'battery', 'verified_quote': 'battery lasts all day'}])
    monkeypatch.setattr(chat, 'retrieve_reviews', lambda *args: (_ for _ in ()).throw(AssertionError('unnecessary search')))
    monkeypatch.setattr(chat, 'get_settings', lambda: SimpleNamespace(groq_api_key='test-key', groq_model='test-model'))
    monkeypatch.setattr(chat, 'ChatGroq', FakeChat)
    app.dependency_overrides[get_db] = lambda: None
    try:
        response = TestClient(app).post('/api/chat', json={'question': 'What do customers like most about Luna?'})
        assert response.status_code == 200 and response.json()['claims'][0]['review_ids'] == ['7']
        assert 'limited current-version classified sample' in calls[0][1].content
    finally:
        app.dependency_overrides.clear()
