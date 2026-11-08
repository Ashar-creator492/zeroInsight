"""Store local review embeddings in PostgreSQL."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0008_review_embeddings"
down_revision = "0007_unavailable_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "review_embeddings",
        sa.Column("review_id", sa.String(64), sa.ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("model_name", sa.String(200), primary_key=True),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("review_embeddings")
