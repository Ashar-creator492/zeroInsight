"""Preserve category-specific evidence for version 8 classifications."""
from alembic import op
import sqlalchemy as sa

revision = "0006_complaint_evidence"
down_revision = "0005_processing_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_classifications", sa.Column("complaint_evidence", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("review_classifications", "complaint_evidence")
