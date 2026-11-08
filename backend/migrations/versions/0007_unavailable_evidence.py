"""Record claims excluded because their supporting quotes were unavailable."""
from alembic import op
import sqlalchemy as sa

revision = "0007_unavailable_evidence"
down_revision = "0006_complaint_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_classifications", sa.Column("unavailable_evidence", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("review_classifications", "unavailable_evidence")
