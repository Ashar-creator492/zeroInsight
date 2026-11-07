from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.classification import Complaint, Sentiment
from backend.app.models import Product
from backend.app.schemas import ProductOut, ProductSummary, ReviewsPage, ReviewTrend
from backend.app.services.reviews import get_review_page, get_review_trend, get_summary

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def products(db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.name)).all()


def require_product(db: Session, product_id: str) -> None:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")


@router.get("/{product_id}/reviews", response_model=ReviewsPage)
def reviews(
    product_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    rating: int | None = Query(default=None, ge=1, le=5),
    sentiment: Sentiment | None = None,
    complaint: Complaint | None = None,
    sort: Literal["date", "rating"] = "date",
    order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
):
    require_product(db, product_id)
    return get_review_page(db, product_id, page, page_size, get_settings().groq_model,
                           search, rating, sentiment, complaint, sort, order)


@router.get("/{product_id}/summary", response_model=ProductSummary)
def summary(product_id: str, db: Session = Depends(get_db)):
    require_product(db, product_id)
    return get_summary(db, product_id)


@router.get("/{product_id}/review-trend", response_model=ReviewTrend)
def review_trend(product_id: str, db: Session = Depends(get_db)):
    require_product(db, product_id)
    return get_review_trend(db, product_id)
