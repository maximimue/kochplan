"""households

Gemeinsamer Haushalt: Supermarkt/Budget/Personen/Geräte wandern vom User in `households`,
Pläne gehören dem Haushalt, Plan-Einträge tragen Portionen je Mitglied.
Bestandsdaten: jeder User bekommt einen eigenen Haushalt mit derselben ID wie der User —
so lassen sich Pläne ohne Zuordnungstabelle umhängen.

Revision ID: e186ebf73e2b
Revises: 0da119c7d2aa
Create Date: 2026-10-28 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'e186ebf73e2b'
down_revision = '0da119c7d2aa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'households',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('supermarket', sa.String(length=30), nullable=True),
        sa.Column('weekly_budget_cents', sa.Integer(), nullable=True),
        sa.Column('household_size', sa.Integer(), nullable=False),
        sa.Column('appliances', postgresql.ARRAY(sa.String(length=40)), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('invite_code', sa.String(length=12), nullable=True),
        sa.Column('invite_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invite_code'),
    )
    op.execute("""
        INSERT INTO households (id, supermarket, weekly_budget_cents, household_size, appliances)
        SELECT id, supermarket, weekly_budget_cents, household_size, appliances FROM users
    """)

    op.add_column('users', sa.Column('household_id', sa.UUID(), nullable=True))
    op.execute("UPDATE users SET household_id = id")
    op.alter_column('users', 'household_id', nullable=False)
    op.create_foreign_key('users_household_id_fkey', 'users', 'households', ['household_id'], ['id'])
    op.create_index(op.f('ix_users_household_id'), 'users', ['household_id'], unique=False)
    op.drop_column('users', 'supermarket')
    op.drop_column('users', 'weekly_budget_cents')
    op.drop_column('users', 'household_size')
    op.drop_column('users', 'appliances')

    op.add_column('meal_plans', sa.Column('household_id', sa.UUID(), nullable=True))
    op.execute("UPDATE meal_plans SET household_id = user_id")
    op.alter_column('meal_plans', 'household_id', nullable=False)
    op.create_foreign_key('meal_plans_household_id_fkey', 'meal_plans', 'households', ['household_id'], ['id'],
                          ondelete='CASCADE')
    op.create_index(op.f('ix_meal_plans_household_id'), 'meal_plans', ['household_id'], unique=False)
    op.create_unique_constraint('meal_plans_household_id_week_start_key', 'meal_plans', ['household_id', 'week_start'])
    op.drop_column('meal_plans', 'user_id')   # entfernt auch Index und Unique-Constraint auf (user_id, week_start)

    op.add_column('plan_entries', sa.Column('portions', postgresql.JSONB(astext_type=sa.Text()),
                                            server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column('plan_entries', sa.Column('total_portions', sa.Numeric(precision=5, scale=2), nullable=True))
    op.execute("UPDATE plan_entries SET total_portions = servings")
    op.alter_column('plan_entries', 'total_portions', nullable=False)
    op.drop_column('plan_entries', 'servings')


def downgrade() -> None:
    op.add_column('plan_entries', sa.Column('servings', sa.Integer(), nullable=True))
    op.execute("UPDATE plan_entries SET servings = GREATEST(1, ROUND(total_portions))")
    op.alter_column('plan_entries', 'servings', nullable=False)
    op.drop_column('plan_entries', 'total_portions')
    op.drop_column('plan_entries', 'portions')

    # Pläne gehen an das älteste Mitglied des Haushalts zurück.
    op.add_column('meal_plans', sa.Column('user_id', sa.UUID(), nullable=True))
    op.execute("""
        UPDATE meal_plans p SET user_id = (
            SELECT u.id FROM users u WHERE u.household_id = p.household_id ORDER BY u.created_at LIMIT 1)
    """)
    op.execute("DELETE FROM meal_plans WHERE user_id IS NULL")
    op.alter_column('meal_plans', 'user_id', nullable=False)
    op.create_foreign_key('meal_plans_user_id_fkey', 'meal_plans', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_meal_plans_user_id'), 'meal_plans', ['user_id'], unique=False)
    op.create_unique_constraint('meal_plans_user_id_week_start_key', 'meal_plans', ['user_id', 'week_start'])
    op.drop_column('meal_plans', 'household_id')

    op.add_column('users', sa.Column('supermarket', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('weekly_budget_cents', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('household_size', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('appliances', postgresql.ARRAY(sa.String(length=40)),
                                     server_default=sa.text("'{}'"), nullable=False))
    op.execute("""
        UPDATE users u SET supermarket = h.supermarket, weekly_budget_cents = h.weekly_budget_cents,
            household_size = h.household_size, appliances = h.appliances
        FROM households h WHERE h.id = u.household_id
    """)
    op.alter_column('users', 'household_size', nullable=False)
    op.drop_index(op.f('ix_users_household_id'), table_name='users')
    op.drop_column('users', 'household_id')
    op.drop_table('households')
