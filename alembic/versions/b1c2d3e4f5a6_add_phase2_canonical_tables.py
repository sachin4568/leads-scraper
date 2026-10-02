"""Add phase2 canonical tables: canonical_leads, lead_observations, lead_identities, lead_change_histories, lead_contacts, human_outcome_event_records

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # canonical_leads: master business entity table
    op.execute("""
        CREATE TABLE IF NOT EXISTS canonical_leads (
            id varchar(36) PRIMARY KEY,
            business_name varchar(255) NOT NULL,
            canonical_domain varchar(255),
            canonical_phone varchar(50),
            canonical_email varchar(255),
            google_place_id varchar(255),
            industry varchar(100) NOT NULL,
            address text,
            city varchar(100),
            state varchar(100),
            country varchar(100) DEFAULT 'India',
            website_state varchar(50) DEFAULT 'UNKNOWN',
            business_maturity varchar(50) DEFAULT 'UNKNOWN',
            is_temporary boolean NOT NULL DEFAULT true,
            conflicts jsonb DEFAULT '{}',
            observation_count integer DEFAULT 1,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_business_name ON canonical_leads(business_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_canonical_domain ON canonical_leads(canonical_domain)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_canonical_phone ON canonical_leads(canonical_phone)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_canonical_email ON canonical_leads(canonical_email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_google_place_id ON canonical_leads(google_place_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_industry ON canonical_leads(industry)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_city ON canonical_leads(city)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_state ON canonical_leads(state)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_canonical_leads_country ON canonical_leads(country)")

    # lead_observations: raw historical source data tied to a canonical lead
    op.execute("""
        CREATE TABLE IF NOT EXISTS lead_observations (
            id varchar(36) PRIMARY KEY,
            canonical_lead_id varchar(36) NOT NULL REFERENCES canonical_leads(id) ON DELETE CASCADE,
            source_name varchar(100) NOT NULL,
            source_record_id varchar(255),
            idempotency_key varchar(255) UNIQUE,
            observed_business_name varchar(255),
            observed_phone varchar(50),
            observed_email varchar(255),
            observed_website varchar(255),
            observed_address text,
            observed_city varchar(100),
            match_level varchar(50),
            match_score float,
            match_explanation text,
            observed_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_observations_canonical_lead_id ON lead_observations(canonical_lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_observations_source_name ON lead_observations(source_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_observations_source_record_id ON lead_observations(source_record_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_observations_idempotency_key ON lead_observations(idempotency_key)")

    # lead_identities: multi-signal identity hashes for dedup / canonical lookup
    op.execute("""
        CREATE TABLE IF NOT EXISTS lead_identities (
            id varchar(36) PRIMARY KEY,
            canonical_lead_id varchar(36) NOT NULL REFERENCES canonical_leads(id) ON DELETE CASCADE,
            identity_hash varchar(64) NOT NULL,
            identity_type varchar(50) NOT NULL,
            raw_signal varchar(255) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_identities_canonical_lead_id ON lead_identities(canonical_lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_identities_identity_hash ON lead_identities(identity_hash)")

    # lead_change_histories: audit log of field-level changes over time
    op.execute("""
        CREATE TABLE IF NOT EXISTS lead_change_histories (
            id varchar(36) PRIMARY KEY,
            canonical_lead_id varchar(36) NOT NULL REFERENCES canonical_leads(id) ON DELETE CASCADE,
            observation_id varchar(36) NOT NULL,
            field_name varchar(100) NOT NULL,
            old_value text,
            new_value text,
            changed_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_change_histories_canonical_lead_id ON lead_change_histories(canonical_lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_change_histories_observation_id ON lead_change_histories(observation_id)")

    # lead_contacts: individual contact records per canonical lead
    op.execute("""
        CREATE TABLE IF NOT EXISTS lead_contacts (
            id varchar(36) PRIMARY KEY,
            canonical_lead_id varchar(36) NOT NULL REFERENCES canonical_leads(id) ON DELETE CASCADE,
            full_name varchar(255),
            role varchar(50) NOT NULL DEFAULT 'GENERIC',
            priority_level integer DEFAULT 7,
            phone varchar(50),
            email varchar(255),
            source_name varchar(100),
            confidence float DEFAULT 0.5,
            evidence_reference text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_contacts_canonical_lead_id ON lead_contacts(canonical_lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_contacts_role ON lead_contacts(role)")

    # human_outcome_event_records: human feedback events for ML training
    op.execute("""
        CREATE TABLE IF NOT EXISTS human_outcome_event_records (
            id varchar(36) PRIMARY KEY,
            canonical_lead_id varchar(36) NOT NULL,
            original_prediction varchar(50) NOT NULL,
            original_probability float NOT NULL,
            original_model_version varchar(50) NOT NULL,
            human_outcome varchar(50) NOT NULL,
            reason text,
            decision_timestamp timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_human_outcome_event_records_canonical_lead_id ON human_outcome_event_records(canonical_lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_human_outcome_event_records_human_outcome ON human_outcome_event_records(human_outcome)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS human_outcome_event_records CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_contacts CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_change_histories CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_identities CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_observations CASCADE")
    op.execute("DROP TABLE IF EXISTS canonical_leads CASCADE")
