"""Persist per-image processing outcomes and indexed exact reuse evidence."""
from alembic import op
import sqlalchemy as sa
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {c['name'] for c in inspector.get_columns('claim_images')}
    for column in (
        sa.Column('processing_status', sa.String(24), nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.String(80), nullable=True),
        sa.Column('annotation_error', sa.String(80), nullable=True),
        sa.Column('duplicate_evidence', sa.JSON(), nullable=True),
    ):
        if column.name not in existing:
            op.add_column('claim_images', column)
    indexes = {i['name'] for i in inspector.get_indexes('claim_images')}
    if 'ix_claim_images_file_hash' not in indexes:
        op.create_index('ix_claim_images_file_hash', 'claim_images', ['file_hash'])


def downgrade():
    raise RuntimeError('Dropping processing evidence requires a reviewed data migration')
