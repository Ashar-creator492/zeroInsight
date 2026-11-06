"""Run a capped Luna review pilot or a later approved full batch."""

import argparse
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import make_engine
from backend.app.models import Review, ReviewClassification
from backend.app.services.classification import CLASSIFICATION_VERSION, LUNA_ID, make_chain, process_reviews


def pilot_reviews(reviews: list[Review]) -> list[Review]:
    """Pick a stable spread of ratings and review lengths; preserve source records."""
    chosen = []
    quotas = [(1, 2), (2, 2), (3, 2), (4, 2), (5, 2)]
    for rating, count in quotas:
        subset = sorted((r for r in reviews if r.rating == rating), key=lambda r: (-len(r.review_text), r.id))
        chosen.extend(subset[:count])
    remaining = sorted((r for r in reviews if r not in chosen), key=lambda r: (len(r.review_text), r.id))
    chosen.extend(remaining[:max(0, 10 - len(chosen))])
    return chosen[:10]


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify Luna reviews with Groq")
    parser.add_argument("--all", action="store_true", help="Process all Luna reviews after explicit pilot approval")
    parser.add_argument("--limit", type=int, default=25, help="Maximum reviews in an approved full-batch run")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.groq_api_key:
        parser.error("GROQ_API_KEY is missing. Add it to your private .env file; never paste it into chat.")
    if args.limit < 1:
        parser.error("--limit must be positive")
    with Session(make_engine()) as db:
        reviews = db.scalars(select(Review).where(Review.product_id == LUNA_ID).order_by(Review.id)).all()
        if args.all:
            existing = {row.review_id: row for row in db.scalars(select(ReviewClassification).where(
                ReviewClassification.model_name == settings.groq_model,
                ReviewClassification.version == CLASSIFICATION_VERSION,
            )).all()}
            selected = [review for review in reviews if review.id not in existing or
                        existing[review.id].status != "completed" or
                        existing[review.id].content_fingerprint != review.content_fingerprint][:args.limit]
        else:
            selected = pilot_reviews(reviews)
        chain = make_chain(settings.groq_api_key, settings.groq_model)
        counts = process_reviews(db, chain, settings.groq_model, selected)
        print(json.dumps(counts))
        if not args.all:
            for review in selected:
                row = db.scalar(select(ReviewClassification).where(
                    ReviewClassification.review_id == review.id,
                    ReviewClassification.model_name == settings.groq_model,
                    ReviewClassification.version == CLASSIFICATION_VERSION,
                ))
                print(json.dumps({"source_id": review.source_id, "rating": review.rating,
                                  "review_text": review.review_text, "status": row.status,
                                  "sentiment": row.sentiment, "complaint_categories": row.complaint_categories,
                                  "praised_features": row.praised_features, "negative_experiences": row.negative_experiences,
                                  "input_tokens": row.input_tokens, "output_tokens": row.output_tokens}, ensure_ascii=False))


if __name__ == "__main__":
    main()
