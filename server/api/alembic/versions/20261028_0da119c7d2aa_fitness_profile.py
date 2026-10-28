"""fitness profile

Revision ID: 0da119c7d2aa
Revises: d65760bac288
Create Date: 2026-10-28 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0da119c7d2aa'
down_revision = 'd65760bac288'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('fitness_goal', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('sex', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('birth_year', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('height_cm', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('weight_kg', sa.Numeric(precision=5, scale=1), nullable=True))
    op.add_column('users', sa.Column('activity_level', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'activity_level')
    op.drop_column('users', 'weight_kg')
    op.drop_column('users', 'height_cm')
    op.drop_column('users', 'birth_year')
    op.drop_column('users', 'sex')
    op.drop_column('users', 'fitness_goal')
