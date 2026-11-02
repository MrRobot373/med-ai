"""clinical content signoffs

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-02 05:00:53.706652
"""
from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    
    op.create_table('content_signoffs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('area', sa.String(length=24), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('user_id', sa.String(length=32), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('registration_no', sa.String(length=80), nullable=False),
    sa.Column('registration_council', sa.String(length=120), nullable=True),
    sa.Column('statement', sa.Text(), nullable=False),
    sa.Column('tests_passed', sa.Integer(), nullable=False),
    sa.Column('tests_total', sa.Integer(), nullable=False),
    sa.Column('signed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_reason', sa.String(length=300), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('content_signoffs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_content_signoffs_area'), ['area'], unique=False)
        batch_op.create_index(batch_op.f('ix_content_signoffs_content_hash'), ['content_hash'], unique=False)

    


def downgrade() -> None:
    
    with op.batch_alter_table('content_signoffs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_content_signoffs_content_hash'))
        batch_op.drop_index(batch_op.f('ix_content_signoffs_area'))

    op.drop_table('content_signoffs')
    
