"""4.1: staff-API работает с cards — права app_rw по design §2 и CHECK teaser 1..600 (как в API)."""

from alembic import op

revision = "0003_cards_staff_access"
down_revision = "0002_full_schema"
branch_labels = None
depends_on = None


def upgrade():
    """Выдаёт app_rw SELECT/INSERT/UPDATE на cards (DELETE нет: снятие карточки через archive).

    Публичный каталог по-прежнему читает только view catalog_cards; это контролируют import-linter и SQL-тест.
    """
    op.execute("ALTER TABLE cards DROP CONSTRAINT card_teaser_length")
    op.execute("ALTER TABLE cards ADD CONSTRAINT card_teaser_length CHECK (char_length(teaser_text) BETWEEN 1 AND 600)")
    op.execute("GRANT SELECT, INSERT, UPDATE ON cards TO app_rw")


def downgrade():
    """Возвращает закрытую таблицу и прежний CHECK."""
    op.execute("REVOKE SELECT, INSERT, UPDATE ON cards FROM app_rw")
    op.execute("ALTER TABLE cards DROP CONSTRAINT card_teaser_length")
    op.execute("ALTER TABLE cards ADD CONSTRAINT card_teaser_length CHECK (char_length(teaser_text) <= 600)")
