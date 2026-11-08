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


RESULT = {"sentiment": "negative", "complaints": [{"category": "battery", "evidence_quote": "Battery dies by noon"}], "praised_features": []}


def test_schema_rejects_invalid_categories_and_extra_fields():
    assert ClassificationResult.model_validate(RESULT).complaints[0].category == "battery"
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({**RESULT, "complaints": [{"category": "imaginary", "evidence_quote": "text"}]})
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({**RESULT, "unsupported": True})


def test_evidence_fields_must_quote_review_text(engine):
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        result, _ = classify_review(FakeChain({**RESULT, "complaints": [{"category": "battery", "evidence_quote": "battery exploded"}], "praised_features": [{"category": "display", "evidence_quote": "bright screen"}]}), review)
        assert result.complaints == [] and result.praised_features == []
        review.review_text = "Good"
        with pytest.raises(ValueError, match="generic praise"):
            classify_review(FakeChain({"sentiment": "positive", "complaints": [], "praised_features": [{"category": "design", "evidence_quote": "Good"}]}), review)

def test_general_praise_and_concrete_feature_are_separate(engine):
    with Session(engine) as db:
        review = db.get(Review, "b" * 64)
        review.review_text = "Great display. Impressive watch."
        output = {"sentiment": "positive", "complaints": [], "praised_features": [{"category": "display", "evidence_quote": "Great display"}]}
        assert classify_review(FakeChain(output), review)[0].praised_features[0].category == "display"
        with pytest.raises(ValueError, match="generic praise"):
            classify_review(FakeChain({**output, "praised_features": [{"category": "design", "evidence_quote": "Impressive watch"}]}), review)

def test_feature_category_requires_specific_evidence(engine):
    with Session(engine) as db:
        review = db.get(Review, "b" * 64)
        review.review_text = "The calling function is clear. Fast delivery and great service."
        base = {"sentiment": "positive", "complaints": [], "praised_features": []}
        calling = {**base, "praised_features": [{"category": "calling", "evidence_quote": "calling function"}, {"category": "delivery", "evidence_quote": "Fast delivery"}]}
        assert classify_review(FakeChain(calling), review)[0].praised_features[0].category == "calling"
        with pytest.raises(ValueError, match="software evidence"):
            classify_review(FakeChain({**base, "praised_features": [{"category": "software/app", "evidence_quote": "calling function"}]}), review)
        with pytest.raises(ValueError, match="support evidence"):
            classify_review(FakeChain({**base, "praised_features": [{"category": "customer support", "evidence_quote": "great service"}]}), review)

def test_ungrounded_output_is_marked_unavailable_without_retry(engine):
    with Session(engine) as db:
        review = db.get(Review, "b" * 64)
        output = {"sentiment": "positive", "complaints": [], "praised_features": [{"category": "display", "evidence_quote": "invented screen"}]}
        chain, tracker = FakeChain(output), {}
        result, _ = classify_review(chain, review, usage_tracker=tracker)
        assert result.praised_features == [] and result.sentiment == "positive" and chain.calls == 1
        assert tracker["unavailable_evidence"] == [{"kind": "praised_feature", "category": "display", "evidence_status": "unavailable"}]
        assert tracker["evidence_error_count"] == 1

def test_json_mode_and_schema_retry_are_locally_validated(monkeypatch, engine):
    from backend.app.services import classification

    class StubGroq:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, schema, **kwargs):
            assert schema is ClassificationResult
            assert kwargs == {"method": "json_schema", "strict": True, "include_raw": True}
            return "bound"

    monkeypatch.setattr("langchain_groq.ChatGroq", StubGroq)
    assert classification.make_chain("test-key", "openai/gpt-oss-20b") == "bound"
    with Session(engine) as db:
        review = db.get(Review, "b" * 64)
        valid = {"sentiment": "positive", "complaints": [], "praised_features": [{"category": "display", "evidence_quote": "Great display"}]}
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
        complaint = {"category": "appearance", "evidence_quote": "white strap does not look good"}
        appearance = {"sentiment": "mixed", "complaints": [complaint], "praised_features": []}
        assert classify_review(FakeChain(appearance), review)[0].complaints[0].category == "appearance"
        with pytest.raises(ValueError, match="appearance preference"):
            classify_review(FakeChain({**appearance, "complaints": [{**complaint, "category": "build quality"}]}), review)
        review.review_text = "Good quality"
        broad = {"sentiment": "positive", "complaints": [], "praised_features": [{"category": "build quality", "evidence_quote": "Good quality"}]}
        with pytest.raises(ValueError, match="build quality feature lacks"):
            classify_review(FakeChain(broad), review)

