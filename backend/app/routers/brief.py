"""Build a review-backed improvement brief without a model call."""
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models import Review, ReviewClassification
from backend.app.routers.products import require_product
from backend.app.services.classification import CLASSIFICATION_VERSION
from backend.app.services.intelligence import current_query

router = APIRouter(prefix='/api/products/{product_id}', tags=['brief'])


@router.get('/improvement-brief')
def improvement_brief(product_id: str, db: Session = Depends(get_db)):
    require_product(db, product_id)
    total = db.scalar(select(func.count()).select_from(Review).where(Review.product_id == product_id)) or 0
    rows = db.scalars(current_query(get_settings().groq_model, product_id).where(ReviewClassification.status == 'completed')).all()
    complaints, praise = defaultdict(dict), defaultdict(dict)
    for row in rows:
        review = row.review
        for items, groups in ((row.complaint_evidence or [], complaints), (row.praised_features or [], praise)):
            for item in items:
                category, quote = item.get('category'), item.get('evidence_quote')
                if not isinstance(category, str) or not isinstance(quote, str) or not quote.strip():
                    continue
                if quote not in review.review_text and quote not in (review.title or ''):
                    continue
                groups[category][review.id] = {'review_id': review.source_id, 'quote': quote, 'source_url': review.source_url}

    def summarize(groups):
        result = []
        for category, reviews in groups.items():
            count = len(reviews)
            result.append({'category': category, 'count': count, 'percentage': round(100 * count / len(rows), 1) if rows else 0,
                           'evidence': list(reviews.values())[:5]})
        return sorted(result, key=lambda item: (-item['count'], item['category']))

    complaint_groups, praise_groups = summarize(complaints), summarize(praise)
    recommendations = []
    for item in complaint_groups:
        count = item['count']
        priority = 'high' if count >= 10 else 'medium' if count >= 3 else 'low'
        recommendations.append({**item, 'priority': priority,
                                'action': f"Investigate customer-reported {item['category']} experiences and verify the underlying causes.",
                                'rationale': f'{count} classified reviews contain an exact supporting quote; frequency guides review order, not severity.',
                                'uncertainty': 'AI interpretations and quote matches require human review; severity and causes are not established.'})
    return {'product_id': product_id, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'version': CLASSIFICATION_VERSION, 'total_reviews': total, 'analyzed_reviews': len(rows),
            'excluded_reviews': total - len(rows), 'complaints': complaint_groups, 'praised_features': praise_groups,
            'recommendations': recommendations,
            'methodology': 'Counts use distinct completed classifications with exact quotes. Percentages use all completed classifications. Priority is review frequency: high 10+, medium 3–9, low 1–2; severity is unknown.',
            'limitations': 'Reviews are customer reports, not verified defects. Exact quotes do not guarantee semantic accuracy. Failed and pending classifications are excluded. This independent project is not endorsed by the brand.'}
