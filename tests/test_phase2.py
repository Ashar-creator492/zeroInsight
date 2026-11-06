from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from groq import BadRequestError, RateLimitError
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Product, Review, ReviewClassification
from backend.app.services.classification import (
    ClassificationResult, RequestPacer, classify_review, describe_parse_error,
    process_reviews, rate_limit_details,
)


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
        output = self.output[min(self.calls - 1, len(self.output) - 1)] if isinstance(self.output, list) else self.output
        if isinstance(output, Exception):
            raise output
        return {"parsed": output, "parsing_error": None,
                "raw": SimpleNamespace(usage_metadata={"input_tokens": 100, "output_tokens": 40})}


RESULT = {"sentiment": "negative", "complaint_categories": ["battery"], "praised_features": [],
          "general_praise": [],
          "negative_experiences": ["Battery dies by noon"], "product_attributes": ["battery"],
          "issue_severity": "medium", "investigation_areas": ["Check battery runtime reports"]}


def test_schema_rejects_invalid_categories_and_extra_fields():
    assert ClassificationResult.model_validate(RESULT).complaint_categories == ["battery"]
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({**RESULT, "complaint_categories": ["imaginary"]})
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({**RESULT, "unsupported": True})


def test_evidence_fields_must_quote_review_text(engine):
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        for field, phrase in (("negative_experiences", "battery exploded"),
                              ("product_attributes", "Bluetooth")):
            with pytest.raises(ValueError, match="absent from the review"):
                classify_review(FakeChain({**RESULT, field: [phrase]}), review)
        with pytest.raises(ValueError, match="absent from the review"):
            classify_review(FakeChain({**RESULT, "praised_features": [
                {"category": "display", "evidence_quote": "bright screen"}]}), review)
        review.review_text = "Good"
        generic = {**RESULT, "complaint_categories": [], "negative_experiences": [],
                   "product_attributes": [], "praised_features": [
                       {"category": "design", "evidence_quote": "Good"}]}
        with pytest.raises(ValueError, match="generic praise"):
            classify_review(FakeChain(generic), review)


def test_general_praise_and_concrete_feature_are_separate(engine):
    with Session(engine) as db:
        review = db.get(Review, "b" * 64)
        review.review_text = "Great display. Impressive watch."
        output = {**RESULT, "sentiment": "positive", "complaint_categories": [],
                  "negative_experiences": [], "product_attributes": ["display"],
                  "praised_features": [{"category": "display", "evidence_quote": "Great display"}],
                  "general_praise": ["Impressive watch"]}
        result, _ = classify_review(FakeChain(output), review)
        assert result.praised_features[0].category == "display"
        assert result.general_praise == ["Impressive watch"]
        with pytest.raises(ValueError, match="generic praise"):
            classify_review(FakeChain({**output, "praised_features": [
                {"category": "design", "evidence_quote": "Impressive watch"}]}), review)
        with pytest.raises(ValueError, match="duplicates"):
            classify_review(FakeChain({**output, "general_praise": ["Great display"]}), review)


def test_feature_category_requires_specific_evidence(engine):
    with Session(engine) as db:
        review = db.get(Review, "b" * 64)
        review.review_text = "The calling function is clear. Fast delivery and great service."
        base = {**RESULT, "sentiment": "positive", "complaint_categories": [],
                "negative_experiences": [], "product_attributes": [],
                "general_praise": ["great service"], "issue_severity": "none"}
        calling = {**base, "praised_features": [{"category": "calling", "evidence_quote": "calling function"},
                                               {"category": "delivery", "evidence_quote": "Fast delivery"}]}
        assert classify_review(FakeChain(calling), review)[0].praised_features[0].category == "calling"
        with pytest.raises(ValueError, match="software evidence"):
            classify_review(FakeChain({**base, "praised_features": [
                {"category": "software/app", "evidence_quote": "calling function"}]}), review)
        with pytest.raises(ValueError, match="support evidence"):
            classify_review(FakeChain({**base, "praised_features": [
                {"category": "customer support", "evidence_quote": "great service"}], "general_praise": []}), review)


