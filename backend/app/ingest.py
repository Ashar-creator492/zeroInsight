# Validate and import Luna CSV records with stable identifiers and quality reporting.
"""Validate and import the supplied Luna review CSV."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import make_engine
from backend.app.models import Product, Review

PRODUCT_ID = "luna-smartwatch"
PRODUCT_NAME = "Luna Smartwatch"
REQUIRED_COLUMNS = {"id", "product", "review_text", "title", "rating", "date", "source_url"}


class CSVValidationError(ValueError):
    pass


def parse_rating(value: str) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CSVValidationError(f"Invalid rating: {value!r}") from exc
    if not number.is_integer() or not 1 <= number <= 5:
        raise CSVValidationError(f"Invalid rating: {value!r}")
    return int(number)


def parse_date(value: str) -> date | None:
    for format_string in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, format_string).date()
        except ValueError:
            pass
    return None


# Reject malformed input while retaining repeated review text and stable source identifiers.
def load_reviews(path: Path) -> tuple[list[dict], dict]:
    errors: list[str] = []
    parsed: list[dict] = []
    seen_ids: set[str] = set()
    text_counts: Counter[str] = Counter()
    missing = Counter()
    invalid_dates = 0
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or not REQUIRED_COLUMNS.issubset(columns):
            raise CSVValidationError(f"Expected unique columns {sorted(REQUIRED_COLUMNS)}; found {columns}")
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                errors.append(f"Line {line_number}: malformed row")
                continue
            missing.update(key for key in REQUIRED_COLUMNS if not row[key].strip())
            if not all(row[key].strip() for key in ("id", "product", "review_text", "rating", "date", "source_url")):
                errors.append(f"Line {line_number}: missing required value")
                continue
            if row["product"].strip() != PRODUCT_NAME:
                errors.append(f"Line {line_number}: unexpected product")
                continue
            source_id = row["id"].strip()
            if source_id in seen_ids:
                errors.append(f"Line {line_number}: duplicate source ID {source_id}")
                continue
            seen_ids.add(source_id)
            try:
                rating = parse_rating(row["rating"].strip())
            except CSVValidationError as exc:
                errors.append(f"Line {line_number}: {exc}")
                continue
            review_date = parse_date(row["date"].strip())
            if review_date is None:
                invalid_dates += 1
            text_counts[row["review_text"].strip()] += 1
            values = {
                "id": hashlib.sha256(f"{PRODUCT_ID}:{source_id}".encode()).hexdigest(),
                "product_id": PRODUCT_ID,
                "source_id": source_id,
                "review_text": row["review_text"],
                "title": row["title"] if row["title"].strip() else None,
                "rating": rating,
                "review_date": review_date,
                "raw_date": row["date"],
                "source_url": row["source_url"],
            }
            fingerprint_data = {key: value.isoformat() if isinstance(value, date) else value for key, value in values.items() if key != "id"}
            values["content_fingerprint"] = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            parsed.append(values)
    report = {
        "records": len(parsed),
        "columns": columns,
        "missing_values": {key: missing[key] for key in sorted(REQUIRED_COLUMNS)},
        "invalid_dates": invalid_dates,
        "repeated_review_texts": sum(count - 1 for count in text_counts.values() if count > 1),
        "review_text_length": {
            "min": min((len(row["review_text"].strip()) for row in parsed), default=0),
            "max": max((len(row["review_text"].strip()) for row in parsed), default=0),
        },
        "errors": errors,
    }
    if errors:
        raise CSVValidationError(json.dumps(report, indent=2))
    return parsed, report


# Use content fingerprints to skip unchanged imports and update changed source records.
def import_reviews(session: Session, rows: list[dict]) -> dict[str, int]:
    result = {"inserted": 0, "updated": 0, "unchanged": 0}
    if session.get(Product, PRODUCT_ID) is None:
        session.add(Product(id=PRODUCT_ID, name=PRODUCT_NAME))
        session.flush()
    existing = {review.source_id: review for review in session.scalars(select(Review).where(Review.product_id == PRODUCT_ID))}
    for values in rows:
        review = existing.get(values["source_id"])
        if review is None:
            session.add(Review(**values))
            result["inserted"] += 1
        elif review.content_fingerprint == values["content_fingerprint"]:
            result["unchanged"] += 1
        else:
            for key, value in values.items():
                setattr(review, key, value)
            result["updated"] += 1
    session.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Luna reviews into PostgreSQL")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Validate without connecting to PostgreSQL")
    args = parser.parse_args()
    rows, report = load_reviews(args.csv_path)
    if not args.dry_run:
        with Session(make_engine()) as session:
            report.update(import_reviews(session, rows))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
