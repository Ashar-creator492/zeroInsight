# Relational product, review, and versioned classification models.
from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    reviews: Mapped[list["Review"]] = relationship(back_populates="product")


# Preserve the original review and a fingerprint for detecting source changes.
class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("product_id", "source_id", name="uq_review_product_source"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_date: Mapped[date | None] = mapped_column(Date)
    raw_date: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    product: Mapped[Product] = relationship(back_populates="reviews")
    classifications: Mapped[list["ReviewClassification"]] = relationship(back_populates="review")


# Keep analysis, attempts, and evidence scoped to a model and classification version.
class ReviewClassification(Base):
    __tablename__ = "review_classifications"
    __table_args__ = (UniqueConstraint("review_id", "model_name", "version", name="uq_classification_review_model_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    complaint_categories: Mapped[list[str] | None] = mapped_column(JSON)
    complaint_evidence: Mapped[list[dict] | None] = mapped_column(JSON)
    unavailable_evidence: Mapped[list[dict] | None] = mapped_column(JSON)
    praised_features: Mapped[list[dict] | None] = mapped_column(JSON)
    general_praise: Mapped[list[str] | None] = mapped_column(JSON)
    negative_experiences: Mapped[list[str] | None] = mapped_column(JSON)
    product_attributes: Mapped[list[str] | None] = mapped_column(JSON)
    issue_severity: Mapped[str | None] = mapped_column(String(20))
    investigation_areas: Mapped[list[str] | None] = mapped_column(JSON)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str | None] = mapped_column(String(80))
    validation_error: Mapped[str | None] = mapped_column(Text)
    rate_limit_info: Mapped[dict | None] = mapped_column(JSON)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    review: Mapped[Review] = relationship(back_populates="classifications")
