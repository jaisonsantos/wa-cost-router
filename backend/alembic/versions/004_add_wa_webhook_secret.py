"""add wa webhook secret"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
import uuid
import os
import base64
import hashlib
from cryptography.fernet import Fernet

# revision identifiers, used by Alembic.
revision = '004_add_wa_webhook_secret'
down_revision = '003_add_message_job_fk'
branch_labels = None
depends_on = None


def _get_fernet():
    secret = os.getenv("APP_SECRET_KEY", "please-change-me")
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def upgrade() -> None:
    op.add_column('wa_connection', sa.Column('webhook_secret_enc', sa.Text(), nullable=True))

    bind = op.get_bind()
    session = Session(bind=bind)
    fernet = _get_fernet()
    try:
        results = session.execute(
            sa.text("SELECT id, webhook_verify_token FROM wa_connection")
        ).fetchall()
        seen_tokens = set()
        for row in results:
            verify_token = row.webhook_verify_token
            if not verify_token:
                verify_token = f"legacy-verify-{uuid.uuid4()}"
            elif verify_token in seen_tokens:
                verify_token = f"{verify_token}-{uuid.uuid4().hex[:8]}"

            seen_tokens.add(verify_token)

            secret_plain = f"legacy-webhook-secret-{uuid.uuid4()}"
            secret_cipher = fernet.encrypt(secret_plain.encode()).decode()

            session.execute(
                sa.text(
                    "UPDATE wa_connection SET webhook_verify_token = :token, webhook_secret_enc = :secret WHERE id = :id"
                ),
                {"token": verify_token, "secret": secret_cipher, "id": str(row.id)},
            )
        session.commit()
    finally:
        session.close()

    op.alter_column(
        'wa_connection',
        'webhook_secret_enc',
        existing_type=sa.Text(),
        nullable=False,
    )
    op.alter_column(
        'wa_connection',
        'webhook_verify_token',
        existing_type=sa.String(),
        nullable=False,
    )
    op.create_index(
        'uq_wa_connection_webhook_verify_token',
        'wa_connection',
        ['webhook_verify_token'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        'uq_wa_connection_webhook_verify_token',
        table_name='wa_connection',
    )
    op.alter_column(
        'wa_connection',
        'webhook_verify_token',
        existing_type=sa.String(),
        nullable=True,
    )
    op.drop_column('wa_connection', 'webhook_secret_enc')
