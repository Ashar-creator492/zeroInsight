# Create the initial product and review tables.
"""Create products and reviews tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("product_id", sa.String(length=80), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("source_id", sa.String(length=200), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_date", sa.Date()),
        sa.Column("raw_date", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
        sa.UniqueConstraint("product_id", "source_id", name="uq_review_product_source"),
    )
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_table("products")