def test_parse_error_reports_missing_fields_without_review_text():
    response = {"raw": SimpleNamespace(content='{"sentiment":"positive"}'),
                "parsed": None, "parsing_error": ValueError("bad")}
    summary = describe_parse_error(response)
    assert "missing fields:" in summary
    assert "complaints" in summary
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
        urdu = {"sentiment": "positive", "complaints": [], "praised_features": []}
        assert classify_review(FakeChain(urdu), review)[0].praised_features == []
        result, _ = classify_review(FakeChain({**urdu, "praised_features": [{"category": "software/app", "evidence_quote": "prayer alarm"}]}), review)
        assert result.praised_features == []
        review.review_text = "I like it, but the battery needs charging twice daily"
        mixed = {"sentiment": "mixed", "complaints": [{"category": "battery", "evidence_quote": "battery needs charging twice daily"}], "praised_features": []}
        assert classify_review(FakeChain(mixed), review)[0].complaints[0].category == "battery"
        review.review_text = "The gold colour started to fade, though I like the watch"
        fading = {**mixed, "complaints": [{"category": "build quality", "evidence_quote": "gold colour started to fade"}]}
        assert classify_review(FakeChain(fading), review)[0].complaints[0].category == "build quality"

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


def test_unavailable_evidence_is_persisted_but_excluded_from_analytics(engine):
    from backend.app.services.intelligence import distribution
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        output = {**RESULT, "complaints": [{"category": "battery", "evidence_quote": "invented failure"}], "praised_features": [{"category": "display", "evidence_quote": "invented screen"}]}
        chain = FakeChain(output)
        assert process_reviews(db, chain, "test-model", [review])["analyzed"] == 1
        record = db.scalar(select(ReviewClassification))
        assert chain.calls == 1 and record.sentiment == "negative" and record.evidence_error_count == 2
        assert record.complaint_categories == [] and record.praised_features == []
        assert record.unavailable_evidence == [{"kind": "complaint", "category": "battery", "evidence_status": "unavailable"}, {"kind": "praised_feature", "category": "display", "evidence_status": "unavailable"}]
        assert distribution(db, "test-model", "complaint_categories")["counts"] == {}
        assert distribution(db, "test-model", "praised_features")["counts"] == {}
        assert "invented" not in str(record.unavailable_evidence)

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


def test_intelligence_queries_do_not_mix_products(engine):
    with Session(engine) as db:
        process_reviews(db, FakeChain(RESULT), "openai/gpt-oss-20b", [db.get(Review, "a" * 64)])
        db.add(Product(id="test-product", name="Test fixture"))
        db.add(Review(id="c" * 64, product_id="test-product", source_id="3", review_text="Fixture", title=None,
                      rating=3, review_date=None, raw_date="", source_url="https://example.test", content_fingerprint="h" * 64))
        db.commit()

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app)
        root = "/api/products/test-product/intelligence"
        assert client.get(root + "/progress").json()["total_reviews"] == 1
        assert client.get(root + "/progress").json()["analyzed"] == 0
        assert client.get(root + "/sentiment").json()["counts"] == {}
        assert client.get(root + "/classifications").json()["total"] == 0
    finally:
        app.dependency_overrides.clear()


def test_review_filters_evidence_and_analytics_use_current_results(engine):
    with Session(engine) as db:
        first = db.get(Review, "a" * 64)
        second = db.get(Review, "b" * 64)
        process_reviews(db, FakeChain(RESULT), "openai/gpt-oss-20b", [first])
        positive = {"sentiment": "positive", "complaints": [], "praised_features": [{"category": "display", "evidence_quote": "Great display"}]}
        process_reviews(db, FakeChain(positive), "openai/gpt-oss-20b", [second])

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app)
        root = "/api/products/luna-smartwatch"
        assert client.get(root + "/reviews?search=display").json()["total"] == 1
        filtered = client.get(root + "/reviews?sentiment=negative&complaint=battery").json()
        assert filtered["total"] == 1
        assert filtered["items"][0]["classification"]["negative_experiences"] == ["Battery dies by noon"]
        assert client.get(root + "/reviews?rating=5").json()["total"] == 1
        assert client.get(root + "/reviews?sort=rating&order=asc&page_size=1&page=2").json()["items"][0]["rating"] == 5
        assert client.get(root + "/reviews?complaint=invalid").status_code == 422
        matrix = client.get(root + "/intelligence/sentiment-by-rating").json()
        assert matrix["analyzed_reviews"] == 2
        assert matrix["ratings"][1]["negative"] == 1
        assert matrix["ratings"][4]["positive"] == 1
        categories = client.get(root + "/intelligence/complaint-breakdown").json()
        assert categories["categories"] == [{"category": "battery", "count": 1, "severity": {"unknown": 1}}]
    finally:
        app.dependency_overrides.clear()


