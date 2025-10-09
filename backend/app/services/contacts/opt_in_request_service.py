"""Serviços para orquestrar solicitações de opt-in proativas."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    Contact,
    ContactChannelOptIn,
    ContactOptInRequest,
    OptInRequestStatusEnum,
)
from app.services.contacts.consent_service import ConsentService, DuplicateOptInError

logger = logging.getLogger(__name__)


class OptInRequestError(RuntimeError):
    """Erro base para falhas ao manipular solicitações de opt-in."""


class OptInRequestNotFoundError(OptInRequestError):
    """Indica que a solicitação informada não existe."""


class OptInRequestInvalidStateError(OptInRequestError):
    """Indica que a solicitação não pode ser processada no estado atual."""

class SandboxEmailOptInSender:
    """Implementação de teste para envio de templates por e-mail."""

    def send_opt_in_template(
        self,
        *,
        to_email: str,
        template_id: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        message_id = str(uuid.uuid4())
        logger.info(
            "Dispatching opt-in template",
            extra={
                "to_email": to_email,
                "template_id": template_id,
                "variables": variables,
                "message_id": message_id,
            },
        )
        return {"status": "sent", "message_id": message_id, "success": True}


class OptInRequestService:
    """Orquestra fluxos de disparo e confirmação de opt-ins."""

    ACTIVE_STATUSES = {
        OptInRequestStatusEnum.pending,
        OptInRequestStatusEnum.sending,
        OptInRequestStatusEnum.sent,
    }

    RETRYABLE_STATUSES = {
        OptInRequestStatusEnum.pending,
        OptInRequestStatusEnum.failed,
    }

    def __init__(
        self,
        db: Session,
        *,
        email_sender: Optional[SandboxEmailOptInSender] = None,
        template_id: Optional[str] = None,
        max_attempts: Optional[int] = None,
        retry_minutes: Optional[int] = None,
    ) -> None:
        self.db = db
        self.email_sender = email_sender or SandboxEmailOptInSender()
        self.template_id = template_id or settings.OPT_IN_EMAIL_TEMPLATE_ID
        self.max_attempts = (
            max_attempts if max_attempts is not None else settings.OPT_IN_MAX_ATTEMPTS
        )
        retry_window = (
            retry_minutes if retry_minutes is not None else settings.OPT_IN_RETRY_MINUTES
        )
        self.retry_delay = timedelta(minutes=retry_window)

    # ------------------------------------------------------------------
    def enqueue_request(
        self,
        *,
        org_id: UUID,
        contact_id: UUID,
        requested_channel: str,
        requested_address: str,
        trigger_metadata: Optional[Dict[str, Any]] = None,
        dispatch_immediately: bool = True,
    ) -> Optional[ContactOptInRequest]:
        """Registra (ou reusa) uma solicitação de opt-in e dispara envio."""

        contact = self._get_contact(org_id=org_id, contact_id=contact_id)
        if not contact:
            logger.warning(
                "Skipping opt-in request because contact was not found",
                extra={"org_id": str(org_id), "contact_id": str(contact_id)},
            )
            return None

        if not contact.email:
            logger.info(
                "Contact has no email available to deliver opt-in request",
                extra={
                    "org_id": str(org_id),
                    "contact_id": str(contact_id),
                    "requested_channel": requested_channel,
                },
            )
            return None

        delivery_address = contact.email.strip().lower()
        now = datetime.now(timezone.utc)

        existing = self._find_latest_request(
            org_id=org_id,
            contact_id=contact_id,
            requested_channel=requested_channel,
            requested_address=requested_address,
        )

        metadata = {"trigger": trigger_metadata or {}}

        if existing:
            if existing.status in self.ACTIVE_STATUSES:
                if (
                    dispatch_immediately
                    and existing.status in self.RETRYABLE_STATUSES
                    and self._should_dispatch(existing, reference_time=now)
                ):
                    return self._dispatch(existing)
                return existing

            if (
                existing.status == OptInRequestStatusEnum.failed
                and existing.attempt_count < existing.max_attempts
                and dispatch_immediately
                and self._should_dispatch(existing, reference_time=now)
            ):
                return self._dispatch(existing)

        request = ContactOptInRequest(
            org_id=org_id,
            contact_id=contact_id,
            requested_channel=requested_channel,
            requested_address=requested_address,
            delivery_channel="email",
            delivery_address=delivery_address,
            template_id=self.template_id,
            template_variables={
                "requested_channel": requested_channel,
                "requested_address": requested_address,
            },
            status=OptInRequestStatusEnum.pending,
            attempt_count=0,
            max_attempts=self.max_attempts,
            next_attempt_at=now,
            delivery_metadata=metadata,
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)

        if dispatch_immediately:
            return self._dispatch(request)
        return request

    def process_due_requests(self, *, limit: int = 50) -> List[ContactOptInRequest]:
        """Processa solicitações elegíveis para retry."""

        now = datetime.now(timezone.utc)
        due_requests = (
            self.db.query(ContactOptInRequest)
            .filter(
                ContactOptInRequest.status.in_(list(self.RETRYABLE_STATUSES)),
                ContactOptInRequest.attempt_count < ContactOptInRequest.max_attempts,
                ContactOptInRequest.next_attempt_at.isnot(None),
                ContactOptInRequest.next_attempt_at <= now,
            )
            .order_by(ContactOptInRequest.next_attempt_at.asc())
            .limit(limit)
            .all()
        )

        processed: List[ContactOptInRequest] = []
        for request in due_requests:
            processed.append(self._dispatch(request))
        return processed

    def confirm_from_webhook(
        self,
        *,
        org_id: UUID,
        request_id: UUID,
        channel: str,
        channel_address: str,
        agent: str,
        legal_basis: Optional[str] = None,
        captured_at: Optional[datetime] = None,
        evidence_uri: Optional[str] = None,
        proof_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_ip: Optional[str] = None,
    ) -> ContactOptInRequest:
        """Confirma opt-in via webhook e sincroniza com o catálogo."""

        request = self._get_request_for_org(org_id=org_id, request_id=request_id)
        if not request:
            raise OptInRequestNotFoundError("Solicitação de opt-in não encontrada.")

        if request.status == OptInRequestStatusEnum.confirmed:
            return request

        if request.status == OptInRequestStatusEnum.cancelled:
            raise OptInRequestInvalidStateError(
                "Solicitação de opt-in foi cancelada e não pode ser confirmada."
            )

        consent_service = ConsentService(self.db)
        idempotency_key = f"optin-request:{request.id}"
        try:
            opt_in = consent_service.register_opt_in(
                org_id=org_id,
                contact_id=request.contact_id,
                channel=channel,
                channel_address=channel_address,
                source="webhook",
                agent=agent,
                legal_basis=legal_basis,
                captured_at=captured_at,
                idempotency_key=idempotency_key,
                evidence_uri=evidence_uri,
                proof_hash=proof_hash,
                source_metadata=metadata or {},
                request_ip=request_ip,
            )
        except DuplicateOptInError:
            opt_in = self._load_latest_opt_in(
                contact_id=request.contact_id,
                channel=channel,
                channel_address=channel_address,
            )

        confirmation = {
            "channel": channel,
            "channel_address": channel_address,
            "agent": agent,
            "legal_basis": legal_basis,
            "captured_at": captured_at.isoformat() if captured_at else None,
            "metadata": metadata or {},
            "evidence_uri": evidence_uri,
            "proof_hash": proof_hash,
            "request_ip": request_ip,
        }

        request.status = OptInRequestStatusEnum.confirmed
        request.confirmed_at = datetime.now(timezone.utc)
        request.next_attempt_at = None
        request.last_error = None
        request.confirmation_payload = confirmation
        if opt_in:
            request.opt_in_id = opt_in.id
        self.db.commit()
        self.db.refresh(request)
        return request

    def get_request(self, *, request_id: UUID) -> Optional[ContactOptInRequest]:
        return (
            self.db.query(ContactOptInRequest)
            .filter(ContactOptInRequest.id == request_id)
            .first()
        )

    # ------------------------------------------------------------------
    def _dispatch(self, request: ContactOptInRequest) -> ContactOptInRequest:
        if request.status == OptInRequestStatusEnum.confirmed:
            return request

        if request.attempt_count >= request.max_attempts:
            request.status = OptInRequestStatusEnum.failed
            request.next_attempt_at = None
            request.last_error = "Número máximo de tentativas atingido"
            self.db.commit()
            self.db.refresh(request)
            return request

        now = datetime.now(timezone.utc)
        request.status = OptInRequestStatusEnum.sending
        request.last_attempt_at = now
        request.attempt_count += 1
        request.next_attempt_at = now + self.retry_delay
        self.db.commit()
        self.db.refresh(request)

        metadata = dict(request.delivery_metadata or {})
        attempts: List[Dict[str, Any]] = metadata.setdefault("attempts", [])
        attempt_payload = {
            "attempt": request.attempt_count,
            "at": now.isoformat(),
        }

        try:
            response = self.email_sender.send_opt_in_template(
                to_email=request.delivery_address,
                template_id=request.template_id,
                variables=request.template_variables,
            )
        except Exception as exc:  # pragma: no cover - unexpected failure path
            logger.exception(
                "Failed to dispatch opt-in request",
                extra={
                    "request_id": str(request.id),
                    "org_id": str(request.org_id),
                    "contact_id": str(request.contact_id),
                },
            )
            request.status = (
                OptInRequestStatusEnum.pending
                if request.attempt_count < request.max_attempts
                else OptInRequestStatusEnum.failed
            )
            request.last_error = str(exc)
            request.delivery_metadata = metadata
            attempt_payload.update({"status": "exception", "error": str(exc)})
            attempts.append(attempt_payload)
            if request.status == OptInRequestStatusEnum.failed:
                request.next_attempt_at = None
            self.db.commit()
            self.db.refresh(request)
            return request

        success = True
        status_value = str(response.get("status", "")).lower()
        if response.get("success") is False or status_value in {"error", "failed"}:
            success = False

        attempt_payload.update({
            "status": "success" if success else "error",
            "response": response,
        })
        attempts.append(attempt_payload)

        if success:
            request.status = OptInRequestStatusEnum.sent
            request.next_attempt_at = None
            request.external_message_id = response.get("message_id")
            request.last_error = None
        else:
            request.status = (
                OptInRequestStatusEnum.pending
                if request.attempt_count < request.max_attempts
                else OptInRequestStatusEnum.failed
            )
            request.last_error = response.get("error") or response.get("status") or "send_failed"
            if request.status == OptInRequestStatusEnum.failed:
                request.next_attempt_at = None

        request.delivery_metadata = metadata
        self.db.commit()
        self.db.refresh(request)
        return request

    def _get_contact(self, *, org_id: UUID, contact_id: UUID) -> Optional[Contact]:
        return (
            self.db.query(Contact)
            .filter(
                Contact.org_id == org_id,
                Contact.id == contact_id,
            )
            .first()
        )

    def _find_latest_request(
        self,
        *,
        org_id: UUID,
        contact_id: UUID,
        requested_channel: str,
        requested_address: str,
    ) -> Optional[ContactOptInRequest]:
        return (
            self.db.query(ContactOptInRequest)
            .filter(
                ContactOptInRequest.org_id == org_id,
                ContactOptInRequest.contact_id == contact_id,
                ContactOptInRequest.requested_channel == requested_channel,
                ContactOptInRequest.requested_address == requested_address,
            )
            .order_by(ContactOptInRequest.created_at.desc())
            .first()
        )

    def _should_dispatch(
        self,
        request: ContactOptInRequest,
        *,
        reference_time: datetime,
    ) -> bool:
        if request.status not in self.RETRYABLE_STATUSES:
            return False

        if request.attempt_count >= request.max_attempts:
            return False

        if request.next_attempt_at and request.next_attempt_at > reference_time:
            return False

        return True

    def _get_request_for_org(
        self,
        *,
        org_id: UUID,
        request_id: UUID,
    ) -> Optional[ContactOptInRequest]:
        return (
            self.db.query(ContactOptInRequest)
            .filter(
                ContactOptInRequest.id == request_id,
                ContactOptInRequest.org_id == org_id,
            )
            .first()
        )

    def _load_latest_opt_in(
        self,
        *,
        contact_id: UUID,
        channel: str,
        channel_address: str,
    ) -> Optional[ContactChannelOptIn]:
        return (
            self.db.query(ContactChannelOptIn)
            .filter(
                ContactChannelOptIn.contact_id == contact_id,
                ContactChannelOptIn.channel == channel,
                ContactChannelOptIn.channel_address == channel_address,
            )
            .order_by(ContactChannelOptIn.version.desc())
            .first()
        )
