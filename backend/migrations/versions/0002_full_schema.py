"""1.6: остальные таблицы design §2 поверх среза каталога; права app_rw по матрице; WM-индекс аудита."""

from alembic import op

revision = "0002_full_schema"
down_revision = "0001_catalog"
branch_labels = None
depends_on = None

# Явные GRANT для каждой таблицы (ALTER DEFAULT PRIVILEGES не используется: новая таблица не получает права молча).
# decisions неизменяемы; TRUNCATE и REFERENCES не выдаются никому.
GRANTS = {
    "staff_users": "SELECT, INSERT, UPDATE",
    "access_requests": "SELECT, INSERT, UPDATE",
    "materials": "SELECT, INSERT, UPDATE, DELETE",
    "grants": "SELECT, INSERT, UPDATE, DELETE",
    "magic_links": "SELECT, INSERT, UPDATE, DELETE",
    "decisions": "SELECT, INSERT",
}


def upgrade():
    """Создаёт таблицы staff_users, materials, access_requests, decisions, grants, magic_links."""
    op.execute("""
        CREATE TABLE staff_users (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          email varchar(254) NOT NULL,
          password_hash text NOT NULL,
          totp_secret_enc text NOT NULL,
          role varchar(16) NOT NULL CONSTRAINT staff_role CHECK (role IN ('reviewer', 'admin')),
          is_active boolean NOT NULL DEFAULT true,
          failed_logins integer NOT NULL DEFAULT 0,
          locked_until timestamptz,
          totp_last_step bigint,
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE UNIQUE INDEX uq_staff_users_email_lower ON staff_users (lower(email))")
    op.execute(
        "ALTER TABLE cards ADD CONSTRAINT fk_cards_created_by_staff_users "
        "FOREIGN KEY (created_by) REFERENCES staff_users (id) ON DELETE RESTRICT"
    )
    op.execute("""
        CREATE TABLE materials (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          card_id uuid NOT NULL REFERENCES cards (id) ON DELETE RESTRICT,
          storage_key varchar(128) NOT NULL UNIQUE,
          original_name varchar(255) NOT NULL,
          mime varchar(100) NOT NULL,
          size bigint NOT NULL,
          sha256 varchar(64) NOT NULL CONSTRAINT material_sha256_hex CHECK (sha256 ~ '^[0-9a-f]{64}$'),
          pages integer NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_materials_card_id ON materials (card_id)")
    op.execute("""
        CREATE TABLE access_requests (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          card_id uuid NOT NULL REFERENCES cards (id) ON DELETE RESTRICT,
          email_enc text,
          email_hash varchar(64) NOT NULL CONSTRAINT request_email_hash_hex CHECK (email_hash ~ '^[0-9a-f]{64}$'),
          display_name varchar(60) CONSTRAINT request_display_name_len CHECK (char_length(display_name) <= 60),
          purpose text CONSTRAINT request_purpose_len CHECK (char_length(purpose) <= 1000),
          status varchar(16) NOT NULL DEFAULT 'pending' CONSTRAINT request_status
            CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'withdrawn', 'purged')),
          created_at timestamptz NOT NULL DEFAULT now(),
          retain_until timestamptz
        )
    """)
    op.execute("CREATE INDEX ix_access_requests_status_created_at ON access_requests (status, created_at)")
    op.execute("CREATE INDEX ix_access_requests_status_retain_until ON access_requests (status, retain_until)")
    op.execute(
        "CREATE UNIQUE INDEX uq_access_requests_pending ON access_requests (card_id, email_hash) "
        "WHERE status = 'pending'"
    )
    op.execute("""
        CREATE TABLE decisions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          request_id uuid NOT NULL UNIQUE REFERENCES access_requests (id) ON DELETE RESTRICT,
          reviewer_id uuid NOT NULL REFERENCES staff_users (id) ON DELETE RESTRICT,
          decision varchar(16) NOT NULL CONSTRAINT decision_kind CHECK (decision IN ('approve', 'reject')),
          reason_code varchar(32) CONSTRAINT decision_reason_code CHECK (reason_code IS NULL OR reason_code IN
            ('insufficient_profile', 'not_qualified', 'conflict_of_interest', 'capacity_limit', 'other')),
          comment_internal text,
          decided_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT decision_reject_has_reason CHECK ((decision = 'reject') = (reason_code IS NOT NULL))
        )
    """)
    op.execute("""
        CREATE TABLE grants (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          request_id uuid NOT NULL UNIQUE REFERENCES access_requests (id) ON DELETE RESTRICT,
          card_id uuid NOT NULL REFERENCES cards (id) ON DELETE RESTRICT,
          viewer_pseudonym varchar(32) NOT NULL UNIQUE,
          material_ids uuid[] NOT NULL,
          allow_download boolean NOT NULL DEFAULT false,
          expires_at timestamptz NOT NULL,
          max_views integer NOT NULL CONSTRAINT grant_max_views_range CHECK (max_views BETWEEN 1 AND 100),
          views_used integer NOT NULL DEFAULT 0,
          revoked_at timestamptz,
          revoked_by uuid REFERENCES staff_users (id) ON DELETE RESTRICT,
          revoke_reason text,
          expiry_processed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT grant_views_used_range CHECK (views_used >= 0 AND views_used <= max_views),
          CONSTRAINT grant_materials_or_revoked CHECK (cardinality(material_ids) >= 1 OR revoked_at IS NOT NULL)
        )
    """)
    op.execute("CREATE INDEX ix_grants_card_id ON grants (card_id)")
    op.execute("CREATE INDEX ix_grants_expires_at ON grants (expires_at)")
    op.execute("""
        CREATE TABLE magic_links (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          grant_id uuid NOT NULL REFERENCES grants (id) ON DELETE CASCADE,
          token_hash varchar(64) NOT NULL UNIQUE
            CONSTRAINT magic_link_token_hash_hex CHECK (token_hash ~ '^[0-9a-f]{64}$'),
          expires_at timestamptz NOT NULL,
          used_at timestamptz,
          used_ip_hash varchar(64),
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_magic_links_grant_id ON magic_links (grant_id)")
    op.execute("CREATE INDEX ix_magic_links_expires_at ON magic_links (expires_at)")
    # Поиск просмотра по WM-коду (design §11): view_id и wm_code лежат в allowlist details
    op.execute("CREATE INDEX ix_audit_events_wm_code ON audit_events ((details->>'wm_code'))")
    for table, privileges in GRANTS.items():
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
        op.execute(f"GRANT {privileges} ON {table} TO app_rw")


def downgrade():
    """Удаляет объекты 0002 в обратном порядке; данные этих таблиц теряются."""
    op.execute("DROP INDEX ix_audit_events_wm_code")
    for table in ("magic_links", "grants", "decisions", "access_requests", "materials"):
        op.execute(f"DROP TABLE {table}")
    op.execute("ALTER TABLE cards DROP CONSTRAINT fk_cards_created_by_staff_users")
    op.execute("DROP TABLE staff_users")
