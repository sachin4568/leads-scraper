"""Create Phase 1 tenant foundation.

Revision ID: 20260810_0001
Revises:
Create Date: 2026-08-10
"""

from alembic import op

revision = "20260810_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("""
        CREATE TABLE workspaces (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(120) NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
        CREATE TABLE users (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), email varchar(320) NOT NULL UNIQUE, google_subject varchar(255) UNIQUE, created_at timestamptz NOT NULL DEFAULT now());
        CREATE TABLE workspace_members (workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE, user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, role varchar(32) NOT NULL DEFAULT 'member', PRIMARY KEY (workspace_id, user_id));
        CREATE TABLE leads (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES workspaces(id), business_name varchar(255) NOT NULL, website varchar(2048), email varchar(320), phone varchar(50), notes text, deleted_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
        CREATE INDEX ix_leads_workspace_id ON leads(workspace_id);
    """)
    for table in ("workspace_members", "leads"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_workspace_isolation ON {table} USING (workspace_id = current_setting('app.workspace_id', true)::uuid) WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid)"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS leads CASCADE")
    op.execute("DROP TABLE IF EXISTS workspace_members CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS workspaces CASCADE")
