"""Track classification attempts and validation failures."""

from alembic import op
import sqlalchemy as sa

revision = "0004_classification_attempts"
down_revision = "0003_general_praise"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_classifications", sa.Column("error_type", sa.String(length=80)))
    op.add_column("review_classifications", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("review_classifications", sa.Column("schema_error_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("review_classifications", sa.Column("evidence_error_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("review_classifications", "evidence_error_count")
    op.drop_column("review_classifications", "schema_error_count")
    op.drop_column("review_classifications", "attempt_count")
    op.drop_column("review_classifications", "error_type")
