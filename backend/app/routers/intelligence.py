from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models import ReviewClassification
from backend.app.routers.products import require_product
from backend.app.services.intelligence import current_query, distribution, progress

router = APIRouter(prefix="/api/products/{product_id}/intelligence", tags=["intelligence"])


def check_luna(db: Session, product_id: str):
    require_product(db, product_id)


@router.get("/progress")
def analysis_progress(product_id: str, db: Session = Depends(get_db)):
    check_luna(db, product_id)
    return progress(db, get_settings().groq_model)


@router.get("/sentiment")
def sentiments(product_id: str, db: Session = Depends(get_db)):
    check_luna(db, product_id)
    return distribution(db, get_settings().groq_model, "sentiment")


@router.get("/complaints")
def complaints(product_id: str, db: Session = Depends(get_db)):
    check_luna(db, product_id)
    return distribution(db, get_settings().groq_model, "complaint_categories")


@router.get("/praised-features")
def praised_features(product_id: str, db: Session = Depends(get_db)):
    check_luna(db, product_id)
    return distribution(db, get_settings().groq_model, "praised_features")


@router.get("/classifications")
def classifications(product_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    db: Session = Depends(get_db)):
    check_luna(db, product_id)
    query = current_query(get_settings().groq_model)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(ReviewClassification.review_id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"review_id": row.review_id, "status": row.status, "sentiment": row.sentiment if row.status == "completed" else None,
                       "complaint_categories": row.complaint_categories if row.status == "completed" else None,
                       "praised_features": row.praised_features if row.status == "completed" else None,
                       "general_praise": row.general_praise if row.status == "completed" else None,
                       "negative_experiences": row.negative_experiences if row.status == "completed" else None,
                       "product_attributes": row.product_attributes if row.status == "completed" else None,
                       "issue_severity": row.issue_severity if row.status == "completed" else None,
                       "investigation_areas": row.investigation_areas if row.status == "completed" else None,
                       "model_name": row.model_name, "version": row.version, "analyzed_at": row.analyzed_at,
                       "input_tokens": row.input_tokens, "output_tokens": row.output_tokens,
                       "attempt_count": row.attempt_count, "schema_error_count": row.schema_error_count,
                       "evidence_error_count": row.evidence_error_count, "error_type": row.error_type,
                       "validation_error": row.validation_error, "rate_limit_info": row.rate_limit_info} for row in rows],
            "total": total, "page": page, "page_size": page_size}
