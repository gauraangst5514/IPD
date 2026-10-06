"""Add processing failure states to existing PostgreSQL enums."""
from alembic import op
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for state in ("PROCESSING_FAILED", "PARTIAL_PROCESSING"):
                op.execute(f"ALTER TYPE claimstatus ADD VALUE IF NOT EXISTS '{state}'")


def downgrade():
    raise RuntimeError("PostgreSQL enum value removal requires a reviewed data migration")
