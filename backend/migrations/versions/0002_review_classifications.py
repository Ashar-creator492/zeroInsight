# Create storage for versioned review classifications.
"""Store Groq review interpretations and processing status."""

from alembic import op
import sqlalchemy as sa

revision = "0002_review_classifications"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_classifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.String(length=64), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=30), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sentiment", sa.String(length=20)),
        sa.Column("complaint_categories", sa.JSON()),
        sa.Column("praised_features", sa.JSON()),
        sa.Column("negative_experiences", sa.JSON()),
        sa.Column("product_attributes", sa.JSON()),
        sa.Column("issue_severity", sa.String(length=20)),
        sa.Column("investigation_areas", sa.JSON()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_id", "model_name", "version", name="uq_classification_review_model_version"),
    )
    op.create_index("ix_review_classifications_review_id", "review_classifications", ["review_id"])


def downgrade() -> None:
    op.drop_index("ix_review_classifications_review_id", table_name="review_classifications")
    op.drop_table("review_classifications")
