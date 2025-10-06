"""encrypt provider credentials"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
import json
import os
import base64
import hashlib
from cryptography.fernet import Fernet

# revision identifiers, used by Alembic.
revision = '002_encrypt_provider_credentials'
down_revision = '001_add_mvp_models'
branch_labels = None
depends_on = None


def _get_fernet():
    secret = os.getenv("APP_SECRET_KEY", "please-change-me")
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def upgrade() -> None:
    op.add_column('provider_credential', sa.Column('credentials_ciphertext', sa.Text(), nullable=True))
    bind = op.get_bind()
    session = Session(bind=bind)
    fernet = _get_fernet()

    try:
        results = session.execute(sa.text("SELECT id, credentials_encrypted FROM provider_credential"))
        for row in results:
            credentials = row.credentials_encrypted
            if credentials is None:
                plaintext = "{}"
            elif isinstance(credentials, str):
                plaintext = credentials
            else:
                plaintext = json.dumps(credentials)
            ciphertext = fernet.encrypt(plaintext.encode()).decode()
            session.execute(
                sa.text(
                    "UPDATE provider_credential SET credentials_ciphertext = :cipher WHERE id = :id"
                ),
                {"cipher": ciphertext, "id": str(row.id)},
            )
        session.commit()
    finally:
        session.close()

    op.drop_column('provider_credential', 'credentials_encrypted')
    op.alter_column(
        'provider_credential',
        'credentials_ciphertext',
        new_column_name='credentials_encrypted',
        existing_type=sa.Text(),
        nullable=False,
    )


def downgrade() -> None:
    op.add_column('provider_credential', sa.Column('credentials_decrypted', sa.JSON(), nullable=True))
    bind = op.get_bind()
    session = Session(bind=bind)
    fernet = _get_fernet()

    try:
        results = session.execute(sa.text("SELECT id, credentials_encrypted FROM provider_credential"))
        for row in results:
            ciphertext = row.credentials_encrypted
            if not ciphertext:
                continue
            plaintext = fernet.decrypt(ciphertext.encode()).decode()
            try:
                data = json.loads(plaintext)
            except json.JSONDecodeError:
                data = plaintext
            if isinstance(data, (dict, list)):
                value = json.dumps(data)
            else:
                value = data
            session.execute(
                sa.text(
                    "UPDATE provider_credential SET credentials_decrypted = :plain WHERE id = :id"
                ),
                {"plain": value, "id": str(row.id)},
            )
        session.commit()
    finally:
        session.close()

    op.drop_column('provider_credential', 'credentials_encrypted')
    op.alter_column(
        'provider_credential',
        'credentials_decrypted',
        new_column_name='credentials_encrypted',
        existing_type=sa.JSON(),
        nullable=True,
    )
