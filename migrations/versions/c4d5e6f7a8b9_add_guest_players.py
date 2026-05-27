"""add guest_players table and make team_members.user_id nullable

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-05-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1) New table: guest_players
    # ------------------------------------------------------------------
    op.create_table(
        "guest_players",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("identifier", sa.String(255), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("linked_user_id", sa.Integer(), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["linked_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guest_players_team_id", "guest_players", ["team_id"])
    op.create_index("ix_guest_players_identifier", "guest_players", ["identifier"])
    op.create_index("ix_guest_players_linked_user_id", "guest_players", ["linked_user_id"])

    # ------------------------------------------------------------------
    # 2) team_members — relax user_id, add guest_player_id, add CHECK
    # ------------------------------------------------------------------
    # Drop old unique constraint on (team_id, user_id) — replaced by partial unique indexes
    op.drop_constraint("uq_team_members_team_user", "team_members", type_="unique")

    op.alter_column("team_members", "user_id", existing_type=sa.Integer(), nullable=True)

    op.add_column(
        "team_members",
        sa.Column("guest_player_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_team_members_guest_player_id",
        "team_members", "guest_players",
        ["guest_player_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_team_members_guest_player_id", "team_members", ["guest_player_id"])

    # Partial unique indexes (Postgres-specific) — one user per team, one guest per team
    op.create_index(
        "uq_team_members_team_user",
        "team_members",
        ["team_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_team_members_team_guest",
        "team_members",
        ["team_id", "guest_player_id"],
        unique=True,
        postgresql_where=sa.text("guest_player_id IS NOT NULL"),
    )

    # XOR check — exactly one of (user_id, guest_player_id) must be set
    op.create_check_constraint(
        "ck_team_members_one_player_ref",
        "team_members",
        "(user_id IS NOT NULL)::int + (guest_player_id IS NOT NULL)::int = 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_team_members_one_player_ref", "team_members", type_="check")
    op.drop_index("uq_team_members_team_guest", table_name="team_members")
    op.drop_index("uq_team_members_team_user", table_name="team_members")
    op.drop_index("ix_team_members_guest_player_id", table_name="team_members")
    op.drop_constraint("fk_team_members_guest_player_id", "team_members", type_="foreignkey")
    op.drop_column("team_members", "guest_player_id")
    op.alter_column("team_members", "user_id", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint("uq_team_members_team_user", "team_members", ["team_id", "user_id"])

    op.drop_index("ix_guest_players_linked_user_id", table_name="guest_players")
    op.drop_index("ix_guest_players_identifier", table_name="guest_players")
    op.drop_index("ix_guest_players_team_id", table_name="guest_players")
    op.drop_table("guest_players")
