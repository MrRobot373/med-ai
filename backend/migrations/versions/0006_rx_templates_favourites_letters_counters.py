"""rx templates favourites letters counters

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-02 04:23:10.297696
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    
    op.create_table('counters',
    sa.Column('key', sa.String(length=40), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('drug_favourites',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.String(length=32), nullable=False),
    sa.Column('drug', sa.String(length=200), nullable=False),
    sa.Column('dose', sa.String(length=60), nullable=True),
    sa.Column('frequency', sa.String(length=20), nullable=True),
    sa.Column('duration_days', sa.Integer(), nullable=True),
    sa.Column('route', sa.String(length=40), nullable=True),
    sa.Column('instructions', sa.String(length=300), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'drug', name='uq_favourite_user_drug')
    )
    with op.batch_alter_table('drug_favourites', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_drug_favourites_user_id'), ['user_id'], unique=False)

    op.create_table('rx_templates',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('owner_id', sa.String(length=32), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('diagnosis', sa.String(length=500), nullable=True),
    sa.Column('advice', sa.Text(), nullable=True),
    sa.Column('items', sa.JSON(), nullable=False),
    sa.Column('is_shared', sa.Boolean(), nullable=False),
    sa.Column('use_count', sa.Integer(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('rx_templates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_rx_templates_owner_id'), ['owner_id'], unique=False)

    op.create_table('letters',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('number', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('patient_id', sa.String(length=32), nullable=False),
    sa.Column('encounter_id', sa.String(length=32), nullable=True),
    sa.Column('branch_id', sa.String(length=32), nullable=True),
    sa.Column('author_id', sa.String(length=32), nullable=True),
    sa.Column('fields', sa.JSON(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('void_reason', sa.String(length=300), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    with op.batch_alter_table('letters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_letters_kind'), ['kind'], unique=False)
        batch_op.create_index(batch_op.f('ix_letters_patient_id'), ['patient_id'], unique=False)

    


def downgrade() -> None:
    
    with op.batch_alter_table('letters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_letters_patient_id'))
        batch_op.drop_index(batch_op.f('ix_letters_kind'))

    op.drop_table('letters')
    with op.batch_alter_table('rx_templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rx_templates_owner_id'))

    op.drop_table('rx_templates')
    with op.batch_alter_table('drug_favourites', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_drug_favourites_user_id'))

    op.drop_table('drug_favourites')
    op.drop_table('counters')
    
