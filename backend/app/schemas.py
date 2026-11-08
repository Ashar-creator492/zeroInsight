from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class ReviewAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sentiment: str | None
    complaint_categories: list[str] | None
    complaint_evidence: list[dict] | None
    unavailable_evidence: list[dict] | None
    praised_features: list[dict] | None
    general_praise: list[str] | None
    negative_experiences: list[str] | None
    issue_severity: str | None
    investigation_areas: list[str] | None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    source_id: str
    review_text: str
    title: str | None
    rating: int
    review_date: date | None
    source_url: str
    analysis_status: Literal["completed", "failed", "pending"] = "pending"
    classification: ReviewAnalysis | None = None


class ReviewsPage(BaseModel):
    items: list[ReviewOut]
    total: int
    page: int
    page_size: int


class ProductSummary(BaseModel):
    product_id: str
    total_reviews: int
    average_rating: float | None
    rating_distribution: dict[int, int]


class ReviewTrendPoint(BaseModel):
    month: str
    count: int


class ReviewTrend(BaseModel):
    product_id: str
    points: list[ReviewTrendPoint]
    undated_reviews: int