def test_ungrounded_output_is_retried_without_persisting_it(engine):
    with Session(engine) as db:
        review = db.get(Review, "b" * 64)
        valid = {**RESULT, "sentiment": "positive", "complaint_categories": [],
                 "negative_experiences": [], "product_attributes": ["display"],
                 "praised_features": [{"category": "display", "evidence_quote": "Great display"}],
                 "issue_severity": "none"}
        chain = FakeChain([{**valid, "praised_features": [
            {"category": "display", "evidence_quote": "invented screen"}]}, valid])
        tracker = {}
        assert classify_review(chain, review, usage_tracker=tracker)[0].praised_features[0].evidence_quote == "Great display"
        assert chain.calls == 2
        assert {key: tracker[key] for key in ("attempt_count", "schema_error_count", "evidence_error_count",
                                               "input_tokens", "output_tokens")} == {
            "attempt_count": 2, "schema_error_count": 0, "evidence_error_count": 1,
            "input_tokens": 200, "output_tokens": 80}
        assert tracker["validation_error"] == "praised_features contains a quote absent from the review"


def test_json_mode_and_schema_retry_are_locally_validated(monkeypatch, engine):
    from backend.app.services import classification

    class StubGroq:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, schema, **kwargs):
            assert schema is ClassificationResult
            assert kwargs == {"method": "json_mode", "include_raw": True}
            return "bound"

    monkeypatch.setattr("langchain_groq.ChatGroq", StubGroq)
    assert classification.make_chain("test-key", "test-model") == "bound"
    with Session(engine) as db:
        review = db.get(Review, "b" * 64)
        valid = {**RESULT, "sentiment": "positive", "complaint_categories": [],
                 "negative_experiences": [], "product_attributes": ["display"],
                 "praised_features": [{"category": "display", "evidence_quote": "Great display"}],
                 "issue_severity": "none"}
        response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
        schema_error = BadRequestError("Generated JSON does not match the expected schema", response=response, body={})
        chain = FakeChain([schema_error, valid])
        tracker = {}
        assert classify_review(chain, review, usage_tracker=tracker)[0].sentiment == "positive"
        assert tracker["attempt_count"] == 2
        assert tracker["schema_error_count"] == 1
        malformed = FakeChain([{"sentiment": "positive"}, valid])
        tracker = {}
        assert classify_review(malformed, review, usage_tracker=tracker)[0].sentiment == "positive"
        assert tracker["schema_error_count"] == 1


def test_appearance_vs_build_and_generic_quality(engine):
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        review.review_text = "The white strap does not look good, but the watch is nice"
        appearance = {**RESULT, "sentiment": "mixed", "complaint_categories": ["appearance"],
                      "negative_experiences": ["white strap does not look good"], "product_attributes": ["white strap"],
                      "general_praise": ["the watch is nice"], "issue_severity": "low"}
        assert classify_review(FakeChain(appearance), review)[0].complaint_categories == ["appearance"]
        with pytest.raises(ValueError, match="appearance preference"):
            classify_review(FakeChain({**appearance, "complaint_categories": ["build quality"]}), review)
        review.review_text = "Good quality"
        broad_quality = {**RESULT, "sentiment": "positive", "complaint_categories": [],
                         "negative_experiences": [], "product_attributes": [], "general_praise": ["Good quality"],
                         "praised_features": [{"category": "build quality", "evidence_quote": "Good quality"}],
                         "issue_severity": "none"}
        with pytest.raises(ValueError, match="build quality feature lacks"):
            classify_review(FakeChain({**broad_quality, "general_praise": []}), review)
        assert classify_review(FakeChain({**broad_quality, "praised_features": []}), review)[0].praised_features == []


def test_parse_error_reports_missing_fields_without_review_text():
    response = {"raw": SimpleNamespace(content='{"sentiment":"positive"}'),
                "parsed": None, "parsing_error": ValueError("bad")}
    summary = describe_parse_error(response)
    assert "missing fields:" in summary
    assert "complaint_categories" in summary
    assert "positive" not in summary


def test_pacer_spaces_retries_by_tokens_without_live_calls():
    now = [0.0]
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    pacer = RequestPacer(clock=lambda: now[0], sleep=sleep)
    pacer.before_request()
    pacer.record_usage(4500, 500)
    pacer.before_request()
    assert waits == [60.0]
    assert now[0] == 60.0


