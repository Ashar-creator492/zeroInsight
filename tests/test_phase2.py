from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Product, Review, ReviewClassification
from backend.app.services.classification import ClassificationResult, classify_review, process_reviews


@pytest.fixture
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Product(id="luna-smartwatch", name="Luna Smartwatch"))
        db.add_all([
            Review(id="a" * 64, product_id="luna-smartwatch", source_id="1", review_text="Battery dies by noon", title=None,
                   rating=2, review_date=None, raw_date="", source_url="https://example.test/1", content_fingerprint="f" * 64),
            Review(id="b" * 64, product_id="luna-smartwatch", source_id="2", review_text="Great display", title=None,
                   rating=5, review_date=None, raw_date="", source_url="https://example.test/2", content_fingerprint="g" * 64),
        ])
        db.commit()
    yield engine
    engine.dispose()


class FakeChain:
    def __init__(self, output):
        self.output = output
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if isinstance(self.output, Exception):
            raise self.output
        return {"parsed": self.output, "parsing_error": None,
                "raw": SimpleNamespace(usage_metadata={"input_tokens": 100, "output_tokens": 40})}


RESULT = {"sentiment": "negative", "complaint_categories": ["battery"], "praised_features": [],
          "negative_experiences": ["Battery dies by noon"], "product_attributes": ["battery"],
          "issue_severity": "medium", "investigation_areas": ["Check battery runtime reports"]}


def test_schema_rejects_invalid_categories_and_extra_fields():
    assert ClassificationResult.model_validate(RESULT).complaint_categories == ["battery"]
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({**RESULT, "complaint_categories": ["imaginary"]})
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({**RESULT, "unsupported": True})


def test_classification_persistence_cache_failure_and_retry(engine):
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        chain = FakeChain(RESULT)
        assert process_reviews(db, chain, "test-model", [review]) == {"analyzed": 1, "failed": 0, "cached": 0}
        assert process_reviews(db, chain, "test-model", [review]) == {"analyzed": 0, "failed": 0, "cached": 1}
        assert chain.calls == 1
        record = db.scalar(select(ReviewClassification))
        assert record.review_id == review.id
        assert record.input_tokens == 100
        review.content_fingerprint = "z" * 64
        db.commit()
        assert process_reviews(db, FakeChain({**RESULT, "sentiment": "wrong"}), "test-model", [review])["failed"] == 1
        assert process_reviews(db, FakeChain(RESULT), "test-model", [review])["analyzed"] == 1
        assert db.query(ReviewClassification).count() == 1


def test_malformed_response_and_exception_are_not_persisted_as_success(engine):
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        with pytest.raises(ValueError, match="malformed"):
            classify_review(FakeChain(None), review)
        assert process_reviews(db, FakeChain(ValueError("bad output")), "test-model", [review])["failed"] == 1
        assert db.scalar(select(ReviewClassification)).status == "failed"


def test_intelligence_endpoints_use_only_stored_results(engine):
    with Session(engine) as db:
        process_reviews(db, FakeChain(RESULT), "openai/gpt-oss-20b", [db.get(Review, "a" * 64)])

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app)
        root = "/api/products/luna-smartwatch/intelligence"
        assert client.get(root + "/progress").json()["pending"] == 1
        assert client.get(root + "/progress").json()["analyzed"] == 1
        assert client.get(root + "/sentiment").json()["counts"] == {"negative": 1}
        assert client.get(root + "/complaints").json()["counts"] == {"battery": 1}
        assert client.get(root + "/praised-features").json()["counts"] == {}
        page = client.get(root + "/classifications?page_size=1").json()
        assert page["total"] == 1 and page["items"][0]["review_id"] == "a" * 64
        assert client.get("/api/products/unknown/intelligence/progress").status_code == 404
    finally:
        app.dependency_overrides.clear()
