from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import Review, ReviewClassification
from backend.app.services.classification import CLASSIFICATION_VERSION


def current_query(model_name: str, product_id: str = "luna-smartwatch"):
    return (
        select(ReviewClassification)
        .join(Review, Review.id == ReviewClassification.review_id)
        .where(Review.product_id == product_id, ReviewClassification.model_name == model_name,
               ReviewClassification.version == CLASSIFICATION_VERSION,
               ReviewClassification.content_fingerprint == Review.content_fingerprint)
    )


def progress(db: Session, model_name: str, product_id: str = "luna-smartwatch") -> dict:
    total = db.scalar(select(func.count()).select_from(Review).where(Review.product_id == product_id)) or 0
    rows = db.scalars(current_query(model_name, product_id)).all()
    done = sum(row.status == "completed" for row in rows)
    failed = sum(row.status == "failed" for row in rows)
    failed_by_type = Counter(row.error_type or "Unknown" for row in rows if row.status == "failed")
    rate_limits = db.scalars(select(ReviewClassification).where(
        ReviewClassification.model_name == model_name, ReviewClassification.status == "failed",
        ReviewClassification.error_type == "RateLimitError"
    )).all()
    cooldowns = [row.rate_limit_info.get("retry_at") for row in rate_limits
                 if row.rate_limit_info and row.rate_limit_info.get("retry_at")]
    future_cooldowns = [value for value in cooldowns if datetime.fromisoformat(value) > datetime.now(timezone.utc)]
    return {"product_id": product_id, "model_name": model_name, "version": CLASSIFICATION_VERSION,
            "total_reviews": total, "analyzed": done, "failed": failed, "pending": total - done - failed,
            "failed_by_type": dict(failed_by_type), "cooldown_until": max(future_cooldowns, default=None),
            "input_tokens": sum(row.input_tokens or 0 for row in rows),
            "output_tokens": sum(row.output_tokens or 0 for row in rows),
            "attempts": sum(row.attempt_count or 0 for row in rows),
            "schema_errors": sum(row.schema_error_count or 0 for row in rows),
            "evidence_errors": sum(row.evidence_error_count or 0 for row in rows)}


def distribution(db: Session, model_name: str, field: str, product_id: str = "luna-smartwatch") -> dict:
    rows = db.scalars(current_query(model_name, product_id).where(ReviewClassification.status == "completed")).all()
    counts = Counter()
    for row in rows:
        value = getattr(row, field)
        if field == "praised_features":
            counts.update(item["category"] for item in value or [])
        else:
            counts.update(value if isinstance(value, list) else [value])
    return {"product_id": product_id, "analyzed_reviews": len(rows), "counts": dict(sorted(counts.items()))}


def sentiment_by_rating(db: Session, model_name: str, product_id: str) -> dict:
    query = current_query(model_name, product_id).with_only_columns(
        Review.rating, ReviewClassification.sentiment, func.count(ReviewClassification.id)
    ).where(ReviewClassification.status == "completed").group_by(Review.rating, ReviewClassification.sentiment)
    rows = db.execute(query).all()
    values = {rating: {name: 0 for name in ("positive", "negative", "neutral", "mixed")} for rating in range(1, 6)}
    for rating, sentiment, count in rows:
        if sentiment in values[rating]:
            values[rating][sentiment] = count
    return {"product_id": product_id, "analyzed_reviews": sum(sum(counts.values()) for counts in values.values()),
            "ratings": [{"rating": rating, **counts} for rating, counts in values.items()]}


def complaint_breakdown(db: Session, model_name: str, product_id: str) -> dict:
    rows = db.scalars(current_query(model_name, product_id).where(ReviewClassification.status == "completed")).all()
    categories: dict[str, Counter] = {}
    for row in rows:
        for category in set(row.complaint_categories or []):
            counts = categories.setdefault(category, Counter())
            counts["count"] += 1
            counts[row.issue_severity or "unknown"] += 1
    return {"product_id": product_id, "analyzed_reviews": len(rows), "categories": [
        {"category": category, "count": counts["count"], "severity": {key: value for key, value in counts.items() if key != "count"}}
        for category, counts in sorted(categories.items(), key=lambda item: (-item[1]["count"], item[0]))
    ]}
