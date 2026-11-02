"""security: lockout, two-step verification, audit hash chain

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-02 04:00:32.019321
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prev_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('entry_hash', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_audit_logs_entry_hash'), ['entry_hash'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('mfa_secret', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('mfa_recovery', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('mfa_last_step', sa.Integer(), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('mfa_last_step')
        batch_op.drop_column('mfa_recovery')
        batch_op.drop_column('mfa_secret')
        batch_op.drop_column('mfa_enabled')
        batch_op.drop_column('locked_until')
        batch_op.drop_column('failed_attempts')
        batch_op.drop_column('password_changed_at')
        batch_op.drop_column('must_change_password')

    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_entry_hash'))
        batch_op.drop_column('entry_hash')
        batch_op.drop_column('prev_hash')

