from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import Review
from backend.app.schemas import ProductSummary, ReviewsPage


def get_review_page(db: Session, product_id: str, page: int, page_size: int) -> ReviewsPage:
    total = db.scalar(select(func.count()).select_from(Review).where(Review.product_id == product_id)) or 0
    items = db.scalars(
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.review_date.desc(), Review.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ReviewsPage(items=items, total=total, page=page, page_size=page_size)


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
