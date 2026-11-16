from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from backend.app.database import Base
from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import Product, Review, ReviewClassification
from backend.app.routers import brief


def test_brief_counts_distinct_verified_evidence_and_excludes_failed(monkeypatch):
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(brief, 'get_settings', lambda: SimpleNamespace(groq_model='model'))
    with Session(engine) as db:
        db.add(Product(id='luna-smartwatch', name='Luna'))
        for i in range(3):
            db.add(Review(id=str(i) * 64, product_id='luna-smartwatch', source_id=str(i), review_text='Battery dies early; after charging it lasted... Read more', title='Good screen', rating=2, raw_date='', source_url='https://example.test', content_fingerprint=str(i) * 64))
        db.flush()
        db.add_all([
            ReviewClassification(review_id='0' * 64, model_name='model', version='8', content_fingerprint='0' * 64, status='completed', complaint_evidence=[{'category': 'battery', 'evidence_quote': 'Battery dies early'}, {'category': 'battery', 'evidence_quote': 'Battery dies early'}, {'category': 'display', 'evidence_quote': 'invented'}, {'category': 'charging', 'evidence_quote': 'after charging it lasted...'}], praised_features=[{'category': 'display', 'evidence_quote': 'Good screen'}]),
            ReviewClassification(review_id='1' * 64, model_name='model', version='8', content_fingerprint='1' * 64, status='failed'),
            ReviewClassification(review_id='2' * 64, model_name='model', version='9', content_fingerprint='2' * 64, status='completed', complaint_evidence=[{'category': 'battery', 'evidence_quote': 'Battery dies early'}]),
        ])
        db.commit()
        result = brief.improvement_brief('luna-smartwatch', db)
        assert (result['version'], result['total_reviews'], result['analyzed_reviews'], result['excluded_reviews']) == ('8', 3, 1, 2)
        assert [(row['category'], row['count']) for row in result['complaints']] == [('battery', 1)]
        assert result['complaints'][0]['percentage'] == 100
        assert result['recommendations'][0]['priority'] == 'low'
        assert result['praised_features'][0]['evidence'][0]['quote'] == 'Good screen'
    def override_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get('/api/products/luna-smartwatch/improvement-brief')
        assert response.status_code == 200 and response.json()['analyzed_reviews'] == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
