from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    reviews: Mapped[list["Review"]] = relationship(back_populates="product")


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
