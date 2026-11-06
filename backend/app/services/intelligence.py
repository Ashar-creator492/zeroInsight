from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import Review, ReviewClassification
from backend.app.services.classification import CLASSIFICATION_VERSION


def current_query(model_name: str):
    return (
        select(ReviewClassification)
        .join(Review, Review.id == ReviewClassification.review_id)
        .where(Review.product_id == "luna-smartwatch", ReviewClassification.model_name == model_name,
               ReviewClassification.version == CLASSIFICATION_VERSION,
               ReviewClassification.content_fingerprint == Review.content_fingerprint)
    )


def progress(db: Session, model_name: str) -> dict:
    total = db.scalar(select(func.count()).select_from(Review).where(Review.product_id == "luna-smartwatch")) or 0
    rows = db.scalars(current_query(model_name)).all()
    done = sum(row.status == "completed" for row in rows)
    failed = sum(row.status == "failed" for row in rows)
    return {"product_id": "luna-smartwatch", "model_name": model_name, "version": CLASSIFICATION_VERSION,
            "total_reviews": total, "analyzed": done, "failed": failed, "pending": total - done - failed,
            "input_tokens": sum(row.input_tokens or 0 for row in rows if row.status == "completed"),
            "output_tokens": sum(row.output_tokens or 0 for row in rows if row.status == "completed")}


def distribution(db: Session, model_name: str, field: str) -> dict:
    rows = db.scalars(current_query(model_name).where(ReviewClassification.status == "completed")).all()
    counts = Counter()
    for row in rows:
        value = getattr(row, field)
        counts.update(value if isinstance(value, list) else [value])
    return {"product_id": "luna-smartwatch", "analyzed_reviews": len(rows), "counts": dict(sorted(counts.items()))}