def test_review_filters_exclude_stale_and_failed_classifications(engine):
    with Session(engine) as db:
        review = db.get(Review, "a" * 64)
        process_reviews(db, FakeChain(RESULT), "openai/gpt-oss-20b", [review])
        review.content_fingerprint = "z" * 64
        db.commit()
        failed = db.get(Review, "b" * 64)
        process_reviews(db, FakeChain(ValueError("malformed")), "openai/gpt-oss-20b", [failed])

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app)
        root = "/api/products/luna-smartwatch"
        assert client.get(root + "/reviews?sentiment=negative").json()["total"] == 0
        assert client.get(root + "/reviews?complaint=battery").json()["total"] == 0
        page = client.get(root + "/reviews").json()
        statuses = {item["source_id"]: item["analysis_status"] for item in page["items"]}
        assert statuses == {"1": "pending", "2": "failed"}
        assert all(item["classification"] is None for item in page["items"])
    finally:
        app.dependency_overrides.clear()


def test_strict_case_sensitive_evidence_and_stop_on_first_rate_limit(engine):
    import httpx
    from groq import RateLimitError

    with Session(engine) as db:
        review = db.get(Review, 'a' * 64)
        review.review_text = 'Battery drains quickly'
        inaccurate_quote = {**RESULT, "complaints": [{"category": "battery", "evidence_quote": "battery drains quickly"}]}
        tracker = {}
        result, _ = classify_review(FakeChain(inaccurate_quote), review, retries=1, usage_tracker=tracker)
        assert result.complaints == [] and tracker['unavailable_evidence'][0]['evidence_status'] == 'unavailable'
        request = httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')
        response = httpx.Response(429, headers={'retry-after': '7'}, request=request)
        chain = FakeChain(RateLimitError('minute limit', response=response, body={}))
        waits = []
        result = process_reviews(db, chain, 'test-model', [review], sleep=waits.append, stop_on_rate_limit=True)
        assert result['rate_limited'] == 1
        assert chain.calls == 1
        assert waits == []
        record = db.scalar(select(ReviewClassification))
        assert record.attempt_count == 1
        assert record.rate_limit_info['retry_after_seconds'] == 7


def test_json_generation_failure_gets_one_recovery_and_preserves_checkpoint(engine):
    request = httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')
    response = httpx.Response(400, request=request)
    error = BadRequestError('Failed to generate JSON. Please adjust your prompt.', response=response,
                            body={'code': 'json_validate_failed', 'failed_generation': 'private synthetic output'})
    with Session(engine) as db:
        review = db.get(Review, 'a' * 64)
        failing = FakeChain(error)
        assert process_reviews(db, failing, 'test-model', [review])['failed'] == 1
        record = db.scalar(select(ReviewClassification))
        original_id = record.id
        assert failing.calls == 2
        assert record.attempt_count == 2 and record.schema_error_count == 2
        assert record.validation_error == 'Groq JSON generation or validation failed'
        assert 'private synthetic output' not in record.error
        recovering = FakeChain([error, RESULT])
        assert process_reviews(db, recovering, 'test-model', [review])['analyzed'] == 1
        assert recovering.calls == 2
        assert db.scalar(select(ReviewClassification)).id == original_id
        assert process_reviews(db, recovering, 'test-model', [review])['cached'] == 1
        assert recovering.calls == 2
        assert len(db.scalars(select(ReviewClassification)).all()) == 1


