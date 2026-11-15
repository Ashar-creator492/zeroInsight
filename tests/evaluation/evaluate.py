"""Compare stored classifications with partial audit labels without calling the model."""
import argparse
import json
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import make_engine
from backend.app.models import Review, ReviewClassification
from backend.app.services.classification import ClassificationResult, LUNA_ID


def evaluate_case(label, review, classification):
    """Return observable discrepancies; exact quote matching is not semantic verification."""
    if classification is None or classification.status != "completed":
        return ["classification unavailable"]
    try:
        result = ClassificationResult.model_validate({
            "sentiment": classification.sentiment,
            "complaints": classification.complaint_evidence,
            "praised_features": classification.praised_features,
        })
    except ValidationError:
        return ["invalid classification schema"]
    problems = []
    if "sentiment" in label and label["sentiment"] != result.sentiment:
        problems.append("sentiment mismatch")
    for field, items, noun in (("complaints", result.complaints, "complaints"),
                               ("features", result.praised_features, "features")):
        categories = {item.category for item in items}
        for category in sorted(set(label.get("required_" + field, [])) - categories):
            problems.append("missing " + noun + ": " + category)
        for category in sorted(set(label.get("forbidden_" + field, [])) & categories):
            problems.append("unsupported " + noun + ": " + category)
        if label.get("forbid_all_" + field) and categories:
            problems.append("unexpected " + noun)
        for item in items:
            if not item.evidence_quote.strip() or not any(
                item.evidence_quote in source for source in (review.title or "", review.review_text)
            ):
                problems.append("invalid exact evidence: " + item.category)
    for category, context in label.get("feature_quote_contains", {}).items():
        matching = [item.evidence_quote for item in result.praised_features if item.category == category]
        if matching and not any(context.casefold() in quote.casefold() for quote in matching):
            problems.append("feature evidence lacks labeled context: " + category)
    if classification.unavailable_evidence:
        problems.append("unavailable evidence requires review")
    return problems


def main():
    parser = argparse.ArgumentParser(description="Read-only audit of stored Luna classifications")
    parser.add_argument("--version", choices=["8", "9"], required=True)
    args = parser.parse_args()
    labels = json.loads(Path(__file__).with_name("luna_v9.json").read_text())["cases"]
    settings = get_settings()
    engine = make_engine()
    with engine.connect() as connection:
        if connection.dialect.name != "postgresql":
            raise RuntimeError("The audit requires PostgreSQL read-only transactions")
        connection.execute(text("SET TRANSACTION READ ONLY"))
        with Session(bind=connection) as db:
            for label in labels:
                review = db.scalar(select(Review).where(Review.product_id == LUNA_ID, Review.source_id == label["source_id"]))
                if review is None:
                    problems = ["review unavailable"]
                else:
                    row = db.scalar(select(ReviewClassification).where(
                        ReviewClassification.review_id == review.id,
                        ReviewClassification.version == args.version,
                        ReviewClassification.model_name == settings.groq_model,
                    ))
                    problems = evaluate_case(label, review, row)
                print(json.dumps({"source_id": label["source_id"], "issues": problems}))
    engine.dispose()


if __name__ == "__main__":
    main()
