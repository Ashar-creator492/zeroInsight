# Expose filtered semantic review retrieval.
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.security import limit_ai_requests
from backend.app.services.retrieval import retrieve_reviews

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"], dependencies=[Depends(limit_ai_requests)])


@router.get("/reviews")
def search_reviews(q: str = Query(min_length=1, max_length=500),
                   product_id: str = Query(default="luna-smartwatch", min_length=1, max_length=100),
                   rating: int | None = Query(default=None, ge=1, le=5),
                   limit: int = Query(default=5, ge=1, le=20),
                   db: Session = Depends(get_db)):
    return {"reviews": retrieve_reviews(db, q, product_id, rating, limit)}
