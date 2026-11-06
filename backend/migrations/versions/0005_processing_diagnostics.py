"""Persist safe validation and rate-limit diagnostics."""

from alembic import op
import sqlalchemy as sa

revision = "0005_processing_diagnostics"
down_revision = "0004_classification_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_classifications", sa.Column("validation_error", sa.Text()))
    op.add_column("review_classifications", sa.Column("rate_limit_info", sa.JSON()))


def downgrade() -> None:
    op.drop_column("review_classifications", "rate_limit_info")
    op.drop_column("review_classifications", "validation_error")
