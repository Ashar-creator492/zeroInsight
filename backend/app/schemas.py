from datetime import date

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


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
