"""Create Phase 2 discovery tables, RLS policies, and source_id uniqueness constraint.

Revision ID: 20260810_0002
Revises: 20260810_0001
Create Date: 2026-08-10
"""

from alembic import op

revision = "20260810_0002"
down_revision = "20260810_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE scrape_jobs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            niche varchar(120) NOT NULL,
            country varchar(100),
            region varchar(100),
            state varchar(100),
            target_lead_count integer NOT NULL DEFAULT 100,
            status varchar(32) NOT NULL DEFAULT 'PENDING',
            sources jsonb,
            leads_scraped integer NOT NULL DEFAULT 0,
            error_message text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_scrape_jobs_workspace_id ON scrape_jobs(workspace_id);

        CREATE TABLE source_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            lead_id uuid REFERENCES leads(id) ON DELETE SET NULL,
            source varchar(64) NOT NULL,
            source_id varchar(255) NOT NULL,
            raw_data jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_source_records_source_source_id UNIQUE (source, source_id)
        );
        CREATE INDEX ix_source_records_workspace_id ON source_records(workspace_id);
        CREATE INDEX ix_source_records_lead_id ON source_records(lead_id);
    """)

    for table in ("scrape_jobs", "source_records"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_workspace_isolation ON {table} USING (workspace_id = current_setting('app.workspace_id', true)::uuid) WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid)"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS source_records CASCADE")
    op.execute("DROP TABLE IF EXISTS scrape_jobs CASCADE")
