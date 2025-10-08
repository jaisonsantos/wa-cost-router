"""Serviços de negócio para gerenciamento de consentimentos (opt-in/out)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.models import ContactChannelOptIn, ContactConsentAudit, OptInStatusEnum
from app.services.contacts.repository import ContactRepository


class ConsentError(Exception):
    """Erro base para operações de consentimento."""


class ConsentValidationError(ConsentError):
    """Falha de validação para operações de opt-in/out."""


class DuplicateOptInError(ConsentError):
    """Tentativa de registrar consentimento duplicado."""


class ContactNotFoundError(ConsentError):
    """Contato não encontrado para o opt-in solicitado."""


@dataclass
class ConsentEvidence:
    """Contém metadados mínimos da evidência registrada."""

    agent: str
    recorded_at: datetime
    channel: str

    def asdict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "recorded_at": self.recorded_at.isoformat(),
            "channel": self.channel,
        }


class ConsentService:
    """Regras de negócio para versionamento e validação de consentimentos."""

    DEFAULT_ALLOWED_SOURCES = {
        "manual",
        "import",
        "webhook",
        "crm_sync",
    }

    def __init__(
        self,
        db: Session,
        *,
        allowed_sources: Optional[set[str]] = None,
        validity_window_days: int = 365,
        future_tolerance_minutes: int = 5,
    ) -> None:
        self.db = db
        self.repository = ContactRepository(db)
        self.allowed_sources = allowed_sources or self.DEFAULT_ALLOWED_SOURCES
        self.validity_window = timedelta(days=validity_window_days)
        self.future_tolerance = timedelta(minutes=future_tolerance_minutes)

    # Public API ---------------------------------------------------------
    def register_opt_in(
        self,
        *,
        org_id,
        contact_id,
        channel: str,
        channel_address: str,
        source: str,
        agent: str,
        legal_basis: Optional[str] = None,
        captured_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
        evidence_uri: Optional[str] = None,
        proof_hash: Optional[str] = None,
        source_metadata: Optional[Dict[str, Any]] = None,
        request_ip: Optional[str] = None,
    ) -> ContactChannelOptIn:
        """Registra ou atualiza um opt-in, respeitando regras de validação."""

        contact = self._get_contact(org_id=org_id, contact_id=contact_id)
        captured_at = self._validate_captured_at(captured_at)
        self._validate_source(source)

        latest = self._get_latest_opt_in(contact_id=contact.id, channel=channel, channel_address=channel_address)

        if latest:
            latest_captured_at = self._normalize_db_timestamp(latest.captured_at)
            same_idempotency = self._check_idempotency(latest, idempotency_key)
            if same_idempotency:
                return latest

            if (
                latest.status == OptInStatusEnum.granted
                and latest_captured_at is not None
                and captured_at <= latest_captured_at
            ):
                raise DuplicateOptInError("Opt-in já registrado com timestamp mais recente.")

            next_version = latest.version + 1
        else:
            next_version = 1

        evidence = ConsentEvidence(agent=agent, recorded_at=datetime.now(timezone.utc), channel=channel)

        payload_metadata = dict(source_metadata or {})
        payload_metadata.update(evidence.asdict())
        if idempotency_key:
            payload_metadata["idempotency_key"] = idempotency_key

        opt_in = ContactChannelOptIn(
            org_id=org_id,
            contact_id=contact.id,
            channel=channel,
            channel_address=channel_address,
            status=OptInStatusEnum.granted,
            version=next_version,
            legal_basis=legal_basis,
            captured_at=captured_at,
            source=source,
            source_metadata=payload_metadata,
            evidence_uri=evidence_uri,
            proof_hash=proof_hash,
        )

        self.db.add(opt_in)
        self._record_audit(
            org_id=org_id,
            contact_id=contact.id,
            opt_in=opt_in,
            channel=channel,
            channel_address=channel_address,
            status=OptInStatusEnum.granted,
            source=source,
            agent=agent,
            request_ip=request_ip,
            evidence_uri=evidence_uri,
            proof_hash=proof_hash,
            context=payload_metadata,
        )
        self.db.commit()
        self.db.refresh(opt_in)
        return opt_in

    def revoke_opt_in(
        self,
        *,
        org_id,
        contact_id,
        channel: str,
        channel_address: str,
        source: str,
        agent: str,
        captured_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
        source_metadata: Optional[Dict[str, Any]] = None,
        evidence_uri: Optional[str] = None,
        proof_hash: Optional[str] = None,
        request_ip: Optional[str] = None,
    ) -> ContactChannelOptIn:
        """Revoga o opt-in mais recente do contato para o canal informado."""

        contact = self._get_contact(org_id=org_id, contact_id=contact_id)
        captured_at = self._validate_captured_at(captured_at)
        self._validate_source(source)

        latest = self._get_latest_opt_in(contact_id=contact.id, channel=channel, channel_address=channel_address)
        if not latest:
            raise ConsentValidationError("Nenhum opt-in ativo encontrado para revogação.")

        same_idempotency = self._check_idempotency(latest, idempotency_key)
        if same_idempotency and latest.status == OptInStatusEnum.revoked:
            return latest

        if latest.status == OptInStatusEnum.revoked and not same_idempotency:
            raise DuplicateOptInError("Opt-in já está revogado para este canal.")

        evidence = ConsentEvidence(agent=agent, recorded_at=datetime.now(timezone.utc), channel=channel)

        payload_metadata = dict(source_metadata or {})
        payload_metadata.update(evidence.asdict())
        payload_metadata["action"] = "revoked"
        if idempotency_key:
            payload_metadata["idempotency_key"] = idempotency_key

        opt_in = ContactChannelOptIn(
            org_id=org_id,
            contact_id=contact.id,
            channel=channel,
            channel_address=channel_address,
            status=OptInStatusEnum.revoked,
            version=latest.version + 1,
            captured_at=captured_at,
            source=source,
            source_metadata=payload_metadata,
            evidence_uri=evidence_uri,
            proof_hash=proof_hash,
        )

        self.db.add(opt_in)
        self._record_audit(
            org_id=org_id,
            contact_id=contact.id,
            opt_in=opt_in,
            channel=channel,
            channel_address=channel_address,
            status=OptInStatusEnum.revoked,
            source=source,
            agent=agent,
            request_ip=request_ip,
            evidence_uri=evidence_uri,
            proof_hash=proof_hash,
            context=payload_metadata,
        )
        self.db.commit()
        self.db.refresh(opt_in)
        return opt_in

    # Helpers ------------------------------------------------------------
    def _get_contact(self, org_id, contact_id):
        contact = self.repository.get_contact(org_id=org_id, contact_id=contact_id)
        if not contact:
            raise ContactNotFoundError("Contato não encontrado para o consentimento solicitado.")
        return contact

    def _validate_source(self, source: str) -> None:
        if source not in self.allowed_sources:
            raise ConsentValidationError(f"Origem de opt-in '{source}' não é permitida.")

    def _validate_captured_at(self, captured_at: Optional[datetime]) -> datetime:
        if captured_at is None:
            captured_at = datetime.now(timezone.utc)
        elif captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)
        else:
            captured_at = captured_at.astimezone(timezone.utc)

        now = datetime.now(timezone.utc)
        if captured_at - now > self.future_tolerance:
            raise ConsentValidationError("Timestamp de consentimento não pode estar no futuro.")
        if now - captured_at > self.validity_window:
            raise ConsentValidationError("Timestamp de consentimento ultrapassa a janela de validade.")
        return captured_at

    def _get_latest_opt_in(self, *, contact_id, channel: str, channel_address: str) -> Optional[ContactChannelOptIn]:
        return (
            self.db.query(ContactChannelOptIn)
            .filter(
                ContactChannelOptIn.contact_id == contact_id,
                ContactChannelOptIn.channel == channel,
                ContactChannelOptIn.channel_address == channel_address,
            )
            .order_by(desc(ContactChannelOptIn.version))
            .first()
        )

    def _check_idempotency(
        self, latest: ContactChannelOptIn, idempotency_key: Optional[str]
    ) -> bool:
        if not idempotency_key:
            return False

        metadata = latest.source_metadata or {}
        return metadata.get("idempotency_key") == idempotency_key

    @staticmethod
    def _normalize_db_timestamp(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _record_audit(
        self,
        *,
        org_id,
        contact_id,
        opt_in: ContactChannelOptIn,
        channel: str,
        channel_address: str,
        status: OptInStatusEnum,
        source: str,
        agent: str,
        request_ip: Optional[str],
        evidence_uri: Optional[str],
        proof_hash: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> None:
        audit_entry = ContactConsentAudit(
            org_id=org_id,
            contact_id=contact_id,
            opt_in=opt_in,
            channel=channel,
            channel_address=channel_address,
            status=status,
            source=source,
            agent=agent,
            request_ip=request_ip,
            evidence_uri=evidence_uri,
            proof_hash=proof_hash,
            context=dict(context) if context else None,
        )

        self.db.add(audit_entry)

