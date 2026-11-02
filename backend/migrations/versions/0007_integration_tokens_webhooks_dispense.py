"""integration tokens webhooks dispense

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-02 04:52:56.842197
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    
    op.create_table('api_tokens',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('prefix', sa.String(length=12), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('scopes', sa.JSON(), nullable=False),
    sa.Column('created_by', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used_ip', sa.String(length=64), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    with op.batch_alter_table('api_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_tokens_prefix'), ['prefix'], unique=False)

    op.create_table('webhooks',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('secret_enc', sa.Text(), nullable=False),
    sa.Column('events', sa.JSON(), nullable=False),
    sa.Column('payload', sa.String(length=10), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.String(length=32), nullable=True),
    sa.Column('last_status', sa.String(length=200), nullable=True),
    sa.Column('last_delivery_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('webhook_deliveries',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('webhook_id', sa.String(length=32), nullable=False),
    sa.Column('event', sa.String(length=40), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('response_code', sa.Integer(), nullable=True),
    sa.Column('error', sa.String(length=300), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('webhook_deliveries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_webhook_deliveries_next_attempt_at'), ['next_attempt_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_webhook_deliveries_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_webhook_deliveries_webhook_id'), ['webhook_id'], unique=False)

    with op.batch_alter_table('prescriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dispensed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('dispensed_by', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('dispense_note', sa.String(length=300), nullable=True))

    


def downgrade() -> None:
    
    with op.batch_alter_table('prescriptions', schema=None) as batch_op:
        batch_op.drop_column('dispense_note')
        batch_op.drop_column('dispensed_by')
        batch_op.drop_column('dispensed_at')

    with op.batch_alter_table('webhook_deliveries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_webhook_deliveries_webhook_id'))
        batch_op.drop_index(batch_op.f('ix_webhook_deliveries_status'))
        batch_op.drop_index(batch_op.f('ix_webhook_deliveries_next_attempt_at'))

    op.drop_table('webhook_deliveries')
    op.drop_table('webhooks')
    with op.batch_alter_table('api_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_api_tokens_prefix'))

    op.drop_table('api_tokens')
    
