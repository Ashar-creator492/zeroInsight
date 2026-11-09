# Query paginated reviews, rating statistics, and monthly review counts.
import json
from sqlalchemy import Text, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from backend.app.models import Review, ReviewClassification
from backend.app.schemas import ProductSummary, ReviewAnalysis, ReviewOut, ReviewsPage, ReviewTrend, ReviewTrendPoint
from backend.app.services.classification import CLASSIFICATION_VERSION


# Filter the complete dataset server-side and attach only matching current-version analyses.
def get_review_page(db: Session, product_id: str, page: int, page_size: int, model_name: str,
                    search: str | None = None, rating: int | None = None, sentiment: str | None = None,
                    complaint: str | None = None, sort: str = "date", order: str = "desc") -> ReviewsPage:
    query = select(Review, ReviewClassification).outerjoin(ReviewClassification, and_(
        ReviewClassification.review_id == Review.id, ReviewClassification.model_name == model_name,
        ReviewClassification.version == CLASSIFICATION_VERSION,
        ReviewClassification.content_fingerprint == Review.content_fingerprint,
    )).where(Review.product_id == product_id)
    if search and search.strip():
        term = search.strip()
        query = query.where(or_(Review.review_text.icontains(term, autoescape=True),
                                Review.title.icontains(term, autoescape=True),
                                Review.source_id.icontains(term, autoescape=True)))
    if rating is not None:
        query = query.where(Review.rating == rating)
    if sentiment:
        query = query.where(ReviewClassification.status == "completed", ReviewClassification.sentiment == sentiment)
    if complaint:
        # Compare a quoted JSON string so categories match as complete array entries.
        query = query.where(ReviewClassification.status == "completed",
                            cast(ReviewClassification.complaint_categories, Text).contains(json.dumps(complaint), autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    field = Review.review_date if sort == "date" else Review.rating
    ordering = field.asc() if order == "asc" else field.desc()
    rows = db.execute(query.order_by(ordering.nulls_last(), Review.id).offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for review, classification in rows:
        status = classification.status if classification and classification.status in {"completed", "failed"} else "pending"
        analysis = ReviewAnalysis.model_validate(classification) if status == "completed" else None
        items.append(ReviewOut.model_validate(review).model_copy(update={"analysis_status": status, "classification": analysis}))
    return ReviewsPage(items=items, total=total, page=page, page_size=page_size)


# Calculate rating counts and the average directly from stored reviews.
def get_summary(db: Session, product_id: str) -> ProductSummary:
    rows = db.execute(
        select(Review.rating, func.count(Review.id))
        .where(Review.product_id == product_id)
        .group_by(Review.rating)
    ).all()
    distribution = {rating: 0 for rating in range(1, 6)}
    distribution.update({rating: count for rating, count in rows})
    total = sum(distribution.values())
    average = sum(rating * count for rating, count in distribution.items()) / total if total else None
    return ProductSummary(product_id=product_id, total_reviews=total, average_rating=average, rating_distribution=distribution)


# Group dated reviews by month and report undated reviews separately.
def get_review_trend(db: Session, product_id: str) -> ReviewTrend:
    year = func.extract("year", Review.review_date)
    month = func.extract("month", Review.review_date)
    rows = db.execute(select(year, month, func.count(Review.id)).where(
        Review.product_id == product_id, Review.review_date.is_not(None)
    ).group_by(year, month).order_by(year, month)).all()
    undated = db.scalar(select(func.count()).select_from(Review).where(
        Review.product_id == product_id, Review.review_date.is_(None)
    )) or 0
    return ReviewTrend(product_id=product_id, points=[
        ReviewTrendPoint(month=f"{int(y):04d}-{int(m):02d}", count=count) for y, m, count in rows
    ], undated_reviews=undated)
