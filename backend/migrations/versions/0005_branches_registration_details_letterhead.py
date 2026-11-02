"""branches, doctor registration details, per-branch letterhead data

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-02 04:11:46
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_FKS = [
    ("appointments", "branch_id", "fk_appointments_branch"),
    ("encounters", "branch_id", "fk_encounters_branch"),
    ("prescriptions", "branch_id", "fk_prescriptions_branch"),
    ("patients", "registered_branch_id", "fk_patients_branch"),
]


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=60), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("registration", sa.String(length=120), nullable=True),
        sa.Column("footer_text", sa.String(length=300), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "user_branches",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("branch_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "branch_id"),
    )
    for table, col, fk in _FKS:
        with op.batch_alter_table(table) as b:
            b.add_column(sa.Column(col, sa.String(length=32), nullable=True))
            b.create_foreign_key(fk, "branches", [col], ["id"], ondelete="SET NULL")
    with op.batch_alter_table("appointments") as b:
        b.create_index("ix_appointments_branch_id", ["branch_id"])
    with op.batch_alter_table("patients") as b:
        b.add_column(sa.Column("merged_into_id", sa.String(length=32), nullable=True))
        b.create_index("ix_patients_merged_into_id", ["merged_into_id"])
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("phone", sa.String(length=60), nullable=True))
        b.add_column(sa.Column("qualifications", sa.String(length=200), nullable=True))
        b.add_column(sa.Column("registration_no", sa.String(length=80), nullable=True))
        b.add_column(sa.Column("registration_council", sa.String(length=120), nullable=True))
        b.add_column(sa.Column("signature_data_url", sa.Text(), nullable=True))

    # Everything that already exists belongs to the one clinic the install has been serving: create it
    # as the default branch, attach existing records and give every existing user access to it.
    bid = uuid.uuid4().hex
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO branches (id, code, name, is_default, is_active) "
            "VALUES (:id, 'MAIN', 'Main clinic', 1, 1)"
        ),
        {"id": bid},
    )
    for table, col, _ in _FKS:
        bind.execute(sa.text(f"UPDATE {table} SET {col} = :b"), {"b": bid})
    bind.execute(
        sa.text("INSERT INTO user_branches (user_id, branch_id) SELECT id, :b FROM users"), {"b": bid}
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as b:
        for c in ("signature_data_url", "registration_council", "registration_no", "qualifications", "phone"):
            b.drop_column(c)
    with op.batch_alter_table("patients") as b:
        b.drop_index("ix_patients_merged_into_id")
        b.drop_column("merged_into_id")
    with op.batch_alter_table("appointments") as b:
        b.drop_index("ix_appointments_branch_id")
    for table, col, fk in reversed(_FKS):
        with op.batch_alter_table(table) as b:
            b.drop_constraint(fk, type_="foreignkey")
            b.drop_column(col)
    op.drop_table("user_branches")
    op.drop_table("branches")