def test_unrelated_bad_request_is_not_retried(engine):
    response = httpx.Response(400, request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions'))
    error = BadRequestError('Invalid model configuration', response=response, body={'code': 'invalid_request_error'})
    with Session(engine) as db:
        review = db.get(Review, 'a' * 64)
        chain = FakeChain(error)
        assert process_reviews(db, chain, 'test-model', [review])['failed'] == 1
        assert chain.calls == 1
        assert db.scalar(select(ReviewClassification)).schema_error_count == 0


def test_invalid_and_incomplete_response_fail_without_saving_success(engine):
    class InvalidResponseChain:
        def __init__(self, content):
            self.content = content
            self.calls = 0
        def invoke(self, messages):
            self.calls += 1
            return {'raw': SimpleNamespace(content=self.content, usage_metadata={}), 'parsed': None,
                    'parsing_error': ValueError('parse failed')}

    with Session(engine) as db:
        review = db.get(Review, 'a' * 64)
        for content, expected in [('{bad json', 'invalid JSON'), ('', 'invalid JSON'),
                                  ('{"sentiment":"positive"}', 'missing fields:')]:
            chain = InvalidResponseChain(content)
            assert process_reviews(db, chain, 'test-model', [review])['failed'] == 1
            record = db.scalar(select(ReviewClassification))
            assert chain.calls == 3 and record.status == 'failed'
            assert expected in record.validation_error
            assert db.query(ReviewClassification).count() == 1
        assert process_reviews(db, FakeChain(RESULT), 'test-model', [review])['analyzed'] == 1
        assert db.query(ReviewClassification).count() == 1


def test_interrupted_before_request_leaves_review_pending(engine):
    class InterruptedPacer:
        def before_request(self):
            raise KeyboardInterrupt()
    with Session(engine) as db:
        review = db.get(Review, 'a' * 64)
        with pytest.raises(KeyboardInterrupt):
            process_reviews(db, FakeChain(RESULT), 'test-model', [review], pacer=InterruptedPacer())
        assert db.scalar(select(ReviewClassification)) is None


def test_strict_schema_request_and_version_isolation(engine):
    from backend.app.services.classification import CLASSIFICATION_VERSION, make_chain
    assert CLASSIFICATION_VERSION == '8'
    chain = make_chain('test-only-key', 'openai/gpt-oss-20b')
    response_format = chain.first.steps__['raw'].kwargs['response_format']
    assert response_format['type'] == 'json_schema'
    assert response_format['json_schema']['strict'] is True
    schema = response_format['json_schema']['schema']
    assert set(schema['required']) == {'sentiment', 'complaints', 'praised_features'}
    assert schema['additionalProperties'] is False
    for field in ('complaints', 'praised_features'):
        assert schema['properties'][field]['items']['additionalProperties'] is False
    with Session(engine) as db:
        review = db.get(Review, 'a' * 64)
        legacy = ReviewClassification(review_id=review.id, model_name='openai/gpt-oss-20b', version='7',
                                      content_fingerprint=review.content_fingerprint, status='completed', sentiment='positive')
        db.add(legacy); db.commit()
        assert process_reviews(db, FakeChain(RESULT), 'openai/gpt-oss-20b', [review])['analyzed'] == 1
        rows = db.scalars(select(ReviewClassification).order_by(ReviewClassification.version)).all()
        assert [row.version for row in rows] == ['7', '8']
        assert rows[0].sentiment == 'positive'
        assert rows[1].complaint_evidence == RESULT['complaints']
        assert rows[1].issue_severity is None


def test_version8_progress_excludes_version7_and_respects_its_cooldown(engine):
    from backend.app.services.intelligence import progress
    with Session(engine) as db:
        review = db.get(Review, 'a' * 64)
        old = ReviewClassification(review_id=review.id, model_name='test-model', version='7',
                                   content_fingerprint=review.content_fingerprint, status='failed',
                                   error_type='RateLimitError', rate_limit_info={'retry_at': '2099-01-01T00:00:00+00:00'})
        db.add(old); db.commit()
        state = progress(db, 'test-model')
        assert state['version'] == '8' and state['analyzed'] == 0 and state['pending'] == 2
        assert state['cooldown_until'] == '2099-01-01T00:00:00+00:00'
        chain = FakeChain(RESULT)
        assert process_reviews(db, chain, 'test-model', [review])['cooldown_active'] == 1
        assert chain.calls == 0


def test_supported_and_unavailable_evidence_can_coexist(engine):
    with Session(engine) as db:
        review = db.get(Review, 'a' * 64)
        output = {**RESULT, 'complaints': [RESULT['complaints'][0], {'category': 'connectivity', 'evidence_quote': 'disconnects'}]}
        assert process_reviews(db, FakeChain(output), 'test-model', [review])['analyzed'] == 1
        record = db.scalar(select(ReviewClassification))
        assert record.complaint_categories == ['battery']
        assert record.complaint_evidence == [RESULT['complaints'][0]]
        assert record.unavailable_evidence == [{'kind': 'complaint', 'category': 'connectivity', 'evidence_status': 'unavailable'}]
