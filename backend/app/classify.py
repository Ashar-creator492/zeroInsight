"""Run a capped Luna review pilot or a later approved full batch."""

import argparse
import fcntl
import json
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import make_engine
from backend.app.models import Review, ReviewClassification
from backend.app.services.classification import CLASSIFICATION_VERSION, LUNA_ID, RequestPacer, make_chain, process_reviews


@contextmanager
def exclusive_processing():
    """Prevent two local classifier commands from bypassing one-process pacing."""
    path = Path("data/raw/.classify.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another Luna classification process is running") from exc
        try:
            yield
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


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
    parser.add_argument("--source-ids", nargs="+", help="Classify only these real Luna source IDs for validation")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.groq_api_key:
        parser.error("GROQ_API_KEY is missing. Add it to your private .env file; never paste it into chat.")
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.all and args.source_ids:
        parser.error("--all and --source-ids cannot be combined")
    if args.source_ids and len(args.source_ids) > 30:
        parser.error("Validation samples are capped at 30 reviews")
    with exclusive_processing(), Session(make_engine()) as db:
        reviews = db.scalars(select(Review).where(Review.product_id == LUNA_ID).order_by(Review.id)).all()
        if args.source_ids:
            by_source = {review.source_id: review for review in reviews}
            missing = set(args.source_ids) - by_source.keys()
            if missing:
                parser.error(f"Unknown Luna source IDs: {', '.join(sorted(missing))}")
            selected = [by_source[source_id] for source_id in dict.fromkeys(args.source_ids)]
        elif args.all:
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
        counts = process_reviews(db, chain, settings.groq_model, selected,
                                 daily_token_cap=160_000,
                                 pacer=RequestPacer())
        print(json.dumps(counts), flush=True)
        if not args.all:
            for review in selected:
                row = db.scalar(select(ReviewClassification).where(
                    ReviewClassification.review_id == review.id,
                    ReviewClassification.model_name == settings.groq_model,
                    ReviewClassification.version == CLASSIFICATION_VERSION,
                ))
                print(json.dumps({"source_id": review.source_id, "rating": review.rating,
                                  "review_text": review.review_text, "status": row.status if row else "pending",
                                  "sentiment": row.sentiment if row else None,
                                  "complaint_categories": row.complaint_categories if row else None,
                                  "praised_features": row.praised_features if row else None,
                                  "negative_experiences": row.negative_experiences if row else None,
                                  "input_tokens": row.input_tokens if row else None,
                                  "output_tokens": row.output_tokens if row else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
