# Add storage for general praise in review classifications.
"""Separate generic praise from evidence-backed feature praise."""

from alembic import op
import sqlalchemy as sa

revision = "0003_general_praise"
down_revision = "0002_review_classifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_classifications", sa.Column("general_praise", sa.JSON()))


def downgrade() -> None:
    op.drop_column("review_classifications", "general_praise")