def test_retry_after_and_daily_limit_are_recorded_without_repeated_requests(engine):
    now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    minute_response = httpx.Response(429, headers={"retry-after": "7", "x-ratelimit-remaining-requests": "25",
                                                "x-ratelimit-remaining-tokens": "0"}, request=request)
    minute_error = RateLimitError("token limit", response=minute_response, body={})
    info = rate_limit_details(minute_error, now=now)
    assert info["kind"] == "tokens_per_minute"
    assert info["retry_after_seconds"] == 7
    assert info["retry_at"] == "2026-11-06T12:00:07+00:00"
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        waits = []
        tracker = {}
        chain = FakeChain([minute_error, RESULT])
        assert classify_review(chain, review, sleep=waits.append, usage_tracker=tracker)[0].sentiment == "negative"
        assert waits == [7]
        assert tracker["attempt_count"] == 2
        daily_response = httpx.Response(429, headers={"retry-after": "3600", "x-ratelimit-remaining-requests": "0"}, request=request)
        daily_error = RateLimitError("daily limit", response=daily_response, body={})
        chain = FakeChain(daily_error)
        assert process_reviews(db, chain, "test-model", [review])["rate_limited"] == 1
        record = db.scalar(select(ReviewClassification))
        assert chain.calls == 1
        assert record.rate_limit_info["kind"] == "requests_per_day"
        assert record.attempt_count == 1
        assert record.error_type == "RateLimitError"
        assert process_reviews(db, chain, "test-model", [review])["cooldown_active"] == 1
        assert chain.calls == 1


def test_synthetic_urdu_quote_and_indirect_complaints(engine):
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        review.review_text = "بہت اچھی گھڑی ہے"
        urdu = {**RESULT, "sentiment": "positive", "complaint_categories": [],
                "negative_experiences": [], "product_attributes": [], "praised_features": [],
                "general_praise": ["بہت اچھی گھڑی ہے"], "issue_severity": "none"}
        assert classify_review(FakeChain(urdu), review)[0].praised_features == []
        with pytest.raises(ValueError, match="absent from the review"):
            classify_review(FakeChain({**urdu, "praised_features": [
                {"category": "software/app", "evidence_quote": "prayer alarm"}]}), review)
        review.review_text = "I like it, but the battery needs charging twice daily"
        mixed = {**RESULT, "sentiment": "mixed", "complaint_categories": ["battery"],
                 "negative_experiences": ["battery needs charging twice daily"],
                 "product_attributes": ["battery"], "general_praise": ["I like it"],
                 "issue_severity": "medium"}
        assert classify_review(FakeChain(mixed), review)[0].complaint_categories == ["battery"]
        review.review_text = "The gold colour started to fade, though I like the watch"
        fading = {**RESULT, "sentiment": "mixed", "complaint_categories": ["build quality"],
                  "negative_experiences": ["gold colour started to fade"], "product_attributes": ["gold colour"],
                  "general_praise": ["I like the watch"], "issue_severity": "low"}
        assert classify_review(FakeChain(fading), review)[0].complaint_categories == ["build quality"]


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
        assert record.attempt_count == 1
        assert record.schema_error_count == 0
        review.content_fingerprint = "z" * 64
        db.commit()
        assert process_reviews(db, FakeChain({**RESULT, "sentiment": "wrong"}), "test-model", [review])["failed"] == 1
        assert record.error_type == "ValidationError"
        assert record.attempt_count == 3
        assert record.schema_error_count == 3
        assert process_reviews(db, FakeChain(RESULT), "test-model", [review])["analyzed"] == 1
        assert db.query(ReviewClassification).count() == 1


def test_retry_usage_and_error_counts_are_persisted(engine):
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        chain = FakeChain([{**RESULT, "negative_experiences": ["invented failure"]}, RESULT])
        assert process_reviews(db, chain, "test-model", [review])["analyzed"] == 1
        record = db.scalar(select(ReviewClassification))
        assert record.attempt_count == 2
        assert record.evidence_error_count == 1
        assert record.input_tokens == 200
        assert record.output_tokens == 80


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
