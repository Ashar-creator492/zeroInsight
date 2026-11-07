import csv

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.ingest import CSVValidationError, import_reviews, load_reviews
from backend.app.main import app
from backend.app.models import Review

COLUMNS = ["id", "product", "review_text", "title", "rating", "date", "source_url"]


def sample_row(**changes):
    row = {"id": "1", "product": "Luna Smartwatch", "review_text": "Battery lasts all day", "title": "", "rating": "5", "date": "10/31/2026", "source_url": "https://example.test/luna"}
    row.update(changes)
    return row


def write_csv(path, rows, columns=COLUMNS):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_csv_validation_and_quality_report(tmp_path):
    path = tmp_path / "reviews.csv"
    write_csv(path, [sample_row(), sample_row(id="2", review_text="Battery lasts all day", date="unknown")])
    rows, report = load_reviews(path)
    assert report["records"] == 2
    assert report["missing_values"]["title"] == 2
    assert report["repeated_review_texts"] == 1
    assert report["invalid_dates"] == 1
    assert rows[0]["title"] is None
    assert rows[1]["review_date"] is None


def test_missing_column_or_value_is_rejected(tmp_path):
    path = tmp_path / "reviews.csv"
    write_csv(path, [sample_row()], columns=COLUMNS[:-1])
    with pytest.raises(CSVValidationError):
        load_reviews(path)
    write_csv(path, [sample_row(review_text="")])
    with pytest.raises(CSVValidationError, match="missing required value"):
        load_reviews(path)


@pytest.mark.parametrize("rating", ["0", "6", "4.5", "nope"])
def test_invalid_rating_is_rejected(tmp_path, rating):
    path = tmp_path / "reviews.csv"
    write_csv(path, [sample_row(rating=rating)])
    with pytest.raises(CSVValidationError, match="Invalid rating"):
        load_reviews(path)


def test_duplicate_source_ids_are_rejected(tmp_path):
    path = tmp_path / "reviews.csv"
    write_csv(path, [sample_row(), sample_row()])
    with pytest.raises(CSVValidationError, match="duplicate source ID"):
        load_reviews(path)


def test_idempotent_import_update_and_api(tmp_path, engine):
    path = tmp_path / "reviews.csv"
    write_csv(path, [sample_row(), sample_row(id="2", review_text="Good display", rating="3")])
    rows, _ = load_reviews(path)
    with Session(engine) as session:
        assert import_reviews(session, rows) == {"inserted": 2, "updated": 0, "unchanged": 0}
        assert import_reviews(session, rows) == {"inserted": 0, "updated": 0, "unchanged": 2}
        assert session.scalar(select(Review).where(Review.source_id == "1")).review_text == "Battery lasts all day"
    write_csv(path, [sample_row(review_text="Battery improved"), sample_row(id="2", review_text="Good display", rating="3")])
    changed, _ = load_reviews(path)
    with Session(engine) as session:
        assert import_reviews(session, changed) == {"inserted": 0, "updated": 1, "unchanged": 1}

    def test_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app)
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/products").json() == [{"id": "luna-smartwatch", "name": "Luna Smartwatch"}]
        response = client.get("/api/products/luna-smartwatch/reviews?page_size=1&page=2")
        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert len(response.json()["items"]) == 1
        summary = client.get("/api/products/luna-smartwatch/summary").json()
        assert summary == {"product_id": "luna-smartwatch", "total_reviews": 2, "average_rating": 4.0, "rating_distribution": {"1": 0, "2": 0, "3": 1, "4": 0, "5": 1}}
        assert client.get("/api/products/unknown/summary").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_monthly_trend_counts_dated_and_undated_reviews(tmp_path, engine):
    path = tmp_path / "reviews.csv"
    write_csv(path, [sample_row(), sample_row(id="2", date="10/01/2026"),
                     sample_row(id="3", date="11/01/2026"), sample_row(id="4", date="unknown")])
    rows, _ = load_reviews(path)
    with Session(engine) as session:
        import_reviews(session, rows)

    def test_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        response = TestClient(app).get("/api/products/luna-smartwatch/review-trend")
        assert response.status_code == 200
        assert response.json() == {"product_id": "luna-smartwatch", "points": [
            {"month": "2026-10", "count": 2}, {"month": "2026-11", "count": 1}], "undated_reviews": 1}
        assert TestClient(app).get("/api/products/unknown/review-trend").status_code == 404
    finally:
        app.dependency_overrides.clear()
